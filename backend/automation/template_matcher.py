"""多尺度模板匹配工具"""

from __future__ import annotations

import cv2
import numpy as np

DEFAULT_SCALES: tuple[float, ...] = (
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.5,
)


def multi_scale_match(
    screen_gray: np.ndarray,
    template: np.ndarray,
    scales: tuple[float, ...] = DEFAULT_SCALES,
) -> tuple[float, tuple[int, int], float, tuple[int, int]]:
    """多尺度模板匹配，返回 (最高分, 位置, 缩放比, 模板尺寸)"""
    best_score = -1.0
    best_loc = (0, 0)
    best_scale = 1.0
    best_size = template.shape[::-1]

    th, tw = template.shape
    sh, sw = screen_gray.shape

    for scale in scales:
        new_w = int(tw * scale)
        new_h = int(th * scale)
        if new_w > sw or new_h > sh or new_w < 5 or new_h < 5:
            continue
        scaled = cv2.resize(template, (new_w, new_h))
        match_result = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
        if max_val > best_score:
            best_score = float(max_val)
            best_loc = max_loc
            best_scale = scale
            best_size = (new_w, new_h)

    return best_score, best_loc, best_scale, best_size
