// 生成：tools/extract_engine.py ← InfoTest main/sync/command_tree_sync.py。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import { atomic_write_bytes_nofollow, open_directory_nofollow, read_regular_nofollow } from "../case_compiler/_sealed_io";
import { accepts_schema } from "../common/schema_identity";

const _ROOT = _cex_data_path("");
export const COMMAND_TREE_STORE_ROOT = path.join(_ROOT, "runtime", "command_tree");
export const ACTIVE_SCHEMA = "ist.command-tree.active";
export const MANIFEST_SCHEMA = "ist.command-tree.generation";
export const PROJECTION_POLICY_SCHEMA = "ist.vendor-stdlib.projection-policy";
const _PROJECTION_POLICY_RULES: Record<string, string> = {
  declaration_claim_fields: "forbidden-v1",
  field_contract: "closed-v2",
  source_xml_identity: "sha256-bound-v1",
  sensitive_parameter_marker: "redacted-unexecutable-v3",
  xml_default_literals: "absent-from-xml-derived-surfaces-v2",
  argument_value_domain: "multi-source-claims-v14",
};
const _XML_DERIVED_DOMAIN_SOURCES = new Set(["xml_limit", "xml_help"]);
export const DEFAULT_INDEX_MAX_BYTES = 2 * 1024 * 1024;
export const DEFAULT_XML_MAX_BYTES = 16 * 1024 * 1024;
export const DEFAULT_PROJECTION_MAX_BYTES = 16 * 1024 * 1024;
export const DEFAULT_MANIFEST_MAX_BYTES = 2 * 1024 * 1024;
const DEFAULT_MAX_PAGES = 16;
const DEFAULT_MAX_LINKS = 4096;
const _PRODUCT_RE = /^[A-Za-z0-9_-]+$/;
const _PLATFORM_RE = /^[A-Za-z0-9_-]+$/;
const _VERSION_RE = /^[0-9]+(?:\.[0-9]+)*$/;
const _BUILD_RE = /^[0-9]+(?:\.[0-9]+)*$/;
const _GENERATION_RE = /^g-[0-9a-f]{24}-[0-9a-f]{24}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;

export class CommandTreeSyncError extends Error {}
export class CommandTreeProjectionPolicyStale extends CommandTreeSyncError {}

export interface BuildIdentity {
  product: string;
  platform: string;
  release: string;
  build: string;
  full_version: string;
  inventory_version: string;
  filename_tokens: string[];
}

export interface CommandTreeSyncResult {
  product: string;
  platform: string;
  version: string;
  device_build: string;
  full_version: string;
  generation_id: string;
  generation_root: string;
  xml_path: string;
  projection_path: string;
  manifest_path: string;
  manifest_sha256: string;
  source_url: string;
  source_sha256: string;
  source_size: number;
  projection_sha256: string;
  results_total: number;
  results_nonempty: number;
  item_count: number;
  published: boolean;
}

export function inventory_version_from_build(full_version: string): string {
  const identity = parse_build_identity(full_version);
  return identity.inventory_version;
}

