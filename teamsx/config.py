# -*- coding: utf-8 -*-
"""TeamsX 全局配置。"""
from __future__ import annotations

import os
import sys

_PREFERRED_DATA_ROOT = r"D:\TeamsX"


def _drive_ready(path: str) -> bool:
    """目标盘符存在（如 D: 不存在则直接不可用）。"""
    drive, _ = os.path.splitdrive(os.path.abspath(path))
    if not drive:
        return True
    return os.path.isdir(drive + os.sep)


def _can_use_data_dir(path: str) -> bool:
    """目录可创建且可写。"""
    if not path:
        return False
    if not _drive_ready(path):
        return False
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".teamsx_write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def resolve_data_root() -> str:
    """
    数据根目录：
    1. 环境变量 TEAMSX_DATA_ROOT（用户指定）
    2. D:\\TeamsX（盘符存在且可写）
    3. %LOCALAPPDATA%\\TeamsX
    4. %USERPROFILE%\\TeamsX
    """
    env = os.environ.get("TEAMSX_DATA_ROOT", "").strip().rstrip("\\/")
    if env:
        return env

    if _can_use_data_dir(_PREFERRED_DATA_ROOT):
        return _PREFERRED_DATA_ROOT

    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app:
        fallback = os.path.join(local_app, "TeamsX")
        if _can_use_data_dir(fallback):
            return fallback

    home = os.path.expanduser("~")
    return os.path.join(home, "TeamsX") if home else _PREFERRED_DATA_ROOT


DATA_ROOT = resolve_data_root()

if (
    not os.environ.get("TEAMSX_DATA_ROOT", "").strip()
    and os.path.normcase(os.path.abspath(DATA_ROOT))
    != os.path.normcase(os.path.abspath(_PREFERRED_DATA_ROOT))
):
    print(f"[TeamsX] 未使用 D 盘，数据目录: {DATA_ROOT}")

ENGINE = os.environ.get("TEAMSX_ENGINE", "webview2").strip().lower()

PREFER_WEBVIEW2 = (
    sys.platform == "win32"
    and ENGINE not in ("qtwebengine", "webengine", "chromium")
)

# WebView 池
MAX_ACTIVE_WEBVIEWS = 5
MAX_SUSPENDED_WEBVIEWS = 50
WEBVIEW_IDLE_TIMEOUT = 600

# 角标 / 通知（前台即时 + 后台 3s 轻轮询，避免 120ms 全员扫）
NOTIFICATION_CHECK_INTERVAL = 90
BADGE_FOREGROUND_POLL_MS = 400
BADGE_BACKGROUND_POLL_MS = 3000
BADGE_FAST_POLL_MS = BADGE_FOREGROUND_POLL_MS  # 兼容旧名
BADGE_POLL_BATCH_SIZE = 1
BADGE_CHECKS_PER_TICK = 4
TITLE_BADGE_POLL_MS = BADGE_FOREGROUND_POLL_MS
BADGE_DEBOUNCE_MS = 0

# 维护（周期性重申后台 Low，利于内存逐步回落）
MEMORY_CLEAN_INTERVAL = 300
TEAMS_HEALTH_CHECK_INTERVAL_SEC = 120
TEAMS_HEALTH_RELOAD_COOLDOWN_SEC = 300
SUSPEND_STALE_RELOAD_SEC = 1200
TEAMS_ENGINE_RECOVER_COOLDOWN_SEC = 600
PROFILE_HTTP_CACHE_MAX_BYTES = 48 * 1024 * 1024
DAILY_CACHE_CLEAN_HOUR = 7

# UI
SIDEBAR_SMALL_BTN_W = 52
SIDEBAR_SMALL_BTN_H = 26
MAX_PINNED_ACCOUNTS = 20
ACCOUNTS_TXT_NAME = "accounts.txt"

# 登录
LOGIN_TIMEOUT_SEC = 300
LOGIN_VERIFY_MIN_SEC = 0
LOGIN_VERIFY_REQUIRED_HITS = 2
MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024

# 列表显示状态
DISPLAY_ACTIVE = "active"
DISPLAY_SLEEP = "sleep"
DISPLAY_OFFLINE = "offline"

# profile 缓存清理（保留 Cookies / WidevineCdm）
PROFILE_CACHE_DIRS = [
    "Cache", "Code Cache", "GPUCache", "DawnCache", "DawnGraphiteCache",
    "DawnWebGPUCache", "GrShaderCache", "ShaderCache", "GraphiteDawnCache",
    "Service Worker/CacheStorage", "Service Worker/ScriptCache",
    "blob_storage", "Media Cache", "VideoDecodeStats",
    "optimization_guide_model_store", "component_crx_cache",
    "extensions_crx_cache", "BrowserMetrics", "Crashpad",
    "hyphen-data", "Safe Browsing",
    "Download Service", "Shared Dictionary", "Network Action Predictor",
    "Favicons", "Top Sites", "Visited Links", "JumpListIconsRecentClosed",
    "WebAssistDatabase", "AutofillAiModelCache", "BudgetDatabase",
    "EdgeEDrop", "EntityExtraction", "Nurturing",
    "Platform Notifications", "Notification Resources", "Notification State",
    "SharedStorage", "History",
]

CURRENT_THEME = "light"

BADGE_RED = "#e53935"
BADGE_RED_HOVER = "#c62828"
TEXT_NORMAL = "#e8e8e8"
TEXT_NORMAL_LIGHT = "#1a1a1a"
