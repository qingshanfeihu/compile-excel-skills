import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import { pyRepr } from "../_py";
import { all_capability_names, classify_capability, load_atlas as _load_atlas } from "./ir_coverage";
import { accepts_schema } from "../common/schema_identity";

export { classify_capability, all_capability_names };

const _LANGUAGE_DOCS_INDEX_PATH = path.join(_cex_data_path(""), "knowledge/data/compile_ref/language_docs_index.json");

export class QueryUnavailable extends Error {}

export function language_document_catalog(query = ""): Record<string, any> {
  let payload: any;
  try {
    payload = JSON.parse(fs.readFileSync(_LANGUAGE_DOCS_INDEX_PATH, "utf8"));
  } catch (exc: any) {
    throw new QueryUnavailable(`language_docs_index.json 不可达或损坏（${exc?.constructor?.name ?? "Error"}）`);
  }
  if (payload === null || Array.isArray(payload) || typeof payload !== "object" || !accepts_schema(payload.schema, "ist.ide.language-docs") || !Array.isArray(payload.entries)) {
    throw new QueryUnavailable("language_docs_index.json schema mismatch");
  }
  const terms = String(query ?? "").split(/\s+/).filter((term) => term.trim()).map((term) => term.toLowerCase());
  const matches: any[] = [];
  for (const entry of payload.entries) {
    if (entry === null || Array.isArray(entry) || typeof entry !== "object") {
      continue;
    }
    const searchable = JSON.stringify(entry).toLowerCase();
    if (!terms.length || terms.every((term) => searchable.includes(term))) {
      matches.push(entry);
    }
  }
  return { schema: payload.schema, query: String(query ?? ""), matches };
}

export const NOT_DIRECTLY_HIT = "未在文档直接命中";
export const MANUAL_SOURCE_UNAVAILABLE = "command_tree_unavailable";
export const PARAM_CONTRACT_UNAVAILABLE = "projection_unavailable";

function _paramContractUnavailable(reason: string): Record<string, any> {
  return { status: PARAM_CONTRACT_UNAVAILABLE, reason, head: "", version: null, device_os_build: null, args: [], selected: null };
}

export function param_contract_of(command: string, position: number | null = null): Record<string, any> | null {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { load_vendor_stdlib, match_command_head } = require("./vendor_stdlib");
  const tokens = String(command ?? "").split(/\s+/).filter(Boolean);
  if (!tokens.length) {
    return null;
  }
  const inventory = load_vendor_stdlib();
  if (inventory === null || inventory === undefined) {
    return _paramContractUnavailable("command-tree projection could not be loaded");
  }
  const headers = inventory.headers;
  if (headers === null || headers === undefined || Array.isArray(headers) || typeof headers !== "object") {
    return _paramContractUnavailable("command-tree projection has no usable XML headers map");
  }
  const candidate = match_command_head(tokens, headers);
  if (candidate === null) {
    return null;
  }
  const [head, entry] = candidate;
  const args: Array<Record<string, any>> = [];
  for (const item of entry.args ?? []) {
    if (item !== null && typeof item === "object" && !Array.isArray(item)) {
      args.push({ ...item });
    }
  }
  let selected: Record<string, any> | null = null;
  if (position !== null && position !== undefined) {
    selected = args.find((item) => item.position === position) ?? null;
  }
  return { head, version: inventory.version, device_os_build: inventory.device_os_build, args, selected };
}

