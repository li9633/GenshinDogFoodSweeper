"""Phase 3 — Zip 发布包"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from build_support.config import BuildConfig


def create_zip(config: BuildConfig) -> Path:
    """Phase 3：将 setup.exe + version.txt 打包为 .zip"""
    assert config.setup_exe is not None, "setup.exe 尚未构建"

    output_dir = config.output_dir
    zip_name = config.zip_name
    dist_name = config.dist_dir_name

    # 在临时目录中整理发布文件
    bundle_dir = output_dir / f"_zip_{dist_name}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 复制 setup.exe
        dest_setup = bundle_dir / config.setup_exe.name
        shutil.copy2(config.setup_exe, dest_setup)

        # 生成 version.txt
        version_txt = bundle_dir / "version.txt"
        version_txt.write_text(
            f"名称: {dist_name}\n"
            f"渠道: {config.channel}\n"
            f"版本: {dist_name}\n"
            f"构建时间: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Git Commit: {config.commit_hash or 'N/A'}\n",
            encoding="utf-8",
        )

        # 打包为 .zip
        zip_path = output_dir / zip_name
        base = str(zip_path.resolve())
        root_dir = str(bundle_dir.resolve())
        shutil.make_archive(base, "zip", root_dir)

        expected = output_dir / f"{zip_name}.zip"
        print(f"发布包已生成: {expected}")
        return expected

    finally:
        shutil.rmtree(bundle_dir, ignore_errors=True)