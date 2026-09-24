# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/recompose_submission.py（sha256 e0c4f94e2a246c29）。不在这里手改。
from __future__ import annotations
import copy
import hashlib
import json
import contextvars
import logging
import fcntl
import os
import re
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Any, Callable, Iterator, Sequence
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, canonical_json, lexical_absolute, lexical_path_inside_root, open_directory_nofollow, read_regular_nofollow, sha256_bytes, validate_json_budget
from cex_core.engine.engine_managed_outputs import MACHINE_MINDMAP_SUBMISSION_LOCK_NAME, MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME, RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME
SCHEMA = 'ist.machine-mindmap-submission'
_ARTIFACT_NAME = 'machine_mindmap.json'
_DISPATCH_ID_RE = re.compile('^[0-9a-f]{32}$')
_AUTOID_RE = re.compile('^\\d{18}$')
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_RECEIPT_BYTES = 16 * 1024
_MAX_GROUNDING_BYTES = 4 * 1024 * 1024
_MAX_GROUNDING_RESULT_BYTES = 512 * 1024
_GROUNDING_SCHEMA = 'ist.recompose-command-grounding'
_GROUNDING_KINDS = frozenset({'param', 'complete', 'heads'})
RECOMPOSE_HEADS_SCOPE_REFUSAL = 'recompose_heads_not_offered'
RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT = "error: kind='heads' is not offered in the recompose scope (the head inventory is bound to a compile-worker session); use kind='param' for an exact head or kind='complete' for a partial head"
_LOCK = threading.RLock()
logger = logging.getLogger(__name__)
_BINDING_KEYS = frozenset({'source', 'governing_spec', 'governing_spec_status', 'governing_spec_sha256', 'governing_spec_generation_id', 'governing_spec_manifest_sha256', 'defect_spec_status', 'defect_spec_receipt_sha256'})
_ARTIFACT_BINDING_KEYS = ('source', 'governing_spec', 'defect_spec_status', 'defect_spec_receipt_sha256')

class MachineMindmapSubmissionError(PermissionError):
    pass

class MachineMindmapContentError(MachineMindmapSubmissionError):

    def __init__(self, message: str, *, code: str='mindmap_content_invalid') -> None:
        super().__init__(message)
        self.code = str(code)

@dataclass(frozen=True)
class MachineMindmapSubmissionReceipt:
    out_name: str
    dispatch_id: str
    status: str
    artifact_sha256: str | None
    artifact_size: int | None
    binding: dict[str, object]
    binding_sha256: str

@dataclass(frozen=True)
class _RecomposeDispatchScope:
    outputs_root: Path
    out_name: str
    dispatch_id: str
    binding_sha256: str
    assigned_autoids: tuple[str, ...] = ()
_CURRENT_RECOMPOSE_DISPATCH: contextvars.ContextVar[_RecomposeDispatchScope | None] = contextvars.ContextVar('ist_recompose_dispatch', default=None)

def _validate_identity(out_name: str, dispatch_id: str) -> tuple[str, str]:
    name = str(out_name or '').strip()
    identity = str(dispatch_id or '').strip()
    if not name or name in {'.', '..'} or Path(name).name != name or ('/' in name) or ('\\' in name) or ('~' in name) or any((ord(char) < 32 for char in name)) or (len(name) > 180):
        raise MachineMindmapSubmissionError('machine mindmap submission out_name is invalid')
    if _DISPATCH_ID_RE.fullmatch(identity) is None:
        raise MachineMindmapSubmissionError('machine mindmap submission dispatch identity is invalid')
    return (name, identity)

def _batch_path(outputs_root: str | Path, out_name: str) -> Path:
    name, _ = _validate_identity(out_name, '0' * 32)
    root = lexical_absolute(outputs_root)
    path = lexical_path_inside_root(root / name, root, error_type=MachineMindmapSubmissionError, traversal_message='machine mindmap submission path traversal is forbidden', outside_message='machine mindmap submission escaped outputs root')
    if path != root / name:
        raise MachineMindmapSubmissionError('machine mindmap submission batch identity is invalid')
    return path

def machine_mindmap_submission_path(outputs_root: str | Path, out_name: str) -> Path:
    return _batch_path(outputs_root, out_name) / MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME

def machine_mindmap_artifact_path(outputs_root: str | Path, out_name: str) -> Path:
    return _batch_path(outputs_root, out_name) / _ARTIFACT_NAME

def recompose_command_grounding_path(outputs_root: str | Path, out_name: str) -> Path:
    return _batch_path(outputs_root, out_name) / RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME

def _compile_context_identity(outputs_root: Path, out_name: str) -> str:
    path = _batch_path(outputs_root, out_name) / 'compile_context.json'
    try:
        raw = read_regular_nofollow(path, error_type=MachineMindmapSubmissionError, invalid_message='compile context path is invalid', directory_message='compile context parent is unavailable', open_message='compile context is unavailable', bounds_message='compile context exceeds its boundary', changed_message='compile context changed while reading', max_bytes=2 * 1024 * 1024, min_bytes=1, preserve_missing=True, trusted_root=outputs_root, require_current_uid=True)
    except FileNotFoundError:
        return ''
    assert isinstance(raw, bytes)
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapSubmissionError('compile context is not valid JSON') from exc
    identity = str(document.get('identity_sha256') or '') if isinstance(document, dict) else ''
    if _SHA256_RE.fullmatch(identity) is None:
        raise MachineMindmapSubmissionError('compile context identity is invalid')
    return identity

def _grounding_query(*, kind: str, name: str, domain: str, query: str, position: int) -> dict[str, Any]:
    return {'kind': str(kind or '').strip().lower(), 'name': str(name or '').strip(), 'domain': str(domain or '').strip(), 'query': str(query or '').strip(), 'position': int(position or 0)}

def _grounding_key(query: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(dict(query), ensure_ascii=False))

def _read_grounding_bytes(path: Path, outputs_root: Path) -> bytes | None:
    try:
        raw = read_regular_nofollow(path, error_type=MachineMindmapSubmissionError, invalid_message='recompose command grounding path is invalid', directory_message='recompose command grounding parent is unavailable', open_message='recompose command grounding is unavailable', bounds_message='recompose command grounding exceeds its boundary', changed_message='recompose command grounding changed while reading', max_bytes=_MAX_GROUNDING_BYTES, min_bytes=1, preserve_missing=True, trusted_root=outputs_root, require_current_uid=True)
    except FileNotFoundError:
        return None
    assert isinstance(raw, bytes)
    return raw

