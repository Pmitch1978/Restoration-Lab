"""Version 3 DSP behavior, stereo safety, export routing and preset serialization."""
import json
import time
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace,asdict
import numpy as np
import soundfile as sf
from scipy import signal
from reference_engine import Controls,EQBand,Mastering
from mastering_tools import Multiband,compression_curve,smooth_reduction
from studio_tools import ParametricEQ,StereoWidth,eq_filters
from realtime import export_audio

class StudioTests(unittest.TestCase):
    sr=48000
    def tones(self,seconds=2):
        t=np.arange(round(seconds*self.sr))/self.sr
        l=sum(.03*np.sin(2*np.pi*f*t) for f in (70,500,2200,9000))
        r=sum(.02*np.cos(2*np.pi*f*t) for f in (90,600,2500,8000))
        return np.column_stack((l,r))
    def test_four_band_recombination(self):
        x=self.tones(3);c=Controls(strength=0)
        y,_=Multiband(self.sr,2).process(x,c,(0,0,0,0),2)
        t=np.arange(self.sr*2)/self.sr
        for f in (70,500,2200,9000):
            phase=np.exp(-2j*np.pi*f*t)
            a=abs(np.sum(x[self.sr:,0]*phase));b=abs(np.sum(y[self.sr:,0]*phase))
            self.assertLess(abs(20*np.log10(b/a)),.03)
    def test_attack_release_and_soft_knee(self):
        wanted=np.r_[np.full(4800,12.),np.zeros(48000)]
        fast,_=smooth_reduction(wanted,0,1,50,self.sr)
        slow,_=smooth_reduction(wanted,0,100,500,self.sr)
        self.assertGreater(fast[480],slow[480]+5)
        self.assertLess(fast[-1],slow[-1])
        levels=np.array([-24.,-18.,-12.])
        hard=compression_curve(levels,-18,4,0);soft=compression_curve(levels,-18,4,6)
        self.assertEqual(hard[1],0);self.assertGreater(soft[1],0)
        self.assertAlmostEqual(soft[-1],hard[-1])
    def test_linked_stereo_and_streaming(self):
        x=self.tones();x[:,1]=x[:,0]*.3
        c=Controls(master=True,match=False,strength=1,low_threshold=-40,mid_threshold=-40)
        a=Mastering(self.sr,2).process(x,c,finalizing=True)
        m=Mastering(self.sr,2);b=np.concatenate([m.process(x[i:i+997],c,finalizing=True) for i in range(0,len(x),997)])
        np.testing.assert_allclose(a,b,atol=1e-12)
        np.testing.assert_allclose(a[:,1],a[:,0]*.3,atol=1e-12)
    def test_eq_gain_and_cut(self):
        c=Controls(eq_bands=(EQBand('bell',1000,6,2),)+tuple(EQBand(enabled=False) for _ in range(5)))
        _,h=signal.sosfreqz(eq_filters(c,self.sr),worN=[1000],fs=self.sr)
        self.assertAlmostEqual(20*np.log10(abs(h[0])),6,places=8)
        for kind,low,high in [('highpass',30,5000),('lowpass',5000,30)]:
            bands=(EQBand(kind,500,0,.707),)+c.eq_bands[1:]
            _,h=signal.sosfreqz(eq_filters(replace(c,eq_bands=bands),self.sr),worN=[low,high],fs=self.sr)
            self.assertLess(abs(h[0]),abs(h[1])*.02)
        x=self.tones();np.testing.assert_allclose(ParametricEQ(self.sr,2).process(x,replace(c,eq_enabled=False)),x)
    def test_width_preserves_mid_and_default_is_identity(self):
        x=self.tones();c=Controls()
        np.testing.assert_allclose(StereoWidth(self.sr,2).process(x,c),x,atol=1e-16)
        for width in (0,1.5,2):
            processor=StereoWidth(self.sr,2);y=processor.process(x,replace(c,stereo_width=width,bass_protect=False))
            np.testing.assert_allclose(y.sum(axis=1),x.sum(axis=1),atol=1e-15)
            if width==0:np.testing.assert_allclose(y[-1000:,0],y[-1000:,1],atol=.003)
        mono=x[:,:1];np.testing.assert_array_equal(StereoWidth(self.sr,1).process(mono,c),mono)
        y=StereoWidth(self.sr,2).process(x,replace(c,mono_audition=True));np.testing.assert_array_equal(y[:,0],y[:,1])
    def test_bass_protection_retains_low_width(self):
        t=np.arange(self.sr*3)/self.sr;side=.1*np.sin(2*np.pi*30*t)+.03*np.sin(2*np.pi*6000*t)
        x=np.column_stack((side,-side));c=Controls(stereo_width=2,bass_protect=True,bass_protect_hz=200)
        y=StereoWidth(self.sr,2).process(x,c)
        def amp(z,f):return abs(np.sum(z[self.sr:,0]*np.exp(-2j*np.pi*f*t[self.sr:])))
        self.assertLess(abs(20*np.log10(amp(y,30)/amp(x,30))),1)
        self.assertGreater(20*np.log10(amp(y,6000)/amp(x,6000)),5.5)
    def test_export_ignores_auditions_preserves_stereo_and_rate(self):
        x=self.tones(2)
        class Engine:
            source=x;sr=self.sr
            def get(self,a,b,c):return self.source[a:b].copy()
        c=Controls(master=True,match=False,target_lufs=-18,stereo_width=1.3)
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.wav';b=Path(d)/'b.wav'
            ra=export_audio(Engine(),a,c)
            rb=export_audio(Engine(),b,replace(c,mono_audition=True,low_solo=True,mid_solo=True))
            ay,sr=sf.read(a,always_2d=True);by,_=sf.read(b,always_2d=True)
            np.testing.assert_array_equal(ay,by);self.assertEqual(sr,self.sr);self.assertEqual(ay.shape,x.shape)
            self.assertGreater(np.max(abs(ay[:,0]-ay[:,1])),.01)
            self.assertAlmostEqual(ra['integrated_lufs'],-18,delta=.2)
            self.assertLessEqual(rb['true_peak_dbtp'],-1)
    def test_preset_json_and_export_report_serializable(self):
        c=Controls(stereo_width=1.4,lowmid_attack=33)
        data=json.loads(json.dumps(asdict(c)));data['eq_bands']=tuple(EQBand(**b) for b in data['eq_bands'])
        self.assertEqual(Controls(**data),c)
    def test_invalid_values(self):
        x=self.tones(.1)
        for c in (Controls(low_attack=0),Controls(crossover_mid=300),Controls(high_knee=float('nan'))):
            with self.assertRaises(ValueError):Multiband(self.sr,2).process(x,c,(0,0,0,0),2)
        with self.assertRaises(ValueError):StereoWidth(self.sr,2).process(x,Controls(stereo_width=3))

if __name__=='__main__':unittest.main()
