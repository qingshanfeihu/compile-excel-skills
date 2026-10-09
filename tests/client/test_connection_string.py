"""连接串与初始化探活：只拿管理员给的一行连接串就能连上。

- 连接串解析：各种指纹写法统一成 64 位小写十六进制，非法指纹、http 带指纹拒绝；
- cex_init 先探活：地址上不是 compile-excel-server（漏了端口打到别的网站）时提示默认端口和连接串；
  拒绝连接、证书不受信任、证书里没有这个地址、指纹对不上，各给中文说明，什么都不写；
- 带内置 CA 的真服务端（同级 compile-excel-server 检出，TLS 起服务）端到端：init → 登录 →
  自动选构建 → https 同步 → 网关（同一 CA 签发的证书）；通道上有多个构建时列出来，
  用 cex_init 的 device_build 指定，登录保留；登录时给出浏览器证书警告的说明与服务器证书指纹；
- 审查补的：没给 workspace 时先找已有工作区；沿用的指纹在服务端改用正式证书后退回系统证书；
  cex_sync 按参数里的通道选构建；取 CA 与探活限大小、限总时长；PEM 严格解析（拼接的第二张、
  非法字符都拒绝）；没选构建号时文档检索与命令树核对不崩；同一服务端的不同写法不算换服务端。
- 真网关：证书用服务端 ces tls gateway 签发、网关凭 [server] ca_file 信任服务端，编译助手经它租床、
  查状态、还床；不配 ca_file 时网关报的是怎么改配置。
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, SERVER_ROOT

from cex_client import auth, bundle, connect, gateway, manual_search, tools
from cex_client import workspace as wsmod
from cex_client.errors import ClientError

FP = "0123456789abcdef" * 4
SAMPLE_BUILD = "SAMPLE_BUILD_LOCAL"  # provision.py --sample 发布在 stable（与 candidate）上的构建
NEXT_BUILD = "TLS_BUILD_NEXT"        # 本测试另发的构建，只在 candidate 上


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ── 连接串解析 ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("written", [
    FP,
    FP.upper(),
    "sha256:" + FP,
    "SHA256:" + FP.upper(),
    ":".join(FP[i:i + 2] for i in range(0, 64, 2)).upper(),      # openssl -fingerprint 的样子
    " ".join(FP[i:i + 4] for i in range(0, 64, 4)).upper(),      # ces 菜单给人核对的分组
    "%20".join(FP[i:i + 4] for i in range(0, 64, 4)),            # 从浏览器地址栏复制来的
])
def test_fingerprint_forms_normalise_to_lowercase_hex(written):
    assert connect.parse_connection_string(f" https://ces.lab:8900/#ca={written} ") == \
        ("https://ces.lab:8900", FP)


def test_a_plain_address_has_no_fingerprint():
    assert connect.parse_connection_string("https://ces.lab:8900/") == ("https://ces.lab:8900", "")
    assert connect.parse_connection_string("http://127.0.0.1:8900") == ("http://127.0.0.1:8900", "")


@pytest.mark.parametrize("text, says", [
    ("https://ces.lab:8900#ca=" + FP[:-1], "64 位十六进制"),
    ("https://ces.lab:8900#ca=" + FP + "0", "64 位十六进制"),
    ("https://ces.lab:8900#ca=" + "g" * 64, "64 位十六进制"),
    ("https://ces.lab:8900#ca=", "64 位十六进制"),
    ("https://ces.lab:8900#fingerprint=" + FP, "ca=<证书指纹>"),
    ("http://ces.lab:8900#ca=" + FP, "https://"),
])
def test_bad_connection_strings_are_refused(text, says):
    with pytest.raises(ClientError, match=re.escape(says)):
        connect.parse_connection_string(text)


def test_a_bad_fingerprint_writes_nothing(tmp_path):
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": "https://ces.lab:8900#ca=abc"})
    assert out["ok"] is False and "指纹" in out["error"]
    assert not (tmp_path / ".compile-excel").exists()


# ── 探活：地址不对时的提示 ─────────────────────────────────────────────

class _Answering:
    """回环上的假网站：所有路径都回同一个应答（模拟"漏了端口，打到同机别的网站上"）。"""

    def __init__(self, status: int, body: bytes, content_type: str = "text/html"):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_GET(self):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_POST = do_GET

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.mark.parametrize("status, body, says", [
    (404, b"<html>Not Found</html>", "/healthz 回 HTTP 404"),
    (200, b"<html>Welcome to nginx!</html>", "/healthz 回的不是 JSON"),
    (200, b'{"status": "UP"}', "/healthz 自称"),
])
def test_another_service_on_the_address_is_named(tmp_path, status, body, says):
    site = _Answering(status, body)
    try:
        out = tools.call("cex_init", {"workspace": str(tmp_path), "server": site.base})
    finally:
        site.close()
    assert out["ok"] is False and "这个地址上的服务不是 compile-excel-server" in out["error"]
    assert says in out["error"] and "没写端口" not in out["error"]
    assert not (tmp_path / ".compile-excel" / "config.json").exists()


def _http_error_404(*_args, **_kwargs):
    raise urllib.error.HTTPError("http://172.16.2.90/healthz", 404, "Not Found", {},
                                 io.BytesIO(b"<html>404</html>"))


def test_the_missing_port_case_points_at_8900_and_the_connection_string(tmp_path, monkeypatch):
    """真实用户的情形：填了 http://172.16.2.90（漏了端口），那台机器 80 口上的网站回 404。"""
    monkeypatch.setattr(auth._OPENER, "open", _http_error_404)
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": "http://172.16.2.90",
                                  "insecure_lan": True})
    assert out["ok"] is False
    assert "这个地址上的服务不是 compile-excel-server" in out["error"]
    assert "地址里没写端口，服务端默认端口是 8900，例如 https://172.16.2.90:8900" in out["error"]
    assert "连接串" in out["error"]
    assert not (tmp_path / ".compile-excel" / "config.json").exists()

    # 旧工作区（没探活就建好的）登录时打到同一个 404：同样的提示
    ws = wsmod.init(tmp_path / "old", server="http://172.16.2.90", device_build="B_1",
                    insecure_lan=True)
    started = tools.call("cex_login_start", {"workspace": str(ws.root)})
    assert started["ok"] is False and "不是 compile-excel-server" in started["error"]
    assert "https://172.16.2.90:8900" in started["error"]


def test_a_refused_connection_is_explained(tmp_path):
    port = _free_port()
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": f"http://127.0.0.1:{port}"})
    assert out["ok"] is False and f"连不上 http://127.0.0.1:{port}" in out["error"]
    assert "拒绝连接" in out["error"] and "确认服务端已启动" in out["error"]
    assert not (tmp_path / ".compile-excel" / "config.json").exists()


