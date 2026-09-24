# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/step_graph.py（sha256 74a5dec9a24deb02）。不在这里手改。
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
_FOUND_OPS = frozenset({'found', 'not_found', 'abs_found', 'found_times'})

def assertion_block_kinds() -> frozenset[str]:
    from cex_core.engine.case_compiler.criterion_carriers import CRITERION_CARRIERS
    return frozenset((carrier.block_kind for group in CRITERION_CARRIERS for carrier in group.carriers if str(carrier.block_kind or '').strip()))
GP_NO_MEANINGFUL_ASSERTION = 'GP002'
GP_CODES = frozenset({GP_NO_MEANINGFUL_ASSERTION})

@dataclass(frozen=True)
class GraphIssue:
    code: str
    severity: str
    path: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class StepGraphReport:
    ok: bool
    issues: tuple[GraphIssue, ...] = ()
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> tuple[GraphIssue, ...]:
        return tuple((i for i in self.issues if i.severity == 'error'))

    @property
    def warnings(self) -> tuple[GraphIssue, ...]:
        return tuple((i for i in self.issues if i.severity == 'warning'))

def _norm(value: Any) -> str:
    return str(value or '').strip()

def _has_meaningful_assert(step: dict[str, Any]) -> bool:
    kind = _norm(step.get('kind')).upper()
    return bool(_asserts_list_payload(step) or (kind == 'STEP' and _norm(step.get('E')) == 'check_point' and (_norm(step.get('F')) in _FOUND_OPS) and _norm(step.get('G'))) or MEANINGFUL_ASSERT_PAYLOAD.get(kind, _no_payload)(step))

def _asserts_list_payload(step: dict[str, Any]) -> bool:
    rows = step.get('asserts') if isinstance(step.get('asserts'), list) else []
    return any((isinstance(row, dict) and _norm(row.get('op')) in _FOUND_OPS and _norm(row.get('pattern')) for row in rows))

def _no_payload(step: dict[str, Any]) -> bool:
    return False

def _distribution_payload(step: dict[str, Any]) -> bool:
    from cex_core.engine.case_compiler.distribution_assertion import distribution_count_binding_error
    buckets = step.get('buckets')
    if not isinstance(buckets, list) or not buckets:
        return False
    return distribution_count_binding_error(step.get('field'), buckets) is None
MEANINGFUL_ASSERT_PAYLOAD: dict[str, Any] = {'OBSERVE_ASSERT': _asserts_list_payload, 'EXPECT_FROM': lambda step: _norm(step.get('op')) in _FOUND_OPS, 'OBSERVE_DIST': lambda step: _distribution_payload(step), 'OBSERVE_MEMBER': lambda step: isinstance(step.get('ips'), list) and any((_norm(item) for item in step.get('ips') or [])), 'OBSERVE_EXIT': lambda step: bool(_norm(step.get('expect'))), 'CAPTURE_COMPARE': lambda step: True}

def check_step_graph(blocks: Any) -> StepGraphReport:
    issues: list[GraphIssue] = []
    if not isinstance(blocks, list) or not blocks:
        return StepGraphReport(ok=True, stats={'steps': 0})
    payloads = [_has_meaningful_assert(step if isinstance(step, dict) else {}) for step in blocks]
    if not any(payloads):
        issues.append(GraphIssue(code=GP_NO_MEANINGFUL_ASSERTION, severity='error', path='steps', message='no meaningful assertion in this case (the assertion payload for its block kind is empty or unsupported)', evidence={}))
    ok = not any((issue.severity == 'error' for issue in issues))
    return StepGraphReport(ok=ok, issues=tuple(issues), stats={'steps': len(payloads)})
__all__ = ['GP_CODES', 'MEANINGFUL_ASSERT_PAYLOAD', 'GP_NO_MEANINGFUL_ASSERTION', 'GraphIssue', 'StepGraphReport', 'assertion_block_kinds', 'check_step_graph']
