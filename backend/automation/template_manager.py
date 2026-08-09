"""
模板管理器
==========
统一管理所有游戏 UI 元素模板图片，提供 key → 文件路径的映射。

特性：
  - 内置注册表（REGISTRY）维护 key → filename 映射
  - 自动发现 templates 目录下未被注册的 PNG 文件
  - 支持模糊搜索

使用示例:
    from backend.automation.template_manager import TemplateManager

    # 获取模板路径
    path = TemplateManager.get_path("背包标题")

    # 列出所有模板
    for key, filename in TemplateManager.list_all().items():
        print(f"{key} → {filename}")

    # 搜索
    results = TemplateManager.search("背包")
"""

from __future__ import annotations

from pathlib import Path

from .template_registry import REGISTRY


class TemplateManager:
    """游戏 UI 模板管理器"""

    TEMPLATES_DIR = (
        Path(__file__).parent.parent.parent / "resources" / "templates"
    )

    # 模板注册表（从 template_registry.py 导入）
    REGISTRY: dict[str, str] = REGISTRY

    # ---------- 查询 ----------

    @classmethod
    def get_path(cls, key: str) -> Path | None:
        """根据 key 获取模板完整路径，不存在则返回 None"""
        filename = cls.REGISTRY.get(key)
        if filename is None:
            return None
        filepath = cls.TEMPLATES_DIR / filename
        return filepath if filepath.exists() else None

    @classmethod
    def list_all(cls) -> dict[str, str]:
        """
        列出所有可用模板。

        返回 {key: filename}，来源包括：
          1. REGISTRY 中注册且文件存在的模板
          2. 目录中未被注册的 PNG 文件（自动发现，key = 文件名去扩展名）
        """
        result: dict[str, str] = {}

        if not cls.TEMPLATES_DIR.exists():
            return result

        registered_files = set(cls.REGISTRY.values())

        # 1. 已注册的模板
        for key, filename in cls.REGISTRY.items():
            if (cls.TEMPLATES_DIR / filename).exists():
                result[key] = filename

        # 2. 自动发现未注册的 PNG
        for filepath in sorted(cls.TEMPLATES_DIR.glob("*.png")):
            if filepath.name not in registered_files:
                result[filepath.stem] = filepath.name

        return result

    @classmethod
    def search(cls, keyword: str) -> dict[str, str]:
        """模糊搜索：key 中包含 keyword 的模板（不区分大小写）"""
        kw = keyword.lower()
        return {k: v for k, v in cls.list_all().items() if kw in k.lower()}

    # ---------- 注册 ----------

    @classmethod
    def register(cls, key: str, filename: str) -> None:
        """注册（或覆盖）一个模板映射"""
        cls.REGISTRY[key] = filename