# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec — single-file Windows executable.

Build (on Windows, or via the GitHub Actions workflow):
    pip install -r requirements.txt pyinstaller
    pyinstaller --noconfirm --clean SwimmingTinyWhale.spec
Output: dist/SwimmingTinyWhale.exe

All art is procedural and sounds are synthesised at runtime, so there are no
data files to bundle. Save files are written next to the .exe (see
storage._here). ``assets.draw`` is imported lazily inside functions, so it is
listed as a hidden import.
"""

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['assets', 'assets.draw'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'numpy', 'tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SwimmingTinyWhale',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,   # windowed game — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
