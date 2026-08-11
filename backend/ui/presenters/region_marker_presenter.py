"""区域标记 Presenter — 截图 + 标记 + 颜色提取，纯业务逻辑"""

from __future__ import annotations

import cv2
import numpy as np
from utils.logger import log

from backend.automation.color_sampler import sample_roi_color
from backend.automation.template_manager import TemplateManager
from backend.utils.screen_capture import CaptureResult, ScreenshotCapture


class RegionMarkerPresenter:
    """区域标记业务逻辑"""

    @staticmethod
    def capture() -> CaptureResult:
        return ScreenshotCapture().capture()

    @staticmethod
    def mark_region(
        result: CaptureResult, x: int, y: int, w: int, h: int
    ) -> CaptureResult:
        result.draw_rect(
            x, y, w, h, color=(0, 255, 0), thickness=3, label=f"({x}, {y}) {w}x{h}"
        )
        return result

    @staticmethod
    def save_template(
        result: CaptureResult, filename: str, x: int, y: int, w: int, h: int
    ) -> None:
        roi = result.image[y : y + h, x : x + w]
        save_dir = TemplateManager.IMAGES_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{filename}.png"
        cv2.imwrite(str(save_path), cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))
        TemplateManager.register(filename, f"images/{filename}.png", (x, y, w, h))
        TemplateManager.save()
        log.info(f"已保存模板: {filename}.png ({w}x{h})，区域已写入 templates.json")

    @staticmethod
    def extract_color(result: CaptureResult, x: int, y: int, w: int, h: int) -> dict:
        """提取 ROI 主色调，返回 {r, g, b, h_hsv, s_hsv, v_hsv}"""
        r, g, b = sample_roi_color(result.image, x, y, w, h)
        hsv = cv2.cvtColor(np.uint8([[[r, g, b]]]), cv2.COLOR_RGB2HSV)[0][0]
        return {
            "r": int(r),
            "g": int(g),
            "b": int(b),
            "h_hsv": int(hsv[0]),
            "s_hsv": int(hsv[1]),
            "v_hsv": int(hsv[2]),
        }
