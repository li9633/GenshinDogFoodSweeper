"""圣遗物扫描结果保存能力（实现侧）
================================
- **接口规范**在 ``backend/contracts/artifact_save.py``（ArtifactSaver 等）；
- 本包提供实现：数据集组装、格式注册表、内置格式、SaveJob 兜底封装。

用法::

    from backend.contracts.artifact_save import SaveTarget
    from backend.features.artifact_save import SaveJob, build_dataset, create_saver

    dataset = build_dataset(artifacts, meta)
    job = SaveJob(saver=create_saver("GDFS-v1.0"), target=SaveTarget(Path("D:/out")))
    result = job.run(dataset)      # SaveResult(ok, path, message)
"""

from backend.features.artifact_save.dataset import build_dataset, enrich_set_effects
from backend.features.artifact_save.registry import (
    DEFAULT_FORMAT_ID,
    available_formats,
    create_saver,
    is_known_format,
    register,
)
from backend.features.artifact_save.saver import SaveJob

__all__ = [
    "DEFAULT_FORMAT_ID",
    "SaveJob",
    "available_formats",
    "build_dataset",
    "create_saver",
    "enrich_set_effects",
    "is_known_format",
    "register",
]
