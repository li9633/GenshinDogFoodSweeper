"""项目目录路径 — 只返回目录路径，不涉及具体文件。具体资源文件请使用 common.resources.Resource。"""

import sys
from pathlib import Path

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

RESOURCES = ROOT / "resources"
DATA = ROOT / "data"

IMAGE = RESOURCES / "image"
ICONS = RESOURCES / "icons"
TEMPLATES = RESOURCES / "templates"
TEMPLATES_CONFIG = TEMPLATES / "config"
TEMPLATES_IMAGES = TEMPLATES / "images"

ENGINES = ROOT / "engines"
SCAN_RESULT = ROOT / "scan_result"

if getattr(sys, "frozen", False):
    QML_DIR = ROOT / "ui" / "qml"
else:
    QML_DIR = ROOT / "backend" / "ui" / "qml"

BUILD_DIR = ROOT / "build"
INSTALLER_DIR = ROOT / "installer"
INSTALLER_TOOLS = INSTALLER_DIR / "tools"
INSTALLER_QML = INSTALLER_DIR / "qml"
TEMP_DISPOSABLE = ROOT / "temp" / "disposable"