# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — TeamsX（PyQt6 + qtwebview2 WebView2-only）
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPEC))
ICON = os.path.join(ROOT, "logo.ico")

_runtime_hooks = [os.path.join(ROOT, "pyi_rth_teamsx_webview2.py")]
try:
    import _pyinstaller_hooks_contrib

    _contrib_rth = os.path.join(
        os.path.dirname(_pyinstaller_hooks_contrib.__file__), "rthooks"
    )
    for _name in ("pyi_rth_pywintypes.py", "pyi_rth_pythoncom.py"):
        _p = os.path.join(_contrib_rth, _name)
        if os.path.isfile(_p):
            _runtime_hooks.append(_p)
except Exception:
    pass

datas = []
binaries = []
hiddenimports = [
    "qtwebview2",
    "qtpy",
    "pythonnet",
    "chardet",
    "markdown",
    "mistune",
    "pygments",
    "pygments.lexers",
    "pygments.formatters",
    "pygments.formatters.html",
    "certifi",
    "teamsx",
    "teamsx.config",
    "teamsx.startup",
    "teamsx.app",
    "teamsx.bootstrap",
    "teamsx.bootstrap.ssl",
    "teamsx.engine",
    "teamsx.engine.webview2",
    "teamsx.notify",
    "teamsx.notify.win_toast",
]

for pkg in (
    "PyQt6",
    "certifi",
    "qtwebview2",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# qtwebview2 frozen 路径兼容：同时放到 _MEIPASS/lib（库内 get_absolute_path 的 frozen 分支）
_qtwv2_lib_dirs = [
    os.path.join(ROOT, ".venv-build", "Lib", "site-packages", "qtwebview2", "lib"),
]
try:
    import qtwebview2 as _qtwv2_pkg

    _qtwv2_lib_dirs.insert(0, os.path.join(os.path.dirname(_qtwv2_pkg.__file__), "lib"))
except Exception:
    pass
for _lib_dir in _qtwv2_lib_dirs:
    if not os.path.isdir(_lib_dir):
        continue
    for _name in os.listdir(_lib_dir):
        if _name.lower().endswith(".dll"):
            _src = os.path.join(_lib_dir, _name)
            datas.append((_src, "lib"))
    _loader = os.path.join(_lib_dir, "runtimes", "win-x64", "native", "WebView2Loader.dll")
    if os.path.isfile(_loader):
        binaries.append(
            (_loader, os.path.join("lib", "runtimes", "win-x64", "native"))
        )
    break

# 通知音：与 exe 同级的 audio\teams_notify_official.mp3（build.ps1 会再复制一份到 dist 根目录）
_audio_dir = os.path.join(ROOT, "audio")
if os.path.isdir(_audio_dir):
    for _name in sorted(os.listdir(_audio_dir)):
        _src = os.path.join(_audio_dir, _name)
        if os.path.isfile(_src):
            datas.append((_src, "audio"))
else:
    print("WARNING: missing audio/ — notify sound will not be bundled")

if os.path.isfile(ICON):
    datas.append((ICON, "."))

a = Analysis(
    [os.path.join(ROOT, "TeamsX.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=_runtime_hooks,
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TeamsX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.isfile(ICON) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TeamsX",
)
