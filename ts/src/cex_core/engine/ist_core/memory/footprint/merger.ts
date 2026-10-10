import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../../../_root";
import { acquireLockSync, restrictFilePrivate } from "../../../../../platform/index";
import { LEVEL_KINDS, MergeResult, RoutedFact, TEMPLATE_MAP, makeMergeResult } from "./schema";
import { catalog_head_tokens_clean } from "./router";

const logger = {
  warning: (...args: any[]) => console.warn(...args),
  exception: (...args: any[]) => console.error(...args),
};

const _MAX_FOOTPRINT_JSON_BYTES = 16 * 1024 * 1024;
const _FOOTPRINT_LOCK_NAME = ".footprint.write.lock";

export class FootprintWriteError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "FootprintWriteError";
  }
}

function _strict_json_object(payload: Buffer): Record<string, any> {
  const { validate_json_budget } = require("../../../case_compiler/_sealed_io");
  validate_json_budget(payload, {
    errorType: FootprintWriteError,
    message: "footprint JSON exceeds the structural budget",
    max_depth: 128,
    max_tokens: 500000,
  });
  let value: any;
  try {
    const text = payload.toString("utf8");
    value = JSON.parse(text);
  } catch (exc) {
    throw new FootprintWriteError("footprint JSON is invalid");
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new FootprintWriteError("footprint JSON root must be an object");
  }
  return value;
}

function _withLockedFootprintRoot<T>(footprint_dir: string, fn: (root: string) => T): T {
  const { open_directory_nofollow } = require("../../../case_compiler/_sealed_io");
  const root = open_directory_nofollow(String(footprint_dir), {
    errorType: FootprintWriteError,
    invalid_message: "footprint root path is invalid",
    unavailable_message: "footprint root is unavailable or unsafe",
  });
  const lockPath = path.join(root, _FOOTPRINT_LOCK_NAME);
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });
  if (!fs.existsSync(lockPath)) {
    const fd = fs.openSync(lockPath, "wx", 0o600);
    fs.closeSync(fd);
  }
  restrictFilePrivate(lockPath);
  const lock = acquireLockSync(lockPath);
  try {
    return fn(root);
  } finally {
    lock.release();
  }
}

function _read_footprint_at(parent_dir: string, name: string): Record<string, any> | null {
  const payload = _read_footprint_payload_at(parent_dir, name);
  return payload === null ? null : _strict_json_object(payload);
}

function _read_footprint_payload_at(parent_dir: string, name: string): Buffer | null {
  const { read_regular_at_nofollow } = require("../../../case_compiler/_sealed_io");
  try {
    const payload = read_regular_at_nofollow(parent_dir, name, {
      errorType: FootprintWriteError,
      open_message: "footprint target is unavailable or unsafe",
      bounds_message: "footprint target is not a bounded single-link regular file",
      changed_message: "footprint target changed while being read",
      max_bytes: _MAX_FOOTPRINT_JSON_BYTES,
      min_bytes: 1,
      preserve_missing: true,
      require_current_uid: true,
    });
    return payload as Buffer;
  } catch (exc: any) {
    if (exc && exc.code === "ENOENT") {
      return null;
    }
    throw exc;
  }
}

function _write_footprint_at(parent_dir: string, name: string, data: Record<string, any>): void {
  const payload = Buffer.from(JSON.stringify(data, null, 2) + "\n", "utf8");
  _write_footprint_payload_at(parent_dir, name, payload);
}

function _write_footprint_payload_at(parent_dir: string, name: string, payload: Buffer): void {
  const { atomic_write_bytes_at_nofollow } = require("../../../case_compiler/_sealed_io");
  if (payload.length > _MAX_FOOTPRINT_JSON_BYTES) {
    throw new FootprintWriteError("footprint JSON exceeds the byte budget");
  }
  atomic_write_bytes_at_nofollow(parent_dir, name, payload, {
    errorType: FootprintWriteError,
    unavailable_message: "footprint target cannot be published safely",
    mode: 0o600,
  });
}

function _entry_device_autoid(item: Record<string, any>, opts: { node_name: string }): string {
  const evidence = item.evidence || {};
  if (evidence === null || typeof evidence !== "object" || Array.isArray(evidence)) {
    throw new FootprintWriteError(`footprint node ${opts.node_name} has an invalid evidence object`);
  }
  const device_run = evidence.device_run || {};
  if (device_run === null || typeof device_run !== "object" || Array.isArray(device_run)) {
    throw new FootprintWriteError(`footprint node ${opts.node_name} has an invalid device_run object`);
  }
  return String(device_run.autoid || "");
}

