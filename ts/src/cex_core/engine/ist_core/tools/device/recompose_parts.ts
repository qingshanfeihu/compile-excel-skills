import fs from "node:fs";
import nodePath from "node:path";

import {
  atomic_write_bytes_nofollow,
  canonical_json,
  lexical_absolute,
  lexical_path_inside_root,
  open_directory_nofollow,
  read_regular_nofollow,
  sha256_bytes,
} from "../../../case_compiler/_sealed_io";
import { MACHINE_MINDMAP_PARTS_LEDGER_NAME } from "../../../engine_managed_outputs";
import { P } from "../../../_py";
import { acquireLockSync } from "../../../../../platform/index";

export const PARTS_SCHEMA = "ist.machine-mindmap-parts";
const _AUTOID_RE = /^\d{18}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _DISPATCH_ID_RE = /^[0-9a-f]{32}$/;
const _MAX_LEDGER_BYTES = 16 * 1024 * 1024;
const _MAX_RECORD_BYTES = 4 * 1024 * 1024;
const _HEADER_KEYS = new Set(["schema", "kind", "out_name", "binding_sha256", "source_sha256", "case_autoids"]);
const _ENTRY_KEYS = new Set(["schema", "kind", "dispatch_id", "autoid", "case", "case_sha256"]);
const _INVALID_ENTRY_KEYS = new Set(["schema", "kind", "autoid", "reason"]);
const _ENGINE_DERIVABLE_CASE_KEYS = new Set(["autoid", "group_path", "steps"]);
export const MACHINE_MINDMAP_BUCKETS: readonly string[] = ["exp_recipe", "step_recipe", "true_gap"];

export class MachineMindmapPartsError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "MachineMindmapPartsError";
  }
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _caseIsHollow(case_: Record<string, any>): boolean {
  return Object.keys(case_).every((k) => _ENGINE_DERIVABLE_CASE_KEYS.has(k));
}

export class MachineMindmapPartsSnapshot {
  readonly out_name: string;
  readonly binding_sha256: string;
  readonly source_sha256: string;
  readonly case_autoids: readonly string[];
  readonly cases: Record<string, Record<string, any>>;
  readonly ledger_sha256: string;

  constructor(opts: {
    out_name: string;
    binding_sha256: string;
    source_sha256: string;
    case_autoids: readonly string[];
    cases: Record<string, Record<string, any>>;
    ledger_sha256: string;
  }) {
    this.out_name = opts.out_name;
    this.binding_sha256 = opts.binding_sha256;
    this.source_sha256 = opts.source_sha256;
    this.case_autoids = Object.freeze([...opts.case_autoids]);
    this.cases = opts.cases;
    this.ledger_sha256 = opts.ledger_sha256;
  }

  get submitted_autoids(): string[] {
    return this.case_autoids.filter((aid) => aid in this.cases && !_caseIsHollow(this.cases[aid]));
  }

  get missing_autoids(): string[] {
    const submitted = new Set(this.submitted_autoids);
    return this.case_autoids.filter((aid) => !submitted.has(aid));
  }

  is_complete(): boolean {
    return this.missing_autoids.length === 0;
  }

  ordered_cases(): Array<Record<string, any>> {
    if (!this.is_complete()) {
      throw new MachineMindmapPartsError("machine mindmap parts ledger does not cover the closed case set");
    }
    return this.case_autoids.map((aid) => this.cases[aid]);
  }
}

function _validateOutName(out_name: string): string {
  const name = String(out_name ?? "").trim();
  if (
    !name ||
    name === "." ||
    name === ".." ||
    nodePath.basename(name) !== name ||
    name.includes("/") ||
    name.includes("\\") ||
    name.includes("~") ||
    [...name].some((char) => char.charCodeAt(0) < 32) ||
    name.length > 180
  ) {
    throw new MachineMindmapPartsError("machine mindmap parts out_name is invalid");
  }
  return name;
}

function _validateCaseAutoids(case_autoids: Iterable<string> | null | undefined): string[] {
  const ordered = [...(case_autoids ?? [])].map((aid) => String(aid));
  if (ordered.length === 0 || ordered.some((aid) => !_AUTOID_RE.test(aid)) || new Set(ordered).size !== ordered.length) {
    throw new MachineMindmapPartsError("machine mindmap parts case set is not a closed 18-digit autoid set");
  }
  return ordered;
}

export function machine_mindmap_parts_path(outputs_root: string | P, out_name: string): P {
  const name = _validateOutName(out_name);
  const root = new P(lexical_absolute(String(outputs_root)));
  const target = lexical_path_inside_root(root.joinpath(name, MACHINE_MINDMAP_PARTS_LEDGER_NAME)._p, root._p, {
    errorType: MachineMindmapPartsError,
    traversal_message: "machine mindmap parts path traversal is forbidden",
    outside_message: "machine mindmap parts path escaped outputs root",
  });
  if (target !== root.joinpath(name, MACHINE_MINDMAP_PARTS_LEDGER_NAME)._p) {
    throw new MachineMindmapPartsError("machine mindmap parts path identity is invalid");
  }
  return new P(target);
}

function _line(value: Record<string, any>): Buffer {
  const record = { ...value };
  try {
    JSON.stringify(record, (_key, v) => (typeof v === "number" && !Number.isFinite(v) ? (() => { throw new MachineMindmapPartsError("non-finite"); })() : v));
  } catch (exc) {
    if (exc instanceof MachineMindmapPartsError) {
      throw new MachineMindmapPartsError("machine mindmap parts record contains a non-finite or unserializable value");
    }
    throw new MachineMindmapPartsError("machine mindmap parts record contains a non-finite or unserializable value");
  }
  const payload = Buffer.concat([canonical_json(record, { ensure_ascii: false }), Buffer.from("\n", "utf8")]);
  if (payload.length > _MAX_RECORD_BYTES) {
    throw new MachineMindmapPartsError("machine mindmap parts record exceeds its budget");
  }
  return payload;
}

