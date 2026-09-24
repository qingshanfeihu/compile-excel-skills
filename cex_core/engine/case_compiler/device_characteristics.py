# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/device_characteristics.py（sha256 b39a9377fccac182）。不在这里手改。
from __future__ import annotations
import json
import logging
import ntpath
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from cex_core.engine.knowledge_paths import KNOWLEDGE_DATA_ROOT
logger = logging.getLogger(__name__)
CHARACTERISTICS_PATH = KNOWLEDGE_DATA_ROOT / 'compile_ref' / 'device_characteristics.json'
CHARACTERISTICS_SCHEMA = 'ist.device-characteristics'
PINNED_SOURCE_ROOTS: Mapping[str, str] = {'manual': 'knowledge/data/manual/', 'spec': 'knowledge/data/spec/'}
UNCLASSIFIED = 'unclassified'
TIERS: tuple[str, ...] = ('T1', 'T2', 'T3', 'T4')
DISCLOSURE_CODES: tuple[str, ...] = ('authored_count', 'sampling_required', 'count_is_worker_declared', 'device_decides', 'characteristic', 'structure_characteristic', 'behaviour_unclassified', 'counter_field_undocumented', 'no_characteristic_for_pair', 'no_object_kind_declared', 'trigger_echo_bounded', 'characteristics_unavailable', 'observation_pairing_unavailable', 'characteristics_truncated', 'characteristic_scope_unverified')
MAX_PINNED_SOURCE_BYTES = 32 * 1024 * 1024

def _max_detail_chars() -> int:
    from cex_core.engine.case_compiler.step_structure import MAX_VALUE_CHARS
    return int(MAX_VALUE_CHARS)
MAX_FACTS_PER_TIER = 12
MAX_DISCLOSURE_MESSAGE_CHARS = 400
_cache: dict[str, Any] = {}

