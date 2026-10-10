import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ClientError } from "./errors.js";
import { Workspace, writeFileSafely } from "./workspace.js";
import { callTool, leaseArgs } from "./gateway.js";
import { topologyPath, prepare } from "./engine_env.js";

const _PROTOCOLS = new Set(["http", "https", "tcp", "udp", "dns"]);
const _ENGINE_REPORT_TOOL = /用\s*compile_report_underdetermined\s*如实呈报\(obstacle=([^)]*)\)/g;
const _ENGINE_TOOL_NAME = /compile_report_underdetermined/g;

export function servicesPath(ws: Workspace): string {
  return path.join(path.dirname(topologyPath(ws)), "services.json");
}

function _write(ws: Workspace, p: string, data: Buffer | string): void {
  writeFileSafely(ws.root, p, data);
}

export function normalizeServices(raw: unknown): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  if (!Array.isArray(raw)) return out;
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const i = item as Record<string, unknown>;
    const proto = String(i.proto ?? "").trim().toLowerCase();
    const ip = String(i.ip ?? "").trim();
    const port = Number(i.port);
    if (!_PROTOCOLS.has(proto) || !ip || !Number.isInteger(port) || port <= 0 || port >= 65536) continue;
    out.push({
      host: String(i.host ?? "").trim(),
      ip,
      proto,
      port,
      note: String(i.note ?? "").trim(),
    });
  }
  return out;
}

export function clientSummary(text: string): string {
  return text
    .replace(_ENGINE_REPORT_TOOL, (_, obstacle) => `把这一缺口如实告诉用户（${obstacle}），由用户补充床事实或调整用例`)
    .replace(_ENGINE_TOOL_NAME, "向用户如实报告缺口");
}

function _servicesLines(services: Record<string, unknown>[]): string[] {
  if (!services.length) return [];
  const lines = ["本床服务清单(后端按服务选:协议与端口对得上的那一条,不要只挑一个裸 IP):"];
  for (const row of services) {
    const note = row.note ? `  (${row.note})` : "";
    lines.push(`  ${row.host || "-"} ${row.ip} ${row.proto}/${row.port}${note}`);
  }
  return lines;
}

export async function factsView(
  topology: Record<string, unknown>,
  services: Record<string, unknown>[] = [],
): Promise<Record<string, unknown>> {
  const { EnvFacts } = await import("../cex_core/engine/ist_core/tools/_shared/env_facts.js");
  const facts = new EnvFacts(topology);
  const summary = clientSummary(facts.summary_for_agent());
  const extra = _servicesLines(services);
  return {
    services,
    listener_ips: facts.listener_ips(),
    service_ips: facts.service_ips(),
    listener_trigger_pairs: facts.listener_trigger_pairs().map(([ip, hosts]: [string, string[]]) => ({
      target: ip,
      trigger_hosts: hosts,
    })),
    summary: summary + (extra.length ? "\n" + extra.join("\n") : ""),
  };
}

export async function fetch(ws: Workspace, { refresh = false }: { refresh?: boolean } = {}): Promise<Record<string, unknown>> {
  const out = await callTool(ws, "bed_topology", { ...leaseArgs(ws), refresh: Boolean(refresh) });
  if (!out.ok) return out;
  const topology = out.topology;
  if (typeof topology !== "object" || topology === null) {
    throw new ClientError("the gateway returned no topology");
  }
  const raw = JSON.stringify(topology, null, 2) + "\n";
  if (crypto.createHash("sha256").update(raw, "utf8").digest("hex") !== out.sha256) {
    throw new ClientError("the bed topology does not match the digest the gateway sent");
  }
  const services = normalizeServices(out.services);
  const p = topologyPath(ws);
  _write(ws, p, raw);
  _write(ws, path.join(path.dirname(p), "network_topology_rag.md"), String(out.rag_md ?? ""));
  _write(ws, servicesPath(ws), JSON.stringify(services, null, 1) + "\n");
  prepare(ws);
  return {
    ok: true,
    sha256: out.sha256,
    path: p,
    bed: (topology as Record<string, unknown>)._bed,
    observation: out.observation,
    ...(await factsView(topology as Record<string, unknown>, services)),
  };
}

export function load(ws: Workspace): Record<string, unknown> | null {
  const p = topologyPath(ws);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export function loadServices(ws: Workspace): Record<string, unknown>[] {
  try {
    return normalizeServices(JSON.parse(fs.readFileSync(servicesPath(ws), "utf8")));
  } catch {
    return [];
  }
}
