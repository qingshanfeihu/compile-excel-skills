# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/authority_reconcile.py（sha256 a0e257c75fb775ee）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence
from cex_core.engine.common.schema_identity import accepts_schema
AUTHORITY_SCHEMA = 'ist.authority-reconcile'
_SHA256_RE = re.compile('[0-9a-f]{64}')

class AuthorityLayer(str, Enum):
    SPEC = 'spec'
    CASE = 'case'
    EXCEL = 'excel_dialect'
    CAPABILITY = 'capability_xml'
    PRECEDENT = 'precedent'
    MANUAL = 'manual_reference'
    BED = 'bed'

class AuthorityState(str, Enum):
    READY = 'ready'
    NEEDS_DECISION = 'needs_decision'
    BLOCKED = 'blocked'

class EvidenceStatus(str, Enum):
    PRESENT = 'present'
    ABSENT = 'absent'
    UNKNOWN = 'unknown'
    NOT_REFERENCED = 'not_referenced'
ManualStatus = EvidenceStatus

class RegistryStatus(str, Enum):
    AVAILABLE = 'available'
    UNAVAILABLE = 'unavailable'
    UNKNOWN = 'unknown'

class ClosureStatus(str, Enum):
    VERIFIED = 'verified'
    CONFLICT = 'conflict'
    UNAVAILABLE = 'unavailable'
    NOT_REQUIRED = 'not_required'

class ComparisonStatus(str, Enum):
    MATCH = 'match'
    CONFLICT = 'conflict'
    UNAVAILABLE = 'unavailable'
    EXPLICIT_ABSENCE = 'explicit_absence'
    NOT_REQUIRED = 'not_required'

class ReconcileFailure(str, Enum):
    MISSING_IDENTITY = 'missing_identity'
    BUILD_MISMATCH = 'build_mismatch'
    SPEC_CASE_CONFLICT = 'spec_case_conflict'
    CASE_CAPABILITY_CONFLICT = 'case_capability_conflict'
    CAPABILITY_PRECEDENT_CONFLICT = 'capability_precedent_conflict'
    SEMANTIC_CLOSURE_MISSING = 'semantic_closure_missing'
    SEMANTIC_BINDING_AMBIGUOUS = 'semantic_binding_ambiguous'
    SEMANTIC_SOURCE_DRIFT = 'semantic_source_drift'
    EXPECTED_SOURCE_CONFLICT = 'expected_source_conflict'
    EXPECTED_SOURCE_UNKNOWN = 'expected_source_unknown'
    CAPABILITY_UNKNOWN = 'capability_unknown'
    STALE_OBSERVATION = 'stale_observation'
    REFERENCE_IDENTITY_MISMATCH = 'reference_identity_mismatch'
    REFERENCE_CONFLICT = 'reference_conflict'
    REFERENCE_UNKNOWN = 'reference_unknown'
    REGISTRY_UNAVAILABLE = 'registry_unavailable'
    IDEMPOTENCY_CONFLICT = 'idempotency_conflict'
    PROJECTION_INVALID = 'projection_invalid'
    ARTIFACT_IDENTITY_MISMATCH = 'artifact_identity_mismatch'
    DELIVERY_IDENTITY_MISMATCH = 'delivery_identity_mismatch'
    AUTHORITY_NOT_READY = 'authority_not_ready'
    UNKNOWN = 'unknown'

class _ClaimOriginView:
    source_kind: str

    @property
    def authority_source(self) -> str:
        from cex_core.engine.case_compiler.provenance_ir import claim_authority_source
        return claim_authority_source(self.source_kind)

    @property
    def derivation(self) -> str:
        from cex_core.engine.case_compiler.provenance_ir import claim_derivation
        return claim_derivation(self.source_kind)

@dataclass(frozen=True)
class TypedExpectation(_ClaimOriginView):
    expectation_id: str
    semantic_key: str
    operator: str
    value: str
    source_kind: str
    source_locator: str

    def to_dict(self) -> dict[str, str]:
        return {'expectation_id': self.expectation_id, 'semantic_key': self.semantic_key, 'operator': self.operator, 'value': self.value, 'source_kind': self.source_kind, 'source_locator': self.source_locator}

@dataclass(frozen=True)
class ExpectedFacet(_ClaimOriginView):
    block_index: int
    assert_index: int | None
    output_ordinal: int
    operator: str
    value: str
    source_kind: str
    source_locator: str

    def to_dict(self) -> dict[str, Any]:
        return {'block_index': self.block_index, 'assert_index': self.assert_index, 'output_ordinal': self.output_ordinal, 'operator': self.operator, 'value': self.value, 'source_kind': self.source_kind, 'source_locator': self.source_locator}

@dataclass(frozen=True)
class FacetedExpectation:
    expectation_id: str
    semantic_key: str
    declaration_sha256: str
    mechanical_case_sha256: str
    facets: tuple[ExpectedFacet, ...]

    def ordered_facets(self) -> tuple[ExpectedFacet, ...]:
        return tuple(sorted(self.facets, key=lambda item: (item.block_index, -1 if item.assert_index is None else item.assert_index, item.output_ordinal)))

    def facet_id(self, facet: ExpectedFacet) -> str:
        return canonical_sha256({'expectation_id': self.expectation_id, 'semantic_key': self.semantic_key, 'declaration_sha256': self.declaration_sha256, 'mechanical_case_sha256': self.mechanical_case_sha256, 'block_index': facet.block_index, 'assert_index': facet.assert_index, 'output_ordinal': facet.output_ordinal})

    def to_dict(self) -> dict[str, Any]:
        return {'expectation_id': self.expectation_id, 'semantic_key': self.semantic_key, 'declaration_sha256': self.declaration_sha256, 'mechanical_case_sha256': self.mechanical_case_sha256, 'facets': [item.to_dict() for item in self.ordered_facets()]}

def _expected_facets(expected: TypedExpectation | FacetedExpectation) -> tuple:
    return expected.ordered_facets() if isinstance(expected, FacetedExpectation) else (expected,)

@dataclass(frozen=True)
class FinalAssertion(_ClaimOriginView):
    assertion_id: str
    semantic_key: str
    operator: str
    value: str
    source_kind: str
    source_locator: str
    expectation_id: str
    observation_ref: str

    def to_dict(self) -> dict[str, str]:
        return {'assertion_id': self.assertion_id, 'semantic_key': self.semantic_key, 'operator': self.operator, 'value': self.value, 'source_kind': self.source_kind, 'source_locator': self.source_locator, 'expectation_id': self.expectation_id, 'observation_ref': self.observation_ref}

@dataclass(frozen=True)
class ExpectedClaim(_ClaimOriginView):
    claim_id: str
    producer: str
    expectation_id: str
    semantic_key: str
    operator: str
    value: str
    source_kind: str
    source_locator: str

    def to_dict(self) -> dict[str, str]:
        return {'claim_id': self.claim_id, 'producer': self.producer, 'expectation_id': self.expectation_id, 'semantic_key': self.semantic_key, 'operator': self.operator, 'value': self.value, 'source_kind': self.source_kind, 'source_locator': self.source_locator}

