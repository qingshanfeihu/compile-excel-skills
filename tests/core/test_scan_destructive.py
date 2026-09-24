"""自毁命令扫描：规则只从 grammar 读；读不到就拒绝；E 列 APV 的每一步都查，不按 F 列分辖区。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from conftest import REPO_ROOT

from cex_core.scan_destructive import (
    DestructiveRulesUnavailable,
    load_patterns,
    scan_lines,
    scan_workbook,
)

GRAMMAR = {"destructive_commands": {"patterns": [
    r"^clear\s+config\s+all\b", r"\breboot\b", r"\bshutdown\b"]}}


def test_fails_closed_without_rules(tmp_path):
    for grammar in ({}, {"destructive_commands": {"patterns": []}},
                    {"destructive_commands": {"patterns": ["("]}}, tmp_path / "missing.json"):
        with pytest.raises(DestructiveRulesUnavailable):
            load_patterns(grammar)


def test_scan_lines_hits_and_misses():
    patterns = load_patterns(GRAMMAR)
    findings = scan_lines([("a", "clear config all"), ("b", "system reboot noninteractive"),
                           ("c", "clear slb real r1"), ("d", "no slb real http r1")], patterns)
    assert [f["where"] for f in findings] == ["a", "b"]


def test_scan_workbook_checks_every_apv_step_regardless_of_method(tmp_path):
    template = REPO_ROOT / "cex_core" / "templates" / "case_template.xlsx"
    target = tmp_path / "case.xlsx"
    shutil.copy2(template, target)
    wb = load_workbook(target)
    from cex_core.ist_emit.excel_contract import resolve_execution_sheet

    ws, _ = resolve_execution_sheet(wb, allow_legacy=False)
    start = ws.max_row + 1
    rows = [("APV_1", "cmd", "system reboot noninteractive"),
            ("APV_1", "cmd_config", "slb real http r1 10.0.0.1 80\nclear config all"),
            ("check_point", "found", "reboot"),
            ("APV_1", "cmd_config", "clear slb real r1")]
    for offset, (device, method, command) in enumerate(rows):
        ws.cell(row=start + offset, column=5, value=device)
        ws.cell(row=start + offset, column=6, value=method)
        ws.cell(row=start + offset, column=7, value=command)
    wb.save(target)
    findings = scan_workbook(target, GRAMMAR)
    assert [f["command"] for f in findings] == ["system reboot noninteractive", "clear config all"]


def test_repo_grammar_is_not_bundled(tmp_path):
    """规则不写在 cex_core 里：没有 grammar 文件就没有规则。"""
    assert not list(Path(REPO_ROOT / "cex_core").rglob("domain_grammar*.json"))
