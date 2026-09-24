# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/authority_delivery_policy.py（sha256 836d38ed2927df66）。不在这里手改。
from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import fields
import re
from cex_core.engine.ist_core.compile_engine.authority_reconcile import AUTHORITY_SCHEMA, AuthorityReceipt, AuthorityState, ExecutionBinding, ReconcileFailure, authority_state_for_failures, canonical_sha256
_RECEIPT_FIELDS = frozenset((field.name for field in fields(AuthorityReceipt)))

def effective_authority_facts(facts: Sequence[Mapping], aid: str) -> list[dict]:
    from cex_core.engine.ist_core.compile_engine.engine_quarantine import effective_case_facts
    rows = list(facts)
    live = {id(row) for row in effective_case_facts(rows, aid)}
    return [row for row in rows if row.get('aid') != aid or id(row) in live]

def is_authority_decision_terminal(fact: Mapping) -> bool:
    return fact.get('ev') == 'blocked' and fact.get('reason_code') == 'authority_needs_decision' and (fact.get('terminal_layer') == 'delivery')

def _reason_items(reasons: object) -> Sequence:
    if isinstance(reasons, str):
        return (reasons,)
    return reasons if isinstance(reasons, (list, tuple)) else ()

def authority_gap_only(reasons: object) -> bool:
    items = _reason_items(reasons)
    if not items:
        return False
    for item in items:
        if not isinstance(item, str):
            return False
        parts = item.split(':')
        if len(parts) != 3 or parts[0] != 'authority_blocked' or (not parts[1].strip()):
            return False
        try:
            failures = [ReconcileFailure(code) for code in parts[2].split(',')]
        except ValueError:
            return False
        if any((authority_state_for_failures([failure]) is not AuthorityState.BLOCKED for failure in failures)):
            return False
    return True

def is_authority_gap_disclosure(fact: Mapping) -> bool:
    return bool(fact.get('failure_axis') == 'authority_chain' and authority_gap_only(fact.get('reasons')) and all((item.split(':')[1] == fact.get('aid') for item in _reason_items(fact.get('reasons')))))

def _is_volume_failure_event(fact: Mapping) -> bool:
    """是不是一条收口卷面失败事实（名字认闭集，缺口披露不算）。

    `ev` 按 `terminal_outcomes.FINAL_VOLUME_FAILURE_EVENTS` 放宽：新账签按轴拆开的
    名字，三批不可重生的冻结语料里是旧名。缺口披露（`final_volume_authority_disclosure`
    与旧账里同形的那些）照常交付、不是失败。
    """
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import FINAL_VOLUME_FAILURE_EVENTS
    return bool(fact.get('ev') in FINAL_VOLUME_FAILURE_EVENTS and (not is_authority_gap_disclosure(fact)))

def is_volume_identity_failure(fact: Mapping) -> bool:
    """卷身份轴：卷不可读 / SHA 不符 / 组成漏案多案 / autoid 重复那 8 个码。

    **两个谓词的轴判别是不对称的，这是 fail-closed 的方向，不是笔误。** 本谓词用
    「不是权威链轴」而不是「等于卷身份轴」：`failure_axis` 是 2026-09-02 才加的字段，
    更早的账与手写夹具里根本没有这个键，而这一支的后果是**撤凭据**——轴缺位时按
    卷身份读，等于「说不清是哪条轴就当卷面出事」，撤了不会放行错的卷。
    `is_volume_authority_unverified` 则必须用正向相等：它的后果是把案判成「未核成」
    并压住交付，轴缺位时不该凭空推定权威链没核成。
    """
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import AUTHORITY_CHAIN_AXIS
    return bool(_is_volume_failure_event(fact) and str(fact.get('failure_axis') or '') != AUTHORITY_CHAIN_AXIS)

def is_volume_authority_unverified(fact: Mapping) -> bool:
    """权威链轴：卷面可能一个字节不差，没核成的是来源权威链那一道。

    正向相等，理由见 `is_volume_identity_failure` 的不对称说明。
    """
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import AUTHORITY_CHAIN_AXIS
    return bool(_is_volume_failure_event(fact) and str(fact.get('failure_axis') or '') == AUTHORITY_CHAIN_AXIS)

