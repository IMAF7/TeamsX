# -*- coding: utf-8 -*-
"""
Teams 页面引擎 — WebView2（Edge 148 原生 DRM / 视频）。

设计原则：
- 单内核：不拦截 NewWindow / window.open / SharePoint 导航，完全交给 Teams + WebView2
- 仅做：权限放行、SSO 环境变量、文档脚本注入、页面适配器
"""
from __future__ import annotations

import os
import shutil
import sys
from typing import Any, Callable, List, Optional

from PyQt6.QtCore import QTimer, QUrl


def use_webview2_multi_profile() -> bool:
    """单 Environment + 多 Profile 共享浏览器进程（省内存）。设 TEAMSX_MULTI_PROFILE=0 可回退旧模式。"""
    return os.environ.get("TEAMSX_MULTI_PROFILE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def webview2_profile_name(account_id: int) -> str:
    return f"acc_{int(account_id)}"


def migrate_legacy_session_to_shared_profile(
    legacy_session_dir: str, shared_udf: str, profile_name: str
) -> None:
    """首次启用共享 Profile 时，把旧 per-account session 目录拷到新 Profile。"""
    legacy = os.path.abspath(legacy_session_dir or "")
    shared = os.path.abspath(shared_udf or "")
    if not legacy or not shared or not profile_name:
        return
    dest = os.path.join(shared, profile_name)
    marker = os.path.join(dest, ".teamsx_profile_migrated")
    if os.path.isfile(marker):
        return
    if not os.path.isdir(legacy):
        return
    try:
        if os.path.isdir(dest) and any(os.scandir(dest)):
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write("existing\n")
            return
        os.makedirs(dest, exist_ok=True)
        for name in os.listdir(legacy):
            src = os.path.join(legacy, name)
            dst = os.path.join(dest, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif os.path.isfile(src):
                shutil.copy2(src, dst)
        print(f"[WebView2] 已迁移账号配置 {profile_name}")
    except Exception as e:
        print(f"[WebView2] 迁移账号配置 {profile_name} 失败: {e}")
    try:
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("ok\n")
    except Exception:
        pass


def use_webview2() -> bool:
    if sys.platform != "win32":
        return False
    if os.environ.get("TEAMSX_ENGINE", "webview2").strip().lower() in (
        "qtwebengine",
        "webengine",
        "chromium",
    ):
        return False
    try:
        os.environ.setdefault("QT_API", "pyqt6")
        import qtwebview2  # noqa: F401

        return True
    except ImportError:
        return False


def teams_engine_name() -> str:
    return "webview2" if use_webview2() else "qtwebengine"


def apply_webview2_sso_env() -> None:
    """SSO + 自动播放；须在首个 WebView2 实例创建前调用。"""
    parts: List[str] = []
    existing = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "").strip()
    if existing:
        parts.append(existing)

    def _add(part: str) -> None:
        if part and part not in " ".join(parts):
            parts.append(part)

    _add("--enable-features=msSingleSignOnOSForPrimaryAccountIsShared")
    _add("--autoplay-policy=no-user-gesture-required")
    # 译达通同款：禁用备用渲染进程，多账号时显著省内存
    if os.environ.get("TEAMSX_KEEP_SPARE_RENDERER", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        _add("--disable-features=SpareRendererForSitePerProcess")
        _add("--disable-spare-renderer-for-site-per-process")
    if os.environ.get("TEAMSX_DISABLE_GPU_COMPOSITING", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        _add("--disable-gpu-compositing")
    # 标准版默认关闭后台节流，保证隐藏账号仍能收到 Teams Notification API 推送
    if os.environ.get("TEAMSX_ENABLE_BG_THROTTLE", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        _add("--disable-background-timer-throttling")
        _add("--disable-renderer-backgrounding")
        _add("--disable-backgrounding-occluded-windows")

    merged = " ".join(parts).strip()
    if merged:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = merged


def apply_webview2_runtime_env() -> None:
    """
    固定版 WebView2 运行时（须 x64 Python + x64 运行时包）：
    TEAMSX_WEBVIEW2_BROWSER_FOLDER → WEBVIEW2_BROWSER_EXECUTABLE_FOLDER
    """
    folder = os.environ.get("TEAMSX_WEBVIEW2_BROWSER_FOLDER", "").strip().strip('"')
    if folder and os.path.isdir(folder):
        os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = os.path.abspath(folder)
        print(f"[WebView2] 固定版运行时: {os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER']}")
    apply_webview2_sso_env()


def bridge_connect_js_webview2(account_id: int, bridge_source: str) -> str:
    return (
        f"window.__accountId = {int(account_id)};"
        + """
    window.connectTeamsBridge = function connectTeamsBridge() {
        if (typeof window.qtwebview2 === 'undefined' || !window.qtwebview2.api) {
            setTimeout(connectTeamsBridge, 100);
            return;
        }
        if (window.__teamsBridgeReady) return;
        window.__teamsBridgeReady = true;
        const api = window.qtwebview2.api;
        window.__externalNotificationCallback = function(type, sender, content, count) {
            if (window.__TEAMS_NOTIFICATIONS_OFF && String(type||'unread') !== 'unread') return;
            try {
                api.post(String(type||'unread'), String(sender||''),
                    String(content != null ? content : ''), parseInt(count, 10) || 0);
            } catch (e) {}
        };
        window.__teamsCopyImageToClipboard = function(dataUrl) {
            try { api.copyImageDataUrl(String(dataUrl)); } catch (e) {}
        };
        window.__teamsCopyImageUrl = function(url) {
            try { api.copyImageUrl(String(url)); } catch (e) {}
        };
        window.__teamsCacheNotifySoundUrl = function(url) {
            try { api.cacheNotifySoundUrl(String(url || '')); } catch (e) {}
        };
        if (window.__teamsSyncBadgeFromTitle) window.__teamsSyncBadgeFromTitle();
    };
    window.connectTeamsBridge();
    """
    )


class WebView2PageAdapter:
    """兼容 TeamsWebView 内 page().runJavaScript / url() 等调用。"""

    @staticmethod
    def _wrap_js_for_qtwebview2(js: str) -> str:
        body = (js or "").strip()
        if not body:
            return "return null;"
        if body.startswith("return "):
            return body if body.endswith(";") else f"{body};"
        if body.endswith(";"):
            body = body[:-1].strip()
        return f"return ({body});"

    def __init__(self, webview_widget, url_changed_cb: Optional[Callable[[QUrl], None]] = None):
        self._wv = webview_widget
        self._url_changed_cb = url_changed_cb
        self._current_url = QUrl()

    def runJavaScript(self, js: str, callback: Optional[Callable[[Any], None]] = None):
        if not self._wv or not getattr(self._wv, "is_ready", False):
            if callback:
                callback(None)
            return

        def _done(result_dict: dict):
            if not callback:
                return
            if not isinstance(result_dict, dict) or not result_dict.get("success", False):
                callback(None)
                return
            callback(result_dict.get("result"))

        self._wv.evaluate_js(self._wrap_js_for_qtwebview2(js), _done)

    def url(self) -> QUrl:
        wv = getattr(self._wv, "_webview", None)
        if wv is not None and getattr(self._wv, "is_ready", False):
            try:
                src = wv.Source
                if src is not None:
                    self._current_url = QUrl(str(src))
            except Exception:
                pass
        return QUrl(self._current_url)

    def set_current_url(self, url: QUrl):
        self._current_url = QUrl(url)

    def triggerAction(self, action):
        try:
            from PyQt6.QtWebEngineCore import QWebEnginePage

            if action == QWebEnginePage.WebAction.ReloadAndBypassCache:
                self._wv.reload()
        except Exception:
            self._wv.reload()

    def setFeaturePermission(self, origin, feature, policy):
        pass

    def setWebChannel(self, channel):
        pass

    def javaScriptConsoleMessage(self):
        return None


def set_core_memory_usage_target_level(core, *, low: bool) -> bool:
    """WebView2：Normal=前台，Low=后台（内存逐步回落，长连接仍可保持）。"""
    from qtwebview2 import _dotnet_bridge as dotnet

    try:
        enum_type = dotnet.Core.CoreWebView2MemoryUsageTargetLevel
        level = enum_type.Low if low else enum_type.Normal
        core.MemoryUsageTargetLevel = level
        return True
    except Exception as e:
        print(f"[WebView2] MemoryUsageTargetLevel({'Low' if low else 'Normal'}): {e}")
        return False


def apply_webview_memory_profile(widget, *, foreground: bool, quiet: bool = False) -> None:
    """对已就绪的 QtWebView2Widget 设置内存档位。"""
    if widget is None or not getattr(widget, "is_ready", False):
        return False
    inner = getattr(widget, "_webview", None)
    if inner is None:
        return False
    try:
        core = inner.CoreWebView2
        if core is not None:
            ok = set_core_memory_usage_target_level(core, low=not foreground)
            if ok and not quiet:
                print(
                    f"[WebView2] 内存档已设为 {'Normal' if foreground else 'Low'}"
                )
            return bool(ok)
    except Exception as e:
        print(f"[WebView2] apply_webview_memory_profile: {e}")
    return False


def _get_core_webview2(widget):
    if widget is None or not getattr(widget, "is_ready", False):
        return None
    inner = getattr(widget, "_webview", None)
    if inner is None:
        return None
    try:
        return inner.CoreWebView2
    except Exception:
        return None


def suspend_core_webview2(widget) -> bool:
    """真正冻结隐藏页：TrySuspendAsync 释放渲染进程内存（脚本/网络暂停，恢复不重载）。"""
    core = _get_core_webview2(widget)
    if core is None:
        return False
    try:
        # TrySuspendAsync 仅对不可见页有效；可见页会抛 COMException。
        core.TrySuspendAsync()
        return True
    except Exception as e:
        print(f"[WebView2] TrySuspendAsync: {e}")
        return False


def resume_core_webview2(widget) -> bool:
    """恢复冻结页：Resume 不重载页面，仅恢复脚本/网络。"""
    core = _get_core_webview2(widget)
    if core is None:
        return False
    try:
        core.Resume()
        return True
    except Exception as e:
        print(f"[WebView2] Resume: {e}")
        return False


def empty_working_set_for_pid(pid: int) -> bool:
    """Windows EmptyWorkingSet：把进程工作集页还给系统（不杀进程）。"""
    if sys.platform != "win32" or int(pid) <= 0:
        return False
    try:
        import ctypes

        PROCESS_SET_QUOTA = 0x0100
        PROCESS_QUERY_INFORMATION = 0x0400
        access = PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION
        handle = ctypes.windll.kernel32.OpenProcess(access, False, int(pid))
        if not handle:
            return False
        try:
            return bool(ctypes.windll.psapi.EmptyWorkingSet(handle))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception as e:
        print(f"[WebView2] EmptyWorkingSet pid={pid}: {e}")
        return False


def empty_working_set_for_widget(widget) -> bool:
    """对 WebView2 宿主窗口所属进程执行 EmptyWorkingSet。"""
    if widget is None or sys.platform != "win32":
        return False
    try:
        import ctypes

        hwnd = int(widget.winId())
        if hwnd <= 0:
            return False
        pid = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return empty_working_set_for_pid(int(pid.value or 0))
    except Exception as e:
        print(f"[WebView2] EmptyWorkingSet widget: {e}")
        return False


def _apply_core_settings(core) -> None:
    from qtwebview2 import _dotnet_bridge as dotnet

    try:
        settings = core.Settings
        settings.IsScriptEnabled = True
        for name, value in (
            ("IsWebMessageEnabled", True),
            ("AreDefaultScriptDialogsEnabled", True),
            ("AreBrowserAcceleratorKeysEnabled", False),
        ):
            if hasattr(settings, name):
                setattr(settings, name, value)
    except Exception:
        pass

    def on_permission(sender, args):
        try:
            args.State = dotnet.Core.CoreWebView2PermissionState.Allow
        except Exception:
            pass

    try:
        core.PermissionRequested += on_permission
    except Exception:
        pass


class TeamsProfileWebView2Widget:
    """QtWebView2Widget 子类：共享 CoreWebView2Environment + 独立 ProfileName。"""

    _shared_env = None
    _shared_env_udf: Optional[str] = None

    @classmethod
    def _get_shared_environment(cls, user_data_folder: str):
        from qtwebview2 import _dotnet_bridge as dotnet

        udf = os.path.abspath(user_data_folder)
        if cls._shared_env is not None and cls._shared_env_udf == udf:
            return cls._shared_env
        task = dotnet.Core.CoreWebView2Environment.CreateAsync(None, udf, None)
        env = task.GetAwaiter().GetResult()
        cls._shared_env = env
        cls._shared_env_udf = udf
        print(f"[WebView2] 共享浏览器进程 Environment: {udf}")
        return env


def _init_webview_multi_profile(widget, profile_name: str) -> None:
    """EnsureCoreWebView2Async(共享 Environment, ProfileOptions)。"""
    from qtwebview2 import _dotnet_bridge as dotnet

    if getattr(widget, "_webview", None):
        return
    dotnet.load_dotnet_env()
    widget._webview = dotnet.WinForms.WebView2()
    props = dotnet.WinForms.CoreWebView2CreationProperties()
    udf = widget._user_data_folder
    if not udf:
        raise RuntimeError("WebView2 shared user data folder is required")
    props.UserDataFolder = udf
    widget._webview.CreationProperties = props
    widget._webview.CoreWebView2InitializationCompleted += widget._on_webview_ready
    widget._webview.WebMessageReceived += widget._on_script_notify
    if widget._is_transparent:
        widget._webview.DefaultBackgroundColor = dotnet.System_.Drawing.Color.Transparent
    elif widget.background_color:
        widget._webview.DefaultBackgroundColor = (
            dotnet.System_.Drawing.ColorTranslator.FromHtml(widget.background_color)
        )
    env = TeamsProfileWebView2Widget._get_shared_environment(udf)
    opts = env.CreateCoreWebView2ControllerOptions()
    opts.ProfileName = (profile_name or "Default").strip() or "Default"
    widget._webview.EnsureCoreWebView2Async(env, opts)


def _make_teams_webview_widget_class(profile_name: str):
    from qtwebview2 import QtWebView2Widget

    pname = (profile_name or "Default").strip() or "Default"

    class _TeamsWv2(QtWebView2Widget):
        def _init_webview(self):
            _init_webview_multi_profile(self, pname)

    return _TeamsWv2


def create_webview2_widget(
    parent,
    session_dir: str,
    user_agent: str,
    js_bridge,
    doc_scripts: List[str],
    on_navigation_completed: Callable[[bool], None],
    on_url_changed: Callable[[QUrl], None],
    on_dom_loaded: Optional[Callable[[], None]] = None,
    *,
    account_id: Optional[int] = None,
    shared_user_data_folder: Optional[str] = None,
):
    """创建 WebView2 控件。不拦截新窗口/媒体链接，行为与 Edge 嵌入 Teams 一致。"""
    os.environ.setdefault("QT_API", "pyqt6")

    page_adapter = WebView2PageAdapter(None, on_url_changed)

    def init_settings_hook(core):
        from qtwebview2 import _dotnet_bridge as dotnet

        for script in doc_scripts:
            if script and script.strip():
                try:
                    core.AddScriptToExecuteOnDocumentCreatedAsync(script)
                except Exception as e:
                    print(f"[WebView2] 注入脚本失败: {e}")

        def on_nav_completed(sender, args):
            ok = bool(getattr(args, "IsSuccess", False))
            try:
                if sender.Source is not None:
                    page_adapter.set_current_url(QUrl(str(sender.Source)))
            except Exception:
                pass
            QTimer.singleShot(0, lambda o=ok: on_navigation_completed(o))

        def on_source_changed(sender, args):
            try:
                src = sender.Source
                url = QUrl(str(src)) if src is not None else QUrl()
            except Exception:
                url = QUrl()
            page_adapter.set_current_url(url)
            QTimer.singleShot(0, lambda u=QUrl(url): on_url_changed(u))

        core.NavigationCompleted += on_nav_completed
        core.SourceChanged += on_source_changed
        _apply_core_settings(core)
        set_core_memory_usage_target_level(core, low=False)

    multi = (
        use_webview2_multi_profile()
        and account_id is not None
        and shared_user_data_folder
    )
    profile_name = webview2_profile_name(int(account_id)) if multi else ""
    if multi:
        migrate_legacy_session_to_shared_profile(
            session_dir, shared_user_data_folder, profile_name
        )
        Wv2Widget = _make_teams_webview_widget_class(profile_name)
        udf = shared_user_data_folder
    else:
        from qtwebview2 import QtWebView2Widget

        Wv2Widget = QtWebView2Widget
        udf = session_dir

    widget = Wv2Widget(
        parent=parent,
        js_apis=js_bridge,
        user_data_folder=udf,
        user_agent=user_agent if user_agent else None,
        context_menus=False,
        debug=False,
        lazyload=False,
        handle_new_window=False,
        fullscreen_support=False,
        init_settings_hook=init_settings_hook,
    )
    if multi:
        print(
            f"[WebView2] 账号 {account_id} Profile={profile_name} "
            f"(共享进程 {udf})"
        )
    page_adapter._wv = widget

    if on_dom_loaded is not None:
        widget.bridge.domContentLoaded.connect(on_dom_loaded)

    return widget, page_adapter


def dispose_webview2_widget(wv2) -> None:
    """同步释放 WebView2（须在主线程）；走 closeEvent 内 Dispose，避免仅 deleteLater 泄漏。"""
    if wv2 is None:
        return
    try:
        wv2.hide()
        inner = getattr(wv2, "_webview", None)
        if inner is not None and getattr(wv2, "is_ready", False):
            try:
                if not bool(getattr(inner, "IsDisposed", False)):
                    inner.Stop()
            except Exception:
                pass
        wv2.setParent(None)
        wv2.close()
        wv2.is_ready = False
        wv2._webview = None
    except Exception as e:
        print(f"[WebView2] dispose_webview2_widget: {e}")
