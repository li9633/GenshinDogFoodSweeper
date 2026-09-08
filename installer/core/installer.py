"""安装 / 卸载 / 重启 核心流程"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from installer.core.constants import APP_EXE, ProgressCallback
from installer.core.extract import extract_7z
from installer.core.registry import remove_registry, write_registry
from installer.core.shortcut import create_shortcuts, remove_shortcuts
from installer.core.utils import get_own_dir


def _copy_uninstaller(install_dir: Path) -> None:
    """将预构建的 uninst.exe 复制到安装目录"""
    own = get_own_dir()
    src = own / "uninst.exe"
    if not src.exists():
        return
    dst = install_dir / "uninst.exe"
    shutil.copy2(src, dst)


def run_install(
    install_dir: Path,
    version: str,
    progress_cb: ProgressCallback | None = None,
    *,
    skip_shortcuts: bool = False,
) -> None:
    """安装/更新核心流程：解压 app.7z → 复制卸载程序 → 写注册表 → 快捷方式"""
    own = get_own_dir()
    archive = own / "app.7z"
    if not archive.exists():
        raise FileNotFoundError(f"未找到 app.7z，路径: {archive}")

    extract_7z(archive, install_dir, progress_cb)
    _copy_uninstaller(install_dir)
    write_registry(install_dir, version)
    if not skip_shortcuts:
        create_shortcuts(install_dir)


def run_uninstall(
    install_dir: Path,
    progress_cb: ProgressCallback | None = None,
) -> None:
    """卸载核心流程：删快捷方式 → 删注册表 → 延迟删除目录"""
    progress_cb and progress_cb(0, "正在删除快捷方式...")
    remove_shortcuts()
    progress_cb and progress_cb(30, "正在删除注册表...")
    remove_registry()
    progress_cb and progress_cb(60, "正在清理安装目录...")

    subprocess.Popen(
        f'cmd /c "timeout /t 3 /nobreak >nul & rmdir /s /q "{install_dir}""',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )
    progress_cb and progress_cb(100, "卸载完成")


def restart_app(install_dir: Path) -> None:
    """启动主程序"""
    app_exe = install_dir / APP_EXE
    if app_exe.exists():
        subprocess.Popen(
            [str(app_exe)],
            cwd=str(install_dir),
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )