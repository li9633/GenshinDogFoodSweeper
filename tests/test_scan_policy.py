"""扫描数据模型与停止策略的判定规则（纯逻辑，不需要游戏窗口）"""

from __future__ import annotations

import pytest

from backend.automation.scan_stop_policy import StopPolicy
from backend.models.artifact import ArtifactInfo, ArtifactStat
from backend.models.scan_models import FullScanRequest, StopMode, StopReason
from backend.models.slot_models import (
    BAG_SLOT_CONFIG,
    SALVAGE_SLOT_CONFIG,
    ArtifactRarity,
)


class _FakeSlot:
    def __init__(self, rarity: ArtifactRarity) -> None:
        self.rarity = rarity


def _artifact(rarity: int = 5) -> ArtifactInfo:
    return ArtifactInfo(
        set_name="角斗士的终幕礼",
        piece_type="生之花",
        rarity=rarity,
        main_stat=ArtifactStat(name="生命值", value=4780.0, is_percentage=False),
        level=20,
    )


# StopMode / StopReason

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("anchor", StopMode.ANCHOR),
        ("five_star_only", StopMode.FIVE_STAR_ONLY),
        ("fixed_count", StopMode.FIXED_COUNT),
        ("", StopMode.ANCHOR),
        (None, StopMode.ANCHOR),
        ("不存在的模式", StopMode.ANCHOR),
    ],
)
def test_stop_mode_parse_falls_back(raw: str | None, expected: StopMode) -> None:
    assert StopMode.parse(raw) is expected


def test_stop_mode_labels_match_ui_order() -> None:
    assert [m.label for m in (StopMode.ANCHOR, StopMode.FIVE_STAR_ONLY, StopMode.FIXED_COUNT)] == [
        "首尾锚点定位",
        "仅扫描五星",
        "固定扫描数量",
    ]


def test_stop_reason_labels() -> None:
    assert StopReason.COMPLETED.label == "扫描完成"
    assert StopReason.USER_STOP.label == "已手动停止"


# FullScanRequest

def test_request_derives_anchor_from_slot_config() -> None:
    request = FullScanRequest.from_slot_config(BAG_SLOT_CONFIG, engines_dir="engines")
    roi_x, roi_y = BAG_SLOT_CONFIG.roi[:2]
    assert request.anchor_first_center == (
        roi_x + BAG_SLOT_CONFIG.slot_w // 2,
        roi_y + BAG_SLOT_CONFIG.slot_h // 2,
    )


def test_request_rejects_config_without_roi() -> None:
    import dataclasses

    no_roi = dataclasses.replace(SALVAGE_SLOT_CONFIG, name="无 ROI", roi=None)
    with pytest.raises(ValueError, match="roi"):
        FullScanRequest.from_slot_config(no_roi, engines_dir="engines")


def test_request_carries_policy_snapshot() -> None:
    request = FullScanRequest.from_slot_config(
        BAG_SLOT_CONFIG,
        engines_dir="engines",
        stop_mode=StopMode.FIXED_COUNT,
        fixed_count=50,
        dedup_enabled=False,
    )
    assert request.stop_mode is StopMode.FIXED_COUNT
    assert request.fixed_count == 50
    assert request.dedup_enabled is False


# StopPolicy

def test_only_five_star_mode_filters_slots() -> None:
    assert StopPolicy(StopMode.ANCHOR).slot_pre_filter() is None
    pre_filter = StopPolicy(StopMode.FIVE_STAR_ONLY).slot_pre_filter()
    assert pre_filter is not None
    assert pre_filter(_FakeSlot(ArtifactRarity.FIVE)) is True
    assert pre_filter(_FakeSlot(ArtifactRarity.FOUR)) is False


def test_accepts_depends_on_mode() -> None:
    five_policy = StopPolicy(StopMode.FIVE_STAR_ONLY)
    assert five_policy.accepts(_artifact(5)) is True
    assert five_policy.accepts(_artifact(4)) is False
    assert StopPolicy(StopMode.ANCHOR).accepts(_artifact(4)) is True


def test_dedup_only_applies_to_five_star_with_switch_on() -> None:
    assert StopPolicy(StopMode.FIVE_STAR_ONLY, dedup_enabled=True).dedup_applies(_artifact(5))
    assert not StopPolicy(StopMode.FIVE_STAR_ONLY, dedup_enabled=False).dedup_applies(_artifact(5))
    assert not StopPolicy(StopMode.FIVE_STAR_ONLY).dedup_applies(_artifact(4))
    assert not StopPolicy(StopMode.ANCHOR).dedup_applies(_artifact(5))


def test_count_stop_reason() -> None:
    fixed = StopPolicy(StopMode.FIXED_COUNT, fixed_count=10)
    assert fixed.count_stop_reason(scanned=9, bag_count=100) is None
    assert fixed.count_stop_reason(scanned=10, bag_count=100) is StopReason.FIXED_COUNT

    anchor = StopPolicy(StopMode.ANCHOR)
    assert anchor.count_stop_reason(scanned=4, bag_count=5) is None
    assert anchor.count_stop_reason(scanned=5, bag_count=5) is StopReason.BAG_COUNT
    # 背包数量未知（模板不显示数量）时不应误判
    assert anchor.count_stop_reason(scanned=99, bag_count=0) is None


def test_progress_total_uses_smaller_target_in_fixed_mode() -> None:
    fixed = StopPolicy(StopMode.FIXED_COUNT, fixed_count=10)
    assert fixed.progress_total(bag_count=100) == 10
    assert fixed.progress_total(bag_count=4) == 4
    assert fixed.progress_total(bag_count=0) == 10
    assert StopPolicy(StopMode.ANCHOR).progress_total(bag_count=1523) == 1523
