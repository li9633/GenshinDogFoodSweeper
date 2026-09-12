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
    if hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        exe_dir = Path(sys.executable).parent
        if meipass.parent == exe_dir:
            # COLLECT 模式（one-dir）：资源在 exe 同级目录，不在 _internal 中
            ROOT = exe_dir
        else:
            # onefile 模式：所有资源都提取到 _MEIPASS 临时目录
            ROOT = meipass
    else:
        ROOT = Path(sys.executable).parent
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

# ── QML 目录 ──
# 开发模式：backend/ui/qml/（在 backend 包内）
# 打包模式：ui/qml/（spec 文件将 backend/ui/qml 复制到 dist 根目录的 ui/qml）
if getattr(sys, "frozen", False):
    QML_DIR = ROOT / "ui" / "qml"
else:
    QML_DIR = ROOT / "backend" / "ui" / "qml"

# ── 构建目录 ──
BUILD_DIR = ROOT / "build"
INSTALLER_DIR = ROOT / "installer"
INSTALLER_TOOLS = INSTALLER_DIR / "tools"
INSTALLER_QML = INSTALLER_DIR / "qml"
TEMP_DISPOSABLE = ROOT / "temp" / "disposable"