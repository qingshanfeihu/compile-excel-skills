"""登录与带令牌的请求：OAuth 设备授权流，令牌只存在工作区 token.json（0600）。

设备流拆成两步，方便在工具调用里用：`start_login` 拿到授权网址和设备码交给用户，
`wait_login` 轮询到用户在浏览器里授权完成（每次调用有时限，没完成就返回 pending）。
access 过期时用 refresh 换新；服务端每次都轮换 refresh（旧的再用一次整族吊销），所以换新在
工作区锁里做：同时跑的几个工具调用只有一个真去换，其余的在锁里重读 token.json 用换好的。
只有服务端明说这张 refresh 失效（invalid_grant）才删令牌；网络故障、5xx 保留令牌，下次再试。
带令牌的请求一律不跟随重定向：令牌只发给工作区配置的那个服务端。
https 用工作区的校验上下文（Workspace.ssl_context：连接串带了 CA 指纹时是系统证书库 + 内置 CA）。
连接、登录这条路径上的报错用中文并带处理办法：这些是新手第一次用时直接看到的。
"""

from __future__ import annotations

import errno
import io
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.client import BadStatusLine, HTTPConnection, HTTPException, RemoteDisconnected
from typing import Any

from .errors import ClientError, NotLoggedIn, ServerUnreachable
from .workspace import (
    CONNECTION_STRING_FORM,
    DEFAULT_SERVER_PORT,
    Workspace,
    read_private_json,
    same_server,
    state_lock,
    write_private_json,
)

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
CLIENT_ID = "compile-excel-skill"
# 服务端按"申请 ∩ 账号拥有"授予：没有 jumphost:admin 的账号申请它也只拿到自己有的那几项
BASE_SCOPES = "artifacts:read docs:query bundles:read config:read jumphost:run"
DEFAULT_SCOPES = BASE_SCOPES + " jumphost:admin"
USER_AGENT = "cex-client/1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """3xx 原样当应答交回（HTTPError），不带着 Authorization 跟到别的源、也不从 https 降到 http。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)
_TLS_NOT_HTTPS = ("wrong_version_number", "wrong version number", "record layer failure",
                  "packet length too long", "unknown protocol", "http request")


def http(method: str, url: str, *, data: bytes | None = None,
         headers: dict[str, str] | None = None, timeout: float = 60.0,
         context: ssl.SSLContext | None = None) -> tuple[int, bytes]:
    """一次请求，不跟随重定向。context 是 https 的校验上下文（发往服务端、网关时传
    ws.ssl_context()）；None 用系统证书库。"""
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    opener = _OPENER if context is None else urllib.request.build_opener(
        _NoRedirect, urllib.request.HTTPSHandler(context=context))
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError, TimeoutError, HTTPException) as exc:
        raise ServerUnreachable(_unreachable(exc, url)) from None


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("deadline exceeded")
    return left


class _DeadlineReader(io.RawIOBase):
    """每次从套接字读之前把超时改成离总截止还剩多少：慢速发送（一次一个字节）也挂不过截止时间。"""

    def __init__(self, sock: socket.socket, deadline: float):
        super().__init__()
        self._sock, self._deadline = sock, deadline
        self._raw = sock.makefile("rb", buffering=0)  # 走套接字的引用计数：连接先关了也能读完

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int | None:
        self._sock.settimeout(_remaining(self._deadline))
        return self._raw.readinto(buffer)

    def close(self) -> None:
        if not self.closed:
            self._raw.close()
        super().close()


class _DeadlineSocket:
    """给 http.client 用的已连好的套接字：收发都受同一个总截止时间约束（它只用 sendall/makefile/close）。"""

    def __init__(self, sock: socket.socket, deadline: float):
        self._sock, self._deadline = sock, deadline

    def sendall(self, data: bytes) -> None:
        self._sock.settimeout(_remaining(self._deadline))
        self._sock.sendall(data)

    def makefile(self, mode: str = "rb", *args: Any, **kwargs: Any) -> io.BufferedReader:
        return io.BufferedReader(_DeadlineReader(self._sock, self._deadline))

    def close(self) -> None:
        self._sock.close()


