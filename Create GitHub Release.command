#!/bin/bash
# Create local GitHub release assets. Does not install, upload or publish.
set -euo pipefail
cd "$(dirname "$0")"
trap 'result=$?; if [ "$result" -ne 0 ]; then echo "Packaging stopped. Review the error above."; fi; read -r -p "Press Return to close. " reply || true' EXIT

if [ "$(uname -s)" != Darwin ]; then
  echo "Create the macOS installer on your Mac."
  exit 1
fi
for command_path in /usr/bin/pkgbuild /usr/sbin/pkgutil /usr/bin/ditto /usr/bin/codesign /usr/bin/shasum /usr/bin/lipo /usr/libexec/PlistBuddy; do
  if [ ! -x "$command_path" ]; then
    echo "Required Mac tool is missing: $command_path"
    echo "Install Apple's Command Line Tools, then retry."
    exit 1
  fi
done

# Optional explicit target: bash 'Create GitHub Release.command' '/path/App.app'
# Otherwise use the latest timestamped build in this extracted project.
app_path="${1:-}"
if [ -z "$app_path" ]; then
  for candidate in "$PWD"/mac-builds/*/dist/"Restoration Lab.app"; do
    if [ -d "$candidate" ]; then app_path="$candidate"; fi
  done
fi
if [ -z "$app_path" ] || [ ! -d "$app_path" ]; then
  echo "First run Build Mac App.command in this folder."
  echo "Then reopen Create GitHub Release.command."
  exit 1
fi
if [ "$(basename "$app_path")" != "Restoration Lab.app" ]; then
  echo "Select the built Restoration Lab.app bundle."
  exit 1
fi
app_path="$(cd "$(dirname "$app_path")" && pwd)/Restoration Lab.app"
app_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app_path/Contents/Info.plist")"
app_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app_path/Contents/Info.plist")"
if [ "$app_id" != com.patrickmitchell.restorationlab ] || [ "$app_version" != 3.0.0 ]; then
  echo "Expected Restoration Lab version 3.0.0. Rebuild from the current source."
  exit 1
fi
executable="$app_path/Contents/MacOS/Restoration Lab"
/usr/bin/codesign --verify --deep --strict "$app_path"
architectures="$(/usr/bin/lipo -archs "$executable")"
case "$architectures" in
  arm64) release_arch=arm64 ;;
  x86_64) release_arch=x86_64 ;;
  *arm64*x86_64*|*x86_64*arm64*) release_arch=universal2 ;;
  *) echo "Unrecognized executable architecture: $architectures"; exit 1 ;;
esac
echo "Checking bundled runtime before packaging…"
"$executable" --self-test

release_tag="$(date +%Y%m%d-%H%M%S)-$$"
release_dir="$PWD/github-releases/v$app_version-$release_arch-$release_tag"
work_dir="$release_dir/packaging-work"
stage_dir="$work_dir/payload"
mkdir -p "$stage_dir"
/usr/bin/ditto "$app_path" "$stage_dir/Restoration Lab.app"
base_name="Restoration-Lab-v$app_version-macOS-$release_arch"
pkg_name="$base_name-unsigned.pkg"
zip_name="$base_name.zip"

# Fixed install destination; do not relocate to another copy found on the Mac.
/usr/bin/pkgbuild --root "$stage_dir" \
  --component-plist "$PWD/installer-components.plist" \
  --install-location /Applications \
  --identifier com.patrickmitchell.restorationlab.installer \
  --version "$app_version" --ownership recommended "$release_dir/$pkg_name"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$app_path" "$release_dir/$zip_name"

# Inspect the payload without installing anything on the build Mac.
/usr/sbin/pkgutil --payload-files "$release_dir/$pkg_name" > "$work_dir/installed-files.txt"
if ! /usr/bin/grep -Fq 'Restoration Lab.app/Contents/MacOS/Restoration Lab' "$work_dir/installed-files.txt"; then
  echo "Installer payload verification failed."
  exit 1
fi
cp README.md "$release_dir/README.md"
cp RELEASE_NOTES.md "$release_dir/RELEASE_NOTES.md"
cd "$release_dir"
/usr/bin/shasum -a 256 "$pkg_name" "$zip_name" README.md RELEASE_NOTES.md > SHA256SUMS.txt
echo
echo "SUCCESS: $release_dir"
echo "Upload the PKG, ZIP and SHA256SUMS.txt to a GitHub Release tagged v$app_version."
echo "Do not upload packaging-work; it is only local staging and verification data."
echo "The PKG is unsigned; the app is not Apple-notarized."
echo "Test the installer on another Mac before publishing."
/usr/bin/open "$release_dir"
