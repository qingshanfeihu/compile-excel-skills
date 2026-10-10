import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { _cex_data_path } from "../_root";
import {
  open_directory_nofollow,
  read_regular_at_nofollow,
  read_regular_nofollow,
  validate_json_budget,
} from "./_sealed_io";
import {
  ExcelContractError,
  contract_enabled_fs_by_e,
  contract_sha256,
  load_excel_contract,
} from "./excel_contract";
import {
  contains_prohibited_declaration,
  validate_source_context_binding,
} from "../defect_spec_source";
import {
  KNOWLEDGE_AUTO_ENV,
  KNOWLEDGE_DATA_ROOT,
  KNOWLEDGE_FOOTPRINTS,
  KNOWLEDGE_FOOTPRINTS_NODES,
  KNOWLEDGE_FRAMEWORK_MIRROR,
  KNOWLEDGE_VERIFIED_PACKAGES,
  KNOWLEDGE_MANUAL,
  KNOWLEDGE_MARKDOWN,
  PROJECT_ROOT,
  SpecGenerationUnavailable,
  WORKSPACE_DEFECTS,
  WORKSPACE_INPUTS,
  WORKSPACE_OUTPUTS,
  output_scope,
  resolve_active_spec_generation,
  scope_bucket,
} from "../knowledge_paths";
import { accepts_schema } from "../common/schema_identity";

function _scoped_outputs_root(): string {
  return scope_bucket(WORKSPACE_OUTPUTS);
}

const _CODE_ROOT = _cex_data_path("");

export type Layer = "G" | "E" | "V";
const _VALID_LAYERS = ["G", "E", "V"];
export const MUTATION_ROLE_CONTROL = "control";
const _VALID_MUTATION_ROLES = ["", MUTATION_ROLE_CONTROL];
export const ASSERTION_TYPE_SCHEMA = "ist.ide.assertion";
export const _EXPECT_KINDS = new Set(["Author", "Manual", "ConfigBinding", "Spec", "DefectSpec", "CapabilityXml"]);
const _CLAIM_ORIGIN: Record<string, [string, string]> = {
  intent: ["Author", ""],
  author: ["Author", ""],
  spec: ["Spec", ""],
  defect_spec: ["DefectSpec", ""],
  manual: ["Manual", ""],
  capability_xml: ["CapabilityXml", ""],
  config_derived: ["ConfigBinding", "config_derived"],
  captured_relation: ["ConfigBinding", "captured_relation"],
  distribution_derived: ["ConfigBinding", "distribution_derived"],
  membership_derived: ["ConfigBinding", "membership_derived"],
  status_derived: ["Author", "status_derived"],
};

export function claim_authority_source(source_kind: string): string {
  return (_CLAIM_ORIGIN[String(source_kind || "").trim()] || ["", ""])[0];
}

export function claim_derivation(source_kind: string): string {
  return (_CLAIM_ORIGIN[String(source_kind || "").trim()] || ["", ""])[1];
}

const _RUNTIME_ONLY_KINDS = new Set(["DeviceRuntime", "Probe", "Observed", "CurrentRun", "Precedent", "Footprint"]);
const _FLIP_KINDS = new Set(["Flipped", "Exempt"]);
export const ORDERING_EXEMPT_REASON = "multicore_nondeterministic_order";
export const FLIP_CONTROL_UNCONSTRUCTIBLE_REASON = "flip_control_unconstructible";
export const EXEMPT_REASON_CODES = new Set([
  "shared_bed_hidden_vars",
  ORDERING_EXEMPT_REASON,
  "device_default_row",
  "non_readonly_probe",
  "direction_review_pending",
  FLIP_CONTROL_UNCONSTRUCTIBLE_REASON,
]);
export const COMPILER_ISSUED_EXEMPT_CODES = new Set([FLIP_CONTROL_UNCONSTRUCTIBLE_REASON]);
const EMIT_ACCEPTED_EXEMPT_CODES = new Set([...EXEMPT_REASON_CODES].filter((c) => c !== "direction_review_pending"));
export const AUTHOR_DECLARABLE_EXEMPT_CODES = new Set([...EXEMPT_REASON_CODES].filter((c) => !COMPILER_ISSUED_EXEMPT_CODES.has(c)));
const _FORM_KIND = "GatesPass";
const _VALID_SOURCE_KINDS = [
  "footprint", "emit_auto", "precedent", "env_facts", "test_env_dispatch",
  "manual", "spec", "defect_spec", "capability_xml", "intent",
  "config_derived", "captured_relation", "distribution_derived", "membership_derived",
  "status_derived", "skeleton", "device_runtime", "unknown",
];
export const RUNTIME_PLACEHOLDER = "<RUNTIME>";
const KNOWN_PROVENANCE_CLAIM_LIMIT = 12;
const _SOURCE_LOCATOR_REQUIRED = new Set(["footprint", "manual", "spec", "defect_spec", "capability_xml", "precedent", "env_facts", "intent", "skeleton"]);

function _read_intent_json_lazy(): [typeof import("./contract_entry").read_intent_json, typeof import("./contract_entry").ContractError] {
  const mod = require("./contract_entry");
  return [mod.read_intent_json, mod.ContractError];
}

export function known_provenance_facts(autoid: string, opts: { outputs_root: string }): string[] {
  const lines = [
    "<known_provenance_facts>",
    "The following values are engine-read facts, not suggestions and not a credential.",
  ];
  const aid = String(autoid || "").trim();
  if (/^\d{18}$/.test(aid)) {
    const [read_intent_json, ContractError] = _read_intent_json_lazy();
    const root = path.resolve(String(opts.outputs_root));
    let payload: Record<string, any> = {};
    try {
      [payload] = read_intent_json(path.join(root, aid, "intent.json"), { trusted_root: root });
    } catch (exc) {
      if (!(exc instanceof ContractError)) throw exc;
      payload = {};
    }
    const claims = payload["author_claims"];
    const pairs: [string, string][] = [];
    if (claims && typeof claims === "object" && !Array.isArray(claims)) {
      for (const key of Object.keys(claims).sort()) {
        const claim = claims[key];
        if (!claim || typeof claim !== "object" || Array.isArray(claim)) continue;
        const expectation_id = String(claim["expectation_id"] || key).trim();
        const semantic_key = String(claim["semantic_key"] || "").trim();
        if (expectation_id && semantic_key) pairs.push([expectation_id, semantic_key]);
      }
    }
    if (pairs.length) {
      lines.push(
        "Stamped Author assertion identities (copy both fields onto each assertion that redeems that claim, and use source.kind='intent' with source.ref equal to the expectation_id):"
      );
      for (const [expectation_id, semantic_key] of pairs.slice(0, KNOWN_PROVENANCE_CLAIM_LIMIT)) {
        lines.push(
          `  - expectation_id=${JSON.stringify(expectation_id)}; semantic_key=${JSON.stringify(semantic_key)}; source={'kind': 'intent', 'ref': ${JSON.stringify(expectation_id)}}`
        );
      }
      if (pairs.length > KNOWN_PROVENANCE_CLAIM_LIMIT) {
        lines.push(`  - ... ${pairs.length - KNOWN_PROVENANCE_CLAIM_LIMIT} more stamped pairs remain in the same intent.json`);
      }
    }
  }
  lines.push(
    "Source-kind routing already enforced by the engine:",
    "  - intent redeems a stamped expected assertion; it does not source an APV CONFIG command or a test-environment action.",
    "  - E='test_env' actions use source.kind='test_env_dispatch' and the compiler-derived source.ref 'lib/env.py#Env.<lowercase F>'.",
    "  - APV commands/configuration and other actions cite the real source actually consulted (for example an existing manual or footprint locator); source.kind 'emit_auto' is accepted only for the time/sleep language primitive.",
    "  - Field routing is part of the contract: put product-command provenance in CONFIG.ref (kind:locator), observation-command provenance in OBSERVE_ASSERT.cmd_ref, and expected-value authority in each asserts[].ref. Do not invent a nested provenance/source object. Commands with different sources belong in separate CONFIG blocks.",
    "  - A manual locator must identify one exact file. Copy the project-relative or manual-root-relative path exposed by the retrieval result; a bare basename such as 'cli_cn.md' is invalid when more than one version/root carries it. An ambiguity rejection lists the exact candidate paths; copy one of those paths instead of retrying another bare stem.",
    "</known_provenance_facts>"
  );
  return lines;
}

function _isPlainObject(value: any): value is Record<string, any> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export class StepSource {
  kind: string = "unknown";
  ref: string = "";
  receipt: Record<string, any> = {};

  constructor(opts: { kind?: string; ref?: string; receipt?: Record<string, any> } = {}) {
    this.kind = opts.kind ?? "unknown";
    this.ref = opts.ref ?? "";
    this.receipt = opts.receipt ?? {};
    if (!_VALID_SOURCE_KINDS.includes(this.kind)) {
      this.kind = "unknown";
    }
  }
}

export class StepIR {
  E: string;
  F: string;
  G: string;
  layer: Layer = "V";
  source: StepSource = new StepSource();
  assertion_type: Record<string, any> | null = null;
  spec_gap: string = "";
  observation_id: string = "";
  result_channel: string = "";
  observation_ref: string = "";
  expectation_id: string = "";
  semantic_key: string = "";
  mutation_role: string = "";

  constructor(opts: {
    E: string;
    F: string;
    G: string;
    layer?: Layer;
    source?: StepSource;
    assertion_type?: Record<string, any> | null;
    spec_gap?: string;
    observation_id?: string;
    result_channel?: string;
    observation_ref?: string;
    expectation_id?: string;
    semantic_key?: string;
    mutation_role?: string;
  }) {
    this.E = opts.E;
    this.F = opts.F;
    this.G = opts.G;
    this.layer = opts.layer ?? "V";
    this.source = opts.source ?? new StepSource();
    this.assertion_type = opts.assertion_type ?? null;
    this.spec_gap = opts.spec_gap ?? "";
    this.observation_id = opts.observation_id ?? "";
    this.result_channel = opts.result_channel ?? "";
    this.observation_ref = opts.observation_ref ?? "";
    this.expectation_id = opts.expectation_id ?? "";
    this.semantic_key = opts.semantic_key ?? "";
    this.mutation_role = opts.mutation_role ?? "";
    if (!_VALID_LAYERS.includes(this.layer)) {
      this.layer = "V";
    }
    if (!_VALID_MUTATION_ROLES.includes(this.mutation_role)) {
      this.mutation_role = "";
    }
  }
}

export class CaseProvenance {
  autoid: string;
  steps: StepIR[] = [];
  skeleton_ref: string = "";
  assertion_schema: string = "";
  provisional_at_emit: boolean = true;

  constructor(opts: {
    autoid: string;
    steps?: StepIR[];
    skeleton_ref?: string;
    assertion_schema?: string;
    provisional_at_emit?: boolean;
  }) {
    this.autoid = opts.autoid;
    this.steps = opts.steps ?? [];
    this.skeleton_ref = opts.skeleton_ref ?? "";
    this.assertion_schema = opts.assertion_schema ?? "";
    this.provisional_at_emit = opts.provisional_at_emit ?? true;
  }

  to_dict(): Record<string, any> {
    return {
      autoid: this.autoid,
      skeleton_ref: this.skeleton_ref,
      ...(this.assertion_schema ? { assertion_schema: this.assertion_schema } : {}),
      provisional_at_emit: this.provisional_at_emit,
      steps: this.steps.map((s) => ({
        E: s.E,
        F: s.F,
        G: s.G,
        layer: s.layer,
        source: {
          kind: s.source.kind,
          ref: s.source.ref,
          ...(Object.keys(s.source.receipt).length ? { receipt: s.source.receipt } : {}),
        },
        ...(s.assertion_type !== null ? { assertion_type: s.assertion_type } : {}),
        ...(s.spec_gap ? { spec_gap: s.spec_gap } : {}),
        ...(s.observation_id ? { observation_id: s.observation_id } : {}),
        ...(s.result_channel ? { result_channel: s.result_channel } : {}),
        ...(s.observation_ref ? { observation_ref: s.observation_ref } : {}),
        ...(s.expectation_id ? { expectation_id: s.expectation_id } : {}),
        ...(s.semantic_key ? { semantic_key: s.semantic_key } : {}),
        ...(s.mutation_role ? { mutation_role: s.mutation_role } : {}),
      })),
    };
  }

  to_json(): string {
    return JSON.stringify(this.to_dict(), null, 2);
  }

  layer_steps(layer: Layer): StepIR[] {
    return this.steps.filter((s) => s.layer === layer);
  }

  static from_dict(d: Record<string, any>): CaseProvenance {
    const steps: StepIR[] = [];
    for (const raw of (d["steps"] || [])) {
      const src = raw["source"] || {};
      steps.push(
        new StepIR({
          E: String(raw["E"] ?? ""),
          F: String(raw["F"] ?? ""),
          G: String(raw["G"] ?? ""),
          layer: raw["layer"] ?? "V",
          source: new StepSource({
            kind: src["kind"] ?? "unknown",
            ref: String(src["ref"] ?? ""),
            receipt: _isPlainObject(src["receipt"]) ? { ...src["receipt"] } : {},
          }),
          assertion_type: "assertion_type" in raw ? raw["assertion_type"] : null,
          spec_gap: String(raw["spec_gap"] || ""),
          observation_id: String(raw["observation_id"] || ""),
          result_channel: String(raw["result_channel"] || ""),
          observation_ref: String(raw["observation_ref"] || ""),
          expectation_id: String(raw["expectation_id"] || ""),
          semantic_key: String(raw["semantic_key"] || ""),
          mutation_role: String(raw["mutation_role"] || ""),
        })
      );
    }
    let _prov_at_emit: boolean;
    if ("provisional_at_emit" in d) {
      _prov_at_emit = Boolean(d["provisional_at_emit"] ?? true);
    } else {
      _prov_at_emit = Boolean(d["provisional"] ?? true);
    }
    return new CaseProvenance({
      autoid: String(d["autoid"] ?? ""),
      steps,
      skeleton_ref: String(d["skeleton_ref"] ?? ""),
      assertion_schema: String(d["assertion_schema"] ?? ""),
      provisional_at_emit: _prov_at_emit,
    });
  }

  static from_json(text: string): CaseProvenance {
    return CaseProvenance.from_dict(JSON.parse(text));
  }
}

const _EXTERNAL_SOURCE_KINDS = new Set(["footprint", "manual", "spec", "defect_spec", "capability_xml", "precedent", "env_facts", "intent", "skeleton"]);
const _DERIVED_SOURCE_KINDS = new Set(["config_derived", "captured_relation", "distribution_derived", "membership_derived", "status_derived"]);
const _CONFIG_BINDING_DERIVATION_SCHEMA = "ist.config-binding.derivation";
const _CONFIG_BINDING_RULES: Record<string, Set<string>> = {
  config_derived: new Set(["config.literal-copy", "config.fixture-literal-backref"]),
  captured_relation: new Set(["capture.static-relation", "capture.static-reference"]),
  distribution_derived: new Set(["distribution.interval"]),
  membership_derived: new Set(["membership.literal-set"]),
  status_derived: new Set(["status.exit-code"]),
};
const _CONFIG_BINDING_GENERATORS: Record<string, string> = {
  "config.literal-copy": "main/case_compiler/provenance_ir.py",
  "config.fixture-literal-backref": "main/case_compiler/provenance_ir.py",
  "capture.static-relation": "main/case_compiler/provenance_ir.py",
  "capture.static-reference": "main/case_compiler/provenance_ir.py",
  "distribution.interval": "main/case_compiler/distribution_assertion.py",
  "membership.literal-set": "main/case_compiler/membership_assertion.py",
  "status.exit-code": "main/case_compiler/provenance_ir.py",
};
const _EXIT_STATUS_EXPECTATIONS: Record<string, string> = { success: "(?m)^IST_EXIT_STATUS=0\\r?$" };

