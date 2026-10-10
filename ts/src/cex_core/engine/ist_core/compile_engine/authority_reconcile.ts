// 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/authority_reconcile.py（sha256 a0e257c75fb775ee）。不在这里手改。
import crypto from "node:crypto";

import { pyJsonDumps, PyValueError } from "../../_py";
import { accepts_schema } from "../../common/schema_identity";

export const AUTHORITY_SCHEMA = 'ist.authority-reconcile';
const _SHA256_RE = /^[0-9a-f]{64}$/;

export enum AuthorityLayer {
  SPEC = 'spec',
  CASE = 'case',
  EXCEL = 'excel_dialect',
  CAPABILITY = 'capability_xml',
  PRECEDENT = 'precedent',
  MANUAL = 'manual_reference',
  BED = 'bed',
}

export enum AuthorityState {
  READY = 'ready',
  NEEDS_DECISION = 'needs_decision',
  BLOCKED = 'blocked',
}

export enum EvidenceStatus {
  PRESENT = 'present',
  ABSENT = 'absent',
  UNKNOWN = 'unknown',
  NOT_REFERENCED = 'not_referenced',
}
export const ManualStatus = EvidenceStatus;
export type ManualStatus = EvidenceStatus;

export enum RegistryStatus {
  AVAILABLE = 'available',
  UNAVAILABLE = 'unavailable',
  UNKNOWN = 'unknown',
}

export enum ClosureStatus {
  VERIFIED = 'verified',
  CONFLICT = 'conflict',
  UNAVAILABLE = 'unavailable',
  NOT_REQUIRED = 'not_required',
}

export enum ComparisonStatus {
  MATCH = 'match',
  CONFLICT = 'conflict',
  UNAVAILABLE = 'unavailable',
  EXPLICIT_ABSENCE = 'explicit_absence',
  NOT_REQUIRED = 'not_required',
}

export enum ReconcileFailure {
  MISSING_IDENTITY = 'missing_identity',
  BUILD_MISMATCH = 'build_mismatch',
  SPEC_CASE_CONFLICT = 'spec_case_conflict',
  CASE_CAPABILITY_CONFLICT = 'case_capability_conflict',
  CAPABILITY_PRECEDENT_CONFLICT = 'capability_precedent_conflict',
  SEMANTIC_CLOSURE_MISSING = 'semantic_closure_missing',
  SEMANTIC_BINDING_AMBIGUOUS = 'semantic_binding_ambiguous',
  SEMANTIC_SOURCE_DRIFT = 'semantic_source_drift',
  EXPECTED_SOURCE_CONFLICT = 'expected_source_conflict',
  EXPECTED_SOURCE_UNKNOWN = 'expected_source_unknown',
  CAPABILITY_UNKNOWN = 'capability_unknown',
  STALE_OBSERVATION = 'stale_observation',
  REFERENCE_IDENTITY_MISMATCH = 'reference_identity_mismatch',
  REFERENCE_CONFLICT = 'reference_conflict',
  REFERENCE_UNKNOWN = 'reference_unknown',
  REGISTRY_UNAVAILABLE = 'registry_unavailable',
  IDEMPOTENCY_CONFLICT = 'idempotency_conflict',
  PROJECTION_INVALID = 'projection_invalid',
  ARTIFACT_IDENTITY_MISMATCH = 'artifact_identity_mismatch',
  DELIVERY_IDENTITY_MISMATCH = 'delivery_identity_mismatch',
  AUTHORITY_NOT_READY = 'authority_not_ready',
  UNKNOWN = 'unknown',
}

class _ClaimOriginView {
  source_kind: string = '';

  get authority_source(): string {
    const { claim_authority_source } = require("../../case_compiler/provenance_ir");
    return claim_authority_source(this.source_kind);
  }

  get derivation(): string {
    const { claim_derivation } = require("../../case_compiler/provenance_ir");
    return claim_derivation(this.source_kind);
  }
}

export class TypedExpectation extends _ClaimOriginView {
  expectation_id: string = '';
  semantic_key: string = '';
  operator: string = '';
  value: string = '';
  override source_kind: string = '';
  source_locator: string = '';

  constructor(init: Partial<TypedExpectation> = {}) {
    super();
    Object.assign(this, init);
  }

  to_dict(): Record<string, string> {
    return { 'expectation_id': this.expectation_id, 'semantic_key': this.semantic_key, 'operator': this.operator, 'value': this.value, 'source_kind': this.source_kind, 'source_locator': this.source_locator };
  }
}

export class ExpectedFacet extends _ClaimOriginView {
  block_index: number = 0;
  assert_index: number | null = null;
  output_ordinal: number = 0;
  operator: string = '';
  value: string = '';
  override source_kind: string = '';
  source_locator: string = '';

  constructor(init: Partial<ExpectedFacet> = {}) {
    super();
    Object.assign(this, init);
  }

  to_dict(): Record<string, any> {
    return { 'block_index': this.block_index, 'assert_index': this.assert_index, 'output_ordinal': this.output_ordinal, 'operator': this.operator, 'value': this.value, 'source_kind': this.source_kind, 'source_locator': this.source_locator };
  }
}

export class FacetedExpectation {
  expectation_id: string = '';
  semantic_key: string = '';
  declaration_sha256: string = '';
  mechanical_case_sha256: string = '';
  facets: ExpectedFacet[] = [];

  constructor(init: Partial<FacetedExpectation> = {}) {
    Object.assign(this, init);
  }

  ordered_facets(): ExpectedFacet[] {
    return [...this.facets].sort((a, b) => (a.block_index - b.block_index) || ((a.assert_index === null ? -1 : a.assert_index) - (b.assert_index === null ? -1 : b.assert_index)) || (a.output_ordinal - b.output_ordinal));
  }

  facet_id(facet: ExpectedFacet): string {
    return canonical_sha256({ 'expectation_id': this.expectation_id, 'semantic_key': this.semantic_key, 'declaration_sha256': this.declaration_sha256, 'mechanical_case_sha256': this.mechanical_case_sha256, 'block_index': facet.block_index, 'assert_index': facet.assert_index, 'output_ordinal': facet.output_ordinal });
  }

  to_dict(): Record<string, any> {
    return { 'expectation_id': this.expectation_id, 'semantic_key': this.semantic_key, 'declaration_sha256': this.declaration_sha256, 'mechanical_case_sha256': this.mechanical_case_sha256, 'facets': this.ordered_facets().map((item) => item.to_dict()) };
  }
}

function _expected_facets(expected: TypedExpectation | FacetedExpectation): (TypedExpectation | ExpectedFacet)[] {
  return expected instanceof FacetedExpectation ? expected.ordered_facets() : [expected];
}

export class FinalAssertion extends _ClaimOriginView {
  assertion_id: string = '';
  semantic_key: string = '';
  operator: string = '';
  value: string = '';
  override source_kind: string = '';
  source_locator: string = '';
  expectation_id: string = '';
  observation_ref: string = '';

  constructor(init: Partial<FinalAssertion> = {}) {
    super();
    Object.assign(this, init);
  }

  to_dict(): Record<string, string> {
    return { 'assertion_id': this.assertion_id, 'semantic_key': this.semantic_key, 'operator': this.operator, 'value': this.value, 'source_kind': this.source_kind, 'source_locator': this.source_locator, 'expectation_id': this.expectation_id, 'observation_ref': this.observation_ref };
  }
}

export class ExpectedClaim extends _ClaimOriginView {
  claim_id: string = '';
  producer: string = '';
  expectation_id: string = '';
  semantic_key: string = '';
  operator: string = '';
  value: string = '';
  override source_kind: string = '';
  source_locator: string = '';

  constructor(init: Partial<ExpectedClaim> = {}) {
    super();
    Object.assign(this, init);
  }

  to_dict(): Record<string, string> {
    return { 'claim_id': this.claim_id, 'producer': this.producer, 'expectation_id': this.expectation_id, 'semantic_key': this.semantic_key, 'operator': this.operator, 'value': this.value, 'source_kind': this.source_kind, 'source_locator': this.source_locator };
  }
}

export class SemanticBindingReceipt {
  autoid: string = '';
  projection_receipt_sha256: string = '';
  contract_sha256: string = '';
  artifact_sha256: string = '';
  binding_graph_sha256: string = '';
  provenance_sha256: string = '';
  expectations: (TypedExpectation | FacetedExpectation)[] = [];
  assertions: FinalAssertion[] = [];
  bindings: [string, string][] = [];
  status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  differences: string[] = [];
  failures: ReconcileFailure[] = [];
  receipt_sha256: string = '';

  constructor(init: Partial<SemanticBindingReceipt> = {}) {
    Object.assign(this, init);
  }

  to_dict(): Record<string, any> {
    return { 'schema': 'ist.expectation-assertion-binding', 'autoid': this.autoid, 'projection_receipt_sha256': this.projection_receipt_sha256, 'contract_sha256': this.contract_sha256, 'artifact_sha256': this.artifact_sha256, 'binding_graph_sha256': this.binding_graph_sha256, 'provenance_sha256': this.provenance_sha256, 'expectations': this.expectations.map((item) => item.to_dict()), 'assertions': this.assertions.map((item) => item.to_dict()), 'bindings': this.bindings.map(([left, right]) => ({ 'expectation_id': left, 'assertion_id': right })), 'status': this.status, 'differences': [...this.differences], 'failures': this.failures.map((item) => item.valueOf()), 'receipt_sha256': this.receipt_sha256 };
  }
}

export class SemanticClosureResult {
  status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  receipt: SemanticBindingReceipt = new SemanticBindingReceipt();
  failures: ReconcileFailure[] = [];

  constructor(init: Partial<SemanticClosureResult> = {}) {
    Object.assign(this, init);
  }
}

export class ExpectedClaimReceipt {
  autoid: string = '';
  semantic_binding_receipt_sha256: string = '';
  projection_receipt_sha256: string = '';
  contract_sha256: string = '';
  artifact_sha256: string = '';
  binding_graph_sha256: string = '';
  provenance_sha256: string = '';
  claims: ExpectedClaim[] = [];
  status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  differences: string[] = [];
  receipt_sha256: string = '';

  constructor(init: Partial<ExpectedClaimReceipt> = {}) {
    Object.assign(this, init);
  }

  to_dict(): Record<string, any> {
    return { 'schema': 'ist.expected-source-claims', 'autoid': this.autoid, 'semantic_binding_receipt_sha256': this.semantic_binding_receipt_sha256, 'projection_receipt_sha256': this.projection_receipt_sha256, 'contract_sha256': this.contract_sha256, 'artifact_sha256': this.artifact_sha256, 'binding_graph_sha256': this.binding_graph_sha256, 'provenance_sha256': this.provenance_sha256, 'claims': this.claims.map((item) => item.to_dict()), 'status': this.status, 'differences': [...this.differences], 'receipt_sha256': this.receipt_sha256 };
  }

