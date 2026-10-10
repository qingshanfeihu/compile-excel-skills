import crypto from "node:crypto";
import path from "node:path";
import { P as Path } from "../../_py";
import { build_package_advisories, write_json_atomic } from "../../case_compiler/package_advisories";
import { file_identity, walk_identity } from "../../common/file_identity";
import { canonical_root, inspect_verified_corpus, provenance_path } from "./verified_corpus";

export class FrameworkDerivedProjectionError extends Error {
  reason_code: string;
  projection_path: string;
  generator: string;
  observed_file_sha256: string;
  expected_content_sha256: string;
  observed_content_sha256: string;
  changed_inputs: Record<string, any>[];
  expected_identity_sha256: string;
  observed_identity_sha256: string;

  constructor(
    message: string,
    opts: {
      reason_code: string;
      projection_path?: string;
      generator?: string;
      observed_file_sha256?: string;
      expected_content_sha256?: string;
      observed_content_sha256?: string;
      changed_inputs?: Record<string, any>[];
      expected_identity_sha256?: string;
      observed_identity_sha256?: string;
    }
  ) {
    super(message);
    this.name = "FrameworkDerivedProjectionError";
    this.reason_code = opts.reason_code;
    this.projection_path = opts.projection_path ?? "";
    this.generator = opts.generator ?? "";
    this.observed_file_sha256 = opts.observed_file_sha256 ?? "";
    this.expected_content_sha256 = opts.expected_content_sha256 ?? "";
    this.observed_content_sha256 = opts.observed_content_sha256 ?? "";
    this.changed_inputs = opts.changed_inputs ?? [];
    this.expected_identity_sha256 = opts.expected_identity_sha256 ?? "";
    this.observed_identity_sha256 = opts.observed_identity_sha256 ?? "";
  }

  disclosure(): Record<string, any> {
    const out: Record<string, any> = {};
    for (const [key, value] of Object.entries(this)) {
      if (value) out[key] = value;
    }
    return out;
  }
}

function _paths(project_root: Path): Record<string, Path> {
  const compile_ref = new Path(project_root.toString()).join("knowledge/data/compile_ref");
  return {
    usage: compile_ref.join("capability_usage_index.json"),
    package: compile_ref.join("package_advisories_10.5.json"),
    behavior: compile_ref.join("device_behavior_examples.json"),
    language: compile_ref.join("language_docs_index.json"),
  };
}

function _load_json_bytes(path_: Path): [any, Buffer] {
  if (path_.is_symlink() || !path_.is_file()) {
    throw new FrameworkDerivedProjectionError("framework-derived projection is missing or unsafe", { reason_code: "framework_derived_projection_missing" });
  }
  try {
    const raw = path_.read_bytes();
    return [JSON.parse(raw.toString("utf8")), raw];
  } catch (exc: any) {
    throw new FrameworkDerivedProjectionError("framework-derived projection is unreadable", { reason_code: "framework_derived_projection_unreadable" });
  }
}

function _load_json(path_: Path): any {
  return _load_json_bytes(path_)[0];
}

function _content_digest(value: any): string {
  const raw = Buffer.from(JSON.stringify(value), "utf8");
  return crypto.createHash("sha256").update(raw).digest("hex");
}

function _check_projection(project_root: Path, path_: Path, expected: any, opts: { reason_code: string; generator: string }): void {
  const relative = path_.relative_to(project_root).toString().replace(/\\/g, "/");
  let observed: any;
  let raw: Buffer;
  try {
    [observed, raw] = _load_json_bytes(path_);
  } catch (exc: any) {
    if (exc instanceof FrameworkDerivedProjectionError) {
      throw new FrameworkDerivedProjectionError(String(exc), {
        reason_code: exc.reason_code,
        projection_path: relative,
        generator: opts.generator,
      });
    }
    throw exc;
  }
  if (JSON.stringify(observed) !== JSON.stringify(expected)) {
    throw new FrameworkDerivedProjectionError("projection content differs from the current generator output", {
      reason_code: opts.reason_code,
      projection_path: relative,
      generator: opts.generator,
      observed_file_sha256: crypto.createHash("sha256").update(raw).digest("hex"),
      expected_content_sha256: _content_digest(expected),
      observed_content_sha256: _content_digest(observed),
    });
  }
}

function _package_payload(project_root: Path): Record<string, any> {
  return build_package_advisories(canonical_root(project_root).toString(), provenance_path(project_root).toString(), {
    poison_root: new Path(project_root.toString()).join("tests/fixtures/precedents/poisoned").toString(),
    retro_scan_path: null,
  });
}

