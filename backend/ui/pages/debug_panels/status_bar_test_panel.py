"""状态栏颜色测试面板 — 独立调试子组件"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
)
from utils.logger import log

_TEST_LEVELS: list[tuple[str, str]] = [
    ("INFO", "信息 (灰)"),
    ("SUCCESS", "成功 (绿)"),
    ("WARNING", "警告 (橙)"),
    ("ERROR", "错误 (红)"),
    ("CRITICAL", "严重 (红底白字)"),
]


class StatusBarTestPanel(QGroupBox):
    """状态栏颜色测试"""

    def __init__(self, parent=None):
        super().__init__("状态栏颜色测试", parent)
        layout = QHBoxLayout()
        self.setLayout(layout)

        for level, tip in _TEST_LEVELS:
            btn = QPushButton(tip)
            btn.clicked.connect(lambda _checked, l=level: self._test_log(l))
            layout.addWidget(btn)

    @staticmethod
    def _test_log(level: str) -> None:
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