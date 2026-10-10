// 生成：tools/extract_engine.py ← InfoTest main/kms/manual_catalog_store.py（sha256 96444bf13421dc6a）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { KNOWLEDGE_MANUAL } from "../knowledge_paths";
import { read_regular_nofollow } from "../case_compiler/_sealed_io";
import { accepts_schema } from "../common/schema_identity";

export const CATALOG_SCHEMA = "ist.manual-command-catalog";
export const CATALOG_STATUS_SCHEMA = "ist.manual-catalog-status";
export const CATALOG_STATUSES = new Set(["ok", "catalog_missing", "catalog_unreadable", "schema_unknown", "identity_uncoupled", "md_missing"]);
const _MAX_CATALOG_BYTES = 16 * 1024 * 1024;
const _SHA256_RE = /^[0-9a-f]{64}$/;

export function manual_root(): string {
  return KNOWLEDGE_MANUAL;
}

export function md_path(version: string, family: string, root?: string): string {
  return path.join(root ?? manual_root(), String(version), `${family}_cn.md`);
}

export function catalog_path(version: string, family: string, root?: string): string {
  return path.join(root ?? manual_root(), String(version), `${family}_cn.catalog.json`);
}

function _status(version: string, family: string, status: string, detail: string, catalog_sha256 = "", md_sha256 = ""): Record<string, any> {
  if (!CATALOG_STATUSES.has(status)) {
    throw new Error(status);
  }
  return { schema: CATALOG_STATUS_SCHEMA, version: String(version), family: String(family), status, detail, catalog_sha256, md_sha256 };
}

function _sealed_read(filePath: string, max_bytes: number): Buffer | null {
  try {
    return read_regular_nofollow(filePath, {
      errorType: Error,
      invalid_message: "manual catalog 路径无效",
      directory_message: "manual catalog 目录不可安全读取",
      open_message: "manual catalog 文件不可读",
      bounds_message: "manual catalog 文件大小越界",
      changed_message: "manual catalog 文件读取期间发生变化",
      max_bytes,
      min_bytes: 1,
    }) as Buffer;
  } catch {
    return null;
  }
}

function _real_directory(dirPath: string): boolean {
  try {
    return fs.lstatSync(dirPath).isDirectory();
  } catch {
    return true;
  }
}

export function catalog_schema_valid(catalog: any): boolean {
  if (typeof catalog !== "object" || catalog === null || Array.isArray(catalog) || !accepts_schema(catalog.schema, CATALOG_SCHEMA)) {
    return false;
  }
  const identity = catalog.identity;
  if (typeof identity !== "object" || identity === null || Array.isArray(identity)) {
    return false;
  }
  const adocMap = identity.adoc_sha256;
  if (typeof adocMap !== "object" || adocMap === null || Array.isArray(adocMap) || Object.keys(adocMap).length === 0) {
    return false;
  }
  for (const [name, digest] of Object.entries(adocMap)) {
    if (typeof name !== "string" || !name || path.basename(name) !== name || typeof digest !== "string" || !_SHA256_RE.test(digest)) {
      return false;
    }
  }
  const mdDigest = identity.md_sha256;
  if (typeof mdDigest !== "string" || !_SHA256_RE.test(mdDigest)) {
    return false;
  }
  for (const key of ["signatures", "value_domains", "worked_examples"]) {
    if (!Array.isArray(catalog[key])) {
      return false;
    }
  }
  return true;
}

const _CATALOG_STATUS_CACHE = new Map<string, [unknown, Record<string, any>]>();
const _COUPLED_CATALOG_CACHE = new Map<string, [unknown, Record<string, any> | null, Record<string, any>]>();
const _IDENTITY_CACHE_MAX = 32;
const _COUPLED_CACHE_MAX = 8;
const _CLAIMS_CACHE = new Map<string, Record<string, Record<string, any>>>();
const _CLAIMS_CACHE_MAX = 8;
const _COMPOUND_KEYWORD_RE_CACHE = new Map<string, RegExp>();

