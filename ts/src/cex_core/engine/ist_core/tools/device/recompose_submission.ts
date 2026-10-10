import fs from "node:fs";
import nodePath from "node:path";

import {
  atomic_write_bytes_nofollow,
  canonical_json,
  lexical_absolute,
  lexical_path_inside_root,
  open_directory_nofollow,
  read_regular_nofollow,
  sha256_bytes,
  validate_json_budget,
} from "../../../case_compiler/_sealed_io";
import {
  MACHINE_MINDMAP_SUBMISSION_LOCK_NAME,
  MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME,
  RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME,
} from "../../../engine_managed_outputs";
import { P } from "../../../_py";
import { acquireLockSync } from "../../../../../platform/index";

export const SCHEMA = "ist.machine-mindmap-submission";
const _ARTIFACT_NAME = "machine_mindmap.json";
const _DISPATCH_ID_RE = /^[0-9a-f]{32}$/;
const _AUTOID_RE = /^\d{18}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _MAX_ARTIFACT_BYTES = 16 * 1024 * 1024;
const _MAX_RECEIPT_BYTES = 16 * 1024;
const _MAX_GROUNDING_BYTES = 4 * 1024 * 1024;
const _MAX_GROUNDING_RESULT_BYTES = 512 * 1024;
const _GROUNDING_SCHEMA = "ist.recompose-command-grounding";
const _GROUNDING_KINDS = new Set(["param", "complete", "heads"]);
export const RECOMPOSE_HEADS_SCOPE_REFUSAL = "recompose_heads_not_offered";
export const RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT = "error: kind='heads' is not offered in the recompose scope (the head inventory is bound to a compile-worker session); use kind='param' for an exact head or kind='complete' for a partial head";
const logger = { warning: (..._args: any[]) => {} };
const _BINDING_KEYS = new Set(["source", "governing_spec", "governing_spec_status", "governing_spec_sha256", "governing_spec_generation_id", "governing_spec_manifest_sha256", "defect_spec_status", "defect_spec_receipt_sha256"]);
const _ARTIFACT_BINDING_KEYS = ["source", "governing_spec", "defect_spec_status", "defect_spec_receipt_sha256"];

export class MachineMindmapSubmissionError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "MachineMindmapSubmissionError";
  }
}

export class MachineMindmapContentError extends MachineMindmapSubmissionError {
  code: string;
  constructor(message?: string, opts: { code?: string } = {}) {
    super(message);
    this.name = "MachineMindmapContentError";
    this.code = opts.code ?? "mindmap_content_invalid";
  }
}

export class MachineMindmapSubmissionReceipt {
  readonly out_name: string;
  readonly dispatch_id: string;
  readonly status: string;
  readonly artifact_sha256: string | null;
  readonly artifact_size: number | null;
  readonly binding: Record<string, any>;
  readonly binding_sha256: string;
  constructor(opts: { out_name: string; dispatch_id: string; status: string; artifact_sha256: string | null; artifact_size: number | null; binding: Record<string, any>; binding_sha256: string }) {
    this.out_name = opts.out_name;
    this.dispatch_id = opts.dispatch_id;
    this.status = opts.status;
    this.artifact_sha256 = opts.artifact_sha256;
    this.artifact_size = opts.artifact_size;
    this.binding = opts.binding;
    this.binding_sha256 = opts.binding_sha256;
  }
}

interface _RecomposeDispatchScope {
  outputs_root: string;
  out_name: string;
  dispatch_id: string;
  binding_sha256: string;
  assigned_autoids: readonly string[];
}

let _currentRecomposeDispatch: _RecomposeDispatchScope | null = null;

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _validateIdentity(out_name: string, dispatch_id: string): [string, string] {
  const name = String(out_name ?? "").trim();
  const identity = String(dispatch_id ?? "").trim();
  if (!name || name === "." || name === ".." || nodePath.basename(name) !== name || name.includes("/") || name.includes("\\") || name.includes("~") || [...name].some((c) => c.charCodeAt(0) < 32) || name.length > 180) {
    throw new MachineMindmapSubmissionError("machine mindmap submission out_name is invalid");
  }
  if (!_DISPATCH_ID_RE.test(identity)) {
    throw new MachineMindmapSubmissionError("machine mindmap submission dispatch identity is invalid");
  }
  return [name, identity];
}

function _batchPath(outputs_root: string | P, out_name: string): string {
  const [name] = _validateIdentity(out_name, "0".repeat(32));
  const root = lexical_absolute(String(outputs_root));
  const path = lexical_path_inside_root(nodePath.join(root, name), root, { errorType: MachineMindmapSubmissionError, traversal_message: "machine mindmap submission path traversal is forbidden", outside_message: "machine mindmap submission escaped outputs root" });
  if (path !== nodePath.join(root, name)) {
    throw new MachineMindmapSubmissionError("machine mindmap submission batch identity is invalid");
  }
  return path;
}

export function machine_mindmap_submission_path(outputs_root: string | P, out_name: string): P {
  return new P(nodePath.join(_batchPath(outputs_root, out_name), MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME));
}

export function machine_mindmap_artifact_path(outputs_root: string | P, out_name: string): P {
  return new P(nodePath.join(_batchPath(outputs_root, out_name), _ARTIFACT_NAME));
}

export function recompose_command_grounding_path(outputs_root: string | P, out_name: string): P {
  return new P(nodePath.join(_batchPath(outputs_root, out_name), RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME));
}

function _compileContextIdentity(outputs_root: string, out_name: string): string {
  const path = nodePath.join(_batchPath(outputs_root, out_name), "compile_context.json");
  let raw: Buffer;
  try {
    raw = read_regular_nofollow(path, {
      errorType: MachineMindmapSubmissionError,
      invalid_message: "compile context path is invalid",
      directory_message: "compile context parent is unavailable",
      open_message: "compile context is unavailable",
      bounds_message: "compile context exceeds its boundary",
      changed_message: "compile context changed while reading",
      max_bytes: 2 * 1024 * 1024,
      min_bytes: 1,
      preserve_missing: true,
      trusted_root: outputs_root,
      require_current_uid: true,
    }) as Buffer;
  } catch (exc) {
    if ((exc as any)?.code === "ENOENT" || exc instanceof MachineMindmapSubmissionError && /unavailable/.test((exc as Error).message)) {
      return "";
    }
    if ((exc as any)?.code === "ENOENT") return "";
    throw exc;
  }
  let document: any;
  try {
    document = JSON.parse(raw.toString("utf8"));
  } catch (exc) {
    throw new MachineMindmapSubmissionError("compile context is not valid JSON");
  }
  const identity = _isMapping(document) ? String(document.identity_sha256 ?? "") : "";
  if (!_SHA256_RE.test(identity)) {
    throw new MachineMindmapSubmissionError("compile context identity is invalid");
  }
  return identity;
}

function _groundingQuery(opts: { kind: string; name: string; domain: string; query: string; position: number }): Record<string, any> {
  return { kind: String(opts.kind ?? "").trim().toLowerCase(), name: String(opts.name ?? "").trim(), domain: String(opts.domain ?? "").trim(), query: String(opts.query ?? "").trim(), position: Number(opts.position ?? 0) };
}

