"""Profile once; restore blocks on demand. File playback, not live input capture."""
from dataclasses import replace
import queue
import threading
import time
import numpy as np
import pywt
from scipy import signal, ndimage
from reference_engine import Controls, Mastering, drift_correct, quiet_mask, blocks, swt, db


def spectral_profile(x, sr):
    profiles = []
    for ch in range(x.shape[1]):
        _, _, z = signal.stft(x[:, ch].astype('float32'), fs=sr, window='hann',
            nperseg=2048, noverlap=1536, boundary='zeros', padded=True)
        mag = np.abs(z).astype('float32')
        energy = np.mean(mag**2, axis=0)
        count = max(1, int(np.ceil(.12*len(energy))))
        quiet = np.argpartition(energy, count-1)[:count]
        profiles.append(np.median(mag[:, quiet], axis=1))
    return np.array(profiles, dtype='float32')


def spectral_apply(x, sr, profile, amount):
    if amount <= 0:
        return x.copy()
    freq = np.fft.rfftfreq(2048, 1/sr)
    strength = np.interp(freq, [0,120,350,1000,3000,6000,12000,sr/2],
                         [.025,.04,.09,.24,.48,.77,1.,1.]).astype('float32')
    out = np.empty_like(x, dtype='float64')
    floor = 10**(-7*amount/20)
    for ch in range(x.shape[1]):
        _, _, z = signal.stft(x[:,ch].astype('float32'), fs=sr, window='hann',
            nperseg=2048, noverlap=1536, boundary='zeros', padded=True)
        mag = np.abs(z).astype('float32')
        gain = np.clip(1-amount*strength[:,None]*profile[ch,:,None]/
                       np.maximum(mag,1e-9), floor, 1).astype('float32')
        gain = np.clip(ndimage.gaussian_filter(gain,(1.2,2.),mode='nearest'),floor,1)
        _, y = signal.istft(z*gain,fs=sr,window='hann',nperseg=2048,
                             noverlap=1536,input_onesided=True,boundary=True)
        out[:,ch] = y[:len(x)]
    return out


def wavelet_profile(x, sr, progress):
    mask, fraction = quiet_mask(x, sr)
    values = [[] for _ in range(10)]
    for start, stop, offset, block in blocks(x, sr):
        coeff = swt(block)
        for i,c in enumerate(coeff):
            values[i].append(np.abs(c[offset:offset+stop-start][mask[start:stop]]).ravel())
        progress(f'Wavelet profile: {stop/sr:.0f} / {len(x)/sr:.0f} s')
    sigma = np.array([np.median(np.concatenate(v))/.67448975 for v in values])
    return sigma, fraction


def wavelet_apply(x, sr, sigmas, amount):
    if amount <= 0:
        return x.copy()
    padding = (-len(x))%512
    block = np.pad(x,((0,padding),(0,0)),mode='reflect') if padding else x
    coeff = swt(block)
    floor = 10**(-2*amount/20)
    for c,sigma in zip(coeff,sigmas):
        magnitude = np.sqrt(np.mean(c*c,axis=1))
        gain = np.clip(1-.7*amount*sigma/(magnitude+1e-15),floor,1)
        gain = ndimage.uniform_filter1d(gain,max(1,round(.005*sr)),mode='nearest')
        c *= gain[:,None]
    return pywt.iswt(coeff,'sym8',axis=0,norm=True)[:len(x)]


def nr_key(c):
    return c.mode, c.spectral_amount, c.wavelet_amount


