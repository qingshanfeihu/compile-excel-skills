# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/criterion_author_rules.py（sha256 f195d70256505bcb）。不在这里手改。
from __future__ import annotations
import fcntl
import hashlib
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import logging
from cex_core.engine.case_compiler.behaviour_classes import MAX_BEHAVIOUR_CLASS_CHARS, MAX_BEHAVIOUR_CLASSES, MAX_METHOD_CHARS, MAX_OBJECT_KIND_CHARS, MAX_PARAGRAPH_CHARS, MAX_SOURCE_PATH_CHARS
from cex_core.engine.common.nullable_scalar import restore_endpoint_encodings
from cex_core.engine.common.runtime_paths import runtime_path
from cex_core.engine.common.schema_identity import accepts_schema
logger = logging.getLogger(__name__)
ENGINE_RULE_SCHEMA = 'ist.criterion-engine-rule'
AUTHOR_RULE_SCHEMA = 'ist.criterion-author-rule'
ADJUDICATION_BRIEF_SCHEMA = 'ist.criterion-engine-adjudication-brief'
AUTHOR_RULE_PATH = runtime_path('criterion_author_rules.jsonl')
VETO_ANSWER = '否决并重裁'

class CriterionAuthorRuleError(ValueError):
    pass

class BehaviourClassification(BaseModel):
    """一个算法方法**按它自己的文档**属于哪一类（2026-09-06 裁决 E3）。

    这不是判据裁定的一部分，也不签任何期望：它决定编写侧拿到哪几条设备特性提示。
    引擎随后按闭集与文档字节机械复核（``behaviour_classes.
    validate_behaviour_classification``），核不过的那条降为 ``unclassified``。
    """
    model_config = ConfigDict(extra='forbid', strict=True)
    method: str = Field(min_length=1, max_length=MAX_METHOD_CHARS, description='The algorithm method value exactly as the case states it.')
    object_kind: str = Field(max_length=MAX_OBJECT_KIND_CHARS, description='The command-tree object path this method configures, copied from the request; empty when the request carried none.')
    behaviour_class: str = Field(min_length=1, max_length=MAX_BEHAVIOUR_CLASS_CHARS, description='One class copied exactly from the supplied closed set.')
    source_path: str = Field(min_length=1, max_length=MAX_SOURCE_PATH_CHARS, description='The documentation file the quote comes from, copied from the candidate paragraph you used.')
    quote: str = Field(min_length=1, max_length=MAX_PARAGRAPH_CHARS, description='The verbatim paragraph that states this behaviour; the engine resolves it against the documentation bytes.')
_BEHAVIOUR_CLASS_FIELDS: tuple[tuple[str, int], ...] = (('method', MAX_METHOD_CHARS), ('object_kind', MAX_OBJECT_KIND_CHARS), ('behaviour_class', MAX_BEHAVIOUR_CLASS_CHARS), ('source_path', MAX_SOURCE_PATH_CHARS), ('quote', MAX_PARAGRAPH_CHARS))

class CriterionAdjudicationResult(BaseModel):
    """LangChain ``ToolStrategy`` 的单 shape 结构化终态。

    身份、shape、证据 allowlist 均由引擎 brief 绑定，不放进模型可写字段。模型只
    提交开放世界的语义判断及可选自检锚；parser 随后仍会按 brief 机械复核。
    """
    model_config = ConfigDict(extra='forbid', strict=True)
    criterion_type: str = Field(min_length=1, max_length=128, description='One criterion type copied exactly from the supplied L catalogue.')
    rationale: str = Field(min_length=1, max_length=8192, description='English reasoning grounded only in the supplied evidence bundle.')
    disclosure: str = Field(min_length=1, max_length=8192, description='Chinese user-facing disclosure of the semantic judgement.')
    manual_anchor_ids: list[str] | None = Field(default=None, max_length=256, description='Optional self-check citations chosen only from allowed_manual_anchor_ids; the engine binds the authoritative allowlist independently.')
    tree_context_ids: list[str] | None = Field(default=None, max_length=256, description='Optional self-check citations chosen only from allowed_tree_context_ids; the engine binds the authoritative allowlist independently.')
    behaviour_classes: list[BehaviourClassification] | None = Field(default=None, max_length=MAX_BEHAVIOUR_CLASSES, description='One entry per (method, object_kind) the brief lists under behaviour_classification; omit an entry whose candidate paragraphs do not state the behaviour rather than guessing it.')

    @model_validator(mode='before')
    @classmethod
    def restore_endpoint_stringified_fields(cls, data: Any) -> Any:
        return restore_endpoint_encodings(data, cls.model_json_schema())

    @field_validator('behaviour_classes', mode='before')
    @classmethod
    def keep_only_usable_behaviour_classes(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return None
        kept: list[Any] = []
        for item in value:
            if isinstance(item, BehaviourClassification):
                kept.append(item)
                continue
            if not isinstance(item, Mapping):
                continue
            normalized = {key: item[key][:limit] for key, limit in _BEHAVIOUR_CLASS_FIELDS if isinstance(item.get(key), str)}
            normalized.setdefault('object_kind', '')
            try:
                kept.append(BehaviourClassification.model_validate(normalized, strict=True))
            except (TypeError, ValueError):
                continue
        return kept[:MAX_BEHAVIOUR_CLASSES]

def render_criterion_adjudication_result(value: Any) -> str:
    if isinstance(value, str):
        value = _load_criterion_judgment_object(value)
    try:
        parsed = CriterionAdjudicationResult.model_validate(value, strict=True)
    except (TypeError, ValueError) as exc:
        raise CriterionAuthorRuleError('criterion structured response failed schema validation') from exc
    return parsed.model_dump_json(exclude_none=True)

def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def _identity_preview(value: Any) -> str:
    if isinstance(value, set):
        value = sorted(value)
    structured = isinstance(value, (list, tuple, dict))
    if structured:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=isinstance(value, dict), separators=(',', ':'), default=str)
    else:
        raw = str(value if value is not None else '<missing>')
    safe = ''.join((char if char.isprintable() else f'\\u{ord(char):04x}' for char in raw))
    if re_full_sha(safe):
        safe = f'{safe[:12]}…{safe[-8:]}'
    elif len(safe) > 160:
        safe = safe[:120] + '…' + safe[-24:]
    return safe if structured else json.dumps(safe, ensure_ascii=False)

