import crypto from "node:crypto";
import { _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.xml_conflict_core");

export const CONFLICT_CLAIM_SCHEMA = "ist.delta.conflict-claim";
export const S3_CLAIM_KIND = "xml_command_shape_conflict";
export const S3_REASON_CODE = "parameter_contract_violation";
export const S3_DELTA_SCHEMA = "ist.delta.xml-command-shape-delta";
export const S3_OPTIONS = ["xml_replace_command", "xml_keep_case_blocked", "abandon_generation"];
export const S3_NEAR_HEAD_REASON_CODE = "command_head_near_miss";
export const S3_NEAR_HEAD_DELTA_SCHEMA = "ist.delta.xml-command-near-head-delta";
export const S4_CLAIM_KIND = "xml_expectation_conflict";
export const S4_REASON_CODE = "capability_xml_expectation_mismatch";
export const S4_DELTA_SCHEMA = "ist.delta.xml-expectation-delta";
export const S4_OPTIONS = ["use_xml_expectation", "use_case_expectation", "abandon_generation"];

export type Verdict = Record<string, any>;
export type Resolve = (command: string) => Verdict;

function _canonical_sha256(payload: Record<string, any>): string {
  return crypto.createHash("sha256").update(JSON.stringify(payload, Object.keys(payload).sort())).digest("hex");
}

export function is_scenario3_violation(verdict: Verdict): boolean {
  return Boolean(verdict.kind === "hit" && !verdict.parameters_valid && verdict.reason_code === S3_REASON_CODE && verdict.origin === "vendor_xml");
}

const _LOCATOR_TOKEN = /^\[[^\]]*\]$/;

export function is_command_attempt(occurrence: Record<string, any>, verdict: Verdict): boolean {
  if (verdict.kind !== "hit") {
    return true;
  }
  const head = String(verdict.head || "").split(/\s+/).filter(Boolean);
  const { norm_command_tokens } = require("./vendor_stdlib");
  const remainder = norm_command_tokens(String(occurrence.command || "")).slice(head.length);
  if (
    occurrence.source_surface === "mindmap_step" &&
    verdict.parameters_valid === false &&
    ((verdict.parameter_error || {}).code === "arity_too_few") &&
    !remainder.some((token: string) => !_LOCATOR_TOKEN.test(token))
  ) {
    return false;
  }
  if (!("truncated_by" in occurrence)) {
    return true;
  }
  if (occurrence.truncated_by === "cjk") {
    return false;
  }
  if (head.length < 2) {
    return false;
  }
  return remainder.some((token: string) => !_LOCATOR_TOKEN.test(token));
}

export function slice_is_admissible(occurrence: Record<string, any>, verdict: Verdict): boolean {
  return is_command_attempt(occurrence, verdict);
}

export function scenario3_violations(commands: Iterable<Record<string, any>>, resolve: Resolve): Record<string, any>[] {
  const out: Record<string, any>[] = [];
  for (const item of commands) {
    const command = String(item.command || "");
    const verdict = resolve(command);
    if (!is_scenario3_violation(verdict)) {
      continue;
    }
    if (!is_command_attempt(item, verdict)) {
      continue;
    }
    out.push({ occurrence_index: Number(item.occurrence_index || 0), command, result: verdict });
  }
  return out;
}

export function build_head_index(heads: any): Map<number, string[]> {
  const grouped = new Map<number, string[]>();
  for (const head of heads || []) {
    const parts = String(head || "").split(/\s+/).filter(Boolean);
    if (parts.length) {
      const size = parts.length;
      if (!grouped.has(size)) grouped.set(size, []);
      grouped.get(size)!.push(parts.join(" "));
    }
  }
  const out = new Map<number, string[]>();
  for (const [size, names] of grouped) {
    out.set(size, [...names].sort());
  }
  return out;
}

