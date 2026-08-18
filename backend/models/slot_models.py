"""
圣遗物格子检测 — 数据模型
==========================
纯数据定义，与检测逻辑无关。包括：
- 稀有度枚举与颜色阈值
- 格子检测几何配置
- 检测结果与调试信息数据结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """单个稀有度的卡片颜色阈值范围。所有范围均为闭区间 [min, max]。

    H 通道（色相，OpenCV 0-180 范围）是最稳定的颜色特征，
    半透明背景混色对其影响远小于饱和度/明度。
    """

    rarity: ArtifactRarity
    h_min: int  # 色相最小值（OpenCV 0-180）
    h_max: int  # 色相最大值（OpenCV 0-180）
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

    def matches(
        self,
        card_gray: float,
        sat_val: float,
        b: int,
        g: int,
        r: int,
        hue_val: float = 0.0,
        require_hue: bool = True,
        min_votes: int = 4,
        sat_guard: int = 20,
    ) -> bool:
        """检查给定的卡片颜色是否在此稀有度范围内。

        H 通道强制匹配（半透明背景下色相最稳定），但低饱和度（<sat_guard）
        时 H 不可靠，自动跳过 H 强制匹配且 H 不参与投票。
        6 维投票（含 H），达到 min_votes 票即匹配。
        """
        hue_reliable = sat_val >= sat_guard
        effective_require_hue = require_hue and hue_reliable
        if effective_require_hue and not (self.h_min <= hue_val <= self.h_max):
            return False
        votes = sum(
            [
                hue_reliable and self.h_min <= hue_val <= self.h_max,
                self.gray_min <= card_gray <= self.gray_max,
                self.sat_min <= sat_val <= self.sat_max,
                self.b_min <= b <= self.b_max,
                self.g_min <= g <= self.g_max,
                self.r_min <= r <= self.r_max,
            ]
        )
        return votes >= min_votes


# === 稀有度阈值（基于实测数据） ===

FIVE_STAR_GOLDEN = RarityThreshold(
    rarity=ArtifactRarity.FIVE,
    h_min=90,
    h_max=120,
    gray_min=85,
    gray_max=140,
    sat_min=150,
    sat_max=225,
    b_min=160,
    b_max=225,
    g_min=95,
    g_max=150,
    r_min=25,
    r_max=85,
)

FOUR_STAR_PURPLE = RarityThreshold(
    rarity=ArtifactRarity.FOUR,
    h_min=150,
    h_max=180,
    gray_min=125,
    gray_max=165,
    sat_min=60,
    sat_max=125,
    b_min=125,
    b_max=180,
    g_min=95,
    g_max=145,
    r_min=155,
    r_max=215,
)

THREE_STAR_BLUE = RarityThreshold(
    rarity=ArtifactRarity.THREE,
    h_min=5,
    h_max=30,
    gray_min=120,
    gray_max=165,
    sat_min=85,
    sat_max=155,
    b_min=65,
    b_max=115,
    g_min=115,
    g_max=165,
    r_min=145,
    r_max=200,
)

TWO_STAR_GREEN = RarityThreshold(
    rarity=ArtifactRarity.TWO,
    h_min=30,
    h_max=60,
    gray_min=115,
    gray_max=150,
    sat_min=80,
    sat_max=120,
    b_min=70,
    b_max=110,
    g_min=125,
    g_max=165,
    r_min=100,
    r_max=145,
)

ONE_STAR_GRAY = RarityThreshold(
    rarity=ArtifactRarity.ONE,
    h_min=0,
    h_max=180,
    gray_min=115,
    gray_max=160,
    sat_min=0,
    sat_max=30,
    b_min=110,
    b_max=160,
    g_min=110,
    g_max=155,
    r_min=110,
    r_max=160,
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
    hue_val: float = 0.0,
    thresholds: list[RarityThreshold] | None = None,
    min_votes: int = 4,
) -> ArtifactRarity:
    """根据卡片颜色特征判断圣遗物稀有度。

    按 thresholds 顺序匹配，返回第一个命中的稀有度。
    使用投票制（默认 ≥4/6），H 通道在混色下最稳定，低饱和度时自动跳过 H。
    未命中任何阈值时返回 ArtifactRarity.UNKNOWN。
    """
    if thresholds is None:
        thresholds = ALL_RARITY_THRESHOLDS
    for t in thresholds:
        if t.matches(
            card_gray,
            sat_val,
            card_b,
            card_g,
            card_r,
            hue_val=hue_val,
            require_hue=True,
            min_votes=min_votes,
        ):
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
    hue_val: float = 0.0  # 卡片区域 H 通道均值（OpenCV 0-180）
    sat_pass: bool = False  # 饱和度特征是否通过
    std_pass: bool = False  # 灰度标准差特征是否通过
    edge_pass: bool = False  # 边缘密度特征是否通过
    bar_pass: bool = False  # 等级条白色特征是否通过
    card_gray: float = 0.0  # 卡片区域灰度均值
    card_b: int = 0  # 卡片区域 B 通道均值
    card_g: int = 0  # 卡片区域 G 通道均值
    card_r: int = 0  # 卡片区域 R 通道均值
    rarity: ArtifactRarity = ArtifactRarity.UNKNOWN  # 稀有度分类结果
    # 星级采样（中心优先分支：中间有星→奇数列1/3/5星，无星→偶数列2/4星）
    star_sample_xs: list[int] = field(default_factory=list)  # 每颗星星采样中心绝对X坐标列表
    star_sample_y: int = 0  # 星级采样线绝对Y坐标
    has_center_star: bool = False  # 中心是否有星星（决定奇偶分支）
    star_matches: int = 0  # 匹配星星颜色的采样点数
    star_pass: bool = False  # 星级特征是否通过


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
    # 多特征融合投票阈值
    sat_threshold: int = 10  # 饱和度阈值：>此值认为有颜色
    std_threshold: int = 15  # 灰度标准差阈值：>此值认为纹理丰富
    edge_threshold: float = 0.03  # 边缘密度阈值：>此值认为有图标轮廓
    bar_threshold: int = 210  # 等级条白色均值阈值：真实≥222，选中scale变暗≈214，半透明背景≤215
    # 星级扫描参数（中心优先：中间有星→1/3/5星，无星→2/4星，gap递推左右采样）
    star_offset_y: int = 33  # 格子底部边缘到星级扫描线的垂直偏移（向上）
    star_gap: int = 19  # 相邻星星之间的间距
    star_gray_target: int = 164  # 星星灰度目标值 (#A4A4A4)
    star_gray_tolerance: int = 8  # 星星灰度容差 (±8)
    # 圣遗物详情弹窗 ROI（相对于游戏窗口，用于 OCR 识别）
    detail_roi_configs: dict[str, tuple[int, int, int, int]] = field(
        default_factory=lambda: {
            "圣遗物星级": (1742, 159, 39, 40),
            "圣遗物名称": (1329, 144, 262, 62),
            "部位+主词条": (1339, 214, 160, 174),
        }
    )
    # 锁定图标锚点定位（用于兼容自定义圣遗物等 flex 布局变化）
    # 搜索区域默认从 TemplateManager 获取（templates.json），仅需覆盖时配置
    # 优先匹配解锁状态，失败再匹配锁定状态
    lock_anchor_search_region: tuple[int, int, int, int] | None = None
    lock_anchor_to_level: tuple[int, int, int, int] | None = None  # 锁图标→等级 (dx, dy, dw, dh)，flex同行dy≈0
    lock_anchor_to_sub_stats: tuple[int, int, int, int] | None = None  # 等级→副词条 (dx, dy, dw, dh)，相对等级区域

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
BAG_SLOT_CONFIG = SlotDetectorConfig(
    name="背包圣遗物列表",
    roi=(118, 193, 1170, 810),
    # 锁定图标→等级/副词条 offset（锁定图标与等级flex同行，；副词条从等级向下偏移）
    lock_anchor_to_level=(-340, 8, 71, 44),
    lock_anchor_to_sub_stats=(9, 46, 455, 166),
)

# 分解页面格子配置（详情弹窗 ROI 待校准，当前沿用背包页默认值）
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
    # 分解页面的详情弹窗 ROI 坐标（锁定状态已改用模板管理器定位）
    detail_roi_configs={
        "圣遗物星级": (1825, 163, 25, 33),
        "圣遗物名称": (1379, 158, 440, 41),
        "部位+主词条": (1368, 212, 214, 170),
    },
    # 锁定图标搜索区域（分解页弹窗右移，实测坐标）
    lock_anchor_search_region=(1750, 440, 123, 160),
    # 锁定图标→等级/副词条 offset（分解页弹窗位置不同；副词条从等级计算）
    lock_anchor_to_level=(-375, 8,71, 44),
    lock_anchor_to_sub_stats=(9, 46, 455, 166),
)

# 所有可用配置列表（调试面板下拉切换用）
ALL_SLOT_CONFIGS: list[SlotDetectorConfig] = [BAG_SLOT_CONFIG, SALVAGE_SLOT_CONFIG]