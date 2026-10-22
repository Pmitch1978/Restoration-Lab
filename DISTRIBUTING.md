# Create a GitHub release

## On your Mac

1. Extract this source package into a fresh folder. Run **Build Mac App.command** and wait for SUCCESS. This creates and smoke-checks the bundled app.
2. Run **Create GitHub Release.command**. It finds the newest local build, checks version/identity/signature/architecture, runs the bundled smoke check, and creates an installer and ZIP under a new `github-releases` folder.
3. Test the `.pkg` on a second Mac if available. Confirm it installs into Applications, opens, displays Version 1.5 and the waveform icon, opens USER GUIDE, plays your WAV and exports. The packager inspects payload contents but does not perform an installation test.

If your already-built app is elsewhere, run `bash "Create GitHub Release.command" "/absolute/path/Restoration Lab.app"` from the source folder. The helper only packages the app; it does not upload or install it.

## On GitHub

Create a repository and add the **contents** of this source folder, including README.md, Python files, assets, launchers and installer-components.plist. Keep virtual environments, app builds and packaging-work out of the source repository. The included .gitignore excludes those generated files.

Choose **Releases → Draft a new release**, create tag **v1.5.0**, and title it **Restoration Lab 1.5**. Paste RELEASE_NOTES.md into the release description. Attach the generated **.pkg**, **.zip** and **SHA256SUMS.txt**, plus README.md and RELEASE_NOTES.md if you want the complete checksum set downloadable. Publish only after your Mac testing. For an experimental release, mark it as a pre-release.

End users download the binary assets under Releases. GitHub's automatic source ZIP is source code and does not contain a compiled Mac app. Do not upload the local `packaging-work` folder or virtual environments as release assets.

## What the installer does

The unsigned component package installs one application bundle into **/Applications/Restoration Lab.app** using Apple's Installer. It has no preinstall/postinstall scripts, background services or network downloads. The app bundle contains its runtime. Installer may request administrator authorization. Quit the app before updating; replacement uses standard Installer upgrade behavior.

The generated filename includes the app version and executable architecture. A build on your M1 using native Python is normally arm64; it does not support Intel unless separately built/tested. The script does not infer a minimum supported macOS version or claim compatibility with untested Macs. Record the macOS version and hardware you actually tested in your release notes.

## Signing status

The current build uses local ad-hoc app signing and creates an **unsigned** PKG. It is not an Apple-notarized public release. Expect security prompts or blocks on downloaded copies; do not describe it as verified by Apple. Users can inspect the source/run it with Python if they prefer.

For a normal Developer ID distribution workflow, sign the app and its nested code with a Developer ID Application identity and hardened-runtime settings, sign the installer with Developer ID Installer, then submit the distribution to Apple's notarization service and staple the accepted ticket. That workflow requires your Apple developer identities and is not performed by this helper. Signing just the PKG does not convert the contained ad-hoc app into a notarized app.

References: [Apple: packaging Mac software](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution), [Apple: notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [GitHub: managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).
