"""Decode supported inputs to float64 without resampling or changing channels."""
from pathlib import Path
import numpy as np
import soundfile as sf


def read_audio(path):
    suffix = Path(path).suffix.lower()
    if suffix not in ('.wav', '.mp3'):
        raise ValueError('Choose a WAV or MP3 file.')
    if suffix == '.mp3' and 'MP3' not in sf.available_formats():
        raise ValueError('This audio runtime lacks MP3 decoding. Rebuild the app with the supplied requirements.txt.')
    with sf.SoundFile(path) as source:
        if source.format not in ('WAV', 'WAVEX', 'RF64', 'MP3', 'MPEG'):
            raise ValueError('The selected file does not contain WAV or MP3 audio.')
        if source.samplerate not in (44100, 48000) or source.channels not in (1, 2):
            raise ValueError('Supported input: mono/stereo WAV or MP3 at 44.1 or 48 kHz. Convert other rates or channel layouts first.')
        sr = source.samplerate
        audio = source.read(dtype='float64', always_2d=True)
    if len(audio) < 2048 or not np.isfinite(audio).all():
        raise ValueError('Audio must contain at least 2048 finite samples.')
    return audio, sr