def _raise_identity_drift(key: str, *, expected: Any, actual: Any) -> None:
    raise CriterionAuthorRuleError(f'criterion adjudication identity drift: key={key}; expected={_identity_preview(expected)}; actual={_identity_preview(actual)}')

def _raise_evidence_gap(key: str, *, expected: Any, actual: Any) -> None:
    raise CriterionAuthorRuleError(f'criterion adjudication evidence chain is incomplete: key={key}; expected={_identity_preview(expected)}; actual={_identity_preview(actual)}')

def re_full_sha(value: Any) -> bool:
    return re.fullmatch('[0-9a-f]{64}', str(value or '')) is not None

def resolve_compile_manual_version(*, full_version: str='', device_build: str='') -> str:
    from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import _manual_version_from_full_version
    for candidate in (full_version, device_build):
        version = _manual_version_from_full_version(str(candidate or ''))
        if version:
            return version
    try:
        from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
        session = current_worker_device_session()
    except Exception:
        session = None
    if session is not None:
        version = _manual_version_from_full_version(getattr(session, 'capability_full_version', ''))
        if version:
            return version
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import configured_device_os_build_identity
        return _manual_version_from_full_version(configured_device_os_build_identity())
    except Exception:
        return ''

def _manual_anchor_id(anchor: Mapping[str, Any]) -> str:
    material = {'source_path': str(anchor.get('source_path') or ''), 'source_sha256': str(anchor.get('source_sha256') or ''), 'source_span': anchor.get('source_span'), 'quote': str(anchor.get('quote') or '')}
    return 'manual:' + _sha256(material)[:24]

def _rule_has_reuse_pins(record: Mapping[str, Any]) -> bool:
    if not str(record.get('manual_version') or ''):
        return False
    if record.get('pin_failures'):
        return False
    anchor_pins = record.get('anchor_chapter_shas')
    catalog_pins = record.get('catalog_pins')
    return isinstance(anchor_pins, dict) and bool(anchor_pins) and isinstance(catalog_pins, dict) and bool(catalog_pins)

def _families_from_anchors(anchors: Sequence[Mapping[str, Any]]) -> set[str]:
    families: set[str] = set()
    for anchor in anchors:
        if not isinstance(anchor, Mapping):
            continue
        normalized = str(anchor.get('source_path') or '').replace('\\', '/')
        match = re.search('/manual/[^/]+/(cli|app)_cn\\.md$', normalized)
        if match:
            families.add(match.group(1))
    return families

def _catalog_pins(manual_version: str, families: set[str], *, root: Path | None=None) -> dict[str, dict[str, str]]:
    from cex_core.engine.kms import manual_catalog_store
    pins: dict[str, dict[str, str]] = {}
    for family in sorted(families):
        if family not in ('cli', 'app'):
            continue
        verdict = manual_catalog_store.load_catalog_status(manual_version, family, root=root)
        pins[family] = {'catalog_sha256': str(verdict.get('catalog_sha256') or '')}
    return pins

def _rule_reusable(record: Mapping[str, Any], *, manual_version: str, root: Path | None=None) -> bool:
    if not _rule_has_reuse_pins(record):
        return False
    if str(record.get('manual_version') or '') != str(manual_version or ''):
        return False
    identity = record.get('identity')
    evidence = identity.get('evidence_chain') if isinstance(identity, dict) else None
    anchors = evidence.get('manual_anchors') if isinstance(evidence, dict) else None
    if not isinstance(anchors, list) or not anchors:
        return False
    from cex_core.engine.kms.manual_chapter_locator import anchor_chapter_pins
    try:
        live_anchor_pins = anchor_chapter_pins(anchors, manual_version=manual_version, root=root)
    except Exception:
        return False
    if dict(record.get('anchor_chapter_shas') or {}) != live_anchor_pins:
        return False
    return True
SUPERSEDE_CAUSES = ('author_veto', 'manual_section_changed', 'prior_not_verifiable')

def supersede_cause(prior: Mapping[str, Any], *, veto: Mapping[str, Any] | None, manual_version: str) -> str:
    if veto is not None:
        return 'author_veto'
    if not _rule_has_reuse_pins(prior):
        return 'prior_not_verifiable'
    del manual_version
    return 'manual_section_changed'

def round_rule_supply(active: Mapping[tuple[str, str], Mapping[str, Any]], records: Sequence[Mapping[str, Any]], *, manual_version: str) -> dict[tuple[str, str], dict[str, Any]]:
    supply = {tuple(key): dict(value) for key, value in active.items()}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        shape_key = str(record.get('shape_key') or '')
        if not shape_key:
            continue
        pinned = str(record.get('manual_version') or '')
        version = pinned or str(manual_version or '') or str(record.get('version_family') or '')
        supply[shape_key, version] = dict(record)
    return supply

def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate JSON key: {key}')
        out[key] = value
    return out

