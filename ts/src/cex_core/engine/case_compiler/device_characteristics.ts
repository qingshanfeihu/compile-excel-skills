import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { KNOWLEDGE_DATA_ROOT } from "../knowledge_paths";
import { read_regular_nofollow } from "./_sealed_io";

export const CHARACTERISTICS_PATH = path.join(KNOWLEDGE_DATA_ROOT, "compile_ref", "device_characteristics.json");
export const CHARACTERISTICS_SCHEMA = "ist.device-characteristics";
export const PINNED_SOURCE_ROOTS: Record<string, string> = { manual: "knowledge/data/manual/", spec: "knowledge/data/spec/" };
export const UNCLASSIFIED = "unclassified";
export const TIERS = ["T1", "T2", "T3", "T4"];
export const DISCLOSURE_CODES = ["authored_count", "sampling_required", "count_is_worker_declared", "device_decides", "characteristic", "structure_characteristic", "behaviour_unclassified", "counter_field_undocumented", "no_characteristic_for_pair", "no_object_kind_declared", "trigger_echo_bounded", "characteristics_unavailable", "observation_pairing_unavailable", "characteristics_truncated", "characteristic_scope_unverified"];
export const MAX_PINNED_SOURCE_BYTES = 32 * 1024 * 1024;

function _maxDetailChars(): number {
  const { MAX_VALUE_CHARS } = require("./step_structure");
  return Number(MAX_VALUE_CHARS);
}
export const MAX_FACTS_PER_TIER = 12;
export const MAX_DISCLOSURE_MESSAGE_CHARS = 400;
let _cache: Record<string, any> = {};

export function load_device_characteristics(): Record<string, any> | null {
  let mtime: number;
  try {
    mtime = fs.statSync(CHARACTERISTICS_PATH).mtimeMs;
  } catch {
    return null;
  }
  if (_cache["mtime"] === mtime) return _cache["data"] ?? null;
  let data: any;
  try {
    data = JSON.parse(fs.readFileSync(CHARACTERISTICS_PATH, "utf8"));
  } catch {
    return null;
  }
  if (!data || typeof data !== "object" || Array.isArray(data) || String(data["schema"] ?? "") !== CHARACTERISTICS_SCHEMA) return null;
  if (!_pinnedSourcesConfined(data)) {
    _cache = { mtime, data: null };
    return null;
  }
  if (!_pinnedSourcesUnchanged(data)) {
    _cache = { mtime, data: null };
    return null;
  }
  _cache = { mtime, data };
  return data;
}

export function pinned_source_is_confined(rel: any): boolean {
  const text = String(rel ?? "");
  if (!text || text !== text.trim()) return false;
  if (text.startsWith("/") || /^[A-Za-z]:/.test(text) || text.includes("\\")) return false;
  const parts = text.split("/");
  if (parts.some((p) => p === ".." || p === "")) return false;
  return Object.values(PINNED_SOURCE_ROOTS).some((prefix) => text.startsWith(prefix) && text.length > prefix.length);
}

function _pinnedSourcesConfined(data: Record<string, any>): boolean {
  const pinned = data?.["identity"]?.["pinned_sources"];
  if (!pinned || typeof pinned !== "object" || Array.isArray(pinned) || Object.keys(pinned).length === 0) return false;
  return Object.keys(pinned).every((rel) => pinned_source_is_confined(rel));
}

export function read_pinned_source_bytes(rel: string): Buffer {
  const root = path.dirname(path.dirname(KNOWLEDGE_DATA_ROOT));
  if (!pinned_source_is_confined(rel)) {
    throw new Error(`pinned source is outside knowledge/: ${JSON.stringify(rel)}`);
  }
  const raw = read_regular_nofollow(rel, {
    errorType: Error,
    invalid_message: `pinned source path is not readable: ${rel}`,
    directory_message: `pinned source is a directory: ${rel}`,
    open_message: `pinned source could not be opened: ${rel}`,
    bounds_message: `pinned source is out of bounds: ${rel}`,
    changed_message: `pinned source changed while reading: ${rel}`,
    max_bytes: MAX_PINNED_SOURCE_BYTES,
    trusted_root: root,
  });
  return Buffer.isBuffer(raw) ? raw : Buffer.from(raw as unknown as Uint8Array);
}

function _pinnedSourcesUnchanged(data: Record<string, any>): boolean {
  const pinned = data?.["identity"]?.["pinned_sources"];
  if (!pinned || typeof pinned !== "object" || Array.isArray(pinned) || Object.keys(pinned).length === 0) return false;
  for (const [rel, expected] of Object.entries(pinned)) {
    let actual: string;
    try {
      actual = crypto.createHash("sha256").update(read_pinned_source_bytes(rel)).digest("hex");
    } catch {
      return false;
    }
    if (actual !== String(expected)) return false;
  }
  return true;
}

