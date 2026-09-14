"""保存格式注册表
===============
UI 通过 ``available_formats()`` 枚举可选项，通过 ``create_saver()`` 取得实现；
扫描层只拿到契约里的 ``ArtifactSaver`` 接口，不知道具体格式是什么。
"""

from __future__ import annotations

from backend.contracts.artifact_save import ArtifactSaver, SaveFormatInfo
from backend.features.artifact_save.formats import BUILTIN_SAVERS, DEFAULT_SAVER
from backend.utils.logger import log

DEFAULT_FORMAT_ID: str = DEFAULT_SAVER.format_id

_REGISTRY: dict[str, type[ArtifactSaver]] = {}


def register(saver_cls: type[ArtifactSaver]) -> None:
    """注册保存格式（同 id 重复注册时后者生效并告警）"""
    if saver_cls.format_id in _REGISTRY:
        log.warning(f"保存格式 {saver_cls.format_id} 重复注册，使用后者")
    _REGISTRY[saver_cls.format_id] = saver_cls


def available_formats() -> list[SaveFormatInfo]:
    """所有已注册格式（保持注册顺序，供 UI 下拉框）"""
    return [SaveFormatInfo.of(saver_cls) for saver_cls in _REGISTRY.values()]


def create_saver(format_id: str | None) -> ArtifactSaver:
    """按 id 创建保存实现

    未知 id（用户配置过期、格式被下线）不报错，回退默认格式并告警 ——
    保存格式的可选项变化不应该让扫描直接失败。
    """
    saver_cls = _REGISTRY.get(format_id or "")
    if saver_cls is None:
        if format_id:
            log.warning(f"未知保存格式 {format_id!r}，回退默认 {DEFAULT_FORMAT_ID}")
        saver_cls = _REGISTRY.get(DEFAULT_FORMAT_ID) or DEFAULT_SAVER
    return saver_cls()


def is_known_format(format_id: str | None) -> bool:
    return bool(format_id) and format_id in _REGISTRY


def _register_builtins() -> None:
    for saver_cls in BUILTIN_SAVERS:
        register(saver_cls)


_register_builtins()