def _engine_record_valid(record: Any) -> bool:
    if not isinstance(record, dict) or not accepts_schema(record.get('schema'), ENGINE_RULE_SCHEMA):
        return False
    body = {key: value for key, value in record.items() if key != 'rule_sha256'}
    identity = body.get('identity')
    output = body.get('output')
    evidence = identity.get('evidence_chain') if isinstance(identity, dict) else None
    return bool(re_full_sha(body.get('shape_key')) and str(body.get('version_family') or '') and isinstance(body.get('generation'), int) and (not isinstance(body.get('generation'), bool)) and (int(body.get('generation') or 0) >= 1) and isinstance(output, dict) and (set(output) == {'criterion_type', 'mode'}) and str(output.get('criterion_type') or '') and (output.get('mode') == 'direct') and isinstance(identity, dict) and (set(identity) == {'kind', 'adjudicator', 'brief_sha256', 'decision_sha256', 'evidence_chain'}) and (identity.get('kind') == 'engine_adjudication') and (identity.get('adjudicator') == 'criterion-adjudicator') and re_full_sha(identity.get('brief_sha256')) and re_full_sha(identity.get('decision_sha256')) and isinstance(evidence, dict) and (set(evidence) == {'manual_anchors', 'tree_context', 'language'}) and isinstance(evidence.get('manual_anchors'), list) and bool(evidence['manual_anchors']) and isinstance(evidence.get('tree_context'), list) and bool(evidence['tree_context']) and isinstance(evidence.get('language'), dict) and (str(record.get('rule_sha256') or '') == _sha256(body)))

def _rule_history(path: Path) -> list[dict[str, Any]]:
    try:
        handle = Path(path).open('rb')
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    with handle:
        for raw in handle:
            try:
                item = json.loads(raw.decode('utf-8'), object_pairs_hook=_reject_duplicate_keys)
            except (UnicodeError, ValueError, json.JSONDecodeError):
                continue
            if _engine_record_valid(item):
                rows.append(item)
    return rows

def build_criterion_veto_question(record: Mapping[str, Any]) -> dict[str, Any]:
    if not _engine_record_valid(dict(record)):
        raise CriterionAuthorRuleError('criterion veto target is not a valid engine rule')
    material = {'schema': 'ist.criterion-engine-veto', 'shape_key': str(record['shape_key']), 'version_family': str(record['version_family']), 'rule_sha256': str(record['rule_sha256'])}
    answer_key = _sha256(material)
    return {'question': f"是否否决这条已披露的引擎判据裁定，并在下次同键编译时重新裁定？裁定规则：{str(record.get('rule_id') or '')}", 'header': '判据事后否决', 'options': [{'label': VETO_ANSWER, 'description': '废止这一代裁定；下次同 shape/version 由引擎重新取证裁定。'}], 'multiSelect': False, '_allow_other': False, '_answer_key': answer_key, '_veto_material': material}

def _veto_receipt(record: Mapping[str, Any], *, answer_path: Path | None=None) -> dict[str, Any] | None:
    from cex_core.engine.ist_core.tools.ask_user import _engine_question_digest
    question = build_criterion_veto_question(record)
    answer_key = str(question['_answer_key'])
    digest = _engine_question_digest(question)
    if not digest:
        return None
    path = Path(answer_path or runtime_path('ask_user_answers.jsonl'))
    try:
        handle = path.open('rb')
    except OSError:
        return None
    created_at = float(record.get('created_at') or 0.0)
    found: dict[str, Any] | None = None
    with handle:
        for raw in handle:
            try:
                item = json.loads(raw.decode('utf-8'))
            except (UnicodeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict) or not accepts_schema(item.get('schema'), 'ist.ask_user.answer'):
                continue
            try:
                if float(item.get('ts') or 0.0) < created_at:
                    continue
            except (TypeError, ValueError):
                continue
            for binding in item.get('answer_bindings') or []:
                if not isinstance(binding, dict):
                    continue
                if str(binding.get('answer_key') or '') == answer_key and str(binding.get('question_digest') or '') == digest and (str(binding.get('answer') or '') == VETO_ANSWER):
                    found = {'answer_key': answer_key, 'question_digest': digest, 'question_id': str(item.get('question_id') or ''), 'ts': float(item.get('ts') or 0.0), 'receipt_sha256': _sha256({'schema': item.get('schema'), 'question_id': item.get('question_id'), 'ts': item.get('ts'), 'binding': binding})}
    return found
_HISTORY_STATE_CACHE: dict[tuple, tuple[tuple, dict, dict]] = {}
_HISTORY_STATE_CACHE_MAX = 8

def _ledger_identity(path: Path) -> tuple[int, ...]:
    try:
        info = Path(path).lstat()
    except OSError:
        return ()
    return (int(info.st_mode), int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns), int(info.st_ctime_ns))

def _manual_pin_identity(manual_version: str | None) -> tuple:
    if not manual_version:
        return ()
    from cex_core.engine.kms import manual_catalog_store
    return tuple((manual_catalog_store.manual_identity(str(manual_version), family) for family in ('app', 'cli')))

def clear_author_rule_cache() -> None:
    from cex_core.engine.kms import manual_catalog_store
    manual_catalog_store.clear_bounded(_HISTORY_STATE_CACHE)

def _history_state(*, path: Path, answer_path: Path | None=None, manual_version: str | None=None) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    answers = Path(answer_path or runtime_path('ask_user_answers.jsonl'))
    cache_key = (str(path), str(answers), str(manual_version or ''))

    def _identity() -> tuple:
        return (_ledger_identity(path), _ledger_identity(answers), _manual_pin_identity(manual_version))
    identity = _identity()
    cached = _HISTORY_STATE_CACHE.get(cache_key)
    if cached is not None and cached[0] == identity:
        return _copy_history_state(cached[1], cached[2])
    active, history = _compute_history_state(path=path, answer_path=answer_path, manual_version=manual_version)
    if _identity() == identity:
        from cex_core.engine.kms import manual_catalog_store
        manual_catalog_store.remember_bounded(_HISTORY_STATE_CACHE, cache_key, (identity, dict(active), dict(history)), limit=_HISTORY_STATE_CACHE_MAX)
    return _copy_history_state(active, history)

