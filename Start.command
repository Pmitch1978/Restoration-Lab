#!/bin/bash
set -e
cd "$(dirname "$0")"

on_exit() {
  result=$?
  if [ "$result" -ne 0 ]; then
    echo
    echo "Startup stopped. The error above has been left visible."
    read -r -p "Press Return to close this launcher. " reply
  fi
}
trap on_exit EXIT

# Check Tk WITHOUT opening a window. In particular, reject Apple's old Tk 8.5.
usable_python() {
  "$1" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3,10) and tkinter.TkVersion >= 8.6 else 1)' 2>/dev/null
}

selected_python=""
if [ -n "${RESTORATION_PYTHON:-}" ]; then
  if usable_python "$RESTORATION_PYTHON"; then
    selected_python="$RESTORATION_PYTHON"
  else
    echo "RESTORATION_PYTHON must point to Python 3.10+ with Tk 8.6+."
    exit 1
  fi
fi

# Prefer mature Python versions with broad numerical-wheel availability.
if [ -z "$selected_python" ]; then
  for version in 3.13 3.12 3.11 3.14 3.10; do
    for candidate in \
      "/Library/Frameworks/Python.framework/Versions/$version/bin/python$version" \
      "/opt/homebrew/bin/python$version" \
      "/usr/local/bin/python$version"; do
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
  echo "A compatible GUI runtime was not found."
  echo "Install Python 3.13 using the macOS installer at:"
  echo "https://www.python.org/downloads/macos/"
  echo "That installer supplies its own Tk. Then reopen Start.command."
  echo "The Apple Python 3.9 / deprecated system Tk runtime is not used."
  exit 1
fi

# Use a separate environment; preserve the original .venv and its dependencies.
runtime_tag="$("$selected_python" -c 'import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))')"
runtime_dir=".venv-gui-$runtime_tag"
if [ ! -x "$runtime_dir/bin/python" ]; then
  "$selected_python" -m venv "$runtime_dir"
fi
if ! usable_python "$runtime_dir/bin/python"; then
  echo "The app environment at $runtime_dir has an incompatible Python/Tk runtime."
  echo "Move that app-local folder aside, then launch again."
  exit 1
fi
"$runtime_dir/bin/python" -c 'import sys, tkinter; print("Launching with", sys.executable); print("Python", sys.version.split()[0], "Tk", tkinter.TkVersion)'
"$runtime_dir/bin/python" -m pip install -r requirements.txt
"$runtime_dir/bin/python" app.py
