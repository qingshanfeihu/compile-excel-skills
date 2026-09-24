# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/step_graph.py（sha256 74a5dec9a24deb02）。不在这里手改。
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
_FOUND_OPS = frozenset({'found', 'not_found', 'abs_found', 'found_times'})

def assertion_block_kinds() -> frozenset[str]:
    """承载断言的块类型闭集——**现取现算**，取自判据载体注册表。

    这里曾经是一份手写字面量，于是「哪种块算断言」在全仓有两处声明：注册表
    `criterion_carriers.CRITERION_CARRIERS` 和本模块。两处各自长大，本模块那份
    每漏一种就是一条假拒绝：OBSERVE_MEMBER、OBSERVE_DIST 都是被补进来的，
    OBSERVE_EXIT 漏到 2026-09-18 才由回放量出来——冻结语料 486 案里，294 个交付且
    真机 PASS 的锚有 **147 个**被判 GP002「全案没有有意义断言」，而它们的
    `expectation_binding` 正指着那一格 OBSERVE_EXIT 当断言载体。
    改成从注册表派生，新增载体类型不必再来改这里。

    `implementation_blocks`（如 CAPTURE）是非断言实现块（observation_only），
    按注册表自己的角色划分排除在外。
    """
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
    """`asserts[]` 这条通路不挑块类型——带算子和 pattern 的断言行谁挂都算数。"""
    rows = step.get('asserts') if isinstance(step.get('asserts'), list) else []
    return any((isinstance(row, dict) and _norm(row.get('op')) in _FOUND_OPS and _norm(row.get('pattern')) for row in rows))

def _no_payload(step: dict[str, Any]) -> bool:
    return False

def _distribution_payload(step: dict[str, Any]) -> bool:
    """分布块承载了断言吗——判据不在这里，在 `distribution_assertion` 那一份。

    这一格曾经写成「`field` 非空即有载荷」，与展开器自己的契约打架：桶各自带完整
    `{range}` 版式时 `field` **本就该**留空，展开器照样把它展成每桶一条 `found`。
    冻结语料 486 案里 GP002 的 8 次命中全是这种合法形态（`known_wrong/<batch>`），
    全是假拒绝。现在两处读同一个函数：展开器拿它当硬门，这里拿它判载荷，不会再分叉。
    """
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