export function build_xml_menu_index(heads: any): Map<string, string[]> {
  const grouped = new Map<string, Set<string>>();
  const table = heads && typeof heads === "object" && !Array.isArray(heads) ? heads : {};
  for (const [rawHead, rawEntry] of Object.entries(table)) {
    if (typeof rawEntry !== "object" || rawEntry === null) {
      continue;
    }
    if (String((rawEntry as any).origin || "") !== "vendor_xml") {
      continue;
    }
    const locator = String((rawEntry as any).src || "");
    const [sourceKind, ...restParts] = locator.split(":");
    if (sourceKind !== "vendor_xml" || restParts.length < 2) {
      continue;
    }
    const xmlPath = restParts.slice(1).join(":");
    const parts = xmlPath.split("/").map((p) => p.trim().toLowerCase()).filter(Boolean);
    const menuParts = parts.slice(1, -1);
    const head = String(rawHead || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
    const commandPath = parts.slice(1).join(" ");
    if (!head || head !== commandPath) {
      continue;
    }
    for (let depth = 1; depth <= menuParts.length; depth++) {
      const menu = menuParts.slice(0, depth).join(" ");
      if (menu) {
        if (!grouped.has(menu)) grouped.set(menu, new Set());
        grouped.get(menu)!.add(head);
      }
    }
  }
  const out = new Map<string, string[]>();
  for (const [menu, descendants] of [...grouped.entries()].sort()) {
    out.set(menu, [...descendants].sort());
  }
  return out;
}

function _one_edit_apart(left: string, right: string): boolean {
  if (left === right) {
    return false;
  }
  if (Math.abs(left.length - right.length) > 1) {
    return false;
  }
  if (left.length === right.length) {
    let diff = 0;
    for (let i = 0; i < left.length; i++) {
      if (left[i] !== right[i]) diff++;
    }
    return diff === 1;
  }
  const [short, long] = left.length < right.length ? [left, right] : [right, left];
  let index = 0;
  while (index < short.length && short[index] === long[index]) {
    index++;
  }
  return short.slice(index) === long.slice(index + 1);
}

export function near_head_candidate(
  command: string,
  headIndex: Map<number, string[]>,
  menuIndex: Map<string, string[]> | null = null
): [string, string] | null {
  const { norm_command_tokens } = require("./vendor_stdlib");
  const tokens = norm_command_tokens(command);
  const maxSize = Math.min(tokens.length, 8);
  for (let size = maxSize; size >= 2; size--) {
    const prefix = tokens.slice(0, size);
    const hits: string[] = [];
    for (const head of headIndex.get(size) || []) {
      const parts = head.split(/\s+/);
      const differing: number[] = [];
      for (let i = 0; i < size; i++) {
        if (parts[i] !== prefix[i]) differing.push(i);
      }
      if (differing.length !== 1) continue;
      const position = differing[0];
      if (position !== size - 1) continue;
      if (_one_edit_apart(prefix[position], parts[position])) {
        hits.push(head);
      }
    }
    if (hits.length) {
      const authored = prefix.join(" ");
      if (menuIndex && menuIndex.has(authored)) {
        return null;
      }
      return [authored, [...hits].sort()[0]];
    }
  }
  return null;
}

export function generation_binding(inventory: any, capabilityReceipt: any = null): Record<string, any> {
  const inv = inventory && typeof inventory === "object" && !Array.isArray(inventory) ? inventory : {};
  const source = inv.source && typeof inv.source === "object" && !Array.isArray(inv.source) ? inv.source : {};
  const binding: Record<string, any> = {
    version: String(inv.version || ""),
    build: String(inv.device_os_build || ""),
    source_filename: String(source.filename || ""),
    source_sha256: String(source.sha256 || ""),
  };
  if (capabilityReceipt && typeof capabilityReceipt === "object" && !Array.isArray(capabilityReceipt)) {
    for (const key of ["bed", "full_version", "product", "platform", "generation_id", "manifest_sha256", "projection_sha256"]) {
      binding[key] = String(capabilityReceipt[key] || "");
    }
  }
  return binding;
}

function _xml_parameter_signature(result: Record<string, any>): string {
  const head = String(result.head || "").trim();
  const error = result.parameter_error;
  if (!head || typeof error !== "object" || error === null) {
    return head;
  }
  const required = error.required_min;
  const maximum = error.pmax;
  if (
    typeof required === "number" && !Number.isNaN(required) &&
    typeof maximum === "number" && !Number.isNaN(maximum) &&
    required >= 0 && required <= maximum && maximum <= 64
  ) {
    const placeholders: string[] = [];
    for (let i = 1; i <= required; i++) placeholders.push(`<arg${i}>`);
    for (let i = required + 1; i <= maximum; i++) placeholders.push(`[arg${i}]`);
    return [head, ...placeholders].join(" ");
  }
  const index = error.argument_index;
  const expectedType = String(error.expected_type || "").trim().toLowerCase();
  if (typeof index === "number" && !Number.isNaN(index) && index > 0) {
    const marker = expectedType ? `${expectedType}:arg${index}` : `arg${index}`;
    return `${head} <${marker}>`;
  }
  return head;
}

export function scenario3_delta_payload(autoid: string, occurrence: Record<string, any>, generation: Record<string, any>): Record<string, any> {
  const result = occurrence.result || {};
  return {
    autoid,
    occurrence_index: occurrence.occurrence_index,
    command: occurrence.command,
    xml_command: String(result.head || ""),
    xml_signature: _xml_parameter_signature(result),
    xml_locator: String(result.src || ""),
    device_build: String(result.device_build || ""),
    parameter_error: { ...(result.parameter_error || {}) },
    capability_generation: generation,
  };
}

export function scenario3_claim(autoid: string, occurrence: Record<string, any>, generation: Record<string, any>): Record<string, any> {
  const { conflict_chain_id } = require("../ist_core/compile_engine/conflict_chain");
  const result = occurrence.result || {};
  const deltaPayload = scenario3_delta_payload(autoid, occurrence, generation);
  const deltaId = _canonical_sha256({ schema: S3_DELTA_SCHEMA, payload: deltaPayload });
  const chainId = conflict_chain_id({ autoid, scenario: "scenario_3", delta_id: deltaId, payload: deltaPayload });
  return {
    schema: CONFLICT_CLAIM_SCHEMA,
    source_kind: "CapabilityXml",
    claim_kind: S3_CLAIM_KIND,
    conflict_scenario: "scenario_3",
    reason_code: S3_REASON_CODE,
    delta_id: deltaId,
    conflict_chain_id: chainId,
    options: [...S3_OPTIONS],
    xml_present: true,
    command: occurrence.command,
    xml_command: String(result.head || ""),
    xml_signature: _xml_parameter_signature(result),
    xml_locator: String(result.src || ""),
    device_build: String(result.device_build || ""),
    parameter_error: { ...(result.parameter_error || {}) },
    occurrence_index: occurrence.occurrence_index,
    capability_generation: generation,
    requires_user_decision: true,
    terminal: false,
    reason: "用例命令与设备 XML 的参数形态不一致",
  };
}

export function scenario3_ledger_mutator(autoid: string, violations: Record<string, any>[], generation: Record<string, any>): (claims: any[]) => any[] {
  return (claims: any[]) => {
    const kept = claims.filter((claim: any) => !(claim.claim_kind === S3_CLAIM_KIND && claim.reason_code === S3_REASON_CODE));
    for (const occurrence of violations) {
      kept.push(scenario3_claim(autoid, occurrence, generation));
    }
    return kept;
  };
}

export function near_head_violations(
  commands: Iterable<Record<string, any>>,
  resolve: Resolve,
  headIndex: Map<number, string[]>,
  heads: any = null
): Record<string, any>[] {
  const table = heads && typeof heads === "object" && !Array.isArray(heads) ? heads : {};
  const menuIndex = build_xml_menu_index(table);
  const out: Record<string, any>[] = [];
  for (const item of commands) {
    const command = String(item.command || "");
    if (!command.trim()) continue;
    const verdict = resolve(command);
    if (verdict.kind === "hit") continue;
    const near = near_head_candidate(command, headIndex, menuIndex);
    if (near === null) continue;
    const entry = (table as any)[near[1]];
    if (typeof entry !== "object" || entry === null) continue;
    if (String(entry.origin || "") !== "vendor_xml") continue;
    const locator = String(entry.src || "");
    if (!locator) continue;
    out.push({
      occurrence_index: Number(item.occurrence_index || 0),
      command,
      authored_head: near[0],
      xml_command: near[1],
      xml_locator: locator,
      result: verdict,
    });
  }
  return out;
}

export function near_head_delta_payload(autoid: string, occurrence: Record<string, any>, generation: Record<string, any>): Record<string, any> {
  const result = occurrence.result || {};
  return {
    autoid,
    occurrence_index: occurrence.occurrence_index,
    command: occurrence.command,
    authored_head: occurrence.authored_head,
    xml_command: occurrence.xml_command,
    xml_locator: String(occurrence.xml_locator || ""),
    device_build: String(result.device_build || ""),
    capability_generation: generation,
  };
}

export function near_head_claim(autoid: string, occurrence: Record<string, any>, generation: Record<string, any>): Record<string, any> {
  const { conflict_chain_id } = require("../ist_core/compile_engine/conflict_chain");
  const deltaPayload = near_head_delta_payload(autoid, occurrence, generation);
  const deltaId = _canonical_sha256({ schema: S3_NEAR_HEAD_DELTA_SCHEMA, payload: deltaPayload });
  const chainId = conflict_chain_id({ autoid, scenario: "scenario_3", delta_id: deltaId, payload: deltaPayload });
  const result = occurrence.result || {};
  return {
    schema: CONFLICT_CLAIM_SCHEMA,
    source_kind: "CapabilityXml",
    claim_kind: S3_CLAIM_KIND,
    conflict_scenario: "scenario_3",
    reason_code: S3_NEAR_HEAD_REASON_CODE,
    delta_id: deltaId,
    conflict_chain_id: chainId,
    options: [...S3_OPTIONS],
    xml_present: true,
    command: occurrence.command,
    authored_head: occurrence.authored_head,
    xml_command: occurrence.xml_command,
    xml_locator: String(occurrence.xml_locator || ""),
    device_build: String(result.device_build || ""),
    parameter_error: {},
    occurrence_index: occurrence.occurrence_index,
    capability_generation: generation,
    requires_user_decision: true,
    terminal: false,
    reason: "用例写的命令名在设备命令树里不存在，树里有一个只差一个字符的",
  };
}

export function near_head_ledger_mutator(autoid: string, violations: Record<string, any>[], generation: Record<string, any>): (claims: any[]) => any[] {
  return (claims: any[]) => {
    const kept = claims.filter((claim: any) => !(claim.claim_kind === S3_CLAIM_KIND && claim.reason_code === S3_NEAR_HEAD_REASON_CODE));
    for (const occurrence of violations) {
      kept.push(near_head_claim(autoid, occurrence, generation));
    }
    return kept;
  };
}

export function static_scenario3_ledger_mutator(
  autoid: string,
  parameterViolations: Record<string, any>[],
  nearHeadMisses: Record<string, any>[],
  generation: Record<string, any>,
  supersededDeltaIds: Iterable<string> = []
): (claims: any[]) => any[] {
  const fresh = [
    ...parameterViolations.map((occ) => scenario3_claim(autoid, occ, generation)),
    ...nearHeadMisses.map((occ) => near_head_claim(autoid, occ, generation)),
  ];
  const replaceIds = new Set<string>([
    ...[...supersededDeltaIds].filter((v) => String(v)).map(String),
    ...fresh.map((c) => String(c.delta_id || "")).filter(Boolean),
  ]);
  return (claims: any[]) => {
    const kept = claims.filter((claim: any) => !(claim && typeof claim === "object" && replaceIds.has(String(claim.delta_id || ""))));
    return [...kept, ...fresh];
  };
}

export function xml_result_assertions(verdict: Verdict, validOperators: Iterable<string>): Record<string, string>[] {
  if (!(verdict.kind === "hit" && verdict.origin === "vendor_xml")) {
    return [];
  }
  const rawResults = verdict.results;
  if (!Array.isArray(rawResults) || !rawResults.length) {
    return [];
  }
  const operators = new Set(validOperators);
  const assertions: Record<string, string>[] = [];
  for (const declaration of rawResults) {
    if (typeof declaration !== "object" || declaration === null || !Object.keys(declaration).every((k) => ["operator", "text", "locator"].includes(k))) {
      return [];
    }
    const operator = String(declaration.operator || "").trim();
    const text = String(declaration.text || "");
    const locator = String(declaration.locator || "").trim();
    if (!operators.has(operator) || !text || !locator) {
      return [];
    }
    if (operator === "found_times") {
      return [];
    }
    assertions.push({ operator, value: text, locator });
  }
  return assertions;
}

export function scenario4_conflict(group: Record<string, any>, verdict: Verdict, validOperators: Iterable<string>): Record<string, any> | null {
  const xmlAssertions = xml_result_assertions(verdict, validOperators);
  if (!xmlAssertions.length) return null;
  const caseAssertions = (group.assertions || []).map((item: any) => ({ ...item }));
  if (!caseAssertions.length) return null;
  const key = (a: any) => `${a.operator}${a.value}`;
  const caseMultiset = caseAssertions.map(key).sort();
  const xmlMultiset = xmlAssertions.map(key).sort();
  if (JSON.stringify(caseMultiset) === JSON.stringify(xmlMultiset)) return null;
  return {
    occurrence_index: Number(group.occurrence_index),
    original_command: String(group.command),
    rewritten_command: String(verdict.head || group.command),
    xml_locator: String(verdict.src || ""),
    case_assertions: caseAssertions,
    xml_assertions: xmlAssertions,
  };
}

export function scenario4_claim(autoid: string, conflict: Record<string, any>, generation: Record<string, any>): Record<string, any> {
  const { conflict_chain_id } = require("../ist_core/compile_engine/conflict_chain");
  const deltaPayload = { autoid, ...conflict, capability_generation: generation };
  const deltaId = _canonical_sha256({ schema: S4_DELTA_SCHEMA, payload: deltaPayload });
  return {
    schema: CONFLICT_CLAIM_SCHEMA,
    source_kind: "CapabilityXml",
    claim_kind: S4_CLAIM_KIND,
    conflict_scenario: "scenario_4",
    reason_code: S4_REASON_CODE,
    delta_id: deltaId,
    conflict_chain_id: conflict_chain_id({ autoid, scenario: "scenario_4", delta_id: deltaId, payload: deltaPayload }),
    options: [...S4_OPTIONS],
    xml_present: true,
    ...conflict,
    case_expectation: JSON.stringify(conflict.case_assertions),
    xml_expectation: JSON.stringify(conflict.xml_assertions),
    case_expectation_supported: false,
    capability_generation: generation,
    requires_user_decision: true,
    terminal: false,
    reason: "用例静态断言与设备 XML 的结构化结果声明不一致",
  };
}

export function scenario4_ledger_mutator(autoid: string, conflicts: Record<string, any>[], generation: Record<string, any>): (claims: any[]) => any[] {
  return (claims: any[]) => {
    const kept = claims.filter((claim: any) => !(claim.claim_kind === S4_CLAIM_KIND && claim.reason_code === S4_REASON_CODE));
    for (const conflict of conflicts) {
      kept.push(scenario4_claim(autoid, conflict, generation));
    }
    return kept;
  };
}

const _CJK_BOUNDARY = /[⺀-鿿豈-﫿︰-﹏＀-￯　-〿]/;
const _SENTENCE_BREAK = /[,;]/;
const _ASCII_WORD = /[A-Za-z][A-Za-z0-9_-]*/g;

function _normalize_unicode_spaces(text: string): string {
  return [...String(text || "")].map((ch) => (/\s/.test(ch) && ch.charCodeAt(0) > 127 ? " " : ch)).join("");
}

export function command_head_first_tokens(heads: any): Set<string> {
  const out = new Set<string>();
  for (const head of heads || []) {
    const parts = String(head || "").split(/\s+/).filter(Boolean);
    if (parts.length) out.add(parts[0].toLowerCase());
  }
  return out;
}

export function mindmap_command_slices(line: string, headFirstTokens: Set<string>): Record<string, any>[] {
  const text = String(line || "");
  if (!text.trim()) return [];
  const out: Record<string, any>[] = [];
  const re = new RegExp(_ASCII_WORD.source, "g");
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (!headFirstTokens.has(match[0].toLowerCase())) continue;
    const prev = match.index ? text[match.index - 1] : "";
    if (prev && /[\w]/.test(prev) && prev.charCodeAt(0) < 128) continue;
    let tail = text.slice(match.index);
    const cjk = tail.match(_CJK_BOUNDARY);
    const punct = tail.match(_SENTENCE_BREAK);
    const candidates = [cjk, punct].filter(Boolean) as RegExpMatchArray[];
    let truncatedBy = "eol";
    if (candidates.length) {
      const first = candidates.reduce((a, b) => (a.index! < b.index! ? a : b));
      truncatedBy = first === cjk ? "cjk" : "punct";
      tail = tail.slice(0, first.index);
    }
    const rawSpanEnd = match.index + tail.length;
    tail = _normalize_unicode_spaces(tail).trim();
    if (tail) {
      out.push({ command: tail, truncated_by: truncatedBy, span_start: match.index, span_end: rawSpanEnd });
    }
  }
  return out;
}

