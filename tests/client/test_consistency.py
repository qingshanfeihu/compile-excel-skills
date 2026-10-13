"""bound 批的一致性工件打包用**真引擎**判（cex_client.consistency 只是搬运工，判据全在
cex_core/engine 抽取里）：密封结论 → verdict material → consistency_contract.json 覆盖层
的三种结局（sealed / abandoned / pending_record），以及 cex_consistency_record 的补包口径
（卡上有结论时 verdict 冻结、无结论时由模型补判、引文一律由引擎按出处重解）。

判据函数都是纯字符串/字典计算，不需要 InfoTest 检出；只需要引擎模块可导入（数据根设一个
临时目录即可，这些函数不读数据面）。子进程跑；脚本里把结论按投影期 `_eligible` 的同一趟
`stamp_consistency_quotes` 盖章，模拟的就是发布后的契约卡。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT

A1 = "203600000000000001"
SPEC_NAME = "12345_Listener_Spec.md"
SPEC_TEXT = ("# 监听器配置指南\n\n"
             "3、监听器端口修改后需执行 write mem 才落盘\n"
             "4、重启设备后未保存的监听器配置回退为出厂值\n")
TITLE = "1.配置port 为53.执行write mem后重启设备\n2.查看sdns listener  [check1]"
SPEC_LINE3 = "3、监听器端口修改后需执行 write mem 才落盘"


def _nodes_text() -> str:
    import json

    case = {"data": {"text": TITLE, "autoid": A1}, "children": [
        {"data": {"text": "2.查看sdns listener"},
         "children": [{"data": {"text": "[check1]配置未被保存"}, "children": []}]}]}
    return json.dumps([{"data": {"text": "12345 监听器改造"}, "children": [
        {"data": {"text": "配置保存"}, "children": [case]}]}], ensure_ascii=False)


MM_CASE = {
    "autoid": A1, "title": TITLE, "group_path": ["配置保存"],
    "steps": [{"n": "2", "text": "2.查看sdns listener"}],
    "expectations_by_step": [{"n": "2", "text": "[check1]配置未被保存",
                              "origin": "expectation:check1", "assertion": None}],
}


def _conclusion(verdict: str, disposition: str, reason: str, incompatibility: str) -> dict:
    return {"schema": "ist.recompose-consistency", "verdict": verdict,
            "spec_locator": f"spec:{SPEC_NAME}:3", "case_locator": "expectation:check1",
            "incompatibility": incompatibility,
            "premises": [{"origin": "spec", "locator": f"spec:{SPEC_NAME}:3"},
                         {"origin": "case", "locator": "expectation:check1"}],
            "spec_clauses": [{"text": SPEC_LINE3, "disposition": disposition,
                              "reason": reason}],
            "missing_preconditions": []}


CONCLUSIONS = {
    "consistent": _conclusion("consistent", "consistent", "同一条要求",
                              "预期与规格书第3条对得上"),
    "underdetermined": _conclusion("underdetermined", "not_applicable",
                                   "程序没有建立该前置", "步骤未执行 write mem 即断言保存"),
    "mutually_exclusive": _conclusion("mutually_exclusive", "contradicts",
                                      "预期断言未落盘也保存", "预期与规格书第3条不能同时成立"),
}
CONCLUSIONS["underdetermined"]["missing_preconditions"] = [
    "步骤未执行 write mem 即断言配置保存行为"]

MODEL_PACKAGE = {
    "spec_locator": f"spec:{SPEC_NAME}:3", "case_locator": "expectation:check1",
    "incompatibility": "预期与规格书第3条对得上",
    "premises": [{"origin": "spec", "locator": f"spec:{SPEC_NAME}:3"},
                 {"origin": "case", "locator": "expectation:check1"}],
    "spec_clauses": [{"text": SPEC_LINE3, "disposition": "consistent",
                      "reason": "同一条要求"}],
}


def _script(tmp_path: Path, steps: str) -> str:
    """子进程脚本：常量内嵌（dict 直接 repr），helpers 提供 derive/record 两个入口
    （steps 段把结果放进可 JSON 化的 out）。"""
    head = f'''
import copy, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import consistency
from cex_core.engine.case_compiler.mindmap_contract_projector import (
    _expectation_id, stamp_consistency_quotes)
from cex_core.engine.case_compiler.consistency_contract import (
    load_consistency_contract, validate_consistency_contract)

A1 = {A1!r}
SPEC_NAME = {SPEC_NAME!r}
SPEC_TEXT = {SPEC_TEXT!r}
SPEC_LINE3 = {SPEC_LINE3!r}
NODES = {_nodes_text()!r}
MM_CASE = {MM_CASE!r}
CONCLUSIONS = {CONCLUSIONS!r}
MODEL_PACKAGE = {MODEL_PACKAGE!r}

case_root = Path({str(tmp_path / "cases")!r})
(case_root / A1).mkdir(parents=True, exist_ok=True)

def stamp(conclusion):
    """投影期 `_eligible` 对结论做的那一趟盖章：卡上看到的就是这个样子。"""
    if isinstance(conclusion, dict):
        c = copy.deepcopy(conclusion)
        stamp_consistency_quotes(c, A1, mindmap_text=NODES, governing_spec=SPEC_NAME,
                                 spec_text=SPEC_TEXT, defect_spec_receipt=None,
                                 cross_check=False)
        return c
    return conclusion

def make_card(conclusion):
    exp_id = _expectation_id(A1, "2", 1)
    card = {{"autoid": A1, "batch": "b",
             "expectations": [{{"assertion": {{"expectation_id": exp_id,
                                               "semantic_key": "k"}}}}],
             "consistency": conclusion}}
    raw = json.dumps(card, ensure_ascii=False).encode("utf-8")
    return card, hashlib.sha256(raw).hexdigest()

def resolve(target):
    """str → 密封结论盖章；dict → 原样用（调用方自备已盖章形状，模拟发布后被改动的卡）。"""
    if isinstance(target, str):
        return stamp(CONCLUSIONS[target])
    return copy.deepcopy(target)

def derive(target):
    conclusion = resolve(target)
    card, sha = make_card(conclusion)
    mm = dict(MM_CASE)
    if isinstance(conclusion, dict):
        mm["consistency"] = conclusion
    outcome = consistency.derive_from_conclusion(aid=A1, card=card, card_sha256=sha,
        mm_case=mm, mindmap_text=NODES, spec_name=SPEC_NAME, spec_text=SPEC_TEXT,
        defect_receipt=None, case_root=case_root)
    return outcome, card, sha

def record(model, target):
    conclusion = resolve(target)
    card, sha = make_card(conclusion)
    return consistency.record_material(aid=A1, conclusion=conclusion, model=model,
        card=card, card_sha256=sha, mm_case=dict(MM_CASE), mindmap_text=NODES,
        spec_name=SPEC_NAME, spec_text=SPEC_TEXT, defect_receipt=None, case_root=case_root)

out = {{}}
'''
    return head + steps + "\nprint(json.dumps(out, ensure_ascii=False))\n"


def _run(tmp_path: Path, steps: str) -> dict:
    proc = subprocess.run([sys.executable, "-c", _script(tmp_path, steps)],
                          capture_output=True, text=True, timeout=300,
                          env={**os.environ, "CEX_ENGINE_DATA_ROOT": str(tmp_path)})
    assert proc.returncode == 0, proc.stderr[-3000:]
    import json

    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_a_stamped_consistent_conclusion_lands_a_valid_overlay(tmp_path):
    out = _run(tmp_path, '''
o, card, sha = derive("consistent")
overlay, osha = load_consistency_contract(consistency.overlay_path(case_root, A1))
out["consistent"] = {
    "status": o["status"], "code": o.get("code", ""),
    "sha_matches": osha == o.get("overlay_sha256"),
    "validate": validate_consistency_contract(overlay, base_contract=card,
        base_contract_sha256=sha, accepted_material=o["material"],
        consistency_receipt_sha256=o["receipt_sha256"], machine_case=MM_CASE),
    "scope": o.get("scope"),
    "premise_digests": [bool(p.get("source_sha256")) for p in o["material"]["premises"]],
    "quote": o["material"]["spec_quote"],
}''')
    got = out["consistent"]
    assert got["status"] == "sealed", got
    assert got["sha_matches"] and got["validate"] == ""
    assert got["quote"] == SPEC_LINE3
    assert all(got["premise_digests"])
    # case_locator 唯一命中一条分步期望：背书作用域收窄到那条 expectation
    assert got["scope"]["kind"] == "expectation", got
    assert got["scope"]["expectation_id"] == f"u1:{A1}:2:1"


def test_underdetermined_compiles_and_endorses_the_spec_clause(tmp_path):
    out = _run(tmp_path, '''
o, card, sha = derive("underdetermined")
out["u"] = {"status": o["status"], "verdict": (o.get("material") or {}).get("verdict")}''')
    assert out["u"] == {"status": "sealed", "verdict": "consistent"}


def test_missing_or_untiled_evidence_is_named_not_guessed(tmp_path):
    out = _run(tmp_path, '''
no_clauses = stamp(CONCLUSIONS["consistent"]); no_clauses.pop("spec_clauses")
o = derive(no_clauses)[0]
out["no_clauses"] = {"status": o["status"], "code": o.get("code", "")}
partial = stamp(CONCLUSIONS["consistent"])
partial["spec_clauses"] = [{"text": "3、监听器端口修改后需执行", "disposition": "consistent",
                            "reason": "半句"}]
o = derive(partial)[0]
out["gap"] = {"status": o["status"], "code": o.get("code", "")}
tampered = stamp(CONCLUSIONS["consistent"]); tampered["spec_quote"] = "我编的一句"
o = derive(tampered)[0]
out["drift"] = {"status": o["status"], "code": o.get("code", "")}
o = derive(None)[0]
out["missing_conclusion"] = {"status": o["status"], "code": o.get("code", "")}''')
    assert out["no_clauses"] == {"status": "pending_record", "code": "scenario1_clauses_invalid"}
    assert out["gap"]["status"] == "pending_record" and out["gap"]["code"] == "scenario1_clause_gap"
    assert out["drift"]["code"] == "consistency_spec_quote_drift", out["drift"]
    assert out["missing_conclusion"]["code"] == "consistency_conclusion_missing"


def test_a_complete_mutually_exclusive_conclusion_abandons_the_case(tmp_path):
    out = _run(tmp_path, '''
o, card, sha = derive("mutually_exclusive")
out["me"] = {"status": o["status"], "code": o.get("code", ""),
             "spec_locator": (o.get("evidence") or {}).get("spec_locator")}''')
    assert out["me"]["status"] == "abandoned"
    assert out["me"]["code"] == "case_abandoned_by_consistency"
    assert out["me"]["spec_locator"] == f"spec:{SPEC_NAME}:3"


def test_the_record_tool_fixes_the_package_without_resealing(tmp_path):
    out = _run(tmp_path, '''
o = record(dict(MODEL_PACKAGE, verdict="consistent"), None)
out["record"] = {"status": o["status"], "verdict": o.get("fixed_verdict")}
o = record(dict(MODEL_PACKAGE, verdict="conflict"), "consistent")
out["frozen"] = o.get("record_error", "")
o = record(dict(MODEL_PACKAGE, verdict="conflict"), "underdetermined")
out["forced"] = o.get("record_error", "")
forged = dict(MODEL_PACKAGE, verdict="consistent", spec_quote="我编的一句")
o = record(forged, None)
out["forged"] = {"status": o["status"], "code": o.get("code", "")}
o = record({"spec_locator": "x", "bogus": 1}, None)
out["bogus"] = o.get("record_error", "")
o = record({"verdict": "consistent", "spec_locator": "spec:" + SPEC_NAME + ":3",
            "case_locator": "title", "incompatibility": "i", "premises": "不是数组",
            "spec_clauses": []}, None)
out["premises_shape"] = o.get("record_error", "")''')
    assert out["record"] == {"status": "sealed", "verdict": "consistent"}
    assert out["frozen"] == "consistency_verdict_frozen"
    assert out["forced"] == "consistency_verdict_frozen"
    assert out["forged"]["code"] == "consistency_spec_quote_drift", out["forged"]
    assert out["bogus"].startswith("record_keys_invalid")
    assert out["premises_shape"] == "consistency_conflict_premises_missing"


def test_the_record_tool_abandons_on_a_supplied_conflict_verdict(tmp_path):
    out = _run(tmp_path, '''
model = dict(MODEL_PACKAGE, verdict="conflict",
             incompatibility="预期断言与规格书第3条不能同时成立",
             spec_clauses=[{"text": SPEC_LINE3, "disposition": "contradicts",
                            "reason": "预期断言未落盘也保存"}])
o = record(model, None)
out["conflict"] = {"status": o["status"], "code": o.get("code", "")}''')
    assert out["conflict"]["status"] == "abandoned"
    assert out["conflict"]["code"] == "case_abandoned_by_consistency"


def test_the_ts_port_carries_the_same_material_schema_literals():
    """TS 端口曾把两个 draft/material schema 常量写成别的名字；一致性工件的字节身份
    （material 回执 sha、覆盖层 sha）跨端口必须同码同源，逐字比对钉住。"""
    py = (REPO_ROOT / "cex_core" / "engine" / "case_compiler"
          / "mindmap_contract_projector.py").read_text(encoding="utf-8")
    ts = (REPO_ROOT / "ts" / "src" / "cex_core" / "engine" / "case_compiler"
          / "mindmap_contract_projector.ts").read_text(encoding="utf-8")
    assert "_CONSISTENCY_DRAFT_SCHEMA = 'ist.consistency-verdict'" in py
    assert "_CONSISTENCY_MATERIAL_SCHEMA = 'ist.consistency-verdict-material'" in py
    assert 'const _CONSISTENCY_DRAFT_SCHEMA = "ist.consistency-verdict";' in ts
    assert 'const _CONSISTENCY_MATERIAL_SCHEMA = "ist.consistency-verdict-material";' in ts
