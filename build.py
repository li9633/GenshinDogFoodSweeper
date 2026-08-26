"""构建脚本 — 等同于 npm run build"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "GenshinDogFoodSweeper.spec"


def clean():
    """清理旧的构建产物"""
    for d in (BUILD_DIR, ROOT / "dist"):
        if d.exists():
            shutil.rmtree(d)
    print("已清理旧构建产物")


def build():
    """运行 PyInstaller 打包"""
    subprocess.run(
        ["pyinstaller", "--clean", "-y", str(SPEC_FILE)],
        check=True,
        cwd=str(ROOT),
    )
    print("打包完成")


def post_build():
    """打包后清理 build 目录"""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    print("已删除 build 目录")


if __name__ == "__main__":
    clean()
    build()
    post_build()
    print("构建完成！产物在 dist/ 目录")
