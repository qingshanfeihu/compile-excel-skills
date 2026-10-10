import crypto from "node:crypto";
import path from "node:path";
import { P as Path } from "../../_py";
import { lexical_absolute, lexical_path_inside_root, read_regular_nofollow, sha256_bytes, validate_json_budget } from "../../case_compiler/_sealed_io";
import { projection_receipt_valid } from "../../case_compiler/mindmap_contract_projector";
import { accepts_schema } from "../../common/schema_identity";
import * as CC from "./conflict_chain";
import * as F from "./facts";

export const PROOF_SCHEMA = "ist.consistency-requirement-proof";
export const REQUIRED = "required";
export const NOT_APPLICABLE = "not_applicable_no_governing_spec";
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _PROOF_KEYS = new Set([
  "schema",
  "autoid",
  "batch_name",
  "requirement",
  "binding_status",
  "base_contract_sha256",
  "machine_mindmap_sha256",
  "projection_sha256",
  "governing_spec_status",
  "governing_spec_status_sha256",
  "defect_spec_status",
  "defect_spec_status_sha256",
  "defect_spec_receipt_sha256",
]);

export class ConsistencyRequirementError extends Error {
  code: string;
  detail: string;
  constructor(code: string, detail: string) {
    super(`${code}: ${detail}`);
    this.name = "ConsistencyRequirementError";
    this.code = String(code);
    this.detail = String(detail);
  }
}

function _raise(code: string, detail: string): never {
  throw new ConsistencyRequirementError(code, detail);
}

function _safe_component(value: any, opts: { field: string }): string {
  const name = String(value ?? "").trim();
  if (!name || name === "." || name === ".." || path.isAbsolute(name) || name.includes("/") || name.includes("\\") || name.includes("~") || [...name].some((ch) => ch.charCodeAt(0) < 32) || name.length > 180) {
    _raise("batch_identity_invalid", `${opts.field} is not one safe output component`);
  }
  return name;
}

export function batch_name_from_contract_ref(opts: {
  project_root: string | Path;
  outputs_root: string | Path;
  autoid: string;
  contract_ref: string;
}): string {
  const aid = _safe_component(opts.autoid, { field: "autoid" });
  const project = lexical_absolute(opts.project_root.toString());
  const outputs = lexical_absolute(opts.outputs_root.toString());
  let path_: string;
  try {
    path_ = lexical_path_inside_root(path.join(project, String(opts.contract_ref ?? "")), outputs, {
      errorType: ValueError,
      traversal_message: "contract ref traversal is forbidden",
      outside_message: "contract ref escaped outputs root",
    });
  } catch (exc) {
    _raise("batch_identity_invalid", String(exc));
  }
  if (path.basename(path_) !== `${aid}.json` || path.basename(path.dirname(path_)) !== "contracts") {
    _raise("batch_identity_invalid", "base contract is not the bound contracts/<autoid>.json sibling");
  }
  const batch_dir = path.dirname(path.dirname(path_));
  if (path.dirname(batch_dir) !== outputs) {
    _raise("batch_identity_invalid", "base contract batch is not a direct output child");
  }
  return _safe_component(path.basename(batch_dir), { field: "batch_name" });
}

function _read_status(path_: Path, opts: { kind: string; max_bytes: number }): [Record<string, any>, Buffer] {
  const code = `${opts.kind}_status_unavailable`;
  let raw: Buffer;
  let payload: any;
  try {
    raw = read_regular_nofollow(path_.toString(), {
      trusted_root: path_.parent.toString(),
      errorType: ValueError,
      invalid_message: `${opts.kind} status path is invalid`,
      directory_message: `${opts.kind} status directory is unavailable`,
      open_message: `${opts.kind} status is unavailable`,
      bounds_message: `${opts.kind} status exceeds its sealed size boundary`,
      changed_message: `${opts.kind} status changed while being read`,
      max_bytes: opts.max_bytes,
      min_bytes: 1,
      require_current_uid: true,
    }) as Buffer;
    validate_json_budget(raw, { errorType: ValueError, message: `${opts.kind} status exceeds the JSON structure budget`, maxTokens: 100000 });
    payload = JSON.parse(raw.toString("utf8"));
  } catch (exc) {
    _raise(code, `${exc instanceof Error ? exc.name : "Error"}: ${exc}`);
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    _raise(`${opts.kind}_status_invalid`, `${opts.kind} status must be a JSON object`);
  }
  return [payload, raw];
}