function _behavior_payload(project_root: Path): Record<string, any> {
  const gen_device_behavior_examples = require("../../scripts/gen_device_behavior_examples");
  try {
    return gen_device_behavior_examples.build(new Path(project_root.toString()));
  } catch (exc: any) {
    throw new FrameworkDerivedProjectionError("device behavior corpus is unavailable", { reason_code: "device_behavior_corpus_unavailable" });
  }
}

const _CODE_ROOT = new Path(path.resolve(__dirname, "../../.."));
const _CODE_GLOBS = ["main/case_compiler/**/*.py"];
const _CODE_FILES = [
  "main/ist_core/tools/device/structural_gate.py",
  "main/ist_core/compile_engine/verified_corpus.py",
  "main/ist_core/compile_engine/framework_projections.py",
  "main/ist_core/worker_device_context.py",
  "main/ist_core/tools/knowledge/behavior_tool.py",
  "main/common/schema_identity.py",
  "main/common/file_identity.py",
  "scripts/gen_capability_usage_index.py",
  "scripts/gen_device_behavior_examples.py",
  "scripts/maintenance/build_language_docs_index.py",
];
const _PROJECTION_NAMES = new Set(["capability_usage_index.json", "package_advisories_10.5.json", "device_behavior_examples.json", "language_docs_index.json"]);

function _content(tuples: [string, number, number, string][]): [string, number, string][] {
  return tuples.map(([rel, size, _mtime_ns, sha]) => [rel, size, sha]);
}

function _singleton(path_: Path, rel: string): [string, number | string, string | null] {
  try {
    const [_resolved, size, _mtime_ns, sha] = file_identity(path_.toString());
    return [rel, size, sha];
  } catch {
    return [rel, "<absent>", null];
  }
}

function _code_identity(): [string, number | string, string | null][] {
  const files = new Set<Path>();
  for (const pattern of _CODE_GLOBS) {
    for (const p of _CODE_ROOT.glob(pattern)) files.add(p);
  }
  for (const rel of _CODE_FILES) files.add(_CODE_ROOT.join(rel));
  const out: [string, number | string, string | null][] = [];
  for (const p of [...files].sort((a, b) => a.toString().localeCompare(b.toString()))) {
    out.push(_singleton(p, p.relative_to(_CODE_ROOT).toString().replace(/\\/g, "/")));
  }
  return out;
}

function _rebuild_callable_ids(): number[] {
  const gen_capability_usage_index = require("../../scripts/gen_capability_usage_index");
  const gen_device_behavior_examples = require("../../scripts/gen_device_behavior_examples");
  const build_language_docs_index = require("../../scripts/maintenance/build_language_docs_index");
  const { steps_from_xlsx } = require("../tools/device/structural_gate");
  return [
    inspect_verified_corpus as any,
    gen_capability_usage_index.build as any,
    gen_device_behavior_examples.build as any,
    build_language_docs_index.build_language_docs_index as any,
    build_package_advisories as any,
    steps_from_xlsx as any,
  ].map((fn) => {
    // Approximate id() with a hash of the function source
    return crypto.createHash("sha256").update(String(fn), "utf8").digest("hex").slice(0, 16);
  }) as any;
}

function _validation_identity(project_root: Path): any[] {
  const root = new Path(project_root.toString());
  const knowledge = root.join("knowledge");
  return [
    root.resolve().toString(),
    ["verified", walk_identity(knowledge.join("framework/verified").toString())],
    ["mirror", _content(walk_identity(knowledge.join("framework/mirror").toString()))],
    ["behavior_corpus", _content(walk_identity(knowledge.join("data/device_behavior_corpus").toString()))],
    ["manual", _content(walk_identity(knowledge.join("data/manual").toString()))],
    ["compile_ref", _content(walk_identity(knowledge.join("data/compile_ref").toString()))],
    ["poisoned", _content(walk_identity(root.join("tests/fixtures/precedents/poisoned").toString()))],
    [
      "singletons",
      [
        _singleton(provenance_path(root), "knowledge/framework/mirror_precedent_provenance.json"),
        _singleton(knowledge.join("shadow_exec/manifest.json"), "knowledge/shadow_exec/manifest.json"),
        _singleton(_CODE_ROOT.join("scripts/data/package_deny_rulings.json"), "scripts/data/package_deny_rulings.json"),
      ],
    ],
    ["code", _code_identity()],
    ["callables", _rebuild_callable_ids()],
  ];
}