  static from_dict(raw: Record<string, any>): ExpectedClaimReceipt {
    if (!accepts_schema(raw['schema'], 'ist.expected-source-claims')) {
      throw new PyValueError('expected claim receipt schema mismatch');
    }
    let receipt: ExpectedClaimReceipt;
    try {
      const claims = (raw['claims'] as any[]).map((item) => new ExpectedClaim(item));
      receipt = new ExpectedClaimReceipt({ autoid: String(raw['autoid']), semantic_binding_receipt_sha256: String(raw['semantic_binding_receipt_sha256']), projection_receipt_sha256: String(raw['projection_receipt_sha256']), contract_sha256: String(raw['contract_sha256']), artifact_sha256: String(raw['artifact_sha256']), binding_graph_sha256: String(raw['binding_graph_sha256']), provenance_sha256: String(raw['provenance_sha256']), claims, status: ClosureStatus[String(raw['status']).toUpperCase() as keyof typeof ClosureStatus] ?? (String(raw['status']) as ClosureStatus), differences: (raw['differences'] || []).map((item: any) => String(item)), receipt_sha256: String(raw['receipt_sha256']) });
    } catch (exc) {
      throw new PyValueError('expected claim receipt is incomplete');
    }
    const material = receipt.to_dict();
    delete material['receipt_sha256'];
    if (canonical_sha256(material) !== receipt.receipt_sha256) {
      throw new PyValueError('expected claim receipt SHA mismatch');
    }
    const identity_values = [receipt.semantic_binding_receipt_sha256, receipt.projection_receipt_sha256, receipt.contract_sha256, receipt.artifact_sha256, receipt.binding_graph_sha256, receipt.provenance_sha256, receipt.receipt_sha256];
    if (!receipt.autoid || identity_values.some((value) => !_SHA256_RE.test(value))) {
      throw new PyValueError('expected claim receipt identity is incomplete');
    }
    const claim_ids = receipt.claims.map((item) => item.claim_id);
    const _claim_incomplete = (item: ExpectedClaim): boolean => {
      const required = [item.claim_id, item.expectation_id, item.semantic_key, item.operator, item.source_kind, item.source_locator];
      if (expected_source_group(item.source_kind) !== 'configbinding') {
        required.push(item.value);
      }
      return !['u1', 'u3'].includes(item.producer) || !required.every((value) => String(value).trim());
    };
    if (!receipt.claims.length || new Set(claim_ids).size !== claim_ids.length || receipt.claims.some(_claim_incomplete)) {
      throw new PyValueError('expected claim identities are incomplete or duplicated');
    }
    if ([ClosureStatus.VERIFIED, ClosureStatus.CONFLICT].includes(receipt.status)) {
      const producers: Map<string, Set<string>> = new Map();
      for (const item of receipt.claims) {
        const key = `${item.expectation_id}${item.semantic_key}`;
        if (!producers.has(key)) producers.set(key, new Set());
        producers.get(key)!.add(item.producer);
      }
      if ([...producers.values()].some((value) => !(value.size === 2 && value.has('u1') && value.has('u3')))) {
        throw new PyValueError('expected claim producer bijection is incomplete');
      }
    }
    return receipt;
  }
}

export class SourceClaimClosure {
  source_kind: string = '';
  status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  receipt_sha256: string = '';
  differences: string[] = [];

  constructor(init: Partial<SourceClaimClosure> = {}) {
    Object.assign(this, init);
  }
}

const _EXPECTED_SOURCE_GROUPS: Record<string, string> = { 'intent': 'author', 'author': 'author', 'spec': 'spec', 'defect_spec': 'spec', 'defectspec': 'spec', 'manual': 'manual', 'capability_xml': 'capability_xml', 'capabilityxml': 'capability_xml', 'config_derived': 'configbinding', 'captured_relation': 'configbinding', 'distribution_derived': 'configbinding', 'membership_derived': 'configbinding', 'configbinding': 'configbinding', 'status_derived': 'author' };

export function expected_source_group(source_kind: string): string {
  return _EXPECTED_SOURCE_GROUPS[String(source_kind || '').trim().toLowerCase()] ?? '';
}

const _SOURCE_RANK: Record<string, number> = { 'spec': 4, 'author': 3, 'capability_xml': 2, 'manual': 1 };

export function source_outranks(winner: string, loser: string): boolean {
  const winner_group = expected_source_group(winner) || String(winner || '').trim().toLowerCase();
  const loser_group = expected_source_group(loser) || String(loser || '').trim().toLowerCase();
  const high = _SOURCE_RANK[winner_group];
  const low = _SOURCE_RANK[loser_group];
  return high !== undefined && low !== undefined && high > low;
}

export function product_assertion_steps(steps: any[], opts: { mutation_receipt?: Record<string, any> | null } = {}): any[] {
  const mutation_receipt = opts.mutation_receipt ?? null;
  const { MUTATION_ROLE_CONTROL } = require("../../case_compiler/provenance_ir");
  const _flip_evidence_ref = (step: any): string => {
    const assertion_type = step?.assertion_type;
    if (typeof assertion_type !== "object" || assertion_type === null || Array.isArray(assertion_type)) {
      return '';
    }
    const flip = assertion_type['flip'];
    if (typeof flip !== "object" || flip === null || Array.isArray(flip)) {
      return '';
    }
    return String(flip['evidence_ref'] || '');
  };
  const assertions = steps.filter((step) => String(step.E ?? '').trim() === 'check_point');
  const declared = assertions.filter((step) => String(step?.mutation_role ?? '') === MUTATION_ROLE_CONTROL);
  if (!declared.length) {
    return assertions;
  }
  const minted: Record<string, number> = {};
  const requirements = (typeof mutation_receipt === "object" && mutation_receipt !== null) ? (mutation_receipt['requirements'] || []) : [];
  for (const item of requirements) {
    if (typeof item === "object" && item !== null && String(item['mode'] || '') === 'in_case_serialized') {
      const key = String(item['evidence_ref'] || '');
      minted[key] = (minted[key] || 0) + 1;
    }
  }
  const declared_refs: Record<string, number> = {};
  for (const step of declared) {
    const key = _flip_evidence_ref(step);
    declared_refs[key] = (declared_refs[key] || 0) + 1;
  }
  const _countsEqual = (a: Record<string, number>, b: Record<string, number>): boolean => {
    const ak = Object.keys(a);
    const bk = Object.keys(b);
    return ak.length === bk.length && ak.every((k) => a[k] === b[k]);
  };
  if (!Object.keys(minted).length || '' in minted || !_countsEqual(declared_refs, minted)) {
    return assertions;
  }
  return assertions.filter((step) => String(step?.mutation_role ?? '') !== MUTATION_ROLE_CONTROL);
}

const _COMPOSITE_ASSERTION_KINDS = new Set(['captured_relation', 'distribution_derived', 'membership_derived', 'status_derived']);

function _same_expected_source(expected: TypedExpectation | ExpectedFacet, actual: FinalAssertion): boolean {
  if (expected.source_kind !== actual.source_kind) {
    return false;
  }
  if (_COMPOSITE_ASSERTION_KINDS.has(expected.source_kind)) {
    return expected.source_locator === actual.source_locator || (expected.operator === actual.operator && expected.value === actual.value);
  }
  return expected.source_locator === actual.source_locator;
}

function _recomputed_composite_receipt(step: any): [Record<string, any> | null, number, string] {
  const { build_config_binding_derivation_receipt, derivation_output_count, reconcile_config_binding_derivation_receipt } = require("../../case_compiler/provenance_ir");
  const source = step?.source;
  const kind = String(source?.kind ?? '');
  if (!_COMPOSITE_ASSERTION_KINDS.has(kind)) {
    return [null, 0, 'source.kind is not a relation/composite assertion kind'];
  }
  const supplied = source?.receipt;
  if (typeof supplied !== "object" || supplied === null || Array.isArray(supplied) || !Object.keys(supplied).length) {
    return [null, 0, 'relation/composite assertion has no derivation receipt'];
  }
  const source_input = supplied['source_input'];
  if (typeof source_input !== "object" || source_input === null || Array.isArray(source_input)) {
    return [null, 0, 'composite derivation source_input is missing'];
  }
  const rule_id = String(supplied['rule_id'] || '');
  const [rebuilt, error] = build_config_binding_derivation_receipt({ source_kind: kind, recipe_id: String(source?.ref ?? ''), rule_id, source_input, output_step: { 'E': step.E, 'F': step.F, 'G': step.G }, output_ordinal: supplied['output_ordinal'] ?? 0 });
  if (rebuilt === null || rebuilt === undefined) {
    return [null, 0, error];
  }
  const [reconciled, reconcile_error] = reconcile_config_binding_derivation_receipt(supplied, rebuilt);
  if (reconciled === null || reconciled === undefined) {
    return [null, 0, reconcile_error];
  }
  const [size, size_error] = derivation_output_count({ source_kind: kind, rule_id, source_input });
  if (size === null || size === undefined) {
    return [null, 0, size_error];
  }
  return [reconciled, size, ''];
}

function _composite_assertion_groups_are_complete(steps: any[]): boolean {
  const groups: Map<string, Record<string, any>[]> = new Map();
  const sizes: Map<string, number> = new Map();
  for (const step of steps) {
    const source = step?.source;
    const kind = String(source?.kind ?? '');
    if (!_COMPOSITE_ASSERTION_KINDS.has(kind)) {
      continue;
    }
    const [receipt, size, _error] = _recomputed_composite_receipt(step);
    if (receipt === null) {
      return false;
    }
    const identity = JSON.stringify([kind, String(source?.ref ?? ''), String(receipt['rule_id'] || ''), String(receipt['source_input_sha256'] || '')]);
    if (!groups.has(identity)) groups.set(identity, []);
    groups.get(identity)!.push(receipt);
    if (sizes.has(identity) && sizes.get(identity) !== size) {
      return false;
    }
    sizes.set(identity, size);
  }
  for (const [identity, receipts] of groups) {
    const ordinals = receipts.map((receipt) => Math.trunc(Number(receipt['output_ordinal']) || 0)).sort((a, b) => a - b);
    const size = sizes.get(identity)!;
    if (receipts.length !== size || JSON.stringify(ordinals) !== JSON.stringify(Array.from({ length: size }, (_, i) => i))) {
      return false;
    }
  }
  return true;
}

export function author_fixture_policies_from_contract(contract: Record<string, any>): Record<string, Record<string, any>> {
  const policies: Record<string, Record<string, any>> = {};
  for (const item of (contract['expectations'] || [])) {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      continue;
    }
    const author_claim = item['author_claim'];
    const normalized_claim = item['normalized_claim'];
    if (typeof author_claim !== "object" || author_claim === null || Array.isArray(author_claim) || typeof normalized_claim !== "object" || normalized_claim === null || Array.isArray(normalized_claim)) {
      continue;
    }
    const expectation_id = String(author_claim['expectation_id'] || '').trim();
    const policy = normalized_claim['fixture_policy'];
    if (expectation_id && normalized_claim['mode'] === 'fixture_backref' && String(normalized_claim['expectation_id'] || '') === expectation_id && typeof policy === "object" && policy !== null && !Array.isArray(policy)) {
      policies[expectation_id] = { ...policy };
    }
  }
  return policies;
}

function _author_claim_is_compiled_form(step: any, opts: { fixture_policy?: Record<string, any> | null } = {}): boolean {
  const fixture_policy = opts.fixture_policy ?? null;
  const source = step?.source;
  const kind = String(source?.kind ?? '');
  if (kind === 'intent') {
    return !!(String(source?.ref ?? '') === String(step?.expectation_id || '') && step.G);
  }
  if (_COMPOSITE_ASSERTION_KINDS.has(kind)) {
    if (!String(step?.observation_ref ?? '').trim()) {
      return false;
    }
    const [receipt, _size, _error] = _recomputed_composite_receipt(step);
    return receipt !== null;
  }
  if (kind === 'config_derived' && typeof fixture_policy === "object" && fixture_policy !== null) {
    const allowed_kinds = fixture_policy['allowed_kinds'];
    const receipt = source?.receipt;
    const source_input = (typeof receipt === "object" && receipt !== null) ? receipt['source_input'] : null;
    const fixture_kind = String((typeof source_input === "object" && source_input !== null) ? source_input['fixture_kind'] : '');
    const fixture_value = (typeof source_input === "object" && source_input !== null) ? source_input['value'] : null;
    const prefix = String(fixture_policy['value_prefix'] || '');
    const suffix = String(fixture_policy['domain_suffix'] || '');
    let safe_fixture_value = false;
    if (typeof fixture_value === "string" && prefix) {
      if (fixture_kind === 'text_value') {
        safe_fixture_value = !!(fixture_value.startsWith(prefix) && /^[A-Za-z0-9._-]+$/.test(fixture_value));
      } else if (fixture_kind === 'domain_name' && suffix) {
        safe_fixture_value = !!(fixture_value.startsWith(prefix) && fixture_value.endsWith(suffix) && /^[A-Za-z0-9.-]+$/.test(fixture_value));
      }
    }
    return !!(fixture_policy['expected_binding_rule'] === 'config.fixture-literal-backref' && fixture_policy['disclosure_required'] === true && Array.isArray(allowed_kinds) && allowed_kinds.every((item: any) => typeof item === "string") && new Set(allowed_kinds).size === 2 && allowed_kinds.includes('domain_name') && allowed_kinds.includes('text_value') && JSON.stringify(Object.keys(fixture_policy).sort()) === JSON.stringify(['allowed_kinds', 'disclosure_required', 'domain_suffix', 'expected_binding_rule', 'value_prefix']) && typeof receipt === "object" && receipt !== null && receipt['rule_id'] === 'config.fixture-literal-backref' && receipt['status'] === 'compiler_recomputed' && typeof source_input === "object" && source_input !== null && (allowed_kinds as string[]).includes(fixture_kind) && source_input['operator'] === step.F && fixture_value === step.G && safe_fixture_value && step.G);
  }
  return false;
}

