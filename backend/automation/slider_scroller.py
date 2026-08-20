"""
滑块滚动验证器 — 纯逻辑层，无 Qt 依赖
===================================
封装滑块"闯关验证"循环：滑块检测 → 拖拽 → 再检测 → 判定到底/到顶。
使用回调模式解耦调试预览，可在任意线程中安全调用。
"""

from __future__ import annotations

from collections.abc import Callable
from time import sleep

import numpy as np
from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slider_detector import SliderDetector
from backend.automation.slot_detector import SlotDetectorConfig
from backend.utils.screen_capture import ScreenshotCapture


class SliderScroller:
    """滑块滚动验证器 — 纯逻辑，无 Qt 依赖

    通过 debug_callback 回调注入调试预览生成，解耦 UI 层。
    """

    def __init__(
        self,
        mouse: MouseController,
        capture: ScreenshotCapture,
        window_helper,
        config: SlotDetectorConfig,
        debug_callback: Callable[..., None] | None = None,
    ):
        self._mouse = mouse
        self._capture = capture
        self._win = window_helper
        self._config = config
        self._debug_cb = debug_callback or (lambda *a, **kw: None)

    def _emit_debug(
        self,
        img: np.ndarray,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int,
        region_h: int,
        slider_y: int | None,
        label: str = "",
        best_ratio: float = 0.0,
        best_y: int = -1,
    ) -> None:
        self._debug_cb(
            img, region_x, top_y, bottom_y,
            region_w, region_h, slider_y, label, best_ratio, best_y,
        )

    # ==================================================================
    # 确保滑块在顶部
    # ==================================================================

    def ensure_at_top(self, force: bool = False) -> int | None:
        """检测滑块位置，不在顶部则闯关拖拽到顶。

        Args:
            force: 强制拖拽到顶（跳过距离检测），用于校准后位置偏差极小的情况

        Returns:
            slider_y 或 None
        """
        sr = self._config.slider_region()
        if sr is None:
            log.warning("确保到顶: 无效的滑轨区域配置")
            return None
        region_x, top_y, bottom_y, region_w, region_h = sr

        result = self._capture.capture()
        if result is None:
            log.warning("确保到顶: 截图失败")
            return None

        slider_y, best_ratio, best_y, _ = SliderDetector.find_slider(
            result.image, region_x, top_y, bottom_y, region_w, region_h
        )
        self._emit_debug(
            result.image, region_x, top_y, bottom_y,
            region_w, region_h, slider_y, "初始检测", best_ratio, best_y,
        )

        if slider_y is None:
            log.warning("确保到顶: 未检测到滑块")
            return None

        distance_from_top = slider_y - top_y
        if force or distance_from_top > SliderDetector.PROXIMITY:
            if force:
                log.info("确保到顶: 强制拖拽到顶 (force=True)")
            else:
                log.info(
                    f"确保到顶: 滑块距顶部{distance_from_top}px, 开始闯关拖拽到顶..."
                )
            slider_y = self.verify_top(slider_y)

        log.info(f"确保到顶: 已确认在顶部 (slider_y={slider_y})")
        return slider_y

    # ==================================================================
    # 颜色检测是否到底
    # ==================================================================

    def check_bottom_by_color(self) -> tuple[int | None, bool]:
        """颜色检测是否到底。

        Returns:
            (slider_y, is_at_bottom)
        """
        sr = self._config.slider_region()
        if sr is None:
            log.warning("颜色检测: 无效的滑轨区域配置")
            return (None, False)
        region_x, _top_y, region_y, region_w, region_h = sr

        result = self._capture.capture()
        if result is None:
            log.warning("颜色检测: 截图失败")
            return (None, False)

        img = result.image
        top_y = max(0, region_y - SliderDetector.MAX_SEARCH)
        slider_y, best_ratio, best_y, _ = SliderDetector.find_slider(
            img, region_x, top_y, region_y, region_w, region_h,
        )
        self._emit_debug(
            img, region_x, top_y, region_y, region_w, region_h,
            slider_y, "颜色检测", best_ratio, best_y,
        )

        if slider_y is None:
            log.warning("颜色检测: 未找到滑块颜色")
            return (None, False)

        distance_from_bottom = region_y - slider_y
        if distance_from_bottom <= SliderDetector.PROXIMITY:
            log.info(
                f"颜色检测: 滑块接近底部 y={slider_y}, "
                f"距起始={distance_from_bottom}px, 开始闯关验证..."
            )
            confirmed_y = self.verify_bottom(slider_y)
            if confirmed_y is None:
                log.warning("颜色检测: 闯关验证超时，未确认到底")
                return (None, False)

            log.info("颜色检测: 闯关验证通过 (滑块已停止), 判定: 已到底 ✓")
            return (confirmed_y, True)

        log.info(
            f"颜色检测: 滑块位于 y={slider_y}, "
            f"距起始={distance_from_bottom}px, 判定: 未到底 ✗"
        )
        return (slider_y, False)

    # ==================================================================
    # 闯关验证：到底
    # ==================================================================

    def verify_bottom(self, initial_slider_y: int) -> int | None:
        """闯关验证到底。

        反复拖拽到底，直到滑块不再移动。

        Returns:
            最终 slider_y 或 None
        """
        sr = self._config.slider_region()
        if sr is None:
            log.warning("验证到底: 无效的滑轨区域配置")
            return None
        region_x, _top_y, region_y, region_w, region_h = sr

        prev_y = initial_slider_y
        self._win.focus()
        ox, oy = self._win.get_origin()
        drag_x = ox + region_x + region_w // 2

        window = self._capture.find_genshin_window()
        window_bottom = (oy + window.height) if window else (oy + 1000)
        top_y = max(0, region_y - SliderDetector.MAX_SEARCH)

        log.info(f"到底验证: 开始, 初始滑块Y={prev_y}, 拖拽列X={drag_x}")

        for attempt in range(SliderDetector.VERIFY_MAX):
            drag_from_y = oy + prev_y + region_h // 2
            drag_to_y = min(
                drag_from_y + SliderDetector.DRAG_DIST, window_bottom - 10
            )
            self._mouse.drag(
                drag_x, drag_from_y, drag_x, drag_to_y,
                SliderDetector.DRAG_STEPS, SliderDetector.DRAG_DELAY,
            )
            sleep(0.15)

            result = self._capture.capture()
            if result is None:
                continue

            current_y, best_ratio, best_y, _ = SliderDetector.find_slider(
                result.image, region_x, top_y, region_y, region_w, region_h,
            )
            self._emit_debug(
                result.image, region_x, top_y, region_y,
                region_w, region_h, current_y,
                f"到底-{attempt + 1}", best_ratio, best_y,
            )

            if current_y is None:
                if SliderDetector.check_track_color(
                    result.image, region_x, region_y, region_w, region_h
                ):
                    log.info(
                        f"到底验证: 第{attempt + 1}次 检测到滑轨颜色, 确认到底"
                    )
                    return prev_y
                continue

            if abs(current_y - prev_y) <= 5:
                log.info(
                    f"到底验证: 第{attempt + 1}次 滑块未移动 "
                    f"(prev={prev_y}, cur={current_y}), 确认到底"
                )
                return current_y

            log.info(
                f"到底验证: 第{attempt + 1}次 滑块移动 "
                f"(prev={prev_y} → cur={current_y}), 继续..."
            )
            prev_y = current_y

        return None

    # ==================================================================
    # 闯关验证：到顶
    # ==================================================================

    def verify_top(self, initial_slider_y: int) -> int | None:
        """闯关验证到顶。

        反复拖拽到顶，直到滑块不再移动。

        Returns:
            最终 slider_y 或 None
        """
        sr = self._config.slider_region()
        if sr is None:
            log.warning("验证到顶: 无效的滑轨区域配置")
            return None
        region_x, top_y, bottom_y, region_w, region_h = sr

        prev_y = initial_slider_y
        self._win.focus()
        ox, oy = self._win.get_origin()
        drag_x = ox + region_x + region_w // 2

        log.info(f"到顶验证: 开始, 初始滑块Y={prev_y}, 拖拽列X={drag_x}")

        for attempt in range(SliderDetector.VERIFY_MAX):
            drag_from_y = oy + prev_y + region_h // 2
            drag_to_y = max(
                drag_from_y - SliderDetector.DRAG_DIST, oy + 10
            )
            self._mouse.drag(
                drag_x, drag_from_y, drag_x, drag_to_y,
                SliderDetector.DRAG_STEPS, SliderDetector.DRAG_DELAY,
            )
            sleep(0.15)

            result = self._capture.capture()
            if result is None:
                continue

            current_y, best_ratio, best_y, _ = SliderDetector.find_slider(
                result.image, region_x, top_y, bottom_y, region_w, region_h
            )
            self._emit_debug(
                result.image, region_x, top_y, bottom_y,
                region_w, region_h, current_y, f"到顶-{attempt + 1}",
                best_ratio, best_y,
            )

            if current_y is None:
                log.info(
                    f"到顶验证: 第{attempt + 1}次 未找到滑块（可能在顶部边缘），确认到顶"
                )
                break

            if current_y - top_y <= SliderDetector.PROXIMITY:
                log.info(
                    f"到顶验证: 第{attempt + 1}次 滑块已接近顶部 "
                    f"(y={current_y}, 距顶={current_y - top_y}px), 确认到顶"
                )
                prev_y = current_y
                break

            if abs(current_y - prev_y) <= 5:
                log.info(
                    f"到顶验证: 第{attempt + 1}次 滑块未移动 "
                    f"(prev={prev_y}, cur={current_y}), 确认到顶"
                )
                prev_y = current_y
                break

            log.info(
                f"到顶验证: 第{attempt + 1}次 滑块移动 "
                f"(prev={prev_y} → cur={current_y}), 继续..."
            )
            prev_y = current_y

        # 追加拖拽确保100%到顶
        log.info(f"到顶验证: 追加{SliderDetector.EXTRA_TICKS}次拖拽确保100%到顶")
        for _ in range(SliderDetector.EXTRA_TICKS):
            drag_from_y = oy + prev_y + region_h // 2
            drag_to_y = max(
                drag_from_y - SliderDetector.DRAG_DIST // 2, oy + 10
            )
            self._mouse.drag(
                drag_x, drag_from_y, drag_x, drag_to_y,
                SliderDetector.DRAG_STEPS // 2, SliderDetector.DRAG_DELAY,
            )
            sleep(0.05)

        log.info("到顶验证: 完成")
        return prev_y