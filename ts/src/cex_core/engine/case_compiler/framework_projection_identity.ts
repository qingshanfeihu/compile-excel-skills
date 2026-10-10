import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";
import { canonical_json, read_regular_nofollow, sha256_bytes, validate_json_budget } from "./_sealed_io";

_cex_set_caller("cex_core.engine.case_compiler.framework_projection_identity");

export const IDENTITY_SCHEMA = "ist.framework-mirror-source-identity";
export const IDENTITY_SCOPE = "framework_sync:lib-tree+smoke-test-conftest";
export const ATTRIBUTION_BINDING_SCHEMA = "ist.attribution-framework-projection-binding";
const _INDEX_FORMAT = "method-reference-windowed-index-v1";
const _SHARD_FORMAT = "method-reference-windowed-shard-v1";
const _HASH_RE = /^[0-9a-f]{64}$/;
export const FRAMEWORK_PROJECTION_SOURCE_PATHS = [
  "lib/test_xlsx.py", "lib/apv/apv.py", "lib/apv/apv_ssh.py", "lib/apv/clear.py", "lib/apv/ssl_comm.py",
  "lib/apv/seg_comm.py", "lib/apv/ha_comm.py", "lib/apv/preparation.py", "lib/apv/apv_action.py",
  "lib/apv/apv_synonyms", "lib/dic_operation.py", "lib/client_action.py", "lib/client_synonyms",
  "lib/env.py", "lib/check_point.py", "lib/ssh_server.py", "smoke_test/conftest.py",
];
const _REQUIRED_SOURCE_PATHS = new Set(FRAMEWORK_PROJECTION_SOURCE_PATHS);

export class FrameworkProjectionIdentityError extends Error {
  detail: string;
  reason_code: string;
  constructor(detail: string, reason_code: string) {
    super(detail);
    this.detail = detail;
    this.reason_code = reason_code;
  }
}

class _SealedReadError extends Error {}

function _raise(detail: string, reasonCode: string): never {
  throw new FrameworkProjectionIdentityError(detail, reasonCode);
}

function _sealedBytes(p: string, opts: { trusted_root: string; max_bytes: number; label: string; min_bytes?: number }): Buffer {
  try {
    return read_regular_nofollow(p, {
      errorType: _SealedReadError,
      invalid_message: `${opts.label} path is invalid`,
      directory_message: `${opts.label} parent is unavailable`,
      open_message: `${opts.label} is unavailable`,
      bounds_message: `${opts.label} exceeds its sealed size boundary`,
      changed_message: `${opts.label} changed while being read`,
      max_bytes: opts.max_bytes,
      min_bytes: opts.min_bytes ?? 0,
      trusted_root: opts.trusted_root,
    }) as Buffer;
  } catch (exc) {
    if (exc instanceof _SealedReadError) {
      _raise(exc.message, "framework_projection_identity_unavailable");
    }
    throw exc;
  }
}

function _sealedJson(p: string, opts: { trusted_root: string; max_bytes: number; label: string }): [Record<string, any>, Buffer] {
  const raw = _sealedBytes(p, { ...opts, min_bytes: 2 });
  let payload: any;
  try {
    validate_json_budget(raw, {
      errorType: _SealedReadError,
      message: `${opts.label} exceeds its JSON structure boundary`,
      maxDepth: 64,
      maxTokens: 250000,
    });
    payload = JSON.parse(raw.toString("utf8"));
  } catch {
    _raise(`${opts.label} is not a valid bounded JSON object`, "framework_projection_identity_unavailable");
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    _raise(`${opts.label} is not a JSON object`, "framework_projection_identity_incomplete");
  }
  return [payload, raw];
}

function _safeRelative(value: string): boolean {
  if (!value || path.posix.isAbsolute(value)) return false;
  const parts = value.split("/");
  return parts.every((part) => part !== "" && part !== "." && part !== "..") && value.split(path.sep).join("/") === value;
}

