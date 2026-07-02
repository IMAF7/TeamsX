# -*- coding: utf-8 -*-
"""应用入口：从 TeamsX 核心模块启动 UI。"""
from __future__ import annotations


def run_app() -> None:
    import sys

    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    from teamsx.single_instance import (
        find_other_teamsx_pids,
        start_single_instance_listener,
        terminate_pids,
        try_activate_existing_instance,
    )

    app = QApplication(sys.argv)
    font = QFont()
    font.setPointSize(9)
    app.setFont(font)

    # 真正存活的实例：直接唤醒它并退出本次启动
    if try_activate_existing_instance():
        sys.exit(0)

    # 没有可唤醒的实例，但仍找到 TeamsX 进程 = 监听器已死的残留空壳，静默清理后继续启动
    residual = find_other_teamsx_pids()
    if residual:
        killed = terminate_pids(residual)
        print(f"已清理 {killed}/{len(residual)} 个残留 TeamsX 进程: {residual}")

    from TeamsX import MainWindow

    window = MainWindow()
    app._teamsx_single_instance_server = start_single_instance_listener(  # type: ignore[attr-defined]
        window.show_from_tray
    )
    window.show()
    sys.exit(app.exec())
