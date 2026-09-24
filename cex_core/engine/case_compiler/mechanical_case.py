# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/mechanical_case.py（sha256 100fd6c46788d531）。不在这里手改。
from __future__ import annotations
import json
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NamedTuple, Self
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, sha256_bytes, validate_json_budget
from cex_core.engine.case_compiler.blocks import _ASSERTION_ID_BLOCK_KINDS, _NO_ASSERTION_ID_KINDS, _assertion_identity, _assertion_slot_label
from cex_core.engine.case_compiler.mindmap_contract_projector import _canonical_sha256
from cex_core.engine.case_compiler.provenance_ir import _EXPECT_KINDS
MECHANICAL_CASE_SCHEMA = 'ist.mechanical-case'
LEGACY_MECHANICAL_GATE_REPORT_SCHEMA = 'ist.mechanical-case-gate-report'
MECHANICAL_GATE_REPORT_SCHEMA = 'ist.mechanical-case-gate-report'
MECHANICAL_CASE_KEYS: tuple[str, ...] = ('schema', 'autoid', 'description', 'binding', 'init_commands', 'blocks', 'expectation_binding', 'escape_hatches', 'seal')
MECHANICAL_CASE_BODY_KEYS = frozenset(MECHANICAL_CASE_KEYS) - {'seal'}
_AUTOID_PATTERN = '^\\d{18}$'
_SHA256_PATTERN = '^[0-9a-f]{64}$'
_MAX_MECHANICAL_CASE_BYTES = 4 * 1024 * 1024
_OBSERVE_ASSERT_KIND = 'OBSERVE_ASSERT'
_GENERIC_STEP_KIND = 'STEP'
_CHECK_POINT_OBJECT = 'check_point'

class MechanicalCaseError(ValueError):
    pass

def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate JSON key: {key}')
        out[key] = value
    return out

def _reject_constant(value: str) -> None:
    raise ValueError(f'non-finite JSON constant: {value}')

def _normalized_kind(block: dict[str, Any]) -> str:
    return str(block.get('kind', '') or '').strip().upper()

def _require_text_entries(values: list[str], *, label: str) -> None:
    for index, value in enumerate(values):
        if not value.strip():
            raise ValueError(f'{label}[{index}] must be non-empty text')

def _slot_label(block_index: int, assert_index: int | None) -> str:
    if assert_index is None:
        return _assertion_slot_label(_GENERIC_STEP_KIND, block_index, 0)
    return _assertion_slot_label(_OBSERVE_ASSERT_KIND, block_index, assert_index + 1)

def _slot_sort_key(slot: tuple[int, int | None]) -> tuple[int, int]:
    return (slot[0], -1 if slot[1] is None else slot[1])

def _carried_identity(container: Any, label: str) -> dict[str, str]:
    if not isinstance(container, dict):
        raise ValueError(f'{label} must be an object carrying the assertion identity minted by the contract card')
    ids, error = _assertion_identity(container)
    if error:
        raise ValueError(f'{label}: {error}')
    return ids

class _Sealed(BaseModel):
    """全字段无默认值 + 拒未知键 + 严格类型：缺键、多键、类型漂移都当场拒。"""
    model_config = ConfigDict(extra='forbid', strict=True, populate_by_name=False)

class MechanicalCaseDescription(_Sealed):
    intent_verbatim: str = Field(min_length=1, max_length=8192, description='The case intent copied verbatim from the signed contract card.')
    group_path: list[str] = Field(min_length=1, max_length=64, description='The mindmap group path copied verbatim from the contract card.')

    @model_validator(mode='after')
    def _validate_description(self) -> Self:
        if not self.intent_verbatim.strip():
            raise ValueError('intent_verbatim must be non-empty text')
        _require_text_entries(self.group_path, label='group_path')
        return self

