# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/recompose_submit_tool.py（sha256 1978bd91b94b7645）。不在这里手改。
from __future__ import annotations
import json
import logging
import threading
from pathlib import Path
from typing import Any
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field
from cex_core.engine.case_compiler.step_structure import LEGAL_FORM_ENTRY, STEP_STRUCTURE_KEY, apply_engine_slots, budget_violations, distribution_criterion_bindings, normalized_expectations_for_case, object_kind_closed_set, step_structure_violations, strip_engine_slots
from cex_core.engine.ist_core.tools.device.recompose_parts import append_machine_mindmap_cases, machine_mindmap_case_value_violations, machine_mindmap_case_verbatim_violations, read_machine_mindmap_parts
from cex_core.engine.ist_core.tools.device.recompose_submission import MachineMindmapContentError, canonical_machine_mindmap_submission_result, current_recompose_assignment, current_recompose_dispatch, machine_mindmap_submission_open_guard, read_machine_mindmap_submission, submit_machine_mindmap_payload
_PARTS_COMPLETE_NEXT = 'All dispatched cases are recorded. The only legal next action is to call submit_machine_mindmap now to seal; further submit_machine_mindmap_cases calls will be rejected.'
_SHARD_COMPLETE_NEXT = 'Every case assigned to this dispatch is recorded. Do not call submit_machine_mindmap: sibling shards may still be running and the engine seals the batch itself once the whole set is recorded. Finish your turn with the Chinese report.'

def _scope_outstanding(ledger_missing: tuple[str, ...], assigned: tuple[str, ...]) -> list[str]:
    if not assigned:
        return list(ledger_missing)
    scope = set(assigned)
    return [aid for aid in ledger_missing if aid in scope]

def current_dispatch_outstanding_autoids() -> tuple[str, ...] | None:
    try:
        outputs_root, out_name, _ = current_recompose_dispatch()
        assigned = current_recompose_assignment()
        ledger = read_machine_mindmap_parts(outputs_root, out_name)
    except Exception:
        return None
    return tuple(_scope_outstanding(ledger.missing_autoids, assigned))
logger = logging.getLogger(__name__)

def _rejected(schema: str, violations: list[dict[str, Any]]) -> str:
    return json.dumps({'schema': schema, 'status': 'rejected', 'violations': violations}, ensure_ascii=False, sort_keys=True, indent=2)
_SUBMIT_PAYLOAD_STREAKS: dict[str, int] = {}
_SUBMIT_PAYLOAD_STREAK_LOCK = threading.Lock()

def _bump_submit_payload_streak(key: str) -> int:
    with _SUBMIT_PAYLOAD_STREAK_LOCK:
        value = _SUBMIT_PAYLOAD_STREAKS.get(key, 0) + 1
        _SUBMIT_PAYLOAD_STREAKS[key] = value
        return value

def _reset_submit_payload_streak(key: str) -> None:
    with _SUBMIT_PAYLOAD_STREAK_LOCK:
        _SUBMIT_PAYLOAD_STREAKS.pop(key, None)

def _payload_reject(code: str, locus: str, detail: str, *, streak: int | None=None, json_decode_error: dict[str, Any] | None=None) -> tuple[None, str]:
    if streak is not None and streak >= 2:
        detail += ' → Two consecutive payload-channel failures were observed; their cause is not established. Do not repeat the unchanged payload. If it cannot be corrected within the remaining budget, finish per your report contract and include this receipt verbatim. This receipt establishes neither content validity nor fault ownership.'
    violation: dict[str, Any] = {'code': code, 'locus': locus, 'detail': detail}
    if json_decode_error is not None:
        violation['json_decode_error'] = json_decode_error
    return (None, _rejected('ist.machine-mindmap-parts-result', [violation]))

