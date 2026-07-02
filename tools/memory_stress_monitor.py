# -*- coding: utf-8 -*-
"""
TeamsX 20 账号内存/性能压测辅助脚本。

用法（在 TeamsX 已打开 20 个账号后另开终端运行）:
  python tools/memory_stress_monitor.py --duration 1800 --interval 30

输出 CSV 列：时间、可用内存MB、WebView2进程数、WebView2总内存MB、TeamsX进程数

验收标准（计划）:
  1. 后台账号收到消息后 1-3 秒内本机提示音/Toast
  2. 温态账号点开不触发 load_teams / hard_reload_teams
  3. 30 分钟内 msedgewebview2 总内存不持续单调上涨
  4. 前台切换、来电、通知开关不回退
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path


def _system_free_mb() -> int:
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


def _process_stats(image_name: str) -> tuple[int, int]:
    if sys.platform != "win32":
        return 0, 0
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=flags,
        )
        if proc.returncode != 0:
            return 0, 0
        count = 0
        total_kb = 0
        needle = image_name.lower()
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line or needle not in line.lower():
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


def main() -> int:
    parser = argparse.ArgumentParser(description="TeamsX memory stress monitor")
    parser.add_argument("--duration", type=int, default=1800, help="seconds (default 30min)")
    parser.add_argument("--interval", type=int, default=30, help="sample interval seconds")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("memory_stress_log.csv"),
        help="CSV output path",
    )
    args = parser.parse_args()
    end_at = time.time() + max(60, int(args.duration))
    interval = max(5, int(args.interval))
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Monitoring until {dt.datetime.now() + dt.timedelta(seconds=end_at - time.time())}")
    print(f"Logging to {out}")

    new_file = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(
                [
                    "timestamp",
                    "free_mb",
                    "webview2_count",
                    "webview2_mb",
                    "teamsx_count",
                    "teamsx_mb",
                ]
            )
        samples: list[int] = []
        while time.time() < end_at:
            free_mb = _system_free_mb()
            wv2_count, wv2_mb = _process_stats("msedgewebview2.exe")
            tx_count, tx_mb = _process_stats("TeamsX.exe")
            now = dt.datetime.now().isoformat(timespec="seconds")
            writer.writerow([now, free_mb, wv2_count, wv2_mb, tx_count, tx_mb])
            fh.flush()
            samples.append(wv2_mb)
            print(
                f"{now} free={free_mb}MB wv2={wv2_count}/{wv2_mb}MB teamsx={tx_count}/{tx_mb}MB"
            )
            time.sleep(interval)

    if len(samples) >= 3:
        rising = all(samples[i] <= samples[i + 1] for i in range(len(samples) - 1))
        delta = samples[-1] - samples[0]
        print(f"WebView2 memory delta: {delta:+d} MB over run")
        if rising and delta > 512:
            print("WARN: monotonic WebView2 memory growth detected")
        else:
            print("OK: no sustained monotonic growth pattern")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已手动停止监控（Ctrl+C），属正常退出。")
        raise SystemExit(0)
