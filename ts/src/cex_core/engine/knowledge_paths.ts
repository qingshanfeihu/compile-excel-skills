import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "./_root";
import { read_regular_nofollow, validate_json_budget, open_directory_nofollow } from "./case_compiler/_sealed_io";
import { accepts_schema } from "./common/schema_identity";

_cex_set_caller("cex_core.engine.knowledge_paths");

let _currentUsername = "";

export const MAIN_DIR = _cex_data_path("main");
export const PROJECT_ROOT = path.dirname(MAIN_DIR);
export const KNOWLEDGE_ROOT = path.join(PROJECT_ROOT, "knowledge");
export const KNOWLEDGE_DATA_ROOT = path.join(KNOWLEDGE_ROOT, "data");
export const KNOWLEDGE_INTERMEDIATE = path.join(KNOWLEDGE_ROOT, ".intermediate");
export const KNOWLEDGE_ORGIN = path.join(KNOWLEDGE_DATA_ROOT, "orgin");
export const ORGIN_WORKDIR_NAME = "_pdf_splits";

function _isSkippedDir(name: string): boolean {
  return name.startsWith(".") || name === ORGIN_WORKDIR_NAME;
}

export function* iter_orgin_files(orgin_dir?: string | null): Generator<string> {
  const root = orgin_dir != null ? path.resolve(String(orgin_dir)) : KNOWLEDGE_ORGIN;
  if (!fs.existsSync(root)) {
    return;
  }
  function* _walk(d: string): Generator<string> {
    const children = fs.readdirSync(d, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    for (const child of children) {
      const full = path.join(d, child.name);
      if (child.isDirectory()) {
        if (_isSkippedDir(child.name)) continue;
        yield* _walk(full);
      } else if (child.isFile()) {
        if (child.name.startsWith(".")) continue;
        yield full;
      }
    }
  }
  yield* _walk(root);
}

export function orgin_rel_key(p: string, orgin_dir?: string | null): string {
  const root = orgin_dir != null ? path.resolve(String(orgin_dir)) : KNOWLEDGE_ORGIN;
  const pp = path.resolve(String(p));
  const rel = path.relative(root, pp);
  if (!rel.startsWith("..") && !path.isAbsolute(rel)) {
    return rel.split(path.sep).join("/");
  }
  return path.basename(pp);
}

export const KNOWLEDGE_MARKDOWN = path.join(KNOWLEDGE_DATA_ROOT, "markdown");
export const KNOWLEDGE_MARKDOWN_PRODUCT = path.join(KNOWLEDGE_MARKDOWN, "product");
export const KNOWLEDGE_MARKDOWN_QA = path.join(KNOWLEDGE_MARKDOWN, "qa");
export const KNOWLEDGE_MANUAL = path.join(KNOWLEDGE_DATA_ROOT, "manual");
export const KNOWLEDGE_SPEC = path.join(KNOWLEDGE_DATA_ROOT, "spec");
export const KNOWLEDGE_SPEC_GENERATIONS = path.join(KNOWLEDGE_SPEC, "generations");
export const KNOWLEDGE_SPEC_ACTIVE = path.join(KNOWLEDGE_SPEC, "active.json");
export const SPEC_GENERATION_SCHEMA = "ist.spec.generation";
export const SPEC_ACTIVE_SCHEMA = "ist.spec.active";
const _SPEC_POINTER_MAX_BYTES = 64 * 1024;
const _SPEC_MANIFEST_MAX_BYTES = 16 * 1024 * 1024;
const _SPEC_ARTIFACT_MAX_BYTES = 16 * 1024 * 1024;
const _SPEC_DOC_MAX_BYTES = 16 * 1024 * 1024;
const _GENERATION_ID_RE = /^[0-9]{20}-[0-9a-f]{16}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;

export class SpecGenerationUnavailable extends Error {}

export function spec_generation_age_seconds(generation_id: string, now_ns?: bigint | number | null): [boolean, number | null] {
  const gid = String(generation_id || "");
  if (!_GENERATION_ID_RE.test(gid)) {
    return [false, null];
  }
  let builtNs: bigint;
  try {
    builtNs = BigInt(gid.slice(0, 20));
  } catch {
    return [false, null];
  }
  const clock = now_ns == null ? process.hrtime.bigint() : BigInt(now_ns);
  let ageS = (clock - builtNs) / 1000000000n;
  if (ageS < 0n) {
    ageS = 0n;
  }
  return [true, Number(ageS)];
}

export interface ActiveSpecGeneration {
  generation_id: string;
  root: string;
  docs: string;
  state: string;
  index: string;
  manifest: string;
  manifest_sha256: string;
  document_entries: Record<string, { size: number; sha256: string }>;
}

export function spec_store_root(project_root?: string | null): string {
  if (project_root == null) {
    return KNOWLEDGE_SPEC;
  }
  return path.join(String(project_root), "knowledge", "data", "spec");
}

function _readSpecJson(p: string, label: string, maxBytes: number): [Buffer, Record<string, any>] {
  let value: any;
  let raw: Buffer;
  try {
    raw = read_regular_nofollow(p, {
      errorType: SpecGenerationUnavailable,
      invalid_message: `${label}路径无效`,
      directory_message: `${label}目录不可安全读取`,
      open_message: `${label}不可读`,
      bounds_message: `${label}超出大小限制`,
      changed_message: `${label}读取期间发生变化`,
      max_bytes: maxBytes,
      min_bytes: 2,
    }) as Buffer;
    validate_json_budget(raw, { errorType: SpecGenerationUnavailable, message: `${label}结构超出限制` });
    value = JSON.parse(raw.toString("utf8"));
  } catch (exc) {
    if (exc instanceof SpecGenerationUnavailable) throw exc;
    throw new SpecGenerationUnavailable(`${label}不是有效 JSON`);
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new SpecGenerationUnavailable(`${label}结构无效`);
  }
  return [raw, value];
}

function _validateManifestEntry(value: any, label: string, maxBytes: number): [number, string] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new SpecGenerationUnavailable(`${label}清单项无效`);
  }
  const size = value.size;
  const digest = String(value.sha256 || "");
  if (typeof size !== "number" || !Number.isInteger(size) || size < 1 || size > maxBytes || !_SHA256_RE.test(digest)) {
    throw new SpecGenerationUnavailable(`${label}清单项无效`);
  }
  return [size, digest];
}

