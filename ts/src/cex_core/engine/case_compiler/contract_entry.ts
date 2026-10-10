import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { accepts_schema as _acceptsSchema } from "../common/schema_identity";
import {
  atomic_write_bytes_nofollow,
  open_directory_nofollow,
  read_regular_at_nofollow,
  read_regular_nofollow,
  sha256_bytes,
  validate_json_budget,
} from "./_sealed_io";

export const SCHEMA_VERSION = 4;
export const CONTRACT_CLASSES = new Set(["pattern", "mindmap_verbatim"]);
const _MINDMAP_BUCKET_ZH: Record<string, string> = { exp_recipe: "判据在期望槽", step_recipe: "判据来自步骤" };
export const WARNING_PANEL_SCHEMA = "ist.ide.warning-panel";
export const CONFIRM_LABEL = "确认签约";
export const REJECT_LABEL = "退回修改";
export const INTENT_JSON_MAX_BYTES = 4 * 1024 * 1024;
const _WARNING_LABELS: Record<string, string> = {
  vacuous_found_in_clean: "干净态已经满足正向断言，判别力灰显",
  config_echo: "当前证据只覆盖配置回显，未直接覆盖运行时行为",
  config_existence_only: "当前断言只证明配置存在，未直接覆盖运行时行为",
  direction_review: "断言方向仍待作者确认",
  poison_confirmed: "引用资产已被机械拒引规则隔离",
  retro_grade_b: "引用资产的回溯认证证据不完整",
  retro_grade_c: "引用资产的回溯认证发现明确风险",
  scope_adaptation: "本行为模式包含范围适配",
  command_not_in_vendor_tree: "脑图中的命令在设备命令树中查无此头",
  command_manual_only: "脑图中的命令仅见于手册声明，命令树未收录",
  command_arg_count_mismatch: "脑图中的命令参数个数与命令树签名不符",
  mindmap_proposal_disclosure: "重组阶段 proposal 提醒（用户面消费）",
  rebind_license_mapping: "经披露许可的重绑映射（原文保留）",
  process_value_concretization: "过程值具体化映射（预期文本未改）",
  rebind_license_unbound: "许可未能于当前床兑现",
};
const _COMMAND_FINDING_CODES = new Set(["command_not_in_vendor_tree", "command_manual_only", "command_arg_count_mismatch"]);
const _EXPECTATION_COVERED_BY = new Set(["set-ratio"]);
const _EXPECTATION_EXEMPTED_PARTS = new Set(["ordering"]);
const _EXPECTATION_EXEMPT_REASONS = new Set([ORDERING_EXEMPT_REASON]);

export class ContractError extends Error {}

function _nonempty(value: any, field: string): string {
  const text = String(value ?? "").trim();
  if (!text) throw new ContractError(`${field} is required`);
  return text;
}

function _publicText(value: any, field: string): string {
  const { scrub_text } = require("../ist_core/security_scrub");
  return _nonempty(scrub_text(value, { scrub_paths: true }), field);
}

