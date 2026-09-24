# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/criterion_carriers.py（sha256 f9a48aab688e917f）。不在这里手改。
from __future__ import annotations
from cex_core.engine.common.engine_track_schema import accepts_engine_schema, engine_schema_id
from cex_core.engine.case_compiler.provenance_ir import _EXPECT_KINDS
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class Carrier:
    block_kind: str
    operator: str
    lowering_operators: tuple[str, ...]
    implementation_blocks: tuple[str, ...] = ()

@dataclass(frozen=True)
class CriterionCarriers:
    criterion_type: str
    label_zh: str
    carriers: tuple[Carrier, ...]

def _assertion(operator: str) -> Carrier:
    return Carrier('OBSERVE_ASSERT', operator, (operator,))
CRITERION_CARRIERS: tuple[CriterionCarriers, ...] = (CriterionCarriers('reachability', '可达性', (Carrier('OBSERVE_EXIT', '', ('found',)), _assertion('found'), _assertion('abs_found'))), CriterionCarriers('status_value', '状态值', (_assertion('found'), _assertion('abs_found'), _assertion('not_found'), Carrier('OBSERVE_EXIT', '', ('found',)), Carrier('EXPECT_FROM', '', ('found', 'not_found', 'abs_found'), ('CAPTURE',)))), CriterionCarriers('content_match', '内容匹配', (_assertion('found'), _assertion('abs_found'), Carrier('OBSERVE_MEMBER', '', ('found', 'not_found')))), CriterionCarriers('absence', '不存在性', (_assertion('not_found'),)), CriterionCarriers('count', '计数', (_assertion('found_times'),)), CriterionCarriers('distribution', '分布', (Carrier('OBSERVE_DIST', '', ('found',)),)), CriterionCarriers('before_after', '前后对照', (Carrier('CAPTURE_COMPARE', '', ('found', 'not_found'), ('CAPTURE',)),)))
CRITERION_TYPE_ALLOWED_SLOTS: dict[str, frozenset[tuple[str, str]]] = {item.criterion_type: frozenset(((carrier.block_kind, carrier.operator) for carrier in item.carriers)) for item in CRITERION_CARRIERS}

def criterion_type_blueprints() -> list[dict[str, Any]]:
    out = []
    for item in CRITERION_CARRIERS:
        implementations: dict[str, list[str]] = {}
        for carrier in item.carriers:
            for kind in carrier.implementation_blocks:
                implementations.setdefault(kind, []).append(carrier.block_kind)
        out.append({'criterion_type': item.criterion_type, 'label_zh': item.label_zh, 'operators': list(dict.fromkeys((operator for carrier in item.carriers for operator in carrier.lowering_operators))), 'block_kinds': list(dict.fromkeys([carrier.block_kind for carrier in item.carriers] + list(implementations))), 'allowed_slots': [{'block_kind': carrier.block_kind, 'operator': carrier.operator} for carrier in item.carriers], 'implementation_blocks': [{'block_kind': kind, 'role': 'observation_only', 'used_by': users} for kind, users in implementations.items()]})
    return out

def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def carrier_contract_sha256() -> str:
    return _digest(criterion_type_blueprints())

@dataclass(frozen=True)
class RequirementSource:
    kind: str
    ref: str
    raw: bytes
_REQUIREMENT_AUTHORITIES = frozenset(_EXPECT_KINDS)
_SHA256 = re.compile('[0-9a-f]{64}\\Z')
_UNVERIFIED_REASONS = frozenset({'requirements_absent', 'requirement_source_identity_invalid', 'requirement_source_unavailable', 'claim_identity_unavailable', 'claim_identity_invalid', 'requirement_document_invalid', 'requirement_binding_mismatch', 'requirement_coverage_incomplete', 'requirement_content_missing', 'requirement_alternatives_missing'})

def requirement_reference_valid(value: Any) -> bool:
    return bool(isinstance(value, Mapping) and set(value) == {'kind', 'ref', 'sha256'} and isinstance(value.get('kind'), str) and (value['kind'] in _REQUIREMENT_AUTHORITIES) and isinstance(value.get('ref'), str) and value['ref'].strip() and _SHA256.fullmatch(str(value.get('sha256') or '')))