@dataclass(frozen=True)
class SemanticBindingReceipt:
    autoid: str
    projection_receipt_sha256: str
    contract_sha256: str
    artifact_sha256: str
    binding_graph_sha256: str
    provenance_sha256: str
    expectations: tuple[TypedExpectation | FacetedExpectation, ...]
    assertions: tuple[FinalAssertion, ...]
    bindings: tuple[tuple[str, str], ...]
    status: ClosureStatus
    differences: tuple[str, ...]
    failures: tuple[ReconcileFailure, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {'schema': 'ist.expectation-assertion-binding', 'autoid': self.autoid, 'projection_receipt_sha256': self.projection_receipt_sha256, 'contract_sha256': self.contract_sha256, 'artifact_sha256': self.artifact_sha256, 'binding_graph_sha256': self.binding_graph_sha256, 'provenance_sha256': self.provenance_sha256, 'expectations': [item.to_dict() for item in self.expectations], 'assertions': [item.to_dict() for item in self.assertions], 'bindings': [{'expectation_id': left, 'assertion_id': right} for left, right in self.bindings], 'status': self.status.value, 'differences': list(self.differences), 'failures': [item.value for item in self.failures], 'receipt_sha256': self.receipt_sha256}

@dataclass(frozen=True)
class SemanticClosureResult:
    status: ClosureStatus
    receipt: SemanticBindingReceipt
    failures: tuple[ReconcileFailure, ...] = ()

@dataclass(frozen=True)
class ExpectedClaimReceipt:
    autoid: str
    semantic_binding_receipt_sha256: str
    projection_receipt_sha256: str
    contract_sha256: str
    artifact_sha256: str
    binding_graph_sha256: str
    provenance_sha256: str
    claims: tuple[ExpectedClaim, ...]
    status: ClosureStatus
    differences: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {'schema': 'ist.expected-source-claims', 'autoid': self.autoid, 'semantic_binding_receipt_sha256': self.semantic_binding_receipt_sha256, 'projection_receipt_sha256': self.projection_receipt_sha256, 'contract_sha256': self.contract_sha256, 'artifact_sha256': self.artifact_sha256, 'binding_graph_sha256': self.binding_graph_sha256, 'provenance_sha256': self.provenance_sha256, 'claims': [item.to_dict() for item in self.claims], 'status': self.status.value, 'differences': list(self.differences), 'receipt_sha256': self.receipt_sha256}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> 'ExpectedClaimReceipt':
        if not accepts_schema(raw.get('schema'), 'ist.expected-source-claims'):
            raise ValueError('expected claim receipt schema mismatch')
        try:
            claims = tuple((ExpectedClaim(**item) for item in raw['claims']))
            receipt = cls(autoid=str(raw['autoid']), semantic_binding_receipt_sha256=str(raw['semantic_binding_receipt_sha256']), projection_receipt_sha256=str(raw['projection_receipt_sha256']), contract_sha256=str(raw['contract_sha256']), artifact_sha256=str(raw['artifact_sha256']), binding_graph_sha256=str(raw['binding_graph_sha256']), provenance_sha256=str(raw['provenance_sha256']), claims=claims, status=ClosureStatus(str(raw['status'])), differences=tuple((str(item) for item in raw.get('differences') or ())), receipt_sha256=str(raw['receipt_sha256']))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('expected claim receipt is incomplete') from exc
        material = receipt.to_dict()
        material.pop('receipt_sha256', None)
        if canonical_sha256(material) != receipt.receipt_sha256:
            raise ValueError('expected claim receipt SHA mismatch')
        identity_values = (receipt.semantic_binding_receipt_sha256, receipt.projection_receipt_sha256, receipt.contract_sha256, receipt.artifact_sha256, receipt.binding_graph_sha256, receipt.provenance_sha256, receipt.receipt_sha256)
        if not receipt.autoid or any((not _SHA256_RE.fullmatch(value) for value in identity_values)):
            raise ValueError('expected claim receipt identity is incomplete')
        claim_ids = [item.claim_id for item in claims]

        def _claim_incomplete(item: 'ExpectedClaim') -> bool:
            required = [item.claim_id, item.expectation_id, item.semantic_key, item.operator, item.source_kind, item.source_locator]
            if expected_source_group(item.source_kind) != 'configbinding':
                required.append(item.value)
            return item.producer not in {'u1', 'u3'} or not all((str(value).strip() for value in required))
        if not claims or len(set(claim_ids)) != len(claim_ids) or any((_claim_incomplete(item) for item in claims)):
            raise ValueError('expected claim identities are incomplete or duplicated')
        if receipt.status in {ClosureStatus.VERIFIED, ClosureStatus.CONFLICT}:
            producers: dict[tuple[str, str], set[str]] = {}
            for item in claims:
                producers.setdefault((item.expectation_id, item.semantic_key), set()).add(item.producer)
            if any((value != {'u1', 'u3'} for value in producers.values())):
                raise ValueError('expected claim producer bijection is incomplete')
        return receipt

@dataclass(frozen=True)
class SourceClaimClosure:
    source_kind: str
    status: ClosureStatus
    receipt_sha256: str
    differences: tuple[str, ...] = ()
_EXPECTED_SOURCE_GROUPS = {'intent': 'author', 'author': 'author', 'spec': 'spec', 'defect_spec': 'spec', 'defectspec': 'spec', 'manual': 'manual', 'capability_xml': 'capability_xml', 'capabilityxml': 'capability_xml', 'config_derived': 'configbinding', 'captured_relation': 'configbinding', 'distribution_derived': 'configbinding', 'membership_derived': 'configbinding', 'configbinding': 'configbinding', 'status_derived': 'author'}

def expected_source_group(source_kind: str) -> str:
    return _EXPECTED_SOURCE_GROUPS.get(str(source_kind or '').strip().lower(), '')
_SOURCE_RANK = {'spec': 4, 'author': 3, 'capability_xml': 2, 'manual': 1}

def source_outranks(winner: str, loser: str) -> bool:
    winner_group = expected_source_group(winner) or str(winner or '').strip().lower()
    loser_group = expected_source_group(loser) or str(loser or '').strip().lower()
    high, low = (_SOURCE_RANK.get(winner_group), _SOURCE_RANK.get(loser_group))
    return high is not None and low is not None and (high > low)

def product_assertion_steps(steps: Sequence[Any], *, mutation_receipt: Mapping[str, Any] | None=None) -> list[Any]:
    from collections import Counter
    from cex_core.engine.case_compiler.provenance_ir import MUTATION_ROLE_CONTROL

    def _flip_evidence_ref(step: Any) -> str:
        assertion_type = getattr(step, 'assertion_type', None)
        if not isinstance(assertion_type, Mapping):
            return ''
        flip = assertion_type.get('flip')
        if not isinstance(flip, Mapping):
            return ''
        return str(flip.get('evidence_ref') or '')
    assertions = [step for step in steps if step.E.strip() == 'check_point']
    declared = [step for step in assertions if str(getattr(step, 'mutation_role', '') or '') == MUTATION_ROLE_CONTROL]
    if not declared:
        return assertions
    minted: Any = Counter((str(item.get('evidence_ref') or '') for item in (mutation_receipt.get('requirements') if isinstance(mutation_receipt, Mapping) else None) or () if isinstance(item, Mapping) and str(item.get('mode') or '') == 'in_case_serialized'))
    if not minted or '' in minted or Counter((_flip_evidence_ref(step) for step in declared)) != minted:
        return assertions
    return [step for step in assertions if str(getattr(step, 'mutation_role', '') or '') != MUTATION_ROLE_CONTROL]
_COMPOSITE_ASSERTION_KINDS = frozenset({'captured_relation', 'distribution_derived', 'membership_derived', 'status_derived'})

def _same_expected_source(expected: TypedExpectation, actual: FinalAssertion) -> bool:
    if expected.source_kind != actual.source_kind:
        return False
    if expected.source_kind in _COMPOSITE_ASSERTION_KINDS:
        return expected.source_locator == actual.source_locator or (expected.operator == actual.operator and expected.value == actual.value)
    return expected.source_locator == actual.source_locator

def _recomputed_composite_receipt(step: Any) -> tuple[dict[str, Any] | None, int, str]:
    from cex_core.engine.case_compiler.provenance_ir import build_config_binding_derivation_receipt, derivation_output_count, reconcile_config_binding_derivation_receipt
    source = getattr(step, 'source', None)
    kind = str(getattr(source, 'kind', '') or '')
    if kind not in _COMPOSITE_ASSERTION_KINDS:
        return (None, 0, 'source.kind is not a relation/composite assertion kind')
    supplied = getattr(source, 'receipt', None)
    if not isinstance(supplied, dict) or not supplied:
        return (None, 0, 'relation/composite assertion has no derivation receipt')
    source_input = supplied.get('source_input')
    if not isinstance(source_input, dict):
        return (None, 0, 'composite derivation source_input is missing')
    rule_id = str(supplied.get('rule_id') or '')
    rebuilt, error = build_config_binding_derivation_receipt(source_kind=kind, recipe_id=str(getattr(source, 'ref', '') or ''), rule_id=rule_id, source_input=source_input, output_step={'E': step.E, 'F': step.F, 'G': step.G}, output_ordinal=supplied.get('output_ordinal', 0))
    if rebuilt is None:
        return (None, 0, error)
    reconciled, reconcile_error = reconcile_config_binding_derivation_receipt(supplied, rebuilt)
    if reconciled is None:
        return (None, 0, reconcile_error)
    size, size_error = derivation_output_count(source_kind=kind, rule_id=rule_id, source_input=source_input)
    if size is None:
        return (None, 0, size_error)
    return (reconciled, size, '')

def _composite_assertion_groups_are_complete(steps: Sequence[Any]) -> bool:
    groups: dict[tuple[str, str, str, str], list[Any]] = {}
    sizes: dict[tuple[str, str, str, str], int] = {}
    for step in steps:
        source = getattr(step, 'source', None)
        kind = str(getattr(source, 'kind', '') or '')
        if kind not in _COMPOSITE_ASSERTION_KINDS:
            continue
        receipt, size, _error = _recomputed_composite_receipt(step)
        if receipt is None:
            return False
        identity = (kind, str(getattr(source, 'ref', '') or ''), str(receipt.get('rule_id') or ''), str(receipt.get('source_input_sha256') or ''))
        groups.setdefault(identity, []).append(receipt)
        if identity in sizes and sizes[identity] != size:
            return False
        sizes[identity] = size
    for identity, receipts in groups.items():
        ordinals = sorted((int(receipt.get('output_ordinal') or 0) for receipt in receipts))
        if len(receipts) != sizes[identity] or ordinals != list(range(sizes[identity])):
            return False
    return True

def author_fixture_policies_from_contract(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    policies: dict[str, dict[str, Any]] = {}
    for item in contract.get('expectations') or []:
        if not isinstance(item, Mapping):
            continue
        author_claim = item.get('author_claim')
        normalized_claim = item.get('normalized_claim')
        if not isinstance(author_claim, Mapping) or not isinstance(normalized_claim, Mapping):
            continue
        expectation_id = str(author_claim.get('expectation_id') or '').strip()
        policy = normalized_claim.get('fixture_policy')
        if expectation_id and normalized_claim.get('mode') == 'fixture_backref' and (str(normalized_claim.get('expectation_id') or '') == expectation_id) and isinstance(policy, Mapping):
            policies[expectation_id] = dict(policy)
    return policies

def _author_claim_is_compiled_form(step: Any, *, fixture_policy: Mapping[str, Any] | None=None) -> bool:
    source = getattr(step, 'source', None)
    kind = str(getattr(source, 'kind', '') or '')
    if kind == 'intent':
        return bool(str(getattr(source, 'ref', '') or '') == str(step.expectation_id or '') and step.G)
    if kind in _COMPOSITE_ASSERTION_KINDS:
        if not str(getattr(step, 'observation_ref', '') or '').strip():
            return False
        receipt, _size, _error = _recomputed_composite_receipt(step)
        return receipt is not None
    if kind == 'config_derived' and isinstance(fixture_policy, Mapping):
        allowed_kinds = fixture_policy.get('allowed_kinds')
        receipt = getattr(source, 'receipt', None)
        source_input = receipt.get('source_input') if isinstance(receipt, Mapping) else None
        fixture_kind = str(source_input.get('fixture_kind') if isinstance(source_input, Mapping) else '')
        fixture_value = source_input.get('value') if isinstance(source_input, Mapping) else None
        prefix = str(fixture_policy.get('value_prefix') or '')
        suffix = str(fixture_policy.get('domain_suffix') or '')
        safe_fixture_value = False
        if isinstance(fixture_value, str) and prefix:
            if fixture_kind == 'text_value':
                safe_fixture_value = bool(fixture_value.startswith(prefix) and re.fullmatch('[A-Za-z0-9._-]+', fixture_value))
            elif fixture_kind == 'domain_name' and suffix:
                safe_fixture_value = bool(fixture_value.startswith(prefix) and fixture_value.endswith(suffix) and re.fullmatch('[A-Za-z0-9.-]+', fixture_value))
        return bool(fixture_policy.get('expected_binding_rule') == 'config.fixture-literal-backref' and fixture_policy.get('disclosure_required') is True and isinstance(allowed_kinds, list) and all((isinstance(item, str) for item in allowed_kinds)) and (set(allowed_kinds) == {'domain_name', 'text_value'}) and (set(fixture_policy) == {'value_prefix', 'domain_suffix', 'allowed_kinds', 'expected_binding_rule', 'disclosure_required'}) and isinstance(receipt, Mapping) and (receipt.get('rule_id') == 'config.fixture-literal-backref') and (receipt.get('status') == 'compiler_recomputed') and isinstance(source_input, Mapping) and (fixture_kind in set(allowed_kinds)) and (source_input.get('operator') == step.F) and (fixture_value == step.G) and safe_fixture_value and step.G)
    return False

def _assertion_observation_instances(assertions: Sequence[Any], all_steps: Sequence[Any]) -> tuple[dict[int, tuple[str, int]], str]:
    """按已对齐步骤表定位生产者实例，不把命令文本或调用方自造引用当实例。

    与 assertion_binding.compile_binding 同口径：observation_id 优先，通道别名
    必须唯一。一个生产者的两种名字映射到同一行；同命令的不同生产行保持独立。
    """
    ids: dict[str, list[int]] = {}
    channels: dict[str, list[int]] = {}
    positions: dict[int, list[int]] = {}
    for index, step in enumerate(all_steps):
        positions.setdefault(id(step), []).append(index)
        if str(getattr(step, 'E', '') or '').strip() == 'check_point' or not str(getattr(step, 'observation_id', '') or '').strip():
            continue
        for field, mapping in (('observation_id', ids), ('result_channel', channels)):
            value = str(getattr(step, field, '') or '').strip()
            if value:
                mapping.setdefault(value, []).append(index)
    if any((len(indices) != 1 for indices in ids.values())):
        return ({}, 'duplicate observation_id')
    resolved: dict[int, tuple[str, int]] = {}
    for step in assertions:
        reference = str(getattr(step, 'observation_ref', '') or '').strip()
        if not reference:
            continue
        producers = ids.get(reference, channels.get(reference, []))
        if not producers:
            return ({}, 'undefined observation_ref')
        if len(producers) != 1:
            return ({}, 'ambiguous observation_ref')
        consumers = positions.get(id(step))
        if consumers is None:
            consumers = [index for index, candidate in enumerate(all_steps) if candidate == step]
        if len(consumers) != 1:
            return ({}, 'assertion is not uniquely located in all_steps')
        if producers[0] >= consumers[0]:
            return ({}, 'observation_ref is not defined before the assertion')
        resolved[id(step)] = ('observation-producer', producers[0])
    return (resolved, '')

def check_expectation_assertion_bijection(*, autoid: str, final_steps: Sequence[Any], all_steps: Sequence[Any] | None=None, stamped_expectations: Mapping[str, Any], stamped_author_claims: Mapping[str, Any] | None=None, stamped_defect_spec_claims: Mapping[str, Any] | None=None, stamped_author_fixture_policies: Mapping[str, Mapping[str, Any]] | None=None) -> str | None:
    stamped_author_claims = stamped_author_claims or {}
    stamped_defect_spec_claims = stamped_defect_spec_claims or {}
    stamped_author_fixture_policies = stamped_author_fixture_policies or {}
    contract_ids = [*(str(item) for item in stamped_expectations), *(str(item) for item in stamped_author_claims), *(str(item) for item in stamped_defect_spec_claims)]
    expected_ids = set(contract_ids)
    observed_groups: dict[str, list[Any]] = {}
    for step in final_steps:
        observed_groups.setdefault(str(step.expectation_id or ''), []).append(step)
    if '' in observed_groups or len(expected_ids) != len(contract_ids) or expected_ids != set(observed_groups):
        return f'error: final assertions have no explicit expectation_id bijection to the typed expectation contract for case {autoid}'
    observation_instances: dict[int, tuple[str, int]] = {}
    if all_steps is not None:
        observation_instances, observation_error = _assertion_observation_instances(final_steps, all_steps)
        if observation_error:
            return f'error: assertion observation binding is invalid for case {autoid}: {observation_error}'
    for expectation_id, group in observed_groups.items():
        signatures: set[tuple[Any, str, str]] = set()
        for step in group:
            observation_ref = str(getattr(step, 'observation_ref', '') or '').strip()
            source_kind = str(getattr(getattr(step, 'source', None), 'kind', '') or '')
            observation_key: Any = observation_instances.get(id(step), ('<composite-observation-ref>' if source_kind in _COMPOSITE_ASSERTION_KINDS else '<unresolved-observation-ref>', observation_ref, ''))
            signatures.add((observation_key, str(getattr(step, 'F', '') or ''), str(getattr(step, 'G', '') or '')))
        if len(signatures) != len(group):
            return f'error: assertions sharing expectation_id {expectation_id!r} do not differ in observation, operator, or expected value for case {autoid}'
    for step in final_steps:
        if step.expectation_id in stamped_author_claims:
            claim = stamped_author_claims[step.expectation_id]
            if step.semantic_key != str(claim.get('semantic_key') or '') or not step.F.strip() or (not _author_claim_is_compiled_form(step, fixture_policy=stamped_author_fixture_policies.get(step.expectation_id))):
                return f'error: pending Author claim was not compiled into a source-bound F/G assertion for case {autoid}'
            continue
        if step.expectation_id in stamped_defect_spec_claims:
            claim = stamped_defect_spec_claims[step.expectation_id]
            resolver_receipt = claim.get('resolver_receipt')
            current_resolver = {key: value for key, value in (step.source.receipt or {}).items() if key != 'defect_spec_compilation'}
            if step.semantic_key != str(claim.get('semantic_key') or '') or step.source.kind != 'defect_spec' or step.source.ref != str(claim.get('locator') or '') or (current_resolver != resolver_receipt) or (not step.F.strip()) or (not step.G):
                return f'error: pending DefectSpec claim was not compiled into a source-bound F/G assertion for case {autoid}'
            continue
        if step.expectation_id not in stamped_expectations:
            return f'error: final assertion does not map to a stamped expectation for case {autoid}'
        expected_assertion = stamped_expectations[step.expectation_id]
        expected_source = expected_assertion.get('source') or {}
        if step.semantic_key != str(expected_assertion.get('semantic_key') or ''):
            return f'error: final assertion semantic_key drifted from the typed expectation contract for case {autoid}'
        expected_group = expected_source_group(str(expected_source.get('kind') or ''))
        final_group = expected_source_group(step.source.kind)
        if not expected_group or not final_group:
            return f'error: final assertion source is outside the expected-source closure for case {autoid}'
        if expected_group == final_group:
            expected_tuple = (str(expected_assertion.get('operator') or ''), str(expected_assertion.get('value') or ''), str(expected_source.get('kind') or ''), str(expected_source.get('locator') or ''))
            final_tuple = (step.F, step.G, step.source.kind, step.source.ref)
            if expected_tuple != final_tuple:
                return f'error: final assertions are not a byte-exact bijection of the typed expectation contract for case {autoid}'
            if str(expected_source.get('kind') or '') == 'defect_spec' and {key: value for key, value in (step.source.receipt or {}).items() if key != 'defect_spec_compilation'} != expected_source.get('receipt'):
                return f'error: final DefectSpec resolver receipt drifted from the typed expectation contract for case {autoid}'
    for expectation_id, group in observed_groups.items():
        if not _composite_assertion_groups_are_complete(group):
            return f'error: relation/composite assertion expansion is incomplete for expectation_id {expectation_id!r} in case {autoid}'
    return None

@dataclass(frozen=True)
class AuthorityEvidence:
    layer: AuthorityLayer
    status: EvidenceStatus
    identity: str = ''
    build: str = ''
    locators: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})

