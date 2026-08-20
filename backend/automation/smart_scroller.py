"""
SmartScroller — 基于 SlotDetector.bottom_y 校准的精准翻页器
=============================================================
通过 SlotDetector.detect() 返回的 bottom_y 计算 pixels_per_scroll，
不受滑块大小影响，比像素标尺匹配更可靠。

核心逻辑：
  1. calibrate()     → detect() 两次 bottom_y 差值 → pixels_per_scroll
  2. scroll_rows(n)  → 总像素 = n × row_height → ticks → 连续 scroll
  3. wait_until_settled() → 监测画面哈希，连续 3 帧稳定即结束
  4. scroll_to_top() → 持续上滚直到画面不再变化
"""

from __future__ import annotations

import hashlib
from time import perf_counter, sleep

import numpy as np
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slider_scroller import SliderScroller
from backend.automation.slot_detector import (
    BAG_SLOT_CONFIG,
    SlotDetector,
    SlotDetectorConfig,
)
from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture


class SmartScroller:
    """基于 SlotDetector.bottom_y 校准的精准翻页器。

    使用示例:
        scroller = SmartScroller(capture, mouse, win)
        scroller.calibrate()          # 校准 pixels_per_scroll
        scroller.scroll_rows(100)     # 翻 100 行
        scroller.scroll_to_top()      # 回到顶部
    """

    _DEFAULT_ROW_HEIGHT = 96  # 兜底默认值

    def __init__(
        self,
        capture: ScreenshotCapture,
        mouse: MouseController,
        win: WindowHelper,
        *,
        slider: SliderScroller | None = None,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
        row_height: int | None = None,
    ) -> None:
        """
        Args:
            capture: 截图工具
            mouse: 鼠标控制器
            win: 窗口助手
            slider: 滑块滚动器，用于 ensure_at_top
            config: SlotDetector 配置（用于 calibrate 和计算 row_height）
            row_height: 每行高度，None 则自动从 config 计算
        """
        self._capture = capture
        self._mouse = mouse
        self._win = win
        self._slider = slider
        self._config = config
        self._row_height = row_height or self._calc_row_height()

        self._pixels_per_scroll: float = 0.0
        self._current_row: int = 0
        self._calibrated = False

    def _calc_row_height(self) -> int:
        """通过 SlotDetector.detect() 自动计算行高"""
        result = self._capture.capture()
        if result is None:
            return self._DEFAULT_ROW_HEIGHT
        det = SlotDetector.detect(result.image, config=self._config)
        return det.row_height if det.row_height > 0 else self._DEFAULT_ROW_HEIGHT

    # ==================================================================
    # 属性
    # ==================================================================

    @property
    def pixels_per_scroll(self) -> float:
        return self._pixels_per_scroll

    @property
    def current_row(self) -> int:
        return self._current_row

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    # ==================================================================
    # 校准（基于 SlotDetector.bottom_y）
    # ==================================================================

    def calibrate(self) -> float:
        """执行一次滚动，通过 SlotDetector 的 bottom_y 计算 pixels_per_scroll。

        pixels_per_scroll = bottom_y₁ - bottom_y₂
        （滚动后内容上移，bottom_y 变小，差值为正）

        Raises:
            RuntimeError: 校准失败
        """
        ox, oy = self._win.get_origin()
        if ox == 0 and oy == 0:
            raise RuntimeError("校准失败: 未检测到原神窗口")

        self._win.focus()
        roi = self._config.roi
        if roi is None:
            raise RuntimeError("校准失败: ROI 未配置")

        # 截图1
        result1 = self._capture.capture()
        if result1 is None:
            raise RuntimeError("校准失败: 截图1失败")
        det1 = SlotDetector.detect(result1.image, config=self._config)
        if not det1.slots:
            raise RuntimeError("校准失败: 未检测到格子")
        bottom_y1 = det1.bottom_y

        # 滚动 1 tick
        rx, ry, rw, rh = roi
        self._mouse.move_to(ox + rx + rw // 2, oy + ry + rh // 2)
        self._mouse.scroll_one_tick()
        sleep(0.15)

        # 截图2
        result2 = self._capture.capture()
        if result2 is None:
            raise RuntimeError("校准失败: 截图2失败")
        det2 = SlotDetector.detect(result2.image, config=self._config)
        if not det2.slots:
            raise RuntimeError("校准失败: 滚动后未检测到格子")
        bottom_y2 = det2.bottom_y

        offset = bottom_y1 - bottom_y2
        if offset <= 0:
            raise RuntimeError(f"校准失败: 无效偏移 (bottom_y {bottom_y1}→{bottom_y2})")

        self._pixels_per_scroll = float(offset)
        self._calibrated = True
        log.info(
            f"SmartScroller 校准完成: {self._pixels_per_scroll:.2f} px/tick "
            f"(bottom_y {bottom_y1}→{bottom_y2})"
        )
        return self._pixels_per_scroll

    # ==================================================================
    # 滚动到顶部
    # ==================================================================

    def scroll_to_top(self, force: bool = False) -> bool:
        """通过滑块拖拽滚动到顶部。

        Args:
            force: 强制拖拽到顶，跳过距离检测
        """
        if self._slider is None:
            log.warning("SmartScroller: 未注入 SliderScroller, 无法到顶")
            return False
        self._win.focus()
        result = self._slider.ensure_at_top(force=force)
        if result is not None:
            self._current_row = 0
            return True
        return False

    # ==================================================================
    # 翻行
    # ==================================================================

    def scroll_rows(self, rows: int, tick_interval_ms: int = 15) -> None:
        """翻指定行数。

        total_px = rows × row_height → ticks = ceil(total_px / pixels_per_scroll)
        """
        if not self._calibrated:
            self.calibrate()

        if rows <= 0:
            return

        ox, oy = self._win.get_origin()
        if ox == 0 and oy == 0:
            return

        total_px = rows * self._row_height
        ticks = max(1, int(np.ceil(total_px / self._pixels_per_scroll)))

        self._win.focus()
        roi = self._config.roi
        if roi is None:
            return
        rx, ry, rw, rh = roi
        self._mouse.move_to(ox + rx + rw // 2, oy + ry + rh // 2)

        log.info(f"SmartScroller: 翻 {rows} 行 → {total_px}px → {ticks} ticks")

        for _ in range(ticks):
            self._mouse.scroll_one_tick()
            sleep(tick_interval_ms / 1000.0)

        self._current_row += rows
        self._wait_until_settled()

    # ==================================================================
    # 稳定检测
    # ==================================================================

    def _wait_until_settled(
        self, timeout_ms: int = 500, stable_frames: int = 3
    ) -> bool:
        """监测画面哈希，连续 N 帧稳定即认为翻页动画结束。"""
        ox, oy = self._win.get_origin()
        if ox == 0 and oy == 0:
            return False

        if self._config.roi:
            sx, sy, sw, sh = self._config.roi
        else:
            return False

        deadline = perf_counter() + timeout_ms / 1000.0
        stable_count = 0
        last_hash = ""

        while perf_counter() < deadline:
            result = self._capture.capture()
            if result is None:
                sleep(0.03)
                continue

            region = result.image[oy + sy : oy + sy + sh, ox + sx : ox + sx + sw]
            current_hash = hashlib.md5(region.tobytes()).hexdigest()

            if current_hash == last_hash:
                stable_count += 1
                if stable_count >= stable_frames:
                    return True
            else:
                stable_count = 0
                last_hash = current_hash

            sleep(0.03)

        return False

    # ==================================================================
    # 重置
    # ==================================================================

    def reset(self) -> None:
        self._current_row = 0