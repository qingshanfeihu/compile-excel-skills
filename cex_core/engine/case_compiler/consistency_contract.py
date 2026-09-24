# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/consistency_contract.py（sha256 d5b179f4a989901c）。不在这里手改。
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Mapping
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, canonical_json, read_regular_nofollow, sha256_bytes, validate_json_budget
from cex_core.engine.case_compiler.mindmap_contract_projector import _CONSISTENCY_MATERIAL_KEYS, _CONSISTENCY_MATERIAL_SCHEMA, _expectation_id, _norm_ws, _source_atom_forms
from cex_core.engine.engine_managed_outputs import CONSISTENCY_CONTRACT_SIDECAR_NAME
CONSISTENCY_CONTRACT_SCHEMA = 'ist.consistency-contract'
SPEC_ENDORSEMENT_SCHEMA = 'ist.spec-endorsement'
SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY = 1
SPEC_ENDORSEMENT_EXPECTATION_BINDING_SCHEMA = 'ist.spec-endorsement-expectation-binding'
_AUTOID_RE = re.compile('^[0-9]{18}$')
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_OUTER_KEYS = frozenset({'schema', 'autoid', 'base_contract_sha256', 'consistency_receipt_sha256', 'spec_endorsement'})
_ENDORSEMENT_KEYS = frozenset({'schema', 'authority_groups', 'scope', 'spec_quote', 'spec_locator', 'case_quote', 'case_locator'})
_MAX_BYTES = 256 * 1024

class ConsistencyContractError(ValueError):
    pass

def spec_endorsement_expectation_binding_rule() -> dict[str, Any]:
    return {'schema': SPEC_ENDORSEMENT_EXPECTATION_BINDING_SCHEMA, 'applies_when': {'spec_endorsement.scope.kind': 'expectation'}, 'base_expectation_count': {'comparison': 'exactly', 'value': SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY}, 'mechanical_assertion_binding_count': {'comparison': 'exactly', 'value': SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY}, 'note': 'Read the engine-minted consistency_contract.json after an accepted consistent verdict. When its spec_endorsement scope names one expectation_id, that id is governed by these exact cardinalities; the general rule that permits differentiated assertions to share an expectation_id does not apply to the endorsed id.'}

def consistency_material_receipt_sha256(material: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(dict(material), ensure_ascii=False))

