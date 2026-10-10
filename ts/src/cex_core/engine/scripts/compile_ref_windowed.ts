// 生成：tools/extract_engine.py ← InfoTest main/scripts/compile_ref_windowed.py（sha256 2d4579acb916fe9c）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const _ROOT = _cex_data_path("");
const _COMPILE_REF = path.join(_ROOT, "knowledge", "data", "compile_ref");
const _DEFAULT_INDEX_PATH = path.join(_COMPILE_REF, "method_reference.json");
const _SHARD_DIR_NAME = "method_reference";
const _MAX_WINDOW_LINES = 200;
const _INDEX_FORMAT = "method-reference-windowed-index-v1";
const _SHARD_FORMAT = "method-reference-windowed-shard-v1";
const _UNSET = Symbol("unset");

export class WindowedProjectionError extends Error {}

export function render_json(value: any): string {
  return JSON.stringify(value, null, 2) + "\n";
}

export function line_count(value: any): number {
  return render_json(value).split(/\r?\n/).length - 1;
}

function _container_kind(value: any): string {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return "mapping";
  }
  if (Array.isArray(value)) {
    return "sequence";
  }
  return "scalar";
}

function _source_sha256(data: Record<string, any>): string {
  return crypto.createHash("sha256").update(render_json(data), "utf8").digest("hex");
}

function _shard_payload(section: string, container: string, entries: any, source_sha256: string): Record<string, any> {
  return { _meta: { format: _SHARD_FORMAT, section, container, source_sha256 }, entries };
}

function _fits(section: string, container: string, entries: any, source_sha256: string, max_lines: number): boolean {
  return line_count(_shard_payload(section, container, entries, source_sha256)) <= max_lines;
}

function _oversize_error(_section: string, max_lines: number): WindowedProjectionError {
  return new WindowedProjectionError(`method_reference contains an indivisible semantic unit that exceeds the ${max_lines}-line read-window budget`);
}

function _split_mapping(section: string, entries: Record<string, any>, source_sha256: string, max_lines: number): Array<Record<string, any>> {
  if (_fits(section, "mapping", entries, source_sha256, max_lines)) {
    return [entries];
  }
  const parts: Array<Record<string, any>> = [];
  let current: Record<string, any> = {};
  for (const [key, value] of Object.entries(entries)) {
    const candidate = { ...current, [key]: value };
    if (_fits(section, "mapping", candidate, source_sha256, max_lines)) {
      current = candidate;
      continue;
    }
    if (Object.keys(current).length) {
      parts.push(current);
      current = { [key]: value };
    } else {
      current = candidate;
    }
    if (!_fits(section, "mapping", current, source_sha256, max_lines)) {
      throw _oversize_error(section, max_lines);
    }
  }
  if (Object.keys(current).length || !Object.keys(entries).length) {
    parts.push(current);
  }
  return parts;
}

function _split_sequence(section: string, entries: any[], source_sha256: string, max_lines: number): any[][] {
  if (_fits(section, "sequence", entries, source_sha256, max_lines)) {
    return [entries];
  }
  const parts: any[][] = [];
  let current: any[] = [];
  for (const value of entries) {
    const candidate = [...current, value];
    if (_fits(section, "sequence", candidate, source_sha256, max_lines)) {
      current = candidate;
      continue;
    }
    if (current.length) {
      parts.push(current);
      current = [value];
    } else {
      current = candidate;
    }
    if (!_fits(section, "sequence", current, source_sha256, max_lines)) {
      throw _oversize_error(section, max_lines);
    }
  }
  if (current.length || !entries.length) {
    parts.push(current);
  }
  return parts;
}

function _split_section(section: string, value: any, source_sha256: string, max_lines: number): [string, any[]] {
  const container = _container_kind(value);
  if (container === "mapping") {
    return [container, _split_mapping(section, value, source_sha256, max_lines)];
  }
  if (container === "sequence") {
    return [container, _split_sequence(section, value, source_sha256, max_lines)];
  }
  if (!_fits(section, container, value, source_sha256, max_lines)) {
    throw _oversize_error(section, max_lines);
  }
  return [container, [value]];
}

