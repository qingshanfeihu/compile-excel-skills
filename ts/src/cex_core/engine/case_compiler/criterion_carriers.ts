import crypto from "node:crypto";
import { accepts_engine_schema, engine_schema_id } from "../common/engine_track_schema";

export class Carrier {
  block_kind: string;
  operator: string;
  lowering_operators: string[];
  implementation_blocks: string[];
  constructor(block_kind: string, operator: string, lowering_operators: string[], implementation_blocks: string[] = []) {
    this.block_kind = block_kind;
    this.operator = operator;
    this.lowering_operators = lowering_operators;
    this.implementation_blocks = implementation_blocks;
    Object.freeze(this);
  }
}

export class CriterionCarriers {
  criterion_type: string;
  label_zh: string;
  carriers: Carrier[];
  constructor(criterion_type: string, label_zh: string, carriers: Carrier[]) {
    this.criterion_type = criterion_type;
    this.label_zh = label_zh;
    this.carriers = carriers;
    Object.freeze(this);
  }
}

function _assertion(operator: string): Carrier {
  return new Carrier("OBSERVE_ASSERT", operator, [operator]);
}

export const CRITERION_CARRIERS: CriterionCarriers[] = [
  new CriterionCarriers("reachability", "可达性", [new Carrier("OBSERVE_EXIT", "", ["found"]), _assertion("found"), _assertion("abs_found")]),
  new CriterionCarriers("status_value", "状态值", [
    _assertion("found"), _assertion("abs_found"), _assertion("not_found"),
    new Carrier("OBSERVE_EXIT", "", ["found"]),
    new Carrier("EXPECT_FROM", "", ["found", "not_found", "abs_found"], ["CAPTURE"]),
  ]),
  new CriterionCarriers("content_match", "内容匹配", [
    _assertion("found"), _assertion("abs_found"),
    new Carrier("OBSERVE_MEMBER", "", ["found", "not_found"]),
  ]),
  new CriterionCarriers("absence", "不存在性", [_assertion("not_found")]),
  new CriterionCarriers("count", "计数", [_assertion("found_times")]),
  new CriterionCarriers("distribution", "分布", [new Carrier("OBSERVE_DIST", "", ["found"])]),
  new CriterionCarriers("before_after", "前后对照", [new Carrier("CAPTURE_COMPARE", "", ["found", "not_found"], ["CAPTURE"])]),
];

export const CRITERION_TYPE_ALLOWED_SLOTS: Record<string, Set<[string, string]>> = Object.fromEntries(
  CRITERION_CARRIERS.map((item) => [
    item.criterion_type,
    new Set(item.carriers.map((carrier) => [carrier.block_kind, carrier.operator] as [string, string])),
  ])
);

export function criterion_type_blueprints(): Array<Record<string, any>> {
  const out: Array<Record<string, any>> = [];
  for (const item of CRITERION_CARRIERS) {
    const implementations: Record<string, string[]> = {};
    for (const carrier of item.carriers) {
      for (const kind of carrier.implementation_blocks) {
        (implementations[kind] = implementations[kind] || []).push(carrier.block_kind);
      }
    }
    const operators: string[] = [];
    const seenOps = new Set<string>();
    for (const carrier of item.carriers) {
      for (const op of carrier.lowering_operators) {
        if (!seenOps.has(op)) {
          seenOps.add(op);
          operators.push(op);
        }
      }
    }
    const blockKinds: string[] = [];
    const seenKinds = new Set<string>();
    for (const k of [...item.carriers.map((c) => c.block_kind), ...Object.keys(implementations)]) {
      if (!seenKinds.has(k)) {
        seenKinds.add(k);
        blockKinds.push(k);
      }
    }
    out.push({
      criterion_type: item.criterion_type,
      label_zh: item.label_zh,
      operators,
      block_kinds: blockKinds,
      allowed_slots: item.carriers.map((carrier) => ({ block_kind: carrier.block_kind, operator: carrier.operator })),
      implementation_blocks: Object.entries(implementations).map(([kind, users]) => ({
        block_kind: kind,
        role: "observation_only",
        used_by: users,
      })),
    });
  }
  return out;
}