function _assertion_observation_instances(assertions: any[], all_steps: any[]): [Map<any, [string, number]>, string] {
  const ids: Map<string, number[]> = new Map();
  const channels: Map<string, number[]> = new Map();
  const positions: Map<any, number[]> = new Map();
  for (let index = 0; index < all_steps.length; index++) {
    const step = all_steps[index];
    if (!positions.has(step)) positions.set(step, []);
    positions.get(step)!.push(index);
    if (String(step?.E ?? '').trim() === 'check_point' || !String(step?.observation_id ?? '').trim()) {
      continue;
    }
    for (const [field, mapping] of [['observation_id', ids], ['result_channel', channels]] as [string, Map<string, number[]>][]) {
      const value = String(step?.[field] ?? '').trim();
      if (value) {
        if (!mapping.has(value)) mapping.set(value, []);
        mapping.get(value)!.push(index);
      }
    }
  }
  if ([...ids.values()].some((indices) => indices.length !== 1)) {
    return [new Map(), 'duplicate observation_id'];
  }
  const resolved: Map<any, [string, number]> = new Map();
  for (const step of assertions) {
    const reference = String(step?.observation_ref ?? '').trim();
    if (!reference) {
      continue;
    }
    const producers = ids.get(reference) ?? channels.get(reference) ?? [];
    if (!producers.length) {
      return [new Map(), 'undefined observation_ref'];
    }
    if (producers.length !== 1) {
      return [new Map(), 'ambiguous observation_ref'];
    }
    let consumers = positions.get(step);
    if (consumers === undefined || consumers === null) {
      consumers = all_steps.map((candidate, index) => [candidate, index] as const).filter(([candidate]) => candidate === step).map(([, index]) => index);
    }
    if (consumers.length !== 1) {
      return [new Map(), 'assertion is not uniquely located in all_steps'];
    }
    if (producers[0] >= consumers[0]) {
      return [new Map(), 'observation_ref is not defined before the assertion'];
    }
    resolved.set(step, ['observation-producer', producers[0]]);
  }
  return [resolved, ''];
}

export function check_expectation_assertion_bijection(opts: { autoid: string; final_steps: any[]; all_steps?: any[] | null; stamped_expectations: Record<string, any>; stamped_author_claims?: Record<string, any> | null; stamped_defect_spec_claims?: Record<string, any> | null; stamped_author_fixture_policies?: Record<string, Record<string, any>> | null }): string | null {
  const { autoid, final_steps, stamped_expectations } = opts;
  const all_steps = opts.all_steps ?? null;
  const stamped_author_claims = opts.stamped_author_claims ?? {};
  const stamped_defect_spec_claims = opts.stamped_defect_spec_claims ?? {};
  const stamped_author_fixture_policies = opts.stamped_author_fixture_policies ?? {};
  const contract_ids = [...Object.keys(stamped_expectations).map((item) => String(item)), ...Object.keys(stamped_author_claims).map((item) => String(item)), ...Object.keys(stamped_defect_spec_claims).map((item) => String(item))];
  const expected_ids = new Set(contract_ids);
  const observed_groups: Map<string, any[]> = new Map();
  for (const step of final_steps) {
    const key = String(step?.expectation_id || '');
    if (!observed_groups.has(key)) observed_groups.set(key, []);
    observed_groups.get(key)!.push(step);
  }
  if (observed_groups.has('') || expected_ids.size !== contract_ids.length || !(expected_ids.size === observed_groups.size && [...expected_ids].every((x) => observed_groups.has(x)))) {
    return `error: final assertions have no explicit expectation_id bijection to the typed expectation contract for case ${autoid}`;
  }
  let observation_instances: Map<any, [string, number]> = new Map();
  if (all_steps !== null) {
    const [instances, observation_error] = _assertion_observation_instances(final_steps, all_steps);
    observation_instances = instances;
    if (observation_error) {
      return `error: assertion observation binding is invalid for case ${autoid}: ${observation_error}`;
    }
  }
  for (const [expectation_id, group] of observed_groups) {
    const signatures: Set<string> = new Set();
    for (const step of group) {
      const observation_ref = String(step?.observation_ref ?? '').trim();
      const source_kind = String(step?.source?.kind ?? '');
      const observation_key = observation_instances.has(step) ? JSON.stringify(observation_instances.get(step)) : JSON.stringify([_COMPOSITE_ASSERTION_KINDS.has(source_kind) ? '<composite-observation-ref>' : '<unresolved-observation-ref>', observation_ref, '']);
      signatures.add(observation_key + '|' + String(step?.F ?? '') + '|' + String(step?.G ?? ''));
    }
    if (signatures.size !== group.length) {
      return `error: assertions sharing expectation_id ${JSON.stringify(expectation_id)} do not differ in observation, operator, or expected value for case ${autoid}`;
    }
  }
  for (const step of final_steps) {
    if (step.expectation_id in stamped_author_claims) {
      const claim = stamped_author_claims[step.expectation_id];
      if (step.semantic_key !== String(claim['semantic_key'] || '') || !String(step.F ?? '').trim() || !_author_claim_is_compiled_form(step, { fixture_policy: stamped_author_fixture_policies[step.expectation_id] })) {
        return `error: pending Author claim was not compiled into a source-bound F/G assertion for case ${autoid}`;
      }
      continue;
    }
    if (step.expectation_id in stamped_defect_spec_claims) {
      const claim = stamped_defect_spec_claims[step.expectation_id];
      const resolver_receipt = claim['resolver_receipt'];
      const current_resolver: Record<string, any> = {};
      for (const [key, value] of Object.entries(step.source.receipt || {})) {
        if (key !== 'defect_spec_compilation') current_resolver[key] = value;
      }
      if (step.semantic_key !== String(claim['semantic_key'] || '') || step.source.kind !== 'defect_spec' || step.source.ref !== String(claim['locator'] || '') || JSON.stringify(current_resolver) !== JSON.stringify(resolver_receipt) || !String(step.F ?? '').trim() || !step.G) {
        return `error: pending DefectSpec claim was not compiled into a source-bound F/G assertion for case ${autoid}`;
      }
      continue;
    }
    if (!(step.expectation_id in stamped_expectations)) {
      return `error: final assertion does not map to a stamped expectation for case ${autoid}`;
    }
    const expected_assertion = stamped_expectations[step.expectation_id];
    const expected_source = expected_assertion['source'] || {};
    if (step.semantic_key !== String(expected_assertion['semantic_key'] || '')) {
      return `error: final assertion semantic_key drifted from the typed expectation contract for case ${autoid}`;
    }
    const expected_group = expected_source_group(String(expected_source['kind'] || ''));
    const final_group = expected_source_group(step.source.kind);
    if (!expected_group || !final_group) {
      return `error: final assertion source is outside the expected-source closure for case ${autoid}`;
    }
    if (expected_group === final_group) {
      const expected_tuple = [String(expected_assertion['operator'] || ''), String(expected_assertion['value'] || ''), String(expected_source['kind'] || ''), String(expected_source['locator'] || '')];
      const final_tuple = [step.F, step.G, step.source.kind, step.source.ref];
      if (JSON.stringify(expected_tuple) !== JSON.stringify(final_tuple)) {
        return `error: final assertions are not a byte-exact bijection of the typed expectation contract for case ${autoid}`;
      }
      const current_resolver2: Record<string, any> = {};
      for (const [key, value] of Object.entries(step.source.receipt || {})) {
        if (key !== 'defect_spec_compilation') current_resolver2[key] = value;
      }
      if (String(expected_source['kind'] || '') === 'defect_spec' && JSON.stringify(current_resolver2) !== JSON.stringify(expected_source['receipt'])) {
        return `error: final DefectSpec resolver receipt drifted from the typed expectation contract for case ${autoid}`;
      }
    }
  }
  for (const [expectation_id, group] of observed_groups) {
    if (!_composite_assertion_groups_are_complete(group)) {
      return `error: relation/composite assertion expansion is incomplete for expectation_id ${JSON.stringify(expectation_id)} in case ${autoid}`;
    }
  }
  return null;
}

export class AuthorityEvidence {
  layer: AuthorityLayer = AuthorityLayer.SPEC;
  status: EvidenceStatus = EvidenceStatus.ABSENT;
  identity: string = '';
  build: string = '';
  locators: string[] = [];
  metadata: Record<string, any> = {};

  constructor(init: Partial<AuthorityEvidence> = {}) {
    Object.assign(this, init);
    if (this.metadata === null || this.metadata === undefined) {
      this.metadata = {};
    }
  }
}

export class SpecCaseComparison {
  locator_status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  semantic_status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  locator_receipt_sha256: string = '';
  semantic_receipt_sha256: string = '';
  differences: string[] = [];

  constructor(init: Partial<SpecCaseComparison> = {}) {
    Object.assign(this, init);
  }
}

export class ManualCaseComparison {
  semantic_status: ClosureStatus = ClosureStatus.UNAVAILABLE;
  semantic_receipt_sha256: string = '';
  differences: string[] = [];

  constructor(init: Partial<ManualCaseComparison> = {}) {
    Object.assign(this, init);
  }
}

export class CaseCapabilityComparison {
  requirements: string[] = [];
  enabled: string[] = [];
  disabled: string[] = [];
  unknown: string[] = [];
  registry_receipt_sha256: string = '';

  constructor(init: Partial<CaseCapabilityComparison> = {}) {
    Object.assign(this, init);
  }
}

export class CapabilityPrecedentComparison {
  referenced_capabilities: string[] = [];
  precedent_capabilities: string[] = [];
  registry_receipt_sha256: string = '';
  build_status: ClosureStatus = ClosureStatus.NOT_REQUIRED;
  differences: string[] = [];

  constructor(init: Partial<CapabilityPrecedentComparison> = {}) {
    Object.assign(this, init);
  }
}

export class ExecutionBinding {
  autoid: string = '';
  projection_receipt_sha256: string = '';
  projection_sha256: string = '';
  artifact_sha256: string = '';
  run_id: string = '';
  dispatch_id: string = '';
  batch_run_id: string = '';
  bed_lease_id: string = '';
  bed_build: string = '';
  module: string = '';
  consistency_contract_sha256: string | null = null;

  constructor(init: Partial<ExecutionBinding> = {}) {
    Object.assign(this, init);
  }
}

export class AuthorityInputs {
  binding: ExecutionBinding = new ExecutionBinding();
  spec: AuthorityEvidence = new AuthorityEvidence();
  case_: AuthorityEvidence = new AuthorityEvidence();
  excel: AuthorityEvidence = new AuthorityEvidence();
  capability: AuthorityEvidence = new AuthorityEvidence();
  precedent: AuthorityEvidence = new AuthorityEvidence();
  bed: AuthorityEvidence = new AuthorityEvidence();
  manual: AuthorityEvidence = new AuthorityEvidence();
  spec_case: SpecCaseComparison = new SpecCaseComparison();
  case_capability: CaseCapabilityComparison = new CaseCapabilityComparison();
  case_product_capability: CaseCapabilityComparison = new CaseCapabilityComparison();
  capability_precedent: CapabilityPrecedentComparison = new CapabilityPrecedentComparison();
  source_claims: SourceClaimClosure[] = [];
  manual_case: ManualCaseComparison = new ManualCaseComparison({ semantic_status: ClosureStatus.NOT_REQUIRED });
  registry_status: RegistryStatus = RegistryStatus.AVAILABLE;
  schema: string = AUTHORITY_SCHEMA;

  constructor(init: Partial<AuthorityInputs> = {}) {
    Object.assign(this, init);
  }
}

export class PairwiseComparison {
  comparison_id: string = '';
  left: AuthorityLayer = AuthorityLayer.SPEC;
  right: AuthorityLayer = AuthorityLayer.SPEC;
  status: ComparisonStatus = ComparisonStatus.UNAVAILABLE;
  failure: ReconcileFailure | null = null;
  left_identity: string = '';
  right_identity: string = '';
  differences: string[] = [];

  constructor(init: Partial<PairwiseComparison> = {}) {
    Object.assign(this, init);
  }

  get is_conflict(): boolean {
    return this.status === ComparisonStatus.CONFLICT;
  }

