import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";
import { accepts_schema } from "../common/schema_identity";
import { carrier_contract_sha256, derive_required_carriers, RequirementSource } from "./criterion_carriers";
import {
  AUTHORED_STEP_CAUSE_ORIGIN,
  authored_expectation_step_binding,
  ground_source_span,
  with_authored_step_anchor,
} from "./mindmap_contract_projector";

const ROOT = _cex_data_path("");
const PROJECTION_PATH = path.join(ROOT, "knowledge", "data", "compile_ref", "criterion_rules.json");
export const NORMALIZED_CLAIM_SCHEMA = "ist.normalized-claim";
const _CHECK_LOCATOR_RE = /\[check[0-9]+\]/gi;
const _ASCII_TOKEN_RE = /(?<![A-Za-z0-9_-])([A-Za-z][A-Za-z0-9_-]*)(?![A-Za-z0-9_-])/g;

export class CriterionNormalizationError extends Error {}

export interface NormalizationResult {
  expectations: Array<Record<string, any>>;
  disclosures: Array<Record<string, any>>;
  pending: Array<Record<string, any>>;
}

function _canonical_sha256(value: any): string {
  return crypto.createHash("sha256").update(canonicalJson(value), "utf8").digest("hex");
}

function canonicalJson(value: any): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function load_projection(projectionPath: string = PROJECTION_PATH): Record<string, any> {
  let payload: any;
  try {
    payload = JSON.parse(fs.readFileSync(projectionPath, "utf8"));
  } catch (exc) {
    throw new CriterionNormalizationError("criterion rule projection is unavailable");
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload) || !accepts_schema(payload.schema, "ist.criterion-rules")) {
    throw new CriterionNormalizationError("criterion rule projection schema is invalid");
  }
  const expected = String(payload.projection_sha256 || "");
  const body: Record<string, any> = {};
  for (const [key, value] of Object.entries(payload)) {
    if (key !== "projection_sha256") body[key] = value;
  }
  if (!/^[0-9a-f]{64}$/.test(expected) || _canonical_sha256(body) !== expected) {
    throw new CriterionNormalizationError("criterion rule projection identity is invalid");
  }
  const types = payload.criterion_types;
  const rules = payload.rules;
  if (!Array.isArray(types) || !Array.isArray(rules)) {
    throw new CriterionNormalizationError("criterion rule projection is incomplete");
  }
  const carrierIdentity = (payload.identity || {}).criterion_carrier_contract_sha256;
  if (carrierIdentity !== carrier_contract_sha256()) {
    throw new CriterionNormalizationError("criterion carrier projection identity is stale");
  }
  return payload;
}

function _criterion_type_ids(projection: Record<string, any>): Set<string> {
  const out = new Set<string>();
  for (const row of projection.criterion_types || []) {
    if (row && typeof row === "object" && String(row.criterion_type || "")) {
      out.add(String(row.criterion_type || ""));
    }
  }
  return out;
}

function _semantic_text(text: any): string {
  return String(text || "").replace(_CHECK_LOCATOR_RE, "").split(/\s+/).filter(Boolean).join(" ").trim();
}

function _claim_step_binding(claim: Record<string, any>, opts: { autoid: string; mindmap_text: string; source_text?: string | null }): [number | null, string | null] {
  const sourceText = opts.source_text === null || opts.source_text === undefined ? String(claim.source_text || "") : opts.source_text;
  return authored_expectation_step_binding(String(opts.mindmap_text || ""), {
    autoid: String(claim.autoid || opts.autoid || ""),
    origin: String(claim.origin || ""),
    source_text: String(sourceText || ""),
  });
}

function _claim_step(claim: Record<string, any>, opts: { autoid: string; mindmap_text: string }): number | null {
  return _claim_step_binding(claim, opts)[0];
}

