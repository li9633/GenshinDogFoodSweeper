"""构建安装程序
============
先运行 build.py 生成主 App 产物，再运行本脚本打包安装程序。

用法:
    # 从目录打包（自动压缩，默认删除中间产物 app.7z）
    python build_installer.py --path dist/GenshinDogFoodSweeper-v0.9.38-release.1-abc1234

    # 从目录打包 + 保留 app.7z + 自定义文件名
    python build_installer.py --path dist/... --keep --name "MyApp-setup"

    # 从已有 .7z 打包 + 自定义文件名
    python build_installer.py --zip dist/app.7z --name "MyApp-setup"

    # 空打包（测试安装程序体积）
    python build_installer.py --empty
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
INSTALLER_DIR = ROOT / "installer"
INSTALLER_SPEC = INSTALLER_DIR / "installer.spec"
UNINSTALLER_SPEC = INSTALLER_DIR / "uninstaller.spec"
TOOLS_DIR = INSTALLER_DIR / "tools"
DISPOSABLE = ROOT / "temp" / "disposable"

from common.paths import IMAGE
from common.resources import Resource


def _ensure_7za() -> Path:
    """确保 7za.exe 存在（需手动放置到 installer/tools/7za.exe）"""
    seven_za = TOOLS_DIR / "7za.exe"
    if not seven_za.exists():
        raise FileNotFoundError(f"未找到 7za.exe，请手动放置到 {seven_za}")
    print(f"7za.exe 已就绪: {seven_za}")
    return seven_za


def _compress_app(app_dist: Path) -> Path:
    """将 App 产物目录压缩为 app.7z"""
    archive = app_dist.parent / "app.7z"

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
    """构建安装程序，返回 setup.exe 路径

    流程:
        1. 构建 uninst.exe（小体积，无 app.7z，独立图标）
        2. 构建 setup.exe（内嵌 uninst.exe + app.7z）
    """
    _ensure_7za()

    # -- 步骤1: 构建 uninst.exe --
    _generate_uninstaller_spec()
    uninst_dist = DISPOSABLE / "uninst_dist"
    print("构建 uninst.exe ...")
    subprocess.run(
        [
            "pyinstaller", "--clean", "-y",
            "--distpath", str(uninst_dist.resolve()),
            "--workpath", str((DISPOSABLE / "uninst_build").resolve()),
            str(UNINSTALLER_SPEC),
        ],
        check=True,
        cwd=str(ROOT),
    )
    uninst_exe = uninst_dist / "uninst.exe"
    if not uninst_exe.exists():
        raise FileNotFoundError("uninst.exe 构建失败")
    print(f"uninst.exe 构建完成: {uninst_exe}")

    # -- 步骤2: 构建 setup.exe --
    _generate_spec(app_7z, setup_name, one_dir, uninst_exe=uninst_exe)

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
            uninst_exe.unlink(missing_ok=True)
            print(f"安装程序已生成: {dest_dir / f'{setup_name}.exe'}")
            return dest_dir / f"{setup_name}.exe"
    else:
        setup_path = ROOT / "dist" / f"{setup_name}.exe"
        if setup_path.exists():
            dest = output_dir / f"{setup_name}.exe"
            shutil.move(str(setup_path), str(dest))
            uninst_exe.unlink(missing_ok=True)
            print(f"安装程序已生成: {dest}")
            return dest

    raise FileNotFoundError(f"未找到安装程序产物: {setup_path}")


def _generate_spec(
    app_7z: Path,
    setup_name: str,
    one_dir: bool = False,
    *,
    uninst_exe: Path | None = None,
) -> None:
    """生成安装程序 PyInstaller spec 文件"""
    installer_icon = Resource.INSTALLER_ICON_ICO

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

    icon_image_dir = IMAGE / "GenshinDogFoodSweeper-icon"
    icon_image_dest = "resources/image/GenshinDogFoodSweeper-icon"

    seven_za = TOOLS_DIR / "7za.exe"
    disposable_as_win = str(DISPOSABLE.resolve())

    # uninst.exe 行
    uninst_line = ""
    if uninst_exe and uninst_exe.exists():
        uninst_line = f'        ("{uninst_exe.resolve().as_posix()}", "."),'

    icon_line = f"    icon='{installer_icon.as_posix()}'," if installer_icon.exists() else "    icon=None,"

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=['.', r'{disposable_as_win}'],
    binaries=[
        ("{seven_za.resolve().as_posix()}", "tools"),
    ],
    datas=[
        ("{app_7z.resolve().as_posix()}", "."),
{uninst_line}
        ("{icon_image_dir.resolve().as_posix()}", "{icon_image_dest}"),
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
{icon_line}
    debug=False,
    strip=False,
    upx=False,
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


def _generate_uninstaller_spec() -> None:
    """生成卸载程序 PyInstaller spec 文件（不含 app.7z，体积更小）"""
    uninstaller_icon = Resource.UNINSTALLER_ICON_ICO
    icon_image_dir = IMAGE / "GenshinDogFoodSweeper-icon"
    icon_image_dest = "resources/image/GenshinDogFoodSweeper-icon"

    qml_dir = INSTALLER_DIR / "qml"
    qml_entries: list[str] = []
    for f in sorted(qml_dir.rglob("*")):
        if f.is_dir():
            continue
        rel = f.relative_to(qml_dir)
        qml_entries.append(
            f'        ("{f.resolve().as_posix()}", "qml/{rel.parent.as_posix()}")'
        )

    icon_line = f"    icon='{uninstaller_icon.as_posix()}'," if uninstaller_icon.exists() else "    icon=None,"
    disposable_as_win = str(DISPOSABLE.resolve())

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=['.', r'{disposable_as_win}'],
    binaries=[],
    datas=[
        ("{icon_image_dir.resolve().as_posix()}", "{icon_image_dest}"),
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
    a.binaries,
    a.datas,
    name='uninst',
{icon_line}
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
'''
    UNINSTALLER_SPEC.write_text(spec_content, encoding="utf-8")
    print(f"已生成 uninstaller spec: {UNINSTALLER_SPEC}")


def _cleanup_disposable() -> None:
    """删除临时生成的文件"""
    # 构建时生成的 spec
    if UNINSTALLER_SPEC.exists():
        UNINSTALLER_SPEC.unlink()
        print(f"已清理临时文件: {UNINSTALLER_SPEC}")
    # 中间产物 uninst.exe 及其构建目录
    for d in [DISPOSABLE / "uninst_dist", DISPOSABLE / "uninst_build"]:
        if d.exists():
            shutil.rmtree(d)
            print(f"已清理临时目录: {d}")


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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--path", type=str, help="主 App 产物目录（自动压缩为 .7z 后打包）")
    group.add_argument("--zip", type=str, help="已有的 .7z 压缩包（直接打包，不压缩）")
    group.add_argument("--empty", action="store_true", help="空打包，仅测试安装程序体积")
    parser.add_argument(
        "--keep", action="store_true",
        help="配合 --path 使用，构建后保留中间产物 app.7z",
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="自定义安装程序文件名（不含 .exe 后缀），默认自动生成",
    )
    args = parser.parse_args()

    # --keep 仅在 --path 模式下有意义
    if args.keep and not args.path:
        print("警告: --keep 仅在 --path 模式下生效，已忽略")

    if args.empty:
        app_7z = _create_dummy_app_7z()
        setup_name = args.name or "GenshinDogFoodSweeper-empty-setup"
        output_dir = ROOT / "dist"
        one_dir = True
    elif args.path:
        app_dist = Path(args.path)
        if not app_dist.is_dir():
            parser.error(f"--path 指定的目录不存在: {app_dist}")
        app_7z = _compress_app(app_dist)
        setup_name = args.name or f"{app_dist.name}-setup"
        output_dir = app_dist.parent
        one_dir = False
        build_installer(app_7z, setup_name, output_dir, one_dir=one_dir)
        if not args.keep:
            app_7z.unlink(missing_ok=True)
            print(f"已删除中间产物: {app_7z}")
        else:
            print(f"已保留中间产物: {app_7z}")
        raise SystemExit(0)
    else:
        app_7z = Path(args.zip)
        if not app_7z.is_file():
            parser.error(f"--zip 指定的文件不存在: {app_7z}")
        if app_7z.suffix.lower() != ".7z":
            parser.error(f"--zip 需要 .7z 文件，但得到: {app_7z}")
        setup_name = args.name or f"{app_7z.stem}-setup"
        output_dir = app_7z.parent
        one_dir = False

    build_installer(app_7z, setup_name, output_dir, one_dir=one_dir)