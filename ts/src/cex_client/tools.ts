import fs from "node:fs";
import path from "node:path";
import { ClientError } from "./errors.js";
import { Workspace, find, require as requireWorkspace, writePrivateJson, NO_DEVICE_BUILD } from "./workspace.js";
import { loadToken, _form, requestJson, logout as authLogout } from "./auth.js";
import { cachedManifest, sync as bundleSync, entryPath } from "./bundle.js";
import { setup as connectSetup, tlsSummary, chooseBuild, browserCertificateNote } from "./connect.js";
import { submit as deviceSubmit, status as deviceStatus, results as deviceResults } from "./device.js";
import { callTool, lease, leaseArgs, CLIENT_CONFIG_SOURCE } from "./gateway.js";
import { query as manualSearchQuery } from "./manual_search.js";
import { startQrLogin, waitQrLogin, logout as portalLogout } from "./portal.js";
import { getTicket, loginUrl, probeUrl } from "./bugs.js";

export const SPECS_PATH = path.join(__dirname, "tool_specs.json");
export const MAX_CHECK_COMMANDS = 200;

export function loadSpecs(): Record<string, unknown>[] {
  return JSON.parse(fs.readFileSync(SPECS_PATH, "utf8")).tools;
}

function _ws(args: Record<string, unknown>): Workspace {
  const start = args.workspace;
  return requireWorkspace(start ? path.resolve(String(start)) : undefined);
}

function _initRoot(args: Record<string, unknown>): string {
  if (args.workspace) return path.resolve(String(args.workspace));
  const found = find();
  if (found !== null) return found.root;
  const explicit = process.env.CEX_WORKSPACE?.trim();
  return explicit ? path.resolve(explicit) : process.cwd();
}

export async function cexInit(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const root = _initRoot(args);
  const insecure = args.insecure_lan;
  const ws = await connectSetup(root, {
    server: String(args.server ?? ""),
    deviceBuild: String(args.device_build ?? ""),
    channel: String(args.channel ?? ""),
    insecureLan: insecure === undefined || insecure === null ? null : Boolean(insecure),
  });
  const build = ws.selectedBuild;
  const out: Record<string, unknown> = {
    ok: true,
    workspace: ws.root,
    server: ws.server,
    tls: tlsSummary(ws),
    device_build: build || null,
    channel: ws.channel,
  };
  let loggedIn = false;
  try {
    loadToken(ws);
    loggedIn = true;
  } catch {}
  if (loggedIn) {
    out.next = build
      ? "Still logged in. Call cex_sync to fetch compile data."
      : "Still logged in. cex_sync picks the device build when the server publishes only one; otherwise set the user's choice with cex_init device_build.";
  } else {
    out.next = "Call cex_login_start to sign in, then cex_sync to fetch compile data." +
      (build ? "" : " The device build is chosen after login.");
  }
  return out;
}

export async function cexStatus(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = find(args.workspace ? path.resolve(String(args.workspace)) : undefined);
  if (ws === null) {
    return {
      ok: false,
      workspace: null,
      next: "No workspace here; call cex_init with the connection string the administrator gave (https://host:8900#ca=<fingerprint>).",
    };
  }
  const build = ws.selectedBuild;
  const status: Record<string, unknown> = {
    ok: true,
    workspace: ws.root,
    server: ws.server,
    tls: tlsSummary(ws),
    device_build: build || null,
    device_build_selected: Boolean(build),
    channel: ws.channel,
  };
  if (!build) status.device_build_hint = NO_DEVICE_BUILD;
  try {
    const token = loadToken(ws);
    status.logged_in = true;
    status.scope = token.scope ?? "";
  } catch (exc) {
    status.logged_in = false;
    status.login_hint = String(exc);
  }
  const cached = build ? cachedManifest(ws) : null;
  status.bundle = cached ? { bundle_id: cached.bundle_id, created_at: cached.created_at } : null;
  return status;
}