function _normalizedClaim(value: any, opts: { item_text: string; source_claim: Record<string, any>; field: string }): Record<string, any> {
  const { item_text, source_claim, field } = opts;
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ContractError(`${field} must be an object`);
  const required = new Set(["schema", "expectation_id", "semantic_key", "original_text", "original_claim_sha256", "source_span", "shape_key", "version_family", "status", "criterion_type", "criterion_label_zh", "rule_id", "rule_identity", "evidence_chain", "author_veto", "mode", "disclosure", "catalog_sha256"]);
  const optional = new Set(["min_requests", "min_requests_formula", "triage", "triage_details", "fixture_authority", "fixture_policy", "algorithm_classes", "anchor_citation_corrected", "supersede_cause", "required_carriers", "authored_step", "authored_step_cause"]);
  const keys = new Set(Object.keys(value));
  if (![...required].every((k) => keys.has(k)) || [...keys].some((k) => !required.has(k) && !optional.has(k))) throw new ContractError(`${field} fields are not closed`);
  const { NORMALIZED_CLAIM_SCHEMA, load_projection } = require("./criterion_normalization");
  const projection = load_projection();
  const typeRows = Object.fromEntries((projection?.["criterion_types"] ?? []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r)).map((r: any) => [String(r["criterion_type"] ?? ""), String(r["label_zh"] ?? "")]));
  const ruleIds = new Set((projection?.["rules"] ?? []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r)).map((r: any) => String(r["rule_id"] ?? "")));
  const staticRules = Object.fromEntries((projection?.["rules"] ?? []).filter((r: any) => r && typeof r === "object" && !Array.isArray(r)).map((r: any) => [String(r["rule_id"] ?? ""), r]));
  const status = String(value["status"] ?? "");
  const criterionType = value["criterion_type"] !== null && value["criterion_type"] !== undefined ? String(value["criterion_type"]) : null;
  const ruleId = value["rule_id"] !== null && value["rule_id"] !== undefined ? String(value["rule_id"]) : null;
  const sourceSpan = value["source_span"];
  const algorithmClasses = value["algorithm_classes"];
  const { load_grammar } = require("./domain_grammar");
  const knownAlgorithmClasses = new Set(Object.keys(load_grammar()?.["algorithm_classes"] ?? {}));
  if (!Array.isArray(algorithmClasses) || algorithmClasses.length !== new Set(algorithmClasses).size || algorithmClasses.some((item: any) => typeof item !== "string" || !knownAlgorithmClasses.has(item))) throw new ContractError(`${field}.algorithm_classes is invalid`);
  if (sourceSpan !== null && sourceSpan !== undefined && (!sourceSpan || typeof sourceSpan !== "object" || Array.isArray(sourceSpan) || typeof sourceSpan["start"] !== "number" || typeof sourceSpan["end"] !== "number" || sourceSpan["start"] < 0 || sourceSpan["end"] <= sourceSpan["start"])) throw new ContractError(`${field}.source_span is invalid`);
  if ("authored_step" in value || "authored_step_cause" in value) {
    const { AUTHORED_STEP_UNKNOWN_CAUSES } = require("./mindmap_contract_projector");
    const authoredStep = value["authored_step"];
    const cause = value["authored_step_cause"];
    if (authoredStep !== null && authoredStep !== undefined && (typeof authoredStep !== "number" || authoredStep < 1)) throw new ContractError(`${field}.authored_step is invalid`);
    if ((cause === null || cause === undefined) !== (authoredStep === null || authoredStep === undefined)) throw new ContractError(`${field}.authored_step_cause is not paired`);
    if (cause !== null && cause !== undefined && !AUTHORED_STEP_UNKNOWN_CAUSES.includes(cause)) throw new ContractError(`${field}.authored_step_cause is outside closed set`);
  }
  if (value["schema"] !== NORMALIZED_CLAIM_SCHEMA || String(value["original_text"] ?? "") !== item_text || String(value["expectation_id"] ?? "") !== String(source_claim?.["expectation_id"] ?? "") || String(value["semantic_key"] ?? "") !== String(source_claim?.["semantic_key"] ?? "") || String(value["original_claim_sha256"] ?? "") !== String(source_claim?.["claim_sha256"] ?? "") || !/^[0-9a-f]{64}$/.test(String(value["shape_key"] ?? "")) || String(value["catalog_sha256"] ?? "") !== String(projection?.["projection_sha256"] ?? "") || !["matched", "unmatched", "manual_recommended", "numeric_tolerance_out_of_range"].includes(status) || !String(value["disclosure"] ?? "").trim()) throw new ContractError(`${field} identity is invalid`);
  if (criterionType !== null && (!(criterionType in typeRows) || String(value["criterion_label_zh"] ?? "") !== typeRows[criterionType])) throw new ContractError(`${field}.criterion_type is invalid`);
  if (criterionType === null && value["criterion_label_zh"] !== null && value["criterion_label_zh"] !== undefined) throw new ContractError(`${field}.criterion_label_zh must be null`);
  if (ruleId !== null) {
    const ruleIdentity = value["rule_identity"];
    if (!ruleIdentity || typeof ruleIdentity !== "object" || Array.isArray(ruleIdentity)) throw new ContractError(`${field}.rule identity is invalid`);
    if (!ruleIds.has(ruleId)) {
      const { load_author_rules, resolve_compile_manual_version } = require("./criterion_author_rules");
      const resolvedManualVersion = resolve_compile_manual_version();
      const authorRule = load_author_rules({ manual_version: resolvedManualVersion || undefined })?.[`${String(value["shape_key"] ?? "")},${resolvedManualVersion}`];
      if (!authorRule || typeof authorRule !== "object" || Array.isArray(authorRule) || String(authorRule["rule_id"] ?? "") !== ruleId || JSON.stringify(authorRule["identity"]) !== JSON.stringify(ruleIdentity)) throw new ContractError(`${field}.rule identity is invalid`);
    }
    if (ruleIdentity["kind"] === "engine_adjudication") {
      const evidenceChain = value["evidence_chain"];
      const authorVeto = value["author_veto"];
      if (!evidenceChain || typeof evidenceChain !== "object" || Array.isArray(evidenceChain) || JSON.stringify(evidenceChain) !== JSON.stringify(ruleIdentity["evidence_chain"]) || !authorVeto || typeof authorVeto !== "object" || Array.isArray(authorVeto) || JSON.stringify(Object.keys(authorVeto).sort()) !== JSON.stringify(["answer", "answer_key", "rule_sha256"]) || !/^[0-9a-f]{64}$/.test(String(authorVeto["answer_key"] ?? "")) || authorVeto["answer"] !== "否决并重裁" || !/^[0-9a-f]{64}$/.test(String(authorVeto["rule_sha256"] ?? ""))) throw new ContractError(`${field}.engine adjudication evidence is invalid`);
    } else if (value["evidence_chain"] !== null && value["evidence_chain"] !== undefined || value["author_veto"] !== null && value["author_veto"] !== undefined) throw new ContractError(`${field}.static rule may not carry engine adjudication fields`);
    const staticRule = staticRules[ruleId];
    if (staticRule && typeof staticRule === "object" && !Array.isArray(staticRule)) {
      const output = staticRule["output"] ?? {};
      for (const extra of ["fixture_authority", "fixture_policy"]) {
        if (JSON.stringify(value[extra]) !== JSON.stringify(output[extra])) {
          if (extra in value || extra in output) throw new ContractError(`${field}.${extra} differs from the generated rule`);
        }
      }
    }
  }
  if (ruleId === null && value["rule_identity"] !== null && value["rule_identity"] !== undefined) throw new ContractError(`${field}.rule_identity must be null`);
  if (status === "matched" && (criterionType === null || ruleId === null)) throw new ContractError(`${field} matched state has no rule/type`);
  if ("required_carriers" in value) {
    const { required_carriers_record_error } = require("./criterion_carriers");
    const carrierError = required_carriers_record_error(value["required_carriers"], value);
    if (carrierError) throw new ContractError(`${field}.required_carriers: ${carrierError}`);
  }
  return { ...value };
}