function _safe_filename_part(section: string): string {
  const cleaned = [...section].map((ch) => /[a-zA-Z0-9_-]/.test(ch) ? ch : "-").join("");
  return cleaned || "section";
}

function _rebuild(index: Record<string, any>, shard_payloads: Record<string, Record<string, any>>): Record<string, any> {
  const meta = index._meta;
  if (typeof meta !== "object" || meta === null || meta.format !== _INDEX_FORMAT) {
    throw new WindowedProjectionError("method_reference index format is invalid");
  }
  const source_sha256 = meta.source_sha256;
  const sections = index.sections;
  if (typeof source_sha256 !== "string" || !Array.isArray(sections)) {
    throw new WindowedProjectionError("method_reference index is incomplete");
  }
  const rebuilt: Record<string, any> = {};
  for (const section_info of sections) {
    if (typeof section_info !== "object" || section_info === null) {
      throw new WindowedProjectionError("method_reference index section is invalid");
    }
    const name = section_info.name;
    const container = section_info.container;
    const descriptors = section_info.shards;
    if (typeof name !== "string" || !["mapping", "sequence", "scalar"].includes(container) || !Array.isArray(descriptors) || !descriptors.length) {
      throw new WindowedProjectionError("method_reference index section is incomplete");
    }
    let value: any;
    if (container === "mapping") {
      value = {};
    } else if (container === "sequence") {
      value = [];
    } else {
      value = _UNSET;
    }
    for (const descriptor of descriptors) {
      if (typeof descriptor !== "object" || descriptor === null || typeof descriptor.path !== "string") {
        throw new WindowedProjectionError("method_reference shard descriptor is invalid");
      }
      const relPath = descriptor.path;
      const shard = shard_payloads[relPath];
      if (typeof shard !== "object" || shard === null) {
        throw new WindowedProjectionError("method_reference shard is unavailable");
      }
      const shard_meta = shard._meta;
      if (typeof shard_meta !== "object" || shard_meta === null || shard_meta.format !== _SHARD_FORMAT || shard_meta.section !== name || shard_meta.container !== container || shard_meta.source_sha256 !== source_sha256) {
        throw new WindowedProjectionError("method_reference shard metadata does not match index");
      }
      const entries = shard.entries;
      if (container === "mapping") {
        if (typeof entries !== "object" || entries === null || Array.isArray(entries)) {
          throw new WindowedProjectionError("method_reference mapping shard is invalid");
        }
        const overlap = Object.keys(value).filter((k) => k in entries);
        if (overlap.length) {
          throw new WindowedProjectionError("method_reference mapping shard is invalid");
        }
        Object.assign(value, entries);
      } else if (container === "sequence") {
        if (!Array.isArray(entries)) {
          throw new WindowedProjectionError("method_reference sequence shard is invalid");
        }
        value.push(...entries);
      } else {
        if (value !== _UNSET) {
          throw new WindowedProjectionError("method_reference scalar section is split");
        }
        value = entries;
      }
    }
    rebuilt[name] = value;
  }
  if (_source_sha256(rebuilt) !== source_sha256) {
    throw new WindowedProjectionError("method_reference shards do not reconstruct the indexed source");
  }
  return rebuilt;
}

