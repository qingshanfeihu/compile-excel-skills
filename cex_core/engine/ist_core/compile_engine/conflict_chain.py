# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/conflict_chain.py（sha256 fe878da64fb96cdb）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence
from cex_core.engine.common.schema_identity import accepts_schema

class SpecValue(str, Enum):
    FOUND = 'found'
    ABSENT = 'absent'
    UNKNOWN = 'unknown'

@dataclass(frozen=True)
class SpecEvaluation:
    value: SpecValue
    source: str
    reason: str
    ticket_consulted: bool
    retryable: bool
_OPENKM_FOUND = frozenset({'bound'})
_OPENKM_ABSENT = frozenset({'no_governing_spec'})
_SPEC_AMBIGUOUS = frozenset({'ambiguous'})
_SPEC_UNKNOWN = frozenset({'unavailable', 'invalid_source'})
_TICKET_FOUND = frozenset({'resolved'})
_TICKET_ABSENT = frozenset({'candidate_only', 'missing', 'no_ticket_reference', 'resolved_absent'})

def _status(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ''

def evaluate_spec(openkm_status: object, ticket_status: object=None, *, ticket_eligible: object=None) -> SpecEvaluation:
    openkm = _status(openkm_status)
    if openkm in _OPENKM_FOUND:
        return SpecEvaluation(SpecValue.FOUND, 'openkm', 'openkm_found', False, False)
    if openkm in _SPEC_AMBIGUOUS:
        return SpecEvaluation(SpecValue.ABSENT, 'openkm', 'openkm_ambiguous', False, False)
    if openkm in _SPEC_UNKNOWN or openkm not in _OPENKM_ABSENT:
        return SpecEvaluation(SpecValue.UNKNOWN, 'openkm', 'openkm_unresolved', False, True)
    ticket = _status(ticket_status)
    if ticket in _TICKET_FOUND:
        if ticket_eligible is True:
            return SpecEvaluation(SpecValue.FOUND, 'ticket', 'ticket_found', True, False)
        return SpecEvaluation(SpecValue.UNKNOWN, 'ticket', 'ticket_found_not_eligible', True, True)
    if ticket in _SPEC_AMBIGUOUS:
        return SpecEvaluation(SpecValue.ABSENT, 'ticket', 'ticket_ambiguous', True, False)
    if ticket in _TICKET_ABSENT:
        return SpecEvaluation(SpecValue.ABSENT, 'ticket', 'ticket_absent', True, False)
    return SpecEvaluation(SpecValue.UNKNOWN, 'ticket', 'ticket_unresolved', True, True)

def spec_absent(governing_status: object) -> bool:
    return _status(governing_status) in _OPENKM_ABSENT | _SPEC_AMBIGUOUS

class CompletenessOutcome(str, Enum):
    COMPARE = 'compare'
    SCENARIO_1 = 'scenario_1'
    CONTINUE_CASE = 'continue_case'
    SCENARIO_2 = 'scenario_2'
    WAIT_SPEC_RETRY = 'wait_spec_retry'
    HOLD_INVALID_INPUT = 'hold_invalid_input'

def classify_completeness(spec_value: SpecValue | str, case_complete: object) -> CompletenessOutcome:
    try:
        spec = SpecValue(spec_value)
    except (TypeError, ValueError):
        return CompletenessOutcome.HOLD_INVALID_INPUT
    if type(case_complete) is not bool:
        return CompletenessOutcome.HOLD_INVALID_INPUT
    if spec is SpecValue.UNKNOWN:
        return CompletenessOutcome.WAIT_SPEC_RETRY
    if spec is SpecValue.FOUND:
        return CompletenessOutcome.COMPARE if case_complete else CompletenessOutcome.SCENARIO_1
    return CompletenessOutcome.CONTINUE_CASE if case_complete else CompletenessOutcome.SCENARIO_2

class Scenario3Decision(str, Enum):
    USE_X = 'xml_replace_command'
    KEEP_CASE_BLOCKED = 'xml_keep_case_blocked'
    ABANDON = 'abandon_generation'

class Scenario4Option(str, Enum):
    USE_X_EXPECTATION = 'use_xml_expectation'
    USE_CASE_EXPECTATION = 'use_case_expectation'
    ABANDON = 'abandon_generation'
_SCENARIO4_OPTIONS = (Scenario4Option.USE_X_EXPECTATION, Scenario4Option.USE_CASE_EXPECTATION, Scenario4Option.ABANDON)
_SCENARIO4_OPTIONS_AFTER_X = (Scenario4Option.USE_X_EXPECTATION, Scenario4Option.ABANDON)

@dataclass(frozen=True)
class Scenario4Plan:
    valid: bool
    options: tuple[Scenario4Option, ...]
    basis_command: str | None
    reason: str

def scenario4_plan(*, original_command: object, rewritten_command: object=None, scenario3_decision: Scenario3Decision | str | None=None) -> Scenario4Plan:
    original = original_command.strip() if isinstance(original_command, str) else ''
    rewritten = rewritten_command.strip() if isinstance(rewritten_command, str) else ''
    if scenario3_decision is None:
        if not original:
            return Scenario4Plan(False, (), None, 'original_command_missing')
        return Scenario4Plan(True, _SCENARIO4_OPTIONS, original, 'original_command')
    try:
        decision = Scenario3Decision(scenario3_decision)
    except (TypeError, ValueError):
        return Scenario4Plan(False, (), None, 'scenario3_decision_unknown')
    if decision is Scenario3Decision.USE_X:
        if not rewritten:
            return Scenario4Plan(False, (), None, 'rewritten_command_missing')
        return Scenario4Plan(True, _SCENARIO4_OPTIONS_AFTER_X, rewritten, 'rewritten_command')
    return Scenario4Plan(True, (), None, 'scenario3_terminal')

class DeltaAction(str, Enum):
    CONTINUE = 'continue'
    TERMINATE = 'terminate'
    ABANDON = 'abandon'
_ACTION_STRICTNESS = {DeltaAction.CONTINUE: 0, DeltaAction.TERMINATE: 1, DeltaAction.ABANDON: 2}

@dataclass(frozen=True)
class DeltaDecision:
    delta_id: str
    action: DeltaAction

@dataclass(frozen=True)
class DeltaReduction:
    valid: bool
    action: DeltaAction
    reason: str
    expected_count: int
    decided_count: int

@dataclass(frozen=True)
class DeltaFrontierReduction:
    valid: bool
    original_delta_ids: tuple[str, ...]
    effective_delta_ids: tuple[str, ...]
    pruned_delta_ids: tuple[str, ...]
    reduction: DeltaReduction
    reason: str

def _invalid_delta_reduction(reason: str, *, expected_count: int=0, decided_count: int=0) -> DeltaReduction:
    return DeltaReduction(False, DeltaAction.TERMINATE, reason, expected_count, decided_count)

def _parse_delta_decision(value: object) -> DeltaDecision | None:
    if isinstance(value, DeltaDecision):
        delta_id = value.delta_id
        action = value.action
    elif isinstance(value, Mapping):
        delta_id = value.get('delta_id')
        action = value.get('action')
    else:
        return None
    if not isinstance(delta_id, str) or not delta_id.strip():
        return None
    try:
        parsed_action = DeltaAction(action)
    except (TypeError, ValueError):
        return None
    return DeltaDecision(delta_id.strip(), parsed_action)

def reduce_delta_decisions(expected_delta_ids: object, decisions: object) -> DeltaReduction:
    if not isinstance(expected_delta_ids, Sequence) or isinstance(expected_delta_ids, (str, bytes, bytearray)):
        return _invalid_delta_reduction('expected_delta_ids_invalid')
    expected: list[str] = []
    for raw in expected_delta_ids:
        if not isinstance(raw, str) or not raw.strip():
            return _invalid_delta_reduction('expected_delta_id_invalid')
        expected.append(raw.strip())
    expected_count = len(expected)
    if len(set(expected)) != expected_count:
        return _invalid_delta_reduction('expected_delta_id_duplicate', expected_count=expected_count)
    if not isinstance(decisions, Sequence) or isinstance(decisions, (str, bytes, bytearray)):
        return _invalid_delta_reduction('decisions_invalid', expected_count=expected_count)
    parsed: list[DeltaDecision] = []
    for raw in decisions:
        item = _parse_delta_decision(raw)
        if item is None:
            return _invalid_delta_reduction('decision_invalid', expected_count=expected_count, decided_count=len(parsed))
        parsed.append(item)
    decided_count = len(parsed)
    decision_ids = [item.delta_id for item in parsed]
    if len(set(decision_ids)) != decided_count:
        return _invalid_delta_reduction('decision_delta_id_duplicate', expected_count=expected_count, decided_count=decided_count)
    expected_set = set(expected)
    decision_set = set(decision_ids)
    if not decision_set.issubset(expected_set):
        return _invalid_delta_reduction('decision_delta_id_unknown', expected_count=expected_count, decided_count=decided_count)
    if decision_set != expected_set:
        return _invalid_delta_reduction('decision_missing', expected_count=expected_count, decided_count=decided_count)
    action = max((item.action for item in parsed), key=_ACTION_STRICTNESS.__getitem__, default=DeltaAction.CONTINUE)
    return DeltaReduction(True, action, 'complete', expected_count, decided_count)
CONFLICT_CHAIN_SCHEMA = 'ist.delta.conflict-chain'
CONFLICT_DECISION_SCHEMA = 'ist.delta.conflict-decision'
BATCH_CONFLICT_DECISION_SCHEMA = 'ist.delta.batch-conflict-decision'
BATCH_NEED_BINDING_MIGRATION_SCHEMA = 'ist.delta.needs-decision-binding-migration'
BATCH_USE_CASE = 'batch_use_case'
BATCH_USE_XML = 'batch_use_xml'
BATCH_ABANDON = 'batch_abandon'
BATCH_CONFLICT_TOKENS = frozenset({BATCH_USE_CASE, BATCH_USE_XML, BATCH_ABANDON})
BATCH_BINDING_FIELDS = ('case_manifest_sha256', 'capability_projection_sha256', 'governing_spec_sha256')
_SHA256_RE = re.compile('[0-9a-f]{64}')
_LEGACY_SCENARIO_BY_CLAIM_KIND = {'spec_case_conflict': 'scenario_1', 'scenario2_incomplete_case': 'scenario_2', 'xml_command_shape_conflict': 'scenario_3', 'xml_expectation_conflict': 'scenario_4'}
_CONFLICT_SCENARIOS = frozenset({'scenario_1', 'scenario_2', 'scenario_3', 'scenario_4', 'spec_unknown'})

def claim_conflict_scenario(claim: object) -> str:
    if not isinstance(claim, Mapping):
        return ''
    explicit = str(claim.get('conflict_scenario') or '').strip()
    if explicit:
        return explicit if explicit in _CONFLICT_SCENARIOS else ''
    return _LEGACY_SCENARIO_BY_CLAIM_KIND.get(str(claim.get('claim_kind') or '').strip(), '')

def claim_delta_id(claim: object) -> str:
    if not isinstance(claim, Mapping):
        return ''
    explicit = str(claim.get('delta_id') or '').strip()
    if explicit:
        return explicit
    payload = {str(key): value for key, value in claim.items() if str(key) not in {'decision_binding'}}
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError):
        return ''
    return hashlib.sha256(encoded).hexdigest()

