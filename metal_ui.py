"""Hardware-style artwork shared by Tk controls and the headless preview.

All artwork is drawn locally; no downloaded skin or image-generation asset is
required. Coordinates use a 1280 x 740 design grid and scale with the window.
"""
from functools import lru_cache
from pathlib import Path
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 740
WHITE = '#f0f2f2'
MUTED = '#9ca6a9'
TEAL = '#40d2c5'
GOLD = '#e8b557'
BLACK = '#080d0e'


@lru_cache(maxsize=40)
def font(size, bold=False):
    name = 'Arial Bold.ttf' if bold else 'Arial.ttf'
    paths = [str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('arialbd.ttf' if bold else 'arial.ttf')),
             f'/System/Library/Fonts/Supplemental/{name}',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else
             '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text(draw, xy, label, size=11, fill=WHITE, anchor='la', bold=False):
    draw.text(xy, str(label), font=font(size, bold), fill=fill, anchor=anchor)


def shorten(label, length=64):
    return label if len(label) <= length else label[:length-1]+'…'


def metal(size, dark=False):
    w, h = size
    rng = np.random.default_rng(4)
    yy = np.arange(h)[:, None]
    xx = np.arange(w)[None, :]
    if dark:
        level = 24 + 4*np.cos(yy/h*np.pi) + rng.normal(0, 1.0, (h, 1))
        level = level + rng.normal(0, .55, (h, w)) + 2*xx/max(1, w)
    else:
        level = 160 + 46*np.cos((yy/h-.36)*np.pi)
        level = level + 12*np.sin(xx/max(1,w)*np.pi) + rng.normal(0, 1.0, (h, 1))
        level = level + rng.normal(0, .6, (h,w))
    array = np.clip(level, 0, 255).astype('uint8')
    return Image.fromarray(np.repeat(array[..., None], 3, axis=2), 'RGB')


BUTTONS = {
    'guide': (870, 23, 128, 34, 'USER GUIDE'),
    'open': (1010, 23, 108, 34, 'LOAD AUDIO'),
    'export': (1130, 23, 116, 34, 'EXPORT'),
    'wave': (48, 92, 132, 24, 'WAVEFORM'),
    'spectrum': (182, 92, 132, 24, 'SPECTRUM'),
    'reduction': (316, 92, 132, 24, 'REDUCTION'),
    'off': (48, 398, 128, 32, 'OFF'),
    'stft': (187, 398, 128, 32, 'STFT'),
    'wavelet': (326, 398, 128, 32, 'WAVELET'),
    'both': (465, 398, 138, 32, 'BOTH'),
    'drift': (340, 447, 263, 30, 'DRIFT CORRECTION'),
    'removed': (340, 491, 263, 30, 'LISTEN TO REMOVED'),
    'profile': (340, 577, 263, 26, 'PROFILE / DETAILS'),
    'preset': (1070, 370, 158, 26, 'NATURAL   ▾'),
    'ab': (663, 580, 174, 27, 'A · MASTERING OFF'),
    'bypass': (847, 580, 154, 27, 'BYPASS ALL'),
    'match': (1011, 580, 218, 27, 'LEVEL MATCH'),
    'rewind': (48, 651, 52, 37, 'rewind'),
    'play': (112, 651, 52, 37, 'play'),
    'pause': (176, 651, 52, 37, 'pause'),
    'stop': (240, 651, 52, 37, 'stop'),
}

# x, y, width, height, label, low, high, default, units
KNOBS = {
    'spectral_amount': (48, 438, 124, 139, 'STFT AMOUNT', 0, 100, 100, '%'),
    'wavelet_amount': (188, 438, 124, 139, 'WAVELET AMOUNT', 0, 100, 100, '%'),
    'strength': (653, 438, 116, 139, 'STRENGTH', 0, 100, 50, '%'),
    'bass': (766, 438, 116, 139, 'BASS', -6, 6, 0, 'dB'),
    'mid': (876, 438, 116, 139, 'MID', -6, 6, 0, 'dB'),
    'treble': (986, 438, 116, 139, 'TREBLE', -6, 6, 0, 'dB'),
    'output_db': (1098, 438, 116, 139, 'OUTPUT', -18, 12, 0, 'dB'),
}

SLIDERS = {
    'nr_strength': (340, 528, 263, 46, 'NR STRENGTH', 0, 100, 100, '%'),
}


