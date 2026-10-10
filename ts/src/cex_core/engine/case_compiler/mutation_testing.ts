// 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mutation_testing.py（sha256 205e5e339a01d2c0）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { SCHEMA as PASS_AUDIT_SCHEMA } from "./pass_audit";
import { accepts_schema } from "../common/schema_identity";
import {
  ASSERTION_TYPE_SCHEMA,
  AUTHOR_DECLARABLE_EXEMPT_CODES,
  COMPILER_ISSUED_EXEMPT_CODES,
  EXEMPT_REASON_CODES,
  FLIP_CONTROL_UNCONSTRUCTIBLE_REASON,
  MUTATION_ROLE_CONTROL,
} from "./provenance_ir";

export const MUTATION_SCHEMA = "ist.ide.mutation";
export const LEGACY_DELIVERY_CREDENTIAL_SCHEMA = "ist.ide.legacy-delivery-credential";
export const EXEMPT_GOVERNANCE_SCHEMA = "ist.ide.exempt-governance";
export const EXEMPT_MAX_RATIO = 0.5;
export const EXEMPT_REVIEW_DAYS = 30;
const _INVERSE_ASSERTION: Record<string, string> = { found: "not_found", not_found: "found" };
const _ADVISORY_MESSAGES: Record<string, string> = { flip_baseline_unavailable: "干净态底账没有这条观测命令的可用记录，翻转判据交上机实证", vacuous_found_in_clean: "干净态底账已经满足这条正向断言，判别力灰显", flip_baseline_not_discriminating: "干净态底账不能把这条断言翻转过来，判别力交上机实证", [FLIP_CONTROL_UNCONSTRUCTIBLE_REASON]: "这条断言在案内构造不出反向对照，编译器已附豁免码，判别力交上机实证", non_readonly_probe: "这条断言的观测窗不是设备只读探针，编译器复算后自行签发豁免码，判别力交上机实证", inserted_observation_noninterference_unverified: "编译器已插入一次额外观测；该观测是否影响后续状态尚未核验" };
const _READONLY_WINDOW_HEADS = new Set(["show", "get"]);
const _NON_DEVICE_WINDOW_OBJECTS = new Set(["", "test_env", "time", "check_point"]);
const _CLIENT_CONTROL_SHELL_SYNTAX_RE = /[\r\n;&|`<>]|\$\(/;
const _MUTATION_BEFORE_RE = /^\[IDE-MUTATION-BEFORE:([1-9][0-9]*)\]$/;
const _MUTATION_CONTROL_RE = /^\[IDE-MUTATION-CONTROL:([1-9][0-9]*)\]$/;
export const ENGINE_COMPUTED_EXEMPT_CODES = new Set(["non_readonly_probe"]);
export const EXEMPT_ISSUER_COMPILER = "compiler";

function _isMapping(value: any): value is Record<string, any> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function _sha256Hex(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function _canonicalJson(value: any): string {
  return JSON.stringify(_sortKeys(value));
}

function _sortKeys(value: any): any {
  if (Array.isArray(value)) {
    return value.map(_sortKeys);
  }
  if (_isMapping(value)) {
    const out: Record<string, any> = {};
    for (const key of Object.keys(value).sort()) {
      out[key] = _sortKeys(value[key]);
    }
    return out;
  }
  return value;
}

function _readonly_command_head(command: string): boolean {
  const text = String(command || "").trim();
  if (!text) {
    return false;
  }
  return _READONLY_WINDOW_HEADS.has(text.split(/\s+/, 2)[0].toLowerCase());
}

function _readonly_device_window(command: string, window_e: string): boolean {
  return _readonly_command_head(command) && !_NON_DEVICE_WINDOW_OBJECTS.has(String(window_e || "").trim());
}

function _state_changing_config_step(step: any): boolean {
  if (!_isMapping(step)) {
    return false;
  }
  if (!["cmd_config", "cmds_config"].includes(String(step["F"] || "").trim())) {
    return false;
  }
  return !_readonly_device_window(String(step["G"] || ""), String(step["E"] || ""));
}

function _shlexSplit(text: string): string[] {
  const out: string[] = [];
  let current = "";
  let quote: string | null = null;
  let hasToken = false;
  for (const ch of text) {
    if (quote !== null) {
      if (ch === quote) {
        quote = null;
      } else if (ch === "\\" && quote === '"') {
        continue;
      } else {
        current += ch;
      }
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      hasToken = true;
      continue;
    }
    if (/\s/.test(ch)) {
      if (hasToken || current) {
        out.push(current);
        current = "";
        hasToken = false;
      }
      continue;
    }
    if (ch === "\\") {
      continue;
    }
    current += ch;
  }
  if (quote !== null) {
    throw new Error("No closing quotation");
  }
  if (hasToken || current) {
    out.push(current);
  }
  return out;
}

function _auto_in_case_window_error(command: string, window_e: string, opts: { assertion_count: number }): string {
  const text = String(command || "").trim();
  const eValue = String(window_e || "").trim();
  if (_readonly_device_window(text, eValue)) {
    return "";
  }
  if (eValue !== "test_env") {
    return "window is not a read-only device show/get command";
  }
  if (opts.assertion_count !== 1) {
    return "client pre-config control is limited to a case with exactly one product assertion so the extra observation cannot contaminate sibling statistics or ordering assertions";
  }
  if (!text || _CLIENT_CONTROL_SHELL_SYNTAX_RE.test(text)) {
    return "client pre-config control requires one observation command without shell chaining, pipes, redirection, substitution, or background syntax";
  }
  let probeHeads: Set<string>;
  try {
    const { verbs } = require("./domain_grammar");
    probeHeads = new Set(verbs("mutation_preconfig_client_probes"));
  } catch {
    return "client observation grammar is unavailable";
  }
  let commandText = text;
  if (commandText.length >= 2 && commandText[0] === commandText[commandText.length - 1] && ['"', "'"].includes(commandText[0])) {
    commandText = commandText.slice(1, -1).trim();
  }
  let parts: string[];
  try {
    parts = _shlexSplit(commandText);
  } catch {
    return "client observation command is not valid single-command shell syntax";
  }
  const head = parts.length ? parts[0].split("/").pop()!.toLowerCase() : "";
  if (!probeHeads.has(head)) {
    return "client pre-config control requires a command head from the mutation-specific generated domain grammar";
  }
  return "";
}

function _auto_in_case_window_supported(command: string, window_e: string, opts: { assertion_count: number }): boolean {
  return !_auto_in_case_window_error(command, window_e, opts);
}

export function mutation_control_order_failure(steps: Record<string, any>[]): string {
  function markerText(step: Record<string, any>): string {
    return String(step["desc"] || step["D"] || "").trim();
  }
  for (let index = 0; index < steps.length; index++) {
    const before = _MUTATION_BEFORE_RE.exec(markerText(steps[index]));
    if (before === null || before[0] !== markerText(steps[index])) {
      continue;
    }
    const ordinal = before[1];
    if (index + 1 >= steps.length) {
      return `mutation BEFORE ${ordinal} is not followed by its CONTROL row`;
    }
    const control = _MUTATION_CONTROL_RE.exec(markerText(steps[index + 1]));
    if (control === null || control[0] !== markerText(steps[index + 1])) {
      return `mutation BEFORE ${ordinal} is not followed by its CONTROL row`;
    }
    if (control[1] !== ordinal) {
      return `mutation BEFORE ${ordinal} is paired with another CONTROL ordinal`;
    }
    let cursor = index + 2;
    while (cursor < steps.length) {
      const marker = markerText(steps[cursor]);
      const beforeM = _MUTATION_BEFORE_RE.exec(marker);
      const controlM = _MUTATION_CONTROL_RE.exec(marker);
      if (!((beforeM !== null && beforeM[0] === marker) || (controlM !== null && controlM[0] === marker))) {
        break;
      }
      cursor += 1;
    }
    if (cursor >= steps.length || !_state_changing_config_step(steps[cursor])) {
      return `mutation BEFORE/CONTROL ${ordinal} does not precede its config anchor`;
    }
  }
  return "";
}

function _parse_requirements(value: any): [Record<string, any>[], string] {
  if (value === null || value === undefined || value === "") {
    return [[], ""];
  }
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch (exc) {
      return [[], `mutation requirements are not valid JSON: ${exc}`];
    }
  }
  if (!Array.isArray(value)) {
    return [[], "mutation requirements must be an array"];
  }
  if (!value.every((item) => _isMapping(item))) {
    return [[], "each mutation requirement must be an object"];
  }
  return [value.map((item) => ({ ...item })), ""];
}

export function derive_mutation_requirements(steps: Record<string, any>[], exemptions_value: any, opts: { device_build: string }): [Record<string, any>[], string] {
  const [exemptions, error] = _parse_requirements(exemptions_value);
  if (error) {
    return [[], error];
  }
  if (exemptions.length) {
    return [[], "mutation requirements are compiler-derived; declare only exempt=true and reason_code on the affected check_point step"];
  }
  const build = String(opts.device_build || "").trim();
  const assertionWindows: [string, string, string][] = [];
  let currentWindow = "";
  let currentWindowE = "";
  for (const step of steps) {
    if (!_isMapping(step)) {
      continue;
    }
    if (String(step["E"] || "").trim() === "check_point") {
      const exempt = step["exempt"];
      const reasonCode = String(step["reason_code"] || "").trim();
      if (!(exempt === null || exempt === undefined || exempt === false || exempt === true)) {
        return [[], "check_point exempt must be a boolean"];
      }
      if (exempt !== true && reasonCode) {
        return [[], "check_point reason_code is valid only when exempt=true"];
      }
      if (exempt === true && !AUTHOR_DECLARABLE_EXEMPT_CODES.has(reasonCode)) {
        return [[], `check_point Exempt.reason_code must be one of ${[...AUTHOR_DECLARABLE_EXEMPT_CODES].sort()}`];
      }
      assertionWindows.push([currentWindow, currentWindowE, exempt === true ? reasonCode : ""]);
      continue;
    }
    if (String(step["H"] || "").trim()) {
      continue;
    }
    currentWindow = String(step["G"] || "").trim();
    currentWindowE = String(step["E"] || "").trim();
  }
  const requirements: Record<string, any>[] = [];
  const assertionCount = assertionWindows.length;
  for (let index = 0; index < assertionWindows.length; index++) {
    const [command, windowE, reasonCode] = assertionWindows[index];
    const ordinal = index + 1;
    let engineComputed = ENGINE_COMPUTED_EXEMPT_CODES.has(reasonCode);
    if (engineComputed && _auto_in_case_window_supported(command, windowE, { assertion_count: assertionCount })) {
      engineComputed = false;
    }
    if (reasonCode) {
      const requirement: Record<string, any> = { assertion_ordinals: [ordinal], mode: "exempt", reason_code: reasonCode };
      if (engineComputed) {
        requirement["issuer"] = EXEMPT_ISSUER_COMPILER;
        requirement["auto_derived"] = true;
      }
      if (windowE === "test_env") {
        requirement["window_channel"] = "client";
      }
      requirements.push(requirement);
      requirements.push(requirement);
      continue;
    }
    if (!command) {
      return [[], `assertion ${ordinal} has no preceding observation window command`];
    }
    if (!build) {
      return [[], `assertion ${ordinal} cannot derive ledger mutation without the engine-issued device build`];
    }
    requirements.push({ assertion_ordinals: [ordinal], mode: "ledger", observation_command: command, device_build: build });
  }
  return [requirements, ""];
}

function _negative_target_introduced_by_forward_config(configStep: Record<string, any>, opts: { operator: string; pattern: string; device_build: string }): boolean {
  const { operator, pattern, device_build } = opts;
  if (operator !== "not_found" || !pattern) {
    return false;
  }
  const configText = String(configStep["G"] || "");
  if (!configText) {
    return false;
  }
  try {
    if (!new RegExp(pattern, "m").test(configText)) {
      return false;
    }
  } catch {
    return false;
  }
  let forwardHeads: Set<string>;
  try {
    const { derive_inverse_pairs } = require("./vendor_stdlib");
    forwardHeads = new Set([...derive_inverse_pairs({ device_build })].map((head: any) => String(head).trim().toLowerCase()).filter((head: string) => head));
  } catch {
    return false;
  }
  for (const line of configText.split("\n").length ? configText.split("\n") : [configText]) {
    const folded = line.trim().toLowerCase();
    let lineHasPattern = false;
    try {
      lineHasPattern = new RegExp(pattern).test(line);
    } catch {
      lineHasPattern = false;
    }
    if (lineHasPattern && [...forwardHeads].some((head) => folded === head || folded.startsWith(head + " "))) {
      return true;
    }
  }
  return false;
}

function _preserved_assertion_control_conflict(steps: Record<string, any>[], originalIndex: number, configIndex: number): string {
  const original = steps[originalIndex];
  if (["H", "I"].some((key) => String(original[key] || "").trim())) {
    return "";
  }

  function windowKey(index: number): [string, string, string] | null {
    for (let prev = index - 1; prev >= 0; prev--) {
      const previous = steps[prev];
      if (!_isMapping(previous)) {
        return null;
      }
      if (previous["E"] === "check_point" || String(previous["H"] || "").trim()) {
        continue;
      }
      if (!_readonly_device_window(previous["G"] ?? "", previous["E"] ?? "")) {
        return null;
      }
      return [String(previous["E"] || ""), String(previous["F"] || ""), String(previous["G"] || "")];
    }
    return null;
  }
  const targetWindow = windowKey(originalIndex);
  if (targetWindow === null) {
    return "";
  }
  for (let index = configIndex - 1; index >= 0; index--) {
    const candidate = steps[index];
    if (!_isMapping(candidate)) {
      break;
    }
    if (candidate["E"] === "check_point") {
      if (String(candidate["F"] || "") === String(original["F"] || "") && String(candidate["G"] || "") === String(original["G"] || "") && !["H", "I"].some((key) => String(candidate[key] || "").trim()) && JSON.stringify(windowKey(index)) === JSON.stringify(targetWindow)) {
        return `the same result-window assertion already occurs at steps[${index}] before config steps[${configIndex}], with only assertions and read-only device observations in between; inserting its inverse there would contradict the existing before-state requirement`;
      }
      continue;
    }
    if (!_readonly_device_window(candidate["G"] ?? "", candidate["E"] ?? "")) {
      break;
    }
  }
  return "";
}

function _auto_in_case_requirement(steps: Record<string, any>[], provSteps: any[], originalIndex: number, command: string, opts: { assertion_count: number; operator: string; pattern: string; device_build: string }): [Record<string, any> | null, string] {
  const { _DERIVED_SOURCE_KINDS } = require("./provenance_ir");
  if (originalIndex >= 0 && originalIndex < provSteps.length) {
    const origin = provSteps[originalIndex];
    const originSource = _isMapping(origin) ? origin["source"] : null;
    const derivation = _isMapping(originSource) ? originSource["receipt"] : null;
    if (_isMapping(originSource) && _DERIVED_SOURCE_KINDS.has(String(originSource["kind"] || "")) && _isMapping(derivation) && _isMapping(derivation["source_input"])) {
      return [null, `the expected value is a registered derivation output (${originSource["kind"]}); an inverted control row is never a legal output of that rule`];
    }
  }
  let windowIndex: number | null = null;
  for (let idx = originalIndex - 1; idx >= 0; idx--) {
    const step = steps[idx];
    if (!_isMapping(step)) {
      continue;
    }
    if (String(step["E"] || "").trim() === "check_point") {
      continue;
    }
    if (String(step["G"] || "").trim() === command) {
      windowIndex = idx;
      break;
    }
  }
  if (windowIndex === null) {
    return [null, "no observation step carries the window command"];
  }
  const windowStep = steps[windowIndex];
  if (String(windowStep["H"] || "").trim()) {
    return [null, "window step carries an H register and is not the result window"];
  }
  const windowError = _auto_in_case_window_error(command, String(windowStep["E"] || ""), opts);
  if (windowError) {
    return [null, windowError];
  }
  let configIndex: number | null = null;
  for (let idx = windowIndex - 1; idx >= 0; idx--) {
    const candidate = steps[idx];
    if (_state_changing_config_step(candidate)) {
      configIndex = idx;
      break;
    }
  }
  if (configIndex === null) {
    return [null, "no earlier config step to anchor the control"];
  }
  const preservationConflict = _preserved_assertion_control_conflict(steps, originalIndex, configIndex);
  if (preservationConflict) {
    return [null, preservationConflict];
  }
  const configStep = steps[configIndex];
  if (_negative_target_introduced_by_forward_config(configStep, { operator: opts.operator, pattern: opts.pattern, device_build: opts.device_build })) {
    return [null, "a not_found target is introduced by the nearest forward CONFIG; the same target is normally absent before that command, so an inserted found pre-control would not be a mechanically valid flip"];
  }
  if (!Array.isArray(provSteps) || windowIndex >= provSteps.length) {
    return [null, "window step has no aligned provenance to copy"];
  }
  const preProv = JSON.parse(JSON.stringify(provSteps[windowIndex]));
  if (!_isMapping(preProv)) {
    return [null, "window step has no aligned provenance to copy"];
  }
  delete preProv["assertion_type"];
  return [{ mode: "in_case_serialized", config_step_index: configIndex, pre_observe: { E: String(windowStep["E"] || ""), F: String(windowStep["F"] || ""), G: command }, pre_observe_provenance: preProv, auto_derived: true }, ""];
}

export const PRE_OBSERVE_OBSERVATION_PREFIX = "obs_mutation_";

function _collect_observation_names(provSteps: any[]): Set<string> {
  const taken = new Set<string>();
  for (const step of provSteps) {
    if (!_isMapping(step)) {
      continue;
    }
    for (const key of ["observation_id", "result_channel"]) {
      const name = String(step[key] || "").trim();
      if (name) {
        taken.add(name);
      }
    }
  }
  return taken;
}

function _mint_pre_observe_observation_id(pendingRef: string, taken: Set<string>): string {
  const digest = _sha256Hex(String(pendingRef)).slice(0, 24);
  const base = `${PRE_OBSERVE_OBSERVATION_PREFIX}${digest}`;
  let candidate = base;
  let suffix = 1;
  while (taken.has(candidate) || taken.has(`result_${candidate}`)) {
    candidate = `${base}_${suffix}`;
    suffix += 1;
  }
  return candidate;
}

export function compiler_inserted_observation_ids(receipt: any): Set<string> {
  const out = new Set<string>();
  if (!_isMapping(receipt)) {
    return out;
  }
  for (const item of receipt["requirements"] || []) {
    if (!_isMapping(item)) {
      continue;
    }
    if (String(item["mode"] || "") !== "in_case_serialized") {
      continue;
    }
    const name = String(item["pre_observe_observation_id"] || "").trim();
    if (name) {
      out.add(name);
    }
  }
  return out;
}

function _assertion_window_channel(steps: Record<string, any>[], originalIndex: number): string {
  for (let index = originalIndex - 1; index >= 0; index--) {
    const step = steps[index];
    if (!_isMapping(step)) {
      continue;
    }
    if (String(step["E"] || "").trim() === "check_point") {
      continue;
    }
    if (String(step["H"] || "").trim()) {
      continue;
    }
    return String(step["E"] || "").trim() === "test_env" ? "client" : "";
  }
  return "";
}

function _advisory(ordinal: number, code: string, detail: string, command: string, opts: { message?: string } = {}): Record<string, any> {
  return { assertion_ordinal: ordinal, code, message: opts.message ? `断言 ${ordinal}：${opts.message}` : `断言 ${ordinal}：${_ADVISORY_MESSAGES[code] ?? code}`, detail: String(detail || ""), observation_command: String(command || "") };
}

function _warning_panel(items: Record<string, any>[]): Record<string, any> {
  const { WARNING_PANEL_SCHEMA } = require("./contract_entry");
  return { schema: WARNING_PANEL_SCHEMA, items };
}

function _evidence_ref(prefix: string, material: Record<string, any>): string {
  const digest = _sha256Hex(Buffer.from(_canonicalJson(material), "utf-8"));
  return `mutation:${prefix}:${digest}`;
}

function _set_flip(provStep: Record<string, any>, evidenceRef: string): string {
  const assertion = provStep["assertion_type"];
  if (!_isMapping(assertion)) {
    return "typed mutation requires assertion_type on every check_point";
  }
  assertion["flip"] = { kind: "Flipped", evidence_ref: evidenceRef };
  return "";
}

function _set_exempt(provStep: Record<string, any>, reasonCode: string): string {
  const assertion = provStep["assertion_type"];
  if (!_isMapping(assertion)) {
    return "typed exemption requires assertion_type on every check_point";
  }
  assertion["flip"] = { kind: "Exempt", reason_code: reasonCode };
  return "";
}

function _bipolar_observation_sequences(steps: Record<string, any>[], provSteps: any[]): Record<string, any>[] {
  const grouped = new Map<string, [number, string][]>();
  let ordinal = 0;
  steps.forEach((step, index) => {
    if (!_isMapping(step) || String(step["E"] || "").trim() !== "check_point") {
      return;
    }
    ordinal += 1;
    const operator = String(step["F"] || "").trim();
    const pattern = String(step["G"] || "");
    if (!(operator in _INVERSE_ASSERTION) || !pattern || index >= provSteps.length) {
      return;
    }
    const provenance = provSteps[index];
    if (!_isMapping(provenance)) {
      return;
    }
    const expectationId = String(provenance["expectation_id"] || "").trim();
    const semanticKey = String(provenance["semantic_key"] || "").trim();
    if (!expectationId || !semanticKey) {
      return;
    }
    const key = JSON.stringify([expectationId, semanticKey, pattern]);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push([ordinal, operator]);
  });
  const disclosures: Record<string, any>[] = [];
  for (const [key, sequence] of grouped) {
    const [expectationId, semanticKey, pattern] = JSON.parse(key);
    const operators = sequence.map(([, operator]) => operator);
    if (!(operators.includes("found") && operators.includes("not_found"))) {
      continue;
    }
    disclosures.push({ expectation_id: expectationId, semantic_key: semanticKey, assertion_ordinals: sequence.map((item) => item[0]), operators, pattern_sha256: _sha256Hex(pattern) });
  }
  return disclosures;
}

function _bipolar_control_suppression_detail(disclosures: Record<string, any>[]): string {
  if (!disclosures.length) {
    return "";
  }
  const rows = disclosures.map((item) => `expectation_id=${item["expectation_id"]}, semantic_key=${item["semantic_key"]}, ordinals=${JSON.stringify(item["assertion_ordinals"])}, operators=${JSON.stringify(item["operators"])}, pattern_sha256=${item["pattern_sha256"]}`);
  return "the case already contains a found/not_found sequence for the same identity-bound observation object (" + rows.join("; ") + "); its case-level polarity sensitivity is explicit, so no additional compiler control row was injected";
}

function _baseline_flips(operator: string, pattern: string, echo: string): [boolean, string] {
  if (!(operator in _INVERSE_ASSERTION)) {
    return [false, "ledger mutation supports only found/not_found assertions"];
  }
  let matched: boolean;
  try {
    matched = new RegExp(pattern, "s").test(echo);
  } catch (exc) {
    return [false, `assertion pattern is not valid regex: ${exc}`];
  }
  return [(operator === "found" && !matched) || (operator === "not_found" && matched), ""];
}

function _is_compiler_issued_exempt(item: Record<string, any>): boolean {
  if (String(item["issuer"] || "") === EXEMPT_ISSUER_COMPILER) {
    return true;
  }
  return COMPILER_ISSUED_EXEMPT_CODES.has(String(item["reason_code"] || ""));
}

function _exempt_bucket(item: Record<string, any>): string {
  if (String(item["window_channel"] || "") === "client") {
    return "structural";
  }
  if (_is_compiler_issued_exempt(item)) {
    return "compiler_issued";
  }
  return "discretionary";
}

function _governance_counts(items: Record<string, any>[]): [number, number, number, number, number, number] {
  const total = items.length;
  const exemptItems = items.filter((item) => item["status"] === "exempt");
  const buckets = exemptItems.map((item) => _exempt_bucket(item));
  const exempt = exemptItems.length;
  const structural = buckets.filter((b) => b === "structural").length;
  const compilerIssued = buckets.filter((b) => b === "compiler_issued").length;
  const discretionary = exempt - structural;
  const ratio = total ? discretionary / total : 0.0;
  return [total, exempt, structural, compilerIssued, discretionary, ratio];
}

function _all_exempt_are_compiler_issued(items: Record<string, any>[]): boolean {
  const exemptItems = items.filter((item) => item["status"] === "exempt");
  return Boolean(exemptItems.length) && exemptItems.every((item) => _is_compiler_issued_exempt(item));
}

function _exempt_governance(items: Record<string, any>[]): Record<string, any> {
  const [total, exempt, structural, compilerIssued, discretionary, ratio] = _governance_counts(items);
  const issued = new Date();
  const due = new Date(issued.getTime() + EXEMPT_REVIEW_DAYS * 86400000);
  return { schema: EXEMPT_GOVERNANCE_SCHEMA, total_assertions: total, exempt_assertions: exempt, structural_exempt_assertions: structural, compiler_issued_exempt_assertions: compilerIssued, discretionary_exempt_assertions: discretionary, exempt_ratio: Math.round(ratio * 1e6) / 1e6, max_exempt_ratio: EXEMPT_MAX_RATIO, within_limit: Boolean(total > 0 && exempt < total && ratio <= EXEMPT_MAX_RATIO), review_required: exempt > 0, review_status: exempt > 0 ? "pending" : "not_required", issued_at: issued.toISOString(), review_due_at: due.toISOString(), expires_at: due.toISOString(), delivery_run_limit: 1 };
}

export const EXEMPT_GOVERNANCE_BLOCK_CODES = ["governance_missing", "governance_schema_invalid", "governance_counts_mismatch", "all_assertions_exempt", "exempt_ratio_exceeded", "governance_window_invalid", "governance_review_invalid"] as const;
export const MUTATION_SETTLE_CODES = new Set([...EXEMPT_GOVERNANCE_BLOCK_CODES, "mutation_receipt_not_object", "mutation_receipt_schema_invalid", "mutation_receipt_artifact_mismatch", "mutation_receipt_requirements_invalid", "mutation_ledger_baseline_stale", "mutation_receipt_balance_inconsistent", "build_mismatch_at_run", "mutation_requirement_not_object", "mutation_requirement_evidence_invalid", "mutation_receipt_not_ready"]);

function _parseIso(value: any): Date | null {
  const text = String(value || "");
  if (!text) return null;
  const normalized = text.endsWith("+00:00") ? text.slice(0, -6) + "Z" : text;
  const date = new Date(normalized);
  return isNaN(date.getTime()) ? null : date;
}

function _governance_window(governance: Record<string, any>): [Date, Date] | null {
  try {
    const issued = _parseIso(governance["issued_at"]);
    const due = _parseIso(governance["review_due_at"]);
    const expires = _parseIso(governance["expires_at"]);
    if (issued === null || due === null || expires === null) {
      return null;
    }
    if (due.getTime() !== expires.getTime() || expires.getTime() <= issued.getTime() || expires.getTime() - issued.getTime() > EXEMPT_REVIEW_DAYS * 86400000 + 1000 || Date.now() >= expires.getTime()) {
      return null;
    }
    return [issued, expires];
  } catch {
    return null;
  }
}

export function exempt_review_content_sha256(receipt: Record<string, any>): string {
  const content = JSON.parse(JSON.stringify(receipt));
  const governance = content["exempt_governance"];
  if (_isMapping(governance)) {
    for (const key of ["reviewed_at", "reviewer_sha256", "review_binding"]) {
      delete governance[key];
    }
    governance["review_status"] = governance["review_required"] ? "pending" : "not_required";
  }
  return _sha256Hex(Buffer.from(_canonicalJson(content), "utf-8"));
}

function _review_bound(receipt: Record<string, any>, governance: Record<string, any>, opts: { decision?: string } = {}): boolean {
  const decision = opts.decision ?? "approve";
  const binding = governance["review_binding"];
  const window = _governance_window(governance);
  if (!_isMapping(binding) || window === null || governance["review_status"] !== (decision === "approve" ? "reviewed" : "rejected") || binding["decision"] !== decision || binding["scope"] !== "receipt_version" || !accepts_schema(binding["schema"], "ist.exempt-review-binding")) {
    return false;
  }
  const reviewer = String(governance["reviewer_sha256"] || "");
  const artifact = String(receipt["xlsx_sha256"] || "");
  if (!/^[0-9a-f]{64}$/.test(reviewer) || !/^[0-9a-f]{64}$/.test(artifact) || binding["reviewer_sha256"] !== reviewer || binding["xlsx_sha256"] !== artifact || binding["receipt_content_sha256"] !== exempt_review_content_sha256(receipt)) {
    return false;
  }
  try {
    const reviewed = _parseIso(governance["reviewed_at"]);
    return reviewed !== null && window[0].getTime() <= reviewed.getTime() && reviewed.getTime() < window[1].getTime();
  } catch {
    return false;
  }
}

function _exempt_governance_check(receipt: Record<string, any>, opts: { allow_compiler_issued_full_exempt?: boolean } = {}): string {
  const allowCompilerIssuedFullExempt = opts.allow_compiler_issued_full_exempt ?? false;
  const items = ((receipt["requirements"] || []) as any[]).filter((item) => _isMapping(item));
  const exemptCount = items.filter((item) => item["status"] === "exempt").length;
  if (exemptCount === 0) {
    return "";
  }
  const governance = receipt["exempt_governance"];
  if (!_isMapping(governance)) {
    return "governance_missing";
  }
  if (governance["schema"] !== EXEMPT_GOVERNANCE_SCHEMA || governance["review_required"] !== true || !["pending", "reviewed", "rejected"].includes(governance["review_status"])) {
    return "governance_schema_invalid";
  }
  const [total, exempt, structural, compilerIssued, discretionary, ratio] = _governance_counts(items);
  const withinLimit = Boolean(total > 0 && exempt < total && ratio <= EXEMPT_MAX_RATIO);
  const issuedDisclosure = governance["compiler_issued_exempt_assertions"];
  if (governance["total_assertions"] !== total || governance["exempt_assertions"] !== exempt || governance["structural_exempt_assertions"] !== structural || (issuedDisclosure !== null && issuedDisclosure !== undefined && issuedDisclosure !== compilerIssued) || governance["discretionary_exempt_assertions"] !== discretionary || governance["exempt_ratio"] !== Math.round(ratio * 1e6) / 1e6 || governance["max_exempt_ratio"] !== EXEMPT_MAX_RATIO || governance["within_limit"] !== withinLimit) {
    return "governance_counts_mismatch";
  }
  if (!withinLimit) {
    const authorDeclared = discretionary - compilerIssued;
    const authorRatio = total ? authorDeclared / total : 0.0;
    if (!_review_bound(receipt, governance) && !(allowCompilerIssuedFullExempt && total > 0 && authorRatio <= EXEMPT_MAX_RATIO && _all_exempt_are_compiler_issued(items))) {
      return exempt >= total ? "all_assertions_exempt" : "exempt_ratio_exceeded";
    }
  }
  if (_governance_window(governance) === null) {
    return "governance_window_invalid";
  }
  if (governance["review_status"] !== "pending" && !_review_bound(receipt, governance)) {
    return "governance_review_invalid";
  }
  return "";
}

export function exempt_governance_block_codes(receipt: Record<string, any>, opts: { allow_compiler_issued_full_exempt?: boolean } = {}): string[] {
  const primary = _exempt_governance_check(receipt, opts);
  const codes = primary ? [primary] : [];
  const governance = receipt["exempt_governance"];
  if (primary && primary !== "governance_window_invalid" && _isMapping(governance) && _governance_window(governance) === null) {
    codes.push("governance_window_invalid");
  }
  return codes;
}

function _exempt_governance_ready(receipt: Record<string, any>, opts: { allow_compiler_issued_full_exempt?: boolean } = {}): boolean {
  return !_exempt_governance_check(receipt, opts);
}

export function exempt_governance_failure_message(receipt: Record<string, any>, opts: { allow_compiler_issued_full_exempt?: boolean } = {}): string {
  const allowCompilerIssuedFullExempt = opts.allow_compiler_issued_full_exempt ?? true;
  if (!_isMapping(receipt)) {
    return "";
  }
  const code = _exempt_governance_check(receipt, { allow_compiler_issued_full_exempt: allowCompilerIssuedFullExempt });
  if (!code) {
    return "";
  }
  let governance = receipt["exempt_governance"];
  if (!_isMapping(governance)) {
    governance = {};
  }
  const total = governance["total_assertions"];
  const exempt = governance["exempt_assertions"];
  const compilerIssued = governance["compiler_issued_exempt_assertions"] || 0;
  const structural = governance["structural_exempt_assertions"] || 0;
  const discretionary = governance["discretionary_exempt_assertions"] || 0;
  const authorDeclared = ((receipt["requirements"] || []) as any[]).filter((item) => _isMapping(item) && item["status"] === "exempt" && !_is_compiler_issued_exempt(item)).length;
  if (code === "governance_missing") {
    return "IDE mutation receipt declares Exempt assertions but carries no exempt governance record — re-run compile_emit to re-issue it.";
  }
  if (code === "governance_schema_invalid") {
    return `IDE mutation exempt governance record is not a valid ${EXEMPT_GOVERNANCE_SCHEMA} receipt (schema or review_status is unusable) — re-run compile_emit to re-issue it.`;
  }
  if (code === "governance_counts_mismatch") {
    return "IDE mutation exempt governance counters do not match the requirements they claim to summarise — the receipt is stale or was edited after emit; re-run compile_emit.";
  }
  if (code === "governance_window_invalid") {
    return `IDE mutation exempt governance review window is invalid or has expired (${EXEMPT_REVIEW_DAYS}-day validity) — re-run compile_emit to re-issue the receipt.`;
  }
  if (code === "governance_review_invalid") {
    return "IDE mutation exempt governance review record is unusable (reviewer identity or review timestamp out of window) — re-run compile_emit to re-issue the receipt.";
  }
  let head: string;
  if (code === "all_assertions_exempt") {
    head = `IDE mutation exemption governance failed: every assertion in this case is exempt (${exempt}/${total} assertions exempt) — a case with zero flip evidence has no discriminating power.`;
  } else {
    head = `IDE mutation exemption governance failed: ${exempt}/${total} assertions exempt (${discretionary} discretionary, capped at ${EXEMPT_MAX_RATIO}).`;
  }
  if (authorDeclared) {
    if (code === "all_assertions_exempt") {
      return head + ` ${authorDeclared} of them are author-declared. A pre-state control needs a pure-read window; an assertion whose observation is itself the action carries none. This case has no assertion left with a control: land at least one assertion on a pure-read window if the procedure has one.`;
    }
    return head + ` ${authorDeclared} of them are author-declared, over the discretionary cap. Remove the declaration from an assertion whose observation is a pure read.`;
  }
  const reasons: string[] = [];
  const panel = receipt["warning_panel"];
  const engineIssuedCodes = new Set([...COMPILER_ISSUED_EXEMPT_CODES, ...ENGINE_COMPUTED_EXEMPT_CODES]);
  for (const item of (_isMapping(panel) ? panel["items"] : null) || []) {
    if (!_isMapping(item)) {
      continue;
    }
    if (!engineIssuedCodes.has(item["code"])) {
      continue;
    }
    const detail = String(item["detail"] || "").trim();
    if (detail.startsWith("author-declared")) {
      continue;
    }
    if (detail && !reasons.includes(detail)) {
      reasons.push(detail);
    }
  }
  const tail = reasons.length ? "; the in-case control could not be built because: " + reasons.slice(0, 3).join("; ") : "";
  return head + ` These exemptions are all engine-issued (${compilerIssued} compiler-issued, ${structural} client-channel), 0 declared by the author. This is not an authoring defect and there is no pragma to remove` + tail + ".";
}

export function review_exempt_governance(receipt: Record<string, any>, opts: { reviewer_id: string; decision: string }): [Record<string, any>, string] {
  const reviewer = String(opts.reviewer_id || "").trim();
  const verdict = String(opts.decision || "").trim().toLowerCase();
  if (!reviewer) {
    return [receipt, "reviewer_id is required"];
  }
  if (!["approve", "reject"].includes(verdict)) {
    return [receipt, "decision must be approve or reject"];
  }
  const output = JSON.parse(JSON.stringify(receipt));
  const governance = output["exempt_governance"];
  if (!_isMapping(governance) || governance["schema"] !== EXEMPT_GOVERNANCE_SCHEMA) {
    return [receipt, "exempt governance receipt is missing"];
  }
  if (!governance["review_required"]) {
    return [receipt, "this receipt has no Exempt assertion to review"];
  }
  if (_governance_window(governance) === null) {
    return [receipt, "exempt governance window is invalid or expired"];
  }
  const artifact = String(receipt["xlsx_sha256"] || "");
  if (!/^[0-9a-f]{64}$/.test(artifact)) {
    return [receipt, "an artifact-bound receipt is required"];
  }
  const reviewerSha = _sha256Hex(reviewer);
  const binding = { schema: "ist.exempt-review-binding", scope: "receipt_version", decision: verdict, xlsx_sha256: artifact, reviewer_sha256: reviewerSha, receipt_content_sha256: exempt_review_content_sha256(receipt) };
  if (JSON.stringify(governance["review_binding"]) === JSON.stringify(binding) && _review_bound(receipt, governance, { decision: verdict })) {
    return [output, ""];
  }
  governance["review_status"] = verdict === "approve" ? "reviewed" : "rejected";
  governance["reviewed_at"] = new Date().toISOString();
  governance["reviewer_sha256"] = reviewerSha;
  governance["review_binding"] = binding;
  return [output, ""];
}

function _scrub_declared_mutation_roles(provenance: any): void {
  if (!_isMapping(provenance)) {
    return;
  }
  const steps = provenance["steps"];
  if (!Array.isArray(steps)) {
    return;
  }
  for (const step of steps) {
    if (_isMapping(step)) {
      delete step["mutation_role"];
    }
  }
}

function _step_flip_evidence_ref(provStep: any): string {
  if (!_isMapping(provStep)) {
    return "";
  }
  const assertion = provStep["assertion_type"];
  if (!_isMapping(assertion)) {
    return "";
  }
  const flip = assertion["flip"];
  if (!_isMapping(flip) || flip["kind"] !== "Flipped") {
    return "";
  }
  return String(flip["evidence_ref"] || "");
}

function _counter(values: string[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const value of values) {
    out.set(value, (out.get(value) ?? 0) + 1);
  }
  return out;
}

function _countersEqual(a: Map<string, number>, b: Map<string, number>): boolean {
  if (a.size !== b.size) return false;
  for (const [key, count] of a) {
    if (b.get(key) !== count) return false;
  }
  return true;
}

function _counterSum(counter: Map<string, number>): number {
  let total = 0;
  for (const count of counter.values()) total += count;
  return total;
}

function _control_row_balance(receiptItems: Record<string, any>[], outSteps: Record<string, any>[], provSteps: any[]): Record<string, any> {
  const assertions = outSteps.filter((step, index) => index < provSteps.length && _isMapping(step) && String(step["E"] || "").trim() === "check_point").map((_, index) => {
    const cpIndices = outSteps.map((step, i) => [_isMapping(step) && String(step["E"] || "").trim() === "check_point", i] as [boolean, number]).filter(([isCp]) => isCp).map(([, i]) => i);
    return provSteps[cpIndices[index]];
  });
  const controlRows = assertions.filter((step) => _isMapping(step) && String(step["mutation_role"] || "") === MUTATION_ROLE_CONTROL);
  const productRows = assertions.filter((step) => !_isMapping(step) || String(step["mutation_role"] || "") !== MUTATION_ROLE_CONTROL);
  const mintedControls = _counter(receiptItems.filter((item) => String(item["mode"] || "") === "in_case_serialized").map((item) => String(item["evidence_ref"] || "")));
  const landedControls = _counter(controlRows.map((step) => _step_flip_evidence_ref(step)));
  const mintedFlips = _counter(receiptItems.map((item) => String(item["evidence_ref"] || "")).filter((ref) => ref));
  const landedFlips = _counter(productRows.map((step) => _step_flip_evidence_ref(step)).filter((ref) => ref));
  const counts = { product_assertions: productRows.length, receipt_requirements: receiptItems.length, minted_controls: _counterSum(mintedControls), landed_controls: _counterSum(landedControls), minted_flip_credentials: _counterSum(mintedFlips), landed_flip_credentials: _counterSum(landedFlips), balanced: true };
  let failure = "";
  if (productRows.length !== receiptItems.length) {
    failure = `IDE mutation credential ledger does not balance: the case carries ${productRows.length} product assertion rows but the receipt records ${receiptItems.length} requirements`;
  } else if (mintedControls.has("")) {
    failure = "IDE mutation credential ledger does not balance: an in_case_serialized requirement carries no evidence_ref";
  } else if (!_countersEqual(landedControls, mintedControls)) {
    failure = `IDE mutation credential ledger does not balance: the receipt minted ${_counterSum(mintedControls)} in-case control credential(s) but the case carries ${_counterSum(landedControls)} control row(s) bound to them`;
  } else if (!_countersEqual(landedFlips, mintedFlips)) {
    failure = `IDE mutation credential ledger does not balance: the receipt records ${_counterSum(mintedFlips)} flip credential(s) but ${_counterSum(landedFlips)} product assertion row(s) carry a matching flip evidence_ref`;
  }
  if (failure) {
    counts.balanced = false;
  }
  return { failure, counts };
}

export function compile_mutation_plan(
  steps: Record<string, any>[],
  provenance: Record<string, any> | null,
  requirementsValue: any,
  opts: { required: boolean; derive_defaults?: boolean; device_build?: string; device_build_source?: string }
): [Record<string, any>[], Record<string, any> | null, Record<string, any>, string] {
  const deriveDefaults = opts.derive_defaults ?? false;
  const deviceBuild = opts.device_build ?? "";
  const deviceBuildSource = opts.device_build_source ?? "";
  _scrub_declared_mutation_roles(provenance);
  let requirements: Record<string, any>[];
  let error: string;
  try {
    if (deriveDefaults) {
      [requirements, error] = derive_mutation_requirements(steps, requirementsValue, { device_build: deviceBuild });
    } else {
      [requirements, error] = _parse_requirements(requirementsValue);
    }
  } catch (exc: any) {
    return [steps, provenance, {}, String(exc?.message ?? exc)];
  }
  if (error) {
    return [steps, provenance, {}, error];
  }
  if (opts.required && !requirements.length) {
    return [steps, provenance, {}, "IDE assertion types require mutation evidence for every product assertion"];
  }
  if (!requirements.length) {
    return [steps, provenance, {}, ""];
  }
  if (!_isMapping(provenance)) {
    return [steps, provenance, {}, "mutation requirements need aligned provenance"];
  }
  if (provenance["assertion_schema"] !== ASSERTION_TYPE_SCHEMA) {
    return [steps, provenance, {}, `mutation requirements require assertion_schema=${ASSERTION_TYPE_SCHEMA}`];
  }
  const provSteps = provenance["steps"];
  if (!Array.isArray(provSteps) || provSteps.length !== steps.length) {
    return [steps, provenance, {}, "provenance steps are not aligned before mutation"];
  }
  const assertionIndices = steps.map((step, index) => [step, index] as [Record<string, any>, number]).filter(([step]) => String(step["E"] || "").trim() === "check_point").map(([, index]) => index);
  const byOrdinal = new Map<number, Record<string, any>>();
  for (let reqIndex = 0; reqIndex < requirements.length; reqIndex++) {
    const requirement = requirements[reqIndex];
    const ordinals = requirement["assertion_ordinals"];
    if (!Array.isArray(ordinals) || !ordinals.length) {
      return [steps, provenance, {}, `mutation requirements[${reqIndex}].assertion_ordinals must be a non-empty array`];
    }
    for (const ordinal of ordinals) {
      if (typeof ordinal !== "number" || !Number.isInteger(ordinal) || ordinal < 1) {
        return [steps, provenance, {}, "assertion ordinals are 1-based positive integers"];
      }
      if (byOrdinal.has(ordinal)) {
        return [steps, provenance, {}, `assertion ordinal ${ordinal} is declared twice`];
      }
      byOrdinal.set(ordinal, requirement);
    }
  }
  const expected = new Set(Array.from({ length: assertionIndices.length }, (_, i) => i + 1));
  if (byOrdinal.size !== expected.size || ![...byOrdinal.keys()].every((k) => expected.has(k))) {
    return [steps, provenance, {}, `mutation requirements must cover every product check_point exactly once; expected=${JSON.stringify([...expected].sort((a, b) => a - b))} got=${JSON.stringify([...byOrdinal.keys()].sort((a, b) => a - b))}`];
  }
  const outputSteps = steps.map((step) => ({ ...step }));
  if (deriveDefaults) {
    for (const step of outputSteps) {
      delete step["exempt"];
      delete step["reason_code"];
    }
  }
  const outputProvenance = JSON.parse(JSON.stringify(provenance));
  const outputProvSteps = outputProvenance["steps"];
  const takenObservationNames = _collect_observation_names(outputProvSteps);
  const insertions = new Map<number, [Record<string, any>, Record<string, any>][]>();
  const receiptItems: Record<string, any>[] = [];
  const advisories: Record<string, any>[] = [];
  const bipolarDisclosures = _bipolar_observation_sequences(steps, outputProvSteps);
  const bipolarDetail = _bipolar_control_suppression_detail(bipolarDisclosures);
  for (const ordinal of [...byOrdinal.keys()].sort((a, b) => a - b)) {
    let requirement = byOrdinal.get(ordinal)!;
    const originalIndex = assertionIndices[ordinal - 1];
    const originalStep = steps[originalIndex];
    const originalProv = outputProvSteps[originalIndex];
    const operator = String(originalStep["F"] || "").trim();
    const pattern = String(originalStep["G"] || "");
    let mode = String(requirement["mode"] || "").trim();
    if (mode === "in_case_serialized" && bipolarDetail) {
      const typeError = _set_exempt(originalProv, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON);
      if (typeError) {
        return [steps, provenance, {}, `assertion ${ordinal} ${typeError}`];
      }
      const windowChannel = _assertion_window_channel(steps, originalIndex);
      receiptItems.push({ assertion_ordinal: ordinal, mode: "exempt", status: "exempt", reason_code: FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, auto_derived: true, ...(windowChannel ? { window_channel: windowChannel } : {}) });
      const preObserve = requirement["pre_observe"];
      advisories.push(_advisory(ordinal, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, bipolarDetail, _isMapping(preObserve) ? String(preObserve["G"] || "") : "", { message: "案体已有同一观测对象的 found/not_found 双极性序列，已免插入额外控制行" }));
      continue;
    }
    if (mode === "exempt") {
      const allowedOptional = new Set(["window_channel", ...(deriveDefaults ? ["issuer", "auto_derived"] : [])]);
      const requiredKeys = new Set(["assertion_ordinals", "mode", "reason_code"]);
      const keys = new Set(Object.keys(requirement).filter((k) => !allowedOptional.has(k)));
      if (keys.size !== requiredKeys.size || ![...requiredKeys].every((k) => keys.has(k))) {
        return [steps, provenance, {}, `assertion ${ordinal} exempt pragma requires exactly assertion_ordinals/mode/reason_code`];
      }
      const reasonCode = String(requirement["reason_code"] || "").trim();
      if (!AUTHOR_DECLARABLE_EXEMPT_CODES.has(reasonCode)) {
        return [steps, provenance, {}, `assertion ${ordinal} exempt reason_code must be one of ${[...AUTHOR_DECLARABLE_EXEMPT_CODES].sort()}`];
      }
      const engineIssued = deriveDefaults && String(requirement["issuer"] || "") === EXEMPT_ISSUER_COMPILER;
      const typeError = _set_exempt(originalProv, reasonCode);
      if (typeError) {
        return [steps, provenance, {}, `assertion ${ordinal} ${typeError}`];
      }
      const exemptItem: Record<string, any> = { assertion_ordinal: ordinal, mode, status: "exempt", reason_code: reasonCode };
      if (engineIssued) {
        exemptItem["issuer"] = EXEMPT_ISSUER_COMPILER;
        exemptItem["auto_derived"] = true;
      }
      if (String(requirement["window_channel"] || "") === "client") {
        exemptItem["window_channel"] = "client";
      }
      receiptItems.push(exemptItem);
      if (engineIssued) {
        advisories.push(_advisory(ordinal, reasonCode, "the assertion observation window is not a read-only device show/get path; the compiler recomputed this and issued the exemption itself", String(requirement["observation_command"] || "")));
      } else if (reasonCode === "non_readonly_probe") {
        advisories.push(_advisory(ordinal, reasonCode, "author-declared; the compiler did not verify whether this read changes device state and inserted no pre-state control", String(requirement["observation_command"] || ""), { message: "作者声明这条观测不是纯读；编译器未核，未插前置对照，判别力交上机实证" }));
      }
      continue;
    }
    if (mode === "ledger") {
      const command = String(requirement["observation_command"] || "").trim();
      const build = String(requirement["device_build"] || "").trim();
      if (!command || !build) {
        return [steps, provenance, {}, `assertion ${ordinal} ledger mutation requires observation_command and device_build`];
      }
      const { lookup_flip_baseline } = require("./local_replay");
      const baseline = lookup_flip_baseline(command, build);
      let ledgerGap = "";
      let gapCode = "";
      if (baseline["status"] !== "available") {
        gapCode = "flip_baseline_unavailable";
        ledgerGap = `clean-state baseline is unknown: ${baseline["reason_code"] || "BASELINE_UNKNOWN"}`;
      } else {
        const [flips, replayError] = _baseline_flips(operator, pattern, String(baseline["echo"] || ""));
        if (replayError) {
          gapCode = "flip_baseline_unavailable";
          ledgerGap = replayError;
        } else if (!flips) {
          gapCode = operator === "found" ? "vacuous_found_in_clean" : "flip_baseline_not_discriminating";
          ledgerGap = "does not fail against the recorded clean-state baseline";
        }
      }
      if (!ledgerGap) {
        const evidenceRef = _evidence_ref("ledger", { ordinal, operator, pattern, baseline });
        const typeError = _set_flip(originalProv, evidenceRef);
        if (typeError) {
          return [steps, provenance, {}, `assertion ${ordinal} ${typeError}`];
        }
        receiptItems.push({ assertion_ordinal: ordinal, mode, status: "flipped", evidence_ref: evidenceRef, baseline });
        continue;
      }
      advisories.push(_advisory(ordinal, gapCode, ledgerGap, command));
      let autoReq: Record<string, any> | null;
      let whyNot: string;
      if (!(operator in _INVERSE_ASSERTION) || !pattern) {
        [autoReq, whyNot] = [null, !(operator in _INVERSE_ASSERTION) ? `assertion operator ${JSON.stringify(operator || "(empty)")} has no in-case inverse control in the framework method set` : "assertion pattern is empty; there is nothing to invert"];
      } else if (bipolarDetail) {
        [autoReq, whyNot] = [null, bipolarDetail];
      } else {
        [autoReq, whyNot] = _auto_in_case_requirement(steps, outputProvSteps, originalIndex, command, { assertion_count: assertionIndices.length, operator, pattern, device_build: deviceBuild });
      }
      if (autoReq === null) {
        const typeError = _set_exempt(originalProv, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON);
        if (typeError) {
          return [steps, provenance, {}, `assertion ${ordinal} ${typeError}`];
        }
        const windowChannel = _assertion_window_channel(steps, originalIndex);
        receiptItems.push({ assertion_ordinal: ordinal, mode: "exempt", status: "exempt", reason_code: FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, auto_derived: true, ...(windowChannel ? { window_channel: windowChannel } : {}) });
        advisories.push(_advisory(ordinal, FLIP_CONTROL_UNCONSTRUCTIBLE_REASON, whyNot, command, { message: whyNot === bipolarDetail && bipolarDetail ? "案体已有同一观测对象的 found/not_found 双极性序列，已免插入额外控制行" : "" }));
        continue;
      }
      requirement = { ...autoReq, assertion_ordinals: [ordinal] };
      mode = "in_case_serialized";
    }
    if (mode !== "in_case_serialized") {
      return [steps, provenance, {}, `assertion ${ordinal} mutation mode must be ledger or in_case_serialized or exempt`];
    }
    if (!(operator in _INVERSE_ASSERTION) || !pattern) {
      return [steps, provenance, {}, `assertion ${ordinal} in-case mutation supports a non-empty found/not_found assertion`];
    }
    const configIndex = requirement["config_step_index"];
    if (typeof configIndex !== "number" || !Number.isInteger(configIndex) || configIndex < 0 || configIndex >= steps.length) {
      return [steps, provenance, {}, `assertion ${ordinal} has invalid config_step_index`];
    }
    const configStep = steps[configIndex];
    if (configIndex >= originalIndex || !_state_changing_config_step(configStep)) {
      return [steps, provenance, {}, `assertion ${ordinal} config_step_index must point to an earlier state-changing config step`];
    }
    const preservationConflict = _preserved_assertion_control_conflict(steps, originalIndex, configIndex);
    if (preservationConflict) {
      return [steps, provenance, {}, `assertion ${ordinal} in-case mutation control contradicts a before-state requirement: ${preservationConflict}`];
    }
    if (_negative_target_introduced_by_forward_config(configStep, { operator, pattern, device_build: deviceBuild })) {
      return [steps, provenance, {}, `assertion ${ordinal} in-case mutation control direction is invalid: a not_found target is introduced by the referenced forward CONFIG`];
    }
    const pre = requirement["pre_observe"];
    const preProv = requirement["pre_observe_provenance"];
    if (!_isMapping(pre) || !_isMapping(preProv)) {
      return [steps, provenance, {}, `assertion ${ordinal} in-case mutation requires pre_observe and pre_observe_provenance`];
    }
    const command = String(pre["G"] || "").trim();
    const preE = String(pre["E"] || "").trim();
    const clientControl = preE === "test_env";
    if (clientControl && !(deriveDefaults && requirement["auto_derived"] === true)) {
      return [steps, provenance, {}, `assertion ${ordinal} client pre_observe is compiler-derived only; an explicit requirements payload cannot authorize an extra client command`];
    }
    const windowError = _auto_in_case_window_error(command, preE, { assertion_count: assertionIndices.length });
    if (windowError) {
      return [steps, provenance, {}, `assertion ${ordinal} in-case pre_observe is not eligible: ${windowError}`];
    }
    const postMatch = steps.slice(configIndex + 1, originalIndex).some((step) => String(step["G"] || "").trim() === command && String(step["E"] || "").trim() !== "check_point");
    if (!postMatch) {
      return [steps, provenance, {}, `assertion ${ordinal} has no matching post-config observation`];
    }
    const pendingRef = _evidence_ref("pending", { ordinal, operator, pattern, command });
    const typeError = _set_flip(originalProv, pendingRef);
    if (typeError) {
      return [steps, provenance, {}, `assertion ${ordinal} ${typeError}`];
    }
    const marker = `[IDE-MUTATION-BEFORE:${ordinal}]`;
    const preStep = { ...pre };
    preStep["desc"] = marker;
    const preProvStep = JSON.parse(JSON.stringify(preProv));
    const preObservationId = _mint_pre_observe_observation_id(pendingRef, takenObservationNames);
    const preResultChannel = `result_${preObservationId}`;
    takenObservationNames.add(preObservationId);
    takenObservationNames.add(preResultChannel);
    delete preProvStep["assertion_type"];
    delete preProvStep["observation_ref"];
    preProvStep["observation_id"] = preObservationId;
    preProvStep["result_channel"] = preResultChannel;
    const controlStep = { E: "check_point", F: _INVERSE_ASSERTION[operator], G: pattern, desc: `[IDE-MUTATION-CONTROL:${ordinal}]` };
    const controlProv = JSON.parse(JSON.stringify(originalProv));
    controlProv["mutation_role"] = MUTATION_ROLE_CONTROL;
    delete controlProv["observation_id"];
    delete controlProv["result_channel"];
    controlProv["observation_ref"] = preObservationId;
    controlProv["assertion_type"] = JSON.parse(JSON.stringify(originalProv["assertion_type"]));
    controlProv["assertion_type"]["flip"] = { kind: "Flipped", evidence_ref: pendingRef };
    if (!insertions.has(configIndex)) insertions.set(configIndex, []);
    insertions.get(configIndex)!.push([preStep, preProvStep], [controlStep, controlProv]);
    advisories.push(_advisory(ordinal, "inserted_observation_noninterference_unverified", "The compiler inserted this additional observation before the configuration anchor. Its effect on later observations has not been verified; insertion alone establishes neither interference nor non-interference.", command));
    receiptItems.push({ assertion_ordinal: ordinal, mode, status: "pending", evidence_ref: pendingRef, pre_observe: command, pre_observe_observation_id: preObservationId, control_operator: _INVERSE_ASSERTION[operator], control_pattern: pattern, ...(clientControl ? { control_channel: "client" } : {}), ...(requirement["auto_derived"] === true ? { auto_derived: true } : {}) });
  }
  for (const index of [...insertions.keys()].sort((a, b) => b - a)) {
    for (const [step, provStep] of [...insertions.get(index)!].reverse()) {
      outputSteps.splice(index, 0, step);
      outputProvSteps.splice(index, 0, provStep);
    }
  }
  const orderFailure = mutation_control_order_failure(outputSteps);
  if (orderFailure) {
    return [steps, provenance, {}, orderFailure];
  }
  const balance = _control_row_balance(receiptItems, outputSteps, outputProvSteps);
  if (balance["failure"]) {
    return [steps, provenance, {}, balance["failure"]];
  }
  const governance = _exempt_governance(receiptItems);
  return [outputSteps, outputProvenance, { schema: MUTATION_SCHEMA, requirements: receiptItems, exempt_governance: governance, warning_panel: _warning_panel(advisories), device_build: String(deviceBuild || "").trim(), device_build_source: String(deviceBuildSource || "").trim(), inserted_control_steps: [...insertions.values()].reduce((sum, items) => sum + items.length, 0), control_row_balance: balance["counts"] }, ""];
}

export function receipt_balance_self_consistent(receipt: any): boolean {
  if (!_isMapping(receipt)) {
    return false;
  }
  const balance = receipt["control_row_balance"];
  if (balance === null || balance === undefined) {
    return true;
  }
  if (!_isMapping(balance)) {
    return false;
  }
  const items = ((receipt["requirements"] || []) as any[]).filter((item) => _isMapping(item));
  const minted = items.filter((item) => String(item["mode"] || "") === "in_case_serialized").length;
  return balance["balanced"] === true && balance["minted_controls"] === minted && balance["landed_controls"] === minted && balance["receipt_requirements"] === items.length;
}

export function receipt_build_mismatch(receipt: Record<string, any>, execution_build: string): string {
  if (!_isMapping(receipt)) {
    return "mutation receipt is not an object";
  }
  const { device_build_identity } = require("./local_replay");
  const rawRunBuild = String(execution_build || "").trim();
  const runBuild = rawRunBuild ? device_build_identity(rawRunBuild) : "";
  const recorded = new Set<string>();
  const receiptBuild = String(receipt["device_build"] || "").trim();
  if (receiptBuild) {
    recorded.add(device_build_identity(receiptBuild));
  }
  for (const item of receipt["requirements"] || []) {
    if (!_isMapping(item) || item["mode"] !== "ledger") {
      continue;
    }
    const baseline = item["baseline"];
    if (_isMapping(baseline)) {
      const baselineBuild = String(baseline["device_os_build"] || "").trim();
      if (baselineBuild) {
        recorded.add(device_build_identity(baselineBuild));
      }
    }
  }
  if (!recorded.size) {
    return "";
  }
  if (!runBuild) {
    return "run execution build is missing while the receipt binds a build";
  }
  const mismatched = [...recorded].filter((build) => build !== runBuild).sort();
  if (mismatched.length) {
    return `emit-time device build ${JSON.stringify(mismatched)} does not match run execution build ${runBuild}`;
  }
  return "";
}

function _ledger_baseline_assets_current(receipt: any): boolean {
  const ledgerItems = _isMapping(receipt) ? ((receipt["requirements"] || []) as any[]).filter((item) => _isMapping(item) && item["mode"] === "ledger" && item["status"] === "flipped") : [];
  if (!ledgerItems.length) {
    return true;
  }
  let currentIdentity: any;
  try {
    const { flip_baseline_asset_identity } = require("./local_replay");
    currentIdentity = flip_baseline_asset_identity();
  } catch {
    currentIdentity = {};
  }
  return Boolean(currentIdentity && Object.keys(currentIdentity).length && ledgerItems.every((item) => _isMapping(item["baseline"]) && JSON.stringify(item["baseline"]["asset_identity"]) === JSON.stringify(currentIdentity)));
}

function _completed_mutation_receipt_ready(receipt: Record<string, any>, artifactSha256: string, opts: { execution_build?: string | null; allow_compiler_issued_full_exempt?: boolean } = {}): boolean {
  const executionBuild = opts.execution_build ?? null;
  const ledgerAssetsCurrent = _ledger_baseline_assets_current(receipt);
  return Boolean(
    _isMapping(receipt) &&
      receipt["schema"] === MUTATION_SCHEMA &&
      receipt["xlsx_sha256"] === artifactSha256 &&
      receipt["requirements"] &&
      ledgerAssetsCurrent &&
      receipt_balance_self_consistent(receipt) &&
      (executionBuild === null || !receipt_build_mismatch(receipt, executionBuild)) &&
      _exempt_governance_ready(receipt, { allow_compiler_issued_full_exempt: opts.allow_compiler_issued_full_exempt ?? false }) &&
      ((receipt["requirements"] || []) as any[]).every((item) => {
        if (!_isMapping(item)) return false;
        const status = item["status"];
        if (!["flipped", "exempt"].includes(status)) return false;
        if (status === "flipped" && /^mutation:(?:ledger|run):[0-9a-f]{64}$/.test(String(item["evidence_ref"] || ""))) return true;
        if (status === "exempt" && EXEMPT_REASON_CODES.has(String(item["reason_code"] || ""))) return true;
        return false;
      })
  );
}

export function mutation_receipt_ready(receipt: Record<string, any>, artifact_sha256: string, opts: { execution_build?: string | null } = {}): boolean {
  return _completed_mutation_receipt_ready(receipt, artifact_sha256, { execution_build: opts.execution_build ?? null });
}

export function mutation_receipt_pass_ready(receipt: Record<string, any>, artifact_sha256: string, opts: { execution_build?: string | null } = {}): boolean {
  return _completed_mutation_receipt_ready(receipt, artifact_sha256, { execution_build: opts.execution_build ?? null, allow_compiler_issued_full_exempt: true });
}

export function mutation_receipt_run_ready(receipt: Record<string, any>, artifact_sha256: string, opts: { execution_build?: string | null } = {}): boolean {
  const executionBuild = opts.execution_build ?? null;
  if (!(_isMapping(receipt) && receipt["schema"] === MUTATION_SCHEMA && receipt["xlsx_sha256"] === artifact_sha256 && receipt["requirements"] && receipt_balance_self_consistent(receipt) && (executionBuild === null || !receipt_build_mismatch(receipt, executionBuild)) && _exempt_governance_ready(receipt, { allow_compiler_issued_full_exempt: true }))) {
    return false;
  }
  if (!_ledger_baseline_assets_current(receipt)) {
    return false;
  }
  for (const item of receipt["requirements"] || []) {
    if (!_isMapping(item)) {
      return false;
    }
    const status = String(item["status"] || "");
    const ref = String(item["evidence_ref"] || "");
    if (status === "flipped" && /^mutation:(?:ledger|run):[0-9a-f]{64}$/.test(ref)) {
      continue;
    }
    if (status === "exempt" && EXEMPT_REASON_CODES.has(String(item["reason_code"] || ""))) {
      continue;
    }
    if (status === "pending" && item["mode"] === "in_case_serialized" && /^mutation:pending:[0-9a-f]{64}$/.test(ref)) {
      continue;
    }
    return false;
  }
  return true;
}

export function receipt_not_ready_reason(receipt: Record<string, any>, artifact_sha256: string, opts: { execution_build?: string | null; allow_compiler_issued_full_exempt?: boolean } = {}): string {
  const executionBuild = opts.execution_build ?? null;
  const allowCompilerIssuedFullExempt = opts.allow_compiler_issued_full_exempt ?? false;
  if (_completed_mutation_receipt_ready(receipt, artifact_sha256, { execution_build: executionBuild, allow_compiler_issued_full_exempt: allowCompilerIssuedFullExempt })) {
    return "";
  }
  if (!_isMapping(receipt)) {
    return "mutation_receipt_not_object";
  }
  if (receipt["schema"] !== MUTATION_SCHEMA) {
    return "mutation_receipt_schema_invalid";
  }
  if (receipt["xlsx_sha256"] !== artifact_sha256) {
    return "mutation_receipt_artifact_mismatch";
  }
  if (!receipt["requirements"]) {
    return "mutation_receipt_requirements_invalid";
  }
  if (!_ledger_baseline_assets_current(receipt)) {
    return "mutation_ledger_baseline_stale";
  }
  if (!receipt_balance_self_consistent(receipt)) {
    return "mutation_receipt_balance_inconsistent";
  }
  if (executionBuild !== null && receipt_build_mismatch(receipt, executionBuild)) {
    return "build_mismatch_at_run";
  }
  const governance = _exempt_governance_check(receipt, { allow_compiler_issued_full_exempt: allowCompilerIssuedFullExempt });
  if (governance) {
    return governance;
  }
  for (const item of receipt["requirements"] || []) {
    if (!_isMapping(item)) {
      return "mutation_requirement_not_object";
    }
    const status = String(item["status"] || "");
    if (status === "flipped" && /^mutation:(?:ledger|run):[0-9a-f]{64}$/.test(String(item["evidence_ref"] || ""))) {
      continue;
    }
    if (status === "exempt" && EXEMPT_REASON_CODES.has(String(item["reason_code"] || ""))) {
      continue;
    }
    return "mutation_requirement_evidence_invalid";
  }
  return "mutation_receipt_not_ready";
}

export function mutation_credential_path(autoid: string, credential_root: string): string {
  const identity = String(autoid || "").trim();
  if (!/^[A-Za-z0-9_.-]+$/.test(identity)) {
    throw new Error("unsafe mutation credential identity");
  }
  return path.join(String(credential_root), `${identity}.json`);
}

function _write_json_atomic(p: string, payload: Record<string, any>): void {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = path.join(path.dirname(p), `.${path.basename(p)}.${process.pid}.${Date.now()}.tmp`);
  try {
    const fd = fs.openSync(tmp, "w");
    try {
      fs.writeSync(fd, JSON.stringify(payload, null, 2) + "\n", null, "utf-8");
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(tmp, p);
  } catch (exc) {
    try {
      fs.unlinkSync(tmp);
    } catch {}
    throw exc;
  }
}

export function publish_mutation_credential(receipt: Record<string, any>, credential_root: string): void {
  const autoid = String(receipt["autoid"] || "");
  const p = mutation_credential_path(autoid, credential_root);
  _write_json_atomic(p, receipt);
}

export function clear_mutation_credential(autoid: string, credential_root: string): void {
  try {
    fs.unlinkSync(mutation_credential_path(autoid, credential_root));
  } catch (exc: any) {
    if (exc?.code !== "ENOENT") throw exc;
  }
}

export function load_mutation_credential(autoid: string, credential_root: string): Record<string, any> {
  try {
    const payload = JSON.parse(fs.readFileSync(mutation_credential_path(autoid, credential_root), "utf-8"));
    return _isMapping(payload) ? payload : {};
  } catch {
    return {};
  }
}

export function mint_legacy_delivery_credential(case_dir: string, opts: { autoid: string; case_artifact: string; final_artifact_sha256: string; delivery_verdict: Record<string, any>; credential_root: string }): Record<string, any> {
  const identity = String(opts.autoid || "").trim();
  const provenancePath = path.join(String(case_dir), "case.provenance.json");
  const casePath = path.join(String(case_dir), "case.xlsx");
  if (!fs.existsSync(provenancePath) || !fs.statSync(provenancePath).isFile()) {
    return { status: "not_applicable" };
  }
  let provenanceBytes: Buffer;
  let provenance: any;
  try {
    provenanceBytes = fs.readFileSync(provenancePath);
    provenance = JSON.parse(provenanceBytes.toString("utf-8"));
  } catch {
    return { status: "rejected", reason_code: "LEGACY_PROVENANCE_UNREADABLE" };
  }
  if (!_isMapping(provenance)) {
    return { status: "rejected", reason_code: "LEGACY_PROVENANCE_INVALID" };
  }
  if (provenance["assertion_schema"] === ASSERTION_TYPE_SCHEMA) {
    return { status: "not_applicable" };
  }
  const provisional = provenance["provisional_at_emit"] ?? provenance["provisional"] ?? true;
  const finalSha = String(opts.final_artifact_sha256 || "").trim().toLowerCase();
  const verdict = _isMapping(opts.delivery_verdict) ? opts.delivery_verdict : {};
  const runId = String(verdict["run_id"] || "").trim();
  if (!/^[0-9a-f]{64}$/.test(finalSha)) {
    return { status: "rejected", reason_code: "FINAL_ARTIFACT_IDENTITY_MISSING" };
  }
  if (!(verdict["ctx"] === "delivery" && verdict["result"] === "pass" && runId && String(verdict["artifact"] || "") === String(opts.case_artifact || "") && String(verdict["volume_artifact_sha256"] || "").toLowerCase() === finalSha)) {
    return { status: "rejected", reason_code: "DELIVERY_VERDICT_IDENTITY_INVALID" };
  }
  let caseSha: string;
  try {
    caseSha = _sha256Hex(fs.readFileSync(casePath));
  } catch {
    return { status: "rejected", reason_code: "CASE_ARTIFACT_UNAVAILABLE" };
  }
  const material = { schema: LEGACY_DELIVERY_CREDENTIAL_SCHEMA, autoid: identity, case_artifact: String(opts.case_artifact || ""), case_artifact_sha256: caseSha, provenance_sha256: _sha256Hex(provenanceBytes), emit_snapshot_provisional: provisional === true, final_artifact_sha256: finalSha, delivery_run_id: runId, verdict: "pass" };
  const credentialId = _sha256Hex(Buffer.from(_canonicalJson(material), "utf-8"));
  const credential = { ...material, credential_id: credentialId };
  let observed: any;
  try {
    const p = mutation_credential_path(`${identity}.legacy-delivery`, opts.credential_root);
    _write_json_atomic(p, credential);
    observed = JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch (exc: any) {
    return { status: "rejected", reason_code: "LEGACY_DELIVERY_CREDENTIAL_WRITE_FAILED", error_type: exc?.constructor?.name ?? "Error" };
  }
  if (JSON.stringify(observed) !== JSON.stringify(credential)) {
    return { status: "rejected", reason_code: "LEGACY_DELIVERY_CREDENTIAL_READBACK_MISMATCH" };
  }
  return { status: "issued", schema: LEGACY_DELIVERY_CREDENTIAL_SCHEMA, credential_id: credentialId, case_artifact_sha256: caseSha, final_artifact_sha256: finalSha, delivery_run_id: runId };
}

export function finalize_mutation_run(case_dir: string, opts: { artifact_sha256: string; run_id: string; verdict: string; credential_root?: string | null; execution_build?: string | null; allow_compiler_issued_full_exempt?: boolean }): Record<string, any> {
  const receiptPath = path.join(String(case_dir), "case.mutation.json");
  const provenancePath = path.join(String(case_dir), "case.provenance.json");
  let receipt: any;
  try {
    receipt = JSON.parse(fs.readFileSync(receiptPath, "utf-8"));
  } catch (exc: any) {
    if (exc?.code === "ENOENT") {
      return { status: "receipt_unavailable", reason_code: "mutation_receipt_missing", error_type: exc?.constructor?.name ?? "Error" };
    }
    if (exc instanceof SyntaxError) {
      return { status: "receipt_invalid", reason_code: "mutation_receipt_invalid_json", error_type: exc?.constructor?.name ?? "Error" };
    }
    if (exc && typeof exc === "object" && "code" in exc) {
      return { status: "receipt_unavailable", reason_code: "mutation_receipt_unreadable", error_type: exc?.constructor?.name ?? "Error" };
    }
    return { status: "receipt_invalid", reason_code: "mutation_receipt_structure_unreadable", error_type: exc?.constructor?.name ?? "Error" };
  }
  if (!_isMapping(receipt)) {
    return { status: "receipt_invalid", reason_code: "mutation_receipt_not_object" };
  }
  if (receipt["schema"] !== MUTATION_SCHEMA) {
    return { status: "receipt_invalid", reason_code: "mutation_receipt_schema_invalid" };
  }
  if (receipt["xlsx_sha256"] !== opts.artifact_sha256) {
    return { status: "identity_mismatch", reason_code: "mutation_receipt_artifact_mismatch" };
  }
  const executionBuild = opts.execution_build ?? null;
  if (executionBuild !== null) {
    const buildMismatch = receipt_build_mismatch(receipt, executionBuild);
    if (buildMismatch) {
      let revoked = true;
      let revokeError = "";
      let revocationFailure: Record<string, string> | null = null;
      const autoidValue = String(receipt["autoid"] || "").trim();
      if (opts.credential_root !== null && opts.credential_root !== undefined && autoidValue) {
        try {
          clear_mutation_credential(autoidValue, opts.credential_root);
        } catch (exc: any) {
          revoked = false;
          revokeError = `${exc?.constructor?.name ?? "Error"}: ${exc?.message ?? exc}`;
          revocationFailure = { error_type: exc?.constructor?.name ?? "Error", message: String(exc?.message ?? exc) };
        }
      }
      const result: Record<string, any> = { status: "rejected", reason_code: "build_mismatch_at_run", detail: buildMismatch };
      if (!revoked) {
        result["credential_revoke_failed"] = revokeError;
        result["revocation_failure"] = revocationFailure;
      }
      return result;
    }
  }
  if (opts.verdict !== "pass") {
    return { status: "unknown", reason_code: "run_verdict_not_pass" };
  }
  const requirements = receipt["requirements"];
  if (!Array.isArray(requirements) || !requirements.length || requirements.some((item) => !_isMapping(item))) {
    return { status: "receipt_invalid", reason_code: "mutation_receipt_requirements_invalid" };
  }
  const pending = requirements.filter((item) => _isMapping(item) && item["status"] === "pending");
  if (!pending.length) {
    const statuses = new Set(((receipt["requirements"] || []) as any[]).filter((item) => _isMapping(item)).map((item) => String(item["status"] || "")));
    const ready = (opts.allow_compiler_issued_full_exempt ?? false) ? mutation_receipt_pass_ready : mutation_receipt_ready;
    if (ready(receipt, opts.artifact_sha256, { execution_build: executionBuild })) {
      return { status: statuses.has("flipped") ? "flipped" : "exempt" };
    }
    const result: Record<string, any> = { status: "unknown", reason_code: receipt_not_ready_reason(receipt, opts.artifact_sha256, { execution_build: executionBuild, allow_compiler_issued_full_exempt: opts.allow_compiler_issued_full_exempt ?? false }) };
    const codes = exempt_governance_block_codes(receipt, { allow_compiler_issued_full_exempt: opts.allow_compiler_issued_full_exempt ?? false });
    if (codes.length > 1 && result["reason_code"] === codes[0]) {
      result["reason_codes"] = [...codes];
    }
    return result;
  }
  if (!String(opts.run_id || "").trim()) {
    return { status: "unknown", reason_code: "run_identity_missing" };
  }
  let provenance: any;
  try {
    provenance = JSON.parse(fs.readFileSync(provenancePath, "utf-8"));
  } catch {
    return { status: "provenance_unreadable", reason_code: "mutation_provenance_unreadable" };
  }
  const replacements: Record<string, string> = {};
  for (const item of pending) {
    const finalRef = _evidence_ref("run", { autoid: receipt["autoid"], artifact_sha256: opts.artifact_sha256, run_id: opts.run_id, assertion_ordinal: item["assertion_ordinal"] });
    replacements[String(item["evidence_ref"] || "")] = finalRef;
    item["status"] = "flipped";
    item["evidence_ref"] = finalRef;
    item["run_receipt"] = { run_id: opts.run_id, artifact_sha256: opts.artifact_sha256 };
  }
  for (const step of provenance["steps"] || []) {
    const assertion = _isMapping(step) ? step["assertion_type"] : null;
    const flip = _isMapping(assertion) ? assertion["flip"] : null;
    const oldRef = _isMapping(flip) ? String(flip["evidence_ref"] || "") : "";
    if (oldRef in replacements) {
      flip["evidence_ref"] = replacements[oldRef];
    }
  }
  _write_json_atomic(provenancePath, provenance);
  _write_json_atomic(receiptPath, receipt);
  if (opts.credential_root !== null && opts.credential_root !== undefined) {
    publish_mutation_credential(receipt, opts.credential_root);
  }
  return { status: "flipped", finalized: pending.length, run_id: opts.run_id };
}

export function build_mutation_pass_audit_fact(case_dir: string, opts: { autoid: string; final_artifact_sha256: string }): Record<string, any> {
  const identity = String(opts.autoid || "").trim();
  const finalSha = String(opts.final_artifact_sha256 || "").trim().toLowerCase();
  const base: Record<string, any> = { ev: "pass_audit", aid: identity, schema: PASS_AUDIT_SCHEMA, artifact: "case.xlsx", artifact_sha256: finalSha, audit_basis: "mutation_flip", status: "unavailable", outcome: "unknown", total_assertions: null, flipped_assertions: null, exempt_assertions: null, compiler_issued_exempt_assertions: null, author_declared_exempt_assertions: null, pending_assertions: null };
  const receiptPath = path.join(String(case_dir), "case.mutation.json");
  const casePath = path.join(String(case_dir), "case.xlsx");
  let caseSha = "";
  try {
    caseSha = _sha256Hex(fs.readFileSync(casePath));
  } catch {}
  base["case_artifact_sha256"] = caseSha;
  let material: Record<string, any>;
  let receiptBytes: Buffer;
  let receipt: any;
  try {
    receiptBytes = fs.readFileSync(receiptPath);
    receipt = JSON.parse(receiptBytes.toString("utf-8"));
  } catch (exc: any) {
    base["reason_code"] = "MUTATION_RECEIPT_UNAVAILABLE";
    base["read_error"] = { error_type: exc?.constructor?.name ?? "Error" };
    material = { aid: identity, final_artifact_sha256: finalSha, case_artifact_sha256: caseSha, reason_code: base["reason_code"], read_error: base["read_error"] };
    base["audit_revision"] = _sha256Hex(Buffer.from(_canonicalJson(material), "utf-8")).slice(0, 24);
    return base;
  }
  const receiptSha = _sha256Hex(receiptBytes);
  base["mutation_receipt_sha256"] = receiptSha;
  base["case_artifact_sha256"] = caseSha;
  const requirements = _isMapping(receipt) ? receipt["requirements"] : null;
  const rows = Array.isArray(requirements) ? requirements.filter((item: any) => _isMapping(item)) : [];
  const statuses = rows.map((item: any) => String(item["status"] || ""));
  const [, , , issued, discretionary] = _governance_counts(rows);
  const counts = { total_assertions: rows.length, flipped_assertions: statuses.filter((s: string) => s === "flipped").length, exempt_assertions: statuses.filter((s: string) => s === "exempt").length, compiler_issued_exempt_assertions: issued, author_declared_exempt_assertions: discretionary - issued, pending_assertions: statuses.filter((s: string) => !["flipped", "exempt"].includes(s)).length };
  if (!/^[0-9a-f]{64}$/.test(finalSha)) {
    base["reason_code"] = "FINAL_ARTIFACT_IDENTITY_MISSING";
  } else if (!_isMapping(receipt) || receipt["schema"] !== MUTATION_SCHEMA) {
    base["reason_code"] = "MUTATION_RECEIPT_SCHEMA_INVALID";
  } else if (String(receipt["autoid"] || "") !== identity) {
    base["reason_code"] = "MUTATION_RECEIPT_AUTOID_MISMATCH";
  } else if (!caseSha || receipt["xlsx_sha256"] !== caseSha) {
    base["reason_code"] = "MUTATION_RECEIPT_ARTIFACT_MISMATCH";
  } else if (!rows.length || rows.length !== (requirements as any[]).length) {
    base["reason_code"] = "MUTATION_REQUIREMENTS_INVALID";
  } else {
    Object.assign(base, counts);
    if (base["exempt_assertions"] && !_exempt_governance_ready(receipt)) {
      base["status"] = "incomplete";
      base["reason_code"] = "MUTATION_EXEMPT_GOVERNANCE_INVALID";
    } else if (!mutation_receipt_ready(receipt, caseSha)) {
      base["status"] = "incomplete";
      base["reason_code"] = "MUTATION_FLIP_INCOMPLETE";
    } else if (base["exempt_assertions"]) {
      base["status"] = "incomplete";
      base["reason_code"] = "MUTATION_EXEMPT_PRESENT";
    } else {
      base["status"] = "complete";
      base["outcome"] = "clean";
    }
  }
  material = { aid: identity, final_artifact_sha256: finalSha, case_artifact_sha256: caseSha, mutation_receipt_sha256: receiptSha, status: base["status"], reason_code: base["reason_code"] ?? "" };
  base["audit_revision"] = _sha256Hex(Buffer.from(_canonicalJson(material), "utf-8")).slice(0, 24);
  return base;
}
