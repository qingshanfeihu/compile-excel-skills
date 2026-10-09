"""连服务端：解析管理员给的连接串、cex_init 时探活并核对内置 CA、登录后自动选构建号。

连接串形如 https://<主机>:<端口>#ca=<CA 证书 DER 的 SHA-256>。带指纹时：先不校验证书取 /ca.pem，
算指纹核对（对不上就拒绝：可能被调包，或连接串抄错），核对上了再用"系统证书库 + 这份 CA"校验证书
访问 /healthz，确认应答的是 compile-excel-server，都过了才写工作区（ca.pem 与配置里的 ca_sha256）。
此后发往服务端和网关的 https 请求都用这份上下文（Workspace.ssl_context）。
没有 #ca= 的是普通地址：只用系统证书库（或 SSL_CERT_FILE）。
探活与取 CA 都封顶：应答最多读 64 KiB、总时限 15 秒（auth.http_capped），冒充者撑不爆内存、挂不住调用。
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import socket
import ssl
import urllib.parse
from pathlib import Path
from typing import Any

from . import auth
from . import workspace as wsmod
from .errors import ClientError
from .workspace import CONNECTION_STRING_FORM, Workspace

SERVICE_NAME = "compile-excel-server"
PROBE_TIMEOUT = 10.0
FETCH_MAX_BYTES = 64 * 1024  # 探活、取 CA 的应答最多读这么多，超了就拒绝
FETCH_DEADLINE = 15.0        # 探活、取 CA 每次请求的总时限（秒），到点没读完就拒绝
CHANNELS = ("stable", "candidate")
_HEX = frozenset("0123456789abcdef")


def normalize_fingerprint(text: str) -> str:
    """指纹统一成 64 位小写十六进制：接受 sha256: 前缀、大写、冒号或空格分隔。"""
    value = urllib.parse.unquote(text or "").strip().lower()
    for prefix in ("sha256:", "sha-256:"):
        value = value.removeprefix(prefix)
    value = re.sub(r"[\s:]", "", value)
    if len(value) != 64 or set(value) - _HEX:
        raise ClientError(f"连接串里的证书指纹不对（{text!r}）：应是 64 位十六进制的 SHA-256。"
                          "请从管理员给的连接串原样复制，不要删改")
    return value


def parse_connection_string(text: str) -> tuple[str, str]:
    """(服务端地址, CA 指纹)；没有 #ca= 时指纹是空串。"""
    base, sep, fragment = (text or "").strip().partition("#")
    url = base.strip().rstrip("/")
    if not sep:
        return url, ""
    params = {}
    for item in fragment.split("&"):
        key, eq, value = item.partition("=")
        if eq:
            params[key.strip().lower()] = value
    if "ca" not in params:
        raise ClientError(f"连接串 # 后面应是 ca=<证书指纹>（{text!r}）：请从管理员给的连接串原样复制，"
                          f"形如 {CONNECTION_STRING_FORM}")
    fingerprint = normalize_fingerprint(params["ca"])
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ClientError(f"带证书指纹（#ca=）的连接串要以 https:// 开头（{url!r}）：请从管理员给的"
                          "连接串原样复制")
    return url, fingerprint


def _unverified_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _healthz_service(status: int, raw: bytes) -> str | None:
    """探活应答里的 service；不是 200 或不是 JSON 对象返回 None。"""
    if status != 200:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return None
    return str(payload.get("service") or "") if isinstance(payload, dict) else None


def _get(url: str, context: ssl.SSLContext | None, **kwargs: Any) -> tuple[int, bytes]:
    return auth.http_capped("GET", url, max_bytes=FETCH_MAX_BYTES, deadline_s=FETCH_DEADLINE,
                            context=context, **kwargs)


