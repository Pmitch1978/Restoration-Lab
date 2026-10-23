# Version 3.0.0

Adds a Mastering Studio with six-band parametric EQ, four-band stereo-linked compression and adjustable mid/side stereo width. Each compressor band now exposes attack, release, soft knee and makeup gain alongside threshold/ratio, solo and dynamics bypass.

Adds bass-width protection, correlation monitoring, mono audition and user mastering preset save/load. Solo and mono audition are monitor-only and excluded from export. Width changes use a fixed 10 ms transition; compression/makeup bypass transitions use 5 ms smoothing.

Retains restoration, upward drift correction, Grain, frequency focus, loops, WAV/MP3 input, PCM24/float WAV export, LUFS targeting and estimated true-peak verification. Updates guide, version labels, native self-tests and build artifact names.

Compression ratios now follow the displayed band ratio scaled toward 1:1 by Strength. Tone preset selection no longer multiplies compression ratios. Default compression is consequently gentler than some Version 2 preset combinations. The compressor enable switch now bypasses dynamics while retaining the crossover/tone path. Older versions do not read Version 3 presets.

## Approved metal Studio interface

Replaces the earlier form-style settings window with a scaled canvas interface using the main app’s actual brushed-metal materials and machined knob artwork. Consolidates the Studio into EQ, Compressor and Stereo & Loudness tabs. Adds EQ node and crossover dragging, monitor spectrum and vectorscope, live channel/band meters and a shared preset/playback toolbar. Mastering audio behavior and export routing remain the Version 3 chain.