@dataclass(frozen=True)
class SpecCaseComparison:
    locator_status: ClosureStatus
    semantic_status: ClosureStatus
    locator_receipt_sha256: str = ''
    semantic_receipt_sha256: str = ''
    differences: tuple[str, ...] = ()

@dataclass(frozen=True)
class ManualCaseComparison:
    semantic_status: ClosureStatus
    semantic_receipt_sha256: str = ''
    differences: tuple[str, ...] = ()

@dataclass(frozen=True)
class CaseCapabilityComparison:
    requirements: tuple[str, ...]
    enabled: tuple[str, ...]
    disabled: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    registry_receipt_sha256: str = ''

@dataclass(frozen=True)
class CapabilityPrecedentComparison:
    referenced_capabilities: tuple[str, ...] = ()
    precedent_capabilities: tuple[str, ...] = ()
    registry_receipt_sha256: str = ''
    build_status: ClosureStatus = ClosureStatus.NOT_REQUIRED
    differences: tuple[str, ...] = ()

@dataclass(frozen=True)
class ExecutionBinding:
    autoid: str
    projection_receipt_sha256: str
    projection_sha256: str
    artifact_sha256: str
    run_id: str
    dispatch_id: str
    batch_run_id: str
    bed_lease_id: str
    bed_build: str
    module: str
    consistency_contract_sha256: str | None = None

@dataclass(frozen=True)
class AuthorityInputs:
    binding: ExecutionBinding
    spec: AuthorityEvidence
    case: AuthorityEvidence
    excel: AuthorityEvidence
    capability: AuthorityEvidence
    precedent: AuthorityEvidence
    bed: AuthorityEvidence
    manual: AuthorityEvidence
    spec_case: SpecCaseComparison
    case_capability: CaseCapabilityComparison
    case_product_capability: CaseCapabilityComparison
    capability_precedent: CapabilityPrecedentComparison
    source_claims: tuple[SourceClaimClosure, ...]
    manual_case: ManualCaseComparison = ManualCaseComparison(semantic_status=ClosureStatus.NOT_REQUIRED)
    registry_status: RegistryStatus = RegistryStatus.AVAILABLE
    schema: str = AUTHORITY_SCHEMA

@dataclass(frozen=True)
class PairwiseComparison:
    comparison_id: str
    left: AuthorityLayer
    right: AuthorityLayer
    status: ComparisonStatus
    failure: ReconcileFailure | None
    left_identity: str
    right_identity: str
    differences: tuple[str, ...] = ()

    @property
    def is_conflict(self) -> bool:
        return self.status is ComparisonStatus.CONFLICT

    def to_dict(self) -> dict[str, Any]:
        return {'comparison_id': self.comparison_id, 'left': self.left.value, 'right': self.right.value, 'status': self.status.value, 'failure': self.failure.value if self.failure else None, 'left_identity': self.left_identity, 'right_identity': self.right_identity, 'differences': list(self.differences)}

@dataclass(frozen=True)
class AuthorityReceipt:
    schema: str
    input_sha256: str
    idempotency_key: str
    receipt_sha256: str
    state: AuthorityState
    binding: ExecutionBinding
    spec_generation_id: str
    spec_manifest_sha256: str
    source_identities: tuple[tuple[str, str, str, str], ...]
    comparisons: tuple[PairwiseComparison, ...]
    conflicts: tuple[str, ...]
    failures: tuple[ReconcileFailure, ...]

    def to_dict(self) -> dict[str, Any]:
        return {'schema': self.schema, 'input_sha256': self.input_sha256, 'idempotency_key': self.idempotency_key, 'receipt_sha256': self.receipt_sha256, 'state': self.state.value, 'binding': _binding_dict(self.binding), 'spec_generation_id': self.spec_generation_id, 'spec_manifest_sha256': self.spec_manifest_sha256, 'source_identities': [{'layer': layer, 'status': status, 'identity': identity, 'build': build} for layer, status, identity, build in self.source_identities], 'comparisons': [item.to_dict() for item in self.comparisons], 'conflicts': list(self.conflicts), 'failures': [item.value for item in self.failures]}

@dataclass(frozen=True)
class PersistenceResult:
    state: AuthorityState
    receipt: AuthorityReceipt
    persisted: bool
    failure: ReconcileFailure | None = None
    detail: str = ''

