"""backfill：运行身份取自 run_results.json（评审：started 恒为 null、xlsx 按当前目录解析、
check_points / cli_errors 两个字段在回执里根本不存在）。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "compile-excel" / "scripts" / "backfill.py"


def _workspace(tmp_path: Path, *, with_sha: bool) -> tuple[Path, Path, bytes]:
    ws = tmp_path / "project"
    (ws / ".compile-excel").mkdir(parents=True)
    batch = ws / "compile_outputs" / "b1"
    batch.mkdir(parents=True)
    workbook = b"not really a workbook, only its bytes matter here"
    (batch / "case.xlsx").write_bytes(workbook)
    run = {"schema": "ist.excel.device-run-result", "xlsx": "compile_outputs/b1/case.xlsx",
           "batch": "b1", "task_id": "cex_sdns_1_2", "result_channel": "ready",
           "submitted": "2026-09-27T10:00:00+08:00", "finished": "2026-09-27T10:03:00+08:00",
           "cases": [{"autoid": "202609270000000001", "verdict": "pass"},
                     {"autoid": "202609270000000002", "verdict": "fail",
                      "failed_checks": ["#### Fail Num 1: fail to find 'x' in:\nshow y\nz"],
                      "attribution": {"layer": "undetermined"}}],
           "totals": {"cases": 2, "pass": 1, "fail": 1, "not_run": 0}}
    if with_sha:
        run["xlsx_sha256"] = "ab" * 32  # 网关对账过的、真上机那份工作簿的摘要
    results = batch / "run_results.json"
    results.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    return ws, results, workbook


def _backfill(results: Path, cwd: Path) -> dict:
    proc = subprocess.run([sys.executable, str(SCRIPT), "--results", str(results)],
                          capture_output=True, text=True, cwd=cwd, timeout=60, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def _lines(results: Path) -> list[dict]:
    text = (results.parent / "footprint.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_run_identity_and_failed_checks_come_from_the_run_results(tmp_path):
    _ws, results, _ = _workspace(tmp_path, with_sha=True)
    out = _backfill(results, cwd=tmp_path)
    assert out["appended"] == 2 and out["true_pass"] == 1 and out["not_run"] == 0
    first, second = _lines(results)
    assert first["run"]["xlsx_sha256"] == "ab" * 32
    assert first["run"]["task_id"] == "cex_sdns_1_2"
    assert first["run"]["submitted"] == "2026-09-27T10:00:00+08:00"
    assert first["true_pass"] is True and second["true_pass"] is False
    assert second["failed_checks"] and second["attribution"] == "undetermined"
    assert "check_points" not in second and "cli_errors" not in second


def test_workbook_path_resolves_against_the_workspace_not_the_cwd(tmp_path):
    _ws, results, workbook = _workspace(tmp_path, with_sha=False)
    _backfill(results, cwd=tmp_path)  # 当前目录不是工作区根
    run = _lines(results)[0]["run"]
    assert run["xlsx_sha256"] == hashlib.sha256(workbook).hexdigest()
    assert run["xlsx_sha256_source"] == "workbook"


def test_the_same_run_is_backfilled_once(tmp_path):
    _ws, results, _ = _workspace(tmp_path, with_sha=True)
    _backfill(results, cwd=tmp_path)
    again = _backfill(results, cwd=tmp_path)
    assert again["appended"] == 0 and len(_lines(results)) == 2


def test_broken_cases_are_not_true_passes_and_keep_their_reason(tmp_path):
    ws, results, _workbook = _workspace(tmp_path, with_sha=True)
    run = json.loads(results.read_text(encoding="utf-8"))
    run["cases"][0] = {"autoid": "202609270000000001", "verdict": "broken",
                       "recorded_result": "pass", "broken_reason": "no closing in the case log"}
    run["totals"] = {"cases": 2, "pass": 0, "fail": 1, "broken": 1, "not_run": 0}
    run["rc"], run["run_dir"] = 124, "2026-09-27-10:00:00B"
    results.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    out = _backfill(results, cwd=tmp_path)
    assert out["true_pass"] == 0 and out["broken"] == 1
    line = _lines(results)[0]
    assert line["verdict"] == "broken" and line["true_pass"] is False
    assert line["broken_reason"] == "no closing in the case log"
    assert line["run"]["rc"] == 124 and line["run"]["run_dir"] == "2026-09-27-10:00:00B"