function _canonical_sha256(value: any): string {
  return crypto.createHash("sha256").update(JSON.stringify(value, null, 0), "utf8").digest("hex");
}

export const RESEAL_TRIGGER_EVENTS = new Set(["criterion_rule_updated"]);

export function sealed_projection_reseal_trigger(facts: Record<string, any>[], opts: { receipt_index: number; case_ids: Set<string> }): string {
  for (let index = Math.max(Number(opts.receipt_index), -1) + 1; index < facts.length; index++) {
    const fact = facts[index];
    if (typeof fact !== "object" || fact === null) continue;
    const event = String(fact.ev ?? "");
    if (!RESEAL_TRIGGER_EVENTS.has(event)) continue;
    const aid = String(fact.aid ?? "");
    if (aid && !opts.case_ids.has(aid)) continue;
    return event;
  }
  return "";
}

function _latest_recompose(batch_dir: Path, opts: { autoid: string; facts: Record<string, any>[] | null }): Record<string, any> {
  let loaded: Record<string, any>[];
  if (opts.facts === null || opts.facts === undefined) {
    try {
      loaded = F.load_facts(batch_dir.join("facts.jsonl") as any);
    } catch (exc) {
      _raise("facts_unavailable", `${exc instanceof Error ? exc.name : "Error"}: ${exc}`);
    }
  } else {
    loaded = opts.facts;
  }
  if (!Array.isArray(loaded)) {
    _raise("facts_invalid", "facts must be a sequence of JSON objects");
  }
  let receipt_index = -1;
  let receipt: Record<string, any> | null = null;
  for (let index = loaded.length - 1; index >= 0; index--) {
    const item = loaded[index];
    if (typeof item === "object" && item !== null && item.ev === "recompose_done") {
      receipt_index = index;
      receipt = { ...item };
      break;
    }
  }
  if (receipt === null) {
    _raise("recompose_receipt_missing", "latest recompose_done is unavailable");
  }
  for (const item of loaded.slice(receipt_index + 1)) {
    if (typeof item === "object" && item !== null && item.ev === "conflict_chain_reentered" && ["", opts.autoid].includes(String(item.aid ?? ""))) {
      _raise("recompose_receipt_superseded", "latest projection was invalidated by reentry");
    }
  }
  return receipt;
}

