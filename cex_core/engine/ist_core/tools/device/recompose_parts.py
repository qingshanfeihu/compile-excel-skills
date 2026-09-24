# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/recompose_parts.py（sha256 504f51a2ae2c294e）。不在这里手改。
from __future__ import annotations
import fcntl
import json
import os
import re
import stat
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, canonical_json, lexical_absolute, lexical_path_inside_root, open_directory_nofollow, read_regular_nofollow, sha256_bytes
from cex_core.engine.engine_managed_outputs import MACHINE_MINDMAP_PARTS_LEDGER_NAME
PARTS_SCHEMA = 'ist.machine-mindmap-parts'
_AUTOID_RE = re.compile('^\\d{18}$')
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_DISPATCH_ID_RE = re.compile('^[0-9a-f]{32}$')
_MAX_LEDGER_BYTES = 16 * 1024 * 1024
_MAX_RECORD_BYTES = 4 * 1024 * 1024
_HEADER_KEYS = frozenset({'schema', 'kind', 'out_name', 'binding_sha256', 'source_sha256', 'case_autoids'})
_ENTRY_KEYS = frozenset({'schema', 'kind', 'dispatch_id', 'autoid', 'case', 'case_sha256'})
_INVALID_ENTRY_KEYS = frozenset({'schema', 'kind', 'autoid', 'reason'})
_APPEND_LOCK = threading.RLock()
_ENGINE_DERIVABLE_CASE_KEYS = frozenset({'autoid', 'group_path', 'steps'})
MACHINE_MINDMAP_BUCKETS: tuple[str, ...] = ('exp_recipe', 'step_recipe', 'true_gap')

class MachineMindmapPartsError(PermissionError):
    pass

def _case_is_hollow(case: Mapping[str, Any]) -> bool:
    return not set(case) - _ENGINE_DERIVABLE_CASE_KEYS

@dataclass(frozen=True)
class MachineMindmapPartsSnapshot:
    out_name: str
    binding_sha256: str
    source_sha256: str
    case_autoids: tuple[str, ...]
    cases: dict[str, dict[str, Any]]
    ledger_sha256: str

    @property
    def submitted_autoids(self) -> tuple[str, ...]:
        return tuple((aid for aid in self.case_autoids if aid in self.cases and (not _case_is_hollow(self.cases[aid]))))

    @property
    def missing_autoids(self) -> tuple[str, ...]:
        submitted = set(self.submitted_autoids)
        return tuple((aid for aid in self.case_autoids if aid not in submitted))

    def is_complete(self) -> bool:
        return not self.missing_autoids

    def ordered_cases(self) -> list[dict[str, Any]]:
        if not self.is_complete():
            raise MachineMindmapPartsError('machine mindmap parts ledger does not cover the closed case set')
        return [self.cases[aid] for aid in self.case_autoids]

def _validate_out_name(out_name: str) -> str:
    name = str(out_name or '').strip()
    if not name or name in {'.', '..'} or Path(name).name != name or ('/' in name) or ('\\' in name) or ('~' in name) or any((ord(char) < 32 for char in name)) or (len(name) > 180):
        raise MachineMindmapPartsError('machine mindmap parts out_name is invalid')
    return name

def _validate_case_autoids(case_autoids: Sequence[str]) -> tuple[str, ...]:
    ordered = tuple((str(aid) for aid in case_autoids or ()))
    if not ordered or any((_AUTOID_RE.fullmatch(aid) is None for aid in ordered)) or len(set(ordered)) != len(ordered):
        raise MachineMindmapPartsError('machine mindmap parts case set is not a closed 18-digit autoid set')
    return ordered

def machine_mindmap_parts_path(outputs_root: str | Path, out_name: str) -> Path:
    name = _validate_out_name(out_name)
    root = lexical_absolute(outputs_root)
    target = lexical_path_inside_root(root / name / MACHINE_MINDMAP_PARTS_LEDGER_NAME, root, error_type=MachineMindmapPartsError, traversal_message='machine mindmap parts path traversal is forbidden', outside_message='machine mindmap parts path escaped outputs root')
    if target != root / name / MACHINE_MINDMAP_PARTS_LEDGER_NAME:
        raise MachineMindmapPartsError('machine mindmap parts path identity is invalid')
    return target

def _line(value: Mapping[str, object]) -> bytes:
    record = dict(value)
    try:
        json.dumps(record, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise MachineMindmapPartsError('machine mindmap parts record contains a non-finite or unserializable value') from exc
    payload = canonical_json(record, ensure_ascii=False) + b'\n'
    if len(payload) > _MAX_RECORD_BYTES:
        raise MachineMindmapPartsError('machine mindmap parts record exceeds its budget')
    return payload

def _decode_line(raw: bytes) -> dict[str, object]:

    def reject_duplicates(pairs):
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f'non-finite JSON constant: {value}')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapPartsError('machine mindmap parts ledger contains invalid JSON') from exc
    if not isinstance(value, dict):
        raise MachineMindmapPartsError('machine mindmap parts record must be an object')
    return value

def _header_line(out_name: str, binding_sha256: str, source_sha256: str, case_autoids: Sequence[str]) -> bytes:
    return _line({'schema': PARTS_SCHEMA, 'kind': 'dispatch', 'out_name': out_name, 'binding_sha256': binding_sha256, 'source_sha256': source_sha256, 'case_autoids': list(case_autoids)})

