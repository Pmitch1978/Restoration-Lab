"""Render the same GUI artwork without requiring a desktop display."""
import argparse
from pathlib import Path
import numpy as np
from metal_ui import Renderer, KNOBS


def demo_state():
    n=1600
    rng=np.random.default_rng(21)
    x=np.linspace(0,1,n)
    envelope=(.22+.42*np.sin(x*11)**2)*(.65+.35*np.sin(x*179)**2)
    envelope *= np.where((x>.52)&(x<.55),.14,1)
    high=envelope*rng.uniform(.35,1,n)
    low=-envelope*rng.uniform(.35,1,n)
    peaks=np.stack([np.column_stack([low,high]),np.column_stack([low*.86,high*.94])])
    t=np.arange(2048)/48000
    audio=np.column_stack([.22*np.sin(2*np.pi*437*t),.18*np.sin(2*np.pi*660*t)])
    return dict(peaks=peaks,monitor=audio,playing=True,sr=48000,duration=222,
                position=56,loop_a=48,loop_b=66,loop_enabled=True,focus=True,frequency=6300,width=1.5,history=[(1.1+.4*np.sin(i*.11),.7+.5*np.sin(i*.09)**2) for i in range(240)],
                load=30,misses=0,meter_peaks=[-9,-11],gr=1.4,filename='PREVIEW SESSION.wav',
                format='48 kHz · STEREO',status='Design preview · example waveform and meter readings',view='wave',
                loudness_status='SESSION I -14.2   M -13.8   S -14.0 LUFS',
                mastering_status='Natural · MULTIBAND · 45% · EQ +0.5 / +0.0 / +1.0 dB · EXPORT -14.0 LUFS')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    parser.add_argument('--view',choices=['wave','spectrum','reduction'],default='wave')
    args=parser.parse_args()
    renderer=Renderer()
    state=demo_state()
    state['view']=args.view
    values={key:spec[7] for key,spec in KNOBS.items()}
    values.update(spectral_amount=65,wavelet_amount=80,strength=45,bass=.5,treble=1,output_db=-1)
    buttons={'both':dict(active=True),args.view:dict(active=True),
             'drift':dict(active=True),'match':dict(active=True),
             'loop':dict(active=True),'focus':dict(active=True),'processed':dict(active=True),'ab':dict(active=True,label='MASTERING ON'),'play':dict(active=True)}
    renderer.preview(state,values,buttons).save(args.output)
    print(args.output)