export function manual_param_excerpt(command_head: string, opts: { max_lines?: number } = {}): Record<string, any> {
  const maxLines = opts.max_lines ?? 80;
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { manual_source_dir } = require("./vendor_stdlib");
  const head = String(command_head ?? "").split(/\s+/).filter(Boolean).join(" ");
  const out: Record<string, any> = { hit: false, command: head, sections: [], note: "" };
  if (!head) {
    out.note = "empty command head";
    return out;
  }
  const root = manual_source_dir();
  if (root === null || root === undefined) {
    out.note = MANUAL_SOURCE_UNAVAILABLE;
    return out;
  }
  const src = path.relative(_cex_data_path(""), root).split(path.sep).join("/");
  const syntaxPrefix = `**${head}**`;
  let files: string[] = [];
  try {
    files = fs.readdirSync(root).filter((name) => name.endsWith(".md")).sort();
  } catch {
    files = [];
  }
  for (const name of files) {
    let lines: string[];
    try {
      lines = fs.readFileSync(path.join(root, name), "utf8").split(/\r?\n/);
    } catch {
      continue;
    }
    for (let index = 0; index < lines.length; index++) {
      if (!lines[index].trim().startsWith(syntaxPrefix)) {
        continue;
      }
      let end = Math.min(lines.length, index + 1 + maxLines);
      for (let j = index + 1; j < end; j++) {
        if (lines[j].trim().startsWith("**")) {
          end = j;
          break;
        }
      }
      const window = lines.slice(index, end);
      out.sections.push({
        file: `${src}/${name}`,
        line: index + 1,
        has_parameter_table: window.some((ln) => (ln.trim().startsWith("|") && ln.includes("参数")) || ln.includes("<table")),
        text: window.join("\n"),
      });
    }
  }
  if (out.sections.length) {
    out.hit = true;
  } else {
    out.note = NOT_DIRECTLY_HIT;
  }
  return out;
}

const _MIRROR_ROOT = path.join(_cex_data_path(""), "knowledge", "framework", "mirror");
let _SOURCE_OVERLAY: Record<string, any> | null = null;

const _cachedClearers: Array<() => void> = [];
function _lru1<F extends (...args: any[]) => any>(fn: F): F & { cache_clear(): void } {
  let cached: { value: ReturnType<F> } | null = null;
  const wrapped = (() => {
    if (cached === null) {
      cached = { value: fn() };
    }
    return cached.value;
  }) as F & { cache_clear(): void };
  wrapped.cache_clear = () => {
    cached = null;
  };
  _cachedClearers.push(wrapped.cache_clear);
  return wrapped;
}

function _clearSourceCaches(): void {
  for (const clear of _cachedClearers) {
    clear();
  }
}

export function source_overlay<T>(sources: Record<string, any> | null | undefined, fn: () => T): T {
  const previous = _SOURCE_OVERLAY;
  _SOURCE_OVERLAY = sources ? { ...sources } : null;
  _clearSourceCaches();
  try {
    return fn();
  } finally {
    _SOURCE_OVERLAY = previous;
    _clearSourceCaches();
  }
}

export function mirror_src(rel: string): string {
  if (_SOURCE_OVERLAY !== null && rel in _SOURCE_OVERLAY) {
    const raw = _SOURCE_OVERLAY[rel];
    if (raw instanceof Uint8Array || Buffer.isBuffer(raw)) {
      return Buffer.from(raw).toString("utf8").replace(/�/g, "�");
    }
    return String(raw);
  }
  try {
    return fs.readFileSync(path.join(_MIRROR_ROOT, rel), "utf8");
  } catch {
    return "";
  }
}

const _devices_keys = _lru1((): Set<string> => {
  const src = mirror_src("lib/test_xlsx.py");
  const m = /devices\s*=\s*\{([\s\S]*?)\}/.exec(src);
  if (!m) {
    return new Set();
  }
  return new Set([...m[1].matchAll(/'([^']+)'\s*:/g)].map((mm) => mm[1]));
});

export const host_slot_es = _lru1((): Set<string> => {
  const conftest = mirror_src("smoke_test/conftest.py");
  const slots = new Set<string>();
  for (const m of conftest.matchAll(/def (\w+)\([^)]*\):([\s\S]*?)(?=\n@|\ndef |$)/g)) {
    if (m[2].includes("ssh_server(") && !m[2].includes("class ")) {
      slots.add(m[1]);
    }
  }
  const keys = _devices_keys();
  return new Set([...slots].filter((slot) => keys.has(slot)));
});