class RealtimeRestoration:
    def __init__(self,source,sr,drift=True,progress=lambda message:None):
        if sr not in (44100,48000) or source.ndim != 2 or source.shape[1] not in (1,2):
            raise ValueError('Use mono/stereo 44.1 or 48 kHz audio.')
        if len(source)<2048 or not np.isfinite(source).all():
            raise ValueError('Need at least 2048 finite samples.')
        self.source = np.array(source,dtype='float64',copy=True)
        self.sr = sr
        started = time.perf_counter()
        progress('Analyzing gain drift…')
        self.corrected,dr = drift_correct(self.source,sr) if drift else (self.source, {
            'slope_db_s':0.,'ending_correction_db':0.,'note':'Disabled'})
        progress('Analyzing STFT noise profile…')
        self.profile_source = spectral_profile(self.source,sr)
        self.profile_corrected = (spectral_profile(self.corrected,sr)
            if self.corrected is not self.source and dr['ending_correction_db'] != 0
            else self.profile_source)
        self.sigmas,fraction = wavelet_profile(self.corrected,sr,progress)
        # Combined uses the same per-song wavelet profile as standalone wavelet.
        # Do not pre-render a complete processed song to prepare this mode.
        self.report = {'sample_rate':sr,'channels':source.shape[1], 'frames':len(source),
            'duration':len(source)/sr,'analysis_seconds':time.perf_counter()-started,
            'drift':dr,'wavelet_sigmas_A9_D9_to_D1':self.sigmas.tolist(),
            'quiet_frame_fraction':fraction,'whole_song_processed_caches':0,
            'combined_order':'optional drift → STFT → wavelet',
            'combined_profile':'wavelet profile from corrected original; fixed during playback',
            'amount_method':'scale subtraction and attenuation ceiling directly',
            'context_seconds_each_side':.5,'default_core_frames':16384,
            'static_loudness_compensation':False}
        self.waveform_peaks = self.envelope(self.source,1000)

    @staticmethod
    def envelope(x,count):
        edges = np.linspace(0,len(x),min(count,len(x))+1,dtype=int)
        return np.array([np.max(np.abs(x[a:b])) for a,b in zip(edges[:-1],edges[1:])])

    def get(self,start,stop,c):
        if not (0 <= start <= stop <= len(self.source)):
            raise ValueError('Invalid source range')
        if start==stop:
            return self.source[start:stop].copy()
        if c.mode=='Off':
            return self.source[start:stop].copy()
        if c.mode not in ('STFT','Wavelet','Both'):
            raise ValueError('Unknown NR mode')
        a,b = float(np.clip(c.spectral_amount,0,1)),float(np.clip(c.wavelet_amount,0,1))
        # Amount=0 is exact bypass, including optional drift correction.
        if ((c.mode=='STFT' and a==0) or (c.mode=='Wavelet' and b==0)
            or (c.mode=='Both' and a==0 and b==0)):
            return self.source[start:stop].copy()
        # Align STFT frame origins with the whole-file 512-sample grid.
        use_wavelet = c.mode in ('Wavelet','Both') and b>0
        logical_lo = (start-self.sr//2)//512*512
        logical_hi = stop+self.sr//2
        lo = max(0,logical_lo)
        hi = min(len(self.source),logical_hi)
        x = ((1-b)*self.source[lo:hi]+b*self.corrected[lo:hi]
             if use_wavelet else self.source[lo:hi])
        offset=start-lo
        if use_wavelet:
            # A fixed reflected extension at FILE edges prevents SWT's periodic
            # block boundary from changing the song opening/ending by core size.
            left,right = max(0,-logical_lo),max(0,logical_hi-len(self.source))
            if left or right:
                x=np.pad(x,((left,right),(0,0)),mode='reflect')
            offset=start-logical_lo
        if c.mode in ('STFT','Both') and a>0:
            profile = ((1-b)*self.profile_source+b*self.profile_corrected
                       if use_wavelet else self.profile_source)
            x = spectral_apply(x,self.sr,profile,a)
        if use_wavelet:
            x = wavelet_apply(x,self.sr,self.sigmas,b)
        return np.array(x[offset:offset+stop-start],dtype='float64',copy=True)


class RealtimeTransport:
    """Worker performs NR, callback consumes blocks. No transform in callback.

    One ready block plus at most one in-flight block. Pausing closes transport;
    resuming constructs a new one at the last consumed sample.
    """
    def __init__(self,engine,controls,start=0,block_frames=16384):
        self.engine,self.controls = engine,controls
        self.block_frames = block_frames
        self.position = start
        self.ready = queue.Queue(maxsize=1)
        self.cancel = threading.Event()
        self.finished = threading.Event()
        self.current = None
        self.offset = 0
        self.error = None
        self.underflows = 0
        self.max_processing_seconds = 0.
        self.last_load = 0.
        self.last_reduction_db = 0.
        self.thread = threading.Thread(target=self._produce,args=(start,),daemon=True)

    def start(self):
        self.thread.start()

    def _produce(self,start):
        previous = None
        try:
            while start<len(self.engine.source) and not self.cancel.is_set():
                # Backpressure before taking a fresh control snapshot.
                while self.ready.full() and not self.cancel.wait(.002):
                    pass
                if self.cancel.is_set(): break
                stop = min(start+self.block_frames,len(self.engine.source))
                c = self.controls()
                t = time.perf_counter()
                y = self.engine.get(start,stop,c)
                if previous is not None and nr_key(c)!=nr_key(previous):
                    fade = min(2048,len(y))
                    old = self.engine.get(start,start+fade,previous)
                    ramp = np.linspace(0,1,fade)[:,None]
                    y[:fade] = old*(1-ramp)+y[:fade]*ramp
                if not np.isfinite(y).all():
                    raise ValueError('Non-finite NR output')
                elapsed = time.perf_counter()-t
                self.max_processing_seconds = max(self.max_processing_seconds,elapsed)
                self.last_load = elapsed / ((stop-start)/self.engine.sr)
                raw=self.engine.source[start:stop]
                # RMS difference is a level-change indicator, not noise purity.
                self.last_reduction_db = max(0.,db(np.sqrt(np.mean(raw*raw)))-db(np.sqrt(np.mean(y*y))))
                while not self.cancel.is_set():
                    try:
                        self.ready.put((start,y),timeout=.02)
                        break
                    except queue.Full: pass
                start=stop
                previous=c
        except Exception as exc:
            self.error=str(exc)
        finally:
            self.finished.set()

    def read(self,frames):
        out=np.zeros((frames,self.engine.source.shape[1]),dtype='float64')
        valid=0
        while valid<frames:
            if self.current is None:
                try:
                    start,self.current=self.ready.get_nowait()
                except queue.Empty:
                    if not self.eof and not self.error: self.underflows+=1
                    break
                if start!=self.position:
                    self.error='Playback sequence mismatch'
                    self.current=None
                    break
                self.offset=0
            n=min(frames-valid,len(self.current)-self.offset)
            out[valid:valid+n]=self.current[self.offset:self.offset+n]
            valid+=n
            self.position+=n
            self.offset+=n
            if self.offset==len(self.current): self.current=None
        return out,valid

    @property
    def eof(self):
        return self.position>=len(self.engine.source)

    def close(self):
        self.cancel.set()
        if self.thread.is_alive(): self.thread.join(timeout=5.)


def export_audio(engine,path,controls,progress=lambda value:None):
    """Same NR blocks, fixed settings; mastering uses 2048-sample device blocks."""
    import soundfile as sf
    c=replace(controls,match=False,removed=False)
    master=Mastering(engine.sr,engine.source.shape[1])
    peak=0.
    with sf.SoundFile(path,'w',samplerate=engine.sr,channels=engine.source.shape[1],subtype='PCM_24') as f:
        for start in range(0,len(engine.source),16384):
            stop=min(start+16384,len(engine.source))
            y=engine.get(start,stop,c)
            for offset in range(0,len(y),2048):
                part=y[offset:offset+2048]
                output=master.process(part,c) if c.master else part
                if not np.isfinite(output).all(): raise ValueError('Non-finite export')
                peak=max(peak,float(np.max(np.abs(output))))
                if peak>=1: raise ValueError('PCM overload. Lower gain or enable mastering.')
                f.write(output)
            progress(stop/len(engine.source))
    return {'frames':len(engine.source),'sample_peak_dbfs':db(peak),'mastered':c.master,
            'true_peak_verified':False,'nr_processed_during_export':True}
