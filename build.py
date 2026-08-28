"""构建脚本
========
用法:
    python build.py                      # 默认 alpha 渠道
    python build.py --channel release    # 正式版
    python build.py --channel beta --num 3  # 公开测试版第 3 次迭代
"""

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "GenshinDogFoodSweeper.spec"
CHANNEL_FILE = ROOT / "backend" / "utils" / "_build_channel.py"


def clean(channel: str, num: int):
    """清理同渠道的旧构建产物（不删除其他渠道的输出）"""
    # 清理 build 临时目录
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    # 只清理同渠道同版本号的旧产物
    versioned_dist = ROOT / "dist" / f"GenshinDogFoodSweeper-{channel}-{num}"
    if versioned_dist.exists():
        shutil.rmtree(versioned_dist)
        print(f"已清理旧产物: {versioned_dist.name}")
    else:
        print("无需清理（同渠道版本号无旧产物）")


def write_channel(channel: str, channel_num: int):
    """写入构建渠道配置，供 version.py 在运行时读取"""
    CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNEL_FILE.write_text(
        f'# 构建时自动生成，请勿手动编辑\n'
        f'BUILD_CHANNEL = "{channel}"\n'
        f'BUILD_CHANNEL_NUM = {channel_num}\n',
        encoding="utf-8",
    )
    print(f"渠道配置: {channel}.{channel_num}")


def build():
    """运行 PyInstaller 打包"""
    subprocess.run(
        ["pyinstaller", "--clean", "-y", str(SPEC_FILE)],
        check=True,
        cwd=str(ROOT),
    )
    print("打包完成")


def post_build(channel: str, num: int):
    """打包后清理：删除 build 临时目录，重命名产物为渠道版本名"""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    print("已删除 build 目录")

    # 清理临时渠道文件
    if CHANNEL_FILE.exists():
        CHANNEL_FILE.unlink()
        print("已清理渠道配置文件")

    # 重命名产物目录为渠道版本名
    default_dist = ROOT / "dist" / "GenshinDogFoodSweeper"
    versioned_dist = ROOT / "dist" / f"GenshinDogFoodSweeper-{channel}-{num}"
    if default_dist.exists():
        shutil.move(str(default_dist), str(versioned_dist))
        print(f"产物已重命名: {default_dist.name} → {versioned_dist.name}")
    else:
        print(f"警告: 未找到产物目录 {default_dist}")


def parse_args():
    parser = argparse.ArgumentParser(description="构建原神狗粮清扫器")
    parser.add_argument(
        "--channel",
        choices=["dev", "alpha", "beta", "release"],
        default="alpha",
        help="发布渠道 (默认: alpha)",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=1,
        help="渠道内迭代号 (默认: 1)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    clean(args.channel, args.num)
    write_channel(args.channel, args.num)
    build()
    post_build(args.channel, args.num)
    print(f"构建完成！渠道: {args.channel}.{args.num}")
    print(f"产物在 dist/GenshinDogFoodSweeper-{args.channel}-{args.num}/ 目录")