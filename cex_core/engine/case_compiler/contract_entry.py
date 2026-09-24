# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/contract_entry.py（sha256 7f79aa50c9f1a0c7）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from cex_core.engine.common.schema_identity import accepts_schema as _accepts_schema
from cex_core.engine.case_compiler.provenance_ir import ORDERING_EXEMPT_REASON, validate_expected_with_source
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, open_directory_nofollow, read_regular_at_nofollow, read_regular_nofollow, sha256_bytes, validate_json_budget
SCHEMA_VERSION = 4
CONTRACT_CLASSES = frozenset({'pattern', 'mindmap_verbatim'})
_MINDMAP_BUCKET_ZH = {'exp_recipe': '判据在期望槽', 'step_recipe': '判据来自步骤'}
WARNING_PANEL_SCHEMA = 'ist.ide.warning-panel'
CONFIRM_LABEL = '确认签约'
REJECT_LABEL = '退回修改'
INTENT_JSON_MAX_BYTES = 4 * 1024 * 1024
_WARNING_LABELS = {'vacuous_found_in_clean': '干净态已经满足正向断言，判别力灰显', 'config_echo': '当前证据只覆盖配置回显，未直接覆盖运行时行为', 'config_existence_only': '当前断言只证明配置存在，未直接覆盖运行时行为', 'direction_review': '断言方向仍待作者确认', 'poison_confirmed': '引用资产已被机械拒引规则隔离', 'retro_grade_b': '引用资产的回溯认证证据不完整', 'retro_grade_c': '引用资产的回溯认证发现明确风险', 'scope_adaptation': '本行为模式包含范围适配', 'command_not_in_vendor_tree': '脑图中的命令在设备命令树中查无此头', 'command_manual_only': '脑图中的命令仅见于手册声明，命令树未收录', 'command_arg_count_mismatch': '脑图中的命令参数个数与命令树签名不符', 'mindmap_proposal_disclosure': '重组阶段 proposal 提醒（用户面消费）', 'rebind_license_mapping': '经披露许可的重绑映射（原文保留）', 'process_value_concretization': '过程值具体化映射（预期文本未改）', 'rebind_license_unbound': '许可未能于当前床兑现'}
_COMMAND_FINDING_CODES = frozenset({'command_not_in_vendor_tree', 'command_manual_only', 'command_arg_count_mismatch'})
_EXPECTATION_COVERED_BY = frozenset({'set-ratio'})
_EXPECTATION_EXEMPTED_PARTS = frozenset({'ordering'})
_EXPECTATION_EXEMPT_REASONS = frozenset({ORDERING_EXEMPT_REASON})

class ContractError(ValueError):
    pass

