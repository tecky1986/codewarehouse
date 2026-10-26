# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for container-packing (onedir, no Python sources).

Build (run from /workspace):
  pyinstaller container_packing.spec

Produces dist/container_packing/ with the container_packing executable
plus an _internal resource directory. Backend code is compiled into the
PYZ archive; only static assets are shipped as data files.
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_ROOT = os.path.dirname(os.path.abspath(globals().get("__file__", "container_packing.spec")))

a = Analysis(
    [os.path.join(_ROOT, "start.py")],
    pathex=[os.path.join(_ROOT, "backend")],
    binaries=[],
    datas=[
        (os.path.join(_ROOT, "backend", "static"), "backend/static"),
    ]
    + collect_data_files("openpyxl")
    + collect_data_files("uvicorn"),
    hiddenimports=collect_submodules("app")
    + collect_submodules("packing_engine")
    + [
        "openpyxl",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.workers",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "tests"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="container_packing",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="container_packing",
)
