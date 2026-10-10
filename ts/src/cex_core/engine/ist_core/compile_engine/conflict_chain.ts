import { accepts_schema } from "../../common/schema_identity";

export const SpecValue = {
  FOUND: "found",
  ABSENT: "absent",
  UNKNOWN: "unknown",
} as const;
export type SpecValue = (typeof SpecValue)[keyof typeof SpecValue];

export interface SpecEvaluation {
  value: SpecValue;
  source: string;
  reason: string;
  ticket_consulted: boolean;
  retryable: boolean;
}

const _OPENKM_FOUND = new Set(["bound"]);
const _OPENKM_ABSENT = new Set(["no_governing_spec"]);
const _SPEC_AMBIGUOUS = new Set(["ambiguous"]);
const _SPEC_UNKNOWN = new Set(["unavailable", "invalid_source"]);
const _TICKET_FOUND = new Set(["resolved"]);
const _TICKET_ABSENT = new Set(["candidate_only", "missing", "no_ticket_reference", "resolved_absent"]);

function _status(value: any): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function evaluate_spec(openkm_status: any, ticket_status: any = null, opts: { ticket_eligible?: any } = {}): SpecEvaluation {
  const openkm = _status(openkm_status);
  if (_OPENKM_FOUND.has(openkm)) {
    return { value: SpecValue.FOUND, source: "openkm", reason: "openkm_found", ticket_consulted: false, retryable: false };
  }
  if (_SPEC_AMBIGUOUS.has(openkm)) {
    return { value: SpecValue.ABSENT, source: "openkm", reason: "openkm_ambiguous", ticket_consulted: false, retryable: false };
  }
  if (_SPEC_UNKNOWN.has(openkm) || !_OPENKM_ABSENT.has(openkm)) {
    return { value: SpecValue.UNKNOWN, source: "openkm", reason: "openkm_unresolved", ticket_consulted: false, retryable: true };
  }
  const ticket = _status(ticket_status);
  if (_TICKET_FOUND.has(ticket)) {
    if (opts.ticket_eligible === true) {
      return { value: SpecValue.FOUND, source: "ticket", reason: "ticket_found", ticket_consulted: true, retryable: false };
    }
    return { value: SpecValue.UNKNOWN, source: "ticket", reason: "ticket_found_not_eligible", ticket_consulted: true, retryable: true };
  }
  if (_SPEC_AMBIGUOUS.has(ticket)) {
    return { value: SpecValue.ABSENT, source: "ticket", reason: "ticket_ambiguous", ticket_consulted: true, retryable: false };
  }
  if (_TICKET_ABSENT.has(ticket)) {
    return { value: SpecValue.ABSENT, source: "ticket", reason: "ticket_absent", ticket_consulted: true, retryable: false };
  }
  return { value: SpecValue.UNKNOWN, source: "ticket", reason: "ticket_unresolved", ticket_consulted: true, retryable: true };
}

export function spec_absent(governing_status: any): boolean {
  return _OPENKM_ABSENT.has(_status(governing_status)) || _SPEC_AMBIGUOUS.has(_status(governing_status));
}

export const CompletenessOutcome = {
  COMPARE: "compare",
  SCENARIO_1: "scenario_1",
  CONTINUE_CASE: "continue_case",
  SCENARIO_2: "scenario_2",
  WAIT_SPEC_RETRY: "wait_spec_retry",
  HOLD_INVALID_INPUT: "hold_invalid_input",
} as const;
export type CompletenessOutcome = (typeof CompletenessOutcome)[keyof typeof CompletenessOutcome];

export function classify_completeness(spec_value: SpecValue | string, case_complete: any): CompletenessOutcome {
  let spec: SpecValue;
  try {
    spec = spec_value as SpecValue;
    if (!Object.values(SpecValue).includes(spec)) throw new Error("invalid");
  } catch {
    return CompletenessOutcome.HOLD_INVALID_INPUT;
  }
  if (typeof case_complete !== "boolean") {
    return CompletenessOutcome.HOLD_INVALID_INPUT;
  }
  if (spec === SpecValue.UNKNOWN) {
    return CompletenessOutcome.WAIT_SPEC_RETRY;
  }
  if (spec === SpecValue.FOUND) {
    return case_complete ? CompletenessOutcome.COMPARE : CompletenessOutcome.SCENARIO_1;
  }
  return case_complete ? CompletenessOutcome.CONTINUE_CASE : CompletenessOutcome.SCENARIO_2;
}

export const Scenario3Decision = {
  USE_X: "xml_replace_command",
  KEEP_CASE_BLOCKED: "xml_keep_case_blocked",
  ABANDON: "abandon_generation",
} as const;
export type Scenario3Decision = (typeof Scenario3Decision)[keyof typeof Scenario3Decision];

