"""
圣遗物格子检测器
================
基于灰度阈值 + 轮廓检测，自动定位圣遗物列表中的每个格子位置。
不依赖 Qt，可独立测试。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import cv2
import numpy as np


class DetectResult(NamedTuple):
    """格子检测结果。"""

    slots: list[tuple[int, int, int, int, int, int]]
    bottom_y: int  # 最后一行底部边缘的 Y 坐标


@dataclass(frozen=True)
class SlotDetectorConfig:
    """圣遗物格子检测的几何配置。

    如果原神 UI 改版导致格子尺寸或间距变化，只需创建新的配置实例传入即可，
    检测算法本身无需改动。
    """

    name: str = "未命名"  # 配置名称，调试面板下拉显示用
    slot_w: int = 125  # 格子宽度
    slot_h: int = 153  # 格子高度（含底部白色等级条）
    level_h: int = 36  # 底部白色等级条高度
    cols: int = 8  # 每行列数
    rows: int = 4  # 每页行数
    roi_left_offset: int = 6  # ROI 左侧到第一列左边缘的偏移
    roi_right_offset: int = 15  # ROI 右侧到最后一列右边缘的偏移
    top_offset: int = 90  # 白色条顶部到格子上边缘的距离
    white_threshold: int = 200  # 白色二值化阈值
    tolerance: int = 20  # 等级条尺寸容差 (px)
    roi: tuple[int, int, int, int] | None = None  # 截图裁剪区域 (x, y, w, h)
    has_artifact_count: bool = True  # 页面是否显示圣遗物数量（背包: True, 分解: False）
    # 滑轨区域（相对于格子 ROI，用于滚动条检测）
    slider_x_offset: int = 4  # 滑轨 X = ROI右边缘 + 此值
    slider_top_offset: int = -9  # 滑轨顶部 = ROI顶部 + 此值
    slider_bottom_offset: int = -25  # 滑轨底部 = ROI底部 + 此值
    slider_region_w: int = 10  # 滑块检测区域宽度
    slider_region_h: int = 10  # 滑块检测区域高度

    def col_step(self, roi_w: int) -> float:
        """根据 ROI 宽度和左右 offset 计算列步长。"""
        span = roi_w - self.roi_left_offset - self.roi_right_offset
        return (span - self.slot_w) / (self.cols - 1)

    def row_step(self, roi_h: int) -> float:
        """根据 ROI 高度计算行步长。"""
        return (roi_h - self.slot_h) / (self.rows - 1)

    def slider_region(self) -> tuple[int, int, int, int, int] | None:
        """返回滑轨检测区域 (x, top_y, bottom_y, w, h)。

        基于格子 ROI 和偏移量动态计算，切换配置时自动跟随。
        """
        if self.roi is None:
            return None
        rx, ry, rw, rh = self.roi
        return (
            rx + rw + self.slider_x_offset,
            ry + self.slider_top_offset,
            ry + rh + self.slider_bottom_offset,
            self.slider_region_w,
            self.slider_region_h,
        )


## 背包圣遗物列表格子配置
BAG_SLOT_CONFIG = SlotDetectorConfig(
    name="背包圣遗物列表",
    roi=(118, 193, 1170, 810)
)

# 分解页面格子配置
SALVAGE_SLOT_CONFIG = SlotDetectorConfig(
    name="圣遗物分解",
    roi=(50, 131, 1255, 780),
    has_artifact_count=False,
    rows=4,
    cols=9,
    roi_left_offset=9,
    roi_right_offset=7,
    slider_x_offset=8,
    slider_top_offset=2,
    slider_bottom_offset=-22,
)

# 所有可用配置列表（调试面板下拉切换用）
ALL_SLOT_CONFIGS: list[SlotDetectorConfig] = [BAG_SLOT_CONFIG, SALVAGE_SLOT_CONFIG]


class SlotDetector:
    """圣遗物格子检测器

    算法流程：
    1. 裁剪 ROI 区域
    2. 灰度化 → 高阈值二值化 → 提取白色等级条区域
    3. 按等级条尺寸过滤 → 向上扩展为完整格子
    4. 排序 → 返回格子中心坐标

    所有几何参数由 SlotDetectorConfig 提供，调用方可通过 config 参数自定义。
    """

    @staticmethod
    def detect(
        image: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
        white_threshold: int | None = None,
        tolerance: int | None = None,
    ) -> DetectResult:
        """检测格子位置。

        检测原理：每个圣遗物格子底部有白色等级条(#E3E3E3≈227)，
        检测到白色条后向上扩展得到完整格子。
        先腐蚀消去选中格子的6-7px白色边框，再检测等级条。

        Args:
            image: BGR 截图 (H, W, 3)
            roi: 检测区域
            white_threshold: 白色阈值 (0-255)
            tolerance: 尺寸容差 (px)
            top_offset: 白色条顶部到格子上边缘的距离 (px)

        Returns:
            DetectResult(slots, bottom_y)
            slots: [(cx, cy, x, y, w, h), ...] 按 y 再 x 排序
            bottom_y: 最后一行底部边缘的 Y 坐标
        """
        if white_threshold is None:
            white_threshold = config.white_threshold
        if tolerance is None:
            tolerance = config.tolerance

        if roi is None:
            roi = config.roi
        if roi is not None:
            rx, ry, rw, rh = roi
            crop = image[ry : ry + rh, rx : rx + rw].copy()
            offset_x, offset_y = rx, ry
        else:
            crop = image.copy()
            offset_x, offset_y = 0, 0

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, white_threshold, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.erode(binary, kernel, iterations=2)

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 计算期望列中心 x 坐标（在 crop 坐标系内）
        span_w = rw - config.roi_left_offset - config.roi_right_offset
        col_step = (span_w - config.slot_w) / (config.cols - 1)
        expected_cx = [
            config.roi_left_offset + c * col_step + config.slot_w / 2
            for c in range(config.cols)
        ]

        # 将轮廓匹配到最近的列，每列每行只保留一个最佳匹配
        col_bars: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if (
                abs(w - config.slot_w) > tolerance
                or abs(h - config.level_h) > tolerance
            ):
                continue
            bar_cx = x + w // 2
            # 找最近的期望列
            col_idx = min(
                range(len(expected_cx)), key=lambda i: abs(bar_cx - expected_cx[i])
            )
            if abs(bar_cx - expected_cx[col_idx]) > tolerance:
                continue
            row_key = y // 50
            key = (col_idx, row_key)
            # 同一列同一行只保留第一个
            if key not in col_bars:
                col_bars[key] = (x, y, w, h)

        level_bars = sorted(col_bars.values(), key=lambda b: (b[1] // 50, b[0]))
        slots = SlotDetector._bars_to_slots(level_bars, offset_x, offset_y, config)
        bottom_y = max(s[3] + s[5] for s in slots) if slots else 0
        return DetectResult(slots, bottom_y)

    @staticmethod
    def _bars_to_slots(
        level_bars: list[tuple[int, int, int, int]],
        offset_x: int,
        offset_y: int,
        config: SlotDetectorConfig,
    ) -> list[tuple[int, int, int, int, int, int]]:
        slots: list[tuple[int, int, int, int, int, int]] = []
        seen: set[tuple[int, int]] = set()
        for bx, by, bw, bh in level_bars:
            sx = offset_x + bx
            sy = offset_y + by - config.top_offset
            sw = config.slot_w
            sh = config.top_offset + config.level_h
            cx = sx + sw // 2
            cy = sy + sh // 2
            key = (cx // 10, cy // 10)
            if key in seen:
                continue
            seen.add(key)
            slots.append((cx, cy, sx, sy, sw, sh))
        return slots

    @staticmethod
    def draw_debug(
        image: np.ndarray,
        slots: list[tuple[int, int, int, int, int, int]],
        roi: tuple[int, int, int, int] | None = None,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
    ) -> np.ndarray:
        """在灰度图上绘制检测结果，返回 RGB 预览图。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        if roi is None:
            roi = config.roi
        if roi is not None:
            rx, ry, rw, rh = roi
            cv2.rectangle(debug, (rx, ry), (rx + rw, ry + rh), (255, 255, 0), 2)

            # 左侧 offset 参考线
            ref_left = rx + config.roi_left_offset
            cv2.line(debug, (ref_left, ry), (ref_left, ry + rh), (255, 255, 0), 1)
            cv2.putText(
                debug,
                f"+{config.roi_left_offset}",
                (ref_left + 2, ry + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 0),
                1,
            )

            # 右侧 offset 参考线
            ref_right = rx + rw - config.roi_right_offset
            cv2.line(debug, (ref_right, ry), (ref_right, ry + rh), (255, 255, 0), 1)
            cv2.putText(
                debug,
                f"-{config.roi_right_offset}",
                (ref_right + 2, ry + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 0),
                1,
            )

            # 每列左右边框竖线（绝对位置计算，无累积误差）
            span_w = rw - config.roi_left_offset - config.roi_right_offset
            for c in range(config.cols):
                col_left = int(
                    ref_left + c * (span_w - config.slot_w) / (config.cols - 1)
                )
                col_right = col_left + config.slot_w
                cv2.line(debug, (col_left, ry), (col_left, ry + rh), (255, 0, 0), 1)
                cv2.line(debug, (col_right, ry), (col_right, ry + rh), (0, 0, 255), 1)
            # 行分隔横线（绝对位置计算）
            for r in range(config.rows + 1):
                gy = int(ry + r * (rh - config.slot_h) / config.rows)
                cv2.line(debug, (rx, gy), (rx + rw, gy), (255, 0, 255), 1)

            # 金色滑轨区域（动态计算）
            sr = config.slider_region()
            if sr is not None:
                sx, stop_y, sbot_y, sw, sh = sr
                cv2.rectangle(debug, (sx, stop_y), (sx + sw, sbot_y), (0, 215, 255), 1)
                cv2.putText(
                    debug, "滑轨", (sx + sw + 4, (stop_y + sbot_y) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 215, 255), 1,
                )

        for i, (cx, cy, x, y, w, h) in enumerate(slots):
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                debug,
                str(i + 1),
                (cx - 12, cy + 8),
                cv2.FONT_HERSHEY_DUPLEX,
                0.55,
                (0, 0, 255),
                2,
            )

        if slots:
            last_bottom = max(s[3] + s[5] for s in slots)
            cv2.line(
                debug, (0, last_bottom), (debug.shape[1], last_bottom), (0, 0, 255), 2
            )

        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)