def conflict_token_action(token: object) -> DeltaAction | None:
    value = str(token or '').strip()
    if value in {'xml_replace_command', 'use_xml_expectation', 'use_case_expectation'}:
        return DeltaAction.CONTINUE
    if value == 'xml_keep_case_blocked':
        return DeltaAction.TERMINATE
    if value == 'abandon_generation':
        return DeltaAction.ABANDON
    return None

def reduce_delta_frontier(claims: object, decisions: object) -> DeltaFrontierReduction:
    invalid = _invalid_delta_reduction('delta_frontier_invalid')
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)) or (not claims) or (not isinstance(decisions, Sequence)) or isinstance(decisions, (str, bytes, bytearray)):
        return DeltaFrontierReduction(False, (), (), (), invalid, 'frontier_input_invalid')
    original: list[str] = []
    scenarios: dict[str, str] = {}
    for claim in claims:
        scenario = claim_conflict_scenario(claim)
        delta_id = claim_delta_id(claim)
        if scenario not in {'scenario_3', 'scenario_4'} or not delta_id:
            return DeltaFrontierReduction(False, tuple(original), (), (), invalid, 'frontier_claim_invalid')
        if delta_id in scenarios:
            return DeltaFrontierReduction(False, tuple(original), (), (), invalid, 'frontier_delta_duplicate')
        original.append(delta_id)
        scenarios[delta_id] = scenario
    parsed: list[DeltaDecision] = []
    for raw in decisions:
        item = _parse_delta_decision(raw)
        if item is None:
            return DeltaFrontierReduction(False, tuple(original), (), (), _invalid_delta_reduction('decision_invalid', expected_count=len(original), decided_count=len(parsed)), 'frontier_decision_invalid')
        parsed.append(item)
    decision_ids = [item.delta_id for item in parsed]
    if len(set(decision_ids)) != len(decision_ids):
        return DeltaFrontierReduction(False, tuple(original), (), (), invalid, 'frontier_decision_duplicate')
    if any((delta_id not in scenarios for delta_id in decision_ids)):
        return DeltaFrontierReduction(False, tuple(original), (), (), invalid, 'frontier_decision_unknown')
    s3_ids = [delta_id for delta_id in original if scenarios[delta_id] == 'scenario_3']
    s4_ids = [delta_id for delta_id in original if scenarios[delta_id] == 'scenario_4']
    rows_by_id = {item.delta_id: item for item in parsed}
    if s3_ids:
        s3_rows = [rows_by_id[delta_id] for delta_id in s3_ids if delta_id in rows_by_id]
        s3_reduction = reduce_delta_decisions(s3_ids, s3_rows)
        if not s3_reduction.valid:
            return DeltaFrontierReduction(False, tuple(original), tuple(s3_ids), (), s3_reduction, 'scenario3_incomplete')
        if s3_reduction.action is not DeltaAction.CONTINUE:
            if any((delta_id in rows_by_id for delta_id in s4_ids)):
                return DeltaFrontierReduction(False, tuple(original), tuple(s3_ids), tuple(s4_ids), s3_reduction, 'scenario4_decision_after_scenario3_terminal')
            return DeltaFrontierReduction(True, tuple(original), tuple(s3_ids), tuple(s4_ids), s3_reduction, 'scenario4_pruned')
    reduction = reduce_delta_decisions(original, parsed)
    return DeltaFrontierReduction(reduction.valid, tuple(original), tuple(original), (), reduction, 'complete' if reduction.valid else reduction.reason)