class MechanicalCaseBinding(_Sealed):
    contract_sha256: str = Field(pattern=_SHA256_PATTERN, description='Byte SHA256 of the frozen contracts/<autoid>.json this case compiles.')
    consistency_contract_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN, description='Byte SHA256 of the linked ist.consistency-contract overlay in the sealed artifact. On submission this is engine-owned glue: omit it or pass null and submit_mechanical_case stamps the SHA it just verified; a non-empty caller value is accepted only when it is identical. It remains null in the sealed artifact only when the engine stamped consistency as not applicable.')
    mindmap_source_sha256: str = Field(pattern=_SHA256_PATTERN, description='Byte SHA256 of the mindmap source the contract card was minted from.')
    capability_generation_id: str = Field(min_length=1, max_length=128, description='Command-tree capability generation this case was authored against.')
    capability_projection_sha256: str = Field(pattern=_SHA256_PATTERN, description='Byte SHA256 of the capability projection for that generation.')
    authored_round: int = Field(ge=1, description='Engine round that authored this mechanical case.')

    @model_validator(mode='after')
    def _validate_binding(self) -> Self:
        if not self.capability_generation_id.strip():
            raise ValueError('capability_generation_id must be non-empty text')
        return self

class MechanicalCaseExpectationBinding(_Sealed):
    expectation_id: str = Field(min_length=1, max_length=512, description='Expectation id minted by the contract card, copied verbatim.')
    semantic_key: str = Field(min_length=1, max_length=512, description='Semantic key minted by the contract card, copied verbatim.')
    claim_kind: str = Field(min_length=1, max_length=64, description='Identity-bearing expected source that signed this claim; one of the six declaration kinds. Device observation never signs expected.')
    block_index: int = Field(ge=0, description='Index into blocks[] of the combinator that carries this assertion.')
    assert_index: int | None = Field(default=None, description="For OBSERVE_ASSERT only: index into that block's asserts[]. Combinators that synthesise exactly one assertion carry null.")
    scope_ref: str | None = Field(default=None, description='Scope marker that tells sibling claims sharing one semantic_key apart, copied verbatim from a signed source; null when the claim needs none.')
    state_change_step: int | None = Field(default=None, description="Index into blocks[] of the product-configuration step that causes the state this assertion checks, when that step's own command line does not contain the asserted value. Use it only when the causal step is real and in this case's procedure; the engine checks that the index names a product-configuration block. Required together with binding_disclosure. It does not weaken the always-true defence: a not_found assertion whose declared causal step is the build-bound inverse of the asserted state is still refused, because undoing that state and then reporting it absent proves nothing about the behaviour under test.")
    binding_disclosure: str | None = Field(default=None, description="User-facing Chinese, one sentence: why the asserted value is absent from that step's command line, and how that step causes the change. It is copied verbatim into the delivery report as an authoring-side declaration, so write it for the reader of that report. Required together with state_change_step.")

    @model_validator(mode='after')
    def _validate_expectation_binding(self) -> Self:
        if self.claim_kind not in _EXPECT_KINDS:
            raise ValueError(f'claim_kind {self.claim_kind!r} is not an identity-bearing expected source; allowed: {sorted(_EXPECT_KINDS)}')
        if self.assert_index is not None and self.assert_index < 0:
            raise ValueError('assert_index must be a non-negative index or null')
        if self.scope_ref is not None and (not self.scope_ref.strip()):
            raise ValueError('scope_ref must be non-empty text or null')
        if self.state_change_step is not None and self.state_change_step < 0:
            raise ValueError('state_change_step must be a non-negative index or null')
        if self.binding_disclosure is not None and (not self.binding_disclosure.strip()):
            raise ValueError('binding_disclosure must be non-empty text or null')
        if (self.state_change_step is None) != (self.binding_disclosure is None):
            raise ValueError('state_change_step and binding_disclosure are declared together or not at all')
        return self

class MechanicalCaseEscapeHatch(_Sealed):
    block_index: int = Field(ge=0, description='Index into blocks[] of the kind=STEP combinator being accounted for.')
    capabilities_touched: list[str] = Field(max_length=64, description='Capabilities this generic step reaches, as observed capability names.')
    reason: str = Field(min_length=1, max_length=4096, description='Why a specialised combinator could not express this step.')

    @model_validator(mode='after')
    def _validate_escape_hatch(self) -> Self:
        if not self.reason.strip():
            raise ValueError('escape hatch reason must be non-empty text')
        _require_text_entries(self.capabilities_touched, label='capabilities_touched')
        return self