function _decodeLine(raw: Buffer): Record<string, any> {
  let value: any;
  try {
    value = JSON.parse(raw.toString("utf8"), (_key, v) => {
      if (v !== null && typeof v === "object" && !Array.isArray(v)) {
        const keys = Object.keys(v);
        if (new Set(keys).size !== keys.length) throw new Error("duplicate JSON key");
      }
      if (typeof v === "number" && !Number.isFinite(v)) throw new Error(`non-finite JSON constant: ${v}`);
      return v;
    });
  } catch (exc) {
    throw new MachineMindmapPartsError("machine mindmap parts ledger contains invalid JSON");
  }
  if (!_isMapping(value)) {
    throw new MachineMindmapPartsError("machine mindmap parts record must be an object");
  }
  return value;
}

function _headerLine(out_name: string, binding_sha256: string, source_sha256: string, case_autoids: string[]): Buffer {
  return _line({ schema: PARTS_SCHEMA, kind: "dispatch", out_name, binding_sha256, source_sha256, case_autoids: [...case_autoids] });
}

function _sameKeys(obj: Record<string, any>, expected: Set<string>): boolean {
  const keys = Object.keys(obj);
  return keys.length === expected.size && keys.every((k) => expected.has(k));
}

function _snapshotFromBytes(raw: Buffer, opts: { out_name: string; binding_sha256?: string | null; source_sha256?: string | null }): MachineMindmapPartsSnapshot {
  const outName = opts.out_name;
  const bindingSha256 = opts.binding_sha256 ?? null;
  const sourceSha256 = opts.source_sha256 ?? null;
  if (raw.length === 0 || raw.length > _MAX_LEDGER_BYTES || raw[raw.length - 1] !== 0x0a) {
    throw new MachineMindmapPartsError("machine mindmap parts byte framing is invalid");
  }
  const lines = raw.toString("binary").split("\n").filter((_s, i, arr) => i < arr.length - 1).map((s) => Buffer.from(s, "binary"));
  if (lines.length === 0 || lines.some((line) => line.length > _MAX_RECORD_BYTES)) {
    throw new MachineMindmapPartsError("machine mindmap parts record framing is invalid");
  }
  const header = _decodeLine(lines[0]);
  const headerBinding = header.binding_sha256;
  const headerSource = header.source_sha256;
  if (
    !_sameKeys(header, _HEADER_KEYS) ||
    header.schema !== PARTS_SCHEMA ||
    header.kind !== "dispatch" ||
    header.out_name !== outName ||
    typeof headerBinding !== "string" ||
    !_SHA256_RE.test(headerBinding) ||
    typeof headerSource !== "string" ||
    !_SHA256_RE.test(headerSource) ||
    !Array.isArray(header.case_autoids)
  ) {
    throw new MachineMindmapPartsError("machine mindmap parts dispatch header is invalid");
  }
  if (bindingSha256 !== null && headerBinding !== bindingSha256) {
    throw new MachineMindmapPartsError("machine mindmap parts ledger belongs to another authority binding");
  }
  if (sourceSha256 !== null && headerSource !== sourceSha256) {
    throw new MachineMindmapPartsError("machine mindmap parts ledger belongs to another source generation");
  }
  const ordered = _validateCaseAutoids(header.case_autoids);
  const allowed = new Set(ordered);
  const cases: Record<string, Record<string, any>> = {};
  for (const encoded of lines.slice(1)) {
    const row = _decodeLine(encoded);
    if (row.kind === "invalid") {
      const reason = row.reason;
      const invalidAutoid = row.autoid;
      if (
        !_sameKeys(row, _INVALID_ENTRY_KEYS) ||
        row.schema !== PARTS_SCHEMA ||
        typeof invalidAutoid !== "string" ||
        !allowed.has(invalidAutoid) ||
        typeof reason !== "string" ||
        !reason.trim() ||
        reason.length > 200
      ) {
        throw new MachineMindmapPartsError("machine mindmap parts invalidation record is invalid");
      }
      delete cases[invalidAutoid];
      continue;
    }
    const autoid = row.autoid;
    const digest = row.case_sha256;
    const case_ = row.case;
    if (
      !_sameKeys(row, _ENTRY_KEYS) ||
      row.schema !== PARTS_SCHEMA ||
      row.kind !== "case" ||
      typeof row.dispatch_id !== "string" ||
      !_DISPATCH_ID_RE.test(String(row.dispatch_id)) ||
      typeof autoid !== "string" ||
      !allowed.has(autoid) ||
      !_isMapping(case_) ||
      typeof digest !== "string" ||
      !_SHA256_RE.test(digest) ||
      digest !== sha256_bytes(canonical_json(case_, { ensure_ascii: false }))
    ) {
      throw new MachineMindmapPartsError("machine mindmap parts case record is invalid or stale");
    }
    cases[autoid] = case_;
  }
  return new MachineMindmapPartsSnapshot({
    out_name: outName,
    binding_sha256: headerBinding,
    source_sha256: headerSource,
    case_autoids: ordered,
    cases,
    ledger_sha256: sha256_bytes(raw),
  });
}

export function initialize_machine_mindmap_parts(
  outputs_root: string | P,
  out_name: string,
  opts: { binding_sha256: string; source_sha256: string; case_autoids: Iterable<string> },
): [P, MachineMindmapPartsSnapshot] {
  const name = _validateOutName(out_name);
  for (const digest of [opts.binding_sha256, opts.source_sha256]) {
    if (typeof digest !== "string" || !_SHA256_RE.test(digest)) {
      throw new MachineMindmapPartsError("machine mindmap parts identity digest is invalid");
    }
  }
  const ordered = _validateCaseAutoids(opts.case_autoids);
  const root = new P(lexical_absolute(String(outputs_root)));
  const path = machine_mindmap_parts_path(root, name);
  const header = _headerLine(name, opts.binding_sha256, opts.source_sha256, ordered);
  let existing: MachineMindmapPartsSnapshot | null = null;
  try {
    const raw = read_regular_nofollow(path._p, {
      errorType: MachineMindmapPartsError,
      invalid_message: "machine mindmap parts path is invalid",
      directory_message: "machine mindmap parts parent is unavailable",
      open_message: "machine mindmap parts ledger is unavailable",
      bounds_message: "machine mindmap parts ledger exceeds its boundary",
      changed_message: "machine mindmap parts ledger changed while reading",
      max_bytes: _MAX_LEDGER_BYTES,
      min_bytes: 1,
      trusted_root: root._p,
      require_current_uid: true,
    }) as Buffer;
    const candidate = _snapshotFromBytes(raw, { out_name: name, binding_sha256: opts.binding_sha256, source_sha256: opts.source_sha256 });
    if (candidate.case_autoids.length === ordered.length && candidate.case_autoids.every((a, i) => a === ordered[i])) {
      existing = candidate;
    }
  } catch (exc) {
    if (exc instanceof MachineMindmapPartsError || (exc as any)?.code === "ENOENT") {
      existing = null;
    } else {
      existing = null;
    }
  }
  if (existing !== null) {
    return [path, existing];
  }
  atomic_write_bytes_nofollow(path._p, header, {
    errorType: MachineMindmapPartsError,
    invalid_message: "machine mindmap parts path is invalid",
    unavailable_message: "machine mindmap parts ledger cannot be initialized safely",
    create_parents: false,
    mode: 0o600,
  });
  return [path, new MachineMindmapPartsSnapshot({
    out_name: name,
    binding_sha256: opts.binding_sha256,
    source_sha256: opts.source_sha256,
    case_autoids: ordered,
    cases: {},
    ledger_sha256: sha256_bytes(header),
  })];
}

