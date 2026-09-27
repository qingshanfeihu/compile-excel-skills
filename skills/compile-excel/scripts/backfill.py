#!/usr/bin/env python3
"""backfill: 上机结果回填 —— 把一次上机的逐 case 判定追加进批足迹（footprint.jsonl）。

对齐 ist-verify 的回填口径：
- 每个 case 一行，判定原样来自 run_results.json（框架结果库的 pass / fail / not_run）；
  只有真 PASS 才算写回记录，fail / not_run 带着失败断言留给返工环，不美化。
- 回填不改 case.xlsx（E/F/G/H/I 契约与 marker 身份钉死），不改 cases.json（作者 IR）。
- 每行带运行身份，全部取自 run_results.json：网关对账过的工作簿 SHA-256（上机跑的就是它）、
  task_id、投递与取回时间、结果通道。回执缺 xlsx_sha256 时才按工作区解析工作簿路径现算
  （run_results.json 里的 xlsx 是相对工作区根的路径，工作区根从回执所在目录往上找），不按当前目录。
- 同一次上机（同一 task_id）已经回填过就不再追加，足迹里一次运行只有一份。

用法：
  python3 scripts/backfill.py --results <workspace>/compile_outputs/<batch>/run_results.json
产出/更新（与 run_results.json 同目录）：
  footprint.jsonl   追加式足迹账本，一行一 case 判定
退出码：0 = 回填完成（或这次运行已回填过）；2 = 输入非法。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RESULTS_SCHEMA = "ist.excel.device-run-result"
FOOTPRINT_SCHEMA = "ist.excel.device-footprint"
STATE_DIR = ".compile-excel"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _resolve_xlsx(recorded: str, results_path: Path) -> Path | None:
    """run_results.json 的 xlsx 相对工作区根；工作区根 = 回执所在目录往上第一个带 .compile-excel/ 的目录。"""
    if not recorded:
        return None
    path = Path(recorded).expanduser()
    if path.is_absolute():
        return path if path.is_file() else None
    for root in (results_path.parent, *results_path.parent.parents):
        if (root / STATE_DIR).is_dir():
            candidate = root / path
            return candidate if candidate.is_file() else None
    candidate = results_path.parent / path.name  # 回执与工作簿同目录（run_device 就是这么写的）
    return candidate if candidate.is_file() else None


def _already_backfilled(out_path: Path, task_id: str) -> bool:
    if not task_id or not out_path.is_file():
        return False
    for line in out_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and (rec.get("run") or {}).get("task_id") == task_id:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="上机结果回填足迹")
    ap.add_argument("--results", required=True, help="run_device.py / cex_case_results 写的 run_results.json")
    args = ap.parse_args()

    results_path = Path(args.results).expanduser().resolve()
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": f"results 不存在: {results_path}"},
                         ensure_ascii=False))
        return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": f"results 不可读: {exc}"}, ensure_ascii=False))
        return 2
    if not isinstance(data, dict) or data.get("schema") != RESULTS_SCHEMA:
        schema = data.get("schema") if isinstance(data, dict) else None
        print(json.dumps({"ok": False, "error": f"schema 不符: {schema!r}"}, ensure_ascii=False))
        return 2
    cases = data.get("cases")
    if not isinstance(cases, list) or not all(isinstance(c, dict) and c.get("autoid") for c in cases):
        print(json.dumps({"ok": False, "error": "run_results.json 的 cases 不是带 autoid 的对象数组"},
                         ensure_ascii=False))
        return 2

    xlsx_sha = str(data.get("xlsx_sha256") or "")
    sha_source = "run_results"
    if not xlsx_sha:
        xlsx = _resolve_xlsx(str(data.get("xlsx") or ""), results_path)
        xlsx_sha = _sha256(xlsx) if xlsx is not None else ""
        sha_source = "workbook" if xlsx is not None else "unavailable"
    task_id = str(data.get("task_id") or "")
    run_identity = {
        "task_id": task_id or None,
        "xlsx": data.get("xlsx"),
        "xlsx_sha256": xlsx_sha,
        "xlsx_sha256_source": sha_source,
        "submitted": data.get("submitted"),
        "finished": data.get("finished"),
        "result_channel": data.get("result_channel"),
        "batch": data.get("batch"),
    }

    out_path = results_path.parent / "footprint.jsonl"
    totals = data.get("totals") or {}
    summary = {"true_pass": totals.get("pass", 0), "fail": totals.get("fail", 0),
               "not_run": totals.get("not_run", 0)}
    if _already_backfilled(out_path, task_id):
        print(json.dumps({"ok": True, "footprint": str(out_path), "appended": 0,
                          "note": f"task {task_id} 已经回填过，不重复追加", **summary},
                         ensure_ascii=False))
        return 0

    written = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for case in cases:
            verdict = str(case.get("verdict") or "not_run")
            rec = {
                "schema": FOOTPRINT_SCHEMA,
                "autoid": str(case["autoid"]),
                "verdict": verdict,
                "true_pass": verdict == "pass",
                "failed_checks": list(case.get("failed_checks") or []),
                "attribution": (case.get("attribution") or {}).get("layer"),
                "note": case.get("note"),
                "run": run_identity,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    print(json.dumps({"ok": True, "footprint": str(out_path), "appended": written, **summary},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