function _groundingKey(query: Record<string, any>): string {
  return sha256_bytes(canonical_json({ ...query }, { ensure_ascii: false }));
}

function _readGroundingBytes(path: string | P, outputs_root: string): Buffer | null {
  try {
    return read_regular_nofollow(String(path instanceof P ? path._p : path), {
      errorType: MachineMindmapSubmissionError,
      invalid_message: "recompose command grounding path is invalid",
      directory_message: "recompose command grounding parent is unavailable",
      open_message: "recompose command grounding is unavailable",
      bounds_message: "recompose command grounding exceeds its boundary",
      changed_message: "recompose command grounding changed while reading",
      max_bytes: _MAX_GROUNDING_BYTES,
      min_bytes: 1,
      preserve_missing: true,
      trusted_root: outputs_root,
      require_current_uid: true,
    }) as Buffer;
  } catch (exc) {
    if ((exc as any)?.code === "ENOENT") return null;
    if (exc instanceof MachineMindmapSubmissionError && /unavailable/.test((exc as Error).message)) return null;
    throw exc;
  }
}

function _isRecomposeScopeRefusal(entry: Record<string, any>): boolean {
  const query = entry.query;
  return entry.replayable === false && entry.scope_refusal_reason === RECOMPOSE_HEADS_SCOPE_REFUSAL && _isMapping(query) && query.kind === "heads" && Boolean(String(query.name ?? "").trim()) && entry.result === RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT && !("head_in_tree" in entry) && !("recorded_heads" in entry);
}

function _validateGroundingDocument(document: any, opts: { out_name: string; dispatch_id: string; allowed_statuses: Set<string> }): Record<string, any> {
  const { out_name, dispatch_id, allowed_statuses } = opts;
  if (
    !_isMapping(document) ||
    document.schema !== _GROUNDING_SCHEMA ||
    document.out_name !== out_name ||
    document.dispatch_id !== dispatch_id ||
    !allowed_statuses.has(document.status) ||
    !_isMapping(document.entries) ||
    typeof document.binding_sha256 !== "string" ||
    !_SHA256_RE.test(String(document.binding_sha256 ?? "")) ||
    typeof document.compile_context_sha256 !== "string" ||
    (document.compile_context_sha256 && !_SHA256_RE.test(String(document.compile_context_sha256)))
  ) {
    throw new MachineMindmapSubmissionError("recompose command grounding identity is invalid");
  }
  const status = String(document.status ?? "");
  const machineSha = document.machine_mindmap_sha256;
  if ((status === "open" && machineSha !== null && machineSha !== undefined) || (status === "sealed" && (typeof machineSha !== "string" || !_SHA256_RE.test(machineSha)))) {
    throw new MachineMindmapSubmissionError("recompose command grounding machine identity is invalid");
  }
  for (const [key, entry] of Object.entries<any>(document.entries)) {
    if (
      !_SHA256_RE.test(key) ||
      !_isMapping(entry) ||
      !_isMapping(entry.query) ||
      typeof entry.result !== "string" ||
      typeof entry.result_sha256 !== "string" ||
      _groundingKey(entry.query) !== key ||
      sha256_bytes(Buffer.from(entry.result, "utf8")) !== entry.result_sha256
    ) {
      throw new MachineMindmapSubmissionError("recompose command grounding entry is invalid");
    }
    if ("scope_refusal_reason" in entry && !_isRecomposeScopeRefusal(entry)) {
      throw new MachineMindmapSubmissionError("recompose command grounding scope refusal is invalid");
    }
  }
  return document;
}

function _projectionHeadStamp(name: string, opts: { kind: string }): Record<string, any> | null {
  if (!String(name ?? "").trim()) return null;
  const { load_vendor_stdlib } = require("../../../case_compiler/vendor_stdlib");
  const inventory = load_vendor_stdlib();
  if (inventory === null || inventory === undefined) return null;
  const { recorded_command_heads } = require("../worker_device_context");
  const heads: string[] = recorded_command_heads(inventory, name);
  if (!heads.length && opts.kind === "complete") {
    const { rank_vendor_command_completions } = require("../../../case_compiler/vendor_stdlib");
    const continuations = rank_vendor_command_completions(name).filter((c: any) => c.prefix_continuation).length;
    if (continuations) return null;
  }
  return { head_in_tree: heads.length > 0, recorded_heads: heads.length };
}

function _groundingRequest(opts: { kind: string; name: string; domain: string; query: string; position: number }): [_RecomposeDispatchScope, string, Record<string, any>, string] | null {
  const scope = _currentRecomposeDispatch;
  if (scope === null) return null;
  const kindValue = String(opts.kind ?? "").trim().toLowerCase();
  if (!_GROUNDING_KINDS.has(kindValue)) return null;
  const queryValue = _groundingQuery(opts);
  return [scope, kindValue, queryValue, _groundingKey(queryValue)];
}

function _groundingEntry(opts: { kind: string; name: string; query: Record<string, any>; result: string; scope_refusal_reason?: string }): Record<string, any> {
  const { kind, name, query, result } = opts;
  const scopeRefusalReason = opts.scope_refusal_reason ?? "";
  if (typeof result !== "string" || Buffer.byteLength(result, "utf8") > _MAX_GROUNDING_RESULT_BYTES) {
    throw new MachineMindmapSubmissionError("recompose command grounding result exceeds its boundary");
  }
  const entry: Record<string, any> = { query: { ...query }, result, result_sha256: sha256_bytes(Buffer.from(result, "utf8")) };
  if (!result.startsWith("error:")) {
    const stamp = _projectionHeadStamp(name, { kind });
    if (stamp !== null) {
      entry.head_in_tree = stamp.head_in_tree;
      entry.recorded_heads = stamp.recorded_heads;
    }
  }
  if (scopeRefusalReason) {
    entry.replayable = false;
    entry.scope_refusal_reason = scopeRefusalReason;
    if (kind !== "heads" || !_isRecomposeScopeRefusal(entry)) {
      throw new MachineMindmapSubmissionError("recompose command grounding scope refusal is invalid");
    }
  }
  return entry;
}

function _openGroundingDocumentLocked(scope: _RecomposeDispatchScope, path: string, opts: { reset_stale?: boolean } = {}): [Record<string, any>, string, string] {
  assert_machine_mindmap_submission_open(scope.outputs_root, scope.out_name, scope.dispatch_id);
  const prepared = read_machine_mindmap_submission(scope.outputs_root, scope.out_name, scope.dispatch_id);
  if (prepared.binding_sha256 !== scope.binding_sha256) {
    throw new MachineMindmapSubmissionError("recompose command grounding dispatch binding changed after scope validation");
  }
  const contextSha = _compileContextIdentity(scope.outputs_root, scope.out_name);
  const raw = _readGroundingBytes(path, scope.outputs_root);
  const fresh = { schema: _GROUNDING_SCHEMA, out_name: scope.out_name, dispatch_id: scope.dispatch_id, status: "open", machine_mindmap_sha256: null, binding_sha256: prepared.binding_sha256, compile_context_sha256: contextSha, entries: {} };
  if (raw === null) {
    return [fresh, prepared.binding_sha256, contextSha];
  }
  let document: any;
  try {
    document = JSON.parse(raw.toString("utf8"));
  } catch (exc) {
    throw new MachineMindmapSubmissionError("recompose command grounding is not valid JSON");
  }
  document = _validateGroundingDocument(document, { out_name: scope.out_name, dispatch_id: scope.dispatch_id, allowed_statuses: new Set(["open"]) });
  if (document.binding_sha256 !== prepared.binding_sha256 || document.compile_context_sha256 !== contextSha) {
    if (opts.reset_stale) {
      return [fresh, prepared.binding_sha256, contextSha];
    }
    throw new MachineMindmapSubmissionError("recompose command grounding context identity drifted");
  }
  return [document, prepared.binding_sha256, contextSha];
}

