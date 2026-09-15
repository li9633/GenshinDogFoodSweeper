"""7z 解压，含进度解析"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from installer.core.constants import ProgressCallback
from installer.core.logging import get_logger
from installer.core.utils import get_own_dir

logger = get_logger(__name__)


def _is_valid_pe(path: Path) -> bool:
    """检查文件是否为有效的 Windows PE 且未被截断

    返回 False 如果文件不是 PE 格式，或文件大小不匹配 PE 头中声明的节区范围。
    """
    try:
        file_size = path.stat().st_size
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                return False
            f.seek(0x3C)
            pe_offset = int.from_bytes(f.read(4), "little")
            f.seek(pe_offset)
            if f.read(4) != b"PE\0\0":
                return False
            # 读 NumberOfSections
            f.seek(pe_offset + 6)
            num_sections = int.from_bytes(f.read(2), "little")
            # 读 SizeOfOptionalHeader
            f.seek(pe_offset + 20)
            size_opt = int.from_bytes(f.read(2), "little")
            # 节表起始 = PE 偏移 + 24 + SizeOfOptionalHeader
            section_start = pe_offset + 24 + size_opt
            expected_end = 0
            for i in range(num_sections):
                f.seek(section_start + i * 40 + 20)
                raw_offset = int.from_bytes(f.read(4), "little")
                raw_size = int.from_bytes(f.read(4), "little")
                section_end = raw_offset + raw_size
                expected_end = max(expected_end, section_end)
            return file_size >= expected_end
    except OSError:
        return False


def _find_7za() -> Path:
    """查找捆绑的 7za.exe"""
    own = get_own_dir()
    bundled = own / "tools" / "7za.exe"

    if bundled.exists():
        logger.info("捆绑 7za: %s (size=%d)", bundled, bundled.stat().st_size)
    else:
        dev_path = Path(__file__).resolve().parent.parent / "tools" / "7za.exe"
        if dev_path.exists():
            bundled = dev_path
            logger.info("开发模式 7za: %s (size=%d)", bundled, bundled.stat().st_size)

    if not bundled.exists():
        raise FileNotFoundError(f"未找到 7za.exe: {bundled}")

    if not _is_valid_pe(bundled):
        raise FileNotFoundError(
            f"7za.exe 无效或已截断: {bundled} (size={bundled.stat().st_size})"
        )

    return bundled


def extract_7z(
    archive: Path, dest: Path, progress_cb: ProgressCallback | None = None
) -> None:
    """解压 .7z 文件到目标目录，通过解析 stderr 报告进度

    7za 的 stdout 在连管道时使用块缓冲，导致进度行无法实时获取。
    但 stderr 在 C 运行时中默认无缓冲，因此将所有输出（含进度）重定向到
    stderr（-bso2 -bse2 -bsp2），从 stderr 管道逐块读取即可实时解析。
    7za 输出格式: " 23% 45 - filename"
    """
    dest.mkdir(parents=True, exist_ok=True)
    seven_zip = _find_7za()
    logger.info("使用 7za: %s", seven_zip)

    cmd = [
        str(seven_zip),
        "x",
        str(archive),
        f"-o{dest!s}",
        "-y",
        "-mmt=on",
        "-bso2",
        "-bse2",
        "-bsp2",
    ]
    progress_cb and progress_cb(0, "正在准备解压...")
    logger.debug("执行命令: %s", cmd)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    last_pct = -1
    buf = b""
    while True:
        chunk = proc.stderr.read1(4096)  # type: ignore[union-attr]
        if not chunk:
            break
        buf += chunk
        # 7za 用 \r 覆盖终端行更新进度，可能长时间不输出 \n。
        # 将 \r 也视为行分隔符，确保每个进度片段到达时立即处理。
        buf = buf.replace(b"\r", b"\n")
        while b"\n" in buf:
            line_bytes, buf = buf.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            logger.debug("7za: %s", line)
            m = re.search(r"(\d{1,3})%", line)
            if m:
                pct = int(m.group(1))
                if pct != last_pct:
                    last_pct = pct
                    file_match = re.search(r"-\s+(.+)", line)
                    if file_match:
                        text = f"解压 {file_match.group(1)}"
                    else:
                        text = f"正在解压... {pct}%"
                    progress_cb and progress_cb(pct, text)
                    logger.debug("进度 %d%%: %s", pct, text)

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"7z 解压失败，返回码: {proc.returncode}")

    progress_cb and progress_cb(100, "解压完成")