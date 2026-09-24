# 生成：tools/extract_engine.py ← InfoTest scripts/gen_device_characteristics.py（sha256 6a03bb492c0dcfba）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence
ROOT = _cex_data_path('')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cex_core.engine.case_compiler.device_characteristics import MAX_PINNED_SOURCE_BYTES, PINNED_SOURCE_ROOTS, pinned_source_is_confined
DEFAULT_SOURCE = ROOT / 'scripts/data/device_characteristics_source.json'
DEFAULT_OUTPUT = ROOT / 'knowledge/data/compile_ref/device_characteristics.json'
SCHEMA = 'ist.device-characteristics'
SOURCE_SCHEMA = 'ist.device-characteristics-source'
PINNED_ROOTS: Mapping[str, tuple[str, ...]] = {kind: (prefix,) for kind, prefix in PINNED_SOURCE_ROOTS.items()}
PINNED_KINDS: tuple[str, ...] = ('manual', 'spec', 'device')
EVALUATORS: tuple[str, ...] = ('structure_signal', 'weight_declarations', 'stated_tokens')
OBSERVATION_EVALUATORS: tuple[str, ...] = ('resolver_query',)
PREREQUISITE_RULES: tuple[str, ...] = ('enabling_step_present', 'query_target_bound_to_head')
MAX_QUOTE_CHARS = 1200
FIELD_WINDOW_CHARS = 4000
HEAD_WINDOW_CHARS = 600
_ID_RE = re.compile('^[a-z][a-z0-9]*(-[a-z0-9]+){1,11}$')
_TAG_RE = re.compile('<[^>]{1,200}>')
_LEAD_RE = re.compile('^[>\\-\\*\\s]+')
_WS_RE = re.compile('\\s+')

class DeviceCharacteristicsError(RuntimeError):
    pass

def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeviceCharacteristicsError(f'unreadable JSON source: {path}') from exc
    if not isinstance(value, dict):
        raise DeviceCharacteristicsError(f'JSON source must be an object: {path}')
    return value

def plain_text(quote: str) -> str:
    stripped = _TAG_RE.sub(' ', str(quote or ''))
    lines = [_LEAD_RE.sub('', line) for line in stripped.splitlines()]
    return _WS_RE.sub(' ', ' '.join(lines)).strip()

def _ground(rel: str, quote: str) -> dict[str, Any]:
    from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
    from cex_core.engine.case_compiler.mindmap_contract_projector import ground_source_span
    if not rel or not quote.strip():
        raise DeviceCharacteristicsError(f'characteristic has no bounded source: {rel!r}')
    if not pinned_source_is_confined(rel):
        raise DeviceCharacteristicsError(f'characteristic source escapes the pinned documentation trees: {rel}')
    if len(quote) > MAX_QUOTE_CHARS:
        raise DeviceCharacteristicsError(f'characteristic quote exceeds {MAX_QUOTE_CHARS} characters: {rel}')
    raw = read_regular_nofollow(rel, error_type=DeviceCharacteristicsError, invalid_message=f'characteristic source is not a repo file: {rel}', directory_message=f'characteristic source is not a repo file: {rel}', open_message=f'characteristic source is not a readable regular file: {rel}', bounds_message=f'characteristic source is out of bounds: {rel}', changed_message=f'characteristic source changed while reading: {rel}', max_bytes=MAX_PINNED_SOURCE_BYTES, trusted_root=ROOT)
    raw = raw if isinstance(raw, bytes) else bytes(raw)
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise DeviceCharacteristicsError(f'characteristic source is not utf-8: {rel}') from exc
    span = ground_source_span(quote, text, origin='manual')
    if span is None:
        raise DeviceCharacteristicsError(f'characteristic quote is not grounded in its source: {rel}')
    line_start = text.count('\n', 0, int(span['start'])) + 1
    line_end = text.count('\n', 0, int(span['end'])) + 1
    return {'source_path': rel, 'source_sha256': _sha256_bytes(raw), 'source_span': span, 'line_start': line_start, 'line_end': line_end, 'locator': f'{rel}:{line_start}' if line_start == line_end else f'{rel}:{line_start}-{line_end}', '_text': text, '_quote': quote}

