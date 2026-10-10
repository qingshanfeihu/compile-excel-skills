// 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mechanical_case.py（sha256 100fd6c46788d531）。不在这里手改。
import { read_regular_nofollow, sha256_bytes, validate_json_budget } from "./_sealed_io";
import { _assertion_identity } from "./blocks";
import { _canonical_sha256 } from "./mindmap_contract_projector";
import { _EXPECT_KINDS } from "./provenance_ir";

export const MECHANICAL_CASE_SCHEMA = "ist.mechanical-case";
export const LEGACY_MECHANICAL_GATE_REPORT_SCHEMA = "ist.mechanical-case-gate-report";
export const MECHANICAL_GATE_REPORT_SCHEMA = "ist.mechanical-case-gate-report";
export const MECHANICAL_CASE_KEYS = ["schema", "autoid", "description", "binding", "init_commands", "blocks", "expectation_binding", "escape_hatches", "seal"] as const;
export const MECHANICAL_CASE_BODY_KEYS = new Set(MECHANICAL_CASE_KEYS.filter((k) => k !== "seal"));
const _AUTOID_PATTERN = "^\\d{18}$";
const _SHA256_PATTERN = "^[0-9a-f]{64}$";
const _AUTOID_RE = new RegExp(_AUTOID_PATTERN);
const _SHA256_RE = new RegExp(_SHA256_PATTERN);
const _MAX_MECHANICAL_CASE_BYTES = 4 * 1024 * 1024;
const _OBSERVE_ASSERT_KIND = "OBSERVE_ASSERT";
const _GENERIC_STEP_KIND = "STEP";
const _CHECK_POINT_OBJECT = "check_point";
const _NO_ASSERTION_ID_KINDS = new Set(["CONFIG", "OBSERVE_ONLY", "CAPTURE", "SLEEP", "OBSERVE_ASSERT", "SSL_CERT_LOAD"]);
const _ASSERTION_ID_BLOCK_KINDS = new Set(["CAPTURE_COMPARE", "OBSERVE_DIST", "OBSERVE_MEMBER", "EXPECT_FROM", "OBSERVE_EXIT"]);

export class MechanicalCaseError extends Error {}

function _rejectDuplicateKeys(): (this: any, key: string, value: any) => any {
  const seen = new Set<string>();
  return function (this: any, key: string, value: any): any {
    if (key === "") {
      return value;
    }
    if (seen.has(key)) {
      throw new Error(`duplicate JSON key: ${key}`);
    }
    seen.add(key);
    return value;
  };
}

function _parseJsonStrict(raw: Buffer): any {
  const text = raw.toString("utf-8");
  const payload = JSON.parse(text, _rejectDuplicateKeys());
  _rejectNonFinite(payload);
  return payload;
}

function _rejectNonFinite(value: any): void {
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new Error(`non-finite JSON constant: ${value}`);
  }
  if (Array.isArray(value)) {
    for (const item of value) _rejectNonFinite(item);
  } else if (value !== null && typeof value === "object") {
    for (const item of Object.values(value)) _rejectNonFinite(item);
  }
}

function _normalized_kind(block: Record<string, any>): string {
  return String(block["kind"] ?? "").trim().toUpperCase();
}

function _require_text_entries(values: string[], label: string): void {
  values.forEach((value, index) => {
    if (!String(value).trim()) {
      throw new Error(`${label}[${index}] must be non-empty text`);
    }
  });
}

function _assertion_slot_label(kind: string, blockIndex: number, offset: number): string {
  return offset > 1 ? `${kind}#${blockIndex + 1}[${offset}]` : `${kind}#${blockIndex + 1}`;
}

function _slot_label(blockIndex: number, assertIndex: number | null): string {
  if (assertIndex === null) {
    return _assertion_slot_label(_GENERIC_STEP_KIND, blockIndex, 0);
  }
  return _assertion_slot_label(_OBSERVE_ASSERT_KIND, blockIndex, assertIndex + 1);
}

function _slot_sort_key(slot: [number, number | null]): [number, number] {
  return [slot[0], slot[1] === null ? -1 : slot[1]];
}

