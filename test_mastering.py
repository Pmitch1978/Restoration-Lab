"""Audible preset distinctions and enabling/bypass behavior."""
import unittest
import numpy as np
import tkinter as tk
from reference_engine import Controls, Mastering, PRESETS
from app import App
import test_gui


class MasteringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sr=48000
        t=np.arange(cls.sr)/cls.sr
        cls.t=t
        tone=sum(.02*np.sin(2*np.pi*f*t) for f in (90,1000,9000))
        cls.source=np.column_stack([tone,tone*.8])

    def render(self,preset,**settings):
        controls=Controls(preset=preset,master=True,match=False,**settings)
        processor=Mastering(self.sr,2)
        return np.concatenate([processor.process(self.source[i:i+2048],controls)
            for i in range(0,len(self.source),2048)])

    def level_at(self,audio,f):
        data=audio[self.sr//2:,0]
        phase=np.exp(-2j*np.pi*f*self.t[self.sr//2:])
        return 20*np.log10(abs(np.sum(data*phase))*2/len(data))

    def test_eight_distinct_preset_curves_at_full_strength(self):
        self.assertEqual(len(PRESETS),8)
        outputs={name:self.render(name,strength=1) for name in PRESETS}
        for name,output in outputs.items():
            self.assertTrue(np.isfinite(output).all(),name)
            self.assertLessEqual(np.max(np.abs(output)),10**(-1/20)+1e-12)
        for i,a in enumerate(PRESETS):
            for b in list(PRESETS)[i+1:]:
                self.assertGreater(np.max(np.abs(outputs[a][24000:]-outputs[b][24000:])),1e-5,(a,b))
        high=self.level_at(outputs['Bright'],9000)-self.level_at(outputs['Smooth'],9000)
        bass=self.level_at(outputs['Deep Bass'],90)-self.level_at(outputs['Bright'],90)
        self.assertGreater(high,4.)
        self.assertGreater(bass,2.5)

    def test_zero_strength_converges_and_unmastered_bypasses(self):
        reference=self.render('Natural',strength=0,bass=.7,output_db=-2)
        for name in PRESETS:
            np.testing.assert_allclose(self.render(name,strength=0,bass=.7,output_db=-2),reference,atol=1e-12)
            out=Mastering(self.sr,2).process(self.source,Controls(preset=name,master=False,match=True))
            np.testing.assert_array_equal(out,self.source)

    def test_preset_selection_enables_mastering_and_preserves_monitor_switches(self):
        app=test_gui.GuiTests().make_controls()
        app.status=tk.StringVar(app._interp)
        app.master_on.set(False)
        app.removed.set(False)
        for variable in (app.master_on,app.preset):
            variable.trace_add('write',lambda *args:app.update_controls())
        app.select_preset('Bright')
        self.assertTrue(app.controls.master)
        self.assertEqual(app.controls.preset,'Bright')
        app.bypass.set(True)
        app.select_preset('Smooth')
        self.assertTrue(app.bypass.get())
        self.assertFalse(app.controls.master)
        self.assertIn('BYPASS ALL',app.status.get())
        app.bypass.set(False)
        app.removed.set(True)
        app.select_preset('Vocal')
        self.assertTrue(app.removed.get())
        self.assertIn('LISTEN TO REMOVED',app.status.get())


if __name__=='__main__': unittest.main()
