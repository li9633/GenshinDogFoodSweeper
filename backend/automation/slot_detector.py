"""
圣遗物格子检测器
================
基于灰度阈值 + 轮廓检测，自动定位圣遗物列表中的每个格子位置。
不依赖 Qt，可独立测试。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from utils.logger import log

from backend.models.slot_models import (
    ALL_RARITY_THRESHOLDS,  # noqa: F401
    ALL_SLOT_CONFIGS,  # noqa: F401
    BAG_SLOT_CONFIG,
    FIVE_STAR_GOLDEN,  # noqa: F401
    FOUR_STAR_PURPLE,  # noqa: F401
    ONE_STAR_GRAY,  # noqa: F401
    SALVAGE_SLOT_CONFIG,  # noqa: F401
    THREE_STAR_BLUE,  # noqa: F401
    TWO_STAR_GREEN,  # noqa: F401
    ArtifactRarity,  # noqa: F401
    DetectResult,
    RarityThreshold,  # noqa: F401
    SlotDebugInfo,
    SlotDetectorConfig,
    classify_rarity,
)


def _draw_chinese_text(
    img_bgr: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
    font_size: int = 14,
) -> np.ndarray:
    """用 PIL 在 BGR 图像上绘制中文文本（cv2.putText 不支持中文）。"""
    from PIL import Image, ImageDraw, ImageFont

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil_img)

    font = None
    for fp in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if Path(fp).exists():
            font = ImageFont.truetype(fp, font_size)
            break

    if font is None:
        font = ImageFont.load_default()

    draw.text((x, y), text, font=font, fill=color[::-1])
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


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
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

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
            ref_left + c * col_step + config.slot_w / 2 for c in range(config.cols)
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

        # === 几何网格 + 多特征融合投票 ===
        # 卡片主体：3特征投票（饱和度 + 灰度标准差 + 边缘密度）
        # 等级条：白色均值（保留原有逻辑）
        # 综合：卡片投票 >= 2 AND 等级条白色
        SAMPLE_MARGIN = 5
        SAMPLE_W = 10
        CARD_SAMPLE_ABOVE = 15
        CARD_SAMPLE_H = 10
        LVL_MARGIN = 3
        bar_threshold = 205

        # 多特征融合投票阈值
        SAT_THRESHOLD = 20  # HSV S通道：>20 表示有颜色（非灰色空格子）
        STD_THRESHOLD = 15  # 灰度标准差：>15 表示纹理丰富（非纯色背景）
        EDGE_THRESHOLD = 0.03  # 边缘密度：>3% 表示有图标轮廓

        slots: list[tuple[int, int, int, int, int, int]] = []
        debug_infos: list[SlotDebugInfo] = []
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
                # 卡片主体采样区域（等级条上方）
                ly1 = level_top - CARD_SAMPLE_ABOVE - CARD_SAMPLE_H
                ly2 = level_top - CARD_SAMPLE_ABOVE

                if lx1 < 0 or rx2 > gray.shape[1] or ly1 < 0 or ly2 > gray.shape[0]:
                    continue

                # 灰度区域
                card_l_gray = gray[ly1:ly2, lx1:lx2]
                card_r_gray = gray[ly1:ly2, rx1:rx2]
                # HSV S通道区域
                card_l_sat = hsv[ly1:ly2, lx1:lx2, 1]
                card_r_sat = hsv[ly1:ly2, rx1:rx2, 1]
                card_l_bgr = crop[ly1:ly2, lx1:lx2]
                card_r_bgr = crop[ly1:ly2, rx1:rx2]

                if card_l_gray.size == 0 or card_r_gray.size == 0:
                    continue

                # 特征1：饱和度均值（取左右中更饱和的）
                sat_l = float(np.mean(card_l_sat))
                sat_r = float(np.mean(card_r_sat))
                sat_val = max(sat_l, sat_r)

                # 特征2：灰度标准差（取左右中变化更大的）
                std_l = float(np.std(card_l_gray))
                std_r = float(np.std(card_r_gray))
                std_val = max(std_l, std_r)

                # 特征3：边缘密度（取左右中边缘更多的）
                edges_l = cv2.Canny(card_l_gray, 50, 150)
                edges_r = cv2.Canny(card_r_gray, 50, 150)
                edge_l = float(np.count_nonzero(edges_l)) / edges_l.size
                edge_r = float(np.count_nonzero(edges_r)) / edges_r.size
                edge_val = max(edge_l, edge_r)

                # 投票：至少2个特征认为"有圣遗物"
                votes = 0
                if sat_val > SAT_THRESHOLD:
                    votes += 1
                if std_val > STD_THRESHOLD:
                    votes += 1
                if edge_val > EDGE_THRESHOLD:
                    votes += 1

                # 卡片区域原始颜色（取左右两侧均值，避免图标位置偏移导致波动）
                gray_l = float(np.mean(card_l_gray))
                gray_r = float(np.mean(card_r_gray))
                card_gray_mean = (gray_l + gray_r) / 2
                bgr_l = np.mean(card_l_bgr, axis=(0, 1))
                bgr_r = np.mean(card_r_bgr, axis=(0, 1))
                card_bgr_mean = (bgr_l + bgr_r) / 2

                # 等级条检测（保留原有逻辑）
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

                # 综合判断：卡片投票 >= 2 AND 等级条白色
                if votes >= 1 and bar_mean >= bar_threshold:
                    sx = offset_x + col_left
                    sy = offset_y + (row_bottom - config.slot_h)
                    cx = sx + config.slot_w // 2
                    cy = sy + config.slot_h // 2
                    slots.append((cx, cy, sx, sy, config.slot_w, config.slot_h))

                debug_infos.append(SlotDebugInfo(
                    row=r, col=c,
                    lx=offset_x + col_left + SAMPLE_MARGIN + SAMPLE_W // 2,
                    rx=offset_x + col_right - SAMPLE_MARGIN - SAMPLE_W // 2,
                    sly=offset_y + (ly1 + ly2) // 2,
                    bly=offset_y + (bly1 + bly2) // 2,
                    sat_val=sat_val, std_val=std_val, edge_val=edge_val,
                    votes=votes, bar_mean=bar_mean,
                    bar_margin=bar_mean - bar_threshold,
                    card_gray=card_gray_mean,
                    card_b=int(card_bgr_mean[0]),
                    card_g=int(card_bgr_mean[1]),
                    card_r=int(card_bgr_mean[2]),
                    rarity=classify_rarity(
                        card_gray_mean, sat_val,
                        int(card_bgr_mean[0]), int(card_bgr_mean[1]), int(card_bgr_mean[2]),
                    ),
                ))

        bottom_y = offset_y + page_bottom_crop
        return DetectResult(slots, bottom_y, debug_infos)

    @staticmethod
    def draw_debug(
        image: np.ndarray,
        slots: list[tuple[int, int, int, int, int, int]],
        roi: tuple[int, int, int, int] | None = None,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
        page_bottom: int | None = None,
        debug_infos: list[SlotDebugInfo] | None = None,
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
                debug = _draw_chinese_text(
                    debug,
                    f"行{r}底",
                    rx + 2,
                    gy - 14,
                    (255, 0, 255),
                    font_size=14,
                )

            # 金色滑轨区域（动态计算）
            sr = config.slider_region()
            if sr is not None:
                sx, stop_y, sbot_y, sw, _sh = sr
                cv2.rectangle(debug, (sx, stop_y), (sx + sw, sbot_y), (0, 215, 255), 1)
                debug = _draw_chinese_text(
                    debug,
                    "滑轨",
                    sx + sw + 4,
                    (stop_y + sbot_y) // 2 - 8,
                    (0, 215, 255),
                    font_size=14,
                )

            # 多特征融合投票调试可视化（使用 detect() 预计算数据）
            if debug_infos:
                for info in debug_infos:
                    # 蓝色圆点（卡片主体采样中心）
                    cv2.circle(debug, (info.lx, info.sly), 2, (255, 0, 0), -1)
                    cv2.circle(debug, (info.rx, info.sly), 2, (255, 0, 0), -1)

                    # 青色圆点（等级条采样中心）
                    cv2.circle(debug, (info.lx, info.bly), 2, (255, 255, 0), -1)
                    cv2.circle(debug, (info.rx, info.bly), 2, (255, 255, 0), -1)

                    # 三特征值 + 投票（绿=通过 红=未通过）
                    vote_color = (0, 255, 0) if info.votes >= 1 else (0, 0, 255)
                    cv2.putText(
                        debug,
                        f"S{info.sat_val:.0f} D{info.std_val:.0f} E{info.edge_val * 100:.0f}% V{info.votes}/3",
                        (info.lx + 4, info.sly - 4),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        vote_color,
                        1,
                    )

                    # 等级条均值
                    cv2.putText(
                        debug,
                        f"b{info.bar_mean:.0f}({info.bar_margin:+.0f})",
                        (info.lx + 4, info.bly - 4),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        (255, 255, 0),
                        1,
                    )

                    # 原始像素值：灰度 + BGR + 稀有度
                    cv2.putText(
                        debug, f"G{info.card_gray:.0f} ({info.card_b},{info.card_g},{info.card_r}) R{info.rarity}",
                        (info.lx + 4, info.sly + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1,
                    )
                    log.debug(
                        f"[{info.row},{info.col}] "
                        f"S{info.sat_val:.0f} D{info.std_val:.0f} "
                        f"E{info.edge_val * 100:.0f}% V{info.votes}/3 "
                        f"b{info.bar_mean:.0f}({info.bar_margin:+.0f}) "
                        f"G{info.card_gray:.0f} ({info.card_b},{info.card_g},{info.card_r}) "
                        f"R{info.rarity}"
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