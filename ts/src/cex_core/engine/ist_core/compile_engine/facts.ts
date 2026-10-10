import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { P as Path } from "../../_py";
import { open_directory_nofollow, validate_json_budget } from "../../case_compiler/_sealed_io";
import * as EE from "./engine_errors";
import * as CC from "./conflict_chain";
import { FACT_EVENTS, REGISTRY_LOCATION, UnregisteredFactEvent, require_registered, unregistered_fact_events } from "./fact_events";

const logger = console;

const _DISCLOSED_UNREGISTERED = new Set<string>();

export const CTX_DELIVERY = "delivery";
export const CTX_SUBSET = "subset";
export const EXECUTION_DISPATCH_EVENTS: Record<string, string> = {
  [CTX_DELIVERY]: "delivery_dispatch_started",
  [CTX_SUBSET]: "subset_dispatch_started",
};
export const FRAMEWORK_RESULT_DOMAIN = new Set(["pass", "fail"]);
export const RESULT_DOMAIN = new Set(["pass", "fail", "broken", "not_run"]);
export const NO_PROGRESS_K = 3;
export const ATTRIBUTION_TEXT_MAX_CHARS = 8000;
export const FRAMEWORK_RESULT_SCHEMA_SINCE = "内部评审日期（已脱敏）";

function _is_wsl_ntfs(): boolean {
  try {
    if (process.platform === "win32") return false;
    return process.cwd().startsWith("/mnt/");
  } catch {
    return false;
  }
}
const _WSL_NTFS = _is_wsl_ntfs();

function _is_ntfs_path(p: string | Path): boolean {
  if (process.platform === "win32") return false;
  try {
    const s = String(p);
    return s.startsWith("/mnt/") || (s.length >= 2 && s[1] === ":");
  } catch {
    return false;
  }
}

function _check_uid_match(file_uid: number): boolean {
  if (process.platform !== "win32" && typeof (os as any).getuid === "function" && Number(file_uid) === (os as any).getuid()) return true;
  if (process.platform === "win32") return true;
  return _WSL_NTFS;
}

function _clear_nonblock(file_fd: number): void {
  // Node.js does not expose fcntl; no-op.
}

function _pread_all(file_fd: number, size: number, offset: number = 0): Buffer {
  if (size <= 0) return Buffer.alloc(0);
  const chunks: Buffer[] = [];
  let got = 0;
  const buf = Buffer.alloc(Math.min(size, 1024 * 1024));
  while (got < size) {
    const toRead = Math.min(buf.length, size - got);
    const n = fs.readSync(file_fd, buf, 0, toRead, offset + got);
    if (n <= 0) break;
    chunks.push(buf.subarray(0, n));
    got += n;
  }
  return Buffer.concat(chunks);
}

export class FactLedgerCorruptError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "FactLedgerCorruptError";
  }
}

const _MAX_FACT_LEDGER_BYTES = 512 * 1024 * 1024;
const _MAX_FACT_LINE_BYTES = 4 * 1024 * 1024;

function _ledger_size_error(path_: Path, size: number, opts: { stage: string }): FactLedgerCorruptError {
  return new FactLedgerCorruptError(
    `事实流超出大小限制: stage=${opts.stage}, path=${path_}, logical_size_bytes=${Math.floor(size)}, limit_bytes=${_MAX_FACT_LEDGER_BYTES}`
  );
}

function _decode_fact_line(raw: Buffer, path_: Path, line_number: number): Record<string, any> {
  if (raw.length > _MAX_FACT_LINE_BYTES) {
    throw new FactLedgerCorruptError(`事实流第 ${line_number} 行超出大小限制: ${path_}`);
  }
  validate_json_budget(raw, {
    errorType: FactLedgerCorruptError,
    message: `事实流第 ${line_number} 行超出结构预算: ${path_}`,
    maxDepth: 128,
    maxTokens: 500000,
  });
  try {
    const item = JSON.parse(raw.toString("utf8"));
    if (typeof item !== "object" || item === null || Array.isArray(item) || !item.ev) {
      throw new FactLedgerCorruptError(`事实流第 ${line_number} 行不是有效事实: ${path_}`);
    }
    return item;
  } catch (exc) {
    if (exc instanceof FactLedgerCorruptError) throw exc;
    throw new FactLedgerCorruptError(`事实流第 ${line_number} 行损坏: ${path_}`);
  }
}

function _disclose_unregistered_events(facts: Record<string, any>[], path_: Path): void {
  for (const name of unregistered_fact_events(facts)) {
    const mark = `${path_}:${name}`;
    if (_DISCLOSED_UNREGISTERED.has(mark)) continue;
    _DISCLOSED_UNREGISTERED.add(mark);
    logger.warn(`事实流含未登记的事件名（照常读出，不丢行）: ev=${name}, path=${path_}, registry=${REGISTRY_LOCATION}`);
  }
}

function _decode_facts(payload: Buffer, path_: Path): Record<string, any>[] {
  const out: Record<string, any>[] = [];
  const lines = payload.toString("utf8").split(/\r?\n/);
  for (let line_number = 1; line_number <= lines.length; line_number++) {
    const raw = Buffer.from(lines[line_number - 1], "utf8");
    if (!raw.toString("utf8").trim()) continue;
    out.push(_decode_fact_line(raw, path_, line_number));
  }
  const deduped = dedup(out);
  _disclose_unregistered_events(deduped, path_);
  return deduped;
}

function _repair_torn_tail(file_fd: number, path_: Path): void {
  const size = fs.fstatSync(file_fd).size;
  if (!_is_ntfs_path(path_) && size > _MAX_FACT_LEDGER_BYTES) {
    throw _ledger_size_error(path_, size, { stage: "repair_precheck" });
  }
  if (size <= 0 || _pread_all(file_fd, 1, size - 1).toString() === "\n") return;
  const start = Math.max(0, size - _MAX_FACT_LINE_BYTES - 1);
  const tail = _pread_all(file_fd, size - start, start);
  const last_newline = tail.lastIndexOf("\n");
  if (last_newline < 0 && start > 0) {
    throw new FactLedgerCorruptError("事实流尾帧超出大小限制，不能安全修复");
  }
  const frame_start = start + last_newline + 1;
  const frame = _pread_all(file_fd, size - frame_start, frame_start);
  let complete = false;
  try {
    _decode_fact_line(frame, path_, 1);
    complete = true;
  } catch {
    complete = false;
  }
  if (complete) {
    fs.writeSync(file_fd, Buffer.from("\n"), 0, 1, size);
  } else {
    fs.ftruncateSync(file_fd, frame_start);
  }
  fs.fsyncSync(file_fd);
}

