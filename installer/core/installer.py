"""安装 / 卸载 / 重启 核心流程"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import tempfile
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
    """卸载核心流程：删快捷方式 → 删注册表 → 延迟删除目录

    通过创建临时批处理脚本解决自删除问题：
    uninst.exe 自身运行在安装目录中，无法直接删除自己。
    将删除命令写入 %TEMP% 下的 bat 文件，由独立的 cmd 进程
    在 uninst.exe 退出后执行删除。
    """
    progress_cb and progress_cb(0, "正在删除快捷方式...")
    remove_shortcuts()
    progress_cb and progress_cb(30, "正在删除注册表...")
    remove_registry()
    progress_cb and progress_cb(60, "正在清理安装目录...")

    batch = _generate_cleanup_batch(install_dir, os.getpid())
    subprocess.Popen(
        f'cmd /c "{batch}"',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )
    progress_cb and progress_cb(100, "卸载完成")


def _generate_cleanup_batch(install_dir: Path, parent_pid: int) -> Path:
    """在 %TEMP% 下生成延迟删除的批处理脚本

    等待 uninst.exe 退出后再删除安装目录，避免因进程未退出导致删除失败。
    """
    batch = Path(tempfile.gettempdir()) / "gdf_cleanup.bat"
    batch.write_text(
        f'@echo off\r\n'
        f'cd /d %TEMP%\r\n'
        f':wait\r\n'
        f'tasklist /FI "PID eq {parent_pid}" 2>nul | findstr /I "{parent_pid}" >nul\r\n'
        f'if not errorlevel 1 (\r\n'
        f'    ping 127.0.0.1 -n 2 >nul\r\n'
        f'    goto wait\r\n'
        f')\r\n'
        f'ping 127.0.0.1 -n 2 >nul\r\n'
        f'rmdir /s /q "{install_dir}"\r\n'
        f'del "%~f0"\r\n',
        encoding="ascii",
    )
    return batch


def restart_app(install_dir: Path) -> bool:
    """启动主程序，返回 True 表示成功启动

    使用 ShellExecute + runas 动词，当主程序需要管理员权限时
    会弹出 UAC 提权对话框，而不是直接报错 ERROR_ELEVATION_REQUIRED(740)。
    """
    from installer.core.logging import get_logger as _get_logger
    _log = _get_logger(__name__)

    app_exe = install_dir / APP_EXE
    _log.info("尝试启动: %s", app_exe)
    if not app_exe.exists():
        _log.error("主程序不存在: %s", app_exe)
        return False

    # ShellExecuteW 返回值 > 32 表示成功
    # 常见错误码: 1223 (用户取消UAC), 5 (拒绝访问), 2 (文件未找到)
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,                    # hwnd
        "runas",                 # lpOperation — 触发 UAC 提权
        str(app_exe),            # lpFile
        None,                    # lpParameters
        str(install_dir),        # lpDirectory
        1,                       # nShowCmd (SW_SHOWNORMAL)
    )
    if ret > 32:
        _log.info("主程序已启动 (ShellExecute ret=%d): %s", ret, app_exe)
        return True
    if ret == 1223:
        _log.warning("用户取消了 UAC 提权")
    else:
        _log.error("ShellExecute 失败, ret=%d: %s", ret, app_exe)
    return False