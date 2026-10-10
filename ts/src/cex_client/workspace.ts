import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import {
  IS_WINDOWS,
  restrictDirPrivate,
  restrictFilePrivate,
  writeFileAtomic,
  writePrivateJson as platformWritePrivateJson,
  acquireLockSync,
  type FileLock,
} from "../platform/index.js";
import { ClientError } from "./errors.js";

export const STATE_DIR = ".compile-excel";
export const OUTPUTS_DIR = "compile_outputs";
export const CONFIG_SCHEMA = "cex.workspace/v1";
const _SAFE_COMPONENT_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const _BAD_COMPONENT_CHARS = new Set("\\:*?\"<>|");
export const DEFAULT_SERVER_PORT = 8900;
export const CONNECTION_STRING_FORM = `https://主机:${DEFAULT_SERVER_PORT}#ca=指纹`;
export const NO_DEVICE_BUILD =
  "还没有选构建号：登录后会自动选；服务端有多个构建时，用 cex_init 的 device_build 指定";

export function safeComponent(value: unknown, what: string): string {
  const text = String(value ?? "");
  if (!_SAFE_COMPONENT_RE.test(text) || text.includes("..")) {
    throw new ClientError(`${what} is not a safe path component: ${JSON.stringify(text)}`);
  }
  return text;
}

export function safeRelativePath(value: unknown): string {
  const text = String(value ?? "");
  if (!text || text.startsWith("/") || Buffer.byteLength(text, "utf8") > 1024) {
    throw new ClientError(`bundle entry path is invalid: ${JSON.stringify(text)}`);
  }
  for (const part of text.split("/")) {
    if (!part || part === "." || part === ".." || part.startsWith(".") ||
        [...part].some((ch) => ch.charCodeAt(0) < 32 || _BAD_COMPONENT_CHARS.has(ch))) {
      throw new ClientError(`bundle entry path is invalid: ${JSON.stringify(text)}`);
    }
  }
  return text;
}

export function isLoopbackHost(host: string | null | undefined): boolean {
  const h = (host ?? "").trim().replace(/^\[|\]$/g, "");
  if (h === "localhost") return true;
  try {
    if (h.includes(":")) {
      const addr = parseIPv6(h);
      return addr !== null && addr.every((b, i) => b === (i === 15 ? 1 : 0));
    }
    const addr = parseIPv4(h);
    return addr !== null && addr[0] === 127;
  } catch {
    return false;
  }
}

function parseIPv4(host: string): number[] | null {
  const parts = host.split(".");
  if (parts.length !== 4) return null;
  const out: number[] = [];
  for (const p of parts) {
    if (!/^\d{1,3}$/.test(p)) return null;
    const n = parseInt(p, 10);
    if (n > 255) return null;
    out.push(n);
  }
  return out;
}

function parseIPv6(host: string): number[] | null {
  if (host.includes(".")) {
    const lastColon = host.lastIndexOf(":");
    if (lastColon < 0) return null;
    const v4 = parseIPv4(host.slice(lastColon + 1));
    if (v4 === null) return null;
    host = host.slice(0, lastColon) + `:${v4[0] * 256 + v4[1]}:${v4[2] * 256 + v4[3]}`;
  }
  const halves = host.split("::");
  if (halves.length > 2) return null;
  const groups: number[] = [];
  const parseGroups = (s: string): number[] | null => {
    if (!s) return [];
    const parts = s.split(":");
    const out: number[] = [];
    for (const p of parts) {
      if (!/^[0-9a-fA-F]{1,4}$/.test(p)) return null;
      out.push(parseInt(p, 16));
    }
    return out;
  };
  if (halves.length === 1) {
    const g = parseGroups(halves[0]);
    if (g === null || g.length !== 8) return null;
    groups.push(...g);
  } else {
    const left = parseGroups(halves[0]);
    const right = parseGroups(halves[1]);
    if (left === null || right === null) return null;
    if (left.length + right.length > 8) return null;
    const missing = 8 - left.length - right.length;
    groups.push(...left, ...Array(missing).fill(0), ...right);
  }
  if (groups.length !== 8) return null;
  const bytes: number[] = [];
  for (const g of groups) {
    bytes.push((g >> 8) & 0xff, g & 0xff);
  }
  return bytes;
}