export function discard_machine_mindmap_parts(outputs_root: string | P, out_name: string): void {
  const name = _validateOutName(out_name);
  const root = new P(lexical_absolute(String(outputs_root)));
  const path = machine_mindmap_parts_path(root, name);
  try {
    open_directory_nofollow(path.parent._p, {
      errorType: MachineMindmapPartsError,
      invalid_message: "machine mindmap parts parent is invalid",
      unavailable_message: "machine mindmap parts parent is unavailable",
    });
  } catch (exc) {
    if (exc instanceof MachineMindmapPartsError) return;
    throw exc;
  }
  let info: fs.Stats;
  try {
    info = fs.lstatSync(path._p);
  } catch (exc) {
    if ((exc as any)?.code === "ENOENT") return;
    throw exc;
  }
  if (!info.isFile() || info.nlink !== 1 || (typeof process.getuid === "function" && info.uid !== process.getuid())) {
    throw new MachineMindmapPartsError("machine mindmap parts ledger is not a sealed regular file");
  }
  fs.unlinkSync(path._p);
}

export function read_machine_mindmap_parts(
  outputs_root: string | P,
  out_name: string,
  opts: { binding_sha256?: string | null; source_sha256?: string | null; preserve_missing?: boolean } = {},
): MachineMindmapPartsSnapshot {
  const name = _validateOutName(out_name);
  const root = new P(lexical_absolute(String(outputs_root)));
  const path = machine_mindmap_parts_path(root, name);
  const raw = read_regular_nofollow(path._p, {
    errorType: MachineMindmapPartsError,
    invalid_message: "machine mindmap parts path is invalid",
    directory_message: "machine mindmap parts parent is unavailable",
    open_message: "machine mindmap parts ledger is unavailable",
    bounds_message: "machine mindmap parts ledger exceeds its boundary",
    changed_message: "machine mindmap parts ledger changed while reading",
    max_bytes: _MAX_LEDGER_BYTES,
    min_bytes: 1,
    preserve_missing: opts.preserve_missing ?? false,
    trusted_root: root._p,
    require_current_uid: true,
  }) as Buffer;
  return _snapshotFromBytes(raw, { out_name: name, binding_sha256: opts.binding_sha256 ?? null, source_sha256: opts.source_sha256 ?? null });
}

export function machine_mindmap_case_value_violations(cases: Iterable<Record<string, any>>, allowed_autoids: Iterable<string>): Array<Record<string, string>> {
  const violations: Array<Record<string, string>> = [];
  const materialized = [...(cases ?? [])];
  if (materialized.length === 0) {
    return [{ code: "cases_empty", locus: "cases", detail: "the submission carries no case objects; record at least one finished case per call" }];
  }
  const allowed = new Set([...(allowed_autoids ?? [])].map((aid) => String(aid)));
  const firstIndexByAutoid = new Map<string, number>();
  for (const [index, case_] of materialized.entries()) {
    const autoid = _isMapping(case_) ? case_.autoid : undefined;
    if (typeof autoid !== "string" || !_AUTOID_RE.test(autoid)) {
      violations.push({ code: "autoid_invalid", locus: `cases[${index}].autoid`, detail: `each case must carry its dispatched 18-digit autoid as a JSON string; got ${Array.isArray(autoid) ? "list" : autoid === null ? "NoneType" : typeof autoid}. Copy the autoid verbatim from the dispatched mindmap, quoted as a string.` });
      continue;
    }
    if (!allowed.has(autoid)) {
      violations.push({ code: "autoid_not_dispatched", locus: `cases[${index}].autoid`, detail: `autoid ${autoid} is outside the engine-dispatched closed set; only cases signed into this dispatch can be recorded` });
      continue;
    }
    if (firstIndexByAutoid.has(autoid)) {
      violations.push({ code: "autoid_duplicated_in_call", locus: `cases[${index}].autoid`, detail: `autoid ${autoid} appears twice in this call (first at cases[${firstIndexByAutoid.get(autoid)}]). The ledger replays records in order, so the later copy silently replaces the earlier one and only one of them is ever written; a per-field rejection could not say which copy it is about either. Submit one record per autoid. To replace a record you already submitted, send it again in a later call.` });
      continue;
    }
    firstIndexByAutoid.set(autoid, index);
    if (_caseIsHollow(case_)) {
      violations.push({ code: "case_carries_no_recomposition", locus: `cases[${index}]`, detail: `case ${autoid} carries only fields the engine backfills from the source snapshot (group_path, steps); nothing the recomposer produces is present. Recording it would mark the case finished and drop it from outstanding_autoids, so it would never be written. Submit the case with its contract, origin, proposal, bucket and expectations_by_step, or leave it out of this call and record it when it is done.` });
      continue;
    }
    const projector = require("../../../case_compiler/mindmap_contract_projector");
    if (projector.proposal_shape_error(case_)) {
      const proposal = case_.proposal;
      let observed: string;
      if (!("proposal" in case_)) {
        observed = "the key is absent";
      } else if (Array.isArray(proposal)) {
        observed = "the array contains a non-string or an empty string";
      } else {
        observed = `got a JSON ${proposal === null ? "NoneType" : typeof proposal}`;
      }
      violations.push({ code: "proposal_shape_invalid", locus: `cases[${index}].proposal`, detail: `case ${autoid} must carry \`proposal\` as an array of non-empty plain strings, one entry per thing the source leaves missing, and an empty array when nothing is missing; ${observed}. The engine does not derive this field, and the projector voids a draft whose proposal is malformed, so the case would never be written. Add the field and submit this one case again; no semantic verdict was made.` });
      continue;
    }
    const { validate_case_enhancement_fields } = require("../compile_engine/rebind_binder");
    for (const detail of validate_case_enhancement_fields(case_)) {
      violations.push({ code: "enhancement_shape_invalid", locus: `cases[${index}].enhancements`, detail: `case ${autoid} enhancement fields are malformed: ${detail}. Repair the five-field rebind license or concretization object and resubmit this case; no semantic verdict was made.` });
    }
    const bucket = case_.bucket;
    if (typeof bucket !== "string" || !MACHINE_MINDMAP_BUCKETS.includes(bucket)) {
      let observed: string;
      if (!("bucket" in case_)) {
        observed = "the key is absent";
      } else if (typeof bucket === "string") {
        observed = `got '${bucket.slice(0, 40)}'`;
      } else {
        observed = `got a JSON ${bucket === null ? "NoneType" : typeof bucket}`;
      }
      violations.push({ code: "bucket_not_in_closed_set", locus: `cases[${index}].bucket`, detail: `case ${autoid} must carry \`bucket\` as one of the three classification values exp_recipe, step_recipe or true_gap; ${observed}. The engine does not derive this field — it recomputes only source_status and typed_assertion_status from the case itself — so an absent or unknown bucket stays unknown all the way to the artifact. Classify this case by the three-bucket criteria in the skill and submit this one case again; no semantic verdict was made.` });
      continue;
    }
    if (bucket === "true_gap") {
      if (projector._derived_source_status({ ...case_ }) === "complete") {
        violations.push({ code: "true_gap_source_complete", locus: `cases[${index}].bucket`, detail: `case ${autoid} declares bucket=true_gap, but the engine recomputes its source_status as complete from the case's description, authored steps and natural-language expectations. A complete source cannot be turned into a gap by classification. Use step_recipe or exp_recipe and preserve the source fields; true_gap is reserved for a mechanically incomplete source.` });
      }
      continue;
    }
    if (projector.primary_expectation_membership_error(case_)) {
      violations.push({ code: "primary_expectation_not_in_step_expectations", locus: `cases[${index}].expectations_by_step`, detail: `case ${autoid}: contract.expectation and origin.expectation are not represented together in expectations_by_step. The projector requires an entry with the same origin and matching text after whitespace normalization and the existing author-locator label normalization. Check the selected primary declaration against its actual source, and include that declaration with its original origin in the step-bound list; retain the other authored expectations. Keep unresolved assertion fields null. This is structural membership, not an Author-versus-Spec verdict or a request to rewrite expected values. Nothing from this call was recorded; repair the submitted references/list and resubmit this case.` });
    }
  }
  return violations;
}