function _verifyGenerationFile(p: string, label: string, expected: any, maxBytes: number): void {
  const [size, digest] = _validateManifestEntry(expected, label, maxBytes);
  const payload = read_regular_nofollow(p, {
    errorType: SpecGenerationUnavailable,
    invalid_message: `${label}路径无效`,
    directory_message: `${label}目录不可安全读取`,
    open_message: `${label}不可读`,
    bounds_message: `${label}超出大小限制`,
    changed_message: `${label}读取期间发生变化`,
    max_bytes: maxBytes,
    min_bytes: 1,
  }) as Buffer;
  if (payload.length !== size || crypto.createHash("sha256").update(payload).digest("hex") !== digest) {
    throw new SpecGenerationUnavailable(`${label}与活动代际清单不一致`);
  }
}

function _sealedDirectoryEntries(p: string, label: string): Map<string, fs.Stats> {
  const dir = open_directory_nofollow(p, {
    errorType: SpecGenerationUnavailable,
    invalid_message: `${label}路径无效`,
    unavailable_message: `${label}不可安全读取`,
  });
  const out = new Map<string, fs.Stats>();
  for (const name of fs.readdirSync(dir)) {
    out.set(name, fs.lstatSync(path.join(dir, name)));
  }
  return out;
}

export function resolve_active_spec_generation(
  project_root?: string | null,
  opts: { store_root?: string | null; verify_documents?: boolean } = {}
): ActiveSpecGeneration {
  const storeRoot = opts.store_root ?? null;
  const verifyDocuments = opts.verify_documents ?? true;
  const store = storeRoot != null ? path.resolve(String(storeRoot)) : spec_store_root(project_root);
  const pointerPath = path.join(store, "active.json");
  const [, pointer] = _readSpecJson(pointerPath, "规格书活动指针", _SPEC_POINTER_MAX_BYTES);
  const generationId = String(pointer.generation_id || "");
  const expectedManifestSha = String(pointer.manifest_sha256 || "");
  if (
    !accepts_schema(pointer.schema, SPEC_ACTIVE_SCHEMA) ||
    !_GENERATION_ID_RE.test(generationId) ||
    !_SHA256_RE.test(expectedManifestSha) ||
    Object.keys(pointer).sort().join(",") !== "generation_id,manifest_sha256,schema"
  ) {
    throw new SpecGenerationUnavailable("规格书活动指针结构无效");
  }
  const generationRoot = path.join(store, "generations", generationId);
  const manifestPath = path.join(generationRoot, "manifest.json");
  const [manifestRaw, manifest] = _readSpecJson(manifestPath, "规格书代际清单", _SPEC_MANIFEST_MAX_BYTES);
  if (crypto.createHash("sha256").update(manifestRaw).digest("hex") !== expectedManifestSha) {
    throw new SpecGenerationUnavailable("规格书活动指针与代际清单不一致");
  }
  if (
    !accepts_schema(manifest.schema, SPEC_GENERATION_SCHEMA) ||
    manifest.generation_id !== generationId ||
    typeof manifest.created_at !== "string" ||
    !manifest.created_at ||
    Object.keys(manifest).sort().join(",") !== "artifacts,created_at,documents,generation_id,schema"
  ) {
    throw new SpecGenerationUnavailable("规格书代际清单结构无效");
  }
  const artifacts = manifest.artifacts;
  const documents = manifest.documents;
  if (
    typeof artifacts !== "object" || artifacts === null || Array.isArray(artifacts) ||
    Object.keys(artifacts).sort().join(",") !== "index.json,state.tsv" ||
    typeof documents !== "object" || documents === null || Array.isArray(documents)
  ) {
    throw new SpecGenerationUnavailable("规格书代际清单结构无效");
  }
  const statePath = path.join(generationRoot, "state.tsv");
  const indexPath = path.join(generationRoot, "index.json");
  const docsPath = path.join(generationRoot, "docs");
  _verifyGenerationFile(statePath, "规格书同步台账", artifacts["state.tsv"], _SPEC_ARTIFACT_MAX_BYTES);
  _verifyGenerationFile(indexPath, "规格书索引", artifacts["index.json"], _SPEC_ARTIFACT_MAX_BYTES);
  const normalizedDocs: Record<string, { size: number; sha256: string }> = {};
  const casefoldNames = new Set<string>();
  for (const name of Object.keys(documents)) {
    const entry = documents[name];
    if (
      typeof name !== "string" || !name.endsWith(".md") || path.basename(name) !== name ||
      casefoldNames.has(name.toLowerCase())
    ) {
      throw new SpecGenerationUnavailable("规格书代际文档名无效");
    }
    const [size, digest] = _validateManifestEntry(entry, "规格书文档", _SPEC_DOC_MAX_BYTES);
    normalizedDocs[name] = { size, sha256: digest };
    casefoldNames.add(name.toLowerCase());
    if (verifyDocuments) {
      _verifyGenerationFile(path.join(docsPath, name), "规格书文档", entry, _SPEC_DOC_MAX_BYTES);
    }
  }
  const rootEntries = _sealedDirectoryEntries(generationRoot, "规格书代际目录");
  if (Array.from(rootEntries.keys()).sort().join(",") !== "docs,index.json,manifest.json,state.tsv") {
    throw new SpecGenerationUnavailable("规格书代际目录与清单不闭合");
  }
  if (!rootEntries.get("docs")!.isDirectory()) {
    throw new SpecGenerationUnavailable("规格书代际 docs 不是普通目录");
  }
  const docsEntries = _sealedDirectoryEntries(docsPath, "规格书代际 docs");
  const docNames = Array.from(docsEntries.keys()).sort();
  if (
    docNames.join(",") !== Object.keys(normalizedDocs).sort().join(",") ||
    docNames.some((n) => {
      const info = docsEntries.get(n)!;
      return !info.isFile() || Number(info.nlink) !== 1;
    })
  ) {
    throw new SpecGenerationUnavailable("规格书代际 docs 与清单不闭合");
  }
  return {
    generation_id: generationId,
    root: generationRoot,
    docs: docsPath,
    state: statePath,
    index: indexPath,
    manifest: manifestPath,
    manifest_sha256: expectedManifestSha,
    document_entries: normalizedDocs,
  };
}

