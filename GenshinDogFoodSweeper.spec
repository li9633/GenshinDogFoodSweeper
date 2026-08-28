# -*- mode: python ; coding: utf-8 -*-

import shutil
from pathlib import Path


a = Analysis(
    ['backend\\main.py'],
    pathex=['backend'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtQuickControls2',
        'PySide6.QtWidgets',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'database',
        'database.init_db',
        'database.connection',
        'database.repository',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # PySide6 未使用的模块
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        'PySide6.QtCharts',
        'PySide6.QtQuick3D',
        'PySide6.QtQuick3DUtils',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtLocation',
        'PySide6.QtRemoteObjects',
        'PySide6.QtTextToSpeech',
        # PaddlePaddle 训练专用模块（OCR 推理不需要）
        'paddle.dataset',
        'paddle.distributed',
        'paddle.dist_checkpoint',
        'paddle.fleet',
        'paddle.hapi',
        'paddle.incubate',
        'paddle.io',
        'paddle.jit',
        'paddle.metric',
        'paddle.onnx',
        'paddle.optimizer',
        'paddle.quantization',
        'paddle.regularizer',
        'paddle.callbacks',
        'paddle.checkpoint',
        'paddle.sparse',
        'paddle.text',
        'paddle.geometric',
        'paddle.vision',
        # 其他未使用的第三方库
        'tkinter',
        'unittest',
        'test',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# 过滤掉不需要的二进制文件（约 300MB），项目不使用这些功能
_EXCLUDE_BIN_PATTERNS = (
    'Qt6WebEngine', 'Qt6Pdf', 'Qt6QmlWebEngine',  # Web 引擎 (~195MB)
    'opencv_videoio_ffmpeg',                         # 视频 I/O (~55MB)
    '_avif',                                         # AVIF 格式 (~8MB)
    'pdfium',                                        # PDF 渲染 (~7MB)
    'hf_xet',                                        # HuggingFace XET (~9MB)
)
a.binaries = [
    (name, path, typ)
    for name, path, typ in a.binaries
    if not any(p in name for p in _EXCLUDE_BIN_PATTERNS)
]
print(f'已过滤 {len(_EXCLUDE_BIN_PATTERNS)} 类无关二进制，剩余 {len(a.binaries)} 个')

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GenshinDogFoodSweeper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    uac_admin=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/app.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['*.pyd', '*.dll'],
    name='GenshinDogFoodSweeper',
)

# ---- 复制资源文件到 exe 同级目录 ----
_dist_dir = Path('dist') / 'GenshinDogFoodSweeper'

_qml_src = Path('backend') / 'ui' / 'qml'
if _qml_src.exists():
    shutil.copytree(_qml_src, _dist_dir / 'ui' / 'qml', dirs_exist_ok=True)
    print(f'已复制 QML 资源: {_qml_src} -> {_dist_dir / "ui" / "qml"}')

_tpl_src = Path('resources') / 'templates'
if _tpl_src.exists():
    shutil.copytree(_tpl_src, _dist_dir / 'resources' / 'templates', dirs_exist_ok=True)
    print(f'已复制模板资源: {_tpl_src} -> {_dist_dir / "resources" / "templates"}')

# 复制应用图标
for _icon_name in ('app.ico', 'app.png'):
    _icon_src = Path('resources') / _icon_name
    if _icon_src.exists():
        _dist_dir_res = _dist_dir / 'resources'
        _dist_dir_res.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_icon_src, _dist_dir_res / _icon_name)
        print(f'已复制图标: {_icon_src}')