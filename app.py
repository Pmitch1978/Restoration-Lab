#!/usr/bin/env python3
"""Restoration Lab: metal GUI over the established Python playback engine."""
from dataclasses import replace, fields, asdict
from pathlib import Path
import json
import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import numpy as np
from PIL import Image, ImageTk
from legacy_app import App as ProcessingApp
from reference_engine import Controls, EQBand, PRESETS, PRESET_DESCRIPTIONS
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
        self.root.title('Restoration Lab Version 3.0')
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
        self.root.minsize(1000, 708)
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
        self.focus_band=tk.BooleanVar(value=False)
        self.original=tk.BooleanVar(value=False)
        self.loop_enabled=False
        self.loop_a=0
        self.loop_b=0
        self.loop_range=None
        self.export_subtype='PCM_24'
        self.marker_drag=None
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
            'drift':self.toggle_drift,
            'removed':lambda:self.removed.set(not self.removed.get()),
            'match':lambda:self.match.set(not self.match.get()),
            'ab':lambda:self.master_on.set(not self.master_on.get()),
            'bypass':lambda:self.bypass.set(not self.bypass.get()),
            'preset':self.choose_preset, 'profile':self.profile_details,
            'advanced':self.mastering_settings,
            'focus':lambda:self.focus_band.set(True),
            'full_range':lambda:self.focus_band.set(False),
            'original':lambda:self.select_monitor(True),
            'processed':lambda:self.select_monitor(False),
            'loop':self.toggle_loop,
            'set_a':lambda:self.set_loop_point('a'),
            'set_b':lambda:self.set_loop_point('b'),
            'clear_loop':self.clear_loop,
        }
        for key, specs in VALUE_CONTROLS.items():
            var = tk.DoubleVar(value=specs[7])
            self.vars[key] = var
            var.trace_add('write',lambda *args,k=key:self.knob_changed(k))
        for variable in (self.mode,self.preset,self.master_on,self.match,self.removed,self.drift,self.bypass,self.focus_band,self.original):
            variable.trace_add('write',self.ui_changed)
        self.advanced_flags={}
        defaults=Controls()
        excluded={'mode','preset','master','match','removed','preview_original','focus','eq_bands'}
        for field in fields(defaults):
            name=field.name;value=getattr(defaults,name)
            if name in excluded or name in self.vars:continue
            if isinstance(value,bool):
                self.advanced_flags[name]=tk.BooleanVar(value=value)
                self.advanced_flags[name].trace_add('write',self.ui_changed)
            elif isinstance(value,(int,float)):
                self.vars[name]=tk.DoubleVar(value=value)
                self.vars[name].trace_add('write',self.ui_changed)
        self.eq_vars=[]
        for band in defaults.eq_bands:
            row={key:(tk.BooleanVar(value=value) if isinstance(value,bool) else
                tk.StringVar(value=value) if isinstance(value,str) else tk.DoubleVar(value=value))
                for key,value in asdict(band).items()}
            for variable in row.values():variable.trace_add('write',self.ui_changed)
            self.eq_vars.append(row)
        self.master_meter_text=tk.StringVar(value='Play audio to measure this session.')
        self.status.trace_add('write',lambda *args:self.draw_dynamic())
        self.install_menu()
        self.update_controls()
        self.root.after_idle(self.layout)

    def install_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar,tearoff=False)
        file_menu.add_command(label='Open WAV or MP3…',command=self.open_file,accelerator='⌘O')
        file_menu.add_command(label='Export WAV…',command=self.export,accelerator='⌘E')
        file_menu.add_separator()
        file_menu.add_command(label='Close',command=self.close)
        file_menu.add_command(label='Mastering settings…',command=self.mastering_settings)
        menubar.add_cascade(label='File',menu=file_menu)
        help_menu = tk.Menu(menubar,tearoff=False)
        help_menu.add_command(label='User guide — Version 3.0',command=lambda:open_manual(self.root))
        help_menu.add_command(label='Controls & meters',command=self.help)
        help_menu.add_command(label='Profile details',command=self.profile_details)
        menubar.add_cascade(label='Help',menu=help_menu)
        self.root.config(menu=menubar)
        self.root.bind('<Command-o>',lambda event:self.open_file())
        self.root.bind('<Command-e>',lambda event:self.export())
        self.root.bind('<Control-o>',lambda event:self.open_file())
        self.root.bind('<Control-e>',lambda event:self.export())

    def help(self):
        messagebox.showinfo('Restoration Lab 3.0',
            'Loop: SET A / SET B at the playhead, then LOOP. Drag A/B on the waveform. '
            'Minimum loop: 50 ms or 2048 samples. Looping is playback only.\n\n'
            'Grain: lower preserves faster changes; higher smooths reduction more. '
            '50% preserves the original smoothing. It is not an amount control.\n\n'
            'Frequency Focus: TARGET BAND applies cleanup around Frequency with Width in octaves. '
            'FULL RANGE restores broad cleanup. The plot shows a targeting weight, not EQ gain.\n\n'
            'ORIGINAL / PROCESSED compares dry source with the selected processing chain. '
            'MASTERING ON/OFF controls mastering separately. Removed and Level Match are monitor only.\n\n'
            'Export: choose PCM24 or float32 WAV. Exports always cover the full song and use '
            'processing settings, even when ORIGINAL monitoring is selected. BYPASS ALL exports dry.\n\n'
            'Knobs: drag vertically, wheel or arrow keys. Shift for fine adjustments; '
            'double-click resets. Space plays/pauses. See USER GUIDE for details.',parent=self.root)

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
        if getattr(self,"_loading_studio_preset",False):return
        values = {key:var.get() for key,var in self.vars.items()}
        eq_bands=tuple(EQBand(**{k:v.get() for k,v in row.items()}) for row in self.eq_vars) if hasattr(self,'eq_vars') else Controls().eq_bands
        nr_strength=values.pop('nr_strength',100)/100
        for key in ('spectral_amount','wavelet_amount','strength','grain'):
            if key in values: values[key]/=100
        for key in ('spectral_amount','wavelet_amount'):
            if key in values: values[key]*=nr_strength
        self.controls=Controls(mode=self.mode.get(),preset=self.preset.get(),
            master=self.master_on.get(),match=self.match.get(),removed=self.removed.get(),
            focus=self.focus_band.get() if hasattr(self,'focus_band') else False,
            preview_original=self.original.get() if hasattr(self,'original') else False,
            eq_bands=eq_bands,**{key:var.get() for key,var in getattr(self,'advanced_flags',{}).items()},**values)
        if hasattr(self,'bypass') and self.bypass.get():
            self.controls=replace(self.controls,mode='Off',master=False,match=False,removed=False,preview_original=False)

    def knob_changed(self,key):
        self.update_controls()
        self.draw_knob(key)

    def ui_changed(self,*args):
        if getattr(self,"_loading_studio_preset",False):return
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
            'focus':self.focus_band.get(),'full_range':not self.focus_band.get(),
            'original':self.original.get() and not self.removed.get() and not self.bypass.get(),
            'processed':not self.original.get() and not self.removed.get() and not self.bypass.get(),
            'loop':self.loop_enabled,
        }.get(key,False)
        label={'ab':'MASTERING ON' if self.master_on.get() else 'MASTERING OFF',
               'preset':self.preset.get().upper()+'   ▾'}.get(key)
        enabled=self.enabled.get(key,True)
        if key in ('stop','pause','rewind'): enabled=not self.busy
        if key=='export': enabled=enabled and self.restoration is not None
        if key in ('loop','set_a','set_b','clear_loop','original','processed'):
            enabled=not self.busy and self.restoration is not None
        if key=='drift': enabled=enabled and not self.busy
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
            if self.restoration is None or self.busy: return
            px,_,pw,_=self.renderer.plot_rect
            total=len(self.restoration.source)
            for marker,value in (('a',self.loop_a),('b',self.loop_b)):
                mx=px+value/total*(pw-1)
                if abs(x-mx)<=12:
                    self.marker_drag=marker
                    self._marker_resume=self.playing or self.play_requested
                    self.playing=False
                    self.shutdown_stream()
                    return
            self.seek_fraction((x-px)/pw)


    def pointer_drag(self,event):
        if self.marker_drag:
            x,_=self.design_point(event)
            px,_,pw,_=self.renderer.plot_rect
            total=len(self.restoration.source)
            minimum=max(2048,round(.05*self.restoration.sr))
            sample=round(np.clip((x-px)/(pw-1),0,1)*total)
            if self.marker_drag=='a': self.loop_a=max(0,min(sample,self.loop_b-minimum))
            else: self.loop_b=min(total,max(sample,self.loop_a+minimum))
            self.draw_dynamic()
            return
        if not self.drag: return
        key,start,value=self.drag
        x,y=self.design_point(event)
        low,high=VALUE_CONTROLS[key][5:7]
        if key in SLIDERS:
            box=SLIDERS[key]
            self.set_value(key,low+(x-box[0]-12)/(box[2]-25)*(high-low))
            return
        fine=.1 if event.state & 0x0001 else 1.
        if key=='frequency':
            self.set_value(key,value*np.exp((start-y)*np.log(high/low)/160*fine))
        else:
            self.set_value(key,value+(start-y)*(high-low)/160*fine)

    def pointer_up(self,event):
        self.drag=None
        if self.marker_drag:
            self.marker_drag=None
            self.apply_loop(resume=self._marker_resume)

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
        step=self.vars[key].get()*.025 if key=='frequency' else 1. if VALUE_CONTROLS[key][8]=='%' else .1
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
                step=self.vars[key].get()*.025 if key=='frequency' else 1. if VALUE_CONTROLS[key][8]=='%' else .1
                if event.state & 1: step*=.1
                self.set_value(key,self.vars[key].get()+step*(1 if event.keysym in ('Up','Right') else -1))
        else: return
        return 'break'

    def hover(self,event):
        x,y=self.design_point(event)
        key=self.hit(x,y)
        self.canvas.config(cursor='hand2' if key in BUTTONS else 'sb_h_double_arrow' if key in SLIDERS else 'sb_v_double_arrow' if key in KNOBS else '')

    def toggle_drift(self):
        if self.busy: return
        self.drift.set(not self.drift.get())
        if self.restoration is None: return
        import threading
        from realtime import RealtimeRestoration
        engine,path=self.restoration,self.path
        self.playing=False
        self.shutdown_stream()
        self.set_busy(True)
        self.drift_check.config(state='disabled')
        use_drift=self.drift.get()
        def work():
            try:
                updated=RealtimeRestoration(engine.source,engine.sr,use_drift,
                    lambda message:self.events.put(('status',message)))
                updated.source_subtype=getattr(engine,'source_subtype','PCM_24')
                self.events.put(('loaded',(path,updated)))
            except Exception as exc:
                self.events.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def select_monitor(self,original):
        self.removed.set(False)
        self.original.set(original)

    def apply_loop(self,resume=None):
        if self.restoration is None or self.busy: return
        if resume is None: resume=self.playing or self.play_requested
        self.playing=False
        self.shutdown_stream()
        minimum=max(2048,round(.05*self.restoration.sr))
        if self.loop_b-self.loop_a<minimum:
            self.loop_enabled=False
            self.status.set('Loop is too short: use at least 50 ms / 2048 frames.')
        self.loop_range=(int(self.loop_a),int(self.loop_b)) if self.loop_enabled else None
        if self.loop_range and not self.loop_a<=self.position<self.loop_b:
            self.position=self.loop_a
        if resume: self.toggle()
        self.refresh_buttons()
        self.draw_dynamic()

    def toggle_loop(self):
        self.loop_enabled=not self.loop_enabled
        self.apply_loop()

    def set_loop_point(self,which):
        if self.restoration is None or self.busy: return
        minimum=max(2048,round(.05*self.restoration.sr))
        if which=='a': self.loop_a=max(0,min(self.position,self.loop_b-minimum))
        else: self.loop_b=min(len(self.restoration.source),max(self.position,self.loop_a+minimum))
        self.apply_loop()

    def clear_loop(self):
        if self.restoration is None or self.busy: return
        self.loop_enabled=False
        self.loop_a=0
        self.loop_b=len(self.restoration.source)
        self.apply_loop()

    def export(self):
        if self.busy or self.restoration is None: return
        window=tk.Toplevel(self.root)
        window.title('Export WAV — Restoration Lab 3.0')
        window.transient(self.root)
        choice=tk.StringVar(window,value='32-bit float WAV' if self.export_subtype=='FLOAT' else '24-bit PCM WAV')
        ttk.Label(window,text='Export format',font=('',13,'bold')).pack(padx=25,pady=(22,10))
        combo=ttk.Combobox(window,textvariable=choice,state='readonly',width=25,
            values=['24-bit PCM WAV','32-bit float WAV'])
        combo.pack(padx=25,pady=8)
        ttk.Label(window,text='Full song · original sample rate and channels.\n'
            'Loop points and monitor comparisons are not exported.\n'
            'LUFS targeting and verified peak ceiling apply with mastering on.\n'
            'Float preserves values above 0 dBFS when mastering is off.',justify='left').pack(padx=25,pady=12)
        accepted=[]
        row=ttk.Frame(window);row.pack(pady=(4,20))
        def confirm():
            accepted.append(True)
            window.destroy()
        ttk.Button(row,text='Cancel',command=window.destroy).pack(side='left',padx=8)
        ttk.Button(row,text='Choose destination…',command=confirm).pack(side='left',padx=8)
        window.grab_set()
        combo.focus_set()
        self.root.wait_window(window)
        if not accepted:return
        self.export_subtype='FLOAT' if choice.get().startswith('32') else 'PCM_24'
        super().export()

    def mastering_settings(self):
        existing=getattr(self,'mastering_window',None)
        if existing is not None and existing.winfo_exists():existing.lift();return
        from studio_ui import MasteringStudio
        self.studio=MasteringStudio(self)

    def save_studio_preset(self):
        filename=filedialog.asksaveasfilename(parent=self.mastering_window,defaultextension='.json',filetypes=[('Restoration Lab preset','*.json')])
        if filename:Path(filename).write_text(json.dumps({'version':3,'controls':asdict(self.controls)},indent=2))

    def load_studio_preset(self):
        filename=filedialog.askopenfilename(parent=self.mastering_window,filetypes=[('Restoration Lab preset','*.json')])
        if not filename:return
        try:
            from studio_tools import eq_filters, StereoWidth
            from mastering_tools import validate
            data=json.loads(Path(filename).read_text())
            if data.get('version')!=3:raise ValueError('A Version 3 preset is required')
            values=data['controls'];values['eq_bands']=tuple(EQBand(**row) for row in values['eq_bands'])
            candidate=Controls(**values)
            if candidate.preset not in PRESETS:raise ValueError('Unknown tone preset')
            defaults=Controls()
            for field in fields(defaults):
                value=getattr(candidate,field.name);default=getattr(defaults,field.name)
                if isinstance(default,bool) and not isinstance(value,bool):raise ValueError('Invalid switch')
                if not isinstance(default,bool) and isinstance(default,(float,int)) and (isinstance(value,bool) or not isinstance(value,(float,int)) or not np.isfinite(value)):raise ValueError('Invalid numeric setting')
            sr=self.restoration.sr if self.restoration is not None else 48000
            validate(candidate,sr);eq_filters(candidate,sr);StereoWidth(sr,2).process(np.zeros((2,2)),candidate)
            # Only mastering controls are restored; source/restoration and monitor state remain.
            self._loading_studio_preset=True
            try:
                for key,var in self.vars.items():
                    if key in values and key not in ('spectral_amount','wavelet_amount','grain','frequency','width'):var.set(values[key]*100 if key=='strength' else values[key])
                for key,var in self.advanced_flags.items():
                    if key!='mono_audition' and not key.endswith('_solo'):var.set(values[key])
                for row,band in zip(self.eq_vars,candidate.eq_bands):
                    for key,value in asdict(band).items():row[key].set(value)
                self.preset.set(candidate.preset)
            finally:self._loading_studio_preset=False
            self.ui_changed()
            self.status.set('Version 3 mastering preset loaded.')
        except (ValueError,KeyError,TypeError,OSError) as exc:messagebox.showerror('Preset could not be loaded',str(exc),parent=self.mastering_window)

    def show_export_report(self,filename):
        report=json.loads(Path(filename).with_suffix('.report.json').read_text())['export']
        self.last_export_report=report
        value=report.get('integrated_lufs')
        loud=f'{value:.2f} LUFS' if value is not None else 'LUFS unavailable (short/silent/below gate)'
        summary=f"Saved {Path(filename).name} · {loud} · {report['true_peak_dbtp']:.2f} dBTP (4× estimate)"
        notes=report.get('warnings',[])
        self.status.set(summary+(' · '+notes[0] if notes else ''))
        messagebox.showinfo('Export complete',summary+'\n\n'+
            ('\n'.join(notes) if notes else ('Peak ceiling verified on the exported WAV.' if report['mastered'] else 'Peak measured on the exported WAV.'))+
            '\n\nFull measurements are in the accompanying .report.json file.',parent=self.root)

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
            self.last_export_report={}
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
            self.last_export_report={}
            self.loop_enabled=False
            self.loop_range=None
            self.loop_a=0
            self.loop_b=len(engine.source) if engine is not None else 0
            self.export_subtype='FLOAT' if engine is not None and getattr(engine,'source_subtype','') in ('FLOAT','DOUBLE') else 'PCM_24'
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
        elif self.controls.preview_original:
            mastering_status='ORIGINAL MONITOR — processing settings retained for export'
        elif not self.controls.master:
            mastering_status='MASTERING OFF — choose a preset or enable mastering'
        else:
            c=self.controls
            mastering_status=(f'{c.preset} · '+('4-BAND COMP' if c.multiband else 'COMP BYPASS')+f' · {c.strength*100:.0f}% · '
                f'EQ {c.bass+pb*c.strength:+.1f} / {c.mid+pm*c.strength:+.1f} / '
                f'{c.treble+pt*c.strength:+.1f} dB · '+(f'EXPORT {c.target_lufs:.1f} LUFS' if c.loudness_target else 'LUFS TARGET OFF'))
        def reading(key):
            value=self.last_meters.get(key)
            return f'{value:.1f}' if value is not None else '—'
        levels=('SESSION I '+reading('integrated_lufs')+'   M '+reading('momentary_lufs')+
                '   S '+reading('short_term_lufs')+' LUFS')
        bands=self.last_meters.get('band_reduction_db',[0.,0.,0.])
        if hasattr(self,'master_meter_text'):
            self.master_meter_text.set(levels+'\nBand reduction L / LM / HM / H: '+
                ' / '.join(f'{v:.1f}' for v in bands)+' dB\nStereo correlation: '+reading('correlation')+' (negative: check mono)\nMeter follows playback, including Level Match. Resets on seek/stop.')
        return dict(loudness_status=levels,loop_enabled=self.loop_enabled,loop_a=self.loop_a/sr,loop_b=self.loop_b/sr,
            focus=self.controls.focus,frequency=self.controls.frequency,width=self.controls.width,
            mastering_status=mastering_status,view=self.view,peaks=self.peaks,monitor=snapshot,playing=active,
            sr=sr,duration=len(engine.source)/sr if engine is not None else 0,
            position=self.position/sr,history=self.history,load=load,misses=misses,
            meter_peaks=meter_peaks,
            gr=self.last_meters.get('compression_db',0) if active and self.controls.master and not self.controls.removed and not self.controls.preview_original else 0,
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
                    self.show_export_report(payload)
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