export const WORKSPACE_DIR_NAME = "workspace";
export const WORKSPACE_ROOT = path.join(PROJECT_ROOT, WORKSPACE_DIR_NAME);
export const WORKSPACE_INPUTS = path.join(WORKSPACE_ROOT, "inputs");
export const WORKSPACE_OUTPUTS = path.join(WORKSPACE_ROOT, "outputs");
export const WORKSPACE_DEFECTS = path.join(WORKSPACE_ROOT, "defects");
export const WORKSPACE_BUCKETS: readonly string[] = ["inputs", "outputs"];

export function set_current_username(name: string): void {
  _currentUsername = name;
}

export function current_username(): string {
  return _currentUsername.trim() || (process.env.IST_SSH_USER || "").trim() || "tui";
}

const _SCOPE_RE = /^[a-z0-9][a-z0-9_.@+-]{0,63}$/;
const _WINDOWS_RESERVED_SCOPE_BASENAMES = new Set([
  "aux", "con", "nul", "prn",
  ...Array.from({ length: 9 }, (_, i) => `com${i + 1}`),
  ...Array.from({ length: 9 }, (_, i) => `lpt${i + 1}`),
]);

export class ScopeUnavailable extends Error {}

export function validate_output_scope(name: string): string {
  const scope = String(name || "").trim();
  const deviceBasename = scope.split(".", 1)[0];
  if (!_SCOPE_RE.test(scope) || scope.endsWith(".") || _WINDOWS_RESERVED_SCOPE_BASENAMES.has(deviceBasename)) {
    throw new ScopeUnavailable(`unsafe output scope: ${JSON.stringify(scope)}`);
  }
  return scope;
}