function _transport_failure_pattern(codes: number[]): string {
  const alternation = [...new Set(codes.map((c) => Math.trunc(c)))].sort((a, b) => a - b).join("|");
  return `(?m)^IST_EXIT_STATUS=(${alternation})\\r?$`;
}

export function exit_status_assertion(expect: string, probe: string = "", codes: number[] = []): [Record<string, string> | null, string] {
  const { _EXIT_STATUS_EXPECTS } = require("./blocks");
  const value = String(expect || "").trim().toLowerCase();
  if (!_EXIT_STATUS_EXPECTS.includes(value)) {
    return [null, "exit-status expect must be exactly success or failure"];
  }
  if (value === "success") {
    return [{ E: "check_point", F: "found", G: _EXIT_STATUS_EXPECTATIONS["success"] }, ""];
  }
  const tool = String(probe || "").trim().toLowerCase();
  const cleaned = [...new Set((codes || []).filter((c) => Number.isInteger(c) && typeof c === "number" && c > 0))].sort((a, b) => a - b);
  if (!tool || !cleaned.length) {
    return [
      null,
      "expect=failure asserts a transport-level failure of the probe tool, so it needs the probe tool name and that tool's documented transport-failure exit codes (grammar section probe_tools); a bare non-zero exit code is not accepted because it also matches client-side errors and misses answered refusals",
    ];
  }
  return [{ E: "check_point", F: "found", G: _transport_failure_pattern(cleaned) }, ""];
}

const _TEST_ENV_DISPATCH_SOURCES = ["lib/env.py", "lib/test_xlsx.py"];
const _LINE_LOCATOR_RE = /^(.*?)(?::([1-9]\d*)(?:-([1-9]\d*))?)?$/;
const _MANUAL_LOCATOR_SHAPE = "manual:<source-file-or-unique-stem>[:<line>|:<line-start>-<line-end>]";
const _CAPABILITY_XML_EXPECT_RECEIPT_SCHEMA = "ist.capability-xml-expected";
const _DEFECT_SPEC_RECEIPT_SCHEMA = "ist.defect-spec-receipt";
const _DEFECT_SPEC_MAX_SOURCE_BYTES = 64 * 1024 * 1024;
const _DEFECT_SPEC_MAX_TICKET_BYTES = 64 * 1024 * 1024;
const _DEFECT_SPEC_MAX_SOURCE_CANDIDATES = 4096;
const _DEFECT_SPEC_MAX_SOURCE_TOTAL_BYTES = 256 * 1024 * 1024;
const _DEFECT_SPEC_MAX_TICKET_JSON_DEPTH = 64;
const _DEFECT_SPEC_MAX_TICKET_JSON_TOKENS = 131072;
const _DEFECT_SPEC_LOCATOR_RE = /^defect:(bugzilla|zentao|zentao_story):([A-Za-z][A-Za-z0-9_]*-\d+):(title|description)$/;

export function _sha256_file(p: string): string {
  const digest = crypto.createHash("sha256");
  const fd = fs.openSync(p, "r");
  try {
    const buf = Buffer.alloc(1024 * 1024);
    let n: number;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) {
      digest.update(buf.subarray(0, n));
    }
  } finally {
    fs.closeSync(fd);
  }
  return digest.digest("hex");
}

function _path_parts(p: string): string[] {
  return p.split(/[\\/]+/).filter((part) => part !== "");
}

function _safe_file_under(p: string, root: string): string | null {
  try {
    const resolvedRoot = fs.realpathSync(root);
    const resolved = fs.realpathSync(p);
    const rel = path.relative(resolvedRoot, resolved);
    if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) {
      return null;
    }
    return fs.statSync(resolved).isFile() ? resolved : null;
  } catch {
    return null;
  }
}

function _line_locator(locator: string): [string, number | null, number | null] {
  const match = _LINE_LOCATOR_RE.exec(locator.trim());
  if (!match || match[0] !== locator.trim()) {
    return [locator.trim(), null, null];
  }
  const start = match[2] ? parseInt(match[2], 10) : null;
  const end = match[3] ? parseInt(match[3], 10) : start;
  return [match[1].trim(), start, end];
}

const _LOCATOR_ERROR_AMBIGUOUS = "ambiguous_locator";

class LocatorResolutionError extends Error {
  code: string;
  constructor(message: string, code: string = "") {
    super(message);
    this.code = String(code || "");
  }
}

function _ambiguous_locator_error(message: string): LocatorResolutionError {
  return new LocatorResolutionError(message, _LOCATOR_ERROR_AMBIGUOUS);
}

function _is_ambiguous_locator_error(error: any): boolean {
  return error instanceof LocatorResolutionError && error.code === _LOCATOR_ERROR_AMBIGUOUS;
}

function _narrow_to_bound_manual_version(candidates: string[], root: string): string[] {
  let version: string;
  try {
    const { resolve_compile_manual_version } = require("./criterion_author_rules");
    version = String(resolve_compile_manual_version() || "");
  } catch {
    return [];
  }
  if (!version) {
    return [];
  }
  const resolvedRoot = path.resolve(root);
  const narrowed: string[] = [];
  for (const candidate of candidates) {
    const rel = path.relative(resolvedRoot, candidate);
    if (rel.startsWith("..")) continue;
    if (_path_parts(rel).includes(version)) {
      narrowed.push(candidate);
    }
  }
  return narrowed;
}

function _rglob(root: string, predicate: (p: string) => boolean): string[] {
  const out: string[] = [];
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop()!;
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
      } else if (predicate(full)) {
        out.push(full);
      }
    }
  }
  return out;
}

function _unique_named_file(root: string, locator: string, opts: { suffix?: string } = {}): [string | null, any] {
  const suffix = opts.suffix || "";
  const raw = locator.trim();
  if (!raw) {
    return [null, "empty locator"];
  }
  if (path.isAbsolute(raw) || _path_parts(raw).includes("..")) {
    return [null, "absolute paths and '..' are not allowed"];
  }
  const variants = [raw];
  if (suffix && !raw.endsWith(suffix)) {
    variants.push(raw + suffix);
  }
  const directCandidates: string[] = [];
  for (const item of variants) {
    const directProject = _safe_file_under(path.join(PROJECT_ROOT, item), root);
    if (directProject !== null) {
      directCandidates.push(directProject);
    }
    const directRoot = _safe_file_under(path.join(root, item), root);
    if (directRoot !== null) {
      directCandidates.push(directRoot);
    }
  }
  const directUnique = [...new Set(directCandidates)].sort();
  if (directUnique.length === 1) {
    return [directUnique[0], ""];
  }
  if (directUnique.length > 1) {
    return [null, _ambiguous_locator_error(`source locator ${JSON.stringify(raw)} resolves to multiple explicit paths inside ${root}`)];
  }
  if (path.basename(raw) !== raw) {
    return [null, `no real source file matches explicit path ${JSON.stringify(raw)}`];
  }
  let candidates: string[] = [];
  const wanted = path.basename(raw);
  const wantedNames = new Set([wanted]);
  if (suffix && !wanted.endsWith(suffix)) {
    wantedNames.add(wanted + suffix);
  }
  try {
    for (const wantedName of wantedNames) {
      for (const candidate of _rglob(root, (p) => path.basename(p) === wantedName)) {
        const safe = _safe_file_under(candidate, root);
        if (safe === null) continue;
        candidates.push(safe);
      }
    }
    if (suffix && !wanted.endsWith(suffix)) {
      for (const candidate of _rglob(root, (p) => {
        try {
          return fs.statSync(p).isFile() && path.basename(p, path.extname(p)) === wanted;
        } catch {
          return false;
        }
      })) {
        const safe = _safe_file_under(candidate, root);
        if (safe !== null) {
          candidates.push(safe);
        }
      }
    }
  } catch {
    return [null, `source root is unreadable: ${root}`];
  }
  let unique = [...new Set(candidates)].sort();
  if (!unique.length) {
    return [null, `no real source file matches ${JSON.stringify(raw)}`];
  }
  if (unique.length > 1) {
    unique = _narrow_to_bound_manual_version(unique, root).length ? _narrow_to_bound_manual_version(unique, root) : unique;
  }
  if (unique.length === 1) {
    return [unique[0], ""];
  }
  if (unique.length > 1) {
    const shown: string[] = [];
    for (const candidate of unique.slice(0, 6)) {
      const rel = path.relative(path.resolve(root), candidate);
      if (!rel.startsWith("..")) {
        shown.push(rel.split(path.sep).join("/"));
      } else {
        shown.push(path.basename(candidate));
      }
    }
    const tail = unique.length <= 6 ? "" : ` (+${unique.length - 6} more)`;
    return [null, _ambiguous_locator_error(`source locator ${JSON.stringify(raw)} is ambiguous; use one exact root-relative path (${unique.length} matches: ${shown.join(", ")}${tail})`)];
  }
  return [unique[0], ""];
}

function _unique_named_file_across_roots(roots: string[], locator: string, opts: { suffix?: string } = {}): [string | null, string | null, any] {
  const suffix = opts.suffix || "";
  const matches: [string, string][] = [];
  for (const root of roots) {
    const [p, error] = _unique_named_file(root, locator, { suffix });
    if (p !== null) {
      matches.push([p, root]);
      continue;
    }
    if (_is_ambiguous_locator_error(error)) {
      return [null, null, error];
    }
  }
  const seen = new Map<string, [string, string]>();
  for (const [p, root] of matches) {
    try {
      seen.set(fs.realpathSync(p), [fs.realpathSync(p), fs.realpathSync(root)]);
    } catch {
      seen.set(p, [p, root]);
    }
  }
  const unique = [...seen.values()].sort((a, b) => a[0].localeCompare(b[0]));
  if (!unique.length) {
    const idx = locator.trim().lastIndexOf(":");
    const head = idx > 0 ? locator.trim().slice(0, idx) : "";
    const tail = idx > 0 ? locator.trim().slice(idx + 1) : "";
    if (head && tail && _line_locator(locator.trim())[1] === null) {
      for (const root of roots) {
        if (_unique_named_file(root, head, { suffix })[0] !== null) {
          return [null, null, `source file ${JSON.stringify(head)} exists, but ${JSON.stringify(tail)} is not a line locator; manual refs use ${_MANUAL_LOCATOR_SHAPE} — give a line number or a line range, not a section name`];
        }
      }
    }
    const searched = roots.join(" | ");
    return [null, null, `no real source file matches ${JSON.stringify(locator.trim())}; searched manual roots: ${searched}`];
  }
  if (unique.length > 1) {
    return [null, null, `source locator ${JSON.stringify(locator.trim())} is ambiguous across manual roots; use a project-relative path (hits: ` + unique.map(([p]) => p.split(path.sep).join("/")).join(" | ") + ")"];
  }
  return [unique[0][0], unique[0][1], ""];
}

function _file_receipt(opts: {
  kind: string;
  locator: string;
  path: string;
  root: string;
  line_start?: number | null;
  line_end?: number | null;
  selector?: string;
}): [Record<string, any> | null, string] {
  const line_start = opts.line_start ?? null;
  const line_end = opts.line_end ?? null;
  const selector = opts.selector || "";
  let relative: string;
  const projectResolved = path.resolve(PROJECT_ROOT);
  const relToProject = path.relative(projectResolved, opts.path);
  if (!relToProject.startsWith("..") && !path.isAbsolute(relToProject)) {
    relative = relToProject.split(path.sep).join("/");
  } else {
    relative = path.relative(path.resolve(opts.root), opts.path).split(path.sep).join("/");
  }
  const receipt: Record<string, any> = {
    kind: opts.kind,
    locator: opts.locator,
    path: relative,
    sha256: _sha256_file(opts.path),
    size: fs.statSync(opts.path).size,
  };
  if (line_start !== null) {
    let line_count: number;
    try {
      const content = fs.readFileSync(opts.path, "utf-8");
      line_count = content.split("\n").length;
    } catch (exc: any) {
      return [null, `cannot read source lines: ${exc}`];
    }
    if (line_end! < line_start) {
      return [null, `invalid descending line range ${line_start}-${line_end}`];
    }
    if (line_end! > line_count) {
      return [null, `line locator ${line_start}-${line_end} exceeds source length ${line_count}`];
    }
    receipt["line_start"] = line_start;
    receipt["line_end"] = line_end;
  }
  if (selector) {
    receipt["selector"] = selector;
  }
  return [receipt, ""];
}

function _canonical_json_sha256(value: any): string {
  return crypto.createHash("sha256").update(_canonicalJsonStringify(value), "utf-8").digest("hex");
}

function _canonicalJsonStringify(value: any): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "number" || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return "[" + value.map((item) => _canonicalJsonStringify(item)).join(",") + "]";
  }
  if (_isPlainObject(value)) {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + _canonicalJsonStringify(value[k])).join(",") + "}";
  }
  return JSON.stringify(String(value));
}

function _defect_spec_resolution_seal(receipt: Record<string, any>, opts: { create: boolean; project_root?: string | null }): string {
  const { defect_backend_lookup_is_sealable } = require("../defect_spec_source");
  if (!defect_backend_lookup_is_sealable(receipt["lookup"], { ticket_id: String(receipt["ticket_number"] || "") })) {
    return "DefectSpec resolution seal backend closure is incomplete";
  }
  let encoded: Buffer;
  try {
    encoded = Buffer.from(_canonicalJsonStringify(receipt), "utf-8");
  } catch {
    return "DefectSpec resolution seal receipt is not canonical JSON";
  }
  if (!encoded.length || encoded.length > 8 * 1024 * 1024) {
    return "DefectSpec resolution seal receipt exceeds its size boundary";
  }
  const receipt_sha = crypto.createHash("sha256").update(encoded).digest("hex");
  const seal_dir = path.join(opts.project_root || PROJECT_ROOT, "runtime", "compiler_seals", "defect_spec_resolution");
  const seal_name = `${receipt_sha}.json`;
  try {
    const directory_path = open_directory_nofollow(seal_dir, {
      errorType: Error,
      invalid_message: "DefectSpec resolution seal path is invalid",
      unavailable_message: "DefectSpec resolution seal directory is unavailable",
      preserve_missing: !opts.create,
      create_missing: opts.create,
      create_mode: 0o700,
    });
    let observed: Buffer;
    try {
      observed = read_regular_at_nofollow(directory_path, seal_name, {
        errorType: Error,
        open_message: "DefectSpec resolution seal is unavailable",
        bounds_message: "DefectSpec resolution seal is not a bounded regular file",
        changed_message: "DefectSpec resolution seal changed while being read",
        max_bytes: 8 * 1024 * 1024,
        min_bytes: 1,
        preserve_missing: true,
        require_current_uid: true,
      }) as Buffer;
    } catch (exc: any) {
      if (exc && exc.code === "ENOENT") {
        if (!opts.create) {
          return "DefectSpec resolution seal is unavailable";
        }
        const seal_path = path.join(seal_dir, seal_name);
        try {
          fs.writeFileSync(seal_path, encoded, { mode: 0o600, flag: "wx" });
        } catch (writeExc: any) {
          if (!writeExc || writeExc.code !== "EEXIST") {
            throw writeExc;
          }
        }
        observed = read_regular_at_nofollow(directory_path, seal_name, {
          errorType: Error,
          open_message: "DefectSpec resolution seal is unavailable",
          bounds_message: "DefectSpec resolution seal is not a bounded regular file",
          changed_message: "DefectSpec resolution seal changed while being read",
          max_bytes: 8 * 1024 * 1024,
          min_bytes: 1,
          require_current_uid: true,
        }) as Buffer;
      } else {
        throw exc;
      }
    }
    if (!observed.equals(encoded)) {
      return "DefectSpec resolution seal identity drift";
    }
    return "";
  } catch (exc: any) {
    if (exc && exc.code === "ENOENT") {
      return "DefectSpec resolution seal is unavailable";
    }
    return String(exc && exc.message ? exc.message : exc) || "DefectSpec resolution seal is unavailable";
  }
}

