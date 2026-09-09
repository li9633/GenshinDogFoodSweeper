r"""安装程序入口
============
PySide6 + QML 安装向导。

用法:
    GenshinDogFoodSweeper-setup.exe                            # 自动检测：有注册表→更新，无→安装
    GenshinDogFoodSweeper-setup.exe --quick-update --fallback-install-dir "C:\..." --old-version "0.9.3"  # 快速更新
    uninst.exe                                                 # 自动检测：程序名含 uninst → 卸载
    GenshinDogFoodSweeper-setup.exe --mode uninstall           # 显式卸载
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

import shiboken6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from installer.core import (
    APP_NAME,
    get_default_install_dir,
    get_logger,
    resolve_directory,
)

logger = get_logger(__name__)

from installer.presenters.confirm_presenter import ConfirmPresenter
from installer.presenters.coordinator import VERSION, AppCoordinator
from installer.presenters.directory_presenter import DirectoryPresenter
from installer.presenters.finish_presenter import FinishPresenter
from installer.presenters.progress_presenter import ProgressPresenter
from installer.presenters.welcome_presenter import WelcomePresenter


def _setup_log() -> Path:
    """在安装程序运行目录创建日志文件，返回日志路径"""
    if getattr(sys, "frozen", False):
        log_dir = Path(sys.executable).parent
    else:
        log_dir = Path.cwd()
    timestamp = datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"install-log-{timestamp}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )
    return log_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原神狗粮扫荡器 安装程序")
    parser.add_argument(
        "--mode",
        type=str,
        default="install",
        choices=["install", "uninstall"],
        help="运行模式",
    )
    parser.add_argument("--quick-update", action="store_true", help="快速更新模式")
    parser.add_argument(
        "--fallback-install-dir",
        type=str,
        default=None,
        help="回退安装目录（由主 App 传入）",
    )
    parser.add_argument(
        "--old-version",
        type=str,
        default=None,
        help="旧版本号（由主 App 传入，快速更新时使用）",
    )
    return parser.parse_args()


_UNINSTALLER_NAMES = frozenset({"uninst.exe", "uninstall.exe", "uninstaller.exe"})


def _is_uninstaller_exe() -> bool:
    """检测当前程序是否为卸载器（通过文件名判断）。"""
    if getattr(sys, "frozen", False):
        name = Path(sys.executable).name.lower()
        return name in _UNINSTALLER_NAMES
    return False


def main() -> None:
    args = _parse_args()

    # -- 三级级联解析安装目录 --
    mode = args.mode
    quick_update = args.quick_update
    install_dir, old_version = resolve_directory(
        args.fallback_install_dir,
        strict=not quick_update,
    )

    # 命令行传入的旧版本号优先
    if args.old_version:
        old_version = args.old_version

    # -- 模式修正 --
    if quick_update:
        mode = "update"

    # 自动检测卸载模式：程序名为 uninst.exe / uninstall.exe / uninstaller.exe
    if mode == "install" and _is_uninstaller_exe():
        mode = "uninstall"

    # 非卸载模式下，注册表命中 → 自动进入更新模式
    if mode != "uninstall" and install_dir is not None:
        mode = "update"

    if mode == "uninstall" and install_dir is None:
        print("未找到已安装的程序", file=sys.stderr)
        sys.exit(1)

    if mode == "install" and install_dir is None:
        install_dir = get_default_install_dir()

    # -- 创建 App --
    log_path = _setup_log()
    logger.info("Installer started, version=%s", VERSION)
    _install_success = False

    app = QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # 全局文本渲染 — Windows ClearType
    QQuickWindow.setTextRenderType(QQuickWindow.NativeTextRendering)

    # -- 创建 Coordinator + Presenters --
    engine = QQmlApplicationEngine()
    coord = AppCoordinator()
    coord.mode = mode
    coord.quick_update = quick_update
    coord.install_dir = str(install_dir)
    if old_version:
        coord.old_version = old_version

    welcome_presenter = WelcomePresenter(coord)
    directory_presenter = DirectoryPresenter(coord)
    confirm_presenter = ConfirmPresenter(coord)
    progress_presenter = ProgressPresenter(coord)
    finish_presenter = FinishPresenter(coord)

    _presenters = [
        coord,
        welcome_presenter,
        directory_presenter,
        confirm_presenter,
        progress_presenter,
        finish_presenter,
    ]

    def _on_install_finished(ok: bool) -> None:
        nonlocal _install_success
        _install_success = ok
        if ok:
            logger.info("Installation completed successfully")
        else:
            logger.error("Installation failed")

    coord.installFinished.connect(lambda ok, _msg: _on_install_finished(ok))

    # -- 加载 QML --
    ctx = engine.rootContext()
    ctx.setContextProperty("WelcomePresenter", welcome_presenter)
    ctx.setContextProperty("DirectoryPresenter", directory_presenter)
    ctx.setContextProperty("ConfirmPresenter", confirm_presenter)
    ctx.setContextProperty("ProgressPresenter", progress_presenter)
    ctx.setContextProperty("FinishPresenter", finish_presenter)
    ctx.setContextProperty("Coordinator", coord)

    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(QUrl.fromLocalFile(str(qml_dir / "main.qml")))

    if not engine.rootObjects():
        print("QML 加载失败", file=sys.stderr)
        sys.exit(-1)

    # 快速更新：直接跳到进度页
    if quick_update:
        coord.navigate_to("progress")
        coord.start_action()
    elif mode == "uninstall":
        coord.navigate_to("confirm")
    elif mode == "update":
        coord.navigate_to("welcome")

    app.exec()

    if _install_success:
        try:
            log_path.unlink(missing_ok=True)
        except OSError:
            pass
    else:
        logger.info("Log preserved at: %s", log_path)

    # 强制同步销毁 QML 引擎
    shiboken6.delete(engine)


if __name__ == "__main__":
    main()