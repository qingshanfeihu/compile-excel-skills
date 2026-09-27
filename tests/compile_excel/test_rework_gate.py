"""返工闸：逐案全行指纹（I6 case_fingerprints）、init 锁、--force 必带理由、只在闸通过时写账。

基线取 run_results.json 里上机时记下的 case_fingerprints；指纹函数是 cex_client.fingerprints 的
case_fingerprints。发行版里还没有这个模块时，用一个按同一契约写的替身（每案对全部步骤含出处取
sha，"__init__" 对 init_commands 取 sha）注入 sys.modules——闸只比较两次调用的结果，不依赖算法细节。
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "compile-excel" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import rework_gate  # noqa: E402

PASS_ID = "202609279000010001"
FAIL_ID = "202609279000010002"

DOC = {
    "batch": "rw_batch",
    "init_commands": ["clear slb virtual httplist"],
    "cases": [
        {"autoid": PASS_ID, "steps": [
            {"e": "APV_0", "f": "cmd_config", "g": "slb real http r1 10.0.0.1 80"},
            {"e": "APV_0", "f": "cmd_config", "g": "show slb real http"},
            {"e": "check_point", "f": "found", "g": "r1",
             "source": {"kind": "configbinding", "ref": "step:1"}},
            {"e": "APV_0", "f": "cmd_config", "g": "no slb real http r1"}]},
        {"autoid": FAIL_ID, "steps": [
            {"e": "APV_0", "f": "cmd_config", "g": "show version"},
            {"e": "check_point", "f": "found", "g": "Version:",
             "source": {"kind": "spec", "ref": "spec:x.md:1"}}]},
    ],
}


def _stub_case_fingerprints(doc: dict) -> dict[str, str]:
    def sha(value) -> str:
        blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    out = {str(c.get("autoid")): sha(c.get("steps") or []) for c in doc.get("cases") or []}
    out["__init__"] = sha([str(c) for c in doc.get("init_commands") or []])
    return out


@pytest.fixture
def fingerprint(monkeypatch):
    try:
        from cex_client.fingerprints import case_fingerprints
    except ImportError:
        stub = types.ModuleType("cex_client.fingerprints")
        stub.case_fingerprints = _stub_case_fingerprints
        monkeypatch.setitem(sys.modules, "cex_client.fingerprints", stub)
        case_fingerprints = _stub_case_fingerprints
    return case_fingerprints


def _batch(tmp_path: Path, fingerprint, *, with_fingerprints: bool = True) -> Path:
    batch_dir = tmp_path / "compile_outputs" / DOC["batch"]
    batch_dir.mkdir(parents=True)
    (batch_dir / "cases.json").write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
    run = {"schema": "ist.excel.device-run-result", "task_id": "cex_task_1",
           "xlsx_sha256": "0" * 64, "finished": "2026-09-27T10:00:00+08:00",
           "cases": [{"autoid": PASS_ID, "verdict": "pass"},
                     {"autoid": FAIL_ID, "verdict": "fail"}],
           "totals": {"cases": 2, "pass": 1, "fail": 1, "not_run": 0}}
    if with_fingerprints:
        run["case_fingerprints"] = fingerprint(DOC)
        # 现行客户端还会写只含 check_point 的旧指纹；有全行指纹时闸不能再退回它
        run["provenance_fingerprints"] = {
            c["autoid"]: rework_gate._entries_fp(rework_gate._cp_entries(c["autoid"], c))
            for c in DOC["cases"]}
    (batch_dir / "run_results.json").write_text(json.dumps(run), encoding="utf-8")
    return batch_dir


def _gate(batch_dir: Path, doc: dict, *extra: str, capsys) -> tuple[int, dict]:
    cases = batch_dir.parent / "next_cases.json"
    cases.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code = rework_gate.main(["--batch-dir", str(batch_dir), "--cases", str(cases), *extra])
    return code, json.loads(capsys.readouterr().out)


def test_changed_config_step_of_a_pass_case_is_a_violation(tmp_path, fingerprint, capsys):
    """只比 check_point 的旧闸看不见配置步和观察命令的改动（评审复现：httpslist→httplist 照样放行）。"""
    batch_dir = _batch(tmp_path, fingerprint)
    doc = copy.deepcopy(DOC)
    doc["cases"][0]["steps"][0]["g"] = "slb real http r1 10.0.0.9 80"
    code, out = _gate(batch_dir, doc, capsys=capsys)
    assert code == 1
    assert out["baseline"] == "case_fingerprints"
    assert [(v["autoid"], v["code"]) for v in out["violations"]] == [(PASS_ID, "pass_case_changed")]
    assert not (batch_dir / "rework.json").exists(), "拒绝时不能留下一份像是过了闸的 rework.json"


def test_changed_init_commands_lock_every_pass_case(tmp_path, fingerprint, capsys):
    batch_dir = _batch(tmp_path, fingerprint)
    doc = copy.deepcopy(DOC)
    doc["init_commands"] = ["clear slb virtual httplist", "slb real http r0 10.0.0.2 80"]
    code, out = _gate(batch_dir, doc, capsys=capsys)
    assert code == 1
    assert [v["code"] for v in out["violations"]] == ["init_commands_changed"]


def test_reworking_only_the_fail_case_passes_and_regating_keeps_the_round(tmp_path, fingerprint,
                                                                          capsys):
    batch_dir = _batch(tmp_path, fingerprint)
    doc = copy.deepcopy(DOC)
    doc["cases"][1]["steps"][1]["g"] = "Version: 10"
    code, out = _gate(batch_dir, doc, capsys=capsys)
    assert code == 0, out
    assert out["redispatch"] == [FAIL_ID] and out["changed_fail"] == [FAIL_ID]
    assert out["kept_pass"] == [PASS_ID] and out["violations"] == []
    record = json.loads((batch_dir / "rework.json").read_text(encoding="utf-8"))
    assert record["round"] == 1 and record["prior_task_id"] == "cex_task_1"
    # 同一轮上机的返工再过一次闸：还是这一轮，不另起一轮
    code, out = _gate(batch_dir, doc, capsys=capsys)
    assert code == 0 and out["round"] == 1


def test_force_needs_a_reason_and_records_it(tmp_path, fingerprint, capsys):
    batch_dir = _batch(tmp_path, fingerprint)
    doc = copy.deepcopy(DOC)
    doc["cases"][0]["steps"][1]["g"] = "show slb real http r1"
    code, out = _gate(batch_dir, doc, "--force", capsys=capsys)
    assert code == 2 and "--reason" in out["error"]
    assert not (batch_dir / "rework.json").exists()
    code, out = _gate(batch_dir, doc, "--force", "--reason", "用户复核：pass 判定建立在假观察上",
                      capsys=capsys)
    assert code == 0 and out["ok"] and out["forced"]
    record = json.loads((batch_dir / "rework.json").read_text(encoding="utf-8"))
    assert record["reason"] == "用户复核：pass 判定建立在假观察上"
    # 打印的违规与记账的违规是同一份
    assert out["violations"] == record["violations"]
    assert [(v["code"], v.get("overridden")) for v in record["violations"]] == [
        ("pass_case_changed", True)]


def test_pass_case_cannot_be_dropped_and_new_cases_cannot_slip_in(tmp_path, fingerprint, capsys):
    batch_dir = _batch(tmp_path, fingerprint)
    doc = copy.deepcopy(DOC)
    newcomer = copy.deepcopy(doc["cases"][1])
    newcomer["autoid"] = "202609279000010003"
    doc["cases"] = [doc["cases"][1], newcomer]
    code, out = _gate(batch_dir, doc, capsys=capsys)
    assert code == 1
    assert sorted((v["autoid"], v["code"]) for v in out["violations"]) == [
        (PASS_ID, "pass_case_dropped"), ("202609279000010003", "case_not_in_prior_run")]


def test_old_results_fall_back_to_check_points_and_say_so(tmp_path, fingerprint, capsys):
    batch_dir = _batch(tmp_path, fingerprint, with_fingerprints=False)
    prov = {"schema": "ist.excel.provenance", "batch": DOC["batch"], "cases": {
        aid: rework_gate._cp_entries(aid, case)
        for aid, case in ((c["autoid"], c) for c in DOC["cases"])}}
    prov_path = batch_dir / "provenance.json"
    prov_path.write_text(json.dumps(prov, ensure_ascii=False), encoding="utf-8")
    run_path = batch_dir / "run_results.json"
    os.utime(prov_path, (run_path.stat().st_mtime - 60, run_path.stat().st_mtime - 60))
    code, out = _gate(batch_dir, DOC, capsys=capsys)
    assert code == 0 and out["baseline"] == "provenance.json"
    assert "check_point" in out["baseline_note"]
    # provenance.json 在上机之后被重写（emit 先于闸）：不再是上机卷面，不能拿来当基线
    os.utime(prov_path, (run_path.stat().st_mtime + 60, run_path.stat().st_mtime + 60))
    code, out = _gate(batch_dir, DOC, capsys=capsys)
    assert code == 1 and out["baseline"] == "none"
    assert [v["code"] for v in out["violations"]] == ["pass_baseline_missing"]


def test_cases_of_another_batch_are_refused(tmp_path, fingerprint, capsys):
    batch_dir = _batch(tmp_path, fingerprint)
    doc = copy.deepcopy(DOC)
    doc["batch"] = "other_batch"
    code, out = _gate(batch_dir, doc, capsys=capsys)
    assert code == 2 and "other_batch" in out["error"]
