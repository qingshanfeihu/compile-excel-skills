import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { runtime_path } from "../common/runtime_paths";

export const BEHAVIOUR_LEDGER_PATH = runtime_path("device_behaviour_classes.jsonl");
export const BEHAVIOUR_RECORD_SCHEMA = "ist.device-behaviour-class";
export const SEED_CLASS_MAP: Record<string, string> = { uniform_rotation: "rotation" };
export const MAX_METHODS_PER_CASE = 8;
export const MAX_BEHAVIOUR_CLASSES = MAX_METHODS_PER_CASE * 2;
export const MAX_PARAGRAPHS_PER_METHOD = 6;
export const MAX_PARAGRAPH_CHARS = 1200;
export const MAX_METHOD_CHARS = 64;
export const MAX_BEHAVIOUR_CLASS_CHARS = 64;
export const MAX_OBJECT_KIND_CHARS = 200;
export const MAX_SOURCE_PATH_CHARS = 400;
export const MAX_LEDGER_BYTES = 8 * 1024 * 1024;
export const LEDGER_OVER_BYTE_CAP = "ledger_over_byte_cap";

export class BehaviourClassError extends Error {}

function _isMap(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _unclassified(): string {
  const { UNCLASSIFIED } = require("./device_characteristics");
  return UNCLASSIFIED;
}

export function case_method_bindings(structure: Array<Record<string, any>>): Array<Record<string, string>> {
  const out: Array<Record<string, string>> = [];
  const seen = new Set<string>();
  for (const entry of structure || []) {
    if (!_isMap(entry)) continue;
    const methods = (entry.stated_conditions || [])
      .filter((item: any) => _isMap(item) && String(item.kind || "") === "algorithm" && String(item.value || "").trim())
      .map((item: any) => String(item.value || "").trim().toLowerCase().slice(0, MAX_METHOD_CHARS));
    if (!methods.length) continue;
    const kinds = (entry.objects || []).filter((item: any) => _isMap(item) && String(item.kind || "").trim()).map((item: any) => String(item.kind || "").trim());
    const kindsList = kinds.length ? kinds : [""];
    for (const method of methods) {
      for (const kind of kindsList) {
        const key = `${method}${kind}`;
        if (seen.has(key) || seen.size >= MAX_METHODS_PER_CASE) continue;
        seen.add(key);
        out.push({ method, object_kind: kind });
      }
    }
  }
  return out;
}

export function method_paragraph_candidates(method: string, object_kind = "", opts: { limit?: number } = {}): Array<Record<string, string>> {
  const limit = opts.limit ?? MAX_PARAGRAPHS_PER_METHOD;
  const token = String(method || "").trim().toLowerCase();
  if (!token || token.length > MAX_METHOD_CHARS) return [];
  const segments = String(object_kind || "").split("/").filter(Boolean);
  const out: Array<Record<string, string>> = [];
  for (const [rel, text] of _documentationSources()) {
    let offset = 0;
    for (const block of text.split("\n\n")) {
      const start = offset;
      offset += block.length + 2;
      const folded = block.toLowerCase();
      const position = _standalonePosition(folded, token);
      if (position < 0) continue;
      const [quote, cut] = _window(block, position, token.length);
      const lineStart = text.slice(0, start + cut).split("\n").length;
      out.push({ source_path: rel, line_start: String(lineStart), quote, _rank: segments.some((seg) => folded.includes(seg)) ? "0" : "1" });
    }
  }
  out.sort((a, b) => {
    if (a._rank !== b._rank) return a._rank < b._rank ? -1 : 1;
    if (a.source_path !== b.source_path) return a.source_path < b.source_path ? -1 : 1;
    return Number(a.line_start) - Number(b.line_start);
  });
  return out.slice(0, limit).map((row) => {
    const { _rank, ...rest } = row;
    return rest;
  });
}

function _standalonePosition(text: string, token: string): number {
  let index = text.indexOf(token);
  while (index >= 0) {
    const before = index > 0 ? text[index - 1] : " ";
    const afterIndex = index + token.length;
    const after = afterIndex < text.length ? text[afterIndex] : " ";
    if (!_wordChar(before) && !_wordChar(after)) return index;
    index = text.indexOf(token, index + 1);
  }
  return -1;
}

function _window(block: string, position: number, length: number): [string, number] {
  if (block.length <= MAX_PARAGRAPH_CHARS) return [block, 0];
  const half = Math.floor((MAX_PARAGRAPH_CHARS - length) / 2);
  let start = Math.max(0, position - half);
  start = Math.min(start, Math.max(0, block.length - MAX_PARAGRAPH_CHARS));
  return [block.slice(start, start + MAX_PARAGRAPH_CHARS), start];
}

function _wordChar(char: string): boolean {
  return /^[A-Za-z0-9_]$/.test(char);
}

function _documentationSources(): Array<[string, string]> {
  const { load_device_characteristics, read_pinned_source_bytes } = require("./device_characteristics");
  const data = load_device_characteristics() || {};
  const pinned = ((data.identity || {}).pinned_sources || {}) as Record<string, string>;
  const out: Array<[string, string]> = [];
  for (const rel of Object.keys(pinned).sort()) {
    try {
      out.push([rel, read_pinned_source_bytes(rel).toString("utf8")]);
    } catch {
      continue;
    }
  }
  return out;
}

export function documentation_sha256(): string {
  const { load_device_characteristics } = require("./device_characteristics");
  const data = load_device_characteristics() || {};
  const pinned = ((data.identity || {}).pinned_sources || {}) as Record<string, string>;
  const joined = Object.keys(pinned).sort().map((rel) => `${rel}:${pinned[rel]}`).join("|");
  return joined ? crypto.createHash("sha256").update(Buffer.from(joined, "utf8")).digest("hex") : "";
}

export function validate_behaviour_classification(rows: any, opts: { asked?: Array<Record<string, string>> } = {}): Array<Record<string, any>> {
  const { behaviour_class_closed_set } = require("./device_characteristics");
  const { ground_source_span } = require("./mindmap_contract_projector");
  const closed = behaviour_class_closed_set();
  const wanted = new Set(
    (opts.asked || []).filter((row) => _isMap(row)).map((row) => `${String(row.method || "").toLowerCase()}${String(row.object_kind || "")}`)
  );
  const sources = Object.fromEntries(_documentationSources());
  const out: Array<Record<string, any>> = [];
  const seen = new Set<string>();
  const rowsList = Array.isArray(rows) ? rows : [];
  for (const row of rowsList) {
    if (!_isMap(row)) continue;
    const method = String(row.method || "").trim().toLowerCase().slice(0, MAX_METHOD_CHARS);
    const objectKind = String(row.object_kind || "").trim();
    if (!method || seen.has(`${method}${objectKind}`)) continue;
    if (wanted.size && !wanted.has(`${method}${objectKind}`)) continue;
    seen.add(`${method}${objectKind}`);
    const behaviour = String(row.behaviour_class || "").trim();
    const rel = String(row.source_path || "").trim();
    const quote = String(row.quote || "").slice(0, MAX_PARAGRAPH_CHARS);
    let reason = "";
    if (closed === null || closed === undefined) {
      reason = "closed_set_unavailable";
    } else if (behaviour === _unclassified()) {
      reason = "declared_unclassified";
    } else if (!closed.has(behaviour)) {
      reason = "class_outside_closed_set";
    } else if (!(rel in sources)) {
      reason = "citation_outside_pinned_documentation";
    } else if (!quote.trim() || ground_source_span(quote, sources[rel], { origin: "manual" }) === null) {
      reason = "citation_not_grounded";
    }
    if (reason) {
      out.push({ method, object_kind: objectKind, behaviour_class: _unclassified(), pinned: "", source_path: "", locator: "", quote: "", reason_code: reason });
      continue;
    }
    const text = sources[rel];
    const span = ground_source_span(quote, text, { origin: "manual" });
    const line = text.slice(0, Number(span.start)).split("\n").length;
    out.push({
      method,
      object_kind: objectKind,
      behaviour_class: behaviour,
      pinned: rel.includes("/spec/") ? "spec" : "manual",
      source_path: rel,
      locator: `${rel}:${line}`,
      quote,
      reason_code: "ok",
    });
  }
  return out;
}

function _ledgerOverByteCap(target: string): boolean {
  try {
    if (fs.lstatSync(target).isSymbolicLink() || !fs.statSync(target).isFile()) return false;
    return Number(fs.statSync(target).size) > MAX_LEDGER_BYTES;
  } catch {
    return false;
  }
}

function _ledgerLines(target: string): string[] {
  if (_ledgerOverByteCap(target)) {
    console.warn(`behaviour class ledger exceeds ${MAX_LEDGER_BYTES} bytes; reason_code=${LEDGER_OVER_BYTE_CAP}`);
    return [];
  }
  let raw: Buffer;
  try {
    if (fs.lstatSync(target).isSymbolicLink() || !fs.statSync(target).isFile()) return [];
    raw = fs.readFileSync(target);
  } catch {
    return [];
  }
  return raw.toString("utf8").split("\n");
}

function _validLedgerRecord(record: any, closed: Set<string> | null): Record<string, any> | null {
  const { pinned_source_is_confined } = require("./device_characteristics");
  if (!_isMap(record)) return null;
  if (String(record.schema || "") !== BEHAVIOUR_RECORD_SCHEMA) return null;
  const method = String(record.method || "");
  const kind = String(record.object_kind || "");
  const behaviour = String(record.behaviour_class || "");
  const rel = String(record.source_path || "");
  const quote = String(record.quote || "");
  if (!method || method.length > MAX_METHOD_CHARS) return null;
  if (kind.length > MAX_OBJECT_KIND_CHARS) return null;
  if (quote.length > MAX_PARAGRAPH_CHARS || rel.length > MAX_SOURCE_PATH_CHARS) return null;
  if (closed === null || !closed.has(behaviour) || behaviour === _unclassified()) return null;
  if (!pinned_source_is_confined(rel)) return null;
  return record;
}

export function load_behaviour_classes(opts: { path?: string | null; documentation_sha?: string } = {}): Map<string, Record<string, any>> {
  const { behaviour_class_closed_set } = require("./device_characteristics");
  const target = opts.path || BEHAVIOUR_LEDGER_PATH;
  const wanted = opts.documentation_sha || documentation_sha256();
  const closed = behaviour_class_closed_set();
  const out = new Map<string, Record<string, any>>();
  for (const line of _ledgerLines(target)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let record: any;
    try {
      record = JSON.parse(trimmed);
    } catch {
      continue;
    }
    const valid = _validLedgerRecord(record, closed);
    if (valid === null) continue;
    if (String(valid.documentation_sha256 || "") !== wanted) continue;
    const key = `${String(valid.method)}${String(valid.object_kind || "")}`;
    if (!out.has(key)) out.set(key, valid);
  }
  return out;
}

export function persist_behaviour_classes(rows: Array<Record<string, any>>, opts: { path?: string | null; documentation_sha?: string } = {}): Array<Record<string, any>> {
  const target = opts.path || BEHAVIOUR_LEDGER_PATH;
  const sha = opts.documentation_sha || documentation_sha256();
  if (_ledgerOverByteCap(target)) {
    console.warn(`behaviour class append skipped; reason_code=${LEDGER_OVER_BYTE_CAP} cap=${MAX_LEDGER_BYTES}`);
    return [];
  }
  const records = (rows || [])
    .filter((row) => _isMap(row) && !["", _unclassified()].includes(String(row.behaviour_class || "")) && String(row.method || ""))
    .map((row) => ({
      schema: BEHAVIOUR_RECORD_SCHEMA,
      method: String(row.method || ""),
      object_kind: String(row.object_kind || ""),
      behaviour_class: String(row.behaviour_class || ""),
      pinned: String(row.pinned || ""),
      source_path: String(row.source_path || ""),
      locator: String(row.locator || ""),
      quote: String(row.quote || ""),
      documentation_sha256: sha,
    }));
  const deduped = _dropAlreadyRecorded(target, records);
  if (!deduped.length) return [];
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const existed = fs.existsSync(target);
  const fd = fs.openSync(target, "a");
  try {
    for (const record of deduped) {
      const raw = Buffer.from(JSON.stringify(record) + "\n", "utf8");
      let offset = 0;
      while (offset < raw.length) {
        const written = fs.writeSync(fd, raw, offset, raw.length - offset, null);
        if (written <= 0) throw new BehaviourClassError("behaviour class append made no progress");
        offset += written;
      }
    }
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  void existed;
  return deduped;
}

function _dropAlreadyRecorded(target: string, records: Array<Record<string, any>>): Array<Record<string, any>> {
  if (!records.length) return [];
  const seen = new Set<string>();
  for (const line of _ledgerLines(target)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let record: any;
    try {
      record = JSON.parse(trimmed);
    } catch {
      continue;
    }
    if (!_isMap(record)) continue;
    if (String(record.schema || "") !== BEHAVIOUR_RECORD_SCHEMA) continue;
    seen.add(`${String(record.method || "")}${String(record.object_kind || "")}${String(record.documentation_sha256 || "")}`);
  }
  const out: Array<Record<string, any>> = [];
  for (const record of records) {
    const key = `${String(record.method || "")}${String(record.object_kind || "")}${String(record.documentation_sha256 || "")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ ...record });
  }
  return out;
}

export function seed_behaviour_class(method: string): Record<string, any> | null {
  const { load_grammar } = require("./domain_grammar");
  const token = String(method || "").trim().toLowerCase();
  if (!token) return null;
  let classes: any;
  try {
    classes = load_grammar().algorithm_classes || {};
  } catch {
    return null;
  }
  if (!_isMap(classes)) return null;
  for (const [classId, behaviour] of Object.entries(SEED_CLASS_MAP)) {
    const spec = classes[classId];
    if (!_isMap(spec)) continue;
    const methods = new Set((spec.methods || []).map((name: any) => String(name).trim().toLowerCase()));
    if (methods.has(token)) {
      return {
        behaviour_class: behaviour,
        pinned: "seed",
        source_path: "knowledge/data/compile_ref/domain_grammar.json",
        locator: `domain_grammar.json:algorithm_classes.${classId}`,
        quote: String(spec.provenance || ""),
        reason_code: "seed_cache",
      };
    }
  }
  return null;
}

export function resolve_behaviour_classes(structure: Array<Record<string, any>>, opts: { path?: string | null } = {}): Array<Record<string, any>> {
  const bindings = case_method_bindings(structure);
  if (!bindings.length) return [];
  const ledger = load_behaviour_classes({ path: opts.path ?? null });
  const out: Array<Record<string, any>> = [];
  for (const binding of bindings) {
    const method = binding.method;
    const kind = binding.object_kind;
    const record = ledger.get(`${method}${kind}`) || ledger.get(`${method}`);
    if (record) {
      out.push({
        method,
        object_kind: kind,
        behaviour_class: String(record.behaviour_class || ""),
        pinned: String(record.pinned || ""),
        source_path: String(record.source_path || ""),
        locator: String(record.locator || ""),
        quote: String(record.quote || ""),
        reason_code: "adjudicated",
      });
      continue;
    }
    const seed = seed_behaviour_class(method);
    if (seed) {
      out.push({ method, object_kind: kind, ...seed });
      continue;
    }
    out.push({ method, object_kind: kind, behaviour_class: _unclassified(), pinned: "", source_path: "", locator: "", quote: "", reason_code: "no_documentation_judgement" });
  }
  return out;
}

export function classification_request(structure: Array<Record<string, any>>): Array<Record<string, any>> {
  const out: Array<Record<string, any>> = [];
  for (const row of resolve_behaviour_classes(structure)) {
    if (String(row.reason_code || "") === "adjudicated") continue;
    out.push({ method: row.method, object_kind: row.object_kind, documentation: method_paragraph_candidates(row.method, row.object_kind) });
  }
  return out.filter((row) => row.documentation && row.documentation.length);
}

export function unique_bindings(rows: Iterable<Record<string, any>>): Array<Record<string, string>> {
  const out: Array<Record<string, string>> = [];
  const seen = new Set<string>();
  for (const row of rows || []) {
    if (!_isMap(row)) continue;
    const key0 = String(row.method || "");
    const key1 = String(row.object_kind || "");
    if (!key0 || seen.has(`${key0}${key1}`)) continue;
    seen.add(`${key0}${key1}`);
    out.push({ method: key0, object_kind: key1 });
  }
  return out;
}