export function append_facts(path_: Path, facts: Record<string, any>[]): number {
  require_registered(facts, { where: String(path_) });
  const { stamp_decision_axis } = require("./routing_closed_sets");
  facts = facts.map((fact) => stamp_decision_axis(fact));
  const directory_fd = open_directory_nofollow(path_.parent.toString(), {
    errorType: FactLedgerCorruptError,
    invalid_message: "事实流路径无效",
    unavailable_message: "事实流目录不可安全写入",
    create_missing: true,
  }) as unknown as number;
  let file_fd: number | null = null;
  try {
    const { open_or_create_regular_at_nofollow } = require("../../case_compiler/_sealed_io");
    file_fd = open_or_create_regular_at_nofollow(directory_fd, path_.name, {
      flags: fs.constants.O_RDWR | fs.constants.O_APPEND | (((fs.constants as any).O_NOFOLLOW ?? 0) | ((fs.constants as any).O_CLOEXEC ?? 0)),
      mode: 0o600,
      errorType: FactLedgerCorruptError,
      unavailable_message: "事实流不可安全打开",
    }) as number;
  } catch (exc) {
    fs.closeSync(directory_fd);
    throw exc;
  }
  try {
    const info = fs.fstatSync(file_fd);
    if (!info.isFile() || Number(info.nlink) !== 1 || !_check_uid_match(Number(info.uid))) {
      throw new FactLedgerCorruptError("事实流必须是当前用户拥有的单链接普通文件");
    }
    if (!_is_ntfs_path(path_) && info.size > _MAX_FACT_LEDGER_BYTES) {
      throw _ledger_size_error(path_, info.size, { stage: "open_precheck" });
    }
    // Node.js does not support flock; use exclusive file access as approximation
    const locked_info = fs.fstatSync(file_fd);
    const path_info = fs.statSync(path_.toString());
    if (
      Number(path_info.dev) !== Number(locked_info.dev) ||
      Number(path_info.ino) !== Number(locked_info.ino) ||
      !locked_info.isFile() ||
      !path_info.isFile() ||
      Number(locked_info.nlink) !== 1 ||
      Number(path_info.nlink) !== 1 ||
      !_check_uid_match(Number(locked_info.uid)) ||
      !_check_uid_match(Number(path_info.uid)) ||
      (!_is_ntfs_path(path_) && Number(locked_info.size) > _MAX_FACT_LEDGER_BYTES) ||
      (!_is_ntfs_path(path_) && Number(path_info.size) > _MAX_FACT_LEDGER_BYTES)
    ) {
      throw new FactLedgerCorruptError("事实流在加锁前被替换");
    }
    const locked_size = Math.max(Number(locked_info.size), Number(path_info.size));
    if (!_is_ntfs_path(path_) && locked_size > _MAX_FACT_LEDGER_BYTES) {
      throw _ledger_size_error(path_, locked_size, { stage: "locked_precheck" });
    }
    _repair_torn_tail(file_fd, path_);
    const repaired_info = fs.fstatSync(file_fd);
    if (!repaired_info.isFile() || Number(repaired_info.nlink) !== 1 || !_check_uid_match(Number(repaired_info.uid)) || (!_is_ntfs_path(path_) && repaired_info.size > _MAX_FACT_LEDGER_BYTES)) {
      throw new FactLedgerCorruptError("事实流修复后身份异常");
    }
    if (!_is_ntfs_path(path_) && repaired_info.size > _MAX_FACT_LEDGER_BYTES) {
      throw _ledger_size_error(path_, repaired_info.size, { stage: "repair_postcheck" });
    }
    const size = repaired_info.size;
    const payload = _pread_all(file_fd, size);
    if (payload.length !== size) {
      throw new FactLedgerCorruptError(`事实流短读未拿到完整快照: path=${path_}, logical_size_bytes=${Math.floor(size)}, read_bytes=${payload.length}`);
    }
    const existing = new Set(_decode_facts(payload, path_).map(idem_key));
    let written = 0;
    for (const f of facts) {
      const f_with_pid = { ...f, _pid: process.pid };
      const k = idem_key(f_with_pid);
      if (existing.has(k)) continue;
      const encoded = Buffer.from(JSON.stringify(f_with_pid) + "\n", "utf8");
      _decode_fact_line(encoded.subarray(0, encoded.length - 1), path_, written + 1);
      const current_size = fs.fstatSync(file_fd).size;
      if (!_is_ntfs_path(path_) && current_size + encoded.length > _MAX_FACT_LEDGER_BYTES) {
        throw new FactLedgerCorruptError(
          `事实流追加将超出大小限制: path=${path_}, logical_size_bytes=${Math.floor(current_size)}, append_bytes=${encoded.length}, limit_bytes=${_MAX_FACT_LEDGER_BYTES}`
        );
      }
      fs.writeSync(file_fd, encoded, 0, encoded.length, null);
      fs.fsyncSync(file_fd);
      existing.add(k);
      written += 1;
    }
    return written;
  } finally {
    fs.closeSync(file_fd);
    fs.closeSync(directory_fd);
  }
}

function _read_facts_under_shared_lock(path_: Path): Buffer {
  let directory_fd: number;
  try {
    directory_fd = open_directory_nofollow(path_.parent.toString(), {
      errorType: FactLedgerCorruptError,
      invalid_message: "事实流路径无效",
      unavailable_message: "事实流目录不可安全读取",
      preserve_missing: true,
    }) as unknown as number;
  } catch (exc: any) {
    if (exc instanceof Error && (exc as any).code === "ENOENT") return Buffer.alloc(0);
    throw exc;
  }
  try {
    let file_fd: number;
    try {
      file_fd = fs.openSync(path_.toString(), fs.constants.O_RDONLY | ((fs.constants as any).O_NOFOLLOW ?? 0) | ((fs.constants as any).O_CLOEXEC ?? 0) | ((fs.constants as any).O_NONBLOCK ?? 0));
    } catch (exc: any) {
      if (exc instanceof Error && (exc as any).code === "ENOENT") return Buffer.alloc(0);
      throw new FactLedgerCorruptError("事实流不可读");
    }
    try {
      const before = fs.fstatSync(file_fd);
      let named: fs.Stats;
      try {
        named = fs.statSync(path_.toString());
      } catch (exc) {
        throw new FactLedgerCorruptError("事实流在共享锁内不可用");
      }
      if (
        Number(before.dev) !== Number(named.dev) ||
        Number(before.ino) !== Number(named.ino) ||
        !before.isFile() ||
        !named.isFile() ||
        Number(before.nlink) !== 1 ||
        Number(named.nlink) !== 1 ||
        !_check_uid_match(Number(before.uid)) ||
        !_check_uid_match(Number(named.uid))
      ) {
        throw new FactLedgerCorruptError("事实流必须是未替换的单链接普通文件");
      }
      const size = Number(before.size);
      if (!_is_ntfs_path(path_) && size > _MAX_FACT_LEDGER_BYTES) {
        throw _ledger_size_error(path_, size, { stage: "shared_read_precheck" });
      }
      _clear_nonblock(file_fd);
      const payload = _pread_all(file_fd, size);
      const after = fs.fstatSync(file_fd);
      if (Number(after.dev) !== Number(before.dev) || Number(after.ino) !== Number(before.ino) || Number(after.size) !== size || Number(after.mtimeMs) !== Number(before.mtimeMs)) {
        throw new FactLedgerCorruptError("事实流共享锁快照身份漂移");
      }
      if (payload.length !== size) {
        throw new FactLedgerCorruptError(`事实流短读未拿到完整快照: path=${path_}, logical_size_bytes=${Math.floor(size)}, read_bytes=${payload.length}`);
      }
      return payload;
    } finally {
      fs.closeSync(file_fd);
    }
  } finally {
    fs.closeSync(directory_fd);
  }
}

export function load_facts(path_: Path): Record<string, any>[] {
  const payload = _read_facts_under_shared_lock(new Path(path_.toString()));
  return _decode_facts(payload, path_);
}

export function is_suspend_placeholder_decision(f: Record<string, any>): boolean {
  return f.ev === "decision" && String(f.token ?? "") === "suspend";
}

export function idem_key(f: Record<string, any>): string {
  const ev = String(f.ev ?? "");
  const aid = String(f.aid ?? "");
  if (ev === "attribution_protocol_error") {
    const dispatch_id = String(f.dispatch_id ?? "");
    if (dispatch_id) return `${ev}:${aid}:${dispatch_id}:${String(f.reason_code ?? "")}`;
  }
  if (ev === "verdict") return `${ev}:${aid}:${String(f.run_id ?? "")}`;
  if (ev === "authored") return `${ev}:${aid}:${Number(f.round ?? 0)}`;
  if (ev === "attribution") {
    const rid = String(f.run_id ?? "");
    const key = rid ? `${ev}:${aid}:${rid}` : `${ev}:${aid}:${Number(f.round ?? 0)}`;
    return structural_interference_attribution(f) ? `${key}:structural_interference` : key;
  }
  if (ev === "escalated") {
    const rid = String(f.run_id ?? "");
    if (rid) return `${ev}:${aid}:${rid}`;
  }
  if (ev === "decision") {
    const key = `${ev}:${aid}:${String(f.question_id ?? f.question ?? "").slice(0, 120)}`;
    if (CC.is_direct_abandon_decision(f)) return `${key}:direct_abandon`;
    if (is_suspend_placeholder_decision(f)) return `${key}:suspend`;
    return key;
  }
  if (["writeback", "rollback"].includes(ev)) {
    return `${ev}:${aid}:${String(f.voucher_run ?? f.of ?? "")}:${String(f.reason ?? "")}`;
  }
  if (ev === "metrics_scope") return `${ev}:${String(f.schema ?? "")}:${Number(f.run_seq ?? 0)}`;
  if (["gate_rejected", "gate_disabled", "ir_gap"].includes(ev)) {
    const occurrence_id = String(f.occurrence_id ?? "");
    if (occurrence_id) return `${ev}:${aid}:${occurrence_id}`;
  }
  if (ev === "worker_device_attempt") {
    const rid = String(f.run_id ?? "");
    if (rid) return `${ev}:${aid}:${rid}`;
  }
  if (ev === "probe_evidence") {
    const probe_id = String(f.probe_id ?? "");
    if (probe_id) return `${ev}:${aid}:${probe_id}`;
  }
  if (ev === "llm_usage") {
    const usage_id = String(f.usage_id ?? "");
    if (usage_id) return `${ev}:${aid}:${usage_id}`;
  }
  if (ev === "worker_outcome") {
    const rid = String(f.run_id ?? "");
    const artifact = String(f.artifact ?? "");
    if (rid || artifact) return `${ev}:${aid}:${String(f.outcome ?? "")}:${rid}:${artifact}:${Number(f.round ?? 0)}`;
  }
  if (ev === "worker_loop_outcome") {
    const dispatch_id = String(f.dispatch_id ?? "");
    if (dispatch_id) return `${ev}:${aid}:${dispatch_id}`;
  }
  if (ev === "compile_attempt_resolved") {
    const attempt_id = String(f.compile_attempt_id ?? "");
    if (attempt_id) return `${ev}:${aid}:${attempt_id}`;
  }
  if (ev === "mechanical_case_submission_rejected") {
    const occurrence_id = String(f.occurrence_id ?? "");
    if (occurrence_id) return `${ev}:${aid}:${occurrence_id}`;
  }
  if (ev === "worker_claim") {
    const claim_id = String(f.claim_id ?? "");
    if (claim_id) return `${ev}:${aid}:${claim_id}`;
  }
  if (ev === "no_progress_decision") {
    const decision_id = String(f.decision_id ?? "");
    if (decision_id) return `${ev}:${aid}:${decision_id}`;
  }
  if (ev === "compilation_assessment") {
    const assessment_id = String(f.assessment_id ?? "");
    if (assessment_id) return `${ev}:${aid}:${assessment_id}`;
  }
  if (ev === "case_terminal_outcome") {
    const terminal_id = String(f.terminal_id ?? "");
    if (terminal_id) return `${ev}:${aid}:${terminal_id}`;
  }
  if (ev === "compilability") {
    const revision = String(f.revision ?? f.decision_id ?? f.artifact ?? f.round ?? "");
    if (revision) return `${ev}:${aid}:${revision}:${String(f.status ?? f.compilability ?? "")}:${f.compilable}`;
  }
  if (["pass_audit", "assertion_strength_audit"].includes(ev)) {
    const artifact = String(f.artifact ?? "");
    const revision = String(f.audit_revision ?? f.run_id ?? "");
    const detector = String(f.detector ?? "");
    if (artifact || revision || detector) return `${ev}:${aid}:${artifact}:${revision}:${detector}`;
  }
  const core: Record<string, any> = {};
  for (const [k, v] of Object.entries(f)) {
    if (!String(k).startsWith("_") && k !== "decision_axis") core[k] = v;
  }
  return `${ev}:${aid}:${JSON.stringify(core)}`;
}

