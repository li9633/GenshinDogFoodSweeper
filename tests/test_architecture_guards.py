"""导入根与全局副作用的回归测试

这两条是历史上真实踩过的坑：
1. 同一个文件被两种导入路径加载 → 单例/枚举/数据类身份分裂（settings 双实例）；
2. `import` 某个包时偷偷安装全局异常过滤器。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 曾是"短写顶层包"的名字（现在是 backend.* 的子包）
_LEGACY_TOP_LEVEL = (
    "ui",
    "models",
    "utils",
    "database",
    "service",
    "api",
    "crawler",
    "automation",
    "exceptions",
    "contracts",
    "domain",
    "features",
)


def _project_module(name: str) -> bool:
    """sys.modules[name] 是否指向本项目仓库内的文件"""
    module = sys.modules.get(name)
    if module is None:
        return False
    file = getattr(module, "__file__", None)
    if not file:
        return False
    try:
        return REPO_ROOT in Path(file).resolve().parents
    except OSError:
        return False


def test_app_import_graph_has_no_dual_roots() -> None:
    """导入应用主要模块后，不得出现仓库内的短写顶层包"""
    import backend.contracts.artifact_save
    import backend.crawler.version_checker
    import backend.features.artifact_save
    import backend.ui.presenters.registry
    import backend.utils.settings_manager  # noqa: F401

    offenders = [name for name in _LEGACY_TOP_LEVEL if _project_module(name)]
    assert offenders == [], f"这些模块被短写顶层包名加载了: {offenders}"


def test_settings_singleton_is_shared() -> None:
    """settings 单例必须被各处共享（曾因双导入根出现两份缓存）"""
    import backend.ui.presenters.artifact_scan_presenter as scan_module
    from backend.utils.settings_manager import SettingsManager, settings

    assert SettingsManager.__module__ == "backend.utils.settings_manager"
    assert scan_module.settings is settings


def test_importing_exception_package_has_no_side_effect() -> None:
    """导入异常包不得改变 sys.excepthook（过滤器改由入口显式安装）"""
    import backend.exceptions.automation
    import backend.exceptions.automation.exceptions  # noqa: F401

    before = sys.excepthook
    import importlib

    importlib.reload(importlib.import_module("backend.exceptions.automation"))

    assert sys.excepthook is before


def test_exception_handler_installs_explicitly_and_idempotently() -> None:
    """显式安装后才生效，且重复调用保持同一个处理器"""
    from backend.exceptions.automation.exception_handler import (
        install_exception_filters,
    )

    before = sys.excepthook
    install_exception_filters()
    first = sys.excepthook
    assert first is not before
    install_exception_filters()
    assert sys.excepthook is first


def test_exception_module_does_not_depend_on_ui() -> None:
    """领域层异常只承载消息，不得引用 UI 层"""
    from backend.exceptions.automation import exceptions

    source = Path(exceptions.__file__).read_text(encoding="utf-8-sig")
    assert "backend.ui" not in source
    assert "gmessagebox" not in source