export function public_methods(rel: string, cls: string): Set<string> {
  const src = mirror_src(rel);
  const clsRe = new RegExp(`^(?<indent>[ \\t]*)class[ \\t]+${escapeRegExp(cls)}\\b[^\\n]*:\\s*$`, "m");
  const match = clsRe.exec(src);
  if (match === null) {
    return new Set();
  }
  const indent = match.groups!.indent;
  const tail = src.slice(match.index + match[0].length);
  const boundary = new RegExp(`^${escapeRegExp(indent)}(?:class[ \\t]|def[ \\t]|@)`, "m").exec(tail);
  const body = boundary !== null ? tail.slice(0, boundary.index) : tail;
  const methodIndent = escapeRegExp(indent + "    ");
  return new Set([...body.matchAll(new RegExp(`^${methodIndent}def[ \\t]+(\\w+)\\(`, "gm"))].map((m) => m[1]));
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export const LIFECYCLE_FS = new Set(["__init__", "xlsx_begin", "read_until", "close", "soft_close", "clear", "delete_ip", "delete_route", "load_synonyms", "check_direct_match", "get_same", "get_similar_function"]);

export const valid_es = _lru1((): Set<string> => {
  const keys = _devices_keys();
  return keys.size ? new Set([...keys, "check_point", "time"]) : new Set();
});

export const APV_CMD_PRIMITIVE_FS = new Set(["cmd", "cmd_enable", "cmd_config", "cmds_config"]);
export const SEG_CMD_PRIMITIVE_FS = new Set([...APV_CMD_PRIMITIVE_FS, "array_config"]);
export const CMD_PRIMITIVE_FS = SEG_CMD_PRIMITIVE_FS;
const _SEAT_RUNTIME_CLASS: Record<string, [string, string, Set<string>]> = {
  apv: ["lib/apv/apv.py", "APV", APV_CMD_PRIMITIVE_FS],
  segment: ["lib/apv/apv_ssh.py", "APV_SSH", SEG_CMD_PRIMITIVE_FS],
};

function _mirrorCmdPrimitives(family: string): Set<string> {
  const [rel, cls, closure] = _SEAT_RUNTIME_CLASS[family];
  const declared = public_methods(rel, cls);
  if (!declared.size) {
    throw new QueryUnavailable(`mirror 中 ${rel} 的 ${cls} 类体解析为空；传输原语无法现算`);
  }
  return new Set([...declared].filter((name) => closure.has(name)));
}

const _apv_cmd_primitives = _lru1(() => _mirrorCmdPrimitives("apv"));
const _seg_cmd_primitives = _lru1(() => _mirrorCmdPrimitives("segment"));

const _segment_es = _lru1((): Set<string> => new Set([..._devices_keys()].filter((key) => /^Seg\d+_tmp$/.test(key))));

const _apv_full_fs_by_family = _lru1((): Record<string, Set<string>> => ({
  ssl_comm: public_methods("lib/apv/ssl_comm.py", "ssl_comm"),
  seg_comm: public_methods("lib/apv/seg_comm.py", "seg_comm"),
  ha_comm: public_methods("lib/apv/ha_comm.py", "ha_comm"),
  preparation: public_methods("lib/apv/preparation.py", "preparation"),
}));

export const apv_full_fs = _lru1((): Set<string> => {
  const byFamily = _apv_full_fs_by_family();
  if (!Object.values(byFamily).some((value) => value.size)) {
    return new Set();
  }
  const mixinUnion = new Set<string>();
  for (const value of Object.values(byFamily)) {
    for (const name of value) {
      if (!LIFECYCLE_FS.has(name)) {
        mixinUnion.add(name);
      }
    }
  }
  return new Set([...mixinUnion, "execute", ..._apv_cmd_primitives()]);
});

const _segment_full_fs = _lru1((): Set<string> => {
  const ssl = new Set([...public_methods("lib/apv/ssl_comm.py", "ssl_comm")].filter((name) => !LIFECYCLE_FS.has(name)));
  const prep = new Set([...public_methods("lib/apv/preparation.py", "preparation")].filter((name) => !LIFECYCLE_FS.has(name)));
  if (!ssl.size && !prep.size) {
    return new Set();
  }
  return new Set([...ssl, ...prep, "execute", ..._seg_cmd_primitives()]);
});

export const valid_fs_by_e = _lru1((): Record<string, Set<string>> => {
  const envHosts = new Set([...public_methods("lib/env.py", "Env")].filter((name) => !LIFECYCLE_FS.has(name)));
  const cp = new Set([...public_methods("lib/check_point.py", "Check_Point")].filter((name) => !LIFECYCLE_FS.has(name)));
  const slotFs = new Set([...public_methods("lib/ssh_server.py", "ssh_server")].filter((name) => !LIFECYCLE_FS.has(name)));
  const out: Record<string, Set<string>> = {};
  if (envHosts.size) {
    out.test_env = envHosts;
  }
  if (cp.size) {
    out.check_point = cp;
  }
  out.time = new Set(["sleep"]);
  if (slotFs.size) {
    for (const slot of host_slot_es()) {
      out[slot] = slotFs;
    }
  }
  const httpFs = new Set([...public_methods("smoke_test/conftest.py", "http_server")].filter((name) => !LIFECYCLE_FS.has(name) && name !== "start" && name !== "stop"));
  if (httpFs.size && _devices_keys().has("http_server_231")) {
    out.http_server_231 = httpFs;
  }
  const apvFs = apv_full_fs();
  if (apvFs.size) {
    for (const e of ["APV_0", "APV_1", "APV_2"]) {
      out[e] = apvFs;
    }
  }
  const segmentFs = _segment_full_fs();
  if (segmentFs.size) {
    for (const e of _segment_es()) {
      out[e] = segmentFs;
    }
  }
  return out;
});

export const APV_ACTION_SRC = "lib/apv/apv_action.py";
export const CLIENT_ACTION_SRC = "lib/client_action.py";
const _APV_SYNONYMS_SRC = "lib/apv/apv_synonyms";
const _CLIENT_SYNONYMS_SRC = "lib/client_synonyms";

export function norm_action(s: string): string {
  return String(s).toLowerCase().replace(/\s+/g, "");
}

function _synonymValuesByCanonical(srcRel: string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const rawLine of mirror_src(srcRel).split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("：")) {
      continue;
    }
    const splitAt = line.indexOf("：");
    const canonical = line.slice(0, splitAt);
    const values = line.slice(splitAt + 1);
    out[norm_action(canonical)] = values.split("，").map((value) => value.trim()).filter(Boolean);
  }
  return out;
}