def normalization_identity(claim: Mapping[str, Any]) -> str:
    return _digest({key: claim.get(key) for key in ('expectation_id', 'semantic_key', 'original_claim_sha256', 'status', 'criterion_type', 'rule_id', 'rule_identity', 'catalog_sha256')})

def _unverified(base: Mapping[str, Any], reason: str) -> dict[str, Any]:
    if reason not in _UNVERIFIED_REASONS:
        raise ValueError('unregistered requirement verification reason')
    return {**base, 'status': 'unverified', 'reason': reason, 'obligations': []}

def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate requirement field')
        value[key] = item
    return value

def _source_identity(source: RequirementSource, pointer: str) -> dict[str, str]:
    return {'kind': source.kind, 'ref': source.ref, 'source_sha256': hashlib.sha256(source.raw).hexdigest(), 'pointer': pointer}

def derive_required_carriers(expectation: Mapping[str, Any], normalized_claim: Mapping[str, Any], *, requirement_sources: Mapping[str, RequirementSource] | None=None) -> dict[str, Any]:
    claim = normalized_claim
    base = {'schema': engine_schema_id('required_carriers'), 'expectation_id': str(claim.get('expectation_id') or ''), 'semantic_key': str(claim.get('semantic_key') or ''), 'claim_sha256': str(claim.get('original_claim_sha256') or ''), 'normalization_sha256': normalization_identity(claim), 'check_scope': 'all_obligations_in_explicit_requirement_document'}
    reference = expectation.get('criterion_requirements_ref')
    if not isinstance(reference, Mapping):
        return _unverified(base, 'requirements_absent')
    if not requirement_reference_valid(reference):
        return _unverified(base, 'requirement_source_identity_invalid')
    source = (requirement_sources or {}).get(reference['ref'])
    if not isinstance(source, RequirementSource):
        return _unverified(base, 'requirement_source_unavailable')
    if source.kind != reference['kind'] or source.ref != reference['ref'] or (not isinstance(source.raw, bytes)) or (hashlib.sha256(source.raw).hexdigest() != reference['sha256']):
        return _unverified(base, 'requirement_source_identity_invalid')
    source_claim = expectation.get('author_claim') or expectation.get('defect_spec_claim')
    if not isinstance(source_claim, Mapping):
        return _unverified(base, 'claim_identity_unavailable')
    if not base['expectation_id'] or not base['semantic_key'] or (not _SHA256.fullmatch(base['claim_sha256'])) or (source_claim.get('expectation_id') != base['expectation_id']) or (source_claim.get('semantic_key') != base['semantic_key']) or (source_claim.get('claim_sha256') != base['claim_sha256']) or (claim.get('status') != 'matched') or (not claim.get('criterion_type')) or (not claim.get('rule_id')) or (not isinstance(claim.get('rule_identity'), Mapping)) or (not claim['rule_identity']) or (not _SHA256.fullmatch(str(claim.get('catalog_sha256') or ''))):
        return _unverified(base, 'claim_identity_invalid')
    try:
        document = json.loads(source.raw, object_pairs_hook=_unique_json_object)
    except (ValueError, UnicodeError):
        return _unverified(base, 'requirement_document_invalid')
    expected_fields = {'schema', 'expectation_id', 'semantic_key', 'claim_sha256', 'normalization_sha256', 'coverage', 'obligations'}
    if not isinstance(document, dict) or set(document) != expected_fields:
        return _unverified(base, 'requirement_document_invalid')
    if not accepts_engine_schema(document['schema'], 'criterion_requirements'):
        return _unverified(base, 'requirement_document_invalid')
    if any((document[key] != base[key] for key in ('expectation_id', 'semantic_key', 'claim_sha256', 'normalization_sha256'))):
        return _unverified(base, 'requirement_binding_mismatch')
    obligations = document['obligations']
    coverage = document['coverage']
    if not isinstance(obligations, list) or not obligations or (not isinstance(coverage, dict)) or (set(coverage) != {'scope', 'obligation_ids'}) or (coverage['scope'] != 'complete') or (not isinstance(coverage['obligation_ids'], list)):
        return _unverified(base, 'requirement_coverage_incomplete')
    normalized: list[dict[str, Any]] = []
    obligation_ids: list[str] = []
    for index, obligation in enumerate(obligations):
        if not isinstance(obligation, dict) or set(obligation) != {'obligation_id', 'requirement', 'alternatives'}:
            return _unverified(base, 'requirement_document_invalid')
        identifier = obligation['obligation_id']
        if not isinstance(identifier, str) or not identifier.strip() or identifier in obligation_ids:
            return _unverified(base, 'requirement_coverage_incomplete')
        if not isinstance(obligation['requirement'], str) or not obligation['requirement'].strip():
            return _unverified(base, 'requirement_content_missing')
        alternatives = obligation['alternatives']
        if not isinstance(alternatives, list) or not alternatives:
            return _unverified(base, 'requirement_alternatives_missing')
        choices = []
        choice_ids: set[str] = set()
        for choice_index, choice in enumerate(alternatives):
            if not isinstance(choice, dict) or set(choice) != {'alternative_id', 'carriers'}:
                return _unverified(base, 'requirement_document_invalid')
            choice_id = choice['alternative_id']
            if not isinstance(choice_id, str) or not choice_id.strip() or choice_id in choice_ids:
                return _unverified(base, 'requirement_document_invalid')
            carrier_rows = choice['carriers']
            if not isinstance(carrier_rows, list) or not carrier_rows:
                return _unverified(base, 'requirement_alternatives_missing')
            pairs = []
            for row in carrier_rows:
                if not isinstance(row, dict) or set(row) != {'block_kind', 'operator'} or (not isinstance(row['block_kind'], str)) or (not row['block_kind'].strip()) or (not isinstance(row['operator'], str)):
                    return _unverified(base, 'requirement_document_invalid')
                pair = (row['block_kind'], row['operator'])
                if pair in pairs:
                    return _unverified(base, 'requirement_document_invalid')
                pairs.append(pair)
            choice_ids.add(choice_id)
            choices.append({'alternative_id': choice_id, 'carriers': [dict(row) for row in carrier_rows], 'identity': _source_identity(source, f'/obligations/{index}/alternatives/{choice_index}')})
        obligation_ids.append(identifier)
        normalized.append({'obligation_id': identifier, 'requirement': obligation['requirement'], 'alternatives': choices, 'identity': _source_identity(source, f'/obligations/{index}')})
    if coverage['obligation_ids'] != obligation_ids:
        return _unverified(base, 'requirement_coverage_incomplete')
    result = {**base, 'status': 'verified', 'reason': '', 'source_identity': _source_identity(source, ''), 'coverage': {'scope': 'complete', 'obligation_ids': list(obligation_ids)}, 'obligations': normalized}
    result['requirements_sha256'] = _digest(result)
    return result

