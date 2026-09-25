# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/execution_failure.py（sha256 1dce0fb245230255）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping
from cex_core.engine.ist_core.security_scrub import scrub_text
from cex_core.engine.ist_core.tools.device.batch_result_protocol import MAX_ERROR_TEXT_CHARS, REASON_CODES
from cex_core.engine.common.schema_identity import accepts_schema
MAX_EXECUTION_ATTEMPTS = 3
NO_PROGRESS_STALL_HITS = 2
NO_DEVICE_REEXECUTION_REASON_CODES = frozenset({'result_channel_unavailable'})
EXECUTION_FAILURE_EVENT = 'execution_failure'
EXECUTION_SUCCESS_EVENT = 'execution_success'
REENTRY_CLEAR_EVENTS = frozenset({'conflict_chain_reentered'})

class FailureCategory(str, Enum):
    ENGINE_REJECTION = 'engine_rejection'
    RUNTIME_INFRASTRUCTURE = 'runtime_infrastructure'
    DEVICE_PREREQUISITE = 'device_prerequisite'
    CONNECTION = 'connection'
    OCCUPANCY = 'occupancy'
    ENVIRONMENT = 'environment'
    UNKNOWN = 'unknown'

class FailureAction(str, Enum):
    RETRY = 'retry'
    BLOCKED = 'blocked'
    IST_CORE_DEFECT = 'ist_core_defect'
    UNABLE_TO_COMPILE = 'unable_to_compile'
BUDGETED_CATEGORIES = frozenset({FailureCategory.ENGINE_REJECTION, FailureCategory.UNKNOWN})
NO_PROGRESS_CATEGORIES = frozenset({FailureCategory.RUNTIME_INFRASTRUCTURE})
PREREQUISITE_CATEGORIES = frozenset({FailureCategory.DEVICE_PREREQUISITE, FailureCategory.CONNECTION})
WAIT_CATEGORIES = frozenset({FailureCategory.OCCUPANCY, FailureCategory.ENVIRONMENT})
if BUDGETED_CATEGORIES | NO_PROGRESS_CATEGORIES | PREREQUISITE_CATEGORIES | WAIT_CATEGORIES != frozenset(FailureCategory):
    raise RuntimeError('execution failure category budget partition is not exhaustive')
_REASON_CODE_CATEGORY: dict[str, FailureCategory] = {'device_busy': FailureCategory.OCCUPANCY, 'env_pool_exhausted': FailureCategory.ENVIRONMENT, 'invalid_request': FailureCategory.ENGINE_REJECTION, 'environment_unavailable': FailureCategory.ENVIRONMENT, 'device_unreachable': FailureCategory.ENVIRONMENT, 'device_prerequisite_unmet': FailureCategory.DEVICE_PREREQUISITE, 'bed_identity_mismatch': FailureCategory.ENGINE_REJECTION, 'artifact_identity_mismatch': FailureCategory.ENGINE_REJECTION, 'delivery_failed': FailureCategory.RUNTIME_INFRASTRUCTURE, 'execution_failed': FailureCategory.UNKNOWN, 'session_desync': FailureCategory.RUNTIME_INFRASTRUCTURE, 'result_channel_unavailable': FailureCategory.RUNTIME_INFRASTRUCTURE, 'producer_protocol_error': FailureCategory.ENGINE_REJECTION}
_FAILURE_REASON_CODES = frozenset(REASON_CODES) - {'completed'}
if frozenset(_REASON_CODE_CATEGORY) != _FAILURE_REASON_CODES:
    raise RuntimeError(f'execution failure reason mapping is not exhaustive: missing={sorted(_FAILURE_REASON_CODES - frozenset(_REASON_CODE_CATEGORY))}, extra={sorted(frozenset(_REASON_CODE_CATEGORY) - _FAILURE_REASON_CODES)}')
_IMPLEMENTATION_SOURCE_PATHS = ('main/ist_core/compile_engine/execution_failure.py', 'main/ist_core/compile_engine/nodes.py', 'main/ist_core/tools/device/batch_result_protocol.py', 'main/ist_core/tools/device/batch_tools.py', 'main/case_compiler/device_mcp_client.py')