function compressIPv6(host: string): string | null {
  const bytes = parseIPv6(host);
  if (bytes === null) return null;
  const groups: number[] = [];
  for (let i = 0; i < 16; i += 2) {
    groups.push((bytes[i] << 8) | bytes[i + 1]);
  }
  let bestStart = -1;
  let bestLen = 0;
  let curStart = -1;
  let curLen = 0;
  for (let i = 0; i < 8; i++) {
    if (groups[i] === 0) {
      if (curStart === -1) curStart = i;
      curLen++;
      if (curLen > bestLen) {
        bestStart = curStart;
        bestLen = curLen;
      }
    } else {
      curStart = -1;
      curLen = 0;
    }
  }
  if (bestLen < 2) bestStart = -1;
  const hex = groups.map((g) => g.toString(16));
  let out = "";
  for (let i = 0; i < 8; i++) {
    if (i === bestStart) {
      out += "::";
      i += bestLen - 1;
      continue;
    }
    if (out && !out.endsWith(":")) out += ":";
    out += hex[i];
  }
  return out;
}

export function checkServerUrl(
  url: string,
  { allowInsecureHttp, what = "服务端" }: { allowInsecureHttp: boolean; what?: string },
): string {
  const trimmed = (url ?? "").trim().replace(/\/+$/, "");
  let parts: URL;
  try {
    parts = new URL(trimmed);
  } catch {
    throw new ClientError(`${what}地址不对（${JSON.stringify(url)}）：要写成 https://主机:端口；` +
      (what === "服务端" ? `最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）` : "网关地址由服务端下发，请管理员核对 gateway.url"));
  }
  const scheme = parts.protocol.replace(":", "");
  if ((scheme !== "http" && scheme !== "https") || !parts.hostname) {
    throw new ClientError(`${what}地址不对（${JSON.stringify(url)}）：要写成 https://主机:端口；` +
      (what === "服务端" ? `最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）` : "网关地址由服务端下发，请管理员核对 gateway.url"));
  }
  const port = parts.port ? parseInt(parts.port, 10) : (scheme === "https" ? 443 : 80);
  if (Number.isNaN(port) || port < 1 || port > 65535) {
    throw new ClientError(`${what}地址里的端口不对（${JSON.stringify(url)}）：端口是 1–65535 的数字；` +
      (what === "服务端" ? `最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）` : "网关地址由服务端下发，请管理员核对 gateway.url"));
  }
  if (parts.username || parts.password) {
    throw new ClientError(`${what}地址里不能带用户名或口令（${parts.hostname}）：去掉 @ 及前面的部分`);
  }
  if (scheme === "http" && !allowInsecureHttp && !isLoopbackHost(parts.hostname)) {
    throw new ClientError(
      `明文 http 连非本机的${what}（${parts.hostname}）会把登录令牌明文发到网络上：请改用 https，` +
      (what === "服务端" ? `最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）` : "网关地址由服务端下发，请管理员核对 gateway.url") +
      `。确认是可信实验网、${what}确实只开了明文时，才在 cex_init 里加 insecure_lan=true 放行`);
  }
  return trimmed;
}

const _DEFAULT_PORTS: Record<string, number> = { https: 443, http: 80 };

export function normalizeServerUrl(url: string): string {
  const text = (url ?? "").trim().replace(/\/+$/, "");
  let parts: URL;
  try {
    parts = new URL(text);
  } catch {
    return text;
  }
  const scheme = parts.protocol.replace(":", "").toLowerCase();
  if (!(scheme in _DEFAULT_PORTS)) return text;
  let host = parts.hostname;
  if (!host) return text;
  const port = parts.port ? parseInt(parts.port, 10) : _DEFAULT_PORTS[scheme];
  if (host.includes(":")) {
    const compressed = compressIPv6(host);
    if (compressed !== null) {
      host = `[${compressed}]`;
    }
  }
  if (port !== _DEFAULT_PORTS[scheme]) {
    host += `:${port}`;
  }
  const pathStr = parts.pathname.replace(/\/+$/, "");
  return `${scheme}://${host}${pathStr}${parts.search}${parts.hash ? "" : ""}`;
}

