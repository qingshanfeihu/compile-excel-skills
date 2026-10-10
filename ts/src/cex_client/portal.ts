import fs from "node:fs";
import path from "node:path";
import { ClientError } from "./errors.js";
import { readPrivateJson, writePrivateJson } from "./workspace.js";
import { httpRequest, httpRequestNoRedirect } from "./http.js";
import { restrictDirPrivate } from "../platform/index.js";

export const QR_PATH = "/ueba/openapi/policy/v1/getQrCode";
export const LOGIN_PATH = "/prx/000/http/localhost/login";
export const USER_AGENT = "cex-client/1";
export const TIMEOUT = 20_000;

export class PortalSessionExpired extends ClientError {}

export function cacheDir(): string {
  const base = process.env.XDG_CACHE_HOME ?? path.join(process.env.HOME ?? ".", ".cache");
  const p = path.join(base, "compile-excel");
  fs.mkdirSync(p, { recursive: true });
  restrictDirPrivate(p);
  return p;
}

export function sessionPath(): string {
  return path.join(cacheDir(), "portal-session.json");
}

export function originOf(url: string): string {
  const parts = new URL(url);
  if (parts.protocol !== "https:" && !["127.0.0.1", "localhost"].includes(parts.hostname)) {
    throw new ClientError("portal address must be https");
  }
  return `${parts.protocol}//${parts.host}`;
}

export class PortalSession {
  origin: string;
  cookies: Record<string, string>[];

  constructor(origin: string, cookies: Record<string, string>[] = []) {
    this.origin = origin;
    this.cookies = cookies;
  }

  static load(origin: string): PortalSession {
    const data = readPrivateJson(sessionPath()) ?? {};
    if (data.origin !== origin) return new PortalSession(origin);
    return new PortalSession(origin, (data.cookies as Record<string, string>[]) ?? []);
  }

  save(): void {
    writePrivateJson(sessionPath(), {
      origin: this.origin,
      saved_at: Math.floor(Date.now() / 1000),
      cookies: this.cookies,
    });
  }

  async request(
    method: string,
    url: string,
    { data, headers, follow = false }: {
      data?: string | Buffer;
      headers?: Record<string, string>;
      follow?: boolean;
    } = {},
  ): Promise<[number, Record<string, string>, Buffer]> {
    if (!url.startsWith(this.origin + "/")) {
      throw new ClientError("refusing to send portal cookies to another host");
    }
    const cookieHeader = this.cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    const opts = {
      method,
      headers: { "User-Agent": USER_AGENT, ...(headers ?? {}), ...(cookieHeader ? { Cookie: cookieHeader } : {}) },
      body: data,
      timeoutMs: TIMEOUT,
      maxRedirects: follow ? 5 : 0,
    };
    try {
      const res = follow ? await httpRequest(url, opts) : await httpRequestNoRedirect(url, opts);
      const setCookies = res.headers["set-cookie"];
      if (setCookies) {
        for (const sc of Array.isArray(setCookies) ? setCookies : [setCookies]) {
          const [pair] = String(sc).split(";");
          const [name, value] = pair.split("=", 2);
          if (name && value) {
            this.cookies = this.cookies.filter((c) => c.name !== name);
            this.cookies.push({ name, value });
          }
        }
      }
      return [res.status, res.headers, res.body];
    } catch (e) {
      if (e instanceof ClientError) throw e;
      throw new ClientError(`portal unreachable (${e instanceof Error ? e.constructor.name : String(e)})`);
    }
  }
}

export function isLoginRedirect(status: number, headers: Record<string, string>): boolean {
  if (![301, 302, 303, 307, 308].includes(status)) return false;
  const location = headers.location ?? "";
  return location.toLowerCase().includes("login");
}

export async function loggedIn(session: PortalSession, probeUrl: string): Promise<boolean> {
  const [status, headers] = await session.request("GET", probeUrl);
  return status === 200 && !isLoginRedirect(status, headers);
}