export function multi_tenant(): boolean {
  return ["1", "true", "yes"].includes((process.env.IST_MULTI_TENANT || "").trim().toLowerCase());
}

export function process_tenant_from_env(): boolean {
  return ["1", "true", "yes"].includes((process.env.IST_PROCESS_TENANT_FROM_ENV || "").trim().toLowerCase());
}

export function output_scope(): string {
  if (!multi_tenant()) {
    return "";
  }
  let scope = _currentUsername.trim();
  if (!scope && process_tenant_from_env()) {
    scope = (process.env.IST_SSH_USER || "").trim();
  }
  if (!scope) {
    throw new ScopeUnavailable("request identity is unavailable in multi-tenant mode");
  }
  return validate_output_scope(scope);
}

export function workspace_bucket_root(
  bucket: string,
  opts: { project_root?: string | null; workspace_root?: string | null } = {}
): string {
  const projectRoot = opts.project_root ?? null;
  const workspaceRoot = opts.workspace_root ?? null;
  if (!WORKSPACE_BUCKETS.includes(bucket)) {
    throw new Error(`unknown workspace bucket: ${JSON.stringify(bucket)}`);
  }
  if (projectRoot !== null && workspaceRoot !== null) {
    throw new TypeError("pass at most one of project_root / workspace_root");
  }
  let base: string;
  if (workspaceRoot !== null) {
    base = path.resolve(String(workspaceRoot));
  } else if (projectRoot !== null) {
    base = path.join(path.resolve(String(projectRoot)), WORKSPACE_DIR_NAME);
  } else {
    base = WORKSPACE_ROOT;
  }
  return path.join(base, bucket);
}

export function scope_bucket(root: string, scope?: string | null): string {
  const resolved = scope === undefined || scope === null ? output_scope() : scope;
  return resolved ? path.join(root, resolved) : root;
}

export function scoped_bucket_root(
  bucket: string,
  opts: { project_root?: string | null; workspace_root?: string | null; scope?: string | null } = {}
): string {
  return scope_bucket(
    workspace_bucket_root(bucket, { project_root: opts.project_root ?? null, workspace_root: opts.workspace_root ?? null }),
    opts.scope ?? null
  );
}

export function scoped_outputs_root(): string {
  return scope_bucket(WORKSPACE_OUTPUTS);
}

export function scoped_inputs_root(): string {
  return scope_bucket(WORKSPACE_INPUTS);
}

export function user_output_dir(): string {
  const d = scoped_outputs_root();
  fs.mkdirSync(d, { recursive: true });
  return d;
}

export function compile_out_name(): string {
  return (process.env.IST_COMPILE_OUT_NAME || "").trim();
}

export function autoid_output_path(autoid: string, ...parts: string[]): string {
  let base = user_output_dir();
  const name = compile_out_name();
  if (name) {
    base = path.join(base, name);
  }
  base = path.join(base, autoid);
  return parts.length ? path.join(base, parts[0]) : base;
}

