# Restoration Lab 1.5

Adaptive WAV/MP3 restoration and real-time playback with STFT, wavelet or combined noise reduction, mastering presets, EQ, A/B comparison and export.

## Install on Mac

Download the package matching your Mac from **Releases**. `arm64` is for Apple Silicon (M1 and later); `x86_64` is for Intel. Only download architectures actually provided in the release.

Quit an older copy, open the `.pkg` installer and follow the prompts. It installs **Restoration Lab.app** in Applications. Alternatively, extract the app ZIP and drag the complete `.app` into Applications. Python is included; no separate dependency installation is needed.

This is an experimental, non-notarized release. The installer is unsigned, and macOS may block downloaded files. Review the source and release information before deciding whether to allow it in **System Settings → Privacy & Security**. Compatibility with other Macs/older macOS versions is not yet established.

## Use

Choose your output in macOS Sound settings, load a mono/stereo WAV or MP3 at 44.1 or 48 kHz, then press Play. Compare Off, STFT, Wavelet and Both. Enable mastering with A/B, adjust the controls and export a full-length PCM24 WAV. Click **USER GUIDE** for the complete manual.

File processing only; no live audio input or VST support. Meters are not certified LUFS/true-peak meters. Level Match and Listen to Removed affect monitoring only.

## Run or build from source

Use Python 3.13 from python.org (includes Tk), then double-click **Start.command**. To bundle the app, run **Build Mac App.command**. To create GitHub release assets afterward, run **Create GitHub Release.command**. See **DISTRIBUTING.md** for the release steps.

### MP3 input update

LOAD AUDIO accepts WAV or MP3 (mono/stereo, 44.1 or 48 kHz). MP3 is decoded to floating-point audio before restoration; output remains PCM24 WAV. WAV is the preferred source when available. Decoding does not recover detail lost to MP3 compression. No FFmpeg installation is needed.

To update your installed Mac app, extract this package and run **Build Mac App.command**, then install the newly built app. Start.command runs the updated source directly.
