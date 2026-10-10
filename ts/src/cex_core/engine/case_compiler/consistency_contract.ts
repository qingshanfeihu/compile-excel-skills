import crypto from "node:crypto";
import path from "node:path";
import { atomic_write_bytes_nofollow, canonical_json, read_regular_nofollow, sha256_bytes, validate_json_budget } from "./_sealed_io";
import { _CONSISTENCY_MATERIAL_KEYS, _CONSISTENCY_MATERIAL_SCHEMA, _expectation_id, _norm_ws, _source_atom_forms } from "./mindmap_contract_projector";
import { CONSISTENCY_CONTRACT_SIDECAR_NAME } from "../engine_managed_outputs";

export const CONSISTENCY_CONTRACT_SCHEMA = "ist.consistency-contract";
export const SPEC_ENDORSEMENT_SCHEMA = "ist.spec-endorsement";
export const SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY = 1;
export const SPEC_ENDORSEMENT_EXPECTATION_BINDING_SCHEMA = "ist.spec-endorsement-expectation-binding";
const _AUTOID_RE = /^[0-9]{18}$/;
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _OUTER_KEYS = new Set(["schema", "autoid", "base_contract_sha256", "consistency_receipt_sha256", "spec_endorsement"]);
const _ENDORSEMENT_KEYS = new Set(["schema", "authority_groups", "scope", "spec_quote", "spec_locator", "case_quote", "case_locator"]);
const _MAX_BYTES = 256 * 1024;

export class ConsistencyContractError extends Error {}

