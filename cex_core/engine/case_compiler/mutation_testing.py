# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mutation_testing.py（sha256 205e5e339a01d2c0）。不在这里手改。
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import shlex
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler.pass_audit import SCHEMA as PASS_AUDIT_SCHEMA
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.case_compiler.provenance_ir import ASSERTION_TYPE_SCHEMA, AUTHOR_DECLARABLE_EXEMPT_CODES, COMPILER_ISSUED_EXEMPT_CODES, EXEMPT_REASON_CODES, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, MUTATION_ROLE_CONTROL
MUTATION_SCHEMA = 'ist.ide.mutation'
LEGACY_DELIVERY_CREDENTIAL_SCHEMA = 'ist.ide.legacy-delivery-credential'
EXEMPT_GOVERNANCE_SCHEMA = 'ist.ide.exempt-governance'
EXEMPT_MAX_RATIO = 0.5
EXEMPT_REVIEW_DAYS = 30
_INVERSE_ASSERTION = {'found': 'not_found', 'not_found': 'found'}
_ADVISORY_MESSAGES = {'flip_baseline_unavailable': '干净态底账没有这条观测命令的可用记录，翻转判据交上机实证', 'vacuous_found_in_clean': '干净态底账已经满足这条正向断言，判别力灰显', 'flip_baseline_not_discriminating': '干净态底账不能把这条断言翻转过来，判别力交上机实证', FLIP_CONTROL_UNCONSTRUCTIBLE_REASON: '这条断言在案内构造不出反向对照，编译器已附豁免码，判别力交上机实证', 'non_readonly_probe': '这条断言的观测窗不是设备只读探针，编译器复算后自行签发豁免码，判别力交上机实证', 'inserted_observation_noninterference_unverified': '编译器已插入一次额外观测；该观测是否影响后续状态尚未核验'}
_READONLY_WINDOW_HEADS = frozenset({'show', 'get'})
_NON_DEVICE_WINDOW_OBJECTS = frozenset({'', 'test_env', 'time', 'check_point'})
_CLIENT_CONTROL_SHELL_SYNTAX_RE = re.compile('[\\r\\n;&|`<>]|\\$\\(')
_MUTATION_BEFORE_RE = re.compile('^\\[IDE-MUTATION-BEFORE:([1-9][0-9]*)\\]$')
_MUTATION_CONTROL_RE = re.compile('^\\[IDE-MUTATION-CONTROL:([1-9][0-9]*)\\]$')
ENGINE_COMPUTED_EXEMPT_CODES = frozenset({'non_readonly_probe'})
EXEMPT_ISSUER_COMPILER = 'compiler'

def _readonly_command_head(command: str) -> bool:
    text = str(command or '').strip()
    if not text:
        return False
    return text.split(None, 1)[0].lower() in _READONLY_WINDOW_HEADS

def _readonly_device_window(command: str, window_e: str) -> bool:
    return _readonly_command_head(command) and str(window_e or '').strip() not in _NON_DEVICE_WINDOW_OBJECTS

def _state_changing_config_step(step: Any) -> bool:
    if not isinstance(step, dict):
        return False
    if str(step.get('F') or '').strip() not in {'cmd_config', 'cmds_config'}:
        return False
    return not _readonly_device_window(str(step.get('G') or ''), str(step.get('E') or ''))

def _auto_in_case_window_error(command: str, window_e: str, *, assertion_count: int) -> str:
    text = str(command or '').strip()
    e_value = str(window_e or '').strip()
    if _readonly_device_window(text, e_value):
        return ''
    if e_value != 'test_env':
        return 'window is not a read-only device show/get command'
    if assertion_count != 1:
        return 'client pre-config control is limited to a case with exactly one product assertion so the extra observation cannot contaminate sibling statistics or ordering assertions'
    if not text or _CLIENT_CONTROL_SHELL_SYNTAX_RE.search(text):
        return 'client pre-config control requires one observation command without shell chaining, pipes, redirection, substitution, or background syntax'
    try:
        from cex_core.engine.case_compiler.domain_grammar import verbs
        probe_heads = frozenset(verbs('mutation_preconfig_client_probes'))
    except Exception:
        return 'client observation grammar is unavailable'
    command_text = text
    if len(command_text) >= 2 and command_text[0] == command_text[-1] and (command_text[0] in {'"', "'"}):
        command_text = command_text[1:-1].strip()
    try:
        parts = shlex.split(command_text, posix=True)
    except ValueError:
        return 'client observation command is not valid single-command shell syntax'
    head = parts[0].rsplit('/', 1)[-1].lower() if parts else ''
    if head not in probe_heads:
        return 'client pre-config control requires a command head from the mutation-specific generated domain grammar'
    return ''

def _auto_in_case_window_supported(command: str, window_e: str, *, assertion_count: int) -> bool:
    return not _auto_in_case_window_error(command, window_e, assertion_count=assertion_count)

def mutation_control_order_failure(steps: list[dict[str, Any]]) -> str:

    def marker_text(step: dict[str, Any]) -> str:
        return str(step.get('desc') or step.get('D') or '').strip()
    for index, step in enumerate(steps):
        before = _MUTATION_BEFORE_RE.fullmatch(marker_text(step))
        if before is None:
            continue
        ordinal = before.group(1)
        if index + 1 >= len(steps):
            return f'mutation BEFORE {ordinal} is not followed by its CONTROL row'
        control = _MUTATION_CONTROL_RE.fullmatch(marker_text(steps[index + 1]))
        if control is None:
            return f'mutation BEFORE {ordinal} is not followed by its CONTROL row'
        if control.group(1) != ordinal:
            return f'mutation BEFORE {ordinal} is paired with another CONTROL ordinal'
        cursor = index + 2
        while cursor < len(steps) and (_MUTATION_BEFORE_RE.fullmatch(marker_text(steps[cursor])) or _MUTATION_CONTROL_RE.fullmatch(marker_text(steps[cursor]))):
            cursor += 1
        if cursor >= len(steps) or not _state_changing_config_step(steps[cursor]):
            return f'mutation BEFORE/CONTROL {ordinal} does not precede its config anchor'
    return ''

def _parse_requirements(value: Any) -> tuple[list[dict[str, Any]], str]:
    if value is None or value == '':
        return ([], '')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as exc:
            return ([], f'mutation requirements are not valid JSON: {exc}')
    if not isinstance(value, list):
        return ([], 'mutation requirements must be an array')
    if not all((isinstance(item, dict) for item in value)):
        return ([], 'each mutation requirement must be an object')
    return ([dict(item) for item in value], '')

def derive_mutation_requirements(steps: list[dict[str, Any]], exemptions_value: Any, *, device_build: str) -> tuple[list[dict[str, Any]], str]:
    exemptions, error = _parse_requirements(exemptions_value)
    if error:
        return ([], error)
    if exemptions:
        return ([], 'mutation requirements are compiler-derived; declare only exempt=true and reason_code on the affected check_point step')
    build = str(device_build or '').strip()
    assertion_windows: list[tuple[str, str, str]] = []
    current_window = ''
    current_window_e = ''
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get('E') or '').strip() == 'check_point':
            exempt = step.get('exempt')
            reason_code = str(step.get('reason_code') or '').strip()
            if exempt not in (None, False, True):
                return ([], 'check_point exempt must be a boolean')
            if exempt is not True and reason_code:
                return ([], 'check_point reason_code is valid only when exempt=true')
            if exempt is True and reason_code not in AUTHOR_DECLARABLE_EXEMPT_CODES:
                return ([], f'check_point Exempt.reason_code must be one of {sorted(AUTHOR_DECLARABLE_EXEMPT_CODES)}')
            assertion_windows.append((current_window, current_window_e, reason_code if exempt is True else ''))
            continue
        if str(step.get('H') or '').strip():
            continue
        current_window = str(step.get('G') or '').strip()
        current_window_e = str(step.get('E') or '').strip()
    requirements: list[dict[str, Any]] = []
    assertion_count = len(assertion_windows)
    for ordinal, (command, window_e, reason_code) in enumerate(assertion_windows, start=1):
        engine_computed = reason_code in ENGINE_COMPUTED_EXEMPT_CODES
        if engine_computed and _auto_in_case_window_supported(command, window_e, assertion_count=assertion_count):
            engine_computed = False
        if reason_code:
            requirement: dict[str, Any] = {'assertion_ordinals': [ordinal], 'mode': 'exempt', 'reason_code': reason_code}
            if engine_computed:
                requirement['issuer'] = EXEMPT_ISSUER_COMPILER
                requirement['auto_derived'] = True
            if window_e == 'test_env':
                requirement['window_channel'] = 'client'
            requirements.append(requirement)
            continue
        if not command:
            return ([], f'assertion {ordinal} has no preceding observation window command')
        if not build:
            return ([], f'assertion {ordinal} cannot derive ledger mutation without the engine-issued device build')
        requirements.append({'assertion_ordinals': [ordinal], 'mode': 'ledger', 'observation_command': command, 'device_build': build})
    return (requirements, '')