class _ImplementationAstNormalizer(ast.NodeTransformer):

    @staticmethod
    def _without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            return body[1:]
        return body

    def visit_Module(self, node: ast.Module) -> ast.AST:
        node.body = self._without_docstring(node.body)
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.body = self._without_docstring(node.body)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.body = self._without_docstring(node.body)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.body = self._without_docstring(node.body)
        return self.generic_visit(node)

def _execution_implementation_material() -> bytes:
    root = _cex_data_path('')
    chunks: list[bytes] = []
    for relative in _IMPLEMENTATION_SOURCE_PATHS:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f'execution implementation source unavailable: {relative}')
        try:
            source = path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise RuntimeError(f'execution implementation source invalid: {relative}') from exc
        normalized = _ImplementationAstNormalizer().visit(tree)
        ast.fix_missing_locations(normalized)
        chunks.extend((relative.encode('utf-8'), b'\x00', ast.dump(normalized, annotate_fields=True, include_attributes=False).encode('utf-8'), b'\x00'))
    return b''.join(chunks)

@lru_cache(maxsize=1)
def current_execution_implementation_sha256() -> str:
    return hashlib.sha256(_execution_implementation_material()).hexdigest()

@dataclass(frozen=True)
class ExecutionIdentity:
    autoid: str
    artifact_sha256: str
    bed_host: str
    build: str
    implementation_sha256: str = field(default_factory=lambda: current_execution_implementation_sha256(), init=False)

    def __post_init__(self) -> None:
        for field_name in ('autoid', 'artifact_sha256', 'bed_host'):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f'execution identity {field_name} must be non-empty text')
        if not isinstance(self.build, str):
            raise ValueError('execution identity build must be text')
        if not isinstance(self.implementation_sha256, str) or len(self.implementation_sha256) != 64 or any((char not in '0123456789abcdef' for char in self.implementation_sha256)):
            raise ValueError('execution identity implementation_sha256 must be lowercase sha256')

@dataclass(frozen=True)
class ExecutionFailureDecision:
    identity: ExecutionIdentity
    reason_code: str
    category: FailureCategory
    attempt: int
    action: FailureAction
    record_failure: bool
    prerequisite_receipt_sha256: str = ''
    fingerprint_hits: int = 0
    no_progress_fingerprint: str = ''
    decision_axis: tuple[str, ...] = ()

    @property
    def exhausted(self) -> bool:
        return self.action is not FailureAction.RETRY

def reason_code_categories() -> dict[str, FailureCategory]:
    return dict(_REASON_CODE_CATEGORY)

def classify_reason_code(reason_code: str):
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue, recognize
    if reason_code == 'completed':
        raise ValueError('completed is not an execution failure reason')
    recognized = recognize('execution_reason_codes', reason_code)
    if isinstance(recognized, UnrecognizedRoutingValue):
        return recognized
    return _REASON_CODE_CATEGORY[recognized]

def _normalize_failure_reason(reason_code: str, prerequisite_receipt_sha256: str) -> tuple[str, str]:
    receipt = str(prerequisite_receipt_sha256 or '')
    receipt_valid = len(receipt) == 64 and all((char in '0123456789abcdef' for char in receipt))
    if reason_code == 'device_prerequisite_unmet':
        if receipt_valid:
            return (reason_code, receipt)
        return ('producer_protocol_error', '')
    if receipt:
        return ('producer_protocol_error', '')
    return (reason_code, '')

def _classify_recorded_failure(fact: Mapping[str, Any]) -> tuple[str, FailureCategory, str]:
    reason_code, receipt_sha256 = _normalize_failure_reason(str(fact.get('reason_code') or ''), str(fact.get('prerequisite_receipt_sha256') or ''))
    try:
        return (reason_code, classify_reason_code(reason_code), receipt_sha256)
    except ValueError:
        from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue
        return (reason_code, UnrecognizedRoutingValue('execution_reason_codes', reason_code), receipt_sha256)

def _recognized_failure_category(reason_code: object):
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue, recognize
    recognized = recognize('execution_reason_codes', reason_code)
    if isinstance(recognized, UnrecognizedRoutingValue):
        return recognized
    return _REASON_CODE_CATEGORY[recognized]

def is_occupancy_reason_code(reason_code: str):
    category = _recognized_failure_category(reason_code)
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue
    if isinstance(category, UnrecognizedRoutingValue):
        return category
    return category is FailureCategory.OCCUPANCY

