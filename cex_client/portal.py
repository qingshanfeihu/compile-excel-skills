"""公司门户（Array 零信任 WebVPN）扫码登录与会话。

协议事实来自对真实门户登录页的实测（不是标准 OAuth/OIDC）：
- 打开门户登录地址会经 302 链落到 WebVPN 登录页并下发网关会话 cookie；
- 二维码：GET /ueba/openapi/policy/v1/getQrCode?uuid=<uuid>；
- 用户手机扫码确认后，轮询 POST /prx/000/http/localhost/login，
  表单 method=twodimension&uuid=<uuid>&submit=true，会话建立；
- 内网资源以 /prx/000/http/localh/<原路径> 形式凭会话 cookie 访问；被 302 回登录页即会话失效。
轮询接口的应答格式没有实测过，所以登录是否完成不看它的应答，而是每轮去访问一个受保护资源，
没被重定向到登录页才算成功。

会话存在用户级 `~/.cache/compile-excel/portal-session.json`（0600），不进工作区，不存任何口令。
"""

from __future__ import annotations

import base64
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as uuidlib
from pathlib import Path
from typing import Any

from .errors import ClientError
from .workspace import read_private_json, write_private_json

QR_PATH = "/ueba/openapi/policy/v1/getQrCode"
LOGIN_PATH = "/prx/000/http/localhost/login"
USER_AGENT = "cex-client/1"
TIMEOUT = 20.0


class PortalSessionExpired(ClientError):
    pass


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    path = Path(base) / "compile-excel"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def session_path() -> Path:
    return cache_dir() / "portal-session.json"


def origin_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost"):
        raise ClientError("portal address must be https")
    return f"{parts.scheme}://{parts.netloc}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _jar_to_json(jar: http.cookiejar.CookieJar) -> list[dict[str, Any]]:
    return [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path,
             "secure": c.secure, "expires": c.expires} for c in jar]


def _jar_from_json(items: list[dict[str, Any]]) -> http.cookiejar.CookieJar:
    jar = http.cookiejar.CookieJar()
    for item in items or []:
        jar.set_cookie(http.cookiejar.Cookie(
            version=0, name=item["name"], value=item["value"], port=None, port_specified=False,
            domain=item["domain"], domain_specified=bool(item["domain"].startswith(".")),
            domain_initial_dot=item["domain"].startswith("."), path=item.get("path") or "/",
            path_specified=True, secure=bool(item.get("secure")), expires=item.get("expires"),
            discard=False, comment=None, comment_url=None, rest={}))
    return jar


class PortalSession:
    def __init__(self, origin: str, jar: http.cookiejar.CookieJar | None = None):
        self.origin = origin
        self.jar = jar or http.cookiejar.CookieJar()
        cookies = urllib.request.HTTPCookieProcessor(self.jar)
        self.follow = urllib.request.build_opener(cookies)
        self.nofollow = urllib.request.build_opener(cookies, _NoRedirect())

    @classmethod
    def load(cls, origin: str) -> "PortalSession":
        data = read_private_json(session_path()) or {}
        if data.get("origin") != origin:
            return cls(origin)
        return cls(origin, _jar_from_json(data.get("cookies") or []))

    def save(self) -> None:
        write_private_json(session_path(), {"origin": self.origin, "saved_at": int(time.time()),
                                            "cookies": _jar_to_json(self.jar)})

    def request(self, method: str, url: str, *, data: bytes | None = None,
                headers: dict[str, str] | None = None, follow: bool = False
                ) -> tuple[int, dict[str, str], bytes]:
        if not url.startswith(self.origin + "/"):
            raise ClientError("refusing to send portal cookies to another host")
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"User-Agent": USER_AGENT, **(headers or {})})
        opener = self.follow if follow else self.nofollow
        try:
            with opener.open(req, timeout=TIMEOUT) as resp:
                return resp.status, dict(resp.headers.items()), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except (urllib.error.URLError, OSError) as exc:
            raise ClientError(f"portal unreachable ({type(exc).__name__})") from None


def is_login_redirect(status: int, headers: dict[str, str]) -> bool:
    if status not in (301, 302, 303, 307, 308):
        return False
    location = next((v for k, v in headers.items() if k.lower() == "location"), "")
    return "login" in location.lower()


def logged_in(session: PortalSession, probe_url: str) -> bool:
    status, headers, _ = session.request("GET", probe_url)
    return status == 200 and not is_login_redirect(status, headers)


def _pending_path() -> Path:
    return cache_dir() / "portal-login-pending.json"


def start_qr_login(login_url: str) -> dict[str, Any]:
    origin = origin_of(login_url)
    session = PortalSession(origin)
    status, _, _ = session.request("GET", login_url, follow=True)
    if status >= 400:
        raise ClientError(f"portal login page returned HTTP {status}")
    login_uuid = str(uuidlib.uuid4())
    status, headers, body = session.request(
        "GET", f"{origin}{QR_PATH}?uuid={urllib.parse.quote(login_uuid)}")
    if status != 200 or not body:
        raise ClientError(f"QR code request returned HTTP {status}")
    content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    image = body
    if "json" in content_type.lower():
        try:
            payload = json.loads(body.decode("utf-8"))
            encoded = next(v for k, v in _walk(payload) if isinstance(v, str) and len(v) > 100)
            image = base64.b64decode(encoded.split(",", 1)[-1])
        except (ValueError, StopIteration, UnicodeError):
            raise ClientError("QR code response is JSON without an image") from None
    qr_file = cache_dir() / "portal-qr.png"
    fd = os.open(qr_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(image)
    write_private_json(_pending_path(), {"origin": origin, "uuid": login_uuid,
                                         "cookies": _jar_to_json(session.jar),
                                         "started_at": int(time.time())})
    return {"qr_image": str(qr_file), "expires_in": 300,
            "next": "Ask the user to open the QR image and scan it with the company app, then "
                    "call cex_portal_login_wait."}


def _walk(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def wait_qr_login(probe_url: str, timeout_s: float = 60.0, interval_s: float = 3.0
                  ) -> dict[str, Any]:
    pending = read_private_json(_pending_path())
    if not pending:
        raise ClientError("no portal login in progress; call cex_portal_login_start")
    if time.time() - pending["started_at"] > 300:
        _pending_path().unlink(missing_ok=True)
        raise ClientError("the QR code expired; call cex_portal_login_start again")
    session = PortalSession(pending["origin"], _jar_from_json(pending["cookies"]))
    form = urllib.parse.urlencode({"method": "twodimension", "uuid": pending["uuid"],
                                   "submit": "true"}).encode()
    deadline = time.time() + max(timeout_s, 1.0)
    while True:
        session.request("POST", pending["origin"] + LOGIN_PATH, data=form,
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
        if logged_in(session, probe_url):
            session.save()
            _pending_path().unlink(missing_ok=True)
            return {"ok": True, "logged_in": True}
        if time.time() + interval_s > deadline:
            write_private_json(_pending_path(), {**pending, "cookies": _jar_to_json(session.jar)})
            return {"ok": False, "pending": True,
                    "next": "The user has not scanned yet; call cex_portal_login_wait again."}
        time.sleep(interval_s)


def logout() -> dict[str, Any]:
    removed = session_path().exists()
    session_path().unlink(missing_ok=True)
    _pending_path().unlink(missing_ok=True)
    (cache_dir() / "portal-qr.png").unlink(missing_ok=True)
    return {"ok": True, "session_removed": removed}
