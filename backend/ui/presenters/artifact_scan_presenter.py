"""
圣遗物扫描 Presenter
====================
全量圣遗物扫描的主流程 Presenter。

本 Presenter 仅负责：
- QML 属性/信号/Slot 的声明与暴露
- UI 状态管理
- 全量扫描调度（调 FullScanWorker）
- 配置管理（SlotDetectorConfig 切换）
"""

from __future__ import annotations

from models.artifact import ArtifactInfo
from PySide6.QtCore import Property, QObject, Signal, Slot
from ui.lifecycle import OnWindowReady
from utils.logger import log

from backend.automation.artifact_scanner import FullScanWorker
from backend.automation.mouse_controller import MouseController
from backend.automation.slot_detector import BAG_SLOT_CONFIG
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture
from backend.utils.settings_manager import settings
from common.paths import ENGINES, SCAN_RESULT


class ArtifactScanPresenter(QObject, OnWindowReady):
    """圣遗物扫描 — 注册为 QML context property `ArtifactScan`"""

    # ========== 信号 ==========

    # 全量扫描
    fullScanStepChanged = Signal()
    fullScanProgressChanged = Signal()
    fullScanPageChanged = Signal()
    fullScanRunningChanged = Signal()
    fullScanSavedPathChanged = Signal()

    # 扫描选项变更
    scanOptionsChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        OnWindowReady.__init__(self)
        self._mouse = MouseController()

    def on_window_ready(self) -> None:
        self._capture = ScreenshotCapture()

        self._active_config = BAG_SLOT_CONFIG

        # 全量扫描
        self._full_scan_worker: FullScanWorker | None = None
        self._full_scan_step = ""
        self._full_scan_progress = ""
        self._full_scan_running = False
        self._full_scan_current_page = 0
        self._full_scan_total_pages = 0
        self._full_scan_results: list[ArtifactInfo] = []
        self._full_scan_saved_path: str = ""

    # ==================================================================
    # 扫描选项（扫描前设置，同步到 settings）
    # ==================================================================

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

    _STOP_MODE_KEYS = ("anchor", "five_star_only", "fixed_count")

    @Property(int, notify=scanOptionsChanged)
    def scanStopModeIndex(self) -> int:
        mode = self.scanStopMode or "anchor"
        try:
            return self._STOP_MODE_KEYS.index(mode)
        except ValueError:
            return 0

    @Slot(int)
    def setScanStopModeByIndex(self, index: int) -> None:
        if 0 <= index < len(self._STOP_MODE_KEYS):
            self.setScanStopMode(self._STOP_MODE_KEYS[index])

    @Property(int, notify=scanOptionsChanged)
    def scanFixedCount(self) -> int:
        return settings.get_int("scan.fixed_count")

    @Slot(int)
    def setScanFixedCount(self, value: int) -> None:
        settings.set("scan.fixed_count", str(value))
        self.scanOptionsChanged.emit()

    # ==================================================================
    # 全量扫描
    # ==================================================================

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

    @Property(str, notify=fullScanSavedPathChanged)
    def fullScanSavedPath(self) -> str:
        return self._full_scan_saved_path

    @Slot()
    def startFullScan(self) -> None:
        """开始全量圣遗物扫描 — 参数从当前 SlotDetectorConfig 读取"""
        if self._full_scan_running:
            log.warning("全量扫描已在运行中")
            return
        ox, oy = WindowHelper.get_origin()
        if ox == 0 and oy == 0:
            log.warning("未检测到原神窗口")
            return

        cfg = self._active_config
        roi = cfg.roi or (0, 0, 0, 0)
        engines_dir = ENGINES

        self._full_scan_results = []
        self._full_scan_saved_path = ""

        log.info("全量扫描开始 (保存目录: scan_result/)")

        def _save_results(results: list[ArtifactInfo]) -> None:
            import json
            from dataclasses import asdict

            from backend.database.repository.artifact_set_repo import ArtifactSetRepo
            from backend.utils.datetime_helper import DateTimeHelper

            all_sets = {s.id: s for s in ArtifactSetRepo.find_all()}
            for r in results:
                if r.set_id is not None:
                    artifact_set = all_sets.get(r.set_id)
                    if artifact_set:
                        r.set_effects = artifact_set.set_effects

            out_dir = SCAN_RESULT
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"scan_{DateTimeHelper.file_timestamp()}.json"
            filepath = out_dir / filename
            data = [asdict(r) for r in results]
            for d in data:
                d.pop("raw_texts", None)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._full_scan_saved_path = str(filepath)
            self.fullScanSavedPathChanged.emit()
            log.info(f"扫描结果已保存: {filepath} ({len(data)} 件)")

        self._full_scan_worker = FullScanWorker(
            mouse=self._mouse,
            capture=self._capture,
            engines_dir=engines_dir,
            margin_x=roi[0],
            margin_y=roi[1],
            item_w=cfg.slot_w,
            item_h=cfg.slot_h,
            gap=24,
            anchor_first_x=roi[0],
            anchor_first_y=roi[1],
            anchor_first_w=cfg.slot_w,
            anchor_first_h=cfg.slot_h,
            slot_config=cfg,
            tick_delay_ms=30,
            page_settle_ms=200,
            click_interval_ms=150,
            stop_mode=settings.get("scan.stop_mode") or "anchor",
            on_complete=_save_results,
        )
        self._full_scan_worker.stepChanged.connect(self._on_full_scan_step)
        self._full_scan_worker.progressChanged.connect(self._on_full_scan_progress)
        self._full_scan_worker.pageChanged.connect(self._on_full_scan_page)
        self._full_scan_worker.finished.connect(self._on_full_scan_finished)
        self._full_scan_worker.errorOccurred.connect(self._on_full_scan_error)

        self._full_scan_running = True
        self._full_scan_step = "正在初始化..."
        self._full_scan_progress = ""
        self._full_scan_current_page = 0
        self._full_scan_total_pages = 0
        self.fullScanRunningChanged.emit()
        self.fullScanStepChanged.emit()
        self._full_scan_worker.start()
        log.info("全量扫描开始")

    @Slot()
    def stopFullScan(self) -> None:
        if self._full_scan_worker is not None:
            self._full_scan_worker.stop()
        log.info("全量扫描已请求停止")

    @Slot()
    def stopAllOperations(self) -> None:
        """全局热键 → 终止所有正在运行的自动化操作"""
        if self._full_scan_running:
            self.stopFullScan()
            log.info("热键终止: 已停止全量扫描")
        else:
            log.debug("热键终止: 无正在运行的操作")

    def _on_full_scan_step(self, step: str) -> None:
        self._full_scan_step = step
        self.fullScanStepChanged.emit()

    def _on_full_scan_progress(self, current: int, total: int) -> None:
        self._full_scan_progress = f"{current}/{total}"
        self.fullScanProgressChanged.emit()

    def _on_full_scan_page(self, current: int, total: int) -> None:
        self._full_scan_current_page = current
        self._full_scan_total_pages = total
        self.fullScanPageChanged.emit()

    def _on_full_scan_finished(self, scanned: int, expected: int) -> None:
        self._full_scan_running = False
        self._full_scan_worker = None
        self._full_scan_step = f"扫描完成: 背包{expected}个, 识别{scanned}个"
        self._full_scan_progress = f"{scanned}/{expected}"
        self.fullScanRunningChanged.emit()
        self.fullScanStepChanged.emit()
        self.fullScanProgressChanged.emit()
        stop_mode = settings.get("scan.stop_mode") or "anchor"
        if stop_mode == "fixed_count":
            log.info(f"全量扫描完成: 固定数量{scanned}个")
        else:
            log.info(f"全量扫描完成: 背包{expected}个, 识别{scanned}个")

    def _on_full_scan_error(self, error: str) -> None:
        self._full_scan_running = False
        self._full_scan_worker = None
        self._full_scan_step = f"扫描出错: {error[:100]}"
        self.fullScanRunningChanged.emit()
        self.fullScanStepChanged.emit()
        log.error(f"全量扫描出错: {error}")