export const Scenario4Option = {
  USE_X_EXPECTATION: "use_xml_expectation",
  USE_CASE_EXPECTATION: "use_case_expectation",
  ABANDON: "abandon_generation",
} as const;
export type Scenario4Option = (typeof Scenario4Option)[keyof typeof Scenario4Option];

const _SCENARIO4_OPTIONS = [Scenario4Option.USE_X_EXPECTATION, Scenario4Option.USE_CASE_EXPECTATION, Scenario4Option.ABANDON];
const _SCENARIO4_OPTIONS_AFTER_X = [Scenario4Option.USE_X_EXPECTATION, Scenario4Option.ABANDON];

export interface Scenario4Plan {
  valid: boolean;
  options: Scenario4Option[];
  basis_command: string | null;
  reason: string;
}

export function scenario4_plan(opts: {
  original_command: any;
  rewritten_command?: any;
  scenario3_decision?: Scenario3Decision | string | null;
}): Scenario4Plan {
  const original = typeof opts.original_command === "string" ? opts.original_command.trim() : "";
  const rewritten = typeof opts.rewritten_command === "string" ? opts.rewritten_command.trim() : "";
  if (opts.scenario3_decision === null || opts.scenario3_decision === undefined) {
    if (!original) {
      return { valid: false, options: [], basis_command: null, reason: "original_command_missing" };
    }
    return { valid: true, options: [..._SCENARIO4_OPTIONS], basis_command: original, reason: "original_command" };
  }
  let decision: Scenario3Decision;
  try {
    decision = opts.scenario3_decision as Scenario3Decision;
    if (!Object.values(Scenario3Decision).includes(decision)) throw new Error("invalid");
  } catch {
    return { valid: false, options: [], basis_command: null, reason: "scenario3_decision_unknown" };
  }
  if (decision === Scenario3Decision.USE_X) {
    if (!rewritten) {
      return { valid: false, options: [], basis_command: null, reason: "rewritten_command_missing" };
    }
    return { valid: true, options: [..._SCENARIO4_OPTIONS_AFTER_X], basis_command: rewritten, reason: "rewritten_command" };
  }
  return { valid: true, options: [], basis_command: null, reason: "scenario3_terminal" };
}

function _isSubsetOf<T>(a: Set<T>, b: Set<T>): boolean {
  return [...a].every((x) => b.has(x));
}

export const DeltaAction = {
  CONTINUE: "continue",
  TERMINATE: "terminate",
  ABANDON: "abandon",
} as const;
export type DeltaAction = (typeof DeltaAction)[keyof typeof DeltaAction];

const _ACTION_STRICTNESS: Record<DeltaAction, number> = {
  [DeltaAction.CONTINUE]: 0,
  [DeltaAction.TERMINATE]: 1,
  [DeltaAction.ABANDON]: 2,
};

export interface DeltaDecision {
  delta_id: string;
  action: DeltaAction;
}

export interface DeltaReduction {
  valid: boolean;
  action: DeltaAction;
  reason: string;
  expected_count: number;
  decided_count: number;
}

export interface DeltaFrontierReduction {
  valid: boolean;
  original_delta_ids: string[];
  effective_delta_ids: string[];
  pruned_delta_ids: string[];
  reduction: DeltaReduction;
  reason: string;
}

function _invalid_delta_reduction(reason: string, opts: { expected_count?: number; decided_count?: number } = {}): DeltaReduction {
  return {
    valid: false,
    action: DeltaAction.TERMINATE,
    reason,
    expected_count: opts.expected_count ?? 0,
    decided_count: opts.decided_count ?? 0,
  };
}

function _parse_delta_decision(value: any): DeltaDecision | null {
  let delta_id: any;
  let action: any;
  if (typeof value === "object" && value !== null && "delta_id" in value && "action" in value) {
    delta_id = value.delta_id;
    action = value.action;
  } else {
    return null;
  }
  if (typeof delta_id !== "string" || !delta_id.trim()) return null;
  let parsed_action: DeltaAction;
  try {
    parsed_action = action as DeltaAction;
    if (!Object.values(DeltaAction).includes(parsed_action)) throw new Error("invalid");
  } catch {
    return null;
  }
  return { delta_id: delta_id.trim(), action: parsed_action };
}