def test_plain_http_to_a_remote_host_still_needs_insecure_lan(tmp_path):
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": "http://10.9.8.7:8900"})
    assert out["ok"] is False and "明文" in out["error"] and "insecure_lan=true" in out["error"]


# ── 构建号可选 ────────────────────────────────────────────────────────

def test_tools_that_need_a_build_say_how_it_gets_chosen(tmp_path, ces_stub):
    init = tools.call("cex_init", {"workspace": str(tmp_path), "server": ces_stub})
    assert init["ok"] and init["device_build"] is None and init["tls"] == "明文（本机回环）"
    status = tools.call("cex_status", {"workspace": str(tmp_path)})
    assert status["device_build_selected"] is False and status["bundle"] is None
    assert status["device_build_hint"] == wsmod.NO_DEVICE_BUILD
    checked = tools.call("cex_cmd_check", {"workspace": str(tmp_path), "commands": ["show version"]})
    assert checked["ok"] is False and checked["error"] == wsmod.NO_DEVICE_BUILD
    # 只改构建号：不再给 server，不探活
    chosen = tools.call("cex_init", {"workspace": str(tmp_path), "device_build": "B_9"})
    assert chosen["ok"] and chosen["device_build"] == "B_9" and chosen["server"] == ces_stub


def test_changing_server_or_fingerprint_replaces_the_stored_ca(tmp_path):
    ca_pem = _sample_ca_pem()
    if ca_pem is None:
        pytest.skip("cryptography is not installed")
    fp = wsmod.ca_fingerprint(ca_pem)
    ws = wsmod.init(tmp_path, server="https://a.example.test:8900", ca_sha256=fp, ca_pem=ca_pem)
    assert ws.ca_path.is_file() and ws.ssl_context() is not None
    wsmod.write_private_json(ws.token_path, {"access_token": "x", "server": ws.server})
    wsmod.init(tmp_path, server="https://a.example.test:8900", ca_sha256=fp, ca_pem=ca_pem,
               device_build="B_2")
    assert ws.token_path.exists(), "same server, same CA: the session stays"
    wsmod.init(tmp_path, server="https://a.example.test:8900")
    assert not ws.ca_path.exists() and not ws.token_path.exists()
    assert ws.ssl_context() is None
    wsmod.init(tmp_path, server="https://b.example.test:8900", ca_sha256=fp, ca_pem=ca_pem)
    ws.ca_path.write_text(ca_pem.replace("A", "B", 1), encoding="ascii")
    with pytest.raises(ClientError, match="ca.pem"):
        ws.ssl_context()


def _sample_ca_pem() -> str | None:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
    except ImportError:
        return None
    import datetime as dt

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test CA")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now).not_valid_after(now + dt.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


# ── 带内置 CA 的真服务端 ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def tls_server(tmp_path_factory):
    if not (SERVER_ROOT / "deploy" / "certs.py").is_file():
        pytest.skip(f"找不到带内置 CA 的 compile-excel-server 检出 {SERVER_ROOT}（设 CES_SERVER_ROOT）")
    for module in ("fastapi", "uvicorn", "cryptography"):
        pytest.importorskip(module)
    root = tmp_path_factory.mktemp("tls_srv")
    data = root / "data"

    def run(*argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                              timeout=120, cwd=SERVER_ROOT, check=False)

    proc = run(str(SERVER_ROOT / "deploy" / "provision.py"), "--data", str(data), "--sample")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    code_file = root / "alice.code"
    proc = run(str(SERVER_ROOT / "ces_main.py"), "users", "add", "alice", "--data", str(data),
               "--out", str(code_file))
    assert proc.returncode == 0, proc.stdout + proc.stderr

    sys.path.insert(0, str(SERVER_ROOT))
    try:
        from deploy import certs
        from registry import Registry
    finally:
        sys.path.remove(str(SERVER_ROOT))
    reg = Registry(data / "registry")
    projection = {"version": "9.9", "device_os_build": "101",
                  "heads": {"show version": {"src": "xml", "pmax": 0}}}
    files = {
        "cmdtree/vendor_stdlib_9.9_101.json": json.dumps(projection).encode(),
        "projections/domain_grammar.json": b'{"destructive_commands": {"patterns": []}}',
        "template/case_template.xlsx":
            (REPO_ROOT / "cex_core" / "templates" / "case_template.xlsx").read_bytes(),
        "spec/docs/规格说明.md": "# 下一版规格\n".encode(),
    }
    entries = []
    for rel, payload in files.items():
        path = root / "bundle_src" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        blob = reg.put_blob_file(path)
        entries.append({"kind": rel.split("/")[0], "path": rel, "sha256": blob["sha256"],
                        "media_type": "application/octet-stream", "meta": {}})
    reg.submit_bundle(NEXT_BUILD, entries, publisher="test")  # 新包只进 candidate
    cert, key = certs.ensure_server_cert(data, ["127.0.0.1", "localhost"])
    ca_path = certs.ca_paths(data)[0]
    fingerprint = certs.fingerprint(ca_path)

    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, str(SERVER_ROOT / "ces_main.py"), "serve", "--data", str(data),
         "--host", "127.0.0.1", "--port", str(port), "--tls-cert", str(cert),
         "--tls-key", str(key)],
        cwd=SERVER_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"https://127.0.0.1:{port}"
    context = ssl.create_default_context(cafile=str(ca_path))
    for _ in range(150):
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=1, context=context):
                break
        except OSError:
            time.sleep(0.2)
    else:
        server.kill()
        pytest.fail("TLS server did not start")
    yield {"base": base, "fp": fingerprint, "context": context, "data": data, "certs": certs,
           "code": code_file.read_text(encoding="utf-8").strip(), "cert": Path(cert)}
    server.terminate()
    server.wait(timeout=10)


def _browser_form(der: bytes) -> str:
    """浏览器证书详情里 SHA-256 指纹的写法：大写、两位一组、空格分隔。"""
    digest = hashlib.sha256(der).hexdigest().upper()
    return " ".join(digest[i:i + 2] for i in range(0, 64, 2))


def _leaf_der(cert_path: Path) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    return x509.load_pem_x509_certificates(cert_path.read_bytes())[0].public_bytes(
        serialization.Encoding.DER)


