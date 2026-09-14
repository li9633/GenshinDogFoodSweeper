"""扫描停止策略 —— 停止条件判断的唯一出处
========================================
这些判断原先散落在 ``FullScanWorker.run()`` 与 ``on_slot`` 闭包里，
并且在循环中反复从 settings 现读，既难读也难测。现在收敛为不可变策略对象：
扫描开始时由请求快照一次，之后只做纯判断。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.models.artifact import ArtifactInfo
from backend.models.scan_models import StopMode, StopReason
from backend.models.slot_models import ArtifactRarity, SlotObject


@dataclass(frozen=True)
class StopPolicy:
    """一次扫描的停止策略（不可变）"""

    mode: StopMode = StopMode.ANCHOR
    fixed_count: int = 0  # 仅 FIXED_COUNT 模式有效，<=0 表示不限制
    dedup_enabled: bool = True  # 仅 FIVE_STAR_ONLY 模式生效

    @property
    def uses_anchor(self) -> bool:
        """是否需要先定位首尾锚点"""
        return self.mode is StopMode.ANCHOR

    @property
    def only_five_star(self) -> bool:
        return self.mode is StopMode.FIVE_STAR_ONLY

    def slot_pre_filter(self) -> Callable[[SlotObject], bool] | None:
        """点击前的格子预筛

        「只认五星」模式下先按格子星级跳过非五星，省下一次点击 + OCR。
        """
        if not self.only_five_star:
            return None
        return lambda slot: slot.rarity == ArtifactRarity.FIVE

    def accepts(self, info: ArtifactInfo) -> bool:
        """识别结果是否计入结果集（「只认五星」模式下非五星直接丢弃）"""
        return not self.only_five_star or info.rarity == ArtifactRarity.FIVE

    def dedup_applies(self, info: ArtifactInfo) -> bool:
        """是否需要对这条结果做去重判断"""
        return (
            self.only_five_star
            and self.dedup_enabled
            and info.rarity == ArtifactRarity.FIVE
        )

    def count_stop_reason(
        self,
        *,
        scanned: int,
        bag_count: int,
    ) -> StopReason | None:
        """数量类停止条件：达到固定数量 / 达到背包数量（无则返回 None）"""
        if (
            self.mode is StopMode.FIXED_COUNT
            and self.fixed_count > 0
            and scanned >= self.fixed_count
        ):
            return StopReason.FIXED_COUNT
        if bag_count > 0 and scanned >= bag_count:
            return StopReason.BAG_COUNT
        return None

    def progress_total(self, bag_count: int) -> int:
        """进度分母：固定数量模式下取「固定数量」与「背包数量」的较小值"""
        if self.mode is StopMode.FIXED_COUNT and self.fixed_count > 0:
            return (
                min(self.fixed_count, bag_count) if bag_count > 0 else self.fixed_count
            )
        return bag_count