  to_dict(): Record<string, any> {
    return { 'comparison_id': this.comparison_id, 'left': this.left, 'right': this.right, 'status': this.status, 'failure': this.failure ? this.failure.valueOf() : null, 'left_identity': this.left_identity, 'right_identity': this.right_identity, 'differences': [...this.differences] };
  }
}

export class AuthorityReceipt {
  schema: string = '';
  input_sha256: string = '';
  idempotency_key: string = '';
  receipt_sha256: string = '';
  state: AuthorityState = AuthorityState.BLOCKED;
  binding: ExecutionBinding = new ExecutionBinding();
  spec_generation_id: string = '';
  spec_manifest_sha256: string = '';
  source_identities: [string, string, string, string][] = [];
  comparisons: PairwiseComparison[] = [];
  conflicts: string[] = [];
  failures: ReconcileFailure[] = [];

  constructor(init: Partial<AuthorityReceipt> = {}) {
    Object.assign(this, init);
  }

  to_dict(): Record<string, any> {
    return { 'schema': this.schema, 'input_sha256': this.input_sha256, 'idempotency_key': this.idempotency_key, 'receipt_sha256': this.receipt_sha256, 'state': this.state, 'binding': _binding_dict(this.binding), 'spec_generation_id': this.spec_generation_id, 'spec_manifest_sha256': this.spec_manifest_sha256, 'source_identities': this.source_identities.map(([layer, status, identity, build]) => ({ 'layer': layer, 'status': status, 'identity': identity, 'build': build })), 'comparisons': this.comparisons.map((item) => item.to_dict()), 'conflicts': [...this.conflicts], 'failures': this.failures.map((item) => item.valueOf()) };
  }
}

export class PersistenceResult {
  state: AuthorityState = AuthorityState.BLOCKED;
  receipt: AuthorityReceipt = new AuthorityReceipt();
  persisted: boolean = false;
  failure: ReconcileFailure | null = null;
  detail: string = '';

  constructor(state: AuthorityState, receipt: AuthorityReceipt, persisted: boolean, failure: ReconcileFailure | null = null, detail: string = '') {
    this.state = state;
    this.receipt = receipt;
    this.persisted = persisted;
    this.failure = failure;
    this.detail = detail;
  }
}

export class ExpectedClaimPersistenceResult {
  state: AuthorityState = AuthorityState.BLOCKED;
  fact: Record<string, any> = {};
  persisted: boolean = false;
  failure: ReconcileFailure | null = null;
  detail: string = '';

  constructor(state: AuthorityState, fact: Record<string, any>, persisted: boolean, failure: ReconcileFailure | null = null, detail: string = '') {
    this.state = state;
    this.fact = fact;
    this.persisted = persisted;
    this.failure = failure;
    this.detail = detail;
  }
}

export class ExpectedAuthorityPreflight {
  state: AuthorityState = AuthorityState.BLOCKED;
  claim_receipt_sha256: string = '';
  source_claims: SourceClaimClosure[] = [];
  resolved_conflicts: string[] = [];
  unresolved_conflicts: string[] = [];
  failures: ReconcileFailure[] = [];
  receipt_sha256: string = '';

  constructor(init: Partial<ExpectedAuthorityPreflight> = {}) {
    Object.assign(this, init);
  }

  to_dict(): Record<string, any> {
    return { 'schema': 'ist.expected-authority-preflight', 'state': this.state, 'claim_receipt_sha256': this.claim_receipt_sha256, 'source_claims': this.source_claims.map((item) => ({ 'source_kind': item.source_kind, 'status': item.status, 'receipt_sha256': item.receipt_sha256, 'differences': [...item.differences] })), 'resolved_conflicts': [...this.resolved_conflicts], 'unresolved_conflicts': [...this.unresolved_conflicts], 'failures': this.failures.map((item) => item.valueOf()), 'receipt_sha256': this.receipt_sha256 };
  }
}

export class DeliveryClaim {
  binding: ExecutionBinding = new ExecutionBinding();
  authority_receipt_sha256: string = '';
  spec_generation_id: string = '';
  spec_manifest_sha256: string = '';

  constructor(init: Partial<DeliveryClaim> = {}) {
    Object.assign(this, init);
  }
}

export class GateVerdict {
  state: AuthorityState = AuthorityState.BLOCKED;
  failures: ReconcileFailure[] = [];
  mismatched_fields: string[] = [];

  constructor(state: AuthorityState, failures: ReconcileFailure[] = [], mismatched_fields: string[] = []) {
    this.state = state;
    this.failures = failures;
    this.mismatched_fields = mismatched_fields;
  }

  get allowed(): boolean {
    return this.state === AuthorityState.READY;
  }
}

export type FactReader = () => Record<string, any>[];
export type FactAppender = (fact: Record<string, any>) => void;
export type BindingValidator = (binding: ExecutionBinding) => boolean;

function _canonical_json(value: any): Buffer {
  return Buffer.from(pyJsonDumps(value, { ensure_ascii: false, sort_keys: true, separators: [',', ':'] }), 'utf-8');
}

export function canonical_sha256(value: any): string {
  return crypto.createHash("sha256").update(_canonical_json(value)).digest("hex");
}

export function reconcile_expectation_assertions(opts: { autoid: string; projection_receipt_sha256: string; contract_sha256: string; artifact_sha256: string; binding_graph_sha256: string; provenance_sha256: string; expectations: (TypedExpectation | FacetedExpectation)[]; assertions: FinalAssertion[] }): SemanticClosureResult {
  const { autoid, projection_receipt_sha256, contract_sha256, artifact_sha256, binding_graph_sha256, provenance_sha256, expectations, assertions } = opts;
  const identity_fields: Record<string, string> = { 'projection_receipt_sha256': projection_receipt_sha256, 'contract_sha256': contract_sha256, 'artifact_sha256': artifact_sha256, 'binding_graph_sha256': binding_graph_sha256, 'provenance_sha256': provenance_sha256 };
  const malformed = Object.entries(identity_fields).filter(([, value]) => !_SHA256_RE.test(String(value || ''))).map(([name]) => name);
  const differences: string[] = [];
  const failures: ReconcileFailure[] = [];
  if (!autoid || malformed.length || !expectations.length || !assertions.length) {
    if (malformed.length) {
      differences.push('invalid_identity:' + [...malformed].sort().join(','));
    }
    if (!expectations.length) {
      differences.push('missing_typed_expectations');
    }
    if (!assertions.length) {
      differences.push('missing_final_assertions');
    }
    failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
  }
  const _complete_fields = (item: TypedExpectation | ExpectedFacet | FinalAssertion): boolean => {
    const runtime_bound = expected_source_group(item.source_kind) === 'configbinding';
    const required = [item.operator, item.source_kind, item.source_locator];
    if (!runtime_bound) {
      required.push(item.value);
    }
    return required.every((value) => String(value).trim());
  };
  const _complete_expected = (item: TypedExpectation | FacetedExpectation): boolean => {
    if (!String(item.expectation_id).trim() || !String(item.semantic_key).trim()) {
      return false;
    }
    if (item instanceof FacetedExpectation) {
      if (!_SHA256_RE.test(String(item.declaration_sha256)) || !_SHA256_RE.test(String(item.mechanical_case_sha256)) || !item.facets.length) {
        return false;
      }
      if (item.facets.some((facet) => typeof facet.block_index !== "number" || !Number.isInteger(facet.block_index) || facet.block_index < 0 || (facet.assert_index !== null && (typeof facet.assert_index !== "number" || !Number.isInteger(facet.assert_index) || facet.assert_index < 0)) || typeof facet.output_ordinal !== "number" || !Number.isInteger(facet.output_ordinal) || facet.output_ordinal < 0)) {
        return false;
      }
    }
    return _expected_facets(item).every((facet) => _complete_fields(facet));
  };
  if (expectations.some((item) => !_complete_expected(item)) || assertions.some((item) => !_complete_fields(item) || ![item.assertion_id, item.expectation_id, item.semantic_key, item.observation_ref].every((value) => String(value).trim()))) {
    differences.push('incomplete_semantic_tuple');
    failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
  }
  const exp_ids = expectations.map((item) => item.expectation_id);
  const assertion_ids = assertions.map((item) => item.assertion_id);
  if (new Set(exp_ids).size !== exp_ids.length || new Set(assertion_ids).size !== assertion_ids.length) {
    differences.push('duplicate_semantic_identity');
    failures.push(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS);
  }
  for (const expected of expectations) {
    if (expected instanceof FacetedExpectation) {
      const slots = expected.facets.map((facet) => [facet.block_index, facet.assert_index, facet.output_ordinal]);
      if (new Set(slots.map((s) => JSON.stringify(s))).size !== slots.length) {
        differences.push(`duplicate_facet_identity:${expected.expectation_id}`);
        failures.push(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS);
      }
      const coords = new Set(slots.map(([block, assertion]) => JSON.stringify([block, assertion])));
      for (const coordinate of coords) {
        const ordinals = slots.filter(([block, assertion]) => JSON.stringify([block, assertion]) === coordinate).map(([, , ordinal]) => ordinal as number).sort((a, b) => a - b);
        if (JSON.stringify(ordinals) !== JSON.stringify(Array.from({ length: ordinals.length }, (_, i) => i))) {
          differences.push(`incomplete_facet_identity:${expected.expectation_id}`);
          failures.push(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS);
        }
      }
    }
  }
  const assertions_by_expectation: Map<string, FinalAssertion[]> = new Map();
  for (const assertion of assertions) {
    if (!assertions_by_expectation.has(assertion.expectation_id)) assertions_by_expectation.set(assertion.expectation_id, []);
    assertions_by_expectation.get(assertion.expectation_id)!.push(assertion);
  }
  for (const [expectation_id, group] of assertions_by_expectation) {
    const signatures = new Set(group.map((item) => JSON.stringify([item.observation_ref, item.operator, item.value])));
    if (signatures.size !== group.length) {
      differences.push(`duplicate_assertion_shape:${expectation_id}`);
      failures.push(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS);
    }
  }
  const bindings: [string, string][] = [];
  if (!failures.length) {
    const remaining: Map<string, FinalAssertion> = new Map(assertions.map((item) => [item.assertion_id, item]));
    for (const expected of [...expectations].sort((a, b) => a.expectation_id < b.expectation_id ? -1 : 1)) {
      const candidates = [...remaining.values()].filter((item) => item.expectation_id === expected.expectation_id).sort((a, b) => a.assertion_id < b.assertion_id ? -1 : 1);
      if (!candidates.length) {
        differences.push(`unbound_expectation:${expected.expectation_id}`);
        failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
        continue;
      }
      const facets = _expected_facets(expected);
      const expected_groups = new Set(facets.map((facet) => expected_source_group(facet.source_kind)));
      const local: FinalAssertion[] = [];
      let independent = false;
      for (const actual of candidates) {
        if (actual.semantic_key !== expected.semantic_key) {
          differences.push(`semantic_key_drift:${expected.expectation_id}`);
          failures.push(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS);
          remaining.delete(actual.assertion_id);
          continue;
        }
        const actual_group = expected_source_group(actual.source_kind);
        if (expected_groups.has('') || !actual_group) {
          differences.push(`unsupported_source:${expected.expectation_id}`);
          failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
          remaining.delete(actual.assertion_id);
          continue;
        }
        if (!expected_groups.has(actual_group)) {
          independent = true;
          bindings.push([expected.expectation_id, actual.assertion_id]);
          remaining.delete(actual.assertion_id);
          continue;
        }
        local.push(actual);
      }
      const eligible: Map<number, string[]> = new Map();
      const anchored: Set<number> = new Set();
      const by_group: Map<string, FinalAssertion[]> = new Map();
      const by_value: Map<string, FinalAssertion[]> = new Map();
      for (const actual of local) {
        const group = expected_source_group(actual.source_kind);
        if (!by_group.has(group)) by_group.set(group, []);
        by_group.get(group)!.push(actual);
        const vkey = JSON.stringify([group, actual.operator, actual.value]);
        if (!by_value.has(vkey)) by_value.set(vkey, []);
        by_value.get(vkey)!.push(actual);
      }
      for (let index = 0; index < facets.length; index++) {
        const facet = facets[index];
        const group = expected_source_group(facet.source_kind);
        const same_group = by_group.get(group) ?? [];
        if (!same_group.length) {
          if (local.length && !independent) {
            differences.push(`unbound_facet:${expected.expectation_id}:${index}`);
            failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
          }
          continue;
        }
        const exact = by_value.get(JSON.stringify([group, facet.operator, facet.value])) ?? [];
        if (!exact.length) {
          const explained = same_group.every((actual) => facets.some((alternative, other) => other !== index && alternative.operator === actual.operator && alternative.value === actual.value && _same_expected_source(alternative as TypedExpectation, actual)));
          if (explained) {
            differences.push(`unbound_facet:${expected.expectation_id}:${index}`);
            failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
          } else {
            differences.push(`operator_or_value_conflict:${expected.expectation_id}`);
            failures.push(ReconcileFailure.EXPECTED_SOURCE_CONFLICT);
          }
          continue;
        }
        anchored.add(index);
        eligible.set(index, exact.filter((actual) => _same_expected_source(facet as TypedExpectation, actual)).map((actual) => actual.assertion_id));
        if (!eligible.get(index)!.length) {
          differences.push(`source_drift:${expected.expectation_id}`);
          failures.push(ReconcileFailure.SEMANTIC_SOURCE_DRIFT);
        }
      }
      const assigned: Map<string, number> = new Map();
      const assign = (start: number): boolean => {
        const pending = [start];
        const parents: Map<number, [number, string] | null> = new Map([[start, null]]);
        const seen: Set<string> = new Set();
        while (pending.length) {
          let index = pending.pop()!;
          for (let assertion_id of eligible.get(index) ?? []) {
            if (seen.has(assertion_id)) {
              continue;
            }
            seen.add(assertion_id);
            if (!assigned.has(assertion_id)) {
              for (;;) {
                assigned.set(assertion_id, index);
                const parent = parents.get(index);
                if (parent === null || parent === undefined) {
                  return true;
                }
                [index, assertion_id] = parent;
              }
            }
            const previous = assigned.get(assertion_id)!;
            if (!parents.has(previous)) {
              parents.set(previous, [index, assertion_id]);
              pending.push(previous);
            }
          }
        }
        return false;
      };
      for (const [index, matches] of eligible) {
        if (matches.length && !assign(index)) {
          differences.push(`uncovered_facet:${expected.expectation_id}`);
          failures.push(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS);
        }
      }
      for (const actual of local) {
        const group = expected_source_group(actual.source_kind);
        if (![...anchored].some((index) => expected_source_group(facets[index].source_kind) === group)) {
          remaining.delete(actual.assertion_id);
          continue;
        }
        const same_source = new Set(facets.map((facet, index) => [facet, index] as const).filter(([facet]) => _same_expected_source(facet as TypedExpectation, actual)).map(([, index]) => index));
        if (!same_source.size) {
          differences.push(`source_drift:${expected.expectation_id}`);
          failures.push(ReconcileFailure.SEMANTIC_SOURCE_DRIFT);
          remaining.delete(actual.assertion_id);
          continue;
        }
        if ([...same_source].some((i) => anchored.has(i))) {
          bindings.push([expected.expectation_id, actual.assertion_id]);
        }
        remaining.delete(actual.assertion_id);
      }
    }
    if (remaining.size) {
      differences.push(...[...remaining.keys()].sort().map((assertion_id) => `unbound_assertion:${assertion_id}`));
      failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
    }
  }
  const unique_failures = [...new Set(failures)];
  let status: ClosureStatus;
  if (unique_failures.includes(ReconcileFailure.EXPECTED_SOURCE_CONFLICT) && ![ReconcileFailure.SEMANTIC_CLOSURE_MISSING, ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS, ReconcileFailure.SEMANTIC_SOURCE_DRIFT].some((item) => unique_failures.includes(item))) {
    status = ClosureStatus.CONFLICT;
  } else if (unique_failures.length) {
    status = ClosureStatus.UNAVAILABLE;
  } else {
    status = ClosureStatus.VERIFIED;
  }
  const sorted_expectations = [...expectations].sort((a, b) => a.expectation_id < b.expectation_id ? -1 : 1);
  const sorted_assertions = [...assertions].sort((a, b) => a.assertion_id < b.assertion_id ? -1 : 1);
  const sorted_bindings = [...bindings].sort((a, b) => JSON.stringify(a) < JSON.stringify(b) ? -1 : 1);
  const material: Record<string, any> = { 'schema': 'ist.expectation-assertion-binding', 'autoid': autoid, ...identity_fields, 'expectations': sorted_expectations.map((item) => item.to_dict()), 'assertions': sorted_assertions.map((item) => item.to_dict()), 'bindings': sorted_bindings.map(([left, right]) => ({ 'expectation_id': left, 'assertion_id': right })), 'status': status, 'differences': [...new Set(differences)].sort(), 'failures': unique_failures.map((item) => item.valueOf()) };
  const receipt = new SemanticBindingReceipt({ autoid, projection_receipt_sha256, contract_sha256, artifact_sha256, binding_graph_sha256, provenance_sha256, expectations: sorted_expectations, assertions: sorted_assertions, bindings: sorted_bindings, status, differences: material['differences'], failures: unique_failures, receipt_sha256: canonical_sha256(material) });
  return new SemanticClosureResult({ status, receipt, failures: unique_failures });
}