def _base_expectation_ids(contract: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in contract.get('expectations') or []:
        if not isinstance(item, Mapping):
            continue
        carrier = next((item.get(key) for key in ('assertion', 'author_claim', 'defect_spec_claim') if isinstance(item.get(key), Mapping)), None)
        if isinstance(carrier, Mapping):
            ids.append(str(carrier.get('expectation_id') or ''))
    return ids

def _expectation_scope(machine_case: Mapping[str, Any], material: Mapping[str, Any], base_contract: Mapping[str, Any]) -> dict[str, str]:
    locator = str(material.get('case_locator') or '')
    quote = _norm_ws(str(material.get('case_quote') or ''))
    autoid = str(material.get('autoid') or '')
    candidates: list[str] = []
    for index, item in enumerate(machine_case.get('expectations_by_step') or [], start=1):
        if not isinstance(item, Mapping) or str(item.get('origin') or '') != locator:
            continue
        source_text = str(item.get('text') or '')
        if quote not in {_norm_ws(form) for form in _source_atom_forms(source_text, locator)}:
            continue
        step = str(item.get('n') or '').strip()
        if step:
            candidates.append(_expectation_id(autoid, step, index))
    base_ids = _base_expectation_ids(base_contract)
    unique = set(candidates)
    if len(unique) == SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY:
        expectation_id = next(iter(unique))
        if candidates.count(expectation_id) == SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY and base_ids.count(expectation_id) == SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY:
            return {'kind': 'expectation', 'expectation_id': expectation_id}
    return {'kind': 'case'}

def build_consistency_contract(*, autoid: str, base_contract: Mapping[str, Any], base_contract_sha256: str, accepted_material: Mapping[str, Any], machine_case: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(accepted_material)
    receipt = consistency_material_receipt_sha256(material)
    if _AUTOID_RE.fullmatch(str(autoid or '')) is None or str(base_contract.get('autoid') or '') != autoid or str(material.get('autoid') or '') != autoid or (set(material) != _CONSISTENCY_MATERIAL_KEYS) or (material.get('schema') != _CONSISTENCY_MATERIAL_SCHEMA) or (material.get('verdict') != 'consistent') or (_SHA256_RE.fullmatch(str(base_contract_sha256 or '')) is None):
        raise ConsistencyContractError('consistency_contract_identity_or_material_invalid')
    endorsement = {'schema': SPEC_ENDORSEMENT_SCHEMA, 'authority_groups': ['Spec', 'Author'], 'scope': _expectation_scope(machine_case, material, base_contract), 'spec_quote': str(material['spec_quote']), 'spec_locator': str(material['spec_locator']), 'case_quote': str(material['case_quote']), 'case_locator': str(material['case_locator'])}
    return {'schema': CONSISTENCY_CONTRACT_SCHEMA, 'autoid': autoid, 'base_contract_sha256': base_contract_sha256, 'consistency_receipt_sha256': receipt, 'spec_endorsement': endorsement}

def validate_consistency_contract(overlay: Mapping[str, Any], *, base_contract: Mapping[str, Any], base_contract_sha256: str, accepted_material: Mapping[str, Any], consistency_receipt_sha256: str, machine_case: Mapping[str, Any] | None=None) -> str:
    if not isinstance(overlay, Mapping) or set(overlay) != _OUTER_KEYS:
        return 'consistency_contract_schema_keys_invalid'
    material = dict(accepted_material)
    autoid = str(material.get('autoid') or '')
    if overlay.get('schema') != CONSISTENCY_CONTRACT_SCHEMA or _AUTOID_RE.fullmatch(autoid) is None or overlay.get('autoid') != autoid or (str(base_contract.get('autoid') or '') != autoid) or (str(overlay.get('base_contract_sha256') or '') != base_contract_sha256) or (_SHA256_RE.fullmatch(str(base_contract_sha256 or '')) is None) or (set(material) != _CONSISTENCY_MATERIAL_KEYS) or (material.get('schema') != _CONSISTENCY_MATERIAL_SCHEMA) or (material.get('verdict') != 'consistent'):
        return 'consistency_contract_identity_invalid'
    material_receipt = consistency_material_receipt_sha256(material)
    if material_receipt != consistency_receipt_sha256 or overlay.get('consistency_receipt_sha256') != consistency_receipt_sha256:
        return 'consistency_contract_receipt_invalid'
    endorsement = overlay.get('spec_endorsement')
    if not isinstance(endorsement, Mapping) or set(endorsement) != _ENDORSEMENT_KEYS:
        return 'spec_endorsement_schema_keys_invalid'
    if endorsement.get('schema') != SPEC_ENDORSEMENT_SCHEMA or endorsement.get('authority_groups') != ['Spec', 'Author'] or any((endorsement.get(field) != material.get(field) for field in ('spec_quote', 'spec_locator', 'case_quote', 'case_locator'))):
        return 'spec_endorsement_material_invalid'
    scope = endorsement.get('scope')
    if not isinstance(scope, Mapping):
        return 'spec_endorsement_scope_invalid'
    recomputed_scope = _expectation_scope(machine_case, material, base_contract) if machine_case is not None else None
    if scope.get('kind') == 'case':
        if set(scope) != {'kind'}:
            return 'spec_endorsement_scope_invalid'
        if recomputed_scope is not None and dict(scope) != recomputed_scope:
            return 'spec_endorsement_scope_drift'
    elif scope.get('kind') == 'expectation':
        if set(scope) != {'kind', 'expectation_id'} or machine_case is None:
            return 'spec_endorsement_scope_invalid'
        if dict(scope) != recomputed_scope or recomputed_scope.get('kind') != 'expectation':
            return 'spec_endorsement_expectation_not_unique'
    else:
        return 'spec_endorsement_scope_invalid'
    return ''

def consistency_contract_path(outputs_root: str | Path, autoid: str) -> Path:
    aid = str(autoid or '')
    if _AUTOID_RE.fullmatch(aid) is None:
        raise ConsistencyContractError('consistency contract autoid is invalid')
    return Path(outputs_root) / aid / CONSISTENCY_CONTRACT_SIDECAR_NAME

def write_consistency_contract(outputs_root: str | Path, overlay: Mapping[str, Any]) -> tuple[Path, str]:
    autoid = str(overlay.get('autoid') or '')
    target = consistency_contract_path(outputs_root, autoid)
    payload = canonical_json(dict(overlay), ensure_ascii=False)
    atomic_write_bytes_nofollow(target, payload, error_type=ConsistencyContractError, invalid_message='consistency contract path is invalid', unavailable_message='consistency contract cannot be written safely', create_parents=False, mode=384)
    return (target, sha256_bytes(payload))

def parse_consistency_contract(raw: bytes) -> tuple[dict[str, Any], str]:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= _MAX_BYTES:
        raise ConsistencyContractError('consistency contract exceeds its byte budget')
    validate_json_budget(raw, error_type=ConsistencyContractError, message='consistency contract exceeds its JSON structure budget', max_depth=32, max_tokens=8192)
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ConsistencyContractError('consistency contract is not valid JSON') from exc
    if not isinstance(payload, dict):
        raise ConsistencyContractError('consistency contract must be a JSON object')
    return (payload, sha256_bytes(raw))

def load_consistency_contract_document(path: str | Path) -> tuple[dict[str, Any], str, bytes]:
    raw = read_regular_nofollow(Path(path), error_type=ConsistencyContractError, invalid_message='consistency contract path is invalid', directory_message='consistency contract directory is unavailable', open_message='consistency contract is unavailable', bounds_message='consistency contract exceeds its byte budget', changed_message='consistency contract changed while being read', max_bytes=_MAX_BYTES, min_bytes=1, require_current_uid=True)
    assert isinstance(raw, bytes)
    payload, sha256 = parse_consistency_contract(raw)
    return (payload, sha256, raw)

def load_consistency_contract(path: str | Path) -> tuple[dict[str, Any], str]:
    payload, sha256, _raw = load_consistency_contract_document(path)
    return (payload, sha256)
__all__ = ['CONSISTENCY_CONTRACT_SCHEMA', 'SPEC_ENDORSEMENT_EXPECTATION_BINDING_SCHEMA', 'SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY', 'SPEC_ENDORSEMENT_SCHEMA', 'ConsistencyContractError', 'build_consistency_contract', 'consistency_contract_path', 'consistency_material_receipt_sha256', 'load_consistency_contract', 'load_consistency_contract_document', 'parse_consistency_contract', 'spec_endorsement_expectation_binding_rule', 'validate_consistency_contract', 'write_consistency_contract']