export function reduce_delta_decisions(expected_delta_ids: any, decisions: any): DeltaReduction {
  if (!Array.isArray(expected_delta_ids) || typeof expected_delta_ids === "string") {
    return _invalid_delta_reduction("expected_delta_ids_invalid");
  }
  const expected: string[] = [];
  for (const raw of expected_delta_ids) {
    if (typeof raw !== "string" || !raw.trim()) {
      return _invalid_delta_reduction("expected_delta_id_invalid");
    }
    expected.push(raw.trim());
  }
  const expected_count = expected.length;
  if (new Set(expected).size !== expected_count) {
    return _invalid_delta_reduction("expected_delta_id_duplicate", { expected_count });
  }
  if (!Array.isArray(decisions) || typeof decisions === "string") {
    return _invalid_delta_reduction("decisions_invalid", { expected_count });
  }
  const parsed: DeltaDecision[] = [];
  for (const raw of decisions) {
    const item = _parse_delta_decision(raw);
    if (item === null) {
      return _invalid_delta_reduction("decision_invalid", { expected_count, decided_count: parsed.length });
    }
    parsed.push(item);
  }
  const decided_count = parsed.length;
  const decision_ids = parsed.map((item) => item.delta_id);
  if (new Set(decision_ids).size !== decided_count) {
    return _invalid_delta_reduction("decision_delta_id_duplicate", { expected_count, decided_count });
  }
  const expected_set = new Set(expected);
  const decision_set = new Set(decision_ids);
  if (![...decision_set].every((x) => expected_set.has(x))) {
    return _invalid_delta_reduction("decision_delta_id_unknown", { expected_count, decided_count });
  }
  if (decision_set.size !== expected_set.size) {
    return _invalid_delta_reduction("decision_missing", { expected_count, decided_count });
  }
  const action = parsed.reduce<DeltaAction>(
    (max, item) => (_ACTION_STRICTNESS[item.action] > _ACTION_STRICTNESS[max] ? item.action : max),
    DeltaAction.CONTINUE
  );
  return { valid: true, action, reason: "complete", expected_count, decided_count };
}

export const CONFLICT_CHAIN_SCHEMA = "ist.delta.conflict-chain";
export const CONFLICT_DECISION_SCHEMA = "ist.delta.conflict-decision";
export const BATCH_CONFLICT_DECISION_SCHEMA = "ist.delta.batch-conflict-decision";
export const BATCH_NEED_BINDING_MIGRATION_SCHEMA = "ist.delta.needs-decision-binding-migration";
export const BATCH_USE_CASE = "batch_use_case";
export const BATCH_USE_XML = "batch_use_xml";
export const BATCH_ABANDON = "batch_abandon";
export const BATCH_CONFLICT_TOKENS = new Set([BATCH_USE_CASE, BATCH_USE_XML, BATCH_ABANDON]);
export const BATCH_BINDING_FIELDS = ["case_manifest_sha256", "capability_projection_sha256", "governing_spec_sha256"];
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _LEGACY_SCENARIO_BY_CLAIM_KIND: Record<string, string> = {
  spec_case_conflict: "scenario_1",
  scenario2_incomplete_case: "scenario_2",
  xml_command_shape_conflict: "scenario_3",
  xml_expectation_conflict: "scenario_4",
};
const _CONFLICT_SCENARIOS = new Set(["scenario_1", "scenario_2", "scenario_3", "scenario_4", "spec_unknown"]);

export function claim_conflict_scenario(claim: any): string {
  if (typeof claim !== "object" || claim === null) return "";
  const explicit = String(claim.conflict_scenario ?? "").trim();
  if (explicit) {
    return _CONFLICT_SCENARIOS.has(explicit) ? explicit : "";
  }
  return _LEGACY_SCENARIO_BY_CLAIM_KIND[String(claim.claim_kind ?? "").trim()] ?? "";
}

export function claim_delta_id(claim: any): string {
  if (typeof claim !== "object" || claim === null) return "";
  const explicit = String(claim.delta_id ?? "").trim();
  if (explicit) return explicit;
  const payload: Record<string, any> = {};
  for (const [key, value] of Object.entries(claim)) {
    if (String(key) !== "decision_binding") payload[String(key)] = value;
  }
  try {
    const encoded = JSON.stringify(payload);
    return crypto.createHash("sha256").update(encoded, "utf8").digest("hex");
  } catch {
    return "";
  }
}

export function conflict_token_action(token: any): DeltaAction | null {
  const value = String(token ?? "").trim();
  if (["xml_replace_command", "use_xml_expectation", "use_case_expectation"].includes(value)) {
    return DeltaAction.CONTINUE;
  }
  if (value === "xml_keep_case_blocked") {
    return DeltaAction.TERMINATE;
  }
  if (value === "abandon_generation") {
    return DeltaAction.ABANDON;
  }
  return null;
}