export function dedup(facts: Record<string, any>[]): Record<string, any>[] {
  const seen = new Set<string>();
  const out: Record<string, any>[] = [];
  for (const f of facts) {
    const k = idem_key(f);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(f);
  }
  return out;
}

export function this_run_slice(facts: Record<string, any>[]): Record<string, any>[] {
  let idx = -1;
  for (let i = facts.length - 1; i >= 0; i--) {
    if (facts[i].ev === "run_start") {
      idx = i;
      break;
    }
  }
  return idx >= 0 ? facts.slice(idx + 1) : facts;
}

export function volume_sequence(facts: Record<string, any>[]): number {
  const seqs = facts
    .filter((f) => f.ev === "merged")
    .map((f) => String(f.run_id ?? "").split(":").pop() ?? "")
    .filter((tail) => /^\d+$/.test(tail))
    .map((tail) => Number(tail));
  return seqs.length ? Math.max(...seqs) : 0;
}

function _facts_of(facts: Record<string, any>[], aid: string, ev: string | null = null): Record<string, any>[] {
  let filtered = facts;
  if (["verdict", "attribution", "diagnosis", "case_terminal_outcome"].includes(ev ?? "")) {
    const { effective_case_facts } = require("./engine_quarantine");
    filtered = effective_case_facts(facts, aid);
  }
  return filtered.filter((f) => String(f.aid ?? "") === aid && (ev === null || f.ev === ev));
}

export function latest_verdict(facts: Record<string, any>[], aid: string, ctx: string | null = null, artifact: string | null = null): Record<string, any> | null {
  const vs = _facts_of(facts, aid, "verdict").filter(
    (f) => (ctx === null || f.ctx === ctx) && (artifact === null || String(f.artifact ?? "") === artifact)
  );
  return vs.length ? vs[vs.length - 1] : null;
}

const _NON_PASS_VERDICT_RESULTS = ["fail", "broken", "not_run"];