export function build_method_reference_window(data: Record<string, any>, max_lines: number = _MAX_WINDOW_LINES): [Record<string, any>, Record<string, string>] {
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new WindowedProjectionError("method_reference projection must be a JSON object");
  }
  if (max_lines < 1) {
    throw new WindowedProjectionError("read-window budget must be positive");
  }
  const source_sha256 = _source_sha256(data);
  const section_infos: Array<Record<string, any>> = [];
  const shard_payloads: Record<string, Record<string, any>> = {};
  const shard_texts: Record<string, string> = {};
  let ordinal = 1;
  for (const [section, value] of Object.entries(data)) {
    if (typeof section !== "string") {
      throw new WindowedProjectionError("method_reference section names must be strings");
    }
    const [container, parts] = _split_section(section, value, source_sha256, max_lines);
    const descriptors: Array<Record<string, any>> = [];
    for (const entries of parts) {
      const filename = `shard-${String(ordinal).padStart(3, "0")}-${_safe_filename_part(section)}.json`;
      const relPath = `${_SHARD_DIR_NAME}/${filename}`;
      const payload = _shard_payload(section, container, entries, source_sha256);
      const text = render_json(payload);
      const lines = text.split(/\r?\n/).length - 1;
      if (lines > max_lines) {
        throw _oversize_error(section, max_lines);
      }
      shard_payloads[relPath] = payload;
      shard_texts[relPath] = text;
      descriptors.push({ path: relPath, entry_count: typeof entries === "object" && entries !== null ? (Array.isArray(entries) ? entries.length : Object.keys(entries).length) : 1, line_count: lines });
      ordinal += 1;
    }
    section_infos.push({ name: section, container, shards: descriptors });
  }
  const index = {
    _meta: {
      format: _INDEX_FORMAT,
      purpose: "Navigation index for the worker-readable method-reference projection. Each listed shard is a complete semantic subset, never a physical-line slice. For a named method or note, fs_grep this shard directory first, then fs_read only the matching shard; absence from one shard is not a claim about the whole projection.",
      regenerate: "python scripts/gen_method_reference.py",
      max_lines,
      shard_dir: _SHARD_DIR_NAME,
      source_sha256,
    },
    sections: section_infos,
  };
  if (line_count(index) > max_lines) {
    throw new WindowedProjectionError(`method_reference navigation index exceeds the ${max_lines}-line read-window budget`);
  }
  if (JSON.stringify(_rebuild(index, shard_payloads)) !== JSON.stringify(data)) {
    throw new WindowedProjectionError("method_reference partition lost or changed semantic data");
  }
  return [index, shard_texts];
}

function _resolve_shard_path(index_path: string, rel_path: string): string {
  const rel = path.normalize(rel_path);
  if (path.isAbsolute(rel) || rel.split(path.sep).some((p) => ["", ".", ".."].includes(p))) {
    throw new WindowedProjectionError("method_reference index contains an unsafe shard path");
  }
  const parts = rel.split(path.sep);
  if (parts.length !== 2 || parts[0] !== _SHARD_DIR_NAME || !path.basename(rel).startsWith("shard-") || path.extname(rel) !== ".json") {
    throw new WindowedProjectionError("method_reference index points outside its shard namespace");
  }
  const root = path.resolve(path.dirname(index_path));
  const resolved = path.resolve(root, rel);
  if (!resolved.startsWith(root)) {
    throw new WindowedProjectionError("method_reference shard escapes compile_ref");
  }
  return resolved;
}

function _read_index(index_path: string): Record<string, any> {
  let data: any;
  try {
    data = JSON.parse(fs.readFileSync(index_path, "utf8"));
  } catch (exc) {
    throw new WindowedProjectionError("method_reference index is unavailable or invalid");
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new WindowedProjectionError("method_reference index must be a JSON object");
  }
  return data;
}

export function method_reference_artifact_paths(index_path: string = _DEFAULT_INDEX_PATH): string[] {
  const index = _read_index(index_path);
  if ((index._meta ?? {}).format !== _INDEX_FORMAT) {
    throw new WindowedProjectionError("method_reference index format is invalid");
  }
  const paths = [index_path];
  for (const section of index.sections ?? []) {
    if (typeof section !== "object" || section === null) {
      throw new WindowedProjectionError("method_reference index section is invalid");
    }
    for (const descriptor of section.shards ?? []) {
      if (typeof descriptor !== "object" || descriptor === null || typeof descriptor.path !== "string") {
        throw new WindowedProjectionError("method_reference shard descriptor is invalid");
      }
      paths.push(_resolve_shard_path(index_path, descriptor.path));
    }
  }
  return paths;
}