def _reject_non_json_numbers(value: object) -> None:
    if isinstance(value, float) and (not math.isfinite(value)):
        raise ValueError('conflict chain payload contains a non-finite number')
    if isinstance(value, Mapping):
        if any((not isinstance(key, str) for key in value)):
            raise TypeError('conflict chain payload keys must be strings')
        for nested in value.values():
            _reject_non_json_numbers(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_non_json_numbers(nested)

def conflict_chain_id(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise TypeError('conflict chain payload must be a mapping')
    _reject_non_json_numbers(payload)
    envelope = {'schema': CONFLICT_CHAIN_SCHEMA, 'payload': payload}
    try:
        encoded = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise TypeError('conflict chain payload must be JSON serializable') from exc
    return hashlib.sha256(encoded).hexdigest()

def decision_is_current(decision: object, current_chain_id: object, *, expected_delta_id: str | None=None) -> bool:
    if not isinstance(decision, Mapping):
        return False
    if not isinstance(current_chain_id, str) or not _SHA256_RE.fullmatch(current_chain_id):
        return False
    if decision.get('schema') != CONFLICT_DECISION_SCHEMA:
        return False
    if decision.get('conflict_chain_id') != current_chain_id:
        return False
    delta_id = decision.get('delta_id')
    token = decision.get('token')
    if not isinstance(delta_id, str) or not delta_id.strip():
        return False
    if not isinstance(token, str) or not token.strip():
        return False
    if expected_delta_id is not None and delta_id != expected_delta_id:
        return False
    return decision.get('superseded') is not True

def scenario1_claims_reviewable(claims: object) -> bool:
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)) or (not claims):
        return False
    for claim in claims:
        if not isinstance(claim, Mapping):
            return False
        if not accepts_schema(claim.get('schema'), 'ist.delta.conflict-claim') or claim.get('conflict_scenario') != 'scenario_1' or (not _SHA256_RE.fullmatch(str(claim.get('conflict_chain_id') or ''))) or (claim.get('options') != ['abandon_generation']):
            return False
        reason = str(claim.get('reason_code') or claim.get('claim_kind') or '')
        if reason == 'scenario1_spec_case_conflict':
            if any((not isinstance(claim.get(field), str) or not str(claim.get(field)).strip() for field in ('spec_quote', 'case_quote', 'spec_locator', 'case_locator', 'incompatibility'))):
                return False
            continue
        if reason == 'scenario1_case_incomplete':
            missing = claim.get('missing_fields')
            if not isinstance(missing, list) or not missing or any((field not in {'description', 'steps', 'expectation'} for field in missing)):
                return False
            continue
        return False
    return True
