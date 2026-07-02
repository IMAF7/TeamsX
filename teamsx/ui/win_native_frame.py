# -*- coding: utf-8 -*-
"""Windows 原生窗口边框（自绘客户区）支持。

目标：保留自定义标题栏外观的同时，拿到系统 DWM 提供的最小化/最大化/还原
动画、Aero Snap 贴边、原生阴影与圆角——与大型软件（Chrome / VSCode / QQ）一致。

做法（经典 “native frame, custom client” 技术）：
- 窗口保留原生 Win32 样式（WS_CAPTION | WS_THICKFRAME | WS_MIN/MAXIMIZEBOX），
  这样 DWM 才会给最小化/最大化/还原动画。
- 处理 WM_NCCALCSIZE 把可见的系统边框/标题栏“吃掉”，使整窗成为客户区，
  从而能画自定义标题栏。
- 处理 WM_NCHITTEST 实现窗口四边/四角缩放（系统级，丝滑）。
- 用 DwmExtendFrameIntoClientArea + Win11 圆角属性提供原生阴影与圆角。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Optional, Tuple

# Window messages
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_GETMINMAXINFO = 0x0024

# Hit-test results
HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

# System metrics
SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

# DWM
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

RESIZE_BORDER = 8  # 缩放热区像素宽度（逻辑像素 * 缩放，简单起见用物理像素近似）


class _MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


class _NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [
        ("rgrc", wintypes.RECT * 3),
        ("lppos", ctypes.c_void_p),
    ]


def is_supported() -> bool:
    return sys.platform == "win32"


def _user32():
    return ctypes.windll.user32


def _dwmapi():
    return ctypes.windll.dwmapi


def apply_native_frame(hwnd: int) -> None:
    """开启 DWM 阴影 + Win11 圆角。"""
    if not is_supported() or not hwnd:
        return
    try:
        margins = _MARGINS(1, 1, 1, 1)
        _dwmapi().DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))
    except Exception:
        pass
    try:
        pref = ctypes.c_int(DWMWCP_ROUND)
        _dwmapi().DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(pref),
            ctypes.sizeof(pref),
        )
    except Exception:
        pass


def _is_maximized(hwnd: int) -> bool:
    try:
        return bool(_user32().IsZoomed(wintypes.HWND(hwnd)))
    except Exception:
        return False


def _frame_thickness() -> Tuple[int, int]:
    try:
        u = _user32()
        cx = u.GetSystemMetrics(SM_CXSIZEFRAME) + u.GetSystemMetrics(SM_CXPADDEDBORDER)
        cy = u.GetSystemMetrics(SM_CYSIZEFRAME) + u.GetSystemMetrics(SM_CXPADDEDBORDER)
        return int(cx), int(cy)
    except Exception:
        return 8, 8


def handle_nc_message(
    hwnd: int,
    msg: int,
    wparam: int,
    lparam: int,
    *,
    border: int = RESIZE_BORDER,
) -> Optional[int]:
    """处理与原生边框相关的窗口消息。

    返回 None 表示不拦截（交回默认处理）；返回 int 表示拦截并作为消息结果。
    """
    if msg == WM_NCCALCSIZE:
        if wparam:
            # 去掉系统非客户区：整窗当作客户区。
            # 最大化时窗口会比工作区大出一圈边框，需内缩，避免内容被裁/盖住任务栏。
            if _is_maximized(hwnd):
                try:
                    params = ctypes.cast(
                        lparam, ctypes.POINTER(_NCCALCSIZE_PARAMS)
                    ).contents
                    cx, cy = _frame_thickness()
                    params.rgrc[0].left += cx
                    params.rgrc[0].top += cy
                    params.rgrc[0].right -= cx
                    params.rgrc[0].bottom -= cy
                except Exception:
                    pass
            return 0
        return None

    if msg == WM_NCHITTEST:
        try:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            rect = wintypes.RECT()
            _user32().GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
            if _is_maximized(hwnd):
                return None  # 最大化时不做边缘缩放
            left = x < rect.left + border
            right = x >= rect.right - border
            top = y < rect.top + border
            bottom = y >= rect.bottom - border
            if top and left:
                return HTTOPLEFT
            if top and right:
                return HTTOPRIGHT
            if bottom and left:
                return HTBOTTOMLEFT
            if bottom and right:
                return HTBOTTOMRIGHT
            if left:
                return HTLEFT
            if right:
                return HTRIGHT
            if top:
                return HTTOP
            if bottom:
                return HTBOTTOM
        except Exception:
            return None
        return None  # 非边缘 → 交回默认（标题栏拖动等由上层处理）

    return None
