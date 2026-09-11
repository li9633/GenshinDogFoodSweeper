"""应用更新服务
============
独立的更新模块，管理版本检查、下载、安装的完整生命周期。
不依赖任何 UI Presenter，仅通过信号与 QML 层通信。

负责 UpdateWindow 的创建和生命周期管理，
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent

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


class UpdateService(QObject):
    """应用更新服务

    通过 QML context property 注入，提供：
    - 版本检查
    - 下载进度
    - 安装触发
    - UpdateWindow 生命周期管理
    """

    _engine: ClassVar[QQmlApplicationEngine | None] = None

    # ── 信号 ──
    updateFound = Signal()              # 有新版本可用
    updateCheckFailed = Signal(str)     # 检查失败的错误消息
    updateCheckNone = Signal(str)       # 无更新的提示消息

    checkingChanged = Signal()
    statusTextChanged = Signal()
    statusTypeChanged = Signal()
    versionInfoChanged = Signal()        # version / changelog 变更时发射
    downloadingChanged = Signal()
    downloadProgressChanged = Signal()
    downloadTotalChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._check_worker: _CheckWorker | None = None
        self._download_worker: _DownloadWorker | None = None
        self._update_window: QObject | None = None
        self._update_component: QQmlComponent | None = None
        self._checking = False
        self._status_text = ""
        self._status_type = "idle"
        self._version = ""
        self._changelog = ""
        self._current_version = ""
        self._download_url = ""
        self._downloading = False
        self._download_progress = 0
        self._download_total = 0

        self._current_version = AppVersion.display()

    # ── QML 属性 ──

    @Property(bool, notify=downloadingChanged)
    def downloading(self) -> bool:
        return self._downloading

    @Property(str, constant=True)
    def currentVersion(self) -> str:
        return self._current_version

    @Property(bool, notify=checkingChanged)
    def checking(self) -> bool:
        return self._checking

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=statusTypeChanged)
    def statusType(self) -> str:
        return self._status_type

    @Property(str, notify=versionInfoChanged)
    def version(self) -> str:
        return self._version

    @Property(str, notify=versionInfoChanged)
    def changelog(self) -> str:
        return self._changelog

    @Property(int, notify=downloadProgressChanged)
    def downloadProgress(self) -> int:
        return self._download_progress

    @Property(int, notify=downloadTotalChanged)
    def downloadTotal(self) -> int:
        return self._download_total

    # ── 引擎注入 ──

    @classmethod
    def set_engine(cls, engine: QQmlApplicationEngine) -> None:
        """在 main.py 中调用一次，注入 QML 引擎引用。

        UpdateService 需要引擎引用来动态创建 UpdateWindow。
        """
        cls._engine = engine

    # ── UpdateWindow 生命周期 ──

    def _show_update_window(self, *, qml_dir: str | None = None) -> None:
        """创建并显示独立的 UpdateWindow。

        如果窗口已存在且 C++ 对象有效，则聚焦窗口而非新建。
        """
        from backend.utils.logger import log

        # ── 复用已存在的窗口 ──
        if self._update_window is not None:
            try:
                self._update_window.setProperty("visible", True)
                self._update_window.raise_()
                self._update_window.requestActivate()
                log.debug("UpdateWindow 已聚焦")
                return
            except RuntimeError:
                # C++ 对象已被 Qt 销毁，清理引用后重新创建
                log.debug("UpdateWindow 的 C++ 对象已被销毁，重新创建")
                self._update_window = None
                self._update_component = None

        engine = UpdateService._engine
        if engine is None:
            log.warning("_engine 未注入，无法创建 UpdateWindow")
            return

        if qml_dir is None:
            from common.paths import QML_DIR
            qml_dir = str(QML_DIR)

        qml_path = Path(qml_dir) / "components" / "UpdateWindow.qml"
        log.debug(f"加载 UpdateWindow: {qml_path}")
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_path)))
        if component.isError():
            log.warning(f"UpdateWindow.qml 加载失败: {component.errorString()}")
            return

        log.debug(
            f"创建 UpdateWindow 实例 — "
            f"version={self._version!r} changelog_len={len(self._changelog)}"
        )
        win = component.create()
        if win is None:
            log.warning(f"UpdateWindow 创建失败: {component.errorString()}")
            return

        # QML 通过 UpdateService 上下文属性绑定，无需手动注入或信号转发
        win.updateNow.connect(self.downloadAndInstall)
        # 「稍后再说」/ ✕ 图标 和 X 按钮，都走 closing 信号关闭
        win.remindLater.connect(win.close)
        win.closing.connect(self._on_window_closing)

        self._update_window = win
        self._update_component = component  # 必须保持引用，否则 Python GC 回收组件时会连带销毁 Window
        win.setProperty("visible", True)
        log.debug("UpdateWindow 已显示")

    # ── 窗口关闭 ──

    def _on_window_closing(self) -> None:
        """QML Window 关闭时，清理 Python 侧引用。

        同时释放 QQmlComponent 引用，避免不必要的内存占用。
        下次 _show_update_window 会重新创建组件和窗口。
        """
        self._update_window = None
        self._update_component = None

    # ── 公开槽 ──

    @Slot()
    def checkForUpdates(self) -> None:
        """检查是否有可用更新"""
        from backend.utils.logger import log

        if self._checking:
            return
        self._checking = True
        self._status_text = "正在检查更新…"
        self._status_type = "checking"
        self.checkingChanged.emit()
        self.statusTextChanged.emit()
        self.statusTypeChanged.emit()
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

    # ── 内部回调 ──

    def _on_check_finished(self, result: object, error: object, using_mock: bool) -> None:
        from backend.utils.logger import log

        self._checking = False
        self.checkingChanged.emit()

        if error is not None:
            self._status_text = f"检查失败: {error}"
            self._status_type = "error"
            self.statusTextChanged.emit()
            self.statusTypeChanged.emit()
            self.updateCheckFailed.emit(str(error))
            log.info(f"检查更新失败: {error}")
            return

        if result is None:
            mock_hint = " (本地模拟器)" if using_mock else ""
            self._status_text = f"已是最新版本{mock_hint}"
            self._status_type = "uptodate"
            self.statusTextChanged.emit()
            self.statusTypeChanged.emit()
            self.updateCheckNone.emit(self._status_text)
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
            self._status_text = f"发现新版本 {self._version}{mock_hint}"
            self._status_type = "available"
            self.statusTextChanged.emit()
            self.statusTypeChanged.emit()
            self.updateFound.emit()
            log.info(f"发现新版本 {self._version}{mock_hint}")
            self._show_update_window()
        else:
            self._status_text = f"已是最新版本{mock_hint}"
            self._status_type = "uptodate"
            self.statusTextChanged.emit()
            self.statusTypeChanged.emit()
            self.updateCheckNone.emit(self._status_text)

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

    def _install(self, setup_path: Path) -> None:
        from backend.utils.app_updater import UPDATE_OWNER, UPDATE_REPO, AppUpdater
        AppUpdater(UPDATE_OWNER, UPDATE_REPO).install(setup_path)