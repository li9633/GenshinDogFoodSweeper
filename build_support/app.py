"""Phase 1 — 主 App PyInstaller 打包"""

from __future__ import annotations

import shutil
from pathlib import Path

from build_support.config import (
    BuildConfig,
    auto_increment_num,
    clean_channel,
    write_channel,
)
from build_support.utils import (
    CHANNEL_FILE,
    PROJECT,
    SPEC_FILE,
    rmfile,
    rmtree,
    run_pyinstaller,
)
from common.paths import BUILD_DIR, ROOT


def build_app(config: BuildConfig) -> Path:
    """Phase 1：PyInstaller 打包主 App，返回产物目录路径"""

    # 确定渠道号
    if config.clear:
        config.channel_num = clean_channel(config.channel)
        print(f"{config.channel} 渠道本次构建为第 {config.channel_num} 次")
    else:
        config.channel_num = config.channel_num or auto_increment_num(config.channel)

    # 写入渠道配置（供运行时 common/version.py 读取）
    if not config.commit_hash:
        from build_support.utils import get_git_hash
        config.commit_hash = get_git_hash()
    write_channel(config)

    # PyInstaller 打包
    print(f"开始打包主 App … (渠道: {config.channel}.{config.channel_num})")
    run_pyinstaller(SPEC_FILE)

    # 后处理
    _post_build(config)

    return config.app_dist  # type: ignore[return-value]


def _post_build(config: BuildConfig) -> None:
    rmtree(BUILD_DIR)
    print("已删除 build 目录")
    rmfile(CHANNEL_FILE)
    print("已清理渠道配置文件")

    default_dist = ROOT / "dist" / PROJECT
    versioned_dist = ROOT / "dist" / config.dist_dir_name
    if default_dist.exists():
        shutil.move(str(default_dist), str(versioned_dist))
        print(f"产物已重命名: {default_dist.name} → {versioned_dist.name}")
        config.app_dist = versioned_dist
    else:
        raise FileNotFoundError(f"未找到产物目录 {default_dist}")