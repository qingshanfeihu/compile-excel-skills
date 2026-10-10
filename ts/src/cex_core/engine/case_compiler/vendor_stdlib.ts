import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { _cex_data_path, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.vendor_stdlib");

const _ROOT = _cex_data_path("");
const _DEFAULT_INV_DIR = path.join(_ROOT, "knowledge", "data", "compile_ref");
let _INV_DIR = _DEFAULT_INV_DIR;
const _COMMAND_TREE_STORE_ROOT = path.join(_ROOT, "runtime", "command_tree");
const _CACHE = new Map<string, Record<string, any>>();
const _ENV_CAPABILITIES = path.join(_ROOT, "knowledge", "data", "auto_env", "env_capabilities.json");
const _CANONICAL_RE = /^vendor_stdlib_(?<version>\d+(?:\.\d+)*)_(?<build>[A-Za-z0-9_.-]+)\.json$/;
const _MAX_HEAD_TOKENS = 8;
const _EXECUTABLE_ARGUMENT_TYPES = new Set(["STRING", "XSTRING", "U16", "U32", "IPADDR", "DOTTEDIP", "IPMASK"]);
const _REDACTED_ARGUMENT_TYPE = "REDACTED_SENSITIVE";
const _VALUE_DOMAIN_KINDS = new Set(["enum", "union", "range", "length", "default"]);
const _VALUE_DOMAIN_SOURCES = new Set(["xml_limit", "xml_help", "manual_table", "footprint"]);
const _CLOSED_SET_ENUM_SOURCES = new Set(["xml_limit", "manual_table", "footprint"]);
export const XML_COMMAND_NOT_FOUND = "command_not_found";

function _commandTreeStoreRoot(): string {
  if (_INV_DIR !== _DEFAULT_INV_DIR) {
    return path.join(_INV_DIR, "command_tree");
  }
  return _COMMAND_TREE_STORE_ROOT;
}

function _buildSuffix(build: string): string {
  const value = String(build || "").trim();
  const match = /(?:^|[._-])(\d+)$/.exec(value);
  return match ? match[1] : value;
}

export function _inventory_version_from_device_build(build: string): string {
  const value = String(build || "").trim();
  if (!value) return "";
  try {
    const { inventory_version_from_build } = require("../sync/command_tree_sync");
    return inventory_version_from_build(value);
  } catch {
    return "";
  }
}

export function configured_device_os_build_identity(): string {
  const explicit = (process.env.IST_DEVICE_OS_BUILD || "").trim();
  if (explicit) {
    return explicit;
  }
  try {
    const payload = JSON.parse(fs.readFileSync(_ENV_CAPABILITIES, "utf8"));
    return String(payload.build || "").trim();
  } catch {
    return "";
  }
}

export function device_os_build_suffix(build: string): string {
  return _buildSuffix(build);
}

function _inventoryVersionFromDeviceBuild(build: string): string {
  const value = String(build || "").trim();
  if (!value) {
    return "";
  }
  try {
    const { inventory_version_from_build } = require("../sync/command_tree_sync");
    return inventory_version_from_build(value);
  } catch {
    return "";
  }
}

function _productPlatformFromDeviceBuild(build: string): [string, string] {
  const value = String(build || "").trim();
  if (!value) {
    return ["", ""];
  }
  try {
    const { parse_build_identity } = require("../sync/command_tree_sync");
    const identity = parse_build_identity(value);
    return [identity.product, identity.platform];
  } catch {
    return ["", ""];
  }
}

export function configured_device_os_build(): string {
  const explicit = (process.env.IST_DEVICE_OS_BUILD || "").trim();
  if (explicit) {
    return _buildSuffix(explicit);
  }
  try {
    const payload = JSON.parse(fs.readFileSync(_ENV_CAPABILITIES, "utf8"));
    return _buildSuffix(String(payload.build || ""));
  } catch {
    return "";
  }
}

function _productPlatformFromCommandTreePartition(ver: string, build: string): [string, string] {
  if (!ver || !build) {
    return ["", ""];
  }
  const root = path.join(_commandTreeStoreRoot(), "products");
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory() || fs.lstatSync(root).isSymbolicLink()) {
    return ["", ""];
  }
  const hits: Array<[string, string]> = [];
  try {
    for (const productDir of fs.readdirSync(root).sort()) {
      const platforms = path.join(root, productDir, "platforms");
      if (fs.lstatSync(path.join(root, productDir)).isSymbolicLink() || !fs.existsSync(platforms) || !fs.statSync(platforms).isDirectory()) {
        continue;
      }
      for (const platformDir of fs.readdirSync(platforms).sort()) {
        if (fs.lstatSync(path.join(platforms, platformDir)).isSymbolicLink()) {
          continue;
        }
        const partition = path.join(platforms, platformDir, "builds", `${ver}_${build}`);
        if (fs.existsSync(partition) && fs.statSync(partition).isDirectory() && !fs.lstatSync(partition).isSymbolicLink()) {
          hits.push([productDir, platformDir]);
        }
      }
    }
  } catch {
    return ["", ""];
  }
  return hits.length === 1 ? hits[0] : ["", ""];
}