def _negative_target_introduced_by_forward_config(config_step: dict[str, Any], *, operator: str, pattern: str, device_build: str) -> bool:
    if operator != 'not_found' or not pattern:
        return False
    config_text = str(config_step.get('G') or '')
    if not config_text:
        return False
    try:
        if re.search(pattern, config_text, re.MULTILINE) is None:
            return False
    except re.error:
        return False
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import derive_inverse_pairs
        forward_heads = {str(head).strip().casefold() for head in derive_inverse_pairs(device_build=device_build) if str(head).strip()}
    except Exception:
        return False
    for line in config_text.splitlines() or [config_text]:
        folded = line.strip().casefold()
        try:
            line_has_pattern = re.search(pattern, line) is not None
        except re.error:
            line_has_pattern = False
        if line_has_pattern and any((folded == head or folded.startswith(head + ' ') for head in forward_heads)):
            return True
    return False

def _preserved_assertion_control_conflict(steps: list[dict[str, Any]], original_index: int, config_index: int) -> str:
    original = steps[original_index]
    if any((str(original.get(key) or '').strip() for key in ('H', 'I'))):
        return ''

    def window_key(index: int) -> tuple[str, str, str] | None:
        for previous in reversed(steps[:index]):
            if not isinstance(previous, dict):
                return None
            if previous.get('E') == 'check_point' or str(previous.get('H') or '').strip():
                continue
            if not _readonly_device_window(previous.get('G', ''), previous.get('E', '')):
                return None
            return tuple((str(previous.get(key) or '') for key in ('E', 'F', 'G')))
        return None
    target_window = window_key(original_index)
    if target_window is None:
        return ''
    for index in range(config_index - 1, -1, -1):
        candidate = steps[index]
        if not isinstance(candidate, dict):
            break
        if candidate.get('E') == 'check_point':
            if all((str(candidate.get(key) or '') == str(original.get(key) or '') for key in ('F', 'G'))) and (not any((str(candidate.get(key) or '').strip() for key in ('H', 'I')))) and (window_key(index) == target_window):
                return f'the same result-window assertion already occurs at steps[{index}] before config steps[{config_index}], with only assertions and read-only device observations in between; inserting its inverse there would contradict the existing before-state requirement'
            continue
        if not _readonly_device_window(candidate.get('G', ''), candidate.get('E', '')):
            break
    return ''

def _auto_in_case_requirement(steps: list[dict[str, Any]], prov_steps: list[Any], original_index: int, command: str, *, assertion_count: int, operator: str, pattern: str, device_build: str) -> tuple[dict[str, Any] | None, str]:
    from cex_core.engine.case_compiler.provenance_ir import _DERIVED_SOURCE_KINDS
    if 0 <= original_index < len(prov_steps):
        origin = prov_steps[original_index]
        origin_source = origin.get('source') if isinstance(origin, dict) else None
        derivation = origin_source.get('receipt') if isinstance(origin_source, dict) else None
        if isinstance(origin_source, dict) and str(origin_source.get('kind') or '') in _DERIVED_SOURCE_KINDS and isinstance(derivation, dict) and isinstance(derivation.get('source_input'), dict):
            return (None, f"the expected value is a registered derivation output ({origin_source.get('kind')}); an inverted control row is never a legal output of that rule")
    window_index = None
    for idx in range(original_index - 1, -1, -1):
        step = steps[idx]
        if not isinstance(step, dict):
            continue
        if str(step.get('E') or '').strip() == 'check_point':
            continue
        if str(step.get('G') or '').strip() == command:
            window_index = idx
            break
    if window_index is None:
        return (None, 'no observation step carries the window command')
    window_step = steps[window_index]
    if str(window_step.get('H') or '').strip():
        return (None, 'window step carries an H register and is not the result window')
    window_error = _auto_in_case_window_error(command, str(window_step.get('E') or ''), assertion_count=assertion_count)
    if window_error:
        return (None, window_error)
    config_index = None
    for idx in range(window_index - 1, -1, -1):
        candidate = steps[idx]
        if _state_changing_config_step(candidate):
            config_index = idx
            break
    if config_index is None:
        return (None, 'no earlier config step to anchor the control')
    preservation_conflict = _preserved_assertion_control_conflict(steps, original_index, config_index)
    if preservation_conflict:
        return (None, preservation_conflict)
    config_step = steps[config_index]
    if _negative_target_introduced_by_forward_config(config_step, operator=operator, pattern=pattern, device_build=device_build):
        return (None, 'a not_found target is introduced by the nearest forward CONFIG; the same target is normally absent before that command, so an inserted found pre-control would not be a mechanically valid flip')
    if not isinstance(prov_steps, list) or window_index >= len(prov_steps):
        return (None, 'window step has no aligned provenance to copy')
    pre_prov = copy.deepcopy(prov_steps[window_index])
    if not isinstance(pre_prov, dict):
        return (None, 'window step has no aligned provenance to copy')
    pre_prov.pop('assertion_type', None)
    return ({'mode': 'in_case_serialized', 'config_step_index': config_index, 'pre_observe': {'E': str(window_step.get('E') or ''), 'F': str(window_step.get('F') or ''), 'G': command}, 'pre_observe_provenance': pre_prov, 'auto_derived': True}, '')
PRE_OBSERVE_OBSERVATION_PREFIX = 'obs_mutation_'

def _collect_observation_names(prov_steps: list[Any]) -> set[str]:
    taken: set[str] = set()
    for step in prov_steps:
        if not isinstance(step, dict):
            continue
        for key in ('observation_id', 'result_channel'):
            name = str(step.get(key) or '').strip()
            if name:
                taken.add(name)
    return taken

def _mint_pre_observe_observation_id(pending_ref: str, taken: set[str]) -> str:
    digest = hashlib.sha256(str(pending_ref).encode('utf-8')).hexdigest()[:24]
    base = f'{PRE_OBSERVE_OBSERVATION_PREFIX}{digest}'
    candidate = base
    suffix = 1
    while candidate in taken or f'result_{candidate}' in taken:
        candidate = f'{base}_{suffix}'
        suffix += 1
    return candidate

def compiler_inserted_observation_ids(receipt: Any) -> set[str]:
    out: set[str] = set()
    if not isinstance(receipt, dict):
        return out
    for item in receipt.get('requirements') or []:
        if not isinstance(item, dict):
            continue
        if str(item.get('mode') or '') != 'in_case_serialized':
            continue
        name = str(item.get('pre_observe_observation_id') or '').strip()
        if name:
            out.add(name)
    return out

def _assertion_window_channel(steps: list[dict[str, Any]], original_index: int) -> str:
    for index in range(original_index - 1, -1, -1):
        step = steps[index]
        if not isinstance(step, dict):
            continue
        if str(step.get('E') or '').strip() == 'check_point':
            continue
        if str(step.get('H') or '').strip():
            continue
        return 'client' if str(step.get('E') or '').strip() == 'test_env' else ''
    return ''

def _advisory(ordinal: int, code: str, detail: str, command: str, *, message: str='') -> dict[str, Any]:
    return {'assertion_ordinal': ordinal, 'code': code, 'message': f'断言 {ordinal}：{message}' if message else f'断言 {ordinal}：{_ADVISORY_MESSAGES.get(code, code)}', 'detail': str(detail or ''), 'observation_command': str(command or '')}

def _warning_panel(items: list[dict[str, Any]]) -> dict[str, Any]:
    from cex_core.engine.case_compiler.contract_entry import WARNING_PANEL_SCHEMA
    return {'schema': WARNING_PANEL_SCHEMA, 'items': items}