export function _rollback_footprint_autoid(opts: { autoid: string; footprint_dir?: string | null }): string {
  const aid = String(opts.autoid || "").trim();
  if (!/^\d{18}$/.test(aid)) {
    return "error: footprint rollback autoid is invalid";
  }
  let footprint_dir = opts.footprint_dir ?? null;
  if (footprint_dir === null) {
    const { KNOWLEDGE_FOOTPRINTS } = require("../../../knowledge_paths");
    footprint_dir = String(KNOWLEDGE_FOOTPRINTS);
  }
  const { lexical_absolute } = require("../../../case_compiler/_sealed_io");
  const root = lexical_absolute(String(footprint_dir));
  const prepared: Array<[string, Buffer, Record<string, any>]> = [];
  const changed_names: string[] = [];
  try {
    _withLockedFootprintRoot(root, (rootDir) => {
      const nodesDir = _open_target_directory_at(rootDir, ["nodes"]);
      const names = fs.readdirSync(nodesDir).sort();
      for (const name of names) {
        if (!name.endsWith(".json") || name.startsWith(".") || path.basename(name) !== name) {
          continue;
        }
        const payload = _read_footprint_payload_at(nodesDir, name);
        if (payload === null) {
          throw new FootprintWriteError("footprint node disappeared during rollback precheck");
        }
        const data = _strict_json_object(payload);
        let changed = false;
        for (const field of ["behaviors", "decision_rules"]) {
          const entries = data[field] ?? [];
          if (!Array.isArray(entries) || entries.some((item) => item === null || typeof item !== "object" || Array.isArray(item))) {
            throw new FootprintWriteError(`footprint node ${name} has an invalid ${field} array`);
          }
          const kept = entries.filter((item) => _entry_device_autoid(item, { node_name: name }) !== aid);
          if (kept.length !== entries.length) {
            data[field] = kept;
            changed = true;
          }
        }
        const cli = data.cli ?? {};
        if (cli === null || typeof cli !== "object" || Array.isArray(cli)) {
          throw new FootprintWriteError(`footprint node ${name} has an invalid cli object`);
        }
        const commands = cli.commands ?? [];
        if (!Array.isArray(commands) || commands.some((item) => item === null || typeof item !== "object" || Array.isArray(item))) {
          throw new FootprintWriteError(`footprint node ${name} has an invalid cli.commands array`);
        }
        const kept_commands = commands.filter((item) => _entry_device_autoid(item, { node_name: name }) !== aid);
        if (kept_commands.length !== commands.length) {
          cli.commands = kept_commands;
          data.cli = cli;
          changed = true;
        }
        if (changed) {
          prepared.push([name, payload, data]);
        }
      }
      try {
        for (const [name, , data] of prepared) {
          _write_footprint_at(nodesDir, name, data);
          changed_names.push(name);
        }
      } catch (exc) {
        const restore_errors: any[] = [];
        const old_by_name: Record<string, Buffer> = {};
        for (const [name, old_payload] of prepared) {
          old_by_name[name] = old_payload;
        }
        for (const name of changed_names.slice().reverse()) {
          try {
            _write_footprint_payload_at(nodesDir, name, old_by_name[name]);
          } catch (restore_exc) {
            restore_errors.push(restore_exc);
          }
        }
        if (restore_errors.length > 0) {
          throw new FootprintWriteError("footprint rollback failed and restoration was incomplete");
        }
        throw exc;
      }
    });
  } catch (exc: any) {
    return `error: footprint rollback rejected (${exc?.constructor?.name ?? "Error"}: ${exc})`;
  }
  return `footprint rollback autoid=${aid}: nodes updated ${prepared.length}`;
}

function _open_target_directory_at(root_dir: string, relative_parts: string[]): string {
  let current = root_dir;
  for (const component of relative_parts) {
    if (!component || component === "." || component === ".." || path.basename(component) !== component) {
      throw new FootprintWriteError("footprint target directory is invalid");
    }
    current = path.join(current, component);
    if (!fs.existsSync(current)) {
      try {
        fs.mkdirSync(current, { mode: 0o755 });
      } catch (exc: any) {
        if (!exc || exc.code !== "EEXIST") {
          throw exc;
        }
      }
    }
    const st = fs.lstatSync(current);
    if (st.isSymbolicLink() || !st.isDirectory()) {
      throw new FootprintWriteError("footprint target directory is unavailable or unsafe");
    }
  }
  return current;
}

const _LINE_PREFIX_RE = /^\s*\d+:\s*/;
const _ELLIPSIS_RE = /\.{3,}/g;

function _project_root(): string {
  return String(_cex_data_path(""));
}

const _MARKDOWN_ROOT = ["knowledge", "data", "markdown"];
const _EVIDENCE_ROOTS = [_MARKDOWN_ROOT, ["knowledge", "data", "manual"]];

function _evidence_root_dirs(): string[] {
  const root = _project_root();
  const out: string[] = [];
  for (const parts of _EVIDENCE_ROOTS) {
    const candidate = path.resolve(path.join(root, ...parts));
    try {
      if (fs.statSync(candidate).isDirectory()) {
        out.push(candidate);
      }
    } catch {}
  }
  return out;
}