def _login(ws_dir: Path, srv) -> dict:
    started = tools.call("cex_login_start", {"workspace": str(ws_dir)})
    assert started["ok"], started
    assert started["verification_uri"].startswith(srv["base"])
    # 服务端用内置 CA：浏览器会报证书警告，给一段说明和服务器证书的指纹让用户核对
    note = started["browser_certificate"]
    assert _browser_form(_leaf_der(srv["cert"])) in note
    assert str(ws_dir.resolve() / ".compile-excel" / "ca.pem") in note
    assert "browser_certificate" in started["next"]
    body = urllib.parse.urlencode({"user_code": started["user_code"], "username": "alice",
                                   "access_code": srv["code"]}).encode()
    with urllib.request.urlopen(urllib.request.Request(srv["base"] + "/activate", data=body),
                                timeout=10, context=srv["context"]) as resp:
        assert resp.status == 200
    done = tools.call("cex_login_wait", {"workspace": str(ws_dir), "timeout_s": 30})
    assert done["ok"], done
    return done


def test_connection_string_end_to_end(tls_server, tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    srv = tls_server
    ws_dir = tmp_path / "project"
    ws_dir.mkdir()
    grouped = " ".join(srv["fp"][i:i + 4] for i in range(0, 64, 4)).upper()
    init = tools.call("cex_init", {"workspace": str(ws_dir),
                                   "server": f"{srv['base']}#ca={grouped}"})
    assert init["ok"], init
    assert init["server"] == srv["base"] and init["device_build"] is None
    assert init["tls"] == "内置 CA（指纹已核对）"
    state = ws_dir / ".compile-excel"
    stored = (state / "ca.pem").read_text(encoding="ascii")
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(stored)).hexdigest() == srv["fp"]
    config = json.loads((state / "config.json").read_text(encoding="utf-8"))
    assert config["ca_sha256"] == srv["fp"] and config["device_build"] == ""

    status = tools.call("cex_status", {"workspace": str(ws_dir)})
    assert status["tls"] == "内置 CA（指纹已核对）" and status["device_build_selected"] is False
    assert status["logged_in"] is False and status["login_hint"].startswith("还没有登录")

    # stable 上只有样例构建（NEXT_BUILD 只在 candidate 上，不算）：登录后自动选它
    done = _login(ws_dir, srv)
    assert done["device_build"] == SAMPLE_BUILD and SAMPLE_BUILD in done["device_build_note"]
    assert "builds" not in done
    status = tools.call("cex_status", {"workspace": str(ws_dir)})
    assert status["device_build"] == SAMPLE_BUILD and status["device_build_selected"] is True

    synced = tools.call("cex_sync", {"workspace": str(ws_dir)})
    assert synced["ok"] and synced["source"] == "server" and synced["build"] == SAMPLE_BUILD, synced
    assert synced["downloaded"] == sum(synced["entries"].values()) > 0
    assert (state / "bundle" / SAMPLE_BUILD / "manifest.json").is_file()

    # 同一服务端只给地址（cex_status 里看到的那个）重跑 cex_init：沿用核对过的 CA，登录与构建号保留
    again = tools.call("cex_init", {"workspace": str(ws_dir), "server": srv["base"]})
    assert again["ok"] and again["tls"] == "内置 CA（指纹已核对）"
    assert again["device_build"] == SAMPLE_BUILD
    assert tools.call("cex_status", {"workspace": str(ws_dir)})["logged_in"] is True

    # 网关的证书由同一个 CA 签发：工具调用经工作区的上下文校验它
    gateway = _TlsGateway(srv["certs"], srv["data"], tmp_path / "gw")
    try:
        wsmod.write_private_json(state / "client_config.json", {
            "gateway": {"url": gateway.url}, "_fetched_from": srv["base"]})
        leased = tools.call("cex_bed_lease", {"workspace": str(ws_dir), "action": "status"})
        assert leased["ok"] and leased["leased"] is False, leased
        assert gateway.auth and gateway.auth[0].startswith("Bearer ")
    finally:
        gateway.close()

    out = tools.call("cex_logout", {"workspace": str(ws_dir)})
    assert out["ok"] and out["revoked_on_server"] is True


def test_wrong_fingerprint_untrusted_certificate_and_missing_address(tls_server, tmp_path):
    srv = tls_server
    port = srv["base"].rsplit(":", 1)[1]
    wrong = tools.call("cex_init", {"workspace": str(tmp_path), "server": f"{srv['base']}#ca={FP}"})
    assert wrong["ok"] is False and "指纹不一致" in wrong["error"]
    assert "调包" in wrong["error"] and "抄错" in wrong["error"]
    assert not (tmp_path / ".compile-excel" / "ca.pem").exists()
    assert not (tmp_path / ".compile-excel" / "config.json").exists()

    untrusted = tools.call("cex_init", {"workspace": str(tmp_path), "server": srv["base"]})
    assert untrusted["ok"] is False and "证书不受信任" in untrusted["error"]
    assert "连接串" in untrusted["error"]

    # 127.1 也是回环，但证书里只写了 127.0.0.1 与 localhost
    elsewhere = tools.call("cex_init", {"workspace": str(tmp_path),
                                        "server": f"https://127.1:{port}#ca={srv['fp']}"})
    assert elsewhere["ok"] is False and "证书里没有这个地址（127.1）" in elsewhere["error"]
    assert "ces 菜单里重新签发证书" in elsewhere["error"]

    # 端口对、协议写成了 http：服务端只说 TLS
    plain = tools.call("cex_init", {"workspace": str(tmp_path), "server": f"http://127.0.0.1:{port}"})
    assert plain["ok"] is False and "https://" in plain["error"]
    assert not (tmp_path / ".compile-excel" / "config.json").exists()


def test_several_builds_are_listed_and_cex_init_sets_the_choice(tls_server, tmp_path,
                                                                 monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    srv = tls_server
    ws_dir = tmp_path / "candidate"
    init = tools.call("cex_init", {"workspace": str(ws_dir), "channel": "candidate",
                                   "server": f"{srv['base']}#ca=sha256:{srv['fp'].upper()}"})
    assert init["ok"] and init["channel"] == "candidate", init
    done = _login(ws_dir, srv)
    assert done["device_build"] is None and done["builds"] == [SAMPLE_BUILD, NEXT_BUILD]
    assert "cex_init 的 device_build" in done["device_build_note"]
    refused = tools.call("cex_sync", {"workspace": str(ws_dir)})
    assert refused["ok"] is False and NEXT_BUILD in refused["error"] and "多个构建" in refused["error"]

    chosen = tools.call("cex_init", {"workspace": str(ws_dir), "device_build": NEXT_BUILD})
    assert chosen["ok"] and chosen["device_build"] == NEXT_BUILD and chosen["channel"] == "candidate"
    assert (ws_dir / ".compile-excel" / "token.json").exists(), "same server: the login stays"
    synced = tools.call("cex_sync", {"workspace": str(ws_dir)})
    assert synced["ok"] and synced["build"] == NEXT_BUILD and synced["channel"] == "candidate", synced
    spec = ws_dir / ".compile-excel" / "bundle" / NEXT_BUILD / "spec" / "docs" / "规格说明.md"
    assert spec.read_text(encoding="utf-8") == "# 下一版规格\n"


class _TlsGateway:
    """假网关：证书由服务端的内置 CA 签发，按网关 tools/call 的应答形状回 lease_status。"""

    def __init__(self, certs, data: Path, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        cert, key = folder / "gw.pem", folder / "gw.key"
        certs.issue(data, ["127.0.0.1"], cert, key)
        self.auth: list[str] = []
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                size = int(self.headers.get("Content-Length") or 0)
                message = json.loads(self.rfile.read(size))
                gw.auth.append(self.headers.get("Authorization") or "")
                body = json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": {
                    "structuredContent": {"ok": True, "leased": False}}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert), str(key))
        self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
        self.url = f"https://127.0.0.1:{self.httpd.server_address[1]}/mcp"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# ── 审查补的：测试用证书与可换证书、可换应答的假服务端 ──────────────────