export function clear_characteristics_cache(): void {
  _cache = {};
}

export function behaviour_class_closed_set(): Set<string> | null {
  const data = load_device_characteristics();
  if (!data) return null;
  const rows = data["behaviour_classes"];
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const ids = new Set<string>();
  for (const row of rows) {
    if (row && typeof row === "object" && !Array.isArray(row)) {
      const id = String(row["id"] ?? "");
      if (id) ids.add(id);
    }
  }
  return ids.size ? ids : null;
}

export function characteristic_facts(): Record<string, any>[] {
  const data = load_device_characteristics();
  if (!data) return [];
  return (Array.isArray(data["facts"]) ? data["facts"] : []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r));
}

export function structure_predicate_specs(): Record<string, any>[] {
  const data = load_device_characteristics();
  if (!data) return [];
  return (Array.isArray(data["structure_predicates"]) ? data["structure_predicates"] : []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r));
}

function _text(value: any, limit: number | null = null): string {
  const raw = String(value ?? "");
  return raw.slice(0, limit ?? _maxDetailChars());
}

function _statedValues(entry: any): string[] {
  const out: string[] = [];
  for (const item of entry?.["stated_conditions"] ?? []) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    out.push(_text(item["value"]));
    out.push(_text(item["text"], 2000));
  }
  return out.filter((v) => v);
}

function _weightDeclarations(entries: any[], kase: any): [string, string][] {
  const { concretized_weights, stated_weights } = require("./step_structure");
  const out: [string, string][] = [];
  for (const entry of entries) {
    const number = String(entry?.["n"] ?? "").trim();
    for (const weights of [stated_weights(entry), concretized_weights(kase ?? {}, entry)]) {
      if (weights) out.push([number, weights.map((v: any) => String(v)).join(":")]);
    }
  }
  return out;
}

function _structureSignalSteps(entries: any[], spec: any): string[] {
  const { _norm_head_tokens, command_role_atlas } = require("./step_structure");
  const roles = new Set((spec?.["roles"] ?? []).map((v: any) => String(v)));
  const classes = new Set((spec?.["command_classes"] ?? []).map((v: any) => String(v)));
  const atlas = classes.size ? command_role_atlas() : null;
  const hits: string[] = [];
  for (const entry of entries) {
    const number = String(entry?.["n"] ?? "").trim();
    if (!number) continue;
    let matched = (entry?.["objects"] ?? []).some((item: any) => item && typeof item === "object" && !Array.isArray(item) && roles.has(String(item["role"] ?? "")));
    if (!matched && atlas !== null) {
      for (const item of entry?.["operations"] ?? []) {
        if (!item || typeof item !== "object" || Array.isArray(item)) continue;
        const tokens = _norm_head_tokens(item["head"]);
        if (tokens && classes.has(atlas.command_class(tokens))) {
          matched = true;
          break;
        }
      }
    }
    if (matched) hits.push(number);
  }
  return hits;
}

function _statedTokenSteps(entries: any[], spec: any): string[] {
  const groups = (spec?.["token_groups"] ?? []).filter((g: any) => Array.isArray(g) && g.length).map((g: any) => new Set(g.map((t: any) => String(t))));
  if (!groups.length) return [];
  const perGroupSteps: string[][] = [];
  for (const group of groups) {
    const hits: string[] = [];
    for (const entry of entries) {
      const number = String(entry?.["n"] ?? "").trim();
      if (!number) continue;
      const folded = _statedValues(entry).join(" ").toLowerCase();
      if ([...group].some((token) => folded.includes(token.toLowerCase()))) hits.push(number);
    }
    perGroupSteps.push(hits);
  }
  if (String(spec?.["match"] ?? "") === "all") {
    if (!perGroupSteps.every((s) => s.length)) return [];
  } else if (!perGroupSteps.some((s) => s.length)) {
    return [];
  }
  const ordered: string[] = [];
  for (const hits of perGroupSteps) {
    for (const number of hits) {
      if (!ordered.includes(number)) ordered.push(number);
    }
  }
  return ordered;
}