DIRECT_ABANDON_REASON_PREFIX = 'direct:scenario12_abandon:'

def is_direct_abandon_decision(fact: object) -> bool:
    if not isinstance(fact, Mapping) or fact.get('ev') != 'decision':
        return False
    if str(fact.get('answer') or '').strip():
        return False
    return str(fact.get('reason') or '').startswith(DIRECT_ABANDON_REASON_PREFIX)

def need_accepts_direct_abandon(need: object, scenario: object) -> bool:
    if not isinstance(need, Mapping):
        return False
    if scenario not in ('scenario_1', 'scenario_2'):
        return False
    if str(need.get('conflict_scenario') or '') != scenario:
        return False
    return 'expected_delta_ids' not in need and need.get('auxiliary_claims') is None

def capability_xml_claim_reviewable(claim: object) -> bool:
    if not isinstance(claim, Mapping):
        return False
    if claim.get('source_kind') != 'CapabilityXml':
        return False
    scenario = str(claim.get('conflict_scenario') or '')
    if scenario not in {'scenario_3', 'scenario_4'}:
        return False
    generation = claim.get('capability_generation')
    if not isinstance(generation, Mapping):
        return False
    if any((not isinstance(generation.get(field), str) or not str(generation.get(field)).strip() for field in ('version', 'build', 'source_filename'))):
        return False
    if not _SHA256_RE.fullmatch(str(generation.get('source_sha256') or '').lower()):
        return False
    return claim.get('xml_present') is True and isinstance(claim.get('xml_locator'), str) and bool(str(claim.get('xml_locator') or '').strip())

def capability_xml_expected_signable(claim: object) -> bool:
    if not capability_xml_claim_reviewable(claim) or not isinstance(claim, Mapping) or claim_conflict_scenario(claim) != 'scenario_4':
        return False
    assertions = claim.get('xml_assertions')
    if not isinstance(assertions, list) or not assertions:
        return False
    try:
        from cex_core.engine.case_compiler.case_ir import VALID_CHECK_METHODS
    except Exception:
        return False
    for assertion in assertions:
        if not isinstance(assertion, Mapping):
            return False
        if set(assertion) != {'operator', 'value', 'locator'}:
            return False
        operator = str(assertion.get('operator') or '').strip()
        value = assertion.get('value')
        locator = str(assertion.get('locator') or '').strip()
        if operator not in VALID_CHECK_METHODS or operator == 'found_times' or (not isinstance(value, str)) or (not value) or (not locator):
            return False
    return True

def config_binding_claim_reviewable(claim: object) -> bool:
    if not isinstance(claim, Mapping) or claim.get('source_kind') != 'ConfigBinding' or claim_conflict_scenario(claim) != 'scenario_4' or (not _SHA256_RE.fullmatch(str(claim.get('config_binding_receipt_sha256') or ''))) or (not isinstance(claim.get('config_binding_receipt'), Mapping)):
        return False
    try:
        from cex_core.engine.ist_core.compile_engine.authority_reconcile import ExpectedClaimReceipt, expected_source_group
        receipt = ExpectedClaimReceipt.from_dict(dict(claim['config_binding_receipt']))
    except (TypeError, ValueError):
        return False
    groups = {expected_source_group(item.source_kind) for item in receipt.claims}
    return bool(receipt.receipt_sha256 == claim.get('config_binding_receipt_sha256') and 'configbinding' in groups and (len(groups - {'configbinding'}) >= 1))

