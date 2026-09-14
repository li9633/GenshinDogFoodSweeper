"""端口适配器：把底层原语接到遍历契约上
========================================
- 冻结模块（``slot_detector`` / ``page_scroller`` / ``slider_scroller``）**只调用不改**；
- 三个功能共用这里的适配器，于是「怎么截图、怎么点击、怎么识别、怎么翻页」
  各自只有一份实现（原先在三个模块里各写一遍）。

注意：识别与锁图标定位等动作里的 try/except 与日志也收敛到这里，
feature 侧只关心「识别到了什么、要不要动作」。
"""

from __future__ import annotations

from typing import Any, ClassVar

from backend.automation.artifact_recognizer import ArtifactRecognizer
from backend.automation.mouse_controller import MouseController
from backend.automation.page_scroller import PageScroller
from backend.automation.slider_scroller import SliderScroller
from backend.automation.slot_detector import SlotDetector
from backend.automation.window_helper import WindowHelper
from backend.models.artifact import ArtifactInfo
from backend.models.artifact_recognition_field import ArtifactRecognitionField
from backend.models.slot_models import SlotDetectorConfig
from backend.utils.logger import log


class WindowScreenSource:
    """游戏窗口截图端口：内部处理「找窗口 → 聚焦 → 注入坐标原点」

    ``capture`` 可由调用方注入（Presenter 已持有的截图器），不传则自建。
    """

    def __init__(self, config: SlotDetectorConfig | None = None, capture: Any = None) -> None:
        if capture is None:
            from backend.automation.screen_capture import ScreenshotCapture

            capture = ScreenshotCapture()
        self._capture = capture
        self._config = config
        self._prepared = False

    def prepare(self) -> None:
        """聚焦窗口 + 注入坐标原点（幂等：同一轮遍历内只做一次）"""
        if self._prepared:
            return
        WindowHelper.focus()
        MouseController.set_origin(WindowHelper.get_origin())
        self._prepared = True

    def capture(self) -> Any | None:
        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)
        return None if result is None else result.image


class MousePointer:
    """指针端口（``MouseController`` 的静态点击口）"""

    def click(self, x: int, y: int) -> None:
        MouseController.move_and_click(x, y)


class DetectorSlotFinder:
    """格子检测端口（冻结的 ``SlotDetector``）"""

    def __init__(self, config: SlotDetectorConfig) -> None:
        self._config = config

    def find(self, image: Any) -> Any:
        return SlotDetector.detect(image, config=self._config)


class ScrollerNavigator:
    """列表导航端口：``SliderScroller``（回顶）+ ``PageScroller``（翻页），两者均冻结"""

    def __init__(
        self,
        config: SlotDetectorConfig,
        *,
        tick_delay_ms: int = 30,
        page_settle_ms: int = 200,
    ) -> None:
        self._config = config
        self._tick_delay_ms = tick_delay_ms
        self._page_settle_ms = page_settle_ms
        mouse = MouseController()
        self._capture = _capture()
        self._slider = SliderScroller(mouse, self._capture, config)
        self._pager = PageScroller(mouse, self._capture, config)

    def to_top(self) -> None:
        self._slider.ensure_at_top()

    def to_bottom(self) -> None:
        """滚到底部；滑轨缺失或滑块检测失败时抛 RuntimeError，由调用方提示用户"""
        from backend.automation.slider_detector import SliderDetector

        region = self._config.slider_region()
        if region is None:
            raise RuntimeError(f"扫描模板 {self._config.name!r} 未配置滑轨区域")
        slider_x, slider_top, slider_bottom, slider_w, slider_h = region

        WindowHelper.focus()
        slider_y = self._find_slider(slider_x, slider_top, slider_bottom, slider_w, slider_h)
        if slider_y is None:
            raise RuntimeError("滚动到底部失败：未检测到滑块")
        if slider_y - slider_top > SliderDetector.PROXIMITY:
            # 离顶部较远：先回顶再滚到底，保证"到底"位置准确
            log.info("滚动到底: 先回到顶部...")
            self._slider.ensure_at_top()
            slider_y = self._find_slider(slider_x, slider_top, slider_bottom, slider_w, slider_h)
            if slider_y is None:
                raise RuntimeError("滚动到底部失败：未检测到滑块")
        self._slider.scroll_to_bottom(slider_y)

    def _find_slider(self, x: int, top: int, bottom: int, w: int, h: int) -> int | None:
        from backend.automation.slider_detector import SliderDetector

        window = WindowHelper.find_genshin_window()
        result = self._capture.capture(window=window)
        if result is None:
            return None
        slider_y, _, _, _ = SliderDetector.find_slider(result.image, x, top, bottom, w, h)
        return slider_y

    def next_page(self, det_result: Any) -> bool:
        return self._pager.scroll_to_next_page(
            det_result, self._tick_delay_ms, self._page_settle_ms
        )