export async function cexLoginStart(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  const { startLogin } = await import("./auth.js");
  const out: Record<string, unknown> = { ok: true, ...(await startLogin(ws)) };
  const note = await browserCertificateNote(ws);
  if (note) {
    out.browser_certificate = note;
    out.next = "Show the user the URL and code, and relay browser_certificate to them word for word before they open the URL: the browser will warn about the certificate, and the note tells them what to check. They sign in with their username and access code in a browser. Then call cex_login_wait.";
  }
  return out;
}

export async function cexLoginWait(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  const { waitLogin } = await import("./auth.js");
  const timeout = Math.min(Math.max(Number(args.timeout_s ?? 60), 1), 300);
  const out = await waitLogin(ws, timeout);
  if (out.ok && !ws.selectedBuild) {
    try {
      Object.assign(out, await chooseBuild(ws));
    } catch (exc) {
      out.device_build_note = `登录成功，但没取到构建列表（${exc}）：稍后调用 cex_sync 会再选一次；也可以用 cex_init 的 device_build 直接指定`;
    }
  }
  return out;
}

export async function cexLogout(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return authLogout(_ws(args));
}

export async function cexSync(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  const channel = String(args.channel ?? "");
  let picked: Record<string, unknown> = {};
  if (!ws.selectedBuild) {
    loadToken(ws);
    picked = await chooseBuild(ws, channel);
    if (!picked.device_build) throw new ClientError(String(picked.device_build_note));
  }
  const out = await bundleSync(ws, channel || undefined);
  if (Object.keys(picked).length) out.device_build_note = picked.device_build_note;
  return out;
}

export async function cexClientConfig(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  const config = await requestJson(ws, "GET", "/v1/config/client");
  writePrivateJson(ws.clientConfigPath, { ...config, [CLIENT_CONFIG_SOURCE]: ws.server });
  return { ok: true, config };
}

export async function cexDocsQuery(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  const query = String(args.q ?? "").trim();
  if (!query) throw new ClientError("q is required");
  let limit = parseInt(String(args.limit ?? "3"), 10);
  if (Number.isNaN(limit)) limit = 3;
  limit = Math.max(1, Math.min(limit, 10));
  const local = manualSearchQuery(ws, query, limit);
  const localResults = ((local.results as Record<string, unknown>[]) ?? []).map((r) => ({ ...r, source: "local_manual" }));
  let serverResults: Record<string, unknown>[] = [];
  let serverSearched = false;
  let serverNote = "";
  try {
    const [body, headers] = _form({ q: query, limit: String(limit) });
    const payload = await requestJson(ws, "POST", "/v1/docs/query", { data: body, headers });
    serverSearched = true;
    for (const row of (payload.results as Record<string, unknown>[]) ?? []) {
      const { ref, ...rest } = row;
      serverResults.push({ ...rest, source: "server_document" });
    }
  } catch (exc) {
    serverNote = `Server documents were not searched: ${exc}`;
  }
  const localAvailable = Boolean(local.manuals_searched);
  const skipped = (local.manuals_skipped as { path: string; reason: string }[]) ?? [];
  let localNote = !localAvailable
    ? String(local.error ?? "No searchable local manuals in this build's bundle; call cex_sync if manuals are expected.")
    : "";
  if (skipped.length) {
    localNote += (localNote ? " " : "") + `Skipped unreadable local manuals: ${skipped.map((r) => r.path).join(", ")}.`;
  }
  const out: Record<string, unknown> = {
    ok: localAvailable || serverSearched,
    query,
    build: ws.selectedBuild || null,
    bundle_id: local.bundle_id,
    manuals_searched: local.manuals_searched ?? 0,
    manuals_skipped: skipped,
    server_searched: serverSearched,
    results: [...localResults.slice(0, limit), ...serverResults.slice(0, limit)],
  };
  if (local.bundle) out.bundle = local.bundle;
  if (localNote) out.local_note = localNote;
  if (serverNote) out.server_note = serverNote;
  if (!out.ok) {
    out.error = `docs query unavailable — ${localNote}; ${serverNote}; this is a supply failure, not evidence that the manual lacks this content`;
    out.next = local.next ?? "Call cex_sync and retry when the server is available.";
  }
  return out;
}

