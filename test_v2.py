from dataclasses import replace
import tempfile, time, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from reference_engine import Controls
from realtime import RealtimeRestoration, RealtimeTransport, export_audio, focus_residual, focus_weights

class Version2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sr=48000
        t=np.arange(cls.sr*2+179)/cls.sr
        x=.15*np.sin(2*np.pi*440*t)+.05*np.sin(2*np.pi*6300*t)+np.random.default_rng(6).normal(0,.009,len(t))
        cls.x=np.column_stack((x,-.7*x)); cls.engine=RealtimeRestoration(cls.x,cls.sr,False)

    def test_focus_selects_removed_signal(self):
        t=np.arange(self.sr*2)/self.sr
        low=.1*np.sin(2*np.pi*440*t); high=.1*np.sin(2*np.pi*6000*t)
        original=np.column_stack((low+high,low-high))
        actual=focus_residual(original,original*.5,self.sr,6000,.5)
        expected=np.column_stack((low+.5*high,low-.5*high))
        np.testing.assert_allclose(actual[24000:-24000],expected[24000:-24000],atol=.0005)
        np.testing.assert_array_equal(focus_weights(np.array([0,100,6000,20000]),6000,.5),[0,0,1,0])

    def test_grain_and_zero_bypass(self):
        for mode in ('STFT','Wavelet','Both'):
            c=Controls(mode=mode)
            a=self.engine.get(0,20000,replace(c,grain=0)); b=self.engine.get(0,20000,replace(c,grain=1))
            self.assertGreater(np.max(np.abs(a-b)),1e-7)
            for focus in (False,True):
                z=self.engine.get(0,20000,replace(c,spectral_amount=0,wavelet_amount=0,focus=focus))
                np.testing.assert_array_equal(z,self.x[:20000])

    def test_targeting_block_stability_and_stereo(self):
        for mode in ('STFT','Wavelet','Both'):
            c=Controls(mode=mode,grain=.8,focus=True)
            full=self.engine.get(0,len(self.x),c)
            parts=np.concatenate([self.engine.get(i,min(len(self.x),i+16384),c) for i in range(0,len(self.x),16384)])
            np.testing.assert_allclose(parts,full,atol=2e-7)
            np.testing.assert_allclose(parts[:,1],-.7*parts[:,0],atol=2e-7)

    def test_loop_repeats_and_keeps_dry_alignment(self):
        a,b=3000,15013; length=b-a
        tr=RealtimeTransport(self.engine,lambda:Controls(mode='Off'),start=90000,block_frames=4096,loop=(a,b));tr.start()
        chunks=[]; originals=[];count=0; deadline=time.monotonic()+15
        try:
            while count<length*3+981:
                if tr.ready.empty() and tr.current is None:
                    self.assertLess(time.monotonic(),deadline); time.sleep(.001); continue
                y,n=tr.read(2048);self.assertIsNone(tr.error)
                chunks.append(y[:n]); originals.append(tr.last_original[:n]);count+=n
            y=np.concatenate(chunks)
            np.testing.assert_array_equal(y,np.concatenate(originals))
            np.testing.assert_array_equal(y[:length],y[length:2*length])
            self.assertTrue(a<=tr.position<b);self.assertFalse(tr.eof)
            np.testing.assert_array_equal(y[length-1:length+1],np.zeros((2,2)))
        finally:tr.close()
        self.assertFalse(tr.thread.is_alive())
        with self.assertRaises(ValueError):RealtimeTransport(self.engine,lambda:Controls(),loop=(0,50))

    def test_float_headroom_and_full_length_exports(self):
        source=np.full((9001,1),1.25);engine=RealtimeRestoration(source,44100,False)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'float.wav'
            report=export_audio(engine,p,Controls(mode='Off',removed=True,preview_original=True),subtype='FLOAT')
            data,rate=sf.read(p,always_2d=True);np.testing.assert_array_equal(data,source)
            self.assertEqual((rate,sf.info(p).subtype,len(data)),(44100,'FLOAT',9001))
            self.assertGreater(report['sample_peak_dbfs'],0)
            with self.assertRaises(ValueError):export_audio(engine,Path(temp)/'pcm.wav',Controls(mode='Off'))
            for subtype in ('PCM_24','FLOAT'):
                c=Controls(mode='Both',focus=True,grain=.8)
                report=export_audio(self.engine,p,replace(c,preview_original=True,removed=True),subtype=subtype)
                actual,_=sf.read(p,always_2d=True)
                np.testing.assert_allclose(actual,self.engine.get(0,len(self.x),c),atol=2e-7)
                self.assertEqual(len(actual),len(self.x));self.assertFalse(report['loop_applied'])

if __name__=='__main__':unittest.main()
