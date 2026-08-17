"""
模板管理器
==========
所有 images/*.png 即为全部模板，templates.json 仅提供可选的显示名和区域。

JSON 格式（可选字段，缺省则用文件名作为显示名）：
  [
    {"file": "images/artifact_text.png", "display_name": "圣遗物文本", "region": [140, 52, 120, 65]}
  ]

查找时同时支持 display_name 和文件名 stem，例如：
  TemplateManager.get_path("圣遗物文本")   → 通过 display_name
  TemplateManager.get_path("artifact_text") → 通过文件名 stem
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from backend.models.template import Template


class TemplateManager:
    """游戏 UI 模板管理器"""

    TEMPLATES_DIR = (
        Path(__file__).parent.parent.parent / "resources" / "templates"
    )
    IMAGES_DIR: ClassVar[Path] = TEMPLATES_DIR / "images"

    _config_path: ClassVar[Path] = TEMPLATES_DIR / "config" / "templates.json"
    _registry: ClassVar[list[dict[str, object]]] = []
    _index: ClassVar[dict[str, dict[str, object]]] = {}

    # ---------- 内部 ----------

    @classmethod
    def _load(cls) -> None:
        if cls._registry:
            return
        if cls._config_path.exists():
            data = json.loads(cls._config_path.read_text(encoding="utf-8"))
            cls._registry = data if isinstance(data, list) else []
        cls._rebuild_index()

    @classmethod
    def _rebuild_index(cls) -> None:
        cls._index.clear()
        for e in cls._registry:
            name = e.get("display_name")
            file = e.get("file")
            if name:
                cls._index[str(name)] = e
            if file:
                cls._index[Path(str(file)).stem] = e

    @classmethod
    def _find_entry(cls, key: str) -> dict[str, object] | None:
        """按 display_name 或文件名 stem 查找"""
        cls._load()
        return cls._index.get(key)

    @classmethod
    def save(cls) -> None:
        cls._config_path.parent.mkdir(parents=True, exist_ok=True)
        cls._config_path.write_text(
            json.dumps(cls._registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def reload(cls) -> None:
        """清空缓存，重新从 JSON 和磁盘加载"""
        cls._registry.clear()
        cls._index.clear()
        cls._load()

    # ---------- 查询 ----------

    @classmethod
    def get(cls, key: str) -> Template | None:
        """根据 display_name 或文件名获取 Template 对象"""
        entry = cls._find_entry(key)
        if entry is None:
            # 回退：直接按文件名在 images/ 下查找
            direct = cls.IMAGES_DIR / f"{key}.png"
            if direct.exists():
                return Template(
                    display_name=key,
                    path=direct,
                    region=None,
                    stem=direct.stem,
                )
            return None
        filename = entry.get("file")
        if filename:
            filepath = cls.TEMPLATES_DIR / str(filename)
            if not filepath.exists():
                return None
            region = entry.get("region")
            return Template(
                display_name=str(entry.get("display_name", Path(str(filename)).stem)),
                path=filepath,
                region=tuple(region) if region is not None else None,
                stem=filepath.stem,
            )
        return None

    @classmethod
    def get_path(cls, key: str) -> Path | None:
        """根据 display_name 或文件名获取模板完整路径"""
        entry = cls._find_entry(key)
        if entry:
            filename = entry.get("file")
            if filename:
                filepath = cls.TEMPLATES_DIR / str(filename)
                if filepath.exists():
                    return filepath
        # 回退：直接按文件名在 images/ 下查找
        direct = cls.IMAGES_DIR / f"{key}.png"
        return direct if direct.exists() else None

    @classmethod
    def get_region(cls, key: str) -> tuple[int, int, int, int] | None:
        """获取模板的搜索区域 (x, y, w, h)，未配置则返回 None"""
        entry = cls._find_entry(key)
        if entry is None:
            return None
        region = entry.get("region")
        if region is None:
            return None
        return tuple(region)  # type: ignore[return-value]

    @classmethod
    def list_all(cls) -> dict[str, str]:
        """列出 images/ 下所有 PNG，返回 {显示名: 相对路径}"""
        cls._load()
        result: dict[str, str] = {}
        if not cls.IMAGES_DIR.exists():
            return result

        for png in sorted(cls.IMAGES_DIR.glob("*.png")):
            rel = str(png.relative_to(cls.TEMPLATES_DIR)).replace("\\", "/")
            entry = cls._index.get(png.stem)
            display_name = str(entry["display_name"]) if entry and entry.get("display_name") else png.stem
            result[display_name] = rel

        return result

    @classmethod
    def search(cls, keyword: str) -> dict[str, str]:
        """模糊搜索：key 中包含 keyword 的模板"""
        kw = keyword.lower()
        return {k: v for k, v in cls.list_all().items() if kw in k.lower()}

    # ---------- 注册 ----------

    @classmethod
    def register(
        cls,
        key: str,
        filename: str,
        region: tuple[int, int, int, int] | None = None,
    ) -> None:
        """注册（或覆盖）显示名和区域，按文件名 stem 去重"""
        cls._load()
        stem = Path(filename).stem
        entry = cls._index.get(stem)

        if entry is not None:
            entry["display_name"] = key
            entry["file"] = filename
            entry["region"] = list(region) if region is not None else entry.get("region")
        else:
            entry = {
                "display_name": key,
                "file": filename,
                "region": list(region) if region is not None else None,
            }
            cls._registry.append(entry)

        cls._index[key] = entry
        cls._index[stem] = entry