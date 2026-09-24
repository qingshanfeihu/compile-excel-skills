"""登录与带令牌的请求：OAuth 设备授权流，令牌只存在工作区 token.json（0600）。

设备流拆成两步，方便在工具调用里用：`start_login` 拿到授权网址和设备码交给用户，
`wait_login` 轮询到用户在浏览器里授权完成（每次调用有时限，没完成就返回 pending）。
access 过期时用 refresh 换新；服务端每次都轮换 refresh，新的立刻落盘。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .errors import ClientError, NotLoggedIn, ServerUnreachable
from .workspace import Workspace, read_private_json, write_private_json

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
CLIENT_ID = "compile-excel-skill"
DEFAULT_SCOPES = "artifacts:read docs:query bundles:read config:read jumphost:run"
USER_AGENT = "cex-client/1"


def http(method: str, url: str, *, data: bytes | None = None,
         headers: dict[str, str] | None = None, timeout: float = 60.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ServerUnreachable(f"server unreachable ({type(exc).__name__})") from None


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
    body, headers = _form({"client_id": CLIENT_ID, "scope": scope})
    status, raw = http("POST", ws.server + "/device_authorize", data=body, headers=headers)
    payload = _json(raw)
    if status != 200 or "device_code" not in payload:
        raise ClientError(f"device authorization failed (HTTP {status}, "
                          f"{payload.get('error', 'no detail')})")
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


def wait_login(ws: Workspace, timeout_s: float = 60.0) -> dict[str, Any]:
    pending = read_private_json(ws.pending_login_path)
    if not pending:
        raise ClientError("no login in progress; call cex_login_start first")
    if pending.get("server") != ws.server:
        ws.pending_login_path.unlink(missing_ok=True)
        raise ClientError("the workspace server changed during login; start again")
    deadline = min(time.time() + max(timeout_s, 1), float(pending["expires_at"]))
    interval = max(int(pending.get("interval") or 5), 1)
    while True:
        body, headers = _form({"grant_type": DEVICE_GRANT,
                               "device_code": pending["device_code"],
                               "client_id": CLIENT_ID})
        status, raw = http("POST", ws.server + "/token", data=body, headers=headers)
        payload = _json(raw)
        if status == 200 and "access_token" in payload:
            _store_tokens(ws, payload, None)
            ws.pending_login_path.unlink(missing_ok=True)
            return {"ok": True, "scope": payload.get("scope", "")}
        error = payload.get("error", f"HTTP {status}")
        if error == "slow_down":
            interval += 5
        elif error != "authorization_pending":
            ws.pending_login_path.unlink(missing_ok=True)
            raise ClientError(f"login failed: {error}")
        if time.time() + interval > deadline:
            if time.time() >= float(pending["expires_at"]) - 1:
                ws.pending_login_path.unlink(missing_ok=True)
                raise ClientError("the device code expired; call cex_login_start again")
            return {"ok": False, "pending": True,
                    "next": "The user has not approved yet; call cex_login_wait again."}
        time.sleep(interval)


def load_token(ws: Workspace) -> dict[str, Any]:
    token = read_private_json(ws.token_path)
    if not token or not token.get("access_token"):
        raise NotLoggedIn("not logged in; call cex_login_start")
    if token.get("server") != ws.server:
        raise NotLoggedIn("the token belongs to another server; log in again")
    return token


def _refresh(ws: Workspace, token: dict[str, Any]) -> dict[str, Any]:
    if not token.get("refresh_token"):
        raise NotLoggedIn("session expired; log in again")
    body, headers = _form({"grant_type": "refresh_token",
                           "refresh_token": token["refresh_token"], "client_id": CLIENT_ID})
    status, raw = http("POST", ws.server + "/token", data=body, headers=headers)
    payload = _json(raw)
    if status != 200 or "access_token" not in payload:
        ws.token_path.unlink(missing_ok=True)
        raise NotLoggedIn("session expired or was revoked; log in again")
    _store_tokens(ws, payload, token)
    return load_token(ws)


def request(ws: Workspace, method: str, path: str, *, data: bytes | None = None,
            headers: dict[str, str] | None = None, timeout: float = 120.0,
            stream_to: Any = None) -> tuple[int, bytes]:
    """带令牌的请求；access 过期或 401 时换新一次再试。"""
    token = load_token(ws)
    if int(token.get("expires_at") or 0) < time.time() + 30:
        token = _refresh(ws, token)
    for attempt in (0, 1):
        auth = {"Authorization": f"Bearer {token['access_token']}", **(headers or {})}
        status, raw = http(method, ws.server + path, data=data, headers=auth, timeout=timeout)
        if status != 401:
            return status, raw
        if attempt == 0:
            token = _refresh(ws, token)
    raise NotLoggedIn("the server rejected the session; log in again")


def request_json(ws: Workspace, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    status, raw = request(ws, method, path, **kwargs)
    payload = _json(raw)
    if status >= 400:
        detail = payload.get("detail") or payload.get("error") or f"HTTP {status}"
        raise ClientError(f"{method} {path} failed: {detail}")
    return payload


def logout(ws: Workspace) -> dict[str, Any]:
    token = read_private_json(ws.token_path) or {}
    revoked = False
    if token.get("refresh_token") and token.get("server") == ws.server:
        body, headers = _form({"token": token["refresh_token"]})
        try:
            status, _ = http("POST", ws.server + "/revoke", data=body, headers=headers)
            revoked = status == 200
        except ServerUnreachable:
            revoked = False
    ws.token_path.unlink(missing_ok=True)
    ws.pending_login_path.unlink(missing_ok=True)
    return {"ok": True, "revoked_on_server": revoked}