export function mindmap_command_occurrences(case_: Record<string, any>, headFirstTokens: Set<string> | null = null): Record<string, any>[] {
  const out: Record<string, any>[] = [];
  let index = 0;
  for (const step of case_.steps || []) {
    if (typeof step !== "object" || step === null) continue;
    for (const line of String(step.text || "").split(/\r?\n/)) {
      const text = line.trim();
      if (!text) continue;
      const stepN = String(step.n || "");
      out.push({ command: text, occurrence_index: index, step_n: stepN, source_surface: "mindmap_step" });
      if (headFirstTokens) {
        const seen = new Set([text]);
        let coveredUntil = -1;
        let sliceIndex = 0;
        for (const sliced of mindmap_command_slices(line, headFirstTokens)) {
          sliceIndex++;
          const command = sliced.command;
          const spanStart = sliced.span_start;
          const spanEnd = sliced.span_end;
          if (spanStart !== undefined && spanStart < coveredUntil) continue;
          if (spanEnd !== undefined) coveredUntil = Math.max(coveredUntil, Number(spanEnd));
          if (seen.has(command)) continue;
          seen.add(command);
          out.push({
            command,
            occurrence_index: index,
            slice_index: sliceIndex,
            truncated_by: sliced.truncated_by,
            step_n: stepN,
            source_surface: "mindmap_step",
          });
        }
      }
      index++;
    }
  }
  return out;
}

