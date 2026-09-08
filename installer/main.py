r"""安装程序入口
============
PySide6 + QML 安装向导。

用法:
    GenshinDogFoodSweeper-setup.exe                            # GUI 安装向导
    GenshinDogFoodSweeper-setup.exe --mode update              # GUI 更新向导
    GenshinDogFoodSweeper-setup.exe --quick-update --fallback-install-dir "C:\..." --old-version "0.9.3"  # 快速更新
    GenshinDogFoodSweeper-setup.exe --mode uninstall           # GUI 卸载
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

import shiboken6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from installer.installer_logic import (
    APP_NAME,
    get_default_install_dir,
    resolve_directory,
)
from installer.presenters.installer_presenter import InstallerPresenter


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原神狗粮扫荡器 安装程序")
    parser.add_argument(
        "--mode",
        type=str,
        default="install",
        choices=["install", "update", "uninstall"],
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
    if quick_update and mode == "install":
        mode = "update"

    if mode in ("update", "uninstall") and install_dir is None:
        if mode == "uninstall":
            print("未找到已安装的程序", file=sys.stderr)
            sys.exit(1)
        # 更新模式回退到安装模式
        mode = "install"
        quick_update = False
        install_dir = get_default_install_dir()

    if mode == "install" and install_dir is None:
        install_dir = get_default_install_dir()

    if mode == "update" and install_dir is None:
        install_dir = get_default_install_dir()

    # -- 创建 App --
    app = QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # 全局文本渲染 — Windows ClearType
    QQuickWindow.setTextRenderType(QQuickWindow.NativeTextRendering)

    # -- 创建 Presenter --
    engine = QQmlApplicationEngine()
    presenter = InstallerPresenter()
    _presenters = [presenter]  # 保持 Python 引用，防止 GC 回收

    presenter.mode = mode
    presenter.quickUpdate = quick_update
    presenter.installDir = str(install_dir)
    if old_version:
        presenter.oldVersion = old_version

    # -- 加载 QML --
    engine.rootContext().setContextProperty("InstallerPresenter", presenter)

    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(QUrl.fromLocalFile(str(qml_dir / "main.qml")))

    if not engine.rootObjects():
        print("QML 加载失败", file=sys.stderr)
        sys.exit(-1)

    # 快速更新：直接跳到进度页
    if quick_update:
        presenter.navigateRequested.emit("progress")
        presenter.startAction()
    elif mode == "uninstall":
        presenter.navigateRequested.emit("confirm")
    elif mode == "update":
        presenter.navigateRequested.emit("welcome")

    app.exec()

    # 强制同步销毁 QML 引擎
    shiboken6.delete(engine)


if __name__ == "__main__":
    main()
