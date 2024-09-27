# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['portfolio_balancer.py'],
    pathex=[],
    binaries=[
        ('/usr/bin/cbc', './cbc')  # Ensure the path is correct
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # Ensure binaries are passed here
    a.datas,
    [],
    name='portfolio_balancer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