def bind_requirement_source(expectation: Mapping[str, Any], source: RequirementSource) -> dict[str, Any]:
    result = copy.deepcopy(dict(expectation))
    result['criterion_requirements_ref'] = {'kind': source.kind, 'ref': source.ref, 'sha256': hashlib.sha256(source.raw).hexdigest()}
    claim = result.get('normalized_claim')
    if not isinstance(claim, dict):
        raise ValueError('normalized claim is required before binding requirement evidence')
    required = derive_required_carriers(result, claim, requirement_sources={source.ref: source})
    if required['status'] != 'verified':
        raise ValueError(str(required['reason']))
    claim['required_carriers'] = required
    return result

def required_carriers_record_error(value: Any, claim: Mapping[str, Any]) -> str:
    base = derive_required_carriers({}, claim)
    base_fields = set(base) - {'status', 'reason', 'obligations'}
    if not isinstance(value, dict) or any((value.get(key) != base[key] for key in base_fields)):
        return 'required carrier record identity is invalid'
    if value.get('status') == 'unverified':
        if set(value) != set(base) or not isinstance(value.get('reason'), str) or value['reason'] not in _UNVERIFIED_REASONS or (value.get('obligations') != []):
            return 'unverified required carrier record is invalid'
        return ''
    if set(value) != set(base) | {'source_identity', 'coverage', 'requirements_sha256'}:
        return 'required carrier record fields are not closed'
    if value.get('status') != 'verified' or value.get('reason') != '':
        return 'required carrier record status is invalid'
    body = {key: item for key, item in value.items() if key != 'requirements_sha256'}
    if _digest(body) != value.get('requirements_sha256'):
        return 'required carrier record digest is invalid'
    identity = value['source_identity']
    if not isinstance(identity, dict) or set(identity) != {'kind', 'ref', 'source_sha256', 'pointer'} or identity['pointer'] != '' or (not requirement_reference_valid({'kind': identity['kind'], 'ref': identity['ref'], 'sha256': identity['source_sha256']})):
        return 'required carrier source identity is invalid'
    obligations = value['obligations']
    if not isinstance(obligations, list) or not obligations:
        return 'required carrier obligations are empty'
    ids = []
    for index, obligation in enumerate(obligations):
        if not isinstance(obligation, dict) or set(obligation) != {'obligation_id', 'requirement', 'alternatives', 'identity'}:
            return 'required carrier obligation fields are not closed'
        identifier = obligation['obligation_id']
        if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
            return 'required carrier obligation identity is invalid'
        if not isinstance(obligation['requirement'], str) or not obligation['requirement'].strip():
            return 'required carrier obligation content is empty'
        if obligation['identity'] != {**identity, 'pointer': f'/obligations/{index}'}:
            return 'required carrier obligation source is invalid'
        alternatives = obligation['alternatives']
        if not isinstance(alternatives, list) or not alternatives:
            return 'required carrier alternatives are empty'
        choice_ids = set()
        for choice_index, choice in enumerate(alternatives):
            if not isinstance(choice, dict) or set(choice) != {'alternative_id', 'carriers', 'identity'}:
                return 'required carrier alternative fields are not closed'
            choice_id = choice['alternative_id']
            if not isinstance(choice_id, str) or not choice_id.strip() or choice_id in choice_ids:
                return 'required carrier alternative identity is invalid'
            if choice['identity'] != {**identity, 'pointer': f'/obligations/{index}/alternatives/{choice_index}'}:
                return 'required carrier alternative source is invalid'
            rows = choice['carriers']
            if not isinstance(rows, list) or not rows:
                return 'required carrier alternative slots are empty'
            pairs = set()
            for row in rows:
                if not isinstance(row, dict) or set(row) != {'block_kind', 'operator'} or (not isinstance(row['block_kind'], str)) or (not row['block_kind'].strip()) or (not isinstance(row['operator'], str)) or ((row['block_kind'], row['operator']) in pairs):
                    return 'required carrier slot shape is invalid'
                pairs.add((row['block_kind'], row['operator']))
            choice_ids.add(choice_id)
        ids.append(identifier)
    if value['coverage'] != {'scope': 'complete', 'obligation_ids': ids}:
        return 'required carrier obligation coverage is incomplete'
    return ''

