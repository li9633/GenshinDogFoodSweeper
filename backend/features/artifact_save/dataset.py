"""数据集组装
============
把扫描结果 + 上下文组装成 :class:`ScanDataset`（契约类型），并统一回填套装效果。

数据集组装放在实现侧（而不是契约里）：回填需要查库，属于 IO，
契约包必须保持零依赖。
"""

from __future__ import annotations

from backend.contracts.artifact_save import ScanDataset
from backend.models.artifact import ArtifactInfo
from backend.models.scan_models import ScanMeta


def build_dataset(
    artifacts: list[ArtifactInfo],
    meta: ScanMeta,
    *,
    enrich: bool = True,
) -> ScanDataset:
    """组装数据集

    Args:
        artifacts: 扫描识别结果（``enrich=True`` 时会就地回填 ``set_effects``）
        meta: 扫描上下文
        enrich: 是否从数据库回填套装效果。由这里统一回填，
            保存格式实现就不必各自查库、也不会各查各的。
    """
    items = list(artifacts)
    if enrich:
        enrich_set_effects(items)
    return ScanDataset(artifacts=items, meta=meta)


def enrich_set_effects(artifacts: list[ArtifactInfo]) -> None:
    """从数据库回填套装效果（延迟导入，避免导入期拉起数据库依赖）"""
    from backend.database.repository.artifact_set_repo import ArtifactSetRepo

    all_sets = {s.id: s for s in ArtifactSetRepo.find_all()}
    if not all_sets:
        return
    for artifact in artifacts:
        if artifact.set_id is None:
            continue
        artifact_set = all_sets.get(artifact.set_id)
        if artifact_set:
            artifact.set_effects = artifact_set.set_effects
