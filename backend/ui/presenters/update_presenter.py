"""App 更新 Presenter

承担 AboutTab 和 UpdateWindow 的 Presenter 职责：
- AboutTab → checking、errorText、checkForUpdates
- UpdateWindow → version、changelog、downloading、downloadAndInstall
- UpdateWindow 生命周期管理（继承 WindowPresenter）

纯业务逻辑委托给 AppUpdater（backend/utils/app_updater.py）。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot
from ui.presenters.window_presenter import WindowPresenter

from common.version_manager import AppVersion


class _CheckWorker(QThread):
    """版本检查工作线程"""

    finished = Signal(object, object, bool)

    def run(self) -> None:
        from backend.utils.app_updater import (
            UPDATE_OWNER,
            UPDATE_REPO,
            AppUpdater,
            detect_mock_server,
        )

        mock_url = detect_mock_server()
        using_mock = mock_url is not None

        try:
            updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO, api_base=mock_url)
            has_update, info, error = updater.is_update_available()

            if error:
                self.finished.emit(None, error, using_mock)
            else:
                self.finished.emit((has_update, info), None, using_mock)
        except Exception as e:
            self.finished.emit(None, str(e), using_mock)


class _DownloadWorker(QThread):
    """安装包下载工作线程"""

    progress = Signal(int, int)
    finished_download = Signal(bool, str)

    def __init__(self, url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        from backend.utils.app_updater import (
            UPDATE_OWNER,
            UPDATE_REPO,
            AppUpdater,
        )

        try:
            updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO)
            path = updater.download(self._url, progress_cb=self.progress.emit)
            self.finished_download.emit(True, str(path))
        except Exception as e:
            self.finished_download.emit(False, str(e))


class UpdatePresenter(WindowPresenter):
    """App 更新 Presenter

    作为 QML context property "UpdatePresenter" 注入，供 AboutTab 和 UpdateWindow 绑定。
    """

    _QML_PATH = "components/UpdateWindow.qml"
    _WINDOW_TITLE = "发现新版本"

    # ════════════════════════════════════════════
    # 信号
    # ════════════════════════════════════════════

    # AboutTab 状态
    checkingChanged = Signal()
    errorTextChanged = Signal()

    # UpdateWindow 数据
    versionInfoChanged = Signal()
    downloadingChanged = Signal()
    downloadProgressChanged = Signal()
    downloadTotalChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # ── 业务数据 ──
        self._version = ""
        self._changelog = ""
        self._current_version = ""
        self._download_url = ""
        self._downloading = False
        self._download_progress = 0
        self._download_total = 0

        # ── UI 状态 ──
        self._checking = False
        self._error_text = ""

        # ── 工作线程 ──
        self._check_worker: _CheckWorker | None = None
        self._download_worker: _DownloadWorker | None = None

        self._current_version = AppVersion.display()

    # ════════════════════════════════════════════
    # QML 属性 — AboutTab
    # ════════════════════════════════════════════

    @Property(bool, notify=checkingChanged)
    def checking(self) -> bool:
        return self._checking

    @Property(str, notify=errorTextChanged)
    def errorText(self) -> str:
        return self._error_text

    # ════════════════════════════════════════════
    # QML 属性 — UpdateWindow
    # ════════════════════════════════════════════

    @Property(str, constant=True)
    def currentVersion(self) -> str:
        return self._current_version

    @Property(str, notify=versionInfoChanged)
    def version(self) -> str:
        return self._version

    @Property(str, notify=versionInfoChanged)
    def changelog(self) -> str:
        return self._changelog

    @Property(bool, notify=downloadingChanged)
    def downloading(self) -> bool:
        return self._downloading

    @Property(int, notify=downloadProgressChanged)
    def downloadProgress(self) -> int:
        return self._download_progress

    @Property(int, notify=downloadTotalChanged)
    def downloadTotal(self) -> int:
        return self._download_total

    # ════════════════════════════════════════════
    # 公开槽
    # ════════════════════════════════════════════

    @Slot()
    def checkForUpdates(self) -> None:
        """检查是否有可用更新（AboutTab 按钮调用）"""
        from backend.utils.logger import log

        if self._checking:
            return
        self._checking = True
        self.checkingChanged.emit()
        log.info("正在检查更新…")

        self._check_worker = _CheckWorker()
        self._check_worker.finished.connect(self._on_check_finished)
        self._check_worker.start()

    @Slot()
    def downloadAndInstall(self) -> None:
        """下载安装包并拉起安装程序"""
        if self._downloading or not self._download_url:
            return

        self._downloading = True
        self._download_progress = 0
        self._download_total = 0
        self.downloadingChanged.emit()
        self.downloadProgressChanged.emit()

        self._download_worker = _DownloadWorker(self._download_url)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished_download.connect(self._on_download_finished)
        self._download_worker.start()

    # ════════════════════════════════════════════
    # 窗口生命周期（继承 WindowPresenter）
    # ════════════════════════════════════════════

    def _on_before_create(self, win: QObject) -> None:
        """UpdateWindow 创建后：连接 QML 信号"""
        win.updateNow.connect(self.downloadAndInstall)
        win.remindLater.connect(win.close)

    # ════════════════════════════════════════════
    # 内部回调
    # ════════════════════════════════════════════

    def _on_check_finished(
        self, result: object, error: object, using_mock: bool
    ) -> None:
        from backend.utils.logger import log

        self._checking = False
        self.checkingChanged.emit()

        if error is not None:
            self._error_text = f"检查失败: {error}"
            self.errorTextChanged.emit()
            log.warning(f"检查更新失败: {error}")
            return

        # 检查成功，清除旧的失败提示
        if self._error_text:
            self._error_text = ""
            self.errorTextChanged.emit()

        if result is None:
            # 无更新
            return

        has_update, info = result  # type: ignore[misc]
        mock_hint = " [模拟器]" if using_mock else ""
        if has_update and info:
            self._version = info.get("tag", "?")
            self._changelog = info.get("body", "") or ""
            self._download_url = info.get("download_url", "")
            log.debug(
                f"发现新版本: tag={self._version!r} "
                f"changelog_len={len(self._changelog)} download_url={bool(self._download_url)}"
            )
            self.versionInfoChanged.emit()
            log.info(f"发现新版本 {self._version}{mock_hint}")
            self.show_window()
        # else: 无更新，静默不处理

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        self._download_progress = downloaded
        self._download_total = total
        self.downloadProgressChanged.emit()

    def _on_download_finished(self, success: bool, filepath: str) -> None:
        self._downloading = False
        self.downloadingChanged.emit()
        if success:
            self._install(Path(filepath))
        else:
            self.downloadProgressChanged.emit()

    # ════════════════════════════════════════════
    # 安装
    # ════════════════════════════════════════════

    def _install(self, setup_path: Path) -> None:
        from backend.utils.app_updater import UPDATE_OWNER, UPDATE_REPO, AppUpdater

        AppUpdater(UPDATE_OWNER, UPDATE_REPO).install(setup_path)