export function resolve_consistency_requirement(opts: {
  outputs_root: string | Path;
  project_root: string | Path;
  batch_name: string;
  autoid: string;
  facts?: Record<string, any>[] | null;
}): Record<string, any> {
  const outputs = lexical_absolute(opts.outputs_root.toString());
  const project = lexical_absolute(opts.project_root.toString());
  const batch = _safe_component(opts.batch_name, { field: "batch_name" });
  const aid = _safe_component(opts.autoid, { field: "autoid" });
  const batch_dir = lexical_absolute(path.join(outputs, batch));
  if (path.dirname(batch_dir) !== outputs) {
    _raise("batch_identity_invalid", "batch is not a direct output child");
  }
  const receipt = _latest_recompose(new Path(batch_dir), { autoid: aid, facts: opts.facts ?? null });
  if (!projection_receipt_valid(new Path(batch_dir).toString(), receipt)) {
    _raise("projection_receipt_invalid", "latest projection receipt is not byte-closed");
  }
  const contract_map = receipt.contract_sha256_by_autoid;
  const written = receipt.written_autoids;
  const contract_sha = typeof contract_map === "object" && contract_map !== null ? String(contract_map[aid] ?? "") : "";
  if (!_SHA256_RE.test(contract_sha) || !Array.isArray(written) || written.filter((x: string) => x === aid).length !== 1) {
    _raise("contract_identity_missing", "autoid is absent or duplicated in the signed projection contract map");
  }
  const [governing, governing_raw] = _read_status(new Path(path.join(batch_dir, "governing_spec_status.json")), { kind: "governing_spec", max_bytes: 1024 * 1024 });
  const expected_governing_sha = String(receipt.governing_spec_status_sha256 ?? "");
  if (!_SHA256_RE.test(expected_governing_sha) || sha256_bytes(governing_raw) !== expected_governing_sha) {
    _raise("governing_spec_status_sha256_mismatch", "governing status bytes differ from recompose_done");
  }
  const governing_status = String(governing.status ?? "");
  if (!accepts_schema(governing.schema, "ist.governing-spec-status") || !governing_status || governing_status !== String(receipt.governing_spec_status ?? "")) {
    _raise("governing_spec_status_identity_mismatch", "governing status payload differs from recompose_done");
  }
  const governing_pairs: [string, string][] = [
    ["name", "governing_spec"],
    ["sha256", "governing_spec_sha256"],
    ["size", "governing_spec_size"],
    ["generation_id", "governing_spec_generation_id"],
    ["manifest_sha256", "governing_spec_manifest_sha256"],
  ];
  if (governing_pairs.some(([sidecar_key, receipt_key]) => governing[sidecar_key] !== receipt[receipt_key])) {
    _raise("governing_spec_status_identity_mismatch", "governing status source identity differs from recompose_done");
  }
  const [defect, defect_raw] = _read_status(new Path(path.join(batch_dir, "defect_spec_status.json")), { kind: "defect_spec", max_bytes: 4 * 1024 * 1024 });
  const expected_defect_sha = String(receipt.defect_spec_status_sha256 ?? "");
  if (!_SHA256_RE.test(expected_defect_sha) || sha256_bytes(defect_raw) !== expected_defect_sha) {
    _raise("defect_spec_status_sha256_mismatch", "DefectSpec status bytes differ from recompose_done");
  }
  const defect_status = String(defect.status ?? "");
  const defect_receipt_sha = defect.receipt_sha256;
  const fact_defect_receipt_sha = receipt.defect_spec_receipt_sha256;
  if (!accepts_schema(defect.schema, "ist.defect-spec-status") || !defect_status || defect_status !== String(receipt.defect_spec_status ?? "") || defect_receipt_sha !== fact_defect_receipt_sha) {
    _raise("defect_spec_status_identity_mismatch", "DefectSpec status payload differs from recompose_done");
  }
  const embedded_receipt = defect.receipt;
  if (typeof embedded_receipt === "object" && embedded_receipt !== null) {
    if (!_SHA256_RE.test(String(defect_receipt_sha ?? "")) || _canonical_sha256(embedded_receipt) !== defect_receipt_sha) {
      _raise("defect_spec_receipt_sha256_mismatch", "DefectSpec receipt digest differs from its status sidecar");
    }
  } else if (embedded_receipt !== null || defect_receipt_sha !== null) {
    _raise("defect_spec_receipt_sha256_mismatch", "DefectSpec receipt and receipt_sha256 must be present together");
  }
  if (defect_status === "resolved" && (defect.eligible !== true || typeof embedded_receipt !== "object" || embedded_receipt === null)) {
    _raise("defect_spec_status_identity_mismatch", "resolved DefectSpec lacks an eligible sealed receipt");
  }
  const requirement = !CC.spec_absent(governing_status) || defect_status === "resolved" ? REQUIRED : NOT_APPLICABLE;
  const proof: Record<string, any> = {
    schema: PROOF_SCHEMA,
    autoid: aid,
    batch_name: batch,
    requirement,
    binding_status: requirement === NOT_APPLICABLE ? "not_applicable" : "pending",
    base_contract_sha256: contract_sha,
    machine_mindmap_sha256: String(receipt.machine_mindmap_sha256 ?? ""),
    projection_sha256: String(receipt.projection_sha256 ?? receipt.disclosure_sha256 ?? ""),
    governing_spec_status: governing_status,
    governing_spec_status_sha256: expected_governing_sha,
    defect_spec_status: defect_status,
    defect_spec_status_sha256: expected_defect_sha,
    defect_spec_receipt_sha256: defect_receipt_sha,
  };
  if (Object.keys(proof).length !== _PROOF_KEYS.size || ![..._PROOF_KEYS].every((k) => k in proof)) {
    _raise("proof_shape_invalid", "consistency requirement proof keys drifted");
  }
  if (!_SHA256_RE.test(proof.machine_mindmap_sha256) || !_SHA256_RE.test(proof.projection_sha256)) {
    _raise("projection_receipt_invalid", "projection identity is incomplete");
  }
  return proof;
}

