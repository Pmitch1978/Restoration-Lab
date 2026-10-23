"""Audio behavior tests, including independent FFmpeg loudness cross-checks."""
import json
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from reference_engine import Controls, Mastering
from mastering_tools import Multiband, LiveLoudness, integrated_lufs, true_peak, finalize
from realtime import export_audio


class MasterUpgradeTests(unittest.TestCase):
    sr=48000

    def program(self,seconds=4):
        t=np.arange(round(seconds*self.sr))/self.sr
        rng=np.random.default_rng(42)
        x=(.06*np.sin(2*np.pi*80*t)+.04*np.sin(2*np.pi*1000*t)+
           .025*np.sin(2*np.pi*7500*t)+.015*rng.normal(size=len(t)))
        return np.column_stack([x,x*.75])

    def test_unity_crossover_recombination_flat_magnitude(self):
        x=self.program()
        c=Controls(strength=0)
        y,_=Multiband(self.sr,2).process(x,c,(0,0,0),2)
        # IIR crossover is an all-pass, so compare settled spectral magnitudes.
        for f in (80,1000,7500):
            t=np.arange(len(x)-self.sr)/self.sr
            ph=np.exp(-2j*np.pi*f*t)
            a=abs(np.sum(x[self.sr:,0]*ph));b=abs(np.sum(y[self.sr:,0]*ph))
            self.assertLess(abs(20*np.log10(b/a)),.02)

    def test_low_band_compression_preserves_high_band(self):
        t=np.arange(self.sr*2)/self.sr
        x=np.column_stack([.6*np.sin(2*np.pi*60*t)+.04*np.sin(2*np.pi*9000*t)]*2)
        base=Controls(strength=1,low_ratio=1,mid_ratio=1,high_ratio=1)
        a,_=Multiband(self.sr,2).process(x,base,(0,0,0),2)
        b,gr=Multiband(self.sr,2).process(x,replace(base,low_ratio=6,low_threshold=-30),(0,0,0),2)
        def amp(y,f):return abs(np.sum(y[self.sr:,0]*np.exp(-2j*np.pi*f*t[self.sr:])))
        self.assertLess(20*np.log10(amp(b,60)/amp(a,60)),-10)
        self.assertLess(abs(20*np.log10(amp(b,9000)/amp(a,9000))),.1)
        self.assertGreater(gr[0],10)
        # Stereo relationship is preserved by channel-linked gains.
        np.testing.assert_allclose(b[:,0],b[:,1])

    def test_stream_partition_independence(self):
        x=self.program(1)
        c=Controls()
        a=Mastering(self.sr,2);b=Mastering(self.sr,2)
        whole=a.process(x,c,finalizing=True)
        parts=np.concatenate([b.process(x[i:i+997],c,finalizing=True) for i in range(0,len(x),997)])
        np.testing.assert_allclose(whole,parts,atol=1e-11)

    def test_live_loudness_agrees_with_offline(self):
        x=self.program()
        live=LiveLoudness(self.sr,2)
        for i in range(0,len(x),2048):values=live.process(x[i:i+2048])
        self.assertAlmostEqual(values['integrated_lufs'],integrated_lufs(x,self.sr),delta=.05)
        self.assertIsNotNone(values['short_term_lufs'])

    def test_target_and_oversampled_peak_with_intersample_content(self):
        x=self.program()
        c=Controls(master=True,target_lufs=-16,ceiling_dbtp=-1,max_limiting_db=6)
        out,r=finalize(x,self.sr,c)
        self.assertAlmostEqual(r['integrated_lufs'],-16,delta=.2)
        self.assertLessEqual(true_peak(out),10**(-1/20))
        t=np.arange(self.sr)/self.sr
        # This phase creates peaks between sample instants.
        x=np.column_stack([.99*np.sin(2*np.pi*12000*t+np.pi/4)]*2)
        self.assertGreater(true_peak(x),np.max(np.abs(x))+.1)
        out,r=finalize(x,self.sr,replace(c,loudness_target=False))
        self.assertLessEqual(true_peak(out),10**(-1/20))
        self.assertEqual(out.shape,x.shape)

    def test_budget_warns_when_target_is_unreachable(self):
        x=np.zeros((self.sr*3,2));x[::self.sr//2]=.9
        out,r=finalize(x,self.sr,Controls(master=True,target_lufs=-6,max_limiting_db=0))
        self.assertTrue(any('Target not reached' in w for w in r['warnings']))
        self.assertLess(r['integrated_lufs'],-6.2)
        self.assertLessEqual(true_peak(out),10**(-1/20))

    def test_silence_short_and_invalid_controls(self):
        for count in (100,self.sr):
            x=np.zeros((count,1));out,r=finalize(x,self.sr,Controls())
            np.testing.assert_array_equal(x,out)
            self.assertIsNone(r['integrated_lufs'])
            self.assertTrue(r['warnings'])
        for c in (Controls(crossover_low=900,crossover_high=1000),Controls(target_lufs=float('nan'))):
            with self.assertRaises(ValueError):finalize(self.program(1),self.sr,c)

    def test_encoded_export_and_monitor_settings_do_not_leak(self):
        x=self.program(3)
        class Engine:
            source=x
            sr=self.sr
            def get(self,a,b,c):return self.source[a:b].copy()
        c=Controls(mode='Off',master=True,target_lufs=-16,match=True,removed=True,preview_original=True)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'master.wav'
            r=export_audio(Engine(),p,c)
            y,sr=sf.read(p,always_2d=True)
            self.assertEqual(y.shape,x.shape);self.assertEqual(sr,self.sr)
            self.assertAlmostEqual(integrated_lufs(y,sr),-16,delta=.2)
            self.assertAlmostEqual(r['true_peak_dbtp'],20*np.log10(true_peak(y)),delta=.001)
            self.assertTrue(r['true_peak_verified'])
            if shutil.which('ffmpeg'):
                result=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-af',
                    'loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
                stats=json.loads(result.stderr[result.stderr.rfind('{'):])
                self.assertAlmostEqual(float(stats['input_i']),r['integrated_lufs'],delta=.15)
                self.assertLessEqual(float(stats['input_tp']),-.9)
            dry=Path(d)/'dry.wav'
            r=export_audio(Engine(),dry,replace(c,master=False),subtype='FLOAT')
            y,sr=sf.read(dry,always_2d=True)
            np.testing.assert_allclose(y,x,atol=1e-8)
            self.assertFalse(r['mastered'])

    def test_advanced_controls_and_bypass_preserve_settings(self):
        import tkinter as tk
        from test_gui import GuiTests
        app=GuiTests().make_controls()
        app.advanced_flags={k:tk.BooleanVar(app._interp,value=v) for k,v in
            {'multiband':False,'loudness_target':True}.items()}
        app.vars['target_lufs']=tk.DoubleVar(app._interp,value=-18)
        app.vars['low_ratio']=tk.DoubleVar(app._interp,value=4)
        app.update_controls()
        original=app.controls
        self.assertFalse(original.multiband)
        self.assertEqual(original.target_lufs,-18)
        self.assertEqual(original.low_ratio,4)
        app.bypass.set(True);app.update_controls()
        self.assertFalse(app.controls.master)
        app.bypass.set(False);app.update_controls()
        self.assertEqual(app.controls,original)

    def test_peak_limiting_chunk_boundary_and_mono_44100(self):
        sr=44100
        t=np.arange(sr*11)/sr
        x=(.12*np.sin(2*np.pi*800*t))[:,None]
        x[sr*5-2:sr*5+3]=.99
        c=Controls(master=True,target_lufs=-16,max_limiting_db=12)
        y,r=finalize(x,sr,c)
        self.assertEqual(y.shape,x.shape)
        self.assertAlmostEqual(r['integrated_lufs'],-16,delta=.2)
        # Independent 8x estimate across a 5-second processing boundary.
        oversampled=signal.resample_poly(y,8,1,axis=0,window=('kaiser',10))
        self.assertLessEqual(20*np.log10(np.max(np.abs(oversampled))),-.9)


if __name__=='__main__':unittest.main()
