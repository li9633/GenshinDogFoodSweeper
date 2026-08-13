"""
设置页面 Presenter
==================
封装主题切换、数据同步、OCR 模型下载的业务逻辑，
通过 Property/Signal/Slot 暴露给 QML 层。

与旧 settings_page.py 共享同一套后端（settings / SyncWorker / OcrModelManager），
仅 UI 框架不同。
"""

from __future__ import annotations

import time
from typing import ClassVar

from PySide6.QtCore import Property, QObject, Signal, Slot
from utils.datetime_helper import DateTimeHelper
from utils.settings_manager import settings


class SettingsPresenter(QObject):
    """设置页面 Presenter — 注册为 QML context property"""

    # -- 主题 --
    themeChanged = Signal(str)

    # -- 同步 --
    syncStarted = Signal()
    syncProgress = Signal(int, int, str)
    syncFinished = Signal(int, int, int)
    syncFailed = Signal(str)
    syncTimeChanged = Signal()
    syncStatsChanged = Signal()

    # -- 模型 --
    modelDownloadStarted = Signal()
    modelDownloadProgress = Signal(int, int, str)
    modelDownloadFinished = Signal(bool, str)
    modelStatusChanged = Signal()
    modelVersionChanged = Signal()
    modelReadyChanged = Signal()

    # -- 圣遗物更新检查 --
    versionCheckIntervalChanged = Signal()

    # -- 状态栏 --
    statusMessage = Signal(str, int, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._sync_worker = None
        self._model_manager = None
        self._download_worker = None

    # ========== 主题 ==========

    @Property(str, notify=themeChanged)
    def currentTheme(self) -> str:
        return settings.get_theme()

    @Property(int, notify=themeChanged)
    def themeIndex(self) -> int:
        return 0 if settings.get_theme() == "dark" else 1

    @Slot(str)
    def setTheme(self, theme: str) -> None:
        if theme == self.currentTheme:
            return
        settings.set_theme(theme)
        self.themeChanged.emit(theme)

    @Slot(int)
    def setThemeByIndex(self, index: int) -> None:
        self.setTheme("dark" if index == 0 else "light")

    # ========== 圣遗物更新检查 ==========

    _VERSION_CHECK_INTERVALS: ClassVar[list[str]] = ["always", "12h", "1d", "7d"]
    _VERSION_CHECK_LABELS: ClassVar[list[str]] = ["每次启动", "12小时", "1天", "一星期"]

    @Property("QStringList", notify=versionCheckIntervalChanged)
    def versionCheckIntervalLabels(self) -> list[str]:
        return self._VERSION_CHECK_LABELS

    @Property(int, notify=versionCheckIntervalChanged)
    def versionCheckIntervalIndex(self) -> int:
        key = settings.get("check.version_check_interval")
        try:
            return self._VERSION_CHECK_INTERVALS.index(key)
        except ValueError:
            return 0

    @Slot(int)
    def setVersionCheckIntervalByIndex(self, index: int) -> None:
        if 0 <= index < len(self._VERSION_CHECK_INTERVALS):
            new_key = self._VERSION_CHECK_INTERVALS[index]
            if new_key == settings.get("check.version_check_interval"):
                return
            settings.set("check.version_check_interval", new_key)
            self.versionCheckIntervalChanged.emit()

    # ========== 同步 ==========

    @Property(str, notify=syncTimeChanged)
    def syncTime(self) -> str:
        ts = settings.get_int("data.last_sync_ts")
        return f"上次同步: {DateTimeHelper.relative_time(ts if ts > 0 else None)}"

    @Property(str, notify=syncStatsChanged)
    def syncStats(self) -> str:
        sets = settings.get_int("data.last_sync_sets")
        slots = settings.get_int("data.last_sync_pieces")
        expected = settings.get_int("data.last_sync_expected")
        if sets > 0:
            if expected > 0:
                rate = slots / expected * 100
                return (
                    f"已同步 {sets} 个套装，{slots} 个部位，"
                    f"期望{expected}个，达成率{rate:.1f}%"
                )
            return f"已同步 {sets} 个套装，{slots} 个部位"
        return "尚未同步数据"

    @Slot()
    def startSync(self) -> None:
        from backend.ui.presenters.sync_worker import SyncWorker

        self.syncStarted.emit()
        self.statusMessage.emit("正在同步圣遗物数据…", 0, "INFO")

        self._sync_worker = SyncWorker()
        self._sync_worker.progress.connect(self.syncProgress.emit)
        self._sync_worker.finished_sync.connect(self._on_sync_finished)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _notify_sync_changed(self) -> None:
        self.syncTimeChanged.emit()
        self.syncStatsChanged.emit()

    def _notify_model_changed(self) -> None:
        self.modelStatusChanged.emit()
        self.modelVersionChanged.emit()
        self.modelReadyChanged.emit()

    def _on_sync_finished(
        self, sets_count: int, slots_count: int, expected_count: int
    ) -> None:
        now_ts = time.time()
        settings.set("data.last_sync_ts", str(int(now_ts)))
        settings.set("data.last_sync_sets", str(sets_count))
        settings.set("data.last_sync_pieces", str(slots_count))
        settings.set("data.last_sync_expected", str(expected_count))
        self._notify_sync_changed()
        self.syncFinished.emit(sets_count, slots_count, expected_count)
        self.statusMessage.emit("同步完成", 3000, "SUCCESS")

    def _on_sync_failed(self, error: str) -> None:
        self.syncFailed.emit(error)
        self.statusMessage.emit(f"同步失败: {error}", 5000, "ERROR")

    # ========== OCR 模型 ==========

    def _get_model_manager(self):
        if self._model_manager is None:
            from backend.automation.ocr_model_manager import OcrModelManager

            self._model_manager = OcrModelManager()
        return self._model_manager

    @Property(str, notify=modelStatusChanged)
    def modelStatus(self) -> str:
        mgr = self._get_model_manager()
        if mgr.is_ready():
            return "[√] 模型就绪"
        missing = mgr.get_missing_models()
        return f"[!] 缺少模型: {', '.join(missing)}"

    @Property(str, notify=modelVersionChanged)
    def modelVersion(self) -> str:
        return self._get_model_manager().get_version_summary()

    @Property(bool, notify=modelReadyChanged)
    def modelReady(self) -> bool:
        return self._get_model_manager().is_ready()

    @Slot()
    def downloadModels(self) -> None:
        self.modelDownloadStarted.emit()

        mgr = self._get_model_manager()
        self._download_worker = mgr.create_download_worker()
        self._download_worker.progress.connect(self.modelDownloadProgress.emit)
        self._download_worker.finished_download.connect(self._on_download_finished)
        self._download_worker.start()

    def _on_download_finished(self, success: bool, message: str) -> None:
        self._notify_model_changed()
        self.modelDownloadFinished.emit(success, message)
        if success:
            self.statusMessage.emit(message, 3000, "SUCCESS")
        else:
            self.statusMessage.emit(message, 5000, "ERROR")