function _digest(value: any): string {
  const canonical = (v: any): any => {
    if (Array.isArray(v)) return v.map(canonical);
    if (typeof v === "object" && v !== null) {
      const out: Record<string, any> = {};
      for (const k of Object.keys(v).sort()) out[k] = canonical(v[k]);
      return out;
    }
    return v;
  };
  return crypto.createHash("sha256").update(Buffer.from(JSON.stringify(canonical(value)), "utf8")).digest("hex");
}

export function carrier_contract_sha256(): string {
  return _digest(criterion_type_blueprints());
}

export class RequirementSource {
  kind: string;
  ref: string;
  raw: Buffer;
  constructor(kind: string, ref: string, raw: Buffer) {
    this.kind = kind;
    this.ref = ref;
    this.raw = raw;
    Object.freeze(this);
  }
}

const _REQUIREMENT_AUTHORITIES = new Set(["expectation", "author_claim", "defect_spec_claim"]);
const _SHA256 = /^[0-9a-f]{64}$/;
const _UNVERIFIED_REASONS = new Set([
  "requirements_absent", "requirement_source_identity_invalid", "requirement_source_unavailable",
  "claim_identity_unavailable", "claim_identity_invalid", "requirement_document_invalid",
  "requirement_binding_mismatch", "requirement_coverage_incomplete", "requirement_content_missing",
  "requirement_alternatives_missing",
]);

