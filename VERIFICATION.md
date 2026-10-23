# Restoration Lab 3.0 — verification

The included verification-tests.log records the 47-test source suite, including new Version 3 DSP checks and inherited restoration tests. verification-gui.log records construction and exercise of the real Tk application and Mastering Studio under Linux with a virtual display. Native app entry smoke checks were exercised as source; no macOS or Windows binary was built here.

Verified behavior includes:

- Four-band unity recombination, low-band selectivity, linked stereo compression and streaming consistency.
- Compressor attack/release response and soft-knee curve.
- Parametric bell gain, high/low-pass response and EQ bypass.
- Original-width identity, preserved center signal, bass protection and mono audition.
- Stereo export, sample rate/sample count retention, exclusion of mono/solo monitoring, LUFS targeting and estimated true-peak ceiling on encoded WAV bytes.
- Actual three-tab metal Studio, EQ/width mapping, canvas click routing, EQ node dragging, user preset save/load, scaled resize, close and reopen.
- Existing STFT/wavelet restoration, focus, Grain, loops, bypass, input decoding and export tests.
- Python compilation and Mac shell-script syntax.

performance.json records a synthetic Linux DSP benchmark of eight seconds through the new mastering chain in approximately 0.8 seconds. This is not a benchmark of the user's M1, total app load, or physical audio-device stability.

The included Studio PNGs are captures of the real controls on Linux; the Studio reuses the same materials and knob drawing code as the main app. Native title bars and value-entry dialogs can differ by OS. Restoration_Lab_3.0_Preview.png is a rendered main-window preview with example data.

Remaining release checks: build on macOS and Windows using the supplied scripts, run the packaged self-tests, listen on real output devices, and compare representative music for pumping, transients and mono compatibility. The meter/limiter is not independently certified; no standards certification is claimed. No dither, phrase-by-phrase gain rider, stereo synthesis or linear-phase crossover is included.