def load_device_characteristics() -> dict[str, Any] | None:
    try:
        mtime = CHARACTERISTICS_PATH.stat().st_mtime_ns
    except OSError:
        return None
    if _cache.get('mtime') == mtime:
        return _cache.get('data')
    try:
        data = json.loads(CHARACTERISTICS_PATH.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        logger.warning('device characteristics projection is unreadable', exc_info=True)
        return None
    if not isinstance(data, dict) or str(data.get('schema') or '') != CHARACTERISTICS_SCHEMA:
        return None
    if not _pinned_sources_confined(data):
        logger.warning('device characteristics projection pins a path outside knowledge/')
        _cache.update(mtime=mtime, data=None)
        return None
    if not _pinned_sources_unchanged(data):
        logger.warning('device characteristics projection is stale for its sources')
        _cache.update(mtime=mtime, data=None)
        return None
    _cache.update(mtime=mtime, data=data)
    return data

def pinned_source_is_confined(rel: Any) -> bool:
    text = str(rel or '')
    if not text or text != text.strip():
        return False
    raw = PurePosixPath(text)
    if raw.is_absolute() or ntpath.isabs(text) or '\\' in text:
        return False
    if any((part in ('..', '') for part in raw.parts)):
        return False
    normalized = raw.as_posix()
    return any((normalized.startswith(prefix) and len(normalized) > len(prefix) for prefix in PINNED_SOURCE_ROOTS.values()))

def _pinned_sources_confined(data: Mapping[str, Any]) -> bool:
    pinned = (data.get('identity') or {}).get('pinned_sources') or {}
    if not isinstance(pinned, Mapping) or not pinned:
        return False
    return all((pinned_source_is_confined(rel) for rel in pinned))

def read_pinned_source_bytes(rel: str) -> bytes:
    from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
    root = KNOWLEDGE_DATA_ROOT.parent.parent
    if not pinned_source_is_confined(rel):
        raise ValueError(f'pinned source is outside knowledge/: {rel!r}')
    raw = read_regular_nofollow(rel, error_type=OSError, invalid_message=f'pinned source path is not readable: {rel}', directory_message=f'pinned source is a directory: {rel}', open_message=f'pinned source could not be opened: {rel}', bounds_message=f'pinned source is out of bounds: {rel}', changed_message=f'pinned source changed while reading: {rel}', max_bytes=MAX_PINNED_SOURCE_BYTES, trusted_root=root)
    return raw if isinstance(raw, bytes) else bytes(raw)

def _pinned_sources_unchanged(data: Mapping[str, Any]) -> bool:
    import hashlib
    pinned = (data.get('identity') or {}).get('pinned_sources') or {}
    if not isinstance(pinned, Mapping) or not pinned:
        return False
    for rel, expected in pinned.items():
        try:
            actual = hashlib.sha256(read_pinned_source_bytes(str(rel))).hexdigest()
        except (OSError, ValueError):
            return False
        if actual != str(expected):
            return False
    return True

def clear_characteristics_cache() -> None:
    _cache.clear()

def behaviour_class_closed_set() -> frozenset[str] | None:
    data = load_device_characteristics()
    if not data:
        return None
    rows = data.get('behaviour_classes')
    if not isinstance(rows, list) or not rows:
        return None
    ids = {str(row.get('id') or '') for row in rows if isinstance(row, Mapping) and str(row.get('id') or '')}
    return frozenset(ids) if ids else None

def characteristic_facts() -> list[dict[str, Any]]:
    data = load_device_characteristics()
    if not data:
        return []
    return [row for row in data.get('facts') or [] if isinstance(row, Mapping)]

def structure_predicate_specs() -> list[dict[str, Any]]:
    data = load_device_characteristics()
    if not data:
        return []
    return [row for row in data.get('structure_predicates') or [] if isinstance(row, Mapping)]

def _text(value: Any, limit: int | None=None) -> str:
    raw = str(value if value is not None else '')
    return raw[:limit if limit is not None else _max_detail_chars()]

def _stated_values(entry: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for item in entry.get('stated_conditions') or ():
        if not isinstance(item, Mapping):
            continue
        out.append(_text(item.get('value')))
        out.append(_text(item.get('text'), 2000))
    return [value for value in out if value]

def _weight_declarations(entries: Sequence[Mapping[str, Any]], case: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    from cex_core.engine.case_compiler.step_structure import concretized_weights, stated_weights
    out: list[tuple[str, str]] = []
    for entry in entries:
        number = str(entry.get('n') or '').strip()
        for weights in (stated_weights(entry), concretized_weights(case or {}, entry)):
            if weights:
                out.append((number, ':'.join((str(value) for value in weights))))
    return out

def _structure_signal_steps(entries: Sequence[Mapping[str, Any]], spec: Mapping[str, Any]) -> list[str]:
    from cex_core.engine.case_compiler.step_structure import _norm_head_tokens, command_role_atlas
    roles = {str(v) for v in spec.get('roles') or ()}
    classes = {str(v) for v in spec.get('command_classes') or ()}
    atlas = command_role_atlas() if classes else None
    hits: list[str] = []
    for entry in entries:
        number = str(entry.get('n') or '').strip()
        if not number:
            continue
        matched = any((isinstance(item, Mapping) and str(item.get('role') or '') in roles for item in entry.get('objects') or ()))
        if not matched and atlas is not None:
            for item in entry.get('operations') or ():
                if not isinstance(item, Mapping):
                    continue
                tokens = _norm_head_tokens(item.get('head'))
                if tokens and atlas.command_class(tokens) in classes:
                    matched = True
                    break
        if matched:
            hits.append(number)
    return hits

def _stated_token_steps(entries: Sequence[Mapping[str, Any]], spec: Mapping[str, Any]) -> list[str]:
    groups = [{str(token) for token in group} for group in spec.get('token_groups') or () if isinstance(group, list) and group]
    if not groups:
        return []
    per_group_steps: list[list[str]] = []
    for group in groups:
        hits: list[str] = []
        for entry in entries:
            number = str(entry.get('n') or '').strip()
            if not number:
                continue
            folded = ' '.join(_stated_values(entry)).casefold()
            if any((token in folded for token in group)):
                hits.append(number)
        per_group_steps.append(hits)
    if str(spec.get('match') or '') == 'all':
        if not all(per_group_steps):
            return []
    elif not any(per_group_steps):
        return []
    ordered: list[str] = []
    for hits in per_group_steps:
        for number in hits:
            if number not in ordered:
                ordered.append(number)
    return ordered

def evaluate_structure_predicates(structure: Sequence[Mapping[str, Any]], *, case: Mapping[str, Any] | None=None) -> dict[str, list[str]]:
    entries = [entry for entry in structure if isinstance(entry, Mapping)]
    if not entries:
        return {}
    hits: dict[str, list[str]] = {}
    for spec in structure_predicate_specs():
        ident = str(spec.get('id') or '')
        evaluator = str(spec.get('evaluator') or '')
        if not ident:
            continue
        if evaluator == 'structure_signal':
            steps = _structure_signal_steps(entries, spec)
        elif evaluator == 'weight_declarations':
            declarations = _weight_declarations(entries, case)
            least = spec.get('distinct_at_least')
            least = least if isinstance(least, int) and (not isinstance(least, bool)) else 2
            distinct = {value for _step, value in declarations}
            steps = [step for step, _value in declarations] if len(distinct) >= least else []
        elif evaluator == 'stated_tokens':
            steps = _stated_token_steps(entries, spec)
        else:
            steps = []
        if steps:
            ordered: list[str] = []
            for number in steps:
                if number not in ordered:
                    ordered.append(number)
            hits[ident] = ordered
    return hits

def characteristics_for(*, object_kinds: Iterable[str]=(), behaviour_classes: Iterable[str]=(), structure_predicates: Iterable[str]=(), require_predicate: bool=False) -> list[dict[str, Any]]:
    return _filter_pool(characteristic_facts(), object_kinds=object_kinds, behaviour_classes=behaviour_classes, structure_predicates=structure_predicates, require_predicate=require_predicate)

def _disclosure(tier: str, code: str, *, fact: Mapping[str, Any] | None=None, **detail: Any) -> dict[str, Any]:
    if code not in DISCLOSURE_CODES:
        raise ValueError(f'device disclosure code is outside the closed set: {code!r}')
    row: dict[str, Any] = {'tier': tier, 'code': code, 'fact_id': str((fact or {}).get('id') or ''), 'characteristic_class': str((fact or {}).get('characteristic_class') or ''), 'locator': str((fact or {}).get('locator') or ''), 'pinned': str((fact or {}).get('pinned') or ''), 'quote': str((fact or {}).get('quote') or ''), 'text': str((fact or {}).get('text') or ''), 'detail': {key: value for key, value in detail.items() if value not in ('', None)}}
    observation = (fact or {}).get('observation')
    if isinstance(observation, Mapping):
        row['observation'] = dict(observation)
    return row

def _predicate_label(predicate_id: str) -> str:
    for spec in structure_predicate_specs():
        if str(spec.get('id') or '') == str(predicate_id or ''):
            return str(spec.get('label_zh') or '')
    return ''

def _authored_counts(entries: Sequence[Mapping[str, Any]], steps: Sequence[str]) -> list[tuple[str, int, str]]:
    from cex_core.engine.case_compiler.step_structure import stated_count_integers
    wanted = {str(value) for value in steps if str(value)}
    if not wanted:
        return []
    out: list[tuple[str, int, str]] = []
    for entry in entries:
        number = str(entry.get('n') or '').strip()
        if number not in wanted:
            continue
        for item in entry.get('stated_conditions') or ():
            if not isinstance(item, Mapping) or str(item.get('kind') or '') != 'count':
                continue
            values = stated_count_integers(item.get('value'))
            source_text = str(item.get('text') or '').strip()
            if len(values) == 1 and source_text:
                row = (number, values[0], source_text)
                if row not in out:
                    out.append(row)
    return out

def select_disclosure(step_structure: Sequence[Mapping[str, Any]], behaviour: Sequence[Mapping[str, Any]]=(), characteristics: Sequence[Mapping[str, Any]] | None=None, *, case: Mapping[str, Any] | None=None, distribution_steps: Sequence[str]=(), has_distribution_criterion: bool=False) -> dict[str, list[dict[str, Any]]]:
    entries = [entry for entry in step_structure if isinstance(entry, Mapping)]
    records = [row for row in behaviour if isinstance(row, Mapping)]
    tiers: dict[str, list[dict[str, Any]]] = {tier: [] for tier in TIERS}
    kinds = sorted({str(item.get('kind') or '') for entry in entries for item in entry.get('objects') or () if isinstance(item, Mapping) and str(item.get('kind') or '')})
    classes = sorted({str(row.get('behaviour_class') or '') for row in records if str(row.get('behaviour_class') or '') and str(row.get('behaviour_class') or '') != UNCLASSIFIED})
    if has_distribution_criterion:
        for number, value, source_text in _authored_counts(entries, distribution_steps)[:MAX_FACTS_PER_TIER]:
            tiers['T1'].append(_disclosure('T1', 'authored_count', step=number, count=value, source_text=source_text))
        tiers['T1'].append(_disclosure('T1', 'sampling_required'))
        tiers['T1'].append(_disclosure('T1', 'count_is_worker_declared'))
        tiers['T1'].append(_disclosure('T1', 'device_decides'))
    available = characteristics is not None or load_device_characteristics() is not None
    if not available:
        tiers['T4'].append(_disclosure('T4', 'characteristics_unavailable'))
        return tiers
    pool = [dict(row) for row in characteristics if isinstance(row, Mapping)] if characteristics is not None else None

    def _select(**kwargs: Any) -> list[dict[str, Any]]:
        if pool is None:
            return characteristics_for(**kwargs)
        return _filter_pool(pool, **kwargs)
    shown: list[Mapping[str, Any]] = []
    matched = _select(object_kinds=kinds, behaviour_classes=classes)
    for fact in matched[:MAX_FACTS_PER_TIER]:
        tiers['T2'].append(_disclosure('T2', 'characteristic', fact=fact))
        shown.append(fact)
    if len(matched) > MAX_FACTS_PER_TIER:
        tiers['T4'].append(_disclosure('T4', 'characteristics_truncated'))
    predicate_hits = evaluate_structure_predicates(entries, case=case)
    for fact in _select(object_kinds=kinds, behaviour_classes=classes, structure_predicates=list(predicate_hits), require_predicate=True)[:MAX_FACTS_PER_TIER]:
        fired = [name for name in (fact.get('applies_to') or {}).get('structure_predicates') or () if name in predicate_hits]
        steps = sorted({number for name in fired for number in predicate_hits.get(name, [])})
        tiers['T3'].append(_disclosure('T3', 'structure_characteristic', fact=fact, predicates=fired, steps=steps, label_zh=_predicate_label(fired[0]) if fired else ''))
        shown.append(fact)
    unverified = _unverified_object_scope_facts(pool if pool is not None else characteristic_facts(), object_kinds=kinds, behaviour_classes=classes, structure_predicates=list(predicate_hits))
    for fact in unverified[:MAX_FACTS_PER_TIER]:
        applies = fact.get('applies_to') or {}
        tiers['T4'].append(_disclosure('T4', 'characteristic_scope_unverified', fact=fact, object_kinds=kinds, documented_object_kinds=sorted((str(value) for value in applies.get('object_kinds') or ()))))
    if len(unverified) > MAX_FACTS_PER_TIER and (not any((row.get('code') == 'characteristics_truncated' for row in tiers['T4']))):
        tiers['T4'].append(_disclosure('T4', 'characteristics_truncated'))
    for row in records:
        if str(row.get('behaviour_class') or '') == UNCLASSIFIED:
            tiers['T4'].append(_disclosure('T4', 'behaviour_unclassified', method=_text(row.get('method')), object_kind=_text(row.get('object_kind'))))
    for fact in shown:
        observation = fact.get('observation')
        if isinstance(observation, Mapping) and (not observation.get('fields_documented')):
            tiers['T4'].append(_disclosure('T4', 'counter_field_undocumented', fact=fact, show_command=_text(observation.get('show_command'))))
    if not tiers['T2'] and (not tiers['T3']):
        if kinds:
            tiers['T4'].append(_disclosure('T4', 'no_characteristic_for_pair', object_kinds=kinds, behaviour_classes=classes or [UNCLASSIFIED]))
        else:
            tiers['T4'].append(_disclosure('T4', 'no_object_kind_declared', behaviour_classes=classes or [UNCLASSIFIED]))
    if has_distribution_criterion:
        tiers['T4'].append(_disclosure('T4', 'trigger_echo_bounded'))
    return tiers

def _unverified_object_scope_facts(pool: Sequence[Mapping[str, Any]], *, object_kinds: Sequence[str], behaviour_classes: Sequence[str], structure_predicates: Sequence[str]) -> list[dict[str, Any]]:
    kinds = set(object_kinds)
    namespaces = {kind.split('/', 1)[0] for kind in kinds if '/' in kind}
    if not namespaces or not structure_predicates:
        return []
    scoped = [fact for fact in pool if isinstance(fact, Mapping) and isinstance(fact.get('applies_to'), Mapping)]
    documented = {str(kind) for fact in scoped for kind in (fact.get('applies_to') or {}).get('object_kinds') or () if str(kind).split('/', 1)[0] in namespaces}
    candidates = _filter_pool(scoped, object_kinds=documented - kinds, behaviour_classes=behaviour_classes, structure_predicates=structure_predicates, require_predicate=True)
    return [fact for fact in candidates if not kinds.intersection((str(kind) for kind in (fact.get('applies_to') or {}).get('object_kinds') or ()))]

def _filter_pool(pool: Sequence[Mapping[str, Any]], *, object_kinds: Iterable[str]=(), behaviour_classes: Iterable[str]=(), structure_predicates: Iterable[str]=(), require_predicate: bool=False) -> list[dict[str, Any]]:
    kinds = {str(value) for value in object_kinds if str(value)}
    classes = {str(value) for value in behaviour_classes if str(value)}
    predicates = {str(value) for value in structure_predicates if str(value)}
    if not kinds:
        return []
    out: list[dict[str, Any]] = []
    for fact in pool:
        applies = fact.get('applies_to')
        if not isinstance(applies, Mapping):
            continue
        fact_kinds = {str(v) for v in applies.get('object_kinds') or ()}
        fact_classes = {str(v) for v in applies.get('behaviour_classes') or ()}
        fact_predicates = {str(v) for v in applies.get('structure_predicates') or ()}
        if not fact_kinds & kinds:
            continue
        if fact_classes and classes and (not fact_classes & classes):
            continue
        if require_predicate:
            if not fact_predicates or not fact_predicates & predicates:
                continue
        elif fact_predicates:
            continue
        out.append(dict(fact))
    return out
DEVICE_DISCLOSURE_FACT_EVENT = 'device_disclosure'
MAX_DISCLOSURE_ROWS = 40

def device_disclosure_fact(*, aid: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    kept = [{'tier': str(row.get('tier') or ''), 'code': str(row.get('reason_code') or row.get('code') or ''), 'message': str(row.get('message') or '')[:MAX_DISCLOSURE_MESSAGE_CHARS], 'locator': str(row.get('locator') or '')} for row in rows or () if isinstance(row, Mapping) and str(row.get('message') or '').strip()]
    return {'ev': DEVICE_DISCLOSURE_FACT_EVENT, 'aid': str(aid or ''), 'rows': kept[:MAX_DISCLOSURE_ROWS], 'row_count': len(kept)}

def observation_pairing_unavailable_disclosure() -> dict[str, Any]:
    return _disclosure('T4', 'observation_pairing_unavailable')
MECHANICAL_FINDING_CODES: tuple[str, ...] = ('feature_prerequisite_missing', 'query_target_not_listener', 'trigger_host_not_paired_with_target', 'query_target_not_on_device', 'bed_facts_unavailable')
PREREQUISITE_RULE_CODES: Mapping[str, str] = {'enabling_step_present': 'feature_prerequisite_missing', 'query_target_bound_to_head': 'query_target_not_listener'}
MAX_MECHANICAL_FINDINGS = 12
MAX_FINDING_BLOCKS = 12
MAX_FINDING_BLOCK_INDEX = 4096
MAX_FINDING_NAMES = 12
MAX_FINDING_NAME_CHARS = 64
MAX_FINDING_LOCATOR_CHARS = 256
MAX_FINDING_QUOTE_CHARS = 1200
MAX_FINDING_ROW_BYTES = 32 * 1024
MAX_MECHANICAL_FINDINGS_BYTES = MAX_MECHANICAL_FINDINGS * MAX_FINDING_ROW_BYTES + 4096
PREREQUISITE_FINDING_FACT_EVENT = 'prerequisite_finding'
MECHANICAL_FINDINGS_SCHEMA = 'ist.mechanical-findings'

def _norm_ip(value: Any) -> str:
    import ipaddress
    text = str(value or '').strip().strip('[]')
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return ''

def _block_commands(block: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    single = block.get('cmd')
    if isinstance(single, str) and single.strip():
        out.append(single)
    for item in block.get('cmds') or ():
        if isinstance(item, str) and item.strip():
            out.append(item)
    if str(block.get('kind') or '').strip().upper() == 'STEP':
        try:
            from cex_core.engine.case_compiler.blocks import _DUT_HOSTS
            from cex_core.engine.case_compiler.mechanical_case_gate import _is_config_establishing_block
        except Exception:
            return out
        if _is_config_establishing_block(block, _DUT_HOSTS):
            for line in str(block.get('G') or '').splitlines():
                if line.strip():
                    out.append(line)
    return out

def _resolver_queries(command: str, predicate: Mapping[str, Any]) -> list[str]:
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    if str(predicate.get('evaluator') or '') != 'resolver_query':
        return []
    tools = {str(tool).casefold() for tool in predicate.get('query_tools') or () if str(tool or '').strip()}
    marker = str(predicate.get('server_marker') or '')
    if not tools or len(marker) != 1:
        return []
    tokens = norm_command_tokens(command)
    out: list[str] = []
    for index, token in enumerate(tokens):
        if token.casefold() not in tools:
            continue
        for offset in range(index + 1, len(tokens)):
            candidate = tokens[offset]
            if candidate.casefold() in tools:
                break
            if candidate.startswith(marker):
                target = _norm_ip(candidate[len(marker):])
                if target:
                    out.append(target)
                break
    return out

class _BedPairing:
    __slots__ = ('available', 'trigger_hosts', 'paired', 'carried')

    def __init__(self, bed_facts: Mapping[str, Any] | None) -> None:
        self.available = False
        self.trigger_hosts: frozenset[str] = frozenset()
        self.paired: dict[str, tuple[str, ...]] = {}
        self.carried: dict[str, str] = {}
        if not isinstance(bed_facts, Mapping):
            return
        reach = bed_facts.get('reachability')
        rows = (reach or {}).get('listener_trigger_pairs') if isinstance(reach, Mapping) else None
        triggers: set[str] = set()
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                listener = _norm_ip(row.get('listener_ip'))
                hosts = tuple((str(host or '').strip().casefold() for host in row.get('trigger_hosts') or () if str(host or '').strip()))
                if not listener:
                    continue
                self.paired[listener] = hosts
                triggers.update(hosts)
        for row in bed_facts.get('target_device_carried_addresses') or ():
            if not isinstance(row, Mapping):
                continue
            device = str(row.get('device') or '').strip()
            for address in row.get('addresses') or ():
                normalized = _norm_ip(address)
                if normalized and normalized not in self.carried:
                    self.carried[normalized] = device
        listener_owners = {self.carried[address] for address in self.paired if address in self.carried}
        for row in bed_facts.get('target_device_carried_addresses') or ():
            if not isinstance(row, Mapping):
                continue
            device = str(row.get('device') or '').strip()
            if device and device not in listener_owners:
                triggers.add(device.casefold())
        self.trigger_hosts = frozenset(triggers)
        self.available = bool(self.paired) and bool(self.trigger_hosts)

def _prerequisite_facts() -> list[dict[str, Any]]:
    return [fact for fact in characteristic_facts() if str(fact.get('characteristic_class') or '') == 'prerequisites' and fact.get('enabling_command_heads') and (str(fact.get('prerequisite_rule') or '') in PREREQUISITE_RULE_CODES)]

def _observation_predicate(ident: str) -> dict[str, Any] | None:
    data = load_device_characteristics()
    for row in (data or {}).get('observation_predicates') or ():
        if isinstance(row, Mapping) and str(row.get('id') or '') == str(ident or ''):
            return dict(row)
    return None

def _finding(code: str, *, fact: Mapping[str, Any] | None=None, **detail: Any) -> dict[str, Any]:
    if code not in MECHANICAL_FINDING_CODES:
        raise ValueError(f'mechanical finding code is outside the closed set: {code!r}')
    row: dict[str, Any] = {'code': code, 'fact_id': _text((fact or {}).get('id'), MAX_FINDING_LOCATOR_CHARS), 'locator': _text((fact or {}).get('locator'), MAX_FINDING_LOCATOR_CHARS), 'quote': _text((fact or {}).get('quote'), MAX_FINDING_QUOTE_CHARS), 'text': _text((fact or {}).get('text'), MAX_FINDING_QUOTE_CHARS)}
    for key, value in detail.items():
        if value in ('', None):
            continue
        if key in ('host', 'target'):
            row[key] = _text(value, MAX_FINDING_NAME_CHARS)
        elif key == 'paired_hosts':
            row[key] = [_text(name, MAX_FINDING_NAME_CHARS) for name in value or ()][:MAX_FINDING_NAMES]
        else:
            row[key] = value
    return row

def mechanical_findings(case: Mapping[str, Any], *, bed_facts: Mapping[str, Any] | None=None) -> list[dict[str, Any]]:
    from cex_core.engine.case_compiler.scenario_fidelity import object_kind_offset_in_command as _segment_offset, object_kind_segments as _kind_segments
    from cex_core.engine.case_compiler.step_structure import command_role_atlas
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    if not isinstance(case, Mapping):
        return []
    blocks = [row for row in case.get('blocks') or () if isinstance(row, Mapping)]
    if not blocks:
        return []
    facts = _prerequisite_facts()
    if not facts:
        return []
    atlas = command_role_atlas()
    bed = _BedPairing(bed_facts)
    init_tokens = [norm_command_tokens(str(item)) for item in case.get('init_commands') or () if str(item or '').strip()]
    block_tokens: list[list[tuple[str, ...]]] = [[tuple(norm_command_tokens(command)) for command in _block_commands(block)] for block in blocks]
    all_tokens = [tuple(row) for row in init_tokens] + [tokens for row in block_tokens for tokens in row]
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def _add(row: dict[str, Any]) -> None:
        key = (row.get('code'), row.get('fact_id'), row.get('target'), row.get('host'))
        if key in seen:
            return
        seen.add(key)
        out.append(row)
    predicates: list[Mapping[str, Any]] = []
    for fact in facts:
        predicate = _observation_predicate(str(fact.get('observation_predicate') or ''))
        if not predicate:
            continue
        predicates.append(predicate)
        queries = _trigger_queries(blocks, predicate, bed)
        if not queries:
            continue
        kinds = [_kind_segments(kind) for kind in (fact.get('applies_to') or {}).get('object_kinds') or ()]
        configured: list[int] = []
        for index, rows in enumerate(block_tokens):
            for tokens in rows:
                if atlas is not None and atlas.command_class(tokens) != 'write':
                    continue
                if any((segments and _segment_offset(segments, tokens) >= 0 for segments in kinds)):
                    configured.append(index)
                    break
        if not configured:
            continue
        heads = [tuple(str(head).split()) for head in fact.get('enabling_command_heads') or ()]
        rule = str(fact.get('prerequisite_rule') or '')
        code = PREREQUISITE_RULE_CODES.get(rule, '')
        if not code:
            continue
        if rule == 'enabling_step_present':
            seen_heads = sorted({' '.join(head) for head in heads for tokens in all_tokens if len(head) <= len(tokens) and tuple(tokens[:len(head)]) == head})
            if seen_heads:
                continue
            _add(_finding(code, fact=fact, configured_blocks=sorted(set(configured))[:MAX_FINDING_BLOCKS], observed_blocks=sorted({index for index, _, _ in queries})[:MAX_FINDING_BLOCKS]))
        else:
            bound = {_norm_ip(tokens[len(head)]) for head in heads for tokens in all_tokens if len(tokens) > len(head) and tuple(tokens[:len(head)]) == head} - {''}
            for target in sorted({target for _, _, target in queries} - bound):
                _add(_finding(code, fact=fact, target=target, observed_blocks=sorted({index for index, _, value in queries if value == target})[:MAX_FINDING_BLOCKS]))
    queries = sorted({row for predicate in predicates for row in _trigger_queries(blocks, predicate, bed)})
    if not queries:
        return out[:MAX_MECHANICAL_FINDINGS]
    if not bed.available:
        _add(_finding('bed_facts_unavailable'))
        return out[:MAX_MECHANICAL_FINDINGS]
    for target in sorted({value for _, _, value in queries}):
        hosts = sorted({host for _, host, value in queries if value == target and host})
        paired = bed.paired.get(target)
        if paired is None:
            if target in bed.carried:
                continue
            for host in hosts:
                _add(_finding('query_target_not_on_device', host=host, target=target, observed_blocks=sorted({index for index, name, value in queries if value == target and name == host})[:MAX_FINDING_BLOCKS]))
            continue
        allowed = frozenset(paired)
        for host in hosts:
            if host in allowed:
                continue
            _add(_finding('trigger_host_not_paired_with_target', host=host, target=target, paired_hosts=list(paired), observed_blocks=sorted({index for index, name, value in queries if value == target and name == host})[:MAX_FINDING_BLOCKS]))
    return out[:MAX_MECHANICAL_FINDINGS]

def _trigger_queries(blocks: list[Mapping[str, Any]], predicate: Mapping[str, Any], bed: Any) -> list[tuple[int, str, str]]:
    """把观察块里「命令行上写出 @目标」的域名查询抽成 (块号, 触发机, 目标)。

    判据与原先内联的那份逐字同源——提出来只为让配对检查能独立于前置条件规则跑。
    """
    queries: list[tuple[int, str, str]] = []
    for index, block in enumerate(blocks):
        host = str(block.get('host') or '').strip().casefold()
        if not str(block.get('kind') or '').startswith('OBSERVE'):
            continue
        if bed.available and host not in bed.trigger_hosts:
            continue
        if not bed.available and (not host):
            continue
        for command in _block_commands(block):
            for target in _resolver_queries(command, predicate):
                if bed.available and target not in bed.paired and (target in bed.carried):
                    continue
                queries.append((index, host, target))
    return queries

def _finding_block_indices(values: Any) -> list[int]:
    out: list[int] = []
    for value in values or ():
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= index <= MAX_FINDING_BLOCK_INDEX:
            out.append(index)
        if len(out) >= MAX_FINDING_BLOCKS:
            break
    return out

def prerequisite_finding_fact(*, aid: str, findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    from cex_core.engine.ist_core.display_lexicon import mechanical_finding_cn
    kept: list[dict[str, Any]] = []
    for row in findings or ():
        if not isinstance(row, Mapping):
            continue
        code = str(row.get('code') or '')
        if code not in MECHANICAL_FINDING_CODES:
            continue
        message = str(mechanical_finding_cn(row) or '')[:MAX_DISCLOSURE_MESSAGE_CHARS]
        if not message.strip():
            continue
        kept.append({'code': code, 'fact_id': _text(row.get('fact_id'), MAX_FINDING_LOCATOR_CHARS), 'locator': _text(row.get('locator'), MAX_FINDING_LOCATOR_CHARS), 'message': message, 'text': _text(row.get('text'), MAX_DISCLOSURE_MESSAGE_CHARS), 'host': _text(row.get('host'), MAX_FINDING_NAME_CHARS), 'target': _text(row.get('target'), MAX_FINDING_NAME_CHARS), 'paired_hosts': [_text(name, MAX_FINDING_NAME_CHARS) for name in row.get('paired_hosts') or ()][:MAX_FINDING_NAMES], 'configured_blocks': _finding_block_indices(row.get('configured_blocks')), 'observed_blocks': _finding_block_indices(row.get('observed_blocks'))})
    return {'ev': PREREQUISITE_FINDING_FACT_EVENT, 'aid': str(aid or ''), 'rows': kept[:MAX_MECHANICAL_FINDINGS], 'row_count': len(kept)}

def flatten_tiers(tiers: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tier in TIERS:
        for row in tiers.get(tier) or ():
            if isinstance(row, Mapping):
                out.append(dict(row))
    return out
__all__ = ['CHARACTERISTICS_PATH', 'CHARACTERISTICS_SCHEMA', 'DEVICE_DISCLOSURE_FACT_EVENT', 'MAX_FINDING_BLOCKS', 'MAX_FINDING_BLOCK_INDEX', 'MAX_FINDING_LOCATOR_CHARS', 'MAX_FINDING_NAMES', 'MAX_FINDING_NAME_CHARS', 'MAX_FINDING_QUOTE_CHARS', 'MAX_FINDING_ROW_BYTES', 'MAX_MECHANICAL_FINDINGS', 'MAX_MECHANICAL_FINDINGS_BYTES', 'MECHANICAL_FINDINGS_SCHEMA', 'MECHANICAL_FINDING_CODES', 'PREREQUISITE_FINDING_FACT_EVENT', 'PREREQUISITE_RULE_CODES', 'mechanical_findings', 'prerequisite_finding_fact', 'MAX_DISCLOSURE_MESSAGE_CHARS', 'MAX_DISCLOSURE_ROWS', 'DISCLOSURE_CODES', 'MAX_FACTS_PER_TIER', 'PINNED_SOURCE_ROOTS', 'TIERS', 'UNCLASSIFIED', 'behaviour_class_closed_set', 'characteristic_facts', 'characteristics_for', 'device_disclosure_fact', 'clear_characteristics_cache', 'evaluate_structure_predicates', 'flatten_tiers', 'load_device_characteristics', 'observation_pairing_unavailable_disclosure', 'pinned_source_is_confined', 'read_pinned_source_bytes', 'select_disclosure', 'structure_predicate_specs']
