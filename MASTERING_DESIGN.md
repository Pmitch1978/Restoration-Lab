# Version 3 mastering design

Restored audio → six-band parametric EQ → four compensated LR4 crossover bands with linked dynamics → mid/side stereo width → output gain → monitor sample ceiling or export LUFS/oversampled peak finalization.

Four bands are built as a sequential LR4 split tree. Lower branches receive all-pass compensation for every later split; their unity magnitude sum is flat. Channel-linked detection uses max L/R power with a 5 ms power pole. Threshold/ratio/soft knee computes desired dB reduction; stateful attack/release poles smooth it per sample. Strength interpolates ratios toward 1:1; preset ratios are retained in legacy preset metadata but do not multiply user ratios. Dynamics bypass retains split phase and tone gains. Bypass mix and makeup transitions use 5 ms poles.

Six EQ filters use RBJ biquad equations; all channels share coefficients but retain separate states. The graph shows the six-band response only. Main tone controls add crossover band gains. Changes crossfade over a block. Frequencies are clamped at 45% of sample rate. Shelves use Q for damping, and filter boost/cut is bounded to ±18 dB.

Stereo width preserves M=(L+R)/2 and scales S=(L−R)/2. Bass protection preserves the low-pass side signal and scales the remainder. Width smoothing has a 10 ms time constant independent of block partition. No decorrelation, delay widening or stereo synthesis is used. Correlation is normalized L/R inner product before mono audition. Mono input bypasses width. Export clears mono audition and every solo flag, plus other monitor comparisons.

Loudness uses pyloudnorm DeMan / BS.1770 integrated measurement. The existing 4× polyphase lookahead limiter and encoded-WAV verification follow the new processing stages. No hardware/standards certification is claimed. The limiting budget bounds drive, and achieved LUFS is reported when a target is not reachable. No dither is added.

Upward drift correction remains a separate optional restoration operation. There is no new phrase-by-phrase automatic gain rider. Native builds and physical listening checks are required before public distribution.