class Renderer:
    plot_rect = (48, 125, 992, 203)
    meter_rect = (1057, 90, 178, 239)
    footer_rect = (314, 645, 916, 53)

    def __init__(self):
        self.base = self.faceplate()
        self._wave_key = None
        self._wave_image = None

    def faceplate(self):
        im = metal((WIDTH, HEIGHT), dark=True)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((3, 3, 1276, 736), radius=13, outline='#70777b', width=1)
        d.line((18, 73, 1262, 73), fill='#050707', width=2)
        d.line((18, 75, 1262, 75), fill='#3f4547')
        text(d, (40, 35), 'RESTORATION LAB', 29, anchor='lm', bold=True)
        text(d, (358, 35), 'Version 1.5', 16, anchor='lm')
        d.line((477, 22, 477, 51), fill='#6b7376')
        text(d, (495, 29), 'ADAPTIVE RESTORATION', 11)
        text(d, (495, 45), '& MASTERING', 11, fill=MUTED)
        for box in [(28, 82, 1252, 342), (28, 358, 625, 615),
                    (642, 358, 1252, 615), (28, 631, 1252, 706)]:
            d.rounded_rectangle(box, radius=8, fill='#15191a', outline='#454d50', width=1)
            d.rounded_rectangle((box[0]+3, box[1]+3, box[2]-3, box[3]-3),
                                radius=6, outline='#070a0b')
        d.rounded_rectangle((36, 87, 1244, 336), radius=6, fill=BLACK, outline='#1e3737')
        text(d, (48, 380), 'R E S T O R A T I O N', 17, anchor='lm', bold=True)
        d.line((307, 380, 601, 380), fill='#4d5558')
        text(d, (663, 380), 'M A S T E R I N G', 17, anchor='lm', bold=True)
        text(d, (1008, 383), 'PRESET', 10, anchor='lm', fill=MUTED)
        text(d, (48, 597), 'STFT: up to 7 dB   /   Wavelet: up to 2 dB', 10, fill=MUTED)
        text(d, (48, 697), 'FILE PLAYBACK', 8, fill=MUTED)
        for x in (16, 1264):
            for y in (16, 724):
                d.ellipse((x-7,y-7,x+7,y+7),fill='#070909',outline='#555e62')
                d.ellipse((x-5,y-5,x+5,y+5),fill='#989fa1',outline='#d6d9d9')
                d.line((x-3,y-3,x+3,y+3),fill='#303436',width=2)
                d.line((x-3,y+3,x+3,y-3),fill='#303436',width=2)
        return im

    def button(self, key, label=None, active=False, enabled=True, focus=False):
        _, _, w, h, title = BUTTONS[key]
        title = label or title
        im = Image.new('RGBA', (w,h))
        d = ImageDraw.Draw(im)
        tint = GOLD if key in ('ab','match','preset') else TEAL
        if key == 'bypass': tint = GOLD
        d.rounded_rectangle((0,0,w-1,h-1),radius=3,fill='#050707',outline='#50585a')
        if active:
            d.rounded_rectangle((2,2,w-3,h-3),radius=2,fill='#10302f' if tint==TEAL else '#352a15',outline=tint,width=2)
        else:
            inner = metal((w-8,h-8))
            im.paste(inner,(4,4))
            d.line((4,4,w-5,4),fill='#eeeeec')
            d.line((4,h-5,w-5,h-5),fill='#6e7476')
            d.line((w-5,5,w-5,h-5),fill='#72787a')
        color = WHITE if active else '#161b1c'
        if not enabled:
            color = '#777f80'
        cx, cy = w//2, h//2
        if title in ('play','rewind','pause','stop'):
            if title == 'play': d.polygon([(cx-5,cy-9),(cx+8,cy),(cx-5,cy+9)],fill=color)
            elif title == 'pause':
                d.rectangle((cx-7,cy-8,cx-3,cy+8),fill=color)
                d.rectangle((cx+3,cy-8,cx+7,cy+8),fill=color)
            elif title == 'stop': d.rectangle((cx-7,cy-7,cx+7,cy+7),fill=color)
            else:
                d.polygon([(cx+7,cy-8),(cx-4,cy),(cx+7,cy+8)],fill=color)
                d.rectangle((cx-8,cy-8,cx-5,cy+8),fill=color)
        else:
            text(d,(cx,cy),title,10 if h<29 else 11,fill=color,anchor='mm',bold=True)
        if focus: d.rectangle((1,1,w-2,h-2),outline=TEAL)
        return im

    def knob(self, key, value, focus=False):
        _, _, w, h, title, low, high, default, units = KNOBS[key]
        im = Image.new('RGBA',(w,h))
        d = ImageDraw.Draw(im)
        cx, cy, r = w/2, 63, 34 if key in ('bass','mid','treble','output_db') else 37
        text(d,(cx,7),title,11,anchor='mm',bold=True)
        for i in range(31):
            angle = math.radians(135+i*9)
            a, b = r+7, r+10+(2 if i%5==0 else 0)
            color = TEAL if key in ('spectral_amount','wavelet_amount') and i/30 <= (value-low)/(high-low) else '#a7afb2'
            d.line((cx+a*math.cos(angle),cy+a*math.sin(angle),
                    cx+b*math.cos(angle),cy+b*math.sin(angle)),fill=color,width=1)
        d.ellipse((cx-r-4,cy-r-3,cx+r+4,cy+r+5),fill='#070909',outline='#616a6e',width=2)
        # Brushed, radial aluminum with a machined rim. Cached by geometry.
        disc = self.disc(round(r*2))
        im.alpha_composite(disc,(round(cx-r),round(cy-r)))
        angle = math.radians(135+270*(value-low)/(high-low))
        p1=(cx+(r*.36)*math.cos(angle),cy+(r*.36)*math.sin(angle))
        p2=(cx+(r*.86)*math.cos(angle),cy+(r*.86)*math.sin(angle))
        d.line((*p1,*p2),fill='#171b1b',width=3)
        d.rounded_rectangle((cx-46,119,cx+46,138),radius=2,fill='#070c0d',outline='#3b4547')
        display = f'{value:.0f}%' if units=='%' else f'{value:+.1f} dB' if abs(value)>.049 else '0.0 dB'
        text(d,(cx,129),display,12,anchor='mm',bold=True)
        if focus: d.rounded_rectangle((cx-49,116,cx+49,138),radius=3,outline=TEAL)
        return im

    def slider(self,key,value,focus=False):
        _,_,w,h,title,low,high,default,units=SLIDERS[key]
        im=Image.new('RGBA',(w,h))
        d=ImageDraw.Draw(im)
        text(d,(0,5),title,10,anchor='lm',bold=True)
        text(d,(w-2,5),f'{value:.0f}%',10,anchor='rm')
        d.rounded_rectangle((0,18,w-1,31),radius=3,fill='#040809',outline='#4a5558')
        end=12+(w-25)*(value-low)/(high-low)
        d.rectangle((8,23,max(9,end),26),fill=TEAL)
        cap=metal((20,21))
        im.paste(cap,(round(end)-10,14))
        d.rectangle((round(end)-10,14,round(end)+9,34),outline='#d3d9d9')
        d.line((end,18,end,30),fill='#586467')
        for i in range(11):
            x=12+(w-25)*i/10
            d.line((x,36,x,39),fill='#8d999d')
        if focus: d.rectangle((0,12,w-1,35),outline=TEAL)
        return im

    @staticmethod
    @lru_cache(maxsize=4)
    def disc(size):
        yy, xx = np.mgrid[0:size,0:size]
        x=(xx-(size-1)/2)/(size/2)
        y=(yy-(size-1)/2)/(size/2)
        radius=np.sqrt(x*x+y*y)
        angle=np.arctan2(y,x)
        level=179+28*np.cos(angle*2+.8)+12*np.sin(angle*5)+7*np.cos(radius*size*3)
        level += 16*(-x-y)/2
        level = np.where(radius>.95,226-52*x,level)
        alpha=np.clip((1-radius)*size*2,0,1)*255
        rgb=np.repeat(np.clip(level,0,255)[...,None],3,axis=2)
        rgba=np.concatenate([rgb,alpha[...,None]],axis=2).astype('uint8')
        return Image.fromarray(rgba,'RGBA')

    def plot(self, state):
        _, _, w, h = self.plot_rect
        view = state.get('view','wave')
        peaks=state.get('peaks')
        key=(id(peaks),state.get('duration',0),view)
        if key != self._wave_key or view != 'wave':
            im=Image.new('RGB',(w,h),BLACK)
            d=ImageDraw.Draw(im)
            for x in range(0,w,99): d.line((x,0,x,167),fill='#16312f')
            if view=='wave':
                for center in (39,117): d.line((0,center,w,center),fill='#24423f')
                for y in (0,78,156): d.line((0,y,w,y),fill='#182e2d')
                if peaks is not None:
                    channels=peaks.shape[0]
                    for ch in range(channels):
                        center=(ch+.5)*156/channels
                        height=69/channels
                        for x in range(w):
                            i=min(peaks.shape[1]-1,x*peaks.shape[1]//w)
                            low,high=np.clip(peaks[ch,i],-1,1)
                            d.line((x,center-high*height,x,center-low*height),fill=TEAL)
                else:
                    text(d,(w//2,73),'LOAD WAV OR MP3 TO BEGIN',17,fill=MUTED,anchor='mm')
                    text(d,(w//2,99),'Full-song analysis · real-time restoration · live mastering',11,fill=MUTED,anchor='mm')
                duration=state.get('duration',0)
                for i in range(6):
                    seconds=duration*i/5
                    stamp=f'{int(seconds)//60}:{int(seconds)%60:02}'
                    text(d,(min(w-1,max(1,i*(w-2)/5)),163),stamp,9,fill=MUTED,
                         anchor='la' if i==0 else 'ra' if i==5 else 'ma')
            elif view=='spectrum':
                for db in (-12,-36,-60,-84):
                    y=9+(-db)/96*140
                    d.line((0,y,w,y),fill='#24403d')
                    text(d,(w-5,y-3),f'{db} dBFS',9,fill=MUTED,anchor='rd')
                snapshot=state.get('monitor')
                if snapshot is not None and state.get('playing'):
                    data=np.mean(snapshot,axis=1)
                    n=len(data)
                    window=np.hanning(n)
                    magnitude=np.abs(np.fft.rfft(data*window))*2/max(1,window.sum())
                    freq=np.fft.rfftfreq(n,1/state.get('sr',48000))
                    logfreq=np.geomspace(25,20000,400)
                    level=np.interp(logfreq,freq,20*np.log10(np.maximum(magnitude,1e-8)))
                    points=[(i*(w-1)/399,9+np.clip(-db,0,96)/96*140) for i,db in enumerate(level)]
                    d.polygon([(0,155),*points,(w-1,155)],fill='#0b302c')
                    d.line(points,fill=TEAL,width=2)
                else:
                    text(d,(w//2,75),'PLAY AUDIO TO VIEW THE OUTPUT SPECTRUM',13,fill=MUTED,anchor='mm')
                for f in (30,100,300,1000,3000,10000,20000):
                    x=np.log(f/25)/np.log(20000/25)*(w-1)
                    text(d,(min(w-25,max(13,x)),165),f'{f/1000:g}k' if f>=1000 else str(f),9,fill=MUTED,anchor='ma')
            else:
                for db in (0,3,6,9,12):
                    y=10+db/12*140
                    d.line((0,y,w,y),fill='#24403d')
                    text(d,(w-5,y+1),str(db)+' dB',9,fill=MUTED,anchor='ra')
                self.reduction_lines(d,state.get('history',[]),w,10,140)
                text(d,(0,165),'RECENT PLAYBACK  /  0–12 dB',9,fill=MUTED)
            if view=='wave':
                self._wave_key=key
                self._wave_image=im.copy()
        else:
            im=self._wave_image.copy()
        d=ImageDraw.Draw(im)
        if view=='wave' and state.get('duration',0)>0:
            x=round(np.clip(state.get('position',0)/state['duration'],0,1)*(w-1))
            d.line((x,0,x,157),fill='#e4ebe8',width=1)
        if view!='reduction':
            d.rectangle((0,180,w,202),fill='#090f10')
            self.reduction_lines(d,state.get('history',[]),w,182,18)
        return im

    @staticmethod
    def reduction_lines(d,history,w,top,height):
        for band,color in ((0,TEAL),(1,GOLD)):
            points=[(i/239*(w-1),top+min(12,max(0,pair[band]))/12*height)
                    for i,pair in enumerate(history[-240:])]
            if len(points)>1: d.line(points,fill=color,width=1)

    def meters(self,state):
        _,_,w,h=self.meter_rect
        im=Image.new('RGB',(w,h),BLACK)
        d=ImageDraw.Draw(im)
        text(d,(53,10),'OUTPUT',11,anchor='mm')
        text(d,(149,10),'GR',11,anchor='mm')
        for x,label in ((47,'L'),(88,'R'),(149,'dB')):
            text(d,(x,32),label,10,fill=MUTED,anchor='mm')
        peaks=state.get('meter_peaks',[-90,-90])
        gr=state.get('gr',0)
        for ch,x in enumerate((37,78,139)):
            d.rectangle((x-4,47,x+23,220),fill='#030707',outline='#2d4140')
            for i in range(28):
                if ch<2:
                    threshold=-60+i/27*60
                    lit=peaks[min(ch,len(peaks)-1)]>=threshold
                    color='#e24f3d' if i>=26 else GOLD if i>=22 else TEAL
                    y=213-i*5.9
                else:
                    lit=gr>=(i+1)/28*12
                    color=GOLD
                    y=51+i*5.9
                d.rectangle((x,y,x+18,y+3),fill=color if lit else '#182423')
        for db in (0,-12,-24,-36,-48,-60):
            y=52+(-db)/60*160
            text(d,(25,y),str(db),8,fill=MUTED,anchor='rm')
        for db in (0,3,6,9,12):
            text(d,(132,52+db/12*160),str(db),8,fill=MUTED,anchor='rm')
        text(d,(66,233),'SAMPLE PEAK',8,fill=MUTED,anchor='mm')
        text(d,(150,233),'COMP',8,fill=MUTED,anchor='mm')
        return im

    def footer(self,state):
        _,_,w,h=self.footer_rect
        im=Image.new('RGB',(w,h),'#15191a')
        d=ImageDraw.Draw(im)
        def stamp(seconds): return f'{int(seconds)//60:02}:{int(seconds)%60:02}'
        duration=state.get('duration',0)
        position=state.get('position',0)
        text(d,(130,14),f'{stamp(position)} / {stamp(duration)}',21,anchor='mm')
        d.rounded_rectangle((0,36,260,42),radius=3,fill='#05090a',outline='#353e40')
        if duration:
            d.rounded_rectangle((1,37,max(3,position/duration*259),41),radius=2,fill=TEAL)
        d.line((287,0,287,48),fill='#4c5355')
        text(d,(414,10),'SYSTEM AUDIO OUTPUT',10,fill=MUTED,anchor='mm')
        text(d,(414,33),state.get('format','NO AUDIO LOADED'),12,anchor='mm')
        d.line((547,0,547,48),fill='#4c5355')
        text(d,(628,10),'NR LOAD',10,fill=MUTED,anchor='mm')
        text(d,(628,34),f'{state.get("load",0):.0f}%',18,anchor='mm')
        d.line((712,0,712,48),fill='#4c5355')
        text(d,(810,10),'BUFFER MISSES',10,fill=MUTED,anchor='mm')
        text(d,(810,34),str(state.get('misses',0)),18,fill='#ed674f' if state.get('misses',0) else WHITE,anchor='mm')
        return im

    def screen_labels(self,state):
        im=Image.new('RGB',(560,21),BLACK)
        d=ImageDraw.Draw(im)
        text(d,(555,10),shorten(state.get('filename','NO FILE LOADED'),65),10,fill=MUTED,anchor='rm')
        return im

    def legend(self,state):
        im=Image.new('RGB',(997,12),BLACK)
        d=ImageDraw.Draw(im)
        view=state.get('view','wave')
        label={'wave':'SOURCE WAVEFORM · CLICK TO SEEK',
               'spectrum':'OUTPUT SPECTRUM · MONITOR SIGNAL',
               'reduction':'REDUCTION · RECENT PLAYBACK HISTORY'}[view]
        text(d,(0,6),label,8,fill=MUTED,anchor='lm')
        text(d,(995,6),'TEAL: NR RMS DECREASE   /   AMBER: COMPRESSION',8,fill=MUTED,anchor='rm')
        return im

    def status(self,state):
        im=Image.new('RGB',(1190,19),'#181d1f')
        d=ImageDraw.Draw(im)
        text(d,(4,9),shorten(state.get('status','Open a WAV or MP3 to begin.'),122),10,fill=MUTED,anchor='lm')
        return im

    def parts(self,state):
        yield 'plot',self.plot_rect[:2],self.plot(state)
        yield 'meters',self.meter_rect[:2],self.meters(state)
        yield 'footer',self.footer_rect[:2],self.footer(state)
        yield 'filename',(479,94),self.screen_labels(state)
        yield 'legend',(48,328),self.legend(state)
        yield 'status',(45,714),self.status(state)
        banner=Image.new('RGB',(565,22),'#15191a')
        text(ImageDraw.Draw(banner),(0,11),state.get('mastering_status',
            'MASTERING OFF — choose a preset or press A/B to enable'),10,
            fill=GOLD,anchor='lm')
        yield 'mastering_status',(663,404),banner

    def preview(self,state,values=None,buttons=None):
        im=self.base.copy().convert('RGBA')
        values=values or {k:v[7] for k,v in KNOBS.items()}
        buttons=buttons or {}
        for key,(_,_,_,_,_) in BUTTONS.items():
            config=buttons.get(key,{})
            im.alpha_composite(self.button(key,**config),BUTTONS[key][:2])
        for key,value in values.items():
            im.alpha_composite(self.knob(key,value),KNOBS[key][:2])
        for key,spec in SLIDERS.items():
            im.alpha_composite(self.slider(key,state.get(key,spec[7])),spec[:2])
        for _,xy,part in self.parts(state): im.alpha_composite(part.convert('RGBA'),xy)
        return im.convert('RGB')
