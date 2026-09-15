"""构建脚本
========
一行命令完成：PyInstaller 打包 → 安装程序 → Zip 发布包。

用法:
    python build.py                                      # 最简：alpha 渠道，只打包主 App
    python build.py --installer                          # 打包 + 安装程序
    python build.py --installer --zip                    # 打包 + 安装程序 + zip 发布包
    python build.py --channel release --installer --zip  # 正式版全流程
    python build.py --clear --installer --zip            # 清理旧产物 + 全流程
    python build.py --skip-build --installer --zip       # 跳过打包，用已有 dist 产物
    python build.py --empty --installer                  # 空包测试安装程序体积
    python build.py --installer --zip --keep             # 保留中间产物 app.7z
    python build.py --installer --zip --name "MyRelease" # 自定义文件名
"""

from __future__ import annotations

from build_support.app import build_app
from build_support.config import BuildConfig, find_existing_dist, parse_args
from build_support.installer import build_installer, compress_app, create_empty_7z
from build_support.zip import create_zip


def main(argv: list[str] | None = None) -> None:
    config = parse_args(argv)

    # ═══════════════════════════════════════
    # Phase 1: 主 App 打包
    # ═══════════════════════════════════════

    if config.skip_build:
        if not config.empty:
            config.app_dist = find_existing_dist(config.channel)
    else:
        config.app_dist = build_app(config)
        print(f"Phase 1 完成 → {config.app_dist}")

    # ═══════════════════════════════════════
    # Phase 2: 安装程序
    # ═══════════════════════════════════════

    if config.build_installer:
        if config.empty:
            config.app_7z = create_empty_7z()
        else:
            assert config.app_dist is not None, "app_dist 未设置"
            config.app_7z = compress_app(config.app_dist)

        config.setup_exe = build_installer(config)
        print(f"Phase 2 完成 → {config.setup_exe}")

        if not config.keep and config.app_7z:
            config.app_7z.unlink(missing_ok=True)
            print(f"已删除中间产物: {config.app_7z}")

    # ═══════════════════════════════════════
    # Phase 3: Zip 发布包
    # ═══════════════════════════════════════

    if config.create_zip:
        config.zip_file = create_zip(config)
        print(f"Phase 3 完成 → {config.zip_file}")

    # ═══════════════════════════════════════
    # 摘要
    # ═══════════════════════════════════════

    _print_summary(config)


def _print_summary(config: BuildConfig) -> None:
    print()
    print("=" * 60)
    print("  构建完成")
    print("=" * 60)
    print(f"  渠道:    {config.channel}.{config.channel_num}")
    if config.commit_hash:
        print(f"  Commit:  {config.commit_hash}")
    if config.custom_name:
        print(f"  名称:    {config.custom_name}")
    print("-" * 60)
    if config.app_dist:
        print(f"  [Phase 1] App 产物:    {config.app_dist}")
    if config.setup_exe:
        print(f"  [Phase 2] 安装程序:    {config.setup_exe}")
    if config.app_7z and config.keep:
        print(f"           中间产物:    {config.app_7z}")
    if config.zip_file:
        print(f"  [Phase 3] 发布包:      {config.zip_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()