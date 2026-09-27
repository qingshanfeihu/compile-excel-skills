"""令牌换新与带令牌的请求：用回环上的假服务端（按服务端 auth_store.rotate_refresh 的轮换语义：
同一张 refresh 用第二次就整族吊销）测，不连真服务端。

- 两个工具调用同时发现 access 过期：只换一次，两边都用换好的那张，没人被登出（H1）；
- /token 回 502、网络不通：令牌保留；只有服务端对"文件里这张 refresh"回 invalid_grant 才删（H1）；
- 服务端回重定向：带令牌的请求不跟随，令牌不会发到别的源（M3）；
- 登录申请的权限带上 jumphost:admin（服务端按"申请 ∩ 账号拥有"授予），旧服务端不认就退回（M6）。
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pytest

from cex_client import auth, tools
from cex_client import workspace as wsmod
from cex_client.errors import ClientError, NotLoggedIn
from conftest import REPO_ROOT


class FakeAuthServer:
    """最小的 compile-excel-server 认证面：/token（refresh 轮换）、/device_authorize、/v1/docs/query。"""

    def __init__(self, *, refresh_delay: float = 0.3, known_scopes: set[str] | None = None):
        self.lock = threading.Lock()
        self.tokens: dict[str, dict] = {}
        self.log: list[str] = []
        self.token_status: int | None = None  # 设了就让 /token 直接回这个状态码（模拟 502）
        self.redirect_to: str | None = None
        self.requested_scopes: list[str] = []
        self.known_scopes = known_scopes
        self.seen_auth: list[str] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _send(self, code, obj, headers=None):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):  # noqa: N802
                size = int(self.headers.get("Content-Length") or 0)
                form = parse_qs(self.rfile.read(size).decode())
                if self.path == "/token":
                    if server.token_status is not None:
                        return self._send(server.token_status, {"detail": "bad gateway"})
                    time.sleep(refresh_delay)
                    with server.lock:
                        presented = form["refresh_token"][0]
                        row = server.tokens.get(presented)
                        if row is None or row["revoked"]:
                            server.log.append("invalid")
                            return self._send(400, {"error": "invalid_grant"})
                        if row["rotated"]:
                            for other in server.tokens.values():
                                if other["family"] == row["family"]:
                                    other["revoked"] = True
                            server.log.append("reused")
                            return self._send(400, {"error": "invalid_grant"})
                        row["rotated"] = True
                        access, refresh = server.issue(row["family"])
                        server.log.append("rotated")
                        return self._send(200, {"access_token": access, "refresh_token": refresh,
                                                "expires_in": 900, "scope": "docs:query"})
                if self.path == "/device_authorize":
                    scope = form.get("scope", [""])[0]
                    server.requested_scopes.append(scope)
                    if server.known_scopes is not None and set(scope.split()) - server.known_scopes:
                        return self._send(400, {"error": "invalid_scope"})
                    return self._send(200, {"device_code": "dc", "user_code": "ABCD",
                                            "verification_uri": "http://x/activate",
                                            "expires_in": 600, "interval": 1})
                if self.path == "/v1/docs/query":
                    header = self.headers.get("Authorization") or ""
                    server.seen_auth.append(header)
                    if server.redirect_to:
                        return self._send(302, {}, {"Location": server.redirect_to + "/v1/docs/query"})
                    with server.lock:
                        row = server.tokens.get(header[7:])
                        ok = bool(row and row["kind"] == "access" and not row["revoked"])
                    return self._send(200 if ok else 401,
                                      {"results": []} if ok else {"detail": "unauthorized"})
                return self._send(404, {})

            do_GET = do_POST  # noqa: N815

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def issue(self, family: str) -> tuple[str, str]:
        access, refresh = secrets.token_hex(8), secrets.token_hex(8)
        self.tokens[access] = {"kind": "access", "family": family, "revoked": False,
                               "rotated": False}
        self.tokens[refresh] = {"kind": "refresh", "family": family, "revoked": False,
                                "rotated": False}
        return access, refresh

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def fake():
    server = FakeAuthServer()
    yield server
    server.close()


def _workspace(tmp_path, base: str, *, expired: bool, fake: FakeAuthServer | None = None):
    ws = wsmod.init(tmp_path / "ws", server=base, device_build="B_1")
    access, refresh = fake.issue("fam1") if fake else ("a", "r")
    wsmod.write_private_json(ws.token_path, {
        "access_token": access, "refresh_token": refresh, "scope": "docs:query",
        "expires_at": int(time.time()) + (-5 if expired else 3600), "server": ws.server})
    return ws


def test_concurrent_refresh_rotates_once_and_nobody_is_logged_out(tmp_path, fake):
    ws = _workspace(tmp_path, fake.base, expired=True, fake=fake)
    env = {k: v for k, v in os.environ.items() if k != "CEX_WORKSPACE"}
    args = json.dumps({"workspace": str(ws.root), "q": "slb"})
    procs = [subprocess.Popen([sys.executable, str(REPO_ROOT / "bin" / "cex_tool"),
                               "cex_docs_query", args], stdout=subprocess.PIPE, text=True, env=env)
             for _ in range(3)]
    outs = [json.loads(p.communicate(timeout=60)[0]) for p in procs]
    assert all(out.get("ok") for out in outs), outs
    assert fake.log == ["rotated"], "the refresh token is presented exactly once"
    assert ws.token_path.exists()
    again = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})
    assert again["ok"], again


def test_a_transient_token_failure_keeps_the_session(tmp_path, fake):
    ws = _workspace(tmp_path, fake.base, expired=True, fake=fake)
    fake.token_status = 502
    out = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})
    assert out["ok"] is False and "HTTP 502" in out["error"] and "kept" in out["error"]
    assert ws.token_path.exists(), "a 502 on /token is not a revocation"
    fake.token_status = None
    assert tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})["ok"]


def test_an_unreachable_server_keeps_the_session(tmp_path):
    ws = _workspace(tmp_path, "http://127.0.0.1:9", expired=True)
    out = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})
    assert out["ok"] is False and "unreachable" in out["error"]
    assert ws.token_path.exists()


def test_invalid_grant_logs_out_only_for_the_refresh_token_in_the_file(tmp_path, fake):
    ws = _workspace(tmp_path, fake.base, expired=True, fake=fake)
    token = wsmod.read_private_json(ws.token_path)
    fake.tokens[token["refresh_token"]]["revoked"] = True
    with pytest.raises(NotLoggedIn):
        auth._refresh(ws, token)
    assert not ws.token_path.exists(), "the server revoked exactly this refresh token"

    # 另一个调用刚换好的新令牌：拿旧的那张去换失败，也不能删掉新的
    ws = _workspace(tmp_path / "second", fake.base, expired=False, fake=fake)
    fresh = wsmod.read_private_json(ws.token_path)
    stale = {**fresh, "access_token": "old-access", "refresh_token": "old-refresh"}
    assert auth._refresh(ws, stale)["access_token"] == fresh["access_token"]
    assert fake.log == ["invalid"], "an already rotated token is reused, not refreshed again"


def test_authenticated_requests_do_not_follow_redirects(tmp_path, fake):
    other = FakeAuthServer()
    try:
        ws = _workspace(tmp_path, fake.base, expired=False, fake=fake)
        fake.redirect_to = other.base
        out = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})
        assert out["ok"] is False and "redirect" in out["error"]
        assert other.seen_auth == [], "the bearer token never reaches another origin"
        assert fake.seen_auth and fake.seen_auth[0].startswith("Bearer ")
        # 组织常量也不能从重定向后的应答里缓存
        config = tools.call("cex_client_config", {"workspace": str(ws.root)})
        assert config["ok"] is False and not ws.client_config_path.exists()
    finally:
        other.close()


def test_login_asks_for_admin_and_falls_back_on_an_older_server(tmp_path, fake):
    ws = _workspace(tmp_path, fake.base, expired=False)
    assert tools.call("cex_login_start", {"workspace": str(ws.root)})["ok"]
    assert "jumphost:admin" in fake.requested_scopes[-1].split()
    assert "jumphost:run" in fake.requested_scopes[-1].split()
    old = FakeAuthServer(known_scopes=set(auth.BASE_SCOPES.split()))
    try:
        ws2 = _workspace(tmp_path / "old", old.base, expired=False)
        assert tools.call("cex_login_start", {"workspace": str(ws2.root)})["ok"]
        assert old.requested_scopes == [auth.DEFAULT_SCOPES, auth.BASE_SCOPES]
    finally:
        old.close()


def test_granted_scope_is_requested_intersect_user(tmp_path):
    """服务端授予的是"申请 ∩ 账号拥有"：申请 jumphost:admin 不会让没有它的账号登录失败
    （按服务端源码核：_requested_scopes 只拒未知 scope，/activate 取交集）。"""
    from conftest import SERVER_ROOT

    server = (SERVER_ROOT / "server.py")
    if not server.is_file():
        pytest.skip(f"no compile-excel-server checkout at {SERVER_ROOT}")
    text = server.read_text(encoding="utf-8")
    assert 'granted = sorted(set(flow["scope"]) & set(principal.scopes))' in text
    scopes = (SERVER_ROOT / "auth_store.py").read_text(encoding="utf-8")
    assert '"jumphost:admin"' in scopes, "the server knows the admin scope"


def test_refresh_errors_never_leak_tokens(tmp_path, fake):
    ws = _workspace(tmp_path, fake.base, expired=True, fake=fake)
    fake.token_status = 502
    with pytest.raises(ClientError) as exc:
        auth._refresh(ws, wsmod.read_private_json(ws.token_path))
    token = wsmod.read_private_json(ws.token_path)
    assert token["refresh_token"] not in str(exc.value)
