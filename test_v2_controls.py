"""Headless interaction checks using a Tcl interpreter and the real app methods."""
import unittest
from types import SimpleNamespace
import numpy as np
import test_gui
from app import App

class Controls2Tests(unittest.TestCase):
    def make_app(self):
        a=test_gui.GuiTests().make_controls()
        import tkinter as tk
        a.focus_band=tk.BooleanVar(a._interp,value=False)
        a.original=tk.BooleanVar(a._interp,value=False)
        a.restoration=SimpleNamespace(source=np.zeros((48000,2)),sr=48000)
        a.position=12000;a.busy=False;a.playing=False;a.play_requested=False
        a.loop_enabled=False;a.loop_a=0;a.loop_b=48000;a.loop_range=None
        a.shutdown_stream=lambda:None;a.refresh_buttons=lambda:None;a.draw_dynamic=lambda:None
        a.status=tk.StringVar(a._interp)
        return a

    def test_loop_point_constraints_toggle_and_clear(self):
        a=self.make_app();a.set_loop_point('a');self.assertEqual(a.loop_a,12000)
        a.position=36000;a.set_loop_point('b');a.toggle_loop()
        self.assertEqual(a.loop_range,(12000,36000))
        a.toggle_loop();self.assertIsNone(a.loop_range)
        self.assertEqual((a.loop_a,a.loop_b),(12000,36000))
        a.position=47999;a.set_loop_point('a')
        self.assertGreaterEqual(a.loop_b-a.loop_a,2400)
        a.clear_loop();self.assertEqual((a.loop_a,a.loop_b,a.loop_range),(0,48000,None))

    def test_new_controls_and_monitor_switch_do_not_change_processing(self):
        a=self.make_app();a.vars['grain'].set(80);a.focus_band.set(True)
        a.vars['frequency'].set(5200);a.vars['width'].set(.7);a.update_controls()
        self.assertEqual((a.controls.grain,a.controls.focus,a.controls.frequency,a.controls.width),(.8,True,5200,.7))
        before=a.controls
        a.select_monitor(True);a.update_controls()
        self.assertTrue(a.controls.preview_original);self.assertFalse(a.controls.removed)
        self.assertEqual(a.controls.mode,before.mode)
        a.bypass.set(True);a.update_controls()
        self.assertEqual(a.controls.mode,'Off');self.assertFalse(a.controls.master or a.controls.preview_original)
        a.bypass.set(False);a.select_monitor(False);a.update_controls()
        self.assertTrue(a.controls.focus)

    def test_float_source_selects_float_export_default(self):
        a=self.make_app()
        a.peaks_engine=None
        a.restoration.source_subtype='FLOAT'
        a.draw_wave()
        self.assertEqual(a.export_subtype,'FLOAT')
        a.restoration=SimpleNamespace(source=np.zeros((4800,1)),sr=48000,source_subtype='PCM_24')
        a.draw_wave()
        self.assertEqual(a.export_subtype,'PCM_24')

if __name__=='__main__':unittest.main()
