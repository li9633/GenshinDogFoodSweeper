from __future__ import annotations

from time import sleep

from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slot_detector import (
    BAG_SLOT_CONFIG,
    SlotDetector,
    SlotDetectorConfig,
)
from backend.automation.window_helper import WindowHelper, WindowInfo
from backend.models.slot_models import DetectResult
from backend.utils.screen_capture import ScreenshotCapture


class PageScroller:
    """基于格子检测的精准翻页器。

    解耦设计：
    - SlotDetector 负责格子识别
    - PageScroller 负责计算滚动距离 + 执行滚动
    - 两者通过返回值传递数据，不直接耦合
    """

    # 1 行 = 格子153px + 间距24px = 177px, 10 格/行 → 17.7px/格
    _PX_PER_TICK = 17.7

    def __init__(
        self,
        mouse: MouseController,
        capture: ScreenshotCapture,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
        window: WindowInfo | None = None,
    ) -> None:
        self._mouse = mouse
        self._capture = capture
        self._config = config
        self._window = window

    def set_config(self, config: SlotDetectorConfig) -> None:
        """运行时切换格子检测配置（调试面板切换页面时使用）。"""
        self._config = config

    # ==================================================================
    # 翻页
    # ==================================================================

    def scroll_to_next_page(
        self,
        det_result: DetectResult,
        tick_delay_ms: int = 80,
        page_settle_ms: int = 200,
        fast: bool = False,
    ) -> bool:
        """根据格子检测结果计算滚动距离 → 执行滚动。

        调用前需外部完成截图和格子检测，传入 DetectResult。
        鼠标位置取自第一个检测格子的中心。
        返回 True 表示已翻页，False 表示已是最后一页即无需翻页。

        fast=True 时一次发送所有滚轮 tick，跳过逐 tick 延迟，
        适合快速跳转多页场景。
        """
        if not det_result.slots:
            return False

        bottom_y = det_result.bottom_y
        roi_top = self._config.roi[1]
        scroll_px = bottom_y - roi_top

        if scroll_px <= 0:
            return False

        ticks = max(1, int(scroll_px / self._PX_PER_TICK))
        flag_x = det_result.slots[0].cx
        flag_y = det_result.slots[0].cy

        if fast:
            self._mouse.move_to(flag_x, flag_y)
            self._mouse.scroll(-ticks)
        else:
            for _ in range(ticks):
                self._mouse.move_to(flag_x, flag_y)
                self._mouse.scroll_one_tick()
                sleep(tick_delay_ms / 1000.0)

        sleep(page_settle_ms / 1000.0)
        return True

    # ==================================================================
    # 循环翻到底
    # ==================================================================

    def scroll_to_bottom(
        self,
        tick_delay_ms: int = 80,
        page_settle_ms: int = 200,
        max_pages: int = 0,
        total_pages: int = 0,
    ) -> int:
        """循环截图+检测+翻页直到到底。

        max_pages=0 表示无限制，由 scroll_to_next_page 返回 False 自然停止。
        安全上限应由调用方根据 OCR 计算的总页数传入。
        total_pages 仅用于日志显示，不影响翻页逻辑。

        Returns:
            翻页次数
        """
        pages = 0
        while max_pages == 0 or pages < max_pages:
            window = self._window or WindowHelper.find_genshin_window()
            result = self._capture.capture(window=window)
            if result is None:
                break
            det_result = SlotDetector.detect(result.image, config=self._config)
            if not self.scroll_to_next_page(
                det_result,
                tick_delay_ms=tick_delay_ms,
                page_settle_ms=page_settle_ms,
            ):
                break
            pages += 1
            if total_pages > 0:
                log.info(f"翻页中... 当前第{pages + 1}页，共{total_pages}页")
            else:
                log.info(f"翻页中... 当前第{pages + 1}页")
        return pages

    # ==================================================================
    # 格子信息（调试用）
    # ==================================================================

    def get_grid_info(self) -> tuple[list, int] | None:
        """截图 → 检测格子 → 返回 (slots, bottom_y)。

        用于调试面板的预览显示。
        """
        window = self._window or WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)
        if result is None:
            return None
        det_result = SlotDetector.detect(result.image, config=self._config)
        if not det_result.slots:
            return None
        return det_result.slots, det_result.bottom_y