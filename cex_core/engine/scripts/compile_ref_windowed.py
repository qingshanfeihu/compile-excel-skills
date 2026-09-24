# 生成：tools/extract_engine.py ← InfoTest scripts/compile_ref_windowed.py（sha256 2d4579acb916fe9c）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
_ROOT = _cex_data_path('')
_COMPILE_REF = _ROOT / 'knowledge' / 'data' / 'compile_ref'
_DEFAULT_INDEX_PATH = _COMPILE_REF / 'method_reference.json'
_SHARD_DIR_NAME = 'method_reference'
_MAX_WINDOW_LINES = 200
_INDEX_FORMAT = 'method-reference-windowed-index-v1'
_SHARD_FORMAT = 'method-reference-windowed-shard-v1'
_UNSET = object()

class WindowedProjectionError(RuntimeError):
    pass

def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'

def line_count(value: Any) -> int:
    return len(render_json(value).splitlines())

def _container_kind(value: Any) -> str:
    if isinstance(value, dict):
        return 'mapping'
    if isinstance(value, list):
        return 'sequence'
    return 'scalar'

def _source_sha256(data: dict[str, Any]) -> str:
    return hashlib.sha256(render_json(data).encode('utf-8')).hexdigest()

def _shard_payload(*, section: str, container: str, entries: Any, source_sha256: str) -> dict[str, Any]:
    return {'_meta': {'format': _SHARD_FORMAT, 'section': section, 'container': container, 'source_sha256': source_sha256}, 'entries': entries}

def _fits(*, section: str, container: str, entries: Any, source_sha256: str, max_lines: int) -> bool:
    return line_count(_shard_payload(section=section, container=container, entries=entries, source_sha256=source_sha256)) <= max_lines

def _oversize_error(_section: str, max_lines: int) -> WindowedProjectionError:
    return WindowedProjectionError(f'method_reference contains an indivisible semantic unit that exceeds the {max_lines}-line read-window budget')

def _split_mapping(*, section: str, entries: dict[str, Any], source_sha256: str, max_lines: int) -> list[dict[str, Any]]:
    if _fits(section=section, container='mapping', entries=entries, source_sha256=source_sha256, max_lines=max_lines):
        return [entries]
    parts: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for key, value in entries.items():
        candidate = {**current, key: value}
        if _fits(section=section, container='mapping', entries=candidate, source_sha256=source_sha256, max_lines=max_lines):
            current = candidate
            continue
        if current:
            parts.append(current)
            current = {key: value}
        else:
            current = candidate
        if not _fits(section=section, container='mapping', entries=current, source_sha256=source_sha256, max_lines=max_lines):
            raise _oversize_error(section, max_lines)
    if current or not entries:
        parts.append(current)
    return parts

def _split_sequence(*, section: str, entries: list[Any], source_sha256: str, max_lines: int) -> list[list[Any]]:
    if _fits(section=section, container='sequence', entries=entries, source_sha256=source_sha256, max_lines=max_lines):
        return [entries]
    parts: list[list[Any]] = []
    current: list[Any] = []
    for value in entries:
        candidate = [*current, value]
        if _fits(section=section, container='sequence', entries=candidate, source_sha256=source_sha256, max_lines=max_lines):
            current = candidate
            continue
        if current:
            parts.append(current)
            current = [value]
        else:
            current = candidate
        if not _fits(section=section, container='sequence', entries=current, source_sha256=source_sha256, max_lines=max_lines):
            raise _oversize_error(section, max_lines)
    if current or not entries:
        parts.append(current)
    return parts

def _split_section(*, section: str, value: Any, source_sha256: str, max_lines: int) -> tuple[str, list[Any]]:
    container = _container_kind(value)
    if container == 'mapping':
        return (container, _split_mapping(section=section, entries=value, source_sha256=source_sha256, max_lines=max_lines))
    if container == 'sequence':
        return (container, _split_sequence(section=section, entries=value, source_sha256=source_sha256, max_lines=max_lines))
    if not _fits(section=section, container=container, entries=value, source_sha256=source_sha256, max_lines=max_lines):
        raise _oversize_error(section, max_lines)
    return (container, [value])

def _safe_filename_part(section: str) -> str:
    cleaned = ''.join((ch if ch.isalnum() or ch in '_-' else '-' for ch in section))
    return cleaned or 'section'

