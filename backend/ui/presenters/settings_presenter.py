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
from utils.logger import log
from utils.settings_manager import settings
from utils.version import AppVersion, Channel


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

    # -- 快捷键 --
    hotkeyChanged = Signal()
    hotkeyCaptureStarted = Signal()
    hotkeyCaptureFinished = Signal()

    # -- 状态栏 --
    statusMessage = Signal(str, int, str)

    # -- 关于 --
    _APP_TITLE: ClassVar[str] = "原神狗粮清扫器"
    _APP_SUBTITLE: ClassVar[str] = "原神圣遗物自动化管理工具"
    _APP_VERSION: ClassVar[str] = (
        AppVersion.clean()
        if AppVersion.CHANNEL == Channel.RELEASE
        else AppVersion.string()
    )
    _APP_VERSION_FULL: ClassVar[str] = AppVersion.debug_string()
    _APP_DESCRIPTION: ClassVar[str] = (
        "基于 OCR 视觉识别的原神圣遗物自动管理工具。"
        "通过截图识别圣遗物属性，根据自定义规则自动筛选和标记狗粮，"
        "帮助旅行者高效清理背包、告别手动对比属性的繁琐操作。"
    )
    _GITHUB_URL: ClassVar[str] = "https://github.com/li9633/GenshinDogFoodSweeper"
    _ISSUES_URL: ClassVar[str] = f"{_GITHUB_URL}/issues"

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._sync_worker = None
        self._model_manager = None
        self._download_worker = None

    # ========== 关于 ==========

    @Property(str, constant=True)
    def appTitle(self) -> str:
        return self._APP_TITLE

    @Property(str, constant=True)
    def appSubtitle(self) -> str:
        return self._APP_SUBTITLE

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return self._APP_VERSION

    @Property(str, constant=True)
    def appVersionFull(self) -> str:
        return self._APP_VERSION_FULL

    @Property(bool, constant=True)
    def isDevVersion(self) -> bool:
        """是否为开发/内部版本（需要显示水印）"""
        return AppVersion.CHANNEL in (Channel.DEV, Channel.ALPHA)

    @Property(bool, constant=True)
    def isReleaseVersion(self) -> bool:
        """是否为正式版"""
        return AppVersion.CHANNEL == Channel.RELEASE

    @Property(str, constant=True)
    def appDescription(self) -> str:
        return self._APP_DESCRIPTION

    @Property(str, constant=True)
    def githubUrl(self) -> str:
        return self._GITHUB_URL

    @Property(str, constant=True)
    def issuesUrl(self) -> str:
        return self._ISSUES_URL

    @Property(str, constant=True)
    def appIconPath(self) -> str:
        """应用图标路径，兼容开发模式和 PyInstaller 打包"""
        import sys
        from pathlib import Path
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent.parent.parent.parent
        for name in ("app.png", "app.ico"):
            p = base / "resources" / name
            if p.exists():
                return "file:///" + str(p).replace("\\", "/")
        return ""

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

    # ========== 快捷键 ==========

    @Property(str, notify=hotkeyChanged)
    def hotkey(self) -> str:
        from backend.automation.hotkey_listener import HotkeyListener
        return HotkeyListener.get_hotkey()

    @Property(str, notify=hotkeyChanged)
    def hotkeyDisplay(self) -> str:
        from backend.automation.hotkey_listener import HotkeyListener
        return HotkeyListener.human_readable(self.hotkey)

    @Slot()
    def startHotkeyCapture(self) -> None:
        from backend.automation.hotkey_listener import HotkeyListener
        HotkeyListener.start_capture()
        self.hotkeyCaptureStarted.emit()

    @Slot()
    def cancelHotkeyCapture(self) -> None:
        from backend.automation.hotkey_listener import HotkeyListener
        HotkeyListener.cancel_capture()
        self.hotkeyCaptureFinished.emit()

    def _on_hotkey_captured(self, _hotkey: str) -> None:
        self.hotkeyChanged.emit()
        self.hotkeyCaptureFinished.emit()

    # ========== 圣遗物更新检查 ==========

    _VERSION_CHECK_INTERVALS: ClassVar[list[str]] = ["always", "12h", "1d", "7d"]
    _VERSION_CHECK_LABELS: ClassVar[list[str]] = ["每次启动", "12小时", "1天", "一星期"]

    @Property("QStringList", notify=versionCheckIntervalChanged)
    def versionCheckIntervalLabels(self) -> list[str]:
        return self._VERSION_CHECK_LABELS

    @Property(int, notify=versionCheckIntervalChanged)
    def versionCheckIntervalIndex(self) -> int:
        key = settings.get("sync_check.version_check_interval")
        try:
            return self._VERSION_CHECK_INTERVALS.index(key)
        except ValueError:
            return 0

    @Slot(int)
    def setVersionCheckIntervalByIndex(self, index: int) -> None:
        if 0 <= index < len(self._VERSION_CHECK_INTERVALS):
            new_key = self._VERSION_CHECK_INTERVALS[index]
            if new_key == settings.get("sync_check.version_check_interval"):
                return
            settings.set("sync_check.version_check_interval", new_key)
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

    @Property(str, notify=syncStatsChanged)
    def dbStats(self) -> str:
        """当前数据库实际存储的圣遗物数据量（可能因手动删除等操作与上次同步记录不一致）"""
        try:
            from database.repository.artifact_piece_repo import ArtifactPieceRepo
            from database.repository.artifact_set_repo import ArtifactSetRepo
            sets = ArtifactSetRepo.count()
            pieces = ArtifactPieceRepo.count()
            if sets > 0:
                return f"本地已同步: {sets} 个套装，{pieces} 个部位"
            return "本地数据库内暂无数据，请先同步圣遗物数据"
        except Exception:
            return "本地数据库内无法读取"

    @Slot()
    def refreshSyncInfo(self) -> None:
        """刷新同步信息显示（Tab 切换时触发，确保当前数据库状态为最新）"""
        self.syncTimeChanged.emit()
        self.syncStatsChanged.emit()

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
            # 模型下载成功后自动启动 OcrWorker，避免用户立即使用时等待初始化
            try:
                from backend.automation.ocr_worker import OcrWorker
                worker = OcrWorker.instance()
                if not worker.isRunning():
                    worker.start()
                    log.info("模型下载完成，OcrWorker 线程已自动启动")
            except Exception:
                log.warning("模型下载后启动 OcrWorker 失败，将在首次使用时延迟启动")
        else:
            self.statusMessage.emit(message, 5000, "ERROR")