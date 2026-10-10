#!/usr/bin/env node
// 生成：tools/extract_engine.py ← InfoTest scripts/gen_device_characteristics.py（sha256 6a03bb492c0dcfba）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import { MAX_PINNED_SOURCE_BYTES, PINNED_SOURCE_ROOTS, pinned_source_is_confined } from "../case_compiler/device_characteristics";

const ROOT = _cex_data_path("");
const DEFAULT_SOURCE = path.join(ROOT, "scripts", "data", "device_characteristics_source.json");
const DEFAULT_OUTPUT = path.join(ROOT, "knowledge", "data", "compile_ref", "device_characteristics.json");
const SCHEMA = "ist.device-characteristics";
const SOURCE_SCHEMA = "ist.device-characteristics-source";
const PINNED_ROOTS: Record<string, string[]> = Object.fromEntries(Object.entries(PINNED_SOURCE_ROOTS).map(([k, v]) => [k, [v] as string[]]));
const PINNED_KINDS = ["manual", "spec", "device"];
const EVALUATORS = ["structure_signal", "weight_declarations", "stated_tokens"];
const OBSERVATION_EVALUATORS = ["resolver_query"];
const PREREQUISITE_RULES = ["enabling_step_present", "query_target_bound_to_head"];
const MAX_QUOTE_CHARS = 1200;
const FIELD_WINDOW_CHARS = 4000;
const HEAD_WINDOW_CHARS = 600;
const _ID_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+){1,11}$/;
const _TAG_RE = /<[^>]{1,200}>/g;
const _LEAD_RE = /^[>\-*\s]+/;
const _WS_RE = /\s+/g;

export class DeviceCharacteristicsError extends Error {}

function _sha256_bytes(raw: Buffer): string {
  return crypto.createHash("sha256").update(raw).digest("hex");
}

function _read_json(filePath: string): Record<string, any> {
  let value: any;
  try {
    value = JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (exc) {
    throw new DeviceCharacteristicsError(`unreadable JSON source: ${filePath}`);
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new DeviceCharacteristicsError(`JSON source must be an object: ${filePath}`);
  }
  return value;
}

export function plain_text(quote: string): string {
  const stripped = String(quote ?? "").replace(_TAG_RE, " ");
  const lines = stripped.split(/\r?\n/).map((line) => line.replace(_LEAD_RE, ""));
  return lines.join(" ").replace(_WS_RE, " ").trim();
}

function _ground(rel: string, quote: string): Record<string, any> {
  const { read_regular_nofollow } = require("../case_compiler/_sealed_io") as any;
  const { ground_source_span } = require("../case_compiler/mindmap_contract_projector") as any;
  if (!rel || !quote.trim()) {
    throw new DeviceCharacteristicsError(`characteristic has no bounded source: ${JSON.stringify(rel)}`);
  }
  if (!pinned_source_is_confined(rel)) {
    throw new DeviceCharacteristicsError(`characteristic source escapes the pinned documentation trees: ${rel}`);
  }
  if (quote.length > MAX_QUOTE_CHARS) {
    throw new DeviceCharacteristicsError(`characteristic quote exceeds ${MAX_QUOTE_CHARS} characters: ${rel}`);
  }
  const raw = read_regular_nofollow(rel, {
    errorType: DeviceCharacteristicsError,
    invalidMessage: `characteristic source is not a repo file: ${rel}`,
    directoryMessage: `characteristic source is not a repo file: ${rel}`,
    openMessage: `characteristic source is not a readable regular file: ${rel}`,
    boundsMessage: `characteristic source is out of bounds: ${rel}`,
    changedMessage: `characteristic source changed while reading: ${rel}`,
    maxBytes: MAX_PINNED_SOURCE_BYTES,
    trustedRoot: ROOT,
  });
  let text: string;
  try {
    text = raw.toString("utf8");
  } catch (exc) {
    throw new DeviceCharacteristicsError(`characteristic source is not utf-8: ${rel}`);
  }
  const span = ground_source_span(quote, text, { origin: "manual" });
  if (span === null) {
    throw new DeviceCharacteristicsError(`characteristic quote is not grounded in its source: ${rel}`);
  }
  const lineStart = text.slice(0, span.start).split("\n").length;
  const lineEnd = text.slice(0, span.end).split("\n").length;
  return {
    source_path: rel,
    source_sha256: _sha256_bytes(raw),
    source_span: span,
    line_start: lineStart,
    line_end: lineEnd,
    locator: lineStart === lineEnd ? `${rel}:${lineStart}` : `${rel}:${lineStart}-${lineEnd}`,
    _text: text,
    _quote: quote,
  };
}

function _closed_ids(rows: any, what: string): Array<Record<string, string>> {
  if (!Array.isArray(rows) || !rows.length) {
    throw new DeviceCharacteristicsError(`${what} closed set is unavailable`);
  }
  const out: Array<Record<string, string>> = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (typeof row !== "object" || row === null || Object.keys(row).length !== 2 || !("id" in row) || !("label_zh" in row)) {
      throw new DeviceCharacteristicsError(`${what} entry fields are not closed`);
    }
    const ident = String(row.id ?? "").trim();
    const label = String(row.label_zh ?? "").trim();
    if (!ident || seen.has(ident) || !label) {
      throw new DeviceCharacteristicsError(`${what} entry identity is invalid: ${JSON.stringify(ident)}`);
    }
    seen.add(ident);
    out.push({ id: ident, label_zh: label });
  }
  return out;
}