@dataclass(frozen=True)
class ExpectedClaimPersistenceResult:
    state: AuthorityState
    fact: Mapping[str, Any]
    persisted: bool
    failure: ReconcileFailure | None = None
    detail: str = ''

@dataclass(frozen=True)
class ExpectedAuthorityPreflight:
    state: AuthorityState
    claim_receipt_sha256: str
    source_claims: tuple[SourceClaimClosure, ...]
    resolved_conflicts: tuple[str, ...]
    unresolved_conflicts: tuple[str, ...]
    failures: tuple[ReconcileFailure, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {'schema': 'ist.expected-authority-preflight', 'state': self.state.value, 'claim_receipt_sha256': self.claim_receipt_sha256, 'source_claims': [{'source_kind': item.source_kind, 'status': item.status.value, 'receipt_sha256': item.receipt_sha256, 'differences': list(item.differences)} for item in self.source_claims], 'resolved_conflicts': list(self.resolved_conflicts), 'unresolved_conflicts': list(self.unresolved_conflicts), 'failures': [item.value for item in self.failures], 'receipt_sha256': self.receipt_sha256}

@dataclass(frozen=True)
class DeliveryClaim:
    binding: ExecutionBinding
    authority_receipt_sha256: str
    spec_generation_id: str = ''
    spec_manifest_sha256: str = ''

@dataclass(frozen=True)
class GateVerdict:
    state: AuthorityState
    failures: tuple[ReconcileFailure, ...] = ()
    mismatched_fields: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.state is AuthorityState.READY
FactReader = Callable[[], Sequence[Mapping[str, Any]]]
FactAppender = Callable[[Mapping[str, Any]], None]
BindingValidator = Callable[[ExecutionBinding], bool]

def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()

def reconcile_expectation_assertions(*, autoid: str, projection_receipt_sha256: str, contract_sha256: str, artifact_sha256: str, binding_graph_sha256: str, provenance_sha256: str, expectations: Sequence[TypedExpectation | FacetedExpectation], assertions: Sequence[FinalAssertion]) -> SemanticClosureResult:
    identity_fields = {'projection_receipt_sha256': projection_receipt_sha256, 'contract_sha256': contract_sha256, 'artifact_sha256': artifact_sha256, 'binding_graph_sha256': binding_graph_sha256, 'provenance_sha256': provenance_sha256}
    malformed = [name for name, value in identity_fields.items() if not _SHA256_RE.fullmatch(str(value or ''))]
    differences: list[str] = []
    failures: list[ReconcileFailure] = []
    if not autoid or malformed or (not expectations) or (not assertions):
        if malformed:
            differences.append('invalid_identity:' + ','.join(sorted(malformed)))
        if not expectations:
            differences.append('missing_typed_expectations')
        if not assertions:
            differences.append('missing_final_assertions')
        failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)

    def _complete_fields(item) -> bool:
        runtime_bound = expected_source_group(item.source_kind) == 'configbinding'
        required = [item.operator, item.source_kind, item.source_locator]
        if not runtime_bound:
            required.append(item.value)
        return all((str(value).strip() for value in required))

    def _complete_expected(item) -> bool:
        if not str(item.expectation_id).strip() or not str(item.semantic_key).strip():
            return False
        if isinstance(item, FacetedExpectation):
            if not _SHA256_RE.fullmatch(str(item.declaration_sha256)) or not _SHA256_RE.fullmatch(str(item.mechanical_case_sha256)) or (not item.facets):
                return False
            if any((type(facet.block_index) is not int or facet.block_index < 0 or (facet.assert_index is not None and (type(facet.assert_index) is not int or facet.assert_index < 0)) or (type(facet.output_ordinal) is not int) or (facet.output_ordinal < 0) for facet in item.facets)):
                return False
        return all((_complete_fields(facet) for facet in _expected_facets(item)))
    if any((not _complete_expected(item) for item in expectations)) or any((not _complete_fields(item) or not all((str(value).strip() for value in (item.assertion_id, item.expectation_id, item.semantic_key, item.observation_ref))) for item in assertions)):
        differences.append('incomplete_semantic_tuple')
        failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
    exp_ids = [item.expectation_id for item in expectations]
    assertion_ids = [item.assertion_id for item in assertions]
    if len(set(exp_ids)) != len(exp_ids) or len(set(assertion_ids)) != len(assertion_ids):
        differences.append('duplicate_semantic_identity')
        failures.append(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS)
    for expected in expectations:
        if isinstance(expected, FacetedExpectation):
            slots = [(facet.block_index, facet.assert_index, facet.output_ordinal) for facet in expected.facets]
            if len(set(slots)) != len(slots):
                differences.append(f'duplicate_facet_identity:{expected.expectation_id}')
                failures.append(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS)
            for coordinate in {(block, assertion) for block, assertion, _ in slots}:
                ordinals = sorted((ordinal for block, assertion, ordinal in slots if (block, assertion) == coordinate))
                if ordinals != list(range(len(ordinals))):
                    differences.append(f'incomplete_facet_identity:{expected.expectation_id}')
                    failures.append(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS)
    assertions_by_expectation: dict[str, list[FinalAssertion]] = {}
    for assertion in assertions:
        assertions_by_expectation.setdefault(assertion.expectation_id, []).append(assertion)
    for expectation_id, group in assertions_by_expectation.items():
        signatures = {(item.observation_ref, item.operator, item.value) for item in group}
        if len(signatures) != len(group):
            differences.append(f'duplicate_assertion_shape:{expectation_id}')
            failures.append(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS)
    bindings: list[tuple[str, str]] = []
    if not failures:
        remaining = {item.assertion_id: item for item in assertions}
        for expected in sorted(expectations, key=lambda item: item.expectation_id):
            candidates = sorted([item for item in remaining.values() if item.expectation_id == expected.expectation_id], key=lambda item: item.assertion_id)
            if not candidates:
                differences.append(f'unbound_expectation:{expected.expectation_id}')
                failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
                continue
            facets = _expected_facets(expected)
            expected_groups = {expected_source_group(facet.source_kind) for facet in facets}
            local: list[FinalAssertion] = []
            independent = False
            for actual in candidates:
                if actual.semantic_key != expected.semantic_key:
                    differences.append(f'semantic_key_drift:{expected.expectation_id}')
                    failures.append(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS)
                    del remaining[actual.assertion_id]
                    continue
                actual_group = expected_source_group(actual.source_kind)
                if '' in expected_groups or not actual_group:
                    differences.append(f'unsupported_source:{expected.expectation_id}')
                    failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
                    del remaining[actual.assertion_id]
                    continue
                if actual_group not in expected_groups:
                    independent = True
                    bindings.append((expected.expectation_id, actual.assertion_id))
                    del remaining[actual.assertion_id]
                    continue
                local.append(actual)
            eligible: dict[int, list[str]] = {}
            anchored: set[int] = set()
            by_group: dict[str, list[FinalAssertion]] = {}
            by_value: dict[tuple[str, str, str], list[FinalAssertion]] = {}
            for actual in local:
                group = expected_source_group(actual.source_kind)
                by_group.setdefault(group, []).append(actual)
                by_value.setdefault((group, actual.operator, actual.value), []).append(actual)
            for index, facet in enumerate(facets):
                group = expected_source_group(facet.source_kind)
                same_group = by_group.get(group, [])
                if not same_group:
                    if local and (not independent):
                        differences.append(f'unbound_facet:{expected.expectation_id}:{index}')
                        failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
                    continue
                exact = by_value.get((group, facet.operator, facet.value), [])
                if not exact:
                    explained = all((any((other != index and alternative.operator == actual.operator and (alternative.value == actual.value) and _same_expected_source(alternative, actual) for other, alternative in enumerate(facets))) for actual in same_group))
                    if explained:
                        differences.append(f'unbound_facet:{expected.expectation_id}:{index}')
                        failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
                    else:
                        differences.append(f'operator_or_value_conflict:{expected.expectation_id}')
                        failures.append(ReconcileFailure.EXPECTED_SOURCE_CONFLICT)
                    continue
                anchored.add(index)
                eligible[index] = [actual.assertion_id for actual in exact if _same_expected_source(facet, actual)]
                if not eligible[index]:
                    differences.append(f'source_drift:{expected.expectation_id}')
                    failures.append(ReconcileFailure.SEMANTIC_SOURCE_DRIFT)
            assigned: dict[str, int] = {}

            def assign(start: int) -> bool:
                pending = [start]
                parents: dict[int, tuple[int, str] | None] = {start: None}
                seen: set[str] = set()
                while pending:
                    index = pending.pop()
                    for assertion_id in eligible[index]:
                        if assertion_id in seen:
                            continue
                        seen.add(assertion_id)
                        if assertion_id not in assigned:
                            while True:
                                assigned[assertion_id] = index
                                parent = parents[index]
                                if parent is None:
                                    return True
                                index, assertion_id = parent
                        previous = assigned[assertion_id]
                        if previous not in parents:
                            parents[previous] = (index, assertion_id)
                            pending.append(previous)
                return False
            for index, matches in eligible.items():
                if matches and (not assign(index)):
                    differences.append(f'uncovered_facet:{expected.expectation_id}')
                    failures.append(ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS)
            for actual in local:
                group = expected_source_group(actual.source_kind)
                if not any((expected_source_group(facets[index].source_kind) == group for index in anchored)):
                    del remaining[actual.assertion_id]
                    continue
                same_source = {index for index, facet in enumerate(facets) if _same_expected_source(facet, actual)}
                if not same_source:
                    differences.append(f'source_drift:{expected.expectation_id}')
                    failures.append(ReconcileFailure.SEMANTIC_SOURCE_DRIFT)
                    del remaining[actual.assertion_id]
                    continue
                if same_source & anchored:
                    bindings.append((expected.expectation_id, actual.assertion_id))
                del remaining[actual.assertion_id]
        if remaining:
            differences.extend((f'unbound_assertion:{assertion_id}' for assertion_id in sorted(remaining)))
            failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
    unique_failures = tuple(dict.fromkeys(failures))
    if ReconcileFailure.EXPECTED_SOURCE_CONFLICT in unique_failures and (not any((item in unique_failures for item in (ReconcileFailure.SEMANTIC_CLOSURE_MISSING, ReconcileFailure.SEMANTIC_BINDING_AMBIGUOUS, ReconcileFailure.SEMANTIC_SOURCE_DRIFT)))):
        status = ClosureStatus.CONFLICT
    elif unique_failures:
        status = ClosureStatus.UNAVAILABLE
    else:
        status = ClosureStatus.VERIFIED
    material = {'schema': 'ist.expectation-assertion-binding', 'autoid': autoid, **identity_fields, 'expectations': [item.to_dict() for item in sorted(expectations, key=lambda x: x.expectation_id)], 'assertions': [item.to_dict() for item in sorted(assertions, key=lambda x: x.assertion_id)], 'bindings': [{'expectation_id': left, 'assertion_id': right} for left, right in sorted(bindings)], 'status': status.value, 'differences': sorted(set(differences)), 'failures': [item.value for item in unique_failures]}
    receipt = SemanticBindingReceipt(autoid=autoid, projection_receipt_sha256=projection_receipt_sha256, contract_sha256=contract_sha256, artifact_sha256=artifact_sha256, binding_graph_sha256=binding_graph_sha256, provenance_sha256=provenance_sha256, expectations=tuple(sorted(expectations, key=lambda x: x.expectation_id)), assertions=tuple(sorted(assertions, key=lambda x: x.assertion_id)), bindings=tuple(sorted(bindings)), status=status, differences=tuple(material['differences']), failures=unique_failures, receipt_sha256=canonical_sha256(material))
    return SemanticClosureResult(status=status, receipt=receipt, failures=unique_failures)