class EscapeHatchDefect(NamedTuple):
    code: str
    entry_index: int
    detail: str

def escape_hatch_accounting_defects(blocks: Sequence[Any], accounted_block_indices: Sequence[int]) -> list[EscapeHatchDefect]:
    kinds = [_normalized_kind(block) if isinstance(block, Mapping) else '' for block in blocks]
    defects: list[EscapeHatchDefect] = []
    declared: set[int] = set()
    for entry_index, block_index in enumerate(accounted_block_indices):
        if not 0 <= block_index < len(kinds):
            defects.append(EscapeHatchDefect('escape_hatch_out_of_range', entry_index, f'escape_hatches[{entry_index}].block_index {block_index} is out of range for {len(kinds)} blocks'))
            continue
        if block_index in declared:
            defects.append(EscapeHatchDefect('escape_hatch_duplicated', entry_index, f'escape_hatches[{entry_index}] accounts for blocks[{block_index}] twice'))
            continue
        declared.add(block_index)
    generic = {index for index, kind in enumerate(kinds) if kind == _GENERIC_STEP_KIND}
    if declared != generic:
        defects.append(EscapeHatchDefect('escape_hatch_set_mismatch', -1, f'escape_hatches must account for exactly the kind=STEP combinators; unaccounted={sorted(generic - declared)}, not-a-generic-step={sorted(declared - generic)}'))
    return defects

class MechanicalCaseSeal(_Sealed):
    mechanical_case_sha256: str = Field(pattern=_SHA256_PATTERN, description='Canonical SHA256 of the whole document except this field itself; it proves nothing was edited after sealing, not who minted it.')
    capabilities_used: list[str] = Field(min_length=1, max_length=1024, description='Sorted, de-duplicated capability names the expansion touches.')
    expanded_step_count: int = Field(ge=1, description='Row count produced by the expand_blocks dry run during the submission-rule check.')
    check_point_count: int = Field(ge=1, description='check_point row count in that expansion, counted at combinator granularity (before the emit-side per-bucket distribution fan-out); zero is an eternal FAIL.')
    gate_report_sha256: str = Field(pattern=_SHA256_PATTERN, description='Byte SHA256 of the rule report this seal was minted alongside.')
    gate_report_schema: Literal['ist.mechanical-case-gate-report'] = Field(default=MECHANICAL_GATE_REPORT_SCHEMA, description='Bare schema identity of the gate report bound by gate_report_sha256.')

    @model_validator(mode='after')
    def _validate_seal(self) -> Self:
        _require_text_entries(self.capabilities_used, label='capabilities_used')
        if list(self.capabilities_used) != sorted(set(self.capabilities_used)):
            raise ValueError('capabilities_used must be sorted and de-duplicated; mint the seal with seal_mechanical_case instead of hand-writing it')
        if self.expanded_step_count < self.check_point_count:
            raise ValueError('expanded_step_count cannot be smaller than check_point_count; check_point rows are part of the expansion')
        return self

