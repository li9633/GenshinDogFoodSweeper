"""安装程序后端逻辑
================
处理 7z 解压、注册表读写、快捷方式创建、目录验证。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "GenshinDogFoodSweeper"
APP_NAME_CN = "原神狗粮扫荡器"
APP_EXE = f"{APP_NAME}.exe"
REG_UNINST_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

# 进度信号回调类型：Callable[[int, str], None]  (百分比, 状态文字)
from collections.abc import Callable

ProgressCallback = Callable[[int, str], None]


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_own_dir() -> Path:
    """setup.exe 自身所在目录（开发模式为 installer/，打包后为 MEIPASS）"""
    if _is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).parent


def get_default_install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / APP_NAME


# ============================================================
# 注册表
# ============================================================

def _try_import_winreg():
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def read_registry_install_dir() -> Path | None:
    winreg = _try_import_winreg()
    if not winreg:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_UNINST_KEY) as key:
            uninst_path = winreg.QueryValueEx(key, "UninstallString")[0]
            return Path(uninst_path).parent
    except Exception:
        return None


def write_registry(install_dir: Path, version: str) -> None:
    winreg = _try_import_winreg()
    if not winreg:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_UNINST_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME_CN)
            winreg.SetValueEx(
                key, "UninstallString", 0, winreg.REG_SZ,
                str(install_dir / "uninst.exe"),
            )
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(
                key, "DisplayIcon", 0, winreg.REG_SZ,
                str(install_dir / APP_EXE),
            )
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
    except Exception as e:
        print(f"注册表写入失败: {e}", file=sys.stderr)


def remove_registry() -> None:
    winreg = _try_import_winreg()
    if not winreg:
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_UNINST_KEY)
    except Exception as e:
        print(f"注册表删除失败: {e}", file=sys.stderr)
# ============================================================

def _is_app_directory(path: Path) -> bool:
    """检查目录是否包含主程序 exe 和其他关键文件"""
    if not path.exists() or not path.is_dir():
        return False
    if not (path / APP_EXE).exists():
        return False
    return (path / "_internal").exists()


def resolve_install_dir(fallback_dir: str | None = None) -> Path | None:
    """解析安装目录：注册表 → fallback 目录验证 → None"""
    reg_dir = read_registry_install_dir()
    if reg_dir and _is_app_directory(reg_dir):
        return reg_dir

    if fallback_dir:
        fb = Path(fallback_dir)
        if _is_app_directory(fb):
            return fb

    return None


# ============================================================
# 7z 解压
# ============================================================

def _find_7za() -> Path:
    """查找 7za.exe：优先 MEIPASS/tools/，其次 PATH"""
    own = get_own_dir()
    candidates: list[Path] = []

    bundled = own / "tools" / "7za.exe"
    if bundled.exists():
        candidates.append(bundled)

    dev_path = Path(__file__).parent / "tools" / "7za.exe"
    if dev_path.exists() and dev_path != bundled:
        candidates.append(dev_path)

    which = shutil.which("7za.exe") or shutil.which("7z.exe")
    if which:
        candidates.append(Path(which))

    for candidate in candidates:
        try:
            subprocess.run(
                [str(candidate), "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return candidate
        except Exception:
            continue

    raise FileNotFoundError(
        "未找到可用的 7za.exe，请确保 installer/tools/7za.exe 是有效的可执行文件"
    )


def extract_7z(archive: Path, dest: Path, progress_cb: ProgressCallback | None = None) -> None:
    """解压 .7z 文件到目标目录，通过解析 stdout 报告进度"""
    seven_zip = _find_7za()
    dest.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(seven_zip), "x", str(archive), f"-o{dest!s}",
        "-y", "-mmt=on",
    ]
    progress_cb and progress_cb(0, "正在准备解压...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    last_pct = 0
    for line in proc.stdout:  # type: ignore[union-attr]
        m = re.search(r"(\d{1,3})%", line)
        if m:
            pct = int(m.group(1))
            if pct != last_pct:
                last_pct = pct
                progress_cb and progress_cb(pct, f"正在解压... {pct}%")

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"7z 解压失败，返回码: {proc.returncode}")

    progress_cb and progress_cb(100, "解压完成")


# ============================================================
# 快捷方式
# ============================================================

def _try_create_shortcut(target: Path, shortcut: Path, description: str = "") -> None:
    try:
        import pythoncom
        from win32com.client import Dispatch
        pythoncom.CoInitialize()
        shell = Dispatch("WScript.Shell")
        link = shell.CreateShortCut(str(shortcut))
        link.TargetPath = str(target)
        link.WorkingDirectory = str(target.parent)
        if description:
            link.Description = description
        link.Save()
    except Exception as e:
        print(f"创建快捷方式失败: {e}", file=sys.stderr)


def create_shortcuts(install_dir: Path) -> None:
    """创建桌面和开始菜单快捷方式"""
    target = install_dir / APP_EXE
    desktop = Path.home() / "Desktop"
    _try_create_shortcut(target, desktop / f"{APP_NAME_CN}.lnk", APP_NAME_CN)

    start_menu = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME_CN
    )
    start_menu.mkdir(parents=True, exist_ok=True)
    _try_create_shortcut(target, start_menu / f"{APP_NAME_CN}.lnk", APP_NAME_CN)


def remove_shortcuts() -> None:
    desktop = Path.home() / "Desktop"
    for lnk in desktop.glob(f"*{APP_NAME_CN}*.lnk"):
        lnk.unlink(missing_ok=True)
    start_menu = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME_CN
    )
    if start_menu.exists():
        shutil.rmtree(start_menu, ignore_errors=True)


# ============================================================
# 安装信息
# ============================================================

def read_registry_version() -> str:
    """从注册表读取已安装版本号"""
    winreg = _try_import_winreg()
    if not winreg:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_UNINST_KEY) as key:
            return winreg.QueryValueEx(key, "DisplayVersion")[0]
    except Exception:
        return ""


# ============================================================
# 安装 / 更新 / 卸载
# ============================================================

def install(install_dir: Path, version: str, progress_cb: ProgressCallback | None = None) -> None:
    """执行安装：解压 app.7z → 写注册表 → 创建快捷方式 → 写安装信息"""
    own = get_own_dir()
    archive = own / "app.7z"
    if not archive.exists():
        raise FileNotFoundError(f"未找到 app.7z，路径: {archive}")

    # 备份自身为卸载程序
    own_exe = Path(sys.executable) if _is_frozen() else None
    uninst_dest = install_dir / "uninst.exe"

    # 先解压
    extract_7z(archive, install_dir, progress_cb)

    # 复制自身为卸载程序
    if own_exe and own_exe.exists():
        shutil.copy2(own_exe, uninst_dest)

    write_registry(install_dir, version)
    create_shortcuts(install_dir)


def quick_update(install_dir: Path, version: str,
                 progress_cb: ProgressCallback | None = None) -> None:
    """快速更新：与 install 相同，但跳过快捷方式"""
    own = get_own_dir()
    archive = own / "app.7z"
    if not archive.exists():
        raise FileNotFoundError(f"未找到 app.7z，路径: {archive}")

    # 等待主程序退出
    time.sleep(1.5)

    extract_7z(archive, install_dir, progress_cb)

    # 更新卸载程序
    own_exe = Path(sys.executable) if _is_frozen() else None
    uninst_dest = install_dir / "uninst.exe"
    if own_exe and own_exe.exists():
        shutil.copy2(own_exe, uninst_dest)

    write_registry(install_dir, version)


def restart_app(install_dir: Path) -> None:
    """启动主程序"""
    app_exe = install_dir / APP_EXE
    if app_exe.exists():
        subprocess.Popen(
            [str(app_exe)],
            cwd=str(install_dir),
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )


def do_uninstall(install_dir: Path) -> None:
    """执行卸载：删快捷方式 → 删注册表 → 延迟删除目录"""
    remove_shortcuts()
    remove_registry()

    subprocess.Popen(
        f'cmd /c "timeout /t 3 /nobreak >nul & rmdir /s /q \"{install_dir}\""',
        shell=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )