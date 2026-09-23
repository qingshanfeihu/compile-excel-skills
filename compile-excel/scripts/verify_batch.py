#!/usr/bin/env python3
"""verify_batch: case.xlsx 验收报告（pass/fail/totals）。

本地终验（工作流 D4 的本地部分）：
1. 结构检查（ist_emit 真语义：唯一 A-I 表头、defined-name、marker 身份钉死）；
2. 布局检查（Author 行/init 行/步骤行/空行分隔/哨兵）；
3. E/F 合法集检查——**从冻结模板 K-P 列自举**（模板第 2 行自述分组）；
4. 逐 case check_point≥1、found_times 的 G/H/I 硬契约、autoid 唯一；
5. 若能定位 InfoTest 引擎（$IST_ENGINE_ROOT 或同级 InfoTest_Engine），
   追加真契约数据驱动的逐行 E/F/G 校验（最强对拍）；不可用则明示 skip。

上机验证（设备执行）归 InfoTest 引擎，不在本报告范围（见 reference/excel-contract.md）。
用法：python verify_batch.py --xlsx <case.xlsx> [--engine-root <InfoTest_Engine>]
退出码：0 = 全过；1 = 有失败项。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openpyxl import load_workbook  # noqa: E402

from ist_emit.case_ir import FileIR  # noqa: E402,F401 — 路径注册
from ist_emit.excel_contract import (  # noqa: E402
    CONTRACT_MARKER,
    EXECUTION_HEADERS,
    PINNED_CONTRACT_SHA256,
    TEMPLATE_SHA256,
    ExcelContractError,
    resolve_execution_sheet,
)
from ist_emit.xlsx_emit import TEMPLATE_PATH  # noqa: E402

REPORT_SCHEMA = "ist.excel.verify-report"


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def payload(self, path: str) -> dict:
        failures = [c for c in self.checks if not c["ok"]]
        return {
            "schema": REPORT_SCHEMA,
            "path": path,
            "totals": len(self.checks),
            "pass": len(self.checks) - len(failures),
            "fail": len(failures),
            "failures": failures,
            "checks": self.checks,
        }


def _ef_sets_from_template() -> tuple[set[str], dict[str, set[str]]]:
    """从冻结模板 K-P 列自举 E 集与 E→F 集合。

    模板第 2 行自述分组（如 L2="APV_0 / APV_1"），列下方即该组 F 值。
    """
    wb = load_workbook(TEMPLATE_PATH)
    ws, _layout = resolve_execution_sheet(wb, allow_legacy=False)
    e_values: set[str] = set()
    f_map: dict[str, set[str]] = {}
    for row in ws.iter_rows(min_row=3, max_row=12, min_col=11, max_col=16, values_only=True):
        for idx, value in enumerate(row):
            if value is None or not str(value).strip():
                continue
            text = str(value).strip()
            if idx == 0:
                e_values.add(text)
            else:
                group_header = ws.cell(row=2, column=11 + idx).value
                for e_name in str(group_header or "").split("/"):
                    e_name = e_name.strip()
                    if e_name:
                        f_map.setdefault(e_name, set()).add(text)
    wb.close()
    return e_values, f_map


def verify(path: Path, engine_root: str = "") -> dict:
    report = Report()
    wb = load_workbook(path, data_only=True)

    # 1) 真语义结构解析（含 marker 身份钉死）
    try:
        sheet, layout = resolve_execution_sheet(wb, allow_legacy=False)
        report.add("execution-sheet resolve (pinned identity)", True,
                   f"header_row={layout.header_row} data_start={layout.data_start}")
    except ExcelContractError as exc:
        report.add("execution-sheet resolve (pinned identity)", False, str(exc))
        return report.payload(str(path))
    marker_cell = sheet.cell(row=1, column=1).value
    marker_sha = str(sheet.cell(row=1, column=3).value or "")
    report.add("contract marker present", marker_cell == CONTRACT_MARKER,
               f"A1={marker_cell!r}")
    report.add("marker contract sha pinned",
               marker_sha == PINNED_CONTRACT_SHA256, marker_sha[:12] + "…")

    grid = [list(r) for r in sheet.iter_rows(values_only=True)]
    data = [row + [None] * max(0, 9 - len(row)) for row in grid[layout.data_start - 1:]]
    data = [row for row in data if any(v not in (None, "") for v in row[:9])]

    # 2) 布局：首行 Author（C=0），init 行 C=1，case 行 C>=2
    first = data[0] if data else []
    report.add("author row first (C=0)",
               bool(data) and str(first[2]) == "0" and "Author" in str(first[3] or ""))
    stmt_bad = [i for i, row in enumerate(data)
                if row[2] is not None and str(row[2]).strip() not in {"0", "1"}
                and not str(row[2]).isdigit()]
    report.add("stmt_type column discipline (0/1/int>=2)", not stmt_bad,
               f"bad_rows={[data[i][0] or data[i][4] for i in stmt_bad][:5]}")

    # 3) E/F 合法集（模板自举）
    e_values, f_map = _ef_sets_from_template()
    ef_bad: list[str] = []
    for row in data:
        e = str(row[4] or "").strip()
        f = str(row[5] or "").strip()
        if not e:
            continue
        if e not in e_values:
            ef_bad.append(f"E={e}")
            continue
        allowed = f_map.get(e)
        if allowed and f and f not in allowed:
            ef_bad.append(f"E={e} F={f}")
    report.add("E/F membership (template-derived)", not ef_bad,
               f"violations={ef_bad[:5]} known_E={sorted(e_values)}")

    # 4) 逐 case：check_point≥1；found_times 契约；autoid 唯一
    autoids: list[str] = []
    current: dict | None = None
    case_results: list[tuple[str, bool, str]] = []
    for row in data:
        a = str(row[0]).strip() if row[0] is not None else ""
        c = str(row[2]).strip() if row[2] is not None else ""
        if a and c not in ("1", "0", "None") and a != EXECUTION_HEADERS[0]:
            if current is not None:
                case_results.append((current["autoid"], current["cp"] > 0, ""))
            current = {"autoid": a, "cp": 0}
            if a in autoids:
                case_results.append((a, False, "autoid 重复"))
            autoids.append(a)
        e = str(row[4] or "").strip()
        f = str(row[5] or "").strip()
        if current is not None and e == "check_point":
            current["cp"] += 1
            if f == "found_times":
                i_text = str(row[8] or "").strip()
                h_text = str(row[7] or "").strip()
                try:
                    count = int(i_text)
                    ok_ft = count > 0 and str(count) == i_text and not h_text
                except ValueError:
                    ok_ft = False
                if not ok_ft:
                    case_results.append(
                        (current["autoid"], False,
                         f"found_times 契约违规：I={i_text!r} H={h_text!r}"))
    if current is not None:
        case_results.append((current["autoid"], current["cp"] > 0, ""))
    no_cp = [aid for aid, ok, _note in case_results if not ok and aid != "999999999999999"]
    report.add("every case has check_point", not no_cp, f"missing={no_cp}")
    report.add("autoid unique", len(autoids) == len(set(autoids)))
    # InfoTest structural_gate 按全数字 ≥12 位识别用例边界（哨兵除外）
    real_autoids = [a for a in autoids if a != "999999999999999"]
    bad_ids = [a for a in real_autoids if not (a.isdigit() and len(a) >= 12)]
    report.add("autoid >= 12 digits (framework boundary)", not bad_ids,
               f"bad={bad_ids}（生产惯例 18 位）")
    report.add("case count", True, f"cases={len(autoids)} autoids={autoids}")

    wb.close()

    # 5) InfoTest 真契约对拍（可选，最强校验）
    engine = Path(engine_root) if engine_root else _locate_engine()
    if engine is None:
        report.add("infotest reverse check", True,
                   "skip：未定位 InfoTest 引擎（$IST_ENGINE_ROOT 可指定）——"
                   "结构检查已过，G 列内容终验建议在 InfoTest lint 侧兜底")
    else:
        code = _run_reverse_check(engine, path)
        report.add("infotest reverse check (data-driven rows)", code == 0,
                   f"engine={engine} exit={code}")

    return report.payload(str(path))


def _locate_engine() -> Path | None:
    import os

    explicit = os.environ.get("IST_ENGINE_ROOT")
    if explicit:
        path = Path(explicit)
        return path if (path / "main" / "case_compiler").is_dir() else None
    sibling = Path(__file__).resolve().parents[4] / "InfoTest_Engine"
    return sibling if (sibling / "main" / "case_compiler").is_dir() else None


def _run_reverse_check(engine: Path, target: Path) -> int:
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "tests" / "reverse_check_infotest.py"),
         str(target)],
        capture_output=True, text=True, timeout=180,
        env={**__import__("os").environ, "IST_ENGINE_ROOT": str(engine)},
    )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="case.xlsx 验收报告")
    parser.add_argument("--xlsx", required=True, help="待验 case.xlsx")
    parser.add_argument("--engine-root", default="", help="InfoTest_Engine 根（缺省自动探测）")
    args = parser.parse_args()

    result = verify(Path(args.xlsx), args.engine_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