export function produce_expected_claim_receipt(semantic_closure: SemanticClosureResult): ExpectedClaimReceipt {
  const binding = semantic_closure.receipt;
  const differences: string[] = [];
  let status: ClosureStatus;
  if (binding.status !== ClosureStatus.VERIFIED) {
    differences.push(...(binding.differences.length ? binding.differences : ['semantic_binding_unavailable']));
    status = binding.status;
  } else {
    status = ClosureStatus.VERIFIED;
  }
  const claims: ExpectedClaim[] = [];
  for (const item of binding.expectations) {
    for (const facet of _expected_facets(item)) {
      const claim_id = item instanceof FacetedExpectation ? `u1:${item.expectation_id}:facet:${item.facet_id(facet as ExpectedFacet)}` : `u1:${item.expectation_id}`;
      claims.push(new ExpectedClaim({ claim_id, producer: 'u1', expectation_id: item.expectation_id, semantic_key: item.semantic_key, operator: facet.operator, value: facet.value, source_kind: facet.source_kind, source_locator: facet.source_locator }));
    }
  }
  for (const assertion of binding.assertions) {
    claims.push(new ExpectedClaim({ claim_id: `u3:${assertion.assertion_id}`, producer: 'u3', expectation_id: assertion.expectation_id, semantic_key: assertion.semantic_key, operator: assertion.operator, value: assertion.value, source_kind: assertion.source_kind, source_locator: assertion.source_locator }));
  }
  const claim_ids = claims.map((item) => item.claim_id);
  if (new Set(claim_ids).size !== claim_ids.length) {
    differences.push('duplicate_expected_claim_identity');
    status = ClosureStatus.UNAVAILABLE;
  }
  const unsupported = [...new Set(claims.filter((item) => !expected_source_group(item.source_kind)).map((item) => item.source_kind))].sort();
  if (unsupported.length) {
    differences.push(...unsupported.map((item) => `unsupported_expected_source:${item}`));
    status = ClosureStatus.UNAVAILABLE;
  }
  const ordered = [...claims].sort((a, b) => a.claim_id < b.claim_id ? -1 : 1);
  const material: Record<string, any> = { 'schema': 'ist.expected-source-claims', 'autoid': binding.autoid, 'semantic_binding_receipt_sha256': binding.receipt_sha256, 'projection_receipt_sha256': binding.projection_receipt_sha256, 'contract_sha256': binding.contract_sha256, 'artifact_sha256': binding.artifact_sha256, 'binding_graph_sha256': binding.binding_graph_sha256, 'provenance_sha256': binding.provenance_sha256, 'claims': ordered.map((item) => item.to_dict()), 'status': status, 'differences': [...new Set(differences)].sort() };
  return new ExpectedClaimReceipt({ autoid: binding.autoid, semantic_binding_receipt_sha256: binding.receipt_sha256, projection_receipt_sha256: binding.projection_receipt_sha256, contract_sha256: binding.contract_sha256, artifact_sha256: binding.artifact_sha256, binding_graph_sha256: binding.binding_graph_sha256, provenance_sha256: binding.provenance_sha256, claims: ordered, status, differences: material['differences'], receipt_sha256: canonical_sha256(material) });
}

export const CLAIM_CONFLICT_BOTH_TRUE_PREFIX = 'claim_conflict_both_true_release:';

function _assertion_claim_proven(operator: string, value: string, assertion_rows: Record<string, any>[]): boolean {
  let hold: string, contradict: string;
  if (operator === 'found' || operator === 'abs_found') {
    [hold, contradict] = ['successed to find', 'fail to find'];
  } else if (operator === 'not_found') {
    [hold, contradict] = ['fail to find', 'successed to find'];
  } else {
    return false;
  }
  if (!String(value).trim()) {
    return false;
  }
  let proven = false;
  for (const row of assertion_rows) {
    if (String(row['pattern'] || '') !== value) {
      continue;
    }
    const judgment = String(row['judgment'] || '');
    if (String(row['outcome'] || '') === 'Fail' && judgment === contradict) {
      return false;
    }
    if (String(row['outcome'] || '') === 'Success' && judgment === hold && !!row['window_non_empty']) {
      proven = true;
    }
  }
  return proven;
}

export function claim_conflict_both_true(opts: { claims: ExpectedClaim[]; semantic_key: string; left: string; right: string; assertion_rows: Record<string, any>[] }): boolean {
  const { claims, semantic_key, left, right, assertion_rows } = opts;
  const needed = new Set(claims.filter((item) => item.semantic_key === semantic_key && [left, right].includes(expected_source_group(item.source_kind))).map((item) => JSON.stringify([item.operator, item.value])));
  return !!needed.size && [...needed].every((kv) => { const [operator, value] = JSON.parse(kv); return _assertion_claim_proven(operator, value, assertion_rows); });
}

export function reconcile_source_claims(opts: { claim_receipt: ExpectedClaimReceipt; source_kind: string; assertion_rows?: Record<string, any>[] | null }): SourceClaimClosure {
  const { claim_receipt, source_kind } = opts;
  const assertion_rows = opts.assertion_rows ?? null;
  const kind = expected_source_group(source_kind);
  const differences: string[] = [];
  let status: ClosureStatus;
  if (!kind) {
    differences.push('source_kind_missing');
  }
  if (claim_receipt.status === ClosureStatus.CONFLICT) {
    differences.push(...(claim_receipt.differences.length ? claim_receipt.differences : ['claim_receipt_conflict']));
    status = ClosureStatus.CONFLICT;
  } else if (claim_receipt.status !== ClosureStatus.VERIFIED) {
    differences.push(...(claim_receipt.differences.length ? claim_receipt.differences : ['claim_receipt_unavailable']));
    status = ClosureStatus.UNAVAILABLE;
  } else {
    const by_key: Map<string, Map<string, Set<string>>> = new Map();
    const unsupported: Set<string> = new Set();
    for (const item of claim_receipt.claims) {
      const group = expected_source_group(item.source_kind);
      if (!group) {
        unsupported.add(String(item.source_kind || 'unknown'));
        continue;
      }
      if (!by_key.has(item.semantic_key)) by_key.set(item.semantic_key, new Map());
      const by_source = by_key.get(item.semantic_key)!;
      if (!by_source.has(group)) by_source.set(group, new Set());
      by_source.get(group)!.add(JSON.stringify([item.operator, item.value]));
    }
    let source_keys: string[] = [];
    if (unsupported.size) {
      differences.push(...[...unsupported].sort().map((item) => `unsupported_expected_source:${item}`));
      status = ClosureStatus.UNAVAILABLE;
    } else {
      source_keys = [...by_key.keys()].filter((key) => by_key.get(key)!.has(kind)).sort();
    }
    if (!unsupported.size && !source_keys.length) {
      differences.push(`typed_source_claim_missing:${kind || 'unknown'}`);
      status = ClosureStatus.UNAVAILABLE;
    } else if (!unsupported.size) {
      const unresolved: string[] = [];
      const resolved: string[] = [];
      const released: string[] = [];
      for (const semantic_key of source_keys) {
        const source_claims = by_key.get(semantic_key)!.get(kind)!;
        for (const [other_kind, other_claims] of [...by_key.get(semantic_key)!.entries()].sort((a, b) => a[0] < b[0] ? -1 : 1)) {
          if (other_kind === kind) {
            continue;
          }
          if (!(source_claims.size === other_claims.size && [...source_claims].every((x) => other_claims.has(x)))) {
            let winner: string, loser: string;
            if (source_outranks(kind, other_kind)) {
              [winner, loser] = [kind, other_kind];
            } else if (source_outranks(other_kind, kind)) {
              [winner, loser] = [other_kind, kind];
            } else if (assertion_rows !== null && [kind, other_kind].includes('configbinding') && claim_conflict_both_true({ claims: claim_receipt.claims, semantic_key, left: kind, right: other_kind, assertion_rows })) {
              released.push(`${CLAIM_CONFLICT_BOTH_TRUE_PREFIX}${semantic_key}:${kind}:${other_kind}`);
              continue;
            } else {
              unresolved.push(`claim_conflict:${semantic_key}:${kind}:${other_kind}`);
              continue;
            }
            resolved.push(`authority_resolution:${semantic_key}:${winner}:${loser}`);
          }
        }
      }
      differences.push(...[...new Set([...resolved, ...released, ...unresolved])].sort());
      status = unresolved.length ? ClosureStatus.CONFLICT : ClosureStatus.VERIFIED;
    } else {
      status = ClosureStatus.UNAVAILABLE;
    }
  }
  const material: Record<string, any> = { 'schema': 'ist.source-claim-closure', 'claim_receipt_sha256': claim_receipt.receipt_sha256, 'source_kind': kind, 'status': status!, 'differences': [...new Set(differences)].sort() };
  return new SourceClaimClosure({ source_kind: kind, status: status!, receipt_sha256: canonical_sha256(material), differences: material['differences'] });
}

