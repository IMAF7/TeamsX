# -*- coding: utf-8 -*-
"""Windows 10/11 原生 Toast：专用于语音/视频来电（静音，铃声由软件播放）。"""
from __future__ import annotations

import base64
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import xml.sax.saxutils as xml_escape
from typing import Optional

APP_USER_MODEL_ID = "TeamsX.TeamsX.CallNotify"
DISMISS_FLAG_DIR = os.path.join(os.environ.get("TEMP", "."), "teamsx_call_dismiss")
_app_id_set = False
_shortcut_exe_path: Optional[str] = None
_app_id_lock = threading.Lock()


def ensure_app_user_model_id() -> None:
    """须在首个 Toast 前调用，打包 exe 才能显示正确应用名与图标。"""
    global _app_id_set
    if sys.platform != "win32":
        return
    with _app_id_lock:
        if _app_id_set:
            return
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
            _app_id_set = True
        except Exception as e:
            print(f"[来电Toast] 设置 AppUserModelID 失败: {e}")


def ensure_toast_shortcut(
    exe_path: Optional[str] = None,
    icon_path: Optional[str] = None,
) -> None:
    """开始菜单快捷方式 + AppUserModelID，否则 Toast 可能不显示。"""
    global _shortcut_exe_path
    if sys.platform != "win32":
        return
    if not exe_path:
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
        elif sys.argv and os.path.isfile(os.path.abspath(sys.argv[0])):
            exe_path = os.path.abspath(sys.argv[0])
        else:
            exe_path = sys.executable
    exe_path = os.path.abspath(exe_path)
    if not os.path.isfile(exe_path):
        return
    with _app_id_lock:
        if _shortcut_exe_path == exe_path:
            return
        try:
            import pythoncom
            import win32com.client
            from win32com.propsys import propsys, pscon
            from win32com.shell import shell, shellcon

            start_menu = shell.SHGetFolderPath(0, shellcon.CSIDL_STARTMENU, None, 0)
            lnk_path = os.path.join(start_menu, "Programs", "TeamsX.lnk")
            sc = win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk_path)
            sc.Targetpath = exe_path
            sc.WorkingDirectory = os.path.dirname(exe_path)
            if icon_path and os.path.isfile(icon_path):
                sc.IconLocation = icon_path
            sc.Save()

            store = propsys.SHGetPropertyStoreFromParsingName(
                lnk_path,
                None,
                shellcon.GPS_READWRITE,
                propsys.IID_IPropertyStore,
            )
            store.SetValue(
                pscon.PKEY_AppUserModel_ID,
                propsys.PROPVARIANTType(APP_USER_MODEL_ID, pythoncom.VT_LPWSTR),
            )
            store.Commit()
            _shortcut_exe_path = exe_path
        except Exception as e:
            print(f"[来电Toast] 注册开始菜单快捷方式失败: {e}")


def call_toast_tag(account_id: int) -> str:
    return f"teamsx-call-{int(account_id)}"


def dismiss_flag_path(account_id: int) -> str:
    os.makedirs(DISMISS_FLAG_DIR, exist_ok=True)
    return os.path.join(DISMISS_FLAG_DIR, f"{call_toast_tag(account_id)}.flag")


def clear_dismiss_flag(account_id: int) -> None:
    path = dismiss_flag_path(account_id)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _xml_text(value: str) -> str:
    return xml_escape.escape(value or "", {'"': "&quot;", "'": "&apos;"})


def _build_toast_xml(
    *,
    title: str,
    body: str,
    tag: str,
    icon_path: Optional[str] = None,
) -> str:
    logo = ""
    if icon_path and os.path.isfile(icon_path):
        logo = (
            f'<image placement="appLogoOverride" src="file:///'
            f'{_xml_text(os.path.abspath(icon_path).replace(chr(92), "/"))}"/>'
        )
    return (
        f'<toast scenario="incomingCall" activationType="foreground" '
        f'duration="long" tag="{_xml_text(tag)}">'
        "<visual>"
        '<binding template="ToastGeneric">'
        f"<text>{_xml_text(title)}</text>"
        f"<text>{_xml_text(body)}</text>"
        f"{logo}"
        "</binding>"
        "</visual>"
        '<audio silent="true"/>'
        "</toast>"
    )