export function normalize_contract(raw: any, source: string = ""): Record<string, any> {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new ContractError("contract must be an object");
  const contractClass = String(raw["contract_class"] ?? "pattern").trim();
  if (!CONTRACT_CLASSES.has(contractClass)) throw new ContractError(`contract_class must be one of ${[...CONTRACT_CLASSES].sort()}`);
  const isMindmap = contractClass === "mindmap_verbatim";
  const autoid = _nonempty(raw["autoid"] ?? raw["pilot_autoid"], "autoid");
  const title = _publicText(raw["intent_verbatim"] ?? raw["title"], "intent_verbatim");
  const method = raw["verification_method"];
  if (!method || typeof method !== "object" || Array.isArray(method)) throw new ContractError("verification_method must be an object");
  const selectedRule = _publicText(method["selected_rule"] ?? method["proposal"], "verification_method.selected_rule");
  const authority = _publicText(method["authority"], "verification_method.authority");
  let alternatives = method["alternatives"];
  if (!Array.isArray(alternatives) || !alternatives.length) {
    if (isMindmap) {
      alternatives = [];
    } else {
      throw new ContractError("verification_method.alternatives must be a non-empty array");
    }
  }
  const normalizedAlternatives: Record<string, string>[] = [];
  for (let index = 0; index < alternatives.length; index++) {
    const alternative = alternatives[index];
    if (!alternative || typeof alternative !== "object" || Array.isArray(alternative)) throw new ContractError(`verification_method.alternatives[${index}] must be an object`);
    const rule = _publicText(alternative["rule"], `verification_method.alternatives[${index}].rule`);
    if (rule === selectedRule) throw new ContractError(`verification_method.alternatives[${index}].rule duplicates selected_rule`);
    normalizedAlternatives.push({ rule, authority: _publicText(alternative["authority"], `verification_method.alternatives[${index}].authority`), rejection_reason: _publicText(alternative["rejection_reason"], `verification_method.alternatives[${index}].rejection_reason`) });
  }
  const pattern = raw["behavior_pattern"];
  let mindmapGroup: Record<string, any> = {};
  let bucket = "";
  let sourceStatus = "";
  let typedAssertionStatus = "";
  let capability = "";
  let shape = "";
  let authorSteps: Record<string, string>[] = [];
  let authorStepsPresent = false;
  if (isMindmap) {
    if (pattern !== null && pattern !== undefined && (typeof pattern !== "object" || Array.isArray(pattern))) throw new ContractError("behavior_pattern must be an object when given");
    const group = raw["mindmap_group"];
    if (!group || typeof group !== "object" || Array.isArray(group)) throw new ContractError("mindmap_group must be an object");
    const groupPath = group["group_path"];
    if (!Array.isArray(groupPath) || !groupPath.length || !groupPath.every((x: any) => String(x).trim())) throw new ContractError("mindmap_group.group_path must be a non-empty string array");
    mindmapGroup = { group_path: groupPath.map((x: any) => _publicText(x, "mindmap_group.group_path[]")) };
    bucket = _nonempty(raw["bucket"], "bucket");
    if (!(bucket in _MINDMAP_BUCKET_ZH)) throw new ContractError(`bucket must be one of ${Object.keys(_MINDMAP_BUCKET_ZH).sort()}`);
    sourceStatus = String(raw["source_status"] ?? "complete").trim();
    if (sourceStatus !== "complete") throw new ContractError("mindmap contract source_status must be complete before signing");
    typedAssertionStatus = String(raw["typed_assertion_status"] ?? ((raw["expectations"] ?? []).some((item: any) => item && typeof item === "object" && !Array.isArray(item) && (item["author_claim"] !== null && item["author_claim"] !== undefined || item["defect_spec_claim"] !== null && item["defect_spec_claim"] !== undefined)) ? "pending" : "ready")).trim();
    if (!["ready", "pending"].includes(typedAssertionStatus)) throw new ContractError("typed_assertion_status must be ready or pending");
    authorStepsPresent = "author_steps" in raw;
    let rawAuthorSteps = raw["author_steps"];
    if (rawAuthorSteps === null || rawAuthorSteps === undefined) rawAuthorSteps = [];
    if (!Array.isArray(rawAuthorSteps)) throw new ContractError("author_steps must be an array");
    authorSteps = [];
    for (let index = 0; index < rawAuthorSteps.length; index++) {
      const item = rawAuthorSteps[index];
      if (!item || typeof item !== "object" || Array.isArray(item) || JSON.stringify(Object.keys(item).sort()) !== JSON.stringify(["n", "origin", "text"])) throw new ContractError(`author_steps[${index}] fields must be exactly n/text/origin`);
      authorSteps.push({ n: _nonempty(item["n"], `author_steps[${index}].n`), text: _publicText(item["text"], `author_steps[${index}].text`), origin: _nonempty(item["origin"], `author_steps[${index}].origin`) });
    }
    capability = String(pattern?.["capability_family"] ?? "").trim();
    shape = String(pattern?.["verification_shape"] ?? "").trim();
  } else {
    authorStepsPresent = false;
    authorSteps = [];
    if (!pattern || typeof pattern !== "object" || Array.isArray(pattern)) throw new ContractError("behavior_pattern must be an object");
    capability = _nonempty(pattern["capability_family"], "behavior_pattern.capability_family");
    shape = _nonempty(pattern["verification_shape"], "behavior_pattern.verification_shape");
  }
  const commandFindings: Record<string, string>[] = [];
  for (let i = 0; i < (raw["command_findings"] ?? []).length; i++) {
    const cf = raw["command_findings"][i];
    if (!cf || typeof cf !== "object" || Array.isArray(cf)) throw new ContractError(`command_findings[${i}] must be an object`);
    const code = String(cf["code"] ?? "").trim();
    if (!_COMMAND_FINDING_CODES.has(code)) throw new ContractError(`command_findings[${i}].code must be one of ${[..._COMMAND_FINDING_CODES].sort()}`);
    commandFindings.push({ command: _publicText(cf["command"], `command_findings[${i}].command`), code, note: _publicText(cf["note"], `command_findings[${i}].note`) });
  }
  const selectedRuleId = String(method["selected_rule_id"] ?? "").trim();
  let ruleSnapshotFields: Record<string, string> = {};
  if (selectedRuleId && isMindmap) throw new ContractError("mindmap_verbatim contracts carry the author's verbatim method; selected_rule_id (rule selection) does not apply");
  if (selectedRuleId) {
    const { RuleRegistryUnavailable, applicability_error, rule_snapshot } = require("./rule_registry");
    try {
      const registryError = applicability_error(selectedRuleId, capability, shape);
      if (!registryError) ruleSnapshotFields = rule_snapshot(selectedRuleId, capability);
    } catch (exc: any) {
      if (exc instanceof RuleRegistryUnavailable) throw new ContractError(String(exc));
      throw exc;
    }
  }
  const expectations = raw["expectations"];
  if (!Array.isArray(expectations) || !expectations.length) throw new ContractError("expectations must be a non-empty array");
  const normalizedExpectations: Record<string, any>[] = [];
  let pendingClaims = 0;
  for (let i = 0; i < expectations.length; i++) {
    const item = expectations[i];
    if (!item || typeof item !== "object" || Array.isArray(item)) throw new ContractError(`expectations[${i}] must be an object`);
    const normalized: Record<string, any> = { text: _publicText(item["text"], `expectations[${i}].text`), text_anchor: _publicText(item["text_anchor"], `expectations[${i}].text_anchor`), value_grounding: _publicText(item["value_grounding"], `expectations[${i}].value_grounding`) };
    if (isMindmap) {
      const assertion = item["assertion"];
      const authorClaim = item["author_claim"];
      const defectSpecClaim = item["defect_spec_claim"];
      const alternativesCount = [assertion, authorClaim, defectSpecClaim].filter((c) => c && typeof c === "object" && !Array.isArray(c)).length;
      if (alternativesCount !== 1) throw new ContractError(`expectations[${i}] requires exactly one assertion, author_claim, or defect_spec_claim`);
      if (assertion && typeof assertion === "object" && !Array.isArray(assertion)) {
        const sourceBinding = assertion["source"];
        if (!sourceBinding || typeof sourceBinding !== "object" || Array.isArray(sourceBinding)) throw new ContractError(`expectations[${i}].assertion.source must be an object`);
        const sourceKind = _nonempty(sourceBinding["kind"], `expectations[${i}].assertion.source.kind`);
        if (!["intent", "spec", "defect_spec", "manual"].includes(sourceKind)) throw new ContractError(`expectations[${i}].assertion.source.kind is not authoritative`);
        const sourceLocator = _nonempty(sourceBinding["locator"], `expectations[${i}].assertion.source.locator`);
        const normalizedSource: Record<string, any> = { kind: sourceKind, locator: sourceLocator };
        if (sourceKind === "defect_spec") {
          if (JSON.stringify(Object.keys(sourceBinding).sort()) !== JSON.stringify(["kind", "locator", "receipt"])) throw new ContractError(`expectations[${i}].assertion.source DefectSpec fields are not closed`);
          const resolverReceipt = sourceBinding["receipt"];
          const [resolved, receiptError] = validate_expected_with_source({ expected: String(assertion["value"] ?? ""), source: { kind: "defect_spec", ref: sourceLocator, receipt: resolverReceipt } });
          if (resolved === null || resolved === undefined) throw new ContractError(`expectations[${i}].assertion.source DefectSpec receipt is invalid: ${receiptError}`);
          normalizedSource["receipt"] = { ...resolverReceipt };
        }
        normalized["assertion"] = { expectation_id: _nonempty(assertion["expectation_id"], `expectations[${i}].assertion.expectation_id`), semantic_key: _nonempty(assertion["semantic_key"] ?? `${autoid}:step:${i + 1}`, `expectations[${i}].assertion.semantic_key`), operator: _nonempty(assertion["operator"], `expectations[${i}].assertion.operator`), value: String(assertion["value"] ?? ""), origin: String(assertion["origin"] ?? ""), source: normalizedSource };
        if (!normalized["assertion"]["value"]) throw new ContractError(`expectations[${i}].assertion.value is required`);
      } else if (authorClaim && typeof authorClaim === "object" && !Array.isArray(authorClaim)) {
        const claimHash = String(authorClaim["claim_sha256"] ?? "");
        const body = Object.fromEntries(Object.entries(authorClaim).filter(([k]) => k !== "claim_sha256"));
        const required = new Set(["schema", "kind", "autoid", "expectation_id", "semantic_key", "origin", "source_text", "source_sha256"]);
        if (JSON.stringify(Object.keys(body).sort()) !== JSON.stringify([...required].sort()) || JSON.stringify(Object.keys(authorClaim).sort()) !== JSON.stringify([...required, "claim_sha256"].sort())) throw new ContractError(`expectations[${i}].author_claim fields are not closed`);
        if (!_acceptsSchema(body["schema"], "ist.author-claim") || body["kind"] !== "Author" || body["autoid"] !== autoid || body["source_text"] !== item["text"] || !String(body["origin"] ?? "").trim() || !/^[0-9a-f]{64}$/.test(String(body["source_sha256"] ?? "")) || !/^[0-9a-f]{64}$/.test(claimHash) || _canonicalHash(body) !== claimHash) throw new ContractError(`expectations[${i}].author_claim identity is invalid`);
        normalized["author_claim"] = { ...authorClaim };
        pendingClaims += 1;
      } else if (defectSpecClaim && typeof defectSpecClaim === "object" && !Array.isArray(defectSpecClaim)) {
        const claimHash = String(defectSpecClaim["claim_sha256"] ?? "");
        const body = Object.fromEntries(Object.entries(defectSpecClaim).filter(([k]) => k !== "claim_sha256"));
        const required = new Set(["schema", "kind", "autoid", "expectation_id", "semantic_key", "origin", "source_text", "locator", "resolver_receipt", "resolver_receipt_sha256"]);
        const resolverReceipt = body["resolver_receipt"];
        const resolverSha = String(body["resolver_receipt_sha256"] ?? "");
        if (JSON.stringify(Object.keys(body).sort()) !== JSON.stringify([...required].sort()) || JSON.stringify(Object.keys(defectSpecClaim).sort()) !== JSON.stringify([...required, "claim_sha256"].sort())) throw new ContractError(`expectations[${i}].defect_spec_claim fields are not closed`);
        const [resolved, receiptError] = validate_expected_with_source({ expected: String(body["source_text"] ?? ""), source: { kind: "defect_spec", ref: String(body["locator"] ?? ""), receipt: resolverReceipt } });
        if (!_acceptsSchema(body["schema"], "ist.defect-spec-claim") || body["kind"] !== "DefectSpec" || body["autoid"] !== autoid || body["source_text"] !== item["text"] || !String(body["origin"] ?? "").trim() || !String(body["expectation_id"] ?? "").trim() || !String(body["semantic_key"] ?? "").trim() || !/^[0-9a-f]{64}$/.test(resolverSha) || !resolverReceipt || typeof resolverReceipt !== "object" || Array.isArray(resolverReceipt) || _canonicalHash(resolverReceipt) !== resolverSha || !/^[0-9a-f]{64}$/.test(claimHash) || _canonicalHash(body) !== claimHash || resolved === null || resolved === undefined) throw new ContractError(`expectations[${i}].defect_spec_claim identity is invalid${receiptError ? `: ${receiptError}` : ""}`);
        normalized["defect_spec_claim"] = { ...defectSpecClaim };
        pendingClaims += 1;
      }
      if ("normalized_claim" in item) {
        const sourceClaim = normalized["assertion"] ?? normalized["author_claim"] ?? normalized["defect_spec_claim"] ?? {};
        normalized["normalized_claim"] = _normalizedClaim(item["normalized_claim"], { item_text: String(item["text"] ?? ""), source_claim: sourceClaim, field: `expectations[${i}].normalized_claim` });
        if ("authored_step" in normalized["normalized_claim"]) {
          const { with_authored_step_anchor } = require("./mindmap_contract_projector");
          if (with_authored_step_anchor(normalized["text_anchor"], normalized["normalized_claim"]["authored_step"]) !== normalized["text_anchor"]) throw new ContractError(`expectations[${i}].text_anchor author step disagrees with normalized_claim.authored_step`);
        }
      }
      if ("criterion_requirements_ref" in item) {
        const { requirement_reference_valid } = require("./criterion_carriers");
        const reference = item["criterion_requirements_ref"];
        if (!requirement_reference_valid(reference)) throw new ContractError(`expectations[${i}].criterion_requirements_ref is invalid`);
        normalized["criterion_requirements_ref"] = { ...reference };
      }
      const required = normalized?.["normalized_claim"]?.["required_carriers"];
      if (required && typeof required === "object" && !Array.isArray(required) && required["status"] === "verified") {
        const identity = required["source_identity"];
        const expectedReference = { kind: identity["kind"], ref: identity["ref"], sha256: identity["source_sha256"] };
        if (JSON.stringify(normalized["criterion_requirements_ref"]) !== JSON.stringify(expectedReference)) throw new ContractError(`expectations[${i}].required_carriers source reference is missing or mismatched`);
      }
    }
    const stateFields = ["covered_by", "exempted_part", "reason"];
    const present = stateFields.filter((f) => item[f] !== null && item[f] !== undefined);
    if (present.length && present.length !== stateFields.length) throw new ContractError(`expectations[${i}] coverage state requires exactly covered_by/exempted_part/reason`);
    if (present.length) {
      const coveredBy = _nonempty(item["covered_by"], `expectations[${i}].covered_by`);
      const exemptedPart = _nonempty(item["exempted_part"], `expectations[${i}].exempted_part`);
      const reason = _nonempty(item["reason"], `expectations[${i}].reason`);
      if (!_EXPECTATION_COVERED_BY.has(coveredBy)) throw new ContractError(`expectations[${i}].covered_by must be one of ${[..._EXPECTATION_COVERED_BY].sort()}`);
      if (!_EXPECTATION_EXEMPTED_PARTS.has(exemptedPart)) throw new ContractError(`expectations[${i}].exempted_part must be one of ${[..._EXPECTATION_EXEMPTED_PARTS].sort()}`);
      if (!_EXPECTATION_EXEMPT_REASONS.has(reason)) throw new ContractError(`expectations[${i}].reason must be one of ${[..._EXPECTATION_EXEMPT_REASONS].sort()}`);
      Object.assign(normalized, { covered_by: coveredBy, exempted_part: exemptedPart, reason });
    }
    normalizedExpectations.push(normalized);
  }
  if (isMindmap) {
    const expectationIds = normalizedExpectations.map((item: any) => String((item["assertion"] ?? item["author_claim"] ?? item["defect_spec_claim"] ?? {})["expectation_id"] ?? ""));
    if (new Set(expectationIds).size !== expectationIds.length) throw new ContractError("expectation assertion IDs must be unique");
    if (typedAssertionStatus === "ready" && pendingClaims) throw new ContractError("ready contract cannot contain pending source claims");
    if (typedAssertionStatus === "pending" && !pendingClaims) throw new ContractError("pending contract must contain a source claim");
  }
  return {
    schema_version: SCHEMA_VERSION,
    contract_class: contractClass,
    autoid,
    source_autoid: String(raw["src_autoid"] ?? "").trim(),
    source,
    intent_verbatim: title,
    intent_anchor: _publicText(raw["intent_anchor"], "intent_anchor"),
    ...((!isMindmap || (capability && shape)) ? { behavior_pattern: { capability_family: capability, verification_shape: shape } } : {}),
    ...(isMindmap ? { mindmap_group: mindmapGroup, bucket, source_status: sourceStatus, typed_assertion_status: typedAssertionStatus, ...(authorStepsPresent ? { author_steps: authorSteps } : {}) } : {}),
    ...(commandFindings.length ? { command_findings: commandFindings } : {}),
    verification_method: { selected_rule: selectedRule, selected_rule_id: selectedRuleId, ...(Object.keys(ruleSnapshotFields).length ? { selected_rule_snapshot: ruleSnapshotFields } : {}), authority, alternatives: normalizedAlternatives },
    expectations: normalizedExpectations,
    scope_adaptations: (raw["scope_adaptations"] ?? []).filter((x: any) => String(x).trim()).map((x: any) => _publicText(x, "scope_adaptations[]")),
  };
}

