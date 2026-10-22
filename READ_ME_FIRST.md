# Restoration Lab Version 1.5

1. Extract this ZIP into a fresh folder on your Mac.
2. Double-click **Start.command** to try the new GUI in Python.
3. To make a standalone Mac app, double-click **Build Mac App.command**.
4. After **SUCCESS**, drag **Restoration Lab.app** from the Finder window into Applications.

See **GUI_README.md** for controls, meters, build checks and limitations. Keep the previous working version until you have tried this one.

Version 1.5 adds the embedded waveform icon, version title, and **USER GUIDE** button. The manual opens inside the app and is also available as **assets/User_Guide.html**. Rebuild and replace the installed `.app` to update its Finder/Dock icon; running Start.command alone does not replace an installed app.

This is the new metal GUI with the established audio engine. It includes source and a Mac builder; it is not a precompiled `.app`.

To distribute on GitHub after building, run **Create GitHub Release.command**. It creates an unsigned `.pkg` installer, app ZIP and checksums. See **DISTRIBUTING.md**. **README.md** is the short GitHub-facing introduction.