function _carried_identity(container: any, label: string): Record<string, string> {
  if (container === null || typeof container !== "object" || Array.isArray(container)) {
    throw new Error(`${label} must be an object carrying the assertion identity minted by the contract card`);
  }
  const [ids, error] = _assertion_identity(container as Record<string, any>);
  if (error) {
    throw new Error(`${label}: ${error}`);
  }
  return ids;
}

function _isPlainObject(value: any): value is Record<string, any> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function _checkExactKeys(value: Record<string, any>, allowed: string[], label: string): void {
  const extra = Object.keys(value).filter((k) => !allowed.includes(k));
  if (extra.length) {
    throw new Error(`${label}: unknown key(s): ${extra.join(", ")}`);
  }
}

function _requireStr(value: any, label: string, opts: { min?: number; max?: number; pattern?: RegExp } = {}): string {
  if (typeof value !== "string") {
    throw new Error(`${label} must be a string`);
  }
  if (opts.min !== undefined && value.length < opts.min) {
    throw new Error(`${label} must have at least ${opts.min} character(s)`);
  }
  if (opts.max !== undefined && value.length > opts.max) {
    throw new Error(`${label} must have at most ${opts.max} character(s)`);
  }
  if (opts.pattern && !opts.pattern.test(value)) {
    throw new Error(`${label} does not match the required pattern`);
  }
  return value;
}

function _requireInt(value: any, label: string, opts: { ge?: number } = {}): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new Error(`${label} must be an integer`);
  }
  if (opts.ge !== undefined && value < opts.ge) {
    throw new Error(`${label} must be >= ${opts.ge}`);
  }
  return value;
}