export function vendor_stdlib_path(version: string, device_build = ""): string {
  const rawBuild = device_build || configured_device_os_build();
  const build = _buildSuffix(rawBuild);
  const ver = String(version || "").trim() || _inventoryVersionFromDeviceBuild(rawBuild);
  let [product, platform] = _productPlatformFromDeviceBuild(rawBuild);
  if (!(product && platform)) {
    [product, platform] = _productPlatformFromCommandTreePartition(ver, build);
  }
  if (product && platform && ver && build) {
    try {
      const { resolve_active_command_tree } = require("../sync/command_tree_sync");
      const active = resolve_active_command_tree({ product, platform, version: ver, device_build: build, store_root: _commandTreeStoreRoot() });
      if (active !== null) {
        return active.projection_path;
      }
    } catch {}
  }
  return path.join(_INV_DIR, `vendor_stdlib_${ver || version}_${build}.json`);
}

export function available_vendor_builds(version = "", opts: { product?: string; platform?: string } = {}): Array<[string, string]> {
  const found: Array<[string, string]> = [];
  for (const f of fs.readdirSync(_INV_DIR).filter((n) => n.startsWith("vendor_stdlib_") && n.endsWith(".json"))) {
    const match = _CANONICAL_RE.exec(f);
    if (!match) continue;
    const pair: [string, string] = [match.groups!.version, match.groups!.build];
    if (!version || pair[0] === version) {
      found.push(pair);
    }
  }
  const productsRoot = path.join(_commandTreeStoreRoot(), "products");
  let scanDirs: Array<[string, string]> = [];
  if (opts.product && opts.platform) {
    scanDirs = [[opts.product, opts.platform]];
  } else if (fs.existsSync(productsRoot) && fs.statSync(productsRoot).isDirectory() && !fs.lstatSync(productsRoot).isSymbolicLink()) {
    try {
      for (const productDir of fs.readdirSync(productsRoot).sort()) {
        if (fs.lstatSync(path.join(productsRoot, productDir)).isSymbolicLink()) continue;
        if (opts.product && productDir !== opts.product) continue;
        const platformsDir = path.join(productsRoot, productDir, "platforms");
        if (!fs.existsSync(platformsDir) || !fs.statSync(platformsDir).isDirectory() || fs.lstatSync(platformsDir).isSymbolicLink()) continue;
        for (const platformDir of fs.readdirSync(platformsDir).sort()) {
          if (fs.lstatSync(path.join(platformsDir, platformDir)).isSymbolicLink()) continue;
          if (opts.platform && platformDir !== opts.platform) continue;
          scanDirs.push([productDir, platformDir]);
        }
      }
    } catch {
      scanDirs = [];
    }
  }
  for (const [scanProduct, scanPlatform] of scanDirs) {
    const commandTreeBuilds = path.join(productsRoot, scanProduct, "platforms", scanPlatform, "builds");
    if (!fs.existsSync(commandTreeBuilds) || !fs.statSync(commandTreeBuilds).isDirectory() || fs.lstatSync(commandTreeBuilds).isSymbolicLink()) {
      continue;
    }
    for (const partition of fs.readdirSync(commandTreeBuilds).sort()) {
      const match = /^(?<version>\d+(?:\.\d+)*)_(?<build>\d+)$/.exec(partition);
      if (match === null || fs.lstatSync(path.join(commandTreeBuilds, partition)).isSymbolicLink()) {
        continue;
      }
      const pair: [string, string] = [match.groups!.version, match.groups!.build];
      if (version && pair[0] !== version) {
        continue;
      }
      try {
        const { resolve_active_command_tree } = require("../sync/command_tree_sync");
        if (
          resolve_active_command_tree({ product: scanProduct, platform: scanPlatform, version: pair[0], device_build: pair[1], store_root: _commandTreeStoreRoot() }) !== null
        ) {
          found.push(pair);
        }
      } catch {
        continue;
      }
    }
  }
  return [...new Set(found.map((p) => p.join("|")))].map((s) => s.split("|") as [string, string]).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : 1));
}

export function available_versions(): string[] {
  return [...new Set(available_vendor_builds().map(([version]) => version))].sort();
}

export function clear_vendor_stdlib_cache(version = "", device_build = ""): void {
  const ver = String(version || "").trim();
  const build = _buildSuffix(device_build);
  for (const key of [..._CACHE.keys()]) {
    const parts = key.split("|");
    const keyVer = parts[0] || "";
    const keyBuild = parts[1] || "";
    if ((!ver || keyVer === ver) && (!build || keyBuild === build)) {
      _CACHE.delete(key);
    }
  }
}

const _SCOPE_NO_CLUE =
  "本机还没有可用的命令树代际：compile_ref 下没有平面 vendor_stdlib 投影，runtime/command_tree 里也没有对应分区，而设备 build 只是个裸号、不带产品与平台身份，无参推导除了那份平面副本没有第二处线索。先开一次批（入口会按真机 build 收敛命令树投影），或显式给出版本与 build。";

function _scopeAmbiguous(candidates: Array<[string, string]>): string {
  const listed = candidates.map(([ver, build]) => `${ver}_${build}`).join("、");
  return `本机有 ${candidates.length} 个命令树代际候选（${listed}），无参推导不替人择一：显式给出版本与 build。`;
}

