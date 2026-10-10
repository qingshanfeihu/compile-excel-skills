// 生成：tools/extract_engine.py ← InfoTest main/ist_core/worker_device_context.py（sha256 8275c23cf9387e3c）。不在这里手改。
import fs from "node:fs";
import crypto from "node:crypto";

import {
  deepcopy,
  P,
  PyValueError,
  pyJsonDumps,
} from "../_py";
import { accepts_engine_schema, engine_schema_id } from "../common/engine_track_schema";
import { canonical_persisted_value, persisted_surface_sha256, scrub_value } from "./security_scrub";

function sha256Hex(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

const _DEFAULT_MAX_ROUNDS = 3;
const _MAX_ROUNDS_CEILING = 10;
const _DEFAULT_MAX_PROBE_CALLS = 5;
const _MAX_PROBE_CALLS_CEILING = 5;
const _COMPILE_LEARNING_GATES = new Set(['mutation_contract_invalid', 'assertion_type_invalid', 'assertion_type_derivation_failed', 'provenance_parse_failed', 'provenance_step_count_mismatch', 'blocks_parse_failed', 'blocks_type_invalid', 'blocks_invalid']);

let _SCOPE: WorkerDeviceSession | null = null;
let _DEVICE_ACCESS = false;
let _FORK_SCOPE: Record<string, string> | null = null;
const _SESSIONS: Map<string, WorkerDeviceSession> = new Map();
const _COMPLETED: Record<string, any>[] = [];
const _SESSION_OUTCOMES: Record<string, any>[] = [];
const _QUARANTINED: Record<string, any>[] = [];
const _REVOKED_DISPATCHES: Set<string> = new Set();
const _DISPATCH_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$/;
export const SESSION_ADMISSION_REJECTION_EVENT = 'session_admission_rejected';
export const SESSION_ADMISSION_REJECTION_SITE = 'worker_session_admission';
export const SESSION_ADMISSION_IDENTITY_FIELDS = ['autoid', 'fork_id', 'dispatch_id', 'batch_run_id'];
const _ADMISSION_REJECTION_FIELDS = new Set([...SESSION_ADMISSION_IDENTITY_FIELDS, 'code', 'detail', 'message_sha256', 'exception_type', 'source_manifest_ref', 'source_manifest_sha256', 'source_case_slice_sha256', 'record_id']);
export const WORKER_READ_ONLY_PROBE_CONTRACT = 'ist.worker_probe.read_only';
const _MAX_WORKER_JOURNAL_BYTES = 64 * 1024 * 1024;
const _MAX_WORKER_JOURNAL_RECORD_BYTES = 1024 * 1024;
export const COMMAND_HEADS_QUERY_SCHEMA = 'ist.command-heads-query';
const _COMMAND_HEADS_RECEIPT_KEYS = new Set(['schema', 'status', 'module_prefix', 'device_build', 'capability_generation_id', 'capability_manifest_sha256', 'projection_version', 'count', 'heads', 'receipt_id', 'result_sha256']);
export const COMMAND_HEADS_RECEIPT_REDACTION_FOLDED = 'command_heads_receipt_redaction_folded';
export const COMMAND_HEADS_RECEIPT_VALIDATION_CODES = new Set(['command_heads_receipt_shape_invalid', 'command_heads_expected_identity_invalid', 'command_heads_receipt_schema_invalid', 'command_heads_receipt_incomplete', 'command_heads_receipt_inventory_invalid', COMMAND_HEADS_RECEIPT_REDACTION_FOLDED, 'command_heads_receipt_identity_mismatch', 'command_heads_receipt_hash_mismatch', 'command_heads_receipt_id_invalid']);
const _REDACTION_MARKER = '****';

function _redaction_folded_inventory(heads: any, opts: { count: number }): boolean {
  if (!Array.isArray(heads) || heads.length === 0) {
    return false;
  }
  if (heads.some((head: any) => typeof head !== "string")) {
    return false;
  }
  if (opts.count !== heads.length || JSON.stringify(heads) !== JSON.stringify([...heads].sort())) {
    return false;
  }
  const seen = new Set<string>();
  const duplicated = new Set<string>();
  for (const head of heads) {
    if (seen.has(head)) {
      duplicated.add(head);
    }
    seen.add(head);
  }
  if (duplicated.size === 0) {
    return false;
  }
  return [...duplicated].every((head) => head.includes(_REDACTION_MARKER));
}
export const COMMAND_HEADS_SESSION_RECEIPTS_MISSING = 'command_heads_session_receipts_missing';
export const COMMAND_HEADS_RECEIPT_SEQUENCE_MISMATCH = 'command_heads_receipt_sequence_mismatch';
export const NOT_COMPILABLE_HEADS_SUMMARY_MISMATCH = 'not_compilable_report_heads_summary_mismatch';
export const NOT_COMPILABLE_HEADS_REFS_MISSING = 'not_compilable_report_heads_refs_missing';
export const NOT_COMPILABLE_HEADS_REF_UNKNOWN = 'not_compilable_report_heads_ref_unknown';
export const NOT_COMPILABLE_HEADS_VALIDATION_CODES = new Set([...COMMAND_HEADS_RECEIPT_VALIDATION_CODES, COMMAND_HEADS_SESSION_RECEIPTS_MISSING, COMMAND_HEADS_RECEIPT_SEQUENCE_MISMATCH, NOT_COMPILABLE_HEADS_SUMMARY_MISMATCH, NOT_COMPILABLE_HEADS_REFS_MISSING, NOT_COMPILABLE_HEADS_REF_UNKNOWN]);
export const NOT_COMPILABLE_REASON_NO_CLI = 'no_cli_equivalent';
export const NOT_COMPILABLE_REASON_ENV_GAP = 'environment_prerequisite_gap';
export const NOT_COMPILABLE_REASON_AUTHOR_GAP = 'author_definition_gap';
export const NOT_COMPILABLE_REASON_AUTHOR_CONFLICT = 'author_definition_conflict';
export const NOT_COMPILABLE_REASON_CODES = new Set([NOT_COMPILABLE_REASON_NO_CLI, NOT_COMPILABLE_REASON_ENV_GAP, NOT_COMPILABLE_REASON_AUTHOR_GAP, NOT_COMPILABLE_REASON_AUTHOR_CONFLICT]);
export const AUTHOR_SIDE_NOT_COMPILABLE_REASON_CODES = new Set([NOT_COMPILABLE_REASON_AUTHOR_GAP, NOT_COMPILABLE_REASON_AUTHOR_CONFLICT]);
export const WORKER_CLAIM_SCHEMA = 'ist.worker-claim';
export const WORKER_CLAIM_REJECTION_CODES = new Set(['author_gap_expectation_already_signed', 'environment_gap_unverified', 'no_cli_signed_expectation_unverified', 'author_conflict_surfaces_insufficient', 'author_conflict_expectation_unsigned']);

export function command_heads_prefix_shape_valid(prefix: any): boolean {
  return typeof prefix === "string" && !!prefix && prefix === prefix.trim().toLowerCase() && !prefix.includes('  ') && ![...prefix].some((ch) => /\s/.test(ch) && ch !== ' ') && ![...prefix].some((ch) => ch.codePointAt(0)! < 32);
}

export function command_head_matches_prefix(head: string, prefix: string): boolean {
  const folded = String(head).toLowerCase();
  return folded === prefix || folded.startsWith(prefix + ' ');
}

export function recorded_command_heads(inventory: Record<string, any>, prefix: any): string[] {
  const normalized = String(prefix || '').split(/\s+/).filter((s) => s).join(' ').toLowerCase();
  if (!normalized) {
    return [];
  }
  return Object.keys((inventory || {}).headers || {}).filter((head) => command_head_matches_prefix(String(head), normalized)).sort();
}

export function validate_command_heads_query_receipt(receipt: any, expected_identity: Record<string, string>): string {
  if (!_isDict(receipt) || !_sameKeys(receipt, _COMMAND_HEADS_RECEIPT_KEYS)) {
    return 'command_heads_receipt_shape_invalid';
  }
  if (!_isDict(expected_identity)) {
    return 'command_heads_expected_identity_invalid';
  }
  const dispatch_id = String(expected_identity.dispatch_id || '').trim();
  const capability_build = String(expected_identity.capability_build || '').trim();
  const generation_id = String(expected_identity.capability_generation_id || '').trim();
  const manifest_sha = String(expected_identity.capability_manifest_sha256 || '').trim().toLowerCase();
  if (!_DISPATCH_ID_RE.test(dispatch_id) || !capability_build || !generation_id || !/^[0-9a-f]{64}$/.test(manifest_sha)) {
    return 'command_heads_expected_identity_invalid';
  }
  if (receipt.schema !== COMMAND_HEADS_QUERY_SCHEMA) {
    return 'command_heads_receipt_schema_invalid';
  }
  if (receipt.status !== 'complete') {
    return 'command_heads_receipt_incomplete';
  }
  const prefix = receipt.module_prefix;
  const projection_version = receipt.projection_version;
  const heads = receipt.heads;
  const count = receipt.count;
  if (!command_heads_prefix_shape_valid(prefix) || typeof projection_version !== "string" || !projection_version.trim() || [...projection_version].some((ch) => ch.codePointAt(0)! < 32) || !Array.isArray(heads) || typeof count !== "number" || !Number.isInteger(count) || typeof count === "boolean" || heads.some((head: any) => typeof head !== "string" || !head || head !== head.trim() || !command_head_matches_prefix(head, prefix))) {
    return 'command_heads_receipt_inventory_invalid';
  }
  if (JSON.stringify(heads) !== JSON.stringify([...new Set(heads)].sort()) || count !== heads.length) {
    if (_redaction_folded_inventory(heads, { count })) {
      return COMMAND_HEADS_RECEIPT_REDACTION_FOLDED;
    }
    return 'command_heads_receipt_inventory_invalid';
  }
  if (receipt.device_build !== capability_build || receipt.capability_generation_id !== generation_id || receipt.capability_manifest_sha256 !== manifest_sha) {
    return 'command_heads_receipt_identity_mismatch';
  }
  const material: Record<string, any> = {};
  for (const key of ['schema', 'status', 'module_prefix', 'device_build', 'capability_generation_id', 'capability_manifest_sha256', 'projection_version', 'count', 'heads']) {
    material[key] = receipt[key];
  }
  const expected_hash = sha256Hex(Buffer.from(pyJsonDumps(material, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf8'));
  const result_sha = receipt.result_sha256;
  if (result_sha !== expected_hash) {
    return 'command_heads_receipt_hash_mismatch';
  }
  const receipt_id = receipt.receipt_id;
  const receipt_prefix = `${dispatch_id}:heads:`;
  if (typeof receipt_id !== "string" || !receipt_id.startsWith(receipt_prefix)) {
    return 'command_heads_receipt_id_invalid';
  }
  const suffix = receipt_id.slice(receipt_prefix.length).split(':');
  if (suffix.length !== 2 || !/^\d+$/.test(suffix[0]) || parseInt(suffix[0], 10) < 1 || suffix[1] !== expected_hash.slice(0, 16)) {
    return 'command_heads_receipt_id_invalid';
  }
  return '';
}

function _isDict(v: any): v is Record<string, any> {
  return v !== null && typeof v === "object" && !Array.isArray(v) && !(v instanceof Set) && !(v instanceof Map) && !Buffer.isBuffer(v);
}

function _sameKeys(obj: Record<string, any>, keys: Set<string>): boolean {
  const ks = Object.keys(obj);
  return ks.length === keys.size && ks.every((k) => keys.has(k));
}

export function validate_command_heads_session_receipts(receipts: any, expected_identity: Record<string, string>): [Record<string, Record<string, any>>, string] {
  if (!Array.isArray(receipts) || receipts.length === 0) {
    return [{}, COMMAND_HEADS_SESSION_RECEIPTS_MISSING];
  }
  const by_id: Record<string, Record<string, any>> = {};
  let sequence = 0;
  for (const raw_receipt of receipts) {
    sequence += 1;
    const receipt_error = validate_command_heads_query_receipt(raw_receipt, expected_identity);
    if (receipt_error) {
      return [{}, receipt_error];
    }
    const receipt = { ...raw_receipt };
    const result_sha256 = String(receipt.result_sha256 || '');
    const expected_receipt_id = `${expected_identity.dispatch_id ?? ''}:heads:${sequence}:${result_sha256.slice(0, 16)}`;
    if (receipt.receipt_id !== expected_receipt_id) {
      return [{}, COMMAND_HEADS_RECEIPT_SEQUENCE_MISMATCH];
    }
    by_id[expected_receipt_id] = receipt;
  }
  return [by_id, ''];
}

export function validate_not_compilable_heads_summary(summaries: any, receipts_by_id: Record<string, Record<string, any>>): string {
  const summary_ids = (summaries || []).filter((item: any) => _isDict(item)).map((item: any) => String(item.receipt_id || ''));
  if (!Array.isArray(summaries) || summaries.length === 0 || summary_ids.length !== new Set(summary_ids).size || summaries.some((item: any) => {
    if (!_isDict(item) || !_sameKeys(item, new Set(['receipt_id', 'module_prefix', 'result_sha256', 'head_count']))) return true;
    const rid = String(item.receipt_id || '');
    if (!(rid in receipts_by_id)) return true;
    return item.module_prefix !== receipts_by_id[rid].module_prefix || item.result_sha256 !== receipts_by_id[rid].result_sha256 || item.head_count !== receipts_by_id[rid].count;
  })) {
    return NOT_COMPILABLE_HEADS_SUMMARY_MISMATCH;
  }
  return '';
}

export function canonical_source_case_slice(value: any, opts: { autoid: string }): Record<string, any> {
  if (!_isDict(value)) {
    throw new PyValueError('source case slice must be an object');
  }
  const aid = String(value.autoid || '').trim();
  if (aid !== String(opts.autoid || '').trim() || !/^\d{18}$/.test(aid)) {
    throw new PyValueError('source case slice autoid does not match the worker session');
  }
  const raw_steps = value.step_intents;
  if (!Array.isArray(raw_steps)) {
    throw new PyValueError('source case slice step_intents must be an array');
  }
  const steps = [];
  for (const item of raw_steps) {
    if (!_isDict(item)) {
      throw new PyValueError('source case slice contains a non-object step');
    }
    steps.push({ desc: String(item.desc || ''), expected: String(item.expected || '') });
  }
  return { autoid: aid, title: String(value.title || ''), step_intents: steps };
}

export function canonical_source_case_slice_sha256(value: any, opts: { autoid: string }): string {
  const canonical = canonical_source_case_slice(value, opts);
  return sha256Hex(Buffer.from(pyJsonDumps(canonical, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf8'));
}

export function validate_source_case_anchors(sources: any, source_case_slice: any, opts: { autoid: string; source_case_slice_sha256: string }): string {
  let canonical: Record<string, any>;
  try {
    canonical = canonical_source_case_slice(source_case_slice, opts);
  } catch (e) {
    if (e instanceof PyValueError || e instanceof Error) {
      return 'source_case_slice_invalid';
    }
    throw e;
  }
  const expected_sha = String(opts.source_case_slice_sha256 || '').trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(expected_sha) || canonical_source_case_slice_sha256(canonical, opts) !== expected_sha) {
    return 'source_case_slice_identity_mismatch';
  }
  if (!Array.isArray(sources) || sources.length === 0) {
    return 'source_anchors_invalid';
  }
  const _normalized = (text: any): string => {
    let value = String(text ?? '');
    value = value.replace(/\\r/g, ' ').replace(/\\n/g, ' ').replace(/\\t/g, ' ');
    value = value.replace(/\r/g, ' ').replace(/\n/g, ' ').replace(/\t/g, ' ');
    value = value.replace(/ /g, ' ');
    return value.split(/\s+/).filter((s) => s).join(' ');
  };
  const corpus_by_kind: Record<string, string[]> = {
    title: [String(canonical.title || '')],
    step: (canonical.step_intents as any[]).map((item: any) => String(item.desc || '')),
    expected: (canonical.step_intents as any[]).map((item: any) => String(item.expected || '')),
  };
  for (let index = 0; index < sources.length; index++) {
    const source = sources[index];
    if (!_isDict(source) || !_sameKeys(source, new Set(['kind', 'quote']))) {
      return `source_anchor_shape_invalid:${index}`;
    }
    const kind = String(source.kind || '').trim();
    const quote = String(source.quote || '').trim();
    if (!(kind in corpus_by_kind) || !quote) {
      return `source_anchor_shape_invalid:${index}`;
    }
    const normalized_quote = _normalized(quote);
    if (!corpus_by_kind[kind].some((corpus) => corpus.includes(quote) || _normalized(corpus).includes(normalized_quote))) {
      return `source_anchor_quote_not_bound:${index}`;
    }
  }
  return '';
}

function _validated_source_binding(opts: { autoid: string; source_manifest_ref: string; source_manifest_sha256: string; source_case_slice_sha256_value: string; source_case_slice: any }): [string, string, string, Record<string, any>] {
  const { autoid, source_manifest_ref, source_manifest_sha256, source_case_slice_sha256_value, source_case_slice } = opts;
  const values = [source_manifest_ref, source_manifest_sha256, source_case_slice_sha256_value, source_case_slice];
  const present = (value: any): boolean => !(value === '' || value === null || value === undefined || (_isDict(value) && Object.keys(value).length === 0));
  if (!values.some(present)) {
    return ['', '', '', {}];
  }
  if (!values.every(present)) {
    throw new PyValueError('worker source binding is incomplete');
  }
  const ref = String(source_manifest_ref).trim();
  const manifest_sha = String(source_manifest_sha256).trim().toLowerCase();
  const slice_sha = String(source_case_slice_sha256_value).trim().toLowerCase();
  if (!ref || ref.startsWith('/') || new P(ref.replace(/\\/g, '/')).parts.includes('..') || !/^[0-9a-f]{64}$/.test(manifest_sha) || !/^[0-9a-f]{64}$/.test(slice_sha)) {
    throw new PyValueError('worker source binding identity is invalid');
  }
  const canonical = canonical_source_case_slice(source_case_slice, { autoid });
  if (canonical_source_case_slice_sha256(canonical, { autoid }) !== slice_sha) {
    throw new PyValueError('worker source case slice digest mismatch');
  }
  const { lexical_path_inside_root, read_regular_nofollow } = require("../case_compiler/_sealed_io");
  const sh = require("./compile_engine/_shared");
  const project_root = sh.project_root();
  const outputs_root = sh.outputs_root();
  const p = lexical_path_inside_root(project_root.joinpath(ref), outputs_root, {
    error_type: PyValueError,
    traversal_message: 'worker source manifest traversal is forbidden',
    outside_message: 'worker source manifest escaped outputs root',
  });
  const raw = read_regular_nofollow(p, {
    trusted_root: outputs_root,
    error_type: PyValueError,
    invalid_message: 'worker source manifest path is invalid',
    directory_message: 'worker source manifest directory is unavailable',
    open_message: 'worker source manifest is unavailable',
    bounds_message: 'worker source manifest exceeds its size boundary',
    changed_message: 'worker source manifest changed while being read',
    max_bytes: 32 * 1024 * 1024,
    min_bytes: 1,
    require_current_uid: true,
  });
  if (sha256Hex(raw) !== manifest_sha) {
    throw new PyValueError('worker source manifest digest mismatch');
  }
  let manifest: any;
  try {
    manifest = JSON.parse(raw.toString('utf8'));
  } catch (exc) {
    throw new PyValueError('worker source manifest is not valid JSON');
  }
  const matches = _isDict(manifest) ? (manifest.cases || []).filter((item: any) => _isDict(item) && String(item.autoid || '') === autoid) : [];
  if (matches.length !== 1) {
    throw new PyValueError('worker source manifest does not contain exactly one bound case');
  }
  const from_manifest = canonical_source_case_slice(matches[0], { autoid });
  if (JSON.stringify(from_manifest) !== JSON.stringify(canonical)) {
    throw new PyValueError('worker source case slice does not match the sealed manifest');
  }
  return [ref, manifest_sha, slice_sha, canonical];
}

export function valid_session_admission_rejection(record: any, opts: { require_identity?: boolean } = {}): boolean {
  const require_identity = opts.require_identity ?? true;
  const { SESSION_ADMISSION_REJECTION_CODES } = require("./compile_engine/engine_quarantine");
  if (!_isDict(record) || !_sameKeys(record, _ADMISSION_REJECTION_FIELDS) || Object.values(record).some((value) => typeof value !== "string") || !SESSION_ADMISSION_REJECTION_CODES.has(record.code) || record.exception_type !== 'SessionAdmissionError' || !/^[0-9a-f]{64}$/.test(record.message_sha256)) {
    return false;
  }
  if (require_identity && (!/^[0-9]{18}$/.test(record.autoid) || !record.fork_id.trim() || !_DISPATCH_ID_RE.test(record.dispatch_id) || !_DISPATCH_ID_RE.test(record.batch_run_id))) {
    return false;
  }
  const body: Record<string, any> = {};
  for (const [key, value] of Object.entries(record)) {
    if (key !== 'record_id') body[key] = value;
  }
  return persisted_surface_sha256(body) === record.record_id;
}

function _session_journal_path(session: WorkerDeviceSession): P {
  const sh = require("./compile_engine/_shared");
  const identity = [String(session.batch_run_id || ''), String(session.dispatch_id || ''), String(session.autoid || ''), String(session.fork_id || '')].join('|');
  const stem = sha256Hex(Buffer.from(identity, 'utf8')).slice(0, 32);
  return sh.project_root().joinpath('runtime', 'worker_oracle_journal', `${stem}.jsonl`);
}

export function persist_worker_session_event(session: WorkerDeviceSession, event: Record<string, any>): boolean {
  const record = scrub_value({
    schema: 'worker_session_event',
    ...event,
    autoid: session.autoid,
    fork_id: session.fork_id,
    dispatch_id: session.dispatch_id,
    batch_run_id: session.batch_run_id,
    bed_lease_id: session.bed_lease_id,
    env_id: session.env_id,
    execution_bed: session.actual_bed || session.expected_bed,
    execution_build: session.expected_build,
    execution_module: session.expected_module,
    capability_bed: session.capability_bed,
    capability_full_version: session.capability_full_version,
    capability_version: session.capability_version,
    capability_build: session.capability_build,
    capability_generation_id: session.capability_generation_id,
    capability_manifest_sha256: session.capability_manifest_sha256,
    capability_projection_sha256: session.capability_projection_sha256,
    source_manifest_ref: session.source_manifest_ref,
    source_manifest_sha256: session.source_manifest_sha256,
    source_case_slice_sha256: session.source_case_slice_sha256,
    remote_artifact_sha256: session.current_remote_artifact_sha256,
  });
  try {
    const p = _session_journal_path(session);
    const sh = require("./compile_engine/_shared");
    const { open_directory_nofollow, open_or_create_regular_at_nofollow } = require("../case_compiler/_sealed_io");
    const root = sh.project_root();
    if (root.is_symlink()) {
      throw new PyValueError('worker journal refuses a symbolic-link project root');
    }
    const payload = Buffer.from(pyJsonDumps(record, { ensure_ascii: false, sort_keys: true }) + '\n', 'utf8');
    if (payload.length > _MAX_WORKER_JOURNAL_RECORD_BYTES) {
      throw new PyValueError('worker journal record exceeds its byte budget');
    }
    const dir_fd = open_directory_nofollow(p.parent, {
      error_type: PyValueError,
      invalid_message: 'worker journal parent is invalid',
      unavailable_message: 'worker journal parent is unavailable',
      create_missing: true,
      create_mode: 0o700,
    });
    try {
      const fd = open_or_create_regular_at_nofollow(dir_fd, p.name, fs.constants.O_WRONLY | fs.constants.O_APPEND, {
        mode: 0o600,
        error_type: PyValueError,
        unavailable_message: 'worker journal cannot be opened safely',
      });
      try {
        const info = fs.fstatSync(fd);
        if (info.size > _MAX_WORKER_JOURNAL_BYTES) {
          throw new PyValueError('worker journal exceeds its byte budget');
        }
        if (info.size + payload.length > _MAX_WORKER_JOURNAL_BYTES) {
          throw new PyValueError('worker journal exceeds its byte budget');
        }
        let offset = 0;
        while (offset < payload.length) {
          const written = fs.writeSync(fd, payload, offset, payload.length - offset);
          if (written <= 0) {
            throw new Error('short write to worker journal');
          }
          offset += written;
        }
        fs.fsyncSync(fd);
      } finally {
        fs.closeSync(fd);
      }
      fs.fsyncSync(dir_fd);
    } finally {
      fs.closeSync(dir_fd);
    }
    return true;
  } catch {
    return false;
  }
}

export function worker_device_loop_enabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes(String(process.env['IST_WORKER_DEVICE_LOOP'] ?? '1').trim().toLowerCase());
}

export function worker_device_access_scope<T>(allowed: boolean, fn: () => T): T {
  const prev = _DEVICE_ACCESS;
  _DEVICE_ACCESS = allowed === true;
  try {
    return fn();
  } finally {
    _DEVICE_ACCESS = prev;
  }
}

export function worker_device_access_enabled(): boolean {
  return _DEVICE_ACCESS === true;
}

export function worker_device_max_rounds(): number {
  const raw = process.env['IST_WORKER_DEVICE_MAX_ROUNDS'] ?? String(_DEFAULT_MAX_ROUNDS);
  let parsed: number;
  try {
    const value = Number(String(raw).trim());
    if (!Number.isFinite(value)) {
      throw new PyValueError();
    }
    parsed = Math.trunc(value);
  } catch {
    parsed = _DEFAULT_MAX_ROUNDS;
  }
  return Math.max(1, Math.min(parsed, _MAX_ROUNDS_CEILING));
}

export function worker_device_infra_retries(): number {
  const raw = process.env['IST_WORKER_DEVICE_INFRA_RETRIES'] ?? '3';
  let parsed: number;
  try {
    parsed = parseInt(String(raw).trim(), 10);
    if (Number.isNaN(parsed)) throw new PyValueError();
  } catch {
    parsed = 3;
  }
  return Math.max(0, Math.min(parsed, 10));
}

export function worker_probe_max_calls(): number {
  const raw = process.env['IST_WORKER_PROBE_MAX_CALLS'] ?? String(_DEFAULT_MAX_PROBE_CALLS);
  let parsed: number;
  try {
    parsed = parseInt(String(raw).trim(), 10);
    if (Number.isNaN(parsed)) throw new PyValueError();
  } catch {
    parsed = _DEFAULT_MAX_PROBE_CALLS;
  }
  return Math.max(0, Math.min(parsed, _MAX_PROBE_CALLS_CEILING));
}

export class WorkerDeviceSession {
  skill: string;
  agent: string;
  autoid: string;
  fork_id: string;
  device_access: boolean;
  dispatch_id: string;
  batch_run_id: string;
  bed_lease_id: string;
  expected_bed: string;
  expected_build: string;
  expected_module: string;
  capability_bed: string;
  capability_full_version: string;
  capability_version: string;
  capability_build: string;
  capability_generation_id: string;
  capability_manifest_sha256: string;
  capability_projection_sha256: string;
  authored_round: number;
  source_manifest_ref: string;
  source_manifest_sha256: string;
  source_case_slice_sha256: string;
  source_case_slice: Record<string, any>;
  max_rounds: number;
  max_infra_retries: number;
  max_probe_calls: number;
  attempts: number;
  probe_calls: number;
  probe_exhausted: boolean;
  probe_evidence: Record<string, any>[];
  command_heads_query_receipts: Record<string, any>[];
  not_compilable_reports: Record<string, any>[];
  worker_claims: Record<string, any>[];
  engine_gaps: Record<string, any>[];
  authoring_accounts: Record<string, any>[];
  authoring_channel_rejection: Record<string, any>;
  admission_rejection: Record<string, any>;
  authoring_budget: Record<string, any>;
  account_supplement: Record<string, any>;
  unsupported_feature_reports: Record<string, any>[];
  probe_plan_keys: Set<string>;
  semantic_attempts: number;
  infrastructure_attempts: number;
  last_artifact_sha256: string;
  current_artifact_sha256: string;
  current_remote_artifact_sha256: string;
  lint_credential_id: string;
  current_attempt_id: string;
  current_prediction: Record<string, any>;
  prediction_chain: Record<string, any>[];
  last_verdict: string;
  last_fail_signatures: Set<any>;
  seen_fail_signatures: Set<any>;
  accumulated_fail_signatures: Set<any>;
  device_no_progress_history: Record<string, any>[];
  compile_no_progress_history: Record<string, any>[];
  compile_learning_history: Record<string, any>[];
  last_no_progress_decision: Record<string, any>;
  no_progress_decisions: Record<string, any>[];
  current_compile_revision: string;
  current_compile_attempt_id: string;
  current_compile_recorded: boolean;
  compile_attempts: Record<string, any>[];
  mechanical_case_submission_attempts: number;
  mechanical_case_rejections: Record<string, any>[];
  mechanical_case_accepted: Record<string, any>;
  gate_advisories: Record<string, any>[];
  mechanical_case_repair_disclosures: Record<string, any>[];
  last_mechanical_case_submission_body: Record<string, any>;
  compile_exhausted: boolean;
  stop_reason: string;
  in_flight: boolean;
  revoked: boolean;
  closed: boolean;
  _lease_cm: any;
  _environment_lease: any;
  _shared_binding: any;
  env_id: string;
  actual_bed: string;
  lease_acquired_at: number;
  lease_acquired_persisted: boolean;
  lease_released_persisted: boolean;
  shared_binding_persisted: boolean;
  lease_error: string;

  constructor(opts: Record<string, any> & { skill: string; agent: string; autoid: string; fork_id: string }) {
    this.skill = opts.skill;
    this.agent = opts.agent;
    this.autoid = opts.autoid;
    this.fork_id = opts.fork_id;
    this.device_access = opts.device_access ?? true;
    this.dispatch_id = opts.dispatch_id ?? '';
    this.batch_run_id = opts.batch_run_id ?? '';
    this.bed_lease_id = opts.bed_lease_id ?? '';
    this.expected_bed = opts.expected_bed ?? '';
    this.expected_build = opts.expected_build ?? '';
    this.expected_module = opts.expected_module ?? '';
    this.capability_bed = opts.capability_bed ?? '';
    this.capability_full_version = opts.capability_full_version ?? '';
    this.capability_version = opts.capability_version ?? '';
    this.capability_build = opts.capability_build ?? '';
    this.capability_generation_id = opts.capability_generation_id ?? '';
    this.capability_manifest_sha256 = opts.capability_manifest_sha256 ?? '';
    this.capability_projection_sha256 = opts.capability_projection_sha256 ?? '';
    this.authored_round = opts.authored_round ?? 1;
    this.source_manifest_ref = opts.source_manifest_ref ?? '';
    this.source_manifest_sha256 = opts.source_manifest_sha256 ?? '';
    this.source_case_slice_sha256 = opts.source_case_slice_sha256 ?? '';
    this.source_case_slice = opts.source_case_slice ?? {};
    this.max_rounds = opts.max_rounds ?? worker_device_max_rounds();
    this.max_infra_retries = opts.max_infra_retries ?? worker_device_infra_retries();
    this.max_probe_calls = opts.max_probe_calls ?? worker_probe_max_calls();
    this.attempts = opts.attempts ?? 0;
    this.probe_calls = opts.probe_calls ?? 0;
    this.probe_exhausted = opts.probe_exhausted ?? false;
    this.probe_evidence = opts.probe_evidence ?? [];
    this.command_heads_query_receipts = opts.command_heads_query_receipts ?? [];
    this.not_compilable_reports = opts.not_compilable_reports ?? [];
    this.worker_claims = opts.worker_claims ?? [];
    this.engine_gaps = opts.engine_gaps ?? [];
    this.authoring_accounts = opts.authoring_accounts ?? [];
    this.authoring_channel_rejection = opts.authoring_channel_rejection ?? {};
    this.admission_rejection = opts.admission_rejection ?? {};
    this.authoring_budget = opts.authoring_budget ?? {};
    this.account_supplement = opts.account_supplement ?? {};
    this.unsupported_feature_reports = opts.unsupported_feature_reports ?? [];
    this.probe_plan_keys = opts.probe_plan_keys ?? new Set();
    this.semantic_attempts = opts.semantic_attempts ?? 0;
    this.infrastructure_attempts = opts.infrastructure_attempts ?? 0;
    this.last_artifact_sha256 = opts.last_artifact_sha256 ?? '';
    this.current_artifact_sha256 = opts.current_artifact_sha256 ?? '';
    this.current_remote_artifact_sha256 = opts.current_remote_artifact_sha256 ?? '';
    this.lint_credential_id = opts.lint_credential_id ?? '';
    this.current_attempt_id = opts.current_attempt_id ?? '';
    this.current_prediction = opts.current_prediction ?? {};
    this.prediction_chain = opts.prediction_chain ?? [];
    this.last_verdict = opts.last_verdict ?? '';
    this.last_fail_signatures = opts.last_fail_signatures ?? new Set();
    this.seen_fail_signatures = opts.seen_fail_signatures ?? new Set();
    this.accumulated_fail_signatures = opts.accumulated_fail_signatures ?? new Set();
    this.device_no_progress_history = opts.device_no_progress_history ?? [];
    this.compile_no_progress_history = opts.compile_no_progress_history ?? [];
    this.compile_learning_history = opts.compile_learning_history ?? [];
    this.last_no_progress_decision = opts.last_no_progress_decision ?? {};
    this.no_progress_decisions = opts.no_progress_decisions ?? [];
    this.current_compile_revision = opts.current_compile_revision ?? '';
    this.current_compile_attempt_id = opts.current_compile_attempt_id ?? '';
    this.current_compile_recorded = opts.current_compile_recorded ?? false;
    this.compile_attempts = opts.compile_attempts ?? [];
    this.mechanical_case_submission_attempts = opts.mechanical_case_submission_attempts ?? 0;
    this.mechanical_case_rejections = opts.mechanical_case_rejections ?? [];
    this.mechanical_case_accepted = opts.mechanical_case_accepted ?? {};
    this.gate_advisories = opts.gate_advisories ?? [];
    this.mechanical_case_repair_disclosures = opts.mechanical_case_repair_disclosures ?? [];
    this.last_mechanical_case_submission_body = opts.last_mechanical_case_submission_body ?? {};
    this.compile_exhausted = opts.compile_exhausted ?? false;
    this.stop_reason = opts.stop_reason ?? '';
    this.in_flight = opts.in_flight ?? false;
    this.revoked = opts.revoked ?? false;
    this.closed = opts.closed ?? false;
    this._lease_cm = opts._lease_cm ?? null;
    this._environment_lease = opts._environment_lease ?? null;
    this._shared_binding = opts._shared_binding ?? null;
    this.env_id = opts.env_id ?? '';
    this.actual_bed = opts.actual_bed ?? '';
    this.lease_acquired_at = opts.lease_acquired_at ?? 0.0;
    this.lease_acquired_persisted = opts.lease_acquired_persisted ?? false;
    this.lease_released_persisted = opts.lease_released_persisted ?? false;
    this.shared_binding_persisted = opts.shared_binding_persisted ?? false;
    this.lease_error = opts.lease_error ?? '';
  }

  record_admission_rejection(error: any): Record<string, any> {
    const Q = require("./compile_engine/engine_quarantine");
    const { SessionAdmissionError, SESSION_ADMISSION_REJECTION_CODES } = Q;
    if (current_worker_device_session() !== this) {
      return {};
    }
    if (!(error instanceof SessionAdmissionError) || !SESSION_ADMISSION_REJECTION_CODES.has(error.code)) {
      throw new PyValueError('admission stop requires a registered typed rejection');
    }
    let record: Record<string, any>;
    {
      const identity: Record<string, string> = {};
      for (const key of SESSION_ADMISSION_IDENTITY_FIELDS) {
        identity[key] = String((this as any)[key] || '');
      }
      const previous = this.admission_rejection.record;
      if (valid_session_admission_rejection(previous, { require_identity: false }) && Object.entries(identity).every(([key, value]) => previous[key] === value)) {
        return deepcopy(this.admission_rejection);
      }
      const raw_detail = String(error instanceof Error ? error.message : error);
      record = scrub_value({
        ...identity,
        code: error.code,
        detail: raw_detail,
        message_sha256: sha256Hex(Buffer.from(raw_detail, 'utf8')),
        exception_type: 'SessionAdmissionError',
        source_manifest_ref: String(this.source_manifest_ref || ''),
        source_manifest_sha256: String(this.source_manifest_sha256 || ''),
        source_case_slice_sha256: String(this.source_case_slice_sha256 || ''),
      });
      record['record_id'] = persisted_surface_sha256(record);
      this.admission_rejection = { record, persisted: false };
    }
    let persisted: boolean;
    try {
      persisted = !!persist_worker_session_event(this, { ev: SESSION_ADMISSION_REJECTION_EVENT, rejection: record });
    } catch {
      persisted = false;
    }
    if ((this.admission_rejection.record || {}).record_id === record['record_id']) {
      this.admission_rejection.persisted = persisted;
    }
    return deepcopy(this.admission_rejection);
  }

  _persistent_admission_reason(): string {
    if (this.closed) {
      return 'worker_session_closed';
    }
    const Q = require("./compile_engine/engine_quarantine");
    try {
      Q.require_session_admission(this);
    } catch (exc: any) {
      if (exc instanceof Q.SessionAdmissionError) {
        this.lease_error = String(exc.message ?? exc);
        if (exc.code === 'dispatch_revoked') {
          this.revoked = true;
        }
        return exc.code;
      }
      if (exc instanceof PyValueError || exc instanceof Error) {
        this.lease_error = String(exc.message ?? exc);
        return 'dispatch_admission_unverified';
      }
      throw exc;
    }
    return '';
  }

  acquire_device_lease(opts: { timeout: number; poll_s?: number }): [any | null, string] {
    const poll_s = opts.poll_s ?? 0.25;
    if (this.device_access) {
      const reason = this._persistent_admission_reason();
      if (reason) {
        return [null, reason];
      }
    }
    {
      if (!this.device_access) {
        this.lease_error = 'pre_ask_static_phase';
        return [null, this.lease_error];
      }
      if (this.revoked || (this.dispatch_id && _REVOKED_DISPATCHES.has(this.dispatch_id))) {
        this.revoked = true;
        return [null, 'dispatch_revoked'];
      }
      const current = this._environment_lease;
      if (current !== null && current !== undefined && !current.released) {
        return [current, ''];
      }
      if (!this.expected_bed) {
        this.lease_error = 'execution_bed_missing';
        return [null, this.lease_error];
      }
    }
    const env_pool = require("../case_compiler/env_pool");
    const cm = env_pool.acquire_lease({ required_host: this.expected_bed, timeout: Math.max(0.0, Number(opts.timeout)), poll_s: Math.max(0.01, Number(poll_s)), strict_ready: true });
    let lease: any;
    try {
      lease = cm.__enter__();
    } catch (exc: any) {
      const reason = `lease_acquire_failed:${exc?.constructor?.name ?? 'Error'}`;
      this.lease_error = reason;
      return [null, reason];
    }
    const actual_bed = String(lease?.bed_host ?? '') || '';
    if (actual_bed !== this.expected_bed) {
      try {
        cm.__exit__(null, null, null);
      } catch {}
      const reason = 'lease_bed_identity_mismatch';
      this.lease_error = reason;
      this.actual_bed = actual_bed;
      return [null, reason];
    }
    const reason = this._persistent_admission_reason();
    if (reason) {
      try {
        cm.__exit__(null, null, null);
      } catch (exc: any) {
        this._lease_cm = cm;
        this._environment_lease = lease;
        this.lease_error = `${reason}; lease_release_failed:${exc?.constructor?.name ?? 'Error'}`;
        return [null, this.lease_error];
      }
      return [null, reason];
    }
    this._lease_cm = cm;
    this._environment_lease = lease;
    this.bed_lease_id = String(lease.lease_id || '');
    this.env_id = String(lease.env_id || '');
    this.actual_bed = actual_bed;
    this.lease_acquired_at = Number(lease.acquired_at || 0.0);
    this.lease_acquired_persisted = false;
    this.lease_released_persisted = false;
    const persisted = persist_worker_session_event(this, { ev: 'worker_device_lease_acquired', lease_acquired_at: this.lease_acquired_at, ts: this.lease_acquired_at });
    if (persisted) {
      this.lease_acquired_persisted = true;
      return [lease, ''];
    }
    try {
      cm.__exit__(null, null, null);
    } catch {}
    this._lease_cm = null;
    this._environment_lease = null;
    this.lease_error = 'lease_identity_unpersisted';
    this.stop_reason = 'lease_identity_unpersisted';
    return [null, 'lease_identity_unpersisted'];
  }

  acquire_shared_environment(): [any | null, string] {
    if (this.device_access) {
      const reason = this._persistent_admission_reason();
      if (reason) {
        return [null, reason];
      }
    }
    let bound: any;
    {
      if (!this.device_access) {
        this.lease_error = 'pre_ask_static_phase';
        return [null, this.lease_error];
      }
      if (this.revoked || (this.dispatch_id && _REVOKED_DISPATCHES.has(this.dispatch_id))) {
        this.revoked = true;
        return [null, 'dispatch_revoked'];
      }
      if (!this.expected_bed) {
        this.lease_error = 'execution_bed_missing';
        return [null, this.lease_error];
      }
      bound = this._shared_binding;
    }
    if (bound !== null && bound !== undefined) {
      return [bound, ''];
    }
    const env_pool = require("../case_compiler/env_pool");
    let binding: any;
    try {
      binding = env_pool.resolve_shared_environment({ required_host: this.expected_bed });
    } catch (exc: any) {
      const reason = `shared_bind_failed:${exc?.constructor?.name ?? 'Error'}`;
      this.lease_error = reason;
      return [null, reason];
    }
    const actual_bed = String(binding?.bed_host ?? '') || '';
    if (actual_bed !== this.expected_bed) {
      const reason = 'shared_bind_bed_identity_mismatch';
      this.lease_error = reason;
      this.actual_bed = actual_bed;
      return [null, reason];
    }
    const reason = this._persistent_admission_reason();
    if (reason) {
      return [null, reason];
    }
    this.env_id = String(binding.env_id || '');
    this.actual_bed = actual_bed;
    if (!persist_worker_session_event(this, { ev: 'worker_device_shared_bound', bound_at: Number(binding?.bound_at ?? 0.0) || 0.0, access: 'read_only' })) {
      this.lease_error = 'shared_bind_unpersisted';
      this.stop_reason = 'shared_bind_unpersisted';
      return [null, 'shared_bind_unpersisted'];
    }
    this._shared_binding = binding;
    this.shared_binding_persisted = true;
    return [binding, ''];
  }

  release_device_lease(): boolean {
    const cm = this._lease_cm;
    const lease = this._environment_lease;
    if (cm === null || cm === undefined || lease === null || lease === undefined) {
      return true;
    }
    this._lease_cm = null;
    this._environment_lease = null;
    let release_ok = true;
    try {
      cm.__exit__(null, null, null);
    } catch {
      release_ok = false;
    }
    const persisted = persist_worker_session_event(this, { ev: 'worker_device_lease_released', released: !!(lease?.released ?? false), release_ok });
    this.lease_released_persisted = !!(release_ok && (lease?.released ?? false) && persisted);
    if (!this.lease_released_persisted) {
      this.lease_error = 'lease_release_unpersisted';
    }
    return this.lease_released_persisted;
  }

  get leased_environment(): any | null {
    const lease = this._environment_lease;
    if (lease === null || lease === undefined || lease.released) {
      return null;
    }
    return lease.env;
  }

  control_snapshot(): Record<string, any> {
    const fields = ['attempts', 'semantic_attempts', 'infrastructure_attempts', 'last_artifact_sha256', 'current_artifact_sha256', 'current_remote_artifact_sha256', 'lint_credential_id', 'current_attempt_id', 'current_prediction', 'prediction_chain', 'last_verdict', 'last_fail_signatures', 'seen_fail_signatures', 'accumulated_fail_signatures', 'device_no_progress_history', 'compile_no_progress_history', 'compile_learning_history', 'last_no_progress_decision', 'no_progress_decisions', 'current_compile_revision', 'current_compile_attempt_id', 'current_compile_recorded', 'compile_attempts', 'compile_exhausted', 'stop_reason', 'in_flight'];
    const out: Record<string, any> = {};
    for (const name of fields) {
      out[name] = deepcopy((this as any)[name]);
    }
    return out;
  }

  restore_control_snapshot(snapshot: Record<string, any>): void {
    for (const [name, value] of Object.entries(snapshot)) {
      (this as any)[name] = deepcopy(value);
    }
  }

  reserve_probe(opts: { command?: string; hypothesis?: string; require_plan?: boolean } = {}): [boolean, number, string] {
    const command = opts.command ?? '';
    const hypothesis = opts.hypothesis ?? '';
    const require_plan = opts.require_plan ?? false;
    if (this.device_access) {
      const reason = this._persistent_admission_reason();
      if (reason) {
        return [false, this.probe_calls, reason];
      }
    }
    if (!this.device_access) {
      return [false, this.probe_calls, 'pre_ask_static_phase'];
    }
    if (this.revoked || (this.dispatch_id && _REVOKED_DISPATCHES.has(this.dispatch_id))) {
      this.revoked = true;
      return [false, this.probe_calls, 'dispatch_revoked'];
    }
    if (this.closed) {
      return [false, this.probe_calls, 'worker_session_closed'];
    }
    if (this.stop_reason) {
      return [false, this.probe_calls, this.stop_reason];
    }
    const plan = String(hypothesis || '').split(/\s+/).filter((s) => s).join(' ');
    if (require_plan && !plan) {
      return [false, this.probe_calls, 'probe_hypothesis_required'];
    }
    const plan_key = sha256Hex(Buffer.from((String(command || '').toLowerCase().split(/\s+/).filter((s) => s).join(' ') + '\n' + plan.toLowerCase()), 'utf8'));
    if (require_plan && this.probe_plan_keys.has(plan_key)) {
      return [false, this.probe_calls, 'probe_plan_repeated'];
    }
    if (this.probe_calls >= this.max_probe_calls) {
      this.probe_exhausted = true;
      return [false, this.probe_calls, 'worker_probe_budget_exhausted'];
    }
    this.probe_calls += 1;
    if (require_plan) {
      this.probe_plan_keys.add(plan_key);
    }
    return [true, this.probe_calls, ''];
  }

  _mutation_receipt_summary(): Record<string, any> {
    let receipt: any;
    let payload: Buffer;
    try {
      const sh = require("./compile_engine/_shared");
      payload = sh.outputs_root().joinpath(this.autoid, 'case.mutation.json').read_bytes();
      receipt = JSON.parse(payload.toString('utf8'));
    } catch {
      return {};
    }
    if (!_isDict(receipt)) {
      return {};
    }
    const rows = (receipt.requirements || []).filter((row: any) => _isDict(row));
    if (!rows.length) {
      return {};
    }
    return {
      assertion_count: rows.length,
      exempt_ordinals: rows.filter((row: any) => row.status === 'exempt').map((row: any) => Math.trunc(Number(row.assertion_ordinal) || 0)).sort((a: number, b: number) => a - b),
      control_flip_expected: rows.filter((row: any) => row.status === 'pending').length,
      mutation_receipt_sha256: sha256Hex(payload),
    };
  }

  record_probe_evidence(event: Record<string, any>): void {
    this.probe_evidence.push(deepcopy(event));
  }

  record_command_heads_query(query_result: Record<string, any>): [Record<string, any>, string] {
    if (!_isDict(query_result)) {
      return [{}, 'command heads query result must be an object'];
    }
    if (query_result.schema !== 'ist.command-heads-query' || query_result.status !== 'complete') {
      return [{}, 'command heads query result is not an accepted v1 result'];
    }
    const prefix = String(query_result.module_prefix || '').trim().toLowerCase();
    const device_build = String(query_result.device_build || '').trim();
    const projection_version = String(query_result.projection_version || '').trim();
    const heads = query_result.heads;
    if (!command_heads_prefix_shape_valid(prefix) || !Array.isArray(heads) || heads.some((head: any) => typeof head !== "string" || !head.trim())) {
      return [{}, 'command heads query result has an invalid module or heads list'];
    }
    const normalized_heads = heads.map((head: any) => String(head).trim());
    if (JSON.stringify(normalized_heads) !== JSON.stringify([...new Set(normalized_heads)].sort()) || query_result.count !== normalized_heads.length || normalized_heads.some((head: string) => !command_head_matches_prefix(head, prefix))) {
      return [{}, 'command heads query result is not a canonical module inventory'];
    }
    const identity_values = [this.dispatch_id, this.capability_build, this.capability_generation_id, this.capability_manifest_sha256];
    if (!identity_values.every((value) => String(value || '').trim())) {
      return [{}, 'command heads query requires complete sealed capability identity'];
    }
    if (!/^[0-9a-f]{64}$/.test(String(this.capability_manifest_sha256 || '').trim().toLowerCase())) {
      return [{}, 'command heads query capability manifest sha256 is invalid'];
    }
    if (device_build !== String(this.capability_build || '').trim()) {
      return [{}, 'command heads query device build does not match the worker session'];
    }
    const material = {
      schema: 'ist.command-heads-query',
      status: 'complete',
      module_prefix: prefix,
      device_build,
      capability_generation_id: this.capability_generation_id,
      capability_manifest_sha256: this.capability_manifest_sha256.toLowerCase(),
      projection_version,
      count: normalized_heads.length,
      heads: normalized_heads,
    };
    const result_sha256 = sha256Hex(Buffer.from(pyJsonDumps(material, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf8'));
    const sequence = this.command_heads_query_receipts.length + 1;
    const receipt = { ...material, receipt_id: `${this.dispatch_id}:heads:${sequence}:${result_sha256.slice(0, 16)}`, result_sha256 };
    const validation_error = validate_command_heads_query_receipt(receipt, { dispatch_id: this.dispatch_id, capability_build: this.capability_build, capability_generation_id: this.capability_generation_id, capability_manifest_sha256: this.capability_manifest_sha256 });
    if (validation_error) {
      return [{}, validation_error];
    }
    if (!persist_worker_session_event(this, { ev: 'command_heads_query_receipt', receipt })) {
      return [{}, 'command heads query receipt could not be persisted'];
    }
    this.command_heads_query_receipts.push(deepcopy(receipt));
    return [receipt, ''];
  }

  record_worker_claim(claim: Record<string, any>, opts: { reason_code: string; rejection_code: string }): Record<string, any> {
    if (!_isDict(claim)) {
      return {};
    }
    const reason_code = String(opts.reason_code || '').trim();
    const rejection_code = String(opts.rejection_code || '').trim();
    if (!NOT_COMPILABLE_REASON_CODES.has(reason_code) || !rejection_code) {
      return {};
    }
    const record: Record<string, any> = {
      schema: WORKER_CLAIM_SCHEMA,
      autoid: this.autoid,
      reason_code,
      rejection_code,
      test_point: String(claim.test_point || '').trim(),
      sources: (claim.sources || []).filter((source: any) => _isDict(source)).map((source: any) => ({ kind: String(source.kind || '').trim(), quote: String(source.quote || '').trim() })),
      obstacle: String(claim.obstacle || '').trim(),
      no_equivalent_reason: String(claim.no_equivalent_reason || '').trim(),
    };
    if (!persist_worker_session_event(this, { ev: 'worker_claim', claim: record })) {
      return {};
    }
    record['ordinal'] = this.worker_claims.length + 1;
    this.worker_claims.push(deepcopy(record));
    return record;
  }

  record_not_compilable(claim: Record<string, any>, command_heads_receipt_ids: string[], opts: { reason_code?: string } = {}): [Record<string, any>, string] {
    const reason_code = String(opts.reason_code ?? NOT_COMPILABLE_REASON_NO_CLI).trim();
    if (!_isDict(claim)) {
      return [{}, 'not-compilable claim must be an object'];
    }
    if (!NOT_COMPILABLE_REASON_CODES.has(reason_code)) {
      return [{}, 'not-compilable reason_code outside the closed set'];
    }
    let refs = command_heads_receipt_ids.map((value) => String(value || '').trim());
    refs = [...new Set(refs.filter((value) => value))];
    const session_receipts = deepcopy(this.command_heads_query_receipts);
    const expected_query_identity = { dispatch_id: this.dispatch_id, capability_build: this.capability_build, capability_generation_id: this.capability_generation_id, capability_manifest_sha256: this.capability_manifest_sha256 };
    const [by_id, receipt_error] = validate_command_heads_session_receipts(session_receipts, expected_query_identity);
    if (receipt_error) {
      return [{}, receipt_error];
    }
    if (!refs.length) {
      return [{}, NOT_COMPILABLE_HEADS_REFS_MISSING];
    }
    if (refs.some((receipt_id) => !(receipt_id in by_id))) {
      return [{}, NOT_COMPILABLE_HEADS_REF_UNKNOWN];
    }
    const sources = claim.sources;
    const source_error = validate_source_case_anchors(sources, this.source_case_slice, { autoid: this.autoid, source_case_slice_sha256: this.source_case_slice_sha256 });
    if (source_error) {
      return [{}, `not-compilable report requires source anchors bound to the sealed case slice (${source_error})`];
    }
    for (const field_name of ['test_point', 'obstacle', 'no_equivalent_reason']) {
      if (!String(claim[field_name] || '').trim()) {
        return [{}, `not-compilable report requires ${field_name}`];
      }
    }
    const identity_values = [this.autoid, this.dispatch_id, this.capability_build, this.capability_generation_id, this.capability_manifest_sha256, this.source_manifest_ref, this.source_manifest_sha256, this.source_case_slice_sha256];
    if (!identity_values.every((value) => String(value || '').trim())) {
      return [{}, 'not-compilable report requires complete sealed capability identity'];
    }
    const query_receipts = refs.map((receipt_id) => ({
      receipt_id,
      module_prefix: String(by_id[receipt_id]['module_prefix']),
      result_sha256: String(by_id[receipt_id]['result_sha256']),
      head_count: Math.trunc(Number(by_id[receipt_id]['count'])),
    }));
    const summary_error = validate_not_compilable_heads_summary(query_receipts, by_id);
    if (summary_error) {
      return [{}, summary_error];
    }
    const material = canonical_persisted_value({
      schema: 'ist.not-compilable',
      autoid: this.autoid,
      reason_code,
      test_point: String(claim['test_point']).trim(),
      sources: sources.map((source: any) => ({ kind: String(source['kind']).trim(), quote: String(source['quote']).trim() })),
      obstacle: String(claim['obstacle']).trim(),
      no_equivalent_reason: String(claim['no_equivalent_reason']).trim(),
      command_heads_receipts: query_receipts,
      capability_build: this.capability_build,
      capability_generation_id: this.capability_generation_id,
      capability_manifest_sha256: this.capability_manifest_sha256.toLowerCase(),
      source_manifest_ref: this.source_manifest_ref,
      source_manifest_sha256: this.source_manifest_sha256,
      source_case_slice_sha256: this.source_case_slice_sha256,
    });
    const report = { ...material, report_hash: persisted_surface_sha256(material) };
    if (!persist_worker_session_event(this, { ev: 'not_compilable', report })) {
      return [{}, 'not-compilable report could not be persisted'];
    }
    this.not_compilable_reports.push(deepcopy(report));
    return [report, ''];
  }

  record_unsupported_feature(probe_evidence_refs: string[], opts: { claim?: Record<string, any> | null } = {}): [Record<string, any>, string] {
    const claim = opts.claim ?? null;
    let refs = probe_evidence_refs.map((value) => String(value || '').trim());
    refs = refs.filter((value) => value);
    const selected = deepcopy(this.probe_evidence.filter((event) => refs.includes(String(event.probe_id || ''))));
    if (new Set(refs).size < 2 || selected.length !== new Set(refs).size) {
      return [{}, 'unsupported_feature requires two existing probe evidence refs'];
    }
    if (new Set(selected.map((item: any) => String(item.command || '').trim())).size < 2) {
      return [{}, 'unsupported_feature co-probes must use two distinct commands'];
    }
    if (new Set(selected.map((item: any) => String(item.hypothesis || '').trim())).size < 2) {
      return [{}, 'unsupported_feature co-probes must test two distinct hypotheses'];
    }
    if (selected.some((item: any) => !['observed', 'cli_rejected'].includes(item.outcome) || item.expectation_authority !== false)) {
      return [{}, 'unsupported_feature co-probes contain unusable evidence'];
    }
    const material = canonical_persisted_value({
      schema: 'ist.compile.unsupported-feature',
      autoid: this.autoid,
      probe_evidence_refs: [...new Set(refs)].sort(),
      claim: _isDict(claim) ? deepcopy(claim) : {},
      co_probes: selected.map((item: any) => ({
        probe_id: String(item.probe_id || ''),
        command_sha256: sha256Hex(Buffer.from(String(item.command || ''), 'utf8')),
        hypothesis_sha256: sha256Hex(Buffer.from(String(item.hypothesis || ''), 'utf8')),
        outcome: String(item.outcome || ''),
      })),
    });
    const report = { ...material, report_hash: persisted_surface_sha256(material) };
    if (!persist_worker_session_event(this, { ev: 'unsupported_feature', ...report })) {
      return [{}, 'unsupported_feature evidence could not be persisted'];
    }
    this.unsupported_feature_reports.push(deepcopy(report));
    return [report, ''];
  }

  fail_probe_persistence(): void {
    this.stop_reason = 'probe_evidence_unpersisted';
  }

  reserve_run(artifact_sha256: string): [boolean, number, string] {
    if (this.device_access) {
      const reason = this._persistent_admission_reason();
      if (reason) {
        return [false, this.attempts, reason];
      }
    }
    if (!this.device_access) {
      return [false, this.attempts, 'pre_ask_static_phase'];
    }
    if (this.revoked || (this.dispatch_id && _REVOKED_DISPATCHES.has(this.dispatch_id))) {
      this.revoked = true;
      return [false, this.attempts, 'dispatch_revoked'];
    }
    if (this.in_flight) {
      return [false, this.attempts, 'run_already_in_flight'];
    }
    if (this.stop_reason) {
      return [false, this.attempts, this.stop_reason];
    }
    if (this.semantic_attempts >= this.max_rounds) {
      this.stop_reason = 'max_semantic_rounds_reached';
      return [false, this.attempts, this.stop_reason];
    }
    if (this.infrastructure_attempts > this.max_infra_retries) {
      this.stop_reason = 'infrastructure_retry_limit';
      return [false, this.attempts, this.stop_reason];
    }
    if (this.last_verdict === 'fail' && this.last_artifact_sha256 && artifact_sha256 === this.last_artifact_sha256) {
      return [false, this.attempts, 'artifact_revision_required_after_fail'];
    }
    this.attempts += 1;
    this.current_artifact_sha256 = artifact_sha256;
    this.current_remote_artifact_sha256 = '';
    this.current_attempt_id = `${this.dispatch_id || this.fork_id}:${this.attempts}:${artifact_sha256.slice(0, 16)}`;
    const parent_hash = this.prediction_chain.length ? String(this.prediction_chain[this.prediction_chain.length - 1].prediction_hash || '') : '';
    const seen_probe_ids = new Set(this.prediction_chain.flatMap((entry: any) => (entry.hypothesis_refs || []).map((ref: any) => String(ref.probe_id || ''))));
    const hypothesis_refs = this.probe_evidence
      .filter((p: any) => String(p.probe_id || '') && !seen_probe_ids.has(String(p.probe_id || '')))
      .map((p: any) => ({ probe_id: String(p.probe_id || ''), hypothesis_sha256: sha256Hex(Buffer.from(String(p.hypothesis || ''), 'utf8')) }));
    const material: Record<string, any> = {
      schema: 'ist.compile.prediction',
      prediction_before_run: { claim: 'all_product_assertions_pass', ...this._mutation_receipt_summary() },
      artifact_sha256,
      attempt_id: this.current_attempt_id,
      revision: this.prediction_chain.length + 1,
      parent_prediction_hash: parent_hash,
      hypothesis_refs,
    };
    this.current_prediction = { ...material, prediction_hash: sha256Hex(Buffer.from(pyJsonDumps(material, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf8')) };
    this.in_flight = true;
    return [true, this.attempts, ''];
  }

  commit_prediction(): Record<string, any> {
    const prediction = deepcopy(this.current_prediction);
    if (!Object.keys(prediction).length) {
      return {};
    }
    if (!this.prediction_chain.length || this.prediction_chain[this.prediction_chain.length - 1].prediction_hash !== prediction.prediction_hash) {
      this.prediction_chain.push(prediction);
    }
    return prediction;
  }

  complete_run(verdict: string, fail_signatures: any = []): string {
    const normalized = new Set(fail_signatures || []);
    this.in_flight = false;
    const revision = this.current_artifact_sha256;
    this.current_artifact_sha256 = '';
    this.current_remote_artifact_sha256 = '';
    if (!['pass', 'fail'].includes(verdict)) {
      this.infrastructure_attempts += 1;
      if (this.infrastructure_attempts > this.max_infra_retries) {
        this.stop_reason = 'infrastructure_retry_limit';
      }
      return this.stop_reason;
    }
    this.semantic_attempts += 1;
    this.last_artifact_sha256 = revision;
    if (verdict === 'fail') {
      const { no_progress_step } = require("./compile_engine/facts");
      const decision = no_progress_step(this.device_no_progress_history, { domain: 'device', value: normalized, revision_sha256: revision });
      this.device_no_progress_history = decision.history;
      delete decision.history;
      this.last_no_progress_decision = { ...decision };
      this.no_progress_decisions.push({ ...decision });
      if (decision.stop) {
        this.stop_reason = 'device_exhausted';
      }
      this.seen_fail_signatures = normalized;
    } else if (verdict === 'pass') {
      this.seen_fail_signatures = new Set();
      this.accumulated_fail_signatures = new Set();
      this.device_no_progress_history = [];
      this.last_no_progress_decision = {};
    }
    this.last_verdict = verdict;
    this.last_fail_signatures = normalized;
    if (verdict === 'fail' && this.semantic_attempts >= this.max_rounds && !this.stop_reason) {
      this.stop_reason = 'max_semantic_rounds_reached';
    }
    return this.stop_reason;
  }

  begin_compile_attempt(revision_sha256: string): string {
    this.current_compile_revision = String(revision_sha256 || '');
    this.current_compile_attempt_id = `${this.dispatch_id || this.fork_id}:compile:${this.compile_attempts.length + 1}:${this.current_compile_revision.slice(0, 16)}`;
    this.current_compile_recorded = false;
    return this.current_compile_attempt_id;
  }

  begin_mechanical_case_submission(): number {
    this.mechanical_case_submission_attempts += 1;
    return this.mechanical_case_submission_attempts;
  }

  remember_mechanical_case_submission_body(body: Record<string, any>): boolean {
    let snapshot: any;
    try {
      snapshot = deepcopy(body);
    } catch {
      return false;
    }
    this.last_mechanical_case_submission_body = snapshot;
    return true;
  }

  prepare_mechanical_case_envelope_sections(body: Record<string, any>, opts: { block_edit_authorization_codes?: Set<string> } = {}): [Record<string, any> | null, string, Record<string, any> | null] {
    const block_edit_authorization_codes = opts.block_edit_authorization_codes ?? new Set<string>();
    const missing_expectation = body.expectation_binding === null || body.expectation_binding === undefined;
    const missing_escape = body.escape_hatches === null || body.escape_hatches === undefined;
    if (!missing_expectation && !missing_escape) {
      return [body, '', null];
    }
    let current: Record<string, any>;
    try {
      current = deepcopy(body);
    } catch {
      return [null, 'submission_body_not_copyable', null];
    }
    let previous: Record<string, any>;
    let latest_codes: Set<string>;
    {
      try {
        previous = deepcopy(this.last_mechanical_case_submission_body);
      } catch {
        return [null, 'prior_submission_not_copyable', null];
      }
      const latest = this.mechanical_case_rejections.length ? this.mechanical_case_rejections[this.mechanical_case_rejections.length - 1] : {};
      latest_codes = new Set((latest.violations || []).filter((item: any) => _isDict(item) && String(item.code || '')).map((item: any) => String(item.code || '')));
    }
    if (!previous || !Object.keys(previous).length) {
      if (missing_expectation) {
        return [null, 'no_prior_complete_submission', null];
      }
      current['escape_hatches'] = [];
      return [current, '', null];
    }
    if (String(previous.schema || '') !== String(current.schema || '') || String(previous.autoid || '') !== String(current.autoid || '')) {
      return [null, 'submission_identity_changed', null];
    }
    let previous_blocks: string;
    let current_blocks: string;
    try {
      previous_blocks = pyJsonDumps(previous.blocks, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] });
      current_blocks = pyJsonDumps(current.blocks, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] });
    } catch {
      return [null, 'blocks_not_canonical_json', null];
    }
    const blocks_changed = previous_blocks !== current_blocks;
    const authorized_codes = [...latest_codes].filter((c) => block_edit_authorization_codes.has(c)).sort();
    if (blocks_changed && !authorized_codes.length) {
      return [null, 'blocks_change_not_authorized', null];
    }
    let disclosure: Record<string, any> | null = null;
    if (blocks_changed) {
      disclosure = { code: 'submission_repair_blocks_changed_for_cited_violation', authorized_by: authorized_codes, restored_sections: [] };
    }
    const current_block_rows = current.blocks;
    const previous_block_rows = previous.blocks;
    if (!Array.isArray(current_block_rows) || !Array.isArray(previous_block_rows)) {
      return [null, 'blocks_not_arrays', null];
    }
    const _binding_still_resolves = (entries: any): boolean => {
      if (!Array.isArray(entries) || !entries.length) {
        return false;
      }
      for (const entry of entries) {
        if (!_isDict(entry)) {
          return false;
        }
        const block_index = entry.block_index;
        if (typeof block_index !== "number" || typeof block_index === "boolean" || !(block_index >= 0 && block_index < current_block_rows.length) || !_isDict(current_block_rows[block_index])) {
          return false;
        }
        let carried = current_block_rows[block_index];
        const assert_index = entry.assert_index;
        if (assert_index !== null && assert_index !== undefined) {
          const assertions = carried.asserts;
          if (typeof assert_index !== "number" || typeof assert_index === "boolean" || !Array.isArray(assertions) || !(assert_index >= 0 && assert_index < assertions.length) || !_isDict(assertions[assert_index])) {
            return false;
          }
          carried = assertions[assert_index];
        }
        if (String(carried.expectation_id || '') !== String(entry.expectation_id || '') || String(carried.semantic_key || '') !== String(entry.semantic_key || '')) {
          return false;
        }
      }
      return true;
    };
    if (missing_expectation) {
      const previous_binding = previous.expectation_binding;
      if (!_binding_still_resolves(previous_binding)) {
        return [null, 'changed_blocks_require_expectation_binding', disclosure];
      }
      current['expectation_binding'] = deepcopy(previous_binding);
      if (disclosure !== null) {
        (disclosure['restored_sections'] as string[]).push('expectation_binding');
      }
    }
    if (missing_escape) {
      const previous_escape = previous.escape_hatches;
      if (!Array.isArray(previous_escape)) {
        return [null, 'prior_escape_hatches_unavailable', disclosure];
      }
      if (blocks_changed) {
        const step_indices = new Set(current_block_rows.map((block: any, index: number) => [_isDict(block) && String(block.kind || '').trim().toUpperCase() === 'STEP', index] as const).filter(([ok]) => ok).map(([, index]) => index));
        const escaped_indices = new Set(previous_escape.filter((entry: any) => _isDict(entry)).map((entry: any) => entry.block_index));
        if (!(step_indices.size === escaped_indices.size && [...step_indices].every((i) => escaped_indices.has(i)))) {
          return [null, 'changed_blocks_require_escape_hatches', disclosure];
        }
        for (const block_index of step_indices) {
          if ((block_index as number) >= previous_block_rows.length || JSON.stringify(current_block_rows[block_index as number]) !== JSON.stringify(previous_block_rows[block_index as number])) {
            return [null, 'changed_blocks_require_escape_hatches', disclosure];
          }
        }
      }
      current['escape_hatches'] = deepcopy(previous_escape);
      if (disclosure !== null) {
        (disclosure['restored_sections'] as string[]).push('escape_hatches');
      }
    }
    return [current, '', disclosure];
  }

  restore_mechanical_case_envelope_sections(body: Record<string, any>): [Record<string, any> | null, string] {
    let [restored, error] = this.prepare_mechanical_case_envelope_sections(body);
    if (error === 'blocks_change_not_authorized') {
      error = 'blocks_changed';
    }
    return [restored, error];
  }

  record_mechanical_case_acceptance(attempt: number, mechanical_case: Record<string, any>, opts: { input_sha256?: string } = {}): void {
    const input_sha256 = opts.input_sha256 ?? '';
    this.mechanical_case_accepted = { attempt: Math.trunc(Number(attempt)), input_sha256: String(input_sha256 || ''), input: _isDict(mechanical_case) ? deepcopy(mechanical_case) : {} };
  }

  record_mechanical_case_rejection(attempt: number, violations: Record<string, any>[], opts: { input_sha256?: string; rule_identity?: string; mechanical_case?: Record<string, any> | null } = {}): void {
    const input_sha256 = opts.input_sha256 ?? '';
    const rule_identity = opts.rule_identity ?? '';
    const mechanical_case = opts.mechanical_case ?? null;
    const normalized: Record<string, any>[] = [];
    for (const item of violations) {
      if (!_isDict(item)) {
        continue;
      }
      const finding: Record<string, any> = {};
      for (const key of ['gate', 'code', 'locus', 'detail', 'legal_form']) {
        finding[key] = String(item[key] || '');
      }
      const expectation_ids = item.expectation_ids;
      if (Array.isArray(expectation_ids)) {
        const bound = [...new Set(expectation_ids.map((value: any) => String(value).trim()).filter((v: string) => v))].sort();
        if (bound.length) {
          finding['expectation_ids'] = bound;
        }
      }
      normalized.push(finding);
    }
    this.mechanical_case_rejections.push({
      attempt: Math.trunc(Number(attempt)),
      violations: normalized,
      ...(input_sha256 ? { input_sha256: String(input_sha256) } : {}),
      ...(rule_identity ? { rule_identity: String(rule_identity) } : {}),
      ...(_isDict(mechanical_case) && input_sha256 ? { input: deepcopy(mechanical_case) } : {}),
    });
  }

  record_gate_advisory(advisory: Record<string, any>): void {
    this.gate_advisories.push({ ...advisory });
  }

  _reject_authoring_statement(code: string): [Record<string, any>, string] {
    const { statement_rejection_stops_dispatch } = require("./tools/device/authoring_account_tools");
    if (statement_rejection_stops_dispatch(code)) {
      this.authoring_channel_rejection = { code, fork_id: this.fork_id, autoid: this.autoid, dispatch_id: this.dispatch_id, batch_run_id: this.batch_run_id };
    }
    return [{}, code];
  }

  _record_authoring_statement(kind: string, payload: Record<string, any>): [Record<string, any>, string] {
    const tools = require("./tools/device/authoring_account_tools");
    const { AuthoringAccountSubmission, EngineGapSubmission } = tools;
    let ValidationError: any;
    try {
      ValidationError = require("pydantic").ValidationError;
    } catch {
      ValidationError = null;
    }
    if (!['engine_gap', 'authoring_account'].includes(kind)) {
      return [{}, 'authoring_statement_invalid'];
    }
    try {
      const schema = kind === 'engine_gap' ? EngineGapSubmission : AuthoringAccountSubmission;
      payload = schema.model_validate(payload).model_dump({ mode: 'python' });
    } catch (exc: any) {
      if (ValidationError !== null && exc instanceof ValidationError) {
        return [{}, 'authoring_statement_invalid'];
      }
      if (exc instanceof Error) {
        return [{}, 'authoring_statement_invalid'];
      }
      throw exc;
    }
    {
      const { current_supplement_grant } = require("./skills/authoring_account_supplement");
      const grant = current_supplement_grant();
      const supplementary = !!(grant !== null && grant !== undefined && Object.keys(this.account_supplement).length && grant['diagnostic_dispatch_id'] === this.dispatch_id && grant['batch_run_id'] === this.batch_run_id && grant['autoid'] === this.autoid);
      if ((!supplementary && (this.skill !== 'compile-worker' || !['compile-worker', 'compile-worker-flash'].includes(this.agent))) || !/^[0-9]{18}$/.test(String(this.autoid || '')) || !this.fork_id || !_DISPATCH_ID_RE.test(String(this.dispatch_id || '')) || !_DISPATCH_ID_RE.test(String(this.batch_run_id || ''))) {
        return this._reject_authoring_statement('no_engine_dispatch');
      }
      if (Object.keys(this.account_supplement).length && (!supplementary || kind !== 'authoring_account')) {
        return this._reject_authoring_statement('no_engine_dispatch');
      }
      if (this.closed) {
        return this._reject_authoring_statement('authoring_session_closed');
      }
      if (this.revoked || _REVOKED_DISPATCHES.has(this.dispatch_id)) {
        return this._reject_authoring_statement('authoring_dispatch_revoked');
      }
      let verification: Record<string, any> = { status: 'model_account', scope: 'model_statement_only' };
      if (kind === 'engine_gap') {
        const checks: any[] = [];
        for (const reference of (payload as any)['rejection_refs']) {
          const matches: any[] = [];
          for (const attempt of this.mechanical_case_rejections) {
            if (reference['submission_attempt'] !== null && reference['submission_attempt'] !== undefined && reference['submission_attempt'] !== attempt.attempt) {
              continue;
            }
            for (const violation of attempt.violations || []) {
              if (['gate', 'code', 'locus'].every((key) => reference[key] === violation[key])) {
                matches.push({
                  attempt: attempt['attempt'],
                  violation: deepcopy(violation),
                  violation_sha256: persisted_surface_sha256(scrub_value(violation)),
                  input_sha256: String(attempt.input_sha256 || ''),
                  rule_identity: String(attempt.rule_identity || ''),
                  identity_status: ['input_sha256', 'rule_identity'].every((key) => /^[0-9a-f]{64}$/.test(String(attempt[key] || ''))) ? 'complete' : 'incomplete',
                });
              }
            }
          }
          checks.push({ reference: deepcopy(reference), matches });
        }
        verification = {
          status: checks.length && checks.every((row) => row.matches.length && row.matches.every((match: any) => match.identity_status === 'complete')) ? 'claim_reference_confirmed' : 'unverified',
          scope: 'rejection_occurrence_only',
          references: checks,
        };
      }
      if (supplementary) {
        verification = { status: 'model_account', scope: 'supplementary_visible_records_only' };
      }
      const body = scrub_value({
        schema: kind === 'engine_gap' ? engine_schema_id('engine_gap') : engine_schema_id('authoring_account'),
        autoid: this.autoid,
        fork_id: this.fork_id,
        dispatch_id: this.dispatch_id,
        batch_run_id: this.batch_run_id,
        authored_round: this.authored_round,
        payload: deepcopy(payload),
        verification,
      });
      const identifier = persisted_surface_sha256(body);
      const records = kind === 'engine_gap' ? this.engine_gaps : this.authoring_accounts;
      for (const prev of records) {
        if (prev['record_id'] === identifier) {
          return [deepcopy(prev), ''];
        }
      }
      if (supplementary && records.length) {
        return this._reject_authoring_statement('authoring_session_closed');
      }
      const record = { ...body, record_id: identifier, ordinal: records.length + 1 };
      const event = kind === 'engine_gap' ? 'engine_gap_submitted' : 'authoring_account_submitted';
      if (!persist_worker_session_event(this, { ev: event, record })) {
        return [{}, 'authoring_journal_unavailable'];
      }
      if (this.revoked || _REVOKED_DISPATCHES.has(this.dispatch_id)) {
        return this._reject_authoring_statement('authoring_dispatch_revoked');
      }
      records.push(deepcopy(record));
      return [deepcopy(record), ''];
    }
  }

  record_engine_gap(payload: Record<string, any>): [Record<string, any>, string] {
    return this._record_authoring_statement('engine_gap', payload);
  }

  record_authoring_account(payload: Record<string, any>): [Record<string, any>, string] {
    return this._record_authoring_statement('authoring_account', payload);
  }

  observe_authoring_budget(opts: { total_limit: number; domain_limit: number; schema_names: string[]; calls: string[] | null }): Record<string, any> {
    const { total_limit, domain_limit, schema_names, calls } = opts;
    const { AuthoringAccountBudgetError, ACCOUNT_TOOL } = require("./middleware/authoring_account_reserve");
    const policy = { total_limit, domain_limit, schema_names };
    const previous = this.authoring_budget;
    if (Object.keys(previous).length && Object.entries(policy).some(([key, value]) => previous[key] !== value)) {
      throw new AuthoringAccountBudgetError('authoring budget policy changed within a dispatch');
    }
    if (previous.closed || previous.unavailable) {
      throw new AuthoringAccountBudgetError('authoring budget journal is closed or unavailable');
    }
    if (Object.keys(previous).length && calls === null) {
      return deepcopy(previous);
    }
    const record: Record<string, any> = {
      schema: engine_schema_id('authoring_tool_budget'),
      ...policy,
      sequence: (previous.sequence ?? 0) + 1,
      used_tool_calls: (previous.used_tool_calls ?? 0) + (calls || []).length,
      used_domain_calls: (previous.used_domain_calls ?? 0) + (calls || []).filter((name) => ![...schema_names, ACCOUNT_TOOL].includes(name)).length,
      response_calls: calls,
      closed: false,
    };
    record['remaining_tool_calls'] = Math.max(0, total_limit - (record['used_tool_calls'] as number));
    if (!persist_worker_session_event(this, { ev: 'authoring_budget_observed', budget: record })) {
      this.authoring_budget = { ...record, unavailable: true };
      throw new AuthoringAccountBudgetError('authoring budget observation was not durably persisted');
    }
    this.authoring_budget = record;
    return deepcopy(record);
  }

  close_authoring_budget(): void {
    if (!Object.keys(this.authoring_budget).length || this.authoring_budget.unavailable) {
      return;
    }
    const record = { ...this.authoring_budget, closed: true };
    if (persist_worker_session_event(this, { ev: 'authoring_budget_closed', budget: record })) {
      this.authoring_budget = record;
    } else {
      this.authoring_budget = { ...record, closed: false, unavailable: true };
    }
  }

  structural_rejection_streak(): Record<string, any> {
    const records = [...this.mechanical_case_rejections];
    const { repeated_rejection } = require("./compile_engine/rejection_history");
    return repeated_rejection(records, { group_fields: ['attempt'] });
  }

  record_mechanical_case_repair_disclosure(attempt: number, disclosure: Record<string, any>): void {
    const authorized_by = [...new Set((disclosure.authorized_by || []).map((value: any) => String(value).trim()).filter((v: string) => v))].sort();
    const restored_sections = [...new Set((disclosure.restored_sections || []).map((value: any) => String(value).trim()).filter((v: string) => v))].sort();
    this.mechanical_case_repair_disclosures.push({ attempt: Math.trunc(Number(attempt)), code: String(disclosure.code || ''), authorized_by, restored_sections });
  }

  consistency_conflict_terminal_allowed(autoid: string): boolean {
    if (String(autoid || '') !== this.autoid) {
      return false;
    }
    return this.mechanical_case_rejections.some((record) => _isDict(record) && (record.violations || []).some((item: any) => _isDict(item) && String(item.code || '') === 'case_abandoned_by_consistency'));
  }

  record_compile_rejection(gate_codes: any): Record<string, any> {
    const { no_progress_step } = require("./compile_engine/facts");
    const violations: Record<string, any>[] = [];
    for (const value of gate_codes || []) {
      let code: string;
      let detail: string;
      let step: any;
      if (_isDict(value)) {
        code = String(value.code || value.gate || '').trim();
        detail = String(value.detail || '').trim();
        step = value.step_index !== undefined ? value.step_index : (value.step !== undefined ? value.step : -1);
      } else {
        code = String(value || '').trim();
        detail = '';
        step = -1;
      }
      if (code) {
        violations.push({ code, detail, step_index: typeof step === "number" && !Number.isNaN(step) ? step : -1 });
      }
    }
    const codes = [...new Set(violations.map((item) => item['code']))].sort();
    const learning = !!codes.length && codes.every((code) => _COMPILE_LEARNING_GATES.has(code));
    let decision: Record<string, any>;
    if (learning) {
      const signature = sha256Hex(Buffer.from(pyJsonDumps(violations, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf8'));
      if (!this.compile_learning_history.some((item: any) => item.revision_sha256 === this.current_compile_revision)) {
        this.compile_learning_history.push({ revision_sha256: this.current_compile_revision, violation_signature: signature, gate_codes: codes });
      }
      let threshold: number;
      try {
        threshold = parseInt(String(process.env['IST_COMPILE_LEARNING_MAX'] ?? '12'), 10);
        if (Number.isNaN(threshold)) throw new PyValueError();
      } catch {
        threshold = 12;
      }
      threshold = Math.max(4, Math.min(threshold, 30));
      const streak = this.compile_learning_history.length;
      decision = {
        domain: 'compile',
        gate_class: 'contract_learning',
        failure_key: `compile_learning:"${signature}"`,
        streak,
        threshold,
        revision_refs: this.compile_learning_history.map((item: any) => String(item.revision_sha256 || '')),
        stop_keys: streak >= threshold ? [`compile_learning:"${signature}"`] : [],
        stop: streak >= threshold,
      };
      decision['decision_id'] = sha256Hex(Buffer.from(pyJsonDumps(decision, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf8')).slice(0, 24);
    } else {
      decision = no_progress_step(this.compile_no_progress_history, { domain: 'compile', value: codes, revision_sha256: this.current_compile_revision });
      this.compile_no_progress_history = decision.history;
      delete decision.history;
      decision['gate_class'] = 'no_progress';
    }
    this.last_no_progress_decision = { ...decision };
    this.no_progress_decisions.push({ ...decision });
    this.compile_attempts.push({
      compile_attempt_id: this.current_compile_attempt_id,
      revision_sha256: this.current_compile_revision,
      result: 'rejected',
      gate_codes: codes,
      violations,
      no_progress_decision: { ...decision },
    });
    this.current_compile_recorded = true;
    if (decision.stop) {
      this.compile_exhausted = true;
      const unresolved = (decision.stop_keys || []).some((key: any) => String(key || '') === 'compile:"provenance_source_unresolved"');
      this.stop_reason = unresolved ? 'missing_authority_exhausted' : learning ? 'compile_contract_learning_exhausted' : 'compile_exhausted';
    }
    return { ...decision };
  }

  cancel_compile_attempt(): void {
    this.current_compile_revision = '';
    this.current_compile_attempt_id = '';
    this.current_compile_recorded = false;
  }

  finish_compile_attempt(opts: { success: boolean }): Record<string, any> {
    const { success } = opts;
    let record: Record<string, any>;
    if (!this.current_compile_recorded) {
      record = { compile_attempt_id: this.current_compile_attempt_id, revision_sha256: this.current_compile_revision, result: success ? 'pass' : 'error', gate_codes: [] };
      this.compile_attempts.push(record);
    } else {
      record = { ...this.compile_attempts[this.compile_attempts.length - 1] };
    }
    if (success) {
      this.compile_no_progress_history = [];
      this.compile_learning_history = [];
      this.compile_exhausted = false;
      if (['compile_exhausted', 'compile_contract_learning_exhausted'].includes(this.stop_reason)) {
        this.stop_reason = '';
      }
    }
    this.current_compile_revision = '';
    this.current_compile_attempt_id = '';
    this.current_compile_recorded = false;
    return { ...record };
  }

  cancel_reservation(): void {
    if (this.in_flight && this.attempts > 0) {
      this.attempts -= 1;
    }
    this.in_flight = false;
    this.current_artifact_sha256 = '';
    this.current_remote_artifact_sha256 = '';
    this.current_attempt_id = '';
    this.current_prediction = {};
  }
}

export function worker_device_scope<T>(opts: {
  skill: string;
  agent: string;
  autoid: string;
  fork_id: string;
  device_access?: boolean;
  dispatch_id?: string;
  batch_run_id?: string;
  expected_bed?: string;
  expected_build?: string;
  expected_module?: string;
  capability_bed?: string;
  capability_full_version?: string;
  capability_version?: string;
  capability_build?: string;
  capability_generation_id?: string;
  capability_manifest_sha256?: string;
  capability_projection_sha256?: string;
  authored_round?: number;
  source_manifest_ref?: string;
  source_manifest_sha256?: string;
  source_case_slice_sha256?: string;
  source_case_slice?: Record<string, any> | null;
}, fn: (session: WorkerDeviceSession | null) => T): T {
  const {
    skill, agent, autoid, fork_id,
    device_access = true, dispatch_id = '', batch_run_id = '',
    expected_bed = '', expected_build = '', expected_module = '',
    capability_bed = '', capability_full_version = '', capability_version = '', capability_build = '',
    capability_generation_id = '', capability_manifest_sha256 = '', capability_projection_sha256 = '',
    authored_round = 1, source_manifest_ref = '', source_manifest_sha256 = '', source_case_slice_sha256 = '',
    source_case_slice = null,
  } = opts;
  let session: WorkerDeviceSession | null = null;
  const { current_supplement_grant } = require("./skills/authoring_account_supplement");
  const supplement_grant = current_supplement_grant();
  const supplementary = !!(skill === 'authoring-account-supplement' && supplement_grant !== null && supplement_grant !== undefined && supplement_grant['diagnostic_dispatch_id'] === dispatch_id && supplement_grant['batch_run_id'] === batch_run_id && supplement_grant['autoid'] === autoid);
  if ((skill === 'compile-worker' || supplementary) && fork_id) {
    const [bound_source_ref, bound_source_manifest_sha256, bound_source_slice_sha256, bound_source_slice] = _validated_source_binding({
      autoid,
      source_manifest_ref,
      source_manifest_sha256,
      source_case_slice_sha256_value: source_case_slice_sha256,
      source_case_slice: source_case_slice || {},
    });
    session = new WorkerDeviceSession({
      skill, agent, autoid, fork_id,
      device_access: device_access === true && !supplementary,
      dispatch_id, batch_run_id, bed_lease_id: '',
      expected_bed, expected_build, expected_module,
      capability_bed, capability_full_version, capability_version, capability_build,
      capability_generation_id, capability_manifest_sha256, capability_projection_sha256,
      authored_round: Math.max(1, Math.trunc(Number(authored_round) || 1)),
      source_manifest_ref: bound_source_ref,
      source_manifest_sha256: bound_source_manifest_sha256,
      source_case_slice_sha256: bound_source_slice_sha256,
      source_case_slice: bound_source_slice,
      account_supplement: supplementary ? deepcopy(supplement_grant) : {},
    });
    if (dispatch_id) {
      session.revoked = _REVOKED_DISPATCHES.has(dispatch_id);
    }
    _SESSIONS.set(fork_id, session);
  }
  const prev_scope = _SCOPE;
  const prev_fork = _FORK_SCOPE;
  _SCOPE = session;
  _FORK_SCOPE = fork_id ? { skill: String(skill || ''), agent: String(agent || ''), fork_id: String(fork_id || '') } : null;
  try {
    return fn(session);
  } finally {
    _SCOPE = prev_scope;
    _FORK_SCOPE = prev_fork;
    if (session !== null) {
      session.release_device_lease();
      session.close_authoring_budget();
      session.closed = true;
      let summary: Record<string, any> = {
        schema: 'worker_loop_outcome',
        autoid: session.autoid,
        fork_id: session.fork_id,
        dispatch_id: session.dispatch_id,
        batch_run_id: session.batch_run_id,
        bed_lease_id: session.bed_lease_id,
        env_id: session.env_id,
        bed: session.actual_bed,
        device_access: session.device_access,
        capability_generation: {
          bed: session.capability_bed,
          full_version: session.capability_full_version,
          version: session.capability_version,
          build: session.capability_build,
          generation_id: session.capability_generation_id,
          manifest_sha256: session.capability_manifest_sha256,
          projection_sha256: session.capability_projection_sha256,
        },
        source_binding: {
          manifest_ref: session.source_manifest_ref,
          manifest_sha256: session.source_manifest_sha256,
          case_slice_sha256: session.source_case_slice_sha256,
        },
        lease_acquired_persisted: session.lease_acquired_persisted,
        lease_released_persisted: session.lease_released_persisted,
        shared_binding_persisted: session.shared_binding_persisted,
        lease_error: session.lease_error,
        stop_reason: session.stop_reason,
        compile_exhausted: session.compile_exhausted,
        max_probe_calls: session.max_probe_calls,
        probe_calls: session.probe_calls,
        probe_exhausted: session.probe_exhausted,
        probe_evidence: session.probe_evidence.map((item) => ({ ...item })),
        command_heads_query_receipts: session.command_heads_query_receipts.map((item) => ({ ...item })),
        not_compilable_reports: session.not_compilable_reports.map((item) => ({ ...item })),
        worker_claims: session.worker_claims.map((item) => deepcopy(item)),
        unsupported_feature_reports: session.unsupported_feature_reports.map((item) => ({ ...item })),
        semantic_attempts: session.semantic_attempts,
        infrastructure_attempts: session.infrastructure_attempts,
        prediction_chain: session.prediction_chain.map((item) => ({ ...item })),
        no_progress_decisions: session.no_progress_decisions.map((item) => ({ ...item })),
        compile_attempts: session.compile_attempts.map((item) => ({ ...item })),
        mechanical_case_submission_attempts: session.mechanical_case_submission_attempts,
        mechanical_case_rejections: session.mechanical_case_rejections.map((item) => deepcopy(item)),
        mechanical_case_repair_disclosures: session.mechanical_case_repair_disclosures.map((item) => ({ ...item })),
        gate_advisories: session.gate_advisories.map((item) => ({ ...item })),
        engine_gaps: session.engine_gaps.map((item) => deepcopy(item)),
        authoring_accounts: session.authoring_accounts.map((item) => deepcopy(item)),
        admission_rejection: deepcopy(session.admission_rejection),
      };
      let exact_heads_receipts: any;
      let exact_not_compilable_reports: any;
      try {
        exact_heads_receipts = deepcopy(summary['command_heads_query_receipts']);
        exact_not_compilable_reports = deepcopy(summary['not_compilable_reports']);
        summary = scrub_value(summary);
      } catch {
        exact_heads_receipts = deepcopy(summary['command_heads_query_receipts']);
        exact_not_compilable_reports = deepcopy(summary['not_compilable_reports']);
      }
      const base_identity_complete = [session.autoid, session.fork_id, session.dispatch_id, session.batch_run_id, session.expected_bed, session.expected_build, session.expected_module].every((value) => String(value || '').trim());
      const _touched_device = session.attempts > 0 || session.probe_calls > 0;
      const device_identity_complete = !_touched_device || ([session.env_id, session.actual_bed].every((value) => String(value || '').trim()) && (session.attempts === 0 || !!String(session.bed_lease_id || '').trim()));
      const identity_complete = base_identity_complete && device_identity_complete;
      if (!identity_complete) {
        summary['quarantined_reason'] = 'execution_identity_incomplete';
        _QUARANTINED.push(summary);
        if (_QUARANTINED.length > 4096) {
          _QUARANTINED.splice(0, _QUARANTINED.length - 4096);
        }
      } else if (session.revoked || _REVOKED_DISPATCHES.has(session.dispatch_id)) {
        summary['quarantined_reason'] = 'dispatch_revoked';
        _QUARANTINED.push(summary);
        if (_QUARANTINED.length > 4096) {
          _QUARANTINED.splice(0, _QUARANTINED.length - 4096);
        }
      } else {
        summary['command_heads_query_receipts'] = exact_heads_receipts;
        summary['not_compilable_reports'] = exact_not_compilable_reports;
        _SESSION_OUTCOMES.push(summary);
        if (_SESSION_OUTCOMES.length > 4096) {
          _SESSION_OUTCOMES.splice(0, _SESSION_OUTCOMES.length - 4096);
        }
      }
      _SESSIONS.delete(fork_id);
    }
  }
}

export function current_worker_device_session(): WorkerDeviceSession | null {
  const session = _SCOPE;
  if (session !== null) {
    return session;
  }
  let fork_id: string;
  try {
    const { get_config } = require("langgraph/config");
    const meta = (get_config() || {}).metadata || {};
    if (!['compile-worker', 'authoring-account-supplement'].includes(String(meta.fork_skill || ''))) {
      return null;
    }
    fork_id = String(meta.fork_id || '');
  } catch {
    return null;
  }
  if (!fork_id) {
    return null;
  }
  return _SESSIONS.get(fork_id) ?? null;
}

export function current_fork_execution_context(): Record<string, string> {
  const current = _FORK_SCOPE;
  return current ? { ...current } : {};
}

export function publish_worker_oracle(record: Record<string, any>): void {
  const session = current_worker_device_session();
  if (session === null) {
    return;
  }
  const item = { ...record };
  item['autoid'] = session.autoid;
  item['fork_id'] = session.fork_id;
  item['dispatch_id'] = session.dispatch_id;
  item['batch_run_id'] = session.batch_run_id;
  item['bed_lease_id'] = session.bed_lease_id;
  item['env_id'] = session.env_id;
  item['bed'] = session.actual_bed;
  const required_identity = [session.autoid, session.fork_id, session.dispatch_id, session.batch_run_id, session.bed_lease_id, session.env_id, session.actual_bed, session.expected_bed, session.expected_build, session.expected_module, String(item.run_id || ''), String(item.artifact_sha256 || '')];
  if (!required_identity.every((value) => String(value || '').trim())) {
    item['quarantined_reason'] = 'execution_identity_incomplete';
    _QUARANTINED.push(item);
    if (_QUARANTINED.length > 4096) {
      _QUARANTINED.splice(0, _QUARANTINED.length - 4096);
    }
    return;
  }
  if (session.revoked || _REVOKED_DISPATCHES.has(session.dispatch_id)) {
    item['quarantined_reason'] = 'dispatch_revoked';
    _QUARANTINED.push(item);
    if (_QUARANTINED.length > 4096) {
      _QUARANTINED.splice(0, _QUARANTINED.length - 4096);
    }
    return;
  }
  _COMPLETED.push(item);
  if (_COMPLETED.length > 4096) {
    _COMPLETED.splice(0, _COMPLETED.length - 4096);
  }
}

export function claim_worker_oracles(autoid: string, opts: { dispatch_id: string; batch_run_id?: string; since?: number }): Record<string, any>[] {
  const { dispatch_id, batch_run_id = '', since = 0.0 } = opts;
  if (!dispatch_id) {
    return [];
  }
  const claimed: Record<string, any>[] = [];
  const keep: Record<string, any>[] = [];
  for (const item of _COMPLETED) {
    if (String(item.autoid || '') === autoid && String(item.dispatch_id || '') === dispatch_id && (!batch_run_id || String(item.batch_run_id || '') === batch_run_id) && Number(item.ts || 0.0) >= since) {
      claimed.push({ ...item });
    } else {
      keep.push(item);
    }
  }
  _COMPLETED.length = 0;
  _COMPLETED.push(...keep);
  return claimed;
}

export function claim_worker_session_outcomes(autoid: string, opts: { dispatch_id: string; batch_run_id?: string }): Record<string, any>[] {
  const { dispatch_id, batch_run_id = '' } = opts;
  if (!dispatch_id) {
    return [];
  }
  const claimed: Record<string, any>[] = [];
  const keep: Record<string, any>[] = [];
  for (const item of _SESSION_OUTCOMES) {
    if (String(item.autoid || '') === autoid && String(item.dispatch_id || '') === dispatch_id && (!batch_run_id || String(item.batch_run_id || '') === batch_run_id)) {
      claimed.push({ ...item });
    } else {
      keep.push(item);
    }
  }
  _SESSION_OUTCOMES.length = 0;
  _SESSION_OUTCOMES.push(...keep);
  return claimed;
}

export function recover_worker_dispatch_journal(autoid: string, opts: { dispatch_id: string; batch_run_id: string }): Record<string, any>[] {
  const { dispatch_id, batch_run_id } = opts;
  if (!autoid || !dispatch_id || !batch_run_id) {
    return [];
  }
  const sh = require("./compile_engine/_shared");
  const root: P = sh.project_root().joinpath('runtime', 'worker_oracle_journal');
  if (!root.is_dir() || root.is_symlink()) {
    return [];
  }
  const out: Record<string, any>[] = [];
  for (const p of root.glob('*.jsonl').sort((a: P, b: P) => a.toString() < b.toString() ? -1 : 1)) {
    try {
      if (p.is_symlink() || fs.statSync(p.toString()).size > 8 * 1024 * 1024) {
        continue;
      }
      const lines = fs.readFileSync(p.toString(), 'utf8').split(/\r?\n/);
      let line_no = 0;
      for (const line of lines) {
        line_no += 1;
        if (line === '' && line_no === lines.length) {
          continue;
        }
        let item: any;
        try {
          item = JSON.parse(line);
        } catch {
          continue;
        }
        if (!_isDict(item)) {
          continue;
        }
        if (String(item.autoid || '') !== autoid || String(item.dispatch_id || '') !== dispatch_id || String(item.batch_run_id || '') !== batch_run_id) {
          continue;
        }
        out.push({ ...item, _journal_file: p.name, _journal_line: line_no });
      }
    } catch {
      continue;
    }
  }
  return out;
}

export function authoring_budget_receipt(autoid: string, opts: { dispatch_id: string; batch_run_id: string }): [Record<string, any>, string] {
  const { dispatch_id, batch_run_id } = opts;
  const rows = recover_worker_dispatch_journal(autoid, { dispatch_id, batch_run_id });
  if (!rows.length) {
    return [{}, 'authoring_budget_missing'];
  }
  const groups: Map<string, Record<string, any>[]> = new Map();
  for (const row of rows) {
    const key = String(row.fork_id || '');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(row);
  }
  const receipts: Record<string, any>[] = [];
  for (const [fork_id, events] of groups) {
    const observed = events.filter((row) => row.ev === 'authoring_budget_observed');
    const closed = events.filter((row) => row.ev === 'authoring_budget_closed');
    if (!fork_id || !observed.length || closed.length !== 1) {
      return [{}, 'authoring_budget_unclosed'];
    }
    let total = 0;
    let domain = 0;
    const first = observed[0].budget || {};
    const limit = first.total_limit;
    const domain_limit = first.domain_limit;
    const schema_names = first.schema_names;
    if (typeof limit !== "number" || !Number.isInteger(limit) || limit < 1 || typeof domain_limit !== "number" || !Number.isInteger(domain_limit) || domain_limit < 0 || !Array.isArray(schema_names) || !schema_names.every((name: any) => typeof name === "string") || limit !== domain_limit + 1 + (schema_names.length ? 1 : 0)) {
      return [{}, 'authoring_budget_invalid'];
    }
    let index = 0;
    for (const row of observed) {
      index += 1;
      const budget = row.budget || {};
      const calls = budget.response_calls;
      if (calls !== null && calls !== undefined && (!Array.isArray(calls) || !calls.every((name: any) => typeof name === "string"))) {
        return [{}, 'authoring_budget_invalid'];
      }
      total += (calls || []).length;
      domain += (calls || []).filter((name: any) => ![...schema_names, 'submit_authoring_account'].includes(name)).length;
      if (!accepts_engine_schema(budget.schema, 'authoring_tool_budget') || budget.sequence !== index || budget.total_limit !== limit || budget.domain_limit !== domain_limit || JSON.stringify(budget.schema_names) !== JSON.stringify(schema_names) || budget.closed !== false || budget.used_tool_calls !== total || budget.used_domain_calls !== domain || budget.remaining_tool_calls !== Math.max(0, limit - total)) {
        return [{}, 'authoring_budget_invalid'];
      }
    }
    const end = closed[0];
    const expected_end = { ...observed[observed.length - 1]['budget'], closed: true };
    if (JSON.stringify(end.budget || {}) !== JSON.stringify(expected_end) || Number(end._journal_line ?? 0) <= Number(observed[observed.length - 1]._journal_line ?? 0)) {
      return [{}, 'authoring_budget_invalid'];
    }
    const closed_body: Record<string, any> = {};
    for (const [key, value] of Object.entries(end)) {
      if (!key.startsWith('_')) closed_body[key] = value;
    }
    receipts.push({
      fork_id,
      total_limit: limit,
      used_tool_calls: total,
      source_manifest_ref: end.source_manifest_ref,
      source_manifest_sha256: end.source_manifest_sha256,
      source_case_slice_sha256: end.source_case_slice_sha256,
      closed_fact_sha256: persisted_surface_sha256(closed_body),
    });
  }
  const limit = Math.min(...receipts.map((row) => row['total_limit']));
  const used = receipts.reduce((acc, row) => acc + row['used_tool_calls'], 0);
  const result: Record<string, any> = {
    schema: engine_schema_id('authoring_tool_budget_receipt'),
    autoid,
    dispatch_id,
    batch_run_id,
    total_limit: limit,
    used_tool_calls: used,
    remaining_tool_calls: Math.max(0, limit - used),
    closed: true,
    fork_receipts: receipts.sort((a, b) => a['fork_id'] < b['fork_id'] ? -1 : a['fork_id'] > b['fork_id'] ? 1 : 0),
  };
  return [{ ...result, receipt_sha256: persisted_surface_sha256(result) }, ''];
}

export function persist_worker_dispatch_termination(opts: {
  skill: string; agent: string; autoid: string; fork_id: string; dispatch_id: string; batch_run_id: string;
  execution_identity: Record<string, any>; source_binding: Record<string, any>; termination: Record<string, any>;
  usage: Record<string, any>; tool_calls: Record<string, any>; structured_response_attempts: number;
}): boolean {
  const { skill, agent, autoid, fork_id, dispatch_id, batch_run_id, execution_identity, source_binding, termination, usage, tool_calls, structured_response_attempts } = opts;
  if (!dispatch_id || !batch_run_id || !autoid || !fork_id) {
    return false;
  }
  const excluded = new Set(['skill', 'agent', 'autoid', 'fork_id', 'dispatch_id', 'batch_run_id', 'device_access']);
  const proto = WorkerDeviceSession.prototype;
  const extra: Record<string, any> = {};
  for (const [key, value] of Object.entries(execution_identity)) {
    if (key in proto || Object.prototype.hasOwnProperty.call(new WorkerDeviceSession({ skill: '', agent: '', autoid: '', fork_id: '' }), key)) {
      if (!excluded.has(key)) {
        extra[key] = value;
      }
    }
  }
  const recorder = new WorkerDeviceSession({ skill, agent, autoid, fork_id, dispatch_id, batch_run_id, device_access: false, ...extra, ...source_binding });
  return persist_worker_session_event(recorder, {
    ev: 'worker_dispatch_terminated',
    invocation_finished: true,
    termination: deepcopy(termination),
    usage: deepcopy(usage),
    tool_calls: { ...tool_calls },
    structured_response_attempts,
  });
}

export function dispatch_identity_from_brief(brief: string): [string, string] {
  let payload: any;
  try {
    const { parse_compile_worker_brief } = require("./compile_engine/worker_protocol");
    payload = parse_compile_worker_brief(String(brief || ''));
  } catch {
    return ['', ''];
  }
  const identity = payload['identity'];
  let dispatch_id = String(identity.worker_dispatch_id || '');
  let batch_run_id = String(identity.batch_run_id || '');
  if (!_DISPATCH_ID_RE.test(dispatch_id)) {
    dispatch_id = '';
  }
  if (batch_run_id && !_DISPATCH_ID_RE.test(batch_run_id)) {
    batch_run_id = '';
  }
  return [dispatch_id, batch_run_id];
}

export function device_access_from_brief(brief: string): boolean {
  let payload: any;
  try {
    const { parse_compile_worker_brief } = require("./compile_engine/worker_protocol");
    payload = parse_compile_worker_brief(String(brief || ''));
  } catch {
    return false;
  }
  const identity = payload['identity'];
  let attempt: number;
  try {
    attempt = Math.trunc(Number(identity.dispatch_attempt) || 0);
  } catch {
    return false;
  }
  return attempt > 1;
}

export function worker_execution_identity_from_brief(brief: string): Record<string, any> {
  let payload: any;
  try {
    const { parse_compile_worker_brief } = require("./compile_engine/worker_protocol");
    payload = parse_compile_worker_brief(String(brief || ''));
  } catch {
    return {};
  }
  const identity = payload['identity'];
  const execution = identity['execution'];
  const capability = identity['capability'];
  const out: Record<string, any> = {
    bed_lease_id: '',
    expected_bed: String(execution.bed || ''),
    expected_build: String(execution.build || ''),
    expected_module: String(execution.module || ''),
    capability_bed: String(capability.bed || ''),
    capability_full_version: String(capability.full_version || ''),
    capability_version: String(capability.version || ''),
    capability_build: String(capability.build || ''),
    capability_generation_id: String(capability.generation_id || ''),
    capability_manifest_sha256: String(capability.manifest_sha256 || ''),
    capability_projection_sha256: String(capability.projection_sha256 || ''),
    authored_round: Math.trunc(Number(identity.authored_round) || 1),
  };
  for (const [key, value] of Object.entries({ ...out })) {
    if (key === 'authored_round') {
      continue;
    }
    if ((value as string).length > 256 || [...(value as string)].some((ch) => ch.codePointAt(0)! < 32)) {
      out[key] = '';
    }
  }
  if (out['capability_version'] && !/^\d+(?:\.\d+){1,2}$/.test(out['capability_version'])) {
    out['capability_version'] = '';
  }
  if (out['capability_build'] && !/^\d+$/.test(out['capability_build'])) {
    out['capability_build'] = '';
  }
  if (out['capability_generation_id'] && !/^g-[0-9a-f]{24}-[0-9a-f]{24}$/.test(out['capability_generation_id'])) {
    out['capability_generation_id'] = '';
  }
  if (out['capability_manifest_sha256'] && !/^[0-9a-f]{64}$/.test(out['capability_manifest_sha256'])) {
    out['capability_manifest_sha256'] = '';
  }
  if (out['capability_projection_sha256'] && !/^[0-9a-f]{64}$/.test(out['capability_projection_sha256'])) {
    out['capability_projection_sha256'] = '';
  }
  return out;
}

export function revoke_worker_dispatch(dispatch_id: string): void {
  const id = String(dispatch_id || '');
  if (!id) {
    return;
  }
  _REVOKED_DISPATCHES.add(id);
  for (const session of _SESSIONS.values()) {
    if (session.dispatch_id === id) {
      session.revoked = true;
    }
  }
}

export function quarantined_worker_oracles(): Record<string, any>[] {
  return _QUARANTINED.map((item) => ({ ...item }));
}
