import fs from "node:fs";
import { ClientError, NotLoggedIn, ServerUnreachable } from "./errors.js";
import { httpRequest, httpRequestNoRedirect, HttpRequestOptions } from "./http.js";
import { DEFAULT_SERVER_PORT } from "./workspace.js";
import {
  CONNECTION_STRING_FORM,
  Workspace,
  readPrivateJson,
  sameServer,
  stateLock,
  writePrivateJson,
} from "./workspace.js";

export const DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code";
export const CLIENT_ID = "compile-excel-skill";
export const BASE_SCOPES = "artifacts:read docs:query bundles:read config:read jumphost:run";
export const DEFAULT_SCOPES = BASE_SCOPES + " jumphost:admin";
export const USER_AGENT = "cex-client/1";
export const NOT_LOGGED_IN = "还没有登录：先调用 cex_login_start，让用户在浏览器里授权";
export const LOGIN_AGAIN = "登录已过期或被撤销：重新登录（cex_login_start）";

function _unreachable(exc: unknown, url = ""): string {
  const parts = new URL(url);
  const where = parts.hostname ? `连不上 ${parts.protocol}//${parts.host}` : "连不上服务端";
  const hint = portHint(url);
  const reason = exc instanceof Error ? exc : new Error(String(exc));
  const msg = reason.message.toLowerCase();

  if (msg.includes("certificate") || msg.includes("ssl") || msg.includes("tls")) {
    if (msg.includes("hostname") || msg.includes("mismatch")) {
      return `${where}：证书里没有这个地址（${parts.hostname}）。请管理员在 ces 菜单里重新签发证书并加上这个地址；或者改用证书里已有的地址连接`;
    }
    return `${where}：证书不受信任（${reason.message}）。请用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）重新执行 cex_init，客户端核对指纹后就信任服务端自带的 CA；服务端用的是组织 CA 签发的证书时，让运行工具的进程带上 SSL_CERT_FILE，指向含该 CA 的证书包`;
  }
  if (msg.includes("econnrefused") || msg.includes("connection refused")) {
    return `${where}：对方拒绝连接（这个端口上没有服务在监听）。请核对地址和端口、确认服务端已启动${hint ? `；${hint}` : ""}`;
  }
  if (msg.includes("etimedout") || msg.includes("timeout") || msg.includes("timed out")) {
    return `${where}：连接超时。请确认本机与服务端网络相通（同一局域网或已连 VPN）、地址无误、服务端的防火墙放行了这个端口${hint ? `；${hint}` : ""}`;
  }
  if (msg.includes("enotfound") || msg.includes("getaddrinfo")) {
    return `${where}：找不到主机 ${parts.hostname}（域名解析失败）。请核对地址拼写，或改用 IP 地址`;
  }
  if (msg.includes("ehostunreach") || msg.includes("enetunreach")) {
    return `${where}：网络不通（${reason.message}）。请确认本机与服务端网络相通（同一局域网或已连 VPN）`;
  }
  const detail = reason.message.trim();
  return `${where}（${reason.constructor.name}${detail ? ": " + detail.slice(0, 160) : ""}）。请确认地址无误、服务端在运行、网络相通`;
}

export function portHint(url: string): string {
  let parts: URL;
  try {
    parts = new URL(url);
  } catch {
    return "";
  }
  if (parts.port || !parts.hostname) return "";
  return `地址里没写端口，服务端默认端口是 ${DEFAULT_SERVER_PORT}，例如 https://${parts.host}:${DEFAULT_SERVER_PORT}；最好直接用管理员给的连接串`;
}

export function notOurServer(url: string, detail: string): string {
  return `这个地址上的服务不是 compile-excel-server（${url}：${detail}）。` +
    (portHint(url) || `请核对地址和端口；最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）`);
}

export function redirectRefused(url: string, status: number): string {
  return `${url} 回了重定向（HTTP ${status}），客户端不跟随重定向（免得把凭据带到别处）：请直接用管理员给的连接串里的地址（形如 ${CONNECTION_STRING_FORM}）`;
}

