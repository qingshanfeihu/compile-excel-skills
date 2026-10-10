import crypto from "node:crypto";
import path from "node:path";
import { P as Path } from "../../_py";
import { scrub_text } from "../security_scrub";
import { MAX_ERROR_TEXT_CHARS, REASON_CODES } from "../tools/device/batch_result_protocol";
import { accepts_schema } from "../../common/schema_identity";

export const MAX_EXECUTION_ATTEMPTS = 3;
export const NO_PROGRESS_STALL_HITS = 2;
export const NO_DEVICE_REEXECUTION_REASON_CODES = new Set(["result_channel_unavailable"]);
export const EXECUTION_FAILURE_EVENT = "execution_failure";
export const EXECUTION_SUCCESS_EVENT = "execution_success";
export const REENTRY_CLEAR_EVENTS = new Set(["conflict_chain_reentered"]);

export const FailureCategory = {
  ENGINE_REJECTION: "engine_rejection",
  RUNTIME_INFRASTRUCTURE: "runtime_infrastructure",
  DEVICE_PREREQUISITE: "device_prerequisite",
  CONNECTION: "connection",
  OCCUPANCY: "occupancy",
  ENVIRONMENT: "environment",
  UNKNOWN: "unknown",
} as const;
export type FailureCategory = (typeof FailureCategory)[keyof typeof FailureCategory];

export const FailureAction = {
  RETRY: "retry",
  BLOCKED: "blocked",
  IST_CORE_DEFECT: "ist_core_defect",
  UNABLE_TO_COMPILE: "unable_to_compile",
} as const;
export type FailureAction = (typeof FailureAction)[keyof typeof FailureAction];

export const BUDGETED_CATEGORIES: Set<string> = new Set([FailureCategory.ENGINE_REJECTION, FailureCategory.UNKNOWN]);
export const NO_PROGRESS_CATEGORIES: Set<string> = new Set([FailureCategory.RUNTIME_INFRASTRUCTURE]);
export const PREREQUISITE_CATEGORIES: Set<string> = new Set([FailureCategory.DEVICE_PREREQUISITE, FailureCategory.CONNECTION]);
export const WAIT_CATEGORIES: Set<string> = new Set([FailureCategory.OCCUPANCY, FailureCategory.ENVIRONMENT]);

const _REASON_CODE_CATEGORY: Record<string, FailureCategory> = {
  device_busy: FailureCategory.OCCUPANCY,
  env_pool_exhausted: FailureCategory.ENVIRONMENT,
  invalid_request: FailureCategory.ENGINE_REJECTION,
  environment_unavailable: FailureCategory.ENVIRONMENT,
  device_unreachable: FailureCategory.ENVIRONMENT,
  device_prerequisite_unmet: FailureCategory.DEVICE_PREREQUISITE,
  bed_identity_mismatch: FailureCategory.ENGINE_REJECTION,
  artifact_identity_mismatch: FailureCategory.ENGINE_REJECTION,
  delivery_failed: FailureCategory.RUNTIME_INFRASTRUCTURE,
  execution_failed: FailureCategory.UNKNOWN,
  session_desync: FailureCategory.RUNTIME_INFRASTRUCTURE,
  result_channel_unavailable: FailureCategory.RUNTIME_INFRASTRUCTURE,
  producer_protocol_error: FailureCategory.ENGINE_REJECTION,
};

const _FAILURE_REASON_CODES = new Set([...REASON_CODES].filter((c: string) => c !== "completed"));
if (Object.keys(_REASON_CODE_CATEGORY).length !== _FAILURE_REASON_CODES.size || ![..._FAILURE_REASON_CODES].every((c: string) => c in _REASON_CODE_CATEGORY)) {
  throw new Error(
    `execution failure reason mapping is not exhaustive: missing=${[..._FAILURE_REASON_CODES].filter((c: string) => !(c in _REASON_CODE_CATEGORY)).sort()}, extra=${Object.keys(_REASON_CODE_CATEGORY).filter((c: string) => !_FAILURE_REASON_CODES.has(c)).sort()}`
  );
}

