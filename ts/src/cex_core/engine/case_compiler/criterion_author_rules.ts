import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import {
  MAX_BEHAVIOUR_CLASS_CHARS,
  MAX_BEHAVIOUR_CLASSES,
  MAX_METHOD_CHARS,
  MAX_OBJECT_KIND_CHARS,
  MAX_PARAGRAPH_CHARS,
  MAX_SOURCE_PATH_CHARS,
} from "./behaviour_classes";
import { restore_endpoint_encodings } from "../common/nullable_scalar";
import { runtime_path } from "../common/runtime_paths";
import { accepts_schema } from "../common/schema_identity";
import { acquireLockSync } from "../../../platform/index";

const logger = console;

export const ENGINE_RULE_SCHEMA = "ist.criterion-engine-rule";
export const AUTHOR_RULE_SCHEMA = "ist.criterion-author-rule";
export const ADJUDICATION_BRIEF_SCHEMA = "ist.criterion-engine-adjudication-brief";
export const AUTHOR_RULE_PATH = runtime_path("criterion_author_rules.jsonl");
export const VETO_ANSWER = "否决并重裁";

export class CriterionAuthorRuleError extends Error {}

export interface BehaviourClassification {
  method: string;
  object_kind: string;
  behaviour_class: string;
  source_path: string;
  quote: string;
}

const _BEHAVIOUR_CLASS_FIELDS: [string, number][] = [
  ["method", MAX_METHOD_CHARS],
  ["object_kind", MAX_OBJECT_KIND_CHARS],
  ["behaviour_class", MAX_BEHAVIOUR_CLASS_CHARS],
  ["source_path", MAX_SOURCE_PATH_CHARS],
  ["quote", MAX_PARAGRAPH_CHARS],
];

function _validateBehaviourClassification(data: any): BehaviourClassification {
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new CriterionAuthorRuleError("invalid behaviour classification");
  for (const [key, limit] of _BEHAVIOUR_CLASS_FIELDS) {
    const value = data[key];
    if (typeof value !== "string" || value.length > limit) throw new CriterionAuthorRuleError(`behaviour classification field ${key} is invalid`);
    if (key !== "object_kind" && value.length < 1) throw new CriterionAuthorRuleError(`behaviour classification field ${key} is required`);
  }
  const allowed = new Set(["method", "object_kind", "behaviour_class", "source_path", "quote"]);
  for (const key of Object.keys(data)) {
    if (!allowed.has(key)) throw new CriterionAuthorRuleError("behaviour classification has extra fields");
  }
  return { method: data.method, object_kind: data.object_kind, behaviour_class: data.behaviour_class, source_path: data.source_path, quote: data.quote };
}

export interface CriterionAdjudicationResult {
  criterion_type: string;
  rationale: string;
  disclosure: string;
  manual_anchor_ids?: string[] | null;
  tree_context_ids?: string[] | null;
  behaviour_classes?: BehaviourClassification[] | null;
}

function _validateCriterionAdjudicationResult(data: any): CriterionAdjudicationResult {
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  const allowed = new Set(["criterion_type", "rationale", "disclosure", "manual_anchor_ids", "tree_context_ids", "behaviour_classes"]);
  for (const key of Object.keys(data)) {
    if (!allowed.has(key)) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  }
  if (typeof data.criterion_type !== "string" || data.criterion_type.length < 1 || data.criterion_type.length > 128) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  if (typeof data.rationale !== "string" || data.rationale.length < 1 || data.rationale.length > 8192) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  if (typeof data.disclosure !== "string" || data.disclosure.length < 1 || data.disclosure.length > 8192) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  if (data.manual_anchor_ids !== undefined && data.manual_anchor_ids !== null) {
    if (!Array.isArray(data.manual_anchor_ids) || data.manual_anchor_ids.length > 256 || !data.manual_anchor_ids.every((v: any) => typeof v === "string")) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  }
  if (data.tree_context_ids !== undefined && data.tree_context_ids !== null) {
    if (!Array.isArray(data.tree_context_ids) || data.tree_context_ids.length > 256 || !data.tree_context_ids.every((v: any) => typeof v === "string")) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
  }
  let behaviourClasses: BehaviourClassification[] | null = null;
  if (data.behaviour_classes !== undefined && data.behaviour_classes !== null) {
    if (!Array.isArray(data.behaviour_classes)) throw new CriterionAuthorRuleError("criterion structured response failed schema validation");
    const kept: BehaviourClassification[] = [];
    for (const item of data.behaviour_classes) {
      try {
        kept.push(_validateBehaviourClassification(item));
      } catch {
        continue;
      }
    }
    behaviourClasses = kept.slice(0, MAX_BEHAVIOUR_CLASSES);
  }
  return {
    criterion_type: data.criterion_type,
    rationale: data.rationale,
    disclosure: data.disclosure,
    manual_anchor_ids: data.manual_anchor_ids ?? null,
    tree_context_ids: data.tree_context_ids ?? null,
    behaviour_classes: behaviourClasses,
  };
}

export function render_criterion_adjudication_result(value: any): string {
  if (typeof value === "string") {
    value = _loadCriterionJudgmentObject(value);
  }
  const parsed = _validateCriterionAdjudicationResult(restore_endpoint_encodings(value, {}));
  return JSON.stringify(Object.fromEntries(Object.entries(parsed).filter(([_, v]) => v !== undefined && v !== null)));
}

function _sha256(value: any): string {
  return crypto.createHash("sha256").update(JSON.stringify(value, Object.keys(value).sort(), 0)).digest("hex");
}

function _identityPreview(value: any): string {
  if (value instanceof Set) value = Array.from(value).sort();
  const structured = Array.isArray(value) || (value !== null && typeof value === "object");
  let raw: string;
  if (structured) {
    raw = JSON.stringify(value, (_, v) => (typeof v === "object" && v !== null ? v : String(v)), 0);
  } else {
    raw = String(value ?? "<missing>");
  }
  const safe = Array.from(raw).map((ch) => (ch.codePointAt(0)! >= 32 && ch.codePointAt(0)! !== 127 ? ch : `\\u${ch.codePointAt(0)!.toString(16).padStart(4, "0")}`)).join("");
  if (re_full_sha(safe)) return `${safe.slice(0, 12)}…${safe.slice(-8)}`;
  if (safe.length > 160) return safe.slice(0, 120) + "…" + safe.slice(-24);
  return structured ? safe : JSON.stringify(safe);
}

function _raiseIdentityDrift(key: string, opts: { expected: any; actual: any }): never {
  throw new CriterionAuthorRuleError(`criterion adjudication identity drift: key=${key}; expected=${_identityPreview(opts.expected)}; actual=${_identityPreview(opts.actual)}`);
}

function _raiseEvidenceGap(key: string, opts: { expected: any; actual: any }): never {
  throw new CriterionAuthorRuleError(`criterion adjudication evidence chain is incomplete: key=${key}; expected=${_identityPreview(opts.expected)}; actual=${_identityPreview(opts.actual)}`);
}

export function re_full_sha(value: any): boolean {
  return /^[0-9a-f]{64}$/.test(String(value ?? ""));
}

