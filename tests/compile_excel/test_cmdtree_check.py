"""cmdtree_check：大写键（cex_author_emit 出件）、init_commands、多行 cmds_config、执行器关键字与
交互应答、root shell 的 cmd、no 形态按自己的头判——都与引擎命令存在性判据同一解释。

评审复现：出件的 cases.json 用大写 E/F/G，旧脚本一行都没查（checked 0）却报 ok；init 里的
假命令与 cmds_config 第二行的假命令也都漏过。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "compile-excel" / "scripts"
sys.path.insert(0, str(SCRIPTS))

PROJECTION = {"version": "9.9", "heads": {
    "show version": {"src": "xml", "pmax": 0},
    "show slb real http": {"src": "xml", "pmax": 1},
    "slb real http": {"src": "xml", "args": [{"type": "STRING"}, {"type": "IPADDR"}, {"type": "U16"}]},
    "no slb real http": {"src": "xml", "args": [{"type": "STRING"}]},
    "clear ssl host": {"src": "xml", "args": [{"type": "STRING"}]},
}}


def _run(tmp_path: Path, doc: dict) -> tuple[int, dict]:
    projection = tmp_path / "vendor_stdlib_9.9_101.json"
    projection.write_text(json.dumps(PROJECTION), encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "CEX_WORKSPACE"}
    env["HOME"] = str(tmp_path)
    proc = subprocess.run([sys.executable, str(SCRIPTS / "cmdtree_check.py"), "--cases", str(cases),
                           "--projection", str(projection)],
                          capture_output=True, text=True, env=env, timeout=60, check=False)
    return proc.returncode, json.loads(proc.stdout)


def _unknown(report: dict) -> list[tuple[str, str]]:
    return [(u["autoid"], u["command"]) for u in report["unknown"]]


@pytest.mark.parametrize("upper", [False, True], ids=["hand-written", "emitted"])
def test_both_key_cases_init_and_every_line_of_cmds_config_are_checked(tmp_path, upper):
    def step(e, f, g):
        return {"E": e, "F": f, "G": g} if upper else {"e": e, "f": f, "g": g}

    doc = {"batch": "t1", "init_commands": ["slb bogushead foo bar"], "cases": [
        {"autoid": "202609260000000001", "steps": [
            step("APV_0", "cmd_config", "slb real http r1 10.0.0.1 80"),
            step("APV_0", "cmds_config", "show version\nslb frobnicate 1 2"),
            step("APV_0", "cmd_config", "show slb real http"),
            step("check_point", "found", "r1")]}]}
    code, report = _run(tmp_path, doc)
    assert code == 1
    assert report["checked"] == 5
    assert _unknown(report) == [("init", "slb bogushead foo bar"),
                                ("202609260000000001", "slb frobnicate 1 2")]


def test_init_commands_grouped_by_device_are_checked_on_every_device(tmp_path):
    doc = {"batch": "t5", "init_commands": {"APV_0": ["slb bogushead foo bar"],
                                            "APV_1": ["slb frobnicate 1 2"]}, "cases": [
        {"autoid": "202609260000000005", "steps": [
            {"e": "APV_0", "f": "cmd_config", "g": "show slb real http"},
            {"e": "check_point", "f": "found", "g": "r1"}]}]}
    code, report = _run(tmp_path, doc)
    assert code == 1
    assert _unknown(report) == [("init", "slb bogushead foo bar"), ("init", "slb frobnicate 1 2")]


def test_executor_keywords_prompt_answers_and_no_forms_are_not_false_misses(tmp_path):
    """cex_author_emit 的真实出件：`,prompt=abort:` 之后的 YES、`,timeout=`、no 形态自己的参数契约。"""
    doc = {"batch": "t2", "cases": [{"autoid": "202609260000000002", "steps": [
        {"E": "APV_0", "F": "cmd_config", "G": "slb real http r1 10.0.0.1 80,timeout=60"},
        {"E": "APV_0", "F": "cmd_config", "G": 'clear ssl host "h1",prompt=abort:'},
        {"E": "APV_0", "F": "cmd_config", "G": "YES"},
        {"E": "APV_0", "F": "cmd_config", "G": "no slb real http r1"},
        {"E": "APV_0", "F": "cmd_config", "G": "YES"},
        {"E": "check_point", "F": "found", "G": "x"}]}]}
    code, report = _run(tmp_path, doc)
    # 只有最后那个 YES 前面没有 prompt=，它是一条（不存在的）命令
    assert _unknown(report) == [("202609260000000002", "YES")]
    assert report["checked"] == 4 and code == 1


def test_root_shell_cmd_is_not_judged_against_the_cli_tree(tmp_path):
    """F=cmd 在设备 Linux root shell 里跑（框架 APV.cmd → APV_Root）：ls/cat 不是 CLI，不能报未知命令；
    把 CLI 命令交给 cmd 则给警告。"""
    doc = {"batch": "t3", "cases": [{"autoid": "202609260000000003", "steps": [
        {"e": "APV_0", "f": "cmd", "g": "cat /var/log/messages"},
        {"e": "check_point", "f": "found", "g": "kernel"},
        {"e": "APV_0", "f": "cmd", "g": "show version"},
        {"e": "check_point", "f": "found", "g": "Version:"}]}]}
    code, report = _run(tmp_path, doc)
    assert code == 0 and report["checked"] == 0 and report["unknown"] == []
    assert any("show version" in w and "cmd_config" in w for w in report["warnings"])


def test_xlsx_input_checks_the_shared_init_row(tmp_path):
    pytest.importorskip("openpyxl")
    doc = {"batch": "t4", "init_commands": ["slb bogushead foo bar"], "cases": [
        {"autoid": "202609260000000004", "steps": [
            {"e": "APV_0", "f": "cmds_config", "g": "show version\nslb frobnicate 1 2"},
            {"e": "APV_0", "f": "cmd_config", "g": "show version"},
            {"e": "check_point", "f": "found", "g": "Version:"}]}]}
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "out"
    compiled = subprocess.run([sys.executable, str(SCRIPTS / "compile_excel.py"), "--cases", str(cases),
                               "--out", str(out)], capture_output=True, text=True, timeout=120, check=False)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    projection = tmp_path / "vendor_stdlib_9.9_101.json"
    projection.write_text(json.dumps(PROJECTION), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPTS / "cmdtree_check.py"), "--xlsx",
                           str(out / "t4" / "case.xlsx"), "--projection", str(projection)],
                          capture_output=True, text=True, timeout=60, check=False)
    report = json.loads(proc.stdout)
    assert proc.returncode == 1
    assert _unknown(report) == [("init", "slb bogushead foo bar"),
                                ("202609260000000004", "slb frobnicate 1 2")]


def test_command_lines_match_the_engine_reading():
    """脚本的命令行解释与引擎 emit_xlsx_tool._apv_command_lines_for_step 逐行一致（引擎可导入时对拍）。"""
    try:
        from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import (
            _apv_command_lines_for_step,
        )
    except ImportError:
        pytest.skip("引擎的 emit_xlsx_tool 在这个解释器里导入不了")
    import cmdtree_check

    steps = [{"E": "APV_0", "F": "cmd_config", "G": 'clear ssl host "h1",prompt=abort:'},
             {"E": "APV_0", "F": "cmd_config", "G": "YES"},
             {"E": "APV_0", "F": "cmds_config", "G": "a b\n\n c d "},
             {"E": "APV_0", "F": "cmd_config", "G": "sdns on,timeout=60"},
             {"E": "APV_0", "F": "cmd_config", "G": "NO"}]
    cli, _shell = cmdtree_check._command_lines([("x", steps)])
    engine = [line for index in range(len(steps)) for line in _apv_command_lines_for_step(steps, index)]
    assert [item["command"] for item in cli] == engine
