"""7z 解压，含进度解析"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from installer.core.constants import ProgressCallback
from installer.core.utils import get_own_dir


def _find_7za() -> Path:
    """查找 7za.exe：优先 MEIPASS/tools/，其次 PATH"""
    own = get_own_dir()
    candidates: list[Path] = []

    bundled = own / "tools" / "7za.exe"
    if bundled.exists():
        candidates.append(bundled)

    dev_path = Path(__file__).resolve().parent.parent / "tools" / "7za.exe"
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
        except Exception as e:
            print(f"跳过无效的 7za 候选 {candidate}: {e}", file=sys.stderr)
            continue

    raise FileNotFoundError(
        "未找到可用的 7za.exe，请确保 installer/tools/7za.exe 是有效的可执行文件"
    )


def extract_7z(
    archive: Path, dest: Path, progress_cb: ProgressCallback | None = None
) -> None:
    """解压 .7z 文件到目标目录，通过解析 stdout 报告进度"""
    seven_zip = _find_7za()
    dest.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(seven_zip),
        "x",
        str(archive),
        f"-o{dest!s}",
        "-y",
        "-mmt=on",
    ]
    progress_cb and progress_cb(0, "正在准备解压...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    last_pct = 0
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.rstrip("\n\r")
        m = re.search(r"(\d{1,3})%", line)
        if m:
            pct = int(m.group(1))
            if pct != last_pct:
                last_pct = pct
                progress_cb and progress_cb(pct, f"正在解压... {pct}%")
        if line.startswith("- "):
            filename = line[2:].strip()
            progress_cb and progress_cb(last_pct, f"解压 {filename}")

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"7z 解压失败，返回码: {proc.returncode}")

    progress_cb and progress_cb(100, "解压完成")