def _copy_history_state(active: Mapping[tuple[str, str], Mapping[str, Any]], history: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    return ({key: dict(value) for key, value in active.items()}, {key: [dict(row) for row in rows] for key, rows in history.items()})

def _compute_history_state(*, path: Path, answer_path: Path | None=None, manual_version: str | None=None) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    history: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in _rule_history(path):
        pinned_version = str(record.get('manual_version') or '')
        if pinned_version and _rule_has_reuse_pins(record):
            key = (str(record['shape_key']), pinned_version)
        else:
            key = (str(record['shape_key']), str(record['version_family']))
        history[key].append(record)
    active: dict[tuple[str, str], dict[str, Any]] = {}
    for key, records in history.items():
        records.sort(key=lambda row: int(row.get('generation') or 0))
        latest = records[-1]
        if _veto_receipt(latest, answer_path=answer_path) is not None:
            continue
        if manual_version is not None:
            if key[1] != manual_version:
                continue
            if not _rule_reusable(latest, manual_version=manual_version):
                continue
        elif not _rule_has_reuse_pins(latest):
            continue
        active[key] = latest
    return (active, history)

def load_author_rules(*, path: Path | None=None, verify_credential: bool=True, answer_path: Path | None=None, manual_version: str | None=None) -> dict[tuple[str, str], dict[str, Any]]:
    del verify_credential
    resolved_manual_version = str(manual_version or resolve_compile_manual_version() or '')
    active, _history = _history_state(path=Path(path or AUTHOR_RULE_PATH), answer_path=answer_path, manual_version=resolved_manual_version or None)
    return active
load_criterion_rules = load_author_rules

def _manual_anchors(projection: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}

    def add(identity: Any, *, owner: str, algorithm_classes: Sequence[str]=()) -> None:
        if not isinstance(identity, Mapping):
            return
        anchor: Mapping[str, Any] | None = None
        if identity.get('kind') == 'manual_anchor':
            anchor = identity
        elif identity.get('kind') == 'user_ruling' and isinstance(identity.get('manual_method_anchor'), Mapping):
            anchor = identity['manual_method_anchor']
        if anchor is None:
            return
        material = {'source_path': str(anchor.get('source_path') or ''), 'source_sha256': str(anchor.get('source_sha256') or ''), 'source_span': anchor.get('source_span'), 'quote': str(anchor.get('quote') or '')}
        anchor_id = _manual_anchor_id(anchor)
        rows[anchor_id] = {'anchor_id': anchor_id, 'owner': owner, 'algorithm_classes': sorted({str(value) for value in algorithm_classes if str(value)}), 'line_start': anchor.get('line_start'), **material}
    for rule in projection.get('rules') or []:
        if isinstance(rule, Mapping):
            add(rule.get('identity'), owner=str(rule.get('rule_id') or ''))
    for class_id, spec in (projection.get('object_classes') or {}).items():
        if isinstance(spec, Mapping):
            add(spec.get('identity'), owner=f'object_class:{class_id}')
    for item in projection.get('adjudication_manual_anchors') or []:
        if isinstance(item, Mapping):
            add(item.get('identity'), owner=f"adjudication:{str(item.get('anchor_key') or '')}", algorithm_classes=[str(value) for value in item.get('algorithm_classes') or []])
    return [rows[key] for key in sorted(rows)]

def _tree_context(*, pending: Sequence[Mapping[str, Any]], machine_mindmap: Mapping[str, Any], contracts: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[str, str], set[str]]]:
    cases = {str(case.get('autoid') or ''): case for case in machine_mindmap.get('cases') or [] if isinstance(case, Mapping) and str(case.get('autoid') or '')}
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    members_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in pending:
        key = (str(row.get('shape_key') or ''), str(row.get('version_family') or ''))
        aid = str(row.get('autoid') or '')
        if re_full_sha(key[0]) and key[1] and aid:
            members_by_key[key].add(aid)
    rows: dict[str, dict[str, Any]] = {}
    for key, member_ids in sorted(members_by_key.items()):
        parent_paths = {tuple((cases.get(aid) or {}).get('group_path') or [])[:-1] for aid in member_ids}
        contextual_ids = set(member_ids)
        contextual_ids.update((aid for aid, case in cases.items() if tuple(case.get('group_path') or [])[:-1] in parent_paths))
        for aid in sorted(contextual_ids):
            case = cases.get(aid) or {}
            relation = 'member' if aid in member_ids else 'sibling'
            atoms = [('title', str(case.get('title') or ''))]
            atoms.extend(((f'step:{index}', str(step.get('text') or '')) for index, step in enumerate(case.get('steps') or [], start=1) if isinstance(step, Mapping)))
            contract = contracts.get(aid) or {}
            for index, expectation in enumerate(contract.get('expectations') or [], start=1):
                if not isinstance(expectation, Mapping):
                    continue
                atoms.append((f'expectation:{index}', str(expectation.get('text') or '')))
            for locator, text_value in atoms:
                if not text_value.strip():
                    continue
                context_id = f'tree:{aid}:{locator}'
                rows[context_id] = {'context_id': context_id, 'autoid': aid, 'relation': relation, 'locator': locator, 'group_path': list(case.get('group_path') or []), 'text': text_value}
                by_key[key].add(context_id)
    return ([rows[key] for key in sorted(rows)], by_key)

def _behaviour_classification_request(machine_mindmap: Mapping[str, Any], members: Sequence[str]) -> list[dict[str, Any]]:
    from cex_core.engine.case_compiler.behaviour_classes import classification_request, unique_bindings
    from cex_core.engine.case_compiler.device_characteristics import UNCLASSIFIED, behaviour_class_closed_set
    closed = behaviour_class_closed_set()
    if not closed:
        return []
    offered = sorted(closed - {UNCLASSIFIED})
    if not offered:
        return []
    wanted = {str(value) for value in members if str(value)}
    structure: list[Mapping[str, Any]] = []
    for case in (machine_mindmap or {}).get('cases') or []:
        if not isinstance(case, Mapping):
            continue
        if wanted and str(case.get('autoid') or '') not in wanted:
            continue
        entries = case.get('step_structure')
        if isinstance(entries, list):
            structure.extend((entry for entry in entries if isinstance(entry, Mapping)))
    if not structure:
        return []
    request = classification_request(structure)
    if not request:
        return []
    asked = unique_bindings(request)
    by_key = {(row['method'], row['object_kind']): row for row in request}
    return [{'method': row['method'], 'object_kind': row['object_kind'], 'behaviour_classes': offered, 'documentation': by_key[row['method'], row['object_kind']]['documentation']} for row in asked]