export function resolve_compile_manual_version(opts: { full_version?: string; device_build?: string } = {}): string {
  let _manualVersionFromFullVersion: (v: string) => string;
  try {
    _manualVersionFromFullVersion = require("../ist_core/tools/device/emit_xlsx_tool")._manual_version_from_full_version;
  } catch {
    return "";
  }
  for (const candidate of [opts.full_version ?? "", opts.device_build ?? ""]) {
    const version = _manualVersionFromFullVersion(String(candidate ?? ""));
    if (version) return version;
  }
  try {
    const session = require("../ist_core/worker_device_context").current_worker_device_session();
    if (session) {
      const version = _manualVersionFromFullVersion(String(session?.capability_full_version ?? ""));
      if (version) return version;
    }
  } catch {}
  try {
    const buildIdentity = require("./vendor_stdlib").configured_device_os_build_identity();
    return _manualVersionFromFullVersion(buildIdentity);
  } catch {
    return "";
  }
}

function _manualAnchorId(anchor: Record<string, any>): string {
  const material = {
    source_path: String(anchor?.["source_path"] ?? ""),
    source_sha256: String(anchor?.["source_sha256"] ?? ""),
    source_span: anchor?.["source_span"],
    quote: String(anchor?.["quote"] ?? ""),
  };
  return "manual:" + _sha256(material).slice(0, 24);
}

function _ruleHasReusePins(record: Record<string, any>): boolean {
  if (!String(record?.["manual_version"] ?? "")) return false;
  if (record?.["pin_failures"]) return false;
  const anchorPins = record?.["anchor_chapter_shas"];
  const catalogPins = record?.["catalog_pins"];
  return Boolean(anchorPins && typeof anchorPins === "object" && !Array.isArray(anchorPins) && Object.keys(anchorPins).length && catalogPins && typeof catalogPins === "object" && !Array.isArray(catalogPins) && Object.keys(catalogPins).length);
}

function _familiesFromAnchors(anchors: Record<string, any>[]): Set<string> {
  const families = new Set<string>();
  for (const anchor of anchors) {
    if (!anchor || typeof anchor !== "object" || Array.isArray(anchor)) continue;
    const normalized = String(anchor?.["source_path"] ?? "").replace(/\\/g, "/");
    const match = /\/manual\/[^/]+\/(cli|app)_cn\.md$/.exec(normalized);
    if (match) families.add(match[1]);
  }
  return families;
}

function _catalogPins(manualVersion: string, families: Set<string>, opts: { root?: string } = {}): Record<string, Record<string, string>> {
  const { load_catalog_status } = require("../kms/manual_catalog_store");
  const pins: Record<string, Record<string, string>> = {};
  for (const family of Array.from(families).sort()) {
    if (!["cli", "app"].includes(family)) continue;
    const verdict = load_catalog_status(manualVersion, family, { root: opts.root });
    pins[family] = { catalog_sha256: String(verdict?.["catalog_sha256"] ?? "") };
  }
  return pins;
}

function _ruleReusable(record: Record<string, any>, opts: { manual_version: string; root?: string }): boolean {
  if (!_ruleHasReusePins(record)) return false;
  if (String(record?.["manual_version"] ?? "") !== String(opts.manual_version ?? "")) return false;
  const identity = record?.["identity"];
  const evidence = identity && typeof identity === "object" && !Array.isArray(identity) ? identity["evidence_chain"] : null;
  const anchors = evidence && typeof evidence === "object" && !Array.isArray(evidence) ? evidence["manual_anchors"] : null;
  if (!Array.isArray(anchors) || !anchors.length) return false;
  let liveAnchorPins: Record<string, Record<string, string>>;
  try {
    const { anchor_chapter_pins } = require("../kms/manual_chapter_locator");
    liveAnchorPins = anchor_chapter_pins(anchors, { manual_version: opts.manual_version, root: opts.root });
  } catch {
    return false;
  }
  return JSON.stringify(record?.["anchor_chapter_shas"] ?? {}) === JSON.stringify(liveAnchorPins);
}

export const SUPERSEDE_CAUSES = ["author_veto", "manual_section_changed", "prior_not_verifiable"] as const;

export function supersede_cause(prior: Record<string, any>, opts: { veto: Record<string, any> | null; manual_version: string }): string {
  if (opts.veto !== null) return "author_veto";
  if (!_ruleHasReusePins(prior)) return "prior_not_verifiable";
  void opts.manual_version;
  return "manual_section_changed";
}

export function round_rule_supply(active: Record<string, Record<string, any>>, records: Record<string, any>[], opts: { manual_version: string }): Record<string, Record<string, any>> {
  const supply: Record<string, Record<string, any>> = {};
  for (const [key, value] of Object.entries(active)) {
    supply[key] = { ...value };
  }
  for (const record of records) {
    if (!record || typeof record !== "object" || Array.isArray(record)) continue;
    const shapeKey = String(record?.["shape_key"] ?? "");
    if (!shapeKey) continue;
    const pinned = String(record?.["manual_version"] ?? "");
    const version = pinned || String(opts.manual_version ?? "") || String(record?.["version_family"] ?? "");
    supply[`${shapeKey},${version}`] = { ...record };
  }
  return supply;
}

function _rejectDuplicateKeys(pairs: [string, any][]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [key, value] of pairs) {
    if (key in out) throw new Error(`duplicate JSON key: ${key}`);
    out[key] = value;
  }
  return out;
}

function _engineRecordValid(record: any): boolean {
  if (!record || typeof record !== "object" || Array.isArray(record) || !accepts_schema(record["schema"], ENGINE_RULE_SCHEMA)) return false;
  const body: Record<string, any> = Object.fromEntries(Object.entries(record as Record<string, any>).filter(([k]) => k !== "rule_sha256"));
  const identity: Record<string, any> | null = body["identity"];
  const output: Record<string, any> | null = body["output"];
  const evidence = identity && typeof identity === "object" && !Array.isArray(identity) ? identity["evidence_chain"] : null;
  return Boolean(
    re_full_sha(body["shape_key"]) &&
      String(body["version_family"] ?? "") &&
      typeof body["generation"] === "number" &&
      Number.isInteger(body["generation"]) &&
      body["generation"] >= 1 &&
      output &&
      typeof output === "object" &&
      !Array.isArray(output) &&
      JSON.stringify(Object.keys(output).sort()) === JSON.stringify(["criterion_type", "mode"]) &&
      String(output["criterion_type"] ?? "") &&
      output["mode"] === "direct" &&
      identity &&
      typeof identity === "object" &&
      !Array.isArray(identity) &&
      JSON.stringify(Object.keys(identity).sort()) === JSON.stringify(["adjudicator", "brief_sha256", "decision_sha256", "evidence_chain", "kind"]) &&
      identity["kind"] === "engine_adjudication" &&
      identity["adjudicator"] === "criterion-adjudicator" &&
      re_full_sha(identity["brief_sha256"]) &&
      re_full_sha(identity["decision_sha256"]) &&
      evidence &&
      typeof evidence === "object" &&
      !Array.isArray(evidence) &&
      JSON.stringify(Object.keys(evidence).sort()) === JSON.stringify(["language", "manual_anchors", "tree_context"]) &&
      Array.isArray(evidence["manual_anchors"]) &&
      evidence["manual_anchors"].length &&
      Array.isArray(evidence["tree_context"]) &&
      evidence["tree_context"].length &&
      evidence["language"] &&
      typeof evidence["language"] === "object" &&
      !Array.isArray(evidence["language"]) &&
      String(record["rule_sha256"] ?? "") === _sha256(body)
  );
}

