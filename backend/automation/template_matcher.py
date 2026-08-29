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
    image: np.ndarray,
    template: Template,
    use_region: bool = True,
    search_region: tuple[int, int, int, int] | None = None,
    scales: tuple[float, ...] = DEFAULT_SCALES,
) -> tuple[float, tuple[int, int], float, tuple[int, int]]:
    """在 RGB 图像中匹配模板，自动处理灰度转换和区域裁剪。

    Args:
        image: RGB 彩色图像
        template: Template 对象（含 region 信息）
        use_region: 是否使用区域裁剪。
            - True 时优先使用 search_region，其次使用 template.region，都没有则全图搜索
            - False 时忽略所有 region，全图搜索
        search_region: 覆盖 template.region 的搜索区域 (x, y, w, h)，
            用于弹窗等场景下模板位置与默认注册位置不同的情况
        scales: 多尺度列表

    Returns:
        (score, (center_x, center_y), scale, (w, h))
        center_x/center_y 是匹配中心在原始图像（全图）中的坐标
    """
    tmpl = cv2.imread(str(template.path), cv2.IMREAD_GRAYSCALE)
    if tmpl is None:
        log.warning(f"[模板匹配] 无法加载模板: {template.path}")
        return -1.0, (0, 0), 1.0, (0, 0)

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    if use_region:
        region = search_region if search_region is not None else template.region
        if region:
            rx, ry, rw, rh = region
            search_area = gray[ry:ry + rh, rx:rx + rw]
            if search_area.size == 0:
                log.warning(f"[模板匹配] {template.display_name} 搜索区域无效")
                return -1.0, (0, 0), 1.0, (0, 0)
        else:
            rx, ry = 0, 0
            search_area = gray
    else:
        rx, ry = 0, 0
        search_area = gray

    best_score = -1.0
    best_loc = (0, 0)
    best_scale = 1.0
    best_size = tmpl.shape[::-1]

    th, tw = tmpl.shape
    sh, sw = search_area.shape

    for scale in scales:
        new_w = int(tw * scale)
        new_h = int(th * scale)
        if new_w > sw or new_h > sh or new_w < 5 or new_h < 5:
            continue
        scaled = cv2.resize(tmpl, (new_w, new_h))
        match_result = cv2.matchTemplate(search_area, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
        if max_val > best_score:
            best_score = float(max_val)
            best_loc = max_loc
            best_scale = scale
            best_size = (new_w, new_h)

    cx = rx + best_loc[0] + best_size[0] // 2
    cy = ry + best_loc[1] + best_size[1] // 2

    log.debug(
        f"[模板匹配] [{template.display_name}] 模板={tw}x{th} 搜索区域={sw}x{sh} "
        f"最佳得分={best_score:.3f} 中心=({cx}, {cy}) 缩放={best_scale:.2f} 尺寸={best_size}"
    )
    return best_score, (cx, cy), best_scale, best_size


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