export function parse_build_identity(full_version: string): BuildIdentity {
  const text = String(full_version ?? "").trim();
  const match = /^([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)\s+([0-9]+(?:\.[0-9]+)*)\s+build\s+([0-9]+(?:\.[0-9]+)*)$/i.exec(text);
  if (!match) {
    throw new CommandTreeSyncError("设备完整版本格式无效");
  }
  const [, product, platform, release, build] = match;
  const releaseParts = release.split(".");
  if (releaseParts.length < 2 || releaseParts.length > 3) {
    throw new CommandTreeSyncError("设备 release 版本段数无效");
  }
  const inventory_version = releaseParts.slice(0, 2).join(".");
  const filename_tokens = [product.toLowerCase(), platform.toLowerCase(), ...release.split("."), build];
  return { product, platform, release, build, full_version: text, inventory_version, filename_tokens };
}

export function parse_build_identity_from_text(text: string): BuildIdentity | null {
  const trimmed = String(text ?? "").trim();
  if (!trimmed) {
    return null;
  }
  try {
    return parse_build_identity(trimmed);
  } catch (exc) {
    if (exc instanceof CommandTreeSyncError) {
      return null;
    }
    throw exc;
  }
}

function _sha(data: Buffer | string): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function _canonical_json(payload: Record<string, any>): Buffer {
  return Buffer.from(JSON.stringify(payload, null, 2), "utf8");
}

export function projection_policy_identity(): Record<string, any> {
  return { schema: PROJECTION_POLICY_SCHEMA, rules: _PROJECTION_POLICY_RULES };
}

export function resolve_family_key(product: string, platform: string): string {
  const productStr = String(product ?? "").trim();
  const platformStr = String(platform ?? "").trim();
  if (!_PRODUCT_RE.test(productStr) || !_PLATFORM_RE.test(platformStr)) {
    throw new CommandTreeSyncError("命令树 product/platform 身份无效");
  }
  return `${productStr}/${platformStr}`;
}

type HttpFetcher = (url: string, max_bytes: number) => Buffer;
type ProjectionBuilder = (args: { version: string; device_build: string; xml_path: string; output_dir: string; manual_version: string }) => unknown;

function _has_forbidden_url_char(raw: string): boolean {
  return /[\s\x00-\x1f\x7f<>"'`\\^|]/.test(raw);
}

function _authority(parsed: URL): string {
  let host = parsed.hostname.toLowerCase();
  try {
    host = Buffer.from(host, "utf8").toString("ascii");
  } catch {
    throw new CommandTreeSyncError("构建站 URL host 必须是 ASCII");
  }
  if (host.length > 253) {
    throw new CommandTreeSyncError("构建站 URL host 长度超限");
  }
  const port = parsed.port;
  const defaultPort = parsed.protocol === "https:" ? 443 : 80;
  const renderedHost = host.includes(":") ? `[${host}]` : host;
  if (!port || parseInt(port, 10) === defaultPort) {
    return renderedHost;
  }
  return `${renderedHost}:${port}`;
}

function _validate_base_url(index_url: string, allowed_authorities: Iterable<string>, allow_insecure_http: boolean): [string, string, string] {
  const original = String(index_url ?? "");
  const raw = original.trim();
  if (raw.length > 2048 || raw !== original || _has_forbidden_url_char(raw)) {
    throw new CommandTreeSyncError("构建站索引 URL 含空白或控制字符");
  }
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new CommandTreeSyncError("构建站索引 URL 无效");
  }
  const scheme = parsed.protocol.replace(":", "").toLowerCase();
  if (!["https", "http"].includes(scheme)) {
    throw new CommandTreeSyncError("构建站索引只允许 http/https");
  }
  if (scheme === "http" && !allow_insecure_http) {
    throw new CommandTreeSyncError("构建站 HTTP 需要显式受控内网风险开关");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new CommandTreeSyncError("构建站索引 URL 不允许凭据、query 或 fragment");
  }
  if (parsed.pathname.includes("%")) {
    throw new CommandTreeSyncError("构建站索引 URL 不允许百分号编码");
  }
  const authority = _authority(parsed);
  const allowed = new Set([...allowed_authorities].map((a) => String(a ?? "").trim().toLowerCase()).filter(Boolean));
  if (!allowed.size) {
    throw new CommandTreeSyncError("构建站允许 authority 列表为空");
  }
  if (!allowed.has(authority)) {
    throw new CommandTreeSyncError("构建站索引 authority 未在允许列表");
  }
  const pathPrefix = parsed.pathname.endsWith("/") ? parsed.pathname : parsed.pathname + "/";
  return [raw, authority, pathPrefix];
}

function _validated_link(page_url: string, href: string, authority: string, path_prefix: string): string | null {
  const raw = String(href ?? "").trim();
  if (!raw || _has_forbidden_url_char(raw)) {
    return null;
  }
  let resolved: URL;
  try {
    resolved = new URL(raw, page_url);
  } catch {
    return null;
  }
  if (resolved.username || resolved.password || resolved.search || resolved.hash) {
    return null;
  }
  if (_authority(resolved) !== authority) {
    return null;
  }
  if (!resolved.pathname.startsWith(path_prefix)) {
    return null;
  }
  return resolved.toString();
}

function _normalize_allowed_ip_networks(values: Iterable<string>): Set<string> {
  const networks = new Set<string>();
  for (const value of values) {
    const raw = String(value ?? "").trim();
    if (!raw) {
      continue;
    }
    networks.add(raw);
  }
  if (!networks.size) {
    throw new CommandTreeSyncError("构建站允许 IP 网段为空");
  }
  return networks;
}

function _resolve_allowed_addresses(host: string, _port: number, _allowed_networks: Set<string>): Array<{ address: string; family: number }> {
  return [{ address: host, family: 0 }];
}

function _open_direct_socket(candidates: Array<{ address: string; family: number }>, timeout: number): import("net").Socket {
  const net = require("node:net");
  const { address, family } = candidates[0];
  const socket = net.createConnection({ host: address, port: 443, family, timeout: timeout * 1000 });
  return socket;
}

function _default_fetch(url: string, max_bytes: number, allowed_networks: Set<string>): Buffer {
  const parsed = new URL(url);
  const scheme = parsed.protocol.replace(":", "").toLowerCase();
  const host = parsed.hostname;
  const port = parsed.port ? parseInt(parsed.port, 10) : scheme === "https" ? 443 : 80;
  const hostHeader = parsed.host;
  const requestTarget = parsed.pathname + parsed.search;
  let requestTargetAscii: string;
  try {
    requestTargetAscii = Buffer.from(requestTarget, "utf8").toString("ascii");
  } catch {
    throw new CommandTreeSyncError("构建站请求 URL 必须是 ASCII");
  }
  const candidates = _resolve_allowed_addresses(host, port, allowed_networks);
  const socket = _open_direct_socket(candidates, 20.0);
  let connection = socket;
  try {
    if (scheme === "https") {
      const tls = require("node:tls");
      connection = tls.connect({ socket, servername: host });
    }
    const request = Buffer.from(`GET ${requestTargetAscii} HTTP/1.1\r\nHost: ${hostHeader}\r\nUser-Agent: InfoTest-Engine/command-tree-sync\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n`, "utf8");
    connection.write(request);
    return new Promise<Buffer>((resolve, reject) => {
      const chunks: Buffer[] = [];
      let total = 0;
      connection.on("data", (chunk: Buffer) => {
        total += chunk.length;
        if (total > max_bytes) {
          connection.destroy();
          reject(new CommandTreeSyncError("构建站响应实际大小超限"));
          return;
        }
        chunks.push(chunk);
      });
      connection.on("end", () => {
        resolve(Buffer.concat(chunks));
      });
      connection.on("error", (err: Error) => {
        reject(new CommandTreeSyncError(`构建站请求失败(${err.name})`));
      });
    }) as unknown as Buffer;
  } finally {
    connection.destroy();
  }
}

function _target_filename_tokens(filename: string): string[] {
  const name = path.basename(filename);
  if (!name.toLowerCase().startsWith("command_tree-") || !name.toLowerCase().endsWith(".xml")) {
    return [];
  }
  const core = name.slice("command_tree-".length, -".xml".length);
  return core.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

function _page_filename_tokens(url: string): string[] {
  const parsed = new URL(url);
  const filename = path.posix.basename(parsed.pathname);
  const stem = filename.toLowerCase().endsWith(".html") ? filename.slice(0, -5) : filename;
  return stem.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

function _contains_token_sequence(tokens: string[], wanted: string[]): boolean {
  if (!wanted.length || tokens.length < wanted.length) {
    return false;
  }
  for (let i = 0; i <= tokens.length - wanted.length; i++) {
    if (tokens.slice(i, i + wanted.length).join("|") === wanted.join("|")) {
      return true;
    }
  }
  return false;
}

class _HrefParser {
  hrefs: string[] = [];
  oversized_href = false;
  feed(data: string): void {
    const regex = /<a\s+[^>]*href=["']([^"']+)["'][^>]*>/gi;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(data)) !== null) {
      if (match[1].length > 2048) {
        this.oversized_href = true;
      }
      this.hrefs.push(match[1]);
    }
  }
}

function _discover_xml_url(index_url: string, identity: BuildIdentity, fetcher: HttpFetcher, authority: string, path_prefix: string, index_max_bytes: number, max_pages: number, max_links: number): string {
  if (max_pages < 3) {
    throw new CommandTreeSyncError("构建站索引遍历页数预算不足");
  }
  let link_count = 0;

  function links_on(page: string): string[] {
    const raw = fetcher(page, index_max_bytes);
    if (raw.length > index_max_bytes) {
      throw new CommandTreeSyncError("构建站索引页面超限");
    }
    const parser = new _HrefParser();
    try {
      parser.feed(raw.toString("latin1"));
    } catch {
      throw new CommandTreeSyncError("构建站索引 HTML 无法解析");
    }
    if (parser.oversized_href) {
      throw new CommandTreeSyncError("构建站索引 href 长度超限");
    }
    link_count += parser.hrefs.length;
    if (link_count > max_links) {
      throw new CommandTreeSyncError("构建站索引链接数超限");
    }
    const links: string[] = [];
    for (const href of parser.hrefs) {
      const link = _validated_link(page, href, authority, path_prefix);
      if (link !== null) {
        links.push(link);
      }
    }
    return links;
  }
  const release_tokens = identity.release.split(".");
  const product_token = identity.product.toLowerCase();
  const release_pages = new Set(links_on(index_url).filter((link) => {
    const parsed = new URL(link);
    return parsed.pathname.toLowerCase().endsWith(".html") && _page_filename_tokens(link).join("|") === [product_token, ...release_tokens].join("|");
  }));
  if (release_pages.size !== 1) {
    throw new CommandTreeSyncError(`构建站精确 release 页面数量不是 1(count=${release_pages.size})`);
  }
  const release_page = [...release_pages][0];
  const platform_tokens = identity.platform.match(/[A-Za-z0-9]+/g)?.map((t) => t.toLowerCase()) ?? [];
  const platform_pages = new Set(links_on(release_page).filter((link) => {
    const parsed = new URL(link);
    return parsed.pathname.toLowerCase().endsWith(".html") && _page_filename_tokens(link).includes(product_token) && _contains_token_sequence(_page_filename_tokens(link), release_tokens) && _contains_token_sequence(_page_filename_tokens(link), platform_tokens);
  }));
  if (platform_pages.size !== 1) {
    throw new CommandTreeSyncError(`构建站精确 product/platform 页面数量不是 1(count=${platform_pages.size})`);
  }
  const platform_page = [...platform_pages][0];
  const matches = new Set<string>();
  for (const link of links_on(platform_page)) {
    const filename = path.posix.basename(new URL(link).pathname);
    if (_target_filename_tokens(filename).join("|") === identity.filename_tokens.join("|")) {
      matches.add(link);
    }
  }
  if (matches.size !== 1) {
    throw new CommandTreeSyncError(`构建站精确 XML 候选数量不是 1(count=${matches.size})`);
  }
  return [...matches][0];
}

export function preflight_command_tree_xml(raw: Buffer, max_bytes: number = DEFAULT_XML_MAX_BYTES, error_type: ErrorConstructor = CommandTreeSyncError as unknown as ErrorConstructor): Record<string, number> {
  if (!raw || raw.length > max_bytes) {
    throw new error_type("vendor XML 大小无效");
  }
  if (raw.includes(0)) {
    throw new error_type("vendor XML 编码不在受控 ASCII 兼容集合");
  }
  const upper = raw.toString("ascii").toUpperCase();
  if (upper.includes("<!DOCTYPE") || upper.includes("<!ENTITY")) {
    throw new error_type("vendor XML 含禁止的实体声明");
  }
  let node_count = 0;
  let depth = 0;
  let item_count = 0;
  let results_total = 0;
  let results_nonempty = 0;
  let root_name = "";
  let scope_seen = false;
  const result_text: boolean[] = [];
  const element_stack: string[] = [];

  function start(name: string, _attrs: Record<string, string>): void {
    depth += 1;
    node_count += 1;
    if (node_count > 250000 || depth > 96) {
      throw new error_type("vendor XML 结构预算超限");
    }
    if (node_count === 1) {
      root_name = name;
    }
    if (name === "scope" && depth === 2) {
      scope_seen = true;
    } else if (name === "item") {
      if (element_stack.length && element_stack[0] === "commands" && ["commands", "scope", "menu"].includes(element_stack[element_stack.length - 1]) && element_stack.slice(1).every((a) => ["scope", "menu"].includes(a))) {
        item_count += 1;
      }
    } else if (name === "results") {
      if (result_text.length) {
        throw new error_type("vendor XML results 不允许嵌套");
      }
      results_total += 1;
      result_text.push(false);
    }
    element_stack.push(name);
  }

  function text_data(value: string): void {
    if (result_text.length && value.trim()) {
      result_text[result_text.length - 1] = true;
    }
  }

  function end(name: string): void {
    if (!element_stack.length || element_stack[element_stack.length - 1] !== name) {
      throw new error_type("vendor XML 元素栈不闭合");
    }
    if (name === "results") {
      if (!result_text.length) {
        throw new error_type("vendor XML results 结构不闭合");
      }
      if (result_text.pop()) {
        results_nonempty += 1;
      }
    }
    element_stack.pop();
    depth -= 1;
  }

  const xmlText = raw.toString("utf8");
  const tagRe = /<\/?([^\s>\/]+)(?:\s[^>]*)?>/g;
  let match: RegExpExecArray | null;
  let lastIndex = 0;
  while ((match = tagRe.exec(xmlText)) !== null) {
    const [full, tagName] = match;
    if (full.startsWith("</")) {
      end(tagName);
    } else if (full.endsWith("/>")) {
      start(tagName, {});
      end(tagName);
    } else {
      start(tagName, {});
    }
    const textBefore = xmlText.slice(lastIndex, match.index).trim();
    if (textBefore) {
      text_data(textBefore);
    }
    lastIndex = match.index + full.length;
  }
  const tail = xmlText.slice(lastIndex).trim();
  if (tail) {
    text_data(tail);
  }

  if (depth !== 0 || result_text.length || element_stack.length) {
    throw new error_type("vendor XML 结构不闭合");
  }
  if (root_name !== "commands" || !scope_seen) {
    throw new error_type("vendor XML 根结构不符合 commands/scope 契约");
  }
  if (item_count < 1) {
    throw new error_type("vendor XML 没有命令 item");
  }
  return { item_count, results_total, results_nonempty };
}

function _validate_xml(raw: Buffer, max_bytes: number): Record<string, number> {
  const counts = preflight_command_tree_xml(raw, max_bytes, CommandTreeSyncError as unknown as ErrorConstructor);
  return counts;
}

function _partition_root(store_root: string, product: string, platform: string, version: string, build: string): string {
  if (!_PRODUCT_RE.test(product) || !_PLATFORM_RE.test(platform) || !_VERSION_RE.test(version) || !_BUILD_RE.test(build)) {
    throw new CommandTreeSyncError("命令树 product/platform/version/build 身份无效");
  }
  return path.join(store_root, "products", product, "platforms", platform, "builds", `${version}_${build}`);
}

function _read_regular(filePath: string, max_bytes: number): Buffer {
  try {
    return read_regular_nofollow(filePath, {
      errorType: CommandTreeSyncError,
      invalid_message: "命令树代际路径无效",
      directory_message: "命令树代际目录不可安全读取",
      open_message: "命令树代际文件不可读",
      bounds_message: "命令树代际文件大小越界",
      changed_message: "命令树代际文件读取期间发生变化",
      max_bytes,
      min_bytes: 1,
    }) as Buffer;
  } catch (exc) {
    if ((exc as NodeJS.ErrnoException).code === "ENOENT") {
      throw new CommandTreeSyncError("命令树代际文件缺失");
    }
    throw exc;
  }
}

function _artifact_entry(raw: Buffer): Record<string, number | string> {
  return { size: raw.length, sha256: _sha(raw) };
}

function _generation_id(product: string, platform: string, version: string, build: string, full_version: string, source_url: string, xml_sha256: string, projection_sha256: string, xml_counts: Record<string, number>): string {
  const identity = _sha(_canonical_json({ product, platform, version, device_build: build, full_version, source_url, xml_sha256, projection_sha256, xml_counts }));
  return `g-${xml_sha256.slice(0, 24)}-${identity.slice(0, 24)}`;
}

function _xml_sensitive_literal_pattern(literal: string, ignore_case: boolean): RegExp | null {
  const text = String(literal ?? "").toLowerCase();
  if (!text) {
    return null;
  }
  const flags = ignore_case ? "i" : "";
  if (/^[a-z0-9]+$/.test(text)) {
    return new RegExp(`(?<![a-z0-9])${text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![a-z0-9])`, flags);
  }
  return new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), flags);
}

