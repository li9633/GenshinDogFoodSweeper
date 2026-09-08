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
DISPOSABLE = ROOT / "temp" / "disposable"

from backend.utils.version import _MAJOR, _MINOR, _PATCH


def _ensure_7za() -> Path:
    """确保 7za.exe 存在（需手动放置到 installer/tools/7za.exe）"""
    seven_za = TOOLS_DIR / "7za.exe"
    if not seven_za.exists():
        raise FileNotFoundError(f"未找到 7za.exe，请手动放置到 {seven_za}")
    print(f"7za.exe 已就绪: {seven_za}")
    return seven_za


def _compress_app(app_dist: Path, skip_if_exists: bool = False) -> Path:
    """将 App 产物目录压缩为 app.7z"""
    archive = app_dist.parent / "app.7z"
    if skip_if_exists and archive.exists():
        print(f"app.7z 已存在，跳过压缩: {archive}")
        return archive

    _ensure_7za()
    seven_za = TOOLS_DIR / "7za.exe"

    print(f"压缩 App 产物: {app_dist.name} → app.7z")
    subprocess.run(
        [
            str(seven_za),
            "a",
            "-mx=9",
            "-mmt=on",
            "-y",
            str(archive.resolve()),
            str(app_dist.resolve()) + "\\*",
        ],
        check=True,
    )
    print(f"app.7z 已生成: {archive}")
    return archive


def build_installer(
    app_7z: Path, setup_name: str, output_dir: Path, one_dir: bool = False
) -> Path:
    """构建安装程序，返回 setup.exe 路径"""
    _ensure_7za()
    _write_installer_version()
    _generate_spec(app_7z, setup_name, one_dir)

    print("打包安装程序...")
    try:
        subprocess.run(
            ["pyinstaller", "--clean", "-y", str(INSTALLER_SPEC)],
            check=True,
            cwd=str(ROOT),
        )
    finally:
        _cleanup_disposable()

    if one_dir:
        setup_dir = ROOT / "dist" / setup_name
        setup_path = setup_dir / f"{setup_name}.exe"
        if setup_path.exists():
            dest_dir = output_dir / setup_name
            if dest_dir != setup_dir:
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                shutil.move(str(setup_dir), str(dest_dir))
            print(f"安装程序已生成: {dest_dir / f'{setup_name}.exe'}")
            return dest_dir / f"{setup_name}.exe"
    else:
        setup_path = ROOT / "dist" / f"{setup_name}.exe"
        if setup_path.exists():
            dest = output_dir / f"{setup_name}.exe"
            shutil.move(str(setup_path), str(dest))
            print(f"安装程序已生成: {dest}")
            return dest

    raise FileNotFoundError(f"未找到安装程序产物: {setup_path}")


def _generate_spec(app_7z: Path, setup_name: str, one_dir: bool = False) -> None:
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
    disposable_as_win = str(DISPOSABLE.resolve())

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=['.', r'{disposable_as_win}'],
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
        'installer.core',
        'installer.core.constants',
        'installer.core.utils',
        'installer.core.registry',
        'installer.core.extract',
        'installer.core.shortcut',
        'installer.core.installer',
        'installer.core.logging',
        'installer.presenters.coordinator',
        'installer.presenters.welcome_presenter',
        'installer.presenters.directory_presenter',
        'installer.presenters.confirm_presenter',
        'installer.presenters.progress_presenter',
        'installer.presenters.finish_presenter',
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
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebChannel',
    ],
    noarchive=False,
    optimize=2,
)

# 过滤掉安装器不需要的二进制文件
_EXCLUDE_BIN_PATTERNS = (
    'Qt6WebEngine', 'Qt6Pdf', 'Qt6QmlWebEngine',
)
a.binaries = [
    (name, path, typ)
    for name, path, typ in a.binaries
    if not any(p in name for p in _EXCLUDE_BIN_PATTERNS)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [] if {one_dir} else a.binaries,
    [] if {one_dir} else a.datas,
    exclude_binaries={one_dir},
    name='{setup_name}',
    icon=None,
    debug=False,
    strip=False if {one_dir} else True,
    upx=True,
    console=False,
)
'''

    if one_dir:
        spec_content += f"""
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{setup_name}',
)
"""
    INSTALLER_SPEC.write_text(spec_content, encoding="utf-8")
    print(f"已生成 spec: {INSTALLER_SPEC}")


def _write_installer_version() -> None:
    """将项目版本号写入 temp/disposable/_installer_version.py，供安装器运行时读取"""
    DISPOSABLE.mkdir(parents=True, exist_ok=True)
    version_file = DISPOSABLE / "_installer_version.py"
    version_file.write_text(
        f"# Auto-generated by build_installer.py\n"
        f'VERSION = "{_MAJOR}.{_MINOR}.{_PATCH}"\n',
        encoding="utf-8",
    )
    print(f"安装器版本已注入: {_MAJOR}.{_MINOR}.{_PATCH}")


def _cleanup_disposable() -> None:
    """删除临时生成的 _installer_version.py"""
    version_file = DISPOSABLE / "_installer_version.py"
    if version_file.exists():
        version_file.unlink()
        print(f"已清理临时文件: {version_file}")


def _create_dummy_app_7z() -> Path:
    """创建空的 app.7z，用于测试安装程序打包体积"""
    _ensure_7za()
    seven_za = TOOLS_DIR / "7za.exe"
    dummy_dir = ROOT / "dist" / "_empty_app"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    (dummy_dir / "dummy.txt").write_text("empty")
    archive = ROOT / "dist" / "app.7z"
    subprocess.run(
        [
            str(seven_za),
            "a",
            "-mx=0",
            "-y",
            str(archive.resolve()),
            str(dummy_dir.resolve()) + "\\*",
        ],
        check=True,
    )
    shutil.rmtree(dummy_dir, ignore_errors=True)
    print(f"空 app.7z 已生成: {archive}")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建安装程序")
    parser.add_argument("--app-dist", type=str, default=None, help="主 App 产物目录")
    parser.add_argument(
        "--empty", action="store_true", help="空打包，仅测试安装程序体积"
    )
    parser.add_argument(
        "--keep-7z", action="store_true", help="构建后保留 app.7z，加速后续测试"
    )
    args = parser.parse_args()

    if args.empty:
        app_7z = _create_dummy_app_7z()
        setup_name = "GenshinDogFoodSweeper-empty-setup"
        output_dir = ROOT / "dist"
        one_dir = True
    elif args.app_dist:
        app_dist = Path(args.app_dist)
        app_7z = _compress_app(app_dist, skip_if_exists=args.keep_7z)
        setup_name = f"{app_dist.name}-setup"
        output_dir = app_dist.parent
        one_dir = False
    else:
        parser.error("必须指定 --app-dist 或 --empty")

    build_installer(app_7z, setup_name, output_dir, one_dir=one_dir)
    if not args.keep_7z:
        app_7z.unlink(missing_ok=True)
        print(f"已删除中间产物: {app_7z}")