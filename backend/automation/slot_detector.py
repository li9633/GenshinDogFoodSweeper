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
    white_threshold: int = 226  # 白色二值化阈值 (E3E3E3=227 vs 空格子 DEDEDE=222)
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

        # 列位置
        ref_left = config.roi_left_offset
        span_w = rw - config.roi_left_offset - config.roi_right_offset
        col_step = (span_w - config.slot_w) / (config.cols - 1)

        # === 轮廓检测找页尾 ===
        _, binary = cv2.threshold(gray, white_threshold, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.erode(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        expected_cx = [
            ref_left + c * col_step + config.slot_w / 2
            for c in range(config.cols)
        ]
        tolerance = config.tolerance
        page_bottom_crop = 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if (
                abs(w - config.slot_w) > tolerance
                or abs(h - config.level_h) > tolerance
            ):
                continue
            bar_cx = x + w // 2
            col_idx = min(
                range(len(expected_cx)), key=lambda i: abs(bar_cx - expected_cx[i])
            )
            if abs(bar_cx - expected_cx[col_idx]) > tolerance:
                continue
            bar_bottom = y + h
            page_bottom_crop = max(page_bottom_crop, bar_bottom)

        if page_bottom_crop > 0:
            pass  # 使用轮廓检测到的页尾
        else:
            page_bottom_crop = rh

        # 行间距 = 列间距（UI 设计假设）
        col_gap = (span_w - config.slot_w * config.cols) / (config.cols - 1)
        row_step = config.slot_h + col_gap

        # === 几何网格 + 双区域采样 ===
        # 1. 卡片主体：等级条上方区域，非白色=有圣遗物
        # 2. 等级条：底部白色文字条，白色=有圣遗物
        # 综合：两者都满足才判定为有效格子
        SAMPLE_MARGIN = 5
        SAMPLE_W = 10
        CARD_SAMPLE_ABOVE = 15  # 等级条上方采样偏移
        CARD_SAMPLE_H = 10      # 采样高度
        LVL_MARGIN = 3
        card_threshold = 180  # 卡片主体：圣遗物(~110) << 180 < 空格子(~223)
        bar_threshold = 220   # 等级条：220-227 vs 空格子背景 222-225

        # 采样阈值
        card_threshold = 180  # 卡片主体：圣遗物(~110) << 180 < 空格子(~223)
        bar_threshold = 220   # 等级条：220-227 vs 空格子背景 222-225

        slots: list[tuple[int, int, int, int, int, int]] = []
        for r in range(config.rows):
            row_bottom = int(page_bottom_crop - (config.rows - 1 - r) * row_step)
            level_top = max(0, row_bottom - config.level_h)
            level_bottom = min(rh, row_bottom)

            for c in range(config.cols):
                col_left = int(ref_left + c * col_step)
                col_right = col_left + config.slot_w

                lx1 = col_left + SAMPLE_MARGIN
                lx2 = col_left + SAMPLE_MARGIN + SAMPLE_W
                rx1 = col_right - SAMPLE_MARGIN - SAMPLE_W
                rx2 = col_right - SAMPLE_MARGIN
                # 区域1：卡片主体（等级条上方）
                ly1 = level_top - CARD_SAMPLE_ABOVE - CARD_SAMPLE_H
                ly2 = level_top - CARD_SAMPLE_ABOVE

                if lx1 < 0 or rx2 > gray.shape[1] or ly1 < 0 or ly2 > gray.shape[0]:
                    continue

                left_region = gray[ly1:ly2, lx1:lx2]
                right_region = gray[ly1:ly2, rx1:rx2]
                if left_region.size == 0 or right_region.size == 0:
                    continue

                card_left = float(np.mean(left_region))
                card_right = float(np.mean(right_region))
                card_mean = round(max(card_left, card_right))

                # 区域2：等级条
                bly1 = level_top + LVL_MARGIN
                bly2 = level_bottom - LVL_MARGIN

                if bly1 < 0 or bly2 > gray.shape[0]:
                    continue

                bar_left_region = gray[bly1:bly2, lx1:lx2]
                bar_right_region = gray[bly1:bly2, rx1:rx2]
                if bar_left_region.size == 0 or bar_right_region.size == 0:
                    continue

                bar_left = float(np.mean(bar_left_region))
                bar_right = float(np.mean(bar_right_region))
                bar_mean = round(max(bar_left, bar_right))

                # 综合判断：卡片非白色(有圣遗物图) AND 等级条白色(有等级文字)
                if card_mean < card_threshold and bar_mean >= bar_threshold:
                    sx = offset_x + col_left
                    sy = offset_y + (row_bottom - config.slot_h)
                    cx = sx + config.slot_w // 2
                    cy = sy + config.slot_h // 2
                    slots.append((cx, cy, sx, sy, config.slot_w, config.slot_h))

        bottom_y = offset_y + page_bottom_crop
        return DetectResult(slots, bottom_y)

    @staticmethod
    def draw_debug(
        image: np.ndarray,
        slots: list[tuple[int, int, int, int, int, int]],
        roi: tuple[int, int, int, int] | None = None,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
        page_bottom: int | None = None,
    ) -> np.ndarray:
        """在灰度图上绘制检测结果，返回 RGB 预览图。

        Args:
            page_bottom: 页尾Y坐标，用于粉色行线/蓝色采样点/红色页尾线计算。
                         为 None 时使用 ROI 底部。
        """
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
            # 行底部分隔线（粉色=预期行底部，以页尾为基准倒推）
            pg_bottom = page_bottom if page_bottom is not None else ry + rh
            col_gap = (span_w - config.slot_w * config.cols) / (config.cols - 1)
            row_step = config.slot_h + col_gap
            for r in range(config.rows):
                gy = int(pg_bottom - (config.rows - 1 - r) * row_step)
                cv2.line(debug, (rx, gy), (rx + rw, gy), (255, 0, 255), 1)
                cv2.putText(
                    debug, f"行{r}底", (rx + 2, gy - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 255), 1,
                )

            # 金色滑轨区域（动态计算）
            sr = config.slider_region()
            if sr is not None:
                sx, stop_y, sbot_y, sw, _sh = sr
                cv2.rectangle(debug, (sx, stop_y), (sx + sw, sbot_y), (0, 215, 255), 1)
                cv2.putText(
                    debug, "滑轨", (sx + sw + 4, (stop_y + sbot_y) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 215, 255), 1,
                )

            # 双区域采样点 + 调试值
            # 蓝色=卡片主体(非白色=有圣遗物) 青色=等级条(白色=有等级)
            # 绿=两条件都满足 红=至少一个不满足
            SAMPLE_MARGIN = 5
            SAMPLE_W = 10
            CARD_SAMPLE_ABOVE = 15
            CARD_SAMPLE_H = 10
            LVL_MARGIN = 3
            card_threshold = 180
            bar_threshold = 220
            pg_bottom = page_bottom if page_bottom is not None else ry + rh
            col_gap = (span_w - config.slot_w * config.cols) / (config.cols - 1)
            row_step = config.slot_h + col_gap
            col_step = (span_w - config.slot_w) / (config.cols - 1)
            for r in range(config.rows):
                row_bottom = int(pg_bottom - (config.rows - 1 - r) * row_step)
                level_top = max(ry, row_bottom - config.level_h)
                level_bottom = min(pg_bottom, row_bottom)
                for c in range(config.cols):
                    col_left = int(ref_left + c * col_step)
                    col_right = col_left + config.slot_w

                    # 采样 X 坐标
                    slx1 = col_left + SAMPLE_MARGIN
                    slx2 = col_left + SAMPLE_MARGIN + SAMPLE_W
                    srx1 = col_right - SAMPLE_MARGIN - SAMPLE_W
                    srx2 = col_right - SAMPLE_MARGIN

                    # 卡片主体采样
                    sly1 = level_top - CARD_SAMPLE_ABOVE - CARD_SAMPLE_H
                    sly2 = level_top - CARD_SAMPLE_ABOVE
                    sly = (sly1 + sly2) // 2

                    left_region = gray[sly1:sly2, slx1:slx2]
                    right_region = gray[sly1:sly2, srx1:srx2]
                    card_left = float(np.mean(left_region)) if left_region.size > 0 else 0
                    card_right = float(np.mean(right_region)) if right_region.size > 0 else 0
                    card_mean = round(max(card_left, card_right))
                    card_margin = card_mean - card_threshold

                # 等级条采样
                    bly1 = level_top + LVL_MARGIN
                    bly2 = level_bottom - LVL_MARGIN
                    bly = (bly1 + bly2) // 2

                    bar_left_region = gray[bly1:bly2, slx1:slx2]
                    bar_right_region = gray[bly1:bly2, srx1:srx2]
                    bar_left = float(np.mean(bar_left_region)) if bar_left_region.size > 0 else 0
                    bar_right = float(np.mean(bar_right_region)) if bar_right_region.size > 0 else 0
                    bar_mean = round(max(bar_left, bar_right))
                    bar_margin = bar_mean - bar_threshold

                # 蓝色圆点（卡片主体采样中心）
                    lx = col_left + SAMPLE_MARGIN + SAMPLE_W // 2
                    rx = col_right - SAMPLE_MARGIN - SAMPLE_W // 2
                    cv2.circle(debug, (lx, sly), 2, (255, 0, 0), -1)
                    cv2.circle(debug, (rx, sly), 2, (255, 0, 0), -1)

                    # 青色圆点（等级条采样中心）
                    cv2.circle(debug, (lx, bly), 2, (255, 255, 0), -1)
                    cv2.circle(debug, (rx, bly), 2, (255, 255, 0), -1)

                    # 综合判断：卡片非白色 AND 等级条白色
                    cv2.putText(
                        debug, f"c{card_mean:.0f}({card_margin:+.0f})",
                        (lx + 4, sly - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1,
                    )
                    # print(f"c{card_mean:.0f}({card_margin:+.0f})")

                    cv2.putText(
                        debug, f"b{bar_mean:.0f}({bar_margin:+.0f})",
                        (lx + 4, bly - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 0), 1,
                    )
                    # print(f"b{bar_mean:.0f}({bar_margin:+.0f})")

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

        if page_bottom is not None:
            cv2.line(
                debug, (0, page_bottom), (debug.shape[1], page_bottom), (0, 0, 255), 2
            )
        elif slots:
            last_bottom = max(s[3] + s[5] for s in slots)
            cv2.line(
                debug, (0, last_bottom), (debug.shape[1], last_bottom), (0, 0, 255), 2
            )

        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)