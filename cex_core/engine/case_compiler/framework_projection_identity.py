# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/framework_projection_identity.py（sha256 13f67c6252e90cd7）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from cex_core.engine.case_compiler._sealed_io import canonical_json, read_regular_nofollow, sha256_bytes, validate_json_budget
IDENTITY_SCHEMA = 'ist.framework-mirror-source-identity'
IDENTITY_SCOPE = 'framework_sync:lib-tree+smoke-test-conftest'
ATTRIBUTION_BINDING_SCHEMA = 'ist.attribution-framework-projection-binding'
_INDEX_FORMAT = 'method-reference-windowed-index-v1'
_SHARD_FORMAT = 'method-reference-windowed-shard-v1'
_HASH_RE = re.compile('[0-9a-f]{64}')
FRAMEWORK_PROJECTION_SOURCE_PATHS = ('lib/test_xlsx.py', 'lib/apv/apv.py', 'lib/apv/apv_ssh.py', 'lib/apv/clear.py', 'lib/apv/ssl_comm.py', 'lib/apv/seg_comm.py', 'lib/apv/ha_comm.py', 'lib/apv/preparation.py', 'lib/apv/apv_action.py', 'lib/apv/apv_synonyms', 'lib/dic_operation.py', 'lib/client_action.py', 'lib/client_synonyms', 'lib/env.py', 'lib/check_point.py', 'lib/ssh_server.py', 'smoke_test/conftest.py')
_REQUIRED_SOURCE_PATHS = frozenset(FRAMEWORK_PROJECTION_SOURCE_PATHS)

class FrameworkProjectionIdentityError(RuntimeError):

    def __init__(self, detail: str, *, reason_code: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_code = reason_code

class _SealedReadError(RuntimeError):
    pass

def _raise(detail: str, reason_code: str) -> None:
    raise FrameworkProjectionIdentityError(detail, reason_code=reason_code)

def _sealed_bytes(path: Path, *, trusted_root: Path, max_bytes: int, label: str, min_bytes: int=0) -> bytes:
    try:
        return read_regular_nofollow(path, error_type=_SealedReadError, invalid_message=f'{label} path is invalid', directory_message=f'{label} parent is unavailable', open_message=f'{label} is unavailable', bounds_message=f'{label} exceeds its sealed size boundary', changed_message=f'{label} changed while being read', max_bytes=max_bytes, min_bytes=min_bytes, trusted_root=trusted_root)
    except _SealedReadError as exc:
        _raise(str(exc), 'framework_projection_identity_unavailable')

def _sealed_json(path: Path, *, trusted_root: Path, max_bytes: int, label: str) -> tuple[dict, bytes]:
    raw = _sealed_bytes(path, trusted_root=trusted_root, max_bytes=max_bytes, label=label, min_bytes=2)
    try:
        validate_json_budget(raw, error_type=_SealedReadError, message=f'{label} exceeds its JSON structure boundary', max_depth=64, max_tokens=250000)
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError, _SealedReadError):
        _raise(f'{label} is not a valid bounded JSON object', 'framework_projection_identity_unavailable')
    if not isinstance(payload, dict):
        _raise(f'{label} is not a JSON object', 'framework_projection_identity_incomplete')
    return (payload, raw)

def _safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value and (not path.is_absolute()) and all((part not in {'', '.', '..'} for part in path.parts)) and (path.as_posix() == value))

def _in_framework_scope(relative: str) -> bool:
    return _safe_relative(relative) and (relative.startswith('lib/') or relative == 'smoke_test/conftest.py')