class _Pki:
    """一套测试证书：自签的 CA，和它给 127.0.0.1 / localhost 签发的服务器证书。"""

    def __init__(self, folder: Path, name: str):
        import datetime as dt
        import ipaddress

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

        folder.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now(dt.timezone.utc)
        valid = {"not_valid_before": now - dt.timedelta(minutes=5),
                 "not_valid_after": now + dt.timedelta(days=2)}
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
        ca = (x509.CertificateBuilder(issuer_name=ca_name, subject_name=ca_name,
                                      public_key=ca_key.public_key(),
                                      serial_number=x509.random_serial_number(), **valid)
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                           key_encipherment=False, data_encipherment=False,
                                           key_agreement=False, key_cert_sign=True, crl_sign=True,
                                           encipher_only=False, decipher_only=False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
                             critical=False)
              .sign(ca_key, hashes.SHA256()))
        key = ec.generate_private_key(ec.SECP256R1())
        leaf = (x509.CertificateBuilder(
                    issuer_name=ca_name,
                    subject_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")]),
                    public_key=key.public_key(), serial_number=x509.random_serial_number(), **valid)
                .add_extension(x509.SubjectAlternativeName([
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]),
                    critical=False)
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                               critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    ca_key.public_key()), critical=False)
                .sign(ca_key, hashes.SHA256()))
        pem, der = serialization.Encoding.PEM, serialization.Encoding.DER
        self.ca_pem = ca.public_bytes(pem).decode("ascii")
        self.ca_der = ca.public_bytes(der)
        self.fp = hashlib.sha256(self.ca_der).hexdigest()
        self.leaf_der = leaf.public_bytes(der)
        self.ca_path = folder / "ca.pem"
        self.ca_path.write_text(self.ca_pem, encoding="ascii")
        self.cert_path, self.key_path = folder / "server.pem", folder / "server.key"
        self.cert_path.write_bytes(leaf.public_bytes(pem))
        self.key_path.write_bytes(key.private_bytes(
            pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    def server_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.cert_path), str(self.key_path))
        return context


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    pytest.importorskip("cryptography")
    folder = tmp_path_factory.mktemp("pki")
    return {"builtin": _Pki(folder / "builtin", "服务端内置 CA"),
            "public": _Pki(folder / "public", "正式机构 CA"),
            "other": _Pki(folder / "other", "别的 CA")}


HEALTHZ = (200, json.dumps({"ok": True, "service": "compile-excel-server"}).encode())
Route = tuple[int, bytes] | Callable[[BaseHTTPRequestHandler], None]


class _Site:
    """回环上的假服务端：给了 context 就是 https（证书可在测试中途换），否则明文。
    routes 里每个路径的应答是 (状态码, 正文)，或自己写原始应答的函数（模拟慢速发送、不带长度的长应答）。"""

    def __init__(self, context: ssl.SSLContext | None = None):
        self.context = context
        self.routes: dict[str, Route] = {"/healthz": HEALTHZ}
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def setup(self):
                self.request.settimeout(10)
                if isinstance(self.request, ssl.SSLSocket):
                    self.request.do_handshake()
                super().setup()

            def _answer(self):
                size = int(self.headers.get("Content-Length") or 0)
                if size:
                    self.rfile.read(size)
                route = site.routes.get(self.path.split("?", 1)[0],
                                        (404, b'{"detail": "Not Found"}'))
                if callable(route):
                    self.close_connection = True
                    try:
                        route(self)
                    except OSError:  # 客户端读够了（或到点了）就断开
                        pass
                    return
                status, body = route
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _answer

        class Server(ThreadingHTTPServer):
            daemon_threads = True

            def get_request(self):
                sock, addr = super().get_request()
                if site.context is not None:
                    sock = site.context.wrap_socket(sock, server_side=True,
                                                    do_handshake_on_connect=False)
                return sock, addr

            def handle_error(self, request, client_address):
                return  # 客户端不认证书、读到一半断开：都是测试里预期的

        self.httpd = Server(("127.0.0.1", 0), Handler)
        scheme = "https" if context is not None else "http"
        self.base = f"{scheme}://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def site_factory():
    sites: list[_Site] = []

    def make(context: ssl.SSLContext | None = None) -> _Site:
        sites.append(_Site(context))
        return sites[-1]

    yield make
    for site in sites:
        site.close()


def _drip(data: bytes, *, head: bytes = b"", every: float = 0.05):
    """先一次发出 head，再每隔 every 秒发 data 的一个字节。"""
    def answer(handler: BaseHTTPRequestHandler) -> None:
        handler.wfile.write(head)
        for index in range(len(data)):
            handler.wfile.write(data[index:index + 1])
            time.sleep(every)
    return answer


def _endless(handler: BaseHTTPRequestHandler) -> None:
    """不带长度、一直发的应答（按连接关闭定界）。"""
    handler.wfile.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/x-pem-file\r\n\r\n")
    for _ in range(64):
        handler.wfile.write(b"A" * 65536)


def _config(ws_dir: Path) -> dict:
    return json.loads((ws_dir / ".compile-excel" / "config.json").read_text(encoding="utf-8"))


def _give_token(ws_dir: Path) -> None:
    ws = wsmod.Workspace(ws_dir.resolve())
    wsmod.write_private_json(ws.token_path, {"access_token": "a", "refresh_token": "r",
                                             "expires_at": int(time.time()) + 3600,
                                             "server": ws.server})


# ── 1. 没给 workspace：先找已有的工作区 ──────────────────────────────────

