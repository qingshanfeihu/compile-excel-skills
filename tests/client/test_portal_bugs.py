"""门户扫码登录与取单：用本地假门户（按实测协议形状录制的应答）测，不访问真实门户。

假门户：登录页下发网关 cookie；getQrCode 回 PNG；扫码前轮询不建会话，扫码后第一次轮询发会话 cookie；
受保护资源没会话就 302 回登录页；Bugzilla 详情页返回合成的缺陷页（描述里带口令，验证脱敏）。
"""

from __future__ import annotations

import json
import os
import stat
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from cex_client import tools
from cex_client import workspace as wsmod

PNG = b"\x89PNG\r\n\x1a\nfake-qr"
BUG_PAGE = """<html><head><title>Bug 4242 - health check</title></head><body>
<h1 id="bz_pagetitle">Bug 4242 - SLB health check fails after reload</h1>
<span id="short_desc_nonedit_display">SLB health check fails after reload</span>
<table><tr><td id="field_container_product">APV</td>
<td id="field_container_component">SLB</td>
<td id="field_container_bug_severity">major</td></tr></table>
<span id="static_bug_status">RESOLVED</span>
<span id="bz_reporter_name">Some Person</span>
<pre class="bz_comment_text">Steps: configure the real service and enable health check.
Login with password=hunter2secret then observe the monitor goes down after a while.</pre>
</body></html>"""


class FakePortal:
    def __init__(self):
        self.scanned = False
        self.requests: list[str] = []
        portal = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _send(self, status, body=b"", headers=None):
                self.send_response(status)
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _session(self):
                return "AN_SESSION=ok" in (self.headers.get("Cookie") or "")

            def do_GET(self):  # noqa: N802
                portal.requests.append("GET " + self.path)
                path = urlsplit(self.path).path
                if path == "/":
                    self._send(302, headers={"Location": "/prx/000/http/localh/login/index.html"})
                elif path == "/prx/000/http/localh/login/index.html":
                    self._send(200, b"<html>login</html>",
                               {"Set-Cookie": "AN_GATEWAY=g1; Path=/"})
                elif path == "/ueba/openapi/policy/v1/getQrCode":
                    if "uuid=" not in self.path or "AN_GATEWAY=g1" not in (self.headers.get("Cookie") or ""):
                        self._send(400)
                    else:
                        self._send(200, PNG, {"Content-Type": "image/png"})
                elif path.startswith("/prx/000/http/localh/bugzilla/"):
                    if not self._session():
                        self._send(302, headers={"Location": "/prx/000/http/localh/login/index.html"})
                    elif path.endswith("/show_bug.cgi"):
                        self._send(200, BUG_PAGE.encode(), {"Content-Type": "text/html"})
                    else:
                        self._send(200, b"<html>bugzilla home</html>")
                else:
                    self._send(404)

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                form = parse_qs(self.rfile.read(length).decode())
                portal.requests.append("POST " + self.path)
                if self.path == "/prx/000/http/localhost/login" and \
                        form.get("method") == ["twodimension"] and form.get("uuid"):
                    if portal.scanned:
                        self._send(302, headers={"Location": "/prx/000/http/localh/welcome",
                                                 "Set-Cookie": "AN_SESSION=ok; Path=/"})
                    else:
                        self._send(200, b'{"status":"waiting"}')
                else:
                    self._send(400)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    fake = FakePortal()
    ws = wsmod.init(tmp_path / "project", server="http://127.0.0.1:1", device_build="B_1")
    wsmod.write_private_json(ws.client_config_path, {
        "schema": "cex.client-config/v1",
        "portal": {"login_url": fake.base + "/"},
        "defects": {"bugzilla": {"proxy_url": fake.base + "/prx/000/http/localh/bugzilla"},
                    "zentao": {"base_url": fake.base + "/prx/000/http/localh/zentao"}}})
    yield fake, ws, tmp_path
    fake.close()