function _requireStrList(value: any, label: string, opts: { min?: number; max?: number } = {}): string[] {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`);
  }
  if (opts.min !== undefined && value.length < opts.min) {
    throw new Error(`${label} must have at least ${opts.min} item(s)`);
  }
  if (opts.max !== undefined && value.length > opts.max) {
    throw new Error(`${label} must have at most ${opts.max} item(s)`);
  }
  for (const item of value) {
    if (typeof item !== "string") {
      throw new Error(`${label} entries must be strings`);
    }
  }
  return value as string[];
}

export interface MechanicalCaseDescription {
  intent_verbatim: string;
  group_path: string[];
}

function _validateDescription(value: any): MechanicalCaseDescription {
  if (!_isPlainObject(value)) {
    throw new Error("description must be an object");
  }
  _checkExactKeys(value, ["intent_verbatim", "group_path"], "description");
  const intent_verbatim = _requireStr(value["intent_verbatim"], "description.intent_verbatim", { min: 1, max: 8192 });
  const group_path = _requireStrList(value["group_path"], "description.group_path", { min: 1, max: 64 });
  if (!intent_verbatim.trim()) {
    throw new Error("intent_verbatim must be non-empty text");
  }
  _require_text_entries(group_path, "group_path");
  return { intent_verbatim, group_path };
}

export interface MechanicalCaseBinding {
  contract_sha256: string;
  consistency_contract_sha256: string | null;
  mindmap_source_sha256: string;
  capability_generation_id: string;
  capability_projection_sha256: string;
  authored_round: number;
}

function _validateBinding(value: any): MechanicalCaseBinding {
  if (!_isPlainObject(value)) {
    throw new Error("binding must be an object");
  }
  _checkExactKeys(value, ["contract_sha256", "consistency_contract_sha256", "mindmap_source_sha256", "capability_generation_id", "capability_projection_sha256", "authored_round"], "binding");
  const contract_sha256 = _requireStr(value["contract_sha256"], "binding.contract_sha256", { pattern: _SHA256_RE });
  const consistencyRaw = value["consistency_contract_sha256"];
  let consistency_contract_sha256: string | null = null;
  if (consistencyRaw !== undefined && consistencyRaw !== null) {
    consistency_contract_sha256 = _requireStr(consistencyRaw, "binding.consistency_contract_sha256", { pattern: _SHA256_RE });
  }
  const mindmap_source_sha256 = _requireStr(value["mindmap_source_sha256"], "binding.mindmap_source_sha256", { pattern: _SHA256_RE });
  const capability_generation_id = _requireStr(value["capability_generation_id"], "binding.capability_generation_id", { min: 1, max: 128 });
  const capability_projection_sha256 = _requireStr(value["capability_projection_sha256"], "binding.capability_projection_sha256", { pattern: _SHA256_RE });
  const authored_round = _requireInt(value["authored_round"], "binding.authored_round", { ge: 1 });
  if (!capability_generation_id.trim()) {
    throw new Error("capability_generation_id must be non-empty text");
  }
  return { contract_sha256, consistency_contract_sha256, mindmap_source_sha256, capability_generation_id, capability_projection_sha256, authored_round };
}

export interface MechanicalCaseExpectationBinding {
  expectation_id: string;
  semantic_key: string;
  claim_kind: string;
  block_index: number;
  assert_index: number | null;
  scope_ref: string | null;
  state_change_step: number | null;
  binding_disclosure: string | null;
}

function _validateExpectationBinding(value: any, label: string): MechanicalCaseExpectationBinding {
  if (!_isPlainObject(value)) {
    throw new Error(`${label} must be an object`);
  }
  _checkExactKeys(value, ["expectation_id", "semantic_key", "claim_kind", "block_index", "assert_index", "scope_ref", "state_change_step", "binding_disclosure"], label);
  const expectation_id = _requireStr(value["expectation_id"], `${label}.expectation_id`, { min: 1, max: 512 });
  const semantic_key = _requireStr(value["semantic_key"], `${label}.semantic_key`, { min: 1, max: 512 });
  const claim_kind = _requireStr(value["claim_kind"], `${label}.claim_kind`, { min: 1, max: 64 });
  const block_index = _requireInt(value["block_index"], `${label}.block_index`, { ge: 0 });
  const assertRaw = value["assert_index"];
  let assert_index: number | null = null;
  if (assertRaw !== undefined && assertRaw !== null) {
    assert_index = _requireInt(assertRaw, `${label}.assert_index`);
  }
  const scopeRaw = value["scope_ref"];
  let scope_ref: string | null = null;
  if (scopeRaw !== undefined && scopeRaw !== null) {
    scope_ref = _requireStr(scopeRaw, `${label}.scope_ref`);
  }
  const stateRaw = value["state_change_step"];
  let state_change_step: number | null = null;
  if (stateRaw !== undefined && stateRaw !== null) {
    state_change_step = _requireInt(stateRaw, `${label}.state_change_step`);
  }
  const disclosureRaw = value["binding_disclosure"];
  let binding_disclosure: string | null = null;
  if (disclosureRaw !== undefined && disclosureRaw !== null) {
    binding_disclosure = _requireStr(disclosureRaw, `${label}.binding_disclosure`);
  }
  if (!_EXPECT_KINDS.has(claim_kind)) {
    throw new Error(`claim_kind ${JSON.stringify(claim_kind)} is not an identity-bearing expected source; allowed: ${[..._EXPECT_KINDS].sort().join(", ")}`);
  }
  if (assert_index !== null && assert_index < 0) {
    throw new Error("assert_index must be a non-negative index or null");
  }
  if (scope_ref !== null && !scope_ref.trim()) {
    throw new Error("scope_ref must be non-empty text or null");
  }
  if (state_change_step !== null && state_change_step < 0) {
    throw new Error("state_change_step must be a non-negative index or null");
  }
  if (binding_disclosure !== null && !binding_disclosure.trim()) {
    throw new Error("binding_disclosure must be non-empty text or null");
  }
  if ((state_change_step === null) !== (binding_disclosure === null)) {
    throw new Error("state_change_step and binding_disclosure are declared together or not at all");
  }
  return { expectation_id, semantic_key, claim_kind, block_index, assert_index, scope_ref, state_change_step, binding_disclosure };
}

export interface MechanicalCaseEscapeHatch {
  block_index: number;
  capabilities_touched: string[];
  reason: string;
}

function _validateEscapeHatch(value: any, label: string): MechanicalCaseEscapeHatch {
  if (!_isPlainObject(value)) {
    throw new Error(`${label} must be an object`);
  }
  _checkExactKeys(value, ["block_index", "capabilities_touched", "reason"], label);
  const block_index = _requireInt(value["block_index"], `${label}.block_index`, { ge: 0 });
  const capabilities_touched = _requireStrList(value["capabilities_touched"], `${label}.capabilities_touched`, { max: 64 });
  const reason = _requireStr(value["reason"], `${label}.reason`, { min: 1, max: 4096 });
  if (!reason.trim()) {
    throw new Error("escape hatch reason must be non-empty text");
  }
  _require_text_entries(capabilities_touched, "capabilities_touched");
  return { block_index, capabilities_touched, reason };
}

export interface EscapeHatchDefect {
  code: string;
  entry_index: number;
  detail: string;
}

export function escape_hatch_accounting_defects(blocks: any[], accounted_block_indices: number[]): EscapeHatchDefect[] {
  const kinds = blocks.map((block) => (_isPlainObject(block) ? _normalized_kind(block) : ""));
  const defects: EscapeHatchDefect[] = [];
  const declared = new Set<number>();
  accounted_block_indices.forEach((block_index, entry_index) => {
    if (!(block_index >= 0 && block_index < kinds.length)) {
      defects.push({ code: "escape_hatch_out_of_range", entry_index, detail: `escape_hatches[${entry_index}].block_index ${block_index} is out of range for ${kinds.length} blocks` });
      return;
    }
    if (declared.has(block_index)) {
      defects.push({ code: "escape_hatch_duplicated", entry_index, detail: `escape_hatches[${entry_index}] accounts for blocks[${block_index}] twice` });
      return;
    }
    declared.add(block_index);
  });
  const generic = new Set<number>();
  kinds.forEach((kind, index) => {
    if (kind === _GENERIC_STEP_KIND) generic.add(index);
  });
  const sameSet = declared.size === generic.size && [...declared].every((v) => generic.has(v));
  if (!sameSet) {
    const unaccounted = [...generic].filter((v) => !declared.has(v)).sort((a, b) => a - b);
    const notGeneric = [...declared].filter((v) => !generic.has(v)).sort((a, b) => a - b);
    defects.push({ code: "escape_hatch_set_mismatch", entry_index: -1, detail: `escape_hatches must account for exactly the kind=STEP combinators; unaccounted=[${unaccounted.join(", ")}], not-a-generic-step=[${notGeneric.join(", ")}]` });
  }
  return defects;
}

export interface MechanicalCaseSeal {
  mechanical_case_sha256: string;
  capabilities_used: string[];
  expanded_step_count: number;
  check_point_count: number;
  gate_report_sha256: string;
  gate_report_schema: string;
}

function _validateSeal(value: any): MechanicalCaseSeal {
  if (!_isPlainObject(value)) {
    throw new Error("seal must be an object");
  }
  _checkExactKeys(value, ["mechanical_case_sha256", "capabilities_used", "expanded_step_count", "check_point_count", "gate_report_sha256", "gate_report_schema"], "seal");
  const mechanical_case_sha256 = _requireStr(value["mechanical_case_sha256"], "seal.mechanical_case_sha256", { pattern: _SHA256_RE });
  const capabilities_used = _requireStrList(value["capabilities_used"], "seal.capabilities_used", { min: 1, max: 1024 });
  const expanded_step_count = _requireInt(value["expanded_step_count"], "seal.expanded_step_count", { ge: 1 });
  const check_point_count = _requireInt(value["check_point_count"], "seal.check_point_count", { ge: 1 });
  const gate_report_sha256 = _requireStr(value["gate_report_sha256"], "seal.gate_report_sha256", { pattern: _SHA256_RE });
  const gate_report_schema = _requireStr(value["gate_report_schema"] ?? MECHANICAL_GATE_REPORT_SCHEMA, "seal.gate_report_schema");
  if (gate_report_schema !== MECHANICAL_GATE_REPORT_SCHEMA) {
    throw new Error(`seal.gate_report_schema must be ${MECHANICAL_GATE_REPORT_SCHEMA}`);
  }
  _require_text_entries(capabilities_used, "capabilities_used");
  const sortedUnique = [...new Set(capabilities_used)].sort();
  if (JSON.stringify(capabilities_used) !== JSON.stringify(sortedUnique)) {
    throw new Error("capabilities_used must be sorted and de-duplicated; mint the seal with seal_mechanical_case instead of hand-writing it");
  }
  if (expanded_step_count < check_point_count) {
    throw new Error("expanded_step_count cannot be smaller than check_point_count; check_point rows are part of the expansion");
  }
  return { mechanical_case_sha256, capabilities_used, expanded_step_count, check_point_count, gate_report_sha256, gate_report_schema };
}

export interface MechanicalCase {
  schema_: string;
  autoid: string;
  description: MechanicalCaseDescription;
  binding: MechanicalCaseBinding;
  init_commands: string[];
  blocks: Record<string, any>[];
  expectation_binding: MechanicalCaseExpectationBinding[];
  escape_hatches: MechanicalCaseEscapeHatch[];
  seal: MechanicalCaseSeal;
}

function _blockKinds(blocks: Record<string, any>[]): string[] {
  const kinds: string[] = [];
  blocks.forEach((block, index) => {
    const kind = _normalized_kind(block);
    if (!kind) {
      throw new Error(`blocks[${index}] needs a non-empty string kind; the carrier layering for assertion identity is decided by it`);
    }
    kinds.push(kind);
  });
  return kinds;
}

type _SlotKey = string;

function _slotKey(blockIndex: number, assertIndex: number | null): _SlotKey {
  return `${blockIndex}:${assertIndex === null ? "null" : assertIndex}`;
}

function _assertionCarriers(caseData: MechanicalCase, kinds: string[]): Map<_SlotKey, Record<string, string>> {
  const carriers = new Map<_SlotKey, Record<string, string>>();
  kinds.forEach((kind, index) => {
    const block = caseData.blocks[index];
    if (kind === _OBSERVE_ASSERT_KIND) {
      const asserts = block["asserts"];
      if (!Array.isArray(asserts) || !asserts.length) {
        throw new Error(`blocks[${index}] is an OBSERVE_ASSERT without a non-empty asserts[] array, so the assertions it carries cannot be read; each assertion declares its own identity there`);
      }
      asserts.forEach((entry, offset) => {
        carriers.set(_slotKey(index, offset), _carried_identity(entry, _slot_label(index, offset)));
      });
    } else if (_ASSERTION_ID_BLOCK_KINDS.has(kind)) {
      carriers.set(_slotKey(index, null), _carried_identity(block, _slot_label(index, null)));
    } else if (kind === _GENERIC_STEP_KIND) {
      if (String(block["E"] ?? "").trim() === _CHECK_POINT_OBJECT) {
        carriers.set(_slotKey(index, null), _carried_identity(block, _slot_label(index, null)));
      }
    }
  });
  return carriers;
}

function _matchCarriedIdentity(index: number, item: MechanicalCaseExpectationBinding, slot: [number, number | null], kind: string, carriers: Map<_SlotKey, Record<string, string>>): void {
  const carried = carriers.get(_slotKey(slot[0], slot[1]));
  if (carried === undefined) {
    if (kind === _OBSERVE_ASSERT_KIND) {
      let count = 0;
      for (const key of carriers.keys()) {
        if (Number(key.split(":")[0]) === item.block_index) count += 1;
      }
      throw new Error(`expectation_binding[${index}].assert_index ${item.assert_index} is out of range for the ${count} asserts[] entries on blocks[${item.block_index}]`);
    }
    throw new Error(`expectation_binding[${index}] targets blocks[${item.block_index}], a kind=${kind} whose E is not ${_CHECK_POINT_OBJECT}: it expands to an action row, not an assertion row, so there is nothing to bind an expectation to`);
  }
  const declared = { expectation_id: item.expectation_id, semantic_key: item.semantic_key };
  if (JSON.stringify(carried) !== JSON.stringify(declared)) {
    const carriedText = Object.keys(carried).length ? JSON.stringify(carried) : "no identity at all";
    throw new Error(`expectation_binding[${index}] declares ${JSON.stringify(declared)} but ${_slot_label(slot[0], slot[1])} carries ${carriedText}; the binding is the ledger of which claim is redeemed in which assertion slot, not a second place to mint identity — copy both keys verbatim from the assertion that compiles this expectation`);
  }
}

function _validateExpectationSlots(caseData: MechanicalCase, kinds: string[], carriers: Map<_SlotKey, Record<string, string>>): void {
  const seenSlots = new Set<_SlotKey>();
  caseData.expectation_binding.forEach((item, index) => {
    if (item.block_index >= kinds.length) {
      throw new Error(`expectation_binding[${index}].block_index ${item.block_index} is out of range for ${kinds.length} blocks`);
    }
    const kind = kinds[item.block_index];
    if (kind === _OBSERVE_ASSERT_KIND) {
      if (item.assert_index === null) {
        throw new Error(`expectation_binding[${index}] targets OBSERVE_ASSERT blocks[${item.block_index}], whose assertion count is decided by asserts[]; assert_index must name that entry`);
      }
    } else if (_ASSERTION_ID_BLOCK_KINDS.has(kind) || kind === _GENERIC_STEP_KIND) {
      if (item.assert_index !== null) {
        throw new Error(`expectation_binding[${index}] targets blocks[${item.block_index}] of kind ${kind}, which carries assertion identity at block level; assert_index must be null`);
      }
    } else if (_NO_ASSERTION_ID_KINDS.has(kind)) {
      throw new Error(`expectation_binding[${index}] targets blocks[${item.block_index}] of kind ${kind}, which produces no check_point to bind an expectation to`);
    } else {
      throw new Error(`expectation_binding[${index}] targets blocks[${item.block_index}] of unknown kind ${JSON.stringify(kind)}; assertion carriage cannot be decided`);
    }
    const slot: [number, number | null] = [item.block_index, item.assert_index];
    const key = _slotKey(slot[0], slot[1]);
    if (seenSlots.has(key)) {
      throw new Error(`expectation_binding[${index}] reuses assertion slot block_index=${item.block_index}, assert_index=${item.assert_index}; one slot compiles exactly one expectation`);
    }
    seenSlots.add(key);
    _matchCarriedIdentity(index, item, slot, kind, carriers);
  });
  const undeclared = [...carriers.keys()]
    .filter((key) => !seenSlots.has(key))
    .map((key) => {
      const [b, a] = key.split(":");
      return [Number(b), a === "null" ? null : Number(a)] as [number, number | null];
    })
    .sort((x, y) => {
      const kx = _slot_sort_key(x);
      const ky = _slot_sort_key(y);
      return kx[0] - ky[0] || kx[1] - ky[1];
    });
  if (undeclared.length) {
    const labels = undeclared.map((slot) => _slot_label(slot[0], slot[1])).join(", ");
    throw new Error(`blocks carry ${carriers.size} assertion slots but expectation_binding declares only ${seenSlots.size}; unaccounted: ${labels}. Every assertion slot must name a contract-card expectation; one expectation may intentionally occupy multiple distinct slots`);
  }
}

function _validateEscapeHatchAccounting(caseData: MechanicalCase): void {
  const defects = escape_hatch_accounting_defects(caseData.blocks, caseData.escape_hatches.map((hatch) => hatch.block_index));
  if (defects.length) {
    throw new Error(defects[0].detail);
  }
}

function _validateCase(payload: Record<string, any>): MechanicalCase {
  if (payload["schema"] !== MECHANICAL_CASE_SCHEMA) {
    throw new Error(`schema must be ${MECHANICAL_CASE_SCHEMA}`);
  }
  const autoid = _requireStr(payload["autoid"], "autoid", { pattern: _AUTOID_RE });
  const description = _validateDescription(payload["description"]);
  const binding = _validateBinding(payload["binding"]);
  const init_commands = _requireStrList(payload["init_commands"], "init_commands", { max: 512 });
  const blocksRaw = payload["blocks"];
  if (!Array.isArray(blocksRaw) || blocksRaw.length < 1 || blocksRaw.length > 1024) {
    throw new Error("blocks must be an array of 1..1024 items");
  }
  const blocks = blocksRaw.map((block, index) => {
    if (!_isPlainObject(block)) {
      throw new Error(`blocks[${index}] must be an object`);
    }
    return block;
  });
  const expectationRaw = payload["expectation_binding"];
  if (!Array.isArray(expectationRaw) || expectationRaw.length < 1 || expectationRaw.length > 1024) {
    throw new Error("expectation_binding must be an array of 1..1024 items");
  }
  const expectation_binding = expectationRaw.map((item, index) => _validateExpectationBinding(item, `expectation_binding[${index}]`));
  const escapeRaw = payload["escape_hatches"];
  if (!Array.isArray(escapeRaw) || escapeRaw.length > 1024) {
    throw new Error("escape_hatches must be an array of at most 1024 items");
  }
  const escape_hatches = escapeRaw.map((item, index) => _validateEscapeHatch(item, `escape_hatches[${index}]`));
  const seal = _validateSeal(payload["seal"]);
  const caseData: MechanicalCase = { schema_: MECHANICAL_CASE_SCHEMA, autoid, description, binding, init_commands, blocks, expectation_binding, escape_hatches, seal };
  _require_text_entries(init_commands, "init_commands");
  const kinds = _blockKinds(blocks);
  const carriers = _assertionCarriers(caseData, kinds);
  _validateExpectationSlots(caseData, kinds, carriers);
  _validateEscapeHatchAccounting(caseData);
  if (expectation_binding.length !== seal.check_point_count) {
    throw new Error(`expectation_binding declares ${expectation_binding.length} expectations but the seal counts ${seal.check_point_count} check_point rows; at combinator granularity every check_point row redeems exactly one expectation`);
  }
  return caseData;
}

function _canonical_digest(payload: Record<string, any>): [string, string] {
  try {
    return [_canonical_sha256(payload), ""];
  } catch (exc: any) {
    return ["", `mechanical case is not canonicalisable: ${exc?.constructor?.name ?? "Error"}: ${exc?.message ?? exc}`];
  }
}

function _mechanical_case_body(payload: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [key, value] of Object.entries(payload)) {
    if (key !== "seal") out[key] = value;
  }
  return out;
}

function _mechanical_case_digest_input(payload: Record<string, any>): Record<string, any> {
  const seal = payload["seal"];
  const metrics = _isPlainObject(seal)
    ? Object.fromEntries(Object.entries(seal).filter(([key]) => key !== "mechanical_case_sha256"))
    : seal;
  return { ..._mechanical_case_body(payload), seal: metrics };
}

export function validate_mechanical_case(payload: any): [MechanicalCase | null, string] {
  if (!_isPlainObject(payload)) {
    return [null, "mechanical case must be a JSON object"];
  }
  let caseData: MechanicalCase;
  try {
    caseData = _validateCase(payload);
  } catch (exc: any) {
    return [null, `invalid mechanical case: ${exc?.message ?? exc}`];
  }
  const seal = payload["seal"];
  if (!_isPlainObject(seal)) {
    return [null, "mechanical case seal must be a decoded JSON object; pass model_dump(by_alias=True) rather than a model instance"];
  }
  const declared = String(seal["mechanical_case_sha256"] || "");
  const [recomputed, digestError] = _canonical_digest(_mechanical_case_digest_input(payload));
  if (digestError) {
    return [null, digestError];
  }
  if (declared !== recomputed) {
    return [null, `mechanical case seal does not match its body: declared ${declared}, recomputed ${recomputed}`];
  }
  return [caseData, ""];
}

export function seal_mechanical_case(
  body: Record<string, any>,
  opts: {
    capabilities_used: string[];
    expanded_step_count: number;
    check_point_count: number;
    gate_report_sha256: string;
    gate_report_schema?: string;
  }
): Record<string, any> {
  if (!_isPlainObject(body)) {
    throw new MechanicalCaseError("mechanical case body must be a JSON object");
  }
  const keys = new Set(Object.keys(body).filter((k) => k !== "seal"));
  const expected = MECHANICAL_CASE_BODY_KEYS;
  const sameSet = keys.size === expected.size && [...keys].every((k) => expected.has(k as any));
  if (!sameSet) {
    const missing = [...expected].filter((k) => !keys.has(k as string)).sort();
    const unknown = [...keys].filter((k) => !expected.has(k as any)).sort();
    throw new MechanicalCaseError(`mechanical case body keys mismatch; missing=${JSON.stringify(missing)}, unknown=${JSON.stringify(unknown)}`);
  }
  const capabilities_used = opts.capabilities_used;
  if (typeof capabilities_used === "string" || !Array.isArray(capabilities_used)) {
    throw new MechanicalCaseError("capabilities_used must be an array of capability names");
  }
  for (const value of capabilities_used) {
    if (typeof value !== "string" || !value.trim()) {
      throw new MechanicalCaseError("capabilities_used entries must be non-empty text");
    }
  }
  const metrics = {
    capabilities_used: [...new Set(capabilities_used)].sort(),
    expanded_step_count: opts.expanded_step_count,
    check_point_count: opts.check_point_count,
    gate_report_sha256: opts.gate_report_sha256,
    gate_report_schema: opts.gate_report_schema ?? MECHANICAL_GATE_REPORT_SCHEMA,
  };
  const [canonical, digestError] = _canonical_digest({ ..._mechanical_case_body(body), seal: metrics });
  if (digestError) {
    throw new MechanicalCaseError(digestError);
  }
  const seal = { mechanical_case_sha256: canonical, ...metrics };
  try {
    _validateSeal(seal);
  } catch (exc: any) {
    throw new MechanicalCaseError(`invalid mechanical case seal: ${exc?.message ?? exc}`);
  }
  return seal;
}

export interface MintedMechanicalCase {
  document: Record<string, any> | null;
  code: string;
  detail: string;
}

export function mint_and_land_mechanical_case(
  body: Record<string, any>,
  target: string,
  opts: {
    capabilities_used: string[];
    expanded_step_count: number;
    check_point_count: number;
    gate_report_sha256: string;
  }
): MintedMechanicalCase {
  let seal: Record<string, any>;
  try {
    seal = seal_mechanical_case({ ...body }, {
      capabilities_used: [...opts.capabilities_used],
      expanded_step_count: Math.trunc(opts.expanded_step_count),
      check_point_count: Math.trunc(opts.check_point_count),
      gate_report_sha256: opts.gate_report_sha256,
    });
  } catch (exc: any) {
    if (exc instanceof MechanicalCaseError) {
      return { document: null, code: "seal_uncastable", detail: String(exc.message ?? exc) };
    }
    throw exc;
  }
  const document = { ...body, seal };
  const [caseData, error] = validate_mechanical_case(document);
  if (caseData === null) {
    return { document: null, code: "sealed_document_invalid", detail: error };
  }
  const { atomic_write_bytes_nofollow, canonical_json } = require("./_sealed_io");
  try {
    atomic_write_bytes_nofollow(String(target), canonical_json(document, { ensure_ascii: false }), {
      errorType: MechanicalCaseError,
      invalid_message: "mechanical case path is invalid",
      unavailable_message: "mechanical case directory is unavailable",
    });
  } catch (exc: any) {
    if (exc instanceof MechanicalCaseError || (exc && typeof exc === "object" && "code" in exc)) {
      return { document: null, code: "artifact_not_landed", detail: `the sealed mechanical case could not be written: ${exc?.constructor?.name ?? "Error"}` };
    }
    throw exc;
  }
  return { document, code: "", detail: "" };
}

export function load_mechanical_case(p: string): [MechanicalCase, string] {
  const raw = read_regular_nofollow(String(p), {
    errorType: MechanicalCaseError,
    invalid_message: "mechanical case path is invalid",
    directory_message: "mechanical case directory is unavailable",
    open_message: "mechanical case is unavailable",
    bounds_message: "mechanical case exceeds the byte budget",
    changed_message: "mechanical case changed while being read",
    max_bytes: _MAX_MECHANICAL_CASE_BYTES,
  }) as Buffer;
  validate_json_budget(raw, { errorType: MechanicalCaseError, message: "mechanical case exceeds the JSON structure budget" });
  let payload: any;
  try {
    payload = _parseJsonStrict(raw);
  } catch (exc: any) {
    throw new MechanicalCaseError("mechanical case is not valid JSON");
  }
  const [caseData, error] = validate_mechanical_case(payload);
  if (caseData === null) {
    throw new MechanicalCaseError(error);
  }
  return [caseData, sha256_bytes(raw)];
}
