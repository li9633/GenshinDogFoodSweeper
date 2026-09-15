"""Phase 2 — 安装程序 (setup.exe) 构建"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from build_support.utils import ensure_7za, rmtree, run_pyinstaller
from common.paths import (
    IMAGE,
    INSTALLER_DIR,
    INSTALLER_QML,
    INSTALLER_TOOLS,
    ROOT,
    TEMP_DISPOSABLE,
)
from common.resources import Resource

_INSTALLER_MAIN = INSTALLER_DIR / "main.py"

_SPEC_INSTALLER = TEMP_DISPOSABLE / "installer.spec"
_SPEC_UNINSTALLER = TEMP_DISPOSABLE / "uninstaller.spec"


def build_installer(config: BuildConfig) -> Path:  # type: ignore[name-defined]  # noqa: F821
    """Phase 2：构建 setup.exe，返回 setup.exe 路径"""
    ensure_7za()
    TEMP_DISPOSABLE.mkdir(parents=True, exist_ok=True)

    # 步骤1: 构建 uninst.exe（产物在 TEMP_DISPOSABLE/uninst_dist/）
    uninst_exe = _build_uninst_exe()

    # 步骤2: 构建 setup.exe（内嵌 app.7z + uninst.exe）
    setup_exe = _build_setup_exe(config, uninst_exe)

    # 清理 TEMP_DISPOSABLE 下所有临时产物
    rmtree(TEMP_DISPOSABLE)
    print("已清理临时目录: temp/disposable")

    return setup_exe


def compress_app(app_dist: Path) -> Path:
    """将 App 产物目录压缩为 app.7z"""
    seven_za = ensure_7za()
    archive = app_dist.parent / "app.7z"
    print(f"压缩 App 产物: {app_dist.name} → app.7z")
    subprocess.run(
        [str(seven_za), "a", "-mx=9", "-mmt=on", "-y",
         str(archive.resolve()), str(app_dist.resolve()) + "\\*"],
        check=True,
    )
    print(f"app.7z 已生成: {archive}")
    return archive


def create_empty_7z() -> Path:
    """创建空的 app.7z，用于测试安装程序打包体积"""
    seven_za = ensure_7za()
    dummy_dir = TEMP_DISPOSABLE / "_empty_app"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    (dummy_dir / "dummy.txt").write_text("empty")
    archive = ROOT / "dist" / "app.7z"
    subprocess.run(
        [str(seven_za), "a", "-mx=0", "-y",
         str(archive.resolve()), str(dummy_dir.resolve()) + "\\*"],
        check=True,
    )
    rmtree(dummy_dir)
    print(f"空 app.7z 已生成: {archive}")
    return archive


# ────────────────────────────────
# 内部实现
# ────────────────────────────────

def _build_uninst_exe() -> Path:
    """构建卸载程序 uninst.exe（小体积，不含 app.7z）"""
    _generate_uninstaller_spec()
    uninst_dist = TEMP_DISPOSABLE / "uninst_dist"
    print("构建 uninst.exe ...")
    run_pyinstaller(
        _SPEC_UNINSTALLER,
        distpath=str(uninst_dist.resolve()),
        workpath=str((TEMP_DISPOSABLE / "uninst_build").resolve()),
    )
    uninst_exe = uninst_dist / "uninst.exe"
    if not uninst_exe.exists():
        raise FileNotFoundError("uninst.exe 构建失败")
    print(f"uninst.exe 构建完成: {uninst_exe}")
    return uninst_exe


def _build_setup_exe(config: BuildConfig, uninst_exe: Path) -> Path:  # type: ignore[name-defined]  # noqa: F821
    """构建 setup.exe（内嵌 app.7z + uninst.exe）"""
    app_7z = config.app_7z
    assert app_7z is not None

    _generate_installer_spec(config, uninst_exe)

    print("打包安装程序 …")
    run_pyinstaller(_SPEC_INSTALLER)

    output_dir = config.output_dir
    setup_name = config.setup_name
    setup_path = ROOT / "dist" / f"{setup_name}.exe"

    if setup_path.exists():
        dest = output_dir / f"{setup_name}.exe"
        shutil.move(str(setup_path), str(dest))
        print(f"安装程序已生成: {dest}")
        return dest

    raise FileNotFoundError(f"未找到安装程序产物: {setup_path}")


# ────────────────────────────────
# Spec 生成（写入 temp/disposable/）
# ────────────────────────────────

def _collect_qml_entries() -> list[str]:
    """收集 installer/qml/ 下所有文件（含 qmldir）"""
    entries: list[str] = []
    for f in sorted(INSTALLER_QML.rglob("*")):
        if f.is_dir():
            continue
        rel = f.relative_to(INSTALLER_QML)
        entries.append(
            f'        ("{f.resolve().as_posix()}", "qml/{rel.parent.as_posix()}")'
        )
    return entries


def _generate_installer_spec(config: BuildConfig, uninst_exe: Path) -> None:  # type: ignore[name-defined]  # noqa: F821
    app_7z = config.app_7z
    assert app_7z is not None

    installer_icon = Resource.INSTALLER_ICON_ICO
    icon_line = (
        f"    icon='{installer_icon.as_posix()}',"
        if installer_icon.exists() else "    icon=None,"
    )
    uninst_line = f'        ("{uninst_exe.resolve().as_posix()}", "."),'
    icon_image_dir = IMAGE / "GenshinDogFoodSweeper-icon"
    icon_image_dest = "resources/image/GenshinDogFoodSweeper-icon"
    seven_za = INSTALLER_TOOLS / "7za.exe"
    qml_entries = _collect_qml_entries()

    installer_main = _INSTALLER_MAIN.resolve().as_posix()
    root_posix = ROOT.resolve().as_posix()

    spec = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['{installer_main}'],
    pathex=['{root_posix}'],
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
    name='{config.setup_name}',
{icon_line}
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
'''
    _SPEC_INSTALLER.write_text(spec, encoding="utf-8")
    print(f"已生成 spec: {_SPEC_INSTALLER}")


def _generate_uninstaller_spec() -> None:
    uninstaller_icon = Resource.UNINSTALLER_ICON_ICO
    icon_line = (
        f"    icon='{uninstaller_icon.as_posix()}',"
        if uninstaller_icon.exists() else "    icon=None,"
    )
    icon_image_dir = IMAGE / "GenshinDogFoodSweeper-icon"
    icon_image_dest = "resources/image/GenshinDogFoodSweeper-icon"
    qml_entries = _collect_qml_entries()

    installer_main = _INSTALLER_MAIN.resolve().as_posix()
    root_posix = ROOT.resolve().as_posix()

    spec = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['{installer_main}'],
    pathex=['{root_posix}'],
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
    _SPEC_UNINSTALLER.write_text(spec, encoding="utf-8")
    print(f"已生成 uninstaller spec: {_SPEC_UNINSTALLER}")