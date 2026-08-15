"""
圣遗物格子检测器
================
基于灰度阈值 + 轮廓检测，自动定位圣遗物列表中的每个格子位置。
不依赖 Qt，可独立测试。
"""

from __future__ import annotations

import cv2
import numpy as np


class SlotDetector:
    """圣遗物格子检测器

    算法流程：
    1. 裁剪 ROI 区域
    2. 灰度化 → 高阈值二值化 → 提取白色等级条区域
    3. 按等级条尺寸过滤 → 向上扩展为完整格子
    4. 排序 → 返回格子中心坐标
    """

    # 圣遗物格子尺寸常量
    SLOT_W = 125   # 格子宽度
    SLOT_H = 153   # 格子高度（含底部白色等级条）
    LEVEL_H = 36   # 底部白色等级条高度
    COLS = 8       # 每行列数
    ROWS = 4       # 每页行数
    ROI_LEFT_OFFSET = 6    # ROI 左侧到第一列左边缘的偏移
    ROI_RIGHT_OFFSET = 15  # ROI 右侧到最后一列右边缘的偏移

    @classmethod
    def col_step(cls, roi_w: int) -> float:
        """根据 ROI 宽度和左右 offset 计算列步长。

        span = roi_w - 6 - 15  # 第1列左到第8列右的实际距离
        span = 8 × SLOT_W + 7 × gap  →  gap = (span - 8×SLOT_W) / 7
        col_step = SLOT_W + gap = (span - SLOT_W) / 7
        """
        span = roi_w - cls.ROI_LEFT_OFFSET - cls.ROI_RIGHT_OFFSET
        return (span - cls.SLOT_W) / (cls.COLS - 1)

    @classmethod
    def row_step(cls, roi_h: int) -> float:
        """根据 ROI 高度计算行步长。"""
        return (roi_h - cls.SLOT_H) / (cls.ROWS - 1)

    @staticmethod
    def detect(
        image: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
        white_threshold: int = 200,
        tolerance: int = 20,
        top_offset: int = 90,
    ) -> list[tuple[int, int, int, int, int, int]]:
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
            [(cx, cy, x, y, w, h), ...] 按 y 再 x 排序
        """
        if roi is not None:
            rx, ry, rw, rh = roi
            crop = image[ry:ry + rh, rx:rx + rw].copy()
            offset_x, offset_y = rx, ry
        else:
            crop = image.copy()
            offset_x, offset_y = 0, 0

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, white_threshold, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.erode(binary, kernel, iterations=2)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        level_bars: list[tuple[int, int, int, int]] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if abs(w - SlotDetector.SLOT_W) <= tolerance and abs(h - SlotDetector.LEVEL_H) <= tolerance:
                level_bars.append((x, y, w, h))

        level_bars.sort(key=lambda b: (b[1] // 50, b[0]))

        slots = SlotDetector._bars_to_slots(level_bars, offset_x, offset_y, top_offset)
        slots = SlotDetector._dedup(slots)
        return slots

    @staticmethod
    def _dedup(
        slots: list[tuple[int, int, int, int, int, int]],
        threshold: int = 30,
    ) -> list[tuple[int, int, int, int, int, int]]:
        result: list[tuple[int, int, int, int, int, int]] = []
        for s in sorted(slots, key=lambda s: (s[1] // 50, s[0])):
            if not any(abs(s[0] - r[0]) < threshold and abs(s[1] - r[1]) < threshold for r in result):
                result.append(s)
        return result

    @staticmethod
    def _bars_to_slots(
        level_bars: list[tuple[int, int, int, int]],
        offset_x: int, offset_y: int, top_offset: int,
    ) -> list[tuple[int, int, int, int, int, int]]:
        slots: list[tuple[int, int, int, int, int, int]] = []
        seen: set[tuple[int, int]] = set()
        for bx, by, bw, bh in level_bars:
            sx = offset_x + bx
            sy = offset_y + by - top_offset
            sw = SlotDetector.SLOT_W
            sh = top_offset + SlotDetector.LEVEL_H
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
    ) -> np.ndarray:
        """在灰度图上绘制检测结果，返回 RGB 预览图。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        if roi is not None:
            rx, ry, rw, rh = roi
            cv2.rectangle(debug, (rx, ry), (rx + rw, ry + rh), (255, 255, 0), 2)

            # 6px 参考线：ROI 左侧 + 6px = 最左列格子左边缘
            x_offset = 6
            ref_left = rx + x_offset
            cv2.line(debug, (ref_left, ry), (ref_left, ry + rh), (255, 255, 0), 1)
            cv2.putText(debug, f"+{x_offset}", (ref_left + 2, ry + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)

            # 15px 参考线：ROI 右侧 - 15px = 最右列格子右边缘
            x_offset = 15
            ref_right = rx + rw - x_offset
            cv2.line(debug, (ref_right, ry), (ref_right, ry + rh), (255, 255, 0), 1)
            cv2.putText(debug, f"-{x_offset}", (ref_right + 2, ry + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)

            # 每列左右边框竖线（绝对位置计算，无累积误差）
            span_w = rw - SlotDetector.ROI_LEFT_OFFSET - SlotDetector.ROI_RIGHT_OFFSET
            for c in range(SlotDetector.COLS):
                col_left = int(ref_left + c * (span_w - SlotDetector.SLOT_W) / (SlotDetector.COLS - 1))
                col_right = col_left + SlotDetector.SLOT_W
                cv2.line(debug, (col_left, ry), (col_left, ry + rh), (255, 0, 0), 1)
                cv2.line(debug, (col_right, ry), (col_right, ry + rh), (0, 0, 255), 1)
            # 行分隔横线（绝对位置计算）
            for r in range(SlotDetector.ROWS + 1):
                gy = int(ry + r * (rh - SlotDetector.SLOT_H) / SlotDetector.ROWS)
                cv2.line(debug, (rx, gy), (rx + rw, gy), (255, 0, 255), 1)

        for i, (cx, cy, x, y, w, h) in enumerate(slots):
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                debug, str(i + 1), (cx - 12, cy + 8),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 0, 255), 2,
            )

        if slots:
            last_bottom = max(s[3] + s[5] for s in slots)
            cv2.line(debug, (0, last_bottom), (debug.shape[1], last_bottom), (0, 0, 255), 2)

        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)