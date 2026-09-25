# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/behaviour_classes.py（sha256 cab7ec6aa593493b）。不在这里手改。
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from cex_core.engine.common.runtime_paths import runtime_path
logger = logging.getLogger(__name__)
BEHAVIOUR_LEDGER_PATH = runtime_path('device_behaviour_classes.jsonl')
BEHAVIOUR_RECORD_SCHEMA = 'ist.device-behaviour-class'
SEED_CLASS_MAP: Mapping[str, str] = {'uniform_rotation': 'rotation'}
MAX_METHODS_PER_CASE = 8
MAX_BEHAVIOUR_CLASSES = MAX_METHODS_PER_CASE * 2
MAX_PARAGRAPHS_PER_METHOD = 6
MAX_PARAGRAPH_CHARS = 1200
MAX_METHOD_CHARS = 64
MAX_BEHAVIOUR_CLASS_CHARS = 64
MAX_OBJECT_KIND_CHARS = 200
MAX_SOURCE_PATH_CHARS = 400
MAX_LEDGER_BYTES = 8 * 1024 * 1024

class BehaviourClassError(RuntimeError):
    pass

def _unclassified() -> str:
    from cex_core.engine.case_compiler.device_characteristics import UNCLASSIFIED
    return UNCLASSIFIED

def case_method_bindings(structure: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in structure or ():
        if not isinstance(entry, Mapping):
            continue
        methods = [str(item.get('value') or '').strip().casefold()[:MAX_METHOD_CHARS] for item in entry.get('stated_conditions') or () if isinstance(item, Mapping) and str(item.get('kind') or '') == 'algorithm' and str(item.get('value') or '').strip()]
        if not methods:
            continue
        kinds = [str(item.get('kind') or '').strip() for item in entry.get('objects') or () if isinstance(item, Mapping) and str(item.get('kind') or '').strip()] or ['']
        for method in methods:
            for kind in kinds:
                key = (method, kind)
                if key in seen or len(seen) >= MAX_METHODS_PER_CASE:
                    continue
                seen.add(key)
                out.append({'method': method, 'object_kind': kind})
    return out

def method_paragraph_candidates(method: str, object_kind: str='', *, limit: int=MAX_PARAGRAPHS_PER_METHOD) -> list[dict[str, str]]:
    token = str(method or '').strip().casefold()
    if not token or len(token) > MAX_METHOD_CHARS:
        return []
    segments = [part for part in str(object_kind or '').split('/') if part]
    out: list[dict[str, str]] = []
    for rel, text in _documentation_sources():
        offset = 0
        for block in text.split('\n\n'):
            start = offset
            offset += len(block) + 2
            folded = block.casefold()
            position = _standalone_position(folded, token)
            if position < 0:
                continue
            quote, cut = _window(block, position, len(token))
            line_start = text.count('\n', 0, start + cut) + 1
            out.append({'source_path': rel, 'line_start': str(line_start), 'quote': quote, '_rank': '0' if any((seg in folded for seg in segments)) else '1'})
    out.sort(key=lambda row: (row['_rank'], row['source_path'], int(row['line_start'])))
    return [{key: value for key, value in row.items() if key != '_rank'} for row in out[:limit]]

def _standalone_position(text: str, token: str) -> int:
    index = text.find(token)
    while index >= 0:
        before = text[index - 1] if index > 0 else ' '
        after_index = index + len(token)
        after = text[after_index] if after_index < len(text) else ' '
        if not _word_char(before) and (not _word_char(after)):
            return index
        index = text.find(token, index + 1)
    return -1

def _window(block: str, position: int, length: int) -> tuple[str, int]:
    if len(block) <= MAX_PARAGRAPH_CHARS:
        return (block, 0)
    half = (MAX_PARAGRAPH_CHARS - length) // 2
    start = max(0, position - half)
    start = min(start, max(0, len(block) - MAX_PARAGRAPH_CHARS))
    return (block[start:start + MAX_PARAGRAPH_CHARS], start)

def _word_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char == '_')

