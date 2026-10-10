import fs from "node:fs";
import crypto from "node:crypto";
import tls from "node:tls";
import { ClientError } from "./errors.js";
import { httpRequest, httpRequestNoRedirect } from "./http.js";
import {
  CONNECTION_STRING_FORM,
  Workspace,
  checkServerUrl,
  normalizeServerUrl,
  pemToDer,
  sameServer,
  safeComponent,
} from "./workspace.js";
import { readPrivateJson } from "./workspace.js";

export const SERVICE_NAME = "compile-excel-server";
export const PROBE_TIMEOUT = 10_000;
export const FETCH_MAX_BYTES = 64 * 1024;
export const FETCH_DEADLINE = 15_000;
export const CHANNELS = ["stable", "candidate"] as const;

const _HEX = new Set("0123456789abcdef");

export function normalizeFingerprint(text: string): string {
  let value = decodeURIComponent(text ?? "").trim().toLowerCase();
  for (const prefix of ["sha256:", "sha-256:"]) {
    if (value.startsWith(prefix)) value = value.slice(prefix.length);
  }
  value = value.replace(/[\s:]/g, "");
  if (value.length !== 64 || [...value].some((c) => !_HEX.has(c))) {
    throw new ClientError(
      `连接串里的证书指纹不对（${JSON.stringify(text)}）：应是 64 位十六进制的 SHA-256。请从管理员给的连接串原样复制，不要删改`);
  }
  return value;
}

export function parseConnectionString(text: string): [string, string] {
  const idx = (text ?? "").trim().indexOf("#");
  const base = idx < 0 ? text.trim() : text.trim().slice(0, idx);
  const sep = idx >= 0;
  const fragment = idx >= 0 ? text.trim().slice(idx + 1) : "";
  const url = base.replace(/\/+$/, "");
  if (!sep) return [url, ""];
  const params: Record<string, string> = {};
  for (const item of fragment.split("&")) {
    const eqIdx = item.indexOf("=");
    if (eqIdx >= 0) params[item.slice(0, eqIdx).trim().toLowerCase()] = item.slice(eqIdx + 1);
  }
  if (!("ca" in params)) {
    throw new ClientError(
      `连接串 # 后面应是 ca=<证书指纹>（${JSON.stringify(text)}）：请从管理员给的连接串原样复制，形如 ${CONNECTION_STRING_FORM}`);
  }
  const fingerprint = normalizeFingerprint(params.ca);
  if (!url.startsWith("https://")) {
    throw new ClientError(
      `带证书指纹（#ca=）的连接串要以 https:// 开头（${JSON.stringify(url)}）：请从管理员给的连接串原样复制`);
  }
  return [url, fingerprint];
}

function _healthzService(status: number, raw: Buffer): string | null {
  if (status !== 200) return null;
  try {
    const payload = JSON.parse(raw.toString("utf8"));
    return typeof payload === "object" && payload !== null ? String(payload.service ?? "") : null;
  } catch {
    return null;
  }
}

