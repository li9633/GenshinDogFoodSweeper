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
    ArtifactRarity,
    DetectResult,
    RarityThreshold,  # noqa: F401
    SlotDebugInfo,
    SlotDetectorConfig,
    SlotObject,
    classify_rarity,
    star_count_to_rarity,
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

    几何计算统一入口 _compute_grid()：detect() 和 draw_debug() 共用同一套公式，
    确保预览图中的辅助线与实际采样位置 100% 一致。
    """

    @staticmethod
    def _compute_grid(
        roi: tuple[int, int, int, int],
        config: SlotDetectorConfig,
        page_bottom: int,
    ) -> tuple[list[int], list[int], list[int], float, float]:
        """计算几何网格位置（detect / draw_debug 共用，唯一计算入口）。

        Args:
            roi: (rx, ry, rw, rh) ROI 区域，图像坐标
            config: 检测配置
            page_bottom: 页尾 Y 坐标，图像坐标

        Returns:
            (col_lefts, col_rights, row_bottoms, col_step, row_step)
            所有坐标均为图像坐标。
        """
        rx, _ry, rw, _rh = roi
        ref_left = rx + config.roi_left_offset
        span_w = rw - config.roi_left_offset - config.roi_right_offset

        col_gap = (span_w - config.slot_w * config.cols) / (config.cols - 1)
        col_step = (span_w - config.slot_w) / (config.cols - 1)
        row_step = config.slot_h + col_gap

        col_lefts = [int(ref_left + c * col_step) for c in range(config.cols)]
        col_rights = [cl + config.slot_w for cl in col_lefts]
        row_bottoms = [
            int(page_bottom - (config.rows - 1 - r) * row_step)
            for r in range(config.rows)
        ]

        return col_lefts, col_rights, row_bottoms, col_step, row_step

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

        # 列位置（几何计算，用于轮廓匹配）
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

        # 统一几何网格（与 draw_debug 共用 _compute_grid，确保预览线=采样位置）
        col_lefts_img, col_rights_img, row_bottoms_img, _, _ = SlotDetector._compute_grid(
            (rx, ry, rw, rh), config, ry + page_bottom_crop
        )

        # === 几何网格 + 多特征融合投票 ===
        # 卡片主体：3特征投票（饱和度 + 灰度标准差 + 边缘密度）
        # 等级条：白色均值（保留原有逻辑）
        # 综合：卡片投票 >= 1 AND 等级条白色
        SAMPLE_MARGIN = 1
        SAMPLE_W = 10
        CARD_SAMPLE_ABOVE = 15
        CARD_SAMPLE_H = 10
        LVL_MARGIN = 1

        # 多特征融合投票阈值（从 config 读取，可通过 SlotDetectorConfig 调参）
        sat_threshold = config.sat_threshold
        std_threshold = config.std_threshold
        edge_threshold = config.edge_threshold
        bar_threshold = config.bar_threshold

        slots: list[tuple[int, int, int, int, int, int]] = []
        debug_infos: list[SlotDebugInfo] = []
        for r in range(config.rows):
            row_bottom = row_bottoms_img[r] - ry  # 图像坐标 → crop 坐标
            level_top = max(0, row_bottom - config.level_h)
            level_bottom = min(rh, row_bottom)

            for c in range(config.cols):
                col_left = col_lefts_img[c] - rx  # 图像坐标 → crop 坐标
                col_right = col_rights_img[c] - rx

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

                # S/D/E 特征独立判断
                sat_pass = sat_val > sat_threshold
                std_pass = std_val > std_threshold
                edge_pass = edge_val > edge_threshold

                # 卡片区域原始颜色（取左右两侧均值，避免图标位置偏移导致波动）
                gray_l = float(np.mean(card_l_gray))
                gray_r = float(np.mean(card_r_gray))
                card_gray_mean = (gray_l + gray_r) / 2
                bgr_l = np.mean(card_l_bgr, axis=(0, 1))
                bgr_r = np.mean(card_r_bgr, axis=(0, 1))
                card_bgr_mean = (bgr_l + bgr_r) / 2

                # H 通道（色相）— 混色下最稳定的颜色特征
                card_l_hue = hsv[ly1:ly2, lx1:lx2, 0]
                card_r_hue = hsv[ly1:ly2, rx1:rx2, 0]
                hue_l = float(np.mean(card_l_hue))
                hue_r = float(np.mean(card_r_hue))
                hue_val = (hue_l + hue_r) / 2

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

                # 星级扫描：中心优先分支策略（中间有星→1/3/5星，无星→2/4星，gap递推左右采样）
                STAR_SAMPLE_W = 4
                STAR_SAMPLE_H = 5
                star_y = row_bottom - config.star_offset_y
                star_y1 = max(0, star_y - STAR_SAMPLE_H // 2)
                star_y2 = min(gray.shape[0], star_y + STAR_SAMPLE_H // 2)
                center_x = (col_left + col_right) // 2

                # 1. 检测中心星（判断奇偶模式）
                center_sx = center_x - STAR_SAMPLE_W // 2
                center_region = gray[star_y1:star_y2, center_sx:center_sx + STAR_SAMPLE_W]
                center_gray = float(np.mean(center_region)) if center_region.size > 0 else 0.0
                has_center_star = abs(center_gray - config.star_gray_target) <= config.star_gray_tolerance

                # 2. 分支采样（1/3/5星 vs 2/4星）
                star_sample_xs: list[int] = []
                star_matches = 0
                if has_center_star:
                    offsets = [0, -1, 1, -2, 2]  # 中心, 左1, 右1, 左2, 右2 (最多5星)
                else:
                    offsets = [-1.5, -0.5, 0.5, 1.5]  # 居中连续排列 (最多4星)

                for offset in offsets:
                    sx = int(center_x + offset * config.star_gap - STAR_SAMPLE_W // 2)
                    if sx < col_left or sx + STAR_SAMPLE_W > col_right:
                        continue
                    region = gray[star_y1:star_y2, sx:sx + STAR_SAMPLE_W]
                    g = float(np.mean(region)) if region.size > 0 else 0.0
                    star_sample_xs.append(offset_x + sx + STAR_SAMPLE_W // 2)
                    if abs(g - config.star_gray_target) <= config.star_gray_tolerance:
                        star_matches += 1

                star_pass = star_matches >= 1

                # 等级条白色特征 + 汇总投票（5维：S/D/E/B/Star，Star为必要条件）
                bar_pass = bar_mean >= bar_threshold
                votes = sum([sat_pass, std_pass, edge_pass, bar_pass, star_pass])

                # 综合判断：星星检测为主（50%权重），等级条为辅
                # 空格子天然无星星，无需card_bar_diff辅助判断
                slot_occupied = star_pass and bar_pass

                # 星级降级机制：颜色分类与星星计数一致则直接采用，否则降级为星星检测
                if slot_occupied:
                    color_rarity = classify_rarity(
                        card_gray_mean, sat_val,
                        int(card_bgr_mean[0]), int(card_bgr_mean[1]), int(card_bgr_mean[2]),
                        hue_val=hue_val,
                    )
                    star_rarity = star_count_to_rarity(star_matches)
                    final_rarity = color_rarity if color_rarity == star_rarity else star_rarity
                else:
                    color_rarity = ArtifactRarity.UNKNOWN
                    final_rarity = ArtifactRarity.UNKNOWN

                # 格子坐标（窗口相对）
                sx = offset_x + col_left
                sy = offset_y + (row_bottom - config.slot_h)

                # 锁定图标检测：锁位于圣遗物图标左上角，单点采样
                lock_x = sx + config.lock_offset_x
                lock_y = sy + config.lock_offset_y
                lock_px = lock_x - offset_x
                lock_py = lock_y - offset_y
                lock_gray_mean = float(gray[lock_py, lock_px]) if 0 <= lock_px < gray.shape[1] and 0 <= lock_py < gray.shape[0] else 0.0
                lock_pass = lock_gray_mean >= config.lock_gray_threshold

                if star_pass and bar_pass:
                    cx = sx + config.slot_w // 2
                    cy = sy + config.slot_h // 2
                    slots.append(SlotObject(
                        cx=cx, cy=cy, x=sx, y=sy, w=config.slot_w, h=config.slot_h,
                        rarity=final_rarity,
                        star_count=star_matches,
                        locked=lock_pass,
                        row=r, col=c,
                    ))

                debug_infos.append(SlotDebugInfo(
                    row=r, col=c,
                    lx=offset_x + col_left + SAMPLE_MARGIN + SAMPLE_W // 2,
                    rx=offset_x + col_right - SAMPLE_MARGIN - SAMPLE_W // 2,
                    sly=offset_y + (ly1 + ly2) // 2,
                    bly=offset_y + (bly1 + bly2) // 2,
                    sat_val=sat_val, std_val=std_val, edge_val=edge_val,
                    votes=votes, bar_mean=bar_mean,
                    bar_margin=bar_mean - bar_threshold,
                    hue_val=hue_val,
                    sat_pass=sat_pass, std_pass=std_pass, edge_pass=edge_pass,
                    bar_pass=bar_pass,
                    card_gray=card_gray_mean,
                    card_b=int(card_bgr_mean[0]),
                    card_g=int(card_bgr_mean[1]),
                    card_r=int(card_bgr_mean[2]),
                    rarity=color_rarity,
                    star_sample_xs=star_sample_xs,
                    star_sample_y=offset_y + star_y,
                    has_center_star=has_center_star,
                    star_matches=star_matches,
                    star_pass=star_pass,
                    lock_x=lock_x, lock_y=lock_y,
                    lock_gray_mean=lock_gray_mean, lock_pass=lock_pass,
                ))

        bottom_y = offset_y + page_bottom_crop

        # 计算行高（相邻行底部Y差值）
        row_bottoms = tuple(float(row_bottoms_img[r]) for r in range(config.rows))
        if config.rows >= 2:
            heights = [row_bottoms[i + 1] - row_bottoms[i] for i in range(config.rows - 1)]
            row_height = int(np.mean(heights))
        else:
            row_height = 0

        return DetectResult(slots, bottom_y, debug_infos, row_height, row_bottoms)

    @staticmethod
    def draw_debug(
        image: np.ndarray,
        slots: list[SlotObject],
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

            # 每列左右边框竖线 + 行底部分隔线（统一使用 _compute_grid，与 detect 一致）
            pg_bottom = page_bottom if page_bottom is not None else ry + rh
            col_lefts, col_rights, row_bottoms, _, _ = SlotDetector._compute_grid(
                (rx, ry, rw, rh), config, pg_bottom
            )
            for c in range(config.cols):
                cv2.line(debug, (col_lefts[c], ry), (col_lefts[c], ry + rh), (255, 0, 0), 1)
                cv2.line(debug, (col_rights[c], ry), (col_rights[c], ry + rh), (0, 0, 255), 1)
            for r in range(config.rows):
                gy = row_bottoms[r]
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

                    # 金色圆点（每颗星星采样位置，实心=通过，空心=未通过）
                    for sx in info.star_sample_xs:
                        cv2.circle(
                            debug, (sx, info.star_sample_y), 3, (0, 215, 255), -1
                        )

                    # 锁图标检测（蓝色=锁定，黄色=未锁，单像素点）
                    lock_color = (255, 0, 0) if info.lock_pass else (0, 255, 255)
                    if 0 <= info.lock_y < debug.shape[0] and 0 <= info.lock_x < debug.shape[1]:
                        debug[info.lock_y, info.lock_x] = lock_color
                    cv2.putText(
                        debug,
                        f"L{info.lock_gray_mean:.0f}",
                        (info.lock_x + 8, info.lock_y + 4),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        lock_color,
                        1,
                    )

                    # 三特征值 + 投票（绿=通过 红=未通过）
                    vote_color = (0, 255, 0) if info.votes >= 1 else (0, 0, 255)
                    cv2.putText(
                        debug,
                        f"S{info.sat_val:.0f} D{info.std_val:.0f} E{info.edge_val * 100:.0f}% V{info.votes}/5",
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

                    # 星级扫描结果（金色=通过，暗金=未通过）
                    star_color = (0, 215, 255) if info.star_pass else (0, 140, 255)
                    pattern = "奇" if info.has_center_star else "偶"
                    text_x = info.star_sample_xs[0] + 6 if info.star_sample_xs else info.lx
                    cv2.putText(
                        debug,
                        f"★{info.star_matches} {pattern}",
                        (text_x, info.star_sample_y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        star_color,
                        1,
                    )

                    # 原始像素值：灰度 + BGR + H + 稀有度
                    cv2.putText(
                        debug, f"G{info.card_gray:.0f} ({info.card_b},{info.card_g},{info.card_r}) H{info.hue_val:.0f} R{info.rarity}",
                        (info.lx + 4, info.sly + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1,
                    )
                    log.debug(
                        f"#{info.row * config.cols + info.col + 1} [{info.row},{info.col}] "
                        f"S{info.sat_val:.0f}{'✓' if info.sat_pass else '✗'}"
                        f" D{info.std_val:.0f}{'✓' if info.std_pass else '✗'}"
                        f" E{info.edge_val * 100:.0f}%{'✓' if info.edge_pass else '✗'}"
                        f" B{info.bar_mean:.0f}{'✓' if info.bar_pass else '✗'}"
                        f" ★{info.star_matches}/5 C{'✓' if info.has_center_star else '✗'}{'✓' if info.star_pass else '✗'}"
                        f" V{info.votes}/5 "
                        f"Δ{info.bar_mean - info.card_gray:.0f} "
                        f"G{info.card_gray:.0f} ({info.card_b},{info.card_g},{info.card_r}) "
                        f"H{info.hue_val:.0f} "
                        f"R{info.rarity}"
                        f" {'LOCK' if info.lock_pass else 'UNLOCK'}"
                    )

        for i, slot in enumerate(slots):
            cv2.rectangle(debug, (slot.x, slot.y), (slot.x + slot.w, slot.y + slot.h), (0, 255, 0), 2)
            cv2.putText(
                debug,
                str(i + 1),
                (slot.cx - 12, slot.cy + 8),
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
            last_bottom = max(s.y + s.h for s in slots)
            cv2.line(
                debug, (0, last_bottom), (debug.shape[1], last_bottom), (0, 0, 255), 2
            )

        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)

    @staticmethod
    def generate_row_height_debug(
        image: np.ndarray,
        result: DetectResult,
        roi: tuple[int, int, int, int] | None = None,
        config: SlotDetectorConfig = BAG_SLOT_CONFIG,
    ) -> np.ndarray:
        """在图像上画行分割线和行高标注，返回 RGB 预览图。

        Args:
            image: 原始 BGR 截图
            result: detect() 返回的检测结果
            roi: 检测区域
            config: 配置

        Returns:
            RGB 格式的调试预览图
        """
        debug = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        if roi is None:
            roi = config.roi
        if roi is None:
            return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)
        rx, ry, rw, rh = roi

        for i, y in enumerate(result.row_bottoms):
            y_int = int(y)
            cv2.line(debug, (rx, y_int), (rx + rw, y_int), (0, 255, 255), 2)
            cv2.putText(
                debug, f"R{i}", (rx + 5, y_int - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1,
            )
            if i < len(result.row_bottoms) - 1:
                next_y = int(result.row_bottoms[i + 1])
                mid_x = rx + rw - 40
                cv2.arrowedLine(
                    debug, (mid_x, y_int), (mid_x, next_y),
                    (0, 255, 0), 2, tipLength=0.15,
                )
                gap = next_y - y_int
                cv2.putText(
                    debug, f"{gap}px", (mid_x + 5, (y_int + next_y) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1,
                )

        cv2.putText(
            debug,
            f"Row Height: {result.row_height}px  |  Rows: {config.rows}",
            (rx + 5, ry + rh - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2,
        )
        return cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)