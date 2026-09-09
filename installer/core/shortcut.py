"""快捷方式创建与删除"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from installer.core.constants import APP_EXE, APP_NAME_CN


def _try_create_shortcut(target: Path, shortcut: Path, description: str = "") -> None:
    try:
        import pythoncom
        from win32com.client import Dispatch

        pythoncom.CoInitialize()
        try:
            shell = Dispatch("WScript.Shell")
            link = shell.CreateShortCut(str(shortcut))
            link.TargetPath = str(target)
            link.WorkingDirectory = str(target.parent)
            if description:
                link.Description = description
            link.Save()
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"创建快捷方式失败: {e}", file=sys.stderr)


def create_shortcuts(install_dir: Path) -> None:
    """创建桌面和开始菜单快捷方式"""
    target = install_dir / APP_EXE
    desktop = Path.home() / "Desktop"
    _try_create_shortcut(target, desktop / f"{APP_NAME_CN}.lnk", APP_NAME_CN)

    start_menu = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / APP_NAME_CN
    )
    start_menu.mkdir(parents=True, exist_ok=True)
    _try_create_shortcut(target, start_menu / f"{APP_NAME_CN}.lnk", APP_NAME_CN)


def remove_shortcuts() -> None:
    desktop = Path.home() / "Desktop"
    for lnk in desktop.glob(f"*{APP_NAME_CN}*.lnk"):
        lnk.unlink(missing_ok=True)
    start_menu = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / APP_NAME_CN
    )
    if start_menu.exists():
        shutil.rmtree(start_menu, ignore_errors=True)