import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from reference_engine import Controls, spectral, wavelet
from realtime import RealtimeRestoration, RealtimeTransport, export_audio


class RealtimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sr=48000
        t=np.arange(cls.sr*11+77)/cls.sr
        tone=.09*np.sin(2*np.pi*437*t)
        noise=np.random.default_rng(91).normal(0,.003,len(t))
        cls.source=np.column_stack([tone+noise,-.5*(tone+noise)])
        cls.engine=RealtimeRestoration(cls.source,cls.sr,drift=False)

    def test_streamed_wavelet_agrees_with_reference_and_stable_edges(self):
        expected,report=wavelet(self.source,self.sr)
        parts=[]
        for start in range(0,len(self.source),16384):
            parts.append(self.engine.get(start,min(start+16384,len(self.source)),Controls(mode='Wavelet')))
        result=np.concatenate(parts)
        # File endpoints now have a fixed reflected extension. The historical
        # reference wrapped contextual blocks periodically at these endpoints.
        margin=self.sr//2
        np.testing.assert_allclose(result[margin:-margin],expected[margin:-margin],atol=1e-10,rtol=0)
        stable_reference=self.engine.get(0,len(self.source),Controls(mode='Wavelet'))
        np.testing.assert_allclose(result,stable_reference,atol=1e-10,rtol=0)
        np.testing.assert_allclose(result[:,1],-.5*result[:,0],atol=1e-12)

    def test_streamed_stft_agrees_with_offline_reference(self):
        expected=spectral(self.source,self.sr)
        parts=[]
        for start in range(0,len(self.source),16384):
            parts.append(self.engine.get(start,min(start+16384,len(self.source)),Controls(mode='STFT')))
        np.testing.assert_allclose(np.concatenate(parts),expected,atol=1e-7,rtol=0)

    def test_amount_changes_actual_processing_not_cached_mix(self):
        start,stop=16384,32768
        dry=self.source[start:stop]
        for mode in ['STFT','Wavelet','Both']:
            zero=self.engine.get(start,stop,Controls(mode=mode,spectral_amount=0,wavelet_amount=0))
            np.testing.assert_array_equal(zero,dry)
            half=self.engine.get(start,stop,Controls(mode=mode,spectral_amount=.5,wavelet_amount=.5))
            full=self.engine.get(start,stop,Controls(mode=mode))
            self.assertTrue(np.isfinite(half).all())
            self.assertGreater(np.max(np.abs(half-(dry+full)*.5)),1e-8)
        self.assertFalse(hasattr(self.engine,'s'))
        self.assertFalse(hasattr(self.engine,'w'))
        self.assertFalse(hasattr(self.engine,'b'))

    def test_transport_modes_seek_and_exact_sample_count(self):
        current=[Controls(mode='Off')]
        start=3000
        transport=RealtimeTransport(self.engine,lambda:current[0],start)
        transport.start()
        count=0
        try:
            deadline=time.perf_counter()+20
            while not transport.eof:
                if transport.ready.empty() and transport.current is None:
                    if time.perf_counter()>deadline: self.fail('Worker timed out')
                    if transport.error: self.fail(transport.error)
                    time.sleep(.001)
                    continue
                out,n=transport.read(2048)
                self.assertTrue(np.isfinite(out).all())
                if count < 8192:
                    np.testing.assert_array_equal(out[:n],self.source[start+count:start+count+n])
                count+=n
                if n: deadline=time.perf_counter()+20
                if count>32768: current[0]=Controls(mode='Both',wavelet_amount=.5)
                if count>65536: current[0]=Controls(mode='Wavelet')
            self.assertEqual(count,len(self.source)-start)
            self.assertIsNone(transport.error)
        finally: transport.close()
        self.assertFalse(transport.thread.is_alive())

    def test_mono_export_and_zero_signal(self):
        source=np.zeros((9001,1))
        engine=RealtimeRestoration(source,44100,drift=True)
        for mode in ['Off','STFT','Wavelet','Both']:
            np.testing.assert_array_equal(engine.get(0,len(source),Controls(mode=mode)),source)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'result.wav'
            report=export_audio(engine,path,Controls(mode='Both',master=True))
            info=sf.info(path)
            self.assertEqual((info.frames,info.channels,info.samplerate,info.subtype),(9001,1,44100,'PCM_24'))
            self.assertTrue(report['nr_processed_during_export'])

    def test_worker_errors_are_reported(self):
        transport=RealtimeTransport(self.engine,lambda:Controls(mode='invalid'))
        transport.start()
        self.assertTrue(transport.finished.wait(3))
        self.assertIn('Unknown NR mode',transport.error)
        transport.close()

    def test_actual_app_callback_and_eof(self):
        from app import App
        from reference_engine import Mastering
        x=self.source[:9001]
        engine=RealtimeRestoration(x,self.sr,drift=False)
        app=App.__new__(App)
        app.restoration=engine
        app.controls=Controls(mode='Both',master=True)
        app.transport=RealtimeTransport(engine,lambda:app.controls)
        app.transport.start()
        deadline=time.perf_counter()+3
        while app.transport.ready.empty() and time.perf_counter()<deadline:time.sleep(.001)
        app.playing=True
        app.position=0
        app.audio_error=None
        app.mastering=Mastering(self.sr,2)
        try:
            for _ in range(5):
                output=np.empty((2048,2),dtype='float32')
                app.callback(output,2048,None,None)
                self.assertTrue(np.isfinite(output).all())
                self.assertIsNone(app.audio_error)
            self.assertEqual(app.position,len(x))
            self.assertFalse(app.playing)
            self.assertEqual(app.transport.underflows,0)
        finally:app.transport.close()


if __name__=='__main__': unittest.main()