const _EXPECTED_SOURCE_ORDER = ['author', 'spec', 'capability_xml', 'manual', 'configbinding'];

function _not_referenced_source_closure(claim_receipt: ExpectedClaimReceipt, source_kind: string): SourceClaimClosure {
  const material = { 'schema': 'ist.source-claim-closure', 'claim_receipt_sha256': claim_receipt.receipt_sha256, 'source_kind': source_kind, 'status': ClosureStatus.NOT_REQUIRED, 'differences': ['not_referenced'] };
  return new SourceClaimClosure({ source_kind, status: ClosureStatus.NOT_REQUIRED, receipt_sha256: canonical_sha256(material), differences: ['not_referenced'] });
}

export function expected_claim_fact(claim_receipt: ExpectedClaimReceipt, source_claims: SourceClaimClosure[]): Record<string, any> {
  let receipt_invalid = false;
  try {
    ExpectedClaimReceipt.from_dict(claim_receipt.to_dict());
  } catch (e) {
    if (e instanceof PyValueError || e instanceof Error) {
      receipt_invalid = true;
    } else {
      throw e;
    }
  }
  const supplied: Map<string, SourceClaimClosure> = new Map(source_claims.map((item) => [item.source_kind, item]));
  const closure_invalid = supplied.size !== source_claims.length || [...supplied.keys()].some((kind) => !_EXPECTED_SOURCE_ORDER.includes(kind)) || source_claims.some((item) => !_SHA256_RE.test(item.receipt_sha256));
  const closures = _EXPECTED_SOURCE_ORDER.map((kind) => supplied.get(kind) ?? _not_referenced_source_closure(claim_receipt, kind));
  let differences = [...new Set([...closures.flatMap((item) => item.differences).filter((difference) => difference !== 'not_referenced'), ...claim_receipt.differences])].sort();
  const statuses = new Set(closures.map((item) => item.status));
  let state: AuthorityState;
  if (receipt_invalid || closure_invalid || claim_receipt.status === ClosureStatus.UNAVAILABLE || statuses.has(ClosureStatus.UNAVAILABLE)) {
    state = AuthorityState.BLOCKED;
    if (receipt_invalid) {
      differences.push('expected_claim_receipt_invalid');
    }
    if (closure_invalid) {
      differences.push('source_closure_identity_invalid');
    }
  } else if (claim_receipt.status === ClosureStatus.CONFLICT || statuses.has(ClosureStatus.CONFLICT)) {
    state = AuthorityState.NEEDS_DECISION;
  } else {
    state = AuthorityState.READY;
  }
  differences = [...new Set(differences)].sort();
  const idempotency_key = ['ist.expected-source-claims-bound', claim_receipt.autoid, claim_receipt.artifact_sha256, claim_receipt.semantic_binding_receipt_sha256].join(':');
  return { 'ev': 'expected_source_claims_bound', 'aid': claim_receipt.autoid, 'artifact_sha256': claim_receipt.artifact_sha256, 'idempotency_key': idempotency_key, 'semantic_binding_receipt_sha256': claim_receipt.semantic_binding_receipt_sha256, 'claim_receipt_sha256': claim_receipt.receipt_sha256, 'claim_receipt': claim_receipt.to_dict(), 'source_closures': Object.fromEntries(closures.map((item) => [item.source_kind, { 'status': item.status, 'receipt_sha256': item.receipt_sha256, 'differences': [...item.differences] }])), 'status': state, 'differences': differences };
}

export function reconcile_expected_authority_preflight(claim_receipt: ExpectedClaimReceipt): ExpectedAuthorityPreflight {
  let verified: ExpectedClaimReceipt;
  let receipt_valid = true;
  try {
    verified = ExpectedClaimReceipt.from_dict(claim_receipt.to_dict());
  } catch (e) {
    if (!(e instanceof PyValueError) && !(e instanceof Error)) throw e;
    verified = claim_receipt;
    receipt_valid = false;
  }
  const referenced_groups = new Set(verified.claims.map((item) => expected_source_group(item.source_kind)).filter((g) => g));
  const closures = _EXPECTED_SOURCE_ORDER.map((source_kind) => referenced_groups.has(source_kind) ? reconcile_source_claims({ claim_receipt: verified, source_kind }) : _not_referenced_source_closure(verified, source_kind));
  const fact = expected_claim_fact(verified, closures);
  let state = String(fact['status']) as AuthorityState;
  const resolved = [...new Set(closures.flatMap((closure) => closure.differences).filter((item) => item.startsWith('authority_resolution:')))].sort();
  const unresolved = [...new Set(closures.flatMap((closure) => closure.differences).filter((item) => item.startsWith('claim_conflict:')))].sort();
  const failures: ReconcileFailure[] = [];
  if (!receipt_valid || state === AuthorityState.BLOCKED) {
    failures.push(ReconcileFailure.EXPECTED_SOURCE_UNKNOWN);
    state = AuthorityState.BLOCKED;
  } else if (state === AuthorityState.NEEDS_DECISION) {
    failures.push(ReconcileFailure.EXPECTED_SOURCE_CONFLICT);
  }
  const material: Record<string, any> = { 'schema': 'ist.expected-authority-preflight', 'state': state, 'claim_receipt_sha256': verified.receipt_sha256, 'source_claims': closures.map((item) => ({ 'source_kind': item.source_kind, 'status': item.status, 'receipt_sha256': item.receipt_sha256, 'differences': [...item.differences] })), 'resolved_conflicts': [...resolved], 'unresolved_conflicts': [...unresolved], 'failures': failures.map((item) => item.valueOf()) };
  return new ExpectedAuthorityPreflight({ state, claim_receipt_sha256: verified.receipt_sha256, source_claims: closures, resolved_conflicts: resolved, unresolved_conflicts: unresolved, failures, receipt_sha256: canonical_sha256(material) });
}

export function append_expected_claim_fact_once(claim_receipt: ExpectedClaimReceipt, source_claims: SourceClaimClosure[], opts: { read_facts: FactReader; append_fact: FactAppender }): ExpectedClaimPersistenceResult {
  const { read_facts, append_fact } = opts;
  const fact = expected_claim_fact(claim_receipt, source_claims);
  let existing: Record<string, any>[];
  try {
    existing = Array.from(read_facts());
  } catch (exc: any) {
    return new ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, false, ReconcileFailure.REGISTRY_UNAVAILABLE, `read:${exc?.constructor?.name ?? 'Error'}`);
  }
  const _matches = (item: Record<string, any>): boolean => {
    const stripped: Record<string, any> = {};
    for (const [key, value] of Object.entries(item)) {
      if (key !== '_pid') stripped[key] = value;
    }
    return JSON.stringify(stripped) === JSON.stringify(fact);
  };
  const same_key = existing.filter((item) => item['ev'] === fact['ev'] && item['idempotency_key'] === fact['idempotency_key']);
  if (same_key.length) {
    if (same_key.every(_matches)) {
      return new ExpectedClaimPersistenceResult(String(fact['status']) as AuthorityState, fact, false);
    }
    return new ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, false, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'same claim binding key has different content');
  }
  let persisted: Record<string, any>[];
  try {
    append_fact(fact);
    persisted = Array.from(read_facts());
  } catch (exc: any) {
    return new ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, false, ReconcileFailure.REGISTRY_UNAVAILABLE, `write_or_verify:${exc?.constructor?.name ?? 'Error'}`);
  }
  const matches = persisted.filter((item) => item['ev'] === fact['ev'] && item['idempotency_key'] === fact['idempotency_key']);
  if (!matches.length || !matches.every(_matches)) {
    return new ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, false, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'claim fact readback mismatch');
  }
  return new ExpectedClaimPersistenceResult(String(fact['status']) as AuthorityState, fact, true);
}

function _binding_dict(binding: ExecutionBinding): Record<string, any> {
  return { 'autoid': binding.autoid, 'projection_receipt_sha256': binding.projection_receipt_sha256, 'projection_sha256': binding.projection_sha256, 'artifact_sha256': binding.artifact_sha256, 'run_id': binding.run_id, 'dispatch_id': binding.dispatch_id, 'batch_run_id': binding.batch_run_id, 'bed_lease_id': binding.bed_lease_id, 'bed_build': binding.bed_build, 'module': binding.module, 'consistency_contract_sha256': binding.consistency_contract_sha256 };
}

function _evidence_dict(evidence: AuthorityEvidence): Record<string, any> {
  return { 'layer': evidence.layer, 'status': evidence.status, 'identity': evidence.identity, 'build': evidence.build, 'locators': [...evidence.locators], 'metadata': { ...evidence.metadata } };
}

function _manual_evidence(inputs: AuthorityInputs): AuthorityEvidence {
  return inputs.manual;
}

function _spec_generation_identity(inputs: AuthorityInputs): [string, string] {
  if (inputs.spec.status !== EvidenceStatus.PRESENT) {
    return ['', ''];
  }
  const metadata = inputs.spec.metadata;
  return [String(metadata['generation_id'] || ''), String(metadata['manifest_sha256'] || '')];
}

function _inputs_dict(inputs: AuthorityInputs): Record<string, any> {
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  return { 'schema': inputs.schema, 'binding': _binding_dict(inputs.binding), 'spec': _evidence_dict(inputs.spec), 'case': _evidence_dict(case_ev), 'excel': _evidence_dict(inputs.excel), 'capability': _evidence_dict(inputs.capability), 'precedent': _evidence_dict(inputs.precedent), 'manual': _evidence_dict(_manual_evidence(inputs)), 'bed': _evidence_dict(inputs.bed), 'spec_case': { 'locator_status': inputs.spec_case.locator_status, 'semantic_status': inputs.spec_case.semantic_status, 'locator_receipt_sha256': inputs.spec_case.locator_receipt_sha256, 'semantic_receipt_sha256': inputs.spec_case.semantic_receipt_sha256, 'differences': [...inputs.spec_case.differences] }, 'manual_case': { 'semantic_status': inputs.manual_case.semantic_status, 'semantic_receipt_sha256': inputs.manual_case.semantic_receipt_sha256, 'differences': [...inputs.manual_case.differences] }, 'source_claims': [...inputs.source_claims].sort((a, b) => a.source_kind < b.source_kind ? -1 : 1).map((item) => ({ 'source_kind': item.source_kind, 'status': item.status, 'receipt_sha256': item.receipt_sha256, 'differences': [...item.differences] })), 'case_capability': { 'requirements': [...inputs.case_capability.requirements], 'enabled': [...inputs.case_capability.enabled], 'disabled': [...inputs.case_capability.disabled], 'unknown': [...inputs.case_capability.unknown], 'registry_receipt_sha256': inputs.case_capability.registry_receipt_sha256 }, 'case_product_capability': { 'requirements': [...inputs.case_product_capability.requirements], 'enabled': [...inputs.case_product_capability.enabled], 'disabled': [...inputs.case_product_capability.disabled], 'unknown': [...inputs.case_product_capability.unknown], 'registry_receipt_sha256': inputs.case_product_capability.registry_receipt_sha256 }, 'capability_precedent': { 'referenced_capabilities': [...inputs.capability_precedent.referenced_capabilities], 'precedent_capabilities': [...inputs.capability_precedent.precedent_capabilities], 'registry_receipt_sha256': inputs.capability_precedent.registry_receipt_sha256, 'build_status': inputs.capability_precedent.build_status, 'differences': [...inputs.capability_precedent.differences] }, 'registry_status': inputs.registry_status };
}

