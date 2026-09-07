r"""安装程序入口
============
PySide6 + QML 安装向导。

用法:
    GenshinDogFoodSweeper-setup.exe                     # GUI 安装向导
    GenshinDogFoodSweeper-setup.exe --quick-update --fallback-install-dir "C:\..."  # 快速更新
    GenshinDogFoodSweeper-setup.exe --uninstall         # 卸载
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
    read_registry_version,
    resolve_install_dir,
)
from installer.presenters.installer_presenter import InstallerPresenter


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原神狗粮扫荡器 安装程序")
    parser.add_argument("--quick-update", action="store_true", help="快速更新模式")
    parser.add_argument("--fallback-install-dir", type=str, default=None,
                        help="回退安装目录（由主 App 传入）")
    parser.add_argument("--uninstall", action="store_true", help="卸载")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # -- 卸载模式（无 GUI）--
    if args.uninstall:
        InstallerPresenter.uninstall(args.fallback_install_dir)
        sys.exit(0)

    # -- 快速更新模式 --
    is_update = args.quick_update
    if is_update:
        resolved = resolve_install_dir(args.fallback_install_dir)
        if not resolved:
            is_update = False
            resolved = get_default_install_dir()

    # -- 创建 App --
    app = QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # 全局文本渲染 — Windows ClearType
    QQuickWindow.setTextRenderType(QQuickWindow.NativeTextRendering)

    # -- 创建 Presenter --
    engine = QQmlApplicationEngine()
    presenter = InstallerPresenter()
    _presenters = [presenter]  # 保持 Python 引用，防止 GC 回收
    if is_update:
        presenter.mode = "update"
        presenter.installDir = str(resolved) if resolved else str(get_default_install_dir())
        presenter.oldVersion = read_registry_version()

    # -- 加载 QML --
    engine.rootContext().setContextProperty("InstallerPresenter", presenter)

    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(QUrl.fromLocalFile(str(qml_dir / "main.qml")))

    if not engine.rootObjects():
        print("QML 加载失败", file=sys.stderr)
        sys.exit(-1)

    # 快速更新：直接跳到进度页
    if is_update:
        presenter.navigateRequested.emit("progress")
        presenter.startInstall()

    app.exec()

    # 强制同步销毁 QML 引擎
    shiboken6.delete(engine)


if __name__ == "__main__":
    main()