async function _fetchCa(url: string, expected: string, inherited = false): Promise<Buffer> {
  let status: number, raw: Buffer;
  try {
    const res = await httpRequestNoRedirect(url + "/ca.pem", {
      maxBytes: FETCH_MAX_BYTES,
      timeoutMs: FETCH_DEADLINE,
      rejectUnauthorized: false,
    });
    status = res.status;
    raw = res.body;
  } catch (e) {
    throw new ClientError(String(e));
  }
  if (status >= 300 && status < 400) {
    throw new ClientError(
      `${url} 回了重定向（HTTP ${status}），客户端不跟随重定向（免得把凭据带到别处）：请直接用管理员给的连接串里的地址（形如 ${CONNECTION_STRING_FORM}）`);
  }
  if (status === 404 && inherited) return Buffer.alloc(0);
  let der: Buffer | null = null;
  if (status === 200) {
    try {
      der = pemToDer(raw.toString("ascii"));
    } catch {
      der = null;
    }
  }
  if (status === 200) {
    try {
      der = pemToDer(raw.toString("ascii"));
    } catch {
      der = null;
    }
  }
  if (der === null) {
    let probeStatus = 0, probeRaw: Buffer = Buffer.alloc(0);
    try {
      const res = await httpRequestNoRedirect(url + "/healthz", {
        maxBytes: FETCH_MAX_BYTES,
        timeoutMs: FETCH_DEADLINE,
        rejectUnauthorized: false,
      });
      probeStatus = res.status;
      probeRaw = res.body;
    } catch {}
    if (_healthzService(probeStatus, probeRaw) !== SERVICE_NAME) {
      throw new ClientError(
        `这个地址上的服务不是 compile-excel-server（${url}：${status !== 200 ? `/ca.pem 回 HTTP ${status}` : "/ca.pem 回的不是证书"}）。请核对地址和端口；最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）`);
    }
    if (status === 200) {
      throw new ClientError(
        "服务端发来的根证书格式不对（应当恰好是一张证书）：可能连到了冒充的服务端，也可能服务端配置有误。已拒绝连接，什么都没保存；请把这段报错发给管理员");
    }
    throw new ClientError(
      `服务端没有启用内置 CA（/ca.pem 回 HTTP ${status}），连接串里的指纹用不上：请向管理员要新的连接串；服务端用的是正式机构签发的证书时，去掉 #ca= 及后面的部分，只用地址`);
  }
  const actual = crypto.createHash("sha256").update(der).digest("hex");
  if (actual !== expected) {
    throw new ClientError(
      `服务端发来的 CA 证书与连接串里的指纹不一致（连接串 ${expected.slice(0, 16)}…，实际 ${actual.slice(0, 16)}…）：可能连到了冒充的服务端（证书被调包），也可能连接串抄错了。已拒绝连接，什么都没保存；请向管理员核对连接串`);
  }
  return der;
}

export async function probe(
  url: string,
  caSha256 = "",
  { insecureLan = false, inherited = false }: { insecureLan?: boolean; inherited?: boolean } = {},
): Promise<string> {
  const checkedUrl = checkServerUrl(url, { allowInsecureHttp: insecureLan });
  let caPem = "";
  let ca: string | undefined;
  if (caSha256) {
    const der = await _fetchCa(checkedUrl, caSha256, inherited);
    if (der.length > 0) {
      caPem = der.toString("base64");
      ca = `-----BEGIN CERTIFICATE-----\n${caPem}\n-----END CERTIFICATE-----\n`;
    }
  }
  let status: number, raw: Buffer;
  try {
    const res = await httpRequestNoRedirect(checkedUrl + "/healthz", {
      maxBytes: FETCH_MAX_BYTES,
      timeoutMs: FETCH_DEADLINE,
      headers: { Accept: "application/json" },
      ca,
    });
    status = res.status;
    raw = res.body;
  } catch (e) {
    throw new ClientError(String(e));
  }
  if (status >= 300 && status < 400) {
    throw new ClientError(
      `${checkedUrl} 回了重定向（HTTP ${status}），客户端不跟随重定向（免得把凭据带到别处）：请直接用管理员给的连接串里的地址（形如 ${CONNECTION_STRING_FORM}）`);
  }
  const service = _healthzService(status, raw);
  if (service !== SERVICE_NAME) {
    const detail = status !== 200
      ? `/healthz 回 HTTP ${status}`
      : service === null
        ? "/healthz 回的不是 JSON"
        : `/healthz 自称 ${service || "无名服务"}`;
    throw new ClientError(
      `这个地址上的服务不是 compile-excel-server（${checkedUrl}：${detail}）。请核对地址和端口；最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）`);
  }
  return caPem;
}

function _previousConfig(root: string): Record<string, unknown> {
  const ws = new Workspace(root);
  if (!fs.existsSync(ws.configPath)) return {};
  try {
    return ws.config();
  } catch {
    return {};
  }
}

