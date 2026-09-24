# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/views.py（sha256 ff1a3cd4ef5fb40f）。不在这里手改。
from __future__ import annotations
from collections import Counter
from cex_core.engine.ist_core.compile_engine import facts as F
from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import effective_authority_facts, is_authority_decision_terminal, is_authority_gap_disclosure, is_volume_identity_failure, unverified_authority_pending
S_PENDING = 'pending'
S_AWAITING_USER = 'awaiting_user'
S_COMPOSED = 'composed'
S_AUTHORED = 'authored'
S_FAILED = 'failed'
S_BROKEN = 'broken'
S_BROKEN_ERRORED = 'broken_errored'
S_BROKEN_BLOCKED = 'broken_blocked'
S_BROKEN_ABORTED = 'broken_aborted'
S_BROKEN_VERDICT_UNRECOGNIZED = 'broken_verdict_unrecognized'
S_SUBSET_VERIFIED = 'subset_verified'
S_DELIVERABLE = 'deliverable'
S_CONTRADICTED = 'contradicted'
S_ESCALATED = 'escalated'
S_QUARANTINED = 'quarantined'
S_TERMINAL = 'failed_terminal'
S_SUSPENDED = 'suspended'
S_UNSUPPORTED_FEATURE = 'unsupported_feature'
CASE_VIEW_STATES = frozenset({S_PENDING, S_AWAITING_USER, S_COMPOSED, S_AUTHORED, S_FAILED, S_BROKEN, S_BROKEN_ERRORED, S_BROKEN_BLOCKED, S_BROKEN_ABORTED, S_BROKEN_VERDICT_UNRECOGNIZED, S_SUBSET_VERIFIED, S_DELIVERABLE, S_CONTRADICTED, S_ESCALATED, S_QUARANTINED, S_TERMINAL, S_SUSPENDED, S_UNSUPPORTED_FEATURE})
SCENARIO2_REASON_CODE = 'scenario2_incomplete_case'
_REENTRANT_TERMINAL_EVENTS = frozenset({'source_conflict_blocked', 'authority_preflight_blocked', 'blocked', 'ist_core_defect', 'intent_stamp_failed', 'authoring_failure'})
_PERMANENT_TERMINAL_EVENTS = frozenset({'xml_absence_terminal', 'unable_to_compile'})

def scenario2_abandon_active(mine: list[dict]) -> bool:
    return any((fact.get('ev') == 'policy_abandon' and fact.get('reason_code') == SCENARIO2_REASON_CODE for fact in mine))
_V12_EXECUTION_TERMINAL_EVENTS = frozenset({'blocked', 'ist_core_defect', 'unable_to_compile', 'authoring_failure'})

def is_engineering_fault_terminal(fact: dict) -> bool:
    return bool(fact.get('ev') == 'attribution' and str(fact.get('disposition') or '') == 'engineering_fault' and fact.get('is_terminal') and str(fact.get('run_id') or '').strip())

def case_abandoned(mine: list[dict]) -> bool:
    return any((fact.get('ev') == 'policy_abandon' for fact in mine))