function _assertGroundingIdentityStableLocked(scope: _RecomposeDispatchScope, opts: { binding_sha256: string; compile_context_sha256: string }): void {
  assert_machine_mindmap_submission_open(scope.outputs_root, scope.out_name, scope.dispatch_id);
  const prepared = read_machine_mindmap_submission(scope.outputs_root, scope.out_name, scope.dispatch_id);
  if (prepared.binding_sha256 !== opts.binding_sha256 || prepared.binding_sha256 !== scope.binding_sha256 || _compileContextIdentity(scope.outputs_root, scope.out_name) !== opts.compile_context_sha256) {
    throw new MachineMindmapSubmissionError("recompose command grounding context identity drifted while rendering");
  }
}

function _commitGroundingEntryLocked(path: string, document: Record<string, any>, opts: { key: string; entry: Record<string, any>; replace_failed?: boolean }): void {
  const existing = document.entries[opts.key];
  const mayReplace = (opts.replace_failed ?? false) && _isMapping(existing) && String(existing.result ?? "").startsWith("error:");
  if (existing !== null && existing !== undefined && JSON.stringify(existing) !== JSON.stringify(opts.entry) && !mayReplace) {
    throw new MachineMindmapSubmissionError("identical recompose grounding query produced different bytes");
  }
  document.entries[opts.key] = opts.entry;
  const encoded = canonical_json(document, { ensure_ascii: false });
  if (encoded.length > _MAX_GROUNDING_BYTES) {
    throw new MachineMindmapSubmissionError("recompose command grounding exceeds its byte budget");
  }
  atomic_write_bytes_nofollow(path, encoded, { errorType: MachineMindmapSubmissionError, invalid_message: "recompose command grounding path is invalid", unavailable_message: "recompose command grounding cannot be committed", create_parents: false, mode: 0o600 });
}

function _withSubmissionLock<T>(batch: string, fn: () => T): T {
  open_directory_nofollow(batch, { errorType: MachineMindmapSubmissionError, invalid_message: "machine mindmap submission batch path is invalid", unavailable_message: "machine mindmap submission batch is unavailable" });
  const lockPath = nodePath.join(batch, MACHINE_MINDMAP_SUBMISSION_LOCK_NAME);
  let fd: number;
  try {
    fd = fs.openSync(lockPath, fs.constants.O_RDWR | fs.constants.O_CREAT | (((fs.constants as any).O_NOFOLLOW || 0)), 0o600);
  } catch (exc) {
    throw new MachineMindmapSubmissionError("machine mindmap submission lock is unavailable");
  }
  try {
    const info = fs.fstatSync(fd);
    const named = fs.lstatSync(lockPath);
    if (!info.isFile() || !named.isFile() || info.nlink !== 1 || named.nlink !== 1 || info.dev !== named.dev || info.ino !== named.ino || (info.mode & 0o077) !== 0) {
      throw new MachineMindmapSubmissionError("machine mindmap submission lock identity is invalid");
    }
  } catch (exc) {
    fs.closeSync(fd);
    throw exc;
  }
  const handle = acquireLockSync(lockPath + ".flock");
  try {
    return fn();
  } finally {
    handle.release();
    fs.closeSync(fd);
  }
}

export function record_recompose_command_grounding(opts: { kind: string; name?: string; domain?: string; query?: string; position?: number; result: string }): string | null {
  const request = _groundingRequest({ kind: opts.kind, name: opts.name ?? "", domain: opts.domain ?? "", query: opts.query ?? "", position: opts.position ?? 0 });
  if (request === null) return null;
  const [scope, kindValue, queryValue, key] = request;
  const entry = _groundingEntry({ kind: kindValue, name: opts.name ?? "", query: queryValue, result: opts.result });
  const batch = _batchPath(scope.outputs_root, scope.out_name);
  const path = recompose_command_grounding_path(scope.outputs_root, scope.out_name)._p;
  _withSubmissionLock(batch, () => {
    const [document] = _openGroundingDocumentLocked(scope, path);
    _commitGroundingEntryLocked(path, document, { key, entry });
  });
  return key;
}

export function resolve_recompose_command_grounding(render: () => string, opts: { kind: string; name?: string; domain?: string; query?: string; position?: number; scope_refusal_reason?: string }): [string, string | null] {
  const request = _groundingRequest({ kind: opts.kind, name: opts.name ?? "", domain: opts.domain ?? "", query: opts.query ?? "", position: opts.position ?? 0 });
  if (request === null) {
    return [render(), null];
  }
  const [scope, kindValue, queryValue, key] = request;
  const batch = _batchPath(scope.outputs_root, scope.out_name);
  const path = recompose_command_grounding_path(scope.outputs_root, scope.out_name)._p;
  return _withSubmissionLock(batch, () => {
    const [document, bindingSha, contextSha] = _openGroundingDocumentLocked(scope, path, { reset_stale: true });
    const existing = document.entries[key];
    if (_isMapping(existing) && !String(existing.result ?? "").startsWith("error:")) {
      return [String(existing.result), key];
    }
    const result = render();
    const entry = _groundingEntry({ kind: kindValue, name: opts.name ?? "", query: queryValue, result, scope_refusal_reason: opts.scope_refusal_reason ?? "" });
    _assertGroundingIdentityStableLocked(scope, { binding_sha256: bindingSha, compile_context_sha256: contextSha });
    _commitGroundingEntryLocked(path, document, { key, entry, replace_failed: true });
    return [result, key];
  });
}

function _sealRecomposeCommandGroundingLocked(outputs_root: string, out_name: string, dispatch_id: string, machine_mindmap_sha256: string): void {
  const path = recompose_command_grounding_path(outputs_root, out_name)._p;
  const raw = _readGroundingBytes(path, outputs_root);
  if (raw === null) return;
  let document: any;
  try {
    document = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new MachineMindmapSubmissionError("recompose command grounding is not valid JSON");
  }
  document = _validateGroundingDocument(document, { out_name, dispatch_id, allowed_statuses: new Set(["open"]) });
  document.status = "sealed";
  document.machine_mindmap_sha256 = machine_mindmap_sha256;
  atomic_write_bytes_nofollow(path, canonical_json(document, { ensure_ascii: false }), { errorType: MachineMindmapSubmissionError, invalid_message: "recompose command grounding path is invalid", unavailable_message: "recompose command grounding cannot be sealed", create_parents: false, mode: 0o600 });
}

