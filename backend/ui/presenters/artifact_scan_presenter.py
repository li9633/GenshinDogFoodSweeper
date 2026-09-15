"""圣遗物扫描 Presenter
====================
本 Presenter 只做三件事：

1. 声明/暴露 QML 属性、信号与 Slot；
2. 维护 UI 状态（步骤文案、进度、页码、保存结果）；
3. 调度扫描：把「扫描模板 + 策略 + 保存任务」组装成请求交给 FullScanWorker，
   再把 worker 的信号翻译成 UI 状态变更。

它**不知道**保存格式怎么实现、扫描模板有哪些几何参数 —— 那些分别封装在
``backend/service/artifact_save`` 与 ``FullScanRequest`` 里。
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import Property, QObject, Signal, Slot

from backend.automation.artifact_scanner import FullScanWorker
from backend.automation.screen_capture import ScreenshotCapture
from backend.automation.window_helper import WindowHelper
from backend.contracts.artifact_save import SaveResult, SaveTarget
from backend.exceptions.automation import GameWindowNotFoundError
from backend.features.artifact_save import (
    DEFAULT_FORMAT_ID,
    SaveJob,
    available_formats,
    create_saver,
    is_known_format,
)
from backend.models.scan_models import FullScanRequest, ScanMeta, StopMode, StopReason
from backend.models.slot_models import BAG_SLOT_CONFIG
from backend.ui.lifecycle import OnWindowReady
from backend.ui.presenters.worker_host import WorkerHost
from backend.utils.logger import log
from backend.utils.qml_url import local_path_from_url
from backend.utils.settings_manager import settings
from common.paths import ENGINES, SCAN_RESULT

_SETTING_SAVE_DIR = "scan.save_dir"
_SETTING_SAVE_FORMAT = "scan.save_format"

_FIXED_COUNT_FALLBACK = 100  # 数量输入框未设置过时的初始值


class ArtifactScanPresenter(QObject, OnWindowReady):
    """圣遗物扫描 — 注册为 QML context property `ArtifactScan`"""

    # 信号

    # 全量扫描
    fullScanStepChanged = Signal()
    fullScanProgressChanged = Signal()
    fullScanProgressTextChanged = Signal()
    fullScanPageChanged = Signal()
    fullScanRunningChanged = Signal()
    fullScanSavedPathChanged = Signal()
    fullScanSaveErrorChanged = Signal()
    fullScanIdleChanged = Signal()

    # 选项变更
    scanOptionsChanged = Signal()
    saveOptionsChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)
        self._capture: ScreenshotCapture | None = None
        self._active_config = BAG_SLOT_CONFIG

        # 全量扫描状态：全部在 __init__ 就绪，QML 首次求值绑定也不会缺属性
        self._host = WorkerHost(self)
        self._full_scan_step = ""
        self._full_scan_progress = ""
        self._full_scan_running = False
        self._full_scan_current_page = 0
        self._full_scan_total_pages = 0
        self._full_scan_saved_path = ""
        self._full_scan_save_error = ""

    def on_window_ready(self) -> None:
        self._capture = ScreenshotCapture()

    # ════════════════════════════════════════════
    # 扫描选项（扫描前设置，直接持久化到 settings）
    # ════════════════════════════════════════════

    _STOP_MODE_KEYS: ClassVar[tuple[StopMode, ...]] = (
        StopMode.ANCHOR,
        StopMode.FIVE_STAR_ONLY,
        StopMode.FIXED_COUNT,
    )

    @Property(bool, notify=scanOptionsChanged)
    def scanEnableDedup(self) -> bool:
        return settings.get_bool("scan.enable_dedup")

    @Slot(bool)
    def setScanEnableDedup(self, value: bool) -> None:
        settings.set("scan.enable_dedup", "true" if value else "false")
        self.scanOptionsChanged.emit()

    @Property(str, notify=scanOptionsChanged)
    def scanStopMode(self) -> str:
        return settings.get("scan.stop_mode")

    @Slot(str)
    def setScanStopMode(self, value: str) -> None:
        settings.set("scan.stop_mode", value)
        self.scanOptionsChanged.emit()

    @Property("QVariantList", notify=scanOptionsChanged)
    def scanStopModeNames(self) -> list[str]:
        """停止条件下拉框选项文案（与 scanStopModeIndex 同源，避免 QML 再抄一份顺序）"""
        return [mode.label for mode in self._STOP_MODE_KEYS]

    @Property(int, notify=scanOptionsChanged)
    def scanStopModeIndex(self) -> int:
        mode = StopMode.parse(settings.get("scan.stop_mode"))
        try:
            return self._STOP_MODE_KEYS.index(mode)
        except ValueError:
            return 0

    @Slot(int)
    def setScanStopModeByIndex(self, index: int) -> None:
        if 0 <= index < len(self._STOP_MODE_KEYS):
            self.setScanStopMode(self._STOP_MODE_KEYS[index].value)

    @Property(bool, notify=scanOptionsChanged)
    def scanShowsDedup(self) -> bool:
        """「去重」选项是否适用当前停止条件"""
        return StopMode.parse(settings.get("scan.stop_mode")) is StopMode.FIVE_STAR_ONLY

    @Property(bool, notify=scanOptionsChanged)
    def scanShowsFixedCount(self) -> bool:
        """「固定数量」选项是否适用当前停止条件"""
        return StopMode.parse(settings.get("scan.stop_mode")) is StopMode.FIXED_COUNT

    @Property(int, notify=scanOptionsChanged)
    def scanFixedCount(self) -> int:
        return settings.get_int("scan.fixed_count")

    @Property(int, notify=scanOptionsChanged)
    def scanFixedCountInitial(self) -> int:
        """数量输入框的初始值（没设置过时给一个可用默认值）"""
        current = settings.get_int("scan.fixed_count")
        return current if current > 0 else _FIXED_COUNT_FALLBACK

    @Slot(int)
    def setScanFixedCount(self, value: int) -> None:
        settings.set("scan.fixed_count", str(value))
        self.scanOptionsChanged.emit()

    # ════════════════════════════════════════════
    # 保存选项（位置 / 格式，由用户在界面上切换）
    # ════════════════════════════════════════════

    @Property(str, notify=saveOptionsChanged)
    def saveDirectory(self) -> str:
        """当前保存目录（绝对路径；未自定义时为内置 scan_result）"""
        return self._resolve_save_dir()

    @Slot(str)
    def setSaveDirectory(self, url: str) -> None:
        """接收 QML FolderDialog 给出的 file:// URL"""
        directory = local_path_from_url(url).strip()
        if not directory:
            return
        settings.set(_SETTING_SAVE_DIR, str(Path(directory)))
        log.info(f"保存目录已切换: {directory}")
        self.saveOptionsChanged.emit()

    @Property("QVariantList", notify=saveOptionsChanged)
    def saveFormatNames(self) -> list[str]:
        """格式下拉框选项文案（默认档由注册表决定，标记在这里拼好）"""
        return [
            f"{info.name}（默认）" if info.id == DEFAULT_FORMAT_ID else info.name
            for info in available_formats()
        ]

    @Property(str, notify=saveOptionsChanged)
    def saveFormatDescription(self) -> str:
        """当前所选格式的说明文案"""
        current = self._resolve_format_id()
        return next(
            (info.description for info in available_formats() if info.id == current),
            "",
        )

    @Property(str, notify=saveOptionsChanged)
    def saveFormatId(self) -> str:
        return self._resolve_format_id()

    @Property(int, notify=saveOptionsChanged)
    def saveFormatIndex(self) -> int:
        ids = [info.id for info in available_formats()]
        current = self._resolve_format_id()
        return ids.index(current) if current in ids else 0

    @Slot(int)
    def setSaveFormatByIndex(self, index: int) -> None:
        formats = available_formats()
        if not 0 <= index < len(formats):
            return
        settings.set(_SETTING_SAVE_FORMAT, formats[index].id)
        log.info(f"保存格式已切换: {formats[index].name}")
        self.saveOptionsChanged.emit()

    # ════════════════════════════════════════════
    # 全量扫描
    # ════════════════════════════════════════════

    @Property(str, notify=fullScanStepChanged)
    def fullScanStep(self) -> str:
        return self._full_scan_step

    @Property(str, notify=fullScanProgressChanged)
    def fullScanProgress(self) -> str:
        return self._full_scan_progress

    @Property(bool, notify=fullScanRunningChanged)
    def fullScanRunning(self) -> bool:
        return self._full_scan_running

    @Property(int, notify=fullScanPageChanged)
    def fullScanCurrentPage(self) -> int:
        return self._full_scan_current_page

    @Property(int, notify=fullScanPageChanged)
    def fullScanTotalPages(self) -> int:
        return self._full_scan_total_pages

    @Property(bool, notify=fullScanIdleChanged)
    def fullScanIdle(self) -> bool:
        """空闲态（既无步骤提示也无进度）—— 界面据此显示「请先选择扫描选项」"""
        return not self._full_scan_step and not self._full_scan_progress

    @Property(str, notify=fullScanRunningChanged)
    def fullScanButtonText(self) -> str:
        """开始/扫描中按钮文案（与 UpdatePresenter.updateButtonText 同一套做法）"""
        return "扫描中…" if self._full_scan_running else "开始扫描"

    @Property(str, notify=fullScanProgressTextChanged)
    def fullScanProgressText(self) -> str:
        """进度展示文案（含页码），在这里拼好，QML 只负责摆放"""
        if not self._full_scan_progress:
            return ""
        if self._full_scan_current_page > 0:
            return (
                f"{self._full_scan_progress} | 第 {self._full_scan_current_page}"
                f"/{self._full_scan_total_pages} 页"
            )
        return self._full_scan_progress

    @Property(str, notify=fullScanSavedPathChanged)
    def fullScanSavedPath(self) -> str:
        return self._full_scan_saved_path

    @Property(str, notify=fullScanSaveErrorChanged)
    def fullScanSaveError(self) -> str:
        return self._full_scan_save_error

    @Slot()
    def startFullScan(self) -> None:
        """开始全量扫描：组装请求 + 保存任务，随后交给 worker"""
        if self._full_scan_running or self._host.busy:
            log.warning("全量扫描已在运行中")
            return
        if self._capture is None:
            log.warning("窗口尚未就绪，无法开始扫描")
            return
        if not self._game_window_ready():
            return

        try:
            request = self._build_request()
        except ValueError as exc:
            # 模板配置不完整（如缺 roi）：直接告诉用户，而不是扫到一半才失败
            self._set_step(f"无法开始扫描: {exc}")
            log.warning(f"无法开始扫描: {exc}")
            return

        save_job = SaveJob(
            saver=create_saver(self._resolve_format_id()),
            target=SaveTarget(directory=Path(self._resolve_save_dir())),
        )
        worker = FullScanWorker(
            request,
            capture=self._capture,
            save_job=save_job,
        )
        worker.stepChanged.connect(self._set_step)
        worker.progressChanged.connect(self._on_progress)
        worker.pageChanged.connect(self._on_page)
        worker.saveCompleted.connect(self._on_saved)
        worker.scanCompleted.connect(self._on_completed)
        worker.errorOccurred.connect(self._on_error)

        self._full_scan_running = True
        self._full_scan_current_page = 0
        self._full_scan_total_pages = 0
        self._full_scan_saved_path = ""
        self._full_scan_save_error = ""
        self._set_step("正在初始化...")
        self._set_progress_text("")
        self.fullScanRunningChanged.emit()
        self.fullScanPageChanged.emit()
        self.fullScanSavedPathChanged.emit()
        self.fullScanSaveErrorChanged.emit()

        self._host.start(worker)
        log.info(
            f"全量扫描开始（保存目录: {self._resolve_save_dir()}，"
            f"格式: {save_job.format_id}）"
        )

    @Slot()
    def stopFullScan(self) -> None:
        if not self._host.busy:
            return
        self._host.stop()
        log.info("全量扫描已请求停止")

    @Slot()
    def stopAllOperations(self) -> None:
        """全局热键 → 终止所有正在运行的自动化操作"""
        if self._full_scan_running or self._host.busy:
            self.stopFullScan()
            log.info("热键终止: 已停止全量扫描")
        else:
            log.debug("热键终止: 无正在运行的操作")

    # ════════════════════════════════════════════
    # worker 信号处理
    # ════════════════════════════════════════════

    def _on_progress(self, current: int, total: int) -> None:
        self._set_progress_text(f"{current}/{total}")

    def _on_page(self, current: int, total: int) -> None:
        self._full_scan_current_page = current
        self._full_scan_total_pages = total
        self.fullScanPageChanged.emit()
        # 页码参与展示文案（"进度 | 第 x/y 页"），改页码也要通知文案绑定
        self.fullScanProgressTextChanged.emit()

    def _on_saved(self, result: SaveResult) -> None:
        """保存结束（成功/失败都走这里），UI 只负责展示结果"""
        self._full_scan_saved_path = (
            str(result.path) if result.ok and result.path else ""
        )
        self._full_scan_save_error = "" if result.ok else result.message
        self.fullScanSavedPathChanged.emit()
        self.fullScanSaveErrorChanged.emit()

    def _on_completed(self, meta: ScanMeta) -> None:
        """扫描结束（自然完成或用户停止）"""
        self._full_scan_running = False
        self._set_progress_text(
            f"{meta.scanned}/{meta.bag_count}" if meta.bag_count else str(meta.scanned)
        )
        self._set_step(_completion_text(meta))
        self.fullScanRunningChanged.emit()
        log.info(f"全量扫描完成: 识别 {meta.scanned} 件（{meta.stopped_by.label}）")

    def _on_error(self, error: str) -> None:
        self._full_scan_running = False
        self._set_step(f"扫描出错: {error[:100]}")
        self.fullScanRunningChanged.emit()
        log.error(f"全量扫描出错: {error}")

    # ════════════════════════════════════════════
    # 内部
    # ════════════════════════════════════════════

    def _build_request(self) -> FullScanRequest:
        """由当前模板与选项构造扫描请求（模板细节封装在请求内部）"""
        return FullScanRequest.from_slot_config(
            self._active_config,
            engines_dir=ENGINES,
            stop_mode=StopMode.parse(settings.get("scan.stop_mode")),
            fixed_count=settings.get_int("scan.fixed_count"),
            dedup_enabled=settings.get_bool("scan.enable_dedup"),
        )

    def _game_window_ready(self) -> bool:
        """原神窗口是否就绪

        ``WindowHelper.get_origin()`` 在找不到窗口时**抛异常**，这里必须接住：
        否则异常会从 QML 调用的槽里冒出去，界面既不开始扫描也不给出任何说明。
        提示由 UI 层负责（异常本身只带消息、不弹窗）。
        """
        try:
            origin_x, origin_y = WindowHelper.get_origin()
        except GameWindowNotFoundError as exc:
            self._notify_window_missing(str(exc))
            return False
        if origin_x == 0 and origin_y == 0:
            self._notify_window_missing(GameWindowNotFoundError._MESSAGE)
            return False
        return True

    def _notify_window_missing(self, message: str) -> None:
        """页面文案 + 弹窗提示（弹窗失败不影响流程）"""
        self._set_step(message)
        log.warning(message)
        try:
            from backend.ui.gmessagebox import GMessageBox

            GMessageBox.warning(message)
        except Exception as exc:
            log.debug(f"提示弹窗失败: {exc}")

    def _resolve_save_dir(self) -> str:
        """用户自定义目录优先，否则用内置 scan_result"""
        return settings.get(_SETTING_SAVE_DIR).strip() or str(SCAN_RESULT)

    def _resolve_format_id(self) -> str:
        """用户选择优先；未知/为空时回退默认格式"""
        chosen = settings.get(_SETTING_SAVE_FORMAT).strip()
        return chosen if is_known_format(chosen) else DEFAULT_FORMAT_ID

    def _set_step(self, step: str) -> None:
        self._full_scan_step = step
        self.fullScanStepChanged.emit()
        self.fullScanIdleChanged.emit()

    def _set_progress_text(self, text: str) -> None:
        self._full_scan_progress = text
        self.fullScanProgressChanged.emit()
        self.fullScanProgressTextChanged.emit()
        self.fullScanIdleChanged.emit()


def _completion_text(meta: ScanMeta) -> str:
    """扫描结束文案（数量来自 worker 汇报的元信息）"""
    if meta.bag_count:
        text = f"扫描完成: 背包{meta.bag_count}个, 识别{meta.scanned}个"
    else:
        text = f"扫描完成: 识别{meta.scanned}个"
    if meta.stopped_by is not StopReason.COMPLETED:
        text += f"（{meta.stopped_by.label}）"
    return text