export async function setup(
  root: string,
  { server = "", deviceBuild = "", channel = "", insecureLan }: {
    server?: string;
    deviceBuild?: string;
    channel?: string;
    insecureLan?: boolean | null;
  } = {},
): Promise<Workspace> {
  const resolvedRoot = root;
  if (channel && !CHANNELS.includes(channel as "stable" | "candidate")) {
    throw new ClientError(`channel 只能是 stable 或 candidate：${JSON.stringify(channel)}`);
  }
  const previous = _previousConfig(resolvedRoot);
  if (deviceBuild) {
    safeComponent(deviceBuild, "device_build");
  }
  if (!server.trim()) {
    if (!previous.server) {
      throw new ClientError(
        `缺少服务端地址：请向管理员要连接串（形如 ${CONNECTION_STRING_FORM}），用 cex_init 的 server 传入`);
    }
    const ws = new Workspace(resolvedRoot);
    const config: Record<string, unknown> = { ...previous };
    if (deviceBuild) config.device_build = deviceBuild;
    if (channel) config.channel = channel;
    if (insecureLan !== null && insecureLan !== undefined) config.allow_insecure_http = Boolean(insecureLan);
    config.server = normalizeServerUrl(
      checkServerUrl(String(config.server ?? ""), { allowInsecureHttp: Boolean(config.allow_insecure_http) }));
    ws.saveConfig(config);
    return ws;
  }
  const [url, fingerprint] = parseConnectionString(server);
  const insecure = Boolean(insecureLan);
  const normalizedUrl = normalizeServerUrl(checkServerUrl(url, { allowInsecureHttp: insecure }));
  const isSameServer = sameServer(previous.server, normalizedUrl);
  const inheritedCa = !fingerprint && isSameServer && Boolean(previous.ca_sha256);
  const effectiveFingerprint = fingerprint || (inheritedCa ? String(previous.ca_sha256) : "");
  const caPem = await probe(normalizedUrl, effectiveFingerprint, { insecureLan: insecure, inherited: inheritedCa });
  let finalFingerprint = effectiveFingerprint;
  if (!caPem) {
    finalFingerprint = "";
  }
  const build = deviceBuild || (isSameServer ? String(previous.device_build ?? "") : "");
  return workspaceInit(resolvedRoot, {
    server: normalizedUrl,
    deviceBuild: build,
    channel: channel || String(previous.channel ?? "stable"),
    insecureLan: insecure,
    caSha256: finalFingerprint,
    caPem,
  });
}

async function workspaceInit(
  root: string,
  opts: {
    server: string;
    deviceBuild?: string;
    channel?: string;
    insecureLan?: boolean;
    caSha256?: string;
    caPem?: string;
  },
): Promise<Workspace> {
  const { init } = await import("./workspace.js");
  return init(root, opts);
}

export async function publishedBuilds(ws: Workspace, channel: string): Promise<string[]> {
  const { requestJson } = await import("./auth.js");
  const payload = await requestJson(ws, "GET", "/v1/builds");
  const names = new Set<string>();
  for (const row of (payload.builds as unknown[]) ?? []) {
    if (typeof row !== "object" || row === null) continue;
    const pointer = ((row as Record<string, unknown>).channels as Record<string, unknown> | undefined)?.[channel] as Record<string, unknown> | undefined;
    const name = String((row as Record<string, unknown>).build ?? "");
    if (pointer?.bundle_id && name) {
      try {
        names.add(safeComponent(name, "build"));
      } catch {
        continue;
      }
    }
  }
  return [...names].sort();
}

