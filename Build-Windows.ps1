$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Run this build on Windows.' }
py -3.13 -m venv .venv-windows
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 x64 from python.org, including Tcl/Tk and the Python launcher.' }
$python = Join-Path $PSScriptRoot '.venv-windows\Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $python -m pip install -r requirements.txt 'pyinstaller>=6.11,<7'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $python -m unittest discover -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& $python -m PyInstaller --clean --noconfirm RestorationLabWindows.spec
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
& '.\dist\Restoration Lab\Restoration Lab.exe' --self-test
if ($LASTEXITCODE -ne 0) { throw 'Packaged application self-test failed.' }
& $python -m pip freeze | Set-Content '.\dist\Restoration Lab\build-dependencies.txt'
Compress-Archive -Path '.\dist\Restoration Lab' -DestinationPath '.\Restoration-Lab-1.5-Windows-x64.zip' -Force
Write-Host 'Built: Restoration-Lab-1.5-Windows-x64.zip'