const _IMPLEMENTATION_SOURCE_PATHS = [
  "main/ist_core/compile_engine/execution_failure.py",
  "main/ist_core/compile_engine/nodes.py",
  "main/ist_core/tools/device/batch_result_protocol.py",
  "main/ist_core/tools/device/batch_tools.py",
  "main/case_compiler/device_mcp_client.py",
];

function _execution_implementation_material(): Buffer {
  const root = new Path(path.resolve(__dirname, "../../.."));
  const chunks: Buffer[] = [];
  for (const relative of _IMPLEMENTATION_SOURCE_PATHS) {
    const p = root.join(relative);
    if (!p.is_file() || p.is_symlink()) {
      throw new Error(`execution implementation source unavailable: ${relative}`);
    }
    try {
      const source = p.read_text("utf8");
      // Normalize: remove docstrings (approximated by removing triple-quoted strings at start of blocks)
      const normalized = source.replace(/"""[\s\S]*?"""/g, "").replace(/'''[\s\S]*?'''/g, "");
      chunks.push(Buffer.from(relative, "utf8"), Buffer.from("\0", "utf8"), Buffer.from(normalized, "utf8"), Buffer.from("\0", "utf8"));
    } catch (exc) {
      throw new Error(`execution implementation source invalid: ${relative}`);
    }
  }
  return Buffer.concat(chunks);
}

let _implementation_sha256_cache: string | null = null;
export function current_execution_implementation_sha256(): string {
  if (_implementation_sha256_cache === null) {
    _implementation_sha256_cache = crypto.createHash("sha256").update(_execution_implementation_material()).digest("hex");
  }
  return _implementation_sha256_cache;
}

export interface ExecutionIdentity {
  autoid: string;
  artifact_sha256: string;
  bed_host: string;
  build: string;
  implementation_sha256: string;
}

export function createExecutionIdentity(autoid: string, artifact_sha256: string, bed_host: string, build: string): ExecutionIdentity {
  for (const [field_name, value] of Object.entries({ autoid, artifact_sha256, bed_host })) {
    if (typeof value !== "string" || !value) {
      throw new Error(`execution identity ${field_name} must be non-empty text`);
    }
  }
  if (typeof build !== "string") {
    throw new Error("execution identity build must be text");
  }
  return { autoid, artifact_sha256, bed_host, build, implementation_sha256: current_execution_implementation_sha256() };
}

export interface ExecutionFailureDecision {
  identity: ExecutionIdentity;
  reason_code: string;
  category: FailureCategory;
  attempt: number;
  action: FailureAction;
  record_failure: boolean;
  prerequisite_receipt_sha256: string;
  fingerprint_hits: number;
  no_progress_fingerprint: string;
  decision_axis: string[];
  exhausted: boolean;
}

export function reason_code_categories(): Record<string, FailureCategory> {
  return { ..._REASON_CODE_CATEGORY };
}

export function classify_reason_code(reason_code: string): FailureCategory {
  const { UnrecognizedRoutingValue, recognize } = require("./routing_closed_sets");
  if (reason_code === "completed") throw new Error("completed is not an execution failure reason");
  const recognized = recognize("execution_reason_codes", reason_code);
  if (recognized instanceof UnrecognizedRoutingValue) return recognized as any;
  return _REASON_CODE_CATEGORY[recognized];
}

function _normalize_failure_reason(reason_code: string, prerequisite_receipt_sha256: string): [string, string] {
  const receipt = String(prerequisite_receipt_sha256 ?? "");
  const receipt_valid = /^[0-9a-f]{64}$/.test(receipt);
  if (reason_code === "device_prerequisite_unmet") {
    if (receipt_valid) return [reason_code, receipt];
    return ["producer_protocol_error", ""];
  }
  if (receipt) return ["producer_protocol_error", ""];
  return [reason_code, ""];
}