def http_capped(method: str, url: str, *, max_bytes: int, deadline_s: float,
                headers: dict[str, str] | None = None,
                context: ssl.SSLContext | None = None) -> tuple[int, bytes]:
    """小应答的一次请求（探活、取 CA）：应答体最多读 max_bytes（超了就拒绝），连接、握手、发送、
    读应答合起来不超过 deadline_s 秒（到点没读完就拒绝）。冒充者回几百 MB、或一个字节一个字节
    慢慢发，都撑不爆内存、挂不住调用。不跟随重定向；context 同 http()。"""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    origin = f"{parts.scheme}://{parts.netloc}"
    deadline = time.monotonic() + deadline_s
    conn = HTTPConnection(host, port)  # 只借它拼请求、解析应答；套接字自己连
    sock: socket.socket | None = None
    response = None
    connected = False
    try:
        sock = socket.create_connection((host, port), timeout=_remaining(deadline))
        connected = True
        if parts.scheme == "https":
            sock.settimeout(_remaining(deadline))  # 握手整个过程受这一个超时约束
            sock = (context or ssl.create_default_context()).wrap_socket(sock,
                                                                         server_hostname=host)
        conn.sock = _DeadlineSocket(sock, deadline)
        conn.request(method, target, headers={"User-Agent": USER_AGENT, **(headers or {})})
        response = conn.getresponse()
        too_big = ClientError(f"{origin}{parts.path} 回的内容超过 {max_bytes} 字节，不像是 "
                              "compile-excel-server 的应答，已拒绝。请核对地址；最好直接用管理员给的"
                              f"连接串（形如 {CONNECTION_STRING_FORM}）")
        if response.length is not None and response.length > max_bytes:
            raise too_big
        body = bytearray()
        while len(body) <= max_bytes:
            chunk = response.read(min(65536, max_bytes + 1 - len(body)))
            if not chunk:
                break
            body += chunk
        if len(body) > max_bytes:
            raise too_big
        return response.status, bytes(body)
    except ClientError:
        raise
    except (OSError, HTTPException) as exc:  # 超时、TLS 错误都是 OSError
        # 连上以后的超时都是撞上了总截止（每步的超时就是剩下的时间）；连不上的照常说明原因
        if connected and (isinstance(exc, TimeoutError) or time.monotonic() >= deadline):
            raise ClientError(f"{origin}{parts.path} 在 {deadline_s:g} 秒内没有回完应答，已放弃："
                              "对方可能不是 compile-excel-server，或网络太慢。请核对地址、确认网络"
                              f"通畅后重试；最好直接用管理员给的连接串（形如 {CONNECTION_STRING_FORM}）"
                              ) from None
        raise ServerUnreachable(_unreachable(exc, url)) from None
    finally:
        if response is not None:
            response.close()
        conn.close()
        if sock is not None:
            sock.close()


def port_hint(url: str) -> str:
    """地址里没写端口时的提示（新手最常见的错：漏了端口，打到同机别的网站上）；写了端口返回空串。"""
    parts = urllib.parse.urlsplit(url)
    try:
        if parts.port is not None or not parts.hostname:
            return ""
    except ValueError:
        return ""
    return (f"地址里没写端口，服务端默认端口是 {DEFAULT_SERVER_PORT}，例如 "
            f"https://{parts.netloc}:{DEFAULT_SERVER_PORT}；最好直接用管理员给的连接串")


def not_our_server(url: str, detail: str) -> str:
    """地址上应答的不是 compile-excel-server。"""
    return (f"这个地址上的服务不是 compile-excel-server（{url}：{detail}）。"
            + (port_hint(url) or "请核对地址和端口；最好直接用管理员给的连接串"
               f"（形如 {CONNECTION_STRING_FORM}）"))


def redirect_refused(url: str, status: int) -> str:
    return (f"{url} 回了重定向（HTTP {status}），客户端不跟随重定向（免得把凭据带到别处）："
            f"请直接用管理员给的连接串里的地址（形如 {CONNECTION_STRING_FORM}）")


