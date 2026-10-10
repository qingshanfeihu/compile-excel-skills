// 生成：tools/extract_engine.py ← InfoTest main/kms/spec_index.py（sha256 4b4b4ecc171e5a1f）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import { SpecGenerationUnavailable, is_spec_document, resolve_active_spec_generation } from "../knowledge_paths";
import { atomic_write_bytes_nofollow, read_regular_nofollow, validate_json_budget } from "../case_compiler/_sealed_io";
import { accepts_schema } from "../common/schema_identity";

export const SCHEMA = "ist.spec_index";
const _BUG_NUM_RE = /(?<!\d)(\d{5,6})(?!\d)/g;
const _ASCII_TOKEN_RE = /[a-z0-9]{2,}/g;
const _CJK_RE = /[一-鿿]/g;
const _BODY_SCAN_LIMIT_BYTES = 512 * 1024;
const _SPEC_MAX_BYTES = 16 * 1024 * 1024;
const _INDEX_MAX_BYTES = 16 * 1024 * 1024;
const _KEYWORD_TOP = 24;
const _KEYWORD_MIN_TF = 3;
const _KEYWORD_DF_CAP = 0.2;

function _read_bounded(filePath: string, label: string, max_bytes: number): Buffer {
  const result = read_regular_nofollow(filePath, {
    errorType: Error,
    invalid_message: `${label} path is invalid`,
    directory_message: `${label} parent is unavailable`,
    open_message: `${label} is unavailable`,
    bounds_message: `${label} exceeds its sealed size boundary`,
    changed_message: `${label} changed while being read`,
    max_bytes,
    min_bytes: 1,
  });
  return result as Buffer;
}

function _top_terms(body: string): string[] {
  const tf = new Map<string, number>();
  const t = body.toLowerCase();
  for (const match of t.matchAll(_ASCII_TOKEN_RE)) {
    const w = match[0];
    tf.set(w, (tf.get(w) ?? 0) + 1);
  }
  const cjk = [...body].filter((ch) => /[一-鿿]/.test(ch)).join("");
  for (let i = 0; i < cjk.length - 1; i++) {
    const bg = cjk.slice(i, i + 2);
    tf.set(bg, (tf.get(bg) ?? 0) + 1);
  }
  const ranked = [...tf.entries()].filter(([, n]) => n >= _KEYWORD_MIN_TF).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return ranked.slice(0, _KEYWORD_TOP * 3).map(([w]) => w);
}

function _tokens(text: string): Set<string> {
  const t = text.toLowerCase();
  const out = new Set<string>();
  for (const match of t.matchAll(_ASCII_TOKEN_RE)) {
    out.add(match[0]);
  }
  const cjk = [...t].filter((ch) => /[一-鿿]/.test(ch)).join("");
  for (let i = 0; i < cjk.length - 1; i++) {
    out.add(cjk.slice(i, i + 2));
  }
  return out;
}