export function cluster_key(contract: Record<string, any>): string {
  if (contract?.["contract_class"] === "mindmap_verbatim") {
    const group = contract?.["mindmap_group"] ?? {};
    return "mm::" + (group?.["group_path"] ?? []).join("/");
  }
  const pattern = contract["behavior_pattern"];
  return `${pattern["capability_family"]}::${pattern["verification_shape"]}`;
}

function _canonicalHash(payload: Record<string, any>): string {
  return crypto.createHash("sha256").update(JSON.stringify(payload, Object.keys(payload).sort(), 0)).digest("hex");
}

function _signedCardPayload(card: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const key of ["schema_version", "cluster_key", "contract_class", "mindmap_group", "behavior_pattern", "cases", "warnings"]) {
    if (key in card) out[key] = card[key];
  }
  return out;
}

function _authorCardText(value: any, masked: boolean): string {
  const text = String(value);
  return masked ? "〇".repeat(text.length) : text;
}

function _authorCardAnchor(value: any, authoredText: string, masked: boolean): string {
  const text = String(value);
  if (!masked || text.length > 65536) return text;
  let anchor: any;
  try {
    validate_json_budget(text, { errorType: Error, message: "anchor exceeds JSON budget" });
    anchor = JSON.parse(text);
  } catch {
    try {
      anchor = JSON.parse(text);
    } catch {
      return text;
    }
  }
  if (anchor && typeof anchor === "object" && !Array.isArray(anchor) && anchor["quote"] === authoredText) {
    return String({ ...anchor, quote: _authorCardText(authoredText, true) });
  }
  return text;
}

function _uniqueAnchorKeys(pairs: [string, any][]): Record<string, any> {
  const result: Record<string, any> = {};
  for (const [key, value] of pairs) {
    if (key in result) throw new Error("duplicate anchor key");
    result[key] = value;
  }
  return result;
}

function _renderCard(payload: Record<string, any>, digest: string, opts: { mask_author_text?: boolean } = {}): string {
  if (payload?.["contract_class"] === "mindmap_verbatim") return _renderCardV4Mindmap(payload, digest, opts);
  if (Number(payload?.["schema_version"] ?? 0) <= 2) return _renderCardV2(payload, digest);
  return _renderCardV3(payload, digest, opts);
}

function _renderCardV4Mindmap(payload: Record<string, any>, digest: string, opts: { mask_author_text?: boolean } = {}): string {
  const group = payload?.["mindmap_group"] ?? {};
  const groupPath = (group?.["group_path"] ?? []).map((x: any) => String(x));
  const cases = payload["cases"];
  const warnings = payload["warnings"];
  const lines = [`用例组：${groupPath.length ? _authorCardText(groupPath[groupPath.length - 1], opts.mask_author_text ?? false) : "（未分组）"}　　适用 ${cases.length} 条`, "", `引擎把这 ${cases.length} 条归成同一个行为模式，按同一套契约处理：`];
  const rewritten: string[] = [];
  const chosen: string[] = [];
  for (const kase of cases) {
    const method = kase["verification_method"];
    const tail = kase["autoid"].slice(-6);
    lines.push(`  ${tail}  ${_authorCardText(kase["intent_verbatim"], opts.mask_author_text ?? false)}`);
    if (method?.["alternatives"]?.length) {
      chosen.push(`  ${tail}  选了「${method["selected_rule"]}」，未选：` + method["alternatives"].map((alt: any) => `「${alt["rule"]}」（${alt["rejection_reason"]}）`).join("、"));
    }
    if (String(method?.["selected_rule"] ?? "") !== String(kase?.["intent_verbatim"] ?? "") && method?.["machine_rewritten"]) {
      rewritten.push(`  ${tail}  ${method["selected_rule"]}`);
    }
  }
  if (chosen.length) lines.push(...["", "引擎在多个验证方法里做了选择：", ...chosen]);
  if (rewritten.length) lines.push(...["", "注意：引擎改写了你的原文：", ...rewritten]);
  if (!chosen.length && !rewritten.length) lines.push(...["", "你的原文一个字没改，引擎也没有替你做任何选择。"]);
  const criterionLines: string[] = [];
  const { criterion_verbal_zh } = require("./mindmap_contract_projector");
  for (const kase of cases) {
    const tail = String(kase?.["autoid"] ?? "").slice(-6);
    for (const expectation of kase?.["expectations"] ?? []) {
      if (!expectation || typeof expectation !== "object" || Array.isArray(expectation)) continue;
      const normalizedClaim = expectation["normalized_claim"];
      if (!normalizedClaim || typeof normalizedClaim !== "object" || Array.isArray(normalizedClaim)) continue;
      const label = criterion_verbal_zh(String(normalizedClaim["criterion_label_zh"] ?? normalizedClaim["criterion_type"] ?? "")) || "还没定";
      const suffix = normalizedClaim["status"] === "matched" ? "" : "（类型还没定下来）";
      criterionLines.push(`  ${tail}  原文「${_authorCardText(expectation["text"], opts.mask_author_text ?? false)}」；归类为「${label}」${suffix}`);
    }
  }
  if (criterionLines.length) lines.push(...["", "归类预期（人工脑图预期原文不动）：", ...criterionLines]);
  const scopeTotal = cases.reduce((sum: number, c: any) => sum + (c?.["scope_adaptations"]?.length ?? 0), 0);
  if (scopeTotal) lines.push(`配置组合共 ${scopeTotal} 种，逐条各跑一遍。`);
  const filteredWarnings = (warnings ?? []).filter((item: any) => String(item?.["code"] ?? "") !== "scope_adaptation");
  lines.push("");
  lines.push("警告面板：");
  if (filteredWarnings.length) {
    lines.push(...filteredWarnings.map((item: any) => `- 尾号${String(item["autoid"]).slice(-6)}：${item["message"]}（${item["code"]}）`));
  } else {
    lines.push("- 当前没有软提示");
  }
  lines.push(`签约哈希：${digest}`);
  return lines.join("\n");
}