export function reduce_delta_frontier(claims: any, decisions: any): DeltaFrontierReduction {
  const invalid = _invalid_delta_reduction("delta_frontier_invalid");
  if (!Array.isArray(claims) || claims.length === 0 || !Array.isArray(decisions) || typeof decisions === "string") {
    return { valid: false, original_delta_ids: [], effective_delta_ids: [], pruned_delta_ids: [], reduction: invalid, reason: "frontier_input_invalid" };
  }
  const original: string[] = [];
  const scenarios: Record<string, string> = {};
  for (const claim of claims) {
    const scenario = claim_conflict_scenario(claim);
    const delta_id = claim_delta_id(claim);
    if (!["scenario_3", "scenario_4"].includes(scenario) || !delta_id) {
      return { valid: false, original_delta_ids: [...original], effective_delta_ids: [], pruned_delta_ids: [], reduction: invalid, reason: "frontier_claim_invalid" };
    }
    if (delta_id in scenarios) {
      return { valid: false, original_delta_ids: [...original], effective_delta_ids: [], pruned_delta_ids: [], reduction: invalid, reason: "frontier_delta_duplicate" };
    }
    original.push(delta_id);
    scenarios[delta_id] = scenario;
  }
  const parsed: DeltaDecision[] = [];
  for (const raw of decisions) {
    const item = _parse_delta_decision(raw);
    if (item === null) {
      return {
        valid: false,
        original_delta_ids: [...original],
        effective_delta_ids: [],
        pruned_delta_ids: [],
        reduction: _invalid_delta_reduction("decision_invalid", { expected_count: original.length, decided_count: parsed.length }),
        reason: "frontier_decision_invalid",
      };
    }
    parsed.push(item);
  }
  const decision_ids = parsed.map((item) => item.delta_id);
  if (new Set(decision_ids).size !== decision_ids.length) {
    return { valid: false, original_delta_ids: [...original], effective_delta_ids: [], pruned_delta_ids: [], reduction: invalid, reason: "frontier_decision_duplicate" };
  }
  if (decision_ids.some((delta_id) => !(delta_id in scenarios))) {
    return { valid: false, original_delta_ids: [...original], effective_delta_ids: [], pruned_delta_ids: [], reduction: invalid, reason: "frontier_decision_unknown" };
  }
  const s3_ids = original.filter((delta_id) => scenarios[delta_id] === "scenario_3");
  const s4_ids = original.filter((delta_id) => scenarios[delta_id] === "scenario_4");
  const rows_by_id: Record<string, DeltaDecision> = Object.fromEntries(parsed.map((item) => [item.delta_id, item]));
  if (s3_ids.length) {
    const s3_rows = s3_ids.filter((delta_id) => delta_id in rows_by_id).map((delta_id) => rows_by_id[delta_id]);
    const s3_reduction = reduce_delta_decisions(s3_ids, s3_rows);
    if (!s3_reduction.valid) {
      return { valid: false, original_delta_ids: [...original], effective_delta_ids: [...s3_ids], pruned_delta_ids: [], reduction: s3_reduction, reason: "scenario3_incomplete" };
    }
    if (s3_reduction.action !== DeltaAction.CONTINUE) {
      if (s4_ids.some((delta_id) => delta_id in rows_by_id)) {
        return {
          valid: false,
          original_delta_ids: [...original],
          effective_delta_ids: [...s3_ids],
          pruned_delta_ids: [...s4_ids],
          reduction: s3_reduction,
          reason: "scenario4_decision_after_scenario3_terminal",
        };
      }
      return {
        valid: true,
        original_delta_ids: [...original],
        effective_delta_ids: [...s3_ids],
        pruned_delta_ids: [...s4_ids],
        reduction: s3_reduction,
        reason: "scenario4_pruned",
      };
    }
  }
  const reduction = reduce_delta_decisions(original, parsed);
  return {
    valid: reduction.valid,
    original_delta_ids: [...original],
    effective_delta_ids: [...original],
    pruned_delta_ids: [],
    reduction,
    reason: reduction.valid ? "complete" : reduction.reason,
  };
}

function _reject_non_json_numbers(value: any): void {
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new Error("conflict chain payload contains a non-finite number");
  }
  if (typeof value === "object" && value !== null) {
    if (Array.isArray(value)) {
      for (const nested of value) _reject_non_json_numbers(nested);
    } else {
      for (const [key, nested] of Object.entries(value)) {
        if (typeof key !== "string") throw new Error("conflict chain payload keys must be strings");
        _reject_non_json_numbers(nested);
      }
    }
  }
}

export function conflict_chain_id(payload: Record<string, any>): string {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    throw new Error("conflict chain payload must be a mapping");
  }
  _reject_non_json_numbers(payload);
  const envelope = { schema: CONFLICT_CHAIN_SCHEMA, payload };
  try {
    const encoded = JSON.stringify(envelope);
    return crypto.createHash("sha256").update(encoded, "utf8").digest("hex");
  } catch (exc) {
    throw new Error("conflict chain payload must be JSON serializable");
  }
}