def _fetch_ca(url: str, expected: str, *, inherited: bool = False) -> bytes:
    """不校验证书取 /ca.pem，严格解析（恰好一张证书）后按指纹核对；对上了返回 CA 证书的 DER。
    inherited：指纹是从旧配置沿用来的（用户这次没给 #ca=）；这时 /ca.pem 回 404 说明服务端已不用
    内置 CA，返回 b""，由调用方改用系统证书库校验。"""
    unverified = _unverified_context()
    status, raw = _get(url + "/ca.pem", unverified)
    if 300 <= status < 400:
        raise ClientError(auth.redirect_refused(url, status))
    if status == 404 and inherited:
        return b""
    der = None
    if status == 200:
        try:
            der = wsmod.pem_to_der(raw.decode("ascii"))
        except (UnicodeError, ValueError):
            der = None
    if der is None:
        # 取不到 CA：看一眼这是不是 compile-excel-server，说清是地址错了还是服务端没用内置 CA
        probe_status, probe_raw = _get(url + "/healthz", unverified)
        if _healthz_service(probe_status, probe_raw) != SERVICE_NAME:
            raise ClientError(auth.not_our_server(
                url, f"/ca.pem 回 HTTP {status}" if status != 200 else "/ca.pem 回的不是证书"))
        if status == 200:
            raise ClientError("服务端发来的根证书格式不对（应当恰好是一张证书）：可能连到了冒充的服务端，"
                              "也可能服务端配置有误。已拒绝连接，什么都没保存；请把这段报错发给管理员")
        raise ClientError(f"服务端没有启用内置 CA（/ca.pem 回 HTTP {status}），连接串里的指纹用不上："
                          "请向管理员要新的连接串；服务端用的是正式机构签发的证书时，"
                          "去掉 #ca= 及后面的部分，只用地址")
    actual = hashlib.sha256(der).hexdigest()
    if actual != expected:
        raise ClientError(f"服务端发来的 CA 证书与连接串里的指纹不一致（连接串 {expected[:16]}…，"
                          f"实际 {actual[:16]}…）：可能连到了冒充的服务端（证书被调包），也可能连接串"
                          "抄错了。已拒绝连接，什么都没保存；请向管理员核对连接串")
    return der


def _trusting(der: bytes) -> ssl.SSLContext:
    """系统证书库 + 这一张 CA（只信任解出的这张 DER）。"""
    context = ssl.create_default_context()
    try:
        context.load_verify_locations(cadata=der)
    except ssl.SSLError:
        raise ClientError("服务端发来的根证书读不出来：已拒绝连接，什么都没保存；"
                          "请把这段报错发给管理员") from None
    return context


def probe(url: str, ca_sha256: str = "", *, insecure_lan: bool = False,
          inherited: bool = False) -> str:
    """探活：确认地址上是 compile-excel-server；带指纹时先核对内置 CA，再用它校验证书。
    返回核对过的 CA 证书 PEM（由 DER 重新生成）；不带指纹、或沿用来的指纹已用不上
    （inherited 且 /ca.pem 回 404，改用系统证书库校验通过）时是空串。
    任何一步不对都抛 ClientError（中文，带处理办法）。"""
    url = wsmod.check_server_url(url, allow_insecure_http=insecure_lan)
    ca_pem = ""
    context = None
    if ca_sha256:
        der = _fetch_ca(url, ca_sha256, inherited=inherited)
        if der:
            context = _trusting(der)
            ca_pem = ssl.DER_cert_to_PEM_cert(der)
    status, raw = _get(url + "/healthz", context, headers={"Accept": "application/json"})
    if 300 <= status < 400:
        raise ClientError(auth.redirect_refused(url, status))
    service = _healthz_service(status, raw)
    if service != SERVICE_NAME:
        detail = (f"/healthz 回 HTTP {status}" if status != 200
                  else "/healthz 回的不是 JSON" if service is None
                  else f"/healthz 自称 {service or '无名服务'}")
        raise ClientError(auth.not_our_server(url, detail))
    return ca_pem


def _previous_config(root: Path) -> dict[str, Any]:
    ws = Workspace(root)
    if not ws.config_path.is_file():
        return {}
    try:
        return ws.config()
    except ClientError:
        return {}