function _classify_recorded_failure(fact: Record<string, any>): [string, FailureCategory, string] {
  const [reason_code, receipt_sha256] = _normalize_failure_reason(String(fact.reason_code ?? ""), String(fact.prerequisite_receipt_sha256 ?? ""));
  try {
    return [reason_code, classify_reason_code(reason_code), receipt_sha256];
  } catch {
    const { UnrecognizedRoutingValue } = require("./routing_closed_sets");
    return [reason_code, new UnrecognizedRoutingValue("execution_reason_codes", reason_code) as any, receipt_sha256];
  }
}

function _recognized_failure_category(reason_code: any): FailureCategory | any {
  const { UnrecognizedRoutingValue, recognize } = require("./routing_closed_sets");
  const recognized = recognize("execution_reason_codes", reason_code);
  if (recognized instanceof UnrecognizedRoutingValue) return recognized;
  return _REASON_CODE_CATEGORY[recognized];
}

export function is_occupancy_reason_code(reason_code: string): boolean | any {
  const category = _recognized_failure_category(reason_code);
  const { UnrecognizedRoutingValue } = require("./routing_closed_sets");
  if (category instanceof UnrecognizedRoutingValue) return category;
  return category === FailureCategory.OCCUPANCY;
}

export function is_environment_blocked_reason_code(reason_code: string): boolean | any {
  const category = _recognized_failure_category(reason_code);
  const { UnrecognizedRoutingValue } = require("./routing_closed_sets");
  if (category instanceof UnrecognizedRoutingValue) return category;
  return category === FailureCategory.ENVIRONMENT;
}

export function is_runtime_infrastructure_reason_code(reason_code: string): boolean | any {
  const category = _recognized_failure_category(reason_code);
  const { UnrecognizedRoutingValue } = require("./routing_closed_sets");
  if (category instanceof UnrecognizedRoutingValue) return category;
  return category === FailureCategory.RUNTIME_INFRASTRUCTURE;
}

export function is_runtime_infrastructure_terminal_fact(fact: Record<string, any>): boolean {
  return (
    typeof fact === "object" &&
    fact !== null &&
    ["blocked", "ist_core_defect"].includes(String(fact.ev ?? "")) &&
    is_runtime_infrastructure_reason_code(String(fact.reason_code ?? "")) === true
  );
}

export function is_runtime_infrastructure_action(action: any): boolean | any {
  const { UnrecognizedRoutingValue, recognize } = require("./routing_closed_sets");
  const recognized = recognize("failure_action", String(action?.value ?? action ?? ""));
  if (recognized instanceof UnrecognizedRoutingValue) return recognized;
  return recognized === FailureAction.BLOCKED;
}

export function is_case_scoped_terminal_action(action: any): boolean | any {
  const { UnrecognizedRoutingValue, recognize } = require("./routing_closed_sets");
  const recognized = recognize("failure_action", String(action?.value ?? action ?? ""));
  if (recognized instanceof UnrecognizedRoutingValue) return recognized;
  return ([FailureAction.IST_CORE_DEFECT, FailureAction.UNABLE_TO_COMPILE] as string[]).includes(recognized);
}

const _CATEGORY_TERMINAL_ACTION: Record<FailureCategory, FailureAction> = {
  [FailureCategory.DEVICE_PREREQUISITE]: FailureAction.UNABLE_TO_COMPILE,
  [FailureCategory.CONNECTION]: FailureAction.UNABLE_TO_COMPILE,
  [FailureCategory.OCCUPANCY]: FailureAction.RETRY,
  [FailureCategory.ENVIRONMENT]: FailureAction.RETRY,
  [FailureCategory.RUNTIME_INFRASTRUCTURE]: FailureAction.BLOCKED,
  [FailureCategory.ENGINE_REJECTION]: FailureAction.IST_CORE_DEFECT,
  [FailureCategory.UNKNOWN]: FailureAction.IST_CORE_DEFECT,
};

