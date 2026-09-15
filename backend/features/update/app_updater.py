"""App 自动更新
============
查询 GitHub Releases，下载新版本安装程序，拉起快速更新。

纯业务逻辑模块，不含任何 QObject / 信号 / 线程 / 全局可变状态。
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import requests

from backend.utils.logger import log
from common.version_manager import AppVersion

# ── 常量 ──

GITHUB_API = "https://api.github.com"

UPDATE_OWNER = "li9633"
UPDATE_REPO = "GenshinDogFoodSweeper"

# ── 工具函数 ──


class CancelDownloadError(Exception):
    """下载被取消"""


def detect_mock_server(
    host: str = "127.0.0.1", port: int = 9888, timeout: float = 0.5
) -> str | None:
    """两步探测：TCP 端口 → /health 签名验证 → 返回 base_url。

    纯 debug 日志，release 下探测失败静默。
    """
    # 第 1 步：TCP 端口探测（~毫秒级，失败则跳过 HTTP）
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    reachable = sock.connect_ex((host, port)) == 0
    sock.close()
    if not reachable:
        log.debug(f"[detect_mock] 端口 {host}:{port} 未监听")
        return None

    # 第 2 步：GET /health + 双签名验证
    url = f"http://{host}:{port}/health"
    log.debug(f"[detect_mock] GET {url}")
    try:
        import urllib.request

        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.headers.get("X-GenshinDogFood-Mock") != "true":
            log.debug("[detect_mock] /health 缺少签名 Header")
            return None
        data = json.loads(resp.read().decode())
        if not data.get("mock_github_api"):
            log.debug("[detect_mock] /health JSON 缺少 mock_github_api: true")
            return None
        base_url = data.get("base_url", f"http://{host}:{port}")
        log.debug(f"[detect_mock] ✓ 已检测到模拟器 → {base_url}")
        return base_url
    except Exception as exc:
        log.debug(
            f"[detect_mock] /health 失败 ({type(exc).__name__}: {exc})"
        )
        return None


# ── 核心类 ──


class AppUpdater:
    """App 自动更新器

    所有依赖通过构造函数显式注入，无隐式全局状态。

    Usage:
        # 自动探测：优先本地模拟器，否则 GitHub API
        updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO)

        # 显式指定（测试用）
        updater = AppUpdater(UPDATE_OWNER, UPDATE_REPO, api_base="http://127.0.0.1:9888")
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
        if api_base is None:
            api_base = detect_mock_server()
            if api_base:
                log.info(f"使用本地模拟器 {api_base}")
        base = api_base if api_base else GITHUB_API
        self._api = f"{base}/repos/{owner}/{repo}/releases"
        log.debug(f"[AppUpdater] API = {self._api}")

    def check(self) -> dict | None:
        """查询最新 Release，返回 {tag, name, download_url, size, body} 或 None。

        Raises:
            requests.HTTPError: GitHub API 返回非 2xx（如 404 无 Release、403 限流）
            requests.ConnectionError: 网络不可达
            requests.Timeout: 请求超时
        """
        check_url = f"{self._api}/latest"
        log.debug(f"[AppUpdater.check] GET {check_url}")
        resp = requests.get(
            check_url,
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        log.debug(f"[AppUpdater.check] ← {resp.status_code} {resp.reason}")
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
            log.debug(f"[AppUpdater] HTTP {status}: {e}")
            if status == 404:
                return False, None, "仓库暂无已发布的版本"
            if status == 403:
                return False, None, "API 访问受限，可能是触发了 GitHub 速率限制"
            return False, None, f"服务器响应异常 (HTTP {status})"
        except requests.ConnectionError as e:
            log.debug(f"[AppUpdater] ConnectionError: {e}")
            return False, None, "网络连接失败，请检查网络设置"
        except requests.Timeout as e:
            log.debug(f"[AppUpdater] Timeout: {e}")
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
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        """下载到临时目录，返回文件路径

        Args:
            url: 下载地址
            progress_cb: 进度回调 (downloaded_bytes, total_bytes)
            cancel_check: 取消检查回调，返回 True 时中止下载
        """
        dest = Path(tempfile.gettempdir()) / f"{self._repo}_update_setup.exe"
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
                    if cancel_check and cancel_check():
                        raise CancelDownloadError(f"下载已取消 ({downloaded} 字节)")
        return dest

    def install(self, setup_path: Path) -> None:
        """拉起安装程序 --quick-update，返回后由调用方负责退出进程"""
        current_dir = str(Path(sys.executable).parent)
        subprocess.Popen(
            [str(setup_path), "--quick-update",
             "--fallback-install-dir", current_dir],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )