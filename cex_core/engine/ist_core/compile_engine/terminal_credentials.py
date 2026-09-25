# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/terminal_credentials.py（sha256 ad7d31ac9d02b624）。不在这里手改。
from __future__ import annotations
from cex_core.engine.common.engine_track_schema import engine_schema_id
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.ist_core.security_scrub import canonical_persisted_value, persisted_surface_sha256, scrub_text
SCHEMA = 'ist.compile.terminal_credential'
_CENTRAL_DEVICE_CONTEXTS = {'delivery': 'central_delivery', 'subset': 'central_subset'}
ATTRIBUTION_EVIDENCE_CORPUS_FIELDS = ('device_context', 'causality', 'detail_tail', 'framework_traceback')
ROUND_CAP_RECEIPT_SCHEMA = 'ist.delta.round-cap-receipt'
AUTHORING_FAILURE_RECEIPT_SCHEMA = 'ist.compile.authoring-failure-receipt'
AUTHORING_FAILURE_RECEIPT_SCHEMA_V2 = engine_schema_id('authoring_failure_receipt')
XML_ABSENCE_RECEIPT_SCHEMA = 'ist.delta.xml-absence-receipt'
_SHA256_RE = re.compile('[0-9a-f]{64}')
_ECHO_NAME_RE = re.compile('device_echo\\.r[1-9]\\d*\\.txt')
_NON_DELIVERY_LAYERS = frozenset({'device', 'compile', 'ought'})
_TO_UNATTRIBUTED_LAYER = 'unattributed'
_EXECUTION_TERMINAL_OUTCOMES = frozenset({'blocked', 'ist_core_defect', 'unable_to_compile'})
EMIT_LEDGER_CLAIM_KINDS = frozenset({'missing_teardown', 'xml_expectation_conflict', 'xml_command_shape_conflict', 'command_existence', 'sleep_budget_exceeded', 'answerer_undetermined'})

def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def _object_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()

def _fact_sha256(fact: dict) -> str:
    core = {key: value for key, value in fact.items() if not str(key).startswith('_') and key != 'decision_axis'}
    return _object_sha256(core)

def _is_nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value.strip().lower()))

def _read_regular_file(path: Path) -> bytes | None:
    try:
        if not path.is_file() or path.is_symlink():
            return None
        return path.read_bytes()
    except OSError:
        return None

def _read_case_file(case_dir: Path | None, name: str) -> bytes | None:
    if case_dir is None:
        return None
    root = Path(case_dir)
    try:
        if not root.is_dir() or root.is_symlink():
            return None
        target = root / name
        if target.parent.resolve() != root.resolve():
            return None
    except OSError:
        return None
    return _read_regular_file(target)

def find_case_dir(batch_dir: Path, aid: str) -> Path | None:
    batch = Path(batch_dir).resolve()
    candidates = (batch / 'unfinished' / aid, batch / 'delivered' / aid, batch / aid)
    for candidate in candidates:
        try:
            if candidate.is_dir() and (not candidate.is_symlink()) and candidate.resolve().is_relative_to(batch):
                return candidate
        except (OSError, ValueError):
            continue
    return None

def _decision_resolves_question(fact: dict) -> bool:
    return fact.get('ev') == 'decision' and str(fact.get('token') or '') != 'suspend'

def _latest_unanswered_question(facts: Iterable[dict], aid: str) -> dict:
    rows = [fact for fact in facts if str(fact.get('aid') or '') == aid]
    answered = {str(fact.get('question_id') or '') for fact in rows if _decision_resolves_question(fact) and str(fact.get('question_id') or '')}
    return next((fact for fact in reversed(rows) if fact.get('ev') == 'needs_decision' and str(fact.get('question_id') or '') and (str(fact.get('question_id') or '') not in answered)), {})

def _deterministic_verifiability_claim(item: dict) -> bool:
    from cex_core.engine.case_compiler.verifiability import CLAIM_KINDS
    return str(item.get('claim_kind') or '') in CLAIM_KINDS and item.get('verifiable') is False and _is_nonempty_text(item.get('reason')) and ('sources' not in item)

def _structured_claims(raw: Any) -> list[dict]:
    claims: list[dict] = []
    for item in raw if isinstance(raw, list) else ():
        if not isinstance(item, dict):
            continue
        if not _is_nonempty_text(item.get('claim_kind')):
            continue
        if _deterministic_verifiability_claim(item):
            claims.append(item)
            continue
        if str(item.get('claim_kind') or '') in EMIT_LEDGER_CLAIM_KINDS and (_is_nonempty_text(item.get('reason')) or _is_nonempty_text(item.get('reason_code'))):
            claims.append(item)
            continue
        substantive = any((_is_nonempty_text(item.get(key)) for key in ('reason', 'test_point', 'obstacle', 'no_equivalent_reason')))
        sources = item.get('sources')
        source_rows = [source for source in sources if isinstance(source, dict) and _is_nonempty_text(source.get('kind')) and _is_nonempty_text(source.get('quote'))] if isinstance(sources, list) else []
        if substantive and source_rows and (len(source_rows) == len(sources)):
            claims.append(item)
    return claims

def _build_ought_credential(aid: str, facts: list[dict], case_dir: Path | None) -> dict:
    refs: dict = {'schema': SCHEMA, 'kind': 'ought'}
    question = _latest_unanswered_question(facts, aid)
    if question:
        refs['question_id'] = str(question.get('question_id') or '')
        refs['question_fact_sha256'] = _fact_sha256(question)
    if case_dir is None:
        return refs
    payload = _read_case_file(case_dir, 'needs_decision.json')
    if payload is None:
        return refs
    try:
        ledger = json.loads(payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return refs
    if not isinstance(ledger, dict):
        return refs
    claims = _structured_claims(canonical_persisted_value(_structured_claims(ledger.get('claims'))))
    refs['ledger_receipt'] = {'name': 'needs_decision.json', 'bytes_sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}
    refs['claims'] = claims
    refs['claim_receipts'] = [{'claim_kind': str(claim.get('claim_kind') or ''), 'claim_sha256': _object_sha256(claim), 'source_quote_sha256': [hashlib.sha256(str(source.get('quote') or '').encode('utf-8')).hexdigest() for source in claim.get('sources') or []]} for claim in claims]
    return refs

def _build_compile_credential(aid: str, facts: list[dict]) -> dict:
    refs: dict = {'schema': SCHEMA, 'kind': 'compile'}
    decision = next((fact for fact in reversed(facts) if fact.get('ev') == 'no_progress_decision' and str(fact.get('aid') or '') == aid and (str(fact.get('domain') or '') == 'compile') and (fact.get('stop') is True)), {})
    if not decision:
        return refs
    refs.update({'decision_id': str(decision.get('decision_id') or ''), 'domain': 'compile', 'failure_key': str(decision.get('failure_key') or ''), 'streak': decision.get('streak'), 'threshold': decision.get('threshold'), 'revision_refs': list(decision.get('revision_refs') or []), 'stop': True, 'decision_fact_sha256': _fact_sha256(decision)})
    return refs

def _active_suspension_fact(aid: str, facts: list[dict]) -> dict:
    last_suspended = -1
    last_resumed = -1
    for index, fact in enumerate(facts):
        if str(fact.get('aid') or '') != aid:
            continue
        if fact.get('ev') == 'suspended':
            last_suspended = index
        elif fact.get('ev') == 'resumed':
            last_resumed = index
    if last_suspended < 0 or last_resumed > last_suspended:
        return {}
    return facts[last_suspended]

def _build_suspension_credential(aid: str, facts: list[dict]) -> dict:
    fact = _active_suspension_fact(aid, facts)
    refs = {'schema': SCHEMA, 'kind': 'suspension', 'reason': str(fact.get('reason') or '')}
    if fact:
        refs['suspension_fact_sha256'] = _fact_sha256(fact)
        if _is_nonempty_text(fact.get('question_id')):
            refs['question_id'] = str(fact['question_id'])
        if fact.get('suspension_kind') == 'execution_pause':
            refs.update({key: fact.get(key) for key in ('suspension_kind', 'pause_kind', 'basis_status', 'source_fact_sha256', 'source_event', 'source_run_id', 'evidence', 'fix_direction')})
    return refs
_ROUND_CAP_BLOCK_EVENTS = frozenset({'source_conflict_blocked', 'authority_preflight_blocked', 'ist_core_defect'})
_ROUND_CAP_REASON_CODE = 'blocked_round_cap_reached'
_ROUND_CAP_RECEIPT_FIELDS = ('round_cap_receipt_schema', 'source_block_event', 'source_block_fact_sha256', 'rounds_used', 'base_max_rounds', 'granted_rounds', 'effective_max_rounds', 'round_cap_receipt_sha256')

def _round_cap_receipt_material(fact: dict) -> dict:
    return {'schema': str(fact.get('round_cap_receipt_schema') or ''), 'aid': str(fact.get('aid') or ''), 'blocking_class': str(fact.get('blocking_class') or ''), 'reason_code': str(fact.get('reason_code') or ''), 'source_block_event': str(fact.get('source_block_event') or ''), 'source_block_fact_sha256': str(fact.get('source_block_fact_sha256') or ''), 'rounds_used': fact.get('rounds_used'), 'base_max_rounds': fact.get('base_max_rounds'), 'granted_rounds': fact.get('granted_rounds'), 'effective_max_rounds': fact.get('effective_max_rounds')}

def build_round_cap_policy_abandon_fact(*, aid: str, source_block_fact: dict, rounds_used: int, base_max_rounds: int, granted_rounds: int) -> dict:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    source = canonical_persisted_value(dict(source_block_fact))
    fact = {'ev': 'policy_abandon', 'aid': str(aid or ''), 'blocking_class': BT.A_ROUND_CAP, 'reason': '阻塞重入已达到编译轮次上限', 'reason_code': _ROUND_CAP_REASON_CODE, 'source_block_event': str(source.get('ev') or ''), 'source_block_fact_sha256': _fact_sha256(source), 'rounds_used': rounds_used, 'base_max_rounds': base_max_rounds, 'granted_rounds': granted_rounds, 'effective_max_rounds': base_max_rounds + granted_rounds, 'round_cap_receipt_schema': ROUND_CAP_RECEIPT_SCHEMA, 'terminal': True}
    fact['round_cap_receipt_sha256'] = persisted_surface_sha256(_round_cap_receipt_material(fact))
    return fact

def _round_cap_policy_fact(aid: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'policy_abandon' and str(fact.get('aid') or '') == aid and (fact.get('blocking_class') == BT.A_ROUND_CAP)), {})

def _build_round_cap_credential(aid: str, facts: list[dict]) -> dict:
    fact = _round_cap_policy_fact(aid, facts)
    refs = {'schema': SCHEMA, 'kind': 'round_cap'}
    if not fact:
        return refs
    refs['abandon_fact_sha256'] = _fact_sha256(fact)
    refs.update({field: fact.get(field) for field in _ROUND_CAP_RECEIPT_FIELDS})
    return refs
_AUTHORING_FAILURE_REASON_CODE = 'authoring_rounds_exhausted_case_side'
AUTHORING_ROUTE_ROUND_CAP = 'round_cap_exhausted'
AUTHORING_ROUTE_WORKER_CLAIM_HANDOFF = 'worker_claim_handoff'
AUTHORING_FAILURE_ROUTES = frozenset({AUTHORING_ROUTE_ROUND_CAP, AUTHORING_ROUTE_WORKER_CLAIM_HANDOFF})
_AUTHORING_FAILURE_RECEIPT_FIELDS = ('reason_code', 'settlement_route', 'rounds_used', 'base_max_rounds', 'granted_rounds', 'effective_max_rounds', 'round_causes_sha256')

def _authoring_failure_receipt_material(fact: dict) -> dict:
    return {'schema': str(fact.get('authoring_failure_receipt_schema') or ''), 'aid': str(fact.get('aid') or ''), 'reason_code': str(fact.get('reason_code') or ''), 'settlement_route': str(fact.get('settlement_route') or ''), 'rounds_used': fact.get('rounds_used'), 'base_max_rounds': fact.get('base_max_rounds'), 'granted_rounds': fact.get('granted_rounds'), 'effective_max_rounds': fact.get('effective_max_rounds'), 'round_causes_sha256': str(fact.get('round_causes_sha256') or '')}

def _round_causes_sha256(round_causes: list[dict]) -> str:
    return _object_sha256([canonical_persisted_value(dict(row)) for row in round_causes])

def build_authoring_failure_fact(*, aid: str, round_causes: list[dict], rounds_used: int, base_max_rounds: int, granted_rounds: int, settlement_route: str=AUTHORING_ROUTE_ROUND_CAP) -> dict:
    causes = [dict(row) for row in round_causes if isinstance(row, dict)]
    if not causes or not all((bool(row.get('case_side')) for row in causes)):
        raise ValueError('authoring failure requires case-side causes for every round')
    route = str(settlement_route or '')
    if route not in AUTHORING_FAILURE_ROUTES:
        raise ValueError(f'authoring failure settlement_route {route!r} is not a route')
    fact = {'ev': 'authoring_failure', 'aid': str(aid or ''), 'round': int(rounds_used), 'reason_code': _AUTHORING_FAILURE_REASON_CODE, 'settlement_route': route, 'terminal_layer': 'authoring', 'rounds_used': int(rounds_used), 'base_max_rounds': int(base_max_rounds), 'granted_rounds': int(granted_rounds), 'effective_max_rounds': int(base_max_rounds) + int(granted_rounds), 'round_causes': causes, 'round_causes_sha256': _round_causes_sha256(causes), 'authoring_failure_receipt_schema': AUTHORING_FAILURE_RECEIPT_SCHEMA, 'reentrant': True, 'terminal': True}
    fact['authoring_failure_receipt_sha256'] = persisted_surface_sha256(_authoring_failure_receipt_material(fact))
    return fact

def _authoring_failure_fact(aid: str, facts: list[dict]) -> dict:
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'authoring_failure' and str(fact.get('aid') or '') == aid), {})

def build_verified_authoring_failure_fact(*, aid: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine import authoring_evidence as AE
    proof, errors = AE.verified_failure_proof(facts, aid)
    if errors:
        raise ValueError('authoring failure evidence incomplete: ' + ', '.join(errors))
    causes = [{'round': index, 'cause': 'verified_authoring_attempt_failure', 'case_side': True, 'source_event': 'worker_dispatch_started', 'source_fact_sha256': attempt['dispatch_sha256']} for index, attempt in enumerate(proof['attempts'], 1)]
    fact = build_authoring_failure_fact(aid=aid, round_causes=causes, rounds_used=3, base_max_rounds=3, granted_rounds=0)
    fact['authoring_proof'] = proof
    fact['diagnostic_id'] = 'AF-0002'
    fact['authoring_failure_receipt_schema'] = AUTHORING_FAILURE_RECEIPT_SCHEMA_V2
    fact['batch_run_id'] = proof['attempts'][-1]['batch_run_id']
    fact['dispatch_id'] = proof['attempts'][-1]['dispatch_id']
    fact['authoring_failure_receipt_sha256'] = _authoring_failure_v2_digest(fact)
    return fact
_AUTHORING_V2_REF_FIELDS = _AUTHORING_FAILURE_RECEIPT_FIELDS + ('authoring_failure_receipt_schema', 'authoring_failure_receipt_sha256', 'diagnostic_id', 'batch_run_id', 'dispatch_id')

def _authoring_failure_v2_digest(fact: dict) -> str:
    return persisted_surface_sha256({key: value for key, value in fact.items() if key not in ('authoring_failure_receipt_sha256', 'decision_axis') and (not key.startswith('_'))})

def _build_authoring_failure_credential(aid: str, facts: list[dict]) -> dict:
    fact = _authoring_failure_fact(aid, facts)
    refs = {'schema': SCHEMA, 'kind': 'authoring_failure'}
    if not fact:
        return refs
    refs['terminal_fact_sha256'] = _fact_sha256(fact)
    refs.update({field: fact.get(field) for field in _AUTHORING_FAILURE_RECEIPT_FIELDS})
    if fact.get('authoring_proof'):
        refs['authoring_proof'] = fact['authoring_proof']
    if fact.get('authoring_failure_receipt_schema') == AUTHORING_FAILURE_RECEIPT_SCHEMA_V2:
        refs.update({field: fact.get(field) for field in _AUTHORING_V2_REF_FIELDS})
    return refs

def _validate_authoring_failure(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    from cex_core.engine.ist_core.compile_engine import facts as fact_rules
    expected_sha = str(refs.get('terminal_fact_sha256') or '')
    index = next((i for i in range(len(facts) - 1, -1, -1) if facts[i].get('ev') == 'authoring_failure' and str(facts[i].get('aid') or '') == aid and (_fact_sha256(facts[i]) == expected_sha)), -1)
    if index < 0:
        return ['authoring_failure_receipt_missing']
    fact = facts[index]
    if fact.get('authoring_failure_receipt_schema') == AUTHORING_FAILURE_RECEIPT_SCHEMA_V2 or 'authoring_proof' in fact or 'authoring_proof' in refs:
        from cex_core.engine.ist_core.compile_engine import authoring_evidence as AE
        proof, errors = AE.verified_failure_proof(facts[:index], aid)
        expected_keys = {'ev', 'aid', 'round', 'reason_code', 'settlement_route', 'terminal_layer', 'rounds_used', 'base_max_rounds', 'granted_rounds', 'effective_max_rounds', 'round_causes', 'round_causes_sha256', 'authoring_failure_receipt_schema', 'reentrant', 'terminal', 'authoring_failure_receipt_sha256', 'authoring_proof', 'diagnostic_id', 'batch_run_id', 'dispatch_id'}
        fact_keys = {key for key in fact if not key.startswith('_') and key != 'decision_axis'}
        if fact_keys != expected_keys or fact.get('terminal') is not True or fact.get('reentrant') is not True or (fact.get('terminal_layer') != 'authoring') or (fact.get('reason_code') != _AUTHORING_FAILURE_REASON_CODE) or (fact.get('settlement_route') != AUTHORING_ROUTE_ROUND_CAP) or (fact.get('authoring_failure_receipt_schema') != AUTHORING_FAILURE_RECEIPT_SCHEMA_V2) or (fact.get('diagnostic_id') != 'AF-0002'):
            errors.append('authoring_failure_contract_mismatch')
        expected_refs = {'schema', 'kind', 'terminal_fact_sha256', 'authoring_proof', *_AUTHORING_V2_REF_FIELDS}
        if set(refs) != expected_refs or refs.get('schema') != SCHEMA or refs.get('kind') != 'authoring_failure' or any((refs.get(field) != fact.get(field) for field in _AUTHORING_V2_REF_FIELDS)):
            errors.append('authoring_failure_binding_mismatch')
        if refs.get('authoring_proof') != proof or fact.get('authoring_proof') != proof:
            errors.append('authoring_proof_binding_mismatch')
        if fact.get('authoring_failure_receipt_sha256') != _authoring_failure_v2_digest(fact):
            errors.append('authoring_proof_hash_mismatch')
        required_counts = {'round': 3, 'rounds_used': 3, 'effective_max_rounds': 3, 'base_max_rounds': 3, 'granted_rounds': 0}
        if any((type(fact.get(key)) is not int or fact.get(key) != value for key, value in required_counts.items())):
            errors.append('authoring_three_attempt_contract_mismatch')
        expected_causes = [{'round': number, 'cause': 'verified_authoring_attempt_failure', 'case_side': True, 'source_event': 'worker_dispatch_started', 'source_fact_sha256': attempt['dispatch_sha256']} for number, attempt in enumerate(proof['attempts'], 1)]
        if fact.get('round_causes') != expected_causes or fact.get('round_causes_sha256') != _round_causes_sha256(expected_causes):
            errors.append('authoring_failure_causes_mismatch')
        last = proof['attempts'][-1] if proof['attempts'] else {}
        if fact.get('batch_run_id') != last.get('batch_run_id') or fact.get('dispatch_id') != last.get('dispatch_id'):
            errors.append('authoring_failure_dispatch_mismatch')
        return sorted(set(errors))
    from cex_core.engine.ist_core.compile_engine import authoring_evidence as AE
    if AE.uses_new_policy(facts[:index]):
        return ['authoring_failure_v2_proof_required']
    errors: list[str] = []
    if fact.get('reason_code') != _AUTHORING_FAILURE_REASON_CODE or str(fact.get('settlement_route') or '') not in AUTHORING_FAILURE_ROUTES or fact.get('terminal') is not True or (fact.get('reentrant') is not True) or (fact.get('terminal_layer') != 'authoring') or (fact.get('authoring_failure_receipt_schema') != AUTHORING_FAILURE_RECEIPT_SCHEMA):
        errors.append('authoring_failure_contract_mismatch')
    if any((refs.get(field) != fact.get(field) for field in _AUTHORING_FAILURE_RECEIPT_FIELDS)):
        errors.append('authoring_failure_binding_mismatch')
    material = _authoring_failure_receipt_material(fact)
    if not _is_sha256(fact.get('authoring_failure_receipt_sha256')) or persisted_surface_sha256(material) != fact.get('authoring_failure_receipt_sha256'):
        errors.append('authoring_failure_receipt_hash_mismatch')
    recomputed = fact_rules.authoring_round_causes(facts[:index], aid)
    recorded = [dict(row) for row in fact.get('round_causes') or [] if isinstance(row, dict)]
    if not recorded or not all((bool(row.get('case_side')) for row in recorded)):
        errors.append('authoring_failure_causes_not_case_side')
    if _round_causes_sha256(recomputed) != _round_causes_sha256(recorded) or _round_causes_sha256(recorded) != str(fact.get('round_causes_sha256') or ''):
        errors.append('authoring_failure_causes_mismatch')
    rounds_used = fact.get('rounds_used')
    if isinstance(rounds_used, bool) or not isinstance(rounds_used, int) or rounds_used < 1:
        errors.append('authoring_failure_rounds_invalid')
    return errors
AUTHOR_GAP_RECEIPT_SCHEMA = 'ist.author-definition-gap'
_AUTHOR_GAP_RECEIPT_FIELDS = ('author_gap_receipt_schema', 'declaration_basis', 'author_gap_declaration', 'source_event', 'source_fact_sha256', 'not_compilable_report_hash', 'author_gap_receipt_sha256')
_AUTHOR_GAP_BASES = frozenset({'worker_report', 'surviving_claim', 'static_ledger'})

def _author_gap_receipt_material(fact: dict) -> dict:
    return {'schema': str(fact.get('author_gap_receipt_schema') or ''), 'aid': str(fact.get('aid') or ''), 'blocking_class': str(fact.get('blocking_class') or ''), 'declaration_basis': str(fact.get('declaration_basis') or ''), 'author_gap_declaration': str(fact.get('author_gap_declaration') or ''), 'source_event': str(fact.get('source_event') or ''), 'source_fact_sha256': str(fact.get('source_fact_sha256') or ''), 'not_compilable_report_hash': str(fact.get('not_compilable_report_hash') or '')}

def build_author_definition_gap_abandon_fact(*, aid: str, declaration: str, declaration_basis: str, source_fact: dict, obstacle_cn: str='', report_hash: str='', variant: str='') -> dict:
    """第八格放弃事实。`variant` 只换用户面 `reason` 的说法与那句导语。

    `reason` **不在** `_author_gap_receipt_material` 的键集里，所以换说法不动收据
    哈希、存量批的凭据不会因此整片失效；凭据层（`blocking_class` / `reason_code` /
    收据材料）一个字不变。
    """
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    basis = str(declaration_basis or '')
    if basis not in _AUTHOR_GAP_BASES:
        raise ValueError(f'unknown author-gap declaration basis: {basis!r}')
    declaration_text = str(canonical_persisted_value(str(declaration or '').strip()))
    if not declaration_text:
        raise ValueError('author-gap abandon requires a non-empty declaration')
    source = canonical_persisted_value(dict(source_fact or {}))
    reason_cn = BT.variant_text('reason', cls=BT.A_AUTHOR_DEFINITION_GAP, variant=variant)
    if obstacle_cn.strip():
        reason_cn = BT.variant_text('reason_lead', variant=variant) + obstacle_cn.strip()
    fact = {'ev': 'policy_abandon', 'aid': str(aid or ''), 'blocking_class': BT.A_AUTHOR_DEFINITION_GAP, 'reason_code': 'author_definition_gap', 'reason': reason_cn, 'declaration_basis': basis, 'author_gap_declaration': declaration_text, 'source_event': str(source.get('ev') or ''), 'source_fact_sha256': _fact_sha256(source), 'not_compilable_report_hash': str(report_hash or ''), 'author_gap_receipt_schema': AUTHOR_GAP_RECEIPT_SCHEMA, 'terminal': True}
    fact['author_gap_receipt_sha256'] = persisted_surface_sha256(_author_gap_receipt_material(fact))
    return fact

def author_gap_variant(aid: str, facts: list[dict]) -> str:
    """第八格的用户面变体：`gap`（缺定义）还是 `conflict`（两处说法互斥）。

    **不新增事实字段**——放弃事实已按 `source_fact_sha256` 绑定了那份
    `not_compilable` 报告，变体就读它的 `reason_code`。加字段会改收据材料的键集，
    存量批落过的凭据会按哈希不符整片失效，那是用户看不见的回归。
    信封声明路（`declaration_basis != worker_report`）恒为 `gap`：那条路根本没有报告。
    """
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.worker_device_context import NOT_COMPILABLE_REASON_AUTHOR_CONFLICT
    case_aid = str(aid or '')
    policy = _author_gap_policy_fact(case_aid, facts)
    if str(policy.get('declaration_basis') or '') != 'worker_report':
        return BT.AUTHOR_GAP_VARIANT
    source = _find_fact_by_sha(facts, aid=case_aid, ev='not_compilable', expected_sha256=str(policy.get('source_fact_sha256') or ''))
    report = source.get('report') if isinstance(source, dict) else None
    if isinstance(report, dict) and str(report.get('reason_code') or '') == NOT_COMPILABLE_REASON_AUTHOR_CONFLICT:
        return BT.AUTHOR_CONFLICT_VARIANT
    return BT.AUTHOR_GAP_VARIANT

def _author_gap_policy_fact(aid: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'policy_abandon' and str(fact.get('aid') or '') == aid and (fact.get('blocking_class') == BT.A_AUTHOR_DEFINITION_GAP)), {})

def _build_author_definition_gap_credential(aid: str, facts: list[dict]) -> dict:
    fact = _author_gap_policy_fact(aid, facts)
    refs = {'schema': SCHEMA, 'kind': 'author_definition_gap'}
    if not fact:
        return refs
    refs['abandon_fact_sha256'] = _fact_sha256(fact)
    refs.update({field: fact.get(field) for field in _AUTHOR_GAP_RECEIPT_FIELDS})
    return refs

def _validate_author_definition_gap(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.worker_device_context import AUTHOR_SIDE_NOT_COMPILABLE_REASON_CODES
    errors: list[str] = []
    policy = _author_gap_policy_fact(aid, facts)
    if not policy:
        return ['author_gap_policy_receipt_missing']
    if str(refs.get('abandon_fact_sha256') or '') != _fact_sha256(policy) or policy.get('author_gap_receipt_schema') != AUTHOR_GAP_RECEIPT_SCHEMA or policy.get('blocking_class') != BT.A_AUTHOR_DEFINITION_GAP or (policy.get('reason_code') != 'author_definition_gap'):
        errors.append('author_gap_policy_contract_mismatch')
    if any((refs.get(field) != policy.get(field) for field in _AUTHOR_GAP_RECEIPT_FIELDS)):
        errors.append('author_gap_binding_mismatch')
    material = _author_gap_receipt_material(policy)
    if not _is_sha256(policy.get('author_gap_receipt_sha256')) or persisted_surface_sha256(material) != policy.get('author_gap_receipt_sha256'):
        errors.append('author_gap_receipt_hash_mismatch')
    declaration = str(policy.get('author_gap_declaration') or '')
    if not declaration.strip():
        errors.append('author_gap_declaration_missing')
    basis = str(policy.get('declaration_basis') or '')
    source_sha = str(policy.get('source_fact_sha256') or '')
    if basis == 'surviving_claim':
        source = _find_fact_by_sha(facts, aid=aid, ev='escalated', expected_sha256=source_sha)
        if not source:
            errors.append('author_gap_declaration_receipt_missing')
        else:
            from cex_core.engine.ist_core.compile_engine import facts as fact_rules
            if fact_rules._fact_esc_family(source) != fact_rules.ESCALATION_FAMILY_UNDERDETERMINED_CLAIM or fact_rules.underdetermined_declaration(source) != declaration:
                errors.append('author_gap_declaration_mismatch')
    elif basis == 'worker_report':
        source = _find_fact_by_sha(facts, aid=aid, ev='not_compilable', expected_sha256=source_sha)
        report = source.get('report') if isinstance(source, dict) else None
        if not isinstance(report, dict):
            errors.append('author_gap_report_receipt_missing')
        elif str(report.get('reason_code') or '') not in AUTHOR_SIDE_NOT_COMPILABLE_REASON_CODES or str(report.get('report_hash') or '') != str(policy.get('not_compilable_report_hash') or '') or str(canonical_persisted_value(str(report.get('no_equivalent_reason') or '').strip())) != declaration:
            errors.append('author_gap_report_mismatch')
    elif basis == 'static_ledger':
        source = _find_fact_by_sha(facts, aid=aid, ev='author_definition_gap_disclosed', expected_sha256=source_sha)
        if not source:
            errors.append('author_gap_static_ledger_receipt_missing')
        elif str(source.get('declaration') or '') != declaration:
            errors.append('author_gap_static_ledger_declaration_mismatch')
    else:
        errors.append('author_gap_basis_invalid')
    return errors

def author_definition_gap_auto_resolution_valid(*, aid: str, ledger_sha256: str, facts: list[dict]) -> bool:
    ledger_sha = str(ledger_sha256 or '')
    if _SHA256_RE.fullmatch(ledger_sha) is None:
        return False
    rows = [fact for fact in facts if isinstance(fact, dict) and str(fact.get('aid') or '') == str(aid or '')]
    disclosures = [fact for fact in rows if fact.get('ev') == 'author_definition_gap_disclosed' and accepts_schema(fact.get('schema'), 'ist.author-definition-gap-disclosure') and (str(fact.get('ledger_sha256') or '') == ledger_sha)]
    if not disclosures:
        return False
    policy = _author_gap_policy_fact(str(aid or ''), rows)
    if str(policy.get('declaration_basis') or '') != 'static_ledger':
        return False
    refs = _build_author_definition_gap_credential(str(aid or ''), rows)
    return not _validate_author_definition_gap(str(aid or ''), refs, rows)

def _xml_absence_veto_claims(claims: Any) -> list[dict]:
    return [claim for claim in claims if isinstance(claim, dict) and claim.get('claim_kind') == 'command_existence' and (claim.get('terminal') is True) and (claim.get('requires_user_decision') is False)] if isinstance(claims, list) else []

def xml_absence_veto_claims(claims: Any) -> list[dict]:
    return _xml_absence_veto_claims(claims)

def _xml_absence_receipt_material(fact: dict) -> dict:
    return {'schema': str(fact.get('xml_absence_receipt_schema') or ''), 'aid': str(fact.get('aid') or ''), 'blocking_class': str(fact.get('blocking_class') or ''), 'reason': str(fact.get('reason') or ''), 'claims_sha256': str(fact.get('claims_sha256') or ''), 'veto_claim_sha256s': list(fact.get('veto_claim_sha256s') or [])}

def build_xml_absence_terminal_fact(*, aid: str, claims: list[dict]) -> dict:
    persisted_claims = canonical_persisted_value([dict(claim) for claim in claims if isinstance(claim, dict)])
    vetoes = _xml_absence_veto_claims(persisted_claims)
    reason = str((vetoes[0] if vetoes else {}).get('reason') or '设备 XML 命令树未收录该命令，设备不支持这个功能')
    reason = str(canonical_persisted_value(reason))
    fact = {'ev': 'xml_absence_terminal', 'aid': str(aid or ''), 'blocking_class': 'manual_error_confirmed', 'claims': persisted_claims, 'reason': reason, 'claims_sha256': persisted_surface_sha256(persisted_claims), 'veto_claim_sha256s': [persisted_surface_sha256(claim) for claim in vetoes], 'xml_absence_receipt_schema': XML_ABSENCE_RECEIPT_SCHEMA}
    fact['xml_absence_receipt_sha256'] = persisted_surface_sha256(_xml_absence_receipt_material(fact))
    return fact

def build_final_volume_failure_terminal_fact(*, aid: str, failure: dict, round_no: int) -> dict:
    """收口卷面失败的案级终态。**签发点唯一入口**，别在调用处自己拼这个形状。

    位域写在 `ev` 上（`blocked` = 用例自己的期望值来源待裁 / `ist_core_defect` = 引擎侧），
    由成因前缀表 `terminal_outcomes.AUTHORITY_POSITION_BY_PREFIX` 判，混因取最严；
    `terminal_layer` 说的是**阶段**（交付），不是位域。两者揉进同一个字段，签发侧与凭据
    复核侧就会漂开——凭据那一枚（`delivery_failure`）对两个位域载荷同构、由校验侧按
    同一张表复核 `outcome`（见 `_validate_delivery_failure`）。

    `reason_code` / `source_event` 取 `failure` 自己的 `ev`，不按轴重算名字：旧名事实
    冻结在三批语料里，重算会让终态指着一条账上不存在的名字。
    """
    from cex_core.engine.ist_core.compile_engine import terminal_outcomes as TO
    event = str(failure.get('ev') or '')
    from cex_core.engine.ist_core.compile_engine.terminal_reentry_identity import copy_identity
    return {**copy_identity(failure), 'ev': TO.CASE_TERMINAL_EVENT_BY_OUTCOME[TO.authority_failure_position(failure.get('reasons'))], 'aid': str(aid or ''), 'round': round_no, 'reason_code': event, 'failure_axis': str(failure.get('failure_axis') or ''), 'terminal_layer': 'delivery', 'source_event': event, 'source_fact_sha256': _fact_sha256(dict(failure)), 'reentrant': True, 'terminal': False}

def _xml_absence_terminal_fact(aid: str, facts: list[dict]) -> dict:
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'xml_absence_terminal' and str(fact.get('aid') or '') == aid), {})
_XML_ABSENCE_RECEIPT_FIELDS = ('blocking_class', 'reason', 'claims_sha256', 'veto_claim_sha256s', 'xml_absence_receipt_schema', 'xml_absence_receipt_sha256')

