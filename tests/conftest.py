"""测试公共设置：发行根进 sys.path；定位同级的 InfoTest 与 compile-excel-server 检出（对拍与联调用）。

检出按 环境变量 → 本仓旁边 → 本仓上一级旁边 的顺序找（后两种对应"与本仓同级"与"本仓在 circle/
这类中间目录里"两种布局）。找不到时依赖 InfoTest 的漂移、对拍、隔离测试（tests/core）照常跳过；
设 CEX_REQUIRE_INFOTEST=1 时这些跳过一律改判失败——CI 或发版前用它，免得静默少跑一整片。
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRE_INFOTEST_ENV = "CEX_REQUIRE_INFOTEST"
# 改判范围：本仓自己的漂移/对拍/隔离测试。tests/client 里有的测试另要可选的参考批次，
# 跳过原因里也提到 InfoTest，不能一概改判
_INFOTEST_GATED = REPO_ROOT / "tests" / "core"


def _sibling_checkout(env: str, name: str, marker: str, *, repo_root: Path = REPO_ROOT) -> Path:
    """环境变量优先；否则在本仓旁边、再上一级旁边找带 marker 的检出；都没有时给第一个候选
    （测试据此报"找不到 …"）。"""
    raw = os.environ.get(env, "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    candidates = [repo_root.parent / name, repo_root.parent.parent / name]
    for candidate in candidates:
        if (candidate / marker).exists():
            return candidate.resolve()
    return candidates[0].resolve()


INFOTEST_ROOT = _sibling_checkout("INFOTEST_ROOT", "InfoTest_Engine", "main")
SERVER_ROOT = _sibling_checkout("CES_SERVER_ROOT", "compile-excel-server", "server.py")


def infotest_required() -> bool:
    return os.environ.get(REQUIRE_INFOTEST_ENV, "").strip() not in ("", "0")


def _skip_reason(report) -> str:
    longrepr = report.longrepr
    return str(longrepr[2] if isinstance(longrepr, tuple) and len(longrepr) == 3 else longrepr)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not (report.skipped and not hasattr(report, "wasxfail") and infotest_required()):
        return
    reason = _skip_reason(report)
    if _INFOTEST_GATED in Path(str(item.path)).resolve().parents and "InfoTest" in reason:
        report.outcome = "failed"
        report.longrepr = (f"{REQUIRE_INFOTEST_ENV} is set, so this InfoTest-dependent test must run "
                           f"(INFOTEST_ROOT resolved to {INFOTEST_ROOT}): {reason}")


@pytest.fixture()
def ces_stub():
    """只答探活的假服务端地址：cex_init 先探活，不连真服务端的测试拿它当 server。"""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_GET(self):
            found = self.path == "/healthz"
            body = json.dumps({"ok": True, "service": "compile-excel-server"} if found
                              else {"detail": "Not Found"}).encode()
            self.send_response(200 if found else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_POST = do_GET

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()