def _validate_sync_meta(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    by_path = payload.get('by_path')
    synced_at = payload.get('synced_at')
    if payload.get('version') != 1 or not isinstance(by_path, Mapping) or (not isinstance(synced_at, str)) or (not synced_at.strip()):
        _raise('framework sync receipt is incomplete', 'framework_projection_identity_incomplete')
    return (by_path, synced_at)

def build_framework_source_identity(mirror_root: Path) -> dict[str, Any]:
    mirror_root = Path(mirror_root)
    sync_meta, sync_raw = _sealed_json(mirror_root / '.sync_meta.json', trusted_root=mirror_root, max_bytes=16 * 1024 * 1024, label='framework sync receipt')
    by_path, synced_at = _validate_sync_meta(sync_meta)
    scoped: dict[str, str] = {}
    for raw_relative, raw_digest in by_path.items():
        if not isinstance(raw_relative, str):
            _raise('framework sync receipt contains a non-string source path', 'framework_projection_identity_incomplete')
        if raw_relative.startswith('lib/') and (not _safe_relative(raw_relative)):
            _raise('framework sync receipt contains an unsafe library source path', 'framework_projection_identity_incomplete')
        if not _in_framework_scope(raw_relative):
            continue
        if not isinstance(raw_digest, str) or not _HASH_RE.fullmatch(raw_digest):
            _raise('framework sync receipt contains an invalid source digest', 'framework_projection_identity_incomplete')
        scoped[raw_relative] = raw_digest
    missing = sorted(_REQUIRED_SOURCE_PATHS - set(scoped))
    if missing:
        _raise('framework sync receipt is missing required projection sources: ' + ', '.join(missing), 'framework_projection_identity_incomplete')
    observed: dict[str, str] = {}
    for relative, expected in sorted(scoped.items()):
        raw = _sealed_bytes(mirror_root / PurePosixPath(relative), trusted_root=mirror_root, max_bytes=64 * 1024 * 1024, label='framework projection source')
        actual = sha256_bytes(raw)
        if actual != expected:
            _raise(f'framework projection source drifted from sync receipt: {relative}', 'framework_projection_identity_stale')
        observed[relative] = actual
    canonical = canonical_json(observed, ensure_ascii=True)
    return {'schema': IDENTITY_SCHEMA, 'scope': IDENTITY_SCOPE, 'complete': True, 'synced_at': synced_at, 'sync_receipt_sha256': sha256_bytes(sync_raw), 'snapshot_sha256': sha256_bytes(canonical), 'source_count': len(observed), 'source_hashes': observed}

def _safe_shard_path(compile_ref_root: Path, raw_path: str) -> Path:
    if not _safe_relative(raw_path):
        _raise('method-reference index contains an unsafe shard path', 'framework_projection_identity_incomplete')
    rel = PurePosixPath(raw_path)
    if len(rel.parts) != 2 or rel.parts[0] != 'method_reference' or (not rel.name.startswith('shard-')) or (not rel.name.endswith('.json')):
        _raise('method-reference index points outside its shard namespace', 'framework_projection_identity_incomplete')
    return compile_ref_root / rel

def _load_windowed_projection(compile_ref_root: Path) -> tuple[dict[str, Any], str]:
    index, _ = _sealed_json(compile_ref_root / 'method_reference.json', trusted_root=compile_ref_root, max_bytes=512 * 1024, label='method-reference index')
    index_meta = index.get('_meta')
    sections = index.get('sections')
    if not isinstance(index_meta, Mapping) or index_meta.get('format') != _INDEX_FORMAT or (not isinstance(index_meta.get('source_sha256'), str)) or (not _HASH_RE.fullmatch(str(index_meta.get('source_sha256')))) or (not isinstance(sections, list)) or (not sections):
        _raise('method-reference index identity is incomplete', 'framework_projection_identity_incomplete')
    source_sha = str(index_meta['source_sha256'])
    rebuilt: dict[str, Any] = {}
    for section in sections:
        if not isinstance(section, Mapping):
            _raise('method-reference index contains an invalid section', 'framework_projection_identity_incomplete')
        name = section.get('name')
        container = section.get('container')
        descriptors = section.get('shards')
        if not isinstance(name, str) or name in rebuilt or container not in {'mapping', 'sequence', 'scalar'} or (not isinstance(descriptors, list)) or (not descriptors):
            _raise('method-reference index section identity is incomplete', 'framework_projection_identity_incomplete')
        value: Any = {} if container == 'mapping' else [] if container == 'sequence' else None
        scalar_seen = False
        for descriptor in descriptors:
            if not isinstance(descriptor, Mapping) or not isinstance(descriptor.get('path'), str):
                _raise('method-reference shard descriptor is incomplete', 'framework_projection_identity_incomplete')
            shard_path = _safe_shard_path(compile_ref_root, str(descriptor['path']))
            shard, _ = _sealed_json(shard_path, trusted_root=compile_ref_root, max_bytes=2 * 1024 * 1024, label='method-reference shard')
            shard_meta = shard.get('_meta')
            entries = shard.get('entries')
            if not isinstance(shard_meta, Mapping) or shard_meta.get('format') != _SHARD_FORMAT or shard_meta.get('section') != name or (shard_meta.get('container') != container) or (shard_meta.get('source_sha256') != source_sha):
                _raise('method-reference shard identity does not match its index', 'framework_projection_identity_incomplete')
            if container == 'mapping':
                if not isinstance(entries, dict) or set(value) & set(entries):
                    _raise('method-reference mapping shard is invalid', 'framework_projection_identity_incomplete')
                value.update(entries)
            elif container == 'sequence':
                if not isinstance(entries, list):
                    _raise('method-reference sequence shard is invalid', 'framework_projection_identity_incomplete')
                value.extend(entries)
            else:
                if scalar_seen:
                    _raise('method-reference scalar section is split', 'framework_projection_identity_incomplete')
                value = entries
                scalar_seen = True
        rebuilt[name] = value
    rendered = (json.dumps(rebuilt, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if sha256_bytes(rendered) != source_sha:
        _raise('method-reference shards do not reconstruct the indexed projection', 'framework_projection_identity_incomplete')
    return (rebuilt, source_sha)

def _validate_recorded_identity(identity: Any) -> dict[str, Any]:
    if not isinstance(identity, dict):
        _raise('method-reference projection has no framework source identity', 'framework_projection_identity_incomplete')
    hashes = identity.get('source_hashes')
    if identity.get('schema') != IDENTITY_SCHEMA or identity.get('scope') != IDENTITY_SCOPE or identity.get('complete') is not True or (not isinstance(identity.get('synced_at'), str)) or (not isinstance(identity.get('sync_receipt_sha256'), str)) or (not _HASH_RE.fullmatch(str(identity.get('sync_receipt_sha256')))) or (not isinstance(identity.get('snapshot_sha256'), str)) or (not _HASH_RE.fullmatch(str(identity.get('snapshot_sha256')))) or (not isinstance(hashes, dict)) or (not hashes) or (identity.get('source_count') != len(hashes)):
        _raise('method-reference framework source identity is incomplete', 'framework_projection_identity_incomplete')
    if not _REQUIRED_SOURCE_PATHS.issubset(hashes):
        _raise('method-reference framework source identity omits required sources', 'framework_projection_identity_incomplete')
    for relative, digest in hashes.items():
        if not isinstance(relative, str) or not _in_framework_scope(relative) or (not isinstance(digest, str)) or (not _HASH_RE.fullmatch(digest)):
            _raise('method-reference framework source identity contains an invalid entry', 'framework_projection_identity_incomplete')
    if sha256_bytes(canonical_json(hashes, ensure_ascii=True)) != identity['snapshot_sha256']:
        _raise('method-reference framework source identity snapshot digest is invalid', 'framework_projection_identity_incomplete')
    return identity
_SYNC_PROVENANCE_FIELDS = ('synced_at', 'sync_receipt_sha256')

def _content_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in identity.items() if k not in _SYNC_PROVENANCE_FIELDS}

def _validated_attribution_projection(project_root: Path | None=None) -> tuple[dict[str, Any], str]:
    root = Path(project_root) if project_root is not None else _cex_data_path('')
    projection, projection_sha256 = _load_windowed_projection(root / 'knowledge/data/compile_ref')
    projection_meta = projection.get('_meta')
    if not isinstance(projection_meta, Mapping):
        _raise('method-reference projection metadata is incomplete', 'framework_projection_identity_incomplete')
    recorded = _validate_recorded_identity(projection_meta.get('framework_source_identity'))
    current = build_framework_source_identity(root / 'knowledge/framework/mirror')
    if _content_identity(recorded) != _content_identity(current):
        if set(recorded.get('source_hashes') or {}) != set(current.get('source_hashes') or {}):
            detail = 'method-reference projection source closure differs from the current framework mirror'
        else:
            detail = 'method-reference projection source hashes differ from the current framework mirror'
        _raise(detail, 'framework_projection_identity_stale')
    return (dict(recorded), projection_sha256)

def attribution_projection_binding(identity: Mapping[str, Any], *, method_reference_sha256: str) -> dict[str, str]:
    if not _HASH_RE.fullmatch(str(method_reference_sha256 or '')):
        _raise('method-reference projection digest is unavailable', 'framework_projection_identity_incomplete')
    recorded = _validate_recorded_identity(dict(identity))
    return {'schema': ATTRIBUTION_BINDING_SCHEMA, 'identity_sha256': sha256_bytes(canonical_json(recorded, ensure_ascii=True)), 'sync_receipt_sha256': str(recorded['sync_receipt_sha256']), 'framework_snapshot_sha256': str(recorded['snapshot_sha256']), 'method_reference_sha256': str(method_reference_sha256)}

def validate_attribution_projection_identity(project_root: Path | None=None) -> dict[str, Any]:
    recorded, _projection_sha256 = _validated_attribution_projection(project_root)
    return recorded

def validate_attribution_projection_binding(project_root: Path | None=None) -> dict[str, str]:
    recorded, projection_sha256 = _validated_attribution_projection(project_root)
    return attribution_projection_binding(recorded, method_reference_sha256=projection_sha256)
__all__ = ['FrameworkProjectionIdentityError', 'ATTRIBUTION_BINDING_SCHEMA', 'FRAMEWORK_PROJECTION_SOURCE_PATHS', 'IDENTITY_SCHEMA', 'IDENTITY_SCOPE', 'attribution_projection_binding', 'build_framework_source_identity', 'validate_attribution_projection_binding', 'validate_attribution_projection_identity']