export function load_recompose_command_grounding(outputs_root: string | P, out_name: string, opts: { machine_mindmap_sha256: string }): [Record<string, any>, string] | null {
  const root = lexical_absolute(String(outputs_root));
  const path = recompose_command_grounding_path(root, out_name)._p;
  const raw = _readGroundingBytes(path, root);
  if (raw === null) return null;
  let document: any;
  let dispatch_id: string;
  try {
    document = JSON.parse(raw.toString("utf8"));
    dispatch_id = String(document?.dispatch_id ?? "");
  } catch {
    throw new MachineMindmapSubmissionError("recompose command grounding is not valid JSON");
  }
  document = _validateGroundingDocument(document, { out_name, dispatch_id, allowed_statuses: new Set(["sealed"]) });
  if (document.machine_mindmap_sha256 !== opts.machine_mindmap_sha256) {
    throw new MachineMindmapSubmissionError("recompose command grounding machine identity drifted");
  }
  const receipt = read_machine_mindmap_submission(root, out_name, dispatch_id);
  if (receipt.status !== "submitted" || receipt.artifact_sha256 !== opts.machine_mindmap_sha256 || document.binding_sha256 !== receipt.binding_sha256 || document.compile_context_sha256 !== _compileContextIdentity(root, out_name)) {
    throw new MachineMindmapSubmissionError("recompose command grounding dispatch is not the submitted machine identity");
  }
  return [document, sha256_bytes(raw)];
}

export function revalidate_recompose_command_grounding(
  outputs_root: string | P,
  out_name: string,
  opts: { machine_mindmap_sha256: string; query_runner?: ((query: Record<string, any>) => string) | null },
): [Record<string, any>, string] | null {
  const root = lexical_absolute(String(outputs_root));
  const path = recompose_command_grounding_path(root, out_name)._p;
  const raw = _readGroundingBytes(path, root);
  if (raw === null) return null;
  let document: any;
  let dispatch_id: string;
  try {
    document = JSON.parse(raw.toString("utf8"));
    dispatch_id = String(document?.dispatch_id ?? "");
  } catch {
    throw new MachineMindmapSubmissionError("recompose command grounding is not valid JSON");
  }
  document = _validateGroundingDocument(document, { out_name, dispatch_id, allowed_statuses: new Set(["sealed"]) });
  if (document.machine_mindmap_sha256 !== opts.machine_mindmap_sha256) {
    throw new MachineMindmapSubmissionError("recompose command grounding machine identity drifted");
  }
  const receipt = read_machine_mindmap_submission(root, out_name, dispatch_id);
  if (receipt.status !== "submitted" || receipt.artifact_sha256 !== opts.machine_mindmap_sha256 || document.binding_sha256 !== receipt.binding_sha256) {
    throw new MachineMindmapSubmissionError("recompose command grounding dispatch is not the submitted machine identity");
  }
  const currentContextSha = _compileContextIdentity(root, out_name);
  if (!currentContextSha) {
    throw new MachineMindmapSubmissionError("recompose command grounding has no current compile context");
  }
  if (document.compile_context_sha256 === currentContextSha) {
    return [document, sha256_bytes(raw)];
  }
  if (_currentRecomposeDispatch !== null) {
    throw new MachineMindmapSubmissionError("recompose command grounding cannot be revalidated inside its write scope");
  }
  let queryRunner = opts.query_runner ?? null;
  if (queryRunner === null) {
    const { lang_query } = require("./lang_query_tool");
    queryRunner = (q: Record<string, any>) => lang_query(q.kind, q.name, q.domain, q.query, q.position);
  }
  for (const key of Object.keys(document.entries).sort()) {
    const entry = document.entries[key];
    if (_isRecomposeScopeRefusal(entry)) continue;
    const query = { ...entry.query };
    if (!["param", "complete", "heads"].includes(String(query.kind ?? ""))) {
      throw new MachineMindmapSubmissionError("recompose command grounding contains a non-replayable query");
    }
    let replayed: any;
    try {
      replayed = queryRunner(query);
    } catch (exc) {
      throw new MachineMindmapSubmissionError("recompose command grounding query replay failed");
    }
    if (typeof replayed !== "string" || replayed !== entry.result) {
      throw new MachineMindmapSubmissionError("recompose command grounding query result changed under current context");
    }
  }
  const rebound = { ...document, compile_context_sha256: currentContextSha };
  const encoded = canonical_json(rebound, { ensure_ascii: false });
  _withSubmissionLock(_batchPath(root, out_name), () => {
    const currentRaw = _readGroundingBytes(path, root);
    if (currentRaw !== null && !currentRaw.equals(raw)) {
      throw new MachineMindmapSubmissionError("recompose command grounding changed during context revalidation");
    }
    if (currentRaw === null) {
      throw new MachineMindmapSubmissionError("recompose command grounding changed during context revalidation");
    }
    if (_compileContextIdentity(root, out_name) !== currentContextSha) {
      throw new MachineMindmapSubmissionError("compile context changed during grounding revalidation");
    }
    atomic_write_bytes_nofollow(path, encoded, { errorType: MachineMindmapSubmissionError, invalid_message: "recompose command grounding path is invalid", unavailable_message: "recompose command grounding cannot be rebound", create_parents: false, mode: 0o600 });
  });
  return [rebound, sha256_bytes(encoded)];
}

function _validateBinding(binding: Record<string, any>): [Record<string, any>, string] {
  const value = { ...binding };
  const keys = new Set(Object.keys(value));
  if (keys.size !== _BINDING_KEYS.size || ![..._BINDING_KEYS].every((k) => keys.has(k))) {
    throw new MachineMindmapSubmissionError("machine mindmap submission binding shape is invalid");
  }
  for (const key of ["source", "governing_spec_status", "defect_spec_status"]) {
    if (typeof value[key] !== "string" || !String(value[key]).trim()) {
      throw new MachineMindmapSubmissionError(`machine mindmap submission binding field is invalid: ${key}`);
    }
  }
  for (const key of ["governing_spec", "governing_spec_sha256", "governing_spec_generation_id", "governing_spec_manifest_sha256", "defect_spec_receipt_sha256"]) {
    if (value[key] !== null && value[key] !== undefined && typeof value[key] !== "string") {
      throw new MachineMindmapSubmissionError(`machine mindmap submission binding field is invalid: ${key}`);
    }
  }
  return [value, sha256_bytes(canonical_json(value, { ensure_ascii: false }))];
}

export function machine_mindmap_submission_binding_from_brief(brief: Record<string, any>): Record<string, any> {
  if (!_isMapping(brief)) {
    throw new MachineMindmapSubmissionError("machine mindmap submission brief is invalid");
  }
  const keys = ["mindmap_path", "governing_spec", "governing_spec_status", "governing_spec_sha256", "governing_spec_generation_id", "governing_spec_manifest_sha256", "defect_spec_status", "defect_spec_receipt_sha256"];
  if (!keys.every((k) => k in brief)) {
    throw new MachineMindmapSubmissionError("machine mindmap submission brief binding is incomplete");
  }
  const binding = { source: brief.mindmap_path, governing_spec: brief.governing_spec, governing_spec_status: brief.governing_spec_status, governing_spec_sha256: brief.governing_spec_sha256, governing_spec_generation_id: brief.governing_spec_generation_id, governing_spec_manifest_sha256: brief.governing_spec_manifest_sha256, defect_spec_status: brief.defect_spec_status, defect_spec_receipt_sha256: brief.defect_spec_receipt_sha256 };
  return _validateBinding(binding)[0];
}