export function delivery_verdict_bound_to_volume(
  facts: Record<string, any>[],
  aid: string,
  current_volume: string,
  current_volume_artifact_sha256: string = ""
): Record<string, any> | null {
  const v = latest_verdict(facts, aid, CTX_DELIVERY);
  if (!v) return null;
  const current_sha = String(current_volume_artifact_sha256 ?? "").toLowerCase();
  const verdict_sha = String(v.volume_artifact_sha256 ?? "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(current_sha) || !/^[0-9a-f]{64}$/.test(verdict_sha) || verdict_sha !== current_sha) return null;
  if (String(v.volume ?? "") !== String(current_volume)) return null;
  return v;
}

export function deliverable(
  facts: Record<string, any>[],
  aid: string,
  current_artifact: string,
  current_volume: string,
  current_volume_artifact_sha256: string = ""
): boolean {
  const v = delivery_verdict_bound_to_volume(facts, aid, current_volume, current_volume_artifact_sha256);
  return Boolean(v && v.result === "pass" && String(v.artifact ?? "") === current_artifact);
}

export function volume_resident_accounted(
  facts: Record<string, any>[],
  aid: string,
  current_volume: string,
  current_volume_artifact_sha256: string = ""
): boolean {
  const v = delivery_verdict_bound_to_volume(facts, aid, current_volume, current_volume_artifact_sha256);
  return Boolean(v) && _NON_PASS_VERDICT_RESULTS.includes(String(v?.result ?? ""));
}

export function subset_verified(facts: Record<string, any>[], aid: string, current_artifact: string): boolean {
  const v = latest_verdict(facts, aid, null, current_artifact);
  return Boolean(v && v.result === "pass");
}

function _norm_sigs(xs: any): Set<string> {
  let _n: (s: string) => string;
  try {
    _n = require("../tools/device/batch_tools").normalize_fail_signature;
  } catch {
    _n = (s: string) => s;
  }
  const out = new Set<string>();
  for (const x of xs ?? []) {
    if (Array.isArray(x) && x.length === 2) {
      out.add(`${String(x[0])}:${_n(String(x[1]))}`);
    } else {
      out.add(_n(String(x)));
    }
  }
  return out;
}

export function sig_key_text(s: any): string {
  if (Array.isArray(s) && s.length === 2) return String(s[1]);
  return String(s);
}

export function sig_key_texts(raw_sigs: any): string[] {
  return [..._norm_sigs(raw_sigs)].map(sig_key_text).sort();
}

export function canonical_failure_key(domain: string, value: any): string {
  let payload: string;
  try {
    payload = JSON.stringify(value);
  } catch {
    payload = String(value);
  }
  return `${String(domain ?? "unknown").trim().toLowerCase()}:${payload}`;
}

function _atomic_failure_keys(domain: string, value: any): string[] {
  let atoms: any[];
  if (Array.isArray(value) || value instanceof Set) {
    atoms = [...value];
  } else if (value === null || value === undefined || value === "") {
    atoms = [];
  } else {
    atoms = [value];
  }
  return [...new Set(atoms.filter((atom) => atom !== null && atom !== undefined && atom !== "").map((atom) => canonical_failure_key(domain, atom)))].sort();
}

function _history_failure_keys(item: Record<string, any>, domain: string): string[] {
  const keys = item.failure_keys;
  if (Array.isArray(keys) || keys instanceof Set) {
    return [...new Set([...keys].map((k) => String(k)).filter(Boolean))].sort();
  }
  return [];
}

export function no_progress_step(
  history: Record<string, any>[] | readonly Record<string, any>[],
  opts: { domain: string; value: any; revision_sha256: string }
): Record<string, any> {
  const normalized_domain = String(opts.domain ?? "unknown").trim().toLowerCase();
  const current_keys = _atomic_failure_keys(normalized_domain, opts.value);
  const revision = String(opts.revision_sha256 ?? "");
  const rows = (history ?? [])
    .filter((item) => typeof item === "object" && item !== null)
    .map((item) => ({
      failure_keys: _history_failure_keys(item, normalized_domain),
      revision_sha256: String(item.revision_sha256 ?? ""),
    }));
  rows.push({ failure_keys: current_keys, revision_sha256: revision });
  const refs_by_key: Record<string, string[]> = {};
  for (const key of current_keys) {
    const revisions: string[] = [];
    for (let i = rows.length - 1; i >= 0; i--) {
      if (!rows[i].failure_keys.includes(key)) break;
      const candidate = rows[i].revision_sha256;
      if (candidate && !revisions.includes(candidate)) revisions.push(candidate);
    }
    refs_by_key[key] = [...revisions].reverse();
  }
  const ranked_keys = [...current_keys].sort((a, b) => refs_by_key[b].length - refs_by_key[a].length || a.localeCompare(b));
  const primary_key = ranked_keys[0] ?? "";
  const primary_refs = refs_by_key[primary_key] ?? [];
  const streaks: Record<string, number> = {};
  for (const key of Object.keys(refs_by_key).sort()) streaks[key] = refs_by_key[key].length;
  const stop_keys = Object.entries(streaks)
    .filter(([, streak]) => streak >= NO_PROGRESS_K)
    .map(([key]) => key)
    .sort();
  return {
    domain: normalized_domain,
    failure_key: primary_key,
    failure_keys: current_keys,
    streak: primary_refs.length,
    streaks,
    threshold: NO_PROGRESS_K,
    revision_refs: primary_refs,
    revision_refs_by_key: refs_by_key,
    stop_keys,
    stop: stop_keys.length > 0,
    history: rows,
  };
}

export function signature_freeze_step(prev_sigs: any, cur_sigs: any, seen: any = [], accumulated: any = []): [boolean, Set<string>, Set<string>] {
  const prev = new Set<string>(prev_sigs ?? []);
  const cur = new Set<string>(cur_sigs ?? []);
  const seen_set = new Set<string>(seen ?? []);
  const acc = new Set<string>(accumulated ?? []);
  const new_seen = new Set<string>([...seen_set, ...prev]);
  const recurring = new Set<string>([...cur].filter((x) => new_seen.has(x)));
  const new_seen2 = new Set<string>([...new_seen, ...cur]);
  const new_acc = new Set<string>([...acc, ...recurring]);
  if (cur.size === 0) return [false, new_seen2, new_acc];
  if (cur.size < prev.size) return [false, new_seen2, new_acc];
  return [[...cur].every((x) => new_acc.has(x)), new_seen2, new_acc];
}

export function frozen_signatures_and_status(fail_sig_sequence: any): [boolean, Set<string>] {
  const seq = (fail_sig_sequence ?? []).map((s: any) => new Set(s ?? []));
  if (seq.length === 0) return [false, new Set()];
  let seen = new Set(seq[0]);
  let acc = new Set<string>();
  let is_frozen = false;
  for (let i = 1; i < seq.length; i++) {
    [is_frozen, seen, acc] = signature_freeze_step(seq[i - 1], seq[i], seen, acc);
  }
  return [is_frozen, acc];
}

export function frozen(facts: Record<string, any>[], aid: string, current_artifact: string | null = null): boolean {
  let vs = _facts_of(facts, aid, "verdict");
  if (current_artifact !== null) {
    vs = vs.filter((v) => String(v.artifact ?? "") === current_artifact);
  }
  vs = vs.filter((v) => ["pass", "fail"].includes(v.result));
  const fail_run: Record<string, any>[] = [];
  for (let i = vs.length - 1; i >= 0; i--) {
    if (vs[i].result !== "fail") break;
    fail_run.unshift(vs[i]);
  }
  if (fail_run.length < 2) return false;
  const seq = fail_run.map((v) => _norm_sigs(v.signatures));
  const [is_frozen] = frozen_signatures_and_status(seq);
  return is_frozen;
}

export function transient_recur(facts: Record<string, any>[], aid: string): boolean {
  const fs = _facts_of(facts, aid);
  let last_transient_i = -1;
  for (let i = 0; i < fs.length; i++) {
    if (fs[i].ev === "attribution" && fs[i].layer === "transient") last_transient_i = i;
  }
  if (last_transient_i < 0) return false;
  return fs.slice(last_transient_i + 1).some((f) => f.ev === "verdict" && f.result === "fail");
}

export function contradictions(facts: Record<string, any>[], aid: string, artifact: string | null = null): number {
  let n = 0;
  const passed_artifacts = new Set<string>();
  for (const f of _facts_of(facts, aid, "verdict")) {
    const art = String(f.artifact ?? "");
    if (artifact !== null && art !== artifact) continue;
    if (f.result === "pass") {
      passed_artifacts.add(art);
    } else if (f.ctx === CTX_DELIVERY && f.result === "fail" && passed_artifacts.has(art)) {
      n += 1;
    }
  }
  return n;
}

export function recovered(facts: Record<string, any>[], aid: string, artifact: string | null = null): number {
  let n = 0;
  const failed_artifacts = new Set<string>();
  for (const f of _facts_of(facts, aid, "verdict")) {
    const art = String(f.artifact ?? "");
    if (artifact !== null && art !== artifact) continue;
    if (f.result === "fail") {
      failed_artifacts.add(art);
    } else if (f.result === "pass" && failed_artifacts.has(art)) {
      n += 1;
    }
  }
  return n;
}

export function rounds_used(facts: Record<string, any>[], aid: string): number {
  return _facts_of(facts, aid, "authored").length;
}

export function dispatch_rounds_used(facts: Record<string, any>[], aid: string): number {
  const base = Math.max(
    0,
    ..._facts_of(facts, aid, "prior_dispatch_sequence")
      .filter((row) => typeof row.last_ordinal === "number" && row.last_ordinal >= 0)
      .map((row) => row.last_ordinal)
  );
  return base + _facts_of(facts, aid, "worker_dispatch_started").length;
}

export function next_authoring_attempt(facts: Record<string, any>[], aid: string, opts: { dispatch_reserved?: boolean } = {}): number {
  const { uses_new_policy, effective_budget_used } = require("./authoring_evidence");
  if (uses_new_policy(facts)) {
    return effective_budget_used(facts, aid, { raw_count: 0 }) + 1;
  }
  return Math.max(rounds_used(facts, aid) + 1, dispatch_rounds_used(facts, aid) + (opts.dispatch_reserved ? 0 : 1));
}

export const EMIT_REJECT_PRODUCER = "producer";
export const EMIT_REJECT_LEDGER = "ledger";

export function pending_emit_aids(facts: Record<string, any>[]): Set<string> {
  const pending = new Set<string>();
  for (const fact of this_run_slice(facts)) {
    const aid = String(fact.aid ?? "");
    if (!aid) continue;
    const event = fact.ev;
    if (event === "composed") {
      pending.add(aid);
    } else if (["authored", "emit_invalid"].includes(event)) {
      pending.delete(aid);
    }
  }
  return pending;
}

export function emit_todo_aids(facts: Record<string, any>[]): Set<string> {
  return pending_emit_aids(facts);
}

export const AUTHORING_CAUSE_SUBMISSION_REJECTED = "submission_rejected";
export const AUTHORING_CAUSE_NO_OUTPUT = "no_output";
export const AUTHORING_CAUSE_DEVICE_RESULT_CASE_SIDE = "device_result_case_side";
export const AUTHORING_CAUSE_COMPILE_POLICY_EXHAUSTED = "compile_policy_exhausted";
export const AUTHORING_CAUSE_WORKER_CLAIM = "worker_claim_not_compilable";
export const AUTHORING_CAUSE_API_SIDE = "api_side";
export const AUTHORING_CAUSE_BUDGET_GOVERNANCE = "budget_governance";
export const AUTHORING_CAUSE_ENGINE_SIDE = "engine_side";
export const AUTHORING_CAUSE_ENV = "environment";
export const AUTHORING_CAUSE_PRODUCT = "product";
const _AUTHORING_API_SIDE_FORK_FAULTS = new Set(Object.keys(EE.API_CAUSE_CODES));
export const AUTHORING_CASE_SIDE_CAUSES = new Set([
  AUTHORING_CAUSE_SUBMISSION_REJECTED,
  AUTHORING_CAUSE_NO_OUTPUT,
  AUTHORING_CAUSE_DEVICE_RESULT_CASE_SIDE,
  AUTHORING_CAUSE_COMPILE_POLICY_EXHAUSTED,
  AUTHORING_CAUSE_WORKER_CLAIM,
]);
const _AUTHORING_CASE_SIDE_LAYERS = new Set(["G", "E", "V", "dispatch"]);
const _AUTHORING_CASE_SIDE_DISPOSITIONS = new Set(["reflow", "frozen"]);
const _AUTHORING_PRESCRIPTION_DISPOSITIONS = new Set(["rerun_isolated"]);

export function authoring_round_causes(facts: Record<string, any>[], aid: string): Record<string, any>[] {
  const { aborted_dispatch } = require("./authoring_stops");
  const { _fact_sha256 } = require("./terminal_credentials");
  const out: Record<string, any>[] = [];

  function _add(fact: Record<string, any>, cause: string): void {
    out.push({
      round: fact.round,
      cause,
      case_side: AUTHORING_CASE_SIDE_CAUSES.has(cause),
      source_event: String(fact.ev ?? ""),
      source_fact_sha256: _fact_sha256(fact),
    });
  }

  for (const fact of _facts_of(facts, aid)) {
    const event = String(fact.ev ?? "");
    if (event === "compose_rejected") {
      _add(fact, AUTHORING_CAUSE_SUBMISSION_REJECTED);
    } else if (event === "worker_claim") {
      _add(fact, AUTHORING_CAUSE_WORKER_CLAIM);
    } else if (event === "escalated") {
      if (aborted_dispatch(fact)) continue;
      const subclass = String(fact.subclass ?? "");
      const fork_fault = String(fact.fork_fault ?? "");
      if (_AUTHORING_API_SIDE_FORK_FAULTS.has(fork_fault) || fact.api_error) {
        _add(fact, AUTHORING_CAUSE_API_SIDE);
      } else if (fork_fault === "FUTILITY_BLOCKED" || String(fact.engine_budget_exhausted ?? "")) {
        _add(fact, AUTHORING_CAUSE_BUDGET_GOVERNANCE);
      } else {
        _add(fact, subclass === ESC_NO_OUTPUT ? AUTHORING_CAUSE_NO_OUTPUT : AUTHORING_CAUSE_ENGINE_SIDE);
      }
    } else if (event === "attribution") {
      const layer = String(fact.layer ?? "");
      const disposition = String(fact.disposition ?? "");
      if (layer === "user") continue;
      if (layer === "product_defect") {
        _add(fact, AUTHORING_CAUSE_PRODUCT);
      } else if (layer === "transient" || disposition === "env_blocked") {
        _add(fact, AUTHORING_CAUSE_ENV);
      } else if (_AUTHORING_PRESCRIPTION_DISPOSITIONS.has(disposition)) {
        continue;
      } else if (_AUTHORING_CASE_SIDE_LAYERS.has(layer) && _AUTHORING_CASE_SIDE_DISPOSITIONS.has(disposition)) {
        _add(fact, AUTHORING_CAUSE_DEVICE_RESULT_CASE_SIDE);
      } else {
        _add(fact, AUTHORING_CAUSE_ENGINE_SIDE);
      }
    } else if (event === "worker_loop_outcome") {
      const outcome = String(fact.outcome ?? "");
      if (outcome === "compile_exhausted") {
        _add(fact, AUTHORING_CAUSE_COMPILE_POLICY_EXHAUSTED);
      } else if (["broken", "engine_defect"].includes(outcome)) {
        _add(fact, AUTHORING_CAUSE_ENGINE_SIDE);
      }
    }
  }
  return out;
}

export function authoring_failure_eligible(facts: Record<string, any>[], aid: string): boolean {
  const causes = authoring_round_causes(facts, aid);
  return causes.length > 0 && causes.every((row) => Boolean(row.case_side));
}

export function effective_rounds_used(facts: Record<string, any>[], aid: string): number {
  const { effective_budget_used } = require("./authoring_evidence");
  return effective_budget_used(facts, aid, Math.max(rounds_used(facts, aid), dispatch_rounds_used(facts, aid)));
}

export const ESC_NO_OUTPUT = "no_output";
export const ESC_NOT_EXECUTED = "not_executed";
export const ESC_NO_LEDGER_CHANNEL = "no_ledger_channel";
export const ESC_HARNESS_FAULT = "harness_fault";
export const ESC_WORKER_ENVELOPE = "worker_envelope_invalid";
export const ESC_VERDICT_UNRECOGNIZED = "verdict_unrecognized";
export const ESCALATION_FAMILY_UNDERDETERMINED_CLAIM = "underdetermined_claim";
export const ESCALATION_FAMILY_BINDING_UNAVAILABLE = "binding_unavailable";
export const ESCALATION_FAMILY_WORKER_PROTOCOL_DRIFT = "worker_protocol_drift";
export const ESCALATION_FAMILIES = new Set([
  ESCALATION_FAMILY_UNDERDETERMINED_CLAIM,
  ESCALATION_FAMILY_BINDING_UNAVAILABLE,
  ESCALATION_FAMILY_WORKER_PROTOCOL_DRIFT,
]);
const _ESC_LEGACY_PREFIX: [string, string][] = [
  ["no output from fork", ESC_NO_OUTPUT],
  ["case did not execute for", ESC_NOT_EXECUTED],
  ["worker declared underdetermined", ESC_NO_LEDGER_CHANNEL],
];

function _fact_subclass(f: Record<string, any>): string {
  const sub = String(f.subclass ?? "").trim();
  if (sub) return sub;
  const reason = String(f.reason ?? "");
  for (const [prefix, kind] of _ESC_LEGACY_PREFIX) {
    if (reason.includes(prefix)) return kind;
  }
  return "";
}

function _fact_esc_family(f: Record<string, any>): string {
  const family = String(f.esc_family ?? "").trim();
  if (ESCALATION_FAMILIES.has(family)) return family;
  if (!family && _fact_subclass(f) === ESC_NO_LEDGER_CHANNEL) return ESCALATION_FAMILY_UNDERDETERMINED_CLAIM;
  return "";
}

export function escalated_family(facts: Record<string, any>[], aid: string): string {
  const esc = _facts_of(facts, aid, "escalated");
  return esc.length ? _fact_esc_family(esc[esc.length - 1]) : "";
}

const _WORKER_SAID_MARKER = "worker said: ";

export function underdetermined_declaration(fact: Record<string, any>): string {
  const declared = String(fact.worker_declaration ?? "").trim();
  if (declared) return declared;
  const reason = String(fact.reason ?? "");
  const marker = reason.indexOf(_WORKER_SAID_MARKER);
  if (marker < 0) return "";
  return reason.slice(marker + _WORKER_SAID_MARKER.length).trim();
}

export function surviving_underdetermined_declaration(facts: Record<string, any>[], aid: string): Record<string, any> {
  const mine = facts.filter((f) => String(f.aid ?? "") === aid);
  let last_esc = -1;
  let last_authored = -1;
  for (let index = 0; index < mine.length; index++) {
    if (mine[index].ev === "escalated") last_esc = index;
    else if (mine[index].ev === "authored") last_authored = index;
  }
  if (last_esc < 0 || last_authored > last_esc) return {};
  const fact = mine[last_esc];
  if (_fact_esc_family(fact) !== ESCALATION_FAMILY_UNDERDETERMINED_CLAIM) return {};
  if (!underdetermined_declaration(fact)) return {};
  return fact;
}

export function author_definition_gap_landing_facts(facts: Record<string, any>[], aid: string, declaration_fact: Record<string, any>): Record<string, any>[] {
  const TC = require("./terminal_credentials");
  const declaration = underdetermined_declaration(declaration_fact);
  if (!declaration) return [];
  const abandon = TC.build_author_definition_gap_abandon_fact({
    aid,
    declaration,
    declaration_basis: "surviving_claim",
    source_fact: declaration_fact,
  });
  const out: Record<string, any>[] = [];
  const mine = facts.filter((f) => String(f.aid ?? "") === aid);
  let released = false;
  let seen_declaration = false;
  for (const fact of mine) {
    if (fact === declaration_fact || (fact.ev === "escalated" && fact.run_id && fact.run_id === declaration_fact.run_id)) {
      seen_declaration = true;
      released = false;
      continue;
    }
    if (seen_declaration && ["authored", "de_escalated"].includes(fact.ev)) {
      released = true;
    }
  }
  if (!released) {
    out.push({
      ev: "de_escalated",
      aid,
      note: "auto: underdetermined claim survived the engine's recovery attempt — landing it as the disclosed author-definition-gap disposition (2026-08-21 ruling; the verbatim gap list goes into the delivery report)",
    });
  }
  out.push(abandon);
  return out;
}

export function engine_budget_terminal_facts(facts: Record<string, any>[], aid: string, new_escalated: Record<string, any>, budget_kind: string): Record<string, any>[] {
  const TC = require("./terminal_credentials");
  const mine = facts.filter((f) => String(f.aid ?? "") === aid);
  return [
    {
      ev: "ist_core_defect",
      aid,
      round: effective_rounds_used(mine, aid),
      reason_code: `engine_budget_exhausted_${budget_kind}`,
      terminal_layer: "engine",
      source_event: "escalated",
      source_fact_sha256: TC._fact_sha256(TC.canonical_persisted_value({ ...new_escalated })),
      reentrant: true,
      terminal: false,
    },
  ];
}

export function structural_interference_attribution(fact: Record<string, any>): boolean {
  return fact.ev === "attribution" && fact.provenance === "engine_auto:g6_prescreen";
}

export function current_attribution(facts: Record<string, any>[], aid: string = ""): Record<string, any> {
  const mine = facts.filter((fact) => !aid || String(fact.aid ?? "") === aid);
  const verdict = mine.slice().reverse().find((fact) => fact.ev === "verdict");
  if (verdict !== undefined && !verdict.run_id) return {};
  const attributions = mine.filter(
    (fact) =>
      fact.ev === "attribution" &&
      !structural_interference_attribution(fact) &&
      fact.provenance !== "engine_auto:execution_pause_reentry" &&
      (verdict === undefined || fact.run_id === verdict.run_id)
  );
  return attributions.length ? attributions[attributions.length - 1] : {};
}

export function current_execution_prescription(facts: Record<string, any>[], aid: string): Record<string, any> {
  const { _fact_sha256 } = require("./terminal_credentials");
  const mine = facts.filter((fact) => String(fact.aid ?? "") === aid);
  const pause_index = mine.reduce((max, fact, index) => (fact.ev === "suspended" ? index : max), -1);
  const resume_index = mine.reduce((max, fact, index) => (fact.ev === "resumed" ? index : max), -1);
  const consumed = mine.reduce((max, fact, index) => (["verdict", "authored", "composed"].includes(fact.ev) ? index : max), -1);
  if (pause_index >= 0 && resume_index > Math.max(pause_index, consumed)) {
    const pause = mine[pause_index];
    const resumed = mine[resume_index];
    const source_sha = _fact_sha256(pause);
    const question_id = pause.question_id;
    if (pause.suspension_kind === "execution_pause" && typeof question_id === "string" && question_id && resumed.of === question_id) {
      const later = mine.slice(resume_index + 1);
      const bound = later.some((fact) => fact.ev === "suspension_reentered" && fact.source_suspended_sha256 === source_sha);
      const requests = later.filter(
        (fact) =>
          fact.ev === "attribution" &&
          fact.source === "engine_auto" &&
          fact.mechanical === true &&
          fact.provenance === "engine_auto:execution_pause_reentry" &&
          fact.run_id === `execution-reentry:${source_sha}` &&
          fact.source_event === "suspended" &&
          fact.source_fact_sha256 === source_sha &&
          fact.disposition === "rerun_isolated" &&
          fact.is_terminal === false
      );
      if (bound && requests.length) return requests[requests.length - 1];
    }
  }
  return current_attribution(mine, aid);
}

export function execution_retry_requested(facts: Record<string, any>[], aid: string): boolean {
  return ["rerun_isolated", "transient"].includes(current_execution_prescription(facts, aid).disposition);
}

export function retired_execution_attribution_kind(att: Record<string, any>): string {
  const aid = String(att.aid ?? "");
  if (!aid || att.source !== "engine_auto" || att.mechanical !== true) return "";
  for (const [kind, layer, disposition] of [
    ["env", "E", "env_blocked"],
    ["bed", "E", "env_blocked"],
    ["contra", "V", "defect_candidate"],
  ] as const) {
    if (att.run_id === `retired_ask:${kind}:${aid}` && att.provenance === `engine_auto:retired_ask:${kind}` && att.layer === layer && att.disposition === disposition) {
      return kind;
    }
  }
  return "";
}

export function attribution_is_terminal(att: Record<string, any>): boolean {
  if (structural_interference_attribution(att) || retired_execution_attribution_kind(att)) return false;
  if ("is_terminal" in att) return Boolean(att.is_terminal);
  return Number(att.round ?? 0) === 99;
}

export function scenario5_device_defect(layer: string, disposition: string): boolean {
  return String(layer ?? "") === "product_defect" && String(disposition ?? "") === "defect_candidate";
}

export function scenario5_terminal_needs_run_evidence(attribution: Record<string, any>): boolean {
  return attribution_source(attribution) !== "user";
}

export function scenario5_device_run_evidence(mine: Record<string, any>[], opts: { aid: string; run_id: string }): boolean {
  if (!opts.aid || typeof opts.run_id !== "string" || !opts.run_id.trim()) return false;
  const latest = mine
    .slice()
    .reverse()
    .find((fact) => fact.ev === "verdict" && String(fact.aid ?? "") === opts.aid && fact.run_id === opts.run_id) ?? {};
  return ["pass", "fail"].includes(latest.result);
}

export function scenario5_attribution_has_evidence(attribution: Record<string, any>, mine: Record<string, any>[]): boolean {
  if (!scenario5_device_defect(attribution.layer, attribution.disposition)) return false;
  if (!scenario5_terminal_needs_run_evidence(attribution)) return true;
  return scenario5_device_run_evidence(mine, { aid: String(attribution.aid ?? ""), run_id: attribution.run_id });
}

export function attribution_source(att: Record<string, any>): string {
  if ("source" in att) return String(att.source ?? "");
  if (String(att.evidence ?? "") === "user") return "user";
  if (String(att.layer ?? "") === "engine" || String(att.provenance ?? "").startsWith("engine_auto")) return "engine_auto";
  return "";
}

export function escalated_subclass(facts: Record<string, any>[], aid: string): string {
  const esc = _facts_of(facts, aid, "escalated");
  return esc.length ? _fact_subclass(esc[esc.length - 1]) : "";
}

export function de_escalated_after_last_escalation(facts: Record<string, any>[], aid: string): Record<string, any> | null {
  const mine = facts.filter((f) => String(f.aid ?? "") === aid);
  const last_esc = mine.reduce((max, f, i) => (f.ev === "escalated" ? i : max), -1);
  if (last_esc < 0) return null;
  for (const f of mine.slice(last_esc + 1)) {
    if (f.ev === "de_escalated") return f;
  }
  return null;
}

export function recovery_attempts(facts: Record<string, any>[], aid: string): number {
  return _facts_of(facts, aid, "de_escalated").length;
}

export function deesc_cap_threshold(max_rounds: number = 3, granted: number = 0): number {
  return Math.max(1, Math.floor(max_rounds || 3) + Math.floor(granted || 0));
}

export function escalation_attempts(facts: Record<string, any>[], aid: string, subclass: string, opts: { fork_fault?: string | null } = {}): number {
  const rows = _facts_of(facts, aid, "escalated").filter((f) => _fact_subclass(f) === subclass);
  if (opts.fork_fault === null || opts.fork_fault === undefined) return rows.length;
  const want = String(opts.fork_fault ?? "").trim();
  return rows.filter((f) => String(f.fork_fault ?? "").trim() === want).length;
}

export function fold_wave_common_cause(deaths: Record<string, any>[], opts: { total: number }): Record<string, any> | null {
  if (opts.total <= 0) return null;
  const groups: Record<string, Record<string, any>[]> = {};
  for (const row of deaths) {
    if (typeof row !== "object" || row === null) continue;
    const cause = String(row.cause_code ?? "").trim();
    if (!cause) continue;
    const api_error = typeof row.api_error === "object" && row.api_error !== null ? row.api_error : null;
    const code = String((api_error ?? {}).code ?? "");
    const key = `${cause}:${code}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push({ aid: String(row.aid ?? ""), api_error });
  }
  if (Object.keys(groups).length === 0) return null;
  const [key, members] = Object.entries(groups).sort((a, b) => b[1].length - a[1].length)[0];
  const count = members.length;
  if (count * 2 <= opts.total) return null;
  return {
    cause_code: key.split(":")[0],
    api_error: members.find((m) => m.api_error)?.api_error ?? null,
    count,
    total: opts.total,
    aids: [...new Set(members.map((m) => m.aid).filter(Boolean))].sort(),
  };
}

const _API_FIRST_OCCURRENCE_FAULTS: Record<string, [string, string]> = {
  API_REQUEST_REJECTED: [
    "the API endpoint rejected the request (non-transient 400/422)",
    "switch the model or the API endpoint, then recompile",
  ],
  API_AUTH_REJECTED: [
    "the API endpoint rejected the credentials or permissions (401/403)",
    "top up the account, correct the key, or wait for the usage window to reset, then recompile; the whole batch stops here because the same credentials gate every remaining case",
  ],
};

export function deesc_auto_resolution(
  facts: Record<string, any>[],
  aid: string,
  new_escalated: Record<string, any>,
  opts: { max_rounds?: number; granted?: number } = {}
): Record<string, any>[] {
  const AE = require("./authoring_evidence");
  if (AE.uses_new_policy([...facts, new_escalated])) {
    return AE.interruption_facts(facts, aid, new_escalated);
  }
  const sub = _fact_subclass(new_escalated);
  if (sub === ESC_NO_OUTPUT) {
    const { escalation_budget_kind } = require("./_shared");
    const _budget_kind = escalation_budget_kind(new_escalated);
    if (_budget_kind) {
      return engine_budget_terminal_facts(facts, aid, new_escalated, _budget_kind);
    }
  }
  if ([ESC_NO_OUTPUT, ESC_NOT_EXECUTED].includes(sub)) {
    const prior = escalation_attempts(facts, aid, sub);
    const cap = deesc_cap_threshold(2, opts.granted ?? 0);
    if (prior === 0) {
      return [
        {
          ev: "de_escalated",
          aid,
          note: `auto: first ${sub} occurrence — engine grants one bounded serial max-effort recovery`,
          recovery_policy: "serial_max_effort_once",
        },
        {
          ev: "ask_path_retired_disclosure",
          aid,
          retired_kind: "deesc",
          mechanical_route: "bounded_engine_recovery",
          disclosure: "本轮无产物/未执行由引擎自动恢复一次：该案在独立单槽中重试并提升 effort。",
        },
      ];
    }
    if (prior + 1 >= cap) {
      const _n = prior + 1;
      const _disposition = sub === ESC_NO_OUTPUT ? "engineering_fault" : "env_blocked";
      const _layer = sub === ESC_NO_OUTPUT ? "engine" : "E";
      const _terminal_rows: Record<string, any>[] = [
        { ev: "de_escalated", aid, note: `auto: round-cap reached (${_n}x ${sub}, threshold=${cap})` },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: _layer,
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_cap:${aid}:${sub}:${_n}`,
          provenance: "engine_auto:deesc_cap",
          disposition: _disposition,
          fix_direction: `escalation round-cap reached (${_n}x ${sub}, threshold=${cap}) — engine exhausted its recovery attempts for this case without producing new evidence`,
          evidence: "",
          user_note:
            sub === ESC_NO_OUTPUT
              ? `引擎已自动恢复一次但第 ${_n} 次仍无产物，已按引擎/框架工程故障收口。`
              : `自动恢复一次后第 ${_n} 次仍无法执行，已按环境/平台限制如实收口。`,
        },
        EE.engine_error_fact(aid, sub === ESC_NO_OUTPUT ? EE.E_WORKER_TIMEOUT : EE.E_ENVIRONMENT, `escalation round-cap reached (${_n}x ${sub}, threshold=${cap})`),
      ];
      _terminal_rows.push({
        ev: "ask_path_retired_disclosure",
        aid,
        retired_kind: "deesc",
        mechanical_route: _disposition,
        disclosure: sub === ESC_NO_OUTPUT ? "引擎自动恢复一次后仍无产物，已按引擎/框架工程故障收口。" : "引擎自动恢复一次后仍无法执行，已按环境/平台限制收口。",
      });
      if (sub === ESC_NOT_EXECUTED) {
        _terminal_rows.push({
          ev: "environment_execution_disclosure",
          aid,
          obstacle_class: "platform_limitation",
          environment_basis: [String(new_escalated.reason ?? "").slice(0, 300)],
          author_unreachable_values: [],
          disclosure: "自动恢复后仍无法执行，当前平台无法完成编写/上机。",
        });
      }
      return _terminal_rows;
    }
    return [];
  }
  if (sub === ESC_HARNESS_FAULT) {
    const prior = escalation_attempts(facts, aid, sub);
    const cap = deesc_cap_threshold(2, opts.granted ?? 0);
    if (prior === 0) {
      return [
        {
          ev: "de_escalated",
          aid,
          note: "auto: first harness fault — engine grants one bounded serial max-effort recovery",
          recovery_policy: "serial_max_effort_once",
        },
        {
          ev: "ask_path_retired_disclosure",
          aid,
          retired_kind: "deesc",
          mechanical_route: "bounded_engine_recovery",
          disclosure: "测试框架首次失败由引擎自动恢复一次：该案在独立单槽中重试并提升 effort。",
        },
      ];
    }
    if (prior + 1 >= cap) {
      const _n = prior + 1;
      return [
        { ev: "de_escalated", aid, note: `auto: harness fault recurred after recovery attempt (${_n}x ${sub}, threshold=${cap})` },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_harness:${aid}:${_n}`,
          provenance: "engine_auto:deesc_harness",
          disposition: "engineering_fault",
          fix_direction: `test harness crashed at collect/setup and recurred after ${_n}x recovery attempt(s) (threshold=${cap}) — this is an engine/framework-side gap (e.g. an unsafe dispatch/build-string construction defect), not a product defect; do not record it in the defect-candidate ledger`,
          evidence: "",
          user_note: `测试框架自身崩溃,恢复尝试后仍复现(第 ${_n} 次)——判定为工程故障(引擎/框架缺口),不是产品缺陷,已呈报。`,
        },
        EE.engine_error_fact(aid, EE.E_COLLECT_SETUP, `harness crashed at collect/setup and recurred after ${_n}x recovery attempt(s) (threshold=${cap})`),
      ];
    }
    return [];
  }
  if (sub === ESC_WORKER_ENVELOPE) {
    const prior = escalation_attempts(facts, aid, sub, { fork_fault: String(new_escalated.fork_fault ?? "").trim() });
    const cap = deesc_cap_threshold(2, opts.granted ?? 0);
    const _fault = String(new_escalated.fork_fault ?? "").trim();
    if (_fault === "LLM_QUOTA_EXHAUSTED") {
      const _n = prior + 1;
      const _what = "LLM endpoint account is out of quota/credit";
      return [
        { ev: "de_escalated", aid, note: `auto: ${_what} — signed on first occurrence; a retry cannot mint credit` },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_envelope:${aid}:${_n}`,
          provenance: "engine_auto:deesc_envelope",
          disposition: "engineering_fault",
          fix_direction: `${_what} — top up the account or switch endpoints; retrying cannot change an empty account (signed on first occurrence, no recovery attempt spent), not a product defect`,
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
        },
        EE.engine_error_fact(aid, EE.E_LLM_QUOTA_EXHAUSTED, `${_what} (signed on first occurrence)`),
      ];
    }
    if (_fault in _API_FIRST_OCCURRENCE_FAULTS) {
      const _n = prior + 1;
      const [_what, _goto] = _API_FIRST_OCCURRENCE_FAULTS[_fault];
      return [
        { ev: "de_escalated", aid, note: `auto: ${_what} — signed on first occurrence; resending the same request cannot change the verdict` },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_envelope:${aid}:${_n}`,
          provenance: "engine_auto:deesc_envelope",
          disposition: "engineering_fault",
          fix_direction: `${_what} — ${_goto}; resending the same request gets the same rejection (signed on first occurrence, no recovery attempt spent), an API-side condition, not a product defect and not an engine fault`,
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
        },
        EE.engine_error_fact(aid, EE.API_CAUSE_CODES[_fault], `${_what} (signed on first occurrence)`),
      ];
    }
    if (_fault === "TRANSIENT_ERROR" && new_escalated.wave_common_cause) {
      const _n = prior + 1;
      const _what = "LLM endpoint transient pressure exhausted the engine's retries";
      return [
        {
          ev: "de_escalated",
          aid,
          note: `auto: ${_what} — over half of this dispatch wave died on the same endpoint condition; the engine stops here instead of spending a recovery attempt on the same window`,
        },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_envelope:${aid}:${_n}`,
          provenance: "engine_auto:deesc_envelope",
          disposition: "engineering_fault",
          fix_direction: `${_what} — rerun later with the same parameters, or raise the endpoint-side quota; over half of this wave died the same way, so no second wave was dispatched — an endpoint-side condition, not a product defect`,
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
        },
        EE.engine_error_fact(aid, EE.E_LLM_TRANSIENT_EXHAUSTED, `${_what} (wave common cause, no second wave)`),
      ];
    }
    if (prior + 1 >= cap) {
      const _n = prior + 1;
      let _code: string;
      let _what: string;
      let _gap: string;
      if (_fault === "TRANSIENT_ERROR") {
        _code = EE.E_LLM_TRANSIENT_EXHAUSTED;
        _what = "LLM endpoint transient pressure exhausted the engine's retries";
        _gap =
          "the endpoint kept rate-limiting/overloading through the call-level backoff retries; rerun later, or raise the endpoint-side quota — this repo no longer ships concurrency or rate knobs — an endpoint-side condition, not an engine fault";
      } else if (_fault) {
        _code = EE.E_FORK_CHANNEL_FAULT;
        _what = `engine fork/governance channel aborted the worker (${_fault})`;
        _gap = "this is an engine-side fork channel gap (the worker process was aborted before its first round; repair the durable run registry / governance layer)";
      } else {
        _code = EE.E_WORKER_RESULT_ENVELOPE;
        _what = "worker result envelope failed protocol validation";
        _gap = "this is an engine-side fork channel gap (truncated tool call / missing structured response; repair the fork return-envelope channel)";
      }
      return [
        { ev: "de_escalated", aid, note: `auto: ${_what} again after a recovery attempt (${_n}x ${sub}, threshold=${cap})` },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_envelope:${aid}:${_n}`,
          provenance: "engine_auto:deesc_envelope",
          disposition: "engineering_fault",
          fix_direction: `${_what} and it recurred after ${_n}x recovery attempt(s) (threshold=${cap}) — ${_gap}, not a product defect`,
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
        },
        EE.engine_error_fact(aid, _code, `${_what} ${_n}x (threshold=${cap})`),
      ];
    }
    return [{ ev: "de_escalated", aid, note: "auto: first occurrence — engine spends its own recovery attempt" }];
  }
  if (sub === ESC_NO_LEDGER_CHANNEL) {
    const { COMMAND_HEADS_RECEIPT_REDACTION_FOLDED } = require("../worker_device_context");
    if (String(new_escalated.diagnostic_code ?? "") === COMMAND_HEADS_RECEIPT_REDACTION_FOLDED) {
      return [
        {
          ev: "de_escalated",
          aid,
          note: "auto: command inventory receipt was broken by the engine's own redaction — a retry cannot change it",
        },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_redact:${aid}:${_facts_of(facts, aid, "escalated").length + 1}`,
          provenance: "engine_auto:deesc_redact",
          disposition: "engineering_fault",
          fix_direction:
            "the command-heads receipt was validated against a redacted copy; redaction folded distinct command heads into one literal, so a valid receipt was rejected — engine-side gap in where the redaction boundary sits, not a product defect",
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
        },
        EE.engine_error_fact(aid, EE.E_INVENTORY_RECEIPT_REDACTED, "command inventory receipt validated against a redacted copy; redaction folded distinct heads into duplicates"),
      ];
    }
    const family = _fact_esc_family(new_escalated);
    if (family === ESCALATION_FAMILY_UNDERDETERMINED_CLAIM) {
      const landing = author_definition_gap_landing_facts(facts, aid, new_escalated);
      if (landing.length) {
        return [
          ...landing,
          {
            ev: "ask_path_retired_disclosure",
            aid,
            retired_kind: "non_batch_gather",
            mechanical_route: "author_definition_gap",
            disclosure: "作者定义缺口已直接披露收尾。",
          },
        ];
      }
    }
    const prior_esc = _facts_of(facts, aid, "escalated").filter((f) => _fact_subclass(f) === sub && _fact_esc_family(f) === family);
    if (prior_esc.length === 0) {
      return [{ ev: "de_escalated", aid, note: `auto: first ${family || "unclassified"} occurrence — engine spends its own recovery attempt` }];
    }
    if (family === ESCALATION_FAMILY_UNDERDETERMINED_CLAIM) {
      const landing = author_definition_gap_landing_facts(facts, aid, new_escalated);
      if (landing.length) return landing;
      const _n = prior_esc.length + 1;
      return [
        {
          ev: "de_escalated",
          aid,
          note: "auto: underdetermined claim recurred without a quotable declaration — the structured landing exists but was not used",
        },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_eng:${aid}:${family}:${_n}`,
          provenance: "engine_auto:deesc_eng",
          disposition: "engineering_fault",
          fix_direction:
            "an underdetermined claim recurred for the same case after one recovery attempt, but carried no quotable declaration and the structured author-definition-gap terminal was never signed — a worker protocol/guidance gap (the landing channel exists since the 2026-08-21 ruling), not a product defect and not a missing ledger channel",
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
          user_note: "编写侧连续两轮声明「通过标准欠定」但未留下可引用的缺口清单，也未走结构化欠定终点；已按工程故障终止该案，待引擎侧修正编写引导。",
        },
      ];
    }
    if ([ESCALATION_FAMILY_BINDING_UNAVAILABLE, ESCALATION_FAMILY_WORKER_PROTOCOL_DRIFT].includes(family)) {
      let failure: string;
      let provenance: string;
      let user_note: string;
      if (family === ESCALATION_FAMILY_BINDING_UNAVAILABLE) {
        failure = "required engine-owned intent/consistency binding remained unavailable";
        provenance = "engine_auto:deesc_binding";
        user_note = "引擎自有的意图/一致性绑定恢复后仍不可用，已按工程故障终止该案。";
      } else {
        failure = "worker terminal/protocol outcome again lacked its engine-owned receipt";
        provenance = "engine_auto:deesc_worker_protocol";
        user_note = "worker 终态/协议结果恢复后仍与引擎回执不一致，已按工程故障终止该案。";
      }
      return [
        { ev: "de_escalated", aid, note: `auto: ${family} recurred for the same case after a recovery attempt` },
        {
          ev: "attribution",
          aid,
          round: rounds_used(facts, aid),
          layer: "engine",
          is_terminal: true,
          source: "engine_auto",
          run_id: `auto_eng:${aid}:${family}:${prior_esc.length + 1}`,
          provenance,
          disposition: "engineering_fault",
          fix_direction: `${failure} after one recovery attempt; this is an engine-side ${family.replace(/_/g, " ")} failure, not an underdetermined claim or product defect`,
          evidence: String(new_escalated.reason ?? "").slice(0, 300),
          user_note,
        },
      ];
    }
    return [];
  }
  return [];
}

export function serial_recovery_pending(facts: Record<string, any>[], aids: string[]): boolean {
  const wanted = new Set(aids.filter((aid) => String(aid)));
  for (const aid of wanted) {
    const mine = facts.filter((fact) => String(fact.aid ?? "") === aid);
    const latest = mine.slice().reverse().find((fact) => ["de_escalated", "authored", "composed"].includes(fact.ev));
    if (latest && latest.ev === "de_escalated" && latest.recovery_policy === "serial_max_effort_once") return true;
  }
  return false;
}

export const STRONG_DISPOSITIONS = ["defect_candidate", "expectation_suspect"];

export function strong_claims(facts: Record<string, any>[], aid: string): Record<string, any>[] {
  const out: Record<string, any>[] = [];
  const seen = new Set<string>();
  for (const f of _facts_of(facts, aid, "attribution")) {
    if (!STRONG_DISPOSITIONS.includes(String(f.disposition))) continue;
    const ev = String(f.evidence ?? "");
    if (!ev || ["user", "engine_auto"].includes(attribution_source(f))) continue;
    const claim = String(f.fix_direction ?? "").slice(0, ATTRIBUTION_TEXT_MAX_CHARS);
    const k = `${String(f.disposition)}:${claim}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push({
      round: Number(f.round ?? 0),
      layer: String(f.layer ?? ""),
      disposition: String(f.disposition),
      claim,
      evidence: ev.slice(0, ATTRIBUTION_TEXT_MAX_CHARS),
      user_note: String(f.user_note ?? "").slice(0, ATTRIBUTION_TEXT_MAX_CHARS),
      is_terminal: attribution_is_terminal(f),
    });
  }
  return out;
}