def _resolve_cases_payload(cases: Any, cases_path: str, *, out_name: str, dispatch_id: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """载荷通道优先级：原生数组 > 文件通道 > 字符串化数组（体内容错）。

    实证（2026-09-20 批 Bug77137_0920_1 s5、_2 s4 两轮）：cases 数组经端点序列化
    后成畸形字符串，单收原生数组的 pydantic 口直接拒、只说 "do not repeat the
    rejected payload"，模型没有更好的改法只能同形重交，烧穿 tool-budget。双收
    字符串通道 + 畸形时结构化拒收止血；重复失败只记次数与原始错误，不从载荷形状推断故障责任。
    预算内无可用修法时按合法报告契约收口。回执文案不提 fs_write/cases_path：本工具只挂在引擎 trusted
    投影面（loader._projected…：fs_read/fs_grep/lang_query+提交口），该面按设计
    不开放写文件工具——指一条不存在的门比不指更烧预算（s4 十一次拒收实证）。
    cases_path 参数保留：程序侧/未来有写面的派发可用。畸形载荷不落账。
    """
    streak_key = f'{out_name}:{dispatch_id}'
    reissue_hint = 'Re-issue the call once with the same case content as a compact native array: trim free-form prose (notes, reasons, basis), keep every verbatim atom exactly as authored.'
    if isinstance(cases, list) and cases:
        return (list(cases), None)
    if isinstance(cases, list) and (not (cases_path or '').strip()):
        return ([], None)
    text = ''
    locus = 'cases'
    if (cases_path or '').strip():
        locus = 'cases_path'
        try:
            from cex_core.engine.ist_core.tools.device import _sealed_output
            target = _sealed_output.scoped_output_path(cases_path.strip())
            batch_root = _sealed_output.scoped_output_path(_sealed_output.output_root() / out_name / '.payload-channel-scope').parent
            target.relative_to(batch_root)
            text = _sealed_output.read_bytes(target, max_bytes=16 * 1024 * 1024).decode('utf-8')
        except Exception as exc:
            return _payload_reject('cases_path_unreadable', 'cases_path', f"the cases_path file could not be read ({type(exc).__name__}); it must be a regular JSON file inside the current batch's outputs directory.", streak=_bump_submit_payload_streak(streak_key))
    elif isinstance(cases, str) and cases.strip():
        text = cases
    if not text.strip():
        return _payload_reject('cases_payload_empty', 'cases', 'no payload channel carried content; the cause is not established. ' + reissue_hint, streak=_bump_submit_payload_streak(streak_key))
    try:
        from cex_core.engine.case_compiler._sealed_io import validate_json_budget
        from cex_core.engine.case_compiler.mechanical_case import _reject_constant, _reject_duplicate_keys
        if len(text.encode('utf-8')) > 16 * 1024 * 1024:
            raise ValueError('payload exceeds the byte budget')
        validate_json_budget(text, error_type=ValueError, message='payload exceeds the JSON structure budget')
        parsed = json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except Exception as exc:
        diagnostic = None
        syntax_location = ''
        if isinstance(exc, json.JSONDecodeError):
            diagnostic = {'msg': exc.msg, 'pos': exc.pos, 'lineno': exc.lineno, 'colno': exc.colno}
            syntax_location = f'JSON syntax: {exc.msg}; character offset {exc.pos} (0-based), line {exc.lineno} and column {exc.colno} (1-based). '
        return _payload_reject('cases_payload_unparseable', locus, f'the payload arrived as text that is not valid JSON ({type(exc).__name__}); ' + syntax_location + 'the cause is not established. ' + reissue_hint, streak=_bump_submit_payload_streak(streak_key), json_decode_error=diagnostic)
    if not isinstance(parsed, list) or not parsed or (not all((isinstance(entry, dict) for entry in parsed))):
        return _payload_reject('cases_payload_unparseable', locus, f'the payload must be a non-empty JSON array of case objects; got {type(parsed).__name__}. ' + reissue_hint, streak=_bump_submit_payload_streak(streak_key))
    return (parsed, None)

def _verbatim_precheck(outputs_root: Path, out_name: str, dispatch_id: str, *, source_sha256: str, cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]], str]:
    from cex_core.engine.case_compiler._sealed_io import lexical_absolute, read_regular_nofollow, sha256_bytes
    from cex_core.engine.ist_core.compile_engine import _shared as _sh
    from cex_core.engine.ist_core.tools.device.recompose_parts import MachineMindmapPartsError
    receipt = read_machine_mindmap_submission(outputs_root, out_name, dispatch_id)
    binding = receipt.binding
    root = lexical_absolute(outputs_root)
    batch = root / out_name
    raw = read_regular_nofollow(batch / 'mindmap_source.json', error_type=MachineMindmapPartsError, invalid_message='mindmap snapshot path is invalid', directory_message='mindmap snapshot directory is unavailable', open_message='mindmap snapshot is unavailable', bounds_message='mindmap snapshot exceeds its sealed size boundary', changed_message='mindmap snapshot changed while being read', max_bytes=32 * 1024 * 1024, min_bytes=1, trusted_root=root, require_current_uid=True)
    assert isinstance(raw, bytes)
    if sha256_bytes(raw) != str(source_sha256 or ''):
        raise MachineMindmapPartsError('mindmap snapshot identity drift')
    spec_text: str | None = None
    spec_name = str(binding.get('governing_spec') or '').strip()
    if spec_name:
        from cex_core.engine.kms.spec_index import resolve_indexed_spec
        resolved = resolve_indexed_spec(_sh.project_root(), spec_name)
        if resolved is None or resolved.sha256 != str(binding.get('governing_spec_sha256') or '') or resolved.generation_id != str(binding.get('governing_spec_generation_id') or '') or (resolved.manifest_sha256 != str(binding.get('governing_spec_manifest_sha256') or '')):
            raise MachineMindmapPartsError('governing spec identity drift')
        spec_text = resolved.content.decode('utf-8', errors='replace')
    defect_receipt: dict[str, Any] | None = None
    try:
        status_raw = read_regular_nofollow(batch / 'defect_spec_status.json', error_type=MachineMindmapPartsError, invalid_message='defect spec status path is invalid', directory_message='defect spec status directory is unavailable', open_message='defect spec status is unavailable', bounds_message='defect spec status exceeds its boundary', changed_message='defect spec status changed while being read', max_bytes=4 * 1024 * 1024, min_bytes=1, trusted_root=root, require_current_uid=True)
        payload = json.loads(status_raw.decode('utf-8'))
    except (MachineMindmapPartsError, ValueError, UnicodeError):
        payload = None
    candidate = payload.get('receipt') if isinstance(payload, dict) else None
    if isinstance(candidate, dict):
        if str(payload.get('receipt_sha256') or '') != str(binding.get('defect_spec_receipt_sha256') or ''):
            raise MachineMindmapPartsError('defect spec receipt identity drift')
        defect_receipt = candidate
    mindmap_text = raw.decode('utf-8', errors='replace').lstrip('\ufeff\uffff')
    verified_cases, verbatim_violations = machine_mindmap_case_verbatim_violations(cases, mindmap_text=mindmap_text, spec_text=spec_text, governing_spec=spec_name or None, governing_spec_status=str(binding.get('governing_spec_status') or '') or None, defect_spec_receipt=defect_receipt, defect_spec_status=str(binding.get('defect_spec_status') or '') or None, defect_spec_receipt_sha256=str(binding.get('defect_spec_receipt_sha256') or '') or None)
    return (verified_cases, verbatim_violations, mindmap_text)