def is_authority_unverified_block(fact: Mapping) -> bool:
    """收口判出来源待裁时落的案级阻塞终态。

    与 ASK 面板那条 `blocked` **不同源、不同 reason_code**：面板那条由
    `_authority_publish_decision_block` 在闸上签，`reason_code=authority_needs_decision`，
    凭据指向 `authority_delivery_gate`；本条是收口分流器在闸的凭据复核不成立时落的，
    `reason_code` 取收口卷面失败事件名，凭据指向那条失败事实。两条都落在待裁那一格，
    读点按各自的谓词认，不合并——合并会让「闸已核过」与「闸没核成」说同一句话。
    """
    from cex_core.engine.ist_core.compile_engine.terminal_outcomes import AUTHORITY_CHAIN_AXIS, FINAL_VOLUME_FAILURE_EVENTS
    return bool(fact.get('ev') == 'blocked' and fact.get('terminal_layer') == 'delivery' and (str(fact.get('reason_code') or '') in FINAL_VOLUME_FAILURE_EVENTS) and (str(fact.get('failure_axis') or '') == AUTHORITY_CHAIN_AXIS))

def is_authority_block_terminal(fact: Mapping) -> bool:
    """来源侧阻塞族：面板那条 ∪ 收口来源待裁那条。用户面三处各自只认这一个谓词。"""
    return is_authority_decision_terminal(fact) or is_authority_unverified_block(fact)

def _current_ready_receipt(fact: Mapping, *, aid: str, current_volume_sha256: str) -> bool:
    if fact.get('ev') != 'authority_reconciled' or not isinstance(current_volume_sha256, str) or (not re.fullmatch('[0-9a-f]{64}', current_volume_sha256)):
        return False
    receipt = fact.get('receipt')
    if not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS:
        return False
    binding = receipt.get('binding')
    if receipt.get('schema') != AUTHORITY_SCHEMA or receipt.get('state') != 'ready' or receipt.get('conflicts') != [] or (receipt.get('failures') != []) or (not isinstance(binding, dict)) or (set(binding) != {field.name for field in fields(ExecutionBinding)}) or (binding.get('autoid') != aid) or (binding.get('artifact_sha256') != current_volume_sha256) or (not isinstance(receipt.get('source_identities'), list)) or (not receipt['source_identities']) or (not isinstance(receipt.get('comparisons'), list)) or (not receipt['comparisons']):
        return False
    input_sha = receipt.get('input_sha256')
    if not isinstance(input_sha, str) or not re.fullmatch('[0-9a-f]{64}', input_sha):
        return False
    key = f'{AUTHORITY_SCHEMA}:{input_sha}'
    if receipt.get('idempotency_key') != key or fact.get('idempotency_key') != key:
        return False
    try:
        from cex_core.engine.ist_core.compile_engine import authority_reconcile as AR
        layers = {item.value for item in AR.AuthorityLayer}
        identities = receipt['source_identities']
        if len(identities) != len(layers) or {item['layer'] for item in identities} != layers or any((AR.EvidenceStatus(item['status']) is AR.EvidenceStatus.PRESENT and (not str(item['identity']).strip()) for item in identities)) or any((not isinstance(value, str) or not value.strip() for key, value in binding.items() if key != 'consistency_contract_sha256')) or any((not re.fullmatch('[0-9a-f]{64}', binding[key]) for key in ('projection_sha256', 'projection_receipt_sha256', 'artifact_sha256'))) or (binding['consistency_contract_sha256'] is not None and (not re.fullmatch('[0-9a-f]{64}', binding['consistency_contract_sha256']))):
            return False
        for comparison in receipt['comparisons']:
            if set(comparison) != {field.name for field in fields(AR.PairwiseComparison)} or AR.ComparisonStatus(comparison['status']) in {AR.ComparisonStatus.CONFLICT, AR.ComparisonStatus.UNAVAILABLE} or comparison['failure'] is not None or (comparison['left'] not in layers) or (comparison['right'] not in layers) or (not comparison['left_identity']) or (not comparison['right_identity']):
                return False
        return receipt.get('receipt_sha256') == canonical_sha256({name: value for name, value in receipt.items() if name != 'receipt_sha256'})
    except (KeyError, TypeError, ValueError, RecursionError):
        return False

def authority_decision_confirmed(block: Mapping, facts: Sequence[Mapping]) -> bool:
    from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
    if not is_authority_decision_terminal(block):
        return False
    facts = effective_authority_facts(facts, str(block.get('aid') or ''))
    index = next((i for i, row in enumerate(facts) if row == block), -1)
    if index < 0:
        return False
    prefix = list(facts[:index + 1])
    aid = str(block.get('aid') or '')
    refs = TC.build_terminal_credential(aid=aid, outcome='blocked', preferred_layer='delivery', facts=prefix)
    valid, _errors = TC.validate_terminal_credential({'aid': aid, 'outcome': 'blocked', 'layer': 'delivery', 'credential_refs': refs}, facts=prefix)
    return valid

