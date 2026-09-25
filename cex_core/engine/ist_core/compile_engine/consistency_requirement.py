# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/consistency_requirement.py（sha256 335d3955cbfa2c92）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from cex_core.engine.case_compiler._sealed_io import lexical_absolute, lexical_path_inside_root, read_regular_nofollow, sha256_bytes, validate_json_budget
from cex_core.engine.case_compiler.mindmap_contract_projector import projection_receipt_valid
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.ist_core.compile_engine import conflict_chain as CC
from cex_core.engine.ist_core.compile_engine import facts as F
PROOF_SCHEMA = 'ist.consistency-requirement-proof'
REQUIRED = 'required'
NOT_APPLICABLE = 'not_applicable_no_governing_spec'
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_PROOF_KEYS = frozenset({'schema', 'autoid', 'batch_name', 'requirement', 'binding_status', 'base_contract_sha256', 'machine_mindmap_sha256', 'projection_sha256', 'governing_spec_status', 'governing_spec_status_sha256', 'defect_spec_status', 'defect_spec_status_sha256', 'defect_spec_receipt_sha256'})

class ConsistencyRequirementError(ValueError):

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f'{self.code}: {self.detail}')

def _raise(code: str, detail: str) -> None:
    raise ConsistencyRequirementError(code, detail)

def _safe_component(value: object, *, field: str) -> str:
    name = str(value or '').strip()
    if not name or name in {'.', '..'} or Path(name).is_absolute() or ('/' in name) or ('\\' in name) or ('~' in name) or any((ord(ch) < 32 for ch in name)) or (len(name) > 180):
        _raise('batch_identity_invalid', f'{field} is not one safe output component')
    return name

def batch_name_from_contract_ref(*, project_root: str | Path, outputs_root: str | Path, autoid: str, contract_ref: str) -> str:
    aid = _safe_component(autoid, field='autoid')
    project = lexical_absolute(project_root)
    outputs = lexical_absolute(outputs_root)
    try:
        path = lexical_path_inside_root(project / str(contract_ref or ''), outputs, error_type=ValueError, traversal_message='contract ref traversal is forbidden', outside_message='contract ref escaped outputs root')
    except ValueError as exc:
        _raise('batch_identity_invalid', str(exc))
    if path.name != f'{aid}.json' or path.parent.name != 'contracts':
        _raise('batch_identity_invalid', 'base contract is not the bound contracts/<autoid>.json sibling')
    batch_dir = path.parent.parent
    if batch_dir.parent != outputs:
        _raise('batch_identity_invalid', 'base contract batch is not a direct output child')
    return _safe_component(batch_dir.name, field='batch_name')

def _read_status(path: Path, *, kind: str, max_bytes: int) -> tuple[dict[str, Any], bytes]:
    code = f'{kind}_status_unavailable'
    try:
        raw = read_regular_nofollow(path, trusted_root=path.parent, error_type=ValueError, invalid_message=f'{kind} status path is invalid', directory_message=f'{kind} status directory is unavailable', open_message=f'{kind} status is unavailable', bounds_message=f'{kind} status exceeds its sealed size boundary', changed_message=f'{kind} status changed while being read', max_bytes=max_bytes, min_bytes=1, require_current_uid=True)
        assert isinstance(raw, bytes)
        validate_json_budget(raw, error_type=ValueError, message=f'{kind} status exceeds the JSON structure budget', max_tokens=100000)
        payload = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        _raise(code, f'{type(exc).__name__}: {exc}')
    if not isinstance(payload, dict):
        _raise(f'{kind}_status_invalid', f'{kind} status must be a JSON object')
    return (payload, raw)

def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
RESEAL_TRIGGER_EVENTS = frozenset({'criterion_rule_updated'})