def produce_expected_claim_receipt(semantic_closure: SemanticClosureResult) -> ExpectedClaimReceipt:
    binding = semantic_closure.receipt
    differences: list[str] = []
    if binding.status is not ClosureStatus.VERIFIED:
        differences.extend(binding.differences or ('semantic_binding_unavailable',))
        status = binding.status
    else:
        status = ClosureStatus.VERIFIED
    claims: list[ExpectedClaim] = [ExpectedClaim(claim_id=f'u1:{item.expectation_id}:facet:{item.facet_id(facet)}' if isinstance(item, FacetedExpectation) else f'u1:{item.expectation_id}', producer='u1', expectation_id=item.expectation_id, semantic_key=item.semantic_key, operator=facet.operator, value=facet.value, source_kind=facet.source_kind, source_locator=facet.source_locator) for item in binding.expectations for facet in _expected_facets(item)]
    for assertion in binding.assertions:
        claims.append(ExpectedClaim(claim_id=f'u3:{assertion.assertion_id}', producer='u3', expectation_id=assertion.expectation_id, semantic_key=assertion.semantic_key, operator=assertion.operator, value=assertion.value, source_kind=assertion.source_kind, source_locator=assertion.source_locator))
    claim_ids = [item.claim_id for item in claims]
    if len(set(claim_ids)) != len(claim_ids):
        differences.append('duplicate_expected_claim_identity')
        status = ClosureStatus.UNAVAILABLE
    unsupported = sorted({item.source_kind for item in claims if not expected_source_group(item.source_kind)})
    if unsupported:
        differences.extend((f'unsupported_expected_source:{item}' for item in unsupported))
        status = ClosureStatus.UNAVAILABLE
    ordered = tuple(sorted(claims, key=lambda item: item.claim_id))
    material = {'schema': 'ist.expected-source-claims', 'autoid': binding.autoid, 'semantic_binding_receipt_sha256': binding.receipt_sha256, 'projection_receipt_sha256': binding.projection_receipt_sha256, 'contract_sha256': binding.contract_sha256, 'artifact_sha256': binding.artifact_sha256, 'binding_graph_sha256': binding.binding_graph_sha256, 'provenance_sha256': binding.provenance_sha256, 'claims': [item.to_dict() for item in ordered], 'status': status.value, 'differences': sorted(set(differences))}
    return ExpectedClaimReceipt(autoid=binding.autoid, semantic_binding_receipt_sha256=binding.receipt_sha256, projection_receipt_sha256=binding.projection_receipt_sha256, contract_sha256=binding.contract_sha256, artifact_sha256=binding.artifact_sha256, binding_graph_sha256=binding.binding_graph_sha256, provenance_sha256=binding.provenance_sha256, claims=ordered, status=status, differences=tuple(material['differences']), receipt_sha256=canonical_sha256(material))
CLAIM_CONFLICT_BOTH_TRUE_PREFIX = 'claim_conflict_both_true_release:'

def _assertion_claim_proven(operator: str, value: str, assertion_rows: Sequence[Mapping[str, Any]]) -> bool:
    """一条 (operator, value) 断言有没有被框架逐条结果行证明成立。

    只认 ``window_audit.assertion_result_rows`` 切出的执行点结果行：判定词方向与
    operator 语义对上（found/abs_found ↔ successed to find，not_found ↔ fail to
    find）、pattern 逐字相等、回显窗非空（空窗的 not_found 是空转，不算证据）。
    存在同 pattern 的反方向 ``Fail`` 行＝同一断言被反证过，一票否掉（fail-closed）。
    不认识的算子或空值一律不证——不放行。
    """
    if operator in ('found', 'abs_found'):
        hold, contradict = ('successed to find', 'fail to find')
    elif operator == 'not_found':
        hold, contradict = ('fail to find', 'successed to find')
    else:
        return False
    if not str(value).strip():
        return False
    proven = False
    for row in assertion_rows:
        if str(row.get('pattern') or '') != value:
            continue
        judgment = str(row.get('judgment') or '')
        if str(row.get('outcome') or '') == 'Fail' and judgment == contradict:
            return False
        if str(row.get('outcome') or '') == 'Success' and judgment == hold and bool(row.get('window_non_empty')):
            proven = True
    return proven

def claim_conflict_both_true(*, claims: Sequence[ExpectedClaim], semantic_key: str, left: str, right: str, assertion_rows: Sequence[Mapping[str, Any]]) -> bool:
    """``claim_conflict`` 两边来源的**每一条** (operator, value) 是否都被逐条证明成立。

    逐条核对，不看整案通过；任一断言缺结果行即 False（维持待裁）。
    """
    needed = {(item.operator, item.value) for item in claims if item.semantic_key == semantic_key and expected_source_group(item.source_kind) in {left, right}}
    return bool(needed) and all((_assertion_claim_proven(operator, value, assertion_rows) for operator, value in needed))

def reconcile_source_claims(*, claim_receipt: ExpectedClaimReceipt, source_kind: str, assertion_rows: Sequence[Mapping[str, Any]] | None=None) -> SourceClaimClosure:
    kind = expected_source_group(source_kind)
    differences: list[str] = []
    if not kind:
        differences.append('source_kind_missing')
    if claim_receipt.status is ClosureStatus.CONFLICT:
        differences.extend(claim_receipt.differences or ('claim_receipt_conflict',))
        status = ClosureStatus.CONFLICT
    elif claim_receipt.status is not ClosureStatus.VERIFIED:
        differences.extend(claim_receipt.differences or ('claim_receipt_unavailable',))
        status = ClosureStatus.UNAVAILABLE
    else:
        by_key: dict[str, dict[str, set[tuple[str, str]]]] = {}
        unsupported: set[str] = set()
        for item in claim_receipt.claims:
            group = expected_source_group(item.source_kind)
            if not group:
                unsupported.add(str(item.source_kind or 'unknown'))
                continue
            by_source = by_key.setdefault(item.semantic_key, {})
            by_source.setdefault(group, set()).add((item.operator, item.value))
        if unsupported:
            differences.extend((f'unsupported_expected_source:{item}' for item in sorted(unsupported)))
            status = ClosureStatus.UNAVAILABLE
        else:
            source_keys = sorted((key for key, claims in by_key.items() if kind in claims))
        if not unsupported and (not source_keys):
            differences.append(f"typed_source_claim_missing:{kind or 'unknown'}")
            status = ClosureStatus.UNAVAILABLE
        elif not unsupported:
            unresolved: list[str] = []
            resolved: list[str] = []
            released: list[str] = []
            for semantic_key in source_keys:
                source_claims = by_key[semantic_key][kind]
                for other_kind, other_claims in sorted(by_key[semantic_key].items()):
                    if other_kind == kind:
                        continue
                    if source_claims != other_claims:
                        if source_outranks(kind, other_kind):
                            winner, loser = (kind, other_kind)
                        elif source_outranks(other_kind, kind):
                            winner, loser = (other_kind, kind)
                        elif assertion_rows is not None and 'configbinding' in {kind, other_kind} and claim_conflict_both_true(claims=claim_receipt.claims, semantic_key=semantic_key, left=kind, right=other_kind, assertion_rows=assertion_rows):
                            released.append(f'{CLAIM_CONFLICT_BOTH_TRUE_PREFIX}{semantic_key}:{kind}:{other_kind}')
                            continue
                        else:
                            unresolved.append(f'claim_conflict:{semantic_key}:{kind}:{other_kind}')
                            continue
                        resolved.append(f'authority_resolution:{semantic_key}:{winner}:{loser}')
            differences.extend(sorted(set([*resolved, *released, *unresolved])))
            status = ClosureStatus.CONFLICT if unresolved else ClosureStatus.VERIFIED
    material = {'schema': 'ist.source-claim-closure', 'claim_receipt_sha256': claim_receipt.receipt_sha256, 'source_kind': kind, 'status': status.value, 'differences': sorted(set(differences))}
    return SourceClaimClosure(source_kind=kind, status=status, receipt_sha256=canonical_sha256(material), differences=tuple(material['differences']))
_EXPECTED_SOURCE_ORDER = ('author', 'spec', 'capability_xml', 'manual', 'configbinding')

def _not_referenced_source_closure(claim_receipt: ExpectedClaimReceipt, source_kind: str) -> SourceClaimClosure:
    material = {'schema': 'ist.source-claim-closure', 'claim_receipt_sha256': claim_receipt.receipt_sha256, 'source_kind': source_kind, 'status': ClosureStatus.NOT_REQUIRED.value, 'differences': ['not_referenced']}
    return SourceClaimClosure(source_kind=source_kind, status=ClosureStatus.NOT_REQUIRED, receipt_sha256=canonical_sha256(material), differences=('not_referenced',))