export function terminal_action_for_category(category: FailureCategory): FailureAction | any {
  const { UnrecognizedRoutingValue, recognize } = require("./routing_closed_sets");
  const recognized = recognize("failure_category", String((category as any)?.value ?? category ?? ""));
  if (recognized instanceof UnrecognizedRoutingValue) return recognized;
  return _CATEGORY_TERMINAL_ACTION[recognized as FailureCategory];
}

export function no_progress_fingerprint(identity: Record<string, any> | ExecutionIdentity, reason_code: string): string {
  let fields: Record<string, any>;
  if ("autoid" in identity) {
    fields = {
      aid: identity.autoid,
      artifact_sha256: identity.artifact_sha256,
      bed_host: identity.bed_host,
      build: identity.build,
      implementation_sha256: identity.implementation_sha256,
    };
  } else {
    fields = identity;
  }
  const material = [
    String(fields.aid ?? fields.autoid ?? ""),
    String(fields.artifact_sha256 ?? ""),
    String(fields.bed_host ?? ""),
    String(fields.build ?? ""),
    String(fields.implementation_sha256 ?? ""),
    String(reason_code ?? ""),
  ].join("\n");
  return crypto.createHash("sha256").update(material, "utf8").digest("hex");
}

function _decision_axis_for_action(action: FailureAction): string[] {
  const { axis_payload_for_event } = require("./routing_closed_sets");
  return [...axis_payload_for_event(action)];
}

function _matches_identity(fact: Record<string, any>, identity: ExecutionIdentity): boolean {
  return (
    String(fact.aid ?? "") === identity.autoid &&
    String(fact.artifact_sha256 ?? "") === identity.artifact_sha256 &&
    String(fact.bed_host ?? "") === identity.bed_host &&
    String(fact.build ?? "") === identity.build &&
    String(fact.implementation_sha256 ?? "") === identity.implementation_sha256
  );
}

export function identity_group(facts: Iterable<Record<string, any>>, identity: ExecutionIdentity): Record<string, any>[] {
  const group: Record<string, any>[] = [];
  for (const fact of facts) {
    if (typeof fact !== "object" || fact === null) continue;
    const event = String(fact.ev ?? "");
    if (REENTRY_CLEAR_EVENTS.has(event) && String(fact.aid ?? "") === identity.autoid) {
      group.push(fact);
      continue;
    }
    if (_matches_identity(fact, identity)) group.push(fact);
  }
  return group;
}

