"""安装 / 卸载 / 重启 核心流程"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import tempfile
import time
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


def _kill_main_app() -> None:
    """终止主程序进程 GenshinDogFoodSweeper.exe 及其子进程树

    在卸载前必须结束主程序，否则安装目录中的文件会被锁定，
    导致 rmdir 失败 (The process cannot access the file)。

    使用 taskkill /t 杀死整个进程树（含子进程），
    然后用 tasklist 验证是否真的退出，最多重试 3 次。
    """
    from installer.core.logging import get_logger as _get_logger
    _log = _get_logger(__name__)

    for attempt in range(3):
        remaining = _find_processes_in_dir(install_dir=None)
        if not remaining:
            _log.info("安装目录中无残留进程")
            return

        if attempt == 0:
            _log.info("发现 %d 个进程占用安装目录，正在终止...", len(remaining))
            try:
                subprocess.run(
                    ["taskkill", "/f", "/t", "/im", APP_EXE],
                    capture_output=True,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW")
                    else 0,
                )
            except FileNotFoundError:
                _log.warning("taskkill 未找到，跳过终止主程序")
                return
            except subprocess.SubprocessError as e:
                _log.warning("终止主程序失败: %s", e)
        else:
            _log.info("等待进程退出 (第 %d 次检查)...", attempt)
            time.sleep(2)

    remaining = _find_processes_in_dir(install_dir=None)
    if remaining:
        _log.warning("仍有 %d 个进程未退出: %s", len(remaining), remaining)


def _find_processes_in_dir(install_dir: Path | None) -> list[dict]:
    """查找占用安装目录的进程

    通过 wmic 查询可执行文件路径在安装目录下的进程。

    Args:
        install_dir: 安装目录。为 None 时使用全局 APP_EXE 作为关键词。

    Returns:
        [{pid, name, path}, ...]
    """
    try:
        if install_dir is not None:
            keyword = str(install_dir.resolve())
        else:
            keyword = APP_EXE.replace(".exe", "")

        result = subprocess.run(
            [
                "wmic", "process", "where",
                f'Name like "%{keyword}%" or ExecutablePath like "%{keyword}%"',
                "get", "ProcessId,Name,ExecutablePath",
                "/format:csv",
            ],
            capture_output=True,
            check=False,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )
        processes: list[dict] = []
        for line in result.stdout.strip().splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.strip().split(",")
            if len(parts) >= 4:
                processes.append({
                    "pid": parts[2].strip(),
                    "name": parts[3].strip(),
                    "path": parts[1].strip() if len(parts) > 1 else "",
                })
        return processes
    except (FileNotFoundError, subprocess.SubprocessError):
        return []


def run_uninstall(
    install_dir: Path,
    progress_cb: ProgressCallback | None = None,
) -> None:
    """卸载核心流程：终止主程序 → 删快捷方式 → 删注册表 → 延迟删除目录

    通过创建临时批处理脚本解决自删除问题：
    uninst.exe 自身运行在安装目录中，无法直接删除自己。
    将删除命令写入 %TEMP% 下的 bat 文件，由独立的 cmd 进程
    在 uninst.exe 退出后执行删除。
    """
    progress_cb and progress_cb(0, "正在关闭主程序...")
    _kill_main_app()
    progress_cb and progress_cb(15, "正在删除快捷方式...")
    remove_shortcuts()
    progress_cb and progress_cb(40, "正在删除注册表...")
    remove_registry()
    progress_cb and progress_cb(60, "正在清理安装目录...")

    batch = _generate_cleanup_batch(install_dir, os.getpid())

    # 关键：设置 cwd 为 %TEMP%，避免外层 cmd.exe 继承安装目录作为工作目录，
    # 从而持有安装目录句柄，导致 del/rmdir 失败（文件被占用）。
    # 详见 _generate_cleanup_batch 中 cd /d %TEMP% 仅改变内层 cmd 的 cwd，
    # 外层 shell=True 的 cmd.exe 仍持有安装目录句柄。
    subprocess.Popen(
        ["cmd", "/c", str(batch)],
        cwd=str(Path(tempfile.gettempdir())),
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )
    progress_cb and progress_cb(100, "卸载完成")


def _generate_cleanup_batch(install_dir: Path, parent_pid: int) -> Path:
    """在 %TEMP% 下生成延迟删除的批处理脚本

    等待 uninst.exe 退出后再删除安装目录，避免因进程未退出导致删除失败。

    删除策略：
    1. del /f /s /q 先逐个删除文件（更细粒度，能定位被锁定的文件）
    2. rmdir /s /q 清空剩余空目录
    3. 重试 5 次，每次间隔 3 秒
    4. 失败时列出残留文件 + wmic 诊断
    5. 兜底：PowerShell MoveFileEx 安排重启后删除
    """
    batch = Path(tempfile.gettempdir()) / "gdf_cleanup.bat"
    log = Path(tempfile.gettempdir()) / "gdf_cleanup.log"
    keyword = APP_EXE.replace(".exe", "")

    # PowerShell MoveFileEx 兜底命令
    _ps_movefilex = (
        f'powershell -Command "'
        f'$code = @\\\"\\r\\n'
        f'using System.Runtime.InteropServices;\\r\\n'
        f'public class K32 {{ [DllImport(\\\\\\\"kernel32.dll\\\\\\\", CharSet=CharSet.Unicode)]\\r\\n'
        f'public static extern bool MoveFileEx(string a, string b, uint f); }}'
        f'\\\"@; '
        f'Add-Type -TypeDefinition $code; '
        f'[K32]::MoveFileEx(\\\\\\\"{install_dir}\\\\\\\", $null, 4)"'
        f' >> "{log}" 2>&1'
    )

    batch.write_text(
        f'@echo off\r\n'
        f'chcp 65001 >nul\r\n'
        f'cd /d %TEMP%\r\n'
        f'\r\n'
        f'echo [%date% %time%] 等待进程 {parent_pid} 退出...>> "{log}"\r\n'
        f':wait\r\n'
        f'tasklist /FI "PID eq {parent_pid}" 2>nul | findstr /I "{parent_pid}" >nul\r\n'
        f'if not errorlevel 1 (\r\n'
        f'    ping 127.0.0.1 -n 2 >nul\r\n'
        f'    goto wait\r\n'
        f')\r\n'
        f'echo [%date% %time%] 进程已退出，开始删除安装目录>> "{log}"\r\n'
        f'ping 127.0.0.1 -n 2 >nul\r\n'
        f'\r\n'
        f'set RETRY=0\r\n'
        f':retry\r\n'
        f'del /f /s /q "{install_dir}\\*" >> "{log}" 2>&1\r\n'
        f'rmdir /s /q "{install_dir}" >> "{log}" 2>&1\r\n'
        f'if not exist "{install_dir}" goto done\r\n'
        f'set /a RETRY+=1\r\n'
        f'if %RETRY% LSS 5 (\r\n'
        f'    echo [%date% %time%] 删除失败，第 %RETRY% 次重试...>> "{log}"\r\n'
        f'    ping 127.0.0.1 -n 3 >nul\r\n'
        f'    goto retry\r\n'
        f')\r\n'
        f'echo [%date% %time%] === 删除失败，诊断占用目录的进程 ===>> "{log}"\r\n'
        f'wmic process where "Name like \'%%{keyword}%%\' or ExecutablePath like \'%%{keyword}%%\'" get ProcessId,Name,ExecutablePath /format:csv >> "{log}" 2>&1\r\n'
        f'echo [%date% %time%] 残留文件（可能被锁定）:>> "{log}"\r\n'
        f'dir /s /b "{install_dir}" 2>nul >> "{log}" 2>&1\r\n'
        f'echo [%date% %time%] === 诊断结束 ===>> "{log}"\r\n'
        f'echo [%date% %time%] 删除最终失败，请手动删除: "{install_dir}">> "{log}"\r\n'
        f'echo [%date% %time%] 尝试安排重启后删除...>> "{log}"\r\n'
        f'{_ps_movefilex}\r\n'
        f':done\r\n'
        f'del "%~f0"\r\n',
        encoding="utf-8",
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
    if ret == 1223:
        _log.warning("用户取消了 UAC 提权")
    elif ret > 32:
        _log.info("主程序已启动 (ShellExecute ret=%d): %s", ret, app_exe)
        return True
    else:
        _log.error("ShellExecute 失败, ret=%d: %s", ret, app_exe)
    return False