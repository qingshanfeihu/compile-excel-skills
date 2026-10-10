import fs from "node:fs";
import path from "node:path";
import {
  CONTRACT_CARD_MAX_BYTES,
  scan_json_budget,
  validate_json_budget,
  sha256_bytes,
  stat_regular_nofollow,
  read_regular_nofollow,
  read_regular_at_nofollow,
} from "./_sealed_io";
import { build_validation_cards, build_warning_panel, ContractError, encode_json_atomic, normalize_contract, write_json_atomic } from "./contract_entry";
import { accepts_schema } from "../../ist_emit/schema_identity";

const AUTHORED_CONFLICT_KEY = "authored_conflict";
type ConsistencyStampFailure = string;

function premise_stamp_failure(index: number, problem: string): ConsistencyStampFailure {
  return `premise[${index}]_${problem}`;
}

function conflict_surface_stamp_failure(index: number, problem: string): ConsistencyStampFailure {
  return `authored_conflict_surface[${index}]_${problem}`;
}

function recompose_consistency_failure(value: any): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "consistency_not_object";
  const keys = Object.keys(value).sort();
  const required = ["case_locator", "case_quote", "incompatibility", "premises", "schema", "spec_clauses", "spec_locator", "spec_quote", "verdict"].sort();
  const optional = [AUTHORED_CONFLICT_KEY, "missing_preconditions"];
  const allowed = new Set([...required, ...optional]);
  if (keys.some((k) => !allowed.has(k))) return "consistency_keys_invalid";
  for (const k of required) {
    if (!(k in value)) return "consistency_keys_invalid";
  }
  if (value.schema !== "ist.consistency-material") return "consistency_schema_invalid";
  if (!["consistent", "conflict"].includes(String(value.verdict))) return "consistency_verdict_invalid";
  for (const k of ["spec_locator", "spec_quote", "case_locator", "case_quote", "incompatibility"]) {
    if (typeof value[k] !== "string" || !value[k].trim()) return "consistency_text_field_invalid";
  }
  return "";
}

function clause_coverage_failure(specQuote: string, clauses: any): string {
  if (clauses === null || clauses === undefined) return "";
  if (!Array.isArray(clauses) || clauses.some((c) => typeof c !== "string" || !c.trim())) {
    return "consistency_spec_clauses_invalid";
  }
  const quote = String(specQuote || "");
  for (const clause of clauses) {
    if (!quote.includes(clause)) return "consistency_spec_clause_not_covered";
  }
  return "";
}

function _scenario1_clause_failure(specQuote: string, clauses: any): string {
  if (clauses === null || clauses === undefined) return "scenario1_clause_consistent_branch";
  const failure = clause_coverage_failure(specQuote, clauses);
  return failure || "scenario1_clause_consistent_branch";
}

function _criterion_disclosure_message(normalizedClaim: any): string {
  const status = String(normalizedClaim?.status || "unmatched");
  const shapeKey = String(normalizedClaim?.shape_key || "");
  const versionFamily = String(normalizedClaim?.version_family || "");
  if (status === "matched") {
    return `归类预期已匹配判据（${shapeKey || "未命名形态"}${versionFamily ? `，${versionFamily}` : ""}）`;
  }
  return `归类预期未匹配到判据（${shapeKey || "未命名形态"}${versionFamily ? `，${versionFamily}` : ""}），按作者原文断言处理`;
}

const _PROJECTION_JSON_MAX_BYTES = 2 * 1024 * 1024;
const _PROJECTION_JSON_MAX_TOKENS = 400000;
const _PROJECTION_JSON_MAX_DEPTH = 64;
const MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME = "mindmap_disclosures.json";
const DISCLOSURE_STORAGE_CONTRACT_REFS = "contract-refs";
const _DISCLOSURE_REF_KEYS = new Set(["autoid", "expectation_id"]);
const _DISCLOSURE_REF_FIELDS = ["normalized_claim", "rule_identity", "evidence_chain", "author_veto"];
const DISCLOSURE_LOAD_SCHEMA = "ist.mindmap.disclosure-load";

export class MachineMindmapError extends Error {}

