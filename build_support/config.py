"""构建配置 — BuildConfig + CLI 参数解析 + 渠道管理"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from build_support.utils import CHANNEL_FILE, PROJECT, get_git_hash
from common.constants import APP_NAME_CN
from common.paths import ROOT
from common.version_manager import AppVersion


@dataclass
class BuildConfig:
    # ── 版本信息 ──
    channel: str = "alpha"
    channel_num: int = 1
    commit_hash: str = ""
    extra: str = ""

    # ── 构建开关 ──
    clear: bool = False
    skip_build: bool = False
    build_installer: bool = False
    create_zip: bool = False
    keep: bool = False
    empty: bool = False
    custom_name: str | None = None

    # ── 产物路径（流水线填充）──
    app_dist: Path | None = field(default=None, init=False)
    app_7z: Path | None = field(default=None, init=False)
    setup_exe: Path | None = field(default=None, init=False)
    zip_file: Path | None = field(default=None, init=False)

    # ── 派生属性 ──

    @property
    def dist_dir_name(self) -> str:
        return AppVersion.dist_dir_name(
            PROJECT, self.channel, self.channel_num,
            self.commit_hash, self.extra,
        )

    @property
    def output_base(self) -> str:
        return self.custom_name or self.dist_dir_name

    @property
    def setup_name(self) -> str:
        return f"{self.output_base}-setup"

    @property
    def zip_name(self) -> str:
        return self.output_base

    @property
    def output_dir(self) -> Path:
        return ROOT / "dist"


def parse_args(argv: list[str] | None = None) -> BuildConfig:
    parser = argparse.ArgumentParser(description=f"构建 {APP_NAME_CN}")
    parser.add_argument(
        "--channel", choices=["dev", "alpha", "beta", "release"],
        default="alpha", help="发布渠道 (默认: alpha)",
    )
    parser.add_argument(
        "--num", type=int, default=0,
        help="渠道内迭代号 (默认: 自动递增)",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="清理同渠道所有旧产物后构建",
    )
    parser.add_argument(
        "--extra", type=str, default="",
        help="扩展标签，如 portable",
    )
    parser.add_argument(
        "--installer", action="store_true",
        help="构建安装程序 (setup.exe)",
    )
    parser.add_argument(
        "--zip", action="store_true",
        help="打包 .zip 发布包（隐含 --installer）",
    )
    parser.add_argument(
        "--skip-build", action="store_true",
        help="跳过主 App 打包，复用已有 dist 产物",
    )
    parser.add_argument(
        "--empty", action="store_true",
        help="空包测试（仅与 --installer 一起，不打包主 App）",
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="保留中间产物 (app.7z)",
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="自定义输出文件名前缀（不加后缀）",
    )
    args = parser.parse_args(argv)

    # --zip 隐含 --installer
    if args.zip:
        args.installer = True

    # --empty 隐含 --skip-build
    if args.empty:
        args.skip_build = True
        if not args.installer:
            parser.error("--empty 必须与 --installer 一起使用")

    return BuildConfig(
        channel=args.channel,
        channel_num=args.num,
        commit_hash=get_git_hash(),
        extra=args.extra,
        clear=args.clear,
        skip_build=args.skip_build,
        build_installer=args.installer,
        create_zip=args.zip,
        keep=args.keep,
        empty=args.empty,
        custom_name=args.name,
    )


def write_channel(config: BuildConfig) -> None:
    CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHANNEL_FILE.write_text(
        "# 构建时自动生成，请勿手动编辑\n"
        f'BUILD_CHANNEL = "{config.channel}"\n'
        f"BUILD_CHANNEL_NUM = {config.channel_num}\n"
        f'BUILD_COMMIT_HASH = "{config.commit_hash}"\n',
        encoding="utf-8",
    )
    print(f"渠道配置: {config.channel}.{config.channel_num}")


def clean_channel(channel: str) -> int:
    """删除 dist/ 下指定渠道的旧产物目录，返回最大迭代号 + 1"""
    dist = ROOT / "dist"
    if not dist.exists():
        print("无需清理（dist 目录不存在）")
        return 1

    marker = f"-{channel}."
    max_num = 0
    to_delete: list[Path] = []

    for d in dist.iterdir():
        if not d.is_dir() or not d.name.startswith(PROJECT):
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


def auto_increment_num(channel: str) -> int:
    """检测 dist/ 下已有同渠道产物，取最大迭代号 + 1"""
    dist = ROOT / "dist"
    prefix = AppVersion.dist_prefix(PROJECT, channel)
    max_num = 0
    if dist.exists():
        for d in dist.iterdir():
            if d.is_dir() and d.name.startswith(prefix):
                try:
                    n = int(d.name[len(prefix):].split("-")[0])
                    max_num = max(max_num, n)
                except ValueError:
                    pass
    return max_num + 1


def find_existing_dist(channel: str) -> Path:
    """扫描 dist/ 下匹配渠道的最新产物目录"""
    dist = ROOT / "dist"
    prefix = AppVersion.dist_prefix(PROJECT, channel)
    candidates = sorted(
        [d for d in dist.iterdir() if d.is_dir() and d.name.startswith(prefix)],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"dist/ 下未找到 {channel} 渠道的产物，请先运行 python build.py"
        )
    print(f"复用已有产物: {candidates[0].name}")
    return candidates[0]