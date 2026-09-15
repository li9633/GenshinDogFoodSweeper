"""扫描结果保存契约
==================
扫描结束后，扫描层把 :class:`ScanDataset`（扫描的全部数据）交给一个
:class:`ArtifactSaver`，由实现自行决定保存格式、文件结构与落盘方式。

新增一种格式只需两步：

1. 写一个满足 :class:`ArtifactSaver` 协议的类（实现放功能包内，如
   ``backend/features/artifact_save/formats/``）；
2. 在功能包的注册表里登记。

实现约束（重要）：

- **不得触碰 Qt / 任何界面对象**：保存发生在扫描线程中；
- **不得读取全局 settings**：需要什么就从 :class:`ScanDataset` / :class:`SaveTarget` 拿；
- 允许抛异常，调用方（功能包里的 SaveJob）会统一兜底成 ``SaveResult(ok=False)``。

本模块只依赖 ``backend.models``：契约要能被任何实现方引用，不允许反向依赖功能实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable

from backend.models.artifact import ArtifactInfo
from backend.models.scan_models import ScanMeta

_FIVE_STAR = 5


@dataclass(frozen=True)
class ScanDataset:
    """一次扫描产出的全部数据 —— 保存格式实现拿到的完整输入"""

    artifacts: list[ArtifactInfo]
    meta: ScanMeta

    @property
    def material_count(self) -> int:
        """强化材料件数（非圣遗物）"""
        return sum(1 for a in self.artifacts if a.is_material)

    @property
    def five_star_count(self) -> int:
        return sum(1 for a in self.artifacts if a.rarity == _FIVE_STAR)


@dataclass(frozen=True)
class SaveTarget:
    """保存位置 —— 由用户在 UI 上选定（扩展点：未来可加文件名模板、覆盖策略等）"""

    directory: Path

    def ensure_directory(self) -> Path:
        """确保目录存在并返回（保存格式实现统一从入口创建目录）"""
        self.directory.mkdir(parents=True, exist_ok=True)
        return self.directory


@dataclass(frozen=True)
class SaveResult:
    """保存结果 —— 保存格式实现回报给扫描层的唯一产物"""

    ok: bool
    format_id: str
    path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class SaveFormatInfo:
    """供 UI 枚举的格式信息"""

    id: str
    name: str
    description: str

    @classmethod
    def of(cls, saver_cls: type[ArtifactSaver]) -> SaveFormatInfo:
        return cls(
            id=saver_cls.format_id,
            name=saver_cls.display_name,
            description=saver_cls.description,
        )


@runtime_checkable
class ArtifactSaver(Protocol):
    """保存格式接口规范"""

    format_id: ClassVar[str]
    """稳定标识，用于持久化用户选择（如 ``"GDFS-v1.0"``），一经发布不应变更"""

    display_name: ClassVar[str]
    """界面下拉框展示名"""

    description: ClassVar[str]
    """一句话说明，供界面提示用户格式差异"""

    def save(self, dataset: ScanDataset, target: SaveTarget) -> SaveResult:
        """把扫描数据保存到 target，返回保存结果"""
        ...
