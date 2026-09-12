"""App 自动更新
============
查询 GitHub Releases，下载新版本安装程序，拉起快速更新。

纯业务逻辑模块，不含任何 QObject / 信号 / 线程 / 全局可变状态。
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import requests

from backend.utils.logger import log
from common.version_manager import AppVersion

# ── 常量 ──

GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/releases"

UPDATE_OWNER = "li9633"
UPDATE_REPO = "GenshinDogFoodSweeper"

# ── 工具函数 ──


def detect_mock_server(
    host: str = "127.0.0.1", port: int = 9888, timeout: float = 0.5
) -> str | None:
    """探测本地是否运行了 GitHub API 模拟器。

    test_quick_update.py 启动后会监听本地端口，此函数通过快速 HTTP 请求
    探测其是否存在。若探测成功，返回 API 基础 URL 模板。

    Returns:
        str | None: 如 "http://127.0.0.1:9888/repos/{owner}/{repo}/releases"
                    若未探测到则返回 None
    """
    url = f"http://{host}:{port}/repos/test/releases/latest"
    try:
        import urllib.request
        req = urllib.request.Request(url)
        urllib.request.urlopen(req, timeout=timeout)
        return f"http://{host}:{port}/repos/{{owner}}/{{repo}}/releases"
    except Exception:
        return None


# ── 核心类 ──


class AppUpdater:
    """App 自动更新器

    所有依赖通过构造函数显式注入，无隐式全局状态。

    Usage:
        # 真实 GitHub API（默认）
        updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO)

        # 本地模拟器（调试/测试）
        mock = detect_mock_server()
        updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO, api_base=mock)
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        api_base: str | None = None,
    ) -> None:
        self._owner = owner
        self._repo = repo
        template = api_base if api_base else GITHUB_API
        self._api = template.format(owner=owner, repo=repo)

    def check(self) -> dict | None:
        """查询最新 Release，返回 {tag, name, download_url, size, body} 或 None。

        Raises:
            requests.HTTPError: GitHub API 返回非 2xx（如 404 无 Release、403 限流）
            requests.ConnectionError: 网络不可达
            requests.Timeout: 请求超时
        """
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
            log.warning("未在 Release 中找到安装程序（.exe 资产）")
            return None

        return {
            "tag": tag,
            "name": release.get("name", tag),
            "download_url": setup_asset["browser_download_url"],
            "size": setup_asset["size"],
            "body": release.get("body", ""),
        }

    def is_update_available(self) -> tuple[bool, dict | None, str | None]:
        """检查是否有可用更新。

        Returns:
            (has_update, release_info, error_message)
            - has_update: 是否有新版本
            - release_info: Release 信息 dict（有更新时非 None）
            - error_message: 用户可读的错误信息（正常时为 None）
        """
        try:
            latest = self.check()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            log.debug(f"检查更新失败 (HTTP {status}): {e}")
            if status == 404:
                return False, None, "仓库暂无已发布的版本"
            if status == 403:
                return False, None, "API 访问受限，可能是触发了 GitHub 速率限制"
            return False, None, f"服务器响应异常 (HTTP {status})"
        except requests.ConnectionError:
            return False, None, "网络连接失败，请检查网络设置"
        except requests.Timeout:
            return False, None, "请求超时，请稍后重试"
        except Exception as e:
            log.warning(f"检查更新失败: {e}")
            return False, None, f"检查失败: {e}"

        if not latest:
            return False, None, None
        try:
            parts = latest["tag"].split(".")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            return False, None, None
        current = (AppVersion.MAJOR, AppVersion.MINOR, AppVersion.PATCH)
        return (major, minor, patch) > current, latest, None

    def download(
        self,
        url: str,
        *,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> Path:
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
        """拉起安装程序 --quick-update，返回后由调用方负责退出进程"""
        current_dir = str(Path(sys.executable).parent)
        subprocess.Popen(
            [str(setup_path), "--quick-update",
             "--fallback-install-dir", current_dir],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )