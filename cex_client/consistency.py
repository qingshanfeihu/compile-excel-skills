"""规格一致性工件在客户端的机械打包：密封的重组结论 → 判据材料 → consistency_contract.json 覆盖层。

引擎的 author 提交链（scenario 1）在管辖规格书绑定时要求每案先有一枚被接受的 case-vs-spec
一致性工件：`ist.consistency-verdict-material`（引文由引擎按出处盖章）与由它铸出的
`consistency_contract.json` 覆盖层（Spec+Author 背书）。issue #10 的
`consistency_stage_unavailable` 就是这一段没接上。

裁决本身不在这里做第二次：重组技能按 [R11] 已让模型在密封前给每案下
`ist.recompose-consistency` 结论，投影时引擎把引文与 premises 按出处盖章进契约卡
（`mindmap_contract_projector._eligible`）。本模块把那枚**密封的结论**机械打包成提交
工件——全部调 `cex_core/engine` 抽取来的同一批引擎函数，不重写、不另立判据：

- `recompose_abandon_actionable`：案内互斥的案级放弃，照引擎的判定顺序**先于**材料推导
  （引擎 submit 也是先 `recompose_consistency_violation` 再查台账）；
- `resolve_consistency_evidence`：结论 → draft → 按出处重解引文（cross_check=True 逐字节
  对合，模型伪造不了引文），出 accepted material；出处解不出、条款不平铺都按引擎码原样
  返回 invalid；
- `build_consistency_contract` / `validate_consistency_contract` /
  `write_consistency_contract` / `load_consistency_contract`：覆盖层的铸、核、落盘、读回。

结论缺失或证据不平时（比如盖章文法只强制 mutually_exclusive 平铺 spec_clauses，
consistent/underdetermined 的卡可能没带全材料），本模块不猜：返回 pending_record 与引擎
失败码，由 `cex_consistency_record` 工具让模型**按同一密封出处补包证据**。卡上有结论时
verdict 由结论映射强制（consistent/underdetermined→consistent，mutually_exclusive→
conflict），模型改不动；卡上没有结论（比如缺陷单成立但没有绑定规格书）才由模型补判
{consistent|conflict}。

与引擎的差别只在这层胶水记工件的位置：没有服务端的 dispatch 台账，accepted material
与回执摘要记在客户端编写状态里（`.compile-excel/state/author/<批>.json`），覆盖层落在
本批每案目录 `compile_outputs/<批>/cases/<autoid>/consistency_contract.json`——客户端
把该目录当引擎的 outputs_root 用，与 intent、封存的机械用例同规。

引擎的 `validate_consistency_requirement` 的 complete 分支按服务端扁平布局
（outputs_root/<autoid>/）核对覆盖层路径，与本批目录下的布局天然不同，客户端不接它；
提交期以 material↔覆盖层↔冻结卡↔密封案的四方对合为准。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ClientError

# verdict 映射：重组结论（三值闭集）→ 材料 verdict（引擎闭集 {consistent, conflict}）。
# underdetermined 映射成 consistent：案继续编（缺的前置由编写阶段补步骤），
# 规格条文仍是它兑现断言的出处——它与规格并不互斥，只是程序还没说够。
VERDICT_MAP = {"consistent": "consistent", "underdetermined": "consistent",
               "mutually_exclusive": "conflict"}

STATUS_SEALED = "sealed"
STATUS_ABANDONED = "abandoned"
STATUS_PENDING = "pending_record"

# cex_consistency_record 接受的模型字段：draft 十键里除 schema/autoid 之外的部分，
# 外加卡上无结论时的 verdict。引文字段允许省略（引擎按 locator 盖章）；给了就得逐字对合。
_MODEL_KEYS = frozenset({"verdict", "spec_locator", "case_locator", "incompatibility",
                         "premises", "spec_clauses", "spec_quote", "case_quote"})
_PREMISE_DRAFT_KEYS = ("origin", "locator", "text")


def _detail(code: str) -> str:
    """把引擎的失败码翻译成这一层的确切出路（面向模型，英文）。"""
    text = str(code or "")
    if "clause" in text:
        return ("the spec_clauses do not tile the whole engine-stamped spec_quote (every "
                "character, in order, no gaps): slice the cited span completely as "
                "{text, disposition, reason} objects")
    if "text_field" in text:
        return ("every evidence field must be a non-empty string: spec_locator, case_locator, "
                "incompatibility, and both quotes the engine stamps from them")
    if "premises_missing" in text:
        return "cite the premises that carry the contradiction ({origin: spec|case, locator})"
    if "locator" in text or "drift" in text:
        return ("a locator does not resolve against the sealed sources, or the quote differs "
                "from the engine-stamped bytes: re-read the bound spec file and the case "
                "source and cite exact locators (spec:<file>:<line[-line]>, title, step:<n>, "
                "expectation:<label>, orphan_note:<n>, defect:<ticket>:<id>:title|description)")
    if "identity" in text or "keys" in text:
        return "the verdict draft must carry exactly the ten keys of the consistency material"
    if "conclusion_missing" in text:
        return ("this batch is bound to a governing spec, so every complete case needs the "
                "case-vs-spec conclusion")
    return "repair the exact reason cited in this violation"


def _pending(code: str) -> dict[str, Any]:
    code = str(code or "consistency_verdict_missing")
    return {"status": STATUS_PENDING, "code": code, "detail": _detail(code)}


def _abandoned(conclusion: Any, extra: str = "") -> dict[str, Any]:
    conclusion = conclusion if isinstance(conclusion, dict) else {}
    evidence = {field: str(conclusion.get(field) or "")
                for field in ("spec_locator", "spec_quote", "case_locator", "case_quote",
                              "incompatibility")}
    return {"status": STATUS_ABANDONED, "code": "case_abandoned_by_consistency",
            "evidence": evidence,
            "detail": ("the recompose stage judged this case and its bound specification "
                       "mutually exclusive on two complete sources "
                       f"(spec {evidence['spec_locator']!r}); the case is abandoned at case "
                       "level — no workbook, no question to a human; nothing here is "
                       "repairable by resubmitting" + extra)}


def _clean_premise(item: Any) -> dict[str, Any]:
    """卡片结论里的 premises 可能带材料层字段（source_sha256）；draft 只认
    {origin, locator, text}，逐键过滤，别把材料字段喂回 draft 闸。"""
    if not isinstance(item, dict):
        return {}
    return {key: item[key] for key in _PREMISE_DRAFT_KEYS if key in item}


def draft_from_conclusion(aid: str, conclusion: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """密封结论 → 十键 draft：丢 missing_preconditions/authored_conflict，
    缺的可选字段补 ''（draft 闸要精确键集）。"""
    from cex_core.engine.case_compiler.mindmap_contract_projector import (
        _CONSISTENCY_DRAFT_SCHEMA)

    verdict = VERDICT_MAP.get(str(conclusion.get("verdict") or ""))
    if verdict is None:
        return None, "consistency_verdict_invalid"
    premises = conclusion.get("premises")
    draft = {"schema": _CONSISTENCY_DRAFT_SCHEMA, "autoid": aid, "verdict": verdict,
             "spec_quote": str(conclusion.get("spec_quote") or ""),
             "case_quote": str(conclusion.get("case_quote") or ""),
             "spec_locator": str(conclusion.get("spec_locator") or ""),
             "case_locator": str(conclusion.get("case_locator") or ""),
             "incompatibility": str(conclusion.get("incompatibility") or ""),
             "premises": [_clean_premise(item) for item in premises]
                          if isinstance(premises, list) else [],
             "spec_clauses": conclusion.get("spec_clauses")}
    return draft, ""


def draft_for_record(aid: str, conclusion: Any, model: Any) -> tuple[dict[str, Any] | None, str]:
    """cex_consistency_record 的入口整形：卡上有结论时 verdict 由映射强制（模型改不动，
    给了不一致的按 consistency_verdict_frozen 拒），卡上没有结论时才由模型补判
    {consistent|conflict}。"""
    if not isinstance(model, dict):
        return None, "record_must_be_object"
    extra = sorted(set(model) - _MODEL_KEYS)
    if extra:
        return None, "record_keys_invalid: " + ", ".join(extra)
    frozen = None
    if isinstance(conclusion, dict):
        frozen = VERDICT_MAP.get(str(conclusion.get("verdict") or ""))
        if frozen is None:
            return None, "consistency_verdict_invalid"
    declared = str(model.get("verdict") or "").strip()
    if frozen is not None:
        if declared and declared != frozen:
            return None, "consistency_verdict_frozen"
        verdict = frozen
    else:
        if declared not in ("consistent", "conflict"):
            return None, "consistency_identity_or_verdict_invalid"
        verdict = declared
    premises = model.get("premises")
    if not isinstance(premises, list):
        return None, "consistency_conflict_premises_missing"
    from cex_core.engine.case_compiler.mindmap_contract_projector import (
        _CONSISTENCY_DRAFT_SCHEMA)

    draft = {"schema": _CONSISTENCY_DRAFT_SCHEMA, "autoid": aid, "verdict": verdict,
             "spec_quote": str(model.get("spec_quote") or ""),
             "case_quote": str(model.get("case_quote") or ""),
             "spec_locator": str(model.get("spec_locator") or ""),
             "case_locator": str(model.get("case_locator") or ""),
             "incompatibility": str(model.get("incompatibility") or ""),
             "premises": [_clean_premise(item) for item in premises],
             "spec_clauses": model.get("spec_clauses")}
    return draft, ""


def land_material(*, aid: str, draft: dict[str, Any], card: dict[str, Any], card_sha256: str,
                  mm_case: dict[str, Any], mindmap_text: str, spec_name: str | None,
                  spec_text: str | None, defect_receipt: dict[str, Any] | None,
                  case_root: Path) -> dict[str, Any]:
    """draft →（引擎复核）accepted material →（引擎铸造与核验）覆盖层落盘。三态返回，
    不抛引擎异常；要存的凭据是 **accepted** 那份材料（引文与 source_sha256 都是引擎重解
    过的字节），不是 draft。"""
    from cex_core.engine.case_compiler.consistency_contract import (
        build_consistency_contract, consistency_material_receipt_sha256,
        validate_consistency_contract, write_consistency_contract)
    from cex_core.engine.case_compiler.mindmap_contract_projector import (
        resolve_consistency_evidence)

    state, reason, accepted = resolve_consistency_evidence(
        mm_case, draft, mindmap_text=mindmap_text, governing_spec=spec_name,
        spec_text=spec_text, defect_spec_receipt=defect_receipt)
    if state == "invalid":
        return _pending(str(reason))
    if not isinstance(accepted, dict):
        return _pending("consistency_verdict_missing")
    if state == "conflict":
        return _abandoned(accepted)
    if state != "consistent":
        return _pending("consistency_identity_or_verdict_invalid")
    try:
        overlay = build_consistency_contract(
            autoid=aid, base_contract=card, base_contract_sha256=card_sha256,
            accepted_material=accepted, machine_case=mm_case)
    except ValueError as exc:
        return _pending(f"consistency_contract_invalid: {exc}")
    receipt = consistency_material_receipt_sha256(accepted)
    error = validate_consistency_contract(overlay, base_contract=card,
                                          base_contract_sha256=card_sha256,
                                          accepted_material=accepted,
                                          consistency_receipt_sha256=receipt,
                                          machine_case=mm_case)
    if error:
        return _pending(f"consistency_contract_invalid: {error}")
    try:
        # 引擎自己的落盘（canonical bytes、0600、原子）：别经 write_json_atomic，
        # 换个序列化就等于换一个 sha。
        _target, overlay_sha = write_consistency_contract(case_root, overlay)
    except (ValueError, OSError) as exc:
        raise ClientError(f"the consistency overlay for {aid} cannot be written: {exc}") from exc
    return {"status": STATUS_SEALED, "material": accepted, "receipt_sha256": receipt,
            "overlay_sha256": overlay_sha,
            "scope": (overlay.get("spec_endorsement") or {}).get("scope")
                     or {"kind": "case"}}


def derive_from_conclusion(*, aid: str, card: dict[str, Any], card_sha256: str,
                           mm_case: dict[str, Any], mindmap_text: str,
                           spec_name: str | None, spec_text: str | None,
                           defect_receipt: dict[str, Any] | None,
                           case_root: Path) -> dict[str, Any]:
    """密封卡结论 → 提交工件的默认路（prepare 用）。案内互斥先按引擎的放弃判据定案，
    再谈材料能不能铸出来——顺序照引擎 submit。"""
    from cex_core.engine.ist_core.tools.device.mechanical_case_submit_tool import (
        recompose_abandon_actionable)

    conclusion = card.get("consistency")
    if isinstance(conclusion, dict) and recompose_abandon_actionable(
            card, spec_surface_present=True):
        return _abandoned(conclusion)
    if not isinstance(conclusion, dict):
        outcome = _pending("consistency_conclusion_missing")
        outcome["fixed_verdict"] = None
        return outcome
    draft, error = draft_from_conclusion(aid, conclusion)
    if draft is None:
        outcome = _pending(error)
        outcome["fixed_verdict"] = None
        return outcome
    outcome = land_material(aid=aid, draft=draft, card=card, card_sha256=card_sha256,
                            mm_case=mm_case, mindmap_text=mindmap_text, spec_name=spec_name,
                            spec_text=spec_text, defect_receipt=defect_receipt,
                            case_root=case_root)
    outcome["fixed_verdict"] = draft["verdict"]
    return outcome


def record_material(*, aid: str, conclusion: Any, model: Any, card: dict[str, Any],
                    card_sha256: str, mm_case: dict[str, Any], mindmap_text: str,
                    spec_name: str | None, spec_text: str | None,
                    defect_receipt: dict[str, Any] | None,
                    case_root: Path) -> dict[str, Any]:
    """cex_consistency_record 的推导：模型补包证据，verdict 冻结规则见 draft_for_record。"""
    draft, error = draft_for_record(aid, conclusion, model)
    if draft is None:
        outcome = _pending(error)
        outcome["record_error"] = error
        return outcome
    outcome = land_material(aid=aid, draft=draft, card=card, card_sha256=card_sha256,
                            mm_case=mm_case, mindmap_text=mindmap_text, spec_name=spec_name,
                            spec_text=spec_text, defect_receipt=defect_receipt,
                            case_root=case_root)
    outcome["fixed_verdict"] = draft["verdict"]
    return outcome


def overlay_path(case_root: Path, aid: str) -> Path:
    from cex_core.engine.case_compiler.consistency_contract import (
        consistency_contract_path)

    return Path(consistency_contract_path(case_root, aid))


def load_and_verify(*, aid: str, record: dict[str, Any], card: dict[str, Any],
                    card_sha256: str, mm_case: dict[str, Any],
                    case_root: Path) -> tuple[dict[str, Any] | None, str, str]:
    """提交期重核（照引擎 submit 的台账核对位）：盘上覆盖层 ↔ 状态里存的 accepted
    material ↔ 冻结的契约卡 ↔ 密封的机械案，四方对合才放行。返回 (覆盖层, 字节 sha, 错误)。"""
    from cex_core.engine.case_compiler.consistency_contract import (
        load_consistency_contract, validate_consistency_contract)

    material = record.get("material")
    if not isinstance(material, dict) or not str(record.get("receipt_sha256") or ""):
        return None, "", "consistency_verdict_missing: the authoring state carries no accepted material"
    try:
        overlay, overlay_sha = load_consistency_contract(overlay_path(case_root, aid))
    except (ValueError, OSError) as exc:
        return None, "", f"consistency_contract_invalid: {type(exc).__name__}: {exc}"
    if overlay_sha != str(record.get("overlay_sha256") or ""):
        return None, overlay_sha, ("consistency_contract_invalid: the overlay on disk hashes to "
                                   f"{overlay_sha[:12]}, not the {str(record.get('overlay_sha256') or '')[:12]} "
                                   "recorded when it was sealed")
    error = validate_consistency_contract(overlay, base_contract=card,
                                          base_contract_sha256=card_sha256,
                                          accepted_material=material,
                                          consistency_receipt_sha256=str(record["receipt_sha256"]),
                                          machine_case=mm_case)
    if error:
        return None, overlay_sha, f"consistency_contract_invalid: {error}"
    return overlay, overlay_sha, ""


def intent_binding(record: dict[str, Any], *, overlay: Path, project_root: Path) -> dict[str, Any]:
    """sealed 案写进 intent.json 的绑定字段（客户端布局的路径相对工作区根记；
    引擎 complete 分支按服务端扁平布局核对，客户端不接，见模块 docstring）。"""
    return {"consistency_binding_status": "complete",
            "consistency_contract_path": overlay.relative_to(project_root).as_posix(),
            "consistency_contract_sha256": record["overlay_sha256"],
            "consistency_receipt_sha256": record["receipt_sha256"]}


LEGAL_FORM = {
    "keys": ["spec_locator (string)", "case_locator (string)",
             "incompatibility (one sentence)",
             "premises [{origin: 'spec'|'case', locator}] (quote bytes optional)",
             "spec_clauses [{text, disposition, reason}] tiling the whole stamped spec_quote "
             "with no gaps"],
    "note": ("pass this object as cex_consistency_record's material; the engine re-resolves "
             "every locator from the sealed sources and rejects drifted quotes"),
}


def write_brief(ws_root: Path, batch: Path, aid: str, out_name: str, record: dict[str, Any],
                *, conclusion: Any, spec_name: str | None, spec_path: str | None,
                case_atoms: dict[str, Any]) -> str:
    """pending_record 案的单案 brief：卡上（可能残缺的）结论、固定 verdict 与本案可用的
    出处原子，供模型照着补包。"""
    import json

    from .workspace import write_file_safely

    path = batch / "consistency_briefs" / f"{aid}.json"
    payload = {"schema": "cex.consistency-brief", "autoid": aid, "out_name": out_name,
               "reason_code": record.get("code", ""), "detail": record.get("detail", ""),
               "fixed_verdict": record.get("fixed_verdict"),
               "verdict_note": ("omit verdict — the sealed conclusion fixes it"
                                if record.get("fixed_verdict") is not None else
                                "no sealed conclusion on this card: give verdict "
                                "'consistent' or 'conflict', judged against the sealed sources"),
               "governing_spec": {"name": spec_name, "path": spec_path},
               "case_source_atoms": case_atoms,
               "conclusion": conclusion,
               "legal_form": LEGAL_FORM}
    write_file_safely(ws_root, path,
                      json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
    return str(path)


def drop_brief(batch: Path, aid: str) -> None:
    path = batch / "consistency_briefs" / f"{aid}.json"
    if path.is_file():
        path.unlink()


def source_atoms(mindmap_text: str, aid: str) -> dict[str, Any]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import (
        consistency_source_atoms_for_brief)

    return consistency_source_atoms_for_brief(mindmap_text).get(aid) or {}


__all__ = ["STATUS_ABANDONED", "STATUS_PENDING", "STATUS_SEALED", "VERDICT_MAP",
           "derive_from_conclusion", "draft_for_record", "drop_brief", "intent_binding",
           "load_and_verify", "overlay_path", "record_material", "source_atoms",
           "write_brief"]