def _snapshot_from_bytes(raw: bytes, *, out_name: str, binding_sha256: str | None, source_sha256: str | None=None) -> MachineMindmapPartsSnapshot:
    if not raw or len(raw) > _MAX_LEDGER_BYTES or (not raw.endswith(b'\n')):
        raise MachineMindmapPartsError('machine mindmap parts byte framing is invalid')
    lines = raw.splitlines()
    if not lines or any((len(line) > _MAX_RECORD_BYTES for line in lines)):
        raise MachineMindmapPartsError('machine mindmap parts record framing is invalid')
    header = _decode_line(lines[0])
    header_binding = header.get('binding_sha256')
    header_source = header.get('source_sha256')
    if set(header) != _HEADER_KEYS or header.get('schema') != PARTS_SCHEMA or header.get('kind') != 'dispatch' or (header.get('out_name') != out_name) or (not isinstance(header_binding, str)) or (_SHA256_RE.fullmatch(header_binding) is None) or (not isinstance(header_source, str)) or (_SHA256_RE.fullmatch(header_source) is None) or (not isinstance(header.get('case_autoids'), list)):
        raise MachineMindmapPartsError('machine mindmap parts dispatch header is invalid')
    if binding_sha256 is not None and header_binding != binding_sha256:
        raise MachineMindmapPartsError('machine mindmap parts ledger belongs to another authority binding')
    if source_sha256 is not None and header_source != source_sha256:
        raise MachineMindmapPartsError('machine mindmap parts ledger belongs to another source generation')
    ordered = _validate_case_autoids(header['case_autoids'])
    allowed = set(ordered)
    cases: dict[str, dict[str, Any]] = {}
    for encoded in lines[1:]:
        row = _decode_line(encoded)
        if row.get('kind') == 'invalid':
            reason = row.get('reason')
            invalid_autoid = row.get('autoid')
            if set(row) != _INVALID_ENTRY_KEYS or row.get('schema') != PARTS_SCHEMA or (not isinstance(invalid_autoid, str)) or (invalid_autoid not in allowed) or (not isinstance(reason, str)) or (not reason.strip()) or (len(reason) > 200):
                raise MachineMindmapPartsError('machine mindmap parts invalidation record is invalid')
            cases.pop(invalid_autoid, None)
            continue
        autoid = row.get('autoid')
        digest = row.get('case_sha256')
        case = row.get('case')
        if set(row) != _ENTRY_KEYS or row.get('schema') != PARTS_SCHEMA or row.get('kind') != 'case' or (not isinstance(row.get('dispatch_id'), str)) or (_DISPATCH_ID_RE.fullmatch(str(row.get('dispatch_id'))) is None) or (not isinstance(autoid, str)) or (autoid not in allowed) or (not isinstance(case, dict)) or (not isinstance(digest, str)) or (_SHA256_RE.fullmatch(digest) is None) or (digest != sha256_bytes(canonical_json(case, ensure_ascii=False))):
            raise MachineMindmapPartsError('machine mindmap parts case record is invalid or stale')
        cases[autoid] = case
    return MachineMindmapPartsSnapshot(out_name=out_name, binding_sha256=header_binding, source_sha256=header_source, case_autoids=ordered, cases=cases, ledger_sha256=sha256_bytes(raw))

def initialize_machine_mindmap_parts(outputs_root: str | Path, out_name: str, *, binding_sha256: str, source_sha256: str, case_autoids: Sequence[str]) -> tuple[Path, MachineMindmapPartsSnapshot]:
    name = _validate_out_name(out_name)
    for digest in (binding_sha256, source_sha256):
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise MachineMindmapPartsError('machine mindmap parts identity digest is invalid')
    ordered = _validate_case_autoids(case_autoids)
    root = lexical_absolute(outputs_root)
    path = machine_mindmap_parts_path(root, name)
    header = _header_line(name, binding_sha256, source_sha256, ordered)
    existing: MachineMindmapPartsSnapshot | None = None
    try:
        raw = read_regular_nofollow(path, error_type=MachineMindmapPartsError, invalid_message='machine mindmap parts path is invalid', directory_message='machine mindmap parts parent is unavailable', open_message='machine mindmap parts ledger is unavailable', bounds_message='machine mindmap parts ledger exceeds its boundary', changed_message='machine mindmap parts ledger changed while reading', max_bytes=_MAX_LEDGER_BYTES, min_bytes=1, trusted_root=root, require_current_uid=True)
        assert isinstance(raw, bytes)
        candidate = _snapshot_from_bytes(raw, out_name=name, binding_sha256=binding_sha256, source_sha256=source_sha256)
        if candidate.case_autoids == ordered:
            existing = candidate
    except (MachineMindmapPartsError, FileNotFoundError, OSError):
        existing = None
    if existing is not None:
        return (path, existing)
    atomic_write_bytes_nofollow(path, header, error_type=MachineMindmapPartsError, invalid_message='machine mindmap parts path is invalid', unavailable_message='machine mindmap parts ledger cannot be initialized safely', create_parents=False, mode=384)
    return (path, MachineMindmapPartsSnapshot(out_name=name, binding_sha256=binding_sha256, source_sha256=source_sha256, case_autoids=ordered, cases={}, ledger_sha256=sha256_bytes(header)))

def discard_machine_mindmap_parts(outputs_root: str | Path, out_name: str) -> None:
    name = _validate_out_name(out_name)
    root = lexical_absolute(outputs_root)
    path = machine_mindmap_parts_path(root, name)
    try:
        directory_fd = open_directory_nofollow(path.parent, error_type=MachineMindmapPartsError, invalid_message='machine mindmap parts parent is invalid', unavailable_message='machine mindmap parts parent is unavailable')
    except MachineMindmapPartsError:
        return
    try:
        try:
            info = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()):
            raise MachineMindmapPartsError('machine mindmap parts ledger is not a sealed regular file')
        os.unlink(path.name, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)

