"""PNG → ICO 转换脚本
====================
将 AI 生成的 PNG 图标转换为多尺寸 ICO 文件。

- PNG：放在 resources/image/，运行时直接使用（更高清）
- ICO：输出到 resources/icons/，仅 PyInstaller 打包 EXE 图标时使用

用法：
    # 单文件转换
    python generate_icon.py --source image/app-main-icon-v2.png --output icons/app-main-icon-v2.ico

    # 批量转换
    python generate_icon.py --dir ./image --outdir ./icons
"""

import argparse
from pathlib import Path

from PIL import Image

# ICO 标准尺寸（Windows 常用）
SIZES = [16, 24, 32, 48, 64, 128, 256]


def png_to_ico(source: Path, dest: Path) -> None:
    img = Image.open(source)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # 先缩放到 ICO 最大尺寸 (256)，再由 sizes 参数自动生成所有子尺寸
    img = img.resize((256, 256), Image.LANCZOS)
    ico_sizes = [(s, s) for s in SIZES]

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="ICO", sizes=ico_sizes)
    print(f"√ 已生成 ICO: {dest} ({dest.stat().st_size:,} bytes) 内含 {len(ico_sizes)} 个尺寸")


def main():
    parser = argparse.ArgumentParser(description="PNG → ICO 图标转换")
    parser.add_argument("--source", help="源 PNG 文件路径")
    parser.add_argument("--output", help="目标 ICO 文件路径")
    parser.add_argument("--dir", help="批量模式：源 PNG 目录")
    parser.add_argument("--outdir", default=".", help="批量模式：输出目录（默认当前目录）")
    args = parser.parse_args()

    if args.dir:
        in_dir = Path(args.dir)
        out_dir = Path(args.outdir)
        for png in sorted(in_dir.glob("*.png")):
            ico = out_dir / f"{png.stem}.ico"
            png_to_ico(png, ico)
        print(f"\n批量转换完成，共 {sum(1 for _ in in_dir.glob('*.png'))} 个文件")
    elif args.source and args.output:
        png_to_ico(Path(args.source), Path(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()