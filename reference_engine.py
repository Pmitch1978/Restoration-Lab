"""Offline restoration references and stateful playback mastering. No GUI dependency."""
from dataclasses import dataclass
import time
import numpy as np
import pywt
from scipy import signal, ndimage, stats


def db(value):
    return float(20 * np.log10(max(float(value), 1e-15)))


def drift_correct(x, sr):
    duration = len(x) / sr
    if duration < 40:
        return x.copy(), {"slope_db_s": 0., "ending_correction_db": 0.,
                          "note": "Skipped: fewer than two full analysis windows."}
    starts = range(15 * sr, len(x) - 15 * sr - 5 * sr + 1, 5 * sr)
    times, levels = [], []
    for start in starts:
        rms = np.sqrt(np.mean(x[start:start + 5 * sr] ** 2))
        if rms > 1e-12:
            times.append(start / sr + 2.5)
            levels.append(db(rms))
    slope = float(stats.theilslopes(levels, times).slope) if len(times) > 1 else 0.
    applied = max(slope, 0.)
    curve = -applied * np.clip(np.arange(len(x)) / sr - 15, 0, duration - 30)
    return x * (10 ** (curve[:, None] / 20)), {
        "slope_db_s": slope, "ending_correction_db": float(curve[-1]),
        "note": "Level trend can include intentional arrangement changes."}


def spectral(x, sr):
    """Port of recovered suno_spectral_cleanup_exact.py; float32 reference math."""
    nfft, hop = 2048, 512
    if len(x) < nfft:
        raise ValueError("At least 2048 samples are required.")
    freq = np.fft.rfftfreq(nfft, 1 / sr)
    strength = np.interp(freq, [0, 120, 350, 1000, 3000, 6000, 12000, sr / 2],
                         [.025, .04, .09, .24, .48, .77, 1., 1.]).astype('float32')
    floor = 10 ** (-7 / 20)
    y = np.empty(x.shape, dtype=np.float32)
    for ch in range(x.shape[1]):
        _, _, z = signal.stft(x[:, ch].astype('float32'), fs=sr, window='hann',
            nperseg=nfft, noverlap=nfft-hop, boundary='zeros', padded=True)
        mag = np.abs(z).astype('float32')
        energy = np.mean(mag ** 2, axis=0)
        count = max(1, int(np.ceil(.12 * energy.size)))
        quiet = np.argpartition(energy, count-1)[:count]
        noise = np.median(mag[:, quiet], axis=1).astype('float32')
        gain = np.clip(1 - strength[:, None] * noise[:, None] /
                       np.maximum(mag, 1e-9), floor, 1).astype('float32')
        gain = np.clip(ndimage.gaussian_filter(gain, sigma=(1.2, 2.),
                                              mode='nearest'), floor, 1)
        _, result = signal.istft(z * gain, fs=sr, window='hann', nperseg=nfft,
            noverlap=nfft-hop, input_onesided=True, boundary=True)
        y[:, ch] = result[:len(x)]
    return y.astype('float64')