function _ruleHistory(filePath: string): Record<string, any>[] {
  let handle: number;
  try {
    handle = fs.openSync(filePath, "r");
  } catch {
    return [];
  }
  const rows: Record<string, any>[] = [];
  try {
    const buffer = Buffer.alloc(1024 * 1024);
    let position = 0;
    let chunk = "";
    while (true) {
      const bytesRead = fs.readSync(handle, buffer, 0, buffer.length, position);
      if (bytesRead <= 0) break;
      position += bytesRead;
      chunk += buffer.toString("utf8", 0, bytesRead);
      const lines = chunk.split("\n");
      chunk = lines.pop() ?? "";
      for (const raw of lines) {
        try {
          const item = JSON.parse(raw);
          if (_engineRecordValid(item)) rows.push(item);
        } catch {
          continue;
        }
      }
    }
    if (chunk.trim()) {
      try {
        const item = JSON.parse(chunk);
        if (_engineRecordValid(item)) rows.push(item);
      } catch {}
    }
  } finally {
    fs.closeSync(handle);
  }
  return rows;
}

export function build_criterion_veto_question(record: Record<string, any>): Record<string, any> {
  if (!_engineRecordValid({ ...record })) throw new CriterionAuthorRuleError("criterion veto target is not a valid engine rule");
  const material = { schema: "ist.criterion-engine-veto", shape_key: String(record["shape_key"]), version_family: String(record["version_family"]), rule_sha256: String(record["rule_sha256"]) };
  const answerKey = _sha256(material);
  return {
    question: `是否否决这条已披露的引擎判据裁定，并在下次同键编译时重新裁定？裁定规则：${String(record?.["rule_id"] ?? "")}`,
    header: "判据事后否决",
    options: [{ label: VETO_ANSWER, description: "废止这一代裁定；下次同 shape/version 由引擎重新取证裁定。" }],
    multiSelect: false,
    _allow_other: false,
    _answer_key: answerKey,
    _veto_material: material,
  };
}

function _vetoReceipt(record: Record<string, any>, opts: { answer_path?: string } = {}): Record<string, any> | null {
  let _engineQuestionDigest: (q: Record<string, any>) => string;
  try {
    _engineQuestionDigest = require("../ist_core/tools/ask_user")._engine_question_digest;
  } catch {
    return null;
  }
  const question = build_criterion_veto_question(record);
  const answerKey = String(question["_answer_key"]);
  const digest = _engineQuestionDigest(question);
  if (!digest) return null;
  const filePath = opts.answer_path ?? runtime_path("ask_user_answers.jsonl");
  let handle: number;
  try {
    handle = fs.openSync(filePath, "r");
  } catch {
    return null;
  }
  const createdAt = Number(record?.["created_at"] ?? 0);
  let found: Record<string, any> | null = null;
  try {
    const buffer = Buffer.alloc(1024 * 1024);
    let position = 0;
    let chunk = "";
    while (true) {
      const bytesRead = fs.readSync(handle, buffer, 0, buffer.length, position);
      if (bytesRead <= 0) break;
      position += bytesRead;
      chunk += buffer.toString("utf8", 0, bytesRead);
      const lines = chunk.split("\n");
      chunk = lines.pop() ?? "";
      for (const raw of lines) {
        try {
          const item = JSON.parse(raw);
          if (!item || typeof item !== "object" || Array.isArray(item) || !accepts_schema(item["schema"], "ist.ask_user.answer")) continue;
          if (Number(item["ts"] ?? 0) < createdAt) continue;
          for (const binding of item["answer_bindings"] ?? []) {
            if (!binding || typeof binding !== "object" || Array.isArray(binding)) continue;
            if (String(binding["answer_key"] ?? "") === answerKey && String(binding["question_digest"] ?? "") === digest && String(binding["answer"] ?? "") === VETO_ANSWER) {
              found = {
                answer_key: answerKey,
                question_digest: digest,
                question_id: String(item["question_id"] ?? ""),
                ts: Number(item["ts"] ?? 0),
                receipt_sha256: _sha256({ schema: item["schema"], question_id: item["question_id"], ts: item["ts"], binding }),
              };
            }
          }
        } catch {
          continue;
        }
      }
    }
  } finally {
    fs.closeSync(handle);
  }
  return found;
}

const _HISTORY_STATE_CACHE = new Map<string, [any, Record<string, Record<string, any>>, Record<string, Record<string, any>[]>]>();
const _HISTORY_STATE_CACHE_MAX = 8;

function _ledgerIdentity(filePath: string): [number, number, number, number, number, number] | [] {
  try {
    const info = fs.lstatSync(filePath);
    return [Number(info.mode), Number(info.dev), Number(info.ino), Number(info.size), Number(info.mtimeMs), Number(info.ctimeMs)];
  } catch {
    return [];
  }
}

function _manualPinIdentity(manualVersion: string | null): any[] {
  if (!manualVersion) return [];
  try {
    const { manual_identity } = require("../kms/manual_catalog_store");
    return [manual_identity(String(manualVersion), "app"), manual_identity(String(manualVersion), "cli")];
  } catch {
    return [];
  }
}

export function clear_author_rule_cache(): void {
  try {
    const { clear_bounded } = require("../kms/manual_catalog_store");
    clear_bounded(_HISTORY_STATE_CACHE);
  } catch {
    _HISTORY_STATE_CACHE.clear();
  }
}

function _historyState(opts: { path: string; answer_path?: string; manual_version?: string | null }): [Record<string, Record<string, any>>, Record<string, Record<string, any>[]>] {
  const answers = opts.answer_path ?? runtime_path("ask_user_answers.jsonl");
  const cacheKey = JSON.stringify([opts.path, answers, String(opts.manual_version ?? "")]);
  const identity = [_ledgerIdentity(opts.path), _ledgerIdentity(answers), _manualPinIdentity(opts.manual_version ?? null)];
  const cached = _HISTORY_STATE_CACHE.get(cacheKey);
  if (cached && JSON.stringify(cached[0]) === JSON.stringify(identity)) {
    return _copyHistoryState(cached[1], cached[2]);
  }
  const [active, history] = _computeHistoryState(opts);
  if (JSON.stringify([_ledgerIdentity(opts.path), _ledgerIdentity(answers), _manualPinIdentity(opts.manual_version ?? null)]) === JSON.stringify(identity)) {
    try {
      const { remember_bounded } = require("../kms/manual_catalog_store");
      remember_bounded(_HISTORY_STATE_CACHE, cacheKey, [identity, { ...active }, { ...history }], { limit: _HISTORY_STATE_CACHE_MAX });
    } catch {}
  }
  return _copyHistoryState(active, history);
}