export function evaluate_structure_predicates(structure: any[], opts: { case?: any } = {}): Record<string, string[]> {
  const entries = (structure ?? []).filter((e: any) => e && typeof e === "object" && !Array.isArray(e));
  if (!entries.length) return {};
  const hits: Record<string, string[]> = {};
  for (const spec of structure_predicate_specs()) {
    const ident = String(spec?.["id"] ?? "");
    const evaluator = String(spec?.["evaluator"] ?? "");
    if (!ident) continue;
    let steps: string[];
    if (evaluator === "structure_signal") {
      steps = _structureSignalSteps(entries, spec);
    } else if (evaluator === "weight_declarations") {
      const declarations = _weightDeclarations(entries, opts.case);
      let least = spec?.["distinct_at_least"];
      least = typeof least === "number" && Number.isInteger(least) ? least : 2;
      const distinct = new Set(declarations.map(([, value]) => value));
      steps = distinct.size >= least ? declarations.map(([step]) => step) : [];
    } else if (evaluator === "stated_tokens") {
      steps = _statedTokenSteps(entries, spec);
    } else {
      steps = [];
    }
    if (steps.length) {
      const ordered: string[] = [];
      for (const number of steps) {
        if (!ordered.includes(number)) ordered.push(number);
      }
      hits[ident] = ordered;
    }
  }
  return hits;
}

export function characteristics_for(opts: { object_kinds?: Iterable<string>; behaviour_classes?: Iterable<string>; structure_predicates?: Iterable<string>; require_predicate?: boolean } = {}): Record<string, any>[] {
  return _filterPool(characteristic_facts(), opts);
}

function _disclosure(tier: string, code: string, opts: { fact?: any } & Record<string, any> = {}): Record<string, any> {
  if (!DISCLOSURE_CODES.includes(code)) {
    throw new Error(`device disclosure code is outside the closed set: ${JSON.stringify(code)}`);
  }
  const fact = opts.fact ?? {};
  const row: Record<string, any> = {
    tier,
    code,
    fact_id: String(fact["id"] ?? ""),
    characteristic_class: String(fact["characteristic_class"] ?? ""),
    locator: String(fact["locator"] ?? ""),
    pinned: String(fact["pinned"] ?? ""),
    quote: String(fact["quote"] ?? ""),
    text: String(fact["text"] ?? ""),
    detail: Object.fromEntries(Object.entries(opts).filter(([k, v]) => k !== "fact" && v !== "" && v !== null && v !== undefined)),
  };
  const observation = fact["observation"];
  if (observation && typeof observation === "object" && !Array.isArray(observation)) row["observation"] = { ...observation };
  return row;
}

function _predicateLabel(predicateId: string): string {
  for (const spec of structure_predicate_specs()) {
    if (String(spec?.["id"] ?? "") === String(predicateId ?? "")) return String(spec?.["label_zh"] ?? "");
  }
  return "";
}

function _authoredCounts(entries: any[], steps: string[]): [string, number, string][] {
  const { stated_count_integers } = require("./step_structure");
  const wanted = new Set(steps.filter((s) => String(s)).map((s) => String(s)));
  if (!wanted.size) return [];
  const out: [string, number, string][] = [];
  for (const entry of entries) {
    const number = String(entry?.["n"] ?? "").trim();
    if (!wanted.has(number)) continue;
    for (const item of entry?.["stated_conditions"] ?? []) {
      if (!item || typeof item !== "object" || Array.isArray(item) || String(item["kind"] ?? "") !== "count") continue;
      const values = stated_count_integers(item["value"]);
      const sourceText = String(item["text"] ?? "").trim();
      if (values.length === 1 && sourceText) {
        const row: [string, number, string] = [number, values[0], sourceText];
        if (!out.some((r) => r[0] === row[0] && r[1] === row[1] && r[2] === row[2])) out.push(row);
      }
    }
  }
  return out;
}

export function select_disclosure(stepStructure: any[], behaviour: any[] = [], characteristics: any[] | null = null, opts: { case?: any; distribution_steps?: string[]; has_distribution_criterion?: boolean } = {}): Record<string, any[]> {
  const entries = (stepStructure ?? []).filter((e: any) => e && typeof e === "object" && !Array.isArray(e));
  const records = (behaviour ?? []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r));
  const tiers: Record<string, any[]> = Object.fromEntries(TIERS.map((t) => [t, []]));
  const kinds = [...new Set(entries.flatMap((e: any) => (e?.["objects"] ?? []).filter((i: any) => i && typeof i === "object" && !Array.isArray(i)).map((i: any) => String(i["kind"] ?? ""))).filter((k: string) => k))].sort();
  const classes = [...new Set(records.map((r: any) => String(r?.["behaviour_class"] ?? "")).filter((c: string) => c && c !== UNCLASSIFIED))].sort();
  if (opts.has_distribution_criterion) {
    for (const [number, value, sourceText] of _authoredCounts(entries, opts.distribution_steps ?? []).slice(0, MAX_FACTS_PER_TIER)) {
      tiers["T1"].push(_disclosure("T1", "authored_count", { step: number, count: value, source_text: sourceText }));
    }
    tiers["T1"].push(_disclosure("T1", "sampling_required"));
    tiers["T1"].push(_disclosure("T1", "count_is_worker_declared"));
    tiers["T1"].push(_disclosure("T1", "device_decides"));
  }
  const available = characteristics !== null || load_device_characteristics() !== null;
  if (!available) {
    tiers["T4"].push(_disclosure("T4", "characteristics_unavailable"));
    return tiers;
  }
  const pool = characteristics !== null ? characteristics.filter((r: any) => r && typeof r === "object" && !Array.isArray(r)).map((r: any) => ({ ...r })) : null;

  function _select(kwargs: any): Record<string, any>[] {
    if (pool === null) return characteristics_for(kwargs);
    return _filterPool(pool, kwargs);
  }
  const shown: any[] = [];
  const matched = _select({ object_kinds: kinds, behaviour_classes: classes });
  for (const fact of matched.slice(0, MAX_FACTS_PER_TIER)) {
    tiers["T2"].push(_disclosure("T2", "characteristic", { fact }));
    shown.push(fact);
  }
  if (matched.length > MAX_FACTS_PER_TIER) tiers["T4"].push(_disclosure("T4", "characteristics_truncated"));
  const predicateHits = evaluate_structure_predicates(entries, { case: opts.case });
  for (const fact of _select({ object_kinds: kinds, behaviour_classes: classes, structure_predicates: Object.keys(predicateHits), require_predicate: true }).slice(0, MAX_FACTS_PER_TIER)) {
    const fired = (fact?.["applies_to"]?.["structure_predicates"] ?? []).filter((name: string) => name in predicateHits);
    const steps = [...new Set(fired.flatMap((name: string) => predicateHits[name] ?? []))].sort();
    tiers["T3"].push(_disclosure("T3", "structure_characteristic", { fact, predicates: fired, steps, label_zh: fired.length ? _predicateLabel(fired[0]) : "" }));
    shown.push(fact);
  }
  const unverified = _unverifiedObjectScopeFacts(pool ?? characteristic_facts(), { object_kinds: kinds, behaviour_classes: classes, structure_predicates: Object.keys(predicateHits) });
  for (const fact of unverified.slice(0, MAX_FACTS_PER_TIER)) {
    const applies = fact?.["applies_to"] ?? {};
    tiers["T4"].push(_disclosure("T4", "characteristic_scope_unverified", { fact, object_kinds: kinds, documented_object_kinds: [...new Set((applies?.["object_kinds"] ?? []).map((v: any) => String(v)))].sort() }));
  }
  if (unverified.length > MAX_FACTS_PER_TIER && !tiers["T4"].some((r: any) => r["code"] === "characteristics_truncated")) {
    tiers["T4"].push(_disclosure("T4", "characteristics_truncated"));
  }
  for (const row of records) {
    if (String(row?.["behaviour_class"] ?? "") === UNCLASSIFIED) {
      tiers["T4"].push(_disclosure("T4", "behaviour_unclassified", { method: _text(row?.["method"]), object_kind: _text(row?.["object_kind"]) }));
    }
  }
  for (const fact of shown) {
    const observation = fact?.["observation"];
    if (observation && typeof observation === "object" && !Array.isArray(observation) && !observation["fields_documented"]) {
      tiers["T4"].push(_disclosure("T4", "counter_field_undocumented", { fact, show_command: _text(observation["show_command"]) }));
    }
  }
  if (!tiers["T2"].length && !tiers["T3"].length) {
    if (kinds.length) {
      tiers["T4"].push(_disclosure("T4", "no_characteristic_for_pair", { object_kinds: kinds, behaviour_classes: classes.length ? classes : [UNCLASSIFIED] }));
    } else {
      tiers["T4"].push(_disclosure("T4", "no_object_kind_declared", { behaviour_classes: classes.length ? classes : [UNCLASSIFIED] }));
    }
  }
  if (opts.has_distribution_criterion) tiers["T4"].push(_disclosure("T4", "trigger_echo_bounded"));
  return tiers;
}

function _unverifiedObjectScopeFacts(pool: any[], opts: { object_kinds: string[]; behaviour_classes: string[]; structure_predicates: string[] }): Record<string, any>[] {
  const kinds = new Set(opts.object_kinds);
  const namespaces = new Set([...kinds].filter((k) => k.includes("/")).map((k) => k.split("/")[0]));
  if (!namespaces.size || !opts.structure_predicates.length) return [];
  const scoped = pool.filter((f: any) => f && typeof f === "object" && !Array.isArray(f) && f["applies_to"] && typeof f["applies_to"] === "object" && !Array.isArray(f["applies_to"]));
  const documented = new Set<string>();
  for (const fact of scoped) {
    for (const kind of fact?.["applies_to"]?.["object_kinds"] ?? []) {
      const k = String(kind);
      if (namespaces.has(k.split("/")[0])) documented.add(k);
    }
  }
  const candidates = _filterPool(scoped, { object_kinds: [...documented].filter((k) => !kinds.has(k)), behaviour_classes: opts.behaviour_classes, structure_predicates: opts.structure_predicates, require_predicate: true });
  return candidates.filter((fact: any) => {
    const factKinds = new Set((fact?.["applies_to"]?.["object_kinds"] ?? []).map((v: any) => String(v)));
    return ![...kinds].some((k) => factKinds.has(k));
  });
}