function _preparedPayload(out_name: string, dispatch_id: string, binding: Record<string, any>): Record<string, any> {
  const [bound, bindingSha256] = _validateBinding(binding);
  return { schema: SCHEMA, out_name, dispatch_id, status: "prepared", artifact_sha256: null, artifact_size: null, binding: bound, binding_sha256: bindingSha256 };
}

function _removeRegularLeaf(directory: string, name: string): void {
  const target = nodePath.join(directory, name);
  let info: fs.Stats;
  try {
    info = fs.lstatSync(target);
  } catch (exc) {
    if ((exc as any)?.code === "ENOENT") return;
    throw exc;
  }
  if (!info.isFile() || info.nlink !== 1 || (typeof process.getuid === "function" && info.uid !== process.getuid())) {
    throw new MachineMindmapSubmissionError("machine mindmap submission target is not a sealed regular file");
  }
  fs.unlinkSync(target);
}

export function initialize_machine_mindmap_submission(
  outputs_root: string | P,
  out_name: string,
  dispatch_id: string,
  opts: { binding: Record<string, any>; case_autoids?: Iterable<string> | null; source_sha256?: string | null },
): [P, readonly string[]] {
  const [name, identity] = _validateIdentity(out_name, dispatch_id);
  const batch = _batchPath(outputs_root, name);
  const [, bindingSha256] = _validateBinding(opts.binding);
  return _withSubmissionLock(batch, () => {
    let preservedGrounding: Record<string, any> | null = null;
    const groundingPath = recompose_command_grounding_path(outputs_root, name)._p;
    try {
      const groundingRaw = _readGroundingBytes(groundingPath, lexical_absolute(String(outputs_root)));
      if (groundingRaw !== null) {
        const candidate = JSON.parse(groundingRaw.toString("utf8"));
        const oldDispatch = String(candidate?.dispatch_id ?? "");
        _validateIdentity(name, oldDispatch);
        preservedGrounding = _validateGroundingDocument(candidate, { out_name: name, dispatch_id: oldDispatch, allowed_statuses: new Set(["open", "sealed"]) });
      }
    } catch {
      preservedGrounding = null;
    }
    _removeRegularLeaf(batch, _ARTIFACT_NAME);
    _removeRegularLeaf(batch, RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME);
    _removeRegularLeaf(batch, MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME);
    let alreadySubmitted: readonly string[] = [];
    if (opts.case_autoids) {
      const { initialize_machine_mindmap_parts } = require("./recompose_parts");
      if (typeof opts.source_sha256 !== "string") {
        throw new MachineMindmapSubmissionError("machine mindmap parts dispatch requires the source digest");
      }
      const [, snapshot] = initialize_machine_mindmap_parts(outputs_root, name, { binding_sha256: bindingSha256, source_sha256: opts.source_sha256, case_autoids: opts.case_autoids });
      alreadySubmitted = snapshot.submitted_autoids;
    } else {
      const { discard_machine_mindmap_parts } = require("./recompose_parts");
      discard_machine_mindmap_parts(outputs_root, name);
    }
    const contextSha = _compileContextIdentity(lexical_absolute(String(outputs_root)), name);
    if (preservedGrounding !== null && preservedGrounding.binding_sha256 === bindingSha256 && preservedGrounding.compile_context_sha256 === contextSha) {
      preservedGrounding = { ...preservedGrounding, dispatch_id: identity, status: "open", machine_mindmap_sha256: null };
      atomic_write_bytes_nofollow(groundingPath, canonical_json(preservedGrounding, { ensure_ascii: false }), { errorType: MachineMindmapSubmissionError, invalid_message: "recompose command grounding path is invalid", unavailable_message: "recompose command grounding cannot be rebound", create_parents: false, mode: 0o600 });
    }
    const receiptPath = machine_mindmap_submission_path(outputs_root, name);
    atomic_write_bytes_nofollow(receiptPath._p, canonical_json(_preparedPayload(name, identity, opts.binding), { ensure_ascii: false }), { errorType: MachineMindmapSubmissionError, invalid_message: "machine mindmap submission receipt path is invalid", unavailable_message: "machine mindmap submission cannot be prepared safely", create_parents: false, mode: 0o600 });
    return [receiptPath, alreadySubmitted];
  });
}

function _decodeReceipt(raw: Buffer): Record<string, any> {
  let value: any;
  try {
    value = JSON.parse(raw.toString("utf8"), (_key, v) => {
      if (v !== null && typeof v === "object" && !Array.isArray(v)) {
        const keys = Object.keys(v);
        if (new Set(keys).size !== keys.length) throw new Error("duplicate JSON key");
      }
      if (typeof v === "number" && !Number.isFinite(v)) throw new Error(`non-finite JSON constant: ${v}`);
      return v;
    });
  } catch {
    throw new MachineMindmapSubmissionError("machine mindmap submission receipt is invalid JSON");
  }
  if (!_isMapping(value)) {
    throw new MachineMindmapSubmissionError("machine mindmap submission receipt must be an object");
  }
  return value;
}

export function rederive_sealed_mechanical_fields(outputs_root: string | P, name: string, mindmap_text: string): string[] {
  const { fill_mechanical_fields, load_machine_mindmap } = require("../../../case_compiler/mindmap_contract_projector");
  const artifactPath = machine_mindmap_artifact_path(outputs_root, name);
  const receiptPath = machine_mindmap_submission_path(outputs_root, name);
  if (!artifactPath.exists()) return [];
  const [data] = load_machine_mindmap(artifactPath);
  const repaired: string[] = fill_mechanical_fields(data, mindmap_text);
  if (!repaired.length) return [];
  const raw = canonical_json(data, { ensure_ascii: false });
  atomic_write_bytes_nofollow(artifactPath._p, raw, { errorType: MachineMindmapSubmissionError, invalid_message: "machine mindmap artifact path is invalid", unavailable_message: "machine mindmap artifact cannot be committed safely", create_parents: false, mode: 0o600 });
  let receipt: any;
  try {
    receipt = JSON.parse(fs.readFileSync(receiptPath._p).toString("utf8"));
  } catch {
    return repaired;
  }
  receipt.artifact_sha256 = require("node:crypto").createHash("sha256").update(raw).digest("hex");
  receipt.artifact_size = raw.length;
  atomic_write_bytes_nofollow(receiptPath._p, canonical_json(receipt, { ensure_ascii: false }), { errorType: MachineMindmapSubmissionError, invalid_message: "machine mindmap submission receipt path is invalid", unavailable_message: "machine mindmap submission receipt cannot be committed", create_parents: false, mode: 0o600 });
  return repaired;
}

