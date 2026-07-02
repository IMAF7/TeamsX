# -*- coding: utf-8 -*-
"""通用卡片对话框：圆角、跟随软件主题色（确认 / 信息提示）。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


def _palette(light: bool) -> dict:
    if light:
        return {
            "card_bg": "#ffffff", "card_border": "#e6e8ec",
            "title": "#1f2329", "body": "#5b616b",
            "danger_bg": "#fdecec", "danger_fg": "#e5484d",
            "info_bg": "#e8f1ff", "info_fg": "#2f6fed",
            "danger": "#e5484d", "danger_hover": "#d13b40",
            "accent": "#2f6fed", "accent_hover": "#2560d6",
            "ghost_text": "#6b7280", "ghost_border": "#d6dae0", "ghost_hover": "#f0f2f5",
            "shadow_alpha": 60,
        }
    return {
        "card_bg": "#2b2d31", "card_border": "#3a3d42",
        "title": "#f2f3f5", "body": "#aab0b8",
        "danger_bg": "#4a2e30", "danger_fg": "#ff6b6f",
        "info_bg": "#2f4a6e", "info_fg": "#7fb2ff",
        "danger": "#e5484d", "danger_hover": "#f15a5f",
        "accent": "#3b82f6", "accent_hover": "#4a90f0",
        "ghost_text": "#b6bbc2", "ghost_border": "#4a4d52", "ghost_hover": "#3a3d42",
        "shadow_alpha": 130,
    }


class ConfirmCardDialog(QDialog):
    """卡片式确认 / 信息框。

    danger=True：确认按钮为红色（危险操作）。
    single=True：仅一个按钮（信息提示）。
    """

    def __init__(
        self,
        parent=None,
        *,
        title: str = "确认",
        message: str = "",
        ok_text: str = "确定",
        cancel_text: str = "取消",
        danger: bool = False,
        single: bool = False,
        width: int = 396,
        light: bool = True,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        pal = _palette(bool(light))

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 26)

        card = QFrame()
        card.setObjectName("confirmCard")
        card.setStyleSheet(
            f"QFrame#confirmCard {{ background: {pal['card_bg']};"
            f"border: 1px solid {pal['card_border']}; border-radius: 18px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, pal["shadow_alpha"]))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(12)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {pal['title']};"
            "border: none; background: transparent;"
        )
        if single:
            head.addWidget(title_lbl, 1)
        else:
            icon = QLabel("!" if danger else "?")
            icon.setFixedSize(38, 38)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_bg = pal["danger_bg"] if danger else pal["info_bg"]
            icon_fg = pal["danger_fg"] if danger else pal["info_fg"]
            icon.setStyleSheet(
                f"background: {icon_bg}; color: {icon_fg};"
                "border: none; border-radius: 19px; font-size: 20px; font-weight: 700;"
            )
            head.addWidget(icon)
            head.addWidget(title_lbl, 1)
        lay.addLayout(head)

        inner_w = width - 48 - 48  # root margins + card margins
        body = QLabel(message)
        body.setWordWrap(True)
        body.setFixedWidth(inner_w)
        body.setStyleSheet(
            f"font-size: 13px; color: {pal['body']}; border: none;"
            "background: transparent; line-height: 150%;"
        )
        lay.addWidget(body)

        lay.addStretch()
        lay.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if not single:
            cancel = QPushButton(cancel_text)
            cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel.setFixedHeight(34)
            cancel.setMinimumWidth(80)
            cancel.setStyleSheet(
                f"QPushButton {{ color: {pal['ghost_text']}; background: transparent;"
                f"border: 1px solid {pal['ghost_border']}; border-radius: 9px;"
                "padding: 5px 16px; font-size: 12px; }"
                f"QPushButton:hover {{ background: {pal['ghost_hover']}; color: {pal['title']}; }}"
            )
            cancel.clicked.connect(self.reject)
            btn_row.addWidget(cancel)
            btn_row.addSpacing(10)

        ok = QPushButton(ok_text)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setDefault(True)
        ok.setFixedHeight(34)
        ok.setMinimumWidth(80)
        accent = pal["danger"] if danger else pal["accent"]
        accent_hover = pal["danger_hover"] if danger else pal["accent_hover"]
        ok.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: {accent}; border: none;"
            "border-radius: 9px; padding: 5px 16px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {accent_hover}; }}"
        )
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

        root.addWidget(card)
        self.setFixedWidth(width)
        self.setFixedHeight(max(180, self.sizeHint().height()))

    def showEvent(self, event):
        parent = self.parentWidget()
        if parent is not None:
            g = parent.frameGeometry()
            self.move(
                g.center().x() - self.width() // 2,
                g.center().y() - self.height() // 2,
            )
        super().showEvent(event)

    @staticmethod
    def confirm(
        parent,
        *,
        title: str,
        message: str,
        ok_text: str = "确定",
        cancel_text: str = "取消",
        danger: bool = False,
        light: bool = True,
    ) -> bool:
        dlg = ConfirmCardDialog(
            parent,
            title=title,
            message=message,
            ok_text=ok_text,
            cancel_text=cancel_text,
            danger=danger,
            light=light,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted

    @staticmethod
    def info(
        parent,
        *,
        title: str,
        message: str,
        ok_text: str = "知道了",
        width: int = 420,
        light: bool = True,
    ) -> None:
        dlg = ConfirmCardDialog(
            parent,
            title=title,
            message=message,
            ok_text=ok_text,
            single=True,
            width=width,
            light=light,
        )
        dlg.exec()
