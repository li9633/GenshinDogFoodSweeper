"""App 自动更新
============
查询 GitHub Releases，下载新版本安装程序，拉起快速更新。
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from backend.utils.logger import log
from backend.utils.version_manager import AppVersion

GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases"


class AppUpdater:
    """App 自动更新器"""

    def __init__(self, owner: str, repo: str) -> None:
        self._owner = owner
        self._repo = repo
        self._api = GITHUB_API.format(owner=owner, repo=repo)

    def check(self) -> dict | None:
        """查询最新 Release，返回 {tag, name, download_url, size, body} 或 None"""
        try:
            resp = requests.get(
                f"{self._api}/latest",
                headers={"Accept": "application/vnd.github+json"},
                timeout=15,
            )
            resp.raise_for_status()
            release = resp.json()

            tag = release.get("tag_name", "").lstrip("v")
            setup_asset = next(
                (a for a in release.get("assets", [])
                 if a["name"].endswith("-setup.exe")),
                None,
            )
            if not setup_asset:
                log.warning("未在 Release 中找到安装程序")
                return None

            return {
                "tag": tag,
                "name": release.get("name", tag),
                "download_url": setup_asset["browser_download_url"],
                "size": setup_asset["size"],
                "body": release.get("body", ""),
            }
        except Exception as e:
            log.warning(f"检查更新失败: {e}")
            return None

    def is_update_available(self) -> tuple[bool, dict | None]:
        """(是否有更新, Release 信息)"""
        latest = self.check()
        if not latest:
            return False, None
        try:
            parts = latest["tag"].split(".")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            return False, None
        return AppVersion.is_newer_than(major, minor, patch), latest

    def download(self, url: str, progress_cb=None) -> Path:
        """下载到临时目录，返回文件路径"""
        dest = Path(tempfile.gettempdir()) / f"{self._repo}_update_setup.exe"
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)
        return dest

    def install(self, setup_path: Path) -> None:
        """拉起安装程序 --quick-update，并退出当前进程"""
        current_dir = str(Path(sys.executable).parent)
        subprocess.Popen(
            [str(setup_path), "--quick-update",
             "--fallback-install-dir", current_dir],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        sys.exit(0)