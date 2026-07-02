#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TeamsX 多账号管理器 v2.0
- B/Z/M 导入，点击账号登录（一次一个）
- 程序/数据/缓存固定在 D:\\TeamsX（删除该文件夹即清空一切）
- 红色未读角标、Teams 网页内提示音/提醒（非系统通知）、多账号 WebView 池
- Windows 使用 Edge WebView2 显示 Teams（qtwebview2），不再回退 QtWebEngine
"""
import sys
import os

import json
import locale
import math
import re
import base64
from urllib.parse import quote
import urllib.error
import urllib.request
import sqlite3
import shutil
import gc
import hashlib
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Set, List, Tuple
from collections import deque

try:
    import markdown
    from pygments.formatters import HtmlFormatter

    HAS_MARKDOWN = True
except ImportError:
    markdown = None  # type: ignore
    HtmlFormatter = None  # type: ignore
    HAS_MARKDOWN = False

try:
    import mistune
    from pygments import highlight
    from pygments.formatters import HtmlFormatter as PygmentsHtmlFormatter
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.util import ClassNotFound

    HAS_MISTUNE = True
except ImportError:
    mistune = None  # type: ignore
    highlight = None  # type: ignore
    PygmentsHtmlFormatter = None  # type: ignore
    get_lexer_by_name = None  # type: ignore
    guess_lexer = None  # type: ignore
    ClassNotFound = Exception  # type: ignore
    HAS_MISTUNE = False

from teamsx.config import DATA_ROOT as _TEAMS_DATA_ROOT_EARLY
from teamsx.bootstrap.ssl import urllib_ssl_context as _urllib_ssl_context

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget,
QPushButton, QLabel, QDialog, QLineEdit, QFormLayout,
QMessageBox, QSplitter, QFileDialog, QMenu, QCheckBox,
QScrollArea, QComboBox, QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem, QStyle,
QStylePainter, QStyleOptionComboBox,
QTextEdit, QSizePolicy, QFrame, QAbstractScrollArea, QWIDGETSIZE_MAX,
QSystemTrayIcon, QGraphicsDropShadowEffect, QGraphicsOpacityEffect)
from PyQt6.QtGui import (
    QAction, QActionGroup, QFont, QColor, QBrush, QCursor, QGuiApplication,
    QImage, QPixmap, QIcon, QPainter, QFontMetrics, QTextCursor,
    QTextBlockFormat, QPainterPath, QBitmap, QRegion, QPen,
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QPoint, QPointF, QRect, QRectF, QSize, pyqtSignal, QObject, pyqtSlot,
    QThread, QEvent, QEventLoop, QFileSystemWatcher,
    QPropertyAnimation, QEasingCurve, pyqtProperty, QParallelAnimationGroup,
    QSequentialAnimationGroup, QAbstractAnimation,
)
from teamsx.engine.webview2 import (
    use_webview2,
    create_webview2_widget,
    dispose_webview2_widget,
    bridge_connect_js_webview2,
    apply_webview2_runtime_env,
)
from teamsx.notify.win_taskbar_badge import get_taskbar_badge_controller
from teamsx.ui.close_action_dialog import CloseActionCardDialog
from teamsx.ui.confirm_card_dialog import ConfirmCardDialog
from teamsx.ui import win_native_frame

_HAS_TEAMS_ENGINE = True

# 原生窗口边框：保留自定义标题栏，但用系统 DWM 提供最小化/最大化/还原动画、
# 贴边、原生阴影与圆角（与大型软件一致）。
# 注意：默认关闭。开启后窗口改为系统原生边框（自绘客户区），需在本机实测确认
# 显示/缩放/最大化正常后再启用；置 False 即回退旧的自绘无边框窗口。
USE_NATIVE_WINDOW_FRAME = False

DIALOG_LIGHT_STYLE = """
QDialog, QWidget { background-color: #f5f5f5; color: #1a1a1a; }
QLabel { color: #1a1a1a; font-size: 13px; }
QLineEdit, QListWidget { background-color: #ffffff; color: #1a1a1a; border: 1px solid #ccc; padding: 6px; }
QCheckBox { color: #1a1a1a; font-size: 13px; }
QPushButton { background-color: #e8e8e8; color: #1a1a1a; border: 1px solid #bbb; padding: 6px 12px; border-radius: 4px; }
QPushButton:hover { background-color: #ddd; }
"""

# 尝试导入 chardet 用于编码检测
try:
    import chardet

    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False
    print("提示：安装 chardet 可获得更好的文件编码检测，命令：pip install chardet")

# 自定义数据角色常量
REMARK_ROLE = Qt.ItemDataRole.UserRole + 1
STATUS_ROLE = Qt.ItemDataRole.UserRole + 2
GROUP_ID_ROLE = Qt.ItemDataRole.UserRole + 3
PIN_ROLE = Qt.ItemDataRole.UserRole + 4
BADGE_COUNT_ROLE = Qt.ItemDataRole.UserRole + 5

MAX_PINNED_ACCOUNTS = 20

BADGE_RED = "#e53935"
BADGE_RED_HOVER = "#c62828"
TEXT_NORMAL = "#e8e8e8"
TEXT_NORMAL_LIGHT = "#1a1a1a"


def list_delegate_colors() -> Dict[str, str]:
    if CURRENT_THEME == "light":
        return {
            "text": TEXT_NORMAL_LIGHT,
            "text_sel": "#1a3c66",
            "bg_sel": "#e3efff",
            "bg_sel_border": "#9cc4f5",
            "bg_hover": "#eef2f7",
        }
    return {
        "text": TEXT_NORMAL,
        "text_sel": "#eaf2ff",
        "bg_sel": "#33507a",
        "bg_sel_border": "#5a8edb",
        "bg_hover": "#34373c",
    }
BADGE_DEBOUNCE_MS = 120

SCROLLBAR_STYLE = """
QScrollBar:horizontal { height: 0px; max-height: 0px; background: transparent; }
QScrollBar::handle:horizontal { height: 0px; min-height: 0px; background: transparent; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; height: 0; border: none; background: none; }
QScrollBar:vertical { width: 4px; margin: 0; border: none; }
QScrollBar::handle:vertical { min-height: 20px; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; background: none; }
"""

SCROLLBAR_DARK = """
QScrollBar:vertical { background: #252525; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #252525; }
QScrollBar::handle:vertical { background: #5a5a5a; }
QScrollBar::handle:vertical:hover { background: #707070; }
QScrollBar::handle:vertical:pressed { background: #808080; }
"""

SCROLLBAR_LIGHT = """
QScrollBar:vertical { background: #ffffff; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #ffffff; }
QScrollBar::handle:vertical { background: #c8c8c8; }
QScrollBar::handle:vertical:hover { background: #b0b0b0; }
QScrollBar::handle:vertical:pressed { background: #999999; }
"""

APP_DARK_STYLE = """
QMainWindow { background: transparent; }
QWidget#shadowOuter { background: transparent; }
QFrame#mainFrame {
    background-color: #1e1e1e;
    border: none;
    border-radius: 0px;
}
QWidget { background-color: #1e1e1e; color: #e8e8e8; }
QLabel { color: #e8e8e8; background: transparent; }
QListWidget {
    background-color: #252525; border: none; outline: none; color: #e8e8e8;
}
QListWidget::item { padding: 12px 10px; border-bottom: 1px solid #3c3c3c; color: #e8e8e8; }
QListWidget::item:selected { background-color: #3c3c3c; color: #ffffff; }
QListWidget::item:hover { background-color: #2d2d2d; }
QLineEdit, QComboBox {
    background-color: #3c3c3c; color: #ffffff; border: 1px solid #555;
    padding: 6px 8px; border-radius: 4px; selection-background-color: #0078d4;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #3c3c3c; color: #ffffff; border: 1px solid #555;
    selection-background-color: #0078d4; selection-color: #ffffff;
}
QPushButton {
    background-color: #3c3c3c; color: #e8e8e8; border: 1px solid #555;
    padding: 6px 12px; border-radius: 4px;
}
QPushButton:hover { background-color: #4a4a4a; color: #ffffff; }
QPushButton:disabled { background-color: #2d2d2d; color: #666; }
QSplitter::handle { background-color: #3c3c3c; }
QMenu { background-color: #2d2d2d; color: #e8e8e8; border: 1px solid #555; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background-color: #0078d4; color: #ffffff; }
""" + SCROLLBAR_STYLE + SCROLLBAR_DARK

APP_LIGHT_STYLE = """
QMainWindow { background: transparent; }
QWidget#shadowOuter { background: transparent; }
QFrame#mainFrame {
    background-color: #f3f3f3;
    border: none;
    border-radius: 0px;
}
QWidget { background-color: #f3f3f3; color: #1a1a1a; }
QLabel { color: #1a1a1a; background: transparent; }
QListWidget {
    background-color: #f6f6f6; border: none; outline: none; color: #1a1a1a;
}
QListWidget::item { padding: 12px 10px; border-bottom: 1px solid #e0e0e0; color: #1a1a1a; }
QListWidget::item:selected { background-color: #cce4f7; color: #000000; }
QListWidget::item:hover { background-color: #eeeeee; }
QLineEdit, QComboBox {
    background-color: #ffffff; color: #1a1a1a; border: 1px solid #ccc;
    padding: 6px 8px; border-radius: 4px; selection-background-color: #0078d4;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #ffffff; color: #1a1a1a; border: 1px solid #ccc;
    selection-background-color: #0078d4; selection-color: #ffffff;
}
QPushButton {
    background-color: #e8e8e8; color: #1a1a1a; border: 1px solid #bbb;
    padding: 6px 12px; border-radius: 4px;
}
QPushButton:hover { background-color: #dddddd; color: #000000; }
QPushButton:disabled { background-color: #f0f0f0; color: #999; }
QSplitter::handle { background-color: #ddd; }
QMenu { background-color: #ffffff; color: #1a1a1a; border: 1px solid #ccc; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background-color: #0078d4; color: #ffffff; }
""" + SCROLLBAR_STYLE + SCROLLBAR_LIGHT

CURRENT_THEME = "light"
ACCOUNTS_TXT_NAME = "accounts.txt"

_ICON_OK: Optional[QIcon] = None
_ICON_FAIL: Optional[QIcon] = None
_ICON_SLEEP: Optional[QIcon] = None

# 列表圆点：绿=在线活跃，黄=休眠，红=未登录/已卸载
DISPLAY_ACTIVE = "active"
DISPLAY_SLEEP = "sleep"
DISPLAY_OFFLINE = "offline"

# ==================== 配置常量 ====================
WINDOW_SHADOW_MARGIN = 14
WINDOW_FRAME_RADIUS = 16
# WebView2 原生 HWND 常比 Qt 布局宽/高出 1~2px；两主题统一内缩，仅底色随主题变
TEAMS_WEBVIEW_EDGE_INSET = 2
MAX_ACTIVE_WEBVIEWS = 0
MAX_SUSPENDED_WEBVIEWS = 0
# 账号运行档位：foreground=完整扫描；warm_notify=轻量通知保活；cold_unloaded=已卸载
RUNTIME_FOREGROUND = "foreground"
RUNTIME_WARM_NOTIFY = "warm_notify"
RUNTIME_COLD_UNLOADED = "cold_unloaded"
WARM_TITLE_POLL_MS = 1200
WARM_CALL_DETECT_POLL_MS = 300
MEMORY_GUARD_INTERVAL_SEC = 45
# 底线：20 个账号都保持活着+连着收消息，不因内存压力卸载（卸载=点开重刷页面）。
# 仅在系统真的快 OOM（低于红线）时才应急卸载，避免整机崩。
MEMORY_PRESSURE_MIN_FREE_MB = 700
MEMORY_PRESSURE_SUSPENDED_LIMIT = 40
MEMORY_LIGHT_PROBE_INTERVAL_SEC = 5
LOW_MEMORY_RED_MB = 600
# 自适应工作集回收（标准版：不卸载、不冻结、不重载；逐账号判断闲置+体积）
ADAPTIVE_RECYCLE_ACCOUNT_WS_MB = 250
ADAPTIVE_RECYCLE_IDLE_BASE_SEC = 480
ADAPTIVE_RECYCLE_IDLE_MIN_SEC = 90
ADAPTIVE_RECYCLE_IDLE_PER_ACCOUNT_SEC = 12
ADAPTIVE_RECYCLE_SWITCH_QUIET_SEC = 8
ADAPTIVE_RECYCLE_DECISION_MIN_SEC = 20
ADAPTIVE_RECYCLE_DECISION_MAX_SEC = 60
ADAPTIVE_RECYCLE_STEP_WAIT_SEC = 8
ADAPTIVE_RECYCLE_FREE_OK_MB = 2048
ADAPTIVE_RECYCLE_FREE_LIGHT_MB = 1200
ADAPTIVE_RECYCLE_FREE_MEDIUM_MB = 800
ADAPTIVE_RECYCLE_FREE_HEAVY_MB = 300
ADAPTIVE_RECYCLE_TARGET_BASE_MB = 800
ADAPTIVE_RECYCLE_TARGET_PER_ACCOUNT_MB = 430
ADAPTIVE_RECYCLE_ENABLE_WS_TRIM = True
ADAPTIVE_RECYCLE_LOADING_STORM_DELTA = 4
# 智能内存控制器：趋势采样 + 动态决策（非固定周期扫描）
MEMORY_CTRL_SAMPLE_WINDOW_SEC = 600
MEMORY_CTRL_TREND_WINDOW_SEC = 180
MEMORY_CTRL_TREND_MIN_SAMPLES = 4
MEMORY_CTRL_FREE_FALL_MB_PER_MIN = 80
MEMORY_CTRL_USED_RISE_MB_PER_MIN = 120
MEMORY_CTRL_CRITICAL_IDLE_SEC = 15
MEMORY_CTRL_HEAVY_IDLE_SEC = 50
MEMORY_CTRL_MEDIUM_IDLE_SEC = 120
MEMORY_CTRL_SCHED_MIN_SEC = 5
MEMORY_CTRL_SCHED_MAX_SEC = 120
MEMORY_CTRL_RECYCLE_EFFECTIVE_MB = 80
# 内存整理（静默）：停车区脉冲 Normal→Low，不切前台、不闪屏
MEMORY_GROOM_ENABLE = True
MEMORY_GROOM_DWELL_MS = 250
MEMORY_GROOM_USER_QUIET_SEC = 60
MEMORY_GROOM_ACCOUNT_COOLDOWN_SEC = 180
MEMORY_GROOM_WS_TRIGGER_MB = 9500
MEMORY_GROOM_MAINTENANCE_INTERVAL_SEC = 150
MEMORY_GROOM_STEP_WAIT_SEC = 12
MEMORY_ENFORCE_LOW_MEM_MIN_SEC = 120
# 高级：极端 OOM 时允许自动卸载（默认关闭，标准版不卸载在线账号）
ENABLE_AUTO_UNLOAD_ON_OOM = False
AUTO_UNLOAD_OOM_FREE_MB = 200
AUTO_UNLOAD_OOM_SUSTAIN_SEC = 45
# 标准版底线：所有账号保持长连接=都能收消息；后台账号用 Low 内存档+轻量轮询省内存，
# 绝不 TrySuspend 冻结（冻结=断连接=收不到消息）。点开休眠账号瞬间显示，不重载。
ENABLE_BACKGROUND_FREEZE = False
NOTIFY_WAKER_INTERVAL_SEC = 4
NOTIFY_WAKER_DWELL_SEC = 2.5
NOTIFY_WAKER_WAVE_ALL = False
NOTIFICATION_CHECK_INTERVAL = 500
BADGE_FOREGROUND_POLL_MS = 400
BADGE_BACKGROUND_POLL_MS = 3000
BADGE_CHECKS_PER_TICK = 2
TITLE_BADGE_POLL_MS = BADGE_FOREGROUND_POLL_MS
REALTIME_SCAN_MS = 500
CHATLIST_SCAN_MS = 500
TOAST_SCAN_MS = 450
MUTE_ALL_POLL_MS = 3000
NOTIFY_SOUND_SUPPRESS_AFTER_SWITCH_SEC = 2.8
# 来电铃声：video.mp3 播完后重复，挂断立即停止
CALL_NOTIFY_DURATION_SEC = 9.0
# 后台账号来电无 DOM 挂断信号，铃声最长响这么久后自动停（接近 Teams 振铃时长）
CALL_RING_MAX_DURATION_SEC = 40.0
CALL_DETECT_POLL_MS = 200
CALL_END_DEBOUNCE_MS = 900
AUTO_LOGIN_PASSWORD_ERROR_LIMIT = 3
# 启动后短暂建立未读基线，不阻塞消息提示音
NOTIFY_STARTUP_ARM_SEC = 0
NOTIFY_TITLE_SYNC_MIN_MS = 0
MSG_NOTIFY_DEDUP_MAX = 600
MSG_NOTIFY_DEDUP_TTL_SEC = 2.5
# Teams Notification API 事件去重（用 options.tag，比 DOM 扫描稳定）
NOTIFY_API_DEDUP_TTL_SEC = 120.0
# 分级内存：最近 N 个账号保持 Normal；更久未用的账号压到 Low + 停重扫描
MEMORY_TIER_HOT_COUNT = 8
MEMORY_TIER_IDLE_SEC = 600
MEMORY_RENDERER_TRIM_INTERVAL_SEC = 300
LOCK_UNLOAD_INTERVAL_MS = 200
TEAMS_NOTIFY_OFFICIAL_BASENAME = "teams_notify_official.mp3"
TEAMS_CALL_NOTIFY_BASENAME = "video.mp3"
TEAMS_NOTIFY_AUDIO_DIR = "audio"
MEMORY_CLEAN_INTERVAL = 300
TEAMS_HEALTH_CHECK_INTERVAL_SEC = 120
CLOSE_ACTION_SETTING_KEY = "close_action"
TEAMS_HEALTH_RELOAD_COOLDOWN_SEC = 300
TEAMS_ENGINE_RECOVER_COOLDOWN_SEC = 600
PROFILE_HTTP_CACHE_MAX_BYTES = 48 * 1024 * 1024
SIDEBAR_SMALL_BTN_W = 52
SIDEBAR_SMALL_BTN_H = 26
SIDEBAR_DEFAULT_WIDTH = 270
SIDEBAR_COLLAPSE_AT = 24
SIDEBAR_EXPAND_AT = 56
SIDEBAR_EXPAND_STRIP_W = 10
GROUP_SIDEBAR_ANIM_MS = 220
DAILY_CACHE_CLEAN_HOUR = 7
LOGIN_TIMEOUT_SEC = 300
LOGIN_VERIFY_MIN_SEC = 0
LOGIN_VERIFY_REQUIRED_HITS = 2
MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024

PROFILE_CACHE_DIRS = [
    "Cache", "Code Cache", "GPUCache", "DawnCache", "DawnGraphiteCache",
    "DawnWebGPUCache", "GrShaderCache", "ShaderCache", "GraphiteDawnCache",
    "Service Worker/CacheStorage", "Service Worker/ScriptCache",
    "blob_storage", "Media Cache", "VideoDecodeStats",
    "optimization_guide_model_store", "component_crx_cache",
    "extensions_crx_cache", "BrowserMetrics", "Crashpad",
    "hyphen-data", "Safe Browsing",
    # WebView2 / Edge 可安全删除的附加缓存（不动 Cookies / Local Storage / IndexedDB）
    "Download Service", "Shared Dictionary", "Network Action Predictor",
    "Favicons", "Top Sites", "Visited Links", "JumpListIconsRecentClosed",
    "WebAssistDatabase", "AutofillAiModelCache", "BudgetDatabase",
    "EdgeEDrop", "EntityExtraction", "Nurturing",
    "Platform Notifications", "Notification Resources", "Notification State",
    "SharedStorage", "History",
]

def _make_dot_icon(color: str, size: int = 14) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    margin = max(1, size // 7)
    p.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    p.end()
    return QIcon(pix)


def _bridge_connect_js_source() -> str:
    """QWebChannel 桥接（须在 MainWorld，与 qt.webChannelTransport 同域）"""
    return """
    window.connectTeamsBridge = function connectTeamsBridge() {
        if (typeof qt === 'undefined' || !qt.webChannelTransport) {
            setTimeout(connectTeamsBridge, 100);
            return;
        }
        if (typeof QWebChannel === 'undefined') {
            setTimeout(connectTeamsBridge, 150);
            return;
        }
        if (window.__teamsBridgeReady) return;
        new QWebChannel(qt.webChannelTransport, function(channel) {
            var bridge = channel.objects.notifyBridge;
            if (!bridge) {
                setTimeout(connectTeamsBridge, 200);
                return;
            }
            window.__teamsBridgeReady = true;
            window.__externalNotificationCallback = function(type, sender, content, count) {
                // 通知关闭时：仍同步角标；来电/挂断始终上报（由 Python 决定是否响铃弹窗）
                const t = String(type || 'unread');
                const always = (
                    t === 'unread' || t === 'incoming_call' || t === 'incoming_video'
                    || t === 'call_end'
                );
                if (window.__TEAMS_NOTIFICATIONS_OFF && !always) return;
                try {
                    bridge.post(String(type||'unread'), String(sender||''),
                        String(content!=null?content:''), parseInt(count,10)||0);
                } catch(e) {}
            };
            window.__teamsCopyImageToClipboard = function(dataUrl) {
                try { bridge.copyImageDataUrl(String(dataUrl)); } catch(e) {}
            };
            window.__teamsCopyImageUrl = function(url) {
                try { bridge.copyImageUrl(String(url)); } catch(e) {}
            };
            window.__teamsCacheNotifySoundUrl = function(url) {
                try { bridge.cacheNotifySoundUrl(String(url || '')); } catch(e) {}
            };
            if (window.__teamsSyncBadgeFromTitle) window.__teamsSyncBadgeFromTitle();
        });
    };
    window.connectTeamsBridge();
    """


def account_status_icon(display_status: str) -> QIcon:
    global _ICON_OK, _ICON_FAIL, _ICON_SLEEP
    if _ICON_OK is None:
        _ICON_OK = _make_dot_icon("#22c55e", 16)
        _ICON_SLEEP = _make_dot_icon("#f5b82e", 16)
        _ICON_FAIL = _make_dot_icon("#ff5252", 16)
    if display_status == DISPLAY_ACTIVE:
        return _ICON_OK
    if display_status == DISPLAY_SLEEP:
        return _ICON_SLEEP
    return _ICON_FAIL


class AppPaths:
    """数据目录：优先 D:\\TeamsX；无 D 盘时回退到 %LOCALAPPDATA%\\TeamsX。可用 TEAMSX_DATA_ROOT 覆盖。"""

    try:
        from teamsx.config import DATA_ROOT as DATA_ROOT
    except ImportError:
        DATA_ROOT = _TEAMS_DATA_ROOT_EARLY

    @classmethod
    def data_root(cls) -> str:
        try:
            os.makedirs(cls.DATA_ROOT, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"无法创建数据目录 {cls.DATA_ROOT}: {e}")
        return cls.DATA_ROOT

    @classmethod
    def db_dir(cls) -> str:
        path = os.path.join(cls.data_root(), "db")
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def db_file(cls) -> str:
        return os.path.join(cls.db_dir(), "teams_accounts.db")

    @classmethod
    def _app_resource_bases(cls) -> List[str]:
        """源码：脚本目录；打包：exe 旁优先，其次 _MEIPASS。"""
        bases: List[str] = []
        if getattr(sys, "frozen", False):
            bases.append(os.path.dirname(os.path.abspath(sys.executable)))
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                bases.append(meipass)
        else:
            bases.append(os.path.dirname(os.path.abspath(__file__)))
        return bases

    @classmethod
    def teams_notify_official(cls) -> str:
        rel = os.path.join(TEAMS_NOTIFY_AUDIO_DIR, TEAMS_NOTIFY_OFFICIAL_BASENAME)
        for base in cls._app_resource_bases():
            path = os.path.join(base, rel)
            if os.path.isfile(path):
                return path
        return os.path.join(cls._app_resource_bases()[0], rel)

    @classmethod
    def teams_call_notify(cls) -> str:
        rel = os.path.join(TEAMS_NOTIFY_AUDIO_DIR, TEAMS_CALL_NOTIFY_BASENAME)
        for base in cls._app_resource_bases():
            path = os.path.join(base, rel)
            if os.path.isfile(path):
                return path
        return os.path.join(cls._app_resource_bases()[0], rel)

    @classmethod
    def app_icon(cls) -> str:
        for base in cls._app_resource_bases():
            path = os.path.join(base, "logo.ico")
            if os.path.isfile(path):
                return path
        return ""

    @classmethod
    def app_qicon(cls) -> QIcon:
        """应用图标：logo.ico → 打包 exe 内嵌图标 → 空。"""
        path = cls.app_icon()
        if path:
            icon = QIcon(path)
            if not icon.isNull():
                return icon
        if getattr(sys, "frozen", False):
            exe_icon = QIcon(os.path.abspath(sys.executable))
            if not exe_icon.isNull():
                return exe_icon
        return QIcon()

    @classmethod
    def profiles_root(cls) -> str:
        path = os.path.join(cls.data_root(), "profiles")
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def cache_root(cls) -> str:
        path = os.path.join(cls.data_root(), "cache")
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def accounts_txt(cls) -> str:
        return os.path.join(cls.data_root(), ACCOUNTS_TXT_NAME)

    @classmethod
    def shared_webview2_user_data(cls) -> str:
        """所有账号共享的 WebView2 UserDataFolder（多 Profile 单浏览器进程）。"""
        path = os.path.join(cls.profiles_root(), "_shared_webview2")
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def account_dirs(cls, remark: str, account_id: int) -> Tuple[str, str]:
        # 路径仅按账号 ID，改备注不会换目录、不会丢登录态
        folder = f"account_{account_id}"
        session_dir = os.path.join(cls.profiles_root(), folder, "session")
        cache_dir = os.path.join(cls.cache_root(), folder)
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)
        return session_dir, cache_dir


def _dir_size(path: str) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def clean_profile_cache(user_data_dir: str) -> Tuple[int, int]:
    """清理 session 目录内的浏览器缓存子目录，保留 Cookies 等登录数据。"""
    if not user_data_dir or not os.path.isdir(user_data_dir):
        return 0, 0
    removed = 0
    freed = 0
    for name in PROFILE_CACHE_DIRS:
        path = os.path.join(user_data_dir, name)
        if not os.path.exists(path):
            continue
        try:
            if os.path.isdir(path):
                freed += _dir_size(path)
                shutil.rmtree(path, ignore_errors=True)
            else:
                freed += os.path.getsize(path)
                os.remove(path)
            removed += 1
        except OSError as e:
            print(f"清理缓存跳过 {path}: {e}")
    return removed, freed


def clear_account_cache_dir(cache_dir: str) -> int:
    """删除并重建独立 cache 目录，返回约释放字节数。"""
    if not cache_dir:
        return 0
    freed = 0
    if os.path.isdir(cache_dir):
        freed = _dir_size(cache_dir)
        shutil.rmtree(cache_dir, ignore_errors=True)
    os.makedirs(cache_dir, exist_ok=True)
    return freed


def clean_orphan_cache_dirs(valid_cache_dirs: Set[str]) -> int:
    """删除 cache 根目录下已无账号引用的孤立文件夹。"""
    cache_root = os.path.normpath(AppPaths.cache_root())
    freed = 0
    if not os.path.isdir(cache_root):
        return 0
    try:
        for name in os.listdir(cache_root):
            path = os.path.normpath(os.path.join(cache_root, name))
            if path in valid_cache_dirs:
                continue
            if os.path.isdir(path):
                freed += _dir_size(path)
                shutil.rmtree(path, ignore_errors=True)
    except OSError as e:
        print(f"清理孤立缓存目录错误: {e}")
    return freed


class CacheCleanWorker(QObject):
    """后台清理缓存，避免阻塞 UI"""

    finished = pyqtSignal(str, int)
    failed = pyqtSignal(str)

    def __init__(
        self,
        accounts: List[Tuple],
        cache_root: str,
        skip_session_dirs: Optional[Set[str]] = None,
        skip_cache_dirs: Optional[Set[str]] = None,
    ):
        super().__init__()
        self._accounts = accounts
        self._cache_root = os.path.normpath(cache_root)
        self._valid_cache_dirs: Set[str] = set()
        self._skip_session_dirs = skip_session_dirs or set()
        self._skip_cache_dirs = skip_cache_dirs or set()

    def run(self):
        total_freed = 0
        count = 0
        try:
            for acc in self._accounts:
                session_dir = acc[2] if len(acc) > 2 else None
                cache_dir = acc[3] if len(acc) > 3 else None
                acc_freed = 0
                if cache_dir:
                    normalized = os.path.normpath(os.path.abspath(cache_dir))
                    if normalized.startswith(self._cache_root):
                        self._valid_cache_dirs.add(normalized)
                        if normalized not in self._skip_cache_dirs:
                            acc_freed += clear_account_cache_dir(cache_dir)
                if session_dir:
                    norm_session = os.path.normpath(os.path.abspath(session_dir))
                    if norm_session not in self._skip_session_dirs:
                        _removed, freed = clean_profile_cache(session_dir)
                        acc_freed += freed
                if acc_freed > 0:
                    count += 1
                    total_freed += acc_freed
            total_freed += clean_orphan_cache_dirs(self._valid_cache_dirs)
            msg = (
                f"已清理 {count} 个账号的浏览器磁盘缓存，释放约 {format_bytes(total_freed)}。\n"
                f"登录态（Cookies / Local Storage）已保留，无需重新登录。"
            )
            self.finished.emit(msg, total_freed)
        except Exception as e:
            self.failed.emit(str(e))


def parse_account_blocks(text: str) -> List[Dict[str, str]]:
    """解析 B/Z/M 格式账号块。B=备注 Z=账号 M/N=密码，空行分隔多条。"""
    key_map = {
        "b": "remark", "z": "email", "m": "password", "n": "password",
        "备注": "remark", "账号": "email", "密码": "password",
        "remark": "remark", "email": "email", "password": "password",
    }
    accounts: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    def normalize_value(field: str, value: str) -> str:
        value = (value or "").strip()
        if field in ("email", "password"):
            # 导入文件里 Z/M 行常因复制粘贴混入半角/全角空格、制表符等，
            # 这些不应作为账号或密码的一部分参与登录。
            return re.sub(r"[\s\u00a0\u3000]+", "", value)
        return value

    def flush():
        nonlocal current
        if current.get("remark") or current.get("email"):
            accounts.append(dict(current))
        current = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        parts = re.split(r"[:：]", line, maxsplit=1)
        if len(parts) < 2:
            continue
        key = parts[0].strip().lower()
        field = key_map.get(key) or key_map.get(parts[0].strip())
        val = normalize_value(field or "", parts[1])
        if field and val:
            current[field] = val
    flush()
    return accounts


def format_account_block(remark: str, email: str = "", password: str = "") -> str:
    """单条 B/Z/M 账号块（与导入格式一致）"""
    lines = [f"B：{remark.strip()}"]
    em = (email or "").strip()
    pw = (password or "").strip()
    if em:
        lines.append(f"Z：{em}")
    if pw:
        lines.append(f"M：{pw}")
    return "\n".join(lines)


_REMARK_SORT_FN = None


def _init_remark_sort_fn():
    """微信式排序：按备注首字拼音/字母分组（A-Z、0-9、#）"""
    global _REMARK_SORT_FN
    if _REMARK_SORT_FN is not None:
        return _REMARK_SORT_FN
    try:
        from pypinyin import Style, lazy_pinyin

        def _pinyin_key(text: str) -> str:
            letters = lazy_pinyin(text, style=Style.FIRST_LETTER)
            return "".join((x or "#").upper() for x in letters)

        _REMARK_SORT_FN = _pinyin_key
        return _REMARK_SORT_FN
    except ImportError:
        pass
    for loc in (
        "Chinese_China.65001",
        "Chinese_China.936",
        "Chinese (Simplified)_China.936",
        "zh_CN.UTF-8",
    ):
        try:
            locale.setlocale(locale.LC_COLLATE, loc)

            def _locale_key(text: str) -> str:
                return locale.strxfrm(text)

            _REMARK_SORT_FN = _locale_key
            return _REMARK_SORT_FN
        except locale.Error:
            continue
    _REMARK_SORT_FN = lambda text: text.lower()
    return _REMARK_SORT_FN


def remark_sort_key(remark: str) -> Tuple:
    """微信好友式：# → 数字 → A-Z（中文按拼音首字母，如 阿→A）"""
    s = (remark or "").strip()
    if s.startswith("📌"):
        s = s.lstrip("📌").strip()
    if not s:
        return (9, "", "")
    sort_fn = _init_remark_sort_fn()
    py = sort_fn(s)
    ch = s[0]
    if ch.isdigit():
        return (1, py, s)
    if ch.isascii() and ch.isalpha():
        return (0, ch.upper() + s.lower(), s.lower())
    if ch.isascii():
        return (2, py, s)
    return (0, py, s)


def read_accounts_txt_content() -> str:
    path = AppPaths.accounts_txt()
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"读取账号备份文件失败: {e}")
        return ""


def write_accounts_txt_from_blocks(blocks: List[Dict[str, str]]):
    path = AppPaths.accounts_txt()
    parts = [
        format_account_block(
            b.get("remark", ""),
            b.get("email", ""),
            b.get("password", ""),
        )
        for b in blocks
        if (b.get("remark") or b.get("email"))
    ]
    text = ("\n\n".join(parts) + "\n") if parts else ""
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except OSError as e:
        print(f"写入账号备份文件失败: {e}")


def upsert_account_in_accounts_txt(remark: str, email: str = "", password: str = ""):
    """将账号写入 D:\\TeamsX\\accounts.txt，便于换设备导入"""
    blocks = parse_account_blocks(read_accounts_txt_content())
    email_key = (email or "").strip().lower()
    remark_key = (remark or "").strip()
    new_block = {
        "remark": remark_key,
        "email": (email or "").strip(),
        "password": (password or "").strip(),
    }
    updated = False
    for i, b in enumerate(blocks):
        be = (b.get("email") or "").strip().lower()
        br = (b.get("remark") or "").strip()
        if email_key and be == email_key:
            blocks[i] = new_block
            updated = True
            break
        if not email_key and br == remark_key:
            blocks[i] = new_block
            updated = True
            break
    if not updated:
        blocks.append(new_block)
    write_accounts_txt_from_blocks(blocks)


def remove_account_from_accounts_txt(email: str = "", remark: str = ""):
    blocks = parse_account_blocks(read_accounts_txt_content())
    email_key = (email or "").strip().lower()
    remark_key = (remark or "").strip()
    kept = []
    for b in blocks:
        be = (b.get("email") or "").strip().lower()
        br = (b.get("remark") or "").strip()
        if email_key and be == email_key:
            continue
        if not email_key and remark_key and br == remark_key:
            continue
        kept.append(b)
    write_accounts_txt_from_blocks(kept)


# ==================== 工具类 ====================

class SafeDict(dict):
    """线程安全的字典"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)

    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)

    def pop(self, key, *args):
        with self._lock:
            return super().pop(key, *args)

    def clear(self):
        with self._lock:
            super().clear()

class WebViewPool:
    """WebView 池管理器 - 控制活跃 WebView 数量"""
    def __init__(self):
        self.views: Dict[int, dict] = {}  # account_id -> {view, last_used, active, use_count}
        self._lock = threading.Lock()

    def get(self, account_id: int) -> Optional[dict]:
        """获取 WebView 信息"""
        with self._lock:
            return self.views.get(account_id)

    def register(self, account_id: int, web_view):
        """注册 WebView"""
        with self._lock:
            self.views[account_id] = {
                'view': web_view,
                'last_used': time.time(),
                'active': True,
                'use_count': int(self.views.get(account_id, {}).get("use_count", 0)),
            }

    def mark_used(self, account_id: int):
        """记录一次使用（LFU）并更新最后使用时间（LRU）"""
        with self._lock:
            if account_id in self.views:
                self.views[account_id]['last_used'] = time.time()
                self.views[account_id]['active'] = True
                self.views[account_id]['use_count'] = int(self.views[account_id].get("use_count", 0)) + 1

    def deactivate(self, account_id: int):
        """标记 WebView 为非活跃"""
        with self._lock:
            if account_id in self.views:
                self.views[account_id]['active'] = False

    def remove(self, account_id: int):
        """移除 WebView"""
        with self._lock:
            return self.views.pop(account_id, None)

    def get_lfu_lru_account(self, exclude: Optional[Set[int]] = None) -> Optional[int]:
        """最不常用账号（use_count 最少）；并列时取 last_used 最早（LRU）。"""
        exclude = exclude or set()
        with self._lock:
            candidates = []
            for acc_id, info in self.views.items():
                if acc_id in exclude:
                    continue
                use_count = int(info.get("use_count", 0))
                last_used = float(info.get("last_used", 0.0) or 0.0)
                candidates.append((use_count, last_used, acc_id))
            if not candidates:
                return None
            candidates.sort(key=lambda x: (x[0], x[1]))
            return candidates[0][2]

    def clear(self):
        """清空池"""
        with self._lock:
            self.views.clear()

# ==================== UI 组件 ====================

class AccountListDelegate(QStyledItemDelegate):
    """账号列表：左侧状态点 + 备注 + 右侧红色未读角标"""

    BADGE_W = 22
    BADGE_H = 18

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        colors = list_delegate_colors()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        pill = QRectF(rect).adjusted(6, 3, -6, -3)
        radius = 9.0
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["bg_sel"]))
            painter.drawRoundedRect(pill, radius, radius)
            border = colors.get("bg_sel_border")
            if border:
                pen = QPen(QColor(border))
                pen.setWidthF(1.2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(pill.adjusted(0.6, 0.6, -0.6, -0.6), radius, radius)
        elif hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["bg_hover"]))
            painter.drawRoundedRect(pill, radius, radius)

        count = int(index.data(BADGE_COUNT_ROLE) or 0)
        remark = index.data(REMARK_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        is_pinned = bool(index.data(PIN_ROLE))
        prefix = "📌 " if is_pinned else ""
        label = f"{prefix}{remark}"

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        text_left = rect.left() + 10
        if icon and not icon.isNull():
            icon_sz = 16
            iy = rect.top() + (rect.height() - icon_sz) // 2
            icon.paint(painter, QRect(text_left, iy, icon_sz, icon_sz))
            text_left += icon_sz + 8

        badge_reserve = self.BADGE_W + 16 if count > 0 else 8
        text_rect = QRect(text_left, rect.top(), rect.width() - text_left - badge_reserve, rect.height())
        painter.setPen(QColor(colors["text_sel"] if selected else colors["text"]))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        elided = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        if count > 0:
            badge_text = "99+" if count > 99 else str(count)
            fm = painter.fontMetrics()
            bw = max(self.BADGE_W, fm.horizontalAdvance(badge_text) + 12)
            bh = self.BADGE_H
            bx = rect.right() - bw - 10
            by = rect.top() + (rect.height() - bh) // 2
            badge_rect = QRect(bx, by, bw, bh)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(BADGE_RED_HOVER if selected else BADGE_RED))
            painter.drawRoundedRect(badge_rect, bh // 2, bh // 2)
            painter.setPen(QColor("#ffffff"))
            font.setBold(True)
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width() if option.rect.width() > 0 else 200, 46)


class AccountListWidget(QListWidget):
    """账号列表（自动排序，不支持手动拖动）"""

    orderChanged = pyqtSignal()
    _WHEEL_ANGLE_TO_PX = 46.0 / 120.0  # 约一行高度 / 标准滚轮刻度
    _WHEEL_ANIM_MS = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDragEnabled(False)
        self.setDropIndicatorShown(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        bar = self.verticalScrollBar()
        bar.setSingleStep(10)
        bar.setPageStep(180)
        self._block_order_signal = False
        self._press_pos: Optional[QPoint] = None
        self._drag_started = False
        self._wheel_anim: Optional[QPropertyAnimation] = None

    def _wheel_pixel_delta(self, event) -> float:
        pixel = event.pixelDelta().y()
        if pixel != 0:
            return -float(pixel)
        angle = event.angleDelta().y()
        if angle == 0:
            return 0.0
        return -float(angle) * self._WHEEL_ANGLE_TO_PX

    def _animate_scroll_by(self, delta: float) -> None:
        bar = self.verticalScrollBar()
        if self._wheel_anim is not None and self._wheel_anim.state() == QAbstractAnimation.State.Running:
            base = int(self._wheel_anim.endValue())
        else:
            base = bar.value()
        target = max(bar.minimum(), min(bar.maximum(), int(base + delta)))
        if target == bar.value():
            return
        if self._wheel_anim is None:
            self._wheel_anim = QPropertyAnimation(bar, b"value", self)
            self._wheel_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._wheel_anim.stop()
        self._wheel_anim.setDuration(self._WHEEL_ANIM_MS)
        self._wheel_anim.setStartValue(bar.value())
        self._wheel_anim.setEndValue(target)
        self._wheel_anim.start()

    def wheelEvent(self, event):
        delta = self._wheel_pixel_delta(event)
        if delta == 0.0:
            event.ignore()
            return
        # 触控板 pixelDelta 本身已连续，直接跟手；鼠标滚轮刻度用缓动动画
        if event.pixelDelta().y() != 0:
            bar = self.verticalScrollBar()
            if self._wheel_anim is not None:
                self._wheel_anim.stop()
            bar.setValue(
                max(bar.minimum(), min(bar.maximum(), bar.value() + int(delta)))
            )
        else:
            self._animate_scroll_by(delta)
        event.accept()

    def mousePressEvent(self, event):
        self._press_pos = event.position().toPoint()
        self._drag_started = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 仅允许上下拖动排序：按住左键左右滑动不触发任何拖动/位移
        if event.buttons() & Qt.MouseButton.LeftButton and self._press_pos is not None:
            pos = event.position().toPoint()
            dx = abs(pos.x() - self._press_pos.x())
            dy = abs(pos.y() - self._press_pos.y())
            if not self._drag_started:
                # 横向优先则忽略（不触发 InternalMove）
                if dx > dy and dx >= QApplication.startDragDistance():
                    event.ignore()
                    return
                if dy >= QApplication.startDragDistance():
                    self._drag_started = True
        super().mouseMoveEvent(event)

    def dropEvent(self, event):
        super().dropEvent(event)
        if not self._block_order_signal:
            self.orderChanged.emit()


class SidebarContentHost(QWidget):
    """账号列表与分组管理叠放，切换时做淡入淡出。"""

    def __init__(self, account_list: QListWidget, group_panel: QWidget, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._account = account_list
        self._group = group_panel
        account_list.setParent(self)
        group_panel.setParent(self)
        account_list.show()
        group_panel.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._account.setGeometry(rect)
        self._group.setGeometry(rect)


class _GroupComboCenterDelegate(QStyledItemDelegate):
    """下拉列表项文字居中。"""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter


class GroupFilterComboBox(QComboBox):
    """分组下拉：左键按下切换展开/收起。

    须在 mouseRelease 吞掉左键，否则 Qt 在松开时又 showPopup，会把内部状态弄乱，
    表现为「收起后再点第一下没反应、要两下才展开」。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(False)
        self.setItemDelegate(_GroupComboCenterDelegate(self))
        self._was_open = False

    def _is_popup_visible(self) -> bool:
        try:
            view = self.view()
            if view is None:
                return False
            win = view.window()
            return bool(win and win.isVisible() and view.isVisible())
        except Exception:
            return False

    def hidePopup(self) -> None:
        self._was_open = False
        super().hidePopup()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            should_close = self._was_open or self._is_popup_visible()
            if should_close:
                self._was_open = False
                if self._is_popup_visible():
                    QComboBox.hidePopup(self)
            else:
                self._was_open = True
                QComboBox.showPopup(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        label = opt.currentText
        opt.currentText = ""
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        if label:
            edit_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_ComboBox,
                opt,
                QStyle.SubControl.SC_ComboBoxEditField,
                self,
            )
            painter.drawText(edit_rect, int(Qt.AlignmentFlag.AlignCenter), label)


class TitleBrandLabel(QLabel):
    """标题栏品牌文字，点击切换主题"""
    clicked = pyqtSignal()

    def __init__(self, text: str = "TeamsX", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ShadowContainer(QWidget):
    """承载主框的容器，在四周留白处手绘柔和阴影（替代 QGraphicsDropShadowEffect，
    避免与原生 WebView2 子窗口冲突，也避免顶部出现一条灰线）。"""

    def __init__(self, margin: int, radius: int, parent=None):
        super().__init__(parent)
        self._margin = margin
        self._radius = radius
        self._show_shadow = True
        self._color = QColor(0, 0, 0, 38)

    def configure(self, margin: int, show_shadow: bool, color: QColor) -> None:
        self._margin = margin
        self._show_shadow = show_shadow
        self._color = color
        self.update()

    def paintEvent(self, event):
        if not self._show_shadow or self._margin <= 0:
            return
        m = self._margin
        inner = QRectF(self.rect()).adjusted(m, m, -m, -m)
        if inner.width() <= 0 or inner.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        base_alpha = self._color.alpha()
        for i in range(m, 0, -1):
            t = i / m
            alpha = int(base_alpha * (1.0 - t) ** 1.8)
            if alpha <= 0:
                continue
            c = QColor(self._color)
            c.setAlpha(alpha)
            painter.setBrush(c)
            ring = inner.adjusted(-i, -i, i, i)
            rad = self._radius + i
            painter.drawRoundedRect(ring, rad, rad)
        painter.end()


class TitleBarControlButton(QWidget):
    """标题栏窗口控制键：自绘图标 + 悬停/离开动作动画。"""

    KIND_MIN = "min"
    KIND_MAX = "max"
    KIND_CLOSE = "close"

    clicked = pyqtSignal()

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._light = False
        self._maximized = False
        self._pressed = False
        self._rotation = 0.0
        self._offset_y = 0.0
        self._icon_scale = 1.0
        self._motion_anim = None
        self._hovered = False
        self.setFixedSize(46, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_theme_light(self, light: bool) -> None:
        self._light = bool(light)
        self.update()

    def set_maximized(self, maximized: bool) -> None:
        if self._kind != self.KIND_MAX:
            return
        self._maximized = bool(maximized)
        self.update()

    def get_icon_rotation(self) -> float:
        return self._rotation

    def set_icon_rotation(self, value: float) -> None:
        self._rotation = float(value)
        self.update()

    icon_rotation = pyqtProperty(float, get_icon_rotation, set_icon_rotation)

    def get_icon_offset_y(self) -> float:
        return self._offset_y

    def set_icon_offset_y(self, value: float) -> None:
        self._offset_y = float(value)
        self.update()

    icon_offset_y = pyqtProperty(float, get_icon_offset_y, set_icon_offset_y)

    def get_icon_scale(self) -> float:
        return self._icon_scale

    def set_icon_scale(self, value: float) -> None:
        self._icon_scale = max(0.5, float(value))
        self.update()

    icon_scale = pyqtProperty(float, get_icon_scale, set_icon_scale)

    def _stop_motion_anim(self) -> None:
        if self._motion_anim is not None:
            self._motion_anim.stop()

    def _current_motion_value(self, prop: bytes) -> float:
        if prop == b"icon_rotation":
            return self._rotation
        if prop == b"icon_offset_y":
            return self._offset_y
        return self._icon_scale

    def _animate_motion(
        self,
        targets: Dict[str, float],
        duration: int,
        *,
        easing_in: bool = True,
    ) -> None:
        self._stop_motion_anim()
        easing = (
            QEasingCurve.Type.OutCubic
            if easing_in
            else QEasingCurve.Type.InOutCubic
        )
        if len(targets) == 1:
            prop_name, end = next(iter(targets.items()))
            prop = prop_name.encode()
            anim = QPropertyAnimation(self, prop, self)
            anim.setDuration(duration)
            anim.setStartValue(self._current_motion_value(prop))
            anim.setEndValue(end)
            anim.setEasingCurve(easing)
            self._motion_anim = anim
            anim.start()
            return
        group = QParallelAnimationGroup(self)
        for prop_name, end in targets.items():
            prop = prop_name.encode()
            anim = QPropertyAnimation(self, prop, self)
            anim.setDuration(duration)
            anim.setStartValue(self._current_motion_value(prop))
            anim.setEndValue(end)
            anim.setEasingCurve(easing)
            group.addAnimation(anim)
        self._motion_anim = group
        group.start()

    def _icon_color(self) -> QColor:
        if self._hovered and self._kind == self.KIND_CLOSE:
            return QColor(255, 255, 255)
        return QColor(50, 50, 50) if self._light else QColor(224, 224, 224)

    def _hover_bg_color(self) -> Optional[QColor]:
        if not self._hovered:
            return None
        if self._kind == self.KIND_CLOSE:
            return QColor(232, 17, 35)
        return QColor(225, 225, 225) if self._light else QColor(64, 64, 64)

    def _play_hover_motion(self) -> None:
        if self._kind == self.KIND_CLOSE:
            self._animate_motion({"icon_rotation": self._rotation + 180.0}, 520)
        elif self._kind == self.KIND_MIN:
            self._animate_motion(
                {"icon_offset_y": 8.0, "icon_scale": 0.78},
                340,
            )
        else:
            self._animate_motion({"icon_rotation": 90.0}, 380)

    def _play_leave_motion(self) -> None:
        if self._kind == self.KIND_CLOSE:
            self._animate_motion({"icon_rotation": 0.0}, 420, easing_in=False)
        elif self._kind == self.KIND_MIN:
            self._animate_motion(
                {"icon_offset_y": 0.0, "icon_scale": 1.0},
                300,
                easing_in=False,
            )
        else:
            self._animate_motion({"icon_rotation": 0.0}, 340, easing_in=False)

    def _draw_min_icon(self, painter: QPainter) -> None:
        painter.drawLine(QPointF(-5, 0), QPointF(5, 0))

    def _draw_max_icon(self, painter: QPainter) -> None:
        if self._maximized:
            painter.drawRect(QRectF(-1, -5, 8, 8))
            painter.drawRect(QRectF(-5, -1, 8, 8))
        else:
            painter.drawRect(QRectF(-5, -5, 10, 10))

    def _draw_close_icon(self, painter: QPainter) -> None:
        painter.drawLine(QPointF(-5, -5), QPointF(5, 5))
        painter.drawLine(QPointF(5, -5), QPointF(-5, 5))

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg = self._hover_bg_color()
        if bg is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(4, 5, -4, -5), 6, 6)
        cx = self.width() * 0.5
        cy = self.height() * 0.5
        scale = self._icon_scale
        if self._pressed:
            scale *= 0.88
        painter.save()
        painter.translate(cx, cy + self._offset_y)
        painter.rotate(self._rotation)
        painter.scale(scale, scale)
        pen = QPen(self._icon_color())
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._kind == self.KIND_MIN:
            self._draw_min_icon(painter)
        elif self._kind == self.KIND_MAX:
            self._draw_max_icon(painter)
        else:
            self._draw_close_icon(painter)
        painter.restore()
        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self._play_hover_motion()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self._play_leave_motion()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_pressed = self._pressed
            self._pressed = False
            self.update()
            if was_pressed and self.rect().contains(event.position().toPoint()):
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class GearMenuButton(QWidget):
    """齿轮工具按钮：点击时旋转并发出信号（用于弹出工具菜单）。"""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._light = False
        self._rotation = 0.0
        self._hovered = False
        self._pressed = False
        self._spin_anim = None
        self.setFixedSize(44, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_theme_light(self, light: bool) -> None:
        self._light = bool(light)
        self.update()

    def get_rotation(self) -> float:
        return self._rotation

    def set_rotation(self, value: float) -> None:
        self._rotation = float(value)
        self.update()

    rotation = pyqtProperty(float, get_rotation, set_rotation)

    def animate_to(self, angle: float) -> None:
        if self._spin_anim is not None:
            self._spin_anim.stop()
        anim = QPropertyAnimation(self, b"rotation", self)
        anim.setDuration(440)
        anim.setStartValue(self._rotation)
        anim.setEndValue(float(angle))
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._spin_anim = anim
        anim.start()

    def _icon_color(self) -> QColor:
        return QColor(70, 70, 70) if self._light else QColor(224, 224, 224)

    def _hover_bg(self) -> Optional[QColor]:
        if not self._hovered:
            return None
        return QColor(0, 0, 0, 28) if self._light else QColor(255, 255, 255, 30)

    def _gear_path(self) -> QPainterPath:
        """完整齿轮轮廓：梯形齿环 + 中心镂空（而非放射状细条，避免像太阳）。"""
        n = 8
        r_tip = 10.0
        r_root = 7.4
        half_tip = math.radians(9.0)
        half_root = math.radians(17.0)
        step = 2.0 * math.pi / n
        path = QPainterPath()
        first = True
        for i in range(n):
            c = i * step
            for ang, r in (
                (c - half_root, r_root),
                (c - half_tip, r_tip),
                (c + half_tip, r_tip),
                (c + half_root, r_root),
            ):
                x = r * math.cos(ang)
                y = r * math.sin(ang)
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
        path.closeSubpath()
        path.addEllipse(QPointF(0, 0), 3.8, 3.8)
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return path

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg = self._hover_bg()
        if bg is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(3, 3, -3, -3), 6, 6
            )
        cx = self.width() * 0.5
        cy = self.height() * 0.5
        scale = 0.9 if self._pressed else 1.0
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._rotation)
        painter.scale(scale, scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillPath(self._gear_path(), self._icon_color())
        painter.restore()
        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was = self._pressed
            self._pressed = False
            self.update()
            if was and self.rect().contains(event.position().toPoint()):
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CustomTitleBar(QWidget):
    """自定义无边框窗口标题栏"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFixedHeight(38)
        self._light = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 0, 0)
        layout.setSpacing(0)
        self.title_label = TitleBrandLabel("TeamsX")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; border: none; background: transparent;")
        layout.addWidget(self.title_label)
        layout.addStretch()
        self.min_btn = TitleBarControlButton(TitleBarControlButton.KIND_MIN, self)
        self.max_btn = TitleBarControlButton(TitleBarControlButton.KIND_MAX, self)
        self.close_btn = TitleBarControlButton(TitleBarControlButton.KIND_CLOSE, self)
        self.close_btn.setObjectName("CloseBtn")
        for btn in (self.min_btn, self.max_btn, self.close_btn):
            layout.addWidget(btn)
        self.is_maximized = False
        self._expanded = False
        self.apply_bar_theme(False)
        # 事件绑定
        self.min_btn.clicked.connect(self.main_window.animated_minimize)
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.main_window.request_close)
        # 拖拽
        self.dragging = False
        self._system_move = False
        self.drag_start_pos = QPoint()
        self.before_maximize_geometry = None
        self._normal_size = (1280, 800)
        self._reset_drag_timer: Optional[QTimer] = None

    def cancel_drag_state(self):
        """防止 startSystemMove 过程中丢失 mouseRelease 导致标题栏永久不可拖动。"""
        try:
            self.dragging = False
            self._system_move = False
        except Exception:
            pass

    def _can_drag_title(self) -> bool:
        return not self._expanded and not self.main_window.isFullScreen()

    def recheck_expanded_state(self):
        """最小化恢复等系统操作后，按实际窗口尺寸校正展开状态。"""
        try:
            mw = self.main_window
            if mw.isFullScreen():
                return
            screen = QGuiApplication.primaryScreen()
            if not screen:
                return
            ag = screen.availableGeometry()
            g = mw.geometry()
            if g.width() >= ag.width() - 4 and g.height() >= ag.height() - 4:
                self._expanded = True
            elif (
                abs(g.width() - self._normal_size[0]) <= 8
                and abs(g.height() - self._normal_size[1]) <= 8
            ):
                self._expanded = False
            self.is_maximized = self._expanded
            self.max_btn.set_maximized(self._expanded)
        except Exception:
            pass

    def sync_window_state(self):
        """同步按钮状态（避免窗口状态变化后内部标记不同步）。"""
        try:
            self.cancel_drag_state()
            if self.main_window.isFullScreen():
                self._expanded = False
                self.is_maximized = False
                self.max_btn.set_maximized(False)
                return
            self.is_maximized = self._expanded
            self.max_btn.set_maximized(self._expanded)
        except Exception:
            pass

    def apply_bar_theme(self, light: bool):
        self._light = light
        if light:
            self.setStyleSheet(
                "background-color: #f3f3f3; border-bottom: 1px solid #ddd;"
            )
            self.title_label.setStyleSheet(
                "color: #1a1a1a; font-weight: bold; font-size: 14px; border: none; background: transparent;"
            )
        else:
            self.setStyleSheet(
                "background-color: #1e1e1e; border-bottom: 1px solid #333;"
            )
            self.title_label.setStyleSheet(
                "color: #e0e0e0; font-weight: bold; font-size: 14px; border: none; background: transparent;"
            )
        for btn in (self.min_btn, self.max_btn, self.close_btn):
            btn.set_theme_light(light)

    def toggle_maximize(self):
        """
        展开 = 铺满工作区；还原 = 恢复几何与可缩放状态。
        """
        self.cancel_drag_state()
        try:
            self.main_window.end_window_drag()
        except Exception:
            pass
        try:
            if self.main_window.isFullScreen():
                self.main_window.showNormal()
        except Exception:
            pass

        mw = self.main_window

        # 原生窗口：直接用系统 showMaximized/showNormal，最大化/还原动画由 DWM 提供。
        if getattr(mw, "_native_frame", False):
            if mw.isMaximized():
                mw.showNormal()
                self._expanded = False
            else:
                mw.showMaximized()
                self._expanded = True
            self.sync_window_state()
            try:
                if self._reset_drag_timer is None:
                    self._reset_drag_timer = QTimer(self)
                    self._reset_drag_timer.setSingleShot(True)
                    self._reset_drag_timer.timeout.connect(self.cancel_drag_state)
                self._reset_drag_timer.start(200)
            except Exception:
                pass
            return

        target = None
        if self._expanded:
            w, h = self._normal_size
            # 还原后保持可自由缩放：仅恢复最小尺寸，不再锁死最大尺寸
            mw.setMinimumSize(900, 600)
            mw.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
            if self.before_maximize_geometry:
                target = QRect(self.before_maximize_geometry)
            else:
                screen = QGuiApplication.primaryScreen()
                if screen:
                    ag = screen.availableGeometry()
                    target = QRect(
                        ag.x() + max(0, (ag.width() - w) // 2),
                        ag.y() + max(0, (ag.height() - h) // 2),
                        w,
                        h,
                    )
            next_expanded = False
        else:
            self.before_maximize_geometry = mw.geometry()
            self._normal_size = (mw.width(), mw.height())
            screen = QGuiApplication.primaryScreen()
            if screen:
                ag = screen.availableGeometry()
                mw.setMinimumSize(640, 480)
                mw.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
                target = QRect(ag)
            next_expanded = True

        if target is None:
            return

        def _apply_geometry():
            mw.setGeometry(target)
            self._expanded = next_expanded
            self.sync_window_state()
            if hasattr(self.main_window, "_sync_window_shadow_layout"):
                self.main_window._sync_window_shadow_layout()
            try:
                if self._reset_drag_timer is None:
                    self._reset_drag_timer = QTimer(self)
                    self._reset_drag_timer.setSingleShot(True)
                    self._reset_drag_timer.timeout.connect(self.cancel_drag_state)
                self._reset_drag_timer.start(200)
            except Exception:
                pass

        # 直接切换几何，不做透明度淡入淡出（在半透明 WebView2 窗口上会“闪一下”）。
        _apply_geometry()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._can_drag_title():
            win = self.main_window.windowHandle()
            if win is not None:
                try:
                    if win.startSystemMove():
                        self._system_move = True
                        self.main_window.begin_window_drag()
                        event.accept()
                        return
                except Exception:
                    pass
            self.main_window.begin_window_drag()
            self.dragging = True
            self.drag_start_pos = (
                event.globalPosition().toPoint() - self.main_window.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if self._system_move:
            return
        if (
            self.dragging
            and event.buttons() == Qt.MouseButton.LeftButton
            and self._can_drag_title()
        ):
            self.main_window.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging or self._system_move:
                self.main_window.end_window_drag()
            self.dragging = False
            self._system_move = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()
            event.accept()

class EditRemarkDialog(QDialog):
    def __init__(self, current_remark, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑备注")
        self.setModal(True)
        light = bool(getattr(parent, "_theme_light", False)) if parent else False
        self._build_ui(current_remark, light)

    def _build_ui(self, current_remark, light: bool) -> None:
        if light:
            pal = {
                "card_bg": "#ffffff", "card_border": "#e6e8ec", "title": "#1f2329",
                "label": "#5b616b", "input_bg": "#f6f8fb", "input_border": "#dfe3e8",
                "input_focus": "#3b82f6", "input_text": "#1f2329",
                "accent": "#2f6fed", "accent_hover": "#2560d6",
                "ghost_text": "#6b7280", "ghost_border": "#d6dae0", "ghost_hover": "#f0f2f5",
                "shadow_alpha": 60,
            }
        else:
            pal = {
                "card_bg": "#2b2d31", "card_border": "#3a3d42", "title": "#f2f3f5",
                "label": "#aab0b8", "input_bg": "#34373c", "input_border": "#42454a",
                "input_focus": "#5a9cf5", "input_text": "#f2f3f5",
                "accent": "#3b82f6", "accent_hover": "#4a90f0",
                "ghost_text": "#b6bbc2", "ghost_border": "#4a4d52", "ghost_hover": "#3a3d42",
                "shadow_alpha": 130,
            }
        self.setFixedSize(380, 232)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 26)

        card = QFrame()
        card.setObjectName("editRemarkCard")
        card.setStyleSheet(
            f"QFrame#editRemarkCard {{ background: {pal['card_bg']};"
            f"border: 1px solid {pal['card_border']}; border-radius: 18px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, pal["shadow_alpha"]))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(13)

        title = QLabel("编辑备注")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {pal['title']};"
            "border: none; background: transparent;"
        )
        lay.addWidget(title)

        lbl = QLabel("备注")
        lbl.setStyleSheet(
            f"font-size: 12px; color: {pal['label']}; border: none; background: transparent;"
        )
        self.remark_edit = QLineEdit()
        self.remark_edit.setMaxLength(50)
        self.remark_edit.setText(current_remark)
        self.remark_edit.setFixedHeight(36)
        self.remark_edit.setStyleSheet(
            f"QLineEdit {{ background: {pal['input_bg']}; color: {pal['input_text']};"
            f"border: 1px solid {pal['input_border']}; border-radius: 9px;"
            "padding: 7px 10px; font-size: 13px; }"
            f"QLineEdit:focus {{ border: 1px solid {pal['input_focus']}; }}"
        )
        block = QVBoxLayout()
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(4)
        block.addWidget(lbl)
        block.addWidget(self.remark_edit)
        lay.addLayout(block)

        lay.addStretch()
        lay.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(34)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ color: {pal['ghost_text']}; background: transparent;"
            f"border: 1px solid {pal['ghost_border']}; border-radius: 9px;"
            "padding: 5px 16px; font-size: 12px; }"
            f"QPushButton:hover {{ background: {pal['ghost_hover']}; color: {pal['title']}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("确定")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setDefault(True)
        ok_btn.setFixedHeight(34)
        ok_btn.setMinimumWidth(80)
        ok_btn.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: {pal['accent']}; border: none;"
            "border-radius: 9px; padding: 5px 16px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {pal['accent_hover']}; }}"
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        root.addWidget(card)

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent is not None:
            g = parent.frameGeometry()
            self.move(
                g.center().x() - self.width() // 2,
                g.center().y() - self.height() // 2,
            )
        super().showEvent(event)

    def get_remark(self):
        return self.remark_edit.text().strip()

class AddAccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加账号")
        self.setModal(True)
        light = bool(getattr(parent, "_theme_light", False)) if parent else False
        self._build_ui(light)

    def _palette(self, light: bool) -> dict:
        if light:
            return {
                "card_bg": "#ffffff", "card_border": "#e6e8ec",
                "title": "#1f2329", "label": "#5b616b",
                "input_bg": "#f6f8fb", "input_border": "#dfe3e8",
                "input_focus": "#3b82f6", "input_text": "#1f2329",
                "accent": "#2f6fed", "accent_hover": "#2560d6",
                "ghost_text": "#6b7280", "ghost_border": "#d6dae0", "ghost_hover": "#f0f2f5",
                "shadow_alpha": 60,
            }
        return {
            "card_bg": "#2b2d31", "card_border": "#3a3d42",
            "title": "#f2f3f5", "label": "#aab0b8",
            "input_bg": "#34373c", "input_border": "#42454a",
            "input_focus": "#5a9cf5", "input_text": "#f2f3f5",
            "accent": "#3b82f6", "accent_hover": "#4a90f0",
            "ghost_text": "#b6bbc2", "ghost_border": "#4a4d52", "ghost_hover": "#3a3d42",
            "shadow_alpha": 130,
        }

    def _build_ui(self, light: bool) -> None:
        pal = self._palette(light)
        self.setFixedSize(420, 348)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 26)

        card = QFrame()
        card.setObjectName("addAccountCard")
        card.setStyleSheet(
            f"QFrame#addAccountCard {{ background: {pal['card_bg']};"
            f"border: 1px solid {pal['card_border']}; border-radius: 18px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, pal["shadow_alpha"]))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(13)

        title = QLabel("添加账号")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {pal['title']};"
            "border: none; background: transparent;"
        )
        lay.addWidget(title)

        label_css = (
            f"font-size: 12px; color: {pal['label']};"
            "border: none; background: transparent;"
        )
        input_css = (
            f"QLineEdit {{ background: {pal['input_bg']}; color: {pal['input_text']};"
            f"border: 1px solid {pal['input_border']}; border-radius: 9px;"
            "padding: 7px 10px; font-size: 13px; }"
            f"QLineEdit:focus {{ border: 1px solid {pal['input_focus']}; }}"
        )

        self.remark_edit = QLineEdit()
        self.remark_edit.setMaxLength(50)
        self.remark_edit.setPlaceholderText("例如：大河")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("邮箱（可选）")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("密码（可选）")
        for lbl_text, edit in (
            ("备注", self.remark_edit),
            ("账号", self.email_edit),
            ("密码", self.password_edit),
        ):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(label_css)
            edit.setStyleSheet(input_css)
            edit.setFixedHeight(36)
            block = QVBoxLayout()
            block.setContentsMargins(0, 0, 0, 0)
            block.setSpacing(4)
            block.addWidget(lbl)
            block.addWidget(edit)
            lay.addLayout(block)

        lay.addStretch()
        lay.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(34)
        cancel_btn.setMinimumWidth(76)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ color: {pal['ghost_text']}; background: transparent;"
            f"border: 1px solid {pal['ghost_border']}; border-radius: 9px;"
            "padding: 5px 16px; font-size: 12px; }"
            f"QPushButton:hover {{ background: {pal['ghost_hover']}; color: {pal['title']}; }}"
        )
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("确定")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setDefault(True)
        ok_btn.setFixedHeight(34)
        ok_btn.setMinimumWidth(76)
        ok_btn.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: {pal['accent']}; border: none;"
            "border-radius: 9px; padding: 5px 16px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {pal['accent_hover']}; }}"
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        root.addWidget(card)

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent is not None:
            g = parent.frameGeometry()
            self.move(
                g.center().x() - self.width() // 2,
                g.center().y() - self.height() // 2,
            )
        super().showEvent(event)

    def get_remark(self):
        return self.remark_edit.text().strip()

    def get_email(self):
        return self.email_edit.text().strip()

    def get_password(self):
        return self.password_edit.text()


class AccountGroupPickerDialog(QDialog):
    """为单个账号选择分组"""

    def __init__(self, db: "Database", account_id: int, edit_mode: bool, parent=None):
        super().__init__(parent)
        self.db = db
        self.account_id = account_id
        self.edit_mode = edit_mode
        self.setWindowTitle("编辑分组" if edit_mode else "添加到分组")
        self.setModal(True)
        light = bool(getattr(parent, "_theme_light", False)) if parent else False
        self._build_ui(light)

    def _build_ui(self, light: bool) -> None:
        if light:
            pal = {
                "card_bg": "#ffffff", "card_border": "#e6e8ec", "title": "#1f2329",
                "label": "#5b616b", "input_bg": "#f6f8fb", "input_border": "#dfe3e8",
                "input_focus": "#3b82f6", "input_text": "#1f2329", "hint": "#8a9099",
                "accent": "#2f6fed", "accent_hover": "#2560d6",
                "ghost_text": "#6b7280", "ghost_border": "#d6dae0", "ghost_hover": "#f0f2f5",
                "menu_sel": "#eaf2ff", "shadow_alpha": 60,
            }
        else:
            pal = {
                "card_bg": "#2b2d31", "card_border": "#3a3d42", "title": "#f2f3f5",
                "label": "#aab0b8", "input_bg": "#34373c", "input_border": "#42454a",
                "input_focus": "#5a9cf5", "input_text": "#f2f3f5", "hint": "#9aa0a6",
                "accent": "#3b82f6", "accent_hover": "#4a90f0",
                "ghost_text": "#b6bbc2", "ghost_border": "#4a4d52", "ghost_hover": "#3a3d42",
                "menu_sel": "#34507a", "shadow_alpha": 130,
            }
        self.setFixedSize(360, 236)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 26)

        card = QFrame()
        card.setObjectName("groupPickerCard")
        card.setStyleSheet(
            f"QFrame#groupPickerCard {{ background: {pal['card_bg']};"
            f"border: 1px solid {pal['card_border']}; border-radius: 18px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, pal["shadow_alpha"]))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(13)

        title = QLabel("编辑分组" if self.edit_mode else "添加到分组")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {pal['title']};"
            "border: none; background: transparent;"
        )
        lay.addWidget(title)

        lbl = QLabel("选择分组")
        lbl.setStyleSheet(
            f"font-size: 12px; color: {pal['label']}; border: none; background: transparent;"
        )
        self.group_combo = QComboBox()
        self.group_combo.setFixedHeight(36)
        self.group_combo.setStyleSheet(
            f"QComboBox {{ background: {pal['input_bg']}; color: {pal['input_text']};"
            f"border: 1px solid {pal['input_border']}; border-radius: 9px;"
            "padding: 5px 10px; font-size: 13px; }"
            f"QComboBox:focus {{ border: 1px solid {pal['input_focus']}; }}"
            "QComboBox::drop-down { border: none; width: 22px; }"
            f"QComboBox QAbstractItemView {{ background: {pal['card_bg']};"
            f"color: {pal['input_text']}; border: 1px solid {pal['input_border']};"
            f"border-radius: 8px; outline: none; selection-background-color: {pal['menu_sel']}; }}"
        )
        if self.edit_mode:
            self.group_combo.addItem("（移出分组）", 0)
        groups = self.db.get_all_groups()
        for gid, name in groups:
            self.group_combo.addItem(name, gid)
        cur = self.db.get_account_group(self.account_id)
        if cur:
            for i in range(self.group_combo.count()):
                if self.group_combo.itemData(i) == cur[0]:
                    self.group_combo.setCurrentIndex(i)
                    break
        block = QVBoxLayout()
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(4)
        block.addWidget(lbl)
        block.addWidget(self.group_combo)
        lay.addLayout(block)

        if not groups and not self.edit_mode:
            hint = QLabel("请先在「管理」中创建分组")
            hint.setStyleSheet(
                f"font-size: 12px; color: {pal['hint']}; border: none; background: transparent;"
            )
            lay.addWidget(hint)

        lay.addStretch()
        lay.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(34)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ color: {pal['ghost_text']}; background: transparent;"
            f"border: 1px solid {pal['ghost_border']}; border-radius: 9px;"
            "padding: 5px 16px; font-size: 12px; }"
            f"QPushButton:hover {{ background: {pal['ghost_hover']}; color: {pal['title']}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("确定")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setDefault(True)
        ok_btn.setFixedHeight(34)
        ok_btn.setMinimumWidth(80)
        ok_btn.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: {pal['accent']}; border: none;"
            "border-radius: 9px; padding: 5px 16px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {pal['accent_hover']}; }}"
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        root.addWidget(card)

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent is not None:
            g = parent.frameGeometry()
            self.move(
                g.center().x() - self.width() // 2,
                g.center().y() - self.height() // 2,
            )
        super().showEvent(event)

    def selected_group_id(self) -> Optional[int]:
        gid = self.group_combo.currentData()
        if gid in (None, 0):
            return None
        return int(gid)

# ==================== 数据库类 ====================

class Database:
    def __init__(self):
        self.db_file = AppPaths.db_file()
        self._lock = threading.RLock()
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_file, check_same_thread=False, timeout=30)

    def init_db(self):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA cache_size=-10000")
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
                    )
                    if not cursor.fetchone():
                        cursor.execute('''
                        CREATE TABLE accounts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            remark TEXT NOT NULL,
                            user_data_dir TEXT,
                            cache_dir TEXT,
                            email TEXT,
                            password TEXT,
                            login_status TEXT DEFAULT 'pending',
                            is_pinned INTEGER DEFAULT 0,
                            pin_order INTEGER DEFAULT 0,
                            sort_order INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        ''')
                        cursor.execute('CREATE INDEX IF NOT EXISTS idx_remark ON accounts(remark)')
                        cursor.execute(
                            'CREATE INDEX IF NOT EXISTS idx_email ON accounts(email)'
                        )
                    else:
                        cursor.execute("PRAGMA table_info(accounts)")
                        columns = [c[1] for c in cursor.fetchall()]
                        for col, ddl in [
                            ("user_data_dir", "ALTER TABLE accounts ADD COLUMN user_data_dir TEXT"),
                            ("cache_dir", "ALTER TABLE accounts ADD COLUMN cache_dir TEXT"),
                            ("email", "ALTER TABLE accounts ADD COLUMN email TEXT"),
                            ("password", "ALTER TABLE accounts ADD COLUMN password TEXT"),
                            (
                                "login_status",
                                "ALTER TABLE accounts ADD COLUMN login_status TEXT DEFAULT 'pending'",
                            ),
                            ("is_pinned", "ALTER TABLE accounts ADD COLUMN is_pinned INTEGER DEFAULT 0"),
                            ("pin_order", "ALTER TABLE accounts ADD COLUMN pin_order INTEGER DEFAULT 0"),
                            ("sort_order", "ALTER TABLE accounts ADD COLUMN sort_order INTEGER DEFAULT 0"),
                        ]:
                            if col not in columns:
                                cursor.execute(ddl)
                        cursor.execute(
                            "UPDATE accounts SET sort_order = id WHERE sort_order IS NULL"
                        )
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='groups'"
                    )
                    if not cursor.fetchone():
                        cursor.execute('''
                        CREATE TABLE groups (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        ''')
                        cursor.execute('''
                        CREATE TABLE account_groups (
                            account_id INTEGER NOT NULL,
                            group_id INTEGER NOT NULL,
                            PRIMARY KEY (account_id, group_id),
                            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
                        )
                        ''')
                    # settings：用于锁定密码等轻量配置
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)"
                    )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"数据库初始化错误: {e}")
            raise RuntimeError(f"无法初始化数据库: {self.db_file}") from e

    def get_setting(self, key: str) -> Optional[str]:
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT v FROM settings WHERE k = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                conn.close()
        except sqlite3.Error:
            return None

    def set_setting(self, key: str, value: str):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                        (key, value),
                    )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"保存设置错误: {e}")

    def _ensure_account_paths(self, account_id: int, remark: str) -> Tuple[str, str]:
        session_dir, cache_dir = AppPaths.account_dirs(remark, account_id)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE accounts SET user_data_dir = ?, cache_dir = ? WHERE id = ?',
                (session_dir, cache_dir, account_id),
            )
            conn.commit()
        finally:
            conn.close()
        return session_dir, cache_dir

    def get_all_accounts(self):
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, remark, user_data_dir, cache_dir, email, password, login_status, '
                    'COALESCE(is_pinned,0), COALESCE(pin_order,0), COALESCE(sort_order, id) '
                    'FROM accounts '
                    'ORDER BY is_pinned DESC, pin_order ASC, sort_order ASC, id ASC'
                )
                return cursor.fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"查询错误: {e}")
            return []

    def count_pinned_accounts(self, exclude_id: Optional[int] = None) -> int:
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                if exclude_id is not None:
                    cursor.execute(
                        "SELECT COUNT(*) FROM accounts WHERE is_pinned = 1 AND id != ?",
                        (exclude_id,),
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_pinned = 1")
                return int(cursor.fetchone()[0])
            finally:
                conn.close()
        except sqlite3.Error:
            return 0

    def is_account_pinned(self, account_id: int) -> bool:
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COALESCE(is_pinned,0) FROM accounts WHERE id = ?", (account_id,)
                )
                row = cursor.fetchone()
                return bool(row and row[0])
            finally:
                conn.close()
        except sqlite3.Error:
            return False

    def set_account_pinned(self, account_id: int, pinned: bool) -> Tuple[bool, str]:
        try:
            with self._lock:
                if pinned and self.count_pinned_accounts(exclude_id=account_id) >= MAX_PINNED_ACCOUNTS:
                    return False, f"最多置顶 {MAX_PINNED_ACCOUNTS} 个账号"
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    if pinned:
                        cursor.execute(
                            "SELECT COALESCE(MAX(pin_order), -1) + 1 FROM accounts WHERE is_pinned = 1"
                        )
                        pin_order = int(cursor.fetchone()[0])
                        cursor.execute(
                            "UPDATE accounts SET is_pinned = 1, pin_order = ? WHERE id = ?",
                            (pin_order, account_id),
                        )
                    else:
                        cursor.execute(
                            "UPDATE accounts SET is_pinned = 0, pin_order = 0 WHERE id = ?",
                            (account_id,),
                        )
                    conn.commit()
                    return True, ""
                finally:
                    conn.close()
        except sqlite3.Error as e:
            return False, str(e)

    def save_display_order(self, pinned_ids: List[int], unpinned_ids: List[int]):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    for i, aid in enumerate(pinned_ids):
                        cursor.execute(
                            "UPDATE accounts SET is_pinned = 1, pin_order = ?, sort_order = ? WHERE id = ?",
                            (i, i, aid),
                        )
                    for i, aid in enumerate(unpinned_ids):
                        cursor.execute(
                            "UPDATE accounts SET is_pinned = 0, pin_order = 0, sort_order = ? WHERE id = ?",
                            (i, aid),
                        )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"保存排序错误: {e}")

    def add_account(self, remark, email=None, password=None):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO accounts (remark, user_data_dir, cache_dir, email, password, login_status)
                        VALUES (?, '', '', ?, ?, 'pending')
                        ''',
                        (remark, email or "", password or ""),
                    )
                    conn.commit()
                    account_id = cursor.lastrowid
                finally:
                    conn.close()
            if account_id:
                self._ensure_account_paths(account_id, remark)
            return account_id
        except sqlite3.Error as e:
            print(f"添加账号错误: {e}")
            return None

    def delete_account(self, account_id):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT user_data_dir, cache_dir FROM accounts WHERE id = ?',
                        (account_id,),
                    )
                    res = cursor.fetchone()
                    if res:
                        for path in (res[0], res[1]):
                            if path and os.path.exists(path):
                                try:
                                    shutil.rmtree(path, ignore_errors=True)
                                except Exception as e:
                                    print(f"删除目录失败 {path}: {e}")
                        if res[0]:
                            parent = os.path.dirname(res[0])
                            if parent and os.path.basename(parent) == "session":
                                profile_parent = os.path.dirname(parent)
                                if os.path.isdir(profile_parent):
                                    shutil.rmtree(profile_parent, ignore_errors=True)
                    cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"删除账号错误: {e}")

    def update_remark(self, account_id, remark):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'UPDATE accounts SET remark = ? WHERE id = ?', (remark, account_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"更新备注错误: {e}")

    def update_account_credentials(
        self, account_id, remark=None, email=None, password=None
    ):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    if remark is not None:
                        cursor.execute(
                            'UPDATE accounts SET remark = ? WHERE id = ?', (remark, account_id)
                        )
                    if email is not None:
                        cursor.execute(
                            'UPDATE accounts SET email = ? WHERE id = ?', (email, account_id)
                        )
                    if password is not None:
                        cursor.execute(
                            'UPDATE accounts SET password = ? WHERE id = ?',
                            (password, account_id),
                        )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"更新账号凭据错误: {e}")

    def set_login_status(self, account_id: int, status: str):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'UPDATE accounts SET login_status = ? WHERE id = ?',
                        (status, account_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"更新登录状态错误: {e}")

    def find_account_by_email(self, email: str):
        if not email:
            return None
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, remark, user_data_dir, cache_dir, email, password, login_status '
                    'FROM accounts WHERE lower(email) = lower(?)',
                    (email.strip(),),
                )
                return cursor.fetchone()
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"按邮箱查询错误: {e}")
            return None

    def get_account(self, account_id):
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, remark, user_data_dir, cache_dir, email, password, login_status '
                    'FROM accounts WHERE id = ?',
                    (account_id,),
                )
                row = cursor.fetchone()
                if row and (not row[2] or not row[3]):
                    session_dir, cache_dir = self._ensure_account_paths(row[0], row[1])
                    return (row[0], row[1], session_dir, cache_dir, row[4], row[5], row[6])
                return row
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"获取账号错误: {e}")
            return None

    def get_all_groups(self) -> List[Tuple]:
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM groups ORDER BY id")
                return cursor.fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"查询分组错误: {e}")
            return []

    def add_group(self, name: str) -> Optional[int]:
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO groups (name) VALUES (?)", (name.strip(),))
                    conn.commit()
                    return cursor.lastrowid
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"添加分组错误: {e}")
            return None

    def update_group_name(self, group_id: int, name: str):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE groups SET name = ? WHERE id = ?", (name.strip(), group_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"更新分组错误: {e}")

    def delete_group(self, group_id: int):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM account_groups WHERE group_id = ?", (group_id,))
                    cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"删除分组错误: {e}")

    def get_account_ids_in_group(self, group_id: int) -> Set[int]:
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT account_id FROM account_groups WHERE group_id = ?", (group_id,)
                )
                return {row[0] for row in cursor.fetchall()}
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"查询分组成员错误: {e}")
            return set()

    def get_account_ids_in_other_groups(self, exclude_group_id: int) -> Set[int]:
        """已分配到其它分组的账号（编辑当前分组时不重复展示）"""
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT account_id FROM account_groups WHERE group_id != ?",
                    (exclude_group_id,),
                )
                return {row[0] for row in cursor.fetchall()}
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"查询其它分组成员错误: {e}")
            return set()

    def set_group_members(self, group_id: int, account_ids: List[int]):
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM account_groups WHERE group_id = ?", (group_id,)
                    )
                    for aid in account_ids:
                        cursor.execute(
                            "INSERT OR IGNORE INTO account_groups (account_id, group_id) VALUES (?, ?)",
                            (aid, group_id),
                        )
                    conn.commit()
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"设置分组成员错误: {e}")

    def get_groups_for_account(self, account_id: int) -> List[int]:
        try:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT group_id FROM account_groups WHERE account_id = ?", (account_id,)
                )
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()
        except sqlite3.Error as e:
            return []

    def account_has_group(self, account_id: int) -> bool:
        return bool(self.get_groups_for_account(account_id))

    def get_account_group(self, account_id: int) -> Optional[Tuple[int, str]]:
        gids = self.get_groups_for_account(account_id)
        if not gids:
            return None
        gid = gids[0]
        for g_id, name in self.get_all_groups():
            if g_id == gid:
                return gid, name
        return gid, ""

    def set_account_group(self, account_id: int, group_id: Optional[int]) -> bool:
        try:
            with self._lock:
                conn = self.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM account_groups WHERE account_id = ?", (account_id,)
                    )
                    if group_id:
                        cursor.execute(
                            "INSERT OR IGNORE INTO account_groups (account_id, group_id) VALUES (?, ?)",
                            (account_id, group_id),
                        )
                    conn.commit()
                    return True
                finally:
                    conn.close()
        except sqlite3.Error as e:
            print(f"设置账号分组错误: {e}")
            return False


class ImageClipboardHelper(QObject):
    """通过当前 WebView 页面上下文拉取图片并写入系统剪贴板"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def copy_via_webview(self, web_view: "TeamsWebView", image_url: str):
        if not web_view or not web_view.page() or not image_url:
            return
        url_js = json.dumps(image_url)
        js = f"""
        (function() {{
            const targetUrl = {url_js};
            function toDataUrl(img) {{
                const w = img.naturalWidth || img.width || 0;
                const h = img.naturalHeight || img.height || 0;
                if (!w || !h) return '';
                const c = document.createElement('canvas');
                c.width = w; c.height = h;
                c.getContext('2d').drawImage(img, 0, 0);
                return c.toDataURL('image/png');
            }}
            const imgs = document.querySelectorAll('img');
            for (let i = 0; i < imgs.length; i++) {{
                const im = imgs[i];
                if (im.src === targetUrl || im.currentSrc === targetUrl) {{
                    if (im.complete && im.naturalWidth) return toDataUrl(im);
                }}
            }}
            return '';
        }})();
        """
        web_view.page().runJavaScript(js, lambda data: self._apply_data_url(web_view, data, image_url))

    def _apply_data_url(self, web_view, data_url, fallback_url: str):
        if data_url and isinstance(data_url, str) and data_url.startswith("data:"):
            bridge = getattr(web_view, "_notify_bridge", None)
            if bridge:
                bridge.copyImageDataUrl(data_url)
            return
        self._fetch_with_credentials(web_view, fallback_url)

    def _fetch_with_credentials(self, web_view, image_url: str):
        if not web_view or not web_view.page():
            return
        url_js = json.dumps(image_url)
        js = f"""
        (function() {{
            return fetch({url_js}, {{credentials: 'include', mode: 'cors'}})
                .then(r => r.blob())
                .then(b => new Promise((res, rej) => {{
                    const fr = new FileReader();
                    fr.onload = () => res(fr.result);
                    fr.onerror = rej;
                    fr.readAsDataURL(b);
                }}))
                .catch(() => '');
        }})();
        """
        web_view.page().runJavaScript(js, lambda data: self._finish(data))

    def _finish(self, data_url):
        if not data_url or not isinstance(data_url, str) or not data_url.startswith("data:"):
            print("复制图片失败: 无法获取图片数据")
            return
        try:
            comma = data_url.find(",")
            raw = base64.b64decode(data_url[comma + 1 :].strip())
            img = QImage()
            if not img.loadFromData(raw):
                print("剪贴板: 无法解析图片")
                return
            pix = QPixmap.fromImage(img)
            if not pix.isNull():
                QGuiApplication.clipboard().setPixmap(pix)
        except Exception as e:
            print(f"复制图片到剪贴板失败: {e}")


class JsNotifyBridge(QObject):
    """网页消息与图片复制桥接"""

    def __init__(self, account_id: int, callback, web_view=None, image_helper=None, parent=None):
        super().__init__(parent)
        self._account_id = account_id
        self._callback = callback
        self._web_view = web_view
        self._image_helper = image_helper

    def set_web_view(self, web_view):
        self._web_view = web_view

    def set_callback(self, callback):
        self._callback = callback

    @pyqtSlot(str, str, str, int)
    def post(self, msg_type: str, sender: str, content: str, count: int):
        if not self._callback:
            return
        aid = self._account_id
        cb = self._callback

        def _deliver():
            try:
                cb(aid, int(count), msg_type, sender, content or "")
            except Exception as e:
                print(f"通知桥接错误: {e}")

        QTimer.singleShot(0, _deliver)

    @pyqtSlot(str)
    def cacheNotifySoundUrl(self, url: str) -> None:
        host = None
        if self._web_view is not None:
            host = getattr(self._web_view, "_host_main", None)
        if host is not None and hasattr(host, "_cache_teams_notify_sound_url"):
            u = (url or "").strip()
            QTimer.singleShot(0, lambda h=host, u=u: h._cache_teams_notify_sound_url(u))

    @pyqtSlot(str)
    def copyImageDataUrl(self, data_url: str):
        if not data_url or not data_url.startswith("data:"):
            return
        try:
            comma = data_url.find(",")
            if comma < 0:
                return
            raw = base64.b64decode(data_url[comma + 1 :].strip())
            img = QImage()
            if not img.loadFromData(raw):
                print("剪贴板: 无法解析图片")
                return
            pix = QPixmap.fromImage(img)
            if not pix.isNull():
                QGuiApplication.clipboard().setPixmap(pix)
        except Exception as e:
            print(f"复制图片到剪贴板失败: {e}")

    @pyqtSlot(str)
    def copyImageUrl(self, image_url: str):
        if not image_url:
            return
        if self._image_helper and self._web_view:
            self._image_helper.copy_via_webview(self._web_view, image_url)
        else:
            print("复制图片失败: 桥接未就绪")


class GroupManagePanel(QWidget):
    """分组管理（侧边栏内嵌）：新建、编辑、删除、分配成员"""

    closed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setVisible(False)
        self.setObjectName("groupManagePanel")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 0, 8, 4)
        outer.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("groupManagePanelFrame")
        frame.setMinimumWidth(0)
        frame.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_lbl = QLabel("分组管理")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent;")
        title_row.addWidget(title_lbl)
        title_row.addStretch(1)
        collapse_btn = QPushButton("收起")
        collapse_btn.setFixedSize(SIDEBAR_SMALL_BTN_W, SIDEBAR_SMALL_BTN_H)
        collapse_btn.clicked.connect(self.collapse)
        title_row.addWidget(collapse_btn)
        layout.addLayout(title_row)

        layout.addWidget(QLabel("分组列表"))
        self.group_list = QListWidget()
        self.group_list.setMaximumHeight(72)
        layout.addWidget(self.group_list, 0)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("分组名称")
        layout.addWidget(self.name_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self._add_group)
        btn_row.addWidget(self.add_btn)
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self._edit_group)
        btn_row.addWidget(edit_btn)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._delete_group)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.member_checks: List[QCheckBox] = []
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.members_widget = QWidget()
        self.members_layout = QVBoxLayout(self.members_widget)
        self.members_layout.setContentsMargins(6, 6, 6, 6)
        self.members_layout.setSpacing(4)
        self.members_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.members_widget)
        layout.addWidget(scroll, 1)

        self.save_btn = QPushButton("保存成员")
        self.save_btn.clicked.connect(self._save_members)
        layout.addWidget(self.save_btn)

        outer.addWidget(frame, 1)
        self._panel_frame = frame
        frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.group_list.currentItemChanged.connect(self._on_group_changed)
        self._reload_groups()

    def _msg_parent(self):
        w = self.window()
        return w if w is not None else self

    def _dialog_light(self) -> bool:
        return bool(getattr(self, "_light", False))

    def expand(self) -> None:
        self._reload_groups()

    def collapse(self) -> None:
        if not self.isVisible():
            return
        self.closed.emit()

    def apply_panel_theme(self, light: bool) -> None:
        self._light = bool(light)
        if light:
            c = {
                "bg": "#ffffff", "border": "#e6e8ec", "title": "#1f2329",
                "sub": "#8a9099", "input_bg": "#f6f8fb", "input_border": "#dfe3e8",
                "input_focus": "#3b82f6", "text": "#1f2329",
                "list_bg": "#f6f8fb", "list_sel": "#e8f1ff", "list_sel_text": "#1a3c66",
                "btn_bg": "#f1f3f6", "btn_border": "#dfe3e8", "btn_hover": "#e6eaf0",
                "accent": "#2f6fed", "accent_hover": "#2560d6",
                "scroll_bg": "#fafbfc", "scroll_handle": "#cfd4db",
            }
        else:
            c = {
                "bg": "#2b2d31", "border": "#3a3d42", "title": "#f2f3f5",
                "sub": "#9aa0a6", "input_bg": "#34373c", "input_border": "#42454a",
                "input_focus": "#5a9cf5", "text": "#eceef0",
                "list_bg": "#34373c", "list_sel": "#34507a", "list_sel_text": "#eaf2ff",
                "btn_bg": "#3a3d42", "btn_border": "#4a4d52", "btn_hover": "#454950",
                "accent": "#3b82f6", "accent_hover": "#4a90f0",
                "scroll_bg": "#2f3136", "scroll_handle": "#4a4d52",
            }
        self._panel_frame.setStyleSheet(
            f"#groupManagePanelFrame {{ background-color: {c['bg']};"
            f" border: 1px solid {c['border']}; border-radius: 12px; }}"
            f"#groupManagePanelFrame QLabel {{ color: {c['title']}; background: transparent; }}"
            f"#groupManagePanelFrame QLineEdit {{ background: {c['input_bg']};"
            f" color: {c['text']}; border: 1px solid {c['input_border']};"
            f" border-radius: 8px; padding: 5px 9px; font-size: 12px; }}"
            f"#groupManagePanelFrame QLineEdit:focus {{ border: 1px solid {c['input_focus']}; }}"
            f"#groupManagePanelFrame QPushButton {{ background: {c['btn_bg']};"
            f" color: {c['text']}; border: 1px solid {c['btn_border']};"
            f" border-radius: 8px; padding: 4px 10px; font-size: 12px; }}"
            f"#groupManagePanelFrame QPushButton:hover, #groupManagePanelFrame QPushButton:hover {{ }}"
            f"#groupManagePanelFrame QPushButton:hover {{ background: {c['btn_hover']}; }}"
            f"#groupManagePanelFrame QListWidget {{ background: {c['list_bg']};"
            f" color: {c['text']}; border: 1px solid {c['input_border']};"
            f" border-radius: 8px; padding: 2px; outline: none; }}"
            f"#groupManagePanelFrame QListWidget::item {{ border-radius: 6px; padding: 4px 6px; }}"
            f"#groupManagePanelFrame QListWidget::item:selected {{ background: {c['list_sel']};"
            f" color: {c['list_sel_text']}; }}"
            f"#groupManagePanelFrame QScrollArea {{ background: {c['scroll_bg']};"
            f" border: 1px solid {c['input_border']}; border-radius: 8px; }}"
            f"#groupManagePanelFrame QScrollArea > QWidget > QWidget {{ background: transparent; }}"
            f"#groupManagePanelFrame QCheckBox {{ color: {c['text']}; background: transparent;"
            f" spacing: 6px; padding: 2px 0; font-size: 12px; }}"
            "#groupManagePanelFrame QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }"
            f"#groupManagePanelFrame QScrollBar::handle:vertical {{ background: {c['scroll_handle']};"
            " border-radius: 4px; min-height: 24px; }"
            "#groupManagePanelFrame QScrollBar::add-line:vertical,"
            " #groupManagePanelFrame QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._style_accent_button(self.save_btn, c)
        self._style_accent_button(self.add_btn, c)

    def _style_accent_button(self, btn: QPushButton, c: dict) -> None:
        btn.setStyleSheet(
            f"QPushButton {{ background: {c['accent']}; color: #ffffff; border: none;"
            " border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
        )

    def _reload_groups(self):
        self.group_list.clear()
        for gid, name in self.db.get_all_groups():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, gid)
            self.group_list.addItem(item)

    def _add_group(self):
        name = self.name_edit.text().strip()
        if not name:
            return
        if self.db.add_group(name):
            self.name_edit.clear()
            self._reload_groups()

    def _edit_group(self):
        """编辑当前分组名称，并刷新该分组的成员勾选列表"""
        item = self.group_list.currentItem()
        if not item:
            ConfirmCardDialog.info(
                self._msg_parent(), title="提示",
                message="请先在左侧选择一个分组", light=self._dialog_light(),
            )
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        name = self.name_edit.text().strip()
        if name and name != item.text():
            self.db.update_group_name(gid, name)
            self._reload_groups()
            for i in range(self.group_list.count()):
                if self.group_list.item(i).data(Qt.ItemDataRole.UserRole) == gid:
                    self.group_list.setCurrentRow(i)
                    break
        self._on_group_changed()

    def _delete_group(self):
        item = self.group_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        if ConfirmCardDialog.confirm(
            self._msg_parent(),
            title="删除分组",
            message=f"确定要删除分组「{item.text()}」吗？\n组内成员不会被删除，仅解除分组。",
            ok_text="删除",
            danger=True,
            light=self._dialog_light(),
        ):
            self.db.delete_group(gid)
            self._reload_groups()
            self._clear_member_checks()

    def _clear_member_checks(self):
        while self.members_layout.count():
            w = self.members_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.member_checks = []

    def _on_group_changed(self):
        self._clear_member_checks()
        item = self.group_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        self.name_edit.setText(item.text())
        in_group = self.db.get_account_ids_in_group(gid)
        in_other_groups = self.db.get_account_ids_in_other_groups(gid)
        for acc in self.db.get_all_accounts():
            aid, remark = acc[0], acc[1]
            if aid in in_other_groups:
                continue
            cb = QCheckBox(remark)
            cb.setProperty("account_id", aid)
            cb.setChecked(aid in in_group)
            self.members_layout.addWidget(cb)
            self.member_checks.append(cb)

    def _save_members(self):
        item = self.group_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        ids = [cb.property("account_id") for cb in self.member_checks if cb.isChecked()]
        self.db.set_group_members(gid, ids)
        ConfirmCardDialog.info(
            self._msg_parent(), title="完成",
            message="分组成员已保存", light=self._dialog_light(),
        )
        self._on_group_changed()


# ==================== WebView 类 ====================

_TEAMS_LOGIN_FAIL_REASONS = frozenset({
    "still_on_login", "login_form", "sign_in_ui", "welcome_heading", "passkey_ui",
    "auth_path", "login_title", "welcome_text", "unsupported_browser", "not_teams",
})

_TEAMS_SHELL_VERIFY_JS = r"""
(function() {
    try {
        const href = (location.href || '').toLowerCase();
        const host = (location.hostname || '').toLowerCase();
        if (host.includes('login.microsoft') || host.includes('login.live') || host.includes('account.live')
            || href.includes('login.microsoftonline.com') || href.includes('login.microsoft.com'))
            return JSON.stringify({ok: false, reason: 'still_on_login'});
        if (!host.includes('teams.microsoft') && !host.includes('teams.cloud.microsoft')
            && !host.includes('teams.live.com'))
            return JSON.stringify({ok: false, reason: 'not_teams'});
        const visible = (el) => {
            if (!el) return false;
            const r = el.getBoundingClientRect();
            const st = getComputedStyle(el);
            return r.width > 8 && r.height > 8 && st.visibility !== 'hidden' && st.display !== 'none';
        };
        const loginInput = document.querySelector(
            'input[type="email"], input[type="password"], input[name="loginfmt"], input[name="passwd"], '
            + '#i0116, #i0118, #passwordInput'
        );
        if (visible(loginInput))
            return JSON.stringify({ok: false, reason: 'login_form'});
        const title = (document.title || '').trim();
        const bodyText = ((document.body && document.body.innerText) || '').trim();
        if (/browser.*(not supported|不受支持)|你的浏览器版本不受支持|download microsoft teams/i.test(
            bodyText.substring(0, 900)))
            return JSON.stringify({ok: false, reason: 'unsupported_browser'});
        if (/^(sign in|登录|sign in to teams)$/i.test(title))
            return JSON.stringify({ok: false, reason: 'login_title'});
        if (/sign in to teams|登录 teams|welcome to teams|开始使用 teams/i.test(
            bodyText.substring(0, 350)))
            return JSON.stringify({ok: false, reason: 'welcome_text'});
        try {
            const ck = document.cookie || '';
            if (/ESTSAUTH|ESTSAUTHPERSISTENT|TeamsAuth|skypetoken|MicrosoftTeams/i.test(ck))
                return JSON.stringify({ok: true, reason: 'auth_cookie'});
        } catch (e) {}
        if (/microsoft teams/i.test(title) && !/sign in|登录/i.test(title))
            return JSON.stringify({ok: true, reason: 'title'});
        if (/\/v2\//.test(href) || /\/_#/.test(href) || /\/dl\/launcher\//.test(href))
            return JSON.stringify({ok: true, reason: 'app_url'});
        const passkey = document.querySelector(
            '[data-testid="credential-picker"], [data-testid="fido-keys"], #idA_PWD_SwitchToPassword'
        );
        if (visible(passkey))
            return JSON.stringify({ok: false, reason: 'passkey_ui'});
        const signInUi = document.querySelector(
            '[data-tid="signInButton"], [data-tid="sign-in-button"], '
            + 'button[data-testid="loginButton"], a[href*="login.microsoft"]'
        );
        if (visible(signInUi))
            return JSON.stringify({ok: false, reason: 'sign_in_ui'});
        const headings = document.querySelectorAll('h1, h2, [role="heading"]');
        for (const h of headings) {
            const t = (h.innerText || h.textContent || '').trim();
            if (visible(h) && /sign in|登录|开始使用|get started|welcome to teams/i.test(t)
                && bodyText.length < 500)
                return JSON.stringify({ok: false, reason: 'welcome_heading'});
        }
        const shellSelectors = [
            '[data-tid="teams-app-bar"]', '[data-tid="app-bar"]', '[data-testid="app-bar"]',
            '[data-tid="chat-pane-list"]', '[data-tid="chat-list"]', '[data-testid="chat-list"]',
            '[data-tid="me-control"]', '[data-tid="profile-picture"]',
            '[data-tid="topbar-profile-button"]', '[data-tid="experience-layout"]',
            '[id="teams-app-frame"]', 'div[data-app-name="Teams"]',
            'button[aria-label*="Chat" i]', 'button[aria-label*="聊天"]',
            'nav[role="navigation"]', '[data-tid="left-rail"]', '[data-tid="leftRail"]'
        ];
        for (const sel of shellSelectors) {
            try {
                const el = document.querySelector(sel);
                if (visible(el))
                    return JSON.stringify({ok: true, reason: 'shell'});
            } catch (e) {}
        }
        const root = document.querySelector('#root, #app, [data-tid="app"]');
        if (root && visible(root) && (root.innerText || '').trim().length > 60)
            return JSON.stringify({ok: true, reason: 'root'});
        if (bodyText.length > 120)
            return JSON.stringify({ok: true, reason: 'body'});
        return JSON.stringify({ok: false, reason: 'no_shell'});
    } catch (e) {
        return JSON.stringify({ok: false, reason: 'error'});
    }
})();
"""

class TeamsWebView(QWidget):
    """Teams WebView — PyQt 壳 + WebView2（Windows）或 Qt WebEngine（回退）"""

    loginCompleted = pyqtSignal(int, bool, str)
    sessionLoggedIn = pyqtSignal(int)

    def __init__(
        self,
        account_id,
        session_dir,
        cache_dir,
        notification_callback=None,
        login_email=None,
        login_password=None,
        auto_login=False,
        image_helper=None,
        parent=None,
    ):
        super().__init__(parent)
        self.account_id = account_id
        self._image_helper = image_helper
        self.session_dir = session_dir
        self.cache_dir = cache_dir
        self.user_data_dir = session_dir
        self.notification_callback = notification_callback
        self.load_timeout_timer = None
        self.retry_count = 0
        self.max_retries = 3
        self.is_valid = True
        self.is_loading = False
        self._is_closing = False
        self._login_email = (login_email or "").strip()
        self._login_password = login_password or ""
        self._auto_login = auto_login and bool(self._login_email and self._login_password)
        self._login_active = False
        self._login_poll_count = 0
        self._login_max_polls = 90
        self._login_poll_timer = None
        self._login_timeout_timer = None
        self._login_verify_timer = None
        self._login_started_at = 0.0
        self._seen_login_host = False
        self._email_step_done = False
        self._login_verify_hits = 0
        self._login_password_error_hits = 0
        self._session_probe_hits = 0
        self._runtime_mode = RUNTIME_FOREGROUND
        self._core_suspended = False
        self._session_reported = False
        self._session_probe_timer = None
        self._host_main = None
        self._engine_kind = "webview2"
        self._page_adapter = None
        self._wv2_widget = None
        self._wv2_doc_scripts: List[str] = []
        self.profile = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        try:
            os.makedirs(session_dir, exist_ok=True)
            os.makedirs(cache_dir, exist_ok=True)
        except Exception as e:
            print(f"创建用户目录失败: {e}")
            self.is_valid = False
            return

        self._notify_bridge = JsNotifyBridge(
            account_id, notification_callback, self, image_helper, self
        )

        if not (_HAS_TEAMS_ENGINE and use_webview2()):
            self.is_valid = False
            raise RuntimeError(
                "WebView2 引擎不可用。请安装/检查: qtwebview2 + pythonnet + pywin32，"
                "并确保 Python 与 WebView2 运行时位数一致（通常 x64）。"
            )
        if not self._init_webview2_engine():
            self.is_valid = False
            raise RuntimeError("WebView2 引擎初始化失败（已禁用 QtWebEngine 回退）。")

        if not self.is_valid:
            return

        self._offline_timer = QTimer(self)
        self._offline_timer.timeout.connect(self._check_offline_and_reconnect)
        self._offline_timer.start(45000)
        self._offline_retry_count = 0
        self._blank_health_suspect_count = 0
        self._suspended_at = 0.0
        self._last_ok_load_at = 0.0
        self._last_health_reload_at = 0.0
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_page_health)
        self._health_timer.start(TEAMS_HEALTH_CHECK_INTERVAL_SEC * 1000)

        # load_teams 在 WebView2 is_ready 后由 _on_wv2_engine_ready 触发

    def _on_wv2_engine_ready(self, success: bool, error_message: str = ""):
        """WebView2 异步初始化完成；失败则直接报错（无回退）。"""
        if success:
            QTimer.singleShot(100, self.load_teams)
            return
        msg = f"账号 {self.account_id} WebView2 初始化失败"
        if error_message:
            msg += f": {error_message}"
        print(msg)
        self.is_valid = False

    def _init_webview2_engine(self) -> bool:
        try:
            os.environ.setdefault("QT_API", "pyqt6")
            from qtwebview2 import DictJsBridge

            apply_webview2_runtime_env()
            print("[WebView2] User-Agent 使用 WebView2 原生（不覆盖）")

            self._engine_kind = "webview2"
            self._wv2_doc_scripts = []
            self._inject_persistent_scripts()
            self._inject_bridge_connect_script()
            self._inject_login_page_scripts()

            js_bridge = DictJsBridge()
            nb = self._notify_bridge
            js_bridge.bind_js_api_func(nb.post, name="post")
            js_bridge.bind_js_api_func(nb.copyImageDataUrl, name="copyImageDataUrl")
            js_bridge.bind_js_api_func(nb.copyImageUrl, name="copyImageUrl")
            js_bridge.bind_js_api_func(nb.cacheNotifySoundUrl, name="cacheNotifySoundUrl")

            self._wv2_widget, self._page_adapter = create_webview2_widget(
                parent=self,
                session_dir=self.session_dir,
                account_id=self.account_id,
                shared_user_data_folder=AppPaths.shared_webview2_user_data(),
                user_agent="",
                js_bridge=js_bridge,
                doc_scripts=list(self._wv2_doc_scripts),
                on_navigation_completed=self._on_wv2_navigation_completed,
                on_url_changed=self._on_url_changed,
            )
            self._layout.addWidget(self._wv2_widget, 1)
            try:
                self._wv2_widget.bridge.domContentLoaded.connect(
                    lambda: self._schedule_session_check(1500)
                )
            except Exception:
                pass
            try:
                self._wv2_widget.bridge.initialization_done.connect(
                    self._on_wv2_engine_ready
                )
            except Exception:
                pass
            print(f"账号 {self.account_id} 使用 WebView2（{self.session_dir}）")
            return True
        except Exception as e:
            print(f"WebView2 引擎创建失败: {e}")
            self._wv2_widget = None
            self._page_adapter = None
            return False

    def _on_wv2_navigation_completed(self, ok: bool):
        self.on_load_finished(bool(ok))

    def page(self):
        return self._page_adapter

    def load(self, url: QUrl):
        u = url.toString() if isinstance(url, QUrl) else str(url)
        if self._wv2_widget:
            self._wv2_widget.load_url(u)
            if self._page_adapter:
                self._page_adapter.set_current_url(QUrl(u))

    def stop(self):
        if self._wv2_widget and self._wv2_widget.is_ready:
            try:
                self._wv2_widget._webview.CoreWebView2.Stop()
            except Exception:
                pass

    def setPage(self, page):
        # WebView2-only：不支持外部 setPage
        return

    def _on_feature_permission(self, origin, feature):
        # WebView2-only：权限由 WebView2 侧处理
        return

    def _on_js_console_message(self, level, message, line_number, source_id):
        text = (message or "").strip()
        if not text:
            return
        low = text.lower()
        if any(
            k in low
            for k in (
                "playback",
                "widevine",
                "drm",
                "eme",
                "media",
                "encrypted",
                "cdm",
            )
        ):
            print(f"[Teams/{self.account_id}] js[{level}]: {text} ({source_id}:{line_number})")

    def hard_reload_teams(self):
        """强制恢复 Teams 页（绕过僵死渲染/缓存导致的白屏）。"""
        if not self.is_valid or self._is_closing:
            return
        self.is_loading = False
        if self.load_timeout_timer:
            self.load_timeout_timer.stop()
            self.load_timeout_timer.deleteLater()
            self.load_timeout_timer = None
        url = ""
        try:
            if self.page():
                url = self.page().url().toString()
        except Exception:
            url = ""
        if url and self._is_teams_app_url(url):
            try:
                self.is_loading = True
                if self._wv2_widget and getattr(self._wv2_widget, "is_ready", False):
                    self._wv2_widget.reload()
                else:
                    raise RuntimeError("WebView2 未就绪")
                self.load_timeout_timer = QTimer(self)
                self.load_timeout_timer.setSingleShot(True)
                self.load_timeout_timer.timeout.connect(self.on_load_timeout)
                self.load_timeout_timer.start(30000)
                print(f"账号 {self.account_id} 强制刷新 Teams（绕过缓存）")
                return
            except Exception as e:
                print(f"账号 {self.account_id} 强制刷新失败，改为重新加载: {e}")
        self.load_teams()

    def load_teams(self):
        """加载 Teams 页面"""
        if not self.is_valid:
            return

        if self.load_timeout_timer:
            try:
                self.load_timeout_timer.stop()
            except RuntimeError:
                pass
            try:
                self.load_timeout_timer.deleteLater()
            except RuntimeError:
                pass
            self.load_timeout_timer = None

        self.is_loading = True
        teams_url = "https://teams.microsoft.com/?lang=zh-CN"
        if self._login_email:
            teams_url += f"&login_hint={quote(self._login_email)}"

        # 注意：WebView2 导航完成可能非常快（甚至同步触发回调），
        # 必须先创建/绑定 timeout timer，避免回调里 stop 到旧的 deleteLater timer。
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(self.on_load_timeout)
        self.load_timeout_timer = t
        t.start(30000)

        self.load(QUrl(teams_url))

    def on_load_finished(self, ok):
        """页面加载完成回调"""
        if self.load_timeout_timer:
            try:
                self.load_timeout_timer.stop()
            except RuntimeError:
                pass
            self.load_timeout_timer = None

        self.is_loading = False

        if ok:
            self._last_ok_load_at = time.time()
            self.retry_count = 0
            self._offline_retry_count = 0
            self._blank_health_suspect_count = 0
            host = getattr(self, "_host_main", None)
            if host is not None and hasattr(host, "clear_teams_load_failures"):
                host.clear_teams_load_failures()
            QTimer.singleShot(2000, self.setup_callbacks)
            if self._auto_login and not self._login_active:
                QTimer.singleShot(1500, self._maybe_start_auto_login)
            self._schedule_session_check(800)
            self._start_session_probe_timer()
            # 页面就绪后补设内存档：后台加载时档位虽已是 warm，
            # 但当时 WebView2 未就绪，Low 内存目标没设上，必须在此重设一次。
            QTimer.singleShot(1500, self._reapply_runtime_memory_profile)
            QTimer.singleShot(5000, self._reapply_runtime_memory_profile)
            QTimer.singleShot(15000, self._reapply_runtime_memory_profile)
        else:
            print(f"账号 {self.account_id} 页面加载失败")
            host = getattr(self, "_host_main", None)
            if host is not None and hasattr(host, "register_teams_load_failure"):
                host.register_teams_load_failure(self.account_id)
            if self._auto_login:
                self._finish_login(False, "页面加载失败")

    def on_load_timeout(self):
        """加载超时处理"""
        self.is_loading = False
        self.retry_count += 1
        if self.retry_count <= self.max_retries:
            print(f"账号 {self.account_id} 加载超时，第{self.retry_count}次重试...")
            QTimer.singleShot(1000, self.load_teams)
        else:
            print(f"账号 {self.account_id} 加载超时，已达最大重试次数")
            self.load_timeout_timer = None
            host = getattr(self, "_host_main", None)
            if host is not None and hasattr(host, "register_teams_load_failure"):
                host.register_teams_load_failure(self.account_id)

    def _check_page_health(self):
        """检测 Teams 白屏/空壳页，自动恢复（长时间挂着不动时常见）。"""
        if self._is_closing or not self.is_valid or not self.page():
            return
        if self.is_loading or self._login_active or not self.isVisible():
            return
        if self._last_ok_load_at and (time.time() - self._last_ok_load_at) < 120:
            return
        if self._last_health_reload_at and (
            time.time() - self._last_health_reload_at
        ) < TEAMS_HEALTH_RELOAD_COOLDOWN_SEC:
            return
        url = self.page().url().toString()
        if not self._is_teams_app_url(url):
            return
        js = r"""
        (function() {
            try {
                const u = (location.href || '').toLowerCase();
                if (!u.includes('teams.microsoft.com') || u.includes('login.')) return false;
                const pick = document.querySelector(
                    '#root, #app, [data-tid], [class*="app-layer"], [role="main"]'
                );
                if (pick) {
                    const t = (pick.innerText || '').trim();
                    if (t.length > 40) return false;
                }
                const body = (document.body && document.body.innerText || '').trim();
                return body.length < 30;
            } catch (e) {
                return false;
            }
        })();
        """

        def on_blank(is_blank):
            if self._is_closing or not self.is_valid:
                return
            if not is_blank:
                self._blank_health_suspect_count = 0
                return
            self._blank_health_suspect_count += 1
            if self._blank_health_suspect_count < 2:
                print(f"账号 {self.account_id} 疑似 Teams 白屏，等待二次确认…")
                return
            self._blank_health_suspect_count = 0
            self._last_health_reload_at = time.time()
            host = getattr(self, "_host_main", None)
            if host is not None and hasattr(host, "request_teams_recovery"):
                host.request_teams_recovery(f"账号 {self.account_id} 白屏")
                return
            print(f"账号 {self.account_id} 检测到 Teams 白屏，自动恢复…")
            QTimer.singleShot(300, self.hard_reload_teams)

        self.page().runJavaScript(js, on_blank)

    def _verify_resume_health(self) -> None:
        """休眠恢复后轻量健康确认：仅白屏/异常 URL 才 reload。"""
        if self._is_closing or not self.is_valid or not self.page():
            return
        if self.is_loading or self._login_active:
            return
        url = self.page().url().toString()
        if self._is_login_host_url(url):
            return
        if not self._is_teams_app_url(url):
            print(f"账号 {self.account_id} 恢复后 URL 异常，尝试重载…")
            QTimer.singleShot(300, self.hard_reload_teams)
            return
        js = r"""
        (function() {
            try {
                const u = (location.href || '').toLowerCase();
                if (!u.includes('teams.microsoft.com') || u.includes('login.')) return false;
                const pick = document.querySelector(
                    '#root, #app, [data-tid], [class*="app-layer"], [role="main"]'
                );
                if (pick) {
                    const t = (pick.innerText || '').trim();
                    if (t.length > 40) return false;
                }
                const body = (document.body && document.body.innerText || '').trim();
                return body.length < 30;
            } catch (e) {
                return false;
            }
        })();
        """

        def on_blank(is_blank):
            if self._is_closing or not self.is_valid:
                return
            if not is_blank:
                return
            print(f"账号 {self.account_id} 恢复后检测到白屏，尝试重载…")
            QTimer.singleShot(300, self.hard_reload_teams)

        self.page().runJavaScript(js, on_blank)

    @property
    def is_closing(self):
        return self._is_closing or not self.is_valid

    @staticmethod
    def _is_login_host_url(url: str) -> bool:
        u = (url or "").lower()
        return (
            "login.microsoftonline.com" in u
            or "login.microsoft.com" in u
            or "login.live.com" in u
            or "account.live.com" in u
        )

    @staticmethod
    def _is_teams_app_url(url: str) -> bool:
        u = (url or "").lower()
        if TeamsWebView._is_login_host_url(u):
            return False
        return (
            "teams.microsoft.com" in u
            or "teams.cloud.microsoft" in u
            or "teams.live.com" in u
        )

    def _webview2_ready(self) -> bool:
        if self._engine_kind != "webview2":
            return True
        w = getattr(self, "_wv2_widget", None)
        return bool(w and getattr(w, "is_ready", False))

    def _schedule_session_check(self, delay_ms: int = 800, retries: int = 0):
        """WebView2 须等 is_ready 后再跑 JS 检测，否则永远标红。"""
        if self._session_reported or self._is_closing:
            return

        def _run():
            if self._session_reported or self._is_closing:
                return
            if not self._webview2_ready():
                if retries < 48:
                    QTimer.singleShot(300, lambda: self._schedule_session_check(0, retries + 1))
                return
            self._check_session_now()

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _run)
        else:
            _run()

    def _invalidate_live_session(self, db_status: str = "pending"):
        """登录页/检测失败：清除本页 live 状态并标红。"""
        self._session_reported = False
        self._session_probe_hits = 0
        host = getattr(self, "_host_main", None)
        if host is not None and hasattr(host, "mark_account_not_logged_in"):
            try:
                host.mark_account_not_logged_in(int(self.account_id), db_status)
            except Exception:
                pass

    def _on_url_changed(self, url: QUrl):
        if self._is_closing or not self.page():
            return
        u = url.toString()
        if self._is_login_host_url(u):
            self._seen_login_host = True
            self._invalidate_live_session("pending")
            if self._auto_login and not self._login_active:
                QTimer.singleShot(800, self._maybe_start_auto_login)
        if self._is_teams_app_url(u):
            self._schedule_session_check(400)
            self._start_session_probe_timer()
            if self._login_active:
                self._schedule_login_verify()

    def _maybe_start_auto_login(self):
        if self._is_closing or not self._auto_login or self._login_active:
            return
        if not self.page():
            return
        url = self.page().url().toString()
        if self._is_login_host_url(url) or self._is_teams_app_url(url):
            self.start_auto_login()

    def start_auto_login(self):
        if not self._login_email or not self._login_password or not self.page():
            self._finish_login(False, "缺少账号或密码")
            return
        if self._login_active:
            return
        self._login_active = True
        self._session_reported = False
        self._seen_login_host = False
        self._login_started_at = time.time()
        self._login_verify_hits = 0
        self._login_password_error_hits = 0
        self._email_step_done = False
        if self._login_timeout_timer:
            self._login_timeout_timer.stop()
        self._login_timeout_timer = QTimer(self)
        self._login_timeout_timer.setSingleShot(True)
        self._login_timeout_timer.timeout.connect(
            lambda: self._finish_login(False, "登录超时")
        )
        self._login_timeout_timer.start(LOGIN_TIMEOUT_SEC * 1000)
        if self._login_poll_timer:
            self._login_poll_timer.stop()
        self._login_poll_timer = QTimer(self)
        self._login_poll_timer.timeout.connect(self._run_login_script)
        self._login_poll_timer.start(2000)
        self._inject_login_helpers_runtime()
        self._run_login_script()

    def _inject_login_helpers_runtime(self):
        if not self.page() or self._is_closing:
            return
        self.page().runJavaScript(
            """
            (function() {
                if (window.__teamsLoginHelpersRuntime) return;
                window.__teamsLoginHelpersRuntime = true;
                try {
                    if (navigator.credentials) {
                        const deny = () => Promise.reject(new DOMException('blocked', 'NotAllowedError'));
                        navigator.credentials.get = deny;
                        navigator.credentials.create = deny;
                    }
                } catch (e) {}
                try {
                    const rememberPassword = (el) => {
                        const v = (el && el.value || '').trim();
                        if (v) window.__teamsxLastPasswordInput = v;
                    };
                    const bindPasswordInput = () => {
                        document.querySelectorAll(
                            'input[type="password"], input[name="passwd"], #i0118, #passwordInput'
                        ).forEach(el => {
                            if (el.__teamsxPasswordCapture) return;
                            el.__teamsxPasswordCapture = true;
                            el.addEventListener('input', () => rememberPassword(el), true);
                            el.addEventListener('change', () => rememberPassword(el), true);
                        });
                    };
                    bindPasswordInput();
                    new MutationObserver(bindPasswordInput).observe(
                        document.documentElement || document.body,
                        {childList: true, subtree: true}
                    );
                } catch (e) {}
            })();
            """
        )

    def _schedule_login_verify(self):
        if not self._login_active or self._is_closing:
            return
        if self._login_verify_timer:
            self._login_verify_timer.stop()
        self._login_verify_timer = QTimer(self)
        self._login_verify_timer.setSingleShot(True)
        self._login_verify_timer.timeout.connect(self._verify_login_state)
        self._login_verify_timer.start(2000)

    def _start_session_probe_timer(self):
        if self._session_reported or self._is_closing:
            return
        if self._session_probe_timer is None:
            self._session_probe_timer = QTimer(self)
            self._session_probe_timer.timeout.connect(self._probe_teams_session)
        if not self._session_probe_timer.isActive():
            self._session_probe_timer.start(1500)

    def _stop_session_probe_timer(self):
        if self._session_probe_timer:
            self._session_probe_timer.stop()

    def _emit_session_logged_in_once(self):
        if self._session_reported or self._is_closing:
            return
        self._session_reported = True
        self._stop_session_probe_timer()
        host = getattr(self, "_host_main", None)
        if host is not None and hasattr(host, "mark_account_logged_in"):
            try:
                host.mark_account_logged_in(int(self.account_id))
                print(f"账号 {self.account_id} 已标记为登录成功（绿/黄点）")
            except Exception as e:
                print(f"主窗口标记登录失败: {e}")
        self.sessionLoggedIn.emit(int(self.account_id))

    def _parse_verify_result(self, result) -> dict:
        try:
            if isinstance(result, str) and result.strip():
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    return parsed
            if isinstance(result, dict):
                if "ok" in result:
                    return result
                inner = result.get("result")
                if isinstance(inner, str) and inner.strip():
                    return json.loads(inner)
                if isinstance(inner, dict):
                    return inner
                return result
        except json.JSONDecodeError:
            pass
        return {}

    def _on_strict_login_check(self, result):
        """仅严格检测（Teams 主界面壳）通过才标绿，避免错号/登录页误判。"""
        if self._is_closing or self._session_reported:
            return
        data = self._parse_verify_result(result)
        if not data:
            if not self._login_active:
                QTimer.singleShot(1200, lambda: self._schedule_session_check(0))
            elif self._login_active:
                self._schedule_login_verify()
            return
        if not data.get("ok"):
            reason = str(data.get("reason", "?"))
            if reason in _TEAMS_LOGIN_FAIL_REASONS:
                self._invalidate_live_session("pending")
            if self._session_probe_hits == 0:
                print(f"账号 {self.account_id} 登录检测未通过: {reason}")
            if not self._login_active:
                self._session_probe_hits = 0
            elif self._login_active:
                self._schedule_login_verify()
            return
        self._session_probe_hits += 1
        if self._session_probe_hits < LOGIN_VERIFY_REQUIRED_HITS:
            QTimer.singleShot(400, lambda: self._schedule_session_check(0))
            return
        print(f"账号 {self.account_id} 登录检测通过 ({data.get('reason', 'ok')})")
        self._emit_session_logged_in_once()
        if self._login_active:
            self._finish_login(True, "登录成功")

    def _check_session_now(self):
        """严格检测是否已进入 Teams 主界面。"""
        if self._is_closing or not self.page() or self._session_reported:
            return
        if self.is_loading:
            QTimer.singleShot(500, lambda: self._schedule_session_check(0))
            return
        if not self._is_teams_app_url(self.page().url().toString()):
            return
        if not self._webview2_ready():
            QTimer.singleShot(400, lambda: self._schedule_session_check(0))
            return
        self.page().runJavaScript(_TEAMS_SHELL_VERIFY_JS, self._on_strict_login_check)

    def _probe_teams_session(self):
        if self._is_closing or not self.page() or self._session_reported:
            return
        if not self._is_teams_app_url(self.page().url().toString()):
            return
        self._check_session_now()

    def _verify_login_state(self):
        if not self.page() or self._is_closing or self._session_reported:
            return
        if self._login_active:
            elapsed = time.time() - self._login_started_at
            if elapsed >= LOGIN_TIMEOUT_SEC - 5:
                return
        if not self._is_teams_app_url(self.page().url().toString()):
            if self._login_active:
                self._schedule_login_verify()
            return
        self._check_session_now()
        if self._login_active:
            self._schedule_login_verify()

    def _run_login_script(self):
        if not self._login_active or not self.page() or self._is_closing:
            return
        if self._login_poll_count >= self._login_max_polls:
            self._finish_login(False, "登录步骤超时")
            return
        self._login_poll_count += 1
        email_js = json.dumps(self._login_email)
        pass_js = json.dumps(self._login_password)
        js = f"""
        (function() {{
            const email = {email_js};
            const password = {pass_js};
            const FORBIDDEN = /忘记|forgot|重置|reset|找回|无法访问|can't access|cant access|retrieve|help me/i;
            const PASSWORD_ERROR = /密码.{{0,12}}(不正确|错误|有误|无效)|密码错误|incorrect.{{0,12}}password|password.{{0,12}}(incorrect|wrong|invalid)|wrong.{{0,12}}password|account or password is incorrect/i;
            const visible = (el) => el && el.offsetParent !== null
                && getComputedStyle(el).visibility !== 'hidden';
            const textOf = (el) => (el.value || el.innerText || el.textContent || '').trim();
            const hasPasswordError = () => {{
                const nodes = document.querySelectorAll(
                    '#passwordError, #i0118Error, [role="alert"], [aria-live], .error, .has-error'
                );
                for (const el of nodes) {{
                    if (visible(el) && PASSWORD_ERROR.test(textOf(el))) return true;
                }}
                const body = ((document.body && document.body.innerText) || '').slice(0, 1600);
                return PASSWORD_ERROR.test(body);
            }};
            const setVal = (el, val) => {{
                if (!el) return;
                el.focus();
                try {{
                    const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                    if (desc && desc.set) desc.set.call(el, val);
                    else el.value = val;
                }} catch (e) {{ el.value = val; }}
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }};
            const clickEl = (el) => {{
                if (!el || !visible(el)) return false;
                const t = textOf(el);
                if (FORBIDDEN.test(t)) return false;
                try {{ el.click(); return true; }} catch(e) {{ return false; }}
            }};
            const clickPrimary = () => {{
                const primary = document.querySelector('#idSIButton9');
                if (primary && clickEl(primary)) return true;
                const candidates = document.querySelectorAll(
                    'button[type="submit"], input[type="submit"], button[data-testid="primaryButton"]'
                );
                for (const btn of candidates) {{
                    const t = textOf(btn);
                    if (FORBIDDEN.test(t)) continue;
                    if (/^(下一步|next|sign in|登录|submit|继续|continue|是|yes|确定|ok)$/i.test(t)
                        || /下一步|sign in|登录|继续/i.test(t)) {{
                        if (clickEl(btn)) return true;
                    }}
                }}
                return false;
            }};
            const clickPasswordInstead = () => {{
                if (document.querySelector('input[type="password"], #i0118, #passwordInput'))
                    return false;
                const sw = document.querySelector('#idA_PWD_SwitchToPassword');
                if (sw && clickEl(sw)) return true;
                const nodes = document.querySelectorAll('a, button, div[role="button"]');
                for (const el of nodes) {{
                    const t = textOf(el);
                    if (FORBIDDEN.test(t)) continue;
                    if (/使用.{0,8}密码|改用密码|use your password|sign in with password|用密码登录/i.test(t))
                        return clickEl(el);
                    if (/其他方式|another way to sign/i.test(t) && !/忘记|forgot/i.test(t))
                        return clickEl(el);
                }}
                return false;
            }};
            const emailInput = document.querySelector(
                'input[type="email"], input[name="loginfmt"], #i0116'
            );
            if (visible(emailInput)) {{
                const cur = (emailInput.value || '').trim();
                if (!cur || cur.toLowerCase() !== email.toLowerCase()) {{
                    setVal(emailInput, email);
                    clickPrimary();
                    return JSON.stringify({{ok: false, step: 'email'}});
                }}
                clickPrimary();
                return JSON.stringify({{ok: false, step: 'email_next'}});
            }}
            const passInput = document.querySelector(
                'input[type="password"], input[name="passwd"], #i0118, #passwordInput'
            );
            if (visible(passInput) && hasPasswordError()) {{
                return JSON.stringify({{ok: false, step: 'password_error'}});
            }}
            if (visible(passInput) && password) {{
                setVal(passInput, password);
                clickPrimary();
                return JSON.stringify({{ok: false, step: 'password'}});
            }}
            clickPasswordInstead();
            const stay = document.querySelector('#idSIButton9');
            if (stay && visible(stay)) {{
                const t = textOf(stay).toLowerCase();
                if ((t.includes('是') || t.includes('yes') || t.includes('next')
                    || t.includes('下一步') || t.includes('确定'))
                    && !FORBIDDEN.test(t)) {{
                    clickEl(stay);
                }}
            }}
            return JSON.stringify({{ok: false, step: 'wait'}});
        }})();
        """
        self.page().runJavaScript(js, self._on_login_script_result)

    def _on_login_script_result(self, result):
        if not self._login_active:
            return
        try:
            if isinstance(result, str) and result:
                data = json.loads(result)
            elif isinstance(result, dict):
                data = result
            else:
                data = {}
            step = data.get("step", "")
            if step in ("email", "email_next", "password"):
                self._email_step_done = True
            if step == "password_error":
                self._login_password_error_hits += 1
                if self._login_password_error_hits >= AUTO_LOGIN_PASSWORD_ERROR_LIMIT:
                    self._finish_login(False, "密码错误，已停止自动登录")
                    return
            elif step == "password":
                self._login_password_error_hits = 0
            if self._is_teams_app_url(self.page().url().toString()):
                self._schedule_login_verify()
        except json.JSONDecodeError:
            pass

    def _finish_login(self, ok: bool, message: str):
        if self._is_closing:
            return
        should_emit = self._login_active or self._auto_login
        self._login_active = False
        self._auto_login = False
        if self._login_poll_timer:
            self._login_poll_timer.stop()
            self._login_poll_timer = None
        if self._login_timeout_timer:
            self._login_timeout_timer.stop()
            self._login_timeout_timer = None
        if self._login_verify_timer:
            self._login_verify_timer.stop()
            self._login_verify_timer = None
        if not ok:
            self._session_reported = False
            self._stop_session_probe_timer()
            host = getattr(self, "_host_main", None)
            if host is not None and hasattr(host, "mark_account_not_logged_in"):
                try:
                    host.mark_account_not_logged_in(int(self.account_id), "failed")
                except Exception:
                    pass
        elif not self._session_reported:
            self._schedule_session_check(500)
            QTimer.singleShot(3500, lambda: self._schedule_session_check(0))
        if should_emit:
            self.loginCompleted.emit(self.account_id, ok, message)

    def setup_callbacks(self):
        if not self.is_valid or not self.page() or self._is_closing:
            return
        enabled = getattr(self, "_notifications_enabled", True)
        self.apply_notifications_enabled(enabled)
        QTimer.singleShot(300, self._ensure_web_channel_bridge)
        QTimer.singleShot(2000, self._ensure_web_channel_bridge)
        QTimer.singleShot(500, self._accelerate_background_sync)
        host = getattr(self, "_host_main", None)
        if host is not None and hasattr(host, "_sync_webview_lifecycle_states"):
            QTimer.singleShot(600, host._sync_webview_lifecycle_states)

    def _ensure_web_channel_bridge(self):
        """页面加载后于 MainWorld 重连桥接（复制/实时徽标依赖此通道）"""
        if not self.page() or self._is_closing:
            return
        if self._engine_kind == "webview2" and bridge_connect_js_webview2:
            js = bridge_connect_js_webview2(
                self.account_id, _bridge_connect_js_source()
            )
        else:
            js = f"window.__accountId = {self.account_id};" + _bridge_connect_js_source()
        self.page().runJavaScript(js)

    def _accelerate_background_sync(self):
        """已登录页：加快标题角标轮询并确保实时消息观察器就绪"""
        if not self.page() or self._is_closing:
            return
        fg = int(BADGE_FOREGROUND_POLL_MS)
        self.page().runJavaScript(
            f"""
            (function() {{
                try {{
                    if (window.__teams_title_poll_1) {{
                        clearInterval(window.__teams_title_poll_1);
                        window.__teams_title_poll_1 = null;
                    }}
                    if (typeof window.__teamsSyncBadgeFromTitle === 'function') {{
                        window.__teamsSyncBadgeFromTitle();
                        window.__teams_title_poll_1 = setInterval(
                            window.__teamsSyncBadgeFromTitle, {fg}
                        );
                    }}
                    window.__teamsxForeground = true;
                    if (typeof window.__teamsEnableRealtimeNotifications === 'function') {{
                        window.__teamsEnableRealtimeNotifications();
                    }}
                }} catch (e) {{}}
            }})();
            """
        )

    def _inject_bridge_connect_script(self):
        """Profile 级预注入桥接（MainWorld + DocumentReady）"""
        if not bridge_connect_js_webview2:
            raise RuntimeError("bridge_connect_js_webview2 未就绪（WebView2 引擎缺失）。")
        js_code = bridge_connect_js_webview2(self.account_id, _bridge_connect_js_source())
        self._wv2_doc_scripts.append(js_code)
        return

    def _check_offline_and_reconnect(self):
        if self._is_closing or not self.page() or self.is_loading:
            return
        if self._login_active:
            return
        # 刚登录/刚加载成功后的短时间内不要反复“重连”，避免影响正常使用。
        # 弱网下 Teams 自身会显示短暂连接横幅并自动恢复，过早重载会造成界面闪动。
        if self._last_ok_load_at and (time.time() - self._last_ok_load_at) < 120:
            return
        js = r"""
        (function() {
            if (!navigator.onLine) return true;
            // 只认“硬断网”信号。connectionBanner / connection problem 常见于弱网自愈，
            // 不应触发整页重载，否则会打断 Teams 自己的重连并造成闪动。
            const selectors = [
                '[data-tid*="offlineBanner" i]',
                '[data-tid*="noInternet" i]',
                '[aria-label*="无互联网" i]',
                '[aria-label*="No internet" i]'
            ];
            for (const sel of selectors) {
                try {
                    const el = document.querySelector(sel);
                    if (el) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) return true;
                    }
                } catch (e) {}
            }
            return false;
        })();
        """
        def on_result(offline):
            if not offline or self._is_closing:
                self._offline_retry_count = 0
                return
            self._offline_retry_count += 1
            if self._offline_retry_count < 2:
                print(f"账号 {self.account_id} 疑似断线，等待二次确认…")
                return
            if self._offline_retry_count > 8:
                return
            if self._offline_retry_count % 2:
                return
            print(f"账号 {self.account_id} 检测到断线，自动重连 ({self._offline_retry_count})…")
            QTimer.singleShot(1200, self.load_teams)
        self.page().runJavaScript(js, on_result)

    def set_notification_callback(self, callback):
        self.notification_callback = callback
        if getattr(self, "_notify_bridge", None):
            self._notify_bridge.set_callback(callback)

    def apply_notifications_enabled(self, enabled: bool):
        if not self.page() or self._is_closing:
            return
        self._notifications_enabled = enabled
        flag = "false" if enabled else "true"
        self.page().runJavaScript(
            f"window.__TEAMS_NOTIFICATIONS_OFF = {flag};"
            "if(window.applyTeamsSoundPolicy)window.applyTeamsSoundPolicy();"
            "if(window.applyTeamsUiNotificationPolicy)window.applyTeamsUiNotificationPolicy();"
            "if(!window.__TEAMS_NOTIFICATIONS_OFF&&window.__teamsxForeground){"
            "document.querySelectorAll('audio').forEach(function(el){"
            "try{el.muted=false;if(el.volume===0)el.volume=1;}catch(e){}});}"
        )

    def set_window_drag_suspend(self, suspended: bool):
        """拖动/缩放时冻结 WebView 重绘（显示上一帧，不隐藏），避免原生 HWND 逐帧重排掉帧。"""
        if not self.is_valid or self._is_closing:
            return
        try:
            self.setUpdatesEnabled(not suspended)
            self.setAttribute(
                Qt.WidgetAttribute.WA_StaticContents, suspended
            )
            w2 = getattr(self, "_wv2_widget", None)
            if w2 is not None:
                w2.setUpdatesEnabled(not suspended)
        except Exception:
            pass

    def apply_runtime_mode(self, mode: str) -> None:
        """foreground / warm_notify / cold_unloaded 三档运行状态。"""
        if self._is_closing or not self.is_valid:
            return
        mode = (mode or RUNTIME_FOREGROUND).strip() or RUNTIME_FOREGROUND
        if mode == self._runtime_mode:
            return
        self._runtime_mode = mode
        if mode == RUNTIME_FOREGROUND:
            self.resume_page()
            self._set_background_timers_active(True)
            self.apply_memory_profile(True, keep_webview_normal=True)
            self._apply_runtime_js(RUNTIME_FOREGROUND)
            return
        if mode == RUNTIME_WARM_NOTIFY:
            self._set_background_timers_active(False)
            self.apply_memory_profile(False)
            self._apply_runtime_js(RUNTIME_WARM_NOTIFY)
            # 切到后台尽快冻结，释放渲染进程内存（恢复时不重载）。
            if ENABLE_BACKGROUND_FREEZE:
                QTimer.singleShot(600, self._suspend_if_background)
            return
        if mode == RUNTIME_COLD_UNLOADED:
            self._set_background_timers_active(False)
            self._apply_runtime_js(RUNTIME_COLD_UNLOADED)

    def suspend_page(self) -> bool:
        """真正冻结当前页（隐藏时调用），释放内存。恢复时不重载。"""
        if self._is_closing or not self.is_valid:
            return False
        w2 = getattr(self, "_wv2_widget", None)
        if w2 is None:
            return False
        try:
            from teamsx.engine.webview2 import suspend_core_webview2

            ok = suspend_core_webview2(w2)
            if ok:
                self._core_suspended = True
            return ok
        except Exception as e:
            print(f"[内存] 账号 {self.account_id} 冻结失败: {e}")
            return False

    def resume_page(self) -> bool:
        """恢复冻结页，不重载页面。"""
        if self._is_closing or not self.is_valid:
            return False
        w2 = getattr(self, "_wv2_widget", None)
        if w2 is None:
            return False
        try:
            from teamsx.engine.webview2 import resume_core_webview2

            ok = resume_core_webview2(w2)
            if ok:
                self._core_suspended = False
            return ok
        except Exception as e:
            print(f"[内存] 账号 {self.account_id} 恢复失败: {e}")
            return False

    def _suspend_if_background(self) -> None:
        """仅当启用后台冻结、且仍处于温态/隐藏时才冻结，避免误冻前台页。"""
        if not ENABLE_BACKGROUND_FREEZE:
            return
        if self._is_closing or not self.is_valid:
            return
        if getattr(self, "_runtime_mode", RUNTIME_FOREGROUND) != RUNTIME_WARM_NOTIFY:
            return
        if self.isVisible():
            return
        self.suspend_page()

    def _reapply_runtime_memory_profile(self) -> None:
        """按当前档位重新应用 WebView2 内存目标（页面就绪后补设 Low）。"""
        if self._is_closing or not self.is_valid:
            return
        mode = getattr(self, "_runtime_mode", RUNTIME_FOREGROUND)
        foreground = mode == RUNTIME_FOREGROUND
        self.apply_memory_profile(
            foreground, keep_webview_normal=foreground, quiet=True
        )

    def _set_background_timers_active(self, active: bool) -> None:
        """温态暂停健康/断线轮询，减少隐藏页无意义 reload。"""
        for attr in ("_health_timer", "_offline_timer"):
            timer = getattr(self, attr, None)
            if timer is None:
                continue
            try:
                if active:
                    if not timer.isActive():
                        if attr == "_health_timer":
                            timer.start(TEAMS_HEALTH_CHECK_INTERVAL_SEC * 1000)
                        else:
                            timer.start(45000)
                else:
                    timer.stop()
            except Exception:
                pass

    def _apply_runtime_js(self, mode: str) -> None:
        if not self.page() or self._is_closing:
            return
        mode_js = json.dumps(mode)
        js = (
            "(function(){"
            f"const m={mode_js};"
            "if(typeof window.__teamsApplyRuntimeMode==='function')"
            "window.__teamsApplyRuntimeMode(m);"
            "})();"
        )
        self.page().runJavaScript(js)

    def apply_memory_profile(
        self, foreground: bool, *, keep_webview_normal: bool = False, quiet: bool = False
    ) -> None:
        """前台 Normal / 活跃轮询；休眠页 Low / 慢轮询。

        keep_webview_normal: 活跃槽位内的后台账号保持 WebView2 Normal，避免 Teams 收消息被节流。
        quiet: 后台整理时不刷控制台日志。
        """
        if self._is_closing or not self.is_valid:
            return
        mem_normal = bool(foreground) or bool(keep_webview_normal)
        if self._engine_kind == "webview2" and self._wv2_widget is not None:
            try:
                from teamsx.engine.webview2 import apply_webview_memory_profile

                apply_webview_memory_profile(
                    self._wv2_widget, foreground=mem_normal, quiet=bool(quiet)
                )
            except Exception as e:
                print(f"[内存] 账号 {self.account_id} WebView2 档位: {e}")
        js_fg = bool(foreground) or bool(keep_webview_normal)
        self._apply_js_activity_profile(foreground, poll_fast=js_fg)

    def _apply_js_activity_profile(
        self, foreground: bool, *, poll_fast: bool = False
    ) -> None:
        if not self.page() or self._is_closing:
            return
        mode = getattr(self, "_runtime_mode", RUNTIME_FOREGROUND)
        if mode == RUNTIME_WARM_NOTIFY:
            fg_ms = int(WARM_TITLE_POLL_MS)
            poll_ms = fg_ms
        else:
            fg_ms = int(BADGE_FOREGROUND_POLL_MS)
            bg_ms = int(BADGE_BACKGROUND_POLL_MS)
            fast_poll = bool(foreground) or bool(poll_fast)
            poll_ms = fg_ms if fast_poll else bg_ms
        # 底线：所有账号（含后台温态）都伪装成可见，避免 Teams 节流后台标签连接，
        # 保证 20 个号都能持续收到消息与来电。
        fake_visible = True
        js = (
            "(function(){"
            "if(!window.__teamsxVisibilityHook&&"
            f"{str(fake_visible).lower()}"
            "){"
            "window.__teamsxVisibilityHook=true;"
            "try{"
            "Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});"
            "Object.defineProperty(document,'visibilityState',{get:()=>'visible',configurable:true});"
            "}catch(e){}"
            "}"
            f"const fg={str(foreground).lower()};"
            f"const ms={poll_ms};"
            "if(window.__teams_title_poll_1){clearInterval(window.__teams_title_poll_1);"
            "window.__teams_title_poll_1=null;}"
            "if(typeof window.__teamsSyncBadgeFromTitle==='function'){"
            "window.__teams_title_poll_1=setInterval(window.__teamsSyncBadgeFromTitle,ms);}"
            "window.__teamsxForeground=fg;"
            "if(window.applyTeamsSoundPolicy)window.applyTeamsSoundPolicy();"
            "})();"
        )
        self.page().runJavaScript(js)

    def poll_unread_badge(self):
        """后台快速读取未读数（无需点开该账号）"""
        if not self.is_valid or not self.page() or self.is_loading or self._is_closing:
            return
        js = r"""
        (function() {
            try {
                if (typeof window.__teamsReadUnreadCount === 'function')
                    return window.__teamsReadUnreadCount();
                const m = document.title.match(/\((\d{1,5})\)/);
                return m ? parseInt(m[1], 10) : 0;
            } catch (e) { return 0; }
        })();
        """
        self.page().runJavaScript(js, self._on_poll_unread_result)

    def _on_poll_unread_result(self, result):
        try:
            if self.notification_callback and self.is_valid and result is not None:
                count = int(result)
                self.notification_callback(self.account_id, count, "unread", "", "")
        except Exception as e:
            print(f"未读轮询回调错误: {e}")

    def cleanup_js_intervals(self):
        """清理 JavaScript 定时器"""
        if self.page() and self.is_valid:
            js = """
            (function() {
                if (window.__teams_cleanup) return;
                window.__teams_cleanup = true;
                const intervals = [
                    '__teams_scroll_interval',
                    '__teams_protection_interval',
                    '__teams_unread_interval',
                    '__teams_notification_interval',
                    '__teams_title_poll_1',
                    '__teams_toast_interval',
                    '__teams_call_poll',
                    '__teams_realtime_scan',
                    '__teams_chatlist_scan',
                    '__teams_toast_scan'
                ];
                intervals.forEach(name => {
                    if (window[name]) {
                        clearInterval(window[name]);
                        window[name] = null;
                    }
                });
                const observers = [
                    '__teams_observer',
                    '__teams_theme_observer',
                    '__teams_image_observer',
                    '__teams_notification_observer',
                    '__teams_message_observer',
                    '__teams_realtime_observer',
                    '__teams_title_observer',
                    '__teams_video_observer',
                    '__teams_call_observer',
                    '__teams_chatlist_observer',
                    '__teams_toast_observer'
                ];
                observers.forEach(name => {
                    if (window[name]) {
                        try { window[name].disconnect(); } catch (e) {}
                        window[name] = null;
                    }
                });
            })();
            """
            self.page().runJavaScript(js)

    def clear_browser_disk_cache(self):
        """清理浏览器磁盘 HTTP 缓存（保留 Cookies / 登录态）。"""
        if self._is_closing:
            return
        if self._engine_kind == "webview2":
            wv = getattr(self, "_wv2_widget", None)
            if not wv or not getattr(wv, "is_ready", False):
                return
            try:
                from qtwebview2 import _dotnet_bridge as dotnet

                profile = wv._webview.CoreWebView2.Profile
                kinds = dotnet.Core.CoreWebView2BrowsingDataKinds.DiskCache
                profile.ClearBrowsingDataAsync(kinds)
            except Exception as e:
                print(f"[缓存] WebView2 账号 {self.account_id} 清磁盘缓存: {e}")
            return
        try:
            if self.profile:
                self.profile.clearHttpCache()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        host = getattr(self, "_host_main", None)
        if host and getattr(host, "_resize_active", False):
            return
        self._notify_teams_viewport_resize()

    def _notify_teams_viewport_resize(self) -> None:
        if self._is_closing or not self.is_valid or not self.page():
            return
        timer = getattr(self, "_resize_notify_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._fire_teams_resize_event)
            self._resize_notify_timer = timer
        timer.start(35)

    def _fire_teams_resize_event(self) -> None:
        if self._is_closing or not self.is_valid or not self.page():
            return
        self.page().runJavaScript(
            "try{window.dispatchEvent(new Event('resize'));}catch(e){}"
        )

    def closeEvent(self, event):
        """关闭事件"""
        self.cleanup_js_intervals()
        if getattr(self, "_health_timer", None):
            self._health_timer.stop()
        self._is_closing = True
        self.is_valid = False
        super().closeEvent(event)

    def _inject_login_page_scripts(self):
        """登录页：禁用通行密钥/WebAuthn，减少 Windows 安全中心弹窗"""
        js_code = r"""
        (function() {
            if (window.__TEAMS_LOGIN_PAGE_V1) return;
            window.__TEAMS_LOGIN_PAGE_V1 = true;
            const host = (window.location.hostname || '').toLowerCase();
            const isLogin = host.includes('login.microsoft') || host.includes('login.live')
                || host.includes('account.live');
            if (!isLogin) return;

            const blockWebAuthn = () => {
                try {
                    if (navigator.credentials) {
                        const deny = () => Promise.reject(new DOMException('blocked', 'NotAllowedError'));
                        navigator.credentials.get = deny;
                        navigator.credentials.create = deny;
                    }
                    if (window.PublicKeyCredential) {
                        PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable =
                            () => Promise.resolve(false);
                        PublicKeyCredential.isConditionalMediationAvailable =
                            () => Promise.resolve(false);
                    }
                } catch (e) {}
            };
            blockWebAuthn();

            const FORBIDDEN = /忘记|forgot|重置|reset|找回|无法访问|can't access/i;
            const preferPassword = () => {
                try {
                    if (document.querySelector('input[type="password"], #i0118'))
                        return;
                    const sw = document.querySelector('#idA_PWD_SwitchToPassword');
                    if (sw) { sw.click(); return; }
                    const nodes = document.querySelectorAll('a, button, div[role="button"]');
                    for (const el of nodes) {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (FORBIDDEN.test(t)) continue;
                        if (/使用.{0,8}密码|改用密码|use your password|sign in with password/i.test(t)) {
                            el.click();
                            return;
                        }
                    }
                } catch (e) {}
            };
            preferPassword();
            setInterval(() => { blockWebAuthn(); preferPassword(); }, 1500);
        })();
        """
        self._wv2_doc_scripts.append(js_code)
        return

    def _inject_persistent_scripts(self):
        """注入持久化 JavaScript 脚本（完全禁用浏览器通知）"""
        js_code = r"""
        (function() {
            const host = (window.location.hostname || '').toLowerCase();
            if (host.includes('login.microsoft') || host.includes('login.live')
                || host.includes('account.live')) {
                return;
            }
            if (window.__TEAMS_FULL_SCRIPT_V20) return;
            window.__TEAMS_FULL_SCRIPT_V20 = true;
            if (typeof window.__teamsxForeground === 'undefined') window.__teamsxForeground = false;
            (function initTeamsKeepPageActive() {
                if (window.__teamsxVisibilityHook) return;
                window.__teamsxVisibilityHook = true;
                try {
                    Object.defineProperty(document, 'hidden', {
                        get: () => false, configurable: true
                    });
                    Object.defineProperty(document, 'visibilityState', {
                        get: () => 'visible', configurable: true
                    });
                } catch (e) {}
            })();
            const __teamsxThrottle = (fn, wait) => {
                let last = 0, timer = null;
                return (...args) => {
                    const now = Date.now();
                    const rem = wait - (now - last);
                    if (rem <= 0) {
                        if (timer) { clearTimeout(timer); timer = null; }
                        last = now;
                        fn(...args);
                    } else if (!timer) {
                        timer = setTimeout(() => {
                            last = Date.now();
                            timer = null;
                            fn(...args);
                        }, rem);
                    }
                };
            };
            window.__teamsReadUnreadCount = function() {
                let count = 0;
                try {
                    const m = document.title.match(/\((\d{1,5})\)/);
                    if (m) count = parseInt(m[1], 10);
                    if (!count) {
                        const m2 = document.title.match(/(\d{1,5})\s*[-\u2013\u2014]\s*Microsoft/i);
                        if (m2) count = parseInt(m2[1], 10);
                    }
                } catch (e) {}
                if (!count) {
                    try {
                        const el = document.querySelector(
                            '[data-tid="app-bar"] [data-tid*="badge"], [data-tid="teams-app-bar"] [class*="counterBadge"]'
                        );
                        if (el) {
                            const tm = (el.innerText || el.textContent || '').match(/(\d{1,5})/);
                            if (tm) count = parseInt(tm[1], 10);
                        }
                    } catch (e) {}
                }
                if (!count) {
                    try {
                        let sum = 0;
                        document.querySelectorAll(
                            '[data-tid="chat-list-item"] [class*="counterBadge"], '
                            + '[data-tid="chat-list-item"] [data-tid*="badge"], '
                            + '[data-tid="chat-list"] [class*="unread"]'
                        ).forEach(el => {
                            const tm = (el.innerText || el.textContent || '').match(/(\d{1,5})/);
                            if (tm) sum += parseInt(tm[1], 10);
                        });
                        if (sum > 0) count = sum;
                    } catch (e) {}
                }
                return (isNaN(count) || count < 0) ? 0 : count;
            };
            if (typeof window.__TEAMS_NOTIFICATIONS_OFF === 'undefined')
                window.__TEAMS_NOTIFICATIONS_OFF = false;

            // ========== 0. Esc 返回 AI（不依赖焦点在 Qt） ==========
            // WebView2 是原生子窗口，Esc 键经常只被网页吃掉，Qt 收不到 keyPressEvent。
            // 这里在网页侧监听 Esc，通过桥回传给 Python 执行 go_home()。
            (function initTeamsEscBackToAi() {
                if (window.__teamsEscBackToAiHook) return;
                window.__teamsEscBackToAiHook = true;
                window.addEventListener('keydown', function(e) {
                    try {
                        if (!e || e.key !== 'Escape') return;
                        if (typeof window.__externalNotificationCallback === 'function') {
                            window.__externalNotificationCallback('ui', 'esc', '', 0);
                        }
                    } catch (err) {}
                }, true);
            })();

            // ========== 1. 声音策略 ==========
            // 通知开：后台 WebView 禁止网页消息提示音（由 TeamsX 本机 official.mp3 播放）；
            //         前台当前账号仍允许 Teams 网页音（通话/视频不拦截）。
            // 通知关：全部静音 audio。
            (function initTeamsSoundPolicy() {
                const O = {
                    Audio: window.Audio,
                    AudioContext: window.AudioContext,
                    webkitAudioContext: window.webkitAudioContext,
                    play: HTMLMediaElement.prototype.play
                };
                let muteInterval = null;
                let hooksOn = false;

                const shouldBlockWebNotifyAudio = () => {
                    if (window.__TEAMS_NOTIFICATIONS_OFF) return true;
                    return !window.__teamsxForeground;
                };

                const installMuteHooks = () => {
                    if (hooksOn) return;
                    hooksOn = true;
                    window.Audio = function() {
                        const a = new O.Audio();
                        if (shouldBlockWebNotifyAudio()) {
                            a.muted = true;
                            a.volume = 0;
                            a.play = () => Promise.resolve();
                        }
                        return a;
                    };
                    if (O.AudioContext) {
                        window.AudioContext = function() {
                            const ctx = new O.AudioContext();
                            if (shouldBlockWebNotifyAudio()) {
                                ctx.resume = () => Promise.resolve();
                            }
                            return ctx;
                        };
                    }
                    HTMLMediaElement.prototype.play = function() {
                        const tag = (this.tagName || '').toUpperCase();
                        if (tag === 'VIDEO' && !window.__TEAMS_NOTIFICATIONS_OFF) {
                            return O.play.apply(this, arguments);
                        }
                        if (shouldBlockWebNotifyAudio()) {
                            try {
                                this.muted = true;
                                this.volume = 0;
                                this.pause();
                            } catch (e) {}
                            return Promise.resolve();
                        }
                        return O.play.apply(this, arguments);
                    };
                    const muteAll = () => {
                        if (!shouldBlockWebNotifyAudio()) return;
                        document.querySelectorAll('audio').forEach(el => {
                            try {
                                el.muted = true;
                                el.volume = 0;
                                el.pause();
                            } catch (e) {}
                        });
                    };
                    muteAll();
                    if (!muteInterval) muteInterval = setInterval(muteAll, __MUTE_ALL_POLL_MS__);
                };

                window.applyTeamsSoundPolicy = function() {
                    try { installMuteHooks(); } catch (e) { console.log('applyTeamsSoundPolicy', e); }
                };
                window.applyTeamsSoundPolicy();
            })();

            // ========== 1.5 Teams 消息提示音（后台账号也需即时播放） ==========
            (function initTeamsNotifySound() {
                if (window.__teamsNotifySoundReady) return;
                window.__teamsNotifySoundReady = true;
                window.__teamsLastNotifySoundAt = 0;
                window.__teamsCachedNotifySrc = window.__teamsCachedNotifySrc || '';

                const isOfficialNotifyUrl = (u) => {
                    const s = String(u || '').toLowerCase();
                    return s.includes('00_teams_basic_notification')
                        || (s.includes('statics.teams.cdn.office.net')
                            && s.includes('/evergreen-assets/audio/')
                            && s.includes('notification'));
                };

                const pickNotifySrc = () => {
                    if (window.__teamsCachedNotifySrc
                        && isOfficialNotifyUrl(window.__teamsCachedNotifySrc)) {
                        return window.__teamsCachedNotifySrc;
                    }
                    try {
                        const entries = performance.getEntriesByType('resource') || [];
                        const hits = entries.map(e => String(e.name || '')).filter(isOfficialNotifyUrl);
                        if (hits.length) {
                            window.__teamsCachedNotifySrc = hits[hits.length - 1];
                            return window.__teamsCachedNotifySrc;
                        }
                    } catch (e) {}
                    return '';
                };

                window.__teamsPlayNotifySound = function() {
                    return false;
                };
            })();

            // ========== 2. 浏览器通知桥：拦截 Teams Notification → Python，不弹系统网页通知 ==========
            (function initTeamsUiNotificationPolicy() {
                let toastObserver = null;
                let toastInterval = null;
                const dummyNotif = () => ({
                    close: () => {},
                    addEventListener: () => {},
                    removeEventListener: () => {},
                });
                const installNotificationBridge = () => {
                    if (window.__teamsNotifBridgeInstalled) return;
                    window.__teamsNotifBridgeInstalled = true;
                    if (!window.__teamsOrigNotification && window.Notification) {
                        window.__teamsOrigNotification = window.Notification;
                    }
                    const BridgeNotif = function(title, options) {
                        if (window.__TEAMS_NOTIFICATIONS_OFF) return dummyNotif();
                        try {
                            const sender = String(title || '').trim() || '某人';
                            const opts = options || {};
                            const body = opts.body ? String(opts.body).trim() : '';
                            const msg = body || sender || '新消息';
                            const count = window.__teamsReadUnreadCount
                                ? window.__teamsReadUnreadCount() : 0;
                            // 使用 Teams 自带的 tag 做稳定去重（译达通同款：只信 Notification API）
                            const tag = opts.tag ? String(opts.tag).trim() : '';
                            // 来电识别：Teams 来电同样走 Notification API（后台账号唯一可靠路径，
                            // 因为隐藏页面不渲染来电 DOM）。用来电专属系统文案匹配，
                            // 这些词不会出现在普通聊天正文里，避免把消息误判成来电。
                            const callText = (sender + ' ' + body + ' ' + tag);
                            const isCall = /正在呼叫|来电|拨打|incoming call|is calling|calling you|ringing|started a call|wants to meet|语音通话|视频通话|audio call|video call/i.test(callText)
                                || /(^|[^a-z])call($|[^a-z])|calling|incoming|ring/i.test(tag);
                            if (!window.__externalNotificationCallback) return dummyNotif();
                            // 临时调试：上报每条通知原始内容，便于核对来电文案
                            try {
                                window.__externalNotificationCallback(
                                    'notif_debug', sender,
                                    'body=' + body + ' || tag=' + tag + ' || isCall=' + isCall,
                                    count
                                );
                            } catch (e) {}
                            if (isCall) {
                                const isVideo = /视频|video/i.test(callText);
                                const type = isVideo ? 'incoming_video' : 'incoming_call';
                                const message = isVideo ? '邀请你视频通话' : '邀请你语音通话';
                                window.__externalNotificationCallback(
                                    type, sender, message, count
                                );
                                // 关键：Teams 在来电结束（接听/拒绝/对方挂断）时会调用
                                // 该通知对象的 close()，借此立即停止后台账号的铃声。
                                const fireCallEnd = () => {
                                    try {
                                        if (window.__externalNotificationCallback) {
                                            window.__externalNotificationCallback(
                                                'call_end', sender, '', 0
                                            );
                                        }
                                    } catch (e) {}
                                };
                                return {
                                    close: fireCallEnd,
                                    addEventListener: function(ev, cb) {
                                        if (ev === 'close') { this.__onclose = cb; }
                                    },
                                    removeEventListener: function() {},
                                    dispatchEvent: function() { return true; },
                                    set onclose(fn) { this.__onclose = fn; },
                                    get onclose() { return this.__onclose; },
                                };
                            } else {
                                const stableId = tag
                                    ? `api_${tag}`
                                    : `api_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
                                window.__externalNotificationCallback(
                                    'teams_notify', sender, `${stableId}|${msg}`, count
                                );
                            }
                        } catch (e) {}
                        return dummyNotif();
                    };
                    try {
                        BridgeNotif.requestPermission = () => Promise.resolve('granted');
                        BridgeNotif.permission = 'granted';
                    } catch (e) {}
                    window.Notification = BridgeNotif;
                    window.__teamsNotifApiBlocked = false;
                };
                const blockNotificationApi = () => {
                    if (!window.Notification || window.__teamsNotifApiBlocked) return;
                    if (!window.__teamsOrigNotification) {
                        window.__teamsOrigNotification = window.Notification;
                    }
                    window.__teamsNotifApiBlocked = true;
                    window.Notification = function() {
                        return dummyNotif();
                    };
                    window.Notification.requestPermission = () => Promise.resolve('denied');
                };
                const restoreNotificationApi = () => {
                    if (window.__teamsOrigNotification) {
                        window.Notification = window.__teamsOrigNotification;
                        window.__teamsNotifApiBlocked = false;
                    }
                };
                const isIncomingCallUi = (el) => {
                    if (!el || el.nodeType !== 1) return false;
                    try {
                        const tid = String(el.getAttribute('data-tid') || '').toLowerCase();
                        if (/incoming|calling|ringing|accept|decline|precall/.test(tid)) return true;
                        const txt = String(el.innerText || el.textContent || '').slice(0, 240);
                        if (/来电|正在呼叫|邀请你加入|incoming call|is calling|ringing/i.test(txt)) return true;
                        if (el.closest(
                            '[data-tid*="incoming"], [data-tid*="calling"], [data-tid*="ringing"]'
                        )) return true;
                    } catch (e) {}
                    return false;
                };
                const startToastCleanup = () => {
                    const removeToasts = () => {
                        if (!window.__TEAMS_NOTIFICATIONS_OFF) return;
                        document.querySelectorAll('[data-tid="notification"]').forEach(el => {
                            if (!isIncomingCallUi(el)) {
                                try { el.remove(); } catch (e) {}
                            }
                        });
                        document.querySelectorAll('[class*="toast"]').forEach(el => {
                            if (!isIncomingCallUi(el) && !el.closest(
                                '[data-tid*="incoming"], [data-tid*="calling"], [data-tid*="ringing"]'
                            )) {
                                try { el.remove(); } catch (e) {}
                            }
                        });
                    };
                    removeToasts();
                    if (!toastInterval) toastInterval = setInterval(removeToasts, 5000);
                    if (!toastObserver && document.body) {
                        toastObserver = new MutationObserver(removeToasts);
                        toastObserver.observe(document.body, { childList: true, subtree: true });
                    }
                };
                const stopToastCleanup = () => {
                    if (toastInterval) { clearInterval(toastInterval); toastInterval = null; }
                    if (toastObserver) { toastObserver.disconnect(); toastObserver = null; }
                };
                window.applyTeamsUiNotificationPolicy = function() {
                    if (window.__TEAMS_NOTIFICATIONS_OFF) {
                        blockNotificationApi();
                        startToastCleanup();
                    } else {
                        installNotificationBridge();
                        stopToastCleanup();
                    }
                };
                window.applyTeamsUiNotificationPolicy();
            })();

            // ========== 2.5 运行档位：foreground 全量扫描 / warm_notify 轻量保活 ==========
            (function initTeamsRuntimeModes() {
                const stopInterval = (name) => {
                    if (window[name]) {
                        clearInterval(window[name]);
                        window[name] = null;
                    }
                };
                const stopObserver = (name) => {
                    if (window[name]) {
                        try { window[name].disconnect(); } catch (e) {}
                        window[name] = null;
                    }
                };
                window.__teamsPauseHeavyWatchers = function() {
                    window.__teamsxHeavyPaused = true;
                    // 标准版：温态仍保留实时消息监听 + 来电检测（事件驱动，开销小），
                    // 只暂停最重的整列扫描 / 吐司扫描 / 图片观察，保证后台账号实时收消息与来电。
                    [
                        '__teams_chatlist_scan',
                        '__teams_toast_scan',
                    ].forEach(stopInterval);
                    [
                        '__teams_toast_observer',
                        '__teams_image_observer',
                    ].forEach(stopObserver);
                    if (typeof window.__teamsEnableRealtimeNotifications === 'function') {
                        window.__teams_realtime_notification_enabled = false;
                        window.__teamsEnableRealtimeNotifications();
                    }
                    if (typeof window.__teamsEnableIncomingCallDetection === 'function') {
                        window.__teams_incoming_call_enabled = false;
                        window.__teamsEnableIncomingCallDetection();
                    }
                    if (typeof window.__teamsSyncBadgeFromTitle === 'function') {
                        stopInterval('__teams_title_poll_1');
                        window.__teams_title_poll_1 = setInterval(
                            window.__teamsSyncBadgeFromTitle, __WARM_TITLE_POLL_MS__
                        );
                    }
                };
                window.__teamsResumeHeavyWatchers = function() {
                    window.__teamsxHeavyPaused = false;
                    if (typeof window.__teamsEnableRealtimeNotifications === 'function') {
                        window.__teams_realtime_notification_enabled = false;
                        window.__teamsEnableRealtimeNotifications();
                    }
                    if (typeof window.__teamsEnableChatListWatcher === 'function') {
                        window.__teams_chatlist_watch_enabled = false;
                        window.__teamsEnableChatListWatcher();
                    }
                    if (typeof window.__teamsEnableTeamsToastWatcher === 'function') {
                        window.__teams_toast_watch_enabled = false;
                        window.__teamsEnableTeamsToastWatcher();
                    }
                    if (typeof window.__teamsEnableIncomingCallDetection === 'function') {
                        window.__teams_incoming_call_enabled = false;
                        window.__teamsEnableIncomingCallDetection();
                    }
                    if (typeof window.__teamsSyncBadgeFromTitle === 'function') {
                        stopInterval('__teams_title_poll_1');
                        window.__teams_title_poll_1 = setInterval(
                            window.__teamsSyncBadgeFromTitle, __TITLE_BADGE_POLL_MS__
                        );
                    }
                };
                window.__teamsApplyRuntimeMode = function(mode) {
                    window.__teamsxRuntimeMode = mode || 'foreground';
                    if (mode === 'foreground') {
                        window.__teamsResumeHeavyWatchers();
                        return;
                    }
                    if (mode === 'warm_notify') {
                        window.__teamsPauseHeavyWatchers();
                        return;
                    }
                    if (mode === 'cold_unloaded') {
                        window.__teamsPauseHeavyWatchers();
                    }
                };
            })();

            // ========== 3. 图片交互（复制经 Python 剪贴板，避免 QtWebEngine clipboard 失败） ==========
            const enableImageInteractions = () => {
                const showToastMsg = (message, isError = false) => {
                    let el = document.getElementById('teams-x-toast');
                    if (!el && document.body) {
                        el = document.createElement('div');
                        el.id = 'teams-x-toast';
                        el.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);'
                            + 'z-index:100000;pointer-events:none;color:#fff;padding:8px 16px;border-radius:8px;';
                        document.body.appendChild(el);
                    }
                    if (!el) return;
                    el.textContent = message;
                    el.style.background = isError ? 'rgba(220,53,69,.9)' : 'rgba(0,0,0,.8)';
                    el.style.display = 'block';
                    clearTimeout(window.__teams_toast_hide_timer);
                    window.__teams_toast_hide_timer = setTimeout(() => {
                        el.style.display = 'none';
                    }, 2000);
                };
                const stabilizeImageAfterCopy = (img) => {
                    if (!img || !img.isConnected) return;
                    const scrollEl = img.closest('[role="log"], [data-tid*="message"], [class*="message"]');
                    const scrollTop = scrollEl ? scrollEl.scrollTop : null;
                    const scrollLeft = scrollEl ? scrollEl.scrollLeft : null;
                    const reset = () => {
                        try { img.blur(); } catch (e) {}
                        img.style.removeProperty('transform');
                        img.style.removeProperty('margin');
                        img.style.removeProperty('top');
                        img.style.removeProperty('left');
                        if (scrollEl != null && scrollTop != null) {
                            scrollEl.scrollTop = scrollTop;
                            scrollEl.scrollLeft = scrollLeft;
                        }
                        void img.offsetHeight;
                    };
                    requestAnimationFrame(() => requestAnimationFrame(reset));
                };
                document.addEventListener('contextmenu', (e) => {
                    const t = e.target;
                    if (t && t.tagName === 'IMG' && t.hasAttribute('data-teams-enhanced')) {
                        e.preventDefault();
                        e.stopImmediatePropagation();
                    }
                }, true);
                const MAX_CLIP_EDGE = 2048;
                const waitForClipboardBridge = (fn, maxMs) => {
                    const deadline = Date.now() + (maxMs || 8000);
                    const tick = () => {
                        if (window.__teamsCopyImageToClipboard) { fn(); return; }
                        if (typeof window.connectTeamsBridge === 'function') {
                            try { window.connectTeamsBridge(); } catch (e) {}
                        }
                        if (Date.now() > deadline) {
                            showToastMsg('✗ 复制失败，请切换账号后重试', true);
                            return;
                        }
                        setTimeout(tick, 80);
                    };
                    tick();
                };
                const imageToDataUrl = (img) => {
                    let w = img.naturalWidth || img.width || 0;
                    let h = img.naturalHeight || img.height || 0;
                    if (!w || !h) return '';
                    const scale = Math.min(1, MAX_CLIP_EDGE / Math.max(w, h));
                    w = Math.max(1, Math.floor(w * scale));
                    h = Math.max(1, Math.floor(h * scale));
                    const c = document.createElement('canvas');
                    c.width = w; c.height = h;
                    c.getContext('2d').drawImage(img, 0, 0, w, h);
                    return c.toDataURL('image/png', 0.92);
                };
                const copyDataUrlViaPython = (dataUrl, imgEl) => {
                    waitForClipboardBridge(() => {
                        try {
                            window.__teamsCopyImageToClipboard(dataUrl);
                            showToastMsg('已复制');
                            stabilizeImageAfterCopy(imgEl);
                        } catch (err) {
                            showToastMsg('复制失败', true);
                        }
                    });
                };
                const copyImageViaCanvas = (imageUrl, srcImgEl) => {
                    const img = new Image();
                    img.crossOrigin = 'anonymous';
                    img.onload = () => {
                        try {
                            const dataUrl = imageToDataUrl(img);
                            if (dataUrl) copyDataUrlViaPython(dataUrl, srcImgEl);
                            else showToastMsg('复制失败', true);
                        } catch (e) {
                            showToastMsg('复制失败', true);
                        }
                    };
                    img.onerror = () => {
                        if (imageUrl && window.__teamsCopyImageUrl) {
                            window.__teamsCopyImageUrl(imageUrl);
                            showToastMsg('正在复制…');
                            stabilizeImageAfterCopy(srcImgEl);
                        } else {
                            showToastMsg('复制失败', true);
                        }
                    };
                    img.src = imageUrl;
                };
                const copyImageToClipboard = (imageUrl, imgEl) => {
                    if (!imageUrl && imgEl) imageUrl = imgEl.src;
                    if (!imageUrl) {
                        showToastMsg('✗ 无图片地址', true);
                        return false;
                    }
                    if (imageUrl.startsWith('data:')) {
                        copyDataUrlViaPython(imageUrl, imgEl);
                        return true;
                    }
                    try {
                        if (imgEl && imgEl.complete && (imgEl.naturalWidth || imgEl.width)) {
                            const dataUrl = imageToDataUrl(imgEl);
                            if (dataUrl) {
                                copyDataUrlViaPython(dataUrl, imgEl);
                                return true;
                            }
                        }
                    } catch (err) {
                        console.error('复制失败:', err);
                    }
                    copyImageViaCanvas(imageUrl, imgEl);
                    return true;
                };
                
                // 下载图片
                const downloadImage = (imageUrl, filename) => {
                    try {
                        const a = document.createElement('a');
                        a.href = imageUrl;
                        a.download = filename || imageUrl.split('/').pop() || 'teams_image.png';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        showToastMsg('✓ 图片下载中...');
                    } catch (err) {
                        showToastMsg('✗ 下载失败', true);
                    }
                };
                
                const resolveImageUrl = (imgOrUrl) => {
                    if (imgOrUrl && typeof imgOrUrl === 'object' && imgOrUrl.tagName === 'IMG') {
                        return imgOrUrl.currentSrc || imgOrUrl.src || '';
                    }
                    return String(imgOrUrl || '');
                };
                const fetchImageObjectUrl = (imageUrl) => fetch(imageUrl, { credentials: 'include', mode: 'cors' })
                    .then((r) => {
                        if (!r.ok) throw new Error('fetch failed');
                        return r.blob();
                    })
                    .then((blob) => URL.createObjectURL(blob));
                const loadViewerImage = (srcImg, displayImg, imageUrl, onReady, onFail) => {
                    const done = () => { if (onReady) onReady(); };
                    const fail = () => { if (onFail) onFail(); };
                    if (!imageUrl) { fail(); return; }
                    if (imageUrl.startsWith('data:')) {
                        displayImg.onload = done;
                        displayImg.onerror = fail;
                        displayImg.src = imageUrl;
                        return;
                    }
                    if (srcImg && srcImg.complete && (srcImg.naturalWidth || srcImg.width)) {
                        try {
                            const dataUrl = imageToDataUrl(srcImg);
                            if (dataUrl) {
                                displayImg.onload = done;
                                displayImg.onerror = () => {
                                    fetchImageObjectUrl(imageUrl)
                                        .then((objUrl) => {
                                            displayImg.onload = () => {
                                                URL.revokeObjectURL(objUrl);
                                                done();
                                            };
                                            displayImg.onerror = fail;
                                            displayImg.src = objUrl;
                                        })
                                        .catch(fail);
                                };
                                displayImg.src = dataUrl;
                                return;
                            }
                        } catch (e) {}
                    }
                    displayImg.referrerPolicy = 'no-referrer-when-downgrade';
                    displayImg.crossOrigin = 'anonymous';
                    displayImg.onload = done;
                    displayImg.onerror = () => {
                        fetchImageObjectUrl(imageUrl)
                            .then((objUrl) => {
                                displayImg.onload = () => {
                                    URL.revokeObjectURL(objUrl);
                                    done();
                                };
                                displayImg.onerror = fail;
                                displayImg.src = objUrl;
                            })
                            .catch(fail);
                    };
                    displayImg.src = imageUrl;
                };

                // 显示图片查看器
                const showImageViewer = (srcImgOrUrl) => {
                    const srcImg = (srcImgOrUrl && typeof srcImgOrUrl === 'object' && srcImgOrUrl.tagName === 'IMG')
                        ? srcImgOrUrl : null;
                    const imageUrl = resolveImageUrl(srcImgOrUrl);
                    const viewer = document.createElement('div');
                    viewer.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.95);
                        z-index: 100000;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        cursor: pointer;
                    `;

                    const statusEl = document.createElement('div');
                    statusEl.textContent = '加载中...';
                    statusEl.style.cssText = `
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        color: #fff;
                        font-size: 16px;
                        pointer-events: none;
                        z-index: 100001;
                    `;
                    
                    const img = document.createElement('img');
                    img.style.cssText = `
                        max-width: 90%;
                        max-height: 90%;
                        object-fit: contain;
                        border-radius: 8px;
                        cursor: default;
                        opacity: 0;
                        transition: opacity .2s ease;
                    `;
                    
                    const btnContainer = document.createElement('div');
                    btnContainer.style.cssText = `
                        position: absolute;
                        bottom: 20px;
                        right: 20px;
                        display: flex;
                        gap: 12px;
                        z-index: 100001;
                        cursor: default;
                    `;
                    
                    const downloadBtn = document.createElement('button');
                    downloadBtn.textContent = '⬇ 下载图片';
                    downloadBtn.style.cssText = `
                        background: #0078d4;
                        border: none;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: bold;
                    `;
                    downloadBtn.onclick = (e) => {
                        e.stopPropagation();
                        const filename = imageUrl.split('/').pop().split('?')[0] || 'teams_image.png';
                        downloadImage(imageUrl, filename);
                    };
                    
                    const copyBtn = document.createElement('button');
                    copyBtn.textContent = '📋 复制图片';
                    copyBtn.style.cssText = `
                        background: #28a745;
                        border: none;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: bold;
                    `;
                    copyBtn.onclick = (e) => {
                        e.stopPropagation();
                        if (img.complete && (img.naturalWidth || img.width)) {
                            copyImageToClipboard(imageUrl, img);
                        } else {
                            img.onload = () => copyImageToClipboard(imageUrl, img);
                        }
                    };
                    
                    const closeBtn = document.createElement('button');
                    closeBtn.textContent = '✕ 关闭';
                    closeBtn.style.cssText = `
                        background: #6c757d;
                        border: none;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: bold;
                    `;
                    closeBtn.onclick = (e) => {
                        e.stopPropagation();
                        viewer.remove();
                    };
                    
                    btnContainer.appendChild(copyBtn);
                    btnContainer.appendChild(downloadBtn);
                    btnContainer.appendChild(closeBtn);
                    
                    viewer.appendChild(statusEl);
                    viewer.appendChild(img);
                    viewer.appendChild(btnContainer);
                    viewer.onclick = (e) => {
                        if (e.target === viewer) viewer.remove();
                    };
                    
                    document.body.appendChild(viewer);
                    loadViewerImage(
                        srcImg,
                        img,
                        imageUrl,
                        () => {
                            statusEl.remove();
                            img.style.opacity = '1';
                        },
                        () => {
                            statusEl.textContent = '图片加载失败';
                            statusEl.style.color = '#ff6b6b';
                        }
                    );
                };
                
                // 仅聊天记录里“真实发送的图片/附件”才允许点开、复制；
                // Teams 界面内嵌插画、空状态图、图标一律跳过
                const isChatAttachmentImage = (img) => {
                    if (!img || img.tagName !== 'IMG') return false;

                    // 排除应用框架与空状态/插画容器
                    if (img.closest(
                        '[data-tid="app-bar"], [data-tid="teams-app-bar"], [data-tid="left-rail"], '
                        + 'header, nav, aside, footer, [role="banner"], [role="navigation"], '
                        + '[data-tid*="empty"], [data-tid*="zero"], [data-tid*="placeholder"], '
                        + '[data-tid*="welcome"], [data-tid*="hero"], [data-tid*="illustration"], '
                        + '[class*="empty"], [class*="placeholder"], [class*="illustration"], '
                        + '[class*="zeroState"], [class*="ZeroState"]'
                    )) {
                        return false;
                    }

                    // 按来源排除：静态资源 / 插画 / 图标 / 表情 / 头像
                    const src = img.currentSrc || img.src || '';
                    if (!src || src.startsWith('data:image/svg+xml')) return false;
                    const lower = src.toLowerCase();
                    if (lower.includes('evergreen-assets') || lower.includes('/illustrations/')
                        || lower.includes('/assets/') || lower.includes('statics.')
                        || lower.includes('cdn.office.net') || lower.includes('/fluent')
                        || lower.includes('emoji') || lower.includes('avatar')
                        || lower.includes('icon') || lower.includes('presence')
                        || lower.includes('reaction') || lower.endsWith('.svg')) {
                        return false;
                    }

                    // 必须位于真实消息正文 / 附件容器内（不再用宽松的 role="log"）
                    let host = img.closest(
                        '[data-tid="message-body"], [data-tid="messageBodyContent"], '
                        + '[data-tid*="attachment"]'
                    );
                    if (!host) {
                        // 备用：消息流里被链接包裹的图片（真实图片附件常包一层 <a>）
                        const inLog = img.closest('div[role="log"], [data-tid="chat-pane-list"]');
                        const linked = img.closest('a[href]');
                        if (!(inLog && linked)) return false;
                    }

                    const alt = (img.getAttribute('alt') || '').trim();
                    if (alt.length === 1) return false; // 单字符多为表情
                    const width = img.naturalWidth || img.width || 0;
                    const height = img.naturalHeight || img.height || 0;
                    if (width < 64 && height < 64) return false;
                    return true;
                };

                // 增强单个图片
                const enhanceImage = (img) => {
                    if (img.hasAttribute('data-teams-enhanced')) return;
                    if (!isChatAttachmentImage(img)) return;
                    
                    img.setAttribute('data-teams-enhanced', 'true');
                    img.style.cursor = 'pointer';
                    
                    img.addEventListener('click', (e) => {
                        e.stopPropagation();
                        showImageViewer(img);
                    });
                    
                    img.addEventListener('contextmenu', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        if (typeof window.connectTeamsBridge === 'function') {
                            try { window.connectTeamsBridge(); } catch (err) {}
                        }
                        copyImageToClipboard(img.currentSrc || img.src, img);
                        return false;
                    }, true);
                };
                
                // 监控新图片
                if (window.__teams_image_observer) {
                    window.__teams_image_observer.disconnect();
                }
                window.__teams_image_observer = new MutationObserver(() => {
                    document.querySelectorAll('img:not([data-teams-enhanced])').forEach(enhanceImage);
                });
                window.__teams_image_observer.observe(document.body, { childList: true, subtree: true });
                
                // 处理现有图片
                document.querySelectorAll('img').forEach(enhanceImage);
            };
            setTimeout(enableImageInteractions, 2000);

            // ========== 3.5 标题未读数快速同步（降低徽标延迟） ==========
            (function enableFastTitleBadgeSync() {
                if (window.__teams_title_badge_sync) return;
                window.__teams_title_badge_sync = true;
                let lastCount = -1;
                let lastPostAt = 0;
                window.__teamsSyncBadgeFromTitle = () => {
                    const count = window.__teamsReadUnreadCount ? window.__teamsReadUnreadCount() : 0;
                    if (count === lastCount) return;
                    lastCount = count;
                    const now = Date.now();
                    if (now - lastPostAt < __NOTIFY_TITLE_SYNC_MIN_MS__) return;
                    lastPostAt = now;
                    if (window.__externalNotificationCallback) {
                        window.__externalNotificationCallback('unread', '', '', count);
                    }
                };
                window.__teams_title_poll_1 = setInterval(window.__teamsSyncBadgeFromTitle, __TITLE_BADGE_POLL_MS__);
                try {
                    const titleEl = document.querySelector('title');
                    if (titleEl) {
                        window.__teams_title_observer = new MutationObserver(window.__teamsSyncBadgeFromTitle);
                        window.__teams_title_observer.observe(titleEl, {
                            childList: true, characterData: true, subtree: true
                        });
                    }
                } catch (e) {}
            })();

            // ========== 4. 实时消息通知检测（MutationObserver 实时监控） ==========
            const enableRealTimeNotificationDetection = () => {
                if (window.__teams_realtime_notification_enabled) return;
                window.__teams_realtime_notification_enabled = true;
                
                let processedMessages = new Set();
                const MAX_CACHE = 200;
                
                const getMessageType = (element) => {
                    const text = (element.innerText || element.textContent || '').toLowerCase();
                    const html = (element.innerHTML || '').toLowerCase();

                    // 图片/表情：优先识别 img
                    const imgs = element.querySelectorAll('img');
                    if (imgs && imgs.length) {
                        let isEmoji = false;
                        imgs.forEach(img => {
                            const src = (img.getAttribute('src') || '').toLowerCase();
                            const alt = (img.getAttribute('alt') || '').trim();
                            if (src.includes('emoji') || src.includes('emoticon') || alt.length === 1) {
                                isEmoji = true;
                            }
                        });
                        // 同一条消息可能既有 emoji 又有图片，优先图片
                        if (!isEmoji) return 'image';
                        return 'emoji';
                    }

                    // 文件：附件/文件卡片
                    if (element.querySelector('[data-tid*="attachment"]') ||
                        element.querySelector('[aria-label*="attachment"]') ||
                        html.includes('attachment') || text.includes('文件') || text.includes('附件')) {
                        return 'file';
                    }

                    if (element.querySelector('[aria-label*="voice"]') ||
                        element.querySelector('[aria-label*="audio"]') ||
                        html.includes('voice-message') || html.includes('audio-message') ||
                        text.includes('语音') || text.includes('录音')) return 'voice';

                    if (element.querySelector('[aria-label*="like"]') ||
                        element.querySelector('[data-tid="message-reaction"]') ||
                        html.includes('liked') || text.includes('点赞') || text.includes('👍')) return 'like';

                    return 'reply';
                };

                const getSenderName = (element) => {
                    const nameSelectors = [
                        '[data-tid="message-sender-name"]',
                        '[data-tid="author"]',
                        '[data-tid*="sender"]',
                        '[class*="display-name"]',
                        '[class*="sender"]',
                        '[aria-label*="said"]'
                    ];
                    for (let sel of nameSelectors) {
                        const nameEl = element.querySelector(sel);
                        if (nameEl && nameEl.innerText.trim()) {
                            return nameEl.innerText.trim();
                        }
                    }
                    try {
                        const labelled = element.getAttribute('aria-label') || '';
                        const m = labelled.match(/^(.+?)\s+(said|说|发送)/i);
                        if (m && m[1]) return m[1].trim();
                    } catch (e) {}
                    return '某人';
                };

                const getMessageContent = (element) => {
                    const contentSelectors = [
                        '[data-tid="message-body"]',
                        '[class*="message-content"]',
                        '[class*="message-text"]'
                    ];
                    for (let sel of contentSelectors) {
                        const contentEl = element.querySelector(sel);
                        if (contentEl) {
                            let text = contentEl.innerText.trim();
                            return text.length > 50 ? text.substring(0, 50) + '...' : text;
                        }
                    }
                    return '';
                };
                
                const quickHash = (s) => {
                    // 简单 hash：避免重复通知误杀
                    let h = 2166136261;
                    for (let i = 0; i < s.length; i++) {
                        h ^= s.charCodeAt(i);
                        h = Math.imul(h, 16777619);
                    }
                    return (h >>> 0).toString(16);
                };

                const getMessageDomId = (element) => {
                    if (!element) return '';
                    const attrs = ['data-mid', 'data-itemid', 'data-message-id', 'id'];
                    for (const a of attrs) {
                        try {
                            const v = element.getAttribute(a);
                            if (v && String(v).length < 120) return `${a}:${v}`;
                        } catch (e) {}
                    }
                    try {
                        const tid = element.getAttribute('data-tid');
                        const ts = element.querySelector('time[datetime]');
                        const dt = ts && ts.getAttribute('datetime');
                        if (tid && dt) return `${tid}:${dt}`;
                    } catch (e) {}
                    return '';
                };

                const sendNotification = (type, sender, content, element) => {
                    // DOM 扫描仅标记已处理，不触发提示音（响铃只走 Teams Notification API）
                    if (window.__TEAMS_NOTIFICATIONS_OFF) return;
                    const raw = (element && element.outerHTML) ? element.outerHTML : `${type}|${sender}|${content}|${Date.now()}`;
                    const domId = getMessageDomId(element);
                    const msgId = domId || `${type}_${sender}_${quickHash(raw)}`;
                    if (processedMessages.has(msgId)) return;
                    if (processedMessages.size > MAX_CACHE) {
                        const items = Array.from(processedMessages);
                        items.slice(0, MAX_CACHE / 2).forEach(id => processedMessages.delete(id));
                    }
                    processedMessages.add(msgId);
                };
                
                const scanRealtimeMessages = () => {
                    if (window.__teamsxHeavyPaused) return;
                    const messageSelectors = [
                        '[data-tid="message"]',
                        '[data-tid="chat-message"]',
                        'div[role="log"] > div'
                    ];
                    for (const sel of messageSelectors) {
                        document.querySelectorAll(sel).forEach(messageEl => {
                            if (!messageEl || messageEl.hasAttribute('data-realtime-notified')) return;
                            const type = getMessageType(messageEl);
                            const sender = getSenderName(messageEl);
                            const content = getMessageContent(messageEl);
                            sendNotification(type, sender, content, messageEl);
                            messageEl.setAttribute('data-realtime-notified', 'true');
                        });
                    }
                };

                // 使用 MutationObserver 实时监听新消息
                const handleRealtimeMutations = (mutations) => {
                    for (const mutation of mutations) {
                        if (mutation.type === 'childList') {
                            mutation.addedNodes.forEach(node => {
                                if (node.nodeType === Node.ELEMENT_NODE) {
                                    // 检查是否是消息元素
                                    const messageSelectors = [
                                        '[data-tid="message"]',
                                        '[data-tid="chat-message"]',
                                        'div[role="log"] > div'
                                    ];
                                    for (const sel of messageSelectors) {
                                        const messageEl = node.matches && node.matches(sel) ? node : node.querySelector(sel);
                                        if (messageEl && !messageEl.hasAttribute('data-realtime-notified')) {
                                            const type = getMessageType(messageEl);
                                            const sender = getSenderName(messageEl);
                                            const content = getMessageContent(messageEl);
                                            sendNotification(type, sender, content, messageEl);
                                            messageEl.setAttribute('data-realtime-notified', 'true');
                                        }
                                    }
                                }
                            });
                        }
                    }
                };
                const messageObserver = new MutationObserver(
                    __teamsxThrottle(handleRealtimeMutations, 180)
                );
                
                // 观察聊天区与活动摘要（未打开具体会话时也能收到提醒）
                const startObserving = () => {
                    const targets = new Set();
                    const chatContainer = document.querySelector('div[role="log"]');
                    if (chatContainer) targets.add(chatContainer);
                    document.querySelectorAll(
                        '[data-tid="activity-feed"], [data-tid="chat-list"], main'
                    ).forEach(el => targets.add(el));
                    if (!targets.size && document.body) targets.add(document.body);
                    targets.forEach(el => {
                        try {
                            messageObserver.observe(el, { childList: true, subtree: true });
                        } catch (e) {}
                    });
                    if (!targets.size) setTimeout(startObserving, 500);
                };
                startObserving();
                window.__teams_realtime_scan = setInterval(scanRealtimeMessages, __REALTIME_SCAN_MS__);
                scanRealtimeMessages();
                window.__teams_realtime_observer = messageObserver;
            };
            window.__teamsEnableRealtimeNotifications = enableRealTimeNotificationDetection;
            setTimeout(enableRealTimeNotificationDetection, 400);

            // ========== 4.2 聊天列表变化检测（最可靠：每条新消息都触发，含同会话连发） ==========
            const enableChatListWatcher = () => {
                if (window.__teams_chatlist_watch_enabled) return;
                window.__teams_chatlist_watch_enabled = true;

                const sigMap = {};            // chatKey -> 最近一次消息签名
                let primed = false;           // 首轮仅建立基线，不响铃

                const hashStr = (s) => {
                    let h = 2166136261;
                    s = String(s || '');
                    for (let i = 0; i < s.length; i++) {
                        h ^= s.charCodeAt(i);
                        h = Math.imul(h, 16777619);
                    }
                    return (h >>> 0).toString(16);
                };

                const getItems = () => {
                    let items = document.querySelectorAll(
                        '[data-tid="chat-list-item"], [data-tid*="chat-list-item"]'
                    );
                    if (!items.length) {
                        items = document.querySelectorAll(
                            '[role="treeitem"], [data-tid="chat-list"] [role="listitem"], '
                            + '[data-tid="chat-list"] li, [role="listbox"] [role="option"]'
                        );
                    }
                    if (!items.length) {
                        items = document.querySelectorAll(
                            '[data-tid="chat-list"] > *, [role="list"] > [role="listitem"]'
                        );
                    }
                    return items;
                };

                const itemKey = (item) => {
                    let k = item.getAttribute('id')
                        || item.getAttribute('data-tid')
                        || item.getAttribute('data-itemid')
                        || '';
                    if (!k || k === 'chat-list-item') {
                        const nameEl = item.querySelector(
                            '[data-tid="title"], [class*="title"], [class*="displayName"], '
                            + '[class*="chatName"]'
                        );
                        const nm = nameEl && (nameEl.innerText || '').trim();
                        const aria = (item.getAttribute('aria-label') || '').slice(0, 60);
                        k = nm || aria || '';
                    }
                    return k;
                };

                const itemName = (item) => {
                    const nameEl = item.querySelector(
                        '[data-tid="title"], [class*="title"], [class*="displayName"], '
                        + '[class*="chatName"]'
                    );
                    let nm = nameEl && (nameEl.innerText || '').trim();
                    if (nm) return nm.split(/[\r\n]+/)[0].trim();
                    const aria = (item.getAttribute('aria-label') || '').trim();
                    if (aria) return aria.split(/[，,。.\r\n]/)[0].trim();
                    return '某人';
                };

                const itemSig = (item) => {
                    const full = (item.innerText || item.textContent || '')
                        .replace(/\s+/g, ' ').trim().slice(0, 400);
                    const aria = (item.getAttribute('aria-label') || '').trim().slice(0, 200);
                    return full || aria || '';
                };

                const isUnread = (item) => {
                    try {
                        if (item.querySelector(
                            '[class*="counterBadge"], [data-tid*="badge"], [class*="unread"], '
                            + '[data-tid="unread-indicator"]'
                        )) return true;
                        const aria = item.getAttribute('aria-label') || '';
                        if (/未读|unread/i.test(aria)) return true;
                    } catch (e) {}
                    return false;
                };

                const scan = () => {
                    if (window.__teamsxHeavyPaused) return;
                    if (window.__TEAMS_NOTIFICATIONS_OFF) { primed = true; return; }
                    let items = getItems();
                    if (!items.length) {
                        items = document.querySelectorAll(
                            '[data-tid="activity-feed"] > *, [data-tid*="activity-item"], '
                            + '[data-tid*="activityFeed"]'
                        );
                    }
                    if (!items.length) return;
                    const count = window.__teamsReadUnreadCount
                        ? window.__teamsReadUnreadCount() : 0;
                    items.forEach(item => {
                        const key = itemKey(item);
                        if (!key) return;
                        const info = itemSig(item);
                        const prev = sigMap[key];
                        sigMap[key] = info;
                        if (!primed || prev === undefined) return;   // 基线
                        if (prev === info) return;                   // 无变化
                        // 聊天列表变化只同步角标，不响铃（响铃由 Notification API 负责）
                        if (typeof window.__teamsSyncBadgeFromTitle === 'function') {
                            window.__teamsSyncBadgeFromTitle();
                        }
                    });
                    primed = true;
                };

                window.__teams_chatlist_scan = setInterval(scan, __CHATLIST_SCAN_MS__);
                scan();
                try {
                    const root = document.querySelector('[data-tid="chat-list"]')
                        || document.querySelector('main') || document.body;
                    if (root) {
                        const scanThrottled = __teamsxThrottle(scan, 220);
                        window.__teams_chatlist_observer = new MutationObserver(() => scanThrottled());
                        window.__teams_chatlist_observer.observe(root, {
                            childList: true, subtree: true, characterData: true
                        });
                    }
                } catch (e) {}
            };
            window.__teamsEnableChatListWatcher = enableChatListWatcher;
            setTimeout(enableChatListWatcher, 600);

            // ========== 4.3 Teams 网页通知条：已弃用（与 Notification API 重复，易误触） ==========
            const enableTeamsToastWatcher = () => {
                window.__teams_toast_watch_enabled = true;
            };
            window.__teamsEnableTeamsToastWatcher = enableTeamsToastWatcher;
            setTimeout(enableTeamsToastWatcher, 800);

            // ========== 4.5 语音/视频来电检测（来电 UI 不在聊天流里，需单独监听） ==========
            const enableIncomingCallDetection = () => {
                if (window.__teams_incoming_call_enabled) return;
                window.__teams_incoming_call_enabled = true;

                const CALL_SELECTORS = [
                    '[data-tid="calling-screen"]',
                    '[data-tid="incoming-call"]',
                    '[data-tid="toast-incoming-call"]',
                    '[data-tid="calling-notification"]',
                    '[data-tid="preCallUX"]',
                    '[data-tid*="incomingCall"]',
                    '[data-tid*="incoming-call"]',
                    '[data-tid*="IncomingCall"]',
                    '[data-tid*="ringing"]',
                    '[data-tid="callingScreenContainer"]',
                    '[data-tid="call-accept"]',
                    '[data-tid="call-decline"]',
                    '[id*="incoming-call"]',
                    '[class*="IncomingCall"]',
                    '[class*="incoming-call"]',
                    '[class*="CallingNotification"]'
                ];
                // 仅用通话专属的 data-tid 判定“接听/拒绝”，绝不使用泛化的
                // [aria-label*="接受/Accept"]：聊天气泡的无障碍标签会带上消息原文，
                // 含“接受”二字的普通文字消息会被误判成来电（一直响）。
                const ACCEPT_SELECTORS = [
                    '[data-tid="accept-call"]', '[data-tid="acceptButton"]',
                    '[data-tid*="accept-audio"]', '[data-tid*="accept-video"]',
                    '[data-tid="call-accept"]'
                ];
                const DECLINE_SELECTORS = [
                    '[data-tid="decline-call"]', '[data-tid="rejectButton"]',
                    '[data-tid="call-decline"]'
                ];

                // 元素是否真正可见（排除隐藏/预渲染/模板节点导致的误判）
                // 注意：后台账号的 WebView2 窗口未显示，页面几何尺寸为 0，
                // 这里的“几何可见性”只用于弱信号（aria/文本）兜底，避免聊天“接受”误判。
                const isVisible = (el) => {
                    if (!el || el.nodeType !== 1) return false;
                    try {
                        const r = el.getBoundingClientRect();
                        if (r.width < 4 || r.height < 4) return false;
                        if (r.bottom < 0 || r.right < 0) return false;
                        if (r.top > (window.innerHeight || 0) + 40) return false;
                        const st = window.getComputedStyle(el);
                        if (!st) return true;
                        if (st.display === 'none') return false;
                        if (st.visibility === 'hidden' || st.visibility === 'collapse') return false;
                        if (parseFloat(st.opacity || '1') < 0.05) return false;
                        if (el.offsetParent === null && st.position !== 'fixed') return false;
                    } catch (e) {}
                    return true;
                };
                // 元素是否“已挂载且未被显式隐藏”（不依赖几何尺寸）。
                // 用于强信号（通话专属 data-tid 接听/拒绝按钮）：这些 data-tid
                // 聊天消息绝不会有，因此即便后台窗口几何为 0 也可放心判定为来电，
                // 仅排除 display:none / visibility:hidden / opacity≈0 的预渲染模板。
                const isPresent = (el) => {
                    if (!el || el.nodeType !== 1) return false;
                    if (!el.isConnected) return false;
                    try {
                        const st = window.getComputedStyle(el);
                        if (!st) return true;
                        if (st.display === 'none') return false;
                        if (st.visibility === 'hidden' || st.visibility === 'collapse') return false;
                        if (parseFloat(st.opacity || '1') < 0.05) return false;
                    } catch (e) {}
                    return true;
                };
                const queryAnyVisible = (selList) => {
                    for (const sel of selList) {
                        let els;
                        try { els = document.querySelectorAll(sel); } catch (e) { continue; }
                        for (const el of els) {
                            if (isVisible(el)) return el;
                        }
                    }
                    return null;
                };
                const queryAnyPresent = (selList) => {
                    for (const sel of selList) {
                        let els;
                        try { els = document.querySelectorAll(sel); } catch (e) { continue; }
                        for (const el of els) {
                            if (isPresent(el)) return el;
                        }
                    }
                    return null;
                };
                // 容器内是否含“接听 / 拒绝”通话专属按钮（来电的决定性特征）。
                // 用 isPresent（不依赖几何尺寸），保证后台隐藏窗口也能命中。
                const hasCallActionInside = (root) => {
                    if (!root) return false;
                    try {
                        const a = root.querySelector(ACCEPT_SELECTORS.join(','));
                        if (a && isPresent(a)) return true;
                    } catch (e) {}
                    try {
                        const d = root.querySelector(DECLINE_SELECTORS.join(','));
                        if (d && isPresent(d)) return true;
                    } catch (e) {}
                    return false;
                };

                // 通话接听/拒绝按钮兜底：必须是真正且可见的按钮，且 aria-label 中
                // “接听/接受/answer/accept” 与 “来电/通话/呼叫/call” 相邻出现才算，
                // 单独的“接受”二字（聊天内容）不会命中。
                const findCallActionButton = () => {
                    let nodes;
                    try {
                        nodes = document.querySelectorAll(
                            'button[aria-label], [role="button"][aria-label]'
                        );
                    } catch (e) { return null; }
                    const re = new RegExp(
                        '(接听|接受|应答|answer|accept)[^]{0,10}(来电|通话|呼叫|call)'
                        + '|(来电|通话|呼叫|call)[^]{0,10}(接听|接受|应答|answer|accept)'
                        + '|(拒绝|谢绝|decline|reject)[^]{0,10}(来电|通话|呼叫|call)',
                        'i'
                    );
                    for (const el of nodes) {
                        const al = el.getAttribute('aria-label') || '';
                        if (re.test(al) && isVisible(el)) return el;
                    }
                    return null;
                };

                // 找到正在显示的来电 UI 根节点。
                // 关键：来电必有“可见的接听 + 可见的拒绝按钮”。仅靠 class/data-tid
                // 含 calling/incoming/ringing 的节点（可能隐藏/预渲染/为拨出或通话中）
                // 一律不算来电，彻底避免发图片/文字时误报。
                const findCallRoot = () => {
                    // 1) 最强信号：通话专属的接听 + 拒绝按钮同时挂载（不依赖几何尺寸，
                    //    后台隐藏窗口也能命中；这些 data-tid 聊天消息绝不会有）
                    const accept = queryAnyPresent(ACCEPT_SELECTORS);
                    const decline = queryAnyPresent(DECLINE_SELECTORS);
                    if (accept && decline) {
                        return accept.closest(
                            '[role="dialog"], [data-tid], section, article, div'
                        ) || accept;
                    }
                    // 2) 通话专属容器已挂载，且容器内确有接听/拒绝按钮
                    const direct = queryAnyPresent(CALL_SELECTORS);
                    if (direct && hasCallActionInside(direct)) return direct;
                    // 3) aria-label 组合按钮可见，且其所在容器内还有可见通话按钮
                    const callBtn = findCallActionButton();
                    if (callBtn) {
                        const cont = callBtn.closest(
                            '[role="dialog"], [data-tid], section, article, div'
                        );
                        if (cont && hasCallActionInside(cont)) return cont;
                    }
                    // 4) 文本兜底：可见弹层含来电字样，且层内确有可见通话操作按钮
                    let layers;
                    try {
                        layers = document.querySelectorAll(
                            '[role="dialog"], [data-tid*="toast"], [class*="calling"], [class*="incoming"]'
                        );
                    } catch (e) { layers = []; }
                    for (const layer of layers) {
                        if (!isVisible(layer)) continue;
                        const t = (layer.innerText || layer.textContent || '');
                        if (!/来电|正在呼叫|incoming call|is calling|ringing/i.test(t)) continue;
                        if (hasCallActionInside(layer)) return layer;
                    }
                    return null;
                };

                const isVideoCall = (root) => {
                    if (!root) return false;
                    try {
                        if (root.querySelector(
                            '[data-tid*="video"], [aria-label*="视频"], [aria-label*="Video" i], '
                            + '[data-tid="accept-video"]'
                        )) return true;
                    } catch (e) {}
                    const t = (root.innerText || root.textContent || '');
                    return /视频通话|视频来电|video call/i.test(t);
                };

                const parseCallerFromLabel = (label) => {
                    const s = String(label || '').trim();
                    if (!s) return '';
                    const patterns = [
                        /(?:来自|来自：)\s*([^，。,]+)/,
                        /接听\s*(.+?)\s*的(?:来电|通话|呼叫)/,
                        /(.+?)\s*的(?:视频|语音)?来电/,
                        /(?:Accept|Answer)\s+(?:video\s+)?call\s+from\s+(.+?)(?:'s)?$/i,
                        /(?:Accept|Answer)\s+(.+?)(?:'s)?\s+(?:video\s+)?call/i,
                        /(.+?)\s+is\s+calling/i,
                        /(.+?)\s+正在呼叫/i
                    ];
                    for (const re of patterns) {
                        const m = s.match(re);
                        if (m && m[1]) {
                            const name = m[1].trim();
                            if (name && !/^(来电|呼叫|通话|call|video|audio)$/i.test(name)) return name;
                        }
                    }
                    return '';
                };

                const extractCaller = (root) => {
                    const tryName = (v) => {
                        const n = String(v || '').trim();
                        if (!n || n.length > 40) return '';
                        if (/^(来电|正在呼叫|邀请你加入|语音通话|视频通话|某人)$/i.test(n)) return '';
                        return n;
                    };
                    const scopes = [];
                    if (root) scopes.push(root);
                    try {
                        document.querySelectorAll(
                            '[data-tid*="incoming"], [data-tid*="calling"], [class*="incoming"], [class*="Calling"]'
                        ).forEach(el => scopes.push(el));
                    } catch (e) {}
                    const sels = [
                        '[data-tid="calling-participant-name"]',
                        '[data-tid="participant-display-name"]',
                        '[data-tid*="caller"]',
                        '[data-tid*="participant-name"]',
                        '[data-tid="title"]',
                        '[class*="caller"]',
                        '[class*="display-name"]',
                        '[class*="participant"] [role="heading"]'
                    ];
                    for (const scope of scopes) {
                        for (const s of sels) {
                            try {
                                const el = scope.querySelector && scope.querySelector(s);
                                const v = tryName(el && (el.innerText || el.textContent || ''));
                                if (v) return v;
                            } catch (e) {}
                        }
                    }
                    try {
                        const btns = document.querySelectorAll(
                            ACCEPT_SELECTORS.concat(DECLINE_SELECTORS).join(',')
                        );
                        for (const btn of btns) {
                            const v = parseCallerFromLabel(btn.getAttribute('aria-label'));
                            if (v) return v;
                        }
                    } catch (e) {}
                    for (const scope of scopes) {
                        const t = (scope.innerText || scope.textContent || '').trim();
                        const lines = t.split(/[\r\n]+/).map(s => s.trim()).filter(Boolean);
                        for (const line of lines) {
                            const fromLabel = parseCallerFromLabel(line);
                            if (fromLabel) return fromLabel;
                            const cleaned = line
                                .replace(/(来电|正在呼叫|邀请你加入|视频通话|语音通话|incoming call|is calling|ringing)/ig, '')
                                .trim();
                            const v = tryName(cleaned);
                            if (v) return v;
                        }
                    }
                    // 全局 aria-label 扫描：弹层/按钮上常写“来自 X 的来电 / X is calling”
                    try {
                        const labelled = document.querySelectorAll('[aria-label]');
                        for (const el of labelled) {
                            const al = el.getAttribute('aria-label') || '';
                            if (!/来电|正在呼叫|呼叫|calling|incoming|call from/i.test(al)) continue;
                            const v = parseCallerFromLabel(al);
                            if (v) return v;
                        }
                    } catch (e) {}
                    // document.title 兜底：来电时常含呼叫者名字
                    try {
                        const tt = (document.title || '').trim();
                        const v = parseCallerFromLabel(tt);
                        if (v) return v;
                    } catch (e) {}
                    return '某人';
                };

                const scheduleCallEnd = () => {
                    if (window.__teams_call_end_timer) return;
                    window.__teams_call_end_timer = setTimeout(() => {
                        window.__teams_call_end_timer = null;
                        if (findCallRoot()) return;
                        if (!window.__teams_call_ui_active) return;
                        window.__teams_call_ui_active = false;
                        window.__teams_call_last_notify = 0;
                        window.__teams_call_notified_once = false;
                        window.__teams_call_caller_name = '';
                        const count = window.__teamsReadUnreadCount
                            ? window.__teamsReadUnreadCount() : 0;
                        if (window.__externalNotificationCallback) {
                            window.__externalNotificationCallback(
                                'call_end', '', '', count
                            );
                        }
                    }, __CALL_END_DEBOUNCE_MS__);
                };
                const cancelCallEnd = () => {
                    if (window.__teams_call_end_timer) {
                        clearTimeout(window.__teams_call_end_timer);
                        window.__teams_call_end_timer = null;
                    }
                };

                const tick = () => {
                    const root = findCallRoot();
                    if (!root) {
                        if (window.__teams_call_ui_active) {
                            scheduleCallEnd();
                        }
                        return;
                    }
                    cancelCallEnd();
                    if (window.__TEAMS_NOTIFICATIONS_OFF) {
                        return;
                    }
                    window.__teams_call_ui_active = true;
                    const now = Date.now();
                    const first = !window.__teams_call_notified_once;
                    const gapMs = first ? 0 : 4000;
                    if (
                        !first
                        && window.__teams_call_last_notify
                        && now - window.__teams_call_last_notify < gapMs
                    ) {
                        return;
                    }
                    window.__teams_call_last_notify = now;
                    window.__teams_call_notified_once = true;
                    const video = isVideoCall(root);
                    let caller = extractCaller(root);
                    if (caller && caller !== '某人') {
                        window.__teams_call_caller_name = caller;
                    } else if (window.__teams_call_caller_name) {
                        caller = window.__teams_call_caller_name;
                    }
                    const type = video ? 'incoming_video' : 'incoming_call';
                    const message = video ? '邀请你视频通话' : '邀请你语音通话';
                    const count = window.__teamsReadUnreadCount ? window.__teamsReadUnreadCount() : 0;
                    if (window.__externalNotificationCallback) {
                        window.__externalNotificationCallback(type, caller, message, count);
                    }
                };

                window.__teams_call_last_notify = 0;
                window.__teams_call_ui_active = false;
                window.__teams_call_notified_once = false;
                window.__teams_call_end_timer = null;
                const __callPollMs = (window.__teamsxRuntimeMode === 'warm_notify')
                    ? __WARM_CALL_DETECT_POLL_MS__ : __CALL_DETECT_POLL_MS__;
                // 轮询 + 观察双保险：来电 UI 一出现尽快触发
                window.__teams_call_poll = setInterval(tick, __callPollMs);
                try {
                    const obs = new MutationObserver(__teamsxThrottle(tick, 150));
                    obs.observe(document.body, { childList: true, subtree: true });
                    window.__teams_call_observer = obs;
                } catch (e) {}
                setTimeout(tick, 300);
            };
            window.__teamsEnableIncomingCallDetection = enableIncomingCallDetection;
            setTimeout(enableIncomingCallDetection, 200);
        })();
        """
        js_code = js_code.replace(
            "__CALL_DETECT_POLL_MS__", str(int(CALL_DETECT_POLL_MS))
        )
        js_code = js_code.replace(
            "__CALL_END_DEBOUNCE_MS__", str(int(CALL_END_DEBOUNCE_MS))
        )
        js_code = js_code.replace(
            "__NOTIFY_TITLE_SYNC_MIN_MS__", str(int(NOTIFY_TITLE_SYNC_MIN_MS))
        )
        js_code = js_code.replace(
            "__TITLE_BADGE_POLL_MS__", str(int(TITLE_BADGE_POLL_MS))
        )
        js_code = js_code.replace(
            "__REALTIME_SCAN_MS__", str(int(REALTIME_SCAN_MS))
        )
        js_code = js_code.replace(
            "__CHATLIST_SCAN_MS__", str(int(CHATLIST_SCAN_MS))
        )
        js_code = js_code.replace(
            "__TOAST_SCAN_MS__", str(int(TOAST_SCAN_MS))
        )
        js_code = js_code.replace(
            "__MUTE_ALL_POLL_MS__", str(int(MUTE_ALL_POLL_MS))
        )
        js_code = js_code.replace(
            "__WARM_TITLE_POLL_MS__", str(int(WARM_TITLE_POLL_MS))
        )
        js_code = js_code.replace(
            "__WARM_CALL_DETECT_POLL_MS__", str(int(WARM_CALL_DETECT_POLL_MS))
        )
        self._wv2_doc_scripts.append(js_code)
        return

# ==================== AI 聊天（独立模块，与 Teams/账号无关） ====================

AI_CONFIG_FILENAME = "ai_deepseek.json"
AI_CONTEXT_TURNS = 2
AI_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
AI_DEEPSEEK_MODEL = "deepseek-chat"
AI_MAX_OUTPUT_TOKENS = 8192
AI_SYSTEM_PROMPT = (
    "你是 TeamsXAi，由 TeamsX 公司开发。用自然、有温度的口吻交流，像靠谱的朋友聊天："
    "适当共情，语气真诚。不要使用 emoji、表情符号或特殊装饰字符；"
    "仅使用中文、英文、数字和常见标点，避免出现无法显示的乱码符号。"
    "回答清晰有用，避免生硬套话和机械堆砌。不要主动介绍身份或开发商。"
    "仅当用户明确问「你是什么 AI」「你是谁」等身份问题时，"
    "才说明你是 TeamsX、由 TeamsX 公司开发；不要自称其它模型名称。"
)
AI_IDENTITY_REPLY = "我是 TeamsXAi，由 TeamsX 公司开发～有什么想聊的，随时跟我说。"
AI_IDENTITY_PATTERNS = (
    r"你是什么\s*ai|你是什么\s*人工智能|你是什么\s*模型|你是哪个\s*ai|你是啥\s*ai|"
    r"你是谁|你叫什么|你的名字|"
    r"what\s+ai\s+are\s+you|which\s+ai\s+are\s+you|what\s+are\s+you|who\s+are\s+you|"
    r"what\s+model\s+are\s+you|which\s+model\s+are\s+you|your\s+name|"
    r"qu[eé]\s+ia\s+eres|qu[eé]\s+eres|qui\s+es-tu|c'est\s+quoi\s+ton\s+ia|"
    r"was\s+bist\s+du|welche\s+ki\s+bist\s+du"
)
# Windows 自带字体（无需下载）：界面 Segoe UI / 微软雅黑，代码 Consolas
AI_UI_FONT_FAMILY = (
    '"Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif'
)
AI_CODE_FONT_FAMILY = 'Consolas, "Courier New", monospace'
AI_CHAT_FONT_PX = "14px"
AI_CODE_FONT_PX = "11px"
AI_CODE_BLOCK_FONT_PX = "13px"
AI_CODE_INLINE_FONT_PX = "12px"
AI_CODE_FENCE_RE = re.compile(r"```(\w*)[^\S\r\n]*\r?\n(.*?)```", re.DOTALL)
AI_CODE_FENCE_RE_FALLBACK = re.compile(r"```(\w*)[^\S\r\n]*(.*?)```", re.DOTALL)
AI_CODE_KW = (
    "def", "class", "import", "from", "return", "if", "elif", "else",
    "for", "while", "try", "except", "finally", "with", "as", "pass",
    "break", "continue", "raise", "yield", "lambda", "global", "nonlocal",
    "True", "False", "None", "and", "or", "not", "in", "is", "async", "await",
    "function", "const", "let", "var", "new", "typeof", "void", "null",
    "undefined", "export", "default", "interface", "struct", "enum", "public",
    "private", "static", "void", "int", "float", "double", "bool", "string",
)
AI_CODE_KW_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in AI_CODE_KW) + r")\b"
)
AI_CODE_STR_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
AI_CODE_COMMENT_RE = re.compile(r"(//.*?$|#.*?$)")
AI_CODE_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
AI_STREAM_FULL_WIDTH_CHARS = 80
AI_CODE_INLINE_RE = re.compile(r"`([^`\n]+)`")
AI_INPUT_MIN_H = 50
AI_INPUT_MAX_H = 176
AI_STREAM_TICK_MS = 58
AI_STREAM_TICK_MS_FAST = 36
AI_STREAM_CHARS_SLOW = 2
AI_STREAM_CHARS_FAST = 5
AI_STREAM_RAMP_MID = 0.35
AI_STREAM_RAMP_FAST = 0.55
AI_STREAM_SCROLL_MIN_MS = 180
AI_STREAM_PAINT_MS = 66
AI_STREAM_HEIGHT_STEP = 20
AI_STREAM_REFLOW_MS = 100
AI_STREAM_RESIZE_DEBOUNCE_MS = 150
AI_THINKING_DEFER_MS = 40
AI_STREAM_SCROLL_HEIGHT_DELTA = 24
AI_STREAM_LONG_TEXT_CHARS = 360
AI_CHAT_BOTTOM_PAD_MIN = 32
AI_STREAM_LOCK_MIN_CHARS = 1
AI_THINKING_ROW_H = 28
AI_MSG_MAX_WIDTH = "82%"
AI_USER_BUBBLE_MAX_PX = 500
AI_USER_BUBBLE_MIN_PX = 200
AI_MSG_WRAP_MAX_PX = 1000
AI_MSG_WRAP_MIN_PX = 300
AI_MSG_CONTENT_PAD = 8
AI_USER_BUBBLE_CONTENT_PAD = 12
AI_BUBBLE_CROSS_INSET_CHARS = 2
AI_AI_CONTENT_MAX_PX = 500
AI_AI_CONTENT_MIN_PX = 200
AI_AI_BUBBLE_CONTENT_PAD = 6
AI_AI_CARD_PAD = 14
AI_AI_CARD_RADIUS = 14
AI_CHAT_PAD_LEFT = 32
AI_CHAT_PAD_RIGHT = 32
AI_REPLY_SHIFT_LEFT = 66
AI_MSG_FONT_PT = 11
AI_MSG_LINE_HEIGHT_RATIO = 1.8
AI_MSG_PARA_BOTTOM_MARGIN = 16
# QTextBlockFormat::LineHeightTypes::FixedHeight（勿用 PyQt 枚举，部分版本 int() 会失败）
AI_QTEXT_BLOCK_LH_FIXED = 2
AI_ROW_V_MARGIN = 6
AI_MSG_GAP_SAME = 10
AI_MSG_GAP_ROLE_SWITCH = 22
AI_BUBBLE_RADIUS = 22
AI_BUBBLE_TAIL_RADIUS = 8
AI_USER_CAPSULE_RADIUS = 18
AI_BUBBLE_MIN_W = 64
AI_AVATAR_SIZE = 0
AI_AI_FRAME_MARGIN = 8
AI_AI_FRAME_H_PAD = AI_AI_FRAME_MARGIN * 2
AI_USER_BG_LIGHT = "#e6e6ea"
AI_USER_BG_DARK = "#3c3c42"
AI_USER_FG_LIGHT = "#1a1a1a"
AI_USER_FG_DARK = "#ececec"
AI_AI_BG_DARK = "#2d2d2d"
AI_AI_BG_LIGHT = "#f0f0f0"
AI_AI_FG_DARK = "#e8e8e8"
AI_AI_FG_LIGHT = "#1a1a1a"
AI_CURSOR_BLINK_MS = 600
AI_THINKING_TICK_MS = 380
AI_COMPOSER_MAX_W = 580
AI_COMPOSER_MIN_W = 280
AI_COMPOSER_SIDE_MARGIN = 40
AI_SCROLL_PIN_THRESHOLD = 48


def sanitize_ai_display_text(text: str) -> str:
    """去掉无法显示的替换符、控制字符与孤立代理项。"""
    if not text:
        return ""
    out: List[str] = []
    for ch in text:
        o = ord(ch)
        if ch == "\ufffd":
            continue
        if o < 0x20 and ch not in "\n\r\t":
            continue
        if 0xD800 <= o <= 0xDFFF:
            continue
        out.append(ch)
    return "".join(out)


AI_MD_CODE_LINE_RE = re.compile(
    r"^\s*("
    r"#.*|import\s|from\s|def\s|class\s|async\s|await\s|return\s|"
    r"if\s|elif\s|else\s*:|while\s|for\s|with\s|try\s*:|except\s|"
    r"raise\s|pass\s*|@|\w+\s*=[^=]|print\s*\("
    r")",
    re.MULTILINE,
)


def _close_open_markdown_fences(text: str) -> str:
    if text.count("```") % 2:
        return text.rstrip() + "\n```\n"
    return text


def _looks_like_code_block(paragraph: str) -> bool:
    """识别未加 ``` 围栏的代码段（模型常直接输出 import/def 等行）。"""
    if "```" in paragraph:
        return False
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    if not lines:
        return False
    hits = 0
    for ln in lines:
        s = ln.strip()
        if AI_MD_CODE_LINE_RE.match(ln):
            hits += 1
        elif s.endswith(":") and re.match(r"^[\w.\s\[\]()]+:\s*$", s):
            hits += 1
        elif re.match(r"^[\w.]+\([^)]*\)\s*$", s):
            hits += 1
    if len(lines) == 1:
        return hits >= 1
    return hits >= max(2, int(len(lines) * 0.35))


def _normalize_markdown_before_parse(
    text: str, *, close_open_fences: bool = False
) -> str:
    """流式/完结前：补全围栏、裸代码加 python 围栏、列表项前强制换段。"""
    if not text:
        return text
    if close_open_fences:
        text = _close_open_markdown_fences(text)
    text = re.sub(r"([^\n])\n(-\s+)", r"\1\n\n\2", text)
    parts = re.split(r"\n\n+", text)
    out: List[str] = []
    for part in parts:
        part = part.strip("\n")
        if not part:
            continue
        if "```" in part or not _looks_like_code_block(part):
            out.append(part)
        else:
            out.append(f"```python\n{part}\n```")
    return "\n\n".join(out)


def _strip_pygments_background_css(css: str) -> str:
    """保留 Pygments 文字颜色，移除代码块/每个 token 的背景色。"""
    if not css:
        return css
    css = re.sub(
        r"background(-color)?\s*:\s*[^;]+;",
        "",
        css,
        flags=re.IGNORECASE,
    )
    return css


def _strip_html_background_styles(html: str) -> str:
    """清理 Pygments/markdown 输出里 span 等元素的内联 background（勿用于含 <style> 的整段 HTML）。"""
    if not html:
        return html

    def _clean_style_attr(match: re.Match) -> str:
        style = match.group(1)
        style = re.sub(
            r"background(-color)?\s*:\s*[^;]+;?",
            "",
            style,
            flags=re.IGNORECASE,
        )
        style = re.sub(r"\s+", " ", style).strip().strip(";")
        if not style:
            return ""
        return f'style="{style}"'

    html = re.sub(r'style="([^"]*)"', _clean_style_attr, html, flags=re.IGNORECASE)
    html = re.sub(r"\s*style=\"\"\s*", " ", html)
    html = re.sub(r"<span\s+style=\"\s*\"\s*>", "<span>", html, flags=re.IGNORECASE)
    html = re.sub(
        r"background(-color)?\s*:\s*[^;\"']+;?",
        "",
        html,
        flags=re.IGNORECASE,
    )
    return html


def _pygments_pre_inner_html(highlighted: str) -> str:
    """去掉 Pygments 外层 div/pre，仅保留 token span 供 mistune 包裹。"""
    if not highlighted:
        return highlighted
    s = highlighted.strip()
    m = re.search(
        r"<pre[^>]*>(.*)</pre>\s*</div>\s*$",
        s,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"<pre[^>]*>(.*)</pre>", s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _highlight_code_html(code: str, lexer, formatter) -> str:
    """Pygments 高亮并返回可嵌入 <pre><code> 的内部 HTML。"""
    if highlight is None or formatter is None:
        return ""
    return _strip_html_background_styles(
        _pygments_pre_inner_html(highlight(code, lexer, formatter))
    )


def _make_pygments_formatter(pygments_style: str):
    """class + nobackground：由 QTextDocument 默认样式表着色，无 token/块背景。"""
    formatter_cls = PygmentsHtmlFormatter or HtmlFormatter
    if formatter_cls is None:
        return None
    opts = {
        "style": pygments_style,
        "nobackground": True,
        "noclasses": False,
        "cssclass": "codehilite",
        "nowrap": False,
    }
    try:
        return formatter_cls(**opts)
    except TypeError:
        try:
            return formatter_cls(
                style=pygments_style,
                nobackground=True,
                noclasses=False,
                cssclass="codehilite",
            )
        except TypeError:
            try:
                return formatter_cls(style=pygments_style, nobackground=True)
            except TypeError:
                return formatter_cls(style=pygments_style)


def _pygments_highlight_css(
    pygments_style: str, selector: str = ".codehilite"
) -> str:
    """生成 Pygments token 颜色 CSS（仅剥离 background，color 加 !important 防被父级盖掉）。"""
    formatter = _make_pygments_formatter(pygments_style)
    if formatter is None:
        return ""
    try:
        css = formatter.get_style_defs(selector)
    except Exception:
        css = ""
    css = _strip_pygments_background_css(css)
    if not css:
        return css
    return re.sub(
        r"(?<![!])(color\s*:\s*[^;{}]+)",
        r"\1 !important",
        css,
        flags=re.IGNORECASE,
    )


if HAS_MISTUNE and mistune is not None:

    class _MistuneHighlightRenderer(mistune.HTMLRenderer):
        """Mistune HTML 输出 + Pygments 代码高亮。"""

        def __init__(self, pygments_style: str = "monokai"):
            super().__init__()
            self._pygments_style = pygments_style

        def block_code(self, code, info=None):
            if not code:
                return ""
            lang = (info or "").strip()
            formatter = _make_pygments_formatter(self._pygments_style)
            if formatter is not None and highlight is not None:
                try:
                    if lang:
                        lexer = get_lexer_by_name(lang, stripall=True)
                    else:
                        try:
                            lexer = guess_lexer(code)
                        except ClassNotFound:
                            lexer = get_lexer_by_name("text", stripall=True)
                except ClassNotFound:
                    lexer = get_lexer_by_name("text", stripall=True)
                inner = _highlight_code_html(code, lexer, formatter)
                return f'<pre class="codehilite"><code>{inner}</code></pre>'
            escaped = mistune.escape(code.rstrip("\n"))
            return f'<pre class="codehilite"><code>{escaped}</code></pre>'


class AiMarkdownEngine:
    """
    AI 消息 Markdown 渲染：始终对当前全文解析（流式/换主题同一路径），
    代码高亮与排版颜色由 QTextDocument.defaultStyleSheet 提供，HTML 无背景色。
    """

    @staticmethod
    def pygments_style(theme_light: bool) -> str:
        return "friendly" if theme_light else "monokai"

    @classmethod
    def render_wrapped_html(cls, text: str, theme_light: bool) -> str:
        body = cls.render_body_html(text, theme_light)
        if not body:
            return ""
        return f'<div class="teamsx-md">{body}</div>'

    @classmethod
    def render_body_html(cls, text: str, theme_light: bool) -> str:
        text = sanitize_ai_display_text(text)
        if not text.strip():
            return ""
        text = _normalize_markdown_before_parse(text, close_open_fences=True)
        if HAS_MISTUNE and mistune is not None:
            style = cls.pygments_style(theme_light)
            renderer = _MistuneHighlightRenderer(style)
            md = mistune.create_markdown(
                renderer=renderer,
                plugins=["table", "strikethrough"],
                hard_wrap=True,
            )
            try:
                return _strip_html_background_styles(md(text))
            except Exception:
                pass
        if HAS_MARKDOWN:
            return cls._render_markdown_lib(text)
        return ""

    @staticmethod
    def _render_markdown_lib(text: str) -> str:
        html = markdown.markdown(
            text,
            extensions=["extra", "codehilite", "nl2br", "sane_lists"],
            extension_configs={
                "codehilite": {
                    "css_class": "codehilite",
                    "linenums": False,
                    "pygments_options": {
                        "noclasses": False,
                        "nobackground": True,
                        "nowrap": False,
                    },
                }
            },
        )
        return _strip_html_background_styles(html)


class AiThinkingDotsWidget(QWidget):
    """AI 思考中：三个跳动圆点。"""

    def __init__(self, theme_light: bool, parent=None):
        super().__init__(parent)
        self._theme_light = theme_light
        self._phase = 0
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(0)
        self._dots_wrap = QWidget()
        self._dots_wrap.setStyleSheet(self._bubble_style())
        self._dots_wrap.setFixedHeight(AI_THINKING_ROW_H)
        dots_row = QHBoxLayout(self._dots_wrap)
        dots_row.setContentsMargins(0, 4, 0, 4)
        dots_row.setSpacing(6)
        self._dot_labels: List[QLabel] = []
        for _ in range(3):
            d = QLabel("●")
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dot_labels.append(d)
            dots_row.addWidget(d)
        row.addWidget(
            self._dots_wrap, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        row.addStretch(1)

    def set_content_width(self, width: int):
        """保留兼容；宽度由外层布局决定，此处仅启动动画。"""
        del width
        self.begin_animation()

    def begin_animation(self) -> None:
        if getattr(self, "_timer", None) is not None:
            return
        self._timer = QTimer(self)
        self._timer.setInterval(AI_THINKING_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def _bubble_style(self) -> str:
        fg = "#6a6a6a" if self._theme_light else "#9a9a9a"
        return (
            "background: transparent; border: none;"
            f" QLabel {{ color: {fg}; font-size: 11px; background: transparent; border: none; }}"
        )

    def set_theme_light(self, light: bool):
        self._theme_light = light
        self.setStyleSheet("background: transparent;")
        if getattr(self, "_dots_wrap", None) is not None:
            self._dots_wrap.setStyleSheet(self._bubble_style())
        self._tick()

    def _tick(self):
        self._phase = (self._phase + 1) % 3
        base = "#6a6a6a" if self._theme_light else "#8a8a8a"
        hi = "#1a1a1a" if self._theme_light else "#e8e8e8"
        for i, lbl in enumerate(self._dot_labels):
            c = hi if i == self._phase else base
            lbl.setStyleSheet(
                f"color: {c}; font-size: 12px; background: transparent; border: none;"
            )

    def stop(self):
        self._timer.stop()


class ChatBubbleTextEdit(QTextEdit):
    """只读聊天消息：无气泡，宽度随内容增长，达到 max_width 后才换行。"""

    def __init__(self, max_width: int, content_pad: int = 28, parent=None):
        super().__init__(parent)
        self._layout_max_width = max(120, max_width)
        self._content_pad = max(8, content_pad)
        self._width_locked = False
        self._html_stream_mode = False
        self._stream_layout_mode = False
        self._plain_stream = False
        self._stream_width_floor = 0
        self._stream_height_floor = 0
        self._last_stream_render = ""
        self._last_plain_render = ""
        self._last_plain_base = ""
        self._stream_measure_text = ""
        self._cursor_on = True
        self._plain_streaming = False
        self._rich_streaming = False
        self._had_cursor = False
        self._stream_floor_h = 24
        self._plain_fmt_done = False
        self._last_applied_height = 0
        self._rich_doc_css = ""
        self._suppress_reflow = False
        self._ai_full_width = False
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAcceptRichText(True)
        self.setReadOnly(True)
        self.setMinimumHeight(0)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        if hasattr(self, "setViewportUpdateMode"):
            self.setViewportUpdateMode(
                QAbstractScrollArea.ViewportUpdateMode.MinimalViewportUpdate
            )
        self.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        doc = self.document()
        doc.setDocumentMargin(6)
        doc.setDefaultStyleSheet(
            "body { line-height: 165%; margin: 0; padding: 0; text-align: left; } "
            "p { margin-top: 0; margin-bottom: 0; text-align: left; }"
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.setMaximumWidth(self._layout_max_width)
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(AI_STREAM_REFLOW_MS)
        self._reflow_timer.timeout.connect(self._reflow)
        doc.contentsChanged.connect(self._schedule_reflow)

    def set_rich_document_defaults(self, css: str, *, mark_dirty: bool = True):
        css = css or ""
        if css == (self._rich_doc_css or ""):
            return
        self._rich_doc_css = css
        doc = self.document()
        doc.setDefaultStyleSheet(self._rich_doc_css)
        if mark_dirty:
            n = max(0, doc.characterCount() - 1)
            if n > 0:
                doc.markContentsDirty(0, n)

    def _align_document_left(self):
        doc = self.document()
        block = doc.firstBlock()
        while block.isValid():
            bf = block.blockFormat()
            bf.setAlignment(Qt.AlignmentFlag.AlignLeft)
            cur = QTextCursor(block)
            cur.mergeBlockFormat(bf)
            block = block.next()

    @staticmethod
    def _line_height_px_for_font(font: QFont) -> int:
        pt = font.pointSizeF() or AI_MSG_FONT_PT
        return max(22, int(round(pt * AI_MSG_LINE_HEIGHT_RATIO)))

    def _apply_plain_block_spacing(self):
        """纯文本与 HTML 段落使用相同行高/段间距，避免流式时行距偏挤。"""
        doc = self.document()
        lh_px = self._line_height_px_for_font(self.font())
        block_fmt = QTextBlockFormat()
        block_fmt.setLineHeight(float(lh_px), AI_QTEXT_BLOCK_LH_FIXED)
        block_fmt.setBottomMargin(float(AI_MSG_PARA_BOTTOM_MARGIN))
        # 逐块合并格式，避免 select(Document) 在短文本时 setPosition 越界告警
        block = doc.firstBlock()
        while block.isValid():
            cur = QTextCursor(block)
            cur.mergeBlockFormat(block_fmt)
            block = block.next()

    @staticmethod
    def strip_stream_cursor_html(html: str) -> str:
        if not html:
            return html
        return re.sub(
            r'<span style="color:[^"]*; font-size:14px;">▍</span>\s*$',
            "",
            html,
        )

    def _schedule_reflow(self):
        if self._suppress_reflow:
            return
        if self._plain_streaming or self._rich_streaming:
            return
        if self._plain_stream or self._stream_layout_mode or self._width_locked:
            self._reflow()
            return
        self._reflow_timer.start(AI_STREAM_REFLOW_MS)

    def _sync_stream_height_throttled(self):
        doc = self.document()
        needed = max(self._stream_floor_h, int(doc.size().height()) + 10)
        cur = self.height()
        if needed <= cur:
            return
        if needed - cur < AI_STREAM_HEIGHT_STEP:
            return
        self._stream_floor_h = needed
        self._last_applied_height = needed
        self.setFixedHeight(needed)

    def begin_stream_layout(self):
        """流式排版：全宽换行、高度只增不减。"""
        self._stream_layout_mode = True
        self._html_stream_mode = True

    def end_stream_layout(self, reflow: bool = True):
        self._stream_layout_mode = False
        self._html_stream_mode = False
        self._plain_stream = False
        self._disconnect_plain_reflow_guard()
        if reflow:
            self._ai_full_width = False
            self._stream_width_floor = 0
            self._stream_height_floor = 0
            self._last_stream_render = ""
            self._last_plain_render = ""
            self._last_plain_base = ""
            self._stream_measure_text = ""
            self.lock_layout_width(False, reflow=True)
        else:
            self.apply_post_stream_layout()

    def apply_post_stream_layout(self):
        """流式结束：保持全宽，高度只扩不缩（避免长代码块中间被裁掉）。"""
        layout_max = self._layout_max_width
        margin = int(self.document().documentMargin()) * 2
        inner_w = max(48, layout_max - margin - self._content_pad)
        self._width_locked = False
        self._ai_full_width = True
        self.setFixedWidth(layout_max)
        self.setMaximumWidth(layout_max)
        self.document().setTextWidth(inner_w)
        QTimer.singleShot(0, self._finish_post_stream_layout)

    def _finish_post_stream_layout(self):
        """等 Qt 排完版后再定高，且不低于流式过程中已达到的高度。"""
        if not self.isVisible():
            return
        self._suppress_reflow = True
        try:
            doc_h = self._document_content_height() + 10
            h = max(
                self._stream_height_floor,
                self._last_applied_height,
                self.height(),
                doc_h,
            )
            self._stream_height_floor = h
            self._last_applied_height = h
            self.setFixedHeight(h)
        finally:
            self._suppress_reflow = False

    def _connect_plain_reflow_guard(self):
        try:
            self.document().contentsChanged.disconnect(self._schedule_reflow)
        except (TypeError, RuntimeError):
            pass

    def _disconnect_plain_reflow_guard(self):
        try:
            self.document().contentsChanged.connect(self._schedule_reflow)
        except (TypeError, RuntimeError):
            pass

    def _lock_stream_width(self, inner_width: int):
        self._stream_height_floor = 0
        self._stream_floor_h = 24
        self._layout_max_width = max(120, inner_width)
        self.setMaximumWidth(self._layout_max_width)
        self._connect_plain_reflow_guard()
        margin = int(self.document().documentMargin()) * 2
        inner_w = max(48, self._layout_max_width - margin - self._content_pad)
        self.setFixedWidth(self._layout_max_width)
        self.document().setTextWidth(inner_w)
        self._width_locked = True

    def start_plain_stream(self, inner_width: int):
        """流式：锁定卡片内宽度，纯文本增量输出。"""
        self._plain_streaming = True
        self._rich_streaming = False
        self._stream_layout_mode = True
        self._html_stream_mode = False
        self._plain_stream = True
        self._last_plain_base = ""
        self._last_plain_render = ""
        self._had_cursor = False
        self._plain_fmt_done = False
        self._lock_stream_width(inner_width)

    def stop_plain_stream(self, reflow: bool = True):
        self._plain_streaming = False
        self.end_stream_layout(reflow=reflow)

    def start_rich_stream(self, inner_width: int):
        """流式：锁定宽度，从首字起用富文本 HTML 增量渲染。"""
        self._rich_streaming = True
        self._plain_streaming = False
        self._plain_stream = False
        self._ai_full_width = True
        self._last_stream_render = ""
        self._lock_stream_width(inner_width)
        self.begin_stream_html()

    def stop_rich_stream(self, reflow: bool = True):
        self._rich_streaming = False
        self.end_stream_layout(reflow=reflow)

    def remove_trailing_stream_cursor(self) -> bool:
        """就地删除末尾光标，避免 setHtml 整段重绘闪烁。"""
        doc = self.document()
        if not (self.toPlainText() or "").endswith("▍"):
            return False
        self._suppress_reflow = True
        self.setUpdatesEnabled(False)
        doc.blockSignals(True)
        try:
            cur = QTextCursor(doc)
            cur.movePosition(QTextCursor.MoveOperation.End)
            cur.movePosition(
                QTextCursor.MoveOperation.PreviousCharacter,
                QTextCursor.MoveMode.KeepAnchor,
                1,
            )
            if cur.selectedText() != "▍":
                pos = max(0, doc.characterCount() - 8)
                found = doc.find("▍", pos)
                if found.isNull():
                    return False
                cur = found
                cur.movePosition(
                    QTextCursor.MoveOperation.NextCharacter,
                    QTextCursor.MoveMode.KeepAnchor,
                    1,
                )
                if cur.selectedText() != "▍":
                    return False
            cur.removeSelectedText()
            self._had_cursor = False
            if self._last_stream_render:
                self._last_stream_render = self.strip_stream_cursor_html(
                    self._last_stream_render
                )
            return True
        finally:
            doc.blockSignals(False)
            self.setUpdatesEnabled(True)
            self._suppress_reflow = False

    def begin_stream_html(self):
        self.begin_stream_layout()
        self._stream_height_floor = 0
        self._stream_width_floor = max(self._stream_width_floor, self.width())
        self.lock_layout_width(True)

    def paint_stream_frame(self, text: str, show_cursor: bool = True) -> bool:
        """按帧绘制纯文本（整帧一次提交，避免删插光标导致闪烁）。"""
        if not self._plain_streaming:
            self.start_plain_stream(self._layout_max_width)
        base = text or ""
        display = base + ("▍" if show_cursor else "")
        if display == self._last_plain_render:
            return False
        self.set_stream_measure_text(base)
        doc = self.document()
        doc.blockSignals(True)
        try:
            self.setPlainText(display)
            if not self._plain_fmt_done:
                self._apply_plain_block_spacing()
                self._plain_fmt_done = True
            self._last_plain_base = base
            self._last_plain_render = display
            self._had_cursor = bool(show_cursor)
        finally:
            doc.blockSignals(False)
        self._sync_stream_height_throttled()
        return True

    def lock_layout_width(self, locked: bool = True, reflow: bool = True):
        """流式输出期间锁定为最大行宽，避免随短文本越变越窄。"""
        self._width_locked = locked
        if locked:
            self._apply_locked_width()
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(self._layout_max_width)
        if reflow:
            self._schedule_reflow()

    def _apply_locked_width(self):
        layout_max = self._layout_max_width
        margin = int(self.document().documentMargin()) * 2
        inner_w = max(48, layout_max - margin - self._content_pad)
        self.setFixedWidth(layout_max)
        self.document().setTextWidth(inner_w)

    def set_layout_max_width(self, max_width: int):
        self._layout_max_width = max(120, max_width)
        self.setMaximumWidth(self._layout_max_width)
        if self._width_locked:
            self._apply_locked_width()
        self._schedule_reflow()

    def set_stream_measure_text(self, text: str):
        """用未排版折行的原文测量行宽，避免 QTextEdit 窄宽度反馈循环。"""
        self._stream_measure_text = (text or "").replace("▍", "")

    def set_bubble_html(
        self,
        html: str,
        *,
        stream: bool = False,
        skip_reflow: bool = False,
        force: bool = False,
    ):
        if not force:
            if stream:
                if html == self._last_stream_render:
                    return
            elif html == self._last_stream_render:
                return
        self._last_stream_render = html
        doc = self.document()
        if stream:
            self._suppress_reflow = True
            self.setUpdatesEnabled(False)
            doc.blockSignals(True)
            try:
                if self._rich_doc_css:
                    doc.setDefaultStyleSheet(self._rich_doc_css)
                self.setHtml(html or "")
            finally:
                doc.blockSignals(False)
                self._suppress_reflow = False
                self.setUpdatesEnabled(True)
            self._sync_stream_height_throttled()
            return
        self.setUpdatesEnabled(False)
        try:
            if self._rich_doc_css:
                doc.setDefaultStyleSheet(self._rich_doc_css)
            self.setHtml(html or "")
            self._align_document_left()
        finally:
            self.setUpdatesEnabled(True)
        if not skip_reflow:
            self._reflow()

    def set_bubble_plain(self, text: str):
        self.setPlainText(text or "")
        self._apply_plain_block_spacing()
        if (
            self._plain_streaming
            or self._rich_streaming
            or self._stream_layout_mode
            or self._width_locked
        ):
            self._schedule_reflow()
        else:
            self._reflow()

    def _needs_full_width(self) -> bool:
        if (
            self._stream_layout_mode
            or self._width_locked
            or self._ai_full_width
        ):
            return True
        raw = self._stream_measure_text or (self.toPlainText() or "")
        if len(raw) >= AI_STREAM_FULL_WIDTH_CHARS or raw.count("\n") >= 2:
            return True
        if "```" in raw:
            return True
        low = self.toHtml().lower()
        return "<pre" in low or "<table" in low or "<h1" in low or "<h2" in low

    def _measure_plain_inner_width(self, max_inner: int) -> int:
        """按可见纯文本最长行测算宽度；HTML idealWidth 在流式时偏窄。"""
        plain = (self._stream_measure_text or (self.toPlainText() or "")).replace(
            "▍", ""
        ).strip()
        if not plain:
            return 32
        fm = QFontMetrics(self.font())
        widest = 0
        for line in plain.replace("\r", "").split("\n"):
            if line:
                widest = max(widest, fm.horizontalAdvance(line))
        return min(max_inner, max(32, widest + 20))

    def _document_content_height(self) -> int:
        doc = self.document()
        layout = doc.documentLayout()
        if layout is not None:
            doc_h = layout.documentSize().height()
        else:
            doc_h = doc.size().height()
        plain = (self.toPlainText() or "").replace("▍", "").strip()
        if not plain:
            measure = (self._stream_measure_text or "").replace("▍", "").strip()
            if not measure:
                lh = self._line_height_px_for_font(self.font())
                return max(22, min(int(doc_h) + 6, lh + 14))
        return max(22, int(doc_h) + 6)

    def _apply_widget_height(self, h: int):
        h = max(20, h)
        if self._stream_layout_mode:
            self._stream_height_floor = max(self._stream_height_floor, h)
            h = self._stream_height_floor
        if h == self._last_applied_height:
            return
        self._last_applied_height = h
        self.setFixedHeight(h)

    def _reflow_height_only(self):
        self._apply_widget_height(self._document_content_height() + 8)

    def _reflow(self):
        if self._width_locked:
            self._apply_locked_width()
            self._reflow_height_only()
            return
        doc = self.document()
        margin = int(doc.documentMargin()) * 2
        pad = self._content_pad
        layout_max = self._layout_max_width
        max_inner = max(48, layout_max - margin - pad)

        if self._needs_full_width():
            inner_w = max_inner
            widget_w = layout_max
        else:
            inner_w = self._measure_plain_inner_width(max_inner)
            widget_w = min(
                layout_max, max(AI_BUBBLE_MIN_W, inner_w + margin + pad)
            )

        doc.setTextWidth(inner_w)
        self.setFixedWidth(widget_w)
        self._apply_widget_height(self._document_content_height() + 10)


class AiConfigStore:
    """仅 AI 模块读写，不使用账号数据库与其它设置。"""

    @staticmethod
    def _path() -> str:
        return os.path.join(AppPaths.data_root(), AI_CONFIG_FILENAME)

    @staticmethod
    def load_api_key() -> str:
        path = AiConfigStore._path()
        try:
            if not os.path.isfile(path):
                return ""
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return (data.get("api_key") or "").strip()
        except Exception:
            return ""

    @staticmethod
    def save_api_key(key: str) -> None:
        path = AiConfigStore._path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"api_key": key.strip()}, f, ensure_ascii=False)
        except Exception as e:
            print(f"保存 AI API 密钥失败: {e}")


class DeepSeekStreamWorker(QThread):
    """用 urllib + HTTP/1.1 拉流，规避 Qt 网络栈的 HTTP/2 protocol error。"""

    chunk_received = pyqtSignal(str)
    finished_with_text = pyqtSignal(str)
    failed = pyqtSignal(str)

    _MAX_RETRIES = 2
    _RETRY_DELAY_S = 0.6

    def __init__(self, api_key: str, messages: List[dict], parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._messages = list(messages)
        self._abort = False
        self._full_text = ""

    def request_abort(self):
        self._abort = True

    @staticmethod
    def _is_retriable(err: str) -> bool:
        low = (err or "").lower()
        keys = (
            "http/2",
            "protocol error",
            "connection reset",
            "connection aborted",
            "timed out",
            "timeout",
            "temporary failure",
            "eof",
            "broken pipe",
        )
        return any(k in low for k in keys)

    @staticmethod
    def _http_error_message(exc: urllib.error.HTTPError) -> str:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            detail = json.loads(raw).get("error", {})
            if isinstance(detail, dict) and detail.get("message"):
                return str(detail["message"])
        except Exception:
            pass
        return f"HTTP {exc.code}: {exc.reason}"

    def _emit_sse_line(self, line: str):
        if not line.startswith("data:"):
            return
        data = line[5:].strip()
        if not data or data == "[DONE]":
            return
        try:
            obj = json.loads(data)
            delta = (obj.get("choices") or [{}])[0].get("delta") or {}
            piece = sanitize_ai_display_text(delta.get("content") or "")
            if piece:
                self._full_text += piece
                self.chunk_received.emit(piece)
        except json.JSONDecodeError:
            pass

    def _stream_once(self):
        payload = {
            "model": AI_DEEPSEEK_MODEL,
            "messages": self._messages,
            "max_tokens": AI_MAX_OUTPUT_TOKENS,
            "temperature": 0.78,
            "stream": True,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            AI_DEEPSEEK_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "text/event-stream",
                "User-Agent": "TeamsXAi/2.0",
                "Connection": "close",
            },
            method="POST",
        )
        self._full_text = ""
        sse_buf = ""
        with urllib.request.urlopen(req, timeout=120, context=_urllib_ssl_context()) as resp:
            while not self._abort:
                chunk = resp.read(4096)
                if not chunk:
                    break
                sse_buf += chunk.decode("utf-8", errors="replace")
                while "\n" in sse_buf:
                    line, sse_buf = sse_buf.split("\n", 1)
                    self._emit_sse_line(line.strip())
        if not self._abort and sse_buf.strip():
            for line in sse_buf.splitlines():
                self._emit_sse_line(line.strip())

    def run(self):
        last_err = "网络错误"
        for attempt in range(self._MAX_RETRIES + 1):
            if self._abort:
                return
            try:
                self._stream_once()
                if self._abort:
                    return
                text = (self._full_text or "").strip()
                self.finished_with_text.emit(text or "（无回复内容）")
                return
            except urllib.error.HTTPError as exc:
                last_err = self._http_error_message(exc)
                break
            except Exception as exc:
                last_err = str(exc).strip() or "网络错误"
                if attempt >= self._MAX_RETRIES or not self._is_retriable(last_err):
                    break
                time.sleep(self._RETRY_DELAY_S * (attempt + 1))
        if not self._abort:
            self.failed.emit(last_err)


class DeepSeekAiClient(QObject):
    """DeepSeek Chat Completions 流式（SSE）。"""

    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[DeepSeekStreamWorker] = None

    def cancel(self):
        worker = self._worker
        if worker is None:
            return
        worker.request_abort()
        if worker.isRunning():
            worker.wait(2500)
        self._worker = None

    def chat(self, api_key: str, messages: List[dict]):
        self.cancel()
        worker = DeepSeekStreamWorker(api_key, messages, self)
        self._worker = worker
        worker.chunk_received.connect(self.chunk_received)
        worker.finished_with_text.connect(self._on_worker_finished)
        worker.failed.connect(self.failed)
        worker.finished.connect(self._on_worker_thread_finished)
        worker.start()

    def _on_worker_finished(self, text: str):
        self.finished.emit(text)

    def _on_worker_thread_finished(self):
        sender = self.sender()
        if sender is self._worker:
            self._worker = None


class AiChatPanel(QWidget):
    """ESC 主界面 TeamsXAi：DeepSeek 对话，与 Teams WebView 完全隔离。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._api_key = AiConfigStore.load_api_key()
        self._awaiting_new_api = False
        self._busy = False
        self._context: deque = deque(maxlen=AI_CONTEXT_TURNS * 2)
        self._messages: List[dict] = []
        self._stream_target = ""
        self._stream_visible = ""
        self._stream_api_done = False
        self._stream_active = False
        self._stream_paused = False
        self._stream_tick_count = 0
        self._stream_scroll_h = 0
        self._stream_last_scroll_ms = 0.0
        self._ignore_ai_signals = False
        self._pending_user = ""
        self._client = DeepSeekAiClient(self)
        self._client.chunk_received.connect(self._on_stream_chunk)
        self._client.finished.connect(self._on_stream_finished)
        self._client.failed.connect(self._on_ai_error)
        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(AI_STREAM_TICK_MS)
        self._stream_timer.timeout.connect(self._stream_tick)
        self._stream_paint_timer = QTimer(self)
        self._stream_paint_timer.setInterval(AI_STREAM_PAINT_MS)
        self._stream_paint_timer.timeout.connect(self._flush_stream_paint)
        self._chat_resize_timer = QTimer(self)
        self._chat_resize_timer.setSingleShot(True)
        self._chat_resize_timer.setInterval(AI_STREAM_RESIZE_DEBOUNCE_MS)
        self._chat_resize_timer.timeout.connect(self._on_chat_resize_debounced)
        self._chat_resize_streaming = False
        self._stream_last_paint_height = 0
        self._identity_re = re.compile(AI_IDENTITY_PATTERNS, re.IGNORECASE)
        self._chat_layout_active = False
        self._center_zone = None
        self._composer_bottom = None
        self._theme_light = False
        self._thinking_visible = False
        self._waiting_first_chunk = False
        self._user_scrolled_up = False
        self._cursor_on = True
        self._thinking_widget: Optional[AiThinkingDotsWidget] = None
        self._thinking_just_removed = False
        self._cursor_blink_timer = QTimer(self)
        self._cursor_blink_timer.setInterval(AI_CURSOR_BLINK_MS)
        self._cursor_blink_timer.timeout.connect(self._blink_stream_cursor)
        self._build_ui()
        self._input.installEventFilter(self)
        self._input.textChanged.connect(self._adjust_input_height)
        bar = self._chat_scroll.verticalScrollBar()
        bar.valueChanged.connect(self._on_chat_scroll)
        QTimer.singleShot(0, self._focus_input)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._focus_input)
        QTimer.singleShot(0, self._sync_composer_width)
        if self._chat_layout_active and self._messages:
            QTimer.singleShot(
                0,
                lambda: self._schedule_chat_relayout(
                    streaming=self._stream_active
                ),
            )

    def _focus_input(self):
        if not hasattr(self, "_input") or not self._input.isEnabled():
            return
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)
        cursor = self._input.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._input.setTextCursor(cursor)

    def eventFilter(self, watched, event):
        if watched is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                self._send_message()
                return True
        return super().eventFilter(watched, event)

    def _adjust_input_height(self):
        doc = self._input.document()
        vw = max(80, self._input.viewport().width() - 8)
        doc.setTextWidth(vw)
        doc_h = int(doc.size().height())
        h = max(AI_INPUT_MIN_H, min(AI_INPUT_MAX_H, doc_h + 20))
        self._input.setFixedHeight(h)
        self._composer_inner.setMinimumHeight(h + 8)
        self._send_btn.setFixedSize(52, min(h, 48))
        if self._chat_layout_active:
            self._apply_chat_bottom_pad()
            if not self._user_scrolled_up:
                QTimer.singleShot(0, lambda: self._scroll_bottom(force=True))

    def _composer_side_margin(self) -> int:
        if self._chat_layout_active:
            return AI_COMPOSER_SIDE_MARGIN
        return 48

    def _sync_composer_width(self) -> None:
        wrap = getattr(self, "_composer_wrap", None)
        if wrap is None:
            return
        available = max(
            AI_COMPOSER_MIN_W,
            self.width() - self._composer_side_margin(),
        )
        cw = min(AI_COMPOSER_MAX_W, available)
        wrap.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        wrap.setMinimumWidth(cw)
        wrap.setMaximumWidth(cw)
        if hasattr(self, "_input"):
            self._adjust_input_height()

    def _ai_content_side_margins(self) -> Tuple[int, int, int, int]:
        return (
            max(0, AI_CHAT_PAD_LEFT - AI_REPLY_SHIFT_LEFT),
            AI_ROW_V_MARGIN,
            AI_CHAT_PAD_RIGHT + AI_REPLY_SHIFT_LEFT,
            0,
        )

    def _ai_text_start_inset(self) -> int:
        return AI_AI_CARD_PAD + AI_MSG_CONTENT_PAD

    def _chat_bottom_clearance(self) -> int:
        """对话区底部留白，避免最后几行贴住或被输入框挡住。"""
        if not self._chat_layout_active:
            return AI_CHAT_BOTTOM_PAD_MIN
        comp_h = 0
        if getattr(self, "_composer_bottom", None) is not None:
            comp_h = self._composer_bottom.height()
        return max(AI_CHAT_BOTTOM_PAD_MIN, comp_h + 24)

    def _apply_chat_bottom_pad(self):
        pad = self._chat_bottom_clearance()
        m = self._chat_layout.contentsMargins()
        if m.bottom() != pad:
            self._chat_layout.setContentsMargins(
                m.left(), m.top(), m.right(), pad
            )

    def _is_identity_question(self, text: str) -> bool:
        t = (text or "").strip()
        if not t or len(t) > 120:
            return False
        if self._identity_re.search(t):
            return True
        low = t.lower().replace(" ", "")
        explicit = (
            "你是什么ai", "你是什么人工智能", "你是什么模型", "你是哪个ai",
            "你是谁", "你叫什么", "whataiareyou", "whichaiareyou",
            "whoareyou", "whatareyou", "whatmodelareyou",
        )
        return any(k in low for k in explicit)

    def _build_ui(self):
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._title = QLabel("TeamsXAi")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._chat_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._chat_scroll.setViewportMargins(0, 0, 0, 0)
        self._chat_content = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_content)
        self._chat_layout.setContentsMargins(0, 12, 0, AI_CHAT_BOTTOM_PAD_MIN)
        self._chat_layout.setSpacing(0)
        self._chat_scroll.setWidget(self._chat_content)
        self._chat_scroll.hide()
        self._last_ai_bubble: Optional[ChatBubbleTextEdit] = None
        self._last_ai_row: Optional[QWidget] = None
        self._last_user_max_width: Optional[int] = None

        self._composer_inner = QWidget()
        composer_row = QHBoxLayout(self._composer_inner)
        composer_row.setContentsMargins(12, 6, 10, 6)
        composer_row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setPlaceholderText("给 TeamsXAi 发送消息")
        self._input.setFixedHeight(AI_INPUT_MIN_H)
        self._input.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._input.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._input.setAcceptRichText(False)
        self._send_btn = QPushButton("Go")
        self._send_btn.setFixedSize(52, 44)
        self._send_btn.setToolTip("发送 (Enter)")
        self._send_btn.clicked.connect(self._on_compose_button)
        composer_row.addWidget(self._input, 1)
        composer_row.addWidget(self._send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._composer_wrap = QWidget()
        self._composer_wrap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        wrap_row = QHBoxLayout(self._composer_wrap)
        wrap_row.setContentsMargins(0, 0, 0, 0)
        wrap_row.addWidget(self._composer_inner)

        self._root_layout.addWidget(self._title, 0)

        self._center_zone = QWidget()
        center_layout = QVBoxLayout(self._center_zone)
        center_layout.setContentsMargins(24, 0, 24, 0)
        center_layout.setSpacing(0)
        center_layout.addStretch(1)
        center_layout.addWidget(
            self._composer_wrap, 0, Qt.AlignmentFlag.AlignHCenter
        )
        center_layout.addStretch(1)
        self._root_layout.addWidget(self._center_zone, 1)

        self._apply_ui_fonts()
        self.apply_theme(CURRENT_THEME == "light")
        self._sync_composer_width()

    def _activate_chat_layout(self):
        """首条消息后：输入框回到底部，上方显示对话区。"""
        if self._chat_layout_active:
            return
        self._chat_layout_active = True

        center_layout = self._center_zone.layout()
        if center_layout:
            center_layout.removeWidget(self._composer_wrap)
        self._root_layout.removeWidget(self._center_zone)
        self._center_zone.deleteLater()
        self._center_zone = None

        self._root_layout.insertWidget(1, self._chat_scroll, 1)
        self._chat_scroll.show()

        self._composer_bottom = QWidget()
        bot_layout = QVBoxLayout(self._composer_bottom)
        bot_layout.setContentsMargins(0, 8, 0, 16)
        bot_row = QHBoxLayout()
        bot_row.setContentsMargins(20, 0, 20, 0)
        bot_row.addStretch(1)
        self._composer_wrap.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        bot_row.addWidget(
            self._composer_wrap, 0, Qt.AlignmentFlag.AlignHCenter
        )
        bot_row.addStretch(1)
        bot_layout.addLayout(bot_row)
        self._root_layout.addWidget(self._composer_bottom, 0)
        self._sync_composer_width()
        self._apply_chat_bottom_pad()

    def _message_font(self) -> QFont:
        f = QFont("Segoe UI", AI_MSG_FONT_PT)
        f.setStyleHint(QFont.StyleHint.SansSerif)
        return f

    def _apply_ui_fonts(self):
        """Segoe UI 为主，与 DeepSeek 网页版 Windows 观感一致。"""
        chat_font = self._message_font()
        self._chat_content.setFont(chat_font)
        inp_font = self._message_font()
        self._input.setFont(inp_font)
        title_font = QFont("Segoe UI", 15)
        title_font.setWeight(QFont.Weight.Bold)
        self._title.setFont(title_font)
        btn_font = QFont("Segoe UI", 10)
        btn_font.setWeight(QFont.Weight.Medium)
        self._send_btn.setFont(btn_font)

    def apply_theme(self, light: bool):
        self._theme_light = light
        for attr in ("_bubble_doc_css_light", "_bubble_doc_css_dark"):
            if hasattr(self, attr):
                delattr(self, attr)
        ff = AI_UI_FONT_FAMILY
        if light:
            pane_bg = "#ffffff"
            composer_bg = "#ffffff"
            composer_border = "#e3e3e3"
            title_color = "#1a1a1a"
            input_text = "#1a1a1a"
            self._color_user = "#1a1a1a"
            self._color_ai = "#1c1c1c"
            btn_bg, btn_hover, btn_dis = "#ececec", "#dedede", "#f5f5f5"
            btn_fg, btn_dis_fg = "#1a1a1a", "#aaaaaa"
            chat_default = "#1c1c1c"
        else:
            pane_bg = "#1e1e1e"
            composer_bg = "#2a2a2a"
            composer_border = "#4a4a4a"
            title_color = "#e8e8e8"
            input_text = "#ececec"
            self._color_user = "#e8e8e8"
            self._color_ai = "#ececec"
            btn_bg, btn_hover, btn_dis = "#4a4a4a", "#5a5a5a", "#333333"
            btn_fg, btn_dis_fg = "#ffffff", "#666666"
            chat_default = "#ececec"

        self.setStyleSheet(f"background-color: {pane_bg};")
        self._title.setStyleSheet(
            f"color: {title_color}; font-family: {ff}; "
            f"font-size: 13pt; font-weight: 700; "
            f"padding: 16px 16px 12px; background: transparent; "
            f"letter-spacing: 0.2px;"
        )
        if light:
            sb_handle, sb_hover = "#e8e8ec", "#dcdce0"
        else:
            sb_handle, sb_hover = "#555555", "#666666"
        self._chat_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {pane_bg}; border: none; }}"
            f"QWidget#aiChatContent {{ background-color: {pane_bg}; }}"
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {sb_handle}; border-radius: 3px; min-height: 24px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {sb_hover}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self._chat_content.setObjectName("aiChatContent")
        self._chat_content.setStyleSheet(f"background-color: {pane_bg};")
        if light:
            send_bg, send_hover, send_fg = "#d4d4da", "#c4c4cc", "#1a1a1a"
        else:
            send_bg, send_hover, send_fg = "#4a4a52", "#56565e", "#ececec"
        self._composer_inner.setStyleSheet(
            f"background-color: {composer_bg}; "
            f"border: 1px solid {composer_border}; border-radius: 18px;"
        )
        self._input.setStyleSheet(
            f"background: transparent; color: {input_text}; "
            f"font-family: {ff}; font-size: {AI_MSG_FONT_PT}pt; "
            f"padding: 10px 6px; border: none;"
        )
        self._send_btn.setStyleSheet(
            f"QPushButton {{ font-family: {ff}; font-size: 13px; font-weight: 600; "
            f"background-color: {send_bg}; color: {send_fg}; border-radius: 12px; "
            f"border: none; min-width: 48px; min-height: 40px; }}"
            f"QPushButton:hover {{ background-color: {send_hover}; }}"
            f"QPushButton:disabled {{ background-color: {btn_dis}; color: {btn_dis_fg}; }}"
        )
        if getattr(self, "_composer_bottom", None) is not None:
            try:
                self._composer_bottom.setStyleSheet(f"background-color: {pane_bg};")
            except RuntimeError:
                self._composer_bottom = None
        cz = getattr(self, "_center_zone", None)
        if cz is not None:
            try:
                cz.setStyleSheet(f"background-color: {pane_bg};")
            except RuntimeError:
                self._center_zone = None
        dots = self._thinking_dots_widget()
        if dots is not None:
            try:
                dots.set_theme_light(light)
            except RuntimeError:
                self._thinking_widget = None
        if self._messages:
            self._apply_theme_to_existing_chat()

    @staticmethod
    def _escape_html_plain(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @classmethod
    def _escape_html(cls, text: str) -> str:
        return cls._escape_html_plain(text).replace("\n", "<br>")

    def _user_message_stylesheet(self) -> str:
        if getattr(self, "_theme_light", False):
            bg, fg = AI_USER_BG_LIGHT, AI_USER_FG_LIGHT
        else:
            bg, fg = AI_USER_BG_DARK, AI_USER_FG_DARK
        return (
            f"QTextEdit {{ color: {fg}; background-color: {bg}; border: none; "
            f"border-radius: {AI_USER_CAPSULE_RADIUS}px; "
            f"padding: 10px 14px; font-family: {AI_UI_FONT_FAMILY}; "
            f"font-size: {AI_MSG_FONT_PT}pt; }}"
        )

    def _ai_message_stylesheet(self) -> str:
        # 勿在 QTextEdit 上设 color/font-size，否则会盖掉 setHtml 里的加粗/标题/颜色
        return (
            "QTextEdit { background: transparent; border: none; "
            f"padding: 2px 0; font-family: {AI_UI_FONT_FAMILY}; }}"
        )

    def _ai_card_stylesheet(self) -> str:
        return "QFrame#aiMessageCard { background: transparent; border: none; }"

    def _wrap_ai_message_card(
        self, bubble: ChatBubbleTextEdit, max_width: int
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("aiMessageCard")
        card.setStyleSheet(self._ai_card_stylesheet())
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        card.setMaximumWidth(max_width)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(
            AI_AI_CARD_PAD, AI_AI_CARD_PAD, AI_AI_CARD_PAD, AI_AI_CARD_PAD
        )
        lay.setSpacing(0)
        lay.addWidget(bubble)
        return card

    def _teamsx_markdown_css(self) -> str:
        """Markdown + Pygments 规则（仅用于 QTextDocument.defaultStyleSheet）。"""
        theme_key = "light" if getattr(self, "_theme_light", False) else "dark"
        cache_attr = f"_bubble_doc_css_{theme_key}"
        cached = getattr(self, cache_attr, None)
        if cached is not None:
            return cached
        pal = self._ai_rich_palette()
        ff = AI_UI_FONT_FAMILY
        pt = AI_MSG_FONT_PT
        pygments_style = "friendly" if theme_key == "light" else "monokai"
        pygments_css = _pygments_highlight_css(pygments_style, ".codehilite")
        pygments_md = _pygments_highlight_css(pygments_style, ".teamsx-md .codehilite")
        block = self._code_block_style()
        inline = self._code_inline_style()
        code_base = "#1e1e1e" if theme_key == "light" else "#d4d4d4"
        css = (
            f".teamsx-md {{ color: {pal['text']}; }} "
            f".teamsx-md p {{ {self._ai_para_style(14)} }}"
            f".teamsx-md p:last-child {{ {self._ai_para_style(18)} }}"
            f".teamsx-md h1 {{ {self._ai_heading_style(1)} }}"
            f".teamsx-md h2 {{ {self._ai_heading_style(2)} }}"
            f".teamsx-md h3 {{ {self._ai_heading_style(3)} }}"
            f".teamsx-md h4, .teamsx-md h5, .teamsx-md h6 {{ "
            f"{self._ai_heading_style(3)} }}"
            f".teamsx-md ul, .teamsx-md ol {{ "
            f"{self._ai_para_style(8)} margin-left:22px; padding-left:4px; "
            f"display: block; list-style-position: outside; }}"
            f".teamsx-md ul {{ list-style-type: disc; }}"
            f".teamsx-md ol {{ list-style-type: decimal; }}"
            f".teamsx-md li {{ margin:4px 0; display: list-item; }}"
            f".teamsx-md blockquote {{ {self._ai_quote_block_style()} }}"
            f".teamsx-md table {{ "
            f"border-collapse:collapse; margin:10px 0 14px 0; width:100%; }}"
            f".teamsx-md th, .teamsx-md td {{ "
            f"border:1px solid {pal['quote_border']}; padding:6px 10px; "
            f"font-family:{ff}; font-size:{pt}pt; color:{pal['text']}; }}"
            f".teamsx-md th {{ background:{pal['quote_bg']}; font-weight:600; }}"
            f".teamsx-md a {{ color:#0078d4; text-decoration:none; }}"
            f".teamsx-md pre, .teamsx-md .codehilite, .teamsx-md .codehilite pre {{ "
            f"{block} color:{code_base}; }}"
            f".teamsx-md .codehilite span, .teamsx-md .codehilite .hll, "
            f".teamsx-md pre span, .codehilite span {{ "
            f"background: transparent !important; "
            f"background-color: transparent !important; }}"
            f".teamsx-md code {{ {inline} }}"
            f".teamsx-md .codehilite {{ margin:10px 0 14px 0; }}"
            f"{pygments_css} {pygments_md}"
        )
        setattr(self, cache_attr, css)
        return css

    def _bubble_rich_document_css(self) -> str:
        pal = self._ai_rich_palette()
        pt = AI_MSG_FONT_PT
        return (
            "body { margin: 0; padding: 0; text-align: left; } "
            f"p {{ margin: 0 0 12px 0; text-align: left; color: {pal['text']}; "
            f"font-size: {pt}pt; font-family: {AI_UI_FONT_FAMILY}; line-height: 1.72; }} "
            f"h1 {{ margin: 2px 0 16px 0; font-size: {pt + 7}pt; font-weight: bold; "
            f"color: {pal['h1']}; font-family: {AI_UI_FONT_FAMILY}; text-align: left; }} "
            f"h2 {{ margin: 16px 0 10px 0; font-size: {pt + 4}pt; font-weight: bold; "
            f"color: {pal['h2']}; font-family: {AI_UI_FONT_FAMILY}; text-align: left; }} "
            f"h3 {{ margin: 12px 0 8px 0; font-size: {pt + 1}pt; font-weight: bold; "
            f"color: {pal['h3']}; font-family: {AI_UI_FONT_FAMILY}; text-align: left; }} "
            f"b, strong {{ font-weight: bold; color: {pal['strong']}; }} "
            f"em, i {{ font-style: italic; color: {pal['text']}; }} "
            f"pre, code {{ font-family: {AI_CODE_FONT_FAMILY}; text-align: left; }} "
            f"{self._teamsx_markdown_css()}"
        )

    def _apply_bubble_rich_defaults(
        self, bubble: ChatBubbleTextEdit, *, mark_dirty: bool = True
    ):
        css = self._bubble_rich_document_css()
        bubble.set_rich_document_defaults(css, mark_dirty=mark_dirty)

    def _ai_code_colors(self) -> Dict[str, str]:
        if getattr(self, "_theme_light", False):
            return {
                "text": "#1e1e1e",
                "kw": "#0000ff",
                "str": "#a31515",
                "comment": "#008000",
                "num": "#098658",
            }
        return {
            "text": "#d4d4d4",
            "kw": "#569cd6",
            "str": "#ce9178",
            "comment": "#6a9955",
            "num": "#b5cea8",
        }

    def _code_color_span(self, color: str, text: str) -> str:
        return f'<span style="color:{color};">{text}</span>'

    def _highlight_code_plain_segment(self, segment: str, pal: Dict[str, str]) -> str:
        if not segment:
            return ""
        out = segment
        out = AI_CODE_COMMENT_RE.sub(
            lambda m: self._code_color_span(pal["comment"], m.group(0)), out
        )
        out = AI_CODE_KW_RE.sub(
            lambda m: self._code_color_span(pal["kw"], m.group(0)), out
        )
        out = AI_CODE_NUM_RE.sub(
            lambda m: self._code_color_span(pal["num"], m.group(0)), out
        )
        if "<span" not in out:
            return self._code_color_span(pal["text"], out)
        return out

    def _highlight_code_line_html(self, line: str) -> str:
        pal = self._ai_code_colors()
        esc = self._escape_html_plain(line)
        if not esc:
            return ""
        parts: List[Tuple[str, str]] = []
        pos = 0
        for m in AI_CODE_STR_RE.finditer(esc):
            if m.start() > pos:
                parts.append(("code", esc[pos : m.start()]))
            parts.append(("str", m.group(0)))
            pos = m.end()
        if pos < len(esc):
            parts.append(("code", esc[pos:]))
        if not parts:
            parts.append(("code", esc))
        rendered: List[str] = []
        for kind, seg in parts:
            if kind == "str":
                rendered.append(self._code_color_span(pal["str"], seg))
            else:
                rendered.append(self._highlight_code_plain_segment(seg, pal))
        return "".join(rendered)

    def _highlight_code_html(self, code: str) -> str:
        lines = code.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return "<br>".join(self._highlight_code_line_html(ln) for ln in lines)

    def _remember_last_ai_row(self, bubble: ChatBubbleTextEdit):
        """bubble -> 卡片 -> 行容器。"""
        card = bubble.parent()
        if card is not None and card.parent() is not None:
            self._last_ai_row = card.parent()
        self._last_ai_bubble = bubble

    def _collect_chat_bubbles_in_order(self) -> List[ChatBubbleTextEdit]:
        bubbles: List[ChatBubbleTextEdit] = []
        for i in range(self._chat_layout.count()):
            item = self._chat_layout.itemAt(i)
            if item is None:
                continue
            row = item.widget()
            if row is None:
                continue
            found = row.findChildren(ChatBubbleTextEdit)
            if found:
                bubbles.append(found[0])
        return bubbles

    def _apply_theme_to_existing_chat(self):
        """换主题：更新样式表并按原文重绘（流式/历史同一路径，代码不丢）。"""
        if not self._messages:
            return
        scroll_val, _, pin_bottom = self._chat_scroll_snapshot()
        bubbles = self._collect_chat_bubbles_in_order()
        if len(bubbles) != len(self._messages):
            self._refresh_chat_view(
                show_cursor=self._stream_active,
                scroll=not self._user_scrolled_up,
            )
            return

        wrap_w = self._message_wrap_max_width()
        inner_w = max(AI_MSG_WRAP_MIN_PX, wrap_w - AI_AI_CARD_PAD * 2)
        bar = self._chat_scroll.verticalScrollBar()
        bar.blockSignals(True)
        self._chat_content.setUpdatesEnabled(False)
        try:
            for card in self._chat_content.findChildren(QFrame):
                if card.objectName() == "aiMessageCard":
                    card.setStyleSheet(self._ai_card_stylesheet())
            for msg, bubble in zip(self._messages, bubbles):
                bubble.setFont(self._message_font())
                if msg["role"] == "user":
                    bubble.setStyleSheet(self._user_message_stylesheet())
                    bubble.viewport().update()
                    continue
                bubble.setStyleSheet(self._ai_message_stylesheet())
                text = msg.get("content") or ""
                streaming = (
                    self._stream_active and bubble is self._last_ai_bubble
                )
                if streaming:
                    text = self._stream_visible or text
                self._paint_ai_bubble(
                    bubble,
                    text,
                    inner_w,
                    cursor=streaming and self._cursor_on,
                    stream=streaming,
                    force=True,
                )
        finally:
            self._chat_content.setUpdatesEnabled(True)
            bar.blockSignals(False)

        if pin_bottom:
            QTimer.singleShot(0, lambda: self._scroll_bottom(force=True))
        else:
            bar.setValue(min(scroll_val, bar.maximum()))

    def _on_chat_scroll(self, value: int):
        bar = self._chat_scroll.verticalScrollBar()
        self._user_scrolled_up = value < bar.maximum() - AI_SCROLL_PIN_THRESHOLD

    def _blink_stream_cursor(self):
        """流式期间保持常亮末尾光标，避免闪烁定时器触发布局抖动。"""
        return

    def _clear_chat_layout(self):
        self._last_ai_bubble = None
        self._last_ai_row = None
        self._last_user_max_width = None
        if self._thinking_widget is not None:
            self._thinking_widget.stop()
            self._thinking_widget = None
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_chat_gap(self, height_px: int):
        gap = QWidget()
        gap.setFixedHeight(max(0, height_px))
        gap.setStyleSheet("background: transparent;")
        self._chat_layout.addWidget(gap)

    def _chat_stretch_index(self) -> int:
        for i in range(self._chat_layout.count() - 1, -1, -1):
            item = self._chat_layout.itemAt(i)
            if item is not None and item.spacerItem() is not None:
                return i
        return -1

    def _remove_chat_stretch(self):
        idx = self._chat_stretch_index()
        if idx >= 0:
            self._chat_layout.takeAt(idx)

    def _append_chat_stretch(self):
        if self._chat_stretch_index() < 0:
            self._chat_layout.addStretch(1)

    def _remove_thinking_widget(self):
        if self._thinking_widget is None:
            return
        self._thinking_just_removed = True
        dots = self._thinking_dots_widget()
        if dots is not None:
            dots.stop()
        self._thinking_widget.setParent(None)
        self._thinking_widget.deleteLater()
        self._thinking_widget = None

    def _gap_before_message(self, msg_index: int) -> int:
        if msg_index <= 0:
            return 0
        prev_role = self._messages[msg_index - 1]["role"]
        cur_role = self._messages[msg_index]["role"]
        if prev_role != cur_role:
            return AI_MSG_GAP_ROLE_SWITCH
        return AI_MSG_GAP_SAME

    def _chat_scroll_snapshot(self) -> Tuple[int, int, bool]:
        bar = self._chat_scroll.verticalScrollBar()
        return bar.value(), bar.maximum(), not self._user_scrolled_up

    def _restore_chat_scroll(
        self, value: int, old_max: int, pin_bottom: bool
    ):
        def apply():
            bar = self._chat_scroll.verticalScrollBar()
            if pin_bottom:
                self._scroll_bottom(force=True)
                return
            mx = bar.maximum()
            if mx <= 0:
                bar.setValue(0)
                return
            if old_max <= 0:
                bar.setValue(min(value, mx))
            else:
                bar.setValue(min(int(value * mx / old_max), mx))

        apply()
        for ms in (0, 16, 50, 120):
            QTimer.singleShot(ms, apply)

    def _append_user_row_incremental(self, msg: dict):
        self._remove_chat_stretch()
        idx = len(self._messages) - 1
        if idx > 0:
            self._add_chat_gap(self._gap_before_message(idx))
        w = self._compute_message_widths()[idx]
        self._last_ai_bubble = None
        self._last_ai_row = None
        self._chat_layout.addWidget(self._make_user_row(msg, max_width=w))
        self._append_chat_stretch()

    def _append_thinking_row_incremental(self):
        self._remove_thinking_widget()
        self._remove_chat_stretch()
        self._thinking_widget = self._make_thinking_row()
        self._chat_layout.addWidget(self._thinking_widget)
        self._append_chat_stretch()

    def _replace_thinking_with_ai_row(self):
        idx = len(self._messages) - 1
        w = self._compute_message_widths()[idx]
        row, bubble = self._make_ai_row(
            self._messages[idx], cursor=True, max_width=w
        )
        self._chat_content.setUpdatesEnabled(False)
        try:
            for i in range(self._chat_layout.count()):
                item = self._chat_layout.itemAt(i)
                if item is None:
                    continue
                if item.widget() is self._thinking_widget:
                    old = self._thinking_widget
                    old_dots = self._thinking_dots_widget()
                    if old_dots is not None:
                        old_dots.stop()
                    old.hide()
                    self._thinking_widget = None
                    self._thinking_visible = False
                    self._chat_layout.insertWidget(i, row)
                    self._last_ai_row = row
                    self._last_ai_bubble = bubble
                    old.deleteLater()
                    return
            self._chat_layout.addWidget(row)
            self._last_ai_row = row
            self._last_ai_bubble = bubble
        finally:
            self._chat_content.setUpdatesEnabled(True)

    def _append_ai_stream_row_incremental(self):
        if (
            not self._messages
            or self._messages[-1]["role"] != "assistant"
        ):
            return
        if self._last_ai_bubble is not None and self._stream_active:
            return
        if self._thinking_widget is not None:
            self._replace_thinking_with_ai_row()
            self._append_chat_stretch()
            return
        self._remove_thinking_widget()
        self._thinking_visible = False
        self._remove_chat_stretch()
        idx = len(self._messages) - 1
        if idx > 0 and not self._thinking_just_removed:
            self._add_chat_gap(self._gap_before_message(idx))
        self._thinking_just_removed = False
        w = self._compute_message_widths()[idx]
        row, bubble = self._make_ai_row(
            self._messages[idx], cursor=True, max_width=w
        )
        self._chat_layout.addWidget(row)
        self._last_ai_row = row
        self._last_ai_bubble = bubble
        self._append_chat_stretch()

    def _remove_last_ai_row_incremental(self):
        if self._last_ai_row is not None:
            self._last_ai_row.setParent(None)
            self._last_ai_row.deleteLater()
        self._last_ai_row = None
        self._last_ai_bubble = None
        stretch_idx = self._chat_stretch_index()
        insert_at = stretch_idx if stretch_idx >= 0 else self._chat_layout.count()
        if insert_at > 0:
            item = self._chat_layout.itemAt(insert_at - 1)
            w = item.widget() if item is not None else None
            if w is not None and w.maximumHeight() <= AI_MSG_GAP_ROLE_SWITCH:
                self._chat_layout.takeAt(insert_at - 1)
                w.deleteLater()

    def _chat_viewport_width(self) -> int:
        try:
            return max(400, self._chat_scroll.viewport().width())
        except Exception:
            return 900

    def _message_wrap_max_width(self) -> int:
        """消息区宽度：随聊天视口变宽，全屏时不再固定 680px。"""
        vw = self._chat_viewport_width()
        left_m = max(0, AI_CHAT_PAD_LEFT - AI_REPLY_SHIFT_LEFT)
        right_m = AI_CHAT_PAD_RIGHT + AI_REPLY_SHIFT_LEFT
        usable = vw - left_m - right_m
        return max(
            AI_MSG_WRAP_MIN_PX,
            min(AI_MSG_WRAP_MAX_PX, usable),
        )

    @staticmethod
    def _ai_line_height_px(font_pt: float) -> int:
        return max(22, int(round(font_pt * AI_MSG_LINE_HEIGHT_RATIO)))

    def _ai_para_style(self, extra_bottom: int = 14) -> str:
        pal = self._ai_rich_palette()
        ff = AI_UI_FONT_FAMILY
        pt = AI_MSG_FONT_PT
        lh = self._ai_line_height_px(pt)
        return (
            f"margin:0 0 {extra_bottom}px 0; padding:0; font-family:{ff}; "
            f"font-size:{pt}pt; font-weight:400; color:{pal['text']}; "
            f"line-height:{lh}px; text-align:left;"
        )

    def _ai_heading_style(self, level: int) -> str:
        pal = self._ai_rich_palette()
        ff = AI_UI_FONT_FAMILY
        pt = AI_MSG_FONT_PT
        if level == 1:
            fs = pt + 7
            return (
                f"margin:4px 0 14px 0; padding:0; font-family:{ff}; font-size:{fs}pt; "
                f"font-weight:700; color:{pal['h1']}; line-height:{self._ai_line_height_px(fs)}px; "
                f"text-align:left;"
            )
        if level == 2:
            fs = pt + 4
            return (
                f"margin:14px 0 10px 0; padding:0; font-family:{ff}; font-size:{fs}pt; "
                f"font-weight:700; color:{pal['h2']}; line-height:{self._ai_line_height_px(fs)}px; "
                f"text-align:left;"
            )
        fs = pt + 2
        return (
            f"margin:10px 0 8px 0; padding:0; font-family:{ff}; font-size:{fs}pt; "
            f"font-weight:600; color:{pal['h3']}; line-height:{self._ai_line_height_px(fs)}px; "
            f"text-align:left;"
        )

    def _ai_spacer_style(self, height_px: int = 8) -> str:
        return f"margin:0; padding:{height_px}px 0 0 0; line-height:1px; font-size:1px;"

    def _ai_list_item_style(self) -> str:
        base = self._ai_para_style(8)
        return f"{base} margin-left:18px; padding-left:4px;"

    def _ai_quote_block_style(self) -> str:
        pal = self._ai_rich_palette()
        border = pal["quote_border"]
        bg = pal["quote_bg"]
        ff = AI_UI_FONT_FAMILY
        pt = AI_MSG_FONT_PT
        lh = self._ai_line_height_px(pt)
        return (
            f"margin:10px 0 14px 0; padding:10px 12px 10px 14px; "
            f"border-left:3px solid {border}; background-color:{bg}; "
            f"border-radius:0 8px 8px 0; font-family:{ff}; "
            f"font-size:{pt}pt; font-weight:400; color:{pal['muted']}; "
            f"line-height:{lh}px; text-align:left;"
        )

    def _ai_rich_palette(self) -> Dict[str, str]:
        if getattr(self, "_theme_light", False):
            return {
                "text": "#2b2b2f",
                "muted": "#5c5c66",
                "strong": "#0d0d0d",
                "h1": "#0d0d0d",
                "h2": "#1a1a1f",
                "h3": "#2a2a30",
                "quote_bg": "#f0f0f3",
                "quote_border": "#c8c8d0",
            }
        return {
            "text": "#d8d8de",
            "muted": "#a0a0ac",
            "strong": "#ffffff",
            "h1": "#ffffff",
            "h2": "#ececf2",
            "h3": "#d0d0da",
            "quote_bg": "#323238",
            "quote_border": "#5a5a66",
        }

    def _fmt_ai_inline_line(self, line: str) -> str:
        esc = self._escape_html_plain(sanitize_ai_display_text(line))
        inline_st = self._code_inline_style()
        esc = AI_CODE_INLINE_RE.sub(
            lambda m: f'<code style="{inline_st}">{m.group(1)}</code>', esc
        )
        pal = self._ai_rich_palette()
        esc = re.sub(
            r"\*\*(.+?)\*\*",
            lambda m: (
                f'<b><strong style="font-weight:700; color:{pal["strong"]};">'
                f"{m.group(1)}</strong></b>"
            ),
            esc,
        )
        esc = re.sub(
            r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
            lambda m: (
                f'<em style="font-style:italic; color:{pal["text"]};">'
                f"{m.group(1)}</em>"
            ),
            esc,
        )
        return esc

    def _format_ai_rich_segment_legacy(self, chunk: str) -> str:
        parts: List[str] = []
        buf: List[str] = []
        blank_run = 0

        def flush_buf(is_last: bool = False):
            if not buf:
                return
            merged = " ".join(s.strip() for s in buf if s.strip())
            merged = re.sub(r" +", " ", merged)
            if merged:
                bottom = 18 if is_last else 14
                parts.append(
                    f'<p style="{self._ai_para_style(bottom)}">'
                    f"{self._fmt_ai_inline_line(merged)}</p>"
                )
            buf.clear()

        for line in chunk.split("\n"):
            raw = line.rstrip()
            if not raw.strip():
                flush_buf()
                blank_run += 1
                if blank_run == 1:
                    parts.append(f'<p style="{self._ai_spacer_style(6)}">&nbsp;</p>')
                elif blank_run >= 2:
                    parts.append(f'<p style="{self._ai_spacer_style(12)}">&nbsp;</p>')
                    blank_run = 0
                continue
            blank_run = 0
            hm = re.match(r"^(#{1,3})\s+(.+)$", raw)
            if hm:
                flush_buf()
                level = len(hm.group(1))
                title = self._fmt_ai_inline_line(hm.group(2))
                tag = f"h{min(level, 3)}"
                parts.append(
                    f'<{tag} style="{self._ai_heading_style(level)}">{title}</{tag}>'
                )
                continue
            list_m = re.match(r"^[-*]\s+(.+)$", raw) or re.match(r"^\d+\.\s+(.+)$", raw)
            if list_m:
                flush_buf()
                item = self._fmt_ai_inline_line(list_m.group(1))
                bullet = "•" if raw.lstrip()[0] in "-*" else f"{raw.split('.', 1)[0]}."
                parts.append(
                    f'<p style="{self._ai_list_item_style()}">{bullet} {item}</p>'
                )
                continue
            if raw.startswith(">"):
                flush_buf()
                quote_text = self._fmt_ai_inline_line(raw[1:].lstrip())
                parts.append(
                    f'<p style="{self._ai_quote_block_style()}">{quote_text}</p>'
                )
                continue
            buf.append(raw)
        flush_buf(is_last=True)
        return "".join(parts)

    def _markdown_inner_html(self, text: str) -> str:
        """当前可见全文 → teamsx-md HTML（流式/换主题/完结共用）。"""
        light = getattr(self, "_theme_light", False)
        wrapped = AiMarkdownEngine.render_wrapped_html(text, light)
        if wrapped:
            return wrapped
        legacy = self._format_ai_rich_segment_legacy(text)
        return f'<div class="teamsx-md">{legacy}</div>' if legacy else ""

    def _build_ai_html(self, text: str, cursor: bool = False) -> str:
        pal = self._ai_rich_palette()
        inner = self._markdown_inner_html(text)
        if cursor and self._cursor_on:
            inner += (
                f'<span style="color:{pal["text"]}; font-size:14px;">▍</span>'
            )
        lh = self._ai_line_height_px(AI_MSG_FONT_PT)
        return (
            f'<div style="font-family:{AI_UI_FONT_FAMILY}; '
            f"font-size:{AI_MSG_FONT_PT}pt; line-height:{lh}px; "
            f'margin:0; padding:2px 0 4px 0; text-align:left;">{inner}</div>'
        )

    def _paint_ai_bubble(
        self,
        bubble: ChatBubbleTextEdit,
        text: str,
        inner_w: int,
        *,
        cursor: bool = False,
        stream: bool = False,
        force: bool = False,
    ) -> None:
        """统一绘制 AI 气泡：先套文档样式表，再 setHtml。"""
        self._apply_bubble_rich_defaults(bubble, mark_dirty=False)
        html = self._build_ai_html(text, cursor=cursor)
        if stream and not force and html == bubble._last_stream_render:
            return
        if inner_w != bubble._layout_max_width:
            bubble.set_layout_max_width(inner_w)
        bubble.set_stream_measure_text(text)
        if stream:
            if not bubble._rich_streaming:
                bubble.start_rich_stream(inner_w)
            elif inner_w != bubble._layout_max_width:
                bubble._lock_stream_width(inner_w)
            bubble.set_bubble_html(html, stream=True, force=force)
            return
        if bubble._rich_streaming or bubble._stream_layout_mode:
            bubble.stop_rich_stream(reflow=False)
        bubble.lock_layout_width(False, reflow=True)
        bubble.set_bubble_html(html, stream=False, force=force)

    def _thinking_dots_widget(self) -> Optional[AiThinkingDotsWidget]:
        if self._thinking_widget is None:
            return None
        return self._thinking_widget.findChild(AiThinkingDotsWidget)

    def _make_thinking_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        h = QHBoxLayout(row)
        h.setContentsMargins(*self._ai_content_side_margins())
        h.setSpacing(0)
        col = QVBoxLayout()
        col.setContentsMargins(self._ai_text_start_inset(), 0, 0, 0)
        col.setSpacing(0)
        col.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        dots = AiThinkingDotsWidget(self._theme_light)
        dots.begin_animation()
        col.addWidget(dots, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        h.addLayout(col, 0)
        h.addStretch(1)
        return row

    def _make_user_row(
        self, msg: dict, max_width: Optional[int] = None
    ) -> QWidget:
        text = msg.get("content") or ""
        outer = QWidget()
        outer.setStyleSheet("background: transparent;")
        outer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(
            AI_CHAT_PAD_LEFT, AI_ROW_V_MARGIN, AI_CHAT_PAD_RIGHT, 0
        )
        outer_layout.setSpacing(0)
        h = QHBoxLayout()
        h.setSpacing(0)
        h.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        bubble_w = max(
            AI_USER_BUBBLE_MIN_PX,
            min(
                max_width if max_width is not None else self._message_wrap_max_width(),
                AI_USER_BUBBLE_MAX_PX,
            ),
        )
        bubble = ChatBubbleTextEdit(
            bubble_w,
            content_pad=AI_USER_BUBBLE_CONTENT_PAD,
        )
        bubble.setFont(self._message_font())
        bubble.setStyleSheet(self._user_message_stylesheet())
        bubble.set_bubble_plain(text)
        col.addWidget(
            bubble, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        h.addLayout(col, 0)
        outer_layout.addLayout(h)
        return outer

    def _make_ai_row(
        self,
        msg: dict,
        cursor: bool = False,
        max_width: Optional[int] = None,
    ) -> Tuple[QWidget, ChatBubbleTextEdit]:
        text = msg.get("content") or ""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        h = QHBoxLayout(row)
        h.setContentsMargins(*self._ai_content_side_margins())
        h.setSpacing(0)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        card_w = max_width if max_width is not None else self._message_wrap_max_width()
        inner_w = max(AI_MSG_WRAP_MIN_PX, card_w - AI_AI_CARD_PAD * 2)
        bubble = ChatBubbleTextEdit(
            inner_w,
            content_pad=AI_MSG_CONTENT_PAD,
        )
        bubble.setFont(self._message_font())
        bubble.setStyleSheet(self._ai_message_stylesheet())
        self._apply_bubble_rich_defaults(bubble)
        bubble.set_layout_max_width(inner_w)
        if cursor:
            self._set_ai_bubble_html(
                bubble, text, cursor, layout_max_width=inner_w, stream=True
            )
        else:
            self._set_ai_bubble_html(
                bubble, text, cursor, layout_max_width=inner_w, stream=False
            )
        card = self._wrap_ai_message_card(bubble, card_w)
        col.addWidget(
            card, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        h.addLayout(col, 0)
        h.addStretch(1)
        return row, bubble

    @staticmethod
    def _strip_stream_cursor_html(html: str) -> str:
        return ChatBubbleTextEdit.strip_stream_cursor_html(html)

    def _set_ai_bubble_html(
        self,
        bubble: ChatBubbleTextEdit,
        text: str,
        cursor: bool = False,
        layout_max_width: Optional[int] = None,
        stream: bool = False,
        finalize: bool = False,
    ):
        if layout_max_width is None:
            layout_max_width = self._ai_bubble_inner_width()
        self._paint_ai_bubble(
            bubble,
            text,
            layout_max_width,
            cursor=cursor,
            stream=stream or finalize,
        )

    def _finalize_ai_bubble_in_place(
        self, bubble: ChatBubbleTextEdit, text: str, html: str
    ) -> None:
        """流式结束：优先就地删光标，禁止 setHtml/重排，消除完成瞬间闪烁。"""
        bubble.set_stream_measure_text(text)
        prev = bubble._last_stream_render
        stripped = self._strip_stream_cursor_html(prev) if prev else ""
        content_same = bool(prev) and (html == stripped or html == prev)
        if content_same:
            if html != prev and not bubble.remove_trailing_stream_cursor():
                bubble.set_bubble_html(html, stream=False, skip_reflow=True)
            else:
                bubble.remove_trailing_stream_cursor()
                bubble._last_stream_render = html
        elif html != prev:
            bubble.set_bubble_html(html, stream=False, skip_reflow=True)
        bubble.stop_rich_stream(reflow=False)
        bubble.apply_post_stream_layout()

    def _code_block_style(self) -> str:
        """代码块容器：无背景，颜色由 Pygments 类 + defaultStyleSheet 控制。"""
        return (
            f"font-family:{AI_CODE_FONT_FAMILY}; font-size:{AI_CODE_BLOCK_FONT_PX}; "
            "background:transparent; background-color:transparent; border:none; "
            "border-radius:0; padding:12px 0; margin:14px 0 16px 0; "
            "white-space:pre-wrap; display:block; max-width:100%; text-align:left;"
        )

    def _code_inline_style(self) -> str:
        if getattr(self, "_theme_light", False):
            fg = "#1a1a1a"
        else:
            fg = "#e8e8e8"
        return (
            f"font-family:{AI_CODE_FONT_FAMILY}; font-size:{AI_CODE_INLINE_FONT_PX}; "
            f"color:{fg}; background:transparent !important; background-color:transparent !important; "
            "border:none; padding:2px 4px; border-radius:4px;"
        )

    def _compute_message_widths(self) -> List[int]:
        """每条消息共用同一换行阈值宽度。"""
        wrap_w = self._message_wrap_max_width()
        return [wrap_w] * len(self._messages)

    def _refresh_chat_view(self, show_cursor: bool = False, scroll: bool = True):
        scroll_val, scroll_max, pin_bottom = self._chat_scroll_snapshot()
        if scroll:
            pin_bottom = True
        self._clear_chat_layout()
        msg_widths = self._compute_message_widths()

        for i, msg in enumerate(self._messages):
            if i > 0:
                prev_role = self._messages[i - 1]["role"]
                if prev_role != msg["role"]:
                    self._add_chat_gap(AI_MSG_GAP_ROLE_SWITCH)
                else:
                    self._add_chat_gap(AI_MSG_GAP_SAME)

            width = msg_widths[i]
            if msg["role"] == "user":
                self._last_user_max_width = width
                self._chat_layout.addWidget(
                    self._make_user_row(msg, max_width=width)
                )
                self._last_ai_bubble = None
                self._last_ai_row = None
            else:
                is_last_ai = (
                    show_cursor
                    and i == len(self._messages) - 1
                    and self._stream_active
                )
                row, bubble = self._make_ai_row(
                    msg, cursor=is_last_ai, max_width=width
                )
                self._chat_layout.addWidget(row)
                self._last_ai_bubble = bubble
                self._last_ai_row = row

        if self._thinking_visible:
            self._thinking_widget = self._make_thinking_row()
            self._chat_layout.addWidget(self._thinking_widget)
        self._append_chat_stretch()
        if pin_bottom:
            self._pin_scroll_bottom_once()
        else:
            self._restore_chat_scroll(scroll_val, scroll_max, False)

    def _ai_card_for_bubble(
        self, bubble: ChatBubbleTextEdit
    ) -> Optional[QFrame]:
        parent = bubble.parentWidget()
        if isinstance(parent, QFrame) and parent.objectName() == "aiMessageCard":
            return parent
        return None

    def _schedule_chat_relayout(self, *, streaming: bool = False) -> None:
        self._chat_resize_streaming = bool(streaming)
        self._chat_resize_timer.start(AI_STREAM_RESIZE_DEBOUNCE_MS)

    def _on_chat_resize_debounced(self) -> None:
        if not self._chat_layout_active or not self._messages:
            return
        self._relayout_chat_on_resize(
            streaming=bool(getattr(self, "_chat_resize_streaming", False))
        )

    def _relayout_chat_on_resize(self, *, streaming: bool = False) -> None:
        """窗口缩放：原地更新气泡宽度，避免整页重建导致位置横跳。"""
        self._sync_composer_width()
        if not self._messages:
            return
        scroll_val, scroll_max, pin_bottom = self._chat_scroll_snapshot()
        bubbles = self._collect_chat_bubbles_in_order()
        if len(bubbles) != len(self._messages):
            return

        wrap_w = self._message_wrap_max_width()
        inner_w = max(AI_MSG_WRAP_MIN_PX, wrap_w - AI_AI_CARD_PAD * 2)
        user_w = max(
            AI_USER_BUBBLE_MIN_PX,
            min(wrap_w, AI_USER_BUBBLE_MAX_PX),
        )
        bar = self._chat_scroll.verticalScrollBar()
        bar.blockSignals(True)
        self._chat_content.setUpdatesEnabled(False)
        try:
            for msg, bubble in zip(self._messages, bubbles):
                if msg["role"] == "user":
                    bubble.set_layout_max_width(user_w)
                    if not bubble._width_locked:
                        bubble._reflow()
                    continue
                card = self._ai_card_for_bubble(bubble)
                if card is not None:
                    card.setMaximumWidth(wrap_w)
                text = msg.get("content") or ""
                is_streaming = streaming and bubble is self._last_ai_bubble
                if is_streaming:
                    text = self._stream_visible or text
                else:
                    bubble._width_locked = False
                    bubble._stream_layout_mode = False
                    bubble._rich_streaming = False
                    bubble._ai_full_width = True
                    bubble.setMinimumWidth(0)
                self._paint_ai_bubble(
                    bubble,
                    text,
                    inner_w,
                    cursor=is_streaming and self._cursor_on,
                    stream=is_streaming,
                    force=True,
                )
        finally:
            self._chat_content.setUpdatesEnabled(True)
            bar.blockSignals(False)

        if pin_bottom:
            QTimer.singleShot(0, lambda: self._scroll_bottom(force=True))
        else:
            self._restore_chat_scroll(scroll_val, scroll_max, False)

    def _stream_ramp_params(self, backlog: int) -> Tuple[int, int]:
        """35% 前稍慢，35%-55% 加速，之后适中；积压大时再略提速。"""
        total = max(1, len(self._stream_target))
        ratio = min(1.0, len(self._stream_visible) / total)

        if ratio < AI_STREAM_RAMP_MID:
            return AI_STREAM_CHARS_SLOW, AI_STREAM_TICK_MS

        if ratio < AI_STREAM_RAMP_FAST:
            t = (ratio - AI_STREAM_RAMP_MID) / (AI_STREAM_RAMP_FAST - AI_STREAM_RAMP_MID)
            step = AI_STREAM_CHARS_SLOW + int((AI_STREAM_CHARS_FAST - AI_STREAM_CHARS_SLOW) * t)
            interval = int(AI_STREAM_TICK_MS - (AI_STREAM_TICK_MS - AI_STREAM_TICK_MS_FAST) * t)
            return max(1, step), max(40, interval)

        step = AI_STREAM_CHARS_FAST
        interval = AI_STREAM_TICK_MS_FAST
        if backlog > 80:
            step = min(8, step + backlog // 50)
            interval = max(28, interval - 4)
        return max(1, step), interval

    def _schedule_stream_scroll(self):
        if self._user_scrolled_up:
            return
        now = time.monotonic() * 1000.0
        if now - self._stream_last_scroll_ms < AI_STREAM_SCROLL_MIN_MS:
            return
        self._stream_last_scroll_ms = now
        QTimer.singleShot(0, lambda: self._scroll_bottom(force=True))

    def _ai_bubble_inner_width(self) -> int:
        wrap_w = self._message_wrap_max_width()
        return max(AI_MSG_WRAP_MIN_PX, wrap_w - AI_AI_CARD_PAD * 2)

    def _flush_stream_paint(
        self, show_cursor: bool = True, *, commit_buffer: bool = False
    ):
        del commit_buffer  # 全文渲染，不再需要增量缓冲区提交
        if not self._stream_active or self._last_ai_bubble is None:
            self._stream_paint_timer.stop()
            return
        bubble = self._last_ai_bubble
        prev_h = bubble.height()
        bubble.setUpdatesEnabled(False)
        try:
            self._paint_ai_bubble(
                bubble,
                self._stream_visible or "",
                self._ai_bubble_inner_width(),
                cursor=show_cursor and self._cursor_on,
                stream=True,
            )
        finally:
            bubble.setUpdatesEnabled(True)
        if not show_cursor:
            return
        new_h = bubble.height()
        if (
            new_h - getattr(self, "_stream_last_paint_height", 0)
            >= AI_STREAM_SCROLL_HEIGHT_DELTA
            or new_h > prev_h + AI_STREAM_HEIGHT_STEP
        ):
            self._stream_last_paint_height = new_h
            self._schedule_stream_scroll()

    def _request_stream_paint(self):
        if not self._stream_paint_timer.isActive():
            self._stream_paint_timer.start()

    def _stop_stream_paint(self):
        self._stream_paint_timer.stop()

    def _update_last_ai_bubble(self, text: str, show_cursor: bool = False):
        bubble = self._last_ai_bubble
        if bubble is None:
            return
        if self._stream_active and show_cursor:
            self._request_stream_paint()
        else:
            self._stop_stream_paint()
            bubble.stop_rich_stream()
            self._set_ai_bubble_html(
                bubble, text, show_cursor, layout_max_width=self._ai_bubble_inner_width()
            )
            self._scroll_bottom()

    def _append_user(self, text: str):
        self._activate_chat_layout()
        self._user_scrolled_up = False
        self._messages.append(
            {"role": "user", "content": text, "ts": datetime.now()}
        )
        if not self._chat_layout.count():
            self._refresh_chat_view(scroll=True)
        else:
            self._append_user_row_incremental(self._messages[-1])
        self._scroll_bottom(force=True)

    def _begin_ai_stream(self, show_thinking: bool = True):
        self._last_ai_bubble = None
        self._last_ai_row = None
        self._stream_target = ""
        self._stream_visible = ""
        self._stream_api_done = False
        self._stream_active = True
        self._cursor_on = True
        self._stream_tick_count = 0
        self._stream_scroll_h = 0
        self._thinking_visible = show_thinking
        self._waiting_first_chunk = show_thinking
        self._stream_timer.setInterval(AI_STREAM_TICK_MS)
        self._stream_timer.start()
        self._stop_stream_paint()
        self._cursor_blink_timer.stop()
        self._stream_last_scroll_ms = 0.0
        self._stream_last_paint_height = 0
        self._update_compose_button()
        if show_thinking and self._chat_layout_active:
            QTimer.singleShot(
                AI_THINKING_DEFER_MS, self._append_thinking_row_deferred
            )

    def _append_thinking_row_deferred(self):
        if not self._stream_active or not self._thinking_visible:
            return
        self._append_thinking_row_incremental()
        if not self._user_scrolled_up:
            self._scroll_bottom(force=True)

    def _ensure_assistant_message(self):
        if (
            self._messages
            and self._messages[-1]["role"] == "assistant"
        ):
            return
        self._last_ai_bubble = None
        self._last_ai_row = None
        self._messages.append(
            {"role": "assistant", "content": "", "ts": datetime.now()}
        )

    def _on_stream_chunk(self, piece: str):
        piece = sanitize_ai_display_text(piece)
        if not piece:
            return
        if self._waiting_first_chunk:
            self._waiting_first_chunk = False
            self._thinking_visible = False
            self._ensure_assistant_message()
            self._append_ai_stream_row_incremental()
        self._stream_target += piece
        if not self._stream_timer.isActive():
            self._stream_timer.setInterval(AI_STREAM_TICK_MS)
            self._stream_timer.start()

    def _stream_tick(self):
        if self._waiting_first_chunk:
            return
        if not self._messages or self._messages[-1]["role"] != "assistant":
            return
        backlog = len(self._stream_target) - len(self._stream_visible)
        if backlog > 0:
            step, interval = self._stream_ramp_params(backlog)
            self._stream_visible = self._stream_target[
                : len(self._stream_visible) + step
            ]
            self._messages[-1]["content"] = self._stream_visible
            self._stream_tick_count += 1
            self._stream_timer.setInterval(interval)
            self._request_stream_paint()
        elif self._stream_api_done:
            if self._stream_visible != self._stream_target:
                self._stream_visible = self._stream_target
                self._messages[-1]["content"] = self._stream_visible
            self._flush_stream_paint(show_cursor=False, commit_buffer=True)
            self._finish_stream()

    def _complete_ai_bubble_display(self, final: str) -> bool:
        """结束流式：只删光标、不重新渲染 HTML（避免完成瞬间颜色闪烁）。"""
        if not self._messages or self._messages[-1]["role"] != "assistant":
            return False
        bubble = self._last_ai_bubble
        if bubble is None:
            return False
        self._messages[-1]["content"] = final
        self._stop_stream_paint()
        bubble.remove_trailing_stream_cursor()
        if bubble._last_stream_render:
            bubble._last_stream_render = self._strip_stream_cursor_html(
                bubble._last_stream_render
            )
        bubble.stop_rich_stream(reflow=False)
        bubble.apply_post_stream_layout()
        return True

    def _pin_scroll_bottom_once(self, repeat: bool = True):
        if self._user_scrolled_up:
            return

        def pin():
            if self._user_scrolled_up:
                return
            self._scroll_bottom(force=True)

        QTimer.singleShot(0, pin)
        if repeat:
            for ms in (50, 120):
                QTimer.singleShot(ms, pin)

    def _finish_stream(self):
        if not self._stream_active:
            return
        self._stream_timer.stop()
        self._stop_stream_paint()
        self._cursor_blink_timer.stop()
        self._stream_active = False
        self._remove_thinking_widget()
        self._thinking_visible = False
        self._waiting_first_chunk = False
        final = sanitize_ai_display_text(
            (self._stream_target or self._stream_visible or "").strip()
        )
        self._stream_target = final
        self._stream_visible = final
        was_following = not self._user_scrolled_up
        if final:
            self._ensure_assistant_message()
            if self._messages and self._messages[-1]["role"] == "assistant":
                self._messages[-1]["content"] = final
            if self._last_ai_bubble is None:
                self._append_ai_stream_row_incremental()
            if not self._complete_ai_bubble_display(final):
                self._refresh_chat_view(
                    show_cursor=False, scroll=was_following
                )
        elif (
            self._messages
            and self._messages[-1]["role"] == "assistant"
            and not (self._messages[-1].get("content") or "").strip()
        ):
            self._remove_last_ai_row_incremental()
            self._messages.pop()
        if was_following and not self._user_scrolled_up:
            self._pin_scroll_bottom_once(repeat=False)
        user_text = self._pending_user
        if user_text and final:
            self._context.append(("user", user_text))
            self._context.append(("assistant", final))
        self._pending_user = ""
        self._set_busy(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_composer_width()
        if not self._chat_layout_active or not self._messages:
            return
        if not self.isVisible():
            return
        self._schedule_chat_relayout(streaming=self._stream_active)

    def _play_local_stream(self, text: str):
        """本地固定回复也走流式展示（与 API 流式同速）。"""
        self._set_busy(True)
        self._begin_ai_stream(show_thinking=False)
        self._ensure_assistant_message()
        self._append_ai_stream_row_incremental()
        self._stream_target = text
        self._stream_api_done = True
        if not self._user_scrolled_up:
            self._pin_scroll_bottom_once()

    def _append_ai(self, text: str):
        self._messages.append(
            {"role": "assistant", "content": text, "ts": datetime.now()}
        )
        self._refresh_chat_view()

    def _scroll_bottom(self, force: bool = False):
        if not force and self._user_scrolled_up:
            return
        if not self._chat_layout_active:
            return
        self._apply_chat_bottom_pad()
        bar = self._chat_scroll.verticalScrollBar()
        anchor = self._last_ai_row
        clearance = self._chat_bottom_clearance()
        if anchor is not None:
            self._chat_scroll.ensureWidgetVisible(anchor, 0, clearance)
        bar.setValue(bar.maximum())

    def _can_pause_output(self) -> bool:
        return self._busy and (
            self._stream_active
            or self._thinking_visible
            or self._waiting_first_chunk
        )

    def _update_compose_button(self):
        if self._can_pause_output():
            self._send_btn.setText("Ps")
            self._send_btn.setToolTip("暂停输出")
            self._send_btn.setEnabled(True)
        elif self._busy:
            self._send_btn.setText("Go")
            self._send_btn.setToolTip("发送 (Enter)")
            self._send_btn.setEnabled(False)
        else:
            self._send_btn.setText("Go")
            self._send_btn.setToolTip("发送 (Enter)")
            self._send_btn.setEnabled(True)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._input.setEnabled(not busy)
        self._update_compose_button()
        if not busy:
            QTimer.singleShot(0, self._focus_input)

    def _on_compose_button(self):
        if self._can_pause_output():
            self._pause_output()
            return
        self._send_message()

    def _pause_output(self):
        """暂停流式输出，保留已显示内容。"""
        if not self._can_pause_output():
            return
        self._ignore_ai_signals = True
        self._stream_paused = True
        self._client.cancel()
        self._stream_timer.stop()
        self._cursor_blink_timer.stop()
        self._remove_thinking_widget()
        self._thinking_visible = False
        self._waiting_first_chunk = False
        self._stream_api_done = True
        partial = (self._stream_visible or self._stream_target or "").strip()
        if partial:
            self._ensure_assistant_message()
            self._messages[-1]["content"] = partial
            if self._last_ai_bubble is None:
                self._append_ai_stream_row_incremental()
        elif (
            self._messages
            and self._messages[-1]["role"] == "assistant"
            and not (self._messages[-1].get("content") or "").strip()
        ):
            self._remove_last_ai_row_incremental()
            self._messages.pop()
        self._finish_stream()
        QTimer.singleShot(300, self._clear_pause_ignore)

    def _clear_pause_ignore(self):
        self._ignore_ai_signals = False
        self._stream_paused = False

    def _send_message(self):
        if self._busy:
            return
        text = (self._input.toPlainText() or "").strip()
        if not text:
            return
        self._input.clear()
        self._adjust_input_height()
        show_user = text
        if text != "NEWAPI" and (self._awaiting_new_api or not self._api_key):
            show_user = f"{text[:6]}…{text[-4:]}" if len(text) > 12 else "（API 密钥）"
        self._append_user(show_user if text != "NEWAPI" else "NEWAPI")

        if text == "NEWAPI":
            self._awaiting_new_api = True
            QTimer.singleShot(0, self._focus_input)
            return

        if self._awaiting_new_api or not self._api_key:
            if len(text) < 8:
                QTimer.singleShot(0, self._focus_input)
                return
            self._api_key = text
            AiConfigStore.save_api_key(text)
            self._awaiting_new_api = False
            self._context.clear()
            QTimer.singleShot(0, self._focus_input)
            return

        if self._is_identity_question(text):
            self._pending_user = text
            QTimer.singleShot(
                0, lambda: self._play_local_stream(AI_IDENTITY_REPLY)
            )
            return

        QTimer.singleShot(0, lambda: self._ask_deepseek(text))

    def _ask_deepseek(self, user_text: str):
        messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
        for role, content in self._context:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        self._set_busy(True)
        self._pending_user = user_text
        self._begin_ai_stream()
        self._client.chat(self._api_key, messages)

    def _on_stream_finished(self, content: str):
        if self._ignore_ai_signals:
            return
        content = sanitize_ai_display_text(content or "")
        if self._waiting_first_chunk:
            self._waiting_first_chunk = False
            self._thinking_visible = False
            self._remove_thinking_widget()
            self._ensure_assistant_message()
            if self._last_ai_bubble is None:
                self._append_ai_stream_row_incremental()
        self._stream_target = content
        self._stream_api_done = True
        if not self._stream_timer.isActive():
            self._stream_timer.setInterval(AI_STREAM_TICK_MS)
            self._stream_timer.start()
        self._stream_tick()

    def _on_ai_error(self, err: str):
        if self._ignore_ai_signals:
            return
        self._stream_timer.stop()
        self._cursor_blink_timer.stop()
        self._stream_active = False
        self._stream_api_done = True
        self._remove_thinking_widget()
        self._thinking_visible = False
        self._waiting_first_chunk = False
        if self._messages and self._messages[-1]["role"] == "assistant":
            if not (self._messages[-1].get("content") or "").strip():
                self._remove_last_ai_row_incremental()
                self._messages.pop()
        self._messages.append(
            {
                "role": "assistant",
                "content": f"请求失败：{err}",
                "ts": datetime.now(),
            }
        )
        self._refresh_chat_view(scroll=True)
        self._pending_user = ""
        self._set_busy(False)


# ==================== 主窗口类 ====================

def _query_system_free_memory_mb() -> int:
    """返回系统可用物理内存（MB），失败时 -1。"""
    if sys.platform != "win32":
        return -1
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return int(stat.ullAvailPhys // (1024 * 1024))
    except Exception:
        pass
    return -1


def _query_process_image_memory_mb(image_name: str) -> int:
    """按进程映像名汇总工作集内存（MB）。"""
    if sys.platform != "win32":
        return 0
    try:
        import subprocess

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=flags,
        )
        if proc.returncode != 0:
            return 0
        total_kb = 0
        needle = image_name.lower()
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line or needle not in line.lower():
                continue
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) < 5:
                continue
            mem = parts[4].replace(",", "").replace(" K", "").replace("K", "").strip()
            try:
                total_kb += int(mem)
            except ValueError:
                pass
        return int(total_kb // 1024)
    except Exception:
        return 0


def _query_teamsx_used_memory_mb() -> int:
    """TeamsX 占用内存：主进程 + WebView2 子进程（MB）。"""
    return _query_process_image_memory_mb("TeamsX.exe") + _query_process_image_memory_mb(
        "msedgewebview2.exe"
    )


def _query_webview2_process_stats() -> Tuple[int, int]:
    """返回 (msedgewebview2 进程数, 估算总工作集 MB)。供内存压力日志使用。"""
    if sys.platform != "win32":
        return 0, 0
    try:
        import subprocess

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq msedgewebview2.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=flags,
        )
        if proc.returncode != 0:
            return 0, 0
        count = 0
        total_kb = 0
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line or "msedgewebview2.exe" not in line.lower():
                continue
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) < 5:
                continue
            count += 1
            mem = parts[4].replace(",", "").replace(" K", "").replace("K", "").strip()
            try:
                total_kb += int(mem)
            except ValueError:
                pass
        return count, int(total_kb // 1024)
    except Exception:
        return 0, 0


def _clamp_float(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(val)))


def _adaptive_idle_sec_for_online(online: int) -> float:
    """账号越多，闲置门槛越短（10 号≈8min，25 号≈5min，40 号≈2min）。"""
    online = max(1, int(online))
    return _clamp_float(
        ADAPTIVE_RECYCLE_IDLE_BASE_SEC
        - (online - 10) * ADAPTIVE_RECYCLE_IDLE_PER_ACCOUNT_SEC,
        ADAPTIVE_RECYCLE_IDLE_MIN_SEC,
        ADAPTIVE_RECYCLE_IDLE_BASE_SEC,
    )


def _adaptive_target_high_mb(online: int) -> int:
    online = max(1, int(online))
    return int(
        ADAPTIVE_RECYCLE_TARGET_BASE_MB
        + online * ADAPTIVE_RECYCLE_TARGET_PER_ACCOUNT_MB
    )


def _memory_ctrl_prune_samples(
    samples: deque, *, now: float, window_sec: float
) -> None:
    cutoff = float(now) - float(window_sec)
    while samples and float(samples[0][0]) < cutoff:
        samples.popleft()


def _memory_ctrl_compute_trends(
    samples: deque, *, now: float, window_sec: float
) -> Tuple[float, float]:
    """返回 (free_trend_mb_per_min, used_trend_mb_per_min)；样本不足时 0,0。"""
    cutoff = float(now) - float(window_sec)
    window: List[Tuple[float, int, int, int, int]] = [
        s for s in samples if float(s[0]) >= cutoff
    ]
    if len(window) < int(MEMORY_CTRL_TREND_MIN_SAMPLES):
        return 0.0, 0.0
    t0, free0, used0, _, _ = window[0]
    t1, free1, used1, _, _ = window[-1]
    dt_min = max(0.05, (float(t1) - float(t0)) / 60.0)
    free_trend = (float(free1) - float(free0)) / dt_min
    used_trend = (float(used1) - float(used0)) / dt_min
    return free_trend, used_trend


def _query_process_working_set_mb(pid: int) -> int:
    if sys.platform != "win32" or pid <= 0:
        return 0
    try:
        import ctypes

        PROCESS_QUERY_INFORMATION = 0x0400
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION, False, int(pid)
        )
        if not handle:
            return 0
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(pmc), pmc.cb
            ):
                return int(pmc.WorkingSetSize // (1024 * 1024))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass
    return 0


def _query_widget_process_id(widget) -> int:
    if widget is None or sys.platform != "win32":
        return 0
    try:
        import ctypes

        hwnd = int(widget.winId())
        if hwnd <= 0:
            return 0
        pid = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(
            hwnd, ctypes.byref(pid)
        )
        return int(pid.value or 0)
    except Exception:
        return 0


class MainWindow(QMainWindow):
    """主窗口 - 优化版本"""
    _memoryStatsReady = pyqtSignal(int, int, int, int)

    def __init__(self):
        super().__init__()
        try:
            # 初始化组件
            self.db = Database()
            self.web_views: Dict[int, TeamsWebView] = {}
            self.suspended_webviews: Dict[int, TeamsWebView] = {}
            self._image_helper = ImageClipboardHelper(self)
            self.webview_pool = WebViewPool()
            self.badge_cache: SafeDict = SafeDict()
            self.current_account_id: Optional[int] = None
            self.check_timer: Optional[QTimer] = None
            self.memory_timer: Optional[QTimer] = None
            self._memory_guard_timer: Optional[QTimer] = None
            self._memory_light_timer: Optional[QTimer] = None
            self._memory_guard_debounce_timer: Optional[QTimer] = None
            self._notify_waker_timer: Optional[QTimer] = None
            self._waker_index: int = 0
            self._memory_pressure = False
            self._memory_emergency_active = False
            self._low_memory_since = 0.0
            self._last_emergency_trim_at = 0.0
            self._last_account_switch_at = 0.0
            self._adaptive_recycle_last_at = 0.0
            self._adaptive_recycle_next_interval_sec = float(
                ADAPTIVE_RECYCLE_DECISION_MIN_SEC
            )
            self._adaptive_recycle_last_free_mb = -1
            self._adaptive_recycle_pressure = "ok"
            self._adaptive_recycle_renderer_prev = -1
            self._adaptive_recycle_storm_until = 0.0
            self._adaptive_recycle_account_last: Dict[int, float] = {}
            self._adaptive_recycle_batch_pending = 0
            self._memory_ctrl_samples: deque = deque()
            self._memory_ctrl_state: Dict[str, object] = {}
            self._memory_ctrl_last_logged_level = "ok"
            self._memory_ctrl_last_recycle_effective = False
            self._memory_ctrl_last_recycle_ineffective = False
            self._memory_groom_active = False
            self._memory_groom_target_aid: Optional[int] = None
            self._memory_groom_restore_id: Optional[int] = None
            self._memory_groom_aggressive = False
            self._memory_groom_account_last: Dict[int, float] = {}
            self._memory_groom_rr_index = 0
            self._memory_groom_timer: Optional[QTimer] = None
            self._enforce_low_mem_last_at = 0.0
            self._oom_unload_since = 0.0
            self._memory_guard_last_free_mb = -1
            self._memory_guard_last_used_mb = 0
            self._memory_guard_running = False
            self._memory_guard_last_full_at = 0.0
            self._lifecycle_cur_id: Optional[int] = None
            self._memoryStatsReady.connect(self._on_memory_stats_ready)
            self.image_check_timer: Optional[QTimer] = None
            self.is_closing = False
            self._shutdown_started = False
            self._shutdown_finished = False
            self._round_mask_cache: Dict[Tuple[int, int, int], QBitmap] = {}
            self._corner_mask_cache: Dict[Tuple[int, int, int, int], QBitmap] = {}
            self._chrome_mask_timer: Optional[QTimer] = None
            self._cache_clean_running = False
            self._cache_clean_thread: Optional[QThread] = None
            self.check_queue = deque()
            self._current_group_id = 0
            self._all_accounts_cache: List[Tuple] = []
            self._window_drag_active = False
            self._sidebar_collapsed = False
            self._sidebar_last_width = SIDEBAR_DEFAULT_WIDTH
            self._resize_active = False
            self._fast_mask_key: Optional[Tuple[int, int, int, int]] = None
            self._resize_settle_timer: Optional[QTimer] = None
            self._sidebar_chrome_key: Optional[Tuple] = None
            self._live_layout_timer: Optional[QTimer] = None
            self._badge_pending: Dict[int, int] = {}
            self._badge_debounce_timers: Dict[int, QTimer] = {}
            self._badge_poll_index = 0
            self._notify_sound_global_last: float = 0.0
            self._notify_sound_suppress_until: float = 0.0
            self._notify_startup_arm_until: float = 0.0
            self._notify_baseline_locked: Set[int] = set()
            self._notify_last_unread: Dict[int, int] = {}
            self._notify_sound_fired_at_count: Dict[int, int] = {}
            self._msg_notify_dedup: Dict[Tuple[int, str], float] = {}
            self._api_notify_dedup: Dict[Tuple[int, str], float] = {}
            self._memory_tier_last_trim: Dict[int, float] = {}
            self._memory_guard_wv2_count: int = -1
            self._memory_guard_wv2_mb: int = 0
            self._msg_sound_last_at: float = 0.0
            self._msg_sound_last_by_account: Dict[int, float] = {}
            self._call_ring_loop_timer: Optional[QTimer] = None
            self._call_ring_active_aid: Optional[int] = None
            self._call_ring_started_at: float = 0.0
            self._call_ring_last: Dict[int, float] = {}
            self._call_end_pending: Dict[int, float] = {}
            self._call_sessions: Dict[int, dict] = {}
            self._call_dismiss_watcher: Optional[QFileSystemWatcher] = None
            self._notify_ring_timer: Optional[QTimer] = None
            self._notify_ring_pending = False
            self._notify_sound_ready = False
            self._notify_sound_play_pending = False
            self._notify_sound_dl_lock = threading.Lock()
            self._teams_notify_sound_path: Optional[str] = None
            self._teams_call_sound_path: Optional[str] = None
            self._notify_sound_player = None
            self._notify_sound_output = None
            self._call_sound_player = None
            self._call_sound_output = None
            self._call_sound_ready = False
            self._call_tray_icon: Optional[QSystemTrayIcon] = None
            self._app_tray_icon: Optional[QSystemTrayIcon] = None
            self._force_quit = False
            self._close_dialog_open = False
            self._close_dialog = None
            self._taskbar_badge = get_taskbar_badge_controller()
            self._lock_overlay: Optional[QWidget] = None
            self._lock_input: Optional[QLineEdit] = None
            self._lock_unload_queue: List[int] = []
            self._lock_teardown_active = False
            self._app_locked = False
            self._main_splitter: Optional[QSplitter] = None
            self._theme_light = True
            self._teams_recover_running = False
            self._teams_load_failures = 0
            self._last_teams_recover_at = 0.0

            self._switch_target_id: Optional[int] = None
            self._switch_debounce_timer: Optional[QTimer] = None
            self._trim_suspended_scheduled = False

            # 设置窗口
            self._native_frame = bool(USE_NATIVE_WINDOW_FRAME)
            if self._native_frame:
                # 原生窗口：保留系统样式以获得 DWM 动画/贴边/阴影，
                # 用 nativeEvent(WM_NCCALCSIZE) 隐藏可见边框，自绘标题栏。
                self.setWindowFlags(Qt.WindowType.Window)
            else:
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.Window
                    | Qt.WindowType.WindowMinimizeButtonHint
                )
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            QApplication.instance().installEventFilter(self)
            if self._native_frame:
                self.resize(1280, 800)
            else:
                outer_w = 1280 + 2 * WINDOW_SHADOW_MARGIN
                outer_h = 800 + 2 * WINDOW_SHADOW_MARGIN
                self.resize(outer_w, outer_h)
            self.setMinimumSize(900, 600)
            self._resize_cursor_active = False
            self._active_resize_edges = None
            self.setMouseTracking(True)

            # 设置 UI
            self.setup_ui()
            self.apply_theme(True)

            # 设置窗口标题
            self.setWindowTitle("TeamsX")
            base_icon = AppPaths.app_qicon()
            if not base_icon.isNull():
                self.setWindowIcon(base_icon)
                QApplication.instance().setWindowIcon(base_icon)

            # 初始化
            self.load_accounts()
            self._reload_group_list()

            self._prepare_notify_sound_startup()
            QTimer.singleShot(
                int(NOTIFY_STARTUP_ARM_SEC * 1000), self._finish_notify_startup_arm
            )
            # 延后启动后台轮询，避免与首屏 WebView 初始化争抢主线程
            QTimer.singleShot(1200, self.start_notification_check)
            QTimer.singleShot(1800, self.start_memory_cleanup)
            QTimer.singleShot(2200, self.start_memory_guard)
            QTimer.singleShot(2400, self.start_daily_cache_cleanup)
            self._setup_call_dismiss_watcher()
            self._setup_app_tray()

            print(
                f"TeamsX 启动完成 · 数据: {AppPaths.data_root()} · "
                f"在线账号: 不限制 · "
                f"WebView2: {'共享Profile' if os.environ.get('TEAMSX_MULTI_PROFILE','1') not in ('0','false','no','off') else '独立进程'}"
            )
        except Exception as e:
            print(f"主窗口初始化失败: {e}")
            QMessageBox.critical(None, "初始化失败", f"程序初始化失败: {str(e)}")
            sys.exit(1)

    def apply_theme(self, light: bool):
        """切换深/浅主题（无提示）"""
        global CURRENT_THEME
        self._theme_light = light
        CURRENT_THEME = "light" if light else "dark"
        self.setStyleSheet(APP_LIGHT_STYLE if light else APP_DARK_STYLE)
        self._apply_window_shadow_theme(light)
        if hasattr(self, "account_list"):
            self.account_list.viewport().update()
        self._apply_sidebar_chrome_theme(light)
        self._sync_window_chrome()
        self._style_lock_overlay()

    def toggle_theme(self):
        self.apply_theme(not self._theme_light)

    def _apply_sidebar_chrome_theme(self, light: bool):
        if light:
            header = "font-size: 14px; font-weight: bold; color: #1a1a1a;"
            group_lbl = "font-size: 13px; font-weight: 600; color: #1a1a1a; padding-right: 2px;"
            status = "color: #0078d4; font-size: 11px; font-weight: bold; padding-left: 2px;"
            bottom = "background-color: #f0f0f0; border-top: 1px solid #e0e0e0;"
            sidebar_bg = "#f6f6f6"
        else:
            sidebar_bg = ""
            header = "font-size: 14px; font-weight: bold; color: #e0e0e0;"
            group_lbl = "font-size: 13px; font-weight: 600; color: #e0e0e0; padding-right: 2px;"
            status = "color: #00d4ff; font-size: 11px; font-weight: bold; padding-left: 2px;"
            bottom = "background-color: #252525; border-top: 1px solid #3c3c3c;"
        if hasattr(self, "_header_title_label"):
            self._header_title_label.setStyleSheet(header)
        if hasattr(self, "_group_label"):
            self._group_label.setStyleSheet(group_lbl)
        if hasattr(self, "status_label"):
            self.status_label.setStyleSheet(status)
        if hasattr(self, "mem_status_label"):
            self._mem_hint_color = ""
            self._refresh_memory_hint()
        if hasattr(self, "_bottom_bar"):
            self._bottom_bar.setStyleSheet(bottom)
        if hasattr(self, "tools_btn"):
            self.tools_btn.set_theme_light(light)
        if hasattr(self, "_flyout_buttons"):
            cs = self._flyout_btn_style(light)
            for _b in self._flyout_buttons:
                _b.setStyleSheet(cs)
        if hasattr(self, "_left_panel") and light:
            self._left_panel.setStyleSheet(
                f"background-color: {sidebar_bg};"
            )
        elif hasattr(self, "_left_panel"):
            self._left_panel.setStyleSheet("")
        strip = getattr(self, "_sidebar_expand_strip", None)
        if strip is not None:
            if light:
                strip.setStyleSheet(
                    "QPushButton#sidebarExpandStrip {"
                    " background-color: #e8e8e8; color: #555; border: none;"
                    " border-right: 1px solid #ccc; font-size: 16px; padding: 0;"
                    "}"
                    "QPushButton#sidebarExpandStrip:hover { background-color: #dcdcdc; }"
                )
            else:
                strip.setStyleSheet(
                    "QPushButton#sidebarExpandStrip {"
                    " background-color: #2a2a2a; color: #aaa; border: none;"
                    " border-right: 1px solid #444; font-size: 16px; padding: 0;"
                    "}"
                    "QPushButton#sidebarExpandStrip:hover { background-color: #353535; }"
                )
        self._sync_webview_edge_inset(light)
        if hasattr(self, "ai_chat_panel"):
            self.ai_chat_panel.apply_theme(light)
        if hasattr(self, "group_manage_panel"):
            self.group_manage_panel.apply_panel_theme(light)

    def _apply_window_shadow_theme(self, light: bool):
        self._shadow_color = QColor(0, 0, 0, 34 if light else 60)
        self._sync_window_chrome()

    def _is_window_expanded(self) -> bool:
        maximized = bool(self.windowState() & Qt.WindowState.WindowMaximized)
        expanded = bool(
            getattr(self, "title_bar", None) is not None
            and getattr(self.title_bar, "_expanded", False)
        )
        return maximized or expanded or self.isFullScreen()

    def _build_round_bitmap(self, w: int, h: int, radius: int) -> QBitmap:
        """4 倍超采样渲染圆角后缩小，得到更顺滑的 1 位遮罩（减少原生窗口区域的台阶/斜切感）。"""
        s = 4
        img = QImage(w * s, h * s, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w * s, h * s, radius * s, radius * s)
        p.end()
        small = img.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QBitmap.fromImage(small.createAlphaMask())

    def _build_corner_mask(
        self, w: int, h: int, radius: int, inset: int
    ) -> QBitmap:
        """网页区遮罩：右/底各内缩 inset，仅右下角按 radius 圆角；其余直角。
        圆心与窗口圆角重合，形成均匀的内缩边线（含转角）。"""
        s = 4
        img = QImage(w * s, h * s, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)

        rw = (w - inset) * s
        rh = (h - inset) * s
        r = max(0, radius) * s
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(rw, 0)
        path.lineTo(rw, rh - r)
        path.arcTo(QRectF(rw - 2 * r, rh - 2 * r, 2 * r, 2 * r), 0.0, -90.0)
        path.lineTo(0, rh)
        path.closeSubpath()
        p.fillPath(path, QColor(255, 255, 255))
        p.end()

        small = img.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QBitmap.fromImage(small.createAlphaMask())

    def _cached_round_bitmap(self, w: int, h: int, radius: int) -> QBitmap:
        key = (w, h, radius)
        cached = self._round_mask_cache.get(key)
        if cached is not None:
            return cached
        bmp = self._build_round_bitmap(w, h, radius)
        if len(self._round_mask_cache) > 6:
            self._round_mask_cache.clear()
        self._round_mask_cache[key] = bmp
        return bmp

    def _cached_corner_mask(
        self, w: int, h: int, radius: int, inset: int
    ) -> QBitmap:
        key = (w, h, radius, inset)
        cached = self._corner_mask_cache.get(key)
        if cached is not None:
            return cached
        bmp = self._build_corner_mask(w, h, radius, inset)
        if len(self._corner_mask_cache) > 6:
            self._corner_mask_cache.clear()
        self._corner_mask_cache[key] = bmp
        return bmp

    @staticmethod
    def _build_round_region(w: int, h: int, radius: int) -> QRegion:
        """轻量圆角区域：用矩形 + 四角椭圆组合，构建极快，可缩放时每帧调用。"""
        r = max(0, min(radius, w // 2, h // 2))
        if r <= 0:
            return QRegion(0, 0, w, h)
        region = QRegion(r, 0, w - 2 * r, h)
        region = region.united(QRegion(0, r, w, h - 2 * r))
        d = 2 * r
        region = region.united(
            QRegion(0, 0, d, d, QRegion.RegionType.Ellipse)
        )
        region = region.united(
            QRegion(w - d, 0, d, d, QRegion.RegionType.Ellipse)
        )
        region = region.united(
            QRegion(0, h - d, d, d, QRegion.RegionType.Ellipse)
        )
        region = region.united(
            QRegion(w - d, h - d, d, d, QRegion.RegionType.Ellipse)
        )
        return region

    @staticmethod
    def _build_fast_corner_region(
        w: int, h: int, radius: int, inset: int
    ) -> QRegion:
        """网页区轻量圆角区域（右/底内缩 + 右下圆角），缩放跟手用。"""
        rw = max(0, w - inset)
        rh = max(0, h - inset)
        if rw <= 0 or rh <= 0:
            return QRegion(0, 0, max(1, w), max(1, h))
        r = max(0, min(radius, rw // 2, rh // 2))
        region = QRegion(0, 0, rw, max(1, rh - r))
        region = region.united(QRegion(0, 0, max(1, rw - r), rh))
        if r > 0:
            region = region.united(
                QRegion(rw - 2 * r, rh - 2 * r, 2 * r, 2 * r, QRegion.RegionType.Ellipse)
            )
        return region

    def _build_round_bitmap_fast(self, w: int, h: int, radius: int) -> QBitmap:
        """缩放跟手用 1× 圆角遮罩（比 QRegion 拼接更完整，无透明缝隙）。"""
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, radius, radius)
        p.end()
        return QBitmap.fromImage(img.createAlphaMask())

    def _apply_fast_chrome_masks(self) -> None:
        """缩放跟手：主框 1× 圆角遮罩每帧同步；网页区暂不裁角，避免露底透明。"""
        if getattr(self, "_native_frame", False):
            return
        if self._is_window_expanded():
            frame = getattr(self, "_main_frame", None)
            shell = getattr(self, "_right_shell", None)
            try:
                if frame is not None:
                    frame.clearMask()
                if shell is not None:
                    shell.clearMask()
            except Exception:
                pass
            return
        frame = getattr(self, "_main_frame", None)
        shell = getattr(self, "_right_shell", None)
        if frame is None:
            return
        fw, fh = frame.width(), frame.height()
        if fw <= 2 or fh <= 2:
            return
        sw = shell.width() if shell is not None else 0
        sh = shell.height() if shell is not None else 0
        key = (fw, fh, sw, sh)
        if key == getattr(self, "_fast_mask_key", None):
            return
        self._fast_mask_key = key
        try:
            frame.setMask(
                self._build_round_bitmap_fast(fw, fh, WINDOW_FRAME_RADIUS)
            )
            if shell is not None and sw > 4 and sh > 4:
                shell.clearMask()
        except Exception:
            pass

    def _apply_chrome_masks(self) -> None:
        if getattr(self, "_native_frame", False):
            return
        self._apply_round_mask()
        self._apply_right_shell_mask()

    def _schedule_chrome_masks(self, delay_ms: int = 80) -> None:
        if delay_ms <= 0:
            timer = getattr(self, "_chrome_mask_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
            self._apply_chrome_masks()
            return
        timer = self._chrome_mask_timer
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._apply_chrome_masks)
            self._chrome_mask_timer = timer
        timer.start(delay_ms)

    def _apply_right_shell_mask(self):
        """裁网页区右下角，使转角也有与右/底一致的内缩边线。"""
        shell = getattr(self, "_right_shell", None)
        if shell is None:
            return
        w, h = shell.width(), shell.height()
        if w <= 4 or h <= 4:
            return
        if self._is_window_expanded():
            shell.clearMask()
            return
        inset = TEAMS_WEBVIEW_EDGE_INSET
        radius = max(0, WINDOW_FRAME_RADIUS - inset)
        shell.setMask(self._cached_corner_mask(w, h, radius, inset))

    def _apply_round_mask(self):
        """用超采样位图遮罩裁出圆角；_main_frame 为原生窗口，区域可裁剪原生 WebView2 子窗口。"""
        frame = getattr(self, "_main_frame", None)
        if frame is None:
            return
        w, h = frame.width(), frame.height()
        if w <= 2 or h <= 2:
            return
        if self._is_window_expanded():
            frame.clearMask()
            return
        frame.setMask(self._cached_round_bitmap(w, h, WINDOW_FRAME_RADIUS))

    def _sync_webview_edge_inset(self, light: Optional[bool] = None) -> None:
        """网页区右/底统一内缩边线（含右下圆角）；深浅主题尺寸相同，仅底色随主题。"""
        shell = getattr(self, "_right_shell", None)
        if shell is None:
            return
        lay = shell.layout()
        if lay is None:
            return
        if light is None:
            light = getattr(self, "_theme_light", True)
        shell.setStyleSheet(
            "background-color: #f3f3f3;" if light else "background-color: #1e1e1e;"
        )
        self._schedule_chrome_masks(0)

    def _sync_window_chrome(self):
        lay = getattr(self, "_shadow_outer_layout", None)
        if lay is None:
            return
        if getattr(self, "_native_frame", False):
            # 原生窗口：阴影/圆角由系统 DWM 提供，无需自绘留白与遮罩。
            lay.setContentsMargins(0, 0, 0, 0)
            wrapper = getattr(self, "_shadow_outer", None)
            if wrapper is not None:
                wrapper.configure(0, False, getattr(self, "_shadow_color", QColor(0, 0, 0, 40)))
            if hasattr(self, "title_bar"):
                self.title_bar.apply_bar_theme(getattr(self, "_theme_light", True))
            self._sync_webview_edge_inset()
            self._normalize_main_splitter_sizes(0)
            return
        expanded = self._is_window_expanded()
        margin = 0 if expanded else WINDOW_SHADOW_MARGIN
        lay.setContentsMargins(margin, margin, margin, margin)
        wrapper = getattr(self, "_shadow_outer", None)
        if wrapper is not None:
            wrapper.configure(
                margin,
                not expanded,
                getattr(self, "_shadow_color", QColor(0, 0, 0, 40)),
            )
        if hasattr(self, "title_bar"):
            self.title_bar.apply_bar_theme(getattr(self, "_theme_light", True))
        self._sync_webview_edge_inset()
        self._schedule_chrome_masks(0)
        self._normalize_main_splitter_sizes(0)

    # 兼容旧调用名
    def _sync_window_shadow_layout(self):
        self._sync_window_chrome()

    def setup_ui(self):
        """设置 UI"""
        wrapper = ShadowContainer(WINDOW_SHADOW_MARGIN, WINDOW_FRAME_RADIUS)
        wrapper.setObjectName("shadowOuter")
        wrapper.setMouseTracking(True)
        self._shadow_outer = wrapper
        self._shadow_color = QColor(0, 0, 0, 34)
        self.setCentralWidget(wrapper)
        self._shadow_outer_layout = QVBoxLayout(wrapper)
        # 原生边框：系统负责阴影/圆角，客户区从首帧起就铺满，避免透明留白外露成黑边。
        _init_margin = 0 if getattr(self, "_native_frame", False) else WINDOW_SHADOW_MARGIN
        self._shadow_outer_layout.setContentsMargins(
            _init_margin, _init_margin, _init_margin, _init_margin,
        )
        self._shadow_outer_layout.setSpacing(0)

        self._main_frame = QFrame()
        self._main_frame.setObjectName("mainFrame")
        self._main_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._main_frame.setAutoFillBackground(True)
        self._main_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._shadow_outer_layout.addWidget(self._main_frame)

        main_v_layout = QVBoxLayout(self._main_frame)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)

        # 标题栏
        self.title_bar = CustomTitleBar(self)
        self.title_bar.title_label.clicked.connect(self.toggle_theme)
        self.title_bar._normal_size = (self.width(), self.height())
        main_v_layout.addWidget(self.title_bar)

        # 主分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧面板
        left_panel = QWidget()
        self._left_panel = left_panel
        left_panel.setMinimumWidth(0)
        left_panel.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(6)

        self._header_title_label = QLabel("账号列表")
        self._header_title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        header_layout.addWidget(self._header_title_label)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(
            "color: #00d4ff; font-size: 11px; font-weight: bold; padding-left: 2px;"
        )
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        header_layout.addWidget(self.status_label, 1)

        # 锁定按钮（与「管理」按钮同尺寸）
        self.lock_btn = QPushButton("锁定")
        self.lock_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lock_btn.setFixedSize(SIDEBAR_SMALL_BTN_W, SIDEBAR_SMALL_BTN_H)
        self.lock_btn.clicked.connect(self.on_lock_clicked)
        header_layout.addWidget(self.lock_btn)

        left_layout.addLayout(header_layout)

        group_row = QHBoxLayout()
        # 右侧与 header_layout(8px) 对齐，便于与「锁定」同列
        group_row.setContentsMargins(10, 0, 8, 4)
        group_row.setSpacing(8)
        self._group_label = QLabel("分组")
        self._group_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #e0e0e0; padding-right: 2px;")
        group_row.addWidget(self._group_label)

        self.group_combo = GroupFilterComboBox()
        self.group_combo.setFixedHeight(SIDEBAR_SMALL_BTN_H + 2)
        self.group_combo.setFixedWidth(118)
        self.group_combo.currentIndexChanged.connect(self._on_group_combo_changed)
        group_row.addWidget(self.group_combo)

        group_row.addSpacing(4)
        self.group_manage_btn = QPushButton("管理")
        self.group_manage_btn.setFixedSize(SIDEBAR_SMALL_BTN_W, SIDEBAR_SMALL_BTN_H)
        self.group_manage_btn.clicked.connect(self.manage_groups)
        group_row.addWidget(self.group_manage_btn)

        left_layout.addLayout(group_row)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索备注…")
        self.search_edit.setStyleSheet("margin: 4px 10px;")
        self.search_edit.textChanged.connect(self._refresh_account_list_display)
        left_layout.addWidget(self.search_edit)

        self.account_list = AccountListWidget()
        self.account_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.account_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.account_list.setItemDelegate(AccountListDelegate(self.account_list))
        self.account_list.itemClicked.connect(self.on_account_clicked)
        self.account_list.itemDoubleClicked.connect(self.on_account_clicked)
        self.account_list.orderChanged.connect(self._on_account_list_reordered)
        self.account_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.account_list.customContextMenuRequested.connect(self.show_context_menu)

        self.group_manage_panel = GroupManagePanel(self.db, None)
        self.group_manage_panel.closed.connect(self._on_group_manage_panel_closed)
        self.group_manage_panel.apply_panel_theme(getattr(self, "_theme_light", False))
        self._sidebar_content_host = SidebarContentHost(
            self.account_list, self.group_manage_panel
        )
        left_layout.addWidget(self._sidebar_content_host, 1)
        self._sidebar_view_anim: Optional[QParallelAnimationGroup] = None
        self._sidebar_view_anim_running = False

        # 底部工具栏
        self._bottom_bar = QWidget()
        self._bottom_bar.setStyleSheet("background-color: #252525; border-top: 1px solid #3c3c3c;")
        bottom_layout = QHBoxLayout(self._bottom_bar)
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        bottom_layout.setSpacing(10)

        # 齿轮工具：点击向右依次弹出 导入/添加/刷新/通知，再点收起
        self.tools_btn = GearMenuButton()
        self.tools_btn.set_theme_light(getattr(self, "_theme_light", True))
        self.tools_btn.clicked.connect(self._toggle_tools_flyout)
        bottom_layout.addWidget(self.tools_btn)

        # 内存/进程提示紧跟齿轮（齿轮展开时隐藏，避免与弹出按钮重叠）
        # minimumWidth(0) + Preferred：文字再长也只在剩余空间内显示，不撑宽账号列表
        self.mem_status_label = QLabel("")
        self.mem_status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.mem_status_label.setMinimumWidth(0)
        # Ignored 宽度策略：文字再长也不撑宽账号列表，可压缩到 0
        self.mem_status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.mem_status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._mem_hint_color = ""
        # 标签 stretch=1 吃下剩余空间显示文字；尾部弹簧 stretch=0 仅在标签隐藏时
        # 顶住齿轮在最左，避免齿轮跑到中间
        bottom_layout.addWidget(self.mem_status_label, 1)
        bottom_layout.addStretch(0)
        # 齿轮始终置于最上层，避免被相邻标签遮挡而“消失”
        self.tools_btn.raise_()

        # 弹出选项（手动定位，不进布局；初始隐藏）
        self.import_btn = QPushButton("导入", self._bottom_bar)
        self.import_btn.clicked.connect(self.import_accounts)
        self.add_btn = QPushButton("添加", self._bottom_bar)
        self.add_btn.clicked.connect(self.add_account)
        self.refresh_btn = QPushButton("刷新", self._bottom_bar)
        self.refresh_btn.clicked.connect(self.refresh_current_view)
        # 通知开关：从弹出条移除，改由托盘右键控制；保留隐藏按钮承载开关状态。
        self.notification_toggle = QPushButton("通知", self._bottom_bar)
        self.notification_toggle.setCheckable(True)
        self.notification_toggle.setChecked(True)
        self.notification_toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.notification_toggle.hide()

        self._flyout_buttons = [
            self.import_btn, self.add_btn, self.refresh_btn
        ]
        self._flyout_btn_h = 30
        compact_style = self._flyout_btn_style(getattr(self, "_theme_light", True))
        for b in self._flyout_buttons:
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setStyleSheet(compact_style)
            b.hide()
        self._tools_expanded = False
        self._tools_anim = None
        self._tools_auto_collapse_timer = QTimer(self)
        self._tools_auto_collapse_timer.setSingleShot(True)
        self._tools_auto_collapse_timer.timeout.connect(self._auto_collapse_tools)

        left_layout.addWidget(self._bottom_bar)

        self._right_shell = QWidget()
        self._right_shell.setObjectName("rightShell")
        self._right_shell.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._right_shell.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_shell_layout = QVBoxLayout(self._right_shell)
        right_shell_layout.setContentsMargins(0, 0, 0, 0)
        right_shell_layout.setSpacing(0)

        self.stack_widget = QStackedWidget()
        self.stack_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ai_chat_panel = AiChatPanel()
        self.stack_widget.addWidget(self.ai_chat_panel)
        right_shell_layout.addWidget(self.stack_widget)

        self._main_splitter = main_splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self._right_shell)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setCollapsible(0, True)
        main_splitter.setCollapsible(1, False)
        main_splitter.setSizes([270, 1010])
        main_splitter.setHandleWidth(1)
        main_splitter.splitterMoved.connect(self._on_main_splitter_moved)

        # 标题栏以下区域：锁定遮罩只盖住这里，不碰 CustomTitleBar
        self._body_host = QWidget(self._main_frame)
        body_layout = QVBoxLayout(self._body_host)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(main_splitter)

        main_v_layout.addWidget(self._body_host, 1)

        self._sidebar_expand_strip = QPushButton("›", self._body_host)
        self._sidebar_expand_strip.setObjectName("sidebarExpandStrip")
        self._sidebar_expand_strip.setFixedWidth(SIDEBAR_EXPAND_STRIP_W)
        self._sidebar_expand_strip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._sidebar_expand_strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_expand_strip.setToolTip("展开账号列表")
        self._sidebar_expand_strip.clicked.connect(self._expand_sidebar)
        self._sidebar_expand_strip.hide()

        # 独立隐藏窗口承载后台 WebView，与主界面完全分离，避免切换账号时 AI 页跟着闪
        self._webview_park = QWidget(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint,
        )
        self._webview_park.setGeometry(-32000, -32000, 800, 600)
        self._webview_park_layout = QVBoxLayout(self._webview_park)
        self._webview_park.show()
        self._webview_park_layout.setContentsMargins(0, 0, 0, 0)
        self.go_home()
        self._ensure_lock_overlay_widgets()
        if self._lock_overlay is not None:
            self._lock_overlay.hide()

    def _is_sidebar_collapsed(self) -> bool:
        return bool(getattr(self, "_sidebar_collapsed", False))

    def _expand_sidebar(self) -> None:
        sp = getattr(self, "_main_splitter", None)
        if sp is None or not sp.isVisible():
            return
        total = sp.width()
        if total <= 0:
            return
        w = int(getattr(self, "_sidebar_last_width", SIDEBAR_DEFAULT_WIDTH) or SIDEBAR_DEFAULT_WIDTH)
        w = max(SIDEBAR_EXPAND_AT, min(w, max(SIDEBAR_EXPAND_AT, total // 2)))
        self._sidebar_collapsed = False
        sp.setSizes([w, max(1, total - w)])
        self._sync_sidebar_chrome()
        self._schedule_resize_settle(80)

    def _sync_sidebar_chrome(self) -> None:
        sp = getattr(self, "_main_splitter", None)
        strip = getattr(self, "_sidebar_expand_strip", None)
        host = getattr(self, "_body_host", None)
        if strip is None or host is None:
            return
        collapsed = self._is_sidebar_collapsed()
        locked = getattr(self, "_app_locked", False)
        host_h = host.height() if collapsed and not locked else 0
        key = (collapsed, locked, host_h)
        if key == getattr(self, "_sidebar_chrome_key", None):
            return
        self._sidebar_chrome_key = key
        if sp is not None:
            sp.setHandleWidth(SIDEBAR_EXPAND_STRIP_W if collapsed else 1)
        if collapsed and not locked and sp is not None and sp.isVisible():
            strip.setGeometry(0, 0, SIDEBAR_EXPAND_STRIP_W, host.height())
            strip.raise_()
            strip.show()
        else:
            strip.hide()

    def _on_main_splitter_moved(self, _pos: int = 0, _index: int = 0) -> None:
        sp = getattr(self, "_main_splitter", None)
        if sp is not None:
            left = sp.sizes()[0] if sp.sizes() else 0
            if left > SIDEBAR_COLLAPSE_AT + 16:
                self._sidebar_last_width = left
            if left >= SIDEBAR_EXPAND_AT:
                self._sidebar_collapsed = False
                self._sync_sidebar_chrome()
        self._begin_resize_session()
        self._apply_fast_chrome_masks()
        self._schedule_resize_settle(140)

    def _begin_resize_session(self) -> None:
        if getattr(self, "_resize_active", False):
            return
        self._resize_active = True
        so = getattr(self, "_shadow_outer", None)
        if so is not None:
            try:
                so.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
            except Exception:
                pass

    def _end_resize_session(self) -> None:
        if not getattr(self, "_resize_active", False):
            return
        self._resize_active = False
        so = getattr(self, "_shadow_outer", None)
        if so is not None:
            try:
                so.setAttribute(Qt.WidgetAttribute.WA_StaticContents, False)
                so.update()
            except Exception:
                pass

    def _schedule_resize_settle(self, delay_ms: int = 160) -> None:
        timer = getattr(self, "_resize_settle_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_resize_settled)
            self._resize_settle_timer = timer
        timer.start(max(80, int(delay_ms)))

    def _on_resize_settled(self) -> None:
        self._end_resize_session()
        self._fast_mask_key = None
        try:
            tb = getattr(self, "title_bar", None)
            if tb is not None and not getattr(tb, "_expanded", False):
                tb._normal_size = (self.width(), self.height())
        except Exception:
            pass
        self._normalize_main_splitter_sizes()
        self._sync_sidebar_chrome()
        self._schedule_chrome_masks(0)
        self._on_live_layout_sync()
        self._sync_ai_panel_layout()

    def _normalize_main_splitter_sizes(self, delay_ms: int = 0) -> None:
        """收起左侧账号栏后把剩余宽度给 Teams；带滞后阈值，便于再次拖出。"""
        def _run() -> None:
            sp = getattr(self, "_main_splitter", None)
            if sp is None or not sp.isVisible() or sp.count() < 2:
                return
            total = sp.width()
            if total <= 0:
                return
            sizes = sp.sizes()
            left = sizes[0] if sizes else 0
            right = sizes[1] if len(sizes) > 1 else 0
            left_w = sp.widget(0)
            if left_w is not None and not left_w.isVisible():
                self._sidebar_collapsed = True
                if left != 0 or right != total:
                    sp.setSizes([0, total])
                self._sync_sidebar_chrome()
                return
            if self._is_sidebar_collapsed():
                if left < SIDEBAR_EXPAND_AT:
                    if left != 0 or right != total:
                        sp.setSizes([0, total])
                    self._sync_sidebar_chrome()
                    return
                self._sidebar_collapsed = False
            elif left <= SIDEBAR_COLLAPSE_AT:
                self._sidebar_collapsed = True
                sp.setSizes([0, total])
                self._sync_sidebar_chrome()
                return
            else:
                self._sidebar_last_width = left
                self._sidebar_collapsed = False
            if left + right != total:
                sp.setSizes([left, max(1, total - left)])
            self._sync_sidebar_chrome()

        if delay_ms <= 0:
            _run()
        else:
            QTimer.singleShot(delay_ms, _run)

    def _sync_foreground_webview_layout(self) -> None:
        self._schedule_live_layout_sync(0)
        self._schedule_resize_settle(80)

    def _flyout_btn_style(self, light: bool) -> str:
        if light:
            return (
                "QPushButton{background:#ececec;color:#1a1a1a;border:1px solid #c4c4c4;"
                "border-radius:5px;padding:3px 6px;font-size:12px;}"
                "QPushButton:hover{background:#dcdcdc;}"
                "QPushButton:checked{background:#cfe3ff;border-color:#4a90e2;color:#1a3c66;}"
            )
        return (
            "QPushButton{background:#3c3c3c;color:#e8e8e8;border:1px solid #555;"
            "border-radius:5px;padding:3px 6px;font-size:12px;}"
            "QPushButton:hover{background:#4a4a4a;}"
            "QPushButton:checked{background:#2f5a8f;border-color:#4a90e2;color:#eaf2ff;}"
        )

    def _flyout_target_positions(self) -> List[Tuple[QPushButton, QPoint, QPoint]]:
        """计算每个选项的展开位置与收起位置（收起 = 叠在齿轮右侧）。

        左侧栏较窄时按钮宽度自动收缩以避免被裁切，栏变宽时恢复自然宽度。
        """
        gear = self.tools_btn
        gx, gy, gw, gh = gear.x(), gear.y(), gear.width(), gear.height()
        gap = 6
        start_x = gx + gw + gap
        y = gy + (gh - self._flyout_btn_h) // 2
        collapsed = QPoint(start_x, y)

        # 所有弹出按钮等宽，均匀显示；窄栏时统一收缩，宽栏时有上限避免过长。
        n = len(self._flyout_buttons)
        gaps_total = gap * (n - 1)
        natural_w = max((b.sizeHint().width() for b in self._flyout_buttons), default=52)
        unit = max(48, min(64, natural_w))
        avail = self._bottom_bar.width() - start_x - 8
        if avail > 0 and (unit * n + gaps_total) > avail:
            unit = max(30, (avail - gaps_total) // n)

        result: List[Tuple[QPushButton, QPoint, QPoint]] = []
        x = start_x
        for b in self._flyout_buttons:
            b.resize(unit, self._flyout_btn_h)
            result.append((b, QPoint(x, y), QPoint(collapsed)))
            x += unit + gap
        return result

    def _toggle_tools_flyout(self):
        anim = getattr(self, "_tools_anim", None)
        if anim is not None:
            anim.stop()
        if self._tools_expanded:
            self.tools_btn.animate_to(0.0)
            self._collapse_tools_flyout()
            self._tools_auto_collapse_timer.stop()
            if hasattr(self, "mem_status_label"):
                self.mem_status_label.show()
        else:
            self.tools_btn.animate_to(90.0)
            self._expand_tools_flyout()
            if hasattr(self, "mem_status_label"):
                self.mem_status_label.hide()
            # 展开 30 秒后自动收起，恢复显示内存信息
            self._tools_auto_collapse_timer.start(30_000)
        # 弹出按钮 raise_() 后齿轮会落到下层，这里重新置顶确保齿轮始终可见
        self.tools_btn.raise_()
        self._tools_expanded = not self._tools_expanded

    def _auto_collapse_tools(self):
        """齿轮展开超时未操作：自动收起并恢复内存信息显示。"""
        if getattr(self, "_tools_expanded", False):
            self._toggle_tools_flyout()

    def _expand_tools_flyout(self):
        info = self._flyout_target_positions()
        group = QParallelAnimationGroup(self)
        for i, (b, expanded, collapsed) in enumerate(info):
            b.move(collapsed)
            b.show()
            b.raise_()
            seq = QSequentialAnimationGroup(group)
            if i:
                seq.addPause(i * 55)
            a = QPropertyAnimation(b, b"pos")
            a.setDuration(300)
            a.setStartValue(collapsed)
            a.setEndValue(expanded)
            a.setEasingCurve(QEasingCurve.Type.OutBack)
            seq.addAnimation(a)
            group.addAnimation(seq)
        self._tools_anim = group
        group.start()

    def _collapse_tools_flyout(self):
        info = self._flyout_target_positions()
        group = QParallelAnimationGroup(self)
        for i, (b, _expanded, collapsed) in enumerate(reversed(info)):
            seq = QSequentialAnimationGroup(group)
            if i:
                seq.addPause(i * 45)
            a = QPropertyAnimation(b, b"pos")
            a.setDuration(240)
            a.setStartValue(b.pos())
            a.setEndValue(collapsed)
            a.setEasingCurve(QEasingCurve.Type.InCubic)
            seq.addAnimation(a)
            group.addAnimation(seq)
        group.finished.connect(self._hide_flyout_buttons)
        self._tools_anim = group
        group.start()

    def _hide_flyout_buttons(self):
        if self._tools_expanded:
            return
        for b in self._flyout_buttons:
            b.hide()

    def set_notifications_enabled(self, enabled: bool) -> None:
        """显式设置通知开关（托盘菜单调用），并应用到所有页面。"""
        enabled = bool(enabled)
        if hasattr(self, "notification_toggle") and self.notification_toggle:
            self.notification_toggle.setChecked(enabled)
        self.notification_toggle.setToolTip("通知：开" if enabled else "通知：关")
        for wv in self._iter_all_webviews():
            wv.apply_notifications_enabled(enabled)
        if enabled:
            self._reset_notify_state_on_enabled()
        else:
            self._notify_ring_pending = False
            t = getattr(self, "_notify_ring_timer", None)
            if t is not None and t.isActive():
                t.stop()
            self._stop_all_call_alerts()
        self._sync_tray_notification_check()

    def toggle_system_notification(self):
        """全局开关：仅控制 Teams 网页内提示音/提示（不做 Windows 系统通知）"""
        self.set_notifications_enabled(self.notification_toggle.isChecked())

    def _stop_all_call_alerts(self) -> None:
        """通知关闭：立即停止来电铃声并清理来电会话。"""
        self._stop_call_ring_loop()
        for aid in list(self._call_sessions.keys()):
            self._clear_call_session(aid)

    def _reset_notify_state_on_enabled(self) -> None:
        """通知重新打开：同步未读基线，确保下一条新消息能响（关闭期间不推进 fired_at）。"""
        for aid in self._loaded_account_ids():
            c = max(0, int(self.badge_cache.get(aid, 0) or 0))
            if aid in self._badge_pending:
                c = max(c, int(self._badge_pending[aid] or 0))
            self._notify_last_unread[aid] = c
            self._notify_sound_fired_at_count[aid] = c
            self._notify_baseline_locked.add(aid)
        self._notify_ring_pending = False
        if self._ensure_official_notify_sound() and self._notify_sound_player is None:
            self._init_notify_sound_player()

    def _loaded_account_ids(self) -> List[int]:
        return list(dict.fromkeys(
            list(self.web_views.keys()) + list(self.suspended_webviews.keys())
        ))

    def _get_webview_for_account(self, account_id: int) -> Optional[TeamsWebView]:
        return self.web_views.get(account_id) or self.suspended_webviews.get(account_id)

    def _iter_all_webviews(self):
        for wv in list(self.web_views.values()) + list(self.suspended_webviews.values()):
            if wv and wv.is_valid:
                yield wv

    def begin_window_drag(self):
        """拖动时仅暂停 WebView 重绘；不禁用主界面/AI 区，避免切回窗口后黑屏。"""
        if self._window_drag_active or self.is_closing:
            return
        self._window_drag_active = True
        try:
            for wv in self._iter_all_webviews():
                wv.set_window_drag_suspend(True)
        except Exception:
            pass

    def _schedule_live_layout_sync(self, delay_ms: int = 35) -> None:
        """缩放/拖分割条过程中：实时同步 Teams 布局与分割器尺寸。"""
        timer = getattr(self, "_live_layout_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_live_layout_sync)
            self._live_layout_timer = timer
        if delay_ms <= 0:
            timer.stop()
            self._on_live_layout_sync()
            return
        timer.start(max(16, int(delay_ms)))

    def _on_live_layout_sync(self) -> None:
        self._normalize_main_splitter_sizes()
        if not hasattr(self, "stack_widget") or self.stack_widget is None:
            return
        w = self.stack_widget.currentWidget()
        if isinstance(w, TeamsWebView) and getattr(w, "is_valid", False):
            w.updateGeometry()
            w._fire_teams_resize_event()

    def end_window_drag(self):
        if not self._window_drag_active:
            self._ensure_ui_updates_enabled()
            return
        self._window_drag_active = False
        try:
            for wv in self._iter_all_webviews():
                wv.set_window_drag_suspend(False)
        except Exception:
            pass
        self._ensure_ui_updates_enabled()
        self._sync_webview_lifecycle_states()

    def _ensure_ui_updates_enabled(self):
        """恢复因拖动或失焦可能残留的 updates 禁用状态。"""
        try:
            cw = self.centralWidget()
            if cw:
                cw.setUpdatesEnabled(True)
            if hasattr(self, "stack_widget") and self.stack_widget:
                self.stack_widget.setUpdatesEnabled(True)
            if hasattr(self, "ai_chat_panel") and self.ai_chat_panel:
                self.ai_chat_panel.setUpdatesEnabled(True)
        except Exception:
            pass

    def _repaint_on_window_activate(self):
        self.end_window_drag()
        try:
            self._ensure_ui_updates_enabled()
            if hasattr(self, "stack_widget") and self.stack_widget:
                self.stack_widget.repaint()
            if hasattr(self, "ai_chat_panel") and self.stack_widget.currentIndex() == 0:
                self.ai_chat_panel.repaint()
            self.repaint()
        except Exception:
            pass

    def _install_native_frame(self) -> None:
        """应用 DWM 原生阴影/圆角，并触发一次非客户区重算。"""
        if not getattr(self, "_native_frame", False):
            return
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        if not hwnd:
            return
        win_native_frame.apply_native_frame(hwnd)
        try:
            import ctypes
            from ctypes import wintypes

            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(hwnd), None, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE
                | SWP_NOZORDER | SWP_NOACTIVATE,
            )
        except Exception:
            pass

    def nativeEvent(self, eventType, message):
        # 注意：不要调用 super().nativeEvent()，在 PyQt 6.11/Python 3.14 上会触发
        # 访问冲突崩溃；未处理的消息返回 (False, 0) 交给 Qt 默认处理即可。
        try:
            import ctypes
            from ctypes import wintypes

            et = eventType
            if hasattr(et, "data"):
                et = et.data()
            if isinstance(et, (bytes, bytearray)):
                et = et.decode("ascii", errors="ignore")
            if str(et) != "windows_generic_MSG":
                return False, 0

            msg = ctypes.cast(
                int(message), ctypes.POINTER(wintypes.MSG)
            ).contents

            if getattr(self, "_native_frame", False):
                result = win_native_frame.handle_nc_message(
                    int(msg.hWnd), int(msg.message),
                    int(msg.wParam), int(msg.lParam),
                )
                if result is not None:
                    return True, result

            # 无边框窗口：任务栏图标再点一次应最小化（标准 Windows 切换行为）。
            WM_SYSCOMMAND = 0x0112
            SC_MINIMIZE = 0xF020
            if msg.message == WM_SYSCOMMAND and (int(msg.wParam) & 0xFFF0) == SC_MINIMIZE:
                if not getattr(self, "_shutdown_started", False) and not getattr(
                    self, "_force_quit", False
                ):
                    QTimer.singleShot(0, self.animated_minimize)
                return True, 0
        except Exception:
            pass
        return False, 0

    def changeEvent(self, event):
        super().changeEvent(event)
        t = event.type()
        if t == QEvent.Type.WindowDeactivate:
            self.end_window_drag()
        elif t == QEvent.Type.WindowActivate:
            QTimer.singleShot(0, self._repaint_on_window_activate)
        elif t == QEvent.Type.WindowStateChange:
            self._sync_window_shadow_layout()
            QTimer.singleShot(0, self._sync_taskbar_badge)
            # 从最小化恢复由系统直接显示，不再额外触发显示/透明度操作（会造成闪烁）。
            try:
                if hasattr(self, "title_bar") and self.title_bar:
                    if not (self.windowState() & Qt.WindowState.WindowMinimized):
                        self.title_bar.recheck_expanded_state()
                    self.title_bar.sync_window_state()
                    self.title_bar.cancel_drag_state()
            except Exception:
                pass

    def _resize_edges_at(self, global_pos) -> Optional[object]:
        """命中窗口外缘（阴影边带内）时返回需要缩放的方向，否则 None。"""
        if getattr(self, "_native_frame", False):
            return None  # 原生窗口缩放由系统 WM_NCHITTEST 处理
        if self._is_window_expanded():
            return None
        if getattr(self, "_app_locked", False):
            return None
        try:
            pos = self.mapFromGlobal(global_pos)
        except Exception:
            return None
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        if x < 0 or y < 0 or x > w or y > h:
            return None
        m = WINDOW_SHADOW_MARGIN + 3
        on_left = x <= m
        on_right = x >= w - m
        on_top = y <= m
        on_bottom = y >= h - m
        # 账号列表收起时，左侧内缘留给展开条/分割条，避免误触整窗缩放
        if on_left and self._is_sidebar_collapsed():
            corner = m + 6
            is_corner = (on_top and y <= corner) or (on_bottom and y >= h - corner)
            if not is_corner and x <= WINDOW_SHADOW_MARGIN + SIDEBAR_EXPAND_STRIP_W + 28:
                on_left = False
        if not (on_left or on_right or on_top or on_bottom):
            return None
        edges = Qt.Edge(0)
        if on_left:
            edges |= Qt.Edge.LeftEdge
        if on_right:
            edges |= Qt.Edge.RightEdge
        if on_top:
            edges |= Qt.Edge.TopEdge
        if on_bottom:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges) -> object:
        L = bool(edges & Qt.Edge.LeftEdge)
        R = bool(edges & Qt.Edge.RightEdge)
        T = bool(edges & Qt.Edge.TopEdge)
        B = bool(edges & Qt.Edge.BottomEdge)
        if (T and L) or (B and R):
            return Qt.CursorShape.SizeFDiagCursor
        if (T and R) or (B and L):
            return Qt.CursorShape.SizeBDiagCursor
        if L or R:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def _update_resize_cursor(self, edges) -> None:
        if edges:
            self.setCursor(self._cursor_for_edges(edges))
            self._resize_cursor_active = True
        elif self._resize_cursor_active:
            self.unsetCursor()
            self._resize_cursor_active = False

    def eventFilter(self, watched, event):
        et = event.type()
        if et == QEvent.Type.KeyPress:
            try:
                if event.key() == Qt.Key.Key_Escape:
                    if self.isFullScreen():
                        self._exit_trapped_fullscreen()
                        return True
                    self.go_home()
                    return True
            except Exception:
                pass
        if et == QEvent.Type.MouseMove and not event.buttons():
            try:
                edges = self._resize_edges_at(event.globalPosition().toPoint())
                self._update_resize_cursor(edges)
            except Exception:
                pass
        elif et == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                try:
                    edges = self._resize_edges_at(event.globalPosition().toPoint())
                    if edges:
                        win = self.windowHandle()
                        if win is not None:
                            self._begin_resize_session()
                            self._apply_fast_chrome_masks()
                            self._schedule_resize_settle(150)
                            win.startSystemResize(edges)
                            return True
                except Exception:
                    pass
        if et == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self.end_window_drag()
        return super().eventFilter(watched, event)

    def _exit_trapped_fullscreen(self):
        """WebView2 视频全屏误触整窗全屏时，Esc 恢复标题栏与窗口状态。"""
        if self.isFullScreen():
            self.showNormal()
        if hasattr(self, "title_bar") and self.title_bar:
            self.title_bar.sync_window_state()
        wv = None
        if self.current_account_id:
            wv = self._get_webview_for_account(self.current_account_id)
        if wv and getattr(wv, "_engine_kind", "") == "webview2":
            widget = getattr(wv, "_wv2_widget", None)
            if widget and getattr(widget, "is_ready", False):
                try:
                    widget.evaluate_js(
                        "try{if(document.fullscreenElement)document.exitFullscreen();}catch(e){}"
                    )
                except Exception:
                    pass

    def go_home(self):
        """返回主界面（Esc → TeamsXAi，点击左侧账号则切回 Teams）"""
        try:
            self.current_account_id = None
            if hasattr(self, "stack_widget") and self.stack_widget:
                self.stack_widget.setCurrentIndex(0)
            if hasattr(self, "account_list") and self.account_list:
                self.account_list.clearSelection()
            self._sync_webview_lifecycle_states()
            self.update_status("TeamsXAi")
            if hasattr(self, "ai_chat_panel"):
                QTimer.singleShot(0, self.ai_chat_panel._focus_input)
        except Exception as e:
            print(f"返回主界面错误: {e}")

    def _dock_webview_to_park(self, web_view: Optional[TeamsWebView]) -> None:
        """将 WebView 放进屏外停车区（不碰 stack）。"""
        if web_view is None or not getattr(web_view, "is_valid", True):
            return
        try:
            park = self._webview_park
            if park is None:
                return
            if hasattr(self, "stack_widget") and self.stack_widget:
                idx = self.stack_widget.indexOf(web_view)
                if idx >= 0:
                    self.stack_widget.removeWidget(web_view)
            if web_view.parent() is not park:
                web_view.setParent(park)
            if self._webview_park_layout.indexOf(web_view) < 0:
                self._webview_park_layout.addWidget(web_view)
            web_view.hide()
        except Exception as e:
            print(f"停放 WebView 错误: {e}")

    def _park_webview_background(self, web_view: Optional[TeamsWebView]) -> None:
        """把 WebView 挪到隐藏停车区，不占 stack 前台（用户正在看的页面不挪动）。"""
        if web_view is None or not getattr(web_view, "is_valid", True):
            return
        try:
            if (
                hasattr(self, "stack_widget")
                and self.stack_widget
                and self.stack_widget.currentWidget() is web_view
            ):
                return
        except Exception:
            pass
        try:
            if hasattr(self, "stack_widget") and self.stack_widget:
                idx = self.stack_widget.indexOf(web_view)
                if idx >= 0:
                    self.stack_widget.removeWidget(web_view)
        except Exception:
            pass
        self._dock_webview_to_park(web_view)

    def _get_lru_active_webview_id(self, exclude: Optional[Set[int]] = None) -> Optional[int]:
        """在 web_views 活跃池内取 last_used 最早者（真实 LRU）。"""
        exclude = exclude or set()
        candidates: List[Tuple[float, int]] = []
        for aid in self.web_views.keys():
            aid = int(aid)
            if aid in exclude:
                continue
            info = self.webview_pool.get(aid)
            ts = float(info.get("last_used", 0.0)) if info else 0.0
            candidates.append((ts, aid))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][1]

    def _sleep_webview_account(self, account_id: int) -> None:
        self.suspend_webview(int(account_id))

    def _trim_active_webviews_to_limit(
        self, keep_account_id: Optional[int] = None
    ) -> None:
        """保证 len(web_views) <= MAX_ACTIVE_WEBVIEWS；0 表示不限制。"""
        if int(MAX_ACTIVE_WEBVIEWS) <= 0:
            return
        keep_id = int(keep_account_id) if keep_account_id is not None else None
        need_slot = keep_id is not None and keep_id not in self.web_views

        def _exclude() -> Set[int]:
            ex: Set[int] = set()
            if keep_id is not None:
                ex.add(keep_id)
            cur = self.current_account_id
            if cur is not None:
                ex.add(int(cur))
            return ex

        for _ in range(max(1, len(self.web_views))):
            over = len(self.web_views) > MAX_ACTIVE_WEBVIEWS
            at_cap_need = need_slot and len(self.web_views) >= MAX_ACTIVE_WEBVIEWS
            if not over and not at_cap_need:
                break
            victim = self._get_lru_active_webview_id(_exclude())
            if victim is None:
                break
            self._sleep_webview_account(victim)

    def _ensure_taskbar_minimize_style(self) -> None:
        """无边框窗口保留 WS_MINIMIZEBOX，任务栏图标才能“再点一次最小化”。"""
        if getattr(self, "_native_frame", False):
            return
        if getattr(self, "_taskbar_minimize_style_applied", False):
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.winId())
            if not hwnd:
                return
            GWL_STYLE = -16
            WS_MINIMIZEBOX = 0x00020000
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            new_style = style | WS_MINIMIZEBOX
            if new_style != style:
                user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
                SWP_FRAMECHANGED = 0x0020
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                SWP_NOACTIVATE = 0x0010
                user32.SetWindowPos(
                    wintypes.HWND(hwnd), None, 0, 0, 0, 0,
                    SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE
                    | SWP_NOZORDER | SWP_NOACTIVATE,
                )
            self._taskbar_minimize_style_applied = True
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_native_frame", False) and not getattr(
            self, "_native_frame_installed", False
        ):
            self._native_frame_installed = True
            self._install_native_frame()
        else:
            self._ensure_taskbar_minimize_style()
        self._sync_window_chrome()
        QTimer.singleShot(0, self._sync_taskbar_badge)
        QTimer.singleShot(0, self._normalize_main_splitter_sizes)
        QTimer.singleShot(50, self._focus_ai_input_if_home)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_lock_overlay_geometry()
        self._sync_sidebar_chrome()
        self._begin_resize_session()
        self._apply_fast_chrome_masks()
        self._schedule_resize_settle(160)
        self._sync_ai_panel_layout()

    def _focus_ai_input_if_home(self):
        if not hasattr(self, "stack_widget") or not hasattr(self, "ai_chat_panel"):
            return
        if self.stack_widget.currentIndex() == 0:
            self.ai_chat_panel._focus_input()

    def _sync_ai_panel_layout(self) -> None:
        panel = getattr(self, "ai_chat_panel", None)
        sw = getattr(self, "stack_widget", None)
        if panel is None or sw is None or sw.currentIndex() != 0:
            return
        panel._sync_composer_width()
        if panel._chat_layout_active and panel._messages:
            panel._schedule_chat_relayout(streaming=panel._stream_active)

    def _is_account_foreground(self, account_id: Optional[int]) -> bool:
        if not account_id or self.is_closing or getattr(self, "_app_locked", False):
            return False
        if account_id != self.current_account_id:
            return False
        if account_id in self.suspended_webviews:
            return False
        wv = self._get_webview_for_account(account_id)
        if not wv or not getattr(wv, "is_valid", False):
            return False
        if not hasattr(self, "stack_widget") or self.stack_widget is None:
            return False
        if self.stack_widget.currentIndex() == 0:
            return False
        return self.stack_widget.currentWidget() is wv

    def _sync_webview_lifecycle_states(self):
        """
        同步各 WebView 运行档位：
        - 当前查看账号：foreground（完整扫描 + Normal 内存）
        - 其它活跃/休眠账号：warm_notify（Notification 桥 + 慢轮询）
        """
        if self.is_closing:
            return
        cur = self.current_account_id
        prev = getattr(self, "_lifecycle_cur_id", None)
        self._lifecycle_cur_id = cur
        sync_ids: Set[int] = set()
        if prev is not None and prev in self.web_views:
            sync_ids.add(int(prev))
        if cur is not None and cur in self.web_views:
            sync_ids.add(int(cur))
        for aid in sync_ids:
            wv = self.web_views.get(aid)
            if not wv:
                continue
            mode = RUNTIME_FOREGROUND if aid == cur else RUNTIME_WARM_NOTIFY
            try:
                wv.apply_runtime_mode(mode)
            except Exception as e:
                print(f"[内存] 同步档位失败 账号 {aid}: {e}")
            if aid != cur:
                try:
                    if (
                        getattr(self, "_webview_park", None) is not None
                        and wv.parent() is self._webview_park
                    ):
                        wv.hide()
                except Exception:
                    pass
                if ENABLE_BACKGROUND_FREEZE:
                    try:
                        wv.suspend_page()
                    except Exception:
                        pass
        for aid, wv in list(self.suspended_webviews.items()):
            if not wv:
                continue
            try:
                wv.apply_runtime_mode(RUNTIME_WARM_NOTIFY)
            except Exception as e:
                print(f"[内存] 同步休眠档位失败 账号 {aid}: {e}")
            if ENABLE_BACKGROUND_FREEZE:
                try:
                    if not getattr(wv, "_core_suspended", False):
                        wv.suspend_page()
                except Exception:
                    pass

    def _lock_password_record(self) -> Optional[Tuple[str, str]]:
        """返回 (salt_hex, hash_hex) 或 None"""
        v = (self.db.get_setting("lock_pwd") or "").strip()
        if not v or ":" not in v:
            return None
        salt_hex, hash_hex = v.split(":", 1)
        if not salt_hex or not hash_hex:
            return None
        return salt_hex, hash_hex

    def _hash_password(self, password: str, salt_bytes: bytes) -> str:
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 120_000)
        return dk.hex()

    def on_lock_clicked(self):
        rec = self._lock_password_record()
        if not rec:
            self._show_set_lock_password_dialog()
            return
        self._enter_app_lock()

    def _show_set_lock_password_dialog(self):
        light = bool(getattr(self, "_theme_light", False))
        if light:
            pal = {
                "card_bg": "#ffffff", "card_border": "#e6e8ec", "title": "#1f2329",
                "sub": "#8a9099", "label": "#5b616b", "input_bg": "#f6f8fb",
                "input_border": "#dfe3e8", "input_focus": "#3b82f6", "input_text": "#1f2329",
                "accent": "#2f6fed", "accent_hover": "#2560d6",
                "ghost_text": "#6b7280", "ghost_border": "#d6dae0", "ghost_hover": "#f0f2f5",
                "icon_bg": "#e8f1ff", "icon_fg": "#2f6fed", "shadow_alpha": 60,
            }
        else:
            pal = {
                "card_bg": "#2b2d31", "card_border": "#3a3d42", "title": "#f2f3f5",
                "sub": "#9aa0a6", "label": "#aab0b8", "input_bg": "#34373c",
                "input_border": "#42454a", "input_focus": "#5a9cf5", "input_text": "#f2f3f5",
                "accent": "#3b82f6", "accent_hover": "#4a90f0",
                "ghost_text": "#b6bbc2", "ghost_border": "#4a4d52", "ghost_hover": "#3a3d42",
                "icon_bg": "#2f4a6e", "icon_fg": "#7fb2ff", "shadow_alpha": 130,
            }

        dlg = QDialog(self)
        dlg.setWindowTitle("设置锁定密码")
        dlg.setModal(True)
        dlg.setFixedSize(384, 300)
        dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(24, 20, 24, 26)

        card = QFrame()
        card.setObjectName("lockPwdCard")
        card.setStyleSheet(
            f"QFrame#lockPwdCard {{ background: {pal['card_bg']};"
            f"border: 1px solid {pal['card_border']}; border-radius: 18px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, pal["shadow_alpha"]))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(12)
        icon = QLabel("\U0001F512")
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background: {pal['icon_bg']}; color: {pal['icon_fg']};"
            "border: none; border-radius: 19px; font-size: 18px;"
        )
        head_col = QVBoxLayout()
        head_col.setSpacing(1)
        title = QLabel("设置锁定密码")
        title.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {pal['title']};"
            "border: none; background: transparent;"
        )
        sub = QLabel("锁定后需输入此密码才能解锁界面")
        sub.setStyleSheet(
            f"font-size: 12px; color: {pal['sub']}; border: none; background: transparent;"
        )
        head_col.addWidget(title)
        head_col.addWidget(sub)
        head.addWidget(icon)
        head.addLayout(head_col, 1)
        lay.addLayout(head)

        label_css = (
            f"font-size: 12px; color: {pal['label']}; border: none; background: transparent;"
        )
        input_css = (
            f"QLineEdit {{ background: {pal['input_bg']}; color: {pal['input_text']};"
            f"border: 1px solid {pal['input_border']}; border-radius: 9px;"
            "padding: 7px 10px; font-size: 13px; }"
            f"QLineEdit:focus {{ border: 1px solid {pal['input_focus']}; }}"
        )
        p1 = QLineEdit()
        p2 = QLineEdit()
        p1.setEchoMode(QLineEdit.EchoMode.Password)
        p2.setEchoMode(QLineEdit.EchoMode.Password)
        p1.setPlaceholderText("请输入密码")
        p2.setPlaceholderText("请再次输入密码")
        for lbl_text, edit in (("密码", p1), ("确认密码", p2)):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(label_css)
            edit.setStyleSheet(input_css)
            edit.setFixedHeight(36)
            block = QVBoxLayout()
            block.setContentsMargins(0, 0, 0, 0)
            block.setSpacing(4)
            block.addWidget(lbl)
            block.addWidget(edit)
            lay.addLayout(block)

        lay.addStretch()
        lay.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(34)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ color: {pal['ghost_text']}; background: transparent;"
            f"border: 1px solid {pal['ghost_border']}; border-radius: 9px;"
            "padding: 5px 16px; font-size: 12px; }"
            f"QPushButton:hover {{ background: {pal['ghost_hover']}; color: {pal['title']}; }}"
        )
        ok_btn = QPushButton("确定")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setDefault(True)
        ok_btn.setFixedHeight(34)
        ok_btn.setMinimumWidth(80)
        ok_btn.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: {pal['accent']}; border: none;"
            "border-radius: 9px; padding: 5px 16px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {pal['accent_hover']}; }}"
        )
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)
        root.addWidget(card)

        parent_geo = self.frameGeometry()
        dlg.move(
            parent_geo.center().x() - dlg.width() // 2,
            parent_geo.center().y() - dlg.height() // 2,
        )

        def do_ok():
            a = p1.text()
            b = p2.text()
            if not a or a != b:
                ConfirmCardDialog.info(
                    self, title="提示", message="两次输入的密码不一致，请重新输入。",
                    light=light,
                )
                return
            salt = os.urandom(16)
            h = self._hash_password(a, salt)
            self.db.set_setting("lock_pwd", f"{salt.hex()}:{h}")
            dlg.accept()

        ok_btn.clicked.connect(do_ok)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def _style_lock_overlay(self):
        if self._lock_overlay is None:
            return
        if self._theme_light:
            self._lock_overlay.setStyleSheet("""
            QWidget#lockOverlay { background-color: #f3f3f3; }
            QLineEdit {
                background-color: #ffffff; color: #1a1a1a;
                border: 1px solid #ccc; border-radius: 6px;
                padding: 10px 12px; font-size: 16px;
            }
            """)
        else:
            self._lock_overlay.setStyleSheet("""
            QWidget#lockOverlay { background-color: #1e1e1e; }
            QLineEdit {
                background-color: #2a2a2a; color: #e8e8e8;
                border: 1px solid #3c3c3c; border-radius: 6px;
                padding: 10px 12px; font-size: 16px;
            }
            """)

    def _set_app_locked(self, locked: bool):
        """锁定：隐藏主界面；解锁后仅恢复布局（WebView 需手动点击账号加载）。"""
        self._app_locked = locked
        if hasattr(self, "_main_splitter") and self._main_splitter:
            self._main_splitter.setVisible(not locked)
        elif hasattr(self, "_left_panel") and hasattr(self, "stack_widget"):
            self._left_panel.setVisible(not locked)
            self.stack_widget.setVisible(not locked)
        if locked:
            for wv in self._iter_all_webviews():
                try:
                    wv.hide()
                except Exception:
                    pass

    def _pause_background_services_for_lock(self) -> None:
        for timer in (
            getattr(self, "check_timer", None),
            getattr(self, "badge_fast_timer", None),
            getattr(self, "badge_background_timer", None),
            getattr(self, "memory_timer", None),
            getattr(self, "_daily_cache_timer", None),
        ):
            if timer is not None:
                try:
                    timer.stop()
                except Exception:
                    pass

    def _resume_background_services_after_unlock(self) -> None:
        if self.is_closing:
            return
        try:
            self.start_notification_check()
            self.start_memory_cleanup()
            self.start_daily_cache_cleanup()
        except Exception as e:
            print(f"恢复后台定时器失败: {e}")

    def _ensure_lock_overlay_widgets(self) -> None:
        if self._lock_overlay is not None:
            return
        host = getattr(self, "_body_host", None) or self.centralWidget()
        self._lock_overlay = QWidget(host)
        self._lock_overlay.setObjectName("lockOverlay")
        lay = QVBoxLayout(self._lock_overlay)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        box = QWidget()
        box_l = QHBoxLayout(box)
        box_l.setContentsMargins(0, 0, 0, 0)
        box_l.addStretch(1)
        self._lock_input = QLineEdit()
        self._lock_input.setFixedWidth(380)
        self._lock_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._lock_input.setPlaceholderText("")
        box_l.addWidget(self._lock_input)
        box_l.addStretch(1)
        lay.addWidget(box)
        lay.addStretch(1)
        self._lock_input.returnPressed.connect(self._try_unlock_app)

    def _try_unlock_app(self) -> None:
        rec = self._lock_password_record()
        if not rec or not self._lock_input:
            return
        salt_hex, hash_hex = rec
        salt = bytes.fromhex(salt_hex)
        inp = self._lock_input.text()
        if not inp:
            return
        if self._hash_password(inp, salt) != hash_hex:
            self._lock_input.clear()
            return
        self._unlock_app()

    def _unlock_app(self) -> None:
        if getattr(self, "_lock_teardown_active", False):
            self.update_status("正在释放内存，请稍候…")
            return
        if self._lock_input:
            self._lock_input.clear()
        if self._lock_overlay:
            self._lock_overlay.hide()
        self._set_app_locked(False)
        if getattr(self, "_webview_park", None):
            try:
                self._webview_park.show()
            except Exception:
                pass
        self.go_home()
        self._resume_background_services_after_unlock()
        self._refresh_default_status()
        if self._lock_input:
            self._lock_input.clearFocus()

    def _enter_app_lock(self) -> None:
        """先出锁定界面（无卡顿），再在事件循环里逐个卸载 WebView 释内存。"""
        if getattr(self, "_app_locked", False):
            return
        self._pause_background_services_for_lock()
        self.current_account_id = None
        if hasattr(self, "stack_widget") and self.stack_widget:
            self.stack_widget.setCurrentIndex(0)
        if hasattr(self, "account_list") and self.account_list:
            self.account_list.clearSelection()
        self._ensure_lock_overlay_widgets()
        self._style_lock_overlay()
        self._set_app_locked(True)
        x, y, w, h = self._lock_overlay_geometry()
        self._lock_overlay.setGeometry(x, y, w, h)
        self._lock_overlay.show()
        self._lock_overlay.raise_()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        if self._lock_input:
            self._lock_input.clear()
            self._lock_input.setFocus()
        self.update_status("已锁定")
        self._lock_unload_queue = list(
            dict.fromkeys(
                list(self.web_views.keys()) + list(self.suspended_webviews.keys())
            )
        )
        self._lock_teardown_active = bool(self._lock_unload_queue)
        if getattr(self, "_webview_park", None):
            try:
                self._webview_park.hide()
            except Exception:
                pass
        if self._lock_teardown_active:
            QTimer.singleShot(LOCK_UNLOAD_INTERVAL_MS, self._lock_teardown_step)

    def _lock_teardown_step(self) -> None:
        if not getattr(self, "_lock_teardown_active", False):
            return
        if not self._lock_unload_queue:
            self._lock_teardown_finished()
            return
        aid = int(self._lock_unload_queue.pop(0))
        try:
            self.unload_webview(aid)
        except Exception as e:
            print(f"锁定释放 WebView {aid} 失败: {e}")
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        QTimer.singleShot(LOCK_UNLOAD_INTERVAL_MS, self._lock_teardown_step)

    def _lock_teardown_finished(self) -> None:
        self._lock_teardown_active = False
        self._lock_unload_queue = []
        if getattr(self, "_app_locked", False):
            self.update_status("已锁定 · 内存已释放")
        QTimer.singleShot(800, self._lock_deferred_gc)

    def _lock_deferred_gc(self) -> None:
        if not getattr(self, "_app_locked", False):
            return
        try:
            gc.collect()
        except Exception:
            pass

    def _lock_overlay_geometry(self) -> Tuple[int, int, int, int]:
        """遮罩铺满标题栏以下的内容区。"""
        host = getattr(self, "_body_host", None)
        if host is not None:
            return 0, 0, host.width(), host.height()
        th = self.title_bar.height() if hasattr(self, "title_bar") and self.title_bar else 38
        cw = self.centralWidget()
        if cw is None:
            return 0, th, self.width(), max(0, self.height() - th)
        return 0, th, cw.width(), max(0, cw.height() - th)

    def _sync_lock_overlay_geometry(self):
        if self._lock_overlay and self._lock_overlay.isVisible():
            x, y, w, h = self._lock_overlay_geometry()
            self._lock_overlay.setGeometry(x, y, w, h)

    def update_status(self, text: str):
        """更新状态标签（同文本不重绘，避免无谓刷新）"""
        try:
            if self.status_label.text() == text:
                return
        except Exception:
            pass
        self.status_label.setText(text)

    def _has_active_call(self) -> bool:
        """是否有正在响铃/进行中的来电（用于保护状态栏文案不被默认刷新覆盖）。"""
        if getattr(self, "_call_ring_active_aid", None) is not None:
            return True
        for sess in (getattr(self, "_call_sessions", None) or {}).values():
            if sess.get("ring_loop_started") and not sess.get("suppressed"):
                return True
        return False

    def _refresh_default_status(self) -> None:
        """状态栏默认文案：活跃 / 休眠 / 账号总数。

        来电进行中时跳过：否则 90ms 一次的轮询会把“X 来电”反复覆盖回默认文案，
        造成状态栏蓝色文字闪烁。内存/进程信息单独显示在底部栏，避免撑宽账号列表。
        """
        self._refresh_memory_hint()
        if self._has_active_call():
            return
        online = len(self._loaded_account_ids())
        total_accounts = len(self.db.get_all_accounts())
        self.update_status(f"在线 {online} · 共 {total_accounts} 账号")

    @staticmethod
    def _fmt_mem_size(mb: int) -> str:
        """内存格式化：≥1G 用 GB（1 位小数），低于 1G 用 MB。"""
        mb = max(0, int(mb))
        if mb < 1024:
            return f"{mb}MB"
        return f"{mb / 1024:.1f}GB"

    def _refresh_memory_hint(self) -> None:
        """底部栏内存提示：可用 · 已用（仅 TeamsX 自身；可用低于 1G 转红色）。"""
        label = getattr(self, "mem_status_label", None)
        if label is None:
            return
        parts: List[str] = []
        free_mb = int(getattr(self, "_memory_guard_last_free_mb", -1))
        used_mb = int(getattr(self, "_memory_guard_last_used_mb", 0))
        if free_mb >= 0:
            parts.append(f"可用 {self._fmt_mem_size(free_mb)}")
        if used_mb > 0:
            parts.append(f"已用 {self._fmt_mem_size(used_mb)}")
        if getattr(self, "_memory_pressure", False):
            parts.append("内存紧张")
        text = " · ".join(parts)
        low = free_mb >= 0 and free_mb < int(LOW_MEMORY_RED_MB)
        color = "#ff4d4f" if low else "#2f88ff"
        if getattr(self, "_mem_hint_color", "") != color:
            self._mem_hint_color = color
            label.setStyleSheet(
                f"QLabel {{ color: {color}; font-size: 12px; font-weight: bold; "
                "padding-left: 2px; background: transparent; border: none; }"
            )
        if label.text() != text:
            label.setText(text)

    def start_notification_check(self):
        """启动通知检查定时器"""
        if self.check_timer:
            self.check_timer.stop()

        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.process_notification_queue)
        self.check_timer.start(NOTIFICATION_CHECK_INTERVAL)

        if getattr(self, "badge_fast_timer", None):
            self.badge_fast_timer.stop()
        self.badge_fast_timer = QTimer(self)
        self.badge_fast_timer.timeout.connect(self._poll_foreground_badge)
        self.badge_fast_timer.start(BADGE_FOREGROUND_POLL_MS)

        if getattr(self, "badge_background_timer", None):
            self.badge_background_timer.stop()
        self.badge_background_timer = QTimer(self)
        self.badge_background_timer.timeout.connect(
            self._poll_background_badge_round_robin
        )
        self.badge_background_timer.start(BADGE_BACKGROUND_POLL_MS)

    def _poll_foreground_badge(self):
        """当前账号：轻量未读同步（页面内 Observer 仍负责即时消息）。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        account_id = self.current_account_id
        if not account_id:
            return
        web_view = self._get_webview_for_account(account_id)
        if web_view and web_view.is_valid and not web_view.is_loading:
            web_view.poll_unread_badge()

    def _poll_background_badge_round_robin(self):
        """后台账号：每 3s 扫 1 个号的未读，避免 120ms 全员唤醒。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        all_ids = self._loaded_account_ids()
        if not all_ids:
            return
        n = len(all_ids)
        tries = 0
        while tries < n:
            tries += 1
            account_id = all_ids[self._badge_poll_index % n]
            self._badge_poll_index = (self._badge_poll_index + 1) % n
            if account_id == self.current_account_id:
                continue
            web_view = self._get_webview_for_account(account_id)
            if not web_view or not web_view.is_valid or web_view.is_loading:
                continue
            web_view.poll_unread_badge()
            break

    def process_notification_queue(self):
        """后台账号轻量未读轮询；前台消息由页面内 Notification 桥 + JS 扫描负责。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return

        checked = 0
        fg_id = self.current_account_id
        max_checks = BADGE_CHECKS_PER_TICK
        if not self.check_queue:
            self.check_queue.extend(self._loaded_account_ids())

        while self.check_queue and checked < max_checks:
            account_id = self.check_queue.popleft()
            if account_id == fg_id:
                continue
            web_view = self._get_webview_for_account(account_id)
            if web_view and web_view.is_valid and not web_view.is_loading:
                web_view.poll_unread_badge()
                checked += 1

        # 状态栏不必每 500ms 全量刷新，交给角标/内存定时器即可

    def start_memory_cleanup(self):
        """启动内存清理定时器"""
        if self.memory_timer:
            self.memory_timer.stop()

        self.memory_timer = QTimer()
        self.memory_timer.timeout.connect(self.cleanup_idle_webviews)
        self.memory_timer.start(MEMORY_CLEAN_INTERVAL * 1000)

    def start_memory_guard(self):
        """启动内存压力监控：低频完整统计 + 高频低内存探测。"""
        if getattr(self, "_memory_guard_timer", None):
            self._memory_guard_timer.stop()
        self._memory_guard_timer = QTimer(self)
        self._memory_guard_timer.timeout.connect(self._run_memory_guard)
        self._memory_guard_timer.start(int(MEMORY_GUARD_INTERVAL_SEC) * 1000)
        if getattr(self, "_memory_light_timer", None):
            self._memory_light_timer.stop()
        self._memory_light_timer = QTimer(self)
        self._memory_light_timer.timeout.connect(self._run_lightweight_memory_probe)
        self._memory_light_timer.start(int(MEMORY_LIGHT_PROBE_INTERVAL_SEC) * 1000)
        if getattr(self, "_memory_guard_debounce_timer", None):
            self._memory_guard_debounce_timer.stop()
        self._memory_guard_debounce_timer = QTimer(self)
        self._memory_guard_debounce_timer.setSingleShot(True)
        self._memory_guard_debounce_timer.timeout.connect(self._run_memory_guard)
        QTimer.singleShot(300, self._run_lightweight_memory_probe)
        QTimer.singleShot(1200, self._run_memory_guard)
        if MEMORY_GROOM_ENABLE:
            if getattr(self, "_memory_groom_timer", None):
                self._memory_groom_timer.stop()
            self._memory_groom_timer = QTimer(self)
            self._memory_groom_timer.timeout.connect(self._maybe_memory_groom_maintenance)
            self._memory_groom_timer.start(
                int(MEMORY_GROOM_MAINTENANCE_INTERVAL_SEC) * 1000
            )
        if ENABLE_BACKGROUND_FREEZE:
            self._start_notify_waker()

    def _start_notify_waker(self) -> None:
        """轮询唤醒器：轮流/波浪唤醒冻结账号 → 拉新消息/响铃 → 再冻结。"""
        if getattr(self, "_notify_waker_timer", None):
            try:
                self._notify_waker_timer.stop()
            except Exception:
                pass
        self._waker_index = 0
        self._waker_wave_active = False
        self._notify_waker_timer = QTimer(self)
        self._notify_waker_timer.setSingleShot(True)
        self._notify_waker_timer.timeout.connect(self._run_notify_waker)
        self._schedule_notify_waker(1200)

    def _schedule_notify_waker(self, delay_ms: int = 0) -> None:
        timer = getattr(self, "_notify_waker_timer", None)
        if timer is None or self.is_closing:
            return
        timer.start(max(200, int(delay_ms)))

    def _run_notify_waker(self) -> None:
        """唤醒冻结账号拉新消息/来电，再冻结。标准版用波浪模式同时唤醒全部。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        if getattr(self, "_waker_wave_active", False):
            return
        cur = self.current_account_id
        candidates: List[Tuple[int, TeamsWebView]] = []
        for aid, wv in list(self.web_views.items()) + list(
            self.suspended_webviews.items()
        ):
            if not wv or aid == cur:
                continue
            if getattr(wv, "_core_suspended", False):
                candidates.append((int(aid), wv))
        if not candidates:
            return

        if NOTIFY_WAKER_WAVE_ALL:
            targets = [wv for _, wv in candidates]
            self._waker_wave_active = True
            for _, wv in candidates:
                try:
                    wv.resume_page()
                except Exception:
                    pass

            def _poll_wave(wvs=targets):
                if self.is_closing:
                    return
                for wv in wvs:
                    try:
                        if wv.is_valid and not wv.is_loading:
                            wv.poll_unread_badge()
                    except Exception:
                        pass

            def _resuspend_wave(wvs=targets):
                self._waker_wave_active = False
                if self.is_closing:
                    return
                for wv in wvs:
                    try:
                        if not wv.isVisible():
                            wv.suspend_page()
                    except Exception:
                        pass
                self._schedule_notify_waker(int(NOTIFY_WAKER_INTERVAL_SEC) * 1000)

            dwell_ms = int(NOTIFY_WAKER_DWELL_SEC) * 1000
            QTimer.singleShot(max(400, dwell_ms - 1200), _poll_wave)
            QTimer.singleShot(dwell_ms, _resuspend_wave)
            return

        candidates.sort(key=lambda x: x[0])
        idx = int(getattr(self, "_waker_index", 0)) % len(candidates)
        self._waker_index = idx + 1
        aid, wv = candidates[idx]
        try:
            wv.resume_page()
        except Exception:
            self._schedule_notify_waker(int(NOTIFY_WAKER_INTERVAL_SEC) * 1000)
            return

        def _read_badge(target=wv):
            if self.is_closing:
                return
            try:
                if target.is_valid and not target.is_loading:
                    target.poll_unread_badge()
            except Exception:
                pass

        def _resuspend(target=wv):
            if self.is_closing:
                return
            try:
                if not target.isVisible():
                    target.suspend_page()
            except Exception:
                pass
            self._schedule_notify_waker(int(NOTIFY_WAKER_INTERVAL_SEC) * 1000)

        dwell_ms = int(NOTIFY_WAKER_DWELL_SEC) * 1000
        QTimer.singleShot(max(500, dwell_ms - 1500), _read_badge)
        QTimer.singleShot(dwell_ms, _resuspend)

    def _effective_suspended_limit(self) -> int:
        if int(MAX_SUSPENDED_WEBVIEWS) <= 0:
            return 999999
        return int(MAX_SUSPENDED_WEBVIEWS)

    def _schedule_memory_guard_refresh(self, delay_ms: int = 800) -> None:
        """切换/登录后防抖刷新完整内存数据，避免连续操作时频繁 tasklist。"""
        last = float(getattr(self, "_memory_guard_last_full_at", 0.0) or 0.0)
        if last and (time.time() - last) < 8.0:
            return
        timer = getattr(self, "_memory_guard_debounce_timer", None)
        if timer is None:
            QTimer.singleShot(delay_ms, self._run_memory_guard)
            return
        timer.start(max(0, int(delay_ms)))

    def _apply_memory_guard_stats(
        self, free_mb: int, used_mb: int, wv2_stats: Tuple[int, int]
    ) -> None:
        """主线程应用内存统计结果（采集在后台线程完成）。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        wv2_count, wv2_mb = wv2_stats
        prev_renderer = int(getattr(self, "_memory_guard_wv2_count", -1))
        if prev_renderer >= 0 and (int(wv2_count) - prev_renderer) >= int(
            ADAPTIVE_RECYCLE_LOADING_STORM_DELTA
        ):
            self._adaptive_recycle_storm_until = time.time() + 30.0
        self._memory_guard_last_full_at = time.time()
        self._memory_guard_last_free_mb = free_mb
        self._memory_guard_last_used_mb = used_mb
        self._memory_guard_wv2_count = int(wv2_count)
        self._memory_guard_wv2_mb = int(wv2_mb)
        pressure = (
            free_mb >= 0 and free_mb < int(MEMORY_PRESSURE_MIN_FREE_MB)
        )
        prev = bool(getattr(self, "_memory_pressure", False))
        self._memory_pressure = pressure
        self._update_low_memory_state(free_mb)
        self._enforce_background_low_memory()
        self._apply_memory_tiers()
        self._update_memory_controller_state()
        self._maybe_schedule_adaptive_recycle()
        if pressure and not prev:
            print(
                f"[内存保护] 可用内存 {free_mb}MB < {MEMORY_PRESSURE_MIN_FREE_MB}MB，"
                f"TeamsX 已用 ~{used_mb}MB（WebView2 {wv2_count} 进程 / ~{wv2_mb}MB）"
            )
        if pressure:
            for aid, wv in list(self.suspended_webviews.items()):
                if wv and getattr(wv, "_runtime_mode", "") != RUNTIME_WARM_NOTIFY:
                    try:
                        wv.apply_runtime_mode(RUNTIME_WARM_NOTIFY)
                    except Exception:
                        pass
        self._refresh_default_status()

    def _enforce_background_low_memory(self) -> None:
        """对所有非当前账号补设 WebView2 Low 内存目标（节流，避免整机卡顿）。"""
        now = time.time()
        last = float(getattr(self, "_enforce_low_mem_last_at", 0.0) or 0.0)
        if last and (now - last) < float(MEMORY_ENFORCE_LOW_MEM_MIN_SEC):
            if not getattr(self, "_memory_pressure", False):
                return
        self._enforce_low_mem_last_at = now
        cur = self.current_account_id
        for aid, wv in list(self.web_views.items()):
            if not wv or aid == cur:
                continue
            try:
                wv._reapply_runtime_memory_profile()
            except Exception:
                pass
        for aid, wv in list(self.suspended_webviews.items()):
            if not wv:
                continue
            try:
                wv._reapply_runtime_memory_profile()
            except Exception:
                pass

    def _apply_memory_tiers(self) -> None:
        """分级内存：热账号保持连接；冷账号 Low + 停重扫描（按在线数自适应闲置门槛）。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        cur = self.current_account_id
        now = time.time()
        online = max(1, len(self._loaded_account_ids()))
        idle_need = _adaptive_idle_sec_for_online(online)
        hot_ids: Set[int] = set()
        if cur is not None:
            hot_ids.add(int(cur))
        ranked: List[Tuple[float, int]] = []
        for aid in self._loaded_account_ids():
            meta = self.webview_pool.get(int(aid)) or {}
            ranked.append((float(meta.get("last_used", 0.0) or 0.0), int(aid)))
        ranked.sort(reverse=True)
        for _, aid in ranked[: int(MEMORY_TIER_HOT_COUNT)]:
            hot_ids.add(aid)

        for aid, wv in list(self.web_views.items()) + list(
            self.suspended_webviews.items()
        ):
            if not wv or not getattr(wv, "is_valid", False):
                continue
            iid = int(aid)
            if iid == cur:
                continue
            meta = self.webview_pool.get(iid) or {}
            last_used = float(meta.get("last_used", now) or now)
            idle_sec = max(0.0, now - last_used)
            is_hot = iid in hot_ids
            try:
                wv.apply_runtime_mode(RUNTIME_WARM_NOTIFY)
                if not is_hot:
                    wv.apply_memory_profile(False)
                    if idle_sec >= idle_need:
                        self._maybe_trim_renderer_cache(wv, iid)
            except Exception:
                pass

    def _maybe_trim_renderer_cache(self, web_view: TeamsWebView, account_id: int) -> None:
        """冷账号周期性停重扫描并请求 Chromium 降压（不冻结、不重载）。"""
        aid = int(account_id)
        now = time.time()
        last = float(self._memory_tier_last_trim.get(aid, 0.0) or 0.0)
        if last and (now - last) < float(MEMORY_RENDERER_TRIM_INTERVAL_SEC):
            return
        self._memory_tier_last_trim[aid] = now
        try:
            web_view.apply_memory_profile(False)
        except Exception:
            pass
        page = web_view.page() if web_view else None
        if not page:
            return
        page.runJavaScript(
            "(function(){"
            "try{if(window.__teamsPauseHeavyWatchers)window.__teamsPauseHeavyWatchers();}"
            "catch(e){}"
            "})();"
        )

    def _run_memory_guard(self) -> None:
        """后台采集内存统计，避免 tasklist 阻塞 UI 主线程。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        if getattr(self, "_memory_guard_running", False):
            return
        self._memory_guard_running = True

        def _work() -> None:
            try:
                free_mb = _query_system_free_memory_mb()
                used_mb = _query_teamsx_used_memory_mb()
                wv2_count, wv2_mb = _query_webview2_process_stats()
            except Exception:
                free_mb, used_mb, wv2_count, wv2_mb = -1, 0, 0, 0
            # 通过信号回到主线程（跨线程安全），不要在子线程直接动 UI
            try:
                self._memoryStatsReady.emit(
                    int(free_mb), int(used_mb), int(wv2_count), int(wv2_mb)
                )
            except Exception:
                pass

        threading.Thread(target=_work, daemon=True, name="teamsx-mem-guard").start()

    @pyqtSlot(int, int, int, int)
    def _on_memory_stats_ready(
        self, free_mb: int, used_mb: int, wv2_count: int, wv2_mb: int
    ) -> None:
        self._memory_guard_running = False
        self._apply_memory_guard_stats(free_mb, used_mb, (wv2_count, wv2_mb))

    def _run_lightweight_memory_probe(self) -> None:
        """轻量探测：更新可用内存、压力分级，并驱动智能内存控制器。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        free_mb = _query_system_free_memory_mb()
        if free_mb >= 0:
            self._memory_guard_last_free_mb = free_mb
        self._update_low_memory_state(free_mb)
        self._update_memory_controller_state()
        self._maybe_schedule_adaptive_recycle()
        self._refresh_default_status()

    def _record_memory_sample(
        self,
        now: float,
        free_mb: int,
        used_mb: int,
        wv2_mb: int,
        wv2_count: int,
    ) -> None:
        samples = getattr(self, "_memory_ctrl_samples", None)
        if samples is None:
            self._memory_ctrl_samples = deque()
            samples = self._memory_ctrl_samples
        if free_mb < 0:
            return
        samples.append(
            (float(now), int(free_mb), int(used_mb), int(wv2_mb), int(wv2_count))
        )
        _memory_ctrl_prune_samples(
            samples, now=now, window_sec=float(MEMORY_CTRL_SAMPLE_WINDOW_SEC)
        )

    def _compute_memory_trends(self) -> Tuple[float, float]:
        samples = getattr(self, "_memory_ctrl_samples", None)
        if not samples:
            return 0.0, 0.0
        return _memory_ctrl_compute_trends(
            samples,
            now=time.time(),
            window_sec=float(MEMORY_CTRL_TREND_WINDOW_SEC),
        )

    def _dynamic_recycle_idle_sec(self) -> float:
        """按压力动态调整账号闲置门槛（越危险越短）。"""
        level = str(getattr(self, "_adaptive_recycle_pressure", "ok") or "ok")
        online = max(1, len(self._loaded_account_ids()))
        base = _adaptive_idle_sec_for_online(online)
        if level == "critical":
            return float(MEMORY_CTRL_CRITICAL_IDLE_SEC)
        if level == "heavy":
            return float(MEMORY_CTRL_HEAVY_IDLE_SEC)
        if level == "medium":
            return float(MEMORY_CTRL_MEDIUM_IDLE_SEC)
        if level == "light":
            return min(base, 180.0)
        return base

    def _memory_ctrl_recycle_cooldown_sec(self, idle_need: float) -> float:
        level = str(getattr(self, "_adaptive_recycle_pressure", "ok") or "ok")
        if level == "critical":
            return max(8.0, float(idle_need) * 0.35)
        if level in ("heavy", "medium"):
            return max(20.0, float(idle_need) * 0.5)
        return max(30.0, float(idle_need) * 0.5)

    def _is_loading_phase_active(self) -> bool:
        """启动/加载风暴：有账号正在加载，或刚发生渲染进程激增。

        此阶段系统可用内存的下坠是加载本身造成的，不是泄漏，趋势信号无意义。
        """
        if time.time() < float(
            getattr(self, "_adaptive_recycle_storm_until", 0.0) or 0.0
        ):
            return True
        for wv in list(self.web_views.values()) + list(
            self.suspended_webviews.values()
        ):
            if wv and getattr(wv, "is_loading", False):
                return True
        return False

    def _trend_window_span_sec(self) -> float:
        samples = getattr(self, "_memory_ctrl_samples", None)
        if not samples or len(samples) < 2:
            return 0.0
        return float(samples[-1][0]) - float(samples[0][0])

    def _update_memory_controller_state(self) -> Dict[str, object]:
        """采样 + 趋势 + 压力分 + 建议动作 + 下次检查间隔。"""
        now = time.time()
        free_mb = int(getattr(self, "_memory_guard_last_free_mb", -1))
        used_mb = int(getattr(self, "_memory_guard_last_used_mb", 0) or 0)
        wv2_mb = int(getattr(self, "_memory_guard_wv2_mb", 0) or 0)
        wv2_count = int(getattr(self, "_memory_guard_wv2_count", 0) or 0)
        online = max(1, len(self._loaded_account_ids()))

        self._record_memory_sample(now, free_mb, used_mb, wv2_mb, wv2_count)

        # 趋势仅在“非加载期 + 样本跨度足够长”时才可信，否则启动爬坡会污染趋势
        loading = self._is_loading_phase_active()
        span_ok = self._trend_window_span_sec() >= 60.0
        if loading or not span_ok:
            free_trend, used_trend = 0.0, 0.0
            trend_trusted = False
        else:
            free_trend, used_trend = self._compute_memory_trends()
            trend_trusted = True

        level = self._adaptive_recycle_pressure_level(free_mb, used_mb, online)
        self._adaptive_recycle_pressure = level

        score = 0
        if free_mb >= 0:
            if free_mb < int(ADAPTIVE_RECYCLE_FREE_HEAVY_MB):
                score += 40
            elif free_mb < int(ADAPTIVE_RECYCLE_FREE_MEDIUM_MB):
                score += 30
            elif free_mb < int(ADAPTIVE_RECYCLE_FREE_LIGHT_MB):
                score += 15
            elif free_mb < int(ADAPTIVE_RECYCLE_FREE_OK_MB):
                score += 5
        if trend_trusted:
            if free_trend < -float(MEMORY_CTRL_FREE_FALL_MB_PER_MIN):
                score += 25
            elif free_trend < -40.0:
                score += 12
            if used_trend > float(MEMORY_CTRL_USED_RISE_MB_PER_MIN):
                score += 20
            elif used_trend > 60.0:
                score += 10

        reason_parts: List[str] = []
        action = "none"
        # 绝对可用内存优先：无论是否加载期，低于红线都要回收
        if level == "critical" or (
            free_mb >= 0 and free_mb < int(ADAPTIVE_RECYCLE_FREE_HEAVY_MB)
        ):
            action = "urgent_batch"
            reason_parts.append("free_critical")
        elif level == "heavy":
            action = "urgent_batch"
            reason_parts.append("free_low")
        elif level == "medium":
            action = "trim_batch"
            reason_parts.append("free_low")
        elif trend_trusted and (
            free_trend < -150.0
            or (
                free_trend < -float(MEMORY_CTRL_FREE_FALL_MB_PER_MIN)
                and used_trend > float(MEMORY_CTRL_USED_RISE_MB_PER_MIN)
            )
        ):
            # 非加载期的真实持续增长：提前干预
            action = "trim_batch"
            reason_parts.append("trend_rising")
        elif level == "light":
            action = "trim_one"
            reason_parts.append("free_light")
        else:
            action = "none"
            reason_parts.append("loading" if loading else "stable")

        if trend_trusted and free_trend < -float(MEMORY_CTRL_FREE_FALL_MB_PER_MIN):
            reason_parts.append("free_falling")
        if trend_trusted and used_trend > float(MEMORY_CTRL_USED_RISE_MB_PER_MIN):
            reason_parts.append("used_rising")
        if loading:
            reason_parts.append("loading")

        batch_map = {
            "none": 0,
            "trim_one": 1,
            "trim_batch": 3,
            "urgent_batch": 5,
        }
        batch = int(batch_map.get(action, 0))
        if level == "heavy":
            batch = max(batch, 5)
        if level == "critical":
            batch = 5

        candidates = 0
        if batch > 0 and not self._adaptive_recycle_should_pause():
            if MEMORY_GROOM_ENABLE:
                candidates = len(self._get_groom_candidates(batch))
            else:
                candidates = len(self._get_recycle_candidates(batch))

        # 没有可回收候选时不谎报紧急（启动期账号都在加载、未到闲置门槛）
        if candidates == 0 and action != "none":
            action = "none"
            if "no_candidates" not in reason_parts:
                reason_parts.append("no_candidates")

        if action == "none":
            delay = float(MEMORY_CTRL_SCHED_MAX_SEC if not loading else MEMORY_CTRL_SCHED_MIN_SEC * 2)
        elif action == "urgent_batch":
            delay = float(MEMORY_CTRL_SCHED_MIN_SEC)
        elif getattr(self, "_memory_ctrl_last_recycle_effective", False) and level not in (
            "heavy",
            "critical",
        ):
            delay = float(MEMORY_CTRL_SCHED_MAX_SEC)
        elif getattr(self, "_memory_ctrl_last_recycle_ineffective", False) and level in (
            "heavy",
            "critical",
            "medium",
        ):
            delay = float(MEMORY_CTRL_SCHED_MIN_SEC)
        else:
            delay = (
                float(MEMORY_CTRL_SCHED_MIN_SEC) + float(MEMORY_CTRL_SCHED_MAX_SEC)
            ) / 2.0

        state: Dict[str, object] = {
            "level": level,
            "free_mb": free_mb,
            "used_mb": used_mb,
            "free_trend": free_trend,
            "used_trend": used_trend,
            "trend_trusted": trend_trusted,
            "loading": loading,
            "pressure_score": score,
            "action": action,
            "batch": batch,
            "candidates": candidates,
            "reason": "+".join(reason_parts) if reason_parts else "ok",
            "next_delay_sec": delay,
        }
        self._memory_ctrl_state = state
        self._adaptive_recycle_next_interval_sec = delay

        # 只在“真正要回收”或“等级变化”时打印，避免启动期每 5 秒刷屏
        prev_level = str(getattr(self, "_memory_ctrl_last_logged_level", "ok") or "ok")
        should_log = (action != "none" and candidates > 0) or level != prev_level
        if should_log:
            trend_txt = (
                f"trend_free={free_trend:+.0f} trend_used={used_trend:+.0f}MB/min"
                if trend_trusted
                else ("trend=加载中" if loading else "trend=采样中")
            )
            print(
                f"[内存控制] level={level} free={free_mb}MB {trend_txt} "
                f"action={action} batch={batch} candidates={candidates} "
                f"reason={state['reason']} next={delay:.0f}s"
            )
            self._memory_ctrl_last_logged_level = level
        return state

    def _adaptive_recycle_pressure_level(
        self, free_mb: int, used_mb: int, online: int
    ) -> str:
        if free_mb < 0:
            return "ok"
        target_high = _adaptive_target_high_mb(online)
        if free_mb < int(ADAPTIVE_RECYCLE_FREE_HEAVY_MB):
            return "critical"
        if free_mb < int(ADAPTIVE_RECYCLE_FREE_MEDIUM_MB):
            return "heavy"
        if free_mb < int(ADAPTIVE_RECYCLE_FREE_LIGHT_MB):
            return "medium"
        if free_mb < int(ADAPTIVE_RECYCLE_FREE_OK_MB) or (
            used_mb > 0 and used_mb > target_high
        ):
            return "light"
        return "ok"

    def _adaptive_recycle_batch_size(self, level: str) -> int:
        return {
            "light": 2,
            "medium": 3,
            "heavy": 5,
            "critical": 5,
        }.get(level, 0)

    def _adaptive_recycle_should_pause(self) -> bool:
        now = time.time()
        if self._has_active_call():
            return True
        if getattr(self, "_memory_groom_active", False):
            return True
        free_mb = int(getattr(self, "_memory_guard_last_free_mb", -1))
        level = str(getattr(self, "_adaptive_recycle_pressure", "ok") or "ok")
        storm_until = float(
            getattr(self, "_adaptive_recycle_storm_until", 0.0) or 0.0
        )
        if now < storm_until:
            # 加载风暴时：系统仍充裕则暂停；低内存时允许回收已加载完成的后台账号
            if free_mb < 0 or free_mb >= int(ADAPTIVE_RECYCLE_FREE_MEDIUM_MB):
                return True
        last_switch = float(getattr(self, "_last_account_switch_at", 0.0) or 0.0)
        quiet_sec = float(ADAPTIVE_RECYCLE_SWITCH_QUIET_SEC)
        if level in ("heavy", "critical"):
            quiet_sec = 3.0
        if last_switch and (now - last_switch) < quiet_sec:
            return True
        return False

    def _estimate_account_ws_mb(self, web_view: TeamsWebView) -> int:
        wv2 = getattr(web_view, "_wv2_widget", None)
        pid = _query_widget_process_id(wv2)
        if pid > 0:
            ws = _query_process_working_set_mb(pid)
            if ws > 0:
                return ws
        online = max(1, len(self._loaded_account_ids()))
        total = int(getattr(self, "_memory_guard_wv2_mb", 0) or 0)
        if total > 0:
            return int(total / online)
        return 0

    def _is_recycle_eligible_account(
        self, account_id: int, web_view: TeamsWebView, *, now: float
    ) -> bool:
        aid = int(account_id)
        cur = self.current_account_id
        if cur is not None and aid == int(cur):
            return False
        if not web_view or not getattr(web_view, "is_valid", False):
            return False
        if getattr(web_view, "is_loading", False) or getattr(
            web_view, "_login_active", False
        ):
            return False
        online = max(1, len(self._loaded_account_ids()))
        idle_need = self._dynamic_recycle_idle_sec()
        meta = self.webview_pool.get(aid) or {}
        last_used = float(meta.get("last_used", 0.0) or 0.0)
        if last_used and (now - last_used) < idle_need:
            return False
        last_recycle = float(
            self._adaptive_recycle_account_last.get(aid, 0.0) or 0.0
        )
        cooldown = self._memory_ctrl_recycle_cooldown_sec(idle_need)
        if last_recycle and (now - last_recycle) < cooldown:
            return False
        ws_mb = self._estimate_account_ws_mb(web_view)
        free_mb = int(getattr(self, "_memory_guard_last_free_mb", -1))
        pressure = getattr(self, "_adaptive_recycle_pressure", "ok")
        if ws_mb <= 0:
            return pressure in ("medium", "heavy", "critical")
        if ws_mb < int(ADAPTIVE_RECYCLE_ACCOUNT_WS_MB):
            return pressure in ("heavy", "critical")
        return True

    def _get_recycle_candidates(self, limit: int) -> List[int]:
        now = time.time()
        ranked: List[Tuple[float, float, int]] = []
        for aid in self._loaded_account_ids():
            wv = self._get_webview_for_account(int(aid))
            if not self._is_recycle_eligible_account(int(aid), wv, now=now):
                continue
            meta = self.webview_pool.get(int(aid)) or {}
            use_count = int(meta.get("use_count", 0))
            last_used = float(meta.get("last_used", now) or now)
            ws_mb = self._estimate_account_ws_mb(wv) if wv else 0
            ranked.append((use_count, last_used, -ws_mb, int(aid)))
        ranked.sort(key=lambda x: (x[0], x[1], x[2]))
        return [aid for _, _, _, aid in ranked[: max(0, int(limit))]]

    def _memory_groom_user_quiet(self) -> bool:
        last_switch = float(getattr(self, "_last_account_switch_at", 0.0) or 0.0)
        if last_switch and (time.time() - last_switch) < float(
            MEMORY_GROOM_USER_QUIET_SEC
        ):
            return False
        return True

    def _is_groom_eligible_account(
        self, account_id: int, web_view: TeamsWebView, *, now: float
    ) -> bool:
        aid = int(account_id)
        cur = self.current_account_id
        if cur is not None and aid == int(cur):
            return False
        if not web_view or not getattr(web_view, "is_valid", False):
            return False
        if getattr(web_view, "is_loading", False) or getattr(
            web_view, "_login_active", False
        ):
            return False
        last_groom = float(
            self._memory_groom_account_last.get(aid, 0.0) or 0.0
        )
        if last_groom and (now - last_groom) < float(
            MEMORY_GROOM_ACCOUNT_COOLDOWN_SEC
        ):
            return False
        return True

    def _get_groom_candidates(self, limit: int) -> List[int]:
        """轮换挑选后台账号（模拟手动点一遍，不要求长闲置）。"""
        now = time.time()
        loaded = [int(a) for a in self._loaded_account_ids()]
        if not loaded:
            return []
        start = int(getattr(self, "_memory_groom_rr_index", 0) or 0) % max(
            1, len(loaded)
        )
        ordered = loaded[start:] + loaded[:start]
        picked: List[int] = []
        for aid in ordered:
            wv = self._get_webview_for_account(aid)
            if not self._is_groom_eligible_account(aid, wv, now=now):
                continue
            picked.append(aid)
            if len(picked) >= max(1, int(limit)):
                break
        if picked:
            self._memory_groom_rr_index = (start + len(picked)) % max(1, len(loaded))
        return picked

    def _start_groom_account(self, account_id: int, *, aggressive: bool = False) -> bool:
        """静默整理：在停车区脉冲 Normal→Low，不切 stack、不闪屏。"""
        if not MEMORY_GROOM_ENABLE:
            return False
        if getattr(self, "_memory_groom_active", False):
            return False
        if self._has_active_call():
            return False
        aid = int(account_id)
        wv = self._get_webview_for_account(aid)
        if not wv or not self._is_groom_eligible_account(
            aid, wv, now=time.time()
        ):
            return False
        self._memory_groom_active = True
        self._memory_groom_target_aid = aid
        self._memory_groom_restore_id = None
        self._memory_groom_aggressive = bool(aggressive)
        try:
            self._park_webview_background(wv)
            wv.apply_memory_profile(True, quiet=True)
        except Exception as e:
            self._memory_groom_active = False
            self._memory_groom_target_aid = None
            self._memory_groom_aggressive = False
            print(f"[内存整理] 账号 {aid} 静默整理失败: {e}")
            return False
        QTimer.singleShot(
            int(MEMORY_GROOM_DWELL_MS),
            lambda a=aid: self._finish_groom_account(a),
        )
        return True

    def _finish_groom_account(self, account_id: int) -> None:
        aid = int(account_id)
        try:
            wv = self._get_webview_for_account(aid)
            if wv and getattr(wv, "is_valid", False):
                try:
                    wv.apply_memory_profile(False, quiet=True)
                except Exception:
                    pass
                self._park_webview_background(wv)
                if ADAPTIVE_RECYCLE_ENABLE_WS_TRIM:
                    try:
                        from teamsx.engine.webview2 import empty_working_set_for_widget

                        wv2 = getattr(wv, "_wv2_widget", None)
                        if wv2 is not None:
                            empty_working_set_for_widget(wv2)
                    except Exception:
                        pass
                if getattr(self, "_memory_groom_aggressive", False):
                    self._maybe_trim_renderer_cache(wv, aid)
            self._memory_groom_account_last[aid] = time.time()
            remark = self._account_remark_for_notify(aid)
            print(f"[内存整理] 已静默整理后台账号「{remark}」(id={aid})")
        finally:
            self._memory_groom_active = False
            self._memory_groom_target_aid = None
            self._memory_groom_restore_id = None
            self._memory_groom_aggressive = False
            cont = getattr(self, "_memory_groom_batch_continue", None)
            if cont is not None:
                self._memory_groom_batch_continue = None
                try:
                    cont()
                except Exception:
                    pass

    def _maybe_memory_groom_maintenance(self) -> None:
        """常驻轮换：WS 偏高时自动模拟点后台账号（不靠用户手动）。"""
        if (
            not MEMORY_GROOM_ENABLE
            or self.is_closing
            or getattr(self, "_app_locked", False)
            or getattr(self, "_memory_groom_active", False)
            or getattr(self, "_adaptive_recycle_batch_pending", 0) > 0
        ):
            return
        if not self._memory_groom_user_quiet() or self._adaptive_recycle_should_pause():
            return
        used_mb = int(getattr(self, "_memory_guard_last_used_mb", 0) or 0)
        free_mb = int(getattr(self, "_memory_guard_last_free_mb", -1))
        if used_mb < int(MEMORY_GROOM_WS_TRIGGER_MB) and (
            free_mb < 0 or free_mb >= int(ADAPTIVE_RECYCLE_FREE_LIGHT_MB)
        ):
            return
        candidates = self._get_groom_candidates(1)
        if not candidates:
            return
        self._start_groom_account(candidates[0], aggressive=False)

    def _recycle_account_working_set(
        self, account_id: int, *, aggressive: bool = False
    ) -> bool:
        """压力触发时走「模拟点账号」路径，不再只做静默 Low。"""
        if MEMORY_GROOM_ENABLE:
            return self._start_groom_account(account_id, aggressive=aggressive)
        aid = int(account_id)
        wv = self._get_webview_for_account(aid)
        if not wv:
            return False
        try:
            wv.apply_runtime_mode(RUNTIME_WARM_NOTIFY)
            wv.apply_memory_profile(False)
        except Exception:
            pass
        if ADAPTIVE_RECYCLE_ENABLE_WS_TRIM:
            try:
                from teamsx.engine.webview2 import empty_working_set_for_widget

                wv2 = getattr(wv, "_wv2_widget", None)
                if wv2 is not None:
                    empty_working_set_for_widget(wv2)
            except Exception:
                pass
        if aggressive:
            self._maybe_trim_renderer_cache(wv, aid)
        self._adaptive_recycle_account_last[aid] = time.time()
        remark = self._account_remark_for_notify(aid)
        print(f"[内存回收] 已回收后台账号「{remark}」(id={aid}) 工作集")
        return True

    def _update_low_memory_state(self, free_mb: int) -> None:
        """更新压力分级；可选极端 OOM 卸载（默认关闭）。"""
        online = max(1, len(self._loaded_account_ids()))
        used_mb = int(getattr(self, "_memory_guard_last_used_mb", 0) or 0)
        level = self._adaptive_recycle_pressure_level(free_mb, used_mb, online)
        self._adaptive_recycle_pressure = level
        self._memory_emergency_active = level in ("heavy", "critical")
        if free_mb >= int(ADAPTIVE_RECYCLE_FREE_OK_MB):
            self._low_memory_since = 0.0
            self._oom_unload_since = 0.0
            return
        now = time.time()
        if not ENABLE_AUTO_UNLOAD_ON_OOM:
            return
        if free_mb >= int(AUTO_UNLOAD_OOM_FREE_MB):
            self._oom_unload_since = 0.0
            return
        if not self._oom_unload_since:
            self._oom_unload_since = now
            return
        if (now - self._oom_unload_since) < float(AUTO_UNLOAD_OOM_SUSTAIN_SEC):
            return
        self._maybe_emergency_unload_one()

    def _maybe_emergency_unload_one(self) -> None:
        """仅当 ENABLE_AUTO_UNLOAD_ON_OOM 开启时的最后手段。"""
        if not ENABLE_AUTO_UNLOAD_ON_OOM:
            return
        loaded = self._loaded_account_ids()
        if len(loaded) <= 1:
            return
        exclude: Set[int] = set()
        if self.current_account_id is not None:
            exclude.add(int(self.current_account_id))
        victim = self.webview_pool.get_lfu_lru_account(exclude)
        if victim is None:
            return
        victim = int(victim)
        print(f"[内存保护] 极端 OOM，卸载最不活跃账号 id={victim}")
        try:
            self.unload_webview(victim)
        except Exception as e:
            print(f"[内存保护] 卸载失败: {e}")
        self._oom_unload_since = time.time()

    def _maybe_schedule_adaptive_recycle(self) -> None:
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        if getattr(self, "_adaptive_recycle_batch_pending", 0) > 0:
            return
        if getattr(self, "_memory_groom_active", False):
            return

        state = dict(getattr(self, "_memory_ctrl_state", {}) or {})
        action = str(state.get("action", "") or "")
        level = str(
            state.get("level")
            or getattr(self, "_adaptive_recycle_pressure", "ok")
            or "ok"
        )
        # 遵循控制器决策：none（含无候选/加载期）直接不动
        if action in ("", "none"):
            return

        batch = int(state.get("batch", 0) or 0)
        if batch <= 0:
            return
        if int(state.get("candidates", 0) or 0) <= 0:
            return

        now = time.time()
        last = float(getattr(self, "_adaptive_recycle_last_at", 0.0) or 0.0)
        interval = float(
            state.get("next_delay_sec")
            or getattr(self, "_adaptive_recycle_next_interval_sec", 30.0)
            or 30.0
        )
        urgent = action == "urgent_batch" or int(state.get("pressure_score", 0) or 0) >= 50
        if last and (now - last) < interval and not urgent:
            return
        if self._adaptive_recycle_should_pause():
            return

        self._adaptive_recycle_batch_pending = batch
        QTimer.singleShot(0, self._adaptive_recycle_step)

    def _adaptive_recycle_step(self) -> None:
        """分批整理后台账号（模拟手动点一遍，不卸载、不冻结）。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            self._adaptive_recycle_batch_pending = 0
            return
        if getattr(self, "_memory_groom_active", False):
            return
        if self._adaptive_recycle_should_pause():
            self._adaptive_recycle_batch_pending = 0
            self._adaptive_recycle_next_interval_sec = min(
                float(ADAPTIVE_RECYCLE_DECISION_MAX_SEC),
                float(getattr(self, "_adaptive_recycle_next_interval_sec", 30.0))
                + 10.0,
            )
            return

        pending = int(getattr(self, "_adaptive_recycle_batch_pending", 0) or 0)
        if pending <= 0:
            return

        free_before = int(getattr(self, "_memory_guard_last_free_mb", -1))
        level = getattr(self, "_adaptive_recycle_pressure", "ok")
        if MEMORY_GROOM_ENABLE:
            candidates = self._get_groom_candidates(1)
        else:
            candidates = self._get_recycle_candidates(1)
        if not candidates:
            self._adaptive_recycle_batch_pending = 0
            self._adaptive_recycle_last_at = time.time()
            self._adaptive_recycle_next_interval_sec = float(
                MEMORY_CTRL_SCHED_MIN_SEC
                if level in ("heavy", "critical", "medium")
                else ADAPTIVE_RECYCLE_DECISION_MAX_SEC
            )
            return

        aggressive = level in ("heavy", "critical")
        pending_after = max(0, pending - 1)

        def _after_groom() -> None:
            self._adaptive_recycle_batch_pending = pending_after
            free_after = _query_system_free_memory_mb()
            if free_after >= 0:
                self._memory_guard_last_free_mb = free_after
            improved = (
                free_before >= 0
                and free_after >= 0
                and (free_after - free_before) >= int(MEMORY_CTRL_RECYCLE_EFFECTIVE_MB)
            )
            self._memory_ctrl_last_recycle_effective = improved
            self._memory_ctrl_last_recycle_ineffective = (
                not improved and level in ("heavy", "critical", "medium")
            )
            if improved:
                self._adaptive_recycle_next_interval_sec = float(
                    MEMORY_CTRL_SCHED_MAX_SEC
                )
            else:
                self._adaptive_recycle_next_interval_sec = float(
                    MEMORY_CTRL_SCHED_MIN_SEC
                    if level in ("heavy", "critical")
                    else ADAPTIVE_RECYCLE_DECISION_MIN_SEC
                )
            if self._adaptive_recycle_batch_pending > 0:
                wait_ms = max(
                    500, int(MEMORY_GROOM_STEP_WAIT_SEC) * 1000
                )
                QTimer.singleShot(wait_ms, self._adaptive_recycle_step)
                return
            self._adaptive_recycle_last_at = time.time()
            self._refresh_memory_hint()
            self._refresh_default_status()

        if MEMORY_GROOM_ENABLE:
            self._memory_groom_batch_continue = _after_groom
            if not self._start_groom_account(candidates[0], aggressive=aggressive):
                self._memory_groom_batch_continue = None
                _after_groom()
            return

        self._recycle_account_working_set(candidates[0], aggressive=aggressive)
        self._adaptive_recycle_batch_pending = pending_after

        free_after = _query_system_free_memory_mb()
        if free_after >= 0:
            self._memory_guard_last_free_mb = free_after
        improved = (
            free_before >= 0
            and free_after >= 0
            and (free_after - free_before) >= int(MEMORY_CTRL_RECYCLE_EFFECTIVE_MB)
        )
        self._memory_ctrl_last_recycle_effective = improved
        self._memory_ctrl_last_recycle_ineffective = (
            not improved and level in ("heavy", "critical", "medium")
        )
        if improved:
            self._adaptive_recycle_next_interval_sec = float(
                MEMORY_CTRL_SCHED_MAX_SEC
            )
        else:
            self._adaptive_recycle_next_interval_sec = float(
                MEMORY_CTRL_SCHED_MIN_SEC
                if level in ("heavy", "critical")
                else ADAPTIVE_RECYCLE_DECISION_MIN_SEC
            )

        if self._adaptive_recycle_batch_pending > 0:
            wait_ms = max(500, int(ADAPTIVE_RECYCLE_STEP_WAIT_SEC) * 1000)
            QTimer.singleShot(wait_ms, self._adaptive_recycle_step)
            return

        self._adaptive_recycle_last_at = time.time()
        self._refresh_memory_hint()
        self._refresh_default_status()

    def start_daily_cache_cleanup(self):
        """每天 7:00 后自动清理一次磁盘缓存（无弹窗，保留登录态）。"""
        try:
            self._check_daily_cache_clean()
            self._daily_cache_timer = QTimer(self)
            self._daily_cache_timer.timeout.connect(self._check_daily_cache_clean)
            self._daily_cache_timer.start(60_000)
        except Exception as e:
            print(f"启动每日缓存清理失败: {e}")

    def _cache_clean_was_today(self) -> bool:
        return (self.db.get_setting("cache_clean_last_date") or "") == datetime.now().date().isoformat()

    def _mark_cache_clean_today(self):
        self.db.set_setting("cache_clean_last_date", datetime.now().date().isoformat())

    def _check_daily_cache_clean(self):
        if self._cache_clean_running or getattr(self, "_app_locked", False) or self.is_closing:
            return
        if self._cache_clean_was_today():
            return
        if datetime.now().hour < DAILY_CACHE_CLEAN_HOUR:
            return
        self.clean_unused_cache(manual=False)

    def cleanup_idle_webviews(self):
        """定时内存维护：清理已卸载账号的角标定时器等。"""
        if self.is_closing or getattr(self, "_app_locked", False):
            return
        try:
            loaded_ids = set(self._loaded_account_ids())
            for aid in list(self._badge_debounce_timers.keys()):
                if aid not in loaded_ids:
                    timer = self._badge_debounce_timers.pop(aid, None)
                    if timer:
                        timer.stop()
                        timer.deleteLater()
                    self._badge_pending.pop(aid, None)
        except Exception as e:
            print(f"内存维护: {e}")

    def _schedule_trim_suspended_pool(self) -> None:
        if getattr(self, "_trim_suspended_scheduled", False):
            return
        if len(self.suspended_webviews) <= self._effective_suspended_limit():
            return
        self._trim_suspended_scheduled = True
        QTimer.singleShot(80, self._trim_suspended_pool_step)

    def _trim_suspended_pool_step(self) -> None:
        self._trim_suspended_scheduled = False
        if self.is_closing:
            return
        limit = self._effective_suspended_limit()
        if len(self.suspended_webviews) <= limit:
            return
        exclude: Set[int] = set()
        if self.current_account_id:
            exclude.add(int(self.current_account_id))
        victim = self.webview_pool.get_lfu_lru_account(exclude)
        if victim is None or victim not in self.suspended_webviews:
            victim = None
            oldest_ts = float("inf")
            for aid, wv in self.suspended_webviews.items():
                if aid in exclude:
                    continue
                ts = getattr(wv, "_suspended_at", 0.0) or 0.0
                if ts < oldest_ts:
                    oldest_ts = ts
                    victim = aid
        if victim is not None:
            try:
                self.unload_webview(int(victim))
            except Exception:
                pass
        if len(self.suspended_webviews) > self._effective_suspended_limit():
            if getattr(self, "_memory_emergency_active", False):
                QTimer.singleShot(80, self._trim_suspended_pool_step)
            else:
                self._schedule_trim_suspended_pool()

    def suspend_webview(self, account_id: int):
        """挂起账号：保留 Profile/登录态，释放活跃槽位，不销毁 WebView"""
        if account_id not in self.web_views:
            return
        web_view = self.web_views.pop(account_id)
        # WebView2-only：休眠时保留 LFU/LRU 元数据（不要 remove）
        self.webview_pool.deactivate(account_id)
        if not web_view:
            return
        try:
            was_foreground = (
                hasattr(self, "stack_widget")
                and self.stack_widget
                and self.stack_widget.currentWidget() is web_view
            )
            index = self.stack_widget.indexOf(web_view)
            if index >= 0:
                self.stack_widget.removeWidget(web_view)
            web_view.setParent(self._webview_park)
            self._webview_park_layout.addWidget(web_view)
            web_view.hide()
            web_view._suspended_at = time.time()
            self.suspended_webviews[account_id] = web_view
            try:
                web_view.apply_runtime_mode(RUNTIME_WARM_NOTIFY)
            except Exception:
                pass
            if ENABLE_BACKGROUND_FREEZE:
                try:
                    web_view.suspend_page()
                except Exception:
                    pass
            self._refresh_account_dot(account_id)
            if self.current_account_id == account_id:
                self.current_account_id = None
            if was_foreground and self.stack_widget.count() > 0:
                # 仅当休眠的正是当前页时才换页，避免后台加载把用户拽回 AI
                self.stack_widget.setCurrentIndex(0)
            print(f"账号 {account_id} 已休眠（登录态保留）")
            self._schedule_trim_suspended_pool()
        except Exception as e:
            print(f"休眠 WebView 失败: {e}")
            self.suspended_webviews[account_id] = web_view

    def _resume_webview(self, account_id: int) -> Optional[TeamsWebView]:
        web_view = self.suspended_webviews.pop(account_id, None)
        if not web_view:
            return None
        self._webview_park_layout.removeWidget(web_view)
        web_view.resume_page()
        web_view.show()
        self.web_views[account_id] = web_view
        self.webview_pool.register(account_id, web_view)
        self.stack_widget.addWidget(web_view)
        self.stack_widget.setCurrentWidget(web_view)
        web_view._host_main = self
        self._refresh_account_dot(account_id)
        QTimer.singleShot(500, web_view._verify_resume_health)
        return web_view

    def clear_teams_load_failures(self):
        self._teams_load_failures = 0

    def register_teams_load_failure(self, account_id: int):
        if self.is_closing or self._teams_recover_running:
            return
        self._teams_load_failures += 1
        print(f"Teams 加载失败计数: {self._teams_load_failures} (账号 {account_id})")
        if self._teams_load_failures >= 2:
            self._teams_load_failures = 0
            self.request_teams_recovery("连续加载失败")

    def request_teams_recovery(self, reason: str = ""):
        if self.is_closing or self._teams_recover_running:
            return
        now = time.time()
        if self._last_teams_recover_at and (
            now - self._last_teams_recover_at
        ) < TEAMS_ENGINE_RECOVER_COOLDOWN_SEC:
            wv = self._get_webview(self.current_account_id) if self.current_account_id else None
            if wv and wv.is_valid:
                wv.hard_reload_teams()
            return
        self._last_teams_recover_at = now
        if reason:
            print(f"触发 Teams 全局恢复: {reason}")
        QTimer.singleShot(200, self.recover_teams_engine)

    def recover_teams_engine(self):
        """卸载全部 Teams WebView 后重建当前账号（修复 Chromium 全局白屏）。"""
        if self.is_closing or self._teams_recover_running:
            return
        self._teams_recover_running = True
        keep_id = self.current_account_id
        self.update_status("正在修复 Teams 页面，请稍候…")
        try:
            for aid in list(self.web_views.keys()) + list(self.suspended_webviews.keys()):
                self.unload_webview(aid)
            self._teams_load_failures = 0
            gc.collect()
        except Exception as e:
            print(f"Teams 全局恢复失败: {e}")
            self._teams_recover_running = False
            return

        def _finish():
            self._teams_recover_running = False
            if keep_id:
                self.switch_to_account(keep_id)
            self.update_status("Teams 已修复，正在重新加载…")

        QTimer.singleShot(900, _finish)

    def _enforce_webview_limit(self, keep_account_id: int):
        """超过上限时按 LRU 休眠最不活跃账号（非删除）。"""
        self._trim_active_webviews_to_limit(int(keep_account_id))

    def _freeze_sidebar_splitter_width(self) -> None:
        """切换账号列表/分组管理时保持侧栏宽度不变。"""
        sp = getattr(self, "_main_splitter", None)
        if sp is None:
            return
        sizes = sp.sizes()
        if not sizes or sizes[0] <= 0:
            return
        left = int(sizes[0])

        def _restore():
            try:
                total = sp.width()
                if total <= 0:
                    sp.setSizes(sizes)
                    return
                sp.setSizes([left, max(1, total - left)])
            except Exception:
                pass

        QTimer.singleShot(0, _restore)

    def _animate_sidebar_view(self, *, to_group: bool, on_done=None) -> None:
        acc = self.account_list
        panel = self.group_manage_panel
        host = getattr(self, "_sidebar_content_host", None)
        if host is not None:
            host.resize(host.size())

        anim = getattr(self, "_sidebar_view_anim", None)
        if anim is not None and anim.state() == QAbstractAnimation.State.Running:
            anim.stop()

        outgoing = acc if to_group else panel
        incoming = panel if to_group else acc

        if to_group and incoming.isVisible() and not outgoing.isVisible():
            if on_done:
                on_done()
            return
        if not to_group and incoming.isVisible() and not outgoing.isVisible():
            if on_done:
                on_done()
            return

        incoming.setVisible(True)
        incoming.raise_()
        outgoing.setVisible(True)

        out_eff = QGraphicsOpacityEffect(outgoing)
        in_eff = QGraphicsOpacityEffect(incoming)
        outgoing.setGraphicsEffect(out_eff)
        incoming.setGraphicsEffect(in_eff)
        out_eff.setOpacity(1.0)
        in_eff.setOpacity(0.0)

        fade_out = QPropertyAnimation(out_eff, b"opacity", self)
        fade_out.setDuration(GROUP_SIDEBAR_ANIM_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        fade_in = QPropertyAnimation(in_eff, b"opacity", self)
        fade_in.setDuration(GROUP_SIDEBAR_ANIM_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        self._sidebar_view_anim = group
        self._sidebar_view_anim_running = True

        def _finish():
            self._sidebar_view_anim_running = False
            outgoing.setGraphicsEffect(None)
            incoming.setGraphicsEffect(None)
            outgoing.setVisible(not to_group)
            incoming.setVisible(to_group)
            if on_done:
                on_done()

        group.finished.connect(_finish)
        group.start()

    def _open_group_manage_panel(self) -> None:
        self.group_manage_panel.expand()
        self.group_manage_btn.setText("收起")
        self._freeze_sidebar_splitter_width()

        def _done():
            self._freeze_sidebar_splitter_width()

        self._animate_sidebar_view(to_group=True, on_done=_done)

    def _close_group_manage_panel(self) -> None:
        self.group_manage_btn.setText("管理")
        self._freeze_sidebar_splitter_width()

        def _done():
            self.group_manage_panel.setVisible(False)
            self.account_list.setVisible(True)
            self.account_list.raise_()
            self._reload_group_list()
            self._refresh_account_list_display()
            self._freeze_sidebar_splitter_width()

        self._animate_sidebar_view(to_group=False, on_done=_done)

    def manage_groups(self):
        if getattr(self, "_sidebar_view_anim_running", False):
            return
        panel = self.group_manage_panel
        if panel.isVisible():
            panel.collapse()
            return
        self._open_group_manage_panel()

    def _on_group_manage_panel_closed(self):
        if getattr(self, "_sidebar_view_anim_running", False):
            return
        self._close_group_manage_panel()

    def _reload_group_list(self):
        if not hasattr(self, "group_combo"):
            return
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("全部", 0)
        for gid, name in self.db.get_all_groups():
            self.group_combo.addItem(name, gid)
        for i in range(self.group_combo.count()):
            if self.group_combo.itemData(i) == self._current_group_id:
                self.group_combo.setCurrentIndex(i)
                break
        self.group_combo.blockSignals(False)

    def _on_group_combo_changed(self, _index: int):
        self._current_group_id = self.group_combo.currentData() or 0
        self._refresh_account_list_display()

    def refresh_current_view(self):
        """仅刷新当前停留页，不影响其它已加载账号。"""
        if getattr(self, "_app_locked", False):
            return
        if getattr(self, "_lock_teardown_active", False):
            self.update_status("正在释放内存，请稍候…")
            return

        # AI 主界面：只刷新左侧账号列表
        if hasattr(self, "stack_widget") and self.stack_widget.currentIndex() == 0:
            self._refresh_account_list_display()
            self._refresh_default_status()
            self.update_status("已刷新账号列表")
            return

        aid = self.current_account_id
        if not aid:
            self.update_status("当前无已打开的页面")
            return

        wv = self._get_webview_for_account(aid)
        if wv and wv.is_valid:
            remark = ""
            try:
                acc = self.db.get_account(aid)
                if acc:
                    remark = (acc[1] or "").strip()
            except Exception:
                pass
            label = remark or f"账号 {aid}"
            self.update_status(f"正在刷新 {label}…")
            wv.hard_reload_teams()
            return

        # 已选中账号但尚未加载 WebView
        if self.switch_to_account(aid):
            wv = self._get_webview_for_account(aid)
            if wv and wv.is_valid:
                QTimer.singleShot(300, wv.hard_reload_teams)
            return
        self.update_status("刷新失败：无法加载当前账号")

    def _clear_live_webview_disk_cache(self):
        """先让已加载页面释放磁盘缓存锁，再删 profile 内缓存目录。"""
        for wv in self._iter_all_webviews():
            try:
                wv.clear_browser_disk_cache()
            except Exception:
                pass

    def clean_unused_cache(self, *, manual=False):
        """清理全部账号磁盘缓存（后台线程，保留 session 登录数据）。"""
        if self._cache_clean_running:
            if manual:
                QMessageBox.information(self, "提示", "缓存清理正在进行中，请稍候…")
            return

        try:
            accounts = self.db.get_all_accounts()
            if not accounts and manual:
                QMessageBox.information(self, "提示", "暂无账号需要清理")
                return

            self._cache_clean_running = True
            if manual and hasattr(self, "clean_btn"):
                self.clean_btn.setEnabled(False)
            if manual:
                self.update_status("正在清理磁盘缓存…")

            self._clear_live_webview_disk_cache()

            skip_sessions: Set[str] = set()
            skip_caches: Set[str] = set()
            for wv in self._iter_all_webviews():
                try:
                    if getattr(wv, "session_dir", None):
                        skip_sessions.add(os.path.normpath(os.path.abspath(wv.session_dir)))
                    if getattr(wv, "cache_dir", None):
                        skip_caches.add(os.path.normpath(os.path.abspath(wv.cache_dir)))
                except Exception:
                    pass

            cache_root = AppPaths.cache_root()
            worker = CacheCleanWorker(accounts, cache_root, skip_sessions, skip_caches)
            thread = QThread(self)
            worker.moveToThread(thread)

            def _start_worker():
                worker.run()

            thread.started.connect(_start_worker)
            worker.finished.connect(
                lambda msg, freed: self._on_cache_clean_done(msg, freed, manual=manual)
            )
            worker.failed.connect(
                lambda err: self._on_cache_clean_failed(err, manual=manual)
            )
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda: setattr(self, "_cache_clean_thread", None))
            self._cache_clean_thread = thread
            QTimer.singleShot(800, thread.start)
        except Exception as e:
            self._cache_clean_running = False
            if manual and hasattr(self, "clean_btn"):
                self.clean_btn.setEnabled(True)
            print(f"清理缓存错误: {e}")
            if manual:
                QMessageBox.warning(self, "警告", f"清理缓存时出错: {str(e)}")

    def _on_cache_clean_done(self, msg: str, total_freed: int, *, manual=False):
        self._cache_clean_running = False
        if manual and hasattr(self, "clean_btn"):
            self.clean_btn.setEnabled(True)
        self._mark_cache_clean_today()
        gc.collect()
        if manual:
            if total_freed <= 0:
                msg = (
                    "本次未发现可释放的磁盘缓存（约 0 B）。\n"
                    "登录态已保留。若磁盘仍偏大，可关闭部分账号后再点「清理」。"
                )
            QMessageBox.information(self, "缓存清理完成", msg)
            self.update_status(f"已释放约 {format_bytes(total_freed)}")
        else:
            print(f"[自动缓存清理] {msg}")

    def _on_cache_clean_failed(self, err: str, *, manual=False):
        self._cache_clean_running = False
        if manual and hasattr(self, "clean_btn"):
            self.clean_btn.setEnabled(True)
        print(f"清理缓存错误: {err}")
        if manual:
            QMessageBox.warning(self, "警告", f"清理缓存时出错: {err}")

    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.account_list.itemAt(position)
        if not item:
            return

        account_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet(self._tray_menu_style(bool(getattr(self, "_theme_light", False))))
        self._setup_rounded_menu(menu)

        edit_action = QAction("编辑备注", self)
        edit_action.triggered.connect(lambda checked, aid=account_id: self.edit_remark(aid))
        menu.addAction(edit_action)

        if self.db.is_account_pinned(account_id):
            pin_action = QAction("取消置顶", self)
        else:
            pin_action = QAction("置顶账号", self)
        pin_action.triggered.connect(lambda checked, aid=account_id: self._toggle_account_pin(aid))
        menu.addAction(pin_action)

        if not self.db.account_has_group(account_id):
            add_grp = QAction("添加分组", self)
            add_grp.triggered.connect(lambda checked, aid=account_id: self._account_add_to_group(aid))
            menu.addAction(add_grp)
        else:
            edit_grp = QAction("编辑分组", self)
            edit_grp.triggered.connect(lambda checked, aid=account_id: self._account_edit_group(aid))
            menu.addAction(edit_grp)

        relogin_action = QAction("重新登录", self)
        relogin_action.triggered.connect(lambda checked, aid=account_id: self.login_single_account(aid))
        menu.addAction(relogin_action)

        delete_action = QAction("删除账号", self)
        delete_action.triggered.connect(lambda checked, aid=account_id: self.delete_account(aid))
        menu.addAction(delete_action)

        menu.exec(self.account_list.mapToGlobal(position))

    def _account_add_to_group(self, account_id: int):
        if self.db.account_has_group(account_id):
            return
        groups = self.db.get_all_groups()
        if not groups:
            ConfirmCardDialog.info(
                self, title="提示", message="请先在「管理」中创建分组",
                light=bool(getattr(self, "_theme_light", False)),
            )
            return
        dlg = AccountGroupPickerDialog(self.db, account_id, edit_mode=False, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        gid = dlg.selected_group_id()
        if not gid:
            return
        self.db.set_account_group(account_id, gid)
        self._reload_group_list()
        self.load_accounts()

    def _account_edit_group(self, account_id: int):
        if not self.db.account_has_group(account_id):
            return
        dlg = AccountGroupPickerDialog(self.db, account_id, edit_mode=True, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        gid = dlg.selected_group_id()
        self.db.set_account_group(account_id, gid)
        self._reload_group_list()
        self.load_accounts()

    def edit_remark(self, account_id):
        """编辑备注"""
        try:
            account = self.db.get_account(account_id)
            if not account:
                return

            dialog = EditRemarkDialog(account[1], self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_remark = dialog.get_remark()
                if new_remark:
                    self.db.update_remark(account_id, new_remark)
                    acc = self.db.get_account(account_id)
                    if acc:
                        email = (acc[4] if len(acc) > 4 else "") or ""
                        password = (acc[5] if len(acc) > 5 else "") or ""
                        upsert_account_in_accounts_txt(new_remark, email, password)
                    self.load_accounts()
        except Exception as e:
            print(f"编辑备注错误: {e}")
            QMessageBox.critical(self, "错误", f"编辑备注失败: {str(e)}")

    def delete_account(self, account_id):
        """删除账号"""
        try:
            account = self.db.get_account(account_id)
            if not account:
                return

            confirmed = ConfirmCardDialog.confirm(
                self,
                title="删除账号",
                message=f"确定要删除账号「{account[1]}」吗？\n该操作不可恢复。",
                ok_text="删除",
                danger=True,
                light=bool(getattr(self, "_theme_light", False)),
            )

            if confirmed:
                # 先卸载 WebView
                self.unload_webview(account_id)

                email = (account[4] if len(account) > 4 else "") or ""
                remark = account[1]
                remove_account_from_accounts_txt(email, remark)

                # 删除数据库记录
                self.db.delete_account(account_id)

                # 清理缓存
                self.badge_cache.pop(account_id, None)
                self._sync_taskbar_badge()

                # 如果是当前账号，切换到空视图
                if self.current_account_id == account_id:
                    self.current_account_id = None
                    self.stack_widget.setCurrentIndex(0)

                self.load_accounts()
        except Exception as e:
            print(f"删除账号错误: {e}")
            QMessageBox.critical(self, "错误", f"删除账号失败: {str(e)}")

    def _destroy_webview(self, web_view: TeamsWebView, account_id: int):
        """彻底销毁 WebView：先 Dispose WebView2 原生控件，再删 Qt 壳。"""
        if not web_view:
            return
        try:
            web_view._is_closing = True
            web_view.is_valid = False
            web_view._login_active = False
            web_view._auto_login = False
            for timer_attr in (
                "_offline_timer",
                "_login_poll_timer",
                "_login_timeout_timer",
                "_login_verify_timer",
                "_health_timer",
                "_session_probe_timer",
                "load_timeout_timer",
            ):
                t = getattr(web_view, timer_attr, None)
                if t is not None:
                    try:
                        t.stop()
                    except Exception:
                        pass

            try:
                web_view.loginCompleted.disconnect()
            except Exception:
                pass

            web_view.stop()
            web_view.set_notification_callback(None)
            try:
                web_view.cleanup_js_intervals()
            except Exception:
                pass

            wv2 = getattr(web_view, "_wv2_widget", None)
            web_view._wv2_widget = None
            web_view._page_adapter = None

            if wv2 is not None:
                try:
                    park = getattr(self, "_webview_park", None)
                    if park is not None and wv2.parent() is park:
                        self._webview_park_layout.removeWidget(wv2)
                except Exception:
                    pass
                dispose_webview2_widget(wv2)
                wv2.deleteLater()

            index = self.stack_widget.indexOf(web_view)
            if index >= 0:
                self.stack_widget.removeWidget(web_view)
            web_view.hide()
            web_view.setParent(None)
            web_view.deleteLater()
        except Exception as e:
            print(f"销毁 WebView {account_id} 错误: {e}")

    def unload_webview(self, account_id):
        """卸载 WebView 并释放资源（先解除 Page 与 Profile 绑定，避免 Qt 警告）"""
        try:
            web_view = None
            if account_id in self.web_views:
                web_view = self.web_views.pop(account_id)
            elif account_id in self.suspended_webviews:
                web_view = self.suspended_webviews.pop(account_id)
                try:
                    self._webview_park_layout.removeWidget(web_view)
                except Exception:
                    pass
            else:
                return
            self.webview_pool.remove(account_id)
            timer = self._badge_debounce_timers.pop(account_id, None)
            if timer:
                timer.stop()
                timer.deleteLater()
            self._badge_pending.pop(account_id, None)
            self.badge_cache.pop(account_id, None)
            self._sync_taskbar_badge()
            was_foreground = (
                hasattr(self, "stack_widget")
                and self.stack_widget
                and web_view is not None
                and self.stack_widget.currentWidget() is web_view
            )
            self._destroy_webview(web_view, account_id)
            self._refresh_account_dot(account_id)
            if self.current_account_id == account_id:
                self.current_account_id = None
            if was_foreground and self.stack_widget.count() > 0:
                self.stack_widget.setCurrentIndex(0)
        except Exception as e:
            print(f"卸载 WebView 错误: {e}")

    def load_accounts(self):
        try:
            self._all_accounts_cache = self.db.get_all_accounts()
            self._refresh_account_list_display()
        except Exception as e:
            print(f"加载账号列表错误: {e}")

    def _account_row_meta(self, acc: Tuple) -> Tuple[int, str, str, bool]:
        acc_id, remark = acc[0], acc[1]
        status = (acc[6] if len(acc) > 6 else "pending") or "pending"
        is_pinned = bool(acc[7]) if len(acc) > 7 else False
        return acc_id, remark, status, is_pinned

    def _needs_auto_login(self, account: Tuple, force: bool = False) -> bool:
        """有邮箱密码且尚未登录成功时需自动填表登录"""
        if force:
            return True
        email = ((account[4] if len(account) > 4 else "") or "").strip()
        password = ((account[5] if len(account) > 5 else "") or "").strip()
        status = ((account[6] if len(account) > 6 else "pending") or "pending").strip()
        return bool(email and password and status != "ok")

    def _db_status_for_account(self, account_id: int) -> str:
        if self._all_accounts_cache:
            for acc in self._all_accounts_cache:
                if acc[0] == account_id:
                    return ((acc[6] if len(acc) > 6 else "pending") or "pending").strip()
        acc = self.db.get_account(account_id)
        if acc:
            return ((acc[6] if len(acc) > 6 else "pending") or "pending").strip()
        return "pending"

    def _display_status_for_account(self, account_id: int) -> str:
        """
        红：未验证登录 / 登录失败 / 无页面
        黄：本页已验证登录且处于休眠
        绿：本页已验证登录且在活跃池
        """
        aid = int(account_id)
        wv = self.web_views.get(aid) or self.suspended_webviews.get(aid)
        verified = bool(wv and getattr(wv, "_session_reported", False))
        if aid in self.suspended_webviews:
            return DISPLAY_SLEEP if verified else DISPLAY_OFFLINE
        if aid in self.web_views:
            return DISPLAY_ACTIVE if verified else DISPLAY_OFFLINE
        return DISPLAY_OFFLINE

    def _make_account_list_item(self, acc_id: int, remark: str, status: str, is_pinned: bool) -> QListWidgetItem:
        prefix = "📌 " if is_pinned else ""
        base = f"{prefix}{remark}"
        item = QListWidgetItem(base)
        item.setData(Qt.ItemDataRole.UserRole, acc_id)
        item.setData(REMARK_ROLE, remark)
        item.setData(STATUS_ROLE, status)
        item.setData(PIN_ROLE, is_pinned)
        item.setData(BADGE_COUNT_ROLE, int(self.badge_cache.get(acc_id, 0) or 0))
        item.setIcon(account_status_icon(self._display_status_for_account(acc_id)))
        item.setForeground(QBrush(QColor(list_delegate_colors()["text"])))
        return item

    def _sort_accounts_for_display(self, rows: List[Tuple]) -> List[Tuple]:
        pinned = []
        unpinned = []
        for acc in rows:
            is_pinned = bool(acc[7]) if len(acc) > 7 else False
            if is_pinned:
                pinned.append(acc)
            else:
                unpinned.append(acc)
        pinned.sort(key=lambda a: (a[8] if len(a) > 8 else 0, a[0]))
        unpinned.sort(key=lambda a: (a[9] if len(a) > 9 else a[0], a[0]))
        return pinned + unpinned

    def _refresh_account_list_display(self):
        try:
            current_id = None
            if self.account_list.currentItem():
                current_id = self.account_list.currentItem().data(Qt.ItemDataRole.UserRole)

            keyword = (self.search_edit.text() if hasattr(self, "search_edit") else "").strip().lower()
            group_ids = None
            if self._current_group_id:
                group_ids = self.db.get_account_ids_in_group(self._current_group_id)

            self.account_list._block_order_signal = True
            self.account_list.clear()
            display_rows = self._sort_accounts_for_display(self._all_accounts_cache)
            for acc in display_rows:
                acc_id, remark, status, is_pinned = self._account_row_meta(acc)
                if group_ids is not None and acc_id not in group_ids:
                    continue
                if keyword and keyword not in remark.lower():
                    continue
                self.account_list.addItem(
                    self._make_account_list_item(acc_id, remark, status, is_pinned)
                )
            self.account_list._block_order_signal = False

            if current_id:
                for i in range(self.account_list.count()):
                    if self.account_list.item(i).data(Qt.ItemDataRole.UserRole) == current_id:
                        self.account_list.setCurrentItem(self.account_list.item(i))
                        break
        except Exception as e:
            self.account_list._block_order_signal = False
            print(f"刷新账号列表错误: {e}")

    def _on_account_list_reordered(self):
        pinned_ids = []
        unpinned_ids = []
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            aid = item.data(Qt.ItemDataRole.UserRole)
            if item.data(PIN_ROLE):
                pinned_ids.append(aid)
            else:
                unpinned_ids.append(aid)
        if len(pinned_ids) > MAX_PINNED_ACCOUNTS:
            QMessageBox.warning(self, "提示", f"置顶账号不能超过 {MAX_PINNED_ACCOUNTS} 个")
            self.load_accounts()
            return
        self.db.save_display_order(pinned_ids, unpinned_ids)
        self.load_accounts()

    def _toggle_account_pin(self, account_id: int):
        pinned = self.db.is_account_pinned(account_id)
        ok, msg = self.db.set_account_pinned(account_id, not pinned)
        if not ok:
            QMessageBox.warning(self, "提示", msg or "置顶失败")
            return
        self.load_accounts()
        self._select_account_in_list(account_id)

    def _wire_webview(self, web_view: TeamsWebView):
        if getattr(web_view, "_main_wired", False):
            web_view._host_main = self
            return
        web_view._main_wired = True
        web_view._host_main = self
        web_view.sessionLoggedIn.connect(self._on_session_logged_in)

    def mark_account_not_logged_in(
        self, account_id: int, status: str = "pending"
    ) -> None:
        """登录失败或回到登录页：立即标红。"""
        aid = int(account_id)
        st = (status or "pending").strip() or "pending"
        if st not in ("pending", "failed"):
            st = "pending"
        self.db.set_login_status(aid, st)
        self._set_account_db_status_cache(aid, st)
        QTimer.singleShot(0, lambda a=aid: self._refresh_account_dot(a))

    def mark_account_logged_in(self, account_id: int, message: str = "已登录"):
        """严格验证或登录流程完成后：写库并刷新圆点（绿/黄）。"""
        aid = int(account_id)
        self.db.set_login_status(aid, "ok")
        self._set_account_db_status_cache(aid, "ok")
        QTimer.singleShot(0, lambda a=aid: self._refresh_account_dot(a))
        acc = self.db.get_account(aid)
        if acc:
            self.update_status(f"{acc[1]}: {message}")

    def _set_account_db_status_cache(self, account_id: int, status: str):
        if not self._all_accounts_cache:
            return
        updated: List[Tuple] = []
        for acc in self._all_accounts_cache:
            if acc[0] == account_id and len(acc) > 6:
                if len(acc) > 7:
                    updated.append(acc[:6] + (status,) + acc[7:])
                else:
                    updated.append(acc[:6] + (status,))
            else:
                updated.append(acc)
        self._all_accounts_cache = updated

    def _on_session_logged_in(self, account_id: int):
        try:
            self.mark_account_logged_in(account_id)
            self._maybe_update_password_from_webview(account_id)
        except Exception as e:
            print(f"会话登录状态更新错误: {e}")

    def _maybe_update_password_from_webview(self, account_id: int) -> None:
        """手动修正密码并登录成功后，把正确密码回写到数据库与 accounts.txt。"""
        aid = int(account_id)
        wv = self._get_webview_for_account(aid)
        if not wv or not getattr(wv, "is_valid", False) or not wv.page():
            return

        def _apply_password(value):
            try:
                new_pw = str(value or "").strip()
                if not new_pw:
                    return
                acc = self.db.get_account(aid)
                if not acc:
                    return
                remark = str(acc[1] if len(acc) > 1 else aid)
                email = str(acc[4] if len(acc) > 4 else "")
                old_pw = str((acc[5] if len(acc) > 5 else "") or "")
                if not email or new_pw == old_pw:
                    return
                self.db.update_account_credentials(aid, password=new_pw)
                upsert_account_in_accounts_txt(remark, email, new_pw)
                print(f"账号 {aid} 手动登录成功，已更新保存密码")
            except Exception as e:
                print(f"更新手动登录密码失败: {e}")

        try:
            wv.page().runJavaScript(
                "(function(){try{return window.__teamsxLastPasswordInput||'';}catch(e){return '';}})();",
                _apply_password,
            )
        except Exception as e:
            print(f"读取手动登录密码失败: {e}")

    def _refresh_account_dot(self, account_id: int):
        """按活跃/休眠/离线刷新圆点，不重建整表。"""
        try:
            aid = int(account_id)
            display = self._display_status_for_account(aid)
            icon = account_status_icon(display)
            for i in range(self.account_list.count()):
                item = self.account_list.item(i)
                if item is None:
                    continue
                if int(item.data(Qt.ItemDataRole.UserRole) or 0) != aid:
                    continue
                item.setData(STATUS_ROLE, "ok" if display == DISPLAY_ACTIVE else display)
                item.setIcon(icon)
                row = self.account_list.visualItemRect(item)
                if row.isValid():
                    self.account_list.viewport().update(row)
                self.account_list.viewport().repaint()
                break
        except Exception as e:
            print(f"刷新登录状态图标错误: {e}")

    def _refresh_all_account_dots(self):
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            aid = item.data(Qt.ItemDataRole.UserRole)
            if aid is not None:
                item.setIcon(account_status_icon(self._display_status_for_account(aid)))
        self.account_list.viewport().update()

    def _update_account_status_ui(self, account_id: int, status: str):
        self._set_account_db_status_cache(account_id, status)
        self._refresh_account_dot(account_id)

    def _total_unread_count(self) -> int:
        ids = set(self.badge_cache.keys()) | set(self._badge_pending.keys())
        total = 0
        for aid in ids:
            pending = self._badge_pending.get(aid)
            cached = self.badge_cache.get(aid, 0)
            c = pending if pending is not None else cached
            total += max(0, int(c or 0))
        return total

    def _sync_taskbar_badge(self) -> None:
        if sys.platform != "win32" or self.is_closing:
            return
        try:
            ctrl = getattr(self, "_taskbar_badge", None)
            if ctrl is None:
                return
            hwnd = int(self.winId())
            if hwnd:
                ctrl.bind_hwnd(hwnd)
            total = self._total_unread_count()
            ctrl.update(total)
        except Exception as e:
            print(f"同步任务栏角标错误: {e}")

    def update_account_badge(self, account_id, count):
        try:
            self._badge_pending[account_id] = max(0, int(count))
            if BADGE_DEBOUNCE_MS <= 0:
                self._flush_account_badge(account_id)
            else:
                if account_id not in self._badge_debounce_timers:
                    timer = QTimer(self)
                    timer.setSingleShot(True)
                    timer.timeout.connect(lambda aid=account_id: self._flush_account_badge(aid))
                    self._badge_debounce_timers[account_id] = timer
                self._badge_debounce_timers[account_id].start(BADGE_DEBOUNCE_MS)
                self._sync_taskbar_badge()
        except Exception as e:
            print(f"更新角标错误: {e}")

    def _flush_account_badge(self, account_id: int):
        try:
            if account_id not in self._badge_pending:
                return
            c = self._badge_pending.pop(account_id)
            self.badge_cache[account_id] = c
            for i in range(self.account_list.count()):
                item = self.account_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == account_id:
                    remark = item.data(REMARK_ROLE) or ""
                    is_pinned = bool(item.data(PIN_ROLE))
                    prefix = "📌 " if is_pinned else ""
                    base = f"{prefix}{remark}"
                    item.setData(BADGE_COUNT_ROLE, c)
                    item.setForeground(QBrush(QColor(list_delegate_colors()["text"])))
                    row = self.account_list.indexFromItem(item)
                    if row.isValid():
                        self.account_list.viewport().update(
                            self.account_list.visualRect(row)
                        )
                    break
            self._sync_taskbar_badge()
        except Exception as e:
            print(f"刷新角标显示错误: {e}")

    def _select_account_in_list(self, account_id: int):
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == account_id:
                self.account_list.setCurrentItem(item)
                break

    def _show_account_webview_front(self, account_id: int) -> bool:
        """把账号 WebView 显示到 stack 前台（含从停车区拉回）。"""
        aid = int(account_id)
        wv = self.web_views.get(aid)
        if not wv or not getattr(wv, "is_valid", False):
            return False
        try:
            wv.resume_page()
            if (
                hasattr(self, "_webview_park")
                and self._webview_park
                and wv.parent() is self._webview_park
            ):
                try:
                    self._webview_park_layout.removeWidget(wv)
                except Exception:
                    pass
            idx = self.stack_widget.indexOf(wv)
            if idx < 0:
                self.stack_widget.addWidget(wv)
            self.stack_widget.setCurrentWidget(wv)
            wv.show()
            QTimer.singleShot(0, self._sync_foreground_webview_layout)
            return True
        except Exception as e:
            print(f"显示账号 {aid} 页面错误: {e}")
            return False

    def switch_to_account(self, account_id: int) -> bool:
        """切换到指定账号；未登录成功的账号点击后自动填表登录"""
        if self.is_closing or not account_id:
            return False
        if getattr(self, "_app_locked", False):
            return False
        if getattr(self, "_lock_teardown_active", False):
            self.update_status("正在释放内存，请稍候再打开账号")
            return False
        self._last_account_switch_at = time.time()
        self._arm_notify_sound_suppress(NOTIFY_SOUND_SUPPRESS_AFTER_SWITCH_SEC, account_id)
        QTimer.singleShot(
            600,
            lambda aid=int(account_id): self._sync_notify_baseline_on_focus(aid),
        )
        try:
            account = self.db.get_account(account_id)
            if not account:
                return False

            need_login = self._needs_auto_login(account)
            in_active = account_id in self.web_views
            in_sleep = account_id in self.suspended_webviews

            if self.current_account_id == account_id and (in_active or in_sleep):
                if in_active:
                    if self._show_account_webview_front(account_id):
                        self._select_account_in_list(account_id)
                        self._sync_webview_lifecycle_states()
                        return True
                if in_sleep:
                    self._enforce_webview_limit(account_id)
                    wv = self._resume_webview(account_id)
                    if wv:
                        self._select_account_in_list(account_id)
                        self._sync_webview_lifecycle_states()
                        return True

            old_id = self.current_account_id
            self.current_account_id = account_id
            if old_id and old_id != account_id:
                self.webview_pool.deactivate(old_id)
                old_wv = self.web_views.get(int(old_id))
                if old_wv and getattr(old_wv, "is_valid", False):
                    self._park_webview_background(old_wv)
            self.webview_pool.mark_used(account_id)
            self._select_account_in_list(account_id)

            if in_active:
                wv = self.web_views[account_id]
                self.webview_pool.mark_used(account_id)
                if wv and wv.is_valid and self._show_account_webview_front(account_id):
                    self._sync_webview_lifecycle_states()
                    self._refresh_account_dot(account_id)
                    if self._db_status_for_account(account_id) == "ok":
                        QTimer.singleShot(600, lambda: wv._schedule_session_check(0))
                    elif need_login and not wv._login_active:
                        QTimer.singleShot(500, wv._maybe_start_auto_login)
                        QTimer.singleShot(400, wv._probe_teams_session)
                    return True

            if in_sleep:
                self._enforce_webview_limit(account_id)
                wv = self._resume_webview(account_id)
                if wv:
                    self._sync_webview_lifecycle_states()
                    if self._db_status_for_account(account_id) == "ok":
                        QTimer.singleShot(600, lambda w=wv: w._schedule_session_check(0))
                        self._refresh_account_dot(account_id)
                    elif need_login and not wv._login_active:
                        QTimer.singleShot(500, wv._maybe_start_auto_login)
                        QTimer.singleShot(400, wv._probe_teams_session)
                    return True

            self._enforce_webview_limit(account_id)
            acc_id, session_dir, cache_dir = account[0], account[2], account[3]
            remark = account[1]
            email = ((account[4] if len(account) > 4 else "") or "").strip()
            password = ((account[5] if len(account) > 5 else "") or "").strip()
            self.update_status(f"正在登录: {remark}…")
            web_view = TeamsWebView(
                acc_id,
                session_dir,
                cache_dir,
                self.on_notification_received,
                login_email=email if need_login else None,
                login_password=password if need_login else None,
                auto_login=need_login,
                image_helper=self._image_helper,
            )
            web_view._host_main = self
            web_view._notifications_enabled = (
                self.notification_toggle.isChecked()
                if hasattr(self, "notification_toggle")
                else True
            )
            self._wire_webview(web_view)
            web_view.set_notification_callback(self.on_notification_received)
            web_view.apply_notifications_enabled(
                self.notification_toggle.isChecked()
                if hasattr(self, "notification_toggle")
                else True
            )
            if need_login:
                web_view.loginCompleted.connect(
                    lambda aid, ok, msg: self._on_account_login_finished(
                        aid, ok, msg, show_dialog=False
                    )
                )
            self.web_views[acc_id] = web_view
            self.webview_pool.register(acc_id, web_view)
            self.stack_widget.addWidget(web_view)
            self.stack_widget.setCurrentWidget(web_view)
            self._sync_webview_lifecycle_states()
            self._refresh_account_dot(acc_id)
            if not need_login and self._db_status_for_account(acc_id) == "ok":
                QTimer.singleShot(800, lambda w=web_view: w._schedule_session_check(0))
            return True
        except Exception as e:
            print(f"切换账号错误: {e}")
            QMessageBox.critical(self, "错误", f"切换账号失败: {str(e)}")
            return False
        finally:
            self._schedule_memory_guard_refresh()

    def on_account_clicked(self, item):
        """账号点击事件"""
        if not item or getattr(self, "_app_locked", False):
            return
        account_id = item.data(Qt.ItemDataRole.UserRole)
        self.switch_to_account(account_id)

    def _notifications_enabled(self) -> bool:
        if hasattr(self, "notification_toggle") and self.notification_toggle:
            return bool(self.notification_toggle.isChecked())
        return True

    def _prepare_notify_sound_startup(self) -> None:
        """启动时预加载消息/来电提示音。"""
        if self._ensure_official_notify_sound():
            self._init_notify_sound_player()
        if self._ensure_call_notify_sound():
            self._init_call_sound_player()

    def _ensure_official_notify_sound(self) -> Optional[str]:
        path = AppPaths.teams_notify_official()
        if os.path.isfile(path) and os.path.getsize(path) >= 100:
            self._teams_notify_sound_path = path
            return path
        print(f"[提示音] 未找到固定音频文件: {path}")
        return None

    def _ensure_call_notify_sound(self) -> Optional[str]:
        path = AppPaths.teams_call_notify()
        if os.path.isfile(path) and os.path.getsize(path) >= 100:
            self._teams_call_sound_path = path
            return path
        print(f"[提示音] 未找到来电音频文件: {path}")
        return None

    def _init_notify_sound_player(self) -> None:
        if self.is_closing or self._notify_sound_player is not None:
            return
        path = self._ensure_official_notify_sound()
        if not path:
            return
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            player = QMediaPlayer(self)
            output = QAudioOutput(self)
            output.setVolume(1.0)
            player.setAudioOutput(output)
            player.mediaStatusChanged.connect(self._on_notify_media_status)
            player.errorOccurred.connect(self._on_notify_player_error)
            player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            self._notify_sound_player = player
            self._notify_sound_output = output
            self._sync_notify_sound_ready_from_player()
        except Exception as e:
            print(f"预加载 Teams 提示音失败: {e}")

    def _init_call_sound_player(self) -> None:
        if self.is_closing or self._call_sound_player is not None:
            return
        path = self._ensure_call_notify_sound()
        if not path:
            return
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            player = QMediaPlayer(self)
            output = QAudioOutput(self)
            output.setVolume(1.0)
            player.setAudioOutput(output)
            player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            self._call_sound_player = player
            self._call_sound_output = output
            try:
                from PyQt6.QtMultimedia import QMediaPlayer

                st = player.mediaStatus()
                if st in (
                    QMediaPlayer.MediaStatus.LoadedMedia,
                    QMediaPlayer.MediaStatus.BufferedMedia,
                ):
                    self._call_sound_ready = True
            except Exception:
                pass
        except Exception as e:
            print(f"预加载来电提示音失败: {e}")

    def _sync_notify_sound_ready_from_player(self) -> None:
        player = self._notify_sound_player
        if not player:
            return
        try:
            from PyQt6.QtMultimedia import QMediaPlayer

            st = player.mediaStatus()
            if st in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
            ):
                self._notify_sound_ready = True
                self._notify_sound_play_pending = False
        except Exception:
            pass

    def _on_notify_media_status(self, status) -> None:
        try:
            from PyQt6.QtMultimedia import QMediaPlayer

            if status in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
            ):
                self._notify_sound_ready = True
                self._notify_sound_play_pending = False
            elif status == QMediaPlayer.MediaStatus.InvalidMedia:
                self._reset_notify_sound_file()
        except Exception as e:
            print(f"提示音状态回调错误: {e}")

    def _on_notify_player_error(self, _error, message: str = "") -> None:
        if message:
            print(f"提示音播放器错误: {message}")
        self._notify_sound_ready = False
        self._reset_notify_sound_file()

    def _reset_notify_sound_file(self) -> None:
        """播放器异常时仅重置播放器，不改动 audio 目录内固定文件。"""
        self._notify_sound_ready = False
        self._notify_sound_player = None
        self._notify_sound_output = None

    def _cache_teams_notify_sound_url(self, url: str) -> None:
        return

    def _arm_notify_sound_suppress(self, seconds: float, account_id: Optional[int] = None) -> None:
        until = time.time() + max(0.5, float(seconds))
        self._notify_sound_suppress_until = max(
            float(getattr(self, "_notify_sound_suppress_until", 0.0) or 0.0),
            until,
        )
        if account_id:
            wv = self._get_webview_for_account(int(account_id))
            if wv and getattr(wv, "is_valid", False) and wv.page():
                ms = int(seconds * 1000) + 500
                wv.page().runJavaScript(
                    f"window.__teamsLastNotifySoundAt=Date.now()+{ms};"
                )

    def _finish_notify_startup_arm(self) -> None:
        """启动后为尚未锁定的账号建立未读基线。"""
        for aid in self._loaded_account_ids():
            if aid in self._notify_baseline_locked:
                continue
            c = max(0, int(self.badge_cache.get(aid, 0) or 0))
            self._notify_last_unread[aid] = c
            self._notify_sound_fired_at_count[aid] = c
            self._notify_baseline_locked.add(aid)

    def _notify_sound_armed(self) -> bool:
        return True

    def _sync_notify_baseline_on_focus(self, account_id: int) -> None:
        """切到某账号后同步基线，避免点进时补响。"""
        aid = int(account_id)
        c = max(
            0,
            int(self._badge_pending.get(aid, self.badge_cache.get(aid, 0)) or 0),
        )
        self._notify_last_unread[aid] = c
        self._notify_sound_fired_at_count[aid] = c
        self._notify_baseline_locked.add(aid)

    def _extract_msg_notify_key(self, content: str) -> str:
        """仅对 JS 附带的 msgId（content 中 | 前段）去重；无 msgId 时不拦截。"""
        c = (content or "").strip()
        if "|" not in c:
            return ""
        return c.split("|", 1)[0].strip()

    def _claim_api_notify(self, account_id: int, tag: str) -> bool:
        """Teams Notification API 事件去重（按 tag，窗口较长）。"""
        aid = int(account_id)
        token = (tag or "").strip()
        if not token:
            return True
        dedup_key = (aid, token)
        now = time.time()
        prev = self._api_notify_dedup.get(dedup_key)
        if prev is not None and (now - float(prev)) < float(NOTIFY_API_DEDUP_TTL_SEC):
            return False
        self._api_notify_dedup[dedup_key] = now
        if len(self._api_notify_dedup) > MSG_NOTIFY_DEDUP_MAX:
            items = sorted(self._api_notify_dedup.items(), key=lambda x: x[1])
            for (kk, _) in items[: len(items) // 2]:
                self._api_notify_dedup.pop(kk, None)
        return True

    def _handle_teams_api_notification(
        self,
        account_id: int,
        sender: str,
        content: str,
        new_count: int,
    ) -> None:
        """唯一消息提示音来源：Teams 网页 Notification API（译达通同款）。"""
        if not self._notifications_enabled():
            return
        aid = int(account_id)
        if self._is_account_foreground(aid):
            self._sync_notify_baseline_on_focus(aid)
            return
        if time.time() < float(self._notify_sound_suppress_until or 0.0):
            return
        tag = self._extract_msg_notify_key(content) or (content or sender or "msg").strip()
        if not self._claim_api_notify(aid, tag):
            return
        fired = int(self._notify_sound_fired_at_count.get(aid, 0))
        if new_count > fired:
            self._mark_unread_notified(aid, new_count)
        self._play_message_notify_now(aid)

    def _handle_unread_badge_only(self, account_id: int, new_count: int) -> None:
        """未读轮询/标题同步：只更新角标基线，不响铃。"""
        aid = int(account_id)
        new_count = max(0, int(new_count))
        if aid not in self._notify_baseline_locked:
            self._notify_baseline_locked.add(aid)
        self._notify_last_unread[aid] = new_count
        if new_count > int(self._notify_sound_fired_at_count.get(aid, 0)):
            self._notify_sound_fired_at_count[aid] = new_count

    def _claim_message_notify(self, account_id: int, key: str) -> bool:
        """按消息 ID 短时去重，避免多路检测对同一条消息重复响铃。"""
        aid = int(account_id)
        token = (key or "").strip()
        if not token:
            return True
        dedup_key = (aid, token)
        now = time.time()
        prev = self._msg_notify_dedup.get(dedup_key)
        if prev is not None and (now - float(prev)) < MSG_NOTIFY_DEDUP_TTL_SEC:
            return False
        self._msg_notify_dedup[dedup_key] = now
        if len(self._msg_notify_dedup) > MSG_NOTIFY_DEDUP_MAX:
            items = sorted(self._msg_notify_dedup.items(), key=lambda x: x[1])
            for (kk, _) in items[: len(items) // 2]:
                self._msg_notify_dedup.pop(kk, None)
        return True

    def _mark_unread_notified(self, account_id: int, new_count: int) -> None:
        aid = int(account_id)
        c = max(0, int(new_count))
        self._notify_sound_fired_at_count[aid] = c
        self._notify_last_unread[aid] = c

    def _should_ring_for_unread(self, account_id: int, new_count: int) -> bool:
        """未读数上升即响铃（首见账号先锁基线，不响历史未读）。"""
        aid = int(account_id)
        new_count = max(0, int(new_count))
        if aid not in self._notify_baseline_locked:
            self._notify_baseline_locked.add(aid)
            self._notify_last_unread[aid] = new_count
            self._notify_sound_fired_at_count[aid] = new_count
            return False
        prev = int(self._notify_last_unread.get(aid, 0))
        self._notify_last_unread[aid] = new_count
        if new_count <= prev:
            return False
        fired_at = int(self._notify_sound_fired_at_count.get(aid, prev))
        if new_count <= fired_at:
            return False
        return True

    def _play_notify_sound_mci(self, path: str, alias: str = "teamsx_notify") -> bool:
        """Windows MCI 播放 mp3，不依赖 Qt 媒体是否加载完成。"""
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            winmm = ctypes.windll.winmm
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)
            abs_path = os.path.abspath(path)
            err = winmm.mciSendStringW(
                f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, 0
            )
            if err:
                err = winmm.mciSendStringW(
                    f'open "{abs_path}" alias {alias}', None, 0, 0
                )
            if err:
                return False
            winmm.mciSendStringW(f"play {alias}", None, 0, 0)
            return True
        except Exception as e:
            print(f"MCI 播放提示音失败: {e}")
            return False

    def _play_teams_notify_sound_native(self) -> bool:
        path = self._ensure_official_notify_sound()
        if not path:
            return False
        if self._play_notify_sound_mci(path):
            return True
        if sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(
                    path, winsound.SND_FILENAME | winsound.SND_ASYNC
                )
                return True
            except Exception:
                pass
        if self._notify_sound_player is None:
            self._init_notify_sound_player()
        player = self._notify_sound_player
        if player is None:
            return False
        if not self._notify_sound_ready:
            self._sync_notify_sound_ready_from_player()
        if not self._notify_sound_ready:
            return False
        try:
            from PyQt6.QtMultimedia import QMediaPlayer

            player.setPosition(0)
            player.play()
            return True
        except Exception as e:
            print(f"播放 Teams 提示音失败: {e}")
            return False

    def _stop_call_notify_sound(self) -> None:
        """挂断或用户关闭提醒时立即停止来电铃声。"""
        if sys.platform == "win32":
            try:
                import ctypes

                winmm = ctypes.windll.winmm
                winmm.mciSendStringW("stop teamsx_call", None, 0, 0)
                winmm.mciSendStringW("close teamsx_call", None, 0, 0)
            except Exception:
                pass
        player = getattr(self, "_call_sound_player", None)
        if player is not None:
            try:
                player.stop()
            except Exception:
                pass

    def _stop_call_ring_loop(self) -> None:
        """停止来电循环铃声（挂断/关闭提醒时调用）。"""
        self._call_ring_active_aid = None
        timer = getattr(self, "_call_ring_loop_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._stop_call_notify_sound()

    def _schedule_call_ring_repeat(self) -> None:
        timer = getattr(self, "_call_ring_loop_timer", None)
        if timer is None:
            return
        timer.stop()
        timer.start(int(CALL_NOTIFY_DURATION_SEC * 1000))

    def _on_call_ring_loop_repeat(self) -> None:
        aid = getattr(self, "_call_ring_active_aid", None)
        if aid is None:
            return
        sess = self._call_sessions.get(int(aid))
        if not sess or sess.get("suppressed"):
            self._stop_call_ring_loop()
            return
        # 后台账号无 DOM 挂断信号：超过最大时长自动停，避免对方挂断后无限响。
        started = float(getattr(self, "_call_ring_started_at", 0.0) or 0.0)
        if started and (time.time() - started) >= float(CALL_RING_MAX_DURATION_SEC):
            print(f"账号 {aid} 来电铃声达最大时长，自动停止")
            self._suppress_call_session(int(aid), "响铃超时")
            self._stop_call_ring_loop()
            return
        self._play_call_notify_sound_native(restart=True)
        self._schedule_call_ring_repeat()

    def _start_call_ring_loop(self, account_id: int) -> None:
        """播放完整 video.mp3（约 9 秒）后重复，直到挂断或达最大时长。"""
        aid = int(account_id)
        if getattr(self, "_call_ring_active_aid", None) == aid:
            return
        self._stop_call_ring_loop()
        self._call_ring_active_aid = aid
        self._call_ring_started_at = time.time()
        if self._call_ring_loop_timer is None:
            self._call_ring_loop_timer = QTimer(self)
            self._call_ring_loop_timer.setSingleShot(True)
            self._call_ring_loop_timer.timeout.connect(self._on_call_ring_loop_repeat)
        self._play_call_notify_sound_native(restart=True)
        self._schedule_call_ring_repeat()

    def _play_call_notify_sound_native(self, *, restart: bool = True) -> bool:
        """播放音视频来电专用提示音 audio/video.mp3。"""
        path = self._ensure_call_notify_sound()
        if not path:
            return False
        if sys.platform == "win32":
            if self._play_notify_sound_mci(path, alias="teamsx_call"):
                return True
        if self._call_sound_player is None:
            self._init_call_sound_player()
        player = self._call_sound_player
        if player is None:
            return False
        try:
            from PyQt6.QtMultimedia import QMediaPlayer

            if (
                not restart
                and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            ):
                return True
            player.setPosition(0)
            player.play()
            return True
        except Exception as e:
            print(f"播放来电提示音失败: {e}")
            return False

    def _play_message_notify_now(self, account_id: int) -> None:
        """消息提示音：每条即时播放；同账号极短窗内合并多路重复上报。"""
        if not self._notifications_enabled():
            return
        aid = int(account_id)
        if self._is_account_foreground(aid):
            return
        if time.time() < float(self._notify_sound_suppress_until or 0.0):
            return
        now = time.time()
        last = float(self._msg_sound_last_by_account.get(aid, 0.0) or 0.0)
        if now - last < 0.35:
            return
        self._msg_sound_last_by_account[aid] = now
        self._play_teams_notify_sound_native()

    def _handle_realtime_message(
        self,
        account_id: int,
        kind: str,
        sender: str,
        content: str,
        new_count: int,
    ) -> None:
        """DOM 扫描遗留路径：仅同步基线，不响铃。"""
        if not self._notifications_enabled():
            return
        aid = int(account_id)
        self._handle_unread_badge_only(aid, new_count)

    def _handle_unread_notification(self, account_id: int, new_count: int) -> None:
        """未读数变化：只更新角标，不响铃（响铃交给 teams_notify）。"""
        self._handle_unread_badge_only(int(account_id), new_count)

    def _write_notif_debug(self, account_id: int, sender: str, content: str) -> None:
        """临时调试：把每条 Notification 原始内容写到桌面日志，便于核对来电文案。"""
        try:
            remark = self._account_remark_for_notify(int(account_id))
            line = (
                f"{datetime.now():%H:%M:%S} acc={account_id}({remark}) "
                f"title={sender} {content}\n"
            )
            log_dir = os.path.join(
                os.path.expanduser("~"), "Desktop", "TeamsX监控数据"
            )
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, "teamsx_notif_debug.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _account_remark_for_notify(self, account_id: int) -> str:
        aid = int(account_id)
        for acc in self._all_accounts_cache or []:
            if int(acc[0]) == aid:
                return str(acc[1] if len(acc) > 1 else aid)
        acc = self.db.get_account(aid)
        if acc:
            return str(acc[1] if len(acc) > 1 else aid)
        return str(aid)

    def _setup_call_dismiss_watcher(self) -> None:
        """监听用户手动关闭来电 Toast，关闭后本次来电不再弹窗/响铃。"""
        if sys.platform != "win32":
            return
        try:
            from teamsx.notify.win_toast import DISMISS_FLAG_DIR

            os.makedirs(DISMISS_FLAG_DIR, exist_ok=True)
            watcher = QFileSystemWatcher(self)
            watcher.addPath(DISMISS_FLAG_DIR)
            watcher.directoryChanged.connect(self._on_call_dismiss_dir_changed)
            self._call_dismiss_watcher = watcher
            self._on_call_dismiss_dir_changed(DISMISS_FLAG_DIR)
        except Exception as e:
            print(f"来电 Toast 关闭监听失败: {e}")

    def _on_call_dismiss_dir_changed(self, _path: str = "") -> None:
        if sys.platform != "win32":
            return
        try:
            from teamsx.notify.win_toast import DISMISS_FLAG_DIR, call_toast_tag

            if not os.path.isdir(DISMISS_FLAG_DIR):
                return
            prefix = call_toast_tag(0).rsplit("-", 1)[0] + "-"
            for name in os.listdir(DISMISS_FLAG_DIR):
                if not name.endswith(".flag"):
                    continue
                stem = name[:-5]
                if not stem.startswith(prefix):
                    continue
                try:
                    aid = int(stem[len(prefix):])
                except ValueError:
                    continue
                flag_path = os.path.join(DISMISS_FLAG_DIR, name)
                if not os.path.isfile(flag_path):
                    continue
                self._suppress_call_session(aid, reason="toast_dismissed")
                try:
                    os.remove(flag_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"处理来电 Toast 关闭失败: {e}")

    def _call_session_key(self, caller: str, kind: str) -> str:
        # 仅按呼叫者去重，不分音视频：避免 DOM 与 Notification 两路对同一来电
        # 因音视频判定不一致而生成两个 session 导致重复响铃。
        who = (caller or "").strip() or "某人"
        return f"call:{who}"

    def _get_call_session(self, account_id: int, caller: str, kind: str) -> dict:
        aid = int(account_id)
        key = self._call_session_key(caller, kind)
        sess = self._call_sessions.get(aid)
        if sess and sess.get("key") != key:
            self._clear_call_session(aid)
            sess = None
        if not sess:
            sess = {
                "key": key,
                "caller": (caller or "").strip() or "某人",
                "kind": kind,
                "toast_shown": False,
                "suppressed": False,
                "ring_loop_started": False,
            }
            self._call_sessions[aid] = sess
        return sess

    def _suppress_call_session(self, account_id: int, reason: str = "") -> None:
        aid = int(account_id)
        sess = self._call_sessions.get(aid)
        if not sess or sess.get("suppressed"):
            return
        sess["suppressed"] = True
        self._stop_call_ring_loop()
        if reason:
            print(f"账号 {aid} 本次来电提醒已关闭 ({reason})")

    def _clear_call_session(self, account_id: int) -> None:
        aid = int(account_id)
        self._stop_call_ring_loop()
        self._call_sessions.pop(aid, None)
        self._call_ring_last.pop(aid, None)
        if sys.platform == "win32":
            try:
                from teamsx.notify.win_toast import clear_dismiss_flag, remove_call_toast

                clear_dismiss_flag(aid)
                remove_call_toast(aid)
            except Exception:
                pass

    def _handle_call_ended(self, account_id: int) -> None:
        """来电结束：防抖确认后停。Teams 结束来电时可能先 close 旧通知再建新通知，
        延迟确认可吸收这种抖动，期间若同账号又来电则取消停止。"""
        aid = int(account_id)
        self._call_end_pending[aid] = time.time()
        QTimer.singleShot(
            int(CALL_END_DEBOUNCE_MS),
            lambda a=aid: self._confirm_call_ended(a),
        )

    def _confirm_call_ended(self, account_id: int) -> None:
        aid = int(account_id)
        if aid not in self._call_end_pending:
            return
        self._call_end_pending.pop(aid, None)
        self._clear_call_session(aid)

    def _show_incoming_call_toast(
        self, account_id: int, kind: str, caller: str
    ) -> None:
        """语音/视频来电：系统 Toast 优先，失败时托盘兜底（只弹一个）。"""
        self._do_show_call_toast(int(account_id), kind, (caller or "").strip() or "某人")

    def _do_show_call_toast(self, account_id: int, kind: str, caller: str) -> None:
        if sys.platform != "win32":
            return
        who = (caller or "").strip() or "某人"
        kind_label = "视频来电" if kind == "video" else "语音来电"
        title = f"{who} · {kind_label}"
        body = f"TeamsX · {self._account_remark_for_notify(account_id)}"
        ok = False
        try:
            from teamsx.notify.win_toast import show_incoming_call_toast

            icon_path = AppPaths.app_icon() or (
                os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None
            )
            if getattr(sys, "frozen", False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0]) if sys.argv else sys.executable
            ok = bool(
                show_incoming_call_toast(
                    caller=who,
                    call_kind=kind,
                    account_label=self._account_remark_for_notify(account_id),
                    account_id=int(account_id),
                    icon_path=icon_path,
                    exe_path=exe_path,
                )
            )
        except Exception as e:
            print(f"来电 Toast 错误: {e}")
        if not ok:
            self._show_call_tray_fallback(title, body)

    def _ensure_call_tray_icon(self) -> Optional[QSystemTrayIcon]:
        tray = self._ensure_app_tray_icon()
        if tray is not None:
            self._call_tray_icon = tray
            return tray
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        if self._call_tray_icon is None:
            tray = QSystemTrayIcon(self)
            icon = AppPaths.app_qicon()
            if icon.isNull():
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            tray.setIcon(icon)
            tray.setToolTip("TeamsX")
            tray.show()
            self._call_tray_icon = tray
        return self._call_tray_icon

    def _show_call_tray_fallback(self, title: str, body: str) -> None:
        tray = self._ensure_call_tray_icon()
        if tray is None:
            return
        try:
            tray.showMessage(
                title,
                body,
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )
        except Exception as e:
            print(f"来电托盘通知失败: {e}")

    def _play_incoming_call_sound(self) -> None:
        """来电专用铃声 audio/video.mp3，与消息提示音独立。"""
        self._play_call_notify_sound_native()

    def _handle_incoming_call(self, account_id: int, kind: str, sender: str, content: str) -> None:
        """语音/视频来电：完整播完铃声后循环；挂断即停；Toast 每通一次。"""
        if self.is_closing:
            return
        if not self._notifications_enabled():
            return
        aid = int(account_id)
        self._call_end_pending.pop(aid, None)
        who = (sender or "").strip() or "某人"
        sess = self._get_call_session(aid, who, kind)
        if sess.get("suppressed"):
            return

        if who and who != "某人":
            sess["caller"] = who

        kind_label = "视频通话" if kind == "video" else "语音通话"
        self.update_status(f"{sess.get('caller') or who} 来电（{kind_label}）")

        if not sess.get("toast_shown"):
            sess["toast_shown"] = True
            self._show_incoming_call_toast(aid, kind, sess.get("caller") or who)

        if not sess.get("ring_loop_started"):
            sess["ring_loop_started"] = True
            self._start_call_ring_loop(aid)

    def on_notification_received(self, account_id: int, count: int, msg_type: str = 'unread', sender: str = '', content: str = ''):
        """通知接收回调：同步角标；消息/来电分通道即时提醒。"""
        if self.is_closing:
            return

        try:
            # WebView 内 Esc：回到 AI 主界面（不影响 Teams 自己的 Esc 行为）
            if (msg_type or "") == "ui" and (sender or "") == "esc":
                try:
                    self.go_home()
                except Exception:
                    pass
                return
            aid = int(account_id)
            new_count = max(0, int(count))
            kind = (msg_type or "unread").strip() or "unread"
            if kind == "notif_debug":
                self._write_notif_debug(aid, sender, content)
                return
            self.update_account_badge(aid, new_count)

            if not self._notifications_enabled():
                if kind == "call_end":
                    self._handle_call_ended(aid)
                return

            if kind in ("incoming_call", "incoming_video"):
                call_kind = "video" if kind == "incoming_video" else "call"
                self._handle_incoming_call(aid, call_kind, sender, content)
                return
            if kind == "teams_notify":
                self._handle_teams_api_notification(aid, sender, content, new_count)
                return
            if kind in ("call", "video"):
                msg = (content or "").strip()
                if "邀请你" in msg or msg.startswith("invite"):
                    self._handle_incoming_call(aid, kind, sender, content)
                return
            if kind == "call_end":
                self._handle_call_ended(aid)
                return
            if kind in ("reply", "voice", "image", "emoji", "file", "like"):
                self._handle_realtime_message(aid, kind, sender, content, new_count)
                return
            if kind == "unread":
                self._handle_unread_notification(aid, new_count)
                return
        except Exception as e:
            print(f"处理通知错误: {e}")

    def add_account(self):
        """添加账号"""
        try:
            dialog = AddAccountDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                remark = dialog.get_remark()
                email = dialog.get_email()
                password = dialog.get_password()
                if remark:
                    account_id = self.db.add_account(remark, email, password)
                    if account_id:
                        upsert_account_in_accounts_txt(remark, email, password)
                        self.load_accounts()
                        self._select_account_in_list(account_id)
                        ConfirmCardDialog.info(
                            self, title="添加成功",
                            message=f"账号「{remark}」添加成功\n请点击左侧列表项打开并登录该账号。",
                            light=bool(getattr(self, "_theme_light", False)),
                        )
                    else:
                        QMessageBox.critical(self, "错误", "添加账号失败")
                else:
                    QMessageBox.warning(self, "提示", "请输入备注")
        except Exception as e:
            print(f"添加账号错误: {e}")
            QMessageBox.critical(self, "错误", f"添加账号失败: {str(e)}")

    def import_accounts(self):
        """导入 B/Z/M 格式账号（点击列表项再自动登录）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择账号文件", "", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            file_size = os.path.getsize(file_path)
            if file_size > MAX_IMPORT_FILE_SIZE:
                QMessageBox.warning(
                    self, "文件过大",
                    f"文件大小超过 {MAX_IMPORT_FILE_SIZE // 1024 // 1024}MB 限制",
                )
                return

            encoding = "utf-8"
            if HAS_CHARDET:
                with open(file_path, "rb") as f:
                    raw_data = f.read(10000)
                    detected = chardet.detect(raw_data)
                    encoding = detected.get("encoding", "utf-8") if detected else "utf-8"

            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                content = f.read(MAX_IMPORT_FILE_SIZE + 1)

            accounts_data = parse_account_blocks(content)
            if not accounts_data:
                QMessageBox.warning(
                    self,
                    "提示",
                    "未找到有效账号。\n\n格式示例：\nB：备注\nZ：邮箱\nM：密码\n（空行分隔多条）",
                )
                return

            imported = []

            for acc in accounts_data:
                remark = (acc.get("remark") or acc.get("email") or "未命名").strip()
                email = (acc.get("email") or "").strip()
                password = (acc.get("password") or "").strip()

                if not email:
                    imported.append(f"{remark}(缺少 Z 账号，跳过)")
                    continue

                existing = self.db.find_account_by_email(email)
                if existing:
                    account_id = existing[0]
                    existing_password = (existing[5] if len(existing) > 5 else "") or ""
                    existing_status = (existing[6] if len(existing) > 6 else "") or ""
                    # 空密码不覆盖：编辑 txt 时漏写 M 行，保留已存密码，免得又要手动输
                    effective_password = password or existing_password
                    pw_changed = bool(password) and password != existing_password
                    self.db.update_account_credentials(
                        account_id,
                        remark=remark,
                        email=email,
                        password=password if password else None,
                    )
                    # 已登录且凭据未变 → 保留会话，不强制重新登录
                    if pw_changed or existing_status != "ok":
                        self.db.set_login_status(account_id, "pending")
                    imported.append(f"{remark}({email})(更新)")
                else:
                    effective_password = password
                    account_id = self.db.add_account(remark, email, password)
                    if account_id:
                        imported.append(f"{remark}({email})(新增)")
                    else:
                        imported.append(f"{remark}({email})(失败)")
                upsert_account_in_accounts_txt(remark, email, effective_password)

            self.load_accounts()

            msg = f"成功处理 {len(imported)} 条记录:\n" + "\n".join(imported[:12])
            if len(imported) > 12:
                msg += f"\n... 等共 {len(imported)} 条"
            msg += "\n\n请点击左侧账号，将自动登录该账号（一次一个）。"
            ConfirmCardDialog.info(
                self, title="导入完成", message=msg,
                light=bool(getattr(self, "_theme_light", False)),
            )
        except Exception as e:
            print(f"导入账号错误: {e}")
            QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")

    def login_single_account(self, account_id: int):
        acc = self.db.get_account(account_id)
        if not acc:
            return
        email = acc[4] if len(acc) > 4 else ""
        password = acc[5] if len(acc) > 5 else ""
        if not email or not password:
            QMessageBox.warning(self, "提示", "该账号缺少 Z(邮箱) 或 M(密码)，请重新导入")
            return
        self.unload_webview(account_id)
        remark = acc[1]
        session_dir, cache_dir = acc[2], acc[3]
        self.current_account_id = account_id
        self._enforce_webview_limit(account_id)
        self.update_status(f"正在登录: {remark}")
        web_view = TeamsWebView(
            account_id,
            session_dir,
            cache_dir,
            self.on_notification_received,
            login_email=email,
            login_password=password,
            auto_login=True,
            image_helper=self._image_helper,
        )
        web_view._host_main = self
        web_view._notifications_enabled = self.notification_toggle.isChecked() if hasattr(self, "notification_toggle") else True
        web_view.loginCompleted.connect(
            lambda aid, ok, msg: self._on_account_login_finished(aid, ok, msg, show_dialog=True)
        )
        self._wire_webview(web_view)
        web_view.apply_notifications_enabled(self.notification_toggle.isChecked() if hasattr(self, "notification_toggle") else True)
        self.web_views[account_id] = web_view
        self.webview_pool.register(account_id, web_view)
        self.stack_widget.addWidget(web_view)
        self.stack_widget.setCurrentWidget(web_view)
        self.current_account_id = account_id

    def _on_account_login_finished(
        self, account_id: int, ok: bool, message: str, show_dialog: bool = False
    ):
        acc = self.db.get_account(account_id)
        wv = self._get_webview_for_account(account_id)
        if ok:
            if wv and getattr(wv, "_session_reported", False):
                self.mark_account_logged_in(account_id, message)
                self._refresh_account_dot(account_id)
            elif wv:
                wv._schedule_session_check(0)
                self._refresh_account_dot(account_id)
            else:
                self.mark_account_not_logged_in(account_id, "pending")
        else:
            self.mark_account_not_logged_in(account_id, "failed")
            if wv:
                wv._session_reported = False
            self.load_accounts()
        remark = acc[1] if acc else str(account_id)
        self.update_status(f"{remark}: {message}")
        if show_dialog:
            if ok:
                QMessageBox.information(self, "登录", f"「{remark}」{message}")
            else:
                QMessageBox.warning(self, "登录", f"「{remark}」{message}")
        self._schedule_memory_guard_refresh()

    def _setup_app_tray(self) -> None:
        """启动即显示托盘图标，便于隐藏到任务栏及右键调整关闭方式。"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._ensure_app_tray_icon()

    def _sync_tray_close_action_checks(self) -> None:
        action = (self.db.get_setting(CLOSE_ACTION_SETTING_KEY) or "").strip()
        tray_act = getattr(self, "_tray_act_close_tray", None)
        exit_act = getattr(self, "_tray_act_close_exit", None)
        ask_act = getattr(self, "_tray_act_close_ask", None)
        if tray_act is None or exit_act is None or ask_act is None:
            return
        tray_act.setChecked(action == CloseActionCardDialog.CHOICE_TRAY)
        exit_act.setChecked(action == CloseActionCardDialog.CHOICE_EXIT)
        ask_act.setChecked(
            action not in (
                CloseActionCardDialog.CHOICE_TRAY,
                CloseActionCardDialog.CHOICE_EXIT,
            )
        )

    def _set_saved_close_action(self, action: str) -> None:
        """托盘菜单：设置点 × 时的默认行为（空字符串 = 每次询问）。"""
        act = (action or "").strip()
        if act in (CloseActionCardDialog.CHOICE_TRAY, CloseActionCardDialog.CHOICE_EXIT):
            self.db.set_setting(CLOSE_ACTION_SETTING_KEY, act)
        else:
            self.db.set_setting(CLOSE_ACTION_SETTING_KEY, "")
        self._sync_tray_close_action_checks()

    def _tray_menu_style(self, light: bool) -> str:
        """托盘右键菜单样式：圆角、跟随软件主题色。"""
        if light:
            bg = "#ffffff"
            border = "#e2e5ea"
            text = "#1f2329"
            sep = "#ececf0"
            hover_bg = "#eaf2ff"
            hover_text = "#1a3c66"
            disabled = "#aab0b8"
            accent = "#2f6fed"
        else:
            bg = "#2b2d31"
            border = "#3a3d42"
            text = "#eceef0"
            sep = "#3a3d42"
            hover_bg = "#34507a"
            hover_text = "#eaf2ff"
            disabled = "#7a808a"
            accent = "#5a9cf5"
        return (
            f"QMenu{{background:{bg};border:1px solid {border};border-radius:10px;"
            "padding:6px;}"
            f"QMenu::item{{background:transparent;color:{text};padding:7px 26px 7px 22px;"
            "border-radius:7px;margin:1px 2px;font-size:13px;}"
            f"QMenu::item:selected{{background:{hover_bg};color:{hover_text};}}"
            f"QMenu::item:disabled{{color:{disabled};}}"
            f"QMenu::separator{{height:1px;background:{sep};margin:5px 8px;}}"
            f"QMenu::indicator{{width:16px;height:16px;left:6px;}}"
            f"QMenu::indicator:checked{{background:{accent};border-radius:4px;}}"
            "QMenu::right-arrow{width:10px;height:10px;margin-right:8px;}"
        )

    def _setup_rounded_menu(self, menu: QMenu) -> None:
        """让 QMenu 真正显示圆角：透明窗口背景 + 去掉原生方形阴影。"""
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        menu.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _build_app_tray_menu(self) -> QMenu:
        menu = QMenu(self)
        light = bool(getattr(self, "_theme_light", False))
        style = self._tray_menu_style(light)
        menu.setStyleSheet(style)
        self._setup_rounded_menu(menu)
        self._tray_menu_ref = menu
        self._tray_menu_theme_light = light
        show_act = QAction("显示主窗口", self)
        show_act.triggered.connect(self.show_from_tray)
        menu.addAction(show_act)
        menu.addSeparator()

        self._tray_act_notify = QAction("启用通知", self)
        self._tray_act_notify.setCheckable(True)
        self._tray_act_notify.toggled.connect(self.set_notifications_enabled)
        menu.addAction(self._tray_act_notify)
        menu.addSeparator()

        close_menu = menu.addMenu("关闭方式")
        close_menu.setStyleSheet(style)
        self._setup_rounded_menu(close_menu)
        self._tray_act_close_tray = QAction("隐藏到任务栏", self)
        self._tray_act_close_tray.setCheckable(True)
        self._tray_act_close_exit = QAction("退出软件", self)
        self._tray_act_close_exit.setCheckable(True)
        self._tray_act_close_ask = QAction("每次询问", self)
        self._tray_act_close_ask.setCheckable(True)
        close_group = QActionGroup(self)
        close_group.setExclusive(True)
        for a in (
            self._tray_act_close_tray,
            self._tray_act_close_exit,
            self._tray_act_close_ask,
        ):
            close_group.addAction(a)
        self._tray_act_close_tray.triggered.connect(
            lambda: self._set_saved_close_action(CloseActionCardDialog.CHOICE_TRAY)
        )
        self._tray_act_close_exit.triggered.connect(
            lambda: self._set_saved_close_action(CloseActionCardDialog.CHOICE_EXIT)
        )
        self._tray_act_close_ask.triggered.connect(
            lambda: self._set_saved_close_action("")
        )
        close_menu.addAction(self._tray_act_close_tray)
        close_menu.addAction(self._tray_act_close_exit)
        close_menu.addAction(self._tray_act_close_ask)

        menu.addSeparator()
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self._quit_application)
        menu.addAction(quit_act)
        menu.aboutToShow.connect(self._sync_tray_close_action_checks)
        menu.aboutToShow.connect(self._sync_tray_notification_check)
        menu.aboutToShow.connect(self._sync_tray_menu_theme)
        return menu

    def _sync_tray_menu_theme(self) -> None:
        """仅在主题变化时刷新样式，避免每次弹出重复 polish 造成卡顿。"""
        menu = getattr(self, "_tray_menu_ref", None)
        if menu is None:
            return
        light = bool(getattr(self, "_theme_light", False))
        if getattr(self, "_tray_menu_theme_light", None) == light:
            return
        self._tray_menu_theme_light = light
        style = self._tray_menu_style(light)
        menu.setStyleSheet(style)
        for sub in menu.findChildren(QMenu):
            sub.setStyleSheet(style)

    def _sync_tray_notification_check(self) -> None:
        act = getattr(self, "_tray_act_notify", None)
        if act is None:
            return
        enabled = self._notifications_enabled()
        act.blockSignals(True)
        act.setChecked(enabled)
        act.blockSignals(False)
        act.setText("通知：开" if enabled else "通知：关")

    def _ensure_app_tray_icon(self) -> Optional[QSystemTrayIcon]:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        if self._app_tray_icon is None:
            tray = QSystemTrayIcon(self)
            icon = AppPaths.app_qicon()
            if icon.isNull():
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            tray.setIcon(icon)
            tray.setToolTip("TeamsX")
            tray.setContextMenu(self._build_app_tray_menu())
            tray.activated.connect(self._on_app_tray_activated)
            tray.show()
            self._app_tray_icon = tray
            self._sync_tray_close_action_checks()
            self._sync_tray_notification_check()
        return self._app_tray_icon

    def _on_app_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        ):
            self.show_from_tray()

    def animated_minimize(self) -> None:
        """最小化：直接走系统最小化。"""
        try:
            self.setWindowOpacity(1.0)
        except Exception:
            pass
        self.showMinimized()

    def _restore_window_plain(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        try:
            self.setWindowState(
                (self.windowState() & ~Qt.WindowState.WindowMinimized)
                | Qt.WindowState.WindowActive
            )
        except Exception:
            pass
        try:
            if hasattr(self, "title_bar") and self.title_bar:
                self.title_bar.recheck_expanded_state()
        except Exception:
            pass

    def show_from_tray(self) -> None:
        """从托盘恢复主窗口（也用于单实例二次启动唤醒）。"""
        if self.is_closing or getattr(self, "_shutdown_started", False):
            return
        self._dismiss_close_dialog()
        try:
            self.setWindowOpacity(1.0)
        except Exception:
            pass
        self._restore_window_plain()

    def _hide_to_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.warning(
                self,
                "提示",
                "当前系统托盘不可用，无法隐藏到任务栏，将改为退出软件。",
            )
            self._quit_application()
            return
        tray = self._ensure_app_tray_icon()
        if tray is None:
            self._quit_application()
            return
        self._dismiss_close_dialog()
        self.hide()

    def _resolve_close_action(self) -> Optional[str]:
        action = (self.db.get_setting(CLOSE_ACTION_SETTING_KEY) or "").strip()
        if action in (CloseActionCardDialog.CHOICE_TRAY, CloseActionCardDialog.CHOICE_EXIT):
            return action
        if getattr(self, "_close_dialog_open", False):
            return None
        self._close_dialog_open = True
        dlg = CloseActionCardDialog(self, light=bool(self._theme_light))
        self._close_dialog = dlg
        try:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            # 从托盘“退出”等途径已触发退出时，忽略对话框结果，直接收尾。
            if getattr(self, "_force_quit", False):
                return None
            choice = dlg.choice()
            if choice not in (
                CloseActionCardDialog.CHOICE_TRAY,
                CloseActionCardDialog.CHOICE_EXIT,
            ):
                return None
            if dlg.remember():
                self.db.set_setting(CLOSE_ACTION_SETTING_KEY, choice)
            return choice
        finally:
            self._close_dialog_open = False
            self._close_dialog = None

    def request_close(self) -> None:
        """标题栏关闭：按记住的选择隐藏到托盘或退出。"""
        if getattr(self, "_force_quit", False):
            self.close()
            return
        action = self._resolve_close_action()
        if not action:
            return
        if action == CloseActionCardDialog.CHOICE_TRAY:
            self._hide_to_tray()
        else:
            self._quit_application()

    def _shutdown_single_instance_server(self) -> None:
        """真正退出前立即释放单实例监听，避免退出过程中再次双击连到濒死实例无反应。"""
        app = QApplication.instance()
        server = getattr(app, "_teamsx_single_instance_server", None) if app else None
        if server is not None:
            try:
                server.close()
            except Exception:
                pass
            try:
                app._teamsx_single_instance_server = None
            except Exception:
                pass
        try:
            from teamsx.single_instance import SERVER_NAME
            from PyQt6.QtNetwork import QLocalServer

            QLocalServer.removeServer(SERVER_NAME)
        except Exception:
            pass

    def _dismiss_close_dialog(self) -> None:
        """关掉可能还开着的“关闭方式”选择卡片（例如从托盘退出/恢复时）。"""
        dlg = getattr(self, "_close_dialog", None)
        if dlg is not None:
            try:
                dlg.reject()
            except Exception:
                pass
            try:
                dlg.close()
            except Exception:
                pass
        self._close_dialog = None
        self._close_dialog_open = False

    def _quit_application(self) -> None:
        self._force_quit = True
        self._dismiss_close_dialog()
        self._shutdown_single_instance_server()
        tray = getattr(self, "_app_tray_icon", None)
        if tray is not None:
            try:
                tray.hide()
            except Exception:
                pass
        self.close()

    def closeEvent(self, event):
        """关闭事件：托盘隐藏时不退出；真正退出时异步释放 WebView。"""
        if getattr(self, "_shutdown_finished", False):
            event.accept()
            return
        if not getattr(self, "_force_quit", False):
            event.ignore()
            QTimer.singleShot(0, self.request_close)
            return
        if not getattr(self, "_shutdown_started", False):
            self._shutdown_started = True
            self.is_closing = True
            try:
                self.hide()
            except Exception:
                pass
            event.ignore()
            QTimer.singleShot(0, self._deferred_shutdown)
            return
        event.accept()

    def _deferred_shutdown(self):
        try:
            if self._cache_clean_thread and self._cache_clean_thread.isRunning():
                self._cache_clean_thread.quit()
                self._cache_clean_thread.wait(3000)

            if self.check_timer:
                self.check_timer.stop()
                self.check_timer = None

            if self.memory_timer:
                self.memory_timer.stop()
                self.memory_timer = None

            if getattr(self, "_memory_guard_timer", None):
                self._memory_guard_timer.stop()
                self._memory_guard_timer = None

            if getattr(self, "_memory_light_timer", None):
                self._memory_light_timer.stop()
                self._memory_light_timer = None

            if getattr(self, "_memory_guard_debounce_timer", None):
                self._memory_guard_debounce_timer.stop()
                self._memory_guard_debounce_timer = None

            if getattr(self, "_memory_groom_timer", None):
                self._memory_groom_timer.stop()
                self._memory_groom_timer = None

            if getattr(self, "_notify_waker_timer", None):
                self._notify_waker_timer.stop()
                self._notify_waker_timer = None

            if getattr(self, "badge_fast_timer", None):
                self.badge_fast_timer.stop()
                self.badge_fast_timer = None

            if getattr(self, "badge_background_timer", None):
                self.badge_background_timer.stop()
                self.badge_background_timer = None

            if getattr(self, "_daily_cache_timer", None):
                self._daily_cache_timer.stop()
                self._daily_cache_timer = None

            chrome_timer = getattr(self, "_chrome_mask_timer", None)
            if chrome_timer is not None:
                chrome_timer.stop()

            for timer in list(self._badge_debounce_timers.values()):
                timer.stop()
                timer.deleteLater()
            self._badge_debounce_timers.clear()
            self._badge_pending.clear()

            for account_id in list(self.web_views.keys()):
                self.unload_webview(account_id)
            for account_id in list(self.suspended_webviews.keys()):
                self.unload_webview(account_id)

            self.webview_pool.clear()
            self.badge_cache.clear()
            badge = getattr(self, "_taskbar_badge", None)
            if badge is not None:
                badge.dispose()

            self._shutdown_finished = True
            print("Teams 管理器已关闭")
            self.close()
            self._force_process_exit()
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            self._shutdown_finished = True
            self.close()
            self._force_process_exit()

    def _force_process_exit(self) -> None:
        """确保进程真正退出：先优雅退出事件循环，再硬退出兜底。

        PyQt6 + WebView2(COM) 组合常因后台 COM/线程未释放导致 app.exec() 返回后
        python 主进程挂住（任务管理器里残留无子进程的空壳）。硬退出杜绝残留。
        """
        try:
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass

        def _hard_exit() -> None:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            os._exit(0)

        # 给 Qt 一点时间处理最后的关闭事件，再强制结束进程
        QTimer.singleShot(600, _hard_exit)

# ==================== 主程序入口 ====================

if __name__ == "__main__":
    from teamsx.__main__ import main

    main()