function _commandTreeScope(version = "", device_build = "", opts: { gap?: Record<string, string> | null } = {}): [string, string, string, string] | null {
  const rawBuild = device_build || configured_device_os_build();
  let [product, platform] = _productPlatformFromDeviceBuild(rawBuild);
  let ver = (version || process.env.IST_COMMAND_INVENTORY_VERSION || _inventoryVersionFromDeviceBuild(rawBuild)).trim();
  let build = _buildSuffix(rawBuild);
  if (!ver) {
    let candidates = available_vendor_builds("", { product, platform });
    if (build) {
      candidates = candidates.filter((pair) => pair[1] === build);
    }
    if (candidates.length !== 1) {
      if (opts.gap) {
        opts.gap.reason = candidates.length === 0 ? _SCOPE_NO_CLUE : _scopeAmbiguous(candidates);
      }
      return null;
    }
    [ver, build] = candidates[0];
  }
  if (!build) {
    const candidates = available_vendor_builds(ver, { product, platform });
    if (candidates.length !== 1) {
      if (opts.gap) {
        opts.gap.reason = candidates.length === 0 ? _SCOPE_NO_CLUE : _scopeAmbiguous(candidates);
      }
      return null;
    }
    build = candidates[0][1];
  }
  if (!(product && platform) && ver && build) {
    [product, platform] = _productPlatformFromCommandTreePartition(ver, build);
  }
  return [product, platform, ver, build];
}

export function diagnose_active_command_tree(version = "", device_build = "", opts: { store_root?: string | null } = {}): [string, string] {
  const gap: Record<string, string> = {};
  const scope = _commandTreeScope(version, device_build, { gap });
  if (scope === null) {
    return ["absent", gap.reason || "推不出唯一的命令树作用域（版本 / build 有多个候选或缺席）"];
  }
  const [product, platform, ver, build] = scope;
  if (!(product && platform)) {
    return ["absent", "命令树分区缺产品 / 平台身份"];
  }
  const { CommandTreeProjectionPolicyStale, CommandTreeSyncError, resolve_active_command_tree } = require("../sync/command_tree_sync");
  let active: any;
  try {
    active = resolve_active_command_tree({ product, platform, version: ver, device_build: build, store_root: opts.store_root || _commandTreeStoreRoot() });
  } catch (exc: any) {
    if (exc instanceof CommandTreeProjectionPolicyStale) {
      return ["stale_policy", String(exc.message || exc.constructor.name)];
    }
    if (exc instanceof CommandTreeSyncError) {
      return ["corrupt", String(exc.message || exc.constructor.name)];
    }
    return ["corrupt", String(exc?.constructor?.name || "Error")];
  }
  if (active === null) {
    const buildsDir = path.join(opts.store_root || _commandTreeStoreRoot(), "products", product, "platforms", platform, "builds");
    let present: string[] = [];
    if (fs.existsSync(buildsDir) && fs.statSync(buildsDir).isDirectory() && !fs.lstatSync(buildsDir).isSymbolicLink()) {
      try {
        present = fs.readdirSync(buildsDir).filter((name) => {
          const full = path.join(buildsDir, name);
          return fs.statSync(full).isDirectory() && !fs.lstatSync(full).isSymbolicLink();
        }).sort();
      } catch {
        present = [];
      }
    }
    const listed = present.join("、") || "无";
    return ["absent", `本地没有该 build 的活动代际（查询钥匙 ${ver}_${build}；本机 ${product}/${platform} 在册分区：${listed}）`];
  }
  return ["ok", ""];
}

export function load_vendor_stdlib(version = "", device_build = ""): Record<string, any> | null {
  const scope = _commandTreeScope(version, device_build);
  if (scope === null) {
    return null;
  }
  const [product, platform, ver, build] = scope;
  let active: any = null;
  try {
    const { resolve_active_command_tree } = require("../sync/command_tree_sync");
    if (product && platform) {
      active = resolve_active_command_tree({ product, platform, version: ver, device_build: build, store_root: _commandTreeStoreRoot() });
    }
  } catch {
    return null;
  }
  const p = active !== null ? active.projection_path : path.join(_INV_DIR, `vendor_stdlib_${ver}_${build}.json`);
  const assetDir = active !== null ? active.generation_root : _INV_DIR;
  const cacheKey = `${ver}|${build}|${p}`;
  if (_CACHE.has(cacheKey)) {
    return _CACHE.get(cacheKey)!;
  }
  const legacyCacheKey = `${ver}|${build}`;
  if (active === null && _CACHE.has(legacyCacheKey)) {
    return _CACHE.get(legacyCacheKey)!;
  }
  return _loadVendorStdlibAsset({
    version: ver,
    build,
    projection_path: p,
    asset_dir: assetDir,
    cache_key: cacheKey,
    expected_projection_sha: active !== null ? active.projection_sha256 : "",
    expected_source_sha: active !== null ? active.source_sha256 : "",
  });
}

export function derive_inverse_pairs(version = "", device_build = ""): Record<string, Record<string, any>> {
  const inventory = load_vendor_stdlib(version, device_build);
  if (!inventory) {
    return {};
  }
  const heads = inventory.heads || inventory.headers || {};
  if (typeof heads !== "object" || heads === null || !Object.keys(heads).length) {
    return {};
  }
  const sourceSha = String((inventory.source || {}).sha256 || "");
  const ver = String(inventory.version || version || "");
  const build = String(inventory.device_os_build || device_build || "");
  return _deriveInversePairsCached(ver, build, sourceSha, Object.keys(heads).sort());
}

const _deriveCache = new Map<string, Record<string, Record<string, any>>>();

