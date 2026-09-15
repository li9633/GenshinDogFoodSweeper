"""App 更新 Presenter

承担 AboutTab 和 UpdateWindow 的 Presenter 职责：
- AboutTab → checking、checkResultText、checkResultIsError、checkForUpdates
- UpdateWindow → version、changelog、downloading、downloadAndInstall
- UpdateWindow 生命周期管理（继承 WindowPresenter）

纯业务逻辑委托给 AppUpdater（backend/utils/app_updater.py）。
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot
from utils.logger import log

from backend.ui.presenters.window_presenter import WindowPresenter
from backend.ui.presenters.worker_host import WorkerHost
from common.format_utils import FormatUtils
from common.version_manager import AppVersion


class _CheckWorker(QThread):
    """版本检查工作线程"""

    checkCompleted = Signal(object, object)

    def run(self) -> None:
        from backend.features.update.app_updater import (
            UPDATE_OWNER,
            UPDATE_REPO,
            AppUpdater,
        )
        from backend.utils.logger import log

        try:
            updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO)
            log.debug("[_CheckWorker] 开始 is_update_available() …")
            has_update, info, error = updater.is_update_available()
            log.debug(
                f"[_CheckWorker] is_update_available() → "
                f"has_update={has_update}, "
                f"info={'None' if info is None else ('{tag:' + info.get('tag','?') + '}')}, "
                f"error={error!r}"
            )

            if error:
                self.checkCompleted.emit(None, error)
            else:
                self.checkCompleted.emit((has_update, info), None)
        except Exception as e:
            log.debug(f"[_CheckWorker] 异常: {type(e).__name__}: {e}", exc_info=True)
            self.checkCompleted.emit(None, str(e))


class _DownloadWorker(QThread):
    """安装包下载工作线程"""

    progress = Signal(int, int)
    finished_download = Signal(bool, str)

    def __init__(self, url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url
        self._cancelled = False

    def stop(self) -> None:
        """请求取消下载"""
        self._cancelled = True

    def run(self) -> None:
        from backend.features.update.app_updater import (
            UPDATE_OWNER,
            UPDATE_REPO,
            AppUpdater,
            CancelDownloadError,
        )

        try:
            updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO)
            path = updater.download(
                self._url,
                progress_cb=self.progress.emit,
                cancel_check=lambda: self._cancelled,
            )
            self.finished_download.emit(True, str(path))
        except CancelDownloadError:
            self.finished_download.emit(False, "CANCELLED")
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
    checkResultTextChanged = Signal()
    checkResultIsErrorChanged = Signal()

    # UpdateWindow 数据
    versionInfoChanged = Signal()
    downloadingChanged = Signal()
    downloadProgressChanged = Signal()
    downloadTotalChanged = Signal()

    # UpdateWindow 展示文案
    versionLabelChanged = Signal()
    progressLabelChanged = Signal()
    progressRatioChanged = Signal()
    progressPercentTextChanged = Signal()
    progressSpeedTextChanged = Signal()
    changelogOrPlaceholderChanged = Signal()
    updateButtonTextChanged = Signal()
    networkErrorTextChanged = Signal()

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
        self._check_result_text = ""
        self._check_result_is_error = False

        # ── 展示文案
        self._version_label = ""
        self._progress_label = "正在下载…"
        self._progress_ratio: float = 0.0
        self._progress_percent_text = ""
        self._progress_speed_text = ""
        self._last_progress_ts: float = 0.0
        self._last_progress_bytes: int = 0
        self._changelog_or_placeholder = "暂无更新日志"
        self._update_button_text = "立即更新"
        self._network_error_text = ""

        # ── 工作线程（检查与下载互不干扰，各自单飞）──
        self._check_host = WorkerHost(self)
        self._download_host = WorkerHost(self)

        self._current_version = AppVersion.display()

    # ════════════════════════════════════════════
    # QML 属性 — AboutTab
    # ════════════════════════════════════════════

    @Property(bool, notify=checkingChanged)
    def checking(self) -> bool:
        return self._checking

    @Property(str, notify=checkResultTextChanged)
    def checkResultText(self) -> str:
        return self._check_result_text

    @Property(bool, notify=checkResultIsErrorChanged)
    def checkResultIsError(self) -> bool:
        return self._check_result_is_error

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
    # QML 属性 — 展示文案（Python 侧预计算）
    # ════════════════════════════════════════════

    @Property(str, notify=versionLabelChanged)
    def versionLabel(self) -> str:
        return self._version_label

    @Property(str, notify=progressLabelChanged)
    def progressLabel(self) -> str:
        return self._progress_label

    @Property(float, notify=progressRatioChanged)
    def progressRatio(self) -> float:
        return self._progress_ratio

    @Property(str, notify=progressPercentTextChanged)
    def progressPercentText(self) -> str:
        return self._progress_percent_text

    @Property(str, notify=progressSpeedTextChanged)
    def progressSpeedText(self) -> str:
        return self._progress_speed_text

    @Property(str, notify=changelogOrPlaceholderChanged)
    def changelogOrPlaceholder(self) -> str:
        return self._changelog_or_placeholder

    @Property(str, notify=updateButtonTextChanged)
    def updateButtonText(self) -> str:
        return self._update_button_text

    @Property(str, notify=networkErrorTextChanged)
    def networkErrorText(self) -> str:
        return self._network_error_text

    # ════════════════════════════════════════════
    # 公开槽
    # ════════════════════════════════════════════

    @Slot()
    def checkForUpdates(self) -> None:
        """检查是否有可用更新（AboutTab 按钮调用）"""
        from backend.utils.logger import log

        if self._checking or self._check_host.busy:
            return
        self._checking = True
        self.checkingChanged.emit()

        # 开始新一轮检查，清除上一次的检查结果
        if self._check_result_text:
            self._check_result_text = ""
            self.checkResultTextChanged.emit()

        log.info("正在检查更新…")
        self._clear_network_error()

        worker = _CheckWorker()
        worker.checkCompleted.connect(self._on_check_finished)
        self._check_host.start(worker)

    @Slot()
    def downloadAndInstall(self) -> None:
        """下载安装包并拉起安装程序"""
        if self._downloading or self._download_host.busy or not self._download_url:
            return

        self._downloading = True
        self._download_progress = 0
        self._download_total = 0
        self._last_progress_ts = time.time()
        self._last_progress_bytes = 0
        self.downloadingChanged.emit()
        self.downloadProgressChanged.emit()
        self.downloadTotalChanged.emit()
        self._refresh_download_display(time.time())
        self._refresh_button_text()
        self._clear_network_error()

        worker = _DownloadWorker(self._download_url)
        worker.progress.connect(self._on_download_progress)
        worker.finished_download.connect(self._on_download_finished)
        self._download_host.start(worker)

    @Slot()
    def cancelDownload(self) -> None:
        """取消当前下载"""
        if not self._downloading:
            return
        self._download_host.stop()
        self._downloading = False
        self.downloadingChanged.emit()
        self._refresh_button_text()

    # ════════════════════════════════════════════
    # 窗口生命周期（继承 WindowPresenter）
    # ════════════════════════════════════════════

    def _on_before_create(self, win: QObject) -> None:
        """UpdateWindow 创建后：连接 QML 信号"""
        win.updateNow.connect(self.downloadAndInstall)
        win.remindLater.connect(win.close)
        win.cancelDownload.connect(self.cancelDownload)

    # ════════════════════════════════════════════
    # 内部回调
    # ════════════════════════════════════════════

    def _on_check_finished(
        self, result: object, error: object
    ) -> None:
        from backend.utils.logger import log

        self._checking = False
        self.checkingChanged.emit()

        if error is not None:
            self._check_result_text = f"检查失败: {error}"
            self._check_result_is_error = True
            self.checkResultTextChanged.emit()
            self.checkResultIsErrorChanged.emit()
            log.warning(f"检查更新失败: {error}")
            self._set_network_error(f"连接 GitHub 失败：{error}")
            return

        if result is None:
            # 无更新
            self._check_result_text = "已是最新版本"
            self._check_result_is_error = False
            self.checkResultTextChanged.emit()
            self.checkResultIsErrorChanged.emit()
            log.info("未发现新版本")
            self._clear_network_error()
            return

        has_update, info = result  # type: ignore[misc]
        if has_update and info:
            # 有更新 → 弹窗接管，清除 AboutTab 提示
            if self._check_result_text:
                self._check_result_text = ""
                self.checkResultTextChanged.emit()
            self._clear_network_error()
            self._version = info.get("tag", "?")
            self._changelog = info.get("body", "") or ""
            self._download_url = info.get("download_url", "")
            log.debug(
                f"发现新版本: tag={self._version!r} "
                f"changelog_len={len(self._changelog)} download_url={bool(self._download_url)}"
            )
            self._refresh_version_labels()
            self.versionInfoChanged.emit()
            log.info(f"发现新版本 {self._version}")
            self.show_window()
        else:
            self._check_result_text = "已是最新版本"
            self._check_result_is_error = False
            self.checkResultTextChanged.emit()
            self.checkResultIsErrorChanged.emit()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        now = time.time()
        self._download_progress = downloaded
        if total != self._download_total:
            self._download_total = total
            self.downloadTotalChanged.emit()
        self._refresh_download_display(now)
        self.downloadProgressChanged.emit()

    def _on_download_finished(self, success: bool, filepath: str) -> None:
        if filepath == "CANCELLED":
            return
        self._downloading = False
        self.downloadingChanged.emit()
        self._refresh_button_text()
        if success:
            self._clear_network_error()
            self._install(Path(filepath))
        else:
            log.warning(f"下载安装包失败: {filepath}")
            self._set_network_error("下载失败，请检查网络后重试")
            self.downloadProgressChanged.emit()

    # ════════════════════════════════════════════
    # 展示文案刷新
    # ════════════════════════════════════════════

    def _refresh_version_labels(self) -> None:
        self._version_label = f"版本 {self._version} 可用"
        self._changelog_or_placeholder = self._changelog or "暂无更新日志"
        self.versionLabelChanged.emit()
        self.changelogOrPlaceholderChanged.emit()

    def _refresh_download_display(self, now: float) -> None:
        downloaded = self._download_progress
        total = self._download_total

        if total > 0:
            self._progress_ratio = downloaded / total
            self._progress_label = (
                f"正在下载 {downloaded / 1048576:.1f} / {total / 1048576:.1f} MB"
            )
            self._progress_percent_text = f"{self._progress_ratio * 100:.0f}%"
        elif downloaded > 0:
            self._progress_ratio = 0.0
            self._progress_label = f"正在下载 {downloaded / 1048576:.1f} MB…"
            self._progress_percent_text = ""
        else:
            self._progress_ratio = 0.0
            self._progress_label = "正在下载…"
            self._progress_percent_text = ""

        self._compute_speed_text(downloaded, now)

        self.progressRatioChanged.emit()
        self.progressLabelChanged.emit()
        self.progressPercentTextChanged.emit()
        self.progressSpeedTextChanged.emit()

    def _compute_speed_text(self, downloaded: int, now: float) -> None:
        delta_bytes = downloaded - self._last_progress_bytes
        delta_sec = now - self._last_progress_ts

        if delta_sec > 0 and delta_bytes > 0:
            speed = delta_bytes / delta_sec
            self._progress_speed_text = FormatUtils.speed_bytes(speed)
        else:
            self._progress_speed_text = ""

        self._last_progress_ts = now
        self._last_progress_bytes = downloaded

    def _set_network_error(self, text: str) -> None:
        self._network_error_text = text
        self.networkErrorTextChanged.emit()

    def _clear_network_error(self) -> None:
        if self._network_error_text:
            self._network_error_text = ""
            self.networkErrorTextChanged.emit()

    def _refresh_button_text(self) -> None:
        self._update_button_text = "下载中…" if self._downloading else "立即更新"
        self.updateButtonTextChanged.emit()

    # ════════════════════════════════════════════
    # 安装
    # ════════════════════════════════════════════

    def _install(self, setup_path: Path) -> None:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from backend.features.update.app_updater import (
            UPDATE_OWNER,
            UPDATE_REPO,
            AppUpdater,
        )

        AppUpdater(UPDATE_OWNER, UPDATE_REPO).install(setup_path)

        # 关闭更新窗口
        self.close_window()

        # 延迟退出，让 Qt 事件循环有机会处理完挂起的绑定更新，
        # 避免 QML 属性绑定在 Presenter 销毁时报 TypeError
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(100, app.quit)