export function xml_sensitive_literal_count(text: string, values: Set<string>): number {
  const folded = String(text ?? "").toLowerCase();
  let count = 0;
  for (const value of values) {
    const pattern = _xml_sensitive_literal_pattern(value, false);
    if (pattern === null) {
      continue;
    }
    if (pattern.test(folded)) {
      count += 1;
    }
  }
  return count;
}

export function xml_sensitive_literal_replace(text: string, values: Set<string>): string {
  let out = String(text ?? "");
  for (const value of values) {
    const pattern = _xml_sensitive_literal_pattern(value, true);
    if (pattern === null) {
      continue;
    }
    out = out.replace(pattern, "[redacted]");
  }
  return out;
}

function _xml_default_literal_closure(xml_raw: Buffer): Set<string> {
  const { is_credential_argument, is_placeholder_default_literal } = require("../case_compiler/credential_literals") as any;
  const xmlText = xml_raw.toString("utf8");
  const defaults = new Set<string>();
  const argRe = /<arg\s+[^>]*>/g;
  let match: RegExpExecArray | null;
  while ((match = argRe.exec(xmlText)) !== null) {
    const tag = match[0];
    const nameMatch = /name="([^"]*)"/.exec(tag);
    const typeMatch = /type="([^"]*)"/.exec(tag);
    const helpMatch = /help_string="([^"]*)"/.exec(tag);
    const defaultMatch = /default_value="([^"]*)"/.exec(tag);
    if (defaultMatch) {
      const literal = defaultMatch[1].trim();
      if (literal && !is_placeholder_default_literal(literal)) {
        if (is_credential_argument(nameMatch?.[1], typeMatch?.[1], helpMatch?.[1])) {
          defaults.add(literal);
        }
      }
    }
  }
  return defaults;
}

export function projection_xml_default_literal_count(payload: Record<string, any>, xml_raw: Buffer): number {
  const defaults = _xml_default_literal_closure(xml_raw);
  let hit_count = 0;
  const headers = payload.headers;
  if (typeof headers !== "object" || headers === null) {
    return 0;
  }
  for (const [head, entry] of Object.entries(headers)) {
    hit_count += xml_sensitive_literal_count(String(head), defaults);
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    const entryObj = entry as Record<string, any>;
    const variants = [entryObj.args ?? [], ...(entryObj.arg_variants ?? [])];
    for (const variant of variants) {
      if (!Array.isArray(variant)) {
        continue;
      }
      for (const argument of variant) {
        if (typeof argument !== "object" || argument === null) {
          continue;
        }
        const argObj = argument as Record<string, any>;
        for (const key of ["type", "name", "length", "limit", "help"]) {
          const value = argObj[key];
          if (typeof value === "string") {
            hit_count += xml_sensitive_literal_count(value, defaults);
          }
        }
        const domain = argObj.value_domain;
        if (typeof domain !== "object" || domain === null) {
          continue;
        }
        const domainObj = domain as Record<string, any>;
        for (const claim of domainObj.enum ?? []) {
          if (typeof claim !== "object" || claim === null) {
            continue;
          }
          if (!_XML_DERIVED_DOMAIN_SOURCES.has(String((claim as any).source))) {
            continue;
          }
          for (const member of (claim as any).values ?? []) {
            if (typeof member === "string") {
              hit_count += xml_sensitive_literal_count(member, defaults);
            }
          }
        }
        for (const claim of domainObj.default ?? []) {
          if (typeof claim !== "object" || claim === null) {
            continue;
          }
          if (!_XML_DERIVED_DOMAIN_SOURCES.has(String((claim as any).source))) {
            continue;
          }
          if (typeof (claim as any).value === "string") {
            hit_count += xml_sensitive_literal_count((claim as any).value, defaults);
          }
        }
      }
    }
    for (const result of entryObj.results ?? []) {
      if (typeof result !== "object" || result === null) {
        continue;
      }
      const resultObj = result as Record<string, any>;
      for (const key of ["text", "locator", "operator"]) {
        const value = resultObj[key];
        if (typeof value === "string") {
          hit_count += xml_sensitive_literal_count(value, defaults);
        }
      }
    }
  }
  return hit_count;
}

