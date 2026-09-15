"""自动分解低星圣遗物（清理器）

三个功能共用同一套遍历骨架（``backend/automation/sweep.py``）：

- **阶段一（选择）**：进入分解页面 → 尝试「快速选择」→ 逐格遍历，
  命中 discard 规则保持选中、命中 keep 则反选，到达单批上限或遇到锁定物即停；
- **阶段二（执行）**：点击游戏内分解按钮 → 确认弹窗 → 关闭结果蒙层。

本模块只保留清理器**特有的差异**：

- :class:`DecomposePolicy`（规则判定 + 反选动作 + 单批上限 + 锁定物停止）；
- 「快速选择」弹窗流程与两阶段执行（自有砖，不塞进通用骨架）；
- 模板按钮点击（分解/确认/快速选择/进入分解页）。

冻结模块（``slot_detector`` / ``page_scroller`` / ``slider_scroller``）经
``sweep_adapters`` 的端口适配器原样接入；遍历与识别不再重复实现。
"""

from __future__ import annotations

import threading
import time
from typing import Any, ClassVar

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from backend.automation.dogfood_rule_engine import DogfoodRuleEngine
from backend.automation.sweep import BaseSweepPolicy, ListSweep, SweepObserver
from backend.automation.sweep_adapters import (
    DetectorSlotFinder,
    MousePointer,
    RecognizerArtifactReader,
    ScrollerNavigator,
    WindowScreenSource,
)
from backend.automation.template_manager import TemplateManager
from backend.automation.template_matcher import multi_scale_match
from backend.automation.window_helper import WindowHelper
from backend.contracts.sweep import SlotContext, SweepTiming
from backend.models.artifact import ArtifactInfo
from backend.models.slot_models import SALVAGE_SLOT_CONFIG
from backend.utils.logger import log

# 反选（取消选中）后等待列表响应
_DESELECT_DELAY_S = 0.2

# 单批选择上限（游戏内一次最多分解 1000 件）
_MAX_DISCARD_PER_BATCH = 1000

# 清理流程原先依赖旧的逐格遍历器的点击间隔来等待详情面板，现由遍历骨架的
# SweepTiming.click_delay_s 承担，这里不再额外等待
_DECOMPOSE_TIMING = SweepTiming(detail_settle_s=0.0)


class DecomposePolicy(BaseSweepPolicy):
    """清理策略：规则判定 + 反选动作 + 单批上限 + 遇锁定物停止"""

    def __init__(
        self,
        *,
        rules: list,
        default_action: str,
        max_per_batch: int,
        pointer: MousePointer,
    ) -> None:
        self._engine = DogfoodRuleEngine(default_action=default_action)
        self._rules = rules
        self._limit = min(max_per_batch, _MAX_DISCARD_PER_BATCH)
        self._pointer = pointer
        self._started = time.perf_counter()
        self._last_logged = 0.0

        self.keep = 0
        self.discard = 0
        self.reached_limit = False

    def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
        elapsed = time.perf_counter() - self._started

        if self._engine.evaluate(artifact, self._rules) == "discard":
            self.discard += 1
            self._log(ctx, "分解", artifact, elapsed)
            if self.discard >= self._limit:
                log.info(f"已达到单批上限 {self._limit} 件，暂停选择")
                self.reached_limit = True
                return False
        else:
            self.keep += 1
            self._log(ctx, "保留", artifact, elapsed)
            # 再次点击反选（取消选中）
            self._pointer.click(ctx.slot.cx, ctx.slot.cy)
            time.sleep(_DESELECT_DELAY_S)

        self._log_progress(elapsed)

        if ctx.slot.locked:
            log.info(
                f"[P{ctx.page + 1}-{ctx.index}/{ctx.total}] 检测到锁定圣遗物，"
                f"停止分解流程 (累计保留={self.keep} 分解={self.discard})"
            )
            self.reached_limit = True
            return False
        return True

    @staticmethod
    def _log(ctx: SlotContext, action: str, artifact: ArtifactInfo, elapsed: float) -> None:
        log.info(
            f"[P{ctx.page + 1}-{ctx.index}/{ctx.total}] → {action} "
            f"(套装={artifact.set_name or '?'} "
            f"部位={artifact.piece_type or '?'} "
            f"星级={artifact.rarity or '?'}) "
            f"| 累计耗时={elapsed:.1f}s"
        )

    def _log_progress(self, elapsed: float) -> None:
        """每 10 件或每 5 秒输出一次进度"""
        processed = self.keep + self.discard
        if processed % 10 and elapsed - self._last_logged <= 5.0:
            return
        self._last_logged = elapsed
        avg = elapsed / processed if processed else 0.0
        log.info(
            f"[进度] 已处理 {processed} 个 | 保留 {self.keep} 分解 {self.discard} "
            f"| 平均 {avg:.2f}s/个"
        )