function _path_identity(filePath: string): number[] | null {
  try {
    const info = fs.lstatSync(filePath);
    return [info.mode, info.dev, info.ino, info.size, info.mtimeMs, info.ctimeMs];
  } catch {
    return null;
  }
}

export function manual_identity(version: string, family: string, root?: string): [number[] | null, number[] | null, number[] | null] {
  const base = root ?? manual_root();
  const md = md_path(version, family, base);
  return [_path_identity(path.dirname(md)), _path_identity(md), _path_identity(catalog_path(version, family, base))];
}

export function remember_bounded<K, V>(cache: Map<K, V>, key: K, value: V, limit: number): void {
  if (!cache.has(key) && cache.size >= limit) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) {
      cache.delete(oldest);
    }
  }
  cache.set(key, value);
}

export function clear_bounded(...caches: Array<Map<any, any>>): void {
  for (const cache of caches) {
    cache.clear();
  }
}

export function clear_catalog_cache(): void {
  clear_bounded(_CATALOG_STATUS_CACHE, _COUPLED_CATALOG_CACHE, _CLAIMS_CACHE);
}

export function load_catalog_status(version: string, family: string, root?: string): Record<string, any> {
  const base = root ?? manual_root();
  const key = `${base}\0${version}\0${family}`;
  const identity = manual_identity(version, family, base);
  const cached = _CATALOG_STATUS_CACHE.get(key);
  if (cached !== undefined && JSON.stringify(cached[0]) === JSON.stringify(identity)) {
    return { ...cached[1] };
  }
  const verdict = _verify_catalog_status(version, family, base);
  if (JSON.stringify(manual_identity(version, family, base)) === JSON.stringify(identity)) {
    remember_bounded(_CATALOG_STATUS_CACHE, key, [identity, verdict], _IDENTITY_CACHE_MAX);
  }
  return { ...verdict };
}

function _verify_catalog_status(version: string, family: string, base: string): Record<string, any> {
  const md = md_path(version, family, base);
  const cat = catalog_path(version, family, base);
  if (!_real_directory(path.dirname(md))) {
    return _status(version, family, "catalog_unreadable", `manual 版本目录不是真实目录（拒绝链接根）: ${path.dirname(md)}`);
  }
  const mdRaw = _sealed_read(md, _MAX_CATALOG_BYTES);
  if (mdRaw === null) {
    return _status(version, family, "md_missing", `manual md 缺席或不可读: ${md}`);
  }
  const mdSha = crypto.createHash("sha256").update(mdRaw).digest("hex");
  if (!fs.statSync(cat).isFile()) {
    return _status(version, family, "catalog_missing", `catalog 缺失但 md 在（裁决：拒绝生效，保留旧代际并披露）: ${cat}`, "", mdSha);
  }
  const raw = _sealed_read(cat, _MAX_CATALOG_BYTES);
  if (raw === null) {
    return _status(version, family, "catalog_unreadable", `catalog 不可安全读取（链接/越界/读间变化）: ${cat}`, "", mdSha);
  }
  const catalogSha = crypto.createHash("sha256").update(raw).digest("hex");
  let catalog: any;
  try {
    catalog = JSON.parse(raw.toString("utf8"));
  } catch {
    return _status(version, family, "catalog_unreadable", `catalog 不是合法 JSON: ${cat}`, catalogSha, mdSha);
  }
  if (!catalog_schema_valid(catalog)) {
    return _status(version, family, "schema_unknown", `catalog 不是合法 ${CATALOG_SCHEMA} 形态: ${cat}`, catalogSha, mdSha);
  }
  if (String(catalog.identity.md_sha256).toLowerCase() !== mdSha) {
    return _status(version, family, "identity_uncoupled", "catalog 内嵌 md sha256 与同目录 md 字节不符（非同池出生，拒绝生效）", catalogSha, mdSha);
  }
  return _status(version, family, "ok", "", catalogSha, mdSha);
}