function _mappingActionNames(srcRel: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of mirror_src(srcRel).matchAll(/'([^']+)':\s*self\.func_\d+/g)) {
    out[norm_action(m[1])] = m[1].trim();
  }
  return out;
}

export const execute_action_registry_by_dispatch = _lru1((): Record<string, Record<string, string>> => {
  const specs: Array<[string, string, string]> = [
    ["apv", APV_ACTION_SRC, _APV_SYNONYMS_SRC],
    ["client", CLIENT_ACTION_SRC, _CLIENT_SYNONYMS_SRC],
  ];
  const out: Record<string, Record<string, string>> = {};
  for (const [dispatcher, mappingSrc, synonymSrc] of specs) {
    const canonical = _mappingActionNames(mappingSrc);
    const aliases = _synonymValuesByCanonical(synonymSrc);
    const registry: Record<string, string> = { ...canonical };
    for (const [canonicalNorm, values] of Object.entries(aliases)) {
      if (!(canonicalNorm in canonical)) {
        continue;
      }
      for (const value of values) {
        const key = norm_action(value);
        if (!(key in registry)) {
          registry[key] = value;
        }
      }
    }
    out[dispatcher] = registry;
  }
  return out;
});

export function execute_dispatcher_for_e(e: string): string {
  const value = String(e ?? "").trim();
  if (["APV_0", "APV_1", "APV_2"].includes(value) || _segment_es().has(value)) {
    return "apv";
  }
  if (host_slot_es().has(value)) {
    return "client";
  }
  return "";
}

export const execute_action_registry = _lru1((): Record<string, string> => {
  const reg: Record<string, string> = {};
  for (const registry of Object.values(execute_action_registry_by_dispatch())) {
    for (const [normalized, original] of Object.entries(registry)) {
      if (!(normalized in reg)) {
        reg[normalized] = original;
      }
    }
  }
  return reg;
});

export function execute_action_spec(e: string, action: string): Record<string, any> | null {
  const dispatcher = execute_dispatcher_for_e(e);
  if (!dispatcher) {
    return null;
  }
  const normalized = norm_action(action);
  let info: any;
  try {
    const atlas = _load_atlas();
    info = atlas?.execute_actions?.capabilities?.[`${dispatcher}:${normalized}`];
  } catch {
    return null;
  }
  if (info === null || info === undefined || Array.isArray(info) || typeof info !== "object") {
    return null;
  }
  const allowedEs = new Set((info.allowed_es ?? []).map((value: any) => String(value)));
  if (!allowedEs.has(String(e))) {
    return null;
  }
  return { ...info };
}