def _evidence_ref(prefix: str, material: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return f'mutation:{prefix}:{digest}'

def _set_flip(prov_step: dict[str, Any], evidence_ref: str) -> str:
    assertion = prov_step.get('assertion_type')
    if not isinstance(assertion, dict):
        return 'typed mutation requires assertion_type on every check_point'
    assertion['flip'] = {'kind': 'Flipped', 'evidence_ref': evidence_ref}
    return ''

def _set_exempt(prov_step: dict[str, Any], reason_code: str) -> str:
    assertion = prov_step.get('assertion_type')
    if not isinstance(assertion, dict):
        return 'typed exemption requires assertion_type on every check_point'
    assertion['flip'] = {'kind': 'Exempt', 'reason_code': reason_code}
    return ''

def _bipolar_observation_sequences(steps: list[dict[str, Any]], prov_steps: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[tuple[int, str]]] = {}
    ordinal = 0
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or str(step.get('E') or '').strip() != 'check_point':
            continue
        ordinal += 1
        operator = str(step.get('F') or '').strip()
        pattern = str(step.get('G') or '')
        if operator not in _INVERSE_ASSERTION or not pattern or index >= len(prov_steps):
            continue
        provenance = prov_steps[index]
        if not isinstance(provenance, dict):
            continue
        expectation_id = str(provenance.get('expectation_id') or '').strip()
        semantic_key = str(provenance.get('semantic_key') or '').strip()
        if not expectation_id or not semantic_key:
            continue
        grouped.setdefault((expectation_id, semantic_key, pattern), []).append((ordinal, operator))
    disclosures: list[dict[str, Any]] = []
    for (expectation_id, semantic_key, pattern), sequence in grouped.items():
        operators = [operator for _ordinal, operator in sequence]
        if not {'found', 'not_found'} <= set(operators):
            continue
        disclosures.append({'expectation_id': expectation_id, 'semantic_key': semantic_key, 'assertion_ordinals': [item[0] for item in sequence], 'operators': operators, 'pattern_sha256': hashlib.sha256(pattern.encode('utf-8')).hexdigest()})
    return disclosures

def _bipolar_control_suppression_detail(disclosures: list[dict[str, Any]]) -> str:
    if not disclosures:
        return ''
    rows = [f"expectation_id={item['expectation_id']}, semantic_key={item['semantic_key']}, ordinals={item['assertion_ordinals']}, operators={item['operators']}, pattern_sha256={item['pattern_sha256']}" for item in disclosures]
    return 'the case already contains a found/not_found sequence for the same identity-bound observation object (' + '; '.join(rows) + '); its case-level polarity sensitivity is explicit, so no additional compiler control row was injected'

def _baseline_flips(operator: str, pattern: str, echo: str) -> tuple[bool, str]:
    if operator not in _INVERSE_ASSERTION:
        return (False, 'ledger mutation supports only found/not_found assertions')
    try:
        matched = re.search(pattern, echo, re.DOTALL) is not None
    except re.error as exc:
        return (False, f'assertion pattern is not valid regex: {exc}')
    return (operator == 'found' and (not matched) or (operator == 'not_found' and matched), '')

def _is_compiler_issued_exempt(item: dict[str, Any]) -> bool:
    if str(item.get('issuer') or '') == EXEMPT_ISSUER_COMPILER:
        return True
    return str(item.get('reason_code') or '') in COMPILER_ISSUED_EXEMPT_CODES

def _exempt_bucket(item: dict[str, Any]) -> str:
    if str(item.get('window_channel') or '') == 'client':
        return 'structural'
    if _is_compiler_issued_exempt(item):
        return 'compiler_issued'
    return 'discretionary'

def _governance_counts(items: list[dict[str, Any]]) -> tuple[int, int, int, int, int, float]:
    total = len(items)
    exempt_items = [item for item in items if item.get('status') == 'exempt']
    buckets = [_exempt_bucket(item) for item in exempt_items]
    exempt = len(exempt_items)
    structural = buckets.count('structural')
    compiler_issued = buckets.count('compiler_issued')
    discretionary = exempt - structural
    ratio = discretionary / total if total else 0.0
    return (total, exempt, structural, compiler_issued, discretionary, ratio)

def _all_exempt_are_compiler_issued(items: list[dict[str, Any]]) -> bool:
    exempt_items = [item for item in items if item.get('status') == 'exempt']
    return bool(exempt_items) and all((_is_compiler_issued_exempt(item) for item in exempt_items))

def _exempt_governance(items: list[dict[str, Any]]) -> dict[str, Any]:
    total, exempt, structural, compiler_issued, discretionary, ratio = _governance_counts(items)
    issued = datetime.now(timezone.utc)
    due = issued + timedelta(days=EXEMPT_REVIEW_DAYS)
    return {'schema': EXEMPT_GOVERNANCE_SCHEMA, 'total_assertions': total, 'exempt_assertions': exempt, 'structural_exempt_assertions': structural, 'compiler_issued_exempt_assertions': compiler_issued, 'discretionary_exempt_assertions': discretionary, 'exempt_ratio': round(ratio, 6), 'max_exempt_ratio': EXEMPT_MAX_RATIO, 'within_limit': bool(total > 0 and exempt < total and (ratio <= EXEMPT_MAX_RATIO)), 'review_required': exempt > 0, 'review_status': 'pending' if exempt > 0 else 'not_required', 'issued_at': issued.isoformat(), 'review_due_at': due.isoformat(), 'expires_at': due.isoformat(), 'delivery_run_limit': 1}
EXEMPT_GOVERNANCE_BLOCK_CODES = ('governance_missing', 'governance_schema_invalid', 'governance_counts_mismatch', 'all_assertions_exempt', 'exempt_ratio_exceeded', 'governance_window_invalid', 'governance_review_invalid')
MUTATION_SETTLE_CODES = frozenset({*EXEMPT_GOVERNANCE_BLOCK_CODES, 'mutation_receipt_not_object', 'mutation_receipt_schema_invalid', 'mutation_receipt_artifact_mismatch', 'mutation_receipt_requirements_invalid', 'mutation_ledger_baseline_stale', 'mutation_receipt_balance_inconsistent', 'build_mismatch_at_run', 'mutation_requirement_not_object', 'mutation_requirement_evidence_invalid', 'mutation_receipt_not_ready'})

def _governance_window(governance: dict[str, Any]) -> tuple[datetime, datetime] | None:
    try:
        issued = datetime.fromisoformat(str(governance.get('issued_at') or ''))
        due = datetime.fromisoformat(str(governance.get('review_due_at') or ''))
        expires = datetime.fromisoformat(str(governance.get('expires_at') or ''))
        if any((value.tzinfo is None for value in (issued, due, expires))):
            return None
        issued, due, expires = (value.astimezone(timezone.utc) for value in (issued, due, expires))
        if due != expires or expires <= issued or expires - issued > timedelta(days=EXEMPT_REVIEW_DAYS, seconds=1) or (datetime.now(timezone.utc) >= expires):
            return None
        return (issued, expires)
    except (TypeError, ValueError):
        return None

def exempt_review_content_sha256(receipt: dict[str, Any]) -> str:
    """复审版本身份：业务内容全量入摘要，仅剥离复审自身写入的字段。"""
    content = copy.deepcopy(receipt)
    governance = content.get('exempt_governance')
    if isinstance(governance, dict):
        for key in ('reviewed_at', 'reviewer_sha256', 'review_binding'):
            governance.pop(key, None)
        governance['review_status'] = 'pending' if governance.get('review_required') else 'not_required'
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def _review_bound(receipt: dict[str, Any], governance: dict[str, Any], *, decision: str='approve') -> bool:
    binding = governance.get('review_binding')
    window = _governance_window(governance)
    if not isinstance(binding, dict) or window is None or governance.get('review_status') != ('reviewed' if decision == 'approve' else 'rejected') or (binding.get('decision') != decision) or (binding.get('scope') != 'receipt_version') or (not accepts_schema(binding.get('schema'), 'ist.exempt-review-binding')):
        return False
    reviewer = str(governance.get('reviewer_sha256') or '')
    artifact = str(receipt.get('xlsx_sha256') or '')
    if re.fullmatch('[0-9a-f]{64}', reviewer) is None or re.fullmatch('[0-9a-f]{64}', artifact) is None or binding.get('reviewer_sha256') != reviewer or (binding.get('xlsx_sha256') != artifact) or (binding.get('receipt_content_sha256') != exempt_review_content_sha256(receipt)):
        return False
    try:
        reviewed = datetime.fromisoformat(str(governance.get('reviewed_at') or ''))
        return reviewed.tzinfo is not None and window[0] <= reviewed.astimezone(timezone.utc) < window[1]
    except (TypeError, ValueError):
        return False

def _exempt_governance_check(receipt: dict[str, Any], *, allow_compiler_issued_full_exempt: bool=False) -> str:
    items = [item for item in receipt.get('requirements') or [] if isinstance(item, dict)]
    exempt = sum((item.get('status') == 'exempt' for item in items))
    if exempt == 0:
        return ''
    governance = receipt.get('exempt_governance')
    if not isinstance(governance, dict):
        return 'governance_missing'
    if governance.get('schema') != EXEMPT_GOVERNANCE_SCHEMA or governance.get('review_required') is not True or governance.get('review_status') not in {'pending', 'reviewed', 'rejected'}:
        return 'governance_schema_invalid'
    total, exempt, structural, compiler_issued, discretionary, ratio = _governance_counts(items)
    within_limit = bool(total > 0 and exempt < total and (ratio <= EXEMPT_MAX_RATIO))
    issued_disclosure = governance.get('compiler_issued_exempt_assertions')
    if governance.get('total_assertions') != total or governance.get('exempt_assertions') != exempt or governance.get('structural_exempt_assertions') != structural or (issued_disclosure is not None and issued_disclosure != compiler_issued) or (governance.get('discretionary_exempt_assertions') != discretionary) or (governance.get('exempt_ratio') != round(ratio, 6)) or (governance.get('max_exempt_ratio') != EXEMPT_MAX_RATIO) or (governance.get('within_limit') is not within_limit):
        return 'governance_counts_mismatch'
    if not within_limit:
        author_declared = discretionary - compiler_issued
        author_ratio = author_declared / total if total else 0.0
        if not _review_bound(receipt, governance) and (not (allow_compiler_issued_full_exempt and total > 0 and (author_ratio <= EXEMPT_MAX_RATIO) and _all_exempt_are_compiler_issued(items))):
            return 'all_assertions_exempt' if exempt >= total else 'exempt_ratio_exceeded'
    if _governance_window(governance) is None:
        return 'governance_window_invalid'
    if governance.get('review_status') != 'pending' and (not _review_bound(receipt, governance)):
        return 'governance_review_invalid'
    return ''

def exempt_governance_block_codes(receipt: dict[str, Any], *, allow_compiler_issued_full_exempt: bool=False) -> tuple[str, ...]:
    primary = _exempt_governance_check(receipt, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt)
    codes = [primary] if primary else []
    governance = receipt.get('exempt_governance')
    if primary and primary != 'governance_window_invalid' and isinstance(governance, dict) and (_governance_window(governance) is None):
        codes.append('governance_window_invalid')
    return tuple(codes)

def _exempt_governance_ready(receipt: dict[str, Any], *, allow_compiler_issued_full_exempt: bool=False) -> bool:
    return not _exempt_governance_check(receipt, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt)

def exempt_governance_failure_message(receipt: dict[str, Any], *, allow_compiler_issued_full_exempt: bool=True) -> str:
    if not isinstance(receipt, dict):
        return ''
    code = _exempt_governance_check(receipt, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt)
    if not code:
        return ''
    governance = receipt.get('exempt_governance')
    if not isinstance(governance, dict):
        governance = {}
    total = governance.get('total_assertions')
    exempt = governance.get('exempt_assertions')
    compiler_issued = governance.get('compiler_issued_exempt_assertions') or 0
    structural = governance.get('structural_exempt_assertions') or 0
    discretionary = governance.get('discretionary_exempt_assertions') or 0
    author_declared = sum((item.get('status') == 'exempt' and (not _is_compiler_issued_exempt(item)) for item in receipt.get('requirements') or [] if isinstance(item, dict)))
    if code == 'governance_missing':
        return 'IDE mutation receipt declares Exempt assertions but carries no exempt governance record — re-run compile_emit to re-issue it.'
    if code == 'governance_schema_invalid':
        return f'IDE mutation exempt governance record is not a valid {EXEMPT_GOVERNANCE_SCHEMA} receipt (schema or review_status is unusable) — re-run compile_emit to re-issue it.'
    if code == 'governance_counts_mismatch':
        return 'IDE mutation exempt governance counters do not match the requirements they claim to summarise — the receipt is stale or was edited after emit; re-run compile_emit.'
    if code == 'governance_window_invalid':
        return f'IDE mutation exempt governance review window is invalid or has expired ({EXEMPT_REVIEW_DAYS}-day validity) — re-run compile_emit to re-issue the receipt.'
    if code == 'governance_review_invalid':
        return 'IDE mutation exempt governance review record is unusable (reviewer identity or review timestamp out of window) — re-run compile_emit to re-issue the receipt.'
    if code == 'all_assertions_exempt':
        head = f'IDE mutation exemption governance failed: every assertion in this case is exempt ({exempt}/{total} assertions exempt) — a case with zero flip evidence has no discriminating power.'
    else:
        head = f'IDE mutation exemption governance failed: {exempt}/{total} assertions exempt ({discretionary} discretionary, capped at {EXEMPT_MAX_RATIO}).'
    if author_declared:
        if code == 'all_assertions_exempt':
            return head + f' {author_declared} of them are author-declared. A pre-state control needs a pure-read window; an assertion whose observation is itself the action carries none. This case has no assertion left with a control: land at least one assertion on a pure-read window if the procedure has one.'
        return head + f' {author_declared} of them are author-declared, over the discretionary cap. Remove the declaration from an assertion whose observation is a pure read.'
    reasons: list[str] = []
    panel = receipt.get('warning_panel')
    engine_issued_codes = COMPILER_ISSUED_EXEMPT_CODES | ENGINE_COMPUTED_EXEMPT_CODES
    for item in (panel.get('items') if isinstance(panel, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        if item.get('code') not in engine_issued_codes:
            continue
        detail = str(item.get('detail') or '').strip()
        if detail.startswith('author-declared'):
            continue
        if detail and detail not in reasons:
            reasons.append(detail)
    tail = '; the in-case control could not be built because: ' + '; '.join(reasons[:3]) if reasons else ''
    return head + f' These exemptions are all engine-issued ({compiler_issued} compiler-issued, {structural} client-channel), 0 declared by the author. This is not an authoring defect and there is no pragma to remove' + tail + '.'

def review_exempt_governance(receipt: dict[str, Any], *, reviewer_id: str, decision: str) -> tuple[dict[str, Any], str]:
    reviewer = str(reviewer_id or '').strip()
    verdict = str(decision or '').strip().lower()
    if not reviewer:
        return (receipt, 'reviewer_id is required')
    if verdict not in {'approve', 'reject'}:
        return (receipt, 'decision must be approve or reject')
    output = copy.deepcopy(receipt)
    governance = output.get('exempt_governance')
    if not isinstance(governance, dict) or governance.get('schema') != EXEMPT_GOVERNANCE_SCHEMA:
        return (receipt, 'exempt governance receipt is missing')
    if not governance.get('review_required'):
        return (receipt, 'this receipt has no Exempt assertion to review')
    if _governance_window(governance) is None:
        return (receipt, 'exempt governance window is invalid or expired')
    artifact = str(receipt.get('xlsx_sha256') or '')
    if re.fullmatch('[0-9a-f]{64}', artifact) is None:
        return (receipt, 'an artifact-bound receipt is required')
    reviewer_sha = hashlib.sha256(reviewer.encode('utf-8')).hexdigest()
    binding = {'schema': 'ist.exempt-review-binding', 'scope': 'receipt_version', 'decision': verdict, 'xlsx_sha256': artifact, 'reviewer_sha256': reviewer_sha, 'receipt_content_sha256': exempt_review_content_sha256(receipt)}
    if governance.get('review_binding') == binding and _review_bound(receipt, governance, decision=verdict):
        return (output, '')
    governance['review_status'] = 'reviewed' if verdict == 'approve' else 'rejected'
    governance['reviewed_at'] = datetime.now(timezone.utc).isoformat()
    governance['reviewer_sha256'] = reviewer_sha
    governance['review_binding'] = binding
    return (output, '')

def _scrub_declared_mutation_roles(provenance: Any) -> None:
    if not isinstance(provenance, dict):
        return
    steps = provenance.get('steps')
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict):
            step.pop('mutation_role', None)

def _step_flip_evidence_ref(prov_step: Any) -> str:
    if not isinstance(prov_step, dict):
        return ''
    assertion = prov_step.get('assertion_type')
    if not isinstance(assertion, dict):
        return ''
    flip = assertion.get('flip')
    if not isinstance(flip, dict) or flip.get('kind') != 'Flipped':
        return ''
    return str(flip.get('evidence_ref') or '')

def _control_row_balance(receipt_items: list[dict[str, Any]], out_steps: list[dict[str, Any]], prov_steps: list[Any]) -> dict[str, Any]:
    from cex_core.engine.case_compiler.provenance_ir import MUTATION_ROLE_CONTROL
    assertions = [prov_steps[index] for index, step in enumerate(out_steps) if index < len(prov_steps) and isinstance(step, dict) and (str(step.get('E') or '').strip() == 'check_point')]
    control_rows = [step for step in assertions if isinstance(step, dict) and str(step.get('mutation_role') or '') == MUTATION_ROLE_CONTROL]
    product_rows = [step for step in assertions if not isinstance(step, dict) or str(step.get('mutation_role') or '') != MUTATION_ROLE_CONTROL]
    minted_controls = Counter((str(item.get('evidence_ref') or '') for item in receipt_items if str(item.get('mode') or '') == 'in_case_serialized'))
    landed_controls = Counter((_step_flip_evidence_ref(step) for step in control_rows))
    minted_flips = Counter((str(item.get('evidence_ref') or '') for item in receipt_items if str(item.get('evidence_ref') or '')))
    landed_flips = Counter((ref for ref in (_step_flip_evidence_ref(step) for step in product_rows) if ref))
    counts = {'product_assertions': len(product_rows), 'receipt_requirements': len(receipt_items), 'minted_controls': sum(minted_controls.values()), 'landed_controls': sum(landed_controls.values()), 'minted_flip_credentials': sum(minted_flips.values()), 'landed_flip_credentials': sum(landed_flips.values()), 'balanced': True}
    failure = ''
    if len(product_rows) != len(receipt_items):
        failure = f'IDE mutation credential ledger does not balance: the case carries {len(product_rows)} product assertion rows but the receipt records {len(receipt_items)} requirements'
    elif '' in minted_controls:
        failure = 'IDE mutation credential ledger does not balance: an in_case_serialized requirement carries no evidence_ref'
    elif landed_controls != minted_controls:
        failure = f'IDE mutation credential ledger does not balance: the receipt minted {sum(minted_controls.values())} in-case control credential(s) but the case carries {sum(landed_controls.values())} control row(s) bound to them'
    elif landed_flips != minted_flips:
        failure = f'IDE mutation credential ledger does not balance: the receipt records {sum(minted_flips.values())} flip credential(s) but {sum(landed_flips.values())} product assertion row(s) carry a matching flip evidence_ref'
    if failure:
        counts['balanced'] = False
    return {'failure': failure, 'counts': counts}

def compile_mutation_plan(steps: list[dict[str, Any]], provenance: dict[str, Any] | None, requirements_value: Any, *, required: bool, derive_defaults: bool=False, device_build: str='', device_build_source: str='') -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any], str]:
    _scrub_declared_mutation_roles(provenance)
    if derive_defaults:
        requirements, error = derive_mutation_requirements(steps, requirements_value, device_build=device_build)
    else:
        requirements, error = _parse_requirements(requirements_value)
    if error:
        return (steps, provenance, {}, error)
    if required and (not requirements):
        return (steps, provenance, {}, 'IDE assertion types require mutation evidence for every product assertion')
    if not requirements:
        return (steps, provenance, {}, '')
    if not isinstance(provenance, dict):
        return (steps, provenance, {}, 'mutation requirements need aligned provenance')
    if provenance.get('assertion_schema') != ASSERTION_TYPE_SCHEMA:
        return (steps, provenance, {}, f'mutation requirements require assertion_schema={ASSERTION_TYPE_SCHEMA}')
    prov_steps = provenance.get('steps')
    if not isinstance(prov_steps, list) or len(prov_steps) != len(steps):
        return (steps, provenance, {}, 'provenance steps are not aligned before mutation')
    assertion_indices = [index for index, step in enumerate(steps) if str(step.get('E') or '').strip() == 'check_point']
    by_ordinal: dict[int, dict[str, Any]] = {}
    for req_index, requirement in enumerate(requirements):
        ordinals = requirement.get('assertion_ordinals')
        if not isinstance(ordinals, list) or not ordinals:
            return (steps, provenance, {}, f'mutation requirements[{req_index}].assertion_ordinals must be a non-empty array')
        for ordinal in ordinals:
            if not isinstance(ordinal, int) or ordinal < 1:
                return (steps, provenance, {}, 'assertion ordinals are 1-based positive integers')
            if ordinal in by_ordinal:
                return (steps, provenance, {}, f'assertion ordinal {ordinal} is declared twice')
            by_ordinal[ordinal] = requirement
    expected = set(range(1, len(assertion_indices) + 1))
    if set(by_ordinal) != expected:
        return (steps, provenance, {}, f'mutation requirements must cover every product check_point exactly once; expected={sorted(expected)} got={sorted(by_ordinal)}')
    output_steps = [dict(step) for step in steps]
    if derive_defaults:
        for step in output_steps:
            step.pop('exempt', None)
            step.pop('reason_code', None)
    output_provenance = copy.deepcopy(provenance)
    output_prov_steps = output_provenance['steps']
    taken_observation_names = _collect_observation_names(output_prov_steps)
    insertions: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    receipt_items: list[dict[str, Any]] = []
    advisories: list[dict[str, Any]] = []
    bipolar_disclosures = _bipolar_observation_sequences(steps, output_prov_steps)
    bipolar_detail = _bipolar_control_suppression_detail(bipolar_disclosures)
    for ordinal in sorted(by_ordinal):
        requirement = by_ordinal[ordinal]
        original_index = assertion_indices[ordinal - 1]
        original_step = steps[original_index]
        original_prov = output_prov_steps[original_index]
        operator = str(original_step.get('F') or '').strip()
        pattern = str(original_step.get('G') or '')
        mode = str(requirement.get('mode') or '').strip()
        if mode == 'in_case_serialized' and bipolar_detail:
            type_error = _set_exempt(original_prov, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON)
            if type_error:
                return (steps, provenance, {}, f'assertion {ordinal} {type_error}')
            window_channel = _assertion_window_channel(steps, original_index)
            receipt_items.append({'assertion_ordinal': ordinal, 'mode': 'exempt', 'status': 'exempt', 'reason_code': FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, 'auto_derived': True, **({'window_channel': window_channel} if window_channel else {})})
            pre_observe = requirement.get('pre_observe')
            advisories.append(_advisory(ordinal, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, bipolar_detail, str(pre_observe.get('G') or '') if isinstance(pre_observe, dict) else '', message='案体已有同一观测对象的 found/not_found 双极性序列，已免插入额外控制行'))
            continue
        if mode == 'exempt':
            allowed_optional = {'window_channel'} | ({'issuer', 'auto_derived'} if derive_defaults else set())
            if set(requirement) - allowed_optional != {'assertion_ordinals', 'mode', 'reason_code'}:
                return (steps, provenance, {}, f'assertion {ordinal} exempt pragma requires exactly assertion_ordinals/mode/reason_code')
            reason_code = str(requirement.get('reason_code') or '').strip()
            if reason_code not in AUTHOR_DECLARABLE_EXEMPT_CODES:
                return (steps, provenance, {}, f'assertion {ordinal} exempt reason_code must be one of {sorted(AUTHOR_DECLARABLE_EXEMPT_CODES)}')
            engine_issued = derive_defaults and str(requirement.get('issuer') or '') == EXEMPT_ISSUER_COMPILER
            type_error = _set_exempt(original_prov, reason_code)
            if type_error:
                return (steps, provenance, {}, f'assertion {ordinal} {type_error}')
            exempt_item: dict[str, Any] = {'assertion_ordinal': ordinal, 'mode': mode, 'status': 'exempt', 'reason_code': reason_code}
            if engine_issued:
                exempt_item['issuer'] = EXEMPT_ISSUER_COMPILER
                exempt_item['auto_derived'] = True
            if str(requirement.get('window_channel') or '') == 'client':
                exempt_item['window_channel'] = 'client'
            receipt_items.append(exempt_item)
            if engine_issued:
                advisories.append(_advisory(ordinal, reason_code, 'the assertion observation window is not a read-only device show/get path; the compiler recomputed this and issued the exemption itself', str(requirement.get('observation_command') or '')))
            elif reason_code == 'non_readonly_probe':
                advisories.append(_advisory(ordinal, reason_code, 'author-declared; the compiler did not verify whether this read changes device state and inserted no pre-state control', str(requirement.get('observation_command') or ''), message='作者声明这条观测不是纯读；编译器未核，未插前置对照，判别力交上机实证'))
            continue
        if mode == 'ledger':
            command = str(requirement.get('observation_command') or '').strip()
            build = str(requirement.get('device_build') or '').strip()
            if not command or not build:
                return (steps, provenance, {}, f'assertion {ordinal} ledger mutation requires observation_command and device_build')
            from cex_core.engine.case_compiler.local_replay import lookup_flip_baseline
            baseline = lookup_flip_baseline(command, build)
            ledger_gap = ''
            gap_code = ''
            if baseline.get('status') != 'available':
                gap_code = 'flip_baseline_unavailable'
                ledger_gap = f"clean-state baseline is unknown: {baseline.get('reason_code') or 'BASELINE_UNKNOWN'}"
            else:
                flips, replay_error = _baseline_flips(operator, pattern, str(baseline.get('echo') or ''))
                if replay_error:
                    gap_code = 'flip_baseline_unavailable'
                    ledger_gap = replay_error
                elif not flips:
                    gap_code = 'vacuous_found_in_clean' if operator == 'found' else 'flip_baseline_not_discriminating'
                    ledger_gap = 'does not fail against the recorded clean-state baseline'
            if not ledger_gap:
                evidence_ref = _evidence_ref('ledger', {'ordinal': ordinal, 'operator': operator, 'pattern': pattern, 'baseline': baseline})
                type_error = _set_flip(original_prov, evidence_ref)
                if type_error:
                    return (steps, provenance, {}, f'assertion {ordinal} {type_error}')
                receipt_items.append({'assertion_ordinal': ordinal, 'mode': mode, 'status': 'flipped', 'evidence_ref': evidence_ref, 'baseline': baseline})
                continue
            advisories.append(_advisory(ordinal, gap_code, ledger_gap, command))
            if operator not in _INVERSE_ASSERTION or not pattern:
                auto_req, why_not = (None, f"assertion operator {operator or '(empty)'!r} has no in-case inverse control in the framework method set" if operator not in _INVERSE_ASSERTION else 'assertion pattern is empty; there is nothing to invert')
            elif bipolar_detail:
                auto_req, why_not = (None, bipolar_detail)
            else:
                auto_req, why_not = _auto_in_case_requirement(steps, output_prov_steps, original_index, command, assertion_count=len(assertion_indices), operator=operator, pattern=pattern, device_build=device_build)
            if auto_req is None:
                type_error = _set_exempt(original_prov, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON)
                if type_error:
                    return (steps, provenance, {}, f'assertion {ordinal} {type_error}')
                window_channel = _assertion_window_channel(steps, original_index)
                receipt_items.append({'assertion_ordinal': ordinal, 'mode': 'exempt', 'status': 'exempt', 'reason_code': FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, 'auto_derived': True, **({'window_channel': window_channel} if window_channel else {})})
                advisories.append(_advisory(ordinal, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, why_not, command, message='案体已有同一观测对象的 found/not_found 双极性序列，已免插入额外控制行' if why_not == bipolar_detail and bipolar_detail else ''))
                continue
            requirement = {**auto_req, 'assertion_ordinals': [ordinal]}
            mode = 'in_case_serialized'
        if mode != 'in_case_serialized':
            return (steps, provenance, {}, f'assertion {ordinal} mutation mode must be ledger or in_case_serialized or exempt')
        if operator not in _INVERSE_ASSERTION or not pattern:
            return (steps, provenance, {}, f'assertion {ordinal} in-case mutation supports a non-empty found/not_found assertion')
        config_index = requirement.get('config_step_index')
        if not isinstance(config_index, int) or not 0 <= config_index < len(steps):
            return (steps, provenance, {}, f'assertion {ordinal} has invalid config_step_index')
        config_step = steps[config_index]
        if config_index >= original_index or not _state_changing_config_step(config_step):
            return (steps, provenance, {}, f'assertion {ordinal} config_step_index must point to an earlier state-changing config step')
        preservation_conflict = _preserved_assertion_control_conflict(steps, original_index, config_index)
        if preservation_conflict:
            return (steps, provenance, {}, f'assertion {ordinal} in-case mutation control contradicts a before-state requirement: {preservation_conflict}')
        if _negative_target_introduced_by_forward_config(config_step, operator=operator, pattern=pattern, device_build=device_build):
            return (steps, provenance, {}, f'assertion {ordinal} in-case mutation control direction is invalid: a not_found target is introduced by the referenced forward CONFIG')
        pre = requirement.get('pre_observe')
        pre_prov = requirement.get('pre_observe_provenance')
        if not isinstance(pre, dict) or not isinstance(pre_prov, dict):
            return (steps, provenance, {}, f'assertion {ordinal} in-case mutation requires pre_observe and pre_observe_provenance')
        command = str(pre.get('G') or '').strip()
        pre_e = str(pre.get('E') or '').strip()
        client_control = pre_e == 'test_env'
        if client_control and (not (derive_defaults and requirement.get('auto_derived') is True)):
            return (steps, provenance, {}, f'assertion {ordinal} client pre_observe is compiler-derived only; an explicit requirements payload cannot authorize an extra client command')
        window_error = _auto_in_case_window_error(command, pre_e, assertion_count=len(assertion_indices))
        if window_error:
            return (steps, provenance, {}, f'assertion {ordinal} in-case pre_observe is not eligible: {window_error}')
        post_match = any((str(step.get('G') or '').strip() == command and str(step.get('E') or '').strip() != 'check_point' for step in steps[config_index + 1:original_index]))
        if not post_match:
            return (steps, provenance, {}, f'assertion {ordinal} has no matching post-config observation')
        pending_ref = _evidence_ref('pending', {'ordinal': ordinal, 'operator': operator, 'pattern': pattern, 'command': command})
        type_error = _set_flip(original_prov, pending_ref)
        if type_error:
            return (steps, provenance, {}, f'assertion {ordinal} {type_error}')
        marker = f'[IDE-MUTATION-BEFORE:{ordinal}]'
        pre_step = dict(pre)
        pre_step['desc'] = marker
        pre_prov_step = copy.deepcopy(pre_prov)
        pre_observation_id = _mint_pre_observe_observation_id(pending_ref, taken_observation_names)
        pre_result_channel = f'result_{pre_observation_id}'
        taken_observation_names.update({pre_observation_id, pre_result_channel})
        pre_prov_step.pop('assertion_type', None)
        pre_prov_step.pop('observation_ref', None)
        pre_prov_step['observation_id'] = pre_observation_id
        pre_prov_step['result_channel'] = pre_result_channel
        control_step = {'E': 'check_point', 'F': _INVERSE_ASSERTION[operator], 'G': pattern, 'desc': f'[IDE-MUTATION-CONTROL:{ordinal}]'}
        control_prov = copy.deepcopy(original_prov)
        control_prov['mutation_role'] = MUTATION_ROLE_CONTROL
        control_prov.pop('observation_id', None)
        control_prov.pop('result_channel', None)
        control_prov['observation_ref'] = pre_observation_id
        control_prov['assertion_type'] = copy.deepcopy(original_prov['assertion_type'])
        control_prov['assertion_type']['flip'] = {'kind': 'Flipped', 'evidence_ref': pending_ref}
        insertions.setdefault(config_index, []).extend([(pre_step, pre_prov_step), (control_step, control_prov)])
        advisories.append(_advisory(ordinal, 'inserted_observation_noninterference_unverified', 'The compiler inserted this additional observation before the configuration anchor. Its effect on later observations has not been verified; insertion alone establishes neither interference nor non-interference.', command))
        receipt_items.append({'assertion_ordinal': ordinal, 'mode': mode, 'status': 'pending', 'evidence_ref': pending_ref, 'pre_observe': command, 'pre_observe_observation_id': pre_observation_id, 'control_operator': _INVERSE_ASSERTION[operator], 'control_pattern': pattern, **({'control_channel': 'client'} if client_control else {}), **({'auto_derived': True} if requirement.get('auto_derived') is True else {})})
    for index in sorted(insertions, reverse=True):
        for step, prov_step in reversed(insertions[index]):
            output_steps.insert(index, step)
            output_prov_steps.insert(index, prov_step)
    order_failure = mutation_control_order_failure(output_steps)
    if order_failure:
        return (steps, provenance, {}, order_failure)
    balance = _control_row_balance(receipt_items, output_steps, output_prov_steps)
    if balance['failure']:
        return (steps, provenance, {}, balance['failure'])
    governance = _exempt_governance(receipt_items)
    return (output_steps, output_provenance, {'schema': MUTATION_SCHEMA, 'requirements': receipt_items, 'exempt_governance': governance, 'warning_panel': _warning_panel(advisories), 'device_build': str(device_build or '').strip(), 'device_build_source': str(device_build_source or '').strip(), 'inserted_control_steps': sum((len(items) for items in insertions.values())), 'control_row_balance': balance['counts']}, '')

