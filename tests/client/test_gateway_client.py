"""网关客户端：令牌去向、租约凭据不出现在工具结果里、自检带上工作区的 device_build。
网关用本进程里的假 MCP 端点（按网关 tools/call 的应答形状）。"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cex_client import gateway, tools
from cex_client import workspace as wsmod


class FakeGateway:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.auth: list[str] = []
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):  # noqa: N802
                size = int(self.headers.get("Content-Length") or 0)
                message = json.loads(self.rfile.read(size))
                gw.auth.append(self.headers.get("Authorization") or "")
                name = message["params"]["name"]
                args = message["params"]["arguments"]
                gw.calls.append((name, args))
                lease = {"lease_id": "L1", "token": 4242, "holder": "alice", "expires_at": 99}
                outcome = {
                    "lease_acquire": {"ok": True, **lease, "renewed": False},
                    "lease_status": {"ok": True, "leased": True, "lease": lease, **lease},
                    "lease_heartbeat": {"ok": True, **lease},
                    "env_prepare": {"ok": True, "ready": True, "checks": []},
                }.get(name, {"ok": True})
                body = json.dumps({"jsonrpc": "2.0", "id": message["id"],
                                   "result": {"structuredContent": outcome}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/mcp"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def gw(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    fake = FakeGateway()
    ws = wsmod.init(tmp_path / "ws", server="http://127.0.0.1:9", device_build="B_585")
    wsmod.write_private_json(ws.token_path, {"access_token": "acc", "refresh_token": "ref",
                                             "expires_at": int(time.time()) + 3600,
                                             "scope": "jumphost:run", "server": ws.server})
    # cex_client_config 缓存时记下取自哪个服务端（gateway.CLIENT_CONFIG_SOURCE）
    wsmod.write_private_json(ws.client_config_path, {
        "gateway": {"url": fake.url}, "_fetched_from": ws.server})
    yield ws, fake
    fake.close()


def test_the_fencing_token_never_reaches_a_tool_result(gw):
    ws, _fake = gw
    acquired = tools.call("cex_bed_lease", {"workspace": str(ws.root), "action": "acquire"})
    assert acquired["ok"] and acquired["lease_id"] == "L1"
    assert "4242" not in json.dumps(acquired), acquired
    assert wsmod.read_private_json(ws.lease_path)["token"] == 4242, "it stays in the lease file"
    for action in ("status", "heartbeat"):
        out = tools.call("cex_bed_lease", {"workspace": str(ws.root), "action": action})
        assert out["ok"] and "4242" not in json.dumps(out), (action, out)


def test_env_prepare_sends_the_workspace_device_build(gw):
    ws, fake = gw
    tools.call("cex_bed_lease", {"workspace": str(ws.root), "action": "acquire"})
    out = tools.call("cex_env_prepare", {"workspace": str(ws.root)})
    assert out["ok"], out
    name, args = fake.calls[-1]
    assert name == "env_prepare" and args["device_build"] == "B_585"
    assert args["lease_id"] == "L1" and args["token"] == 4242


def test_the_gateway_address_comes_only_from_the_server_config(gw, tmp_path):
    ws, fake = gw
    # config.json 里种一个 gateway_url：不能把令牌改送到那里
    other = FakeGateway()
    try:
        config = ws.config()
        config["gateway_url"] = other.url
        ws.save_config(config)
        tools.call("cex_bed_lease", {"workspace": str(ws.root), "action": "status"})
        assert other.auth == [] and fake.auth, "the planted address never gets the bearer token"
    finally:
        other.close()
    # 缓存的组织常量来自另一个服务端：拒绝，而不是把令牌送去那里的网关
    assert gateway.CLIENT_CONFIG_SOURCE == "_fetched_from"
    wsmod.write_private_json(ws.client_config_path, {
        "gateway": {"url": fake.url}, "_fetched_from": "https://elsewhere.test"})
    out = tools.call("cex_bed_lease", {"workspace": str(ws.root), "action": "status"})
    assert out["ok"] is False and "another server" in out["error"]
