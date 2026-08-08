"""
原神狗粮清扫器 — 启动入口
===========================
启动 PyQt6 桌面 GUI（系统托盘）+ FastAPI 后端服务。
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
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
    app.setApplicationDisplayName("原神狗粮清扫器")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，托盘常驻

    # 加载样式表
    style_path = Path(__file__).parent / "ui" / "resources" / "style.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    # 启动
    genshin_app = GenshinApp(app)
    genshin_app.run()


if __name__ == "__main__":
    main()