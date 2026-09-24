# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/distribution_assertion.py（sha256 7eb5aaa9ab6ac427）。不在这里手改。
from __future__ import annotations
import re
DISTRIBUTION_DECLARATION_CONTRACT = {'default_layout': 'anchor[^\\n]*field{range}', 'field': "A regex prefix immediately before the count in the same line as anchor. It is not a complete row pattern. A bucket's complete pattern ignores this field, so an empty string is valid only when every bucket provides its own template containing {range}; with neither, nothing says where the count is read and the block is rejected.", 'bucket_pattern': "Optional complete regex template containing {range}. Only {range} is replaced by the bounded integer regex; anchor and field are not prepended. Use this form when the documented identifier and count span lines or require a different order. Bind the count to this bucket's record and preserve record boundaries; a broad cross-record wildcard can read another bucket's count. Layout evidence never signs the expected count.", 'sampling': "total is the author's compiled sample-count declaration used to derive count intervals. OBSERVE_DIST executes cmd once and checks that output; it does not repeat requests, reset counters, or count executed requests. Arrange the required traffic and observation in executable blocks and retain evidence connecting executed samples to the measured counters. A valid interval or a declared total does not prove that execution link."}

def _bucket_binds_its_own_count(bucket: object) -> bool:
    if not isinstance(bucket, dict):
        return False
    template = bucket.get('pattern')
    return isinstance(template, str) and '{range}' in template

def distribution_count_binding_error(field: object, buckets: object) -> str | None:
    if not isinstance(buckets, list) or not buckets:
        return None
    if str(field or '').strip():
        return None
    unbound = [index for index, bucket in enumerate(buckets) if not _bucket_binds_its_own_count(bucket)]
    if not unbound:
        return None
    return f"this distribution check does not say where the count is read: field is empty and bucket(s) {unbound} carry no complete pattern containing {{range}}, so the generated assertion is the bucket anchor, anything else on that line, then a bare number - it matches whichever number appears first after the anchor, which need not be the hit count, and the check cannot tell a correct distribution from a wrong one. Either set field to the text that immediately precedes the count on the anchor's line, or give every bucket its own complete pattern containing {{range}}."

def _fill_by_nines(num: int, nines: int) -> int:
    return num - num % 10 ** nines + (10 ** nines - 1)

def _fill_by_zeros(num: int, zeros: int) -> int:
    return num - num % 10 ** zeros - 1

def _split_to_ranges(lo: int, hi: int) -> list[tuple[int, int]]:
    stops = {hi}
    nines = 1
    stop = _fill_by_nines(lo, nines)
    while lo <= stop < hi:
        stops.add(stop)
        nines += 1
        stop = _fill_by_nines(lo, nines)
    zeros = 1
    stop = _fill_by_zeros(hi, zeros)
    while lo < stop <= hi:
        stops.add(stop)
        zeros += 1
        stop = _fill_by_zeros(hi, zeros)
    ranges: list[tuple[int, int]] = []
    start = lo
    for stop in sorted(stops):
        ranges.append((start, stop))
        start = stop + 1
    return ranges

def _range_to_pattern(start: int, stop: int) -> str:
    pattern = ''
    for ds, de in zip(str(start), str(stop)):
        pattern += ds if ds == de else f'[{ds}-{de}]'
    return pattern

def int_range_to_regex(lo: int, hi: int) -> str:
    if lo > hi:
        raise ValueError(f'区间非法 lo={lo} > hi={hi}')
    if lo < 0:
        raise ValueError(f'区间下界须 >=0，实际 lo={lo}')
    seen: set[str] = set()
    uniq: list[str] = []
    for a, b in _split_to_ranges(lo, hi):
        p = _range_to_pattern(a, b)
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return '|'.join(uniq)

def range_regex_for_count(lo: int, hi: int) -> str:
    return f'(?<!\\d)(?:{int_range_to_regex(lo, hi)})(?!\\d)'

def _bucket_bounds(expected: int, tol: int) -> tuple[int, int]:
    return (max(0, expected - tol), expected + tol)

