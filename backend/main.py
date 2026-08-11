"""
原神狗粮清扫器 — 启动入口
===========================
启动 PyQt6 桌面 GUI（系统托盘）+ FastAPI 后端服务。
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from database.init_db import create_tables
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui.app import GenshinApp
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
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，托盘常驻

    # 初始化数据库
    create_tables()

    # 注册 DB + 状态栏 sink（必须在 QApplication 创建后，否则 Qt 信号无法工作）
    from loguru import logger
    from utils.log_bridge import create_db_sink

    logger.add(
        create_db_sink(),
        level="INFO",
        format="{message}",
    )

    # 启动
    genshin_app = GenshinApp(app)

    # 强制立即绘制窗口，避免等到 exec() 才显示
    from PySide6.QtWidgets import QApplication as QA
    QA.processEvents()

    genshin_app.run()


if __name__ == "__main__":
    main()