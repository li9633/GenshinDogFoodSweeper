"""
模板注册表（纯数据文件）
======================
key → 文件名 的映射。key 为中文可读名称，值为 templates 目录下的 PNG 文件名。

将来添加新模板只需在此文件新增一行，无需修改 TemplateManager 逻辑。
未在此注册的 PNG 文件也会被 TemplateManager 自动发现（key = 文件名去扩展名）。
"""

REGISTRY: dict[str, str] = {
    "背包图标": "backpack.png",
    "丢弃按钮": "discard.png",
    "关闭按钮": "close.png",
}
