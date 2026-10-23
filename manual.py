"""Versioned user guide shared by the in-app reader and portable HTML."""
from html import escape
import tkinter as tk
from tkinter import ttk

TITLE = 'Restoration Lab Version 3.0'
SECTIONS = [('Welcome',
  ['Restoration Lab 3.0 restores WAV and MP3 files locally using adaptive STFT, wavelet, or combined noise '
   'reduction, followed by optional mastering. It is a file processor, not a live input effect. The metal '
   'interface adds looping, grain, frequency targeting and export format selection.']),
 ('Quick start',
  ['Choose Drift Correction before loading. Open mono/stereo WAV or MP3 at 44.1 or 48 kHz. Wait for '
   'profiling, then play. Start with Wavelet, reduce amounts if useful musical texture changes, and compare '
   'with ORIGINAL / PROCESSED.',
   'Set A and B around a passage and enable LOOP. Adjust Grain, then try TARGET BAND and sweep Frequency. '
   'Width sets how broadly restoration acts around that frequency. Check several parts of the full song '
   'before exporting.']),
 ('Playback and loops',
  ['Click the waveform to seek. SET A and SET B place boundaries at the playhead; drag either marker on the '
   'waveform to refine it. LOOP repeats [A, B). CLEAR disables looping and resets markers to the full song. '
   'A loop must span at least 50 milliseconds or 2048 frames, whichever is longer.',
   'A five-millisecond fade down/up at each loop join prevents discontinuities. This is a preview fade, not '
   'a time-overlapping crossfade; the loop sample count remains unchanged. Markers are constrained to valid '
   'order. Changing points during playback restarts buffering.',
   'Loops are monitor only. Export always includes the complete original sample count, with no loop '
   'repetitions or loop-edge fades. Stop/Rewind returns to zero; Play starts at A if an active loop excludes '
   'that position.']),
 ('Cleanup and Grain',
  ['OFF passes the original source through restoration. STFT applies profile-based spectral attenuation; '
   'WAVELET uses stereo-linked sym8 stationary wavelets with nine levels; BOTH applies STFT then wavelets. '
   'Profiles are estimated from low-energy sections of the loaded song and may contain musical content.',
   'Spectral and Wavelet amounts scale each method. Reduction Strength multiplies both. At zero effective '
   'amounts, restoration and drift are bypassed exactly. At full amount the existing spectral floor is -7 dB '
   'per time-frequency bin and the wavelet floor is -2 dB per coefficient, not a promised total reduction.',
   'Grain controls how smoothly the attenuation changes, independently of amount. Low values retain faster '
   'changes in reduction; high values smooth them more. At 50%, smoothing matches version 1.5. STFT '
   'smoothing spans frequency and time; wavelet gain smoothing ranges approximately 1–9 ms. This does not '
   'synthesize missing detail. Compare by ear for transient softness or modulation.']),
 ('Frequency Focus',
  ['FULL RANGE keeps broad restoration. TARGET BAND targets the removed signal around Frequency, for STFT, '
   'Wavelet and Both alike. Frequency ranges 20 Hz–20 kHz on a logarithmic knob; Width ranges 0.1–6 octaves. '
   'Width is the full span between the half-height points of a raised-cosine window; its tails taper to '
   'zero.',
   'The selected restoration difference is filtered with an STFT window and subtracted from the dry source. '
   'This targets the whole restoration difference, including drift if enabled, while preserving the dry path '
   'outside the focus. Finite analysis windows introduce some spectral leakage. Mastering EQ remains '
   'full-range.',
   'The curve is a target weight, not an EQ boost or dB reduction measurement. The gray trace shows recent '
   'monitor spectrum. Move frequency/width while playing; changes crossfade at processing-block boundaries '
   'and may take several tenths of a second to reach the speakers.']),
 ('Drift correction',
  ['Enable Drift Correction before loading. It estimates a positive level trend in five-second windows, '
   'excluding the first and last fifteen seconds, and applies a gradual opposing ramp before wavelet '
   'processing. Short files or falling trends receive no correction.',
   'Drift applies in Wavelet/Both and scales with the wavelet amount. It may mistake an intentional build '
   'for unwanted drift; disable and reload to compare. Changing Drift Correction after loading stops '
   'playback and reanalyzes the original audio with the new setting. Loop markers reset after this '
   'analysis.']),
 ('Mastering Studio — Version 3', ['Open MASTERING STUDIO. The three metal tabs are EQ, COMPRESSOR, and STEREO & LOUDNESS. Enable MASTERING ON to hear the chain. Restoration, EQ, compression, stereo width, output gain and export finalization run in that order. All stages retain the source channel count; stereo tracks remain stereo.', 'The main eight tone presets remain available. Bass/Mid/Treble add gains to Low, both middle bands, and High respectively, plus preset tone offsets scaled by Strength. Strength scales compressor ratios: effective ratio = 1 + (displayed ratio - 1) × Strength. At 100%, each displayed ratio is used directly. Preset names no longer secretly multiply ratios. At 0%, preset offsets and compression are neutral; manual EQ, makeup, width and output gain remain active.', 'The shared SAVE PRESET button writes a Version 3 JSON file; LOAD PRESET restores mastering controls, EQ bands and tone preset. Restoration settings, mastering enable, and monitor selections remain unchanged. Presets are separate from audio files.']),
 ('Six-band parametric EQ', ['Each band has enable, filter type, frequency, gain and Q. Types are bell, low shelf, high shelf, high-pass and low-pass. Gain ranges ±18 dB; Q ranges 0.1–18. Shelves use Q as damping. Gain has no effect on high/low-pass filters. The graph displays the six-band response; main preset tone controls are additional. Drag enabled graph nodes to change frequency and gain; use the wheel over a node to adjust Q. The spectrum behind it follows monitor audio during playback.', 'Frequencies above 45% of the loaded sample rate are clamped. The default high-pass at 30 Hz and low-pass at 18 kHz are disabled. The other four default bands have zero gain. EQ enable bypasses the six bands; it does not disable the main Bass/Mid/Treble controls. Parameter changes crossfade over one audio block.']),
 ('Four-band compressor', ['Four compensated fourth-order Linkwitz-Riley bands have default crossovers at 200 Hz, 1 kHz and 4 kHz. Crossovers must be at least one octave apart and below 45% of the sample rate. Change them from the outside inward when reducing their separation. Unity-gain recombination has flat magnitude with all-pass phase; this is not linear-phase processing.', 'Each band has threshold (-60 to 0 dBFS), ratio (1:1–20:1), attack (0.1–200 ms), release (10–2000 ms), soft knee (0–24 dB) and makeup gain (±18 dB). The detector uses the greater left/right smoothed power and applies the same gain to both channels. A fixed 5 ms power detector precedes the adjustable attack/release gain envelope, so attack describes gain response after detection.', 'Bypass dynamics disables compression and makeup for that band while retaining its crossover/tone path. Unchecking four-band compression bypasses dynamics across all four bands. Solo isolates selected bands for monitoring; several bands may be soloed together. Solo is always cleared internally for export. Each compressor strip has a live gain-reduction meter. Drag the three graph markers to adjust crossovers.']),
 ('Stereo width', ['Width uses mid/side processing. 1.00 is original width, 2.00 doubles side amplitude, and 0.00 removes the adjustable side contribution. The center signal is preserved. Width transitions use a 10 ms time constant. Mono input stays mono; the widener does not invent stereo information.', 'Protect existing bass width retains the existing low-frequency side signal and adjusts the remaining side signal. The bass crossover ranges 40–400 Hz. With protection enabled, setting width to zero still retains bass stereo. Disable protection for complete mono width. Protection uses an IIR filter and is not a brick-wall separation.', 'The stereo page includes a monitor vectorscope. Correlation is measured before mono audition; negative values indicate a need to check mono compatibility. Mono audition sums the signal to equal left/right channels for listening only. It is never applied to export. Widening may increase peaks; the final export limiter follows it.']),
 ('Loudness and leveling', ['Export targets integrated loudness from -30 to -6 LUFS, default -14. The independent peak ceiling ranges -6 to -0.1 dBTP, default -1. The limiting budget is 0–12 dB, default 6. The engine renders the complete processed song once, measures it, applies gain and a linked 4× oversampled limiter, and remeasures the encoded WAV.', 'The limiting budget limits normalization drive relative to source peak headroom. Some sources cannot reach the selected LUFS within that budget. The completion dialog and report show the achieved result and any warning. This peak measurement is a 4× polyphase estimate, not independently certified. Playback uses a sample ceiling and does not chase a LUFS target. The Studio output meters show sample peaks. TRUE PEAK is labeled LAST EXPORT and remains unavailable until an export has completed for the current source.', 'Session integrated, momentary and short-term LUFS follow actual playback, including Level Match and monitor choices, and reset on seek/stop. Short/silent or below-gate audio has no integrated loudness reading. Mono and band solo audition are excluded from export.', 'Drift Correction is separate from final loudness: it reduces detected upward long-term trends during restoration. It is not phrase-by-phrase automatic gain riding and can affect intentional builds. Choose it before loading or reload after changing it.']),
 ('Using the metal Studio', ['The Studio uses the same drawn metal knobs and hardware buttons as the main window. Drag a knob vertically, wheel to adjust, or hold Shift for finer movement. Double-click a knob to type a value; right-click to reset. Width entry uses percentages. Tab moves focus; arrows adjust numeric controls; Enter opens a value entry or activates a button. Escape closes the Studio. The window scales its artwork and hit areas together.', 'Each EQ band has an ON/OFF button and filter-type menu. The persistent footer includes play/stop, tone preset selection, LOAD PRESET, SAVE PRESET, BYPASS ALL and LEVEL MATCH. These share state with the main application. The Studio has no separate processing engine. Preset saving is available on every tab.']),
 ('Comparison and monitoring',
  ['ORIGINAL selects dry source monitoring; PROCESSED selects restoration plus enabled mastering. Selecting '
   'either exits removed listening. ORIGINAL is monitor only: exporting still uses the chosen processing '
   'settings. BYPASS ALL instead bypasses both processing stages for monitoring and export while retaining '
   'knob values.',
   'LISTEN TO REMOVED monitors original minus restored signal, before mastering. It can contain music and '
   'drift-related level changes; it is not isolated noise. Dry and wet use identical loop fades and source '
   'positions.',
   'LEVEL MATCH approximately matches mastered playback RMS to restored playback RMS. It does not match the '
   'restored track to original, perform integrated LUFS matching, or affect exports. The final monitor '
   'safety clamp limits samples to +/-0.999, including float source overloads. Disable Level Match and '
   'Removed when checking export levels.']),
 ('Export formats',
  ['EXPORT WAV opens a format dialog, then a destination picker. Choose 24-bit PCM WAV or 32-bit float WAV. '
   'Float WAV defaults for loaded FLOAT/DOUBLE WAV sources; other inputs default to PCM24. Either choice is '
   'available for every supported input. MP3 is decoded without re-encoding to MP3.',
   'Exports retain source sample rate, channel count, alignment and full sample count. Settings are captured '
   'when export starts. Looping, ORIGINAL monitoring, Level Match, Listen to Removed, band solo, and mono audition are excluded. '
   'BYPASS ALL exports the original audio in the selected format.',
   'PCM24 rejects sample overload when mastering is off. Float32 preserves finite values above full scale '
   'when mastering is off; downstream playback may clip. With mastering on, both formats undergo final peak '
   'control and optional LUFS targeting. Float export does not recover discarded MP3 information.',
   'No dither is added. Export rejects nonfinite output or values outside float32 range. The JSON report '
   'includes selected target, achieved integrated LUFS, measured 4× true peak, sample peak, peak limiting '
   'and any warnings. The source path is protected and the WAV is written through a temporary file. Loudness '
   'finalization adds export time and uses a temporary floating-point render; restoration is rendered only '
   'once.']),
 ('Controls, meters and performance',
  ['Drag knobs vertically, wheel to adjust, Shift for finer adjustment, double-click to reset. Frequency '
   'uses logarithmic drag and relative wheel/key steps. Tab/Shift-Tab changes control focus; arrows adjust; '
   'Home/End sets limits. Enter/Space activates a focused button; otherwise Space toggles playback. '
   'Cmd/Ctrl+O opens audio and Cmd/Ctrl+E exports.',
   'WAVEFORM displays the source and supports seeking and loop editing. SPECTRUM displays recent monitor FFT '
   'amplitude. REDUCTION shows recent NR RMS level decrease and mastering compression; NR decrease includes '
   'musical attenuation and is not a pure noise measurement.',
   'L/R bars show sampled monitor peaks. Session LUFS readouts and per-band gain reduction are available in '
   'the mastering panel/settings. NR LOAD measures worker time per restoration block and excludes mastering, '
   'metering and export; it is not total CPU. Buffer Misses counts playback underruns.',
   'The background worker restores 16384-frame blocks with 0.5 seconds context per side. Device buffers are '
   '2048 frames. Mastering and lightweight playback metering run in the output callback; graphics and '
   'restoration transforms do not. Select your output device in operating-system sound settings.']),
 ('Install and troubleshooting',
  ['Build Mac App.command builds a native Mac app with bundled Python, runs the tests and app self-test, and '
   'preserves prior build folders. Build-Windows.ps1 or the included GitHub Actions workflow builds the '
   'Windows x64 app ZIP. Extract the entire Windows folder and run Restoration Lab.exe; keep its files '
   'together.',
   'This source package is version 3.0.0. Platform installers are unsigned/unnotarized unless you sign them '
   'separately. Build and listen on the intended platform before distributing binaries. USER GUIDE opens '
   'this searchable manual; assets/User_Guide.html is the portable copy.',
   'If playback drops, compare STFT with Both, disable frequency targeting, close other heavy applications, '
   'and restart playback. If processing dulls transients, reduce amounts/strength, lower Grain, broaden or '
   'disable focus, or compare with drift disabled.',
   'If export differs from playback, disable matching/removed monitoring, select PROCESSED and confirm '
   'mastering and bypass settings. Float overloads may clip in playback while remaining intact in the '
   'exported file.'])]

