"""verify_batch：悬空断言（评审复现：三种上机必崩的写法旧版全绿）。

断言读框架 result，result 只由本案最近一条不带 H 的步骤给出：案首就是断言、前面每步都带 H、
或最近那条是 cmds_config / time::sleep（返回 None）——框架 preflight 或运行期抛错，整卷后面的案都不跑。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "compile-excel" / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("openpyxl")

from verify_batch import _dangling_assertions  # noqa: E402

AID = "202609270000000001"


def _row(autoid="", e="", f="", g="", h="", i="", c=""):
    return [autoid or None, None, c or None, None, e, f, g, h or None, i or None]


def _case(*steps):
    rows = [_row(AID, *steps[0], c="2")]
    rows.extend(_row("", *step) for step in steps[1:])
    return rows


@pytest.mark.parametrize("steps", [
    [("check_point", "found", "Build")],                                        # 案首就是断言
    [("APV_0", "cmd_config", "show version", "v1"), ("check_point", "found", "Build")],  # 前面只有带 H 的步
    [("APV_0", "cmds_config", "slb a\nslb b"), ("check_point", "found", "a")],  # cmds_config 返回 None
    [("APV_0", "cmd_config", "show version"), ("time", "sleep", "3"),
     ("check_point", "found", "Version:")],                                      # sleep 返回 None
    [("APV_0", "cmd_config", "show version"), ("APV_0", "cmd_enable", "show x"),
     ("check_point", "found_times", "x", "", "2")],                              # found_times 永远读 result
], ids=["no-step", "only-h", "cmds_config", "sleep", "cmd_enable"])
def test_dangling_shapes_are_rejected(steps):
    assert _dangling_assertions(_case(*steps))


@pytest.mark.parametrize("steps", [
    [("APV_0", "cmd_config", "show version"), ("check_point", "found", "Version:"),
     ("check_point", "not_found", "Error")],                                     # 同一回显上多条断言
    [("APV_0", "cmd_config", "show session", "v1"), ("APV_0", "cmd_config", "show session"),
     ("check_point", "abs_found", "", "v1")],                                    # 捕获比对三步式
    [("test_env", "routerb", "curl -s http://172.16.32.70/"), ("check_point", "found", "IST")],
    [("APV_0", "cmd", "cat /var/log/messages"), ("check_point", "found", "kernel")],  # root shell 回显
    [("APV_0", "cmd_config", "show a", "v1"), ("APV_0", "cmds_config", "x\ny"),
     ("check_point", "found", "", "", "v1")],                                    # 带 I 读寄存器
], ids=["multi-assert", "capture-compare", "test_env", "root-shell-cmd", "register-read"])
def test_assertions_with_an_observation_pass(steps):
    assert _dangling_assertions(_case(*steps)) == []


def test_state_does_not_leak_across_cases():
    rows = _case(("APV_0", "cmd_config", "show version"), ("check_point", "found", "Version:"))
    rows.append(_row("202609270000000002", "check_point", "found", "Version:", c="2"))
    assert [item.split(":")[0] for item in _dangling_assertions(rows)] == ["202609270000000002"]


def test_review_repro_fails_static_verification(tmp_path):
    doc = {"batch": "dangle", "cases": [
        {"autoid": "202609260000000012", "steps": [
            {"e": "APV_0", "f": "cmd_config", "g": "show version", "h": "v1"},
            {"e": "check_point", "f": "found", "g": "Build"}]},
        {"autoid": "202609260000000013", "steps": [
            {"e": "check_point", "f": "found", "g": "Build"}]}]}
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(doc), encoding="utf-8")
    compiled = subprocess.run([sys.executable, str(SCRIPTS / "compile_excel.py"), "--cases", str(cases),
                               "--out", str(tmp_path / "out")], capture_output=True, text=True,
                              timeout=120, check=False)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    verified = subprocess.run([sys.executable, str(SCRIPTS / "verify_batch.py"), "--xlsx",
                               str(tmp_path / "out" / "dangle" / "case.xlsx")],
                              capture_output=True, text=True, timeout=120, check=False)
    report = json.loads(verified.stdout)
    assert verified.returncode == 1
    failed = {c["name"]: c["detail"] for c in report["failures"]}
    detail = failed["every assertion reads an observation echo (no dangling check_point)"]
    assert "202609260000000012" in detail and "202609260000000013" in detail