def receipt_balance_self_consistent(receipt: Any) -> bool:
    if not isinstance(receipt, dict):
        return False
    balance = receipt.get('control_row_balance')
    if balance is None:
        return True
    if not isinstance(balance, dict):
        return False
    items = [item for item in receipt.get('requirements') or [] if isinstance(item, dict)]
    minted = sum((str(item.get('mode') or '') == 'in_case_serialized' for item in items))
    return balance.get('balanced') is True and balance.get('minted_controls') == minted and (balance.get('landed_controls') == minted) and (balance.get('receipt_requirements') == len(items))

def receipt_build_mismatch(receipt: dict[str, Any], execution_build: str) -> str:
    if not isinstance(receipt, dict):
        return 'mutation receipt is not an object'
    from cex_core.engine.case_compiler.local_replay import device_build_identity
    raw_run_build = str(execution_build or '').strip()
    run_build = device_build_identity(raw_run_build) if raw_run_build else ''
    recorded: set[str] = set()
    receipt_build = str(receipt.get('device_build') or '').strip()
    if receipt_build:
        recorded.add(device_build_identity(receipt_build))
    for item in receipt.get('requirements') or []:
        if not isinstance(item, dict) or item.get('mode') != 'ledger':
            continue
        baseline = item.get('baseline')
        if isinstance(baseline, dict):
            baseline_build = str(baseline.get('device_os_build') or '').strip()
            if baseline_build:
                recorded.add(device_build_identity(baseline_build))
    if not recorded:
        return ''
    if not run_build:
        return 'run execution build is missing while the receipt binds a build'
    mismatched = sorted((build for build in recorded if build != run_build))
    if mismatched:
        return f'emit-time device build {mismatched} does not match run execution build {run_build}'
    return ''

