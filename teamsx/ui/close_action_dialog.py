# -*- coding: utf-8 -*-
"""关闭动作选择：卡片式对话框（圆角、跟随软件主题色）。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class _Palette:
    """按主题集中提供配色，便于卡片整体跟随软件主题。"""

    def __init__(self, light: bool):
        if light:
            self.card_bg = "#ffffff"
            self.card_border = "#e6e8ec"
            self.title = "#1f2329"
            self.sub = "#8a9099"
            self.opt_bg = "#f6f8fb"
            self.opt_border = "#e6e8ec"
            self.opt_hover_bg = "#eef4ff"
            self.opt_hover_border = "#bcd6ff"
            self.opt_sel_bg = "#e8f1ff"
            self.opt_sel_border = "#3b82f6"
            self.accent = "#2f6fed"
            self.accent_hover = "#2560d6"
            self.accent_disabled = "#c3d6f5"
            self.ghost_text = "#6b7280"
            self.ghost_border = "#d6dae0"
            self.ghost_hover = "#f0f2f5"
            self.shadow_alpha = 60
        else:
            self.card_bg = "#2b2d31"
            self.card_border = "#3a3d42"
            self.title = "#f2f3f5"
            self.sub = "#9aa0a6"
            self.opt_bg = "#34373c"
            self.opt_border = "#42454a"
            self.opt_hover_bg = "#3a4350"
            self.opt_hover_border = "#5a8edb"
            self.opt_sel_bg = "#2f4a6e"
            self.opt_sel_border = "#5a9cf5"
            self.accent = "#3b82f6"
            self.accent_hover = "#4a90f0"
            self.accent_disabled = "#3a4a5c"
            self.ghost_text = "#b6bbc2"
            self.ghost_border = "#4a4d52"
            self.ghost_hover = "#3a3d42"
            self.shadow_alpha = 130


class _CloseOptionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str, accent: str, pal: _Palette, parent=None,
                 icon_size: int = 24):
        super().__init__(parent)
        self._pal = pal
        self._hovered = False
        self._selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(126)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 15, 16, 15)
        lay.setSpacing(7)
        icon = QLabel(accent)
        icon.setFixedHeight(28)
        icon.setStyleSheet(
            f"font-size: {icon_size}px; color: {pal.accent}; border: none; background: transparent;"
        )
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        sub_lbl = QLabel(subtitle)
        sub_lbl.setWordWrap(True)
        lay.addWidget(icon)
        lay.addWidget(title_lbl)
        lay.addWidget(sub_lbl)
        lay.addStretch()
        self._title_lbl = title_lbl
        self._sub_lbl = sub_lbl
        self._apply_style()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._apply_style()

    def _apply_style(self) -> None:
        pal = self._pal
        if self._selected:
            bg, border = pal.opt_sel_bg, pal.opt_sel_border
        elif self._hovered:
            bg, border = pal.opt_hover_bg, pal.opt_hover_border
        else:
            bg, border = pal.opt_bg, pal.opt_border
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 2px solid {border}; border-radius: 14px; }}"
        )
        self._title_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {pal.title}; border: none; background: transparent;"
        )
        self._sub_lbl.setStyleSheet(
            f"font-size: 12px; color: {pal.sub}; border: none; background: transparent;"
        )

    def enterEvent(self, event):
        self._hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CloseActionCardDialog(QDialog):
    CHOICE_TRAY = "tray"
    CHOICE_EXIT = "exit"

    def __init__(self, parent=None, *, light: bool = True):
        super().__init__(parent)
        self._pal = _Palette(bool(light))
        self._choice: str = ""
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(468, 330)

        pal = self._pal
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("closeActionCard")
        card.setStyleSheet(
            f"QFrame#closeActionCard {{ background: {pal.card_bg};"
            f"border: 1px solid {pal.card_border}; border-radius: 18px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, pal.shadow_alpha))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(16)

        title = QLabel("关闭 TeamsX？")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {pal.title};"
            "border: none; background: transparent;"
        )
        lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(14)
        self._tray_card = _CloseOptionCard(
            "隐藏到任务栏",
            "窗口收起，后台继续运行。\n单击托盘图标可恢复。",
            "◐",
            pal,
            card,
            icon_size=24,
        )
        self._exit_card = _CloseOptionCard(
            "退出软件",
            "结束全部账号页面并释放资源。",
            "✕",
            pal,
            card,
            icon_size=19,
        )
        self._tray_card.clicked.connect(lambda: self._select_choice(self.CHOICE_TRAY))
        self._exit_card.clicked.connect(lambda: self._select_choice(self.CHOICE_EXIT))
        row.addWidget(self._tray_card)
        row.addWidget(self._exit_card)
        lay.addLayout(row)

        self._remember_cb = QCheckBox("记住我的选择")
        self._remember_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remember_cb.setStyleSheet(
            f"QCheckBox {{ color: {pal.sub}; font-size: 12px; spacing: 6px;"
            "background: transparent; border: none; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        lay.addWidget(self._remember_cb, alignment=Qt.AlignmentFlag.AlignLeft)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("取消")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedHeight(34)
        cancel.setMinimumWidth(76)
        cancel.setStyleSheet(
            f"QPushButton {{ color: {pal.ghost_text}; background: transparent;"
            f"border: 1px solid {pal.ghost_border}; border-radius: 9px;"
            "padding: 5px 16px; font-size: 12px; }"
            f"QPushButton:hover {{ background: {pal.ghost_hover}; color: {pal.title}; }}"
        )
        cancel.clicked.connect(self.reject)

        self._ok_btn = QPushButton("确定")
        self._ok_btn.setEnabled(False)
        self._ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ok_btn.setFixedHeight(34)
        self._ok_btn.setMinimumWidth(76)
        self._ok_btn.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: {pal.accent}; border: none;"
            "border-radius: 9px; padding: 5px 16px; font-size: 12px; font-weight: 600; }"
            f"QPushButton:hover:enabled {{ background: {pal.accent_hover}; }}"
            f"QPushButton:disabled {{ background: {pal.accent_disabled}; color: #f0f0f0; }}"
        )
        self._ok_btn.clicked.connect(self._confirm)
        btn_row.addWidget(cancel)
        btn_row.addSpacing(10)
        btn_row.addWidget(self._ok_btn)
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

    def _select_choice(self, choice: str) -> None:
        self._choice = choice
        self._tray_card.set_selected(choice == self.CHOICE_TRAY)
        self._exit_card.set_selected(choice == self.CHOICE_EXIT)
        self._ok_btn.setEnabled(True)

    def _confirm(self) -> None:
        if self._choice in (self.CHOICE_TRAY, self.CHOICE_EXIT):
            self.accept()

    def choice(self) -> str:
        return self._choice

    def remember(self) -> bool:
        return self._remember_cb.isChecked()