export const KNOWLEDGE_MINERU = path.join(KNOWLEDGE_INTERMEDIATE, "mineru");
export const CACHE_JSON = path.join(KNOWLEDGE_INTERMEDIATE, ".cache.json");
export const KNOWLEDGE_FOOTPRINTS = path.join(KNOWLEDGE_ROOT, "footprints");
export const KNOWLEDGE_FOOTPRINTS_NODES = path.join(KNOWLEDGE_FOOTPRINTS, "nodes");

export function footprint_nodes_dir(version?: string | null): string {
  if (!version) {
    return KNOWLEDGE_FOOTPRINTS_NODES;
  }
  return path.join(KNOWLEDGE_FOOTPRINTS, `nodes_${version}`);
}

export const KNOWLEDGE_FRAMEWORK_MIRROR = path.join(KNOWLEDGE_ROOT, "framework", "mirror");
export const KNOWLEDGE_VERIFIED_PACKAGES = path.join(KNOWLEDGE_ROOT, "framework", "verified");
export const KNOWLEDGE_AUTO_ENV = path.join(KNOWLEDGE_DATA_ROOT, "auto_env");
export const KNOWLEDGE_AUTO_ENV_TOPOLOGY = path.join(KNOWLEDGE_AUTO_ENV, "network_topology_rag.md");
export const KNOWLEDGE_AUTO_ENV_TOPOLOGY_JSON = path.join(KNOWLEDGE_AUTO_ENV, "network_topology.json");
export const KNOWLEDGE_AUTO_ENV_ACTIONS_JSON = path.join(KNOWLEDGE_AUTO_ENV, "execute_actions.json");
export const SPEC_NAME_RE = /(?<![a-z])spec(?:ification)?(?![a-z])/i;

export function is_spec_document(name_or_path: string): boolean {
  if (!name_or_path) {
    return false;
  }
  const posixName = String(name_or_path).replace(/\\/g, "/").split("/").pop() || "";
  return SPEC_NAME_RE.test(posixName);
}

const _SOURCE_RETRIEVAL_PRIORITY_RULES: Array<[RegExp, number]> = [
  [/phaseII|phase_II/i, 35],
  [/^cli_/i, 100],
  [/^app_/i, 80],
  [/Design_Doc/i, 20],
  [/Project_Status/i, 15],
];
export const DEFAULT_SOURCE_RETRIEVAL_PRIORITY = 50;
export const SPEC_SOURCE_RETRIEVAL_PRIORITY = 120;

export function source_retrieval_priority(source_file_or_stem: string): number {
  if (!source_file_or_stem) {
    return DEFAULT_SOURCE_RETRIEVAL_PRIORITY;
  }
  const key = source_file_or_stem.trim();
  if (/phaseII|phase_II/i.test(key)) {
    return 35;
  }
  if (is_spec_document(key)) {
    return SPEC_SOURCE_RETRIEVAL_PRIORITY;
  }
  for (const [pattern, score] of _SOURCE_RETRIEVAL_PRIORITY_RULES) {
    if (pattern.test(key)) {
      return score;
    }
  }
  return DEFAULT_SOURCE_RETRIEVAL_PRIORITY;
}

export function evidence_retrieval_priority(evidence: any): number {
  if (typeof evidence !== "object" || evidence === null || Array.isArray(evidence)) {
    return DEFAULT_SOURCE_RETRIEVAL_PRIORITY;
  }
  const src = evidence.source_file || evidence.stem || "";
  return source_retrieval_priority(String(src));
}

export function ensure_intermediate_dirs(): void {
  for (const d of [KNOWLEDGE_INTERMEDIATE, KNOWLEDGE_MINERU]) {
    fs.mkdirSync(d, { recursive: true });
  }
}

export function ensure_data_dirs(): void {
  for (const d of [KNOWLEDGE_DATA_ROOT, KNOWLEDGE_ORGIN, KNOWLEDGE_MARKDOWN, KNOWLEDGE_MARKDOWN_PRODUCT, KNOWLEDGE_MARKDOWN_QA, KNOWLEDGE_MANUAL]) {
    fs.mkdirSync(d, { recursive: true });
  }
}

export function ensure_workspace_dirs(): void {
  for (const d of [WORKSPACE_ROOT, WORKSPACE_INPUTS, WORKSPACE_OUTPUTS, WORKSPACE_DEFECTS]) {
    fs.mkdirSync(d, { recursive: true });
  }
}