function _predicates(rows: any): Array<Record<string, any>> {
  if (!Array.isArray(rows) || !rows.length) {
    throw new DeviceCharacteristicsError("structure predicates are unavailable");
  }
  const out: Array<Record<string, any>> = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (typeof row !== "object" || row === null) {
      throw new DeviceCharacteristicsError("structure predicate must be an object");
    }
    const ident = String(row.id ?? "").trim();
    const label = String(row.label_zh ?? "").trim();
    const evaluator = String(row.evaluator ?? "").trim();
    if (!ident || seen.has(ident) || !label || !EVALUATORS.includes(evaluator)) {
      throw new DeviceCharacteristicsError(`structure predicate identity or evaluator is invalid: ${JSON.stringify(ident)}`);
    }
    seen.add(ident);
    const spec: Record<string, any> = { id: ident, label_zh: label, evaluator };
    if (evaluator === "structure_signal") {
      const roles = (row.roles ?? []).map(String);
      const classes = (row.command_classes ?? []).map(String);
      if (!roles.length && !classes.length) {
        throw new DeviceCharacteristicsError(`structure signal predicate names no role or command class: ${ident}`);
      }
      const { ROLE_COMMAND_CLASSES, STRUCTURE_OBJECT_ROLES } = require("../case_compiler/step_structure") as any;
      const knownClasses = new Set(Object.values(ROLE_COMMAND_CLASSES).flat());
      if (!roles.every((r: string) => (STRUCTURE_OBJECT_ROLES as string[]).includes(r))) {
        throw new DeviceCharacteristicsError(`structure signal predicate names an unknown role: ${ident}`);
      }
      if (!classes.every((c: string) => (knownClasses as Set<string>).has(c))) {
        throw new DeviceCharacteristicsError(`structure signal predicate names an unknown command class: ${ident}`);
      }
      spec.roles = [...new Set(roles)].sort();
      spec.command_classes = [...new Set(classes)].sort();
    } else if (evaluator === "weight_declarations") {
      const least = row.distinct_at_least;
      if (typeof least !== "number" || least < 2) {
        throw new DeviceCharacteristicsError(`weight predicate needs at least two distinct declarations: ${ident}`);
      }
      spec.distinct_at_least = least;
    } else {
      const groups = row.token_groups;
      const match = String(row.match ?? "");
      if (!Array.isArray(groups) || !groups.length || !["all", "any"].includes(match) || groups.some((g: any) => !Array.isArray(g) || !g.length || g.some((t: any) => typeof t !== "string" || !t.trim() || t !== t.toLowerCase()))) {
        throw new DeviceCharacteristicsError(`token predicate groups are invalid: ${ident}`);
      }
      spec.match = match;
      spec.token_groups = groups.map((g: any) => [...new Set(g.map(String))].sort());
    }
    out.push(spec);
  }
  return out;
}