def read_machine_mindmap_parts(outputs_root: str | Path, out_name: str, *, binding_sha256: str | None=None, source_sha256: str | None=None, preserve_missing: bool=False) -> MachineMindmapPartsSnapshot:
    name = _validate_out_name(out_name)
    root = lexical_absolute(outputs_root)
    path = machine_mindmap_parts_path(root, name)
    raw = read_regular_nofollow(path, error_type=MachineMindmapPartsError, invalid_message='machine mindmap parts path is invalid', directory_message='machine mindmap parts parent is unavailable', open_message='machine mindmap parts ledger is unavailable', bounds_message='machine mindmap parts ledger exceeds its boundary', changed_message='machine mindmap parts ledger changed while reading', max_bytes=_MAX_LEDGER_BYTES, min_bytes=1, preserve_missing=preserve_missing, trusted_root=root, require_current_uid=True)
    assert isinstance(raw, bytes)
    return _snapshot_from_bytes(raw, out_name=name, binding_sha256=binding_sha256, source_sha256=source_sha256)

def machine_mindmap_case_value_violations(cases: Iterable[Mapping[str, Any]], allowed_autoids: Iterable[str]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    materialized = list(cases or ())
    if not materialized:
        return [{'code': 'cases_empty', 'locus': 'cases', 'detail': 'the submission carries no case objects; record at least one finished case per call'}]
    allowed = {str(aid) for aid in allowed_autoids or ()}
    first_index_by_autoid: dict[str, int] = {}
    for index, case in enumerate(materialized):
        autoid = case.get('autoid') if isinstance(case, Mapping) else None
        if not isinstance(autoid, str) or _AUTOID_RE.fullmatch(autoid) is None:
            violations.append({'code': 'autoid_invalid', 'locus': f'cases[{index}].autoid', 'detail': f'each case must carry its dispatched 18-digit autoid as a JSON string; got {type(autoid).__name__}. Copy the autoid verbatim from the dispatched mindmap, quoted as a string.'})
            continue
        if autoid not in allowed:
            violations.append({'code': 'autoid_not_dispatched', 'locus': f'cases[{index}].autoid', 'detail': f'autoid {autoid} is outside the engine-dispatched closed set; only cases signed into this dispatch can be recorded'})
            continue
        if autoid in first_index_by_autoid:
            violations.append({'code': 'autoid_duplicated_in_call', 'locus': f'cases[{index}].autoid', 'detail': f'autoid {autoid} appears twice in this call (first at cases[{first_index_by_autoid[autoid]}]). The ledger replays records in order, so the later copy silently replaces the earlier one and only one of them is ever written; a per-field rejection could not say which copy it is about either. Submit one record per autoid. To replace a record you already submitted, send it again in a later call.'})
            continue
        first_index_by_autoid[autoid] = index
        if _case_is_hollow(case):
            violations.append({'code': 'case_carries_no_recomposition', 'locus': f'cases[{index}]', 'detail': f'case {autoid} carries only fields the engine backfills from the source snapshot (group_path, steps); nothing the recomposer produces is present. Recording it would mark the case finished and drop it from outstanding_autoids, so it would never be written. Submit the case with its contract, origin, proposal, bucket and expectations_by_step, or leave it out of this call and record it when it is done.'})
            continue
        from cex_core.engine.case_compiler.mindmap_contract_projector import proposal_shape_error
        if proposal_shape_error(case):
            proposal = case.get('proposal')
            if 'proposal' not in case:
                observed = 'the key is absent'
            elif isinstance(proposal, list):
                observed = 'the array contains a non-string or an empty string'
            else:
                observed = f'got a JSON {type(proposal).__name__}'
            violations.append({'code': 'proposal_shape_invalid', 'locus': f'cases[{index}].proposal', 'detail': f'case {autoid} must carry `proposal` as an array of non-empty plain strings, one entry per thing the source leaves missing, and an empty array when nothing is missing; {observed}. The engine does not derive this field, and the projector voids a draft whose proposal is malformed, so the case would never be written. Add the field and submit this one case again; no semantic verdict was made.'})
            continue
        from cex_core.engine.ist_core.compile_engine.rebind_binder import validate_case_enhancement_fields
        for detail in validate_case_enhancement_fields(case):
            violations.append({'code': 'enhancement_shape_invalid', 'locus': f'cases[{index}].enhancements', 'detail': f'case {autoid} enhancement fields are malformed: {detail}. Repair the five-field rebind license or concretization object and resubmit this case; no semantic verdict was made.'})
        bucket = case.get('bucket')
        if not isinstance(bucket, str) or bucket not in MACHINE_MINDMAP_BUCKETS:
            if 'bucket' not in case:
                observed = 'the key is absent'
            elif isinstance(bucket, str):
                observed = f'got {bucket[:40]!r}'
            else:
                observed = f'got a JSON {type(bucket).__name__}'
            violations.append({'code': 'bucket_not_in_closed_set', 'locus': f'cases[{index}].bucket', 'detail': f'case {autoid} must carry `bucket` as one of the three classification values exp_recipe, step_recipe or true_gap; {observed}. The engine does not derive this field — it recomputes only source_status and typed_assertion_status from the case itself — so an absent or unknown bucket stays unknown all the way to the artifact. Classify this case by the three-bucket criteria in the skill and submit this one case again; no semantic verdict was made.'})
            continue
        if bucket == 'true_gap':
            from cex_core.engine.case_compiler.mindmap_contract_projector import _derived_source_status
            if _derived_source_status(dict(case)) == 'complete':
                violations.append({'code': 'true_gap_source_complete', 'locus': f'cases[{index}].bucket', 'detail': f"case {autoid} declares bucket=true_gap, but the engine recomputes its source_status as complete from the case's description, authored steps and natural-language expectations. A complete source cannot be turned into a gap by classification. Use step_recipe or exp_recipe and preserve the source fields; true_gap is reserved for a mechanically incomplete source."})
            continue
        from cex_core.engine.case_compiler.mindmap_contract_projector import primary_expectation_membership_error
        if primary_expectation_membership_error(case):
            violations.append({'code': 'primary_expectation_not_in_step_expectations', 'locus': f'cases[{index}].expectations_by_step', 'detail': f'case {autoid}: contract.expectation and origin.expectation are not represented together in expectations_by_step. The projector requires an entry with the same origin and matching text after whitespace normalization and the existing author-locator label normalization. Check the selected primary declaration against its actual source, and include that declaration with its original origin in the step-bound list; retain the other authored expectations. Keep unresolved assertion fields null. This is structural membership, not an Author-versus-Spec verdict or a request to rewrite expected values. Nothing from this call was recorded; repair the submitted references/list and resubmit this case.'})
    return violations
_EVIDENCE_ATOM_MAX_CHARS = 1200
_EVIDENCE_CALL_MAX_CHARS = 20000
_CONFLICT_SURFACE_PROBLEMS = frozenset({'locator_unresolved', 'text_drift', 'invalid'})
_COPY_DISCIPLINE = 'Copy that atom whole, byte for byte — never retell it, never drop a leading number, a negation, a condition, or a trailing clause. Runs of whitespace are normalized before the comparison; nothing else is.'
_SPEC_SPAN_HINT = 'If the proposition you need is not complete inside the span you declared — its condition sits on neighbouring lines — declare a span that covers them (`spec:<file>:<start>-<end>` resolves to those lines joined) and quote that whole span. Do not cut the condition away so that a single line matches: a consequent without its condition asserts something the SPEC does not.'

def _evidence_block(atom: str) -> str:
    return '\n<<<SOURCE\n' + atom + '\nSOURCE>>>\n'

def _origin_unresolved_detail(origin: str, *, governing_spec: str | None) -> str:
    if origin.startswith('spec:'):
        if not governing_spec:
            return f'declares origin `{origin}`, which resolves to nothing here because this dispatch has no governing SPEC bound. Changing the filename or line span cannot make a `spec:` origin resolvable in this dispatch. Cite an author-mindmap anchor this case actually carries (`title`, `step:<n>`, `expectation:<n>`, or `expectation:<label>`) and quote that atom whole, or remove the proposition if it has no bound source.'
        bound = f'this dispatch binds governing_spec `{governing_spec}`'
        return f'declares origin `{origin}`, which resolves to nothing here: {bound}, and a `spec:` origin resolves only against that exact file, by 1-based line numbers inside it (`spec:<file>:<line>` or `spec:<file>:<start>-<end>`). Declare a span of the bound SPEC that really carries this proposition, or cite the author mindmap instead, and quote that span whole.'
    if origin.startswith('defect:'):
        return f'declares origin `{origin}`, which resolves to nothing here: no matching engine-bound DefectSpec projection is in force for this dispatch. Cite a source this dispatch actually binds.'
    if not origin:
        return 'declares no origin, so there is nothing for it to be verbatim against. Declare the anchor this text comes from and quote that anchor whole.'
    return f"declares origin `{origin}`, which this case does not carry in the dispatched mindmap. Declare an anchor this case really has (`title`, `step:<n>`, `expectation:<n>`, `expectation:<label>`) and quote that anchor's text whole."
_SPEC_SIDE_FORMS = '`spec_locator` names the governing-source side of the comparison and takes only `spec:<file>:<line>`, `spec:<file>:<start>-<end>`, or `defect:<backend>:<ticket-id>:title|description`.'
_CASE_SIDE_FORMS = '`case_locator` names the anchor inside this case that the comparison lands on, and takes only an anchor this case carries in the dispatched mindmap (`title`, `step:<n>`, `expectation:<label>`, `orphan_note:<n>`).'

def _locator_unresolved_detail(side: str, locator: str, *, governing_spec: str | None) -> str:
    other = 'case_locator' if side == 'spec' else 'spec_locator'
    forms = _SPEC_SIDE_FORMS if side == 'spec' else _CASE_SIDE_FORMS
    if not locator:
        return 'is empty, so this side of the comparison has no locator to resolve. ' + forms
    if side == 'spec' and locator.startswith('spec:'):
        if not governing_spec:
            return f'declares `{locator}`, but this dispatch has no governing SPEC bound. No filename or line-span edit can make this locator resolvable here. Drop this governing-source side of the comparison; a case anchor belongs in `case_locator`, not in this slot.'
        bound = f'this dispatch binds governing_spec `{governing_spec}`'
        return f'declares `{locator}`, which resolves to nothing here: {bound}, and a `spec:` locator resolves only against that exact file, by 1-based line numbers inside it (`spec:<file>:<line>` or `spec:<file>:<start>-<end>`). Declare a span of the bound SPEC that really carries this proposition, or drop this side of the comparison. Do not copy quote bytes; the engine stamps them from the locator.'
    if side == 'spec' and locator.startswith('defect:'):
        return f'declares `{locator}`, which resolves to nothing here: no matching engine-bound DefectSpec projection is in force for this dispatch. Cite a governing source this dispatch actually binds, or drop this side of the comparison.'
    if locator.startswith(('spec:', 'defect:')):
        return f'declares `{locator}`, a governing-source citation. That belongs in `{other}`; this slot takes an anchor of this case. ' + forms
    if side == 'spec':
        return f'declares `{locator}`, which is not a governing-source locator at all. ' + forms + f' An anchor of this case belongs in `{other}`.'
    return f'declares `{locator}`, which this case does not carry in the dispatched mindmap. ' + forms + ' Declare an anchor this case really has. Do not copy quote bytes; the engine stamps them from the locator.'

def _structural_detail(field: str, origin: str) -> str:
    if field == 'expectations_by_step':
        return "does not match the author's expectation set. This case's `expectation:*` anchors form an ordered, complete set: one entry per anchor, in source order, and any `spec:` / `defect:` entry you add goes after all of them. Entries missing, reordered, duplicated, or an external entry interleaved among the authored ones all fail this."
    if field.endswith('].n'):
        if origin.startswith('expectation:'):
            label = origin.split(':', 1)[1]
            if label.isdigit():
                return f"binds origin `{origin}` to a step this case does not have. A numeric `expectation:<n>` label is the author's own step number, so `n` here must be `{label}`."
            return f"binds origin `{origin}` to a step this case does not have. A labelled `expectation:<label>` binds to the step whose text carries `[{label}]` (or to the case's only step, when it has just one); `n` must be that step's number."
        if not origin:
            return 'carries a step number that names no step of this case. `n` must be the number of a step this case really has in the dispatched source.'
        return f'binds origin `{origin}` to a step this case does not have. Only an `expectation:<label>` origin carries its own step binding; with any other origin (`title`, `step:<n>`, `spec:…`, `defect:…`) `n` is free but must still be the number of a step this case really has in the dispatched source.'
    if field in ('group_path', 'steps'):
        return 'is refilled by the engine from the sealed source before this check runs, so a mismatch here means this autoid has no anchor in the dispatched source. Do not hand-write the field; say so in your return instead.'
    if field == 'depends_on':
        return "must be the autoid of the immediately preceding sibling case, and only when this case's own authored text names that autoid; otherwise leave it empty."
    return 'does not match the structure the engine derives from the sealed source.'
_EVIDENCE_EXPECTATION_FIELD_RE = re.compile('^expectations_by_step\\[(\\d+)\\](?:\\.(assertion\\.value|n))?$')

def _unrendered_evidence(case: Mapping[str, Any], field: str) -> dict[str, Any]:
    origin: object = ''
    kind = 'structural'
    try:
        if field in ('intent', 'verification_method', 'expectation'):
            kind = 'anchored'
            raw_origin = case.get('origin')
            if isinstance(raw_origin, Mapping):
                origin = raw_origin.get(field) or ''
        elif str(field or '').startswith('adaptation_notes['):
            kind = 'case_atoms'
        else:
            match = _EVIDENCE_EXPECTATION_FIELD_RE.fullmatch(str(field or ''))
            if match is not None:
                items = [item for item in case.get('expectations_by_step') or () if isinstance(item, dict)]
                index = int(match.group(1))
                if index < len(items):
                    origin = items[index].get('origin') or ''
                kind = 'structural' if match.group(2) == 'n' else 'anchored'
    except Exception:
        origin, kind = ('', 'structural')
    return {'origin': str(origin or ''), 'external': False, 'atoms': [], 'kind': kind, 'unrendered': True}

def _verbatim_field_detail(autoid: str, field: str, evidence: Mapping[str, Any], *, governing_spec: str | None, inline_budget: int) -> tuple[str, int]:
    origin = str(evidence.get('origin') or '')
    kind = str(evidence.get('kind') or 'structural')
    atoms = [str(item) for item in evidence.get('atoms') or () if str(item)]
    normalized_position_note = ''
    if _EVIDENCE_EXPECTATION_FIELD_RE.fullmatch(field):
        normalized_position_note = ' The numeric `expectations_by_step[...]` index is the engine-normalized position after source-derived fields are rebuilt; locate the entry in your submitted payload by its `origin`, not by that numeric position.'
    head = f'case {autoid}: `{field}` '
    if kind == 'structural':
        return (head + _structural_detail(field, origin) + normalized_position_note, 0)
    if kind == 'case_atoms':
        return (head + "must quote verbatim the one author atom it rewrote — a whole step or expectation node of this case, as the author wrote it. What you submitted is not any of this case's atoms. This is not a claim that the note is false; it is that its bytes are not an author atom. Quote the atom whole and keep your own description of the adaptation outside the quote, or drop the note.", 0)
    if not atoms:
        if evidence.get('unrendered'):
            declared = f', `{origin}`' if origin else ''
            return (head + f'is not verbatim equal to the atom at the origin it declares{declared}. The engine could not render that atom into this message — that is an engine-side rendering fault, not a claim that you invented the citation. Re-read that origin in the dispatched source and copy the atom whole. ' + _COPY_DISCIPLINE + normalized_position_note, 0)
        return (head + _origin_unresolved_detail(origin, governing_spec=governing_spec) + normalized_position_note, 0)
    atom = atoms[0]
    detail = head + f'is not verbatim equal to the atom at the origin it declares, `{origin}`. You did not invent this citation — that origin resolves; the bytes you submitted are not the bytes it resolves to.'
    if len(atom) <= _EVIDENCE_ATOM_MAX_CHARS and len(atom) <= inline_budget:
        detail += ' That atom, exactly:' + _evidence_block(atom) + _COPY_DISCIPLINE
        spent = len(atom)
    else:
        detail += f' That atom is {len(atom)} characters and is not inlined here; re-read `{origin}` in the dispatched source and copy it whole. ' + _COPY_DISCIPLINE
        spent = 0
    if origin.startswith('spec:'):
        detail += ' ' + _SPEC_SPAN_HINT
    return (detail + normalized_position_note, spent)

def _consistency_anchor_detail(autoid: str, consistency: Mapping[str, Any], failure: str, *, mindmap_text: str, governing_spec: str | None, spec_text: str | None, defect_spec_receipt: dict[str, Any] | None, inline_budget: int) -> tuple[str, int]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import ConsistencyStampFailure
    del mindmap_text, spec_text, defect_spec_receipt, inline_budget
    head = f'case {autoid}: consistency card, {failure} — '
    engine_owned = 'Quote bytes are engine-owned glue: omit `spec_quote` / `case_quote` / `premises[].text` (or pass empty). A non-empty caller value is only a byte-for-byte cross-check and did not match the bytes the engine resolves from the locator. Do not copy quote bytes back.'
    if failure in ('consistency_spec_locator_unresolved', 'consistency_case_locator_unresolved'):
        side = 'spec' if 'spec_locator' in failure else 'case'
        locator = str(consistency.get(f'{side}_locator') or '').strip()
        return (head + f'`{side}_locator` ' + _locator_unresolved_detail(side, locator, governing_spec=governing_spec), 0)
    if failure in ('consistency_spec_quote_drift', 'consistency_case_quote_drift'):
        side = 'spec' if 'spec_quote' in failure else 'case'
        locator = str(consistency.get(f'{side}_locator') or '').strip()
        return (head + f'`{side}_quote` did not match the engine stamp for `{side}_locator` = `{locator}`. {engine_owned}', 0)
    stamp = ConsistencyStampFailure.of(failure)
    if stamp.collection == 'authored_conflict.surfaces' and stamp.problem in _CONFLICT_SURFACE_PROBLEMS:
        index = stamp.index
        problem = stamp.problem
        conflict = consistency.get('authored_conflict')
        locator = ''
        if isinstance(conflict, Mapping):
            surfaces = conflict.get('surfaces')
            if isinstance(surfaces, list) and 0 <= index < len(surfaces):
                item = surfaces[index]
                if isinstance(item, Mapping):
                    locator = str(item.get('locator') or '')
        if problem == 'locator_unresolved':
            return (head + f'`authored_conflict.surfaces[{index}].locator` `{locator}` does not resolve to one authored surface of this case. Name a locator of the case itself — `title`, `step:<n>`, `expectation:<label>` or `orphan_note:<n>` — out of `consistency_source_atoms`; the specification has no part in this record.', 0)
        if problem == 'text_drift':
            return (head + f'`authored_conflict.surfaces[{index}].quote` did not match the engine stamp for locator `{locator}`. {engine_owned}', 0)
        return (head + f'`authored_conflict.surfaces[{index}]` is not a complete object carrying `locator`. `quote` is optional; the engine stamps it from the locator.', 0)
    if stamp.collection == 'premises' and stamp.problem == 'locator_unresolved':
        index = stamp.index
        premises = consistency.get('premises')
        locator = ''
        origin = ''
        if isinstance(premises, list) and 0 <= index < len(premises):
            item = premises[index]
            if isinstance(item, Mapping):
                locator = str(item.get('locator') or '')
                origin = str(item.get('origin') or '')
        return (head + f'`premises[{index}].locator` `{locator}` (origin `{origin}`) does not resolve against the bound source. Name a locator this dispatch actually binds; omit `premises[].text` — the engine stamps it.', 0)
    if stamp.collection == 'premises' and stamp.problem == 'text_drift':
        index = stamp.index
        return (head + f"`premises[{index}].text` did not match the engine stamp for that premise's locator. {engine_owned}", 0)
    if failure.endswith('_shape_invalid'):
        return (head + 'a reasoning premise is not a complete object carrying `origin` and `locator`. `text` is optional; the engine stamps it from the locator.', 0)
    return (head + 'the consistency card failed locator resolution or quote cross-check. Omit quote fields and name locators this dispatch binds.', 0)

def machine_mindmap_case_verbatim_violations(cases: Iterable[Mapping[str, Any]], *, mindmap_text: str, spec_text: str | None, governing_spec: str | None, governing_spec_status: str | None, defect_spec_receipt: dict[str, Any] | None, defect_spec_status: str | None, defect_spec_receipt_sha256: str | None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import case_status_mismatches, fill_mechanical_fields, normalize_submission_case_statuses, primary_expectation_projection_problems, recompose_consistency_shape_report, stamp_consistency_quotes, verbatim_failures, verbatim_source_evidence
    materialized = [dict(case) for case in cases or ()]
    if not materialized:
        return ([], [])
    doc: dict[str, Any] = {'cases': materialized}
    fill_mechanical_fields(doc, mindmap_text)
    state_violations: list[dict[str, str]] = []
    for index, case in enumerate(materialized):
        for field, code in primary_expectation_projection_problems(case):
            state_violations.append({'code': code, 'locus': f'cases[{index}].{field}', 'detail': f"case {case.get('autoid')}: {field} is empty although expectations_by_step already contains entries claiming an Author origin. Bind the primary field to a complete source atom and its matching valid origin. A title or step atom can carry an authored outcome; a separate expectation child is not required. Source grounding still applies. Keep unresolved assertions null. This is a missing projection field, not missing author content or assertion quote drift."})
        normalize_submission_case_statuses(case)
        for field, actual in case_status_mismatches(case):
            state_violations.append({'code': 'case_status_mismatch', 'locus': f'cases[{index}].{field}', 'detail': f"case {case.get('autoid')}: {field} declares {case.get(field)!r}, but the submitted fields resolve to {actual!r}. Check contract.expectation and its origin against the complete atoms in expectations_by_step. An authored outcome may be sourced from title, step:<n>, or expectation:<label>; a separate expectation child is not required. Natural-language source completeness and an executable assertion tuple are different axes: an unresolved tuple stays null with typed status pending. This is a contradiction in the submitted fields, not a finding that the author omitted an expectation and not a request to copy prose into a regex."})
    if state_violations:
        return (materialized, state_violations)
    bad = verbatim_failures(doc, mindmap_text, spec_text, governing_spec=governing_spec, governing_spec_status=governing_spec_status, defect_spec_receipt=defect_spec_receipt, defect_spec_status=defect_spec_status, defect_spec_receipt_sha256=defect_spec_receipt_sha256)
    index_by_autoid = {str(case.get('autoid') or ''): index for index, case in enumerate(materialized)}
    violations: list[dict[str, str]] = []
    budget = _EVIDENCE_CALL_MAX_CHARS
    for autoid, fields in sorted(bad.items()):
        index = index_by_autoid.get(autoid, 0)
        case = materialized[index] if index < len(materialized) else {}
        for field in fields:
            try:
                evidence = verbatim_source_evidence(case, field, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt)
            except Exception:
                evidence = _unrendered_evidence(case, field)
            detail, spent = _verbatim_field_detail(autoid, field, evidence, governing_spec=governing_spec, inline_budget=budget)
            budget -= spent
            violations.append({'code': 'case_verbatim_mismatch', 'locus': f'cases[{index}].{field}', 'detail': detail})
    for index, case in enumerate(materialized):
        if 'consistency' not in case:
            continue
        consistency = case['consistency']
        if isinstance(consistency, dict):
            stamp_failure = stamp_consistency_quotes(consistency, str(case.get('autoid') or ''), mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, cross_check=True)
            if stamp_failure:
                try:
                    detail, spent = _consistency_anchor_detail(str(case.get('autoid') or ''), consistency, stamp_failure, mindmap_text=mindmap_text, governing_spec=governing_spec, spec_text=spec_text, defect_spec_receipt=defect_spec_receipt, inline_budget=budget)
                except Exception:
                    detail, spent = (f"case {str(case.get('autoid') or '')}: consistency card, {stamp_failure} — the engine could not render the detail for this failure. Omit quote fields and re-read locators against the dispatched source.", 0)
                budget -= spent
                violations.append({'code': 'consistency_anchor_mismatch', 'locus': f'cases[{index}].consistency', 'detail': detail})
                continue
        shape_failure, shape_reason = recompose_consistency_shape_report(consistency)
        if shape_failure:
            violations.append({'code': 'consistency_shape_invalid', 'locus': f'cases[{index}].consistency', 'detail': f'the consistency conclusion does not satisfy the ist.recompose-consistency shape ({shape_failure}): {shape_reason}. Repair exactly that, or leave the field out entirely when there is no comparable spec surface to judge against.'})
            continue
    return (materialized, violations)

def append_machine_mindmap_cases(outputs_root: str | Path, out_name: str, dispatch_id: str, cases: Iterable[Mapping[str, Any]]) -> MachineMindmapPartsSnapshot:
    name = _validate_out_name(out_name)
    identity = str(dispatch_id or '').strip()
    if _DISPATCH_ID_RE.fullmatch(identity) is None:
        raise MachineMindmapPartsError('machine mindmap parts dispatch identity is invalid')
    materialized = [dict(case) for case in cases]
    if not materialized:
        raise MachineMindmapPartsError('machine mindmap parts submission is empty')
    root = lexical_absolute(outputs_root)
    path = machine_mindmap_parts_path(root, name)
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    if not nofollow:
        raise MachineMindmapPartsError('machine mindmap parts ledger requires O_NOFOLLOW')
    with _APPEND_LOCK:
        parent_fd = open_directory_nofollow(path.parent, error_type=MachineMindmapPartsError, invalid_message='machine mindmap parts parent is invalid', unavailable_message='machine mindmap parts parent is unavailable')
        fd: int | None = None
        try:
            parent_info = os.fstat(parent_fd)
            if not stat.S_ISDIR(parent_info.st_mode) or (hasattr(os, 'getuid') and int(parent_info.st_uid) != os.getuid()):
                raise MachineMindmapPartsError('machine mindmap parts parent identity is invalid')
            flags = os.O_RDWR | os.O_APPEND | nofollow | getattr(os, 'O_CLOEXEC', 0)
            try:
                fd = os.open(path.name, flags, dir_fd=parent_fd)
            except OSError as exc:
                raise MachineMindmapPartsError('machine mindmap parts ledger cannot be opened safely') from exc
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()) or stat.S_IMODE(info.st_mode) & 63 or (int(info.st_size) > _MAX_LEDGER_BYTES):
                raise MachineMindmapPartsError('machine mindmap parts target identity is invalid')
            fcntl.flock(fd, fcntl.LOCK_EX)
            locked = os.fstat(fd)
            named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISREG(locked.st_mode) or not stat.S_ISREG(named.st_mode) or int(locked.st_nlink) != 1 or (int(named.st_nlink) != 1) or ((int(locked.st_dev), int(locked.st_ino)) != (int(named.st_dev), int(named.st_ino))):
                raise MachineMindmapPartsError('machine mindmap parts ledger changed while locking')
            os.lseek(fd, 0, os.SEEK_SET)
            current = b''
            remaining = int(locked.st_size)
            while remaining:
                chunk = os.read(fd, min(remaining, 1024 * 1024))
                if not chunk:
                    raise MachineMindmapPartsError('machine mindmap parts ledger read was short')
                current += chunk
                remaining -= len(chunk)
            snapshot = _snapshot_from_bytes(current, out_name=name, binding_sha256=None)
            allowed = set(snapshot.case_autoids)
            records: list[bytes] = []
            accepted: dict[str, dict[str, Any]] = {}
            for case in materialized:
                autoid = case.get('autoid')
                if not isinstance(autoid, str) or _AUTOID_RE.fullmatch(autoid) is None:
                    raise MachineMindmapPartsError('machine mindmap parts case autoid is invalid')
                if autoid in accepted:
                    raise MachineMindmapPartsError('machine mindmap parts submission repeats an autoid')
                if autoid not in allowed:
                    raise MachineMindmapPartsError('machine mindmap parts case autoid is outside the dispatched set')
                if _case_is_hollow(case):
                    raise MachineMindmapPartsError('machine mindmap parts case carries no recomposition')
                encoded = canonical_json(case, ensure_ascii=False)
                records.append(_line({'schema': PARTS_SCHEMA, 'kind': 'case', 'dispatch_id': identity, 'autoid': autoid, 'case': case, 'case_sha256': sha256_bytes(encoded)}))
                accepted[autoid] = case
            payload = b''.join(records)
            if int(locked.st_size) + len(payload) > _MAX_LEDGER_BYTES:
                raise MachineMindmapPartsError('machine mindmap parts ledger exceeds its byte budget')
            os.lseek(fd, 0, os.SEEK_END)
            offset = 0
            while offset < len(payload):
                written = os.write(fd, payload[offset:])
                if written <= 0:
                    raise OSError('short machine mindmap parts append')
                offset += written
            os.fsync(fd)
        except MachineMindmapPartsError:
            raise
        except OSError as exc:
            raise MachineMindmapPartsError('machine mindmap parts ledger append failed') from exc
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                os.close(fd)
            os.close(parent_fd)
    merged = dict(snapshot.cases)
    merged.update(accepted)
    try:
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        _fork_emit_event({'event': 'recompose_progress', 'run': name, 'stage': 'cases_recorded', 'recorded': len(merged), 'total': len(snapshot.case_autoids), 'delta_autoids': sorted(accepted)})
    except Exception:
        pass
    return MachineMindmapPartsSnapshot(out_name=name, binding_sha256=snapshot.binding_sha256, source_sha256=snapshot.source_sha256, case_autoids=snapshot.case_autoids, cases=merged, ledger_sha256=sha256_bytes(current + payload))

def invalidate_machine_mindmap_cases(outputs_root: str | Path, out_name: str, autoids: Iterable[str], *, reason: str) -> MachineMindmapPartsSnapshot | None:
    name = _validate_out_name(out_name)
    targets = [str(aid) for aid in autoids if str(aid or '').strip()]
    if not targets:
        raise MachineMindmapPartsError('machine mindmap parts invalidation is empty')
    reason_text = str(reason or '').strip()
    if not reason_text or len(reason_text) > 200:
        raise MachineMindmapPartsError('machine mindmap parts invalidation reason is invalid')
    root = lexical_absolute(outputs_root)
    path = machine_mindmap_parts_path(root, name)
    nofollow = getattr(os, 'O_NOFOLLOW', 0)
    if not nofollow:
        raise MachineMindmapPartsError('machine mindmap parts ledger requires O_NOFOLLOW')
    with _APPEND_LOCK:
        parent_fd = open_directory_nofollow(path.parent, error_type=MachineMindmapPartsError, invalid_message='machine mindmap parts parent is invalid', unavailable_message='machine mindmap parts parent is unavailable')
        fd: int | None = None
        try:
            parent_info = os.fstat(parent_fd)
            if not stat.S_ISDIR(parent_info.st_mode) or (hasattr(os, 'getuid') and int(parent_info.st_uid) != os.getuid()):
                raise MachineMindmapPartsError('machine mindmap parts parent identity is invalid')
            flags = os.O_RDWR | os.O_APPEND | nofollow | getattr(os, 'O_CLOEXEC', 0)
            try:
                fd = os.open(path.name, flags, dir_fd=parent_fd)
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise MachineMindmapPartsError('machine mindmap parts ledger cannot be opened safely') from exc
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()) or stat.S_IMODE(info.st_mode) & 63 or (int(info.st_size) > _MAX_LEDGER_BYTES):
                raise MachineMindmapPartsError('machine mindmap parts target identity is invalid')
            fcntl.flock(fd, fcntl.LOCK_EX)
            locked = os.fstat(fd)
            named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISREG(locked.st_mode) or not stat.S_ISREG(named.st_mode) or int(locked.st_nlink) != 1 or (int(named.st_nlink) != 1) or ((int(locked.st_dev), int(locked.st_ino)) != (int(named.st_dev), int(named.st_ino))):
                raise MachineMindmapPartsError('machine mindmap parts ledger changed while locking')
            os.lseek(fd, 0, os.SEEK_SET)
            current = b''
            remaining = int(locked.st_size)
            while remaining:
                chunk = os.read(fd, min(remaining, 1024 * 1024))
                if not chunk:
                    raise MachineMindmapPartsError('machine mindmap parts ledger read was short')
                current += chunk
                remaining -= len(chunk)
            snapshot = _snapshot_from_bytes(current, out_name=name, binding_sha256=None)
            allowed = set(snapshot.case_autoids)
            for autoid in targets:
                if _AUTOID_RE.fullmatch(autoid) is None or autoid not in allowed:
                    raise MachineMindmapPartsError('machine mindmap parts invalidation autoid is outside the dispatched set')
            payload = b''.join((_line({'schema': PARTS_SCHEMA, 'kind': 'invalid', 'autoid': autoid, 'reason': reason_text}) for autoid in targets))
            if int(locked.st_size) + len(payload) > _MAX_LEDGER_BYTES:
                raise MachineMindmapPartsError('machine mindmap parts ledger exceeds its byte budget')
            os.lseek(fd, 0, os.SEEK_END)
            offset = 0
            while offset < len(payload):
                written = os.write(fd, payload[offset:])
                if written <= 0:
                    raise OSError('short machine mindmap parts append')
                offset += written
            os.fsync(fd)
        except MachineMindmapPartsError:
            raise
        except OSError as exc:
            raise MachineMindmapPartsError('machine mindmap parts ledger append failed') from exc
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                os.close(fd)
            os.close(parent_fd)
    merged = dict(snapshot.cases)
    for autoid in targets:
        merged.pop(autoid, None)
    return MachineMindmapPartsSnapshot(out_name=name, binding_sha256=snapshot.binding_sha256, source_sha256=snapshot.source_sha256, case_autoids=snapshot.case_autoids, cases=merged, ledger_sha256=sha256_bytes(current + payload))
__all__ = ['MACHINE_MINDMAP_BUCKETS', 'MachineMindmapPartsError', 'MachineMindmapPartsSnapshot', 'PARTS_SCHEMA', 'append_machine_mindmap_cases', 'discard_machine_mindmap_parts', 'initialize_machine_mindmap_parts', 'invalidate_machine_mindmap_cases', 'machine_mindmap_case_value_violations', 'machine_mindmap_case_verbatim_violations', 'machine_mindmap_parts_path', 'read_machine_mindmap_parts']