def expected_claim_fact(claim_receipt: ExpectedClaimReceipt, source_claims: Sequence[SourceClaimClosure]) -> dict[str, Any]:
    try:
        ExpectedClaimReceipt.from_dict(claim_receipt.to_dict())
        receipt_invalid = False
    except ValueError:
        receipt_invalid = True
    supplied = {item.source_kind: item for item in source_claims}
    closure_invalid = len(supplied) != len(source_claims) or any((kind not in _EXPECTED_SOURCE_ORDER for kind in supplied)) or any((not _SHA256_RE.fullmatch(item.receipt_sha256) for item in source_claims))
    closures = tuple((supplied.get(kind) or _not_referenced_source_closure(claim_receipt, kind) for kind in _EXPECTED_SOURCE_ORDER))
    differences = sorted({difference for item in closures for difference in item.differences if difference != 'not_referenced'} | set(claim_receipt.differences))
    statuses = {item.status for item in closures}
    if receipt_invalid or closure_invalid or claim_receipt.status is ClosureStatus.UNAVAILABLE or (ClosureStatus.UNAVAILABLE in statuses):
        state = AuthorityState.BLOCKED
        if receipt_invalid:
            differences.append('expected_claim_receipt_invalid')
        if closure_invalid:
            differences.append('source_closure_identity_invalid')
    elif claim_receipt.status is ClosureStatus.CONFLICT or ClosureStatus.CONFLICT in statuses:
        state = AuthorityState.NEEDS_DECISION
    else:
        state = AuthorityState.READY
    differences = sorted(set(differences))
    idempotency_key = ':'.join(('ist.expected-source-claims-bound', claim_receipt.autoid, claim_receipt.artifact_sha256, claim_receipt.semantic_binding_receipt_sha256))
    return {'ev': 'expected_source_claims_bound', 'aid': claim_receipt.autoid, 'artifact_sha256': claim_receipt.artifact_sha256, 'idempotency_key': idempotency_key, 'semantic_binding_receipt_sha256': claim_receipt.semantic_binding_receipt_sha256, 'claim_receipt_sha256': claim_receipt.receipt_sha256, 'claim_receipt': claim_receipt.to_dict(), 'source_closures': {item.source_kind: {'status': item.status.value, 'receipt_sha256': item.receipt_sha256, 'differences': list(item.differences)} for item in closures}, 'status': state.value, 'differences': differences}

def reconcile_expected_authority_preflight(claim_receipt: ExpectedClaimReceipt) -> ExpectedAuthorityPreflight:
    try:
        verified = ExpectedClaimReceipt.from_dict(claim_receipt.to_dict())
        receipt_valid = True
    except ValueError:
        verified = claim_receipt
        receipt_valid = False
    referenced_groups = {expected_source_group(item.source_kind) for item in verified.claims if expected_source_group(item.source_kind)}
    closures = tuple((reconcile_source_claims(claim_receipt=verified, source_kind=source_kind) if source_kind in referenced_groups else _not_referenced_source_closure(verified, source_kind) for source_kind in _EXPECTED_SOURCE_ORDER))
    fact = expected_claim_fact(verified, closures)
    state = AuthorityState(str(fact['status']))
    resolved = tuple(sorted({item for closure in closures for item in closure.differences if item.startswith('authority_resolution:')}))
    unresolved = tuple(sorted({item for closure in closures for item in closure.differences if item.startswith('claim_conflict:')}))
    failures: list[ReconcileFailure] = []
    if not receipt_valid or state is AuthorityState.BLOCKED:
        failures.append(ReconcileFailure.EXPECTED_SOURCE_UNKNOWN)
        state = AuthorityState.BLOCKED
    elif state is AuthorityState.NEEDS_DECISION:
        failures.append(ReconcileFailure.EXPECTED_SOURCE_CONFLICT)
    material = {'schema': 'ist.expected-authority-preflight', 'state': state.value, 'claim_receipt_sha256': verified.receipt_sha256, 'source_claims': [{'source_kind': item.source_kind, 'status': item.status.value, 'receipt_sha256': item.receipt_sha256, 'differences': list(item.differences)} for item in closures], 'resolved_conflicts': list(resolved), 'unresolved_conflicts': list(unresolved), 'failures': [item.value for item in failures]}
    return ExpectedAuthorityPreflight(state=state, claim_receipt_sha256=verified.receipt_sha256, source_claims=closures, resolved_conflicts=resolved, unresolved_conflicts=unresolved, failures=tuple(failures), receipt_sha256=canonical_sha256(material))

def append_expected_claim_fact_once(claim_receipt: ExpectedClaimReceipt, source_claims: Sequence[SourceClaimClosure], *, read_facts: FactReader, append_fact: FactAppender) -> ExpectedClaimPersistenceResult:
    fact = expected_claim_fact(claim_receipt, source_claims)
    try:
        existing = list(read_facts())
    except Exception as exc:
        return ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, False, ReconcileFailure.REGISTRY_UNAVAILABLE, f'read:{type(exc).__name__}')

    def _matches(item: Mapping[str, Any]) -> bool:
        return {key: value for key, value in item.items() if key != '_pid'} == fact
    same_key = [item for item in existing if item.get('ev') == fact['ev'] and item.get('idempotency_key') == fact['idempotency_key']]
    if same_key:
        if all((_matches(item) for item in same_key)):
            return ExpectedClaimPersistenceResult(AuthorityState(str(fact['status'])), fact, False)
        return ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, False, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'same claim binding key has different content')
    try:
        append_fact(fact)
        persisted = list(read_facts())
    except Exception as exc:
        return ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, False, ReconcileFailure.REGISTRY_UNAVAILABLE, f'write_or_verify:{type(exc).__name__}')
    matches = [item for item in persisted if item.get('ev') == fact['ev'] and item.get('idempotency_key') == fact['idempotency_key']]
    if not matches or not all((_matches(item) for item in matches)):
        return ExpectedClaimPersistenceResult(AuthorityState.BLOCKED, fact, False, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'claim fact readback mismatch')
    return ExpectedClaimPersistenceResult(AuthorityState(str(fact['status'])), fact, True)

def _binding_dict(binding: ExecutionBinding) -> dict[str, Any]:
    return {'autoid': binding.autoid, 'projection_receipt_sha256': binding.projection_receipt_sha256, 'projection_sha256': binding.projection_sha256, 'artifact_sha256': binding.artifact_sha256, 'run_id': binding.run_id, 'dispatch_id': binding.dispatch_id, 'batch_run_id': binding.batch_run_id, 'bed_lease_id': binding.bed_lease_id, 'bed_build': binding.bed_build, 'module': binding.module, 'consistency_contract_sha256': binding.consistency_contract_sha256}

def _evidence_dict(evidence: AuthorityEvidence) -> dict[str, Any]:
    return {'layer': evidence.layer.value, 'status': evidence.status.value, 'identity': evidence.identity, 'build': evidence.build, 'locators': list(evidence.locators), 'metadata': dict(evidence.metadata)}

def _manual_evidence(inputs: AuthorityInputs) -> AuthorityEvidence:
    return inputs.manual

def _spec_generation_identity(inputs: AuthorityInputs) -> tuple[str, str]:
    if inputs.spec.status is not EvidenceStatus.PRESENT:
        return ('', '')
    metadata = inputs.spec.metadata
    return (str(metadata.get('generation_id') or ''), str(metadata.get('manifest_sha256') or ''))

def _inputs_dict(inputs: AuthorityInputs) -> dict[str, Any]:
    return {'schema': inputs.schema, 'binding': _binding_dict(inputs.binding), 'spec': _evidence_dict(inputs.spec), 'case': _evidence_dict(inputs.case), 'excel': _evidence_dict(inputs.excel), 'capability': _evidence_dict(inputs.capability), 'precedent': _evidence_dict(inputs.precedent), 'manual': _evidence_dict(_manual_evidence(inputs)), 'bed': _evidence_dict(inputs.bed), 'spec_case': {'locator_status': inputs.spec_case.locator_status.value, 'semantic_status': inputs.spec_case.semantic_status.value, 'locator_receipt_sha256': inputs.spec_case.locator_receipt_sha256, 'semantic_receipt_sha256': inputs.spec_case.semantic_receipt_sha256, 'differences': list(inputs.spec_case.differences)}, 'manual_case': {'semantic_status': inputs.manual_case.semantic_status.value, 'semantic_receipt_sha256': inputs.manual_case.semantic_receipt_sha256, 'differences': list(inputs.manual_case.differences)}, 'source_claims': [{'source_kind': item.source_kind, 'status': item.status.value, 'receipt_sha256': item.receipt_sha256, 'differences': list(item.differences)} for item in sorted(inputs.source_claims, key=lambda item: item.source_kind)], 'case_capability': {'requirements': list(inputs.case_capability.requirements), 'enabled': list(inputs.case_capability.enabled), 'disabled': list(inputs.case_capability.disabled), 'unknown': list(inputs.case_capability.unknown), 'registry_receipt_sha256': inputs.case_capability.registry_receipt_sha256}, 'case_product_capability': {'requirements': list(inputs.case_product_capability.requirements), 'enabled': list(inputs.case_product_capability.enabled), 'disabled': list(inputs.case_product_capability.disabled), 'unknown': list(inputs.case_product_capability.unknown), 'registry_receipt_sha256': inputs.case_product_capability.registry_receipt_sha256}, 'capability_precedent': {'referenced_capabilities': list(inputs.capability_precedent.referenced_capabilities), 'precedent_capabilities': list(inputs.capability_precedent.precedent_capabilities), 'registry_receipt_sha256': inputs.capability_precedent.registry_receipt_sha256, 'build_status': inputs.capability_precedent.build_status.value, 'differences': list(inputs.capability_precedent.differences)}, 'registry_status': inputs.registry_status.value}

def _source_identities(inputs: AuthorityInputs) -> tuple[tuple[str, str, str, str], ...]:
    evidence = [inputs.spec, inputs.case, inputs.excel, inputs.capability, inputs.precedent, _manual_evidence(inputs), inputs.bed]
    return tuple(((item.layer.value, item.status.value, item.identity, item.build) for item in evidence))

def _comparison(comparison_id: str, left: AuthorityEvidence, right: AuthorityEvidence, status: ComparisonStatus, failure: ReconcileFailure | None=None, differences: Sequence[str]=()) -> PairwiseComparison:
    return PairwiseComparison(comparison_id=comparison_id, left=left.layer, right=right.layer, status=status, failure=failure, left_identity=left.identity or left.status.value, right_identity=right.identity or right.status.value, differences=tuple(differences))

def _closure_comparison(comparison_id: str, left: AuthorityEvidence, right: AuthorityEvidence, closure: ClosureStatus, *, conflict_failure: ReconcileFailure, unavailable_failure: ReconcileFailure, differences: Sequence[str]=()) -> PairwiseComparison:
    if closure is ClosureStatus.VERIFIED:
        return _comparison(comparison_id, left, right, ComparisonStatus.MATCH, differences=differences)
    if closure is ClosureStatus.CONFLICT:
        return _comparison(comparison_id, left, right, ComparisonStatus.CONFLICT, conflict_failure, differences or ('typed_pair_conflict',))
    if closure is ClosureStatus.NOT_REQUIRED:
        return _comparison(comparison_id, left, right, ComparisonStatus.NOT_REQUIRED)
    return _comparison(comparison_id, left, right, ComparisonStatus.UNAVAILABLE, unavailable_failure, differences or ('typed_pair_evidence_unavailable',))

