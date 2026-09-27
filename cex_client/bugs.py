"""凭门户会话按单号取缺陷页，解析、脱敏后存进工作区。

- 地址白名单：只拼这几种详情页（Bugzilla show_bug.cgi?id=<数字>；禅道 bug-view-<数字>.html /
  story-view-<数字>.html），主机必须等于服务端下发的地址，不接受任意 URL；
- 单飞加限速：同一台机器上同一时刻只有一个取单请求（文件锁），两次请求至少间隔 1 秒；
- 被 302 回登录页就报会话过期，让用户重新扫码，不重试；
- 解析与脱敏用 cex_core.defects（逐字抽自 InfoTest），人名、附件链接不出客户端。
禅道详情页地址按禅道标准路由拼，尚未对真实门户验证；Bugzilla 地址与 InfoTest 一致。
"""

from __future__ import annotations

import fcntl
import json
import time
import urllib.parse
from typing import Any

from . import portal
from .errors import ClientError
from .workspace import Workspace, read_private_json, safe_component, write_file_safely

MIN_INTERVAL_S = 1.0


def _config(ws: Workspace) -> dict[str, Any]:
    cached = read_private_json(ws.client_config_path)
    if not cached:
        raise ClientError("no organisation config cached; call cex_client_config first")
    return cached


def detail_url(ws: Workspace, backend: str, number: str) -> str:
    cfg = _config(ws)
    defects = cfg.get("defects") or {}
    if backend == "bugzilla":
        base = (defects.get("bugzilla") or {}).get("proxy_url")
        if not base:
            raise ClientError("the server publishes no defects.bugzilla.proxy_url")
        return f"{base.rstrip('/')}/show_bug.cgi?id={number}"
    if backend in ("zentao", "zentao_story"):
        base = (defects.get("zentao") or {}).get("base_url")
        if not base:
            raise ClientError("the server publishes no defects.zentao.base_url")
        view = "story-view" if backend == "zentao_story" else "bug-view"
        return f"{base.rstrip('/')}/{view}-{number}.html"
    raise ClientError("backend must be bugzilla, zentao or zentao_story")


def probe_url(ws: Workspace) -> str:
    """登录是否成功的探测地址：Bugzilla 代理首页（受会话保护）。"""
    base = ((_config(ws).get("defects") or {}).get("bugzilla") or {}).get("proxy_url")
    if not base:
        raise ClientError("the server publishes no defects.bugzilla.proxy_url to verify login")
    return base.rstrip("/") + "/"


def login_url(ws: Workspace) -> str:
    url = ((_config(ws).get("portal") or {}).get("login_url") or "")
    if not url:
        raise ClientError("the server publishes no portal.login_url")
    return url


def _throttled_fetch(session: portal.PortalSession, url: str) -> tuple[int, dict, bytes]:
    lock_path = portal.cache_dir() / "portal.lock"
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        try:
            last = float(lock.read().strip() or 0)
        except ValueError:
            last = 0.0
        wait = MIN_INTERVAL_S - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        try:
            return session.request("GET", url)
        finally:
            lock.seek(0)
            lock.truncate()
            lock.write(str(time.time()))
            lock.flush()


def get_ticket(ws: Workspace, backend: str, ticket: str) -> dict[str, Any]:
    from cex_core.defects.parse import DefectParseError, canonical_ticket, parse_ticket_html

    backend = (backend or "").strip().lower()
    try:
        canonical = canonical_ticket(backend, ticket)
    except DefectParseError as exc:
        raise ClientError(f"invalid ticket id: {exc}") from None
    number = canonical.split("-", 1)[1]
    url = detail_url(ws, backend, number)
    origin = portal.origin_of(url)
    if origin != portal.origin_of(login_url(ws)):
        raise ClientError("defect tracker must be reached through the portal host")
    session = portal.PortalSession.load(origin)
    status, headers, body = _throttled_fetch(session, url)
    if portal.is_login_redirect(status, headers):
        raise portal.PortalSessionExpired(
            "portal session expired or missing; call cex_portal_login_start and scan again")
    if status != 200:
        raise ClientError(f"defect page returned HTTP {status}")
    try:
        parsed = parse_ticket_html(backend, canonical, body)
    except DefectParseError as exc:
        raise ClientError(f"defect page could not be used: {exc}") from None
    target = (ws.root / "defects" / safe_component(backend, "backend")
              / f"{safe_component(canonical, 'ticket')}.json")
    # 落在用户文件夹里：不跟随预先放好的符号链接（defects/ 或目标文件本身）
    write_file_safely(ws.root, target,
                      json.dumps(parsed, ensure_ascii=False, indent=1).encode("utf-8"))
    return {"ticket": parsed, "saved": str(target.relative_to(ws.root)),
            "source": urllib.parse.urlsplit(url).path}