def is_environment_blocked_reason_code(reason_code: str):
    category = _recognized_failure_category(reason_code)
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue
    if isinstance(category, UnrecognizedRoutingValue):
        return category
    return category is FailureCategory.ENVIRONMENT

def is_runtime_infrastructure_reason_code(reason_code: str):
    category = _recognized_failure_category(reason_code)
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue
    if isinstance(category, UnrecognizedRoutingValue):
        return category
    return category is FailureCategory.RUNTIME_INFRASTRUCTURE

def is_runtime_infrastructure_terminal_fact(fact: Mapping[str, Any]) -> bool:
    return isinstance(fact, Mapping) and str(fact.get('ev') or '') in {'blocked', 'ist_core_defect'} and is_runtime_infrastructure_reason_code(str(fact.get('reason_code') or ''))

def is_runtime_infrastructure_action(action: object):
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue, recognize
    recognized = recognize('failure_action', str(getattr(action, 'value', action) or ''))
    if isinstance(recognized, UnrecognizedRoutingValue):
        return recognized
    return recognized == FailureAction.BLOCKED.value

def is_case_scoped_terminal_action(action: object):
    """上机失败封顶后落在案级终态（ist_core_defect / unable_to_compile）——失败案已由
    归约器结算（隔离/暂挂/终态），其余组成不受连坐。交付模式（09-09 裁决「开发模式
    整批停、交付模式单案隔离」）下图在这类返回后不得直接收口，还有可交付案就回 merge
    （2026-09-11 <batch>：<case> 子集派发被 staging 模块判定拒三次后图
    直收口，11 案 subset_verified 的交付卷随之丢失）；开发模式仍整批收口。"""
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue, recognize
    recognized = recognize('failure_action', str(getattr(action, 'value', action) or ''))
    if isinstance(recognized, UnrecognizedRoutingValue):
        return recognized
    return recognized in {FailureAction.IST_CORE_DEFECT.value, FailureAction.UNABLE_TO_COMPILE.value}
_CATEGORY_TERMINAL_ACTION = {FailureCategory.DEVICE_PREREQUISITE: FailureAction.UNABLE_TO_COMPILE, FailureCategory.CONNECTION: FailureAction.UNABLE_TO_COMPILE, FailureCategory.OCCUPANCY: FailureAction.RETRY, FailureCategory.ENVIRONMENT: FailureAction.RETRY, FailureCategory.RUNTIME_INFRASTRUCTURE: FailureAction.BLOCKED, FailureCategory.ENGINE_REJECTION: FailureAction.IST_CORE_DEFECT, FailureCategory.UNKNOWN: FailureAction.IST_CORE_DEFECT}
if frozenset(_CATEGORY_TERMINAL_ACTION) != frozenset(FailureCategory):
    raise RuntimeError('terminal_action_for_category map is not exhaustive')

def terminal_action_for_category(category: FailureCategory):
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue, recognize
    recognized = recognize('failure_category', str(getattr(category, 'value', category) or ''))
    if isinstance(recognized, UnrecognizedRoutingValue):
        return recognized
    return _CATEGORY_TERMINAL_ACTION[FailureCategory(recognized)]

def no_progress_fingerprint(identity: Mapping[str, Any] | ExecutionIdentity, reason_code: str) -> str:
    """同指纹 = 执行身份五元组 + reason_code；收据 sha / run_id 不入。"""
    if isinstance(identity, ExecutionIdentity):
        fields = {'aid': identity.autoid, 'artifact_sha256': identity.artifact_sha256, 'bed_host': identity.bed_host, 'build': identity.build, 'implementation_sha256': identity.implementation_sha256}
    else:
        fields = identity
    material = '\n'.join((str(fields.get('aid') or fields.get('autoid') or ''), str(fields.get('artifact_sha256') or ''), str(fields.get('bed_host') or ''), str(fields.get('build') or ''), str(fields.get('implementation_sha256') or ''), str(reason_code or '')))
    return hashlib.sha256(material.encode('utf-8')).hexdigest()

def _decision_axis_for_action(action: FailureAction) -> tuple[str, ...]:
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import axis_payload_for_event
    return tuple(axis_payload_for_event(action.value))