def _nonempty(value: Any, field: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ContractError(f'{field} is required')
    return text

def _public_text(value: Any, field: str) -> str:
    from cex_core.engine.ist_core.security_scrub import scrub_text
    return _nonempty(scrub_text(value, scrub_paths=True), field)

def _normalized_claim(value: Any, *, item_text: str, source_claim: dict[str, Any], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f'{field} must be an object')
    required = {'schema', 'expectation_id', 'semantic_key', 'original_text', 'original_claim_sha256', 'source_span', 'shape_key', 'version_family', 'status', 'criterion_type', 'criterion_label_zh', 'rule_id', 'rule_identity', 'evidence_chain', 'author_veto', 'mode', 'disclosure', 'catalog_sha256'}
    optional = {'min_requests', 'min_requests_formula', 'triage', 'triage_details', 'fixture_authority', 'fixture_policy', 'algorithm_classes', 'anchor_citation_corrected', 'supersede_cause', 'required_carriers', 'authored_step', 'authored_step_cause'}
    if not required <= set(value) or set(value) - required - optional:
        raise ContractError(f'{field} fields are not closed')
    from cex_core.engine.case_compiler.criterion_normalization import NORMALIZED_CLAIM_SCHEMA, load_projection
    projection = load_projection()
    type_rows = {str(row.get('criterion_type') or ''): str(row.get('label_zh') or '') for row in projection.get('criterion_types') or [] if isinstance(row, dict)}
    rule_ids = {str(row.get('rule_id') or '') for row in projection.get('rules') or [] if isinstance(row, dict)}
    static_rules = {str(row.get('rule_id') or ''): row for row in projection.get('rules') or [] if isinstance(row, dict)}
    status = str(value.get('status') or '')
    criterion_type = value.get('criterion_type')
    criterion_type = str(criterion_type) if criterion_type is not None else None
    rule_id = value.get('rule_id')
    rule_id = str(rule_id) if rule_id is not None else None
    source_span = value.get('source_span')
    algorithm_classes = value.get('algorithm_classes')
    from cex_core.engine.case_compiler.domain_grammar import load_grammar
    known_algorithm_classes = set((str(key) for key in load_grammar().get('algorithm_classes') or {}))
    if not isinstance(algorithm_classes, list) or len(algorithm_classes) != len(set(algorithm_classes)) or any((not isinstance(item, str) or item not in known_algorithm_classes for item in algorithm_classes)):
        raise ContractError(f'{field}.algorithm_classes is invalid')
    if source_span is not None and (not isinstance(source_span, dict) or not isinstance(source_span.get('start'), int) or (not isinstance(source_span.get('end'), int)) or (int(source_span['start']) < 0) or (int(source_span['end']) <= int(source_span['start']))):
        raise ContractError(f'{field}.source_span is invalid')
    if 'authored_step' in value or 'authored_step_cause' in value:
        from cex_core.engine.case_compiler.mindmap_contract_projector import AUTHORED_STEP_UNKNOWN_CAUSES
        authored_step = value.get('authored_step')
        cause = value.get('authored_step_cause')
        if authored_step is not None and (isinstance(authored_step, bool) or not isinstance(authored_step, int) or authored_step < 1):
            raise ContractError(f'{field}.authored_step is invalid')
        if (cause is None) != (authored_step is not None):
            raise ContractError(f'{field}.authored_step_cause is not paired')
        if cause is not None and cause not in AUTHORED_STEP_UNKNOWN_CAUSES:
            raise ContractError(f'{field}.authored_step_cause is outside closed set')
    if value.get('schema') != NORMALIZED_CLAIM_SCHEMA or str(value.get('original_text') or '') != item_text or str(value.get('expectation_id') or '') != str(source_claim.get('expectation_id') or '') or (str(value.get('semantic_key') or '') != str(source_claim.get('semantic_key') or '')) or (str(value.get('original_claim_sha256') or '') != str(source_claim.get('claim_sha256') or '')) or (re.fullmatch('[0-9a-f]{64}', str(value.get('shape_key') or '')) is None) or (str(value.get('catalog_sha256') or '') != str(projection.get('projection_sha256') or '')) or (status not in {'matched', 'unmatched', 'manual_recommended', 'numeric_tolerance_out_of_range'}) or (not str(value.get('disclosure') or '').strip()):
        raise ContractError(f'{field} identity is invalid')
    if criterion_type is not None and (criterion_type not in type_rows or str(value.get('criterion_label_zh') or '') != type_rows[criterion_type]):
        raise ContractError(f'{field}.criterion_type is invalid')
    if criterion_type is None and value.get('criterion_label_zh') is not None:
        raise ContractError(f'{field}.criterion_label_zh must be null')
    if rule_id is not None:
        rule_identity = value.get('rule_identity')
        if not isinstance(rule_identity, dict):
            raise ContractError(f'{field}.rule identity is invalid')
        if rule_id not in rule_ids:
            from cex_core.engine.case_compiler.criterion_author_rules import load_author_rules, resolve_compile_manual_version
            resolved_manual_version = resolve_compile_manual_version()
            author_rule = load_author_rules(manual_version=resolved_manual_version or None).get((str(value.get('shape_key') or ''), resolved_manual_version))
            if not isinstance(author_rule, dict) or str(author_rule.get('rule_id') or '') != rule_id or author_rule.get('identity') != rule_identity:
                raise ContractError(f'{field}.rule identity is invalid')
        if rule_identity.get('kind') == 'engine_adjudication':
            evidence_chain = value.get('evidence_chain')
            author_veto = value.get('author_veto')
            if not isinstance(evidence_chain, dict) or evidence_chain != rule_identity.get('evidence_chain') or (not isinstance(author_veto, dict)) or (set(author_veto) != {'answer_key', 'answer', 'rule_sha256'}) or (re.fullmatch('[0-9a-f]{64}', str(author_veto.get('answer_key') or '')) is None) or (author_veto.get('answer') != '否决并重裁') or (not re.fullmatch('[0-9a-f]{64}', str(author_veto.get('rule_sha256') or ''))):
                raise ContractError(f'{field}.engine adjudication evidence is invalid')
        elif value.get('evidence_chain') is not None or value.get('author_veto') is not None:
            raise ContractError(f'{field}.static rule may not carry engine adjudication fields')
        static_rule = static_rules.get(rule_id)
        if isinstance(static_rule, dict):
            output = static_rule.get('output') or {}
            for extra in ('fixture_authority', 'fixture_policy'):
                if value.get(extra) != output.get(extra):
                    if extra in value or extra in output:
                        raise ContractError(f'{field}.{extra} differs from the generated rule')
    if rule_id is None and value.get('rule_identity') is not None:
        raise ContractError(f'{field}.rule_identity must be null')
    if status == 'matched' and (criterion_type is None or rule_id is None):
        raise ContractError(f'{field} matched state has no rule/type')
    if 'required_carriers' in value:
        from cex_core.engine.case_compiler.criterion_carriers import required_carriers_record_error
        carrier_error = required_carriers_record_error(value['required_carriers'], value)
        if carrier_error:
            raise ContractError(f'{field}.required_carriers: {carrier_error}')
    return dict(value)

def normalize_contract(raw: dict[str, Any], source: str='') -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ContractError('contract must be an object')
    contract_class = str(raw.get('contract_class') or 'pattern').strip()
    if contract_class not in CONTRACT_CLASSES:
        raise ContractError(f'contract_class must be one of {sorted(CONTRACT_CLASSES)}')
    is_mindmap = contract_class == 'mindmap_verbatim'
    autoid = _nonempty(raw.get('autoid') or raw.get('pilot_autoid'), 'autoid')
    title = _public_text(raw.get('intent_verbatim') or raw.get('title'), 'intent_verbatim')
    method = raw.get('verification_method')
    if not isinstance(method, dict):
        raise ContractError('verification_method must be an object')
    selected_rule = _public_text(method.get('selected_rule') or method.get('proposal'), 'verification_method.selected_rule')
    authority = _public_text(method.get('authority'), 'verification_method.authority')
    alternatives = method.get('alternatives')
    if not isinstance(alternatives, list) or not alternatives:
        if is_mindmap:
            alternatives = []
        else:
            raise ContractError('verification_method.alternatives must be a non-empty array')
    normalized_alternatives: list[dict[str, str]] = []
    for index, alternative in enumerate(alternatives):
        if not isinstance(alternative, dict):
            raise ContractError(f'verification_method.alternatives[{index}] must be an object')
        rule = _public_text(alternative.get('rule'), f'verification_method.alternatives[{index}].rule')
        if rule == selected_rule:
            raise ContractError(f'verification_method.alternatives[{index}].rule duplicates selected_rule')
        normalized_alternatives.append({'rule': rule, 'authority': _public_text(alternative.get('authority'), f'verification_method.alternatives[{index}].authority'), 'rejection_reason': _public_text(alternative.get('rejection_reason'), f'verification_method.alternatives[{index}].rejection_reason')})
    pattern = raw.get('behavior_pattern')
    mindmap_group: dict[str, Any] = {}
    bucket = ''
    source_status = ''
    typed_assertion_status = ''
    if is_mindmap:
        if pattern is not None and (not isinstance(pattern, dict)):
            raise ContractError('behavior_pattern must be an object when given')
        group = raw.get('mindmap_group')
        if not isinstance(group, dict):
            raise ContractError('mindmap_group must be an object')
        group_path = group.get('group_path')
        if not isinstance(group_path, list) or not group_path or (not all((str(x).strip() for x in group_path))):
            raise ContractError('mindmap_group.group_path must be a non-empty string array')
        mindmap_group = {'group_path': [_public_text(x, 'mindmap_group.group_path[]') for x in group_path]}
        bucket = _nonempty(raw.get('bucket'), 'bucket')
        if bucket not in _MINDMAP_BUCKET_ZH:
            raise ContractError(f'bucket must be one of {sorted(_MINDMAP_BUCKET_ZH)}')
        source_status = str(raw.get('source_status') or 'complete').strip()
        if source_status != 'complete':
            raise ContractError('mindmap contract source_status must be complete before signing')
        typed_assertion_status = str(raw.get('typed_assertion_status') or ('pending' if any((isinstance(item, dict) and (item.get('author_claim') is not None or item.get('defect_spec_claim') is not None) for item in raw.get('expectations') or [])) else 'ready')).strip()
        if typed_assertion_status not in {'ready', 'pending'}:
            raise ContractError('typed_assertion_status must be ready or pending')
        author_steps_present = 'author_steps' in raw
        raw_author_steps = raw.get('author_steps')
        if raw_author_steps is None:
            raw_author_steps = []
        if not isinstance(raw_author_steps, list):
            raise ContractError('author_steps must be an array')
        author_steps: list[dict[str, str]] = []
        for index, item in enumerate(raw_author_steps):
            if not isinstance(item, dict) or set(item) != {'n', 'text', 'origin'}:
                raise ContractError(f'author_steps[{index}] fields must be exactly n/text/origin')
            author_steps.append({'n': _nonempty(item.get('n'), f'author_steps[{index}].n'), 'text': _public_text(item.get('text'), f'author_steps[{index}].text'), 'origin': _nonempty(item.get('origin'), f'author_steps[{index}].origin')})
        capability = str((pattern or {}).get('capability_family') or '').strip()
        shape = str((pattern or {}).get('verification_shape') or '').strip()
    else:
        author_steps_present = False
        author_steps = []
        if not isinstance(pattern, dict):
            raise ContractError('behavior_pattern must be an object')
        capability = _nonempty(pattern.get('capability_family'), 'behavior_pattern.capability_family')
        shape = _nonempty(pattern.get('verification_shape'), 'behavior_pattern.verification_shape')
    command_findings: list[dict[str, str]] = []
    for i, cf in enumerate(raw.get('command_findings') or []):
        if not isinstance(cf, dict):
            raise ContractError(f'command_findings[{i}] must be an object')
        code = str(cf.get('code') or '').strip()
        if code not in _COMMAND_FINDING_CODES:
            raise ContractError(f'command_findings[{i}].code must be one of {sorted(_COMMAND_FINDING_CODES)}')
        command_findings.append({'command': _public_text(cf.get('command'), f'command_findings[{i}].command'), 'code': code, 'note': _public_text(cf.get('note'), f'command_findings[{i}].note')})
    selected_rule_id = str(method.get('selected_rule_id') or '').strip()
    rule_snapshot_fields: dict[str, str] = {}
    if selected_rule_id and is_mindmap:
        raise ContractError("mindmap_verbatim contracts carry the author's verbatim method; selected_rule_id (rule selection) does not apply")
    if selected_rule_id:
        from cex_core.engine.case_compiler.rule_registry import RuleRegistryUnavailable, applicability_error, rule_snapshot
        try:
            registry_error = applicability_error(selected_rule_id, capability, shape)
            if not registry_error:
                rule_snapshot_fields = rule_snapshot(selected_rule_id, capability)
        except RuleRegistryUnavailable as exc:
            raise ContractError(str(exc)) from exc
        if registry_error:
            raise ContractError(registry_error)
    expectations = raw.get('expectations')
    if not isinstance(expectations, list) or not expectations:
        raise ContractError('expectations must be a non-empty array')
    normalized_expectations: list[dict[str, Any]] = []
    pending_claims = 0
    for i, item in enumerate(expectations):
        if not isinstance(item, dict):
            raise ContractError(f'expectations[{i}] must be an object')
        normalized = {'text': _public_text(item.get('text'), f'expectations[{i}].text'), 'text_anchor': _public_text(item.get('text_anchor'), f'expectations[{i}].text_anchor'), 'value_grounding': _public_text(item.get('value_grounding'), f'expectations[{i}].value_grounding')}
        if is_mindmap:
            assertion = item.get('assertion')
            author_claim = item.get('author_claim')
            defect_spec_claim = item.get('defect_spec_claim')
            alternatives_count = sum((isinstance(candidate, dict) for candidate in (assertion, author_claim, defect_spec_claim)))
            if alternatives_count != 1:
                raise ContractError(f'expectations[{i}] requires exactly one assertion, author_claim, or defect_spec_claim')
            if isinstance(assertion, dict):
                source_binding = assertion.get('source')
                if not isinstance(source_binding, dict):
                    raise ContractError(f'expectations[{i}].assertion.source must be an object')
                source_kind = _nonempty(source_binding.get('kind'), f'expectations[{i}].assertion.source.kind')
                if source_kind not in {'intent', 'spec', 'defect_spec', 'manual'}:
                    raise ContractError(f'expectations[{i}].assertion.source.kind is not authoritative')
                source_locator = _nonempty(source_binding.get('locator'), f'expectations[{i}].assertion.source.locator')
                normalized_source: dict[str, Any] = {'kind': source_kind, 'locator': source_locator}
                if source_kind == 'defect_spec':
                    if set(source_binding) != {'kind', 'locator', 'receipt'}:
                        raise ContractError(f'expectations[{i}].assertion.source DefectSpec fields are not closed')
                    resolver_receipt = source_binding.get('receipt')
                    resolved, receipt_error = validate_expected_with_source({'expected': str(assertion.get('value') or ''), 'source': {'kind': 'defect_spec', 'ref': source_locator, 'receipt': resolver_receipt}})
                    if resolved is None:
                        raise ContractError(f'expectations[{i}].assertion.source DefectSpec receipt is invalid: {receipt_error}')
                    normalized_source['receipt'] = dict(resolver_receipt)
                normalized['assertion'] = {'expectation_id': _nonempty(assertion.get('expectation_id'), f'expectations[{i}].assertion.expectation_id'), 'semantic_key': _nonempty(assertion.get('semantic_key') or f'{autoid}:step:{i + 1}', f'expectations[{i}].assertion.semantic_key'), 'operator': _nonempty(assertion.get('operator'), f'expectations[{i}].assertion.operator'), 'value': str(assertion.get('value') or ''), 'origin': str(assertion.get('origin') or ''), 'source': normalized_source}
                if not normalized['assertion']['value']:
                    raise ContractError(f'expectations[{i}].assertion.value is required')
            elif isinstance(author_claim, dict):
                assert isinstance(author_claim, dict)
                claim_hash = str(author_claim.get('claim_sha256') or '')
                body = {key: value for key, value in author_claim.items() if key != 'claim_sha256'}
                required = {'schema', 'kind', 'autoid', 'expectation_id', 'semantic_key', 'origin', 'source_text', 'source_sha256'}
                if set(body) != required or set(author_claim) != required | {'claim_sha256'}:
                    raise ContractError(f'expectations[{i}].author_claim fields are not closed')
                if not _accepts_schema(body['schema'], 'ist.author-claim') or body['kind'] != 'Author' or body['autoid'] != autoid or (body['source_text'] != item.get('text')) or (not str(body['origin'] or '').strip()) or (not re.fullmatch('[0-9a-f]{64}', str(body['source_sha256'] or ''))) or (not re.fullmatch('[0-9a-f]{64}', claim_hash)) or (_canonical_hash(body) != claim_hash):
                    raise ContractError(f'expectations[{i}].author_claim identity is invalid')
                normalized['author_claim'] = dict(author_claim)
                pending_claims += 1
            else:
                assert isinstance(defect_spec_claim, dict)
                claim_hash = str(defect_spec_claim.get('claim_sha256') or '')
                body = {key: value for key, value in defect_spec_claim.items() if key != 'claim_sha256'}
                required = {'schema', 'kind', 'autoid', 'expectation_id', 'semantic_key', 'origin', 'source_text', 'locator', 'resolver_receipt', 'resolver_receipt_sha256'}
                resolver_receipt = body.get('resolver_receipt')
                resolver_sha = str(body.get('resolver_receipt_sha256') or '')
                if set(body) != required or set(defect_spec_claim) != required | {'claim_sha256'}:
                    raise ContractError(f'expectations[{i}].defect_spec_claim fields are not closed')
                resolved, receipt_error = validate_expected_with_source({'expected': str(body.get('source_text') or ''), 'source': {'kind': 'defect_spec', 'ref': str(body.get('locator') or ''), 'receipt': resolver_receipt}})
                if not _accepts_schema(body['schema'], 'ist.defect-spec-claim') or body['kind'] != 'DefectSpec' or body['autoid'] != autoid or (body['source_text'] != item.get('text')) or (not str(body['origin'] or '').strip()) or (not str(body['expectation_id'] or '').strip()) or (not str(body['semantic_key'] or '').strip()) or (not re.fullmatch('[0-9a-f]{64}', resolver_sha)) or (not isinstance(resolver_receipt, dict)) or (_canonical_hash(resolver_receipt) != resolver_sha) or (not re.fullmatch('[0-9a-f]{64}', claim_hash)) or (_canonical_hash(body) != claim_hash) or (resolved is None):
                    raise ContractError(f'expectations[{i}].defect_spec_claim identity is invalid' + (f': {receipt_error}' if receipt_error else ''))
                normalized['defect_spec_claim'] = dict(defect_spec_claim)
                pending_claims += 1
            if 'normalized_claim' in item:
                source_claim = normalized.get('assertion') or normalized.get('author_claim') or normalized.get('defect_spec_claim') or {}
                normalized['normalized_claim'] = _normalized_claim(item.get('normalized_claim'), item_text=str(item.get('text') or ''), source_claim=source_claim, field=f'expectations[{i}].normalized_claim')
                if 'authored_step' in normalized['normalized_claim']:
                    from cex_core.engine.case_compiler.mindmap_contract_projector import with_authored_step_anchor
                    if with_authored_step_anchor(normalized['text_anchor'], normalized['normalized_claim']['authored_step']) != normalized['text_anchor']:
                        raise ContractError(f'expectations[{i}].text_anchor author step disagrees with normalized_claim.authored_step')
            if 'criterion_requirements_ref' in item:
                from cex_core.engine.case_compiler.criterion_carriers import requirement_reference_valid
                reference = item['criterion_requirements_ref']
                if not requirement_reference_valid(reference):
                    raise ContractError(f'expectations[{i}].criterion_requirements_ref is invalid')
                normalized['criterion_requirements_ref'] = dict(reference)
            required = (normalized.get('normalized_claim') or {}).get('required_carriers')
            if isinstance(required, dict) and required.get('status') == 'verified':
                identity = required['source_identity']
                expected_reference = {'kind': identity['kind'], 'ref': identity['ref'], 'sha256': identity['source_sha256']}
                if normalized.get('criterion_requirements_ref') != expected_reference:
                    raise ContractError(f'expectations[{i}].required_carriers source reference is missing or mismatched')
        state_fields = ('covered_by', 'exempted_part', 'reason')
        present = [field for field in state_fields if item.get(field) is not None]
        if present and len(present) != len(state_fields):
            raise ContractError(f'expectations[{i}] coverage state requires exactly covered_by/exempted_part/reason')
        if present:
            covered_by = _nonempty(item.get('covered_by'), f'expectations[{i}].covered_by')
            exempted_part = _nonempty(item.get('exempted_part'), f'expectations[{i}].exempted_part')
            reason = _nonempty(item.get('reason'), f'expectations[{i}].reason')
            if covered_by not in _EXPECTATION_COVERED_BY:
                raise ContractError(f'expectations[{i}].covered_by must be one of {sorted(_EXPECTATION_COVERED_BY)}')
            if exempted_part not in _EXPECTATION_EXEMPTED_PARTS:
                raise ContractError(f'expectations[{i}].exempted_part must be one of {sorted(_EXPECTATION_EXEMPTED_PARTS)}')
            if reason not in _EXPECTATION_EXEMPT_REASONS:
                raise ContractError(f'expectations[{i}].reason must be one of {sorted(_EXPECTATION_EXEMPT_REASONS)}')
            normalized.update({'covered_by': covered_by, 'exempted_part': exempted_part, 'reason': reason})
        normalized_expectations.append(normalized)
    if is_mindmap:
        expectation_ids = [str((item.get('assertion') or item.get('author_claim') or item.get('defect_spec_claim') or {}).get('expectation_id') or '') for item in normalized_expectations]
        if len(set(expectation_ids)) != len(expectation_ids):
            raise ContractError('expectation assertion IDs must be unique')
        if typed_assertion_status == 'ready' and pending_claims:
            raise ContractError('ready contract cannot contain pending source claims')
        if typed_assertion_status == 'pending' and (not pending_claims):
            raise ContractError('pending contract must contain a source claim')
    return {'schema_version': SCHEMA_VERSION, 'contract_class': contract_class, 'autoid': autoid, 'source_autoid': str(raw.get('src_autoid') or '').strip(), 'source': source, 'intent_verbatim': title, 'intent_anchor': _public_text(raw.get('intent_anchor'), 'intent_anchor'), **({'behavior_pattern': {'capability_family': capability, 'verification_shape': shape}} if not is_mindmap or (capability and shape) else {}), **({'mindmap_group': mindmap_group, 'bucket': bucket, 'source_status': source_status, 'typed_assertion_status': typed_assertion_status, **({'author_steps': author_steps} if author_steps_present else {})} if is_mindmap else {}), **({'command_findings': command_findings} if command_findings else {}), 'verification_method': {'selected_rule': selected_rule, 'selected_rule_id': selected_rule_id, **({'selected_rule_snapshot': rule_snapshot_fields} if rule_snapshot_fields else {}), 'authority': authority, 'alternatives': normalized_alternatives}, 'expectations': normalized_expectations, 'scope_adaptations': [_public_text(x, 'scope_adaptations[]') for x in raw.get('scope_adaptations') or [] if str(x).strip()]}

def cluster_key(contract: dict[str, Any]) -> str:
    if contract.get('contract_class') == 'mindmap_verbatim':
        group = contract.get('mindmap_group') or {}
        return 'mm::' + '/'.join(group.get('group_path') or [])
    pattern = contract['behavior_pattern']
    return f"{pattern['capability_family']}::{pattern['verification_shape']}"

def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

def _signed_card_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {key: card[key] for key in ('schema_version', 'cluster_key', 'contract_class', 'mindmap_group', 'behavior_pattern', 'cases', 'warnings') if key in card}

def _author_card_text(value: Any, masked: bool) -> str:
    text = str(value)
    return '〇' * len(text) if masked else text

def _author_card_anchor(value: Any, authored_text: str, masked: bool) -> str:
    text = str(value)
    if not masked or len(text) > 65536:
        return text
    import ast
    try:
        from cex_core.engine.case_compiler._sealed_io import validate_json_budget
        validate_json_budget(text, error_type=ValueError, message='anchor exceeds JSON budget')
        try:
            anchor = json.loads(text, object_pairs_hook=_unique_anchor_keys)
        except json.JSONDecodeError:
            expression = ast.parse(text, mode='eval')
            for node in ast.walk(expression):
                if isinstance(node, ast.Dict):
                    keys = [ast.literal_eval(key) for key in node.keys]
                    if len(keys) != len(set(keys)):
                        return text
            anchor = ast.literal_eval(expression)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return text
    if isinstance(anchor, dict) and anchor.get('quote') == authored_text:
        return str({**anchor, 'quote': _author_card_text(authored_text, True)})
    return text

def _unique_anchor_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate anchor key')
        result[key] = value
    return result

def _render_card(payload: dict[str, Any], digest: str, *, mask_author_text: bool=False) -> str:
    if payload.get('contract_class') == 'mindmap_verbatim':
        return _render_card_v4_mindmap(payload, digest, mask_author_text=mask_author_text)
    if int(payload.get('schema_version') or 0) <= 2:
        return _render_card_v2(payload, digest)
    return _render_card_v3(payload, digest, mask_author_text=mask_author_text)

def _render_card_v4_mindmap(payload: dict[str, Any], digest: str, *, mask_author_text: bool=False) -> str:
    group = payload.get('mindmap_group') or {}
    group_path = [str(x) for x in group.get('group_path') or []]
    cases = payload['cases']
    warnings = payload['warnings']
    lines = [f"用例组：{(_author_card_text(group_path[-1], mask_author_text) if group_path else '（未分组）')}\u3000\u3000适用 {len(cases)} 条", '', f'引擎把这 {len(cases)} 条归成同一个行为模式，按同一套契约处理：']
    rewritten: list[str] = []
    chosen: list[str] = []
    for case in cases:
        method = case['verification_method']
        tail = case['autoid'][-6:]
        lines.append(f"  {tail}  {_author_card_text(case['intent_verbatim'], mask_author_text)}")
        if method.get('alternatives'):
            chosen.append(f"  {tail}  选了「{method['selected_rule']}」" + '，未选：' + '、'.join((f"「{alt['rule']}」（{alt['rejection_reason']}）" for alt in method['alternatives'])))
        if str(method.get('selected_rule') or '') not in str(case.get('intent_verbatim') or '') and method.get('machine_rewritten'):
            rewritten.append(f"  {tail}  {method['selected_rule']}")
    if chosen:
        lines += ['', '引擎在多个验证方法里做了选择：'] + chosen
    if rewritten:
        lines += ['', '注意：引擎改写了你的原文：'] + rewritten
    if not chosen and (not rewritten):
        lines += ['', '你的原文一个字没改，引擎也没有替你做任何选择。']
    criterion_lines: list[str] = []
    from cex_core.engine.case_compiler.mindmap_contract_projector import criterion_verbal_zh
    for case in cases:
        tail = str(case.get('autoid') or '')[-6:]
        for expectation in case.get('expectations') or []:
            if not isinstance(expectation, dict):
                continue
            normalized_claim = expectation.get('normalized_claim')
            if not isinstance(normalized_claim, dict):
                continue
            label = criterion_verbal_zh(str(normalized_claim.get('criterion_label_zh') or normalized_claim.get('criterion_type') or '')) or '还没定'
            suffix = '' if normalized_claim.get('status') == 'matched' else '（类型还没定下来）'
            criterion_lines.append(f"  {tail}  原文「{_author_card_text(expectation.get('text'), mask_author_text)}」；归类为「{label}」{suffix}")
    if criterion_lines:
        lines += ['', '归类预期（人工脑图预期原文不动）：'] + criterion_lines
    scope_total = sum((len(c['scope_adaptations']) for c in cases))
    if scope_total:
        lines.append(f'配置组合共 {scope_total} 种，逐条各跑一遍。')
    warnings = [item for item in warnings if str(item.get('code') or '') != 'scope_adaptation']
    lines.append('')
    lines.append('警告面板：')
    if warnings:
        lines.extend((f"- 尾号{str(item['autoid'])[-6:]}：{item['message']}（{item['code']}）" for item in warnings))
    else:
        lines.append('- 当前没有软提示')
    lines.append(f'签约哈希：{digest}')
    return '\n'.join(lines)

def _render_card_v3(payload: dict[str, Any], digest: str, *, mask_author_text: bool=False) -> str:
    pattern = payload['behavior_pattern']
    cases = payload['cases']
    warnings = payload['warnings']
    tails = '、'.join((f"尾号{c['autoid'][-6:]}" for c in cases))
    lines = [f"行为模式：{pattern['capability_family']} × {pattern['verification_shape']}", f'适用用例：{len(cases)} 案（{tails}）']
    for case in cases:
        method = case['verification_method']
        rule_id = str(method.get('selected_rule_id') or '')
        if rule_id:
            snapshot = method.get('selected_rule_snapshot') or {}
            rule_line = f"已选规则“{snapshot.get('name_zh') or method['selected_rule']}”（注册规则 {rule_id}·{snapshot.get('status') or ''}：{snapshot.get('zh_template') or ''}；出处：{method['authority']}）" if snapshot else f"已选规则“{method['selected_rule']}”（未认证规则——不在注册表闭集内；出处：{method['authority']}）"
        else:
            rule_line = f"已选规则“{method['selected_rule']}”（未认证规则——不在注册表闭集内；出处：{method['authority']}）"
        expects = '；'.join((f"{_author_card_text(item['text'], mask_author_text)}（出处：{_author_card_anchor(item['text_anchor'], item['text'], mask_author_text)}；绑定：{item['value_grounding']}" + (f"；covered_by={item['covered_by']}；exempted_part={item['exempted_part']}；reason={item['reason']}" if item.get('covered_by') else '') + '）' for item in case['expectations']))
        declared = [item for item in case['expectations'] if item.get('covered_by')]
        if declared:
            flip_line = f'{len(declared)} 条期望按声明部分豁免（理由码在期望条目内），其余期望的翻转凭据在上机时由变异测试机械铸造'
        else:
            flip_line = '每条期望的判别力凭据（翻转或带码豁免）在上机时由变异测试机械铸造——交付前缺凭据不得出厂'
        lines.append(f"- 尾号{case['autoid'][-6:]}")
        lines.append(f"  你的要求（脑图原文）：“{_author_card_text(case['intent_verbatim'], mask_author_text)}”")
        lines.append(f'  机器打算这样验证：{rule_line}')
        for alternative in method['alternatives']:
            lines.append(f"    备选规则“{alternative['rule']}”（出处：{alternative['authority']}；未选原因：{alternative['rejection_reason']}）")
        lines.append(f'  期望值的来历：{expects}')
        lines.append(f'  凭什么不是白查：{flip_line}')
        if case['scope_adaptations']:
            lines.append('  范围适配：' + '；'.join(case['scope_adaptations']))
    lines.append('警告面板：')
    if warnings:
        lines.extend((f"- 尾号{str(item['autoid'])[-6:]}：{item['message']}（{item['code']}）" for item in warnings))
    else:
        lines.append('- 当前没有结构化软提示')
    lines.append(f'签约哈希：{digest}')
    return '\n'.join(lines)

def _render_card_v2(payload: dict[str, Any], digest: str) -> str:
    pattern = payload['behavior_pattern']
    cases = payload['cases']
    warnings = payload['warnings']
    lines = [f"行为模式：{pattern['capability_family']} × {pattern['verification_shape']}", f"适用用例：{len(cases)} 案（{'、'.join((c['autoid'] for c in cases))}）"]
    for case in cases:
        method = case['verification_method']
        expects = '；'.join((f"{item['text']}（出处：{item['text_anchor']}；绑定：{item['value_grounding']}" + (f"；covered_by={item['covered_by']}；exempted_part={item['exempted_part']}；reason={item['reason']}" if item.get('covered_by') else '') + '）' for item in case['expectations']))
        lines.append(f"- {case['autoid']}：意图“{case['intent_verbatim']}”；已选规则“{method['selected_rule']}”（出处：{method['authority']}）；期望：{expects}")
        for alternative in method['alternatives']:
            lines.append(f"  备选规则“{alternative['rule']}”（出处：{alternative['authority']}；未选原因：{alternative['rejection_reason']}）")
        if case['scope_adaptations']:
            lines.append('  范围适配：' + '；'.join(case['scope_adaptations']))
    lines.append('警告面板：')
    if warnings:
        lines.extend((f"- {item['autoid']}：{item['message']}（{item['code']}）" for item in warnings))
    else:
        lines.append('- 当前没有结构化软提示')
    lines.append(f'签约哈希：{digest}')
    return '\n'.join(lines)

def _record_for_source(source_autoid: str, package_projection: dict[str, Any]) -> dict[str, Any]:
    if not source_autoid:
        return {}
    records = package_projection.get('records')
    if not isinstance(records, dict):
        return {}
    direct = records.get(f'verified_{source_autoid}.xlsx')
    if isinstance(direct, dict):
        return direct
    for record in records.values():
        if isinstance(record, dict) and source_autoid in {str(value) for value in record.get('autoids') or []}:
            return record
    return {}

def build_warning_panel(contracts: list[dict[str, Any]], package_projection: dict[str, Any] | None=None, extra_items: list[dict[str, str]] | None=None) -> dict[str, Any]:
    projection = package_projection if isinstance(package_projection, dict) else {}
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for extra in extra_items or []:
        if not isinstance(extra, dict):
            continue
        item = (str(extra.get('autoid') or ''), str(extra.get('code') or ''), str(extra.get('message') or ''))
        if all(item) and item not in seen:
            seen.add(item)
            items.append({'autoid': item[0], 'code': item[1], 'message': item[2]})
    for contract in sorted(contracts, key=lambda row: row['autoid']):
        autoid = contract['autoid']
        adaptations = [str(x) for x in contract.get('scope_adaptations') or []]
        if adaptations:
            item = (autoid, 'scope_adaptation', str(len(adaptations)))
            if item not in seen:
                seen.add(item)
                items.append({'autoid': autoid, 'code': 'scope_adaptation', 'message': f'{len(adaptations)} 种配置组合，需要保证设计完整'})
        for cf in contract.get('command_findings') or []:
            code = str(cf.get('code') or '')
            if code not in _WARNING_LABELS:
                continue
            message = f"{_WARNING_LABELS[code]}：{cf.get('command')}——{cf.get('note')}"
            item = (autoid, code, message)
            if item not in seen:
                seen.add(item)
                items.append({'autoid': autoid, 'code': code, 'message': message})
        record = _record_for_source(str(contract.get('source_autoid') or ''), projection)
        codes = [str(code) for code in list(record.get('flags') or []) + list((record.get('lint') or {}).get('advisories') or []) if str(code) in _WARNING_LABELS]
        for code in sorted(set(codes)):
            item = (autoid, code, _WARNING_LABELS[code])
            if item not in seen:
                seen.add(item)
                items.append({'autoid': autoid, 'code': code, 'message': _WARNING_LABELS[code]})
    signed = {'schema': WARNING_PANEL_SCHEMA, 'items': items}
    lines = ['警告面板']
    if not items:
        lines.append('- 当前没有软提示')
    else:
        lines.extend((f"- {item['autoid']}：{item['message']}（{item['code']}）" for item in items))
    return {**signed, 'panel_hash': _canonical_hash(signed), 'rendered_zh': '\n'.join(lines)}

def build_validation_cards(contracts: list[dict[str, Any]], *, warning_panel: dict[str, Any] | None=None) -> list[dict[str, Any]]:
    _ = warning_panel
    groups: dict[str, list[dict[str, Any]]] = {}
    for contract in contracts:
        groups.setdefault(cluster_key(contract), []).append(contract)
    cards: list[dict[str, Any]] = []
    for key, members in sorted(groups.items()):
        members = sorted(members, key=lambda row: row['autoid'])
        is_mindmap = members[0].get('contract_class') == 'mindmap_verbatim'
        cases = []
        for member in members:
            cases.append({'autoid': member['autoid'], 'source_autoid': member.get('source_autoid', ''), 'intent_verbatim': member['intent_verbatim'], 'intent_anchor': member['intent_anchor'], 'verification_method': member['verification_method'], 'expectations': member['expectations'], 'scope_adaptations': member['scope_adaptations'], **({'bucket': member['bucket']} if member.get('bucket') else {}), **({'source_status': member['source_status'], 'typed_assertion_status': member['typed_assertion_status']} if is_mindmap else {})})
        signed_payload = {'schema_version': SCHEMA_VERSION, 'cluster_key': key, **({'contract_class': 'mindmap_verbatim', 'mindmap_group': members[0]['mindmap_group']} if is_mindmap else {'behavior_pattern': members[0]['behavior_pattern']}), 'cases': cases, 'warnings': []}
        digest = _canonical_hash(signed_payload)
        rendered = _render_card(signed_payload, digest)
        from cex_core.engine.case_compiler.card_lint import card_lint_findings
        findings = card_lint_findings(rendered, internal_text=_render_card(signed_payload, digest, mask_author_text=True))
        blocking = [f for f in findings if f['code'] != 'card_shape_warn']
        if blocking:
            detail = '; '.join((f"{f['code']}:{f['token'][:40]} ({f['hint']})" for f in blocking[:5]))
            raise ContractError(f'card face for cluster {key} carries internal jargon and was refused: {detail}')
        cards.append({**signed_payload, 'card_hash': digest, 'rendered_zh': rendered, 'lint_advisories': findings})
    return cards

def load_contract_cards(contracts_dir: Path, package_projection: dict[str, Any] | None=None, extra_warning_items: list[dict[str, str]] | None=None) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    contracts: list[dict[str, Any]] = []
    errors: list[str] = []
    directory_fd: int | None = None
    try:
        directory_fd = open_directory_nofollow(contracts_dir, error_type=ContractError, invalid_message='contracts directory path is invalid', unavailable_message='contracts directory is unavailable')
        names = sorted((name for name in os.listdir(directory_fd) if name.endswith('.json') and Path(name).name == name))
        for name in names:
            try:
                encoded = read_regular_at_nofollow(directory_fd, name, error_type=ContractError, open_message='contract is unavailable', bounds_message='contract exceeds its sealed size boundary', changed_message='contract changed while being read', max_bytes=4 * 1024 * 1024, min_bytes=1)
                assert isinstance(encoded, bytes)
                validate_json_budget(encoded, error_type=ContractError, message='contract exceeds the JSON structure budget', max_tokens=100000)
                raw = json.loads(encoded.decode('utf-8'))
                contracts.append(normalize_contract(raw, name))
            except Exception as exc:
                errors.append(f'{name}: {exc}')
    except Exception as exc:
        errors.append(f'contracts/: {exc}')
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    warning_panel = build_warning_panel(contracts, package_projection, extra_items=extra_warning_items)
    cards = build_validation_cards(contracts) if contracts else []
    return (cards, warning_panel, errors)

def load_signatures(path: Path) -> dict[str, dict[str, Any]]:
    try:
        encoded = read_regular_nofollow(path, error_type=ContractError, invalid_message='signature path is invalid', directory_message='signature directory is unavailable', open_message='signature file is unavailable', bounds_message='signature file exceeds its sealed size boundary', changed_message='signature file changed while being read', max_bytes=4 * 1024 * 1024, min_bytes=1)
        assert isinstance(encoded, bytes)
        validate_json_budget(encoded, error_type=ContractError, message='signature file exceeds the JSON structure budget', max_tokens=100000)
        payload = json.loads(encoded.decode('utf-8'))
        signatures = payload.get('signatures') if isinstance(payload, dict) else None
        return signatures if isinstance(signatures, dict) else {}
    except Exception:
        return {}

def signature_valid(card: dict[str, Any], signature: dict[str, Any] | None) -> bool:
    if not isinstance(signature, dict):
        return False
    try:
        signed_payload = _signed_card_payload(card)
        digest = _canonical_hash(signed_payload)
        canonical_render = _render_card(signed_payload, digest)
    except Exception:
        return False
    return bool(card.get('card_hash') == digest and card.get('rendered_zh') == canonical_render and (signature.get('decision') == CONFIRM_LABEL) and (signature.get('card_hash') == digest) and (signature.get('case_autoids') == [case['autoid'] for case in card.get('cases') or []]))

def sign_card(card: dict[str, Any], decision: str) -> dict[str, Any]:
    if decision != CONFIRM_LABEL:
        raise ContractError('only an explicit confirm decision can sign a contract card')
    try:
        signed_payload = _signed_card_payload(card)
        digest = _canonical_hash(signed_payload)
        canonical_render = _render_card(signed_payload, digest)
    except Exception as exc:
        raise ContractError('card payload is incomplete') from exc
    if card.get('card_hash') != digest or card.get('rendered_zh') != canonical_render:
        raise ContractError('card payload or rendered text does not match card_hash')
    if int(signed_payload.get('schema_version') or 0) >= 3:
        from cex_core.engine.case_compiler.card_lint import card_lint_findings
        blocking = [f for f in card_lint_findings(canonical_render, internal_text=_render_card(signed_payload, digest, mask_author_text=True)) if f['code'] != 'card_shape_warn']
        if blocking:
            detail = '; '.join((f"{f['code']}:{f['token'][:40]}" for f in blocking[:5]))
            raise ContractError(f'card face carries internal jargon and cannot be signed: {detail}')
    return {'cluster_key': card['cluster_key'], 'card_hash': digest, 'case_autoids': [case['autoid'] for case in card['cases']], 'decision': CONFIRM_LABEL, 'signed_by': 'user', 'signed_at': time.time()}

def encode_json_atomic(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def write_json_atomic(path: Path, payload: dict[str, Any]) -> str:
    encoded = encode_json_atomic(payload)
    atomic_write_bytes_nofollow(path, encoded, error_type=ContractError, invalid_message='JSON output path is invalid', unavailable_message='JSON output directory is unavailable')
    return sha256_bytes(encoded)

def read_intent_json(path: Path, *, trusted_root: Path | None=None) -> tuple[dict[str, Any], bytes]:
    try:
        encoded = read_regular_nofollow(path, trusted_root=trusted_root, error_type=ContractError, invalid_message='intent JSON path is invalid', directory_message='intent JSON directory is unavailable', open_message='intent JSON is unavailable', bounds_message='intent JSON exceeds its sealed size boundary', changed_message='intent JSON changed while being read', max_bytes=INTENT_JSON_MAX_BYTES, min_bytes=1, require_current_uid=True)
        assert isinstance(encoded, bytes)
        validate_json_budget(encoded, error_type=ContractError, message='intent JSON exceeds its structure budget')
        payload = json.loads(encoded.decode('utf-8'))
    except ContractError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError('intent JSON is not valid JSON') from exc
    if not isinstance(payload, dict):
        raise ContractError('intent JSON must be an object')
    return (payload, encoded)

def write_intent_json_atomic(path: Path, payload: dict[str, Any]) -> str:
    try:
        encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ContractError('intent JSON cannot be encoded') from exc
    if len(encoded) > INTENT_JSON_MAX_BYTES:
        raise ContractError('intent JSON exceeds its sealed size boundary')
    validate_json_budget(encoded, error_type=ContractError, message='intent JSON exceeds its structure budget')
    atomic_write_bytes_nofollow(path, encoded, error_type=ContractError, invalid_message='intent JSON output path is invalid', unavailable_message='intent JSON output directory is unavailable')
    return sha256_bytes(encoded)