def _build_xml_absence_credential(aid: str, facts: list[dict]) -> dict:
    fact = _xml_absence_terminal_fact(aid, facts)
    refs = {'schema': SCHEMA, 'kind': 'xml_absence'}
    if not fact:
        return refs
    refs['terminal_fact_sha256'] = _fact_sha256(fact)
    refs.update({field: fact.get(field) for field in _XML_ABSENCE_RECEIPT_FIELDS})
    return refs

def _build_unsupported_feature_credential(aid: str, facts: list[dict]) -> dict:
    fact = next((row for row in reversed(facts) if row.get('ev') == 'unsupported_feature' and str(row.get('aid') or '') == aid), {})
    refs = {'schema': SCHEMA, 'kind': 'unsupported_feature', 'report_hash': str(fact.get('report_hash') or ''), 'fact_sha256': _fact_sha256(fact) if fact else '', 'probe_evidence_refs': list(fact.get('probe_evidence_refs') or []), 'co_probes': list(fact.get('co_probes') or [])}
    return refs

def _validate_unsupported_feature(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    errors: list[str] = []
    fact = _find_fact_by_sha(facts, aid=aid, ev='unsupported_feature', expected_sha256=str(refs.get('fact_sha256') or ''))
    probes = refs.get('co_probes')
    probe_refs = refs.get('probe_evidence_refs')
    claim = fact.get('claim') if isinstance(fact, dict) else None
    valid_probe_rows = isinstance(probes, list) and len(probes) >= 2 and all((isinstance(item, dict) for item in probes))
    if not fact or not valid_probe_rows or (not isinstance(probe_refs, list)):
        return ['unsupported_feature_co_probe_invalid']
    probe_ids = [str(item.get('probe_id') or '') for item in probes]
    commands = [str(item.get('command_sha256') or '') for item in probes]
    hypotheses = [str(item.get('hypothesis_sha256') or '') for item in probes]
    outcomes = [str(item.get('outcome') or '') for item in probes]
    normalized_refs = [str(value or '') for value in probe_refs]
    if len(set(normalized_refs)) < 2 or len(set(probe_ids)) != len(probe_ids) or set(probe_ids) != set(normalized_refs) or (len(set(commands)) < 2) or (len(set(hypotheses)) < 2) or (not all((_is_sha256(value) for value in commands + hypotheses))) or any((value not in {'observed', 'cli_rejected'} for value in outcomes)):
        errors.append('unsupported_feature_co_probe_invalid')
    material = {'schema': 'ist.compile.unsupported-feature', 'autoid': aid, 'probe_evidence_refs': sorted(set(normalized_refs)), 'claim': claim if isinstance(claim, dict) else {}, 'co_probes': probes}
    if not _is_sha256(refs.get('report_hash')) or persisted_surface_sha256(material) != refs.get('report_hash'):
        errors.append('unsupported_feature_report_hash_mismatch')
    if refs.get('report_hash') != fact.get('report_hash') or refs.get('co_probes') != fact.get('co_probes') or refs.get('probe_evidence_refs') != fact.get('probe_evidence_refs'):
        errors.append('unsupported_feature_binding_mismatch')
    return errors

def _build_not_compilable_credential(aid: str, facts: list[dict]) -> dict:
    fact = next((row for row in reversed(facts) if row.get('ev') == 'not_compilable' and str(row.get('aid') or '') == aid and isinstance(row.get('report'), dict)), {})
    report = fact.get('report') if isinstance(fact, dict) else {}
    report = report if isinstance(report, dict) else {}
    return {'schema': SCHEMA, 'kind': 'not_compilable', 'report_schema': str(report.get('schema') or ''), 'reason_code': str(report.get('reason_code') or ''), 'report_hash': str(report.get('report_hash') or ''), 'fact_sha256': _fact_sha256(fact) if fact else '', 'dispatch_id': str(fact.get('dispatch_id') or '') if fact else '', 'command_heads_receipts': list(report.get('command_heads_receipts') or []), 'capability_build': str(report.get('capability_build') or ''), 'capability_generation_id': str(report.get('capability_generation_id') or ''), 'capability_manifest_sha256': str(report.get('capability_manifest_sha256') or ''), 'source_manifest_ref': str(report.get('source_manifest_ref') or ''), 'source_manifest_sha256': str(report.get('source_manifest_sha256') or ''), 'source_case_slice_sha256': str(report.get('source_case_slice_sha256') or '')}

def _validate_not_compilable(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    errors: list[str] = []
    fact = _find_fact_by_sha(facts, aid=aid, ev='not_compilable', expected_sha256=str(refs.get('fact_sha256') or ''))
    report = fact.get('report') if isinstance(fact, dict) else None
    if not isinstance(report, dict):
        return ['not_compilable_fact_missing']
    report_hash = str(report.get('report_hash') or '')
    material = {key: value for key, value in report.items() if key != 'report_hash'}
    sources = report.get('sources')
    query_receipts = report.get('command_heads_receipts')
    source_rows_valid = isinstance(sources, list) and bool(sources) and all((isinstance(source, dict) and set(source) == {'kind', 'quote'} and (source.get('kind') in {'title', 'step', 'expected'}) and _is_nonempty_text(source.get('quote')) for source in sources))
    receipt_rows_valid = isinstance(query_receipts, list) and bool(query_receipts) and all((isinstance(receipt, dict) and set(receipt) == {'receipt_id', 'module_prefix', 'result_sha256', 'head_count'} and _is_nonempty_text(receipt.get('receipt_id')) and _is_nonempty_text(receipt.get('module_prefix')) and _is_sha256(receipt.get('result_sha256')) and (type(receipt.get('head_count')) is int) and (int(receipt['head_count']) >= 0) for receipt in query_receipts))
    from cex_core.engine.ist_core.worker_device_context import NOT_COMPILABLE_REASON_ENV_GAP, NOT_COMPILABLE_REASON_NO_CLI
    if not accepts_schema(report.get('schema'), 'ist.not-compilable') or str(report.get('autoid') or '') != aid or report.get('reason_code') not in {NOT_COMPILABLE_REASON_NO_CLI, NOT_COMPILABLE_REASON_ENV_GAP} or (not all((_is_nonempty_text(report.get(field)) for field in ('test_point', 'obstacle', 'no_equivalent_reason')))) or (not source_rows_valid) or (not receipt_rows_valid) or (not _is_nonempty_text(report.get('capability_build'))) or (not _is_nonempty_text(report.get('capability_generation_id'))) or (not _is_sha256(report.get('capability_manifest_sha256'))) or (not _is_nonempty_text(report.get('source_manifest_ref'))) or (not _is_sha256(report.get('source_manifest_sha256'))) or (not _is_sha256(report.get('source_case_slice_sha256'))):
        errors.append('not_compilable_report_shape_invalid')
    if not _is_sha256(report_hash) or persisted_surface_sha256(material) != report_hash:
        errors.append('not_compilable_report_hash_mismatch')
    if not _is_nonempty_text(fact.get('dispatch_id')):
        errors.append('not_compilable_dispatch_missing')
    expected_refs = {'report_schema': str(report.get('schema') or ''), 'reason_code': str(report.get('reason_code') or ''), 'report_hash': report_hash, 'dispatch_id': str(fact.get('dispatch_id') or ''), 'command_heads_receipts': list(query_receipts or []), 'capability_build': str(report.get('capability_build') or ''), 'capability_generation_id': str(report.get('capability_generation_id') or ''), 'capability_manifest_sha256': str(report.get('capability_manifest_sha256') or ''), 'source_manifest_ref': str(report.get('source_manifest_ref') or ''), 'source_manifest_sha256': str(report.get('source_manifest_sha256') or ''), 'source_case_slice_sha256': str(report.get('source_case_slice_sha256') or '')}
    if any((refs.get(key) != value for key, value in expected_refs.items())):
        errors.append('not_compilable_binding_mismatch')
    return errors

def abandon_credential_layer(blocking_class: str) -> str:
    return abandon_credential_layer_map().get(str(blocking_class or ''), '')
_ABANDON_CREDENTIAL_LAYER: dict[str, str] = {}

def blocked_credential_layer(blocking_fact: dict | None) -> str:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_BINDING_FIELDS
    fact = blocking_fact if isinstance(blocking_fact, dict) else {}
    layer = _BLOCKED_CREDENTIAL_LAYER.get(str(fact.get('ev') or ''), '')
    if not layer:
        return ''
    receipt_fields = ('mechanical_case_sha256', 'batch_receipt_sha256', *BATCH_BINDING_FIELDS)
    if any((not re.fullmatch('[0-9a-f]{64}', str(fact.get(field) or '')) for field in receipt_fields)):
        return ''
    return layer
_BLOCKED_CREDENTIAL_LAYER: dict[str, str] = {'source_conflict_blocked': 'source_conflict_blocked'}

def blocked_credential_events() -> frozenset:
    return frozenset(_BLOCKED_CREDENTIAL_LAYER)

def abandon_credential_layer_map() -> dict[str, str]:
    global _ABANDON_CREDENTIAL_LAYER
    if not _ABANDON_CREDENTIAL_LAYER:
        from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
        _ABANDON_CREDENTIAL_LAYER = {BT.A_ROUND_CAP: 'round_cap', BT.A_NO_CLI_EQUIVALENT: 'not_compilable', BT.A_ENV_PREREQ_GAP: 'not_compilable', BT.A_AUTHOR_DEFINITION_GAP: 'author_definition_gap', BT.A_BATCH_USER_ABANDON: 'batch_user_abandon', BT.A_SPEC_CASE_CONFLICT: 'source_conflict', BT.A_SPEC_PRESENT_CASE_INCOMPLETE: 'source_conflict', BT.A_INCOMPLETE_CASE: 'source_conflict'}
    return _ABANDON_CREDENTIAL_LAYER
_SOURCE_CONFLICT_LANDINGS: dict[str, str] = {}

def _source_conflict_landings() -> dict[str, str]:
    global _SOURCE_CONFLICT_LANDINGS
    if not _SOURCE_CONFLICT_LANDINGS:
        from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
        _SOURCE_CONFLICT_LANDINGS = {BT.A_SPEC_CASE_CONFLICT: 'scenario1_spec_case_conflict', BT.A_SPEC_PRESENT_CASE_INCOMPLETE: 'scenario1_case_incomplete', BT.A_INCOMPLETE_CASE: 'scenario2_incomplete_case'}
    return _SOURCE_CONFLICT_LANDINGS
_SCENARIO1_EVIDENCE_FIELDS = ('spec_quote', 'case_quote', 'spec_locator', 'case_locator', 'incompatibility')

def _terminal_policy_abandon(aid: str, facts: list[dict]) -> dict:
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'policy_abandon' and str(fact.get('aid') or '') == aid and (str(fact.get('blocking_class') or '') in _source_conflict_landings())), {})

def _conflict_receipt_fact(aid: str, facts: list[dict]) -> dict:
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'consistency_verdict' and str(fact.get('aid') or '') == aid and (str(fact.get('verdict') or '') == 'conflict')), {})

def _build_source_conflict_credential(aid: str, facts: list[dict]) -> dict:
    fact = _terminal_policy_abandon(aid, facts)
    refs: dict = {'schema': SCHEMA, 'kind': 'source_conflict', 'blocking_class': str(fact.get('blocking_class') or ''), 'reason_code': str(fact.get('reason_code') or '')}
    if not fact:
        return refs
    refs['abandon_fact_sha256'] = _fact_sha256(fact)
    evidence = fact.get('scenario1_evidence')
    if isinstance(evidence, list):
        refs['scenario1_evidence'] = [{field: str(row.get(field) or '') for field in _SCENARIO1_EVIDENCE_FIELDS} for row in evidence if isinstance(row, dict)]
    missing = fact.get('missing_fields')
    if isinstance(missing, list):
        refs['missing_fields'] = [str(field) for field in missing]
    receipt = _conflict_receipt_fact(aid, facts)
    if receipt:
        refs['consistency_receipt'] = {'receipt_sha256': str(receipt.get('receipt_sha256') or ''), 'ledger_sha256': str(receipt.get('ledger_sha256') or ''), 'fact_sha256': _fact_sha256(receipt)}
    return refs

def _validate_source_conflict(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    errors: list[str] = []
    fact = _find_fact_by_sha(facts, aid=aid, ev='policy_abandon', expected_sha256=str(refs.get('abandon_fact_sha256') or ''))
    if not fact:
        return ['source_conflict_abandon_receipt_missing']
    blocking_class = str(fact.get('blocking_class') or '')
    reason_code = str(fact.get('reason_code') or '')
    landings = _source_conflict_landings()
    if fact.get('terminal') is not True or landings.get(blocking_class) != reason_code or refs.get('blocking_class') != blocking_class or (refs.get('reason_code') != reason_code):
        errors.append('source_conflict_landing_invalid')
    if reason_code == 'scenario1_spec_case_conflict':
        rows = fact.get('scenario1_evidence')
        rows = rows if isinstance(rows, list) else []
        expected = [{field: str(row.get(field) or '') for field in _SCENARIO1_EVIDENCE_FIELDS} for row in rows if isinstance(row, dict)]
        if not expected or any((not _is_nonempty_text(row[field]) for row in expected for field in ('spec_quote', 'case_quote', 'spec_locator', 'case_locator'))):
            errors.append('source_conflict_dual_quote_missing')
        if refs.get('scenario1_evidence') != expected:
            errors.append('source_conflict_binding_mismatch')
    elif reason_code == 'scenario1_case_incomplete':
        missing = fact.get('missing_fields')
        missing = [str(field) for field in missing] if isinstance(missing, list) else []
        from cex_core.engine.ist_core.compile_engine.questions import MISSING_FIELD_CN
        if not missing or any((field not in MISSING_FIELD_CN for field in missing)):
            errors.append('source_conflict_missing_fields_invalid')
        if refs.get('missing_fields') != missing:
            errors.append('source_conflict_binding_mismatch')
    receipt = _conflict_receipt_fact(aid, facts)
    bound = refs.get('consistency_receipt')
    bound = bound if isinstance(bound, dict) else {}
    if receipt:
        expected_receipt = {'receipt_sha256': str(receipt.get('receipt_sha256') or ''), 'ledger_sha256': str(receipt.get('ledger_sha256') or ''), 'fact_sha256': _fact_sha256(receipt)}
        if bound != expected_receipt or not _is_sha256(expected_receipt['receipt_sha256']):
            errors.append('source_conflict_receipt_mismatch')
    elif bound:
        errors.append('source_conflict_receipt_mismatch')
    return errors
_BATCH_ABANDON_REASON_CODE = 'batch_user_abandon'
_BATCH_RECEIPT_NAME = 'batch_conflict_decision.json'

def _safe_batch_component(value: Any) -> str:
    name = str(value or '').strip()
    if not name or name in {'.', '..'} or Path(name).is_absolute() or ('/' in name) or ('\\' in name) or ('~' in name) or any((ord(ch) < 32 for ch in name)) or (len(name) > 180):
        return ''
    return name

def _batch_receipt_path(case_dir: Path | None, out_name: str) -> Path | None:
    name = _safe_batch_component(out_name)
    if case_dir is None or not name:
        return None
    case = Path(case_dir)
    try:
        if not case.is_dir() or case.is_symlink() or case.parent.is_symlink():
            return None
        parent = case.parent
        if parent.name in {'unfinished', 'delivered'}:
            batch = parent.parent
            outputs = batch.parent
            if batch.name != name or batch.is_symlink():
                return None
        elif parent.name == name:
            batch = parent
            outputs = batch.parent
        else:
            outputs = parent
            batch = outputs / name
        if outputs.is_symlink() or batch.is_symlink() or batch.parent.resolve() != outputs.resolve():
            return None
        return batch / _BATCH_RECEIPT_NAME
    except OSError:
        return None

def _batch_policy_abandon_fact(aid: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'policy_abandon' and str(fact.get('aid') or '') == aid and (fact.get('blocking_class') == BT.A_BATCH_USER_ABANDON) and (fact.get('reason_code') == _BATCH_ABANDON_REASON_CODE)), {})