const _EVIDENCE_ATOM_MAX_CHARS = 1200;
const _EVIDENCE_CALL_MAX_CHARS = 20000;
const _CONFLICT_SURFACE_PROBLEMS = new Set(["locator_unresolved", "text_drift", "invalid"]);
const _COPY_DISCIPLINE = "Copy that atom whole, byte for byte — never retell it, never drop a leading number, a negation, a condition, or a trailing clause. Runs of whitespace are normalized before the comparison; nothing else is.";
const _SPEC_SPAN_HINT = "If the proposition you need is not complete inside the span you declared — its condition sits on neighbouring lines — declare a span that covers them (`spec:<file>:<start>-<end>` resolves to those lines joined) and quote that whole span. Do not cut the condition away so that a single line matches: a consequent without its condition asserts something the SPEC does not.";

function _evidenceBlock(atom: string): string {
  return "\n<<<SOURCE\n" + atom + "\nSOURCE>>>\n";
}

function _originUnresolvedDetail(origin: string, opts: { governing_spec: string | null }): string {
  const governingSpec = opts.governing_spec;
  if (origin.startsWith("spec:")) {
    if (!governingSpec) {
      return `declares origin \`${origin}\`, which resolves to nothing here because this dispatch has no governing SPEC bound. Changing the filename or line span cannot make a \`spec:\` origin resolvable in this dispatch. Cite an author-mindmap anchor this case actually carries (\`title\`, \`step:<n>\`, \`expectation:<n>\`, or \`expectation:<label>\`) and quote that atom whole, or remove the proposition if it has no bound source.`;
    }
    const bound = `this dispatch binds governing_spec \`${governingSpec}\``;
    return `declares origin \`${origin}\`, which resolves to nothing here: ${bound}, and a \`spec:\` origin resolves only against that exact file, by 1-based line numbers inside it (\`spec:<file>:<line>\` or \`spec:<file>:<start>-<end>\`). Declare a span of the bound SPEC that really carries this proposition, or cite the author mindmap instead, and quote that span whole.`;
  }
  if (origin.startsWith("defect:")) {
    return `declares origin \`${origin}\`, which resolves to nothing here: no matching engine-bound DefectSpec projection is in force for this dispatch. Cite a source this dispatch actually binds.`;
  }
  if (!origin) {
    return "declares no origin, so there is nothing for it to be verbatim against. Declare the anchor this text comes from and quote that anchor whole.";
  }
  return `declares origin \`${origin}\`, which this case does not carry in the dispatched mindmap. Declare an anchor this case really has (\`title\`, \`step:<n>\`, \`expectation:<n>\`, \`expectation:<label>\`) and quote that anchor's text whole.`;
}

const _SPEC_SIDE_FORMS = "`spec_locator` names the governing-source side of the comparison and takes only `spec:<file>:<line>`, `spec:<file>:<start>-<end>`, or `defect:<backend>:<ticket-id>:title|description`.";
const _CASE_SIDE_FORMS = "`case_locator` names the anchor inside this case that the comparison lands on, and takes only an anchor this case carries in the dispatched mindmap (`title`, `step:<n>`, `expectation:<label>`, `orphan_note:<n>`).";