def build_engine_adjudication_brief(pending: Iterable[Mapping[str, Any]], *, projection: Mapping[str, Any], machine_mindmap: Mapping[str, Any], contracts: Mapping[str, Mapping[str, Any]], path: Path | None=None, answer_path: Path | None=None, manual_version: str | None=None) -> dict[str, Any] | None:
    resolved_manual_version = str(manual_version or resolve_compile_manual_version() or '')
    pending_rows = [dict(row) for row in pending if isinstance(row, Mapping)]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pending_rows:
        key = (str(row.get('shape_key') or ''), str(row.get('version_family') or ''))
        if re_full_sha(key[0]) and key[1]:
            groups[key].append(row)
    if not groups:
        return None
    active, history = _history_state(path=Path(path or AUTHOR_RULE_PATH), answer_path=answer_path, manual_version=resolved_manual_version or None)
    if resolved_manual_version:
        groups = {key: rows for key, rows in groups.items() if (key[0], resolved_manual_version) not in active}
    else:
        groups = {key: rows for key, rows in groups.items() if key not in active}
    if not groups:
        return None
    anchors = _manual_anchors(projection)
    if not anchors:
        raise CriterionAuthorRuleError('criterion adjudication has no grounded manual anchor')
    tree_rows, tree_ids = _tree_context(pending=[row for rows in groups.values() for row in rows], machine_mindmap=machine_mindmap, contracts=contracts)
    types = [dict(row) for row in projection.get('criterion_types') or [] if isinstance(row, Mapping) and str(row.get('criterion_type') or '')]
    if not types:
        raise CriterionAuthorRuleError('criterion adjudication has no L closed set')
    shapes: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        prior_key = (key[0], resolved_manual_version) if resolved_manual_version else key
        prior = (history.get(prior_key) or history.get(key) or [])[-1:]
        veto = _veto_receipt(prior[0], answer_path=answer_path) if prior else None
        algorithm_classes = sorted({str(value) for row in rows for value in row.get('algorithm_classes') or [] if str(value)})
        algorithm_anchor_ids = sorted({str(anchor.get('anchor_id') or '') for anchor in anchors if set((str(value) for value in anchor.get('algorithm_classes') or [])).intersection(algorithm_classes)})
        allowed_manual_anchor_ids = algorithm_anchor_ids if algorithm_anchor_ids else sorted((str(anchor.get('anchor_id') or '') for anchor in anchors))
        claims = [{'autoid': str(row.get('autoid') or ''), 'expectation_id': str(row.get('expectation_id') or ''), 'semantic_key': str(row.get('semantic_key') or ''), 'original_text': str(row.get('original_text') or ''), 'authored_step': row.get('authored_step'), 'authored_step_cause': row.get('authored_step_cause'), 'source_span': row.get('source_span')} for row in rows]
        shapes.append({'shape_key': key[0], 'version_family': key[1], 'behaviour_classification': _behaviour_classification_request(machine_mindmap, sorted({str(row.get('autoid') or '') for row in rows if row.get('autoid')})), 'members': sorted({str(row.get('autoid') or '') for row in rows if row.get('autoid')}), 'claims': claims, 'algorithm_classes': algorithm_classes, 'allowed_manual_anchor_ids': allowed_manual_anchor_ids, 'allowed_tree_context_ids': sorted(tree_ids.get(key) or []), 'prior_vetoed_decision': {'rule_id': str(prior[0].get('rule_id') or ''), 'criterion_type': str((prior[0].get('output') or {}).get('criterion_type') or ''), 'author_veto_receipt_sha256': str((veto or {}).get('receipt_sha256') or '')} if prior and veto else None})
    body = {'schema': ADJUDICATION_BRIEF_SCHEMA, 'manual_version': resolved_manual_version, 'criterion_types': types, 'manual_anchors': anchors, 'tree_context': tree_rows, 'shapes': shapes, 'shape_count': len(shapes), 'shape_identity_set_sha256': _sha256(sorted(([shape['shape_key'], shape['version_family']] for shape in shapes))), 'policy': {'authority_scope': 'verdict_to_criterion_type_only', 'expected_value_authority': ['Author', 'Spec', 'DefectSpec', 'Manual', 'ConfigBinding', 'CapabilityXml'], 'forbidden_inputs': ['precedent', 'historical_volume', 'device_actual']}}
    return {**body, 'brief_sha256': _sha256(body)}

def serialize_engine_adjudication_brief(brief: Mapping[str, Any]) -> str:
    if brief.get('schema') != ADJUDICATION_BRIEF_SCHEMA:
        _raise_identity_drift('brief.schema', expected=ADJUDICATION_BRIEF_SCHEMA, actual=brief.get('schema'))
    shapes = [row for row in brief.get('shapes') or [] if isinstance(row, Mapping)]
    if brief.get('shape_count') != len(shapes):
        _raise_identity_drift('brief.shape_count', expected=len(shapes), actual=brief.get('shape_count'))
    identity_digest = _sha256(sorted(([str(shape.get('shape_key') or ''), str(shape.get('version_family') or '')] for shape in shapes)))
    if brief.get('shape_identity_set_sha256') != identity_digest:
        _raise_identity_drift('brief.shape_identity_set_sha256', expected=identity_digest, actual=brief.get('shape_identity_set_sha256'))
    body = {key: value for key, value in brief.items() if key != 'brief_sha256'}
    expected_digest = _sha256(body)
    if brief.get('brief_sha256') != expected_digest:
        _raise_identity_drift('brief.brief_sha256', expected=expected_digest, actual=brief.get('brief_sha256'))
    return json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True)