function _observation_predicates(rows: any): Array<Record<string, any>> {
  if (!Array.isArray(rows) || !rows.length) {
    throw new DeviceCharacteristicsError("observation predicates are unavailable");
  }
  const out: Array<Record<string, any>> = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (typeof row !== "object" || row === null) {
      throw new DeviceCharacteristicsError("observation predicate must be an object");
    }
    const ident = String(row.id ?? "").trim();
    const label = String(row.label_zh ?? "").trim();
    const evaluator = String(row.evaluator ?? "").trim();
    const provenance = String(row.provenance ?? "").trim();
    if (!ident || seen.has(ident) || !label || !OBSERVATION_EVALUATORS.includes(evaluator) || !provenance) {
      throw new DeviceCharacteristicsError(`observation predicate identity, evaluator or provenance is invalid: ${JSON.stringify(ident)}`);
    }
    seen.add(ident);
    if (Object.keys(row).length !== 6 || !["id", "label_zh", "evaluator", "query_tools", "server_marker", "provenance"].every((k) => k in row)) {
      throw new DeviceCharacteristicsError(`observation predicate fields are not closed: ${ident}`);
    }
    const tools = row.query_tools;
    const marker = String(row.server_marker ?? "");
    if (!Array.isArray(tools) || !tools.length || tools.some((t: any) => typeof t !== "string" || !t.trim() || t !== t.toLowerCase() || t.split(/\s+/).length !== 1) || marker.length !== 1 || /[a-zA-Z0-9]/.test(marker)) {
      throw new DeviceCharacteristicsError(`resolver query predicate tools or marker are invalid: ${ident}`);
    }
    out.push({ id: ident, label_zh: label, evaluator, query_tools: [...new Set(tools.map(String))].sort(), server_marker: marker, provenance });
  }
  return out;
}

function _destructive_patterns(): RegExp[] {
  const { load_grammar } = require("../case_compiler/domain_grammar") as any;
  const raw = (load_grammar().destructive_commands ?? {}).patterns ?? [];
  const compiled = raw.filter((p: any) => String(p ?? "").trim()).map((p: any) => new RegExp(String(p), "i"));
  if (!compiled.length) {
    throw new DeviceCharacteristicsError("domain grammar carries no destructive_commands.patterns entries");
  }
  return compiled;
}

function _prerequisite(row: Record<string, any>, anchor: Record<string, any>, heads: Record<string, any>, predicateIds: Set<string>, ident: string): Record<string, any> {
  const { norm_command_tokens } = require("../case_compiler/vendor_stdlib") as any;
  const rawHeads = row.enabling_command_heads;
  const rule = String(row.prerequisite_rule ?? "");
  const predicate = String(row.observation_predicate ?? "");
  if (!Array.isArray(rawHeads) || !rawHeads.length || rawHeads.some((h: any) => typeof h !== "string" || !h.trim())) {
    throw new DeviceCharacteristicsError(`a prerequisite names at least one enabling command head: ${ident}`);
  }
  if (!PREREQUISITE_RULES.includes(rule)) {
    throw new DeviceCharacteristicsError(`prerequisite rule is outside the closed set: ${ident} (${JSON.stringify(rule)})`);
  }
  if (!predicateIds.has(predicate)) {
    throw new DeviceCharacteristicsError(`prerequisite names an observation predicate outside the closed set: ${ident} (${JSON.stringify(predicate)})`);
  }
  const text = String(anchor._text ?? "");
  const span = anchor.source_span ?? {};
  const start = Math.max(0, (span.start ?? 0) - HEAD_WINDOW_CHARS);
  const end = (span.end ?? 0) + HEAD_WINDOW_CHARS;
  const section = text.slice(start, end).toLowerCase();
  const destructive = _destructive_patterns();
  const normalized: string[] = [];
  for (const head of rawHeads) {
    const tokens = norm_command_tokens(head);
    const joined = tokens.join(" ");
    if (!joined || !(joined in heads)) {
      throw new DeviceCharacteristicsError(`enabling command head is not in the device command tree: ${ident} (${JSON.stringify(head)})`);
    }
    const matched = destructive.find((p) => p.test(joined));
    if (matched) {
      throw new DeviceCharacteristicsError(`enabling command head matches a destructive command form: ${ident} (${JSON.stringify(head)}, grammar pattern ${JSON.stringify(matched.source)})`);
    }
    for (const token of tokens) {
      if (!new RegExp(`(?<![0-9a-z_])${token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![0-9a-z_])`).test(section)) {
        throw new DeviceCharacteristicsError(`prerequisite quote does not carry its own command: ${ident} (${JSON.stringify(head)}, token ${JSON.stringify(token)})`);
      }
    }
    normalized.push(joined);
  }
  return { enabling_command_heads: [...new Set(normalized)].sort(), prerequisite_rule: rule, observation_predicate: predicate };
}