export function load_coupled_catalog(version: string, family: string, root?: string): [Record<string, any> | null, Record<string, any>] {
  const base = root ?? manual_root();
  const key = `${base}\0${version}\0${family}`;
  const identity = manual_identity(version, family, base);
  const cached = _COUPLED_CATALOG_CACHE.get(key);
  if (cached !== undefined && JSON.stringify(cached[0]) === JSON.stringify(identity)) {
    return [cached[1], { ...cached[2] }];
  }
  const [catalog, verdict] = _verify_coupled_catalog(version, family, base);
  if (JSON.stringify(manual_identity(version, family, base)) === JSON.stringify(identity)) {
    remember_bounded(_COUPLED_CATALOG_CACHE, key, [identity, catalog, verdict], _COUPLED_CACHE_MAX);
  }
  return [catalog, { ...verdict }];
}

function _verify_coupled_catalog(version: string, family: string, base: string): [Record<string, any> | null, Record<string, any>] {
  const verdict = load_catalog_status(version, family, base);
  if (verdict.status !== "ok") {
    return [null, verdict];
  }
  const raw = _sealed_read(catalog_path(version, family, base), _MAX_CATALOG_BYTES);
  let catalog: any = null;
  if (raw !== null) {
    try {
      catalog = JSON.parse(raw.toString("utf8"));
    } catch {
      catalog = null;
    }
  }
  if (catalog === null) {
    return [null, _status(version, family, "catalog_unreadable", "catalog 读取竞态失败")];
  }
  return [catalog, verdict];
}

export function catalog_enum_is_closed_set(param: string, members: string[], desc: string): boolean {
  if (String(param ?? "").includes("|")) {
    return false;
  }
  const text = String(desc ?? "");
  if (text.includes("常见")) {
    return false;
  }
  for (const member of members) {
    const token = String(member ?? "").trim();
    if (!token) {
      continue;
    }
    let pattern = _COMPOUND_KEYWORD_RE_CACHE.get(token);
    if (pattern === undefined) {
      pattern = new RegExp(`${escapeRegExp(token)}\\s*=`);
      _COMPOUND_KEYWORD_RE_CACHE.set(token, pattern);
    }
    if (pattern.test(text)) {
      return false;
    }
  }
  return true;
}

export function catalog_row_describes_one_parameter(param: string): boolean {
  return !String(param ?? "").includes("|");
}