export function seal_defect_spec_resolution_receipt(receipt: Record<string, any>, opts: { project_root?: string | null } = {}): string {
  return _defect_spec_resolution_seal(receipt, { create: true, project_root: opts.project_root ?? null });
}

function _reject_duplicate_keys_local(pairs: [string, any][]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [k, v] of pairs) {
    if (Object.prototype.hasOwnProperty.call(out, k)) {
      throw new Error(`duplicate key ${JSON.stringify(k)}`);
    }
    out[k] = v;
  }
  return out;
}

function _parseJsonStrict(text: string): any {
  return JSON.parse(text, (function () {
    const seen = new Set<string>();
    return function (this: any, key: string, value: any) {
      if (_isPlainObject(value)) {
        const keys = Object.keys(value);
        if (new Set(keys).size !== keys.length) {
          throw new Error(`duplicate key ${JSON.stringify(key)}`);
        }
      }
      return value;
    };
  })());
}

function _immutable_seal(opts: {
  family: string;
  scope_key: string;
  item_key: string;
  payload: Record<string, any>;
  label: string;
  create: boolean;
  allow_missing?: boolean;
  observed_sink?: Record<string, any> | null;
  observation_sink?: Record<string, any> | null;
  project_root?: string | null;
}): string {
  const allow_missing = opts.allow_missing ?? false;
  const root = opts.project_root != null ? path.resolve(opts.project_root) : PROJECT_ROOT;
  const seal_dir = path.join(root, "runtime", "compiler_seals", opts.family, opts.scope_key);
  const seal_name = `${opts.item_key}.json`;
  const encoded = Buffer.from(_canonicalJsonStringify(opts.payload), "utf-8");
  const subject: Record<string, any> = {
    kind: "compiler_seal",
    family: opts.family,
    scope_key: opts.scope_key,
    item_key: opts.item_key,
    expected_sha256: crypto.createHash("sha256").update(encoded).digest("hex"),
  };
  if (opts.observation_sink != null) {
    Object.assign(opts.observation_sink, { check: "immutable_seal_access", outcome: "unavailable", subject });
  }
  try {
    const directory_path = open_directory_nofollow(seal_dir, {
      errorType: Error,
      invalid_message: `${opts.label} seal path is invalid`,
      unavailable_message: `${opts.label} seal directory is unavailable`,
      preserve_missing: !opts.create,
      create_missing: opts.create,
      create_mode: 0o700,
    });
    let observed: Buffer;
    try {
      observed = read_regular_at_nofollow(directory_path, seal_name, {
        errorType: Error,
        open_message: `${opts.label} seal is unavailable`,
        bounds_message: `${opts.label} seal is not a bounded regular file`,
        changed_message: `${opts.label} seal changed while being read`,
        max_bytes: 64 * 1024,
        min_bytes: 1,
        preserve_missing: true,
        require_current_uid: true,
      }) as Buffer;
    } catch (exc: any) {
      if (exc && exc.code === "ENOENT") {
        if (!opts.create) {
          return allow_missing ? "" : `${opts.label} seal is unavailable`;
        }
        const seal_path = path.join(seal_dir, seal_name);
        try {
          fs.writeFileSync(seal_path, encoded, { mode: 0o600, flag: "wx" });
        } catch (writeExc: any) {
          if (!writeExc || writeExc.code !== "EEXIST") {
            throw writeExc;
          }
        }
        observed = read_regular_at_nofollow(directory_path, seal_name, {
          errorType: Error,
          open_message: `${opts.label} seal is unavailable`,
          bounds_message: `${opts.label} seal is not a bounded regular file`,
          changed_message: `${opts.label} seal changed while being read`,
          max_bytes: 64 * 1024,
          min_bytes: 1,
          require_current_uid: true,
        }) as Buffer;
      } else {
        throw exc;
      }
    }
    subject["stored_sha256"] = crypto.createHash("sha256").update(observed).digest("hex");
    if (!observed.equals(encoded)) {
      if (opts.observation_sink != null) {
        Object.assign(opts.observation_sink, { check: "immutable_seal_identity", outcome: "different_bytes" });
      }
      if (opts.observed_sink != null) {
        let existing: any;
        try {
          existing = JSON.parse(observed.toString("utf-8"));
          if (_isPlainObject(existing)) {
            const checkDup = (obj: any): void => {
              if (_isPlainObject(obj)) {
                for (const v of Object.values(obj)) checkDup(v);
              } else if (Array.isArray(obj)) {
                for (const v of obj) checkDup(v);
              }
            };
            checkDup(existing);
          }
        } catch (parseExc: any) {
          if (opts.observation_sink != null) {
            Object.assign(opts.observation_sink, { check: "immutable_seal_json", outcome: "invalid" });
            subject["error_type"] = parseExc && parseExc.constructor ? parseExc.constructor.name : "Error";
          }
          return `${opts.label} seal JSON is invalid: ${parseExc}`;
        }
        if (!_isPlainObject(existing)) {
          if (opts.observation_sink != null) {
            Object.assign(opts.observation_sink, { check: "immutable_seal_json", outcome: "not_object" });
          }
          return `${opts.label} seal JSON must be an object`;
        }
        Object.assign(opts.observed_sink, existing);
      }
      return `${opts.label} seal identity drift`;
    }
    return "";
  } catch (exc: any) {
    if (exc && exc.code === "ENOENT") {
      return allow_missing ? "" : `${opts.label} seal is unavailable`;
    }
    return String(exc && exc.message ? exc.message : exc) || `${opts.label} seal is unavailable`;
  }
}

function _defect_spec_compilation_seal(compilation: Record<string, any>, opts: { create: boolean; allow_missing?: boolean }): string {
  const allow_missing = opts.allow_missing ?? false;
  const autoid = String(compilation["autoid"] || "").trim();
  const expectation_id = String(compilation["expectation_id"] || "").trim();
  const claim_sha256 = String(compilation["claim_sha256"] || "").trim();
  if (!autoid || path.basename(autoid) !== autoid || !expectation_id || !/^[0-9a-f]{64}$/.test(claim_sha256)) {
    return "DefectSpec compilation seal identity is invalid";
  }
  return _immutable_seal({
    family: "defect_spec",
    scope_key: crypto.createHash("sha256").update(autoid, "utf-8").digest("hex"),
    item_key: crypto.createHash("sha256").update(`${expectation_id} ${claim_sha256}`, "utf-8").digest("hex"),
    payload: compilation,
    label: "DefectSpec compilation",
    create: opts.create,
    allow_missing,
  });
}

function _validate_defect_spec_expected_receipt(step: StepIR, opts: { resolver_receipt?: Record<string, any> | null; require_value_match?: boolean } = {}): [Record<string, any> | null, string] {
  const resolver_receipt = opts.resolver_receipt ?? null;
  const require_value_match = opts.require_value_match ?? true;
  const supplied = resolver_receipt !== null ? resolver_receipt : step.source.receipt;
  if (!_isPlainObject(supplied) || !Object.keys(supplied).length) {
    return [null, "DefectSpec requires the complete engine-resolved receipt"];
  }
  const match = _DEFECT_SPEC_LOCATOR_RE.exec(String(step.source.ref || "").trim());
  if (match === null) {
    return [null, "DefectSpec source.ref must be defect:<backend>:<ticket-id>:<title|description>"];
  }
  const locator_backend = match[1];
  const locator_ticket_id = match[2];
  const field = match[3];
  const top_keys = new Set(["schema", "status", "eligible", "authority_group", "reason", "ticket_number", "source_sha256", "source_content_sha256", "source_context", "selection", "ticket", "projection", "projection_sha256", "candidates", "lookup"]);
  if (!top_keys.size || Object.keys(supplied).length !== top_keys.size || !Object.keys(supplied).every((k) => top_keys.has(k))) {
    return [null, "DefectSpec resolver receipt fields are not closed"];
  }
  const ticket = supplied["ticket"];
  const projection = supplied["projection"];
  const lookup = supplied["lookup"];
  const selection = supplied["selection"];
  const ticket_keys = new Set(["backend", "ticket_id", "doc_type", "product", "status", "affected_versions", "fixed_versions", "ticket_sha256"]);
  const projection_keys = new Set(["authority_group", "backend", "ticket_id", "doc_type", "product", "status", "affected_versions", "fixed_versions", "title", "description"]);
  const selection_keys = new Set(["reason", "score", "title_score", "semantic_score", "runner_up_score", "margin"]);
  const keysMatch = (obj: any, keys: Set<string>) => _isPlainObject(obj) && Object.keys(obj).length === keys.size && Object.keys(obj).every((k) => keys.has(k));
  if (
    supplied["schema"] !== _DEFECT_SPEC_RECEIPT_SCHEMA ||
    supplied["status"] !== "resolved" ||
    supplied["eligible"] !== true ||
    supplied["authority_group"] !== "spec" ||
    !keysMatch(ticket, ticket_keys) ||
    !keysMatch(projection, projection_keys) ||
    !keysMatch(selection, selection_keys) ||
    !_isPlainObject(lookup) ||
    !Array.isArray(supplied["candidates"])
  ) {
    return [null, "DefectSpec resolver receipt is not an eligible resolved declaration"];
  }
  const { defect_backend_lookup_is_sealable } = require("../defect_spec_source");
  if (!defect_backend_lookup_is_sealable(lookup, { ticket_id: String(supplied["ticket_number"] || "") })) {
    return [null, "DefectSpec resolver backend closure is incomplete"];
  }
  const ticket_backend = String(ticket["backend"] || "").trim().toLowerCase();
  const ticket_id = String(ticket["ticket_id"] || "").trim();
  const ticket_sha = String(ticket["ticket_sha256"] || "");
  const source_sha = String(supplied["source_sha256"] || "");
  const source_content_sha = String(supplied["source_content_sha256"] || "");
  const source_context = supplied["source_context"];
  if (
    ticket_backend !== locator_backend ||
    ticket_id !== locator_ticket_id ||
    String(projection["backend"] || "").trim().toLowerCase() !== ticket_backend ||
    String(projection["ticket_id"] || "").trim() !== ticket_id ||
    projection["authority_group"] !== "spec" ||
    ["doc_type", "product", "status", "affected_versions", "fixed_versions"].some((key) => JSON.stringify(projection[key]) !== JSON.stringify(ticket[key])) ||
    !/^[0-9a-f]{64}$/.test(ticket_sha) ||
    !/^[0-9a-f]{64}$/.test(source_sha) ||
    !/^[0-9a-f]{64}$/.test(source_content_sha) ||
    !_isPlainObject(source_context) ||
    String(supplied["projection_sha256"] || "") !== _canonical_json_sha256(projection)
  ) {
    return [null, "DefectSpec locator or resolver identity drift"];
  }
  const declared = projection[field];
  if (typeof declared !== "string" || !declared.trim()) {
    return [null, "DefectSpec selected declaration field is empty"];
  }
  if (contains_prohibited_declaration(declared)) {
    return [null, "DefectSpec actual/reproduction/log/comment text cannot sign expected"];
  }
  if (require_value_match && step.G !== declared) {
    return [null, "DefectSpec expected value must byte-match the selected safe projection field"];
  }
  let source_scope: any;
  try {
    source_scope = output_scope();
  } catch (exc: any) {
    if (exc && (exc.code === "EPERM" || exc.code === "EACCES")) {
      return [null, "DefectSpec source scope is unavailable"];
    }
    throw exc;
  }
  const source_root = scope_bucket(WORKSPACE_INPUTS, { scope: source_scope } as any);
  let source_current = false;
  let source_budget_exceeded = false;
  let source_candidates_seen = 0;
  let source_bytes_seen = 0;
  try {
    for (const candidate_path of _rglob(source_root, () => true)) {
      source_candidates_seen += 1;
      if (source_candidates_seen > _DEFECT_SPEC_MAX_SOURCE_CANDIDATES) {
        source_budget_exceeded = true;
        break;
      }
      let candidate_bytes: Buffer;
      try {
        candidate_bytes = read_regular_nofollow(candidate_path, {
          errorType: Error,
          invalid_message: "DefectSpec source path is invalid",
          directory_message: "DefectSpec source directory is unavailable",
          open_message: "DefectSpec source is unavailable or is a symlink",
          bounds_message: "DefectSpec source is not a bounded regular file",
          changed_message: "DefectSpec source changed while being read",
          max_bytes: _DEFECT_SPEC_MAX_SOURCE_BYTES,
          min_bytes: 1,
          trusted_root: source_root,
          require_current_uid: true,
        } as any) as Buffer;
      } catch {
        continue;
      }
      source_bytes_seen += candidate_bytes.length;
      if (source_bytes_seen > _DEFECT_SPEC_MAX_SOURCE_TOTAL_BYTES) {
        source_budget_exceeded = true;
        break;
      }
      if (crypto.createHash("sha256").update(candidate_bytes).digest("hex") === source_sha) {
        if (!validate_source_context_binding(candidate_bytes, source_sha, source_context, source_content_sha)) {
          return [null, "DefectSpec sealed source context drift"];
        }
        source_current = true;
        break;
      }
    }
  } catch {
    source_current = false;
  }
  if (source_budget_exceeded) {
    return [null, "DefectSpec sealed source search budget exceeded"];
  }
  if (!source_current) {
    return [null, "DefectSpec sealed source identity drift"];
  }
  const defect_dir = ticket_backend === "zentao_story" ? "zentao" : ticket_backend;
  const ticket_path = path.join(WORKSPACE_DEFECTS, defect_dir, `${ticket_id}.json`);
  let ticket_bytes: Buffer;
  try {
    ticket_bytes = read_regular_nofollow(ticket_path, {
      errorType: Error,
      invalid_message: "DefectSpec ticket path is invalid",
      directory_message: "DefectSpec ticket directory is unavailable",
      open_message: "DefectSpec ticket is unavailable or is a symlink",
      bounds_message: "DefectSpec ticket is not a bounded regular file",
      changed_message: "DefectSpec ticket changed while being read",
      max_bytes: _DEFECT_SPEC_MAX_TICKET_BYTES,
      min_bytes: 1,
      trusted_root: WORKSPACE_DEFECTS,
      require_current_uid: true,
    } as any) as Buffer;
  } catch {
    return [null, "DefectSpec ticket source is unavailable"];
  }
  if (crypto.createHash("sha256").update(ticket_bytes).digest("hex") !== ticket_sha) {
    return [null, "DefectSpec sealed ticket identity drift"];
  }
  try {
    validate_json_budget(ticket_bytes, { max_depth: _DEFECT_SPEC_MAX_TICKET_JSON_DEPTH, max_tokens: _DEFECT_SPEC_MAX_TICKET_JSON_TOKENS } as any);
  } catch {
    return [null, "DefectSpec ticket payload exceeds its budget"];
  }
  return [{ ...supplied }, ""];
}

export function validate_defect_spec_claim(claim: any, opts: { autoid: string; expectation_id: string; semantic_key: string }): [Record<string, any> | null, string] {
  const autoid = String(opts.autoid || "").trim();
  const expectation_id = String(opts.expectation_id || "").trim();
  const semantic_key = String(opts.semantic_key || "").trim();
  const body_keys = new Set(["schema", "kind", "autoid", "expectation_id", "semantic_key", "origin", "source_text", "source_sha256"]);
  if (!_isPlainObject(claim)) {
    return [null, "DefectSpec claim is malformed"];
  }
  const claimKeys = new Set(Object.keys(claim));
  const expectedKeys = new Set([...body_keys, "claim_sha256"]);
  if (claimKeys.size !== expectedKeys.size || ![...claimKeys].every((k) => expectedKeys.has(k))) {
    return [null, "DefectSpec claim shape is not closed"];
  }
  const claim_sha256 = String(claim["claim_sha256"] || "");
  if (
    !accepts_schema(claim["schema"], "ist.defect-spec-claim") ||
    claim["kind"] !== "DefectSpec" ||
    String(claim["autoid"] || "") !== autoid ||
    String(claim["expectation_id"] || "") !== expectation_id ||
    String(claim["semantic_key"] || "") !== semantic_key ||
    !String(claim["origin"] || "").trim() ||
    !String(claim["source_text"] || "").trim() ||
    !/^[0-9a-f]{64}$/.test(String(claim["source_sha256"] || "")) ||
    !/^[0-9a-f]{64}$/.test(claim_sha256)
  ) {
    return [null, "DefectSpec claim identity is invalid"];
  }
  const body: Record<string, any> = {};
  for (const key of body_keys) {
    body[key] = claim[key];
  }
  if (_canonical_json_sha256(body) !== claim_sha256) {
    return [null, "DefectSpec claim digest drift"];
  }
  const resolver_receipt = claim["resolver_receipt"];
  const resolver_receipt_sha256 = String(claim["resolver_receipt_sha256"] || "");
  if (!_isPlainObject(resolver_receipt) || !/^[0-9a-f]{64}$/.test(resolver_receipt_sha256) || _canonical_json_sha256(resolver_receipt) !== resolver_receipt_sha256) {
    return [null, "DefectSpec claim resolver receipt is invalid"];
  }
  return [{ ...claim, resolver_receipt, resolver_receipt_sha256 }, ""];
}

