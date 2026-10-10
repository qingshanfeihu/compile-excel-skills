import fs from "node:fs";
import path from "node:path";
import { ClientError, NotLoggedIn } from "./errors.js";
import { Workspace, checkServerUrl, readPrivateJson, sameServer, stateLock, writePrivateJson } from "./workspace.js";
import { loadToken, _refresh, http, refuseRedirect } from "./auth.js";

const _SECRET_KEYS = new Set(["token", "fencing_token"]);
export const CLIENT_CONFIG_SOURCE = "_fetched_from";

export function redact(value: unknown): unknown {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (!_SECRET_KEYS.has(k)) out[k] = redact(v);
    }
    return out;
  }
  if (Array.isArray(value)) {
    return value.map(redact);
  }
  return value;
}

export function gatewayUrl(ws: Workspace): string {
  const cfg = ws.config();
  const cached = readPrivateJson(ws.clientConfigPath) ?? {};
  const source = cached[CLIENT_CONFIG_SOURCE];
  if (source !== undefined && !sameServer(source, ws.server)) {
    throw new ClientError("the cached organisation config came from another server; call cex_client_config again");
  }
  const url = String(((cached.gateway as Record<string, unknown> | undefined)?.url) ?? "");
  if (!url) {
    throw new ClientError("no gateway address; call cex_client_config (the server publishes gateway.url)");
  }
  return checkServerUrl(url, { allowInsecureHttp: Boolean(cfg.allow_insecure_http), what: "网关" });
}

export async function callToolRaw(
  ws: Workspace,
  name: string,
  arguments_: Record<string, unknown>,
  timeout = 300_000,
): Promise<Record<string, unknown>> {
  const url = gatewayUrl(ws);
  const body = JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: { name, arguments: arguments_ },
  });
  let token = loadToken(ws);
  if (Number(token.expires_at ?? 0) < Date.now() / 1000 + 30) {
    token = await _refresh(ws, token);
  }
  for (let attempt = 0; attempt < 2; attempt++) {
    const opts = ws.sslOptions();
    const [status, raw] = await http("POST", url, {
      data: body,
      timeout,
      ca: opts?.ca,
      headers: {
        Authorization: `Bearer ${token.access_token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
    });
    refuseRedirect(status, "the gateway");
    if (status === 401 && attempt === 0) {
      token = await _refresh(ws, token);
      continue;
    }
    if (status === 401) {
      throw new NotLoggedIn("the gateway rejected the session; log in again");
    }
    if (status !== 200) {
      throw new ClientError(`gateway returned HTTP ${status}`);
    }
    let reply: Record<string, unknown>;
    try {
      reply = JSON.parse(raw.toString("utf8"));
    } catch {
      throw new ClientError("gateway returned a non-JSON reply");
    }
    if (reply.error) {
      throw new ClientError(`gateway error: ${(reply.error as Record<string, unknown>).message}`);
    }
    const result = (reply.result ?? {}) as Record<string, unknown>;
    let outcome = result.structuredContent;
    if (typeof outcome !== "object" || outcome === null) {
      try {
        outcome = JSON.parse((result.content as unknown[])[0] as string);
      } catch {
        throw new ClientError("gateway reply has no tool result");
      }
    }
    return outcome as Record<string, unknown>;
  }
  throw new ClientError("unreachable");
}

export async function callTool(
  ws: Workspace,
  name: string,
  arguments_: Record<string, unknown>,
  timeout = 300_000,
): Promise<Record<string, unknown>> {
  return redact(await callToolRaw(ws, name, arguments_, timeout)) as Record<string, unknown>;
}

function _leasePath(ws: Workspace): string {
  return ws.leasePath;
}

export function leaseArgs(ws: Workspace): Record<string, unknown> {
  const lease = readPrivateJson(_leasePath(ws));
  if (!lease) {
    throw new ClientError("no bed lease held from this workspace; call cex_bed_lease with action=acquire");
  }
  return { lease_id: lease.lease_id, token: lease.token };
}

export async function lease(ws: Workspace, action: string): Promise<Record<string, unknown>> {
  if (action === "acquire") {
    const out = await callToolRaw(ws, "lease_acquire", {});
    if (out.ok) {
      writePrivateJson(_leasePath(ws), {
        lease_id: out.lease_id,
        token: out.token,
        expires_at: out.expires_at,
      });
    }
    return redact(out) as Record<string, unknown>;
  }
  if (action === "status") {
    return callTool(ws, "lease_status", {});
  }
  if (action === "heartbeat" || action === "release") {
    const out = await callTool(ws, `lease_${action}`, leaseArgs(ws));
    if (action === "release" && out.ok) {
      try { fs.unlinkSync(_leasePath(ws)); } catch {}
    } else if (action === "heartbeat" && out.ok) {
      const current = readPrivateJson(_leasePath(ws)) ?? {};
      writePrivateJson(_leasePath(ws), { ...current, expires_at: out.expires_at });
    }
    return out;
  }
  throw new ClientError("action must be acquire, heartbeat, release or status");
}

function _tasksPath(ws: Workspace): string {
  return path.join(ws.stateDir, "tasks.json");
}

export function rememberTask(ws: Workspace, taskId: string, record: Record<string, unknown>): Record<string, unknown> {
  const lock = stateLock(ws, "tasks");
  try {
    const tasks = readPrivateJson(_tasksPath(ws)) ?? {};
    const seq = 1 + Math.max(0, ...Object.values(tasks).filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null).map((r) => Number(r.seq ?? 0)));
    tasks[taskId] = { ...record, seq };
    writePrivateJson(_tasksPath(ws), tasks);
    return tasks[taskId] as Record<string, unknown>;
  } finally {
    lock.release();
  }
}

export function taskRecord(ws: Workspace, taskId: string): Record<string, unknown> | null {
  const tasks = readPrivateJson(_tasksPath(ws)) ?? {};
  const record = tasks[taskId];
  return typeof record === "object" && record !== null ? record as Record<string, unknown> : null;
}

function _order(record: Record<string, unknown>): [number, string] {
  return [Number(record.seq ?? 0), String(record.submitted_at ?? "")];
}

export function newerSubmissions(ws: Workspace, taskId: string): string[] {
  const tasks = readPrivateJson(_tasksPath(ws)) ?? {};
  const mine = tasks[taskId];
  if (typeof mine !== "object" || mine === null) return [];
  const mineOrder = _order(mine as Record<string, unknown>);
  return Object.entries(tasks)
    .filter(([id, r]) => id !== taskId && typeof r === "object" && r !== null &&
      (r as Record<string, unknown>).xlsx === (mine as Record<string, unknown>).xlsx &&
      _order(r as Record<string, unknown>) > mineOrder)
    .map(([id]) => id);
}