def _ledger_baseline_assets_current(receipt: Any) -> bool:
    """底账翻转项的 baseline 资产身份是否还是当前那一份。

    同一判据此前在 ``mutation_receipt_ready`` 与 ``mutation_receipt_run_ready``
    各写一遍，``receipt_not_ready_reason`` 要给原因时会写第三遍；抽成一个函数后
    三处同源，求值位置保持原样（两个 ready 都在自己原来那一步调用，不挪进合取
    的短路里）。
    """
    ledger_items = [item for item in receipt.get('requirements') or [] if isinstance(item, dict) and item.get('mode') == 'ledger' and (item.get('status') == 'flipped')] if isinstance(receipt, dict) else []
    if not ledger_items:
        return True
    try:
        from cex_core.engine.case_compiler.local_replay import flip_baseline_asset_identity
        current_identity = flip_baseline_asset_identity()
    except Exception:
        current_identity = {}
    return bool(current_identity and all((isinstance(item.get('baseline'), dict) and item['baseline'].get('asset_identity') == current_identity for item in ledger_items)))

def _completed_mutation_receipt_ready(receipt: dict[str, Any], artifact_sha256: str, *, execution_build: str | None=None, allow_compiler_issued_full_exempt: bool=False) -> bool:
    ledger_assets_current = _ledger_baseline_assets_current(receipt)
    return bool(isinstance(receipt, dict) and receipt.get('schema') == MUTATION_SCHEMA and (receipt.get('xlsx_sha256') == artifact_sha256) and receipt.get('requirements') and ledger_assets_current and receipt_balance_self_consistent(receipt) and (execution_build is None or not receipt_build_mismatch(receipt, execution_build)) and _exempt_governance_ready(receipt, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt) and all((isinstance(item, dict) and item.get('status') in {'flipped', 'exempt'} and (item.get('status') == 'flipped' and re.fullmatch('mutation:(?:ledger|run):[0-9a-f]{64}', str(item.get('evidence_ref') or '')) is not None or (item.get('status') == 'exempt' and str(item.get('reason_code') or '') in EXEMPT_REASON_CODES)) for item in receipt.get('requirements') or [])))