def test_qr_login_then_fetch_scrubbed_ticket(env):
    fake, ws, tmp = env
    args = {"workspace": str(ws.root)}
    assert "expired or missing" in tools.call("cex_bug_get", {**args, "backend": "bugzilla",
                                                              "ticket": "4242"})["error"]
    started = tools.call("cex_portal_login_start", args)
    assert started["ok"], started
    qr = started["qr_image"]
    assert open(qr, "rb").read() == PNG and stat.S_IMODE(os.stat(qr).st_mode) == 0o600
    pending = tools.call("cex_portal_login_wait", {**args, "timeout_s": 1})
    assert pending.get("pending") is True
    fake.scanned = True
    done = tools.call("cex_portal_login_wait", {**args, "timeout_s": 5})
    assert done["ok"] and done["logged_in"], done
    session_file = tmp / "cache" / "compile-excel" / "portal-session.json"
    assert stat.S_IMODE(os.stat(session_file).st_mode) == 0o600
    assert "hunter2" not in session_file.read_text(encoding="utf-8")

    got = tools.call("cex_bug_get", {**args, "backend": "bugzilla", "ticket": "BUG-4242"})
    assert got["ok"], got
    ticket = got["ticket"]
    assert ticket["ticket_id"] == "BUG-4242" and "health check" in ticket["title"]
    assert "hunter2secret" not in json.dumps(ticket)
    assert "reported_by" not in ticket and "attachments" not in ticket
    saved = ws.root / got["saved"]
    assert saved == ws.root / "defects" / "bugzilla" / "BUG-4242.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["ticket_id"] == "BUG-4242"


def test_ticket_ids_and_backends_are_allowlisted(env):
    _, ws, _ = env
    args = {"workspace": str(ws.root)}
    for backend, ticket in (("bugzilla", "../etc"), ("bugzilla", "STORY-1"),
                            ("bugzilla", "12 OR 1=1"), ("jira", "1"), ("bugzilla", "0")):
        out = tools.call("cex_bug_get", {**args, "backend": backend, "ticket": ticket})
        assert out["ok"] is False, (backend, ticket)


def test_session_expiry_is_reported_not_retried(env):
    fake, ws, tmp = env
    args = {"workspace": str(ws.root)}
    tools.call("cex_portal_login_start", args)
    fake.scanned = True
    assert tools.call("cex_portal_login_wait", {**args, "timeout_s": 5})["ok"]
    (tmp / "cache" / "compile-excel" / "portal-session.json").write_text(
        json.dumps({"origin": fake.base, "cookies": []}), encoding="utf-8")
    os.chmod(tmp / "cache" / "compile-excel" / "portal-session.json", 0o600)
    before = len(fake.requests)
    out = tools.call("cex_bug_get", {**args, "backend": "bugzilla", "ticket": "4242"})
    assert out["ok"] is False and "scan again" in out["error"]
    assert len(fake.requests) - before == 1, "会话过期只报错，不自己重试或重登"


def test_requests_are_rate_limited(env):
    fake, ws, _ = env
    args = {"workspace": str(ws.root)}
    tools.call("cex_portal_login_start", args)
    fake.scanned = True
    tools.call("cex_portal_login_wait", {**args, "timeout_s": 5})
    start = time.monotonic()
    for _ in range(3):
        assert tools.call("cex_bug_get", {**args, "backend": "bugzilla", "ticket": "4242"})["ok"]
    assert time.monotonic() - start >= 2.0, "两次取单之间至少间隔 1 秒"


def test_logout_forgets_the_session(env):
    fake, ws, tmp = env
    args = {"workspace": str(ws.root)}
    tools.call("cex_portal_login_start", args)
    fake.scanned = True
    tools.call("cex_portal_login_wait", {**args, "timeout_s": 5})
    assert tools.call("cex_portal_logout", args)["session_removed"] is True
    assert not (tmp / "cache" / "compile-excel" / "portal-session.json").exists()