def sealed_projection_reseal_trigger(facts: Sequence[Mapping[str, Any]], *, receipt_index: int, case_ids: frozenset[str] | set[str]) -> str:
    """封存的机械投影要不要重封：命中就返回触发事件名，否则返回空串。

    `receipt_index` 是上一条 `recompose_done` 在 `facts` 里的下标（没有就传 -1）；
    `case_ids` 是本批 manifest 的案闭集，只用于把别批的事件挡在外面。
    """
    for index in range(max(int(receipt_index), -1) + 1, len(facts)):
        fact = facts[index]
        if not isinstance(fact, Mapping):
            continue
        event = str(fact.get('ev') or '')
        if event not in RESEAL_TRIGGER_EVENTS:
            continue
        aid = str(fact.get('aid') or '')
        if aid and aid not in case_ids:
            continue
        return event
    return ''

def _latest_recompose(batch_dir: Path, *, autoid: str, facts: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    if facts is None:
        try:
            loaded: Sequence[Mapping[str, Any]] = F.load_facts(batch_dir / 'facts.jsonl')
        except Exception as exc:
            _raise('facts_unavailable', f'{type(exc).__name__}: {exc}')
    else:
        loaded = facts
    if not isinstance(loaded, Sequence) or isinstance(loaded, (str, bytes)):
        _raise('facts_invalid', 'facts must be a sequence of JSON objects')
    receipt_index = -1
    receipt: dict[str, Any] | None = None
    for index in range(len(loaded) - 1, -1, -1):
        item = loaded[index]
        if isinstance(item, Mapping) and item.get('ev') == 'recompose_done':
            receipt_index = index
            receipt = dict(item)
            break
    if receipt is None:
        _raise('recompose_receipt_missing', 'latest recompose_done is unavailable')
    if any((isinstance(item, Mapping) and item.get('ev') == 'conflict_chain_reentered' and (str(item.get('aid') or '') in {'', autoid}) for item in loaded[receipt_index + 1:])):
        _raise('recompose_receipt_superseded', 'latest projection was invalidated by reentry')
    return receipt

def resolve_consistency_requirement(*, outputs_root: str | Path, project_root: str | Path, batch_name: str, autoid: str, facts: Sequence[Mapping[str, Any]] | None=None) -> dict[str, Any]:
    outputs = lexical_absolute(outputs_root)
    project = lexical_absolute(project_root)
    batch = _safe_component(batch_name, field='batch_name')
    aid = _safe_component(autoid, field='autoid')
    batch_dir = lexical_absolute(outputs / batch)
    if batch_dir.parent != outputs:
        _raise('batch_identity_invalid', 'batch is not a direct output child')
    receipt = _latest_recompose(batch_dir, autoid=aid, facts=facts)
    if not projection_receipt_valid(batch_dir, receipt):
        _raise('projection_receipt_invalid', 'latest projection receipt is not byte-closed')
    contract_map = receipt.get('contract_sha256_by_autoid')
    written = receipt.get('written_autoids')
    contract_sha = str(contract_map.get(aid) or '') if isinstance(contract_map, dict) else ''
    if _SHA256_RE.fullmatch(contract_sha) is None or not isinstance(written, list) or written.count(aid) != 1:
        _raise('contract_identity_missing', 'autoid is absent or duplicated in the signed projection contract map')
    governing, governing_raw = _read_status(batch_dir / 'governing_spec_status.json', kind='governing_spec', max_bytes=1024 * 1024)
    expected_governing_sha = str(receipt.get('governing_spec_status_sha256') or '')
    if _SHA256_RE.fullmatch(expected_governing_sha) is None or sha256_bytes(governing_raw) != expected_governing_sha:
        _raise('governing_spec_status_sha256_mismatch', 'governing status bytes differ from recompose_done')
    governing_status = str(governing.get('status') or '')
    if not accepts_schema(governing.get('schema'), 'ist.governing-spec-status') or not governing_status or governing_status != str(receipt.get('governing_spec_status') or ''):
        _raise('governing_spec_status_identity_mismatch', 'governing status payload differs from recompose_done')
    governing_pairs = (('name', 'governing_spec'), ('sha256', 'governing_spec_sha256'), ('size', 'governing_spec_size'), ('generation_id', 'governing_spec_generation_id'), ('manifest_sha256', 'governing_spec_manifest_sha256'))
    if any((governing.get(sidecar_key) != receipt.get(receipt_key) for sidecar_key, receipt_key in governing_pairs)):
        _raise('governing_spec_status_identity_mismatch', 'governing status source identity differs from recompose_done')
    defect, defect_raw = _read_status(batch_dir / 'defect_spec_status.json', kind='defect_spec', max_bytes=4 * 1024 * 1024)
    expected_defect_sha = str(receipt.get('defect_spec_status_sha256') or '')
    if _SHA256_RE.fullmatch(expected_defect_sha) is None or sha256_bytes(defect_raw) != expected_defect_sha:
        _raise('defect_spec_status_sha256_mismatch', 'DefectSpec status bytes differ from recompose_done')
    defect_status = str(defect.get('status') or '')
    defect_receipt_sha = defect.get('receipt_sha256')
    fact_defect_receipt_sha = receipt.get('defect_spec_receipt_sha256')
    if not accepts_schema(defect.get('schema'), 'ist.defect-spec-status') or not defect_status or defect_status != str(receipt.get('defect_spec_status') or '') or (defect_receipt_sha != fact_defect_receipt_sha):
        _raise('defect_spec_status_identity_mismatch', 'DefectSpec status payload differs from recompose_done')
    embedded_receipt = defect.get('receipt')
    if isinstance(embedded_receipt, dict):
        if _SHA256_RE.fullmatch(str(defect_receipt_sha or '')) is None or _canonical_sha256(embedded_receipt) != defect_receipt_sha:
            _raise('defect_spec_receipt_sha256_mismatch', 'DefectSpec receipt digest differs from its status sidecar')
    elif embedded_receipt is not None or defect_receipt_sha is not None:
        _raise('defect_spec_receipt_sha256_mismatch', 'DefectSpec receipt and receipt_sha256 must be present together')
    if defect_status == 'resolved' and (defect.get('eligible') is not True or not isinstance(embedded_receipt, dict)):
        _raise('defect_spec_status_identity_mismatch', 'resolved DefectSpec lacks an eligible sealed receipt')
    requirement = REQUIRED if not CC.spec_absent(governing_status) or defect_status == 'resolved' else NOT_APPLICABLE
    proof = {'schema': PROOF_SCHEMA, 'autoid': aid, 'batch_name': batch, 'requirement': requirement, 'binding_status': 'not_applicable' if requirement == NOT_APPLICABLE else 'pending', 'base_contract_sha256': contract_sha, 'machine_mindmap_sha256': str(receipt.get('machine_mindmap_sha256') or ''), 'projection_sha256': str(receipt.get('projection_sha256') or receipt.get('disclosure_sha256') or ''), 'governing_spec_status': governing_status, 'governing_spec_status_sha256': expected_governing_sha, 'defect_spec_status': defect_status, 'defect_spec_status_sha256': expected_defect_sha, 'defect_spec_receipt_sha256': defect_receipt_sha}
    if set(proof) != _PROOF_KEYS:
        _raise('proof_shape_invalid', 'consistency requirement proof keys drifted')
    if _SHA256_RE.fullmatch(proof['machine_mindmap_sha256']) is None or _SHA256_RE.fullmatch(proof['projection_sha256']) is None:
        _raise('projection_receipt_invalid', 'projection identity is incomplete')
    return proof

def validate_consistency_requirement(*, outputs_root: str | Path, project_root: str | Path, batch_name: str, autoid: str, intent: Mapping[str, Any], require_complete: bool=False, facts: Sequence[Mapping[str, Any]] | None=None) -> dict[str, Any]:
    proof = resolve_consistency_requirement(outputs_root=outputs_root, project_root=project_root, batch_name=batch_name, autoid=autoid, facts=facts)
    aid = proof['autoid']
    if not isinstance(intent, Mapping) or str(intent.get('autoid') or '') != aid:
        _raise('intent_identity_invalid', 'intent autoid is absent or drifted')
    expected_contract = lexical_absolute(lexical_absolute(outputs_root) / proof['batch_name'] / 'contracts' / f'{aid}.json')
    try:
        expected_contract_ref = str(expected_contract.relative_to(lexical_absolute(project_root)))
    except ValueError:
        _raise('intent_contract_identity_mismatch', 'contract path escaped project root')
    if intent.get('typed_expectation_contract_path') != expected_contract_ref or intent.get('typed_expectation_contract_sha256') != proof['base_contract_sha256']:
        _raise('intent_contract_identity_mismatch', 'intent base contract differs from the signed projection contract map')
    if str(intent.get('governing_spec_status') or '') != proof['governing_spec_status']:
        _raise('intent_governing_status_mismatch', 'intent governing status differs from the signed status sidecar')
    if str(intent.get('consistency_requirement') or '') != proof['requirement']:
        _raise('intent_requirement_mismatch', 'intent consistency requirement differs from cross-ledger evidence')
    status = str(intent.get('consistency_binding_status') or '')
    overlay_path = intent.get('consistency_contract_path')
    overlay_sha = intent.get('consistency_contract_sha256')
    receipt_sha = intent.get('consistency_receipt_sha256')
    if proof['requirement'] == NOT_APPLICABLE:
        if status != 'not_applicable' or overlay_path is not None or overlay_sha is not None or (receipt_sha is not None):
            _raise('intent_binding_invalid', 'not-applicable intent must keep every overlay identity null')
    elif status == 'pending':
        if require_complete:
            _raise('intent_binding_incomplete', 'required overlay binding is pending')
        if overlay_path is not None or overlay_sha is not None or receipt_sha is not None:
            _raise('intent_binding_invalid', 'pending required intent cannot predeclare overlay identities')
    elif status == 'complete':
        expected_overlay = lexical_absolute(outputs_root) / aid / 'consistency_contract.json'
        try:
            expected_overlay_ref = str(expected_overlay.relative_to(lexical_absolute(project_root)))
        except ValueError:
            _raise('intent_binding_invalid', 'overlay path escaped project root')
        if overlay_path != expected_overlay_ref or _SHA256_RE.fullmatch(str(overlay_sha or '')) is None or _SHA256_RE.fullmatch(str(receipt_sha or '')) is None:
            _raise('intent_binding_invalid', 'complete required intent has an invalid overlay identity')
    else:
        _raise('intent_binding_invalid', 'required intent binding status is not closed')
    return proof

def validate_recorded_consistency_requirement_proof(*, outputs_root: str | Path, project_root: str | Path, autoid: str, intent: Mapping[str, Any], recorded_proof: Mapping[str, Any], require_complete: bool=True) -> dict[str, Any]:
    if not isinstance(recorded_proof, Mapping) or set(recorded_proof) != _PROOF_KEYS or recorded_proof.get('schema') != PROOF_SCHEMA or (str(recorded_proof.get('autoid') or '') != str(autoid or '')):
        _raise('recorded_proof_shape_invalid', 'lint credential consistency proof has an invalid exact-key shape')
    batch_name = _safe_component(recorded_proof.get('batch_name'), field='batch_name')
    fresh = validate_consistency_requirement(outputs_root=outputs_root, project_root=project_root, batch_name=batch_name, autoid=autoid, intent=intent, require_complete=require_complete)
    if _canonical_sha256(dict(recorded_proof)) != _canonical_sha256(fresh):
        _raise('recorded_proof_identity_mismatch', 'lint credential consistency proof differs from current sealed batch evidence')
    return fresh
__all__ = ['ConsistencyRequirementError', 'NOT_APPLICABLE', 'PROOF_SCHEMA', 'REQUIRED', 'RESEAL_TRIGGER_EVENTS', 'batch_name_from_contract_ref', 'resolve_consistency_requirement', 'sealed_projection_reseal_trigger', 'validate_recorded_consistency_requirement_proof', 'validate_consistency_requirement']