export function refuseRedirect(status: number, what: string): void {
  if (status >= 300 && status < 400) {
    throw new ClientError(`${what} answered with a redirect (HTTP ${status}); the client does not follow redirects with credentials. Check the configured address (the https URL itself, not one that forwards)`);
  }
}

export function _form(values: Record<string, string>): [string, Record<string, string>] {
  return [
    new URLSearchParams(values).toString(),
    { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
  ];
}

export function _json(raw: Buffer): Record<string, unknown> {
  try {
    const data = JSON.parse(raw.toString("utf8"));
    return typeof data === "object" && data !== null && !Array.isArray(data) ? data as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

async function http(
  method: string,
  url: string,
  { data, headers, timeout = 60_000, ca }: {
    data?: string | Buffer;
    headers?: Record<string, string>;
    timeout?: number;
    ca?: string;
  } = {},
): Promise<[number, Buffer]> {
  const opts: HttpRequestOptions = {
    method,
    headers: { "User-Agent": USER_AGENT, ...(headers ?? {}) },
    body: data,
    timeoutMs: timeout,
    maxRedirects: 0,
    ca,
  };
  try {
    const res = await httpRequestNoRedirect(url, opts);
    return [res.status, res.body];
  } catch (e) {
    if (e instanceof ClientError) throw e;
    throw new ServerUnreachable(_unreachable(e, url));
  }
}

export async function httpCapped(
  method: string,
  url: string,
  { maxBytes, deadlineS, headers, ca }: {
    maxBytes: number;
    deadlineS: number;
    headers?: Record<string, string>;
    ca?: string;
  },
): Promise<[number, Buffer]> {
  const parts = new URL(url);
  const origin = `${parts.protocol}//${parts.host}`;
  const deadline = Date.now() + deadlineS * 1000;
  const opts: HttpRequestOptions = {
    method,
    headers: { "User-Agent": USER_AGENT, ...(headers ?? {}) },
    timeoutMs: deadlineS * 1000,
    maxBytes,
    maxRedirects: 0,
    ca,
  };
  let res;
  try {
    res = await httpRequestNoRedirect(url, opts);
  } catch (e) {
    if (e instanceof ClientError) throw e;
    if (Date.now() >= deadline) {
      throw new ClientError(
        `${origin}${parts.pathname} 在 ${deadlineS} 秒内没有回完应答，已放弃：对方可能不是 compile-excel-server，或网络太慢。请核对地址、确认网络通畅后重试；最好直接用管理员给的连接串（形如 ${CONNECTION_STRING_FORM}）`);
    }
    throw new ServerUnreachable(_unreachable(e, url));
  }
  if (res.status >= 300 && res.status < 400) {
    return [res.status, res.body];
  }
  return [res.status, res.body];
}

export async function startLogin(ws: Workspace, scope = DEFAULT_SCOPES): Promise<Record<string, unknown>> {
  const url = ws.server + "/device_authorize";
  const opts = ws.sslOptions();
  const [body, headers] = _form({ client_id: CLIENT_ID, scope });
  let [status, raw] = await http("POST", url, { data: body, headers, ca: opts?.ca });
  let payload = _json(raw);
  if (status === 400 && payload.error === "invalid_scope" && scope === DEFAULT_SCOPES) {
    const [body2, headers2] = _form({ client_id: CLIENT_ID, scope: BASE_SCOPES });
    [status, raw] = await http("POST", url, { data: body2, headers: headers2, ca: opts?.ca });
    payload = _json(raw);
  }
  if (status >= 300 && status < 400) {
    throw new ClientError(redirectRefused(ws.server, status));
  }
  if (status === 404) {
    throw new ClientError(notOurServer(ws.server, "登录入口 /device_authorize 回 HTTP 404") + "；改好地址后重新执行 cex_init");
  }
  if (status !== 200 || !("device_code" in payload)) {
    const detail = payload.error ?? payload.detail ?? "没有说明";
    throw new ClientError(`发起登录失败（HTTP ${status}，${detail}）。请稍后重试 cex_login_start；一直失败就把这段报错发给管理员`);
  }
  writePrivateJson(ws.pendingLoginPath, {
    device_code: payload.device_code,
    server: ws.server,
    interval: parseInt(String(payload.interval ?? "5"), 10),
    expires_at: Date.now() / 1000 + parseInt(String(payload.expires_in ?? "600"), 10),
  });
  return {
    verification_uri: payload.verification_uri,
    verification_uri_complete: payload.verification_uri_complete,
    user_code: payload.user_code,
    expires_in: payload.expires_in,
    next: "Show the user the URL and code; they sign in with their username and access code in a browser. Then call cex_login_wait.",
  };
}

function _storeTokens(ws: Workspace, issued: Record<string, unknown>, previous: Record<string, unknown> | null): void {
  writePrivateJson(ws.tokenPath, {
    access_token: issued.access_token,
    refresh_token: issued.refresh_token ?? previous?.refresh_token ?? "",
    expires_at: Math.floor(Date.now() / 1000) + parseInt(String(issued.expires_in ?? "900"), 10),
    scope: issued.scope ?? "",
    server: ws.server,
  });
}

const _LOGIN_ERRORS: Record<string, string> = {
  access_denied: "登录被拒绝：用户在授权页点了拒绝，或用户名、访问码不对。核对后重新调用 cex_login_start",
  expired_token: "授权码已过期（没在有效期内完成授权）：重新调用 cex_login_start",
  invalid_grant: "这次登录已失效（授权码用过或被撤销）：重新调用 cex_login_start",
};

export async function waitLogin(ws: Workspace, timeoutS = 60): Promise<Record<string, unknown>> {
  const pending = readPrivateJson(ws.pendingLoginPath);
  if (!pending) {
    throw new ClientError("没有进行中的登录：先调用 cex_login_start");
  }
  if (!sameServer(pending.server, ws.server)) {
    try { fs.unlinkSync(ws.pendingLoginPath); } catch {}
    throw new ClientError("登录过程中工作区换了服务端：重新调用 cex_login_start");
  }
  const deadline = Math.min(Date.now() / 1000 + Math.max(timeoutS, 1), Number(pending.expires_at));
  let interval = Math.max(parseInt(String(pending.interval ?? "5"), 10), 1);
  for (;;) {
    const [body, headers] = _form({
      grant_type: DEVICE_GRANT,
      device_code: String(pending.device_code),
      client_id: CLIENT_ID,
    });
    const opts = ws.sslOptions();
    const [status, raw] = await http("POST", ws.server + "/token", { data: body, headers, ca: opts?.ca });
    const payload = _json(raw);
    if (status === 200 && "access_token" in payload) {
      stateLock(ws, "token").release();
      _storeTokens(ws, payload, null);
      try { fs.unlinkSync(ws.pendingLoginPath); } catch {}
      return { ok: true, scope: payload.scope ?? "" };
    }
    const error = String(payload.error ?? "");
    if (error === "slow_down") {
      interval += 5;
    } else if (error !== "authorization_pending") {
      try { fs.unlinkSync(ws.pendingLoginPath); } catch {}
      if (status === 404 && !error) {
        throw new ClientError(notOurServer(ws.server, "/token 回 HTTP 404"));
      }
      throw new ClientError(_LOGIN_ERRORS[error] ?? `登录失败（${error || `HTTP ${status}`}）：重新调用 cex_login_start；一直失败就把这段报错发给管理员`);
    }
    if (Date.now() / 1000 + interval > deadline) {
      if (Date.now() / 1000 >= Number(pending.expires_at) - 1) {
        try { fs.unlinkSync(ws.pendingLoginPath); } catch {}
        throw new ClientError(_LOGIN_ERRORS.expired_token);
      }
      return { ok: false, pending: true, next: "The user has not approved yet; call cex_login_wait again." };
    }
    await new Promise((r) => setTimeout(r, interval * 1000));
  }
}

export function loadToken(ws: Workspace): Record<string, unknown> {
  const token = readPrivateJson(ws.tokenPath);
  if (!token || !token.access_token) {
    throw new NotLoggedIn(NOT_LOGGED_IN);
  }
  if (!sameServer(token.server, ws.server)) {
    throw new NotLoggedIn("令牌属于另一个服务端（工作区换过服务端）：重新登录（cex_login_start）");
  }
  return token;
}

async function _refresh(ws: Workspace, stale: Record<string, unknown>): Promise<Record<string, unknown>> {
  const lock = stateLock(ws, "token");
  try {
    const current = readPrivateJson(ws.tokenPath);
    if (!current || !current.access_token || !sameServer(current.server, ws.server)) {
      throw new NotLoggedIn(NOT_LOGGED_IN);
    }
    if (current.access_token !== stale.access_token && Number(current.expires_at ?? 0) >= Date.now() / 1000 + 30) {
      return current;
    }
    const presented = String(current.refresh_token ?? "");
    if (!presented) {
      throw new NotLoggedIn(LOGIN_AGAIN);
    }
    const [body, headers] = _form({ grant_type: "refresh_token", refresh_token: presented, client_id: CLIENT_ID });
    const opts = ws.sslOptions();
    const [status, raw] = await http("POST", ws.server + "/token", { data: body, headers, ca: opts?.ca });
    const payload = _json(raw);
    if (status === 200 && "access_token" in payload) {
      _storeTokens(ws, payload, current);
      return loadToken(ws);
    }
    if (payload.error === "invalid_grant") {
      const latest = readPrivateJson(ws.tokenPath) ?? {};
      if (latest.refresh_token === presented) {
        try { fs.unlinkSync(ws.tokenPath); } catch {}
      }
      throw new NotLoggedIn(LOGIN_AGAIN);
    }
    throw new ClientError(`token refresh failed (HTTP ${status}); the session is kept, try again`);
  } finally {
    lock.release();
  }
}

export { _refresh, http };

export async function request(
  ws: Workspace,
  method: string,
  path: string,
  { data, headers, timeout = 120_000 }: {
    data?: string | Buffer;
    headers?: Record<string, string>;
    timeout?: number;
  } = {},
): Promise<[number, Buffer]> {
  let token = loadToken(ws);
  if (Number(token.expires_at ?? 0) < Date.now() / 1000 + 30) {
    token = await _refresh(ws, token);
  }
  const opts = ws.sslOptions();
  for (let attempt = 0; attempt < 2; attempt++) {
    const authHeaders = { Authorization: `Bearer ${token.access_token}`, ...(headers ?? {}) };
    const [status, raw] = await http(method, ws.server + path, { data, headers: authHeaders, timeout, ca: opts?.ca });
    refuseRedirect(status, "the server");
    if (status !== 401) {
      return [status, raw];
    }
    if (attempt === 0) {
      token = await _refresh(ws, token);
    }
  }
  throw new NotLoggedIn("服务端不认这次登录（令牌被拒）：重新登录（cex_login_start）");
}

export async function requestJson(ws: Workspace, method: string, path: string, kwargs?: {
  data?: string | Buffer;
  headers?: Record<string, string>;
  timeout?: number;
}): Promise<Record<string, unknown>> {
  const [status, raw] = await request(ws, method, path, kwargs);
  const payload = _json(raw);
  if (status >= 400) {
    const detail = payload.detail ?? payload.error ?? `HTTP ${status}`;
    throw new ClientError(`${method} ${path} failed: ${detail}`);
  }
  return payload;
}

export async function logout(ws: Workspace): Promise<Record<string, unknown>> {
  const lock = stateLock(ws, "token");
  try {
    const token = readPrivateJson(ws.tokenPath) ?? {};
    let revoked = false;
    if (token.refresh_token && sameServer(token.server, ws.server)) {
      const [body, headers] = _form({ token: String(token.refresh_token) });
      try {
        const opts = ws.sslOptions();
        const [status] = await http("POST", ws.server + "/revoke", { data: body, headers, ca: opts?.ca });
        revoked = status === 200;
      } catch {
        revoked = false;
      }
    }
    try { fs.unlinkSync(ws.tokenPath); } catch {}
    try { fs.unlinkSync(ws.pendingLoginPath); } catch {}
    return { ok: true, revoked_on_server: revoked };
  } finally {
    lock.release();
  }
}