function _filterPool(pool: any[], opts: { object_kinds?: Iterable<string>; behaviour_classes?: Iterable<string>; structure_predicates?: Iterable<string>; require_predicate?: boolean } = {}): Record<string, any>[] {
  const kinds = new Set(Array.from(opts.object_kinds ?? []).map((v) => String(v)).filter((v) => v));
  const classes = new Set(Array.from(opts.behaviour_classes ?? []).map((v) => String(v)).filter((v) => v));
  const predicates = new Set(Array.from(opts.structure_predicates ?? []).map((v) => String(v)).filter((v) => v));
  if (!kinds.size) return [];
  const out: Record<string, any>[] = [];
  for (const fact of pool) {
    const applies = fact?.["applies_to"];
    if (!applies || typeof applies !== "object" || Array.isArray(applies)) continue;
    const factKinds = new Set<string>((applies?.["object_kinds"] ?? []).map((v: any) => String(v)));
    const factClasses = new Set<string>((applies?.["behaviour_classes"] ?? []).map((v: any) => String(v)));
    const factPredicates = new Set<string>((applies?.["structure_predicates"] ?? []).map((v: any) => String(v)));
    if (![...factKinds].some((k) => kinds.has(k))) continue;
    if (factClasses.size && classes.size && ![...factClasses].some((c) => classes.has(c))) continue;
    if (opts.require_predicate) {
      if (!factPredicates.size || ![...factPredicates].some((p) => predicates.has(p))) continue;
    } else if (factPredicates.size) {
      continue;
    }
    out.push({ ...fact });
  }
  return out;
}

export const DEVICE_DISCLOSURE_FACT_EVENT = "device_disclosure";
export const MAX_DISCLOSURE_ROWS = 40;

export function device_disclosure_fact(opts: { aid: string; rows: any[] }): Record<string, any> {
  const kept = (opts.rows ?? [])
    .filter((row: any) => row && typeof row === "object" && !Array.isArray(row) && String(row?.["message"] ?? "").trim())
    .map((row: any) => ({
      tier: String(row?.["tier"] ?? ""),
      code: String(row?.["reason_code"] ?? row?.["code"] ?? ""),
      message: String(row?.["message"] ?? "").slice(0, MAX_DISCLOSURE_MESSAGE_CHARS),
      locator: String(row?.["locator"] ?? ""),
    }));
  return { ev: DEVICE_DISCLOSURE_FACT_EVENT, aid: String(opts.aid ?? ""), rows: kept.slice(0, MAX_DISCLOSURE_ROWS), row_count: kept.length };
}

export function observation_pairing_unavailable_disclosure(): Record<string, any> {
  return _disclosure("T4", "observation_pairing_unavailable");
}

export const MECHANICAL_FINDING_CODES = ["feature_prerequisite_missing", "query_target_not_listener", "trigger_host_not_paired_with_target", "query_target_not_on_device", "bed_facts_unavailable"];
export const PREREQUISITE_RULE_CODES: Record<string, string> = { enabling_step_present: "feature_prerequisite_missing", query_target_bound_to_head: "query_target_not_listener" };
export const MAX_MECHANICAL_FINDINGS = 12;
export const MAX_FINDING_BLOCKS = 12;
export const MAX_FINDING_BLOCK_INDEX = 4096;
export const MAX_FINDING_NAMES = 12;
export const MAX_FINDING_NAME_CHARS = 64;
export const MAX_FINDING_LOCATOR_CHARS = 256;
export const MAX_FINDING_QUOTE_CHARS = 1200;
export const MAX_FINDING_ROW_BYTES = 32 * 1024;
export const MAX_MECHANICAL_FINDINGS_BYTES = MAX_MECHANICAL_FINDINGS * MAX_FINDING_ROW_BYTES + 4096;
export const PREREQUISITE_FINDING_FACT_EVENT = "prerequisite_finding";
export const MECHANICAL_FINDINGS_SCHEMA = "ist.mechanical-findings";

function _normIp(value: any): string {
  const text = String(value ?? "").trim().replace(/^\[|\]$/g, "");
  // simple IPv4/IPv6 validation
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(text) || text.includes(":")) return text;
  return "";
}