function _validate_projection(raw: Buffer, version: string, build: string, xml_name: string, xml_sha: string, xml_raw: Buffer, allow_stale_policy: boolean = false): Record<string, any> {
  let payload: any;
  try {
    payload = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new CommandTreeSyncError("vendor 投影不是合法 JSON");
  }
  const source = typeof payload === "object" && payload !== null ? payload.source : null;
  const policy = typeof payload === "object" && payload !== null ? payload.projection_policy : null;
  const current_policy = projection_policy_identity();
  const policy_is_current = JSON.stringify(policy) === JSON.stringify(current_policy);
  const expected_key = /(?:^|_)(?:capability_)?expected(?:_|$)/i;
  const stack: unknown[] = [payload];
  while (stack.length) {
    const current = stack.pop();
    if (typeof current === "object" && current !== null && !Array.isArray(current)) {
      for (const [key, value] of Object.entries(current as Record<string, any>)) {
        const normalized_key = String(key).replace(/(?<!^)(?=[A-Z])/g, "_").replace(/-/g, "_");
        if (expected_key.test(normalized_key)) {
          throw new CommandTreeSyncError("vendor 投影不得携带 CapabilityXml expected");
        }
        stack.push(value);
      }
    } else if (Array.isArray(current)) {
      stack.push(...current);
    }
  }
  const top_keys = new Set(["schema", "version", "device_os_build", "source", "source_dir", "source_glob", "generator", "stats", "headers", "manual_declarations", "projection_policy"]);
  const source_keys = new Set(["kind", "device_os_build", "sha256", "filename"]);
  const entry_keys = new Set(["src", "pmax", "enums", "args", "arg_variants", "origin", "results"]);
  const argument_keys = new Set(["position", "type", "optional", "name", "length", "limit", "help", "executable", "value_domain"]);
  const result_keys = new Set(["text", "locator", "operator"]);
  const value_domain_keys = new Set(["enum", "union", "range", "length", "default"]);
  const value_domain_sources = new Set(["xml_limit", "xml_help", "manual_table", "footprint"]);

  function xml_result_projection(): Record<string, Array<Record<string, string>>> {
    return {};
  }
  const expected_results = xml_result_projection();

  function reject_extra(mapping: unknown, allowed: Set<string>, label: string): void {
    if (typeof mapping !== "object" || mapping === null || Array.isArray(mapping)) {
      throw new CommandTreeSyncError(`vendor 投影 ${label} 字段不在契约闭集`);
    }
    for (const key of Object.keys(mapping as Record<string, any>)) {
      if (!allowed.has(key)) {
        throw new CommandTreeSyncError(`vendor 投影 ${label} 字段不在契约闭集`);
      }
    }
  }

  function reject_invalid_value_domain(domain: unknown, label: string): void {
    reject_extra(domain, value_domain_keys, `${label} value_domain`);
    if (typeof domain !== "object" || domain === null) {
      throw new CommandTreeSyncError("vendor 投影 value_domain 不得为空对象");
    }
    for (const [kind, claims] of Object.entries(domain as Record<string, any>)) {
      if (!Array.isArray(claims) || !claims.length) {
        throw new CommandTreeSyncError("vendor 投影 value_domain 声明不是非空数组");
      }
      for (const claim of claims) {
        if (typeof claim !== "object" || claim === null) {
          throw new CommandTreeSyncError("vendor 投影 value_domain 声明无效");
        }
        const claimObj = claim as Record<string, any>;
        if (!value_domain_sources.has(String(claimObj.source ?? "")) || !String(claimObj.locator ?? "")) {
          throw new CommandTreeSyncError("vendor 投影 value_domain 声明缺少可核出处");
        }
        if (kind === "enum") {
          const values = claimObj.values;
          if (Object.keys(claimObj).length !== 3 || !Array.isArray(values) || values.length < 2 || !values.every((v: any) => typeof v === "string" && v)) {
            throw new CommandTreeSyncError("vendor 投影 enum 声明无效");
          }
        } else if (kind === "union") {
          const separator = claimObj.separator;
          if (Object.keys(claimObj).length !== 3 || typeof separator !== "string" || separator.length !== 1 || /[a-zA-Z0-9]/.test(separator) || /\s/.test(separator)) {
            throw new CommandTreeSyncError("vendor 投影 union 声明无效");
          }
        } else if (kind === "default") {
          if (Object.keys(claimObj).length !== 3 || typeof claimObj.value !== "string" || !claimObj.value) {
            throw new CommandTreeSyncError("vendor 投影 default 声明无效");
          }
        } else {
          const low = claimObj.min;
          const high = claimObj.max;
          if (Object.keys(claimObj).length !== 4 || typeof low !== "number" || typeof high !== "number" || typeof low === "boolean" || typeof high === "boolean" || low > high) {
            throw new CommandTreeSyncError(`vendor 投影 ${kind} 声明无效`);
          }
        }
      }
    }
  }

  function reject_invalid_argument(argument: unknown, label: string): void {
    reject_extra(argument, argument_keys, label);
    if (typeof argument !== "object" || argument === null) {
      return;
    }
    const argObj = argument as Record<string, any>;
    if ("value_domain" in argObj) {
      reject_invalid_value_domain(argObj.value_domain, label);
    }
    if (String(argObj.type ?? "") === "REDACTED_SENSITIVE") {
      if ((Object.keys(argObj).length !== 4 || argObj.executable !== false) && policy_is_current) {
        throw new CommandTreeSyncError("vendor 投影敏感参数标记不是最小不可执行形态");
      }
    } else if ("executable" in argObj && policy_is_current) {
      throw new CommandTreeSyncError("vendor 投影普通参数不得覆写 executable 语义");
    }
  }

  reject_extra(payload, top_keys, "顶层");
  reject_extra(source, source_keys, "source");
  for (const collection_name of ["headers", "manual_declarations"]) {
    const collection = payload[collection_name];
    if (typeof collection !== "object" || collection === null) {
      throw new CommandTreeSyncError(`vendor 投影 ${collection_name} 不是合法对象`);
    }
    for (const [head, entry] of Object.entries(collection as Record<string, any>)) {
      reject_extra(entry, entry_keys, `${collection_name} entry`);
      const entryObj = entry as Record<string, any>;
      if (policy_is_current && collection_name === "headers" && "enums" in entryObj) {
        throw new CommandTreeSyncError("vendor 投影 headers 不得再携带已退役 enums 字段");
      }
      if (collection_name === "manual_declarations" && entryObj.results) {
        throw new CommandTreeSyncError("vendor 投影手册声明不得携带 XML results");
      }
      const projected_results = entryObj.results ?? [];
      if (!Array.isArray(projected_results)) {
        throw new CommandTreeSyncError("vendor 投影 results 不是合法数组");
      }
      for (const result of projected_results) {
        reject_extra(result, result_keys, "result");
        const resultObj = result as Record<string, any>;
        if (typeof resultObj !== "object" || resultObj === null || typeof resultObj.text !== "string" || !resultObj.text || typeof resultObj.locator !== "string" || !resultObj.locator) {
          throw new CommandTreeSyncError("vendor 投影 result 声明不完整");
        }
      }
      if (collection_name === "headers" && JSON.stringify(projected_results) !== JSON.stringify(expected_results[String(head)] ?? [])) {
        throw new CommandTreeSyncError("vendor 投影 results 与同代 XML 不闭合");
      }
      for (const argument of entryObj.args ?? []) {
        reject_invalid_argument(argument, "argument");
      }
      for (const variant of entryObj.arg_variants ?? []) {
        if (!Array.isArray(variant)) {
          throw new CommandTreeSyncError("vendor 投影 argument variant 不是合法数组");
        }
        for (const argument of variant) {
          reject_invalid_argument(argument, "argument variant");
        }
      }
    }
  }
  if (typeof payload !== "object" || payload === null || !accepts_schema(payload.schema, "ist.vendor_stdlib") || String(payload.version ?? "") !== version || String(payload.device_os_build ?? "") !== build || typeof payload.headers !== "object" || !payload.headers || typeof payload.manual_declarations !== "object" || typeof source !== "object" || source === null || source.kind !== "vendor_command_tree_xml" || String(source.device_os_build ?? "") !== build || String(source.filename ?? "") !== xml_name || String(source.sha256 ?? "").toLowerCase() !== xml_sha) {
    throw new CommandTreeSyncError("vendor 投影身份与 XML 不闭合");
  }
  if (policy_is_current) {
    const hit_count = projection_xml_default_literal_count(payload, xml_raw);
    if (hit_count) {
      throw new CommandTreeSyncError(`vendor 投影 XML default 闭包终态扫描失败 (matched_literal_count=${hit_count})`);
    }
  } else if (!allow_stale_policy) {
    throw new CommandTreeProjectionPolicyStale("vendor 投影生成策略已过期，禁止消费并要求同步迁移");
  }
  return payload;
}

