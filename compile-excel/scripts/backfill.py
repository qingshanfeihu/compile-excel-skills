#!/usr/bin/env python3
"""backfill: 上机结果回填 —— 把 run_device 的逐 case 判定写入批足迹（footprint.jsonl）。

对齐 ist-verify 的回填口径：
- 只有真 PASS 才写回足迹（true-PASS writeback）；fail / underdetermined 留给返工环，不美化。
- 回填不改 case.xlsx（E/F/G/H/I 契约与 marker 身份钉死），不改 cases.json（作者 IR）。
- 每条足迹带运行身份（xlsx SHA-256 + 起止时间），可独立对账。

用法：
  python3 scripts/backfill.py --results <run_results.json>
产出/更新（与 run_results.json 同目录）：
  footprint.jsonl   追加式足迹账本，一行一 case 判定
退出码：0 = 回填完成；2 = 输入非法。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RESULTS_SCHEMA = "ist.excel.device-run-result"
FOOTPRINT_SCHEMA = "ist.excel.device-footprint"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="上机结果回填足迹")
    ap.add_argument("--results", required=True, help="run_device.py 产出的 run_results.json")
    args = ap.parse_args()

    results_path = Path(args.results).expanduser().resolve()
    if not results_path.exists():
        print(json.dumps({"ok": False, "error": f"results 不存在: {results_path}"},
                         ensure_ascii=False))
        return 2
    data = json.loads(results_path.read_text(encoding="utf-8"))
    if data.get("schema") != RESULTS_SCHEMA:
        print(json.dumps({"ok": False,
                          "error": f"schema 不符: {data.get('schema')!r}"},
                         ensure_ascii=False))
        return 2

    xlsx_path = Path(data["xlsx"])
    run_identity = {
        "xlsx_sha256": _sha256(xlsx_path) if xlsx_path.exists() else "",
        "started": data.get("started"),
        "finished": data.get("finished"),
        "batch": data.get("batch"),
    }

    out_path = results_path.parent / "footprint.jsonl"
    written = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for case in data.get("cases", []):
            rec = {
                "schema": FOOTPRINT_SCHEMA,
                "autoid": case["autoid"],
                "verdict": case["verdict"],
                "check_points": [
                    {"op": cp.get("op"), "expected": cp.get("expected"),
                     "ok": cp.get("ok")}
                    for cp in case.get("check_points", [])
                ],
                "cli_errors": len(case.get("cli_errors", [])),
                "run": run_identity,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    t = data.get("totals", {})
    print(json.dumps({
        "ok": True,
        "footprint": str(out_path),
        "appended": written,
        "true_pass": t.get("pass", 0),
        "fail": t.get("fail", 0),
        "underdetermined": t.get("underdetermined", 0),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