export function execute_action_names(): Set<string> {
  return new Set(Object.keys(execute_action_registry()));
}

function _sequenceRatio(a: string, b: string): number {
  // difflib.SequenceMatcher.ratio() equivalent (Ratcliff/Obershelp via matching blocks).
  const m = a.length;
  const n = b.length;
  if (m + n === 0) {
    return 1.0;
  }
  const matches = _matchingBlocks(a, b).reduce((sum, block) => sum + block[2], 0);
  return (2.0 * matches) / (m + n);
}

function _matchingBlocks(a: string, b: string): Array<[number, number, number]> {
  const queue: Array<[number, number, number, number]> = [[0, a.length, 0, b.length]];
  const blocks: Array<[number, number, number]> = [];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop()!;
    const [i, j, k] = _longestMatch(a, alo, ahi, b, blo, bhi);
    if (k > 0) {
      blocks.push([i, j, k]);
      if (alo < i && blo < j) {
        queue.push([alo, i, blo, j]);
      }
      if (i + k < ahi && j + k < bhi) {
        queue.push([i + k, ahi, j + k, bhi]);
      }
    }
  }
  blocks.sort((x, y) => x[0] - y[0]);
  return blocks;
}

function _longestMatch(a: string, alo: number, ahi: number, b: string, blo: number, bhi: number): [number, number, number] {
  let bestI = alo;
  let bestJ = blo;
  let bestSize = 0;
  let j2len: Map<number, number> = new Map();
  for (let i = alo; i < ahi; i++) {
    const newJ2len: Map<number, number> = new Map();
    for (let j = blo; j < bhi; j++) {
      if (a[i] === b[j]) {
        const k = (j2len.get(j - 1) ?? 0) + 1;
        newJ2len.set(j, k);
        if (k > bestSize) {
          bestI = i - k + 1;
          bestJ = j - k + 1;
          bestSize = k;
        }
      }
    }
    j2len = newJ2len;
  }
  return [bestI, bestJ, bestSize];
}

export function nearest_candidates(target: string, candidates: Iterable<any>, opts: { key?: ((c: any) => string) | null; top_n?: number } = {}): string[] {
  const key = opts.key ?? null;
  const topN = opts.top_n ?? 5;
  const keyFn = key ?? ((c: any) => String(c));
  const ranked = [...candidates].sort((a, b) => {
    const ratioA = _sequenceRatio(String(target), String(keyFn(a)));
    const ratioB = _sequenceRatio(String(target), String(keyFn(b)));
    if (ratioB !== ratioA) {
      return ratioB - ratioA;
    }
    return String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0;
  });
  return ranked.slice(0, topN);
}

export function atlas_available(): boolean {
  try {
    _load_atlas();
    return true;
  } catch {
    return false;
  }
}

export function capability_signature(name: string): Record<string, any> | null {
  let atlas: any;
  try {
    atlas = _load_atlas();
  } catch (exc: any) {
    throw new QueryUnavailable(`capability_atlas.json 不可达或损坏（${exc?.constructor?.name ?? "Error"}）`);
  }
  const apvFull = atlas?.methods?.apv_full ?? {};
  for (const [famName, fam] of Object.entries<any>(apvFull)) {
    const info = (fam?.methods ?? {})[name];
    if (info !== null && info !== undefined) {
      return { required: info.required ?? [], optional: info.optional ?? [], source: info.source ?? "", _family: famName };
    }
  }
  return null;
}

export function dispatch_kind_of(f_name: string): string | null {
  const byFamily = _apv_full_fs_by_family();
  if (!Object.values(byFamily).some((value) => value.size)) {
    throw new QueryUnavailable("mirror 未读到 ssl_comm/seg_comm/ha_comm/preparation 任何内容(路径变更/离线),无法判定派发路径");
  }
  if (_apv_cmd_primitives().has(f_name)) {
    return "cmd_primitive";
  }
  if (f_name === "execute") {
    return "execute_registry";
  }
  const mixinUnion = new Set<string>();
  for (const value of Object.values(byFamily)) {
    for (const name of value) {
      if (!LIFECYCLE_FS.has(name)) {
        mixinUnion.add(name);
      }
    }
  }
  if (mixinUnion.has(f_name)) {
    return "direct_method_call";
  }
  return null;
}