def blocks(x, sr):
    """10 s cores, real 0.5 s context on either side, end reflect padding."""
    for start in range(0, len(x), 10 * sr):
        stop = min(start + 10 * sr, len(x))
        lo, hi = max(0, start - sr // 2), min(len(x), stop + sr // 2)
        block = x[lo:hi].astype('float64', copy=False)
        pad = (-len(block)) % 512
        if pad:
            block = np.pad(block, ((0, pad), (0, 0)), mode='reflect')
        yield start, stop, start-lo, block


def swt(block):
    # SWT along time; returned order is A9, D9, ..., D1.
    return pywt.swt(block, 'sym8', level=9, axis=0, norm=True,
                    trim_approx=True)


def quiet_mask(x, sr):
    frame = max(1, int(round(.020 * sr)))
    count = (len(x) + frame - 1) // frame
    energy = np.empty(count)
    for i in range(count):
        energy[i] = np.mean(x[i*frame:min((i+1)*frame, len(x))] ** 2)
    nquiet = max(1, int(np.ceil(.12 * count)))
    selected = np.argpartition(energy, nquiet-1)[:nquiet]
    flags = np.zeros(count, dtype=bool)
    flags[selected] = True
    return np.repeat(flags, frame)[:len(x)], nquiet / count


def wavelet(x, sr, progress=lambda message: None):
    """Faithful implementation of supplied adaptive wavelet instructions.

    Endpoint padding placement and 5 ms window rounding are explicit choices:
    reflect-pad at block end; nearest integer sample count for uniform_filter1d.
    """
    mask, fraction = quiet_mask(x, sr)
    values = [[] for _ in range(10)]
    for start, stop, offset, block in blocks(x, sr):
        coeff = swt(block)
        local_mask = mask[start:stop]
        for i, c in enumerate(coeff):
            values[i].append(np.abs(c[offset:offset+stop-start][local_mask]).ravel())
        progress(f"Wavelet profile: {stop / sr:.0f} / {len(x) / sr:.0f} s")
    sigmas = np.array([np.median(np.concatenate(v)) / .67448975 for v in values])
    del values
    result = np.empty_like(x, dtype='float64')
    roundtrip = 0.
    floor = 10 ** (-2 / 20)
    window = max(1, int(round(.005 * sr)))
    for start, stop, offset, block in blocks(x, sr):
        coeff = swt(block)
        rebuilt = pywt.iswt(coeff, 'sym8', axis=0, norm=True)
        roundtrip = max(roundtrip, float(np.max(np.abs(rebuilt - block))))
        for c, sigma in zip(coeff, sigmas):
            magnitude = np.sqrt(np.mean(c ** 2, axis=1))
            gain = np.clip(1 - .7 * sigma / (magnitude + 1e-15), floor, 1)
            gain = ndimage.uniform_filter1d(gain, size=window, mode='nearest')
            c *= gain[:, None]
        rebuilt = pywt.iswt(coeff, 'sym8', axis=0, norm=True)
        result[start:stop] = rebuilt[offset:offset+stop-start]
        progress(f"Wavelet restore: {stop / sr:.0f} / {len(x) / sr:.0f} s")
    return result, {"sigmas_A9_D9_to_D1": sigmas.tolist(),
        "quiet_frame_fraction": fraction, "max_coefficient_reduction_db": 2.,
        "roundtrip_max_error": roundtrip, "smoothing_samples": window,
        "rms_change_db": db(np.sqrt(np.mean(result**2))) - db(np.sqrt(np.mean(x**2)))}


@dataclass(frozen=True)
class Controls:
    mode: str = 'Wavelet'
    spectral_amount: float = 1.
    wavelet_amount: float = 1.
    master: bool = False
    match: bool = True
    removed: bool = False
    bass: float = 0.
    mid: float = 0.
    treble: float = 0.
    strength: float = .5
    output_db: float = 0.
    preset: str = 'Natural'


class Restoration:
    """Four cached endpoints. Amount controls interpolate, not rethreshold."""
    def __init__(self, source, sr, drift=True, progress=lambda message: None):
        self.source = np.array(source, dtype='float64', copy=True)
        self.sr = sr
        self.report = {"sample_rate": sr, "channels": source.shape[1],
                       "frames": len(source), "duration": len(source) / sr}
        t = time.perf_counter()
        progress('STFT reference…')
        self.s = spectral(self.source, sr)
        base, dr = drift_correct(self.source, sr) if drift else (self.source, {
            "slope_db_s": 0., "ending_correction_db": 0., "note": "Disabled"})
        progress('Wavelet reference…')
        self.w, wr = wavelet(base, sr, progress)
        progress('Combined reference: drift → STFT → wavelet…')
        combined_base = spectral(base, sr) if drift else self.s
        self.b, br = wavelet(combined_base, sr, progress)
        self.report.update(drift=dr, wavelet=wr, combined_wavelet=br,
            cache_seconds=time.perf_counter()-t,
            cached_bytes=sum(a.nbytes for a in [self.source, self.s, self.w, self.b]),
            combined_order='drift (optional), STFT, adaptive wavelet',
            amount_method='Bilinear dry/processed endpoint interpolation; not threshold scaling',
            restoration_level_compensation=False)
        for a in [self.source, self.s, self.w, self.b]:
            if a.shape != self.source.shape or not np.isfinite(a).all():
                raise ValueError('Invalid restoration output')

    def get(self, start, stop, c):
        x = self.source[start:stop]
        a, b = c.spectral_amount, c.wavelet_amount
        if c.mode == 'Off':
            return x.copy()
        if c.mode == 'STFT':
            return (1-a)*x + a*self.s[start:stop]
        if c.mode == 'Wavelet':
            return (1-b)*x + b*self.w[start:stop]
        return ((1-a)*(1-b)*x + a*(1-b)*self.s[start:stop] +
                (1-a)*b*self.w[start:stop] + a*b*self.b[start:stop])


PRESETS = {'Natural': (0., 0., 0., 2.), 'Warm': (1.5, -.5, -1., 2.5),
           'Punchy': (1., .5, 1., 3.),
           'Bright': (-1., -.5, 3., 2.),
           'Vocal': (-1., 2., 1., 2.),
           'Acoustic': (-1., 1., 2., 1.5),
           'Deep Bass': (3., -1., -1., 2.5),
           'Smooth': (1., 0., -3., 2.)}

PRESET_DESCRIPTIONS = {
    'Natural': 'Flat tone, gentle compression',
    'Warm': 'Fuller lows, softer highs',
    'Punchy': 'Bass and presence, firmer compression',
    'Bright': 'Clearer highs, lighter bass',
    'Vocal': 'Forward midrange and vocal presence',
    'Acoustic': 'Light compression and open highs',
    'Deep Bass': 'Stronger low end, restrained highs',
    'Smooth': 'Softer top end, gentle warmth',
}


def eq_sos(sr, bass, mid, treble):
    """RBJ shelves at 150 Hz/6 kHz and a Q=.7 bell at 1 kHz."""
    sections = []
    for kind, f, gain in [('low', 150., bass), ('bell', 1000., mid),
                          ('high', 6000., treble)]:
        a = 10 ** (gain / 40)
        w = 2*np.pi*f/sr
        cw, sw = np.cos(w), np.sin(w)
        alpha = sw/(2*.7) if kind == 'bell' else sw/np.sqrt(2)
        beta = 2*np.sqrt(a)*alpha
        if kind == 'bell':
            b = [1+alpha*a, -2*cw, 1-alpha*a]
            d = [1+alpha/a, -2*cw, 1-alpha/a]
        elif kind == 'low':
            b = [a*((a+1)-(a-1)*cw+beta), 2*a*((a-1)-(a+1)*cw), a*((a+1)-(a-1)*cw-beta)]
            d = [(a+1)+(a-1)*cw+beta, -2*((a-1)+(a+1)*cw), (a+1)+(a-1)*cw-beta]
        else:
            b = [a*((a+1)+(a-1)*cw+beta), -2*a*((a-1)+(a+1)*cw), a*((a+1)+(a-1)*cw-beta)]
            d = [(a+1)-(a-1)*cw+beta, 2*((a-1)-(a+1)*cw), (a+1)-(a-1)*cw-beta]
        sections.append(np.r_[np.array(b)/d[0], np.array(d)/d[0]])
    return np.array(sections)


class Mastering:
    """POC: three-band EQ, linked RMS compressor, sample-peak safety limiter.

    Not a certified loudness meter or true-peak limiter. No added makeup gain.
    """
    def __init__(self, sr, channels):
        self.sr, self.channels = sr, channels
        self.zi = np.zeros((3, 2, channels))
        self.env = np.zeros(1)
        self.key = None
        self.match_gain = 1.
        self.last_gain = 1.
        self.previous = None
        self.meters = {}

    def process(self, raw, c):
        pb, pm, pt, ratio = PRESETS[c.preset]
        key = (c.bass + pb*c.strength, c.mid + pm*c.strength,
               c.treble + pt*c.strength)
        if key != self.key:
            self.sos = eq_sos(self.sr, *key)
            self.key = key
        y, self.zi = signal.sosfilt(self.sos, raw, axis=0, zi=self.zi)
        pole = np.exp(-1/(.020*self.sr))
        power, self.env = signal.lfilter([1-pole], [1, -pole],
            np.mean(y*y, axis=1), zi=self.env)
        level = 10*np.log10(np.maximum(power, 1e-20))
        effective_ratio = 1+(ratio-1)*c.strength
        reduction = np.maximum(level+18., 0.)*(1-1/effective_ratio)
        gain = 10**(-reduction/20)
        y *= gain[:, None]
        # Output level ramps over each audio block as controls move.
        target = 10**(c.output_db/20)
        y *= np.linspace(self.last_gain, target, len(y))[:, None]
        self.last_gain = target
        ceiling = 10**(-1/20)
        limiting = np.minimum(1., ceiling/np.maximum(np.max(np.abs(y), axis=1), 1e-15))
        y *= limiting[:, None]
        matched = y
        if c.match:
            r0, r1 = np.mean(raw**2), np.mean(y**2)
            wanted = np.clip(np.sqrt(r0/max(r1, 1e-20)), .25, 4.) if r0 > 1e-12 else 1.
            end = self.match_gain + .1*(wanted-self.match_gain)
            matched = y*np.linspace(self.match_gain, end, len(y))[:, None]
            self.match_gain = end
        # The monitor crossfades A/B over one block. Export uses no matching.
        out = matched if c.master else raw
        if self.previous is not None and c.master != self.previous:
            ramp = np.linspace(0, 1, len(y))[:, None]
            other = raw if c.master else matched
            out = other*(1-ramp)+out*ramp
        self.previous = c.master
        self.meters = {'compression_db': float(np.max(reduction)),
                       'limiting_db': -db(np.min(limiting)),
                       'peak_dbfs': db(np.max(np.abs(out)))}
        return out


def export_audio(restoration, path, controls, progress=lambda message: None):
    """Export full length. Matching/removed monitor modes never enter export."""
    import soundfile as sf
    from dataclasses import replace
    c = replace(controls, match=False, removed=False)
    master = Mastering(restoration.sr, restoration.source.shape[1])
    peak = 0.
    with sf.SoundFile(path, 'w', samplerate=restoration.sr,
                      channels=restoration.source.shape[1], subtype='PCM_24') as output:
        for start in range(0, len(restoration.source), 2048):
            stop = min(start+2048, len(restoration.source))
            raw = restoration.get(start, stop, c)
            y = master.process(raw, c) if c.master else raw
            if not np.isfinite(y).all():
                raise ValueError('Non-finite export samples')
            peak = max(peak, float(np.max(np.abs(y))))
            # Refuse PCM clipping instead of silently clipping the file.
            if peak >= 1.:
                raise ValueError('Output exceeds PCM headroom. Lower output or enable mastering.')
            output.write(y)
            progress(stop/len(restoration.source))
    return {'frames': len(restoration.source), 'sample_peak_dbfs': db(peak),
            'mastered': c.master, 'true_peak_verified': False,
            'monitor_loudness_match_exported': False}
