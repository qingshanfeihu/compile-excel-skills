#!/usr/bin/env python3
"""rework_gate: 返工纪律闸 —— 重派集 ⊆ fail 集，pass 案锁卷面（镜像引擎 merge 节点口径）。

引擎数据层规则（EngineLedger 迁移合法性表）的 skill 版：
- 上一轮 verdict=pass 的 case，本轮不得重编（改动即违反——pass 意味着卷面已验证，
  重编等于撕掉已验证事实；发现 pass 判定本身有假才允许整批判废重来，走 --force）；
- 本轮重派集（内容有变化的 case）必须 ⊆ 上一轮 fail 集；
- 闸通过时写 rework.json（轮次账：fail 集 / 重派集 / 保留 pass 集），供审计。

用法（同一 batch 目录返工前跑）：
  python3 scripts/rework_gate.py --batch-dir compile_outputs/<batch> --cases cases.json
  python3 scripts/rework_gate.py --batch-dir ... --cases ... --force   # 整批判废重来
退出码：0 = 闸通过（或首轮无历史）；1 = 违反纪律；2 = 输入缺失/非法。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compile_excel import _SOURCE_KINDS, _step_field  # noqa: E402

REWORK_SCHEMA = "ist.excel.rework-record"


def _cp_entries(autoid: str, case: dict) -> list[dict]:
    """case 的 check_point 来源记录，与 compile_excel._build_provenance 同型。"""
    out = []
    # 手写 cases.json 用小写 e/f/g，cex_author_emit 产出的用大写 E/F/G：两种都认，
    # 否则编写阶段的用例一律读不到 check_point，上轮 pass 的案全被误判"内容变化"。
    for s in case.get("steps", []):
        if str(_step_field(s, "e") or "").strip() != "check_point":
            continue
        src = s.get("source") or {}
        kind = str(src.get("kind") or "").strip().lower()
        ref = str(src.get("ref") or "").strip()
        if kind not in _SOURCE_KINDS or not ref:
            kind, ref = "author-verbatim", f"mindmap:{autoid}"
        out.append({
            "E": "check_point",
            "F": str(_step_field(s, "f") or ""),
            "G": str(_step_field(s, "g") or ""),
            "source": {"kind": kind, "ref": ref},
        })
    return out


def _entries_fp(entries: list) -> str:
    return hashlib.sha256(
        json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _prior_fingerprints(prov_path: Path) -> dict[str, str]:
    """从 provenance.json 取上一轮每 case 的步骤指纹（无则空——首轮语义）。"""
    if not prov_path.is_file():
        return {}
    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for autoid, entries in (prov.get("cases") or {}).items():
        if isinstance(entries, list):
            blob = json.dumps(entries, ensure_ascii=False, sort_keys=True)
            out[str(autoid)] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="返工纪律闸")
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--force", action="store_true",
                    help="整批判废重来（记录在案，不静默）")
    args = ap.parse_args()

    batch_dir = Path(args.batch_dir).expanduser().resolve()
    cases_path = Path(args.cases).expanduser().resolve()
    if not cases_path.is_file():
        print(json.dumps({"ok": False, "error": f"cases 不存在: {cases_path}"},
                         ensure_ascii=False))
        return 2
    try:
        doc = json.loads(cases_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"cases JSON 解析失败: {exc}"},
                         ensure_ascii=False))
        return 2

    run_path = batch_dir / "run_results.json"
    prov_path = batch_dir / "provenance.json"
    if not run_path.is_file():
        # 首轮（无上机历史）——闸恒通过，写 round 1 记录
        record = {"schema": REWORK_SCHEMA, "round": 1, "first_round": True,
                  "fail_set": [], "redispatch_set": [], "kept_pass": [],
                  "violations": []}
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "rework.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"ok": True, "round": 1, "first_round": True,
                          "gate": "rework.json written"},
                         ensure_ascii=False))
        return 0

    try:
        prior = json.loads(run_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": f"run_results.json 不可读: {exc}"},
                         ensure_ascii=False))
        return 2

    prior_verdicts = {
        str(c.get("autoid")): str(c.get("verdict"))
        for c in prior.get("cases", [])
    }
    prior_fail = {a for a, v in prior_verdicts.items() if v != "pass"}
    prior_pass = {a for a, v in prior_verdicts.items() if v == "pass"}
    # 以上一轮真上机的卷面为准：投递时记下、随结果写进 run_results.json 的指纹。
    # 编写阶段的 cex_author_emit 会在过闸之前重写 provenance.json，拿它比只会是新比新；
    # 旧回执没有这份指纹时才退回 provenance.json。
    prior_fp = prior.get("provenance_fingerprints") or _prior_fingerprints(prov_path)

    new_cases = doc.get("cases") or []
    new_ids = {str(c.get("autoid") or "") for c in new_cases}

    violations: list[str] = []
    redispatch: list[str] = []
    for case in new_cases:
        autoid = str(case.get("autoid") or "")
        # 指纹与 provenance 同型：pass 案只有内容变化才违规；
        # 无 provenance 可比对时保守判变化（除非 --force）。
        if prior_verdicts.get(autoid) == "pass":
            pf = prior_fp.get(autoid)
            changed = pf is None or pf != _entries_fp(_cp_entries(autoid, case))
            if changed:
                violations.append(
                    f"{autoid}: 上轮 pass，本轮内容变化（pass 锁卷面；"
                    f"确需重来用 --force 整批判废）"
                )
            continue
        if autoid in prior_fail:
            redispatch.append(autoid)

    # fail 集里的 case 被删除也记录（不算违规：收敛可能裁掉无解案）
    dropped_fail = sorted(prior_fail - new_ids)

    prev_rework = batch_dir / "rework.json"
    prev_round = 0
    if prev_rework.is_file():
        try:
            prev_round = int(json.loads(
                prev_rework.read_text(encoding="utf-8")).get("round") or 0)
        except (json.JSONDecodeError, OSError, ValueError):
            prev_round = 0

    record = {
        "schema": REWORK_SCHEMA,
        "round": prev_round + 1,
        "prior_fail_set": sorted(prior_fail),
        "redispatch_set": sorted(set(redispatch)),
        "kept_pass": sorted(prior_pass & new_ids),
        "dropped_fail": dropped_fail,
        "violations": violations,
        "forced": bool(args.force),
    }
    if args.force and violations:
        record["violations"] = [v + " [force 覆盖：整批判废]" for v in violations]
        violations = []

    (batch_dir / "rework.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = not violations
    print(json.dumps({
        "ok": ok,
        "round": record["round"],
        "redispatch": record["redispatch_set"],
        "kept_pass": record["kept_pass"],
        "dropped_fail": dropped_fail,
        "violations": violations,
        "rework": str(batch_dir / "rework.json"),
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
