# -*- coding: utf-8 -*-
"""
PyInstaller 冻结包：修正 qtwebview2 的 DLL 查找路径。

qtwebview2.utils.get_absolute_path 在 frozen 下使用 sys._MEIPASS/lib/...，
实际文件在 sys._MEIPASS/qtwebview2/lib/...，导致 WebView2/.NET 无法加载 → Teams 白屏。
"""
from __future__ import annotations

import importlib.util
import os
import sys


def patch_frozen_qtwebview2_paths() -> bool:
    """在首次 import qtwebview2 包之前调用。成功返回 True。"""
    if not getattr(sys, "frozen", False):
        return False
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return False

    def _get_absolute_path(filename: str) -> str:
        return os.path.join(meipass, "qtwebview2", filename)

    existing = sys.modules.get("qtwebview2.utils")
    if existing is not None:
        existing.get_absolute_path = _get_absolute_path
    else:
        utils_py = os.path.join(meipass, "qtwebview2", "utils.py")
        if not os.path.isfile(utils_py):
            return False
        spec = importlib.util.spec_from_file_location("qtwebview2.utils", utils_py)
        if spec is None or spec.loader is None:
            return False
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.get_absolute_path = _get_absolute_path
        sys.modules["qtwebview2.utils"] = mod

    try:
        import qtwebview2._dotnet_bridge as db

        db.get_absolute_path = _get_absolute_path
    except ImportError:
        pass

    return True