def test_cex_init_without_workspace_updates_the_existing_one(tmp_path, monkeypatch, ces_stub):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    project = (tmp_path / "project").resolve()
    deep = project / "docs" / "deep"
    deep.mkdir(parents=True)
    assert tools.call("cex_init", {"workspace": str(project), "server": ces_stub})["ok"]

    # 在子目录里只给构建号：改的是上级那个工作区，不报"缺少服务端地址"
    monkeypatch.chdir(deep)
    chosen = tools.call("cex_init", {"device_build": "B_1"})
    assert chosen["ok"] and chosen["workspace"] == str(project), chosen
    assert chosen["device_build"] == "B_1" and chosen["server"] == ces_stub
    # 在子目录里补上地址再调：仍是上级那个，不新建嵌套的工作区，构建号保留
    again = tools.call("cex_init", {"server": ces_stub})
    assert again["ok"] and again["workspace"] == str(project) and again["device_build"] == "B_1"
    assert not (deep / ".compile-excel").exists()
    assert not (project / "docs" / ".compile-excel").exists()

    # CEX_WORKSPACE 指着它、当前目录在别处：同样改它
    elsewhere = (tmp_path / "elsewhere").resolve()
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("CEX_WORKSPACE", str(project))
    switched = tools.call("cex_init", {"channel": "candidate"})
    assert switched["ok"] and switched["workspace"] == str(project), switched
    assert switched["channel"] == "candidate" and switched["device_build"] == "B_1"
    assert not (elsewhere / ".compile-excel").exists()

    # CEX_WORKSPACE 指着还没初始化的文件夹：建在那里（其他工具认的就是它）
    fresh = (tmp_path / "fresh").resolve()
    fresh.mkdir()
    monkeypatch.setenv("CEX_WORKSPACE", str(fresh))
    created = tools.call("cex_init", {"server": ces_stub})
    assert created["ok"] and created["workspace"] == str(fresh)
    assert tools.call("cex_status", {})["workspace"] == str(fresh)

    # 哪儿都没有工作区：建在当前目录
    monkeypatch.delenv("CEX_WORKSPACE")
    here = tools.call("cex_init", {"server": ces_stub})
    assert here["ok"] and here["workspace"] == str(elsewhere)


# ── 2. 沿用的指纹：服务端改用正式证书后退回系统证书库 ────────────────────

def test_an_inherited_fingerprint_gives_way_when_the_server_drops_its_ca(
        tmp_path, monkeypatch, pki, site_factory):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    builtin, public = pki["builtin"], pki["public"]
    site = site_factory(builtin.server_context())
    site.routes["/ca.pem"] = (200, builtin.ca_pem.encode("ascii"))
    ws_dir = tmp_path / "project"
    init = tools.call("cex_init", {"workspace": str(ws_dir), "server": f"{site.base}#ca={builtin.fp}"})
    assert init["ok"] and init["tls"] == "内置 CA（指纹已核对）", init
    _give_token(ws_dir)
    state = ws_dir / ".compile-excel"

    # 服务端改用正式机构签发的证书，不再发 /ca.pem
    site.context = public.server_context()
    site.routes["/ca.pem"] = (404, b'{"detail": "no built-in CA"}')
    # 用户这次明确给了 #ca=：照旧报"没有启用内置 CA"，什么都不动
    explicit = tools.call("cex_init", {"workspace": str(ws_dir),
                                       "server": f"{site.base}#ca={builtin.fp}"})
    assert explicit["ok"] is False and "服务端没有启用内置 CA" in explicit["error"]
    # 只给地址、系统证书库还不认这张证书：拒绝，工作区原样（指纹、ca.pem、登录都在）
    untrusted = tools.call("cex_init", {"workspace": str(ws_dir), "server": site.base})
    assert untrusted["ok"] is False and "证书不受信任" in untrusted["error"], untrusted
    assert _config(ws_dir)["ca_sha256"] == builtin.fp
    assert (state / "ca.pem").is_file() and (state / "token.json").is_file()

    # 系统证书库认这张证书了：改用它校验，清掉指纹和 ca.pem，旧登录作废
    monkeypatch.setenv("SSL_CERT_FILE", str(public.ca_path))
    moved = tools.call("cex_init", {"workspace": str(ws_dir), "server": site.base})
    assert moved["ok"] and moved["tls"] == "系统证书", moved
    assert _config(ws_dir)["ca_sha256"] == "" and not (state / "ca.pem").exists()
    assert not (state / "token.json").exists()
    status = tools.call("cex_status", {"workspace": str(ws_dir)})
    assert status["tls"] == "系统证书" and status["logged_in"] is False


# ── 3. cex_sync(channel=…) 按参数里的通道选构建 ──────────────────────────

def test_cex_sync_chooses_the_build_on_the_channel_it_syncs(tmp_path, monkeypatch, ces_stub):
    ws_dir = tmp_path / "project"
    assert tools.call("cex_init", {"workspace": str(ws_dir), "server": ces_stub})["ok"]  # stable
    asked: list[str] = []
    synced: list[Any] = []

    def published(ws, channel):
        asked.append(channel)
        return {"stable": ["S_1", "S_2"], "candidate": ["C_1"]}[channel]

    def sync(ws, channel=None):
        synced.append(channel)
        return {"ok": True, "build": ws.device_build, "channel": channel or ws.channel}

    monkeypatch.setattr(auth, "load_token", lambda ws: {"access_token": "a"})
    monkeypatch.setattr(connect, "published_builds", published)
    monkeypatch.setattr(bundle, "sync", sync)
    out = tools.call("cex_sync", {"workspace": str(ws_dir), "channel": "candidate"})
    assert out["ok"] and out["build"] == "C_1" and out["channel"] == "candidate", out
    assert asked == ["candidate"] and synced == ["candidate"]
    assert "candidate" in out["device_build_note"]

    # 不带 channel：按工作区的通道（stable，上面有两个）选，列出来让用户挑
    config = _config(ws_dir)
    wsmod.Workspace(ws_dir.resolve()).save_config({**config, "device_build": ""})
    refused = tools.call("cex_sync", {"workspace": str(ws_dir)})
    assert refused["ok"] is False and "S_1、S_2" in refused["error"] and asked[-1] == "stable"
    with pytest.raises(ClientError, match="stable 或 candidate"):
        connect.choose_build(wsmod.Workspace(ws_dir.resolve()), "nightly")


# ── 4. 取 CA、探活：限大小、限总时长 ─────────────────────────────────────