export function apv_full_domains(): Set<string> {
  let atlas: any;
  try {
    atlas = _load_atlas();
  } catch {
    return new Set();
  }
  return new Set(Object.keys(atlas?.methods?.apv_full ?? {}));
}

function _domainDisambiguation(family: string, atlas: Record<string, any>): string {
  if (family !== "ssl_comm") {
    return "no curated disambiguation notes exist for this domain";
  }
  const parts: string[] = [];
  const roleConfusion = atlas.cert_role_confusion ?? {};
  const caFamily = roleConfusion.ca_family;
  if (caFamily) {
    parts.push(`role confusion: ${caFamily} (source: ${roleConfusion.source ?? ""})`);
  }
  for (const [name, info] of Object.entries<any>(atlas.cert_behavior_notes ?? {})) {
    const note = info?.note;
    if (note) {
      parts.push(`${name}: ${note} (source: ${info.source ?? ""})`);
    }
  }
  return parts.length ? parts.join("\n") : "no curated disambiguation notes exist for this domain";
}

export function dispatch_domain_orientation(domain: string): Record<string, any> {
  let atlas: any;
  try {
    atlas = _load_atlas();
  } catch (exc: any) {
    throw new QueryUnavailable(`capability_atlas.json 不可达或损坏（${exc?.constructor?.name ?? "Error"}）`);
  }
  const apvFull = atlas?.methods?.apv_full ?? {};
  if (!(domain in apvFull)) {
    throw new Error(`unknown domain ${pyRepr(domain)} — must be one of ${pyRepr(Object.keys(apvFull).sort())}`);
  }
  const methods = apvFull[domain]?.methods ?? {};
  const names = Object.keys(methods).sort();
  if (!names.length) {
    throw new QueryUnavailable(`atlas 里 ${pyRepr(domain)} family 是空的(生成异常),无法给域级 orientation`);
  }
  const disabled: Record<string, string> = {};
  for (const [n, info] of Object.entries<any>(methods)) {
    if (info?.disabled) {
      disabled[n] = info.reason ?? "";
    }
  }
  const kind = dispatch_kind_of(names[0]);
  return { domain, dispatch_kind: kind, n: names.length, names, disabled, disambiguation: _domainDisambiguation(domain, atlas), signatures_omitted: true };
}

function _atlasDispatchKindRaw(name: string): string | null {
  let atlas: any;
  try {
    atlas = _load_atlas();
  } catch {
    return null;
  }
  const apvFull = atlas?.methods?.apv_full ?? {};
  for (const fam of Object.values<any>(apvFull)) {
    const info = (fam?.methods ?? {})[name];
    if (info !== null && info !== undefined) {
      return info.dispatch_kind ?? null;
    }
  }
  return null;
}

export function dispatch_kind_cross_check(name: string): Record<string, any> {
  const live = dispatch_kind_of(name);
  const atlasValue = _atlasDispatchKindRaw(name);
  const stale = atlasValue !== null && live !== null && atlasValue !== live;
  return { live, atlas: atlasValue, stale };
}

const _USAGE_INDEX_PATH = path.join(_cex_data_path(""), "knowledge/data/compile_ref/capability_usage_index.json");
const _USAGE_SAMPLE_N = 3;

function _loadUsageIndex(): Record<string, any> {
  return JSON.parse(fs.readFileSync(_USAGE_INDEX_PATH, "utf8"));
}

export function capability_usage_of(name: string): Record<string, any> | null {
  let idx: any;
  try {
    idx = _loadUsageIndex();
  } catch (exc: any) {
    throw new QueryUnavailable(`capability_usage_index.json 不可达或损坏（${exc?.constructor?.name ?? "Error"}）`);
  }
  const meta = idx._meta ?? {};
  if (meta.corpus_status !== "ready") {
    throw new QueryUnavailable("the engine-owned device-verified corpus is unavailable; an empty authored index is not a confirmed zero-hit result");
  }
  for (const bucket of ["by_f_value", "by_execute_action"]) {
    const entry = (idx[bucket] ?? {})[name];
    if (entry !== null && entry !== undefined) {
      const usages = entry.usages ?? [];
      return { count: entry.count ?? usages.length, samples: usages.slice(0, _USAGE_SAMPLE_N), bucket, corpus_file_count: Number(meta.corpus_file_count ?? 0) };
    }
  }
  return null;
}