function _observation(row: Record<string, any>, anchor: Record<string, any>, heads: Record<string, any>): Record<string, any> {
  const { norm_command_tokens } = require("../case_compiler/vendor_stdlib") as any;
  if (Object.keys(row).length !== 3 || !["show_command", "fields", "fields_documented"].every((k) => k in row)) {
    throw new DeviceCharacteristicsError("observation fields are not closed");
  }
  const command = String(row.show_command ?? "").trim();
  const fields = row.fields;
  const documented = row.fields_documented;
  if (typeof documented !== "boolean" || !Array.isArray(fields)) {
    throw new DeviceCharacteristicsError("fields must be a list and fields_documented a boolean");
  }
  const normalized = norm_command_tokens(command).join(" ");
  if (!normalized || !(normalized in heads)) {
    throw new DeviceCharacteristicsError(`counter command is not in the device command tree: ${JSON.stringify(command)}`);
  }
  const names = fields.map(String);
  if (documented) {
    if (!names.length || names.some((n) => !n.trim())) {
      throw new DeviceCharacteristicsError("a documented counter names at least one non-empty field");
    }
    const text = String(anchor._text ?? "");
    const start = anchor.source_span.start;
    const window = text.slice(start, start + FIELD_WINDOW_CHARS);
    for (const name of names) {
      if (!window.includes(name)) {
        throw new DeviceCharacteristicsError(`counter field is not documented next to its command: ${JSON.stringify(name)}`);
      }
    }
  } else if (names.length) {
    throw new DeviceCharacteristicsError("an undocumented counter carries no field name");
  }
  if (!String(anchor._quote ?? "").includes(normalized.split(/\s+/)[0])) {
    throw new DeviceCharacteristicsError(`counter quote does not carry its own command: ${JSON.stringify(command)}`);
  }
  return { show_command: normalized, fields: names, fields_documented: documented };
}

