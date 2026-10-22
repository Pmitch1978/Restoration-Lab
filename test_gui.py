"""Control mapping and headless artwork tests; real Tk checks run on the Mac."""
import unittest
import tkinter as tk
from types import SimpleNamespace
from app import App
from metal_ui import Renderer, KNOBS, SLIDERS, BUTTONS, WIDTH, HEIGHT
from preview_gui import demo_state


class GuiTests(unittest.TestCase):
    def make_controls(self):
        app=App.__new__(App)
        interp=tk.Tcl()
        app.mode=tk.StringVar(interp,value='Both')
        app.preset=tk.StringVar(interp,value='Natural')
        app.master_on=tk.BooleanVar(interp,value=True)
        app.match=tk.BooleanVar(interp,value=True)
        app.removed=tk.BooleanVar(interp,value=True)
        app.bypass=tk.BooleanVar(interp,value=False)
        app.vars={key:tk.DoubleVar(interp,value=spec[7]) for key,spec in {**KNOBS,**SLIDERS}.items()}
        app.vars['spectral_amount'].set(65)
        app.vars['wavelet_amount'].set(80)
        app.vars['output_db'].set(-1)
        app._interp=interp
        return app

    def test_control_mapping_and_lossless_bypass_restore(self):
        app=self.make_controls()
        app.update_controls()
        original=app.controls
        self.assertEqual(original.mode,'Both')
        self.assertEqual(original.spectral_amount,.65)
        self.assertEqual(original.wavelet_amount,.8)
        self.assertEqual(original.output_db,-1)
        app.bypass.set(True)
        app.update_controls()
        self.assertEqual(app.controls.mode,'Off')
        self.assertFalse(app.controls.master or app.controls.removed or app.controls.match)
        app.bypass.set(False)
        app.update_controls()
        self.assertEqual(app.controls,original)

    def test_master_nr_slider_scales_amounts_and_zero_bypasses(self):
        app=self.make_controls()
        app.vars['nr_strength'].set(50)
        app.update_controls()
        self.assertAlmostEqual(app.controls.spectral_amount,.325)
        self.assertAlmostEqual(app.controls.wavelet_amount,.4)
        self.assertEqual(app.vars['spectral_amount'].get(),65)
        self.assertEqual(app.vars['wavelet_amount'].get(),80)
        self.assertTrue(app.controls.master)
        app.vars['nr_strength'].set(0)
        app.update_controls()
        self.assertEqual(app.controls.spectral_amount,0)
        self.assertEqual(app.controls.wavelet_amount,0)
        self.assertTrue(app.controls.master)

    def test_knob_clamping_and_keyboard(self):
        app=self.make_controls()
        app.focus_control='bass'
        app.set_value('bass',100)
        self.assertEqual(app.vars['bass'].get(),6)
        app.key_press(SimpleNamespace(keysym='Home',state=0))
        self.assertEqual(app.vars['bass'].get(),-6)
        app.key_press(SimpleNamespace(keysym='Up',state=1))
        self.assertAlmostEqual(app.vars['bass'].get(),-5.99)
        app.key_press(SimpleNamespace(keysym='End',state=0))
        self.assertEqual(app.vars['bass'].get(),6)

    def test_artwork_all_views_and_empty_session(self):
        renderer=Renderer()
        for view in ('wave','spectrum','reduction'):
            state=demo_state()
            state['view']=view
            result=renderer.preview(state)
            self.assertEqual(result.size,(WIDTH,HEIGHT))
        result=renderer.preview({})
        self.assertEqual(result.size,(WIDTH,HEIGHT))
        for key,spec in BUTTONS.items():
            self.assertGreaterEqual(spec[0],0)
            self.assertLessEqual(spec[0]+spec[2],WIDTH)
            self.assertLessEqual(spec[1]+spec[3],HEIGHT)


if __name__=='__main__': unittest.main()
