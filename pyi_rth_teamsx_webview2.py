# PyInstaller runtime hook — 须在 import qtwebview2 之前执行
import importlib.util
import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _meipass = sys._MEIPASS

    def _get_absolute_path(filename: str) -> str:
        return os.path.join(_meipass, "qtwebview2", filename)

    _existing = sys.modules.get("qtwebview2.utils")
    if _existing is not None:
        _existing.get_absolute_path = _get_absolute_path
    else:
        _utils_py = os.path.join(_meipass, "qtwebview2", "utils.py")
        if os.path.isfile(_utils_py):
            _spec = importlib.util.spec_from_file_location("qtwebview2.utils", _utils_py)
            if _spec is not None and _spec.loader is not None:
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _mod.get_absolute_path = _get_absolute_path
                sys.modules["qtwebview2.utils"] = _mod