export async function cexCmdCheck(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { loadProjection, resolveVendorCommand } = await import("../cex_core/vendor_cmd.js");
  const ws = _ws(args);
  const commands = args.commands;
  if (!Array.isArray(commands) || !commands.length) {
    throw new ClientError("commands must be a non-empty list of strings");
  }
  if (commands.length > MAX_CHECK_COMMANDS) {
    throw new ClientError(`commands has ${commands.length} entries; at most ${MAX_CHECK_COMMANDS} per call - split the list over several calls`);
  }
  const projectionPath = entryPath(ws, "cmdtree", "vendor_stdlib_");
  if (projectionPath === null) {
    throw new ClientError("no command tree projection in the synced bundle; call cex_sync");
  }
  const projection = loadProjection(projectionPath);
  const results = commands.map((command) => {
    const verdict = resolveVendorCommand(String(command), projection);
    const row: Record<string, unknown> = { command: String(command) };
    for (const k of ["decided", "hit", "head", "src", "origin", "reason_code", "parameter_error"]) {
      if (k in verdict) row[k] = verdict[k];
    }
    return row;
  });
  return { ok: true, projection: path.basename(projectionPath), checked: results.length, all_hit: results.every((r) => r.hit), results };
}

export async function cexScanDestructive(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { scanWorkbook } = await import("../cex_core/scan_destructive.js");
  const ws = _ws(args);
  let xlsx = path.resolve(String(args.xlsx ?? ""));
  if (!path.isAbsolute(xlsx)) xlsx = path.resolve(ws.root, xlsx);
  if (!xlsx.startsWith(path.resolve(ws.root) + path.sep) || !fs.existsSync(xlsx)) {
    throw new ClientError("xlsx must be an existing file inside the workspace");
  }
  const grammar = entryPath(ws, "projections", "domain_grammar");
  if (grammar === null) throw new ClientError("no domain grammar in the synced bundle; call cex_sync");
  const findings = await scanWorkbook(xlsx, grammar);
  return { ok: !findings.length, findings };
}

export async function cexBedLease(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return lease(_ws(args), String(args.action ?? ""));
}

export async function cexEnvPrepare(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  return callTool(ws, "env_prepare", { ...leaseArgs(ws), device_build: ws.deviceBuild });
}

export async function cexCaseSubmit(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return deviceSubmit(_ws(args), String(args.xlsx ?? ""), args.module ? String(args.module) : undefined);
}

export async function cexCaseStatus(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return deviceStatus(_ws(args), String(args.task_id ?? ""));
}

export async function cexCaseResults(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return deviceResults(_ws(args), String(args.task_id ?? ""));
}

export async function cexProbeShow(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  return callTool(ws, "probe_show", {
    ...leaseArgs(ws),
    command: String(args.command ?? ""),
    device_index: parseInt(String(args.device_index ?? "0"), 10),
  });
}

export async function cexInitDevice(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const ws = _ws(args);
  const forwarded: Record<string, unknown> = {};
  for (const k of ["step", "device_index", "device_count", "confirmation"]) {
    if (args[k] !== undefined && args[k] !== null) forwarded[k] = args[k];
  }
  const out = await callTool(ws, "init_device", { ...leaseArgs(ws), ...forwarded });
  if (!out.ok && String(out.error ?? "").includes("jumphost:admin")) {
    out.next = "The session was granted without jumphost:admin. If the user's account has that permission (an administrator grants it on the server), sign in again (cex_logout, then cex_login_start); otherwise device init is not available to this user.";
  }
  return out;
}

export async function cexPortalLoginStart(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return { ok: true, ...(await startQrLogin(loginUrl(_ws(args)))) };
}

export async function cexPortalLoginWait(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const timeout = Math.min(Math.max(Number(args.timeout_s ?? 60), 1), 300);
  return waitQrLogin(probeUrl(_ws(args)), timeout);
}

export async function cexPortalLogout(): Promise<Record<string, unknown>> {
  return portalLogout();
}