function _locatorUnresolvedDetail(side: string, locator: string, opts: { governing_spec: string | null }): string {
  const governingSpec = opts.governing_spec;
  const other = side === "spec" ? "case_locator" : "spec_locator";
  const forms = side === "spec" ? _SPEC_SIDE_FORMS : _CASE_SIDE_FORMS;
  if (!locator) {
    return "is empty, so this side of the comparison has no locator to resolve. " + forms;
  }
  if (side === "spec" && locator.startsWith("spec:")) {
    if (!governingSpec) {
      return `declares \`${locator}\`, but this dispatch has no governing SPEC bound. No filename or line-span edit can make this locator resolvable here. Drop this governing-source side of the comparison; a case anchor belongs in \`case_locator\`, not in this slot.`;
    }
    const bound = `this dispatch binds governing_spec \`${governingSpec}\``;
    return `declares \`${locator}\`, which resolves to nothing here: ${bound}, and a \`spec:\` locator resolves only against that exact file, by 1-based line numbers inside it (\`spec:<file>:<line>\` or \`spec:<file>:<start>-<end>\`). Declare a span of the bound SPEC that really carries this proposition, or drop this side of the comparison. Do not copy quote bytes; the engine stamps them from the locator.`;
  }
  if (side === "spec" && locator.startsWith("defect:")) {
    return `declares \`${locator}\`, which resolves to nothing here: no matching engine-bound DefectSpec projection is in force for this dispatch. Cite a governing source this dispatch actually binds, or drop this side of the comparison.`;
  }
  if (locator.startsWith("spec:") || locator.startsWith("defect:")) {
    return `declares \`${locator}\`, a governing-source citation. That belongs in \`${other}\`; this slot takes an anchor of this case. ` + forms;
  }
  if (side === "spec") {
    return `declares \`${locator}\`, which is not a governing-source locator at all. ` + forms + ` An anchor of this case belongs in \`${other}\`.`;
  }
  return `declares \`${locator}\`, which this case does not carry in the dispatched mindmap. ` + forms + " Declare an anchor this case really has. Do not copy quote bytes; the engine stamps them from the locator.";
}

function _structuralDetail(field: string, origin: string): string {
  if (field === "expectations_by_step") {
    return "does not match the author's expectation set. This case's `expectation:*` anchors form an ordered, complete set: one entry per anchor, in source order, and any `spec:` / `defect:` entry you add goes after all of them. Entries missing, reordered, duplicated, or an external entry interleaved among the authored ones all fail this.";
  }
  if (field.endsWith("].n")) {
    if (origin.startsWith("expectation:")) {
      const label = origin.slice("expectation:".length);
      if (/^\d+$/.test(label)) {
        return `binds origin \`${origin}\` to a step this case does not have. A numeric \`expectation:<n>\` label is the author's own step number, so \`n\` here must be \`${label}\`.`;
      }
      return `binds origin \`${origin}\` to a step this case does not have. A labelled \`expectation:<label>\` binds to the step whose text carries \`[${label}]\` (or to the case's only step, when it has just one); \`n\` must be that step's number.`;
    }
    if (!origin) {
      return "carries a step number that names no step of this case. `n` must be the number of a step this case really has in the dispatched source.";
    }
    return `binds origin \`${origin}\` to a step this case does not have. Only an \`expectation:<label>\` origin carries its own step binding; with any other origin (\`title\`, \`step:<n>\`, \`spec:…\`, \`defect:…\`) \`n\` is free but must still be the number of a step this case really has in the dispatched source.`;
  }
  if (field === "group_path" || field === "steps") {
    return "is refilled by the engine from the sealed source before this check runs, so a mismatch here means this autoid has no anchor in the dispatched source. Do not hand-write the field; say so in your return instead.";
  }
  if (field === "depends_on") {
    return "must be the autoid of the immediately preceding sibling case, and only when this case's own authored text names that autoid; otherwise leave it empty.";
  }
  return "does not match the structure the engine derives from the sealed source.";
}

const _EVIDENCE_EXPECTATION_FIELD_RE = /^expectations_by_step\[(\d+)\](?:\.(assertion\.value|n))?$/;

function _unrenderedEvidence(case_: Record<string, any>, field: string): Record<string, any> {
  let origin: any = "";
  let kind = "structural";
  try {
    if (field === "intent" || field === "verification_method" || field === "expectation") {
      kind = "anchored";
      const rawOrigin = case_.origin;
      if (_isMapping(rawOrigin)) {
        origin = rawOrigin[field] ?? "";
      }
    } else if (String(field ?? "").startsWith("adaptation_notes[")) {
      kind = "case_atoms";
    } else {
      const match = _EVIDENCE_EXPECTATION_FIELD_RE.exec(String(field ?? ""));
      if (match !== null && match.length === 3) {
        const items = ((case_.expectations_by_step ?? []) as any[]).filter((item) => _isMapping(item));
        const index = parseInt(match[1], 10);
        if (index < items.length) {
          origin = items[index].origin ?? "";
        }
        kind = match[2] === "n" ? "structural" : "anchored";
      }
    }
  } catch {
    origin = "";
    kind = "structural";
  }
  return { origin: String(origin ?? ""), external: false, atoms: [], kind, unrendered: true };
}