const _CONFIG_BINDING_RULE_LOGIC: Record<string, Record<string, string[]>> = {
  "config.literal-copy": { "main/case_compiler/provenance_ir.py": ["_derive_rule_config_literal_copy"] },
  "config.fixture-literal-backref": { "main/case_compiler/provenance_ir.py": ["_derive_rule_config_fixture_literal_backref"] },
  "capture.static-relation": { "main/case_compiler/provenance_ir.py": ["_derive_rule_capture_static_relation"] },
  "capture.static-reference": { "main/case_compiler/provenance_ir.py": ["_derive_rule_capture_static_reference"] },
  "distribution.interval": { "main/case_compiler/distribution_assertion.py": ["_derive_rule_distribution_interval"] },
  "membership.literal-set": { "main/case_compiler/membership_assertion.py": ["_derive_rule_membership_literal_set"] },
  "status.exit-code": { "main/case_compiler/provenance_ir.py": ["exit_status_assertion", "_transport_failure_pattern"] },
};

interface _RuleLogicUnit {
  path: string;
  name: string;
  text: string;
}

function _strip_python_comments_and_docstrings(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inTriple: string | null = null;
  for (const line of lines) {
    let work = line;
    if (inTriple !== null) {
      const idx = work.indexOf(inTriple);
      if (idx === -1) {
        out.push("");
        continue;
      }
      work = work.slice(idx + inTriple.length);
      inTriple = null;
    }
    let result = "";
    let i = 0;
    let quote: string | null = null;
    while (i < work.length) {
      const ch = work[i];
      if (quote !== null) {
        result += ch;
        if (ch === "\\") {
          if (i + 1 < work.length) {
            result += work[i + 1];
            i += 2;
            continue;
          }
        } else if (ch === quote) {
          quote = null;
        }
        i += 1;
        continue;
      }
      if (work.startsWith('"""', i) || work.startsWith("'''", i)) {
        const q = work.slice(i, i + 3);
        const close = work.indexOf(q, i + 3);
        if (close === -1) {
          inTriple = q;
          i = work.length;
        } else {
          i = close + 3;
        }
        continue;
      }
      if (ch === '"' || ch === "'") {
        quote = ch;
        result += ch;
        i += 1;
        continue;
      }
      if (ch === "#") {
        break;
      }
      result += ch;
      i += 1;
    }
    out.push(result.replace(/\s+$/, ""));
  }
  return out.join("\n");
}

function _extract_python_top_level_defs(text: string): Map<string, string> {
  const defs = new Map<string, string>();
  const lines = text.split("\n");
  const startRe = /^(def |class |[A-Za-z_][A-Za-z0-9_]*\s*(?::[^=]*)?=)/;
  let currentName: string | null = null;
  let currentLines: string[] = [];
  const flush = () => {
    if (currentName !== null) {
      defs.set(currentName, currentLines.join("\n"));
    }
  };
  for (const line of lines) {
    if (line.length && !/^\s/.test(line) && startRe.test(line)) {
      flush();
      const m = /^(?:def |class )?([A-Za-z_][A-Za-z0-9_]*)/.exec(line);
      currentName = m ? m[1] : null;
      currentLines = [line];
      continue;
    }
    if (currentName !== null) {
      if (line.trim() === "") {
        currentLines.push(line);
      } else if (/^\s/.test(line)) {
        currentLines.push(line);
      } else {
        flush();
        currentName = null;
        currentLines = [];
      }
    }
  }
  flush();
  return defs;
}

function _python_referenced_names(text: string): Set<string> {
  const names = new Set<string>();
  const re = /[A-Za-z_][A-Za-z0-9_]*/g;
  let m: RegExpExecArray | null;
  const keywords = new Set([
    "def", "class", "return", "if", "elif", "else", "for", "while", "in", "not", "and", "or",
    "is", "None", "True", "False", "import", "from", "as", "with", "try", "except", "finally",
    "raise", "lambda", "yield", "pass", "break", "continue", "del", "global", "nonlocal", "assert", "async", "await",
  ]);
  while ((m = re.exec(text)) !== null) {
    if (!keywords.has(m[0])) {
      names.add(m[0]);
    }
  }
  return names;
}

function _config_binding_logic_analysis(rule_id: string): [{ closures: Record<string, Record<string, string>>; externals: Set<string> } | null, string] {
  const units = _CONFIG_BINDING_RULE_LOGIC[rule_id];
  if (units == null) {
    return [null, "derivation rule has no registered logic unit"];
  }
  const closures: Record<string, Record<string, string>> = {};
  const externals = new Set<string>();
  for (const [rel_path, entries] of Object.entries(units)) {
    const abs = path.join(_CODE_ROOT, ...rel_path.split("/"));
    let raw: string;
    try {
      raw = fs.readFileSync(abs, "utf-8");
    } catch {
      return [null, `derivation rule logic source is unavailable: ${rel_path}`];
    }
    const cleaned = _strip_python_comments_and_docstrings(raw);
    const defs = _extract_python_top_level_defs(cleaned);
    const closure: Record<string, string> = {};
    const worklist = [...entries];
    for (const entry of entries) {
      if (!defs.has(entry)) {
        return [null, `derivation rule entry point ${JSON.stringify(entry)} is missing from ${rel_path}`];
      }
    }
    while (worklist.length) {
      const name = worklist.pop()!;
      if (name in closure) continue;
      const node = defs.get(name);
      if (node === undefined) {
        externals.add(`::${name}`);
        continue;
      }
      closure[name] = node;
      for (const ref of _python_referenced_names(node)) {
        if (!(ref in closure)) {
          worklist.push(ref);
        }
      }
    }
    closures[rel_path] = closure;
  }
  for (const ext of [...externals]) {
    const head = ext.replace(/^::/, "");
    let resolved = false;
    for (const closure of Object.values(closures)) {
      if (head in closure) {
        externals.delete(ext);
        resolved = true;
        break;
      }
    }
    if (!resolved) {
    }
  }
  return [{ closures, externals }, ""];
}

function _config_binding_generator_fingerprint(rule_id: string): [string | null, string] {
  const [analysis, error] = _config_binding_logic_analysis(rule_id);
  if (analysis === null) {
    return [null, error];
  }
  const blocked = [...analysis.externals].filter((ref) => ref.startsWith("main.") || ref.startsWith("::")).sort();
  if (blocked.length) {
    return [null, "derivation rule logic reaches unregistered external reference: " + blocked.join(", ")];
  }
  const material: Record<string, string>[] = [];
  for (const [p, closure] of Object.entries(analysis.closures)) {
    for (const name of Object.keys(closure).sort()) {
      material.push({ path: p, name, ast: closure[name] });
    }
  }
  return [_canonical_json_sha256(material), ""];
}

export function derivation_output_count(kind: string, recipe_id: string): [number | null, string] {
  const source_kind = String(kind || "").trim();
  const rule_id = String(recipe_id || "").trim();
  const rules = _CONFIG_BINDING_RULES[source_kind];
  if (!rules || !rules.has(rule_id)) {
    return [null, `unknown ConfigBinding derivation source.kind=${source_kind} recipe=${rule_id}`];
  }
  const [output_count, error] = _derive_rule_output_count(rule_id);
  if (output_count === null) {
    return [null, error];
  }
  return [output_count, ""];
}

function _derive_rule_output_count(rule_id: string): [number | null, string] {
  const producers: Record<string, (input: Record<string, any>) => [any[] | null, string]> = {
    "config.literal-copy": _derive_rule_config_literal_copy,
    "config.fixture-literal-backref": _derive_rule_config_fixture_literal_backref,
    "capture.static-relation": _derive_rule_capture_static_relation,
    "capture.static-reference": _derive_rule_capture_static_reference,
    "distribution.interval": (input) => {
      const mod = require("./distribution_assertion");
      return mod._derive_rule_distribution_interval(input);
    },
    "membership.literal-set": (input) => {
      const mod = require("./membership_assertion");
      return mod._derive_rule_membership_literal_set(input);
    },
    "status.exit-code": _derive_rule_status_exit_code,
  };
  const producer = producers[rule_id];
  if (!producer) {
    return [null, `derivation rule ${JSON.stringify(rule_id)} has no registered producer`];
  }
  const [outputs, error] = producer({});
  if (outputs === null) {
    if (error.includes("source_input")) {
      return [1, ""];
    }
    return [null, error];
  }
  return [outputs.length, ""];
}

function _derive_rule_config_literal_copy(input: Record<string, any>): [any[] | null, string] {
  const value = String(input["value"] ?? "");
  if (!("value" in input)) {
    return [null, "config.literal-copy source_input requires value"];
  }
  return [[{ E: "check_point", F: "found", G: value }], ""];
}

function _derive_rule_config_fixture_literal_backref(input: Record<string, any>): [any[] | null, string] {
  const fixture = String(input["fixture"] || "").trim();
  const literal = String(input["literal"] ?? "");
  if (!fixture || !("literal" in input)) {
    return [null, "config.fixture-literal-backref source_input requires fixture and literal"];
  }
  return [[{ E: "check_point", F: "found", G: literal }], ""];
}

function _derive_rule_capture_static_relation(input: Record<string, any>): [any[] | null, string] {
  const relation = String(input["relation"] || "").trim();
  if (!relation) {
    return [null, "capture.static-relation source_input requires relation"];
  }
  const allowed = new Set(["same", "different"]);
  if (!allowed.has(relation)) {
    return [null, `capture.static-relation relation must be one of ${[...allowed].sort().join(", ")}`];
  }
  return [[{ E: "check_point", F: relation === "same" ? "found" : "not_found", G: relation }], ""];
}

function _derive_rule_capture_static_reference(input: Record<string, any>): [any[] | null, string] {
  const reference = String(input["reference"] || "").trim();
  if (!reference) {
    return [null, "capture.static-reference source_input requires reference"];
  }
  return [[{ E: "check_point", F: "found", G: reference }], ""];
}

function _derive_rule_status_exit_code(input: Record<string, any>): [any[] | null, string] {
  const expect = String(input["expect"] || "").trim();
  if (!expect) {
    return [null, "status.exit-code source_input requires expect"];
  }
  const probe = String(input["probe"] || "");
  const codes = Array.isArray(input["codes"]) ? input["codes"] : [];
  const [step, error] = exit_status_assertion(expect, probe, codes);
  if (step === null) {
    return [null, error];
  }
  return [[step], ""];
}

export function build_config_binding_derivation_receipt(opts: {
  source_kind: string;
  recipe_id: string;
  rule_id: string;
  source_input: Record<string, any>;
  output_step: Record<string, any>;
  output_ordinal?: any;
}): [Record<string, any> | null, string] {
  const source_kind = String(opts.source_kind || "").trim();
  const recipe_id = String(opts.recipe_id || "").trim();
  const rule_id = String(opts.rule_id || "").trim();
  const rules = _CONFIG_BINDING_RULES[source_kind];
  if (!rules || !rules.has(rule_id)) {
    return [null, `unknown ConfigBinding derivation source.kind=${source_kind} rule=${rule_id}`];
  }
  if (recipe_id !== rule_id) {
    return [null, "ConfigBinding derivation recipe_id must equal rule_id"];
  }
  const [fingerprint, fingerprint_error] = _config_binding_generator_fingerprint(rule_id);
  if (fingerprint === null) {
    return [null, fingerprint_error];
  }
  const producers: Record<string, (input: Record<string, any>) => [any[] | null, string]> = {
    "config.literal-copy": _derive_rule_config_literal_copy,
    "config.fixture-literal-backref": _derive_rule_config_fixture_literal_backref,
    "capture.static-relation": _derive_rule_capture_static_relation,
    "capture.static-reference": _derive_rule_capture_static_reference,
    "distribution.interval": (input) => require("./distribution_assertion")._derive_rule_distribution_interval(input),
    "membership.literal-set": (input) => require("./membership_assertion")._derive_rule_membership_literal_set(input),
    "status.exit-code": _derive_rule_status_exit_code,
  };
  const producer = producers[rule_id];
  if (!producer) {
    return [null, `derivation rule ${JSON.stringify(rule_id)} has no registered producer`];
  }
  const [outputs, derive_error] = producer(opts.source_input);
  if (outputs === null) {
    return [null, derive_error];
  }
  let ordinal: number;
  try {
    ordinal = Math.trunc(Number(opts.output_ordinal ?? 0));
  } catch {
    return [null, "ConfigBinding derivation output_ordinal is invalid"];
  }
  if (!Number.isInteger(ordinal) || ordinal < 0 || ordinal >= outputs.length) {
    return [null, "ConfigBinding derivation output_ordinal is out of range"];
  }
  const derived = outputs[ordinal];
  const want = {
    E: String(opts.output_step["E"] ?? ""),
    F: String(opts.output_step["F"] ?? ""),
    G: String(opts.output_step["G"] ?? ""),
  };
  if (String(derived["E"]) !== want.E || String(derived["F"]) !== want.F || String(derived["G"]) !== want.G) {
    return [null, "ConfigBinding derivation output does not match the compiled step"];
  }
  const receipt = {
    schema: _CONFIG_BINDING_DERIVATION_SCHEMA,
    source_kind,
    rule_id,
    recipe_id,
    source_input: opts.source_input,
    output_ordinal: ordinal,
    output_count: outputs.length,
    generator_fingerprint: fingerprint,
    output_step: { E: derived["E"], F: derived["F"], G: derived["G"] },
  };
  return [{ ...receipt, receipt_sha256: _canonical_json_sha256(receipt) }, ""];
}

export function reconcile_config_binding_derivation_receipt(supplied: Record<string, any>, rebuilt: Record<string, any>): [Record<string, any> | null, string] {
  const material_keys = new Set(["schema", "source_kind", "rule_id", "recipe_id", "source_input", "output_ordinal", "output_count", "generator_fingerprint", "output_step"]);
  const supplied_keys = new Set(Object.keys(supplied));
  const expected = new Set([...material_keys, "receipt_sha256"]);
  if (supplied_keys.size !== expected.size || ![...supplied_keys].every((k) => expected.has(k))) {
    return [null, "ConfigBinding derivation receipt fields are not closed"];
  }
  const material: Record<string, any> = {};
  for (const key of material_keys) {
    material[key] = supplied[key];
  }
  if (JSON.stringify(material, Object.keys(material).sort()) !== JSON.stringify(Object.fromEntries(material_keys.size ? [...material_keys].map((k) => [k, rebuilt[k]]) : []), Object.keys(rebuilt).sort())) {
  }
  for (const key of material_keys) {
    if (_canonicalJsonStringify(supplied[key]) !== _canonicalJsonStringify(rebuilt[key])) {
      return [null, "ConfigBinding derivation receipt identity drift"];
    }
  }
  const receipt_sha = String(supplied["receipt_sha256"] || "");
  if (!/^[0-9a-f]{64}$/.test(receipt_sha) || receipt_sha !== _canonical_json_sha256(material)) {
    return [null, "ConfigBinding derivation receipt digest drift"];
  }
  return [{ ...supplied }, ""];
}

