"""Audio input integration checks; fixture is a generated 440 Hz test tone."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
import numpy as np
import soundfile as sf
from audio_input import read_audio
from realtime import RealtimeRestoration, export_audio
from reference_engine import Controls


class InputTests(TestCase):
    def test_mp3_restore_and_wav_export(self):
        audio, sr = read_audio(Path(__file__).parent/'test_assets'/'decoder_check.mp3')
        self.assertEqual((sr, audio.shape, audio.dtype), (44100, (11025, 2), np.dtype('float64')))
        engine = RealtimeRestoration(audio, sr, drift=False)
        from dataclasses import replace
        for mode in ('Off', 'STFT', 'Wavelet', 'Both'):
            controls = replace(Controls(), mode=mode)
            with TemporaryDirectory() as tmp:
                output = Path(tmp)/'restored.wav'
                export_audio(engine, output, controls)
                result, rate = sf.read(output, always_2d=True)
                self.assertEqual((rate, result.shape), (sr, audio.shape))
                self.assertEqual(sf.info(output).subtype, 'PCM_24')
                self.assertTrue(np.isfinite(result).all())

    def test_wav_exact_and_input_validation(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'input.WAV'
            for sr in (44100, 48000):
                for channels in (1, 2):
                    source = np.zeros((4096, channels), dtype='float64')
                    sf.write(path, source, sr, subtype='DOUBLE')
                    audio, rate = read_audio(path)
                    self.assertEqual(rate, sr)
                    np.testing.assert_array_equal(audio, source)
            for rate, frames, channels in ((22050,4096,1),(44100,20,1),(44100,4096,3)):
                sf.write(path, np.zeros((frames,channels)), rate)
                with self.assertRaises(ValueError): read_audio(path)
            path.write_bytes(b'broken')
            with self.assertRaises(sf.LibsndfileError): read_audio(path)
            with self.assertRaises(ValueError): read_audio(Path(tmp)/'other.flac')

    def test_missing_mp3_decoder_has_actionable_error(self):
        with patch('audio_input.sf.available_formats', return_value={'WAV':'WAV'}):
            with self.assertRaisesRegex(ValueError, 'lacks MP3 decoding'):
                read_audio('song.mp3')


if __name__ == '__main__': main()