def _is_recompose_scope_refusal(entry: Mapping[str, Any]) -> bool:
    query = entry.get('query')
    return entry.get('replayable') is False and entry.get('scope_refusal_reason') == RECOMPOSE_HEADS_SCOPE_REFUSAL and isinstance(query, dict) and (query.get('kind') == 'heads') and bool(str(query.get('name') or '').strip()) and (entry.get('result') == RECOMPOSE_HEADS_SCOPE_REFUSAL_RESULT) and ('head_in_tree' not in entry) and ('recorded_heads' not in entry)

def _validate_grounding_document(document: Any, *, out_name: str, dispatch_id: str, allowed_statuses: frozenset[str]) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get('schema') != _GROUNDING_SCHEMA or document.get('out_name') != out_name or (document.get('dispatch_id') != dispatch_id) or (document.get('status') not in allowed_statuses) or (not isinstance(document.get('entries'), dict)) or (not isinstance(document.get('binding_sha256'), str)) or (_SHA256_RE.fullmatch(str(document.get('binding_sha256') or '')) is None) or (not isinstance(document.get('compile_context_sha256'), str)) or (document.get('compile_context_sha256') and _SHA256_RE.fullmatch(str(document['compile_context_sha256'])) is None):
        raise MachineMindmapSubmissionError('recompose command grounding identity is invalid')
    status = str(document.get('status') or '')
    machine_sha = document.get('machine_mindmap_sha256')
    if status == 'open' and machine_sha is not None or (status == 'sealed' and (not isinstance(machine_sha, str) or _SHA256_RE.fullmatch(machine_sha) is None)):
        raise MachineMindmapSubmissionError('recompose command grounding machine identity is invalid')
    for key, entry in document['entries'].items():
        if not isinstance(key, str) or _SHA256_RE.fullmatch(key) is None or (not isinstance(entry, dict)) or (not isinstance(entry.get('query'), dict)) or (not isinstance(entry.get('result'), str)) or (not isinstance(entry.get('result_sha256'), str)) or (_grounding_key(entry['query']) != key) or (sha256_bytes(entry['result'].encode('utf-8')) != entry['result_sha256']):
            raise MachineMindmapSubmissionError('recompose command grounding entry is invalid')
        if 'scope_refusal_reason' in entry and (not _is_recompose_scope_refusal(entry)):
            raise MachineMindmapSubmissionError('recompose command grounding scope refusal is invalid')
    return document

def _projection_head_stamp(name: str, *, kind: str) -> dict[str, Any] | None:
    if not ' '.join(str(name or '').split()):
        return None
    from cex_core.engine.case_compiler.vendor_stdlib import load_vendor_stdlib
    inventory = load_vendor_stdlib()
    if inventory is None:
        return None
    from cex_core.engine.ist_core.worker_device_context import recorded_command_heads
    heads = recorded_command_heads(inventory, name)
    if not heads and kind == 'complete':
        from cex_core.engine.case_compiler.vendor_stdlib import rank_vendor_command_completions
        continuations = sum((1 for candidate in rank_vendor_command_completions(name) if candidate['prefix_continuation']))
        if continuations:
            return None
    return {'head_in_tree': bool(heads), 'recorded_heads': len(heads)}

def _grounding_request(*, kind: str, name: str, domain: str, query: str, position: int) -> tuple[_RecomposeDispatchScope, str, dict[str, Any], str] | None:
    scope = _CURRENT_RECOMPOSE_DISPATCH.get()
    if scope is None:
        return None
    kind_value = str(kind or '').strip().lower()
    if kind_value not in _GROUNDING_KINDS:
        return None
    query_value = _grounding_query(kind=kind, name=name, domain=domain, query=query, position=position)
    return (scope, kind_value, query_value, _grounding_key(query_value))

def _grounding_entry(*, kind: str, name: str, query: Mapping[str, Any], result: str, scope_refusal_reason: str='') -> dict[str, Any]:
    if not isinstance(result, str) or len(result.encode('utf-8')) > _MAX_GROUNDING_RESULT_BYTES:
        raise MachineMindmapSubmissionError('recompose command grounding result exceeds its boundary')
    entry: dict[str, Any] = {'query': dict(query), 'result': result, 'result_sha256': sha256_bytes(result.encode('utf-8'))}
    if not result.startswith('error:'):
        stamp = _projection_head_stamp(name, kind=kind)
        if stamp is not None:
            entry['head_in_tree'] = stamp['head_in_tree']
            entry['recorded_heads'] = stamp['recorded_heads']
    if scope_refusal_reason:
        entry['replayable'] = False
        entry['scope_refusal_reason'] = scope_refusal_reason
        if kind != 'heads' or not _is_recompose_scope_refusal(entry):
            raise MachineMindmapSubmissionError('recompose command grounding scope refusal is invalid')
    return entry

def _open_grounding_document_locked(scope: _RecomposeDispatchScope, path: Path, *, reset_stale: bool=False) -> tuple[dict[str, Any], str, str]:
    assert_machine_mindmap_submission_open(scope.outputs_root, scope.out_name, scope.dispatch_id)
    prepared = read_machine_mindmap_submission(scope.outputs_root, scope.out_name, scope.dispatch_id)
    if prepared.binding_sha256 != scope.binding_sha256:
        raise MachineMindmapSubmissionError('recompose command grounding dispatch binding changed after scope validation')
    context_sha = _compile_context_identity(scope.outputs_root, scope.out_name)
    raw = _read_grounding_bytes(path, scope.outputs_root)
    fresh = {'schema': _GROUNDING_SCHEMA, 'out_name': scope.out_name, 'dispatch_id': scope.dispatch_id, 'status': 'open', 'machine_mindmap_sha256': None, 'binding_sha256': prepared.binding_sha256, 'compile_context_sha256': context_sha, 'entries': {}}
    if raw is None:
        return (fresh, prepared.binding_sha256, context_sha)
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapSubmissionError('recompose command grounding is not valid JSON') from exc
    document = _validate_grounding_document(document, out_name=scope.out_name, dispatch_id=scope.dispatch_id, allowed_statuses=frozenset({'open'}))
    if document['binding_sha256'] != prepared.binding_sha256 or document['compile_context_sha256'] != context_sha:
        if reset_stale:
            return (fresh, prepared.binding_sha256, context_sha)
        raise MachineMindmapSubmissionError('recompose command grounding context identity drifted')
    return (document, prepared.binding_sha256, context_sha)