function _json_contains_key(payload: any, selector: string): boolean {
  if (_isPlainObject(payload)) {
    if (Object.prototype.hasOwnProperty.call(payload, selector)) {
      return true;
    }
    for (const value of Object.values(payload)) {
      if (_json_contains_key(value, selector)) {
        return true;
      }
    }
  } else if (Array.isArray(payload)) {
    for (const value of payload) {
      if (_json_contains_key(value, selector)) {
        return true;
      }
    }
  }
  return false;
}

function _json_values_for_key(payload: any, selector: string): any[] {
  const out: any[] = [];
  if (_isPlainObject(payload)) {
    for (const [key, value] of Object.entries(payload)) {
      if (key === selector) {
        out.push(value);
      }
      out.push(..._json_values_for_key(value, selector));
    }
  } else if (Array.isArray(payload)) {
    for (const value of payload) {
      out.push(..._json_values_for_key(value, selector));
    }
  }
  return out;
}

function _intent_selectors(payload: any): string[] {
  const out: string[] = [];
  const walk = (node: any) => {
    if (_isPlainObject(node)) {
      for (const [key, value] of Object.entries(node)) {
        out.push(key);
        walk(value);
      }
    } else if (Array.isArray(node)) {
      for (const value of node) {
        walk(value);
      }
    }
  };
  walk(payload);
  return out;
}

function _step_redeems_author_claim(step: StepIR): boolean {
  return Boolean(step.expectation_id && step.semantic_key && step.E.trim() === "check_point");
}

function _intent_on_non_assertion(step: StepIR, locator: string, opts: { selector_resolves: boolean }): string {
  const selector_state = opts.selector_resolves ? "resolves" : "does not resolve";
  return `source.kind=intent with ref ${JSON.stringify(locator)} ${selector_state}, but step E=${JSON.stringify(step.E)} is not a check_point assertion carrying expectation_id/semantic_key; intent sourcing redeems a stamped expected assertion and cannot drive an action or environment step`;
}

function _validate_capability_xml_expected_receipt(step: StepIR): [Record<string, any> | null, string] {
  const supplied = step.source.receipt;
  if (!_isPlainObject(supplied) || !Object.keys(supplied).length) {
    return [null, "CapabilityXml expected receipt is unavailable; generation is pending G6"];
  }
  return [{ ...supplied }, ""];
}

export function resolve_source_receipt(case_: CaseProvenance, step: StepIR, opts: { outputs_root?: string | null } = {}): [Record<string, any> | null, string] {
  const outputs_root = opts.outputs_root ?? null;
  const kind = String(step.source.kind || "");
  const locator = String(step.source.ref || "").trim();
  if (kind === "manual") {
    const [name, line_start, line_end] = _line_locator(locator);
    const [p, source_root, error] = _unique_named_file_across_roots([KNOWLEDGE_MANUAL, KNOWLEDGE_MARKDOWN], name, { suffix: ".md" });
    if (p === null) {
      return [null, `${error}. Manual refs use ${_MANUAL_LOCATOR_SHAPE}; line ranges use a hyphen, comma-separated line lists are not supported, and distinct source locations must be split across steps`];
    }
    return _file_receipt({ kind, locator, path: p, root: source_root || KNOWLEDGE_MARKDOWN, line_start, line_end });
  }
  if (kind === "spec") {
    const [name, line_start, line_end] = _line_locator(locator);
    let generation: any;
    try {
      generation = resolve_active_spec_generation();
    } catch (exc) {
      if (exc instanceof SpecGenerationUnavailable) {
        return [null, `active spec generation is unavailable: ${exc}`];
      }
      throw exc;
    }
    const [p, error] = _unique_named_file(generation.docs, name, { suffix: ".md" });
    if (p === null) {
      return [null, `${error}. Spec refs use spec:<file-or-unique-stem>[:<line>|:<line-start>-<line-end>] against the active spec generation`];
    }
    const [receipt, receipt_error] = _file_receipt({ kind, locator, path: p, root: generation.docs, line_start, line_end });
    if (receipt === null) {
      return [null, receipt_error];
    }
    receipt["generation_id"] = generation.generation_id;
    receipt["manifest_sha256"] = generation.manifest_sha256;
    return [receipt, ""];
  }
  if (kind === "defect_spec") {
    const supplied = step.source.receipt;
    if (!_isPlainObject(supplied)) {
      return [null, "DefectSpec resolver receipt is unavailable"];
    }
    const supplied_compilation = supplied["defect_spec_compilation"];
    const resolver_receipt: Record<string, any> = {};
    for (const [key, value] of Object.entries(supplied)) {
      if (key !== "defect_spec_compilation") resolver_receipt[key] = value;
    }
    const root = outputs_root !== null ? path.resolve(outputs_root) : _scoped_outputs_root();
    const autoid = String(case_.autoid || "").trim();
    const intent_candidate = path.join(root, autoid, "intent.json");
    const intent_path = autoid && path.basename(autoid) === autoid ? _safe_file_under(intent_candidate, root) : null;
    let payload: Record<string, any> = {};
    if (intent_path !== null) {
      const [read_intent_json, ContractError] = _read_intent_json_lazy();
      try {
        [payload] = read_intent_json(intent_candidate, { trusted_root: root });
      } catch (exc) {
        if (exc instanceof ContractError) {
          return [null, "DefectSpec stamped intent is unreadable"];
        }
        throw exc;
      }
    }
    const claims = payload["defect_spec_claims"];
    const claim = _isPlainObject(claims) && step.expectation_id ? claims[step.expectation_id] : null;
    if (claim == null) {
      if (supplied_compilation != null) {
        return [null, "DefectSpec compilation has no stamped claim"];
      }
      return _validate_defect_spec_expected_receipt(step, { resolver_receipt });
    }
    const [verified_claim, claim_error] = validate_defect_spec_claim(claim, { autoid, expectation_id: step.expectation_id, semantic_key: step.semantic_key });
    if (verified_claim === null) {
      return [null, claim_error];
    }
    const claim_resolver = verified_claim["resolver_receipt"];
    if (_canonicalJsonStringify(resolver_receipt) !== _canonicalJsonStringify(claim_resolver)) {
      return [null, "DefectSpec resolver receipt drifted from stamped claim"];
    }
    const [rebuilt, resolver_error] = _validate_defect_spec_expected_receipt(step, { resolver_receipt, require_value_match: false });
    if (rebuilt === null) {
      return [null, resolver_error];
    }
    if (step.E.trim() !== "check_point" || !step.F.trim() || !step.G) {
      return [null, "pending DefectSpec claim has no compiled F/G assertion"];
    }
    const material: Record<string, any> = {
      schema: "ist.defect-spec-compilation",
      autoid,
      claim_sha256: String(verified_claim["claim_sha256"]),
      resolver_receipt_sha256: String(verified_claim["resolver_receipt_sha256"]),
      expectation_id: step.expectation_id,
      semantic_key: step.semantic_key,
      operator: step.F,
      value_sha256: crypto.createHash("sha256").update(step.G, "utf-8").digest("hex"),
      source_kind: "defect_spec",
      source_ref: String(step.source.ref || "").trim(),
      status: "compiled_pre_device",
    };
    const compilation = { ...material, receipt_sha256: _canonical_json_sha256(material) };
    if (supplied_compilation != null && _canonicalJsonStringify(supplied_compilation) !== _canonicalJsonStringify(compilation)) {
      return [null, "DefectSpec compilation receipt identity drift"];
    }
    const seal_error = _defect_spec_compilation_seal(compilation, { create: false, allow_missing: true });
    if (seal_error) {
      return [null, seal_error];
    }
    return [{ ...rebuilt, defect_spec_compilation: compilation }, ""];
  }
  if (kind === "capability_xml") {
    return _validate_capability_xml_expected_receipt(step);
  }
  if (kind === "footprint") {
    let name = locator.split("#", 1)[0].trim();
    if (!name.endsWith(".json")) {
      name += ".json";
    }
    const [p, error] = _unique_named_file(KNOWLEDGE_FOOTPRINTS_NODES, name);
    if (p === null) {
      return [null, String(error)];
    }
    return _file_receipt({ kind, locator, path: p, root: KNOWLEDGE_FOOTPRINTS });
  }
  if (kind === "precedent") {
    const name = locator.split("#", 1)[0].trim();
    const [p, source_root, error] = _unique_named_file_across_roots([KNOWLEDGE_VERIFIED_PACKAGES, KNOWLEDGE_FRAMEWORK_MIRROR], name, { suffix: ".xlsx" });
    if (p === null) {
      return [null, String(error)];
    }
    return _file_receipt({ kind, locator, path: p, root: source_root || KNOWLEDGE_VERIFIED_PACKAGES });
  }
  if (kind === "env_facts") {
    const [file_part, separator, selector_raw] = [locator.split("#", 1)[0], locator.includes("#") ? "#" : "", locator.includes("#") ? locator.slice(locator.indexOf("#") + 1) : ""];
    let selector = selector_raw;
    let p: string | null;
    let error: any;
    if (separator) {
      [p, error] = _unique_named_file(KNOWLEDGE_AUTO_ENV, file_part, { suffix: ".json" });
    } else {
      selector = file_part;
      [p, error] = _unique_named_file(KNOWLEDGE_AUTO_ENV, "network_topology.json");
    }
    if (p === null) {
      return [null, String(error)];
    }
    if (selector) {
      let payload: any;
      try {
        payload = JSON.parse(fs.readFileSync(p, "utf-8"));
      } catch (exc: any) {
        return [null, `environment fact source is unreadable: ${exc}`];
      }
      if (!_json_contains_key(payload, selector)) {
        return [null, `environment fact selector ${JSON.stringify(selector)} does not exist in ${path.basename(p)}`];
      }
    }
    return _file_receipt({ kind, locator, path: p, root: KNOWLEDGE_AUTO_ENV, selector });
  }
  if (kind === "test_env_dispatch") {
    if (step.E.trim() !== "test_env") {
      return [null, "test_env_dispatch is valid only for E='test_env'"];
    }
    const dispatch_method = step.F.trim().toLowerCase();
    let allowed: Set<string>;
    let contract_digest: string;
    let contract: any;
    try {
      contract = load_excel_contract();
      allowed = new Set(contract_enabled_fs_by_e(contract)["test_env"] || []);
      contract_digest = contract_sha256(contract);
    } catch (exc) {
      if (exc instanceof ExcelContractError) {
        return [null, `enabled Excel function contract is unavailable for test_env dispatch: ${exc}`];
      }
      throw exc;
    }
    if (!allowed.size) {
      return [null, "enabled Excel function contract has no test_env dispatch methods"];
    }
    if (!allowed.has(dispatch_method)) {
      return [null, `F=${JSON.stringify(step.F)} is not an enabled Excel-contract test_env dispatch method`];
    }
    const canonical_locator = `lib/env.py#Env.${dispatch_method}`;
    if (locator !== canonical_locator) {
      return [null, `test_env_dispatch source.ref must equal the compiler-derived locator ${JSON.stringify(canonical_locator)}`];
    }
    const dispatch_sources: Record<string, string>[] = [];
    for (const rel of _TEST_ENV_DISPATCH_SOURCES) {
      const source_digest = String((contract["source_hashes"] || {})[rel] || "");
      if (!/^[0-9a-f]{64}$/.test(source_digest)) {
        return [null, `enabled Excel function contract does not close dispatch source ${JSON.stringify(rel)}`];
      }
      dispatch_sources.push({ path: rel, sha256: source_digest });
    }
    const material = Buffer.from(JSON.stringify({ E: "test_env", F: dispatch_method, G: step.G, locator: canonical_locator, excel_contract_sha256: contract_digest, sources: dispatch_sources }), "utf-8");
    return [{
      kind,
      locator: canonical_locator,
      excel_contract_sha256: contract_digest,
      dispatch_sources,
      step_sha256: crypto.createHash("sha256").update(material).digest("hex"),
      status: "mechanical_language_primitive",
    }, ""];
  }
  if (kind === "intent") {
    const root = outputs_root !== null ? path.resolve(outputs_root) : _scoped_outputs_root();
    const autoid = String(case_.autoid || "").trim();
    if (!autoid || path.basename(autoid) !== autoid) {
      return [null, "case autoid cannot identify a safe intent source"];
    }
    const intent_candidate = path.join(root, autoid, "intent.json");
    const p = _safe_file_under(intent_candidate, root);
    if (p === null) {
      return [null, `no durable intent.json exists for autoid ${JSON.stringify(autoid)}`];
    }
    const [read_intent_json, ContractError] = _read_intent_json_lazy();
    let payload: Record<string, any>;
    let intent_bytes: Buffer;
    try {
      [payload, intent_bytes] = read_intent_json(intent_candidate, { trusted_root: root });
    } catch (exc) {
      if (exc instanceof ContractError) {
        return [null, "intent source is unreadable"];
      }
      throw exc;
    }
    if (!locator || !_json_contains_key(payload, locator)) {
      if (!_step_redeems_author_claim(step)) {
        return [null, _intent_on_non_assertion(step, locator, { selector_resolves: false })];
      }
      const offered = _intent_selectors(payload);
      const hint = offered.length
        ? `; intent.json offers ${offered.slice(0, 4).map((key) => JSON.stringify(key)).join(", ")}` + (offered.length > 4 ? ` (+${offered.length - 4} more)` : "")
        : "";
      return [null, `intent selector ${JSON.stringify(locator)} does not exist in intent.json${hint}`];
    }
    let relative: string;
    const relToProject = path.relative(path.resolve(PROJECT_ROOT), p);
    if (!relToProject.startsWith("..") && !path.isAbsolute(relToProject)) {
      relative = relToProject.split(path.sep).join("/");
    } else {
      relative = path.relative(path.resolve(root), p).split(path.sep).join("/");
    }
    const receipt: Record<string, any> = {
      kind,
      locator,
      path: relative,
      sha256: crypto.createHash("sha256").update(intent_bytes).digest("hex"),
      size: intent_bytes.length,
      selector: locator,
    };
    const author_claims = payload["author_claims"];
    const claim = _isPlainObject(author_claims) ? author_claims[locator] : null;
    if (claim == null) {
      return [receipt, ""];
    }
    if (!_isPlainObject(claim)) {
      return [null, "pending Author claim in intent.json is malformed"];
    }
    if (!_step_redeems_author_claim(step)) {
      return [null, _intent_on_non_assertion(step, locator, { selector_resolves: true })];
    }
    const body_keys = new Set(["schema", "kind", "autoid", "expectation_id", "semantic_key", "origin", "source_text", "source_sha256"]);
    const claimKeys = new Set(Object.keys(claim));
    const expectedClaimKeys = new Set([...body_keys, "claim_sha256"]);
    if (claimKeys.size !== expectedClaimKeys.size || ![...claimKeys].every((k) => expectedClaimKeys.has(k))) {
      return [null, "pending Author claim shape drifted in intent.json"];
    }
    const body: Record<string, any> = {};
    for (const key of body_keys) {
      body[key] = claim[key];
    }
    const claim_sha256 = String(claim["claim_sha256"] || "");
    if (
      !accepts_schema(claim["schema"], "ist.author-claim") ||
      claim["kind"] !== "Author" ||
      String(claim["autoid"] || "") !== autoid ||
      String(claim["expectation_id"] || "") !== locator ||
      String(claim["semantic_key"] || "") !== step.semantic_key ||
      !String(claim["origin"] || "").trim() ||
      !String(claim["source_text"] || "").trim() ||
      !/^[0-9a-f]{64}$/.test(String(claim["source_sha256"] || "")) ||
      !/^[0-9a-f]{64}$/.test(claim_sha256) ||
      _canonical_json_sha256(body) !== claim_sha256
    ) {
      let problem: string;
      if (!step.semantic_key.trim()) {
        problem = "this assertion carries no expectation_id/semantic_key — write the pair minted by the typed expectation contract onto the assertion itself (the asserts[] entry, or the E=check_point combinator); the pending Author claim stamped in intent.json is the authority to copy from";
      } else {
        problem = "this assertion's identity does not match the pending Author claim stamped in intent.json — copy expectation_id and semantic_key from that claim byte-for-byte";
      }
      return [null, problem];
    }
    if (!step.F.trim() || !step.G) {
      return [null, "pending Author claim has no compiled F/G assertion"];
    }
    const material: Record<string, any> = {
      schema: "ist.author-compilation",
      claim_sha256,
      expectation_id: locator,
      semantic_key: step.semantic_key,
      operator: step.F,
      value_sha256: crypto.createHash("sha256").update(step.G, "utf-8").digest("hex"),
      source_kind: kind,
      source_ref: locator,
      intent_sha256: String(receipt["sha256"] || ""),
      status: "compiled_pre_device",
    };
    receipt["author_compilation"] = { ...material, receipt_sha256: _canonical_json_sha256(material) };
    return [receipt, ""];
  }
  if (kind === "skeleton") {
    const compile_ref = path.join(KNOWLEDGE_DATA_ROOT, "compile_ref");
    const [name, line_start, line_end] = _line_locator(locator);
    const [p, error] = _unique_named_file(compile_ref, name);
    if (p === null) {
      return [null, String(error)];
    }
    return _file_receipt({ kind, locator, path: p, root: compile_ref, line_start, line_end });
  }
  if (_DERIVED_SOURCE_KINDS.has(kind)) {
    const supplied = step.source.receipt;
    if (!_isPlainObject(supplied) || !Object.keys(supplied).length) {
      return [null, "ConfigBinding derivation receipt is required"];
    }
    const source_input = supplied["source_input"];
    if (!_isPlainObject(source_input)) {
      return [null, "ConfigBinding derivation source_input is missing"];
    }
    const [rebuilt, error] = build_config_binding_derivation_receipt({
      source_kind: kind,
      recipe_id: locator,
      rule_id: String(supplied["rule_id"] || ""),
      source_input,
      output_step: { E: step.E, F: step.F, G: step.G },
      output_ordinal: supplied["output_ordinal"] ?? 0,
    });
    if (rebuilt === null) {
      return [null, error];
    }
    return reconcile_config_binding_derivation_receipt(supplied, rebuilt);
  }
  if (kind === "device_runtime") {
    return [{ kind, locator, status: "pending_on_device_fill" }, ""];
  }
  if (kind === "emit_auto" && step.E.trim() === "time" && step.F.trim() === "sleep") {
    return [{ kind, status: "mechanical_language_primitive" }, ""];
  }
  return [null, `source.kind=${kind || "unknown"} has no resolvable receipt`];
}