def _rebuild(index: Mapping[str, Any], shard_payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    meta = index.get('_meta')
    if not isinstance(meta, Mapping) or meta.get('format') != _INDEX_FORMAT:
        raise WindowedProjectionError('method_reference index format is invalid')
    source_sha256 = meta.get('source_sha256')
    sections = index.get('sections')
    if not isinstance(source_sha256, str) or not isinstance(sections, list):
        raise WindowedProjectionError('method_reference index is incomplete')
    rebuilt: dict[str, Any] = {}
    for section_info in sections:
        if not isinstance(section_info, Mapping):
            raise WindowedProjectionError('method_reference index section is invalid')
        name = section_info.get('name')
        container = section_info.get('container')
        descriptors = section_info.get('shards')
        if not isinstance(name, str) or container not in {'mapping', 'sequence', 'scalar'} or (not isinstance(descriptors, list)) or (not descriptors):
            raise WindowedProjectionError('method_reference index section is incomplete')
        if container == 'mapping':
            value: Any = {}
        elif container == 'sequence':
            value = []
        else:
            value = _UNSET
        for descriptor in descriptors:
            if not isinstance(descriptor, Mapping) or not isinstance(descriptor.get('path'), str):
                raise WindowedProjectionError('method_reference shard descriptor is invalid')
            path = descriptor['path']
            shard = shard_payloads.get(path)
            if not isinstance(shard, Mapping):
                raise WindowedProjectionError('method_reference shard is unavailable')
            shard_meta = shard.get('_meta')
            if not isinstance(shard_meta, Mapping) or shard_meta.get('format') != _SHARD_FORMAT or shard_meta.get('section') != name or (shard_meta.get('container') != container) or (shard_meta.get('source_sha256') != source_sha256):
                raise WindowedProjectionError('method_reference shard metadata does not match index')
            entries = shard.get('entries')
            if container == 'mapping':
                if not isinstance(entries, dict) or set(value) & set(entries):
                    raise WindowedProjectionError('method_reference mapping shard is invalid')
                value.update(entries)
            elif container == 'sequence':
                if not isinstance(entries, list):
                    raise WindowedProjectionError('method_reference sequence shard is invalid')
                value.extend(entries)
            else:
                if value is not _UNSET:
                    raise WindowedProjectionError('method_reference scalar section is split')
                value = entries
        rebuilt[name] = value
    if _source_sha256(rebuilt) != source_sha256:
        raise WindowedProjectionError('method_reference shards do not reconstruct the indexed source')
    return rebuilt

def build_method_reference_window(data: dict[str, Any], *, max_lines: int=_MAX_WINDOW_LINES) -> tuple[dict[str, Any], dict[str, str]]:
    if not isinstance(data, dict):
        raise WindowedProjectionError('method_reference projection must be a JSON object')
    if max_lines < 1:
        raise WindowedProjectionError('read-window budget must be positive')
    source_sha256 = _source_sha256(data)
    section_infos: list[dict[str, Any]] = []
    shard_payloads: dict[str, dict[str, Any]] = {}
    shard_texts: dict[str, str] = {}
    ordinal = 1
    for section, value in data.items():
        if not isinstance(section, str):
            raise WindowedProjectionError('method_reference section names must be strings')
        container, parts = _split_section(section=section, value=value, source_sha256=source_sha256, max_lines=max_lines)
        descriptors: list[dict[str, Any]] = []
        for entries in parts:
            filename = f'shard-{ordinal:03d}-{_safe_filename_part(section)}.json'
            path = f'{_SHARD_DIR_NAME}/{filename}'
            payload = _shard_payload(section=section, container=container, entries=entries, source_sha256=source_sha256)
            text = render_json(payload)
            lines = len(text.splitlines())
            if lines > max_lines:
                raise _oversize_error(section, max_lines)
            shard_payloads[path] = payload
            shard_texts[path] = text
            descriptors.append({'path': path, 'entry_count': len(entries) if isinstance(entries, (dict, list)) else 1, 'line_count': lines})
            ordinal += 1
        section_infos.append({'name': section, 'container': container, 'shards': descriptors})
    index = {'_meta': {'format': _INDEX_FORMAT, 'purpose': 'Navigation index for the worker-readable method-reference projection. Each listed shard is a complete semantic subset, never a physical-line slice. For a named method or note, fs_grep this shard directory first, then fs_read only the matching shard; absence from one shard is not a claim about the whole projection.', 'regenerate': 'python scripts/gen_method_reference.py', 'max_lines': max_lines, 'shard_dir': _SHARD_DIR_NAME, 'source_sha256': source_sha256}, 'sections': section_infos}
    if line_count(index) > max_lines:
        raise WindowedProjectionError(f'method_reference navigation index exceeds the {max_lines}-line read-window budget')
    if _rebuild(index, shard_payloads) != data:
        raise WindowedProjectionError('method_reference partition lost or changed semantic data')
    return (index, shard_texts)

def _resolve_shard_path(index_path: Path, rel_path: str) -> Path:
    rel = Path(rel_path)
    if rel.is_absolute() or any((part in {'', '.', '..'} for part in rel.parts)):
        raise WindowedProjectionError('method_reference index contains an unsafe shard path')
    if len(rel.parts) != 2 or rel.parts[0] != _SHARD_DIR_NAME or (not rel.name.startswith('shard-')) or (rel.suffix != '.json'):
        raise WindowedProjectionError('method_reference index points outside its shard namespace')
    root = index_path.parent.resolve()
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WindowedProjectionError('method_reference shard escapes compile_ref') from exc
    return resolved

def _read_index(index_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(index_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise WindowedProjectionError('method_reference index is unavailable or invalid') from exc
    if not isinstance(data, dict):
        raise WindowedProjectionError('method_reference index must be a JSON object')
    return data

def method_reference_artifact_paths(index_path: Path=_DEFAULT_INDEX_PATH) -> tuple[Path, ...]:
    index = _read_index(index_path)
    if (index.get('_meta') or {}).get('format') != _INDEX_FORMAT:
        raise WindowedProjectionError('method_reference index format is invalid')
    paths = [index_path]
    for section in index.get('sections') or []:
        if not isinstance(section, Mapping):
            raise WindowedProjectionError('method_reference index section is invalid')
        for descriptor in section.get('shards') or []:
            if not isinstance(descriptor, Mapping) or not isinstance(descriptor.get('path'), str):
                raise WindowedProjectionError('method_reference shard descriptor is invalid')
            paths.append(_resolve_shard_path(index_path, descriptor['path']))
    return tuple(paths)

def load_method_reference(index_path: Path=_DEFAULT_INDEX_PATH) -> dict[str, Any]:
    index = _read_index(index_path)
    if (index.get('_meta') or {}).get('format') != _INDEX_FORMAT:
        raise WindowedProjectionError('method_reference index format is invalid')
    payloads: dict[str, dict[str, Any]] = {}
    for section in index.get('sections') or []:
        if not isinstance(section, Mapping):
            raise WindowedProjectionError('method_reference index section is invalid')
        for descriptor in section.get('shards') or []:
            if not isinstance(descriptor, Mapping) or not isinstance(descriptor.get('path'), str):
                raise WindowedProjectionError('method_reference shard descriptor is invalid')
            rel_path = descriptor['path']
            shard_path = _resolve_shard_path(index_path, rel_path)
            try:
                payload = json.loads(shard_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                raise WindowedProjectionError('method_reference shard is unavailable or invalid') from exc
            if not isinstance(payload, dict):
                raise WindowedProjectionError('method_reference shard must be a JSON object')
            payloads[rel_path] = payload
    return _rebuild(index, payloads)

def _atomic_write(path: Path, text: str) -> None:
    temp = path.with_name(f'.{path.name}.tmp')
    try:
        temp.write_text(text, encoding='utf-8')
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()

def _owned_stale_shards(index_path: Path, shard_dir: Path, expected_paths: set[Path]) -> set[Path]:
    existing = set(shard_dir.glob('shard-*.json'))
    if not existing:
        return set()
    if not index_path.is_file():
        raise WindowedProjectionError('method_reference shard directory contains unowned shard files')
    index = _read_index(index_path)
    if (index.get('_meta') or {}).get('format') != _INDEX_FORMAT:
        raise WindowedProjectionError('method_reference shard directory has no valid owning index')
    try:
        load_method_reference(index_path)
        declared = set(method_reference_artifact_paths(index_path)[1:])
    except WindowedProjectionError as exc:
        raise WindowedProjectionError('existing method_reference shards fail ownership validation') from exc
    if existing - declared:
        raise WindowedProjectionError('method_reference shard directory contains unowned shard files')
    return declared - expected_paths

def write_method_reference_window(data: dict[str, Any], *, index_path: Path=_DEFAULT_INDEX_PATH, max_lines: int=_MAX_WINDOW_LINES, credential_values: frozenset[str] | set[str] | None=None) -> dict[str, int]:
    index, shard_texts = build_method_reference_window(data, max_lines=max_lines)
    index_text = render_json(index)
    if credential_values is None:
        from cex_core.engine.case_compiler.credential_literals import MirrorCredentialLiteralError, mirror_credential_literals
        try:
            credential_values = mirror_credential_literals()
        except MirrorCredentialLiteralError as exc:
            raise WindowedProjectionError('credential literal closure is unavailable') from exc
    values = frozenset((v for v in credential_values if v))
    if not values:
        raise WindowedProjectionError('credential literal closure is empty')
    from cex_core.engine.case_compiler.credential_literals import matching_credential_literal_count
    matches = sum((matching_credential_literal_count(text, values) for text in [index_text, *shard_texts.values()]))
    if matches:
        raise WindowedProjectionError(f'refusing to write method_reference projection with credential literal matches (count={matches})')
    shard_dir = index_path.parent / _SHARD_DIR_NAME
    shard_dir.mkdir(parents=True, exist_ok=True)
    expected_paths = {_resolve_shard_path(index_path, rel_path) for rel_path in shard_texts}
    stale_paths = _owned_stale_shards(index_path, shard_dir, expected_paths)
    for rel_path, text in shard_texts.items():
        _atomic_write(_resolve_shard_path(index_path, rel_path), text)
    _atomic_write(index_path, index_text)
    for stale in stale_paths:
        stale.unlink()
    return {'index_lines': len(index_text.splitlines()), 'shard_count': len(shard_texts)}
__all__ = ['WindowedProjectionError', 'build_method_reference_window', 'line_count', 'load_method_reference', 'method_reference_artifact_paths', 'render_json', 'write_method_reference_window']
