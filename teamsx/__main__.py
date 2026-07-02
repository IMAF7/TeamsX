# -*- coding: utf-8 -*-
"""python -m teamsx"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QMessageBox


def main() -> None:
    try:
        from teamsx.startup import prepare_runtime

        prepare_runtime()

        from teamsx.app import run_app

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
