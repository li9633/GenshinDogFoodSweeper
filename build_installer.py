"""构建安装程序
============
先运行 build.py 生成主 App 产物，再运行本脚本打包安装程序。

用法:
    python build_installer.py --app-dist dist/GenshinDogFoodSweeper-v0.9.38-release.1-abc1234
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
INSTALLER_DIR = ROOT / "installer"
INSTALLER_SPEC = INSTALLER_DIR / "installer.spec"
TOOLS_DIR = INSTALLER_DIR / "tools"


def _ensure_7za() -> Path:
    """确保 7za.exe 存在（需手动放置到 installer/tools/7za.exe）"""
    seven_za = TOOLS_DIR / "7za.exe"
    if not seven_za.exists():
        raise FileNotFoundError(
            f"未找到 7za.exe，请手动放置到 {seven_za}"
        )
    print(f"7za.exe 已就绪: {seven_za}")
    return seven_za


def _compress_app(app_dist: Path) -> Path:
    """将 App 产物目录压缩为 app.7z"""
    _ensure_7za()
    seven_za = TOOLS_DIR / "7za.exe"
    archive = app_dist.parent / "app.7z"

    print(f"压缩 App 产物: {app_dist.name} → app.7z")
    subprocess.run(
        [str(seven_za), "a", "-mx=9", "-mmt=on", "-y",
         str(archive.resolve()),
         str(app_dist.resolve()) + "\\*"],
        check=True,
    )
    print(f"app.7z 已生成: {archive}")
    return archive


def build_installer(app_7z: Path, setup_name: str, output_dir: Path) -> Path:
    """构建安装程序，返回 setup.exe 路径"""
    _ensure_7za()
    _generate_spec(app_7z, setup_name)

    print("打包安装程序...")
    subprocess.run(
        ["pyinstaller", "--clean", "-y", str(INSTALLER_SPEC)],
        check=True,
        cwd=str(ROOT),
    )

    setup_path = ROOT / "dist" / f"{setup_name}.exe"
    if setup_path.exists():
        dest = output_dir / f"{setup_name}.exe"
        shutil.move(str(setup_path), str(dest))
        print(f"安装程序已生成: {dest}")
        return dest

    raise FileNotFoundError(f"未找到安装程序产物: {setup_path}")


def _generate_spec(app_7z: Path, setup_name: str) -> None:
    """生成 PyInstaller spec 文件"""

    # 递归收集 QML 文件及 qmldir
    qml_dir = INSTALLER_DIR / "qml"
    qml_entries: list[str] = []
    for f in sorted(qml_dir.rglob("*")):
        if f.is_dir():
            continue
        rel = f.relative_to(qml_dir)
        qml_entries.append(
            f'        ("{f.resolve().as_posix()}", "qml/{rel.parent.as_posix()}")'
        )

    seven_za = TOOLS_DIR / "7za.exe"

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ("{app_7z.resolve().as_posix()}", "."),
        ("{seven_za.resolve().as_posix()}", "tools"),
{",\n".join(qml_entries)},
    ],
    hiddenimports=[
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickLayouts',
        'PySide6.QtQuickDialogs',
        'PySide6.QtWidgets',
        'installer.installer_logic',
        'installer.presenters.installer_presenter',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'paddle', 'paddleocr', 'cv2', 'numpy', 'PIL',
        'sqlalchemy', 'fastapi', 'uvicorn', 'pydantic',
        'pydirectinput', 'pyautogui', 'pynput',
        'requests', 'loguru', 'rapidfuzz',
        'aistudio_sdk', 'adodbapi', 'altgraph',
        'Crypto', 'cryptography', 'OpenSSL',
        'pystray', 'pydantic_settings',
        'tkinter', 'unittest', 'test',
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='{setup_name}',
    icon=None,
    debug=False,
    strip=True,
    upx=True,
    console=False,
)
'''
    INSTALLER_SPEC.write_text(spec_content, encoding="utf-8")
    print(f"已生成 spec: {INSTALLER_SPEC}")


def _create_dummy_app_7z() -> Path:
    """创建空的 app.7z，用于测试安装程序打包体积"""
    _ensure_7za()
    seven_za = TOOLS_DIR / "7za.exe"
    dummy_dir = ROOT / "dist" / "_empty_app"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    (dummy_dir / "dummy.txt").write_text("empty")
    archive = ROOT / "dist" / "app.7z"
    subprocess.run(
        [str(seven_za), "a", "-mx=0", "-y",
         str(archive.resolve()),
         str(dummy_dir.resolve()) + "\\*"],
        check=True,
    )
    shutil.rmtree(dummy_dir, ignore_errors=True)
    print(f"空 app.7z 已生成: {archive}")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建安装程序")
    parser.add_argument("--app-dist", type=str, default=None, help="主 App 产物目录")
    parser.add_argument("--empty", action="store_true", help="空打包，仅测试安装程序体积")
    args = parser.parse_args()

    if args.empty:
        app_7z = _create_dummy_app_7z()
        build_installer(app_7z, "GenshinDogFoodSweeper-empty-setup", ROOT / "dist")
        app_7z.unlink(missing_ok=True)
    elif args.app_dist:
        app_dist = Path(args.app_dist)
        app_7z = _compress_app(app_dist)
        build_installer(app_7z, f"{app_dist.name}-setup", app_dist.parent)
        app_7z.unlink(missing_ok=True)
    else:
        parser.error("必须指定 --app-dist 或 --empty")