function _copyHistoryState(active: Record<string, Record<string, any>>, history: Record<string, Record<string, any>[]>): [Record<string, Record<string, any>>, Record<string, Record<string, any>[]>] {
  return [
    Object.fromEntries(Object.entries(active).map(([k, v]) => [k, { ...v }])),
    Object.fromEntries(Object.entries(history).map(([k, v]) => [k, v.map((r) => ({ ...r }))])),
  ];
}

function _computeHistoryState(opts: { path: string; answer_path?: string; manual_version?: string | null }): [Record<string, Record<string, any>>, Record<string, Record<string, any>[]>] {
  const history: Record<string, Record<string, any>[]> = {};
  for (const record of _ruleHistory(opts.path)) {
    const pinnedVersion = String(record?.["manual_version"] ?? "");
    let key: string;
    if (pinnedVersion && _ruleHasReusePins(record)) {
      key = `${String(record["shape_key"])},${pinnedVersion}`;
    } else {
      key = `${String(record["shape_key"])},${String(record["version_family"])}`;
    }
    if (!history[key]) history[key] = [];
    history[key].push(record);
  }
  const active: Record<string, Record<string, any>> = {};
  for (const [key, records] of Object.entries(history)) {
    records.sort((a, b) => Number(a?.["generation"] ?? 0) - Number(b?.["generation"] ?? 0));
    const latest = records[records.length - 1];
    if (_vetoReceipt(latest, { answer_path: opts.answer_path }) !== null) continue;
    if (opts.manual_version !== null && opts.manual_version !== undefined) {
      if (key.split(",")[1] !== opts.manual_version) continue;
      if (!_ruleReusable(latest, { manual_version: opts.manual_version })) continue;
    } else if (!_ruleHasReusePins(latest)) {
      continue;
    }
    active[key] = latest;
  }
  return [active, history];
}

export function load_author_rules(opts: { path?: string; verify_credential?: boolean; answer_path?: string; manual_version?: string | null } = {}): Record<string, Record<string, any>> {
  void opts.verify_credential;
  const resolvedManualVersion = String(opts.manual_version ?? resolve_compile_manual_version() ?? "");
  const [active] = _historyState({ path: opts.path ?? AUTHOR_RULE_PATH, answer_path: opts.answer_path, manual_version: resolvedManualVersion || null });
  return active;
}

export const load_criterion_rules = load_author_rules;

function _manualAnchors(projection: Record<string, any>): Record<string, any>[] {
  const rows: Record<string, Record<string, any>> = {};
  function add(identity: any, opts: { owner: string; algorithm_classes?: string[] }): void {
    if (!identity || typeof identity !== "object" || Array.isArray(identity)) return;
    let anchor: Record<string, any> | null = null;
    if (identity["kind"] === "manual_anchor") {
      anchor = identity;
    } else if (identity["kind"] === "user_ruling" && identity["manual_method_anchor"] && typeof identity["manual_method_anchor"] === "object" && !Array.isArray(identity["manual_method_anchor"])) {
      anchor = identity["manual_method_anchor"];
    }
    if (anchor === null) return;
    const material = {
      source_path: String(anchor?.["source_path"] ?? ""),
      source_sha256: String(anchor?.["source_sha256"] ?? ""),
      source_span: anchor?.["source_span"],
      quote: String(anchor?.["quote"] ?? ""),
    };
    const anchorId = _manualAnchorId(anchor);
    rows[anchorId] = {
      anchor_id: anchorId,
      owner: opts.owner,
      algorithm_classes: [...new Set((opts.algorithm_classes ?? []).map(String).filter((v) => v))].sort(),
      line_start: anchor?.["line_start"],
      ...material,
    };
  }
  for (const rule of projection?.["rules"] ?? []) {
    if (rule && typeof rule === "object" && !Array.isArray(rule)) add(rule["identity"], { owner: String(rule?.["rule_id"] ?? "") });
  }
  for (const [classId, spec] of Object.entries((projection?.["object_classes"] ?? {}) as Record<string, any>)) {
    if (spec && typeof spec === "object" && !Array.isArray(spec)) add(spec["identity"], { owner: `object_class:${classId}` });
  }
  for (const item of projection?.["adjudication_manual_anchors"] ?? []) {
    if (item && typeof item === "object" && !Array.isArray(item)) add(item["identity"], { owner: `adjudication:${String(item?.["anchor_key"] ?? "")}`, algorithm_classes: (item?.["algorithm_classes"] ?? []).map(String) });
  }
  return Object.keys(rows).sort().map((key) => rows[key]);
}

function _treeContext(opts: { pending: Record<string, any>[]; machine_mindmap: Record<string, any>; contracts: Record<string, Record<string, any>> }): [Record<string, any>[], Record<string, Set<string>>] {
  const cases = Object.fromEntries(
    (opts.machine_mindmap?.["cases"] ?? [])
      .filter((c: any) => c && typeof c === "object" && !Array.isArray(c) && String(c?.["autoid"] ?? ""))
      .map((c: any) => [String(c["autoid"]), c])
  );
  const byKey: Record<string, Set<string>> = {};
  const membersByKey: Record<string, Set<string>> = {};
  for (const row of opts.pending) {
    const key = `${String(row?.["shape_key"] ?? "")},${String(row?.["version_family"] ?? "")}`;
    const aid = String(row?.["autoid"] ?? "");
    if (re_full_sha(key.split(",")[0]) && key.split(",")[1] && aid) {
      if (!membersByKey[key]) membersByKey[key] = new Set();
      membersByKey[key].add(aid);
    }
  }
  const rows: Record<string, Record<string, any>> = {};
  for (const [key, memberIds] of Object.entries(membersByKey).sort()) {
    const parentPaths = new Set(Array.from(memberIds).map((aid) => JSON.stringify(((cases[aid]?.["group_path"] ?? []) as string[]).slice(0, -1))));
    const contextualIds = new Set(memberIds);
    for (const [aid, kase] of Object.entries(cases)) {
      if (parentPaths.has(JSON.stringify(((kase?.["group_path"] ?? []) as string[]).slice(0, -1)))) contextualIds.add(aid);
    }
    for (const aid of Array.from(contextualIds).sort()) {
      const kase = cases[aid] ?? {};
      const relation = memberIds.has(aid) ? "member" : "sibling";
      const atoms: [string, string][] = [["title", String(kase?.["title"] ?? "")]];
      atoms.push(...((kase?.["steps"] ?? []) as any[]).filter((s) => s && typeof s === "object" && !Array.isArray(s)).map((step, index) => [`step:${index + 1}`, String(step?.["text"] ?? "")] as [string, string]));
      const contract = opts.contracts?.[aid] ?? {};
      for (let index = 0; index < (contract?.["expectations"] ?? []).length; index++) {
        const expectation = contract["expectations"][index];
        if (expectation && typeof expectation === "object" && !Array.isArray(expectation)) {
          atoms.push([`expectation:${index + 1}`, String(expectation?.["text"] ?? "")]);
        }
      }
      for (const [locator, textValue] of atoms) {
        if (!textValue.trim()) continue;
        const contextId = `tree:${aid}:${locator}`;
        rows[contextId] = { context_id: contextId, autoid: aid, relation, locator, group_path: kase?.["group_path"] ?? [], text: textValue };
        if (!byKey[key]) byKey[key] = new Set();
        byKey[key].add(contextId);
      }
    }
  }
  return [Object.keys(rows).sort().map((key) => rows[key]), byKey];
}

