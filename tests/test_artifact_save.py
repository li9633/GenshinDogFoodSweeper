"""保存格式：GDFS-v1.0（基本信息）/ GDFS-v1.0-full（无损）的落盘契约"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import pytest

from backend.contracts.artifact_save import (
    SaveResult,
    SaveTarget,
    ScanDataset,
)
from backend.features.artifact_save import (
    DEFAULT_FORMAT_ID,
    SaveJob,
    available_formats,
    build_dataset,
    create_saver,
    is_known_format,
)
from backend.models.artifact import ArtifactInfo, ArtifactStat, SubStat
from backend.models.scan_models import ScanMeta, StopMode, StopReason
from common.datetime_helper import DateTimeHelper
from common.paths import TEMP_DISPOSABLE


@pytest.fixture()
def out_dir() -> Path:
    """每次测试一个全新的输出目录（用项目自带临时目录，不依赖 pytest 的 tmp_path）"""
    target = TEMP_DISPOSABLE / f"artifact_save_{uuid4().hex[:8]}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _artifact(index: int, *, material: bool = False) -> ArtifactInfo:
    return ArtifactInfo(
        set_name="角斗士的终幕礼",
        set_id=15001,
        piece_type="生之花",
        piece_name="角斗士的留恋",
        rarity=5,
        main_stat=ArtifactStat(name="生命值", value=4780.0, is_percentage=False),
        sub_stats=[
            SubStat(name="暴击率", value=7.8, is_percentage=True, is_activated=True),
        ],
        level=20,
        is_locked=True,
        set_effects={"2": "攻击力提高18%"},
        raw_texts={"圣遗物名称": "角斗士的留恋", "等级": "+20"},
        is_material=material,
        material_name="祝圣精华" if material else None,
        page=index // 8,
        row=index % 4,
        col=index % 8,
    )


def _dataset() -> ScanDataset:
    now = DateTimeHelper.now()
    artifacts = [_artifact(0), _artifact(1), _artifact(2, material=True)]
    meta = ScanMeta(
        started_at=now,
        finished_at=now,
        scanned=len(artifacts),
        total_pages=3,
        stop_mode=StopMode.ANCHOR,
        stopped_by=StopReason.TAIL_ANCHOR,
        slot_config_name="背包圣遗物列表",
        bag_count=1523,
        dedup_skipped=2,
    )
    return build_dataset(artifacts, meta, enrich=False)


def _save(out: Path, format_id: str) -> tuple[SaveResult, dict]:
    result = SaveJob(saver=create_saver(format_id), target=SaveTarget(out)).run(_dataset())
    assert result.ok, result.message
    assert result.path is not None
    return result, json.loads(result.path.read_text(encoding="utf-8"))


def test_registry_exposes_both_formats_with_default_first() -> None:
    formats = available_formats()
    assert [f.id for f in formats] == ["GDFS-v1.0", "GDFS-v1.0-full"]
    assert DEFAULT_FORMAT_ID == formats[0].id
    assert is_known_format("GDFS-v1.0-full")


def test_unknown_format_falls_back_to_default() -> None:
    assert create_saver("已下线的格式").format_id == DEFAULT_FORMAT_ID
    assert create_saver(None).format_id == DEFAULT_FORMAT_ID


def test_basic_format_drops_raw_texts_only(out_dir: Path) -> None:
    result, payload = _save(out_dir, "GDFS-v1.0")
    assert result.path.name.startswith("scan_") and result.path.name.endswith(".gdfs.json")
    assert payload["format"] == "GDFS-v1.0"
    assert payload["generator"]["app"] == "GenshinDogFoodSweeper"
    assert all("raw_texts" not in item for item in payload["artifacts"])
    # 除 raw_texts 外的字段必须与 asdict 完全一致
    assert payload["artifacts"] == [
        {k: v for k, v in asdict(a).items() if k != "raw_texts"} for a in _dataset().artifacts
    ]


def test_full_format_is_lossless(out_dir: Path) -> None:
    _, payload = _save(out_dir, "GDFS-v1.0-full")
    assert payload["format"] == "GDFS-v1.0-full"
    assert payload["artifacts"] == [asdict(a) for a in _dataset().artifacts]
    assert payload["artifacts"][0]["raw_texts"]["等级"] == "+20"


def test_both_formats_share_scan_metadata(out_dir: Path) -> None:
    _, basic = _save(out_dir, "GDFS-v1.0")
    _, full = _save(out_dir, "GDFS-v1.0-full")
    assert basic["scan"] == full["scan"]
    scan = basic["scan"]
    assert scan["stop_mode"] == "anchor"
    assert scan["stopped_by"] == "tail_anchor"
    assert scan["bag_count"] == 1523
    assert scan["material_count"] == 1
    assert scan["five_star_count"] == 3
    assert scan["dedup_skipped"] == 2
    assert scan["duration_ms"] >= 0


def test_save_failure_is_returned_not_raised(out_dir: Path) -> None:
    blocker = out_dir / "占位文件"
    blocker.write_text("x", encoding="utf-8")
    result = SaveJob(
        saver=create_saver(DEFAULT_FORMAT_ID),
        target=SaveTarget(blocker / "sub"),
    ).run(_dataset())
    assert result.ok is False
    assert "保存失败" in result.message


def test_saver_exception_is_contained(out_dir: Path) -> None:
    class _Boom:
        format_id = "boom"
        display_name = "Boom"
        description = "总是抛异常"

        def save(self, dataset, target):
            raise RuntimeError("boom")

    result = SaveJob(saver=_Boom(), target=SaveTarget(out_dir)).run(_dataset())
    assert result.ok is False
    assert "boom" in result.message