export async function chooseBuild(ws: Workspace, channel = ""): Promise<Record<string, unknown>> {
  const ch = channel || ws.channel;
  if (!CHANNELS.includes(ch as "stable" | "candidate")) {
    throw new ClientError(`channel 只能是 stable 或 candidate：${JSON.stringify(ch)}`);
  }
  const builds = await publishedBuilds(ws, ch);
  if (builds.length === 1) {
    const config = ws.config();
    config.device_build = builds[0];
    ws.saveConfig(config);
    return {
      device_build: builds[0],
      device_build_note: `服务端在 ${ch} 通道上只有一个构建 ${builds[0]}，已自动选用`,
    };
  }
  if (builds.length === 0) {
    return {
      device_build: null,
      device_build_note: `服务端还没有在 ${ch} 通道上发布任何构建，暂时同步不了编译数据：请联系管理员发布构建`,
    };
  }
  return {
    device_build: null,
    builds,
    device_build_note: `服务端在 ${ch} 通道上有多个构建（${builds.join("、")}）：请让用户选被测设备对应的那个，再用 cex_init 的 device_build 指定（不用再给 server，登录保留）`,
  };
}

export function tlsSummary(ws: Workspace): string {
  const config = ws.config();
  const parts = new URL(ws.server);
  if (parts.protocol === "http:") {
    return parts.hostname === "localhost" || parts.hostname.startsWith("127.") ? "明文（本机回环）" : "明文（insecure_lan）";
  }
  if (config.ca_sha256) {
    try {
      ws.sslOptions();
    } catch (e) {
      return `内置 CA（${e}）`;
    }
    return "内置 CA（指纹已核对）";
  }
  return "系统证书";
}

export async function serverCertificateSha256(ws: Workspace): Promise<string> {
  const parts = new URL(ws.server);
  const host = parts.hostname;
  const port = parts.port ? parseInt(parts.port, 10) : 443;
  const opts = ws.sslOptions();
  return new Promise((resolve, reject) => {
    const socket = tls.connect({
      host,
      port,
      servername: host,
      rejectUnauthorized: opts?.ca !== undefined,
      ca: opts?.ca,
      timeout: PROBE_TIMEOUT,
    });
    socket.once("secureConnect", () => {
      const cert = socket.getPeerCertificate(true);
      socket.end();
      if (!cert || !cert.raw) {
        reject(new Error("no peer certificate"));
        return;
      }
      const digest = crypto.createHash("sha256").update(cert.raw).digest("hex").toUpperCase();
      resolve(digest.match(/../g)?.join(" ") ?? "");
    });
    socket.once("error", reject);
    socket.once("timeout", () => {
      socket.destroy();
      reject(new Error("timeout"));
    });
  });
}

export async function browserCertificateNote(ws: Workspace): Promise<string> {
  if (!String(ws.config().ca_sha256 ?? "")) return "";
  let check = "";
  try {
    const fp = await serverCertificateSha256(ws);
    check = `继续之前，请在浏览器的提示页上打开证书详情，核对服务器证书的 SHA-256 指纹是否为：\n${fp}\n一致再选择继续访问；不一致就不要继续，把这段说明发给管理员。`;
  } catch (e) {
    const reason = e instanceof ClientError ? e.message : String(e);
    check = `但这次没能取到服务器证书的指纹，没法核对，请先不要在浏览器里继续：稍后重新调用 \`cex_login_start\` 再核对；一直取不到就把这段说明发给管理员。原因：${reason}`;
  }
  const p = ws.caPath;
  const windowsPath = `"${p.replace(/"/g, "")}"`;
  return (
    "浏览器打开授权页时会提示证书不受信任（例如“您的连接不是私密连接”）。这是因为服务端用的是它自带的根证书，浏览器不认识；编译助手已经按管理员给的连接串核对过这份根证书。"
    + check + "\n"
    + "想以后不再提示，可以把工作区里的根证书 `.compile-excel/ca.pem` 加入系统信任，然后重启浏览器：\n"
    + `- macOS：\`security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db ${p}\`\n`
    + `- Windows：\`certutil -addstore -user Root ${windowsPath}\``);
}