def direct_abandon_terminal(mine: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import is_direct_abandon_decision
    if not any((is_direct_abandon_decision(fact) for fact in mine)):
        if not _author_side_conflict_abandon(mine):
            return {}
    abandons = [f for f in mine if f.get('ev') == 'policy_abandon']
    return abandons[-1] if abandons else {}

def _author_side_conflict_abandon(mine: list[dict]) -> bool:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    if not any((fact.get('ev') == 'consistency_verdict' and str(fact.get('verdict') or '') == 'conflict' for fact in mine)):
        return False
    if any((fact.get('ev') in {'decision', 'needs_decision'} for fact in mine)):
        return False
    latest = next((f for f in reversed(mine) if f.get('ev') == 'policy_abandon'), {})
    return str(latest.get('blocking_class') or '') in {BT.A_SPEC_CASE_CONFLICT, BT.A_SPEC_PRESENT_CASE_INCOMPLETE, BT.A_INCOMPLETE_CASE}

def active_execution_terminal(mine: list[dict], *, facts: list[dict] | None=None) -> dict:
    if facts is not None:
        from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
        aid = next((str(row['aid']) for row in mine if row.get('aid')), '')
        facts = effective_authority_facts(facts, aid)
        live = {_fact_sha256(row) for row in facts}
        mine = [row for row in mine if _fact_sha256(row) in live]
    if case_abandoned(mine):
        return {}
    for index in range(len(mine) - 1, -1, -1):
        fact = mine[index]
        event = str(fact.get('ev') or '')
        if event not in _V12_EXECUTION_TERMINAL_EVENTS:
            continue
        if is_authority_decision_terminal(fact):
            from cex_core.engine.ist_core.compile_engine.authority_decision_reentry import reentry_matches
            if not any((reentry_matches(fact, later, facts if facts is not None else mine) for later in mine[index + 1:])):
                return fact
            continue
        if event in {'blocked', 'ist_core_defect', 'authoring_failure'}:
            raw_round = fact.get('round', 0)
            if type(raw_round) is not int or raw_round < 0:
                return fact
            released = any((later.get('ev') == 'conflict_chain_reentered' and type(later.get('round')) is int and (int(later['round']) > raw_round) for later in mine[index + 1:]))
            if not released:
                return fact
        else:
            return fact
    return {}

def _positive_round(fact: dict) -> int | None:
    value = fact.get('round')
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value

def _reentrant_terminal_round(fact: dict) -> int | None:
    if 'round' not in fact:
        return 0
    value = fact.get('round')
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value

def _reentrant_terminal_active(mine: list[dict], terminal_event: str, *, facts: list[dict] | None=None) -> bool:
    if terminal_event == 'blocked':
        from cex_core.engine.ist_core.compile_engine.authority_decision_reentry import reentry_matches
        if any((is_authority_decision_terminal(fact) and (not any((reentry_matches(fact, later, facts if facts is not None else mine) for later in mine[index + 1:]))) for index, fact in enumerate(mine))):
            return True
    last_terminal_index = max((index for index, fact in enumerate(mine) if fact.get('ev') == terminal_event and (not is_authority_decision_terminal(fact))), default=-1)
    if last_terminal_index < 0:
        return False
    terminal_round = _reentrant_terminal_round(mine[last_terminal_index])
    if terminal_round is None:
        return True
    return not any((fact.get('ev') == 'conflict_chain_reentered' and (reentry_round := _positive_round(fact)) is not None and (reentry_round > terminal_round) for fact in mine[last_terminal_index + 1:]))

def _user_sourced(att: dict) -> bool:
    return F.attribution_is_terminal(att)

def _is_suspended(mine: list[dict]) -> bool:
    last_susp = -1
    last_resume = -1
    for i, f in enumerate(mine):
        if f.get('ev') == 'suspended':
            last_susp = i
        elif f.get('ev') == 'resumed':
            last_resume = i
    return last_susp >= 0 and last_resume < last_susp

def active_execution_pause(mine: list[dict]) -> dict:
    if not _is_suspended(mine):
        return {}
    latest = next((fact for fact in reversed(mine) if fact.get('ev') == 'suspended'), {})
    return latest if latest.get('suspension_kind') == 'execution_pause' else {}

def execution_pause_resume_pending(mine: list[dict]) -> bool:
    pause = {}
    pending = False
    for fact in mine:
        event = fact.get('ev')
        if event == 'suspended':
            pause = fact if fact.get('suspension_kind') == 'execution_pause' else {}
            pending = False
        elif event == 'resumed':
            pending = bool(pause)
        elif event in {'verdict', 'authored', 'composed'}:
            pending = False
    return pending

def _is_escalated(mine: list[dict]) -> bool:
    last_esc = -1
    last_release = -1
    for i, f in enumerate(mine):
        if f.get('ev') == 'escalated':
            last_esc = i
        elif f.get('ev') in ('authored', 'de_escalated'):
            last_release = i
    return last_esc >= 0 and last_release < last_esc

def case_status(fs: list[dict], aid: str, current_artifact: str, current_volume: str, current_volume_artifact_sha256: str='') -> str:
    from cex_core.engine.ist_core.compile_engine import engine_quarantine as EQ
    if aid in EQ.quarantined_aids(fs):
        return S_QUARANTINED
    mine = EQ.effective_case_facts(fs, aid)
    fs = effective_authority_facts(fs, aid)
    if any((f.get('ev') == 'unsupported_feature' for f in mine)):
        return S_UNSUPPORTED_FEATURE
    if case_abandoned(mine):
        return S_TERMINAL
    if any((f.get('ev') in _PERMANENT_TERMINAL_EVENTS for f in mine)):
        return S_TERMINAL
    if any((_reentrant_terminal_active(mine, terminal_event, facts=fs) for terminal_event in _REENTRANT_TERMINAL_EVENTS)):
        return S_TERMINAL
    if _is_escalated(mine):
        return S_ESCALATED
    if _is_suspended(mine):
        return S_SUSPENDED
    if any((f.get('ev') == 'attribution' and _user_sourced(f) and (f.get('disposition') in ('env_blocked', 'defect_candidate', 'user_stop', 'engineering_fault')) and (not F.scenario5_device_defect(f.get('layer'), f.get('disposition')) or F.scenario5_attribution_has_evidence(f, mine)) for f in mine)):
        return S_TERMINAL
    from cex_core.engine.ist_core.compile_engine._shared import _decision_resolves_needs_decision
    current_needs = []
    for index, fact in enumerate(mine):
        if fact.get('ev') != 'needs_decision':
            continue
        if any((later.get('ev') == 'conflict_chain_reentered' and later.get('invalidate_decisions') is True for later in mine[index + 1:])):
            continue
        current_needs.append(fact)
    decisions = [fact for fact in mine if fact.get('ev') == 'decision']
    if any((not any((_decision_resolves_needs_decision(need, decision, mine) for decision in decisions)) for need in current_needs)):
        return S_AWAITING_USER
    if unverified_authority_pending(fs, aid=aid, current_volume_sha256=current_volume_artifact_sha256):
        return S_BROKEN
    last_auth_i = max((i for i, f in enumerate(mine) if f.get('ev') == 'authored'), default=-1)
    last_execution_reuse_i = max((i for i, fact in enumerate(mine) if fact.get('ev') == 'execution_reentry_artifact_reused' and str(fact.get('artifact') or '') == str(mine[last_auth_i].get('artifact') or '')), default=-1) if last_auth_i >= 0 else -1
    if last_auth_i >= 0 and any((f.get('ev') == 'emit_invalid' for f in mine[max(last_auth_i, last_execution_reuse_i) + 1:])):
        return S_PENDING
    last_db_i = max((i for i, f in enumerate(mine) if f.get('ev') == 'delivery_blocked'), default=-1)
    if last_db_i >= 0:
        last_dpass_i = max((i for i, f in enumerate(mine) if f.get('ev') == 'verdict' and f.get('ctx') == F.CTX_DELIVERY and (f.get('result') == 'pass')), default=-1)
        if last_db_i > last_dpass_i and last_db_i > last_auth_i:
            return S_PENDING
    last_volume_identity_failure = max((i for i, f in enumerate(mine) if is_volume_identity_failure(f)), default=-1)
    last_delivery_pass = max((i for i, f in enumerate(mine) if f.get('ev') == 'verdict' and f.get('ctx') == F.CTX_DELIVERY and (f.get('result') == 'pass')), default=-1)
    if last_volume_identity_failure > last_delivery_pass and last_volume_identity_failure > last_auth_i:
        return S_BROKEN
    if F.deliverable(mine, aid, current_artifact, current_volume, current_volume_artifact_sha256):
        return S_DELIVERABLE
    last = F.latest_verdict(mine, aid, artifact=current_artifact) if current_artifact else None
    if last:
        if last.get('result') == 'pass':
            return S_SUBSET_VERIFIED
        if last.get('result') in ('broken', 'not_run'):
            sub = str(last.get('broken_subtype') or '')
            if sub == 'errored':
                return S_BROKEN_ERRORED
            if sub == 'blocked':
                return S_BROKEN_BLOCKED
            if sub == 'aborted':
                return S_BROKEN_ABORTED
            if sub == 'verdict_unrecognized':
                return S_BROKEN_VERDICT_UNRECOGNIZED
            return S_BROKEN
        if last.get('ctx') == F.CTX_DELIVERY and F.contradictions(mine, aid, artifact=current_artifact) > 0:
            return S_CONTRADICTED
        return S_FAILED
    if aid in F.pending_emit_aids(fs):
        return S_COMPOSED
    if F.rounds_used(mine, aid) > 0:
        return S_AUTHORED
    return S_PENDING

def current_delivery_volume_sha256(fs: list[dict]) -> str:
    """当前交付卷的卷面 sha；没有交付合卷则空。

    `batch_view` 与收口的位域推导读同一处：`unverified_authority_pending` 的第二个入参
    就是这个值，视图算一份、收口再算一份的话，两边会对「权威链还没核成」给出不同答案。
    """
    d_merges = [f for f in fs if f.get('ev') == 'merged' and f.get('ctx') != F.CTX_SUBSET]
    return str(d_merges[-1].get('artifact_sha256') or '') if d_merges else ''

def batch_view(fs: list[dict], manifest: dict) -> dict:
    aids = [str(c.get('autoid')) for c in manifest.get('cases') or []]
    d_merges = [f for f in fs if f.get('ev') == 'merged' and f.get('ctx') != F.CTX_SUBSET]
    current_volume = str(d_merges[-1].get('volume')) if d_merges else ''
    current_volume_sha = current_delivery_volume_sha256(fs)
    out: dict = {'cases': {}, 'volume': current_volume, 'volume_artifact_sha256': current_volume_sha}
    for aid in aids:
        mine = [f for f in fs if str(f.get('aid')) == aid]
        authored = [f for f in mine if f.get('ev') == 'authored']
        artifact = str(authored[-1].get('artifact')) if authored else ''
        st = case_status(fs, aid, artifact, current_volume, current_volume_sha)
        authored_rounds = F.rounds_used(mine, aid)
        dispatch_attempts = F.dispatch_rounds_used(mine, aid)
        out['cases'][aid] = {'status': st, 'artifact': artifact, 'rounds': authored_rounds, 'authored_rounds': authored_rounds, 'dispatch_attempts': dispatch_attempts, 'effective_budget': F.effective_rounds_used(mine, aid), 'contradictions': F.contradictions(mine, aid, artifact=artifact or None), 'recovered': F.recovered(mine, aid, artifact=artifact or None), 'frozen': F.frozen(mine, aid, artifact or None), 'transient_recur': F.transient_recur(mine, aid)}
    out['counts'] = dict(Counter((v['status'] for v in out['cases'].values())))
    return out

def is_settled(status: str) -> bool:
    return status in (S_DELIVERABLE, S_ESCALATED, S_QUARANTINED, S_TERMINAL, S_SUSPENDED, S_UNSUPPORTED_FEATURE)

def all_settled(view: dict) -> bool:
    return all((is_settled(v['status']) for v in view['cases'].values())) and bool(view['cases'])
