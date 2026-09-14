"""内置保存格式登记处

新增格式：在 ``formats/`` 下实现满足契约 ``ArtifactSaver`` 协议（见
``backend/contracts/artifact_save.py``）的类，然后登记到 ``BUILTIN_SAVERS``
（注册发生在 registry 导入时）。

顺序即 UI 下拉框顺序，默认格式放最前。
"""

from __future__ import annotations

from backend.contracts.artifact_save import ArtifactSaver
from backend.features.artifact_save.formats.gdfs import (
    GdfsV1FullSaver,
    GdfsV1Saver,
)

BUILTIN_SAVERS: tuple[type[ArtifactSaver], ...] = (GdfsV1Saver, GdfsV1FullSaver)

DEFAULT_SAVER: type[ArtifactSaver] = GdfsV1Saver
"""默认格式：用户选择缺失或失效时回退到它"""