def _powershell_exe() -> str:
    for name in ("powershell.exe", "pwsh.exe"):
        found = shutil.which(name)
        if found:
            return found
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = [
        os.path.join(windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(windir, "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return "powershell.exe"


def _show_toast_sync(xml_content: str, *, dismiss_flag: str) -> bool:
    """同步显示 Toast（XML 内嵌 base64，避免临时文件被提前删除）。"""
    b64 = base64.b64encode(xml_content.encode("utf-8")).decode("ascii")
    flag_ps = dismiss_flag.replace("\\", "\\\\")
    flag_dir_ps = os.path.dirname(dismiss_flag).replace("\\", "\\\\")
    ps_script = f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$null = [Windows.Foundation.TypedEventHandler`2[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications.ToastDismissedEventArgs], Windows.Foundation, ContentType = WindowsRuntime]
New-Item -ItemType Directory -Force -Path '{flag_dir_ps}' | Out-Null
if (Test-Path -LiteralPath '{flag_ps}') {{ Remove-Item -LiteralPath '{flag_ps}' -Force }}
$bytes = [Convert]::FromBase64String('{b64}')
$xmlText = [Text.Encoding]::UTF8.GetString($bytes)
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($xmlText)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$onDismissed = [Windows.Foundation.TypedEventHandler[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications.ToastDismissedEventArgs]]{{
    param($sender, $args)
    [System.IO.File]::WriteAllText('{flag_ps}', 'dismissed')
}}
$toast.add_Dismissed($onDismissed)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{APP_USER_MODEL_ID}')
$notifier.Show($toast)
'OK'
"""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=creationflags,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            if err:
                print(f"[来电Toast] 显示失败: {err[:400]}")
            return False
        return "OK" in (proc.stdout or "")
    except Exception as e:
        print(f"[来电Toast] 显示失败: {e}")
        return False


def _spawn_dismiss_watcher(dismiss_flag: str) -> None:
    """后台监听用户手动关闭 Toast。"""
    flag_ps = dismiss_flag.replace("\\", "\\\\")
    ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$deadline = (Get-Date).AddMinutes(12)
while ((Get-Date) -lt $deadline) {{
    if (Test-Path -LiteralPath '{flag_ps}') {{ break }}
    Start-Sleep -Milliseconds 400
}}
"""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [
                _powershell_exe(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            creationflags=creationflags,
            close_fds=True,
        )
    except Exception:
        pass


def remove_call_toast(account_id: int) -> None:
    if sys.platform != "win32":
        return
    tag = call_toast_tag(account_id)
    ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotificationManager]::History.Remove('{tag}')
"""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [_powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            timeout=5,
            creationflags=creationflags,
        )
    except Exception:
        pass


def show_incoming_call_toast(
    *,
    caller: str,
    call_kind: str,
    account_label: str,
    account_id: int,
    icon_path: Optional[str] = None,
    exe_path: Optional[str] = None,
) -> bool:
    if sys.platform != "win32":
        return False
    ensure_app_user_model_id()
    ensure_toast_shortcut(exe_path=exe_path, icon_path=icon_path)
    who = (caller or "").strip() or "某人"
    acct = (account_label or "").strip() or f"账号 {account_id}"
    if call_kind == "video":
        kind_label = "视频来电"
        subtitle = "邀请你视频通话"
    else:
        kind_label = "语音来电"
        subtitle = "邀请你语音通话"
    title = f"{who} · {kind_label}"
    body = f"TeamsX · {acct} — {subtitle}"
    tag = call_toast_tag(account_id)
    xml_content = _build_toast_xml(
        title=title,
        body=body,
        tag=tag,
        icon_path=icon_path,
    )
    flag = dismiss_flag_path(account_id)
    clear_dismiss_flag(account_id)
    ok = _show_toast_sync(xml_content, dismiss_flag=flag)
    if ok:
        _spawn_dismiss_watcher(flag)
    return ok