export function decision_is_current(decision: any, current_chain_id: any, opts: { expected_delta_id?: string | null } = {}): boolean {
  if (typeof decision !== "object" || decision === null) return false;
  if (typeof current_chain_id !== "string" || !_SHA256_RE.test(current_chain_id)) return false;
  if (decision.schema !== CONFLICT_DECISION_SCHEMA) return false;
  if (decision.conflict_chain_id !== current_chain_id) return false;
  const delta_id = decision.delta_id;
  const token = decision.token;
  if (typeof delta_id !== "string" || !delta_id.trim()) return false;
  if (typeof token !== "string" || !token.trim()) return false;
  if (opts.expected_delta_id !== undefined && opts.expected_delta_id !== null && delta_id !== opts.expected_delta_id) return false;
  return decision.superseded !== true;
}

export function scenario1_claims_reviewable(claims: any): boolean {
  if (!Array.isArray(claims) || claims.length === 0) return false;
  for (const claim of claims) {
    if (typeof claim !== "object" || claim === null) return false;
    if (!accepts_schema(claim.schema, "ist.delta.conflict-claim") || claim.conflict_scenario !== "scenario_1" || !_SHA256_RE.test(String(claim.conflict_chain_id ?? "")) || JSON.stringify(claim.options) !== JSON.stringify(["abandon_generation"])) {
      return false;
    }
    const reason = String(claim.reason_code ?? claim.claim_kind ?? "");
    if (reason === "scenario1_spec_case_conflict") {
      if (["spec_quote", "case_quote", "spec_locator", "case_locator", "incompatibility"].some((field) => typeof claim[field] !== "string" || !String(claim[field]).trim())) {
        return false;
      }
      continue;
    }
    if (reason === "scenario1_case_incomplete") {
      const missing = claim.missing_fields;
      if (!Array.isArray(missing) || missing.length === 0 || missing.some((field: any) => !["description", "steps", "expectation"].includes(field))) {
        return false;
      }
      continue;
    }
    return false;
  }
  return true;
}

export const DIRECT_ABANDON_REASON_PREFIX = "direct:scenario12_abandon:";

export function is_direct_abandon_decision(fact: any): boolean {
  if (typeof fact !== "object" || fact === null || fact.ev !== "decision") return false;
  if (String(fact.answer ?? "").trim()) return false;
  return String(fact.reason ?? "").startsWith(DIRECT_ABANDON_REASON_PREFIX);
}

export function need_accepts_direct_abandon(need: any, scenario: any): boolean {
  if (typeof need !== "object" || need === null) return false;
  if (!["scenario_1", "scenario_2"].includes(String(scenario))) return false;
  if (String(need.conflict_scenario ?? "") !== String(scenario)) return false;
  return !("expected_delta_ids" in need) && need.auxiliary_claims === null;
}

export function capability_xml_claim_reviewable(claim: any): boolean {
  if (typeof claim !== "object" || claim === null) return false;
  if (claim.source_kind !== "CapabilityXml") return false;
  const scenario = String(claim.conflict_scenario ?? "");
  if (!["scenario_3", "scenario_4"].includes(scenario)) return false;
  const generation = claim.capability_generation;
  if (typeof generation !== "object" || generation === null) return false;
  if (["version", "build", "source_filename"].some((field) => typeof generation[field] !== "string" || !String(generation[field]).trim())) {
    return false;
  }
  if (!_SHA256_RE.test(String(generation.source_sha256 ?? "").toLowerCase())) return false;
  return claim.xml_present === true && typeof claim.xml_locator === "string" && String(claim.xml_locator ?? "").trim().length > 0;
}

export function capability_xml_expected_signable(claim: any): boolean {
  if (!capability_xml_claim_reviewable(claim) || typeof claim !== "object" || claim === null || claim_conflict_scenario(claim) !== "scenario_4") {
    return false;
  }
  const assertions = claim.xml_assertions;
  if (!Array.isArray(assertions) || assertions.length === 0) return false;
  try {
    const { VALID_CHECK_METHODS } = require("../../case_compiler/case_ir");
    for (const assertion of assertions) {
      if (typeof assertion !== "object" || assertion === null) return false;
      if (JSON.stringify(Object.keys(assertion).sort()) !== JSON.stringify(["locator", "operator", "value"])) return false;
      const operator = String(assertion.operator ?? "").trim();
      const value = assertion.value;
      const locator = String(assertion.locator ?? "").trim();
      if (!VALID_CHECK_METHODS.has(operator) || operator === "found_times" || typeof value !== "string" || !value || !locator) {
        return false;
      }
    }
    return true;
  } catch {
    return false;
  }
}

