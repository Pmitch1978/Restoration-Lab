"""Metal Mastering Studio: shared main-app materials, scaled canvas controls.

All controls are rendered locally. The approved concept is a visual reference,
not a bitmap stretched over a different interface.
"""
from dataclasses import dataclass,replace
from functools import lru_cache
import math
import tkinter as tk
from tkinter import simpledialog
import numpy as np
from PIL import Image,ImageDraw,ImageTk
from scipy import signal
from metal_ui import metal,text,Renderer,TEAL,GOLD,WHITE,MUTED,BLACK
from studio_tools import eq_filters
from mastering_tools import validate

W,H=1440,800
TABS=('EQ','COMPRESSOR','STEREO & LOUDNESS')
COLORS=(TEAL,GOLD,'#61b7ed','#dc916c')
TYPES={'highpass':'High Pass','low_shelf':'Low Shelf','bell':'Bell','high_shelf':'High Shelf','lowpass':'Low Pass'}
BANDS=('low','lowmid','mid','high')

@dataclass
class Hit:
    rect:tuple
    kind:str
    target:str
    low:float=0
    high:float=1
    default:float=0
    step:float=.1
    log:bool=False
    label:str=''

@lru_cache(maxsize=1)
def background():
    im=metal((W,H),True).convert('RGBA');d=ImageDraw.Draw(im)
    d.rounded_rectangle((3,3,W-4,H-4),radius=14,outline='#637173')
    return im

@lru_cache(maxsize=24)
def button_art(w,h,active,tint):
    im=Image.new('RGBA',(w,h));d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,w-1,h-1),radius=3,fill='#050707',outline='#536163')
    if active:d.rounded_rectangle((3,3,w-4,h-4),radius=2,fill='#123330' if tint==TEAL else '#352a15',outline=tint,width=2)
    else:
        im.paste(metal((w-10,h-10)),(5,5));d.line((5,5,w-6,5),fill='#f1f4f2');d.line((5,h-6,w-6,h-6),fill='#6e7476')
    return im