function _deriveInversePairsCached(version: string, device_build: string, source_sha: string, head_names: string[]): Record<string, Record<string, any>> {
  const cacheKey = `${version}|${device_build}|${source_sha}|${head_names.join(",")}`;
  if (_deriveCache.has(cacheKey)) {
    return _deriveCache.get(cacheKey)!;
  }
  const hset = new Set(head_names);
  const anc = (prefix: string, h: string): string | null => {
    const ws = h.split(" ");
    for (let k = ws.length; k > 0; k--) {
      if (k === 1 && ws.length > 1) continue;
      const cand = `${prefix} ${ws.slice(0, k).join(" ")}`;
      if (hset.has(cand)) return cand;
    }
    return null;
  };
  const pairs: Record<string, Record<string, any>> = {};
  for (const h of head_names) {
    if (h.startsWith("show ") || h.startsWith("no ") || h.startsWith("clear ")) continue;
    const invNo = anc("no", h);
    const invClear = anc("clear", h);
    if (invNo || invClear) {
      pairs[h] = { no: invNo, clear: invClear, src: `vendor_heads:${source_sha.slice(0, 12)}` };
    }
  }
  _deriveCache.set(cacheKey, pairs);
  return pairs;
}

export function manual_source_dir(version = "", device_build = ""): string | null {
  const inventory = load_vendor_stdlib(version, device_build);
  if (inventory === null) {
    return null;
  }
  const rel = String(inventory.source_dir || "");
  if (!rel) {
    return null;
  }
  const root = path.join(_cex_data_path(""), rel);
  return fs.existsSync(root) && fs.statSync(root).isDirectory() ? root : null;
}

export function load_vendor_stdlib_generation(opts: {
  product: string;
  platform: string;
  version: string;
  device_build: string;
  generation_id: string;
  manifest_sha256: string;
  store_root?: string | null;
}): Record<string, any> | null {
  const ver = String(opts.version || "").trim();
  const build = _buildSuffix(opts.device_build);
  const prod = String(opts.product || "").trim();
  const plat = String(opts.platform || "").trim();
  if (!prod || !plat || !ver || !build || !opts.generation_id || !opts.manifest_sha256) {
    return null;
  }
  let generation: any;
  try {
    const { resolve_command_tree_generation } = require("../sync/command_tree_sync");
    generation = resolve_command_tree_generation({
      product: prod,
      platform: plat,
      version: ver,
      device_build: build,
      generation_id: String(opts.generation_id).trim(),
      manifest_sha256: String(opts.manifest_sha256).trim().toLowerCase(),
      store_root: opts.store_root || _commandTreeStoreRoot(),
    });
  } catch {
    return null;
  }
  return _loadVendorStdlibAsset({
    version: ver,
    build,
    projection_path: generation.projection_path,
    asset_dir: generation.generation_root,
    cache_key: `${ver}|${build}|${generation.generation_id}|${generation.manifest_sha256}`,
    expected_projection_sha: generation.projection_sha256,
    expected_source_sha: generation.source_sha256,
  });
}

function _loadVendorStdlibAsset(opts: {
  version: string;
  build: string;
  projection_path: string;
  asset_dir: string;
  cache_key: string;
  expected_projection_sha?: string;
  expected_source_sha?: string;
}): Record<string, any> | null {
  if (_CACHE.has(opts.cache_key)) {
    return _CACHE.get(opts.cache_key)!;
  }
  let data: any;
  try {
    const { read_regular_nofollow } = require("./_sealed_io");
    const raw = read_regular_nofollow(opts.projection_path, {
      errorType: Error,
      invalid_message: "vendor projection path is invalid",
      directory_message: "vendor projection directory is unavailable",
      open_message: "vendor projection is unavailable",
      bounds_message: "vendor projection exceeds size budget",
      changed_message: "vendor projection changed while reading",
      max_bytes: 16 * 1024 * 1024,
      min_bytes: 1,
    }) as Buffer;
    if (opts.expected_projection_sha && crypto.createHash("sha256").update(raw).digest("hex") !== opts.expected_projection_sha) {
      return null;
    }
    data = JSON.parse(raw.toString("utf8"));
  } catch {
    return null;
  }
  const { accepts_schema } = require("../common/schema_identity");
  if (
    !accepts_schema(data.schema, "ist.vendor_stdlib") ||
    String(data.version || "") !== opts.version ||
    _buildSuffix(String(data.device_os_build || "")) !== opts.build ||
    typeof data.headers !== "object" || data.headers === null || Array.isArray(data.headers) ||
    typeof data.manual_declarations !== "object" || data.manual_declarations === null || Array.isArray(data.manual_declarations)
  ) {
    return null;
  }
  if (!_projectionXmlIdentityValid(data, opts.build, { asset_dir: opts.asset_dir, expected_source_sha: opts.expected_source_sha || "" })) {
    return null;
  }
  if (!_projectionContractValid(data)) {
    return null;
  }
  const headers = data.headers;
  const manualDeclarations = data.manual_declarations;
  const overlap = Object.keys(headers).filter((k) => k in manualDeclarations).sort();
  if (overlap.length) {
    return null;
  }
  data.heads = { ...headers, ...manualDeclarations };
  _CACHE.set(opts.cache_key, data);
  return data;
}