function _renderCardV3(payload: Record<string, any>, digest: string, opts: { mask_author_text?: boolean } = {}): string {
  const pattern = payload["behavior_pattern"];
  const cases = payload["cases"];
  const warnings = payload["warnings"];
  const tails = cases.map((c: any) => `尾号${c["autoid"].slice(-6)}`).join("、");
  const lines = [`行为模式：${pattern["capability_family"]} × ${pattern["verification_shape"]}`, `适用用例：${cases.length} 案（${tails}）`];
  for (const kase of cases) {
    const method = kase["verification_method"];
    const ruleId = String(method?.["selected_rule_id"] ?? "");
    let ruleLine: string;
    if (ruleId) {
      const snapshot = method?.["selected_rule_snapshot"] ?? {};
      ruleLine = snapshot ? `已选规则“${snapshot["name_zh"] ?? method["selected_rule"]}”（注册规则 ${ruleId}·${snapshot["status"] ?? ""}：${snapshot["zh_template"] ?? ""}；出处：${method["authority"]}）` : `已选规则“${method["selected_rule"]}”（未认证规则——不在注册表闭集内；出处：${method["authority"]}）`;
    } else {
      ruleLine = `已选规则“${method["selected_rule"]}”（未认证规则——不在注册表闭集内；出处：${method["authority"]}）`;
    }
    const expects = kase["expectations"].map((item: any) => `${_authorCardText(item["text"], opts.mask_author_text ?? false)}（出处：${_authorCardAnchor(item["text_anchor"], item["text"], opts.mask_author_text ?? false)}；绑定：${item["value_grounding"]}${item["covered_by"] ? `；covered_by=${item["covered_by"]}；exempted_part=${item["exempted_part"]}；reason=${item["reason"]}` : ""}）`).join("；");
    const declared = kase["expectations"].filter((item: any) => item?.["covered_by"]);
    const flipLine = declared.length ? `${declared.length} 条期望按声明部分豁免（理由码在期望条目内），其余期望的翻转凭据在上机时由变异测试机械铸造` : "每条期望的判别力凭据（翻转或带码豁免）在上机时由变异测试机械铸造——交付前缺凭据不得出厂";
    lines.push(`- 尾号${kase["autoid"].slice(-6)}`);
    lines.push(`  你的要求（脑图原文）：“${_authorCardText(kase["intent_verbatim"], opts.mask_author_text ?? false)}”`);
    lines.push(`  机器打算这样验证：${ruleLine}`);
    for (const alternative of method["alternatives"] ?? []) {
      lines.push(`    备选规则“${alternative["rule"]}”（出处：${alternative["authority"]}；未选原因：${alternative["rejection_reason"]}）`);
    }
    lines.push(`  期望值的来历：${expects}`);
    lines.push(`  凭什么不是白查：${flipLine}`);
    if (kase["scope_adaptations"]?.length) lines.push("  范围适配：" + kase["scope_adaptations"].join("；"));
  }
  lines.push("警告面板：");
  if (warnings?.length) {
    lines.push(...warnings.map((item: any) => `- 尾号${String(item["autoid"]).slice(-6)}：${item["message"]}（${item["code"]}）`));
  } else {
    lines.push("- 当前没有结构化软提示");
  }
  lines.push(`签约哈希：${digest}`);
  return lines.join("\n");
}

function _renderCardV2(payload: Record<string, any>, digest: string): string {
  const pattern = payload["behavior_pattern"];
  const cases = payload["cases"];
  const warnings = payload["warnings"];
  const lines = [`行为模式：${pattern["capability_family"]} × ${pattern["verification_shape"]}`, `适用用例：${cases.length} 案（${cases.map((c: any) => c["autoid"]).join("、")}）`];
  for (const kase of cases) {
    const method = kase["verification_method"];
    const expects = kase["expectations"].map((item: any) => `${item["text"]}（出处：${item["text_anchor"]}；绑定：${item["value_grounding"]}${item["covered_by"] ? `；covered_by=${item["covered_by"]}；exempted_part=${item["exempted_part"]}；reason=${item["reason"]}` : ""}）`).join("；");
    lines.push(`- ${kase["autoid"]}：意图“${kase["intent_verbatim"]}”；已选规则“${method["selected_rule"]}”（出处：${method["authority"]}）；期望：${expects}`);
    for (const alternative of method["alternatives"] ?? []) {
      lines.push(`  备选规则“${alternative["rule"]}”（出处：${alternative["authority"]}；未选原因：${alternative["rejection_reason"]}）`);
    }
    if (kase["scope_adaptations"]?.length) lines.push("  范围适配：" + kase["scope_adaptations"].join("；"));
  }
  lines.push("警告面板：");
  if (warnings?.length) {
    lines.push(...warnings.map((item: any) => `- ${item["autoid"]}：${item["message"]}（${item["code"]}）`));
  } else {
    lines.push("- 当前没有结构化软提示");
  }
  lines.push(`签约哈希：${digest}`);
  return lines.join("\n");
}