export function mindmap_assertion_groups(case_: Record<string, any>, resolve: Resolve): Record<string, any>[] {
  const byStep = new Map<string, Record<string, string>[]>();
  for (const item of case_.expectations_by_step || []) {
    if (typeof item !== "object" || item === null) continue;
    const assertion = item.assertion;
    if (typeof assertion !== "object" || assertion === null) continue;
    const operator = String(assertion.operator || "").trim();
    const value = String(assertion.value || "");
    if (!operator || !value) continue;
    const key = String(item.n || "").trim();
    if (!byStep.has(key)) byStep.set(key, []);
    byStep.get(key)!.push({ operator, value });
  }
  if (!byStep.size) return [];
  const groups: Record<string, any>[] = [];
  for (const occurrence of mindmap_command_occurrences(case_)) {
    const assertions = byStep.get(occurrence.step_n);
    if (!assertions) continue;
    const verdict = resolve(occurrence.command);
    if (verdict.kind !== "hit") continue;
    const siblings = mindmap_command_occurrences(case_).filter(
      (other) =>
        other.step_n === occurrence.step_n &&
        other.command !== occurrence.command &&
        resolve(other.command).kind === "hit"
    );
    if (siblings.length) continue;
    groups.push({ occurrence_index: occurrence.occurrence_index, command: occurrence.command, assertions });
  }
  return groups;
}