def _validation_failures(inputs: AuthorityInputs) -> list[ReconcileFailure]:
    failures: list[ReconcileFailure] = []
    binding = _binding_dict(inputs.binding)
    required_binding = {key: value for key, value in binding.items() if key != 'consistency_contract_sha256'}
    if any((not str(value).strip() for value in required_binding.values())):
        failures.append(ReconcileFailure.MISSING_IDENTITY)
    for field in ('projection_receipt_sha256', 'projection_sha256', 'artifact_sha256'):
        if not _SHA256_RE.fullmatch(str(binding[field]).lower()):
            failures.append(ReconcileFailure.MISSING_IDENTITY)
    consistency_sha = binding['consistency_contract_sha256']
    if consistency_sha is not None and (not _SHA256_RE.fullmatch(str(consistency_sha).lower())):
        failures.append(ReconcileFailure.MISSING_IDENTITY)
    expected_layers = ((inputs.spec, AuthorityLayer.SPEC), (inputs.case, AuthorityLayer.CASE), (inputs.excel, AuthorityLayer.EXCEL), (inputs.capability, AuthorityLayer.CAPABILITY), (inputs.precedent, AuthorityLayer.PRECEDENT), (_manual_evidence(inputs), AuthorityLayer.MANUAL), (inputs.bed, AuthorityLayer.BED))
    for evidence, layer in expected_layers:
        if evidence.layer is not layer:
            failures.append(ReconcileFailure.MISSING_IDENTITY)
            continue
        if evidence.status is EvidenceStatus.PRESENT and (not evidence.identity.strip()):
            failures.append(ReconcileFailure.MISSING_IDENTITY)
        if evidence.status in {EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED} and (evidence.identity.strip() or evidence.build.strip() or evidence.locators):
            failures.append(ReconcileFailure.MISSING_IDENTITY)
    if inputs.case.status is not EvidenceStatus.PRESENT:
        failures.append(ReconcileFailure.MISSING_IDENTITY)
    if inputs.excel.status is not EvidenceStatus.PRESENT:
        failures.append(ReconcileFailure.REGISTRY_UNAVAILABLE)
    if inputs.capability.status is not EvidenceStatus.PRESENT:
        failures.append(ReconcileFailure.CAPABILITY_UNKNOWN)
    if inputs.bed.status is not EvidenceStatus.PRESENT or not inputs.bed.build.strip():
        failures.append(ReconcileFailure.MISSING_IDENTITY)
    if inputs.spec.status is EvidenceStatus.UNKNOWN:
        failures.append(ReconcileFailure.REFERENCE_UNKNOWN)
    spec_generation_id, spec_manifest_sha256 = _spec_generation_identity(inputs)
    if inputs.spec.status is EvidenceStatus.PRESENT and (re.fullmatch('[0-9]{20}-[0-9a-f]{16}', spec_generation_id) is None or _SHA256_RE.fullmatch(spec_manifest_sha256) is None):
        failures.append(ReconcileFailure.MISSING_IDENTITY)
    if inputs.precedent.status is EvidenceStatus.UNKNOWN:
        failures.append(ReconcileFailure.STALE_OBSERVATION)
    if _manual_evidence(inputs).status is EvidenceStatus.UNKNOWN:
        failures.append(ReconcileFailure.REFERENCE_UNKNOWN)
    if inputs.precedent.status is EvidenceStatus.PRESENT and (not inputs.precedent.build.strip() or not inputs.precedent.locators):
        failures.append(ReconcileFailure.STALE_OBSERVATION)
    if inputs.schema != AUTHORITY_SCHEMA:
        failures.append(ReconcileFailure.MISSING_IDENTITY)
    if inputs.registry_status is RegistryStatus.UNAVAILABLE:
        failures.append(ReconcileFailure.REGISTRY_UNAVAILABLE)
    elif inputs.registry_status is RegistryStatus.UNKNOWN:
        failures.append(ReconcileFailure.UNKNOWN)
    if not inputs.source_claims:
        failures.append(ReconcileFailure.SEMANTIC_CLOSURE_MISSING)
    source_groups = [item.source_kind for item in inputs.source_claims]
    if len(source_groups) != len(set(source_groups)) or any((group not in set(_EXPECTED_SOURCE_ORDER) for group in source_groups)) or any((not _SHA256_RE.fullmatch(item.receipt_sha256) for item in inputs.source_claims)):
        failures.append(ReconcileFailure.EXPECTED_SOURCE_UNKNOWN)
    return list(dict.fromkeys(failures))

def _spec_case_comparisons(inputs: AuthorityInputs) -> list[PairwiseComparison]:
    pair = inputs.spec_case
    if inputs.spec.status in {EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED}:
        return [_comparison('spec_case_locator', inputs.spec, inputs.case, ComparisonStatus.EXPLICIT_ABSENCE), _comparison('spec_case_semantic', inputs.spec, inputs.case, ComparisonStatus.NOT_REQUIRED)]
    return [_closure_comparison('spec_case_locator', inputs.spec, inputs.case, pair.locator_status, conflict_failure=ReconcileFailure.REFERENCE_IDENTITY_MISMATCH, unavailable_failure=ReconcileFailure.REFERENCE_UNKNOWN, differences=pair.differences), _closure_comparison('spec_case_semantic', inputs.spec, inputs.case, pair.semantic_status, conflict_failure=ReconcileFailure.SPEC_CASE_CONFLICT, unavailable_failure=ReconcileFailure.SEMANTIC_CLOSURE_MISSING, differences=pair.differences)]

def _coverage_comparison(*, comparison_id: str, left: AuthorityEvidence, right: AuthorityEvidence, pair: CaseCapabilityComparison) -> PairwiseComparison:
    required = set(pair.requirements)
    enabled = set(pair.enabled)
    disabled = set(pair.disabled)
    unknown = set(pair.unknown)
    overlap = enabled & disabled | enabled & unknown | disabled & unknown
    unclassified = required - enabled - disabled - unknown
    extras = (enabled | disabled | unknown) - required
    if not pair.registry_receipt_sha256 or not _SHA256_RE.fullmatch(pair.registry_receipt_sha256) or overlap or unclassified or extras or unknown:
        differences = [*(f'unknown:{item}' for item in sorted(unknown)), *(f'unclassified:{item}' for item in sorted(unclassified)), *(f'overlap:{item}' for item in sorted(overlap)), *(f'extra:{item}' for item in sorted(extras))]
        if not pair.registry_receipt_sha256:
            differences.append('registry_receipt_missing')
        return _comparison(comparison_id, left, right, ComparisonStatus.UNAVAILABLE, ReconcileFailure.CAPABILITY_UNKNOWN, differences)
    if disabled:
        return _comparison(comparison_id, left, right, ComparisonStatus.CONFLICT, ReconcileFailure.CASE_CAPABILITY_CONFLICT, tuple((f'disabled:{item}' for item in sorted(disabled))))
    return _comparison(comparison_id, left, right, ComparisonStatus.MATCH)

def _case_capability_comparisons(inputs: AuthorityInputs) -> list[PairwiseComparison]:
    return [_coverage_comparison(comparison_id='case_excel_dialect_requirements', left=inputs.case, right=inputs.excel, pair=inputs.case_capability), _coverage_comparison(comparison_id='case_product_capability_requirements', left=inputs.case, right=inputs.capability, pair=inputs.case_product_capability)]

def _capability_precedent_comparisons(inputs: AuthorityInputs) -> list[PairwiseComparison]:
    pair = inputs.capability_precedent
    if inputs.precedent.status in {EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED}:
        return [_comparison('capability_precedent_requirements', inputs.capability, inputs.precedent, ComparisonStatus.EXPLICIT_ABSENCE), _comparison('precedent_bed_build', inputs.precedent, inputs.bed, ComparisonStatus.NOT_REQUIRED)]
    required = set(pair.referenced_capabilities)
    precedent = set(pair.precedent_capabilities)
    differences = tuple(list(pair.differences) + [f'missing_precedent_capability:{item}' for item in sorted(required - precedent)] + [f'extra_precedent_capability:{item}' for item in sorted(precedent - required)])
    if not pair.registry_receipt_sha256 or not _SHA256_RE.fullmatch(pair.registry_receipt_sha256):
        capability_status = ComparisonStatus.UNAVAILABLE
        capability_failure = ReconcileFailure.REGISTRY_UNAVAILABLE
        differences = (*differences, 'precedent_registry_receipt_missing')
    elif differences:
        capability_status = ComparisonStatus.CONFLICT
        capability_failure = ReconcileFailure.CAPABILITY_PRECEDENT_CONFLICT
    else:
        capability_status = ComparisonStatus.MATCH
        capability_failure = None
    return [_comparison('capability_precedent_requirements', inputs.capability, inputs.precedent, capability_status, capability_failure, differences), _closure_comparison('precedent_bed_build', inputs.precedent, inputs.bed, pair.build_status, conflict_failure=ReconcileFailure.BUILD_MISMATCH, unavailable_failure=ReconcileFailure.STALE_OBSERVATION, differences=pair.differences)]

def _reference_comparisons(inputs: AuthorityInputs) -> list[PairwiseComparison]:
    manual = _manual_evidence(inputs)
    if manual.status is EvidenceStatus.PRESENT:
        return [_closure_comparison('manual_case_semantic', manual, inputs.case, inputs.manual_case.semantic_status, conflict_failure=ReconcileFailure.REFERENCE_CONFLICT, unavailable_failure=ReconcileFailure.REFERENCE_UNKNOWN, differences=inputs.manual_case.differences)]
    if manual.status in {EvidenceStatus.ABSENT, EvidenceStatus.NOT_REFERENCED}:
        return [_comparison('manual_case_semantic', manual, inputs.case, ComparisonStatus.EXPLICIT_ABSENCE if manual.status is EvidenceStatus.ABSENT else ComparisonStatus.NOT_REQUIRED)]
    return [_comparison('manual_case_semantic', manual, inputs.case, ComparisonStatus.UNAVAILABLE, ReconcileFailure.REFERENCE_UNKNOWN, ('manual_reference_unavailable',))]

def _expected_source_comparisons(inputs: AuthorityInputs) -> list[PairwiseComparison]:
    return [_closure_comparison(f'expected_source_claim:{item.source_kind}', inputs.case, inputs.case, item.status, conflict_failure=ReconcileFailure.EXPECTED_SOURCE_CONFLICT, unavailable_failure=ReconcileFailure.EXPECTED_SOURCE_UNKNOWN, differences=item.differences) for item in sorted(inputs.source_claims, key=lambda item: item.source_kind)]