function _behaviourClassificationRequest(machineMindmap: Record<string, any>, members: string[]): Record<string, any>[] {
  const { classification_request, unique_bindings } = require("./behaviour_classes");
  const { UNCLASSIFIED, behaviour_class_closed_set } = require("./device_characteristics");
  const closed = behaviour_class_closed_set();
  if (!closed) return [];
  const offered = Array.from(closed).filter((c) => c !== UNCLASSIFIED).sort();
  if (!offered.length) return [];
  const wanted = new Set(members.filter((v) => v));
  const structure: Record<string, any>[] = [];
  for (const kase of machineMindmap?.["cases"] ?? []) {
    if (!kase || typeof kase !== "object" || Array.isArray(kase)) continue;
    if (wanted.size && !wanted.has(String(kase?.["autoid"] ?? ""))) continue;
    const entries = kase?.["step_structure"];
    if (Array.isArray(entries)) structure.push(...entries.filter((e: any) => e && typeof e === "object" && !Array.isArray(e)));
  }
  if (!structure.length) return [];
  const request = classification_request(structure);
  if (!request) return [];
  const asked = unique_bindings(request);
  const byKey = new Map(request.map((row: any) => [`${row["method"]},${row["object_kind"]}`, row]));
  return asked.map((row: any) => ({ method: row["method"], object_kind: row["object_kind"], behaviour_classes: offered, documentation: (byKey.get(`${row["method"]},${row["object_kind"]}`) as Record<string, any>)?.["documentation"] }));
}

export function build_engine_adjudication_brief(pending: Iterable<Record<string, any>>, opts: { projection: Record<string, any>; machine_mindmap: Record<string, any>; contracts: Record<string, Record<string, any>>; path?: string; answer_path?: string; manual_version?: string | null }): Record<string, any> | null {
  const resolvedManualVersion = String(opts.manual_version ?? resolve_compile_manual_version() ?? "");
  const pendingRows = Array.from(pending).filter((row) => row && typeof row === "object" && !Array.isArray(row));
  const groups: Record<string, Record<string, any>[]> = {};
  for (const row of pendingRows) {
    const key = `${String(row?.["shape_key"] ?? "")},${String(row?.["version_family"] ?? "")}`;
    if (re_full_sha(key.split(",")[0]) && key.split(",")[1]) {
      if (!groups[key]) groups[key] = [];
      groups[key].push(row);
    }
  }
  if (!Object.keys(groups).length) return null;
  const [active, history] = _historyState({ path: opts.path ?? AUTHOR_RULE_PATH, answer_path: opts.answer_path, manual_version: resolvedManualVersion || null });
  const filteredGroups: Record<string, Record<string, any>[]> = {};
  for (const [key, rows] of Object.entries(groups)) {
    const shapeKey = key.split(",")[0];
    if (resolvedManualVersion) {
      if (!(active[`${shapeKey},${resolvedManualVersion}`])) filteredGroups[key] = rows;
    } else {
      if (!(active[key])) filteredGroups[key] = rows;
    }
  }
  if (!Object.keys(filteredGroups).length) return null;
  const anchors = _manualAnchors(opts.projection);
  if (!anchors.length) throw new CriterionAuthorRuleError("criterion adjudication has no grounded manual anchor");
  const [treeRows, treeIds] = _treeContext({ pending: Object.values(filteredGroups).flat(), machine_mindmap: opts.machine_mindmap, contracts: opts.contracts });
  const types = (opts.projection?.["criterion_types"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row) && String(row?.["criterion_type"] ?? ""));
  if (!types.length) throw new CriterionAuthorRuleError("criterion adjudication has no L closed set");
  const shapes: Record<string, any>[] = [];
  for (const [key, rows] of Object.entries(filteredGroups).sort()) {
    const [shapeKey, versionFamily] = key.split(",");
    const priorKey = resolvedManualVersion ? `${shapeKey},${resolvedManualVersion}` : key;
    const prior = (history[priorKey] ?? history[key] ?? []).slice(-1);
    const veto = prior.length ? _vetoReceipt(prior[0], { answer_path: opts.answer_path }) : null;
    const algorithmClasses = [...new Set(rows.flatMap((row: any) => (row?.["algorithm_classes"] ?? []).map(String).filter((v: any) => v)))].sort();
    const algorithmAnchorIds = [...new Set(anchors.filter((anchor: any) => (anchor?.["algorithm_classes"] ?? []).some((value: string) => algorithmClasses.includes(value))).map((anchor: any) => String(anchor?.["anchor_id"] ?? "")))].sort();
    const allowedManualAnchorIds = algorithmAnchorIds.length ? algorithmAnchorIds : anchors.map((anchor: any) => String(anchor?.["anchor_id"] ?? "")).sort();
    const claims = rows.map((row: any) => ({
      autoid: String(row?.["autoid"] ?? ""),
      expectation_id: String(row?.["expectation_id"] ?? ""),
      semantic_key: String(row?.["semantic_key"] ?? ""),
      original_text: String(row?.["original_text"] ?? ""),
      authored_step: row?.["authored_step"],
      authored_step_cause: row?.["authored_step_cause"],
      source_span: row?.["source_span"],
    }));
    shapes.push({
      shape_key: shapeKey,
      version_family: versionFamily,
      behaviour_classification: _behaviourClassificationRequest(opts.machine_mindmap, [...new Set(rows.map((row: any) => String(row?.["autoid"] ?? "")).filter((v: any) => v))].sort()),
      members: [...new Set(rows.map((row: any) => String(row?.["autoid"] ?? "")).filter((v: any) => v))].sort(),
      claims,
      algorithm_classes: algorithmClasses,
      allowed_manual_anchor_ids: allowedManualAnchorIds,
      allowed_tree_context_ids: Array.from(treeIds[key] ?? []).sort(),
      prior_vetoed_decision: prior.length && veto ? { rule_id: String(prior[0]?.["rule_id"] ?? ""), criterion_type: String(prior[0]?.["output"]?.["criterion_type"] ?? ""), author_veto_receipt_sha256: String(veto?.["receipt_sha256"] ?? "") } : null,
    });
  }
  const body = {
    schema: ADJUDICATION_BRIEF_SCHEMA,
    manual_version: resolvedManualVersion,
    criterion_types: types,
    manual_anchors: anchors,
    tree_context: treeRows,
    shapes,
    shape_count: shapes.length,
    shape_identity_set_sha256: _sha256(shapes.map((shape) => [shape["shape_key"], shape["version_family"]]).sort()),
    policy: { authority_scope: "verdict_to_criterion_type_only", expected_value_authority: ["Author", "Spec", "DefectSpec", "Manual", "ConfigBinding", "CapabilityXml"], forbidden_inputs: ["precedent", "historical_volume", "device_actual"] },
  };
  return { ...body, brief_sha256: _sha256(body) };
}