function _recordForSource(sourceAutoid: string, packageProjection: Record<string, any>): Record<string, any> {
  if (!sourceAutoid) return {};
  const records = packageProjection?.["records"];
  if (!records || typeof records !== "object" || Array.isArray(records)) return {};
  const direct = records[`verified_${sourceAutoid}.xlsx`];
  if (direct && typeof direct === "object" && !Array.isArray(direct)) return direct;
  for (const record of Object.values(records) as Record<string, any>[]) {
    if (record && typeof record === "object" && !Array.isArray(record) && ((record["autoids"] ?? []) as any[]).map(String).includes(sourceAutoid)) return record;
  }
  return {};
}

export function build_warning_panel(contracts: Record<string, any>[], packageProjection: Record<string, any> | null = null, opts: { extra_items?: Record<string, string>[] } = {}): Record<string, any> {
  const projection = packageProjection && typeof packageProjection === "object" && !Array.isArray(packageProjection) ? packageProjection : {};
  const items: Record<string, string>[] = [];
  const seen = new Set<string>();
  for (const extra of opts.extra_items ?? []) {
    if (!extra || typeof extra !== "object" || Array.isArray(extra)) continue;
    const item = [String(extra?.["autoid"] ?? ""), String(extra?.["code"] ?? ""), String(extra?.["message"] ?? "")];
    if (item.every((v) => v) && !seen.has(item.join("|"))) {
      seen.add(item.join("|"));
      items.push({ autoid: item[0], code: item[1], message: item[2] });
    }
  }
  for (const contract of [...contracts].sort((a, b) => a["autoid"].localeCompare(b["autoid"]))) {
    const autoid = contract["autoid"];
    const adaptations = (contract?.["scope_adaptations"] ?? []).map(String);
    if (adaptations.length) {
      const item = `${autoid}|scope_adaptation|${adaptations.length}`;
      if (!seen.has(item)) {
        seen.add(item);
        items.push({ autoid, code: "scope_adaptation", message: `${adaptations.length} 种配置组合，需要保证设计完整` });
      }
    }
    for (const cf of contract?.["command_findings"] ?? []) {
      const code = String(cf?.["code"] ?? "");
      if (!(code in _WARNING_LABELS)) continue;
      const message = `${_WARNING_LABELS[code]}：${cf?.["command"]}——${cf?.["note"]}`;
      const item = `${autoid}|${code}|${message}`;
      if (!seen.has(item)) {
        seen.add(item);
        items.push({ autoid, code, message });
      }
    }
    const record = _recordForSource(String(contract?.["source_autoid"] ?? ""), projection);
    const codes = [...(record?.["flags"] ?? []), ...(record?.["lint"]?.["advisories"] ?? [])].map(String).filter((code) => code in _WARNING_LABELS);
    for (const code of [...new Set(codes)].sort()) {
      const item = `${autoid}|${code}|${_WARNING_LABELS[code]}`;
      if (!seen.has(item)) {
        seen.add(item);
        items.push({ autoid, code, message: _WARNING_LABELS[code] });
      }
    }
  }
  const signed = { schema: WARNING_PANEL_SCHEMA, items };
  const lines = ["警告面板"];
  if (!items.length) {
    lines.push("- 当前没有软提示");
  } else {
    lines.push(...items.map((item) => `- ${item["autoid"]}：${item["message"]}（${item["code"]}）`));
  }
  return { ...signed, panel_hash: _canonicalHash(signed), rendered_zh: lines.join("\n") };
}

export function build_validation_cards(contracts: Record<string, any>[], opts: { warning_panel?: Record<string, any> | null } = {}): Record<string, any>[] {
  void opts.warning_panel;
  const groups: Record<string, Record<string, any>[]> = {};
  for (const contract of contracts) {
    const key = cluster_key(contract);
    if (!groups[key]) groups[key] = [];
    groups[key].push(contract);
  }
  const cards: Record<string, any>[] = [];
  for (const key of Object.keys(groups).sort()) {
    const members = groups[key].sort((a, b) => a["autoid"].localeCompare(b["autoid"]));
    const isMindmap = members[0]?.["contract_class"] === "mindmap_verbatim";
    const cases = members.map((member) => ({
      autoid: member["autoid"],
      source_autoid: member?.["source_autoid"] ?? "",
      intent_verbatim: member["intent_verbatim"],
      intent_anchor: member["intent_anchor"],
      verification_method: member["verification_method"],
      expectations: member["expectations"],
      scope_adaptations: member["scope_adaptations"],
      ...(member?.["bucket"] ? { bucket: member["bucket"] } : {}),
      ...(isMindmap ? { source_status: member["source_status"], typed_assertion_status: member["typed_assertion_status"] } : {}),
    }));
    const signedPayload = { schema_version: SCHEMA_VERSION, cluster_key: key, ...(isMindmap ? { contract_class: "mindmap_verbatim", mindmap_group: members[0]["mindmap_group"] } : { behavior_pattern: members[0]["behavior_pattern"] }), cases, warnings: [] };
    const digest = _canonicalHash(signedPayload);
    const rendered = _renderCard(signedPayload, digest);
    const { card_lint_findings } = require("./card_lint");
    const findings = card_lint_findings(rendered, { internal_text: _renderCard(signedPayload, digest, { mask_author_text: true }) });
    const blocking = findings.filter((f: any) => f["code"] !== "card_shape_warn");
    if (blocking.length) {
      const detail = blocking.slice(0, 5).map((f: any) => `${f["code"]}:${String(f["token"]).slice(0, 40)} (${f["hint"]})`).join("; ");
      throw new ContractError(`card face for cluster ${key} carries internal jargon and was refused: ${detail}`);
    }
    cards.push({ ...signedPayload, card_hash: digest, rendered_zh: rendered, lint_advisories: findings });
  }
  return cards;
}

