const _FOUND_OPS = new Set(["found", "not_found", "abs_found", "found_times"]);

export function assertion_block_kinds(): Set<string> {
  const { CRITERION_CARRIERS } = require("./criterion_carriers");
  const out = new Set<string>();
  for (const group of CRITERION_CARRIERS) {
    for (const carrier of group.carriers) {
      if (String(carrier.block_kind || "").trim()) {
        out.add(carrier.block_kind);
      }
    }
  }
  return out;
}

export const GP_NO_MEANINGFUL_ASSERTION = "GP002";
export const GP_CODES = new Set([GP_NO_MEANINGFUL_ASSERTION]);

export class GraphIssue {
  code: string;
  severity: string;
  path: string;
  message: string;
  evidence: Record<string, any>;
  constructor(code: string, severity: string, path: string, message: string, evidence: Record<string, any> = {}) {
    this.code = code;
    this.severity = severity;
    this.path = path;
    this.message = message;
    this.evidence = evidence;
    Object.freeze(this);
  }
}

export class StepGraphReport {
  ok: boolean;
  issues: GraphIssue[];
  stats: Record<string, number>;
  constructor(ok: boolean, issues: GraphIssue[] = [], stats: Record<string, number> = {}) {
    this.ok = ok;
    this.issues = issues;
    this.stats = stats;
    Object.freeze(this);
  }
  get errors(): GraphIssue[] {
    return this.issues.filter((i) => i.severity === "error");
  }
  get warnings(): GraphIssue[] {
    return this.issues.filter((i) => i.severity === "warning");
  }
}

function _norm(value: any): string {
  return String(value || "").trim();
}

function _hasMeaningfulAssert(step: Record<string, any>): boolean {
  const kind = _norm(step.kind).toUpperCase();
  const payload = MEANINGFUL_ASSERT_PAYLOAD[kind];
  return Boolean(
    _assertsListPayload(step) ||
      (kind === "STEP" && _norm(step.E) === "check_point" && _FOUND_OPS.has(_norm(step.F)) && _norm(step.G)) ||
      (payload || _noPayload)(step)
  );
}

function _assertsListPayload(step: Record<string, any>): boolean {
  const rows = Array.isArray(step.asserts) ? step.asserts : [];
  return rows.some(
    (row: any) =>
      typeof row === "object" && row !== null && !Array.isArray(row) && _FOUND_OPS.has(_norm(row.op)) && Boolean(_norm(row.pattern))
  );
}

function _noPayload(_step: Record<string, any>): boolean {
  return false;
}

function _distributionPayload(step: Record<string, any>): boolean {
  const { distribution_count_binding_error } = require("./distribution_assertion");
  const buckets = step.buckets;
  if (!Array.isArray(buckets) || !buckets.length) {
    return false;
  }
  return distribution_count_binding_error(step.field, buckets) === null;
}

export const MEANINGFUL_ASSERT_PAYLOAD: Record<string, (step: Record<string, any>) => boolean> = {
  OBSERVE_ASSERT: _assertsListPayload,
  EXPECT_FROM: (step) => _FOUND_OPS.has(_norm(step.op)),
  OBSERVE_DIST: (step) => _distributionPayload(step),
  OBSERVE_MEMBER: (step) => Array.isArray(step.ips) && (step.ips || []).some((item: any) => _norm(item)),
  OBSERVE_EXIT: (step) => Boolean(_norm(step.expect)),
  CAPTURE_COMPARE: (_step) => true,
};

export function check_step_graph(blocks: any): StepGraphReport {
  const issues: GraphIssue[] = [];
  if (!Array.isArray(blocks) || !blocks.length) {
    return new StepGraphReport(true, [], { steps: 0 });
  }
  const payloads = blocks.map((step) => _hasMeaningfulAssert(typeof step === "object" && step !== null ? step : {}));
  if (!payloads.some(Boolean)) {
    issues.push(
      new GraphIssue(
        GP_NO_MEANINGFUL_ASSERTION,
        "error",
        "steps",
        "no meaningful assertion in this case (the assertion payload for its block kind is empty or unsupported)",
        {}
      )
    );
  }
  const ok = !issues.some((issue) => issue.severity === "error");
  return new StepGraphReport(ok, issues, { steps: payloads.length });
}
