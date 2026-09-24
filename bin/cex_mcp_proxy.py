#!/usr/bin/env python3
"""cex_mcp_proxy：把 compile-excel 工具以 stdio MCP 服务暴露给 Claude Code 等 harness。

只依赖标准库。协议：JSON-RPC 2.0，每行一条消息（MCP stdio 传输）。
实现 initialize、notifications/initialized、ping、tools/list、tools/call；
工具清单来自 cex_client/tool_specs.json，执行走 cex_client.tools.call。
工作区：参数里的 workspace，或环境变量 CEX_WORKSPACE，或进程当前目录往上找。
stdout 只写协议消息；诊断写 stderr。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cex_client import tools  # noqa: E402

SERVER_INFO = {"name": "compile-excel", "version": "0.3.0"}
DEFAULT_PROTOCOL = "2025-06-18"


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "invalid request")
    method = message.get("method")
    msg_id = message.get("id")
    is_notification = "id" not in message
    params = message.get("params") or {}
    if method == "initialize":
        requested = params.get("protocolVersion") if isinstance(params, dict) else None
        return _result(msg_id, {
            "protocolVersion": requested or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _result(msg_id, {})
    if method == "tools/list":
        specs = tools.load_specs()
        return _result(msg_id, {"tools": [{
            "name": spec["name"],
            "description": spec["description"],
            "inputSchema": spec["input_schema"],
            "annotations": {"readOnlyHint": bool(spec.get("read_only"))},
        } for spec in specs]})
    if method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _error(msg_id, -32602, "tools/call needs a tool name")
        outcome = tools.call(params["name"], params.get("arguments") or {})
        failed = outcome.get("ok") is False and not outcome.get("pending")
        return _result(msg_id, {
            "content": [{"type": "text", "text": json.dumps(outcome, ensure_ascii=False)}],
            "structuredContent": outcome,
            "isError": failed,
        })
    if is_notification:
        return None
    return _error(msg_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            reply = _error(None, -32700, "parse error")
        else:
            if isinstance(message, list):
                replies = [r for r in (handle(m) for m in message) if r is not None]
                if replies:
                    sys.stdout.write(json.dumps(replies, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
                continue
            reply = handle(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
