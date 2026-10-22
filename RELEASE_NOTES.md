# Restoration Lab v1.5.0

Mastering usability update: selecting a preset enables mastering, A/B states explicitly say Mastering On/Off, and an effective EQ/ratio status row makes the active processing visible. Added Bright, Vocal, Acoustic, Deep Bass and Smooth (eight presets total). Existing Natural/Warm/Punchy settings and NR algorithms are preserved. Manual updated; MP3 support retained.

Initial packaged preview release: black metal interface, waveform app icon, adaptive STFT/Wavelet/Both processing, mastering/EQ, A/B and bypass, PCM24 export, searchable in-app user guide.

Download the installer or app ZIP for the architecture shown in the filename. Quit any older copy before installing. The PKG installs to Applications; the ZIP is the drag-and-drop alternative. No Python installation is required for either binary download.

Experimental build: installer unsigned, app locally signed but not Apple-notarized. Other Macs and older macOS versions require testing. File processing only. No true-peak/LUFS certification. Monitoring-only matching and removed-signal listening are excluded from exports.

Verify downloads with `shasum -a 256 -c SHA256SUMS.txt` after downloading all files listed in the checksum file. If you downloaded just the app/installer, compare its individual `shasum -a 256` result with the corresponding checksum entry.

## MP3 input update

LOAD AUDIO now accepts WAV and MP3. MP3 decodes to float64 with the existing audio library, preserving the decoded sample rate and channels. Existing 44.1/48 kHz, mono/stereo restrictions apply. Export remains PCM24 WAV. The builder checks MP3 decoding both before packaging and inside the built app. Rebuild to update an installed app.
