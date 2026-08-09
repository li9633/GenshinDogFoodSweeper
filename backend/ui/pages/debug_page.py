"""
调试页面
========
包含截图预览组件和状态栏颜色测试，用于调试截图/识别流程。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from utils.logger import log

# 状态栏可测试的日志级别
_TEST_LEVELS: list[tuple[str, str]] = [
    ("INFO", "信息 (灰)"),
    ("SUCCESS", "成功 (绿)"),
    ("WARNING", "警告 (橙)"),
    ("ERROR", "错误 (红)"),
    ("CRITICAL", "严重 (红底白字)"),
]


class DebugPage(QWidget):
    def __init__(self, capture_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("截图预览")
        label.setProperty("class", "section-title")
        layout.addWidget(label)

        self._container = QFrame()
        self._container.setLayout(QVBoxLayout())
        self._container.layout().setContentsMargins(0, 0, 0, 0)
        self._container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self._container, stretch=1)

        if capture_widget is not None:
            self._container.layout().addWidget(capture_widget)

        # 状态栏颜色测试
        self._add_status_bar_test(layout)

    def _add_status_bar_test(self, layout: QVBoxLayout) -> None:
        """添加状态栏颜色测试面板"""
        group = QGroupBox("状态栏颜色测试")
        btn_layout = QHBoxLayout()
        group.setLayout(btn_layout)

        for level, tip in _TEST_LEVELS:
            btn = QPushButton(tip)
            btn.clicked.connect(lambda _checked, l=level: self._test_log(l))
            btn_layout.addWidget(btn)

        layout.addWidget(group)

    @staticmethod
    def _test_log(level: str) -> None:
        """触发指定级别的日志，验证状态栏颜色"""
        msg = f"[调试] 状态栏颜色测试 — {level}"
        if level == "SUCCESS":
            log.success(msg)
        elif level == "WARNING":
            log.warning(msg)
        elif level == "ERROR":
            log.error(msg)
        elif level == "CRITICAL":
            log.critical(msg)
        else:
            log.info(msg)