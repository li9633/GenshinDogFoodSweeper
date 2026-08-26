"""
圣遗物更新检查 Presenter
==================
启动时在后台线程检查原神圣遗物是否有新版本，通过信号通知 UI。
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QThread, Signal, Slot
from ui.lifecycle import OnWindowReady
from utils.logger import log
from utils.settings_manager import settings

# 间隔常量（秒）
INTERVAL_SECONDS: dict[str, int] = {
    "always": 0,
    "12h": 12 * 3600,
    "1d": 24 * 3600,
    "7d": 7 * 24 * 3600,
}


class _VersionCheckWorker(QThread):
    """后台线程：执行圣遗物更新检查"""

    finished = Signal(dict)  # 检查结果 dict
    failed = Signal(str)  # 错误信息

    def run(self) -> None:
        from crawler.version_checker import VersionChecker

        try:
            result = VersionChecker.check()
            self.finished.emit(result)
        except Exception as e:
            log.error(f"圣遗物更新检查异常: {e}")
            self.failed.emit(str(e))


class VersionCheckPresenter(QObject, OnWindowReady):
    """圣遗物更新检查 Presenter — 注册为 QML context property"""

    # 需要 UI 显示弹窗时发射
    updateNeeded = Signal(str, str)  # (title, message)

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
        interval_key = settings.get("check.version_check_interval")
        if interval_key == "always":
            return True
        interval_sec = INTERVAL_SECONDS.get(interval_key, 0)
        if interval_sec <= 0:
            return True
        last_ts = settings.get_int("check.last_version_check_ts")
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
        self._worker.finished.connect(self._on_check_finished)
        self._worker.failed.connect(self._on_check_failed)
        self._worker.start()

    def _on_check_finished(self, result: dict) -> None:
        """检查完成，记录时间并判断是否需要弹窗"""
        now_ts = int(time.time())
        settings.set("check.last_version_check_ts", str(now_ts))

        need_update = result.get("need_update", False)
        db_empty = result.get("db_empty", False)

        if db_empty:
            self.updateNeeded.emit(
                "圣遗物数据库为空",
                "本地圣遗物数据库为空，请前往 设置 → 圣遗物同步，手动同步。",
            )
        elif need_update:
            self.updateNeeded.emit(
                "圣遗物最新数据更新",
                "检测到圣遗物最新数据更新，请前往 设置 → 圣遗物同步，手动进行同步。",
            )
        else:
            log.info("圣遗物更新检查: 本地数据已是最新，无需更新")

    def _on_check_failed(self, error: str) -> None:
        """检查失败（静默，不弹窗打扰用户）"""
        log.warning(f"圣遗物最新数据检查失败: {error}")