import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { P as Path } from "../../_py";
import { DENIED_668_AUTOIDS, POISON_RULE_ID, classify_package, package_rejection } from "../../case_compiler/package_advisories";
import { atomic_write_bytes_nofollow } from "../../case_compiler/_sealed_io";
import { steps_from_xlsx } from "../tools/device/structural_gate";

const _FILENAME_RE = /^verified_(\d{18})\.xlsx$/;
const _MAX_WORKBOOK_BYTES = 128 * 1024 * 1024;

export class VerifiedCorpusError extends Error {
  reason_code: string;
  constructor(message?: string, opts: { reason_code?: string } = {}) {
    super(message);
    this.name = "VerifiedCorpusError";
    this.reason_code = opts.reason_code ?? "verified_corpus_io_unsafe";
  }
}

export interface Candidate {
  path: Path;
  source: string;
  autoid: string;
  sha256: string;
  eligible: boolean;
  reason: string;
}

export interface CorpusInspection {
  active_count: number;
  legacy_count: number;
  incompatible_count: number;
  issues: string[];
  status: string;
}

export function canonical_root(project_root: Path): Path {
  return project_root.join("knowledge/framework/verified");
}

export function legacy_root(project_root: Path): Path {
  return project_root.join("knowledge/framework/mirror");
}

export function provenance_path(project_root: Path): Path {
  return project_root.join("knowledge/framework/mirror_precedent_provenance.json");
}

