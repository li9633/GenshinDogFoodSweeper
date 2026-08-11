"""状态栏颜色测试 — QObject Presenter + 遗留 QWidget（仅保留 QObject）"""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot
from utils.logger import log


class StatusBarTestPresenter(QObject):
    """状态栏测试 Presenter — QML 可绑定"""

    @Slot(str)
    def testLog(self, level: str) -> None:
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