function _step_texts(case_: Record<string, any>): Array<[number, string]> {
  const out: Array<[number, string]> = [];
  const steps = case_.steps || [];
  for (let index = 1; index <= steps.length; index++) {
    const step = steps[index - 1];
    if (!step || typeof step !== "object") continue;
    let number: number;
    try {
      number = parseInt(String(step.n || index), 10);
      if (!Number.isFinite(number)) number = index;
    } catch {
      number = index;
    }
    const text = String(step.text || "");
    if (text.trim()) out.push([number, text]);
  }
  return out;
}

function _head_pattern(head: string): RegExp {
  const parts = String(head).split(/\s+/).filter(Boolean).map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!parts.length) return /(?!x)x/;
  return new RegExp("(?<![A-Za-z0-9_-])" + parts.join("\\s+") + "(?![A-Za-z0-9_-])", "i");
}

function _object_occurrences(case_: Record<string, any>, projection: Record<string, any>): Record<string, Array<Record<string, any>>> {
  const classes = projection.object_classes;
  if (!classes || typeof classes !== "object" || Array.isArray(classes)) {
    throw new CriterionNormalizationError("criterion object classes are unavailable");
  }
  const steps = _step_texts(case_);
  const out: Record<string, Array<Record<string, any>>> = {};
  for (const [classId, spec] of Object.entries(classes)) {
    if (!spec || typeof spec !== "object") continue;
    const patterns = ((spec as any).members || [])
      .filter((head: any) => String(head).trim())
      .map((head: any): [string, RegExp] => [String(head), _head_pattern(String(head))]);
    const hits: Array<Record<string, any>> = [];
    for (const [number, text] of steps) {
      const matched = [...new Set<string>(patterns.filter(([, pattern]: [string, RegExp]) => pattern.test(text)).map(([head]: [string, RegExp]) => head))]
        .sort((a: string, b: string) => b.split(/\s+/).length - a.split(/\s+/).length || a.localeCompare(b));
      if (matched.length) hits.push({ step: number, heads: matched });
    }
    out[String(classId)] = hits;
  }
  return out;
}

function _data_path(dataPath: string): any {
  const { load_grammar } = require("./domain_grammar");
  let value: any = load_grammar();
  for (const segment of String(dataPath || "").split(".")) {
    if (!segment || !value || typeof value !== "object" || !(segment in value)) return null;
    value = value[segment];
  }
  return value;
}

function _word_set(dataPath: string): Set<string> {
  const value = _data_path(dataPath);
  const words = value && typeof value === "object" ? value.words : null;
  const out = new Set<string>();
  for (const item of words || []) {
    const semantic = _semantic_text(item);
    if (semantic) out.add(semantic);
  }
  return out;
}

function _algorithm_classes(case_: Record<string, any>): Set<string> {
  const { load_grammar } = require("./domain_grammar");
  const grammar = load_grammar();
  const classes = grammar.algorithm_classes || {};
  const text = [
    String(case_.title || ""),
    ..._step_texts(case_).map(([, value]) => value),
    ...(case_.expectations_by_step || []).filter((item: any) => item && typeof item === "object").map((item: any) => String(item.text || "")),
  ].join("\n");
  const tokens = new Set<string>();
  for (const m of text.matchAll(_ASCII_TOKEN_RE)) tokens.add(m[1].toLowerCase());
  const out = new Set<string>();
  for (const [classId, spec] of Object.entries<any>(classes)) {
    if (!spec || typeof spec !== "object") continue;
    const methods = (spec.methods || []).map((v: any) => String(v).toLowerCase());
    if (methods.some((m: string) => tokens.has(m))) out.add(String(classId));
  }
  return out;
}

function _resource_profile(resource: any): [Set<string>, Record<string, any>] {
  if (typeof resource === "string") return [new Set([resource.toLowerCase()]), {}];
  if (Array.isArray(resource)) {
    return [new Set(resource.filter((item: any) => typeof item === "string" && item).map((item: string) => item.toLowerCase())), {}];
  }
  if (resource && typeof resource === "object") {
    const markers = new Set<string>();
    for (const key of ["kind", "resource", "marker"]) {
      const value = String(resource[key] || "");
      if (value.trim()) markers.add(value.toLowerCase());
    }
    return [markers, { ...resource }];
  }
  return [new Set(), {}];
}

