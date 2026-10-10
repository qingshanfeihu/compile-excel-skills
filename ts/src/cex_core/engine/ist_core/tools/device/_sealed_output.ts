import {
  atomic_write_bytes_nofollow,
  lexical_absolute,
  read_regular_nofollow,
  validate_json_budget,
  FileIdentity,
} from "../../../case_compiler/_sealed_io";
import { P, PyValueError, pyJsonDumps, pyJsonLoads } from "../../../_py";

export class OutputLedgerError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "OutputLedgerError";
  }
}

export class OutputJsonBudgetError extends OutputLedgerError {
  constructor(message?: string) {
    super(message);
    this.name = "OutputJsonBudgetError";
  }
}

const _MAX_LEDGER_BYTES = 32 * 1024 * 1024;

export function output_root(): P {
  const sh = require("../compile_engine/_shared");
  return new P(lexical_absolute(String(sh.outputs_root())));
}

function _partsOf(text: string): string[] {
  return text.split(/[\\/]+/).filter((s) => s !== "");
}

export function scoped_output_path(raw_path: string | P): P {
  const text = String(raw_path ?? "").trim();
  if (!text) {
    throw new OutputLedgerError("output path is empty");
  }
  const raw = new P(text);
  const rawParts = _partsOf(text);
  if (rawParts.includes("..") || text.startsWith("~") || rawParts.includes("~") || text.includes("\x00")) {
    throw new OutputLedgerError("output path traversal is not allowed");
  }
  const root = output_root();
  let target: P;
  if (raw.is_absolute()) {
    target = new P(lexical_absolute(text));
  } else if (text === "workspace/outputs" || text.startsWith("workspace/outputs/")) {
    const sh = require("../compile_engine/_shared");
    target = new P(lexical_absolute(new P(String(sh.project_root())).joinpath(text)._p));
  } else if (text === "outputs" || text.startsWith("outputs/")) {
    const rel = text.slice("outputs".length).replace(/^\/+/, "");
    target = new P(lexical_absolute(root.joinpath(rel)._p));
  } else {
    target = new P(lexical_absolute(root.joinpath(text)._p));
  }
  let rel: P;
  try {
    rel = target.relative_to(root);
  } catch (exc) {
    if (exc instanceof PyValueError) {
      throw new OutputLedgerError("path is outside the current workspace/outputs scope");
    }
    throw exc;
  }
  if (rel.parts.length === 0) {
    throw new OutputLedgerError("an output file path is required");
  }
  return target;
}

export function case_output_path(autoid: string, filename: string): P {
  const aid = String(autoid ?? "").trim();
  if (aid.length !== 18 || !/^\d+$/.test(aid)) {
    throw new OutputLedgerError("autoid must be exactly 18 digits");
  }
  if (!filename || new P(filename).name !== filename || filename === "." || filename === "..") {
    throw new OutputLedgerError("output filename is invalid");
  }
  return scoped_output_path(output_root().joinpath(aid, filename));
}

export function sibling_last_run_path(raw_path: string | P): P {
  const source = scoped_output_path(raw_path);
  const target = source.name === "last_run.json" ? source : source.parent.joinpath("last_run.json");
  return scoped_output_path(target);
}

export function read_bytes(
  path: string | P,
  opts: { max_bytes?: number; preserve_missing?: boolean; return_identity?: boolean } = {},
): Buffer | [Buffer, FileIdentity] {
  const target = scoped_output_path(path);
  return read_regular_nofollow(target._p, {
    errorType: OutputLedgerError,
    invalid_message: "output file path is invalid",
    directory_message: "output directory is unavailable or unsafe",
    open_message: "output file is unavailable or unsafe",
    bounds_message: "output file exceeds the allowed size or is not regular",
    changed_message: "output file changed while being read",
    max_bytes: opts.max_bytes ?? _MAX_LEDGER_BYTES,
    min_bytes: 0,
    require_current_uid: true,
    preserve_missing: opts.preserve_missing ?? false,
    return_identity: opts.return_identity ?? false,
  });
}

export function read_json(path: string | P, opts: { max_bytes?: number; preserve_missing?: boolean } = {}): any {
  const payload = read_bytes(path, { max_bytes: opts.max_bytes ?? _MAX_LEDGER_BYTES, preserve_missing: opts.preserve_missing ?? false }) as Buffer;
  validate_json_budget(payload, { errorType: OutputJsonBudgetError, message: "output JSON exceeds structural budget" });
  try {
    return pyJsonLoads(payload.toString("utf8"));
  } catch {
    throw new OutputLedgerError("output JSON is invalid");
  }
}

export function write_json(path: string | P, value: any): string {
  const { current_worker_device_session } = require("../worker_device_context");
  const { session_admission_boundary } = require("../compile_engine/engine_quarantine");
  const target = scoped_output_path(path);
  const payload = Buffer.from(pyJsonDumps(value, { ensure_ascii: false, indent: 2 }) + "\n", "utf8");
  if (payload.length > _MAX_LEDGER_BYTES) {
    throw new OutputLedgerError("output JSON exceeds the allowed size");
  }
  validate_json_budget(payload, { errorType: OutputJsonBudgetError, message: "output JSON exceeds structural budget" });
  const boundary = session_admission_boundary(current_worker_device_session());
  try {
    if (boundary && typeof boundary.enter === "function") boundary.enter();
    return atomic_write_bytes_nofollow(target._p, payload, {
      errorType: OutputLedgerError,
      invalid_message: "output file path is invalid",
      unavailable_message: "output directory or file is unavailable or unsafe",
      create_parents: true,
      mode: 0o600,
    });
  } finally {
    if (boundary && typeof boundary.exit === "function") boundary.exit();
  }
}

export function mtime_ns_from_identity(path: string | P): number {
  const target = scoped_output_path(path);
  const [, identity] = read_regular_nofollow(target._p, {
    errorType: OutputLedgerError,
    invalid_message: "output file path is invalid",
    directory_message: "output directory is unavailable or unsafe",
    open_message: "output file is unavailable or unsafe",
    bounds_message: "output file exceeds the allowed size or is not regular",
    changed_message: "output file changed while being read",
    max_bytes: _MAX_LEDGER_BYTES,
    min_bytes: 0,
    require_current_uid: true,
    return_identity: true,
  }) as [Buffer, FileIdentity];
  return Math.trunc(identity[3]);
}

export function ensure_case_directory(autoid: string): P {
  const { open_directory_nofollow } = require("../../../case_compiler/_sealed_io");
  const path = case_output_path(autoid, ".scope-anchor").parent;
  open_directory_nofollow(path._p, {
    errorType: OutputLedgerError,
    invalid_message: "case output directory is invalid",
    unavailable_message: "case output directory is unavailable or unsafe",
    create_missing: true,
    create_mode: 0o700,
  });
  return path;
}
