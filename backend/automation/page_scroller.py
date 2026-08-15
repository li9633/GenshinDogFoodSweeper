from __future__ import annotations

from time import sleep

from utils.logger import log

from backend.automation.mouse_controller import MouseController
from backend.automation.slot_detector import SlotDetector
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

    # 圣遗物列表 ROI 区域
    _ROI = (118, 193, 1170, 810)

    def __init__(
        self,
        mouse: MouseController,
        capture: ScreenshotCapture,
    ) -> None:
        self._mouse = mouse
        self._capture = capture

    # ==================================================================
    # 翻页
    # ==================================================================

    def scroll_to_next_page(
        self,
        ox: int,
        oy: int,
        flag_x: int,
        flag_y: int,
        tick_delay_ms: int = 80,
        page_settle_ms: int = 200,
    ) -> bool:
        """截图 → 检测格子 → 计算滚动距离 → 执行滚动。

        返回 True 表示已翻页，False 表示已是最后一页即无需翻页。
        """
        result = self._capture.capture()
        if result is None:
            return False

        slots = SlotDetector.detect(result.image, roi=self._ROI)
        if not slots:
            return False

        bottom_y = max(s[3] + s[5] for s in slots)
        roi_top = self._ROI[1]
        scroll_px = bottom_y - roi_top

        if scroll_px <= 0:
            return False

        ticks = max(1, int(scroll_px / self._PX_PER_TICK))

        for _ in range(ticks):
            self._mouse.move_to(ox + flag_x, oy + flag_y)
            self._mouse.scroll_one_tick()
            sleep(tick_delay_ms / 1000.0)

        sleep(page_settle_ms / 1000.0)
        return True

    # ==================================================================
    # 循环翻到底
    # ==================================================================

    def scroll_to_bottom(
        self,
        ox: int,
        oy: int,
        flag_x: int,
        flag_y: int,
        tick_delay_ms: int = 80,
        page_settle_ms: int = 200,
        max_pages: int = 0,
        total_pages: int = 0,
    ) -> int:
        """循环调用 scroll_to_next_page 直到到底。

        max_pages=0 表示无限制，由 scroll_to_next_page 返回 False 自然停止。
        安全上限应由调用方根据 OCR 计算的总页数传入。
        total_pages 仅用于日志显示，不影响翻页逻辑。

        Returns:
            翻页次数
        """
        pages = 0
        while max_pages == 0 or pages < max_pages:
            if not self.scroll_to_next_page(
                ox,
                oy,
                flag_x,
                flag_y,
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
        result = self._capture.capture()
        if result is None:
            return None
        slots = SlotDetector.detect(result.image, roi=self._ROI)
        if not slots:
            return None
        bottom_y = max(s[3] + s[5] for s in slots)
        return slots, bottom_y