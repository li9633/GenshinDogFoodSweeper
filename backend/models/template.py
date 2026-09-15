"""模板对象模型"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Template:
    """模板对象：封装模板的路径、显示名、搜索区域等元信息"""

    display_name: str
    path: Path
    region: tuple[int, int, int, int] | None
    stem: str
