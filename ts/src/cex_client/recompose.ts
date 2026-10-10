import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { ClientError } from "./errors.js";
import { Workspace, readPrivateJson, safeComponent, stateLock, toStatePath, writeFileSafely, writePrivateJson } from "./workspace.js";
import { prepare as engineEnvPrepare } from "./engine_env.js";
import { P } from "../cex_core/engine/_py.js";

export const STATE_SCHEMA = "cex.recompose-dispatch/v1";
export const DEFECT_CHANNEL_ABSENT = "client_has_no_defect_spec_channel";
const _STRIP = "\ufeff\uffff";
const _SPEC_STATUS_SCHEMA = "ist.governing-spec-status";
const _DEFECT_STATUS_SCHEMA = "ist.defect-spec-status";

const _CLIENT_TOOL_NAMES: [string, string][] = [
  ["submit_machine_mindmap_cases", "cex_recompose_submit_cases"],
  ["submit_machine_mindmap", "cex_recompose_seal"],
];
const _ENGINE_SELF_SEAL = "Every case assigned to this dispatch is recorded. Do not call submit_machine_mindmap";

function _statePath(ws: Workspace, outName: string): string {
  return path.join(ws.stateDir, "recompose", `${safeComponent(outName, "batch name")}.json`);
}

export function defaultBatchName(stem: string): string {
  const text = String(stem ?? "").trim();
  try {
    return safeComponent(text, "batch name");
  } catch {}
  let asciiPart = text.replace(/[^A-Za-z0-9._-]+/g, "-");
  asciiPart = asciiPart.replace(/\.{2,}/g, ".").replace(/-{2,}/g, "-").replace(/^[-._]+|[-._]+$/g, "");
  const digest = crypto.createHash("sha256").update(text, "utf8").digest("hex").slice(0, 8);
  return safeComponent(asciiPart ? `${asciiPart.slice(0, 48).replace(/[-._]+$/, "")}-${digest}` : `batch-${digest}`, "batch name");
}

export function clientWording(value: unknown): unknown {
  if (typeof value === "string") {
    let s = value;
    if (s.startsWith(_ENGINE_SELF_SEAL)) {
      return "Every case of this batch is recorded; call cex_recompose_seal now. Further cex_recompose_submit_cases calls are rejected.";
    }
    for (const [engineName, clientName] of _CLIENT_TOOL_NAMES) {
      s = s.replace(new RegExp(`\\b${engineName}\\b`, "g"), clientName);
    }
    return s;
  }
  if (Array.isArray(value)) return value.map(clientWording);
  if (typeof value === "object" && value !== null) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = clientWording(v);
    return out;
  }
  return value;
}

export function _loadState(ws: Workspace, outName: string): Record<string, unknown> {
  const state = readPrivateJson(_statePath(ws, outName));
  if (!state || state.schema !== STATE_SCHEMA) {
    throw new ClientError(`no recompose dispatch for ${JSON.stringify(outName)}; call cex_recompose_prepare`);
  }
  return state;
}

function _mindmapFile(ws: Workspace, mindmap: string): string {
  let p = path.resolve(String(mindmap ?? ""));
  if (!path.isAbsolute(p)) p = path.resolve(ws.root, p);
  if (!p.startsWith(path.resolve(ws.root) + path.sep) || !fs.existsSync(p)) {
    throw new ClientError("mindmap must be an existing file inside the workspace");
  }
  return p;
}

function _rootTitles(text: string): string[] {
  let roots: unknown;
  try {
    roots = JSON.parse(text.replace(new RegExp(`^[${_STRIP}]+`), ""));
  } catch (exc) {
    throw new ClientError(`the mindmap is not an XMind JSON export: ${exc}`);
  }
  if (typeof roots === "object" && roots !== null && !Array.isArray(roots)) roots = [roots];
  const titles: string[] = [];
  for (const root of Array.isArray(roots) ? roots : []) {
    if (typeof root !== "object" || root === null) continue;
    const data = typeof (root as Record<string, unknown>).data === "object" ? (root as Record<string, unknown>).data as Record<string, unknown> : {};
    const title = String(data.text ?? (root as Record<string, unknown>).text ?? "").trim();
    if (title && !titles.includes(title)) titles.push(title);
  }
  return titles;
}