def distribution_tolerance_policy(*, independent_steps: bool, min_interval_s: float, shared_bed_isolated: bool) -> dict:
    reasons = []
    if not independent_steps:
        reasons.append('shell_loop_or_compound_step')
    if min_interval_s < 3.0:
        reasons.append('cache_window_below_3s')
    if not shared_bed_isolated:
        reasons.append('shared_bed_counter_interference')
    if reasons:
        return {'status': 'unknown', 'tolerance': None, 'reason_codes': reasons, 'basis': 'sampling context is not equivalent to the controlled replay; do not turn this advisory into a compile error'}
    return {'status': 'known', 'tolerance': 0, 'reason_codes': [], 'basis': 'controlled replay uses independent framework steps, >=3s between requests, and isolated shared-bed counters'}
BUCKET_RULE_EN = 'Every bucket keeps its authored weight share, the bucket counts sum to the sample count, and no single bucket interval reaches the sample count — a bucket wide enough to absorb the whole load cannot falsify a broken algorithm. The sample count is therefore a multiple of the summed weights.'

def validate_distribution(total, buckets) -> str | None:
    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        return f'分布断言 total（总请求数）须为正整数，实际 {total!r}'
    if not isinstance(buckets, list) or len(buckets) < 2:
        return f'分布断言至少需 2 个桶（每后端一个）才有分布可验，实际 {(len(buckets) if isinstance(buckets, list) else buckets)!r} 个'
    sum_lo = sum_hi = sum_exp = 0
    for i, b in enumerate(buckets):
        if not isinstance(b, dict):
            return f'bucket[{i}] 不是 dict'
        if not str(b.get('anchor', '')).strip():
            return f'bucket[{i}] 缺 anchor（后端标识，如成员 IP/名字，用于把命中数锚定到该后端）'
        expected = b.get('expected')
        tol = b.get('tol', 0)
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            return f"bucket[{i}]({b.get('anchor')}) expected（期望命中数）须为非负整数，实际 {expected!r}"
        if not isinstance(tol, int) or isinstance(tol, bool) or tol < 0:
            return f"bucket[{i}]({b.get('anchor')}) tol（容差）须为非负整数，实际 {tol!r}"
        lo, hi = _bucket_bounds(expected, tol)
        if hi >= total:
            return f"bucket[{i}]({b.get('anchor')}) 区间 [{lo},{hi}] 上界 ≥ 总请求数 {total}——单桶宽到可容纳全部流量，对「算法失效=流量全压一个后端」不可证伪=恒真。收紧容差让 hi < {total}。"
        sum_lo += lo
        sum_hi += hi
        sum_exp += expected
    if not sum_lo <= total <= sum_hi:
        return f'守恒矛盾：各桶区间和 [Σlo={sum_lo}, Σhi={sum_hi}] 容纳不下总请求数 {total}（实际总命中必 == 总请求数）。检查期望/容差，确保 Σlo ≤ {total} ≤ Σhi。'
    if abs(sum_exp - total) > len(buckets):
        return f'分布中心偏移：Σ期望命中 {sum_exp} 与总请求数 {total} 相差 > 桶数 {len(buckets)}——rr 应每桶≈N/k、wrr 应每桶≈N×w_i/Σw，Σ期望应≈总请求数。'
    return None

def expand_distribution_step(step: dict) -> tuple[list[dict] | None, str | None]:
    dist = step.get('dist') or {}
    total = dist.get('total')
    field = str(dist.get('field', ''))
    buckets = dist.get('buckets')
    err = validate_distribution(total, buckets)
    if err:
        return (None, err)
    out: list[dict] = []
    for b in buckets:
        anchor = str(b['anchor'])
        lo, hi = _bucket_bounds(int(b['expected']), int(b.get('tol', 0)))
        rng = range_regex_for_count(lo, hi)
        tmpl = b.get('pattern')
        if tmpl:
            if '{range}' not in str(tmpl):
                return (None, f'bucket({anchor}) 的 pattern 模板必须含 {{range}} 占位')
            g = str(tmpl).replace('{range}', rng)
        else:
            g = f'{anchor}[^\\n]*{field}{rng}'
        try:
            re.compile(g, re.DOTALL)
        except re.error as exc:
            return (None, f'bucket({anchor}) generated an invalid regex: {exc}')
        from cex_core.engine.case_compiler.regex_anchor_proof import RegexAnchorAnalysisUnavailable, analyze_regex_anchors
        try:
            contradiction = analyze_regex_anchors(g).contradiction
        except RegexAnchorAnalysisUnavailable:
            contradiction = ''
        if contradiction:
            return (None, f'bucket({anchor}) generated an impossible regex: {contradiction}. The default layout is anchor[^\\n]*field{{range}}; field is a count prefix, not a complete row pattern. For another layout supply a complete bucket pattern containing {{range}}.')
        expanded = {'E': 'check_point', 'F': 'found', 'G': g, 'desc': str(b.get('desc') or f'{anchor} 池累计命中应在 {lo} 到 {hi} 次之间')}
        if step.get('exempt') is True:
            expanded['exempt'] = True
            expanded['reason_code'] = str(step.get('reason_code') or '').strip()
        out.append(expanded)
    return (out, None)