class RecognizerArtifactReader:
    """详情识别端口：把详情面板截图读成 ``ArtifactInfo``（失败返回 None，不抛异常）"""

    # 扫描场景要的字段（跳过套装效果查询以省 DB 开销）；其余场景用全部字段
    SCAN_FIELDS: ClassVar[frozenset[ArtifactRecognitionField]] = frozenset(
        {
            ArtifactRecognitionField.SET_NAME,
            ArtifactRecognitionField.PIECE_TYPE,
            ArtifactRecognitionField.MAIN_STAT,
            ArtifactRecognitionField.SUB_STATS,
            ArtifactRecognitionField.LEVEL,
            ArtifactRecognitionField.RARITY,
            ArtifactRecognitionField.LOCK_STATUS,
        }
    )

    def __init__(
        self,
        config: SlotDetectorConfig,
        ocr: Any,
        *,
        fields: frozenset[ArtifactRecognitionField] | None = None,
    ) -> None:
        self._config = config
        self._ocr = ocr
        self._fields = fields

    def read(self, image: Any) -> ArtifactInfo | None:
        try:
            return ArtifactRecognizer.recognize(
                image,
                self._config.detail_roi_configs,
                self._ocr,
                fields=self._fields,
                lock_anchor_search_region=self._config.lock_anchor_search_region,
                lock_anchor_to_level=self._config.lock_anchor_to_level,
                lock_anchor_to_sub_stats=self._config.lock_anchor_to_sub_stats,
            )
        except Exception as exc:
            log.debug(f"识别异常: {exc}")
            return None


class LockIconToggler:
    """锁定/解锁动作：模板匹配锁定图标并点击（首次定位后缓存坐标）"""

    # 优先匹配解锁（多数圣遗物未锁），失败再匹配锁定
    TEMPLATE_KEYS: ClassVar[tuple[str, ...]] = ("圣遗物状态已解锁", "圣遗物状态已锁定")
    MATCH_THRESHOLD: ClassVar[float] = 0.8

    def __init__(self, config: SlotDetectorConfig) -> None:
        self._config = config
        self._center: tuple[int, int] | None = None

    def reset(self) -> None:
        """清空缓存坐标（每次遍历开始前调用）"""
        self._center = None

    def toggle(self, image: Any) -> None:
        """点击锁定图标切换状态；定位失败抛 ``LockIconNotFoundError``"""
        from time import sleep

        if self._center is None:
            self._center = self._locate(image)
        MouseController.move_and_click(*self._center)
        sleep(0.3)

    def _locate(self, image: Any) -> tuple[int, int]:
        from backend.automation.template_manager import TemplateManager
        from backend.automation.template_matcher import multi_scale_match
        from backend.exceptions.automation.exceptions import LockIconNotFoundError

        search_region = self._config.lock_anchor_search_region
        for key in self.TEMPLATE_KEYS:
            template = TemplateManager.get(key)
            if template is None:
                continue
            score, (cx, cy), _scale, _size = multi_scale_match(
                image, template, search_region=search_region
            )
            if score >= self.MATCH_THRESHOLD:
                log.debug(f"锁定图标匹配成功 ({key}): ({cx}, {cy})")
                return cx, cy
        log.error("未找到锁定图标位置")
        raise LockIconNotFoundError()


def _capture():
    from backend.automation.screen_capture import ScreenshotCapture

    return ScreenshotCapture()
