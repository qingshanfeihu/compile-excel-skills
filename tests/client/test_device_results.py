"""上机回执：失败断言连同实际回显摘出来、日志不再只留尾巴；投递时记下的 check_point 指纹
随结果落进 run_results.json，返工闸以它为准（编写阶段的出件会在过闸之前重写 provenance.json）。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cex_client import device, gateway
from cex_client import workspace as wsmod
from cex_client.fingerprints import case_fingerprints

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
              for i in range(40)) + """2026-01-01 10:00:07 ######################      FAIL      ####################
2026-01-01 10:00:07 #######   end case: 100000000000000002
2026-01-01 10:00:07 #######   begin case: 999999999999999
"""

# 框架给跑完的案收尾：计数、PASS/FAIL 横幅，紧跟 end case（lib/check_point.py close + parser_case_id）
LOG_A = """2026-01-01 09:59:00 #######   step2: 观察
2026-01-01 09:59:00 APV_0 sends command in config: show slb real
2026-01-01 09:59:01 #### Success Num 1: successed to find ok in :
2026-01-01 09:59:01 slb real http r1 ok
2026-01-01 09:59:01 #
2026-01-01 09:59:01 ################# The failed check point num:   0   ####
2026-01-01 09:59:01 #
2026-01-01 09:59:01 ################# The passed check point num:   1   ####
2026-01-01 09:59:01 #### Success Num 1: successed to find: ok
2026-01-01 09:59:01 #
2026-01-01 09:59:01 ######################      PASS      ####################
2026-01-01 09:59:01 #######   end case: 100000000000000001
2026-01-01 09:59:01 #######   begin case: 100000000000000002
"""


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
    submitted = []

    def call_tool(_ws, name, args):
        calls.append(name)
        if name == "case_submit":
            import base64
            import hashlib
            data = base64.b64decode(args["xlsx_b64"])
            submitted.append(f"t{len(submitted) + 1}")
            return {"ok": True, "task_id": submitted[-1], "sha256": hashlib.sha256(data).hexdigest(),
                    "case_ids": ["100000000000000001", "100000000000000002"]}
        if name == "case_results":
            return {"ok": True, "channel": "ready", "xlsx_sha256": "x",
                    "cases": [{"case_id": "100000000000000001", "result": "pass", "log": LOG_A},
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
    assert "100000000000000001" in json.dumps(report["violations"][0], ensure_ascii=False)

    # 只改上一轮 fail 的案：过闸
    cases["cases"][0]["steps"][0]["G"] = "ok"
    (batch / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(GATE), "--batch-dir", str(batch),
                           "--cases", str(batch / "cases.json")], capture_output=True, text=True,
                          check=False)
    report = json.loads(proc.stdout)
    assert proc.returncode == 0, report
    assert report["redispatch"] == ["100000000000000002"]


def _cases_doc(g1: str, g2: str) -> dict:
    return {"batch": "demo", "init_commands": ["hostname apv"], "cases": [
        {"autoid": "100000000000000001", "steps": [
            {"E": "APV_0", "F": "cmd_config", "G": "slb real http r1 10.0.0.1 80"},
            {"E": "check_point", "F": "found", "G": g1, "source": {"kind": "intent", "ref": "e1"}}]},
        {"autoid": "100000000000000002", "steps": [
            {"e": "check_point", "f": "found", "g": g2}]}]}


def test_the_run_records_what_the_cases_json_looked_like_when_it_ran(tmp_path, monkeypatch):
    """I6：投递时按工作簿旁的 cases.json 算逐案全行指纹，取结果时原样写进 run_results.json；
    之后 cases.json 被重写，回执里的指纹不变。"""
    ws = _workspace(tmp_path, monkeypatch)
    batch = _batch(ws, {"100000000000000001": _cp("ok"), "100000000000000002": _cp("fail")})
    doc = _cases_doc("ok", "fail")
    (batch / "cases.json").write_text(json.dumps(doc), encoding="utf-8")
    _fake_gateway(monkeypatch, log=LOG_B)
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    (batch / "cases.json").write_text(json.dumps(_cases_doc("changed", "fixed")), encoding="utf-8")
    device.results(ws, "t1")
    run = json.loads((batch / "run_results.json").read_text(encoding="utf-8"))
    assert run["case_fingerprints"] == case_fingerprints(doc)
    assert set(run["case_fingerprints"]) == {"100000000000000001", "100000000000000002", "__init__"}
    assert run["provenance_fingerprints"], "the check_point fingerprints are still recorded too"


def test_case_fingerprints_normalise_keys_and_cover_every_step():
    doc = _cases_doc("ok", "fail")
    upper = case_fingerprints(doc)
    lower = json.loads(json.dumps(doc).replace('"E"', '"e"').replace('"F"', '"f"')
                       .replace('"G"', '"g"'))
    assert case_fingerprints(lower) == upper, "E/F/G and e/f/g fingerprint the same"
    config_changed = json.loads(json.dumps(doc))
    config_changed["cases"][0]["steps"][0]["G"] = "slb real http r1 10.0.0.2 80"
    changed = case_fingerprints(config_changed)
    assert changed["100000000000000001"] != upper["100000000000000001"], "config steps count"
    assert changed["100000000000000002"] == upper["100000000000000002"]
    init_changed = {**doc, "init_commands": ["hostname other"]}
    assert case_fingerprints(init_changed)["__init__"] != upper["__init__"]
    import hashlib

    expected = hashlib.sha256(json.dumps(
        [{"e": "check_point", "f": "found", "g": "fail", "h": "", "i": ""}],
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert upper["100000000000000002"] == expected


def test_an_older_runs_results_do_not_overwrite_the_newer_receipt(tmp_path, monkeypatch):
    """M8：同一工作簿投了两次，先取第二次的结果写回执；再取第一次的结果照常返回，但不覆盖回执。"""
    ws = _workspace(tmp_path, monkeypatch)
    batch = _batch(ws, {"100000000000000001": _cp("ok"), "100000000000000002": _cp("fail")})
    _fake_gateway(monkeypatch, log=LOG_B)
    assert device.submit(ws, "compile_outputs/demo/case.xlsx")["task_id"] == "t1"
    assert device.submit(ws, "compile_outputs/demo/case.xlsx")["task_id"] == "t2"
    latest = device.results(ws, "t2")
    assert latest["receipt"] == "compile_outputs/demo/run_receipt.md"
    older = device.results(ws, "t1")
    assert older["ok"] and older["receipt"] is None and "t2" in older["note"]
    run = json.loads((batch / "run_results.json").read_text(encoding="utf-8"))
    assert run["task_id"] == "t2", "the batch receipt still describes the latest submission"
    assert "t2" in (batch / "run_receipt.md").read_text(encoding="utf-8")


def test_receipts_are_not_written_through_a_symlink(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    batch = _batch(ws, {"100000000000000001": _cp("ok"), "100000000000000002": _cp("fail")})
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    (batch / "run_results.json").symlink_to(victim)
    _fake_gateway(monkeypatch, log=LOG_B)
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    from cex_client import tools

    out = tools.call("cex_case_results", {"workspace": str(ws.root), "task_id": "t1"})
    assert out["ok"] is False and "symlink" in out["error"]
    assert victim.read_text(encoding="utf-8") == "keep"
