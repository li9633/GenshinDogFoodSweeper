"""
锚点定位器 — 纯逻辑层，无 Qt 依赖
===============================
基于首锚点位置和滑块Y坐标，动态定位尾锚点。
支持空格子检测、页数计算、圣遗物显示文本格式化。
"""

from __future__ import annotations

import cv2
import numpy as np
from models.artifact import ArtifactInfo


class AnchorLocator:
    """锚点定位器 — 纯函数，无状态，无 Qt 依赖"""

    # ---- 空格子检测 ----

    @staticmethod
    def is_empty_slot(cx: int, cy: int, img: np.ndarray) -> bool:
        """检测格子是否为空位（无物品）

        Args:
            cx, cy: 格子中心坐标（窗口相对）
            img: 屏幕截图（BGR或RGB格式）

        Returns:
            True 表示空格子
        """
        h, w = img.shape[:2]
        half = 10
        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w, cx + half)
        y2 = min(h, cy + half)

        if x2 <= x1 or y2 <= y1:
            return True

        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) if roi.ndim == 3 else roi
        mean_val = np.mean(gray)
        std_val = np.std(gray)
        return bool(mean_val < 60 and std_val < 15)

    # ---- 页数计算 ----

    @staticmethod
    def calculate_pages(
        anchor_first_y: int,
        anchor_last_y: int,
        item_h: int,
        gap: int,
        is_tail_center: bool = False,
    ) -> tuple[int, int]:
        """根据首尾锚点计算总行数和总页数

        Args:
            anchor_first_y: 首锚点Y坐标（格子左上角）
            anchor_last_y: 尾锚点Y坐标（格子中心或左上角）
            item_h: 格子高度
            gap: 格子间距
            is_tail_center: 尾锚点Y是否为格子中心（动态定位时为True）

        Returns:
            (total_rows, total_pages)
        """
        row_step = item_h + gap
        if row_step <= 0:
            return (0, 0)

        first_center_y = anchor_first_y + item_h // 2
        if is_tail_center:
            last_center_y = anchor_last_y
        else:
            last_center_y = anchor_last_y + item_h // 2

        total_rows = int((last_center_y - first_center_y) / row_step) + 1
        total_pages = max(1, (total_rows + 3) // 4)
        return (total_rows, total_pages)

    # ---- 显示格式化 ----

    @staticmethod
    def format_artifact_display(artifact: ArtifactInfo) -> list[str]:
        """将 ArtifactInfo 格式化为简洁的显示文本行"""
        lines: list[str] = []

        if artifact.is_material:
            lines.append("【强化材料】")
            if artifact.material_name:
                lines.append(f"名称: {artifact.material_name}")
            if artifact.rarity is not None:
                lines.append(f"星级: {artifact.rarity}★")
            return lines

        if artifact.set_name:
            lines.append(f"套装: {artifact.set_name}")
        if artifact.piece_name:
            lines.append(f"名称: {artifact.piece_name}")
        if artifact.piece_type:
            lines.append(f"部位: {artifact.piece_type}")
        if artifact.rarity is not None:
            lines.append(f"星级: {artifact.rarity}★")
        if artifact.level is not None:
            lines.append(f"等级: +{artifact.level}")
        if artifact.main_stat:
            ms = artifact.main_stat
            pct = "%" if ms.is_percentage else ""
            lines.append(f"主词条: {ms.name} +{ms.value}{pct}")
        if artifact.sub_stats:
            lines.append("副词条:")
            for ss in artifact.sub_stats:
                pct = "%" if ss.is_percentage else ""
                lock = " (待激活)" if ss.is_locked else ""
                lines.append(f"  • {ss.name} +{ss.value}{pct}{lock}")
        else:
            lines.append("副词条: 未识别")
        return lines

    @staticmethod
    def format_artifact_short(artifact: ArtifactInfo) -> str:
        """格式化圣遗物为单行简短描述"""
        if artifact.is_material:
            name = artifact.material_name or "强化材料"
            star = f"{artifact.rarity}★" if artifact.rarity else ""
            return f"[{star} {name}]"

        parts: list[str] = []
        if artifact.rarity:
            parts.append(f"{artifact.rarity}★")
        if artifact.set_name:
            parts.append(artifact.set_name)
        if artifact.piece_name:
            parts.append(artifact.piece_name)
        if artifact.level is not None:
            parts.append(f"+{artifact.level}")
        if artifact.main_stat:
            ms = artifact.main_stat
            pct = "%" if ms.is_percentage else ""
            parts.append(f"{ms.name}+{ms.value}{pct}")
        return " | ".join(parts)