export async function cexBugGet(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  return { ok: true, ...(await getTicket(_ws(args), String(args.backend ?? ""), String(args.ticket ?? ""))) };
}

export async function cexRecomposePrepare(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { prepare } = await import("./recompose.js");
  return prepare(_ws(args), String(args.mindmap ?? ""), {
    outName: String(args.out_name ?? ""),
    spec: String(args.spec ?? ""),
  });
}

export async function cexRecomposeSubmitCases(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { submitCases } = await import("./recompose.js");
  return submitCases(_ws(args), String(args.out_name ?? ""), args.cases);
}

export async function cexRecomposeSeal(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { seal } = await import("./recompose.js");
  return seal(_ws(args), String(args.out_name ?? ""));
}

export async function cexLangQuery(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { langQuery } = await import("./recompose.js");
  return langQuery(_ws(args), args, { outName: String(args.out_name ?? "") });
}

export async function cexBedTopology(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { fetch } = await import("./bed.js");
  return fetch(_ws(args), { refresh: Boolean(args.refresh) });
}

export async function cexAuthorPrepare(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { prepare } = await import("./author.js");
  return prepare(_ws(args), String(args.out_name ?? ""));
}

export async function cexCriterionRecord(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { criterionRecord } = await import("./author.js");
  return criterionRecord(_ws(args), String(args.out_name ?? ""), String(args.shape_key ?? ""), args.judgment);
}

export async function cexAuthorSubmitCase(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { submitCase } = await import("./author.js");
  return submitCase(_ws(args), String(args.out_name ?? ""), args.mechanical_case);
}

export async function cexAuthorEmit(args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { emit } = await import("./author.js");
  return emit(_ws(args), String(args.out_name ?? ""));
}

export const TOOLS: Record<string, (args: Record<string, unknown>) => Promise<Record<string, unknown>>> = {
  cex_init: cexInit,
  cex_status: cexStatus,
  cex_login_start: cexLoginStart,
  cex_login_wait: cexLoginWait,
  cex_logout: cexLogout,
  cex_sync: cexSync,
  cex_client_config: cexClientConfig,
  cex_docs_query: cexDocsQuery,
  cex_cmd_check: cexCmdCheck,
  cex_scan_destructive: cexScanDestructive,
  cex_bed_lease: cexBedLease,
  cex_env_prepare: cexEnvPrepare,
  cex_case_submit: cexCaseSubmit,
  cex_case_status: cexCaseStatus,
  cex_case_results: cexCaseResults,
  cex_probe_show: cexProbeShow,
  cex_init_device: cexInitDevice,
  cex_portal_login_start: cexPortalLoginStart,
  cex_portal_login_wait: cexPortalLoginWait,
  cex_portal_logout: cexPortalLogout,
  cex_bug_get: cexBugGet,
  cex_recompose_prepare: cexRecomposePrepare,
  cex_recompose_submit_cases: cexRecomposeSubmitCases,
  cex_recompose_seal: cexRecomposeSeal,
  cex_lang_query: cexLangQuery,
  cex_bed_topology: cexBedTopology,
  cex_author_prepare: cexAuthorPrepare,
  cex_criterion_record: cexCriterionRecord,
  cex_author_submit_case: cexAuthorSubmitCase,
  cex_author_emit: cexAuthorEmit,
};

export async function call(name: string, args: Record<string, unknown> | null): Promise<Record<string, unknown>> {
  const fn = TOOLS[name];
  if (!fn) return { ok: false, error: `unknown tool ${JSON.stringify(name)}` };
  if (args !== null && (typeof args !== "object" || Array.isArray(args))) {
    return { ok: false, error: "arguments must be a JSON object" };
  }
  try {
    return await fn({ ...(args ?? {}) });
  } catch (exc) {
    if (exc instanceof ClientError) return { ok: false, error: exc.message };
    return { ok: false, error: `${exc instanceof Error ? exc.constructor.name : "Error"}: ${exc}` };
  }
}