def _assert_grounding_identity_stable_locked(scope: _RecomposeDispatchScope, *, binding_sha256: str, compile_context_sha256: str) -> None:
    assert_machine_mindmap_submission_open(scope.outputs_root, scope.out_name, scope.dispatch_id)
    prepared = read_machine_mindmap_submission(scope.outputs_root, scope.out_name, scope.dispatch_id)
    if prepared.binding_sha256 != binding_sha256 or prepared.binding_sha256 != scope.binding_sha256 or _compile_context_identity(scope.outputs_root, scope.out_name) != compile_context_sha256:
        raise MachineMindmapSubmissionError('recompose command grounding context identity drifted while rendering')

def _commit_grounding_entry_locked(path: Path, document: dict[str, Any], *, key: str, entry: dict[str, Any], replace_failed: bool=False) -> None:
    existing = document['entries'].get(key)
    may_replace = replace_failed and isinstance(existing, dict) and str(existing.get('result') or '').startswith('error:')
    if existing is not None and existing != entry and (not may_replace):
        raise MachineMindmapSubmissionError('identical recompose grounding query produced different bytes')
    document['entries'][key] = entry
    encoded = canonical_json(document, ensure_ascii=False)
    if len(encoded) > _MAX_GROUNDING_BYTES:
        raise MachineMindmapSubmissionError('recompose command grounding exceeds its byte budget')
    atomic_write_bytes_nofollow(path, encoded, error_type=MachineMindmapSubmissionError, invalid_message='recompose command grounding path is invalid', unavailable_message='recompose command grounding cannot be committed', create_parents=False, mode=384)

def record_recompose_command_grounding(*, kind: str, name: str='', domain: str='', query: str='', position: int=0, result: str) -> str | None:
    request = _grounding_request(kind=kind, name=name, domain=domain, query=query, position=position)
    if request is None:
        return None
    scope, kind_value, query_value, key = request
    entry = _grounding_entry(kind=kind_value, name=name, query=query_value, result=result)
    batch = _batch_path(scope.outputs_root, scope.out_name)
    path = recompose_command_grounding_path(scope.outputs_root, scope.out_name)
    with _LOCK:
        with _submission_lock(batch):
            document, _binding_sha, _context_sha = _open_grounding_document_locked(scope, path)
            _commit_grounding_entry_locked(path, document, key=key, entry=entry)
    return key

def resolve_recompose_command_grounding(render: Callable[[], str], *, kind: str, name: str='', domain: str='', query: str='', position: int=0, scope_refusal_reason: str='') -> tuple[str, str | None]:
    request = _grounding_request(kind=kind, name=name, domain=domain, query=query, position=position)
    if request is None:
        return (render(), None)
    scope, kind_value, query_value, key = request
    batch = _batch_path(scope.outputs_root, scope.out_name)
    path = recompose_command_grounding_path(scope.outputs_root, scope.out_name)
    with _LOCK:
        with _submission_lock(batch):
            document, binding_sha, context_sha = _open_grounding_document_locked(scope, path, reset_stale=True)
            existing = document['entries'].get(key)
            if isinstance(existing, dict) and (not str(existing.get('result') or '').startswith('error:')):
                return (str(existing['result']), key)
            result = render()
            entry = _grounding_entry(kind=kind_value, name=name, query=query_value, result=result, scope_refusal_reason=scope_refusal_reason)
            _assert_grounding_identity_stable_locked(scope, binding_sha256=binding_sha, compile_context_sha256=context_sha)
            _commit_grounding_entry_locked(path, document, key=key, entry=entry, replace_failed=True)
            return (result, key)

def _seal_recompose_command_grounding_locked(outputs_root: Path, out_name: str, dispatch_id: str, machine_mindmap_sha256: str) -> None:
    path = recompose_command_grounding_path(outputs_root, out_name)
    raw = _read_grounding_bytes(path, outputs_root)
    if raw is None:
        return
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapSubmissionError('recompose command grounding is not valid JSON') from exc
    document = _validate_grounding_document(document, out_name=out_name, dispatch_id=dispatch_id, allowed_statuses=frozenset({'open'}))
    document['status'] = 'sealed'
    document['machine_mindmap_sha256'] = machine_mindmap_sha256
    atomic_write_bytes_nofollow(path, canonical_json(document, ensure_ascii=False), error_type=MachineMindmapSubmissionError, invalid_message='recompose command grounding path is invalid', unavailable_message='recompose command grounding cannot be sealed', create_parents=False, mode=384)