function _verbatimFieldDetail(autoid: string, field: string, evidence: Record<string, any>, opts: { governing_spec: string | null; inline_budget: number }): [string, number] {
  const governingSpec = opts.governing_spec;
  const inlineBudget = opts.inline_budget;
  const origin = String(evidence.origin ?? "");
  const kind = String(evidence.kind ?? "structural");
  const atoms = ((evidence.atoms ?? []) as any[]).map((item) => String(item)).filter((item) => item);
  let normalizedPositionNote = "";
  if (_EVIDENCE_EXPECTATION_FIELD_RE.test(field)) {
    normalizedPositionNote = " The numeric `expectations_by_step[...]` index is the engine-normalized position after source-derived fields are rebuilt; locate the entry in your submitted payload by its `origin`, not by that numeric position.";
  }
  const head = `case ${autoid}: \`${field}\` `;
  if (kind === "structural") {
    return [head + _structuralDetail(field, origin) + normalizedPositionNote, 0];
  }
  if (kind === "case_atoms") {
    return [head + "must quote verbatim the one author atom it rewrote — a whole step or expectation node of this case, as the author wrote it. What you submitted is not any of this case's atoms. This is not a claim that the note is false; it is that its bytes are not an author atom. Quote the atom whole and keep your own description of the adaptation outside the quote, or drop the note.", 0];
  }
  if (atoms.length === 0) {
    if (evidence.unrendered) {
      const declared = origin ? `, \`${origin}\`` : "";
      return [head + `is not verbatim equal to the atom at the origin it declares${declared}. The engine could not render that atom into this message — that is an engine-side rendering fault, not a claim that you invented the citation. Re-read that origin in the dispatched source and copy the atom whole. ` + _COPY_DISCIPLINE + normalizedPositionNote, 0];
    }
    return [head + _originUnresolvedDetail(origin, { governing_spec: governingSpec }) + normalizedPositionNote, 0];
  }
  const atom = atoms[0];
  let detail = head + `is not verbatim equal to the atom at the origin it declares, \`${origin}\`. You did not invent this citation — that origin resolves; the bytes you submitted are not the bytes it resolves to.`;
  let spent: number;
  if (atom.length <= _EVIDENCE_ATOM_MAX_CHARS && atom.length <= inlineBudget) {
    detail += " That atom, exactly:" + _evidenceBlock(atom) + _COPY_DISCIPLINE;
    spent = atom.length;
  } else {
    detail += ` That atom is ${atom.length} characters and is not inlined here; re-read \`${origin}\` in the dispatched source and copy it whole. ` + _COPY_DISCIPLINE;
    spent = 0;
  }
  if (origin.startsWith("spec:")) {
    detail += " " + _SPEC_SPAN_HINT;
  }
  return [detail + normalizedPositionNote, spent];
}

function _consistencyAnchorDetail(autoid: string, consistency: Record<string, any>, failure: string, opts: { governing_spec: string | null }): [string, number] {
  const { ConsistencyStampFailure } = require("../../../case_compiler/mindmap_contract_projector");
  const governingSpec = opts.governing_spec;
  const head = `case ${autoid}: consistency card, ${failure} — `;
  const engineOwned = "Quote bytes are engine-owned glue: omit `spec_quote` / `case_quote` / `premises[].text` (or pass empty). A non-empty caller value is only a byte-for-byte cross-check and did not match the bytes the engine resolves from the locator. Do not copy quote bytes back.";
  if (failure === "consistency_spec_locator_unresolved" || failure === "consistency_case_locator_unresolved") {
    const side = failure.includes("spec_locator") ? "spec" : "case";
    const locator = String(consistency[`${side}_locator`] ?? "").trim();
    return [head + `\`${side}_locator\` ` + _locatorUnresolvedDetail(side, locator, { governing_spec: governingSpec }), 0];
  }
  if (failure === "consistency_spec_quote_drift" || failure === "consistency_case_quote_drift") {
    const side = failure.includes("spec_quote") ? "spec" : "case";
    const locator = String(consistency[`${side}_locator`] ?? "").trim();
    return [head + `\`${side}_quote\` did not match the engine stamp for \`${side}_locator\` = \`${locator}\`. ${engineOwned}`, 0];
  }
  const stamp = ConsistencyStampFailure.of(failure);
  if (stamp.collection === "authored_conflict.surfaces" && _CONFLICT_SURFACE_PROBLEMS.has(stamp.problem)) {
    const index = stamp.index;
    const problem = stamp.problem;
    const conflict = consistency.authored_conflict;
    let locator = "";
    if (_isMapping(conflict)) {
      const surfaces = conflict.surfaces;
      if (Array.isArray(surfaces) && index >= 0 && index < surfaces.length) {
        const item = surfaces[index];
        if (_isMapping(item)) locator = String(item.locator ?? "");
      }
    }
    if (problem === "locator_unresolved") {
      return [head + `\`authored_conflict.surfaces[${index}].locator\` \`${locator}\` does not resolve to one authored surface of this case. Name a locator of the case itself — \`title\`, \`step:<n>\`, \`expectation:<label>\` or \`orphan_note:<n>\` — out of \`consistency_source_atoms\`; the specification has no part in this record.`, 0];
    }
    if (problem === "text_drift") {
      return [head + `\`authored_conflict.surfaces[${index}].quote\` did not match the engine stamp for locator \`${locator}\`. ${engineOwned}`, 0];
    }
    return [head + `\`authored_conflict.surfaces[${index}]\` is not a complete object carrying \`locator\`. \`quote\` is optional; the engine stamps it from the locator.`, 0];
  }
  if (stamp.collection === "premises" && stamp.problem === "locator_unresolved") {
    const index = stamp.index;
    const premises = consistency.premises;
    let locator = "";
    let origin = "";
    if (Array.isArray(premises) && index >= 0 && index < premises.length) {
      const item = premises[index];
      if (_isMapping(item)) {
        locator = String(item.locator ?? "");
        origin = String(item.origin ?? "");
      }
    }
    return [head + `\`premises[${index}].locator\` \`${locator}\` (origin \`${origin}\`) does not resolve against the bound source. Name a locator this dispatch actually binds; omit \`premises[].text\` — the engine stamps it.`, 0];
  }
  if (stamp.collection === "premises" && stamp.problem === "text_drift") {
    const index = stamp.index;
    return [head + `\`premises[${index}].text\` did not match the engine stamp for that premise's locator. ${engineOwned}`, 0];
  }
  if (failure.endsWith("_shape_invalid")) {
    return [head + "a reasoning premise is not a complete object carrying `origin` and `locator`. `text` is optional; the engine stamps it from the locator.", 0];
  }
  return [head + "the consistency card failed locator resolution or quote cross-check. Omit quote fields and name locators this dispatch binds.", 0];
}