def setup(root: Path, *, server: str = "", device_build: str = "", channel: str = "",
          insecure_lan: bool | None = None) -> Workspace:
    """cex_init：探活、核对 CA 都通过了才写工作区。

    - 给了 server（连接串或地址）：探活后写配置。同一服务端只给地址时沿用之前核对过的 CA；
      沿用的 CA 服务端已经不发了（/ca.pem 回 404，比如改用了正式机构签发的证书），就改用系统证书库
      校验，通过了清掉指纹与 ca.pem。换服务端（或换了 CA）时 workspace.init 丢掉旧令牌、组织常量、
      租约，旧 ca.pem 换掉或删掉。"是不是同一服务端"按规范化后的地址比较（大小写、:443 之类不算换）。
    - 没给 server 而工作区已在：只改构建号/通道（不联网，令牌保留）。
    构建号、通道没给时沿用原值（换了服务端的话构建号清空，登录后重新选）。"""
    root = Path(root).expanduser().resolve()
    if channel and channel not in CHANNELS:
        raise ClientError(f"channel 只能是 stable 或 candidate：{channel!r}")
    previous = _previous_config(root)
    if device_build:
        wsmod.safe_component(device_build, "device_build")
    if not (server or "").strip():
        if not previous.get("server"):
            raise ClientError(f"缺少服务端地址：请向管理员要连接串（形如 {CONNECTION_STRING_FORM}），"
                              "用 cex_init 的 server 传入")
        ws = Workspace(root)
        config = dict(previous)
        if device_build:
            config["device_build"] = device_build
        if channel:
            config["channel"] = channel
        if insecure_lan is not None:
            config["allow_insecure_http"] = bool(insecure_lan)
        config["server"] = wsmod.normalize_server_url(wsmod.check_server_url(
            str(config["server"]), allow_insecure_http=bool(config.get("allow_insecure_http"))))
        ws.save_config(config)
        return ws
    url, fingerprint = parse_connection_string(server)
    insecure = bool(insecure_lan)
    url = wsmod.normalize_server_url(wsmod.check_server_url(url, allow_insecure_http=insecure))
    same_server = wsmod.same_server(previous.get("server"), url)
    inherited = bool(not fingerprint and same_server and previous.get("ca_sha256"))
    if inherited:
        fingerprint = str(previous["ca_sha256"])  # 同一服务端只给了地址：沿用核对过的 CA
    ca_pem = probe(url, fingerprint, insecure_lan=insecure, inherited=inherited)
    if not ca_pem:
        fingerprint = ""  # 沿用的 CA 已用不上、改由系统证书库校验：清掉（视同换了 CA，旧令牌作废）
    build = device_build or (str(previous.get("device_build") or "") if same_server else "")
    return wsmod.init(root, server=url, device_build=build,
                      channel=channel or str(previous.get("channel") or "stable"),
                      insecure_lan=insecure, ca_sha256=fingerprint, ca_pem=ca_pem)


def published_builds(ws: Workspace, channel: str) -> list[str]:
    """服务端在这个通道上有包的构建（构建名要拼进本地路径，不安全的名字不列）。"""
    payload = auth.request_json(ws, "GET", "/v1/builds")
    names = set()
    for row in payload.get("builds") or []:
        if not isinstance(row, dict):
            continue
        pointer = (row.get("channels") or {}).get(channel) or {}
        name = str(row.get("build") or "")
        if pointer.get("bundle_id") and name:
            try:
                names.add(wsmod.safe_component(name, "build"))
            except ClientError:
                continue
    return sorted(names)


