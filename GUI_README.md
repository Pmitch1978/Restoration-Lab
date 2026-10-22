# Restoration Lab Version 1.5

Mastering update: eight presets (Natural, Warm, Punchy, Bright, Vocal, Acoustic, Deep Bass, Smooth). Choosing a preset enables B: Mastering On. The mastering panel shows effective EQ/ratio or an inactive/bypass explanation. Bypass All and Removed monitoring are preserved and explicitly reported if active. At Strength 0% the preset EQ/compression changes are zero; Level Match can conceal loudness differences.

Click **USER GUIDE** on the top bar for the full searchable manual inside the app. A portable, printable copy is included at **assets/User_Guide.html**. Version 1.5 embeds a waveform Dock/Finder icon and labels the GUI and title bar with the version. Rebuild, quit the previous installed copy, and replace it in Applications to apply the new icon.

The approved black metal concept is now implemented with aluminum knobs and buttons, white labels, a smoked-glass display, teal restoration traces, amber compressor reduction, and vertical meters. Artwork is drawn by the app; it requires no downloaded skin assets.

## Run on your Mac

Extract this ZIP to a fresh folder. Double-click **Start.command** to try the new interface in Python. It installs Pillow plus the existing audio dependencies. Keep your previous working app as a backup.

To package this version, double-click **Build Mac App.command**. Wait for **SUCCESS**; Finder selects **Restoration Lab.app**. Drag it into **Applications**. The finished app includes Python and dependencies and opens without Terminal. This archive contains source and the builder, not a precompiled Mac executable.

If macOS blocks a downloaded command, attempt opening it once and then use **System Settings → Privacy & Security → Open Anyway**. If a command is not executable, open Terminal in the extracted folder and run `bash Start.command` or `bash "Build Mac App.command"`.

## Controls

- **Knobs:** drag up/down, wheel, or arrow keys. Shift gives fine adjustment. Double-click restores the initial value. Tab changes focus; Enter/Space activates a focused button. Space with no button selected toggles playback.
- **Off / STFT / Wavelet / Both:** the established NR modes. Amount knobs change actual attenuation.
- **NR Strength slider:** scales both method amounts together, preserving the knob settings. At 100%, amounts are exactly as set by the knobs; at 0%, NR is bypassed.
- **Drift Correction:** set before loading a WAV or MP3. The full-song profile is analyzed on load.
- **Profile / Details:** inspect the measured adaptive profile and analysis report.
- **Listen to Removed:** original minus NR output. Monitor-only; never exported.
- **A/B:** A is restored/unmastered; B is restored/mastered. Export follows that selection.
- **Bypass All:** original source with NR and mastering bypassed; export follows bypass too. Press again to restore your control values.
- **Level Match:** approximate RMS matching for monitoring only, never export. It is not a LUFS meter.
- **Preset / Strength / Bass / Mid / Treble / Output:** the existing mastering controls.
- **Transport:** rewind-to-start, play/pause, pause, stop. Click the waveform or small progress bar to seek.

## Displays

- **Waveform:** signed source waveform for each channel. The lower strip shows recent reduction history, not a cached full-song cleaned signal.
- **Spectrum:** FFT of current monitored output during playback, including removed-signal monitoring when selected. Visual amplitude spectrum, not calibrated spectral density.
- **Reduction:** recent history, 0–12 dB. Teal is NR RMS level decrease, amber is compression while mastering is enabled. This does not measure isolated noise.
- **L/R:** sample peaks from recent monitored blocks. Mono appears on both meters. Not true peak or LUFS.
- **GR:** sampled compressor reduction while monitoring mastering.
- **NR Load:** NR worker time divided by block duration, not total CPU or mastering load.
- **Buffer Misses:** playback worker underruns. Counters reset at each playback start and remain visible when stopped.

Choose your interface as the default output in macOS Sound settings. This version processes files; live audio input, Learn/Freeze and recording are not introduced by this GUI update.

Noise reduction and mastering algorithms are unchanged. The GUI takes a small output snapshot per callback; FFTs and drawing run on the interface thread at about 10 updates/second. Resize to scale the complete faceplate. Initial size fits the available MacBook Air desktop.

## Verification

The Mac builder checks the complete GUI, changes controls, checks bypass/restore and resize, tests all four NR modes and WAV read/write, loads PortAudio, then repeats inside the bundle and verifies the local signature. It stops on failure. Results and a dependency snapshot go into unique folders under `mac-builds`.

Source checks run on Linux. A desktop display is unavailable here, so actual Tk interaction, macOS rendering, Finder launch and interface playback must be verified on your Mac. The preview PNG is rendered by the same artwork code using illustrative waveform and readings; it is not a Mac screenshot.

Python 3.10+ with Tk 8.6+ is required. Python.org 3.13 includes compatible Tk. The Mac build targets the selected Python architecture (native Apple Silicon on M1). Local ad-hoc signing is included; public notarization is not.

Startup/interface exception log: `~/Library/Logs/Restoration Lab/app.log`. Help → Controls & meters documents the controls. ⌘O opens a WAV or MP3; ⌘E exports.