class MachineMindmapCasesArgs(BaseModel):
    """Payload channels: native array preferred, file channel for large arrays."""
    model_config = ConfigDict(extra='forbid', strict=True)
    cases: list[dict[str, Any]] | str = Field(default='', description='One or more finished case objects — pass native JSON objects. A JSON-serialized array is also accepted. Payload errors alone do not identify their cause. Each case must carry the 18-digit `autoid` of a case in the dispatched mindmap.')
    cases_path: str = Field(default='', description="Fallback file channel: path to a JSON file inside the current batch's outputs directory containing an array of case objects, for callers that can prepare files — on an engine dispatch this surface has no write tool, so do not pass it. Wins over a stringified `cases`; a native non-empty array still wins over both.")

class MachineMindmapSubmissionArgs(BaseModel):
    """Native object submission; path and overwrite policy are not model fields."""
    model_config = ConfigDict(extra='forbid', strict=True)
    machine_mindmap: dict[str, Any] = Field(description='The producer-owned ist.machine-mindmap envelope. Pass a native JSON object, never a serialized JSON string. For an engine dispatch, omit `source`, `governing_spec`, `defect_spec_status`, and `defect_spec_receipt_sha256`; the tool injects those identities from the trusted dispatch receipt. Omit `cases` and `case_count` to seal the cases already recorded by submit_machine_mindmap_cases; include both only when submitting a complete document in one call.')