def authority_decision_pending(facts: Sequence[Mapping], *, aid: str, current_volume_sha256: str) -> bool:
    from cex_core.engine.ist_core.compile_engine.authority_decision_reentry import reentry_matches
    return any((fact.get('aid') == aid and authority_decision_confirmed(fact, facts) and (not any((reentry_matches(fact, later, facts) for later in facts[index + 1:]))) for index, fact in enumerate(facts)))

def verified_ready_gate(gate: Mapping, facts: Sequence[Mapping], *, aid: str, current_volume_sha256: str) -> bool:
    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
    facts = effective_authority_facts(facts, aid)
    if gate.get('ev') != 'authority_delivery_gate' or gate.get('aid') != aid or gate.get('state') != 'ready' or (gate.get('failures') != []) or (gate.get('mismatched_fields') != []) or (gate.get('artifact_sha256') != current_volume_sha256):
        return False
    index = next((i for i, row in enumerate(facts) if row == gate), -1)
    scope = gate.get('delivery_scope')
    if index < 0 or not isinstance(scope, dict):
        return False
    if any((row.get('ev') == 'authority_delivery_gate' and row.get('aid') == aid for row in facts[index + 1:])):
        return False
    prefix = facts[:index]
    authority = next((row for row in prefix if row.get('ev') == 'authority_reconciled' and row.get('aid') == aid and (_fact_sha256(row) == scope.get('authority_fact_sha256'))), {})
    if not _current_ready_receipt(authority, aid=aid, current_volume_sha256=current_volume_sha256):
        return False
    receipt = authority['receipt']
    authored = next((row for row in reversed(facts) if row.get('ev') == 'authored' and row.get('aid') == aid), {})
    merged = next((row for row in reversed(facts) if row.get('ev') == 'merged' and row.get('ctx') == 'delivery'), {})
    artifact = str(authored.get('artifact') or '')
    return bool(authored in prefix and merged in prefix and re.fullmatch(re.escape(aid) + ':[0-9a-f]{64}', artifact) and (_fact_sha256(authored) == scope.get('authored_fact_sha256')) and (_fact_sha256(merged) == scope.get('merged_fact_sha256')) and (gate.get('receipt_sha256') == receipt['receipt_sha256']) and (scope.get('binding') == receipt['binding']) and ('consistency_contract_sha256' in gate) and (gate['consistency_contract_sha256'] == receipt['binding']['consistency_contract_sha256']) and (authored.get('from_consistency_contract_sha256') == gate['consistency_contract_sha256']) and (scope.get('volume') == merged.get('volume')) and merged.get('volume') and (scope.get('volume_artifact_sha256') == merged.get('artifact_sha256') == current_volume_sha256) and isinstance(merged.get('composition'), list) and (merged['composition'].count(aid) == 1) and isinstance(merged.get('member_artifacts'), dict) and (merged['member_artifacts'].get(aid) == artifact == scope.get('artifact')) and all((row.get('aid') == aid and row.get('receipt') == receipt for row in prefix if row.get('ev') == 'authority_reconciled' and row.get('idempotency_key') == authority['idempotency_key'])))

def governing_unverified_authority_failure(facts: Sequence[Mapping], *, aid: str, current_volume_sha256: str) -> dict:
    """让本案「权威链没核成」此刻仍然成立的那**一条**卷面失败事实；不成立则空字典。

    认两个名字：新账签 final_volume_authority_unverified，三批冻结语料里是
    旧名 + failure_axis=authority_chain（4/4 都带这个轴，已核）。轴判别照旧留着，
    它同时挡掉旧名里真属卷身份轴的那些。判据本身在 is_volume_authority_unverified。

    「成不成立」与「是哪一条」必须同源：收口要按这条事实的 `reasons` 推责任位域
    （`terminal_outcomes.authority_failure_position`），若判真假的地方与取事实的地方各写
    一遍，就会出现「视图判 S_BROKEN、收口找不到该按哪条事实定位域」的分叉。
    """
    rows = effective_authority_facts(facts, aid)
    last_failure = max((i for i, row in enumerate(rows) if row.get('aid') == aid and is_volume_authority_unverified(row)), default=-1)
    if last_failure < 0:
        return {}
    if any((verified_ready_gate(row, rows, aid=aid, current_volume_sha256=current_volume_sha256) for row in rows[last_failure + 1:])):
        return {}
    return dict(rows[last_failure])

def unverified_authority_pending(facts: Sequence[Mapping], *, aid: str, current_volume_sha256: str) -> bool:
    return bool(governing_unverified_authority_failure(facts, aid=aid, current_volume_sha256=current_volume_sha256))
