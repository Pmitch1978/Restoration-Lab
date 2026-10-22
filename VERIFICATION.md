# Metal GUI verification

Mastering preset update: reproduced identical preset output when master=False and distinct output when enabled. Added tests verify eight distinct full-strength curves, >4 dB Bright/Smooth high-band separation on a low-level multitone, zero-strength convergence, exact unmastered bypass, automatic mastering enable on preset selection, and preservation of global bypass/removed monitor states. Existing Natural/Warm/Punchy coefficients are preserved. MP3, GUI and audio regression checks included. Actual Mac interaction/listening still requires the Mac; bundled smoke check now exercises preset selection from mastering-off state.

Version 1.5 update: four GUI regression checks pass after adding version labels and the User Guide button. The generated ICNS has been decoded at each embedded resolution, and the manual HTML and Python/spec syntax checked. The Mac bundled smoke check now opens/reuses/closes the actual guide window and verifies the versioned title. No DSP changes were made for this update.

GitHub distribution update: release-packager Bash syntax and installer component plist checked on Linux. The `.pkg` build, installed app behavior and download/Gatekeeper experience have not been tested here; these require the Mac. The packager checks bundle identity/version/architecture/signature, runs the existing bundled smoke test, and inspects the generated installer payload without installing it. It produces local assets only and does not publish a release.

Verified in this Linux environment:

- Seven existing audio/transport/export tests passed with the new App callback.
- Four GUI checks passed: control mapping, bypass/restore, master NR strength scaling, knob clamping/keyboard behavior, and artwork across all three views plus the empty state.
- Audio engine files `realtime.py` and `reference_engine.py` are byte-for-byte identical to the preceding Mac packaging version.
- Python source/spec syntax and both shell launchers checked.
- The included preview is rendered from the same renderer used by the Tk GUI, not a separately generated design.

The graphical desktop is unavailable here. Tk window creation and physical audio playback have not been tested in this environment. The Mac build script constructs the real GUI, tests amount/bypass controls, loaded waveform and all display views, resizes, checks the processing and WAV libraries, and repeats those checks inside the packaged executable. It stops on failure. User playback testing remains necessary to confirm Mac UI interaction and interface behavior under load.

Previous successful real-time playback on the user's M1 applies to the preceding interface. This update adds Pillow drawing and an output snapshot, so its live performance must be checked on that machine. Graphics refresh at approximately 10 Hz; DSP transforms remain on the existing NR worker and GUI analysis stays off the audio callback.

## MP3 input update checks

Passed 7 input/interface tests on the development host: generated VBR MP3 decode to float64; all four NR modes through PCM24 WAV export with rate, channel count and decoded sample count preserved; WAV regression for mono/stereo at 44.1/48 kHz; invalid input and missing decoder handling; existing headless GUI checks. Python compilation passed. The Mac-specific app build, playback device and installer have not been run here. Mac build self-test now requires a bundled MP3 decode check before and after packaging.