function _fsync_directory(dirPath: string): void {
  const dirPathResolved = open_directory_nofollow(dirPath, {
    errorType: CommandTreeSyncError,
    invalid_message: "命令树代际目录无效",
    unavailable_message: "命令树代际目录不可安全持久化",
  });
  const fd = fs.openSync(dirPathResolved, "r");
  try {
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
}

function _partition_publish_lock(partition: string, callback: () => void): void {
  const lockPath = path.join(partition, ".publish.lock");
  let lockFd: number | null = null;
  try {
    try {
      lockFd = fs.openSync(lockPath, "r+");
    } catch {
      try {
        lockFd = fs.openSync(lockPath, "wx");
      } catch {
        lockFd = fs.openSync(lockPath, "r+");
      }
    }
    const info = fs.fstatSync(lockFd);
    if (!info.isFile() || info.nlink !== 1) {
      throw new CommandTreeSyncError("命令树发布锁身份无效");
    }
    fs.fchmodSync(lockFd, 0o600);
    const named = fs.statSync(lockPath);
    if (named.dev !== info.dev || named.ino !== info.ino || !named.isFile() || named.nlink !== 1) {
      throw new CommandTreeSyncError("命令树发布锁路径发生换档");
    }
    callback();
  } finally {
    if (lockFd !== null) {
      fs.closeSync(lockFd);
    }
  }
}

function _cleanup_owned_directory(generations: string, directory_name: string, staging: boolean, expected_identity?: [number, number]): void {
  if ((staging && !directory_name.startsWith(".staging-")) || (!staging && !_GENERATION_RE.test(directory_name)) || path.basename(directory_name) !== directory_name || [".", ".."].includes(directory_name)) {
    throw new CommandTreeSyncError("命令树代际清理身份无效");
  }
  const dirPath = path.join(generations, directory_name);
  try {
    fs.lstatSync(dirPath);
  } catch {
    return;
  }
  const opened = fs.lstatSync(dirPath);
  if (!opened.isDirectory() || (expected_identity && (opened.dev !== expected_identity[0] || opened.ino !== expected_identity[1]))) {
    throw new CommandTreeSyncError("命令树代际清理目录身份无效");
  }
  const names = fs.readdirSync(dirPath);
  for (const name of names) {
    if (!name || [".", ".."].includes(name) || path.basename(name) !== name) {
      throw new CommandTreeSyncError("命令树 staging 含无效目录项");
    }
    const info = fs.statSync(path.join(dirPath, name));
    if (!info.isFile() || info.nlink !== 1) {
      throw new CommandTreeSyncError("命令树 staging 含不可安全清理的目录项");
    }
  }
  for (const name of names) {
    fs.unlinkSync(path.join(dirPath, name));
  }
  fs.rmdirSync(dirPath);
  _fsync_directory(generations);
}

function _cleanup_owned_staging(generations: string, staging_name: string): void {
  _cleanup_owned_directory(generations, staging_name, true);
}

function _cleanup_owned_generation(generations: string, generation_id: string, expected_identity: [number, number]): void {
  _cleanup_owned_directory(generations, generation_id, false, expected_identity);
}

function _result_from_generation(store_root: string, product: string, platform: string, version: string, build: string, generation_id: string, manifest_sha256: string, published: boolean = false, allow_stale_policy: boolean = false): CommandTreeSyncResult {
  if (!_GENERATION_RE.test(generation_id)) {
    throw new CommandTreeSyncError("命令树 generation_id 无效");
  }
  if (!_SHA256_RE.test(String(manifest_sha256 ?? ""))) {
    throw new CommandTreeSyncError("命令树 manifest SHA 身份无效");
  }
  const partition = _partition_root(store_root, product, platform, version, build);
  const generation = path.join(partition, "generations", generation_id);
  const manifest_path = path.join(generation, "manifest.json");
  const manifest_raw = _read_regular(manifest_path, DEFAULT_MANIFEST_MAX_BYTES);
  const actual_manifest_sha = _sha(manifest_raw);
  if (actual_manifest_sha !== manifest_sha256) {
    throw new CommandTreeSyncError("命令树活动指针与 manifest SHA 不一致");
  }
  let manifest: any;
  try {
    manifest = JSON.parse(manifest_raw.toString("utf8"));
  } catch {
    throw new CommandTreeSyncError("命令树 manifest 无效");
  }
  if (typeof manifest !== "object" || manifest === null) {
    throw new CommandTreeSyncError("命令树 manifest 无效");
  }
  const manifest_product = String(manifest.product ?? "");
  const manifest_platform = String(manifest.platform ?? "");
  const manifest_version = String(manifest.version ?? "");
  const manifest_build = String(manifest.device_build ?? "");
  const full_version = String(manifest.full_version ?? "");
  const identity = parse_build_identity(full_version);
  const manifest_keys = new Set(["schema", "generation_id", "product", "platform", "version", "device_build", "full_version", "source_url", "xml_counts", "artifacts"]);
  if (Object.keys(manifest).length !== manifest_keys.size || !accepts_schema(manifest.schema, MANIFEST_SCHEMA) || String(manifest.generation_id ?? "") !== generation_id || manifest_product !== product || manifest_platform !== platform || manifest_version !== version || manifest_build !== build || identity.product !== product || identity.platform !== platform || identity.build !== build || identity.inventory_version !== version) {
    throw new CommandTreeSyncError("命令树 manifest 身份不闭合");
  }
  const artifacts = manifest.artifacts;
  if (typeof artifacts !== "object" || artifacts === null) {
    throw new CommandTreeSyncError("命令树 manifest artifacts 无效");
  }
  const xml_name = `cmdtree_${build}.xml`;
  const projection_name = `vendor_stdlib_${version}_${build}.json`;
  if (Object.keys(artifacts).length !== 2 || !(xml_name in artifacts) || !(projection_name in artifacts)) {
    throw new CommandTreeSyncError("命令树 manifest 资产集合不完整");
  }
  const generationPath = open_directory_nofollow(generation, {
    errorType: CommandTreeSyncError,
    invalid_message: "命令树代际目录无效",
    unavailable_message: "命令树代际目录不可安全读取",
  });
  const generation_entries = fs.readdirSync(generationPath);
  if (generation_entries.length !== 3 || !generation_entries.includes("manifest.json") || !generation_entries.includes(xml_name) || !generation_entries.includes(projection_name)) {
    throw new CommandTreeSyncError("命令树代际目录资产集合不闭合");
  }
  const xml_path = path.join(generation, xml_name);
  const projection_path = path.join(generation, projection_name);
  const xml_raw = _read_regular(xml_path, DEFAULT_XML_MAX_BYTES);
  const projection_raw = _read_regular(projection_path, DEFAULT_PROJECTION_MAX_BYTES);
  for (const [name, raw] of [[xml_name, xml_raw], [projection_name, projection_raw]] as const) {
    const entry = artifacts[name];
    if (typeof entry !== "object" || entry === null || JSON.stringify(entry) !== JSON.stringify(_artifact_entry(raw))) {
      throw new CommandTreeSyncError("命令树 manifest 资产摘要不一致");
    }
  }
  const counts = _validate_xml(xml_raw, DEFAULT_XML_MAX_BYTES);
  _validate_projection(projection_raw, version, build, xml_name, _sha(xml_raw), xml_raw, allow_stale_policy);
  const declared_counts = manifest.xml_counts;
  if (JSON.stringify(declared_counts) !== JSON.stringify(counts)) {
    throw new CommandTreeSyncError("命令树 manifest XML 计数不一致");
  }
  const source_url = _validated_manifest_source_url(String(manifest.source_url ?? ""));
  const parsedSource = new URL(source_url);
  if (parsedSource.protocol !== "local:" && _target_filename_tokens(path.posix.basename(parsedSource.pathname)).join("|") !== identity.filename_tokens.join("|")) {
    throw new CommandTreeSyncError("命令树 manifest source_url 与产品身份不一致");
  }
  const expected_generation_id = _generation_id(product, platform, version, build, full_version, source_url, _sha(xml_raw), _sha(projection_raw), counts);
  if (generation_id !== expected_generation_id) {
    throw new CommandTreeSyncError("命令树 generation_id 与代际内容不一致");
  }
  return {
    product,
    platform,
    version,
    device_build: build,
    full_version,
    generation_id,
    generation_root: generation,
    xml_path,
    projection_path,
    manifest_path,
    manifest_sha256: actual_manifest_sha,
    source_url,
    source_sha256: _sha(xml_raw),
    source_size: xml_raw.length,
    projection_sha256: _sha(projection_raw),
    results_total: counts.results_total,
    results_nonempty: counts.results_nonempty,
    item_count: counts.item_count,
    published,
  };
}

function _validated_manifest_source_url(source_url: string): string {
  const raw = String(source_url ?? "").trim();
  if (!raw) {
    throw new CommandTreeSyncError("命令树 manifest source_url 为空");
  }
  if (_has_forbidden_url_char(raw)) {
    throw new CommandTreeSyncError("命令树 manifest source_url 含非法字符");
  }
  return raw;
}

export function resolve_active_command_tree(product: string, platform: string, version: string, device_build: string, store_root?: string, _allow_stale_policy: boolean = false): CommandTreeSyncResult | null {
  const productStr = String(product ?? "").trim();
  const platformStr = String(platform ?? "").trim();
  const versionStr = String(version ?? "").trim();
  const device_buildStr = String(device_build ?? "").trim();
  const partition = _partition_root(store_root ?? COMMAND_TREE_STORE_ROOT, productStr, platformStr, versionStr, device_buildStr);
  const pointer = path.join(partition, "active.json");
  try {
    fs.lstatSync(pointer);
  } catch {
    return null;
  }
  const pointer_raw = _read_regular(pointer, 64 * 1024);
  let payload: any;
  try {
    payload = JSON.parse(pointer_raw.toString("utf8"));
  } catch {
    throw new CommandTreeSyncError("命令树 active 指针无效");
  }
  const expected_pointer = new Set(["schema", "product", "platform", "version", "device_build", "generation_id", "manifest_sha256"]);
  if (typeof payload !== "object" || payload === null || Object.keys(payload).length !== expected_pointer.size || !accepts_schema(payload.schema, ACTIVE_SCHEMA) || String(payload.product ?? "") !== productStr || String(payload.platform ?? "") !== platformStr || String(payload.version ?? "") !== versionStr || String(payload.device_build ?? "") !== device_buildStr) {
    throw new CommandTreeSyncError("命令树 active 身份无效");
  }
  return _result_from_generation(store_root ?? COMMAND_TREE_STORE_ROOT, productStr, platformStr, versionStr, device_buildStr, String(payload.generation_id ?? ""), String(payload.manifest_sha256 ?? ""), false, _allow_stale_policy);
}

export function resolve_command_tree_generation(product: string, platform: string, version: string, device_build: string, generation_id: string, manifest_sha256: string, store_root?: string): CommandTreeSyncResult {
  return _result_from_generation(store_root ?? COMMAND_TREE_STORE_ROOT, String(product ?? "").trim(), String(platform ?? "").trim(), String(version ?? "").trim(), String(device_build ?? "").trim(), String(generation_id ?? "").trim(), String(manifest_sha256 ?? "").trim().toLowerCase());
}

function _normalize_platform_allowlist(values: Iterable<string>): Set<string> {
  const platforms = new Set<string>();
  for (const value of values) {
    const original = String(value ?? "");
    const raw = original.trim();
    if (raw !== original || !_PLATFORM_RE.test(raw)) {
      throw new CommandTreeSyncError("命令树 platform allowlist 条目无效");
    }
    platforms.add(raw);
  }
  if (!platforms.size) {
    throw new CommandTreeSyncError("命令树 platform allowlist 为空");
  }
  return platforms;
}

function _normalize_http_sha256_pins(values: Record<string, string> | null): Record<string, string> {
  if (values === null) {
    return {};
  }
  if (typeof values !== "object") {
    throw new CommandTreeSyncError("构建站 HTTP SHA256 pin 配置无效");
  }
  const pins: Record<string, string> = {};
  for (const [full_version, digest] of Object.entries(values)) {
    const identity_key = String(full_version ?? "");
    const digest_value = String(digest ?? "");
    const parsed_identity = parse_build_identity(identity_key);
    if (parsed_identity.full_version !== identity_key) {
      throw new CommandTreeSyncError("构建站 HTTP SHA256 pin 配置无效");
    }
    if (!_SHA256_RE.test(digest_value)) {
      throw new CommandTreeSyncError("构建站 HTTP SHA256 pin 配置无效");
    }
    pins[identity_key] = digest_value;
  }
  return pins;
}

function _normalize_trusted_http_authorities(values: Iterable<string>): Set<string> {
  const trusted = new Set<string>();
  for (const value of values) {
    const original = String(value ?? "");
    const raw = original.trim();
    if (raw !== original || !raw || raw.length > 261 || _has_forbidden_url_char(raw) || /[\/\\@?#%]/.test(raw)) {
      throw new CommandTreeSyncError("构建站可信 HTTP authority 配置无效");
    }
    try {
      const parsed = new URL(`http://${raw}/`);
      const canonical = _authority(parsed);
      if (canonical !== raw.toLowerCase()) {
        throw new CommandTreeSyncError("构建站可信 HTTP authority 配置无效");
      }
      trusted.add(canonical);
    } catch {
      throw new CommandTreeSyncError("构建站可信 HTTP authority 配置无效");
    }
  }
  return trusted;
}

function _prepare_staging_generation(staging: string, product: string, platform: string, inventory_version: string, build: string, full_version: string, xml_url: string, xml_raw: Buffer, xml_sha: string, counts: Record<string, number>, projection_builder: ProjectionBuilder): [string, Buffer] {
  const xml_name = `cmdtree_${build}.xml`;
  const projection_name = `vendor_stdlib_${inventory_version}_${build}.json`;
  const xml_path = path.join(staging, xml_name);
  atomic_write_bytes_nofollow(xml_path, xml_raw, {
    errorType: CommandTreeSyncError,
    invalid_message: "vendor XML staging 路径无效",
    unavailable_message: "vendor XML 无法安全写入 staging",
    create_parents: false,
  });
  let generated: unknown;
  try {
    generated = projection_builder({ version: inventory_version, device_build: build, xml_path, output_dir: staging, manual_version: parse_build_identity(full_version).release });
  } catch (exc) {
    throw new CommandTreeSyncError(`vendor 投影生成失败(${(exc as Error).name})`);
  }
  const projection_path = path.join(staging, projection_name);
  if (typeof generated === "object" && generated !== null && (generated as any).path) {
    if (String((generated as any).path) !== projection_path) {
      throw new CommandTreeSyncError("投影生成器返回了代际外路径");
    }
  }
  const projection_raw = _read_regular(projection_path, DEFAULT_PROJECTION_MAX_BYTES);
  const projection_sha = _sha(projection_raw);
  _validate_projection(projection_raw, inventory_version, build, xml_name, xml_sha, xml_raw);
  const generation_id = _generation_id(product, platform, inventory_version, build, full_version, xml_url, xml_sha, projection_sha, counts);
  const manifest_raw = _canonical_json({
    schema: MANIFEST_SCHEMA,
    generation_id,
    product,
    platform,
    version: inventory_version,
    device_build: build,
    full_version,
    source_url: xml_url,
    xml_counts: counts,
    artifacts: {
      [xml_name]: _artifact_entry(xml_raw),
      [projection_name]: _artifact_entry(projection_raw),
    },
  });
  if (manifest_raw.length > DEFAULT_MANIFEST_MAX_BYTES) {
    throw new CommandTreeSyncError("命令树 manifest 大小超限");
  }
  atomic_write_bytes_nofollow(path.join(staging, "manifest.json"), manifest_raw, {
    errorType: CommandTreeSyncError,
    invalid_message: "命令树 manifest staging 路径无效",
    unavailable_message: "命令树 manifest 无法安全写入 staging",
    create_parents: false,
  });
  const stagingPath = open_directory_nofollow(staging, {
    errorType: CommandTreeSyncError,
    invalid_message: "命令树 staging 目录无效",
    unavailable_message: "命令树 staging 目录不可安全读取",
  });
  const staging_entries = fs.readdirSync(stagingPath);
  if (staging_entries.length !== 3 || !staging_entries.includes("manifest.json") || !staging_entries.includes(xml_name) || !staging_entries.includes(projection_name)) {
    throw new CommandTreeSyncError("命令树 staging 资产集合不闭合");
  }
  _fsync_directory(staging);
  return [generation_id, manifest_raw];
}

function _assert_cached_generation_matches_request(cached: CommandTreeSyncResult, identity: BuildIdentity, canonical_index: string, authority: string, path_prefix: string, required_http_pin: string): void {
  if (cached.full_version !== identity.full_version) {
    throw new CommandTreeSyncError("同 version/build 活动代际的完整产品身份冲突");
  }
  const current_source = _validated_link(canonical_index, cached.source_url, authority, path_prefix);
  if (current_source === null || current_source !== cached.source_url) {
    throw new CommandTreeSyncError("活动命令树来源不符合当前构建站策略");
  }
  if (required_http_pin && cached.source_sha256 !== required_http_pin) {
    throw new CommandTreeSyncError("活动 HTTP 命令树与 operator SHA256 pin 不一致");
  }
}

function _migrate_stale_active_generation(root: string, partition: string, identity: BuildIdentity, inventory_version: string, build: string, canonical_index: string, authority: string, path_prefix: string, required_http_pin: string, projection_builder: ProjectionBuilder): CommandTreeSyncResult {
  const generations = path.join(partition, "generations");
  let result: CommandTreeSyncResult | null = null;
  _partition_publish_lock(partition, () => {
    let current: CommandTreeSyncResult | null;
    let stale = false;
    try {
      current = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root);
    } catch (exc) {
      if (exc instanceof CommandTreeProjectionPolicyStale) {
        current = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root, true);
        stale = true;
      } else {
        throw exc;
      }
    }
    if (current === null) {
      throw new CommandTreeSyncError("命令树 stale active 在迁移锁内消失");
    }
    _assert_cached_generation_matches_request(current, identity, canonical_index, authority, path_prefix, required_http_pin);
    if (!stale) {
      result = current;
      return;
    }
    console.warn(`命令树代际生成策略过期，按缓存 XML 重铸: ${identity.product}/${identity.platform}/${inventory_version} build=${build} stale_generation=${current.generation_id}`);
    const xml_raw = _read_regular(current.xml_path, DEFAULT_XML_MAX_BYTES);
    const counts = _validate_xml(xml_raw, DEFAULT_XML_MAX_BYTES);
    const xml_sha = _sha(xml_raw);
    if (xml_sha !== current.source_sha256) {
      throw new CommandTreeSyncError("命令树 stale XML 摘要在迁移前发生变化");
    }
    const staging = path.join(generations, `.staging-${Date.now()}-${crypto.randomBytes(6).toString("hex")}`);
    open_directory_nofollow(staging, {
      errorType: CommandTreeSyncError,
      invalid_message: "命令树迁移 staging 路径无效",
      unavailable_message: "命令树迁移 staging 不可安全创建",
      create_missing: true,
      create_mode: 0o700,
    });
    let generation_id: string;
    let manifest_raw: Buffer;
    try {
      [generation_id, manifest_raw] = _prepare_staging_generation(staging, identity.product, identity.platform, inventory_version, build, identity.full_version, current.source_url, xml_raw, xml_sha, counts, projection_builder);
    } catch (exc) {
      try {
        _cleanup_owned_staging(generations, path.basename(staging));
      } catch (cleanup_exc) {
        if (exc instanceof Error) {
          throw new CommandTreeSyncError("命令树 stale 迁移失败且残件无法安全清理");
        }
      }
      throw exc;
    }
    const manifest_sha = _sha(manifest_raw);
    const final = path.join(generations, generation_id);
    const staging_info = fs.lstatSync(staging);
    const owned_identity: [number, number] = [staging_info.dev, staging_info.ino];
    let renamed_by_us = false;
    try {
      try {
        fs.renameSync(path.basename(staging), path.basename(final));
        renamed_by_us = true;
        _fsync_directory(generations);
      } catch (exc) {
        const err = exc as NodeJS.ErrnoException;
        if (err.code !== "EEXIST" && err.code !== "ENOTEMPTY") {
          throw new CommandTreeSyncError("命令树迁移代际 rename 发布失败");
        }
        const final_info = fs.lstatSync(final);
        if (!final_info.isDirectory() || fs.lstatSync(final).isSymbolicLink()) {
          throw new CommandTreeSyncError("命令树迁移既有目标代际身份无效");
        }
      }
      _cleanup_owned_staging(generations, path.basename(staging));
      const verified = _result_from_generation(root, identity.product, identity.platform, inventory_version, build, generation_id, manifest_sha);
      const pointer_raw = _canonical_json({
        schema: ACTIVE_SCHEMA,
        product: identity.product,
        platform: identity.platform,
        version: inventory_version,
        device_build: build,
        generation_id,
        manifest_sha256: verified.manifest_sha256,
      });
      atomic_write_bytes_nofollow(path.join(partition, "active.json"), pointer_raw, {
        errorType: CommandTreeSyncError,
        invalid_message: "命令树 active 指针路径无效",
        unavailable_message: "命令树迁移 active 指针无法原子发布",
        create_parents: false,
      });
      result = { ...verified, published: true };
    } catch (exc) {
      try {
        _cleanup_owned_staging(generations, path.basename(staging));
        if (renamed_by_us) {
          let active_after_error: CommandTreeSyncResult | null;
          try {
            active_after_error = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root);
          } catch {
            active_after_error = null;
          }
          if (active_after_error === null || active_after_error.generation_id !== generation_id || active_after_error.manifest_sha256 !== manifest_sha) {
            _cleanup_owned_generation(generations, generation_id, owned_identity);
          }
        }
      } catch (cleanup_exc) {
        if (exc instanceof Error) {
          throw new CommandTreeSyncError("命令树 stale 迁移发布失败且残件无法安全清理");
        }
      }
      throw exc;
    }
  });
  if (result === null) {
    throw new CommandTreeSyncError("命令树迁移逻辑异常");
  }
  return result;
}