export function serialize_engine_adjudication_brief(brief: Record<string, any>): string {
  if (brief?.["schema"] !== ADJUDICATION_BRIEF_SCHEMA) _raiseIdentityDrift("brief.schema", { expected: ADJUDICATION_BRIEF_SCHEMA, actual: brief?.["schema"] });
  const shapes = (brief?.["shapes"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row));
  if (brief?.["shape_count"] !== shapes.length) _raiseIdentityDrift("brief.shape_count", { expected: shapes.length, actual: brief?.["shape_count"] });
  const identityDigest = _sha256(shapes.map((shape: any) => [String(shape?.["shape_key"] ?? ""), String(shape?.["version_family"] ?? "")]).sort());
  if (brief?.["shape_identity_set_sha256"] !== identityDigest) _raiseIdentityDrift("brief.shape_identity_set_sha256", { expected: identityDigest, actual: brief?.["shape_identity_set_sha256"] });
  const body = Object.fromEntries(Object.entries(brief).filter(([k]) => k !== "brief_sha256"));
  const expectedDigest = _sha256(body);
  if (brief?.["brief_sha256"] !== expectedDigest) _raiseIdentityDrift("brief.brief_sha256", { expected: expectedDigest, actual: brief?.["brief_sha256"] });
  return JSON.stringify(brief, null, 2);
}