def _closed_ids(rows: Any, *, what: str) -> list[dict[str, str]]:
    if not isinstance(rows, list) or not rows:
        raise DeviceCharacteristicsError(f'{what} closed set is unavailable')
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {'id', 'label_zh'}:
            raise DeviceCharacteristicsError(f'{what} entry fields are not closed')
        ident = str(row.get('id') or '').strip()
        label = str(row.get('label_zh') or '').strip()
        if not ident or ident in seen or (not label):
            raise DeviceCharacteristicsError(f'{what} entry identity is invalid: {ident!r}')
        seen.add(ident)
        out.append({'id': ident, 'label_zh': label})
    return out

def _predicates(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise DeviceCharacteristicsError('structure predicates are unavailable')
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise DeviceCharacteristicsError('structure predicate must be an object')
        ident = str(row.get('id') or '').strip()
        label = str(row.get('label_zh') or '').strip()
        evaluator = str(row.get('evaluator') or '').strip()
        if not ident or ident in seen or (not label) or (evaluator not in EVALUATORS):
            raise DeviceCharacteristicsError(f'structure predicate identity or evaluator is invalid: {ident!r}')
        seen.add(ident)
        spec: dict[str, Any] = {'id': ident, 'label_zh': label, 'evaluator': evaluator}
        if evaluator == 'structure_signal':
            roles = [str(v) for v in row.get('roles') or []]
            classes = [str(v) for v in row.get('command_classes') or []]
            if not roles and (not classes):
                raise DeviceCharacteristicsError(f'structure signal predicate names no role or command class: {ident}')
            from cex_core.engine.case_compiler.step_structure import ROLE_COMMAND_CLASSES, STRUCTURE_OBJECT_ROLES
            known_classes = {value for values in ROLE_COMMAND_CLASSES.values() for value in values}
            if not set(roles) <= set(STRUCTURE_OBJECT_ROLES):
                raise DeviceCharacteristicsError(f'structure signal predicate names an unknown role: {ident}')
            if not set(classes) <= known_classes:
                raise DeviceCharacteristicsError(f'structure signal predicate names an unknown command class: {ident}')
            spec['roles'] = sorted(roles)
            spec['command_classes'] = sorted(classes)
        elif evaluator == 'weight_declarations':
            least = row.get('distinct_at_least')
            if not isinstance(least, int) or isinstance(least, bool) or least < 2:
                raise DeviceCharacteristicsError(f'weight predicate needs at least two distinct declarations: {ident}')
            spec['distinct_at_least'] = least
        else:
            groups = row.get('token_groups')
            match = str(row.get('match') or '')
            if not isinstance(groups, list) or not groups or match not in {'all', 'any'} or any((not isinstance(group, list) or not group or any((not isinstance(token, str) or not token.strip() or token != token.casefold() for token in group)) for group in groups)):
                raise DeviceCharacteristicsError(f'token predicate groups are invalid: {ident}')
            spec['match'] = match
            spec['token_groups'] = [sorted({str(t) for t in group}) for group in groups]
        out.append(spec)
    return out

def _observation_predicates(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise DeviceCharacteristicsError('observation predicates are unavailable')
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise DeviceCharacteristicsError('observation predicate must be an object')
        ident = str(row.get('id') or '').strip()
        label = str(row.get('label_zh') or '').strip()
        evaluator = str(row.get('evaluator') or '').strip()
        provenance = str(row.get('provenance') or '').strip()
        if not ident or ident in seen or (not label) or (evaluator not in OBSERVATION_EVALUATORS) or (not provenance):
            raise DeviceCharacteristicsError(f'observation predicate identity, evaluator or provenance is invalid: {ident!r}')
        seen.add(ident)
        if set(row) != {'id', 'label_zh', 'evaluator', 'query_tools', 'server_marker', 'provenance'}:
            raise DeviceCharacteristicsError(f'observation predicate fields are not closed: {ident}')
        tools = row.get('query_tools')
        marker = str(row.get('server_marker') or '')
        if not isinstance(tools, list) or not tools or any((not isinstance(tool, str) or not tool.strip() or tool != tool.casefold() or (tool.split() != [tool]) for tool in tools)) or (len(marker) != 1) or marker.isalnum():
            raise DeviceCharacteristicsError(f'resolver query predicate tools or marker are invalid: {ident}')
        out.append({'id': ident, 'label_zh': label, 'evaluator': evaluator, 'query_tools': sorted({str(tool) for tool in tools}), 'server_marker': marker, 'provenance': provenance})
    return out

def _destructive_patterns() -> list[re.Pattern[str]]:
    from cex_core.engine.case_compiler.domain_grammar import load_grammar
    raw = (load_grammar().get('destructive_commands') or {}).get('patterns') or []
    compiled = [re.compile(str(pattern), re.IGNORECASE) for pattern in raw if str(pattern or '').strip()]
    if not compiled:
        raise DeviceCharacteristicsError('domain grammar carries no destructive_commands.patterns entries')
    return compiled

def _prerequisite(row: Mapping[str, Any], anchor: Mapping[str, Any], *, heads: Mapping[str, Any], predicate_ids: set[str], ident: str) -> dict[str, Any]:
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    raw_heads = row.get('enabling_command_heads')
    rule = str(row.get('prerequisite_rule') or '')
    predicate = str(row.get('observation_predicate') or '')
    if not isinstance(raw_heads, list) or not raw_heads or any((not isinstance(head, str) or not head.strip() for head in raw_heads)):
        raise DeviceCharacteristicsError(f'a prerequisite names at least one enabling command head: {ident}')
    if rule not in PREREQUISITE_RULES:
        raise DeviceCharacteristicsError(f'prerequisite rule is outside the closed set: {ident} ({rule!r})')
    if predicate not in predicate_ids:
        raise DeviceCharacteristicsError(f'prerequisite names an observation predicate outside the closed set: {ident} ({predicate!r})')
    text = str(anchor.get('_text') or '')
    span = anchor.get('source_span') or {}
    start = max(0, int(span.get('start') or 0) - HEAD_WINDOW_CHARS)
    end = int(span.get('end') or 0) + HEAD_WINDOW_CHARS
    section = text[start:end].casefold()
    destructive = _destructive_patterns()
    normalized: list[str] = []
    for head in raw_heads:
        tokens = norm_command_tokens(head)
        joined = ' '.join(tokens)
        if not joined or joined not in heads:
            raise DeviceCharacteristicsError(f'enabling command head is not in the device command tree: {ident} ({head!r})')
        matched = next((pattern for pattern in destructive if pattern.search(joined)), None)
        if matched is not None:
            raise DeviceCharacteristicsError(f'enabling command head matches a destructive command form: {ident} ({head!r}, grammar pattern {matched.pattern!r})')
        for token in tokens:
            if not re.search(f'(?<![0-9a-z_]){re.escape(token)}(?![0-9a-z_])', section):
                raise DeviceCharacteristicsError(f'prerequisite quote does not carry its own command: {ident} ({head!r}, token {token!r})')
        normalized.append(joined)
    return {'enabling_command_heads': sorted(set(normalized)), 'prerequisite_rule': rule, 'observation_predicate': predicate}

def _observation(row: Mapping[str, Any], anchor: Mapping[str, Any], *, heads: Mapping[str, Any]) -> dict[str, Any]:
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    if set(row) != {'show_command', 'fields', 'fields_documented'}:
        raise DeviceCharacteristicsError('observation fields are not closed')
    command = str(row.get('show_command') or '').strip()
    fields = row.get('fields')
    documented = row.get('fields_documented')
    if not isinstance(documented, bool) or not isinstance(fields, list):
        raise DeviceCharacteristicsError('fields must be a list and fields_documented a boolean')
    normalized = ' '.join(norm_command_tokens(command))
    if not normalized or normalized not in heads:
        raise DeviceCharacteristicsError(f'counter command is not in the device command tree: {command!r}')
    names = [str(value) for value in fields]
    if documented:
        if not names or any((not name.strip() for name in names)):
            raise DeviceCharacteristicsError('a documented counter names at least one non-empty field')
        text = str(anchor.get('_text') or '')
        start = int(anchor['source_span']['start'])
        window = text[start:start + FIELD_WINDOW_CHARS]
        for name in names:
            if name not in window:
                raise DeviceCharacteristicsError(f'counter field is not documented next to its command: {name!r}')
    elif names:
        raise DeviceCharacteristicsError('an undocumented counter carries no field name')
    if normalized.split()[0] not in str(anchor.get('_quote') or ''):
        raise DeviceCharacteristicsError(f'counter quote does not carry its own command: {command!r}')
    return {'show_command': normalized, 'fields': names, 'fields_documented': documented}

def build_facts(source: Mapping[str, Any], *, object_kinds: frozenset[str], heads: Mapping[str, Any], behaviour_ids: set[str], characteristic_ids: set[str], predicate_ids: set[str], observation_predicate_ids: set[str]) -> list[dict[str, Any]]:
    rows = source.get('facts')
    if not isinstance(rows, list) or not rows:
        raise DeviceCharacteristicsError('the characteristic table is empty')
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise DeviceCharacteristicsError('characteristic must be an object')
        allowed = {'id', 'characteristic_class', 'pinned', 'source_path', 'quote', 'applies_to', 'observation', 'enabling_command_heads', 'prerequisite_rule', 'observation_predicate'}
        if not set(row) <= allowed or not {'id', 'characteristic_class', 'pinned', 'source_path', 'quote', 'applies_to'} <= set(row):
            raise DeviceCharacteristicsError('characteristic fields are not closed')
        ident = str(row.get('id') or '')
        if not _ID_RE.fullmatch(ident) or ident in seen:
            raise DeviceCharacteristicsError(f'characteristic id is invalid: {ident!r}')
        seen.add(ident)
        cls = str(row.get('characteristic_class') or '')
        if cls not in characteristic_ids:
            raise DeviceCharacteristicsError(f'characteristic class is outside the closed set: {cls!r}')
        pinned = str(row.get('pinned') or '')
        if pinned not in PINNED_KINDS:
            raise DeviceCharacteristicsError(f'pinned kind is invalid: {pinned!r}')
        if pinned == 'device':
            raise DeviceCharacteristicsError('a device-pinned characteristic cannot be issued: device echoes record actual only and sign nothing')
        rel = str(row.get('source_path') or '')
        if not pinned_source_is_confined(rel) or not any((rel.startswith(prefix) for prefix in PINNED_ROOTS[pinned])):
            raise DeviceCharacteristicsError(f'a {pinned}-pinned characteristic must cite that tree: {rel}')
        anchor = _ground(rel, str(row.get('quote') or ''))
        applies = row.get('applies_to')
        if not isinstance(applies, Mapping) or set(applies) != {'object_kinds', 'behaviour_classes', 'structure_predicates'}:
            raise DeviceCharacteristicsError(f'applies_to fields are not closed: {ident}')
        kinds = sorted({str(v) for v in applies.get('object_kinds') or []})
        classes = sorted({str(v) for v in applies.get('behaviour_classes') or []})
        predicates = sorted({str(v) for v in applies.get('structure_predicates') or []})
        if not kinds or not set(kinds) <= object_kinds:
            raise DeviceCharacteristicsError(f'characteristic names an object kind outside the command tree: {ident}')
        if not set(classes) <= behaviour_ids:
            raise DeviceCharacteristicsError(f'characteristic names a behaviour class outside the closed set: {ident}')
        if not set(predicates) <= predicate_ids:
            raise DeviceCharacteristicsError(f'characteristic names a structure predicate outside the closed set: {ident}')
        fact: dict[str, Any] = {'id': ident, 'characteristic_class': cls, 'pinned': pinned, 'locator': anchor['locator'], 'source_path': anchor['source_path'], 'source_sha256': anchor['source_sha256'], 'line_start': anchor['line_start'], 'line_end': anchor['line_end'], 'source_span': anchor['source_span'], 'quote': str(row.get('quote') or ''), 'text': plain_text(str(row.get('quote') or '')), 'applies_to': {'object_kinds': kinds, 'behaviour_classes': classes, 'structure_predicates': predicates}}
        prerequisite_keys = {'enabling_command_heads', 'prerequisite_rule', 'observation_predicate'} & set(row)
        if prerequisite_keys:
            if cls != 'prerequisites':
                raise DeviceCharacteristicsError(f'only a prerequisites characteristic carries an enabling command head: {ident}')
            if len(prerequisite_keys) != 3:
                raise DeviceCharacteristicsError(f'a prerequisite declares its heads, its rule and its observation predicate together: {ident}')
            fact.update(_prerequisite(row, anchor, heads=heads, predicate_ids=observation_predicate_ids, ident=ident))
        elif cls == 'prerequisites':
            raise DeviceCharacteristicsError(f'a prerequisites characteristic must name its enabling command head, its rule and its observation predicate: {ident}')
        if 'observation' in row:
            if cls != 'observation_surface':
                raise DeviceCharacteristicsError(f'only an observation_surface characteristic carries a counter: {ident}')
            observation = row.get('observation')
            if not isinstance(observation, Mapping):
                raise DeviceCharacteristicsError(f'observation must be an object: {ident}')
            fact['observation'] = _observation(observation, anchor, heads=heads)
        elif cls == 'observation_surface':
            raise DeviceCharacteristicsError(f'an observation_surface characteristic must name its counter: {ident}')
        out.append(fact)
    return out

def generate_projection(*, source_path: Path=DEFAULT_SOURCE) -> dict[str, Any]:
    from cex_core.engine.case_compiler.step_structure import object_kind_closed_set
    from cex_core.engine.case_compiler.vendor_stdlib import diagnose_active_command_tree, load_vendor_stdlib
    source = _read_json(source_path)
    if str(source.get('schema') or '') != SOURCE_SCHEMA:
        raise DeviceCharacteristicsError('characteristic source schema is unexpected')
    object_kinds = object_kind_closed_set()
    inventory = load_vendor_stdlib()
    if not object_kinds or not isinstance(inventory, dict):
        _status, detail = diagnose_active_command_tree()
        raise DeviceCharacteristicsError('the device command tree is unavailable; object kinds cannot be validated' + (f'（{detail}）' if detail else ''))
    heads = inventory.get('headers')
    if not isinstance(heads, dict) or not heads:
        raise DeviceCharacteristicsError('the device command tree carries no heads')
    behaviour_classes = _closed_ids(source.get('behaviour_classes'), what='behaviour class')
    characteristic_classes = [str(value) for value in source.get('characteristic_classes') or []]
    if not characteristic_classes or len(set(characteristic_classes)) != len(characteristic_classes):
        raise DeviceCharacteristicsError('characteristic classes are not a closed set')
    predicates = _predicates(source.get('structure_predicates'))
    observation_predicates = _observation_predicates(source.get('observation_predicates'))
    facts = build_facts(source, object_kinds=object_kinds, heads=heads, behaviour_ids={row['id'] for row in behaviour_classes}, characteristic_ids=set(characteristic_classes), predicate_ids={row['id'] for row in predicates}, observation_predicate_ids={row['id'] for row in observation_predicates})
    by_kind: dict[str, list[str]] = {}
    by_class: dict[str, list[str]] = {}
    by_predicate: dict[str, list[str]] = {}
    for fact in facts:
        for kind in fact['applies_to']['object_kinds']:
            by_kind.setdefault(kind, []).append(fact['id'])
        for cls in fact['applies_to']['behaviour_classes']:
            by_class.setdefault(cls, []).append(fact['id'])
        for predicate in fact['applies_to']['structure_predicates']:
            by_predicate.setdefault(predicate, []).append(fact['id'])
    pinned_sources = {fact['source_path']: fact['source_sha256'] for fact in facts}
    payload: dict[str, Any] = {'schema': SCHEMA, 'generator': 'scripts/gen_device_characteristics.py', 'authority': {'can_sign_expected': False, 'mechanical_enforcement': False}, 'identity': {'source_path': source_path.relative_to(ROOT).as_posix(), 'source_sha256': _sha256_bytes(source_path.read_bytes()), 'version_family': str(inventory.get('version') or ''), 'device_build': str(inventory.get('device_os_build') or ''), 'object_kind_count': len(object_kinds), 'pinned_sources': dict(sorted(pinned_sources.items()))}, 'behaviour_classes': behaviour_classes, 'characteristic_classes': characteristic_classes, 'structure_predicates': predicates, 'observation_predicates': observation_predicates, 'prerequisite_rules': list(PREREQUISITE_RULES), 'facts': facts, 'index': {'by_object_kind': {k: sorted(v) for k, v in sorted(by_kind.items())}, 'by_behaviour_class': {k: sorted(v) for k, v in sorted(by_class.items())}, 'by_structure_predicate': {k: sorted(v) for k, v in sorted(by_predicate.items())}}}
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    payload['projection_sha256'] = _sha256_bytes(body)
    return payload

def render_projection(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def build() -> dict[str, Any]:
    return generate_projection()

def _write_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--check', action='store_true')
    return parser

def main(argv: Sequence[str] | None=None) -> int:
    args = _parser().parse_args(argv)
    rendered = render_projection(generate_projection(source_path=args.source))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != rendered:
            raise DeviceCharacteristicsError('device characteristic projection is stale; rerun without --check')
        print(f'checked {args.output.relative_to(ROOT)}')
        return 0
    if args.output.is_symlink():
        raise DeviceCharacteristicsError('device characteristic projection path must not be a symbolic link')
    try:
        current = args.output.read_bytes()
    except FileNotFoundError:
        current = None
    except OSError as exc:
        raise DeviceCharacteristicsError('device characteristic projection cannot be read for convergence') from exc
    if current != rendered:
        _write_atomic(args.output, rendered)
    print(f'wrote {args.output.relative_to(ROOT)}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