export function sameServer(a: unknown, b: unknown): boolean {
  const left = String(a ?? "").trim();
  const right = String(b ?? "").trim();
  return Boolean(left && right) && normalizeServerUrl(left) === normalizeServerUrl(right);
}

const _PEM_BEGIN = "-----BEGIN CERTIFICATE-----";
const _PEM_END = "-----END CERTIFICATE-----";

function _wholeDerSequence(der: Buffer): boolean {
  if (der.length < 2 || der[0] !== 0x30) return false;
  if (der[1] < 0x80) return 2 + der[1] === der.length;
  const count = der[1] & 0x7f;
  if (count < 1 || count > 4 || der.length < 2 + count) return false;
  return 2 + count + der.readUIntBE(2, count) === der.length;
}

export function pemToDer(pem: string): Buffer {
  const text = pem.trim();
  if (!text.startsWith(_PEM_BEGIN) || !text.endsWith(_PEM_END) || (text.match(/-----/g) ?? []).length !== 4) {
    throw new Error("not exactly one PEM certificate block");
  }
  const body = text.slice(_PEM_BEGIN.length, -_PEM_END.length).replace(/[\r\n]+/g, "");
  let der: Buffer;
  try {
    der = Buffer.from(body, "base64");
    if (der.toString("base64") !== body) throw new Error("strict");
  } catch {
    throw new Error("the PEM body is not strict base64");
  }
  if (!_wholeDerSequence(der)) {
    throw new Error("the PEM body is not one DER certificate");
  }
  return der;
}

export function caFingerprint(pem: string): string {
  return crypto.createHash("sha256").update(pemToDer(pem)).digest("hex");
}

export class Workspace {
  constructor(public readonly root: string) {}

  get stateDir(): string {
    return path.join(this.root, STATE_DIR);
  }
  get configPath(): string {
    return path.join(this.stateDir, "config.json");
  }
  get tokenPath(): string {
    return path.join(this.stateDir, "token.json");
  }
  get pendingLoginPath(): string {
    return path.join(this.stateDir, "login_pending.json");
  }
  get clientConfigPath(): string {
    return path.join(this.stateDir, "client_config.json");
  }
  get leasePath(): string {
    return path.join(this.stateDir, "lease.json");
  }
  get caPath(): string {
    return path.join(this.stateDir, "ca.pem");
  }
  get outputsDir(): string {
    return path.join(this.root, OUTPUTS_DIR);
  }

  config(): Record<string, unknown> {
    let data: unknown;
    try {
      data = JSON.parse(fs.readFileSync(this.configPath, "utf8"));
    } catch (exc) {
      throw new ClientError(`workspace config unreadable: ${exc}`);
    }
    if (!data || typeof data !== "object" || (data as Record<string, unknown>).schema !== CONFIG_SCHEMA) {
      throw new ClientError("workspace config has an unknown schema; re-run cex_init");
    }
    return data as Record<string, unknown>;
  }

  saveConfig(data: Record<string, unknown>): void {
    writePrivateJson(this.configPath, { ...data, schema: CONFIG_SCHEMA });
  }

  get server(): string {
    const cfg = this.config();
    return normalizeServerUrl(
      checkServerUrl(String(cfg.server ?? ""), { allowInsecureHttp: Boolean(cfg.allow_insecure_http) }),
    );
  }

  get deviceBuild(): string {
    const build = this.config().device_build;
    if (!build) {
      throw new ClientError(NO_DEVICE_BUILD);
    }
    return safeComponent(build, "device_build");
  }

  get selectedBuild(): string {
    return String(this.config().device_build ?? "");
  }