def html_document():
    toc=''.join(f'<li><a href="#section-{i}">{escape(title)}</a></li>'
                for i,(title,_) in enumerate(SECTIONS))
    content=''.join(f'<section id="section-{i}"><h2>{escape(title)}</h2>'+''.join(
        f'<p>{escape(paragraph)}</p>' for paragraph in paragraphs)+'</section>'
        for i,(title,paragraphs) in enumerate(SECTIONS))
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+f'<title>{TITLE} — User Guide</title>'+'''<style>
body{margin:0;background:#101718;color:#e8eded;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:48px 28px}h1{font-size:34px;line-height:1.2}h2{font-size:25px;color:#50d4c8;border-bottom:1px solid #344344;padding-bottom:8px}a{color:#66ded2}nav{background:#1a2425;border:1px solid #344344;padding:12px 28px;border-radius:8px}nav ol{columns:2;gap:40px}section{margin-top:44px;scroll-margin-top:20px}p{margin:12px 0 20px}.subtitle{color:#b5c3c4}@media(max-width:600px){nav ol{columns:1}main{padding:25px 18px}}@media print{body{background:white;color:black;font-size:11pt}main{padding:0;max-width:none}h2,a{color:#164740}nav{background:white}section{break-inside:auto}h2{break-after:avoid}p{orphans:3;widows:3}}
</style><main>'''+f'<h1>{TITLE}</h1><p class="subtitle">Help manual &amp; user guide · File restoration and mastering</p><nav aria-label="Contents"><ol>{toc}</ol></nav>{content}</main></html>'


