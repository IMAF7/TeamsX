# -*- coding: utf-8 -*-
"""本机单实例：重复启动时唤醒已有窗口。"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable, List, Optional

from PyQt6.QtCore import QByteArray
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "TeamsX-SingleInstance-v1"
_TEAMSX_CMD_MARKERS = ("teamsx.py", "teamsx\\__main__", "teamsx/__main__", "-m teamsx")


def _command_line_looks_like_teamsx(command_line: str) -> bool:
    line = (command_line or "").lower().replace("/", "\\")
    return any(marker.replace("/", "\\") in line for marker in _TEAMSX_CMD_MARKERS)


def find_other_teamsx_pids() -> List[int]:
    """返回本机其他 TeamsX 主进程 pid（python/pythonw 运行 TeamsX）。"""
    if sys.platform != "win32":
        return []
    me = int(os.getpid())
    pids: List[int] = []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [
                "wmic",
                "process",
                "where",
                "name='python.exe' or name='pythonw.exe'",
                "get",
                "ProcessId,CommandLine",
                "/format:list",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
            creationflags=flags,
        )
        if proc.returncode != 0:
            return []
        cur_pid = 0
        cur_cmd = ""
        for raw in (proc.stdout or "").splitlines():
            line = raw.strip()
            if not line:
                if (
                    cur_pid > 0
                    and cur_pid != me
                    and _command_line_looks_like_teamsx(cur_cmd)
                ):
                    pids.append(cur_pid)
                cur_pid = 0
                cur_cmd = ""
                continue
            if line.startswith("ProcessId="):
                try:
                    cur_pid = int(line.split("=", 1)[1].strip() or "0")
                except ValueError:
                    cur_pid = 0
            elif line.startswith("CommandLine="):
                cur_cmd = line.split("=", 1)[1].strip()
        if (
            cur_pid > 0
            and cur_pid != me
            and _command_line_looks_like_teamsx(cur_cmd)
        ):
            pids.append(cur_pid)
    except Exception:
        return []
    return sorted(set(pids))


def terminate_pids(pids: List[int]) -> int:
    """强制结束给定 pid（用于清理残留 TeamsX 空壳进程）。返回成功数。"""
    if sys.platform != "win32" or not pids:
        return 0
    me = int(os.getpid())
    killed = 0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for pid in pids:
        if int(pid) == me or int(pid) <= 0:
            continue
        try:
            proc = subprocess.run(
                ["taskkill", "/F", "/PID", str(int(pid))],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=flags,
            )
            if proc.returncode == 0:
                killed += 1
        except Exception:
            continue
    return killed


def try_activate_existing_instance(timeout_ms: int = 800) -> bool:
    """若已有实例在运行，发送唤醒并返回 True。"""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(QByteArray(b"show"))
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


def start_single_instance_listener(on_activate: Callable[[], None]) -> Optional[QLocalServer]:
    """启动本地监听；返回 server 对象（需保持引用）。"""
    server = QLocalServer()

    def _handle_new_connection() -> None:
        if server is None:
            return
        conn = server.nextPendingConnection()
        if conn is None:
            return

        def _read() -> None:
            try:
                data = bytes(conn.readAll()).decode("utf-8", errors="ignore")
            except Exception:
                data = ""
            if "show" in data:
                try:
                    on_activate()
                except Exception as e:
                    print(f"唤醒已有实例失败: {e}")
            conn.disconnectFromServer()

        conn.readyRead.connect(_read)

    try:
        QLocalServer.removeServer(SERVER_NAME)
    except Exception:
        pass
    if not server.listen(SERVER_NAME):
        # 监听失败时尝试清掉陈旧 socket 再试一次
        try:
            QLocalServer.removeServer(SERVER_NAME)
        except Exception:
            pass
        if not server.listen(SERVER_NAME):
            print(f"单实例监听启动失败: {server.errorString()}")
            return None
    server.newConnection.connect(_handle_new_connection)
    return server
