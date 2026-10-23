"""Four-band dynamics, playback metering and full-song loudness finalization.

LUFS uses pyloudnorm's BS.1770 meter. Peak verification is a 4x polyphase
estimate, not a claim of hardware or standards certification.
"""
import warnings
import numpy as np
from scipy import signal, ndimage
import pyloudnorm as pyln
from pyloudnorm.iirfilter import IIRfilter


def db(value):
    return float(20*np.log10(max(float(value), 1e-15)))


BANDS=('low','lowmid','mid','high')


def validate(c,sr):
    cross=[c.crossover_low,c.crossover_mid,c.crossover_high]
    values=cross+[c.target_lufs,c.ceiling_dbtp,c.max_limiting_db,c.strength,c.output_db,c.bass,c.mid,c.treble]
    values += [getattr(c,b+'_'+k) for b in BANDS for k in ('threshold','ratio','attack','release','knee','makeup')]
    if not np.isfinite(values).all():raise ValueError('Mastering settings must be finite')
    if not (40<=cross[0]<=1000 and cross[0]*2<=cross[1] and cross[1]*2<=cross[2] and cross[2]<sr*.45):
        raise ValueError('Crossovers must be an octave apart and below 45% of sample rate')
    if not (-30<=c.target_lufs<=-6 and -6<=c.ceiling_dbtp<=-.1 and 0<=c.max_limiting_db<=12 and 0<=c.strength<=1):
        raise ValueError('Loudness settings out of range')
    if not (-18<=c.output_db<=12 and all(-6<=v<=6 for v in (c.bass,c.mid,c.treble))):
        raise ValueError('Tone gain or output gain out of range')
    for b in BANDS:
        for k,lo,hi in [('threshold',-60,0),('ratio',1,20),('attack',.1,200),('release',10,2000),('knee',0,24),('makeup',-18,18)]:
            if not lo<=getattr(c,b+'_'+k)<=hi:raise ValueError(b+' '+k+' out of range')


def compression_curve(level,threshold,ratio,knee):
    above=level-threshold;slope=1-1/ratio
    if knee<=0:return np.maximum(above,0)*slope
    return np.where(above<=-knee/2,0,np.where(above>=knee/2,above*slope,slope*(above+knee/2)**2/(2*knee)))


def smooth_reduction(wanted,previous,attack,release,sr):
    """Attack/release in dB, with continuous state across audio blocks."""
    a=np.exp(-1/(attack*.001*sr));r=np.exp(-1/(release*.001*sr))
    out=np.empty_like(wanted)
    for i,target in enumerate(wanted):
        pole=a if target>previous else r
        previous=pole*previous+(1-pole)*target
        out[i]=previous
    return out,previous


