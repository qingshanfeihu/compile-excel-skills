"""编写阶段胶水测试用的假引擎：只替 cex_client.author 在提交与出件里调到的那几个引擎函数，
行为按真引擎的约定（封印 = 去掉 seal 的用例体的规范摘要，读回时核封印）。胶水自己的路径、
加锁、核对逻辑照原样跑。子进程里也能用（install 不依赖 pytest）。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

GATE_ROOTS: list[str] = []
STAMPED_ROOTS: list[str] = []
GATE_KWARGS: list[dict] = []
# 每案的一致性 requirement（fe.resolve 的假台账）
RESOLVE_REQUIREMENT: dict[str, str] = {}
ABANDON_ACTIONABLE: dict[str, bool] = {}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def seal_document(body: dict[str, Any]) -> dict[str, Any]:
    plain = {k: v for k, v in body.items() if k != "seal"}
    return {**plain, "seal": {"mechanical_case_sha256": _digest(plain)}}


def _mint(body: dict[str, Any], target, **_kw):
    document = seal_document(body)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return SimpleNamespace(document=document, code="", detail="")


def _load(path):
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    plain = {k: v for k, v in document.items() if k != "seal"}
    if (document.get("seal") or {}).get("mechanical_case_sha256") != _digest(plain):
        raise ValueError("mechanical case seal does not match its body")
    return SimpleNamespace(model_dump=lambda **_kw: document), hashlib.sha256(raw).hexdigest()


def _gate(body, contract, *, outputs_root=None, **_kw):
    GATE_ROOTS.append(str(outputs_root))
    GATE_KWARGS.append(dict(_kw))
    time.sleep(float(os.environ.get("FAKE_GATE_DELAY") or 0))
    return True, {"measurements": {"capabilities_used": [], "expanded_step_count": 1,
                                   "check_point_count": 1}, "advisories": [], "hard_rejects": []}


def _expand(blocks):
    steps = [{"E": b.get("E"), "F": b.get("F"), "G": b.get("G")} for b in blocks]
    prov = []
    for block in blocks:
        head, _, tail = str(block.get("ref") or "").partition(":")
        prov.append({"source": {"kind": head, "ref": tail}} if block.get("ref") else {})
    return steps, prov, None


_PACKAGES = ("cex_core.engine.case_compiler", "cex_core.engine.ist_core",
             "cex_core.engine.ist_core.tools", "cex_core.engine.ist_core.tools.device",
             "cex_core.engine.ist_core.compile_engine")

_MATERIAL_SCHEMA = "ist.consistency-verdict-material"


def _load_mm(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _resolve_evidence(case, proposal, **_kw):
    """按引擎的三态口径返假材料：verdict 非 consistent/conflict、consistent 而缺条款
    （镜像 loose 分支的平铺要求）都 invalid 带码。"""
    if not isinstance(proposal, dict):
        return ("invalid", "consistency_schema_keys_invalid", None)
    verdict = str(proposal.get("verdict") or "")
    if verdict not in ("consistent", "conflict"):
        return ("invalid", "consistency_identity_or_verdict_invalid", None)
    if verdict == "consistent" and not (isinstance(proposal.get("spec_clauses"), list)
                                        and proposal["spec_clauses"]):
        return ("invalid", "scenario1_clauses_invalid", None)
    accepted = {**proposal, "schema": _MATERIAL_SCHEMA,
                "premises": [dict(item, source_sha256=_digest(item))
                             for item in proposal.get("premises") or []
                             if isinstance(item, dict)]}
    return (verdict, "", accepted)


def _overlay_build(*, autoid, base_contract, base_contract_sha256, accepted_material,
                   machine_case):
    return {"schema": "ist.consistency-contract", "autoid": autoid,
            "base_contract_sha256": base_contract_sha256,
            "consistency_receipt_sha256": _digest(accepted_material),
            "spec_endorsement": {"scope": {"kind": "case"}}}


class _ConsistencyRequirementError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


VALIDATIONS: list[str] = []


def _overlay_validate(overlay, **_kw):
    VALIDATIONS.append(str(overlay.get("autoid") or ""))
    return ""


def _overlay_write(outputs_root, overlay):
    target = Path(outputs_root) / str(overlay["autoid"]) / "consistency_contract.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(overlay, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    target.write_bytes(payload)
    return target, hashlib.sha256(payload).hexdigest()


def _overlay_load(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


_MODULES: dict[str, dict[str, Any]] = {
    "cex_core.engine.ist_core.tools.device.mechanical_case_submit_tool": {
        "_violations_with_legal_forms": lambda v: list(v),
        "_canonicalize_submission_blocks": lambda body: (body, ""),
        "_stamp_engine_binding": lambda body, **kw: (
            {**body, "binding": {"contract_sha256": kw["contract_sha256"],
                                 "consistency_contract_sha256":
                                     kw.get("consistency_contract_sha256")}}, []),
        "unique_exempt_blocks_submit": lambda body: None,
        "recompose_abandon_actionable": lambda contract, **kw: bool(
            ABANDON_ACTIONABLE.get(str(contract.get("autoid") or ""), False)),
    },
    "cex_core.engine.ist_core.compile_engine.consistency_requirement": {
        "NOT_APPLICABLE": "not_applicable", "REQUIRED": "required",
        "ConsistencyRequirementError": _ConsistencyRequirementError,
        "resolve_consistency_requirement": lambda **kw: {
            "requirement": RESOLVE_REQUIREMENT.get(str(kw.get("autoid") or ""), "not_applicable"),
            "binding_status": "pending", "governing_spec_status": "bound",
            "autoid": str(kw.get("autoid") or "")},
    },
    "cex_core.engine.case_compiler.mindmap_contract_projector": {
        "load_machine_mindmap": _load_mm,
        "resolve_consistency_evidence": _resolve_evidence,
        "consistency_source_atoms_for_brief": lambda text: {},
        "_CONSISTENCY_DRAFT_SCHEMA": "ist.consistency-verdict",
        "_CONSISTENCY_MATERIAL_SCHEMA": _MATERIAL_SCHEMA,
    },
    "cex_core.engine.case_compiler.consistency_contract": {
        "build_consistency_contract": _overlay_build,
        "consistency_material_receipt_sha256": _digest,
        "validate_consistency_contract": _overlay_validate,
        "write_consistency_contract": _overlay_write,
        "load_consistency_contract": _overlay_load,
        "consistency_contract_path": lambda outputs_root, autoid: str(
            Path(outputs_root) / str(autoid) / "consistency_contract.json"),
        "spec_endorsement_expectation_binding_rule": lambda: {"schema": "rule"},
    },
    "cex_core.engine.case_compiler.mechanical_case": {
        "mint_and_land_mechanical_case": _mint, "load_mechanical_case": _load},
    "cex_core.engine.case_compiler.mechanical_case_gate": {
        "AUDIENCE_WORKER": "worker", "gate_report_digest": lambda report: "0" * 64,
        "run_mechanical_case_gate": _gate},
    "cex_core.engine.case_compiler.vendor_stdlib": {"configured_device_os_build": lambda: "585"},
    "cex_core.engine.engine_managed_outputs": {"MECHANICAL_CASE_SIDECAR_NAME": "mechanical_case.json"},
    "cex_core.engine.case_compiler.blocks": {
        "expand_blocks": _expand,
        "lower_derived_assertions": lambda steps, prov: (steps, prov, None)},
}


def install(setitem: Callable[[Any, str, Any], None] | None = None,
            setattr_: Callable[[Any, str, Any], None] | None = None) -> None:
    """装假引擎。setitem / setattr_ 传 pytest 的 monkeypatch 版本就会在用例结束时复原。"""
    setitem = setitem or (lambda mapping, key, value: mapping.__setitem__(key, value))
    setattr_ = setattr_ or setattr
    for name in _PACKAGES:
        package = types.ModuleType(name)
        package.__path__ = []
        setitem(sys.modules, name, package)
    for name, members in _MODULES.items():
        module = types.ModuleType(name)
        for key, value in members.items():
            setattr(module, key, value)
        setitem(sys.modules, name, module)

    from cex_client import author, skill_scripts

    setattr_(author.engine_env, "prepare",
             lambda ws, pinned=None: (ws.state_dir / "engine" / "fake", {}))
    setattr_(author, "_require_current_seal", lambda ws, state: None)
    setattr_(author, "_manifest_cases", lambda text: {aid: {"autoid": aid}
                                                      for aid in json.loads(text)["autoids"]})
    setattr_(author, "source_case_slice", lambda case, aid: ({}, "0" * 64))

    def ctx(root, batch, text):
        """假批的数据根没有规格书文件：旁车与机械案直接从批目录读，spec_text 给固定串。"""
        spec = json.loads((batch / "governing_spec_status.json").read_text(encoding="utf-8")) \
            if (batch / "governing_spec_status.json").is_file() else {"status": "no_governing_spec"}
        from cex_core.engine.case_compiler.mindmap_contract_projector import (
            load_machine_mindmap)

        mm, _sha = load_machine_mindmap(batch / "machine_mindmap.json")
        return {"text": text, "spec_status": spec,
                "spec_name": spec.get("name") if spec.get("status") == "bound" else None,
                "spec_text": "3、监听器端口修改后需执行 write mem 才落盘\n"
                             if spec.get("status") == "bound" else None,
                "spec_path": None, "defect_receipt": None,
                "mm_cases": {str(c.get("autoid") or ""): c for c in mm.get("cases") or []
                             if isinstance(c, dict)}}

    setattr_(author, "_consistency_ctx", ctx)

    def stamp(ws, root, batch, case_root, aid, receipt, case, ctx=None, outcome=None):
        STAMPED_ROOTS.append(str(case_root))
        (case_root / aid).mkdir(parents=True, exist_ok=True)
        (case_root / aid / "intent.json").write_text(json.dumps({"autoid": aid}), encoding="utf-8")
        requirement = RESOLVE_REQUIREMENT.get(str(aid), "not_applicable")
        if outcome is None and ctx is not None and requirement == "required":
            # 迁移/重投影的打包：走真 cex_client.consistency + 假引擎判据（sys.modules 里那套）
            from cex_client import consistency as cmod

            card_raw = (Path(batch) / "contracts" / f"{aid}.json").read_bytes()
            outcome = cmod.derive_from_conclusion(
                aid=str(aid), card=json.loads(card_raw), card_sha256=
                hashlib.sha256(card_raw).hexdigest(), mm_case=ctx["mm_cases"].get(str(aid)) or {},
                mindmap_text=ctx["text"], spec_name=ctx["spec_name"], spec_text=ctx["spec_text"],
                defect_receipt=ctx["defect_receipt"], case_root=Path(case_root))
        return {"requirement": requirement, "binding_status": "pending",
                "governing_spec_status": "bound"}, outcome

    setattr_(author, "_stamp_intent", stamp)

    def compile_workbook(cases_path, out_dir):
        doc = json.loads(Path(cases_path).read_text(encoding="utf-8"))
        xlsx = Path(out_dir) / doc["batch"] / "case.xlsx"
        xlsx.write_bytes(b"xlsx")
        return {"ok": True, "path": str(xlsx), "batch": doc["batch"]}

    setattr_(skill_scripts, "compile_workbook", compile_workbook)
    setattr_(skill_scripts, "verify_workbook", lambda xlsx: {"pass": 1, "fail": 0, "failures": []})


def sealed_consistency(aid: str, batch, case_root, contract_sha: str) -> dict:
    """一个已落覆盖层的 required 案的台账记录（假引擎口径）。"""
    material = {"schema": _MATERIAL_SCHEMA, "autoid": aid, "verdict": "consistent",
                "spec_quote": "q", "case_quote": "c", "spec_locator": "spec:x.md:1",
                "case_locator": "title", "incompatibility": "i", "premises": [],
                "spec_clauses": [{"text": "q", "disposition": "consistent", "reason": "r"}]}
    overlay = _overlay_build(autoid=aid, base_contract={"autoid": aid},
                             base_contract_sha256=contract_sha, accepted_material=material,
                             machine_case={"autoid": aid})
    _target, overlay_sha = _overlay_write(case_root, overlay)
    RESOLVE_REQUIREMENT[aid] = "required"
    return {"status": "sealed", "material": material,
            "receipt_sha256": _digest(material), "overlay_sha256": overlay_sha,
            "scope": {"kind": "case"}}


_BOUND_CONCLUSION = {"schema": "ist.recompose-consistency", "verdict": "consistent",
                     "spec_locator": "spec:x.md:3", "case_locator": "title",
                     "incompatibility": "对得上",
                     "premises": [{"origin": "case", "locator": "title"}],
                     "spec_clauses": [{"text": "3、监听器端口修改后需执行 write mem 才落盘",
                                       "disposition": "consistent", "reason": "同一条要求"}],
                     "missing_preconditions": []}


def published_batch(ws, name: str, autoids: list[str], *, legacy: bool = False,
                    required: list[str] = (), pending: list[str] = ()) -> None:
    """一个已发布契约卡的批：contracts/、脑图快照、编写状态（legacy=True 时是旧版状态：
    没有 cases_root，每案目录在 compile_outputs/<autoid>/）。required/pending 里的案按 bound
    批台账摆齐：旁车、机械案、带密封结论的卡；required 再落覆盖层与 sealed 记录，pending 只留
    pending_record 记录。"""
    from cex_client import author

    batch = ws.outputs_dir / name
    (batch / "contracts").mkdir(parents=True, exist_ok=True)
    (batch / "mindmap_source.json").write_text(json.dumps({"autoids": autoids}), encoding="utf-8")
    bound = list(required) + list(pending)
    contracts = {}
    for aid in autoids:
        card = {"autoid": aid, "batch": name, "expectations": []}
        if aid in bound:
            card["consistency"] = _BOUND_CONCLUSION
        raw = json.dumps(card, ensure_ascii=False).encode("utf-8")
        (batch / "contracts" / f"{aid}.json").write_bytes(raw)
        contracts[aid] = hashlib.sha256(raw).hexdigest()
    cases = {aid: {"consistency_requirement": "not_applicable"} for aid in autoids}
    if bound:
        (batch / "governing_spec_status.json").write_text(
            json.dumps({"status": "bound", "name": "x.md", "generation_id": "g1"}),
            encoding="utf-8")
        (batch / "defect_spec_status.json").write_text(
            json.dumps({"status": "not_queried"}), encoding="utf-8")
        (batch / "machine_mindmap.json").write_text(json.dumps(
            {"cases": [{"autoid": a, "expectations_by_step": []} for a in autoids]}),
            encoding="utf-8")
        case_root = batch / "cases"
        for aid in required:
            cases[aid] = {"consistency_requirement": "required",
                          "consistency": sealed_consistency(aid, batch, case_root,
                                                            contracts[aid])}
        for aid in pending:
            RESOLVE_REQUIREMENT[aid] = "required"
            cases[aid] = {"consistency_requirement": "required", "consistency": {
                "status": "pending_record", "code": "scenario1_clauses_invalid",
                "detail": "no clauses on the sealed conclusion", "brief_path": None}}
    state = {"out_name": name, "phase": "published", "sealed": {}, "pending": {},
             "cases": cases,
             "receipt": {"written_autoids": list(autoids), "contract_sha256_by_autoid": contracts,
                         "machine_mindmap_sha256": "a" * 64},
             "projected_machine_mindmap_sha256": "a" * 64,
             "data_root": ".compile-excel/engine/fake"}
    if not legacy:
        state["cases_root"] = f"compile_outputs/{name}/cases"
    author._save_state(ws, state)


def body(aid: str, text: str) -> dict[str, Any]:
    return {"schema": "ist.mechanical-case", "autoid": aid,
            "description": {"intent_verbatim": text}, "binding": {}, "init_commands": [],
            "blocks": [{"E": "APV_0", "F": "cmd", "G": text}], "expectation_binding": [],
            "escape_hatches": []}