def load_recompose_command_grounding(outputs_root: str | Path, out_name: str, *, machine_mindmap_sha256: str) -> tuple[dict[str, Any], str] | None:
    root = lexical_absolute(outputs_root)
    path = recompose_command_grounding_path(root, out_name)
    raw = _read_grounding_bytes(path, root)
    if raw is None:
        return None
    try:
        document = json.loads(raw.decode('utf-8'))
        dispatch_id = str(document.get('dispatch_id') or '')
    except (AttributeError, UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapSubmissionError('recompose command grounding is not valid JSON') from exc
    document = _validate_grounding_document(document, out_name=out_name, dispatch_id=dispatch_id, allowed_statuses=frozenset({'sealed'}))
    if document.get('machine_mindmap_sha256') != machine_mindmap_sha256:
        raise MachineMindmapSubmissionError('recompose command grounding machine identity drifted')
    receipt = read_machine_mindmap_submission(root, out_name, dispatch_id)
    if receipt.status != 'submitted' or receipt.artifact_sha256 != machine_mindmap_sha256 or document['binding_sha256'] != receipt.binding_sha256 or (document['compile_context_sha256'] != _compile_context_identity(root, out_name)):
        raise MachineMindmapSubmissionError('recompose command grounding dispatch is not the submitted machine identity')
    return (document, sha256_bytes(raw))

def revalidate_recompose_command_grounding(outputs_root: str | Path, out_name: str, *, machine_mindmap_sha256: str, query_runner: Callable[..., str] | None=None) -> tuple[dict[str, Any], str] | None:
    root = lexical_absolute(outputs_root)
    path = recompose_command_grounding_path(root, out_name)
    raw = _read_grounding_bytes(path, root)
    if raw is None:
        return None
    try:
        document = json.loads(raw.decode('utf-8'))
        dispatch_id = str(document.get('dispatch_id') or '')
    except (AttributeError, UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapSubmissionError('recompose command grounding is not valid JSON') from exc
    document = _validate_grounding_document(document, out_name=out_name, dispatch_id=dispatch_id, allowed_statuses=frozenset({'sealed'}))
    if document.get('machine_mindmap_sha256') != machine_mindmap_sha256:
        raise MachineMindmapSubmissionError('recompose command grounding machine identity drifted')
    receipt = read_machine_mindmap_submission(root, out_name, dispatch_id)
    if receipt.status != 'submitted' or receipt.artifact_sha256 != machine_mindmap_sha256 or document['binding_sha256'] != receipt.binding_sha256:
        raise MachineMindmapSubmissionError('recompose command grounding dispatch is not the submitted machine identity')
    current_context_sha = _compile_context_identity(root, out_name)
    if not current_context_sha:
        raise MachineMindmapSubmissionError('recompose command grounding has no current compile context')
    if document['compile_context_sha256'] == current_context_sha:
        return (document, sha256_bytes(raw))
    if _CURRENT_RECOMPOSE_DISPATCH.get() is not None:
        raise MachineMindmapSubmissionError('recompose command grounding cannot be revalidated inside its write scope')
    if query_runner is None:
        from cex_core.engine.ist_core.tools.device.lang_query_tool import lang_query
        query_runner = lang_query.func
    for key in sorted(document['entries']):
        entry = document['entries'][key]
        if _is_recompose_scope_refusal(entry):
            continue
        query = dict(entry['query'])
        if str(query.get('kind') or '') not in {'param', 'complete', 'heads'}:
            raise MachineMindmapSubmissionError('recompose command grounding contains a non-replayable query')
        try:
            replayed = query_runner(**query)
        except Exception as exc:
            raise MachineMindmapSubmissionError('recompose command grounding query replay failed') from exc
        if not isinstance(replayed, str) or replayed != entry['result']:
            raise MachineMindmapSubmissionError('recompose command grounding query result changed under current context')
    rebound = dict(document)
    rebound['compile_context_sha256'] = current_context_sha
    encoded = canonical_json(rebound, ensure_ascii=False)
    with _LOCK:
        with _submission_lock(_batch_path(root, out_name)):
            current_raw = _read_grounding_bytes(path, root)
            if current_raw != raw:
                raise MachineMindmapSubmissionError('recompose command grounding changed during context revalidation')
            if _compile_context_identity(root, out_name) != current_context_sha:
                raise MachineMindmapSubmissionError('compile context changed during grounding revalidation')
            atomic_write_bytes_nofollow(path, encoded, error_type=MachineMindmapSubmissionError, invalid_message='recompose command grounding path is invalid', unavailable_message='recompose command grounding cannot be rebound', create_parents=False, mode=384)
    return (rebound, sha256_bytes(encoded))

def _validate_binding(binding: Mapping[str, object]) -> tuple[dict[str, object], str]:
    value = dict(binding)
    if set(value) != _BINDING_KEYS:
        raise MachineMindmapSubmissionError('machine mindmap submission binding shape is invalid')
    for key in ('source', 'governing_spec_status', 'defect_spec_status'):
        if not isinstance(value.get(key), str) or not str(value[key]).strip():
            raise MachineMindmapSubmissionError(f'machine mindmap submission binding field is invalid: {key}')
    for key in ('governing_spec', 'governing_spec_sha256', 'governing_spec_generation_id', 'governing_spec_manifest_sha256', 'defect_spec_receipt_sha256'):
        if value.get(key) is not None and (not isinstance(value.get(key), str)):
            raise MachineMindmapSubmissionError(f'machine mindmap submission binding field is invalid: {key}')
    return (value, sha256_bytes(canonical_json(value, ensure_ascii=False)))

def machine_mindmap_submission_binding_from_brief(brief: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(brief, Mapping):
        raise MachineMindmapSubmissionError('machine mindmap submission brief is invalid')
    try:
        binding = {'source': brief['mindmap_path'], 'governing_spec': brief['governing_spec'], 'governing_spec_status': brief['governing_spec_status'], 'governing_spec_sha256': brief['governing_spec_sha256'], 'governing_spec_generation_id': brief['governing_spec_generation_id'], 'governing_spec_manifest_sha256': brief['governing_spec_manifest_sha256'], 'defect_spec_status': brief['defect_spec_status'], 'defect_spec_receipt_sha256': brief['defect_spec_receipt_sha256']}
    except KeyError as exc:
        raise MachineMindmapSubmissionError('machine mindmap submission brief binding is incomplete') from exc
    return _validate_binding(binding)[0]

def _prepared_payload(out_name: str, dispatch_id: str, binding: Mapping[str, object]) -> dict[str, object]:
    bound, binding_sha256 = _validate_binding(binding)
    return {'schema': SCHEMA, 'out_name': out_name, 'dispatch_id': dispatch_id, 'status': 'prepared', 'artifact_sha256': None, 'artifact_size': None, 'binding': bound, 'binding_sha256': binding_sha256}

def _remove_regular_leaf(directory_fd: int, name: str) -> None:
    try:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()):
        raise MachineMindmapSubmissionError('machine mindmap submission target is not a sealed regular file')
    os.unlink(name, dir_fd=directory_fd)

@contextmanager
def _submission_lock(batch: Path) -> Iterator[int]:
    directory_fd = open_directory_nofollow(batch, error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap submission batch path is invalid', unavailable_message='machine mindmap submission batch is unavailable')
    lock_fd: int | None = None
    try:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
        try:
            lock_fd = os.open(MACHINE_MINDMAP_SUBMISSION_LOCK_NAME, flags, 384, dir_fd=directory_fd)
        except OSError as exc:
            raise MachineMindmapSubmissionError('machine mindmap submission lock is unavailable') from exc
        info = os.fstat(lock_fd)
        named = os.stat(MACHINE_MINDMAP_SUBMISSION_LOCK_NAME, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or not stat.S_ISREG(named.st_mode) or int(info.st_nlink) != 1 or (int(named.st_nlink) != 1) or ((int(info.st_dev), int(info.st_ino)) != (int(named.st_dev), int(named.st_ino))) or stat.S_IMODE(info.st_mode) & 63 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()):
            raise MachineMindmapSubmissionError('machine mindmap submission lock identity is invalid')
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield directory_fd
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)
        os.close(directory_fd)

def initialize_machine_mindmap_submission(outputs_root: str | Path, out_name: str, dispatch_id: str, *, binding: Mapping[str, object], case_autoids: Sequence[str] | None=None, source_sha256: str | None=None) -> tuple[Path, tuple[str, ...]]:
    name, identity = _validate_identity(out_name, dispatch_id)
    batch = _batch_path(outputs_root, name)
    bound, binding_sha256 = _validate_binding(binding)
    del bound
    with _LOCK:
        with _submission_lock(batch) as directory_fd:
            preserved_grounding: dict[str, Any] | None = None
            grounding_path = recompose_command_grounding_path(outputs_root, name)
            try:
                grounding_raw = _read_grounding_bytes(grounding_path, lexical_absolute(outputs_root))
                if grounding_raw is not None:
                    candidate = json.loads(grounding_raw.decode('utf-8'))
                    old_dispatch = str(candidate.get('dispatch_id') or '')
                    _validate_identity(name, old_dispatch)
                    preserved_grounding = _validate_grounding_document(candidate, out_name=name, dispatch_id=old_dispatch, allowed_statuses=frozenset({'open', 'sealed'}))
            except (OSError, ValueError, RecursionError):
                preserved_grounding = None
            _remove_regular_leaf(directory_fd, _ARTIFACT_NAME)
            _remove_regular_leaf(directory_fd, RECOMPOSE_COMMAND_GROUNDING_SIDECAR_NAME)
            _remove_regular_leaf(directory_fd, MACHINE_MINDMAP_SUBMISSION_RECEIPT_NAME)
            os.fsync(directory_fd)
            already_submitted: tuple[str, ...] = ()
            if case_autoids:
                from cex_core.engine.ist_core.tools.device.recompose_parts import initialize_machine_mindmap_parts
                if not isinstance(source_sha256, str):
                    raise MachineMindmapSubmissionError('machine mindmap parts dispatch requires the source digest')
                _parts_path, snapshot = initialize_machine_mindmap_parts(outputs_root, name, binding_sha256=binding_sha256, source_sha256=source_sha256, case_autoids=case_autoids)
                already_submitted = snapshot.submitted_autoids
            else:
                from cex_core.engine.ist_core.tools.device.recompose_parts import discard_machine_mindmap_parts
                discard_machine_mindmap_parts(outputs_root, name)
            context_sha = _compile_context_identity(lexical_absolute(outputs_root), name)
            if preserved_grounding is not None and preserved_grounding['binding_sha256'] == binding_sha256 and (preserved_grounding['compile_context_sha256'] == context_sha):
                preserved_grounding = dict(preserved_grounding)
                preserved_grounding.update({'dispatch_id': identity, 'status': 'open', 'machine_mindmap_sha256': None})
                atomic_write_bytes_nofollow(grounding_path, canonical_json(preserved_grounding, ensure_ascii=False), error_type=MachineMindmapSubmissionError, invalid_message='recompose command grounding path is invalid', unavailable_message='recompose command grounding cannot be rebound', create_parents=False, mode=384)
            receipt_path = machine_mindmap_submission_path(outputs_root, name)
            atomic_write_bytes_nofollow(receipt_path, canonical_json(_prepared_payload(name, identity, binding), ensure_ascii=False), error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap submission receipt path is invalid', unavailable_message='machine mindmap submission cannot be prepared safely', create_parents=False, mode=384)
            return (receipt_path, already_submitted)

def _decode_receipt(raw: bytes) -> dict[str, object]:

    def reject_duplicates(pairs):
        out: dict[str, object] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('duplicate JSON key')
            out[key] = value
        return out

    def reject_constant(value):
        raise ValueError(f'non-finite JSON constant: {value}')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise MachineMindmapSubmissionError('machine mindmap submission receipt is invalid JSON') from exc
    if not isinstance(value, dict):
        raise MachineMindmapSubmissionError('machine mindmap submission receipt must be an object')
    return value

def rederive_sealed_mechanical_fields(outputs_root: Path, name: str, mindmap_text: str) -> list[str]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import fill_mechanical_fields, load_machine_mindmap
    artifact_path = machine_mindmap_artifact_path(outputs_root, name)
    receipt_path = machine_mindmap_submission_path(outputs_root, name)
    if not artifact_path.exists():
        return []
    data, _sha = load_machine_mindmap(artifact_path)
    repaired = fill_mechanical_fields(data, mindmap_text)
    if not repaired:
        return []
    raw = canonical_json(data, ensure_ascii=False)
    atomic_write_bytes_nofollow(artifact_path, raw, error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap artifact path is invalid', unavailable_message='machine mindmap artifact cannot be committed safely', create_parents=False, mode=384)
    try:
        receipt = json.loads(receipt_path.read_bytes().decode('utf-8'))
    except Exception:
        return repaired
    receipt['artifact_sha256'] = hashlib.sha256(raw).hexdigest()
    receipt['artifact_size'] = len(raw)
    atomic_write_bytes_nofollow(receipt_path, canonical_json(receipt, ensure_ascii=False), error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap submission receipt path is invalid', unavailable_message='machine mindmap submission receipt cannot be committed', create_parents=False, mode=384)
    return repaired

def read_machine_mindmap_submission(outputs_root: str | Path, out_name: str, dispatch_id: str) -> MachineMindmapSubmissionReceipt:
    name, identity = _validate_identity(out_name, dispatch_id)
    root = lexical_absolute(outputs_root)
    path = machine_mindmap_submission_path(root, name)
    raw = read_regular_nofollow(path, error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap submission receipt path is invalid', directory_message='machine mindmap submission receipt parent is unavailable', open_message='machine mindmap submission receipt is unavailable', bounds_message='machine mindmap submission receipt exceeds its boundary', changed_message='machine mindmap submission receipt changed while reading', max_bytes=_MAX_RECEIPT_BYTES, min_bytes=1, trusted_root=root, require_current_uid=True)
    assert isinstance(raw, bytes)
    value = _decode_receipt(raw)
    required = {'schema', 'out_name', 'dispatch_id', 'status', 'artifact_sha256', 'artifact_size', 'binding', 'binding_sha256'}
    if set(value) != required or value.get('schema') != SCHEMA or value.get('out_name') != name or (value.get('dispatch_id') != identity) or (value.get('status') not in {'prepared', 'submitted'}):
        raise MachineMindmapSubmissionError('machine mindmap submission receipt identity is stale')
    status = str(value['status'])
    digest = value.get('artifact_sha256')
    size = value.get('artifact_size')
    raw_binding = value.get('binding')
    raw_binding_sha256 = value.get('binding_sha256')
    if not isinstance(raw_binding, dict):
        raise MachineMindmapSubmissionError('machine mindmap submission binding is invalid')
    binding, binding_sha256 = _validate_binding(raw_binding)
    if raw_binding_sha256 != binding_sha256:
        raise MachineMindmapSubmissionError('machine mindmap submission binding identity changed')
    if status == 'prepared':
        if digest is not None or size is not None:
            raise MachineMindmapSubmissionError('prepared machine mindmap submission has artifact identity')
    elif not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None or isinstance(size, bool) or (not isinstance(size, int)) or (size < 1) or (size > _MAX_ARTIFACT_BYTES):
        raise MachineMindmapSubmissionError('submitted machine mindmap identity is invalid')
    return MachineMindmapSubmissionReceipt(out_name=name, dispatch_id=identity, status=status, artifact_sha256=digest if isinstance(digest, str) else None, artifact_size=size if isinstance(size, int) else None, binding=binding, binding_sha256=binding_sha256)

def assert_machine_mindmap_submission_binding(outputs_root: str | Path, out_name: str, dispatch_id: str, *, expected_binding: Mapping[str, object]) -> MachineMindmapSubmissionReceipt:
    receipt = read_machine_mindmap_submission(outputs_root, out_name, dispatch_id)
    expected, expected_sha256 = _validate_binding(expected_binding)
    if receipt.binding != expected or receipt.binding_sha256 != expected_sha256:
        raise MachineMindmapSubmissionError('machine mindmap submission does not match the expected binding')
    return receipt

def assert_machine_mindmap_submission_open(outputs_root: str | Path, out_name: str, dispatch_id: str) -> None:
    receipt = read_machine_mindmap_submission(outputs_root, out_name, dispatch_id)
    if receipt.status != 'prepared':
        raise MachineMindmapSubmissionError('machine mindmap submission is already closed')

@contextmanager
def recompose_dispatch_scope(outputs_root: str | Path, out_name: str, dispatch_id: str, *, assigned_autoids: Sequence[str]=()) -> Iterator[None]:
    name, identity = _validate_identity(out_name, dispatch_id)
    root = lexical_absolute(outputs_root)
    receipt = read_machine_mindmap_submission(root, name, identity)
    if receipt.status != 'prepared':
        raise MachineMindmapSubmissionError('machine mindmap submission is already closed')
    assigned = _validated_assignment(root, name, assigned_autoids)
    token = _CURRENT_RECOMPOSE_DISPATCH.set(_RecomposeDispatchScope(root, name, identity, receipt.binding_sha256, assigned))
    try:
        yield
    finally:
        _CURRENT_RECOMPOSE_DISPATCH.reset(token)

def _validated_assignment(outputs_root: Path, out_name: str, assigned_autoids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(assigned_autoids, (str, bytes)):
        raise MachineMindmapSubmissionError('recompose assignment must be a sequence of autoids')
    requested = [str(aid or '').strip() for aid in assigned_autoids or ()]
    if not requested:
        return ()
    if any((not _AUTOID_RE.match(aid) for aid in requested)):
        raise MachineMindmapSubmissionError('recompose assignment carries a malformed autoid')
    if len(set(requested)) != len(requested):
        raise MachineMindmapSubmissionError('recompose assignment repeats an autoid')
    from cex_core.engine.ist_core.tools.device.recompose_parts import read_machine_mindmap_parts
    snapshot = read_machine_mindmap_parts(outputs_root, out_name)
    closed = set(snapshot.case_autoids)
    stray = [aid for aid in requested if aid not in closed]
    if stray:
        raise MachineMindmapSubmissionError('recompose assignment names cases outside the dispatched set')
    wanted = set(requested)
    return tuple((aid for aid in snapshot.case_autoids if aid in wanted))

def current_recompose_assignment() -> tuple[str, ...]:
    scope = _CURRENT_RECOMPOSE_DISPATCH.get()
    if scope is None:
        raise MachineMindmapSubmissionError('recompose submission requires a trusted dispatch')
    return scope.assigned_autoids

def current_recompose_dispatch() -> tuple[Path, str, str]:
    scope = _CURRENT_RECOMPOSE_DISPATCH.get()
    if scope is None:
        raise MachineMindmapSubmissionError('recompose submission requires a trusted dispatch')
    return (scope.outputs_root, scope.out_name, scope.dispatch_id)

def in_recompose_dispatch_scope() -> bool:
    return _CURRENT_RECOMPOSE_DISPATCH.get() is not None

@contextmanager
def machine_mindmap_submission_open_guard(outputs_root: str | Path, out_name: str, dispatch_id: str) -> Iterator[None]:
    name, identity = _validate_identity(out_name, dispatch_id)
    with _LOCK:
        with _submission_lock(_batch_path(outputs_root, name)):
            assert_machine_mindmap_submission_open(outputs_root, name, identity)
            yield

def _step_structure_face(case: Mapping[str, Any]) -> str:
    from cex_core.engine.case_compiler.step_structure import ADAPTED_STEPS_KEY
    return json.dumps({'step_structure': case.get('step_structure'), 'engine_slots': case.get('engine_slots'), ADAPTED_STEPS_KEY: case.get(ADAPTED_STEPS_KEY)}, ensure_ascii=False, sort_keys=True, default=str)

def _reject_inline_step_structure(envelope: dict[str, Any], ledger_faces: dict[str, str]) -> None:
    from cex_core.engine.case_compiler.step_structure import budget_violations, object_kind_closed_set, step_structure_violations, strip_engine_slots
    cases = envelope.get('cases')
    if not isinstance(cases, list):
        return
    object_kinds = object_kind_closed_set()
    violations: list[dict[str, str]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        autoid = str(case.get('autoid') or '')
        if autoid and ledger_faces.get(autoid) == _step_structure_face(case):
            continue
        strip_engine_slots(case)
        violations.extend(step_structure_violations(case, index=index, object_kinds=object_kinds))
    if not violations:
        return
    budgeted = budget_violations(violations)
    raise MachineMindmapContentError(json.dumps({'violations': budgeted}, ensure_ascii=False, sort_keys=True), code=str(budgeted[0].get('code') or 'step_structure_missing'))

def submit_machine_mindmap_payload(outputs_root: str | Path, out_name: str, dispatch_id: str, payload: Mapping[str, Any]) -> MachineMindmapSubmissionReceipt:
    from cex_core.engine.case_compiler.mindmap_contract_projector import MachineMindmapError, validate_machine_mindmap_payload
    name, identity = _validate_identity(out_name, dispatch_id)
    envelope = copy.deepcopy(dict(payload))
    inline_cases = envelope.get('cases')
    ledger_faces: dict[str, str] = {}
    artifact_path = machine_mindmap_artifact_path(outputs_root, name)
    with _LOCK:
        with _submission_lock(_batch_path(outputs_root, name)):
            assert_machine_mindmap_submission_open(outputs_root, name, identity)
            prepared_receipt = read_machine_mindmap_submission(outputs_root, name, identity)
            scope = _CURRENT_RECOMPOSE_DISPATCH.get()
            if scope is not None:
                if scope.outputs_root != lexical_absolute(outputs_root) or scope.out_name != name or scope.dispatch_id != identity or (scope.binding_sha256 != prepared_receipt.binding_sha256):
                    raise MachineMindmapSubmissionError('machine mindmap submission dispatch binding changed after scope validation')
            binding = prepared_receipt.binding
            canonicalized = [key for key in _ARTIFACT_BINDING_KEYS if key in envelope and envelope[key] != binding[key]]
            if canonicalized:
                logger.warning('ignored non-authoritative machine mindmap binding fields: %s', ','.join(canonicalized))
            for key in _ARTIFACT_BINDING_KEYS:
                envelope[key] = binding[key]
            from cex_core.engine.ist_core.tools.device.recompose_parts import MachineMindmapPartsError, _case_is_hollow, read_machine_mindmap_parts
            try:
                snapshot = read_machine_mindmap_parts(outputs_root, name, binding_sha256=prepared_receipt.binding_sha256, preserve_missing=True)
            except FileNotFoundError:
                snapshot = None
            except (MachineMindmapPartsError, OSError) as exc:
                raise MachineMindmapSubmissionError('machine mindmap parts ledger is present but unverifiable') from exc
            if snapshot is not None and snapshot.cases:
                merged = dict(snapshot.cases)
                signed = list(snapshot.case_autoids)
                ledger_faces = {str(autoid): _step_structure_face(value) for autoid, value in snapshot.cases.items() if isinstance(value, dict)}
                extra: list[dict[str, Any]] = []
                for case in inline_cases or ():
                    if not isinstance(case, dict):
                        raise MachineMindmapContentError('machine mindmap structured payload is invalid: every inline case must be a JSON object', code='mindmap_payload_invalid')
                    autoid = case.get('autoid')
                    if isinstance(autoid, str) and autoid in merged:
                        merged[autoid] = case
                    elif isinstance(autoid, str) and autoid in signed:
                        merged[autoid] = case
                    else:
                        extra.append(case)
                ordered = [merged[aid] for aid in signed if aid in merged and (not _case_is_hollow(merged[aid]))] + extra
                envelope['cases'] = ordered
                envelope['case_count'] = len(ordered)
        if envelope.get('cases'):
            source_materialized = False
            try:
                from cex_core.engine.case_compiler.mindmap_contract_projector import fill_mechanical_fields
                source_bytes = read_regular_nofollow(_batch_path(outputs_root, name) / 'mindmap_source.json', error_type=MachineMindmapSubmissionError, invalid_message='mindmap source path is invalid', directory_message='mindmap source parent is unavailable', open_message='mindmap source is unavailable', bounds_message='mindmap source exceeds its boundary', changed_message='mindmap source changed while reading', max_bytes=_MAX_ARTIFACT_BYTES, min_bytes=1, trusted_root=lexical_absolute(outputs_root))
                assert isinstance(source_bytes, bytes)
                fill_mechanical_fields(envelope, source_bytes.decode('utf-8', errors='replace').lstrip('\ufeff\uffff'))
                source_materialized = True
            except Exception:
                pass
            from cex_core.engine.case_compiler.mindmap_contract_projector import case_status_mismatches, normalize_submission_case_statuses, primary_expectation_projection_problems
            for case in envelope.get('cases') or ():
                if not source_materialized or not isinstance(case, dict):
                    continue
                primary_problems = primary_expectation_projection_problems(case)
                if primary_problems:
                    field, code = primary_problems[0]
                    raise MachineMindmapContentError(f"case {case.get('autoid')}: {field} is empty despite authored expectation atoms in expectations_by_step", code=code)
                normalize_submission_case_statuses(case)
                mismatches = case_status_mismatches(case)
                if mismatches:
                    field, actual = mismatches[0]
                    raise MachineMindmapContentError(f"case {case.get('autoid')}: {field} cannot be validated against the submitted assertion fields ({actual})", code='case_status_mismatch')
            _reject_inline_step_structure(envelope, ledger_faces)
            try:
                document = validate_machine_mindmap_payload(envelope)
            except MachineMindmapError as exc:
                raise MachineMindmapContentError(str(exc), code='mindmap_schema_invalid') from exc
            cases = document.get('cases')
            declared_count = document.get('case_count')
            if document.get('schema') != 'ist.machine-mindmap' or not isinstance(document.get('source'), str) or (not str(document.get('source') or '').strip()) or (not isinstance(cases, list)) or any((not isinstance(case, dict) for case in cases)) or isinstance(declared_count, bool) or (not isinstance(declared_count, int)) or (declared_count != len(cases)):
                raise MachineMindmapContentError('machine mindmap structured payload is invalid: schema must be ist.machine-mindmap, source must be a non-empty string, cases must be a list of objects, and case_count must equal len(cases)', code='mindmap_payload_invalid')
            raw = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
            if not raw or len(raw) > _MAX_ARTIFACT_BYTES:
                raise MachineMindmapContentError('machine mindmap artifact exceeds its byte budget', code='mindmap_budget_exceeded')
            validate_json_budget(raw, error_type=MachineMindmapContentError, message='machine mindmap exceeds the JSON structure budget')
            digest = sha256_bytes(raw)
            try:
                existing = read_regular_nofollow(artifact_path, error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap artifact path is invalid', directory_message='machine mindmap artifact parent is unavailable', open_message='machine mindmap artifact is unavailable', bounds_message='machine mindmap artifact exceeds its boundary', changed_message='machine mindmap artifact changed while reading', max_bytes=_MAX_ARTIFACT_BYTES, min_bytes=1, preserve_missing=True, trusted_root=lexical_absolute(outputs_root), require_current_uid=True)
            except FileNotFoundError:
                existing = None
            if existing is not None and existing != raw:
                raise MachineMindmapSubmissionError('machine mindmap artifact already exists for this dispatch')
            if existing is None:
                atomic_write_bytes_nofollow(artifact_path, raw, error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap artifact path is invalid', unavailable_message='machine mindmap artifact cannot be committed safely', create_parents=False, mode=384)
            _seal_recompose_command_grounding_locked(lexical_absolute(outputs_root), name, identity, digest)
            submitted = {'schema': SCHEMA, 'out_name': name, 'dispatch_id': identity, 'status': 'submitted', 'artifact_sha256': digest, 'artifact_size': len(raw), 'binding': binding, 'binding_sha256': prepared_receipt.binding_sha256}
            atomic_write_bytes_nofollow(machine_mindmap_submission_path(outputs_root, name), canonical_json(submitted, ensure_ascii=False), error_type=MachineMindmapSubmissionError, invalid_message='machine mindmap submission receipt path is invalid', unavailable_message='machine mindmap submission receipt cannot be committed', create_parents=False, mode=384)
    return read_machine_mindmap_submission(outputs_root, name, identity)

def verify_machine_mindmap_submission_commit(outputs_root: str | Path, out_name: str, dispatch_id: str, *, expected_binding: Mapping[str, object] | None=None) -> tuple[MachineMindmapSubmissionReceipt, dict[str, Any], dict[str, int]]:
    from cex_core.engine.case_compiler.mindmap_contract_projector import MachineMindmapError, load_machine_mindmap
    from cex_core.engine.ist_core.tools.device.recompose_parts import MACHINE_MINDMAP_BUCKETS
    receipt = assert_machine_mindmap_submission_binding(outputs_root, out_name, dispatch_id, expected_binding=expected_binding) if expected_binding is not None else read_machine_mindmap_submission(outputs_root, out_name, dispatch_id)
    if receipt.status != 'submitted':
        raise MachineMindmapSubmissionError('machine mindmap submission has no durable commit')
    artifact_path = machine_mindmap_artifact_path(outputs_root, out_name)
    try:
        payload, digest = load_machine_mindmap(artifact_path)
    except MachineMindmapError as exc:
        raise MachineMindmapSubmissionError(str(exc)) from exc
    try:
        size = artifact_path.stat(follow_symlinks=False).st_size
    except OSError as exc:
        raise MachineMindmapSubmissionError('machine mindmap submitted artifact is unavailable') from exc
    if digest != receipt.artifact_sha256 or size != receipt.artifact_size:
        raise MachineMindmapSubmissionError('machine mindmap submitted artifact identity changed')
    raw_cases = payload.get('cases')
    case_count = payload.get('case_count')
    if not isinstance(raw_cases, list) or any((not isinstance(case, dict) for case in raw_cases)) or isinstance(case_count, bool) or (not isinstance(case_count, int)) or (case_count != len(raw_cases)):
        raise MachineMindmapSubmissionError('machine mindmap submitted case count is invalid')
    bucket_counts = {name: 0 for name in MACHINE_MINDMAP_BUCKETS}
    for case in raw_cases:
        bucket = case.get('bucket')
        if not isinstance(bucket, str) or bucket not in bucket_counts:
            raise MachineMindmapSubmissionError('machine mindmap submitted bucket is invalid')
        bucket_counts[bucket] += 1
    return (receipt, payload, bucket_counts)

def canonical_machine_mindmap_submission_result(outputs_root: str | Path, out_name: str, dispatch_id: str, *, expected_binding: Mapping[str, object] | None=None) -> str:
    from cex_core.engine.ist_core.compile_engine.recompose_protocol import render_mindmap_recompose_result
    receipt, payload, bucket_counts = verify_machine_mindmap_submission_commit(outputs_root, out_name, dispatch_id, expected_binding=expected_binding)
    case_count = payload['case_count']
    return render_mindmap_recompose_result({'schema': 'ist.mindmap-recompose-result', 'status': 'produced', 'artifact': f'{receipt.out_name}/{_ARTIFACT_NAME}', 'summary': {'case_count': case_count, 'bucket_counts': bucket_counts, 'message_zh': '机器脑图已通过受信任派发的单次结构化提交'}, 'error_code': None, 'reason_zh': None})
__all__ = ['MachineMindmapContentError', 'MachineMindmapSubmissionError', 'MachineMindmapSubmissionReceipt', 'assert_machine_mindmap_submission_binding', 'assert_machine_mindmap_submission_open', 'canonical_machine_mindmap_submission_result', 'current_recompose_assignment', 'current_recompose_dispatch', 'initialize_machine_mindmap_submission', 'load_recompose_command_grounding', 'machine_mindmap_artifact_path', 'machine_mindmap_submission_binding_from_brief', 'machine_mindmap_submission_open_guard', 'machine_mindmap_submission_path', 'read_machine_mindmap_submission', 'record_recompose_command_grounding', 'resolve_recompose_command_grounding', 'revalidate_recompose_command_grounding', 'recompose_command_grounding_path', 'recompose_dispatch_scope', 'rederive_sealed_mechanical_fields', 'submit_machine_mindmap_payload', 'verify_machine_mindmap_submission_commit']