def check_required_carriers(expectation: Mapping[str, Any], *, requirement_sources: Mapping[str, RequirementSource] | None=None, allowed_slots: Mapping[str, frozenset[tuple[str, str]]] | None=None) -> dict[str, Any]:
    claim = expectation.get('normalized_claim')
    if not isinstance(claim, Mapping):
        claim = {}
    required = derive_required_carriers(expectation, claim, requirement_sources=requirement_sources)
    result = {**required, 'check_scope': 'registered_slots_for_all_explicit_obligations', 'carrier_contract_sha256': carrier_contract_sha256(), 'supported_alternatives': {}, 'uncovered_obligations': []}
    if required['status'] != 'verified':
        return result
    stored = claim.get('required_carriers')
    if stored is not None and stored != required:
        return {**result, 'status': 'unverified', 'reason': 'required_carriers_receipt_mismatch'}
    slots = (CRITERION_TYPE_ALLOWED_SLOTS if allowed_slots is None else allowed_slots).get(str(claim.get('criterion_type') or ''), frozenset())
    for obligation in required['obligations']:
        identifier = obligation['obligation_id']
        supported = [alternative['alternative_id'] for alternative in obligation['alternatives'] if all(((row['block_kind'], row['operator']) in slots for row in alternative['carriers']))]
        result['supported_alternatives'][identifier] = supported
        if not supported:
            result['uncovered_obligations'].append(identifier)
    result['status'] = 'gap' if result['uncovered_obligations'] else 'supported'
    result['reason'] = 'required_carrier_unavailable' if result['uncovered_obligations'] else ''
    return result