function _operator_criterion(operator: string): string | null {
  const map: Record<string, string> = { not_found: "absence", found_times: "count", found: "content_match", abs_found: "content_match" };
  return map[String(operator || "").trim()] ?? null;
}

function _stress_triage(opts: { expectation: Record<string, any>; resource_profile: Record<string, any>; prior_match: Record<string, any> | null }): [string, string | null, Record<string, any>] {
  const { expectation, resource_profile, prior_match } = opts;
  if (prior_match && prior_match.criterion_type) {
    return ["l_expressible", String(prior_match.criterion_type), { delegated_rule_id: String(prior_match.rule_id || "") }];
  }
  const assertion = expectation.assertion;
  if (assertion && typeof assertion === "object") {
    const criterionType = _operator_criterion(String(assertion.operator || ""));
    if (criterionType) {
      return ["l_expressible", criterionType, { operator: String(assertion.operator || "") }];
    }
  }
  const distribution = resource_profile.distribution;
  if (distribution && typeof distribution === "object") {
    const { validate_distribution } = require("./distribution_assertion");
    const error = validate_distribution(distribution.total, distribution.buckets);
    if (error === null || error === undefined) {
      return ["l_expressible", "distribution", { distribution }];
    }
    if (String(error).includes("容差") || String(error).includes("上界")) {
      return ["numeric_tolerance_out_of_range", null, { reason: error }];
    }
  }
  return ["manual_recommended", null, {}];
}

function _rule_match(rule: Record<string, any>, opts: {
  case: Record<string, any>; expectation: Record<string, any>; object_occurrences: Record<string, Array<Record<string, any>>>;
  algorithm_classes: Set<string>; resource_markers: Set<string>; resource_profile: Record<string, any>; claim_step?: number | null;
}): Record<string, any> | null {
  const { case: case_, expectation, object_occurrences, algorithm_classes, resource_markers, resource_profile, claim_step } = opts;
  const predicate = rule.predicate;
  const output = rule.output;
  if (!predicate || typeof predicate !== "object" || !output || typeof output !== "object") return null;
  const semantic = _semantic_text(expectation.text);
  const patterns = predicate.claim_patterns;
  if (Array.isArray(patterns) && patterns.length) {
    let patternMatched = false;
    try {
      patternMatched = patterns.some((pattern: any) => new RegExp(String(pattern)).test(semantic));
    } catch {
      return null;
    }
    if (!patternMatched) return null;
  }
  if ("object_class_any" in predicate) {
    const required = (predicate.object_class_any || []).map(String);
    const excluded = (predicate.object_class_none || []).map(String);
    if (!required.length || !required.some((name: string) => object_occurrences[name]?.length)) return null;
    if (excluded.some((name: string) => object_occurrences[name]?.length)) return null;
    if (claim_step === null || claim_step === undefined ||
        !required.some((name: string) => (object_occurrences[name] || []).some((hit: any) => Number(hit.step || 0) < claim_step))) {
      return null;
    }
    const words = _word_set(String(predicate.judgment_word_set || ""));
    if (!words.has(semantic)) return null;
  }
  if (predicate.algorithm_class) {
    if (!algorithm_classes.has(String(predicate.algorithm_class))) return null;
    if (!Array.isArray(patterns) || !patterns.length) return null;
    let match: RegExpExecArray | null = null;
    for (const pattern of patterns) {
      match = new RegExp(String(pattern)).exec(semantic);
      if (match) break;
    }
    if (match === null) return null;
    const groups = match.groups || {};
    let nPool: number | null = null;
    const request = String(groups.request || "");
    const member = String(groups.member || "");
    if (/^\d+$/.test(request) && /^\d+$/.test(member) && request === member) {
      nPool = parseInt(member, 10);
    }
    return {
      criterion_type: String(output.criterion_type || ""), rule_id: String(rule.rule_id || ""),
      mode: String(output.mode || ""), min_requests: nPool,
      min_requests_formula: String(output.min_requests_formula || ""),
    };
  }
  if (predicate.resource_marker) {
    const marker = String(predicate.resource_marker || "").toLowerCase();
    if (!resource_markers.has(marker)) return null;
    const [triage, criterionType, details] = _stress_triage({ expectation, resource_profile, prior_match: null });
    return {
      criterion_type: criterionType, rule_id: String(rule.rule_id || ""),
      mode: String(output.mode || "triage"), triage, triage_details: details,
    };
  }
  if (!["object_class_any", "algorithm_class", "resource_marker", "claim_patterns"].some((key) => key in predicate)) {
    return null;
  }
  const out: Record<string, any> = {
    criterion_type: String(output.criterion_type || ""), rule_id: String(rule.rule_id || ""),
    mode: String(output.mode || "direct"),
  };
  for (const [key, value] of Object.entries(output)) {
    if (!["criterion_type", "mode"].includes(key)) out[key] = value;
  }
  return out;
}