function _blockCommands(block: any): string[] {
  const out: string[] = [];
  const single = block?.["cmd"];
  if (typeof single === "string" && single.trim()) out.push(single);
  for (const item of block?.["cmds"] ?? []) {
    if (typeof item === "string" && item.trim()) out.push(item);
  }
  if (String(block?.["kind"] ?? "").trim().toUpperCase() === "STEP") {
    try {
      const { _DUT_HOSTS } = require("./blocks");
      const { _is_config_establishing_block } = require("./mechanical_case_gate");
      if (_is_config_establishing_block(block, _DUT_HOSTS)) {
        for (const line of String(block?.["G"] ?? "").split(/\r?\n/)) {
          if (line.trim()) out.push(line);
        }
      }
    } catch {
      return out;
    }
  }
  return out;
}

function _resolverQueries(command: string, predicate: any): string[] {
  const { norm_command_tokens } = require("./vendor_stdlib");
  if (String(predicate?.["evaluator"] ?? "") !== "resolver_query") return [];
  const tools = new Set((predicate?.["query_tools"] ?? []).filter((t: any) => String(t ?? "").trim()).map((t: any) => String(t).toLowerCase()));
  const marker = String(predicate?.["server_marker"] ?? "");
  if (!tools.size || marker.length !== 1) return [];
  const tokens = norm_command_tokens(command);
  const out: string[] = [];
  for (let index = 0; index < tokens.length; index++) {
    if (!tools.has(tokens[index].toLowerCase())) continue;
    for (let offset = index + 1; offset < tokens.length; offset++) {
      const candidate = tokens[offset];
      if (tools.has(candidate.toLowerCase())) break;
      if (candidate.startsWith(marker)) {
        const target = _normIp(candidate.slice(marker.length));
        if (target) out.push(target);
        break;
      }
    }
  }
  return out;
}

class _BedPairing {
  available = false;
  triggerHosts: Set<string> = new Set();
  paired: Record<string, string[]> = {};
  carried: Record<string, string> = {};

  constructor(bedFacts: any) {
    if (!bedFacts || typeof bedFacts !== "object" || Array.isArray(bedFacts)) return;
    const reach = bedFacts["reachability"];
    const rows = reach && typeof reach === "object" && !Array.isArray(reach) ? reach["listener_trigger_pairs"] : null;
    if (Array.isArray(rows)) {
      for (const row of rows) {
        if (!row || typeof row !== "object" || Array.isArray(row)) continue;
        const listener = _normIp(row["listener_ip"]);
        const hosts = (row["trigger_hosts"] ?? []).map((h: any) => String(h ?? "").trim().toLowerCase()).filter((h: string) => h);
        if (!listener) continue;
        this.paired[listener] = hosts;
        hosts.forEach((h: string) => this.triggerHosts.add(h));
      }
    }
    for (const row of bedFacts["target_device_carried_addresses"] ?? []) {
      if (!row || typeof row !== "object" || Array.isArray(row)) continue;
      const device = String(row["device"] ?? "").trim();
      for (const address of row["addresses"] ?? []) {
        const normalized = _normIp(address);
        if (normalized && !(normalized in this.carried)) this.carried[normalized] = device;
      }
    }
    const listenerOwners = new Set(Object.keys(this.paired).filter((a) => a in this.carried).map((a) => this.carried[a]));
    for (const row of bedFacts["target_device_carried_addresses"] ?? []) {
      if (!row || typeof row !== "object" || Array.isArray(row)) continue;
      const device = String(row["device"] ?? "").trim();
      if (device && !listenerOwners.has(device)) this.triggerHosts.add(device.toLowerCase());
    }
    this.available = Object.keys(this.paired).length > 0 && this.triggerHosts.size > 0;
  }
}

function _prerequisiteFacts(): Record<string, any>[] {
  return characteristic_facts().filter((f: any) => String(f?.["characteristic_class"] ?? "") === "prerequisites" && f?.["enabling_command_heads"] && String(f?.["prerequisite_rule"] ?? "") in PREREQUISITE_RULE_CODES);
}

function _observationPredicate(ident: string): Record<string, any> | null {
  const data = load_device_characteristics();
  for (const row of data?.["observation_predicates"] ?? []) {
    if (row && typeof row === "object" && !Array.isArray(row) && String(row["id"] ?? "") === String(ident ?? "")) return { ...row };
  }
  return null;
}