function _evidence_trusted_root(p: string): string | null {
  for (const base of _evidence_root_dirs()) {
    const rel = path.relative(base, p);
    if (rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel))) {
      return base;
    }
  }
  return null;
}

function _rglob(roots: string[], name: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const walk = (dir: string) => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        walk(full);
      } else if (e.isFile() && e.name === name) {
        if (!seen.has(full)) {
          seen.add(full);
          out.push(full);
        }
      }
    }
  };
  for (const base of roots) {
    walk(base);
  }
  return out;
}

function _resolve_evidence_path(evidence_file: string): string | null {
  if (!evidence_file) {
    return null;
  }
  const root = _project_root();
  const roots = _evidence_root_dirs();
  if (roots.length === 0) {
    return null;
  }
  const rawStr = String(evidence_file).trim();
  if (!rawStr || rawStr.split(/[\\/]+/).includes("..") || rawStr.startsWith("~") || rawStr.includes("")) {
    return null;
  }
  const rawParts = rawStr.split(/[\\/]+/).filter((c) => c.length > 0);
  const candidates: string[] = [];
  if (path.isAbsolute(rawStr)) {
    candidates.push(path.resolve(rawStr));
  } else if (_EVIDENCE_ROOTS.some((parts) => rawParts.slice(0, 3).join("/") === parts.join("/"))) {
    candidates.push(path.resolve(path.join(root, ...rawParts)));
  } else if (rawParts.length > 1) {
    for (const base of roots) {
      candidates.push(path.resolve(path.join(base, ...rawParts)));
    }
  }
  const { stat_regular_nofollow } = require("../../../case_compiler/_sealed_io");
  for (const direct of candidates) {
    if (_evidence_trusted_root(direct) === null) {
      continue;
    }
    try {
      stat_regular_nofollow(direct, {
        errorType: Error,
        invalid_message: "manual evidence path is invalid",
        directory_message: "manual evidence directory is unsafe",
        open_message: "manual evidence file is unavailable",
        bounds_message: "manual evidence file is not regular or too large",
        max_bytes: 32 * 1024 * 1024,
      });
      return direct;
    } catch {
      continue;
    }
  }
  if (candidates.length > 0) {
    return null;
  }
  const name = rawParts[rawParts.length - 1];
  const usable: string[] = [];
  for (const p of _rglob(roots, name)) {
    try {
      const candidate = path.resolve(p);
      if (_evidence_trusted_root(candidate) === null) {
        continue;
      }
      stat_regular_nofollow(candidate, {
        errorType: Error,
        invalid_message: "manual evidence path is invalid",
        directory_message: "manual evidence directory is unsafe",
        open_message: "manual evidence file is unavailable",
        bounds_message: "manual evidence file is not regular or too large",
        max_bytes: 32 * 1024 * 1024,
      });
      usable.push(candidate);
    } catch {
      continue;
    }
  }
  if (usable.length === 1) {
    return usable[0];
  }
  if (usable.length > 1) {
    logger.warning(
      `证据 basename '${name}' 在可信手册树里有 ${usable.length} 份同名候选，拒绝解析——请在 evidence_file 里带上版本段（如 manual/10.5.0/${name}）`
    );
  }
  return null;
}

const _BR_RE = /<br\s*\/?>/g;
const _CJK_RANGE = "　-〿㐀-䶿一-鿿豈-﫿";
const _CJK_SPACE_RE = new RegExp(`(?<=[${_CJK_RANGE}])\\s+|\\s+(?=[${_CJK_RANGE}])`, "g");

function _normalize(s: string): string {
  let out = s.replace(_LINE_PREFIX_RE, "");
  out = out.replace(_ELLIPSIS_RE, "");
  out = out.replace(_BR_RE, "");
  out = out.replace(/\*\*/g, "").replace(/　/g, " ");
  out = out.split(/\s+/).filter((x) => x).join(" ");
  return out.replace(_CJK_SPACE_RE, "");
}

const _EVIDENCE_COVERAGE = 0.6;

function _covers_quote(quote: string, haystack: string): boolean {
  const n = quote.length;
  if (n === 0) {
    return false;
  }
  const L = Math.ceil(n * _EVIDENCE_COVERAGE);
  for (let i = 0; i <= n - L; i++) {
    if (haystack.includes(quote.substring(i, i + L))) {
      return true;
    }
  }
  return false;
}

const _VERIFIED_RUNS_LEDGER = ["runtime", "logs", "verified_runs.jsonl"];

let _VERIFIED_RUN_SNAPSHOT: Record<string, any> | null = null;

export function verified_run_snapshot<T>(record: Record<string, any>, fn: () => T): T {
  const prev = _VERIFIED_RUN_SNAPSHOT;
  _VERIFIED_RUN_SNAPSHOT = { ...record };
  try {
    return fn();
  } finally {
    _VERIFIED_RUN_SNAPSHOT = prev;
  }
}