def _unreachable(exc: BaseException, url: str = "") -> str:
    """连不上的原因说具体、给出处理办法：只报异常类名的话，会话只会以为服务端挂了。"""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    parts = urllib.parse.urlsplit(url)
    where = f"连不上 {parts.scheme}://{parts.netloc}" if parts.netloc else "连不上服务端"
    hint = port_hint(url)
    if isinstance(reason, ssl.SSLCertVerificationError):
        detail = str(getattr(reason, "verify_message", "") or reason)
        # 62/64：X509_V_ERR_HOSTNAME_MISMATCH / IP_ADDRESS_MISMATCH
        if getattr(reason, "verify_code", None) in (62, 64) or "mismatch" in detail.lower():
            return (f"{where}：证书里没有这个地址（{parts.hostname}）。请管理员在 ces 菜单里重新签发"
                    "证书并加上这个地址；或者改用证书里已有的地址连接")
        return (f"{where}：证书不受信任（{detail}）。请用管理员给的连接串（形如 "
                f"{CONNECTION_STRING_FORM}）重新执行 cex_init，客户端核对指纹后就信任服务端自带的 CA；"
                "服务端用的是组织 CA 签发的证书时，让运行工具的进程带上 SSL_CERT_FILE，指向含该 CA 的证书包")
    if isinstance(reason, ssl.SSLError):
        detail = str(reason.reason or reason)
        if any(mark in str(reason).lower() for mark in _TLS_NOT_HTTPS):
            return (f"{where}：TLS 握手失败（{detail}），这个端口上的服务不像是 https。请核对地址和端口；"
                    f"{hint or '最好直接用管理员给的连接串（形如 ' + CONNECTION_STRING_FORM + '）'}")
        return f"{where}：TLS 握手失败（{detail}）。请核对地址；最好直接用管理员给的连接串"
    if isinstance(reason, ConnectionRefusedError):
        return (f"{where}：对方拒绝连接（这个端口上没有服务在监听）。请核对地址和端口、确认服务端已启动"
                + (f"；{hint}" if hint else ""))
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return (f"{where}：连接超时。请确认本机与服务端网络相通（同一局域网或已连 VPN）、地址无误、"
                "服务端的防火墙放行了这个端口" + (f"；{hint}" if hint else ""))
    if isinstance(reason, socket.gaierror):
        return f"{where}：找不到主机 {parts.hostname}（域名解析失败）。请核对地址拼写，或改用 IP 地址"
    if isinstance(reason, (RemoteDisconnected, BadStatusLine)):
        fix = ("服务端开了 https 时地址要写 https://" if parts.scheme == "http"
               else "请核对地址和端口")
        return (f"{where}：对方没有按 HTTP 应答就断开了。{fix}；最好直接用管理员给的连接串"
                f"（形如 {CONNECTION_STRING_FORM}）")
    if isinstance(reason, OSError) and reason.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH):
        return (f"{where}：网络不通（{reason.strerror or reason}）。请确认本机与服务端网络相通"
                "（同一局域网或已连 VPN）")
    detail = str(reason).strip()
    return (f"{where}（{type(reason).__name__}{': ' + detail[:160] if detail else ''}）。"
            "请确认地址无误、服务端在运行、网络相通")


def refuse_redirect(status: int, what: str) -> None:
    if 300 <= status < 400:
        raise ClientError(f"{what} answered with a redirect (HTTP {status}); the client does not "
                          "follow redirects with credentials. Check the configured address (the "
                          "https URL itself, not one that forwards)")


def _form(values: dict[str, str]) -> tuple[bytes, dict[str, str]]:
    return (urllib.parse.urlencode(values).encode("utf-8"),
            {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})