function _proposal_match(proposal: Record<string, any>, semantic: string): boolean {
  const predicate = proposal.predicate;
  if (!predicate || typeof predicate !== "object") return false;
  const patterns = predicate.claim_patterns;
  return Array.isArray(patterns) && patterns.some((pattern: any) => new RegExp(String(pattern)).test(semantic));
}

function _shape_key(opts: { semantic: string; object_classes: string[]; algorithm_classes: Set<string>; resource_markers: Set<string>; version_family: string }): string {
  return _canonical_sha256({
    schema: "ist.criterion-shape-key", semantic: opts.semantic,
    object_classes: [...opts.object_classes].sort(),
    algorithm_classes: [...opts.algorithm_classes].sort(),
    resource_markers: [...opts.resource_markers].sort(),
    version_family: String(opts.version_family || ""),
  });
}

export function normalize_case_expectations(opts: {
  case: Record<string, any>; expectations: Array<Record<string, any>>; mindmap_text: string;
  resource?: any; version_family?: string; projection?: Record<string, any> | null;
  author_rules?: Record<string, Record<string, any>> | Map<string, Record<string, any>> | null;
  manual_version?: string | null; requirement_sources?: Record<string, RequirementSource> | null;
}): NormalizationResult {
  const case_ = opts.case;
  const projection = { ...(opts.projection || load_projection()) };
  const version_family = String(opts.version_family || (projection.identity || {}).version_family || "");
  let resolved_manual_version = String(opts.manual_version || "");
  if (!resolved_manual_version) {
    const { resolve_compile_manual_version } = require("./criterion_author_rules");
    resolved_manual_version = resolve_compile_manual_version({});
  }
  const typeIds = _criterion_type_ids(projection);
  const typeLabels: Record<string, string> = {};
  for (const row of projection.criterion_types || []) {
    if (row && typeof row === "object") {
      typeLabels[String(row.criterion_type || "")] = String(row.label_zh || "");
    }
  }
  const objectOccurrences = _object_occurrences(case_, projection);
  const presentClasses = Object.entries(objectOccurrences).filter(([, hits]) => hits.length).map(([classId]) => classId).sort();
  const algorithms = _algorithm_classes(case_);
  const [resourceMarkers, resourceProfile] = _resource_profile(opts.resource);
  const rules = (projection.rules || []).filter((row: any) => row && typeof row === "object");
  let authorRules: any = opts.author_rules;
  if (authorRules === null || authorRules === undefined) {
    const { load_author_rules } = require("./criterion_author_rules");
    authorRules = load_author_rules({ manual_version: resolved_manual_version });
  }
  const authorGet = (key: string): Record<string, any> | undefined => {
    if (authorRules instanceof Map) return authorRules.get(key);
    return authorRules[key];
  };
  const out: Array<Record<string, any>> = [];
  const disclosures: Array<Record<string, any>> = [];
  const pending: Array<Record<string, any>> = [];
  for (const rawExpectation of opts.expectations) {
    const expectation = { ...rawExpectation };
    const claim = expectation.author_claim || expectation.defect_spec_claim || expectation.assertion || {};
    const isClaim = claim && typeof claim === "object";
    const expectationId = isClaim ? String(claim.expectation_id || "") : "";
    const semanticKey = isClaim ? String(claim.semantic_key || "") : "";
    const semantic = _semantic_text(expectation.text);
    const span = ground_source_span(String(expectation.text || ""), String(opts.mindmap_text || ""), {
      origin: isClaim ? String(claim.origin || "") : "",
    });
    const shapeKey = _shape_key({
      semantic, object_classes: presentClasses, algorithm_classes: algorithms,
      resource_markers: resourceMarkers, version_family,
    });
    const [claimStep, claimStepCause] = isClaim
      ? _claim_step_binding(claim, {
          autoid: String(case_.autoid || ""), mindmap_text: String(opts.mindmap_text || ""),
          source_text: String(expectation.text || ""),
        })
      : [null, AUTHORED_STEP_CAUSE_ORIGIN];
    let matched: Record<string, any> | null = null;
    let matchedRule: Record<string, any> | null = null;
    if (span !== null) {
      let baseMatch: Record<string, any> | null = null;
      let baseRule: Record<string, any> | null = null;
      let stressRule: Record<string, any> | null = null;
      for (const rule of rules) {
        const predicate = rule && typeof rule === "object" ? rule.predicate : {};
        if (predicate && typeof predicate === "object" && predicate.resource_marker) {
          const marker = String(predicate.resource_marker || "").toLowerCase();
          if (resourceMarkers.has(marker)) stressRule = rule;
          continue;
        }
        const candidate = _rule_match(rule, {
          case: case_, expectation, object_occurrences: objectOccurrences,
          algorithm_classes: algorithms, resource_markers: resourceMarkers,
          resource_profile: resourceProfile, claim_step: claimStep,
        });
        if (candidate !== null) {
          baseMatch = candidate;
          baseRule = rule;
          break;
        }
      }
      if (stressRule !== null) {
        const [triage, stressType, details] = _stress_triage({ expectation, resource_profile: resourceProfile, prior_match: baseMatch });
        matched = {
          criterion_type: stressType, rule_id: String(stressRule.rule_id || ""),
          mode: "triage", triage, triage_details: details,
        };
        matchedRule = stressRule;
      } else {
        matched = baseMatch;
        matchedRule = baseRule;
      }
    }
    const authorRecord = authorGet(`${shapeKey} ${resolved_manual_version}`);
    let vetoBinding: Record<string, any> | null = null;
    if (matched === null && authorRecord && typeof authorRecord === "object") {
      const authorOutput = authorRecord.output;
      const authorIdentity = authorRecord.identity;
      const authorType = authorOutput && typeof authorOutput === "object" ? String(authorOutput.criterion_type || "") : "";
      if (typeIds.has(authorType) && authorIdentity && typeof authorIdentity === "object") {
        matched = {
          criterion_type: authorType, rule_id: String(authorRecord.rule_id || ""),
          mode: String(authorOutput.mode || "direct"),
        };
        matchedRule = { identity: { ...authorIdentity } };
        const { VETO_ANSWER, build_criterion_veto_question } = require("./criterion_author_rules");
        const vetoQuestion = build_criterion_veto_question(authorRecord);
        vetoBinding = {
          answer_key: String(vetoQuestion._answer_key || ""), answer: VETO_ANSWER,
          rule_sha256: String(authorRecord.rule_sha256 || ""),
        };
      }
    }
    let status = matched && matched.criterion_type ? "matched" : "unmatched";
    if (matched && matched.triage === "manual_recommended") status = "manual_recommended";
    if (matched && matched.triage === "numeric_tolerance_out_of_range") status = "numeric_tolerance_out_of_range";
    const criterionType = String((matched || {}).criterion_type || "") || null;
    if (criterionType !== null && !typeIds.has(criterionType)) {
      throw new CriterionNormalizationError("matched criterion type is outside catalogue");
    }
    const isAuthorMatched = status === "matched" && authorRecord && typeof authorRecord === "object";
    const normalizedClaim: Record<string, any> = {
      schema: NORMALIZED_CLAIM_SCHEMA, expectation_id: expectationId, semantic_key: semanticKey,
      original_text: String(expectation.text || ""),
      original_claim_sha256: isClaim ? String(claim.claim_sha256 || "") : "",
      source_span: span, shape_key: shapeKey, version_family: String(version_family || ""),
      algorithm_classes: [...algorithms].sort(), authored_step: claimStep, authored_step_cause: claimStepCause,
      status, criterion_type: criterionType,
      criterion_label_zh: typeLabels[criterionType || ""] || null,
      rule_id: String((matched || {}).rule_id || "") || null,
      rule_identity: matchedRule && typeof matchedRule === "object" ? { ...(matchedRule.identity || {}) } : null,
      evidence_chain: matchedRule && typeof matchedRule === "object" && matchedRule.identity && typeof matchedRule.identity === "object" && matchedRule.identity.evidence_chain && typeof matchedRule.identity.evidence_chain === "object"
        ? { ...matchedRule.identity.evidence_chain } : null,
      author_veto: vetoBinding,
      anchor_citation_corrected: isAuthorMatched ? Boolean(authorRecord.anchor_citation_corrected) : false,
      supersede_cause: isAuthorMatched ? String(authorRecord.supersede_cause || "") || null : null,
      mode: String((matched || {}).mode || "") || null,
      disclosure: isAuthorMatched
        ? String(authorRecord.disclosure || "")
        : status === "matched"
          ? "作者原文保持不变；带身份规则只给出判据类型，编写期不得另行改读。"
          : "作者原文保持不变；静态规则未命中，等待引擎内部判据裁定。",
      catalog_sha256: String(projection.projection_sha256 || ""),
    };
    for (const [key, value] of Object.entries(matched || {})) {
      if (!["criterion_type", "rule_id", "mode"].includes(key)) normalizedClaim[key] = value;
    }
    normalizedClaim.required_carriers = derive_required_carriers(expectation, normalizedClaim, {
      requirement_sources: opts.requirement_sources ?? null,
    });
    expectation.normalized_claim = normalizedClaim;
    expectation.text_anchor = with_authored_step_anchor(expectation.text_anchor, claimStep);
    out.push(expectation);
    const disclosure: Record<string, any> = {
      autoid: String(case_.autoid || ""), expectation_id: expectationId, shape_key: shapeKey,
      version_family: String(version_family || ""), algorithm_classes: [...algorithms].sort(),
      status, criterion_type: criterionType, rule_id: normalizedClaim.rule_id,
      authored_step: claimStep, authored_step_cause: claimStepCause, source_span: span,
      evidence_chain: normalizedClaim.evidence_chain, message: normalizedClaim.disclosure,
    };
    disclosures.push(disclosure);
    if (status !== "matched") {
      pending.push({ ...disclosure, original_text: String(expectation.text || "") });
    }
  }
  return { expectations: out, disclosures, pending };
}

export function criterion_claim(value: any): Record<string, any> | null {
  if (value === null || value === undefined || Array.isArray(value) || typeof value !== "object") return null;
  const claim = (value as Record<string, any>).normalized_claim;
  if (claim && typeof claim === "object" && accepts_schema(claim.schema, NORMALIZED_CLAIM_SCHEMA)) {
    return claim;
  }
  return null;
}
