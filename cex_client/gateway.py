"""跳板机网关客户端：MCP streamable HTTP（POST <网关>/mcp，JSON-RPC），令牌用工作区的 OAuth 令牌。

- 网关地址取自服务端下发的客户端常量 `gateway.url`（cex_client_config 缓存在工作区），
  工作区 config.json 的 `gateway_url` 可覆盖；明文 http 策略与服务端地址一致（回环或显式 insecure_lan）。
- 租约（lease_id + fencing token）存工作区 `.compile-excel/lease.json`（0600），工具调用时自动带上，
  不让模型抄写 token。
- 每次提交记在 `.compile-excel/tasks.json`：task_id → 工作簿路径，用于把结果写回工作簿所在目录。
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
    write_private_json,
)


def gateway_url(ws: Workspace) -> str:
    cfg = ws.config()
    url = str(cfg.get("gateway_url") or "")
    if not url:
        cached = read_private_json(ws.client_config_path) or {}
        url = str((cached.get("gateway") or {}).get("url") or "")
    if not url:
        raise ClientError("no gateway address; call cex_client_config (the server publishes "
                          "gateway.url) or set gateway_url in the workspace config")
    return check_server_url(url, allow_insecure_http=bool(cfg.get("allow_insecure_http")))


def call_tool(ws: Workspace, name: str, arguments: dict[str, Any],
              timeout: float = 300.0) -> dict[str, Any]:
    url = gateway_url(ws)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": arguments}}).encode("utf-8")
    for attempt in (0, 1):
        token = auth.load_token(ws)
        if int(token.get("expires_at") or 0) < time.time() + 30 or attempt == 1:
            token = auth._refresh(ws, token)
        status, raw = auth.http("POST", url, data=body, timeout=timeout, headers={
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json", "Accept": "application/json"})
        if status == 401 and attempt == 0:
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


# ── 租约 ──────────────────────────────────────────────────────────────
def _lease_path(ws: Workspace):
    return ws.state_dir / "lease.json"


def lease_args(ws: Workspace) -> dict[str, Any]:
    lease = read_private_json(_lease_path(ws))
    if not lease:
        raise ClientError("no bed lease held from this workspace; call cex_bed_lease "
                          "with action=acquire")
    return {"lease_id": lease["lease_id"], "token": lease["token"]}


def lease(ws: Workspace, action: str) -> dict[str, Any]:
    if action == "acquire":
        out = call_tool(ws, "lease_acquire", {})
        if out.get("ok"):
            write_private_json(_lease_path(ws), {"lease_id": out["lease_id"],
                                                 "token": out["token"],
                                                 "expires_at": out.get("expires_at")})
        return out
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


def remember_task(ws: Workspace, task_id: str, record: dict[str, Any]) -> None:
    tasks = read_private_json(_tasks_path(ws)) or {}
    tasks[task_id] = record
    write_private_json(_tasks_path(ws), tasks)


def task_record(ws: Workspace, task_id: str) -> dict[str, Any] | None:
    return (read_private_json(_tasks_path(ws)) or {}).get(task_id)