@pytest.mark.parametrize("answer", [
    pytest.param((200, b"A" * (1 << 20)), id="declared-length"),
    pytest.param(_endless, id="no-length"),
])
def test_an_oversized_ca_answer_is_refused(tmp_path, pki, site_factory, answer):
    site = site_factory(pki["other"].server_context())
    site.routes["/ca.pem"] = answer
    started = time.monotonic()
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": f"{site.base}#ca={FP}"})
    assert out["ok"] is False and "超过 65536 字节" in out["error"], out
    assert time.monotonic() - started < 10
    assert not (tmp_path / ".compile-excel" / "config.json").exists()


def test_a_slow_ca_answer_is_cut_at_the_deadline(tmp_path, monkeypatch, pki, site_factory):
    monkeypatch.setattr(connect, "FETCH_DEADLINE", 1.0)
    site = site_factory(pki["other"].server_context())
    # 应答头一个字节一个字节地慢慢发：每次都在单次超时之内，但总时长没有尽头
    site.routes["/ca.pem"] = _drip(b"HTTP/1.0 200 OK\r\n" + b"X-Pad: 1\r\n" * 200)
    started = time.monotonic()
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": f"{site.base}#ca={FP}"})
    elapsed = time.monotonic() - started
    assert out["ok"] is False and "1 秒内没有回完应答" in out["error"], out
    assert elapsed < 4, elapsed
    assert not (tmp_path / ".compile-excel" / "config.json").exists()


