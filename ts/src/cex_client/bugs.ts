import fs from "node:fs";
import path from "node:path";
import { ClientError } from "./errors.js";
import { Workspace, readPrivateJson, safeComponent, writeFileSafely } from "./workspace.js";
import { originOf, PortalSession, PortalSessionExpired, isLoginRedirect } from "./portal.js";
import { withLock } from "../platform/index.js";

export const MIN_INTERVAL_S = 1.0;

function _config(ws: Workspace): Record<string, unknown> {
  const cached = readPrivateJson(ws.clientConfigPath);
  if (!cached) {
    throw new ClientError("no organisation config cached; call cex_client_config first");
  }
  return cached;
}

export function detailUrl(ws: Workspace, backend: string, number: string): string {
  const cfg = _config(ws);
  const defects = (cfg.defects ?? {}) as Record<string, Record<string, unknown>>;
  if (backend === "bugzilla") {
    const base = defects.bugzilla?.proxy_url;
    if (!base) throw new ClientError("the server publishes no defects.bugzilla.proxy_url");
    return `${String(base).replace(/\/+$/, "")}/show_bug.cgi?id=${number}`;
  }
  if (backend === "zentao" || backend === "zentao_story") {
    const base = defects.zentao?.base_url;
    if (!base) throw new ClientError("the server publishes no defects.zentao.base_url");
    const view = backend === "zentao_story" ? "story-view" : "bug-view";
    return `${String(base).replace(/\/+$/, "")}/${view}-${number}.html`;
  }
  throw new ClientError("backend must be bugzilla, zentao or zentao_story");
}

export function probeUrl(ws: Workspace): string {
  const defects = (_config(ws).defects ?? {}) as Record<string, Record<string, unknown>>;
  const base = defects.bugzilla?.proxy_url;
  if (!base) throw new ClientError("the server publishes no defects.bugzilla.proxy_url to verify login");
  return String(base).replace(/\/+$/, "") + "/";
}

export function loginUrl(ws: Workspace): string {
  const url = (_config(ws).portal as Record<string, unknown> | undefined)?.login_url;
  if (!url) throw new ClientError("the server publishes no portal.login_url");
  return String(url);
}

function _cacheDir(): string {
  return path.join(process.env.APPDATA ?? process.env.HOME ?? ".", "cex_portal");
}

async function _throttledFetch(session: PortalSession, url: string): Promise<[number, Record<string, string>, Buffer]> {
  const lockPath = path.join(_cacheDir(), "portal.lock");
  return withLock(lockPath, async () => {
    let last = 0;
    try {
      last = parseFloat(fs.readFileSync(lockPath, "utf8").trim() || "0");
    } catch {}
    const wait = MIN_INTERVAL_S - (Date.now() / 1000 - last);
    if (wait > 0) {
      await new Promise((r) => setTimeout(r, wait * 1000));
    }
    try {
      return await session.request("GET", url);
    } finally {
      fs.writeFileSync(lockPath, String(Date.now() / 1000), "utf8");
    }
  });
}

export async function getTicket(ws: Workspace, backend: string, ticket: string): Promise<Record<string, unknown>> {
  const { DefectParseError, canonical_ticket, parse_ticket_html } = await import("../cex_core/defects/parse.js");
  const backend_ = (backend ?? "").trim().toLowerCase();
  let canonical: string;
  try {
    canonical = canonical_ticket(backend_, ticket);
  } catch (e: unknown) {
    if (e instanceof DefectParseError) throw new ClientError(`invalid ticket id: ${(e as Error).message}`);
    throw e;
  }
  const number = canonical.split("-", 2)[1];
  const url = detailUrl(ws, backend_, number);
  const origin = originOf(url);
  if (origin !== originOf(loginUrl(ws))) {
    throw new ClientError("defect tracker must be reached through the portal host");
  }
  const session = PortalSession.load(origin);
  const [status, headers, body] = await _throttledFetch(session, url);
  if (isLoginRedirect(status, headers)) {
    throw new PortalSessionExpired("portal session expired or missing; call cex_portal_login_start and scan again");
  }
  if (status !== 200) {
    throw new ClientError(`defect page returned HTTP ${status}`);
  }
  let parsed: Record<string, unknown>;
  try {
    parsed = parse_ticket_html(backend_, canonical, body);
  } catch (e: unknown) {
    if (e instanceof DefectParseError) throw new ClientError(`defect page could not be used: ${(e as Error).message}`);
    throw e;
  }
  const target = path.join(ws.root, "defects", safeComponent(backend_, "backend"), `${safeComponent(canonical, "ticket")}.json`);
  writeFileSafely(ws.root, target, JSON.stringify(parsed, null, 1));
  return {
    ticket: parsed,
    saved: path.relative(ws.root, target),
    source: new URL(url).pathname,
  };
}