def _documentation_sources() -> list[tuple[str, str]]:
    from cex_core.engine.case_compiler.device_characteristics import load_device_characteristics, read_pinned_source_bytes
    data = load_device_characteristics() or {}
    pinned = (data.get('identity') or {}).get('pinned_sources') or {}
    out: list[tuple[str, str]] = []
    for rel in sorted(pinned):
        try:
            out.append((rel, read_pinned_source_bytes(str(rel)).decode('utf-8')))
        except (OSError, ValueError, UnicodeError):
            continue
    return out

def documentation_sha256() -> str:
    import hashlib
    from cex_core.engine.case_compiler.device_characteristics import load_device_characteristics
    data = load_device_characteristics() or {}
    pinned = (data.get('identity') or {}).get('pinned_sources') or {}
    joined = '|'.join((f'{rel}:{pinned[rel]}' for rel in sorted(pinned)))
    return hashlib.sha256(joined.encode('utf-8')).hexdigest() if joined else ''

def validate_behaviour_classification(rows: Any, *, asked: Sequence[Mapping[str, str]]=()) -> list[dict[str, Any]]:
    from cex_core.engine.case_compiler.device_characteristics import behaviour_class_closed_set
    from cex_core.engine.case_compiler.mindmap_contract_projector import ground_source_span
    closed = behaviour_class_closed_set()
    wanted = {(str(row.get('method') or '').casefold(), str(row.get('object_kind') or '')) for row in asked or () if isinstance(row, Mapping)}
    sources = dict(_documentation_sources())
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, Mapping):
            continue
        method = str(row.get('method') or '').strip().casefold()[:MAX_METHOD_CHARS]
        object_kind = str(row.get('object_kind') or '').strip()
        if not method or (method, object_kind) in seen:
            continue
        if wanted and (method, object_kind) not in wanted:
            continue
        seen.add((method, object_kind))
        behaviour = str(row.get('behaviour_class') or '').strip()
        rel = str(row.get('source_path') or '').strip()
        quote = str(row.get('quote') or '')[:MAX_PARAGRAPH_CHARS]
        reason = ''
        if closed is None:
            reason = 'closed_set_unavailable'
        elif behaviour == _unclassified():
            reason = 'declared_unclassified'
        elif behaviour not in closed:
            reason = 'class_outside_closed_set'
        elif rel not in sources:
            reason = 'citation_outside_pinned_documentation'
        elif not quote.strip() or ground_source_span(quote, sources[rel], origin='manual') is None:
            reason = 'citation_not_grounded'
        if reason:
            out.append({'method': method, 'object_kind': object_kind, 'behaviour_class': _unclassified(), 'pinned': '', 'source_path': '', 'locator': '', 'quote': '', 'reason_code': reason})
            continue
        text = sources[rel]
        span = ground_source_span(quote, text, origin='manual')
        line = text.count('\n', 0, int(span['start'])) + 1
        out.append({'method': method, 'object_kind': object_kind, 'behaviour_class': behaviour, 'pinned': 'spec' if '/spec/' in rel else 'manual', 'source_path': rel, 'locator': f'{rel}:{line}', 'quote': quote, 'reason_code': 'ok'})
    return out
LEDGER_OVER_BYTE_CAP = 'ledger_over_byte_cap'

def _ledger_over_byte_cap(target: Path) -> bool:
    try:
        if target.is_symlink() or not target.is_file():
            return False
        return target.stat().st_size > MAX_LEDGER_BYTES
    except OSError:
        return False

def _ledger_lines(target: Path) -> list[str]:
    if _ledger_over_byte_cap(target):
        logger.warning('behaviour class ledger exceeds %d bytes; reason_code=%s', MAX_LEDGER_BYTES, LEDGER_OVER_BYTE_CAP)
        return []
    try:
        if target.is_symlink() or not target.is_file():
            return []
        raw = target.read_bytes()
    except OSError:
        return []
    out: list[str] = []
    for chunk in raw.split(b'\n'):
        try:
            out.append(chunk.decode('utf-8', errors='strict'))
        except UnicodeError:
            continue
    return out

