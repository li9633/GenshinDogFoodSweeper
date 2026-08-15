"""
圣遗物格子检测 — 数据模型
==========================
纯数据定义，与检测逻辑无关。包括：
- 稀有度枚举与颜色阈值
- 格子检测几何配置
- 检测结果与调试信息数据结构
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import NamedTuple


class ArtifactRarity(IntEnum):
    """圣遗物稀有度"""

    UNKNOWN = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


@dataclass(frozen=True)
class RarityThreshold:
    """单个稀有度的卡片颜色阈值范围。所有范围均为闭区间 [min, max]。"""

    rarity: ArtifactRarity
    gray_min: int
    gray_max: int
    sat_min: int
    sat_max: int
    b_min: int
    b_max: int
    g_min: int
    g_max: int
    r_min: int
    r_max: int

    def matches(self, card_gray: float, sat_val: float, b: int, g: int, r: int) -> bool:
        """检查给定的卡片颜色是否在此稀有度范围内。"""
        return (
            self.gray_min <= card_gray <= self.gray_max
            and self.sat_min <= sat_val <= self.sat_max
            and self.b_min <= b <= self.b_max
            and self.g_min <= g <= self.g_max
            and self.r_min <= r <= self.r_max
        )


# === 稀有度阈值（基于实测数据） ===

FIVE_STAR_GOLDEN = RarityThreshold(
    rarity=ArtifactRarity.FIVE,
    gray_min=90,
    gray_max=135,
    sat_min=25,
    sat_max=85,
    b_min=170,
    b_max=200,
    g_min=105,
    g_max=140,
    r_min=35,
    r_max=75,
)

# TODO: 待实测后补充具体阈值
FOUR_STAR_PURPLE = RarityThreshold(
    rarity=ArtifactRarity.FOUR,
    gray_min=0,
    gray_max=255,
    sat_min=0,
    sat_max=255,
    b_min=0,
    b_max=255,
    g_min=0,
    g_max=255,
    r_min=0,
    r_max=255,
)

THREE_STAR_BLUE = RarityThreshold(
    rarity=ArtifactRarity.THREE,
    gray_min=0,
    gray_max=255,
    sat_min=0,
    sat_max=255,
    b_min=0,
    b_max=255,
    g_min=0,
    g_max=255,
    r_min=0,
    r_max=255,
)

TWO_STAR_GREEN = RarityThreshold(
    rarity=ArtifactRarity.TWO,
    gray_min=0,
    gray_max=255,
    sat_min=0,
    sat_max=255,
    b_min=0,
    b_max=255,
    g_min=0,
    g_max=255,
    r_min=0,
    r_max=255,
)

ONE_STAR_GRAY = RarityThreshold(
    rarity=ArtifactRarity.ONE,
    gray_min=0,
    gray_max=255,
    sat_min=0,
    sat_max=255,
    b_min=0,
    b_max=255,
    g_min=0,
    g_max=255,
    r_min=0,
    r_max=255,
)

ALL_RARITY_THRESHOLDS: list[RarityThreshold] = [
    FIVE_STAR_GOLDEN,
    FOUR_STAR_PURPLE,
    THREE_STAR_BLUE,
    TWO_STAR_GREEN,
    ONE_STAR_GRAY,
]


def classify_rarity(
    card_gray: float,
    sat_val: float,
    card_b: int,
    card_g: int,
    card_r: int,
    thresholds: list[RarityThreshold] | None = None,
) -> ArtifactRarity:
    """根据卡片颜色特征判断圣遗物稀有度。

    按 thresholds 顺序匹配，返回第一个命中的稀有度。
    未命中任何阈值时返回 ArtifactRarity.UNKNOWN。
    """
    if thresholds is None:
        thresholds = ALL_RARITY_THRESHOLDS
    for t in thresholds:
        if t.matches(card_gray, sat_val, card_b, card_g, card_r):
            return t.rarity
    return ArtifactRarity.UNKNOWN


@dataclass
class SlotDebugInfo:
    """单个格子的调试信息，由 detect() 预计算，供 draw_debug() 直接渲染。"""

    row: int
    col: int
    lx: int  # 左采样点绝对 X
    rx: int  # 右采样点绝对 X
    sly: int  # 卡片采样绝对 Y
    bly: int  # 等级条采样绝对 Y
    sat_val: float
    std_val: float
    edge_val: float
    votes: int
    bar_mean: float
    bar_margin: float
    card_gray: float = 0.0  # 卡片区域灰度均值
    card_b: int = 0  # 卡片区域 B 通道均值
    card_g: int = 0  # 卡片区域 G 通道均值
    card_r: int = 0  # 卡片区域 R 通道均值
    rarity: ArtifactRarity = ArtifactRarity.UNKNOWN  # 稀有度分类结果


class DetectResult(NamedTuple):
    """格子检测结果。"""

    slots: list[tuple[int, int, int, int, int, int]]
    bottom_y: int  # 最后一行底部边缘的 Y 坐标
    debug_infos: list[SlotDebugInfo] = ()


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


# === 预定义配置实例 ===

# 背包圣遗物列表格子配置
BAG_SLOT_CONFIG = SlotDetectorConfig(name="背包圣遗物列表", roi=(118, 193, 1170, 810))

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