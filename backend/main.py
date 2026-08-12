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
from ui.presenters.image_provider import PreviewImageProvider
from utils.logger import log, setup_logging


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
    engine.addImageProvider("preview", PreviewImageProvider())
    log.debug("PreviewImageProvider 注册成功")

    # 将 Python 后端对象暴露给 QML
    import traceback

    from utils.env_manager import EnvManager

    _env_manager = EnvManager()
    engine.rootContext().setContextProperty("EnvManager", _env_manager)
    log.debug(f"EnvManager 注册成功, isDebug={_env_manager.is_debug()}")

    try:
        from ui.presenters.settings_presenter import SettingsPresenter

        presenter = SettingsPresenter()
        engine.rootContext().setContextProperty("SettingsPresenter", presenter)
        log.debug("SettingsPresenter 注册成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"SettingsPresenter 初始化失败: {exc}")

    try:
        from ui.presenters.region_marker_presenter import RegionMarkerPresenter

        region_marker = RegionMarkerPresenter()
        engine.rootContext().setContextProperty("RegionMarker", region_marker)
        log.debug("RegionMarker 注册成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"RegionMarker 初始化失败: {exc}")

    try:
        from ui.presenters.element_detection_presenter import ElementDetectionPresenter

        element_detection = ElementDetectionPresenter()
        engine.rootContext().setContextProperty("ElementDetection", element_detection)
        log.debug("ElementDetection 注册成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"ElementDetection 初始化失败: {exc}")

    try:
        from ui.presenters.artifact_recognition_presenter import (
            ArtifactRecognitionPresenter,
        )

        artifact_recognition = ArtifactRecognitionPresenter()
        engine.rootContext().setContextProperty(
            "ArtifactRecognition", artifact_recognition
        )
        log.debug("ArtifactRecognition 注册成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"ArtifactRecognition 初始化失败: {exc}")

    try:
        from ui.pages.debug_panels.status_bar_test_panel import StatusBarTestPresenter

        status_bar_test = StatusBarTestPresenter()
        engine.rootContext().setContextProperty("StatusBarTest", status_bar_test)
        log.debug("StatusBarTest 注册成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"StatusBarTest 初始化失败: {exc}")

    try:
        from ui.presenters.status_bar_presenter import StatusBarPresenter
        from utils.log_bridge import set_status_callback

        status_bar = StatusBarPresenter()
        engine.rootContext().setContextProperty("StatusBarPresenter", status_bar)
        set_status_callback(status_bar.show)
        log.debug("StatusBar 注册成功，日志桥接已启用")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"StatusBar 初始化失败: {exc}")

    try:
        from ui.presenters.game_detector import GameDetector

        game_detector = GameDetector()
        engine.rootContext().setContextProperty("GameDetector", game_detector)
        log.debug("GameDetector 注册成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"GameDetector 初始化失败: {exc}")

    # -- OCR 引擎预热（后台线程，不阻塞 UI） --
    from PySide6.QtCore import QTimer

    def _start_ocr_worker():
        from backend.automation.ocr_worker import OcrWorker

        # OcrWorker 内部通过 log.info/log.error 自动驱动状态栏
        # （create_db_sink 已将 loguru → 状态栏桥接）
        OcrWorker.instance()

    QTimer.singleShot(2000, _start_ocr_worker)

    # -- 退出清理 --
    def _cleanup():
        from backend.automation.ocr_worker import OcrWorker

        OcrWorker.destroy_instance()
        log.info("OCR Worker 已停止")

    app.aboutToQuit.connect(_cleanup)

    qml_dir = Path(__file__).parent / "ui" / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(str(qml_dir / "main.qml"))

    if not engine.rootObjects():
        sys.exit(-1)

    app.exec()


if __name__ == "__main__":
    main()