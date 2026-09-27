#!/usr/bin/env python3
"""rework_gate: 返工纪律闸 —— 重派集 ⊆ fail 集，pass 案锁卷面（镜像引擎 merge 节点口径）。

引擎数据层规则（EngineLedger 迁移合法性表）的 skill 版：
- 上一轮 verdict=pass 的 case，本轮卷面不得变。比的是逐案全行指纹：每一步的 E/F/G/H/I 与出处都算，
  外加文件级 init_commands——init 在每个案之前重放，改它等于改了每个案。
  pass 意味着卷面已验证，重编等于撕掉已验证事实；发现 pass 判定本身有假才允许整批判废重来，
  走 --force --reason（理由记进 rework.json）；
- 上一轮 pass 的案不能从卷面上消失，上一轮没有的案也不能混进来；上一轮非 pass 的案可以改、可以删；
- 闸通过（或 --force 带理由强过）才写 rework.json（轮次账：fail 集 / 重派集 / 保留 pass 集 /
  违规与理由），拒绝时不写，免得留下一份像是过了闸的账。

基线是上一轮真上机的卷面：投递时记下、随结果写进 run_results.json 的 case_fingerprints
（cex_client.fingerprints.case_fingerprints，算本轮卷面用的是同一个函数）。旧回执没有它时退回
只比 check_point 的旧口径（provenance_fingerprints；再旧的读 provenance.json，且它不能比回执新），
输出里的 baseline 写明用的是哪一种。

顺序——脑图批：cex_author_submit_case 重交失败案 → cex_author_emit → 本闸（--cases 用出件的
compile_outputs/<batch>/cases.json）→ cex_scan_destructive → 上机；
手写批：改 cases.json → 本闸 → compile_excel → cmdtree_check / verify_batch → cex_scan_destructive → 上机。

用法：
  python3 scripts/rework_gate.py --batch-dir compile_outputs/<batch> --cases compile_outputs/<batch>/cases.json
  python3 scripts/rework_gate.py --batch-dir ... --cases ... --force --reason "<为什么整批判废重来>"
退出码：0 = 闸通过（无上机历史、或 --force 带理由强过）；1 = 违反纪律（不写 rework.json）；
        2 = 输入缺失/非法（含 --force 没给 --reason）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _cex_path  # noqa: F401,E402 — 发行根进 sys.path
from compile_excel import _SOURCE_KINDS, _step_field  # noqa: E402

REWORK_SCHEMA = "ist.excel.rework-record"
INIT_KEY = "__init__"

# 基线口径：写进输出与 rework.json，读的人一眼知道比的是什么
BASELINE_FULL = "case_fingerprints"
BASELINE_NOTES = {
    BASELINE_FULL: "逐案全行指纹（每一步 + 出处，外加 init_commands），取自 run_results.json，即上一轮真上机的卷面",
    "provenance_fingerprints": ("旧回执没有 case_fingerprints：退回只比 check_point（E/F/G + 出处）的旧口径，"
                                "配置步、观察命令和 init_commands 的改动这里看不出来"),
    "provenance.json": ("旧回执没有任何指纹：退回只比 provenance.json 里的 check_point，"
                        "配置步、观察命令和 init_commands 的改动这里看不出来"),
    "none": ("没有可信基线（回执里没有指纹，provenance.json 缺失或在上机之后被重写过）："
             "上一轮 pass 的案无法证明未变，一律按变化处理"),
}


class GateInputError(Exception):
    """输入缺失或非法：退出码 2。"""


def _load_case_fingerprints():
    """I6：cex_client.fingerprints.case_fingerprints（上机投递记基线用的同一个函数）；旧发行版没有就返回 None。"""
    try:
        from cex_client.fingerprints import case_fingerprints
    except ImportError:
        return None
    return case_fingerprints


def _cp_entries(autoid: str, case: dict) -> list[dict]:
    """case 的 check_point 来源记录，与 compile_excel._build_provenance 同型（旧口径用）。"""
    out = []
    # 手写 cases.json 用小写 e/f/g，cex_author_emit 产出的用大写 E/F/G：两种都认
    for s in case.get("steps", []):
        if not isinstance(s, dict) or str(_step_field(s, "e") or "").strip() != "check_point":
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
    """从 provenance.json 取每 case 的 check_point 指纹（最旧回执的退路）。"""
    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for autoid, entries in ((prov or {}).get("cases") or {}).items():
        if isinstance(entries, list):
            out[str(autoid)] = _entries_fp(entries)
    return out


def _baseline(prior: dict, run_path: Path, prov_path: Path) -> tuple[str, dict[str, str]]:
    """上一轮真上机卷面的指纹：(口径, {autoid: sha})。"""
    for key in (BASELINE_FULL, "provenance_fingerprints"):
        fps = prior.get(key)
        if isinstance(fps, dict) and fps:
            return key, {str(k): str(v) for k, v in fps.items()}
    # provenance.json 比回执新 = 上机之后重出过件（cex_author_emit / compile_excel 都会重写它），
    # 那是新卷面，拿它当基线只会新比新
    if prov_path.is_file() and prov_path.stat().st_mtime <= run_path.stat().st_mtime:
        fps = _prior_fingerprints(prov_path)
        if fps:
            return "provenance.json", fps
    return "none", {}


def _read_json(path: Path, what: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GateInputError(f"{what} 不存在: {path}") from None
    except (json.JSONDecodeError, OSError, UnicodeError) as exc:
        raise GateInputError(f"{what} 不可读: {exc}") from None
    if not isinstance(data, dict):
        raise GateInputError(f"{what} 顶层必须是 JSON 对象: {path}")
    return data


def _violation(autoid: str, code: str, detail: str) -> dict[str, str]:
    return {"autoid": autoid, "code": code, "detail": detail}


def _prev_record(batch_dir: Path) -> dict:
    path = batch_dir / "rework.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return record if isinstance(record, dict) else {}


def run_gate(batch_dir: Path, cases_path: Path, *, force: bool = False,
             reason: str = "") -> tuple[int, dict]:
    """闸本体：返回 (退出码, 打印的结果)。rework.json 只在闸通过（或强过）时写。"""
    reason = (reason or "").strip()
    if force and not reason:
        raise GateInputError("--force 必须带 --reason \"<理由>\"：整批判废重来要记录在案")
    doc = _read_json(cases_path, "cases")
    new_cases = doc.get("cases")
    if not isinstance(new_cases, list):
        raise GateInputError("cases JSON 缺少 cases 数组")
    batch = str(doc.get("batch") or "").strip()
    if batch and batch != batch_dir.name:
        raise GateInputError(f"cases.json 属于批次 {batch!r}，不是 --batch-dir 的 {batch_dir.name!r}")
    new_ids = [str(c.get("autoid") or "") for c in new_cases if isinstance(c, dict)]
    if "" in new_ids or len(new_ids) != len(new_cases):
        raise GateInputError("cases 里每个案都必须是带 autoid 的对象")

    run_path = batch_dir / "run_results.json"
    prev = _prev_record(batch_dir)
    if not run_path.is_file():
        # 无上机历史：没有 pass 要锁、没有 fail 集要比，闸恒通过
        record = {"schema": REWORK_SCHEMA, "round": 1, "first_round": True,
                  "prior_fail_set": [], "redispatch_set": [], "kept_pass": [],
                  "violations": [], "forced": bool(force), "reason": reason or None,
                  "cases": str(cases_path)}
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "rework.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0, {"ok": True, "round": 1, "first_round": True, "violations": [],
                   "rework": str(batch_dir / "rework.json")}

    prior = _read_json(run_path, "run_results.json")
    prior_verdicts: dict[str, str] = {}
    for case in prior.get("cases") or []:
        if isinstance(case, dict) and str(case.get("autoid") or ""):
            prior_verdicts[str(case["autoid"])] = str(case.get("verdict") or "")
    prior_fail = {a for a, v in prior_verdicts.items() if v != "pass"}
    prior_pass = {a for a, v in prior_verdicts.items() if v == "pass"}

    mode, base = _baseline(prior, run_path, batch_dir / "provenance.json")
    if mode == BASELINE_FULL:
        fingerprint = _load_case_fingerprints()
        if fingerprint is None:
            raise GateInputError(
                "run_results.json 带 case_fingerprints，但这个发行版没有 cex_client/fingerprints.py，"
                "算不出同口径的新指纹：重新安装 compile-excel")
        try:
            new_fp = {str(k): str(v) for k, v in fingerprint(doc).items()}
        except (TypeError, ValueError, AttributeError) as exc:
            raise GateInputError(f"算不出本轮卷面的指纹: {type(exc).__name__}: {exc}") from None
    else:
        new_fp = {aid: _entries_fp(_cp_entries(aid, case))
                  for aid, case in zip(new_ids, new_cases)}

    violations: list[dict[str, str]] = []
    for aid in new_ids:
        if aid not in prior_verdicts:
            violations.append(_violation(
                aid, "case_not_in_prior_run",
                "上一轮没有这个案：重派集只能取自上一轮的 fail 集（新增用例是另一批的事）"))
            continue
        if aid not in prior_pass:
            continue
        before = base.get(aid)
        if before is None:
            violations.append(_violation(
                aid, "pass_baseline_missing",
                "上一轮 pass，但基线里没有它的指纹，证明不了卷面没变（pass 锁卷面）"))
        elif before != new_fp.get(aid):
            violations.append(_violation(
                aid, "pass_case_changed",
                "上一轮 pass，本轮卷面变了（pass 锁卷面；确需重来用 --force --reason 整批判废）"))
    kept_pass = sorted(prior_pass & set(new_ids))
    if mode == BASELINE_FULL and base.get(INIT_KEY) != new_fp.get(INIT_KEY) and kept_pass:
        violations.append(_violation(
            INIT_KEY, "init_commands_changed",
            f"文件级 init_commands 变了：它在每个案之前重放，上一轮 pass 的 {len(kept_pass)} 个案"
            "因此全部变了（pass 锁卷面）"))
    for aid in sorted(prior_pass - set(new_ids)):
        violations.append(_violation(
            aid, "pass_case_dropped",
            "上一轮 pass 的案不在本轮卷面上：已验证的案不能悄悄拿掉"))

    redispatch = sorted(prior_fail & set(new_ids))
    changed_fail = sorted(a for a in redispatch if base.get(a) is None or base.get(a) != new_fp.get(a))
    unchanged_fail = sorted(set(redispatch) - set(changed_fail))
    dropped_fail = sorted(prior_fail - set(new_ids))

    forced = bool(force)
    if forced:
        for item in violations:
            item["overridden"] = True
    ok = forced or not violations
    result = {
        "ok": ok,
        "baseline": mode,
        "baseline_note": BASELINE_NOTES[mode],
        "prior_run": {k: prior.get(k) for k in ("task_id", "xlsx_sha256", "finished")},
        "prior_fail": sorted(prior_fail),
        "redispatch": redispatch,
        "changed_fail": changed_fail,
        "unchanged_fail": unchanged_fail,
        "kept_pass": kept_pass,
        "dropped_fail": dropped_fail,
        "violations": violations,
        "forced": forced,
        "reason": reason or None,
    }
    if not ok:
        result["rework"] = None
        result["note"] = ("闸未通过，rework.json 没有写：只改上一轮失败的案；pass 案确需重来时用 "
                          "--force --reason 整批判废，理由会记进 rework.json")
        return 1, result

    # 同一轮上机的返工闸重跑（改了再过一次闸）不另起一轮
    prior_task = str(prior.get("task_id") or "")
    prev_round = int(prev.get("round") or 0) if str(prev.get("round") or "0").isdigit() else 0
    same_round = bool(prior_task) and prev.get("prior_task_id") == prior_task and prev_round > 0
    round_no = prev_round if same_round else prev_round + 1
    record = {
        "schema": REWORK_SCHEMA,
        "round": round_no,
        "prior_task_id": prior_task or None,
        "cases": str(cases_path),
        "baseline": mode,
        "prior_fail_set": result["prior_fail"],
        "redispatch_set": redispatch,
        "changed_fail": changed_fail,
        "unchanged_fail": unchanged_fail,
        "kept_pass": kept_pass,
        "dropped_fail": dropped_fail,
        "violations": violations,
        "forced": forced,
        "reason": reason or None,
    }
    path = batch_dir / "rework.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    result["round"] = round_no
    result["rework"] = str(path)
    return 0, result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="返工纪律闸")
    ap.add_argument("--batch-dir", required=True, help="compile_outputs/<batch>（run_results.json 所在目录）")
    ap.add_argument("--cases", required=True,
                    help="本轮要上机的 cases.json（脑图批用 cex_author_emit 出件的那份）")
    ap.add_argument("--force", action="store_true",
                    help="整批判废重来：pass 案的变化也放行，必须同时给 --reason")
    ap.add_argument("--reason", default="", help="--force 的理由，原样记进 rework.json")
    args = ap.parse_args(argv)
    try:
        code, result = run_gate(Path(args.batch_dir).expanduser().resolve(),
                                Path(args.cases).expanduser().resolve(),
                                force=args.force, reason=args.reason)
    except GateInputError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