class MechanicalCase(_Sealed):
    schema_: Literal['ist.mechanical-case'] = Field(alias='schema', serialization_alias='schema', description='Versioned mechanical-case schema.')
    autoid: str = Field(pattern=_AUTOID_PATTERN, description='The exact 18-digit case identity this document compiles.')
    description: MechanicalCaseDescription
    binding: MechanicalCaseBinding
    init_commands: list[str] = Field(max_length=512, description='File-level preconfig commands; empty uses the project default.')
    blocks: list[dict[str, Any]] = Field(min_length=1, max_length=1024, description='blocks.py combinator IR; inner legality is decided by expand_blocks.')
    expectation_binding: list[MechanicalCaseExpectationBinding] = Field(min_length=1, max_length=1024, description='Every contract-card expectation this case compiles, one entry each.')
    escape_hatches: list[MechanicalCaseEscapeHatch] = Field(max_length=1024, description='One entry per kind=STEP combinator; the index sets must be equal.')
    seal: MechanicalCaseSeal

    @model_validator(mode='after')
    def _validate_case(self) -> Self:
        _require_text_entries(self.init_commands, label='init_commands')
        kinds = self._block_kinds()
        carriers = self._assertion_carriers(kinds)
        self._validate_expectation_slots(kinds, carriers)
        self._validate_escape_hatch_accounting()
        if len(self.expectation_binding) != self.seal.check_point_count:
            raise ValueError(f'expectation_binding declares {len(self.expectation_binding)} expectations but the seal counts {self.seal.check_point_count} check_point rows; at combinator granularity every check_point row redeems exactly one expectation')
        return self

    def _block_kinds(self) -> list[str]:
        kinds: list[str] = []
        for index, block in enumerate(self.blocks):
            kind = _normalized_kind(block)
            if not kind:
                raise ValueError(f'blocks[{index}] needs a non-empty string kind; the carrier layering for assertion identity is decided by it')
            kinds.append(kind)
        return kinds

    def _assertion_carriers(self, kinds: list[str]) -> dict[tuple[int, int | None], dict[str, str]]:
        carriers: dict[tuple[int, int | None], dict[str, str]] = {}
        for index, kind in enumerate(kinds):
            block = self.blocks[index]
            if kind == _OBSERVE_ASSERT_KIND:
                asserts = block.get('asserts')
                if not isinstance(asserts, list) or not asserts:
                    raise ValueError(f'blocks[{index}] is an OBSERVE_ASSERT without a non-empty asserts[] array, so the assertions it carries cannot be read; each assertion declares its own identity there')
                for offset, entry in enumerate(asserts):
                    carriers[index, offset] = _carried_identity(entry, _slot_label(index, offset))
            elif kind in _ASSERTION_ID_BLOCK_KINDS:
                carriers[index, None] = _carried_identity(block, _slot_label(index, None))
            elif kind == _GENERIC_STEP_KIND:
                if str(block.get('E') or '').strip() == _CHECK_POINT_OBJECT:
                    carriers[index, None] = _carried_identity(block, _slot_label(index, None))
        return carriers

    def _validate_expectation_slots(self, kinds: list[str], carriers: dict[tuple[int, int | None], dict[str, str]]) -> None:
        seen_slots: set[tuple[int, int | None]] = set()
        for index, item in enumerate(self.expectation_binding):
            if item.block_index >= len(kinds):
                raise ValueError(f'expectation_binding[{index}].block_index {item.block_index} is out of range for {len(kinds)} blocks')
            kind = kinds[item.block_index]
            if kind == _OBSERVE_ASSERT_KIND:
                if item.assert_index is None:
                    raise ValueError(f'expectation_binding[{index}] targets OBSERVE_ASSERT blocks[{item.block_index}], whose assertion count is decided by asserts[]; assert_index must name that entry')
            elif kind in _ASSERTION_ID_BLOCK_KINDS or kind == _GENERIC_STEP_KIND:
                if item.assert_index is not None:
                    raise ValueError(f'expectation_binding[{index}] targets blocks[{item.block_index}] of kind {kind}, which carries assertion identity at block level; assert_index must be null')
            elif kind in _NO_ASSERTION_ID_KINDS:
                raise ValueError(f'expectation_binding[{index}] targets blocks[{item.block_index}] of kind {kind}, which produces no check_point to bind an expectation to')
            else:
                raise ValueError(f'expectation_binding[{index}] targets blocks[{item.block_index}] of unknown kind {kind!r}; assertion carriage cannot be decided')
            slot = (item.block_index, item.assert_index)
            if slot in seen_slots:
                raise ValueError(f'expectation_binding[{index}] reuses assertion slot block_index={item.block_index}, assert_index={item.assert_index}; one slot compiles exactly one expectation')
            seen_slots.add(slot)
            self._match_carried_identity(index, item, slot, kind, carriers)
        undeclared = sorted(set(carriers) - seen_slots, key=_slot_sort_key)
        if undeclared:
            raise ValueError(f"blocks carry {len(carriers)} assertion slots but expectation_binding declares only {len(seen_slots)}; unaccounted: {', '.join((_slot_label(*slot) for slot in undeclared))}. Every assertion slot must name a contract-card expectation; one expectation may intentionally occupy multiple distinct slots")

    def _match_carried_identity(self, index: int, item: MechanicalCaseExpectationBinding, slot: tuple[int, int | None], kind: str, carriers: dict[tuple[int, int | None], dict[str, str]]) -> None:
        carried = carriers.get(slot)
        if carried is None:
            if kind == _OBSERVE_ASSERT_KIND:
                count = sum((1 for key in carriers if key[0] == item.block_index))
                raise ValueError(f'expectation_binding[{index}].assert_index {item.assert_index} is out of range for the {count} asserts[] entries on blocks[{item.block_index}]')
            raise ValueError(f'expectation_binding[{index}] targets blocks[{item.block_index}], a kind={kind} whose E is not {_CHECK_POINT_OBJECT}: it expands to an action row, not an assertion row, so there is nothing to bind an expectation to')
        declared = {'expectation_id': item.expectation_id, 'semantic_key': item.semantic_key}
        if carried != declared:
            raise ValueError(f"expectation_binding[{index}] declares {declared} but {_slot_label(*slot)} carries {carried or 'no identity at all'}; the binding is the ledger of which claim is redeemed in which assertion slot, not a second place to mint identity — copy both keys verbatim from the assertion that compiles this expectation")

    def _validate_escape_hatch_accounting(self) -> None:
        defects = escape_hatch_accounting_defects(self.blocks, [hatch.block_index for hatch in self.escape_hatches])
        if defects:
            raise ValueError(defects[0].detail)