def batch_conflict_claim_reviewable(claim: object) -> bool:
    if isinstance(claim, Mapping) and claim.get('source_kind') == 'ConfigBinding':
        return config_binding_claim_reviewable(claim)
    scenario = claim_conflict_scenario(claim)
    if scenario == 'scenario_3':
        return capability_xml_claim_reviewable(claim)
    if scenario == 'scenario_4':
        return capability_xml_expected_signable(claim)
    return False

def batch_conflict_decision_is_current(decision: object, bindings: object, *, conflict_claim_ids: object, auto_case_claim_ids: object=(), conflict_autoids: object, batch_member_autoids: object) -> bool:
    if not isinstance(decision, Mapping) or not isinstance(bindings, Mapping):
        return False
    if decision.get('schema') != BATCH_CONFLICT_DECISION_SCHEMA:
        return False
    if str(decision.get('decision') or '') not in BATCH_CONFLICT_TOKENS:
        return False
    signer = decision.get('signer')
    from cex_core.engine.ist_core.tools.ask_user import hil_identity_digest_is_current
    if not isinstance(signer, Mapping) or signer.get('kind') != 'ask_user' or (not str(signer.get('question_id') or '')) or (not _SHA256_RE.fullmatch(str(signer.get('question_digest') or ''))) or (not hil_identity_digest_is_current(signer.get('hil_identity_sha256'))):
        return False
    for field in BATCH_BINDING_FIELDS:
        current = str(bindings.get(field) or '').lower()
        if not _SHA256_RE.fullmatch(current) or decision.get(field) != current:
            return False

    def _closed_list(value: object) -> list[str] | None:
        if not isinstance(value, (list, tuple)):
            return None
        items = [str(item) for item in value]
        if any((not item for item in items)) or items != sorted(items) or len(set(items)) != len(items):
            return None
        return items
    expected = {'conflict_claim_ids': _closed_list(conflict_claim_ids), 'auto_case_claim_ids': _closed_list(auto_case_claim_ids), 'conflict_autoids': _closed_list(conflict_autoids), 'batch_member_autoids': _closed_list(batch_member_autoids)}
    if any((value is None for value in expected.values())):
        return False
    if not expected['conflict_claim_ids'] or not expected['conflict_autoids']:
        return False
    return all((decision.get(field) == value for field, value in expected.items()))

def batch_auto_case_decision_resolves(need: object, decision: object) -> bool:
    if not isinstance(need, Mapping) or not isinstance(decision, Mapping):
        return False
    if not accepts_schema(decision.get('schema'), 'ist.delta.batch-conflict-auto-resolution'):
        return False
    if decision.get('token') != BATCH_USE_CASE or decision.get('answer') != BATCH_USE_CASE or decision.get('conflict_scenario') != 'scenario_4':
        return False
    ids = decision.get('auto_case_claim_ids')
    if not isinstance(ids, list) or not ids or ids != sorted(ids) or (len(set(ids)) != len(ids)) or any((_SHA256_RE.fullmatch(str(value or '')) is None for value in ids)):
        return False
    need_ids = need.get('batch_auto_case_claim_ids')
    if not isinstance(need_ids, list) or need_ids != sorted(need_ids) or len(set(need_ids)) != len(need_ids) or (ids != need_ids) or bool(need.get('batch_conflict_claim_ids')):
        return False
    for field in BATCH_BINDING_FIELDS:
        if _SHA256_RE.fullmatch(str(need.get(field) or '')) is None or decision.get(field) != need.get(field):
            return False
    members = need.get('batch_member_autoids')
    if not isinstance(members, list) or members != sorted(members) or len(members) != len(set(members)) or (decision.get('batch_member_autoids') != members) or (str(need.get('aid') or '') not in members):
        return False
    auxiliary = need.get('auxiliary_claims')
    if not isinstance(auxiliary, list) or not auxiliary:
        return not decision.get('auxiliary_decisions')
    expected = sorted({str(claim.get('conflict_chain_id') or '') for claim in auxiliary if isinstance(claim, Mapping) and accepts_schema(claim.get('schema'), 'ist.delta.conflict-claim') and (claim.get('conflict_scenario') == 'spec_unknown')})
    rows = decision.get('auxiliary_decisions')
    if not expected or not isinstance(rows, list):
        return False
    actual = [str(row.get('conflict_chain_id') or '') for row in rows if isinstance(row, Mapping) and accepts_schema(row.get('schema'), 'ist.delta.auxiliary-decision') and (row.get('conflict_scenario') == 'spec_unknown') and (row.get('token') in {'retry_spec_lookup', 'continue_without_spec'})]
    return len(actual) == len(rows) and sorted(actual) == expected and (len(actual) == len(set(actual)))