function _inFrameworkScope(relative: string): boolean {
  return _safeRelative(relative) && (relative.startsWith("lib/") || relative === "smoke_test/conftest.py");
}

function _validateSyncMeta(payload: Record<string, any>): [Record<string, any>, string] {
  const byPath = payload.by_path;
  const syncedAt = payload.synced_at;
  if (payload.version !== 1 || typeof byPath !== "object" || byPath === null || Array.isArray(byPath) || typeof syncedAt !== "string" || !syncedAt.trim()) {
    _raise("framework sync receipt is incomplete", "framework_projection_identity_incomplete");
  }
  return [byPath, syncedAt];
}

export function build_framework_source_identity(mirror_root: string): Record<string, any> {
  const mirrorRoot = String(mirror_root);
  const [syncMeta, syncRaw] = _sealedJson(path.join(mirrorRoot, ".sync_meta.json"), {
    trusted_root: mirrorRoot,
    max_bytes: 16 * 1024 * 1024,
    label: "framework sync receipt",
  });
  const [byPath, syncedAt] = _validateSyncMeta(syncMeta);
  const scoped: Record<string, string> = {};
  for (const [rawRelative, rawDigest] of Object.entries(byPath)) {
    if (typeof rawRelative !== "string") {
      _raise("framework sync receipt contains a non-string source path", "framework_projection_identity_incomplete");
    }
    if (rawRelative.startsWith("lib/") && !_safeRelative(rawRelative)) {
      _raise("framework sync receipt contains an unsafe library source path", "framework_projection_identity_incomplete");
    }
    if (!_inFrameworkScope(rawRelative)) {
      continue;
    }
    if (typeof rawDigest !== "string" || !_HASH_RE.test(rawDigest)) {
      _raise("framework sync receipt contains an invalid source digest", "framework_projection_identity_incomplete");
    }
    scoped[rawRelative] = rawDigest;
  }
  const missing = [..._REQUIRED_SOURCE_PATHS].filter((p) => !(p in scoped)).sort();
  if (missing.length) {
    _raise("framework sync receipt is missing required projection sources: " + missing.join(", "), "framework_projection_identity_incomplete");
  }
  const observed: Record<string, string> = {};
  for (const relative of Object.keys(scoped).sort()) {
    const expected = scoped[relative];
    const raw = _sealedBytes(path.join(mirrorRoot, relative), {
      trusted_root: mirrorRoot,
      max_bytes: 64 * 1024 * 1024,
      label: "framework projection source",
    });
    const actual = sha256_bytes(raw);
    if (actual !== expected) {
      _raise(`framework projection source drifted from sync receipt: ${relative}`, "framework_projection_identity_stale");
    }
    observed[relative] = actual;
  }
  const canonical = canonical_json(observed, { ensure_ascii: true });
  return {
    schema: IDENTITY_SCHEMA,
    scope: IDENTITY_SCOPE,
    complete: true,
    synced_at: syncedAt,
    sync_receipt_sha256: sha256_bytes(syncRaw),
    snapshot_sha256: sha256_bytes(canonical),
    source_count: Object.keys(observed).length,
    source_hashes: observed,
  };
}

function _safeShardPath(compileRefRoot: string, rawPath: string): string {
  if (!_safeRelative(rawPath)) {
    _raise("method-reference index contains an unsafe shard path", "framework_projection_identity_incomplete");
  }
  const parts = rawPath.split("/");
  if (parts.length !== 2 || parts[0] !== "method_reference" || !parts[1].startsWith("shard-") || !parts[1].endsWith(".json")) {
    _raise("method-reference index points outside its shard namespace", "framework_projection_identity_incomplete");
  }
  return path.join(compileRefRoot, parts[0], parts[1]);
}