def _valid_ledger_record(record: Any, *, closed: frozenset[str] | None) -> dict[str, Any] | None:
    from cex_core.engine.case_compiler.device_characteristics import pinned_source_is_confined
    if not isinstance(record, dict):
        return None
    if str(record.get('schema') or '') != BEHAVIOUR_RECORD_SCHEMA:
        return None
    method = str(record.get('method') or '')
    kind = str(record.get('object_kind') or '')
    behaviour = str(record.get('behaviour_class') or '')
    rel = str(record.get('source_path') or '')
    quote = str(record.get('quote') or '')
    if not method or len(method) > MAX_METHOD_CHARS:
        return None
    if len(kind) > MAX_OBJECT_KIND_CHARS:
        return None
    if len(quote) > MAX_PARAGRAPH_CHARS or len(rel) > MAX_SOURCE_PATH_CHARS:
        return None
    if closed is None or behaviour not in closed or behaviour == _unclassified():
        return None
    if not pinned_source_is_confined(rel):
        return None
    return record

def load_behaviour_classes(*, path: Path | None=None, documentation_sha: str='') -> dict[tuple[str, str], dict[str, Any]]:
    from cex_core.engine.case_compiler.device_characteristics import behaviour_class_closed_set
    target = Path(path or BEHAVIOUR_LEDGER_PATH)
    wanted = documentation_sha or documentation_sha256()
    closed = behaviour_class_closed_set()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for line in _ledger_lines(target):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, RecursionError, ValueError):
            continue
        valid = _valid_ledger_record(record, closed=closed)
        if valid is None:
            continue
        if str(valid.get('documentation_sha256') or '') != wanted:
            continue
        out.setdefault((str(valid['method']), str(valid.get('object_kind') or '')), valid)
    return out