async function _governingSpec(root: string, batch: string, outName: string, title: string, pin: string, declined: boolean): Promise<Record<string, unknown>> {
  const { build_spec_references } = await import("../cex_core/engine/ist_core/compile_engine/spec_references.js");
  const { load_index, locate_spec, resolve_indexed_spec } = await import("../cex_core/engine/kms/spec_index.js");
  const { SpecGenerationUnavailable, resolve_active_spec_generation } = await import("../cex_core/engine/knowledge_paths.js");

  let active: Record<string, unknown> | null = null;
  try {
    active = resolve_active_spec_generation(root) as unknown as Record<string, unknown>;
  } catch (e) {
    if (e instanceof SpecGenerationUnavailable) active = null;
    else throw e;
  }

  const _locate = (): [Record<string, unknown> | null, [string, string] | null] => {
    if (active === null) return [null, ["unavailable", "governing spec generation is unavailable"]];
    let index: unknown;
    try {
      index = load_index(active.index as string);
    } catch (e) {
      if (e instanceof SpecGenerationUnavailable) return [null, ["unavailable", "governing spec generation is unavailable"]];
      throw e;
    }
    if (typeof index !== "object" || index === null) return [null, ["invalid_source", "governing spec index is invalid"]];
    let raw: unknown;
    try {
      raw = locate_spec(index, title, undefined, false);
    } catch {
      raw = null;
    }
    if (typeof raw !== "object" || raw === null) return [null, ["invalid_source", "governing spec lookup is invalid"]];
    return [raw as Record<string, unknown>, null];
  };

  let locator: Record<string, unknown> | null = { status: "no_governing_spec", matches: [], channel: null };
  let lookupUnknown: [string, string] | null = null;
  if (!declined) {
    [locator, lookupUnknown] = _locate();
    if (lookupUnknown !== null && active !== null) {
      [locator, lookupUnknown] = _locate();
    }
  }
  let forced = declined ? "user_declined_retry" : lookupUnknown !== null ? "auto_retry_exhausted" : "";
  if (forced || locator === null) {
    locator = { status: "no_governing_spec", matches: [], channel: null, resolution: forced, raw_status: lookupUnknown?.[0] ?? null };
  }
  let pinEvidence = "";
  if (pin) {
    pinEvidence = `explicit_user_pin;locator=${locator.status}:${locator.channel}`;
    locator = { status: "matched", channel: "explicit_pin", matches: [{ file: pin, title: "", evidence: pinEvidence }] };
  }

  let matches = (locator.matches as unknown[]) ?? [];
  let status = String(locator.status ?? "");
  let candidates: Record<string, unknown>[] = [];
  if (status === "candidates") {
    candidates = matches.filter((m): m is Record<string, unknown> => typeof m === "object" && m !== null);
    matches = [];
    status = "ambiguous";
  } else if (status === "no_governing_spec") {
    if (matches.length !== 0 || (locator.channel !== null && !forced)) {
      throw new ClientError("governing spec absence receipt is malformed");
    }
  } else if (status !== "matched") {
    lookupUnknown = lookupUnknown ?? ["invalid_source", "governing spec lookup status is unknown"];
    forced = forced || "auto_retry_exhausted";
    status = "no_governing_spec";
    matches = [];
  }
  const unique = status === "matched" && Array.isArray(matches) && matches.length === 1 &&
    typeof matches[0] === "object" && matches[0] !== null &&
    Boolean(String((matches[0] as Record<string, unknown>).file ?? "").trim());
  if (status === "matched" && !unique) {
    lookupUnknown = lookupUnknown ?? ["invalid_source", "governing spec matched receipt is malformed"];
    forced = forced || "auto_retry_exhausted";
    status = "no_governing_spec";
    matches = [];
  }
  const name = unique ? String((matches[0] as Record<string, unknown>).file ?? "").trim() : "";
  const resolved = name ? resolve_indexed_spec(root, name) : null;
  if (name && (resolved === null || active === null || resolved.generation_id !== active.generation_id || resolved.manifest_sha256 !== active.manifest_sha256)) {
    if (pinEvidence) {
      throw new ClientError(`spec ${JSON.stringify(name)} is not in the synced spec generation; pick one of the candidates or pass spec='none'`);
    }
    lookupUnknown = lookupUnknown ?? ["invalid_source", "matched governing spec identity drift"];
    forced = forced || "auto_retry_exhausted";
    status = "no_governing_spec";
  }
  if (resolved !== null) {
    const specStatus: Record<string, unknown> = {
      schema: _SPEC_STATUS_SCHEMA,
      status: "bound",
      name,
      sha256: resolved.sha256,
      size: resolved.size,
      generation_id: resolved.generation_id,
      manifest_sha256: resolved.manifest_sha256,
      locator_channel: locator.channel,
    };
    if (pinEvidence) {
      specStatus.pinned_by_user = true;
      specStatus.pin_evidence = pinEvidence;
    }
    return specStatus;
  }
  const specStatus: Record<string, unknown> = {
    schema: _SPEC_STATUS_SCHEMA,
    status: status === "ambiguous" ? "ambiguous" : "no_governing_spec",
    name: null,
    locator_status: status,
    resolution: forced || null,
    unresolved_reason: lookupUnknown?.[1] ?? null,
    locator_channel: locator.channel,
    generation_id: active?.generation_id ?? null,
    manifest_sha256: active?.manifest_sha256 ?? null,
  };
  if (status === "ambiguous") {
    specStatus.references = build_spec_references(new P(root), new P(batch), outName, candidates).references;
  }
  return specStatus;
}

