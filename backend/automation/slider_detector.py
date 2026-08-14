"""
滑块检测器 — 纯逻辑层，无 Qt 依赖
===============================
基于颜色采样匹配，双向搜索定位原神背包界面中的滚动条滑块位置。
支持滑块存在性检测、滑轨颜色验证、拖拽到位判定。

所有方法均为静态方法，可在任意线程中安全调用。
"""

from __future__ import annotations

import cv2
import numpy as np
from utils.logger import log

# ---- 滑块检测 ROI 参数（与游戏窗口坐标系相关） ----
_SLIDER_REGION_X = 1292
_SLIDER_TOP_Y = 184
_SLIDER_BOTTOM_Y = 978
_SLIDER_REGION_W = 10
_SLIDER_REGION_H = 10

# ---- 滑块颜色参数 ----
# 目标灰度值（滑块有两种状态：
#   不hover: #C7C7C7/#C6C6C6 → 灰度 199/198
#   hover/点击: #E2E2E2 → 灰度 226
# 拖拽时鼠标在滑轨附近必触发hover，需同时匹配两种颜色）
_SLIDER_TARGET_GRAY: tuple[int, ...] = (198, 199, 226)
_SLIDER_GRAY_THRESHOLD: int = 15
_SLIDER_MATCH_RATIO: float = 0.5
_SLIDER_SEARCH_STEP: int = 5
_SLIDER_MAX_SEARCH: int = 800
_SLIDER_PROXIMITY: int = 30
_SLIDER_TRACK_GRAY: int = 169  # 滑轨颜色 #A9A9A9 的灰度值

# ---- 拖拽参数 ----
_SLIDER_DRAG_DIST: int = 80
_SLIDER_DRAG_STEPS: int = 8
_SLIDER_DRAG_DELAY: int = 15
_SLIDER_EXTRA_TICKS: int = 10
_SLIDER_VERIFY_MAX: int = 15