export function validate_consistency_requirement(opts: {
  outputs_root: string | Path;
  project_root: string | Path;
  batch_name: string;
  autoid: string;
  intent: Record<string, any>;
  require_complete?: boolean;
  facts?: Record<string, any>[] | null;
}): Record<string, any> {
  const proof = resolve_consistency_requirement(opts);
  const aid = proof.autoid;
  if (typeof opts.intent !== "object" || opts.intent === null || String(opts.intent.autoid ?? "") !== aid) {
    _raise("intent_identity_invalid", "intent autoid is absent or drifted");
  }
  const expected_contract = lexical_absolute(path.join(lexical_absolute(opts.outputs_root.toString()), proof.batch_name, "contracts", `${aid}.json`));
  let expected_contract_ref: string;
  try {
    expected_contract_ref = path.relative(lexical_absolute(opts.project_root.toString()), expected_contract);
  } catch {
    _raise("intent_contract_identity_mismatch", "contract path escaped project root");
  }
  if (opts.intent.typed_expectation_contract_path !== expected_contract_ref || opts.intent.typed_expectation_contract_sha256 !== proof.base_contract_sha256) {
    _raise("intent_contract_identity_mismatch", "intent base contract differs from the signed projection contract map");
  }
  if (String(opts.intent.governing_spec_status ?? "") !== proof.governing_spec_status) {
    _raise("intent_governing_status_mismatch", "intent governing status differs from the signed status sidecar");
  }
  if (String(opts.intent.consistency_requirement ?? "") !== proof.requirement) {
    _raise("intent_requirement_mismatch", "intent consistency requirement differs from cross-ledger evidence");
  }
  const status = String(opts.intent.consistency_binding_status ?? "");
  const overlay_path = opts.intent.consistency_contract_path;
  const overlay_sha = opts.intent.consistency_contract_sha256;
  const receipt_sha = opts.intent.consistency_receipt_sha256;
  if (proof.requirement === NOT_APPLICABLE) {
    if (status !== "not_applicable" || overlay_path !== null || overlay_sha !== null || receipt_sha !== null) {
      _raise("intent_binding_invalid", "not-applicable intent must keep every overlay identity null");
    }
  } else if (status === "pending") {
    if (opts.require_complete ?? false) {
      _raise("intent_binding_incomplete", "required overlay binding is pending");
    }
    if (overlay_path !== null || overlay_sha !== null || receipt_sha !== null) {
      _raise("intent_binding_invalid", "pending required intent cannot predeclare overlay identities");
    }
  } else if (status === "complete") {
    const expected_overlay = lexical_absolute(path.join(lexical_absolute(opts.outputs_root.toString()), aid, "consistency_contract.json"));
    let expected_overlay_ref: string;
    try {
      expected_overlay_ref = path.relative(lexical_absolute(opts.project_root.toString()), expected_overlay);
    } catch {
      _raise("intent_binding_invalid", "overlay path escaped project root");
    }
    if (overlay_path !== expected_overlay_ref || !_SHA256_RE.test(String(overlay_sha ?? "")) || !_SHA256_RE.test(String(receipt_sha ?? ""))) {
      _raise("intent_binding_invalid", "complete required intent has an invalid overlay identity");
    }
  } else {
    _raise("intent_binding_invalid", "required intent binding status is not closed");
  }
  return proof;
}

export function validate_recorded_consistency_requirement_proof(opts: {
  outputs_root: string | Path;
  project_root: string | Path;
  autoid: string;
  intent: Record<string, any>;
  recorded_proof: Record<string, any>;
  require_complete?: boolean;
}): Record<string, any> {
  if (
    typeof opts.recorded_proof !== "object" ||
    opts.recorded_proof === null ||
    Object.keys(opts.recorded_proof).length !== _PROOF_KEYS.size ||
    ![..._PROOF_KEYS].every((k) => k in opts.recorded_proof) ||
    opts.recorded_proof.schema !== PROOF_SCHEMA ||
    String(opts.recorded_proof.autoid ?? "") !== String(opts.autoid ?? "")
  ) {
    _raise("recorded_proof_shape_invalid", "lint credential consistency proof has an invalid exact-key shape");
  }
  const batch_name = _safe_component(opts.recorded_proof.batch_name, { field: "batch_name" });
  const fresh = validate_consistency_requirement({ ...opts, batch_name, require_complete: opts.require_complete ?? true });
  if (_canonical_sha256({ ...opts.recorded_proof }) !== _canonical_sha256(fresh)) {
    _raise("recorded_proof_identity_mismatch", "lint credential consistency proof differs from current sealed batch evidence");
  }
  return fresh;
}

class ValueError extends Error {
  constructor(message?: string) {
    super(message);
    this.name = "ValueError";
  }
}