def test_the_healthz_probe_is_capped_too(tmp_path, monkeypatch, site_factory):
    site = site_factory()  # 明文回环
    site.routes["/healthz"] = (200, b" " * (1 << 20))
    big = tools.call("cex_init", {"workspace": str(tmp_path), "server": site.base})
    assert big["ok"] is False and "超过 65536 字节" in big["error"], big

    monkeypatch.setattr(connect, "FETCH_DEADLINE", 1.0)
    site.routes["/healthz"] = _drip(b"{" + b" " * 500 + b"}",
                                   head=b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
    started = time.monotonic()
    slow = tools.call("cex_init", {"workspace": str(tmp_path), "server": site.base})
    assert slow["ok"] is False and "秒内没有回完应答" in slow["error"], slow
    assert time.monotonic() - started < 4
    assert not (tmp_path / ".compile-excel" / "config.json").exists()


# ── 5. PEM 严格解析 ───────────────────────────────────────────────────

def _corrupt_body(pem: str, junk: str) -> str:
    lines = pem.strip().splitlines()
    lines[1] = lines[1][:10] + junk + lines[1][10:]
    return "\n".join(lines) + "\n"


def test_pem_parsing_is_strict(pki):
    ca, other = pki["builtin"], pki["other"]
    assert wsmod.pem_to_der(ca.ca_pem) == ca.ca_der
    assert wsmod.pem_to_der(ca.ca_pem.replace("\n", "\r\n")) == ca.ca_der
    assert wsmod.ca_fingerprint(ca.ca_pem) == ca.fp
    bad = {
        "two certificates": ca.ca_pem + other.ca_pem,
        "junk inside the base64": _corrupt_body(ca.ca_pem, "!?"),
        "text before the block": "subject=服务端内置 CA\n" + ca.ca_pem,
        "text after the block": ca.ca_pem + "trailing\n",
        "a private key block": ca.ca_pem.replace("CERTIFICATE", "PRIVATE KEY"),
        "bytes after the DER": ssl.DER_cert_to_PEM_cert(ca.ca_der + b"\x00\x00"),
        "not DER at all": ssl.DER_cert_to_PEM_cert(b"hello world"),
    }
    for text in bad.values():
        with pytest.raises(ValueError):
            wsmod.pem_to_der(text)
        with pytest.raises(ValueError):
            wsmod.ca_fingerprint(text)
    # 宽松解码（ssl.PEM_cert_to_DER_cert 用的就是它）把夹杂的字符悄悄扔掉，照样算出这张的指纹
    lenient = base64.b64decode(re.sub(r"-----[^-]+-----|\s", "",
                                      bad["junk inside the base64"]))
    assert hashlib.sha256(lenient).hexdigest() == ca.fp


def test_a_ca_answer_with_a_second_certificate_is_refused(tmp_path, pki, site_factory):
    ca, other = pki["builtin"], pki["other"]
    site = site_factory(ca.server_context())
    # 第一张对得上指纹：宽松解码会放行，严格解析不收
    site.routes["/ca.pem"] = (200, (ca.ca_pem + other.ca_pem).encode("ascii"))
    out = tools.call("cex_init", {"workspace": str(tmp_path), "server": f"{site.base}#ca={ca.fp}"})
    assert out["ok"] is False and "根证书格式不对" in out["error"], out
    assert not (tmp_path / ".compile-excel" / "ca.pem").exists()
    assert not (tmp_path / ".compile-excel" / "config.json").exists()

    # 另一个网站对所有路径都回 200 网页：说的是"不是 compile-excel-server"
    site.routes["/ca.pem"] = (200, b"<html>hello</html>")
    site.routes["/healthz"] = (200, b"<html>hello</html>")
    other_site = tools.call("cex_init", {"workspace": str(tmp_path),
                                         "server": f"{site.base}#ca={ca.fp}"})
    assert other_site["ok"] is False and "不是 compile-excel-server" in other_site["error"]
    assert "/ca.pem 回的不是证书" in other_site["error"]


def test_the_stored_ca_is_parsed_strictly_and_only_its_one_certificate_is_trusted(
        tmp_path, pki, site_factory):
    ca, other = pki["builtin"], pki["other"]
    ws = wsmod.init(tmp_path, server="https://127.0.0.1:9", ca_sha256=ca.fp, ca_pem=ca.ca_pem)
    assert ws.ssl_context() is not None
    original = ws.ca_path.read_text(encoding="ascii")
    # 有人在 ca.pem 后面追加了一张：整份拒绝，不会把追加的那张也当成可信的
    ws.ca_path.write_text(original + other.ca_pem, encoding="ascii")
    with pytest.raises(ClientError, match="不是恰好一张证书"):
        ws.ssl_context()
    ws.ca_path.write_text(_corrupt_body(original, "!"), encoding="ascii")
    with pytest.raises(ClientError, match="ca.pem"):
        ws.ssl_context()

    # 信任的就是解出的那一张：它签发的证书能过，别的 CA 签发的不行
    ws.ca_path.write_text(original, encoding="ascii")
    context = ws.ssl_context()
    for pki_name, ok in (("builtin", True), ("other", False)):
        site = site_factory(pki[pki_name].server_context())
        host, port = "127.0.0.1", int(site.base.rsplit(":", 1)[1])
        with socket.create_connection((host, port), timeout=5) as raw:
            if ok:
                with context.wrap_socket(raw, server_hostname=host) as tls:
                    assert tls.getpeercert(binary_form=True) == pki[pki_name].leaf_der
            else:
                with pytest.raises(ssl.SSLCertVerificationError):
                    context.wrap_socket(raw, server_hostname=host)


# ── 6. 还没选构建号：文档检索、命令树核对不崩 ────────────────────────────

def test_docs_query_without_a_build_still_searches_server_documents(tmp_path, monkeypatch,
                                                                    ces_stub):
    ws_dir = tmp_path / "project"
    assert tools.call("cex_init", {"workspace": str(ws_dir), "server": ces_stub})["ok"]
    ws = wsmod.Workspace(ws_dir.resolve())
    local = manual_search.query(ws, "slb", 3)
    assert local["ok"] is False and local["build"] is None and local["error"] == wsmod.NO_DEVICE_BUILD

    monkeypatch.setattr(auth, "request_json", lambda *a, **k: {"results": [
        {"title": "规格说明", "snippet": "slb ...", "ref": "x"}]})
    out = tools.call("cex_docs_query", {"workspace": str(ws_dir), "q": "slb"})
    assert out["ok"] and out["build"] is None and out["server_searched"] is True, out
    assert out["local_note"] == wsmod.NO_DEVICE_BUILD
    assert [row["source"] for row in out["results"]] == ["server_document"]

    def down(*args, **kwargs):
        raise ClientError("连不上服务端")

    monkeypatch.setattr(auth, "request_json", down)
    offline = tools.call("cex_docs_query", {"workspace": str(ws_dir), "q": "slb"})
    assert offline["ok"] is False and wsmod.NO_DEVICE_BUILD in offline["error"], offline
    assert "Traceback" not in json.dumps(offline)


def test_cmdtree_check_without_a_build_warns_instead_of_crashing(tmp_path):
    ws_dir = tmp_path / "project"
    wsmod.init(ws_dir, server="http://127.0.0.1:9")  # 不联网；没有构建号
    tree = tmp_path / "cmdtree_585.xml"
    tree.write_text('<cmdtree><scope><menu name="show"><item name="version"/></menu></scope>'
                    '</cmdtree>', encoding="utf-8")
    cases = ws_dir / "cases.json"
    cases.write_text(json.dumps({"cases": [{"autoid": "1", "steps": [
        {"e": "APV_0", "f": "cmd_config", "g": "show version"}]}]}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "CEX_WORKSPACE"}
    script = REPO_ROOT / "skills" / "compile-excel" / "scripts" / "cmdtree_check.py"
    proc = subprocess.run([sys.executable, str(script), "--cases", str(cases), "--tree", str(tree)],
                          capture_output=True, text=True, env=env, timeout=60, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["ok_flag"] is True and report["checked"] == 1
    assert any(wsmod.NO_DEVICE_BUILD in warning and "585" in warning
               for warning in report["warnings"]), report


# ── 7. 同一服务端的不同写法 ───────────────────────────────────────────

@pytest.mark.parametrize("written, normal", [
    ("HTTPS://CES.Lab:8900/", "https://ces.lab:8900"),
    ("https://ces.lab:443", "https://ces.lab"),
    ("http://LocalHost:80/", "http://localhost"),
    ("http://127.0.0.1:443", "http://127.0.0.1:443"),
    ("https://ces.lab:80", "https://ces.lab:80"),
    ("https://[0:0:0:0:0:0:0:1]:8900", "https://[::1]:8900"),
    ("https://[FE80::0001]:443/", "https://[fe80::1]"),
    ("https://ces.lab:8900/sub/", "https://ces.lab:8900/sub"),
])
def test_server_addresses_are_normalised(written, normal):
    assert wsmod.normalize_server_url(written) == normal
    assert wsmod.same_server(written, normal)


def test_the_same_server_written_differently_keeps_the_login(tmp_path, monkeypatch):
    monkeypatch.setattr(connect, "probe", lambda *args, **kwargs: "")  # 不联网
    ws = connect.setup(tmp_path, server="https://ces.lab:8900")
    _give_token(tmp_path)
    for written in ("HTTPS://CES.Lab:8900/", "https://Ces.LAB:8900"):
        ws = connect.setup(tmp_path, server=written)
        assert _config(tmp_path)["server"] == "https://ces.lab:8900"
        assert auth.load_token(ws)["access_token"] == "a", written

    ws = connect.setup(tmp_path, server="https://CES.lab:443/")
    assert _config(tmp_path)["server"] == "https://ces.lab" and not ws.token_path.exists()
    _give_token(tmp_path)
    connect.setup(tmp_path, server="https://ces.lab")
    assert ws.token_path.exists(), "an explicit :443 is the same server"

    connect.setup(tmp_path, server="https://[0:0:0:0:0:0:0:1]:8900")
    assert _config(tmp_path)["server"] == "https://[::1]:8900" and not ws.token_path.exists()
    _give_token(tmp_path)
    connect.setup(tmp_path, server="https://[::1]:8900/")
    assert ws.token_path.exists(), "two spellings of one IPv6 address are the same server"


def test_an_old_workspace_with_an_unnormalised_address_keeps_its_session(tmp_path, ces_stub):
    """旧版写下的地址没规范化：令牌、登录中的状态、组织常量缓存都按规范化后的写法认。"""
    written = ces_stub.replace("http://", "HTTP://") + "/"
    ws = wsmod.Workspace(tmp_path.resolve())
    ws.state_dir.mkdir()
    ws.save_config({"server": written, "device_build": "B_1", "channel": "stable",
                    "allow_insecure_http": False, "ca_sha256": ""})
    wsmod.write_private_json(ws.token_path, {"access_token": "a", "server": written})
    wsmod.write_private_json(ws.client_config_path, {
        "gateway": {"url": "http://127.0.0.1:9/mcp"}, gateway.CLIENT_CONFIG_SOURCE: written})
    assert ws.server == ces_stub
    assert auth.load_token(ws)["access_token"] == "a"
    assert gateway.gateway_url(ws) == "http://127.0.0.1:9/mcp"
    # 只改构建号也把地址写成规范的
    out = tools.call("cex_init", {"workspace": str(tmp_path), "device_build": "B_2"})
    assert out["ok"] and _config(tmp_path)["server"] == ces_stub
    # 再给同一地址（规范写法）：登录保留
    again = tools.call("cex_init", {"workspace": str(tmp_path), "server": ces_stub})
    assert again["ok"] and again["device_build"] == "B_2"
    assert tools.call("cex_status", {"workspace": str(tmp_path)})["logged_in"] is True


# ── 8. 浏览器授权页的证书警告 ─────────────────────────────────────────

def test_login_start_explains_the_browser_certificate_warning(tmp_path, monkeypatch, pki,
                                                              site_factory):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    builtin = pki["builtin"]
    site = site_factory(builtin.server_context())
    site.routes["/ca.pem"] = (200, builtin.ca_pem.encode("ascii"))
    site.routes["/device_authorize"] = (200, json.dumps({
        "device_code": "dc", "user_code": "ABCD-EFGH", "expires_in": 600, "interval": 5,
        "verification_uri": site.base + "/activate"}).encode())
    ws_dir = (tmp_path / "my project").resolve()  # 路径带空格：命令里要加引号
    assert tools.call("cex_init", {"workspace": str(ws_dir),
                                   "server": f"{site.base}#ca={builtin.fp}"})["ok"]
    started = tools.call("cex_login_start", {"workspace": str(ws_dir)})
    assert started["ok"] and started["user_code"] == "ABCD-EFGH", started
    note = started["browser_certificate"]
    fingerprint = _browser_form(builtin.leaf_der)
    assert re.fullmatch(r"(?:[0-9A-F]{2} ){31}[0-9A-F]{2}", fingerprint)
    assert fingerprint in note
    assert _browser_form(builtin.ca_der) not in note, "the server certificate, not the CA"
    assert "证书不受信任" in note and "自带的根证书" in note and "已经按管理员给的连接串核对过" in note
    ca_path = str(ws_dir / ".compile-excel" / "ca.pem")
    assert ("security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db "
            f"'{ca_path}'") in note
    assert f'certutil -addstore -user Root "{ca_path}"' in note
    assert "`.compile-excel/ca.pem`" in note
    assert "browser_certificate" in started["next"]

    # 取不到服务器证书（这里换成别的 CA 签发的）：不给指纹，叫用户先别继续
    site.context = pki["other"].server_context()
    note = connect.browser_certificate_note(wsmod.Workspace(ws_dir))
    assert fingerprint not in note and "请先不要在浏览器里继续" in note and "证书不受信任" in note

    # 系统证书（不带 #ca=）或明文：浏览器不会报警，没有这段
    plain = tmp_path / "plain"
    wsmod.init(plain, server="http://127.0.0.1:9")
    assert connect.browser_certificate_note(wsmod.Workspace(plain.resolve())) == ""


# ── 真网关：证书用 ces tls gateway 签发，网关凭 ca_file 信任服务端 ────────────────
def test_real_gateway_with_a_certificate_from_ces_tls_gateway(tls_server, tmp_path, monkeypatch):
    """三方都只认服务端的内置 CA：编译助手 →（工作区 ca.pem）→ 网关 →（[server] ca_file）→ 服务端。"""
    if not (SERVER_ROOT / "gateway" / "vendor" / "cex_core" / "__init__.py").is_file():
        pytest.skip("服务端检出的 gateway/vendor/cex_core 没生成过（tools/sync_gateway_vendor.py）")
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    srv = tls_server
    data, cert = srv["data"], srv["cert"]
    cfg_root = tmp_path / "cfg"
    cfg_root.mkdir()
    (cfg_root / "install.json").write_text(json.dumps({
        "data": str(data), "port": int(srv["base"].rsplit(":", 1)[1]), "host": "127.0.0.1",
        "tls_cert": str(cert), "tls_key": str(cert.with_name("server.key"))}), encoding="utf-8")
    env = {**os.environ, "CES_CONFIG_ROOT": str(cfg_root)}

    def ces(*argv: str) -> subprocess.CompletedProcess:
        proc = subprocess.run([sys.executable, str(SERVER_ROOT / "ces_main.py"), *argv],
                              capture_output=True, text=True, timeout=120, env=env,
                              cwd=SERVER_ROOT, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return proc

    tls_dir, secret = tmp_path / "gw-tls", tmp_path / "gateway-client.secret"
    ces("tls", "gateway", "127.0.0.1", "--out", str(tls_dir))
    ces("clients", "add", "gateway", "--scopes", "introspect bundles:read", "--out", str(secret))
    apv = tmp_path / "apv_src"
    for sub in ("lib", "conf", "smoke_test/sdns"):
        (apv / sub).mkdir(parents=True)
    config = tmp_path / "gateway.toml"
    config.write_text(
        "[server]\n"
        f'url = "{srv["base"]}"\nclient_id = "gateway"\nclient_secret_file = "{secret}"\n'
        f'ca_file = "{tls_dir / "ca.pem"}"\nbuild = "{SAMPLE_BUILD}"\n'
        "[listen]\n"
        f'host = "127.0.0.1"\nport = 0\ntls_cert = "{tls_dir / "gateway.pem"}"\n'
        f'tls_key = "{tls_dir / "gateway.key"}"\n'
        "[framework]\n"
        f'apv_src = "{apv}"\npy38 = "{sys.executable}"\nconf_name = "bed"\n'
        f'staging_parent = "{apv / "smoke_test" / "sdns"}"\ndefault_module = "sdns"\n'
        "[state]\n"
        f'dir = "{tmp_path / "gw-state"}"\n', encoding="utf-8")
    sys.path.insert(0, str(SERVER_ROOT))
    try:
        from gateway.config import load
        from gateway.introspect import IntrospectError, ServerClient
        from gateway.service import build_server
        from gateway.tools import Gateway
    finally:
        sys.path.remove(str(SERVER_ROOT))

    # 不配 ca_file：网关连服务端时证书不受信任，报的是配置怎么改
    with pytest.raises(IntrospectError, match="ca_file"):
        ServerClient(srv["base"], "gateway", secret).introspect("not-a-token")

    httpd = build_server(Gateway(load(config)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    gateway_url = f"https://127.0.0.1:{httpd.server_address[1]}/mcp"
    try:
        ces("config", "set", "gateway.url", gateway_url)
        ws_dir = tmp_path / "project"
        ws_dir.mkdir()
        init = tools.call("cex_init", {"workspace": str(ws_dir),
                                       "server": f"{srv['base']}#ca={srv['fp']}"})
        assert init["ok"], init
        _login(ws_dir, srv)
        fetched = tools.call("cex_client_config", {"workspace": str(ws_dir)})
        assert fetched["ok"], fetched
        acquired = tools.call("cex_bed_lease", {"workspace": str(ws_dir), "action": "acquire"})
        assert acquired["ok"] and acquired.get("lease_id"), acquired
        status = tools.call("cex_bed_lease", {"workspace": str(ws_dir), "action": "status"})
        assert status["ok"] and status["leased"] is True, status
        released = tools.call("cex_bed_lease", {"workspace": str(ws_dir), "action": "release"})
        assert released["ok"], released
    finally:
        ces("config", "unset", "gateway.url")
        httpd.shutdown()
        httpd.server_close()
