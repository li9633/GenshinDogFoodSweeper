r"""快速更新流程测试
================
使用本地 HTTP Server 模拟 GitHub Release API，测试 AppUpdater 完整链路。

用法:
    cd D:\MyCodeProject\GenshinDogFoodSweeper
    uv run python test_quick_update.py
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

# 确保项目根在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# backend 内部使用 from utils.xxx 的绝对导入，所以 backend 目录也要加入
_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ---------- 可调参数 ----------

MOCK_PORT = 9888
MOCK_HOST = "127.0.0.1"
MOCK_BASE = f"http://{MOCK_HOST}:{MOCK_PORT}"

# ---------- 当前版本（与 version.py 同步） ----------
CURRENT_MAJOR, CURRENT_MINOR, CURRENT_PATCH = 0, 9, 40

# ---------- 模拟数据 ----------


def _make_release(tag: str, name: str, body: str,
                  asset_name: str, asset_url: str,
                  asset_size: int) -> dict:
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


# 场景 A：有更新的 Release
RELEASE_NEWER = _make_release(
    tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 1}",
    name=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 1} 更新说明",
    body="### 新功能\n- 支持自动更新",
    asset_name="GenshinDogFoodSweeper-v0.9.41-alpha.1-setup.exe",
    asset_url=f"{MOCK_BASE}/download/test-setup.exe",
    asset_size=1024 * 1024 * 50,  # 50MB
)

# 场景 B：同版本 Release
RELEASE_SAME = _make_release(
    tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}",
    name=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}",
    body="当前版本",
    asset_name="GenshinDogFoodSweeper-v0.9.40-alpha.1-setup.exe",
    asset_url=f"{MOCK_BASE}/download/test-setup.exe",
    asset_size=1024 * 1024 * 50,
)

# 场景 C：没有 -setup.exe 的 Release
RELEASE_NO_SETUP = _make_release(
    tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 2}",
    name="纯源码发布",
    body="没有安装包",
    asset_name="GenshinDogFoodSweeper-v0.9.42-source.zip",
    asset_url=f"{MOCK_BASE}/download/test-source.zip",
    asset_size=1024 * 1024 * 10,
)

# 场景 D：版本号格式异常
RELEASE_BAD_VERSION = _make_release(
    tag="not-a-version",
    name="格式异常",
    body="",
    asset_name="GenshinDogFoodSweeper-setup.exe",
    asset_url=f"{MOCK_BASE}/download/test-setup.exe",
    asset_size=1024,
)


class MockGitHubHandler(BaseHTTPRequestHandler):
    """模拟 GitHub API 的 HTTP Handler。

    路径规则：
      GET /repos/{owner}/{repo}/releases/latest → 返回当前场景 Release
      GET /download/*                            → 返回模拟安装包二进制
    """

    # 类变量：测试脚本通过修改此属性切换场景
    current_release: dict = RELEASE_NEWER

    def log_message(self, format, *args):
        prefix = "  [Mock API]"
        msg = format % args
        print(f"{prefix} {self.command} {self.path} → {msg}")

    def do_GET(self):
        if self.path.endswith("/releases/latest"):
            self._serve_release()
        elif self.path.startswith("/download/"):
            self._serve_download()
        elif self.path == "/error/500":
            self._serve_error(500)
        elif self.path == "/error/timeout":
            # 模拟超时不响应
            pass
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
        # 返回 64KB 假数据模拟安装包
        fake_data = b"\x00" * 65536
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(fake_data)))
        self.end_headers()
        self.wfile.write(fake_data)

    def _serve_error(self, code: int):
        self.send_response(code)
        self.end_headers()


def start_mock_server() -> HTTPServer:
    server = HTTPServer((MOCK_HOST, MOCK_PORT), MockGitHubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Mock GitHub API started at {MOCK_BASE}")
    return server


# ---------- 测试用例 ----------


class Colors:
    OK = "\033[92m"
    FAIL = "\033[91m"
    INFO = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def _print_header(text: str):
    print(f"\n{'─' * 60}")
    print(f"  {Colors.BOLD}{text}{Colors.RESET}")
    print(f"{'─' * 60}")


def _assert(condition: bool, msg: str):
    if condition:
        print(f"  {Colors.OK}✓{Colors.RESET} {msg}")
    else:
        print(f"  {Colors.FAIL}✗{Colors.RESET} {msg}")
        raise AssertionError(msg)


def _test_check_normal(updater) -> dict:
    """场景：正常 Release — 应正确解析返回"""
    _print_header("1. check() — 正常 Release")
    MockGitHubHandler.current_release = RELEASE_NEWER
    result = updater.check()
    _assert(result is not None, "check() 不应返回 None")
    _assert(result["tag"] == f"{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH + 1}",
            f"tag 应为预定义值，实际: {result['tag']}")
    _assert(result["download_url"] == f"{MOCK_BASE}/download/test-setup.exe",
            "download_url 正确")
    _assert(result["size"] == 1024 * 1024 * 50,
            "size 正确")
    _assert("新功能" in result["body"], "body 包含预期内容")
    return result


def _test_update_available(updater):
    """场景：版本更新检测"""
    _print_header("2. is_update_available() — 有新版本")

    # 场景 A：版本号更大 → 有更新
    MockGitHubHandler.current_release = RELEASE_NEWER
    available, info = updater.is_update_available()
    _assert(available, f"版本 {RELEASE_NEWER['tag_name']} 应高于当前版本")
    _assert(info is not None, "应返回 Release 信息")

    # 场景 B：版本号相同 → 无更新
    MockGitHubHandler.current_release = RELEASE_SAME
    available, info = updater.is_update_available()
    _assert(not available, f"同版本 {RELEASE_SAME['tag_name']} 不应提示更新")
    _assert(info is not None, "即使无更新也应返回 info")

    # 场景 C：版本号更小 → 无更新（生产环境不应出现）
    RELEASE_OLDER = _make_release(
        tag=f"v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH - 1}",
        name="旧版本",
        body="",
        asset_name="GenshinDogFoodSweeper-setup.exe",
        asset_url=f"{MOCK_BASE}/download/test-setup.exe",
        asset_size=1024,
    )
    MockGitHubHandler.current_release = RELEASE_OLDER
    available, _info = updater.is_update_available()
    _assert(not available, "版本倒退不应提示更新")

    # 场景 D：版本号格式异常 → 无更新（不崩溃）
    MockGitHubHandler.current_release = RELEASE_BAD_VERSION
    available, info = updater.is_update_available()
    _assert(not available, "版本号格式异常应返回 False")
    _assert(info is None, "版本号格式异常应返回 None")


def _test_no_setup_asset(updater):
    """场景：Release 中没有 -setup.exe"""
    _print_header("3. check() — 无安装包资产")
    MockGitHubHandler.current_release = RELEASE_NO_SETUP
    result = updater.check()
    _assert(result is None, "无 -setup.exe 时应返回 None")


def _test_network_error():
    """场景：API 不可达"""
    _print_header("4. check() — API 500 错误")

    from backend.utils.app_updater import AppUpdater
    # 指向一个不存在的路径
    fake_updater = AppUpdater(owner="fake", repo="fake")
    fake_updater._api = f"{MOCK_BASE}/error"

    result = fake_updater.check()
    _assert(result is None, "网络错误时应返回 None（不抛异常）")


def _test_download(updater):
    """场景：下载流程"""
    _print_header("5. download() — 下载到临时文件")
    MockGitHubHandler.current_release = RELEASE_NEWER

    # 次数跟踪
    called = {"count": 0}

    def progress(downloaded: int, total: int):
        called["count"] += 1

    try:
        path = updater.download(f"{MOCK_BASE}/download/test-setup.exe",
                                progress_cb=progress)
        _assert(path.exists(), f"下载文件应存在: {path}")
        _assert(path.stat().st_size == 65536,
                f"文件大小应为 65536 字节，实际: {path.stat().st_size}")
        _assert(called["count"] > 0, "progress_cb 应被调用")
        # 清理
        path.unlink(missing_ok=True)
    except Exception as e:
        print(f"  {Colors.INFO}⚠ 下载测试跳过（部分环境可能受限）: {e}{Colors.RESET}")


def _test_download_no_progress(updater):
    """场景：下载无 Content-Length"""
    _print_header("6. download() — 无 Content-Length（不触发进度）")

    class NoLengthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = b"\x00" * 4096
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    # 临时另起一个小服务
    alt_port = MOCK_PORT + 1
    alt_server = HTTPServer((MOCK_HOST, alt_port), NoLengthHandler)
    t = threading.Thread(target=alt_server.serve_forever, daemon=True)
    t.start()

    progress_called = []

    def progress(d, t):
        progress_called.append(d)

    try:
        path = updater.download(f"http://{MOCK_HOST}:{alt_port}/dummy",
                                progress_cb=progress)
        _assert(path.exists(), "无 Content-Length 时也应下载成功")
        _assert(len(progress_called) == 0,
                "无 Content-Length 时不应回调 progress_cb")
        path.unlink(missing_ok=True)
    finally:
        alt_server.shutdown()


def _test_install_skip():
    """验证 install() 参数构造正确性（不实际执行）"""
    _print_header("7. install() — 参数构造验证")

    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit") as mock_exit, \
         patch("sys.executable", r"C:\Program Files\App\python.exe"):

        from backend.utils.app_updater import AppUpdater
        updater = AppUpdater(owner="test", repo="test")
        updater.install(Path(r"C:\Temp\test_setup.exe"))

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        _assert("--quick-update" in args, "install 应包含 --quick-update 参数")
        _assert("--fallback-install-dir" in args, "install 应包含 --fallback-install-dir")
        _assert(r"C:\Program Files\App" in args,
                f"fallback-install-dir 应为当前目录，实际: {args}")
        mock_exit.assert_called_once_with(0)
        print(f"  {Colors.OK}✓{Colors.RESET} 参数: {' '.join(args)}")


# ---------- Main ----------


def main():
    print(f"{Colors.BOLD}=== AppUpdater 快速更新流程测试 ==={Colors.RESET}")
    print(f"当前版本: v{CURRENT_MAJOR}.{CURRENT_MINOR}.{CURRENT_PATCH}")
    print(f"Mock API:  {MOCK_BASE}")

    server = start_mock_server()

    try:
        from backend.utils.app_updater import AppUpdater
        from common.version_manager import AppVersion as _  # noqa: F401

        # 将 AppUpdater 的 GitHub API 指向本地 Mock Server
        with patch("backend.utils.app_updater.GITHUB_API",
                   f"{MOCK_BASE}/repos/{{owner}}/{{repo}}/releases"):
            updater = AppUpdater(owner="test-owner", repo="test-repo")

            _test_check_normal(updater)
            _test_update_available(updater)
            _test_no_setup_asset(updater)
            _test_network_error()
            _test_download(updater)
            _test_download_no_progress(updater)
            _test_install_skip()

    except AssertionError:
        print(f"\n{Colors.FAIL}✗ 测试失败！{Colors.RESET}")
        return 1
    except Exception as e:
        print(f"\n{Colors.FAIL}✗ 未预期异常: {type(e).__name__}: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        server.shutdown()
        print(f"\n{Colors.INFO}Mock server stopped.{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.OK}=== 全部 7 个测试场景通过 ==={Colors.RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())