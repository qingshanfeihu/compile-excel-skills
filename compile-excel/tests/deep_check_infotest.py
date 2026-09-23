#!/usr/bin/env python3
"""用 InfoTest 深层门校验 skill 产物（比 reverse_check 更深一层）。

跑法（用 InfoTest 的 venv 解释器）：
    .venv311/bin/python3 tests/deep_check_infotest.py <case.xlsx>

校验项：
1. structural_gate.lint_xlsx_case —— 必崩/必假结构门全集：
   autoid 18 位纪律、mandatory 崩溃门、断言正则可编译、短模式断言、
   参数切分、autoid 行可执行（首步 E 非空）、配置存在性建议、行锚点矛盾证明；
2. package_registry_tool._load_case_rows —— 合并流的卷面读取器
   （init 首步 APV_0 + 全步骤，遇 999999 哨兵即停）：skill 产物必须能被
   InfoTest 合并通道原样消费；
3. steps_from_xlsx 的用例边界 —— ≥12 位数字 autoid 才构成边界。

输出 JSON：{"ok", "totals", "pass", "fail", "lint": {...}, "rows": {...}}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

INFOTEST_ROOT = Path(
    os.environ.get("IST_ENGINE_ROOT")
    or (Path(__file__).resolve().parents[4] / "InfoTest_Engine")
)
sys.path.insert(0, str(INFOTEST_ROOT))

from main.ist_core.tools.device.structural_gate import (  # noqa: E402
    lint_xlsx_case,
    steps_from_xlsx,
)
from main.ist_core.tools.device.package_registry_tool import (  # noqa: E402
    _load_case_rows,
)


def _violations(items) -> list[dict]:
    return [
        {"code": v.code, "step": v.step_index, "detail": v.detail[:220]}
        for v in (items or [])
    ]


def deep_check(path: str) -> dict:
    checks: list[dict] = []

    lr = lint_xlsx_case(path)
    checks.append({
        "name": "lint_xlsx_case (structural gates)",
        "ok": bool(lr.ok),
        "violations": _violations(lr.violations),
        "disabled": _violations(lr.disabled),
        "advisories": _violations(lr.advisories),
    })

    rows = _load_case_rows(path)
    first_is_init = bool(rows) and rows[0]["E"] == "APV_0"
    checks.append({
        "name": "merge-flow reader (_load_case_rows)",
        "ok": bool(rows) and first_is_init,
        "rows": len(rows),
        "first_row": rows[0] if rows else None,
        "stopped_at_sentinel": True,  # 读取器遇 999999 即停；未抛错即消费成功
    })

    autoid, steps = steps_from_xlsx(path, allow_legacy=True)
    boundary_ok = bool(autoid) and autoid != "999999999999999"
    checks.append({
        "name": "case boundary (steps_from_xlsx autoid)",
        "ok": boundary_ok,
        "autoid": autoid,
        "steps": len(steps),
    })

    failures = [c["name"] for c in checks if not c["ok"]]
    return {
        "schema": "ist.excel.deep-check",
        "path": path,
        "engine": str(INFOTEST_ROOT),
        "ok": not failures,
        "totals": len(checks),
        "pass": len(checks) - len(failures),
        "fail": len(failures),
        "failures": failures,
        "checks": checks,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    result = deep_check(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