class StudioRenderer:
    """One complete, deterministic design surface; hit map shares its geometry."""
    def __init__(self):self.hits={};self.nodes=[];self.focus=None
    def box(self,rect):
        self.d.rounded_rectangle(rect,radius=7,fill='#11191a',outline='#3d5557')
    def button(self,key,rect,label,active=False,tint=TEAL,kind='button',target=None):
        x,y,w,h=rect;self.im.alpha_composite(button_art(w,h,active,tint),(x,y))
        color=WHITE if active else '#142021'
        if label=='play':self.d.polygon(((x+w*.39,y+h*.26),(x+w*.67,y+h*.5),(x+w*.39,y+h*.74)),fill=color)
        elif label=='stop':self.d.rectangle((x+w*.35,y+h*.28,x+w*.65,y+h*.72),fill=color)
        else:text(self.d,(x+w/2,y+h/2),label,11 if h>=32 else 10,fill=color,anchor='mm',bold=True)
        self.hits[key]=Hit(rect,kind,target or key,label=label)
        if self.focus==key:self.d.rectangle((x+1,y+1,x+w-2,y+h-2),outline=TEAL)
    def select(self,key,rect,label,target):
        x,y,w,h=rect;self.d.rounded_rectangle((x,y,x+w,y+h),radius=2,fill='#0a1213',outline='#546769')
        text(self.d,(x+10,y+h/2),label,12,anchor='lm');self.d.polygon(((x+w-19,y+h/2-3),(x+w-9,y+h/2-3),(x+w-14,y+h/2+3)),fill=MUTED)
        self.hits[key]=Hit(rect,'menu',target,label=label)
        if self.focus==key:self.d.rectangle((x,y,x+w,y+h),outline=TEAL)
    def knob(self,key,rect,label,value,lo,hi,default,step,units='',log=False):
        x,y,w,h=rect;compact=h<=100;cx=x+w/2;cy=y+(43 if compact else 57);r=min(23 if compact else 31,w*.29)
        text(self.d,(cx,y+(5 if compact else 9)),label,9 if compact else 10,anchor='mm',bold=True)
        fraction=np.clip(np.log(max(value,lo)/lo)/np.log(hi/lo) if log else (value-lo)/(hi-lo),0,1)
        for i in range(31):
            a=math.radians(135+i*9);ra=r+5;rb=r+8+(i%5==0)*2
            self.d.line((cx+ra*math.cos(a),cy+ra*math.sin(a),cx+rb*math.cos(a),cy+rb*math.sin(a)),fill='#8f9fa1')
        self.d.ellipse((cx-r-3,cy-r-3,cx+r+3,cy+r+3),fill='#060a0a',outline='#8b9698',width=2)
        disc=Renderer.disc(round(r*2));self.im.alpha_composite(disc,(round(cx-r),round(cy-r)))
        a=math.radians(135+270*fraction);self.d.line((cx+r*.32*math.cos(a),cy+r*.32*math.sin(a),cx+r*.88*math.cos(a),cy+r*.88*math.sin(a)),fill='#141a1b',width=3)
        readout=(x+5,y+(74 if compact else 103),x+w-5,y+(90 if compact else 123))
        self.d.rectangle(readout,fill='#060c0d',outline=TEAL if self.focus==key else '#415456')
        if units=='Hz':display=f'{value/1000:.2f} kHz' if value>=1000 else f'{value:.0f} Hz'
        elif units=='%':display=f'{value*100:.0f}%'
        elif units==':1':display=f'{value:.1f}:1'
        elif units=='Q':display=f'{value:.2f}'
        elif units=='ms':display=f'{value:g} ms'
        else:display=f'{value:+.1f} {units}' if units=='dB' else f'{value:.1f} {units}'
        text(self.d,((readout[0]+readout[2])/2,y+(82 if compact else 113)),display,10 if compact else 11,anchor='mm',bold=True)
        self.hits[key]=Hit(rect,'knob',key,lo,hi,default,step,log,label)
    def grid(self,rect,sr,db_range=18):
        x,y,w,h=rect;self.plot=rect;self.maxfreq=min(20000,sr*.45)
        self.d.rectangle((x,y,x+w,y+h),fill=BLACK,outline='#385052')
        for f in (20,30,50,100,200,300,500,1000,2000,3000,5000,10000,20000):
            if f>self.maxfreq:continue
            xx=self.fx(f);self.d.line((xx,y,xx,y+h),fill='#243d3e')
            if f in (20,100,1000,10000,20000):text(self.d,(xx,y+h+10),f'{f//1000}k' if f>=1000 else str(f),10,fill=MUTED,anchor='mm')
        for gain in (-12,-6,0,6,12):
            yy=y+h/2-gain*h/(2*db_range);self.d.line((x,yy,x+w,yy),fill='#385052' if gain==0 else '#203536')
            text(self.d,(x-7,yy),f'{gain:+}',10,fill=MUTED,anchor='rm')
    def fx(self,f):return self.plot[0]+self.plot[2]*np.log(np.clip(f,20,self.maxfreq)/20)/np.log(self.maxfreq/20)
    def spectrum(self,audio,sr):
        if audio is None or len(audio)<32:return
        mono=np.mean(audio,axis=1);n=len(mono);m=np.abs(np.fft.rfft(mono*np.hanning(n)))*2/max(1,n)
        f=np.fft.rfftfreq(n,1/sr);valid=(f>=20)&(f<=self.maxfreq);f=f[valid];m=m[valid]
        if not len(f):return
        x,y,w,h=self.plot;db=20*np.log10(np.maximum(m,1e-9));points=[(self.fx(a),y+h-np.clip((b+90)/90,0,1)*h*.8) for a,b in zip(f,db)]
        if len(points)>1:self.d.polygon([(x,y+h)]+points+[(x+w,y+h)],fill='#283333');self.d.line(points,fill='#5a6465',width=1)
    def bar(self,x,y,w,h,value,color=TEAL,maximum=60):
        self.d.rectangle((x,y,x+w,y+h),fill='#030708',outline='#3a5052')
        for i in range(34):
            yy=y+h-6-i*(h-10)/34;on=i/34<np.clip(value/maximum,0,1)
            self.d.rectangle((x+4,yy-3,x+w-4,yy),fill=color if on else '#152929')
    def meters(self,state):
        x=1264;text(self.d,(1313,124),'OUTPUT',11,anchor='mm',bold=True);text(self.d,(1390,124),'GR',11,anchor='mm',bold=True)
        audio=state.get('audio');peaks=np.max(abs(audio),axis=0) if audio is not None and len(audio) else np.zeros(2)
        for i,label in enumerate(('L','R')):
            xx=x+i*44;text(self.d,(xx+12,146),label,10,anchor='mm',fill=MUTED)
            value=20*np.log10(max(float(peaks[min(i,len(peaks)-1)]),1e-9))
            self.bar(xx,163,25,233,max(0,value+60))
        gr=state.get('meters',{}).get('compression_db',0)
        self.bar(1379,163,25,233,gr,GOLD,12)
        for db in (0,-12,-24,-36,-48,-60):text(self.d,(1257,166-db/60*225),str(db),9,anchor='rm',fill=MUTED)
        for db in (0,3,6,9,12):text(self.d,(1412,166+db/12*225),str(db),9,anchor='lm',fill=MUTED)
        text(self.d,(1313,414),'SAMPLE PEAK',9,anchor='mm',fill=MUTED);text(self.d,(1390,414),'COMP',9,anchor='mm',fill=MUTED)
    def render(self,c,tab=0,state=None,focus=None):
        state=state or {};self.hits={};self.nodes=[];self.focus=focus
        self.im=background().copy();self.d=ImageDraw.Draw(self.im)
        text(self.d,(35,42),'RESTORATION LAB',29,anchor='lm',bold=True)
        text(self.d,(415,42),'MASTERING STUDIO · VERSION 3.0',15,anchor='lm',fill=MUTED)
        self.button('master',(1025,21,205,42),'MASTERING ON' if c.master else 'MASTERING OFF',c.master,GOLD)
        self.button('close',(1250,21,155,42),'CLOSE')
        self.box((22,79,1417,716))
        for i,label in enumerate(TABS):self.button('tab'+str(i),(40+i*222,91,208,32),label,tab==i)
        self.sr=state.get('sr',48000);self.audio=state.get('audio')
        if tab==0:self.eq(c)
        elif tab==1:self.compressor(c,state)
        else:self.stereo(c,state)
        self.meters(state)
        self.box((22,729,1417,781))
        self.button('play',(40,738,60,34),'play',state.get('playing',False))
        self.button('stop',(112,738,60,34),'stop')
        self.select('preset',(208,738,214,34),c.preset,'preset')
        self.button('load',(438,738,170,34),'LOAD PRESET');self.button('save',(624,738,170,34),'SAVE PRESET')
        self.button('bypass',(880,738,207,34),'BYPASS ALL',state.get('bypass',False),GOLD)
        self.button('match',(1103,738,290,34),'LEVEL MATCH',c.match,GOLD)
        self.last_status=state.get('status','')
        return self.im
    def eq(self,c):
        self.grid((72,153,1146,243),self.sr);self.spectrum(self.audio,self.sr)
        f=np.geomspace(20,self.maxfreq,500);_,h=signal.sosfreqz(eq_filters(c,self.sr),worN=f,fs=self.sr);db=20*np.log10(np.maximum(abs(h),1e-9))
        pts=[(self.fx(v),np.clip(274-g*243/36,153,396)) for v,g in zip(f,db)]
        self.d.line(pts,fill=TEAL,width=3)
        for i,b in enumerate(c.eq_bands):
            if not b.enabled:continue
            freq=np.clip(b.frequency,20,self.maxfreq);gain=float(np.interp(freq,f,db));x=self.fx(freq);y=float(np.clip(274-gain*243/36,161,388))
            self.d.ellipse((x-10,y-10,x+10,y+10),fill=BLACK,outline=TEAL,width=2);text(self.d,(x,y),i+1,11,anchor='mm',bold=True)
            self.nodes.append((i,x,y))
        self.button('eq_enable',(1004,124,214,27),'EQ ENABLED' if c.eq_enabled else 'EQ BYPASSED',c.eq_enabled,target='eq_enabled')
        text(self.d,(75,432),'6-BAND PARAMETRIC EQ',11,fill=MUTED)
        for i,b in enumerate(c.eq_bands):
            x=35+i*232;self.box((x,455,x+222,698));text(self.d,(x+13,477),f'BAND {i+1}',12,anchor='lm',bold=True)
            self.button(f'eq.{i}.enabled',(x+156,464,54,25),'ON' if b.enabled else 'OFF',b.enabled,target=f'eq.{i}.enabled')
            self.select(f'eq.{i}.kind',(x+12,500,198,30),TYPES[b.kind],f'eq.{i}.kind')
            for j,(label,key,lo,hi,default,step,units,log) in enumerate((('FREQ','frequency',10,22000,ControlsDefaults.eq_bands[i].frequency,10,'Hz',True),('GAIN','gain',-18,18,0,.1,'dB',False),('Q','q',.1,18,.707,.05,'Q',True))):
                self.knob(f'eq.{i}.{key}',(x+7+j*70,551,70,125),label,getattr(b,key),lo,hi,default,step,units,log)
        text(self.d,(42,701),'Drag nodes: frequency / gain · Wheel: Q · Double-click knob: type value · Right-click: reset',10,fill=MUTED)
    def compressor(self,c,state):
        self.grid((72,153,1146,243),self.sr);f=np.geomspace(20,self.maxfreq,500);remaining=np.ones(len(f),complex)
        for i,frequency in enumerate((c.crossover_low,c.crossover_mid,c.crossover_high)):
            sos=signal.butter(2,min(frequency,self.sr*.45),fs=self.sr,output='sos');_,lp=signal.sosfreqz(sos,worN=f,fs=self.sr)
            sos=signal.butter(2,min(frequency,self.sr*.45),'highpass',fs=self.sr,output='sos');_,hp=signal.sosfreqz(sos,worN=f,fs=self.sr)
            self.band_curve(f,remaining*lp**2,COLORS[i]);remaining*=hp**2
        self.band_curve(f,remaining,COLORS[3])
        for i,(key,value) in enumerate(zip(('crossover_low','crossover_mid','crossover_high'),(c.crossover_low,c.crossover_mid,c.crossover_high))):
            x=self.fx(value);self.d.line((x,153,x,396),fill=COLORS[i],width=2)
            self.d.ellipse((x-5,155,x+5,165),fill=COLORS[i]);text(self.d,(x,174),f'{value:g} Hz',11,anchor='mm',fill=COLORS[i],bold=True)
            self.hits[key]=Hit((x-12,151,24,245),'cross',key,40 if i==0 else 80 if i==1 else 160,1000 if i==0 else 6000 if i==1 else 16000,value,10,True)
        self.button('comp_enable',(996,124,222,27),'COMP ON · STEREO LINKED' if c.multiband else 'COMP BYPASSED',c.multiband,target='multiband')
        reductions=state.get('meters',{}).get('band_reduction_db',[0]*4)
        for i,name in enumerate(BANDS):
            x=35+i*348;self.box((x,449,x+336,698));text(self.d,(x+16,468),('LOW','LOW MID','HIGH MID','HIGH')[i],14,anchor='lm',bold=True)
            params=(('THRESHOLD','threshold',-60,0,-18,.5,'dB'),('RATIO','ratio',1,20,2,.1,':1'),('ATTACK','attack',.1,200,20,1,'ms'),('RELEASE','release',10,2000,150,10,'ms'),('KNEE','knee',0,24,6,.5,'dB'),('MAKEUP','makeup',-18,18,0,.1,'dB'))
            for j,(label,key,lo,hi,default,step,unit) in enumerate(params):
                # Compact 92px knob artwork with 110px row pitch.
                xx=x+8+(j%3)*91;yy=480+(j//3)*92
                self.comp_knob(name+'_'+key,(xx,yy,88,90),label,getattr(c,name+'_'+key),lo,hi,default,step,unit)
            self.bar(x+299,491,19,166,reductions[i] if i<len(reductions) else 0,GOLD,12)
            text(self.d,(x+309,482),'GR',9,anchor='mm',fill=MUTED)
            self.button(name+'_bypass',(x+12,664,151,26),'BYPASS',getattr(c,name+'_bypass'),target=name+'_bypass')
            self.button(name+'_solo',(x+173,664,151,26),'SOLO',getattr(c,name+'_solo'),target=name+'_solo')
        text(self.d,(42,701),'Drag crossover markers · Ratio is scaled by main Strength · Solo is monitor only',10,fill=MUTED)
    def comp_knob(self,key,rect,label,value,lo,hi,default,step,unit):
        self.knob(key,rect,label,value,lo,hi,default,step,unit)
    def band_curve(self,f,h,color):
        x,y,w,hh=self.plot;db=20*np.log10(np.maximum(abs(h),1e-8));pts=[(self.fx(v),float(np.clip(y+hh/2-g*hh/36,y,y+hh))) for v,g in zip(f,db)]
        layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer);rgb=tuple(bytes.fromhex(color.lstrip('#')))
        d.polygon([(x,y+hh)]+pts+[(x+w,y+hh)],fill=(*rgb,28));self.im.alpha_composite(layer);self.d.line(pts,fill=color,width=2)
    def stereo(self,c,state):
        self.box((37,148,625,697));self.box((643,148,1231,697))
        text(self.d,(59,176),'S T E R E O  I M A G E',18,bold=True);text(self.d,(665,176),'L O U D N E S S  &  L I M I T I N G',16,bold=True)
        self.d.rectangle((60,211,380,526),fill=BLACK,outline='#3d5557')
        cx,cy,r=220,369,137
        for rr in (r,r*.5):self.d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),outline='#315153')
        for a in (0,np.pi/4,np.pi/2,np.pi*3/4):self.d.line((cx-r*np.cos(a),cy-r*np.sin(a),cx+r*np.cos(a),cy+r*np.sin(a)),fill='#203d3e')
        text(self.d,(cx,cy-r-5),'M',12,anchor='mm');text(self.d,(cx-r-6,cy),'L',12,anchor='mm');text(self.d,(cx+r+6,cy),'R',12,anchor='mm');text(self.d,(cx,cy+r+7),'S',12,anchor='mm')
        audio=self.audio
        if audio is not None and len(audio):
            l=audio[:,0];rr=audio[:,min(1,audio.shape[1]-1)];mid=(l+rr)*.5;side=(l-rr)*.5
            scale=max(float(np.max(abs(mid))),float(np.max(abs(side))),.05)
            for m,s in zip(mid[::3],side[::3]):
                xx=cx+s/scale*r*.88;yy=cy-m/scale*r*.88;self.d.ellipse((xx,yy,xx+1,yy+1),fill='#309f99')
        self.knob('stereo_width',(407,214,180,130),'WIDTH',c.stereo_width,0,2,1,.01,'%',False)
        self.knob('bass_protect_hz',(407,382,180,130),'BASS PROTECT',c.bass_protect_hz,40,400,120,5,'Hz',True)
        self.button('width_enabled',(413,539,179,30),'WIDTH ON' if c.stereo_enabled else 'WIDTH BYPASS',c.stereo_enabled,target='stereo_enabled')
        corr=state.get('meters',{}).get('correlation');text(self.d,(60,552),'CORRELATION',11,bold=True)
        self.d.rectangle((60,576,380,597),fill=BLACK,outline='#486364')
        if corr is not None:
            width=np.clip((corr+1)*.5,0,1)*312;self.d.rectangle((64,580,64+width,593),fill=TEAL if corr>=0 else GOLD)
        for value,x in ((-1,60),(0,220),(1,380)):text(self.d,(x,612),f'{value:+}',10,anchor='mm',fill=MUTED)
        self.button('bass_protect',(60,647,253,31),'BASS PROTECT ON' if c.bass_protect else 'BASS PROTECT OFF',c.bass_protect,target='bass_protect')
        self.button('mono_audition',(328,647,273,31),'MONO AUDITION',c.mono_audition,target='mono_audition')
        self.d.rectangle((664,211,1209,349),fill=BLACK,outline='#3d5557')
        meters=state.get('meters',{});report=state.get('export',{})
        for i,(label,value,units) in enumerate((('INTEGRATED',meters.get('integrated_lufs'),'LUFS'),('SHORT TERM',meters.get('short_term_lufs'),'LUFS'),('TRUE PEAK',report.get('true_peak_dbtp'),'dBTP · LAST EXPORT'))):
            x=675+i*177;text(self.d,(x+80,231),label,11,anchor='mm',bold=True)
            text(self.d,(x+80,279),'—' if value is None else f'{value:.1f}',32,anchor='mm',fill=TEAL,bold=True)
            text(self.d,(x+80,324),units,10,anchor='mm',fill=MUTED)
        for i,(key,label,lo,hi,default,step,unit) in enumerate((('target_lufs','TARGET LUFS',-30,-6,-14,.5,'LUFS'),('ceiling_dbtp','PEAK CEILING',-6,-.1,-1,.1,'dBTP'),('max_limiting_db','LIMITING BUDGET',0,12,6,.5,'dB'))):
            self.knob(key,(665+i*181,401,174,130),label,getattr(c,key),lo,hi,default,step,unit)
        self.button('loudness_target',(668,578,260,34),'LUFS TARGET ON' if c.loudness_target else 'LUFS TARGET OFF',c.loudness_target,target='loudness_target')
        text(self.d,(667,637),'Stereo output · Full-song export',12,fill=MUTED)
        text(self.d,(667,662),'Playback: sample ceiling · Export: 4× peak verification',10,fill=MUTED)

