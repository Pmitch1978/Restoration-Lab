"""Versioned user guide shared by the in-app reader and portable HTML."""
from html import escape
import tkinter as tk
from tkinter import ttk

TITLE = 'Restoration Lab Version 1.5'
SECTIONS = [
('Welcome', [
 'Restoration Lab restores loaded WAV or MP3 files and lets you adjust noise reduction and mastering while listening. Version 1.5 includes the metal interface, waveform app icon and this built-in guide.',
 'This version processes files. It does not accept a live microphone or interface input. It analyzes the complete song before playback, then processes upcoming audio blocks in real time. The original file is preserved.']),
('Quick start', [
 '1. Choose your speakers or external interface as the output in macOS System Settings → Sound. Use headphones or monitors for detailed listening.',
 '2. Choose Drift Correction before loading the song. Click LOAD AUDIO and select a mono or stereo WAV or MP3 at 44.1 or 48 kHz. Wait for analysis to finish.',
 '3. Press Play. Start with Wavelet mode; compare STFT and Both. Turn the amount knobs down if processing changes useful musical texture.',
 '4. Select B · MASTERED to hear mastering. Choose a preset, adjust Strength and EQ, then compare with A · UNMASTERED. Level Match helps reduce loudness bias while listening.',
 '5. Click EXPORT and choose a new filename. Export follows the selected restoration, mastering, EQ, strength and output settings. Listen to the exported file to confirm the result.']),
('Mouse and keyboard', [
 'Knobs: drag upward to increase and downward to decrease. Hold Shift for a finer drag. Double-click a knob to restore its initial value. The mouse wheel adjusts the knob under the pointer.',
 'NR Strength: click or drag its horizontal aluminum slider. The wheel also adjusts it. Percentage controls use 1% wheel/key increments and EQ/output use 0.1 dB; Shift makes wheel/key increments ten times finer.',
 'Tab moves focus between controls; Shift-Tab moves backward. Arrow keys adjust a focused knob or slider. Home/End sets its minimum/maximum. Enter or Space activates a focused button. Space otherwise toggles playback.',
 '⌘O opens a WAV or MP3; ⌘E exports. Resize the main window to scale the faceplate. USER GUIDE or Help → User guide opens this manual.']),
('Files and analysis', [
 'Supported input: finite mono or stereo WAV or MP3 audio at 44.1 or 48 kHz, containing at least 2048 samples. Other rates and channel layouts must be converted before opening. WAV files that contain silence are supported.',
 'MP3 is decoded to floating-point audio before analysis. WAV is preferred when available: restoration cannot recover detail lost to MP3 compression. Output remains 24-bit PCM WAV; no MP3 re-encoding is performed.',
 'Profiling uses the quietest 12% of the relevant analysis frames. Quiet sections may still contain music: the profile is a low-energy texture estimate, not a recording of noise alone. Thresholds are calculated for each song.',
 'PROFILE / DETAILS shows the analysis report, including available measured drift, adaptive values and processing settings. This build analyzes on load; there is no separate Learn or Freeze mode.',
 'Wait for loading/analysis to finish before opening another file. Choosing Drift Correction after a file has loaded does not reanalyze it; reload the audio file to apply that choice.']),
('Restoration modes', [
 'OFF: passes the original source through the NR section. Mastering can still be enabled independently. BYPASS ALL is the separate control for bypassing both sections.',
 'STFT: frequency-dependent spectral attenuation based on the song profile. At 100% amount, the gain floor allows up to 7 dB attenuation per time-frequency bin. That is not a promise of 7 dB total noise removal.',
 'WAVELET: full-spectrum sym8 stationary wavelets, nine levels, including the A9 approximation and all detail components. Gains are linked between stereo channels. At 100% amount, attenuation is capped at 2 dB per coefficient, with approximately 5 ms gain smoothing.',
 'BOTH: drift correction when enabled, then STFT, then wavelet processing. It combines the methods in sequence and may change musical texture more than either alone. Compare by ear. The wavelet profile remains the one calculated from the corrected song; it is not reestimated whenever the STFT knob changes.',
 'STFT Amount and Wavelet Amount set each method from 0–100%. They change attenuation directly. Their attenuation caps also scale with amount; zero bypasses the corresponding method.',
 'NR Strength multiplies both amount settings without moving their knobs. Example: STFT 60%, Wavelet 80%, Strength 50% gives effective amounts of 30% and 40%. At Strength 0%, NR and its drift correction are bypassed; mastering can remain active.']),
('Drift correction', [
 'The drift option estimates a slow upward level trend before wavelet profiling. It measures stereo RMS in 5-second windows, excluding the first and last 15 seconds, then fits a robust Theil–Sen trend.',
 'Only a positive measured trend receives a smooth opposing downward gain ramp. There is no upward correction for a falling trend. Short songs or insufficient analysis windows can produce no drift correction.',
 'The correction applies in Wavelet/Both modes and scales with the effective wavelet amount. STFT-only and Off do not apply it. The method can interpret an intentional musical build as an upward trend: compare with Drift Correction disabled by reloading the file.']),
('Mastering and EQ', [
 'A · UNMASTERED monitors restored audio without the mastering section. B · MASTERED adds the selected EQ, compressor, output gain and sample-peak ceiling. Click A/B to alternate. Switching A/B uses a brief transition rather than an abrupt cut.',
 'Presets: Natural has flat preset EQ and a base compressor ratio of 2:1. Warm uses +1.5 dB bass, −0.5 dB mid and −1 dB treble with a base ratio of 2.5:1. Punchy uses +1 dB bass, +0.5 dB mid and +1 dB treble with a base ratio of 3:1.',
 'Five additional presets: Bright (−1/−0.5/+3 dB bass/mid/treble, 2:1); Vocal (−1/+2/+1 dB, 2:1); Acoustic (−1/+1/+2 dB, 1.5:1); Deep Bass (+3/−1/−1 dB, 2.5:1); Smooth (+1/0/−3 dB, 2:1). These are starting curves using the same EQ/compressor, not separate mastering algorithms.',
 'Choosing a preset from the menu now enables B: Mastering On. It does not turn off Bypass All or Listen to Removed: the status line warns if either prevents hearing mastering. The mastering panel shows the effective EQ and ratio, or explains why mastering is not being monitored.',
 'If presets seem inactive, check B: Mastering On, Bypass All, Listen to Removed and Strength. At Strength 0%, presets converge to flat preset EQ and a 1:1 compressor. Natural has flat preset EQ at every strength; its effect is compression above threshold. Level Match reduces loudness differences, so listen for tone and dynamics rather than volume alone. Try Bright versus Smooth at 100% Strength for a clear tonal comparison, then reduce Strength to taste.',
 'Strength scales the preset EQ offsets and compressor ratio. At 0% the preset offsets are zero and the ratio is 1:1. Manual EQ and Output remain effective when B is enabled; Strength is not an overall wet/dry control.',
 'Bass, Mid and Treble each range from −6 to +6 dB and add to the strength-scaled preset EQ. The filters are a 150 Hz bass shelf, a 1 kHz mid bell (Q 0.7) and a 6 kHz treble shelf.',
 'Output ranges from −18 to +12 dB. The mastered path has a −1 dBFS sample-peak ceiling; this is not an oversampled true-peak limiter. Fast or extreme changes can sound harsh. Adjust while listening and inspect the export.',
 'The compressor uses stereo-linked RMS detection, about 20 ms smoothing and a −18 dBFS threshold. There is no automatic makeup gain or integrated LUFS target. These are simple mastering tools, not a certified loudness/true-peak mastering suite.']),
('A/B, bypass and monitoring', [
 'BYPASS ALL temporarily selects the original source with NR, mastering and removed-signal monitoring disabled. Press again to restore your settings. The knobs keep their displayed values. Export while bypassed writes the original signal to the selected PCM24 output format.',
 'LISTEN TO REMOVED monitors original source minus the NR output. It helps reveal useful musical content being attenuated. The difference can include drift-related level changes; it is not isolated noise. It overrides the mastered monitor signal while enabled, but does not change exported audio.',
 'LEVEL MATCH performs approximate, smoothed RMS matching between restored and mastered audio for monitoring. It is not integrated LUFS matching and is not exported. Matching occurs after the mastering ceiling, so the final monitor safety clamp can still operate. Disable it when setting final export level.',
 'When comparing restoration against the original, use Off or Bypass All. A/B compares restored audio before and after mastering; it does not itself bypass NR.']),
('Waveform, spectrum and reduction', [
 'WAVEFORM displays the source channels, with a moving playhead. It does not show a pre-rendered cleaned song. Click it to seek. Mono uses one channel; stereo uses two. The time labels span the full song.',
 'SPECTRUM displays an FFT amplitude spectrum of recent monitored output while playing. It reflects mastering, bypass and removed monitoring as selected. It is a visual spectrum, not a calibrated power spectral density or loudness measurement. The spectrum view itself is not a seek control.',
 'REDUCTION displays recent playback history on a 0–12 dB scale. Teal indicates the NR block’s RMS level decrease and amber indicates compressor reduction while mastering is monitored. The small strip below the waveform/spectrum shows the same recent history.',
 'NR RMS decrease is a broad level-change metric, not a count of noise removed. It can include drift correction. History is collected during playback, covers roughly 24 seconds, and resets when another source is loaded.']),
('Meters and performance', [
 'L/R: sample peaks from recent monitored output blocks. Mono is shown on both meters. The meter refresh is about 10 times per second and may miss peaks between sampled blocks. It is not a true-peak meter or export clipping analysis.',
 'GR: sampled compressor gain reduction in dB, shown when monitoring mastering. It does not include NR attenuation or the sample limiter. It reads zero during removed monitoring or full bypass.',
 'NR Load: time spent by the NR worker divided by the duration of its audio block. It excludes mastering and is not the Mac’s total CPU percentage. A 30% reading means that block’s NR work took about 30% of its audio duration.',
 'Buffer Misses: NR producer underruns during this playback run. A miss can produce silence while processing catches up. Counters reset when playback is started again and remain visible after stopping. Device/driver warnings can also appear in the bottom status line.',
 'This build uses 16384-frame NR blocks, 2048-frame device buffers and additional waveform context. Control changes can take several tenths of a second to become audible. It is optimized for song playback, not low-latency instrument monitoring. The external interface does not perform the NR calculations.']),
('Playback and output devices', [
 'Rewind returns to the start and stops. Play starts or pauses; Pause pauses without resetting the playhead. Stop stops and returns to the start. Click the waveform or small progress bar to seek; seeking during playback resumes at the selected position.',
 'SYSTEM AUDIO OUTPUT means the app uses the default device in macOS Sound settings. There is no in-app device selector in this release. Stop playback before changing interface/output settings, then start again.',
 'Use an output device capable of the source sample rate and channel count. If no supported output exists or access fails, an audio-device dialog appears. This version does not record from your interface or route a live input.']),
('Export and delivery', [
 'EXPORT writes the complete source length using the current settings captured when export starts, including the chosen A/B and Bypass state. Export stops playback. Controls changed after export begins do not alter that export.',
 'Output is WAV, 24-bit PCM, at the original sample rate, channel count and sample count. A processing report is saved alongside it as .report.json. The source filename cannot be selected as the export destination.',
 'No automatic normalization, dither, integrated-loudness compensation or true-peak matching is added. The mastered path includes the existing sample-peak ceiling. Unmastered export retains NR without adding that mastering chain.',
 'Level Match and Listen to Removed affect monitoring only. They are excluded from export, so export loudness can differ from matched playback. For a representative audition, disable both monitoring options first.',
 'The exporter rejects nonfinite samples and full-scale overloads and checks the output length. It does not certify codec/inter-sample true peaks. Start with a new output filename: the exporter protects the source, but an existing different destination may be replaced after confirmation in the save dialog.']),
('Install, rebuild and icon', [
 'Start.command runs the Python version. Build Mac App.command creates a bundled Restoration Lab.app on the Mac and checks its runtime. The finished app includes Python and its dependencies; drag the complete .app into Applications.',
 'Version 1.5 embeds the waveform .icns icon and version metadata. To update an installed app, quit it, build this version, then replace the older .app in Applications. Launch the replacement. If a pinned Dock item refers to an older copy, remove that shortcut and drag the new app back into the Dock.',
 'Build on an Apple Silicon Python for an Apple Silicon app. The script does not create a universal Intel/Apple Silicon binary. A local ad-hoc signature is included; this is not a publicly notarized release.',
 'The User_Guide.html file in the assets folder contains this guide for reading outside the app. Open it in a browser; use the browser’s Print command if you want a paper or PDF copy.']),
('Troubleshooting', [
 'No sound: verify an audio file is loaded, the playhead is moving, macOS output is the intended interface, and interface/headphone volume is up. Turn off Listen to Removed: a small difference signal may be very quiet. Try Off or Bypass All.',
 'Controls seem delayed: allow the upcoming processing blocks to reach the output. This version buffers for stable playback; its latency is not determined solely by the audio interface buffer.',
 'Drops or rising Buffer Misses: stop other heavy work, compare STFT-only with Both, stop/restart playback and check the status line for device warnings. Test the built-in output to distinguish an interface problem from processing load.',
 'Unwanted dullness, texture changes or pumping: reduce method amounts/NR Strength, compare modes, compare with drift disabled after reloading, and reduce mastering Strength or EQ. Removed monitoring helps identify content being attenuated.',
 'Export sounds quieter/different: disable Level Match for your comparison and confirm A/B, bypass, preset and Output settings. Monitor matching and removed monitoring are not exported.',
 'Blank or failing Python window: use Python.org 3.13 with its bundled Tk and launch using the supplied script. Startup/interface exceptions from the packaged app are logged at ~/Library/Logs/Restoration Lab/app.log. If a build fails, keep the final error text from Terminal.',
 'Version/icon unchanged: confirm you are opening the newly built app, not Start.command or an earlier .app elsewhere. The faceplate and title bar should both say Version 1.5.']),
]


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
