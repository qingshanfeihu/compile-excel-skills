"""跳板机网关客户端：MCP streamable HTTP（POST <网关>/mcp，JSON-RPC），令牌用工作区的 OAuth 令牌。

- 网关地址只取服务端下发的客户端常量 `gateway.url`（cex_client_config 缓存在工作区
  client_config.json，记着取自哪个服务端）；工作区 config.json 里的字段不能改指令牌的去向。
  明文 http 策略与服务端地址一致（回环或显式 insecure_lan）；不跟随重定向。
- 租约（lease_id + fencing token）存工作区 `.compile-excel/lease.json`（0600），工具调用时自动带上；
  fencing token 不出现在任何工具结果里，不让模型抄写它。
- 每次提交记在 `.compile-excel/tasks.json`：task_id → 工作簿路径与提交序号，用于把结果写回工作簿所在目录。
"""

from __future__ import annotations

import json
import time
from typing import Any

from . import auth
from .errors import ClientError, NotLoggedIn
from .workspace import (
    Workspace,
    check_server_url,
    read_private_json,
    state_lock,
    write_private_json,
)

# 网关结果里这些键是租约凭据：只进 lease.json，不回给模型
_SECRET_KEYS = frozenset({"token", "fencing_token"})
CLIENT_CONFIG_SOURCE = "_fetched_from"


def redact(value: Any) -> Any:
    """去掉结果里（任意层）的 fencing token。"""
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k not in _SECRET_KEYS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def gateway_url(ws: Workspace) -> str:
    cfg = ws.config()
    cached = read_private_json(ws.client_config_path) or {}
    source = cached.get(CLIENT_CONFIG_SOURCE)
    if source is not None and source != ws.server:
        raise ClientError("the cached organisation config came from another server; call "
                          "cex_client_config again")
    url = str((cached.get("gateway") or {}).get("url") or "")
    if not url:
        raise ClientError("no gateway address; call cex_client_config (the server publishes "
                          "gateway.url)")
    return check_server_url(url, allow_insecure_http=bool(cfg.get("allow_insecure_http")))


def call_tool_raw(ws: Workspace, name: str, arguments: dict[str, Any],
                  timeout: float = 300.0) -> dict[str, Any]:
    """网关原样的结果（含租约凭据）；只给本模块存租约用，工具返回一律走 call_tool。"""
    url = gateway_url(ws)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}}).encode("utf-8")
    token = auth.load_token(ws)
    if int(token.get("expires_at") or 0) < time.time() + 30:
        token = auth._refresh(ws, token)
    for attempt in (0, 1):
        status, raw = auth.http("POST", url, data=body, timeout=timeout, headers={
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json", "Accept": "application/json"})
        auth.refuse_redirect(status, "the gateway")
        if status == 401 and attempt == 0:
            token = auth._refresh(ws, token)
            continue
        if status == 401:
            raise NotLoggedIn("the gateway rejected the session; log in again")
        if status != 200:
            raise ClientError(f"gateway returned HTTP {status}")
        try:
            reply = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise ClientError("gateway returned a non-JSON reply") from None
        if "error" in reply:
            raise ClientError(f"gateway error: {reply['error'].get('message')}")
        result = reply.get("result") or {}
        outcome = result.get("structuredContent")
        if not isinstance(outcome, dict):
            try:
                outcome = json.loads(result["content"][0]["text"])
            except (KeyError, IndexError, ValueError, TypeError):
                raise ClientError("gateway reply has no tool result") from None
        return outcome
    raise ClientError("unreachable")


def call_tool(ws: Workspace, name: str, arguments: dict[str, Any],
              timeout: float = 300.0) -> dict[str, Any]:
    return redact(call_tool_raw(ws, name, arguments, timeout=timeout))


# ── 租约 ──────────────────────────────────────────────────────────────
def _lease_path(ws: Workspace):
    return ws.lease_path


def lease_args(ws: Workspace) -> dict[str, Any]:
    lease = read_private_json(_lease_path(ws))
    if not lease:
        raise ClientError("no bed lease held from this workspace; call cex_bed_lease "
                          "with action=acquire")
    return {"lease_id": lease["lease_id"], "token": lease["token"]}


def lease(ws: Workspace, action: str) -> dict[str, Any]:
    if action == "acquire":
        out = call_tool_raw(ws, "lease_acquire", {})
        if out.get("ok"):
            write_private_json(_lease_path(ws), {"lease_id": out["lease_id"],
                                                 "token": out["token"],
                                                 "expires_at": out.get("expires_at")})
        return redact(out)
    if action == "status":
        return call_tool(ws, "lease_status", {})
    if action in ("heartbeat", "release"):
        out = call_tool(ws, f"lease_{action}", lease_args(ws))
        if action == "release" and out.get("ok"):
            _lease_path(ws).unlink(missing_ok=True)
        elif action == "heartbeat" and out.get("ok"):
            current = read_private_json(_lease_path(ws)) or {}
            write_private_json(_lease_path(ws), {**current, "expires_at": out.get("expires_at")})
        return out
    raise ClientError("action must be acquire, heartbeat, release or status")


# ── 任务记录 ──────────────────────────────────────────────────────────
def _tasks_path(ws: Workspace):
    return ws.state_dir / "tasks.json"


def remember_task(ws: Workspace, task_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """记一次提交；seq 是本工作区的提交序号（同一工作簿哪次最新就看它）。"""
    with state_lock(ws, "tasks"):
        tasks = read_private_json(_tasks_path(ws)) or {}
        seq = 1 + max((int(r.get("seq") or 0) for r in tasks.values() if isinstance(r, dict)),
                      default=0)
        tasks[task_id] = {**record, "seq": seq}
        write_private_json(_tasks_path(ws), tasks)
        return tasks[task_id]


def task_record(ws: Workspace, task_id: str) -> dict[str, Any] | None:
    return (read_private_json(_tasks_path(ws)) or {}).get(task_id)


def _order(record: dict[str, Any]) -> tuple[int, str]:
    return int(record.get("seq") or 0), str(record.get("submitted_at") or "")


def newer_submissions(ws: Workspace, task_id: str) -> list[str]:
    """同一工作簿在这次之后又提交过的 task_id（按提交序号；旧记录没有序号时按提交时间）。"""
    tasks = read_private_json(_tasks_path(ws)) or {}
    mine = tasks.get(task_id)
    if not isinstance(mine, dict):
        return []
    return [other_id for other_id, other in tasks.items()
            if other_id != task_id and isinstance(other, dict)
            and other.get("xlsx") == mine.get("xlsx") and _order(other) > _order(mine)]
