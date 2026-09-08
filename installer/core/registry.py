"""注册表读写与目录验证"""

from __future__ import annotations

import sys
from pathlib import Path

from installer.core.constants import APP_EXE, APP_NAME, APP_NAME_CN, REG_UNINST_KEY


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


def write_registry(install_dir: Path, version: str) -> None:
    winreg = _try_import_winreg()
    if not winreg:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_UNINST_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME_CN)
            winreg.SetValueEx(
                key,
                "UninstallString",
                0,
                winreg.REG_SZ,
                str(install_dir / "uninst.exe"),
            )
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(
                key,
                "DisplayIcon",
                0,
                winreg.REG_SZ,
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
# 目录验证与解析
# ============================================================


def _is_app_directory(path: Path) -> bool:
    """检查目录是否包含主程序 exe 和其他关键文件"""
    if not path.exists() or not path.is_dir():
        return False
    if not (path / APP_EXE).exists():
        return False
    return (path / "_internal").exists()


def resolve_directory(
    fallback_dir: str | None = None,
    *,
    strict: bool = True,
) -> tuple[Path | None, str]:
    """三级级联解析安装目录。

    Args:
        fallback_dir: 命令行传入的回退目录
        strict: True=严格校验（_is_app_directory），False=仅检查存在（快速更新）

    Returns:
        (install_dir, old_version_str)
    """
    # Level 1: 注册表
    reg_dir = read_registry_install_dir()
    if reg_dir and _is_app_directory(reg_dir):
        return reg_dir, read_registry_version()

    # Level 2: --fallback-install-dir
    if fallback_dir:
        fb = Path(fallback_dir)
        if strict and not _is_app_directory(fb):
            return None, ""
        if fb.exists() and fb.is_dir():
            return fb, ""

    # Level 3: 无结果
    return None, ""


def resolve_install_dir(fallback_dir: str | None = None) -> Path | None:
    """解析安装目录：注册表 → fallback 目录验证 → None（兼容旧接口）"""
    result, _ = resolve_directory(fallback_dir, strict=True)
    return result