function _record_contains_command(record: Record<string, any>, cmd: string): boolean {
  const cmds = (record.apv_cmds || []).map((item: any) => String(item).trim());
  const body = cmd.split(/[<\[{]/)[0].trim();
  return cmds.some((item: string) => item === cmd || (body && item.startsWith(body)));
}

function _find_verified_run_record(aid: string, run_ts: any, opts: { require_pass?: boolean } = {}): Record<string, any> | null {
  const require_pass = opts.require_pass ?? true;
  const ledger = path.join(_project_root(), ..._VERIFIED_RUNS_LEDGER);
  try {
    const { read_regular_nofollow, validate_json_budget } = require("../../../case_compiler/_sealed_io");
    let payload: Buffer;
    try {
      payload = read_regular_nofollow(ledger, {
        errorType: Error,
        invalid_message: "verified-run ledger path is invalid",
        directory_message: "verified-run ledger directory is unsafe",
        open_message: "verified-run ledger is unavailable",
        bounds_message: "verified-run ledger is not regular or too large",
        changed_message: "verified-run ledger changed while being read",
        max_bytes: 32 * 1024 * 1024,
        require_current_uid: true,
        preserve_missing: true,
      }) as Buffer;
    } catch (exc: any) {
      if (exc && exc.code === "ENOENT") {
        return null;
      }
      throw exc;
    }
    const lines = payload.toString("utf8").split(/\r?\n/);
    const records: Record<string, any>[] = [];
    for (let index = 0; index < lines.length; index++) {
      const line = lines[index];
      if (!line.trim()) {
        continue;
      }
      let rec: any;
      try {
        const encoded = Buffer.from(line, "utf8");
        if (encoded.length > 1024 * 1024) {
          return null;
        }
        validate_json_budget(encoded, { errorType: Error, message: "verified-run record exceeds structural budget" });
        rec = JSON.parse(line);
      } catch {
        if (index === lines.length - 1) {
          break;
        }
        return null;
      }
      if (rec === null || typeof rec !== "object" || Array.isArray(rec)) {
        return null;
      }
      records.push(rec);
    }
    for (const rec of records) {
      if (
        String(rec.autoid) === aid &&
        Math.abs(parseFloat(rec.run_ts ?? -1) - parseFloat(run_ts)) < 1e-6 &&
        (!require_pass || String(rec.verdict) === "pass")
      ) {
        return rec;
      }
    }
  } catch {
    return null;
  }
  return null;
}

function _device_evidence_supports(fact: any): boolean {
  if (["0", "false", "no"].includes((process.env.IST_WRITEBACK_DEVICE_AUTHORITY || "1").trim().toLowerCase())) {
    return false;
  }
  const dev = fact.device_evidence || {};
  const aid = String(dev.autoid || "").trim();
  const run_ts = dev.run_ts;
  const cmd = String(fact.cli_syntax || fact.content || "").trim();
  if (!aid || run_ts === null || run_ts === undefined || !cmd) {
    return false;
  }
  const sealed = _VERIFIED_RUN_SNAPSHOT;
  if (sealed !== null) {
    try {
      return Boolean(
        String(sealed.autoid || "") === aid &&
          String(sealed.verdict || "") === "pass" &&
          Math.abs(parseFloat(sealed.run_ts) - parseFloat(run_ts)) < 1e-6 &&
          (!dev.build || String(sealed.build || "") === String(dev.build)) &&
          /^[0-9a-f]{64}$/.test(String(sealed.xlsx_sha256 || "")) &&
          _record_contains_command(sealed, cmd)
      );
    } catch {
      return false;
    }
  }
  const rec = _find_verified_run_record(aid, run_ts, { require_pass: true });
  return Boolean(rec !== null && _record_contains_command(rec, cmd));
}

function _behavior_run_identity_supports(fact: any): boolean {
  if (fact.fact_kind !== "behavior") {
    return false;
  }
  if (["0", "false", "no"].includes((process.env.IST_WRITEBACK_DEVICE_AUTHORITY || "1").trim().toLowerCase())) {
    return false;
  }
  const dev = fact.device_evidence || {};
  const aid = String(dev.autoid || "").trim();
  const run_ts = dev.run_ts;
  const run_id = String(dev.run_id || "").trim();
  const echo = String(dev.echo_sha256 || "").trim();
  const cmd = String(fact.cli_syntax || fact.content || "").trim();
  if (!aid || run_ts === null || run_ts === undefined || !run_id || !cmd) {
    return false;
  }
  if (!/^[0-9a-f]{64}$/.test(echo)) {
    return false;
  }
  const rec = _find_verified_run_record(aid, run_ts, { require_pass: false });
  return Boolean(rec !== null && _record_contains_command(rec, cmd));
}

function _evidence_supports(fact: any): boolean {
  if (fact.device_evidence) {
    if (String(fact.validity || "").trim() === "uncertain") {
      const dev = fact.device_evidence || {};
      const cmd = String(fact.cli_syntax || fact.content || "").trim();
      return Boolean(String(dev.autoid || "").trim() && cmd);
    }
    if (_device_evidence_supports(fact)) {
      return true;
    }
    if (_behavior_run_identity_supports(fact)) {
      return true;
    }
    return false;
  }
  if (!fact.evidence_quote || !fact.evidence_file) {
    return false;
  }
  const evidencePath = _resolve_evidence_path(fact.evidence_file);
  if (evidencePath === null) {
    return false;
  }
  const trusted = _evidence_trusted_root(evidencePath);
  if (trusted === null) {
    return false;
  }
  let haystack: string;
  try {
    const { read_regular_nofollow } = require("../../../case_compiler/_sealed_io");
    const payload = read_regular_nofollow(evidencePath, {
      errorType: Error,
      invalid_message: "manual evidence path is invalid",
      directory_message: "manual evidence directory is unsafe",
      open_message: "manual evidence file is unavailable",
      bounds_message: "manual evidence file is not regular or too large",
      changed_message: "manual evidence changed while being read",
      max_bytes: 32 * 1024 * 1024,
      trusted_root: trusted,
    }) as Buffer;
    haystack = payload.toString("utf8");
  } catch {
    return false;
  }
  const haystack_norm = _normalize(haystack);
  const quote = _normalize(fact.evidence_quote);
  if (quote && (haystack_norm.includes(quote) || _covers_quote(quote, haystack_norm))) {
    return true;
  }
  if (fact.fact_kind === "cli_command") {
    const cmd = String(fact.cli_syntax || "").trim();
    const body = cmd.split(/[<\[{]/)[0].trim();
    if (body && haystack_norm.includes(_normalize(`**${body}**`))) {
      return true;
    }
  }
  return false;
}

function _now_iso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const offsetMin = -d.getTimezoneOffset();
  const sign = offsetMin >= 0 ? "+" : "-";
  const abs = Math.abs(offsetMin);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

function _update_meta(fp: Record<string, any>, source_thread: string, opts: { count_verified?: boolean } = {}): void {
  const count_verified = opts.count_verified ?? true;
  const meta = (fp.footprint_meta ??= {});
  if (!meta.created_at) {
    meta.created_at = _now_iso();
  }
  if (count_verified) {
    meta.verified_count = (meta.verified_count ?? 0) + 1;
  }
  const threads = (meta.source_threads ??= []);
  if (source_thread && !threads.includes(source_thread)) {
    threads.push(source_thread);
    if (threads.length > 10) {
      threads.splice(0, threads.length - 10);
    }
  }
}

function _evidence(fact: any): Record<string, any> {
  const ev: Record<string, any> = {};
  if (fact.evidence_file) {
    ev.source_file = fact.evidence_file;
  }
  if (fact.evidence_quote) {
    ev.quoted_text = fact.evidence_quote;
  }
  const _raw = String(fact.raw_invocation || "").trim();
  if (_raw && _raw !== String(fact.cli_syntax || "").trim()) {
    ev.raw_invocation = _raw;
  }
  const dev = fact.device_evidence || {};
  if (dev.autoid) {
    const run: Record<string, any> = { autoid: String(dev.autoid) };
    if (dev.run_ts) {
      run.run_ts = dev.run_ts;
    }
    if (dev.build) {
      run.build = String(dev.build);
    }
    if (dev.run_id) {
      run.run_id = String(dev.run_id);
    }
    if (dev.echo_sha256) {
      run.echo_sha256 = String(dev.echo_sha256);
    }
    ev.device_run = run;
  }
  return ev;
}

function _merge_parameters(existing: Record<string, any>[], incoming: Record<string, any>[]): boolean {
  let changed = false;
  const by_name: Record<string, Record<string, any>> = {};
  for (const p of existing) {
    if (p.name) {
      by_name[p.name] = p;
    }
  }
  for (const inc of incoming) {
    const name = inc.name;
    if (!name) {
      continue;
    }
    if (!(name in by_name)) {
      existing.push(inc);
      by_name[name] = inc;
      changed = true;
      continue;
    }
    const cur = by_name[name];
    for (const [k, v] of Object.entries(inc)) {
      if (k === "name") {
        continue;
      }
      if (v !== null && v !== "" && !cur[k]) {
        cur[k] = v;
        changed = true;
      }
    }
  }
  return changed;
}

const _PLACEHOLDER_RE = /[<\[{]/;
const _MANUAL_VERSION_RES = [/(?:^|\/)manual_(\d+(?:\.\d+)*)/, /(?:^|\/)manual\/(\d+(?:\.\d+)*)(?:\/|$)/];

function _derive_valid_for(fact: any): string[] {
  const out: string[] = [];
  for (let v of fact.valid_for || []) {
    v = String(v).trim();
    if (v && !out.includes(v)) {
      out.push(v);
    }
  }
  const src = String(fact.evidence_file || "").trim();
  if (src) {
    for (const rx of _MANUAL_VERSION_RES) {
      const m = rx.exec(src);
      if (m) {
        if (!out.includes(m[1])) {
          out.push(m[1]);
        }
        break;
      }
    }
  }
  const dev = fact.device_evidence || {};
  const build = String(dev.build || "").trim();
  if (build && !out.includes(build)) {
    out.push(build);
  }
  return out;
}

function _entry_valid_for(entry: Record<string, any>): Set<string> {
  return new Set((entry.valid_for || []).map((v: any) => String(v).trim()).filter((v: string) => v));
}

function _apply_temporal_fields(entry: Record<string, any>, fact: any, valid_for: string[]): void {
  if (valid_for.length > 0) {
    entry.valid_for = valid_for.slice();
  }
  const superseded_by = String(fact.superseded_by || "").trim();
  if (superseded_by) {
    entry.superseded_by = superseded_by;
  }
}

export function command_words(cmd: string): string[] {
  const words: string[] = [];
  for (const tok of String(cmd || "").split(_PLACEHOLDER_RE)[0].split(/\s+/)) {
    const t = tok.trim().replace(/,+$/, "");
    if (!t || !/^[a-zA-Z]+$/.test(t.replace(/-/g, ""))) {
      break;
    }
    words.push(t);
  }
  return words;
}

function _attach_device_run(existing: Record<string, any>, fact: any): string {
  const ev = (existing.evidence ??= {});
  const new_ev = _evidence(fact);
  if (!new_ev.device_run) {
    return "skip";
  }
  ev.device_run = new_ev.device_run;
  if (new_ev.raw_invocation) {
    ev.raw_invocation = new_ev.raw_invocation;
  }
  return "update";
}

const _DRIFT_CAP = 20;

function _record_drift(fp: Record<string, any>, kind: string, detail: Record<string, any>): void {
  const observations = (fp.drift_observations ??= []);
  const dedup_key = String(detail.catalog_head || detail.command || "");
  for (const existing of observations) {
    if (existing.kind === kind && String(existing.catalog_head || existing.command || "") === dedup_key) {
      existing.at = _now_iso();
      return;
    }
  }
  const entry: Record<string, any> = { kind, at: _now_iso(), ...detail };
  observations.push(entry);
  if (observations.length > _DRIFT_CAP) {
    observations.splice(0, observations.length - _DRIFT_CAP);
  }
}

function _append_catalog_command(fp: Record<string, any>, fact: any, commands: any[]): string {
  const head = String(fact.catalog_head || "").trim();
  const ident: Record<string, string> = {};
  for (const [k, v] of Object.entries(fact.catalog_identity || {})) {
    if (String(v || "").trim()) {
      ident[String(k)] = String(v);
    }
  }
  const reject = _catalog_head_write_reject_reason(head, ident);
  if (reject) {
    _record_drift(fp, "catalog_head_rejected", { catalog_head: head, reason: reject, catalog: ident });
    return "reject";
  }
  for (const existing of commands) {
    if (String(existing.catalog_head || "").trim() !== head) {
      continue;
    }
    const old_sha = String((existing.catalog || {}).sha256 || "");
    const new_sha = String(ident.sha256 || "");
    if (old_sha === new_sha) {
      if ((fact.device_evidence || {}).autoid) {
        return _attach_device_run(existing, fact);
      }
      return "skip";
    }
    _record_drift(fp, "catalog_ref_updated", { catalog_head: head, previous: existing.catalog || {}, current: ident });
    existing.catalog = ident;
    if (fact.evidence_file || fact.evidence_quote) {
      existing.evidence = _evidence(fact);
    }
    _apply_temporal_fields(existing, fact, _derive_valid_for(fact));
    return "update";
  }
  const entry: Record<string, any> = { fact_key: fact.fact_key, catalog_head: head, catalog: ident, evidence: _evidence(fact) };
  _apply_temporal_fields(entry, fact, _derive_valid_for(fact));
  commands.push(entry);
  return "append";
}

function _catalog_head_write_reject_reason(head: string, ident: Record<string, string>): string | null {
  if (!head) {
    return "empty_catalog_head";
  }
  const version = String(ident.version || "").trim();
  const family = String(ident.family || "").trim();
  if (!version || !family) {
    return "catalog_identity_incomplete";
  }
  let catalog: any;
  let verdict: any;
  try {
    const { load_coupled_catalog } = require("../../../../kms/manual_catalog_store");
    [catalog, verdict] = load_coupled_catalog(version, family);
  } catch (exc) {
    logger.exception(`catalog_head 写侧校验失败: ${version}/${family}`);
    return "catalog_lookup_failed";
  }
  if (catalog === null || String((verdict || {}).status || "") !== "ok") {
    return "catalog_not_in_effect";
  }
  for (const signature of catalog.signatures || []) {
    if (signature === null || typeof signature !== "object") {
      continue;
    }
    const tokens = signature.head_tokens || [];
    if (tokens.map((t: any) => String(t)).filter((t: string) => t).join(" ").trim() === head) {
      return null;
    }
  }
  return "catalog_head_absent";
}

function _append_cli_command(fp: Record<string, any>, fact: any): string {
  const commands = ((fp.cli ??= {}).commands ??= []);
  if (String(fact.catalog_head || "").trim()) {
    return _append_catalog_command(fp, fact, commands);
  }
  const syntax = String(fact.cli_syntax).trim();
  const valid_for = _derive_valid_for(fact);
  const vf_key = new Set(valid_for);
  const setsEqual = (a: Set<string>, b: Set<string>) => a.size === b.size && [...a].every((x) => b.has(x));
  for (const existing of commands) {
    if (String(existing.command || "").trim() === syntax && setsEqual(_entry_valid_for(existing), vf_key)) {
      if (fact.parameters && fact.parameters.length > 0) {
        const changed = _merge_parameters((existing.parameters ??= []), fact.parameters);
        return changed ? "append" : "skip";
      }
      return "skip";
    }
  }
  const is_device_verbatim = Boolean((fact.device_evidence || {}).autoid);
  if (is_device_verbatim) {
    const words = command_words(syntax);
    if (words.length > 0) {
      let targets = commands.filter((e: any) => (e.evidence || {}).source_file && JSON.stringify(command_words(e.command || "")) === JSON.stringify(words));
      targets = targets.concat(
        commands.filter((e: any) => String(e.catalog_head || "").trim() && JSON.stringify(catalog_head_tokens_clean(String(e.catalog_head).split(/\s+/))) === JSON.stringify(words))
      );
      if (targets.length === 1) {
        return _attach_device_run(targets[0], fact);
      }
      if (targets.length === 0) {
        const cat_heads = commands.filter((e: any) => String(e.catalog_head || "").trim()).map((e: any) => String(e.catalog_head).trim());
        if (cat_heads.length > 0) {
          _record_drift(fp, "device_form_not_in_catalog", { command: syntax, catalog_heads: cat_heads.slice(0, 8) });
        }
      }
    }
  }
  const entry: Record<string, any> = { fact_key: fact.fact_key, command: fact.cli_syntax, evidence: _evidence(fact) };
  _apply_temporal_fields(entry, fact, valid_for);
  if (is_device_verbatim) {
    entry.syntax_provenance = "device_run_verbatim";
  }
  if (fact.parameters && fact.parameters.length > 0) {
    entry.parameters = fact.parameters;
  }
  commands.push(entry);
  return "append";
}

function _append_decision_rule(fp: Record<string, any>, fact: any): string {
  const rules = (fp.decision_rules ??= []);
  for (const existing of rules) {
    if (existing.fact_key === fact.fact_key) {
      return "skip";
    }
  }
  const entry: Record<string, any> = { fact_key: fact.fact_key, condition: fact.condition, decision: fact.decision, evidence: _evidence(fact) };
  _apply_temporal_fields(entry, fact, _derive_valid_for(fact));
  rules.push(entry);
  return "append";
}

function _append_behavior(fp: Record<string, any>, fact: any): string {
  const behaviors = (fp.behaviors ??= []);
  const validity = String(fact.validity || "verified").trim() || "verified";
  const observed_under = String(fact.observed_under || "").trim();
  for (const existing of behaviors) {
    if (existing.fact_key === fact.fact_key) {
      if (existing.validity === "uncertain" && validity === "verified") {
        existing.content = fact.content || existing.content || "";
        existing.evidence = _evidence(fact);
        existing.validity = "verified";
        if (observed_under) {
          existing.observed_under = observed_under;
        }
        try {
          const { emit_signal } = require("./signals");
          emit_signal("upgraded_verified", fact.fact_key, {
            source: "merger._append_behavior",
            autoid: String((fact.device_evidence || {}).autoid || ""),
          });
        } catch {}
        return "update";
      }
      return "skip";
    }
  }
  const entry: Record<string, any> = { fact_key: fact.fact_key, content: fact.content, evidence: _evidence(fact) };
  _apply_temporal_fields(entry, fact, _derive_valid_for(fact));
  if (validity !== "verified") {
    entry.validity = validity;
  }
  if (observed_under) {
    entry.observed_under = observed_under;
  }
  behaviors.push(entry);
  return "append";
}

function _append_known_issue(fp: Record<string, any>, fact: any): string {
  const issues = (fp.known_issues ??= []);
  for (const existing of issues) {
    if (existing.issue_id === fact.issue_id) {
      let updated = false;
      if (fact.issue_title && !existing.title) {
        existing.title = fact.issue_title;
        updated = true;
      }
      if (fact.affected_versions && fact.affected_versions.length > 0) {
        const merged = [...new Set([...(existing.affected_versions || []), ...fact.affected_versions])].sort();
        if (JSON.stringify(merged) !== JSON.stringify(existing.affected_versions)) {
          existing.affected_versions = merged;
          updated = true;
        }
      }
      return updated ? "update" : "skip";
    }
  }
  const entry: Record<string, any> = { issue_id: fact.issue_id };
  if (fact.issue_title) {
    entry.title = fact.issue_title;
  }
  if (fact.affected_versions && fact.affected_versions.length > 0) {
    entry.affected_versions = [...new Set<string>(fact.affected_versions)].sort();
    if (fp.level === "leaf") {
      const vs = (fp.version_scope ??= {});
      const cur = new Set<string>(vs.product_versions || []);
      for (const v of fact.affected_versions) {
        cur.add(v);
      }
      vs.product_versions = [...cur].sort();
    }
  }
  issues.push(entry);
  return "append";
}

function _distinct_observation_contexts(fp: Record<string, any>): Set<string> {
  const out = new Set<string>();
  for (const e of [...(fp.decision_rules || []), ...(fp.behaviors || [])]) {
    if (e !== null && typeof e === "object") {
      const ou = String(e.observed_under || "").trim();
      if (ou) {
        out.add(ou);
      }
    }
  }
  return out;
}

const _DISPATCH: Record<string, (fp: Record<string, any>, fact: any) => string> = {
  cli_command: _append_cli_command,
  decision_rule: _append_decision_rule,
  behavior: _append_behavior,
  known_issue: _append_known_issue,
};

export function merge_fact(routed: RoutedFact, footprint_dir: string): MergeResult {
  const fact = routed.fact;
  const { lexical_absolute, lexical_path_inside_root } = require("../../../case_compiler/_sealed_io");
  const root = lexical_absolute(String(footprint_dir));
  let relative_parts: string[];
  let target_path: string;
  try {
    target_path = lexical_path_inside_root(routed.target_file, root, {
      errorType: FootprintWriteError,
      traversal_message: "path escapes footprint dir",
      outside_message: "path escapes footprint dir",
    });
    if (path.extname(target_path).toLowerCase() !== ".json" || path.basename(target_path).startsWith(".")) {
      throw new FootprintWriteError("footprint target must be a public JSON node");
    }
    relative_parts = path.relative(root, target_path).split(path.sep).filter((c) => c.length > 0);
    if (relative_parts.length !== 2) {
      throw new FootprintWriteError("footprint target must be one node directory plus one JSON file");
    }
  } catch (exc: any) {
    if (exc instanceof FootprintWriteError) {
      return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: String(exc.message ?? exc) });
    }
    throw exc;
  }
  if (!LEVEL_KINDS[routed.level] || !LEVEL_KINDS[routed.level].has(fact.fact_kind)) {
    return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: "kind not allowed at level" });
  }
  if (fact.fact_kind !== "known_issue" && !_evidence_supports(fact)) {
    return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: "evidence not found in source file" });
  }
  const handler = _DISPATCH[fact.fact_kind];
  if (!handler) {
    return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: "unknown fact_kind" });
  }
  let _ctx_before: Set<string> = new Set();
  let _ctx_after: Set<string> = new Set();
  let result_action: string;
  try {
    result_action = _withLockedFootprintRoot(root, (rootDir) => {
      const parent_dir = _open_target_directory_at(rootDir, relative_parts.slice(0, -1));
      const name = relative_parts[relative_parts.length - 1];
      let fp = _read_footprint_at(parent_dir, name);
      const created = fp === null;
      if (created) {
        fp = TEMPLATE_MAP[routed.level](path.basename(name, ".json"));
      } else {
        _ctx_before = _distinct_observation_contexts(fp!);
      }
      const action = handler(fp!, fact);
      if (action === "skip") {
        return created ? "__skip_create__" : "__skip_dup__";
      }
      _update_meta(fp!, fact.source_thread, { count_verified: String((fact as any).validity || "verified") !== "uncertain" });
      _write_footprint_at(parent_dir, name, fp!);
      _ctx_after = _distinct_observation_contexts(fp!);
      return created ? "create" : action;
    });
    if (result_action === "__skip_create__") {
      return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: "empty after handler" });
    }
    if (result_action === "__skip_dup__") {
      return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: "duplicate" });
    }
  } catch (exc: any) {
    if (exc instanceof FootprintWriteError || exc instanceof Error) {
      logger.warning(`footprint read/write failed ${target_path!}: ${exc}`);
      return makeMergeResult({ action: "skip", target_file: routed.target_file, detail: String(exc.message ?? exc) });
    }
    throw exc;
  }
  if (_ctx_before.size < 2 && _ctx_after.size >= 2) {
    try {
      const { emit_signal } = require("./signals");
      emit_signal("observation_group_formed", path.basename(target_path!, ".json"), {
        source: "merger.merge_fact",
        fact_key: fact.fact_key,
        contexts: [..._ctx_after].sort().slice(0, 6),
      });
    } catch {}
  }
  return makeMergeResult({ action: result_action, target_file: routed.target_file, detail: fact.fact_kind });
}