def open_manual(parent):
    existing=getattr(parent,'_restoration_manual',None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        return existing
    window=tk.Toplevel(parent)
    parent._restoration_manual=window
    window.title(TITLE+' — User Guide')
    window.geometry(f'{min(1000,parent.winfo_screenwidth()-60)}x{min(680,parent.winfo_screenheight()-120)}')
    window.minsize(660,420)
    window.configure(background='#11191a')
    top=tk.Frame(window,bg='#11191a',padx=16,pady=12)
    top.pack(fill='x')
    tk.Label(top,text=TITLE+' — User Guide',bg='#11191a',fg='#f0f4f3',font=('Helvetica',17,'bold')).pack(side='left')
    query=tk.StringVar(window)
    search=tk.Entry(top,textvariable=query,width=19,bg='#263334',fg='white',insertbackground='white')
    search.pack(side='left',padx=(20,8))
    body=tk.Frame(window,bg='#11191a')
    body.pack(fill='both',expand=True,padx=12,pady=(0,12))
    topics=tk.Listbox(body,width=25,bg='#1a2526',fg='#eef3f1',selectbackground='#20554f',
                      exportselection=False,highlightthickness=0,font=('Helvetica',11))
    topics.pack(side='left',fill='y',padx=(0,10))
    scrollbar=ttk.Scrollbar(body)
    scrollbar.pack(side='right',fill='y')
    article=tk.Text(body,wrap='word',bg='#11191a',fg='#e3ece9',font=('Helvetica',12),
                    padx=16,pady=12,borderwidth=0,highlightthickness=0,yscrollcommand=scrollbar.set)
    article.pack(side='left',fill='both',expand=True)
    scrollbar.config(command=article.yview)
    article.tag_configure('heading',font=('Helvetica',19,'bold'),foreground='#50d4c8',spacing1=18,spacing3=10)
    article.tag_configure('body',spacing3=13)
    article.tag_configure('found',background='#725928',foreground='white')
    for i,(title,paragraphs) in enumerate(SECTIONS):
        topics.insert('end',title)
        article.mark_set('section'+str(i),article.index('end-1c'))
        article.mark_gravity('section'+str(i),'left')
        article.insert('end',title+'\n','heading')
        for paragraph in paragraphs: article.insert('end',paragraph+'\n\n','body')
    article.config(state='disabled')
    article.mark_set('insert','1.0')
    def jump(event=None):
        selected=topics.curselection()
        if selected:
            article.see('section'+str(selected[0]))
            article.yview('section'+str(selected[0]))
    topics.bind('<<ListboxSelect>>',jump)
    def find_next(event=None):
        article.tag_remove('found','1.0','end')
        term=query.get().strip()
        if not term: return 'break'
        start=article.index('insert+1c')
        found=article.search(term,start,stopindex='end',nocase=True)
        if not found: found=article.search(term,'1.0',stopindex='end',nocase=True)
        if found:
            article.tag_add('found',found,f'{found}+{len(term)}c')
            article.mark_set('insert',found)
            article.see(found)
        else: window.bell()
        return 'break'
    ttk.Button(top,text='Find next',command=find_next).pack(side='left')
    search.bind('<Return>',find_next)
    window.bind('<Command-f>',lambda event:search.focus_set())
    window.bind('<Control-f>',lambda event:search.focus_set())
    window.bind('<Escape>',lambda event:window.destroy())
    return window
