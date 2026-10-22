#!/usr/bin/env python3
"""Suno restoration proof of concept — run: python app.py"""
from dataclasses import replace
from pathlib import Path
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from reference_engine import Controls, Mastering, PRESETS
from realtime import RealtimeRestoration, RealtimeTransport, export_audio
from audio_input import read_audio


class App:
    def __init__(self, root):
        self.root = root
        root.title('Restoration Lab — real-time file processor')
        root.geometry('1040x870')
        root.minsize(850, 720)
        self.events = queue.Queue()
        self.restoration = None
        self.stream = None
        self.transport = None
        self.play_requested = False
        self.position = 0
        self.playing = False
        self.busy = False
        self.controls = Controls()
        self.weights = None
        self.audio_error = None
        self.last_meters = {}
        self.wave_redraw = None
        self.path = None
        self.status = tk.StringVar(value='Open a stereo or mono WAV or MP3 to begin.')
        self.mode = tk.StringVar(value='Wavelet')
        self.preset = tk.StringVar(value='Natural')
        self.master_on = tk.BooleanVar(value=False)
        self.match = tk.BooleanVar(value=True)
        self.removed = tk.BooleanVar(value=False)
        self.drift = tk.BooleanVar(value=True)
        self.vars = {}
        self.build()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(50, self.poll)

    def build(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='RESTORATION LAB', font=('Helvetica', 22, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='NR processed during playback • live mastering • experimental build').pack(anchor='w')
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=12)
        self.open_button = ttk.Button(top, text='Open audio', command=self.open_file)
        self.open_button.pack(side='left')
        self.play_button = ttk.Button(top, text='Play / Pause', command=self.toggle)
        self.play_button.pack(side='left', padx=8)
        ttk.Button(top, text='Stop', command=self.stop).pack(side='left')
        self.export_button = ttk.Button(top, text='Export WAV…', command=self.export)
        self.export_button.pack(side='right')
        self.canvas = tk.Canvas(outer, height=150, background='#17202b', highlightthickness=0)
        self.canvas.pack(fill='x')
        self.canvas.bind('<Button-1>', self.seek)
        self.canvas.bind('<Configure>', lambda event: self.draw_wave())
        self.time_label = ttk.Label(outer, text='0:00 / 0:00 — click waveform to seek')
        self.time_label.pack(anchor='w', pady=(4, 10))
        nr = ttk.LabelFrame(outer, text='Noise reduction', padding=12)
        nr.pack(fill='x')
        row = ttk.Frame(nr)
        row.pack(fill='x')
        for name in ['Off', 'STFT', 'Wavelet', 'Both']:
            ttk.Radiobutton(row, text=name, variable=self.mode, value=name,
                            command=self.update_controls).pack(side='left', padx=(0, 22))
        self.slider(nr, 'STFT amount', 'spectral_amount', 0, 100, 100)
        self.slider(nr, 'Wavelet amount', 'wavelet_amount', 0, 100, 100)
        ttk.Checkbutton(nr, text='Listen to removed audio (monitor only)', variable=self.removed,
                        command=self.update_controls).pack(anchor='w')
        self.drift_check = ttk.Checkbutton(nr,
            text='Correct upward level trend in wavelet modes — set before opening audio',
            variable=self.drift)
        self.drift_check.pack(anchor='w')
        ttk.Label(nr, text='Amounts change attenuation directly. Both: drift → STFT → wavelet.').pack(anchor='w')
        mast = ttk.LabelFrame(outer, text='Mastering', padding=12)
        mast.pack(fill='x', pady=10)
        row = ttk.Frame(mast)
        row.pack(fill='x')
        ttk.Checkbutton(row, text='B: Mastered  /  unchecked = A: Unmastered',
                        variable=self.master_on, command=self.update_controls).pack(side='left')
        ttk.Checkbutton(row, text='Loudness match (monitor only)', variable=self.match,
                        command=self.update_controls).pack(side='right')
        row = ttk.Frame(mast)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text='Preset').pack(side='left', padx=(0, 10))
        combo = ttk.Combobox(row, values=list(PRESETS), textvariable=self.preset,
                             state='readonly', width=15)
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>', lambda event: self.update_controls())
        for title, key, lo, hi, value in [('Bass', 'bass', -6, 6, 0),
            ('Mid', 'mid', -6, 6, 0), ('Treble', 'treble', -6, 6, 0),
            ('Mastering strength', 'strength', 0, 100, 50),
            ('Output gain (dB)', 'output_db', -18, 12, 0)]:
            self.slider(mast, title, key, lo, hi, value)
        self.meter_label = ttk.Label(outer, text='Output —   Compressor —   Limiter —')
        self.meter_label.pack(anchor='w')
        self.reduction_canvas = tk.Canvas(outer,height=70,background='#17202b',highlightthickness=0)
        self.reduction_canvas.pack(fill='x',pady=5)
        self.history = []
        ttk.Label(outer,text='Reduction history, 0–12 dB: teal = NR RMS level decrease; gold = compression.').pack(anchor='w')
        ttk.Label(outer, text='Limiter: −1 dBFS sample peak. True peak / LUFS are not verified in this build.').pack(anchor='w')
        ttk.Label(outer, textvariable=self.status, wraplength=980).pack(anchor='w', pady=8)
        self.update_controls()

    def slider(self, parent, title, key, low, high, initial):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=2)
        ttk.Label(row, text=title, width=23).pack(side='left')
        value = tk.DoubleVar(value=initial)
        self.vars[key] = value
        label = ttk.Label(row, width=7)
        label.pack(side='right')
        def changed(*unused):
            label.config(text=f'{value.get():.1f}')
            self.update_controls()
        ttk.Scale(row, from_=low, to=high, variable=value,
                  command=changed).pack(side='left', fill='x', expand=True, padx=8)
        label.config(text=f'{initial:.1f}')

    def update_controls(self):
        values = {key: var.get() for key, var in self.vars.items()}
        for key in ['spectral_amount', 'wavelet_amount', 'strength']:
            if key in values:
                values[key] /= 100
        self.controls = Controls(mode=self.mode.get(), preset=self.preset.get(),
            master=self.master_on.get(), match=self.match.get(),
            removed=self.removed.get(), **values)
        if self.restoration is not None:
            if self.wave_redraw is not None:
                self.root.after_cancel(self.wave_redraw)
            self.wave_redraw = self.root.after(200, self.redraw_selected)

    def redraw_selected(self):
        self.wave_redraw = None
        self.draw_wave()

    def set_busy(self, busy):
        self.busy = busy
        for widget in [self.open_button, self.export_button, self.play_button]:
            widget.config(state='disabled' if busy else 'normal')

    def open_file(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(filetypes=[('WAV or MP3 audio', ('*.wav', '*.mp3', '*.WAV', '*.MP3')), ('WAV audio', '*.wav'), ('MP3 audio', '*.mp3')])
        if not filename:
            return
        self.stop()
        self.shutdown_stream()
        self.restoration = None
        self.draw_wave()
        self.set_busy(True)
        self.drift_check.config(state='disabled')
        use_drift = self.drift.get()
        def work():
            try:
                x, sr = read_audio(filename)
                engine = RealtimeRestoration(x, sr, use_drift,
                    lambda message: self.events.put(('status', message)))
                self.events.put(('loaded', (filename, engine)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def callback(self, outdata, frames, timing, status):
        # No Tk calls or NR transforms in the audio callback.
        outdata.fill(0)
        if status:
            self.audio_error = str(status)
        if not self.playing or self.restoration is None or self.transport is None:
            return
        try:
            engine, c = self.restoration, self.controls
            start = self.transport.position
            raw, n = self.transport.read(frames)
            if self.transport.error:
                raise RuntimeError(self.transport.error)
            if n == 0:
                if self.transport.eof: self.playing = False
                return
            raw = raw[:n]
            mastered = self.mastering.process(raw, c)
            output = engine.source[start:start+n]-raw if c.removed else mastered
            # Device safety clamp only; exports use the selected chain instead.
            outdata[:n] = np.clip(output, -.999, .999)
            self.last_meters = dict(self.mastering.meters)
            self.position = self.transport.position
            if self.transport.eof:
                self.playing = False
        except Exception as exc:
            self.audio_error = str(exc)
            self.playing = False

    def toggle(self):
        if self.restoration is None or self.busy:
            return
        if self.playing or self.play_requested:
            self.playing = False
            self.shutdown_stream()
            return
        if self.position >= len(self.restoration.source):
            self.position = 0
        self.shutdown_stream()
        self.mastering = Mastering(self.restoration.sr, self.restoration.source.shape[1])
        self.transport = RealtimeTransport(self.restoration,lambda:self.controls,self.position)
        self.transport.start()
        self.play_requested = True
        self.status.set('Preparing first playback block…')

    def start_ready_stream(self):
        if not self.play_requested or self.transport is None:
            return
        if self.transport.error:
            error=self.transport.error
            self.shutdown_stream()
            messagebox.showerror('Real-time processing',error)
            return
        if self.transport.ready.empty():
            return
        try:
            import sounddevice as sd
            self.stream = sd.OutputStream(samplerate=self.restoration.sr,
                channels=self.restoration.source.shape[1],blocksize=2048,
                dtype='float32',latency='high',callback=self.callback)
            self.play_requested = False
            self.playing = True
            self.stream.start()
            self.status.set('Playing — NR changes apply at upcoming processing blocks.')
        except Exception as exc:
            self.playing = False
            self.shutdown_stream()
            messagebox.showerror('Audio device',str(exc))

    def stop(self):
        self.playing = False
        self.shutdown_stream()
        self.position = 0
        self.weights = None

    def seek(self, event):
        if self.restoration is None or self.busy:
            return
        resume = self.playing or self.play_requested
        self.playing = False
        self.shutdown_stream()
        self.position = int(np.clip(event.x/max(1, self.canvas.winfo_width()), 0, 1)
                            * (len(self.restoration.source)-1))
        self.weights = None
        if resume:
            self.toggle()

    def shutdown_stream(self):
        self.play_requested = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    def draw_wave(self):
        self.canvas.delete('wave')
        engine = self.restoration
        if engine is None:
            return
        width, height = max(1, self.canvas.winfo_width()), 150
        peaks = engine.waveform_peaks
        for pixel in range(width):
            gray = min(1.,peaks[min(len(peaks)-1,pixel*len(peaks)//width)])
            self.canvas.create_line(pixel, height/2-gray*65, pixel,
                height/2+gray*65, fill='#68717c', tags='wave')

    def export(self):
        if self.busy or self.restoration is None:
            return
        suffix = 'Mastered' if self.controls.master else 'Restored'
        filename = filedialog.asksaveasfilename(defaultextension='.wav',
            initialfile=f'{Path(self.path).stem} - {suffix}.wav',
            filetypes=[('WAV audio', '*.wav')])
        if not filename:
            return
        if Path(filename).resolve() == Path(self.path).resolve():
            messagebox.showerror('Export', 'Choose a new filename to preserve the source.')
            return
        self.playing = False
        self.shutdown_stream()
        self.set_busy(True)
        engine, controls = self.restoration, self.controls
        def work():
            temporary = Path(filename).with_name(Path(filename).name+'.partial.wav')
            try:
                report = export_audio(engine, temporary, controls)
                temporary.replace(filename)
                sidecar = Path(filename).with_suffix('.report.json')
                sidecar.write_text(json.dumps({'restoration': engine.report,
                    'controls': controls.__dict__, 'export': report}, indent=2))
                self.events.put(('exported', filename))
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == 'status': self.status.set(payload)
                elif kind == 'loaded':
                    self.path, self.restoration = payload
                    self.position = 0
                    self.set_busy(False)
                    self.drift_check.config(state='normal')
                    self.status.set(f'{Path(self.path).name} — ready. '
                        f'Analysis: {self.restoration.report["analysis_seconds"]:.1f} s. '
                        'No processed song caches.')
                    self.draw_wave()
                elif kind == 'exported':
                    self.set_busy(False)
                    self.status.set(f'Saved {payload} and processing report.')
                elif kind == 'error':
                    self.set_busy(False)
                    self.drift_check.config(state='normal')
                    self.status.set(payload)
                    messagebox.showerror('Processing', payload)
        except queue.Empty:
            pass
        self.start_ready_stream()
        if self.restoration is not None:
            duration = len(self.restoration.source)/self.restoration.sr
            current = self.position/self.restoration.sr
            self.time_label.config(text=f'{int(current)//60}:{int(current)%60:02} / '
                f'{int(duration)//60}:{int(duration)%60:02} — source waveform; reduction shown below')
            self.canvas.delete('playhead')
            pos = self.position/len(self.restoration.source)*self.canvas.winfo_width()
            self.canvas.create_line(pos, 0, pos, 150, fill='#ffc857', width=2, tags='playhead')
            m = self.last_meters
            if m:
                transport=self.transport
                load=transport.last_load*100 if transport else 0.
                underflows=transport.underflows if transport else 0
                self.meter_label.config(text=f'Output {m["peak_dbfs"]:.1f} dBFS    '
                    f'Compressor {m["compression_db"]:.1f} dB    Limiter {m["limiting_db"]:.1f} dB    '
                    f'NR load {load:.0f}%   Buffer misses {underflows}')
                if self.playing and transport:
                    self.history.append((transport.last_reduction_db,m['compression_db']))
                    self.history=self.history[-240:]
                    self.draw_reductions()
        if self.audio_error:
            self.status.set(f'Audio: {self.audio_error}')
            self.audio_error = None
        self.root.after(50, self.poll)

    def draw_reductions(self):
        canvas=self.reduction_canvas
        canvas.delete('all')
        width=max(1,canvas.winfo_width())
        for value in [0,6,12]:
            y=5+value/12*55
            canvas.create_line(28,y,width,y,fill='#364252')
            canvas.create_text(13,y,text=str(value),fill='#aeb8c6')
        for band,color in [(0,'#46c6bc'),(1,'#ffc857')]:
            points=[]
            for i,pair in enumerate(self.history):
                points.extend([30+i/239*(width-32),5+min(12,pair[band])/12*55])
            if len(points)>=4: canvas.create_line(*points,fill=color,width=2)

    def close(self):
        self.stop()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
