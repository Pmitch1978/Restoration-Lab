# Restoration Lab 1.5 — Windows build source

This package contains the complete Python app and Windows build automation.
It does NOT contain a precompiled Windows executable.

## Build from a Mac using GitHub

1. Put the CONTENTS of this folder at the root of your GitHub repository.
   Include the hidden .github folder. GitHub's browser uploader may omit hidden
   folders; create .github/workflows/windows-build.yml through Add file >
   Create new file and paste the supplied workflow if necessary.
2. Open the repository's Actions tab and select Build Windows.
3. Click Run workflow. GitHub builds on a Windows machine, runs the tests,
   packages the app, and runs the packaged self-test.
4. Download the successful run's Restoration-Lab-1.5-Windows-x64 artifact.
   Extract it, then extract the Windows zip inside.
5. Launch Restoration Lab.exe inside the Restoration Lab folder.
   Keep all files in that folder together.

The workflow does not publish a release automatically.
Do not call an unsuccessful workflow build a usable release.

## Build on Windows

Install Python 3.13 x64 from python.org with Tcl/Tk and the Python launcher.
Open PowerShell in this folder and run:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\Build-Windows.ps1

The execution-policy option applies only to this process.
Output: Restoration-Lab-1.5-Windows-x64.zip

## Windows changes

- Dedicated Windows launcher, local app data logs, and DPI awareness.
- Windows Arial font lookup and Windows .ico application icon.
- Windows PyInstaller specification bundling the audio libraries and assets.
- Original restoration/mastering code retained.
- Existing Mac files retained for reference and separate Mac builds.

## Before distributing

The automated self-test checks GUI startup, controls, numerical processing,
MP3 decoding, and WAV writing. It does not play audio through physical hardware.
Have a Windows tester load WAV and MP3 files, play/pause/seek, change restoration
and mastering controls, resize the window, open the guide, and export a WAV.
Check both speakers and headphones, and a path containing spaces.
The executable is unsigned. Windows reputation/security prompts may appear.

Logs: %LOCALAPPDATA%\Restoration Lab\Logs\app.log