function _first_title_line(body: string): string {
  for (const line of body.split(/\r?\n/)) {
    const s = line.trim();
    if (!s) {
      continue;
    }
    if (s.startsWith("#")) {
      return s.replace(/^#+\s*/, "").trim().slice(0, 200);
    }
    return s.slice(0, 200);
  }
  return "";
}

function _load_lastmod_map(stateTsv: string): Record<string, number> {
  const out: Record<string, number> = {};
  if (!fs.statSync(stateTsv).isFile()) {
    return out;
  }
  const content = fs.readFileSync(stateTsv, "utf8");
  for (const line of content.split(/\r?\n/)) {
    if (!line || line.startsWith("#")) {
      continue;
    }
    const parts = line.split("\t");
    if (parts.length !== 2) {
      continue;
    }
    const [href, ms] = parts;
    try {
      out[path.parse(href).name + ".md".toLowerCase()] = parseInt(ms, 10);
    } catch {
      continue;
    }
  }
  return out;
}

export function build_spec_index(spec_dir: string, state_path?: string): Record<string, any> {
  const specDir = String(spec_dir);
  const lastmod = _load_lastmod_map(state_path ?? path.join(specDir, ".sync_state.tsv"));
  const entries: Record<string, any> = {};
  let nBodyNum = 0;
  let nTitle = 0;
  let nNotSpec = 0;
  const lowerSeen = new Map<string, string>();
  const collisions: string[] = [];
  const perDocTerms = new Map<string, string[]>();
  const files = fs.readdirSync(specDir).filter((f) => f.endsWith(".md")).sort();
  for (const fname of files) {
    const p = path.join(specDir, fname);
    if (!is_spec_document(fname)) {
      nNotSpec += 1;
      continue;
    }
    const raw = _read_bounded(p, "spec document", _SPEC_MAX_BYTES);
    const body = raw.subarray(0, _BODY_SCAN_LIMIT_BYTES).toString("utf8");
    const title = _first_title_line(body);
    const fnameNums = [...new Set([...fname.matchAll(_BUG_NUM_RE)].map((m) => m[1]))].sort();
    const anchored = new Set<string>();
    const plain = new Set<string>();
    for (const line of body.split(/\r?\n/)) {
      const nums = [...line.matchAll(_BUG_NUM_RE)].map((m) => m[1]);
      if (!nums.length) {
        continue;
      }
      const bucket = /bug|#/i.test(line) ? anchored : plain;
      nums.forEach((n) => bucket.add(n));
    }
    for (const n of anchored) {
      plain.delete(n);
    }
    const stat = fs.statSync(p);
    const entry = {
      title,
      bug_numbers_filename: fnameNums,
      bug_numbers_anchored: [...anchored].sort(),
      bug_numbers_body: [...plain].sort(),
      sha256: crypto.createHash("sha256").update(raw).digest("hex"),
      size: raw.length,
      lastmod_ms: lastmod[fname.toLowerCase()] ?? Math.floor(stat.mtimeMs * 1000),
    };
    perDocTerms.set(fname, _top_terms(body));
    if (lowerSeen.has(fname.toLowerCase())) {
      collisions.push(fname);
    }
    lowerSeen.set(fname.toLowerCase(), fname);
    entries[fname] = entry;
    if (anchored.size || plain.size || fnameNums.length) {
      nBodyNum += 1;
    }
    if (title) {
      nTitle += 1;
    }
  }
  const df = new Map<string, number>();
  for (const terms of perDocTerms.values()) {
    for (const t of new Set(terms)) {
      df.set(t, (df.get(t) ?? 0) + 1);
    }
  }
  const cap = Math.max(2, Math.floor(perDocTerms.size * _KEYWORD_DF_CAP));
  for (const [name, terms] of perDocTerms) {
    entries[name].body_keywords = terms.filter((t) => (df.get(t) ?? 0) <= cap).slice(0, _KEYWORD_TOP);
  }
  return {
    schema: SCHEMA,
    generated_from: specDir,
    policy: { rule: "addressing yields candidates with evidence, never silent authority binding; no hit must surface as no_governing_spec" },
    coverage: { total_files: files.length, with_any_bug_number: nBodyNum, with_title: nTitle, skipped_not_spec_named: nNotSpec, case_insensitive_collisions: collisions },
    entries,
  };
}

export function write_index_atomic(filePath: string, payload: Record<string, any>): void {
  const encoded = Buffer.from(JSON.stringify(payload, null, 2) + "\n", "utf8");
  atomic_write_bytes_nofollow(filePath, encoded, {
    errorType: Error,
    invalid_message: "spec index path is invalid",
    unavailable_message: "spec index directory is unavailable",
  });
}

const _SEMANTIC_FLOOR = 3;
const _SEMANTIC_TOP = 3;
const _JEV_RERANK_TOP = 5;

function _project_root(): string {
  return _cex_data_path("");
}

function _jev_rerank_semantic(scored: Array<[number, string, any, string[]]>, query_title: string): [Array<[number, string, any, string[]]>, Record<string, number>] {
  try {
    const jevSpecRerank = require("../common/jev_spec_rerank") as any;
    if (!jevSpecRerank.enabled()) {
      return [scored, {}];
    }
    const top = scored.slice(0, _JEV_RERANK_TOP);
    if (top.length < 2) {
      return [scored, {}];
    }
    const candidates = top.map(([_score, name, entry]) => {
      let head: string | null = null;
      const resolved = resolve_indexed_spec(_project_root(), name);
      if (resolved !== null) {
        head = jevSpecRerank.spec_head_slice(resolved.content.toString("utf8"));
      }
      return { filename: name, title: String(entry.title ?? ""), head };
    });
    const outcome = jevSpecRerank.rerank(query_title, candidates);
    if (outcome === null) {
      return [scored, {}];
    }
    const [order, nouls] = outcome;
    const reordered = order.map((i: number) => top[i]).concat(scored.slice(top.length));
    const noulMap: Record<string, number> = {};
    for (const [i, noul] of Object.entries(nouls)) {
      noulMap[top[parseInt(i, 10)][1]] = noul as number;
    }
    return [reordered, noulMap];
  } catch (exc) {
    console.warn(`spec_index: Jev 精排意外失败，退回原确定性排序: ${(exc as Error).name}`);
    return [scored, {}];
  }
}

const _VERSION_TAIL_RE = /(?:[-_ ]v?\d+(?:\.\d+)*|\d+\.\d+(?:\.\d+)*)+$/;
const _VERSION_NUM_RE = /\d+/g;

function _version_family(name: string): [string, number[]] {
  const stem = name.toLowerCase().endsWith(".md") ? name.slice(0, -3) : name;
  const m = _VERSION_TAIL_RE.exec(stem);
  if (!m) {
    return [stem, []];
  }
  const version = [...m[0].matchAll(_VERSION_NUM_RE)].map((x) => parseInt(x[0], 10));
  return [stem.slice(0, m.index), version];
}

function _collapse_version_families(entries: Record<string, any>): [Record<string, any>, Array<Record<string, any>>] {
  const families = new Map<string, string[]>();
  for (const name of Object.keys(entries)) {
    const [root] = _version_family(name);
    if (!families.has(root)) {
      families.set(root, []);
    }
    families.get(root)!.push(name);
  }
  const canonical: Record<string, any> = {};
  const report: Array<Record<string, any>> = [];
  for (const names of families.values()) {
    if (names.length === 1) {
      canonical[names[0]] = entries[names[0]];
      continue;
    }
    const kept = names.reduce((best, n) => {
      const [, v] = _version_family(n);
      const vBest = _version_family(best)[1];
      if (v.length > vBest.length) return n;
      if (v.length < vBest.length) return best;
      const lmod = Number(entries[n].lastmod_ms ?? 0);
      const lmodBest = Number(entries[best].lastmod_ms ?? 0);
      if (lmod > lmodBest) return n;
      if (lmod < lmodBest) return best;
      return n > best ? n : best;
    });
    canonical[kept] = entries[kept];
    report.push({ kept, dropped: names.filter((n) => n !== kept).sort() });
  }
  return [canonical, report];
}

function _title_numbers(entry: Record<string, any>): string[] {
  return [...String(entry.title ?? "").matchAll(_BUG_NUM_RE)].map((m) => m[1]);
}

export function locate_spec(index: Record<string, any>, query_title: string, bug_numbers?: string[], rerank = true): Record<string, any> {
  const rawEntries: Record<string, any> = index.entries ?? {};
  const [entries, versionDedup] = _collapse_version_families(rawEntries);
  const nums = bug_numbers?.length ? bug_numbers : [...String(query_title).matchAll(_BUG_NUM_RE)].map((m) => m[1]);

  function _result(status: string, channel: string | null, matches: Array<Record<string, any>>): Record<string, any> {
    return { status, channel, matches, version_dedup: versionDedup };
  }
  const channels: Array<[string, string, boolean]> = [
    ["bug_numbers_filename", "bug_filename", true],
    ["__title__", "bug_title", true],
    ["bug_numbers_anchored", "bug_anchored", true],
    ["bug_numbers_body", "bug_body", false],
  ];
  for (const [field, channel, canMatch] of channels) {
    const hits: Array<Record<string, any>> = [];
    for (const [name, e] of Object.entries(entries)) {
      const pool = field === "__title__" ? _title_numbers(e) : (e[field] ?? []);
      const matchedNums = nums.filter((n) => pool.includes(n));
      if (matchedNums.length) {
        hits.push({ file: name, title: e.title ?? "", evidence: `${channel}:${matchedNums.join(",")}` });
      }
    }
    if (hits.length === 1 && canMatch) {
      return _result("matched", channel, hits);
    }
    if (hits.length) {
      return _result("candidates", channel, hits);
    }
  }
  const qt = _tokens(String(query_title));
  let scored: Array<[number, string, any, string[]]> = [];
  if (qt.size) {
    for (const [name, e] of Object.entries(entries)) {
      const claimedNums = new Set([...(e.bug_numbers_filename ?? []), ..._title_numbers(e), ...(e.bug_numbers_anchored ?? [])]);
      if (nums.length && claimedNums.size && ![...claimedNums].some((n) => nums.includes(n))) {
        continue;
      }
      const face = _tokens(name + " " + String(e.title ?? ""));
      (e.body_keywords ?? []).forEach((t: string) => face.add(t));
      const overlap = [...qt].filter((t) => face.has(t));
      if (overlap.length >= _SEMANTIC_FLOOR) {
        scored.push([overlap.length, name, e, overlap.sort()]);
      }
    }
    scored.sort((a, b) => b[0] - a[0] || a[1].localeCompare(b[1]));
  }
  if (scored.length) {
    let jevNouls: Record<string, number> = {};
    if (rerank) {
      [scored, jevNouls] = _jev_rerank_semantic(scored, String(query_title));
    }
    const matches = scored.slice(0, _SEMANTIC_TOP).map(([score, name, e, ov]) => ({
      file: name,
      title: e.title ?? "",
      score,
      evidence: "semantic:" + ov.slice(0, 6).join("/") + (name in jevNouls ? `;jev:noul=${jevNouls[name].toFixed(2)}` : ""),
    }));
    return _result("candidates", "semantic", matches);
  }
  return _result("no_governing_spec", null, []);
}

export function load_index(filePath: string): Record<string, any> | null {
  try {
    const raw = _read_bounded(String(filePath), "spec index", _INDEX_MAX_BYTES);
    validate_json_budget(raw, {
      errorType: Error,
      message: "spec index exceeds the JSON structure budget",
    });
    const data = JSON.parse(raw.toString("utf8"));
    if (typeof data !== "object" || data === null || !accepts_schema(data.schema, SCHEMA)) {
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

export interface ResolvedIndexedSpec {
  path: string;
  content: Buffer;
  sha256: string;
  size: number;
  generation_id: string;
  manifest_sha256: string;
}

export function resolve_indexed_spec(project_root: string, name: string): ResolvedIndexedSpec | null {
  const root = String(project_root);
  const text = String(name ?? "").trim();
  const relative = path.parse(text);
  if (!text || path.isAbsolute(text) || relative.dir !== "" || relative.base !== text) {
    return null;
  }
  let generation: { index: string; docs: string; generation_id: string; manifest_sha256: string };
  try {
    generation = resolve_active_spec_generation(root);
  } catch (exc) {
    if (exc instanceof SpecGenerationUnavailable) {
      return null;
    }
    throw exc;
  }
  const index = load_index(generation.index);
  if (typeof index !== "object" || index === null || !(text in (index.entries ?? {}))) {
    return null;
  }
  const candidate = path.join(generation.docs, text);
  const entry = index.entries[text];
  if (typeof entry !== "object" || entry === null || typeof entry.size !== "number" || entry.size < 1 || entry.size > _SPEC_MAX_BYTES || !/^[0-9a-f]{64}$/.test(String(entry.sha256 ?? ""))) {
    return null;
  }
  let content: Buffer;
  try {
    content = _read_bounded(candidate, "indexed spec document", _SPEC_MAX_BYTES);
  } catch {
    return null;
  }
  if (content.length !== entry.size || crypto.createHash("sha256").update(content).digest("hex") !== entry.sha256) {
    return null;
  }
  return {
    path: path.resolve(candidate),
    content,
    sha256: entry.sha256,
    size: entry.size,
    generation_id: generation.generation_id,
    manifest_sha256: generation.manifest_sha256,
  };
}