export function read_machine_mindmap_submission(outputs_root: string | P, out_name: string, dispatch_id: string): MachineMindmapSubmissionReceipt {
  const [name, identity] = _validateIdentity(out_name, dispatch_id);
  const root = lexical_absolute(String(outputs_root));
  const path = machine_mindmap_submission_path(root, name);
  const raw = read_regular_nofollow(path._p, {
    errorType: MachineMindmapSubmissionError,
    invalid_message: "machine mindmap submission receipt path is invalid",
    directory_message: "machine mindmap submission receipt parent is unavailable",
    open_message: "machine mindmap submission receipt is unavailable",
    bounds_message: "machine mindmap submission receipt exceeds its boundary",
    changed_message: "machine mindmap submission receipt changed while reading",
    max_bytes: _MAX_RECEIPT_BYTES,
    min_bytes: 1,
    trusted_root: root,
    require_current_uid: true,
  }) as Buffer;
  const value = _decodeReceipt(raw);
  const required = new Set(["schema", "out_name", "dispatch_id", "status", "artifact_sha256", "artifact_size", "binding", "binding_sha256"]);
  if (Object.keys(value).length !== required.size || !Object.keys(value).every((k) => required.has(k)) || value.schema !== SCHEMA || value.out_name !== name || value.dispatch_id !== identity || !["prepared", "submitted"].includes(String(value.status))) {
    throw new MachineMindmapSubmissionError("machine mindmap submission receipt identity is stale");
  }
  const status = String(value.status);
  const digest = value.artifact_sha256;
  const size = value.artifact_size;
  const rawBinding = value.binding;
  const rawBindingSha256 = value.binding_sha256;
  if (!_isMapping(rawBinding)) {
    throw new MachineMindmapSubmissionError("machine mindmap submission binding is invalid");
  }
  const [binding, bindingSha256] = _validateBinding(rawBinding);
  if (rawBindingSha256 !== bindingSha256) {
    throw new MachineMindmapSubmissionError("machine mindmap submission binding identity changed");
  }
  if (status === "prepared") {
    if (digest !== null && digest !== undefined) {
      throw new MachineMindmapSubmissionError("prepared machine mindmap submission has artifact identity");
    }
    if (size !== null && size !== undefined) {
      throw new MachineMindmapSubmissionError("prepared machine mindmap submission has artifact identity");
    }
  } else if (typeof digest !== "string" || !_SHA256_RE.test(digest) || typeof size !== "number" || !Number.isInteger(size) || size < 1 || size > _MAX_ARTIFACT_BYTES) {
    throw new MachineMindmapSubmissionError("submitted machine mindmap identity is invalid");
  }
  return new MachineMindmapSubmissionReceipt({ out_name: name, dispatch_id: identity, status, artifact_sha256: typeof digest === "string" ? digest : null, artifact_size: typeof size === "number" ? size : null, binding, binding_sha256: bindingSha256 });
}

export function assert_machine_mindmap_submission_binding(outputs_root: string | P, out_name: string, dispatch_id: string, opts: { expected_binding: Record<string, any> }): MachineMindmapSubmissionReceipt {
  const receipt = read_machine_mindmap_submission(outputs_root, out_name, dispatch_id);
  const [expected, expectedSha256] = _validateBinding(opts.expected_binding);
  if (JSON.stringify(receipt.binding) !== JSON.stringify(expected) || receipt.binding_sha256 !== expectedSha256) {
    throw new MachineMindmapSubmissionError("machine mindmap submission does not match the expected binding");
  }
  return receipt;
}

export function assert_machine_mindmap_submission_open(outputs_root: string | P, out_name: string, dispatch_id: string): void {
  const receipt = read_machine_mindmap_submission(outputs_root, out_name, dispatch_id);
  if (receipt.status !== "prepared") {
    throw new MachineMindmapSubmissionError("machine mindmap submission is already closed");
  }
}

export function recompose_dispatch_scope<T>(outputs_root: string | P, out_name: string, dispatch_id: string, fn: () => T, opts: { assigned_autoids?: Iterable<string> } = {}): T {
  const [name, identity] = _validateIdentity(out_name, dispatch_id);
  const root = lexical_absolute(String(outputs_root));
  const receipt = read_machine_mindmap_submission(root, name, identity);
  if (receipt.status !== "prepared") {
    throw new MachineMindmapSubmissionError("machine mindmap submission is already closed");
  }
  const assigned = _validatedAssignment(root, name, [...(opts.assigned_autoids ?? [])]);
  const previous = _currentRecomposeDispatch;
  _currentRecomposeDispatch = { outputs_root: root, out_name: name, dispatch_id: identity, binding_sha256: receipt.binding_sha256, assigned_autoids: assigned };
  try {
    return fn();
  } finally {
    _currentRecomposeDispatch = previous;
  }
}

function _validatedAssignment(outputs_root: string, out_name: string, assigned_autoids: string[]): readonly string[] {
  const requested = assigned_autoids.map((aid) => String(aid ?? "").trim());
  if (!requested.length) return [];
  if (requested.some((aid) => !_AUTOID_RE.test(aid))) {
    throw new MachineMindmapSubmissionError("recompose assignment carries a malformed autoid");
  }
  if (new Set(requested).size !== requested.length) {
    throw new MachineMindmapSubmissionError("recompose assignment repeats an autoid");
  }
  const { read_machine_mindmap_parts } = require("./recompose_parts");
  const snapshot = read_machine_mindmap_parts(outputs_root, out_name);
  const closed = new Set(snapshot.case_autoids);
  const stray = requested.filter((aid) => !closed.has(aid));
  if (stray.length) {
    throw new MachineMindmapSubmissionError("recompose assignment names cases outside the dispatched set");
  }
  const wanted = new Set(requested);
  return snapshot.case_autoids.filter((aid: any) => wanted.has(aid));
}

export function current_recompose_assignment(): readonly string[] {
  const scope = _currentRecomposeDispatch;
  if (scope === null) {
    throw new MachineMindmapSubmissionError("recompose submission requires a trusted dispatch");
  }
  return scope.assigned_autoids;
}

export function current_recompose_dispatch(): [string, string, string] {
  const scope = _currentRecomposeDispatch;
  if (scope === null) {
    throw new MachineMindmapSubmissionError("recompose submission requires a trusted dispatch");
  }
  return [scope.outputs_root, scope.out_name, scope.dispatch_id];
}

export function in_recompose_dispatch_scope(): boolean {
  return _currentRecomposeDispatch !== null;
}

export function machine_mindmap_submission_open_guard<T>(outputs_root: string | P, out_name: string, dispatch_id: string, fn: () => T): T {
  const [name, identity] = _validateIdentity(out_name, dispatch_id);
  return _withSubmissionLock(_batchPath(outputs_root, name), () => {
    assert_machine_mindmap_submission_open(outputs_root, name, identity);
    return fn();
  });
}

function _stepStructureFace(case_: Record<string, any>): string {
  const { ADAPTED_STEPS_KEY } = require("../../../case_compiler/step_structure");
  const sortKeys = (v: any): any => {
    if (Array.isArray(v)) return v.map(sortKeys);
    if (_isMapping(v)) {
      const out: Record<string, any> = {};
      for (const k of Object.keys(v).sort()) out[k] = sortKeys(v[k]);
      return out;
    }
    if (v === undefined) return null;
    return v;
  };
  return JSON.stringify(sortKeys({ step_structure: case_.step_structure, engine_slots: case_.engine_slots, [ADAPTED_STEPS_KEY]: case_[ADAPTED_STEPS_KEY] }));
}

