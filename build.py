"""构建脚本
========
用法:
    python build.py                      # 默认 alpha 渠道，自动递增
    python build.py --clear              # 清理所有 alpha 旧产物，构建新 alpha
    python build.py --channel release    # 正式版
    python build.py --channel beta --num 3  # 公开测试版第 3 次迭代
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "GenshinDogFoodSweeper.spec"
CHANNEL_FILE = ROOT / "backend" / "utils" / "_build_channel.py"

from backend.utils.version import _MAJOR, _MINOR, _PATCH
from backend.utils.version_manager import AppVersion

_PROJECT = "GenshinDogFoodSweeper"


def _get_git_hash() -> str:
    """获取当前 Git 提交的短哈希（7 位），非 git 环境返回空字符串"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


@dataclass
class BuildInfo:
    """构建信息 — 单一数据源，dist_dir_name 由所有字段自动拼接。

    新增字段后只需更新 dist_dir_name 的 f-string，无需修改任何方法签名。
    """

    channel: str = "alpha"
    channel_num: int = 1
    major: int = _MAJOR
    minor: int = _MINOR
    patch: int = _PATCH
    commit_hash: str = ""  # Git 短哈希，构建时自动获取
    extra: str = ""  # 预留扩展字段，如 "portable"、"debug"

    def dist_dir_name(self) -> str:
        """产物目录名，如 'GenshinDogFoodSweeper-v0.9.31-alpha.1-1a2b3c4'"""
        return AppVersion.dist_dir_name(
            _PROJECT,
            self.channel,
            self.channel_num,
            self.commit_hash,
            self.extra,
        )

    def dist_prefix(self) -> str:
        """同渠道同版本前缀，用于匹配旧产物。如 'GenshinDogFoodSweeper-v0.9.31-alpha.'"""
        return AppVersion.dist_prefix(_PROJECT, self.channel)


def clean_channel(channel: str) -> int:
    """删除 dist/ 下指定渠道的所有版本产物，返回最大迭代号 + 1"""
    dist_dir = ROOT / "dist"
    if not dist_dir.exists():
        print("无需清理（dist 目录不存在）")
        return 1

    marker = f"-{channel}."
    max_num = 0
    to_delete: list[Path] = []

    for d in dist_dir.iterdir():
        if not d.is_dir() or not d.name.startswith(_PROJECT):
            continue
        if marker not in d.name:
            continue

        to_delete.append(d)
        idx = d.name.find(marker) + len(marker)
        end = d.name.find("-", idx)
        if end == -1:
            end = len(d.name)
        try:
            n = int(d.name[idx:end])
            max_num = max(max_num, n)
        except ValueError:
            pass

    for d in to_delete:
        shutil.rmtree(d)
        print(f"已清理旧产物: {d.name}")

    if not to_delete:
        print("无需清理（无该渠道旧产物）")

    return max_num + 1


def write_channel(channel: str, channel_num: int, commit_hash: str = ""):
    """写入构建渠道配置，供 version.py 在运行时读取"""
    CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNEL_FILE.write_text(
        f"# 构建时自动生成，请勿手动编辑\n"
        f'BUILD_CHANNEL = "{channel}"\n'
        f"BUILD_CHANNEL_NUM = {channel_num}\n"
        f'BUILD_COMMIT_HASH = "{commit_hash}"\n',
        encoding="utf-8",
    )
    print(
        f"渠道配置: {channel}.{channel_num}"
        + (f" ({commit_hash})" if commit_hash else "")
    )


def build():
    """运行 PyInstaller 打包"""
    subprocess.run(
        ["pyinstaller", "--clean", "-y", str(SPEC_FILE)],
        check=True,
        cwd=str(ROOT),
    )
    print("打包完成")


def post_build(info: BuildInfo):
    """打包后清理：删除 build 临时目录，重命名产物为版本名"""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    print("已删除 build 目录")

    if CHANNEL_FILE.exists():
        CHANNEL_FILE.unlink()
        print("已清理渠道配置文件")

    default_dist = ROOT / "dist" / _PROJECT
    versioned_dist = ROOT / "dist" / info.dist_dir_name()
    if default_dist.exists():
        shutil.move(str(default_dist), str(versioned_dist))
        print(f"产物已重命名: {default_dist.name} → {versioned_dist.name}")
    else:
        print(f"警告: 未找到产物目录 {default_dist}")


def _auto_increment_num(info: BuildInfo) -> int:
    """检测 dist/ 下已有同渠道产物，取最大迭代号 +1"""
    dist_dir = ROOT / "dist"
    max_num = 0
    if dist_dir.exists():
        prefix = info.dist_prefix()
        for d in dist_dir.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                try:
                    n = int(d.name[len(prefix) :].split("-")[0])
                    max_num = max(max_num, n)
                except ValueError:
                    pass
    return max_num + 1


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
    parser.add_argument(
        "--extra",
        type=str,
        default="",
        help="扩展信息，如 portable、debug",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.clear:
        channel_num = clean_channel(args.channel)
        print(f"{args.channel} 渠道本次构建为第 {channel_num} 次")
    else:
        channel_num = args.num or _auto_increment_num(BuildInfo(channel=args.channel))
    info = BuildInfo(
        channel=args.channel,
        channel_num=channel_num,
        commit_hash=_get_git_hash(),
        extra=args.extra,
    )

    write_channel(info.channel, info.channel_num, info.commit_hash)
    build()
    post_build(info)
    print(f"构建完成！渠道: {info.channel}.{info.channel_num}")
    print(f"产物在 dist/{info.dist_dir_name()}/ 目录")