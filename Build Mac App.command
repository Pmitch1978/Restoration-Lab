#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
trap 'result=$?; if [ "$result" -ne 0 ]; then echo "Build stopped. Review the error above."; fi; read -r -p "Press Return to close. " reply || true' EXIT

if [ "$(uname -s)" != Darwin ]; then
  echo "Build this package on your Mac, not Linux or Windows."
  exit 1
fi
usable_python() {
  "$1" -c 'import sys, tkinter; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,15) and tkinter.TkVersion >= 8.6 else 1)' 2>/dev/null
}
selected_python="${RESTORATION_PYTHON:-}"
if [ -n "$selected_python" ] && ! usable_python "$selected_python"; then
  echo "RESTORATION_PYTHON must point to Python 3.10–3.14 with Tk 8.6+."
  exit 1
fi
if [ -z "$selected_python" ]; then
  for version in 3.13 3.12 3.11 3.14 3.10; do
    for candidate in "/Library/Frameworks/Python.framework/Versions/$version/bin/python$version" "/opt/homebrew/bin/python$version" "/usr/local/bin/python$version"; do
      if [ -x "$candidate" ] && usable_python "$candidate"; then
        selected_python="$candidate"
        break 2
      fi
    done
  done
fi
if [ -z "$selected_python" ] && command -v python3 >/dev/null 2>&1; then
  candidate="$(command -v python3)"
  if usable_python "$candidate"; then selected_python="$candidate"; fi
fi
if [ -z "$selected_python" ]; then
  echo "Install Python 3.13 from https://www.python.org/downloads/macos/ then retry."
  exit 1
fi
runtime_tag="$("$selected_python" -c 'import sys, platform; print(str(sys.version_info.major)+str(sys.version_info.minor)+"-"+platform.machine())')"
runtime_dir=".venv-mac-build-$runtime_tag"
if [ ! -x "$runtime_dir/bin/python" ]; then
  "$selected_python" -m venv "$runtime_dir"
fi
build_python="$runtime_dir/bin/python"
"$build_python" -c 'import sys, platform, tkinter; print("Building with",sys.executable,platform.machine(),"Tk",tkinter.TkVersion)'
"$build_python" -m pip install -r requirements.txt 'pyinstaller>=6.11,<7' 'pyinstaller-hooks-contrib>=2024.10'
"$build_python" mac_entry.py --self-test

# Unique destinations preserve previous builds and never overwrite an installed app.
build_tag="$(date +%Y%m%d-%H%M%S)-$$"
build_root="$PWD/mac-builds/$build_tag"
mkdir -p "$build_root"
"$build_python" -m pip freeze > "$build_root/build-dependencies.txt"
"$build_python" -m PyInstaller --noconfirm --clean \
  --distpath "$build_root/dist" --workpath "$build_root/work" RestorationLab.spec
app_path="$build_root/dist/Restoration Lab.app"
"$app_path/Contents/MacOS/Restoration Lab" --self-test
/usr/bin/codesign --verify --deep --strict "$app_path"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$app_path" "$build_root/Restoration_Lab_macOS.zip"
echo
echo "SUCCESS: $app_path"
echo "Drag Restoration Lab.app into Applications. Double-click it to launch."
echo "The app contains Python and its dependencies. No Start.command is needed."
/usr/bin/open -R "$app_path"
