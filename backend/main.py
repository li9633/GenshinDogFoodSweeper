"""
原神狗粮清扫器 — 启动入口
===========================
PySide6 + QML 桌面 GUI + FastAPI 后端服务。
"""

import os
import sys
import traceback
from pathlib import Path

# 强制使用 Basic 样式，允许自定义控件外观
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

# 修复 PySide6 QSslSocket 警告：Qt 需要找到自带的 OpenSSL DLL
import PySide6

os.add_dll_directory(str(Path(PySide6.__file__).parent))

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from database.init_db import create_tables
from PySide6.QtCore import Qt
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication
from ui.presenters.image_provider import PreviewImageProvider
from ui.presenters.registry import register_all
from utils.logger import log, setup_logging


def _find_icon() -> str | None:
    """查找应用图标，兼容开发模式和 PyInstaller 打包后"""
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent.parent
    for name in ("app.ico", "app.png"):
        p = base / "resources" / name
        if p.exists():
            return str(p)
    return None


def main():
    # 日志初始化
    file_sink_id, stderr_sink_id = setup_logging()

    # 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("GenshinDogFoodSweeper")
    app.setQuitOnLastWindowClosed(False)

    # 设置应用图标
    from PySide6.QtGui import QIcon
    icon_path = _find_icon()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    # 资源根目录：开发模式用脚本所在目录，打包后用 exe 所在目录
    if getattr(sys, 'frozen', False):
        _base_dir = Path(sys.executable).parent
    else:
        _base_dir = Path(__file__).parent

    # 加载 FontAwesome 字体
    from PySide6.QtGui import QFontDatabase
    fonts_dir = _base_dir / "ui" / "qml" / "GenshinUI" / "fonts"
    for font_file in fonts_dir.glob("*.otf"):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            log.warning(f"字体加载失败: {font_file.name}")

    # 初始化数据库
    create_tables()

    # 初始化日志等级
    from database.repository.settings_repo import SettingsRepo
    from utils.version import Channel
    from utils.version_manager import AppVersion

    if SettingsRepo.get("log.db_level") is None:
        _default_level = "DEBUG" if AppVersion.CHANNEL == Channel.DEV else "INFO"
        SettingsRepo.set("log.db_level", _default_level)

    from loguru import logger
    from utils.log_bridge import create_db_sink
    from utils.settings_manager import settings

    # 重新加载设置缓存，确保读到刚写入的默认值
    settings.reload()
    db_level = settings.get("log.db_level")

    sink_id = logger.add(
        create_db_sink(),
        level=db_level,
        format="{message}",
    )

    from utils.log_bridge import register_sink, update_global_level
    register_sink(file_sink_id)
    if stderr_sink_id is not None:
        register_sink(stderr_sink_id)
    register_sink(sink_id)
    update_global_level(db_level)

    # -- QML 引擎 --
    engine = QQmlApplicationEngine()
    engine.addImageProvider("preview", PreviewImageProvider())
    log.debug("PreviewImageProvider 注册成功")

    _presenters = register_all(engine)

    # -- 退出清理 --
    def _cleanup():
        from backend.automation.hotkey_listener import HotkeyListener
        from backend.automation.ocr_worker import OcrWorker

        HotkeyListener.destroy_instance()
        OcrWorker.destroy_instance()
        log.info("热键监听 & OCR Worker 已停止")

    app.aboutToQuit.connect(_cleanup)

    # 全局文本渲染 用 Windows ClearType
    QQuickWindow.setTextRenderType(QQuickWindow.NativeTextRendering)

    qml_dir = _base_dir / "ui" / "qml"
    log.debug(f"QML dir: {qml_dir}, exists: {qml_dir.exists()}")
    engine.addImportPath(str(qml_dir))
    engine.load(str(qml_dir / "main.qml"))

    root_objects = engine.rootObjects()
    log.debug(f"QML rootObjects count: {len(root_objects)}")
    if not root_objects:
        log.error("QML 加载失败：engine.rootObjects() 为空，程序退出")
        sys.exit(-1)

    # -- 系统托盘 --
    try:
        from ui.tray import TrayManager

        _tray = TrayManager(app=app, engine=engine)
        log.debug("TrayManager 启动成功")
    except Exception as exc:
        traceback.print_exc()
        log.error(f"TrayManager 初始化失败: {exc}")

    # -- OCR 初始化器 --
    from ui.gmessagebox import GMessageBox

    GMessageBox.init(engine)
    from backend.automation.ocr_initializer import OcrInitializer

    _ocr_initializer = OcrInitializer()

    # -- 窗口就绪回调 --
    from ui.lifecycle import OnWindowReady

    OnWindowReady.trigger_all()

    app.exec()

    # 强制同步销毁 QML 引擎
    import shiboken6

    shiboken6.delete(engine)


if __name__ == "__main__":
    main()