function _mask_projections(identity: any[]): any[] {
  const masked: any[] = [];
  for (const component of identity) {
    if (Array.isArray(component) && component.length === 2 && component[0] === "compile_ref") {
      masked.push([component[0], component[1].filter((entry: any) => !_PROJECTION_NAMES.has(entry[0]))]);
    } else {
      masked.push(component);
    }
  }
  return masked;
}

function _require_stable_identity(before: any[], after: any[]): void {
  if (JSON.stringify(before) === JSON.stringify(after)) return;
  const old: Record<string, any> = {};
  for (const component of before.slice(1)) {
    if (Array.isArray(component) && component.length === 2) old[component[0]] = component[1];
  }
  const new_: Record<string, any> = {};
  for (const component of after.slice(1)) {
    if (Array.isArray(component) && component.length === 2) new_[component[0]] = component[1];
  }
  const changed: Record<string, any>[] = [];
  const components = new Set([...Object.keys(old), ...Object.keys(new_)]);
  for (const component of [...components].sort()) {
    const left = old[component];
    const right = new_[component];
    if (JSON.stringify(left) === JSON.stringify(right)) continue;
    if (Array.isArray(left) && Array.isArray(right) && [...left, ...right].every((row) => Array.isArray(row) && row.length > 0 && typeof row[0] === "string")) {
      const old_rows: Record<string, any> = Object.fromEntries(left.map((row: any) => [row[0], row]));
      const new_rows: Record<string, any> = Object.fromEntries(right.map((row: any) => [row[0], row]));
      for (const p of [...new Set([...Object.keys(old_rows), ...Object.keys(new_rows)])].sort()) {
        if (JSON.stringify(old_rows[p]) !== JSON.stringify(new_rows[p])) {
          changed.push({ component, relative_path: p, before: old_rows[p], after: new_rows[p] });
        }
      }
    } else {
      changed.push({ component, relative_path: "", before: left, after: right });
    }
  }
  throw new FrameworkDerivedProjectionError("projection inputs changed while they were being checked", {
    reason_code: "framework_projection_inputs_changed",
    changed_inputs: changed,
    expected_identity_sha256: _content_digest(before),
    observed_identity_sha256: _content_digest(after),
  });
}

let _MEMO: Record<string, any> | null = null;

function _memo_lookup(identity: any[]): Record<string, any> | null {
  if (_MEMO !== null && JSON.stringify(_MEMO.identity) === JSON.stringify(identity)) {
    return _MEMO;
  }
  return null;
}

function _memo_store(identity: any[], opts: { verdict: Record<string, any>; payloads: Record<string, any>; inspection: any }): void {
  _MEMO = { identity, verdict: { ...opts.verdict }, payloads: opts.payloads, inspection: opts.inspection };
}

export function clear_projection_validation_memo(): void {
  _MEMO = null;
}

export function converge_language_docs_projection(project_root: Path): boolean {
  project_root = new Path(project_root.toString());
  const path_ = _paths(project_root).language;
  const build_language_docs_index = require("../../scripts/maintenance/build_language_docs_index");
  const language = build_language_docs_index.build_language_docs_index(project_root);
  let current_language: any = null;
  try {
    current_language = _load_json(path_);
  } catch {}
  if (JSON.stringify(current_language) === JSON.stringify(language)) return false;
  build_language_docs_index.write_language_docs_index(path_, { root: project_root });
  return true;
}