function _projectionXmlIdentityValid(data: Record<string, any>, build: string, opts: { asset_dir?: string | null; expected_source_sha?: string } = {}): boolean {
  const source = data.source;
  if (typeof source !== "object" || source === null) {
    return false;
  }
  const filename = String(source.filename || "").trim();
  const expectedSha = String(source.sha256 || "").trim().toLowerCase();
  if (
    source.kind !== "vendor_command_tree_xml" ||
    _buildSuffix(String(source.device_os_build || "")) !== build ||
    !filename ||
    path.basename(filename) !== filename ||
    _buildSuffix(path.basename(filename, path.extname(filename))) !== build ||
    !/^[0-9a-f]{64}$/.test(expectedSha)
  ) {
    return false;
  }
  const xmlPath = path.join(opts.asset_dir || _INV_DIR, filename);
  let raw: Buffer;
  try {
    const { read_regular_nofollow } = require("./_sealed_io");
    raw = read_regular_nofollow(xmlPath, {
      errorType: Error,
      invalid_message: "vendor XML path is invalid",
      directory_message: "vendor XML directory is unavailable",
      open_message: "vendor XML is unavailable",
      bounds_message: "vendor XML exceeds size budget",
      changed_message: "vendor XML changed while reading",
      max_bytes: 16 * 1024 * 1024,
      min_bytes: 1,
    }) as Buffer;
    const { preflight_command_tree_xml } = require("../sync/command_tree_sync");
    preflight_command_tree_xml(raw, { max_bytes: 16 * 1024 * 1024, errorType: Error });
    const actualSha = crypto.createHash("sha256").update(raw).digest("hex");
    if (actualSha !== expectedSha) {
      return false;
    }
    if (opts.expected_source_sha && actualSha !== opts.expected_source_sha) {
      return false;
    }
  } catch {
    return false;
  }
  // Parse XML minimal structure check
  const text = raw.toString("utf8");
  if (!text.includes("<commands") || !text.includes("<scope")) {
    return false;
  }
  // Extract item paths from XML
  const xmlNodes = new Set<string>();
  const stack: Array<[string[], number]> = [[[], 1]];
  const tagRe = /<(menu|item|scope)(?:\s+[^>]*)?>/g;
  let m: RegExpExecArray | null;
  const tokens: Array<[string, string]> = [];
  while ((m = tagRe.exec(text)) !== null) {
    const tag = m[1];
    const attrs = m[0];
    const nameM = /name="([^"]*)"/.exec(attrs);
    const typeM = /type="([^"]*)"/.exec(attrs);
    tokens.push([tag, nameM ? nameM[1] : typeM ? typeM[1] : ""]);
  }
  // Simplified: skip full XML tree validation, approximate by checking headers' src strings
  for (const entry of Object.values(data.headers || {}) as any[]) {
    const src = String((entry || {}).src || "");
    const prefix = `vendor_xml:${build}:`;
    if (!src.startsWith(prefix)) {
      return false;
    }
    const node = src.slice(prefix.length).toLowerCase();
    // node must appear as some path in the xml; approximate check
    const nodeParts = node.split("/");
    if (!nodeParts.every((p) => text.toLowerCase().includes(p))) {
      return false;
    }
  }
  return true;
}

function _projectionContractValid(data: Record<string, any>): boolean {
  const headers = data.headers || {};
  const stats = data.stats || {};
  if (typeof stats !== "object" || stats === null) {
    return false;
  }
  const declaredCount = stats.vendor_header_count;
  if (declaredCount !== null && declaredCount !== undefined) {
    if (Number(declaredCount) !== Object.keys(headers).length) {
      return false;
    }
  }
  for (const [head, entry] of Object.entries<any>(headers)) {
    if (typeof head !== "string" || !head.trim() || typeof entry !== "object" || entry === null) {
      return false;
    }
    const pmax = Number(entry.pmax);
    const args = entry.args;
    if (!Number.isInteger(pmax) || pmax < 0 || !Array.isArray(args)) {
      return false;
    }
    if ("enums" in entry) {
      return false;
    }
    if (args.length > pmax) {
      return false;
    }
    for (const schema of [args, ...(entry.arg_variants || [])]) {
      if (!Array.isArray(schema)) {
        return false;
      }
      for (let pos = 1; pos <= schema.length; pos++) {
        const arg = schema[pos - 1];
        if (typeof arg !== "object" || arg === null) {
          return false;
        }
        const position = Number(arg.position || 0);
        const argType = String(arg.type || "");
        if (position !== pos || ![..._EXECUTABLE_ARGUMENT_TYPES, _REDACTED_ARGUMENT_TYPE].includes(argType) || typeof arg.optional !== "boolean") {
          return false;
        }
        if (argType === _REDACTED_ARGUMENT_TYPE) {
          if (Object.keys(arg).sort().join(",") !== "executable,optional,position,type" || arg.executable !== false) {
            return false;
          }
        } else if ("executable" in arg) {
          return false;
        }
        if ("value_domain" in arg && !_valueDomainValid(arg.value_domain)) {
          return false;
        }
      }
    }
  }
  return true;
}