def batch_conflict_decision_resolves_need(need: object, decision: object) -> bool:
    if not isinstance(need, Mapping) or not isinstance(decision, Mapping):
        return False
    if decision.get('schema') != BATCH_CONFLICT_DECISION_SCHEMA:
        return False
    token = str(decision.get('decision') or decision.get('token') or '')
    if token not in BATCH_CONFLICT_TOKENS:
        return False
    for field in BATCH_BINDING_FIELDS:
        current = str(need.get(field) or '').lower()
        if not _SHA256_RE.fullmatch(current) or decision.get(field) != current:
            return False

    def _closed(value: object, *, sha: bool=False) -> list[str] | None:
        if not isinstance(value, list):
            return None
        items = [str(item) for item in value]
        if any((not item for item in items)) or items != sorted(items) or len(items) != len(set(items)) or (sha and any((_SHA256_RE.fullmatch(item) is None for item in items))):
            return None
        return items
    need_conflicts = _closed(need.get('batch_conflict_claim_ids'), sha=True)
    need_auto = _closed(need.get('batch_auto_case_claim_ids', []), sha=True)
    decision_conflicts = _closed(decision.get('conflict_claim_ids'), sha=True)
    decision_auto = _closed(decision.get('auto_case_claim_ids', []), sha=True)
    members = _closed(need.get('batch_member_autoids'))
    decision_members = _closed(decision.get('batch_member_autoids'))
    conflicted = _closed(decision.get('conflict_autoids'))
    aid = str(need.get('aid') or '')
    allows_batch_terminal = token == BATCH_ABANDON and aid in (members or [])
    if not need_conflicts and (not allows_batch_terminal) or need_auto is None or (not decision_conflicts) or (decision_auto is None) or (not members) or (members != decision_members) or (not conflicted) or (aid not in conflicted and (not allows_batch_terminal)) or (not set(need_conflicts) <= set(decision_conflicts)) or (not set(need_auto) <= set(decision_auto)):
        return False
    scoped = _closed(decision.get('scope_claim_ids', need_conflicts), sha=True)
    if scoped != need_conflicts:
        return False
    if allows_batch_terminal:
        return True
    auxiliary = need.get('auxiliary_claims')
    if not isinstance(auxiliary, list) or not auxiliary:
        return not decision.get('auxiliary_decisions')
    expected_chains = sorted({str(claim.get('conflict_chain_id') or '') for claim in auxiliary if isinstance(claim, Mapping) and accepts_schema(claim.get('schema'), 'ist.delta.conflict-claim') and (claim.get('conflict_scenario') == 'spec_unknown')})
    rows = decision.get('auxiliary_decisions')
    if not expected_chains or not isinstance(rows, list):
        return False
    actual_chains: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or not accepts_schema(row.get('schema'), 'ist.delta.auxiliary-decision') or row.get('conflict_scenario') != 'spec_unknown' or (row.get('token') not in {'retry_spec_lookup', 'continue_without_spec'}):
            return False
        actual_chains.append(str(row.get('conflict_chain_id') or ''))
    return sorted(actual_chains) == expected_chains and len(actual_chains) == len(set(actual_chains))

def needs_decision_fact_sha256(need: object) -> str:
    if not isinstance(need, Mapping):
        return ''
    try:
        raw = json.dumps(dict(need), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError):
        return ''
    return hashlib.sha256(raw).hexdigest()

