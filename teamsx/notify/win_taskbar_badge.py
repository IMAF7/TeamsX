# -*- coding: utf-8 -*-
"""Windows 任务栏数字未读角标（ITaskbarList4::SetOverlayIcon）。"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
from ctypes import HRESULT, POINTER, WINFUNCTYPE, byref, c_void_p, c_wchar_p, wintypes
from typing import Optional

from PyQt6.QtCore import QBuffer, QIODevice, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap

BADGE_RED = "#e53935"

# Win10+ 上 ITaskbarList3 直接 CoCreate 会 E_NOINTERFACE，ITaskbarList4 可用。
_CLSID_TASKBAR_LIST = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
_IID_ITASKBAR_LIST4 = "{C43DC798-95D1-4BEA-9030-BB99E2983A1A}"
_CLSCTX_INPROC_SERVER = 1
_VTBL_HR_INIT = 3
_VTBL_SET_OVERLAY_ICON = 18
_VTBL_RELEASE = 2
_OVERLAY_ICON_SIZE = 16


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def _guid_from(uuid_str: str) -> _GUID:
    g = _GUID()
    ctypes.windll.ole32.IIDFromString(ctypes.c_wchar_p(uuid_str), byref(g))
    return g


def _badge_text(count: int) -> str:
    return "99+" if count > 99 else str(count)


def _make_overlay_pixmap(count: int) -> QPixmap:
    text = _badge_text(count)
    if len(text) == 1:
        w, h, font_px = 16, 16, 11
    elif len(text) == 2:
        w, h, font_px = 20, 16, 9
    else:
        w, h, font_px = 24, 16, 7

    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BADGE_RED))
    painter.drawRoundedRect(0, 0, w, h, h // 2, h // 2)

    font = QFont()
    font.setBold(True)
    font.setPixelSize(font_px)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pix


def _pixmap_to_hicon(pixmap: QPixmap) -> int:
    import win32con
    import win32gui

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pixmap.save(buffer, b"ICO"):
        raise OSError("无法生成角标 ICO")
    data = bytes(buffer.data())

    fd, path = tempfile.mkstemp(suffix=".ico")
    os.close(fd)
    try:
        with open(path, "wb") as fh:
            fh.write(data)
        hicon = win32gui.LoadImage(
            0,
            path,
            win32con.IMAGE_ICON,
            _OVERLAY_ICON_SIZE,
            _OVERLAY_ICON_SIZE,
            win32con.LR_LOADFROMFILE,
        )
        if not hicon:
            raise OSError("LoadImage 失败")
        return int(hicon)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _ensure_com_initialized() -> None:
    try:
        import pythoncom

        pythoncom.CoInitialize()
    except Exception:
        pass


def _set_overlay_icon(hwnd: int, hicon: int, description: str) -> bool:
    if not hwnd:
        return False

    _ensure_com_initialized()
    ole32 = ctypes.windll.ole32
    obj = c_void_p()
    hr = ole32.CoCreateInstance(
        byref(_guid_from(_CLSID_TASKBAR_LIST)),
        None,
        _CLSCTX_INPROC_SERVER,
        byref(_guid_from(_IID_ITASKBAR_LIST4)),
        byref(obj),
    )
    if hr or not obj.value:
        print(f"[任务栏角标] CoCreateInstance 失败: {hex(hr & 0xFFFFFFFF)}")
        return False

    vtbl_fns = ctypes.cast(
        ctypes.cast(obj.value, POINTER(c_void_p)).contents.value,
        POINTER(c_void_p),
    )

    fn_hr_init = WINFUNCTYPE(HRESULT, c_void_p)(vtbl_fns[_VTBL_HR_INIT])
    init_hr = fn_hr_init(obj.value)
    if init_hr:
        print(f"[任务栏角标] HrInit 失败: {hex(init_hr & 0xFFFFFFFF)}")

    fn_set_overlay = WINFUNCTYPE(
        HRESULT, c_void_p, c_void_p, c_void_p, c_wchar_p
    )(vtbl_fns[_VTBL_SET_OVERLAY_ICON])
    overlay_hr = fn_set_overlay(
        obj.value,
        c_void_p(hwnd),
        c_void_p(hicon or 0),
        description,
    )

    fn_release = WINFUNCTYPE(wintypes.ULONG, c_void_p)(vtbl_fns[_VTBL_RELEASE])
    fn_release(obj.value)
    if overlay_hr:
        print(f"[任务栏角标] SetOverlayIcon 失败: {hex(overlay_hr & 0xFFFFFFFF)}")
        return False
    return True


class TaskbarBadgeController:
    """在任务栏按钮右下角叠加数字未读角标。"""

    def __init__(self) -> None:
        self._hwnd: int = 0
        self._hicon: int = 0
        self._last_count: int = -1

    def bind_hwnd(self, hwnd: int) -> None:
        self._hwnd = int(hwnd or 0)

    def clear(self) -> None:
        self.update(0)

    def update(self, count: int) -> None:
        if sys.platform != "win32":
            return

        count = max(0, int(count))
        if count == self._last_count:
            return
        if not self._hwnd:
            return

        import win32gui

        try:
            if count <= 0:
                if _set_overlay_icon(self._hwnd, 0, ""):
                    if self._hicon:
                        win32gui.DestroyIcon(self._hicon)
                        self._hicon = 0
                    self._last_count = 0
                return

            pixmap = _make_overlay_pixmap(count)
            new_hicon = _pixmap_to_hicon(pixmap)
            desc = f"{count} 条未读消息" if count <= 99 else "99+ 条未读消息"
            if not _set_overlay_icon(self._hwnd, new_hicon, desc):
                win32gui.DestroyIcon(new_hicon)
                return

            if self._hicon:
                win32gui.DestroyIcon(self._hicon)
            self._hicon = new_hicon
            self._last_count = count
        except Exception as e:
            print(f"[任务栏角标] 更新失败: {e}")

    def dispose(self) -> None:
        if sys.platform != "win32":
            return
        try:
            if self._hwnd:
                _set_overlay_icon(self._hwnd, 0, "")
            if self._hicon:
                import win32gui

                win32gui.DestroyIcon(self._hicon)
                self._hicon = 0
            self._last_count = -1
            self._hwnd = 0
        except Exception as e:
            print(f"[任务栏角标] 清理失败: {e}")


_controller: Optional[TaskbarBadgeController] = None


def get_taskbar_badge_controller() -> TaskbarBadgeController:
    global _controller
    if _controller is None:
        _controller = TaskbarBadgeController()
    return _controller