def validate_mechanical_case(payload: Any) -> tuple[MechanicalCase | None, str]:
    if not isinstance(payload, dict):
        return (None, 'mechanical case must be a JSON object')
    try:
        case = MechanicalCase.model_validate(payload, strict=True)
    except ValidationError as exc:
        details = '; '.join((f"{'.'.join((str(part) for part in error.get('loc', ())))}: {error.get('msg', '')}" for error in exc.errors()[:8]))
        return (None, f'invalid mechanical case: {details}')
    except (TypeError, ValueError) as exc:
        return (None, f'invalid mechanical case: {exc}')
    seal = payload['seal']
    if not isinstance(seal, dict):
        return (None, 'mechanical case seal must be a decoded JSON object; pass model_dump(by_alias=True) rather than a model instance')
    declared = str(seal.get('mechanical_case_sha256') or '')
    recomputed, digest_error = _canonical_digest(_mechanical_case_digest_input(payload))
    if digest_error:
        return (None, digest_error)
    if declared != recomputed:
        return (None, f'mechanical case seal does not match its body: declared {declared}, recomputed {recomputed}')
    return (case, '')

def _canonical_digest(payload: dict[str, Any]) -> tuple[str, str]:
    try:
        return (_canonical_sha256(payload), '')
    except (TypeError, ValueError, RecursionError) as exc:
        return ('', f'mechanical case is not canonicalisable: {type(exc).__name__}: {exc}')

def _mechanical_case_body(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != 'seal'}

def _mechanical_case_digest_input(payload: dict[str, Any]) -> dict[str, Any]:
    seal = payload.get('seal')
    metrics = {key: value for key, value in seal.items() if key != 'mechanical_case_sha256'} if isinstance(seal, dict) else seal
    return {**_mechanical_case_body(payload), 'seal': metrics}