export function config_binding_claim_reviewable(claim: any): boolean {
  if (typeof claim !== "object" || claim === null || claim.source_kind !== "ConfigBinding" || claim_conflict_scenario(claim) !== "scenario_4" || !_SHA256_RE.test(String(claim.config_binding_receipt_sha256 ?? "")) || typeof claim.config_binding_receipt !== "object" || claim.config_binding_receipt === null) {
    return false;
  }
  try {
    const { ExpectedClaimReceipt, expected_source_group } = require("./authority_reconcile");
    const receipt = ExpectedClaimReceipt.from_dict({ ...claim.config_binding_receipt });
    const groups = new Set(receipt.claims.map((item: any) => expected_source_group(item.source_kind)));
    return receipt.receipt_sha256 === claim.config_binding_receipt_sha256 && groups.has("configbinding") && groups.size - (groups.has("configbinding") ? 1 : 0) >= 1;
  } catch {
    return false;
  }
}

export function batch_conflict_claim_reviewable(claim: any): boolean {
  if (typeof claim === "object" && claim !== null && claim.source_kind === "ConfigBinding") {
    return config_binding_claim_reviewable(claim);
  }
  const scenario = claim_conflict_scenario(claim);
  if (scenario === "scenario_3") {
    return capability_xml_claim_reviewable(claim);
  }
  if (scenario === "scenario_4") {
    return capability_xml_expected_signable(claim);
  }
  return false;
}

export function batch_conflict_decision_is_current(decision: any, bindings: any, opts: {
  conflict_claim_ids: any;
  auto_case_claim_ids?: any;
  conflict_autoids: any;
  batch_member_autoids: any;
}): boolean {
  if (typeof decision !== "object" || decision === null || typeof bindings !== "object" || bindings === null) return false;
  if (decision.schema !== BATCH_CONFLICT_DECISION_SCHEMA) return false;
  if (!BATCH_CONFLICT_TOKENS.has(String(decision.decision ?? ""))) return false;
  const signer = decision.signer;
  const { hil_identity_digest_is_current } = require("../tools/ask_user");
  if (
    typeof signer !== "object" ||
    signer === null ||
    signer.kind !== "ask_user" ||
    !String(signer.question_id ?? "") ||
    !_SHA256_RE.test(String(signer.question_digest ?? "")) ||
    !hil_identity_digest_is_current(signer.hil_identity_sha256)
  ) {
    return false;
  }
  for (const field of BATCH_BINDING_FIELDS) {
    const current = String(bindings[field] ?? "").toLowerCase();
    if (!_SHA256_RE.test(current) || decision[field] !== current) {
      return false;
    }
  }

  function _closed_list(value: any): string[] | null {
    if (!Array.isArray(value)) return null;
    const items = value.map((item: any) => String(item));
    if (items.some((item: string) => !item) || JSON.stringify(items) !== JSON.stringify([...items].sort()) || new Set(items).size !== items.length) {
      return null;
    }
    return items;
  }

  const expected = {
    conflict_claim_ids: _closed_list(opts.conflict_claim_ids),
    auto_case_claim_ids: _closed_list(opts.auto_case_claim_ids ?? []),
    conflict_autoids: _closed_list(opts.conflict_autoids),
    batch_member_autoids: _closed_list(opts.batch_member_autoids),
  };
  if (Object.values(expected).some((value) => value === null)) return false;
  if (expected.conflict_claim_ids!.length === 0 || expected.conflict_autoids!.length === 0) return false;
  return Object.entries(expected).every(([field, value]) => JSON.stringify(decision[field]) === JSON.stringify(value));
}

