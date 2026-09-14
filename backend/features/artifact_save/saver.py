"""保存任务封装
==============
把「用哪个格式 + 存到哪里」打包成一次任务，供扫描层直接调用；
任何保存异常都在这里兜底成 ``SaveResult(ok=False)``，调用方无需 try。
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.artifact_save import (
    ArtifactSaver,
    SaveResult,
    SaveTarget,
    ScanDataset,
)
from backend.utils.logger import log


@dataclass(frozen=True)
class SaveJob:
    """一次保存任务：用哪个格式、存到哪里"""

    saver: ArtifactSaver
    target: SaveTarget

    @property
    def format_id(self) -> str:
        return self.saver.format_id

    def run(self, dataset: ScanDataset) -> SaveResult:
        """执行保存 —— 任何异常都在这里兜底，调用方无需 try"""
        try:
            return self.saver.save(dataset, self.target)
        # 保存失败只影响“这次没存上”，不应中断扫描流程
        except Exception as exc:
            log.exception(f"保存失败 ({self.saver.format_id}): {exc}")
            return SaveResult(
                ok=False,
                format_id=self.saver.format_id,
                message=f"保存失败: {exc}",
            )
