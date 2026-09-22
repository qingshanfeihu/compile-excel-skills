#!/usr/bin/env python3
"""用 InfoTest 真引擎反向校验 skill 产物（emit 对拍，工作流 D1）。

跑法（在 InfoTest_Engine 根目录、用其 venv）：
    cd /path/to/InfoTest_Engine
    .venv311/bin/python3 /path/to/compile-excel/tests/reverse_check_infotest.py <case.xlsx>...

校验项（与 InfoTest 今天编译上机的门槛同源）：
1. resolve_execution_sheet(allow_legacy=False)：真契约数据驱动的工作簿身份
   （marker 版本 + contract_sha256 + defined-name + 唯一 A-I 表头）；
2. 逐行 E/F 契约项校验（contract_entry + validate_g_for_entry）：
   E 对象合法、F 方法已启用、G 参数语法按签名绑定闭合；
3. found_times 行的 G/H/I 硬契约；
4. 结构统计（case 数、check_point 数）与 skill 侧 readback 对齐。

输出 JSON：{"ok": bool, "checks": [...], "row_errors": [...]}。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# InfoTest 引擎根：优先 $IST_ENGINE_ROOT，缺省取本仓同级目录（只读引用，勿改引擎）
INFOTEST_ROOT = Path(
    os.environ.get("IST_ENGINE_ROOT")
    or (Path(__file__).resolve().parents[4] / "InfoTest_Engine")
)
sys.path.insert(0, str(INFOTEST_ROOT))

from main.case_compiler.excel_contract import (  # noqa: E402
    ExcelContractError,
    contract_entry,
    load_excel_contract,
    resolve_execution_sheet,
    validate_g_for_entry,
)
from main.case_compiler.case_ir import parse_found_times_cells  # noqa: E402
from openpyxl import load_workbook  # noqa: E402


def reverse_check(path: str) -> dict:
    contract = load_excel_contract()
    wb = load_workbook(path, data_only=True)
    errors: list[str] = []
    checks: list[dict] = []

    sheet, layout = resolve_execution_sheet(wb, allow_legacy=False)
    checks.append({
        "check": "resolve_execution_sheet(real contract, no legacy)",
        "ok": True,
        "header_row": layout.header_row,
        "data_start": layout.data_start,
    })

    grid = [list(r) for r in sheet.iter_rows(values_only=True)]
    autoids, n_check = [], 0
    case_begin = False
    for row in grid:
        a = row[0] if len(row) > 0 else None
        c = row[2] if len(row) > 2 else None
        e = row[4] if len(row) > 4 else None
        if a is not None and str(a).strip() == layout.header_anchor:
            case_begin = True
            continue
        if not case_begin:
            continue
        if a is not None and str(c) not in ("1", "0", "None"):
            autoids.append(str(a))
        if e is None or not str(e).strip():
            continue
        f = str(row[5] or "").strip()
        g = row[6] if len(row) > 6 else None
        h = row[7] if len(row) > 7 else None
        i = row[8] if len(row) > 8 else None
        if e == "check_point":
            n_check += 1
        entry = contract_entry(str(e), f, contract)
        if entry is None:
            errors.append(f"E={e!r} F={f!r}: not in contract")
            continue
        try:
            validate_g_for_entry(entry, g, contract)
        except ExcelContractError as exc:
            errors.append(f"E={e!r} F={f!r} G={str(g)[:60]!r}: {exc}")
            continue
        if e == "check_point" and f == "found_times":
            try:
                parse_found_times_cells(g, h, i)
            except ValueError as exc:
                errors.append(f"found_times E/F row: {exc}")
    wb.close()

    checks.append({"check": "row-level E/F/G contract validation", "ok": not errors})
    return {
        "path": path,
        "ok": not errors,
        "case_count": len(autoids),
        "autoids": autoids,
        "check_point_count": n_check,
        "checks": checks,
        "row_errors": errors,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    results = [reverse_check(p) for p in sys.argv[1:]]
    ok = all(r["ok"] for r in results)
    print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