export function batch_auto_case_decision_resolves(need: any, decision: any): boolean {
  if (typeof need !== "object" || need === null || typeof decision !== "object" || decision === null) return false;
  if (!accepts_schema(decision.schema, "ist.delta.batch-conflict-auto-resolution")) return false;
  if (decision.token !== BATCH_USE_CASE || decision.answer !== BATCH_USE_CASE || decision.conflict_scenario !== "scenario_4") return false;
  const ids = decision.auto_case_claim_ids;
  if (!Array.isArray(ids) || ids.length === 0 || JSON.stringify(ids) !== JSON.stringify([...ids].sort()) || new Set(ids).size !== ids.length || ids.some((value: any) => !_SHA256_RE.test(String(value ?? "")))) {
    return false;
  }
  const need_ids = need.batch_auto_case_claim_ids;
  if (!Array.isArray(need_ids) || JSON.stringify(need_ids) !== JSON.stringify([...need_ids].sort()) || new Set(need_ids).size !== need_ids.length || JSON.stringify(ids) !== JSON.stringify(need_ids) || Boolean(need.batch_conflict_claim_ids)) {
    return false;
  }
  for (const field of BATCH_BINDING_FIELDS) {
    if (!_SHA256_RE.test(String(need[field] ?? "")) || decision[field] !== need[field]) return false;
  }
  const members = need.batch_member_autoids;
  if (!Array.isArray(members) || JSON.stringify(members) !== JSON.stringify([...members].sort()) || members.length !== new Set(members).size || JSON.stringify(decision.batch_member_autoids) !== JSON.stringify(members) || !members.includes(String(need.aid ?? ""))) {
    return false;
  }
  const auxiliary = need.auxiliary_claims;
  if (!Array.isArray(auxiliary) || auxiliary.length === 0) {
    return !decision.auxiliary_decisions;
  }
  const expected = [...new Set(auxiliary.filter((claim: any) => typeof claim === "object" && claim !== null && accepts_schema(claim.schema, "ist.delta.conflict-claim") && claim.conflict_scenario === "spec_unknown").map((claim: any) => String(claim.conflict_chain_id ?? "")))].sort();
  const rows = decision.auxiliary_decisions;
  if (expected.length === 0 || !Array.isArray(rows)) return false;
  const actual = rows
    .filter((row: any) => typeof row === "object" && row !== null && accepts_schema(row.schema, "ist.delta.auxiliary-decision") && row.conflict_scenario === "spec_unknown" && ["retry_spec_lookup", "continue_without_spec"].includes(row.token))
    .map((row: any) => String(row.conflict_chain_id ?? ""));
  return actual.length === rows.length && JSON.stringify([...actual].sort()) === JSON.stringify(expected) && actual.length === new Set(actual).size;
}

export function batch_conflict_decision_resolves_need(need: any, decision: any): boolean {
  if (typeof need !== "object" || need === null || typeof decision !== "object" || decision === null) return false;
  if (decision.schema !== BATCH_CONFLICT_DECISION_SCHEMA) return false;
  const token = String(decision.decision ?? decision.token ?? "");
  if (!BATCH_CONFLICT_TOKENS.has(token)) return false;
  for (const field of BATCH_BINDING_FIELDS) {
    const current = String(need[field] ?? "").toLowerCase();
    if (!_SHA256_RE.test(current) || decision[field] !== current) return false;
  }

  function _closed(value: any, opts: { sha?: boolean } = {}): string[] | null {
    if (!Array.isArray(value)) return null;
    const items = value.map((item: any) => String(item));
    if (items.some((item: string) => !item) || JSON.stringify(items) !== JSON.stringify([...items].sort()) || items.length !== new Set(items).size || (opts.sha && items.some((item: string) => !_SHA256_RE.test(item)))) {
      return null;
    }
    return items;
  }

  const need_conflicts = _closed(need.batch_conflict_claim_ids, { sha: true });
  const need_auto = _closed(need.batch_auto_case_claim_ids ?? [], { sha: true });
  const decision_conflicts = _closed(decision.conflict_claim_ids, { sha: true });
  const decision_auto = _closed(decision.auto_case_claim_ids ?? [], { sha: true });
  const members = _closed(need.batch_member_autoids);
  const decision_members = _closed(decision.batch_member_autoids);
  const conflicted = _closed(decision.conflict_autoids);
  const aid = String(need.aid ?? "");
  const allows_batch_terminal = token === BATCH_ABANDON && members?.includes(aid);
  if (
    (!need_conflicts && !allows_batch_terminal) ||
    need_auto === null ||
    !decision_conflicts ||
    decision_auto === null ||
    !members ||
    JSON.stringify(members) !== JSON.stringify(decision_members) ||
    !conflicted ||
    (!conflicted.includes(aid) && !allows_batch_terminal) ||
    !_isSubsetOf(new Set(need_conflicts), new Set(decision_conflicts)) ||
    !_isSubsetOf(new Set(need_auto), new Set(decision_auto))
  ) {
    return false;
  }
  const scoped = _closed(decision.scope_claim_ids ?? need_conflicts, { sha: true });
  if (JSON.stringify(scoped) !== JSON.stringify(need_conflicts)) return false;
  if (allows_batch_terminal) return true;
  const auxiliary = need.auxiliary_claims;
  if (!Array.isArray(auxiliary) || auxiliary.length === 0) {
    return !decision.auxiliary_decisions;
  }
  const expected_chains = [...new Set(auxiliary.filter((claim: any) => typeof claim === "object" && claim !== null && accepts_schema(claim.schema, "ist.delta.conflict-claim") && claim.conflict_scenario === "spec_unknown").map((claim: any) => String(claim.conflict_chain_id ?? "")))].sort();
  const rows = decision.auxiliary_decisions;
  if (expected_chains.length === 0 || !Array.isArray(rows)) return false;
  const actual_chains: string[] = [];
  for (const row of rows) {
    if (typeof row !== "object" || row === null || !accepts_schema(row.schema, "ist.delta.auxiliary-decision") || row.conflict_scenario !== "spec_unknown" || !["retry_spec_lookup", "continue_without_spec"].includes(row.token)) {
      return false;
    }
    actual_chains.push(String(row.conflict_chain_id ?? ""));
  }
  return JSON.stringify([...actual_chains].sort()) === JSON.stringify(expected_chains) && actual_chains.length === new Set(actual_chains).size;
}