export function catalog_alternate_row_enum_is_closed_set(param: string, members: string[], desc: string): boolean {
  const raw = String(param ?? "");
  if (!raw.includes("|")) {
    return false;
  }
  const branches = raw.split("|").map((part) => part.trim()).filter((part) => part);
  const cleaned = members.map((item) => String(item).trim()).filter((item) => item);
  if (branches.length < 2 || cleaned.length < 2) {
    return false;
  }
  if (new Set(branches.map((b) => b.toLowerCase())).size !== new Set(cleaned.map((m) => m.toLowerCase())).size || ![...branches.map((b) => b.toLowerCase())].every((b) => cleaned.map((m) => m.toLowerCase()).includes(b))) {
    return false;
  }
  const text = String(desc ?? "");
  if (!text.includes("取值必须为")) {
    return false;
  }
  if (cleaned.some((member) => member.includes("_"))) {
    return false;
  }
  if (text.includes("常见")) {
    return false;
  }
  for (const member of cleaned) {
    if (new RegExp(`${escapeRegExp(member)}\\s*[：:]\\s*(?:该参数|表示)`).test(text)) {
      return false;
    }
    let pattern = _COMPOUND_KEYWORD_RE_CACHE.get(member);
    if (pattern === undefined) {
      pattern = new RegExp(`${escapeRegExp(member)}\\s*=`);
      _COMPOUND_KEYWORD_RE_CACHE.set(member, pattern);
    }
    if (pattern.test(text)) {
      return false;
    }
  }
  return true;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function catalog_manual_claims(catalog: Record<string, any>): Record<string, Record<string, any>> {
  const claims: Record<string, Record<string, any>> = {};
  for (const signature of catalog.signatures ?? []) {
    const tokens = signature.head_tokens ?? [];
    const head = tokens.map((token: any) => String(token)).filter(Boolean).join(" ").trim();
    if (!head) {
      continue;
    }
    const params = signature.params ?? [];
    const entry = { src: String(signature.src ?? ""), pmax: params.length, args: [], results: [], origin: "manual_declaration" };
    claims[head] ??= entry;
    for (const variant of signature.head_variants ?? []) {
      const variantHead = (variant ?? []).map((token: any) => String(token)).filter(Boolean).join(" ").trim();
      if (variantHead) {
        claims[variantHead] ??= { ...entry };
      }
    }
  }
  return claims;
}

export function manual_claims_view(version: string, family: string, root?: string): [Record<string, Record<string, any>>, Record<string, any>] {
  const [catalog, verdict] = load_coupled_catalog(version, family, root);
  if (catalog === null) {
    return [{}, verdict];
  }
  const key = `${verdict.version}\0${verdict.family}\0${verdict.catalog_sha256}`;
  let view = _CLAIMS_CACHE.get(key);
  if (view === undefined) {
    view = catalog_manual_claims(catalog);
    remember_bounded(_CLAIMS_CACHE, key, view, _CLAIMS_CACHE_MAX);
  }
  return [view, verdict];
}

export const PROJECTION_FRESHNESS_SCHEMA = "ist.projection-catalog-freshness";
export const PROJECTION_FRESHNESS_STATUSES = new Set(["current", "stale", "identity_absent", "catalog_unavailable"]);

export function projection_catalog_freshness(projection: any, root?: string): Record<string, any> {
  function _verdict(status: string, version: string, families: Record<string, string>, detail: string): Record<string, any> {
    if (!PROJECTION_FRESHNESS_STATUSES.has(status)) {
      throw new Error(status);
    }
    return { schema: PROJECTION_FRESHNESS_SCHEMA, status, version: String(version), families, detail };
  }
  if (typeof projection !== "object" || projection === null || Array.isArray(projection)) {
    return _verdict("identity_absent", "", {}, "投影不是对象");
  }
  const stats = projection.stats;
  const block = typeof stats === "object" && stats !== null ? (stats as any).value_domain : null;
  const catalogBlock = typeof block === "object" && block !== null ? block.manual_catalog : null;
  if (typeof catalogBlock !== "object" || catalogBlock === null) {
    return _verdict("identity_absent", "", {}, "投影未记录 manual_catalog 段");
  }
  const version = String(catalogBlock.version ?? "");
  const recorded = catalogBlock.identity;
  if (typeof recorded !== "object" || recorded === null || Object.keys(recorded).length === 0) {
    return _verdict("identity_absent", version, {}, "投影未记录分族 catalog sha256（本判据落地前生成的投影）");
  }
  const families: Record<string, string> = {};
  const stale: string[] = [];
  const unavailable: string[] = [];
  for (const [family, pinned] of Object.entries(recorded).sort(([a], [b]) => a.localeCompare(b))) {
    if (typeof pinned !== "object" || pinned === null) {
      families[String(family)] = "identity_absent";
      stale.push(String(family));
      continue;
    }
    const verdict = load_catalog_status(version, String(family), root);
    if (verdict.status !== "ok") {
      families[String(family)] = String(verdict.status ?? "unknown");
      unavailable.push(String(family));
      continue;
    }
    const same = String((pinned as any).catalog_sha256 ?? "") === String(verdict.catalog_sha256 ?? "");
    families[String(family)] = same ? "current" : "stale";
    if (!same) {
      stale.push(String(family));
    }
  }
  if (stale.length) {
    return _verdict("stale", version, families, "投影按旧 catalog 生成，分族不符: " + stale.sort().join(", "));
  }
  if (unavailable.length) {
    return _verdict("catalog_unavailable", version, families, "本地 catalog 不生效，无从比对: " + unavailable.sort().join(", "));
  }
  return _verdict("current", version, families, "");
}
