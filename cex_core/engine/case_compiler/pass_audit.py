# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/pass_audit.py（sha256 c22b15ff1618da17）。不在这里手改。
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Iterable
from cex_core.engine.common.schema_identity import accepts_schema
SCHEMA = 'ist.ide.pass-audit'
COUNT_FIELDS = ('total_assertions', 'flipped_assertions', 'exempt_assertions', 'pending_assertions')

def _sha(value: object) -> str:
    return value if isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) else ''

def _case_sha(aid: str, artifact: object) -> str:
    if not isinstance(artifact, str):
        return ''
    owner, separator, digest = str(artifact or '').partition(':')
    return _sha(digest) if separator and owner == aid else ''

def latest_terminals(facts: Iterable[dict]) -> dict[str, dict]:
    return {str(fact['aid']): fact for fact in facts if fact.get('ev') == 'case_terminal_outcome' and fact.get('aid')}

def group_audits(facts: Iterable[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for fact in facts:
        if fact.get('ev') == 'pass_audit' and fact.get('aid'):
            groups.setdefault(str(fact['aid']), []).append(fact)
    return groups

def terminal_artifacts(terminal: dict) -> tuple[str, str]:
    if terminal.get('outcome') != 'delivered' or terminal.get('credential_valid') is False:
        return ('', '')
    refs = terminal.get('credential_refs')
    if not isinstance(refs, dict):
        return ('', '')
    return (_sha(refs.get('volume_artifact_sha256')), _case_sha(str(terminal.get('aid') or ''), refs.get('artifact')))

def metric_delivery_artifacts(facts: list[dict], final_sha: str | None) -> dict[str, tuple[str, str]]:
    final = _sha(final_sha)
    if not final:
        return {}
    verdicts = {str(fact.get('aid')): fact for fact in facts if fact.get('ev') == 'verdict' and fact.get('ctx') == 'delivery' and (fact.get('volume_artifact_sha256') == final)}
    identities = {aid: (final, _case_sha(aid, fact.get('artifact')) if fact.get('result') == 'pass' else '') for aid, fact in verdicts.items()}
    for aid, terminal in latest_terminals(facts).items():
        volume, case = terminal_artifacts(terminal)
        identities[aid] = (volume, case) if volume == final else ('', '')
    return identities

@dataclass(frozen=True)
class PassAuditView:
    audit: dict | None
    status: str
    reason: str
    counts: tuple[int, int, int, int] | None = None

    @property
    def trusted(self) -> bool:
        return self.status in {'complete', 'incomplete', 'unavailable'}

    @property
    def clean(self) -> bool:
        return self.status == 'complete' and (self.audit or {}).get('outcome') == 'clean'

def select_pass_audit(facts: list[dict], *, aid: str, final_sha: str, case_sha: str) -> PassAuditView:
    candidates = [fact for fact in facts if fact.get('ev') == 'pass_audit' and str(fact.get('aid')) == aid]
    if not candidates:
        return PassAuditView(None, 'missing', 'audit_missing')
    matching = [fact for fact in candidates if fact.get('artifact_sha256') == final_sha]
    audit = (matching or candidates)[-1]
    if not _sha(final_sha) or not _sha(case_sha):
        return PassAuditView(audit, 'unverified', 'delivery_identity_missing')
    if not matching:
        return PassAuditView(audit, 'unverified', 'audit_artifact_mismatch')
    if audit.get('case_artifact_sha256') != case_sha:
        return PassAuditView(audit, 'unverified', 'case_artifact_mismatch')
    if not (accepts_schema(audit.get('schema'), 'ist.ide.pass-audit') and audit.get('artifact') == 'case.xlsx' and (audit.get('audit_basis') == 'mutation_flip') and isinstance(audit.get('audit_revision'), str) and audit['audit_revision'].strip()):
        return PassAuditView(audit, 'unverified', 'audit_schema_invalid')
    status, outcome = (audit.get('status'), audit.get('outcome'))
    if not isinstance(status, str) or not isinstance(outcome, str):
        return PassAuditView(audit, 'unverified', 'audit_state_invalid')
    if status == 'complete' and outcome not in {'clean', 'false_pass'} or (status in {'incomplete', 'unavailable'} and outcome != 'unknown') or status not in {'complete', 'incomplete', 'unavailable'}:
        return PassAuditView(audit, 'unverified', 'audit_state_invalid')
    if status == 'unavailable':
        return PassAuditView(audit, status, str(audit.get('reason_code') or 'audit_unavailable'))
    counts = tuple((audit.get(key) for key in COUNT_FIELDS))
    if not (_sha(audit.get('mutation_receipt_sha256')) and all((isinstance(value, int) and (not isinstance(value, bool)) and (value >= 0) for value in counts)) and (sum(counts[1:]) == counts[0]) and (counts[0] > 0) and (outcome != 'clean' or counts[1] == counts[0])):
        return PassAuditView(audit, 'unverified', 'audit_counts_invalid')
    return PassAuditView(audit, status, str(audit.get('reason_code') or ''), counts)