function _source_identities(inputs: AuthorityInputs): [string, string, string, string][] {
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  const evidence = [inputs.spec, case_ev, inputs.excel, inputs.capability, inputs.precedent, _manual_evidence(inputs), inputs.bed];
  return evidence.map((item) => [item.layer, item.status, item.identity, item.build] as [string, string, string, string]);
}

function _comparison(comparison_id: string, left: AuthorityEvidence, right: AuthorityEvidence, status: ComparisonStatus, failure: ReconcileFailure | null = null, differences: string[] = []): PairwiseComparison {
  return new PairwiseComparison({ comparison_id, left: left.layer, right: right.layer, status, failure, left_identity: left.identity || left.status, right_identity: right.identity || right.status, differences });
}

function _closure_comparison(comparison_id: string, left: AuthorityEvidence, right: AuthorityEvidence, closure: ClosureStatus, opts: { conflict_failure: ReconcileFailure; unavailable_failure: ReconcileFailure; differences?: string[] }): PairwiseComparison {
  const differences = opts.differences ?? [];
  if (closure === ClosureStatus.VERIFIED) {
    return _comparison(comparison_id, left, right, ComparisonStatus.MATCH, null, differences);
  }
  if (closure === ClosureStatus.CONFLICT) {
    return _comparison(comparison_id, left, right, ComparisonStatus.CONFLICT, opts.conflict_failure, differences.length ? differences : ['typed_pair_conflict']);
  }
  if (closure === ClosureStatus.NOT_REQUIRED) {
    return _comparison(comparison_id, left, right, ComparisonStatus.NOT_REQUIRED);
  }
  return _comparison(comparison_id, left, right, ComparisonStatus.UNAVAILABLE, opts.unavailable_failure, differences.length ? differences : ['typed_pair_evidence_unavailable']);
}

function _validation_failures(inputs: AuthorityInputs): ReconcileFailure[] {
  const failures: ReconcileFailure[] = [];
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  const binding = _binding_dict(inputs.binding);
  const required_binding = Object.fromEntries(Object.entries(binding).filter(([key]) => key !== 'consistency_contract_sha256'));
  if (Object.values(required_binding).some((value) => !String(value).trim())) {
    failures.push(ReconcileFailure.MISSING_IDENTITY);
  }
  for (const field of ['projection_receipt_sha256', 'projection_sha256', 'artifact_sha256']) {
    if (!_SHA256_RE.test(String(binding[field]).toLowerCase())) {
      failures.push(ReconcileFailure.MISSING_IDENTITY);
    }
  }
  const consistency_sha = binding['consistency_contract_sha256'];
  if (consistency_sha !== null && !_SHA256_RE.test(String(consistency_sha).toLowerCase())) {
    failures.push(ReconcileFailure.MISSING_IDENTITY);
  }
  const expected_layers: [AuthorityEvidence, AuthorityLayer][] = [[inputs.spec, AuthorityLayer.SPEC], [case_ev, AuthorityLayer.CASE], [inputs.excel, AuthorityLayer.EXCEL], [inputs.capability, AuthorityLayer.CAPABILITY], [inputs.precedent, AuthorityLayer.PRECEDENT], [_manual_evidence(inputs), AuthorityLayer.MANUAL], [inputs.bed, AuthorityLayer.BED]];
  for (const [evidence, layer] of expected_layers) {
    if (evidence.layer !== layer) {
      failures.push(ReconcileFailure.MISSING_IDENTITY);
      continue;
    }
    if (evidence.status === EvidenceStatus.PRESENT && !evidence.identity.trim()) {
      failures.push(ReconcileFailure.MISSING_IDENTITY);
    }
    if ([EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED].includes(evidence.status) && (evidence.identity.trim() || evidence.build.trim() || evidence.locators.length)) {
      failures.push(ReconcileFailure.MISSING_IDENTITY);
    }
  }
  if (case_ev.status !== EvidenceStatus.PRESENT) {
    failures.push(ReconcileFailure.MISSING_IDENTITY);
  }
  if (inputs.excel.status !== EvidenceStatus.PRESENT) {
    failures.push(ReconcileFailure.REGISTRY_UNAVAILABLE);
  }
  if (inputs.capability.status !== EvidenceStatus.PRESENT) {
    failures.push(ReconcileFailure.CAPABILITY_UNKNOWN);
  }
  if (inputs.bed.status !== EvidenceStatus.PRESENT || !inputs.bed.build.trim()) {
    failures.push(ReconcileFailure.MISSING_IDENTITY);
  }
  if (inputs.spec.status === EvidenceStatus.UNKNOWN) {
    failures.push(ReconcileFailure.REFERENCE_UNKNOWN);
  }
  const [spec_generation_id, spec_manifest_sha256] = _spec_generation_identity(inputs);
  if (inputs.spec.status === EvidenceStatus.PRESENT && (!/^[0-9]{20}-[0-9a-f]{16}$/.test(spec_generation_id) || !_SHA256_RE.test(spec_manifest_sha256))) {
    failures.push(ReconcileFailure.MISSING_IDENTITY);
  }
  if (inputs.precedent.status === EvidenceStatus.UNKNOWN) {
    failures.push(ReconcileFailure.STALE_OBSERVATION);
  }
  if (_manual_evidence(inputs).status === EvidenceStatus.UNKNOWN) {
    failures.push(ReconcileFailure.REFERENCE_UNKNOWN);
  }
  if (inputs.precedent.status === EvidenceStatus.PRESENT && (!inputs.precedent.build.trim() || !inputs.precedent.locators.length)) {
    failures.push(ReconcileFailure.STALE_OBSERVATION);
  }
  if (inputs.schema !== AUTHORITY_SCHEMA) {
    failures.push(ReconcileFailure.MISSING_IDENTITY);
  }
  if (inputs.registry_status === RegistryStatus.UNAVAILABLE) {
    failures.push(ReconcileFailure.REGISTRY_UNAVAILABLE);
  } else if (inputs.registry_status === RegistryStatus.UNKNOWN) {
    failures.push(ReconcileFailure.UNKNOWN);
  }
  if (!inputs.source_claims.length) {
    failures.push(ReconcileFailure.SEMANTIC_CLOSURE_MISSING);
  }
  const source_groups = inputs.source_claims.map((item) => item.source_kind);
  if (source_groups.length !== new Set(source_groups).size || source_groups.some((group) => !_EXPECTED_SOURCE_ORDER.includes(group)) || inputs.source_claims.some((item) => !_SHA256_RE.test(item.receipt_sha256))) {
    failures.push(ReconcileFailure.EXPECTED_SOURCE_UNKNOWN);
  }
  return [...new Set(failures)];
}

function _spec_case_comparisons(inputs: AuthorityInputs): PairwiseComparison[] {
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  const pair = inputs.spec_case;
  if ([EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED].includes(inputs.spec.status)) {
    return [_comparison('spec_case_locator', inputs.spec, case_ev, ComparisonStatus.EXPLICIT_ABSENCE), _comparison('spec_case_semantic', inputs.spec, case_ev, ComparisonStatus.NOT_REQUIRED)];
  }
  return [_closure_comparison('spec_case_locator', inputs.spec, case_ev, pair.locator_status, { conflict_failure: ReconcileFailure.REFERENCE_IDENTITY_MISMATCH, unavailable_failure: ReconcileFailure.REFERENCE_UNKNOWN, differences: pair.differences }), _closure_comparison('spec_case_semantic', inputs.spec, case_ev, pair.semantic_status, { conflict_failure: ReconcileFailure.SPEC_CASE_CONFLICT, unavailable_failure: ReconcileFailure.SEMANTIC_CLOSURE_MISSING, differences: pair.differences })];
}

function _coverage_comparison(opts: { comparison_id: string; left: AuthorityEvidence; right: AuthorityEvidence; pair: CaseCapabilityComparison }): PairwiseComparison {
  const { comparison_id, left, right, pair } = opts;
  const required = new Set(pair.requirements);
  const enabled = new Set(pair.enabled);
  const disabled = new Set(pair.disabled);
  const unknown = new Set(pair.unknown);
  const overlap = new Set([...enabled].filter((x) => disabled.has(x)).concat([...enabled].filter((x) => unknown.has(x)), [...disabled].filter((x) => unknown.has(x))));
  const unclassified = new Set([...required].filter((x) => !enabled.has(x) && !disabled.has(x) && !unknown.has(x)));
  const extras = new Set([...enabled, ...disabled, ...unknown].filter((x) => !required.has(x)));
  if (!pair.registry_receipt_sha256 || !_SHA256_RE.test(pair.registry_receipt_sha256) || overlap.size || unclassified.size || extras.size || unknown.size) {
    const differences = [...[...unknown].sort().map((item) => `unknown:${item}`), ...[...unclassified].sort().map((item) => `unclassified:${item}`), ...[...overlap].sort().map((item) => `overlap:${item}`), ...[...extras].sort().map((item) => `extra:${item}`)];
    if (!pair.registry_receipt_sha256) {
      differences.push('registry_receipt_missing');
    }
    return _comparison(comparison_id, left, right, ComparisonStatus.UNAVAILABLE, ReconcileFailure.CAPABILITY_UNKNOWN, differences);
  }
  if (disabled.size) {
    return _comparison(comparison_id, left, right, ComparisonStatus.CONFLICT, ReconcileFailure.CASE_CAPABILITY_CONFLICT, [...disabled].sort().map((item) => `disabled:${item}`));
  }
  return _comparison(comparison_id, left, right, ComparisonStatus.MATCH);
}

function _case_capability_comparisons(inputs: AuthorityInputs): PairwiseComparison[] {
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  return [_coverage_comparison({ comparison_id: 'case_excel_dialect_requirements', left: case_ev, right: inputs.excel, pair: inputs.case_capability }), _coverage_comparison({ comparison_id: 'case_product_capability_requirements', left: case_ev, right: inputs.capability, pair: inputs.case_product_capability })];
}

function _capability_precedent_comparisons(inputs: AuthorityInputs): PairwiseComparison[] {
  const pair = inputs.capability_precedent;
  if ([EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED].includes(inputs.precedent.status)) {
    return [_comparison('capability_precedent_requirements', inputs.capability, inputs.precedent, ComparisonStatus.EXPLICIT_ABSENCE), _comparison('precedent_bed_build', inputs.precedent, inputs.bed, ComparisonStatus.NOT_REQUIRED)];
  }
  const required = new Set(pair.referenced_capabilities);
  const precedent = new Set(pair.precedent_capabilities);
  let differences = [...pair.differences, ...[...required].filter((x) => !precedent.has(x)).sort().map((item) => `missing_precedent_capability:${item}`), ...[...precedent].filter((x) => !required.has(x)).sort().map((item) => `extra_precedent_capability:${item}`)];
  let capability_status: ComparisonStatus;
  let capability_failure: ReconcileFailure | null;
  if (!pair.registry_receipt_sha256 || !_SHA256_RE.test(pair.registry_receipt_sha256)) {
    capability_status = ComparisonStatus.UNAVAILABLE;
    capability_failure = ReconcileFailure.REGISTRY_UNAVAILABLE;
    differences.push('precedent_registry_receipt_missing');
  } else if (differences.length) {
    capability_status = ComparisonStatus.CONFLICT;
    capability_failure = ReconcileFailure.CAPABILITY_PRECEDENT_CONFLICT;
  } else {
    capability_status = ComparisonStatus.MATCH;
    capability_failure = null;
  }
  return [_comparison('capability_precedent_requirements', inputs.capability, inputs.precedent, capability_status, capability_failure, differences), _closure_comparison('precedent_bed_build', inputs.precedent, inputs.bed, pair.build_status, { conflict_failure: ReconcileFailure.BUILD_MISMATCH, unavailable_failure: ReconcileFailure.STALE_OBSERVATION, differences: pair.differences })];
}

