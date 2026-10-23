# Restoration Lab 3.0

Local stereo restoration and mastering for WAV and MP3 recordings, including AI-generated music.

## New in Version 3

- Six-band parametric EQ: bell, shelves, high/low-pass filters; frequency, gain, Q, response graph and individual enable.
- Four-band linked compressor: adjustable crossovers, threshold, ratio, attack, release, soft knee and makeup; band dynamics bypass and monitor solo.
- Mid/side stereo width from 0–200%, existing bass-width protection, correlation readout and mono audition.
- Full-song LUFS targeting, adjustable peak ceiling and measured WAV export reports.
- Mastering Studio matching the main app’s metal finish, silver rotary controls and teal screens, with exactly three tabs: EQ, Compressor, Stereo & Loudness.
- Interactive EQ nodes and crossover markers, live band meters, stereo vectorscope and shared preset/transport controls.
- Save/load user mastering presets from every tab.
- Existing STFT/wavelet restoration, Grain, frequency focus, drift correction, looping and comparison.

Stereo input stays stereo. Source sample rate, full sample count and alignment are retained. Mono input stays mono. Output is 24-bit PCM or 32-bit float WAV. Monitoring choices, including band solo and mono audition, do not affect exports.

## Run and build

**Mac:** extract the folder and run `Start.command` to try the source application. Run `Build Mac App.command` to make a bundled app; then `Create GitHub Release.command` to make local release assets. These scripts preserve earlier build folders. Build on the intended Mac architecture.

**Windows:** upload this folder's contents to repository root, including `.github/workflows/windows-build.yml`, and run **Build Windows** under GitHub Actions. Download **Restoration-Lab-3.0-Windows-x64**; the ZIP inside is the Windows release asset. Alternatively run `Build-Windows.ps1` on Windows with Python 3.13 x64.

**Development:** Python 3.10–3.14 with Tk 8.6+, `python3 -m pip install -r requirements.txt`, then `python3 app.py`. Run `python3 -m unittest discover -v` for tests. Native build scripts also run the actual bundled GUI self-test.

## Mastering workflow

Load a track, adjust restoration and compare. Enable mastering, open **MASTERING STUDIO**, set EQ, compression and width, then choose output loudness. Use Level Match for comparisons and mono audition to check width. Export measures the complete processed WAV and reports achieved LUFS and estimated true peak. A target can be missed within the selected limiting budget.

Start with restrained processing. The tool attenuates estimated noise; it cannot guarantee restoration of missing content or remove every artifact. Crossovers are minimum-phase, EQ uses IIR filters, and peak metering uses a 4× estimate. There is no dither. Keep working earlier releases while evaluating 3.0.

This is a source and build kit. Native macOS/Windows installers must be built and listening-tested on their target platforms. See `VERIFICATION.md` and the in-app guide for details.

## Studio controls

Drag or wheel knobs; Shift gives finer steps. Double-click to type, right-click to reset. Drag EQ nodes to adjust frequency/gain and wheel over them for Q. Drag crossover markers to change band boundaries. Tab and arrow keys provide keyboard adjustment. TRUE PEAK is the last completed export for the current source; playback meters show sample peaks.