def _build_comparisons(inputs: AuthorityInputs) -> list[PairwiseComparison]:
    comparisons = [*_expected_source_comparisons(inputs), *_spec_case_comparisons(inputs), *_case_capability_comparisons(inputs), *_capability_precedent_comparisons(inputs), *_reference_comparisons(inputs)]
    if inputs.capability.build:
        status = ComparisonStatus.MATCH if inputs.capability.build == inputs.bed.build else ComparisonStatus.CONFLICT
        comparisons.append(_comparison('capability_bed_build', inputs.capability, inputs.bed, status, None if status is ComparisonStatus.MATCH else ReconcileFailure.BUILD_MISMATCH, () if status is ComparisonStatus.MATCH else ('build:value_mismatch',)))
    else:
        comparisons.append(_comparison('capability_bed_build', inputs.capability, inputs.bed, ComparisonStatus.UNAVAILABLE, ReconcileFailure.CAPABILITY_UNKNOWN, ('product_capability_build_unavailable',)))
    return comparisons

def _dedup_failures(items: Sequence[ReconcileFailure]) -> tuple[ReconcileFailure, ...]:
    return tuple(dict.fromkeys(items))
AUTHORITY_BLOCKING_FAILURES = frozenset({ReconcileFailure.MISSING_IDENTITY, ReconcileFailure.BUILD_MISMATCH, ReconcileFailure.SEMANTIC_CLOSURE_MISSING, ReconcileFailure.EXPECTED_SOURCE_UNKNOWN, ReconcileFailure.CAPABILITY_UNKNOWN, ReconcileFailure.STALE_OBSERVATION, ReconcileFailure.REFERENCE_IDENTITY_MISMATCH, ReconcileFailure.REFERENCE_UNKNOWN, ReconcileFailure.REGISTRY_UNAVAILABLE, ReconcileFailure.UNKNOWN})

def authority_state_for_failures(failures: Sequence[ReconcileFailure]) -> AuthorityState:
    if any((not isinstance(item, ReconcileFailure) for item in failures)):
        raise ValueError('authority failure is outside the declared vocabulary')
    if any((item in AUTHORITY_BLOCKING_FAILURES for item in failures)):
        return AuthorityState.BLOCKED
    return AuthorityState.NEEDS_DECISION if failures else AuthorityState.READY

def reconcile_authority(inputs: AuthorityInputs) -> AuthorityReceipt:
    raw_inputs = _inputs_dict(inputs)
    input_sha256 = canonical_sha256(raw_inputs)
    idempotency_key = f'{AUTHORITY_SCHEMA}:{input_sha256}'
    validation_failures = _validation_failures(inputs)
    try:
        comparisons = _build_comparisons(inputs)
    except (TypeError, ValueError):
        comparisons = []
        validation_failures.append(ReconcileFailure.UNKNOWN)
    comparison_failures = [item.failure for item in comparisons if item.failure is not None]
    failures = _dedup_failures([*validation_failures, *comparison_failures])
    state = authority_state_for_failures(failures)
    conflicts = tuple((item.comparison_id for item in comparisons if item.status in {ComparisonStatus.CONFLICT, ComparisonStatus.UNAVAILABLE}))
    source_identities = _source_identities(inputs)
    spec_generation_id, spec_manifest_sha256 = _spec_generation_identity(inputs)
    core = {'schema': inputs.schema, 'input_sha256': input_sha256, 'idempotency_key': idempotency_key, 'state': state.value, 'binding': _binding_dict(inputs.binding), 'spec_generation_id': spec_generation_id, 'spec_manifest_sha256': spec_manifest_sha256, 'source_identities': [{'layer': l, 'status': s, 'identity': i, 'build': b} for l, s, i, b in source_identities], 'comparisons': [item.to_dict() for item in comparisons], 'conflicts': list(conflicts), 'failures': [item.value for item in failures]}
    return AuthorityReceipt(schema=inputs.schema, input_sha256=input_sha256, idempotency_key=idempotency_key, receipt_sha256=canonical_sha256(core), state=state, binding=inputs.binding, spec_generation_id=spec_generation_id, spec_manifest_sha256=spec_manifest_sha256, source_identities=source_identities, comparisons=tuple(comparisons), conflicts=conflicts, failures=failures)

def authority_fact(receipt: AuthorityReceipt) -> dict[str, Any]:
    return {'ev': 'authority_reconciled', 'aid': receipt.binding.autoid, 'idempotency_key': receipt.idempotency_key, 'receipt': receipt.to_dict()}

def _receipt_fact_matches(fact: Mapping[str, Any], receipt: AuthorityReceipt) -> bool:
    return fact.get('ev') == 'authority_reconciled' and fact.get('idempotency_key') == receipt.idempotency_key and (fact.get('receipt') == receipt.to_dict())

def append_fact_once(receipt: AuthorityReceipt, *, read_facts: FactReader, append_fact: FactAppender) -> PersistenceResult:
    try:
        existing = list(read_facts())
    except Exception as exc:
        return PersistenceResult(AuthorityState.BLOCKED, receipt, False, ReconcileFailure.REGISTRY_UNAVAILABLE, f'read:{type(exc).__name__}')
    same_key = [item for item in existing if item.get('ev') == 'authority_reconciled' and item.get('idempotency_key') == receipt.idempotency_key]
    if same_key:
        if any((_receipt_fact_matches(item, receipt) for item in same_key)) and all((_receipt_fact_matches(item, receipt) for item in same_key)):
            return PersistenceResult(receipt.state, receipt, False)
        return PersistenceResult(AuthorityState.BLOCKED, receipt, False, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'same idempotency key has different receipt content')
    try:
        append_fact(authority_fact(receipt))
        after = list(read_facts())
    except Exception as exc:
        return PersistenceResult(AuthorityState.BLOCKED, receipt, False, ReconcileFailure.REGISTRY_UNAVAILABLE, f'write_or_verify:{type(exc).__name__}')
    verified = [item for item in after if item.get('ev') == 'authority_reconciled' and item.get('idempotency_key') == receipt.idempotency_key]
    if not verified:
        return PersistenceResult(AuthorityState.BLOCKED, receipt, False, ReconcileFailure.REGISTRY_UNAVAILABLE, 'receipt was not present after append')
    if not all((_receipt_fact_matches(item, receipt) for item in verified)):
        return PersistenceResult(AuthorityState.BLOCKED, receipt, False, ReconcileFailure.IDEMPOTENCY_CONFLICT, 'same key acquired conflicting content during append')
    return PersistenceResult(receipt.state, receipt, True)

def delivery_gate(claim: DeliveryClaim, receipt: AuthorityReceipt, *, read_facts: FactReader, projection_validator: BindingValidator, artifact_validator: BindingValidator) -> GateVerdict:
    claim_values = _binding_dict(claim.binding)
    missing = [name for name, value in claim_values.items() if name != 'consistency_contract_sha256' and (not str(value).strip())]
    consistency_sha = claim_values['consistency_contract_sha256']
    if consistency_sha is not None and (not _SHA256_RE.fullmatch(str(consistency_sha).lower())):
        missing.append('consistency_contract_sha256')
    if not _SHA256_RE.fullmatch(claim.authority_receipt_sha256.lower()):
        missing.append('authority_receipt_sha256')
    if missing:
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.MISSING_IDENTITY,), tuple(sorted(set(missing))))
    receipt_values = _binding_dict(receipt.binding)
    mismatches = sorted((key for key in claim_values if claim_values[key] != receipt_values[key]))
    if claim.authority_receipt_sha256 != receipt.receipt_sha256:
        mismatches.append('authority_receipt_sha256')
    receipt_payload = receipt.to_dict()
    if receipt.receipt_sha256 != canonical_sha256({key: value for key, value in receipt_payload.items() if key != 'receipt_sha256'}):
        mismatches.append('authority_receipt_sha256')
    if claim.spec_generation_id != receipt.spec_generation_id:
        mismatches.append('spec_generation_id')
    if claim.spec_manifest_sha256 != receipt.spec_manifest_sha256:
        mismatches.append('spec_manifest_sha256')
    if receipt.spec_generation_id and (re.fullmatch('[0-9]{20}-[0-9a-f]{16}', claim.spec_generation_id) is None or _SHA256_RE.fullmatch(claim.spec_manifest_sha256) is None):
        mismatches.extend(('spec_generation_id', 'spec_manifest_sha256'))
    if mismatches:
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.DELIVERY_IDENTITY_MISMATCH,), tuple(sorted(set(mismatches))))
    try:
        facts = list(read_facts())
    except Exception:
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.REGISTRY_UNAVAILABLE,))
    matching = [fact for fact in facts if fact.get('ev') == 'authority_reconciled' and fact.get('idempotency_key') == receipt.idempotency_key]
    if not matching:
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.REGISTRY_UNAVAILABLE,))
    if not all((_receipt_fact_matches(item, receipt) for item in matching)):
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.IDEMPOTENCY_CONFLICT,))
    try:
        projection_ok = projection_validator(claim.binding)
    except Exception:
        projection_ok = False
    if projection_ok is not True:
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.PROJECTION_INVALID,))
    try:
        artifact_ok = artifact_validator(claim.binding)
    except Exception:
        artifact_ok = False
    if artifact_ok is not True:
        return GateVerdict(AuthorityState.BLOCKED, (ReconcileFailure.ARTIFACT_IDENTITY_MISMATCH,))
    if receipt.state is not AuthorityState.READY:
        return GateVerdict(receipt.state, (ReconcileFailure.AUTHORITY_NOT_READY,))
    return GateVerdict(AuthorityState.READY)
__all__ = ['AUTHORITY_SCHEMA', 'AuthorityEvidence', 'AuthorityInputs', 'AuthorityLayer', 'AuthorityReceipt', 'AuthorityState', 'authority_state_for_failures', 'CapabilityPrecedentComparison', 'CaseCapabilityComparison', 'ClosureStatus', 'ComparisonStatus', 'DeliveryClaim', 'EvidenceStatus', 'ExpectedClaim', 'ExpectedClaimPersistenceResult', 'ExpectedClaimReceipt', 'ExpectedAuthorityPreflight', 'ExecutionBinding', 'FinalAssertion', 'GateVerdict', 'ManualStatus', 'PairwiseComparison', 'PersistenceResult', 'ReconcileFailure', 'RegistryStatus', 'SemanticBindingReceipt', 'SemanticClosureResult', 'SourceClaimClosure', 'SpecCaseComparison', 'TypedExpectation', 'ExpectedFacet', 'FacetedExpectation', 'append_fact_once', 'append_expected_claim_fact_once', 'author_fixture_policies_from_contract', 'authority_fact', 'canonical_sha256', 'claim_conflict_both_true', 'CLAIM_CONFLICT_BOTH_TRUE_PREFIX', 'delivery_gate', 'expected_source_group', 'expected_claim_fact', 'produce_expected_claim_receipt', 'reconcile_authority', 'reconcile_expected_authority_preflight', 'reconcile_expectation_assertions', 'reconcile_source_claims']
