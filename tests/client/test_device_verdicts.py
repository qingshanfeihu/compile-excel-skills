"""上机判定要有框架收尾作证；pass 里有本案断言不在等的执行失败回显判 broken；runner 丢了不写回执；
回执带运行身份（rc、报告目录、落位）与会话转储。

框架在 begin case 时就给新案写一行结果，值是上一个案的结果，到 end case 才改成本案的
（mirror lib/test_xlsx.py parser_case_id、lib/mysqldb.py update_db_result）；进程被杀不走 teardown，
库里那行就停在占位值上——上一个案 pass，这个没跑完的案在库里也是 pass。
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

from cex_client import device, gateway
from cex_client import workspace as wsmod

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "compile-excel" / "scripts"))

import compile_excel  # noqa: E402

A1, A2, A3 = "100000000000000001", "100000000000000002", "100000000000000003"
MARKERS = ["Failed to execute the command", "Failed to get the file from",
           "RTNETLINK answers: File exists", "RTNETLINK answers: Cannot assign"]


def closing(autoid: str, verdict: str, *, failed: int = 0, passed: int = 1,
            nxt: str | None = None) -> str:
    """框架给跑完的案写的收尾（check_point.close + parser_case_id）。"""
    lines = ["#", f"################# The failed check point num:   {failed}   ####", "#",
             f"################# The passed check point num:   {passed}   ####", "#",
             f"######################      {verdict}      ####################",
             f"#######   end case: {autoid}"]
    if nxt:
        lines.append(f"#######   begin case: {nxt}")
    return "".join(f"2026-10-08 10:00:0{i % 10} {line}\n" for i, line in enumerate(lines))


def body(text: str) -> str:
    return "".join(f"2026-10-08 09:59:59 {line}\n" for line in text.splitlines())


@pytest.mark.parametrize("log,expected", [
    (closing(A1, "PASS"), "pass"),
    (closing(A1, "FAIL", failed=1, passed=0), "fail"),
    (body("APV_0 sends command in config: show x"), None),
    (closing(A2, "PASS"), None),
    (closing(A1, "PASS", failed=1), None),
    (closing(A1, "PASS", passed=0), None),
    (closing(A1, "FAIL") + closing(A1, "PASS"), None),
    (body("######################      FAIL      ####################") + closing(A1, "PASS"), None),
    # 网关截日志尾时计数行可能被截掉：横幅紧跟 end case 照样认
    ("2026-10-08 10:00:00 ######################      PASS      ####################\n"
     f"2026-10-08 10:00:00 #######   end case: {A1}\n", "pass"),
])
def test_framework_verdict_reads_only_a_well_formed_closing(log, expected):
    assert device.framework_verdict(log, A1) == expected


def _workspace(tmp_path: Path, monkeypatch) -> wsmod.Workspace:
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    return wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")


def _compile(ws: wsmod.Workspace, cases: list[dict]) -> Path:
    doc = {"batch": "demo", "cases": cases}
    src = ws.root / "cases.json"
    src.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    compile_excel.compile_excel(str(src), str(ws.outputs_dir))
    return ws.outputs_dir / "demo" / "case.xlsx"


def _steps(pattern: str) -> list[dict]:
    return [{"e": "APV_0", "f": "cmd_config", "g": "show slb real", "desc": "观察"},
            {"e": "check_point", "f": "found", "g": pattern, "desc": "断言"}]


def _gateway(monkeypatch, cases: list[dict], **extra):
    def call_tool(_ws, name, args):
        if name == "case_submit":
            data = base64.b64decode(args["xlsx_b64"])
            return {"ok": True, "task_id": "t1", "sha256": hashlib.sha256(data).hexdigest(),
                    "case_ids": [c["case_id"] for c in cases], "submit_autoid": cases[0]["case_id"],
                    "module": "sdns"}
        if name == "case_results":
            return {"ok": True, "channel": "ready", "xlsx_sha256": "x", "rc": 0,
                    "run_dir": "2026-10-08-10:00:00Infosec", "submit_autoid": cases[0]["case_id"],
                    "module": "sdns", "cases": cases, **extra}
        raise AssertionError(name)

    monkeypatch.setattr(gateway, "call_tool", call_tool)
    monkeypatch.setattr(gateway, "lease_args", lambda _ws: {})
    monkeypatch.setattr(device, "failure_markers", lambda _ws: list(MARKERS))


def test_a_case_the_run_stopped_in_is_broken_not_the_placeholder_pass(tmp_path, monkeypatch):
    """被杀在 A2 里：库里 A2 那行是开跑时写的占位值（A1 的 pass），A3 没开跑。"""
    ws = _workspace(tmp_path, monkeypatch)
    _compile(ws, [{"autoid": a, "steps": _steps("ok")} for a in (A1, A2, A3)])
    killed_in_a2 = body("#######   step2: 观察\nAPV_0 sends command in config: show slb real")
    _gateway(monkeypatch, [
        {"case_id": A1, "result": "pass", "log": body("slb real ok") + closing(A1, "PASS", nxt=A2)},
        {"case_id": A2, "result": "pass", "log": killed_in_a2},
        {"case_id": A3, "result": None, "log": ""},
    ], rc=124)
    assert device.submit(ws, "compile_outputs/demo/case.xlsx")["ok"]
    out = device.results(ws, "t1")
    verdicts = {c["autoid"]: c for c in out["cases"]}
    assert verdicts[A1]["verdict"] == "pass"
    assert verdicts[A2]["verdict"] == "broken" and verdicts[A2]["recorded_result"] == "pass"
    assert "占位" in verdicts[A2]["broken_reason"]
    assert verdicts[A3]["verdict"] == "not_run"
    assert out["totals"] == {"cases": 3, "pass": 1, "fail": 0, "broken": 1, "not_run": 1}
    run = json.loads((ws.outputs_dir / "demo" / "run_results.json").read_text(encoding="utf-8"))
    assert run["rc"] == 124 and run["run_dir"] == "2026-10-08-10:00:00Infosec"
    assert run["submit_autoid"] == A1 and run["module"] == "sdns"
    receipt = (ws.outputs_dir / "demo" / "run_receipt.md").read_text(encoding="utf-8")
    assert "退出码 124" in receipt and "ist_staging_sdns/" + A1 in receipt
    assert "999999999999999" in receipt, "the sentinel the compile appended is explained"


def test_a_result_row_that_disagrees_with_the_case_log_is_broken(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    _compile(ws, [{"autoid": A1, "steps": _steps("ok")}])
    _gateway(monkeypatch, [{"case_id": A1, "result": "pass",
                            "log": closing(A1, "FAIL", failed=1, passed=0)}])
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    case = device.results(ws, "t1")["cases"][0]
    assert case["verdict"] == "broken" and "fail" in case["broken_reason"]


def test_a_pass_with_an_unexpected_execution_failure_is_broken(tmp_path, monkeypatch):
    """668030 的形态：恢复步失败了，断言等的是别的东西，照样命中。"""
    ws = _workspace(tmp_path, monkeypatch)
    _compile(ws, [{"autoid": A1, "steps": _steps("vs3 is present")}])
    log = body("APV_0 sends command in config: config all tftp 10.0.0.1\n"
               "Failed to get the file from tftp server\nFailed to execute the command\n"
               "#######   step9: 校验\nAPV_0 sends command in config: show slb virtual\n"
               "vs3 is present") + closing(A1, "PASS")
    _gateway(monkeypatch, [{"case_id": A1, "result": "pass", "log": log}])
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    case = device.results(ws, "t1")["cases"][0]
    assert case["verdict"] == "broken" and case["recorded_result"] == "pass"
    assert any("Failed to execute the command" in line for line in case["failure_echo"])


def test_a_negative_case_waiting_for_the_rejection_stays_pass(tmp_path, monkeypatch):
    """负向用例：设备必须拒绝这条命令，断言等的就是拒绝的理由（InfoTest 2026-09-03 实证切片）。"""
    ws = _workspace(tmp_path, monkeypatch)
    reject = "is in use.*not allowed to add|already in use|cannot be added"
    _compile(ws, [{"autoid": A1, "steps": _steps(reject)}])
    log = body("APV_0 sends command in config: slb virtual addrlists \"addlist1\" 172.16.34.70\n"
               "#### Success Num 1: successed to find is in use.*not allowed to add in :\n"
               "slb virtual addrlists \"addlist1\" 172.16.34.70\n"
               "The virtual service ip address list is in use. It is not allowed to add another "
               "ip to it or delete the ip address list.\nFailed to execute the command\n"
               "APV(config)#") + closing(A1, "PASS")
    _gateway(monkeypatch, [{"case_id": A1, "result": "pass", "log": log}])
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    case = device.results(ws, "t1")["cases"][0]
    assert case["verdict"] == "pass", case


def test_without_markers_in_the_bundle_the_receipt_says_passes_were_not_scanned(
        tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    _compile(ws, [{"autoid": A1, "steps": _steps("ok")}])
    _gateway(monkeypatch, [{"case_id": A1, "result": "pass",
                            "log": body("Failed to execute the command") + closing(A1, "PASS")}])
    monkeypatch.setattr(device, "failure_markers", lambda _ws: None)
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    assert device.results(ws, "t1")["cases"][0]["verdict"] == "pass"
    run = json.loads((ws.outputs_dir / "demo" / "run_results.json").read_text(encoding="utf-8"))
    assert run["failure_echo_scan"] != "on"
    assert "没有扫空真" in (ws.outputs_dir / "demo" / "run_receipt.md").read_text(encoding="utf-8")


def test_session_dumps_land_beside_the_receipt_and_odd_names_are_dropped(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    _compile(ws, [{"autoid": A1, "steps": _steps("ok")}])
    _gateway(monkeypatch, [{"case_id": A1, "result": "fail",
                            "log": closing(A1, "FAIL", failed=1, passed=0),
                            "sessions": {"apv_172.16.35.71.txt": "APV(config)#show sdns node\n",
                                         "../escape.txt": "no", "notes.log": "no"}}])
    device.submit(ws, "compile_outputs/demo/case.xlsx")
    case = device.results(ws, "t1")["cases"][0]
    rel = f"compile_outputs/demo/evidence/t1/{A1}/apv_172.16.35.71.txt"
    assert case["sessions"] == {"apv_172.16.35.71.txt": rel}
    assert (ws.root / rel).read_text(encoding="utf-8") == "APV(config)#show sdns node\n"
    assert not (ws.root / "compile_outputs" / "demo" / "evidence" / "escape.txt").exists()
    assert rel in (ws.outputs_dir / "demo" / "run_receipt.md").read_text(encoding="utf-8")


def test_a_lost_run_writes_no_receipt(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    _compile(ws, [{"autoid": A1, "steps": _steps("ok")}])
    _gateway(monkeypatch, [{"case_id": A1, "result": None, "log": ""}])
    device.submit(ws, "compile_outputs/demo/case.xlsx")

    def lost(_ws, name, args):
        return {"ok": True, "task_id": "t1", "channel": "runner_lost", "state": "lost", "rc": None}

    monkeypatch.setattr(gateway, "call_tool", lost)
    out = device.results(ws, "t1")
    assert out["channel"] == "runner_lost" and "totals" not in out
    assert not (ws.outputs_dir / "demo" / "run_results.json").exists()
