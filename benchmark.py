"""Run: python benchmark.py [song.wav]. No audio device or GUI required."""
import json
import sys
import time
import numpy as np
import soundfile as sf
from reference_engine import Controls
from realtime import RealtimeRestoration,RealtimeTransport


def benchmark():
    if len(sys.argv)>1:
        x,sr=sf.read(sys.argv[1],dtype='float64',always_2d=True)
    else:
        sr=48000
        t=np.arange(sr*12)/sr
        tone=.12*np.sin(2*np.pi*440*t)
        x=np.column_stack([tone,tone*.8])+np.random.default_rng(72).normal(0,.004,(len(t),2))
    engine=RealtimeRestoration(x,sr,drift=False)
    budget=16384/sr
    report={'sample_rate':sr,'block_frames':16384,'block_budget_ms':1000*budget,
            'analysis_seconds':engine.report['analysis_seconds'],'modes':{}}
    for mode in ['Off','STFT','Wavelet','Both']:
        c=Controls(mode=mode)
        samples=[]
        for start in range(0,min(len(x),16384*8),16384):
            stop=min(start+16384,len(x))
            before=time.perf_counter()
            engine.get(start,stop,c)
            samples.append(time.perf_counter()-before)
        report['modes'][mode]={'median_ms':1000*float(np.median(samples)),
            'max_ms':1000*max(samples),'max_load_fraction':max(samples)/budget}
    # Simulate a speaker consuming 2048 samples at wall-clock sample rate.
    settings=[Controls(mode='Wavelet')]
    transport=RealtimeTransport(engine,lambda:settings[0])
    transport.start()
    first=time.perf_counter()
    while transport.ready.empty() and not transport.finished.is_set(): time.sleep(.001)
    deadline=time.perf_counter()
    read=0
    try:
        while read<min(len(x),sr*5):
            if read>sr: settings[0]=Controls(mode='Both',wavelet_amount=.6)
            if read>sr*3: settings[0]=Controls(mode='STFT',spectral_amount=.4)
            delay=deadline-time.perf_counter()
            if delay>0:time.sleep(delay)
            _,n=transport.read(2048)
            read+=n
            deadline+=2048/sr
            if transport.error: raise RuntimeError(transport.error)
        report['paced_playback']={'seconds':read/sr,'buffer_misses':transport.underflows,
            'max_worker_ms':1000*transport.max_processing_seconds,'mode_changes':2,
            'physical_audio_device':False}
    finally: transport.close()
    print(json.dumps(report,indent=2))


if __name__=='__main__':benchmark()