class SliderDetector:
    """滑块检测器 — 纯函数，无状态，无 Qt 依赖"""

    # 公开常量（供外部引用）
    TARGET_GRAY = _SLIDER_TARGET_GRAY
    GRAY_THRESHOLD = _SLIDER_GRAY_THRESHOLD
    MATCH_RATIO = _SLIDER_MATCH_RATIO
    SEARCH_STEP = _SLIDER_SEARCH_STEP
    MAX_SEARCH = _SLIDER_MAX_SEARCH
    PROXIMITY = _SLIDER_PROXIMITY
    TRACK_GRAY = _SLIDER_TRACK_GRAY
    DRAG_DIST = _SLIDER_DRAG_DIST
    DRAG_STEPS = _SLIDER_DRAG_STEPS
    DRAG_DELAY = _SLIDER_DRAG_DELAY
    EXTRA_TICKS = _SLIDER_EXTRA_TICKS
    VERIFY_MAX = _SLIDER_VERIFY_MAX

    # ---- 核心检测 ----

    @staticmethod
    def find_slider(
        img: np.ndarray,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int = _SLIDER_REGION_W,
        region_h: int = _SLIDER_REGION_H,
    ) -> tuple[int | None, float, int, list[int]]:
        """双向查找滑块位置：从顶部向下 + 从底部向上，取最佳匹配。

        Returns:
            (slider_y, best_ratio, best_y, best_samples)
            slider_y — 匹配到的滑块Y坐标，未匹配返回None
            best_ratio — 最佳匹配率（即使未达阈值）
            best_y — 最佳匹配Y坐标（即使未达阈值，-1表示无采样）
            best_samples — 最佳匹配位置的灰度采样值
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ih, _ = gray.shape

        best_ratio = 0.0
        best_y = -1
        best_samples: list[int] = []

        # 向下搜索：从 top_y 开始
        max_y = min(ih - region_h, top_y + _SLIDER_MAX_SEARCH)
        for check_y in range(top_y, max_y + 1, _SLIDER_SEARCH_STEP):
            ratio, samples = SliderDetector.eval_roi(
                gray, region_x, check_y, region_w, region_h
            )
            if ratio > best_ratio:
                best_ratio = ratio
                best_y = check_y
                best_samples = samples
            if ratio >= _SLIDER_MATCH_RATIO:
                return (check_y, best_ratio, best_y, best_samples)

        # 向上搜索：从 bottom_y 开始
        min_y = max(0, bottom_y - _SLIDER_MAX_SEARCH)
        for check_y in range(bottom_y, min_y - 1, -_SLIDER_SEARCH_STEP):
            ratio, samples = SliderDetector.eval_roi(
                gray, region_x, check_y, region_w, region_h
            )
            if ratio > best_ratio:
                best_ratio = ratio
                best_y = check_y
                best_samples = samples
            if ratio >= _SLIDER_MATCH_RATIO:
                return (check_y, best_ratio, best_y, best_samples)

        log.warning(
            f"双向搜索未匹配: 最佳匹配率={best_ratio:.2f}@y={best_y}, "
            f"灰度值={best_samples}"
        )
        return (None, best_ratio, best_y, best_samples)

    @staticmethod
    def eval_roi(
        gray: np.ndarray,
        rx: int,
        ry: int,
        rw: int,
        rh: int,
    ) -> tuple[float, list[int]]:
        """评估指定ROI是否匹配滑块颜色。

        采样 ROI 中心点及其周围 8 邻域像素灰度值，
        与目标灰度值比较，返回匹配比例和采样值列表。
        """
        roi = gray[ry : ry + rh, rx : rx + rw]
        cx, cy = rw // 2, rh // 2

        samples: list[int] = []
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                py, px = cy + dy, cx + dx
                if 0 <= py < rh and 0 <= px < rw:
                    samples.append(int(roi[py, px]))

        if not samples:
            return (0.0, [])

        match_count = 0
        for sv in samples:
            for tv in _SLIDER_TARGET_GRAY:
                if abs(sv - tv) < _SLIDER_GRAY_THRESHOLD:
                    match_count += 1
                    break

        return (match_count / len(samples), samples)

    @staticmethod
    def check_track_color(
        img: np.ndarray,
        rx: int,
        ry: int,
        rw: int = _SLIDER_REGION_W,
        rh: int = _SLIDER_REGION_H,
    ) -> bool:
        """检测指定位置是否为滑轨颜色（滑块消失后用于确认到底）"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        roi = gray[ry : ry + rh, rx : rx + rw]
        cx, cy = rw // 2, rh // 2
        samples: list[int] = []
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                py, px = cy + dy, cx + dx
                if 0 <= py < rh and 0 <= px < rw:
                    samples.append(int(roi[py, px]))
        if not samples:
            return False
        match_count = sum(
            1 for s in samples
            if abs(s - _SLIDER_TRACK_GRAY) < _SLIDER_GRAY_THRESHOLD
        )
        return match_count / len(samples) >= _SLIDER_MATCH_RATIO

    # ---- 调试预览 ----

    @staticmethod
    def generate_debug_preview(
        img: np.ndarray,
        region_x: int,
        top_y: int,
        bottom_y: int,
        region_w: int = _SLIDER_REGION_W,
        region_h: int = _SLIDER_REGION_H,
        slider_y: int | None = None,
        label: str = "",
        best_ratio: float = 0.0,
        best_y: int = -1,
    ) -> np.ndarray:
        """生成灰度调试预览图：标注双向搜索路径、步进采样点、ROI、滑块位置"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        ih = gray.shape[0]

        search_x = region_x + region_w // 2
        step = _SLIDER_SEARCH_STEP

        # === 向下搜索线（绿色） ===
        down_end = min(ih - 1, top_y + _SLIDER_MAX_SEARCH)
        cv2.line(debug, (search_x, top_y), (search_x, down_end), (0, 255, 0), 1)
        cv2.rectangle(
            debug, (region_x, top_y),
            (region_x + region_w, top_y + region_h), (0, 255, 0), 1,
        )
        for check_y in range(top_y, down_end + 1, step):
            cv2.circle(debug, (search_x, check_y), 1, (0, 180, 0), -1)

        # === 向上搜索线（蓝色） ===
        up_end = max(0, bottom_y - _SLIDER_MAX_SEARCH)
        cv2.line(debug, (search_x, bottom_y), (search_x, up_end), (255, 0, 0), 1)
        cv2.rectangle(
            debug, (region_x, bottom_y),
            (region_x + region_w, bottom_y + region_h), (255, 0, 0), 1,
        )
        for check_y in range(bottom_y, up_end - 1, -step):
            cv2.circle(debug, (search_x, check_y), 1, (180, 0, 0), -1)

        # === 最佳匹配点（黄色） ===
        if best_y >= 0:
            cv2.circle(debug, (search_x, best_y), 4, (0, 255, 255), -1)
            cv2.putText(
                debug, f"best={best_ratio:.2f}", (search_x + 8, best_y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1,
            )

        # === 当前滑块位置（红色） ===
        if slider_y is not None:
            cv2.circle(debug, (search_x, slider_y), 5, (0, 0, 255), -1)
            cv2.putText(
                debug, f"slider@{slider_y}", (search_x + 8, slider_y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1,
            )

        # === 标题 ===
        cv2.putText(
            debug, label, (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )

        return debug