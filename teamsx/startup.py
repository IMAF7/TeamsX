# -*- coding: utf-8 -*-
"""QApplication 之前的运行时准备。"""
from __future__ import annotations

import os
import sys


def prepare_runtime() -> str:
    """WebView2-only：返回 'webview2'，不做 QtWebEngine 回退。"""
    try:
        from teamsx.bootstrap.frozen_webview2 import patch_frozen_qtwebview2_paths

        patch_frozen_qtwebview2_paths()
    except Exception:
        pass

    if sys.platform != "win32":
        raise RuntimeError("仅支持 Windows WebView2 引擎。")
    if os.environ.get("TEAMSX_ENGINE", "webview2").strip().lower() in (
        "qtwebengine",
        "webengine",
        "chromium",
    ):
        raise RuntimeError("已禁用 QtWebEngine 回退；请移除 TEAMSX_ENGINE=qtwebengine 配置。")

    print("[TeamsX] Teams 页面引擎: WebView2（qtwebview2）")
    try:
        from teamsx.engine.webview2 import apply_webview2_runtime_env, use_webview2

        apply_webview2_runtime_env()
        if not use_webview2():
            raise RuntimeError("qtwebview2 未就绪（请安装/检查 WebView2 运行时与 Python/运行时位数）。")
    except ImportError as e:
        raise RuntimeError(f"缺少依赖: {e}. 请安装 qtwebview2 / pythonnet。")

    from teamsx.bootstrap.ssl import bootstrap_ssl_certs

    bootstrap_ssl_certs()

    if sys.platform == "win32":
        try:
            from teamsx.notify.win_toast import ensure_app_user_model_id, ensure_toast_shortcut

            ensure_app_user_model_id()
            exe = sys.executable if getattr(sys, "frozen", False) else (
                os.path.abspath(sys.argv[0]) if sys.argv else sys.executable
            )
            icon = None
            for base in (
                os.path.dirname(os.path.abspath(exe)),
                os.path.dirname(os.path.abspath(__file__)),
            ):
                cand = os.path.join(base, "logo.ico")
                if os.path.isfile(cand):
                    icon = cand
                    break
            ensure_toast_shortcut(exe_path=exe, icon_path=icon)
        except Exception:
            pass

    print("[TeamsX] 当前 Teams 引擎: webview2")
    return "webview2"