export function seal_defect_spec_compilations(case_: CaseProvenance, opts: { outputs_root?: string | null } = {}): string[] {
  const problems: string[] = [];
  for (let index = 0; index < case_.steps.length; index++) {
    const step = case_.steps[index];
    if (String(step.source.kind || "") !== "defect_spec") {
      continue;
    }
    const [receipt, error] = resolve_source_receipt(case_, step, { outputs_root: opts.outputs_root ?? null });
    if (receipt === null) {
      problems.push(`step ${index}: ${error}`);
      continue;
    }
    const compilation = receipt["defect_spec_compilation"];
    if (compilation == null) {
      step.source.receipt = receipt;
      continue;
    }
    if (!_isPlainObject(compilation)) {
      problems.push(`step ${index}: DefectSpec compilation receipt is malformed`);
      continue;
    }
    const seal_error = _defect_spec_compilation_seal(compilation, { create: true });
    if (seal_error) {
      problems.push(`step ${index}: ${seal_error}`);
      continue;
    }
    step.source.receipt = receipt;
  }
  return problems;
}

const _DIRECTION_INPUT_KEYS: Record<string, string> = { "status.exit-code": "expect", "capture.static-relation": "relation" };
const _ASSERT_OPERATORS = new Set(["found", "not_found", "abs_found", "found_times"]);
const _NEGATIVE_ASSERT_OPERATORS = new Set(["not_found"]);
const _EXPECTATION_DIRECTION_SEAL_SCHEMA = "ist.expectation-direction-seal";

export function direction_family(token: string): string {
  return String(token || "").split(":", 1)[0];
}

function _directions_by_family(tokens: any): Record<string, Set<string>> {
  const grouped: Record<string, Set<string>> = {};
  for (let token of tokens || []) {
    token = String(token || "").trim();
    if (token) {
      const family = direction_family(token);
      if (!(family in grouped)) {
        grouped[family] = new Set();
      }
      grouped[family].add(token);
    }
  }
  return grouped;
}

export function direction_flip_families(sealed_tokens: any, current_tokens: any): string[] {
  const sealed = _directions_by_family(sealed_tokens);
  const current = _directions_by_family(current_tokens);
  const common = Object.keys(sealed).filter((family) => family in current);
  return common.filter((family) => {
    const a = [...sealed[family]].sort();
    const b = [...current[family]].sort();
    return a.length !== b.length || a.some((v, i) => v !== b[i]);
  }).sort();
}

export function expectation_direction(step: StepIR): string {
  if (String(step.E || "").trim() !== "check_point") {
    return "";
  }
  const receipt = step.source.receipt;
  if (_isPlainObject(receipt)) {
    const rule_id = String(receipt["rule_id"] || "").trim();
    const key = _DIRECTION_INPUT_KEYS[rule_id];
    const source_input = receipt["source_input"];
    if (key && _isPlainObject(source_input)) {
      const token = String(source_input[key] || "").trim();
      if (token) {
        return `${rule_id}:${key}=${token}`;
      }
    }
  }
  const operator = String(step.F || "").trim();
  if (_ASSERT_OPERATORS.has(operator)) {
    return _NEGATIVE_ASSERT_OPERATORS.has(operator) ? "operator:negative" : "operator:positive";
  }
  return "";
}

function _direction_token_shape_valid(token: string): boolean {
  const operator_tokens = new Set<string>([..._ASSERT_OPERATORS].map((op) => (_NEGATIVE_ASSERT_OPERATORS.has(op) ? "operator:negative" : "operator:positive")));
  if (operator_tokens.has(token)) {
    return true;
  }
  for (const [rule_id, key] of Object.entries(_DIRECTION_INPUT_KEYS)) {
    const prefix = `${rule_id}:${key}=`;
    if (!token.startsWith(prefix)) {
      continue;
    }
    const value = token.slice(prefix.length);
    if (value !== value.trim()) {
      return false;
    }
    if (rule_id === "capture.static-relation") {
      return !_derive_rule_capture_static_relation({ [key]: value })[1];
    }
    if (rule_id === "status.exit-code") {
      const { _EXIT_STATUS_EXPECTS } = require("./blocks");
      return _EXIT_STATUS_EXPECTS.includes(value);
    }
  }
  return false;
}

function _contract_author_claim_shas(contract: any, opts: { autoid: string }): Record<string, string> {
  const expectations = _isPlainObject(contract) ? contract["expectations"] : null;
  if (!Array.isArray(expectations)) {
    return {};
  }
  let _author_claim: any;
  try {
    _author_claim = require("./vk_derivation")._author_claim;
  } catch {
    return {};
  }
  const shas: Record<string, string> = {};
  for (const item of expectations) {
    if (!_isPlainObject(item)) continue;
    const claim = _author_claim(item, String(opts.autoid || ""));
    if (!_isPlainObject(claim)) continue;
    const expectation_id = String(claim["expectation_id"] || "").trim();
    const claim_sha = String(claim["claim_sha256"] || "").trim();
    if (expectation_id && /^[0-9a-f]{64}$/.test(claim_sha)) {
      shas[expectation_id] = claim_sha;
    }
  }
  return shas;
}

export function author_claim_shas(autoid: string, opts: { outputs_root?: string | null; contract?: any } = {}): Record<string, string> {
  const outputs_root = opts.outputs_root ?? null;
  const shas = _contract_author_claim_shas(opts.contract, { autoid });
  const aid = String(autoid || "").trim();
  if (!aid || path.basename(aid) !== aid) {
    return shas;
  }
  const root = outputs_root !== null ? path.resolve(outputs_root) : _scoped_outputs_root();
  const candidate = path.join(root, aid, "intent.json");
  if (_safe_file_under(candidate, root) === null) {
    return shas;
  }
  const [read_intent_json, ContractError] = _read_intent_json_lazy();
  let payload: Record<string, any>;
  try {
    [payload] = read_intent_json(candidate, { trusted_root: root });
  } catch (exc) {
    if (exc instanceof ContractError) {
      return shas;
    }
    throw exc;
  }
  const claims = _isPlainObject(payload) ? payload["author_claims"] : null;
  if (!_isPlainObject(claims)) {
    return shas;
  }
  for (const [key, claim] of Object.entries(claims)) {
    if (!_isPlainObject(claim)) continue;
    const expectation_id = String(claim["expectation_id"] || key).trim();
    const claim_sha = String(claim["claim_sha256"] || "").trim();
    if (expectation_id && /^[0-9a-f]{64}$/.test(claim_sha)) {
      shas[expectation_id] = claim_sha;
    }
  }
  return shas;
}

export const EXPECTATION_DIRECTION_FLIP_EXITS = "A signed expectation's direction is frozen at its first compile: the method may be recompiled (probe tool, observation command, host, exit-code class, operator form) but the asserted outcome may not be flipped. If this run showed the product behaving the other way, keep the assertion and attribute the case as disposition=defect_candidate with a signed expected_with_source receipt. If another signed source (spec/manual/capability_xml) states the opposite, that is a source conflict for the upstream conflict graph to reconcile, never a rewrite here.";

function _deepcopy<T>(value: T): T {
  return value === undefined ? value : JSON.parse(JSON.stringify(value));
}

export function seal_expectation_directions(case_: CaseProvenance, opts: {
  outputs_root?: string | null;
  project_root?: string | null;
  contract?: any;
  disclosures?: Record<string, any>[] | null;
  failure_observations?: Record<string, any>[] | null;
} = {}): string[] {
  const outputs_root = opts.outputs_root ?? null;
  const project_root = opts.project_root ?? null;
  const disclosures = opts.disclosures ?? null;
  const failure_observations = opts.failure_observations ?? null;
  const claim_shas = author_claim_shas(case_.autoid, { outputs_root, contract: opts.contract });
  if (!Object.keys(claim_shas).length) {
    return [];
  }
  const autoid = String(case_.autoid || "").trim();
  const grouped: Record<string, Set<string>> = {};
  const unreadable = new Set<string>();
  for (const step of case_.steps) {
    const expectation_id = String(step.expectation_id || "").trim();
    if (!(expectation_id in claim_shas)) {
      continue;
    }
    if (String(step.E || "").trim() !== "check_point") {
      continue;
    }
    if (String(step.mutation_role || "") === MUTATION_ROLE_CONTROL) {
      continue;
    }
    const direction = expectation_direction(step);
    if (direction) {
      if (!(expectation_id in grouped)) {
        grouped[expectation_id] = new Set();
      }
      grouped[expectation_id].add(direction);
    } else {
      unreadable.add(expectation_id);
    }
  }
  const problems: string[] = [];
  for (const expectation_id of Object.keys(grouped).sort()) {
    const directions = grouped[expectation_id];
    if (unreadable.has(expectation_id)) {
      continue;
    }
    const record: Record<string, any> = {
      schema: _EXPECTATION_DIRECTION_SEAL_SCHEMA,
      autoid,
      expectation_id,
      claim_sha256: claim_shas[expectation_id],
      directions: [...directions].sort(),
    };
    const sealed: Record<string, any> = {};
    const observation: Record<string, any> = {};

    const reject = (message: string, check: string = "", outcome: string = "", assertion: boolean = false): void => {
      problems.push(message);
      if (failure_observations !== null) {
        const item = _deepcopy(observation);
        if (check) item["check"] = check;
        if (outcome) item["outcome"] = outcome;
        if (!_isPlainObject(item["subject"])) item["subject"] = {};
        Object.assign(item["subject"], { expectation_id, claim_sha256: claim_shas[expectation_id] });
        if (assertion) {
          Object.assign(item["subject"], { kind: "compiled_assertion", sealed_directions: sealed["directions"], current_directions: [...directions].sort() });
        }
        failure_observations.push(item);
      }
    };

    const error = _immutable_seal({
      family: "expectation_direction",
      scope_key: crypto.createHash("sha256").update(autoid, "utf-8").digest("hex"),
      item_key: crypto.createHash("sha256").update(`${expectation_id} ${claim_shas[expectation_id]}`, "utf-8").digest("hex"),
      payload: record,
      label: "Author expectation direction",
      create: true,
      observed_sink: sealed,
      observation_sink: observation,
      project_root,
    });
    if (!error) {
      continue;
    }
    if (error === "Author expectation direction seal identity drift") {
      const was: any = sealed["directions"];
      const sealedKeys = Object.keys(sealed).sort();
      const recordKeys = Object.keys(record).sort();
      if (sealedKeys.length !== recordKeys.length || sealedKeys.some((k, i) => k !== recordKeys[i])) {
        reject("Author expectation direction seal field set is invalid", "direction_seal_fields", "invalid");
        continue;
      }
      if (!accepts_schema(sealed["schema"], _EXPECTATION_DIRECTION_SEAL_SCHEMA)) {
        reject("Author expectation direction seal schema is unsupported", "direction_seal_schema", "unsupported");
        continue;
      }
      const mismatched = ["autoid", "expectation_id", "claim_sha256"].filter((key) => _canonicalJsonStringify(sealed[key]) !== _canonicalJsonStringify(record[key]));
      if (mismatched.length) {
        if (!_isPlainObject(observation["subject"])) observation["subject"] = {};
        observation["subject"]["mismatched_fields"] = mismatched;
        reject("Author expectation direction seal identity mismatch: " + mismatched.join(", "), "direction_seal_identity", "mismatch");
        continue;
      }
      if (!Array.isArray(was) || !was.length || was.some((token: any) => typeof token !== "string" || !token.trim() || token !== token.trim() || !_direction_token_shape_valid(token)) || was.join(" ") !== [...new Set<string>(was)].sort().join(" ")) {
        reject("Author expectation direction seal directions shape is invalid", "direction_seal_tokens", "invalid");
        continue;
      }
      const changed_families = direction_flip_families(was, [...directions]);
      if (!changed_families.length) {
        continue;
      }
      const _sealed_by_family = _directions_by_family(was);
      const _current_by_family = _directions_by_family([...directions].sort());
      const capture_family = "capture.static-relation";
      const capture_changed = changed_families.includes(capture_family);
      if (capture_changed) {
        if (![..._current_by_family[capture_family]].every((token) => _direction_token_shape_valid(token))) {
          reject("Author expectation direction seal capture relation token is invalid", "capture_relation_token", "invalid", true);
          continue;
        }
      }
      const remaining_families = new Set(changed_families.filter((f) => !(capture_changed && f === capture_family)));
      const _pure_extension = [...remaining_families].every((family) => {
        const sealedSet = _sealed_by_family[family] || new Set<string>();
        const currentSet = _current_by_family[family] || new Set<string>();
        return [...sealedSet].every((t) => currentSet.has(t));
      });
      if (capture_changed || _pure_extension) {
        if (disclosures !== null) {
          disclosures.push({
            expectation_id,
            claim_sha256: claim_shas[expectation_id],
            sealed_directions: [...was],
            current_directions: [...directions].sort(),
          });
        }
        if (_pure_extension) {
          continue;
        }
      }
      const rejected_families = new Set([...remaining_families].filter((family) => {
        const sealedSet = _sealed_by_family[family];
        const currentSet = _current_by_family[family];
        return [...sealedSet].some((t) => !currentSet.has(t));
      }));
      const was_text = was.length ? was.filter((item: string) => rejected_families.has(direction_family(item))).join("/") : "a different direction";
      const now_text = [...directions].sort().filter((token) => rejected_families.has(direction_family(token))).join("/");
      const err = `expectation ${expectation_id} is now compiled asserting ${now_text}, but this claim was first compiled asserting ${was_text}. ` + EXPECTATION_DIRECTION_FLIP_EXITS;
      reject(err, "direction_restriction", "violated", true);
    } else {
      reject(error);
    }
  }
  return problems;
}