function _isMap(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function requirement_reference_valid(value: any): boolean {
  return Boolean(
    _isMap(value) &&
      Object.keys(value).sort().join(",") === "kind,ref,sha256" &&
      typeof value.kind === "string" &&
      _REQUIREMENT_AUTHORITIES.has(value.kind) &&
      typeof value.ref === "string" &&
      value.ref.trim() &&
      _SHA256.test(String(value.sha256 || ""))
  );
}

export function normalization_identity(claim: Record<string, any>): string {
  return _digest(
    Object.fromEntries(
      ["expectation_id", "semantic_key", "original_claim_sha256", "status", "criterion_type", "rule_id", "rule_identity", "catalog_sha256"].map((key) => [key, claim[key]])
    )
  );
}

function _unverified(base: Record<string, any>, reason: string): Record<string, any> {
  if (!_UNVERIFIED_REASONS.has(reason)) {
    throw new Error("unregistered requirement verification reason");
  }
  return { ...base, status: "unverified", reason, obligations: [] };
}

function _sourceIdentity(source: RequirementSource, pointer: string): Record<string, string> {
  return {
    kind: source.kind,
    ref: source.ref,
    source_sha256: crypto.createHash("sha256").update(source.raw).digest("hex"),
    pointer,
  };
}

export function derive_required_carriers(
  expectation: Record<string, any>,
  normalized_claim: Record<string, any>,
  opts: { requirement_sources?: Record<string, RequirementSource> | null } = {}
): Record<string, any> {
  const claim = normalized_claim;
  const base = {
    schema: engine_schema_id("required_carriers"),
    expectation_id: String(claim.expectation_id || ""),
    semantic_key: String(claim.semantic_key || ""),
    claim_sha256: String(claim.original_claim_sha256 || ""),
    normalization_sha256: normalization_identity(claim),
    check_scope: "all_obligations_in_explicit_requirement_document",
  };
  const reference = expectation.criterion_requirements_ref;
  if (!_isMap(reference)) {
    return _unverified(base, "requirements_absent");
  }
  if (!requirement_reference_valid(reference)) {
    return _unverified(base, "requirement_source_identity_invalid");
  }
  const source = (opts.requirement_sources || {})[reference.ref];
  if (!(source instanceof RequirementSource)) {
    return _unverified(base, "requirement_source_unavailable");
  }
  if (
    source.kind !== reference.kind ||
    source.ref !== reference.ref ||
    !Buffer.isBuffer(source.raw) ||
    crypto.createHash("sha256").update(source.raw).digest("hex") !== reference.sha256
  ) {
    return _unverified(base, "requirement_source_identity_invalid");
  }
  const sourceClaim = expectation.author_claim || expectation.defect_spec_claim;
  if (!_isMap(sourceClaim)) {
    return _unverified(base, "claim_identity_unavailable");
  }
  if (
    !base.expectation_id ||
    !base.semantic_key ||
    !_SHA256.test(base.claim_sha256) ||
    sourceClaim.expectation_id !== base.expectation_id ||
    sourceClaim.semantic_key !== base.semantic_key ||
    sourceClaim.claim_sha256 !== base.claim_sha256 ||
    claim.status !== "matched" ||
    !claim.criterion_type ||
    !claim.rule_id ||
    !_isMap(claim.rule_identity) ||
    !Object.keys(claim.rule_identity).length ||
    !_SHA256.test(String(claim.catalog_sha256 || ""))
  ) {
    return _unverified(base, "claim_identity_invalid");
  }
  let document: any;
  try {
    document = JSON.parse(source.raw.toString("utf8"));
  } catch {
    return _unverified(base, "requirement_document_invalid");
  }
  const expectedFields = new Set(["schema", "expectation_id", "semantic_key", "claim_sha256", "normalization_sha256", "coverage", "obligations"]);
  if (!_isMap(document) || Object.keys(document).sort().join(",") !== [...expectedFields].sort().join(",")) {
    return _unverified(base, "requirement_document_invalid");
  }
  if (!accepts_engine_schema(document.schema, "criterion_requirements")) {
    return _unverified(base, "requirement_document_invalid");
  }
  if (["expectation_id", "semantic_key", "claim_sha256", "normalization_sha256"].some((key) => document[key] !== (base as any)[key])) {
    return _unverified(base, "requirement_binding_mismatch");
  }
  const obligations = document.obligations;
  const coverage = document.coverage;
  if (
    !Array.isArray(obligations) || !obligations.length ||
    !_isMap(coverage) ||
    Object.keys(coverage).sort().join(",") !== "obligation_ids,scope" ||
    coverage.scope !== "complete" ||
    !Array.isArray(coverage.obligation_ids)
  ) {
    return _unverified(base, "requirement_coverage_incomplete");
  }
  const normalized: Array<Record<string, any>> = [];
  const obligationIds: string[] = [];
  for (let index = 0; index < obligations.length; index++) {
    const obligation = obligations[index];
    if (!_isMap(obligation) || Object.keys(obligation).sort().join(",") !== "alternatives,obligation_id,requirement") {
      return _unverified(base, "requirement_document_invalid");
    }
    const identifier = obligation.obligation_id;
    if (typeof identifier !== "string" || !identifier.trim() || obligationIds.includes(identifier)) {
      return _unverified(base, "requirement_coverage_incomplete");
    }
    if (typeof obligation.requirement !== "string" || !obligation.requirement.trim()) {
      return _unverified(base, "requirement_content_missing");
    }
    const alternatives = obligation.alternatives;
    if (!Array.isArray(alternatives) || !alternatives.length) {
      return _unverified(base, "requirement_alternatives_missing");
    }
    const choices: Array<Record<string, any>> = [];
    const choiceIds = new Set<string>();
    for (let choiceIndex = 0; choiceIndex < alternatives.length; choiceIndex++) {
      const choice = alternatives[choiceIndex];
      if (!_isMap(choice) || Object.keys(choice).sort().join(",") !== "alternative_id,carriers") {
        return _unverified(base, "requirement_document_invalid");
      }
      const choiceId = choice.alternative_id;
      if (typeof choiceId !== "string" || !choiceId.trim() || choiceIds.has(choiceId)) {
        return _unverified(base, "requirement_document_invalid");
      }
      const carrierRows = choice.carriers;
      if (!Array.isArray(carrierRows) || !carrierRows.length) {
        return _unverified(base, "requirement_alternatives_missing");
      }
      const pairs: string[] = [];
      for (const row of carrierRows) {
        if (
          !_isMap(row) ||
          Object.keys(row).sort().join(",") !== "block_kind,operator" ||
          typeof row.block_kind !== "string" || !row.block_kind.trim() ||
          typeof row.operator !== "string"
        ) {
          return _unverified(base, "requirement_document_invalid");
        }
        const pair = `${row.block_kind}${row.operator}`;
        if (pairs.includes(pair)) {
          return _unverified(base, "requirement_document_invalid");
        }
        pairs.push(pair);
      }
      choiceIds.add(choiceId);
      choices.push({
        alternative_id: choiceId,
        carriers: carrierRows.map((row: any) => ({ ...row })),
        identity: _sourceIdentity(source, `/obligations/${index}/alternatives/${choiceIndex}`),
      });
    }
    obligationIds.push(identifier);
    normalized.push({
      obligation_id: identifier,
      requirement: obligation.requirement,
      alternatives: choices,
      identity: _sourceIdentity(source, `/obligations/${index}`),
    });
  }
  if (JSON.stringify(coverage.obligation_ids) !== JSON.stringify(obligationIds)) {
    return _unverified(base, "requirement_coverage_incomplete");
  }
  const result: Record<string, any> = {
    ...base,
    status: "verified",
    reason: "",
    source_identity: _sourceIdentity(source, ""),
    coverage: { scope: "complete", obligation_ids: [...obligationIds] },
    obligations: normalized,
  };
  result.requirements_sha256 = _digest(result);
  return result;
}

export function bind_requirement_source(expectation: Record<string, any>, source: RequirementSource): Record<string, any> {
  const result = JSON.parse(JSON.stringify(expectation));
  result.criterion_requirements_ref = {
    kind: source.kind,
    ref: source.ref,
    sha256: crypto.createHash("sha256").update(source.raw).digest("hex"),
  };
  const claim = result.normalized_claim;
  if (!_isMap(claim)) {
    throw new Error("normalized claim is required before binding requirement evidence");
  }
  const required = derive_required_carriers(result, claim, { requirement_sources: { [source.ref]: source } });
  if (required.status !== "verified") {
    throw new Error(String(required.reason));
  }
  claim.required_carriers = required;
  return result;
}

export function required_carriers_record_error(value: any, claim: Record<string, any>): string {
  const base = derive_required_carriers({}, claim);
  const baseFields = new Set(Object.keys(base).filter((k) => k !== "status" && k !== "reason" && k !== "obligations"));
  if (!_isMap(value) || [...baseFields].some((key) => JSON.stringify(value[key]) !== JSON.stringify((base as any)[key]))) {
    return "required carrier record identity is invalid";
  }
  if (value.status === "unverified") {
    if (
      Object.keys(value).sort().join(",") !== Object.keys(base).sort().join(",") ||
      typeof value.reason !== "string" ||
      !_UNVERIFIED_REASONS.has(value.reason) ||
      JSON.stringify(value.obligations) !== "[]"
    ) {
      return "unverified required carrier record is invalid";
    }
    return "";
  }
  if (
    Object.keys(value).sort().join(",") !==
    [...Object.keys(base), "source_identity", "coverage", "requirements_sha256"].sort().join(",")
  ) {
    return "required carrier record fields are not closed";
  }
  if (value.status !== "verified" || value.reason !== "") {
    return "required carrier record status is invalid";
  }
  const body: Record<string, any> = {};
  for (const [key, item] of Object.entries(value)) {
    if (key !== "requirements_sha256") {
      body[key] = item;
    }
  }
  if (_digest(body) !== value.requirements_sha256) {
    return "required carrier record digest is invalid";
  }
  const identity = value.source_identity;
  if (
    !_isMap(identity) ||
    Object.keys(identity).sort().join(",") !== "kind,pointer,ref,source_sha256" ||
    identity.pointer !== "" ||
    !requirement_reference_valid({ kind: identity.kind, ref: identity.ref, sha256: identity.source_sha256 })
  ) {
    return "required carrier source identity is invalid";
  }
  const obligations = value.obligations;
  if (!Array.isArray(obligations) || !obligations.length) {
    return "required carrier obligations are empty";
  }
  const ids: string[] = [];
  for (let index = 0; index < obligations.length; index++) {
    const obligation = obligations[index];
    if (!_isMap(obligation) || Object.keys(obligation).sort().join(",") !== "alternatives,identity,obligation_id,requirement") {
      return "required carrier obligation fields are not closed";
    }
    const identifier = obligation.obligation_id;
    if (typeof identifier !== "string" || !identifier.trim() || ids.includes(identifier)) {
      return "required carrier obligation identity is invalid";
    }
    if (typeof obligation.requirement !== "string" || !obligation.requirement.trim()) {
      return "required carrier obligation content is empty";
    }
    if (JSON.stringify(obligation.identity) !== JSON.stringify({ ...identity, pointer: `/obligations/${index}` })) {
      return "required carrier obligation source is invalid";
    }
    const alternatives = obligation.alternatives;
    if (!Array.isArray(alternatives) || !alternatives.length) {
      return "required carrier alternatives are empty";
    }
    const choiceIds = new Set<string>();
    for (let choiceIndex = 0; choiceIndex < alternatives.length; choiceIndex++) {
      const choice = alternatives[choiceIndex];
      if (!_isMap(choice) || Object.keys(choice).sort().join(",") !== "alternative_id,carriers,identity") {
        return "required carrier alternative fields are not closed";
      }
      const choiceId = choice.alternative_id;
      if (typeof choiceId !== "string" || !choiceId.trim() || choiceIds.has(choiceId)) {
        return "required carrier alternative identity is invalid";
      }
      if (JSON.stringify(choice.identity) !== JSON.stringify({ ...identity, pointer: `/obligations/${index}/alternatives/${choiceIndex}` })) {
        return "required carrier alternative source is invalid";
      }
      const rows = choice.carriers;
      if (!Array.isArray(rows) || !rows.length) {
        return "required carrier alternative slots are empty";
      }
      const pairs = new Set<string>();
      for (const row of rows) {
        if (
          !_isMap(row) ||
          Object.keys(row).sort().join(",") !== "block_kind,operator" ||
          typeof row.block_kind !== "string" || !row.block_kind.trim() ||
          typeof row.operator !== "string" ||
          pairs.has(`${row.block_kind}${row.operator}`)
        ) {
          return "required carrier slot shape is invalid";
        }
        pairs.add(`${row.block_kind}${row.operator}`);
      }
      choiceIds.add(choiceId);
    }
    ids.push(identifier);
  }
  if (JSON.stringify(value.coverage) !== JSON.stringify({ scope: "complete", obligation_ids: ids })) {
    return "required carrier obligation coverage is incomplete";
  }
  return "";
}

export function check_required_carriers(
  expectation: Record<string, any>,
  opts: { requirement_sources?: Record<string, RequirementSource> | null; allowed_slots?: Record<string, Set<string>> | null } = {}
): Record<string, any> {
  const claim = _isMap(expectation.normalized_claim) ? expectation.normalized_claim : {};
  const required = derive_required_carriers(expectation, claim, { requirement_sources: opts.requirement_sources ?? null });
  const result: Record<string, any> = {
    ...required,
    check_scope: "registered_slots_for_all_explicit_obligations",
    carrier_contract_sha256: carrier_contract_sha256(),
    supported_alternatives: {},
    uncovered_obligations: [],
  };
  if (required.status !== "verified") {
    return result;
  }
  const stored = claim.required_carriers;
  if (stored !== null && stored !== undefined && JSON.stringify(stored) !== JSON.stringify(required)) {
    return { ...result, status: "unverified", reason: "required_carriers_receipt_mismatch" };
  }
  const slots = (opts.allowed_slots ?? CRITERION_TYPE_ALLOWED_SLOTS)[String(claim.criterion_type || "")] || new Set<[string, string]>();
  const slotKeys = new Set([...slots].map(([k, op]) => `${k}${op}`));
  for (const obligation of required.obligations) {
    const identifier = obligation.obligation_id;
    const supported = obligation.alternatives
      .filter((alternative: any) => alternative.carriers.every((row: any) => slotKeys.has(`${row.block_kind}${row.operator}`)))
      .map((alternative: any) => alternative.alternative_id);
    result.supported_alternatives[identifier] = supported;
    if (!supported.length) {
      result.uncovered_obligations.push(identifier);
    }
  }
  result.status = result.uncovered_obligations.length ? "gap" : "supported";
  result.reason = result.uncovered_obligations.length ? "required_carrier_unavailable" : "";
  return result;
}
