"""跨功能契约（接口规范）
======================
本包只放**接口**以及**出现在接口签名里的类型**，不含任何实现、不含 IO、
不依赖 Qt：可以被任何一层引用，也便于自动化检查依赖方向。

归属判据（新增接口时按此决定放哪）：

- 被 ≥2 个功能实现或引用 → 放本包（``backend/contracts/``）；
- 只服务单一功能 → 留在该功能自己的包里，不要为了“规范”上提；
- 纯数据模型/枚举若只服务单一功能，留在 ``backend/models/``。

当前契约：

- :mod:`backend.contracts.artifact_save` —— 扫描结果保存格式接口规范。
"""

from backend.contracts.artifact_save import (
    ArtifactSaver,
    SaveFormatInfo,
    SaveResult,
    SaveTarget,
    ScanDataset,
)

__all__ = [
    "ArtifactSaver",
    "SaveFormatInfo",
    "SaveResult",
    "SaveTarget",
    "ScanDataset",
]