from reference_engine import Controls
ControlsDefaults=Controls()

class MasteringStudio:
    def __init__(self,app):
        self.app=app;self.tab=0;self.renderer=StudioRenderer();self.drag=None;self.focus=None;self.job=None;self.photo=None;self.size=None
        self.window=tk.Toplevel(app.root);self.window.title('Restoration Lab 3.0 · Mastering Studio');self.window.geometry('1200x667');self.window.minsize(1008,560);self.window.configure(background='#111718')
        app.mastering_window=self.window
        self.canvas=tk.Canvas(self.window,background='#101617',highlightthickness=0,takefocus=True);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda event:self.paint())
        self.canvas.bind('<Button-1>',self.down);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag',None))
        self.canvas.bind('<Double-Button-1>',self.edit);self.canvas.bind('<Button-3>',self.reset)
        self.canvas.bind('<MouseWheel>',self.wheel);self.canvas.bind('<Button-4>',self.wheel);self.canvas.bind('<Button-5>',self.wheel)
        self.canvas.bind('<Key>',self.key)
        self.window.protocol('WM_DELETE_WINDOW',self.close);self.window.bind('<Destroy>',self.destroyed,add='+')
        self.window.after_idle(lambda:self.canvas.focus_set());self.tick()
    def close(self):
        if self.job is not None:
            try:self.window.after_cancel(self.job)
            except tk.TclError:pass
            self.job=None
        self.window.destroy()
    def destroyed(self,event):
        if event.widget is self.window and self.job is not None:
            try:self.window.after_cancel(self.job)
            except tk.TclError:pass
            self.job=None
    def state(self):
        a=self.app;engine=a.restoration
        return dict(sr=engine.sr if engine is not None else 48000,audio=a.monitor_audio if a.playing else None,meters=a.last_meters if a.playing else {},export=getattr(a,'last_export_report',{}),playing=a.playing,bypass=a.bypass.get())
    def paint(self):
        if not self.window.winfo_exists():return
        image=self.renderer.render(self.app.controls,self.tab,self.state(),self.focus)
        w,h=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height());scale=min(w/W,h/H);self.scale=scale;self.offset=((w-W*scale)/2,(h-H*scale)/2)
        image=image.resize((max(1,round(W*scale)),max(1,round(H*scale))),Image.Resampling.LANCZOS)
        self.photo=ImageTk.PhotoImage(image,master=self.window);self.canvas.delete('art');self.canvas.create_image(*self.offset,image=self.photo,anchor='nw',tags='art')
    def tick(self):
        self.paint();self.job=self.window.after(150,self.tick)
    def xy(self,event):return ((event.x-self.offset[0])/self.scale,(event.y-self.offset[1])/self.scale)
    def hit(self,event):
        x,y=self.xy(event)
        for key,hit in reversed(list(self.renderer.hits.items())):
            a,b,w,h=hit.rect
            if a<=x<=a+w and b<=y<=b+h:return key,hit
        return None,None
    def variable(self,target):
        if target.startswith('eq.'):
            _,index,key=target.split('.');return self.app.eq_vars[int(index)][key]
        return self.app.vars.get(target) or self.app.advanced_flags.get(target)
    def set_value(self,target,value,hit=None):
        if hit:value=np.clip(value,hit.low,hit.high)
        if target.startswith('crossover_'):
            c=self.app.controls;sr=self.state()['sr']
            if target=='crossover_low':value=np.clip(value,40,min(1000,c.crossover_mid/2))
            elif target=='crossover_mid':value=np.clip(value,c.crossover_low*2,min(6000,c.crossover_high/2))
            else:value=np.clip(value,c.crossover_mid*2,min(16000,sr*.45-1))
            try:validate(replace(c,**{target:float(value)}),sr)
            except ValueError:return
        self.variable(target).set(float(value));self.paint()
    def down(self,event):
        self.canvas.focus_set();key,hit=self.hit(event);self.focus=key
        if hit:
            if hit.kind in ('knob','cross'):self.drag=(key,*self.xy(event),self.variable(hit.target).get())
            elif hit.kind=='menu':self.menu(hit,event)
            else:self.action(hit.target)
        elif self.tab==0:
            x,y=self.xy(event)
            for i,xx,yy in self.renderer.nodes:
                if (x-xx)**2+(y-yy)**2<20**2:self.drag=('node'+str(i),x,y,0);break
        self.paint()
    def motion(self,event):
        if self.drag is None:return
        key,x0,y0,initial=self.drag;x,y=self.xy(event)
        if key.startswith('node'):
            index=int(key[4:]);plot=self.renderer.plot
            frequency=20*(self.renderer.maxfreq/20)**np.clip((x-plot[0])/plot[2],0,1)
            self.variable(f'eq.{index}.frequency').set(float(frequency))
            if self.app.controls.eq_bands[index].kind not in ('highpass','lowpass'):
                c=self.app.controls
                bands=list(c.eq_bands);bands[index]=replace(bands[index],gain=0.)
                _,other=signal.sosfreqz(eq_filters(replace(c,eq_bands=tuple(bands)),self.state()['sr']),worN=[frequency],fs=self.state()['sr'])
                offset=20*np.log10(max(abs(other[0]),1e-9))
                self.variable(f'eq.{index}.gain').set(float(np.clip((plot[1]+plot[3]/2-y)*36/plot[3]-offset,-18,18)))
            self.paint();return
        hit=self.renderer.hits.get(key)
        if not hit:return
        if hit.kind=='cross':value=20*(self.renderer.maxfreq/20)**np.clip((x-self.renderer.plot[0])/self.renderer.plot[2],0,1)
        else:
            amount=(y0-y)/180*(.1 if event.state&1 else 1)
            value=initial*(hit.high/hit.low)**amount if hit.log else initial+amount*(hit.high-hit.low)
        self.set_value(hit.target,value,hit)
    def wheel(self,event):
        key,hit=self.hit(event);direction=1 if getattr(event,'num',0)==4 or getattr(event,'delta',0)>0 else -1
        if not hit and self.tab==0:
            x,y=self.xy(event)
            for i,xx,yy in self.renderer.nodes:
                if (x-xx)**2+(y-yy)**2<20**2:
                    var=self.variable(f'eq.{i}.q');var.set(float(np.clip(var.get()+direction*.05,.1,18)));self.paint();return 'break'
        if hit and hit.kind in ('knob','cross'):
            step=hit.step*(.1 if event.state&1 else 1);value=self.variable(hit.target).get()
            self.set_value(hit.target,value*(1+direction*.025) if hit.log else value+direction*step,hit)
        return 'break'
    def edit(self,event=None):
        key,hit=self.hit(event) if event else (self.focus,self.renderer.hits.get(self.focus))
        self.drag=None
        if hit and hit.kind in ('knob','cross'):
            factor=100 if hit.target=='stereo_width' else 1
            prompt=f'Width % ({hit.low*factor:g} to {hit.high*factor:g})' if factor==100 else f'Value ({hit.low:g} to {hit.high:g})'
            value=simpledialog.askfloat(hit.label or hit.target,prompt,parent=self.window,initialvalue=self.variable(hit.target).get()*factor,minvalue=hit.low*factor,maxvalue=hit.high*factor)
            if value is not None:self.set_value(hit.target,value/factor,hit)
    def reset(self,event):
        key,hit=self.hit(event)
        if hit and hit.kind in ('knob','cross'):self.set_value(hit.target,hit.default,hit)
    def key(self,event):
        keys=list(self.renderer.hits)
        if event.keysym in ('Tab','ISO_Left_Tab'):
            i=keys.index(self.focus) if self.focus in keys else -1;self.focus=keys[(i+(-1 if event.state&1 else 1))%len(keys)];self.paint();return 'break'
        hit=self.renderer.hits.get(self.focus)
        if event.keysym=='Escape':self.close();return 'break'
        if event.keysym in ('Return','space'):
            if hit and hit.kind in ('knob','cross'):self.edit()
            elif hit and hit.kind=='menu':
                x,y,w,h=hit.rect;self.menu(hit,None)
            elif hit:self.action(hit.target)
            else:self.app.toggle()
            self.paint();return 'break'
        if hit and hit.kind in ('knob','cross') and event.keysym in ('Left','Down','Right','Up','Home','End'):
            value=hit.low if event.keysym=='Home' else hit.high if event.keysym=='End' else self.variable(hit.target).get()+hit.step*(-1 if event.keysym in ('Left','Down') else 1)
            self.set_value(hit.target,value,hit);return 'break'
    def menu(self,hit,event):
        menu=tk.Menu(self.window,tearoff=False,bg='#142022',fg=WHITE,activebackground='#20514c',activeforeground=WHITE)
        if hit.target=='preset':
            from reference_engine import PRESETS
            choices={k:k for k in PRESETS}
        else:choices=TYPES
        for value,label in choices.items():menu.add_command(label=label,command=lambda value=value:self.choose(hit.target,value))
        if event:x,y=event.x_root,event.y_root
        else:
            a,b,w,h=hit.rect;x=self.canvas.winfo_rootx()+self.offset[0]+a*self.scale;y=self.canvas.winfo_rooty()+self.offset[1]+(b+h)*self.scale
        menu.tk_popup(round(x),round(y))
    def choose(self,target,value):
        if target=='preset':self.app.select_preset(value)
        else:self.variable(target).set(value)
        self.paint()
    def action(self,target):
        a=self.app
        if target.startswith('tab'):self.tab=int(target[-1]);self.focus=None
        elif target=='master':a.master_on.set(not a.master_on.get())
        elif target=='close':self.close();return
        elif target=='play':a.toggle()
        elif target=='stop':a.stop()
        elif target=='load':a.load_studio_preset()
        elif target=='save':a.save_studio_preset()
        elif target=='bypass':a.bypass.set(not a.bypass.get())
        elif target=='match':a.match.set(not a.match.get())
        else:
            var=self.variable(target);var.set(not var.get())
