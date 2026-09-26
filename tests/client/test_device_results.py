"""上机回执：失败断言连同实际回显摘出来、日志不再只留尾巴；投递时记下的 check_point 指纹
随结果落进 run_results.json，返工闸以它为准（编写阶段的出件会在过闸之前重写 provenance.json）。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cex_client import device, gateway
from cex_client import workspace as wsmod

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "skills" / "compile-excel" / "scripts" / "rework_gate.py"

LOG_B = """2026-01-01 10:00:00 #######   begin case: 100000000000000002
2026-01-01 10:00:01 APV_0 sends command in config: slb virtual tcplist vs2 addlist1 port1
2026-01-01 10:00:02 RouterB executes command: ( curl -s -o /dev/null --max-time 8 http://192.0.2.70:80/ ); ist_case_exit_code=$?; echo; printf 'IST_EXIT_STATUS=%s' "$ist_case_exit_code"; echo
2026-01-01 10:00:02 #### Fail Num 1: fail to find (?m)^IST_EXIT_STATUS=0\\r?$ in:
2026-01-01 10:00:02 ( curl -s -o /dev/null --max-time 8 http://192.0.2.70:80/ ); ist_case_exit_code=$?; echo; printf 'IST_EXIT_STATUS=%s' "$ist_case_exit_code"; echo
2026-01-01 10:00:02 IST_EXIT_STATUS=56
2026-01-01 10:00:05 ################# The failed check point num:   1   ####
2026-01-01 10:00:05 #### Fail Num 1: fail to find: (?m)^IST_EXIT_STATUS=0\\r?$
""" + "".join(f"2026-01-01 10:00:06 APV_0 sends command in config: no slb real tcp rs{i}\n"
              for i in range(40))


def _workspace(tmp_path: Path, monkeypatch) -> wsmod.Workspace:
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    return wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")


def _batch(ws: wsmod.Workspace, fp_entries: dict[str, list]) -> Path:
    batch = ws.outputs_dir / "demo"
    batch.mkdir(parents=True)
    (batch / "case.xlsx").write_bytes(b"xlsx-bytes")
    (batch / "provenance.json").write_text(json.dumps(
        {"schema": "ist.excel.provenance", "batch": "demo", "cases": fp_entries},
        ensure_ascii=False), encoding="utf-8")
    return batch


def _cp(pattern: str) -> list[dict]:
    return [{"E": "check_point", "F": "found", "G": pattern,
             "source": {"kind": "status_derived", "ref": "status.exit:abc"}}]


def _fake_gateway(monkeypatch, *, log: str):
    calls = []

    def call_tool(_ws, name, args):
        calls.append(name)
        if name == "case_submit":
            import base64
            import hashlib
            data = base64.b64decode(args["xlsx_b64"])
            return {"ok": True, "task_id": "t1", "sha256": hashlib.sha256(data).hexdigest(),
                    "case_ids": ["100000000000000001", "100000000000000002"]}
        if name == "case_results":
            return {"ok": True, "channel": "ready", "xlsx_sha256": "x",
                    "cases": [{"case_id": "100000000000000001", "result": "pass"},
                              {"case_id": "100000000000000002", "result": "fail", "log": log}]}
        raise AssertionError(name)

    monkeypatch.setattr(gateway, "call_tool", call_tool)
    monkeypatch.setattr(gateway, "lease_args", lambda _ws: {})
    return calls


def test_failed_checks_carry_the_observed_output_and_the_log_is_kept_whole(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    _batch(ws, {"100000000000000001": _cp("ok"), "100000000000000002": _cp("fail")})
    _fake_gateway(monkeypatch, log=LOG_B)
    assert device.submit(ws, "compile_outputs/demo/case.xlsx")["ok"]
    out = device.results(ws, "t1")
    returned = next(c for c in out["cases"] if c["verdict"] == "fail")
    assert len(returned["detail_tail"]) <= 600, "the session gets a short tail, not whole logs"
    assert returned["failed_checks"] and "IST_EXIT_STATUS=56" in returned["failed_checks"][0]
    assert len(returned["failed_checks"]) == 1, "the closing summary line is not a second failure"
    run = json.loads((ws.outputs_dir / "demo" / "run_results.json").read_text(encoding="utf-8"))
    kept = next(c for c in run["cases"] if c["verdict"] == "fail")
    assert kept["detail_tail"] == LOG_B, "the file keeps the whole log the gateway returned"
    receipt = (ws.outputs_dir / "demo" / "run_receipt.md").read_text(encoding="utf-8")
    assert "IST_EXIT_STATUS=56" in receipt


def test_the_rework_gate_compares_against_what_actually_ran(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    batch = _batch(ws, {"100000000000000001": _cp("ok"), "100000000000000002": _cp("fail")})
    _fake_gateway(monkeypatch, log=LOG_B)
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    device.results(ws, "t1")
    run = json.loads((batch / "run_results.json").read_text(encoding="utf-8"))
    assert run["provenance_fingerprints"] == device.provenance_fingerprints(batch / "provenance.json")

    # 出件把 provenance.json 重写成新一轮（pass 案也被改了）：闸必须以上机时的指纹为准
    changed = {"100000000000000001": _cp("changed"), "100000000000000002": _cp("fixed")}
    (batch / "provenance.json").write_text(json.dumps({"cases": changed}), encoding="utf-8")
    cases = {"cases": [{"autoid": a, "steps": [{"E": e["E"], "F": e["F"], "G": e["G"],
                                                 "source": e["source"]} for e in entries]}
                       for a, entries in changed.items()]}
    (batch / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(GATE), "--batch-dir", str(batch),
                           "--cases", str(batch / "cases.json")], capture_output=True, text=True,
                          check=False)
    report = json.loads(proc.stdout)
    assert proc.returncode == 1 and report["violations"], report
    assert "100000000000000001" in report["violations"][0]

    # 只改上一轮 fail 的案：过闸
    cases["cases"][0]["steps"][0]["G"] = "ok"
    (batch / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(GATE), "--batch-dir", str(batch),
                           "--cases", str(batch / "cases.json")], capture_output=True, text=True,
                          check=False)
    report = json.loads(proc.stdout)
    assert proc.returncode == 0, report
    assert report["redispatch"] == ["100000000000000002"]