def _json(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def start_login(ws: Workspace, scope: str = DEFAULT_SCOPES) -> dict[str, Any]:
    url = ws.server + "/device_authorize"
    body, headers = _form({"client_id": CLIENT_ID, "scope": scope})
    status, raw = http("POST", url, data=body, headers=headers, context=ws.ssl_context())
    payload = _json(raw)
    if (status == 400 and payload.get("error") == "invalid_scope" and scope == DEFAULT_SCOPES):
        # 不认识 jumphost:admin 的旧服务端：退回基本权限（设备初始化用不了，其余照常）
        body, headers = _form({"client_id": CLIENT_ID, "scope": BASE_SCOPES})
        status, raw = http("POST", url, data=body, headers=headers, context=ws.ssl_context())
        payload = _json(raw)
    if 300 <= status < 400:
        raise ClientError(redirect_refused(ws.server, status))
    if status == 404:
        raise ClientError(not_our_server(ws.server, "登录入口 /device_authorize 回 HTTP 404")
                          + "；改好地址后重新执行 cex_init")
    if status != 200 or "device_code" not in payload:
        detail = payload.get("error") or payload.get("detail") or "没有说明"
        raise ClientError(f"发起登录失败（HTTP {status}，{detail}）。请稍后重试 cex_login_start；"
                          "一直失败就把这段报错发给管理员")
    write_private_json(ws.pending_login_path, {
        "device_code": payload["device_code"], "server": ws.server,
        "interval": int(payload.get("interval") or 5),
        "expires_at": time.time() + int(payload.get("expires_in") or 600),
    })
    return {
        "verification_uri": payload.get("verification_uri"),
        "verification_uri_complete": payload.get("verification_uri_complete"),
        "user_code": payload.get("user_code"),
        "expires_in": payload.get("expires_in"),
        "next": "Show the user the URL and code; they sign in with their username and access "
                "code in a browser. Then call cex_login_wait.",
    }


def _store_tokens(ws: Workspace, issued: dict[str, Any], previous: dict[str, Any] | None) -> None:
    write_private_json(ws.token_path, {
        "access_token": issued["access_token"],
        "refresh_token": issued.get("refresh_token") or (previous or {}).get("refresh_token", ""),
        "expires_at": int(time.time()) + int(issued.get("expires_in") or 900),
        "scope": issued.get("scope", ""),
        "server": ws.server,
    })


_LOGIN_ERRORS = {
    "access_denied": "登录被拒绝：用户在授权页点了拒绝，或用户名、访问码不对。核对后重新调用 cex_login_start",
    "expired_token": "授权码已过期（没在有效期内完成授权）：重新调用 cex_login_start",
    "invalid_grant": "这次登录已失效（授权码用过或被撤销）：重新调用 cex_login_start",
}


def wait_login(ws: Workspace, timeout_s: float = 60.0) -> dict[str, Any]:
    pending = read_private_json(ws.pending_login_path)
    if not pending:
        raise ClientError("没有进行中的登录：先调用 cex_login_start")
    if not same_server(pending.get("server"), ws.server):
        ws.pending_login_path.unlink(missing_ok=True)
        raise ClientError("登录过程中工作区换了服务端：重新调用 cex_login_start")
    deadline = min(time.time() + max(timeout_s, 1), float(pending["expires_at"]))
    interval = max(int(pending.get("interval") or 5), 1)
    while True:
        body, headers = _form({"grant_type": DEVICE_GRANT,
                               "device_code": pending["device_code"],
                               "client_id": CLIENT_ID})
        status, raw = http("POST", ws.server + "/token", data=body, headers=headers,
                           context=ws.ssl_context())
        payload = _json(raw)
        if status == 200 and "access_token" in payload:
            with state_lock(ws, "token"):
                _store_tokens(ws, payload, None)
            ws.pending_login_path.unlink(missing_ok=True)
            return {"ok": True, "scope": payload.get("scope", "")}
        error = str(payload.get("error") or "")
        if error == "slow_down":
            interval += 5
        elif error != "authorization_pending":
            ws.pending_login_path.unlink(missing_ok=True)
            if status == 404 and not error:
                raise ClientError(not_our_server(ws.server, "/token 回 HTTP 404"))
            raise ClientError(_LOGIN_ERRORS.get(error) or (
                f"登录失败（{error or f'HTTP {status}'}）：重新调用 cex_login_start；"
                "一直失败就把这段报错发给管理员"))
        if time.time() + interval > deadline:
            if time.time() >= float(pending["expires_at"]) - 1:
                ws.pending_login_path.unlink(missing_ok=True)
                raise ClientError(_LOGIN_ERRORS["expired_token"])
            return {"ok": False, "pending": True,
                    "next": "The user has not approved yet; call cex_login_wait again."}
        time.sleep(interval)


NOT_LOGGED_IN = "还没有登录：先调用 cex_login_start，让用户在浏览器里授权"
LOGIN_AGAIN = "登录已过期或被撤销：重新登录（cex_login_start）"


def load_token(ws: Workspace) -> dict[str, Any]:
    token = read_private_json(ws.token_path)
    if not token or not token.get("access_token"):
        raise NotLoggedIn(NOT_LOGGED_IN)
    if not same_server(token.get("server"), ws.server):
        raise NotLoggedIn("令牌属于另一个服务端（工作区换过服务端）：重新登录（cex_login_start）")
    return token


def _refresh(ws: Workspace, stale: dict[str, Any]) -> dict[str, Any]:
    """stale 是调用方手里那张（快过期、或刚被 401 拒掉的）令牌。锁内重读 token.json：别的调用
    已经换好就直接用；否则拿文件里现在那张 refresh 去换。"""
    with state_lock(ws, "token"):
        current = read_private_json(ws.token_path)
        if (not current or not current.get("access_token")
                or not same_server(current.get("server"), ws.server)):
            raise NotLoggedIn(NOT_LOGGED_IN)
        if (current.get("access_token") != stale.get("access_token")
                and int(current.get("expires_at") or 0) >= time.time() + 30):
            return current
        presented = str(current.get("refresh_token") or "")
        if not presented:
            raise NotLoggedIn(LOGIN_AGAIN)
        body, headers = _form({"grant_type": "refresh_token", "refresh_token": presented,
                               "client_id": CLIENT_ID})
        status, raw = http("POST", ws.server + "/token", data=body, headers=headers,
                           context=ws.ssl_context())
        payload = _json(raw)
        if status == 200 and "access_token" in payload:
            _store_tokens(ws, payload, current)
            return load_token(ws)
        if payload.get("error") == "invalid_grant":
            # 服务端判定这张 refresh 失效：锁内 token.json 还是它才删（不会删掉别人刚换好的）
            latest = read_private_json(ws.token_path) or {}
            if latest.get("refresh_token") == presented:
                ws.token_path.unlink(missing_ok=True)
            raise NotLoggedIn(LOGIN_AGAIN)
    raise ClientError(f"token refresh failed (HTTP {status}); the session is kept, try again")


def request(ws: Workspace, method: str, path: str, *, data: bytes | None = None,
            headers: dict[str, str] | None = None, timeout: float = 120.0) -> tuple[int, bytes]:
    """带令牌的请求；access 过期或 401 时换新一次再试。不跟随重定向。"""
    token = load_token(ws)
    if int(token.get("expires_at") or 0) < time.time() + 30:
        token = _refresh(ws, token)
    for attempt in (0, 1):
        auth = {"Authorization": f"Bearer {token['access_token']}", **(headers or {})}
        status, raw = http(method, ws.server + path, data=data, headers=auth, timeout=timeout,
                           context=ws.ssl_context())
        refuse_redirect(status, "the server")
        if status != 401:
            return status, raw
        if attempt == 0:
            token = _refresh(ws, token)
    raise NotLoggedIn("服务端不认这次登录（令牌被拒）：重新登录（cex_login_start）")


def request_json(ws: Workspace, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    status, raw = request(ws, method, path, **kwargs)
    payload = _json(raw)
    if status >= 400:
        detail = payload.get("detail") or payload.get("error") or f"HTTP {status}"
        raise ClientError(f"{method} {path} failed: {detail}")
    return payload


def logout(ws: Workspace) -> dict[str, Any]:
    with state_lock(ws, "token"):
        token = read_private_json(ws.token_path) or {}
        revoked = False
        if token.get("refresh_token") and same_server(token.get("server"), ws.server):
            body, headers = _form({"token": token["refresh_token"]})
            try:
                status, _ = http("POST", ws.server + "/revoke", data=body, headers=headers,
                                 context=ws.ssl_context())
                revoked = status == 200
            except ClientError:  # 连不上、工作区的 CA 坏了：照样删本地令牌
                revoked = False
        ws.token_path.unlink(missing_ok=True)
        ws.pending_login_path.unlink(missing_ok=True)
    return {"ok": True, "revoked_on_server": revoked}
