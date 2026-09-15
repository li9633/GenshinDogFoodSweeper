"""圣遗物扫描器 — 全量扫描工作线程

职责边界：

- **遍历骨架**复用 :mod:`backend.automation.sweep` 的 ``ListSweep``（与锁定器/清理器共用）；
- 本模块只保留**扫描特有的差异**：背包数量与分页、首尾锚点定位流程、
  :class:`ScanPolicy`（五星预筛 / 空格子跳过 / 去重 / 尾锚点与数量停止 / 结果收集）；
- **保存**通过 ``SaveJob`` 完成（格式实现见 ``backend/features/artifact_save``），
  扫描器不知道也不关心存成什么格式。

冻结模块（``slot_detector`` / ``page_scroller`` / ``slider_scroller``）经
``sweep_adapters`` 的端口适配器原样接入。
"""

from __future__ import annotations

from datetime import datetime
from time import perf_counter, sleep
from typing import Any

from PySide6.QtCore import QThread, Signal

from backend.automation.anchor_locator import AnchorLocator
from backend.automation.artifact_count_ocr import ocr_artifact_count
from backend.automation.scan_stop_policy import StopPolicy
from backend.automation.screen_capture import ScreenshotCapture
from backend.automation.sweep import BaseSweepPolicy, ListSweep, SweepObserver
from backend.automation.sweep_adapters import (
    DetectorSlotFinder,
    MousePointer,
    RecognizerArtifactReader,
    ScrollerNavigator,
    WindowScreenSource,
)
from backend.contracts.artifact_save import SaveResult
from backend.contracts.sweep import SlotContext, SweepSummary, SweepTiming
from backend.domain.artifact_deduplicator import ArtifactDeduplicator
from backend.exceptions.automation import OcrModelNotReadyError
from backend.features.artifact_save import SaveJob, build_dataset
from backend.models.artifact import ArtifactInfo
from backend.models.scan_models import FullScanRequest, ScanMeta, StopMode, StopReason
from backend.models.slot_models import SlotObject
from backend.utils.logger import log
from common.datetime_helper import DateTimeHelper

# 每识别 N 件打印一次进度与预计剩余时间（原先每件一条会淹没日志）
_LOG_PROGRESS_EVERY = 10

# 扫描时序：点击间隔沿用 0.35s，另加详情面板稳定等待
_SCAN_TIMING = SweepTiming(detail_settle_s=0.15)


class _ScanError(Exception):
    """扫描过程中的可预期失败 —— 消息会原样展示给用户"""


class ScanPolicy(BaseSweepPolicy):
    """扫描策略：``StopPolicy`` + 去重 + 结果收集"""

    def __init__(
        self,
        *,
        stop_policy: StopPolicy,
        tail_info: ArtifactInfo | None,
        bag_count: int,
        on_result: Any = None,
        log_every: int = _LOG_PROGRESS_EVERY,
    ) -> None:
        self._policy = stop_policy
        self._tail_info = tail_info
        self._bag_count = bag_count
        self._on_result = on_result
        self._log_every = log_every
        self._pre_filter = stop_policy.slot_pre_filter()
        self._last_logged = 0
        self._started_perf = perf_counter()

        self.results: list[ArtifactInfo] = []
        self.stop_reason: StopReason | None = None
        self.dedup_skipped = 0

    # 遍历钩子

    def should_click(self, slot: SlotObject) -> bool:
        """「只认五星」模式下先按格子星级跳过非五星，省一次点击 + OCR"""
        if self._pre_filter is None:
            return True
        return self._pre_filter(slot)

    def should_read(self, slot: SlotObject, image: Any) -> bool:
        """空格子直接跳过（点击无害，但没必要再花一次 OCR）"""
        return not AnchorLocator.is_empty_slot(slot.cx, slot.cy, image)

    def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
        if not self._policy.accepts(artifact):
            return True

        resolved = self._resolve_duplicate(artifact, ctx)
        if resolved is None:
            return True

        if self._tail_info is not None and ArtifactDeduplicator.is_duplicate(
            resolved, self._tail_info
        ):
            log.info("扫描到尾锚点(强化材料)，停止扫描")
            self.stop_reason = StopReason.TAIL_ANCHOR
            return False

        self.results.append(resolved)
        if self._on_result:
            self._on_result(resolved, ctx)
        self._log_progress()

        reason = self._policy.count_stop_reason(
            scanned=len(self.results), bag_count=self._bag_count
        )
        if reason is not None:
            log.info(f"达到停止条件（{reason.label}），停止扫描")
            self.stop_reason = reason
            return False
        return True

    # 去重

    def _resolve_duplicate(
        self, artifact: ArtifactInfo, ctx: SlotContext
    ) -> ArtifactInfo | None:
        """去重：返回应保留的结果，None 表示该件重复、跳过

        与已有结果同页同行同列说明详情面板没刷新，重识别一次；
        仍然重复（或出现在别的格子上）则跳过。
        """
        if not self._policy.dedup_applies(artifact):
            return artifact

        existing = self._find_duplicate(artifact)
        if existing is None:
            return artifact

        same_place = (
            existing.page == artifact.page
            and existing.row == artifact.row
            and existing.col == artifact.col
        )
        if not same_place or ctx.reread is None:
            self.dedup_skipped += 1
            return None

        log.debug(
            f"同位重复 P{ctx.page + 1}R{ctx.slot.row}C{ctx.slot.col}，面板未刷新，重新识别..."
        )
        retried = ctx.reread()
        if retried is None:
            self.dedup_skipped += 1
            return None
        retried.page, retried.row, retried.col = artifact.page, artifact.row, artifact.col
        if self._find_duplicate(retried) is not None:
            self.dedup_skipped += 1
            return None
        return retried

    def _find_duplicate(self, artifact: ArtifactInfo) -> ArtifactInfo | None:
        return next(
            (
                seen
                for seen in self.results
                if ArtifactDeduplicator.is_duplicate(artifact, seen)
            ),
            None,
        )

    # 进度日志（按件数限流）

    def _log_progress(self) -> None:
        scanned = len(self.results)
        if scanned - self._last_logged < self._log_every:
            return
        self._last_logged = scanned
        total = self._policy.progress_total(self._bag_count)
        elapsed = perf_counter() - self._started_perf
        remaining = (elapsed / scanned) * max(0, total - scanned) if scanned else 0.0
        log.info(
            f"已扫描 {scanned}/{total} 件，"
            f"用时 {_fmt_duration(elapsed)}，预计剩余 {_fmt_duration(remaining)}"
        )


