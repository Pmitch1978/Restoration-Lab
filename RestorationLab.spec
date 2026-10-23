# Build on macOS using the selected native Python interpreter.
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

assets=Path(SPECPATH)/'assets'
datas = [(str(assets/'RestorationLab.png'),'assets'),
         (str(assets/'User_Guide.html'),'assets'),
         (str(Path(SPECPATH)/'test_assets'/'decoder_check.mp3'),'test_assets')]
binaries, hiddenimports = [], []
for package in ('sounddevice', '_sounddevice_data', 'soundfile', '_soundfile_data', 'pywt', 'pyloudnorm'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(['mac_entry.py'], pathex=[SPECPATH], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[],
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Restoration Lab', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name='Restoration Lab')
app = BUNDLE(coll, name='Restoration Lab.app', icon=str(assets/'RestorationLab.icns'),
             bundle_identifier='com.patrickmitchell.restorationlab',
             info_plist={'CFBundleShortVersionString': '3.0.0',
                         'CFBundleVersion': '30',
                         'NSHighResolutionCapable': True,
                         'NSPrincipalClass': 'NSApplication'})
