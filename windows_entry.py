"""Windows entry point and bundled-runtime smoke check."""
from pathlib import Path
import sys
import os
import traceback


def smoke_check():
    import tkinter as tk
    import numpy as np
    import scipy.signal
    import pywt
    import sounddevice as sd
    import soundfile as sf
    from tempfile import TemporaryDirectory
    from realtime import RealtimeRestoration
    from reference_engine import Controls
    from audio_input import read_audio

    mp3, mp3_rate = read_audio(Path(__file__).resolve().parent/'test_assets'/'decoder_check.mp3')
    assert mp3_rate == 44100 and mp3.shape == (11025, 2)
    assert np.isfinite(mp3).all() and np.max(np.abs(mp3)) > .01

    root = tk.Tk()
    root.withdraw()
    root.update()
    root.destroy()
    # Exercise compiled numerical extensions and bundled libsndfile/PortAudio.
    sr = 48000
    t = np.arange(12000, dtype=np.float64) / sr
    source = np.column_stack([0.1*np.sin(2*np.pi*440*t)]*2)
    engine = RealtimeRestoration(source, sr, drift=False)
    from dataclasses import replace
    for mode in ('Off', 'STFT', 'Wavelet', 'Both'):
        result = engine.get(0, len(source), replace(Controls(), mode=mode))
        assert result.shape == source.shape and np.isfinite(result).all(), mode
    with TemporaryDirectory() as folder:
        path = Path(folder) / 'check.wav'
        sf.write(path, result, sr, subtype='PCM_24')
        audio, rate = sf.read(path, always_2d=True)
        assert rate == sr and audio.shape == source.shape
    sd.get_portaudio_version()
    # Construct the real interface, exercise controls and resize it, then close.
    from app import App
    root = tk.Tk()
    app = App(root)
    root.update()
    assert root.title() == 'Restoration Lab Version 3.0'
    from manual import open_manual
    guide = open_manual(root)
    root.update()
    assert guide.winfo_exists() and 'User Guide' in guide.title()
    assert open_manual(root) is guide
    guide.destroy()
    app.restoration = engine
    app.path = 'Self-test.wav'
    app.draw_wave()
    app.vars['spectral_amount'].set(65)
    app.vars['wavelet_amount'].set(80)
    app.mode.set('Both')
    app.master_on.set(True)
    root.update()
    app.master_on.set(False)
    app.select_preset('Bright')
    root.update()
    assert app.controls.master and app.controls.preset == 'Bright'
    app.mastering_settings()
    root.update()
    assert app.mastering_window.winfo_exists()
    app.vars['target_lufs'].set(-16)
    app.vars['low_ratio'].set(3)
    assert app.controls.target_lufs == -16 and app.controls.low_ratio == 3
    app.vars['lowmid_attack'].set(35)
    app.vars['stereo_width'].set(1.25)
    app.eq_vars[2]['gain'].set(-2)
    app.advanced_flags['mono_audition'].set(True)
    assert app.controls.lowmid_attack == 35 and app.controls.stereo_width == 1.25
    assert app.controls.eq_bands[2].gain == -2 and app.controls.mono_audition
    app.advanced_flags['mono_audition'].set(False)
    app.mastering_window.destroy()
    app.select_preset('Natural')
    assert app.controls.mode == 'Both' and app.controls.master
    app.vars['nr_strength'].set(50)
    assert abs(app.controls.spectral_amount-.325) < 1e-12
    assert abs(app.controls.wavelet_amount-.4) < 1e-12
    app.vars['nr_strength'].set(100)
    app.bypass.set(True)
    assert app.controls.mode == 'Off' and not app.controls.master
    app.bypass.set(False)
    assert app.controls.mode == 'Both' and app.controls.master
    app.vars['grain'].set(80)
    app.vars['frequency'].set(5200)
    app.focus_band.set(True)
    assert app.controls.grain == .8 and app.controls.focus
    app.loop_a,app.loop_b=1000,8000
    app.toggle_loop()
    assert app.loop_range == (1000,8000)
    app.clear_loop()
    assert app.loop_range is None
    app.select_monitor(True)
    assert app.controls.preview_original
    app.select_monitor(False)
    app.focus_band.set(False)
    from realtime import export_audio
    with TemporaryDirectory() as folder:
        path=Path(folder)/'float.wav'
        export_audio(engine,path,Controls(mode='Off'),subtype='FLOAT')
        assert sf.info(path).subtype == 'FLOAT'
    from types import SimpleNamespace
    master_source=np.tile(source,(4,1))
    master_engine=SimpleNamespace(source=master_source,sr=sr,
        get=lambda a,b,c:master_source[a:b].copy())
    with TemporaryDirectory() as folder:
        path=Path(folder)/'master-check.wav'
        result=export_audio(master_engine,path,Controls(mode='Off',master=True,target_lufs=-18))
        assert abs(result['integrated_lufs']+18)<.2
        assert result['true_peak_dbtp'] <= -1 and result['ceiling_enforced']
    app.set_view('spectrum')
    app.set_view('reduction')
    app.set_view('wave')
    root.geometry('1000x600')
    root.update()
    app.layout()
    root.update()
    for callback in root.tk.call('after','info'):root.after_cancel(callback)
    app.close()
    print('PASS: Version 3.0 GUI/manual, controls, resize, four NR modes, Grain, Frequency Focus, loops, comparison, MP3, PCM24/float WAV, PortAudio.')


def main():
    if '--self-test' in sys.argv:
        smoke_check()
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    import tkinter as tk
    from app import App
    root = tk.Tk()
    def report_callback_exception(kind, value, tb):
        traceback.print_exception(kind, value, tb)
        from tkinter import messagebox
        messagebox.showerror('Restoration Lab',
            f'An interface error occurred. See {log_dir / "app.log"}')
    root.report_callback_exception = report_callback_exception
    App(root)
    root.mainloop()


if __name__ == '__main__':
    log_dir = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Restoration Lab' / 'Logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    # Finder has no Terminal attached. Keep stdout/stderr valid for diagnostics.
    if '--self-test' not in sys.argv or sys.stderr is None:
        from logging.handlers import RotatingFileHandler
        import logging
        logger = logging.getLogger('restoration')
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_dir / 'app.log', maxBytes=2_000_000,
                                      backupCount=2, encoding='utf-8')
        logger.addHandler(handler)
        class LogStream:
            def write(self, text):
                if text.strip(): logger.info(text.rstrip())
                return len(text)
            def flush(self):
                handler.flush()
        sys.stdout = sys.stderr = LogStream()
    try:
        main()
    except Exception:
        traceback.print_exc()
        if '--self-test' in sys.argv:
            raise
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror('Restoration Lab could not start',
                f'See the startup log:\n{log_dir / "app.log"}')
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