export function load_method_reference(index_path: string = _DEFAULT_INDEX_PATH): Record<string, any> {
  const index = _read_index(index_path);
  if ((index._meta ?? {}).format !== _INDEX_FORMAT) {
    throw new WindowedProjectionError("method_reference index format is invalid");
  }
  const payloads: Record<string, Record<string, any>> = {};
  for (const section of index.sections ?? []) {
    if (typeof section !== "object" || section === null) {
      throw new WindowedProjectionError("method_reference index section is invalid");
    }
    for (const descriptor of section.shards ?? []) {
      if (typeof descriptor !== "object" || descriptor === null || typeof descriptor.path !== "string") {
        throw new WindowedProjectionError("method_reference shard descriptor is invalid");
      }
      const relPath = descriptor.path;
      const shardPath = _resolve_shard_path(index_path, relPath);
      let payload: any;
      try {
        payload = JSON.parse(fs.readFileSync(shardPath, "utf8"));
      } catch {
        throw new WindowedProjectionError("method_reference shard is unavailable or invalid");
      }
      if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
        throw new WindowedProjectionError("method_reference shard must be a JSON object");
      }
      payloads[relPath] = payload;
    }
  }
  return _rebuild(index, payloads);
}

function _atomic_write(filePath: string, text: string): void {
  const temp = path.join(path.dirname(filePath), `.${path.basename(filePath)}.tmp`);
  try {
    fs.writeFileSync(temp, text, "utf8");
    fs.renameSync(temp, filePath);
  } finally {
    if (fs.existsSync(temp)) {
      fs.unlinkSync(temp);
    }
  }
}

function _owned_stale_shards(index_path: string, shard_dir: string, expected_paths: Set<string>): Set<string> {
  const existing = new Set(fs.readdirSync(shard_dir).filter((f) => f.startsWith("shard-") && f.endsWith(".json")).map((f) => path.join(shard_dir, f)));
  if (!existing.size) {
    return new Set();
  }
  if (!fs.statSync(index_path).isFile()) {
    throw new WindowedProjectionError("method_reference shard directory contains unowned shard files");
  }
  const index = _read_index(index_path);
  if ((index._meta ?? {}).format !== _INDEX_FORMAT) {
    throw new WindowedProjectionError("method_reference shard directory has no valid owning index");
  }
  let declared: Set<string>;
  try {
    load_method_reference(index_path);
    declared = new Set(method_reference_artifact_paths(index_path).slice(1));
  } catch (exc) {
    throw new WindowedProjectionError("existing method_reference shards fail ownership validation");
  }
  const unowned = [...existing].filter((p) => !declared.has(p));
  if (unowned.length) {
    throw new WindowedProjectionError("method_reference shard directory contains unowned shard files");
  }
  return new Set([...declared].filter((p) => !expected_paths.has(p)));
}

export function write_method_reference_window(data: Record<string, any>, index_path: string = _DEFAULT_INDEX_PATH, max_lines: number = _MAX_WINDOW_LINES, credential_values?: Set<string>): Record<string, number> {
  const [index, shard_texts] = build_method_reference_window(data, max_lines);
  const index_text = render_json(index);
  let values = credential_values;
  if (values === undefined) {
    const { MirrorCredentialLiteralError, mirror_credential_literals } = require("../case_compiler/credential_literals") as any;
    try {
      values = new Set(mirror_credential_literals());
    } catch (exc) {
      throw new WindowedProjectionError("credential literal closure is unavailable");
    }
  }
  const valueSet = new Set([...values].filter((v) => v));
  if (!valueSet.size) {
    throw new WindowedProjectionError("credential literal closure is empty");
  }
  const { matching_credential_literal_count } = require("../case_compiler/credential_literals") as any;
  const matches = [index_text, ...Object.values(shard_texts)].reduce((sum, text) => sum + matching_credential_literal_count(text, valueSet), 0);
  if (matches) {
    throw new WindowedProjectionError(`refusing to write method_reference projection with credential literal matches (count=${matches})`);
  }
  const shard_dir = path.join(path.dirname(index_path), _SHARD_DIR_NAME);
  fs.mkdirSync(shard_dir, { recursive: true });
  const expected_paths = new Set(Object.keys(shard_texts).map((rel) => _resolve_shard_path(index_path, rel)));
  const stale_paths = _owned_stale_shards(index_path, shard_dir, expected_paths);
  for (const [relPath, text] of Object.entries(shard_texts)) {
    _atomic_write(_resolve_shard_path(index_path, relPath), text);
  }
  _atomic_write(index_path, index_text);
  for (const stale of stale_paths) {
    fs.unlinkSync(stale);
  }
  return { index_lines: index_text.split(/\r?\n/).length - 1, shard_count: Object.keys(shard_texts).length };
}