function _publish_generation(root: string, identity: BuildIdentity, xml_url: string, xml_raw: Buffer, counts: Record<string, number>, projection_builder: ProjectionBuilder, replace_active_generation_id: string = ""): CommandTreeSyncResult {
  const inventory_version = identity.inventory_version;
  const build = identity.build;
  const partition = _partition_root(root, identity.product, identity.platform, inventory_version, build);
  const generations = path.join(partition, "generations");
  const directories = [root, path.join(root, "products"), path.join(root, "products", identity.product), path.join(root, "products", identity.product, "platforms"), path.join(root, "products", identity.product, "platforms", identity.platform), path.join(root, "products", identity.product, "platforms", identity.platform, "builds"), partition, generations];
  for (const directory of directories) {
    open_directory_nofollow(directory, {
      errorType: CommandTreeSyncError,
      invalid_message: "命令树代际仓路径无效",
      unavailable_message: "命令树代际仓不可安全创建",
      create_missing: true,
      create_mode: 0o700,
    });
  }
  const xml_sha = _sha(xml_raw);
  const staging = path.join(generations, `.staging-${Date.now()}-${crypto.randomBytes(6).toString("hex")}`);
  open_directory_nofollow(staging, {
    errorType: CommandTreeSyncError,
    invalid_message: "命令树 staging 路径无效",
    unavailable_message: "命令树 staging 不可安全创建",
    create_missing: true,
    create_mode: 0o700,
  });
  let manifest_sha = "";
  let generation_id = "";
  let renamed_by_us = false;
  let owned_identity: [number, number] | null = null;
  try {
    let manifest_raw: Buffer;
    try {
      [generation_id, manifest_raw] = _prepare_staging_generation(staging, identity.product, identity.platform, inventory_version, build, identity.full_version, xml_url, xml_raw, xml_sha, counts, projection_builder);
    } catch (exc) {
      try {
        _cleanup_owned_staging(generations, path.basename(staging));
      } catch (cleanup_exc) {
        if (exc instanceof Error) {
          throw new CommandTreeSyncError("命令树 staging 生成失败且残件无法安全清理");
        }
      }
      throw exc;
    }
    manifest_sha = _sha(manifest_raw);
    const final = path.join(generations, generation_id);
    const staging_stat = fs.lstatSync(staging);
    owned_identity = [staging_stat.dev, staging_stat.ino];
    let result: CommandTreeSyncResult | null = null;
    _partition_publish_lock(partition, () => {
      const current = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root, !!replace_active_generation_id);
      const _partition_text = `${identity.product}/${identity.platform}/${inventory_version} build=${build}`;
      let _new_projection_sha = "";
      try {
        _new_projection_sha = String(JSON.parse(manifest_raw.toString("utf8")).artifacts[`vendor_stdlib_${inventory_version}_${build}.json`].sha256);
      } catch {
        // ignore
      }
      if (current !== null) {
        if (current.generation_id === generation_id && current.manifest_sha256 === manifest_sha) {
          console.info(`命令树代际复用: ${_partition_text} generation=${generation_id}（重生内容与活动代际同一）`);
          _cleanup_owned_staging(generations, path.basename(staging));
          result = current;
          return;
        }
        if (current.generation_id !== replace_active_generation_id) {
          throw new CommandTreeSyncError("命令树活动代际发生并发身份冲突");
        }
        console.warn(`命令树代际换代: ${_partition_text} ${current.generation_id} → ${generation_id}（源 XML 同一=${current.source_sha256 === xml_sha}；投影 sha ${current.projection_sha256.slice(0, 12)} → ${_new_projection_sha.slice(0, 12)}）`);
      } else {
        console.info(`命令树代际首发: ${_partition_text} generation=${generation_id}`);
      }
      try {
        fs.renameSync(path.basename(staging), path.basename(final));
        renamed_by_us = true;
        _fsync_directory(generations);
      } catch (exc) {
        const err = exc as NodeJS.ErrnoException;
        if (err.code !== "EEXIST" && err.code !== "ENOTEMPTY") {
          throw new CommandTreeSyncError("命令树代际 rename 发布失败");
        }
        const final_stat = fs.lstatSync(final);
        if (!final_stat.isDirectory() || fs.lstatSync(final).isSymbolicLink()) {
          throw new CommandTreeSyncError("命令树既有目标代际身份无效");
        }
      }
      _cleanup_owned_staging(generations, path.basename(staging));
      const verified = _result_from_generation(root, identity.product, identity.platform, inventory_version, build, generation_id, manifest_sha);
      const pointer_raw = _canonical_json({
        schema: ACTIVE_SCHEMA,
        product: identity.product,
        platform: identity.platform,
        version: inventory_version,
        device_build: build,
        generation_id,
        manifest_sha256: verified.manifest_sha256,
      });
      atomic_write_bytes_nofollow(path.join(partition, "active.json"), pointer_raw, {
        errorType: CommandTreeSyncError,
        invalid_message: "命令树 active 指针路径无效",
        unavailable_message: "命令树 active 指针无法原子发布",
        create_parents: false,
      });
      result = { ...verified, published: true };
    });
    if (result === null) {
      throw new CommandTreeSyncError("命令树发布逻辑异常");
    }
    return result;
  } catch (exc) {
    try {
      _cleanup_owned_staging(generations, path.basename(staging));
      if (renamed_by_us && owned_identity !== null) {
        const active_after_error = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root);
        if (active_after_error === null || active_after_error.generation_id !== generation_id || active_after_error.manifest_sha256 !== manifest_sha) {
          _cleanup_owned_generation(generations, generation_id, owned_identity);
        }
      }
    } catch (cleanup_exc) {
      if (exc instanceof Error) {
        throw new CommandTreeSyncError("命令树发布失败且残件无法安全清理");
      }
    }
    throw exc;
  }
}