export function load_contract_cards(contractsDir: string, packageProjection: Record<string, any> | null = null, opts: { extra_warning_items?: Record<string, string>[] } = {}): [Record<string, any>[], Record<string, any>, string[]] {
  const contracts: Record<string, any>[] = [];
  const errors: string[] = [];
  let directoryFd: number | null = null;
  try {
    directoryFd = open_directory_nofollow(contractsDir, { errorType: ContractError, invalid_message: "contracts directory path is invalid", unavailable_message: "contracts directory is unavailable" }) as unknown as number;
    const names = fs.readdirSync(directoryFd as any).filter((name) => name.endsWith(".json") && path.basename(name) === name).sort();
    for (const name of names) {
      try {
        const encoded = read_regular_at_nofollow(directoryFd as any, name, { errorType: ContractError, open_message: "contract is unavailable", bounds_message: "contract exceeds its sealed size boundary", changed_message: "contract changed while being read", max_bytes: 4 * 1024 * 1024, min_bytes: 1 }) as Buffer;
        validate_json_budget(encoded, { errorType: ContractError, message: "contract exceeds the JSON structure budget", maxTokens: 100000 });
        const raw = JSON.parse(encoded.toString("utf8"));
        contracts.push(normalize_contract(raw, name));
      } catch (exc: any) {
        errors.push(`${name}: ${exc}`);
      }
    }
  } catch (exc: any) {
    errors.push(`contracts/: ${exc}`);
  } finally {
    if (directoryFd !== null) fs.closeSync(directoryFd);
  }
  const warningPanel = build_warning_panel(contracts, packageProjection, { extra_items: opts.extra_warning_items });
  const cards = contracts.length ? build_validation_cards(contracts) : [];
  return [cards, warningPanel, errors];
}

export function load_signatures(filePath: string): Record<string, Record<string, any>> {
  try {
    const encoded = read_regular_nofollow(filePath, { errorType: ContractError, invalid_message: "signature path is invalid", directory_message: "signature directory is unavailable", open_message: "signature file is unavailable", bounds_message: "signature file exceeds its sealed size boundary", changed_message: "signature file changed while being read", max_bytes: 4 * 1024 * 1024, min_bytes: 1 }) as Buffer;
    validate_json_budget(encoded, { errorType: ContractError, message: "signature file exceeds the JSON structure budget", maxTokens: 100000 });
    const payload = JSON.parse(encoded.toString("utf8"));
    const signatures = payload && typeof payload === "object" && !Array.isArray(payload) ? payload["signatures"] : null;
    return signatures && typeof signatures === "object" && !Array.isArray(signatures) ? signatures : {};
  } catch {
    return {};
  }
}

export function signature_valid(card: Record<string, any>, signature: Record<string, any> | null): boolean {
  if (!signature || typeof signature !== "object" || Array.isArray(signature)) return false;
  try {
    const signedPayload = _signedCardPayload(card);
    const digest = _canonicalHash(signedPayload);
    const canonicalRender = _renderCard(signedPayload, digest);
    return card?.["card_hash"] === digest && card?.["rendered_zh"] === canonicalRender && signature?.["decision"] === CONFIRM_LABEL && signature?.["card_hash"] === digest && JSON.stringify(signature?.["case_autoids"]) === JSON.stringify((card?.["cases"] ?? []).map((c: any) => c["autoid"]));
  } catch {
    return false;
  }
}

export function sign_card(card: Record<string, any>, decision: string): Record<string, any> {
  if (decision !== CONFIRM_LABEL) throw new ContractError("only an explicit confirm decision can sign a contract card");
  let signedPayload: Record<string, any>;
  let digest: string;
  let canonicalRender: string;
  try {
    signedPayload = _signedCardPayload(card);
    digest = _canonicalHash(signedPayload);
    canonicalRender = _renderCard(signedPayload, digest);
  } catch (exc) {
    throw new ContractError("card payload is incomplete");
  }
  if (card?.["card_hash"] !== digest || card?.["rendered_zh"] !== canonicalRender) throw new ContractError("card payload or rendered text does not match card_hash");
  if (Number(signedPayload?.["schema_version"] ?? 0) >= 3) {
    const { card_lint_findings } = require("./card_lint");
    const blocking = card_lint_findings(canonicalRender, { internal_text: _renderCard(signedPayload, digest, { mask_author_text: true }) }).filter((f: any) => f["code"] !== "card_shape_warn");
    if (blocking.length) {
      const detail = blocking.slice(0, 5).map((f: any) => `${f["code"]}:${String(f["token"]).slice(0, 40)}`).join("; ");
      throw new ContractError(`card face carries internal jargon and cannot be signed: ${detail}`);
    }
  }
  return { cluster_key: card["cluster_key"], card_hash: digest, case_autoids: (card["cases"] ?? []).map((c: any) => c["autoid"]), decision: CONFIRM_LABEL, signed_by: "user", signed_at: Date.now() / 1000 };
}

export function encode_json_atomic(payload: Record<string, any>): Buffer {
  return Buffer.from(JSON.stringify(payload, null, 2) + "\n", "utf8");
}

export function write_json_atomic(filePath: string, payload: Record<string, any>): string {
  const encoded = encode_json_atomic(payload);
  atomic_write_bytes_nofollow(filePath, encoded, { errorType: ContractError, invalid_message: "JSON output path is invalid", unavailable_message: "JSON output directory is unavailable" });
  return sha256_bytes(encoded);
}

export function read_intent_json(filePath: string, opts: { trusted_root?: string } = {}): [Record<string, any>, Buffer] {
  let encoded: Buffer;
  let payload: any;
  try {
    encoded = read_regular_nofollow(filePath, { trusted_root: opts.trusted_root, errorType: ContractError, invalid_message: "intent JSON path is invalid", directory_message: "intent JSON directory is unavailable", open_message: "intent JSON is unavailable", bounds_message: "intent JSON exceeds its sealed size boundary", changed_message: "intent JSON changed while being read", max_bytes: INTENT_JSON_MAX_BYTES, min_bytes: 1, require_current_uid: true }) as Buffer;
    validate_json_budget(encoded, { errorType: ContractError, message: "intent JSON exceeds its structure budget" });
    payload = JSON.parse(encoded.toString("utf8"));
  } catch (exc: any) {
    if (exc instanceof ContractError) throw exc;
    throw new ContractError("intent JSON is not valid JSON");
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new ContractError("intent JSON must be an object");
  return [payload, encoded];
}

export function write_intent_json_atomic(filePath: string, payload: Record<string, any>): string {
  let encoded: Buffer;
  try {
    encoded = Buffer.from(JSON.stringify(payload, null, 2) + "\n", "utf8");
  } catch {
    throw new ContractError("intent JSON cannot be encoded");
  }
  if (encoded.length > INTENT_JSON_MAX_BYTES) throw new ContractError("intent JSON exceeds its sealed size boundary");
  validate_json_budget(encoded, { errorType: ContractError, message: "intent JSON exceeds its structure budget" });
  atomic_write_bytes_nofollow(filePath, encoded, { errorType: ContractError, invalid_message: "intent JSON output path is invalid", unavailable_message: "intent JSON output directory is unavailable" });
  return sha256_bytes(encoded);
}

import { ORDERING_EXEMPT_REASON } from "./provenance_ir";
import { validate_expected_with_source } from "./provenance_ir";