export function execution_failure_fact(
  decision: ExecutionFailureDecision,
  opts: { failure_evidence?: Record<string, any> | null; error_text?: string } = {}
): Record<string, any> {
  const fact: Record<string, any> = {
    ev: EXECUTION_FAILURE_EVENT,
    aid: decision.identity.autoid,
    artifact_sha256: decision.identity.artifact_sha256,
    bed_host: decision.identity.bed_host,
    build: decision.identity.build,
    implementation_sha256: decision.identity.implementation_sha256,
    reason_code: decision.reason_code,
    category: decision.category,
    attempt: decision.attempt,
    action: decision.action,
    fingerprint_hits: decision.fingerprint_hits,
    no_progress_fingerprint: decision.no_progress_fingerprint,
    decision_axis: decision.decision_axis,
    prerequisite_receipt_sha256: decision.prerequisite_receipt_sha256,
  };
  const safe_error_text = scrub_text(opts.error_text ?? "", { scrub_paths: true }).trim().slice(0, MAX_ERROR_TEXT_CHARS);
  if (safe_error_text) fact.error_text = safe_error_text;
  let default_result_channel_evidence: Record<string, any> | null = null;
  let failure_evidence = opts.failure_evidence ?? null;
  if (decision.reason_code === "result_channel_unavailable") {
    default_result_channel_evidence = {
      schema: "ist.execution-failure-evidence",
      layer: "framework_result_channel",
      state: "unavailable",
      source: "mysql",
      evidence_scope: "case_artifact",
      evidence_file: "device_echo.raw.txt",
    };
    if (failure_evidence === null) failure_evidence = default_result_channel_evidence;
  }
  if (typeof failure_evidence === "object" && failure_evidence !== null && !Array.isArray(failure_evidence)) {
    const allowed = new Set(["schema", "layer", "state", "source", "settle_attempts", "error_type", "task_id", "evidence_scope", "evidence_file", "evidence_sha256"]);
    const raw_evidence_keys = new Set(Object.keys(failure_evidence).map(String));
    const evidence: Record<string, any> = {};
    for (const [key, value] of Object.entries(failure_evidence)) {
      if (allowed.has(String(key))) evidence[String(key)] = value;
    }
    if (
      [...raw_evidence_keys].every((k) => allowed.has(k)) &&
      accepts_schema(evidence.schema, "ist.execution-failure-evidence") &&
      evidence.layer === "framework_result_channel" &&
      ["query_error", "missing_after_done", "unavailable"].includes(evidence.state) &&
      evidence.source === "mysql" &&
      (!("task_id" in evidence) || (typeof evidence.task_id === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(evidence.task_id) && !evidence.task_id.includes(".."))) &&
      (evidence.evidence_scope === undefined || evidence.evidence_scope === "case_artifact") &&
      (!("settle_attempts" in evidence) || (typeof evidence.settle_attempts === "number" && Number.isInteger(evidence.settle_attempts) && evidence.settle_attempts >= 0)) &&
      typeof evidence.evidence_file === "string" &&
      path.basename(String(evidence.evidence_file)) === String(evidence.evidence_file) &&
      evidence.evidence_file === "device_echo.raw.txt" &&
      (!("error_type" in evidence) || (typeof evidence.error_type === "string" && evidence.error_type.length <= 120)) &&
      (!("evidence_sha256" in evidence) || (typeof evidence.evidence_sha256 === "string" && /^[0-9a-f]{64}$/.test(evidence.evidence_sha256)))
    ) {
      fact.failure_evidence = evidence;
    }
  }
  if (default_result_channel_evidence !== null && !("failure_evidence" in fact)) {
    fact.failure_evidence = default_result_channel_evidence;
  }
  return fact;
}

export function execution_success_fact(identity: ExecutionIdentity): Record<string, string> {
  return {
    ev: EXECUTION_SUCCESS_EVENT,
    aid: identity.autoid,
    artifact_sha256: identity.artifact_sha256,
    bed_host: identity.bed_host,
    build: identity.build,
    implementation_sha256: identity.implementation_sha256,
  };
}