function _step_g_snippet(step: StepIR): string {
  const lines = String(step.G || "").trim().split("\n");
  const text = lines.length ? lines[0].trim() : "";
  return text.slice(0, 60) + (text.length > 60 ? "…" : "");
}

export function check_source_locators(case_: CaseProvenance, opts: { outputs_root?: string | null } = {}): string[] {
  const problems: string[] = [];
  for (let index = 0; index < case_.steps.length; index++) {
    const step = case_.steps[index];
    const kind = String(step.source.kind || "");
    const locator = String(step.source.ref || "").trim();
    const locus = `step ${index} (G=${JSON.stringify(_step_g_snippet(step))})`;
    if (kind === "intent" && !locator && !_step_redeems_author_claim(step)) {
      problems.push(`${locus}: ` + _intent_on_non_assertion(step, locator, { selector_resolves: false }));
      step.source.receipt = {};
      continue;
    }
    if (_SOURCE_LOCATOR_REQUIRED.has(kind) && !locator) {
      problems.push(`${locus}: source.kind=${kind} requires a non-empty source.ref locator`);
      step.source.receipt = {};
      continue;
    }
    const is_language_primitive = step.E.trim() === "time" && step.F.trim() === "sleep";
    if ((kind === "emit_auto" || kind === "unknown") && !is_language_primitive) {
      problems.push(`${locus}: E=${JSON.stringify(step.E)} F=${JSON.stringify(step.F)} cannot use source.kind=${kind}; every command/method/action and expected value needs a resolvable source receipt`);
      step.source.receipt = {};
      continue;
    }
    const [receipt, error] = resolve_source_receipt(case_, step, { outputs_root: opts.outputs_root ?? null });
    if (receipt === null) {
      problems.push(`${locus}: source ${kind}:${locator} does not resolve: ${error}`);
      step.source.receipt = {};
    } else if (kind === "spec" && Object.keys(step.source.receipt).length && _canonicalJsonStringify(step.source.receipt) !== _canonicalJsonStringify(receipt)) {
      problems.push(`${locus}: source spec:${locator} generation identity drift`);
    } else {
      step.source.receipt = receipt;
    }
  }
  return problems;
}

export function validate_expected_with_source(value: any): [Record<string, any> | null, string] {
  if (!_isPlainObject(value)) {
    return [null, "expected_with_source must be an object with `expected` and `source:{kind,ref}`; free text is not a source receipt"];
  }
  const expected = String(value["expected"] || "").trim();
  const source = value["source"];
  if (!expected) {
    return [null, "expected_with_source.expected is required"];
  }
  if (!_isPlainObject(source)) {
    return [null, "expected_with_source.source must be an object"];
  }
  const kind = String(source["kind"] || "").trim().toLowerCase();
  const locator = String(source["ref"] || "").trim();
  const public_to_raw: Record<string, string> = {
    author: "intent",
    intent: "intent",
    capabilityxml: "capability_xml",
    capability_xml: "capability_xml",
    defectspec: "defect_spec",
    defect_spec: "defect_spec",
    spec: "spec",
    manual: "manual",
  };
  for (const item of _DERIVED_SOURCE_KINDS) {
    public_to_raw[item] = item;
  }
  const raw_kind = public_to_raw[kind] || "";
  if (!raw_kind) {
    return [null, "product expectation source.kind must be author, spec, defect_spec, capability_xml, manual, or a verified ConfigBinding derivation; runtime/probe/observed/precedent/footprint cannot sign expected"];
  }
  const supplied_receipt = source["receipt"];
  if (raw_kind === "intent") {
    if (!_isPlainObject(supplied_receipt)) {
      return [null, "Author expected source requires its stamped intent receipt"];
    }
    if (supplied_receipt["kind"] !== "intent" || String(supplied_receipt["locator"] || "") !== locator || String(supplied_receipt["selector"] || "") !== locator) {
      return [null, "Author expected source receipt identity drift"];
    }
    const source_path = String(supplied_receipt["path"] || "").trim();
    let p: string | null = null;
    if (source_path && !path.isAbsolute(source_path) && !_path_parts(source_path).includes("..")) {
      p = _safe_file_under(path.join(PROJECT_ROOT, source_path), _scoped_outputs_root());
    }
    const source_sha = String(supplied_receipt["sha256"] || "");
    if (p === null || !/^[0-9a-f]{64}$/.test(source_sha) || _sha256_file(p) !== source_sha || fs.statSync(p).size !== supplied_receipt["size"]) {
      return [null, "Author expected source receipt does not match stamped intent"];
    }
    let payload: any;
    try {
      payload = JSON.parse(fs.readFileSync(p, "utf-8"));
    } catch {
      return [null, "Author expected source intent is unreadable"];
    }
    const [rebuilt, rebuild_error] = _file_receipt({ kind: "intent", locator, path: p, root: _scoped_outputs_root(), selector: locator });
    if (rebuilt === null) {
      return [null, rebuild_error];
    }
    const supplied_base: Record<string, any> = {};
    for (const [key, item] of Object.entries(supplied_receipt)) {
      if (key !== "author_compilation") supplied_base[key] = item;
    }
    if (_canonicalJsonStringify(supplied_base) !== _canonicalJsonStringify(rebuilt)) {
      return [null, "Author expected source receipt identity drift"];
    }
    const compilation = supplied_receipt["author_compilation"];
    if (_isPlainObject(compilation)) {
      const claims = payload["author_claims"];
      const claim = _isPlainObject(claims) ? claims[locator] : null;
      if (!_isPlainObject(claim)) {
        return [null, "Author compilation has no stamped claim"];
      }
      const claim_body_keys = new Set(["schema", "kind", "autoid", "expectation_id", "semantic_key", "origin", "source_text", "source_sha256"]);
      const claim_body: Record<string, any> = {};
      for (const key of claim_body_keys) {
        claim_body[key] = claim[key];
      }
      const claim_sha = String(claim["claim_sha256"] || "");
      const claimKeys = new Set(Object.keys(claim));
      const expectedClaimKeys = new Set([...claim_body_keys, "claim_sha256"]);
      if (
        claimKeys.size !== expectedClaimKeys.size || ![...claimKeys].every((k) => expectedClaimKeys.has(k)) ||
        !accepts_schema(claim["schema"], "ist.author-claim") ||
        claim["kind"] !== "Author" ||
        String(claim["expectation_id"] || "") !== locator ||
        !/^[0-9a-f]{64}$/.test(claim_sha) ||
        _canonical_json_sha256(claim_body) !== claim_sha
      ) {
        return [null, "Author compilation claim identity drift"];
      }
      const material_keys = new Set(["schema", "claim_sha256", "expectation_id", "semantic_key", "operator", "value_sha256", "source_kind", "source_ref", "intent_sha256", "status"]);
      const material: Record<string, any> = {};
      for (const key of material_keys) {
        material[key] = compilation[key];
      }
      const compilationKeys = new Set(Object.keys(compilation));
      const expectedCompilationKeys = new Set([...material_keys, "receipt_sha256"]);
      if (
        compilationKeys.size !== expectedCompilationKeys.size || ![...compilationKeys].every((k) => expectedCompilationKeys.has(k)) ||
        !accepts_schema(compilation["schema"], "ist.author-compilation") ||
        compilation["claim_sha256"] !== claim_sha ||
        compilation["expectation_id"] !== locator ||
        compilation["semantic_key"] !== claim["semantic_key"] ||
        !String(compilation["operator"] || "").trim() ||
        compilation["value_sha256"] !== crypto.createHash("sha256").update(expected, "utf-8").digest("hex") ||
        compilation["source_kind"] !== "intent" ||
        compilation["source_ref"] !== locator ||
        compilation["intent_sha256"] !== rebuilt["sha256"] ||
        compilation["status"] !== "compiled_pre_device" ||
        compilation["receipt_sha256"] !== _canonical_json_sha256(material)
      ) {
        return [null, "Author compilation receipt identity drift"];
      }
    } else {
      const selected = _json_values_for_key(payload, locator);
      if (!selected.length) {
        return [null, "Author expected selector is absent from stamped intent"];
      }
      const declared_values = new Set(selected.map((item: any) => (_isPlainObject(item) ? String(item["value"] || "") : String(item || ""))));
      if (!declared_values.has(expected)) {
        return [null, "Author expected value differs from stamped intent"];
      }
    }
    return [{ expected, source: { kind: "author", ref: locator, receipt: { ...supplied_receipt } } }, ""];
  }
  if (raw_kind === "defect_spec" && _isPlainObject(supplied_receipt)) {
    const compilation = supplied_receipt["defect_spec_compilation"];
    if (_isPlainObject(compilation)) {
      const resolver_receipt: Record<string, any> = {};
      for (const [key, item] of Object.entries(supplied_receipt)) {
        if (key !== "defect_spec_compilation") resolver_receipt[key] = item;
      }
      const material_keys = new Set(["schema", "autoid", "claim_sha256", "resolver_receipt_sha256", "expectation_id", "semantic_key", "operator", "value_sha256", "source_kind", "source_ref", "status"]);
      const material: Record<string, any> = {};
      for (const key of material_keys) {
        material[key] = compilation[key];
      }
      const autoid = String(compilation["autoid"] || "").trim();
      const expectation_id = String(compilation["expectation_id"] || "").trim();
      const semantic_key = String(compilation["semantic_key"] || "").trim();
      const compilationKeys = new Set(Object.keys(compilation));
      const expectedCompilationKeys = new Set([...material_keys, "receipt_sha256"]);
      if (
        compilationKeys.size !== expectedCompilationKeys.size || ![...compilationKeys].every((k) => expectedCompilationKeys.has(k)) ||
        !accepts_schema(compilation["schema"], "ist.defect-spec-compilation") ||
        !autoid ||
        path.basename(autoid) !== autoid ||
        !expectation_id ||
        !semantic_key ||
        !String(compilation["operator"] || "").trim() ||
        compilation["value_sha256"] !== crypto.createHash("sha256").update(expected, "utf-8").digest("hex") ||
        compilation["source_kind"] !== "defect_spec" ||
        compilation["source_ref"] !== locator ||
        compilation["status"] !== "compiled_pre_device" ||
        compilation["receipt_sha256"] !== _canonical_json_sha256(material)
      ) {
        return [null, "DefectSpec compilation receipt identity drift"];
      }
      const seal_error = _defect_spec_compilation_seal(compilation, { create: false });
      if (seal_error) {
        return [null, seal_error];
      }
      const outputs = _scoped_outputs_root();
      const intent_path = _safe_file_under(path.join(outputs, autoid, "intent.json"), outputs);
      if (intent_path === null) {
        return [null, "DefectSpec compilation has no stamped intent"];
      }
      const [read_intent_json, ContractError] = _read_intent_json_lazy();
      let payload: Record<string, any>;
      try {
        [payload] = read_intent_json(path.join(outputs, autoid, "intent.json"), { trusted_root: outputs });
      } catch (exc) {
        if (exc instanceof ContractError) {
          return [null, "DefectSpec compilation stamped intent is unreadable"];
        }
        throw exc;
      }
      const claims = _isPlainObject(payload) ? payload["defect_spec_claims"] : null;
      const claim = _isPlainObject(claims) ? claims[expectation_id] : null;
      const [verified_claim, claim_error] = validate_defect_spec_claim(claim, { autoid, expectation_id, semantic_key });
      if (verified_claim === null) {
        return [null, claim_error];
      }
      if (
        _canonicalJsonStringify(resolver_receipt) !== _canonicalJsonStringify(verified_claim["resolver_receipt"]) ||
        compilation["claim_sha256"] !== verified_claim["claim_sha256"] ||
        compilation["resolver_receipt_sha256"] !== verified_claim["resolver_receipt_sha256"]
      ) {
        return [null, "DefectSpec compilation claim or resolver receipt drift"];
      }
      const probe_step = new StepIR({
        E: "check_point",
        F: String(compilation["operator"]),
        G: expected,
        layer: "V",
        source: new StepSource({ kind: "defect_spec", ref: locator, receipt: { ...resolver_receipt } }),
        expectation_id,
        semantic_key,
      });
      const [rebuilt2, rebuild_error2] = _validate_defect_spec_expected_receipt(probe_step, { resolver_receipt, require_value_match: false });
      if (rebuilt2 === null) {
        return [null, rebuild_error2];
      }
      return [{ expected, source: { kind: "defect_spec", ref: locator, receipt: { ...supplied_receipt } } }, ""];
    }
  }
  const probe = new CaseProvenance({
    autoid: "product-defect-source",
    steps: [new StepIR({
      E: "check_point",
      F: "found",
      G: expected,
      layer: "V",
      source: new StepSource({ kind: raw_kind, ref: locator, receipt: _isPlainObject(supplied_receipt) ? { ...supplied_receipt } : {} }),
    })],
  });
  const problems = check_source_locators(probe);
  if (problems.length) {
    return [null, problems[0]];
  }
  const resolved = probe.steps[0].source;
  return [{ expected, source: { kind: resolved.kind === "capability_xml" ? "capability_xml" : resolved.kind, ref: resolved.ref, receipt: resolved.receipt } }, ""];
}

export function product_expected_source_is_valid(value: any): boolean {
  const [resolved, _error] = validate_expected_with_source(value);
  return resolved !== null;
}

function _nested_text_values(value: any): string[] {
  if (typeof value === "string") {
    return [value];
  }
  if (_isPlainObject(value)) {
    const result: string[] = [];
    for (const item of Object.values(value)) {
      result.push(..._nested_text_values(item));
    }
    return result;
  }
  if (Array.isArray(value)) {
    const result: string[] = [];
    for (const item of value) {
      result.push(..._nested_text_values(item));
    }
    return result;
  }
  return [];
}

function _expect_derivation_kind(expect: Record<string, any>): string | null {
  if (!("derivation" in expect)) {
    return null;
  }
  let raw = String(expect["derivation"] || "").trim();
  if (raw.startsWith("compiler-derived:")) {
    raw = raw.slice("compiler-derived:".length).trim();
  }
  return raw;
}

