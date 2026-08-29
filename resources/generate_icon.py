"""PNG → ICO 转换脚本
====================
将 AI 生成的 PNG 图标转换为多尺寸 ICO 文件，供 PyInstaller 和 Windows 使用。
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
PNG_PATH = ROOT / "app.png"
ICO_PATH = ROOT / "app.ico"

# ICO 标准尺寸（Windows 常用）
SIZES = [16, 24, 32, 48, 64, 128, 256]


def convert():
    img = Image.open(PNG_PATH)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # 生成各尺寸并保存为 ICO
    img.save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in SIZES if s <= img.width],
    )
    print(f"√ 已生成 ICO: {ICO_PATH} ({ICO_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    convert()
