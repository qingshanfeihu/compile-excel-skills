"""数据包同步中途失败不留下"旧清单 + 新旧混杂的文件"（M1）：新版本摆在旁边、全部核过才整包换上；
读包里的文件（cex_cmd_check 用的投影等）按清单 SHA 再核一遍。假服务端在本进程里跑。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cex_client import bundle, tools
from cex_client import workspace as wsmod
from cex_client.errors import ClientError

V1 = {"projections/domain_grammar.json": b'{"v": 1}',
      "cmdtree/vendor_stdlib_10.5_B_1.json": b'{"version": 1}'}
V2 = {"projections/domain_grammar.json": b'{"v": 2, "rules": "NEW"}',
      "cmdtree/vendor_stdlib_10.5_B_1.json": b'{"version": 2}'}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeBundleServer:
    def __init__(self):
        self.files = V1
        self.bundle_id = "a" * 64
        self.fail: set[str] = set()
        self.blobs = {_sha(b): b for b in [*V1.values(), *V2.values()]}
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _send(self, code, body, ctype="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                if self.path.startswith("/v1/builds/B_1/bundle"):
                    manifest = {"schema": "cex.bundle/v1", "build": "B_1",
                                "bundle_id": server.bundle_id, "created_at": "t",
                                "entries": [{"path": p, "sha256": _sha(b), "kind": p.split("/")[0]}
                                            for p, b in sorted(server.files.items())]}
                    return self._send(200, json.dumps(manifest).encode())
                if self.path.startswith("/v1/blobs/"):
                    digest = self.path.rsplit("/", 1)[1]
                    if digest in server.fail:
                        return self._send(502, b"{}")
                    return self._send(200, server.blobs[digest], "application/octet-stream")
                return self._send(404, b"{}")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def synced(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    server = FakeBundleServer()
    ws = wsmod.init(tmp_path / "ws", server=server.base, device_build="B_1")
    wsmod.write_private_json(ws.token_path, {"access_token": "x", "refresh_token": "y",
                                             "expires_at": int(time.time()) + 3600, "scope": "",
                                             "server": ws.server})
    first = tools.call("cex_sync", {"workspace": str(ws.root)})
    assert first["ok"] and first["downloaded"] == 2, first
    yield ws, server
    server.close()


def test_an_interrupted_sync_leaves_the_previous_bundle_whole(synced):
    ws, server = synced
    server.files, server.bundle_id = V2, "b" * 64
    server.fail = {_sha(V2["projections/domain_grammar.json"])}
    out = tools.call("cex_sync", {"workspace": str(ws.root)})
    assert out["ok"] is False
    assert tools.call("cex_status", {"workspace": str(ws.root)})["bundle"]["bundle_id"] == "a" * 64
    for rel, data in V1.items():
        assert (ws.bundle_dir() / rel).read_bytes() == data, rel
    assert bundle.verify_cache(ws)["bundle_id"] == "a" * 64
    assert bundle.entry_path(ws, "cmdtree", "vendor_stdlib_").read_bytes() == V1[
        "cmdtree/vendor_stdlib_10.5_B_1.json"]
    assert [p.name for p in ws.bundle_dir().parent.iterdir()] == ["B_1"], "no staging left behind"

    server.fail = set()
    done = tools.call("cex_sync", {"workspace": str(ws.root)})
    assert done["ok"] and done["bundle_id"] == "b" * 64 and done["downloaded"] == 2, done
    for rel, data in V2.items():
        assert (ws.bundle_dir() / rel).read_bytes() == data, rel
    again = tools.call("cex_sync", {"workspace": str(ws.root)})
    assert again["downloaded"] == 0 and again["unchanged"] == 2


def test_readers_refuse_a_file_that_does_not_match_the_manifest(synced):
    ws, _server = synced
    (ws.bundle_dir() / "cmdtree" / "vendor_stdlib_10.5_B_1.json").write_bytes(b'{"version": 2}')
    with pytest.raises(ClientError, match="cex_sync"):
        bundle.entry_path(ws, "cmdtree", "vendor_stdlib_")
    out = tools.call("cex_cmd_check", {"workspace": str(ws.root), "commands": ["show version"]})
    assert out["ok"] is False and "cex_sync" in out["error"]