export function split_engine_adjudication_briefs(brief: Record<string, any>): Record<string, any>[] {
  serialize_engine_adjudication_brief(brief);
  const manualById = Object.fromEntries((brief?.["manual_anchors"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [String(row?.["anchor_id"] ?? ""), { ...row }]));
  const contextById = Object.fromEntries((brief?.["tree_context"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [String(row?.["context_id"] ?? ""), { ...row }]));
  const out: Record<string, any>[] = [];
  for (const shape of brief?.["shapes"] ?? []) {
    if (!shape || typeof shape !== "object" || Array.isArray(shape)) continue;
    const manualIds = (shape?.["allowed_manual_anchor_ids"] ?? []).map(String);
    const contextIds = (shape?.["allowed_tree_context_ids"] ?? []).map(String);
    const body = {
      schema: ADJUDICATION_BRIEF_SCHEMA,
      criterion_types: brief?.["criterion_types"] ?? [],
      manual_anchors: manualIds.map((value: string) => manualById[value]),
      tree_context: contextIds.map((value: string) => contextById[value]),
      shapes: [{ ...shape }],
      shape_count: 1,
      shape_identity_set_sha256: _sha256([[String(shape?.["shape_key"] ?? ""), String(shape?.["version_family"] ?? "")]]),
      policy: { ...(brief?.["policy"] ?? {}) },
    };
    out.push({ ...body, brief_sha256: _sha256(body) });
  }
  return out;
}

const _JSON_FENCE_RE = /^```(?:json)?[ \t]*\r?\n(.*)\r?\n```[ \t]*$/is;
const _TRAILING_CLOSE_FENCE_RE = /^```[ \t]*$/;

function _loadCriterionJudgmentObject(reply: string): Record<string, any> {
  const text = String(reply ?? "").trim().replace(/^\uFEFF/, "");
  if (!text) throw new CriterionAuthorRuleError("criterion judgment is not exact JSON");
  function _loads(raw: string): Record<string, any> | null {
    try {
      const payload = JSON.parse(raw);
      return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : null;
    } catch {
      return null;
    }
  }
  const direct = _loads(text);
  if (direct !== null) return direct;
  const fenced = _JSON_FENCE_RE.exec(text);
  if (fenced) {
    const inner = _loads(fenced[1].trim());
    if (inner !== null) return inner;
  }
  for (let index = text.length - 1; index >= 0; index--) {
    if (text[index] !== "{") continue;
    try {
      const payload = JSON.parse(text.slice(index));
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) continue;
      const remainder = text.slice(index + JSON.stringify(payload).length).trim();
      if (remainder === "" || _TRAILING_CLOSE_FENCE_RE.test(remainder)) return payload;
    } catch {
      continue;
    }
  }
  throw new CriterionAuthorRuleError("criterion judgment is not exact JSON");
}

export function parse_engine_adjudication_result(reply: string, opts: { brief: Record<string, any> }): Record<string, any>[] {
  serialize_engine_adjudication_brief(opts.brief);
  const shapes = (opts.brief?.["shapes"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row));
  if (shapes.length !== 1) throw new CriterionAuthorRuleError("criterion judgment parser accepts exactly one engine-bound shape");
  const payload = _loadCriterionJudgmentObject(reply);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new CriterionAuthorRuleError("criterion judgment must be one JSON object");
  const judgmentFields = new Set(["criterion_type", "rationale", "disclosure"]);
  const citationFields = new Set(["manual_anchor_ids", "tree_context_ids", "behaviour_classes"]);
  const ignoredIdentityFields = new Set(["schema", "brief_sha256", "shape_key", "version_family"]);
  const unknown = Object.keys(payload).filter((key) => !judgmentFields.has(key) && !citationFields.has(key) && !ignoredIdentityFields.has(key));
  if (unknown.length) throw new CriterionAuthorRuleError(`criterion judgment fields are not closed; expected/operator/value and all non-judgment fields are forbidden: ${unknown.sort()}`);
  if (![...judgmentFields].every((key) => key in payload)) throw new CriterionAuthorRuleError("criterion judgment requires criterion_type, rationale, and disclosure");
  const catalogue = Object.fromEntries((opts.brief?.["criterion_types"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [String(row?.["criterion_type"] ?? ""), row]));
  const criterionType = String(payload?.["criterion_type"] ?? "");
  if (!(criterionType in catalogue)) _raiseEvidenceGap("criterion_type", { expected: Object.keys(catalogue).sort(), actual: criterionType });
  const rationale = String(payload?.["rationale"] ?? "").trim();
  const disclosure = String(payload?.["disclosure"] ?? "").trim();
  if (!rationale) _raiseEvidenceGap("rationale", { expected: "non-empty judgment rationale", actual: payload?.["rationale"] });
  if (!disclosure) _raiseEvidenceGap("disclosure", { expected: "non-empty Chinese disclosure", actual: payload?.["disclosure"] });
  const shape = shapes[0];
  const manualIds = [...new Set((shape?.["allowed_manual_anchor_ids"] ?? []).map(String).filter((v: string) => v))].sort();
  const contextIds = [...new Set((shape?.["allowed_tree_context_ids"] ?? []).map(String).filter((v: string) => v))].sort();
  if (!manualIds.length || !contextIds.length) throw new CriterionAuthorRuleError("engine-bound criterion evidence allowlists are incomplete");
  function _validModelCitation(field: string, allowed: Set<string>): [string[], boolean] {
    const value = payload?.[field];
    if (!Array.isArray(value) || !value.length) return [[], false];
    const normalized = value.filter((item: any) => typeof item === "string" && item).map(String);
    return [normalized, normalized.length === value.length && new Set(normalized).size === normalized.length && normalized.every((item) => allowed.has(item))];
  }
  const [modelManual, manualValid] = _validModelCitation("manual_anchor_ids", new Set<string>(manualIds as string[]));
  const [modelContext, contextValid] = _validModelCitation("tree_context_ids", new Set<string>(contextIds as string[]));
  const citationCorrected = !(manualValid && contextValid);
  const correctionDisclosure = citationCorrected ? "模型锚引用缺失或越界，已由引擎按信封开放集机械绑定。" : "";
  let finalDisclosure = disclosure;
  if (correctionDisclosure) finalDisclosure = disclosure.replace(/[。；; ]+$/, "") + "；" + correctionDisclosure;
  const { validate_behaviour_classification } = require("./behaviour_classes");
  const asked = (shape?.["behaviour_classification"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => ({ method: String(row?.["method"] ?? ""), object_kind: String(row?.["object_kind"] ?? "") }));
  const behaviourRows = asked.length ? validate_behaviour_classification(payload?.["behaviour_classes"], { asked }) : [];
  return [{
    shape_key: String(shape?.["shape_key"] ?? ""),
    version_family: String(shape?.["version_family"] ?? ""),
    criterion_type: criterionType,
    behaviour_classes: behaviourRows,
    manual_anchor_ids: manualIds,
    tree_context_ids: contextIds,
    rationale,
    disclosure: finalDisclosure,
    engine_brief_sha256: String(opts.brief?.["brief_sha256"] ?? ""),
    anchor_citation_corrected: citationCorrected,
    citation_disclosure: correctionDisclosure,
    model_citation: {
      manual_anchor_ids: manualValid ? modelManual : [],
      tree_context_ids: contextValid ? modelContext : [],
      manual_provided_count: modelManual.length,
      tree_provided_count: modelContext.length,
      manual_valid: manualValid,
      tree_valid: contextValid,
      valid: !citationCorrected,
    },
  }];
}

const _SHAPE_OUTER_ATTEMPTS = 2;

function _nonRetryableForkCauses(): Set<string> {
  try {
    return new Set(require("../ist_core/resilience").NON_RETRYABLE_FORK_CAUSES);
  } catch {
    return new Set(["LLM_QUOTA_EXHAUSTED", "CANCELLED", "ABANDONED_BEFORE_DISPATCH"]);
  }
}

function _forkTerminationCause(terminationCause: (() => string) | null): string {
  if (terminationCause === null) return "";
  try {
    return String(terminationCause() ?? "").trim();
  } catch {
    return "";
  }
}

export function adjudicate_single_shape_with_retry(brief: Record<string, any>, invoke: (wire: string, attempt: number) => string, opts: { non_retryable?: (exc: Error) => boolean; termination_cause?: (() => string) | null } = {}): Record<string, any> {
  const shapes = (brief?.["shapes"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row));
  if (shapes.length !== 1) throw new CriterionAuthorRuleError("single-shape retry received a non-single brief");
  const errors: string[] = [];
  const wire = serialize_engine_adjudication_brief(brief);
  let lastAttempt = 0;
  function _unavailable(attempt: number): Record<string, any> {
    return { status: "unavailable", attempts: attempt, shape: { ...shapes[0] }, decisions: [], errors };
  }
  for (let attempt = 1; attempt <= _SHAPE_OUTER_ATTEMPTS; attempt++) {
    lastAttempt = attempt;
    let reply: string;
    try {
      reply = invoke(wire, attempt);
    } catch (exc: any) {
      const cause = _forkTerminationCause(opts.termination_cause ?? null);
      if (_nonRetryableForkCauses().has(cause)) {
        errors.push(`${cause}: ${exc?.constructor?.name ?? "Error"}: ${exc}`.slice(0, 400));
        return _unavailable(attempt);
      }
      if (opts.non_retryable && opts.non_retryable(exc)) throw exc;
      errors.push(`${exc?.constructor?.name ?? "Error"}: ${exc}`.slice(0, 400));
      continue;
    }
    const cause = _forkTerminationCause(opts.termination_cause ?? null);
    if (_nonRetryableForkCauses().has(cause)) {
      errors.push(`${cause}: ${String(reply ?? "").slice(0, 300)}`);
      return _unavailable(attempt);
    }
    try {
      const decisions = parse_engine_adjudication_result(reply, { brief });
      try {
        const { shadow_criterion_adjudication } = require("../common/typesafe_shadow");
        shadow_criterion_adjudication({ wire, decisions });
      } catch {}
      return { status: "decided", attempts: attempt, shape: { ...shapes[0] }, decisions, errors };
    } catch (exc: any) {
      if (opts.non_retryable && opts.non_retryable(exc)) throw exc;
      errors.push(`${exc?.constructor?.name ?? "Error"}: ${exc}`.slice(0, 400));
      continue;
    }
  }
  return _unavailable(lastAttempt);
}

function _appendRecords(filePath: string, records: Record<string, any>[]): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const existed = fs.existsSync(filePath);
  const fd = fs.openSync(filePath, "a");
  try {
    for (const record of records) {
      const raw = Buffer.from(JSON.stringify(record, Object.keys(record).sort()) + "\n", "utf8");
      let offset = 0;
      while (offset < raw.length) {
        const written = fs.writeSync(fd, raw, offset, raw.length - offset);
        if (written <= 0) throw new CriterionAuthorRuleError("criterion rule append made no progress");
        offset += written;
      }
    }
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  if (!existed) {
    try {
      const dirFd = fs.openSync(path.dirname(filePath), "r");
      try {
        fs.fsyncSync(dirFd);
      } finally {
        fs.closeSync(dirFd);
      }
    } catch {}
  }
}

function _persistBehaviourClasses(decisions: Record<string, any>[]): number {
  const { persist_behaviour_classes } = require("./behaviour_classes");
  const rows = decisions.flatMap((decision) => (decision?.["behaviour_classes"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)));
  if (!rows.length) return 0;
  try {
    return persist_behaviour_classes(rows).length;
  } catch {
    return 0;
  }
}

export function persist_engine_adjudications(decisions: Record<string, any>[], opts: { brief: Record<string, any>; path?: string; answer_path?: string; manual_version?: string | null }): Record<string, any>[] {
  const target = opts.path ?? AUTHOR_RULE_PATH;
  const resolvedManualVersion = String(opts.manual_version ?? opts.brief?.["manual_version"] ?? resolve_compile_manual_version() ?? "");
  const lockPath = target + ".lock";
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  const lock = acquireLockSync(lockPath);
  try {
    return (() => {
    const [active, history] = _historyState({ path: target, answer_path: opts.answer_path, manual_version: resolvedManualVersion || null });
    const anchors = Object.fromEntries((opts.brief?.["manual_anchors"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [String(row?.["anchor_id"] ?? ""), { ...row }]));
    const contexts = Object.fromEntries((opts.brief?.["tree_context"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [String(row?.["context_id"] ?? ""), { ...row }]));
    const catalogue = Object.fromEntries((opts.brief?.["criterion_types"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [String(row?.["criterion_type"] ?? ""), { ...row }]));
    const shapes = Object.fromEntries((opts.brief?.["shapes"] ?? []).filter((row: any) => row && typeof row === "object" && !Array.isArray(row)).map((row: any) => [`${String(row?.["shape_key"] ?? "")},${String(row?.["version_family"] ?? "")}`, row]));
    const records: Record<string, any>[] = [];
    const newRecords: Record<string, any>[] = [];
    let anchorChapterPinsPartial: (anchors: any[], opts: { manual_version: string }) => [Record<string, Record<string, string>>, Record<string, string>[]];
    try {
      anchorChapterPinsPartial = require("../kms/manual_chapter_locator").anchor_chapter_pins_partial;
    } catch {
      anchorChapterPinsPartial = () => [{}, []];
    }
    for (const decision of decisions) {
      const shapeKey = String(decision?.["shape_key"] ?? "");
      const versionFamily = String(decision?.["version_family"] ?? "");
      const reuseKey = resolvedManualVersion ? `${shapeKey},${resolvedManualVersion}` : `${shapeKey},${versionFamily}`;
      if (reuseKey in active) {
        records.push(active[reuseKey]);
        continue;
      }
      const prior = (history[reuseKey] ?? history[`${shapeKey},${versionFamily}`] ?? []).slice(-1);
      const veto = prior.length ? _vetoReceipt(prior[0], { answer_path: opts.answer_path }) : null;
      const cause = prior.length ? supersede_cause(prior[0], { veto, manual_version: resolvedManualVersion }) : null;
      if (prior.length && veto === null && _ruleReusable(prior[0], { manual_version: resolvedManualVersion })) {
        throw new CriterionAuthorRuleError("reusable criterion rule was not returned as active");
      }
      const generation = prior.length ? Number(prior[0]?.["generation"] ?? 0) + 1 : 1;
      const criterionType = String(decision?.["criterion_type"] ?? "");
      const manualAnchorRows = (decision?.["manual_anchor_ids"] ?? []).map((value: string) => anchors[value]);
      const evidenceChain = { manual_anchors: manualAnchorRows, tree_context: (decision?.["tree_context_ids"] ?? []).map((value: string) => contexts[value]), language: catalogue[criterionType] };
      let anchorChapterShas: Record<string, Record<string, string>> = {};
      let catalogPins: Record<string, Record<string, string>> = {};
      let pinFailures: Record<string, string>[] = [];
      if (resolvedManualVersion) {
        [anchorChapterShas, pinFailures] = anchorChapterPinsPartial(manualAnchorRows, { manual_version: resolvedManualVersion });
        catalogPins = _catalogPins(resolvedManualVersion, _familiesFromAnchors(manualAnchorRows));
      }
      const identity = { kind: "engine_adjudication", adjudicator: "criterion-adjudicator", brief_sha256: String(decision?.["engine_brief_sha256"] ?? ""), decision_sha256: _sha256(Object.fromEntries(Object.entries(decision).filter(([k]) => k !== "behaviour_classes"))), evidence_chain: evidenceChain };
      const body = {
        schema: ENGINE_RULE_SCHEMA,
        rule_id: `criterion.engine.${shapeKey.slice(0, 16)}.g${generation}`,
        shape_key: shapeKey,
        version_family: versionFamily,
        manual_version: resolvedManualVersion,
        generation,
        output: { criterion_type: criterionType, mode: "direct" },
        identity,
        anchor_chapter_shas: anchorChapterShas,
        catalog_pins: catalogPins,
        pin_failures: pinFailures,
        rationale: String(decision?.["rationale"] ?? ""),
        disclosure: String(decision?.["disclosure"] ?? ""),
        anchor_citation_corrected: Boolean(decision?.["anchor_citation_corrected"]),
        citation_disclosure: String(decision?.["citation_disclosure"] ?? ""),
        model_citation: { ...(decision?.["model_citation"] ?? {}) },
        members: (shapes[`${shapeKey},${versionFamily}`]?.["members"] ?? []),
        created_at: Date.now() / 1000,
        supersede_cause: cause,
        supersedes_rule_sha256: prior.length ? String(prior[0]?.["rule_sha256"] ?? "") : null,
      };
      const record = { ...body, rule_sha256: _sha256(body) };
      records.push(record);
      newRecords.push(record);
    }
    if (newRecords.length) _appendRecords(target, newRecords);
    _persistBehaviourClasses(decisions);
    return records;
    })();
  } finally {
    lock.release();
  }
}

export function fixture_value_disclosures(mechanicalCase: Record<string, any>): Record<string, any>[] {
  const rows: Record<string, any>[] = [];
  for (let blockIndex = 0; blockIndex < (mechanicalCase?.["blocks"] ?? []).length; blockIndex++) {
    const block = mechanicalCase["blocks"][blockIndex];
    if (!block || typeof block !== "object" || Array.isArray(block) || String(block?.["kind"] ?? "").toUpperCase() !== "OBSERVE_ASSERT") continue;
    for (let assertIndex = 0; assertIndex < (block?.["asserts"] ?? []).length; assertIndex++) {
      const assertion = block["asserts"][assertIndex];
      if (!assertion || typeof assertion !== "object" || Array.isArray(assertion)) continue;
      const binding = assertion?.["binding_input"];
      if (!binding || typeof binding !== "object" || Array.isArray(binding) || binding?.["rule_id"] !== "config.fixture-literal-backref" || !(binding?.["source_input"] && typeof binding["source_input"] === "object" && !Array.isArray(binding["source_input"]))) continue;
      const sourceInput = binding["source_input"];
      rows.push({
        expectation_id: String(assertion?.["expectation_id"] ?? ""),
        fixture_kind: String(sourceInput?.["fixture_kind"] ?? ""),
        value: String(sourceInput?.["value"] ?? ""),
        config_block_index: Number(sourceInput?.["config_block_index"] ?? 0),
        config_command_index: Number(sourceInput?.["config_command_index"] ?? 0),
        assert_block_index: blockIndex,
        assert_index: assertIndex,
      });
    }
  }
  return rows;
}

export function criterion_pending_from_ledgers(ledgers: Record<string, Record<string, any>>): [string, Record<string, any>[]] {
  const found: [string, Record<string, any>[]][] = [];
  for (const [aid, ledger] of Object.entries(ledgers).sort()) {
    for (const claim of ledger?.["claims"] ?? []) {
      if (!claim || typeof claim !== "object" || Array.isArray(claim) || claim?.["claim_kind"] !== "criterion_rule_batch") continue;
      const rows = claim?.["criterion_claims"];
      if (Array.isArray(rows) && rows.length && rows.every((row: any) => row && typeof row === "object" && !Array.isArray(row))) {
        found.push([String(aid), rows.map((row: any) => ({ ...row }))]);
      }
    }
  }
  if (!found.length) return ["", []];
  if (found.length !== 1) throw new CriterionAuthorRuleError("multiple criterion batch ledgers are present");
  return found[0];
}

export function build_batch_criterion_questions(..._args: any[]): Record<string, any>[] {
  throw new CriterionAuthorRuleError("criterion author-confirmation questions are retired");
}

export function persist_author_rule_answer(..._args: any[]): Record<string, any> | null {
  throw new CriterionAuthorRuleError("direct author criterion signing is retired");
}