export function build_facts(source: Record<string, any>, objectKinds: Set<string>, heads: Record<string, any>, behaviourIds: Set<string>, characteristicIds: Set<string>, predicateIds: Set<string>, observationPredicateIds: Set<string>): Array<Record<string, any>> {
  const rows = source.facts;
  if (!Array.isArray(rows) || !rows.length) {
    throw new DeviceCharacteristicsError("the characteristic table is empty");
  }
  const out: Array<Record<string, any>> = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (typeof row !== "object" || row === null) {
      throw new DeviceCharacteristicsError("characteristic must be an object");
    }
    const allowed = new Set(["id", "characteristic_class", "pinned", "source_path", "quote", "applies_to", "observation", "enabling_command_heads", "prerequisite_rule", "observation_predicate"]);
    const required = new Set(["id", "characteristic_class", "pinned", "source_path", "quote", "applies_to"]);
    if (!Object.keys(row).every((k) => allowed.has(k)) || ![...required].every((k) => k in row)) {
      throw new DeviceCharacteristicsError("characteristic fields are not closed");
    }
    const ident = String(row.id ?? "");
    if (!_ID_RE.test(ident) || seen.has(ident)) {
      throw new DeviceCharacteristicsError(`characteristic id is invalid: ${JSON.stringify(ident)}`);
    }
    seen.add(ident);
    const cls = String(row.characteristic_class ?? "");
    if (!characteristicIds.has(cls)) {
      throw new DeviceCharacteristicsError(`characteristic class is outside the closed set: ${cls}`);
    }
    const pinned = String(row.pinned ?? "");
    if (!PINNED_KINDS.includes(pinned)) {
      throw new DeviceCharacteristicsError(`pinned kind is invalid: ${pinned}`);
    }
    if (pinned === "device") {
      throw new DeviceCharacteristicsError("a device-pinned characteristic cannot be issued: device echoes record actual only and sign nothing");
    }
    const rel = String(row.source_path ?? "");
    if (!pinned_source_is_confined(rel) || !PINNED_ROOTS[pinned].some((prefix) => rel.startsWith(prefix))) {
      throw new DeviceCharacteristicsError(`a ${pinned}-pinned characteristic must cite that tree: ${rel}`);
    }
    const anchor = _ground(rel, String(row.quote ?? ""));
    const applies = row.applies_to;
    if (typeof applies !== "object" || applies === null || Object.keys(applies).length !== 3 || !["object_kinds", "behaviour_classes", "structure_predicates"].every((k) => k in applies)) {
      throw new DeviceCharacteristicsError(`applies_to fields are not closed: ${ident}`);
    }
    const kinds = [...new Set((applies.object_kinds ?? []).map(String))].sort();
    const classes = [...new Set((applies.behaviour_classes ?? []).map(String))].sort();
    const predicates = [...new Set((applies.structure_predicates ?? []).map(String))].sort();
    if (!kinds.length || !kinds.every((k) => objectKinds.has(k as string))) {
      throw new DeviceCharacteristicsError(`characteristic names an object kind outside the command tree: ${ident}`);
    }
    if (!classes.every((c) => behaviourIds.has(c as string))) {
      throw new DeviceCharacteristicsError(`characteristic names a behaviour class outside the closed set: ${ident}`);
    }
    if (!predicates.every((p) => predicateIds.has(p as string))) {
      throw new DeviceCharacteristicsError(`characteristic names a structure predicate outside the closed set: ${ident}`);
    }
    const fact: Record<string, any> = {
      id: ident,
      characteristic_class: cls,
      pinned,
      locator: anchor.locator,
      source_path: anchor.source_path,
      source_sha256: anchor.source_sha256,
      line_start: anchor.line_start,
      line_end: anchor.line_end,
      source_span: anchor.source_span,
      quote: String(row.quote ?? ""),
      text: plain_text(String(row.quote ?? "")),
      applies_to: { object_kinds: kinds, behaviour_classes: classes, structure_predicates: predicates },
    };
    const prerequisiteKeys = new Set(["enabling_command_heads", "prerequisite_rule", "observation_predicate"].filter((k) => k in row));
    if (prerequisiteKeys.size) {
      if (cls !== "prerequisites") {
        throw new DeviceCharacteristicsError(`only a prerequisites characteristic carries an enabling command head: ${ident}`);
      }
      if (prerequisiteKeys.size !== 3) {
        throw new DeviceCharacteristicsError(`a prerequisite declares its heads, its rule and its observation predicate together: ${ident}`);
      }
      Object.assign(fact, _prerequisite(row, anchor, heads, observationPredicateIds, ident));
    } else if (cls === "prerequisites") {
      throw new DeviceCharacteristicsError(`a prerequisites characteristic must name its enabling command head, its rule and its observation predicate: ${ident}`);
    }
    if ("observation" in row) {
      if (cls !== "observation_surface") {
        throw new DeviceCharacteristicsError(`only an observation_surface characteristic carries a counter: ${ident}`);
      }
      const observation = row.observation;
      if (typeof observation !== "object" || observation === null) {
        throw new DeviceCharacteristicsError(`observation must be an object: ${ident}`);
      }
      fact.observation = _observation(observation, anchor, heads);
    } else if (cls === "observation_surface") {
      throw new DeviceCharacteristicsError(`an observation_surface characteristic must name its counter: ${ident}`);
    }
    out.push(fact);
  }
  return out;
}