export function reconcile(facts: Record<string, any>[], verdicts: Record<string, any>[]): Record<string, any> {
  const out: Record<string, any> = { append: [], transition: [], confirm: [], duplicate: [] };
  const known = new Set(facts.map(idem_key));
  for (const v of verdicts) {
    const f: Record<string, any> = { ...v, ev: "verdict" };
    const fr = f.framework_result;
    if (fr !== null && fr !== undefined && !FRAMEWORK_RESULT_DOMAIN.has(fr)) {
      throw new Error(
        `framework_result 值域断言失败: ${JSON.stringify(fr)} 不在 ${[...FRAMEWORK_RESULT_DOMAIN].sort()} 内(aid=${f.aid})——这可能意味着框架版本变更引入了新的裁决值,请先核 knowledge/framework/mirror/lib/check_point.py + lib/config.py 确认真实值域,再决定是否扩大这个闭集;不要放行未知值。`
      );
    }
    const r = f.result;
    if (!RESULT_DOMAIN.has(r)) {
      throw new Error(`result 值域断言失败: ${JSON.stringify(r)} 不在 ${[...RESULT_DOMAIN].sort()} 内(aid=${f.aid})——写入前请确认没有把 framework_result 误当 result 写入。`);
    }
    if (known.has(idem_key(f))) {
      out.duplicate.push(String(f.aid));
      continue;
    }
    const aid = String(f.aid);
    const prev = latest_verdict(facts, aid, String(f.ctx ?? "") || null, String(f.artifact));
    const same = Boolean(prev && prev.result === f.result);
    out.append.push(f);
    (same ? out.confirm : out.transition).push(aid);
    facts = [...facts, f];
    known.add(idem_key(f));
  }
  return out;
}

