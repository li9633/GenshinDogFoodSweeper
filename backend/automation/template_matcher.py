"""多尺度模板匹配工具"""

from __future__ import annotations

import cv2
import numpy as np
from utils.logger import log

from backend.models.template import Template

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
    template: Template,
    scales: tuple[float, ...] = DEFAULT_SCALES,
) -> tuple[float, tuple[int, int], float, tuple[int, int]]:
    """多尺度模板匹配，返回 (最高分, 位置, 缩放比, 模板尺寸)

    Args:
        screen_gray: 搜索区域灰度图
        template: Template 对象，内部加载图片并提取 display_name 用于日志
    """
    tmpl = cv2.imread(str(template.path), cv2.IMREAD_GRAYSCALE)
    if tmpl is None:
        log.warning(f"[模板匹配] 无法加载模板: {template.path}")
        return -1.0, (0, 0), 1.0, (0, 0)

    best_score = -1.0
    best_loc = (0, 0)
    best_scale = 1.0
    best_size = tmpl.shape[::-1]

    th, tw = tmpl.shape
    sh, sw = screen_gray.shape

    for scale in scales:
        new_w = int(tw * scale)
        new_h = int(th * scale)
        if new_w > sw or new_h > sh or new_w < 5 or new_h < 5:
            continue
        scaled = cv2.resize(tmpl, (new_w, new_h))
        match_result = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
        if max_val > best_score:
            best_score = float(max_val)
            best_loc = max_loc
            best_scale = scale
            best_size = (new_w, new_h)

    log.debug(
        f"[模板匹配] [{template.display_name}] 模板={tw}x{th} 搜索区域={sw}x{sh} "
        f"最佳得分={best_score:.3f} 位置={best_loc} 缩放={best_scale:.2f} 尺寸={best_size}"
    )
    return best_score, best_loc, best_scale, best_size


def find_all_matches(
    screen_gray: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.8,
    scales: tuple[float, ...] = DEFAULT_SCALES,
    min_distance: int = 10,
) -> list[tuple[float, int, int, int, int]]:
    """查找所有匹配位置，返回 [(score, x, y, w, h), ...]，按 Y 坐标升序排列"""
    th, tw = template.shape
    sh, sw = screen_gray.shape
    all_matches: list[tuple[float, int, int, int, int]] = []

    for scale in scales:
        new_w = int(tw * scale)
        new_h = int(th * scale)
        if new_w > sw or new_h > sh or new_w < 5 or new_h < 5:
            continue
        scaled = cv2.resize(template, (new_w, new_h))
        result = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        for pt in zip(*locations[::-1]):
            score = float(result[pt[1], pt[0]])
            all_matches.append((score, pt[0], pt[1], new_w, new_h))

    if not all_matches:
        return []

    # 非极大值抑制：按得分降序，移除重叠匹配
    all_matches.sort(key=lambda m: m[0], reverse=True)
    kept: list[tuple[float, int, int, int, int]] = []
    for m in all_matches:
        score, x, y, _w, _h = m
        if not any(
            abs(x - kx) < min_distance and abs(y - ky) < min_distance
            for _, kx, ky, _, _ in kept
        ):
            kept.append(m)

    # 按 Y 坐标升序返回
    kept.sort(key=lambda m: m[2])
    return kept