function _isMap(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _sameKeys(a: Record<string, any>, b: Set<string>): boolean {
  const keys = Object.keys(a);
  if (keys.length !== b.size) return false;
  return keys.every((k) => b.has(k));
}

export function spec_endorsement_expectation_binding_rule(): Record<string, any> {
  return {
    schema: SPEC_ENDORSEMENT_EXPECTATION_BINDING_SCHEMA,
    applies_when: { "spec_endorsement.scope.kind": "expectation" },
    base_expectation_count: { comparison: "exactly", value: SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY },
    mechanical_assertion_binding_count: { comparison: "exactly", value: SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY },
    note: "Read the engine-minted consistency_contract.json after an accepted consistent verdict. When its spec_endorsement scope names one expectation_id, that id is governed by these exact cardinalities; the general rule that permits differentiated assertions to share an expectation_id does not apply to the endorsed id.",
  };
}

export function consistency_material_receipt_sha256(material: Record<string, any>): string {
  return sha256_bytes(canonical_json({ ...material }, { ensure_ascii: false }));
}

function _baseExpectationIds(contract: Record<string, any>): string[] {
  const ids: string[] = [];
  for (const item of contract.expectations || []) {
    if (!_isMap(item)) continue;
    const carrier = ["assertion", "author_claim", "defect_spec_claim"].map((k) => item[k]).find(_isMap) || null;
    if (carrier) {
      ids.push(String(carrier.expectation_id || ""));
    }
  }
  return ids;
}

function _expectationScope(
  machine_case: Record<string, any>,
  material: Record<string, any>,
  base_contract: Record<string, any>
): Record<string, string> {
  const locator = String(material.case_locator || "");
  const quote = _norm_ws(String(material.case_quote || ""));
  const autoid = String(material.autoid || "");
  const candidates: string[] = [];
  let index = 0;
  for (const item of machine_case.expectations_by_step || []) {
    index++;
    if (!_isMap(item) || String(item.origin || "") !== locator) continue;
    const sourceText = String(item.text || "");
    const forms = new Set(_source_atom_forms(sourceText, locator).map(_norm_ws));
    if (!forms.has(quote)) continue;
    const step = String(item.n || "").trim();
    if (step) {
      candidates.push(_expectation_id(autoid, step, index));
    }
  }
  const baseIds = _baseExpectationIds(base_contract);
  const unique = new Set(candidates);
  if (unique.size === SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY) {
    const expectationId = Array.from(unique)[0];
    if (
      candidates.filter((c) => c === expectationId).length === SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY &&
      baseIds.filter((b) => b === expectationId).length === SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY
    ) {
      return { kind: "expectation", expectation_id: expectationId };
    }
  }
  return { kind: "case" };
}

export function build_consistency_contract(opts: {
  autoid: string;
  base_contract: Record<string, any>;
  base_contract_sha256: string;
  accepted_material: Record<string, any>;
  machine_case: Record<string, any>;
}): Record<string, any> {
  const { autoid, base_contract, base_contract_sha256, machine_case } = opts;
  const material = { ...opts.accepted_material };
  const receipt = consistency_material_receipt_sha256(material);
  if (
    !_AUTOID_RE.test(String(autoid || "")) ||
    String(base_contract.autoid || "") !== autoid ||
    String(material.autoid || "") !== autoid ||
    !_sameKeys(material, _CONSISTENCY_MATERIAL_KEYS) ||
    material.schema !== _CONSISTENCY_MATERIAL_SCHEMA ||
    material.verdict !== "consistent" ||
    !_SHA256_RE.test(String(base_contract_sha256 || ""))
  ) {
    throw new ConsistencyContractError("consistency_contract_identity_or_material_invalid");
  }
  const endorsement = {
    schema: SPEC_ENDORSEMENT_SCHEMA,
    authority_groups: ["Spec", "Author"],
    scope: _expectationScope(machine_case, material, base_contract),
    spec_quote: String(material.spec_quote),
    spec_locator: String(material.spec_locator),
    case_quote: String(material.case_quote),
    case_locator: String(material.case_locator),
  };
  return {
    schema: CONSISTENCY_CONTRACT_SCHEMA,
    autoid,
    base_contract_sha256,
    consistency_receipt_sha256: receipt,
    spec_endorsement: endorsement,
  };
}

export function validate_consistency_contract(
  overlay: Record<string, any>,
  opts: {
    base_contract: Record<string, any>;
    base_contract_sha256: string;
    accepted_material: Record<string, any>;
    consistency_receipt_sha256: string;
    machine_case?: Record<string, any> | null;
  }
): string {
  const { base_contract, base_contract_sha256, consistency_receipt_sha256 } = opts;
  const machine_case = opts.machine_case ?? null;
  if (!_isMap(overlay) || !_sameKeys(overlay, _OUTER_KEYS)) {
    return "consistency_contract_schema_keys_invalid";
  }
  const material = { ...opts.accepted_material };
  const autoid = String(material.autoid || "");
  if (
    overlay.schema !== CONSISTENCY_CONTRACT_SCHEMA ||
    !_AUTOID_RE.test(autoid) ||
    overlay.autoid !== autoid ||
    String(base_contract.autoid || "") !== autoid ||
    String(overlay.base_contract_sha256 || "") !== base_contract_sha256 ||
    !_SHA256_RE.test(String(base_contract_sha256 || "")) ||
    !_sameKeys(material, _CONSISTENCY_MATERIAL_KEYS) ||
    material.schema !== _CONSISTENCY_MATERIAL_SCHEMA ||
    material.verdict !== "consistent"
  ) {
    return "consistency_contract_identity_invalid";
  }
  const materialReceipt = consistency_material_receipt_sha256(material);
  if (materialReceipt !== consistency_receipt_sha256 || overlay.consistency_receipt_sha256 !== consistency_receipt_sha256) {
    return "consistency_contract_receipt_invalid";
  }
  const endorsement = overlay.spec_endorsement;
  if (!_isMap(endorsement) || !_sameKeys(endorsement, _ENDORSEMENT_KEYS)) {
    return "spec_endorsement_schema_keys_invalid";
  }
  if (
    endorsement.schema !== SPEC_ENDORSEMENT_SCHEMA ||
    JSON.stringify(endorsement.authority_groups) !== JSON.stringify(["Spec", "Author"]) ||
    ["spec_quote", "spec_locator", "case_quote", "case_locator"].some((field) => endorsement[field] !== material[field])
  ) {
    return "spec_endorsement_material_invalid";
  }
  const scope = endorsement.scope;
  if (!_isMap(scope)) {
    return "spec_endorsement_scope_invalid";
  }
  const recomputedScope = machine_case !== null ? _expectationScope(machine_case, material, base_contract) : null;
  if (scope.kind === "case") {
    if (Object.keys(scope).join(",") !== "kind") {
      return "spec_endorsement_scope_invalid";
    }
    if (recomputedScope !== null && JSON.stringify(scope) !== JSON.stringify(recomputedScope)) {
      return "spec_endorsement_scope_drift";
    }
  } else if (scope.kind === "expectation") {
    if (Object.keys(scope).sort().join(",") !== "expectation_id,kind" || machine_case === null) {
      return "spec_endorsement_scope_invalid";
    }
    if (recomputedScope === null || JSON.stringify(scope) !== JSON.stringify(recomputedScope) || recomputedScope.kind !== "expectation") {
      return "spec_endorsement_expectation_not_unique";
    }
  } else {
    return "spec_endorsement_scope_invalid";
  }
  return "";
}

export function consistency_contract_path(outputs_root: string, autoid: string): string {
  const aid = String(autoid || "");
  if (!_AUTOID_RE.test(aid)) {
    throw new ConsistencyContractError("consistency contract autoid is invalid");
  }
  return path.join(outputs_root, aid, CONSISTENCY_CONTRACT_SIDECAR_NAME);
}

export function write_consistency_contract(outputs_root: string, overlay: Record<string, any>): [string, string] {
  const autoid = String(overlay.autoid || "");
  const target = consistency_contract_path(outputs_root, autoid);
  const payload = canonical_json({ ...overlay }, { ensure_ascii: false });
  atomic_write_bytes_nofollow(target, payload, {
    errorType: ConsistencyContractError,
    invalid_message: "consistency contract path is invalid",
    unavailable_message: "consistency contract cannot be written safely",
    create_parents: false,
    mode: 0o600,
  });
  return [target, sha256_bytes(payload)];
}

export function parse_consistency_contract(raw: Buffer): [Record<string, any>, string] {
  if (!Buffer.isBuffer(raw) || raw.length < 1 || raw.length > _MAX_BYTES) {
    throw new ConsistencyContractError("consistency contract exceeds its byte budget");
  }
  validate_json_budget(raw, {
    errorType: ConsistencyContractError,
    message: "consistency contract exceeds its JSON structure budget",
    maxDepth: 32,
    maxTokens: 8192,
  });
  let payload: any;
  try {
    payload = JSON.parse(raw.toString("utf8"));
  } catch (exc) {
    throw new ConsistencyContractError("consistency contract is not valid JSON");
  }
  if (!_isMap(payload)) {
    throw new ConsistencyContractError("consistency contract must be a JSON object");
  }
  return [payload, sha256_bytes(raw)];
}

export function load_consistency_contract_document(p: string): [Record<string, any>, string, Buffer] {
  const raw = read_regular_nofollow(p, {
    errorType: ConsistencyContractError,
    invalid_message: "consistency contract path is invalid",
    directory_message: "consistency contract directory is unavailable",
    open_message: "consistency contract is unavailable",
    bounds_message: "consistency contract exceeds its byte budget",
    changed_message: "consistency contract changed while being read",
    max_bytes: _MAX_BYTES,
    min_bytes: 1,
    require_current_uid: true,
  }) as Buffer;
  const [payload, sha256] = parse_consistency_contract(raw);
  return [payload, sha256, raw];
}

export function load_consistency_contract(p: string): [Record<string, any>, string] {
  const [payload, sha256] = load_consistency_contract_document(p);
  return [payload, sha256];
}