def _source_conflict_blocked_fact(aid: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine import nodes as N
    mine = [row for row in facts if str(row.get('aid') or '') == str(aid)]
    fact = N._effective_blocked_terminal_fact(mine)
    return fact if fact.get('ev') == 'source_conflict_blocked' else {}
_SOURCE_CONFLICT_BLOCKED_BOUND_FIELDS = ('question_id', 'mechanical_case_sha256', 'batch_receipt_sha256')

def _build_source_conflict_blocked_credential(aid: str, facts: list[dict]) -> dict:
    fact = _source_conflict_blocked_fact(aid, facts)
    refs: dict = {'schema': SCHEMA, 'kind': 'source_conflict_blocked'}
    if not fact:
        return refs
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_BINDING_FIELDS
    refs.update({'blocked_fact_sha256': _fact_sha256(fact), 'blocking_class': str(fact.get('blocking_class') or ''), 'question_id': str(fact.get('question_id') or ''), 'reason': str(fact.get('reason') or ''), 'mechanical_case_sha256': str(fact.get('mechanical_case_sha256') or ''), 'batch_receipt_sha256': str(fact.get('batch_receipt_sha256') or ''), **{field: str(fact.get(field) or '') for field in BATCH_BINDING_FIELDS}})
    return refs

def _validate_source_conflict_blocked(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_BINDING_FIELDS
    errors: list[str] = []
    fact = _source_conflict_blocked_fact(aid, facts)
    if not fact:
        return ['source_conflict_blocked_fact_missing']
    if str(refs.get('blocked_fact_sha256') or '') != _fact_sha256(fact):
        errors.append('source_conflict_blocked_fact_mismatch')
    if not _is_nonempty_text(refs.get('question_id')):
        errors.append('source_conflict_blocked_question_missing')
    if not re.fullmatch('[0-9a-f]{64}', str(refs.get('mechanical_case_sha256') or '')):
        errors.append('source_conflict_blocked_mechanical_case_missing')
    if not re.fullmatch('[0-9a-f]{64}', str(refs.get('batch_receipt_sha256') or '')):
        errors.append('source_conflict_blocked_receipt_missing')
    for field in BATCH_BINDING_FIELDS:
        if not re.fullmatch('[0-9a-f]{64}', str(refs.get(field) or '')):
            errors.append(f'source_conflict_blocked_binding_missing:{field}')
    for field in (*_SOURCE_CONFLICT_BLOCKED_BOUND_FIELDS, *BATCH_BINDING_FIELDS):
        if str(refs.get(field) or '') != str(fact.get(field) or ''):
            errors.append(f'source_conflict_blocked_field_mismatch:{field}')
    return sorted(set(errors))

def _build_batch_user_abandon_credential(aid: str, facts: list[dict], case_dir: Path | None) -> dict:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_BINDING_FIELDS
    fact = _batch_policy_abandon_fact(aid, facts)
    refs: dict = {'schema': SCHEMA, 'kind': 'batch_user_abandon', 'blocking_class': BT.A_BATCH_USER_ABANDON, 'reason_code': _BATCH_ABANDON_REASON_CODE}
    if not fact:
        return refs
    members = fact.get('batch_member_autoids')
    members = [str(value) for value in members] if isinstance(members, list) else []
    receipt_sha = str(fact.get('batch_receipt_sha256') or '')
    out_name = str(fact.get('out_name') or '')
    refs.update({'abandon_fact_sha256': _fact_sha256(fact), 'out_name': out_name, 'question_id': str(fact.get('question_id') or ''), 'batch_decision': str(fact.get('batch_decision') or ''), 'batch_receipt_sha256': receipt_sha, 'batch_member_autoids': members, **{field: str(fact.get(field) or '') for field in BATCH_BINDING_FIELDS}})
    by_aid: dict[str, dict] = {}
    for row in facts:
        member = str(row.get('aid') or '')
        if row.get('ev') == 'policy_abandon' and row.get('blocking_class') == BT.A_BATCH_USER_ABANDON and (row.get('reason_code') == _BATCH_ABANDON_REASON_CODE) and (row.get('out_name') == out_name) and (row.get('batch_receipt_sha256') == receipt_sha) and (member in members):
            by_aid[member] = row
    refs['policy_abandon_receipts'] = [{'aid': member, 'fact_sha256': _fact_sha256(by_aid[member])} for member in members if member in by_aid]
    receipt_path = _batch_receipt_path(case_dir, out_name)
    payload = _read_regular_file(receipt_path) if receipt_path else None
    if payload is not None:
        refs['batch_receipt'] = {'name': _BATCH_RECEIPT_NAME, 'bytes_sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}
    return refs

def _batch_receipt_contract_valid(receipt: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_ABANDON, BATCH_BINDING_FIELDS, batch_conflict_decision_is_current
    if receipt.get('commit_complete') is not True or receipt.get('decision') != BATCH_ABANDON:
        return False
    bindings = {field: str(receipt.get(field) or '') for field in BATCH_BINDING_FIELDS}
    conflict_ids = receipt.get('conflict_claim_ids')
    auto_ids = receipt.get('auto_case_claim_ids')
    conflicted = receipt.get('conflict_autoids')
    members = receipt.get('batch_member_autoids')
    if not batch_conflict_decision_is_current(receipt, bindings, conflict_claim_ids=conflict_ids, auto_case_claim_ids=auto_ids, conflict_autoids=conflicted, batch_member_autoids=members):
        return False
    if not set(conflicted) <= set(members):
        return False
    items = receipt.get('conflict_items')
    if not isinstance(items, list):
        return False
    normalized = [{'aid': str(item.get('aid') or ''), 'claim_id': str(item.get('claim_id') or ''), 'scenario': str(item.get('scenario') or '')} for item in items if isinstance(item, dict)]
    if len(normalized) != len(items) or normalized != sorted(normalized, key=lambda item: (item['aid'], item['claim_id'])) or any((item['aid'] not in conflicted or item['claim_id'] not in conflict_ids or item['scenario'] not in {'scenario_3', 'scenario_4'} for item in normalized)) or (len({item['claim_id'] for item in normalized}) != len(normalized)) or ({item['claim_id'] for item in normalized} != set(conflict_ids)) or ({item['aid'] for item in normalized} != set(conflicted)):
        return False
    return True

def _batch_policy_binding_valid(fact: dict, *, aid: str, receipt: dict, receipt_sha256: str, out_name: str) -> bool:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_ABANDON, BATCH_BINDING_FIELDS
    signer = receipt.get('signer')
    signer = signer if isinstance(signer, dict) else {}
    return fact.get('ev') == 'policy_abandon' and str(fact.get('aid') or '') == aid and (fact.get('blocking_class') == BT.A_BATCH_USER_ABANDON) and (fact.get('reason_code') == _BATCH_ABANDON_REASON_CODE) and (fact.get('terminal') is True) and (fact.get('batch_decision') == BATCH_ABANDON) and (fact.get('batch_receipt_sha256') == receipt_sha256) and (fact.get('out_name') == out_name) and (fact.get('question_id') == signer.get('question_id')) and (fact.get('batch_member_autoids') == receipt.get('batch_member_autoids')) and all((fact.get(field) == receipt.get(field) for field in BATCH_BINDING_FIELDS))

def _validate_batch_user_abandon(aid: str, refs: dict, facts: list[dict], case_dir: Path | None) -> list[str]:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_ABANDON, BATCH_BINDING_FIELDS
    errors: list[str] = []
    fact = _find_fact_by_sha(facts, aid=aid, ev='policy_abandon', expected_sha256=str(refs.get('abandon_fact_sha256') or ''))
    if not fact:
        return ['batch_user_abandon_policy_receipt_missing']
    out_name = str(fact.get('out_name') or '')
    receipt_path = _batch_receipt_path(case_dir, out_name)
    payload = _read_regular_file(receipt_path) if receipt_path else None
    if payload is None:
        return ['batch_user_abandon_batch_receipt_missing']
    actual_sha = hashlib.sha256(payload).hexdigest()
    bound_receipt = refs.get('batch_receipt')
    expected_receipt = {'name': _BATCH_RECEIPT_NAME, 'bytes_sha256': actual_sha, 'size': len(payload)}
    if bound_receipt != expected_receipt or refs.get('batch_receipt_sha256') != actual_sha or fact.get('batch_receipt_sha256') != actual_sha:
        errors.append('batch_user_abandon_batch_receipt_mismatch')
    try:
        receipt = json.loads(payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return sorted(set(errors + ['batch_user_abandon_batch_receipt_invalid']))
    if not isinstance(receipt, dict) or not _batch_receipt_contract_valid(receipt):
        return sorted(set(errors + ['batch_user_abandon_batch_receipt_invalid']))
    signer = receipt.get('signer')
    signer = signer if isinstance(signer, dict) else {}
    expected_refs = {'blocking_class': BT.A_BATCH_USER_ABANDON, 'reason_code': _BATCH_ABANDON_REASON_CODE, 'out_name': out_name, 'question_id': str(signer.get('question_id') or ''), 'batch_decision': BATCH_ABANDON, 'batch_receipt_sha256': actual_sha, 'batch_member_autoids': receipt.get('batch_member_autoids'), **{field: str(receipt.get(field) or '') for field in BATCH_BINDING_FIELDS}}
    if any((refs.get(key) != value for key, value in expected_refs.items())):
        errors.append('batch_user_abandon_binding_mismatch')
    if not _batch_policy_binding_valid(fact, aid=aid, receipt=receipt, receipt_sha256=actual_sha, out_name=out_name):
        errors.append('batch_user_abandon_policy_binding_mismatch')
    members = list(receipt['batch_member_autoids'])
    raw_policy_refs = refs.get('policy_abandon_receipts')
    policy_refs = raw_policy_refs if isinstance(raw_policy_refs, list) else []
    canonical_refs = [{'aid': str(item.get('aid') or ''), 'fact_sha256': str(item.get('fact_sha256') or '')} for item in policy_refs if isinstance(item, dict) and set(item) == {'aid', 'fact_sha256'}]
    if len(canonical_refs) != len(policy_refs) or canonical_refs != sorted(canonical_refs, key=lambda item: item['aid']) or [item['aid'] for item in canonical_refs] != members or (len({item['aid'] for item in canonical_refs}) != len(members)) or any((not _is_sha256(item['fact_sha256']) for item in canonical_refs)):
        errors.append('batch_user_abandon_manifest_policy_incomplete')
    for item in canonical_refs:
        member = item['aid']
        policy = _find_fact_by_sha(facts, aid=member, ev='policy_abandon', expected_sha256=item['fact_sha256'])
        if not policy:
            errors.append('batch_user_abandon_policy_receipt_missing')
            continue
        if not _batch_policy_binding_valid(policy, aid=member, receipt=receipt, receipt_sha256=actual_sha, out_name=out_name):
            errors.append('batch_user_abandon_policy_binding_mismatch')
    target_ref = next((item for item in canonical_refs if item['aid'] == aid), {})
    if target_ref.get('fact_sha256') != refs.get('abandon_fact_sha256'):
        errors.append('batch_user_abandon_policy_binding_mismatch')
    return errors

def _device_evidence_quotes(aid: str, run_id: str, attempt: dict, facts: list[dict], echo_text: str) -> list[str]:
    candidates: list[str] = []
    direct = attempt.get('verbatim_evidence')
    if isinstance(direct, list):
        candidates.extend((str(value) for value in direct))
    if _is_nonempty_text(attempt.get('evidence_quote')):
        candidates.append(str(attempt['evidence_quote']))
    candidates.extend((str(fact.get('evidence') or '') for fact in facts if fact.get('ev') == 'attribution' and str(fact.get('aid') or '') == aid and (str(fact.get('run_id') or '') == run_id) and (str(fact.get('source') or '') not in {'user', 'engine_auto'})))
    out: list[str] = []
    for candidate in candidates:
        quote = candidate.strip()
        if len(quote) < 8 or quote not in echo_text or quote in out:
            continue
        out.append(quote)
    return out

def _device_result(fact: dict) -> str:
    return str(fact.get('oracle_result') or fact.get('verdict') or fact.get('result') or '')

def _worker_device_attempt(aid: str, facts: list[dict], *, terminal_verdict: dict | None=None) -> dict:
    terminal = terminal_verdict if isinstance(terminal_verdict, dict) else {}
    terminal_run_id = str(terminal.get('run_id') or '')
    terminal_artifact = str(terminal.get('artifact') or '')
    terminal_result = str(terminal.get('result') or '')
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'worker_device_attempt' and str(fact.get('aid') or '') == aid and (_device_result(fact) in {'pass', 'fail'}) and (not terminal or (terminal_run_id and terminal_artifact and (terminal_result in {'pass', 'fail'}) and (str(fact.get('run_id') or '') == terminal_run_id) and (str(fact.get('artifact') or '') == terminal_artifact) and (_device_result(fact) == terminal_result)))), {})

def _central_delivery_verdict(aid: str, facts: list[dict]) -> dict:
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'verdict' and str(fact.get('aid') or '') == aid and (str(fact.get('ctx') or '') == 'delivery') and (str(fact.get('result') or '') in {'pass', 'fail'})), {})

def _attributed_central_device_verdict(aid: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine.facts import scenario5_device_defect, scenario5_device_run_evidence
    attribution = next((row for row in reversed(facts) if row.get('ev') == 'attribution' and str(row.get('aid') or '') == aid and scenario5_device_defect(row.get('layer'), row.get('disposition')) and (str(row.get('source') or '') not in {'user', 'engine_auto'})), {})
    run_id = str(attribution.get('run_id') or '')
    if not scenario5_device_run_evidence(facts, aid=aid, run_id=run_id):
        return {}
    return next((row for row in reversed(facts) if row.get('ev') == 'verdict' and str(row.get('aid') or '') == aid and (str(row.get('run_id') or '') == run_id) and (row.get('ctx') in _CENTRAL_DEVICE_CONTEXTS) and (row.get('result') in {'pass', 'fail'})), {})

def _delivery_evidence_corpus_text(verdict: dict) -> str:
    inline = verdict.get('evidence_inline')
    inline = inline if isinstance(inline, dict) else {}
    return '\n'.join((str(inline.get(key) or '') for key in ATTRIBUTION_EVIDENCE_CORPUS_FIELDS))

def _delivery_attribution(aid: str, run_id: str, facts: list[dict]) -> dict:
    return next((fact for fact in reversed(facts) if fact.get('ev') == 'attribution' and str(fact.get('aid') or '') == aid and (str(fact.get('run_id') or '') == run_id) and (str(fact.get('source') or '') not in {'user', 'engine_auto'})), {})

def _build_central_delivery_device_credential(aid: str, facts: list[dict], verdict: dict) -> dict:
    run_id = str(verdict.get('run_id') or '')
    attribution = _delivery_attribution(aid, run_id, facts)
    causality = _delivery_evidence_corpus_text(verdict)
    quote = str(attribution.get('evidence') or '').strip()
    refs: dict = {'schema': SCHEMA, 'kind': 'device', 'attempt_source': _CENTRAL_DEVICE_CONTEXTS[str(verdict.get('ctx') or '')], 'run_id': run_id, 'oracle_result': str(verdict.get('result') or ''), 'artifact': str(verdict.get('artifact') or ''), 'volume': str(verdict.get('volume') or ''), 'volume_artifact_sha256': str(verdict.get('volume_artifact_sha256') or ''), 'batch_run_id': str(verdict.get('batch_run_id') or ''), 'dispatch_id': str(verdict.get('dispatch_id') or ''), 'dispatch_scope': str(verdict.get('dispatch_scope') or ''), 'bed': str(verdict.get('bed') or ''), 'build': str(verdict.get('build') or ''), 'verdict_fact_sha256': _fact_sha256(verdict), 'terminal_verdict_fact_sha256': _fact_sha256(verdict), 'terminal_run_id': run_id, 'terminal_artifact': str(verdict.get('artifact') or ''), 'terminal_oracle_result': str(verdict.get('result') or ''), 'attribution_layer': str(attribution.get('layer') or ''), 'attribution_disposition': str(attribution.get('disposition') or '')}
    if attribution:
        refs['attribution_fact_sha256'] = _fact_sha256(attribution)
    if len(quote) >= 8 and quote in causality:
        refs['verbatim_evidence'] = [quote]
    return refs

def _build_device_credential(aid: str, facts: list[dict], case_dir: Path | None, *, outcome: str, delivery_verdict: dict | None) -> dict:
    refs: dict = {'schema': SCHEMA, 'kind': 'device'}
    terminal_verdict = _attributed_central_device_verdict(aid, facts) if outcome == 'device_defect' else delivery_verdict if isinstance(delivery_verdict, dict) and delivery_verdict else _central_delivery_verdict(aid, facts)
    attempt = _worker_device_attempt(aid, facts, terminal_verdict=terminal_verdict if outcome == 'device_defect' else None)
    if not attempt:
        verdict = terminal_verdict
        if not verdict:
            return refs
        return _build_central_delivery_device_credential(aid, facts, verdict)
    run_id = str(attempt.get('run_id') or '')
    refs.update({'attempt_source': 'worker_device_attempt', 'run_id': run_id, 'oracle_result': _device_result(attempt), 'artifact': str(attempt.get('artifact') or ''), 'artifact_sha256': str(attempt.get('artifact_sha256') or ''), 'remote_artifact_sha256': str(attempt.get('remote_artifact_sha256') or ''), 'lint_credential_id': str(attempt.get('lint_credential_id') or ''), 'dispatch_id': str(attempt.get('dispatch_id') or ''), 'batch_run_id': str(attempt.get('batch_run_id') or ''), 'bed_lease_id': str(attempt.get('bed_lease_id') or ''), 'env_id': str(attempt.get('env_id') or ''), 'bed': str(attempt.get('bed') or ''), 'build': str(attempt.get('build') or ''), 'module': str(attempt.get('module') or ''), 'lease_acquired_persisted': attempt.get('lease_acquired_persisted') is True, 'lease_released_persisted': attempt.get('lease_released_persisted') is True, 'attempt_fact_sha256': _fact_sha256(attempt)})
    if outcome == 'device_defect' and terminal_verdict:
        refs.update({'terminal_verdict_fact_sha256': _fact_sha256(terminal_verdict), 'terminal_run_id': str(terminal_verdict.get('run_id') or ''), 'terminal_artifact': str(terminal_verdict.get('artifact') or ''), 'terminal_oracle_result': str(terminal_verdict.get('result') or '')})
    if case_dir is None:
        return refs
    echo_name = Path(str(attempt.get('echo_path') or '')).name
    if not _ECHO_NAME_RE.fullmatch(echo_name):
        return refs
    echo_payload = _read_case_file(case_dir, echo_name)
    if echo_payload is None:
        return refs
    try:
        echo_text = echo_payload.decode('utf-8')
    except UnicodeDecodeError:
        return refs
    evidence_surface = scrub_text(echo_text, scrub_paths=False)
    refs['echo_receipt'] = {'name': echo_name, 'bytes_sha256': hashlib.sha256(echo_payload).hexdigest(), 'size': len(echo_payload), 'evidence_surface_sha256': hashlib.sha256(evidence_surface.encode('utf-8')).hexdigest()}
    refs['verbatim_evidence'] = _device_evidence_quotes(aid, run_id, attempt, facts, evidence_surface)
    return refs

def _build_delivery_credential(delivery_verdict: dict | None, *, aid: str, facts: list[dict], artifact: str) -> dict:
    verdict = delivery_verdict if isinstance(delivery_verdict, dict) else {}
    authored = next((fact for fact in reversed(facts) if fact.get('ev') == 'authored' and str(fact.get('aid') or '') == aid and (str(fact.get('artifact') or '') == artifact)), {})
    refs = {'schema': SCHEMA, 'kind': 'delivery', 'artifact': artifact, 'delivery_run_id': str(verdict.get('run_id') or ''), 'volume': str(verdict.get('volume') or ''), 'volume_artifact_sha256': str(verdict.get('volume_artifact_sha256') or ''), 'mechanical_case_sha256': str(authored.get('from_mechanical_case_sha256') or ''), 'consistency_contract_sha256': authored.get('from_consistency_contract_sha256')}
    if verdict:
        refs['verdict_fact_sha256'] = _fact_sha256(verdict)
    if authored:
        refs['authored_fact_sha256'] = _fact_sha256(authored)
    return refs

def _build_delivery_failure_credential(volume_identity_fact: dict | None) -> dict:
    """收口卷面失败事实 → 凭据。一枚凭据服务两个位域：签在引擎账上（`ist_core_defect`）
    与签在待裁那一格（`blocked`，内部工单）**载荷同构**，格由成因前缀表判、由校验侧复核。
    """
    fact = volume_identity_fact if isinstance(volume_identity_fact, dict) else {}
    refs = {'schema': SCHEMA, 'kind': 'delivery_failure', 'run_id': str(fact.get('run_id') or ''), 'volume': str(fact.get('volume') or ''), 'expected_artifact_sha256': str(fact.get('expected_artifact_sha256') or ''), 'observed_artifact_sha256': str(fact.get('observed_artifact_sha256') or ''), 'reasons': [str(value) for value in fact.get('reasons') or [] if str(value)]}
    if fact:
        refs['identity_fact_sha256'] = _fact_sha256(fact)
    return refs

def _build_authority_decision_credential(aid: str, facts: list[dict]) -> dict:
    terminal = next((fact for fact in reversed(facts) if fact.get('aid') == aid and fact.get('ev') == 'blocked' and (fact.get('terminal_layer') == 'delivery') and (fact.get('reason_code') == 'authority_needs_decision')), {})
    refs = {'schema': SCHEMA, 'kind': 'authority_decision', 'round': terminal.get('round'), 'source_event': terminal.get('source_event'), 'source_fact_sha256': terminal.get('source_fact_sha256')}
    if terminal:
        refs['terminal_fact_sha256'] = _fact_sha256(terminal)
    return refs

def _build_engine_defect_credential(aid: str, facts: list[dict]) -> dict:
    terminal = next((fact for fact in reversed(facts) if fact.get('ev') == 'ist_core_defect' and str(fact.get('aid') or '') == aid and (str(fact.get('terminal_layer') or '') == 'engine')), {})
    refs = {'schema': SCHEMA, 'kind': 'engine_defect', 'reason_code': str(terminal.get('reason_code') or ''), 'round': terminal.get('round'), 'source_event': str(terminal.get('source_event') or ''), 'source_fact_sha256': str(terminal.get('source_fact_sha256') or '')}
    if terminal:
        refs['terminal_fact_sha256'] = _fact_sha256(terminal)
    return refs

def _build_unattributed_stop_credential(aid: str, facts: list[dict]) -> dict:
    """编写侧停点核不出责任那一格的凭据。

    与 `engine_defect` 那一枚**不合并**：载荷多一个 `stop_cause`，校验侧要复核它在
    闭集里、且这条成因确实判在中性那一格上。合并会让「已核实在引擎」与「谁的责任都
    没核出来」共用同一枚凭据，翻位域就失配（内部工单 同一个病）。
    """
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import UNATTRIBUTED_LAYER
    terminal = next((fact for fact in reversed(facts) if fact.get('ev') == 'blocked' and str(fact.get('aid') or '') == aid and (str(fact.get('terminal_layer') or '') == UNATTRIBUTED_LAYER)), {})
    refs = {'schema': SCHEMA, 'kind': 'unattributed_stop', 'reason_code': str(terminal.get('reason_code') or ''), 'stop_cause': str(terminal.get('stop_cause') or ''), 'round': terminal.get('round'), 'source_event': str(terminal.get('source_event') or ''), 'source_fact_sha256': str(terminal.get('source_fact_sha256') or '')}
    if terminal:
        refs['terminal_fact_sha256'] = _fact_sha256(terminal)
    return refs

def _build_execution_failure_credential(aid: str, outcome: str, facts: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine.execution_failure import is_runtime_infrastructure_terminal_fact
    terminal = next((fact for fact in reversed(facts) if str(fact.get('aid') or '') == aid and (outcome == 'blocked' and is_runtime_infrastructure_terminal_fact(fact) or fact.get('ev') == outcome)), {})
    terminal_event = str(terminal.get('ev') or '')
    identity = {'artifact_sha256': str(terminal.get('artifact_sha256') or ''), 'bed_host': str(terminal.get('bed_host') or ''), 'build': str(terminal.get('build') or ''), 'implementation_sha256': str(terminal.get('implementation_sha256') or '')}
    failure = next((fact for fact in reversed(facts) if fact.get('ev') == 'execution_failure' and str(fact.get('aid') or '') == aid and (fact.get('attempt') == terminal.get('attempt')) and (str(fact.get('action') or '') == terminal_event) and all((str(fact.get(key) or '') == value for key, value in identity.items()))), {})
    refs = {'schema': SCHEMA, 'kind': 'execution_failure', 'event': terminal_event, 'reason_code': str(terminal.get('reason_code') or ''), 'category': str(terminal.get('category') or ''), 'attempt': terminal.get('attempt'), 'prerequisite_receipt_sha256': str(terminal.get('prerequisite_receipt_sha256') or ''), **identity}
    if terminal:
        refs['terminal_fact_sha256'] = _fact_sha256(terminal)
    if failure:
        refs['failure_fact_sha256'] = _fact_sha256(failure)
    return refs

def build_terminal_credential(*, aid: str, outcome: str, preferred_layer: str, facts: Iterable[dict], case_dir: Path | None=None, artifact: str='', delivery_verdict: dict | None=None, volume_identity_fact: dict | None=None) -> dict:
    rows = [fact for fact in facts if isinstance(fact, dict)]
    layer = str(preferred_layer or '')
    if outcome == 'blocked' and layer == 'delivery':
        from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import is_authority_unverified_block
        block = next((fact for fact in reversed(rows) if str(fact.get('aid') or '') == aid and fact.get('ev') == 'blocked' and (str(fact.get('terminal_layer') or '') == 'delivery')), {})
        if is_authority_unverified_block(block):
            return _build_delivery_failure_credential(volume_identity_fact)
        return _build_authority_decision_credential(aid, rows)
    if outcome == 'delivered':
        return _build_delivery_credential(delivery_verdict, aid=aid, facts=rows, artifact=artifact)
    if layer == 'delivery':
        return _build_delivery_failure_credential(volume_identity_fact)
    if layer == 'engine':
        return _build_engine_defect_credential(aid, rows)
    if layer == _TO_UNATTRIBUTED_LAYER:
        return _build_unattributed_stop_credential(aid, rows)
    if layer == 'ought':
        return _build_ought_credential(aid, rows, case_dir)
    if layer == 'suspension':
        return _build_suspension_credential(aid, rows)
    if layer == 'device':
        return _build_device_credential(aid, rows, case_dir, outcome=outcome, delivery_verdict=delivery_verdict)
    if layer == 'unsupported_feature':
        return _build_unsupported_feature_credential(aid, rows)
    if layer == 'not_compilable':
        return _build_not_compilable_credential(aid, rows)
    if layer == 'source_conflict':
        return _build_source_conflict_credential(aid, rows)
    if layer == 'source_conflict_blocked':
        return _build_source_conflict_blocked_credential(aid, rows)
    if layer == 'batch_user_abandon':
        return _build_batch_user_abandon_credential(aid, rows, case_dir)
    if layer == 'round_cap':
        return _build_round_cap_credential(aid, rows)
    if layer == 'authoring':
        return _build_authoring_failure_credential(aid, rows)
    if layer == 'author_definition_gap':
        return _build_author_definition_gap_credential(aid, rows)
    if layer == 'xml_absence':
        return _build_xml_absence_credential(aid, rows)
    if layer == 'execution':
        return _build_execution_failure_credential(aid, outcome, rows)
    return _build_compile_credential(aid, rows)

def _find_fact_by_sha(facts: Iterable[dict], *, ev: str | frozenset[str] | set[str], aid: str, expected_sha256: str) -> dict:
    """按 (aid, ev, 事实指纹) 反查凭据所指的那一条事实。

    唯一定位靠 ``expected_sha256``，``ev`` 只是过滤条件——所以允许传一个名字闭集：
    同一族事件按轴拆名之后，旧账里的旧名事实仍要按 sha 查得出来。
    """
    names = {ev} if isinstance(ev, str) else set(ev)
    return next((fact for fact in facts if isinstance(fact, dict) and fact.get('ev') in names and (str(fact.get('aid') or '') == aid) and (_fact_sha256(fact) == expected_sha256)), {})

def _validate_ought(aid: str, refs: dict, facts: list[dict], case_dir: Path | None) -> list[str]:
    errors: list[str] = []
    qid = str(refs.get('question_id') or '')
    question_sha = str(refs.get('question_fact_sha256') or '')
    question = _find_fact_by_sha(facts, aid=aid, ev='needs_decision', expected_sha256=question_sha)
    if not qid or not question or str(question.get('question_id') or '') != qid or any((_decision_resolves_question(fact) and str(fact.get('aid') or '') == aid and (str(fact.get('question_id') or '') == qid) for fact in facts)):
        errors.append('ought_latest_unanswered_question_missing')
    receipt = refs.get('ledger_receipt')
    receipt = receipt if isinstance(receipt, dict) else {}
    if case_dir is None:
        errors.append('ought_ledger_unavailable')
        payload = None
    else:
        payload = _read_case_file(case_dir, 'needs_decision.json')
        if payload is None:
            errors.append('ought_ledger_unavailable')
    if payload is not None and (not _is_sha256(receipt.get('bytes_sha256')) or hashlib.sha256(payload).hexdigest() != str(receipt.get('bytes_sha256') or '') or len(payload) != receipt.get('size')):
        errors.append('ought_ledger_bytes_mismatch')
    claims = refs.get('claims')
    claims = claims if isinstance(claims, list) else []
    structured = _structured_claims(claims)
    receipts = refs.get('claim_receipts')
    receipts = receipts if isinstance(receipts, list) else []
    if not structured or len(structured) != len(claims):
        errors.append('ought_structured_claim_missing')
    expected_receipts = [{'claim_kind': str(claim.get('claim_kind') or ''), 'claim_sha256': _object_sha256(claim), 'source_quote_sha256': [hashlib.sha256(str(source.get('quote') or '').encode('utf-8')).hexdigest() for source in claim.get('sources') or []]} for claim in structured]
    if receipts != expected_receipts:
        errors.append('ought_claim_receipt_mismatch')
    if payload is not None:
        try:
            ledger = json.loads(payload.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            ledger = None
        persisted_ledger_claims = _structured_claims(canonical_persisted_value(_structured_claims(ledger.get('claims')))) if isinstance(ledger, dict) else []
        if not isinstance(ledger, dict) or persisted_ledger_claims != claims:
            errors.append('ought_claim_not_bound_to_ledger')
    return errors

def _validate_compile(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    errors: list[str] = []
    decision = _find_fact_by_sha(facts, aid=aid, ev='no_progress_decision', expected_sha256=str(refs.get('decision_fact_sha256') or ''))
    if not decision or str(decision.get('decision_id') or '') != str(refs.get('decision_id') or ''):
        errors.append('compile_decision_receipt_missing')
        return errors
    expected = {'domain': str(decision.get('domain') or ''), 'failure_key': str(decision.get('failure_key') or ''), 'streak': decision.get('streak'), 'threshold': decision.get('threshold'), 'revision_refs': list(decision.get('revision_refs') or []), 'stop': decision.get('stop')}
    observed = {key: refs.get(key) for key in expected}
    if expected['domain'] != 'compile' or expected['stop'] is not True or (not _is_nonempty_text(expected['failure_key'])) or (not expected['revision_refs']) or (observed != expected):
        errors.append('compile_no_progress_decision_invalid')
    return errors

def _validate_suspension(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    fact = _find_fact_by_sha(facts, aid=aid, ev='suspended', expected_sha256=str(refs.get('suspension_fact_sha256') or ''))
    active = _active_suspension_fact(aid, facts)
    if not fact or not active or _fact_sha256(active) != _fact_sha256(fact):
        return ['suspension_active_receipt_missing']
    errors: list[str] = []
    expected_reason = str(fact.get('reason') or '')
    expected_question_id = str(fact.get('question_id') or '')
    if not _is_nonempty_text(expected_reason):
        errors.append('suspension_reason_missing')
    if str(refs.get('reason') or '') != expected_reason or str(refs.get('question_id') or '') != expected_question_id:
        errors.append('suspension_binding_mismatch')
    if fact.get('suspension_kind') == 'execution_pause':
        if fact.get('source') != 'engine_auto':
            errors.append('execution_pause_issuer_invalid')
        fields = ('suspension_kind', 'pause_kind', 'basis_status', 'source_fact_sha256', 'source_event', 'source_run_id', 'evidence', 'fix_direction')
        if any((refs.get(key) != fact.get(key) for key in fields)):
            errors.append('execution_pause_binding_mismatch')
        from cex_core.engine.ist_core.compile_engine.forced_closure import PAUSE_CREDENTIAL_KINDS as _PAUSE_KINDS
        if fact.get('pause_kind') not in _PAUSE_KINDS:
            errors.append('execution_pause_kind_invalid')
        if fact.get('basis_status') == 'source_bound':
            source = _find_fact_by_sha(facts, aid=aid, ev=str(fact.get('source_event') or ''), expected_sha256=str(fact.get('source_fact_sha256') or ''))
            if not source:
                errors.append('execution_pause_source_missing')
            elif not (fact.get('pause_kind') == 'env' and source.get('ev') == 'attribution' and (source.get('disposition') == 'env_blocked') or (fact.get('pause_kind') == 'bed' and source.get('ev') == 'diagnosis' and str(source.get('h_position') or '').startswith('h_s0')) or (fact.get('pause_kind') == 'contra' and source.get('ev') == 'verdict') or (fact.get('pause_kind') == 'api' and source.get('ev') in {'escalated', 'worker_loop_outcome', 'engine_error'})):
                errors.append('execution_pause_source_kind_mismatch')
            elif fact.get('pause_kind') != 'api' and (str(source.get('run_id') or '') != fact.get('source_run_id') or str(source.get('evidence') or source.get('reason') or source.get('basis') or '') != fact.get('evidence') or str(source.get('fix_direction') or '') != fact.get('fix_direction')):
                errors.append('execution_pause_source_mismatch')
        elif fact.get('basis_status') != 'source_unavailable' or fact.get('source_fact_sha256') or fact.get('evidence'):
            errors.append('execution_pause_source_status_invalid')
    return errors

def _validate_round_cap(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    from cex_core.engine.ist_core.compile_engine import _shared as shared
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.compile_engine import facts as fact_rules
    from cex_core.engine.ist_core.compile_engine import views
    from cex_core.engine.ist_core.compile_engine.conflict_chain import ReentryAction, reduce_blocked_reentry
    expected_policy_sha = str(refs.get('abandon_fact_sha256') or '')
    policy_index = next((index for index in range(len(facts) - 1, -1, -1) if facts[index].get('ev') == 'policy_abandon' and str(facts[index].get('aid') or '') == aid and (_fact_sha256(facts[index]) == expected_policy_sha)), -1)
    if policy_index < 0:
        return ['round_cap_policy_receipt_missing']
    policy = facts[policy_index]
    prefix = facts[:policy_index]
    errors: list[str] = []
    if policy.get('blocking_class') != BT.A_ROUND_CAP or policy.get('reason_code') != _ROUND_CAP_REASON_CODE or policy.get('terminal') is not True or (policy.get('round_cap_receipt_schema') != ROUND_CAP_RECEIPT_SCHEMA):
        errors.append('round_cap_policy_contract_mismatch')
    expected_refs = {field: policy.get(field) for field in _ROUND_CAP_RECEIPT_FIELDS}
    if any((refs.get(field) != value for field, value in expected_refs.items())):
        errors.append('round_cap_binding_mismatch')
    material = _round_cap_receipt_material(policy)
    if not _is_sha256(policy.get('round_cap_receipt_sha256')) or persisted_surface_sha256(material) != policy.get('round_cap_receipt_sha256'):
        errors.append('round_cap_receipt_hash_mismatch')
    source_sha = str(policy.get('source_block_fact_sha256') or '')
    source_event = str(policy.get('source_block_event') or '')
    source_index = next((index for index in range(len(prefix) - 1, -1, -1) if prefix[index].get('ev') == source_event and str(prefix[index].get('aid') or '') == aid and (_fact_sha256(prefix[index]) == source_sha)), -1)
    if source_index < 0 or source_event not in _ROUND_CAP_BLOCK_EVENTS:
        errors.append('round_cap_source_block_receipt_missing')
        return errors
    latest_block_index = max((index for index, fact in enumerate(prefix) if str(fact.get('aid') or '') == aid and fact.get('ev') in _ROUND_CAP_BLOCK_EVENTS), default=-1)
    if latest_block_index != source_index or views.case_abandoned([fact for fact in prefix if str(fact.get('aid') or '') == aid]):
        errors.append('round_cap_source_block_not_active')
    source = prefix[source_index]
    from cex_core.engine.ist_core.compile_engine.authoring_stops import unconfirmed_processing_end
    if unconfirmed_processing_end(source):
        errors.append('round_cap_processing_responsibility_unconfirmed')
        return errors
    raw_block_round = source.get('round', 0)
    if type(raw_block_round) is not int or raw_block_round < 0:
        errors.append('round_cap_counter_invalid')
        return errors
    released = any((fact.get('ev') == 'conflict_chain_reentered' and str(fact.get('aid') or '') == aid and (type(fact.get('round')) is int) and (int(fact['round']) > raw_block_round) for fact in prefix[source_index + 1:]))
    if released:
        errors.append('round_cap_source_block_not_active')
    prior_reentry_round = max((int(fact['round']) for fact in prefix if str(fact.get('aid') or '') == aid and fact.get('ev') == 'conflict_chain_reentered' and (type(fact.get('round')) is int) and (int(fact['round']) >= 0)), default=0)
    expected_rounds = max(raw_block_round, prior_reentry_round, fact_rules.effective_rounds_used(prefix, aid))
    expected_granted = shared.granted_rounds(prefix, aid)
    base_max = policy.get('base_max_rounds')
    if type(base_max) is not int or base_max <= 0:
        errors.append('round_cap_counter_invalid')
        return errors
    effective_max = base_max + expected_granted
    if policy.get('rounds_used') != expected_rounds or policy.get('granted_rounds') != expected_granted or policy.get('effective_max_rounds') != effective_max:
        errors.append('round_cap_counter_mismatch')
    reduction = reduce_blocked_reentry(rounds_used=expected_rounds, max_rounds=effective_max)
    if not reduction.valid or reduction.action is not ReentryAction.ABANDON or reduction.reason != 'round_cap_reached':
        errors.append('round_cap_reduction_not_abandon')
    return errors

def _validate_xml_absence(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    fact = _find_fact_by_sha(facts, aid=aid, ev='xml_absence_terminal', expected_sha256=str(refs.get('terminal_fact_sha256') or ''))
    if not fact:
        return ['xml_absence_terminal_receipt_missing']
    errors: list[str] = []
    claims = fact.get('claims')
    vetoes = _xml_absence_veto_claims(claims)
    valid_vetoes = [claim for claim in vetoes if _is_nonempty_text(claim.get('command')) and _is_nonempty_text(claim.get('reason')) and isinstance(claim.get('xml_basis'), dict) and _is_nonempty_text(claim['xml_basis'].get('build')) and _is_nonempty_text(claim['xml_basis'].get('source_filename')) and _is_sha256(claim['xml_basis'].get('source_sha256'))]
    if fact.get('blocking_class') != 'manual_error_confirmed' or fact.get('xml_absence_receipt_schema') != XML_ABSENCE_RECEIPT_SCHEMA or (not isinstance(claims, list)) or (not vetoes) or (len(valid_vetoes) != len(vetoes)) or (str(fact.get('reason') or '') != str((vetoes[0] if vetoes else {}).get('reason') or '设备 XML 命令树未收录该命令，设备不支持这个功能')):
        errors.append('xml_absence_veto_contract_invalid')
    expected_claims_sha = persisted_surface_sha256(claims) if isinstance(claims, list) else ''
    expected_veto_hashes = [persisted_surface_sha256(claim) for claim in vetoes]
    if fact.get('claims_sha256') != expected_claims_sha or fact.get('veto_claim_sha256s') != expected_veto_hashes:
        errors.append('xml_absence_claim_receipt_mismatch')
    material = _xml_absence_receipt_material(fact)
    if not _is_sha256(fact.get('xml_absence_receipt_sha256')) or persisted_surface_sha256(material) != fact.get('xml_absence_receipt_sha256'):
        errors.append('xml_absence_receipt_hash_mismatch')
    expected_refs = {field: fact.get(field) for field in _XML_ABSENCE_RECEIPT_FIELDS}
    if any((refs.get(field) != value for field, value in expected_refs.items())):
        errors.append('xml_absence_binding_mismatch')
    return errors

def _validate_central_delivery_device(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    errors: list[str] = []
    verdict = _find_fact_by_sha(facts, aid=aid, ev='verdict', expected_sha256=str(refs.get('verdict_fact_sha256') or ''))
    if not verdict or str(verdict.get('ctx') or '') not in _CENTRAL_DEVICE_CONTEXTS:
        return ['device_delivery_verdict_receipt_missing']
    expected_source = _CENTRAL_DEVICE_CONTEXTS[str(verdict['ctx'])]
    if refs.get('attempt_source') != expected_source or verdict.get('dispatch_scope') != expected_source:
        errors.append('device_attempt_source_mismatch')
    run_id = str(verdict.get('run_id') or '')
    required_equal = {'run_id': run_id, 'oracle_result': str(verdict.get('result') or ''), 'artifact': str(verdict.get('artifact') or ''), 'volume': str(verdict.get('volume') or ''), 'volume_artifact_sha256': str(verdict.get('volume_artifact_sha256') or ''), 'batch_run_id': str(verdict.get('batch_run_id') or ''), 'dispatch_id': str(verdict.get('dispatch_id') or ''), 'dispatch_scope': str(verdict.get('dispatch_scope') or ''), 'bed': str(verdict.get('bed') or ''), 'build': str(verdict.get('build') or '')}
    terminal_binding = {'terminal_verdict_fact_sha256': _fact_sha256(verdict), 'terminal_run_id': run_id, 'terminal_artifact': str(verdict.get('artifact') or ''), 'terminal_oracle_result': str(verdict.get('result') or '')}
    if any((not _is_nonempty_text(value) for key, value in required_equal.items() if key != 'volume_artifact_sha256')) or not _is_sha256(required_equal['volume_artifact_sha256']):
        errors.append('device_attempt_identity_incomplete')
    if required_equal['oracle_result'] not in {'pass', 'fail'}:
        errors.append('device_delivery_verdict_inconclusive')
    if any((refs.get(key) != value for key, value in required_equal.items())):
        errors.append('device_attempt_binding_mismatch')
    if any((refs.get(key) != value for key, value in terminal_binding.items())):
        errors.append('device_terminal_binding_mismatch')
    attribution = _find_fact_by_sha(facts, aid=aid, ev='attribution', expected_sha256=str(refs.get('attribution_fact_sha256') or ''))
    if not attribution or str(attribution.get('run_id') or '') != run_id or str(attribution.get('source') or '') in {'user', 'engine_auto'} or (refs.get('attribution_layer') != str(attribution.get('layer') or '')) or (refs.get('attribution_disposition') != str(attribution.get('disposition') or '')):
        errors.append('device_attribution_receipt_missing')
        attribution = {}
    elif str(attribution.get('layer') or '') != 'product_defect':
        errors.append('device_attribution_layer_mismatch')
    causality = _delivery_evidence_corpus_text(verdict)
    quotes = refs.get('verbatim_evidence')
    quotes = quotes if isinstance(quotes, list) else []
    if not quotes or any((not isinstance(quote, str) or len(quote.strip()) < 8 or quote.strip() not in causality for quote in quotes)) or (attribution and str(attribution.get('evidence') or '').strip() not in [str(quote).strip() for quote in quotes]):
        errors.append('device_verbatim_evidence_missing')
    return errors

def _validate_device(aid: str, refs: dict, facts: list[dict], case_dir: Path | None, *, outcome: str) -> list[str]:
    errors: list[str] = []
    terminal_verdict: dict = {}
    if outcome == 'device_defect':
        terminal_verdict = _find_fact_by_sha(facts, aid=aid, ev='verdict', expected_sha256=str(refs.get('terminal_verdict_fact_sha256') or refs.get('verdict_fact_sha256') or ''))
        if not terminal_verdict or str(terminal_verdict.get('ctx') or '') not in _CENTRAL_DEVICE_CONTEXTS or str(terminal_verdict.get('result') or '') not in {'pass', 'fail'}:
            return ['device_terminal_verdict_receipt_missing']
        selected_terminal = _attributed_central_device_verdict(aid, facts)
        if not selected_terminal or _fact_sha256(selected_terminal) != _fact_sha256(terminal_verdict):
            return ['device_terminal_binding_mismatch']
    selected_attempt = _worker_device_attempt(aid, facts, terminal_verdict=terminal_verdict if outcome == 'device_defect' else None)
    source = 'worker_device_attempt' if selected_attempt else _CENTRAL_DEVICE_CONTEXTS.get(str(terminal_verdict.get('ctx') or ''), 'central_delivery')
    if str(refs.get('attempt_source') or 'worker_device_attempt') != source:
        return ['device_attempt_source_mismatch']
    if source in _CENTRAL_DEVICE_CONTEXTS.values():
        return _validate_central_delivery_device(aid, refs, facts)
    attempt = _find_fact_by_sha(facts, aid=aid, ev='worker_device_attempt', expected_sha256=str(refs.get('attempt_fact_sha256') or ''))
    if not attempt:
        errors.append('device_attempt_receipt_missing')
        return errors
    if _fact_sha256(attempt) != _fact_sha256(selected_attempt):
        errors.append('device_attempt_source_mismatch')
    required_equal = {'run_id': str(attempt.get('run_id') or ''), 'oracle_result': str(attempt.get('oracle_result') or attempt.get('verdict') or attempt.get('result') or ''), 'artifact': str(attempt.get('artifact') or ''), 'artifact_sha256': str(attempt.get('artifact_sha256') or ''), 'remote_artifact_sha256': str(attempt.get('remote_artifact_sha256') or ''), 'lint_credential_id': str(attempt.get('lint_credential_id') or ''), 'dispatch_id': str(attempt.get('dispatch_id') or ''), 'batch_run_id': str(attempt.get('batch_run_id') or ''), 'bed_lease_id': str(attempt.get('bed_lease_id') or ''), 'env_id': str(attempt.get('env_id') or ''), 'bed': str(attempt.get('bed') or ''), 'build': str(attempt.get('build') or ''), 'module': str(attempt.get('module') or ''), 'lease_acquired_persisted': attempt.get('lease_acquired_persisted') is True, 'lease_released_persisted': attempt.get('lease_released_persisted') is True}
    if any((not _is_nonempty_text(value) for key, value in required_equal.items() if key not in {'artifact_sha256', 'remote_artifact_sha256', 'lease_acquired_persisted', 'lease_released_persisted'})) or not _is_sha256(required_equal['artifact_sha256']) or (not _is_sha256(required_equal['remote_artifact_sha256'])):
        errors.append('device_attempt_identity_incomplete')
    if required_equal['oracle_result'] not in {'pass', 'fail'}:
        errors.append('device_worker_verdict_inconclusive')
    if outcome == 'device_defect':
        terminal_binding = {'terminal_verdict_fact_sha256': _fact_sha256(terminal_verdict), 'terminal_run_id': str(terminal_verdict.get('run_id') or ''), 'terminal_artifact': str(terminal_verdict.get('artifact') or ''), 'terminal_oracle_result': str(terminal_verdict.get('result') or '')}
        if any((refs.get(key) != value for key, value in terminal_binding.items())) or required_equal['run_id'] != terminal_binding['terminal_run_id'] or required_equal['artifact'] != terminal_binding['terminal_artifact'] or (required_equal['oracle_result'] != terminal_binding['terminal_oracle_result']):
            errors.append('device_terminal_binding_mismatch')
    if required_equal['artifact_sha256'] != required_equal['remote_artifact_sha256']:
        errors.append('device_remote_artifact_mismatch')
    if required_equal['lease_acquired_persisted'] is not True or required_equal['lease_released_persisted'] is not True:
        errors.append('device_lease_lifecycle_incomplete')
    if attempt.get('credential_valid') is False:
        errors.append('device_attempt_identity_rejected')
    if any((refs.get(key) != value for key, value in required_equal.items())):
        errors.append('device_attempt_binding_mismatch')
    receipt = refs.get('echo_receipt')
    receipt = receipt if isinstance(receipt, dict) else {}
    name = str(receipt.get('name') or '')
    payload = _read_case_file(case_dir, name) if case_dir is not None and _ECHO_NAME_RE.fullmatch(name) else None
    evidence_surface = ''
    if payload is None:
        errors.append('device_echo_unavailable')
        echo_text = ''
    else:
        try:
            echo_text = payload.decode('utf-8')
        except UnicodeDecodeError:
            echo_text = ''
            errors.append('device_echo_unavailable')
        evidence_surface = scrub_text(echo_text, scrub_paths=False)
        if not _is_sha256(receipt.get('bytes_sha256')) or hashlib.sha256(payload).hexdigest() != str(receipt.get('bytes_sha256') or '') or len(payload) != receipt.get('size'):
            errors.append('device_echo_bytes_mismatch')
        if not _is_sha256(receipt.get('evidence_surface_sha256')) or hashlib.sha256(evidence_surface.encode('utf-8')).hexdigest() != str(receipt.get('evidence_surface_sha256') or ''):
            errors.append('device_echo_evidence_surface_mismatch')
    quotes = refs.get('verbatim_evidence')
    quotes = quotes if isinstance(quotes, list) else []
    if not quotes or any((not isinstance(quote, str) or len(quote.strip()) < 8 or quote.strip() not in evidence_surface for quote in quotes)):
        errors.append('device_verbatim_evidence_missing')
    return errors

def _validate_delivery(aid: str, refs: dict, facts: list[dict], case_dir: Path | None) -> list[str]:
    errors: list[str] = []
    required = ('artifact', 'delivery_run_id', 'volume', 'volume_artifact_sha256')
    if any((not _is_nonempty_text(refs.get(key)) for key in required[:-1])):
        errors.append('delivery_identity_incomplete')
    if not _is_sha256(refs.get('volume_artifact_sha256')):
        errors.append('delivery_volume_sha_invalid')
    verdict = _find_fact_by_sha(facts, aid=aid, ev='verdict', expected_sha256=str(refs.get('verdict_fact_sha256') or ''))
    if not verdict:
        errors.append('delivery_verdict_receipt_missing')
    elif not (verdict.get('ctx') == 'delivery' and verdict.get('result') == 'pass' and (str(verdict.get('run_id') or '') == refs.get('delivery_run_id')) and (str(verdict.get('artifact') or '') == refs.get('artifact')) and (str(verdict.get('volume') or '') == refs.get('volume')) and (str(verdict.get('volume_artifact_sha256') or '') == refs.get('volume_artifact_sha256'))):
        errors.append('delivery_verdict_binding_mismatch')
    authored = _find_fact_by_sha(facts, aid=aid, ev='authored', expected_sha256=str(refs.get('authored_fact_sha256') or ''))
    mechanical_sha = str(refs.get('mechanical_case_sha256') or '')
    consistency_sha = refs.get('consistency_contract_sha256')
    if not authored:
        errors.append('delivery_authored_receipt_missing')
    elif str(authored.get('artifact') or '') != str(refs.get('artifact') or '') or str(authored.get('from_mechanical_case_sha256') or '') != mechanical_sha or authored.get('from_consistency_contract_sha256') != consistency_sha:
        errors.append('delivery_authoring_identity_mismatch')
    if not _is_sha256(mechanical_sha):
        errors.append('delivery_mechanical_case_sha_invalid')
    if consistency_sha is not None and (not _is_sha256(consistency_sha)):
        errors.append('delivery_consistency_contract_sha_invalid')
    credential_raw = _read_case_file(case_dir, '.grade_credential.json')
    try:
        lint_credential = json.loads(credential_raw.decode('utf-8')) if credential_raw is not None else None
    except (UnicodeError, ValueError, RecursionError):
        lint_credential = None
    scope = lint_credential.get('reachability_scope') if isinstance(lint_credential, dict) else None
    artifact_sha = str(refs.get('artifact') or '').rsplit(':', 1)[-1]
    if not (isinstance(lint_credential, dict) and lint_credential.get('source') == 'lint' and (lint_credential.get('lint_ok') is True) and (lint_credential.get('verdict') == 'PASS') and (str(lint_credential.get('autoid') or '') == aid) and (str(lint_credential.get('xlsx_sha256') or '') == artifact_sha) and isinstance(scope, dict) and (scope.get('source') == 'sealed_mechanical_case') and (scope.get('mechanical_case_sha256') == mechanical_sha) and ('consistency_contract_sha256' in lint_credential) and (lint_credential.get('consistency_contract_sha256') == consistency_sha)):
        errors.append('delivery_lint_identity_mismatch')
    return errors

def _validate_delivery_failure(aid: str, refs: dict, facts: list[dict], outcome: str='') -> list[str]:
    from cex_core.engine.ist_core.compile_engine import terminal_outcomes as TO
    errors: list[str] = []
    failure = _find_fact_by_sha(facts, aid=aid, ev=TO.FINAL_VOLUME_FAILURE_EVENTS, expected_sha256=str(refs.get('identity_fact_sha256') or ''))
    if not failure:
        return ['delivery_failure_receipt_missing']
    from cex_core.engine.ist_core.compile_engine.terminal_reentry_identity import copy_identity
    terminal = next((row for row in reversed(facts) if row.get('aid') == aid and row.get('ev') in {'blocked', 'ist_core_defect'} and (row.get('source_fact_sha256') == _fact_sha256(failure))), {})
    if terminal and copy_identity(terminal) != copy_identity(failure):
        errors.append('delivery_failure_reentry_identity_mismatch')
    expected = {'run_id': str(failure.get('run_id') or ''), 'volume': str(failure.get('volume') or ''), 'expected_artifact_sha256': str(failure.get('expected_artifact_sha256') or ''), 'observed_artifact_sha256': str(failure.get('observed_artifact_sha256') or ''), 'reasons': [str(value) for value in failure.get('reasons') or [] if str(value)]}
    if any((refs.get(key) != value for key, value in expected.items())):
        errors.append('delivery_failure_binding_mismatch')
    if not _is_nonempty_text(expected['run_id']) or not expected['reasons']:
        errors.append('delivery_failure_identity_incomplete')
    if outcome and outcome != TO.authority_failure_position(expected['reasons']):
        errors.append('credential_kind_outcome_mismatch')
    return errors

def _validate_authority_decision(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    from dataclasses import fields
    from cex_core.engine.ist_core.compile_engine import authority_reconcile as AR

    def is_sha(value: object) -> bool:
        return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None
    terminal_index = next((index for index, fact in enumerate(facts) if fact.get('aid') == aid and fact.get('ev') == 'blocked' and (_fact_sha256(fact) == refs.get('terminal_fact_sha256'))), -1)
    if terminal_index < 0:
        return ['authority_decision_terminal_receipt_missing']
    terminal = facts[terminal_index]
    errors: list[str] = []
    if not _is_nonempty_text(aid) or terminal.get('reason_code') != 'authority_needs_decision' or terminal.get('terminal_layer') != 'delivery' or (terminal.get('reentrant') is not True) or (terminal.get('terminal') is not False) or (type(terminal.get('round')) is not int) or (terminal['round'] < 0) or (type(refs.get('round')) is not int) or (refs.get('source_event') != 'authority_delivery_gate') or (not is_sha(refs.get('source_fact_sha256'))) or any((refs.get(key) != terminal.get(key) for key in ('round', 'source_event', 'source_fact_sha256'))):
        errors.append('authority_decision_terminal_contract_mismatch')
    gate_index = next((index for index, fact in enumerate(facts[:terminal_index]) if fact.get('aid') == aid and fact.get('ev') == 'authority_delivery_gate' and (_fact_sha256(fact) == refs.get('source_fact_sha256'))), -1)
    if gate_index < 0:
        return [*errors, 'authority_decision_gate_receipt_missing']
    gate = facts[gate_index]
    scope = gate.get('delivery_scope')
    if not isinstance(scope, dict):
        return [*errors, 'authority_decision_scope_missing']
    binding = scope.get('binding')
    binding_fields = {field.name for field in fields(AR.ExecutionBinding)}
    if not isinstance(binding, dict) or set(binding) != binding_fields:
        return [*errors, 'authority_decision_binding_incomplete']
    if any((not _is_nonempty_text(binding[key]) for key in binding_fields if key != 'consistency_contract_sha256')) or any((not is_sha(binding[key]) for key in ('projection_receipt_sha256', 'projection_sha256', 'artifact_sha256'))) or (binding['consistency_contract_sha256'] is not None and (not is_sha(binding['consistency_contract_sha256']))) or (binding['autoid'] != aid):
        errors.append('authority_decision_binding_invalid')
    artifact = scope.get('artifact')
    if not _is_nonempty_text(scope.get('volume')) or not is_sha(scope.get('volume_artifact_sha256')) or (not isinstance(artifact, str)) or (re.fullmatch(re.escape(aid) + ':[0-9a-f]{64}', artifact) is None) or any((not is_sha(scope.get(key)) for key in ('authored_fact_sha256', 'merged_fact_sha256', 'authority_fact_sha256'))):
        errors.append('authority_decision_scope_invalid')
    if gate.get('state') != AR.AuthorityState.NEEDS_DECISION.value or gate.get('failures') != [AR.ReconcileFailure.AUTHORITY_NOT_READY.value] or gate.get('artifact_sha256') != scope.get('volume_artifact_sha256') or (binding['artifact_sha256'] != scope.get('volume_artifact_sha256')) or ('consistency_contract_sha256' not in gate) or (gate['consistency_contract_sha256'] != binding['consistency_contract_sha256']):
        errors.append('authority_decision_gate_binding_mismatch')
    prefix = facts[:gate_index]
    authored = _find_fact_by_sha(prefix, aid=aid, ev='authored', expected_sha256=str(scope.get('authored_fact_sha256') or ''))
    current_authored = next((row for row in reversed(prefix) if row.get('aid') == aid and row.get('ev') == 'authored'), {})
    if not authored:
        errors.append('authority_decision_authored_receipt_missing')
    elif _fact_sha256(authored) != _fact_sha256(current_authored) or authored.get('artifact') != artifact or authored.get('from_consistency_contract_sha256') != binding['consistency_contract_sha256']:
        errors.append('authority_decision_authored_binding_mismatch')
    merged = _find_fact_by_sha(prefix, aid='', ev='merged', expected_sha256=str(scope.get('merged_fact_sha256') or ''))
    current_merged = next((row for row in reversed(prefix) if row.get('ev') == 'merged' and row.get('ctx') == 'delivery'), {})
    if not merged:
        errors.append('authority_decision_merged_receipt_missing')
    elif _fact_sha256(merged) != _fact_sha256(current_merged) or merged.get('ctx') != 'delivery' or merged.get('volume') != scope.get('volume') or (merged.get('artifact_sha256') != scope.get('volume_artifact_sha256')) or (not isinstance(merged.get('composition'), list)) or (merged['composition'].count(aid) != 1) or (not isinstance(merged.get('member_artifacts'), dict)) or (merged['member_artifacts'].get(aid) != artifact):
        errors.append('authority_decision_merged_binding_mismatch')
    authority = _find_fact_by_sha(prefix, aid=aid, ev='authority_reconciled', expected_sha256=str(scope.get('authority_fact_sha256') or ''))
    if not authority:
        return [*errors, 'authority_decision_authority_receipt_missing']
    receipt = authority.get('receipt')
    if not isinstance(receipt, dict) or set(receipt) != {field.name for field in fields(AR.AuthorityReceipt)}:
        return [*errors, 'authority_decision_authority_receipt_invalid']
    if receipt.get('schema') != AR.AUTHORITY_SCHEMA or receipt.get('state') != AR.AuthorityState.NEEDS_DECISION.value or receipt.get('binding') != binding or (not is_sha(receipt.get('input_sha256'))) or (not is_sha(receipt.get('receipt_sha256'))) or (gate.get('receipt_sha256') != receipt.get('receipt_sha256')):
        errors.append('authority_decision_authority_binding_mismatch')
    key = f"{AR.AUTHORITY_SCHEMA}:{receipt.get('input_sha256')}"
    if receipt.get('idempotency_key') != key or authority.get('idempotency_key') != key:
        errors.append('authority_decision_authority_idempotency_mismatch')
    if any((row.get('ev') == 'authority_reconciled' and row.get('idempotency_key') == key and (row.get('aid') != aid or row.get('receipt') != receipt) for row in prefix)):
        errors.append('authority_decision_authority_idempotency_conflict')
    try:
        receipt_sha256 = AR.canonical_sha256({name: value for name, value in receipt.items() if name != 'receipt_sha256'})
    except (TypeError, ValueError, RecursionError):
        receipt_sha256 = ''
    if receipt.get('receipt_sha256') != receipt_sha256:
        errors.append('authority_decision_authority_hash_mismatch')
    identities = receipt.get('source_identities')
    comparisons = receipt.get('comparisons')
    if not isinstance(identities, list) or not identities or any((not isinstance(item, dict) for item in identities)) or (not isinstance(comparisons, list)) or (not comparisons) or any((not isinstance(item, dict) for item in comparisons)) or (not isinstance(receipt.get('conflicts'), list)) or (not receipt['conflicts']) or (not isinstance(receipt.get('failures'), list)) or (not receipt['failures']):
        return [*errors, 'authority_decision_authority_evidence_incomplete']
    try:
        expected_state = AR.authority_state_for_failures([AR.ReconcileFailure(value) for value in receipt['failures']])
    except (TypeError, ValueError):
        errors.append('authority_decision_authority_failure_invalid')
    else:
        if expected_state is not AR.AuthorityState.NEEDS_DECISION:
            errors.append('authority_decision_authority_state_inconsistent')
    layers = {item.value for item in AR.AuthorityLayer}
    statuses = {item.value for item in AR.EvidenceStatus}
    if {item.get('layer') for item in identities if isinstance(item.get('layer'), str)} != layers or len(identities) != len(layers) or any((not isinstance(item.get('status'), str) or item['status'] not in statuses or (not isinstance(item.get('identity'), str)) or (not isinstance(item.get('build'), str)) or (item.get('status') == AR.EvidenceStatus.PRESENT.value and (not _is_nonempty_text(item.get('identity')))) for item in identities)):
        errors.append('authority_decision_authority_sources_invalid')
    comparison_fields = {field.name for field in fields(AR.PairwiseComparison)}
    comparison_statuses = {item.value for item in AR.ComparisonStatus}
    failures = {item.value for item in AR.ReconcileFailure}
    if any((set(item) != comparison_fields or not _is_nonempty_text(item.get('comparison_id')) or (not isinstance(item.get('left'), str)) or (item['left'] not in layers) or (not isinstance(item.get('right'), str)) or (item['right'] not in layers) or (not isinstance(item.get('status'), str)) or (item['status'] not in comparison_statuses) or (item.get('failure') is not None and (not isinstance(item['failure'], str) or item['failure'] not in failures)) or (not _is_nonempty_text(item.get('left_identity'))) or (not _is_nonempty_text(item.get('right_identity'))) or (not isinstance(item.get('differences'), list)) for item in comparisons)):
        errors.append('authority_decision_authority_comparisons_invalid')
    else:
        expected_conflicts = [item['comparison_id'] for item in comparisons if item['status'] in {AR.ComparisonStatus.CONFLICT.value, AR.ComparisonStatus.UNAVAILABLE.value}]
        expected_failures = list(dict.fromkeys((item['failure'] for item in comparisons if item['failure'] is not None)))
        if receipt['conflicts'] != expected_conflicts or receipt['failures'] != expected_failures:
            errors.append('authority_decision_authority_state_inconsistent')
    return errors

def _validate_execution_failure(aid: str, outcome: str, refs: dict, facts: list[dict]) -> list[str]:
    from cex_core.engine.ist_core.compile_engine.execution_failure import MAX_EXECUTION_ATTEMPTS, NO_DEVICE_REEXECUTION_REASON_CODES, classify_reason_code, current_execution_implementation_sha256, is_runtime_infrastructure_terminal_fact, reason_code_categories, terminal_action_for_category
    from cex_core.engine.ist_core.tools.device.batch_result_protocol import device_prerequisite_receipt_sha256, validate_device_prerequisite_receipts
    terminal_event = str(refs.get('event') or '')
    terminal = _find_fact_by_sha(facts, aid=aid, ev=terminal_event, expected_sha256=str(refs.get('terminal_fact_sha256') or ''))
    failure = _find_fact_by_sha(facts, aid=aid, ev='execution_failure', expected_sha256=str(refs.get('failure_fact_sha256') or ''))
    if not terminal:
        return ['execution_terminal_receipt_missing']
    if not failure:
        return ['execution_failure_receipt_missing']
    errors: list[str] = []
    runtime_infrastructure_terminal = is_runtime_infrastructure_terminal_fact(terminal)
    if not (outcome == 'blocked' and runtime_infrastructure_terminal or (outcome == 'ist_core_defect' and terminal_event == 'ist_core_defect') or (outcome == 'unable_to_compile' and terminal_event == outcome)):
        errors.append('execution_terminal_outcome_mismatch')
    expected = {'event': terminal_event, 'reason_code': str(terminal.get('reason_code') or ''), 'category': str(terminal.get('category') or ''), 'attempt': terminal.get('attempt'), 'artifact_sha256': str(terminal.get('artifact_sha256') or ''), 'bed_host': str(terminal.get('bed_host') or ''), 'build': str(terminal.get('build') or ''), 'implementation_sha256': str(terminal.get('implementation_sha256') or ''), 'prerequisite_receipt_sha256': str(terminal.get('prerequisite_receipt_sha256') or '')}
    if any((refs.get(key) != value for key, value in expected.items())):
        errors.append('execution_terminal_binding_mismatch')
    no_reexecution = expected['reason_code'] in NO_DEVICE_REEXECUTION_REASON_CODES
    terminal_attempt = expected['attempt']
    if isinstance(terminal_attempt, bool) or not isinstance(terminal_attempt, int) or (not 1 <= terminal_attempt <= MAX_EXECUTION_ATTEMPTS) or (not no_reexecution and terminal_attempt != MAX_EXECUTION_ATTEMPTS) or (failure.get('attempt') != terminal_attempt) or (str(failure.get('action') or '') != terminal_event):
        errors.append('execution_retry_budget_not_exhausted')
    terminal_index = next((index for index, fact in enumerate(facts) if fact is terminal), len(facts))
    comparable: list[dict] = []
    for fact in facts[:terminal_index]:
        if str(fact.get('aid') or '') != aid or any((str(fact.get(key) or '') != expected[key] for key in ('artifact_sha256', 'bed_host', 'build', 'implementation_sha256'))):
            continue
        if fact.get('ev') == 'execution_success':
            comparable = []
        elif fact.get('ev') == 'execution_failure':
            comparable.append(fact)
    expected_attempts = list(range(1, int(terminal_attempt or 0) + 1))
    expected_actions = [*['retry'] * max(0, len(expected_attempts) - 1), terminal_event]
    if [fact.get('attempt') for fact in comparable] != expected_attempts or [str(fact.get('action') or '') for fact in comparable] != expected_actions:
        errors.append('execution_attempt_sequence_invalid')
    for key in ('reason_code', 'category', 'artifact_sha256', 'bed_host', 'build', 'implementation_sha256', 'prerequisite_receipt_sha256'):
        if str(failure.get(key) or '') != str(terminal.get(key) or ''):
            errors.append('execution_failure_terminal_mismatch')
            break
    if not _is_sha256(expected['artifact_sha256']):
        errors.append('execution_artifact_identity_invalid')
    if not _is_nonempty_text(expected['bed_host']) or not isinstance(expected['build'], str):
        errors.append('execution_environment_identity_invalid')
    if not _is_sha256(expected['implementation_sha256']) or expected['implementation_sha256'] != current_execution_implementation_sha256():
        errors.append('execution_implementation_identity_stale')
    if expected['reason_code'] not in reason_code_categories():
        errors.append('execution_reason_code_invalid')
    else:
        category = classify_reason_code(expected['reason_code'])
        legacy_runtime_category = runtime_infrastructure_terminal and terminal_event == 'ist_core_defect' and (expected['category'] == 'engine_rejection')
        if category.value != expected['category'] and (not legacy_runtime_category):
            errors.append('execution_category_mismatch')
        if runtime_infrastructure_terminal:
            allowed_outcomes = {'blocked'}
            if terminal_event == 'ist_core_defect':
                allowed_outcomes.add('ist_core_defect')
            if outcome not in allowed_outcomes:
                errors.append('execution_terminal_action_mismatch')
        elif terminal_action_for_category(category).value != outcome:
            errors.append('execution_terminal_action_mismatch')
    prerequisite_sha256 = expected['prerequisite_receipt_sha256']
    if expected['reason_code'] == 'device_prerequisite_unmet':
        receipt_fact = next((fact for fact in facts if isinstance(fact, dict) and fact.get('ev') == 'device_prerequisite_receipt' and (str(fact.get('aid') or '') == aid) and (fact.get('attempt') == MAX_EXECUTION_ATTEMPTS) and (str(fact.get('receipt_sha256') or '') == prerequisite_sha256) and all((str(fact.get(key) or '') == expected[key] for key in ('artifact_sha256', 'bed_host', 'build', 'implementation_sha256')))), {})
        if not _is_sha256(prerequisite_sha256) or not receipt_fact:
            errors.append('execution_prerequisite_receipt_missing')
        else:
            try:
                normalized = validate_device_prerequisite_receipts([receipt_fact.get('receipt')], expected_autoids={aid}, artifact_sha256=expected['artifact_sha256'], bed_host=expected['bed_host'])[0]
                if device_prerequisite_receipt_sha256(normalized) != prerequisite_sha256 or str(receipt_fact.get('run_id') or '') != normalized['run_id']:
                    raise ValueError('receipt digest or run binding mismatch')
            except (TypeError, ValueError):
                errors.append('execution_prerequisite_receipt_invalid')
    elif prerequisite_sha256:
        errors.append('execution_prerequisite_receipt_unexpected')
    if outcome in {'blocked', 'ist_core_defect'}:
        if terminal.get('reentrant') is not True or terminal.get('terminal') is not False:
            errors.append('execution_reentry_contract_mismatch')
    elif terminal.get('reentrant') is not False or terminal.get('terminal') is not True:
        errors.append('execution_reentry_contract_mismatch')
    return errors

def _validate_unattributed_stop(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    """编写侧停点核不出责任那一格的凭据复核。

    与签发口共用 `UNPROVEN_STOP_POSITION_BY_CAUSE` 这一张表：成因码必须在闭集里、
    且这条成因确实判在中性那一格上。消费端换个地方自签 `blocked` 也过不了。
    """
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import BLOCKED, UNATTRIBUTED_LAYER, UNPROVEN_STOP_CAUSES, unproven_stop_position
    terminal = _find_fact_by_sha(facts, aid=aid, ev='blocked', expected_sha256=str(refs.get('terminal_fact_sha256') or ''))
    if not terminal:
        return ['unattributed_stop_terminal_receipt_missing']
    source_sha256 = str(refs.get('source_fact_sha256') or '')
    source_event = str(refs.get('source_event') or '')
    source = next((fact for fact in facts if str(fact.get('ev') or '') == source_event and _fact_sha256(fact) == source_sha256 and (str(fact.get('aid') or '') in {aid, ''})), {})
    errors: list[str] = []
    expected = {'reason_code': str(terminal.get('reason_code') or ''), 'stop_cause': str(terminal.get('stop_cause') or ''), 'round': terminal.get('round'), 'source_event': str(terminal.get('source_event') or ''), 'source_fact_sha256': str(terminal.get('source_fact_sha256') or '')}
    if any((refs.get(key) != value for key, value in expected.items())):
        errors.append('unattributed_stop_binding_mismatch')
    if not source:
        errors.append('unattributed_stop_source_receipt_missing')
    if terminal.get('reason_code') == 'authoring_evidence_unclosed' and source:
        from cex_core.engine.ist_core.compile_engine.authoring_evidence import has_rejected_draft_context, validate_rejected_draft_terminal
        if has_rejected_draft_context(source):
            errors.extend(validate_rejected_draft_terminal(terminal, facts))
    if str(terminal.get('terminal_layer') or '') != UNATTRIBUTED_LAYER or terminal.get('reentrant') is not True or terminal.get('terminal') is not False or (not _is_nonempty_text(expected['reason_code'])) or (not _is_nonempty_text(expected['source_event'])) or (not _is_sha256(expected['source_fact_sha256'])) or isinstance(expected['round'], bool) or (not isinstance(expected['round'], int)) or (expected['round'] < 0):
        errors.append('unattributed_stop_contract_mismatch')
    if expected['stop_cause'] not in UNPROVEN_STOP_CAUSES or unproven_stop_position(expected['stop_cause']) != BLOCKED:
        errors.append('unattributed_stop_cause_outside_closed_set')
    if source and expected['stop_cause']:
        from cex_core.engine.ist_core.compile_engine.authoring_evidence import unproven_stop_cause
        if unproven_stop_cause(source, facts=facts) != expected['stop_cause']:
            errors.append('unattributed_stop_cause_not_replayed')
        from cex_core.engine.ist_core.compile_engine.contradiction_stop import CAUSE, pause_observations
        if expected['stop_cause'] == CAUSE:
            if terminal.get('reason_code') != CAUSE or terminal.get('pause_kind') != 'contra' or terminal.get('contra_observations') != pause_observations(source, facts):
                errors.append('contradiction_stop_observations_mismatch')
    return errors

def _validate_engine_defect(aid: str, refs: dict, facts: list[dict]) -> list[str]:
    terminal = _find_fact_by_sha(facts, aid=aid, ev='ist_core_defect', expected_sha256=str(refs.get('terminal_fact_sha256') or ''))
    if not terminal:
        return ['engine_defect_terminal_receipt_missing']
    governance_errors = []
    if terminal.get('reason_code') == 'governance_end_unclosed':
        from cex_core.engine.ist_core.compile_engine.authoring_stops import validate_governance_end
        governance_errors = validate_governance_end(terminal, facts)
    source_sha256 = str(refs.get('source_fact_sha256') or '')
    source_event = str(refs.get('source_event') or '')
    source = next((fact for fact in facts if str(fact.get('aid') or '') == aid and str(fact.get('ev') or '') == source_event and (_fact_sha256(fact) == source_sha256)), {})
    errors: list[str] = list(governance_errors)
    expected = {'reason_code': str(terminal.get('reason_code') or ''), 'round': terminal.get('round'), 'source_event': str(terminal.get('source_event') or ''), 'source_fact_sha256': str(terminal.get('source_fact_sha256') or '')}
    if any((refs.get(key) != value for key, value in expected.items())):
        errors.append('engine_defect_binding_mismatch')
    if not source:
        errors.append('engine_defect_source_receipt_missing')
    if terminal.get('reason_code') == 'authoring_evidence_unclosed' and source:
        from cex_core.engine.ist_core.compile_engine.authoring_evidence import has_rejected_draft_context, validate_rejected_draft_terminal
        if has_rejected_draft_context(source):
            errors.extend(validate_rejected_draft_terminal(terminal, facts))
    if str(terminal.get('terminal_layer') or '') != 'engine' or terminal.get('reentrant') is not True or terminal.get('terminal') is not False or (not _is_nonempty_text(expected['reason_code'])) or (not _is_nonempty_text(expected['source_event'])) or (not _is_sha256(expected['source_fact_sha256'])) or isinstance(expected['round'], bool) or (not isinstance(expected['round'], int)) or (expected['round'] < 0):
        errors.append('engine_defect_contract_mismatch')
    return errors

def validate_terminal_credential(terminal: dict, *, facts: Iterable[dict], case_dir: Path | None=None) -> tuple[bool, list[str]]:
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import CASE_TERMINAL_OUTCOMES
    outcome = str(terminal.get('outcome') or '')
    if outcome not in CASE_TERMINAL_OUTCOMES:
        return (False, ['outcome_outside_closed_set'])
    refs = terminal.get('credential_refs')
    refs = refs if isinstance(refs, dict) else {}
    if refs.get('schema') != SCHEMA:
        return (False, ['credential_schema_invalid'])
    kind = str(refs.get('kind') or '')
    aid = str(terminal.get('aid') or '')
    layer = str(terminal.get('layer') or '')
    rows = [fact for fact in facts if isinstance(fact, dict)]
    errors: list[str] = []
    if kind == 'delivery':
        if outcome != 'delivered' or layer != 'delivery':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_delivery(aid, refs, rows, case_dir))
    elif kind == 'delivery_failure':
        if layer != 'delivery':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_delivery_failure(aid, refs, rows, outcome=outcome))
    elif kind == 'authority_decision':
        if outcome != 'blocked' or layer != 'delivery':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_authority_decision(aid, refs, rows))
    elif kind == 'unsupported_feature':
        if outcome != 'unable_to_compile' or layer != 'unsupported_feature':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_unsupported_feature(aid, refs, rows))
    elif kind == 'not_compilable':
        if outcome != 'abandoned' or layer != 'not_compilable':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_not_compilable(aid, refs, rows))
    elif kind == 'source_conflict':
        if outcome != 'abandoned' or layer != 'source_conflict':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_source_conflict(aid, refs, rows))
    elif kind == 'source_conflict_blocked':
        if outcome != 'blocked' or layer != 'source_conflict_blocked':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_source_conflict_blocked(aid, refs, rows))
    elif kind == 'batch_user_abandon':
        if outcome != 'abandoned' or layer != 'batch_user_abandon':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_batch_user_abandon(aid, refs, rows, case_dir))
    elif kind == 'round_cap':
        if outcome != 'abandoned' or layer != 'round_cap':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_round_cap(aid, refs, rows))
    elif kind == 'authoring_failure':
        if outcome != 'authoring_failure' or layer != 'authoring':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_authoring_failure(aid, refs, rows))
    elif kind == 'author_definition_gap':
        if outcome != 'abandoned' or layer != 'author_definition_gap':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_author_definition_gap(aid, refs, rows))
    elif kind == 'xml_absence':
        if outcome != 'unable_to_compile' or layer != 'xml_absence':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_xml_absence(aid, refs, rows))
    elif kind == 'suspension':
        if outcome != 'blocked' or layer != 'suspension':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_suspension(aid, refs, rows))
    elif kind == 'execution_failure':
        if outcome not in _EXECUTION_TERMINAL_OUTCOMES or layer != 'execution':
            errors.append('credential_kind_outcome_mismatch')
        else:
            errors.extend(_validate_execution_failure(aid, outcome, refs, rows))
    elif kind == 'engine_defect':
        if outcome != 'ist_core_defect' or layer != 'engine':
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_engine_defect(aid, refs, rows))
    elif kind == 'unattributed_stop':
        if outcome != 'blocked' or layer != _TO_UNATTRIBUTED_LAYER:
            errors.append('credential_kind_outcome_mismatch')
        errors.extend(_validate_unattributed_stop(aid, refs, rows))
    elif kind in _NON_DELIVERY_LAYERS:
        if outcome == 'delivered' or layer != kind:
            errors.append('credential_kind_outcome_mismatch')
        if kind == 'ought' and outcome != 'blocked':
            errors.append('ought_outcome_mismatch')
        if kind == 'ought':
            errors.extend(_validate_ought(aid, refs, rows, case_dir))
        elif kind == 'compile':
            errors.extend(_validate_compile(aid, refs, rows))
        else:
            errors.extend(_validate_device(aid, refs, rows, case_dir, outcome=outcome))
    else:
        errors.append('credential_kind_invalid')
    return (not errors, sorted(set(errors)))
