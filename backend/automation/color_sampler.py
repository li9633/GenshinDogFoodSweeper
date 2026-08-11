"""颜色采样工具 — 从图像 ROI 区域提取主色调"""

from __future__ import annotations

import cv2
import numpy as np


def sample_roi_color(
    image: np.ndarray, x: int, y: int, w: int, h: int
) -> tuple[int, int, int]:
    """
    提取 ROI 区域的主色调（RGB）。

    采样策略：取 ROI 中心 65% 区域，降采样后用 K-Means 聚类找主色，
    避免边缘干扰和文字噪声。
    """
    roi = image[y : y + h, x : x + w]
    if roi.size == 0:
        return (0, 0, 0)
    ch, cw = int(h * 0.65), int(w * 0.65)
    cy, cx = (h - ch) // 2, (w - cw) // 2
    center = roi[cy : cy + ch, cx : cx + cw]
    pixels = center[::2, ::2].reshape(-1, 3).astype(np.float32)
    if len(pixels) < 3:
        return (0, 0, 0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    label_counts = np.bincount(labels.flatten())
    dominant = centers[np.argmax(label_counts)]
    return tuple(round(c) for c in dominant)
