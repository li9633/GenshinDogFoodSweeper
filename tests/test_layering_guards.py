"""分层方向的守卫测试

规范里写了「上层依赖下层，下层绝不依赖上层」，这里把它变成可执行的检查：
用 AST 扫描各层的 import，而不是靠人眼 review。

两条规则：

1. `backend/ui/**` 只允许被 `backend/ui/**` 自己和组合根 `backend/main.py` 导入；
2. 最底两层（`backend/models`、`backend/contracts`）不得依赖任何上层实现
   —— 它们要能被 automation / features / 测试随便导入而不拖进一堆依赖。
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

# 组合根：唯一允许 import UI 层的非 UI 模块
COMPOSITION_ROOT = BACKEND / "main.py"

# 最底两层不允许依赖的包
_FORBIDDEN_FOR_BOTTOM = (
    "backend.automation",
    "backend.features",
    "backend.domain",
    "backend.crawler",
    "backend.database",
    "backend.exceptions",
    "backend.ui",
)


def _python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _imported_modules(path: Path) -> set[str]:
    """文件里所有 import 的模块全名（含函数内的延迟导入）"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _imports_within(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def test_only_entry_point_imports_ui_layer() -> None:
    """除 backend/main.py 外，非 UI 模块不得 import backend.ui"""
    offenders: list[str] = []
    for path in _python_files(BACKEND):
        if "ui" in path.relative_to(BACKEND).parts:
            continue  # UI 层内部互相引用是允许的
        if path == COMPOSITION_ROOT:
            continue
        hits = [m for m in _imported_modules(path) if _imports_within(m, "backend.ui")]
        if hits:
            offenders.append(f"{path.relative_to(REPO_ROOT)} → {sorted(hits)}")

    assert offenders == [], "这些非 UI 模块反向依赖了 UI 层:\n" + "\n".join(offenders)


def test_bottom_layers_do_not_depend_on_upper_layers() -> None:
    """models / contracts 只能依赖彼此，不得依赖任何上层实现"""
    offenders: list[str] = []
    for package in ("models", "contracts"):
        for path in _python_files(BACKEND / package):
            hits = sorted(
                {
                    module
                    for module in _imported_modules(path)
                    if any(_imports_within(module, bad) for bad in _FORBIDDEN_FOR_BOTTOM)
                }
            )
            if hits:
                offenders.append(f"{path.relative_to(REPO_ROOT)} → {hits}")

    assert offenders == [], "底层包反向依赖了上层:\n" + "\n".join(offenders)