def _normalize_disclosure_shapes(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    notes = normalized.get('orphan_notes')
    if isinstance(notes, dict):
        normalized['orphan_notes'] = [str(v) for v in notes.values()]
    elif notes is None and 'orphan_notes' in normalized:
        normalized['orphan_notes'] = []
    check = normalized.get('self_check')
    if check is None and 'self_check' in normalized:
        normalized['self_check'] = {}
    return normalized

@tool(args_schema=MachineMindmapCasesArgs)
def submit_machine_mindmap_cases(cases: list[dict[str, Any]] | str='', cases_path: str='') -> str:
    """Record finished cases durably so a later stop cannot discard them.

    Call this as you finish cases, not once at the end: everything recorded here
    survives running out of tool budget, wallclock, or the fork dying, and a
    redispatch on the same source and SPEC identity resumes from it. While other
    dispatched cases remain outstanding, resubmitting an autoid replaces its earlier
    record and this call remains non-terminal; continue only with the outstanding
    cases or corrections. Once `outstanding_autoids` is empty, further case-part
    submissions are rejected and the only legal next action is
    `submit_machine_mindmap` to seal the completed set.

    Payload channels, in priority order: the native `cases` array; optionally
    `cases_path` — a JSON file inside the batch's outputs directory holding the
    same array (for callers that can prepare files; on an engine dispatch your
    tool surface has no write tool, so follow the receipt's own instructions
    instead). A JSON-serialized `cases` string is accepted too, because provider
    serialization may stringify or truncate large array arguments on their own.
    A mangled or empty payload is rejected with guidance without touching the
    ledger.

    Record only cases you have actually finished. A recorded case drops out of
    `outstanding_autoids`, so a placeholder carrying nothing but its autoid marks
    the case done and it never gets written. Such a submission is rejected.
    """
    outputs_root, out_name, dispatch_id = current_recompose_dispatch()
    assigned = current_recompose_assignment()
    cases, payload_error = _resolve_cases_payload(cases, cases_path, out_name=out_name, dispatch_id=dispatch_id)
    if payload_error is not None:
        return payload_error
    assert cases is not None
    with machine_mindmap_submission_open_guard(outputs_root, out_name, dispatch_id):
        ledger = read_machine_mindmap_parts(outputs_root, out_name)
        if not _scope_outstanding(ledger.missing_autoids, assigned):
            return _rejected('ist.machine-mindmap-parts-result', [{'code': 'case_set_complete', 'locus': 'cases', 'detail': _SHARD_COMPLETE_NEXT if assigned else _PARTS_COMPLETE_NEXT}])
        violations = machine_mindmap_case_value_violations(cases, ledger.case_autoids)
        if violations:
            return _rejected('ist.machine-mindmap-parts-result', violations)
        if assigned:
            scope = set(assigned)
            outside = sorted({aid for case in cases if (aid := str((case or {}).get('autoid') or '')) and aid not in scope})
            if outside:
                return _rejected('ist.machine-mindmap-parts-result', [{'code': 'case_outside_assignment', 'locus': 'cases', 'detail': 'This dispatch is responsible only for its assigned autoids; a sibling shard owns ' + ', '.join(outside[:8]) + '. Submit only your own outstanding cases.'}])
        verbatim_cases, verbatim_violations, mindmap_text = _verbatim_precheck(outputs_root, out_name, dispatch_id, source_sha256=ledger.source_sha256, cases=cases)
        if verbatim_violations:
            return _rejected('ist.machine-mindmap-parts-result', verbatim_violations)
        normalized_violations = machine_mindmap_case_value_violations(verbatim_cases, ledger.case_autoids)
        if normalized_violations:
            return _rejected('ist.machine-mindmap-parts-result', normalized_violations)
        structure_object_kinds = object_kind_closed_set()
        structure_rejections: list[dict[str, str]] = []
        for case_index, case in enumerate(verbatim_cases):
            strip_engine_slots(case)
            structure_rejections.extend(step_structure_violations(case, index=case_index, object_kinds=structure_object_kinds))
        if structure_rejections:
            return _rejected('ist.machine-mindmap-parts-result', budget_violations(structure_rejections))
        for case in verbatim_cases:
            try:
                apply_engine_slots(case, distribution_criterion_bindings(normalized_expectations_for_case(case, mindmap_text=mindmap_text, mindmap_source_sha256=ledger.source_sha256)))
            except Exception as exc:
                logger.warning('engine slot pairing failed for %s', str(case.get('autoid') or ''), exc_info=True)
                return _rejected('ist.machine-mindmap-parts-result', budget_violations([{'code': 'step_structure_count_out_of_range', 'locus': f"cases[{str(case.get('autoid') or '')}].{STEP_STRUCTURE_KEY}", 'detail': f"the engine could not pair this case's distribution criteria with its observation steps from the structure as submitted ({type(exc).__name__}). The engine records no sampling count of its own; it only records which observation step each distribution criterion pairs with. Check the step numbers, object roles and stated conditions of the observation steps against the authored text, within the declared bounds.", 'legal_form': LEGAL_FORM_ENTRY}]))
        snapshot = append_machine_mindmap_cases(outputs_root, out_name, dispatch_id, verbatim_cases)
    _reset_submit_payload_streak(f'{out_name}:{dispatch_id}')
    scope_outstanding = _scope_outstanding(snapshot.missing_autoids, assigned)
    result = {'schema': 'ist.machine-mindmap-parts-result', 'recorded': len(snapshot.submitted_autoids), 'total': len(snapshot.case_autoids), 'outstanding_autoids': scope_outstanding, 'artifact_sha256': snapshot.ledger_sha256}
    if not scope_outstanding:
        result['next'] = _SHARD_COMPLETE_NEXT if assigned else _PARTS_COMPLETE_NEXT
    return json.dumps(result, ensure_ascii=False, sort_keys=True)

@tool(args_schema=MachineMindmapSubmissionArgs, return_direct=True)
def submit_machine_mindmap(machine_mindmap: dict[str, Any]) -> str:
    """Seal the machine mindmap for the engine-fixed dispatch target.

    The caller cannot select a path or overwrite policy. The tool binds the payload to the
    current trusted recompose dispatch, atomically commits it once, and returns a byte-identity
    receipt. Once the engine has signed a case set for this dispatch, the cases and their order
    come from the durable per-case ledger and sealing requires every dispatched case to be
    recorded — passing `cases` yourself cannot widen or narrow that set.
    After success, no more case parts or domain tools are accepted.
    A sharded dispatch (one carrying `assigned_autoids`) must not seal at all: sibling
    shards may still be running and the engine seals the batch itself.
    """
    outputs_root, out_name, dispatch_id = current_recompose_dispatch()
    _assigned = current_recompose_assignment()
    if _assigned:
        return _rejected('ist.machine-mindmap-submission-result', [{'code': 'shard_must_not_seal', 'locus': 'machine_mindmap', 'detail': _SHARD_COMPLETE_NEXT}])
    try:
        submit_machine_mindmap_payload(outputs_root, out_name, dispatch_id, _normalize_disclosure_shapes(machine_mindmap))
    except MachineMindmapContentError as exc:
        return _rejected('ist.machine-mindmap-submission-result', [{'code': exc.code, 'locus': 'machine_mindmap', 'detail': str(exc)}])
    return canonical_machine_mindmap_submission_result(outputs_root, out_name, dispatch_id)
__all__ = ['MachineMindmapCasesArgs', 'MachineMindmapSubmissionArgs', 'submit_machine_mindmap', 'submit_machine_mindmap_cases']
