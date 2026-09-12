"""构建工具 — 辅助函数"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from common.paths import INSTALLER_TOOLS, ROOT

# 文件级常量（非目录，不适合放在 common/paths.py 中）
CHANNEL_FILE = ROOT / "common" / "_build_channel.py"
SPEC_FILE = ROOT / "GenshinDogFoodSweeper.spec"
PROJECT = "GenshinDogFoodSweeper"


def get_git_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=str(ROOT), check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def ensure_7za() -> Path:
    seven_za = INSTALLER_TOOLS / "7za.exe"
    if not seven_za.exists():
        raise FileNotFoundError(f"未找到 7za.exe，请手动放置到 {seven_za}")
    return seven_za


def run_pyinstaller(spec: Path, *, distpath: str | None = None, workpath: str | None = None) -> None:
    cmd = ["pyinstaller", "--clean", "-y"]
    if distpath:
        cmd += ["--distpath", distpath]
    if workpath:
        cmd += ["--workpath", workpath]
    cmd.append(str(spec))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def rmfile(path: Path) -> None:
    if path.exists():
        path.unlink()