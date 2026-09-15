"""圣遗物扫描的数据模型
====================
纯枚举 + 纯数据，不依赖 Qt、不依赖 IO，扫描层与表现层共用。

扫描模板（``SlotDetectorConfig``）的几何细节全部封装在 :class:`FullScanRequest` 内：
调用方只需给一个模板配置和几个策略参数，不必逐项解包 roi / slot_w / gap 之类的细节。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from backend.models.slot_models import SlotDetectorConfig


class StopMode(StrEnum):
    """扫描停止模式（取值与 settings 的 ``scan.stop_mode`` 一致）"""

    ANCHOR = "anchor"  # 首尾锚点定位：识别到尾锚点（强化材料）即停
    FIVE_STAR_ONLY = "five_star_only"  # 只认五星，扫完整个背包
    FIXED_COUNT = "fixed_count"  # 扫够指定件数即停

    @classmethod
    def parse(cls, value: str | None) -> StopMode:
        """宽松解析：空值/未知取值回退 ANCHOR（配置过期不应该让扫描失败）"""
        if not value:
            return cls.ANCHOR
        try:
            return cls(value)
        except ValueError:
            return cls.ANCHOR

    @property
    def label(self) -> str:
        """下拉框文案（选项文案与顺序由 Presenter 统一提供，QML 不再各写一份）"""
        return _STOP_MODE_LABELS[self]


_STOP_MODE_LABELS: dict[StopMode, str] = {
    StopMode.ANCHOR: "首尾锚点定位",
    StopMode.FIVE_STAR_ONLY: "仅扫描五星",
    StopMode.FIXED_COUNT: "固定扫描数量",
}


class StopReason(StrEnum):
    """扫描结束原因（会写入保存文件，取值需保持稳定）"""

    COMPLETED = "completed"  # 扫完所有页
    TAIL_ANCHOR = "tail_anchor"  # 命中尾锚点
    FIXED_COUNT = "fixed_count"  # 达到固定数量
    BAG_COUNT = "bag_count"  # 达到背包总数量
    USER_STOP = "user_stop"  # 用户停止 / 热键终止

    @property
    def label(self) -> str:
        """用户可读文案（日志与界面共用）"""
        return _STOP_REASON_LABELS[self]


_STOP_REASON_LABELS: dict[StopReason, str] = {
    StopReason.COMPLETED: "扫描完成",
    StopReason.TAIL_ANCHOR: "命中尾锚点",
    StopReason.FIXED_COUNT: "已达固定数量",
    StopReason.BAG_COUNT: "已达背包数量",
    StopReason.USER_STOP: "已手动停止",
}


@dataclass(frozen=True)
class FullScanRequest:
    """一次全量扫描的全部输入

    模板几何、时序参数都收在这里（默认值即当前实测值），
    表现层构造请求时不需要知道这些细节。
    """

    slot_config: SlotDetectorConfig
    engines_dir: Path
    stop_mode: StopMode = StopMode.ANCHOR
    fixed_count: int = 0  # 仅 FIXED_COUNT 模式有效，<=0 表示不限制
    dedup_enabled: bool = True  # 仅「只认五星」模式下生效

    # 时序参数
    detail_settle_s: float = 0.15  # 点击后等待详情面板刷新
    tick_delay_ms: int = 30  # 翻页拖动滑块的步进间隔
    page_settle_ms: int = 200  # 翻页后等待列表稳定

    @classmethod
    def from_slot_config(
        cls,
        slot_config: SlotDetectorConfig,
        *,
        engines_dir: Path,
        stop_mode: StopMode = StopMode.ANCHOR,
        fixed_count: int = 0,
        dedup_enabled: bool = True,
    ) -> FullScanRequest:
        """由扫描模板构造请求（模板缺 ROI 时立即报错，而不是扫到一半才发现）"""
        if slot_config.roi is None:
            raise ValueError(
                f"扫描模板 {slot_config.name!r} 未配置 roi，无法定位锚点与滑轨"
            )
        return cls(
            slot_config=slot_config,
            engines_dir=engines_dir,
            stop_mode=stop_mode,
            fixed_count=fixed_count,
            dedup_enabled=dedup_enabled,
        )

    @property
    def anchor_first_center(self) -> tuple[int, int]:
        """首锚点坐标 = 模板 ROI 左上角格子的中心"""
        roi = self.slot_config.roi
        if roi is None:  # from_slot_config 已拦截，直接构造时兜底
            raise ValueError(f"扫描模板 {self.slot_config.name!r} 未配置 roi")
        return (
            roi[0] + self.slot_config.slot_w // 2,
            roi[1] + self.slot_config.slot_h // 2,
        )


@dataclass(frozen=True)
class ScanMeta:
    """一次扫描的上下文信息（不含具体圣遗物数据）"""

    started_at: datetime
    finished_at: datetime
    scanned: int  # 实际识别到的件数
    total_pages: int
    stop_mode: StopMode
    stopped_by: StopReason
    slot_config_name: str
    bag_count: int | None = None  # OCR 识别到的背包数量；None = 该模板不显示数量
    dedup_skipped: int = 0  # 因去重被跳过的件数

    @property
    def duration_ms(self) -> int:
        """扫描耗时（毫秒），由起止时间推导，避免各调用方各算各的"""
        return max(0, int((self.finished_at - self.started_at).total_seconds() * 1000))
