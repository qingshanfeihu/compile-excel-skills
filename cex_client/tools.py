"""工具实现：circle 扩展、Claude Code 的 MCP 代理、pi 的 cex_tool 都调这一份。

每个工具是 `fn(args: dict) -> dict`；参数与说明的单一来源是同目录 tool_specs.json，
三个适配器都从那里生成各自的 schema，不各写一份。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import auth, bundle
from . import workspace as wsmod
from .errors import ClientError

SPECS_PATH = Path(__file__).resolve().parent / "tool_specs.json"


def load_specs() -> list[dict[str, Any]]:
    return json.loads(SPECS_PATH.read_text(encoding="utf-8"))["tools"]


def _ws(args: dict[str, Any]) -> wsmod.Workspace:
    start = args.get("workspace")
    return wsmod.require(Path(start).expanduser() if start else None)


def cex_init(args: dict[str, Any]) -> dict[str, Any]:
    root = Path(args.get("workspace") or ".").expanduser()
    ws = wsmod.init(root, server=str(args.get("server") or ""),
                    device_build=str(args.get("device_build") or ""),
                    channel=str(args.get("channel") or "stable"),
                    insecure_lan=bool(args.get("insecure_lan")))
    return {"ok": True, "workspace": str(ws.root), "server": ws.server,
            "device_build": ws.device_build,
            "next": "Call cex_login_start to sign in, then cex_sync to fetch compile data."}


def cex_status(args: dict[str, Any]) -> dict[str, Any]:
    ws = wsmod.find(Path(args["workspace"]).expanduser() if args.get("workspace") else None)
    if ws is None:
        return {"ok": False, "workspace": None,
                "next": "No workspace here; call cex_init with the server URL and device build."}
    status: dict[str, Any] = {"ok": True, "workspace": str(ws.root), "server": ws.server,
                              "device_build": ws.device_build, "channel": ws.channel}
    try:
        token = auth.load_token(ws)
        status["logged_in"] = True
        status["scope"] = token.get("scope", "")
    except ClientError as exc:
        status["logged_in"] = False
        status["login_hint"] = str(exc)
    cached = bundle.cached_manifest(ws)
    status["bundle"] = ({"bundle_id": cached.get("bundle_id"), "created_at": cached.get("created_at")}
                        if cached else None)
    return status


def cex_login_start(args: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **auth.start_login(_ws(args))}


def cex_login_wait(args: dict[str, Any]) -> dict[str, Any]:
    timeout = float(args.get("timeout_s") or 60)
    return auth.wait_login(_ws(args), timeout_s=min(max(timeout, 1.0), 300.0))


def cex_logout(args: dict[str, Any]) -> dict[str, Any]:
    return auth.logout(_ws(args))


def cex_sync(args: dict[str, Any]) -> dict[str, Any]:
    return bundle.sync(_ws(args), channel=args.get("channel") or None)


def cex_client_config(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    config = auth.request_json(ws, "GET", "/v1/config/client")
    wsmod.write_private_json(ws.client_config_path, config)
    return {"ok": True, "config": config}


def cex_docs_query(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    query = str(args.get("q") or "").strip()
    if not query:
        raise ClientError("q is required")
    limit = max(1, min(int(args.get("limit") or 3), 10))
    body, headers = auth._form({"q": query, "limit": str(limit)})
    return {"ok": True, **auth.request_json(ws, "POST", "/v1/docs/query", data=body,
                                            headers=headers)}


def cex_cmd_check(args: dict[str, Any]) -> dict[str, Any]:
    """按已同步的命令树投影判定命令是否存在、参数是否合契约（与引擎同一判定函数）。"""
    from cex_core.vendor_cmd import load_projection, resolve_vendor_command

    ws = _ws(args)
    commands = args.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ClientError("commands must be a non-empty list of strings")
    projection_path = bundle.entry_path(ws, "cmdtree", "vendor_stdlib_")
    if projection_path is None:
        raise ClientError("no command tree projection in the synced bundle; call cex_sync")
    projection = load_projection(projection_path)
    results = []
    for command in commands[:200]:
        verdict = resolve_vendor_command(str(command), projection)
        results.append({"command": str(command), **{k: verdict.get(k) for k in (
            "decided", "hit", "head", "reason_code", "parameter_error") if k in verdict}})
    return {"ok": True, "projection": projection_path.name,
            "all_hit": all(r.get("hit") for r in results), "results": results}


def cex_scan_destructive(args: dict[str, Any]) -> dict[str, Any]:
    from cex_core.scan_destructive import scan_workbook

    ws = _ws(args)
    xlsx = Path(str(args.get("xlsx") or "")).expanduser()
    if not xlsx.is_absolute():
        xlsx = ws.root / xlsx
    xlsx = xlsx.resolve()
    if ws.root.resolve() not in xlsx.parents or not xlsx.is_file():
        raise ClientError("xlsx must be an existing file inside the workspace")
    grammar = bundle.entry_path(ws, "projections", "domain_grammar")
    if grammar is None:
        raise ClientError("no domain grammar in the synced bundle; call cex_sync")
    findings = scan_workbook(xlsx, grammar)
    return {"ok": not findings, "findings": findings}


TOOLS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "cex_init": cex_init,
    "cex_status": cex_status,
    "cex_login_start": cex_login_start,
    "cex_login_wait": cex_login_wait,
    "cex_logout": cex_logout,
    "cex_sync": cex_sync,
    "cex_client_config": cex_client_config,
    "cex_docs_query": cex_docs_query,
    "cex_cmd_check": cex_cmd_check,
    "cex_scan_destructive": cex_scan_destructive,
}


def call(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    """统一入口：未知工具、参数不是对象、工具内部失败都变成 {ok: false, error}。"""
    fn = TOOLS.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown tool {name!r}"}
    if args is not None and not isinstance(args, dict):
        return {"ok": False, "error": "arguments must be a JSON object"}
    try:
        return fn(dict(args or {}))
    except ClientError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — 工具边界：异常类型交给模型，不带堆栈
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