def _is_dist_step(step) -> bool:
    return isinstance(step, dict) and str(step.get('F', '')).strip() == 'dist' and bool(step.get('dist'))

def expand_distribution_steps(steps: list) -> tuple[list | None, list | None, str | None]:
    new_steps: list = []
    plan: list[tuple[str, int]] = []
    for s in steps:
        if _is_dist_step(s):
            expanded, err = expand_distribution_step(s)
            if err:
                return (None, None, err)
            new_steps.extend(expanded)
            plan.append(('dist', len(expanded)))
        else:
            new_steps.append(s)
            plan.append(('normal', 1))
    return (new_steps, plan, None)

def expand_provenance_steps_with_plan(prov_steps_raw, plan, *, source_steps=None, expanded_steps=None):
    if not isinstance(prov_steps_raw, list) or len(prov_steps_raw) != len(plan):
        return prov_steps_raw
    can_issue_receipts = isinstance(source_steps, list) and len(source_steps) == len(plan) and isinstance(expanded_steps, list) and (sum((n for _kind, n in plan)) == len(expanded_steps))
    out: list = []
    expanded_cursor = 0
    for source_index, (raw, (kind, n)) in enumerate(zip(prov_steps_raw, plan)):
        if kind == 'dist':
            ref = ''
            assertion_type = None
            observation_ref = ''
            expectation_id = ''
            semantic_key = ''
            if isinstance(raw, dict):
                ref = (raw.get('source') or {}).get('ref', '') or ''
                assertion_type = raw.get('assertion_type')
                observation_ref = str(raw.get('observation_ref') or '').strip()
                expectation_id = str(raw.get('expectation_id') or '').strip()
                semantic_key = str(raw.get('semantic_key') or '').strip()
            if (expectation_id or semantic_key) and (not can_issue_receipts):
                raise ValueError('distribution fan-out carries assertion identity but no derivation receipt can be recomputed: the bucket rows would share one expectation_id with no machine-readable grouping marker — the group is keyed by expectation_id, and each row needs its receipt.output_ordinal plus a source_input the compiler can replay to recompute the group size. Pass source_steps and expanded_steps so the compiler can mint distribution.interval receipts.')
            for ordinal in range(n):
                expanded = {'E': 'check_point', 'F': 'found', 'G': '', 'layer': 'V', 'source': {'kind': 'distribution_derived', 'ref': ref}}
                if can_issue_receipts:
                    from cex_core.engine.case_compiler.provenance_ir import build_config_binding_derivation_receipt
                    source_step = source_steps[source_index]
                    source_input = source_step.get('dist') if isinstance(source_step, dict) else None
                    output_step = expanded_steps[expanded_cursor + ordinal]
                    receipt, error = build_config_binding_derivation_receipt(source_kind='distribution_derived', recipe_id=ref, rule_id='distribution.interval', source_input=source_input, output_step=output_step, output_ordinal=ordinal)
                    if receipt is None:
                        raise ValueError(error)
                    expanded['source'] = {'kind': 'distribution_derived', 'ref': receipt['recipe_id'], 'receipt': receipt}
                if isinstance(assertion_type, dict):
                    expanded['assertion_type'] = dict(assertion_type)
                if observation_ref:
                    expanded['observation_ref'] = observation_ref
                if expectation_id:
                    expanded['expectation_id'] = expectation_id
                if semantic_key:
                    expanded['semantic_key'] = semantic_key
                out.append(expanded)
        else:
            out.append(raw)
        expanded_cursor += n
    return out
