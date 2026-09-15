"""QML ↔ Python 路径转换工具"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


def local_path_from_url(url: str) -> str:
    """把 QML 文件对话框给出的 URL 转成本地路径

    FileDialog/FolderDialog 的 ``selectedFile`` / ``selectedFolder`` 是 ``file://`` URL，
    直接当路径用会带上协议头（以及中文/空格的百分号转义），必须先转换。

    非 ``file:`` 开头的输入原样返回（部分平台会直接给出路径）。
    """
    if not url:
        return ""
    if not url.startswith("file:"):
        return url

    path = unquote(urlparse(url).path)
    # Windows 盘符：/D:/dir → D:/dir
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return str(Path(path))