export function converge_framework_derived_projections(project_root: Path): Record<string, any> {
  project_root = new Path(project_root.toString());
  const gen_capability_usage_index = require("../../scripts/gen_capability_usage_index");
  if (gen_capability_usage_index._ROOT.resolve() !== project_root.resolve()) {
    throw new FrameworkDerivedProjectionError("capability usage generator is bound to another project root", { reason_code: "framework_projection_root_mismatch" });
  }
  const identity = _validation_identity(project_root);
  const memo = _memo_lookup(identity);
  const payloads = memo !== null ? memo.payloads : null;
  const inspection = memo !== null ? memo.inspection : inspect_verified_corpus(project_root);
  if (inspection.issues.length) {
    throw new FrameworkDerivedProjectionError("verified corpus must converge before projections are rebuilt", { reason_code: "verified_corpus_not_converged" });
  }
  const paths = _paths(project_root);
  const changed: string[] = [];
  const usage = payloads !== null ? payloads.usage : gen_capability_usage_index.build();
  let current_usage: any = null;
  try {
    current_usage = _load_json(paths.usage);
  } catch {}
  if (JSON.stringify(current_usage) !== JSON.stringify(usage)) {
    gen_capability_usage_index.write_projection(usage, paths.usage);
    changed.push("capability_usage_index");
  }
  const package_ = payloads !== null ? payloads.package : _package_payload(project_root);
  let current_package: any = null;
  try {
    current_package = _load_json(paths.package);
  } catch {}
  if (JSON.stringify(current_package) !== JSON.stringify(package_)) {
    write_json_atomic(paths.package.toString(), package_);
    changed.push("package_advisories");
  }
  const behavior = payloads !== null ? payloads.behavior : _behavior_payload(project_root);
  let current_behavior: any = null;
  try {
    current_behavior = _load_json(paths.behavior);
  } catch {}
  const behavior_changed = JSON.stringify(current_behavior) !== JSON.stringify(behavior);
  if (behavior_changed) {
    const gen_device_behavior_examples = require("../../scripts/gen_device_behavior_examples");
    gen_device_behavior_examples.write_atomic(paths.behavior, behavior);
    changed.push("device_behavior_examples");
  }
  const build_language_docs_index = require("../../scripts/maintenance/build_language_docs_index");
  let language: any;
  if (payloads !== null && !behavior_changed) {
    language = payloads.language;
  } else {
    language = build_language_docs_index.build_language_docs_index(project_root);
  }
  let current_language: any = null;
  try {
    current_language = _load_json(paths.language);
  } catch {}
  if (JSON.stringify(current_language) !== JSON.stringify(language)) {
    build_language_docs_index.write_language_docs_index(paths.language, { root: project_root });
    changed.push("language_docs_index");
  }
  const verdict = {
    verified_corpus_status: inspection.status,
    verified_corpus_count: inspection.active_count,
    usage_status: String((usage._meta ?? {}).corpus_status ?? ""),
    behavior_status: String(behavior.status ?? ""),
  };
  const post_identity = _validation_identity(project_root);
  _require_stable_identity(_mask_projections(identity), _mask_projections(post_identity));
  _memo_store(post_identity, { verdict, payloads: { usage, package: package_, behavior, language }, inspection });
  return { changed, ...verdict };
}

export function validate_framework_derived_projections(project_root: Path): Record<string, any> {
  project_root = new Path(project_root.toString());
  const gen_capability_usage_index = require("../../scripts/gen_capability_usage_index");
  const gen_device_behavior_examples = require("../../scripts/gen_device_behavior_examples");
  const package_generator = require("../../scripts/maintenance/build_package_advisories");
  if (gen_capability_usage_index._ROOT.resolve() !== project_root.resolve()) {
    throw new FrameworkDerivedProjectionError("capability usage generator is bound to another project root", { reason_code: "framework_projection_root_mismatch" });
  }
  const identity = _validation_identity(project_root);
  const memo = _memo_lookup(identity);
  if (memo !== null) {
    _require_stable_identity(identity, _validation_identity(project_root));
    return { ...memo.verdict };
  }
  const inspection = inspect_verified_corpus(project_root);
  if (inspection.issues.length) {
    throw new FrameworkDerivedProjectionError("verified corpus contains legacy or incompatible data", { reason_code: "verified_corpus_migration_required" });
  }
  const paths = _paths(project_root);
  const usage = gen_capability_usage_index.build();
  _check_projection(project_root, paths.usage, usage, { reason_code: "capability_usage_projection_stale", generator: "gen_capability_usage_index" });
  const package_ = _package_payload(project_root);
  _check_projection(project_root, paths.package, package_, { reason_code: "package_advisory_projection_stale", generator: "build_package_advisories" });
  const behavior = _behavior_payload(project_root);
  _check_projection(project_root, paths.behavior, behavior, { reason_code: "device_behavior_projection_stale", generator: "gen_device_behavior_examples" });
  const build_language_docs_index = require("../../scripts/maintenance/build_language_docs_index");
  const language = build_language_docs_index.build_language_docs_index(project_root);
  _check_projection(project_root, paths.language, language, { reason_code: "language_docs_projection_stale", generator: "build_language_docs_index" });
  const verdict = {
    verified_corpus_status: inspection.status,
    verified_corpus_count: inspection.active_count,
    usage_status: String((usage._meta ?? {}).corpus_status ?? ""),
    behavior_status: String(behavior.status ?? ""),
  };
  _require_stable_identity(identity, _validation_identity(project_root));
  _memo_store(identity, { verdict, payloads: { usage, package: package_, behavior, language }, inspection });
  return verdict;
}