def mutation_receipt_ready(receipt: dict[str, Any], artifact_sha256: str, *, execution_build: str | None=None) -> bool:
    """交付收口维持严格豁免阈值与全部凭据完成要求。"""
    return _completed_mutation_receipt_ready(receipt, artifact_sha256, execution_build=execution_build)

def mutation_receipt_pass_ready(receipt: dict[str, Any], artifact_sha256: str, *, execution_build: str | None=None) -> bool:
    """worker的PASS晋升沿用上机豁免标准，pending仍不属于已完成凭据。"""
    return _completed_mutation_receipt_ready(receipt, artifact_sha256, execution_build=execution_build, allow_compiler_issued_full_exempt=True)

def mutation_receipt_run_ready(receipt: dict[str, Any], artifact_sha256: str, *, execution_build: str | None=None) -> bool:
    if not (isinstance(receipt, dict) and receipt.get('schema') == MUTATION_SCHEMA and (receipt.get('xlsx_sha256') == artifact_sha256) and receipt.get('requirements') and receipt_balance_self_consistent(receipt) and (execution_build is None or not receipt_build_mismatch(receipt, execution_build)) and _exempt_governance_ready(receipt, allow_compiler_issued_full_exempt=True)):
        return False
    if not _ledger_baseline_assets_current(receipt):
        return False
    for item in receipt.get('requirements') or []:
        if not isinstance(item, dict):
            return False
        status = str(item.get('status') or '')
        ref = str(item.get('evidence_ref') or '')
        if status == 'flipped' and re.fullmatch('mutation:(?:ledger|run):[0-9a-f]{64}', ref):
            continue
        if status == 'exempt' and str(item.get('reason_code') or '') in EXEMPT_REASON_CODES:
            continue
        if status == 'pending' and item.get('mode') == 'in_case_serialized' and re.fullmatch('mutation:pending:[0-9a-f]{64}', ref):
            continue
        return False
    return True