def split_engine_adjudication_briefs(brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    serialize_engine_adjudication_brief(brief)
    manual_by_id = {str(row.get('anchor_id') or ''): dict(row) for row in brief.get('manual_anchors') or [] if isinstance(row, Mapping)}
    context_by_id = {str(row.get('context_id') or ''): dict(row) for row in brief.get('tree_context') or [] if isinstance(row, Mapping)}
    out: list[dict[str, Any]] = []
    for shape in brief.get('shapes') or []:
        if not isinstance(shape, Mapping):
            continue
        manual_ids = [str(value) for value in shape.get('allowed_manual_anchor_ids') or []]
        context_ids = [str(value) for value in shape.get('allowed_tree_context_ids') or []]
        body = {'schema': ADJUDICATION_BRIEF_SCHEMA, 'criterion_types': list(brief.get('criterion_types') or []), 'manual_anchors': [manual_by_id[value] for value in manual_ids], 'tree_context': [context_by_id[value] for value in context_ids], 'shapes': [dict(shape)], 'shape_count': 1, 'shape_identity_set_sha256': _sha256([[str(shape.get('shape_key') or ''), str(shape.get('version_family') or '')]]), 'policy': dict(brief.get('policy') or {})}
        out.append({**body, 'brief_sha256': _sha256(body)})
    return out
_JSON_FENCE_RE = re.compile('^```(?:json)?[ \\t]*\\r?\\n(.*)\\r?\\n```[ \\t]*$', re.DOTALL | re.IGNORECASE)
_TRAILING_CLOSE_FENCE_RE = re.compile('^```[ \\t]*$')

def _load_criterion_judgment_object(reply: str) -> dict[str, Any]:
    text = str(reply or '').strip().lstrip('\ufeff')
    if not text:
        raise CriterionAuthorRuleError('criterion judgment is not exact JSON')

    def _loads(raw: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
    direct = _loads(text)
    if direct is not None:
        return direct
    fenced = _JSON_FENCE_RE.fullmatch(text)
    if fenced is not None:
        inner = _loads(fenced.group(1).strip())
        if inner is not None:
            return inner
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
    for index in range(len(text) - 1, -1, -1):
        if text[index] != '{':
            continue
        try:
            payload, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        remainder = text[end:].strip()
        if remainder == '' or _TRAILING_CLOSE_FENCE_RE.match(remainder):
            return payload
    raise CriterionAuthorRuleError('criterion judgment is not exact JSON')

def parse_engine_adjudication_result(reply: str, *, brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    serialize_engine_adjudication_brief(brief)
    shapes = [row for row in brief.get('shapes') or [] if isinstance(row, Mapping)]
    if len(shapes) != 1:
        raise CriterionAuthorRuleError('criterion judgment parser accepts exactly one engine-bound shape')
    payload = _load_criterion_judgment_object(reply)
    if not isinstance(payload, dict):
        raise CriterionAuthorRuleError('criterion judgment must be one JSON object')
    judgment_fields = {'criterion_type', 'rationale', 'disclosure'}
    citation_fields = {'manual_anchor_ids', 'tree_context_ids', 'behaviour_classes'}
    ignored_identity_fields = {'schema', 'brief_sha256', 'shape_key', 'version_family'}
    unknown = set(payload) - judgment_fields - citation_fields - ignored_identity_fields
    if unknown:
        raise CriterionAuthorRuleError(f'criterion judgment fields are not closed; expected/operator/value and all non-judgment fields are forbidden: {sorted(unknown)}')
    if not judgment_fields <= set(payload):
        raise CriterionAuthorRuleError('criterion judgment requires criterion_type, rationale, and disclosure')
    catalogue = {str(row.get('criterion_type') or ''): row for row in brief.get('criterion_types') or [] if isinstance(row, Mapping)}
    criterion_type = str(payload.get('criterion_type') or '')
    if criterion_type not in catalogue:
        _raise_evidence_gap('criterion_type', expected=sorted(catalogue), actual=criterion_type)
    rationale = str(payload.get('rationale') or '').strip()
    disclosure = str(payload.get('disclosure') or '').strip()
    if not rationale:
        _raise_evidence_gap('rationale', expected='non-empty judgment rationale', actual=payload.get('rationale'))
    if not disclosure:
        _raise_evidence_gap('disclosure', expected='non-empty Chinese disclosure', actual=payload.get('disclosure'))
    shape = shapes[0]
    manual_ids = sorted({str(value) for value in shape.get('allowed_manual_anchor_ids') or [] if str(value)})
    context_ids = sorted({str(value) for value in shape.get('allowed_tree_context_ids') or [] if str(value)})
    if not manual_ids or not context_ids:
        raise CriterionAuthorRuleError('engine-bound criterion evidence allowlists are incomplete')

    def _valid_model_citation(field: str, allowed: set[str]) -> tuple[list[str], bool]:
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            return ([], False)
        normalized = [str(item) for item in value if isinstance(item, str) and str(item)]
        return (normalized, bool(len(normalized) == len(value) and len(normalized) == len(set(normalized)) and (set(normalized) <= allowed)))
    model_manual, manual_valid = _valid_model_citation('manual_anchor_ids', set(manual_ids))
    model_context, context_valid = _valid_model_citation('tree_context_ids', set(context_ids))
    citation_corrected = not (manual_valid and context_valid)
    correction_disclosure = '模型锚引用缺失或越界，已由引擎按信封开放集机械绑定。' if citation_corrected else ''
    if correction_disclosure:
        disclosure = disclosure.rstrip('。；; ') + '；' + correction_disclosure
    from cex_core.engine.case_compiler.behaviour_classes import validate_behaviour_classification
    asked = [{'method': str(row.get('method') or ''), 'object_kind': str(row.get('object_kind') or '')} for row in shape.get('behaviour_classification') or [] if isinstance(row, Mapping)]
    behaviour_rows = validate_behaviour_classification(payload.get('behaviour_classes'), asked=asked) if asked else []
    return [{'shape_key': str(shape.get('shape_key') or ''), 'version_family': str(shape.get('version_family') or ''), 'criterion_type': criterion_type, 'behaviour_classes': behaviour_rows, 'manual_anchor_ids': manual_ids, 'tree_context_ids': context_ids, 'rationale': rationale, 'disclosure': disclosure, 'engine_brief_sha256': str(brief.get('brief_sha256') or ''), 'anchor_citation_corrected': citation_corrected, 'citation_disclosure': correction_disclosure, 'model_citation': {'manual_anchor_ids': model_manual if manual_valid else [], 'tree_context_ids': model_context if context_valid else [], 'manual_provided_count': len(model_manual), 'tree_provided_count': len(model_context), 'manual_valid': manual_valid, 'tree_valid': context_valid, 'valid': not citation_corrected}}]
_SHAPE_OUTER_ATTEMPTS = 2

def _non_retryable_fork_causes() -> frozenset[str]:
    try:
        from cex_core.engine.ist_core.resilience import NON_RETRYABLE_FORK_CAUSES
        return NON_RETRYABLE_FORK_CAUSES
    except Exception:
        return frozenset({'LLM_QUOTA_EXHAUSTED', 'CANCELLED', 'ABANDONED_BEFORE_DISPATCH'})

def _fork_termination_cause(termination_cause: Callable[[], str] | None) -> str:
    if termination_cause is None:
        return ''
    try:
        return str(termination_cause() or '').strip()
    except Exception:
        return ''

def adjudicate_single_shape_with_retry(brief: Mapping[str, Any], invoke: Callable[[str, int], str], *, non_retryable: Callable[[Exception], bool] | None=None, termination_cause: Callable[[], str] | None=None) -> dict[str, Any]:
    shapes = [row for row in brief.get('shapes') or [] if isinstance(row, Mapping)]
    if len(shapes) != 1:
        raise CriterionAuthorRuleError('single-shape retry received a non-single brief')
    errors: list[str] = []
    wire = serialize_engine_adjudication_brief(brief)
    last_attempt = 0

    def _unavailable(attempt: int) -> dict[str, Any]:
        return {'status': 'unavailable', 'attempts': attempt, 'shape': dict(shapes[0]), 'decisions': [], 'errors': errors}
    for attempt in range(1, _SHAPE_OUTER_ATTEMPTS + 1):
        last_attempt = attempt
        try:
            reply = invoke(wire, attempt)
        except Exception as exc:
            cause = _fork_termination_cause(termination_cause)
            if cause in _non_retryable_fork_causes():
                errors.append(f'{cause}: {type(exc).__name__}: {exc}'[:400])
                return _unavailable(attempt)
            if non_retryable is not None and non_retryable(exc):
                raise
            errors.append(f'{type(exc).__name__}: {exc}'[:400])
            continue
        cause = _fork_termination_cause(termination_cause)
        if cause in _non_retryable_fork_causes():
            errors.append(f"{cause}: {str(reply or '')[:300]}")
            return _unavailable(attempt)
        try:
            decisions = parse_engine_adjudication_result(reply, brief=brief)
        except Exception as exc:
            if non_retryable is not None and non_retryable(exc):
                raise
            errors.append(f'{type(exc).__name__}: {exc}'[:400])
            continue
        from cex_core.engine.common import typesafe_shadow
        typesafe_shadow.shadow_criterion_adjudication(wire=wire, decisions=decisions)
        return {'status': 'decided', 'attempts': attempt, 'shape': dict(shapes[0]), 'decisions': decisions, 'errors': errors}
    return _unavailable(last_attempt)

def _append_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 384)
    try:
        for record in records:
            raw = (json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
            offset = 0
            while offset < len(raw):
                written = os.write(fd, raw[offset:])
                if written <= 0:
                    raise CriterionAuthorRuleError('criterion rule append made no progress')
                offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    if not existed and hasattr(os, 'O_DIRECTORY'):
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

def _persist_behaviour_classes(decisions: Sequence[Mapping[str, Any]]) -> int:
    from cex_core.engine.case_compiler.behaviour_classes import persist_behaviour_classes
    rows = [row for decision in decisions if isinstance(decision, Mapping) for row in decision.get('behaviour_classes') or [] if isinstance(row, Mapping)]
    if not rows:
        return 0
    try:
        return len(persist_behaviour_classes(rows))
    except Exception:
        logger.warning('behaviour class ledger append failed', exc_info=True)
        return 0

def persist_engine_adjudications(decisions: Sequence[Mapping[str, Any]], *, brief: Mapping[str, Any], path: Path | None=None, answer_path: Path | None=None, manual_version: str | None=None) -> list[dict[str, Any]]:
    target = Path(path or AUTHOR_RULE_PATH)
    resolved_manual_version = str(manual_version or brief.get('manual_version') or resolve_compile_manual_version() or '')
    lock_path = target.with_name(target.name + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    lock_fd = os.open(lock_path, flags, 384)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        active, history = _history_state(path=target, answer_path=answer_path, manual_version=resolved_manual_version or None)
        anchors = {str(row.get('anchor_id') or ''): dict(row) for row in brief.get('manual_anchors') or [] if isinstance(row, Mapping)}
        contexts = {str(row.get('context_id') or ''): dict(row) for row in brief.get('tree_context') or [] if isinstance(row, Mapping)}
        catalogue = {str(row.get('criterion_type') or ''): dict(row) for row in brief.get('criterion_types') or [] if isinstance(row, Mapping)}
        shapes = {(str(row.get('shape_key') or ''), str(row.get('version_family') or '')): row for row in brief.get('shapes') or [] if isinstance(row, Mapping)}
        records: list[dict[str, Any]] = []
        new_records: list[dict[str, Any]] = []
        from cex_core.engine.kms.manual_chapter_locator import anchor_chapter_pins_partial
        for decision in decisions:
            shape_key = str(decision.get('shape_key') or '')
            version_family = str(decision.get('version_family') or '')
            reuse_key = (shape_key, resolved_manual_version) if resolved_manual_version else (shape_key, version_family)
            if reuse_key in active:
                records.append(active[reuse_key])
                continue
            prior = (history.get(reuse_key) or history.get((shape_key, version_family)) or [])[-1:]
            veto = _veto_receipt(prior[0], answer_path=answer_path) if prior else None
            cause = supersede_cause(prior[0], veto=veto, manual_version=resolved_manual_version) if prior else None
            if prior and veto is None and _rule_reusable(prior[0], manual_version=resolved_manual_version):
                raise CriterionAuthorRuleError('reusable criterion rule was not returned as active')
            generation = int(prior[0].get('generation') or 0) + 1 if prior else 1
            criterion_type = str(decision.get('criterion_type') or '')
            manual_anchor_rows = [anchors[value] for value in decision['manual_anchor_ids']]
            evidence_chain = {'manual_anchors': manual_anchor_rows, 'tree_context': [contexts[value] for value in decision['tree_context_ids']], 'language': catalogue[criterion_type]}
            anchor_chapter_shas: dict[str, dict[str, str]] = {}
            catalog_pins: dict[str, dict[str, str]] = {}
            pin_failures: list[dict[str, str]] = []
            if resolved_manual_version:
                anchor_chapter_shas, pin_failures = anchor_chapter_pins_partial(manual_anchor_rows, manual_version=resolved_manual_version)
                catalog_pins = _catalog_pins(resolved_manual_version, _families_from_anchors(manual_anchor_rows))
            identity = {'kind': 'engine_adjudication', 'adjudicator': 'criterion-adjudicator', 'brief_sha256': str(decision.get('engine_brief_sha256') or ''), 'decision_sha256': _sha256({key: value for key, value in dict(decision).items() if key != 'behaviour_classes'}), 'evidence_chain': evidence_chain}
            body = {'schema': ENGINE_RULE_SCHEMA, 'rule_id': f'criterion.engine.{shape_key[:16]}.g{generation}', 'shape_key': shape_key, 'version_family': version_family, 'manual_version': resolved_manual_version, 'generation': generation, 'output': {'criterion_type': criterion_type, 'mode': 'direct'}, 'identity': identity, 'anchor_chapter_shas': anchor_chapter_shas, 'catalog_pins': catalog_pins, 'pin_failures': pin_failures, 'rationale': str(decision.get('rationale') or ''), 'disclosure': str(decision.get('disclosure') or ''), 'anchor_citation_corrected': bool(decision.get('anchor_citation_corrected')), 'citation_disclosure': str(decision.get('citation_disclosure') or ''), 'model_citation': dict(decision.get('model_citation') or {}), 'members': list((shapes.get((shape_key, version_family)) or {}).get('members') or []), 'created_at': time.time(), 'supersede_cause': cause, 'supersedes_rule_sha256': str(prior[0].get('rule_sha256') or '') if prior else None}
            record = {**body, 'rule_sha256': _sha256(body)}
            records.append(record)
            new_records.append(record)
        if new_records:
            _append_records(target, new_records)
        _persist_behaviour_classes(decisions)
        return records
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

def fixture_value_disclosures(mechanical_case: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block_index, block in enumerate(mechanical_case.get('blocks') or []):
        if not isinstance(block, Mapping) or str(block.get('kind') or '').upper() != 'OBSERVE_ASSERT':
            continue
        for assert_index, assertion in enumerate(block.get('asserts') or []):
            if not isinstance(assertion, Mapping):
                continue
            binding = assertion.get('binding_input')
            if not isinstance(binding, Mapping) or binding.get('rule_id') != 'config.fixture-literal-backref' or (not isinstance(binding.get('source_input'), Mapping)):
                continue
            source_input = binding['source_input']
            rows.append({'expectation_id': str(assertion.get('expectation_id') or ''), 'fixture_kind': str(source_input.get('fixture_kind') or ''), 'value': str(source_input.get('value') or ''), 'config_block_index': int(source_input.get('config_block_index') or 0), 'config_command_index': int(source_input.get('config_command_index') or 0), 'assert_block_index': block_index, 'assert_index': assert_index})
    return rows

def criterion_pending_from_ledgers(ledgers: Mapping[str, Mapping[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    found: list[tuple[str, list[dict[str, Any]]]] = []
    for aid, ledger in sorted(ledgers.items()):
        for claim in ledger.get('claims') or []:
            if not isinstance(claim, dict) or claim.get('claim_kind') != 'criterion_rule_batch':
                continue
            rows = claim.get('criterion_claims')
            if isinstance(rows, list) and rows and all((isinstance(row, dict) for row in rows)):
                found.append((str(aid), [dict(row) for row in rows]))
    if not found:
        return ('', [])
    if len(found) != 1:
        raise CriterionAuthorRuleError('multiple criterion batch ledgers are present')
    return found[0]

def build_batch_criterion_questions(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    raise CriterionAuthorRuleError('criterion author-confirmation questions are retired')

def persist_author_rule_answer(*_args: Any, **_kwargs: Any) -> dict[str, Any] | None:
    raise CriterionAuthorRuleError('direct author criterion signing is retired')
__all__ = ['ADJUDICATION_BRIEF_SCHEMA', 'AUTHOR_RULE_PATH', 'CriterionAuthorRuleError', 'ENGINE_RULE_SCHEMA', 'SUPERSEDE_CAUSES', 'VETO_ANSWER', 'adjudicate_single_shape_with_retry', 'build_batch_criterion_questions', 'build_criterion_veto_question', 'build_engine_adjudication_brief', 'clear_author_rule_cache', 'criterion_pending_from_ledgers', 'fixture_value_disclosures', 'load_author_rules', 'load_criterion_rules', 'parse_engine_adjudication_result', 'persist_author_rule_answer', 'persist_engine_adjudications', 'resolve_compile_manual_version', 'round_rule_supply', 'serialize_engine_adjudication_brief', 'split_engine_adjudication_briefs', 'supersede_cause']
