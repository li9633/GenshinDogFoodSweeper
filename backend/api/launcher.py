"""API 启动器 — uvicorn 进程管理（独立于 UI）"""

from __future__ import annotations

import threading
from collections.abc import Callable

from utils.logger import log


class ApiLauncher:
    """管理 FastAPI 后端服务的启动与停止"""

    PANEL_URL = "http://127.0.0.1:8765"
    SERVER_PORT = 8765

    def __init__(self, on_status: Callable[[bool, int], None] | None = None):
        self._on_status = on_status
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def run_server():
            import uvicorn

            try:
                uvicorn.run(
                    "backend.server:app",
                    host="127.0.0.1",
                    port=self.SERVER_PORT,
                    log_config=None,
                )
            except (OSError, SystemExit) as e:
                log.error(f"服务器启动失败: {e}")

        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()
        if self._on_status:
            self._on_status(True, self.SERVER_PORT)
        log.info(f"后端服务已启动 → {self.PANEL_URL}")

    def stop(self) -> None:
        pass  # daemon 线程随进程退出