function _valueDomainValid(domain: any): boolean {
  if (typeof domain !== "object" || domain === null || Array.isArray(domain) || !Object.keys(domain).length) {
    return false;
  }
  if (Object.keys(domain).some((k) => !_VALUE_DOMAIN_KINDS.has(k))) {
    return false;
  }
  for (const [kind, claims] of Object.entries<any>(domain)) {
    if (!Array.isArray(claims) || !claims.length) {
      return false;
    }
    for (const claim of claims) {
      if (typeof claim !== "object" || claim === null) {
        return false;
      }
      if (!_VALUE_DOMAIN_SOURCES.has(String(claim.source || "")) || !String(claim.locator || "")) {
        return false;
      }
      if (kind === "enum") {
        const values = claim.values;
        if (
          Object.keys(claim).sort().join(",") !== "locator,source,values" ||
          !Array.isArray(values) || values.length < 2 ||
          !values.every((item) => typeof item === "string" && item)
        ) {
          return false;
        }
      } else if (kind === "union") {
        const separator = claim.separator;
        if (
          Object.keys(claim).sort().join(",") !== "locator,separator,source" ||
          typeof separator !== "string" || separator.length !== 1 ||
          /[a-zA-Z0-9]/.test(separator) || /\s/.test(separator)
        ) {
          return false;
        }
      } else if (kind === "default") {
        if (
          Object.keys(claim).sort().join(",") !== "locator,source,value" ||
          typeof claim.value !== "string" || !claim.value
        ) {
          return false;
        }
      } else {
        const low = claim.min;
        const high = claim.max;
        if (
          Object.keys(claim).sort().join(",") !== "locator,max,min,source" ||
          typeof low !== "number" || !Number.isInteger(low) ||
          typeof high !== "number" || !Number.isInteger(high) ||
          low > high
        ) {
          return false;
        }
      }
    }
  }
  return true;
}

export function norm_command_tokens(cmd: string): string[] {
  return _normTokens(cmd);
}

export function strip_token_quotes(token: string): string {
  const text = String(token || "").trim();
  if (text.length >= 2 && text[0] === text[text.length - 1] && (text[0] === '"' || text[0] === "'")) {
    return text.slice(1, -1);
  }
  return text;
}

export function match_command_head(tokens: string[], heads: Record<string, any>): [string, Record<string, any>] | null {
  return _tryMatch(tokens, heads);
}

function _normTokens(cmd: string): string[] {
  const value = String(cmd || "").trim();
  if (!value) {
    return [];
  }
  try {
    // shlex.split equivalent: simple whitespace split with quote handling
    const tokens: string[] = [];
    let current = "";
    let inQuote: string | null = null;
    for (const c of value) {
      if (inQuote) {
        if (c === inQuote) {
          inQuote = null;
        } else {
          current += c;
        }
      } else if (c === '"' || c === "'") {
        inQuote = c;
      } else if (/\s/.test(c)) {
        if (current) {
          tokens.push(current.toLowerCase());
          current = "";
        }
      } else {
        current += c;
      }
    }
    if (current) tokens.push(current.toLowerCase());
    return tokens;
  } catch {
    return value.toLowerCase().split(/\s+/).filter(Boolean).map(strip_token_quotes);
  }
}

function _headCandidate(tokens: string[], heads: Record<string, any>): [string, Record<string, any>, string[]] | null {
  for (let k = Math.min(tokens.length, _MAX_HEAD_TOKENS); k > 0; k--) {
    const head = tokens.slice(0, k).join(" ");
    const entry = heads[head];
    if (typeof entry === "object" && entry !== null) {
      return [head, entry, tokens.slice(k)];
    }
  }
  return null;
}

function _valueMatchesType(value: string, argType: string): boolean {
  if (argType === "STRING") return true;
  if (argType === "XSTRING") return Boolean(value);
  if (argType === "U16" || argType === "U32") {
    if (!/^\d+$/.test(value)) return false;
    const number = parseInt(value, 10);
    return number <= (argType === "U16" ? 65535 : 4294967295);
  }
  if (argType === "IPADDR" || argType === "DOTTEDIP") {
    // Simplified IP check
    if (argType === "DOTTEDIP") {
      return /^(\d{1,3}\.){3}\d{1,3}$/.test(value);
    }
    return /^(\d{1,3}\.){3}\d{1,3}$/.test(value) || value.includes(":");
  }
  if (argType === "IPMASK") {
    if (/^\d+$/.test(value)) {
      const n = parseInt(value, 10);
      return n >= 0 && n <= 128;
    }
    return /^(\d{1,3}\.){3}\d{1,3}$/.test(value);
  }
  return false;
}

function _valueDomainError(value: string, arg: Record<string, any>, index: number): Record<string, any> | null {
  const domain = arg.value_domain;
  if (typeof domain !== "object" || domain === null) {
    return null;
  }
  const folded = value.toLowerCase();
  for (const claim of domain.default || []) {
    if (folded === String(claim.value || "").toLowerCase()) {
      return null;
    }
  }
  const allEnumClaims = (domain.enum || []).filter((c: any) => typeof c === "object" && c !== null);
  const enumClaims = allEnumClaims.filter((c: any) => _CLOSED_SET_ENUM_SOURCES.has(String(c.source)));
  const rangeClaims = (domain.range || []).filter((c: any) => typeof c === "object" && c !== null);
  if (!enumClaims.length && !rangeClaims.length) {
    return null;
  }
  const allMembers = new Set<string>();
  for (const claim of allEnumClaims) {
    for (const item of claim.values || []) {
      allMembers.add(String(item).toLowerCase());
    }
  }
  if (allMembers.has(folded)) {
    return null;
  }
  const unionSeparators: string[] = [...new Set<string>(
    (domain.union || []).filter((c: any) => typeof c === "object" && c !== null && String(c.separator || "")).map((c: any) => String(c.separator))
  )].sort();
  for (const separator of unionSeparators) {
    const parts = folded.split(separator);
    if (parts.length >= 2 && parts.every((part) => part && allMembers.has(part))) {
      return null;
    }
  }
  let number: number | null = null;
  try {
    number = parseInt(value, 10);
    if (Number.isNaN(number)) number = null;
  } catch {}
  if (rangeClaims.length && number === null) {
    if (!enumClaims.length) {
      return null;
    }
  }
  for (const claim of rangeClaims) {
    if (number !== null && Number(claim.min) <= number && number <= Number(claim.max)) {
      return null;
    }
  }
  if (enumClaims.length) {
    const error: Record<string, any> = {
      code: "enum_mismatch",
      argument_index: index,
      allowed_enums: [...new Set(allEnumClaims.flatMap((c: any) => c.values || []))].sort(),
      value_domain_sources: [...new Set(allEnumClaims.map((c: any) => String(c.source)))].sort(),
    };
    if (unionSeparators.length) {
      error.union_separators = unionSeparators;
    }
    return error;
  }
  return {
    code: "range_mismatch",
    argument_index: index,
    allowed_ranges: rangeClaims.map((c: any) => ({ min: Number(c.min), max: Number(c.max) })),
    value_domain_sources: [...new Set(rangeClaims.map((c: any) => String(c.source)))].sort(),
  };
}