class Multiband:
    """Four LR4 bands, compensated for unity magnitude; linked stereo RMS."""
    def __init__(self,sr,channels):
        self.sr,self.channels=sr,channels;self.key=None;self.states={}
        self.env=np.zeros(4);self.reduction=np.zeros(4);self.mix=np.ones(4);self.makeups=np.zeros(4)
    def filt(self,name,sos,x):
        zi=self.states.setdefault(name,np.zeros((len(sos),2,self.channels)))
        y,self.states[name]=signal.sosfilt(sos,x,axis=0,zi=zi);return y
    def process(self,x,c,gains,preset_ratio):
        validate(c,self.sr)
        key=(c.crossover_low,c.crossover_mid,c.crossover_high);previous=None
        if key!=self.key:
            if self.key is not None:
                from copy import deepcopy
                previous=deepcopy(self)
            self.key=key;self.states={};self.filters=[]
            for f in key:
                pair=[]
                for kind in ('lowpass','highpass'):
                    sos=signal.butter(2,f,kind,fs=self.sr,output='sos');pair.append(np.vstack([sos,sos]))
                self.filters.append(pair)
        bands=[];remaining=x
        for i,(lp,hp) in enumerate(self.filters):
            band=self.filt(f'{i}LP',lp,remaining);remaining=self.filt(f'{i}HP',hp,remaining)
            for j in range(i+1,3):
                l,h=self.filters[j]
                band=self.filt(f'{i}C{j}L',l,band)+self.filt(f'{i}C{j}H',h,band)
            bands.append(band)
        bands.append(remaining)
        if len(gains)==3:gains=(gains[0],gains[1],gains[1],gains[2])
        out=np.zeros_like(x);reductions=[];solo=any(getattr(c,b+'_solo') for b in BANDS)
        pole=np.exp(-1/(.005*self.sr))
        for i,(name,band,gain) in enumerate(zip(BANDS,bands,gains)):
            band=band*10**(gain/20)
            # Max channel power prevents a hard-panned transient escaping detection.
            power,zi=signal.lfilter([1-pole],[1,-pole],np.max(band*band,axis=1),zi=[self.env[i]])
            self.env[i]=zi[0]
            ratio=1+(getattr(c,name+'_ratio')-1)*c.strength
            wanted=compression_curve(10*np.log10(np.maximum(power,1e-20)),getattr(c,name+'_threshold'),ratio,getattr(c,name+'_knee'))
            gr,self.reduction[i]=smooth_reduction(wanted,self.reduction[i],getattr(c,name+'_attack'),getattr(c,name+'_release'),self.sr)
            bypass=getattr(c,name+'_bypass') or not c.multiband
            smoothing=np.exp(-1/(.005*self.sr))
            mix,_=signal.lfilter([1-smoothing],[1,-smoothing],np.full(len(x),0. if bypass else 1.),zi=[smoothing*self.mix[i]])
            self.mix[i]=mix[-1]
            makeup,_=signal.lfilter([1-smoothing],[1,-smoothing],np.full(len(x),getattr(c,name+'_makeup')),zi=[smoothing*self.makeups[i]])
            self.makeups[i]=makeup[-1]
            band=band*10**(((makeup-gr)*mix)[:,None]/20)
            if not solo or getattr(c,name+'_solo'):out+=band
            reductions.append(0. if bypass else float(np.max(gr)))
        if previous is not None:
            from dataclasses import replace
            oldc=replace(c,crossover_low=previous.key[0],crossover_mid=previous.key[1],crossover_high=previous.key[2])
            old,_=previous.process(x,oldc,gains,preset_ratio);r=np.linspace(0,1,len(x))[:,None];out=old*(1-r)+out*r
        return out,reductions


class LiveLoudness:
    """Session-gated integrated / momentary / short-term playback metering.

    Session resets with the playback processor (stop, seek, reload). Metered
    signal includes Level Match when active. No loudness chasing in playback.
    """
    def __init__(self, sr, channels):
        self.sr=sr
        self.hop=round(sr*.1)
        self.pending=np.empty(0)
        self.hops=[]
        self.blocks=[]
        stages=[IIRfilter(3.99984385397,.7071752369554193,1681.9744509555319,sr,'high_shelf_DeMan'),
                IIRfilter(0.,.5003270373253953,38.13547087613982,sr,'high_pass_DeMan')]
        self.sos=np.array([np.r_[f.b,f.a] for f in stages])
        self.zi=np.zeros((2,2,channels))
        self.values={'integrated_lufs':None,'momentary_lufs':None,'short_term_lufs':None}

    @staticmethod
    def loud(e):
        return float(-.691+10*np.log10(e)) if e>0 else None

    def process(self,x):
        y,self.zi=signal.sosfilt(self.sos,x,axis=0,zi=self.zi)
        self.pending=np.r_[self.pending,np.sum(y*y,axis=1)]
        changed=False
        while len(self.pending)>=self.hop:
            self.hops.append(float(np.mean(self.pending[:self.hop])))
            self.hops=self.hops[-30:]
            self.pending=self.pending[self.hop:]
            if len(self.hops)>=4:
                self.blocks.append(float(np.mean(self.hops[-4:])))
                changed=True
        if changed:
            e=np.asarray(self.blocks)
            absolute=e[e>10**((-70+.691)/10)]
            if len(absolute):
                gated=absolute[absolute>np.mean(absolute)*.1]
                self.values['integrated_lufs']=self.loud(float(np.mean(gated))) if len(gated) else None
            self.values['momentary_lufs']=self.loud(float(np.mean(self.hops[-4:])))
            self.values['short_term_lufs']=self.loud(float(np.mean(self.hops))) if len(self.hops)==30 else None
        return self.values.copy()