function _loadWindowedProjection(compileRefRoot: string): [Record<string, any>, string] {
  const [index] = _sealedJson(path.join(compileRefRoot, "method_reference.json"), {
    trusted_root: compileRefRoot,
    max_bytes: 512 * 1024,
    label: "method-reference index",
  });
  const indexMeta = index._meta;
  const sections = index.sections;
  if (
    typeof indexMeta !== "object" || indexMeta === null || Array.isArray(indexMeta) ||
    indexMeta.format !== _INDEX_FORMAT ||
    typeof indexMeta.source_sha256 !== "string" ||
    !_HASH_RE.test(String(indexMeta.source_sha256)) ||
    !Array.isArray(sections) || !sections.length
  ) {
    _raise("method-reference index identity is incomplete", "framework_projection_identity_incomplete");
  }
  const sourceSha = String(indexMeta.source_sha256);
  const rebuilt: Record<string, any> = {};
  for (const section of sections) {
    if (typeof section !== "object" || section === null || Array.isArray(section)) {
      _raise("method-reference index contains an invalid section", "framework_projection_identity_incomplete");
    }
    const name = section.name;
    const container = section.container;
    const descriptors = section.shards;
    if (
      typeof name !== "string" || name in rebuilt ||
      !["mapping", "sequence", "scalar"].includes(container) ||
      !Array.isArray(descriptors) || !descriptors.length
    ) {
      _raise("method-reference index section identity is incomplete", "framework_projection_identity_incomplete");
    }
    let value: any = container === "mapping" ? {} : container === "sequence" ? [] : null;
    let scalarSeen = false;
    for (const descriptor of descriptors) {
      if (typeof descriptor !== "object" || descriptor === null || Array.isArray(descriptor) || typeof descriptor.path !== "string") {
        _raise("method-reference shard descriptor is incomplete", "framework_projection_identity_incomplete");
      }
      const shardPath = _safeShardPath(compileRefRoot, String(descriptor.path));
      const [shard] = _sealedJson(shardPath, {
        trusted_root: compileRefRoot,
        max_bytes: 2 * 1024 * 1024,
        label: "method-reference shard",
      });
      const shardMeta = shard._meta;
      const entries = shard.entries;
      if (
        typeof shardMeta !== "object" || shardMeta === null || Array.isArray(shardMeta) ||
        shardMeta.format !== _SHARD_FORMAT ||
        shardMeta.section !== name ||
        shardMeta.container !== container ||
        shardMeta.source_sha256 !== sourceSha
      ) {
        _raise("method-reference shard identity does not match its index", "framework_projection_identity_incomplete");
      }
      if (container === "mapping") {
        if (typeof entries !== "object" || entries === null || Array.isArray(entries) || Object.keys(value).some((k) => k in entries)) {
          _raise("method-reference mapping shard is invalid", "framework_projection_identity_incomplete");
        }
        Object.assign(value, entries);
      } else if (container === "sequence") {
        if (!Array.isArray(entries)) {
          _raise("method-reference sequence shard is invalid", "framework_projection_identity_incomplete");
        }
        value.push(...entries);
      } else {
        if (scalarSeen) {
          _raise("method-reference scalar section is split", "framework_projection_identity_incomplete");
        }
        value = entries;
        scalarSeen = true;
      }
    }
    rebuilt[name] = value;
  }
  const rendered = Buffer.from(JSON.stringify(rebuilt, null, 2) + "\n", "utf8");
  if (sha256_bytes(rendered) !== sourceSha) {
    _raise("method-reference shards do not reconstruct the indexed projection", "framework_projection_identity_incomplete");
  }
  return [rebuilt, sourceSha];
}