  sslOptions(): { ca?: string } | undefined {
    const expected = String(this.config().ca_sha256 ?? "");
    if (!expected) return undefined;
    const broken = (reason: string) =>
      `工作区里的 CA 证书（.compile-excel/ca.pem）${reason}：请用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）重新执行 cex_init`;
    try {
      if (fs.lstatSync(this.caPath).isSymbolicLink()) {
        throw new ClientError(broken("不见了"));
      }
    } catch {
      throw new ClientError(broken("不见了"));
    }
    if (!fs.existsSync(this.caPath)) {
      throw new ClientError(broken("不见了"));
    }
    let pem: string;
    try {
      pem = fs.readFileSync(this.caPath, "ascii");
    } catch {
      throw new ClientError(broken("读不出来，或不是恰好一张证书"));
    }
    let der: Buffer;
    try {
      der = pemToDer(pem);
    } catch {
      throw new ClientError(broken("读不出来，或不是恰好一张证书"));
    }
    if (crypto.createHash("sha256").update(der).digest("hex") !== expected) {
      throw new ClientError(broken("与配置里记的指纹不一致，可能被改动过"));
    }
    return { ca: pem };
  }

  get channel(): string {
    const channel = String(this.config().channel ?? "stable");
    if (channel !== "stable" && channel !== "candidate") {
      throw new ClientError(`unknown channel ${JSON.stringify(channel)}`);
    }
    return channel;
  }

  bundleDir(build?: string): string {
    return path.join(this.stateDir, "bundle", safeComponent(build ?? this.deviceBuild, "device_build"));
  }
}

export function writePrivateJson(filePath: string, data: Record<string, unknown>): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  try {
    if (fs.lstatSync(filePath).isSymbolicLink()) {
      throw new ClientError(`${path.basename(filePath)} is a symlink; refusing to write`);
    }
  } catch (e: unknown) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
  }
  platformWritePrivateJson(filePath, data);
}

export function readPrivateJson(filePath: string): Record<string, unknown> | null {
  let st: fs.Stats;
  try {
    st = fs.lstatSync(filePath);
  } catch (e: unknown) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw e;
  }
  if (!st.isFile() || st.isSymbolicLink()) {
    throw new ClientError(`${path.basename(filePath)} is not a regular file`);
  }
  if (!IS_WINDOWS && (st.mode & 0o077) !== 0) {
    throw new ClientError(`${path.basename(filePath)} permissions are wider than 0600; fix them or log in again`);
  }
  let data: unknown;
  try {
    data = JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    throw new ClientError(`${path.basename(filePath)} is corrupted; log in again`);
  }
  return data !== null && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : null;
}

export function writeFileSafely(root: string, filePath: string, data: Buffer | string, mode = 0o644): void {
  const rel = path.relative(root, filePath);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new ClientError(`${filePath} is outside ${root}; refusing to write`);
  }
  const parts = rel.split(path.sep);
  if (!parts.length || parts.some((p) => p === "" || p === "." || p === "..")) {
    throw new ClientError(`${filePath} is not a file path under ${root}`);
  }
  let current = root;
  for (const part of parts) {
    current = path.join(current, part);
    try {
      if (fs.lstatSync(current).isSymbolicLink()) {
        throw new ClientError(`${current} is a symlink; refusing to write through it`);
      }
    } catch (e: unknown) {
      if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
    }
  }
  writeFileAtomic(filePath, data, { private: mode === 0o600 });
  if (!IS_WINDOWS) {
    try {
      fs.chmodSync(filePath, mode);
    } catch {}
  }
}

export interface StateLock {
  release(): void;
}

export function stateLock(ws: Workspace, kind: string, key = "", shared = false): StateLock {
  let name = safeComponent(kind, "lock kind");
  if (key) {
    name += "." + crypto.createHash("sha256").update(key, "utf8").digest("hex").slice(0, 24);
  }
  const dir = path.join(ws.stateDir, "locks");
  fs.mkdirSync(dir, { recursive: true });
  const lockPath = path.join(dir, `${name}.lock`);
  return acquireLockSync(lockPath);
}

export function toStatePath(ws: Workspace, p: string): string {
  const resolved = path.resolve(p);
  const rootResolved = path.resolve(ws.root);
  const rel = path.relative(rootResolved, resolved);
  if (!rel.startsWith("..") && !path.isAbsolute(rel)) {
    return rel.split(path.sep).join("/");
  }
  return p;
}

