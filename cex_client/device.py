"""上机：经网关提交工作簿、轮询、取回框架判定，并把回执写回工作簿所在目录。

判定语义归框架：verdict 来自框架结果库；pytest 的 “1 passed” 不代表断言通过。
非 pass 的 case 附框架日志作归因证据；早于投递时间的日志网关已标 stale，这里不拿它当证据。
回执格式沿用原 run_device（ist.excel.device-run-result）：run_results.json 机读、run_receipt.md 人读。
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from . import gateway
from .errors import ClientError
from .workspace import Workspace

RESULT_SCHEMA = "ist.excel.device-run-result"
MAX_XLSX_BYTES = 32 * 1024 * 1024

# 机械归因只判协议级事实；语义归因留给会话（与原 run_device 相同的标记集）
_G_LAYER_MARKERS = (
    "% invalid", "% unrecognized", "% unknown", "% error",
    "syntax error", "invalid input", "command not found",
)
_TRANSIENT_MARKERS = (
    "timeout", "timed out", "read_until", "connection reset",
    "connection closed", "device_busy", "traceback", "not reachable",
)


def attribute_fail(detail_tail: str) -> dict[str, str]:
    text = (detail_tail or "").lower()
    for marker in _G_LAYER_MARKERS:
        if marker in text:
            return {"layer": "G", "evidence": marker, "note": "命令/语法层——回显含 CLI 错误标记"}
    for marker in _TRANSIENT_MARKERS:
        if marker in text:
            return {"layer": "transient?", "evidence": marker,
                    "note": "疑似瞬态（超时/连接/忙）——同签名复发则非瞬态，不升格"}
    return {"layer": "undetermined", "evidence": "",
            "note": "机械标记无法裁决，需会话按 detail_tail 语义归因（E/V/产品缺陷）"}


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def resolve_xlsx(ws: Workspace, xlsx: str) -> Path:
    path = Path(str(xlsx or "")).expanduser()
    if not path.is_absolute():
        path = ws.root / path
    path = path.resolve()
    if ws.root.resolve() not in path.parents or not path.is_file():
        raise ClientError("xlsx must be an existing file inside the workspace")
    if path.stat().st_size > MAX_XLSX_BYTES:
        raise ClientError("workbook is larger than the gateway accepts")
    return path


def submit(ws: Workspace, xlsx: str, module: str | None = None) -> dict[str, Any]:
    path = resolve_xlsx(ws, xlsx)
    data = path.read_bytes()
    args: dict[str, Any] = {**gateway.lease_args(ws),
                            "xlsx_b64": base64.b64encode(data).decode("ascii")}
    if module:
        args["module"] = module
    out = gateway.call_tool(ws, "case_submit", args)
    if out.get("ok"):
        local_sha = hashlib.sha256(data).hexdigest()
        if out.get("sha256") != local_sha:
            raise ClientError("gateway staged a different workbook than the one sent")
        gateway.remember_task(ws, out["task_id"], {
            "xlsx": str(path.relative_to(ws.root)), "sha256": local_sha,
            "submitted_at": _now(), "case_ids": out.get("case_ids", [])})
    return out


def status(ws: Workspace, task_id: str) -> dict[str, Any]:
    return gateway.call_tool(ws, "case_status", {"task_id": task_id})


def results(ws: Workspace, task_id: str) -> dict[str, Any]:
    """取结果；运行结束且结果通道就绪时，把回执写回工作簿目录。"""
    out = gateway.call_tool(ws, "case_results", {"task_id": task_id})
    if not out.get("ok") or out.get("channel") == "not_completed":
        return out
    record = gateway.task_record(ws, task_id) or {}
    cases = []
    for case in out.get("cases") or []:
        verdict = str(case.get("result") or "not_run").lower()
        entry: dict[str, Any] = {"autoid": case["case_id"], "verdict": verdict}
        if verdict != "pass":
            entry["detail_tail"] = "" if case.get("log_stale") else (case.get("log") or "")[-600:]
            if case.get("log_stale"):
                entry["note"] = "框架日志早于本次投递（上一轮残留），不作本次证据"
            entry["attribution"] = attribute_fail(entry["detail_tail"])
        cases.append(entry)
    verdicts = [c["verdict"] for c in cases]
    totals = {"cases": len(verdicts), "pass": verdicts.count("pass"),
              "fail": verdicts.count("fail"),
              "not_run": sum(1 for v in verdicts if v not in ("pass", "fail"))}
    written = None
    if record.get("xlsx"):
        xlsx = ws.root / record["xlsx"]
        result = {
            "schema": RESULT_SCHEMA, "xlsx": record["xlsx"], "xlsx_sha256": out.get("xlsx_sha256"),
            "batch": xlsx.parent.name, "task_id": task_id, "result_channel": out.get("channel"),
            "submitted": record.get("submitted_at"), "finished": _now(), "cases": cases,
            "totals": totals,
        }
        write_receipts(result, xlsx.parent)
        written = str((xlsx.parent / "run_receipt.md").relative_to(ws.root))
    return {**out, "totals": totals, "cases": cases, "receipt": written}


def write_receipts(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    t = result["totals"]
    lines = [
        "# 上机回执（run_receipt）", "",
        f"- batch: `{result['batch']}`",
        f"- xlsx: `{result['xlsx']}` (sha256 `{str(result.get('xlsx_sha256') or '')[:16]}…`)",
        f"- task_id: `{result.get('task_id', '')}`",
        f"- 时间: {result.get('submitted')} → {result['finished']}",
        f"- 总数: {t['cases']} · pass {t['pass']} · fail {t['fail']} · not_run {t['not_run']}",
        f"- result channel: {result.get('result_channel')}", "",
        "| autoid | 框架判定 | 证据摘录 |", "|---|---|---|",
    ]
    for case in result["cases"]:
        note = (case.get("detail_tail") or case.get("note") or "").replace("\n", " ⏎ ")[:160]
        layer = (case.get("attribution") or {}).get("layer")
        if layer:
            note = f"[{layer}] {note}"
        lines.append(f"| {case['autoid']} | {case['verdict']} | {note or '-'} |")
    (out_dir / "run_receipt.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_and_wait(ws: Workspace, xlsx: str, *, module: str | None = None, poll_s: float = 10,
                 max_s: float = 2400, heartbeat_s: float = 300) -> dict[str, Any]:
    """提交 → 轮询到结束（期间续租约）→ 取结果写回执。给 run_device.py 这类一次跑完的入口用。"""
    submitted = submit(ws, xlsx, module)
    if not submitted.get("ok"):
        return submitted
    task_id = submitted["task_id"]
    deadline = time.time() + max_s
    last_beat = time.time()
    while time.time() < deadline:
        state = status(ws, task_id)
        if state.get("state") == "done":
            return {**results(ws, task_id), "task_id": task_id}
        if time.time() - last_beat > heartbeat_s:
            gateway.lease(ws, "heartbeat")
            last_beat = time.time()
        time.sleep(poll_s)
    return {"ok": False, "task_id": task_id,
            "error": f"run did not finish within {int(max_s)}s; poll cex_case_status later"}
