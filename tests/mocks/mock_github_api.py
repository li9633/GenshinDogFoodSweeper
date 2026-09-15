"""GitHub Release API 模拟服务器
================================
提供可编程控制的 HTTP 模拟服务器，用于测试 AppUpdater 更新流程。

基于 FastAPI + uvicorn 实现，替代原始 http.server 方案。

用法:
    from tests.mocks.mock_github_api import MockGitHubServer

    server = MockGitHubServer(port=9888)
    server.start()
    server.set_scenario("newer")  # 切换场景
    server.stop()
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

# # 场景预设
#

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

# # 全局可变状态（线程安全：所有读写通过 _state_lock 保护）
#

_state_lock = threading.Lock()

_current_release: dict = {}
_request_log: list[str] = []
_log_callback: Any = None
_error_scenario: str = "200"
_download_file_path: str | None = None
_bandwidth_limit: int = 0


def _append_log(entry: str) -> None:
    with _state_lock:
        _request_log.append(entry)
        if len(_request_log) > 500:
            _request_log[:] = _request_log[-200:]
        cb = _log_callback
    if cb:
        cb(entry)


# # FastAPI 应用
#


def _create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        body = JSONResponse(
            content={
                "mock_github_api": True,
                "base_url": str(request.base_url).rstrip("/"),
            }
        )
        body.headers["X-GenshinDogFood-Mock"] = "true"
        return body

    @app.get("/repos/{owner}/{repo}/releases/latest")
    async def get_latest_release(request: Request) -> JSONResponse:
        _append_log(f"[Mock API] GET {request.url.path} → 200 OK")

        with _state_lock:
            scenario = _error_scenario

        if scenario == "500":
            _append_log(
                f"[Mock API] GET {request.url.path} → 500 Internal Server Error"
            )
            return JSONResponse(
                status_code=500,
                content={"message": "Internal Server Error"},
            )
        if scenario == "timeout":
            await asyncio.sleep(30)
            _append_log(
                f"[Mock API] GET {request.url.path} → 504 Gateway Timeout"
            )
            return JSONResponse(
                status_code=504,
                content={"message": "Gateway Timeout"},
            )

        with _state_lock:
            release = dict(_current_release) if _current_release else {}

        return JSONResponse(content=release)

    @app.get("/download/{filename:path}")
    async def download_file(filename: str) -> Response:
        _append_log(f"[Mock API] GET /download/{filename} → 200 OK")

        with _state_lock:
            file_path = _download_file_path
            limit = _bandwidth_limit

        if file_path:
            fp = Path(file_path)
            if not fp.is_file():
                return Response(status_code=404)

            content = fp.read_bytes()
            headers = {
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
            }

            if limit > 0:
                expected_duration = len(content) / limit
                await asyncio.sleep(expected_duration)

            return Response(content=content, headers=headers)

        # 无真实文件时返回占位数据
        fake_data = b"\x00" * 65536
        return Response(
            content=fake_data,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(fake_data)),
            },
        )

    return app


# # 服务器控制
#


class MockGitHubServer:
    """可编程控制的模拟 GitHub API 服务器

    基于 FastAPI + uvicorn，通过独立线程运行事件循环。
    与旧版 http.server 方案保持完全相同的公开 API。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9888) -> None:
        self._host = host
        self._port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._error_scenario = "200"
        self._current_scenario = "newer"
        self._custom_release: dict | None = None
        self._log_callback: Any = None
        self._init_state()

    def _init_state(self) -> None:
        base = f"http://{self._host}:{self._port}"
        self._presets = _build_presets(base)

        global _current_release, _log_callback
        global _error_scenario, _download_file_path, _bandwidth_limit
        with _state_lock:
            _request_log.clear()
            _current_release = self._presets["newer"]
            _log_callback = None
            _error_scenario = "200"
            _download_file_path = None
            _bandwidth_limit = 0

    # # 属性
    #

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def api_url(self) -> str:
        return self.base_url

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

    # # 日志回调
    #

    def set_log_callback(self, cb) -> None:
        """设置请求日志回调。

        注意：回调在 HTTP 服务器线程中执行（每个请求一次）。
        Qt 程序必须在回调里只做入队，绝不能直接操作 QWidget ——
        跨线程访问控件会让整个进程无提示崩溃。
        """
        self._log_callback = cb
        global _log_callback
        with _state_lock:
            _log_callback = cb

    # # 场景控制
    #

    def set_error_scenario(self, scenario: str) -> None:
        self._error_scenario = scenario
        global _error_scenario
        with _state_lock:
            _error_scenario = scenario

    def get_current_release(self) -> dict:
        with _state_lock:
            return dict(_current_release)

    def set_scenario(self, name: str) -> None:
        self._current_scenario = name
        global _current_release
        with _state_lock:
            if name in self._presets:
                _current_release = self._presets[name]
            elif name == "custom" and self._custom_release:
                _current_release = self._custom_release

    def set_custom_release(self, release: dict) -> None:
        self._custom_release = release
        global _current_release
        with _state_lock:
            if self._current_scenario == "custom":
                _current_release = release

    def get_request_log(self) -> str:
        with _state_lock:
            return "\n".join(_request_log)

    # # 下载配置
    #

    @property
    def download_file_path(self) -> str | None:
        with _state_lock:
            return _download_file_path

    @download_file_path.setter
    def download_file_path(self, path: str | None) -> None:
        global _download_file_path
        with _state_lock:
            _download_file_path = path

    @property
    def bandwidth_limit(self) -> int:
        with _state_lock:
            return _bandwidth_limit

    @bandwidth_limit.setter
    def bandwidth_limit(self, limit: int) -> None:
        global _bandwidth_limit
        with _state_lock:
            _bandwidth_limit = limit

    # # 生命周期
    #

    def start(self) -> bool:
        if self._running:
            return False

        app = _create_app()
        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            log_level="error",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._server.serve())
            except asyncio.CancelledError:
                pass
            finally:
                loop.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self._running = True
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False

        if self._server is not None:
            self._server.should_exit = True
            self._server = None

        self._thread = None