export function fromStatePath(ws: Workspace, value: unknown): string {
  const text = String(value ?? "");
  if (!text) {
    throw new ClientError("the workspace state records an empty path");
  }
  const p = path.resolve(text);
  if (!path.isAbsolute(text)) {
    return path.join(ws.root, text);
  }
  const rootResolved = path.resolve(ws.root);
  if (p.startsWith(rootResolved + path.sep) || p === rootResolved) {
    return p;
  }
  const parts = p.split(path.sep);
  for (let i = parts.length - 1; i > 0; i--) {
    if (parts[i] === STATE_DIR || parts[i] === OUTPUTS_DIR) {
      return path.join(ws.root, ...parts.slice(i));
    }
  }
  return p;
}

export function find(start?: string): Workspace | null {
  if (start === undefined) {
    const explicit = process.env.CEX_WORKSPACE;
    if (explicit) {
      const root = path.resolve(explicit);
      if (fs.existsSync(path.join(root, STATE_DIR, "config.json"))) {
        return new Workspace(root);
      }
    }
  }
  const here = path.resolve(start ?? process.cwd());
  let current: string | null = here;
  while (current) {
    if (fs.existsSync(path.join(current, STATE_DIR, "config.json"))) {
      return new Workspace(current);
    }
    const parent = path.dirname(current);
    current = parent === current ? null : parent;
  }
  return null;
}

export function requireWorkspace(start?: string): Workspace {
  const ws = find(start);
  if (ws === null) {
    throw new ClientError(
      `这里还没有 compile-excel 工作区：先在项目文件夹里执行 cex_init（server 用管理员给的连接串，形如 ${CONNECTION_STRING_FORM}）`);
  }
  return ws;
}

export function init(
  root: string,
  { server, deviceBuild = "", channel = "stable", insecureLan = false, caSha256 = "", caPem = "" }: {
    server: string;
    deviceBuild?: string;
    channel?: string;
    insecureLan?: boolean;
    caSha256?: string;
    caPem?: string;
  },
): Workspace {
  const resolvedRoot = path.resolve(root);
  const normalizedServer = normalizeServerUrl(checkServerUrl(server, { allowInsecureHttp: insecureLan }));
  if (deviceBuild) {
    safeComponent(deviceBuild, "device_build");
  }
  if (caSha256 && caFingerprint(caPem) !== caSha256) {
    throw new ClientError("CA 证书与指纹对不上，拒绝保存：请用管理员给的连接串重新执行 cex_init");
  }
  const ws = new Workspace(resolvedRoot);
  fs.mkdirSync(ws.stateDir, { recursive: true });
  restrictDirPrivate(ws.stateDir);
  const ignore = path.join(ws.stateDir, ".gitignore");
  if (!fs.existsSync(ignore)) {
    fs.writeFileSync(ignore, "# compile-excel 工作区状态：含令牌，整目录不入库\n*\n", "utf8");
  }
  let previous: Record<string, unknown> = {};
  if (fs.existsSync(ws.configPath)) {
    try {
      previous = ws.config();
    } catch {
      previous = {};
    }
  }
  if (previous && (Object.keys(previous).length > 0) &&
      (!sameServer(previous.server, normalizedServer) || String(previous.ca_sha256 ?? "") !== caSha256)) {
    for (const stale of [ws.tokenPath, ws.clientConfigPath, ws.leasePath, ws.pendingLoginPath]) {
      try {
        fs.unlinkSync(stale);
      } catch {}
    }
  }
  if (caSha256) {
    writeFileSafely(ws.root, ws.caPath, caPem, 0o644);
  } else {
    try {
      fs.unlinkSync(ws.caPath);
    } catch {}
  }
  ws.saveConfig({
    server: normalizedServer,
    device_build: deviceBuild,
    channel,
    allow_insecure_http: Boolean(insecureLan),
    ca_sha256: caSha256,
  });
  return ws;
}

export { requireWorkspace as require };