function _finding(code: string, opts: { fact?: any } & Record<string, any> = {}): Record<string, any> {
  if (!MECHANICAL_FINDING_CODES.includes(code)) {
    throw new Error(`mechanical finding code is outside the closed set: ${JSON.stringify(code)}`);
  }
  const fact = opts.fact ?? {};
  const row: Record<string, any> = {
    code,
    fact_id: _text(fact["id"], MAX_FINDING_LOCATOR_CHARS),
    locator: _text(fact["locator"], MAX_FINDING_LOCATOR_CHARS),
    quote: _text(fact["quote"], MAX_FINDING_QUOTE_CHARS),
    text: _text(fact["text"], MAX_FINDING_QUOTE_CHARS),
  };
  for (const [key, value] of Object.entries(opts)) {
    if (key === "fact" || value === "" || value === null || value === undefined) continue;
    if (key === "host" || key === "target") {
      row[key] = _text(value, MAX_FINDING_NAME_CHARS);
    } else if (key === "paired_hosts") {
      row[key] = (value ?? []).map((name: any) => _text(name, MAX_FINDING_NAME_CHARS)).slice(0, MAX_FINDING_NAMES);
    } else {
      row[key] = value;
    }
  }
  return row;
}

export function mechanical_findings(kase: any, opts: { bed_facts?: any } = {}): Record<string, any>[] {
  const { object_kind_offset_in_command: _segmentOffset, object_kind_segments: _kindSegments } = require("./scenario_fidelity");
  const { command_role_atlas } = require("./step_structure");
  const { norm_command_tokens } = require("./vendor_stdlib");
  if (!kase || typeof kase !== "object" || Array.isArray(kase)) return [];
  const blocks = (kase["blocks"] ?? []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r));
  if (!blocks.length) return [];
  const facts = _prerequisiteFacts();
  if (!facts.length) return [];
  const atlas = command_role_atlas();
  const bed = new _BedPairing(opts.bed_facts);
  const initTokens = (kase["init_commands"] ?? []).filter((i: any) => String(i ?? "").trim()).map((i: any) => norm_command_tokens(String(i)));
  const blockTokens: string[][][] = blocks.map((block: any) => _blockCommands(block).map((command: string) => norm_command_tokens(command)));
  const allTokens = [...initTokens, ...blockTokens.flat()];
  const out: Record<string, any>[] = [];
  const seen = new Set<string>();

  function _add(row: Record<string, any>): void {
    const key = `${row["code"]}|${row["fact_id"]}|${row["target"]}|${row["host"]}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(row);
  }
  const predicates: any[] = [];
  for (const fact of facts) {
    const predicate = _observationPredicate(String(fact?.["observation_predicate"] ?? ""));
    if (!predicate) continue;
    predicates.push(predicate);
    const queries = _triggerQueries(blocks, predicate, bed);
    if (!queries.length) continue;
    const kinds = (fact?.["applies_to"]?.["object_kinds"] ?? []).map((kind: string) => _kindSegments(kind));
    const configured: number[] = [];
    for (let index = 0; index < blockTokens.length; index++) {
      for (const tokens of blockTokens[index]) {
        if (atlas !== null && atlas.command_class(tokens) !== "write") continue;
        if (kinds.some((segments: any) => segments && _segmentOffset(segments, tokens) >= 0)) {
          configured.push(index);
          break;
        }
      }
    }
    if (!configured.length) continue;
    const heads = (fact?.["enabling_command_heads"] ?? []).map((h: string) => String(h).split(/\s+/));
    const rule = String(fact?.["prerequisite_rule"] ?? "");
    const code = PREREQUISITE_RULE_CODES[rule] ?? "";
    if (!code) continue;
    if (rule === "enabling_step_present") {
      const seenHeads = new Set<string>();
      for (const head of heads) {
        for (const tokens of allTokens) {
          if (head.length <= tokens.length && JSON.stringify(tokens.slice(0, head.length)) === JSON.stringify(head)) {
            seenHeads.add(head.join(" "));
          }
        }
      }
      if (seenHeads.size) continue;
      _add(_finding(code, { fact, configured_blocks: [...new Set(configured)].sort((a, b) => a - b).slice(0, MAX_FINDING_BLOCKS), observed_blocks: [...new Set(queries.map((q) => q[0]))].sort((a, b) => a - b).slice(0, MAX_FINDING_BLOCKS) }));
    } else {
      const bound = new Set<string>();
      for (const head of heads) {
        for (const tokens of allTokens) {
          if (tokens.length > head.length && JSON.stringify(tokens.slice(0, head.length)) === JSON.stringify(head)) {
            bound.add(_normIp(tokens[head.length]));
          }
        }
      }
      bound.delete("");
      for (const target of [...new Set(queries.map((q) => q[2]))].sort().filter((t) => !bound.has(t))) {
        _add(_finding(code, { fact, target, observed_blocks: [...new Set(queries.filter((q) => q[2] === target).map((q) => q[0]))].sort((a, b) => a - b).slice(0, MAX_FINDING_BLOCKS) }));
      }
    }
  }
  const queries = [...new Set(predicates.flatMap((p) => _triggerQueries(blocks, p, bed)))].sort();
  if (!queries.length) return out.slice(0, MAX_MECHANICAL_FINDINGS);
  if (!bed.available) {
    _add(_finding("bed_facts_unavailable"));
    return out.slice(0, MAX_MECHANICAL_FINDINGS);
  }
  for (const target of [...new Set(queries.map((q) => q[2]))].sort()) {
    const hosts = [...new Set(queries.filter((q) => q[2] === target && q[1]).map((q) => q[1]))].sort();
    const paired = bed.paired[target];
    if (paired === undefined) {
      if (target in bed.carried) continue;
      for (const host of hosts) {
        _add(_finding("query_target_not_on_device", { host, target, observed_blocks: [...new Set(queries.filter((q) => q[2] === target && q[1] === host).map((q) => q[0]))].sort((a, b) => a - b).slice(0, MAX_FINDING_BLOCKS) }));
      }
      continue;
    }
    const allowed = new Set(paired);
    for (const host of hosts) {
      if (allowed.has(host)) continue;
      _add(_finding("trigger_host_not_paired_with_target", { host, target, paired_hosts: paired, observed_blocks: [...new Set(queries.filter((q) => q[2] === target && q[1] === host).map((q) => q[0]))].sort((a, b) => a - b).slice(0, MAX_FINDING_BLOCKS) }));
    }
  }
  return out.slice(0, MAX_MECHANICAL_FINDINGS);
}

function _triggerQueries(blocks: any[], predicate: any, bed: _BedPairing): [number, string, string][] {
  const queries: [number, string, string][] = [];
  for (let index = 0; index < blocks.length; index++) {
    const block = blocks[index];
    const host = String(block?.["host"] ?? "").trim().toLowerCase();
    if (!String(block?.["kind"] ?? "").startsWith("OBSERVE")) continue;
    if (bed.available && !bed.triggerHosts.has(host)) continue;
    if (!bed.available && !host) continue;
    for (const command of _blockCommands(block)) {
      for (const target of _resolverQueries(command, predicate)) {
        if (bed.available && !(target in bed.paired) && target in bed.carried) continue;
        queries.push([index, host, target]);
      }
    }
  }
  return queries;
}

function _findingBlockIndices(values: any): number[] {
  const out: number[] = [];
  for (const value of values ?? []) {
    let index: number;
    try {
      index = Number(value);
      if (!Number.isInteger(index)) continue;
    } catch {
      continue;
    }
    if (index >= 0 && index <= MAX_FINDING_BLOCK_INDEX) out.push(index);
    if (out.length >= MAX_FINDING_BLOCKS) break;
  }
  return out;
}

export function prerequisite_finding_fact(opts: { aid: string; findings: any[] }): Record<string, any> {
  const { mechanical_finding_cn } = require("../ist_core/display_lexicon");
  const kept: Record<string, any>[] = [];
  for (const row of opts.findings ?? []) {
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const code = String(row["code"] ?? "");
    if (!MECHANICAL_FINDING_CODES.includes(code)) continue;
    const message = String(mechanical_finding_cn(row) ?? "").slice(0, MAX_DISCLOSURE_MESSAGE_CHARS);
    if (!message.trim()) continue;
    kept.push({
      code,
      fact_id: _text(row["fact_id"], MAX_FINDING_LOCATOR_CHARS),
      locator: _text(row["locator"], MAX_FINDING_LOCATOR_CHARS),
      message,
      text: _text(row["text"], MAX_DISCLOSURE_MESSAGE_CHARS),
      host: _text(row["host"], MAX_FINDING_NAME_CHARS),
      target: _text(row["target"], MAX_FINDING_NAME_CHARS),
      paired_hosts: (row["paired_hosts"] ?? []).map((name: any) => _text(name, MAX_FINDING_NAME_CHARS)).slice(0, MAX_FINDING_NAMES),
      configured_blocks: _findingBlockIndices(row["configured_blocks"]),
      observed_blocks: _findingBlockIndices(row["observed_blocks"]),
    });
  }
  return { ev: PREREQUISITE_FINDING_FACT_EVENT, aid: String(opts.aid ?? ""), rows: kept.slice(0, MAX_MECHANICAL_FINDINGS), row_count: kept.length };
}

export function flatten_tiers(tiers: Record<string, any[]>): Record<string, any>[] {
  const out: Record<string, any>[] = [];
  for (const tier of TIERS) {
    for (const row of tiers?.[tier] ?? []) {
      if (row && typeof row === "object" && !Array.isArray(row)) out.push({ ...row });
    }
  }
  return out;
}