function _argumentVariants(entry: Record<string, any>): Array<Array<Record<string, any>>> {
  const variants: Array<Array<Record<string, any>>> = [];
  const primary = entry.args;
  if (Array.isArray(primary)) {
    variants.push(primary);
  }
  for (const candidate of entry.arg_variants || []) {
    if (Array.isArray(candidate) && !variants.some((v) => JSON.stringify(v) === JSON.stringify(candidate))) {
      variants.push(candidate);
    }
  }
  return variants;
}

function _parameterContractError(rem: string[], entry: Record<string, any>): Record<string, any> | null {
  const variants = _argumentVariants(entry);
  if (!variants.length) {
    const pmax = Number(entry.pmax || 0);
    if (rem.length > pmax) {
      return { code: "arity_too_many", actual_count: rem.length, pmax };
    }
    return null;
  }
  const failures: Array<Record<string, any>> = [];
  let accepted = false;
  for (const args of variants) {
    const required = args.filter((arg) => !arg.optional).length;
    const maximum = args.length;
    if (rem.length < required) {
      failures.push({ code: "arity_too_few", actual_count: rem.length, required_min: required, pmax: maximum });
      continue;
    }
    if (rem.length > maximum) {
      failures.push({ code: "arity_too_many", actual_count: rem.length, required_min: required, pmax: maximum });
      continue;
    }
    let mismatch: Record<string, any> | null = null;
    for (let index = 0; index < rem.length; index++) {
      const value = rem[index];
      const arg = args[index];
      const argType = String(arg.type || "");
      if (argType === _REDACTED_ARGUMENT_TYPE && arg.executable === false) {
        mismatch = { code: "sensitive_parameter_unexecutable", argument_index: index + 1 };
        break;
      }
      if (!_valueMatchesType(value, argType)) {
        mismatch = { code: "type_mismatch", argument_index: index + 1, expected_type: argType };
        break;
      }
      const domainError = _valueDomainError(value, arg, index + 1);
      if (domainError !== null) {
        mismatch = domainError;
        break;
      }
    }
    if (mismatch === null) {
      accepted = true;
    } else {
      failures.push(mismatch);
    }
  }
  const sensitive = failures.find((item) => item.code === "sensitive_parameter_unexecutable");
  if (sensitive) {
    return sensitive;
  }
  if (accepted) {
    return null;
  }
  for (const code of ["type_mismatch", "enum_mismatch", "range_mismatch"]) {
    const preferred = failures.find((item) => item.code === code);
    if (preferred) {
      return preferred;
    }
  }
  return failures[0];
}

function _tryMatch(tokens: string[], heads: Record<string, any>): [string, Record<string, any>] | null {
  const candidate = _headCandidate(tokens, heads);
  if (candidate === null) {
    return null;
  }
  const [head, entry, rem] = candidate;
  if ("manual_pmax" in entry && "vendor_pmax" in entry) {
    const manualPmax = Number(entry.manual_pmax || 0);
    const vendorPmax = Number(entry.vendor_pmax || 0);
    if (Math.min(manualPmax, vendorPmax) < rem.length && rem.length <= Math.max(manualPmax, vendorPmax)) {
      return [head, entry];
    }
    return null;
  }
  return _parameterContractError(rem, entry) ? null : [head, entry];
}