function _ticketIds(title: string): Set<string> {
  const text = String(title ?? "");
  const match = text.match(/^\s*(?:BUG\s*[-#：:]?\s*)?(\d{4,})(?!\d)/i);
  if (match) return new Set([match[1]]);
  const out = new Set<string>();
  for (const m of text.matchAll(/(?<!\d)(\d{4,})(?!\d)/g)) {
    const start = Math.max(0, m.index! - 5);
    const end = Math.min(text.length, m.index! + m[0].length + 5);
    if (!/^\d+\.\d+/.test(text.slice(start, end))) out.add(m[1]);
  }
  return out;
}

function _defectSpec(specStatus: Record<string, unknown>, title: string, declined: boolean): Record<string, unknown> {
  const notQueried = (reason: string) => ({
    schema: _DEFECT_STATUS_SCHEMA,
    status: "not_queried",
    ticket_number: null,
    eligible: false,
    receipt_sha256: null,
    receipt: null,
    reason,
  });
  const resolvedAbsent = (reason: string, rawStatus = "", unresolved = "") => ({
    schema: _DEFECT_STATUS_SCHEMA,
    status: "resolved_absent",
    raw_status: rawStatus || null,
    ticket_number: null,
    eligible: false,
    receipt_sha256: null,
    receipt: null,
    reason,
    unresolved: unresolved || null,
  });

  if (specStatus.status === "bound") return notQueried("openkm_found");
  if (specStatus.status === "ambiguous") return notQueried("openkm_ambiguous");
  if (declined) return resolvedAbsent("user_declined_retry");
  const ids = _ticketIds(title);
  if (!ids.size) return { schema: _DEFECT_STATUS_SCHEMA, status: "no_ticket_reference", ticket_number: null, receipt_sha256: null, receipt: null };
  const [raw, reason] = ids.size === 1
    ? ["unavailable", DEFECT_CHANNEL_ABSENT]
    : ["invalid_source", "bug_to_case_root_identity_is_not_unique"];
  return resolvedAbsent("auto_retry_exhausted", raw, `status=${raw}, reason=${reason}`);
}

function _binding(source: string, specStatus: Record<string, unknown>, defect: Record<string, unknown>): Record<string, unknown> {
  return {
    source,
    governing_spec: specStatus.status === "bound" ? specStatus.name : null,
    governing_spec_status: specStatus.status,
    governing_spec_sha256: specStatus.sha256,
    governing_spec_generation_id: specStatus.generation_id,
    governing_spec_manifest_sha256: specStatus.manifest_sha256,
    defect_spec_status: defect.status,
    defect_spec_receipt_sha256: defect.receipt_sha256,
  };
}

function _specView(specStatus: Record<string, unknown>, root: string, batch: string): Record<string, unknown> {
  const view: Record<string, unknown> = {};
  for (const k of ["status", "name", "sha256", "locator_channel", "resolution", "unresolved_reason"]) {
    if (specStatus[k] !== undefined && specStatus[k] !== null) view[k] = specStatus[k];
  }
  if (specStatus.status === "bound") {
    view.path = path.join(root, "knowledge", "data", "spec", "generations", String(specStatus.generation_id), "docs", String(specStatus.name));
  }
  const references = [];
  for (const ref of (specStatus.references as Record<string, unknown>[]) ?? []) {
    references.push({
      name: ref.name,
      anchor: ref.anchor,
      evidence: ref.evidence,
      path: path.join(batch, "spec_references", String(ref.name)),
    });
  }
  if (references.length) view.references = references;
  return view;
}

export async function prepare(ws: Workspace, mindmap: string, { outName = "", spec = "" }: { outName?: string; spec?: string } = {}): Promise<Record<string, unknown>> {
  const [root, info] = engineEnvPrepare(ws);
  const { write_json_atomic: writeJsonAtomic } = await import("../cex_core/engine/case_compiler/contract_entry.js");
  const { closed_mindmap_case_autoids, consistency_source_atoms_for_brief } = await import("../cex_core/engine/case_compiler/mindmap_contract_projector.js");
  const { initialize_machine_mindmap_submission } = await import("../cex_core/engine/ist_core/tools/device/recompose_submission.js");

  const sourceFile = _mindmapFile(ws, mindmap);
  const raw = fs.readFileSync(sourceFile);
  let text: string;
  try {
    text = raw.toString("utf8");
  } catch {
    throw new ClientError("the mindmap is not UTF-8");
  }
  const titles = _rootTitles(text);
  if (titles.length !== 1) {
    throw new ClientError(`the mindmap must have exactly one root title (found ${titles.length})`);
  }
  const name = outName ? safeComponent(outName, "batch name") : defaultBatchName(path.basename(sourceFile, path.extname(sourceFile)));
  const outputs = ws.outputsDir;
  const batch = path.join(outputs, name);
  fs.mkdirSync(batch, { recursive: true });
  const pin = String(spec ?? "").trim();
  const declined = pin.toLowerCase() === "none";
  const specStatus = await _governingSpec(root, batch, name, titles[0], declined ? "" : pin, declined);
  const defect = _defectSpec(specStatus, titles[0], declined);
  const snapshot = path.join(batch, "mindmap_source.json");
  if (!fs.existsSync(snapshot) || fs.lstatSync(snapshot).isSymbolicLink() || !fs.readFileSync(snapshot).equals(raw)) {
    writeFileSafely(ws.root, snapshot, raw);
  }
  writeJsonAtomic(path.join(batch, "governing_spec_status.json"), specStatus);
  writeJsonAtomic(path.join(batch, "defect_spec_status.json"), defect);
  const sourceSha = crypto.createHash("sha256").update(raw).digest("hex");
  const binding = _binding(path.relative(ws.root, snapshot).split(path.sep).join("/"), specStatus, defect);
  const autoids = closed_mindmap_case_autoids(text.replace(new RegExp(`^[${_STRIP}]+`), ""));
  const wasSealed = _isSealed(batch);
  const dispatchId = crypto.randomUUID().replace(/-/g, "");
  const [, already] = initialize_machine_mindmap_submission(outputs, name, dispatchId, {
    binding,
    case_autoids: autoids,
    source_sha256: sourceSha,
  });
  const lock = stateLock(ws, "recompose", name);
  try {
    writePrivateJson(_statePath(ws, name), {
      schema: STATE_SCHEMA,
      out_name: name,
      dispatch_id: dispatchId,
      source_sha256: sourceSha,
      binding,
      data_root: toStatePath(ws, root),
      bundle_id: info.bundle_id,
    });
  } finally {
    lock.release();
  }
  const remaining = autoids.filter((aid: string) => !already.includes(aid));
  const result: Record<string, unknown> = {
    ok: true,
    out_name: name,
    mindmap_snapshot: snapshot,
    root_title: titles[0],
    build: info.build,
    case_count: autoids.length,
    case_autoids: autoids,
    already_recorded: already,
    outstanding_autoids: remaining,
    governing_spec: _specView(specStatus, root, batch),
    defect_spec_status: defect.status,
    defect_spec_receipt_sha256: defect.receipt_sha256,
    consistency_source_atoms: consistency_source_atoms_for_brief(text.replace(new RegExp(`^[${_STRIP}]+`), "")),
    spec_bundle: info.spec,
    next: "Recompose the outstanding cases and record them with cex_recompose_submit_cases as you finish them; then call cex_recompose_seal.",
  };
  if (wasSealed) {
    const authoring = fs.existsSync(path.join(ws.stateDir, "author", `${name}.json`));
    result.reopened_seal = true;
    result.warning = "This batch was sealed. Preparing it again reopened it and removed the sealed machine_mindmap.json; recorded cases stay recorded. Seal it again with cex_recompose_seal before any cex_author_* call" +
      (authoring ? "; authoring has started on this batch, so re-run cex_author_prepare after sealing (authoring refuses to continue on an unsealed batch)" : "") + ".";
    if (!remaining.length) result.next = "Every case is already recorded: call cex_recompose_seal now.";
  }
  if (!outName) {
    result.note = `out_name defaulted to ${JSON.stringify(name)}; pass out_name=${JSON.stringify(name)} to every later cex_recompose_* / cex_author_* call for this batch`;
  }
  if (defect.unresolved) {
    result.defect_spec_note = "The root title names a ticket, but this client cannot bind a DefectSpec projection; the status is resolved_absent. cex_bug_get can read the ticket for discovery only - it never becomes a contract source.";
  }
  return result;
}

function _isSealed(batch: string): boolean {
  try {
    const receipt = JSON.parse(fs.readFileSync(path.join(batch, ".machine_mindmap_submission.json"), "utf8"));
    return receipt.status === "submitted" && fs.existsSync(path.join(batch, "machine_mindmap.json"));
  } catch {
    return false;
  }
}

async function _scope(ws: Workspace, outName: string): Promise<[Record<string, unknown>, <T>(fn: () => T) => T, string]> {
  const state = _loadState(ws, outName);
  const [root] = engineEnvPrepare(ws, { pinned: state.data_root });
  const { recompose_dispatch_scope } = await import("../cex_core/engine/ist_core/tools/device/recompose_submission.js");
  const scope = <T,>(fn: () => T): T => recompose_dispatch_scope(ws.outputsDir, String(state.out_name), String(state.dispatch_id), fn);
  return [state, scope, root];
}

export async function submitCases(ws: Workspace, outName: string, cases: unknown): Promise<Record<string, unknown>> {
  const [, scope] = await _scope(ws, outName);
  const { submit_machine_mindmap_cases } = await import("../cex_core/engine/ist_core/tools/device/recompose_submit_tool.js");
  const raw = await scope(() => submit_machine_mindmap_cases(cases));
  try {
    const result = JSON.parse(String(raw));
    return { ok: result.status !== "rejected", ...(clientWording(result) as Record<string, unknown>) };
  } catch {
    return { ok: false, status: "rejected", detail: clientWording(String(raw).slice(0, 4000)) };
  }
}

export async function seal(ws: Workspace, outName: string): Promise<Record<string, unknown>> {
  const [state, , root] = await _scope(ws, outName);
  const { fill_mechanical_fields } = await import("../cex_core/engine/case_compiler/mindmap_contract_projector.js");
  const { read_machine_mindmap_parts } = await import("../cex_core/engine/ist_core/tools/device/recompose_parts.js");
  const { machine_mindmap_artifact_path, submit_machine_mindmap_payload, verify_machine_mindmap_submission_commit } = await import("../cex_core/engine/ist_core/tools/device/recompose_submission.js");

  const outputs = ws.outputsDir;
  const name = String(state.out_name);
  const dispatchId = String(state.dispatch_id);
  const binding = state.binding as Record<string, unknown>;
  const text = fs.readFileSync(path.join(outputs, name, "mindmap_source.json"), "utf8");
  const snapshot = read_machine_mindmap_parts(outputs, name, { binding_sha256: null, source_sha256: state.source_sha256 as string | null });
  const doc = { cases: snapshot.case_autoids.filter((aid: string) => aid in snapshot.cases).map((aid: string) => ({ ...snapshot.cases[aid] })) };
  fill_mechanical_fields(doc, text.replace(new RegExp(`^[${_STRIP}]+`), ""));
  submit_machine_mindmap_payload(outputs, name, dispatchId, {
    schema: "ist.machine-mindmap",
    source: binding.source,
    governing_spec: binding.governing_spec,
    defect_spec_status: binding.defect_spec_status,
    defect_spec_receipt_sha256: binding.defect_spec_receipt_sha256,
    cases: doc.cases,
    case_count: doc.cases.length,
  });
  verify_machine_mindmap_submission_commit(outputs, name, dispatchId, { expected_binding: binding });
  const sealed = doc.cases.map((c: Record<string, unknown>) => String(c.autoid ?? ""));
  const missing = snapshot.case_autoids.filter((aid: string) => !sealed.includes(aid));
  return {
    ok: true,
    artifact: machine_mindmap_artifact_path(outputs, name),
    case_count: snapshot.case_autoids.length,
    sealed_case_count: sealed.length,
    missing_autoids: missing,
    note: missing.length ? "Cases missing from the ledger fall back to the author's original text in the sealed mindmap." : "",
  };
}

export async function langQuery(ws: Workspace, args: Record<string, unknown>, { outName = "" }: { outName?: string } = {}): Promise<Record<string, unknown>> {
  let scope: (<T>(fn: () => T) => T) | null = null;
  let note: string | null = null;
  let root: string;
  if (outName) {
    const state = _loadState(ws, outName);
    if (_isSealed(path.join(ws.outputsDir, String(state.out_name)))) {
      [root] = engineEnvPrepare(ws, { pinned: state.data_root });
      note = "the recompose batch is sealed, so this lookup is not recorded in its grounding; the result is the same";
    } else {
      [, scope, root] = await _scope(ws, outName);
    }
  } else {
    [root] = engineEnvPrepare(ws);
  }
  const { lang_query } = await import("../cex_core/engine/ist_core/tools/device/lang_query_tool.js");
  const kwargs: Record<string, unknown> = {};
  for (const k of ["kind", "name", "domain", "query", "position"]) {
    if (k in args) kwargs[k] = args[k];
  }
  let result: unknown;
  if (scope === null) {
    result = lang_query(String(kwargs.kind ?? ""), String(kwargs.name ?? ""), String(kwargs.domain ?? ""), String(kwargs.query ?? ""), Number(kwargs.position ?? 0));
  } else {
    result = await scope(() => lang_query(String(kwargs.kind ?? ""), String(kwargs.name ?? ""), String(kwargs.domain ?? ""), String(kwargs.query ?? ""), Number(kwargs.position ?? 0)));
  }
  const out: Record<string, unknown> = { ok: true, data_root: root, result };
  if (note) out.note = note;
  return out;
}