def receipt_not_ready_reason(receipt: dict[str, Any], artifact_sha256: str, *, execution_build: str | None=None, allow_compiler_issued_full_exempt: bool=False) -> str:
    """``mutation_receipt_ready`` 不成立时说出是哪一条不成立；成立时回空串。

    ``mutation_receipt_ready`` 只回 bool，收口失败因此只能报 ``status=unknown``、
    带不出原因，而 03 章 §26.3 要求「无法完成收口时保留原因并显示」。本函数按
    ``mutation_receipt_ready`` 自己的合取顺序逐条复核，返回第一条不成立的码；
    判据不另写一份——豁免治理取 ``_exempt_governance_check`` 已经算出的码，
    底账资产与自洽性取同一批谓词。ready 却来问的情况回空串，
    ``mutation_receipt_not_ready`` 只在 ready 新增了这里还不认识的条件时出现。
    """
    if _completed_mutation_receipt_ready(receipt, artifact_sha256, execution_build=execution_build, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt):
        return ''
    if not isinstance(receipt, dict):
        return 'mutation_receipt_not_object'
    if receipt.get('schema') != MUTATION_SCHEMA:
        return 'mutation_receipt_schema_invalid'
    if receipt.get('xlsx_sha256') != artifact_sha256:
        return 'mutation_receipt_artifact_mismatch'
    if not receipt.get('requirements'):
        return 'mutation_receipt_requirements_invalid'
    if not _ledger_baseline_assets_current(receipt):
        return 'mutation_ledger_baseline_stale'
    if not receipt_balance_self_consistent(receipt):
        return 'mutation_receipt_balance_inconsistent'
    if execution_build is not None and receipt_build_mismatch(receipt, execution_build):
        return 'build_mismatch_at_run'
    governance = _exempt_governance_check(receipt, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt)
    if governance:
        return governance
    for item in receipt.get('requirements') or []:
        if not isinstance(item, dict):
            return 'mutation_requirement_not_object'
        status = str(item.get('status') or '')
        if status == 'flipped' and re.fullmatch('mutation:(?:ledger|run):[0-9a-f]{64}', str(item.get('evidence_ref') or '')):
            continue
        if status == 'exempt' and str(item.get('reason_code') or '') in EXEMPT_REASON_CODES:
            continue
        return 'mutation_requirement_evidence_invalid'
    return 'mutation_receipt_not_ready'

def mutation_credential_path(autoid: str, credential_root: Path) -> Path:
    identity = str(autoid or '').strip()
    if not re.fullmatch('[A-Za-z0-9_.-]+', identity):
        raise ValueError('unsafe mutation credential identity')
    return credential_root / f'{identity}.json'

def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

def publish_mutation_credential(receipt: dict[str, Any], credential_root: Path) -> None:
    autoid = str(receipt.get('autoid') or '')
    path = mutation_credential_path(autoid, credential_root)
    _write_json_atomic(path, receipt)

def clear_mutation_credential(autoid: str, credential_root: Path) -> None:
    mutation_credential_path(autoid, credential_root).unlink(missing_ok=True)

