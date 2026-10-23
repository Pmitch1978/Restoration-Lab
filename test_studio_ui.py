"""Metal Studio artwork, hit geometry and user interaction behavior."""
import unittest
from types import SimpleNamespace
from dataclasses import replace
import numpy as np
from reference_engine import Controls
from studio_ui import StudioRenderer,MasteringStudio,TABS,W,H,Hit

class MetalStudioTests(unittest.TestCase):
    def test_three_pages_and_shared_controls(self):
        self.assertEqual(TABS,('EQ','COMPRESSOR','STEREO & LOUDNESS'))
        renderer=StudioRenderer()
        t=np.arange(2048)/48000;audio=np.column_stack((.1*np.sin(t*2800),.08*np.sin(t*3000)))
        for page in range(3):
            image=renderer.render(Controls(master=True),page,dict(audio=audio,sr=48000,meters={'band_reduction_db':[1,2,3,1],'compression_db':3,'correlation':.7}))
            self.assertEqual(image.size,(W,H))
            for key in ('tab0','tab1','tab2','master','close','play','stop','preset','save','load','bypass','match'):self.assertIn(key,renderer.hits)
            for key,hit in renderer.hits.items():
                x,y,w,h=hit.rect
                self.assertTrue(0<=x<x+w<=W and 0<=y<y+h<=H,key)
            if page==0:self.assertIn('eq.5.q',renderer.hits)
            elif page==1:self.assertIn('high_release',renderer.hits)
            else:self.assertIn('stereo_width',renderer.hits);self.assertIn('target_lufs',renderer.hits)
    def make_studio(self):
        import tkinter as tk
        from test_gui import GuiTests
        a=GuiTests().make_controls();a.restoration=None
        a.eq_vars=[{key:(tk.BooleanVar(a._interp,value=value) if isinstance(value,bool) else tk.StringVar(a._interp,value=value) if isinstance(value,str) else tk.DoubleVar(a._interp,value=value)) for key,value in band.__dict__.items()} for band in Controls().eq_bands]
        a.vars.update({k:tk.DoubleVar(a._interp,value=v) for k,v in {'crossover_low':200,'crossover_mid':1000,'crossover_high':4000,'stereo_width':1,'target_lufs':-14}.items()})
        a.advanced_flags={};a.update_controls()
        studio=MasteringStudio.__new__(MasteringStudio);studio.app=a;studio.renderer=StudioRenderer();studio.renderer.render(a.controls,1);studio.paint=lambda:a.update_controls();studio.state=lambda:{'sr':48000}
        return studio
    def test_crossovers_clamp_to_valid_spacing(self):
        s=self.make_studio()
        s.set_value('crossover_mid',50);self.assertEqual(s.app.vars['crossover_mid'].get(),400)
        s.app.update_controls();s.set_value('crossover_low',900);self.assertEqual(s.app.vars['crossover_low'].get(),200)
        s.app.update_controls();s.set_value('crossover_high',48000);self.assertLess(s.app.vars['crossover_high'].get(),48000*.45)
    def test_numeric_edit_routes_to_eq_and_stereo(self):
        s=self.make_studio()
        s.set_value('eq.2.gain',-3,Hit((0,0,1,1),'knob','eq.2.gain',-18,18))
        s.set_value('stereo_width',1.35,Hit((0,0,1,1),'knob','stereo_width',0,2))
        self.assertEqual(s.app.controls.eq_bands[2].gain,-3);self.assertEqual(s.app.controls.stereo_width,1.35)

if __name__=='__main__':unittest.main()