function _reference_comparisons(inputs: AuthorityInputs): PairwiseComparison[] {
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  const manual = _manual_evidence(inputs);
  if (manual.status === EvidenceStatus.PRESENT) {
    return [_closure_comparison('manual_case_semantic', manual, case_ev, inputs.manual_case.semantic_status, { conflict_failure: ReconcileFailure.REFERENCE_CONFLICT, unavailable_failure: ReconcileFailure.REFERENCE_UNKNOWN, differences: inputs.manual_case.differences })];
  }
  if ([EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED].includes(manual.status)) {
    return [_comparison('manual_case_semantic', manual, case_ev, manual.status === EvidenceStatus.ABSENT ? ComparisonStatus.EXPLICIT_ABSENCE : ComparisonStatus.NOT_REQUIRED)];
  }
  return [_comparison('manual_case_semantic', manual, case_ev, ComparisonStatus.UNAVAILABLE, ReconcileFailure.REFERENCE_UNKNOWN, ['manual_reference_unavailable'])];
}

function _expected_source_comparisons(inputs: AuthorityInputs): PairwiseComparison[] {
  const case_ev = (inputs as any)['case_'] ?? (inputs as any)['case'];
  return [...inputs.source_claims].sort((a, b) => a.source_kind < b.source_kind ? -1 : 1).map((item) => _closure_comparison(`expected_source_claim:${item.source_kind}`, case_ev, case_ev, item.status, { conflict_failure: ReconcileFailure.EXPECTED_SOURCE_CONFLICT, unavailable_failure: ReconcileFailure.EXPECTED_SOURCE_UNKNOWN, differences: item.differences }));
}

function _build_comparisons(inputs: AuthorityInputs): PairwiseComparison[] {
  const comparisons = [..._expected_source_comparisons(inputs), ..._spec_case_comparisons(inputs), ..._case_capability_comparisons(inputs), ..._capability_precedent_comparisons(inputs), ..._reference_comparisons(inputs)];
  if (inputs.capability.build) {
    const status = inputs.capability.build === inputs.bed.build ? ComparisonStatus.MATCH : ComparisonStatus.CONFLICT;
    comparisons.push(_comparison('capability_bed_build', inputs.capability, inputs.bed, status, status === ComparisonStatus.MATCH ? null : ReconcileFailure.BUILD_MISMATCH, status === ComparisonStatus.MATCH ? [] : ['build:value_mismatch']));
  } else {
    comparisons.push(_comparison('capability_bed_build', inputs.capability, inputs.bed, ComparisonStatus.UNAVAILABLE, ReconcileFailure.CAPABILITY_UNKNOWN, ['product_capability_build_unavailable']));
  }
  return comparisons;
}

function _dedup_failures(items: ReconcileFailure[]): ReconcileFailure[] {
  return [...new Set(items)];
}

export const AUTHORITY_BLOCKING_FAILURES: Set<ReconcileFailure> = new Set([ReconcileFailure.MISSING_IDENTITY, ReconcileFailure.BUILD_MISMATCH, ReconcileFailure.SEMANTIC_CLOSURE_MISSING, ReconcileFailure.EXPECTED_SOURCE_UNKNOWN, ReconcileFailure.CAPABILITY_UNKNOWN, ReconcileFailure.STALE_OBSERVATION, ReconcileFailure.REFERENCE_IDENTITY_MISMATCH, ReconcileFailure.REFERENCE_UNKNOWN, ReconcileFailure.REGISTRY_UNAVAILABLE, ReconcileFailure.UNKNOWN]);

export function authority_state_for_failures(failures: ReconcileFailure[]): AuthorityState {
  if (failures.some((item) => !Object.values(ReconcileFailure).includes(item))) {
    throw new PyValueError('authority failure is outside the declared vocabulary');
  }
  if (failures.some((item) => AUTHORITY_BLOCKING_FAILURES.has(item))) {
    return AuthorityState.BLOCKED;
  }
  return failures.length ? AuthorityState.NEEDS_DECISION : AuthorityState.READY;
}

export function reconcile_authority(inputs: AuthorityInputs): AuthorityReceipt {
  const raw_inputs = _inputs_dict(inputs);
  const input_sha256 = canonical_sha256(raw_inputs);
  const idempotency_key = `${AUTHORITY_SCHEMA}:${input_sha256}`;
  const validation_failures = _validation_failures(inputs);
  let comparisons: PairwiseComparison[];
  try {
    comparisons = _build_comparisons(inputs);
  } catch (e) {
    if (e instanceof TypeError || e instanceof PyValueError || e instanceof Error) {
      comparisons = [];
      validation_failures.push(ReconcileFailure.UNKNOWN);
    } else {
      throw e;
    }
  }
  const comparison_failures = comparisons.filter((item) => item.failure !== null).map((item) => item.failure!);
  const failures = _dedup_failures([...validation_failures, ...comparison_failures]);
  const state = authority_state_for_failures(failures);
  const conflicts = comparisons.filter((item) => [ComparisonStatus.CONFLICT, ComparisonStatus.UNAVAILABLE].includes(item.status)).map((item) => item.comparison_id);
  const source_identities = _source_identities(inputs);
  const [spec_generation_id, spec_manifest_sha256] = _spec_generation_identity(inputs);
  const core: Record<string, any> = { 'schema': inputs.schema, 'input_sha256': input_sha256, 'idempotency_key': idempotency_key, 'state': state, 'binding': _binding_dict(inputs.binding), 'spec_generation_id': spec_generation_id, 'spec_manifest_sha256': spec_manifest_sha256, 'source_identities': source_identities.map(([l, s, i, b]) => ({ 'layer': l, 'status': s, 'identity': i, 'build': b })), 'comparisons': comparisons.map((item) => item.to_dict()), 'conflicts': [...conflicts], 'failures': failures.map((item) => item.valueOf()) };
  return new AuthorityReceipt({ schema: inputs.schema, input_sha256, idempotency_key, receipt_sha256: canonical_sha256(core), state, binding: inputs.binding, spec_generation_id, spec_manifest_sha256, source_identities, comparisons, conflicts, failures });
}

export function authority_fact(receipt: AuthorityReceipt): Record<string, any> {
  return { 'ev': 'authority_reconciled', 'aid': receipt.binding.autoid, 'idempotency_key': receipt.idempotency_key, 'receipt': receipt.to_dict() };
}

function _receipt_fact_matches(fact: Record<string, any>, receipt: AuthorityReceipt): boolean {
  return fact['ev'] === 'authority_reconciled' && fact['idempotency_key'] === receipt.idempotency_key && JSON.stringify(fact['receipt']) === JSON.stringify(receipt.to_dict());
}

export function append_fact_once(receipt: AuthorityReceipt, opts: { read_facts: FactReader; append_fact: FactAppender }): PersistenceResult {
  const { read_facts, append_fact } = opts;
  let existing: Record<string, any>[];
  try {
    existing = Array.from(read_facts());
  } catch (exc: any) {
    return new PersistenceResult(AuthorityState.BLOCKED, receipt, false, ReconcileFailure.REGISTRY_UNAVAILABLE, `read:${exc?.constructor?.name ?? 'Error'}`);
  }
  const same_key = existing.filter((item) => item['ev'] === 'authority_reconciled' && item['idempotency_key'] === receipt.idempotency_key);
  if (same_key.length) {
    if (same_key.every((item) => _receipt_fact_matches(item, receipt))) {
      return new PersistenceResult(receipt.state, receipt, false);
    }
    return new PersistenceResult(AuthorityState.BLOCKED, receipt, false, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'same idempotency key has different receipt content');
  }
  let after: Record<string, any>[];
  try {
    append_fact(authority_fact(receipt));
    after = Array.from(read_facts());
  } catch (exc: any) {
    return new PersistenceResult(AuthorityState.BLOCKED, receipt, false, ReconcileFailure.REGISTRY_UNAVAILABLE, `write_or_verify:${exc?.constructor?.name ?? 'Error'}`);
  }
  const verified = after.filter((item) => item['ev'] === 'authority_reconciled' && item['idempotency_key'] === receipt.idempotency_key);
  if (!verified.length) {
    return new PersistenceResult(AuthorityState.BLOCKED, receipt, false, ReconcileFailure.REGISTRY_UNAVAILABLE, 'receipt was not present after append');
  }
  if (!verified.every((item) => _receipt_fact_matches(item, receipt))) {
    return new PersistenceResult(AuthorityState.BLOCKED, receipt, false, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'same key acquired conflicting content during append');
  }
  return new PersistenceResult(receipt.state, receipt, true);
}

export function delivery_gate(claim: DeliveryClaim, receipt: AuthorityReceipt, opts: { read_facts: FactReader; projection_validator: BindingValidator; artifact_validator: BindingValidator }): GateVerdict {
  const { read_facts, projection_validator, artifact_validator } = opts;
  const claim_values = _binding_dict(claim.binding);
  const missing = Object.entries(claim_values).filter(([name, value]) => name !== 'consistency_contract_sha256' && !String(value).trim()).map(([name]) => name);
  const consistency_sha = claim_values['consistency_contract_sha256'];
  if (consistency_sha !== null && !_SHA256_RE.test(String(consistency_sha).toLowerCase())) {
    missing.push('consistency_contract_sha256');
  }
  if (!_SHA256_RE.test(claim.authority_receipt_sha256.toLowerCase())) {
    missing.push('authority_receipt_sha256');
  }
  if (missing.length) {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.MISSING_IDENTITY], [...new Set(missing)].sort());
  }
  const receipt_values = _binding_dict(receipt.binding);
  const mismatches = Object.keys(claim_values).filter((key) => JSON.stringify(claim_values[key]) !== JSON.stringify(receipt_values[key])).sort();
  if (claim.authority_receipt_sha256 !== receipt.receipt_sha256) {
    mismatches.push('authority_receipt_sha256');
  }
  const receipt_payload = receipt.to_dict();
  const receipt_without_sha: Record<string, any> = {};
  for (const [key, value] of Object.entries(receipt_payload)) {
    if (key !== 'receipt_sha256') receipt_without_sha[key] = value;
  }
  if (receipt.receipt_sha256 !== canonical_sha256(receipt_without_sha)) {
    mismatches.push('authority_receipt_sha256');
  }
  if (claim.spec_generation_id !== receipt.spec_generation_id) {
    mismatches.push('spec_generation_id');
  }
  if (claim.spec_manifest_sha256 !== receipt.spec_manifest_sha256) {
    mismatches.push('spec_manifest_sha256');
  }
  if (receipt.spec_generation_id && (!/^[0-9]{20}-[0-9a-f]{16}$/.test(claim.spec_generation_id) || !_SHA256_RE.test(claim.spec_manifest_sha256))) {
    mismatches.push('spec_generation_id', 'spec_manifest_sha256');
  }
  if (mismatches.length) {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.DELIVERY_IDENTITY_MISMATCH], [...new Set(mismatches)].sort());
  }
  let facts: Record<string, any>[];
  try {
    facts = Array.from(read_facts());
  } catch {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.REGISTRY_UNAVAILABLE]);
  }
  const matching = facts.filter((fact) => fact['ev'] === 'authority_reconciled' && fact['idempotency_key'] === receipt.idempotency_key);
  if (!matching.length) {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.REGISTRY_UNAVAILABLE]);
  }
  if (!matching.every((item) => _receipt_fact_matches(item, receipt))) {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.IDEMPOTENCY_CONFLICT]);
  }
  let projection_ok: any;
  try {
    projection_ok = projection_validator(claim.binding);
  } catch {
    projection_ok = false;
  }
  if (projection_ok !== true) {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.PROJECTION_INVALID]);
  }
  let artifact_ok: any;
  try {
    artifact_ok = artifact_validator(claim.binding);
  } catch {
    artifact_ok = false;
  }
  if (artifact_ok !== true) {
    return new GateVerdict(AuthorityState.BLOCKED, [ReconcileFailure.ARTIFACT_IDENTITY_MISMATCH]);
  }
  if (receipt.state !== AuthorityState.READY) {
    return new GateVerdict(receipt.state, [ReconcileFailure.AUTHORITY_NOT_READY]);
  }
  return new GateVerdict(AuthorityState.READY);
}
