"""脑图重组（人工脑图 → 机械脑图）在客户端的编排。

InfoTest 里这一段由编译引擎的 recompose 节点做：封存脑图快照、定位管辖规格书、判缺陷单
通道状态、初始化提交回执、派发重组 fork、最后按已落盘的案密封成 machine_mindmap.json。
客户端没有引擎，这里把那层薄胶水按原顺序移植过来（nodes.py `recompose`），规格书与缺陷单
两份状态的字段形状与引擎逐字段一致；判据（逐字闭集、锚定、一致性引文、密封复核……）一律
调 cex_core.engine 抽取来的同一批函数，不重写。

与引擎的差别（都只在这层胶水里）：
- 输入只收 XMind JSON 导出，且只能有一个根标题（引擎查规格书同样只用第一个根标题）；
- 规格书定位不开 Jev 精排（它调外部 LLM 服务）：只影响语义候选的先后与截取，"命中 /
  多个候选 / 没有"的判定不变；
- 引擎的"查不到规格书再问一次"面板不移植：spec='none' 对应用户在那个面板上拒绝重查
  （resolution=user_declined_retry），spec=<文件名> 对应入口点名（explicit_pin）；
- 缺陷单规格（DefectSpec）不签发：客户端没有引擎那条查单→安全投影→密封收据的通道。
  根标题带单号时，结果与引擎两次查单都不可用相同（resolved_absent，原因写明）；缺陷单
  原文可以用 cex_bug_get 查，但它是线索，不是出处；
- 全部案落盘后由客户端从台账密封（引擎在台账盖满时也是自己密封、不再派 fork；
  self_check / orphan_notes 两个可选字段引擎也不消费）；
- 派发状态落在 .compile-excel/recompose/<批名>.json，每次工具调用据此重新进入同一个派发
  作用域（工具可能跑在独立进程里）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from . import engine_env
from .errors import ClientError
from .workspace import Workspace, read_private_json, safe_component, write_private_json

STATE_SCHEMA = "cex.recompose-dispatch/v1"
DEFECT_CHANNEL_ABSENT = "client_has_no_defect_spec_channel"
_STRIP = "\ufeff\uffff"
_SPEC_STATUS_SCHEMA = "ist.governing-spec-status"
_DEFECT_STATUS_SCHEMA = "ist.defect-spec-status"


def _state_path(ws: Workspace, out_name: str) -> Path:
    return ws.state_dir / "recompose" / f"{safe_component(out_name, 'batch name')}.json"


def _load_state(ws: Workspace, out_name: str) -> dict[str, Any]:
    state = read_private_json(_state_path(ws, out_name))
    if not state or state.get("schema") != STATE_SCHEMA:
        raise ClientError(f"no recompose dispatch for {out_name!r}; call cex_recompose_prepare")
    return state


def _mindmap_file(ws: Workspace, mindmap: str) -> Path:
    path = Path(str(mindmap or "")).expanduser()
    if not path.is_absolute():
        path = ws.root / path
    path = path.resolve()
    if ws.root.resolve() not in path.parents or not path.is_file():
        raise ClientError("mindmap must be an existing file inside the workspace")
    return path


def _root_titles(text: str) -> list[str]:
    try:
        roots = json.loads(text.lstrip(_STRIP))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ClientError(f"the mindmap is not an XMind JSON export: {exc}") from None
    if isinstance(roots, dict):
        roots = [roots]
    titles: list[str] = []
    for root in roots if isinstance(roots, list) else []:
        if not isinstance(root, dict):
            continue
        data = root.get("data") if isinstance(root.get("data"), dict) else {}
        title = str(data.get("text") or root.get("text") or "").strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def _governing_spec(root: Path, batch: Path, out_name: str, title: str,
                    pin: str, declined: bool) -> dict[str, Any]:
    """nodes.py `recompose` 里定位与绑定管辖规格书那一段，去掉面板与事实流。"""
    from cex_core.engine.ist_core.compile_engine.spec_references import build_spec_references
    from cex_core.engine.kms.spec_index import load_index, locate_spec, resolve_indexed_spec
    from cex_core.engine.knowledge_paths import (
        SpecGenerationUnavailable,
        resolve_active_spec_generation,
    )

    try:
        active = resolve_active_spec_generation(root)
    except SpecGenerationUnavailable:
        active = None

    def _locate() -> tuple[dict[str, Any] | None, tuple[str, str] | None]:
        if active is None:
            return None, ("unavailable", "governing spec generation is unavailable")
        try:
            index = load_index(active.index)
        except SpecGenerationUnavailable:
            return None, ("unavailable", "governing spec generation is unavailable")
        if not isinstance(index, dict):
            return None, ("invalid_source", "governing spec index is invalid")
        try:
            raw = locate_spec(index, title, rerank=False)
        except (AttributeError, TypeError, ValueError, RecursionError):
            raw = None
        if not isinstance(raw, dict):
            return None, ("invalid_source", "governing spec lookup is invalid")
        return raw, None

    locator: dict[str, Any] = {"status": "no_governing_spec", "matches": [], "channel": None}
    lookup_unknown: tuple[str, str] | None = None
    if not declined:
        raw_locator, lookup_unknown = _locate()
        if lookup_unknown is not None and active is not None:
            raw_locator, lookup_unknown = _locate()  # 引擎同样自动重查一次
        if raw_locator is not None:
            locator = raw_locator
    forced = "user_declined_retry" if declined else (
        "auto_retry_exhausted" if lookup_unknown is not None else "")
    if forced:
        locator = {"status": "no_governing_spec", "matches": [], "channel": None,
                   "resolution": forced,
                   "raw_status": lookup_unknown[0] if lookup_unknown else None}
    pin_evidence = ""
    if pin:
        pin_evidence = (f"explicit_user_pin;locator={locator.get('status')}:"
                        f"{locator.get('channel')}")
        locator = {"status": "matched", "channel": "explicit_pin",
                   "matches": [{"file": pin, "title": "", "evidence": pin_evidence}]}

    matches = locator.get("matches") or []
    status = locator.get("status")
    candidates: list[dict[str, Any]] = []
    if status == "candidates":
        candidates = [m for m in matches if isinstance(m, dict)]
        matches, status = [], "ambiguous"
    elif status == "no_governing_spec":
        if matches != [] or (locator.get("channel") is not None and not forced):
            raise ClientError("governing spec absence receipt is malformed")
    elif status != "matched":
        lookup_unknown = lookup_unknown or ("invalid_source",
                                            "governing spec lookup status is unknown")
        forced = forced or "auto_retry_exhausted"
        status, matches = "no_governing_spec", []
    unique = (status == "matched" and isinstance(matches, list) and len(matches) == 1
              and isinstance(matches[0], dict) and bool(str(matches[0].get("file") or "").strip()))
    if status == "matched" and not unique:
        lookup_unknown = lookup_unknown or ("invalid_source",
                                            "governing spec matched receipt is malformed")
        forced = forced or "auto_retry_exhausted"
        status, matches = "no_governing_spec", []
    name = str(matches[0].get("file") or "").strip() if unique else ""
    resolved = resolve_indexed_spec(root, name) if name else None
    if name and (resolved is None or active is None
                 or resolved.generation_id != active.generation_id
                 or resolved.manifest_sha256 != active.manifest_sha256):
        if pin_evidence:
            raise ClientError(f"spec {name!r} is not in the synced spec generation; pick one of "
                              "the candidates or pass spec='none'")
        lookup_unknown = lookup_unknown or ("invalid_source",
                                            "matched governing spec identity drift")
        forced = forced or "auto_retry_exhausted"
        resolved, name, status = None, "", "no_governing_spec"
    if resolved is not None:
        spec_status: dict[str, Any] = {
            "schema": _SPEC_STATUS_SCHEMA, "status": "bound", "name": name,
            "sha256": resolved.sha256, "size": resolved.size,
            "generation_id": resolved.generation_id,
            "manifest_sha256": resolved.manifest_sha256,
            "locator_channel": locator.get("channel"),
        }
        if pin_evidence:
            spec_status["pinned_by_user"] = True
            spec_status["pin_evidence"] = pin_evidence
        return spec_status
    spec_status = {
        "schema": _SPEC_STATUS_SCHEMA,
        "status": "ambiguous" if status == "ambiguous" else "no_governing_spec",
        "name": None,
        "locator_status": status,
        "resolution": forced or None,
        "unresolved_reason": lookup_unknown[1] if lookup_unknown else None,
        "locator_channel": locator.get("channel"),
        "generation_id": active.generation_id if active is not None else None,
        "manifest_sha256": active.manifest_sha256 if active is not None else None,
    }
    if status == "ambiguous":
        spec_status["references"] = build_spec_references(root, batch, out_name,
                                                          candidates)["references"]
    return spec_status


def _ticket_ids(title: str) -> set[str]:
    """nodes.py `_resolve_recompose_defect_spec` 从根标题认单号的那一段。"""
    text = str(title or "")
    match = re.match(r"^\s*(?:BUG\s*[-#：:]?\s*)?(\d{4,})(?!\d)", text, flags=re.IGNORECASE)
    if match:
        return {match.group(1)}
    return {n for n in re.findall(r"(?<!\d)(\d{4,})(?!\d)", text)
            if not re.match(r"^\d+\.\d+",
                            text[max(text.find(n) - 5, 0):text.find(n) + len(n) + 5])}


def _defect_spec(spec_status: dict[str, Any], title: str, declined: bool) -> dict[str, Any]:
    """缺陷单通道状态，形状同 nodes.py 的 `_defect_spec_*` 构造。"""
    def not_queried(reason: str) -> dict[str, Any]:
        return {"schema": _DEFECT_STATUS_SCHEMA, "status": "not_queried", "ticket_number": None,
                "eligible": False, "receipt_sha256": None, "receipt": None, "reason": reason}

    def resolved_absent(reason: str, raw_status: str = "", unresolved: str = "") -> dict[str, Any]:
        return {"schema": _DEFECT_STATUS_SCHEMA, "status": "resolved_absent",
                "raw_status": raw_status or None, "ticket_number": None, "eligible": False,
                "receipt_sha256": None, "receipt": None, "reason": reason,
                "unresolved": unresolved or None}

    if spec_status["status"] == "bound":
        return not_queried("openkm_found")
    if spec_status["status"] == "ambiguous":
        return not_queried("openkm_ambiguous")
    if declined:
        return resolved_absent("user_declined_retry")
    ids = _ticket_ids(title)
    if not ids:
        return {"schema": _DEFECT_STATUS_SCHEMA, "status": "no_ticket_reference",
                "ticket_number": None, "receipt_sha256": None, "receipt": None}
    # 引擎在这里查单并签收据；客户端没有这条通道，结果等同引擎两次查单都不可用
    raw, reason = (("unavailable", DEFECT_CHANNEL_ABSENT) if len(ids) == 1
                   else ("invalid_source", "bug_to_case_root_identity_is_not_unique"))
    return resolved_absent("auto_retry_exhausted", raw_status=raw,
                           unresolved=f"status={raw}, reason={reason}")


def _binding(source: str, spec_status: dict[str, Any], defect: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": source,
        "governing_spec": spec_status.get("name") if spec_status["status"] == "bound" else None,
        "governing_spec_status": spec_status["status"],
        "governing_spec_sha256": spec_status.get("sha256"),
        "governing_spec_generation_id": spec_status.get("generation_id"),
        "governing_spec_manifest_sha256": spec_status.get("manifest_sha256"),
        "defect_spec_status": defect["status"],
        "defect_spec_receipt_sha256": defect.get("receipt_sha256"),
    }


def _spec_view(spec_status: dict[str, Any], root: Path, batch: Path) -> dict[str, Any]:
    """给模型看的规格书结论：绑定时带可读路径，多个候选时带参考切片的本地路径。"""
    view = {k: spec_status.get(k) for k in ("status", "name", "sha256", "locator_channel",
                                            "resolution", "unresolved_reason")
            if spec_status.get(k) is not None}
    if spec_status["status"] == "bound":
        view["path"] = str(root / "knowledge" / "data" / "spec" / "generations"
                           / spec_status["generation_id"] / "docs" / spec_status["name"])
    references = []
    for ref in spec_status.get("references") or []:
        references.append({"name": ref.get("name"), "anchor": ref.get("anchor"),
                           "evidence": ref.get("evidence"),
                           "path": str(batch / "spec_references" / str(ref.get("name")))})
    if references:
        view["references"] = references
    return view


def prepare(ws: Workspace, mindmap: str, *, out_name: str = "", spec: str = "") -> dict[str, Any]:
    root, info = engine_env.prepare(ws)
    from cex_core.engine.case_compiler.contract_entry import write_json_atomic
    from cex_core.engine.case_compiler.mindmap_contract_projector import (
        closed_mindmap_case_autoids,
        consistency_source_atoms_for_brief,
    )
    from cex_core.engine.ist_core.tools.device.recompose_submission import (
        initialize_machine_mindmap_submission,
    )

    source_file = _mindmap_file(ws, mindmap)
    raw = source_file.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ClientError("the mindmap is not UTF-8") from None
    titles = _root_titles(text)
    if len(titles) != 1:
        raise ClientError(f"the mindmap must have exactly one root title (found {len(titles)})")
    name = safe_component(out_name or source_file.stem, "batch name")
    outputs = ws.outputs_dir
    batch = outputs / name
    batch.mkdir(parents=True, exist_ok=True)
    pin = str(spec or "").strip()
    declined = pin.lower() == "none"
    spec_status = _governing_spec(root, batch, name, titles[0], "" if declined else pin, declined)
    defect = _defect_spec(spec_status, titles[0], declined)
    snapshot = batch / "mindmap_source.json"
    if not snapshot.is_file() or snapshot.read_bytes() != raw:
        tmp = batch / ".mindmap_source.json.tmp"
        tmp.write_bytes(raw)
        os.replace(tmp, snapshot)
    write_json_atomic(batch / "governing_spec_status.json", spec_status)
    write_json_atomic(batch / "defect_spec_status.json", defect)
    source_sha = hashlib.sha256(raw).hexdigest()
    binding = _binding(snapshot.relative_to(ws.root).as_posix(), spec_status, defect)
    autoids = tuple(closed_mindmap_case_autoids(text.lstrip(_STRIP)))
    was_sealed = _is_sealed(batch)
    dispatch_id = uuid.uuid4().hex
    _receipt, already = initialize_machine_mindmap_submission(
        outputs, name, dispatch_id, binding=binding, case_autoids=autoids,
        source_sha256=source_sha)
    write_private_json(_state_path(ws, name), {
        "schema": STATE_SCHEMA, "out_name": name, "dispatch_id": dispatch_id,
        "source_sha256": source_sha, "binding": binding, "data_root": str(root),
        "bundle_id": info.get("bundle_id")})
    remaining = [aid for aid in autoids if aid not in set(already)]
    result = {
        "ok": True, "out_name": name, "mindmap_snapshot": str(snapshot),
        "root_title": titles[0], "build": info.get("build"), "case_count": len(autoids),
        "case_autoids": list(autoids), "already_recorded": list(already),
        "outstanding_autoids": remaining,
        "governing_spec": _spec_view(spec_status, root, batch),
        "defect_spec_status": defect["status"],
        "defect_spec_receipt_sha256": defect.get("receipt_sha256"),
        "consistency_source_atoms": consistency_source_atoms_for_brief(text.lstrip(_STRIP)),
        "spec_bundle": info.get("spec"),
        "next": ("Recompose the outstanding cases and record them with "
                 "cex_recompose_submit_cases as you finish them; then call cex_recompose_seal."),
    }
    if was_sealed:
        # 重开会删掉已密封的 machine_mindmap.json：编写阶段据它出的契约卡随即失去出处
        authoring = (ws.state_dir / "author" / f"{name}.json").is_file()
        result["reopened_seal"] = True
        result["warning"] = (
            "This batch was sealed. Preparing it again reopened it and removed the sealed "
            "machine_mindmap.json; recorded cases stay recorded. Seal it again with "
            "cex_recompose_seal before any cex_author_* call"
            + ("; authoring has started on this batch, so re-run cex_author_prepare after sealing "
               "(authoring refuses to continue on an unsealed batch)" if authoring else "") + ".")
        if not remaining:
            result["next"] = "Every case is already recorded: call cex_recompose_seal now."
    if defect.get("unresolved"):
        result["defect_spec_note"] = (
            "The root title names a ticket, but this client cannot bind a DefectSpec "
            "projection; the status is resolved_absent. cex_bug_get can read the ticket for "
            "discovery only - it never becomes a contract source.")
    return result


def _is_sealed(batch: Path) -> bool:
    """批目录现在是否处于密封态（提交回执是 submitted 且机械脑图在）。"""
    try:
        receipt = json.loads((batch / ".machine_mindmap_submission.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return receipt.get("status") == "submitted" and (batch / "machine_mindmap.json").is_file()


def _scope(ws: Workspace, out_name: str):
    state = _load_state(ws, out_name)
    engine_env.activate(Path(state["data_root"]))
    from cex_core.engine.ist_core.tools.device.recompose_submission import (
        recompose_dispatch_scope,
    )

    return state, recompose_dispatch_scope(ws.outputs_dir, state["out_name"], state["dispatch_id"])


def submit_cases(ws: Workspace, out_name: str, cases: Any) -> dict[str, Any]:
    state, scope = _scope(ws, out_name)
    from cex_core.engine.ist_core.tools.device.recompose_submit_tool import (
        submit_machine_mindmap_cases,
    )

    with scope:
        raw = submit_machine_mindmap_cases.func(cases=cases)
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        return {"ok": False, "status": "rejected", "detail": str(raw)[:4000]}
    return {"ok": result.get("status") != "rejected", **result}


def seal(ws: Workspace, out_name: str) -> dict[str, Any]:
    """nodes.py `_engine_seal_from_parts`：把台账上已落盘的案密封成机械脑图。缺的案不补写，
    由密封层按作者原文兜底并在结果里点名。"""
    state, _scope_unused = _scope(ws, out_name)
    from cex_core.engine.case_compiler.mindmap_contract_projector import fill_mechanical_fields
    from cex_core.engine.ist_core.tools.device.recompose_parts import read_machine_mindmap_parts
    from cex_core.engine.ist_core.tools.device.recompose_submission import (
        machine_mindmap_artifact_path,
        submit_machine_mindmap_payload,
        verify_machine_mindmap_submission_commit,
    )

    outputs, name, dispatch_id = ws.outputs_dir, state["out_name"], state["dispatch_id"]
    binding = state["binding"]
    text = (outputs / name / "mindmap_source.json").read_bytes().decode("utf-8")
    snapshot = read_machine_mindmap_parts(outputs, name, binding_sha256=None,
                                          source_sha256=state["source_sha256"])
    doc = {"cases": [dict(snapshot.cases[aid]) for aid in snapshot.case_autoids
                     if aid in snapshot.cases]}
    fill_mechanical_fields(doc, text.lstrip(_STRIP))
    submit_machine_mindmap_payload(outputs, name, dispatch_id, {
        "schema": "ist.machine-mindmap",
        "source": binding["source"],
        "governing_spec": binding["governing_spec"],
        "defect_spec_status": binding["defect_spec_status"],
        "defect_spec_receipt_sha256": binding["defect_spec_receipt_sha256"],
        "cases": doc["cases"],
        "case_count": len(doc["cases"]),
    })
    verify_machine_mindmap_submission_commit(outputs, name, dispatch_id, expected_binding=binding)
    sealed = [str(case.get("autoid") or "") for case in doc["cases"]]
    missing = [aid for aid in snapshot.case_autoids if aid not in set(sealed)]
    return {"ok": True, "artifact": str(machine_mindmap_artifact_path(outputs, name)),
            "case_count": len(snapshot.case_autoids), "sealed_case_count": len(sealed),
            "missing_autoids": missing,
            "note": ("Cases missing from the ledger fall back to the author's original text in "
                     "the sealed mindmap." if missing else "")}


def lang_query(ws: Workspace, args: dict[str, Any], out_name: str = "") -> dict[str, Any]:
    """InfoTest lang_query 同一函数；给了批名就在那一批的派发作用域里查（引擎会把命令查询
    记进该批的 grounding）。结果里的文件路径相对引擎数据根（data_root）。

    批次已密封时派发作用域已关：查询照常给结果，只是不再记进这一批的 grounding——编写阶段
    同样要查参数契约与出处，不能因为重组已封就查不了。"""
    scope = None
    note = None
    if out_name:
        state = _load_state(ws, out_name)
        root = Path(state["data_root"])
        if _is_sealed(ws.outputs_dir / state["out_name"]):
            engine_env.activate(root)
            note = ("the recompose batch is sealed, so this lookup is not recorded in its "
                    "grounding; the result is the same")
        else:
            state, scope = _scope(ws, out_name)
    else:
        root, _info = engine_env.prepare(ws)
    from cex_core.engine.ist_core.tools.device.lang_query_tool import lang_query as tool

    kwargs = {k: args[k] for k in ("kind", "name", "domain", "query", "position") if k in args}
    if scope is None:
        result = tool.func(**kwargs)
    else:
        with scope:
            result = tool.func(**kwargs)
    out = {"ok": True, "data_root": str(root), "result": result}
    if note:
        out["note"] = note
    return out


__all__ = ["lang_query", "prepare", "seal", "submit_cases"]
