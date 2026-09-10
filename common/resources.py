"""资源文件路径

调用方不需要关心具体文件名，只需要知道"我要什么资源"。
所有文件名集中在此处定义，修改时只改这一个文件。

用法：
    from common.resources import Resource

    icon = str(Resource.APP_ICON_PNG)              # 应用图标 PNG
    stats = Resource.ARTIFACT_STATS_JSON.read_text() # 词条模板 JSON
"""

from pathlib import Path

from common.paths import ICONS, IMAGE, TEMPLATES_CONFIG


class Resource:
    """资源文件 — 每个属性返回完整 Path"""

    # ── 应用图标 ──
    APP_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "app-main-icon-v2.png"
    APP_ICON_ICO: Path = ICONS / "app-main-icon-v2.ico"

    # ── 安装器四种模式图标（PNG，QML 页面 + setWindowIcon 展示）──
    INSTALL_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "install-icon-v1.png"
    UNINSTALL_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "uninstall-icon-v1.png"
    UPDATE_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "update-icon-v2.png"
    QUICK_UPDATE_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "quick-update-icon-v2.png"

    # ── 安装器 EXE 打包图标（ICO，PyInstaller icon= 参数，文件名带 er 后缀）──
    INSTALLER_ICON_ICO: Path = ICONS / "installer-icon-v1.ico"
    UNINSTALLER_ICON_ICO: Path = ICONS / "uninstaller-icon-v1.ico"

    # ── 安装器 EXE 图标 PNG 版（临时测试 setWindowIcon）──
    INSTALLER_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "installer-icon-v1.png"
    UNINSTALLER_ICON_PNG: Path = IMAGE / "GenshinDogFoodSweeper-icon" / "uninstaller-icon-v1.png"

    # ── 模板文件 ──
    ARTIFACT_STATS_JSON: Path = TEMPLATES_CONFIG / "artifact_stats.json"
    TEMPLATES_JSON: Path = TEMPLATES_CONFIG / "templates.json"