function _rejectInlineStepStructure(envelope: Record<string, any>, ledger_faces: Record<string, string>): void {
  const { budget_violations, object_kind_closed_set, step_structure_violations, strip_engine_slots } = require("../../../case_compiler/step_structure");
  const cases = envelope.cases;
  if (!Array.isArray(cases)) return;
  const objectKinds = object_kind_closed_set();
  const violations: Array<Record<string, string>> = [];
  for (const [index, case_] of cases.entries()) {
    if (!_isMapping(case_)) continue;
    const autoid = String(case_.autoid ?? "");
    if (autoid && ledger_faces[autoid] === _stepStructureFace(case_)) continue;
    strip_engine_slots(case_);
    violations.push(...step_structure_violations(case_, { index, object_kinds: objectKinds }));
  }
  if (!violations.length) return;
  const budgeted = budget_violations(violations);
  throw new MachineMindmapContentError(JSON.stringify({ violations: budgeted }), { code: String(budgeted[0]?.code ?? "step_structure_missing") });
}

export function submit_machine_mindmap_payload(outputs_root: string | P, out_name: string, dispatch_id: string, payload: Record<string, any>): MachineMindmapSubmissionReceipt {
  const { MachineMindmapError, validate_machine_mindmap_payload } = require("../../../case_compiler/mindmap_contract_projector");
  const [name, identity] = _validateIdentity(out_name, dispatch_id);
  const envelope: Record<string, any> = JSON.parse(JSON.stringify(payload));
  const inlineCases = envelope.cases;
  let ledgerFaces: Record<string, string> = {};
  const artifactPath = machine_mindmap_artifact_path(outputs_root, name);
  const commit = (): void => {
    const binding = envelope.__binding;
    delete envelope.__binding;
    const preparedBindingSha256 = envelope.__binding_sha256;
    delete envelope.__binding_sha256;
    if (envelope.cases && Array.isArray(envelope.cases) && envelope.cases.length) {
      let sourceMaterialized = false;
      try {
        const { fill_mechanical_fields } = require("../../../case_compiler/mindmap_contract_projector");
        const sourceBytes = read_regular_nofollow(nodePath.join(_batchPath(outputs_root, name), "mindmap_source.json"), {
          errorType: MachineMindmapSubmissionError,
          invalid_message: "mindmap source path is invalid",
          directory_message: "mindmap source parent is unavailable",
          open_message: "mindmap source is unavailable",
          bounds_message: "mindmap source exceeds its boundary",
          changed_message: "mindmap source changed while reading",
          max_bytes: _MAX_ARTIFACT_BYTES,
          min_bytes: 1,
          trusted_root: lexical_absolute(String(outputs_root)),
        }) as Buffer;
        fill_mechanical_fields(envelope, sourceBytes.toString("utf8").replace(/^﻿?/, ""));
        sourceMaterialized = true;
      } catch {}
      const { case_status_mismatches, normalize_submission_case_statuses, primary_expectation_projection_problems } = require("../../../case_compiler/mindmap_contract_projector");
      for (const case_ of envelope.cases ?? []) {
        if (!sourceMaterialized || !_isMapping(case_)) continue;
        const primaryProblems = primary_expectation_projection_problems(case_);
        if (primaryProblems.length) {
          const [field, code] = primaryProblems[0];
          throw new MachineMindmapContentError(`case ${case_.autoid}: ${field} is empty despite authored expectation atoms in expectations_by_step`, { code });
        }
        normalize_submission_case_statuses(case_);
        const mismatches = case_status_mismatches(case_);
        if (mismatches.length) {
          const [field, actual] = mismatches[0];
          throw new MachineMindmapContentError(`case ${case_.autoid}: ${field} cannot be validated against the submitted assertion fields (${JSON.stringify(actual)})`, { code: "case_status_mismatch" });
        }
      }
      _rejectInlineStepStructure(envelope, ledgerFaces);
      let document: Record<string, any>;
      try {
        document = validate_machine_mindmap_payload(envelope);
      } catch (exc: any) {
        if (exc instanceof MachineMindmapError) {
          throw new MachineMindmapContentError(String(exc instanceof Error ? exc.message : exc), { code: "mindmap_schema_invalid" });
        }
        throw exc;
      }
      const cases = document.cases;
      const declaredCount = document.case_count;
      if (document.schema !== "ist.machine-mindmap" || typeof document.source !== "string" || !String(document.source ?? "").trim() || !Array.isArray(cases) || cases.some((c: any) => !_isMapping(c)) || typeof declaredCount !== "number" || !Number.isInteger(declaredCount) || declaredCount !== cases.length) {
        throw new MachineMindmapContentError("machine mindmap structured payload is invalid: schema must be ist.machine-mindmap, source must be a non-empty string, cases must be a list of objects, and case_count must equal len(cases)", { code: "mindmap_payload_invalid" });
      }
      const raw = Buffer.from(JSON.stringify(document, (_k, v) => (typeof v === "number" && !Number.isFinite(v) ? null : v), 2), "utf8");
      if (!raw.length || raw.length > _MAX_ARTIFACT_BYTES) {
        throw new MachineMindmapContentError("machine mindmap artifact exceeds its byte budget", { code: "mindmap_budget_exceeded" });
      }
      validate_json_budget(raw, { errorType: MachineMindmapContentError as any, message: "machine mindmap exceeds the JSON structure budget" } as any);
      const digest = sha256_bytes(raw);
      let existing: Buffer | null;
      try {
        existing = read_regular_nofollow(artifactPath._p, {
          errorType: MachineMindmapSubmissionError,
          invalid_message: "machine mindmap artifact path is invalid",
          directory_message: "machine mindmap artifact parent is unavailable",
          open_message: "machine mindmap artifact is unavailable",
          bounds_message: "machine mindmap artifact exceeds its boundary",
          changed_message: "machine mindmap artifact changed while reading",
          max_bytes: _MAX_ARTIFACT_BYTES,
          min_bytes: 1,
          preserve_missing: true,
          trusted_root: lexical_absolute(String(outputs_root)),
          require_current_uid: true,
        }) as Buffer;
      } catch (exc) {
        if ((exc as any)?.code === "ENOENT" || (exc instanceof MachineMindmapSubmissionError && /unavailable/.test((exc as Error).message))) {
          existing = null;
        } else {
          throw exc;
        }
      }
      if (existing !== null && !existing.equals(raw)) {
        throw new MachineMindmapSubmissionError("machine mindmap artifact already exists for this dispatch");
      }
      if (existing === null) {
        atomic_write_bytes_nofollow(artifactPath._p, raw, { errorType: MachineMindmapSubmissionError, invalid_message: "machine mindmap artifact path is invalid", unavailable_message: "machine mindmap artifact cannot be committed safely", create_parents: false, mode: 0o600 });
      }
      _sealRecomposeCommandGroundingLocked(lexical_absolute(String(outputs_root)), name, identity, digest);
      const submitted = { schema: SCHEMA, out_name: name, dispatch_id: identity, status: "submitted", artifact_sha256: digest, artifact_size: raw.length, binding, binding_sha256: preparedBindingSha256 };
      atomic_write_bytes_nofollow(machine_mindmap_submission_path(outputs_root, name)._p, canonical_json(submitted, { ensure_ascii: false }), { errorType: MachineMindmapSubmissionError, invalid_message: "machine mindmap submission receipt path is invalid", unavailable_message: "machine mindmap submission receipt cannot be committed", create_parents: false, mode: 0o600 });
    }
  };
  _withSubmissionLock(_batchPath(outputs_root, name), () => {
    assert_machine_mindmap_submission_open(outputs_root, name, identity);
    const preparedReceipt = read_machine_mindmap_submission(outputs_root, name, identity);
    const scope = _currentRecomposeDispatch;
    if (scope !== null) {
      if (scope.outputs_root !== lexical_absolute(String(outputs_root)) || scope.out_name !== name || scope.dispatch_id !== identity || scope.binding_sha256 !== preparedReceipt.binding_sha256) {
        throw new MachineMindmapSubmissionError("machine mindmap submission dispatch binding changed after scope validation");
      }
    }
    const binding = preparedReceipt.binding;
    const canonicalized = _ARTIFACT_BINDING_KEYS.filter((key) => key in envelope && JSON.stringify(envelope[key]) !== JSON.stringify(binding[key]));
    if (canonicalized.length) {
      logger.warning("ignored non-authoritative machine mindmap binding fields: %s", canonicalized.join(","));
    }
    for (const key of _ARTIFACT_BINDING_KEYS) {
      envelope[key] = binding[key];
    }
    envelope.__binding = binding;
    envelope.__binding_sha256 = preparedReceipt.binding_sha256;
    const { MachineMindmapPartsError, _caseIsHollow: _unused, read_machine_mindmap_parts } = require("./recompose_parts");
    void _unused;
    let snapshot: any = null;
    try {
      snapshot = read_machine_mindmap_parts(outputs_root, name, { binding_sha256: preparedReceipt.binding_sha256, preserve_missing: true });
    } catch (exc) {
      if (exc instanceof MachineMindmapPartsError) {
        if (/unavailable/.test(String((exc as Error).message))) {
          snapshot = null;
        } else {
          throw new MachineMindmapSubmissionError("machine mindmap parts ledger is present but unverifiable");
        }
      } else {
        throw new MachineMindmapSubmissionError("machine mindmap parts ledger is present but unverifiable");
      }
    }
    const { _caseIsHollow } = require("./recompose_parts");
    if (snapshot !== null && snapshot.cases && Object.keys(snapshot.cases).length) {
      const merged: Record<string, Record<string, any>> = { ...snapshot.cases };
      const signed = [...snapshot.case_autoids];
      ledgerFaces = {};
      for (const [autoid, value] of Object.entries<any>(snapshot.cases)) {
        if (_isMapping(value)) ledgerFaces[autoid] = _stepStructureFace(value);
      }
      const extra: Array<Record<string, any>> = [];
      for (const case_ of inlineCases ?? []) {
        if (!_isMapping(case_)) {
          throw new MachineMindmapContentError("machine mindmap structured payload is invalid: every inline case must be a JSON object", { code: "mindmap_payload_invalid" });
        }
        const autoid = case_.autoid;
        if (typeof autoid === "string" && (autoid in merged || signed.includes(autoid))) {
          merged[autoid] = case_;
        } else {
          extra.push(case_);
        }
      }
      const ordered = signed.filter((aid: string) => aid in merged && !_caseIsHollow(merged[aid])).map((aid: string) => merged[aid]).concat(extra);
      envelope.cases = ordered;
      envelope.case_count = ordered.length;
    }
    commit();
  });
  return read_machine_mindmap_submission(outputs_root, name, identity);
}