def persist_behaviour_classes(rows: Sequence[Mapping[str, Any]], *, path: Path | None=None, documentation_sha: str='') -> list[dict[str, Any]]:
    target = Path(path or BEHAVIOUR_LEDGER_PATH)
    sha = documentation_sha or documentation_sha256()
    if _ledger_over_byte_cap(target):
        logger.warning('behaviour class append skipped; reason_code=%s cap=%d', LEDGER_OVER_BYTE_CAP, MAX_LEDGER_BYTES)
        return []
    records = [{'schema': BEHAVIOUR_RECORD_SCHEMA, 'method': str(row.get('method') or ''), 'object_kind': str(row.get('object_kind') or ''), 'behaviour_class': str(row.get('behaviour_class') or ''), 'pinned': str(row.get('pinned') or ''), 'source_path': str(row.get('source_path') or ''), 'locator': str(row.get('locator') or ''), 'quote': str(row.get('quote') or ''), 'documentation_sha256': sha} for row in rows or () if isinstance(row, Mapping) and str(row.get('behaviour_class') or '') not in ('', _unclassified()) and str(row.get('method') or '')]
    records = _drop_already_recorded(target, records)
    if not records:
        return []
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY | getattr(os, 'O_CLOEXEC', 0)
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 384)
    try:
        for record in records:
            raw = (json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
            offset = 0
            while offset < len(raw):
                written = os.write(fd, raw[offset:])
                if written <= 0:
                    raise BehaviourClassError('behaviour class append made no progress')
                offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    if not existed and hasattr(os, 'O_DIRECTORY'):
        directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return records

def _drop_already_recorded(target: Path, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    seen: set[tuple[str, str, str]] = set()
    for line in _ledger_lines(target):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, RecursionError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        if str(record.get('schema') or '') != BEHAVIOUR_RECORD_SCHEMA:
            continue
        seen.add((str(record.get('method') or ''), str(record.get('object_kind') or ''), str(record.get('documentation_sha256') or '')))
    out: list[dict[str, Any]] = []
    for record in records:
        key = (str(record.get('method') or ''), str(record.get('object_kind') or ''), str(record.get('documentation_sha256') or ''))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(record))
    return out

def seed_behaviour_class(method: str) -> dict[str, Any] | None:
    from cex_core.engine.case_compiler.domain_grammar import load_grammar
    token = str(method or '').strip().casefold()
    if not token:
        return None
    try:
        classes = load_grammar().get('algorithm_classes') or {}
    except Exception:
        return None
    if not isinstance(classes, Mapping):
        return None
    for class_id, behaviour in SEED_CLASS_MAP.items():
        spec = classes.get(class_id)
        if not isinstance(spec, Mapping):
            continue
        methods = {str(name).strip().casefold() for name in spec.get('methods') or []}
        if token in methods:
            return {'behaviour_class': behaviour, 'pinned': 'seed', 'source_path': 'knowledge/data/compile_ref/domain_grammar.json', 'locator': f'domain_grammar.json:algorithm_classes.{class_id}', 'quote': str(spec.get('provenance') or ''), 'reason_code': 'seed_cache'}
    return None

def resolve_behaviour_classes(structure: Sequence[Mapping[str, Any]], *, path: Path | None=None) -> list[dict[str, Any]]:
    bindings = case_method_bindings(structure)
    if not bindings:
        return []
    ledger = load_behaviour_classes(path=path)
    out: list[dict[str, Any]] = []
    for binding in bindings:
        method = binding['method']
        kind = binding['object_kind']
        record = ledger.get((method, kind)) or ledger.get((method, ''))
        if record:
            out.append({'method': method, 'object_kind': kind, 'behaviour_class': str(record.get('behaviour_class') or ''), 'pinned': str(record.get('pinned') or ''), 'source_path': str(record.get('source_path') or ''), 'locator': str(record.get('locator') or ''), 'quote': str(record.get('quote') or ''), 'reason_code': 'adjudicated'})
            continue
        seed = seed_behaviour_class(method)
        if seed:
            out.append({'method': method, 'object_kind': kind, **seed})
            continue
        out.append({'method': method, 'object_kind': kind, 'behaviour_class': _unclassified(), 'pinned': '', 'source_path': '', 'locator': '', 'quote': '', 'reason_code': 'no_documentation_judgement'})
    return out

def classification_request(structure: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in resolve_behaviour_classes(structure):
        if str(row.get('reason_code') or '') == 'adjudicated':
            continue
        out.append({'method': row['method'], 'object_kind': row['object_kind'], 'documentation': method_paragraph_candidates(row['method'], row['object_kind'])})
    return [row for row in out if row['documentation']]

def unique_bindings(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        key = (str(row.get('method') or ''), str(row.get('object_kind') or ''))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append({'method': key[0], 'object_kind': key[1]})
    return out
__all__ = ['BEHAVIOUR_LEDGER_PATH', 'BEHAVIOUR_RECORD_SCHEMA', 'LEDGER_OVER_BYTE_CAP', 'MAX_BEHAVIOUR_CLASS_CHARS', 'MAX_BEHAVIOUR_CLASSES', 'MAX_LEDGER_BYTES', 'MAX_METHOD_CHARS', 'MAX_METHODS_PER_CASE', 'MAX_OBJECT_KIND_CHARS', 'MAX_PARAGRAPH_CHARS', 'MAX_PARAGRAPHS_PER_METHOD', 'MAX_SOURCE_PATH_CHARS', 'SEED_CLASS_MAP', 'BehaviourClassError', 'case_method_bindings', 'classification_request', 'documentation_sha256', 'load_behaviour_classes', 'method_paragraph_candidates', 'persist_behaviour_classes', 'resolve_behaviour_classes', 'seed_behaviour_class', 'unique_bindings', 'validate_behaviour_classification']