class FullScanWorker(QThread):
    """后台线程：圣遗物全量扫描

    步骤：
    1. 聚焦游戏窗口 → 2. 初始化 OCR 引擎 → 3. 识别背包数量并计算分页
    4. （锚点模式）滑块到顶 → 识别首锚点 → 滑块到底 → 识别尾锚点 → 回到顶部
    5. 逐页逐格：点击 → 识别 → 判定 → 收集，按策略停止
    6. 组装数据集（含套装效果回填）→ 交给 SaveJob 保存
    """

    # 过程信号
    stepChanged = Signal(str)
    progressChanged = Signal(int, int)
    pageChanged = Signal(int, int)
    artifactScanned = Signal(str, bool)  # (简报, 是否为强化材料)

    # 结果信号
    saveCompleted = Signal(object)  # SaveResult
    scanCompleted = Signal(object)  # ScanMeta
    errorOccurred = Signal(str)

    def __init__(
        self,
        request: FullScanRequest,
        *,
        capture: Any = None,
        save_job: SaveJob | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request = request
        self._slot_config = request.slot_config
        self._save_job = save_job
        self._capture = capture
        self._policy = StopPolicy(
            mode=request.stop_mode,
            fixed_count=request.fixed_count,
            dedup_enabled=request.dedup_enabled,
        )

        # 运行期状态
        self._stop_requested = False
        self._stop_reason: StopReason | None = None
        self._results: list[ArtifactInfo] = []
        self._tail_info: ArtifactInfo | None = None
        self._bag_count = 0
        self._total_pages = 1
        self._dedup_skipped = 0
        self._started_at: datetime | None = None

    # 对外控制

    def stop(self) -> None:
        """请求停止（可从任意线程调用，遍历在每个检查点退出）"""
        self._stop_requested = True

    # 主流程

    def run(self) -> None:
        try:
            meta = self._scan()
        except OcrModelNotReadyError:
            self.errorOccurred.emit(OcrModelNotReadyError._MESSAGE)
            return
        except _ScanError as exc:
            self.errorOccurred.emit(str(exc))
            return
        # 后台线程必须兜住一切：异常一旦逃出 run() 就没人知道扫描为什么没有结果
        except Exception as exc:
            log.exception(f"全量扫描异常: {exc}")
            self.errorOccurred.emit(str(exc))
            return

        if self._save_job is not None:
            self.saveCompleted.emit(self._save(self._save_job, meta))
        self.scanCompleted.emit(meta)

    def _scan(self) -> ScanMeta:
        """扫描主流程；可预期失败抛 _ScanError，用户停止则尽早返回"""
        self._started_at = DateTimeHelper.now()

        self._screen = WindowScreenSource(self._slot_config, self._capture)
        self._slot_finder = DetectorSlotFinder(self._slot_config)
        self._pointer = MousePointer()
        self._navigator = ScrollerNavigator(
            self._slot_config,
            tick_delay_ms=self._request.tick_delay_ms,
            page_settle_ms=self._request.page_settle_ms,
        )

        self.stepChanged.emit("正在聚焦游戏窗口...")
        self._screen.prepare()

        ocr = self._create_ocr()
        self._reader = RecognizerArtifactReader(
            self._slot_config, ocr, fields=RecognizerArtifactReader.SCAN_FIELDS
        )

        self._resolve_scope(ocr)
        if self._abort_requested():
            return self._build_meta(StopReason.USER_STOP)

        if self._policy.uses_anchor:
            self._locate_anchors()
            if self._abort_requested():
                return self._build_meta(StopReason.USER_STOP)

        policy = ScanPolicy(
            stop_policy=self._policy,
            tail_info=self._tail_info,
            bag_count=self._bag_count,
            on_result=self._on_result,
        )
        # 与策略共享同一个结果列表：遍历过程中 len() 即为实时进度
        self._results = policy.results
        sweep = ListSweep(
            screen=self._screen,
            pointer=self._pointer,
            slot_finder=self._slot_finder,
            reader=self._reader,
            navigator=self._navigator,
            timing=SweepTiming(
                detail_settle_s=self._request.detail_settle_s,
                tick_delay_ms=self._request.tick_delay_ms,
                page_settle_ms=self._request.page_settle_ms,
            ),
        )
        summary = sweep.run(
            policy=policy,
            observer=SweepObserver(on_page_start=self._on_page_start),
            stop_check=self._abort_requested,
            total_pages=self._total_pages,
        )

        self._stop_reason = policy.stop_reason
        self._dedup_skipped = policy.dedup_skipped
        self._apply_summary_reason(summary)
        self._log_totals()
        return self._build_meta(self._final_reason())

    def _apply_summary_reason(self, summary: SweepSummary) -> None:
        """把遍历骨架的结束原因映射为扫描语义（策略原因优先）"""
        if self._stop_reason is not None:
            return
        if summary.stopped_reason == SweepSummary.USER_STOP:
            self._stop_requested = True

    def _final_reason(self) -> StopReason:
        """结束原因：策略/锚点触发 → 用户停止 → 全部扫完"""
        if self._stop_reason is not None:
            return self._stop_reason
        return StopReason.USER_STOP if self._stop_requested else StopReason.COMPLETED

    def _create_ocr(self):
        self.stepChanged.emit("正在初始化 OCR 引擎...")
        from backend.automation.ocr_engine import OcrEngine  # 延迟导入：引擎依赖较重

        return OcrEngine.create_ocr(self._request.engines_dir)

    def _resolve_scope(self, ocr) -> None:
        """识别背包装备数量（若该模板显示数量）并计算总页数"""
        artifacts_per_page = self._slot_config.rows * self._slot_config.cols
        self._bag_count = 0
        self._total_pages = 1

        if not self._slot_config.has_artifact_count:
            # 不显示数量的界面（如分解页）只能扫当前页
            self.stepChanged.emit(f"扫描模式: {self._slot_config.name}")
            return

        self.stepChanged.emit("正在识别背包圣遗物数量...")
        count = ocr_artifact_count(ScreenshotCapture(), ocr)
        if self._abort_requested():
            return
        if count <= 0:
            raise _ScanError(
                "未能识别圣遗物数量，请确认已打开背包界面并切换到圣遗物页面"
            )

        self._bag_count = count
        self._total_pages = max(1, (count + artifacts_per_page - 1) // artifacts_per_page)
        self.stepChanged.emit(f"共 {count} 个圣遗物, {self._total_pages} 页")
        self.progressChanged.emit(0, self._policy.progress_total(count))
        if self._policy.mode is StopMode.FIXED_COUNT and 0 < self._request.fixed_count < count:
            self.stepChanged.emit(
                f"固定数量模式: 扫描 {self._request.fixed_count} / {count} 件"
            )

    # 锚点流程（扫描特有）

    def _locate_anchors(self) -> None:
        """首锚点 → 尾锚点定位（仅「首尾锚点」模式）"""
        self.stepChanged.emit("正在滚动到顶部...")
        self._navigator.to_top()
        if self._abort_requested():
            return

        self.stepChanged.emit("正在识别首锚点...")
        first_x, first_y = self._request.anchor_first_center
        first_info = self._click_and_recognize(first_x, first_y)
        if self._abort_requested():
            return
        if first_info:
            first_info.page = first_info.row = first_info.col = 0
            display = AnchorLocator.format_artifact_short(first_info)
            self.stepChanged.emit(f"首锚点: {display}")
            log.info(f"首锚点识别: {display}")

        self.stepChanged.emit("正在滚动到底部...")
        try:
            self._navigator.to_bottom()
        except RuntimeError as exc:
            raise _ScanError(str(exc)) from exc
        if self._abort_requested():
            return

        self.stepChanged.emit("正在定位尾锚点...")
        self._recognize_tail_anchor()
        if self._abort_requested():
            return

        self.stepChanged.emit("正在回到顶部...")
        self._navigator.to_top()

    def _recognize_tail_anchor(self) -> None:
        """识别列表末格作为尾锚点（强化材料），用于「扫到它即停」"""
        image = self._screen.capture()
        if image is None:
            raise _ScanError("截图失败，无法定位尾锚点")

        det_result = self._slot_finder.find(image)
        slots = list(getattr(det_result, "slots", []) or [])
        if not slots:
            log.warning("尾锚点定位失败：未检测到任何格子，将扫描至末尾")
            return

        last_slot = slots[-1]
        tail_info = self._click_and_recognize(last_slot.cx, last_slot.cy)
        if tail_info is None:
            log.warning("尾锚点识别失败，将扫描至末尾")
            return

        tail_info.page = tail_info.row = tail_info.col = -1
        display = AnchorLocator.format_artifact_short(tail_info)
        self.stepChanged.emit(f"尾锚点: {display}")
        log.info(f"尾锚点识别: {display}")

        if tail_info.is_material:
            self._tail_info = tail_info
        else:
            # 尾锚点不是强化材料时无法据此判定终点，退化为扫到数量耗尽
            log.warning("尾锚点不是强化材料，无法使用锚点停止，将扫描至末尾")
            self._tail_info = None

    def _click_and_recognize(self, x: int, y: int) -> ArtifactInfo | None:
        self._pointer.click(x, y)
        sleep(self._request.detail_settle_s)
        image = self._screen.capture()
        if image is None:
            return None
        return self._reader.read(image)

    # 遍历回调

    def _on_page_start(self, page: int, slots_total: int) -> None:
        self.stepChanged.emit(f"正在扫描第 {page + 1}/{self._total_pages} 页...")
        self.pageChanged.emit(page + 1, self._total_pages)

    def _on_result(self, artifact: ArtifactInfo, ctx: SlotContext) -> None:
        """每收集一件（已过去重）：实时列表 + 进度"""
        self.artifactScanned.emit(
            AnchorLocator.format_artifact_short(artifact), artifact.is_material
        )
        self.progressChanged.emit(
            len(self._results), self._policy.progress_total(self._bag_count)
        )

    # 收尾

    def _log_totals(self) -> None:
        """收尾核对：自然扫完但数量对不上时告警，便于发现漏扫"""
        scanned = len(self._results)
        if (
            self._bag_count > 0
            and self._final_reason() is StopReason.COMPLETED
            and scanned < self._bag_count
        ):
            log.warning(
                f"数量不匹配: 背包{self._bag_count}个, 实际识别{scanned}个, "
                f"差异{self._bag_count - scanned}个"
            )
        detail = f"识别 {scanned} 件"
        if self._bag_count > 0:
            detail += f" / 背包 {self._bag_count} 件"
        if self._dedup_skipped:
            detail += f" / 去重跳过 {self._dedup_skipped} 件"
        log.info(f"全量扫描结束（{self._final_reason().label}）: {detail}")

    def _build_meta(self, reason: StopReason) -> ScanMeta:
        finished_at = DateTimeHelper.now()
        return ScanMeta(
            started_at=self._started_at or finished_at,
            finished_at=finished_at,
            scanned=len(self._results),
            total_pages=self._total_pages,
            stop_mode=self._request.stop_mode,
            stopped_by=reason,
            slot_config_name=self._slot_config.name,
            bag_count=self._bag_count or None,
            dedup_skipped=self._dedup_skipped,
        )

    def _save(self, save_job: SaveJob, meta: ScanMeta) -> SaveResult:
        """组装数据集并交给保存格式实现（套装效果回填由 build_dataset 统一完成）"""
        self.stepChanged.emit("正在保存扫描结果...")
        dataset = build_dataset(self._results, meta)
        return save_job.run(dataset)

    def _abort_requested(self) -> bool:
        return self._stop_requested or self._stop_reason is not None


def _fmt_duration(seconds: float) -> str:
    """秒 → ``MM:SS``"""
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"