export function compile_assertion_types(case_: CaseProvenance, opts: { current_run_ids?: string[]; required?: boolean | null } = {}): string[] {
  const current_run_ids = opts.current_run_ids ?? [];
  let required = opts.required ?? null;
  const assertions: [number, StepIR][] = [];
  for (let index = 0; index < case_.steps.length; index++) {
    const step = case_.steps[index];
    if (step.E.trim() === "check_point") {
      assertions.push([index, step]);
    }
  }
  const typed = case_.steps.some((step) => step.assertion_type !== null);
  if (required === null) {
    required = Boolean(case_.assertion_schema || typed);
  }
  if (!required) {
    return [];
  }
  const problems: string[] = [];
  if (case_.assertion_schema !== ASSERTION_TYPE_SCHEMA) {
    problems.push(`assertion_schema must equal ${JSON.stringify(ASSERTION_TYPE_SCHEMA)} when IDE assertion types are present`);
  }
  for (let index = 0; index < case_.steps.length; index++) {
    const step = case_.steps[index];
    if (step.E.trim() !== "check_point" && step.assertion_type !== null) {
      problems.push(`step ${index}: assertion_type is only valid on check_point`);
    }
  }
  const active_run_ids = current_run_ids.map((item) => String(item || "").trim()).filter((value) => value);
  for (const [index, step] of assertions) {
    const assertion = step.assertion_type;
    if (!_isPlainObject(assertion)) {
      problems.push(`step ${index}: assertion_type is required`);
      continue;
    }
    const assertionKeys = new Set(Object.keys(assertion));
    if (assertionKeys.size !== 3 || !["expect", "flip", "form"].every((k) => assertionKeys.has(k))) {
      problems.push(`step ${index}: assertion_type must contain exactly expect/flip/form`);
      continue;
    }
    const expect = assertion["expect"];
    if (!_isPlainObject(expect)) {
      problems.push(`step ${index}: assertion_type.expect must be an object`);
    } else {
      const kind = String(expect["kind"] || "");
      const derivation = _expect_derivation_kind(expect);
      if (!_EXPECT_KINDS.has(kind)) {
        problems.push(`step ${index}: expect.kind must be Author/Manual/ConfigBinding/Spec/DefectSpec/CapabilityXml`);
      } else if (derivation !== null) {
        const expectKeys = new Set(Object.keys(expect));
        if (expectKeys.size !== 3 || !["kind", "recipe_id", "derivation"].every((k) => expectKeys.has(k))) {
          problems.push(`step ${index}: derived expect requires exactly kind/recipe_id/derivation`);
        }
        if (!String(expect["recipe_id"] || "").trim()) {
          problems.push(`step ${index}: expect.recipe_id is required`);
        }
        if (!derivation) {
          problems.push(`step ${index}: expect.derivation must name a registered derivation recipe`);
        } else {
          const authority = claim_authority_source(derivation);
          if (kind !== authority) {
            problems.push(`step ${index}: expect.kind must be ${authority} for derivation ${derivation} — the authority group and the derivation recipe are orthogonal fields`);
          }
          if (step.source.kind !== derivation) {
            problems.push(`step ${index}: expect.derivation must equal source.kind`);
          } else if (String(expect["recipe_id"] || "").trim() !== String(step.source.ref || "").trim()) {
            problems.push(`step ${index}: expect.recipe_id must equal source.ref`);
          }
        }
      } else if (kind === "ConfigBinding") {
        problems.push(`step ${index}: ConfigBinding expect requires a derivation recipe`);
      } else if (kind === "Author") {
        const expectKeys = new Set(Object.keys(expect));
        if (expectKeys.size !== 2 || !["kind", "text_hash"].every((k) => expectKeys.has(k))) {
          problems.push(`step ${index}: Author requires exactly kind/text_hash`);
        }
        const text_hash = String(expect["text_hash"] || "");
        if (!/^[0-9a-f]{64}$/.test(text_hash)) {
          problems.push(`step ${index}: Author.text_hash must be a lowercase SHA-256`);
        }
        if (step.source.kind !== "intent") {
          problems.push(`step ${index}: Author expect requires source.kind=intent`);
        }
      } else if (kind === "Manual") {
        const expectKeys = new Set(Object.keys(expect));
        const ok2 = expectKeys.size === 2 && ["kind", "locator"].every((k) => expectKeys.has(k));
        const ok3 = expectKeys.size === 3 && ["kind", "locator", "spec_gap"].every((k) => expectKeys.has(k));
        if (!ok2 && !ok3) {
          problems.push(`step ${index}: Manual requires exactly kind/locator[/spec_gap]`);
        }
        const locator = String(expect["locator"] || "").trim();
        if (!locator) {
          problems.push(`step ${index}: Manual.locator is required`);
        }
        if ("spec_gap" in expect && !String(expect["spec_gap"] || "").trim()) {
          problems.push(`step ${index}: Manual.spec_gap, when given, must state in one line why the governing spec lacks this criterion`);
        }
        if (step.source.kind !== "manual") {
          problems.push(`step ${index}: Manual expect requires source.kind=manual`);
        } else if (locator && locator !== String(step.source.ref || "").trim()) {
          problems.push(`step ${index}: Manual.locator must equal source.ref`);
        }
      } else if (kind === "Spec") {
        const expectKeys = new Set(Object.keys(expect));
        if (expectKeys.size !== 2 || !["kind", "locator"].every((k) => expectKeys.has(k))) {
          problems.push(`step ${index}: Spec requires exactly kind/locator`);
        }
        const locator = String(expect["locator"] || "").trim();
        if (!locator) {
          problems.push(`step ${index}: Spec.locator is required`);
        }
        if (step.source.kind !== "spec") {
          problems.push(`step ${index}: Spec expect requires source.kind=spec`);
        } else if (locator && locator !== String(step.source.ref || "").trim()) {
          problems.push(`step ${index}: Spec.locator must equal source.ref`);
        }
      } else if (kind === "DefectSpec") {
        const expectKeys = new Set(Object.keys(expect));
        if (expectKeys.size !== 3 || !["kind", "locator", "receipt_sha256"].every((k) => expectKeys.has(k))) {
          problems.push(`step ${index}: DefectSpec requires exactly kind/locator/receipt_sha256`);
        }
        const locator = String(expect["locator"] || "").trim();
        const receipt_sha = String(expect["receipt_sha256"] || "");
        if (!locator) {
          problems.push(`step ${index}: DefectSpec.locator is required`);
        }
        if (!/^[0-9a-f]{64}$/.test(receipt_sha)) {
          problems.push(`step ${index}: DefectSpec.receipt_sha256 must be a lowercase SHA-256`);
        }
        if (step.source.kind !== "defect_spec") {
          problems.push(`step ${index}: DefectSpec expect requires source.kind=defect_spec`);
        } else if (locator && locator !== String(step.source.ref || "").trim()) {
          problems.push(`step ${index}: DefectSpec.locator must equal source.ref`);
        }
        const receipt = step.source.receipt;
        if (!_isPlainObject(receipt) || !Object.keys(receipt).length) {
          problems.push(`step ${index}: DefectSpec resolver receipt is unavailable`);
        } else if (receipt_sha && receipt_sha !== _canonical_json_sha256(Object.fromEntries(Object.entries(receipt).filter(([key]) => key !== "defect_spec_compilation")))) {
          problems.push(`step ${index}: DefectSpec.receipt_sha256 receipt drift`);
        }
      } else if (kind === "CapabilityXml") {
        const expectKeys = new Set(Object.keys(expect));
        if (expectKeys.size !== 5 || !["kind", "locator", "device_os_build", "source_sha256", "claim_receipt_sha256"].every((k) => expectKeys.has(k))) {
          problems.push(`step ${index}: CapabilityXml requires exactly kind/locator/device_os_build/source_sha256/claim_receipt_sha256`);
        }
        const locator = String(expect["locator"] || "").trim();
        const build = String(expect["device_os_build"] || "").trim();
        const source_sha = String(expect["source_sha256"] || "");
        const claim_sha = String(expect["claim_receipt_sha256"] || "");
        if (!locator) {
          problems.push(`step ${index}: CapabilityXml.locator is required`);
        }
        if (!build) {
          problems.push(`step ${index}: CapabilityXml.device_os_build is required`);
        }
        if (!/^[0-9a-f]{64}$/.test(source_sha)) {
          problems.push(`step ${index}: CapabilityXml.source_sha256 must be a lowercase SHA-256`);
        }
        if (!/^[0-9a-f]{64}$/.test(claim_sha)) {
          problems.push(`step ${index}: CapabilityXml.claim_receipt_sha256 must be a lowercase SHA-256`);
        }
        if (step.source.kind !== "capability_xml") {
          problems.push(`step ${index}: CapabilityXml expect requires source.kind=capability_xml`);
        } else if (locator && locator !== String(step.source.ref || "").trim()) {
          problems.push(`step ${index}: CapabilityXml.locator must equal source.ref`);
        }
        const receipt = step.source.receipt;
        if (!_isPlainObject(receipt) || !Object.keys(receipt).length) {
          problems.push(`step ${index}: CapabilityXml expected receipt is unavailable; generation is pending G6`);
        } else {
          if (build && build !== String(receipt["device_os_build"] || "")) {
            problems.push(`step ${index}: CapabilityXml.device_os_build receipt drift`);
          }
          if (source_sha && source_sha !== String(receipt["sha256"] || "")) {
            problems.push(`step ${index}: CapabilityXml.source_sha256 receipt drift`);
          }
          if (claim_sha && claim_sha !== String(receipt["receipt_sha256"] || "")) {
            problems.push(`step ${index}: CapabilityXml.claim_receipt_sha256 receipt drift`);
          }
        }
      }
      const expect_texts = [String(step.source.ref || ""), ..._nested_text_values(expect)];
      for (const run_id of active_run_ids) {
        if (expect_texts.some((text) => text.includes(run_id))) {
          problems.push(`step ${index}: expect references the current case run_id`);
          break;
        }
      }
    }
    const flip = assertion["flip"];
    if (!_isPlainObject(flip)) {
      problems.push(`step ${index}: assertion_type.flip must be an object`);
    } else {
      const kind = String(flip["kind"] || "");
      if (!_FLIP_KINDS.has(kind)) {
        problems.push(`step ${index}: flip.kind must be Flipped/Exempt`);
      } else if (kind === "Flipped") {
        const flipKeys = new Set(Object.keys(flip));
        if (flipKeys.size !== 2 || !["kind", "evidence_ref"].every((k) => flipKeys.has(k))) {
          problems.push(`step ${index}: Flipped requires exactly kind/evidence_ref`);
        }
        if (!String(flip["evidence_ref"] || "").trim()) {
          problems.push(`step ${index}: Flipped.evidence_ref is required`);
        }
      } else if (kind === "Exempt") {
        const flipKeys = new Set(Object.keys(flip));
        if (flipKeys.size !== 2 || !["kind", "reason_code"].every((k) => flipKeys.has(k))) {
          problems.push(`step ${index}: Exempt requires exactly kind/reason_code`);
        }
        const reason_code = String(flip["reason_code"] || "").trim();
        if (!EXEMPT_REASON_CODES.has(reason_code)) {
          problems.push(`step ${index}: Exempt.reason_code must be one of ${[...EXEMPT_REASON_CODES].sort().join(", ")}`);
        } else if (reason_code === "direction_review_pending") {
          problems.push(`step ${index}: Exempt.reason_code 'direction_review_pending' is a deferral, not a justification — finish the direction review first, or provide real flip evidence`);
        }
      }
    }
    const form = assertion["form"];
    if (!_isPlainObject(form) || Object.keys(form).length !== 1 || form["kind"] !== _FORM_KIND) {
      problems.push(`step ${index}: form must equal {'kind': '${_FORM_KIND}'}`);
    }
  }
  return problems;
}

export function synthesize_assertion_types(case_: CaseProvenance): string[] {
  const problems: string[] = [];
  for (let index = 0; index < case_.steps.length; index++) {
    const step = case_.steps[index];
    if (step.E.trim() !== "check_point" || step.assertion_type !== null) {
      continue;
    }
    const source_kind = step.source.kind;
    const source_ref = String(step.source.ref || "").trim();
    let expect: Record<string, any>;
    if (source_kind === "intent") {
      expect = { kind: "Author", text_hash: crypto.createHash("sha256").update(String(step.G || ""), "utf-8").digest("hex") };
    } else if (source_kind === "manual") {
      if (!source_ref) {
        problems.push(`step ${index}: Manual expect cannot be derived without source.ref`);
        continue;
      }
      expect = { kind: "Manual", locator: source_ref };
      if (String(step.spec_gap || "").trim()) {
        expect["spec_gap"] = String(step.spec_gap).trim();
      }
    } else if (source_kind === "spec") {
      if (!source_ref) {
        problems.push(`step ${index}: Spec expect cannot be derived without source.ref`);
        continue;
      }
      expect = { kind: "Spec", locator: source_ref };
    } else if (source_kind === "defect_spec") {
      if (!source_ref || !_isPlainObject(step.source.receipt) || !Object.keys(step.source.receipt).length) {
        problems.push(`step ${index}: DefectSpec expect cannot be derived without source.ref and the engine-resolved receipt`);
        continue;
      }
      expect = {
        kind: "DefectSpec",
        locator: source_ref,
        receipt_sha256: _canonical_json_sha256(Object.fromEntries(Object.entries(step.source.receipt).filter(([key]) => key !== "defect_spec_compilation"))),
      };
    } else if (source_kind === "capability_xml") {
      problems.push(`step ${index}: CapabilityXml expect generation is pending G6; provide a typed, XML-bound expected claim instead of deriving a value from command existence`);
      continue;
    } else if (_DERIVED_SOURCE_KINDS.has(source_kind)) {
      const authority = claim_authority_source(source_kind);
      if (!source_ref) {
        problems.push(`step ${index}: ${authority} derivation cannot be derived without source.ref`);
        continue;
      }
      expect = { kind: authority, recipe_id: source_ref, derivation: source_kind };
    } else {
      problems.push(`step ${index}: expect authority cannot be mechanically derived from source.kind=${source_kind || "unknown"}`);
      continue;
    }
    step.assertion_type = { expect, flip: { kind: "Flipped", evidence_ref: "compiler:mutation-pending" }, form: { kind: _FORM_KIND } };
  }
  if (!problems.length) {
    case_.assertion_schema = ASSERTION_TYPE_SCHEMA;
  }
  return problems;
}

export function compile_expect_authority(case_: CaseProvenance): string[] {
  const problems: string[] = [];
  for (const step of case_.steps) {
    if (step.source.kind === "precedent") {
      let rejection: string;
      try {
        const { package_asset_autoid, package_rejection, read_package_projection } = require("./package_advisories");
        const receipt = step.source.receipt || {};
        const asset_id = path.basename(String(receipt["path"] || "")) || String(step.source.ref || "").split("#", 1)[0].trim();
        rejection = package_rejection({
          autoid: package_asset_autoid(asset_id),
          asset_id,
          sha256: String(receipt["sha256"] || ""),
          projection: read_package_projection(),
        });
      } catch {
        rejection = "E_PACKAGE_INDEX_UNAVAILABLE asset_id=package-registry rule_id=PKG-ASSET-001";
      }
      if (rejection) {
        problems.push(rejection);
      }
    }
  }
  return problems;
}

export const check_emit_source_authority = compile_expect_authority;

export function parse_provenance(provenance_json: string): CaseProvenance | null {
  if (!provenance_json || !provenance_json.trim()) {
    return null;
  }
  try {
    return CaseProvenance.from_json(provenance_json);
  } catch {
    return null;
  }
}

export function steps_match(provenance: CaseProvenance, steps: Record<string, any>[]): boolean {
  if (provenance.steps.length !== steps.length) {
    return false;
  }
  for (let i = 0; i < provenance.steps.length; i++) {
    const ps = provenance.steps[i];
    const st = steps[i];
    if (ps.E !== String(st["E"] ?? "") || ps.F !== String(st["F"] ?? "") || ps.G !== String(st["G"] ?? "")) {
      return false;
    }
  }
  return true;
}

export function backfill_efg(provenance: CaseProvenance, steps: Record<string, any>[]): boolean {
  if (provenance.steps.length !== steps.length) {
    return false;
  }
  for (let i = 0; i < provenance.steps.length; i++) {
    const ps = provenance.steps[i];
    const st = steps[i];
    ps.E = String(st["E"] ?? "");
    ps.F = String(st["F"] ?? "");
    ps.G = String(st["G"] ?? "");
  }
  return true;
}

export function check_runtime_consistency(provenance: CaseProvenance): string[] {
  const problems: string[] = [];
  for (let i = 0; i < provenance.steps.length; i++) {
    const s = provenance.steps[i];
    if (s.E.trim() !== "check_point") {
      continue;
    }
    const has_placeholder = s.G.includes(RUNTIME_PLACEHOLDER);
    const is_runtime_kind = s.source.kind === "device_runtime";
    if (is_runtime_kind && !has_placeholder) {
      problems.push(`step[${i}] source is marked device_runtime (unknowable offline) yet a concrete value ${JSON.stringify(s.G)} was filled in — if the value is unknowable offline, fabricating one is forbidden; the expected value should contain the ${RUNTIME_PLACEHOLDER} placeholder.`);
    } else if (has_placeholder && !is_runtime_kind) {
      problems.push(`step[${i}] expected value contains the ${RUNTIME_PLACEHOLDER} placeholder yet its source is marked ${JSON.stringify(s.source.kind)} — a placeholder declares the value unknowable offline, so the source must be marked device_runtime.`);
    }
  }
  return problems;
}