const _SHA256_RE = /^[0-9a-f]{64}$/;
const _LOCATOR_TOKEN = "[0-9A-Za-z\\u4e00-\\u9fff_-]+";
const _ORIGIN_STEP_RE = /^step:([0-9A-Za-z\u4e00-\u9fff_-]+)$/;
const _ORIGIN_EXPECT_RE = /^expectation:([0-9A-Za-z\u4e00-\u9fff_-]+)$/;
const _ORIGIN_SPEC_RE = /^spec:([^:]+):(\d+-\d+)$/;
const _ORIGIN_DEFECT_SPEC_RE = /^defect:([A-Za-z0-9_-]+):([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)$/;
const _CARD_BUCKETS = new Set(["exp_recipe", "step_recipe"]);
const _SOURCE_STATUSES = new Set(["complete", "incomplete"]);
const _TYPED_ASSERTION_STATUSES = new Set(["pending", "ready"]);
const _SCENARIO2_REASON = "scenario2_incomplete_case";
const _SCENARIO2_SOURCE_FIELDS = ["intent", "steps", "expectation"];
const _VALUE_GROUNDING = "author_sealed_text";
const _CONSISTENCY_DRAFT_SCHEMA = "ist.consistency-draft";
export const _CONSISTENCY_MATERIAL_SCHEMA = "ist.consistency-material";
export const _CONSISTENCY_MATERIAL_KEYS = new Set([
  "schema", "autoid", "verdict", "spec_locator", "spec_quote", "spec_clauses",
  "case_locator", "case_quote", "incompatibility", "premises",
]);

export function origin_zh(origin: any): string {
  const text = String(origin || "").trim();
  if (!text) return "（无出处）";
  if (text === "title") return "脑图：标题";
  let m = _ORIGIN_STEP_RE.exec(text);
  if (m) return `脑图：步骤${m[1]}`;
  m = _ORIGIN_EXPECT_RE.exec(text);
  if (m) return `脑图：预期${m[1]}`;
  m = _ORIGIN_SPEC_RE.exec(text);
  if (m) return `规格书：${m[1]} 第${m[2]}行`;
  m = _ORIGIN_DEFECT_SPEC_RE.exec(text);
  if (m) return `缺陷规格：${m[1]}/${m[2]}（${m[3]}）`;
  return text;
}

function _verbatim_quarantine_error(fields: string): string {
  return `机器稿与脑图原文不一致（${fields}），本轮退回，不编写`;
}

function _verbatim_quarantine_disclosure(fields: string): string {
  return `机器稿改写了脑图原文（${fields}），不能当成「按你的脑图原文」`;
}

function _invalid_contract_user_text(reason: string): [string, string] {
  const text = String(reason || "");
  return ["机械脑图没过复查，本轮退回，不编写", `机械脑图没过复查（${text}），不能当成「按你的脑图原文」`];
}

export function load_machine_mindmap(mmPath: string): [any, string] {
  let raw: Buffer;
  try {
    raw = fs.readFileSync(mmPath);
  } catch (exc: any) {
    throw new MachineMindmapError(`machine mindmap is unavailable: ${exc.message || exc}`);
  }
  try {
    validate_json_budget(raw, { errorType: MachineMindmapError, message: "machine mindmap exceeds the JSON structure budget", maxTokens: _PROJECTION_JSON_MAX_TOKENS, maxDepth: _PROJECTION_JSON_MAX_DEPTH });
  } catch (exc: any) {
    if (exc instanceof MachineMindmapError) throw exc;
    throw exc;
  }
  let data: any;
  try {
    data = JSON.parse(raw.toString("utf8").replace(/^﻿/u, ""));
  } catch {
    throw new MachineMindmapError("machine mindmap is not valid JSON");
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new MachineMindmapError("machine mindmap top level must be an object");
  }
  return [data, sha256_bytes(raw)];
}

export function _canonical_sha256(value: any): string {
  return sha256_bytes(Buffer.from(canonicalJson(value), "utf8"));
}

function canonicalJson(value: any): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function _expectation_id(autoid: string, step: string, index: number): string {
  const digest = _canonical_sha256([String(autoid || ""), String(step || ""), index]);
  return `exp-${digest.slice(0, 16)}`;
}

function _semantic_key(autoid: string, step: string): string {
  const digest = _canonical_sha256(["semantic", String(autoid || ""), String(step || "")]);
  return `sem-${digest.slice(0, 16)}`;
}

function _author_claim(opts: { autoid: string; item: any; index: number; mindmap_source_sha256: string }): any {
  const { autoid, item, index, mindmap_source_sha256 } = opts;
  const origin = String(item.origin || "").trim();
  const step = String(item.n || "").trim();
  return {
    expectation_id: _expectation_id(autoid, step, index),
    semantic_key: _semantic_key(autoid, step),
    origin,
    source_sha256: mindmap_source_sha256,
  };
}

function _defect_spec_claim(opts: { autoid: string; item: any; index: number; defect_spec_receipt?: any }): any {
  const { autoid, item, index, defect_spec_receipt } = opts;
  const origin = String(item.origin || "").trim();
  const step = String(item.n || "").trim();
  const out: any = {
    expectation_id: _expectation_id(autoid, step, index),
    semantic_key: _semantic_key(autoid, step),
    origin,
  };
  if (defect_spec_receipt && typeof defect_spec_receipt === "object") out.receipt = defect_spec_receipt;
  return out;
}

function _case_missing_fields(case_: any): string[] {
  const missing: string[] = [];
  const contract = case_.contract || {};
  if (!String(contract.intent || "").trim()) missing.push("intent");
  const steps = case_.steps;
  if (!Array.isArray(steps) || !steps.length || steps.some((item: any) => !item || typeof item !== "object" || !String(item.n || "").trim() || !String(item.text || "").trim())) {
    missing.splice(missing.includes("intent") ? 1 : 0, 0, "steps");
  }
  const expectations = case_.expectations_by_step;
  if (!Array.isArray(expectations) || !expectations.length) {
    if (!missing.includes("expectation")) missing.push("expectation");
  } else if (expectations.some((item: any) => !item || typeof item !== "object" || !String(item.n || "").trim() || !String(item.text || "").trim() || !_valid_origin(String(item.origin || "")))) {
    if (!missing.includes("expectation")) missing.push("expectation");
  }
  return _SCENARIO2_SOURCE_FIELDS.filter((field) => missing.includes(field));
}

function _decision_missing_fields(case_: any): string[] {
  const publicName: Record<string, string> = { intent: "description", steps: "steps", expectation: "expectation" };
  return _case_missing_fields(case_).map((field) => publicName[field]);
}

function _derived_source_status(case_: any): string {
  return _case_missing_fields(case_).length ? "incomplete" : "complete";
}

function _derived_typed_assertion_status(case_: any): string {
  const expectations = case_.expectations_by_step;
  if (!Array.isArray(expectations) || !expectations.length) return "invalid";
  let pending = false;
  for (let index = 1; index <= expectations.length; index++) {
    const item = expectations[index - 1];
    if (!item || typeof item !== "object" || !("assertion" in item)) return "invalid";
    if (item.assertion === null) {
      pending = true;
      continue;
    }
    try {
      _typed_expectation({ autoid: String(case_.autoid || ""), item, index });
    } catch {
      return "invalid";
    }
  }
  return pending ? "pending" : "ready";
}

function _declared_status_matches(case_: any, field: string, actual: string): boolean {
  const declared = case_[field];
  if (declared === null || declared === undefined) return true;
  const allowed = field === "source_status" ? _SOURCE_STATUSES : _TYPED_ASSERTION_STATUSES;
  return typeof declared === "string" && allowed.has(declared) && declared === actual;
}

export function case_status_mismatches(case_: any): [string, string][] {
  const sourceStatus = _derived_source_status(case_);
  const mismatches: [string, string][] = [];
  if (!_declared_status_matches(case_, "source_status", sourceStatus)) {
    mismatches.push(["source_status", sourceStatus]);
  }
  if (sourceStatus === "complete") {
    const typedStatus = _derived_typed_assertion_status(case_);
    if (!_TYPED_ASSERTION_STATUSES.has(typedStatus) || !_declared_status_matches(case_, "typed_assertion_status", typedStatus)) {
      mismatches.push(["typed_assertion_status", typedStatus]);
    }
  }
  return mismatches;
}

export function normalize_submission_case_statuses(case_: any): void {
  const sourceStatus = _derived_source_status(case_);
  case_.source_status = sourceStatus;
  const typedStatus = _derived_typed_assertion_status(case_);
  if (_TYPED_ASSERTION_STATUSES.has(typedStatus)) {
    case_.typed_assertion_status = typedStatus;
  } else if (sourceStatus === "incomplete" && !case_.expectations_by_step) {
    case_.typed_assertion_status = "pending";
  }
}

export function primary_expectation_projection_problems(case_: any): [string, string][] {
  const authored = (case_.expectations_by_step || []).filter((item: any) =>
    item && typeof item === "object" && String(item.text || "").trim() &&
    (String(item.origin || "") === "title" || String(item.origin || "").startsWith("step:") || String(item.origin || "").startsWith("expectation:")));
  if (!authored.length) return [];
  const contract = case_.contract || {};
  const origin = case_.origin || {};
  const problems: [string, string][] = [];
  if (!String(contract.expectation || "").trim()) problems.push(["contract.expectation", "primary_expectation_missing"]);
  if (!String(origin.expectation || "").trim()) problems.push(["origin.expectation", "primary_expectation_origin_missing"]);
  return problems;
}

export function expectation_source_binding(origin: string, expectationId: string, opts: { defect_spec_receipt?: any } = {}): any {
  const text = String(origin || "").trim();
  if (_ORIGIN_SPEC_RE.test(text)) {
    return { kind: "spec", locator: text.replace(/^spec:/, "") };
  }
  if (_ORIGIN_DEFECT_SPEC_RE.test(text)) {
    const out: any = { kind: "defect_spec", locator: text };
    if (opts.defect_spec_receipt && typeof opts.defect_spec_receipt === "object") out.receipt = opts.defect_spec_receipt;
    return out;
  }
  return { kind: "intent", locator: String(expectationId || "") };
}

function _typed_expectation(opts: { autoid: string; item: any; index: number; defect_spec_receipt?: any }): any {
  const { autoid, item, index, defect_spec_receipt } = opts;
  const raw = item.assertion;
  if (!raw || typeof raw !== "object") throw new Error("expectation assertion tuple is missing");
  const operator = String(raw.operator || "").trim();
  const value = String(raw.value || "");
  if (!operator || !value) throw new Error("expectation assertion operator/value is incomplete");
  const { contract_entry, load_excel_contract, validate_g_for_entry } = require("./excel_contract");
  const excelContract = load_excel_contract();
  const entry = contract_entry("check_point", operator, excelContract);
  if (entry === null || entry.status !== "enabled") {
    throw new Error("expectation assertion operator is not enabled");
  }
  validate_g_for_entry(entry, value, excelContract);
  const origin = String(item.origin || "").trim();
  const step = String(item.n || "").trim();
  const expectationId = _expectation_id(autoid, step, index);
  const sourceBinding = expectation_source_binding(origin, expectationId, { defect_spec_receipt });
  return { expectation_id: expectationId, semantic_key: _semantic_key(autoid, step), operator, value, origin, source: sourceBinding };
}

function _author_expectation_clauses(text: string): string[] {
  const source = String(text || "");
  if (!source.trim()) return [];
  const opening: Record<string, string> = { "(": ")", "（": "）", "[": "]", "【": "】", "{": "}" };
  const closing = new Set(Object.values(opening));
  const quotePairs: Record<string, string> = { "“": "”", "‘": "’", '"': '"', "'": "'" };
  const stack: string[] = [];
  let quote: string | null = null;
  let start = 0;
  const clauses: string[] = [];
  for (let index = 0; index < source.length; index++) {
    const char = source[index];
    if (quote !== null) {
      if (char === quote) quote = null;
      continue;
    }
    if (char in quotePairs) {
      quote = quotePairs[char];
      continue;
    }
    if (char in opening) {
      stack.push(opening[char]);
      continue;
    }
    if (closing.has(char)) {
      if (!stack.length || stack.pop() !== char) return [source.trim()];
      continue;
    }
    if ((char === "，" || char === "；") && !stack.length) {
      const clause = source.slice(start, index).trim();
      if (!clause) return [source.trim()];
      clauses.push(clause);
      start = index + 1;
    }
  }
  if (stack.length || quote !== null) return [source.trim()];
  const tail = source.slice(start).trim();
  if (!tail) return [source.trim()];
  clauses.push(tail);
  return clauses.length > 1 ? clauses : [source.trim()];
}

function _expectations(case_: any, opts: { mindmap_source_sha256: string; defect_spec_receipt?: any }): any[] {
  const { mindmap_source_sha256, defect_spec_receipt } = opts;
  const byStep = (case_.expectations_by_step || []).filter((e: any) => e && typeof e === "object" && String(e.text || "").trim());
  if (byStep.length) {
    const autoid = String(case_.autoid || "");
    const claimInputs: [any, number, number][] = [];
    byStep.forEach((sourceItem: any, sourceIndex0: number) => {
      const sourceIndex = sourceIndex0 + 1;
      const origin = String(sourceItem.origin || "").trim();
      const clauses = !(sourceItem.assertion && typeof sourceItem.assertion === "object") && !_ORIGIN_DEFECT_SPEC_RE.test(origin)
        ? _author_expectation_clauses(String(sourceItem.text || ""))
        : [String(sourceItem.text || "")];
      clauses.forEach((clause, clauseIndex0) => {
        claimInputs.push([{ ...sourceItem, text: clause }, sourceIndex, clauseIndex0 + 1]);
      });
    });
    const projected: any[] = [];
    claimInputs.forEach(([item, sourceIndex, clauseIndex], claimIndex0) => {
      const claimIndex = claimIndex0 + 1;
      const origin = String(item.origin || "").trim();
      const clauseCount = claimInputs.filter(([, itemSourceIndex]) => itemSourceIndex === sourceIndex).length;
      let anchor = origin_zh(origin);
      if (clauseCount > 1) anchor += `；原文分句${clauseIndex}/${clauseCount}`;
      const extra = item.assertion && typeof item.assertion === "object"
        ? { assertion: _typed_expectation({ autoid, item, index: claimIndex, defect_spec_receipt }) }
        : _ORIGIN_DEFECT_SPEC_RE.test(origin)
          ? { defect_spec_claim: _defect_spec_claim({ autoid, item, index: claimIndex, defect_spec_receipt }) }
          : { author_claim: _author_claim({ autoid, item, index: claimIndex, mindmap_source_sha256 }) };
      projected.push({ text: String(item.text), text_anchor: anchor, value_grounding: _VALUE_GROUNDING, ...extra });
    });
    return projected;
  }
  const origin = case_.origin || {};
  return [{
    text: String((case_.contract || {}).expectation || ""),
    text_anchor: origin_zh(origin.expectation),
    value_grounding: _VALUE_GROUNDING,
    assertion: _typed_expectation({ autoid: String(case_.autoid || ""), item: { n: "fallback", origin: origin.expectation, assertion: case_.assertion }, index: 1, defect_spec_receipt }),
  }];
}

function _card_bucket(case_: any): string {
  const bucket = case_.bucket;
  if (typeof bucket === "string" && _CARD_BUCKETS.has(bucket)) return bucket;
  if (bucket === "true_gap") return "step_recipe";
  throw new MachineMindmapError("machine mindmap case bucket cannot be carded");
}

function _engine_sampling_records(card: any): any[] {
  const { ENGINE_SLOTS_KEY, engine_sampling_records } = require("./step_structure");
  return engine_sampling_records({ [ENGINE_SLOTS_KEY]: card[ENGINE_SLOTS_KEY] || [] });
}

function _algorithm_family_token_map(): Record<string, string[]> {
  const { load_grammar } = require("./domain_grammar");
  const tokens: Record<string, Set<string>> = {};
  for (const [family, entry] of Object.entries<any>(load_grammar().algorithm_classes || {})) {
    for (const method of entry.methods || []) {
      const key = String(method).trim().toLowerCase();
      if (!tokens[key]) tokens[key] = new Set();
      tokens[key].add(String(family));
    }
  }
  const out: Record<string, string[]> = {};
  for (const [token, families] of Object.entries(tokens)) out[token] = [...families].sort();
  return out;
}

function _author_algorithm_mentions_disclosures(autoid: string, raw: any): any[] {
  const tokens = _algorithm_family_token_map();
  if (!Object.keys(tokens).length) return [];
  const mentions = (text: string): Set<string> => {
    const found = new Set<string>();
    const lowered = String(text || "").toLowerCase();
    for (const token of Object.keys(tokens)) {
      const esc = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (new RegExp(`(?<![a-z0-9])${esc}(?![a-z0-9])`).test(lowered)) found.add(token);
    }
    return found;
  };
  const labels = (mentionsSet: Set<string>): string[] =>
    [...mentionsSet].sort().map((token) => `${token}(${tokens[token].join(",")})`);
  const group = raw.mindmap_group;
  const groupText = group && typeof group === "object"
    ? (group.group_path || []).map((part: any) => String(part)).join("/")
    : String(group || "");
  const titleText = String(raw.intent_verbatim || "");
  const titleTokens = mentions(`${groupText} ${titleText}`);
  if (!titleTokens.size) return [];
  const differing: [string, string, Set<string>][] = [];
  for (const step of raw.author_steps || []) {
    if (!step || typeof step !== "object") continue;
    const stepText = String(step.text || "");
    const stepTokens = mentions(stepText);
    if (!stepTokens.size) continue;
    if ([...stepTokens].some((t) => !titleTokens.has(t))) {
      differing.push([String(step.n || "?"), stepText, stepTokens]);
    }
  }
  if (!differing.length) return [];
  const quoted = differing.map(([n, text, mentionsSet]) => `第 ${n} 步「${text}」出现 ${labels(mentionsSet).join(", ")}`).join("；");
  return [{
    autoid,
    code: "author_algorithm_mentions_disclosure",
    message: `用例 ${autoid} 的分组「${groupText}」、标题「${titleText}」中匹配到词表字符串 ${labels(titleTokens).join(", ")}；步骤中还出现其它词表字符串：${quoted}。括号只列词表分类。匹配可能来自域名、不同对象层次或迁移过程，是否构成算法声明、是否指向同一作用域及是否冲突均未核验。此项只记录原文与字符串命中，不改变来源一致性处置、采样与预期。`,
    reason_code: "author_algorithm_mentions_unverified",
    fallback_allowed: true,
    group_text: groupText,
    title_text: titleText,
    title_tokens: labels(titleTokens),
    differing_steps: differing.map(([n, text, mentionsSet]) => ({ n, text, tokens: labels(mentionsSet) })),
  }];
}

function _step_structure_disclosures(autoid: string, raw: any, opts: { object_kinds_available: boolean; tiers?: any[] }): any[] {
  const { STEP_STRUCTURE_ABSENT_CN, STEP_STRUCTURE_KIND_SKIPPED_CN, device_disclosure_cn } = require("../ist_core/display_lexicon");
  const out: any[] = [];
  if ((raw.author_steps || []).length && !(raw.step_structure || []).length) {
    out.push({ autoid, code: "step_structure_absent", message: STEP_STRUCTURE_ABSENT_CN, reason_code: "step_structure_absent" });
  } else if (!opts.object_kinds_available) {
    out.push({ autoid, code: "step_structure_kind_check_skipped", message: STEP_STRUCTURE_KIND_SKIPPED_CN, reason_code: "projection_unavailable" });
  }
  const rows = (opts.tiers || []).filter((row: any) => row && typeof row === "object");
  if (!rows.some((row: any) => String(row.tier || "") === "T1")) return out;
  for (const row of rows) {
    out.push({
      autoid, code: "device_disclosure", message: device_disclosure_cn(row),
      tier: String(row.tier || ""), reason_code: String(row.code || ""),
      fact_id: String(row.fact_id || ""), characteristic_class: String(row.characteristic_class || ""),
      locator: String(row.locator || ""), pinned: String(row.pinned || ""),
      detail: { ...(row.detail || {}) },
    });
  }
  return out;
}

function _card_step_structure(case_: any, expectations: any[]): [any[], any[], any[]] {
  const { ENGINE_SLOTS_KEY, STEP_STRUCTURE_KEY, apply_engine_slots, distribution_criterion_bindings, strip_engine_slots } = require("./step_structure");
  const structure = case_[STEP_STRUCTURE_KEY];
  if (!Array.isArray(structure)) return [[], [], []];
  const staged = {
    autoid: String(case_.autoid || ""),
    [STEP_STRUCTURE_KEY]: JSON.parse(JSON.stringify(structure)),
    concretizations: JSON.parse(JSON.stringify(case_.concretizations || [])),
    steps: [...(case_.steps || [])],
  };
  strip_engine_slots(staged);
  const bindings = distribution_criterion_bindings(expectations);
  apply_engine_slots(staged, bindings);
  const entries = staged[STEP_STRUCTURE_KEY].filter((item: any) => item && typeof item === "object");
  const records = (staged[ENGINE_SLOTS_KEY] || []).filter((item: any) => item && typeof item === "object");
  return [entries, records, _card_device_disclosure(case_, entries, records, { has_distribution_criterion: Boolean(bindings && bindings.length) })];
}

function _card_device_disclosure(case_: any, entries: any[], records: any[], opts: { has_distribution_criterion: boolean }): any[] {
  const { resolve_behaviour_classes } = require("./behaviour_classes");
  const { flatten_tiers, observation_pairing_unavailable_disclosure, select_disclosure } = require("./device_characteristics");
  const steps = records.flatMap((record: any) => (record.applies_to_steps || []).filter((number: any) => String(number).trim()).map(String));
  const tiers = select_disclosure(entries, resolve_behaviour_classes(entries), { case: case_, distribution_steps: steps, has_distribution_criterion: opts.has_distribution_criterion });
  if (records.some((record: any) => String(record.reason_code || "") === "pairing_ambiguous")) {
    tiers.T4.push(observation_pairing_unavailable_disclosure());
  }
  return flatten_tiers(tiers);
}

export function ground_condition_author_text(authorText: string, stepText: string): any | null {
  for (const form of verbatim_candidates(String(authorText || ""))) {
    for (const stepForm of verbatim_candidates(String(stepText || ""))) {
      const span = ground_source_span(form, stepForm);
      if (span !== null) return span;
    }
  }
  return null;
}

function _condition_grounding(case_: any): any[] {
  const { STEP_STRUCTURE_KEY } = require("./step_structure");
  const out: any[] = [];
  const structure = case_[STEP_STRUCTURE_KEY];
  if (!Array.isArray(structure)) return out;
  const byNumber: Record<string, string> = {};
  for (const item of case_.steps || []) {
    if (item && typeof item === "object") byNumber[String(item.n || "").trim()] = String(item.text || "");
  }
  structure.forEach((entry: any, entryPosition: number) => {
    if (!entry || typeof entry !== "object") return;
    const number = String(entry.n || "").trim();
    const stepText = byNumber[number];
    if (stepText === undefined) return;
    (entry.stated_conditions || []).forEach((condition: any, conditionPosition: number) => {
      if (!condition || typeof condition !== "object") return;
      const authorText = String(condition.author_text || "");
      if (!authorText.trim()) return;
      const span = ground_condition_author_text(authorText, stepText);
      if (span === null || span.match === "verbatim") return;
      out.push({
        n: number, entry: entryPosition, condition: conditionPosition,
        match: String(span.match || ""), start: Number(span.start || 0), end: Number(span.end || 0),
      });
    });
  });
  return out;
}

function _project_case(case_: any, opts: {
  mindmap_source_sha256: string; defect_spec_receipt?: any; mindmap_text?: string;
  resource?: any; criterion_version_family?: string; criterion_manual_version?: string; criterion_rule_records?: any;
}): any {
  const contract = case_.contract || {};
  const origin = case_.origin || {};
  const scope: string[] = (case_.adaptation_notes || []).map(String).filter((x: string) => x.trim());
  const dependsOn = String(case_.depends_on || "").trim();
  if (dependsOn) scope.push(`依赖前序案尾号${dependsOn.slice(-6)}的最终状态，编写期并入或适配`);
  let method = String(contract.verification_method || "").trim();
  let methodOrigin = String(origin.verification_method || "").trim();
  if (!method || !_valid_origin(methodOrigin)) {
    const firstStep = (case_.steps || [{}])[0];
    method = String(firstStep.text || "");
    methodOrigin = `step:${String(firstStep.n || "").trim()}`;
  }
  const consistencyCard = "consistency" in case_ ? { consistency: case_.consistency } : {};
  let projectedExpectations = _expectations(case_, { mindmap_source_sha256: opts.mindmap_source_sha256, defect_spec_receipt: opts.defect_spec_receipt });
  if (opts.mindmap_text !== undefined && opts.mindmap_text !== null) {
    const { normalize_case_expectations } = require("./criterion_normalization");
    const normalized = normalize_case_expectations({
      case: case_, expectations: projectedExpectations, mindmap_text: opts.mindmap_text,
      resource: opts.resource, version_family: opts.criterion_version_family || "",
      author_rules: opts.criterion_rule_records, manual_version: opts.criterion_manual_version || null,
    });
    projectedExpectations = [...normalized.expectations];
  }
  const [stepStructure, engineSlots, deviceDisclosure] = _card_step_structure(case_, projectedExpectations);
  const { ADAPTED_STEPS_KEY } = require("./step_structure");
  return {
    ...consistencyCard,
    contract_class: "mindmap_verbatim",
    autoid: String(case_.autoid || ""),
    bucket: _card_bucket(case_),
    source_status: _derived_source_status(case_),
    typed_assertion_status: _derived_typed_assertion_status(case_),
    mindmap_group: { group_path: (case_.group_path || []).map(String).length ? (case_.group_path || []).map(String) : ["（未分组）"] },
    intent_verbatim: String(contract.intent || case_.title || ""),
    intent_anchor: origin_zh(origin.intent),
    verification_method: { selected_rule: method, authority: origin_zh(methodOrigin) },
    author_steps: (case_.steps || [])
      .filter((item: any) => item && typeof item === "object" && String(item.n || "").trim() && String(item.text || "").trim())
      .map((item: any) => ({ n: String(item.n || ""), text: String(item.text || ""), origin: `step:${String(item.n || "")}` })),
    adapted_steps: (case_[ADAPTED_STEPS_KEY] || [])
      .filter((item: any) => item && typeof item === "object" && String(item.n || "").trim() && String(item.text || "").trim())
      .map((item: any) => ({ n: String(item.n || ""), text: String(item.text || ""), basis: String(item.basis || "") })),
    rebind_licenses: (case_.rebind_licenses || [])
      .filter((item: any) => item && typeof item === "object" && String(item.author_literal || "").trim() && String(item.verdict || "").trim())
      .map((item: any) => ({
        author_literal: String(item.author_literal || ""), verdict: String(item.verdict || ""),
        occurrences: (item.occurrences || []).map((occ: any) => String(occ).trim()).filter(Boolean),
        constraints: String(item.constraints || ""), reason: String(item.reason || ""),
      })),
    step_structure: stepStructure,
    condition_grounding: _condition_grounding(case_),
    engine_slots: engineSlots,
    device_disclosure: deviceDisclosure,
    expectations: projectedExpectations,
    scope_adaptations: scope,
  };
}

function _project_manifest_fallback_case(manifestCase: any, opts: { mindmap_source_sha256: string }): any {
  const autoid = String(manifestCase.autoid || "").trim();
  const title = String(manifestCase.title || "").trim();
  if (!new RegExp(`^${_LOCATOR_TOKEN}$`).test(autoid) || !title) {
    throw new Error("manifest fallback identity or title is invalid");
  }
  if (!_SHA256_RE.test(String(opts.mindmap_source_sha256 || ""))) {
    throw new Error("manifest fallback has no sealed mindmap source SHA256");
  }
  const rawSteps = manifestCase.step_intents;
  if (!Array.isArray(rawSteps) || !rawSteps.length) {
    throw new Error("manifest fallback has no author step_intents");
  }
  const authoredSteps: [number, string, string][] = [];
  rawSteps.forEach((item: any, index0: number) => {
    const index = index0 + 1;
    if (!item || typeof item !== "object") throw new Error("manifest fallback step_intents contains a non-object");
    const desc = String(item.desc || "").trim();
    const expected = String(item.expected || "").trim();
    if (!desc) throw new Error("manifest fallback has an empty author step description");
    authoredSteps.push([index, desc, expected]);
  });
  const claimInputs: any[] = authoredSteps
    .filter(([, , expected]) => expected)
    .map(([stepIndex, , expected]) => ({
      n: String(stepIndex), text: expected,
      origin: `manifest:step_intents[${stepIndex - 1}].expected`,
      text_anchor: `作者用例：第${stepIndex}步预期`,
    }));
  const rawUnbound = manifestCase.unbound_expectations || [];
  if (!Array.isArray(rawUnbound) || rawUnbound.some((value: any) => typeof value !== "string")) {
    throw new Error("manifest fallback unbound_expectations is invalid");
  }
  rawUnbound.forEach((value: string, index0: number) => {
    const index = index0 + 1;
    if (value.trim()) {
      claimInputs.push({
        n: `unbound-${index}`, text: value.trim(),
        origin: `manifest:unbound_expectations[${index0}]`,
        text_anchor: `作者用例：未绑定预期${index}`,
      });
    }
  });
  if (!claimInputs.length) throw new Error("manifest fallback has no Author expected declaration");
  const expectations: any[] = claimInputs.map((item, claimIndex0) => ({
    text: item.text, text_anchor: item.text_anchor, value_grounding: _VALUE_GROUNDING,
    author_claim: _author_claim({ autoid, item, index: claimIndex0 + 1, mindmap_source_sha256: opts.mindmap_source_sha256 }),
  }));
  const [firstStepIndex, firstDesc] = authoredSteps[0];
  return {
    contract_class: "mindmap_verbatim", autoid, bucket: "step_recipe",
    source_status: "complete", typed_assertion_status: "pending",
    mindmap_group: { group_path: (manifestCase.group_path || []).map(String).filter((v: string) => v.trim()).length ? (manifestCase.group_path || []).map(String).filter((v: string) => v.trim()) : ["（未分组）"] },
    intent_verbatim: title, intent_anchor: "作者用例：标题",
    verification_method: { selected_rule: firstDesc, authority: `作者用例：第${firstStepIndex}步描述` },
    author_steps: authoredSteps.map(([stepIndex, desc]) => ({ n: String(stepIndex), text: desc, origin: `manifest:step_intents[${stepIndex - 1}].desc` })),
    expectations,
    scope_adaptations: [],
  };
}

function _enhancement_disclosures_for_case(case_: any): any[] {
  const autoid = String(case_.autoid || "");
  const out: any[] = [];
  const { ADAPTED_STEPS_KEY, step_is_adapted } = require("./step_structure");
  const authoredSteps: Record<string, string> = {};
  for (const item of case_.steps || []) {
    if (item && typeof item === "object") authoredSteps[String(item.n || "").trim()] = String(item.text || "");
  }
  for (const item of case_[ADAPTED_STEPS_KEY] || []) {
    if (!item || typeof item !== "object") continue;
    const number = String(item.n || "").trim();
    const adaptedText = String(item.text || "").trim();
    const authoredText = authoredSteps[number] || "";
    if (!number || !adaptedText || !step_is_adapted(authoredText, adaptedText)) continue;
    out.push({
      autoid, code: "adapted_step_disclosure",
      message: `步骤适配（第${number}步）：作者原文「${authoredText.slice(0, 200)}」→适配为「${adaptedText.slice(0, 200)}」` + (String(item.basis || "").trim() ? `，依据：${String(item.basis || "").trim().slice(0, 200)}` : ""),
      reason_code: "recompose_adapted_step",
    });
  }
  for (const text of case_.proposal || []) {
    if (typeof text === "string" && text.trim()) {
      out.push({ autoid, code: "mindmap_proposal_disclosure", message: `重组 proposal：${text.trim().slice(0, 200)}`, reason_code: "recompose_proposal" });
    }
  }
  for (const item of case_.concretizations || []) {
    if (!item || typeof item !== "object") continue;
    const slot = String(item.slot || "");
    const authorText = String(item.author_text || "");
    const value = String(item.value || "");
    out.push({
      autoid, code: "process_value_concretization",
      message: `过程值具体化（${slot}）：「${authorText || "（留白）"}」→「${value}」（预期文本未改）`,
      reason_code: "recompose_concretization",
    });
  }
  for (const lic of case_.rebind_licenses || []) {
    if (!lic || typeof lic !== "object") continue;
    const authorLiteral = String(lic.author_literal || "");
    const verdict = String(lic.verdict || "");
    const constraints = String(lic.constraints || "");
    const reason = String(lic.reason || "");
    out.push({
      autoid, code: "rebind_license_mapping",
      message: `重绑许可披露（${verdict}）：作者原文「${authorLiteral}」` + (verdict === "rebindable" ? "已按改写制在适配步骤中转为可执行的自动化取值" : "判定承重，适配与编译均保持该字面") + `；承重判断依据：${reason.slice(0, 200)}` + (constraints ? `；约束：${constraints.slice(0, 200)}` : ""),
      reason_code: "recompose_rebind_license",
    });
  }
  return out;
}

export const PROPOSAL_SHAPE_ERROR_CN = "proposal 必须是非空字符串组成的数组（无缺口时为空数组）";

export function proposal_shape_error(case_: any): string | null {
  const proposal = case_.proposal;
  if (!Array.isArray(proposal) || proposal.some((item: any) => typeof item !== "string" || !item.trim())) {
    return PROPOSAL_SHAPE_ERROR_CN;
  }
  return null;
}

export function primary_expectation_membership_error(case_: any): string | null {
  const material = { ...case_ };
  if (_derived_source_status(material) !== "complete" || !_TYPED_ASSERTION_STATUSES.has(_derived_typed_assertion_status(material))) {
    return null;
  }
  const contract = material.contract || {};
  const origin = material.origin || {};
  const primary = _norm_ws(String(contract.expectation || ""));
  const primaryOrigin = String(origin.expectation || "").trim();
  const found = (material.expectations_by_step || []).some((item: any) => {
    if (String(item.origin || "").trim() !== primaryOrigin) return false;
    const candidates = [_norm_ws(String(item.text || "")), _locator_semantic_text(String(item.text || ""), String(item.origin || ""))];
    return candidates.includes(primary);
  });
  if (!found) return "主期望未进入分步期望闭集";
  return null;
}

function _eligible(case_: any, opts: { mindmap_text?: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any } = {}): [boolean, string] {
  const proposalError = proposal_shape_error(case_);
  if (proposalError) return [false, proposalError];
  const { validate_case_enhancement_fields } = require("../ist_core/compile_engine/rebind_binder");
  const enhancementErrors = validate_case_enhancement_fields(case_);
  if (enhancementErrors.length) return [false, enhancementErrors[0]];
  if ("consistency" in case_) {
    const consistency = case_.consistency;
    if (consistency && typeof consistency === "object") {
      const stampFailure = stamp_consistency_quotes(consistency, String(case_.autoid || ""), {
        mindmap_text: opts.mindmap_text || "", governing_spec: opts.governing_spec, spec_text: opts.spec_text,
        defect_spec_receipt: opts.defect_spec_receipt, cross_check: false,
      });
      if (stampFailure) {
        if (stampFailure.includes("locator_unresolved")) return [false, `recompose 一致性结论的出处解不出（${stampFailure}）`];
        if (stampFailure.includes("drift")) return [false, `recompose 一致性结论的引文与引擎盖章不一致（${stampFailure}）`];
        return [false, `recompose 一致性结论不在闭集（${stampFailure}）`];
      }
    }
    const consistencyFailure = recompose_consistency_failure(consistency);
    if (consistencyFailure) return [false, `recompose 一致性结论不在闭集（${consistencyFailure}）`];
  }
  const contract = case_.contract || {};
  const origin = case_.origin || {};
  for (const field of ["intent", "expectation"]) {
    if (!String(contract[field] || "").trim()) return [false, "用例描述或预期不完整"];
    if (!_valid_origin(String(origin[field] || ""))) return [false, "契约字段缺少可核验出处"];
  }
  const rawStepExpectations = case_.expectations_by_step;
  if (!Array.isArray(rawStepExpectations) || !rawStepExpectations.length || rawStepExpectations.some((item: any) =>
    !item || typeof item !== "object" || !String(item.n || "").trim() || !String(item.text || "").trim()
    || !_valid_origin(String(item.origin || "")) || !("assertion" in item))) {
    return [false, "分步期望缺少步骤绑定、原文、出处或 assertion 状态"];
  }
  const sourceStatus = _derived_source_status(case_);
  const typedStatus = _derived_typed_assertion_status(case_);
  const mismatches = case_status_mismatches(case_);
  if (mismatches.length) return [false, `${mismatches[0][0]} 与机械复算结果不一致`];
  if (sourceStatus !== "complete") return [false, "脑图源描述、步骤或自然语言预期不完整"];
  if (!_TYPED_ASSERTION_STATUSES.has(typedStatus)) return [false, "分步期望的 typed assertion 既非 ready 也非 pending"];
  const membershipError = primary_expectation_membership_error(case_);
  if (membershipError) return [false, membershipError];
  return [true, ""];
}

function _scenario2_incomplete_reason(case_: any, opts: { governing_spec_status?: string | null; defect_spec_status?: string | null; defect_spec_receipt_sha256?: string | null; mindmap_text?: string | null } = {}): string {
  const rawProposal = case_.proposal;
  if (!Array.isArray(rawProposal) || rawProposal.some((item: any) => typeof item !== "string" || !item.trim())) return "";
  const proposal = rawProposal.map((item: string) => item.trim());
  if (!proposal.length) return "";
  const proof = case_.scenario2;
  if (!proof || typeof proof !== "object") return "";
  if (JSON.stringify(Object.keys(proof).sort()) !== JSON.stringify(["defect_spec_receipt_sha256", "defect_spec_status", "missing_fields", "reason_code", "spec_status"].sort())) return "";
  const reasonCode = String(proof.reason_code || "").trim();
  const proofMissing = proof.missing_fields;
  if (reasonCode !== _SCENARIO2_REASON || !Array.isArray(proofMissing) || !proofMissing.length
      || proofMissing.some((field: any) => !_SCENARIO2_SOURCE_FIELDS.includes(field))
      || new Set(proofMissing).size !== proofMissing.length) return "";
  const expectedMissing = [...proofMissing];
  const specStatusMap: Record<string, string> = { bound: "checked_no_static_declaration", no_governing_spec: "no_governing_spec", ambiguous: "ambiguous" };
  const expectedSpecStatus = specStatusMap[String(opts.governing_spec_status || "")];
  if (expectedSpecStatus === undefined) return "";
  if (String(proof.spec_status || "") !== expectedSpecStatus) return "";
  const defectStatusMap: Record<string, string> = {
    not_queried: "not_queried", no_ticket_reference: "no_ticket_reference", missing: "checked_no_defect_spec",
    candidate_only: "checked_no_claimable_declaration", resolved: "checked_no_applicable_declaration",
    ambiguous: "ambiguous", resolved_absent: "resolved_absent",
  };
  const expectedDefectStatus = defectStatusMap[String(opts.defect_spec_status || "")];
  if (expectedDefectStatus === undefined) return "";
  if (String(proof.defect_spec_status || "") !== expectedDefectStatus) return "";
  const expectedReceiptSha = String(opts.defect_spec_receipt_sha256 || "");
  const suppliedReceiptSha = String(proof.defect_spec_receipt_sha256 || "");
  if (["not_queried", "no_ticket_reference", "ambiguous", "resolved_absent"].includes(expectedDefectStatus)) {
    if (suppliedReceiptSha) return "";
  } else if (!_SHA256_RE.test(expectedReceiptSha) || suppliedReceiptSha !== expectedReceiptSha) {
    return "";
  }
  const actualMissing = _case_missing_fields(case_);
  if (JSON.stringify(actualMissing) !== JSON.stringify(expectedMissing)) return "";
  if (opts.mindmap_text !== null && opts.mindmap_text !== undefined) {
    const sourceMissing = _source_missing_fields(case_, opts.mindmap_text);
    if (JSON.stringify(sourceMissing) !== JSON.stringify(actualMissing)) return "";
  }
  return "人工脑图和规格书都没写全描述、步骤和预期";
}

function _source_missing_fields(case_: any, mindmapText: string): string[] {
  const autoid = String(case_.autoid || "");
  const anchors = _mindmap_anchor_map(mindmapText)[autoid] || {};
  if (!Object.keys(anchors).length) return [..._SCENARIO2_SOURCE_FIELDS];
  const present: Record<string, boolean> = {
    intent: Boolean(anchors.title),
    steps: Boolean(anchors.__step_text__),
    expectation: Object.keys(anchors).some((key) => key.startsWith("expectation:")),
  };
  return _SCENARIO2_SOURCE_FIELDS.filter((f) => !present[f]);
}

function _valid_origin(value: string): boolean {
  const text = String(value || "").trim();
  return Boolean(text === "title" || _ORIGIN_STEP_RE.test(text) || _ORIGIN_EXPECT_RE.test(text) || _ORIGIN_SPEC_RE.test(text) || _ORIGIN_DEFECT_SPEC_RE.test(text));
}

export function _norm_ws(s: string): string {
  return String(s || "").replace(/\s+/g, " ").trim();
}

function _locator_semantic_text(text: string, origin: string, opts: { strip_trailing_binding?: boolean } = {}): string {
  const stripTrailingBinding = opts.strip_trailing_binding !== false;
  const normalized = _norm_ws(text);
  const originText = String(origin || "").trim();
  const match = _ORIGIN_EXPECT_RE.exec(originText) || _ORIGIN_STEP_RE.exec(originText);
  if (match === null) return normalized;
  const label = match[1].replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const prefix = new RegExp(`^\\s*(?:\\[${label}\\]|${label}[.、:：)）])\\s*`);
  let semantic = normalized.replace(prefix, "");
  if (stripTrailingBinding && _ORIGIN_STEP_RE.test(originText)) {
    semantic = semantic.replace(new RegExp(`\\s*\\[(${_LOCATOR_TOKEN})\\]\\s*$`), "");
  }
  return _norm_ws(semantic);
}

export function _source_atom_forms(rawValue: string, origin: string): string[] {
  const out: string[] = [];
  const add = (text: string) => {
    for (const form of [_norm_ws(text), _locator_semantic_text(text, origin, { strip_trailing_binding: false }), _locator_semantic_text(text, origin)]) {
      if (form && !out.includes(form)) out.push(form);
    }
  };
  for (const value of _verbatim_candidates(rawValue)) add(value);
  if (String(rawValue).includes("\n")) {
    for (const line of String(rawValue).split(/\r?\n/)) add(line);
  }
  return out;
}

const _WS_RUN_RE = /\s+/;

function _whitespace_tolerant_pattern(quote: string): RegExp | null {
  const parts = quote.split(_WS_RUN_RE).filter(Boolean).map((seg) => seg.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!parts.length) return null;
  try {
    return new RegExp(parts.join("\\s+"));
  } catch {
    return null;
  }
}

export function ground_source_span(sourceText: string, mindmapText: string, opts: { origin?: string } = {}): any | null {
  const quote = String(sourceText || "");
  const text = String(mindmapText || "");
  const origin = opts.origin || "";
  if (!quote.trim() || !text) return null;
  const locate = (needle: string, prefix: number, suffix: number, how: string): any | null => {
    const index = text.indexOf(needle);
    if (index >= 0) {
      return { start: index, end: index + needle.length, trimmed_prefix_len: prefix, trimmed_suffix_len: suffix, basis: "mindmap_text_chars", match: how };
    }
    const pattern = _whitespace_tolerant_pattern(needle);
    const found = pattern !== null ? pattern.exec(text) : null;
    if (found === null) return null;
    return { start: found.index, end: found.index + found[0].length, trimmed_prefix_len: prefix, trimmed_suffix_len: suffix, basis: "mindmap_text_chars", match: `${how}:whitespace_tolerant` };
  };
  const span = locate(quote, 0, 0, "verbatim");
  if (span !== null) return span;
  const semantic = _locator_semantic_text(quote, origin);
  if (semantic && semantic !== quote) {
    const at = quote.indexOf(semantic);
    const head = at >= 0 ? quote.slice(0, at) : "";
    const tail = at >= 0 ? quote.slice(at + semantic.length) : "";
    return locate(semantic, head.length, tail.length, "locator_stripped");
  }
  return null;
}

export function source_span_shadow(data: any, mindmapText: string): any[] {
  if (!data || typeof data !== "object") return [];
  const text = String(mindmapText || "");
  if (!text) return [];
  const out: any[] = [];
  for (const case_ of data.cases || []) {
    if (!case_ || typeof case_ !== "object") continue;
    const autoid = String(case_.autoid || "");
    const origins = case_.origin && typeof case_.origin === "object" ? case_.origin : {};
    for (const [field, raw] of [
      ["intent", case_.contract && typeof case_.contract === "object" ? case_.contract.intent : undefined],
      ["expectation", case_.contract && typeof case_.contract === "object" ? case_.contract.expectation : undefined],
    ] as [string, any][]) {
      if (typeof raw !== "string" || !raw.trim()) continue;
      const origin = String(origins[field] || "");
      const forms = _source_atom_forms(raw, origin);
      const formOk = forms.some((form) => form && _norm_ws(text).includes(form));
      const span = ground_source_span(raw, text, { origin });
      if (formOk && span === null) {
        out.push({ autoid, field, origin, divergence: "form_set_ok_span_missing" });
      } else if (span !== null && !formOk) {
        out.push({ autoid, field, origin, divergence: "span_found_form_set_rejected", source_span: [span.start, span.end], match: span.match });
      }
    }
  }
  return out;
}

function _assertion_source_forms(rawValue: string, origin: string): string[] {
  const out: string[] = [];
  for (const value of _verbatim_candidates(rawValue)) {
    const semantic = _locator_semantic_text(value, origin);
    if (semantic && !out.includes(semantic)) out.push(semantic);
  }
  return out;
}

function _spec_sentence_forms(rawValue: string): string[] {
  const out: string[] = [];
  for (const value of _verbatim_candidates(rawValue)) {
    const stripped = _norm_ws(value.replace(/^(?:(?:[-*+]\s+)|(?:#{1,6}\s+)|(?:>\s+)|(?:\d+[.、)）]\s+))+/, ""));
    for (const form of [value, stripped]) {
      if (form && !out.includes(form)) out.push(form);
    }
  }
  return out;
}

function _verbatim_candidates(rawValue: string): string[] {
  const out = [_norm_ws(rawValue)];
  const escaped = JSON.stringify(String(rawValue)).slice(1, -1);
  if (escaped !== rawValue) out.push(_norm_ws(escaped));
  return out.filter(Boolean);
}

export function verbatim_candidates(rawValue: string): string[] {
  return _verbatim_candidates(rawValue);
}

function _spec_origin_resolved_span(origin: string, opts: { governing_spec?: string | null; spec_text?: string | null }): [string[], number, number] | null {
  const match = _ORIGIN_SPEC_RE.exec(String(origin || ""));
  if (match === null || opts.spec_text === null || opts.spec_text === undefined || match[1] !== opts.governing_spec) return null;
  const span = match[2].split("-", 2);
  const start = parseInt(span[0], 10);
  const end = parseInt(span[span.length - 1], 10);
  const lines = opts.spec_text.split(/\r?\n/);
  if (start < 1 || end < start || end > lines.length) return null;
  return [lines, start, end];
}

function _spec_anchor_span_text(origin: string, opts: { governing_spec?: string | null; spec_text?: string | null }): string | null {
  const resolved = _spec_origin_resolved_span(origin, opts);
  if (resolved === null) return null;
  const [lines, start, end] = resolved;
  return lines.slice(start - 1, end).join("\n");
}

function _spec_anchor_text(origin: string, opts: { governing_spec?: string | null; spec_text?: string | null }): string | null {
  const raw = _spec_anchor_span_text(origin, opts);
  return raw === null ? null : _norm_ws(raw);
}

function _defect_spec_anchor_raw_text(origin: string, opts: { defect_spec_receipt?: any }): string | null {
  const match = _ORIGIN_DEFECT_SPEC_RE.exec(String(origin || ""));
  const receipt = opts.defect_spec_receipt;
  if (match === null || !receipt || typeof receipt !== "object") return null;
  const ticket = receipt.ticket;
  const projection = receipt.projection;
  if (!accepts_schema(receipt.schema, "ist.defect-spec-receipt") || receipt.status !== "resolved" || receipt.eligible !== true
      || receipt.authority_group !== "spec" || !ticket || typeof ticket !== "object" || !projection || typeof projection !== "object"
      || String(ticket.backend || "").toLowerCase() !== match[1].toLowerCase()
      || String(ticket.ticket_id || "").toUpperCase() !== match[2].toUpperCase()) {
    return null;
  }
  return String(projection[match[3].toLowerCase()] || "");
}

function _defect_spec_anchor_text(origin: string, opts: { defect_spec_receipt?: any }): string | null {
  const raw = _defect_spec_anchor_raw_text(origin, opts);
  return raw === null ? null : _norm_ws(raw) || null;
}

function _external_origin_forms(origin: string, opts: { governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any }): string[] | null {
  if (String(origin || "").startsWith("spec:")) {
    const side = _spec_anchor_text(origin, opts);
    return side !== null ? _spec_sentence_forms(side) : [];
  }
  if (String(origin || "").startsWith("defect:")) {
    const side = _defect_spec_anchor_text(origin, opts);
    return side !== null ? _verbatim_candidates(side) : [];
  }
  return null;
}

function _external_origin_raw_text(origin: string, opts: { governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any }): string {
  if (String(origin || "").startsWith("spec:")) {
    return _spec_anchor_span_text(origin, opts) || "";
  }
  if (String(origin || "").startsWith("defect:")) {
    return _defect_spec_anchor_raw_text(origin, opts) || "";
  }
  return "";
}

function _node_text(node: any): string {
  const data = node.data && typeof node.data === "object" ? node.data : {};
  return String(data.text || node.text || "");
}

function _node_autoid(node: any): string {
  const data = node.data && typeof node.data === "object" ? node.data : {};
  return String(data.autoid || node.autoid || "").trim();
}

function _node_children(node: any): any[] {
  return (node.children || []).filter((child: any) => child && typeof child === "object");
}

function _numbered_atoms(text: string): Record<string, string> {
  const pattern = new RegExp(`^\\s*\\[?(${_LOCATOR_TOKEN})\\]?[.、:：)）]\\s*`, "gm");
  const src = String(text || "");
  const matches = [...src.matchAll(pattern)];
  const out: Record<string, string> = {};
  matches.forEach((match, index) => {
    const end = index + 1 < matches.length ? matches[index + 1].index! : src.length;
    const atom = src.slice(match.index!, end).trim();
    if (atom) out[match[1]] = atom;
  });
  return out;
}

function _action_atoms(text: string): Record<string, string> {
  const source = String(text || "");
  const numbered = _numbered_atoms(source);
  if (Object.keys(numbered).length) {
    const first = new RegExp(`^\\s*\\[?(${_LOCATOR_TOKEN})\\]?[.、:：)）]\\s*`, "m").exec(source);
    const prefix = first !== null ? source.slice(0, first.index).trim() : "";
    if (prefix) {
      const prefixLabel = !("1" in numbered) ? "1" : "pre1";
      return { [prefixLabel]: prefix, ...numbered };
    }
    return numbered;
  }
  const lines = source.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length > 1) {
    const out: Record<string, string> = {};
    lines.forEach((line, index) => { out[String(index + 1)] = line; });
    return out;
  }
  return source.trim() ? { "1": source.trim() } : {};
}

function _bracket_labeled_atoms(text: string): Record<string, string> {
  const source = String(text || "");
  const pattern = new RegExp(`^\\s*\\[(${_LOCATOR_TOKEN})\\]\\s*`, "gm");
  const matches = [...source.matchAll(pattern)];
  const out: Record<string, string> = {};
  matches.forEach((match, index) => {
    const end = index + 1 < matches.length ? matches[index + 1].index! : source.length;
    const atom = source.slice(match.index!, end).trim();
    if (atom) out[match[1]] = atom;
  });
  return out;
}

function _expectation_step_anchor(label: string): string {
  return `__expectation_step__:${label}`;
}

const _anchorCache = new Map<string, Record<string, Record<string, string[]>>>();

function _cached_mindmap_anchor_map(mindmapText: string): Record<string, Record<string, string[]>> {
  if (_anchorCache.has(mindmapText)) return _anchorCache.get(mindmapText)!;
  const result = _mindmap_anchor_map(mindmapText);
  if (_anchorCache.size >= 2) {
    const firstKey = _anchorCache.keys().next().value;
    if (firstKey !== undefined) _anchorCache.delete(firstKey);
  }
  _anchorCache.set(mindmapText, result);
  return result;
}

function _semantic_whitespace(text: any): string {
  return String(text || "").split(/\s+/).filter(Boolean).join(" ");
}

export const AUTHORED_STEP_ANCHOR_CN = "作者步骤";
const _AUTHORED_STEP_ANCHOR_TAIL_RE = new RegExp(`；${AUTHORED_STEP_ANCHOR_CN}[0-9]+$`);

export function authored_step_anchor_suffix(authoredStep: any): string {
  if (typeof authoredStep === "boolean" || !Number.isInteger(authoredStep)) return "";
  return authoredStep >= 1 ? `；${AUTHORED_STEP_ANCHOR_CN}${authoredStep}` : "";
}

export function with_authored_step_anchor(textAnchor: any, authoredStep: any): string {
  const base = String(textAnchor || "").replace(_AUTHORED_STEP_ANCHOR_TAIL_RE, "");
  return base + authored_step_anchor_suffix(authoredStep);
}

export const AUTHORED_STEP_CAUSE_ORIGIN = "origin_not_a_step_locator";
export const AUTHORED_STEP_CAUSE_ANCHORS = "anchor_rows_unbalanced";
export const AUTHORED_STEP_CAUSE_TEXT = "claim_text_not_uniquely_bound";
export const AUTHORED_STEP_UNKNOWN_CAUSES = new Set([AUTHORED_STEP_CAUSE_ORIGIN, AUTHORED_STEP_CAUSE_ANCHORS, AUTHORED_STEP_CAUSE_TEXT]);

export function authored_expectation_step_binding(mindmapText: string, opts: { autoid: string; origin: string; source_text: string }): [number | null, string | null] {
  const text = String(opts.origin || "").trim();
  const stepMatch = _ORIGIN_STEP_RE.exec(text);
  if (stepMatch !== null) {
    const digits = stepMatch[1];
    if (/^\d+$/.test(digits) && parseInt(digits, 10) >= 1) {
      return [parseInt(digits, 10), null];
    }
    return [null, AUTHORED_STEP_CAUSE_ORIGIN];
  }
  const labelMatch = _ORIGIN_EXPECT_RE.exec(text);
  if (labelMatch === null) return [null, AUTHORED_STEP_CAUSE_ORIGIN];
  const caseAnchors = _cached_mindmap_anchor_map(String(mindmapText || ""))[String(opts.autoid || "")] || {};
  const atoms = (caseAnchors[text] || []).map(_semantic_whitespace);
  const steps = (caseAnchors[_expectation_step_anchor(labelMatch[1])] || []).map(String);
  if (!steps.length || steps.length !== atoms.length) {
    return [null, AUTHORED_STEP_CAUSE_ANCHORS];
  }
  const needle = _semantic_whitespace(opts.source_text);
  const bound = new Set(steps.filter((_, index) => needle && atoms[index].includes(needle)));
  if (bound.size !== 1) return [null, AUTHORED_STEP_CAUSE_TEXT];
  const only = [...bound][0];
  if (/^\d+$/.test(only) && parseInt(only, 10) >= 1) {
    return [parseInt(only, 10), null];
  }
  return [null, AUTHORED_STEP_CAUSE_TEXT];
}

export function authored_expectation_step(mindmapText: string, opts: { autoid: string; origin: string; source_text: string }): number | null {
  return authored_expectation_step_binding(mindmapText, opts)[0];
}

export function _mindmap_anchor_map(mindmapText: string): Record<string, Record<string, string[]>> {
  let roots: any;
  try {
    roots = JSON.parse(String(mindmapText || "").replace(/^﻿﻿/u, ""));
  } catch {
    return {};
  }
  if (roots && typeof roots === "object" && !Array.isArray(roots)) roots = [roots];
  if (!Array.isArray(roots)) return {};
  const out: Record<string, Record<string, string[]>> = {};
  const add = (aid: string, origin: string, value: string) => {
    if (aid && value) {
      if (!out[aid]) out[aid] = {};
      if (!out[aid][origin]) out[aid][origin] = [];
      out[aid][origin].push(value);
    }
  };
  const addStep = (aid: string, label: string, value: string) => {
    add(aid, `step:${label}`, value);
    add(aid, "__step_label__", label);
    add(aid, "__step_text__", value);
  };
  const processCase = (case_: any, orphanNotes: string[], groupPath: string[]) => {
    const aid = _node_autoid(case_);
    const title = _node_text(case_);
    add(aid, "title", title);
    add(aid, "__case_text__", title);
    for (const group of groupPath) add(aid, "__group_path__", group);
    const children = _node_children(case_);
    const leafExpectationLayout = children.length === 1 && !_node_children(children[0]).length && !Object.keys(_numbered_atoms(_node_text(children[0]))).length;
    let stepNodes: any[];
    if (leafExpectationLayout) {
      const stepAtoms = _action_atoms(title);
      for (const [label, atom] of Object.entries(stepAtoms)) addStep(aid, label, atom);
      const expectationText = _node_text(children[0]);
      add(aid, "__case_text__", expectationText);
      let expectationAtoms = _bracket_labeled_atoms(expectationText);
      if (!Object.keys(expectationAtoms).length) expectationAtoms = { "1": expectationText };
      for (const [label, atom] of Object.entries(expectationAtoms)) {
        add(aid, `expectation:${label}`, atom);
        let linkedSteps = Object.entries(stepAtoms)
          .filter(([, stepAtom]) => new RegExp(`\\[${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\]`).test(stepAtom))
          .map(([stepLabel]) => stepLabel);
        if (!linkedSteps.length && Object.keys(stepAtoms).length === 1) linkedSteps = Object.keys(stepAtoms);
        for (const stepLabel of linkedSteps) add(aid, _expectation_step_anchor(label), stepLabel);
      }
      stepNodes = [];
    } else {
      stepNodes = children;
    }
    stepNodes.forEach((stepNode, index0) => {
      const index = index0 + 1;
      const stepText = _node_text(stepNode);
      add(aid, "__case_text__", stepText);
      const numberedAtoms = _numbered_atoms(stepText);
      const atoms = Object.keys(numberedAtoms).length ? _action_atoms(stepText) : {};
      const parentStepLabels = Object.keys(atoms).length ? Object.keys(atoms) : [String(index)];
      if (Object.keys(atoms).length) {
        for (const [label, atom] of Object.entries(atoms)) addStep(aid, label, atom);
      } else {
        addStep(aid, String(index), stepText);
      }
      _node_children(stepNode).forEach((expNode, expIndex0) => {
        const expIndex = expIndex0 + 1;
        const expText = _node_text(expNode);
        add(aid, "__case_text__", expText);
        const expAtoms = _numbered_atoms(expText);
        const linkFor = (label: string) => {
          let linked = Object.entries(atoms)
            .filter(([, stepAtom]) => new RegExp(`\\[${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\]`).test(stepAtom))
            .map(([stepLabel]) => stepLabel);
          if (!linked.length && parentStepLabels.length === 1) linked = parentStepLabels;
          return linked;
        };
        if (Object.keys(expAtoms).length) {
          for (const [label, atom] of Object.entries(expAtoms)) {
            add(aid, `expectation:${label}`, atom);
            for (const parentLabel of linkFor(label)) add(aid, _expectation_step_anchor(label), parentLabel);
          }
        } else {
          const labelMatch = new RegExp(`^\\s*\\[(${_LOCATOR_TOKEN})\\]`).exec(expText);
          const label = labelMatch ? labelMatch[1] : String(expIndex);
          add(aid, `expectation:${label}`, expText);
          for (const parentLabel of linkFor(label)) add(aid, _expectation_step_anchor(label), parentLabel);
        }
      });
    });
    orphanNotes.forEach((note, index0) => {
      add(aid, `orphan_note:${index0 + 1}`, note);
    });
  };
  const walk = (parent: any, groupPath: string[], includeParent = true) => {
    const parentText = _node_text(parent).trim();
    const currentPath = includeParent && parentText ? [...groupPath, parentText] : [...groupPath];
    const children = _node_children(parent);
    const cases = children.filter((child: any) => _node_autoid(child));
    if (cases.length) {
      const orphanNotes = children.filter((child: any) => !_node_autoid(child) && _node_text(child)).map(_node_text);
      let previousSibling = "";
      for (const case_ of cases) {
        processCase(case_, orphanNotes, currentPath);
        const aid = _node_autoid(case_);
        if (previousSibling) add(aid, "__previous_sibling__", previousSibling);
        previousSibling = aid;
      }
    }
    for (const child of children) {
      if (!_node_autoid(child)) walk(child, currentPath);
    }
  };
  for (const root of roots) {
    if (root && typeof root === "object") {
      if (_node_autoid(root)) processCase(root, [], []);
      else walk(root, [], true);
    }
  }
  return out;
}

export function public_case_locators(caseAnchors: any): string[] {
  if (!caseAnchors || typeof caseAnchors !== "object") return [];
  return Object.keys(caseAnchors).filter((locator) => !locator.startsWith("__")).sort();
}

function _verbatim_duplicate_disclosures(mindmapText: string): any[] {
  const byText: Record<string, string[]> = {};
  for (const [aid, caseAnchors] of Object.entries(_mindmap_anchor_map(mindmapText))) {
    const caseText = JSON.stringify(caseAnchors.__case_text__ || []);
    if (caseText !== "[]") {
      if (!byText[caseText]) byText[caseText] = [];
      byText[caseText].push(aid);
    }
  }
  const groups = Object.values(byText).filter((aids) => aids.length > 1).map((aids) => [...aids].sort()).sort();
  const disclosures: any[] = [];
  for (const aids of groups) {
    for (let i = 0; i + 1 < aids.length; i++) {
      const [first, second] = [aids[i], aids[i + 1]];
      disclosures.push({
        autoid: first, related_autoid: second, code: "verbatim_duplicate_disclosure",
        message: `用例 ${first} 与 ${second} 的标题、步骤、预期逐字完全相同；已按原文各出卡，不去重、不合并，请人工确认是否为有意重复`,
        reason_code: "verbatim_duplicate", fallback_allowed: false,
      });
    }
  }
  return disclosures;
}

export function closed_mindmap_case_autoids(mindmapText: string): string[] {
  const anchors = _mindmap_anchor_map(mindmapText);
  const autoids = Object.keys(anchors).filter((aid) => /^[0-9]{18}$/.test(String(aid || "")));
  if (!autoids.length || autoids.length !== Object.keys(anchors).length) {
    throw new MachineMindmapError("trusted mindmap source has no closed 18-digit autoid set");
  }
  return autoids;
}

export function closed_mindmap_command_heads(mindmapText: string, opts: { autoids?: Iterable<string> | null } = {}): string[] {
  const anchors = _mindmap_anchor_map(mindmapText);
  const selected = opts.autoids === null || opts.autoids === undefined ? null : new Set([...opts.autoids].map(String));
  const segments = new Set<string>();
  for (const [aid, caseAnchors] of Object.entries(anchors)) {
    if (selected !== null && !selected.has(aid)) continue;
    for (const [locator, atoms] of Object.entries(caseAnchors)) {
      if (locator.startsWith("__")) continue;
      for (const atom of atoms) {
        for (const line of String(atom).split(/\r?\n/)) {
          for (let segment of line.split(/[；;。]/)) {
            segment = segment.trim().replace(/^\d+[.、．]?\s*/, "").split(/\s+/).join(" ");
            if (segment && [...segment].some((ch) => /[a-zA-Z]/.test(ch))) {
              segments.add(segment);
            }
          }
        }
      }
    }
  }
  return [...segments].sort();
}

function _resolved_side_quote_bytes(locator: string, opts: { side: string; autoid: string; mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any }): string | null {
  const loc = String(locator || "").trim();
  if (!loc) return "";
  if (opts.side === "spec") {
    const raw = _external_origin_raw_text(loc, opts);
    return raw || null;
  }
  const caseAnchors = _mindmap_anchor_map(opts.mindmap_text)[opts.autoid] || {};
  if (!public_case_locators(caseAnchors).includes(loc)) return null;
  const values = caseAnchors[loc] || [];
  if (!values.length || !String(values[0])) return null;
  return String(values[0]);
}

export function consistency_source_atoms_for_brief(mindmapText: string): any {
  const anchors = _mindmap_anchor_map(mindmapText);
  const out: any = {};
  for (const [aid, caseAnchors] of Object.entries(anchors)) {
    const locators: Record<string, string> = {};
    for (const locator of public_case_locators(caseAnchors)) {
      const values = caseAnchors[locator] || [];
      if (values.length && String(values[0])) locators[locator] = String(values[0]);
    }
    if (Object.keys(locators).length) out[String(aid)] = { case_locators: locators };
  }
  return out;
}

export function stamp_consistency_quotes(value: any, autoid: string, opts: {
  mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any;
  cross_check: boolean; mutate?: boolean; spec_optional?: boolean | null; case_optional?: boolean | null;
}): string {
  const mutate = opts.mutate !== false;
  for (const field of ["spec_locator", "case_locator"]) {
    if (field in value && typeof value[field] !== "string") return "consistency_conclusion_invalid";
  }
  const specLocator = String(value.spec_locator || "").trim();
  const caseLocator = String(value.case_locator || "").trim();
  const hasSpecSurface = Boolean(String(opts.spec_text || "").trim()) || (opts.defect_spec_receipt && typeof opts.defect_spec_receipt === "object");
  const specOptional = opts.spec_optional === null || opts.spec_optional === undefined ? !specLocator || !hasSpecSurface : opts.spec_optional;
  const caseOptional = opts.case_optional === null || opts.case_optional === undefined ? !caseLocator : opts.case_optional;
  const resolveKw = { autoid, mindmap_text: opts.mindmap_text, governing_spec: opts.governing_spec, spec_text: opts.spec_text, defect_spec_receipt: opts.defect_spec_receipt };
  let stampedPremises: any[] | null = null;
  const premises = value.premises;
  if (Array.isArray(premises)) {
    stampedPremises = [];
    for (let index = 0; index < premises.length; index++) {
      const premise = premises[index];
      if (!premise || typeof premise !== "object") return premise_stamp_failure(index, "shape_invalid");
      const extra = Object.keys(premise).filter((k) => !["text", "origin", "locator", "source_sha256"].includes(k));
      if (extra.length) return premise_stamp_failure(index, "shape_invalid");
      const origin = String(premise.origin || "");
      const locator = String(premise.locator || "").trim();
      if (!["spec", "case"].includes(origin) || !locator) return premise_stamp_failure(index, "shape_invalid");
      let text = premise.text;
      if (text === null || text === undefined) text = "";
      if (typeof text !== "string") return premise_stamp_failure(index, "shape_invalid");
      const side = origin === "spec" ? "spec" : "case";
      const raw = _resolved_side_quote_bytes(locator, { side, ...resolveKw });
      if (raw === null) {
        if (origin === "spec" && !hasSpecSurface) {
          stampedPremises.push({ ...premise });
          continue;
        }
        return premise_stamp_failure(index, "locator_unresolved");
      }
      if (text.trim() && opts.cross_check && text !== raw) return premise_stamp_failure(index, "text_drift");
      const stamped = { ...premise };
      stamped.text = raw;
      stampedPremises.push(stamped);
    }
  }
  let stampedSurfaces: any[] | null = null;
  const conflict = value[AUTHORED_CONFLICT_KEY];
  if (conflict && typeof conflict === "object" && Array.isArray(conflict.surfaces)) {
    stampedSurfaces = [];
    for (let index = 0; index < conflict.surfaces.length; index++) {
      const surface = conflict.surfaces[index];
      if (!surface || typeof surface !== "object") return conflict_surface_stamp_failure(index, "invalid");
      const locator = String(surface.locator || "").trim();
      const raw = _resolved_side_quote_bytes(locator, { side: "case", ...resolveKw });
      if (!raw) return conflict_surface_stamp_failure(index, "locator_unresolved");
      let caller = surface.quote;
      if (caller === null || caller === undefined) caller = "";
      if (typeof caller !== "string") return conflict_surface_stamp_failure(index, "invalid");
      if (caller.trim() && opts.cross_check && caller !== raw) return conflict_surface_stamp_failure(index, "text_drift");
      const stamped = { ...surface };
      stamped.quote = raw;
      stampedSurfaces.push(stamped);
    }
  }
  const specRaw = _resolved_side_quote_bytes(specLocator, { side: "spec", ...resolveKw });
  if (specLocator) {
    if (specRaw === null) {
      if (!specOptional) return "consistency_spec_locator_unresolved";
    } else {
      let caller = value.spec_quote;
      if (caller === null || caller === undefined) caller = "";
      if (typeof caller !== "string") return "consistency_conclusion_invalid";
      if (caller.trim() && opts.cross_check && caller !== specRaw) return "consistency_spec_quote_drift";
    }
  }
  const caseRaw = _resolved_side_quote_bytes(caseLocator, { side: "case", ...resolveKw });
  if (caseLocator) {
    if (caseRaw === null) {
      if (!caseOptional) return "consistency_case_locator_unresolved";
    } else {
      let caller = value.case_quote;
      if (caller === null || caller === undefined) caller = "";
      if (typeof caller !== "string") return "consistency_conclusion_invalid";
      if (caller.trim() && opts.cross_check && caller !== caseRaw) return "consistency_case_quote_drift";
    }
  }
  if (!mutate) return "";
  if (specLocator && specRaw) {
    value.spec_quote = specRaw;
  } else if (!("spec_quote" in value) || value.spec_quote === null || value.spec_quote === undefined) {
    value.spec_quote = String(value.spec_quote || "");
  }
  if (caseLocator && caseRaw) {
    value.case_quote = caseRaw;
  } else if (!("case_quote" in value) || value.case_quote === null || value.case_quote === undefined) {
    value.case_quote = String(value.case_quote || "");
  }
  if (stampedPremises !== null) value.premises = stampedPremises;
  if (stampedSurfaces !== null) {
    value[AUTHORED_CONFLICT_KEY] = { ...value[AUTHORED_CONFLICT_KEY], surfaces: stampedSurfaces };
  }
  return "";
}

export function resolve_consistency_evidence(case_: any, proposal: any, opts: {
  mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any;
}): [string, string, any | null] {
  if (!proposal || typeof proposal !== "object" || JSON.stringify(Object.keys(proposal).sort()) !== JSON.stringify([..._CONSISTENCY_MATERIAL_KEYS].sort())
      || proposal.schema !== _CONSISTENCY_DRAFT_SCHEMA) {
    return ["invalid", "consistency_schema_keys_invalid", null];
  }
  const premises = proposal.premises;
  if (!Array.isArray(premises)) return ["invalid", "consistency_conflict_premises_missing", null];
  const autoid = String(case_.autoid || "");
  const working: any = { ...proposal };
  working.premises = premises.map((item: any) => (item && typeof item === "object" ? { ...item } : item));
  for (let index = 0; index < working.premises.length; index++) {
    const premise = working.premises[index];
    if (!premise || typeof premise !== "object") return ["invalid", premise_stamp_failure(index, "shape_invalid"), null];
    const extra = Object.keys(premise).filter((k) => !["text", "origin", "locator"].includes(k));
    if (extra.length || !["spec", "case"].includes(premise.origin)) {
      return ["invalid", premise_stamp_failure(index, "shape_invalid"), null];
    }
    if ("text" in premise && typeof premise.text !== "string") {
      return ["invalid", premise_stamp_failure(index, "shape_invalid"), null];
    }
    if (typeof premise.locator !== "string" || !String(premise.locator || "").trim()) {
      return ["invalid", premise_stamp_failure(index, "shape_invalid"), null];
    }
  }
  const stampFailure = stamp_consistency_quotes(working, autoid, { ...opts, cross_check: true, spec_optional: false, case_optional: false });
  if (stampFailure) return ["invalid", stampFailure, null];
  const acceptedPremises: any[] = working.premises.map((premise: any) => {
    const raw = String(premise.text || "");
    return { text: raw, origin: String(premise.origin), locator: String(premise.locator).trim(), source_sha256: sha256_bytes(Buffer.from(_norm_ws(raw), "utf8")) };
  });
  const accepted = { ...working, schema: _CONSISTENCY_MATERIAL_SCHEMA, premises: acceptedPremises };
  const [state, reason] = consistency_evidence_status(case_, accepted, opts);
  return [state, reason, state !== "invalid" ? accepted : null];
}

export function quote_closure_failure(autoid: string, opts: {
  spec_locator: string; spec_quote: string; case_locator: string; case_quote: string;
  mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any;
  spec_optional?: boolean; case_optional?: boolean;
}): string {
  return stamp_consistency_quotes(
    { spec_locator: opts.spec_locator, spec_quote: opts.spec_quote, case_locator: opts.case_locator, case_quote: opts.case_quote },
    autoid,
    { ...opts, cross_check: true, mutate: false, spec_optional: opts.spec_optional ?? false, case_optional: opts.case_optional ?? false },
  );
}

export function recompose_consistency_anchor_failure(value: any, autoid: string, opts: {
  mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any;
}): string {
  if (!value || typeof value !== "object") return "";
  return stamp_consistency_quotes(value, autoid, { ...opts, cross_check: true, mutate: false });
}

export function consistency_evidence_status(case_: any, proposal: any, opts: {
  mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any;
}): [string, string] {
  if (!proposal || typeof proposal !== "object" || JSON.stringify(Object.keys(proposal).sort()) !== JSON.stringify([..._CONSISTENCY_MATERIAL_KEYS].sort())) {
    return ["invalid", "consistency_schema_keys_invalid"];
  }
  const autoid = String(case_.autoid || "");
  if (proposal.schema !== _CONSISTENCY_MATERIAL_SCHEMA || String(proposal.autoid || "") !== autoid || !["consistent", "conflict"].includes(proposal.verdict)) {
    return ["invalid", "consistency_identity_or_verdict_invalid"];
  }
  const stampFailure = stamp_consistency_quotes(proposal, autoid, { ...opts, cross_check: true, spec_optional: false, case_optional: false });
  if (stampFailure) return ["invalid", stampFailure];
  for (const key of ["schema", "autoid", "verdict", "spec_quote", "case_quote", "spec_locator", "case_locator", "incompatibility"]) {
    const value = proposal[key];
    if (typeof value !== "string" || !value.trim()) return ["invalid", "consistency_text_field_invalid"];
  }
  const premises = proposal.premises;
  if (!Array.isArray(premises) || (proposal.verdict === "conflict" && !premises.length)) {
    return ["invalid", "consistency_conflict_premises_missing"];
  }
  for (let index = 0; index < premises.length; index++) {
    const premise = premises[index];
    if (!premise || typeof premise !== "object" || JSON.stringify(Object.keys(premise).sort()) !== JSON.stringify(["locator", "origin", "source_sha256", "text"])
        || !["spec", "case"].includes(premise.origin) || typeof premise.text !== "string" || !String(premise.text || "").trim()
        || typeof premise.locator !== "string" || !String(premise.locator || "").trim()
        || typeof premise.source_sha256 !== "string" || !_SHA256_RE.test(String(premise.source_sha256 || ""))) {
      return ["invalid", premise_stamp_failure(index, "shape_invalid")];
    }
    const expectedDigest = sha256_bytes(Buffer.from(_norm_ws(String(premise.text)), "utf8"));
    if (String(premise.source_sha256) !== expectedDigest) {
      return ["invalid", premise_stamp_failure(index, "digest_invalid")];
    }
  }
  const verdict = String(proposal.verdict);
  if ("consistency" in case_) {
    const coverageFailure = clause_coverage_failure(String(proposal.spec_quote), proposal.spec_clauses);
    if (coverageFailure) return ["invalid", coverageFailure];
    return [verdict, ""];
  }
  const clauseFailure = _scenario1_clause_failure(String(proposal.spec_quote), proposal.spec_clauses);
  if (verdict === "conflict") {
    if (clauseFailure) return ["invalid", clauseFailure];
  } else if (clauseFailure !== "scenario1_clause_consistent_branch") {
    return ["invalid", "consistency_clause_support_missing"];
  }
  return [verdict, ""];
}

export function fill_mechanical_fields(data: any, mindmapText: string): string[] {
  const anchors = _mindmap_anchor_map(mindmapText);
  const repaired: string[] = [];
  for (const case_ of data.cases || []) {
    if (!case_ || typeof case_ !== "object") continue;
    const autoid = String(case_.autoid || "");
    const caseAnchors = anchors[autoid];
    if (!caseAnchors) continue;
    const before = JSON.stringify([case_.group_path, case_.steps, case_.expectations_by_step, case_.origin]);
    case_.group_path = (caseAnchors.__group_path__ || []).filter((value: any) => String(value).trim());
    case_.steps = (caseAnchors.__step_label__ || []).map((label: string, i: number) => ({ n: label, text: (caseAnchors.__step_text__ || [])[i] }));
    const authored: [string, string, string[]][] = [];
    for (const [anchorOrigin, values] of Object.entries(caseAnchors)) {
      const match = _ORIGIN_EXPECT_RE.exec(anchorOrigin);
      if (match === null) continue;
      const label = match[1];
      const allowedSteps = /^\d+$/.test(label) ? [label] : (caseAnchors[_expectation_step_anchor(label)] || []).map(String);
      for (const value of values) authored.push([anchorOrigin, value, allowedSteps]);
    }
    if (authored.length) {
      const machine = (case_.expectations_by_step || []).filter((item: any) => item && typeof item === "object");
      const priorAuthor = machine.filter((item: any) => _ORIGIN_EXPECT_RE.test(String(item.origin || "").trim()));
      const external = machine.filter((item: any) => !priorAuthor.includes(item));
      const rebuilt: any[] = [];
      authored.forEach(([anchorOrigin, value, allowedSteps], index) => {
        const step = index < allowedSteps.length ? allowedSteps[index] : allowedSteps.length ? allowedSteps[0] : "";
        const carried = priorAuthor.length === authored.length ? { ...priorAuthor[index] } : {};
        Object.assign(carried, { n: step, origin: anchorOrigin, text: value });
        if (!("assertion" in carried)) carried.assertion = null;
        rebuilt.push(carried);
      });
      case_.expectations_by_step = [...rebuilt, ...external];
    }
    const origin = case_.origin;
    const contract = case_.contract;
    if (origin && typeof origin === "object" && contract && typeof contract === "object") {
      for (const field of ["intent", "verification_method", "expectation"]) {
        const declared = String(origin[field] || "");
        if (declared.startsWith("spec:") || declared.startsWith("defect:")) continue;
        const candidates = _verbatim_candidates(String(contract[field] || ""));
        if (!candidates.length) continue;
        const matchesDeclared = candidates.some((candidate) =>
          (caseAnchors[declared] || []).some((value: string) => _source_atom_forms(value, declared).includes(candidate)));
        if (matchesDeclared) continue;
        const hits = public_case_locators(caseAnchors).filter((anchorOrigin) =>
          candidates.some((candidate) =>
            (caseAnchors[anchorOrigin] || []).some((value: string) => _source_atom_forms(value, anchorOrigin).includes(candidate))));
        if (new Set(hits).size === 1) origin[field] = hits[0];
      }
    }
    const after = JSON.stringify([case_.group_path, case_.steps, case_.expectations_by_step, case_.origin]);
    const declaredStatus = case_.source_status;
    const derivedStatus = _derived_source_status(case_);
    if (declaredStatus !== derivedStatus) case_.source_status = derivedStatus;
    if (before !== after || declaredStatus !== derivedStatus) repaired.push(autoid);
  }
  return repaired;
}

export function verbatim_failures(data: any, mindmapText: string, specText: string | null, opts: {
  governing_spec?: string | null; governing_spec_status?: string | null; defect_spec_receipt?: any;
  defect_spec_status?: string | null; defect_spec_receipt_sha256?: string | null;
} = {}): Record<string, string[]> {
  const anchors = _mindmap_anchor_map(mindmapText);
  let acceptedSpec = opts.governing_spec;
  if (acceptedSpec === null || acceptedSpec === undefined) {
    acceptedSpec = String(data.governing_spec || "").trim() || null;
  }
  let resolvedSpecStatus = opts.governing_spec_status;
  if ((resolvedSpecStatus === null || resolvedSpecStatus === undefined) && opts.governing_spec !== null && opts.governing_spec !== undefined) {
    resolvedSpecStatus = opts.governing_spec ? "bound" : "no_governing_spec";
  }
  const bad: Record<string, string[]> = {};
  const addBad = (autoid: string, field: string) => {
    if (!bad[autoid]) bad[autoid] = [];
    bad[autoid].push(field);
  };
  for (const case_ of data.cases || []) {
    if (!case_ || typeof case_ !== "object") continue;
    const autoid = String(case_.autoid || "");
    const defectSpecStatus = opts.defect_spec_status !== null && opts.defect_spec_status !== undefined ? opts.defect_spec_status : String(data.defect_spec_status || "") || null;
    const defectSpecReceiptSha = opts.defect_spec_receipt_sha256 !== null && opts.defect_spec_receipt_sha256 !== undefined ? opts.defect_spec_receipt_sha256 : String(data.defect_spec_receipt_sha256 || "") || null;
    const scenario2Unresolved = Boolean(_scenario2_incomplete_reason(case_, {
      governing_spec_status: resolvedSpecStatus, defect_spec_status: defectSpecStatus,
      defect_spec_receipt_sha256: defectSpecReceiptSha,
    }));
    const contract = case_.contract || {};
    const origin = case_.origin || {};
    const caseAnchors = anchors[autoid] || {};
    const authoredGroups = (caseAnchors.__group_path__ || []).map(_norm_ws);
    const machineGroups = (case_.group_path || []).map(_norm_ws).filter(Boolean);
    if (JSON.stringify(machineGroups) !== JSON.stringify(authoredGroups)) addBad(autoid, "group_path");
    const rawMachineSteps = case_.steps;
    const stepLabels = caseAnchors.__step_label__ || [];
    const stepTexts = caseAnchors.__step_text__ || [];
    let stepsInvalid = !Array.isArray(rawMachineSteps) || rawMachineSteps.length !== stepLabels.length;
    if (!stepsInvalid) {
      for (let i = 0; i < rawMachineSteps.length; i++) {
        const item = rawMachineSteps[i];
        if (!item || typeof item !== "object") { stepsInvalid = true; break; }
        const candidates = _verbatim_candidates(String(item.text || ""));
        const sourceForms = _verbatim_candidates(stepTexts[i]);
        if (String(item.n || "").trim() !== stepLabels[i] || !candidates.length || !candidates.some((c) => sourceForms.includes(c))) {
          stepsInvalid = true;
          break;
        }
      }
    }
    if (stepsInvalid) addBad(autoid, "steps");
    for (const field of ["intent", "verification_method", "expectation"]) {
      const candidates = _verbatim_candidates(String(contract[field] || ""));
      if (!candidates.length) continue;
      const fieldOrigin = String(origin[field] || "");
      const externalForms = _external_origin_forms(fieldOrigin, { governing_spec: acceptedSpec, spec_text: specText, defect_spec_receipt: opts.defect_spec_receipt });
      const anchorValues = caseAnchors[fieldOrigin] || [];
      const sourceForms = externalForms !== null ? externalForms : anchorValues.flatMap((value: string) => _source_atom_forms(value, fieldOrigin));
      if (!sourceForms.length || !candidates.some((c) => sourceForms.includes(c))) addBad(autoid, field);
    }
    const machineExpectations = (case_.expectations_by_step || []).filter((item: any) => item && typeof item === "object");
    const authoredExpectations: [string, string, string[]][] = [];
    for (const [anchorOrigin, values] of Object.entries(caseAnchors)) {
      const match = _ORIGIN_EXPECT_RE.exec(anchorOrigin);
      if (match === null) continue;
      const label = match[1];
      const allowedSteps = /^\d+$/.test(label) ? [label] : (caseAnchors[_expectation_step_anchor(label)] || []).map(String);
      for (const value of values) authoredExpectations.push([anchorOrigin, value, allowedSteps]);
    }
    const machineAuthoredExpectations: any[] = [];
    let seenExternal = false;
    let expectationSetInvalid = false;
    for (const item of machineExpectations) {
      const itemOrigin = String(item.origin || "").trim();
      if (itemOrigin.startsWith("spec:") || itemOrigin.startsWith("defect:")) {
        seenExternal = true;
        continue;
      }
      if (seenExternal) expectationSetInvalid = true;
      if (_ORIGIN_EXPECT_RE.test(itemOrigin)) machineAuthoredExpectations.push(item);
    }
    if (machineAuthoredExpectations.length !== authoredExpectations.length) {
      expectationSetInvalid = true;
    } else {
      for (let i = 0; i < machineAuthoredExpectations.length; i++) {
        const item = machineAuthoredExpectations[i];
        const [expectedOrigin, sourceValue, allowedSteps] = authoredExpectations[i];
        const candidates = _verbatim_candidates(String(item.text || ""));
        if (String(item.origin || "").trim() !== expectedOrigin || !allowedSteps.includes(String(item.n || "").trim())
            || !candidates.some((c) => _source_atom_forms(sourceValue, expectedOrigin).includes(c))) {
          expectationSetInvalid = true;
          break;
        }
      }
    }
    if (expectationSetInvalid) addBad(autoid, "expectations_by_step");
    machineExpectations.forEach((item: any, index: number) => {
      if (!item || typeof item !== "object") return;
      const candidates = _verbatim_candidates(String(item.text || ""));
      if (!candidates.length) return;
      const itemOrigin = String(item.origin || "");
      const externalForms = _external_origin_forms(itemOrigin, { governing_spec: acceptedSpec, spec_text: specText, defect_spec_receipt: opts.defect_spec_receipt });
      const anchorValues = caseAnchors[itemOrigin] || [];
      const sourceForms = externalForms !== null ? externalForms : anchorValues.flatMap((value: string) => _source_atom_forms(value, itemOrigin));
      if (!sourceForms.length || !candidates.some((c) => sourceForms.includes(c))) {
        addBad(autoid, `expectations_by_step[${index}]`);
        return;
      }
      const assertion = item.assertion;
      const explicitUnresolvedAssertion = "assertion" in item && assertion === null
        && (scenario2Unresolved || (_derived_source_status(case_) === "complete" && _derived_typed_assertion_status(case_) === "pending"));
      if (!explicitUnresolvedAssertion) {
        const rawAssertionValue = assertion && typeof assertion === "object" ? assertion.value : null;
        const rawAssertionOperator = assertion && typeof assertion === "object" ? assertion.operator : null;
        const assertionValueValid = typeof rawAssertionValue === "string" && Boolean(rawAssertionValue);
        const assertionOperatorValid = typeof rawAssertionOperator === "string" && Boolean(rawAssertionOperator.trim());
        const valueCandidates = assertionValueValid ? _verbatim_candidates(rawAssertionValue as string) : [];
        const assertionSourceForms = externalForms !== null ? externalForms : anchorValues.flatMap((value: string) => _assertion_source_forms(value, itemOrigin));
        if (!assertionOperatorValid || !valueCandidates.length || !valueCandidates.some((c) => assertionSourceForms.includes(c))) {
          addBad(autoid, `expectations_by_step[${index}].assertion.value`);
        }
      }
      const stepNumber = String(item.n || "").trim();
      let allowedSteps: string[];
      if (itemOrigin.startsWith("expectation:")) {
        const expectationLabel = itemOrigin.split(":", 2)[1];
        allowedSteps = /^\d+$/.test(expectationLabel) ? [expectationLabel] : (caseAnchors[_expectation_step_anchor(expectationLabel)] || []).map(String);
      } else {
        allowedSteps = caseAnchors[`step:${stepNumber}`] ? [stepNumber] : [];
      }
      if (!allowedSteps.includes(stepNumber)) addBad(autoid, `expectations_by_step[${index}].n`);
    });
    const authoredCaseText = (caseAnchors.__case_text__ || []).flatMap((value: string) => _source_atom_forms(value, ""));
    const authoredCaseAtoms = new Set<string>();
    for (const [locator, values] of Object.entries(caseAnchors)) {
      for (const value of values) for (const form of _source_atom_forms(value, locator)) authoredCaseAtoms.add(form);
    }
    for (const form of authoredCaseText) authoredCaseAtoms.add(form);
    (case_.adaptation_notes || []).forEach((note: any, index: number) => {
      const candidates = _verbatim_candidates(String(note || ""));
      if (candidates.length && !candidates.some((c) => authoredCaseAtoms.has(c))) {
        addBad(autoid, `adaptation_notes[${index}]`);
      }
    });
    const dependency = String(case_.depends_on || "").trim();
    const sourcePrevious = caseAnchors.__previous_sibling__ || [];
    const explicitDependencies = sourcePrevious.filter((previous: string) => authoredCaseText.some((source) => source.includes(previous)));
    if (explicitDependencies.length) {
      if (dependency !== explicitDependencies[explicitDependencies.length - 1]) addBad(autoid, "depends_on");
    } else if (dependency) {
      addBad(autoid, "depends_on");
    }
  }
  return bad;
}

const _EVIDENCE_FIELD_RE = /^expectations_by_step\[(\d+)\](?:\.(assertion\.value|n))?$/;

function _unfolded_atom(canonical: string, sourceText: string): string {
  if (!canonical) return canonical;
  const pattern = _whitespace_tolerant_pattern(canonical);
  if (pattern === null) return canonical;
  const match = pattern.exec(String(sourceText || ""));
  return match !== null ? match[0] : canonical;
}

export function verbatim_source_evidence(case_: any, field: string, opts: {
  mindmap_text: string; governing_spec?: string | null; spec_text?: string | null; defect_spec_receipt?: any;
}): any {
  const autoid = String(case_.autoid || "");
  const caseAnchors = _mindmap_anchor_map(opts.mindmap_text)[autoid] || {};
  const rawOrigin = case_.origin;
  const originMap = rawOrigin && typeof rawOrigin === "object" ? rawOrigin : {};
  const expectations = (case_.expectations_by_step || []).filter((item: any) => item && typeof item === "object");
  const anchored = (origin: any, assertion = false): any => {
    const text = String(origin || "");
    const external = _external_origin_forms(text, opts);
    if (external !== null) {
      const raw = _external_origin_raw_text(text, opts);
      return { origin: text, external: true, atoms: external.slice(0, 1).map((form) => _unfolded_atom(form, raw)), kind: "anchored" };
    }
    const forms = assertion ? _assertion_source_forms : _source_atom_forms;
    const atoms: string[] = [];
    const canonicalSeen = new Set<string>();
    for (const value of caseAnchors[text] || []) {
      const candidates = forms(value, text);
      if (!candidates.length || canonicalSeen.has(candidates[0])) continue;
      canonicalSeen.add(candidates[0]);
      atoms.push(_unfolded_atom(candidates[0], value));
    }
    return { origin: text, external: false, atoms, kind: "anchored" };
  };
  const structural = (origin: any = ""): any => ({ origin: String(origin || ""), external: false, atoms: [], kind: "structural" });
  if (["intent", "verification_method", "expectation"].includes(field)) {
    return anchored(originMap[field]);
  }
  const match = _EVIDENCE_FIELD_RE.exec(String(field || ""));
  if (match !== null) {
    const index = parseInt(match[1], 10);
    const item = index < expectations.length ? expectations[index] : {};
    const itemOrigin = item && typeof item === "object" ? item.origin : "";
    if (match[2] === "n") return structural(itemOrigin);
    return anchored(itemOrigin, match[2] === "assertion.value");
  }
  if (String(field || "").startsWith("adaptation_notes[")) {
    return { origin: "", external: false, atoms: [], kind: "case_atoms" };
  }
  return structural();
}

function _is_disclosure_ref(value: any): boolean {
  return value && typeof value === "object" && !Array.isArray(value)
    && JSON.stringify(Object.keys(value).sort()) === JSON.stringify([..._DISCLOSURE_REF_KEYS].sort())
    && typeof value.autoid === "string" && typeof value.expectation_id === "string";
}

function _disclosure_items_as_contract_refs(items: any[], contractSha256ByAutoid: Record<string, string>): [any[], number] {
  const projected: any[] = [];
  let converted = 0;
  for (const item of items) {
    const autoid = String(item.autoid || "");
    const expectationId = String(item.expectation_id || "");
    if (!_DISCLOSURE_REF_FIELDS.some((field) => field in item) || !autoid || !expectationId || !(autoid in contractSha256ByAutoid)) {
      projected.push(item);
      continue;
    }
    const ref = { autoid, expectation_id: expectationId };
    const out: any = {};
    for (const [key, value] of Object.entries(item)) {
      out[key] = _DISCLOSURE_REF_FIELDS.includes(key) ? { ...ref } : value;
    }
    projected.push(out);
    converted += 1;
  }
  return [projected, converted];
}

function _sealed_disclosure_payload(payload: any, contractSha256ByAutoid: Record<string, string>): any {
  const encoded = encode_json_atomic(payload);
  const [tokens, depth] = scan_json_budget(encoded);
  if (encoded.length <= _PROJECTION_JSON_MAX_BYTES && tokens <= _PROJECTION_JSON_MAX_TOKENS && depth <= _PROJECTION_JSON_MAX_DEPTH) {
    return payload;
  }
  const [projected, converted] = _disclosure_items_as_contract_refs([...(payload.items || [])], contractSha256ByAutoid);
  if (!converted) return payload;
  return { ...payload, items: projected, storage_format: DISCLOSURE_STORAGE_CONTRACT_REFS };
}

export function project_machine_mindmap(batchDir: string, opts: {
  quarantine?: Record<string, string[]> | null; structure_quarantine?: Record<string, string[]> | null;
  criterion_unavailable?: Record<string, string> | null; missing_autoids?: string[] | null;
  manifest_cases?: any[] | null; expected_machine_sha256?: string | null; previously_owned_autoids?: string[] | null;
  resolved_governing_spec?: string | null; resolved_governing_spec_status?: string | null;
  mindmap_source_sha256?: string | null; resolved_defect_spec_status?: string | null;
  resolved_defect_spec_receipt_sha256?: string | null; resolved_defect_spec_receipt?: any;
  mindmap_text?: string | null; spec_text?: string | null;
  criterion_version_family?: string; criterion_manual_version?: string; criterion_rule_records?: any;
} = {}): any {
  const batchDirResolved = path.resolve(String(batchDir));
  const mmPath = path.join(batchDirResolved, "machine_mindmap.json");
  const [data, machineSha256] = load_machine_mindmap(mmPath);
  if (opts.expected_machine_sha256 && machineSha256 !== opts.expected_machine_sha256) {
    throw new MachineMindmapError("machine mindmap changed after verbatim verification");
  }
  const rawCases = data.cases;
  if (!Array.isArray(rawCases) || rawCases.some((case_: any) => !case_ || typeof case_ !== "object")) {
    throw new MachineMindmapError("machine mindmap cases must be an object array");
  }
  const cases = [...rawCases];
  const declaredCount = data.case_count;
  const autoids = cases.map((case_: any) => String(case_.autoid || "").trim());
  if (typeof declaredCount === "boolean" || !Number.isInteger(declaredCount) || declaredCount !== cases.length) {
    throw new MachineMindmapError("machine mindmap case_count does not match cases");
  }
  if (autoids.some((autoid) => !new RegExp(`^${_LOCATOR_TOKEN}$`).test(autoid))) {
    throw new MachineMindmapError("machine mindmap autoid is missing or invalid");
  }
  if (new Set(autoids).size !== autoids.length) {
    throw new MachineMindmapError("machine mindmap autoid values must be unique");
  }
  const missingIds = (opts.missing_autoids || []).map((autoid: any) => String(autoid || "").trim());
  if (missingIds.some((autoid) => !new RegExp(`^${_LOCATOR_TOKEN}$`).test(autoid)) || new Set(missingIds).size !== missingIds.length
      || missingIds.some((id) => autoids.includes(id))) {
    throw new MachineMindmapError("missing manifest autoid values are invalid or overlap");
  }
  const manifestCaseByAutoid: Record<string, any> = {};
  if (opts.manifest_cases !== null && opts.manifest_cases !== undefined) {
    if (!Array.isArray(opts.manifest_cases) || opts.manifest_cases.some((case_: any) => !case_ || typeof case_ !== "object")) {
      throw new MachineMindmapError("manifest cases must be an object array");
    }
    for (const manifestCase of opts.manifest_cases) {
      const manifestAutoid = String(manifestCase.autoid || "").trim();
      if (!new RegExp(`^${_LOCATOR_TOKEN}$`).test(manifestAutoid) || manifestAutoid in manifestCaseByAutoid) {
        throw new MachineMindmapError("manifest case autoid values are invalid or duplicate");
      }
      manifestCaseByAutoid[manifestAutoid] = manifestCase;
    }
    if (missingIds.some((autoid) => !(autoid in manifestCaseByAutoid))) {
      throw new MachineMindmapError("missing autoid has no manifest source case");
    }
    if (missingIds.length && !_SHA256_RE.test(String(opts.mindmap_source_sha256 || ""))) {
      throw new MachineMindmapError("manifest fallback requires the sealed mindmap source SHA256");
    }
  }
  const artifactSpec = String(data.governing_spec || "").trim() || null;
  const specIdentityClosed = Boolean(
    (["no_governing_spec", "ambiguous"].includes(String(opts.resolved_governing_spec_status)) && opts.resolved_governing_spec === null && artifactSpec === null)
    || (opts.resolved_governing_spec_status === "bound" && opts.resolved_governing_spec !== null && opts.resolved_governing_spec !== undefined && artifactSpec === opts.resolved_governing_spec));
  const scenario2SpecStatus = specIdentityClosed ? opts.resolved_governing_spec_status : null;
  const { CompletenessOutcome, classify_completeness, evaluate_spec } = require("../ist_core/compile_engine/conflict_chain");
  const { MACHINE_MINDMAP_BUCKETS } = require("../ist_core/tools/device/recompose_parts");
  let specEvaluation: any;
  if (opts.resolved_governing_spec_status === null || opts.resolved_governing_spec_status === undefined) {
    specEvaluation = evaluate_spec("no_governing_spec", "no_ticket_reference");
  } else {
    specEvaluation = evaluate_spec(opts.resolved_governing_spec_status, opts.resolved_defect_spec_status, {
      ticket_eligible: opts.resolved_defect_spec_receipt && typeof opts.resolved_defect_spec_receipt === "object" ? opts.resolved_defect_spec_receipt.eligible === true : null,
    });
  }
  const quarantine = opts.quarantine || {};
  const structureQuarantine = { ...(opts.structure_quarantine || {}) };
  const criterionUnavailable = opts.criterion_unavailable || {};
  const written: string[] = [];
  const needsDecision: any[] = [];
  const disclosures: any[] = missingIds
    .filter(() => opts.manifest_cases === null || opts.manifest_cases === undefined)
    .map((autoid) => ({
      autoid: String(autoid), code: "mindmap_gap_disclosure",
      message: "机械脑图没写到这份人工脑图，本轮退回，不编写",
      reason_code: "recompose_missing_case", fallback_allowed: true,
    }));
  const quarantined: any[] = [];
  const bucketCounts: Record<string, number> = {};
  const contractsDir = path.join(batchDirResolved, "contracts");
  const sidecarPath = path.join(batchDirResolved, MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME);
  try {
    if (fs.existsSync(sidecarPath)) fs.unlinkSync(sidecarPath);
  } catch {}
  const currentAutoids = new Set<string>([
    ...cases.map((case_: any) => String(case_.autoid || "")),
    ...missingIds,
    ...(opts.previously_owned_autoids || []).map(String),
  ]);
  fs.mkdirSync(contractsDir, { recursive: true });
  for (const autoid of currentAutoids) {
    if (!new RegExp(`^${_LOCATOR_TOKEN}$`).test(autoid)) continue;
    const name = path.join(contractsDir, `${autoid}.json`);
    if (!fs.existsSync(name)) continue;
    const info = fs.lstatSync(name);
    if (!info.isFile()) throw new MachineMindmapError("machine contract must be a regular file");
    fs.unlinkSync(name);
  }
  const contractSha256ByAutoid: Record<string, string> = {};
  const { object_kind_closed_set: _object_kind_closed_set } = require("./step_structure");
  const { step_structure_quarantine_disclosure_cn, step_structure_quarantine_error_cn } = require("../ist_core/display_lexicon");
  const objectKindsAvailable = _object_kind_closed_set() !== null;
  const criterionDisclosures: any[] = [];
  const criterionPending: any[] = [];
  const typedPending: string[] = [];
  const typedReady: string[] = [];
  const sourceStatusCounts: Record<string, number> = { complete: 0, incomplete: 0 };
  if (opts.manifest_cases !== null && opts.manifest_cases !== undefined) {
    for (const autoid of missingIds) {
      let raw: any;
      try {
        raw = _project_manifest_fallback_case(manifestCaseByAutoid[autoid], { mindmap_source_sha256: String(opts.mindmap_source_sha256 || "") });
        const normalized = normalize_contract({ ...raw }, `${autoid}.json`);
        const panel = build_warning_panel([normalized]);
        build_validation_cards([normalized], { warning_panel: panel });
      } catch (exc: any) {
        quarantined.push({
          autoid, error: "按人工脑图原文铸卡没过，本轮退回，不编写",
          reason_code: "recompose_missing_case_contract_invalid",
          detail: `${exc.constructor.name}: ${String(exc.message || exc).slice(0, 240)}`,
        });
        disclosures.push({
          autoid, code: "mindmap_gap_disclosure",
          message: "机械脑图没写到这份人工脑图，按人工脑图原文铸卡也没过，本轮退回，不编写",
          reason_code: "recompose_missing_case_contract_invalid", fallback_allowed: false,
        });
        continue;
      }
      contractSha256ByAutoid[autoid] = write_json_atomic(path.join(contractsDir, `${autoid}.json`), raw);
      written.push(autoid);
      typedPending.push(autoid);
      sourceStatusCounts.complete += 1;
      bucketCounts.step_recipe = (bucketCounts.step_recipe || 0) + 1;
      disclosures.push({
        autoid, code: "mindmap_gap_disclosure",
        message: "机械脑图没写到这份人工脑图，已按人工脑图原文出卡，本轮仍编写",
        reason_code: "recompose_missing_case", fallback_allowed: true,
      });
    }
  }
  for (const case_ of cases) {
    const autoid = String(case_.autoid || "");
    const rawBucket = case_.bucket;
    const bucket = typeof rawBucket === "string" ? rawBucket : "";
    const bucketClosed = MACHINE_MINDMAP_BUCKETS.has ? MACHINE_MINDMAP_BUCKETS.has(bucket) : MACHINE_MINDMAP_BUCKETS.includes(bucket);
    if (bucketClosed) bucketCounts[bucket] = (bucketCounts[bucket] || 0) + 1;
    const sourceStatus = _derived_source_status(case_);
    sourceStatusCounts[sourceStatus] = (sourceStatusCounts[sourceStatus] || 0) + 1;
    if (!bucketClosed) {
      quarantined.push({
        autoid, error: "机器稿作废：bucket 不在闭集内（exp_recipe / step_recipe / true_gap）",
        reason_code: "recompose_bucket_missing",
        detail: "bucket is outside the closed set: " + (bucket ? JSON.stringify(bucket.slice(0, 40)) : "absent or not a string"),
      });
      disclosures.push({
        autoid: autoid || "unknown", code: "mindmap_gap_disclosure",
        message: "机器稿没给这份用例定分类（可出配方 / 源缺口），本轮退回，不编写",
        reason_code: "recompose_bucket_missing", fallback_allowed: false,
      });
      continue;
    }
    if (autoid in criterionUnavailable) {
      const reason = String(criterionUnavailable[autoid] || "").slice(0, 300);
      quarantined.push({ autoid, error: "归类预期试了一次还是没结果，本轮退回，不编写", reason_code: "adjudication_unavailable", detail: reason });
      disclosures.push({
        autoid: autoid || "unknown", code: "adjudication_unavailable",
        message: "归类预期试了一次还是没结果。这份机械脑图本轮不出卡、不编写，其余继续。",
        reason, reason_code: "adjudication_unavailable", fallback_allowed: false,
      });
      continue;
    }
    if (autoid in structureQuarantine) {
      const codes = (structureQuarantine[autoid] || []).map(String);
      quarantined.push({ autoid, error: step_structure_quarantine_error_cn(codes), reason_code: "recompose_step_structure_invalid", detail: codes.join("、").slice(0, 300) });
      disclosures.push({
        autoid: autoid || "unknown", code: "mindmap_gap_disclosure",
        message: step_structure_quarantine_disclosure_cn(codes),
        reason_code: "recompose_step_structure_invalid", codes: codes.slice(0, 12), fallback_allowed: false,
      });
      continue;
    }
    if (autoid in quarantine) {
      const fields = quarantine[autoid].join("、");
      quarantined.push({ autoid, error: _verbatim_quarantine_error(fields), reason_code: "recompose_verbatim_mismatch", detail: fields });
      disclosures.push({
        autoid: autoid || "unknown", code: "mindmap_gap_disclosure",
        message: _verbatim_quarantine_disclosure(fields),
        reason_code: "recompose_verbatim_mismatch", fallback_allowed: false,
      });
      continue;
    }
    const caseSpecValue = specEvaluation.value;
    const caseComplete = sourceStatus === "complete";
    const outcome = classify_completeness(caseSpecValue, caseComplete);
    if (outcome === CompletenessOutcome.WAIT_SPEC_RETRY) {
      const decision: any = {
        autoid, conflict_scenario: "spec_unknown", reason_code: "spec_lookup_unknown",
        missing_fields: _decision_missing_fields(case_), options: ["retry_spec_lookup", "continue_without_spec"],
      };
      if (caseComplete) decision.defer_until_static_discovery = true;
      needsDecision.push(decision);
      disclosures.push({ ...decision, code: "mindmap_gap_disclosure", message: "规格书没查成，引擎已自动重试一次，按规格书缺失继续", terminal: false, fallback_allowed: false });
      if (!caseComplete) continue;
    }
    if (outcome === CompletenessOutcome.SCENARIO_1) {
      if (opts.mindmap_text !== null && opts.mindmap_text !== undefined
          && JSON.stringify(_source_missing_fields(case_, opts.mindmap_text)) !== JSON.stringify(_case_missing_fields(case_))) {
        quarantined.push({
          autoid, error: "说人工脑图没写完，但和人工脑图原文对不上，本轮退回，不编写",
          reason_code: "recompose_contract_invalid", detail: "source completeness differs from the recomposed case",
        });
        disclosures.push({
          autoid: autoid || "unknown", code: "mindmap_gap_disclosure",
          message: "说人工脑图没写完，但和人工脑图原文对不上，不能当成「你的人工脑图没写完」",
          reason_code: "recompose_contract_invalid", fallback_allowed: false,
        });
        continue;
      }
      const decision = { autoid, conflict_scenario: "scenario_1", reason_code: "scenario1_case_incomplete", missing_fields: _decision_missing_fields(case_), options: ["abandon_generation"] };
      needsDecision.push(decision);
      disclosures.push({ ...decision, code: "mindmap_gap_disclosure", message: "规格书在，但人工脑图的描述、步骤或预期没写完", terminal: false, fallback_allowed: false });
      continue;
    }
    if (outcome === CompletenessOutcome.SCENARIO_2) {
      const incompleteReason = _scenario2_incomplete_reason(case_, {
        governing_spec_status: scenario2SpecStatus, defect_spec_status: opts.resolved_defect_spec_status,
        defect_spec_receipt_sha256: opts.resolved_defect_spec_receipt_sha256, mindmap_text: opts.mindmap_text,
      });
      if (incompleteReason) {
        const decision = { autoid, conflict_scenario: "scenario_2", reason_code: "scenario2_incomplete_case", missing_fields: _decision_missing_fields(case_), options: ["abandon_generation"] };
        needsDecision.push(decision);
        disclosures.push({ ...decision, code: "mindmap_gap_disclosure", message: incompleteReason, terminal: false, fallback_allowed: false });
      } else {
        quarantined.push({
          autoid, error: "说来源缺席，但机械复查没过，本轮退回，不编写",
          reason_code: "recompose_contract_invalid", detail: "scenario-2 source absence did not pass source recheck",
        });
        disclosures.push({
          autoid: autoid || "unknown", code: "mindmap_gap_disclosure",
          message: "说来源缺席，但机械复查没过，不能进入放弃",
          reason_code: "recompose_contract_invalid", fallback_allowed: false,
        });
      }
      continue;
    }
    const [ok, why] = _eligible(case_, {
      mindmap_text: opts.mindmap_text ?? undefined, governing_spec: opts.resolved_governing_spec,
      spec_text: opts.spec_text, defect_spec_receipt: opts.resolved_defect_spec_receipt,
    });
    if (!ok) {
      const [invalidError, invalidMessage] = _invalid_contract_user_text(String(why));
      quarantined.push({ autoid, error: invalidError, reason_code: "recompose_contract_invalid", detail: String(why).slice(0, 300) });
      disclosures.push({
        autoid: autoid || "unknown", code: "mindmap_gap_disclosure", message: invalidMessage,
        reason_code: "recompose_contract_invalid", fallback_allowed: false,
      });
      continue;
    }
    const typedStatus = _derived_typed_assertion_status(case_);
    let raw: any;
    let caseDisclosures: any[];
    try {
      raw = _project_case(case_, {
        mindmap_source_sha256: String(opts.mindmap_source_sha256 || machineSha256),
        defect_spec_receipt: opts.resolved_defect_spec_receipt,
        mindmap_text: opts.mindmap_text ?? undefined,
        resource: (manifestCaseByAutoid[autoid] || {}).resource,
        criterion_version_family: opts.criterion_version_family || "",
        criterion_manual_version: opts.criterion_manual_version || "",
        criterion_rule_records: opts.criterion_rule_records,
      });
      const normalized = normalize_contract({ ...raw }, `${autoid}.json`);
      const panel = build_warning_panel([normalized]);
      build_validation_cards([normalized], { warning_panel: panel });
      caseDisclosures = _step_structure_disclosures(autoid, raw, { object_kinds_available: objectKindsAvailable, tiers: raw.device_disclosure || [] });
      caseDisclosures.push(..._author_algorithm_mentions_disclosures(autoid, raw));
    } catch (exc: any) {
      quarantined.push({
        autoid, error: "机械脑图没过复查，本轮退回，不编写",
        reason_code: "recompose_contract_invalid",
        detail: `${exc.constructor.name}: ${String(exc.message || exc).slice(0, 240)}`,
      });
      disclosures.push({
        autoid: autoid || "unknown", code: "mindmap_gap_disclosure", message: "机械脑图没过复查，本轮退回，不编写",
        reason_code: "recompose_contract_invalid", fallback_allowed: false,
      });
      continue;
    }
    contractSha256ByAutoid[autoid] = write_json_atomic(path.join(contractsDir, `${autoid}.json`), raw);
    disclosures.push(...caseDisclosures);
    for (const item of raw.expectations || []) {
      if (!item || typeof item !== "object") continue;
      const normalizedClaim = item.normalized_claim;
      if (!normalizedClaim || typeof normalizedClaim !== "object") continue;
      const status = String(normalizedClaim.status || "unmatched");
      const disclosure = {
        autoid, code: "criterion_normalization_disclosure",
        message: _criterion_disclosure_message(normalizedClaim),
        expectation_id: String(normalizedClaim.expectation_id || ""),
        shape_key: String(normalizedClaim.shape_key || ""),
        version_family: String(normalizedClaim.version_family || ""),
        algorithm_classes: [...(normalizedClaim.algorithm_classes || [])],
        status,
        criterion_type: normalizedClaim.criterion_type,
        rule_id: normalizedClaim.rule_id,
        authored_step: normalizedClaim.authored_step,
        authored_step_cause: normalizedClaim.authored_step_cause,
        source_span: normalizedClaim.source_span,
        evidence_chain: normalizedClaim.evidence_chain,
        rule_identity: normalizedClaim.rule_identity,
        author_veto: normalizedClaim.author_veto,
        supersede_cause: normalizedClaim.supersede_cause,
        mode: normalizedClaim.mode,
        fixture_policy: normalizedClaim.fixture_policy,
      };
      criterionDisclosures.push(disclosure);
      disclosures.push(disclosure);
      if (status !== "matched") {
        criterionPending.push({ ...disclosure, original_text: String(item.text || ""), semantic_key: String(normalizedClaim.semantic_key || "") });
      }
    }
    if (bucket === "true_gap") {
      disclosures.push({
        autoid: autoid || "unknown", code: "true_gap_card_bucket_disclosure",
        message: "机器稿把这份用例判为没有可用判据，出卡按「判据来自步骤」处理，请据作者原文核对",
        reason_code: "true_gap_card_bucket", fallback_allowed: true,
      });
    }
    disclosures.push(..._enhancement_disclosures_for_case(case_));
    written.push(autoid);
    (typedStatus === "pending" ? typedPending : typedReady).push(autoid);
  }
  if (opts.mindmap_text !== null && opts.mindmap_text !== undefined) {
    disclosures.push(..._verbatim_duplicate_disclosures(opts.mindmap_text));
  }
  if (!written.length) {
    try {
      fs.rmdirSync(contractsDir);
    } catch {}
  }
  const abandoned: string[] = [];
  for (const item of quarantined) {
    if (!("reason_code" in item)) item.reason_code = "recompose_contract_invalid";
    if (!("detail" in item)) item.detail = "";
    if (!("user_message" in item)) item.user_message = String(item.error || "");
  }
  const specValue = specEvaluation.value;
  const summary: any = {
    source: path.basename(mmPath),
    machine_mindmap_sha256: machineSha256,
    written,
    abandoned,
    needs_decision: needsDecision,
    spec_value: specValue && specValue.value !== undefined ? specValue.value : specValue,
    spec_reason: specEvaluation.reason,
    disclosures,
    quarantined,
    bucket_counts: bucketCounts,
    source_status_counts: sourceStatusCounts,
    typed_pending: typedPending,
    typed_ready: typedReady,
    provisional_spec_unknown_autoids: [...new Set(needsDecision.filter((item: any) => item.defer_until_static_discovery === true && written.includes(String(item.autoid || ""))).map((item: any) => String(item.autoid || "")))].sort(),
    contract_sha256_by_autoid: contractSha256ByAutoid,
    criterion_disclosures: criterionDisclosures,
    criterion_pending: criterionPending,
  };
  const disclosureSha256 = write_json_atomic(sidecarPath, _sealed_disclosure_payload({
    schema: "ist.mindmap.disclosures",
    machine_mindmap_sha256: machineSha256,
    written_autoids: written,
    contract_sha256_by_autoid: contractSha256ByAutoid,
    items: disclosures,
    quarantined,
  }, contractSha256ByAutoid));
  summary.disclosure_sha256 = disclosureSha256;
  return summary;
}

function _index_contract_claims(raw: Buffer, autoid: string, index: Map<string, any>): string {
  try {
    validate_json_budget(raw, { errorType: MachineMindmapError, message: "machine contract exceeds the JSON structure budget", maxTokens: _PROJECTION_JSON_MAX_TOKENS, maxDepth: _PROJECTION_JSON_MAX_DEPTH });
  } catch (exc) {
    if (exc instanceof MachineMindmapError) return "structure_budget_exceeded";
    throw exc;
  }
  let contract: any;
  try {
    contract = JSON.parse(raw.toString("utf8"));
  } catch {
    return "json_invalid";
  }
  if (!contract || typeof contract !== "object" || Array.isArray(contract)) return "json_invalid";
  for (const item of contract.expectations || []) {
    const claim = item && typeof item === "object" ? item.normalized_claim : null;
    if (!claim || typeof claim !== "object") continue;
    const expectationId = String(claim.expectation_id || "");
    if (!expectationId) continue;
    const key = `${autoid}${expectationId}`;
    if (index.has(key)) return "ref_invalid";
    index.set(key, claim);
  }
  return "";
}

function _restore_disclosure_refs(items: any[], index: Map<string, any>): [any[] | null, string] {
  const restored: any[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      restored.push(item);
      continue;
    }
    const present = _DISCLOSURE_REF_FIELDS.filter((field) => field in item);
    const refs = present.filter((field) => _is_disclosure_ref(item[field]));
    if (!refs.length) {
      restored.push(item);
      continue;
    }
    if (refs.length !== present.length) return [null, "ref_invalid"];
    const keys = new Set(refs.map((field) => `${item[field].autoid}${item[field].expectation_id}`));
    if (keys.size !== 1) return [null, "ref_invalid"];
    const key = [...keys][0];
    if (key.split("")[0] !== String(item.autoid || "")) return [null, "ref_invalid"];
    const claim = index.get(key);
    if (claim === undefined) return [null, "ref_invalid"];
    const out: any = {};
    for (const [field, value] of Object.entries(item)) {
      out[field] = refs.includes(field) ? claim[field] : value;
    }
    restored.push(out);
  }
  return [restored, ""];
}

function _projection_load(batchDir: string, receipt: any): any {
  const limits = { max_bytes: _PROJECTION_JSON_MAX_BYTES, maxTokens: _PROJECTION_JSON_MAX_TOKENS, maxDepth: _PROJECTION_JSON_MAX_DEPTH };
  const fail = (reason: string, diagnostic: any = {}) => ({ payload: null, reason, diagnostic });
  if (!receipt || typeof receipt !== "object" || receipt.ev !== "recompose_done") {
    return fail("digest_mismatch");
  }
  const sidecarPath = path.join(String(batchDir), MACHINE_MINDMAP_DISCLOSURES_SIDECAR_NAME);
  let probeIdentity: any;
  try {
    probeIdentity = stat_regular_nofollow(sidecarPath, {
      errorType: MachineMindmapError,
      invalid_message: "projection receipt path is invalid",
      directory_message: "projection receipt directory is unavailable",
      open_message: "projection receipt is unavailable",
      bounds_message: "projection receipt is not a sealed regular file",
      min_bytes: 1,
    });
  } catch {
    return fail("sealed_read_failed");
  }
  const measuredBytes = Number(probeIdentity[2]);
  if (measuredBytes > _PROJECTION_JSON_MAX_BYTES) {
    return fail("bytes_over_limit", { bytes: measuredBytes, max_bytes: _PROJECTION_JSON_MAX_BYTES });
  }
  let encoded: Buffer;
  let sidecarIdentity: any;
  try {
    const encodedResult = read_regular_nofollow(sidecarPath, {
      errorType: MachineMindmapError,
      invalid_message: "projection receipt path is invalid",
      directory_message: "projection receipt directory is unavailable",
      open_message: "projection receipt is unavailable",
      bounds_message: "projection receipt exceeds its sealed size boundary",
      changed_message: "projection receipt changed while being read",
      max_bytes: _PROJECTION_JSON_MAX_BYTES,
      min_bytes: 1,
      return_identity: true,
    }) as [Buffer, any];
    [encoded, sidecarIdentity] = encodedResult;
  } catch {
    return fail("sealed_read_failed");
  }
  const [tokens, depth] = scan_json_budget(encoded);
  const measured: any = { bytes: encoded.length, tokens, depth, ...limits };
  if (tokens > _PROJECTION_JSON_MAX_TOKENS || depth > _PROJECTION_JSON_MAX_DEPTH) {
    return fail("structure_budget_exceeded", measured);
  }
  let payload: any;
  try {
    payload = JSON.parse(encoded.toString("utf8"));
  } catch {
    return fail("json_invalid", measured);
  }
  const expectedContracts = receipt.contract_sha256_by_autoid;
  if (!payload || typeof payload !== "object" || !expectedContracts || typeof expectedContracts !== "object") {
    return fail("digest_mismatch", measured);
  }
  const written = (receipt.written_autoids || []).map(String);
  if (!accepts_schema(payload.schema, "ist.mindmap.disclosures") || sha256_bytes(encoded) !== receipt.disclosure_sha256
      || payload.machine_mindmap_sha256 !== receipt.machine_mindmap_sha256
      || JSON.stringify(payload.written_autoids) !== JSON.stringify(written)
      || JSON.stringify(payload.contract_sha256_by_autoid) !== JSON.stringify(expectedContracts)
      || JSON.stringify(Object.keys(expectedContracts).sort()) !== JSON.stringify([...written].sort())) {
    return fail("digest_mismatch", measured);
  }
  const storageFormat = payload.storage_format;
  if (storageFormat !== null && storageFormat !== undefined && storageFormat !== DISCLOSURE_STORAGE_CONTRACT_REFS) {
    return fail("ref_invalid", measured);
  }
  const storesRefs = storageFormat === DISCLOSURE_STORAGE_CONTRACT_REFS;
  const payloadItems = payload.items;
  if (!storesRefs && Array.isArray(payloadItems) && payloadItems.some((item: any) =>
    item && typeof item === "object" && _DISCLOSURE_REF_FIELDS.some((field) => _is_disclosure_ref(item[field])))) {
    return fail("ref_invalid", measured);
  }
  const claimIndex = new Map<string, any>();
  const contractIdentities: Record<string, any> = {};
  const contractsDir = path.join(String(batchDir), "contracts");
  if (Object.keys(expectedContracts).length || fs.existsSync(contractsDir)) {
    try {
      for (const [autoid, expectedSha] of Object.entries<string>(expectedContracts)) {
        if (!new RegExp(`^${_LOCATOR_TOKEN}$`).test(String(autoid))) {
          return fail("digest_mismatch", measured);
        }
        const contractResult = read_regular_at_nofollow(contractsDir, `${autoid}.json`, {
          errorType: MachineMindmapError,
          open_message: "machine contract is unavailable",
          bounds_message: "machine contract exceeds its sealed size boundary",
          changed_message: "machine contract changed while being read",
          max_bytes: CONTRACT_CARD_MAX_BYTES,
          min_bytes: 1,
          return_identity: true,
        }) as [Buffer, any];
        const [raw, contractIdentity] = contractResult;
        if (sha256_bytes(raw) !== expectedSha) return fail("digest_mismatch", measured);
        contractIdentities[String(autoid)] = contractIdentity;
        if (storesRefs) {
          const failure = _index_contract_claims(raw, String(autoid), claimIndex);
          if (failure) return fail(failure, measured);
        }
      }
      for (const name of fs.readdirSync(contractsDir)) {
        if (!name.endsWith(".json") || name.slice(0, -5) in expectedContracts) continue;
        try {
          const raw = read_regular_at_nofollow(contractsDir, name, {
            errorType: MachineMindmapError,
            open_message: "contract is unavailable",
            bounds_message: "contract exceeds its sealed size boundary",
            changed_message: "contract changed while being read",
            max_bytes: CONTRACT_CARD_MAX_BYTES,
            min_bytes: 1,
          }) as Buffer;
          validate_json_budget(raw, { errorType: MachineMindmapError, message: "contract exceeds the JSON structure budget", maxTokens: _PROJECTION_JSON_MAX_TOKENS, maxDepth: _PROJECTION_JSON_MAX_DEPTH });
          const other = JSON.parse(raw.toString("utf8"));
          if (other && typeof other === "object" && other.contract_class === "mindmap_verbatim") {
            return fail("digest_mismatch", measured);
          }
        } catch {
          continue;
        }
      }
    } catch {
      return fail("sealed_read_failed", measured);
    }
  }
  let currentIdentity: any;
  try {
    currentIdentity = stat_regular_nofollow(sidecarPath, {
      errorType: MachineMindmapError,
      invalid_message: "projection receipt path is invalid",
      directory_message: "projection receipt directory is unavailable",
      open_message: "projection receipt is unavailable",
      bounds_message: "projection receipt exceeds its sealed size boundary",
      max_bytes: _PROJECTION_JSON_MAX_BYTES,
      min_bytes: 1,
    });
  } catch {
    return fail("sealed_read_failed");
  }
  if (JSON.stringify(currentIdentity) !== JSON.stringify(sidecarIdentity)) {
    return fail("digest_mismatch", measured);
  }
  let finalPayload = payload;
  if (storesRefs) {
    if (!Array.isArray(payloadItems)) return fail("ref_invalid", measured);
    const [restored, failure] = _restore_disclosure_refs(payloadItems, claimIndex);
    if (failure) return fail(failure, measured);
    finalPayload = { ...payload, items: restored };
  }
  return { payload: finalPayload, reason: "", diagnostic: measured, sidecar_identity: sidecarIdentity, contract_identities: contractIdentities };
}

function _projection_payload(batchDir: string, receipt: any): any | null {
  return _projection_load(path.resolve(String(batchDir)), receipt).payload;
}

export function projection_receipt_valid(batchDir: string, receipt: any): boolean {
  return _projection_payload(path.resolve(String(batchDir)), receipt) !== null;
}

export function load_disclosure_projection(batchDir: string, receipt?: any): any {
  const result = _projection_load(path.resolve(String(batchDir)), receipt || {});
  const payload = result.payload;
  if (payload === null) {
    return { schema: DISCLOSURE_LOAD_SCHEMA, status: "invalid", items: [], reason: result.reason, diagnostic: { ...result.diagnostic }, sidecar_identity: null, contract_identities: {} };
  }
  const items = payload.items;
  if (!Array.isArray(items) || items.some((item: any) => !item || typeof item !== "object")) {
    return { schema: DISCLOSURE_LOAD_SCHEMA, status: "invalid", items: [], reason: "json_invalid", diagnostic: { ...result.diagnostic }, sidecar_identity: null, contract_identities: {} };
  }
  return { schema: DISCLOSURE_LOAD_SCHEMA, status: "valid", items: items.map((item: any) => ({ ...item })), sidecar_identity: result.sidecar_identity, contract_identities: { ...(result.contract_identities || {}) } };
}

export function load_disclosure_items_status(batchDir: string, receipt?: any): any {
  const record = load_disclosure_projection(batchDir, receipt);
  if (record.status !== "valid") {
    return { schema: DISCLOSURE_LOAD_SCHEMA, status: "invalid", items: [], reason: record.reason, diagnostic: { ...record.diagnostic } };
  }
  return { schema: DISCLOSURE_LOAD_SCHEMA, status: "valid", items: [...record.items] };
}

export function load_disclosure_items(batchDir: string, receipt?: any): any[] {
  const result = load_disclosure_items_status(batchDir, receipt);
  return result.status === "valid" ? [...result.items] : [];
}
