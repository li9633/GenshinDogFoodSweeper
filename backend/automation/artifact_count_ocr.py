"""圣遗物数量 OCR 识别模块。

从背包界面截图中 OCR 识别圣遗物数量（如 "1234/1500" → 1234）。
独立模块，不依赖其他业务逻辑，可被任意调用方使用。
"""

from __future__ import annotations

import re

from backend.automation.window_helper import WindowHelper
from backend.utils.screen_capture import ScreenshotCapture


def ocr_artifact_count(capture: ScreenshotCapture, ocr) -> int:
    """OCR 识别背包圣遗物数量（"1234/1500" → 1234）。

    Args:
        capture: 截图工具
        ocr: PaddleOCR 实例

    Returns:
        圣遗物数量，失败返回 0
    """
    window = WindowHelper.find_genshin_window()
    result = capture.capture(window=window)
    if result is None:
        return 0
    img = result.image
    h, w = img.shape[:2]
    roi_x, roi_y = 1606, 52
    roi_w, roi_h = 206, 49
    x1 = max(0, roi_x)
    y1 = max(0, roi_y)
    x2 = min(w, roi_x + roi_w)
    y2 = min(h, roi_y + roi_h)
    if x2 <= x1 or y2 <= y1:
        return 0
    cropped = img[y1:y2, x1:x2].copy()
    ocr_result = ocr.ocr(cropped)
    texts: list[str] = []
    if ocr_result and ocr_result[0]:
        r = ocr_result[0]
        if isinstance(r, dict):
            texts = [t for t in r.get("rec_texts", []) if t and t.strip()]
        elif hasattr(r, "rec_texts"):
            texts = [t for t in r.rec_texts if t and t.strip()]
    full_text = "".join(texts)
    m = re.search(r"(\d+)\s*/\s*\d+", full_text)
    if m:
        return int(m.group(1))
    m2 = re.search(r"\d+", full_text)
    return int(m2.group(0)) if m2 else 0