class ArtifactDecomposer(QObject):
    """自动分解 4 星及以下圣遗物"""

    # 模板匹配阈值
    MATCH_THRESHOLD: ClassVar[float] = 0.80

    # 快速选择弹窗的 OCR 识别区域 (x, y, w, h)
    QUICK_SELECT_ROI: ClassVar[tuple[int, int, int, int]] = (23, 114, 639, 360)

    def __init__(self) -> None:
        super().__init__()
        self._stop_event = threading.Event()
        self._quick_select_pos: tuple[int, int] | None = None
        self._decompose_button_pos: tuple[int, int] | None = None

        # 端口按轮次创建（reset_stop 时重建），避免上一轮的缓存影响本轮
        self._screen: WindowScreenSource | None = None
        self._pointer: MousePointer | None = None
        self._slot_finder: DetectorSlotFinder | None = None

    def stop(self) -> None:
        """线程安全：设置停止标志，遍历在每个检查点退出"""
        self._stop_event.set()
        log.info("[ArtifactDecomposer] 停止标志已设置")

    def reset_stop(self) -> None:
        """清除停止标志与端口缓存，允许下次运行"""
        self._stop_event.clear()
        self._screen = None
        self._pointer = None
        self._slot_finder = None
        self._quick_select_pos = None
        self._decompose_button_pos = None

    def is_stopped(self) -> bool:
        """是否已收到停止请求（供 Presenter 判断"用户手动停止"）"""
        return self._stop_event.is_set()

    def _ports(self) -> tuple[WindowScreenSource, MousePointer, DetectorSlotFinder]:
        if self._screen is None:
            self._screen = WindowScreenSource(SALVAGE_SLOT_CONFIG)
            self._pointer = MousePointer()
            self._slot_finder = DetectorSlotFinder(SALVAGE_SLOT_CONFIG)
        assert self._pointer is not None and self._slot_finder is not None
        return self._screen, self._pointer, self._slot_finder

    # 阶段一：选择

    def select_artifacts(
        self,
        rules: list,
        default_action: str,
        max_per_batch: int = 1000,
        ocr: Any = None,
    ) -> tuple[int, int, bool]:
        """选择一批待分解圣遗物

        Returns:
            (keep_count, discard_count, reached_limit)
        """
        screen, pointer, slot_finder = self._ports()
        policy = DecomposePolicy(
            rules=rules,
            default_action=default_action,
            max_per_batch=max_per_batch,
            pointer=pointer,
        )
        sweep = ListSweep(
            screen=screen,
            pointer=pointer,
            slot_finder=slot_finder,
            reader=RecognizerArtifactReader(SALVAGE_SLOT_CONFIG, ocr),
            navigator=ScrollerNavigator(SALVAGE_SLOT_CONFIG),
            timing=_DECOMPOSE_TIMING,
        )
        summary = sweep.run(
            policy=policy,
            stop_check=self._stop_event.is_set,
            observer=SweepObserver(on_page_start=self._on_page_start),
        )
        log.info(
            f"选择阶段结束（{summary.stopped_reason}）: 保留 {policy.keep} 件, "
            f"分解 {policy.discard} 件, 达上限={policy.reached_limit}"
        )
        return (policy.keep, policy.discard, policy.reached_limit)

    @staticmethod
    def _on_page_start(page: int, slots_total: int) -> None:
        log.info(f"--- 第 {page + 1} 页（检测到 {slots_total} 个格子）---")

    # 阶段二：执行

    def execute_decompose(self) -> bool:
        """点击游戏内分解按钮并确认弹窗，完成分解"""
        screen, _pointer, _finder = self._ports()

        time.sleep(0.5)
        image = screen.capture()
        if image is None:
            log.error("截图失败，无法执行分解")
            return False

        if not self._click_decompose_button(image):
            log.error("未找到分解按钮")
            return False
        log.info("已点击分解按钮")

        # 等待确认弹窗出现（0.2~0.4 秒）
        time.sleep(0.3)
        confirm_image = screen.capture()
        if confirm_image is None or self._click_template(
            confirm_image, "分解页面确认分解按钮"
        ) is None:
            log.error("未找到确认分解按钮，确认弹窗可能未出现")
            return False
        log.info("已确认分解")

        # 等待分解完成弹窗，再次点击关闭蒙层
        time.sleep(0.2)
        self._dismiss_result_overlay()
        log.info("已关闭分解结果蒙层")
        return True

    # 进入分解页面

    def enter_decompose_page(self) -> bool:
        """确保当前在分解页面；不在则尝试点击分解按钮进入"""
        log.info("进入分解页面...")
        screen, _pointer, _finder = self._ports()
        screen.prepare()

        image = screen.capture()
        if image is None:
            log.error("截图失败，无法进入分解页面")
            return False
        if self._is_on_decompose_page(image):
            log.info("已在分解页面")
            return True

        log.info("未在分解页面，尝试查找分解按钮")
        if self._click_template(image, "背包页面分解按钮") is None:
            log.error("未找到分解按钮")
            return False

        time.sleep(1.5)
        after = screen.capture()
        if after is None or not self._is_on_decompose_page(after):
            log.error("点击分解按钮后未能进入分解页面")
            return False

        log.info("已进入分解页面")
        return True

    # 快速选择（清理器自有砖）

    def try_quick_select_decompose(self, ocr) -> bool:
        """尝试用游戏内「快速选择」一键选中 4 星及以下并分解

        Returns:
            True 已执行快速分解；False 无 4 星及以下圣遗物（需走规则选择流程）
        """
        log.info("尝试快速选择4星及以下圣遗物...")
        screen, _pointer, _finder = self._ports()

        # 1. 点击快速选择按钮
        time.sleep(0.5)
        image = screen.capture()
        if image is None:
            log.warning("截图失败，跳过快速选择")
            return False
        self._quick_select_pos = self._click_template(image, "快速选择按钮")
        if self._quick_select_pos is None:
            log.warning("未找到快速选择按钮，跳过快速选择")
            return False

        # 2. 截图并 OCR 识别快速选择弹窗内容
        time.sleep(0.5)
        popup = screen.capture()
        if popup is None:
            log.warning("弹窗截图失败，跳过快速选择")
            self._close_quick_select_popup()
            return False

        rx, ry, rw, rh = self.QUICK_SELECT_ROI
        ocr_result = ocr.ocr(popup[ry : ry + rh, rx : rx + rw])
        if ocr_result is None:
            log.warning("快速选择 OCR 识别失败，跳过快速选择")
            self._close_quick_select_popup()
            return False
        log.info(f"快速选择 OCR 识别完成: {len(ocr_result)} 个区域")

        options = self._parse_quick_select_result(ocr_result, roi_offset=(rx, ry))
        for opt in options:
            log.debug(
                f"  {opt['star']}星圣遗物 ×{opt['count']} "
                f"位置(窗口相对)=({opt['pos'][0]}, {opt['pos'][1]})"
            )

        low_star = [opt for opt in options if opt["star"] <= 4 and opt["count"] > 0]
        if not low_star:
            log.info("无4星及以下圣遗物，关闭快速选择弹窗，进入主流程")
            self._close_quick_select_popup()
            return False

        log.info(f"发现4星及以下圣遗物: {[f'{o["star"]}星×{o["count"]}' for o in low_star]}")

        # 3. 关闭弹窗 → 点分解 → 确认 → 关蒙层
        self._close_quick_select_popup()
        time.sleep(0.5)
        confirm_base = screen.capture()
        if confirm_base is None or not self._click_decompose_button(confirm_base):
            log.error("未找到分解按钮")
            return False

        time.sleep(0.3)
        confirm_image = screen.capture()
        if confirm_image is None or self._click_template(
            confirm_image, "分解页面确认分解按钮"
        ) is None:
            log.error("未找到确认分解按钮，确认弹窗可能未出现")
            return False
        log.info("已确认快速选择分解")

        time.sleep(0.2)
        self._dismiss_result_overlay()
        log.info("已关闭快速选择分解结果蒙层")
        return True

    def _close_quick_select_popup(self) -> None:
        if self._quick_select_pos is None:
            log.warning("快速选择按钮坐标丢失，无法关闭弹窗")
            return
        _screen, pointer, _finder = self._ports()
        pointer.click(*self._quick_select_pos)
        time.sleep(0.3)
        log.info("已关闭快速选择弹窗")

    # 模板按钮点击

    def _is_on_decompose_page(self, image: np.ndarray) -> bool:
        """判断当前是否在分解页面（标题优先，分解按钮兜底）"""
        text_template = TemplateManager.get("圣遗物分解文本")
        if text_template is not None and self._matches(image, text_template):
            return True

        button_template = TemplateManager.get("圣遗物分解页面分解按钮")
        if button_template is not None:
            score, _, _, _ = multi_scale_match(image, button_template)
            if score >= self.MATCH_THRESHOLD:
                log.info("圣遗物分解文本未匹配，但检测到分解页面按钮，判定为在分解页面")
                return True
        return False

    def _matches(self, image: np.ndarray, template: object) -> bool:
        score, _, _, _ = multi_scale_match(image, template)
        return score >= self.MATCH_THRESHOLD

    def _click_decompose_button(self, image: np.ndarray) -> bool:
        """点击分解页面上的分解按钮，并缓存坐标供关闭蒙层复用"""
        pos = self._click_template(image, "圣遗物分解页面分解按钮")
        if pos is None:
            return False
        self._decompose_button_pos = pos
        return True

    def _dismiss_result_overlay(self) -> None:
        """点击分解按钮位置关闭结果蒙层（无蒙层时点击无效，是安全的）"""
        if self._decompose_button_pos is None:
            log.warning("分解按钮坐标丢失，无法关闭蒙层")
            return
        _screen, pointer, _finder = self._ports()
        time.sleep(0.2)
        pointer.click(*self._decompose_button_pos)
        time.sleep(0.2)

    def _click_template(self, image: np.ndarray, key: str) -> tuple[int, int] | None:
        """模板匹配按钮并点击，返回窗口相对坐标（失败返回 None）"""
        template = TemplateManager.get(key)
        if template is None:
            log.error(f"未找到模板: {key}")
            return None

        score, (rel_x, rel_y), scale, _size = multi_scale_match(image, template)
        if score < self.MATCH_THRESHOLD:
            log.warning(f"[{key}] 匹配失败: 得分={score:.3f} < 阈值={self.MATCH_THRESHOLD}")
            return None

        abs_x, abs_y = WindowHelper.to_absolute(rel_x, rel_y)
        log.info(
            f"[{key}] 匹配成功: 得分={score:.3f} 缩放={scale:.2f} "
            f"窗口相对=({rel_x}, {rel_y}) 窗口原点={WindowHelper.get_origin()} "
            f"屏幕绝对=({abs_x}, {abs_y})"
        )
        _screen, pointer, _finder = self._ports()
        pointer.click(rel_x, rel_y)
        return (rel_x, rel_y)

    # 快速选择结果解析（纯函数）

    @staticmethod
    def _parse_quick_select_result(
        ocr_result: list,
        roi_offset: tuple[int, int] = (0, 0),
    ) -> list[dict]:
        """解析快速选择弹窗 OCR 结果，返回结构化选项列表

        OCR 识别到的文本按「星级标签 → 数量」交替排列，如：
        ``"1星圣遗物"`` → ``"1"`` → ``"2星圣遗物"`` → ``"4"`` → …

        Returns:
            ``[{"star": 1, "label": "1星圣遗物", "count": 4, "pos": (x, y)}, ...]``
        """
        import re

        lines: list[dict] = []
        if ocr_result is None or len(ocr_result) == 0:
            return []

        page = ocr_result[0]
        if page is None:
            return []
        # 避免 numpy 数组直接做布尔判断
        if hasattr(page, "__len__") and len(page) == 0:
            return []

        if isinstance(page, dict):
            for text, poly in zip(page.get("rec_texts", []), page.get("dt_polys", [])):
                if not text or not text.strip():
                    continue
                cx = sum(p[0] for p in poly) / len(poly) if poly is not None and len(poly) else 0
                cy = sum(p[1] for p in poly) / len(poly) if poly is not None and len(poly) else 0
                lines.append({"text": text.strip(), "cx": cx, "cy": cy})
        elif isinstance(page, list):
            for line_info in page:
                if not isinstance(line_info, (list, tuple)) or len(line_info) < 2:
                    continue
                poly, rec = line_info[0], line_info[1]
                text = rec[0] if isinstance(rec, (list, tuple)) else str(rec)
                if not text or not text.strip():
                    continue
                if poly is not None and len(poly) > 0:
                    cx = sum(p[0] for p in poly) / len(poly)
                    cy = sum(p[1] for p in poly) / len(poly)
                else:
                    cx, cy = 0, 0
                lines.append({"text": text.strip(), "cx": cx, "cy": cy})

        lines.sort(key=lambda item: item["cy"])

        rx, ry = roi_offset
        options: list[dict] = []
        i = 0
        while i < len(lines) - 1:
            label_line, count_line = lines[i], lines[i + 1]
            if "星圣遗物" in label_line["text"]:
                star_m = re.search(r"(\d+)\s*星", label_line["text"])
                # 兼容 1000 / 1,000 / 1, 000 / 1.000 等格式
                count_clean = re.sub(r"[^\d]", "", count_line["text"])
                count = int(count_clean) if count_clean else None
                if star_m and count is not None:
                    options.append(
                        {
                            "star": int(star_m.group(1)),
                            "label": label_line["text"],
                            "count": count,
                            "pos": (int(rx + label_line["cx"]), int(ry + label_line["cy"])),
                        }
                    )
            i += 1
        return options