function _load_object(path_: Path): Record<string, any> {
  try {
    const value = JSON.parse(path_.read_text("utf-8"));
    return typeof value === "object" && value !== null && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function _deny_projection(project_root: Path): Record<string, any> {
  const projection = _load_object(project_root.join("knowledge/data/compile_ref/package_advisories_10.5.json"));
  const records = projection.records;
  if (typeof records !== "object" || records === null || Array.isArray(records)) {
    return { records: {} };
  }
  return projection;
}

function _regular_digest(path_: Path): string {
  const info = path_.lstat();
  if (!info.isFile() || Number(info.nlink) !== 1 || Number(info.size) <= 0 || Number(info.size) > _MAX_WORKBOOK_BYTES) {
    throw new Error("unsafe_file_identity");
  }
  const digest = crypto.createHash("sha256");
  const fd = fs.openSync(path_.toString(), "r");
  try {
    const buf = Buffer.alloc(1024 * 1024);
    while (true) {
      const n = fs.readSync(fd, buf, 0, buf.length, null);
      if (n <= 0) break;
      digest.update(buf.subarray(0, n));
    }
  } finally {
    fs.closeSync(fd);
  }
  const after = path_.lstat();
  if (
    Number(after.dev) !== Number(info.dev) ||
    Number(after.ino) !== Number(info.ino) ||
    Number(after.size) !== Number(info.size) ||
    Number(after.mtimeMs) !== Number(info.mtimeMs) ||
    !after.isFile() ||
    Number(after.nlink) !== 1
  ) {
    throw new Error("file_changed_while_reading");
  }
  return digest.digest("hex");
}

function _candidate(path_: Path, opts: { source: string; provenance: Record<string, any>; deny_projection: Record<string, any> }): Candidate {
  const match = _FILENAME_RE.exec(path_.name);
  if (match === null) {
    return { path: path_, source: opts.source, autoid: "", sha256: "", eligible: false, reason: "invalid_filename" };
  }
  const autoid = match[1];
  let digest = "";
  try {
    digest = _regular_digest(path_);
    const [workbook_autoid, steps] = steps_from_xlsx(path_.toString());
    if (String(workbook_autoid ?? "") !== autoid || !steps) {
      throw new Error("workbook_identity_mismatch");
    }
  } catch (exc: any) {
    return { path: path_, source: opts.source, autoid, sha256: "", eligible: false, reason: exc instanceof Error ? exc.message : String(exc) };
  }
  const denied = package_rejection({ autoid, sha256: digest, asset_id: path_.name, projection: opts.deny_projection });
  if (denied || DENIED_668_AUTOIDS.has(autoid)) {
    const rule_match = /rule_id=(\S+)/.exec(String(denied ?? ""));
    return { path: path_, source: opts.source, autoid, sha256: digest, eligible: false, reason: rule_match ? rule_match[1] : POISON_RULE_ID };
  }
  let live: Record<string, any> = {};
  try {
    live = classify_package(path_.toString(), opts.provenance);
  } catch {}
  const prior = (opts.deny_projection.records ?? {})[path_.name];
  const prior_certified = Boolean(
    typeof prior === "object" &&
      prior !== null &&
      prior.status === "certified" &&
      !(prior.deny_rules ?? []).includes(POISON_RULE_ID) &&
      (prior.sha256_aliases ?? []).map((v: any) => String(v).toLowerCase()).includes(digest) &&
      (prior.autoids ?? []).map((v: any) => String(v)).includes(autoid)
  );
  if (live.status !== "certified" && !prior_certified) {
    return { path: path_, source: opts.source, autoid, sha256: digest, eligible: false, reason: "certified_delivery_identity_missing" };
  }
  return { path: path_, source: opts.source, autoid, sha256: digest, eligible: true, reason: "" };
}

function _paths(root: Path, opts: { include_unexpected: boolean }): Path[] {
  if (!root.exists()) return [];
  if (root.is_symlink() || !root.is_dir()) {
    throw new VerifiedCorpusError("verified corpus root is unsafe", { reason_code: "verified_corpus_root_unsafe" });
  }
  if (opts.include_unexpected) {
    return root.iterdir().sort((a: any, b: any) => a.name.localeCompare(b.name));
  }
  return root.glob("verified_*.xlsx").sort((a: any, b: any) => a.name.localeCompare(b.name));
}

export function inspect_verified_corpus(project_root: Path): CorpusInspection {
  project_root = new Path(project_root.toString());
  const provenance = _load_object(provenance_path(project_root));
  const projection = _deny_projection(project_root);
  const active_paths = _paths(canonical_root(project_root), { include_unexpected: true });
  const legacy_paths = _paths(legacy_root(project_root), { include_unexpected: false });
  const issues: string[] = [];
  let active = 0;
  let incompatible = 0;
  for (const path_ of active_paths) {
    const item = _candidate(path_, { source: "active", provenance, deny_projection: projection });
    if (item.eligible) {
      active += 1;
    } else {
      incompatible += 1;
      issues.push(`active:${path_.name}:${item.reason}`);
    }
  }
  if (legacy_paths.length) {
    issues.push(`legacy:${legacy_paths.length}`);
  }
  const status = issues.length ? "incompatible" : active ? "ready" : "unavailable";
  return { active_count: active, legacy_count: legacy_paths.length, incompatible_count: incompatible, issues, status };
}

function _quarantine_target(quarantine: Path, item: Candidate, opts: { reason: string }): Path {
  const digest = item.sha256 ? item.sha256.slice(0, 16) : "unsafe";
  const safe_reason = opts.reason.replace(/[^a-zA-Z0-9_-]+/g, "_").slice(0, 48) || "invalid";
  const base = `${item.path.name}.${item.source}.${safe_reason}.${digest}`;
  let target = quarantine.join(base);
  let counter = 1;
  while (target.exists() || target.is_symlink()) {
    target = quarantine.join(`${base}.${counter}`);
    counter += 1;
  }
  return target;
}

function _move_to_quarantine(item: Candidate, quarantine: Path, opts: { reason: string }): string {
  const target = _quarantine_target(quarantine, item, opts);
  fs.renameSync(item.path.toString(), target.toString());
  return target.name;
}

function _write_receipt(path_: Path, payload: Record<string, any>): void {
  const raw = Buffer.from(JSON.stringify(payload, null, 2) + "\n", "utf8");
  atomic_write_bytes_nofollow(path_.toString(), raw, {
    errorType: VerifiedCorpusError,
    invalid_message: "verified corpus receipt path is invalid",
    unavailable_message: "verified corpus receipt cannot be published",
    create_parents: true,
    mode: 0o600,
  });
}

export function converge_verified_corpus(project_root: Path): Record<string, any> {
  project_root = new Path(project_root.toString());
  const active_root = canonical_root(project_root);
  const legacy = legacy_root(project_root);
  if (active_root.exists() && (active_root.is_symlink() || !active_root.is_dir())) {
    throw new VerifiedCorpusError("verified corpus root is unsafe", { reason_code: "verified_corpus_root_unsafe" });
  }
  active_root.mkdir({ parents: true, exist_ok: true, mode: 0o700 });
  const quarantine = project_root.join("runtime/quarantine/verified_packages");
  if (quarantine.exists() && (quarantine.is_symlink() || !quarantine.is_dir())) {
    throw new VerifiedCorpusError("verified corpus quarantine root is unsafe", { reason_code: "verified_corpus_quarantine_unsafe" });
  }
  quarantine.mkdir({ parents: true, exist_ok: true, mode: 0o700 });
  const provenance = _load_object(provenance_path(project_root));
  const projection = _deny_projection(project_root);
  const active_items: Record<string, Candidate> = {};
  for (const path_ of _paths(active_root, { include_unexpected: true })) {
    active_items[path_.name] = _candidate(path_, { source: "active", provenance, deny_projection: projection });
  }
  const legacy_items: Record<string, Candidate> = {};
  for (const path_ of _paths(legacy, { include_unexpected: false })) {
    legacy_items[path_.name] = _candidate(path_, { source: "legacy", provenance, deny_projection: projection });
  }
  const events: Record<string, string>[] = [];
  const names = new Set([...Object.keys(active_items), ...Object.keys(legacy_items)]);
  for (const name of [...names].sort()) {
    const current = active_items[name];
    const old = legacy_items[name];
    if (current !== undefined && old !== undefined) {
      if (current.eligible && old.eligible && current.sha256 === old.sha256) {
        old.path.unlink();
        events.push({ file: name, action: "deduplicated", reason: "same_bytes" });
        continue;
      }
      if (current.eligible && !old.eligible) {
        const target = _move_to_quarantine(old, quarantine, { reason: old.reason });
        events.push({ file: name, action: "quarantined_legacy", reason: old.reason, target });
        continue;
      }
      if (old.eligible && !current.eligible) {
        const target = _move_to_quarantine(current, quarantine, { reason: current.reason });
        fs.renameSync(old.path.toString(), active_root.join(name).toString());
        events.push(
          { file: name, action: "quarantined_active", reason: current.reason, target },
          { file: name, action: "migrated", reason: "certified_legacy" }
        );
        continue;
      }
      for (const item of [current, old]) {
        const reason = item.eligible ? "identity_collision" : item.reason;
        const target = _move_to_quarantine(item, quarantine, { reason });
        events.push({ file: name, action: `quarantined_${item.source}`, reason, target });
      }
      continue;
    }
    const item = current ?? old;
    if (item === undefined) continue;
    if (!item.eligible) {
      const target = _move_to_quarantine(item, quarantine, { reason: item.reason });
      events.push({ file: name, action: `quarantined_${item.source}`, reason: item.reason, target });
    } else if (item.source === "legacy") {
      fs.renameSync(item.path.toString(), active_root.join(name).toString());
      events.push({ file: name, action: "migrated", reason: "certified_legacy" });
    }
  }
  const inspection = inspect_verified_corpus(project_root);
  if (inspection.issues.length) {
    throw new VerifiedCorpusError("verified corpus remained incompatible after convergence", { reason_code: "verified_corpus_not_converged" });
  }
  const receipt = {
    schema: "ist.verified-corpus-convergence",
    active_root: "knowledge/framework/verified",
    legacy_root: "knowledge/framework/mirror",
    status: inspection.status,
    active_count: inspection.active_count,
    events,
  };
  _write_receipt(quarantine.join("last_convergence.json"), receipt);
  return receipt;
}