export function machine_mindmap_case_verbatim_violations(
  cases: Iterable<Record<string, any>>,
  opts: {
    mindmap_text: string;
    spec_text: string | null;
    governing_spec: string | null;
    governing_spec_status: string | null;
    defect_spec_receipt: Record<string, any> | null;
    defect_spec_status: string | null;
    defect_spec_receipt_sha256: string | null;
  },
): [Array<Record<string, any>>, Array<Record<string, string>>] {
  const projector = require("../../../case_compiler/mindmap_contract_projector");
  const materialized = [...(cases ?? [])].map((case_) => ({ ...case_ }));
  if (materialized.length === 0) {
    return [[], []];
  }
  const doc: Record<string, any> = { cases: materialized };
  projector.fill_mechanical_fields(doc, opts.mindmap_text);
  const stateViolations: Array<Record<string, string>> = [];
  for (const [index, case_] of materialized.entries()) {
    for (const [field, code] of projector.primary_expectation_projection_problems(case_)) {
      stateViolations.push({ code, locus: `cases[${index}].${field}`, detail: `case ${case_.autoid}: ${field} is empty although expectations_by_step already contains entries claiming an Author origin. Bind the primary field to a complete source atom and its matching valid origin. A title or step atom can carry an authored outcome; a separate expectation child is not required. Source grounding still applies. Keep unresolved assertions null. This is a missing projection field, not missing author content or assertion quote drift.` });
    }
    projector.normalize_submission_case_statuses(case_);
    for (const [field, actual] of projector.case_status_mismatches(case_)) {
      stateViolations.push({ code: "case_status_mismatch", locus: `cases[${index}].${field}`, detail: `case ${case_.autoid}: ${field} declares ${JSON.stringify(case_[field])}, but the submitted fields resolve to ${JSON.stringify(actual)}. Check contract.expectation and its origin against the complete atoms in expectations_by_step. An authored outcome may be sourced from title, step:<n>, or expectation:<label>; a separate expectation child is not required. Natural-language source completeness and an executable assertion tuple are different axes: an unresolved tuple stays null with typed status pending. This is a contradiction in the submitted fields, not a finding that the author omitted an expectation and not a request to copy prose into a regex.` });
    }
  }
  if (stateViolations.length > 0) {
    return [materialized, stateViolations];
  }
  const bad: Record<string, string[]> = projector.verbatim_failures(doc, opts.mindmap_text, opts.spec_text, {
    governing_spec: opts.governing_spec,
    governing_spec_status: opts.governing_spec_status,
    defect_spec_receipt: opts.defect_spec_receipt,
    defect_spec_status: opts.defect_spec_status,
    defect_spec_receipt_sha256: opts.defect_spec_receipt_sha256,
  });
  const indexByAutoid = new Map<string, number>(materialized.map((case_, index) => [String(case_.autoid ?? ""), index]));
  const violations: Array<Record<string, string>> = [];
  let budget = _EVIDENCE_CALL_MAX_CHARS;
  for (const autoid of Object.keys(bad).sort()) {
    const fields = bad[autoid];
    const index = indexByAutoid.get(autoid) ?? 0;
    const case_ = index < materialized.length ? materialized[index] : {};
    for (const field of fields) {
      let evidence: Record<string, any>;
      try {
        evidence = projector.verbatim_source_evidence(case_, field, {
          mindmap_text: opts.mindmap_text,
          governing_spec: opts.governing_spec,
          spec_text: opts.spec_text,
          defect_spec_receipt: opts.defect_spec_receipt,
        });
      } catch {
        evidence = _unrenderedEvidence(case_, field);
      }
      const [detail, spent] = _verbatimFieldDetail(autoid, field, evidence, { governing_spec: opts.governing_spec, inline_budget: budget });
      budget -= spent;
      violations.push({ code: "case_verbatim_mismatch", locus: `cases[${index}].${field}`, detail });
    }
  }
  for (const [index, case_] of materialized.entries()) {
    if (!("consistency" in case_)) continue;
    const consistency = case_.consistency;
    if (_isMapping(consistency)) {
      const stampFailure = projector.stamp_consistency_quotes(consistency, String(case_.autoid ?? ""), {
        mindmap_text: opts.mindmap_text,
        governing_spec: opts.governing_spec,
        spec_text: opts.spec_text,
        defect_spec_receipt: opts.defect_spec_receipt,
        cross_check: true,
      });
      if (stampFailure) {
        let detail: string;
        let spent: number;
        try {
          [detail, spent] = _consistencyAnchorDetail(String(case_.autoid ?? ""), consistency, stampFailure, { governing_spec: opts.governing_spec });
        } catch {
          [detail, spent] = [`case ${String(case_.autoid ?? "")}: consistency card, ${stampFailure} — the engine could not render the detail for this failure. Omit quote fields and re-read locators against the dispatched source.`, 0];
        }
        budget -= spent;
        violations.push({ code: "consistency_anchor_mismatch", locus: `cases[${index}].consistency`, detail });
        continue;
      }
    }
    const [shapeFailure, shapeReason] = projector.recompose_consistency_shape_report(consistency);
    if (shapeFailure) {
      violations.push({ code: "consistency_shape_invalid", locus: `cases[${index}].consistency`, detail: `the consistency conclusion does not satisfy the ist.recompose-consistency shape (${shapeFailure}): ${shapeReason}. Repair exactly that, or leave the field out entirely when there is no comparable spec surface to judge against.` });
      continue;
    }
  }
  return [materialized, violations];
}

interface _LedgerSession {
  path: P;
  snapshot: MachineMindmapPartsSnapshot;
  payload: Buffer;
}

