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

        if len(slots) < 32:
            slots = SlotDetector._fill_gaps(slots)

        slots = SlotDetector._dedup(slots)
        return slots

    @staticmethod
    def _dedup(
        slots: list[tuple[int, int, int, int, int, int]],
        threshold: int = 30,
    ) -> list[tuple[int, int, int, int, int, int]]:
        result: list[tuple[int, int, int, int, int, int]] = []
        for s in sorted(slots, key=lambda s: (s[1], s[0])):
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
    def _fill_gaps(
        slots: list[tuple[int, int, int, int, int, int]],
        cols: int = 8,
    ) -> list[tuple[int, int, int, int, int, int]]:
        """网格推断：仅在已检测到的行内补齐缺失列，不新增行。

        最后一页可能不足 4 行，只补齐已有行内的缺口。
        """
        if len(slots) < 2:
            return slots

        slot_h = SlotDetector.LEVEL_H + 90
        slot_w = SlotDetector.SLOT_W

        row_groups: dict[int, list[tuple[int, int, int, int, int, int]]] = {}
        for s in slots:
            row_key = s[1] // 50
            row_groups.setdefault(row_key, []).append(s)

        all_xs = sorted({s[0] for s in slots})
        col_w = int(np.median([all_xs[i + 1] - all_xs[i] for i in range(len(all_xs) - 1)])) if len(all_xs) > 1 else slot_w
        grid_cx = min(all_xs)

        detected = {(s[0] // 20, s[1] // 20) for s in slots}
        result = list(slots)

        for row_slots in row_groups.values():
            if len(row_slots) < 2:
                continue
            cy = row_slots[0][1]
            for c in range(cols):
                ecx = grid_cx + c * col_w
                if (ecx // 20, cy // 20) in detected:
                    continue
                sx = ecx - slot_w // 2
                sy = cy - slot_h // 2
                result.append((ecx, cy, sx, sy, slot_w, slot_h))

        return result

    @staticmethod
    def draw_debug(
        image: np.ndarray,
        slots: list[tuple[int, int, int, int, int, int]],
        roi: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """在灰度图上绘制检测结果，返回 RGB 预览图。

        Args:
            image: BGR 截图
            slots: detect() 返回的格子列表
            roi: 检测区域

        Returns:
            RGB numpy 数组 (H, W, 3)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        if roi is not None:
            rx, ry, rw, rh = roi
            cv2.rectangle(debug, (rx, ry), (rx + rw, ry + rh), (255, 255, 0), 2)
            cv2.line(debug, (0, ry), (debug.shape[1], ry), (255, 255, 0), 1)

        for i, (cx, cy, x, y, w, h) in enumerate(slots):
            cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                debug, str(i + 1), (cx - 10, cy + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1,
            )

        if slots:
            last_bottom = max(s[3] + s[5] for s in slots)
            cv2.line(debug, (0, last_bottom), (debug.shape[1], last_bottom), (0, 0, 255), 2)

        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)