function _pendingPath(): string {
  return path.join(cacheDir(), "portal-login-pending.json");
}

function* _walk(value: unknown): Generator<[string, unknown]> {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      yield [key, item];
      yield* _walk(item);
    }
  } else if (Array.isArray(value)) {
    for (const item of value) yield* _walk(item);
  }
}

export async function startQrLogin(loginUrl: string): Promise<Record<string, unknown>> {
  const origin = originOf(loginUrl);
  const session = new PortalSession(origin);
  const [status] = await session.request("GET", loginUrl, { follow: true });
  if (status >= 400) {
    throw new ClientError(`portal login page returned HTTP ${status}`);
  }
  const loginUuid = crypto.randomUUID();
  const [status2, headers, body] = await session.request(
    "GET", `${origin}${QR_PATH}?uuid=${encodeURIComponent(loginUuid)}`);
  if (status2 !== 200 || !body.length) {
    throw new ClientError(`QR code request returned HTTP ${status2}`);
  }
  const contentType = headers["content-type"] ?? "";
  let image = body;
  if (contentType.toLowerCase().includes("json")) {
    try {
      const payload = JSON.parse(body.toString("utf8"));
      const encoded = [..._walk(payload)].find(([, v]) => typeof v === "string" && v.length > 100)?.[1] as string;
      image = Buffer.from(encoded.split(",", 2)[1] ?? encoded, "base64");
    } catch {
      throw new ClientError("QR code response is JSON without an image");
    }
  }
  const qrFile = path.join(cacheDir(), "portal-qr.png");
  fs.writeFileSync(qrFile, image, { mode: 0o600 });
  writePrivateJson(_pendingPath(), {
    origin,
    uuid: loginUuid,
    cookies: session.cookies,
    started_at: Math.floor(Date.now() / 1000),
  });
  return {
    qr_image: qrFile,
    expires_in: 300,
    next: "Ask the user to open the QR image and scan it with the company app, then call cex_portal_login_wait.",
  };
}

export async function waitQrLogin(
  probeUrl: string,
  timeoutS = 60,
  intervalS = 3,
): Promise<Record<string, unknown>> {
  const pending = readPrivateJson(_pendingPath());
  if (!pending) {
    throw new ClientError("no portal login in progress; call cex_portal_login_start");
  }
  if (Date.now() / 1000 - Number(pending.started_at) > 300) {
    try { fs.unlinkSync(_pendingPath()); } catch {}
    throw new ClientError("the QR code expired; call cex_portal_login_start again");
  }
  const session = new PortalSession(
    String(pending.origin),
    (pending.cookies as Record<string, string>[]) ?? [],
  );
  const form = new URLSearchParams({ method: "twodimension", uuid: String(pending.uuid), submit: "true" }).toString();
  const deadline = Date.now() / 1000 + Math.max(timeoutS, 1);
  for (;;) {
    await session.request("POST", String(pending.origin) + LOGIN_PATH, {
      data: form,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    if (await loggedIn(session, probeUrl)) {
      session.save();
      try { fs.unlinkSync(_pendingPath()); } catch {}
      return { ok: true, logged_in: true };
    }
    if (Date.now() / 1000 + intervalS > deadline) {
      writePrivateJson(_pendingPath(), { ...pending, cookies: session.cookies });
      return { ok: false, pending: true, next: "The user has not scanned yet; call cex_portal_login_wait again." };
    }
    await new Promise((r) => setTimeout(r, intervalS * 1000));
  }
}

export function logout(): Record<string, unknown> {
  const removed = fs.existsSync(sessionPath());
  try { fs.unlinkSync(sessionPath()); } catch {}
  try { fs.unlinkSync(_pendingPath()); } catch {}
  try { fs.unlinkSync(path.join(cacheDir(), "portal-qr.png")); } catch {}
  return { ok: true, session_removed: removed };
}