export function publish_local_command_tree(xml_path: string, expected_sha256: string, full_version: string, version: string, projection_builder: ProjectionBuilder, store_root?: string): CommandTreeSyncResult {
  const identity = parse_build_identity(full_version);
  const requested_version = String(version ?? "").trim();
  const requested_parts = requested_version.split(".");
  const release_parts = identity.release.split(".");
  if (!_VERSION_RE.test(requested_version) || ![2, 3].includes(requested_parts.length) || requested_parts.join(".") !== release_parts.slice(0, requested_parts.length).join(".")) {
    throw new CommandTreeSyncError("设备完整版本与请求 product version 不一致");
  }
  if (!_SHA256_RE.test(String(expected_sha256 ?? ""))) {
    throw new CommandTreeSyncError("本地命令树预期 SHA256 无效");
  }
  const raw = _read_regular(String(xml_path), DEFAULT_XML_MAX_BYTES);
  const actual_sha = _sha(raw);
  if (actual_sha !== expected_sha256) {
    throw new CommandTreeSyncError("本地命令树 XML SHA256 不一致");
  }
  const counts = _validate_xml(raw, DEFAULT_XML_MAX_BYTES);
  const source_url = `local://workspace-input/${actual_sha}.xml`;
  return _publish_generation(store_root ?? COMMAND_TREE_STORE_ROOT, identity, source_url, raw, counts, projection_builder);
}

export function rebuild_active_command_tree_projection(full_version: string, product_version: string, store_root?: string): CommandTreeSyncResult {
  const { generate_vendor_stdlib_projection } = require("../scripts/maintenance/build_vendor_stdlib") as any;
  const identity = parse_build_identity(full_version);
  const requested = String(product_version ?? "").trim();
  const parts = requested.split(".");
  if (!_VERSION_RE.test(requested) || ![2, 3].includes(parts.length) || parts.join(".") !== identity.release.split(".").slice(0, parts.length).join(".")) {
    throw new CommandTreeSyncError("设备完整版本与请求 product version 不一致");
  }
  const root = store_root ?? COMMAND_TREE_STORE_ROOT;
  const current = resolve_active_command_tree(identity.product, identity.platform, identity.inventory_version, identity.build, root, true);
  if (current === null) {
    throw new CommandTreeSyncError("真机 build 没有可重生的活动命令树代际");
  }
  const xml_raw = _read_regular(current.xml_path, DEFAULT_XML_MAX_BYTES);
  if (_sha(xml_raw) !== current.source_sha256) {
    throw new CommandTreeSyncError("命令树 XML 在投影重生前发生身份漂移");
  }
  return _publish_generation(root, identity, current.source_url, xml_raw, _validate_xml(xml_raw, DEFAULT_XML_MAX_BYTES), generate_vendor_stdlib_projection, current.generation_id);
}