function _validateRecordedIdentity(identity: any): Record<string, any> {
  if (typeof identity !== "object" || identity === null || Array.isArray(identity)) {
    _raise("method-reference projection has no framework source identity", "framework_projection_identity_incomplete");
  }
  const hashes = identity.source_hashes;
  if (
    identity.schema !== IDENTITY_SCHEMA ||
    identity.scope !== IDENTITY_SCOPE ||
    identity.complete !== true ||
    typeof identity.synced_at !== "string" ||
    typeof identity.sync_receipt_sha256 !== "string" ||
    !_HASH_RE.test(String(identity.sync_receipt_sha256)) ||
    typeof identity.snapshot_sha256 !== "string" ||
    !_HASH_RE.test(String(identity.snapshot_sha256)) ||
    typeof hashes !== "object" || hashes === null || Array.isArray(hashes) || !Object.keys(hashes).length ||
    identity.source_count !== Object.keys(hashes).length
  ) {
    _raise("method-reference framework source identity is incomplete", "framework_projection_identity_incomplete");
  }
  if (![..._REQUIRED_SOURCE_PATHS].every((p) => p in hashes)) {
    _raise("method-reference framework source identity omits required sources", "framework_projection_identity_incomplete");
  }
  for (const [relative, digest] of Object.entries(hashes)) {
    if (typeof relative !== "string" || !_inFrameworkScope(relative) || typeof digest !== "string" || !_HASH_RE.test(digest)) {
      _raise("method-reference framework source identity contains an invalid entry", "framework_projection_identity_incomplete");
    }
  }
  if (sha256_bytes(canonical_json(hashes, { ensure_ascii: true })) !== identity.snapshot_sha256) {
    _raise("method-reference framework source identity snapshot digest is invalid", "framework_projection_identity_incomplete");
  }
  return identity;
}

const _SYNC_PROVENANCE_FIELDS = new Set(["synced_at", "sync_receipt_sha256"]);

function _contentIdentity(identity: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries(identity)) {
    if (!_SYNC_PROVENANCE_FIELDS.has(k)) {
      out[k] = v;
    }
  }
  return out;
}

function _validatedAttributionProjection(projectRoot?: string | null): [Record<string, any>, string] {
  const root = projectRoot != null ? String(projectRoot) : _cex_data_path("");
  const [projection, projectionSha256] = _loadWindowedProjection(path.join(root, "knowledge/data/compile_ref"));
  const projectionMeta = projection._meta;
  if (typeof projectionMeta !== "object" || projectionMeta === null || Array.isArray(projectionMeta)) {
    _raise("method-reference projection metadata is incomplete", "framework_projection_identity_incomplete");
  }
  const recorded = _validateRecordedIdentity(projectionMeta.framework_source_identity);
  const current = build_framework_source_identity(path.join(root, "knowledge/framework/mirror"));
  if (JSON.stringify(_contentIdentity(recorded)) !== JSON.stringify(_contentIdentity(current))) {
    const detail =
      JSON.stringify(Object.keys(recorded.source_hashes || {}).sort()) !== JSON.stringify(Object.keys(current.source_hashes || {}).sort())
        ? "method-reference projection source closure differs from the current framework mirror"
        : "method-reference projection source hashes differ from the current framework mirror";
    _raise(detail, "framework_projection_identity_stale");
  }
  return [{ ...recorded }, projectionSha256];
}

export function attribution_projection_binding(identity: Record<string, any>, opts: { method_reference_sha256: string }): Record<string, string> {
  if (!_HASH_RE.test(String(opts.method_reference_sha256 || ""))) {
    _raise("method-reference projection digest is unavailable", "framework_projection_identity_incomplete");
  }
  const recorded = _validateRecordedIdentity({ ...identity });
  return {
    schema: ATTRIBUTION_BINDING_SCHEMA,
    identity_sha256: sha256_bytes(canonical_json(recorded, { ensure_ascii: true })),
    sync_receipt_sha256: String(recorded.sync_receipt_sha256),
    framework_snapshot_sha256: String(recorded.snapshot_sha256),
    method_reference_sha256: String(opts.method_reference_sha256),
  };
}

export function validate_attribution_projection_identity(project_root?: string | null): Record<string, any> {
  const [recorded] = _validatedAttributionProjection(project_root);
  return recorded;
}

export function validate_attribution_projection_binding(project_root?: string | null): Record<string, string> {
  const [recorded, projectionSha256] = _validatedAttributionProjection(project_root);
  return attribution_projection_binding(recorded, { method_reference_sha256: projectionSha256 });
}