def choose_build(ws: Workspace, channel: str = "") -> dict[str, Any]:
    """工作区还没有构建号时调：通道上只有一个构建就写进配置；没有、或有多个时只回说明
    （多个时带列表，让用户选了再用 cex_init 的 device_build 指定）。channel 没给时用工作区的通道
    （cex_sync 带了 channel 就按它选，与随后同步的通道一致）。"""
    channel = channel or ws.channel
    if channel not in CHANNELS:
        raise ClientError(f"channel 只能是 stable 或 candidate：{channel!r}")
    builds = published_builds(ws, channel)
    if len(builds) == 1:
        config = ws.config()
        config["device_build"] = builds[0]
        ws.save_config(config)
        return {"device_build": builds[0],
                "device_build_note": f"服务端在 {channel} 通道上只有一个构建 {builds[0]}，已自动选用"}
    if not builds:
        return {"device_build": None,
                "device_build_note": f"服务端还没有在 {channel} 通道上发布任何构建，暂时同步不了编译数据："
                                     "请联系管理员发布构建"}
    return {"device_build": None, "builds": builds,
            "device_build_note": f"服务端在 {channel} 通道上有多个构建（{'、'.join(builds)}）：请让用户选"
                                 "被测设备对应的那个，再用 cex_init 的 device_build 指定"
                                 "（不用再给 server，登录保留）"}


def tls_summary(ws: Workspace) -> str:
    """cex_status 里的证书情况。"""
    config = ws.config()
    parts = urllib.parse.urlsplit(ws.server)
    if parts.scheme == "http":
        return ("明文（本机回环）" if wsmod.is_loopback_host(parts.hostname)
                else "明文（insecure_lan）")
    if config.get("ca_sha256"):
        try:
            ws.ssl_context()
        except ClientError as exc:
            return f"内置 CA（{exc}）"
        return "内置 CA（指纹已核对）"
    return "系统证书"


def server_certificate_sha256(ws: Workspace) -> str:
    """服务器证书（叶子证书）DER 的 SHA-256，按浏览器证书详情里的写法：大写、两位一组、空格分隔。
    用工作区的校验上下文连一次，拿到的就是核对过的那张。"""
    parts = urllib.parse.urlsplit(ws.server)
    host, port = parts.hostname or "", parts.port or 443
    context = ws.ssl_context() or ssl.create_default_context()
    with socket.create_connection((host, port), timeout=PROBE_TIMEOUT) as raw:
        raw.settimeout(PROBE_TIMEOUT)
        with context.wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        raise ssl.SSLError("no peer certificate")
    digest = hashlib.sha256(der).hexdigest().upper()
    return " ".join(digest[i:i + 2] for i in range(0, len(digest), 2))


def browser_certificate_note(ws: Workspace) -> str:
    """cex_login_start 的 browser_certificate：工作区信任服务端自带的根证书时，浏览器打开授权页会报
    证书不受信任。说明原因、给出服务器证书指纹让用户在浏览器里核对，并说明怎样让系统信任这份根证书。
    工作区没有记 CA 指纹（系统证书或明文）时返回空串。"""
    if not str(ws.config().get("ca_sha256") or ""):
        return ""
    reason = ""
    try:
        check = ("继续之前，请在浏览器的提示页上打开证书详情，核对服务器证书的 SHA-256 指纹是否为：\n"
                 f"{server_certificate_sha256(ws)}\n"
                 "一致再选择继续访问；不一致就不要继续，把这段说明发给管理员。")
    except ClientError as exc:
        reason = str(exc)
    except OSError as exc:  # 连不上、证书错误（ssl.SSLError 也是 OSError）
        reason = auth._unreachable(exc, ws.server)
    if reason:
        check = ("但这次没能取到服务器证书的指纹，没法核对，请先不要在浏览器里继续：稍后重新调用 "
                 f"`cex_login_start` 再核对；一直取不到就把这段说明发给管理员。原因：{reason}")
    path = str(ws.ca_path)
    windows_path = '"' + path.replace('"', "") + '"'
    return (
        "浏览器打开授权页时会提示证书不受信任（例如“您的连接不是私密连接”）。这是因为服务端用的是"
        "它自带的根证书，浏览器不认识；编译助手已经按管理员给的连接串核对过这份根证书。"
        + check + "\n"
        "想以后不再提示，可以把工作区里的根证书 `.compile-excel/ca.pem` 加入系统信任，然后重启浏览器：\n"
        "- macOS：`security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db "
        f"{shlex.quote(path)}`\n"
        f"- Windows：`certutil -addstore -user Root {windows_path}`")