export function sync_command_tree(index_url: string, allowed_authorities: Iterable<string>, allowed_platforms: Iterable<string>, allowed_ip_networks: Iterable<string>, trusted_http_authorities: Iterable<string>, insecure_http_sha256_pins: Record<string, string> | null, expected_product: string, full_version: string, version: string, device_build: string, projection_builder: ProjectionBuilder, fetcher?: HttpFetcher, store_root?: string, allow_insecure_http: boolean = false, index_max_bytes: number = DEFAULT_INDEX_MAX_BYTES, xml_max_bytes: number = DEFAULT_XML_MAX_BYTES, max_pages: number = DEFAULT_MAX_PAGES, max_links: number = DEFAULT_MAX_LINKS): CommandTreeSyncResult {
  const identity = parse_build_identity(full_version);
  const expected = String(expected_product ?? "");
  if (expected !== "APV" || identity.product !== expected) {
    throw new CommandTreeSyncError("命令树同步只接受 expected product=APV");
  }
  const platforms = _normalize_platform_allowlist(allowed_platforms);
  if (!platforms.has(identity.platform)) {
    throw new CommandTreeSyncError("设备 platform 未在同步 allowlist");
  }
  const allowed_networks = _normalize_allowed_ip_networks(allowed_ip_networks);
  const trusted_http = _normalize_trusted_http_authorities(trusted_http_authorities);
  const http_pins = _normalize_http_sha256_pins(insecure_http_sha256_pins);
  const ver = String(version ?? "").trim();
  const build = String(device_build ?? "").trim();
  if (identity.build !== build) {
    throw new CommandTreeSyncError("设备完整版本与请求 build 不一致");
  }
  const requested_parts = ver.split(".");
  const release_parts = identity.release.split(".");
  if (!_VERSION_RE.test(ver) || ![2, 3].includes(requested_parts.length) || requested_parts.join(".") !== release_parts.slice(0, requested_parts.length).join(".")) {
    throw new CommandTreeSyncError("设备完整版本与请求 product version 不一致");
  }
  const inventory_version = identity.inventory_version;
  const root = store_root ?? COMMAND_TREE_STORE_ROOT;
  const partition = _partition_root(root, identity.product, identity.platform, inventory_version, build);
  const [canonical_index, authority, path_prefix] = _validate_base_url(index_url, allowed_authorities, allow_insecure_http);
  const source_scheme = new URL(canonical_index).protocol.replace(":", "").toLowerCase();
  let required_http_pin = "";
  if (source_scheme === "http") {
    required_http_pin = http_pins[identity.full_version] ?? "";
    if (!trusted_http.has(authority) && !required_http_pin) {
      throw new CommandTreeSyncError("构建站 HTTP authority 未受信任且缺少完整版本身份绑定的 operator SHA256 pin");
    }
  }
  try {
    const active = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root);
    if (active !== null) {
      _assert_cached_generation_matches_request(active, identity, canonical_index, authority, path_prefix, required_http_pin);
      return active;
    }
  } catch (exc) {
    if (exc instanceof CommandTreeProjectionPolicyStale) {
      return _migrate_stale_active_generation(root, partition, identity, inventory_version, build, canonical_index, authority, path_prefix, required_http_pin, projection_builder);
    }
    throw exc;
  }
  const fetch = fetcher ?? ((url: string, max_bytes: number) => _default_fetch(url, max_bytes, allowed_networks));
  const xml_url = _discover_xml_url(canonical_index, identity, fetch, authority, path_prefix, index_max_bytes, max_pages, max_links);
  const xml_raw = fetch(xml_url, xml_max_bytes);
  const xml_sha = _sha(xml_raw);
  if (required_http_pin && xml_sha !== required_http_pin) {
    throw new CommandTreeSyncError("下载 HTTP 命令树与 operator SHA256 pin 不一致");
  }
  const counts = _validate_xml(xml_raw, xml_max_bytes);
  const generations = path.join(partition, "generations");
  const directories = [root, path.join(root, "products"), path.join(root, "products", identity.product), path.join(root, "products", identity.product, "platforms"), path.join(root, "products", identity.product, "platforms", identity.platform), path.join(root, "products", identity.product, "platforms", identity.platform, "builds"), partition, generations];
  for (const directory of directories) {
    open_directory_nofollow(directory, {
      errorType: CommandTreeSyncError,
      invalid_message: "命令树代际仓路径无效",
      unavailable_message: "命令树代际仓不可安全创建",
      create_missing: true,
      create_mode: 0o700,
    });
  }
  const staging = path.join(generations, `.staging-${Date.now()}-${crypto.randomBytes(6).toString("hex")}`);
  open_directory_nofollow(staging, {
    errorType: CommandTreeSyncError,
    invalid_message: "命令树 staging 路径无效",
    unavailable_message: "命令树 staging 不可安全创建",
    create_missing: true,
    create_mode: 0o700,
  });
  let generation_id: string;
  let manifest_raw: Buffer;
  try {
    [generation_id, manifest_raw] = _prepare_staging_generation(staging, identity.product, identity.platform, inventory_version, build, identity.full_version, xml_url, xml_raw, xml_sha, counts, projection_builder);
  } catch (exc) {
    try {
      _cleanup_owned_staging(generations, path.basename(staging));
    } catch (cleanup_exc) {
      if (exc instanceof Error) {
        throw new CommandTreeSyncError("命令树 staging 生成失败且残件无法安全清理");
      }
    }
    throw exc;
  }
  const final = path.join(generations, generation_id);
  const manifest_sha = _sha(manifest_raw);
  const staging_stat = fs.lstatSync(staging);
  const owned_identity: [number, number] = [staging_stat.dev, staging_stat.ino];
  let renamed_by_us = false;
  try {
    let result: CommandTreeSyncResult | null = null;
    _partition_publish_lock(partition, () => {
      const current = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root);
      if (current !== null) {
        if (current.generation_id === generation_id && current.manifest_sha256 === manifest_sha) {
          _cleanup_owned_staging(generations, path.basename(staging));
          result = current;
          return;
        }
        throw new CommandTreeSyncError("命令树活动代际发生并发身份冲突");
      }
      try {
        fs.renameSync(path.basename(staging), path.basename(final));
        renamed_by_us = true;
        _fsync_directory(generations);
      } catch (exc) {
        const err = exc as NodeJS.ErrnoException;
        if (err.code !== "EEXIST" && err.code !== "ENOTEMPTY") {
          throw new CommandTreeSyncError("命令树代际 rename 发布失败");
        }
        try {
          const final_stat = fs.lstatSync(final);
          if (!final_stat.isDirectory() || fs.lstatSync(final).isSymbolicLink()) {
            throw new CommandTreeSyncError("命令树既有目标代际身份无效");
          }
        } catch {
          throw new CommandTreeSyncError("命令树既有目标代际不可核验");
        }
      }
      _cleanup_owned_staging(generations, path.basename(staging));
      const verified = _result_from_generation(root, identity.product, identity.platform, inventory_version, build, generation_id, manifest_sha);
      const pointer_raw = _canonical_json({
        schema: ACTIVE_SCHEMA,
        product: identity.product,
        platform: identity.platform,
        version: inventory_version,
        device_build: build,
        generation_id,
        manifest_sha256: verified.manifest_sha256,
      });
      atomic_write_bytes_nofollow(path.join(partition, "active.json"), pointer_raw, {
        errorType: CommandTreeSyncError,
        invalid_message: "命令树 active 指针路径无效",
        unavailable_message: "命令树 active 指针无法原子发布",
        create_parents: false,
      });
      result = { ...verified, published: true };
    });
    if (result === null) {
      throw new CommandTreeSyncError("命令树发布逻辑异常");
    }
    return result;
  } catch (exc) {
    try {
      _cleanup_owned_staging(generations, path.basename(staging));
      if (renamed_by_us) {
        let active_after_error: CommandTreeSyncResult | null;
        try {
          active_after_error = resolve_active_command_tree(identity.product, identity.platform, inventory_version, build, root);
        } catch {
          active_after_error = null;
        }
        if (active_after_error === null || active_after_error.generation_id !== generation_id || active_after_error.manifest_sha256 !== manifest_sha) {
          _cleanup_owned_generation(generations, generation_id, owned_identity);
        }
      }
    } catch (cleanup_exc) {
      if (exc instanceof Error) {
        throw new CommandTreeSyncError("命令树发布失败且残件无法安全清理");
      }
    }
    throw exc;
  }
}

export function sync_vendor_command_tree_from_config(full_version: string, product_version: string): CommandTreeSyncResult {
  const { generate_vendor_stdlib_projection } = require("../scripts/maintenance/build_vendor_stdlib") as any;
  const identity = parse_build_identity(full_version);
  const index_url = process.env.IST_APV_BUILD_INDEX_URL ?? "";
  if (!index_url) {
    throw new CommandTreeSyncError("缺少部署配置 IST_APV_BUILD_INDEX_URL，无法同步目标 build 命令树");
  }
  const allowed = (process.env.IST_APV_BUILD_ALLOWED_AUTHORITIES ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowed.length) {
    throw new CommandTreeSyncError("缺少部署配置 IST_APV_BUILD_ALLOWED_AUTHORITIES，无法校验构建站来源");
  }
  const trusted_http = (process.env.IST_APV_BUILD_TRUSTED_HTTP_AUTHORITIES ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const allowed_platforms = (process.env.IST_APV_BUILD_ALLOWED_PLATFORMS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowed_platforms.length) {
    throw new CommandTreeSyncError("缺少部署配置 IST_APV_BUILD_ALLOWED_PLATFORMS，无法校验设备平台");
  }
  const allowed_networks = (process.env.IST_APV_BUILD_ALLOWED_IP_NETWORKS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowed_networks.length) {
    throw new CommandTreeSyncError("缺少部署配置 IST_APV_BUILD_ALLOWED_IP_NETWORKS，无法校验构建站地址");
  }
  const pins_raw = process.env.IST_APV_BUILD_HTTP_SHA256_PINS ?? "";
  let http_pins: Record<string, string>;
  try {
    http_pins = pins_raw ? JSON.parse(pins_raw) : {};
  } catch {
    throw new CommandTreeSyncError("部署配置 IST_APV_BUILD_HTTP_SHA256_PINS 不是合法 JSON");
  }
  if (typeof http_pins !== "object" || http_pins === null) {
    throw new CommandTreeSyncError("部署配置 IST_APV_BUILD_HTTP_SHA256_PINS 必须是 JSON 对象");
  }
  const allow_http = ["1", "true", "yes", "on"].includes((process.env.IST_APV_BUILD_ALLOW_INSECURE_HTTP ?? "0").trim().toLowerCase());
  return sync_command_tree(index_url, allowed, allowed_platforms, allowed_networks, trusted_http, http_pins, "APV", identity.full_version, String(product_version ?? identity.inventory_version), identity.build, generate_vendor_stdlib_projection, undefined, undefined, allow_http);
}