export function reduce_execution_failure_facts(
  group: Iterable<Record<string, any>>,
  opts: {
    current_reason: string;
    prerequisite_receipt_sha256?: string;
    fingerprint_identity?: Record<string, any> | ExecutionIdentity | null;
  }
): Record<string, any> {
  const [current_reason, current_receipt_sha256] = _normalize_failure_reason(opts.current_reason, opts.prerequisite_receipt_sha256 ?? "");
  const current_category = classify_reason_code(current_reason);
  let budgeted = 0;
  let prerequisite_attempts = 0;
  let fingerprint_hits: Record<string, number> = {};
  let no_reexecution_terminal: [string, FailureCategory, string, number, FailureAction, number, string] | null = null;
  let stalled_terminal: [string, FailureCategory, string, number, FailureAction, number, string] | null = null;
  let budget_terminal: [string, FailureCategory, string, string] | null = null;
  let prerequisite_terminal: [string, FailureCategory, string] | null = null;

  function _reset(): void {
    budgeted = 0;
    prerequisite_attempts = 0;
    fingerprint_hits = {};
    no_reexecution_terminal = null;
    stalled_terminal = null;
    budget_terminal = null;
    prerequisite_terminal = null;
  }

  function _fingerprint(reason: string): string {
    if (opts.fingerprint_identity === null || opts.fingerprint_identity === undefined) return reason;
    return no_progress_fingerprint(opts.fingerprint_identity, reason);
  }

  for (const fact of group) {
    if (typeof fact !== "object" || fact === null) continue;
    const event = String(fact.ev ?? "");
    if (event === EXECUTION_SUCCESS_EVENT || REENTRY_CLEAR_EVENTS.has(event)) {
      _reset();
      continue;
    }
    if (event !== EXECUTION_FAILURE_EVENT) continue;
    const [old_reason, old_category, old_receipt_sha256] = _classify_recorded_failure(fact);
    const { UnrecognizedRoutingValue } = require("./routing_closed_sets");
    if ((old_category as any) instanceof UnrecognizedRoutingValue) continue;
    if (WAIT_CATEGORIES.has(old_category)) continue;
    if (PREREQUISITE_CATEGORIES.has(old_category)) {
      if (prerequisite_attempts < MAX_EXECUTION_ATTEMPTS) {
        prerequisite_attempts += 1;
        if (prerequisite_attempts === MAX_EXECUTION_ATTEMPTS) {
          prerequisite_terminal = [old_reason, old_category, old_receipt_sha256];
        }
      }
      continue;
    }
    const recorded_attempt = Number(fact.attempt ?? 0);
    const mark = _fingerprint(old_reason);
    if (BUDGETED_CATEGORIES.has(old_category)) {
      if (budgeted >= MAX_EXECUTION_ATTEMPTS) continue;
      budgeted += 1;
      if (NO_DEVICE_REEXECUTION_REASON_CODES.has(old_reason)) {
        no_reexecution_terminal = [old_reason, old_category, old_receipt_sha256, recorded_attempt || budgeted, terminal_action_for_category(old_category), 0, ""];
      }
      if (budgeted === MAX_EXECUTION_ATTEMPTS) {
        budget_terminal = [old_reason, old_category, old_receipt_sha256, mark];
      }
      continue;
    }
    if (NO_PROGRESS_CATEGORIES.has(old_category)) {
      const hits = (fingerprint_hits[old_reason] ?? 0) + 1;
      fingerprint_hits[old_reason] = hits;
      const action = terminal_action_for_category(old_category);
      const packed: [string, FailureCategory, string, number, FailureAction, number, string] = [
        old_reason,
        old_category,
        old_receipt_sha256,
        recorded_attempt || 1,
        action,
        hits,
        mark,
      ];
      if (NO_DEVICE_REEXECUTION_REASON_CODES.has(old_reason)) no_reexecution_terminal = packed;
      if (hits >= NO_PROGRESS_STALL_HITS) stalled_terminal = packed;
    }
  }

  if (no_reexecution_terminal !== null) {
    const [reason, category, receipt, attempt, action, hits, mark] = no_reexecution_terminal;
    return { reason_code: reason, category, attempt, action, record_failure: false, prerequisite_receipt_sha256: receipt, fingerprint_hits: hits, no_progress_fingerprint: mark };
  }
  if (stalled_terminal !== null) {
    const [reason, category, receipt, attempt, action, hits, mark] = stalled_terminal;
    return { reason_code: reason, category, attempt, action, record_failure: false, prerequisite_receipt_sha256: receipt, fingerprint_hits: hits, no_progress_fingerprint: mark };
  }
  if (prerequisite_terminal !== null) {
    const [reason, category, receipt] = prerequisite_terminal;
    return {
      reason_code: reason,
      category,
      attempt: MAX_EXECUTION_ATTEMPTS,
      action: terminal_action_for_category(category),
      record_failure: false,
      prerequisite_receipt_sha256: receipt,
      fingerprint_hits: 0,
      no_progress_fingerprint: "",
    };
  }
  if (budgeted >= MAX_EXECUTION_ATTEMPTS && budget_terminal !== null) {
    const [reason, category, receipt, mark] = budget_terminal;
    return {
      reason_code: reason,
      category,
      attempt: MAX_EXECUTION_ATTEMPTS,
      action: terminal_action_for_category(category),
      record_failure: false,
      prerequisite_receipt_sha256: receipt,
      fingerprint_hits: 0,
      no_progress_fingerprint: "",
    };
  }
  let attempt = budgeted + 1;
  let mark = "";
  let hits = 0;
  const { UNRECOGNIZED_ROUTING_VALUE, UnrecognizedRoutingValue } = require("./routing_closed_sets");
  if ((current_category as any) instanceof UnrecognizedRoutingValue) {
    return {
      reason_code: UNRECOGNIZED_ROUTING_VALUE,
      category: current_category,
      attempt,
      action: FailureAction.BLOCKED,
      record_failure: true,
      prerequisite_receipt_sha256: current_receipt_sha256,
      fingerprint_hits: 0,
      no_progress_fingerprint: "",
      unrecognized: current_category,
    };
  }
  let action: FailureAction;
  if (WAIT_CATEGORIES.has(current_category)) {
    action = FailureAction.RETRY;
  } else if (PREREQUISITE_CATEGORIES.has(current_category)) {
    attempt = prerequisite_attempts + 1;
    action = attempt >= MAX_EXECUTION_ATTEMPTS ? terminal_action_for_category(current_category) : FailureAction.RETRY;
  } else if (NO_DEVICE_REEXECUTION_REASON_CODES.has(current_reason)) {
    action = terminal_action_for_category(current_category);
    hits = (fingerprint_hits[current_reason] ?? 0) + 1;
    mark = _fingerprint(current_reason);
  } else if (NO_PROGRESS_CATEGORIES.has(current_category)) {
    hits = (fingerprint_hits[current_reason] ?? 0) + 1;
    mark = _fingerprint(current_reason);
    action = hits >= NO_PROGRESS_STALL_HITS ? terminal_action_for_category(current_category) : FailureAction.RETRY;
  } else {
    action = attempt >= MAX_EXECUTION_ATTEMPTS ? terminal_action_for_category(current_category) : FailureAction.RETRY;
  }
  return {
    reason_code: current_reason,
    category: current_category,
    attempt,
    action,
    record_failure: true,
    prerequisite_receipt_sha256: current_receipt_sha256,
    fingerprint_hits: hits,
    no_progress_fingerprint: mark,
  };
}

export function reduce_execution_failure(opts: {
  identity: ExecutionIdentity;
  reason_code: string;
  prerequisite_receipt_sha256?: string;
  facts: Iterable<Record<string, any>>;
}): ExecutionFailureDecision {
  const folded = reduce_execution_failure_facts(identity_group(opts.facts, opts.identity), {
    current_reason: opts.reason_code,
    prerequisite_receipt_sha256: opts.prerequisite_receipt_sha256 ?? "",
    fingerprint_identity: opts.identity,
  });
  let action = folded.action;
  const { UnrecognizedRoutingValue } = require("./routing_closed_sets");
  if (action instanceof UnrecognizedRoutingValue) action = FailureAction.BLOCKED;
  return {
    identity: opts.identity,
    reason_code: folded.reason_code,
    category: folded.category,
    attempt: folded.attempt,
    action,
    record_failure: folded.record_failure,
    prerequisite_receipt_sha256: folded.prerequisite_receipt_sha256,
    fingerprint_hits: folded.fingerprint_hits,
    no_progress_fingerprint: folded.no_progress_fingerprint,
    decision_axis: _decision_axis_for_action(action),
    exhausted: action !== FailureAction.RETRY,
  };
}