def load_mutation_credential(autoid: str, credential_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(mutation_credential_path(autoid, credential_root).read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}

def mint_legacy_delivery_credential(case_dir: Path, *, autoid: str, case_artifact: str, final_artifact_sha256: str, delivery_verdict: dict[str, Any], credential_root: Path) -> dict[str, Any]:
    identity = str(autoid or '').strip()
    provenance_path = case_dir / 'case.provenance.json'
    case_path = case_dir / 'case.xlsx'
    if not provenance_path.is_file():
        return {'status': 'not_applicable'}
    try:
        provenance_bytes = provenance_path.read_bytes()
        provenance = json.loads(provenance_bytes.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {'status': 'rejected', 'reason_code': 'LEGACY_PROVENANCE_UNREADABLE'}
    if not isinstance(provenance, dict):
        return {'status': 'rejected', 'reason_code': 'LEGACY_PROVENANCE_INVALID'}
    if provenance.get('assertion_schema') == ASSERTION_TYPE_SCHEMA:
        return {'status': 'not_applicable'}
    provisional = provenance.get('provisional_at_emit', provenance.get('provisional', True))
    final_sha = str(final_artifact_sha256 or '').strip().lower()
    verdict = delivery_verdict if isinstance(delivery_verdict, dict) else {}
    run_id = str(verdict.get('run_id') or '').strip()
    if not re.fullmatch('[0-9a-f]{64}', final_sha):
        return {'status': 'rejected', 'reason_code': 'FINAL_ARTIFACT_IDENTITY_MISSING'}
    if not (verdict.get('ctx') == 'delivery' and verdict.get('result') == 'pass' and run_id and (str(verdict.get('artifact') or '') == str(case_artifact or '')) and (str(verdict.get('volume_artifact_sha256') or '').lower() == final_sha)):
        return {'status': 'rejected', 'reason_code': 'DELIVERY_VERDICT_IDENTITY_INVALID'}
    try:
        case_sha = hashlib.sha256(case_path.read_bytes()).hexdigest()
    except OSError:
        return {'status': 'rejected', 'reason_code': 'CASE_ARTIFACT_UNAVAILABLE'}
    material = {'schema': LEGACY_DELIVERY_CREDENTIAL_SCHEMA, 'autoid': identity, 'case_artifact': str(case_artifact or ''), 'case_artifact_sha256': case_sha, 'provenance_sha256': hashlib.sha256(provenance_bytes).hexdigest(), 'emit_snapshot_provisional': provisional is True, 'final_artifact_sha256': final_sha, 'delivery_run_id': run_id, 'verdict': 'pass'}
    credential_id = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    credential = {**material, 'credential_id': credential_id}
    try:
        path = mutation_credential_path(f'{identity}.legacy-delivery', credential_root)
        _write_json_atomic(path, credential)
        observed = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'status': 'rejected', 'reason_code': 'LEGACY_DELIVERY_CREDENTIAL_WRITE_FAILED', 'error_type': type(exc).__name__}
    if observed != credential:
        return {'status': 'rejected', 'reason_code': 'LEGACY_DELIVERY_CREDENTIAL_READBACK_MISMATCH'}
    return {'status': 'issued', 'schema': LEGACY_DELIVERY_CREDENTIAL_SCHEMA, 'credential_id': credential_id, 'case_artifact_sha256': case_sha, 'final_artifact_sha256': final_sha, 'delivery_run_id': run_id}

def finalize_mutation_run(case_dir: Path, *, artifact_sha256: str, run_id: str, verdict: str, credential_root: Path | None=None, execution_build: str | None=None, allow_compiler_issued_full_exempt: bool=False) -> dict[str, Any]:
    receipt_path = case_dir / 'case.mutation.json'
    provenance_path = case_dir / 'case.provenance.json'
    try:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        return {'status': 'receipt_unavailable', 'reason_code': 'mutation_receipt_missing', 'error_type': type(exc).__name__}
    except json.JSONDecodeError as exc:
        return {'status': 'receipt_invalid', 'reason_code': 'mutation_receipt_invalid_json', 'error_type': type(exc).__name__, 'line': exc.lineno, 'column': exc.colno}
    except UnicodeError as exc:
        return {'status': 'receipt_invalid', 'reason_code': 'mutation_receipt_invalid_encoding', 'error_type': type(exc).__name__}
    except (ValueError, RecursionError) as exc:
        return {'status': 'receipt_invalid', 'reason_code': 'mutation_receipt_structure_unreadable', 'error_type': type(exc).__name__}
    except OSError as exc:
        return {'status': 'receipt_unavailable', 'reason_code': 'mutation_receipt_unreadable', 'error_type': type(exc).__name__}
    if not isinstance(receipt, dict):
        return {'status': 'receipt_invalid', 'reason_code': 'mutation_receipt_not_object'}
    if receipt.get('schema') != MUTATION_SCHEMA:
        return {'status': 'receipt_invalid', 'reason_code': 'mutation_receipt_schema_invalid'}
    if receipt.get('xlsx_sha256') != artifact_sha256:
        return {'status': 'identity_mismatch', 'reason_code': 'mutation_receipt_artifact_mismatch'}
    if execution_build is not None:
        build_mismatch = receipt_build_mismatch(receipt, execution_build)
        if build_mismatch:
            revoked = True
            revocation_failure: dict[str, str] | None = None
            autoid_value = str(receipt.get('autoid') or '').strip()
            if credential_root is not None and autoid_value:
                try:
                    clear_mutation_credential(autoid_value, credential_root)
                except Exception as exc:
                    revoked = False
                    revoke_error = f'{type(exc).__name__}: {exc}'
                    revocation_failure = {'error_type': type(exc).__name__, 'message': str(exc)}
            result = {'status': 'rejected', 'reason_code': 'build_mismatch_at_run', 'detail': build_mismatch}
            if not revoked:
                result['credential_revoke_failed'] = revoke_error
                result['revocation_failure'] = revocation_failure
            return result
    if verdict != 'pass':
        return {'status': 'unknown', 'reason_code': 'run_verdict_not_pass'}
    requirements = receipt.get('requirements')
    if not isinstance(requirements, list) or not requirements or any((not isinstance(item, dict) for item in requirements)):
        return {'status': 'receipt_invalid', 'reason_code': 'mutation_receipt_requirements_invalid'}
    pending = [item for item in requirements if isinstance(item, dict) and item.get('status') == 'pending']
    if not pending:
        statuses = {str(item.get('status') or '') for item in receipt.get('requirements') or [] if isinstance(item, dict)}
        ready = mutation_receipt_pass_ready if allow_compiler_issued_full_exempt else mutation_receipt_ready
        if ready(receipt, artifact_sha256, execution_build=execution_build):
            return {'status': 'flipped' if 'flipped' in statuses else 'exempt'}
        result = {'status': 'unknown', 'reason_code': receipt_not_ready_reason(receipt, artifact_sha256, execution_build=execution_build, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt)}
        codes = exempt_governance_block_codes(receipt, allow_compiler_issued_full_exempt=allow_compiler_issued_full_exempt)
        if len(codes) > 1 and result['reason_code'] == codes[0]:
            result['reason_codes'] = list(codes)
        return result
    if not str(run_id or '').strip():
        return {'status': 'unknown', 'reason_code': 'run_identity_missing'}
    try:
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    except Exception:
        return {'status': 'provenance_unreadable', 'reason_code': 'mutation_provenance_unreadable'}
    replacements: dict[str, str] = {}
    for item in pending:
        final_ref = _evidence_ref('run', {'autoid': receipt.get('autoid'), 'artifact_sha256': artifact_sha256, 'run_id': run_id, 'assertion_ordinal': item.get('assertion_ordinal')})
        replacements[str(item.get('evidence_ref') or '')] = final_ref
        item['status'] = 'flipped'
        item['evidence_ref'] = final_ref
        item['run_receipt'] = {'run_id': run_id, 'artifact_sha256': artifact_sha256}
    for step in provenance.get('steps') or []:
        assertion = step.get('assertion_type') if isinstance(step, dict) else None
        flip = assertion.get('flip') if isinstance(assertion, dict) else None
        old_ref = str(flip.get('evidence_ref') or '') if isinstance(flip, dict) else ''
        if old_ref in replacements:
            flip['evidence_ref'] = replacements[old_ref]
    _write_json_atomic(provenance_path, provenance)
    _write_json_atomic(receipt_path, receipt)
    if credential_root is not None:
        publish_mutation_credential(receipt, credential_root)
    return {'status': 'flipped', 'finalized': len(pending), 'run_id': run_id}

def build_mutation_pass_audit_fact(case_dir: Path, *, autoid: str, final_artifact_sha256: str) -> dict[str, Any]:
    identity = str(autoid or '').strip()
    final_sha = str(final_artifact_sha256 or '').strip().lower()
    base: dict[str, Any] = {'ev': 'pass_audit', 'aid': identity, 'schema': PASS_AUDIT_SCHEMA, 'artifact': 'case.xlsx', 'artifact_sha256': final_sha, 'audit_basis': 'mutation_flip', 'status': 'unavailable', 'outcome': 'unknown', 'total_assertions': None, 'flipped_assertions': None, 'exempt_assertions': None, 'compiler_issued_exempt_assertions': None, 'author_declared_exempt_assertions': None, 'pending_assertions': None}
    receipt_path = case_dir / 'case.mutation.json'
    case_path = case_dir / 'case.xlsx'
    case_sha = ''
    try:
        case_sha = hashlib.sha256(case_path.read_bytes()).hexdigest()
    except OSError:
        pass
    base['case_artifact_sha256'] = case_sha
    try:
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes.decode('utf-8'))
    except (OSError, ValueError, RecursionError) as exc:
        base['reason_code'] = 'MUTATION_RECEIPT_UNAVAILABLE'
        base['read_error'] = {'error_type': type(exc).__name__}
        if isinstance(exc, json.JSONDecodeError):
            base['read_error'].update(line=exc.lineno, column=exc.colno)
        material = {'aid': identity, 'final_artifact_sha256': final_sha, 'case_artifact_sha256': case_sha, 'reason_code': base['reason_code'], 'read_error': base['read_error']}
    else:
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        base['mutation_receipt_sha256'] = receipt_sha
        base['case_artifact_sha256'] = case_sha
        requirements = receipt.get('requirements') if isinstance(receipt, dict) else None
        rows = [item for item in requirements if isinstance(item, dict)] if isinstance(requirements, list) else []
        statuses = [str(item.get('status') or '') for item in rows]
        _, _, _, issued, discretionary, _ = _governance_counts(rows)
        counts = {'total_assertions': len(rows), 'flipped_assertions': statuses.count('flipped'), 'exempt_assertions': statuses.count('exempt'), 'compiler_issued_exempt_assertions': issued, 'author_declared_exempt_assertions': discretionary - issued, 'pending_assertions': sum((status not in {'flipped', 'exempt'} for status in statuses))}
        if not re.fullmatch('[0-9a-f]{64}', final_sha):
            base['reason_code'] = 'FINAL_ARTIFACT_IDENTITY_MISSING'
        elif not isinstance(receipt, dict) or receipt.get('schema') != MUTATION_SCHEMA:
            base['reason_code'] = 'MUTATION_RECEIPT_SCHEMA_INVALID'
        elif str(receipt.get('autoid') or '') != identity:
            base['reason_code'] = 'MUTATION_RECEIPT_AUTOID_MISMATCH'
        elif not case_sha or receipt.get('xlsx_sha256') != case_sha:
            base['reason_code'] = 'MUTATION_RECEIPT_ARTIFACT_MISMATCH'
        elif not rows or len(rows) != len(requirements):
            base['reason_code'] = 'MUTATION_REQUIREMENTS_INVALID'
        else:
            base.update(counts)
            if base['exempt_assertions'] and (not _exempt_governance_ready(receipt)):
                base['status'] = 'incomplete'
                base['reason_code'] = 'MUTATION_EXEMPT_GOVERNANCE_INVALID'
            elif not mutation_receipt_ready(receipt, case_sha):
                base['status'] = 'incomplete'
                base['reason_code'] = 'MUTATION_FLIP_INCOMPLETE'
            elif base['exempt_assertions']:
                base['status'] = 'incomplete'
                base['reason_code'] = 'MUTATION_EXEMPT_PRESENT'
            else:
                base['status'] = 'complete'
                base['outcome'] = 'clean'
        material = {'aid': identity, 'final_artifact_sha256': final_sha, 'case_artifact_sha256': case_sha, 'mutation_receipt_sha256': receipt_sha, 'status': base['status'], 'reason_code': base.get('reason_code', '')}
    base['audit_revision'] = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:24]
    return base