def seal_mechanical_case(body: dict[str, Any], *, capabilities_used: list[str] | tuple[str, ...], expanded_step_count: int, check_point_count: int, gate_report_sha256: str, gate_report_schema: str=MECHANICAL_GATE_REPORT_SCHEMA) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise MechanicalCaseError('mechanical case body must be a JSON object')
    keys = set(body) - {'seal'}
    if keys != MECHANICAL_CASE_BODY_KEYS:
        missing = sorted(MECHANICAL_CASE_BODY_KEYS - keys)
        unknown = sorted(keys - MECHANICAL_CASE_BODY_KEYS)
        raise MechanicalCaseError(f'mechanical case body keys mismatch; missing={missing}, unknown={unknown}')
    if isinstance(capabilities_used, str) or not isinstance(capabilities_used, (list, tuple)):
        raise MechanicalCaseError('capabilities_used must be an array of capability names')
    for value in capabilities_used:
        if not isinstance(value, str) or not value.strip():
            raise MechanicalCaseError('capabilities_used entries must be non-empty text')
    metrics = {'capabilities_used': sorted(set(capabilities_used)), 'expanded_step_count': expanded_step_count, 'check_point_count': check_point_count, 'gate_report_sha256': gate_report_sha256, 'gate_report_schema': gate_report_schema}
    canonical, digest_error = _canonical_digest({**_mechanical_case_body(body), 'seal': metrics})
    if digest_error:
        raise MechanicalCaseError(digest_error)
    seal = {'mechanical_case_sha256': canonical, **metrics}
    try:
        MechanicalCaseSeal.model_validate(seal, strict=True)
    except (TypeError, ValueError) as exc:
        raise MechanicalCaseError(f'invalid mechanical case seal: {exc}') from exc
    return seal

class MintedMechanicalCase(NamedTuple):
    document: dict[str, Any] | None
    code: str
    detail: str

def mint_and_land_mechanical_case(body: dict[str, Any], target: str | Path, *, capabilities_used: list[str] | tuple[str, ...], expanded_step_count: int, check_point_count: int, gate_report_sha256: str) -> MintedMechanicalCase:
    try:
        seal = seal_mechanical_case(dict(body), capabilities_used=list(capabilities_used), expanded_step_count=int(expanded_step_count), check_point_count=int(check_point_count), gate_report_sha256=gate_report_sha256)
    except MechanicalCaseError as exc:
        return MintedMechanicalCase(None, 'seal_uncastable', str(exc))
    document = {**body, 'seal': seal}
    case, error = validate_mechanical_case(document)
    if case is None:
        return MintedMechanicalCase(None, 'sealed_document_invalid', error)
    from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, canonical_json
    try:
        atomic_write_bytes_nofollow(Path(target), canonical_json(document, ensure_ascii=False), error_type=MechanicalCaseError, invalid_message='mechanical case path is invalid', unavailable_message='mechanical case directory is unavailable')
    except (MechanicalCaseError, OSError) as exc:
        return MintedMechanicalCase(None, 'artifact_not_landed', f'the sealed mechanical case could not be written: {type(exc).__name__}')
    return MintedMechanicalCase(document, '', '')

def load_mechanical_case(path: str | Path) -> tuple[MechanicalCase, str]:
    raw = read_regular_nofollow(Path(path), error_type=MechanicalCaseError, invalid_message='mechanical case path is invalid', directory_message='mechanical case directory is unavailable', open_message='mechanical case is unavailable', bounds_message='mechanical case exceeds the byte budget', changed_message='mechanical case changed while being read', max_bytes=_MAX_MECHANICAL_CASE_BYTES)
    assert isinstance(raw, bytes)
    validate_json_budget(raw, error_type=MechanicalCaseError, message='mechanical case exceeds the JSON structure budget')
    try:
        payload = json.loads(raw.decode('utf-8'), object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MechanicalCaseError('mechanical case is not valid JSON') from exc
    case, error = validate_mechanical_case(payload)
    if case is None:
        raise MechanicalCaseError(error)
    return (case, sha256_bytes(raw))
__all__ = ['LEGACY_MECHANICAL_GATE_REPORT_SCHEMA', 'MECHANICAL_GATE_REPORT_SCHEMA', 'MECHANICAL_CASE_BODY_KEYS', 'MECHANICAL_CASE_KEYS', 'MECHANICAL_CASE_SCHEMA', 'EscapeHatchDefect', 'MechanicalCase', 'MechanicalCaseBinding', 'MechanicalCaseDescription', 'MechanicalCaseError', 'MechanicalCaseEscapeHatch', 'MechanicalCaseExpectationBinding', 'MechanicalCaseSeal', 'MintedMechanicalCase', 'escape_hatch_accounting_defects', 'load_mechanical_case', 'mint_and_land_mechanical_case', 'seal_mechanical_case', 'validate_mechanical_case']