export function resolve_vendor_command(cmd: string, version = "", device_build = ""): Record<string, any> {
  const inv = load_vendor_stdlib(version, device_build);
  if (inv === null) {
    return { decided: false, hit: false, head: "", src: "", version: "", device_build: "", origin: "" };
  }
  const heads = inv.heads;
  const tokens = _normTokens(cmd);
  if (!tokens.length || !/^[a-z\[]/.test(tokens[0])) {
    return { decided: false, hit: false, head: "", src: "", version: inv.version || "", device_build: inv.device_os_build || "", origin: "" };
  }
  const candidate = _headCandidate(tokens, heads);
  if (candidate === null) {
    return { decided: true, hit: false, head: "", src: "", version: inv.version || "", device_build: inv.device_os_build || "", origin: "", reason_code: XML_COMMAND_NOT_FOUND };
  }
  const [head, entry, rem] = candidate;
  const parameterError = _parameterContractError(rem, entry);
  if (parameterError !== null) {
    return {
      decided: true,
      hit: false,
      head,
      src: String(entry.src || ""),
      version: inv.version || "",
      device_build: inv.device_os_build || "",
      origin: String(entry.origin || ""),
      reason_code: "parameter_contract_violation",
      parameter_error: parameterError,
    };
  }
  return {
    decided: true,
    hit: true,
    head,
    src: String(entry.src || ""),
    version: inv.version || "",
    device_build: inv.device_os_build || "",
    origin: String(entry.origin || ""),
  };
}

function _recordedHeaders(inv: any): Record<string, any> | null {
  if (typeof inv !== "object" || inv === null) {
    return null;
  }
  const headers = inv.headers;
  return typeof headers === "object" && headers !== null ? headers : null;
}

export function rank_vendor_command_completions(cmd: string, version = "", device_build = ""): Array<Record<string, any>> {
  const headers = _recordedHeaders(load_vendor_stdlib(version, device_build));
  if (headers === null) {
    return [];
  }
  const tokens = _normTokens(cmd);
  if (!tokens.length) {
    return [];
  }
  const scored: Array<[string, Record<string, any>]> = [];
  for (const head of Object.keys(headers)) {
    const ht = head.split(" ");
    let n = 0;
    while (n < ht.length && n < tokens.length && ht[n] === tokens[n]) {
      n++;
    }
    const continues = n < tokens.length && n < ht.length && ht[n].startsWith(tokens[n]);
    if (!n && !continues) {
      continue;
    }
    scored.push([`${-n}|${continues ? 0 : 1}|${ht.length}|${head}`, { head, shared_tokens: n, prefix_continuation: continues }]);
  }
  scored.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return scored.map(([, payload]) => payload);
}

export function complete_vendor_command(cmd: string, k = 3, version = "", device_build = ""): string[] {
  const ranked = rank_vendor_command_completions(cmd, version, device_build);
  return ranked.slice(0, k).map((candidate) => candidate.head);
}

const _PERMUTATION_MIN_TOKENS = 3;
const _PERMUTATION_EXTRA_TOKENS = 1;
const _PERMUTATION_SHOWN_K = 8;

export function recorded_heads_with_token_permutation(
  cmd: string,
  version = "",
  device_build = "",
  opts: { extra_tokens?: number; limit?: number } = {}
): string[] {
  const extraTokens = opts.extra_tokens ?? _PERMUTATION_EXTRA_TOKENS;
  const limit = opts.limit ?? _PERMUTATION_SHOWN_K;
  const headers = _recordedHeaders(load_vendor_stdlib(version, device_build));
  if (headers === null) {
    return [];
  }
  const tokens = _normTokens(cmd);
  if (tokens.length < _PERMUTATION_MIN_TOKENS) {
    return [];
  }
  const query = new Map<string, number>();
  for (const t of tokens) {
    query.set(t, (query.get(t) || 0) + 1);
  }
  const scored: Array<[string, string]> = [];
  for (const head of Object.keys(headers)) {
    const ht = head.split(" ");
    if (JSON.stringify(ht) === JSON.stringify(tokens)) {
      continue;
    }
    const extra = ht.length - tokens.length;
    if (extra < 0 || extra > extraTokens) {
      continue;
    }
    const counts = new Map<string, number>();
    for (const t of ht) {
      counts.set(t, (counts.get(t) || 0) + 1);
    }
    let dominated = false;
    for (const [tok, need] of query) {
      if ((counts.get(tok) || 0) < need) {
        dominated = true;
        break;
      }
    }
    if (dominated) continue;
    scored.push([`${extra}|${ht.length}|${head}`, head]);
  }
  scored.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return scored.slice(0, limit).map(([, head]) => head);
}

const _NEXT_TOKEN_SHOWN_K = 32;

export function recorded_next_tokens_after_shared_prefix(
  cmd: string,
  version = "",
  device_build = "",
  opts: { limit?: number } = {}
): Record<string, any> | null {
  const limit = opts.limit ?? _NEXT_TOKEN_SHOWN_K;
  const headers = _recordedHeaders(load_vendor_stdlib(version, device_build));
  if (headers === null) {
    return null;
  }
  const tokens = _normTokens(cmd);
  if (!tokens.length) {
    return null;
  }
  let maxN = 0;
  let nexts = new Set<string>();
  for (const head of Object.keys(headers)) {
    const ht = head.split(" ");
    let n = 0;
    while (n < ht.length && n < tokens.length && ht[n] === tokens[n]) {
      n++;
    }
    if (n > maxN) {
      maxN = n;
      nexts = new Set();
    }
    if (n === maxN && n > 0 && ht.length > n) {
      nexts.add(ht[n]);
    }
  }
  if (maxN === 0 || nexts.size === 0) {
    return null;
  }
  const ordered = [...nexts].sort();
  return {
    prefix: tokens.slice(0, maxN).join(" "),
    shared_tokens: maxN,
    position: maxN + 1,
    tokens: ordered.slice(0, Math.max(1, limit)),
    total: ordered.length,
  };
}

const _T2_ANSWER_RE = /^(?:yes|no|y|n)$/i;
const _T2_PROMPT_RE = /^prompt\s*=\s*\S+$/i;
const _T3_EXECUTE_PREFIX_RE = /^execute\s*[:：]{1,2}/i;

export function classify_non_command(line: string): string | null {
  const s = String(line || "").trim();
  if (!s) {
    return null;
  }
  if (_T2_ANSWER_RE.test(s) || _T2_PROMPT_RE.test(s)) {
    return "confirmation_answer";
  }
  if (s.charCodeAt(0) > 127) {
    return "chinese_action_description";
  }
  if (_T3_EXECUTE_PREFIX_RE.test(s)) {
    return "chinese_action_description";
  }
  return null;
}
