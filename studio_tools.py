"""Stateful parametric EQ and stereo mastering stages; no GUI dependencies."""
import numpy as np
from scipy import signal


def section(band, sr):
    f,g,q=band.frequency,band.gain,band.q
    if not np.isfinite([f,g,q]).all() or not (10<=f<sr*.49 and -18<=g<=18 and .1<=q<=18):
        raise ValueError('EQ: frequency must be below Nyquist, gain ±18 dB, Q 0.1–18.')
    w=2*np.pi*f/sr;cw=np.cos(w);sw=np.sin(w);a=10**(g/40);alpha=sw/(2*q)
    if band.kind=='bell':b=[1+alpha*a,-2*cw,1-alpha*a];d=[1+alpha/a,-2*cw,1-alpha/a]
    elif band.kind=='highpass':b=[(1+cw)/2,-(1+cw),(1+cw)/2];d=[1+alpha,-2*cw,1-alpha]
    elif band.kind=='lowpass':b=[(1-cw)/2,1-cw,(1-cw)/2];d=[1+alpha,-2*cw,1-alpha]
    elif band.kind in ('low_shelf','high_shelf'):
        # Shelves use Q as their damping control.
        beta=2*np.sqrt(a)*alpha
        if band.kind=='low_shelf':
            b=[a*((a+1)-(a-1)*cw+beta),2*a*((a-1)-(a+1)*cw),a*((a+1)-(a-1)*cw-beta)]
            d=[(a+1)+(a-1)*cw+beta,-2*((a-1)+(a+1)*cw),(a+1)+(a-1)*cw-beta]
        else:
            b=[a*((a+1)+(a-1)*cw+beta),-2*a*((a-1)+(a+1)*cw),a*((a+1)+(a-1)*cw-beta)]
            d=[(a+1)-(a-1)*cw+beta,2*((a-1)-(a+1)*cw),(a+1)-(a-1)*cw-beta]
    else:raise ValueError('Unknown EQ filter type')
    return np.r_[np.asarray(b)/d[0],np.asarray(d)/d[0]]


def eq_filters(c,sr):
    if len(c.eq_bands)!=6:raise ValueError('Six EQ bands are required')
    rows=[]
    from dataclasses import replace
    for b in c.eq_bands:
        sos=section(replace(b,frequency=min(b.frequency,sr*.45)),sr)
        if b.enabled and c.eq_enabled:rows.append(sos)
    return np.asarray(rows) if rows else np.array([[1.,0,0,1,0,0]])


class ParametricEQ:
    def __init__(self,sr,channels):
        self.sr,self.channels=sr,channels;self.key=None;self.zi=None
    def process(self,x,c):
        key=(c.eq_enabled,c.eq_bands)
        previous=None
        if key!=self.key:
            if self.zi is not None:previous=(self.sos,self.zi.copy())
            self.sos=eq_filters(c,self.sr);self.zi=np.zeros((len(self.sos),2,self.channels));self.key=key
        y,self.zi=signal.sosfilt(self.sos,x,axis=0,zi=self.zi)
        if previous:
            old,_=signal.sosfilt(previous[0],x,axis=0,zi=previous[1]);r=np.linspace(0,1,len(x))[:,None];y=old*(1-r)+y*r
        return y


class StereoWidth:
    def __init__(self,sr,channels):
        self.sr,self.channels=sr,channels;self.key=None;self.zi=np.zeros((1,2));self.width=1.;self.correlation=1.
    def process(self,x,c):
        if not np.isfinite([c.stereo_width,c.bass_protect_hz]).all() or not (0<=c.stereo_width<=2 and 40<=c.bass_protect_hz<=400):
            raise ValueError('Width must be 0–200%; bass protection 40–400 Hz')
        if self.channels!=2:return x
        mid=(x[:,0]+x[:,1])*.5;side=(x[:,0]-x[:,1])*.5
        key=min(c.bass_protect_hz,self.sr*.4)
        if key!=self.key:
            self.sos=signal.butter(2,key,fs=self.sr,output='sos');self.zi=np.zeros((1,2));self.key=key
        bass,self.zi=signal.sosfilt(self.sos,side,zi=self.zi)
        target=c.stereo_width if c.stereo_enabled else 1.
        pole=np.exp(-1/(.010*self.sr))
        width,_=signal.lfilter([1-pole],[1,-pole],np.full(len(x),target),zi=[pole*self.width])
        self.width=float(width[-1])
        # Keep the original bass side signal; widen only the remaining side.
        side=side+(width-1)*(side-bass if c.bass_protect else side)
        y=np.column_stack((mid+side,mid-side))
        energy=np.sqrt(np.sum(y[:,0]**2)*np.sum(y[:,1]**2))
        self.correlation=float(np.sum(y[:,0]*y[:,1])/energy) if energy>1e-20 else 1.
        if c.mono_audition:y=np.column_stack((mid,mid))
        return y
