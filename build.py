"""构建脚本
========
用法:
    python build.py                      # 默认 alpha 渠道，自动递增
    python build.py --clear              # 清理所有 alpha 旧产物，构建新 alpha
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


def clean(channel: str, num: int, clear_all: bool = False):
    """清理旧构建产物。

    Args:
        channel: 发布渠道
        num: 迭代号
        clear_all: True 时清理同渠道所有旧产物，False 仅清理同渠道同版本号
    """
    # 清理 build 临时目录
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    dist_dir = ROOT / "dist"
    if not dist_dir.exists():
        print("无需清理（dist 目录不存在）")
        return

    if clear_all:
        # 清理同渠道所有旧产物
        prefix = f"GenshinDogFoodSweeper-{channel}-"
        cleaned = 0
        for d in dist_dir.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                shutil.rmtree(d)
                print(f"已清理旧产物: {d.name}")
                cleaned += 1
        if cleaned == 0:
            print("无需清理（无同渠道旧产物）")
    else:
        # 只清理同渠道同版本号的旧产物
        versioned_dist = dist_dir / f"GenshinDogFoodSweeper-{channel}-{num}"
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
        default=0,
        help="渠道内迭代号 (默认: 自动递增)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清理同渠道所有旧产物后构建新版本",
    )
    args = parser.parse_args()

    # 自动递增：检测 dist/ 下已有同渠道产物，取最大号 +1
    if args.num == 0:
        dist_dir = ROOT / "dist"
        max_num = 0
        if dist_dir.exists():
            for d in dist_dir.iterdir():
                if d.is_dir() and d.name.startswith(f"GenshinDogFoodSweeper-{args.channel}-"):
                    try:
                        n = int(d.name.rsplit("-", 1)[-1])
                        max_num = max(max_num, n)
                    except ValueError:
                        pass
        args.num = max_num + 1

    return args


if __name__ == "__main__":
    args = parse_args()
    clean(args.channel, args.num, clear_all=args.clear)
    write_channel(args.channel, args.num)
    build()
    post_build(args.channel, args.num)
    print(f"构建完成！渠道: {args.channel}.{args.num}")
    print(f"产物在 dist/GenshinDogFoodSweeper-{args.channel}-{args.num}/ 目录")