export function generate_projection(sourcePath: string = DEFAULT_SOURCE): Record<string, any> {
  const { object_kind_closed_set } = require("../case_compiler/step_structure") as any;
  const { diagnose_active_command_tree, load_vendor_stdlib } = require("../case_compiler/vendor_stdlib") as any;
  const source = _read_json(sourcePath);
  if (String(source.schema ?? "") !== SOURCE_SCHEMA) {
    throw new DeviceCharacteristicsError("characteristic source schema is unexpected");
  }
  const objectKinds = object_kind_closed_set();
  const inventory = load_vendor_stdlib();
  if (!objectKinds.size || typeof inventory !== "object" || inventory === null) {
    const [_status, detail] = diagnose_active_command_tree();
    throw new DeviceCharacteristicsError("the device command tree is unavailable; object kinds cannot be validated" + (detail ? `（${detail}）` : ""));
  }
  const heads = inventory.headers;
  if (typeof heads !== "object" || heads === null || !Object.keys(heads).length) {
    throw new DeviceCharacteristicsError("the device command tree carries no heads");
  }
  const behaviourClasses = _closed_ids(source.behaviour_classes, "behaviour class");
  const characteristicClasses = (source.characteristic_classes ?? []).map(String);
  if (!characteristicClasses.length || new Set(characteristicClasses).size !== characteristicClasses.length) {
    throw new DeviceCharacteristicsError("characteristic classes are not a closed set");
  }
  const predicates = _predicates(source.structure_predicates);
  const observationPredicates = _observation_predicates(source.observation_predicates);
  const facts = build_facts(source, objectKinds, heads, new Set(behaviourClasses.map((r) => r.id)), new Set(characteristicClasses), new Set(predicates.map((r) => r.id)), new Set(observationPredicates.map((r) => r.id)));
  const byKind: Record<string, string[]> = {};
  const byClass: Record<string, string[]> = {};
  const byPredicate: Record<string, string[]> = {};
  for (const fact of facts) {
    for (const kind of fact.applies_to.object_kinds) {
      (byKind[kind] ??= []).push(fact.id);
    }
    for (const cls of fact.applies_to.behaviour_classes) {
      (byClass[cls] ??= []).push(fact.id);
    }
    for (const predicate of fact.applies_to.structure_predicates) {
      (byPredicate[predicate] ??= []).push(fact.id);
    }
  }
  const pinnedSources: Record<string, string> = {};
  for (const fact of facts) {
    pinnedSources[fact.source_path] = fact.source_sha256;
  }
  const payload: Record<string, any> = {
    schema: SCHEMA,
    generator: "scripts/gen_device_characteristics.py",
    authority: { can_sign_expected: false, mechanical_enforcement: false },
    identity: {
      source_path: path.relative(ROOT, sourcePath).replace(/\\/g, "/"),
      source_sha256: _sha256_bytes(fs.readFileSync(sourcePath)),
      version_family: String(inventory.version ?? ""),
      device_build: String(inventory.device_os_build ?? ""),
      object_kind_count: objectKinds.size,
      pinned_sources: Object.fromEntries(Object.entries(pinnedSources).sort(([a], [b]) => a.localeCompare(b))),
    },
    behaviour_classes: behaviourClasses,
    characteristic_classes: characteristicClasses,
    structure_predicates: predicates,
    observation_predicates: observationPredicates,
    prerequisite_rules: [...PREREQUISITE_RULES],
    facts,
    index: {
      by_object_kind: Object.fromEntries(Object.entries(byKind).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, [...new Set(v)].sort()])),
      by_behaviour_class: Object.fromEntries(Object.entries(byClass).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, [...new Set(v)].sort()])),
      by_structure_predicate: Object.fromEntries(Object.entries(byPredicate).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, [...new Set(v)].sort()])),
    },
  };
  const body = Buffer.from(JSON.stringify(payload, null, 0), "utf8");
  payload.projection_sha256 = _sha256_bytes(body);
  return payload;
}

export function render_projection(payload: Record<string, any>): string {
  return JSON.stringify(payload, null, 2) + "\n";
}

export function build(): Record<string, any> {
  return generate_projection();
}

function _write_atomic(filePath: string, raw: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temp = path.join(path.dirname(filePath), `.${path.basename(filePath)}.tmp`);
  try {
    fs.writeFileSync(temp, raw, "utf8");
    fs.renameSync(temp, filePath);
  } finally {
    if (fs.existsSync(temp)) {
      fs.unlinkSync(temp);
    }
  }
}

function _parseArgs(argv: string[]): { source: string; output: string; check: boolean } {
  const args = { source: DEFAULT_SOURCE, output: DEFAULT_OUTPUT, check: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--source" && i + 1 < argv.length) {
      args.source = argv[++i];
    } else if (argv[i] === "--output" && i + 1 < argv.length) {
      args.output = argv[++i];
    } else if (argv[i] === "--check") {
      args.check = true;
    }
  }
  return args;
}

export function main(argv?: string[]): number {
  const args = _parseArgs(argv ?? process.argv.slice(2));
  const rendered = render_projection(generate_projection(args.source));
  if (args.check) {
    if (!fs.statSync(args.output).isFile() || fs.readFileSync(args.output, "utf8") !== rendered) {
      throw new DeviceCharacteristicsError("device characteristic projection is stale; rerun without --check");
    }
    console.log(`checked ${path.relative(ROOT, args.output)}`);
    return 0;
  }
  if (fs.lstatSync(args.output).isSymbolicLink()) {
    throw new DeviceCharacteristicsError("device characteristic projection path must not be a symbolic link");
  }
  let current: string | null = null;
  try {
    current = fs.readFileSync(args.output, "utf8");
  } catch {
    current = null;
  }
  if (current !== rendered) {
    _write_atomic(args.output, rendered);
  }
  console.log(`wrote ${path.relative(ROOT, args.output)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
