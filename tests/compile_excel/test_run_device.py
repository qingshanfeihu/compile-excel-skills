"""run_device：拒收与超时分开的退出码、一投递就打 task_id、投递之后的失败都带 task_id。

旧版把「网关拒收」「等超时」「取结果失败」都报成 2，超时时模型分不清该重投还是该接着轮询。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "skills" / "compile-excel" / "scripts"))

import run_device  # noqa: E402

from cex_client.errors import ClientError  # noqa: E402


@pytest.fixture
def gateway_stub(monkeypatch):
    calls = {"status": [], "results": 0, "heartbeat": 0}
    state = {"submit": {"ok": True, "task_id": "cex_task_9"}, "status": {"state": "done"},
             "results": {"ok": True, "channel": "ready", "receipt": "r.md",
                         "totals": {"cases": 2, "pass": 2, "fail": 0, "not_run": 0}}}

    def submit(ws, xlsx, module=None):
        return state["submit"]

    def status(ws, task_id):
        calls["status"].append(task_id)
        if isinstance(state["status"], Exception):
            raise state["status"]
        return state["status"]

    def results(ws, task_id):
        calls["results"] += 1
        return state["results"]

    monkeypatch.setattr(run_device.workspace, "require", lambda start=None: object())
    monkeypatch.setattr(run_device.device, "submit", submit)
    monkeypatch.setattr(run_device.device, "status", status)
    monkeypatch.setattr(run_device.device, "results", results)
    monkeypatch.setattr(run_device.gateway, "lease",
                        lambda ws, action: calls.__setitem__("heartbeat", calls["heartbeat"] + 1) or {})
    monkeypatch.setattr(run_device.time, "sleep", lambda s: None)
    return state, calls


def _run(capsys, *extra: str) -> tuple[int, dict, str]:
    code = run_device.main(["--xlsx", "/nonexistent/ws/compile_outputs/b/case.xlsx", *extra])
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def test_refused_workbook_is_exit_2_without_a_task(gateway_stub, capsys):
    state, _calls = gateway_stub
    state["submit"] = {"ok": False, "problems": ["destructive command: clear config all"]}
    code, out, err = _run(capsys)
    assert code == 2 and out["stage"] == "submit" and out["problems"]
    assert "task_id" not in out and "task_id=" not in err


def test_timeout_is_exit_3_and_names_the_task_to_poll(gateway_stub, capsys):
    state, calls = gateway_stub
    state["status"] = {"state": "running"}
    code, out, err = _run(capsys, "--max-s", "0")
    assert code == 3 and out["task_id"] == "cex_task_9" and "cex_case_status" in out["error"]
    assert "task_id=cex_task_9" in err, "task_id 要在投递后立刻打出来，不等跑完"
    assert calls["results"] == 0


def test_losing_the_status_after_submit_is_exit_4_with_the_task(gateway_stub, capsys):
    state, _calls = gateway_stub
    state["status"] = ClientError("gateway returned HTTP 502")
    code, out, _err = _run(capsys)
    assert code == 4 and out["task_id"] == "cex_task_9" and out["stage"] == "status"


def test_results_not_ready_is_exit_4_with_the_task(gateway_stub, capsys):
    state, _calls = gateway_stub
    state["results"] = {"ok": True, "channel": "not_completed"}
    code, out, _err = _run(capsys)
    assert code == 4 and out["task_id"] == "cex_task_9" and out["channel"] == "not_completed"


@pytest.mark.parametrize("fail,code", [(0, 0), (1, 1)])
def test_finished_run_exit_code_follows_the_verdicts(gateway_stub, capsys, fail, code):
    state, _calls = gateway_stub
    state["results"]["totals"] = {"cases": 2, "pass": 2 - fail, "fail": fail, "not_run": 0}
    got, out, _err = _run(capsys)
    assert got == code and out["task_id"] == "cex_task_9" and out["ok"] is (fail == 0)


def test_a_lost_run_is_exit_5_and_says_to_resubmit(gateway_stub, capsys):
    """runner 死了，网关报 lost：不再轮询到 --max-s，也不叫人按 task_id 接着等。"""
    state, calls = gateway_stub
    state["status"] = {"state": "lost"}
    code, out, _err = _run(capsys)
    assert code == 5 and out["state"] == "lost" and "resubmit" in out["error"]
    assert len(calls["status"]) == 1 and calls["results"] == 0


def test_broken_cases_keep_the_run_from_passing(gateway_stub, capsys):
    state, _calls = gateway_stub
    state["results"]["totals"] = {"cases": 2, "pass": 1, "fail": 0, "broken": 1, "not_run": 0}
    state["results"]["rc"] = 124
    code, out, _err = _run(capsys)
    assert code == 1 and out["ok"] is False and out["rc"] == 124