export function verify_machine_mindmap_submission_commit(
  outputs_root: string | P,
  out_name: string,
  dispatch_id: string,
  opts: { expected_binding?: Record<string, any> | null } = {},
): [MachineMindmapSubmissionReceipt, Record<string, any>, Record<string, number>] {
  const { MachineMindmapError, load_machine_mindmap } = require("../../../case_compiler/mindmap_contract_projector");
  const { MACHINE_MINDMAP_BUCKETS } = require("./recompose_parts");
  const receipt = opts.expected_binding !== null && opts.expected_binding !== undefined
    ? assert_machine_mindmap_submission_binding(outputs_root, out_name, dispatch_id, { expected_binding: opts.expected_binding })
    : read_machine_mindmap_submission(outputs_root, out_name, dispatch_id);
  if (receipt.status !== "submitted") {
    throw new MachineMindmapSubmissionError("machine mindmap submission has no durable commit");
  }
  const artifactPath = machine_mindmap_artifact_path(outputs_root, out_name);
  let payload: Record<string, any>;
  let digest: string;
  try {
    [payload, digest] = load_machine_mindmap(artifactPath);
  } catch (exc: any) {
    if (exc instanceof MachineMindmapError) {
      throw new MachineMindmapSubmissionError(String(exc instanceof Error ? exc.message : exc));
    }
    throw exc;
  }
  let size: number;
  try {
    size = fs.lstatSync(artifactPath._p).size;
  } catch (exc) {
    throw new MachineMindmapSubmissionError("machine mindmap submitted artifact is unavailable");
  }
  if (digest !== receipt.artifact_sha256 || size !== receipt.artifact_size) {
    throw new MachineMindmapSubmissionError("machine mindmap submitted artifact identity changed");
  }
  const rawCases = payload.cases;
  const caseCount = payload.case_count;
  if (!Array.isArray(rawCases) || rawCases.some((c: any) => !_isMapping(c)) || typeof caseCount !== "number" || !Number.isInteger(caseCount) || caseCount !== rawCases.length) {
    throw new MachineMindmapSubmissionError("machine mindmap submitted case count is invalid");
  }
  const bucketCounts: Record<string, number> = Object.fromEntries((MACHINE_MINDMAP_BUCKETS as readonly string[]).map((n) => [n, 0]));
  for (const case_ of rawCases) {
    const bucket = case_.bucket;
    if (typeof bucket !== "string" || !(bucket in bucketCounts)) {
      throw new MachineMindmapSubmissionError("machine mindmap submitted bucket is invalid");
    }
    bucketCounts[bucket] += 1;
  }
  return [receipt, payload, bucketCounts];
}

export function canonical_machine_mindmap_submission_result(outputs_root: string | P, out_name: string, dispatch_id: string, opts: { expected_binding?: Record<string, any> | null } = {}): string {
  const { render_mindmap_recompose_result } = require("../compile_engine/recompose_protocol");
  const [receipt, payload, bucketCounts] = verify_machine_mindmap_submission_commit(outputs_root, out_name, dispatch_id, opts);
  const caseCount = payload.case_count;
  return render_mindmap_recompose_result({ schema: "ist.mindmap-recompose-result", status: "produced", artifact: `${receipt.out_name}/${_ARTIFACT_NAME}`, summary: { case_count: caseCount, bucket_counts: bucketCounts, message_zh: "机器脑图已通过受信任派发的单次结构化提交" }, error_code: null, reason_zh: null });
}
