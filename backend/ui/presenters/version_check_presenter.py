"""
圣遗物更新检查 Presenter
==================
启动时在后台线程检查原神圣遗物是否有新版本，通过信号通知 UI。
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QThread, Signal, Slot
from ui.gmessagebox import GMessageBox
from ui.lifecycle import OnWindowReady
from utils.logger import log
from utils.settings_manager import settings

from backend.exceptions.automation.exceptions import (
    ArtifactDatabaseEmptyError,
    ArtifactUpdateAvailableError,
)

# 间隔常量（秒）
INTERVAL_SECONDS: dict[str, int] = {
    "always": 0,
    "12h": 12 * 3600,
    "1d": 24 * 3600,
    "7d": 7 * 24 * 3600,
}


class _VersionCheckWorker(QThread):
    """后台线程：执行圣遗物更新检查"""

    checkOk = Signal()  # 无需更新
    checkFailed = Signal(str)  # 异常类型名

    def run(self) -> None:
        from crawler.version_checker import VersionChecker

        try:
            VersionChecker.check()
            self.checkOk.emit()
        except Exception as e:
            self.checkFailed.emit(type(e).__name__)


class VersionCheckPresenter(QObject, OnWindowReady):
    """圣遗物更新检查 Presenter — 注册为 QML context property"""

    # 用户点击「立即前往」时发射，QML 侧导航到设置→同步Tab
    navigateToSyncTab = Signal()

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)
        self._worker: _VersionCheckWorker | None = None

    def on_window_ready(self) -> None:
        """窗口就绪后自动检查版本"""
        self.checkVersion()

    # ========== 间隔判断 ==========

    def _should_check(self) -> bool:
        """根据配置判断是否需要执行检查"""
        interval_key = settings.get("sync_check.version_check_interval")
        if interval_key == "always":
            return True
        interval_sec = INTERVAL_SECONDS.get(interval_key, 0)
        if interval_sec <= 0:
            return True
        last_ts = settings.get_int("sync_check.last_version_check_ts")
        if last_ts <= 0:
            return True
        return (time.time() - last_ts) >= interval_sec

    # ========== 公开 Slot ==========

    @Slot()
    def checkVersion(self) -> None:
        """触发圣遗物最新数据检查（由 main.py 在启动时调用）"""
        if not self._should_check():
            log.debug("未到间隔时间，跳过")
            return

        log.info("圣遗物最新数据同步中…")
        self._worker = _VersionCheckWorker()
        self._worker.checkOk.connect(self._on_check_ok)
        self._worker.checkFailed.connect(self._on_check_failed)
        self._worker.start()

    def _on_check_ok(self) -> None:
        """检查完成，无需更新"""
        now_ts = int(time.time())
        settings.set("sync_check.last_version_check_ts", str(now_ts))
        log.debug("圣遗物更新检查: 本地数据已是最新，无需更新")

    def _on_check_failed(self, exc_name: str) -> None:
        """检查失败，根据异常类型名决定是否弹窗"""
        now_ts = int(time.time())
        settings.set("sync_check.last_version_check_ts", str(now_ts))

        if exc_name == ArtifactDatabaseEmptyError.__name__:
            GMessageBox.show(
                "warning", ArtifactDatabaseEmptyError._MESSAGE,
                title="圣遗物数据库为空",
                buttons=[
                    GMessageBox.Button("立即前往", "accept", "primary"),
                    GMessageBox.Button("知道了", "reject", "secondary"),
                ],
                bring_to_front=True,
                on_button=lambda role: self._handle_version_button(role),
            )
        elif exc_name == ArtifactUpdateAvailableError.__name__:
            GMessageBox.show(
                "warning", ArtifactUpdateAvailableError._MESSAGE,
                title="圣遗物最新数据更新",
                buttons=[
                    GMessageBox.Button("立即前往", "accept", "primary"),
                    GMessageBox.Button("知道了", "reject", "secondary"),
                ],
                bring_to_front=True,
                on_button=lambda role: self._handle_version_button(role),
            )
        else:
            log.warning(f"圣遗物最新数据检查失败: {exc_name}")

    def _handle_version_button(self, role: str) -> None:
        """版本更新弹窗按钮回调"""
        if role == "accept":
            log.info("用户点击「立即前往」，跳转到同步Tab")
            self.navigateToSyncTab.emit()