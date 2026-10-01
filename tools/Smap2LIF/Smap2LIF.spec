# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks.tcl_tk import tcltk_info


datas = collect_data_files(
    "smap2lif",
    includes=["schemas/*"],
)
binaries = []
dll_directory_handles = []


def configure_windows_dll_search_path():
    """Expose standard and Conda runtime DLL folders to PyInstaller."""

    search_directories = [
        Path(sys.base_prefix) / "DLLs",
        Path(sys.base_prefix) / "Library" / "bin",
        Path(sys.prefix) / "DLLs",
        Path(sys.prefix) / "Library" / "bin",
    ]
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        search_directories.append(
            Path(conda_prefix) / "Library" / "bin"
        )

    for directory in dict.fromkeys(search_directories):
        if not directory.is_dir():
            continue

        os.environ["PATH"] = (
            str(directory) + os.pathsep + os.environ.get("PATH", "")
        )
        if hasattr(os, "add_dll_directory"):
            dll_directory_handles.append(
                os.add_dll_directory(str(directory))
            )
        print(f"INFO: Added DLL search directory: {directory}")


def find_windows_tk_dll(prefix, version, discovered_path):
    """Locate a Tcl/Tk DLL in standard CPython installation folders."""

    if discovered_path and Path(discovered_path).is_file():
        return Path(discovered_path)

    version_digits = "".join(str(part) for part in version[:2])
    filenames = (
        f"{prefix}{version_digits}t.dll",
        f"{prefix}{version_digits}.dll",
    )
    search_directories = [
        Path(sys.base_prefix) / "DLLs",
        Path(sys.base_prefix) / "Library" / "bin",
        Path(sys.base_prefix),
        Path(sys.prefix) / "DLLs",
        Path(sys.prefix) / "Library" / "bin",
        Path(sys.prefix),
    ]
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        search_directories.append(
            Path(conda_prefix) / "Library" / "bin"
        )
    for data_directory in (
        tcltk_info.tcl_data_dir,
        tcltk_info.tk_data_dir,
    ):
        if data_directory:
            library_directory = Path(data_directory).parent.parent
            search_directories.append(library_directory / "bin")
    if tcltk_info.tkinter_extension_file:
        search_directories.append(
            Path(tcltk_info.tkinter_extension_file).parent
        )

    unique_directories = list(dict.fromkeys(search_directories))
    for directory in unique_directories:
        for filename in filenames:
            candidate = directory / filename
            if candidate.is_file():
                return candidate

    searched = ", ".join(str(path) for path in unique_directories)
    raise SystemExit(
        f"ERROR: Required {prefix.upper()} DLL was not found. "
        f"Searched: {searched}"
    )


if sys.platform == "win32":
    configure_windows_dll_search_path()

    if not tcltk_info.available:
        raise SystemExit(
            "ERROR: Tkinter is not available in the selected Python "
            "installation. Install Python with Tcl/Tk support and recreate "
            "the virtual environment."
        )

    runtime_directories = (
        (tcltk_info.tcl_data_dir, "_tcl_data", "Tcl"),
        (tcltk_info.tk_data_dir, "_tk_data", "Tk"),
    )
    for source_directory, destination, label in runtime_directories:
        if not source_directory or not Path(source_directory).is_dir():
            raise SystemExit(
                f"ERROR: {label} runtime directory was not found: "
                f"{source_directory!r}"
            )
        datas.append((str(source_directory), destination))

    tcl_dll = find_windows_tk_dll(
        "tcl",
        tcltk_info.tcl_version,
        tcltk_info.tcl_shared_library,
    )
    tk_dll = find_windows_tk_dll(
        "tk",
        tcltk_info.tk_version,
        tcltk_info.tk_shared_library,
    )
    binaries.extend(
        [
            (str(tcl_dll), "."),
            (str(tk_dll), "."),
        ]
    )

a = Analysis(
    ["smap2lif_launcher.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "_tkinter",
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
        "tkinter.ttk",
    ],
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
    a.binaries,
    a.datas,
    [],
    name="Smap2LIF",
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
    version="version_info.txt",
)
