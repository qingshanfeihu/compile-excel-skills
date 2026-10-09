"""工具实现：circle 扩展、Claude Code 的 MCP 代理、pi 的 cex_tool 都调这一份。

每个工具是 `fn(args: dict) -> dict`；参数与说明的单一来源是同目录 tool_specs.json，
三个适配器都从那里生成各自的 schema，不各写一份。
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import auth, bugs, bundle, connect, device, gateway, manual_search, portal
from . import workspace as wsmod
from .errors import ClientError

SPECS_PATH = Path(__file__).resolve().parent / "tool_specs.json"
MAX_CHECK_COMMANDS = 200


def load_specs() -> list[dict[str, Any]]:
    return json.loads(SPECS_PATH.read_text(encoding="utf-8"))["tools"]


def _ws(args: dict[str, Any]) -> wsmod.Workspace:
    start = args.get("workspace")
    return wsmod.require(Path(start).expanduser() if start else None)


def _init_root(args: dict[str, Any]) -> Path:
    """cex_init 落在哪个文件夹：给了 workspace 就是它；没给时与其他工具一样先找已有的工作区
    （CEX_WORKSPACE，或从当前目录往上找），免得在子目录里报缺地址、或新建一个嵌套的工作区；
    都没有才新建在 CEX_WORKSPACE 指的文件夹（设了的话，其他工具认的就是它）或当前目录。"""
    if args.get("workspace"):
        return Path(str(args["workspace"])).expanduser()
    found = wsmod.find(None)
    if found is not None:
        return found.root
    explicit = os.environ.get("CEX_WORKSPACE", "").strip()
    return Path(explicit).expanduser() if explicit else Path.cwd()


def cex_init(args: dict[str, Any]) -> dict[str, Any]:
    root = _init_root(args)
    insecure = args.get("insecure_lan")
    ws = connect.setup(root, server=str(args.get("server") or ""),
                       device_build=str(args.get("device_build") or ""),
                       channel=str(args.get("channel") or ""),
                       insecure_lan=None if insecure is None else bool(insecure))
    build = ws.selected_build
    out = {"ok": True, "workspace": str(ws.root), "server": ws.server,
           "tls": connect.tls_summary(ws), "device_build": build or None, "channel": ws.channel}
    try:
        auth.load_token(ws)
        logged_in = True
    except ClientError:
        logged_in = False
    if logged_in:
        out["next"] = ("Still logged in. Call cex_sync to fetch compile data." if build else
                       "Still logged in. cex_sync picks the device build when the server publishes "
                       "only one; otherwise set the user's choice with cex_init device_build.")
    else:
        out["next"] = ("Call cex_login_start to sign in, then cex_sync to fetch compile data."
                       + ("" if build else " The device build is chosen after login."))
    return out


def cex_status(args: dict[str, Any]) -> dict[str, Any]:
    ws = wsmod.find(Path(args["workspace"]).expanduser() if args.get("workspace") else None)
    if ws is None:
        return {"ok": False, "workspace": None,
                "next": "No workspace here; call cex_init with the connection string the "
                        "administrator gave (https://host:8900#ca=<fingerprint>)."}
    build = ws.selected_build
    status: dict[str, Any] = {"ok": True, "workspace": str(ws.root), "server": ws.server,
                              "tls": connect.tls_summary(ws), "device_build": build or None,
                              "device_build_selected": bool(build), "channel": ws.channel}
    if not build:
        status["device_build_hint"] = wsmod.NO_DEVICE_BUILD
    try:
        token = auth.load_token(ws)
        status["logged_in"] = True
        status["scope"] = token.get("scope", "")
    except ClientError as exc:
        status["logged_in"] = False
        status["login_hint"] = str(exc)
    cached = bundle.cached_manifest(ws) if build else None
    status["bundle"] = ({"bundle_id": cached.get("bundle_id"), "created_at": cached.get("created_at")}
                        if cached else None)
    return status


def cex_login_start(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    out = {"ok": True, **auth.start_login(ws)}
    # 服务端用自带的根证书时浏览器会报证书不受信任：给用户一段说明和核对用的服务器证书指纹
    note = connect.browser_certificate_note(ws)
    if note:
        out["browser_certificate"] = note
        out["next"] = ("Show the user the URL and code, and relay browser_certificate to them word "
                       "for word before they open the URL: the browser will warn about the "
                       "certificate, and the note tells them what to check. They sign in with "
                       "their username and access code in a browser. Then call cex_login_wait.")
    return out


def cex_login_wait(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    timeout = float(args.get("timeout_s") or 60)
    out = auth.wait_login(ws, timeout_s=min(max(timeout, 1.0), 300.0))
    if out.get("ok") and not ws.selected_build:
        # 登录成功、工作区还没有构建号：服务端在本通道上只有一个构建就自动选，多个就列出来让用户选
        try:
            out.update(connect.choose_build(ws))
        except ClientError as exc:
            out["device_build_note"] = (f"登录成功，但没取到构建列表（{exc}）：稍后调用 cex_sync 会再选一次；"
                                        "也可以用 cex_init 的 device_build 直接指定")
    return out


def cex_logout(args: dict[str, Any]) -> dict[str, Any]:
    return auth.logout(_ws(args))


def cex_sync(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    channel = str(args.get("channel") or "")
    picked: dict[str, Any] = {}
    if not ws.selected_build:
        # 登录时没选成（当时服务端还没发布、或没取到列表）：同步前再选一次，按这次要同步的通道选
        auth.load_token(ws)
        picked = connect.choose_build(ws, channel)
        if not picked["device_build"]:
            raise ClientError(picked["device_build_note"])
    out = bundle.sync(ws, channel=channel or None)
    if picked:
        out["device_build_note"] = picked["device_build_note"]
    return out


def cex_client_config(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    config = auth.request_json(ws, "GET", "/v1/config/client")
    # 记下取自哪个服务端：网关地址只认这份缓存，换了服务端就得重取
    wsmod.write_private_json(ws.client_config_path,
                             {**config, gateway.CLIENT_CONFIG_SOURCE: ws.server})
    return {"ok": True, "config": config}


def cex_docs_query(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    query = str(args.get("q") or "").strip()
    if not query:
        raise ClientError("q is required")
    try:
        limit = int(str(args.get("limit", 3)).strip())
    except (TypeError, ValueError):
        limit = 3
    limit = max(1, min(limit, 10))
    local = manual_search.query(ws, query, limit)
    local_results = [{**row, "source": "local_manual"} for row in local.get("results", [])]
    server_results: list[dict[str, Any]] = []
    server_searched = False
    server_note = ""
    try:
        body, headers = auth._form({"q": query, "limit": str(limit)})
        payload = auth.request_json(ws, "POST", "/v1/docs/query", data=body,
                                    headers=headers)
        server_searched = True
        for row in payload.get("results") or []:
            if isinstance(row, dict):
                # A server document has no build-bound manual citation.
                server_results.append({**{key: value for key, value in row.items()
                                          if key != "ref"}, "source": "server_document"})
    except ClientError as exc:
        server_note = f"Server documents were not searched: {exc}"

    local_available = bool(local.get("manuals_searched"))
    skipped = local.get("manuals_skipped") or []
    local_note = (str(local.get("error") or "No searchable local manuals in this build's "
                      "bundle; call cex_sync if manuals are expected.")
                  if not local_available else "")
    if skipped:
        skipped_names = ", ".join(str(row["path"]) for row in skipped)
        local_note = (local_note + " " if local_note else "") + (
            f"Skipped unreadable local manuals: {skipped_names}.")
    out = {"ok": local_available or server_searched, "query": query,
           "build": ws.selected_build or None, "bundle_id": local.get("bundle_id"),
           "manuals_searched": local.get("manuals_searched", 0),
           "manuals_skipped": skipped,
           "server_searched": server_searched,
           "results": local_results[:limit] + server_results[:limit]}
    if local.get("bundle"):
        out["bundle"] = local["bundle"]
    if local_note:
        out["local_note"] = local_note
    if server_note:
        out["server_note"] = server_note
    if not out["ok"]:
        out["error"] = (f"docs query unavailable — {local_note}; {server_note}; "
                        "this is a supply failure, not evidence that the manual lacks this content")
        out["next"] = local.get("next") or "Call cex_sync and retry when the server is available."
    return out


def cex_cmd_check(args: dict[str, Any]) -> dict[str, Any]:
    """按已同步的命令树投影判定命令是否存在、参数是否合契约（与引擎同一判定函数）。"""
    from cex_core.vendor_cmd import load_projection, resolve_vendor_command

    ws = _ws(args)
    commands = args.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ClientError("commands must be a non-empty list of strings")
    if len(commands) > MAX_CHECK_COMMANDS:
        # 不悄悄只查前 200 条：超了就整次拒绝，让调用方分批
        raise ClientError(f"commands has {len(commands)} entries; at most {MAX_CHECK_COMMANDS} "
                          "per call - split the list over several calls")
    projection_path = bundle.entry_path(ws, "cmdtree", "vendor_stdlib_")
    if projection_path is None:
        raise ClientError("no command tree projection in the synced bundle; call cex_sync")
    projection = load_projection(projection_path)
    results = []
    for command in commands:
        verdict = resolve_vendor_command(str(command), projection)
        results.append({"command": str(command), **{k: verdict.get(k) for k in (
            "decided", "hit", "head", "src", "origin", "reason_code", "parameter_error")
            if k in verdict}})
    return {"ok": True, "projection": projection_path.name, "checked": len(results),
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


def cex_bed_lease(args: dict[str, Any]) -> dict[str, Any]:
    return gateway.lease(_ws(args), str(args.get("action") or ""))


def cex_env_prepare(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    # 带上本工作区的 device_build：网关据此核被测设备的 build 与编译数据是否同一版
    return gateway.call_tool(ws, "env_prepare", {**gateway.lease_args(ws),
                                                 "device_build": ws.device_build})


def cex_case_submit(args: dict[str, Any]) -> dict[str, Any]:
    return device.submit(_ws(args), str(args.get("xlsx") or ""), args.get("module") or None)


def cex_case_status(args: dict[str, Any]) -> dict[str, Any]:
    return device.status(_ws(args), str(args.get("task_id") or ""))


def cex_case_results(args: dict[str, Any]) -> dict[str, Any]:
    return device.results(_ws(args), str(args.get("task_id") or ""))


def cex_probe_show(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    return gateway.call_tool(ws, "probe_show", {
        **gateway.lease_args(ws), "command": str(args.get("command") or ""),
        "device_index": int(args.get("device_index") or 0)})


def cex_init_device(args: dict[str, Any]) -> dict[str, Any]:
    ws = _ws(args)
    forwarded = {k: args[k] for k in ("step", "device_index", "device_count", "confirmation")
                 if args.get(k) is not None}
    out = gateway.call_tool(ws, "init_device", {**gateway.lease_args(ws), **forwarded})
    if not out.get("ok") and "jumphost:admin" in str(out.get("error") or ""):
        out["next"] = ("The session was granted without jumphost:admin. If the user's account has "
                       "that permission (an administrator grants it on the server), sign in again "
                       "(cex_logout, then cex_login_start); otherwise device init is not available "
                       "to this user.")
    return out


def cex_portal_login_start(args: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **portal.start_qr_login(bugs.login_url(_ws(args)))}


def cex_portal_login_wait(args: dict[str, Any]) -> dict[str, Any]:
    timeout = min(max(float(args.get("timeout_s") or 60), 1.0), 300.0)
    return portal.wait_qr_login(bugs.probe_url(_ws(args)), timeout_s=timeout)


def cex_portal_logout(args: dict[str, Any]) -> dict[str, Any]:
    return portal.logout()


def cex_bug_get(args: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **bugs.get_ticket(_ws(args), str(args.get("backend") or ""),
                                          str(args.get("ticket") or ""))}


def cex_recompose_prepare(args: dict[str, Any]) -> dict[str, Any]:
    from . import recompose

    return recompose.prepare(_ws(args), str(args.get("mindmap") or ""),
                             out_name=str(args.get("out_name") or ""),
                             spec=str(args.get("spec") or ""))


def cex_recompose_submit_cases(args: dict[str, Any]) -> dict[str, Any]:
    from . import recompose

    return recompose.submit_cases(_ws(args), str(args.get("out_name") or ""), args.get("cases"))


def cex_recompose_seal(args: dict[str, Any]) -> dict[str, Any]:
    from . import recompose

    return recompose.seal(_ws(args), str(args.get("out_name") or ""))


def cex_lang_query(args: dict[str, Any]) -> dict[str, Any]:
    from . import recompose

    return recompose.lang_query(_ws(args), args, out_name=str(args.get("out_name") or ""))


def cex_bed_topology(args: dict[str, Any]) -> dict[str, Any]:
    from . import bed

    return bed.fetch(_ws(args), refresh=bool(args.get("refresh")))


def cex_author_prepare(args: dict[str, Any]) -> dict[str, Any]:
    from . import author

    return author.prepare(_ws(args), str(args.get("out_name") or ""))


def cex_criterion_record(args: dict[str, Any]) -> dict[str, Any]:
    from . import author

    return author.criterion_record(_ws(args), str(args.get("out_name") or ""),
                                   str(args.get("shape_key") or ""), args.get("judgment"))


def cex_author_submit_case(args: dict[str, Any]) -> dict[str, Any]:
    from . import author

    return author.submit_case(_ws(args), str(args.get("out_name") or ""),
                              args.get("mechanical_case"))


def cex_author_emit(args: dict[str, Any]) -> dict[str, Any]:
    from . import author

    return author.emit(_ws(args), str(args.get("out_name") or ""))


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
    "cex_bed_lease": cex_bed_lease,
    "cex_env_prepare": cex_env_prepare,
    "cex_case_submit": cex_case_submit,
    "cex_case_status": cex_case_status,
    "cex_case_results": cex_case_results,
    "cex_probe_show": cex_probe_show,
    "cex_init_device": cex_init_device,
    "cex_portal_login_start": cex_portal_login_start,
    "cex_portal_login_wait": cex_portal_login_wait,
    "cex_portal_logout": cex_portal_logout,
    "cex_bug_get": cex_bug_get,
    "cex_recompose_prepare": cex_recompose_prepare,
    "cex_recompose_submit_cases": cex_recompose_submit_cases,
    "cex_recompose_seal": cex_recompose_seal,
    "cex_lang_query": cex_lang_query,
    "cex_bed_topology": cex_bed_topology,
    "cex_author_prepare": cex_author_prepare,
    "cex_criterion_record": cex_criterion_record,
    "cex_author_submit_case": cex_author_submit_case,
    "cex_author_emit": cex_author_emit,
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