def batch_conflict_binding_migration_resolves_need(need: object, decision: object, migration: object) -> bool:
    if not all((isinstance(value, Mapping) for value in (need, decision, migration))):
        return False
    if migration.get('ev') != 'needs_decision_binding_migrated' or migration.get('schema') != BATCH_NEED_BINDING_MIGRATION_SCHEMA or str(migration.get('aid') or '') != str(need.get('aid') or '') or (str(migration.get('question_id') or '') != str(need.get('question_id') or '')) or (migration.get('needs_decision_sha256') != needs_decision_fact_sha256(need)) or (str(decision.get('scope_autoid') or '') != str(need.get('aid') or '')) or (migration.get('decision') != str(decision.get('decision') or decision.get('token') or '')):
        return False
    receipt_sha = str(migration.get('batch_receipt_sha256') or '')
    if _SHA256_RE.fullmatch(receipt_sha) is None or decision.get('batch_receipt_sha256') != receipt_sha:
        return False
    from_bindings = migration.get('from_bindings')
    to_bindings = migration.get('to_bindings')
    if not isinstance(from_bindings, Mapping) or not isinstance(to_bindings, Mapping):
        return False
    expected_from = {field: str(need.get(field) or '').lower() for field in BATCH_BINDING_FIELDS}
    expected_to = {field: str(decision.get(field) or '').lower() for field in BATCH_BINDING_FIELDS}
    if dict(from_bindings) != expected_from or dict(to_bindings) != expected_to or expected_from == expected_to or any((_SHA256_RE.fullmatch(value) is None for value in expected_from.values())) or any((_SHA256_RE.fullmatch(value) is None for value in expected_to.values())):
        return False
    need_scope = need.get('batch_conflict_claim_ids') or []
    decision_scope = decision.get('scope_claim_ids') or []
    if not isinstance(need_scope, list) or not isinstance(decision_scope, list) or migration.get('scope_claim_ids') != need_scope or (decision_scope != need_scope):
        return False
    rebased_need = {**dict(need), **expected_to}
    return batch_conflict_decision_resolves_need(rebased_need, decision)

class ReentryAction(str, Enum):
    RERUN_CHAIN = 'rerun_chain'
    ABANDON = 'abandon'

@dataclass(frozen=True)
class ReentryReduction:
    valid: bool
    action: ReentryAction
    next_round: int | None
    invalidate_decisions: bool
    reason: str

def reduce_blocked_reentry(*, rounds_used: object, max_rounds: object) -> ReentryReduction:
    if type(rounds_used) is not int or type(max_rounds) is not int or rounds_used < 0 or (max_rounds <= 0):
        return ReentryReduction(False, ReentryAction.ABANDON, None, True, 'round_counter_invalid')
    if rounds_used >= max_rounds:
        return ReentryReduction(True, ReentryAction.ABANDON, None, True, 'round_cap_reached')
    return ReentryReduction(True, ReentryAction.RERUN_CHAIN, rounds_used + 1, True, 'rerun_full_chain')
__all__ = ['BATCH_ABANDON', 'BATCH_BINDING_FIELDS', 'BATCH_CONFLICT_DECISION_SCHEMA', 'BATCH_NEED_BINDING_MIGRATION_SCHEMA', 'BATCH_CONFLICT_TOKENS', 'BATCH_USE_CASE', 'BATCH_USE_XML', 'CONFLICT_CHAIN_SCHEMA', 'CONFLICT_DECISION_SCHEMA', 'CompletenessOutcome', 'DeltaAction', 'DeltaDecision', 'DeltaFrontierReduction', 'DeltaReduction', 'ReentryAction', 'ReentryReduction', 'Scenario3Decision', 'Scenario4Option', 'Scenario4Plan', 'SpecEvaluation', 'SpecValue', 'classify_completeness', 'batch_conflict_claim_reviewable', 'batch_conflict_binding_migration_resolves_need', 'batch_auto_case_decision_resolves', 'batch_conflict_decision_resolves_need', 'batch_conflict_decision_is_current', 'capability_xml_claim_reviewable', 'capability_xml_expected_signable', 'config_binding_claim_reviewable', 'claim_conflict_scenario', 'claim_delta_id', 'conflict_token_action', 'conflict_chain_id', 'decision_is_current', 'scenario1_claims_reviewable', 'evaluate_spec', 'needs_decision_fact_sha256', 'spec_absent', 'reduce_blocked_reentry', 'reduce_delta_decisions', 'reduce_delta_frontier', 'scenario4_plan']
