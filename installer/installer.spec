# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ("D:/MyCodeProject/GenshinDogFoodSweeper/dist/app.7z", "."),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/tools/7za.exe", "tools"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/InstallerUI/IButton.qml", "qml/InstallerUI"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/InstallerUI/ILabel.qml", "qml/InstallerUI"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/InstallerUI/IProgressBar.qml", "qml/InstallerUI"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/InstallerUI/ITextField.qml", "qml/InstallerUI"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/InstallerUI/qmldir", "qml/InstallerUI"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/InstallerUI/Theme.qml", "qml/InstallerUI"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/main.qml", "qml/."),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/pages/DirectoryPage.qml", "qml/pages"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/pages/FinishPage.qml", "qml/pages"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/pages/ProgressPage.qml", "qml/pages"),
        ("D:/MyCodeProject/GenshinDogFoodSweeper/installer/qml/pages/WelcomePage.qml", "qml/pages"),
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
    hooksconfig={},
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
    name='GenshinDogFoodSweeper-v0.9.38-beta.4-6831d16-setup',
    icon=None,
    debug=False,
    strip=True,
    upx=True,
    console=False,
)