export function needs_decision_fact_sha256(need: any): string {
  if (typeof need !== "object" || need === null) return "";
  try {
    const raw = JSON.stringify(need);
    return crypto.createHash("sha256").update(raw, "utf8").digest("hex");
  } catch {
    return "";
  }
}

export function batch_conflict_binding_migration_resolves_need(need: any, decision: any, migration: any): boolean {
  if (![need, decision, migration].every((value) => typeof value === "object" && value !== null)) return false;
  if (
    migration.ev !== "needs_decision_binding_migrated" ||
    migration.schema !== BATCH_NEED_BINDING_MIGRATION_SCHEMA ||
    String(migration.aid ?? "") !== String(need.aid ?? "") ||
    String(migration.question_id ?? "") !== String(need.question_id ?? "") ||
    migration.needs_decision_sha256 !== needs_decision_fact_sha256(need) ||
    String(decision.scope_autoid ?? "") !== String(need.aid ?? "") ||
    migration.decision !== String(decision.decision ?? decision.token ?? "")
  ) {
    return false;
  }
  const receipt_sha = String(migration.batch_receipt_sha256 ?? "");
  if (!_SHA256_RE.test(receipt_sha) || decision.batch_receipt_sha256 !== receipt_sha) return false;
  const from_bindings = migration.from_bindings;
  const to_bindings = migration.to_bindings;
  if (typeof from_bindings !== "object" || from_bindings === null || typeof to_bindings !== "object" || to_bindings === null) return false;
  const expected_from: Record<string, string> = {};
  const expected_to: Record<string, string> = {};
  for (const field of BATCH_BINDING_FIELDS) {
    expected_from[field] = String(need[field] ?? "").toLowerCase();
    expected_to[field] = String(decision[field] ?? "").toLowerCase();
  }
  if (
    JSON.stringify({ ...from_bindings }) !== JSON.stringify(expected_from) ||
    JSON.stringify({ ...to_bindings }) !== JSON.stringify(expected_to) ||
    JSON.stringify(expected_from) === JSON.stringify(expected_to) ||
    Object.values(expected_from).some((value) => !_SHA256_RE.test(value)) ||
    Object.values(expected_to).some((value) => !_SHA256_RE.test(value))
  ) {
    return false;
  }
  const need_scope = need.batch_conflict_claim_ids ?? [];
  const decision_scope = decision.scope_claim_ids ?? [];
  if (!Array.isArray(need_scope) || !Array.isArray(decision_scope) || JSON.stringify(migration.scope_claim_ids) !== JSON.stringify(need_scope) || JSON.stringify(decision_scope) !== JSON.stringify(need_scope)) {
    return false;
  }
  const rebased_need = { ...need, ...expected_to };
  return batch_conflict_decision_resolves_need(rebased_need, decision);
}

export const ReentryAction = {
  RERUN_CHAIN: "rerun_chain",
  ABANDON: "abandon",
} as const;
export type ReentryAction = (typeof ReentryAction)[keyof typeof ReentryAction];

export interface ReentryReduction {
  valid: boolean;
  action: ReentryAction;
  next_round: number | null;
  invalidate_decisions: boolean;
  reason: string;
}

export function reduce_blocked_reentry(opts: { rounds_used: any; max_rounds: any }): ReentryReduction {
  if (typeof opts.rounds_used !== "number" || typeof opts.max_rounds !== "number" || opts.rounds_used < 0 || opts.max_rounds <= 0) {
    return { valid: false, action: ReentryAction.ABANDON, next_round: null, invalidate_decisions: true, reason: "round_counter_invalid" };
  }
  if (opts.rounds_used >= opts.max_rounds) {
    return { valid: true, action: ReentryAction.ABANDON, next_round: null, invalidate_decisions: true, reason: "round_cap_reached" };
  }
  return { valid: true, action: ReentryAction.RERUN_CHAIN, next_round: opts.rounds_used + 1, invalidate_decisions: true, reason: "rerun_full_chain" };
}

import crypto from "node:crypto";