def integrated_lufs(x,sr):
    if len(x)<round(.4*sr):
        return None
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        value=pyln.Meter(sr,filter_class='DeMan').integrated_loudness(np.asarray(x,dtype='float64'))
    return float(value) if np.isfinite(value) else None


def true_peak(x):
    """4x estimate in chunks, with FIR context across chunk boundaries."""
    peak=0.
    chunk=262144
    for start in range(0,len(x),chunk):
        end=min(start+chunk,len(x))
        a=max(0,start-64);b=min(len(x),end+64)
        up=signal.resample_poly(x[a:b],4,1,axis=0,window=('kaiser',8.6))
        peak=max(peak,float(np.max(np.abs(up[(start-a)*4:(end-a)*4]))))
    return peak


def peak_limit(x,sr,ceiling_dbtp,gain_db):
    """4x linked lookahead envelope, smooth attenuation, rechecked after downsampling."""
    ceiling=10**(ceiling_dbtp/20)
    out=np.empty_like(x)
    peak_reduction=0.
    halo=max(128,round(.08*sr))
    chunk=sr*5
    for start in range(0,len(x),chunk):
        end=min(start+chunk,len(x));a=max(0,start-halo);b=min(len(x),end+halo)
        up=signal.resample_poly(x[a:b],4,1,axis=0,window=('kaiser',8.6))*10**(gain_db/20)
        # Expanding attenuation before smoothing keeps attack below its bound.
        radius=max(1,round(.005*sr*4))
        peaks=ndimage.maximum_filter1d(np.max(np.abs(up),axis=1),2*radius+1,mode='nearest')
        wanted=np.minimum(1.,ceiling/np.maximum(peaks,1e-20))
        gain=ndimage.uniform_filter1d(wanted,2*radius+1,mode='nearest')
        peak_reduction=max(peak_reduction,-db(np.min(gain)))
        down=signal.resample_poly(up*gain[:,None],1,4,axis=0,window=('kaiser',8.6))
        out[start:end]=down[start-a:end-a]
    # Downsample filtering can create overshoot: verify and conservatively trim.
    measured=true_peak(out)
    trim=min(1.,ceiling/max(measured,1e-20))*10**(-.005/20)
    if trim<1:
        out*=trim
        peak_reduction-=db(trim)
    return out,peak_reduction


def finalize(x,sr,c,progress=lambda value:None):
    validate(c,sr)
    before=integrated_lufs(x,sr)
    initial_peak=true_peak(x)
    ceiling=10**(c.ceiling_dbtp/20)
    requested=(c.target_lufs-before) if c.loudness_target and before is not None else 0.
    # Limit how hard a target is permitted to drive peaks; user sets the budget.
    max_gain=c.ceiling_dbtp-db(initial_peak)+c.max_limiting_db if initial_peak>0 else 0.
    gain=min(requested,max_gain)
    out=None;reduction=0.;achieved=None
    for attempt in range(4):
        out,reduction=peak_limit(x,sr,c.ceiling_dbtp,gain)
        achieved=integrated_lufs(out,sr)
        progress(.65+.07*attempt)
        if not c.loudness_target or before is None or achieved is None: break
        error=c.target_lufs-achieved
        if abs(error)<=.15:break
        updated=min(gain+error,max_gain)
        if abs(updated-gain)<.01:break
        gain=updated
    peak=true_peak(out)
    messages=[]
    if c.loudness_target and before is None:
        messages.append('LUFS target unavailable: silence, below gate, or duration shorter than 400 ms.')
    if c.loudness_target and achieved is not None and abs(achieved-c.target_lufs)>.2:
        messages.append('Target not reached within the limiting budget. Achieved loudness is reported; reduce the target or adjust dynamics.')
    if reduction>3:messages.append('More than 3 dB of peak limiting: check transients and pumping by ear.')
    return out,dict(input_lufs=before,integrated_lufs=achieved,
        target_lufs=c.target_lufs if c.loudness_target else None,
        loudness_gain_db=gain,true_peak_dbtp=db(peak),ceiling_dbtp=c.ceiling_dbtp,
        true_peak_verified=True,true_peak_method='4x polyphase estimate; not independently certified',
        peak_limiting_db=reduction,warnings=messages)
