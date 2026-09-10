"""项目目录路径

只返回目录路径，不涉及具体文件。
具体资源文件请使用 common.resources.Resource。

用法：
    from common.paths import IMAGE, DATA, ENGINES

    data_path = DATA / "cache.db"
    engines_dir = ENGINES
"""

import sys
from pathlib import Path

# ── 项目根目录 ──
# 此文件位于 common/paths.py，Path(__file__).parent.parent 始终指向项目根
if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

# ── 顶层目录 ──
RESOURCES = ROOT / "resources"
DATA = ROOT / "data"

# ── 资源子目录 ──
IMAGE = RESOURCES / "image"
ICONS = RESOURCES / "icons"
TEMPLATES = RESOURCES / "templates"
TEMPLATES_CONFIG = TEMPLATES / "config"
TEMPLATES_IMAGES = TEMPLATES / "images"

# ── 运行时目录 ──
ENGINES = ROOT / "engines"
SCAN_RESULT = ROOT / "scan_result"