class SelectWorker(QThread):
    """后台线程：圣遗物分解 — 选择阶段（进入页面 + 快速选择 + 规则评估）

    结果信号命名为 ``selectCompleted``，不覆盖 ``QThread.finished``。
    """

    stepChanged = Signal(str)
    selectCompleted = Signal(int, int, bool)
    errorOccurred = Signal(str)

    def __init__(
        self,
        decomposer: ArtifactDecomposer,
        rules: list,
        default_action: str,
        max_discard: int,
        engines_dir=None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._decomposer = decomposer
        self._rules = rules
        self._default_action = default_action
        self._max_discard = max_discard
        self._engines_dir = engines_dir

    def stop(self) -> None:
        self._decomposer.stop()

    def run(self) -> None:
        try:
            from backend.automation.ocr_engine import OcrEngine
            from backend.exceptions.automation import OcrModelNotReadyError

            self.stepChanged.emit("正在初始化 OCR 引擎...")
            ocr = OcrEngine.create_ocr(self._engines_dir)

            self.stepChanged.emit("正在进入分解页面...")
            if not self._decomposer.enter_decompose_page():
                self.errorOccurred.emit("进入分解页面失败")
                return

            self.stepChanged.emit("正在快速选择4星及以下圣遗物...")
            self._decomposer.try_quick_select_decompose(ocr)

            self.stepChanged.emit("正在选择圣遗物...")
            keep, discard, reached_limit = self._decomposer.select_artifacts(
                self._rules, self._default_action, self._max_discard, ocr
            )
            self.selectCompleted.emit(keep, discard, reached_limit)

        except OcrModelNotReadyError:
            self.errorOccurred.emit(OcrModelNotReadyError._MESSAGE)
        except Exception as exc:
            import traceback

            tb = traceback.format_exc()
            log.error(f"选择阶段发生未知错误:\n{tb}")
            self.errorOccurred.emit(f"{exc}\n{tb}")


class ExecuteWorker(QThread):
    """后台线程：圣遗物分解 — 执行阶段（点击确认分解按钮）

    结果信号命名为 ``executeCompleted``，不覆盖 ``QThread.finished``。
    """

    stepChanged = Signal(str)
    executeCompleted = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(
        self,
        decomposer: ArtifactDecomposer,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._decomposer = decomposer

    def stop(self) -> None:
        self._decomposer.stop()

    def run(self) -> None:
        from backend.exceptions.automation import OcrModelNotReadyError

        try:
            self.stepChanged.emit("正在执行分解...")
            self.executeCompleted.emit(self._decomposer.execute_decompose())
        except OcrModelNotReadyError:
            self.errorOccurred.emit(OcrModelNotReadyError._MESSAGE)
        except Exception as exc:
            import traceback

            tb = traceback.format_exc()
            log.error(f"执行阶段发生未知错误:\n{tb}")
            self.errorOccurred.emit(f"{exc}\n{tb}")