export function usage_index_corpus_meta(): Record<string, any> {
  let idx: any;
  try {
    idx = _loadUsageIndex();
  } catch {
    return {};
  }
  const meta = idx._meta ?? {};
  const out: Record<string, any> = {};
  for (const key of ["corpus_file_count", "total_rows_scanned", "source_manifest_sha256", "corpus_definition", "corpus_status", "corpus_absence_reason"]) {
    if (meta[key] !== null && meta[key] !== undefined) {
      out[key] = meta[key];
    }
  }
  return out;
}

export function usage_index_empty_bucket_notes(): Record<string, any> {
  let idx: any;
  try {
    idx = _loadUsageIndex();
  } catch {
    return {};
  }
  const meta = idx._meta ?? {};
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries<any>(meta)) {
    if (k.endsWith("_empty_reason")) {
      out[k] = v;
    }
  }
  return out;
}

const _HOST_CORPUS_META_KEYS = ["corpus_file_count", "corpus_status", "corpus_absence_reason", "vendor_corpus_file_count", "vendor_scanned_file_count", "vendor_unreadable_files", "vendor_host_rows", "vendor_source_manifest_sha256", "vendor_commands_cap_per_first_token", "vendor_command_text_max_chars", "vendor_redacted_rows", "host_key_space_sources"];

export function host_observation(name: string): Record<string, any> {
  let idx: any;
  try {
    idx = _loadUsageIndex();
  } catch (exc: any) {
    throw new QueryUnavailable(`capability_usage_index.json 不可达或损坏（${exc?.constructor?.name ?? "Error"}）`);
  }
  const meta = idx._meta ?? {};
  const keySpace: any[] = meta.host_key_space ?? [];
  const corpus: Record<string, any> = {};
  for (const key of _HOST_CORPUS_META_KEYS) {
    if (meta[key] !== null && meta[key] !== undefined) {
      corpus[key] = meta[key];
    }
  }
  return { host: name, host_key_space: keySpace, is_known_host: keySpace.includes(name), vendor: (idx.vendor_host_observations ?? {})[name], authored: (idx.authored_host_usage ?? {})[name], corpus };
}

const _CONFIRMATION_PATTERNS_PATH = path.join(_cex_data_path(""), "knowledge/data/compile_ref/confirmation_prompt_patterns.json");

function _loadConfirmationPatterns(): Record<string, any> {
  return JSON.parse(fs.readFileSync(_CONFIRMATION_PATTERNS_PATH, "utf8"));
}

export function confirmation_prompt_of(name: string): Record<string, any> | null {
  let data: any;
  try {
    data = _loadConfirmationPatterns();
  } catch (exc: any) {
    throw new QueryUnavailable(`confirmation_prompt_patterns.json 不可达或损坏（${exc?.constructor?.name ?? "Error"}）`);
  }
  for (const entry of data.lib_patterns ?? []) {
    if ((entry?.provenance ?? {}).function === name) {
      return entry;
    }
  }
  return null;
}

export const PARAM_SPLIT_RE = /((?:"(?:\\.|[^\\"])*"|'(?:\\.|[^\\'])*'|[^,])+)/;
export const _PARAM_SPLIT_RE = PARAM_SPLIT_RE;
export const SHELL_EXIT_CHANNEL_ON_DEVICE_CLI = false;

export function observe_exit_channel_error(host: string): string {
  const name = String(host ?? "").trim() || "the device under test";
  return `OBSERVE_EXIT on ${pyRepr(name)} is not supported: ${name} is an APV CLI host and the framework sends the G cell verbatim to the product CLI (cmd_config), so the shell exit-status wrapper \`( cmd ); ist_case_exit_code=$?; …\` has no channel there and would be rejected as a non-CLI command. Observe the product command's outcome with OBSERVE_ASSERT (found / abs_found on its output), or place the configuration in CONFIG; OBSERVE_EXIT is for shell hosts reached through test_env (routera / routerb / server*).`;
}
