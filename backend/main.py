"""
原神狗粮清扫器 — 启动入口
===========================
PySide6 + QML 桌面 GUI + FastAPI 后端服务。
"""

import os
import sys
from pathlib import Path

# 强制使用 Basic 样式，允许自定义控件外观
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from database.init_db import create_tables
from PySide6.QtCore import Qt
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication
from utils.logger import setup_logging


def main():
    # 日志初始化（必须在任何日志调用之前）
    setup_logging()

    # 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("GenshinDogFoodSweeper")
    app.setQuitOnLastWindowClosed(False)

    # 初始化数据库
    create_tables()

    # 注册 DB + 状态栏 sink
    from loguru import logger
    from utils.log_bridge import create_db_sink

    logger.add(
        create_db_sink(),
        level="INFO",
        format="{message}",
    )

    # -- QML 引擎 --
    engine = QQmlApplicationEngine()

    # 将 Python 后端对象暴露给 QML
    import traceback
    from utils.env_manager import EnvManager
    _env_manager = EnvManager()
    engine.rootContext().setContextProperty("EnvManager", _env_manager)
    print(f"[OK] EnvManager 注册成功, isDebug={_env_manager.is_debug()}", file=sys.stderr)

    try:
        from ui.presenters.settings_presenter import SettingsPresenter
        presenter = SettingsPresenter()
        engine.rootContext().setContextProperty("SettingsPresenter", presenter)
        print("[OK] SettingsPresenter 注册成功", file=sys.stderr)
    except Exception as exc: 
        traceback.print_exc()
        print(f"[FAIL] SettingsPresenter 初始化失败: {exc}", file=sys.stderr)

    qml_dir = Path(__file__).parent / "ui" / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(str(qml_dir / "main.qml"))

    if not engine.rootObjects():
        sys.exit(-1)

    app.exec()


if __name__ == "__main__":
    main()