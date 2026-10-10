import { analyze_regex_anchors, RegexAnchorAnalysisUnavailable } from "./regex_anchor_proof";

export const DISTRIBUTION_DECLARATION_CONTRACT: Record<string, string> = {
  default_layout: "anchor[^\\n]*field{range}",
  field:
    "A regex prefix immediately before the count in the same line as anchor. It is not a complete row pattern. A bucket's complete pattern ignores this field, so an empty string is valid only when every bucket provides its own template containing {range}; with neither, nothing says where the count is read and the block is rejected.",
  bucket_pattern:
    "Optional complete regex template containing {range}. Only {range} is replaced by the bounded integer regex; anchor and field are not prepended. Use this form when the documented identifier and count span lines or require a different order. Bind the count to this bucket's record and preserve record boundaries; a broad cross-record wildcard can read another bucket's count. Layout evidence never signs the expected count.",
  sampling:
    "total is the author's compiled sample-count declaration used to derive count intervals. OBSERVE_DIST executes cmd once and checks that output; it does not repeat requests, reset counters, or count executed requests. Arrange the required traffic and observation in executable blocks and retain evidence connecting executed samples to the measured counters. A valid interval or a declared total does not prove that execution link.",
};

function _isMap(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _bucketBindsItsOwnCount(bucket: any): boolean {
  if (!_isMap(bucket)) {
    return false;
  }
  const template = bucket.pattern;
  return typeof template === "string" && template.includes("{range}");
}

export function distribution_count_binding_error(field: any, buckets: any): string | null {
  if (!Array.isArray(buckets) || !buckets.length) {
    return null;
  }
  if (String(field || "").trim()) {
    return null;
  }
  const unbound = buckets.map((bucket, index) => (!_bucketBindsItsOwnCount(bucket) ? index : -1)).filter((i) => i >= 0);
  if (!unbound.length) {
    return null;
  }
  return `this distribution check does not say where the count is read: field is empty and bucket(s) ${JSON.stringify(unbound)} carry no complete pattern containing {range}, so the generated assertion is the bucket anchor, anything else on that line, then a bare number - it matches whichever number appears first after the anchor, which need not be the hit count, and the check cannot tell a correct distribution from a wrong one. Either set field to the text that immediately precedes the count on the anchor's line, or give every bucket its own complete pattern containing {range}.`;
}

function _fillByNines(num: number, nines: number): number {
  return num - (num % Math.pow(10, nines)) + (Math.pow(10, nines) - 1);
}

function _fillByZeros(num: number, zeros: number): number {
  return num - (num % Math.pow(10, zeros)) - 1;
}

function _splitToRanges(lo: number, hi: number): Array<[number, number]> {
  const stops = new Set<number>([hi]);
  let nines = 1;
  let stop = _fillByNines(lo, nines);
  while (lo <= stop && stop < hi) {
    stops.add(stop);
    nines += 1;
    stop = _fillByNines(lo, nines);
  }
  let zeros = 1;
  stop = _fillByZeros(hi, zeros);
  while (lo < stop && stop <= hi) {
    stops.add(stop);
    zeros += 1;
    stop = _fillByZeros(hi, zeros);
  }
  const ranges: Array<[number, number]> = [];
  let start = lo;
  for (const s of [...stops].sort((a, b) => a - b)) {
    ranges.push([start, s]);
    start = s + 1;
  }
  return ranges;
}

function _rangeToPattern(start: number, stop: number): string {
  let pattern = "";
  const ss = String(start);
  const se = String(stop);
  for (let i = 0; i < ss.length; i++) {
    pattern += ss[i] === se[i] ? ss[i] : `[${ss[i]}-${se[i]}]`;
  }
  return pattern;
}

export function int_range_to_regex(lo: number, hi: number): string {
  if (lo > hi) {
    throw new Error(`区间非法 lo=${lo} > hi=${hi}`);
  }
  if (lo < 0) {
    throw new Error(`区间下界须 >=0，实际 lo=${lo}`);
  }
  const seen = new Set<string>();
  const uniq: string[] = [];
  for (const [a, b] of _splitToRanges(lo, hi)) {
    const p = _rangeToPattern(a, b);
    if (!seen.has(p)) {
      seen.add(p);
      uniq.push(p);
    }
  }
  return uniq.join("|");
}

export function range_regex_for_count(lo: number, hi: number): string {
  return `(?<!\\d)(?:${int_range_to_regex(lo, hi)})(?!\\d)`;
}

function _bucketBounds(expected: number, tol: number): [number, number] {
  return [Math.max(0, expected - tol), expected + tol];
}

export function distribution_tolerance_policy(opts: {
  independent_steps: boolean;
  min_interval_s: number;
  shared_bed_isolated: boolean;
}): Record<string, any> {
  const reasons: string[] = [];
  if (!opts.independent_steps) {
    reasons.push("shell_loop_or_compound_step");
  }
  if (opts.min_interval_s < 3.0) {
    reasons.push("cache_window_below_3s");
  }
  if (!opts.shared_bed_isolated) {
    reasons.push("shared_bed_counter_interference");
  }
  if (reasons.length) {
    return {
      status: "unknown",
      tolerance: null,
      reason_codes: reasons,
      basis: "sampling context is not equivalent to the controlled replay; do not turn this advisory into a compile error",
    };
  }
  return {
    status: "known",
    tolerance: 0,
    reason_codes: [],
    basis: "controlled replay uses independent framework steps, >=3s between requests, and isolated shared-bed counters",
  };
}

export const BUCKET_RULE_EN =
  "Every bucket keeps its authored weight share, the bucket counts sum to the sample count, and no single bucket interval reaches the sample count — a bucket wide enough to absorb the whole load cannot falsify a broken algorithm. The sample count is therefore a multiple of the summed weights.";

export function validate_distribution(total: any, buckets: any): string | null {
  if (typeof total !== "number" || !Number.isInteger(total) || total <= 0) {
    return `分布断言 total（总请求数）须为正整数，实际 ${JSON.stringify(total)}`;
  }
  if (!Array.isArray(buckets) || buckets.length < 2) {
    return `分布断言至少需 2 个桶（每后端一个）才有分布可验，实际 ${JSON.stringify(Array.isArray(buckets) ? buckets.length : buckets)} 个`;
  }
  let sumLo = 0;
  let sumHi = 0;
  let sumExp = 0;
  for (let i = 0; i < buckets.length; i++) {
    const b = buckets[i];
    if (!_isMap(b)) {
      return `bucket[${i}] 不是 dict`;
    }
    if (!String(b.anchor || "").trim()) {
      return `bucket[${i}] 缺 anchor（后端标识，如成员 IP/名字，用于把命中数锚定到该后端）`;
    }
    const expected = b.expected;
    const tol = b.tol ?? 0;
    if (typeof expected !== "number" || !Number.isInteger(expected) || expected < 0) {
      return `bucket[${i}](${b.anchor}) expected（期望命中数）须为非负整数，实际 ${JSON.stringify(expected)}`;
    }
    if (typeof tol !== "number" || !Number.isInteger(tol) || tol < 0) {
      return `bucket[${i}](${b.anchor}) tol（容差）须为非负整数，实际 ${JSON.stringify(tol)}`;
    }
    const [lo, hi] = _bucketBounds(expected, tol);
    if (hi >= total) {
      return `bucket[${i}](${b.anchor}) 区间 [${lo},${hi}] 上界 ≥ 总请求数 ${total}——单桶宽到可容纳全部流量，对「算法失效=流量全压一个后端」不可证伪=恒真。收紧容差让 hi < ${total}。`;
    }
    sumLo += lo;
    sumHi += hi;
    sumExp += expected;
  }
  if (!(sumLo <= total && total <= sumHi)) {
    return `守恒矛盾：各桶区间和 [Σlo=${sumLo}, Σhi=${sumHi}] 容纳不下总请求数 ${total}（实际总命中必 == 总请求数）。检查期望/容差，确保 Σlo ≤ ${total} ≤ Σhi。`;
  }
  if (Math.abs(sumExp - total) > buckets.length) {
    return `分布中心偏移：Σ期望命中 ${sumExp} 与总请求数 ${total} 相差 > 桶数 ${buckets.length}——rr 应每桶≈N/k、wrr 应每桶≈N×w_i/Σw，Σ期望应≈总请求数。`;
  }
  return null;
}

export function expand_distribution_step(step: Record<string, any>): [Array<Record<string, any>> | null, string | null] {
  const dist = step.dist || {};
  const total = dist.total;
  const field = String(dist.field || "");
  const buckets = dist.buckets;
  const err = validate_distribution(total, buckets);
  if (err) {
    return [null, err];
  }
  const out: Array<Record<string, any>> = [];
  for (const b of buckets) {
    const anchor = String(b.anchor);
    const [lo, hi] = _bucketBounds(Number(b.expected), Number(b.tol ?? 0));
    const rng = range_regex_for_count(lo, hi);
    const tmpl = b.pattern;
    let g: string;
    if (tmpl) {
      if (!String(tmpl).includes("{range}")) {
        return [null, `bucket(${anchor}) 的 pattern 模板必须含 {{range}} 占位`];
      }
      g = String(tmpl).replace("{range}", rng);
    } else {
      g = `${anchor}[^\\n]*${field}${rng}`;
    }
    try {
      new RegExp(g, "s");
    } catch (exc: any) {
      return [null, `bucket(${anchor}) generated an invalid regex: ${exc.message || exc}`];
    }
    let contradiction = "";
    try {
      contradiction = analyze_regex_anchors(g).contradiction;
    } catch (exc) {
      if (!(exc instanceof RegexAnchorAnalysisUnavailable)) throw exc;
    }
    if (contradiction) {
      return [
        null,
        `bucket(${anchor}) generated an impossible regex: ${contradiction}. The default layout is anchor[^\\n]*field{range}; field is a count prefix, not a complete row pattern. For another layout supply a complete bucket pattern containing {range}.`,
      ];
    }
    const expanded: Record<string, any> = {
      E: "check_point",
      F: "found",
      G: g,
      desc: String(b.desc || `${anchor} 池累计命中应在 ${lo} 到 ${hi} 次之间`),
    };
    if (step.exempt === true) {
      expanded.exempt = true;
      expanded.reason_code = String(step.reason_code || "").trim();
    }
    out.push(expanded);
  }
  return [out, null];
}

function _isDistStep(step: any): boolean {
  return _isMap(step) && String(step.F || "").trim() === "dist" && Boolean(step.dist);
}

export function expand_distribution_steps(steps: any[]): [any[] | null, Array<[string, number]> | null, string | null] {
  const newSteps: any[] = [];
  const plan: Array<[string, number]> = [];
  for (const s of steps) {
    if (_isDistStep(s)) {
      const [expanded, err] = expand_distribution_step(s);
      if (err) {
        return [null, null, err];
      }
      newSteps.push(...expanded!);
      plan.push(["dist", expanded!.length]);
    } else {
      newSteps.push(s);
      plan.push(["normal", 1]);
    }
  }
  return [newSteps, plan, null];
}

export function expand_provenance_steps_with_plan(
  prov_steps_raw: any,
  plan: any,
  opts: { source_steps?: any; expanded_steps?: any } = {}
): any {
  if (!Array.isArray(prov_steps_raw) || prov_steps_raw.length !== plan.length) {
    return prov_steps_raw;
  }
  const sourceSteps = opts.source_steps;
  const expandedSteps = opts.expanded_steps;
  const canIssueReceipts =
    Array.isArray(sourceSteps) &&
    sourceSteps.length === plan.length &&
    Array.isArray(expandedSteps) &&
    plan.reduce((a: number, [, n]: [string, number]) => a + n, 0) === expandedSteps.length;
  const out: any[] = [];
  let expandedCursor = 0;
  for (let sourceIndex = 0; sourceIndex < prov_steps_raw.length; sourceIndex++) {
    const raw = prov_steps_raw[sourceIndex];
    const [kind, n] = plan[sourceIndex];
    if (kind === "dist") {
      let ref = "";
      let assertionType: any = null;
      let observationRef = "";
      let expectationId = "";
      let semanticKey = "";
      if (_isMap(raw)) {
        ref = ((raw.source || {}).ref || "") || "";
        assertionType = raw.assertion_type;
        observationRef = String(raw.observation_ref || "").trim();
        expectationId = String(raw.expectation_id || "").trim();
        semanticKey = String(raw.semantic_key || "").trim();
      }
      if ((expectationId || semanticKey) && !canIssueReceipts) {
        throw new Error(
          "distribution fan-out carries assertion identity but no derivation receipt can be recomputed: the bucket rows would share one expectation_id with no machine-readable grouping marker — the group is keyed by expectation_id, and each row needs its receipt.output_ordinal plus a source_input the compiler can replay to recompute the group size. Pass source_steps and expanded_steps so the compiler can mint distribution.interval receipts."
        );
      }
      for (let ordinal = 0; ordinal < n; ordinal++) {
        const expanded: Record<string, any> = {
          E: "check_point",
          F: "found",
          G: "",
          layer: "V",
          source: { kind: "distribution_derived", ref },
        };
        if (canIssueReceipts) {
          const { build_config_binding_derivation_receipt } = require("./provenance_ir");
          const sourceStep = sourceSteps[sourceIndex];
          const sourceInput = _isMap(sourceStep) ? sourceStep.dist : null;
          const outputStep = expandedSteps[expandedCursor + ordinal];
          const [receipt, error] = build_config_binding_derivation_receipt({
            source_kind: "distribution_derived",
            recipe_id: ref,
            rule_id: "distribution.interval",
            source_input: sourceInput,
            output_step: outputStep,
            output_ordinal: ordinal,
          });
          if (receipt === null) {
            throw new Error(error);
          }
          expanded.source = { kind: "distribution_derived", ref: receipt.recipe_id, receipt };
        }
        if (_isMap(assertionType)) {
          expanded.assertion_type = { ...assertionType };
        }
        if (observationRef) {
          expanded.observation_ref = observationRef;
        }
        if (expectationId) {
          expanded.expectation_id = expectationId;
        }
        if (semanticKey) {
          expanded.semantic_key = semanticKey;
        }
        out.push(expanded);
      }
    } else {
      out.push(raw);
    }
    expandedCursor += n;
  }
  return out;
}