export enum FrameworkResultState {
  ABSENT = "absent",
  NOT_GIVEN = "not_given",
  STRIPPED = "stripped",
  GIVEN = "given",
}

export interface FrameworkResultRead {
  state: FrameworkResultState;
  value: string | null;
}

export function read_framework_result(event: Record<string, any>): FrameworkResultRead {
  if (!("framework_result" in event)) {
    return { state: FrameworkResultState.ABSENT, value: null };
  }
  const value = event.framework_result;
  if (value !== null && value !== undefined) {
    return { state: FrameworkResultState.GIVEN, value };
  }
  if (event.broken_subtype === "verdict_unrecognized") {
    return { state: FrameworkResultState.STRIPPED, value: null };
  }
  return { state: FrameworkResultState.NOT_GIVEN, value: null };
}

const _SUBSET_VOLUME_DIR_RE = /^workspace\/outputs\/[^/]+__sub\d+(\/|$)/;
const _INTERMEDIATE_FILENAMES = new Set(["manifest.json", "last_run.json"]);
const _PERMANENT_SUBDIRS = new Set(["delivered", "unfinished"]);

export function classify_reference_permanence(rel_path: string): string {
  const p = String(rel_path ?? "").trim().replace(/^\/+/, "");
  if (_SUBSET_VOLUME_DIR_RE.test(p)) return "intermediate";
  const parts = p.split("/");
  if (parts.length >= 4 && parts[0] === "workspace" && parts[1] === "outputs") {
    if (parts.length === 4 && _INTERMEDIATE_FILENAMES.has(parts[3])) return "intermediate";
    if (parts.length === 4 && parts[3] === "case.xlsx") return "permanent";
    if (parts.length >= 5 && _PERMANENT_SUBDIRS.has(parts[3])) return "permanent";
  }
  return "unknown";
}

const _PATH_TYPE_FIELDS: Record<string, string[]> = {
  merged: ["path"],
  verdict: ["evidence_ref"],
};
const _VALIDITY_EXEMPTION_WHITELIST: Record<string, Record<string, string>> = {};

export function find_lifecycle_mismatches(facts: Record<string, any>[]): Record<string, any>[] {
  const violations: Record<string, any>[] = [];
  for (const f of facts) {
    const ev = String(f.ev ?? "");
    const fields = _PATH_TYPE_FIELDS[ev];
    if (!fields) continue;
    for (const field of fields) {
      const val = f[field];
      if (!val) continue;
      const kind = classify_reference_permanence(String(val));
      if (kind === "permanent") continue;
      if (kind === "intermediate") {
        const exemption = _VALIDITY_EXEMPTION_WHITELIST[`${ev}:${field}`];
        if (exemption && f[exemption.declares_via]) continue;
      }
      violations.push({ ev, aid: f.aid, run_id: f.run_id, field, value: val, classification: kind });
    }
  }
  return violations;
}