def _matches_identity(fact: Mapping[str, Any], identity: ExecutionIdentity) -> bool:
    return str(fact.get('aid') or '') == identity.autoid and str(fact.get('artifact_sha256') or '') == identity.artifact_sha256 and (str(fact.get('bed_host') or '') == identity.bed_host) and (str(fact.get('build') or '') == identity.build) and (str(fact.get('implementation_sha256') or '') == identity.implementation_sha256)

def identity_group(facts: Iterable[Mapping[str, Any]], identity: ExecutionIdentity) -> list[Mapping[str, Any]]:
    """同一执行身份的失败/成功，加上同 aid 的重入清零事实。"""
    group: list[Mapping[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, Mapping):
            continue
        event = str(fact.get('ev') or '')
        if event in REENTRY_CLEAR_EVENTS and str(fact.get('aid') or '') == identity.autoid:
            group.append(fact)
            continue
        if _matches_identity(fact, identity):
            group.append(fact)
    return group

def execution_failure_fact(decision: ExecutionFailureDecision, *, failure_evidence: Mapping[str, Any] | None=None, error_text: str='') -> dict[str, Any]:
    fact: dict[str, Any] = {'ev': EXECUTION_FAILURE_EVENT, 'aid': decision.identity.autoid, 'artifact_sha256': decision.identity.artifact_sha256, 'bed_host': decision.identity.bed_host, 'build': decision.identity.build, 'implementation_sha256': decision.identity.implementation_sha256, 'reason_code': decision.reason_code, 'category': decision.category.value if isinstance(decision.category, FailureCategory) else str(getattr(decision.category, 'value', 'unrecognized_routing_value')), 'attempt': decision.attempt, 'action': decision.action.value, 'fingerprint_hits': decision.fingerprint_hits, 'no_progress_fingerprint': decision.no_progress_fingerprint, 'decision_axis': list(decision.decision_axis), 'prerequisite_receipt_sha256': decision.prerequisite_receipt_sha256}
    safe_error_text = scrub_text(error_text, scrub_paths=True).strip()[:MAX_ERROR_TEXT_CHARS]
    if safe_error_text:
        fact['error_text'] = safe_error_text
    default_result_channel_evidence = None
    if decision.reason_code == 'result_channel_unavailable':
        default_result_channel_evidence = {'schema': 'ist.execution-failure-evidence', 'layer': 'framework_result_channel', 'state': 'unavailable', 'source': 'mysql', 'evidence_scope': 'case_artifact', 'evidence_file': 'device_echo.raw.txt'}
        if failure_evidence is None:
            failure_evidence = default_result_channel_evidence
    if isinstance(failure_evidence, Mapping):
        allowed = {'schema', 'layer', 'state', 'source', 'settle_attempts', 'error_type', 'task_id', 'evidence_scope', 'evidence_file', 'evidence_sha256'}
        raw_evidence_keys = {str(key) for key in failure_evidence}
        evidence = {str(key): value for key, value in failure_evidence.items() if key in allowed}
        if raw_evidence_keys <= allowed and accepts_schema(evidence.get('schema'), 'ist.execution-failure-evidence') and (evidence.get('layer') == 'framework_result_channel') and (evidence.get('state') in {'query_error', 'missing_after_done', 'unavailable'}) and (evidence.get('source') == 'mysql') and ('task_id' not in evidence or (isinstance(evidence.get('task_id'), str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', str(evidence['task_id'])) is not None and ('..' not in str(evidence['task_id'])))) and (evidence.get('evidence_scope') in {None, 'case_artifact'}) and ('settle_attempts' not in evidence or (isinstance(evidence.get('settle_attempts'), int) and (not isinstance(evidence.get('settle_attempts'), bool)) and (int(evidence['settle_attempts']) >= 0))) and isinstance(evidence.get('evidence_file'), str) and (Path(str(evidence['evidence_file'])).name == str(evidence['evidence_file'])) and (evidence.get('evidence_file') == 'device_echo.raw.txt') and ('error_type' not in evidence or (isinstance(evidence.get('error_type'), str) and len(str(evidence['error_type'])) <= 120)) and ('evidence_sha256' not in evidence or (isinstance(evidence.get('evidence_sha256'), str) and len(str(evidence['evidence_sha256'])) == 64 and all((char in '0123456789abcdef' for char in str(evidence['evidence_sha256']))))):
            fact['failure_evidence'] = evidence
    if default_result_channel_evidence is not None and 'failure_evidence' not in fact:
        fact['failure_evidence'] = default_result_channel_evidence
    return fact

def execution_success_fact(identity: ExecutionIdentity) -> dict[str, str]:
    return {'ev': EXECUTION_SUCCESS_EVENT, 'aid': identity.autoid, 'artifact_sha256': identity.artifact_sha256, 'bed_host': identity.bed_host, 'build': identity.build, 'implementation_sha256': identity.implementation_sha256}

def reduce_execution_failure_facts(group: Iterable[Mapping[str, Any]], *, current_reason: str, prerequisite_receipt_sha256: str='', fingerprint_identity: Mapping[str, Any] | ExecutionIdentity | None=None) -> dict[str, Any]:
    """按已分组的事实流记账。回放与 reducer 共用，不构造当前实现身份。"""
    current_reason, current_receipt_sha256 = _normalize_failure_reason(current_reason, prerequisite_receipt_sha256)
    current_category = classify_reason_code(current_reason)
    budgeted = 0
    prerequisite_attempts = 0
    fingerprint_hits: dict[str, int] = {}
    no_reexecution_terminal: tuple[str, FailureCategory, str, int, FailureAction, int, str] | None = None
    stalled_terminal: tuple[str, FailureCategory, str, int, FailureAction, int, str] | None = None
    budget_terminal: tuple[str, FailureCategory, str, str] | None = None
    prerequisite_terminal: tuple[str, FailureCategory, str] | None = None

    def _reset() -> None:
        nonlocal budgeted, fingerprint_hits, no_reexecution_terminal
        nonlocal stalled_terminal, budget_terminal
        nonlocal prerequisite_attempts, prerequisite_terminal
        budgeted = 0
        prerequisite_attempts = 0
        fingerprint_hits = {}
        no_reexecution_terminal = None
        stalled_terminal = None
        budget_terminal = None
        prerequisite_terminal = None

    def _fingerprint(reason: str) -> str:
        if fingerprint_identity is None:
            return reason
        return no_progress_fingerprint(fingerprint_identity, reason)
    for fact in group:
        if not isinstance(fact, Mapping):
            continue
        event = str(fact.get('ev') or '')
        if event == EXECUTION_SUCCESS_EVENT or event in REENTRY_CLEAR_EVENTS:
            _reset()
            continue
        if event != EXECUTION_FAILURE_EVENT:
            continue
        old_reason, old_category, old_receipt_sha256 = _classify_recorded_failure(fact)
        from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue
        if isinstance(old_category, UnrecognizedRoutingValue):
            continue
        if old_category in WAIT_CATEGORIES:
            continue
        if old_category in PREREQUISITE_CATEGORIES:
            if prerequisite_attempts < MAX_EXECUTION_ATTEMPTS:
                prerequisite_attempts += 1
                if prerequisite_attempts == MAX_EXECUTION_ATTEMPTS:
                    prerequisite_terminal = (old_reason, old_category, old_receipt_sha256)
            continue
        recorded_attempt = int(fact.get('attempt') or 0)
        mark = _fingerprint(old_reason)
        if old_category in BUDGETED_CATEGORIES:
            if budgeted >= MAX_EXECUTION_ATTEMPTS:
                continue
            budgeted += 1
            if old_reason in NO_DEVICE_REEXECUTION_REASON_CODES:
                no_reexecution_terminal = (old_reason, old_category, old_receipt_sha256, recorded_attempt or budgeted, terminal_action_for_category(old_category), 0, '')
            if budgeted == MAX_EXECUTION_ATTEMPTS:
                budget_terminal = (old_reason, old_category, old_receipt_sha256, mark)
            continue
        if old_category in NO_PROGRESS_CATEGORIES:
            hits = fingerprint_hits.get(old_reason, 0) + 1
            fingerprint_hits[old_reason] = hits
            action = terminal_action_for_category(old_category)
            packed = (old_reason, old_category, old_receipt_sha256, recorded_attempt or 1, action, hits, mark)
            if old_reason in NO_DEVICE_REEXECUTION_REASON_CODES:
                no_reexecution_terminal = packed
            if hits >= NO_PROGRESS_STALL_HITS:
                stalled_terminal = packed
    if no_reexecution_terminal is not None:
        reason, category, receipt, attempt, action, hits, mark = no_reexecution_terminal
        return {'reason_code': reason, 'category': category, 'attempt': attempt, 'action': action, 'record_failure': False, 'prerequisite_receipt_sha256': receipt, 'fingerprint_hits': hits, 'no_progress_fingerprint': mark}
    if stalled_terminal is not None:
        reason, category, receipt, attempt, action, hits, mark = stalled_terminal
        return {'reason_code': reason, 'category': category, 'attempt': attempt, 'action': action, 'record_failure': False, 'prerequisite_receipt_sha256': receipt, 'fingerprint_hits': hits, 'no_progress_fingerprint': mark}
    if prerequisite_terminal is not None:
        reason, category, receipt = prerequisite_terminal
        return {'reason_code': reason, 'category': category, 'attempt': MAX_EXECUTION_ATTEMPTS, 'action': terminal_action_for_category(category), 'record_failure': False, 'prerequisite_receipt_sha256': receipt, 'fingerprint_hits': 0, 'no_progress_fingerprint': ''}
    if budgeted >= MAX_EXECUTION_ATTEMPTS and budget_terminal is not None:
        reason, category, receipt, mark = budget_terminal
        return {'reason_code': reason, 'category': category, 'attempt': MAX_EXECUTION_ATTEMPTS, 'action': terminal_action_for_category(category), 'record_failure': False, 'prerequisite_receipt_sha256': receipt, 'fingerprint_hits': 0, 'no_progress_fingerprint': ''}
    attempt = budgeted + 1
    mark = ''
    hits = 0
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UNRECOGNIZED_ROUTING_VALUE, UnrecognizedRoutingValue
    if isinstance(current_category, UnrecognizedRoutingValue):
        return {'reason_code': UNRECOGNIZED_ROUTING_VALUE, 'category': current_category, 'attempt': attempt, 'action': FailureAction.BLOCKED, 'record_failure': True, 'prerequisite_receipt_sha256': current_receipt_sha256, 'fingerprint_hits': 0, 'no_progress_fingerprint': '', 'unrecognized': current_category}
    if current_category in WAIT_CATEGORIES:
        action = FailureAction.RETRY
    elif current_category in PREREQUISITE_CATEGORIES:
        attempt = prerequisite_attempts + 1
        action = terminal_action_for_category(current_category) if attempt >= MAX_EXECUTION_ATTEMPTS else FailureAction.RETRY
    elif current_reason in NO_DEVICE_REEXECUTION_REASON_CODES:
        action = terminal_action_for_category(current_category)
        hits = fingerprint_hits.get(current_reason, 0) + 1
        mark = _fingerprint(current_reason)
    elif current_category in NO_PROGRESS_CATEGORIES:
        hits = fingerprint_hits.get(current_reason, 0) + 1
        mark = _fingerprint(current_reason)
        action = terminal_action_for_category(current_category) if hits >= NO_PROGRESS_STALL_HITS else FailureAction.RETRY
    else:
        action = terminal_action_for_category(current_category) if attempt >= MAX_EXECUTION_ATTEMPTS else FailureAction.RETRY
    return {'reason_code': current_reason, 'category': current_category, 'attempt': attempt, 'action': action, 'record_failure': True, 'prerequisite_receipt_sha256': current_receipt_sha256, 'fingerprint_hits': hits, 'no_progress_fingerprint': mark}

def reduce_execution_failure(*, identity: ExecutionIdentity, reason_code: str, prerequisite_receipt_sha256: str='', facts: Iterable[Mapping[str, Any]]) -> ExecutionFailureDecision:
    folded = reduce_execution_failure_facts(identity_group(facts, identity), current_reason=reason_code, prerequisite_receipt_sha256=prerequisite_receipt_sha256, fingerprint_identity=identity)
    action = folded['action']
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import UnrecognizedRoutingValue
    axis_action = FailureAction.BLOCKED if isinstance(action, UnrecognizedRoutingValue) else action
    return ExecutionFailureDecision(identity=identity, reason_code=folded['reason_code'], category=folded['category'], attempt=folded['attempt'], action=axis_action if not isinstance(action, UnrecognizedRoutingValue) else FailureAction.BLOCKED, record_failure=folded['record_failure'], prerequisite_receipt_sha256=folded['prerequisite_receipt_sha256'], fingerprint_hits=folded['fingerprint_hits'], no_progress_fingerprint=folded['no_progress_fingerprint'], decision_axis=_decision_axis_for_action(axis_action))
