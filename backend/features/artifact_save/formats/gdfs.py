"""GDFS 系列保存格式
==================
同一份 schema，两档字段详细程度：

- ``GDFS-v1.0``      基本信息：结构化识别结果，**不含 OCR 原文**（体积更小，默认格式）
- ``GDFS-v1.0-full`` 无损：额外写入 ``raw_texts``，可回溯识别过程、可离线复算

文件结构（单文件、自描述 JSON）：

.. code-block:: json

    {
      "format": "GDFS-v1.0",
      "generated_at": "2026-09-13 22:40:00",
      "generator": { "app": "GenshinDogFoodSweeper", "version": "0.9.40" },
      "scan": { "...扫描上下文..." },
      "artifacts": [ { "...圣遗物字段..." } ]
    }

文件名、落盘、错误兜底等共性都在 :class:`GdfsSaverBase`，
各档只声明自己写入哪些字段。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import ClassVar

from backend.contracts.artifact_save import (
    SaveResult,
    SaveTarget,
    ScanDataset,
)
from backend.models.artifact import ArtifactInfo
from backend.utils.logger import log
from common.constants import APP_NAME
from common.datetime_helper import FMT_DATETIME, DateTimeHelper
from common.version_manager import AppVersion

FILE_SUFFIX = ".gdfs.json"
DEFAULT_STEM = "scan"


class GdfsSaverBase:
    """GDFS 系列公共实现（子类只声明 format_* 与 include_raw_texts）"""

    format_id: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    include_raw_texts: ClassVar[bool] = False

    def save(self, dataset: ScanDataset, target: SaveTarget) -> SaveResult:
        try:
            directory = target.ensure_directory()
            filepath = (
                directory
                / f"{DEFAULT_STEM}_{DateTimeHelper.file_timestamp()}{FILE_SUFFIX}"
            )
            filepath.write_text(
                json.dumps(self._payload(dataset), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            log.error(f"{self.format_id} 保存失败: {exc}")
            return SaveResult(
                ok=False,
                format_id=self.format_id,
                message=f"保存失败: {exc}",
            )

        count = len(dataset.artifacts)
        log.info(f"扫描结果已保存: {filepath} ({count} 件, {self.format_id})")
        return SaveResult(
            ok=True,
            format_id=self.format_id,
            path=filepath,
            message=f"已保存 {count} 件到 {filepath.name}",
        )

    # # 载荷构造
    #

    def _payload(self, dataset: ScanDataset) -> dict:
        meta = dataset.meta
        return {
            "format": self.format_id,
            "generated_at": DateTimeHelper.now_str(),
            "generator": {
                "app": APP_NAME,
                "version": AppVersion.semver(),
            },
            "scan": {
                "started_at": _fmt_datetime(meta.started_at),
                "finished_at": _fmt_datetime(meta.finished_at),
                "duration_ms": meta.duration_ms,
                "stop_mode": meta.stop_mode.value,
                "stopped_by": meta.stopped_by.value,
                "slot_config": meta.slot_config_name,
                "bag_count": meta.bag_count,
                "scanned": meta.scanned,
                "material_count": dataset.material_count,
                "five_star_count": dataset.five_star_count,
                "total_pages": meta.total_pages,
                "dedup_skipped": meta.dedup_skipped,
            },
            "artifacts": [self._artifact_dict(a) for a in dataset.artifacts],
        }

    def _artifact_dict(self, artifact: ArtifactInfo) -> dict:
        """单件数据：不含 OCR 原文的档位在这里剔除 raw_texts"""
        data = asdict(artifact)
        if not self.include_raw_texts:
            data.pop("raw_texts", None)
        return data


class GdfsV1Saver(GdfsSaverBase):
    """GDFS-v1.0 —— 只写圣遗物基本信息"""

    format_id = "GDFS-v1.0"
    display_name = "GDFS-v1.0"
    description = "仅圣遗物基本信息（不含 OCR 原文），体积更小"
    include_raw_texts = False


class GdfsV1FullSaver(GdfsSaverBase):
    """GDFS-v1.0-full —— 无损，额外包含 OCR 原文"""

    format_id = "GDFS-v1.0-full"
    display_name = "GDFS-v1.0-full"
    description = "基本信息 + OCR 原文，可回溯识别过程、可离线复算"
    include_raw_texts = True


def _fmt_datetime(value: datetime) -> str:
    return value.strftime(FMT_DATETIME)
