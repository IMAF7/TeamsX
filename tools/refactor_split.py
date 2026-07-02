# -*- coding: utf-8 -*-
"""One-shot split TeamsX.py monolith into teamsx package."""
from __future__ import annotations

import os
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "TeamsX.py")
OUT_APP = os.path.join(ROOT, "teamsx", "application.py")
OUT_MAIN = os.path.join(ROOT, "teamsx", "__main__.py")
OUT_STARTUP = os.path.join(ROOT, "teamsx", "startup.py")
OUT_BOOT = os.path.join(ROOT, "teamsx", "bootstrap", "qtwebengine_media.py")
OUT_BOOT_INIT = os.path.join(ROOT, "teamsx", "bootstrap", "__init__.py")
OUT_LAUNCHER = os.path.join(ROOT, "TeamsX.py")

with open(SRC, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 1-based line slices from original TeamsX.py
BOOT_START, BOOT_END = 76, 621
APP_START, APP_END = 685, 9228  # constants through MainWindow end

boot_body = "".join(lines[BOOT_START - 1 : BOOT_END])
app_body = "".join(lines[APP_START - 1 : APP_END])

boot_module = '''# -*- coding: utf-8 -*-
"""Qt WebEngine 回退路径：Widevine + ffmpeg（WebView2 默认路径不加载本模块）。"""
from __future__ import annotations

import glob
import os
import re
import shutil
import sys
from typing import List, Optional, Set, Tuple

from teamsx.config import DATA_ROOT

''' + boot_body.replace("_TEAMS_DATA_ROOT_EARLY", "DATA_ROOT")

boot_module = boot_module.replace(
    "def _bootstrap_webengine_media_pyqt_bins() -> None:",
    "def bootstrap_webengine_media_pyqt_bins() -> None:",
)
boot_module = boot_module.replace(
    "def _bootstrap_webengine_media() -> None:",
    "def bootstrap_webengine_media() -> None:",
)

startup_module = '''# -*- coding: utf-8 -*-
"""启动前运行时准备（引擎选择、SSL、条件性 Qt 媒体 bootstrap）。"""
from __future__ import annotations

import sys

from teamsx.config import PREFER_WEBVIEW2


def prepare_runtime() -> str:
    """在 QApplication 之前调用。返回引擎名 webview2 | qtwebengine。"""
    engine = "qtwebengine"
    has_engine = False
    use_wv2 = lambda: False  # noqa: E731

    if PREFER_WEBVIEW2:
        stat = "[TeamsX] Teams 页面引擎: WebView2（需 pip install qtwebview2）"
        print(stat)
        try:
            from teams_engine import use_webview2, teams_engine_name, apply_webview2_runtime_env

            apply_webview2_runtime_env()
            has_engine = True
            use_wv2 = use_webview2
            if use_webview2():
                engine = teams_engine_name()
        except ImportError:
            pass
    else:
        from teamsx.bootstrap.qtwebengine_media import bootstrap_webengine_media

        bootstrap_webengine_media()

    if PREFER_WEBVIEW2 and not (has_engine and use_wv2()):
        from teamsx.bootstrap.qtwebengine_media import bootstrap_webengine_media

        bootstrap_webengine_media()
        engine = "qtwebengine"
    elif not PREFER_WEBVIEW2:
        engine = "qtwebengine"

    from teamsx.bootstrap.ssl import bootstrap_ssl_certs

    bootstrap_ssl_certs()

    if has_engine:
        try:
            from teams_engine import teams_engine_name

            print(f"[TeamsX] 当前 Teams 引擎: {teams_engine_name()}")
        except Exception:
            print(f"[TeamsX] 当前 Teams 引擎: {engine}")
    else:
        print(f"[TeamsX] 当前 Teams 引擎: {engine}")

  if not (PREFER_WEBVIEW2 and has_engine and use_wv2()):
        from teamsx.bootstrap.qtwebengine_media import bootstrap_webengine_media_pyqt_bins

        bootstrap_webengine_media_pyqt_bins()

    return engine
'''

# fix typo in startup - extra space before if
startup_module = startup_module.replace("\n  if not", "\n    if not")

app_header = '''# -*- coding: utf-8 -*-
"""TeamsX 主应用（UI、账号、Teams 页面、AI）。"""
from __future__ import annotations

import sys
import os
import json
import locale
import re
import base64
import glob
from urllib.parse import quote
import urllib.error
import urllib.request
import ssl
import sqlite3
import shutil
import random
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

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QPushButton, QLabel,
    QDialog, QLineEdit, QFormLayout, QMessageBox, QSplitter, QFileDialog,
    QMenu, QCheckBox, QScrollArea, QComboBox, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QTextEdit,
    QSizePolicy, QFrame, QAbstractScrollArea,
)
from PyQt6.QtGui import (
    QAction, QFont, QColor, QBrush, QCursor, QGuiApplication, QImage,
    QPixmap, QIcon, QPainter, QFontMetrics, QTextCursor, QTextBlockFormat,
    QDesktopServices,
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QPoint, QRect, QSize, pyqtSignal, QObject, pyqtSlot,
    QFile, QIODevice, QThread, QEvent,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineScript,
    QWebEngineSettings, qWebEngineVersion,
)
from PyQt6.QtWebChannel import QWebChannel

from teamsx.config import DATA_ROOT as _TEAMS_DATA_ROOT_EARLY

try:
    from teams_engine import (
        use_webview2,
        teams_engine_name,
        create_webview2_widget,
        bridge_connect_js_webview2,
        WebView2PageAdapter,
        apply_webview2_runtime_env,
    )
    _HAS_TEAMS_ENGINE = True
except ImportError:
    use_webview2 = lambda: False  # type: ignore
    teams_engine_name = lambda: "qtwebengine"  # type: ignore
    bridge_connect_js_webview2 = None  # type: ignore
    create_webview2_widget = None  # type: ignore
    WebView2PageAdapter = None  # type: ignore
    apply_webview2_runtime_env = lambda: None  # type: ignore
    _HAS_TEAMS_ENGINE = False

try:
    _QT_WEBENGINE_CHROMIUM_VERSION = str(qWebEngineVersion() or "")
except Exception:
    _QT_WEBENGINE_CHROMIUM_VERSION = ""

try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    certifi = None  # type: ignore
    HAS_CERTIFI = False

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

from teamsx.config import PREFER_WEBVIEW2 as _TEAMSX_PREFER_WEBVIEW2

'''

# Replace teams edge UA helper reference - was in bootstrap, app may need it
app_body = app_body.replace(
    "_teams_edge_user_agent",
    "_teams_edge_user_agent",
)

# Add import for edge UA from bootstrap in application if used
if "_teams_edge_user_agent" in app_body:
    app_header += "from teamsx.bootstrap.qtwebengine_media import _teams_edge_user_agent\n\n"

app_module = app_header + app_body

# Add run_app at end
app_module += '''

def run_app() -> None:
    app = QApplication(sys.argv)
    font = QFont()
    font.setPointSize(9)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
'''

main_module = '''# -*- coding: utf-8 -*-
"""python -m teamsx"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox


def main() -> None:
    try:
        from teamsx.startup import prepare_runtime
        from teamsx.application import run_app

        prepare_runtime()
        run_app()
    except Exception as e:
        print(f"程序启动失败: {e}")
        try:
            QMessageBox.critical(None, "启动失败", f"程序无法启动: {str(e)}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

ssl_module = '''# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import ssl

try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    certifi = None  # type: ignore
    HAS_CERTIFI = False


def bootstrap_ssl_certs() -> None:
    cafile = ""
    if HAS_CERTIFI:
        try:
            cafile = certifi.where()
        except Exception:
            cafile = ""
    if cafile and os.path.isfile(cafile):
        os.environ.setdefault("SSL_CERT_FILE", cafile)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
        print(f"[SSL] 使用 CA 证书: {cafile}")
        return
    print("[SSL] 未找到 certifi CA 包，HTTPS 请求可能失败（pip install certifi）")


def urllib_ssl_context() -> ssl.SSLContext:
    if HAS_CERTIFI:
        try:
            cafile = certifi.where()
            if cafile and os.path.isfile(cafile):
                return ssl.create_default_context(cafile=cafile)
        except Exception:
            pass
    return ssl.create_default_context()
'''

boot_init = '''# -*- coding: utf-8 -*-
from teamsx.bootstrap.qtwebengine_media import (
    bootstrap_webengine_media,
    bootstrap_webengine_media_pyqt_bins,
)
from teamsx.bootstrap.ssl import bootstrap_ssl_certs, urllib_ssl_context

__all__ = [
    "bootstrap_webengine_media",
    "bootstrap_webengine_media_pyqt_bins",
    "bootstrap_ssl_certs",
    "urllib_ssl_context",
]
'''

launcher = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TeamsX 启动入口（实现位于 teamsx 包）。"""
from teamsx.__main__ import main

if __name__ == "__main__":
    main()
'''

os.makedirs(os.path.join(ROOT, "teamsx", "bootstrap"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "tools"), exist_ok=True)

with open(OUT_BOOT, "w", encoding="utf-8", newline="\n") as f:
    f.write(boot_module)
with open(OUT_BOOT_INIT, "w", encoding="utf-8", newline="\n") as f:
    f.write(boot_init)
with open(os.path.join(ROOT, "teamsx", "bootstrap", "ssl.py"), "w", encoding="utf-8", newline="\n") as f:
    f.write(ssl_module)
with open(OUT_STARTUP, "w", encoding="utf-8", newline="\n") as f:
    f.write(startup_module)
with open(OUT_APP, "w", encoding="utf-8", newline="\n") as f:
    f.write(app_module)
with open(OUT_MAIN, "w", encoding="utf-8", newline="\n") as f:
    f.write(main_module)
with open(OUT_LAUNCHER, "w", encoding="utf-8", newline="\n") as f:
    f.write(launcher)

print("Wrote:", OUT_BOOT, OUT_APP, OUT_MAIN, OUT_STARTUP, OUT_LAUNCHER)
