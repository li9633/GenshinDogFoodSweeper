r"""GitHub Release API 模拟服务器
================================
提供可编程控制的 HTTP 模拟服务器，用于测试 AppUpdater 更新流程。

用法:
    from backend.utils.mock_github_api import MockGitHubServer

    server = MockGitHubServer(port=9888)
    server.start()
    server.set_scenario("newer")  # 切换场景
    server.stop()
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

# ============================================================
# 场景预设
# ============================================================

CURRENT_MAJOR, CURRENT_MINOR, CURRENT_PATCH = 0, 9, 40


def _make_release(
    tag: str,
    name: str,
    body: str,
    asset_name: str,
    asset_url: str,
    asset_size: int,
) -> dict:
    return {
        "tag_name": tag,
        "name": name,
        "body": body,
        "assets": [
            {
                "name": asset_name,
                "browser_download_url": asset_url,
                "size": asset_size,
            }
        ],
    }


def _build_presets(base_url: str) -> dict[str, dict]:
    """根据 base_url 构造所有预设场景"""
    return {
        "newer": _make_release(
            tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 1}",
            name=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 1} 更新说明",
            body="### 新功能\n- 支持自动更新",
            asset_name=f"GenshinDogFoodSweeper-v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 1}-alpha.1-setup.exe",
            asset_url=f"{base_url}/download/test-setup.exe",
            asset_size=1024 * 1024 * 50,
        ),
        "same": _make_release(
            tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}",
            name=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}",
            body="当前版本",
            asset_name=f"GenshinDogFoodSweeper-v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}-alpha.1-setup.exe",
            asset_url=f"{base_url}/download/test-setup.exe",
            asset_size=1024 * 1024 * 50,
        ),
        "no_setup": _make_release(
            tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 2}",
            name="纯源码发布",
            body="没有安装包",
            asset_name="GenshinDogFoodSweeper-v0.9.42-source.zip",
            asset_url=f"{base_url}/download/test-source.zip",
            asset_size=1024 * 1024 * 10,
        ),
        "bad_version": _make_release(
            tag="not-a-version",
            name="格式异常",
            body="",
            asset_name="GenshinDogFoodSweeper-setup.exe",
            asset_url=f"{base_url}/download/test-setup.exe",
            asset_size=1024,
        ),
    }


SCENARIO_LABELS = {
    "newer": "有更新版本",
    "same": "同版本（无更新）",
    "no_setup": "无安装包资产",
    "bad_version": "版本号格式异常",
    "custom": "自定义",
}

SCENARIO_500_LABELS = {
    "200": "正常 (200)",
    "500": "服务器错误 (500)",
    "timeout": "超时无响应",
}

# ============================================================
# HTTP Handler
# ============================================================


class MockGitHubHandler(BaseHTTPRequestHandler):
    """模拟 GitHub API 的 HTTP Handler。

    路径规则：
      GET /repos/{owner}/{repo}/releases/latest → 返回当前场景 Release
      GET /download/*                            → 返回模拟安装包二进制
    """

    current_release: ClassVar[dict] = {}
    request_log: ClassVar[list[str]] = []
    log_callback: ClassVar[Any] = None
    error_scenario: ClassVar[str] = "200"
    download_file_path: ClassVar[str | None] = None
    bandwidth_limit: ClassVar[int] = 0

    def log_message(self, format, *args):
        entry = f"[Mock API] {self.command} {self.path} → {format % args}"
        MockGitHubHandler.request_log.append(entry)
        if len(MockGitHubHandler.request_log) > 500:
            MockGitHubHandler.request_log = MockGitHubHandler.request_log[-200:]
        if MockGitHubHandler.log_callback:
            MockGitHubHandler.log_callback(entry)

    def do_GET(self):
        if self.path.endswith("/releases/latest"):
            if MockGitHubHandler.error_scenario == "500":
                self._serve_error(500)
            elif MockGitHubHandler.error_scenario == "timeout":
                import time
                time.sleep(30)
                self._serve_error(504)
            else:
                self._serve_release()
        elif self.path.startswith("/download/"):
            self._serve_download()
        else:
            self._serve_error(404)

    def _serve_release(self):
        release = MockGitHubHandler.current_release
        body = json.dumps(release, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_download(self):
        file_path = MockGitHubHandler.download_file_path
        if file_path:
            fp = Path(file_path)
            if not fp.is_file():
                self._serve_error(404)
                return
            file_size = fp.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(file_size))
            self.end_headers()
            limit = MockGitHubHandler.bandwidth_limit
            with open(fp, "rb") as f:
                while True:
                    t0 = time.perf_counter()
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    if limit > 0:
                        elapsed = time.perf_counter() - t0
                        expected = len(chunk) / limit
                        if elapsed < expected:
                            time.sleep(expected - elapsed)
        else:
            fake_data = b"\x00" * 65536
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(fake_data)))
            self.end_headers()
            self.wfile.write(fake_data)

    def _serve_error(self, code: int):
        self.send_response(code)
        self.end_headers()


# ============================================================
# 服务器控制
# ============================================================


class MockGitHubServer:
    """可编程控制的模拟 GitHub API 服务器"""

    def __init__(self, host: str = "127.0.0.1", port: int = 9888) -> None:
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._error_scenario = "200"
        self._current_scenario = "newer"
        self._custom_release: dict | None = None
        self._log_callback: Any = None
        self._init_presets_and_handler()

    def _init_presets_and_handler(self) -> None:
        base = f"http://{self._host}:{self._port}"
        self._presets = _build_presets(base)
        MockGitHubHandler.request_log.clear()
        MockGitHubHandler.current_release = self._presets["newer"]
        MockGitHubHandler.log_callback = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/repos/{{owner}}/{{repo}}/releases"

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def port(self) -> int:
        return self._port

    @property
    def current_scenario(self) -> str:
        return self._current_scenario

    @property
    def error_scenario(self) -> str:
        return self._error_scenario

    def set_log_callback(self, cb) -> None:
        self._log_callback = cb
        MockGitHubHandler.log_callback = cb

    def set_error_scenario(self, scenario: str) -> None:
        self._error_scenario = scenario
        MockGitHubHandler.error_scenario = scenario

    def get_current_release(self) -> dict:
        return dict(MockGitHubHandler.current_release)

    def set_scenario(self, name: str) -> None:
        self._current_scenario = name
        if name in self._presets:
            MockGitHubHandler.current_release = self._presets[name]
        elif name == "custom" and self._custom_release:
            MockGitHubHandler.current_release = self._custom_release

    def set_custom_release(self, release: dict) -> None:
        self._custom_release = release
        if self._current_scenario == "custom":
            MockGitHubHandler.current_release = release

    def get_request_log(self) -> str:
        return "\n".join(MockGitHubHandler.request_log)

    @property
    def download_file_path(self) -> str | None:
        return MockGitHubHandler.download_file_path

    @download_file_path.setter
    def download_file_path(self, path: str | None) -> None:
        MockGitHubHandler.download_file_path = path

    @property
    def bandwidth_limit(self) -> int:
        return MockGitHubHandler.bandwidth_limit

    @bandwidth_limit.setter
    def bandwidth_limit(self, limit: int) -> None:
        MockGitHubHandler.bandwidth_limit = limit

    def start(self) -> bool:
        if self._running:
            return False
        try:
            self._server = HTTPServer((self._host, self._port), MockGitHubHandler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self._running = True
            return True
        except OSError:
            return False

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            self._running = False