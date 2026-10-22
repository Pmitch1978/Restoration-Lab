#!/usr/bin/env python3
"""Restoration Lab: metal GUI over the established Python playback engine."""
from dataclasses import replace
from pathlib import Path
import json
import queue
import time
import tkinter as tk
from tkinter import messagebox
import numpy as np
from PIL import Image, ImageTk
from legacy_app import App as ProcessingApp
from reference_engine import Controls, PRESETS, PRESET_DESCRIPTIONS
from manual import open_manual
from metal_ui import Renderer, BUTTONS, KNOBS, SLIDERS, WIDTH, HEIGHT, TEAL

VALUE_CONTROLS = {**KNOBS, **SLIDERS}


class ButtonAdapter:
    """Keep the existing loader/export busy-state behavior on canvas buttons."""
    def __init__(self, app, key):
        self.app, self.key = app, key

    def config(self, **kwargs):
        if 'state' in kwargs:
            self.app.enabled[self.key] = kwargs['state'] != 'disabled'
            self.app.draw_button(self.key)

    configure = config


class App(ProcessingApp):
    def build(self):
        self.root.title('Restoration Lab Version 1.5')
        icon_path=Path(__file__).resolve().parent/'assets'/'RestorationLab.png'
        if icon_path.exists():
            with Image.open(icon_path) as image:
                self._app_icon=ImageTk.PhotoImage(image.resize((256,256),Image.Resampling.LANCZOS),master=self.root)
            try:
                self.root.iconphoto(True,self._app_icon)
            except tk.TclError:
                pass  # The Mac bundle supplies its own Dock/Finder icon.
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        # Fit the M1 Air's default desktop, including menu bar and Dock room.
        initial_scale = min(1., (sw-70)/WIDTH, (sh-120)/HEIGHT)
        initial_scale = max(.60, initial_scale)
        self.root.geometry(f'{int(WIDTH*initial_scale)}x{int(HEIGHT*initial_scale)}')
        self.root.minsize(900, 520)
        self.root.configure(background='#101415')
        self.renderer = Renderer()
        self.enabled = {key:True for key in BUTTONS}
        self.buttons_state = {}
        self.images = {}
        self.items = {}
        self.scale = initial_scale
        self.offset = (0,0)
        self.view = 'wave'
        self.history = []
        self.peaks = None
        self.peaks_engine = None
        self.monitor_audio = None
        self.focus_control = None
        self.drag = None
        self.resize_job = None
        self.last_paint = 0.
        self.last_load = 0.
        self.last_misses = 0
        self.bypass = tk.BooleanVar(value=False)
        self.canvas = tk.Canvas(self.root, background='#101415', highlightthickness=0,
                                borderwidth=0, takefocus=True)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self.resized)
        self.canvas.bind('<ButtonPress-1>', self.pointer_down)
        self.canvas.bind('<B1-Motion>', self.pointer_drag)
        self.canvas.bind('<ButtonRelease-1>', self.pointer_up)
        self.canvas.bind('<Double-Button-1>', self.double_click)
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda event:self.wheel(event, 1))
        self.canvas.bind('<Button-5>', lambda event:self.wheel(event, -1))
        self.canvas.bind('<KeyPress>', self.key_press)
        self.canvas.bind('<Motion>', self.hover)
        self.open_button = ButtonAdapter(self,'open')
        self.export_button = ButtonAdapter(self,'export')
        self.play_button = ButtonAdapter(self,'play')
        self.drift_check = ButtonAdapter(self,'drift')
        self.commands = {
            'guide':lambda:open_manual(self.root),
            'open':self.open_file, 'export':self.export,
            'play':self.toggle, 'pause':self.pause, 'stop':self.stop,
            'rewind':self.stop,
            'wave':lambda:self.set_view('wave'),
            'spectrum':lambda:self.set_view('spectrum'),
            'reduction':lambda:self.set_view('reduction'),
            'off':lambda:self.mode.set('Off'),
            'stft':lambda:self.mode.set('STFT'),
            'wavelet':lambda:self.mode.set('Wavelet'),
            'both':lambda:self.mode.set('Both'),
            'drift':lambda:self.drift.set(not self.drift.get()),
            'removed':lambda:self.removed.set(not self.removed.get()),
            'match':lambda:self.match.set(not self.match.get()),
            'ab':lambda:self.master_on.set(not self.master_on.get()),
            'bypass':lambda:self.bypass.set(not self.bypass.get()),
            'preset':self.choose_preset, 'profile':self.profile_details,
        }
        for key, specs in VALUE_CONTROLS.items():
            var = tk.DoubleVar(value=specs[7])
            self.vars[key] = var
            var.trace_add('write',lambda *args,k=key:self.knob_changed(k))
        for variable in (self.mode,self.preset,self.master_on,self.match,self.removed,self.drift,self.bypass):
            variable.trace_add('write',self.ui_changed)
        self.status.trace_add('write',lambda *args:self.draw_dynamic())
        self.install_menu()
        self.update_controls()
        self.root.after_idle(self.layout)

    def install_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar,tearoff=False)
        file_menu.add_command(label='Open WAV…',command=self.open_file,accelerator='⌘O')
        file_menu.add_command(label='Export WAV…',command=self.export,accelerator='⌘E')
        file_menu.add_separator()
        file_menu.add_command(label='Close',command=self.close)
        menubar.add_cascade(label='File',menu=file_menu)
        help_menu = tk.Menu(menubar,tearoff=False)
        help_menu.add_command(label='User guide — Version 1.5',command=lambda:open_manual(self.root))
        help_menu.add_command(label='Controls & meters',command=self.help)
        help_menu.add_command(label='Profile details',command=self.profile_details)
        menubar.add_cascade(label='Help',menu=help_menu)
        self.root.config(menu=menubar)
        self.root.bind('<Command-o>',lambda event:self.open_file())
        self.root.bind('<Command-e>',lambda event:self.export())

    def help(self):
        messagebox.showinfo('Restoration Lab controls',
            'KNOBS\nDrag up/down. Hold Shift for fine adjustment. Use the mouse '
            'wheel or arrow keys. Double-click to restore the default. '
            'Tab moves between controls; Enter/Space activates a button.\n\n'
            'NR Strength scales both NR amount knobs together. At 100% it '
            'uses their values exactly; at 0% it bypasses NR.\n\n'
            'A/B switches between restored audio (A) and restored + mastered (B). '
            'Bypass All monitors/exports the original source. Removed listens to '
            'the original minus NR output; it is monitor-only. Level Match is '
            'approximate RMS matching for monitoring, not export.\n\n'
            'Waveform shows the source, not a cached restored file. Spectrum '
            'shows the current monitored output. Teal history is NR RMS level '
            'decrease; amber is compression while mastering is enabled. '
            'NR load is worker time divided by block duration, not total CPU.\n\n'
            'Output meters show sampled monitor-block sample peaks, not true '
            'peaks or LUFS. GR shows compressor reduction. Monitoring uses '
            'the system default output selected in macOS Sound settings.\n\n'
            'Set Drift Correction before loading a WAV. All profiling uses the '
            'loaded song; this version does not accept live audio input.',parent=self.root)

    def profile_details(self):
        if self.restoration is None:
            messagebox.showinfo('Profile details','Load a WAV to analyze its adaptive profile.',parent=self.root)
            return
        window=tk.Toplevel(self.root)
        window.title('Restoration Lab — profile details')
        window.geometry('680x480')
        output=tk.Text(window,background='#101617',foreground='#edf1ef',
                       insertbackground=TEAL,font=('Menlo',11),wrap='word',padx=18,pady=18)
        output.pack(fill='both',expand=True)
        output.insert('1.0',json.dumps(self.restoration.report,indent=2))
        output.config(state='disabled')

    def choose_preset(self):
        menu=tk.Menu(self.root,tearoff=False)
        for name in PRESETS:
            menu.add_radiobutton(label=name+' — '+PRESET_DESCRIPTIONS[name],
                variable=self.preset,value=name,command=lambda p=name:self.select_preset(p))
        x,y,w,h,_=BUTTONS['preset']
        menu.tk_popup(round(self.canvas.winfo_rootx()+self.offset[0]+x*self.scale),
                      round(self.canvas.winfo_rooty()+self.offset[1]+(y+h)*self.scale))

    def select_preset(self,name):
        if name not in PRESETS:
            raise ValueError('Unknown mastering preset')
        self.preset.set(name)
        self.master_on.set(True)
        if self.bypass.get():
            self.status.set(f'{name} selected. BYPASS ALL is active; turn it off to hear mastering.')
        elif self.removed.get():
            self.status.set(f'{name} selected. Turn off LISTEN TO REMOVED to hear mastering.')
        elif self.vars['strength'].get()==0:
            self.status.set(f'{name} selected — B: Mastered. Raise STRENGTH above 0% to hear the preset.')
        else:
            self.status.set(f'{name} — B: Mastered. {PRESET_DESCRIPTIONS[name]}. '
                'Level Match preserves approximate monitor loudness when enabled.')

    def pause(self):
        if self.playing or self.play_requested: self.toggle()

    def update_controls(self):
        values = {key:var.get() for key,var in self.vars.items()}
        nr_strength=values.pop('nr_strength',100)/100
        for key in ('spectral_amount','wavelet_amount','strength'):
            if key in values: values[key]/=100
        for key in ('spectral_amount','wavelet_amount'):
            if key in values: values[key]*=nr_strength
        self.controls=Controls(mode=self.mode.get(),preset=self.preset.get(),
            master=self.master_on.get(),match=self.match.get(),removed=self.removed.get(),**values)
        if hasattr(self,'bypass') and self.bypass.get():
            self.controls=replace(self.controls,mode='Off',master=False,match=False,removed=False)

    def knob_changed(self,key):
        self.update_controls()
        self.draw_knob(key)

    def ui_changed(self,*args):
        self.update_controls()
        self.refresh_buttons()
        self.draw_dynamic()

    def set_view(self,view):
        self.view=view
        self.refresh_buttons()
        self.draw_dynamic()

    def resized(self,event):
        if self.resize_job is not None:
            self.root.after_cancel(self.resize_job)
        self.resize_job=self.root.after(80,self.layout)

    def layout(self):
        self.resize_job=None
        width,height=self.canvas.winfo_width(),self.canvas.winfo_height()
        if width<2 or height<2: return
        self.scale=min(width/WIDTH,height/HEIGHT)
        self.offset=((width-WIDTH*self.scale)/2,(height-HEIGHT*self.scale)/2)
        self.canvas.delete('all')
        self.images.clear()
        self.items.clear()
        self.put('base',(0,0),self.renderer.base)
        for key in VALUE_CONTROLS: self.draw_knob(key)
        self.buttons_state.clear()
        self.refresh_buttons(force=True)
        self.draw_dynamic()

    def put(self,key,xy,image):
        size=(max(1,round(image.width*self.scale)),max(1,round(image.height*self.scale)))
        if image.size!=size: image=image.resize(size,Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(image,master=self.root)
        self.images[key]=photo
        x,y=self.offset[0]+xy[0]*self.scale,self.offset[1]+xy[1]*self.scale
        if key in self.items:
            self.canvas.itemconfig(self.items[key],image=photo)
            self.canvas.coords(self.items[key],x,y)
        else:
            self.items[key]=self.canvas.create_image(x,y,image=photo,anchor='nw')

    def button_config(self,key):
        active = {
            'off':self.mode.get()=='Off','stft':self.mode.get()=='STFT',
            'wavelet':self.mode.get()=='Wavelet','both':self.mode.get()=='Both',
            'drift':self.drift.get(),'removed':self.removed.get(),
            'ab':self.master_on.get(),'match':self.match.get(),'bypass':self.bypass.get(),
            'wave':self.view=='wave','spectrum':self.view=='spectrum','reduction':self.view=='reduction',
            'play':self.playing or self.play_requested,
        }.get(key,False)
        label={'ab':'B · MASTERING ON' if self.master_on.get() else 'A · MASTERING OFF',
               'preset':self.preset.get().upper()+'   ▾'}.get(key)
        enabled=self.enabled.get(key,True)
        if key in ('stop','pause','rewind'): enabled=not self.busy
        if key=='export': enabled=enabled and self.restoration is not None
        return dict(active=active,label=label,enabled=enabled,focus=self.focus_control==key)

    def draw_button(self,key,force=False):
        if not hasattr(self,'renderer'): return
        config=self.button_config(key)
        if force or self.buttons_state.get(key)!=config:
            self.put('button:'+key,BUTTONS[key][:2],self.renderer.button(key,**config))
            self.buttons_state[key]=config

    def refresh_buttons(self,force=False):
        for key in BUTTONS: self.draw_button(key,force)

    def draw_knob(self,key):
        if key in self.vars:
            specs=VALUE_CONTROLS[key]
            render=self.renderer.slider if key in SLIDERS else self.renderer.knob
            self.put('knob:'+key,specs[:2],render(
                key,self.vars[key].get(),self.focus_control==key))

    def design_point(self,event):
        return ((event.x-self.offset[0])/self.scale,(event.y-self.offset[1])/self.scale)

    @staticmethod
    def inside(x,y,box):
        return box[0]<=x<=box[0]+box[2] and box[1]<=y<=box[1]+box[3]

    def hit(self,x,y):
        for key,box in VALUE_CONTROLS.items():
            if self.inside(x,y,box): return key
        for key,box in BUTTONS.items():
            if self.inside(x,y,box): return key
        return None

    def focus(self,key):
        old=self.focus_control
        self.focus_control=key
        for target in (old,key):
            if target in VALUE_CONTROLS: self.draw_knob(target)
            elif target in BUTTONS: self.draw_button(target)

    def pointer_down(self,event):
        self.canvas.focus_set()
        x,y=self.design_point(event)
        key=self.hit(x,y)
        self.focus(key)
        if key in VALUE_CONTROLS:
            self.drag=(key,y,self.vars[key].get())
            if key in SLIDERS: self.pointer_drag(event)
        elif key in BUTTONS:
            if self.button_config(key)['enabled']: self.commands[key]()
        elif self.inside(x,y,self.renderer.plot_rect) and self.view=='wave':
            self.seek_fraction((x-self.renderer.plot_rect[0])/self.renderer.plot_rect[2])
        elif 314<=x<=574 and 676<=y<=690:
            self.seek_fraction((x-314)/260)

    def pointer_drag(self,event):
        if not self.drag: return
        key,start,value=self.drag
        x,y=self.design_point(event)
        low,high=VALUE_CONTROLS[key][5:7]
        if key in SLIDERS:
            box=SLIDERS[key]
            self.set_value(key,low+(x-box[0]-12)/(box[2]-25)*(high-low))
            return
        fine=.1 if event.state & 0x0001 else 1.
        self.set_value(key,value+(start-y)*(high-low)/160*fine)

    def pointer_up(self,event):
        self.drag=None

    def double_click(self,event):
        key=self.hit(*self.design_point(event))
        if key in VALUE_CONTROLS:
            self.vars[key].set(VALUE_CONTROLS[key][7])
            self.drag=None

    def set_value(self,key,value):
        low,high=VALUE_CONTROLS[key][5:7]
        self.vars[key].set(round(float(np.clip(value,low,high)),2))

    def wheel(self,event,direction=None):
        key=self.hit(*self.design_point(event))
        if key not in VALUE_CONTROLS: return
        delta=direction if direction is not None else (1 if event.delta>0 else -1 if event.delta<0 else 0)
        step=1. if VALUE_CONTROLS[key][8]=='%' else .1
        if event.state & 0x0001: step*=.1
        self.set_value(key,self.vars[key].get()+delta*step)
        self.focus(key)
        return 'break'

    def key_press(self,event):
        key=self.focus_control
        order=list(BUTTONS)+list(VALUE_CONTROLS)
        if event.keysym in ('Tab','ISO_Left_Tab'):
            i=order.index(key) if key in order else -1
            backwards=event.keysym=='ISO_Left_Tab' or event.state & 1
            self.focus(order[(i+(-1 if backwards else 1))%len(order)])
        elif event.keysym in ('Return','space'):
            if key in BUTTONS and self.button_config(key)['enabled']: self.commands[key]()
            elif event.keysym=='space' and not self.busy: self.toggle()
        elif key in VALUE_CONTROLS and event.keysym in ('Up','Right','Down','Left','Home','End'):
            low,high=VALUE_CONTROLS[key][5:7]
            if event.keysym in ('Home','End'):
                self.set_value(key,low if event.keysym=='Home' else high)
            else:
                step=1. if VALUE_CONTROLS[key][8]=='%' else .1
                if event.state & 1: step*=.1
                self.set_value(key,self.vars[key].get()+step*(1 if event.keysym in ('Up','Right') else -1))
        else: return
        return 'break'

    def hover(self,event):
        x,y=self.design_point(event)
        key=self.hit(x,y)
        self.canvas.config(cursor='hand2' if key in BUTTONS else 'sb_h_double_arrow' if key in SLIDERS else 'sb_v_double_arrow' if key in KNOBS else '')

    def seek_fraction(self,fraction):
        if self.restoration is None or self.busy: return
        resume=self.playing or self.play_requested
        self.playing=False
        self.shutdown_stream()
        self.position=int(np.clip(fraction,0,1)*(len(self.restoration.source)-1))
        if resume: self.toggle()
        self.draw_dynamic()

    def callback(self,outdata,frames,timing,status):
        super().callback(outdata,frames,timing,status)
        # One small monitor snapshot; FFTs and graphics stay on the UI thread.
        self.monitor_audio=outdata.copy()

    def shutdown_stream(self):
        transport=self.transport
        if transport is not None:
            self.last_load=transport.last_load*100
            self.last_misses=transport.underflows
        super().shutdown_stream()

    def toggle(self):
        if not self.playing and not self.play_requested and self.restoration is not None and not self.busy:
            self.last_load=self.last_misses=0
        super().toggle()
        self.refresh_buttons()

    def stop(self):
        super().stop()
        if hasattr(self,'renderer'):
            self.monitor_audio=None
            self.refresh_buttons()
            self.draw_dynamic()

    def draw_wave(self):
        engine=self.restoration
        if engine is not self.peaks_engine:
            self.peaks_engine=engine
            self.peaks=None
            self.history=[]
            self.monitor_audio=None
            self.last_load=self.last_misses=0
            if engine is not None:
                # Signed min/max per channel; no normalization of the source.
                source=engine.source
                indices=np.arange(0,len(source),max(1,len(source)//1600))
                lows=np.minimum.reduceat(source,indices,axis=0)
                highs=np.maximum.reduceat(source,indices,axis=0)
                self.peaks=np.stack((lows,highs),axis=-1).transpose(1,0,2)
        self.draw_dynamic()

    def display_state(self):
        engine=self.restoration
        sr=engine.sr if engine is not None else 48000
        transport=self.transport
        load=transport.last_load*100 if transport else self.last_load
        misses=transport.underflows if transport else self.last_misses
        active=self.playing and engine is not None
        snapshot=self.monitor_audio
        meter_peaks=[-90.,-90.]
        if active and snapshot is not None:
            meter_peaks=(20*np.log10(np.maximum(np.max(np.abs(snapshot),axis=0),1e-9))).tolist()
            if len(meter_peaks)==1: meter_peaks*=2
        pb,pm,pt,ratio=PRESETS[self.controls.preset]
        if self.bypass.get():
            mastering_status='BYPASS ALL ACTIVE — mastering is bypassed'
        elif self.controls.removed:
            mastering_status='REMOVED MONITOR ACTIVE — turn it off to hear mastering'
        elif not self.controls.master:
            mastering_status='MASTERING OFF — choose a preset or press A/B to enable'
        else:
            c=self.controls
            mastering_status=(f'{c.preset} · {c.strength*100:.0f}% · '
                f'EQ {c.bass+pb*c.strength:+.1f} / {c.mid+pm*c.strength:+.1f} / '
                f'{c.treble+pt*c.strength:+.1f} dB · Ratio {1+(ratio-1)*c.strength:.2f}:1')
        return dict(mastering_status=mastering_status,view=self.view,peaks=self.peaks,monitor=snapshot,playing=active,
            sr=sr,duration=len(engine.source)/sr if engine is not None else 0,
            position=self.position/sr,history=self.history,load=load,misses=misses,
            meter_peaks=meter_peaks,
            gr=self.last_meters.get('compression_db',0) if active and self.controls.master and not self.controls.removed else 0,
            filename=Path(self.path).name if engine is not None and self.path else 'NO FILE LOADED',
            format=f'{sr/1000:g} kHz · '+('STEREO' if engine.source.shape[1]==2 else 'MONO') if engine is not None else 'NO AUDIO LOADED',
            status=self.status.get())

    def draw_dynamic(self):
        if not hasattr(self,'renderer') or not hasattr(self,'items'): return
        state=self.display_state()
        for key,xy,image in self.renderer.parts(state): self.put(key,xy,image)

    def poll(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=='status': self.status.set(payload)
                elif kind=='loaded':
                    self.path,self.restoration=payload
                    self.position=0
                    self.last_meters={}
                    self.set_busy(False)
                    self.drift_check.config(state='normal')
                    self.draw_wave()
                    self.status.set(f'{Path(self.path).name} — ready. Profile analyzed in '
                        f'{self.restoration.report["analysis_seconds"]:.1f} s. Click the waveform to seek.')
                elif kind=='exported':
                    self.set_busy(False)
                    self.status.set(f'Saved {payload} and processing report.')
                elif kind=='error':
                    self.set_busy(False)
                    self.drift_check.config(state='normal')
                    self.status.set(payload)
                    messagebox.showerror('Processing',payload,parent=self.root)
        except queue.Empty: pass
        self.start_ready_stream()
        if self.audio_error:
            self.status.set(f'Audio: {self.audio_error}')
            self.audio_error=None
        now=time.monotonic()
        if now-self.last_paint>=.10:
            if self.playing and self.transport:
                compression=self.last_meters.get('compression_db',0) if self.controls.master and not self.controls.removed else 0
                self.history.append((self.transport.last_reduction_db,compression))
                self.history=self.history[-240:]
            self.draw_dynamic()
            self.refresh_buttons()
            self.last_paint=now
        self.root.after(50,self.poll)


if __name__=='__main__':
    root=tk.Tk()
    App(root)
    root.mainloop()