function _withLedgerAppend(
  outputs_root: string | P,
  out_name: string,
  fn: (session: _LedgerSession) => Buffer | null,
): _LedgerSession | null {
  const name = _validateOutName(out_name);
  const root = new P(lexical_absolute(String(outputs_root)));
  const path = machine_mindmap_parts_path(root, name);
  const lock = acquireLockSync(path._p + ".lock");
  try {
    open_directory_nofollow(path.parent._p, {
      errorType: MachineMindmapPartsError,
      invalid_message: "machine mindmap parts parent is invalid",
      unavailable_message: "machine mindmap parts parent is unavailable",
    });
    const parentInfo = fs.statSync(path.parent._p);
    if (!parentInfo.isDirectory() || (typeof process.getuid === "function" && parentInfo.uid !== process.getuid())) {
      throw new MachineMindmapPartsError("machine mindmap parts parent identity is invalid");
    }
    let fd: number;
    try {
      fd = fs.openSync(path._p, "r+");
    } catch (exc) {
      if ((exc as any)?.code === "ENOENT") {
        return null;
      }
      throw new MachineMindmapPartsError("machine mindmap parts ledger cannot be opened safely");
    }
    let current: Buffer;
    let snapshot: MachineMindmapPartsSnapshot;
    let lockedSize: number;
    try {
      const info = fs.fstatSync(fd);
      if (!info.isFile() || info.nlink !== 1 || (typeof process.getuid === "function" && info.uid !== process.getuid()) || (info.mode & 0o077) !== 0 || info.size > _MAX_LEDGER_BYTES) {
        throw new MachineMindmapPartsError("machine mindmap parts target identity is invalid");
      }
      const named = fs.lstatSync(path._p);
      if (!info.isFile() || !named.isFile() || info.nlink !== 1 || named.nlink !== 1 || info.dev !== named.dev || info.ino !== named.ino) {
        throw new MachineMindmapPartsError("machine mindmap parts ledger changed while locking");
      }
      lockedSize = info.size;
      current = fs.readFileSync(path._p);
      if (current.length !== lockedSize) {
        throw new MachineMindmapPartsError("machine mindmap parts ledger read was short");
      }
      snapshot = _snapshotFromBytes(current, { out_name: name, binding_sha256: null });
      const payload = fn({ path, snapshot, payload: Buffer.alloc(0) });
      if (payload === null) {
        return null;
      }
      if (lockedSize + payload.length > _MAX_LEDGER_BYTES) {
        throw new MachineMindmapPartsError("machine mindmap parts ledger exceeds its byte budget");
      }
      let offset = 0;
      while (offset < payload.length) {
        const written = fs.writeSync(fd, payload, offset, payload.length - offset, lockedSize + offset);
        if (written <= 0) {
          throw new MachineMindmapPartsError("short machine mindmap parts append");
        }
        offset += written;
      }
      fs.fsyncSync(fd);
      return { path, snapshot, payload: Buffer.concat([current, payload]) };
    } finally {
      fs.closeSync(fd);
    }
  } catch (exc) {
    if (exc instanceof MachineMindmapPartsError) throw exc;
    if ((exc as any)?.code === undefined || exc instanceof Error) {
      if (exc instanceof MachineMindmapPartsError) throw exc;
    }
    throw exc;
  } finally {
    lock.release();
  }
}

export function append_machine_mindmap_cases(
  outputs_root: string | P,
  out_name: string,
  dispatch_id: string,
  cases: Iterable<Record<string, any>>,
): MachineMindmapPartsSnapshot {
  const name = _validateOutName(out_name);
  const identity = String(dispatch_id ?? "").trim();
  if (!_DISPATCH_ID_RE.test(identity)) {
    throw new MachineMindmapPartsError("machine mindmap parts dispatch identity is invalid");
  }
  const materialized = [...cases].map((case_) => ({ ...case_ }));
  if (materialized.length === 0) {
    throw new MachineMindmapPartsError("machine mindmap parts submission is empty");
  }
  const accepted: Record<string, Record<string, any>> = {};
  const session = _withLedgerAppend(outputs_root, name, ({ snapshot }) => {
    const allowed = new Set(snapshot.case_autoids);
    const records: Buffer[] = [];
    for (const case_ of materialized) {
      const autoid = case_.autoid;
      if (typeof autoid !== "string" || !_AUTOID_RE.test(autoid)) {
        throw new MachineMindmapPartsError("machine mindmap parts case autoid is invalid");
      }
      if (autoid in accepted) {
        throw new MachineMindmapPartsError("machine mindmap parts submission repeats an autoid");
      }
      if (!allowed.has(autoid)) {
        throw new MachineMindmapPartsError("machine mindmap parts case autoid is outside the dispatched set");
      }
      if (_caseIsHollow(case_)) {
        throw new MachineMindmapPartsError("machine mindmap parts case carries no recomposition");
      }
      const encoded = canonical_json(case_, { ensure_ascii: false });
      records.push(_line({ schema: PARTS_SCHEMA, kind: "case", dispatch_id: identity, autoid, case: case_, case_sha256: sha256_bytes(encoded) }));
      accepted[autoid] = case_;
    }
    return Buffer.concat(records);
  });
  if (session === null) {
    throw new MachineMindmapPartsError("machine mindmap parts ledger cannot be opened safely");
  }
  const merged = { ...session.snapshot.cases, ...accepted };
  try {
    const { _fork_emit_event } = require("../../skills/loader");
    _fork_emit_event({ event: "recompose_progress", run: name, stage: "cases_recorded", recorded: Object.keys(merged).length, total: session.snapshot.case_autoids.length, delta_autoids: Object.keys(accepted).sort() });
  } catch {}
  return new MachineMindmapPartsSnapshot({
    out_name: name,
    binding_sha256: session.snapshot.binding_sha256,
    source_sha256: session.snapshot.source_sha256,
    case_autoids: session.snapshot.case_autoids,
    cases: merged,
    ledger_sha256: sha256_bytes(session.payload),
  });
}

export function invalidate_machine_mindmap_cases(
  outputs_root: string | P,
  out_name: string,
  autoids: Iterable<string>,
  opts: { reason: string },
): MachineMindmapPartsSnapshot | null {
  const name = _validateOutName(out_name);
  const targets = [...autoids].map((aid) => String(aid)).filter((aid) => String(aid ?? "").trim());
  if (targets.length === 0) {
    throw new MachineMindmapPartsError("machine mindmap parts invalidation is empty");
  }
  const reasonText = String(opts.reason ?? "").trim();
  if (!reasonText || reasonText.length > 200) {
    throw new MachineMindmapPartsError("machine mindmap parts invalidation reason is invalid");
  }
  const session = _withLedgerAppend(outputs_root, name, ({ snapshot }) => {
    const allowed = new Set(snapshot.case_autoids);
    for (const autoid of targets) {
      if (!_AUTOID_RE.test(autoid) || !allowed.has(autoid)) {
        throw new MachineMindmapPartsError("machine mindmap parts invalidation autoid is outside the dispatched set");
      }
    }
    return Buffer.concat(targets.map((autoid) => _line({ schema: PARTS_SCHEMA, kind: "invalid", autoid, reason: reasonText })));
  });
  if (session === null) {
    return null;
  }
  const merged = { ...session.snapshot.cases };
  for (const autoid of targets) {
    delete merged[autoid];
  }
  return new MachineMindmapPartsSnapshot({
    out_name: name,
    binding_sha256: session.snapshot.binding_sha256,
    source_sha256: session.snapshot.source_sha256,
    case_autoids: session.snapshot.case_autoids,
    cases: merged,
    ledger_sha256: sha256_bytes(session.payload),
  });
}
