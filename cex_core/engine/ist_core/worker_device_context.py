# 生成：tools/extract_engine.py ← InfoTest main/ist_core/worker_device_context.py（sha256 8275c23cf9387e3c）。不在这里手改。
from __future__ import annotations
from cex_core.engine.common.engine_track_schema import accepts_engine_schema, engine_schema_id
import contextvars
import copy
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from cex_core.engine.ist_core.security_scrub import canonical_persisted_value, persisted_surface_sha256
_DEFAULT_MAX_ROUNDS = 3
_MAX_ROUNDS_CEILING = 10
_DEFAULT_MAX_PROBE_CALLS = 5
_MAX_PROBE_CALLS_CEILING = 5
_COMPILE_LEARNING_GATES = frozenset({'mutation_contract_invalid', 'assertion_type_invalid', 'assertion_type_derivation_failed', 'provenance_parse_failed', 'provenance_step_count_mismatch', 'blocks_parse_failed', 'blocks_type_invalid', 'blocks_invalid'})
_SCOPE: contextvars.ContextVar['WorkerDeviceSession | None'] = contextvars.ContextVar('ist_worker_device_scope', default=None)
_DEVICE_ACCESS: contextvars.ContextVar[bool] = contextvars.ContextVar('ist_worker_device_access', default=False)
_FORK_SCOPE: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar('ist_fork_execution_scope', default=None)
_SESSIONS: dict[str, 'WorkerDeviceSession'] = {}
_SESSIONS_LOCK = threading.Lock()
_COMPLETED: list[dict] = []
_COMPLETED_LOCK = threading.Lock()
_SESSION_OUTCOMES: list[dict] = []
_SESSION_OUTCOMES_LOCK = threading.Lock()
_SESSION_JOURNAL_LOCK = threading.Lock()
_QUARANTINED: list[dict] = []
_REVOKED_DISPATCHES: set[str] = set()
_DISPATCH_ID_RE = re.compile('^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$')
SESSION_ADMISSION_REJECTION_EVENT = 'session_admission_rejected'
SESSION_ADMISSION_REJECTION_SITE = 'worker_session_admission'
SESSION_ADMISSION_IDENTITY_FIELDS = ('autoid', 'fork_id', 'dispatch_id', 'batch_run_id')
_ADMISSION_REJECTION_FIELDS = frozenset({*SESSION_ADMISSION_IDENTITY_FIELDS, 'code', 'detail', 'message_sha256', 'exception_type', 'source_manifest_ref', 'source_manifest_sha256', 'source_case_slice_sha256', 'record_id'})
WORKER_READ_ONLY_PROBE_CONTRACT = 'ist.worker_probe.read_only'
_MAX_WORKER_JOURNAL_BYTES = 64 * 1024 * 1024
_MAX_WORKER_JOURNAL_RECORD_BYTES = 1024 * 1024
COMMAND_HEADS_QUERY_SCHEMA = 'ist.command-heads-query'
_COMMAND_HEADS_RECEIPT_KEYS = frozenset({'schema', 'status', 'module_prefix', 'device_build', 'capability_generation_id', 'capability_manifest_sha256', 'projection_version', 'count', 'heads', 'receipt_id', 'result_sha256'})
COMMAND_HEADS_RECEIPT_REDACTION_FOLDED = 'command_heads_receipt_redaction_folded'
COMMAND_HEADS_RECEIPT_VALIDATION_CODES = frozenset({'command_heads_receipt_shape_invalid', 'command_heads_expected_identity_invalid', 'command_heads_receipt_schema_invalid', 'command_heads_receipt_incomplete', 'command_heads_receipt_inventory_invalid', COMMAND_HEADS_RECEIPT_REDACTION_FOLDED, 'command_heads_receipt_identity_mismatch', 'command_heads_receipt_hash_mismatch', 'command_heads_receipt_id_invalid'})
_REDACTION_MARKER = '****'

def _redaction_folded_inventory(heads: list, *, count: int) -> bool:
    if not isinstance(heads, list) or not heads:
        return False
    if any((not isinstance(head, str) for head in heads)):
        return False
    if count != len(heads) or heads != sorted(heads):
        return False
    seen: set[str] = set()
    duplicated: set[str] = set()
    for head in heads:
        if head in seen:
            duplicated.add(head)
        seen.add(head)
    if not duplicated:
        return False
    return all((_REDACTION_MARKER in head for head in duplicated))
COMMAND_HEADS_SESSION_RECEIPTS_MISSING = 'command_heads_session_receipts_missing'
COMMAND_HEADS_RECEIPT_SEQUENCE_MISMATCH = 'command_heads_receipt_sequence_mismatch'
NOT_COMPILABLE_HEADS_SUMMARY_MISMATCH = 'not_compilable_report_heads_summary_mismatch'
NOT_COMPILABLE_HEADS_REFS_MISSING = 'not_compilable_report_heads_refs_missing'
NOT_COMPILABLE_HEADS_REF_UNKNOWN = 'not_compilable_report_heads_ref_unknown'
NOT_COMPILABLE_HEADS_VALIDATION_CODES = frozenset({*COMMAND_HEADS_RECEIPT_VALIDATION_CODES, COMMAND_HEADS_SESSION_RECEIPTS_MISSING, COMMAND_HEADS_RECEIPT_SEQUENCE_MISMATCH, NOT_COMPILABLE_HEADS_SUMMARY_MISMATCH, NOT_COMPILABLE_HEADS_REFS_MISSING, NOT_COMPILABLE_HEADS_REF_UNKNOWN})
NOT_COMPILABLE_REASON_NO_CLI = 'no_cli_equivalent'
NOT_COMPILABLE_REASON_ENV_GAP = 'environment_prerequisite_gap'
NOT_COMPILABLE_REASON_AUTHOR_GAP = 'author_definition_gap'
NOT_COMPILABLE_REASON_AUTHOR_CONFLICT = 'author_definition_conflict'
NOT_COMPILABLE_REASON_CODES = frozenset({NOT_COMPILABLE_REASON_NO_CLI, NOT_COMPILABLE_REASON_ENV_GAP, NOT_COMPILABLE_REASON_AUTHOR_GAP, NOT_COMPILABLE_REASON_AUTHOR_CONFLICT})
AUTHOR_SIDE_NOT_COMPILABLE_REASON_CODES = frozenset({NOT_COMPILABLE_REASON_AUTHOR_GAP, NOT_COMPILABLE_REASON_AUTHOR_CONFLICT})
WORKER_CLAIM_SCHEMA = 'ist.worker-claim'
WORKER_CLAIM_REJECTION_CODES = frozenset({'author_gap_expectation_already_signed', 'environment_gap_unverified', 'no_cli_signed_expectation_unverified', 'author_conflict_surfaces_insufficient', 'author_conflict_expectation_unsigned'})

def command_heads_prefix_shape_valid(prefix: Any) -> bool:
    return isinstance(prefix, str) and bool(prefix) and (prefix == prefix.strip().casefold()) and ('  ' not in prefix) and (not any((ch.isspace() and ch != ' ' for ch in prefix))) and (not any((ord(ch) < 32 for ch in prefix)))

def command_head_matches_prefix(head: str, prefix: str) -> bool:
    folded = str(head).casefold()
    return folded == prefix or folded.startswith(prefix + ' ')

def recorded_command_heads(inventory: dict, prefix: Any) -> list[str]:
    normalized = ' '.join(str(prefix or '').split()).casefold()
    if not normalized:
        return []
    return sorted((str(head) for head in (inventory or {}).get('headers') or {} if command_head_matches_prefix(str(head), normalized)))

def validate_command_heads_query_receipt(receipt: Any, expected_identity: dict[str, str]) -> str:
    if not isinstance(receipt, dict) or set(receipt) != _COMMAND_HEADS_RECEIPT_KEYS:
        return 'command_heads_receipt_shape_invalid'
    if not isinstance(expected_identity, dict):
        return 'command_heads_expected_identity_invalid'
    dispatch_id = str(expected_identity.get('dispatch_id') or '').strip()
    capability_build = str(expected_identity.get('capability_build') or '').strip()
    generation_id = str(expected_identity.get('capability_generation_id') or '').strip()
    manifest_sha = str(expected_identity.get('capability_manifest_sha256') or '').strip().lower()
    if not _DISPATCH_ID_RE.fullmatch(dispatch_id) or not capability_build or (not generation_id) or (not re.fullmatch('[0-9a-f]{64}', manifest_sha)):
        return 'command_heads_expected_identity_invalid'
    if receipt.get('schema') != COMMAND_HEADS_QUERY_SCHEMA:
        return 'command_heads_receipt_schema_invalid'
    if receipt.get('status') != 'complete':
        return 'command_heads_receipt_incomplete'
    prefix = receipt.get('module_prefix')
    projection_version = receipt.get('projection_version')
    heads = receipt.get('heads')
    count = receipt.get('count')
    if not command_heads_prefix_shape_valid(prefix) or not isinstance(projection_version, str) or (not projection_version.strip()) or any((ord(ch) < 32 for ch in projection_version)) or (not isinstance(heads, list)) or (type(count) is not int) or any((not isinstance(head, str) or not head or head != head.strip() or (not command_head_matches_prefix(head, prefix)) for head in heads)):
        return 'command_heads_receipt_inventory_invalid'
    if heads != sorted(set(heads)) or count != len(heads):
        if _redaction_folded_inventory(heads, count=count):
            return COMMAND_HEADS_RECEIPT_REDACTION_FOLDED
        return 'command_heads_receipt_inventory_invalid'
    if receipt.get('device_build') != capability_build or receipt.get('capability_generation_id') != generation_id or receipt.get('capability_manifest_sha256') != manifest_sha:
        return 'command_heads_receipt_identity_mismatch'
    material = {key: receipt.get(key) for key in ('schema', 'status', 'module_prefix', 'device_build', 'capability_generation_id', 'capability_manifest_sha256', 'projection_version', 'count', 'heads')}
    expected_hash = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    result_sha = receipt.get('result_sha256')
    if result_sha != expected_hash:
        return 'command_heads_receipt_hash_mismatch'
    receipt_id = receipt.get('receipt_id')
    receipt_prefix = f'{dispatch_id}:heads:'
    if not isinstance(receipt_id, str) or not receipt_id.startswith(receipt_prefix):
        return 'command_heads_receipt_id_invalid'
    suffix = receipt_id[len(receipt_prefix):].split(':')
    if len(suffix) != 2 or not suffix[0].isdigit() or int(suffix[0]) < 1 or (suffix[1] != expected_hash[:16]):
        return 'command_heads_receipt_id_invalid'
    return ''

def validate_command_heads_session_receipts(receipts: Any, expected_identity: dict[str, str]) -> tuple[dict[str, dict], str]:
    if not isinstance(receipts, list) or not receipts:
        return ({}, COMMAND_HEADS_SESSION_RECEIPTS_MISSING)
    by_id: dict[str, dict] = {}
    for sequence, raw_receipt in enumerate(receipts, start=1):
        receipt_error = validate_command_heads_query_receipt(raw_receipt, expected_identity)
        if receipt_error:
            return ({}, receipt_error)
        receipt = dict(raw_receipt)
        result_sha256 = str(receipt.get('result_sha256') or '')
        expected_receipt_id = f"{expected_identity.get('dispatch_id', '')}:heads:{sequence}:{result_sha256[:16]}"
        if receipt.get('receipt_id') != expected_receipt_id:
            return ({}, COMMAND_HEADS_RECEIPT_SEQUENCE_MISMATCH)
        by_id[expected_receipt_id] = receipt
    return (by_id, '')

def validate_not_compilable_heads_summary(summaries: Any, receipts_by_id: dict[str, dict]) -> str:
    summary_ids = [str(item.get('receipt_id') or '') for item in summaries or [] if isinstance(item, dict)]
    if not isinstance(summaries, list) or not summaries or len(summary_ids) != len(set(summary_ids)) or any((not isinstance(item, dict) or set(item) != {'receipt_id', 'module_prefix', 'result_sha256', 'head_count'} or str(item.get('receipt_id') or '') not in receipts_by_id or (item.get('module_prefix') != receipts_by_id[str(item.get('receipt_id') or '')].get('module_prefix')) or (item.get('result_sha256') != receipts_by_id[str(item.get('receipt_id') or '')].get('result_sha256')) or (item.get('head_count') != receipts_by_id[str(item.get('receipt_id') or '')].get('count')) for item in summaries)):
        return NOT_COMPILABLE_HEADS_SUMMARY_MISMATCH
    return ''

def canonical_source_case_slice(value: Any, *, autoid: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError('source case slice must be an object')
    aid = str(value.get('autoid') or '').strip()
    if aid != str(autoid or '').strip() or not re.fullmatch('\\d{18}', aid):
        raise ValueError('source case slice autoid does not match the worker session')
    raw_steps = value.get('step_intents')
    if not isinstance(raw_steps, list):
        raise ValueError('source case slice step_intents must be an array')
    steps = []
    for item in raw_steps:
        if not isinstance(item, dict):
            raise ValueError('source case slice contains a non-object step')
        steps.append({'desc': str(item.get('desc') or ''), 'expected': str(item.get('expected') or '')})
    return {'autoid': aid, 'title': str(value.get('title') or ''), 'step_intents': steps}

def canonical_source_case_slice_sha256(value: Any, *, autoid: str) -> str:
    canonical = canonical_source_case_slice(value, autoid=autoid)
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def validate_source_case_anchors(sources: Any, source_case_slice: Any, *, autoid: str, source_case_slice_sha256: str) -> str:
    try:
        canonical = canonical_source_case_slice(source_case_slice, autoid=autoid)
    except ValueError:
        return 'source_case_slice_invalid'
    expected_sha = str(source_case_slice_sha256 or '').strip().lower()
    if not re.fullmatch('[0-9a-f]{64}', expected_sha) or canonical_source_case_slice_sha256(canonical, autoid=autoid) != expected_sha:
        return 'source_case_slice_identity_mismatch'
    if not isinstance(sources, list) or not sources:
        return 'source_anchors_invalid'

    def _normalized(text: object) -> str:
        value = str(text or '')
        value = value.replace('\\r', ' ').replace('\\n', ' ').replace('\\t', ' ')
        value = value.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
        value = value.replace('\xa0', ' ')
        return ' '.join(value.split())
    corpus_by_kind = {'title': [str(canonical.get('title') or '')], 'step': [str(item.get('desc') or '') for item in canonical['step_intents']], 'expected': [str(item.get('expected') or '') for item in canonical['step_intents']]}
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {'kind', 'quote'}:
            return f'source_anchor_shape_invalid:{index}'
        kind = str(source.get('kind') or '').strip()
        quote = str(source.get('quote') or '').strip()
        if kind not in corpus_by_kind or not quote:
            return f'source_anchor_shape_invalid:{index}'
        normalized_quote = _normalized(quote)
        if not any((quote in corpus or normalized_quote in _normalized(corpus) for corpus in corpus_by_kind[kind])):
            return f'source_anchor_quote_not_bound:{index}'
    return ''

def _validated_source_binding(*, autoid: str, source_manifest_ref: str, source_manifest_sha256: str, source_case_slice_sha256_value: str, source_case_slice: Any) -> tuple[str, str, str, dict]:
    values = (source_manifest_ref, source_manifest_sha256, source_case_slice_sha256_value, source_case_slice)
    if not any((value not in ('', None, {}) for value in values)):
        return ('', '', '', {})
    if not all((value not in ('', None, {}) for value in values)):
        raise ValueError('worker source binding is incomplete')
    ref = str(source_manifest_ref).strip()
    manifest_sha = str(source_manifest_sha256).strip().lower()
    slice_sha = str(source_case_slice_sha256_value).strip().lower()
    if not ref or ref.startswith('/') or '..' in Path(ref).parts or (not re.fullmatch('[0-9a-f]{64}', manifest_sha)) or (not re.fullmatch('[0-9a-f]{64}', slice_sha)):
        raise ValueError('worker source binding identity is invalid')
    canonical = canonical_source_case_slice(source_case_slice, autoid=autoid)
    if canonical_source_case_slice_sha256(canonical, autoid=autoid) != slice_sha:
        raise ValueError('worker source case slice digest mismatch')
    from cex_core.engine.case_compiler._sealed_io import lexical_path_inside_root, read_regular_nofollow
    from cex_core.engine.ist_core.compile_engine import _shared as sh
    project_root = sh.project_root()
    outputs_root = sh.outputs_root()
    path = lexical_path_inside_root(project_root / ref, outputs_root, error_type=ValueError, traversal_message='worker source manifest traversal is forbidden', outside_message='worker source manifest escaped outputs root')
    raw = read_regular_nofollow(path, trusted_root=outputs_root, error_type=ValueError, invalid_message='worker source manifest path is invalid', directory_message='worker source manifest directory is unavailable', open_message='worker source manifest is unavailable', bounds_message='worker source manifest exceeds its size boundary', changed_message='worker source manifest changed while being read', max_bytes=32 * 1024 * 1024, min_bytes=1, require_current_uid=True)
    assert isinstance(raw, bytes)
    if hashlib.sha256(raw).hexdigest() != manifest_sha:
        raise ValueError('worker source manifest digest mismatch')
    try:
        manifest = json.loads(raw.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('worker source manifest is not valid JSON') from exc
    matches = [item for item in manifest.get('cases') or [] if isinstance(item, dict) and str(item.get('autoid') or '') == autoid] if isinstance(manifest, dict) else []
    if len(matches) != 1:
        raise ValueError('worker source manifest does not contain exactly one bound case')
    from_manifest = canonical_source_case_slice(matches[0], autoid=autoid)
    if from_manifest != canonical:
        raise ValueError('worker source case slice does not match the sealed manifest')
    return (ref, manifest_sha, slice_sha, canonical)

def valid_session_admission_rejection(record: object, *, require_identity: bool=True) -> bool:
    from cex_core.engine.ist_core.compile_engine.engine_quarantine import SESSION_ADMISSION_REJECTION_CODES
    if not isinstance(record, dict) or set(record) != _ADMISSION_REJECTION_FIELDS or any((not isinstance(value, str) for value in record.values())) or (record['code'] not in SESSION_ADMISSION_REJECTION_CODES) or (record['exception_type'] != 'SessionAdmissionError') or (not re.fullmatch('[0-9a-f]{64}', record['message_sha256'])):
        return False
    if require_identity and (not re.fullmatch('[0-9]{18}', record['autoid']) or not record['fork_id'].strip() or (not _DISPATCH_ID_RE.fullmatch(record['dispatch_id'])) or (not _DISPATCH_ID_RE.fullmatch(record['batch_run_id']))):
        return False
    body = {key: value for key, value in record.items() if key != 'record_id'}
    return persisted_surface_sha256(body) == record['record_id']

def _session_journal_path(session: 'WorkerDeviceSession') -> Path:
    from cex_core.engine.ist_core.compile_engine import _shared as sh
    identity = '|'.join((str(session.batch_run_id or ''), str(session.dispatch_id or ''), str(session.autoid or ''), str(session.fork_id or '')))
    stem = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]
    return sh.project_root() / 'runtime' / 'worker_oracle_journal' / f'{stem}.jsonl'

def persist_worker_session_event(session: 'WorkerDeviceSession', event: dict) -> bool:
    from cex_core.engine.ist_core.security_scrub import scrub_value
    record = scrub_value({'schema': 'worker_session_event', **dict(event), 'autoid': session.autoid, 'fork_id': session.fork_id, 'dispatch_id': session.dispatch_id, 'batch_run_id': session.batch_run_id, 'bed_lease_id': session.bed_lease_id, 'env_id': session.env_id, 'execution_bed': session.actual_bed or session.expected_bed, 'execution_build': session.expected_build, 'execution_module': session.expected_module, 'capability_bed': session.capability_bed, 'capability_full_version': session.capability_full_version, 'capability_version': session.capability_version, 'capability_build': session.capability_build, 'capability_generation_id': session.capability_generation_id, 'capability_manifest_sha256': session.capability_manifest_sha256, 'capability_projection_sha256': session.capability_projection_sha256, 'source_manifest_ref': session.source_manifest_ref, 'source_manifest_sha256': session.source_manifest_sha256, 'source_case_slice_sha256': session.source_case_slice_sha256, 'remote_artifact_sha256': session.current_remote_artifact_sha256})
    try:
        path = _session_journal_path(session)
        with _SESSION_JOURNAL_LOCK:
            from cex_core.engine.ist_core.compile_engine import _shared as sh
            from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow, open_or_create_regular_at_nofollow
            root = sh.project_root()
            if root.is_symlink():
                raise PermissionError('worker journal refuses a symbolic-link project root')
            nofollow = getattr(os, 'O_NOFOLLOW', 0)
            cloexec = getattr(os, 'O_CLOEXEC', 0)
            if not nofollow:
                raise PermissionError('worker journal requires O_NOFOLLOW')
            payload = (json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
            if len(payload) > _MAX_WORKER_JOURNAL_RECORD_BYTES:
                raise PermissionError('worker journal record exceeds its byte budget')
            dir_fd = open_directory_nofollow(path.parent, error_type=PermissionError, invalid_message='worker journal parent is invalid', unavailable_message='worker journal parent is unavailable', create_missing=True, create_mode=448)
            try:
                parent_info = os.fstat(dir_fd)
                if not stat.S_ISDIR(parent_info.st_mode) or (hasattr(os, 'getuid') and int(parent_info.st_uid) != os.getuid()):
                    raise PermissionError('worker journal parent identity is invalid')
                flags = os.O_WRONLY | os.O_APPEND | nofollow | cloexec
                fd = open_or_create_regular_at_nofollow(dir_fd, path.name, flags, mode=384, error_type=PermissionError, unavailable_message='worker journal cannot be opened safely')
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()) or stat.S_IMODE(info.st_mode) & 63 or (int(info.st_size) > _MAX_WORKER_JOURNAL_BYTES):
                        raise PermissionError('worker journal target identity is invalid')
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    locked_info = os.fstat(fd)
                    named_info = os.stat(path.name, dir_fd=dir_fd, follow_symlinks=False)
                    for current in (locked_info, named_info):
                        if not stat.S_ISREG(current.st_mode) or int(current.st_nlink) != 1 or (hasattr(os, 'getuid') and int(current.st_uid) != os.getuid()) or (int(current.st_size) > _MAX_WORKER_JOURNAL_BYTES):
                            raise PermissionError('worker journal identity changed while locking')
                    if (int(locked_info.st_dev), int(locked_info.st_ino)) != (int(named_info.st_dev), int(named_info.st_ino)):
                        raise PermissionError('worker journal pathname changed while locking')
                    if int(locked_info.st_size) + len(payload) > _MAX_WORKER_JOURNAL_BYTES:
                        raise PermissionError('worker journal exceeds its byte budget')
                    offset = 0
                    while offset < len(payload):
                        written = os.write(fd, payload[offset:])
                        if written <= 0:
                            raise OSError('short write to worker journal')
                        offset += written
                    os.fsync(fd)
                finally:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
                    os.close(fd)
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        return True
    except Exception:
        return False

def worker_device_loop_enabled() -> bool:
    return os.environ.get('IST_WORKER_DEVICE_LOOP', '1').strip().lower() in {'1', 'true', 'yes', 'on'}

@contextmanager
def worker_device_access_scope(allowed: bool) -> Iterator[None]:
    token = _DEVICE_ACCESS.set(allowed is True)
    try:
        yield
    finally:
        _DEVICE_ACCESS.reset(token)

def worker_device_access_enabled() -> bool:
    return _DEVICE_ACCESS.get() is True

def worker_device_max_rounds() -> int:
    raw = os.environ.get('IST_WORKER_DEVICE_MAX_ROUNDS', str(_DEFAULT_MAX_ROUNDS))
    try:
        value = float(str(raw).strip())
        if not math.isfinite(value):
            raise ValueError
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = _DEFAULT_MAX_ROUNDS
    return max(1, min(parsed, _MAX_ROUNDS_CEILING))

def worker_device_infra_retries() -> int:
    raw = os.environ.get('IST_WORKER_DEVICE_INFRA_RETRIES', '3')
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        parsed = 3
    return max(0, min(parsed, 10))

def worker_probe_max_calls() -> int:
    raw = os.environ.get('IST_WORKER_PROBE_MAX_CALLS', str(_DEFAULT_MAX_PROBE_CALLS))
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        parsed = _DEFAULT_MAX_PROBE_CALLS
    return max(0, min(parsed, _MAX_PROBE_CALLS_CEILING))

@dataclass
class WorkerDeviceSession:
    skill: str
    agent: str
    autoid: str
    fork_id: str
    device_access: bool = True
    dispatch_id: str = ''
    batch_run_id: str = ''
    bed_lease_id: str = ''
    expected_bed: str = ''
    expected_build: str = ''
    expected_module: str = ''
    capability_bed: str = ''
    capability_full_version: str = ''
    capability_version: str = ''
    capability_build: str = ''
    capability_generation_id: str = ''
    capability_manifest_sha256: str = ''
    capability_projection_sha256: str = ''
    authored_round: int = 1
    source_manifest_ref: str = ''
    source_manifest_sha256: str = ''
    source_case_slice_sha256: str = ''
    source_case_slice: dict = field(default_factory=dict)
    max_rounds: int = field(default_factory=worker_device_max_rounds)
    max_infra_retries: int = field(default_factory=worker_device_infra_retries)
    max_probe_calls: int = field(default_factory=worker_probe_max_calls)
    attempts: int = 0
    probe_calls: int = 0
    probe_exhausted: bool = False
    probe_evidence: list[dict] = field(default_factory=list)
    command_heads_query_receipts: list[dict] = field(default_factory=list)
    not_compilable_reports: list[dict] = field(default_factory=list)
    worker_claims: list[dict] = field(default_factory=list)
    engine_gaps: list[dict] = field(default_factory=list)
    authoring_accounts: list[dict] = field(default_factory=list)
    authoring_channel_rejection: dict = field(default_factory=dict)
    admission_rejection: dict = field(default_factory=dict)
    authoring_budget: dict = field(default_factory=dict)
    account_supplement: dict = field(default_factory=dict)
    unsupported_feature_reports: list[dict] = field(default_factory=list)
    probe_plan_keys: set[str] = field(default_factory=set)
    semantic_attempts: int = 0
    infrastructure_attempts: int = 0
    last_artifact_sha256: str = ''
    current_artifact_sha256: str = ''
    current_remote_artifact_sha256: str = ''
    lint_credential_id: str = ''
    current_attempt_id: str = ''
    current_prediction: dict = field(default_factory=dict)
    prediction_chain: list[dict] = field(default_factory=list)
    last_verdict: str = ''
    last_fail_signatures: frozenset = field(default_factory=frozenset)
    seen_fail_signatures: frozenset = field(default_factory=frozenset)
    accumulated_fail_signatures: frozenset = field(default_factory=frozenset)
    device_no_progress_history: list[dict] = field(default_factory=list)
    compile_no_progress_history: list[dict] = field(default_factory=list)
    compile_learning_history: list[dict] = field(default_factory=list)
    last_no_progress_decision: dict = field(default_factory=dict)
    no_progress_decisions: list[dict] = field(default_factory=list)
    current_compile_revision: str = ''
    current_compile_attempt_id: str = ''
    current_compile_recorded: bool = False
    compile_attempts: list[dict] = field(default_factory=list)
    mechanical_case_submission_attempts: int = 0
    mechanical_case_rejections: list[dict] = field(default_factory=list)
    mechanical_case_accepted: dict = field(default_factory=dict, repr=False)
    gate_advisories: list[dict] = field(default_factory=list)
    mechanical_case_repair_disclosures: list[dict] = field(default_factory=list)
    last_mechanical_case_submission_body: dict = field(default_factory=dict, repr=False)
    compile_exhausted: bool = False
    stop_reason: str = ''
    in_flight: bool = False
    revoked: bool = False
    closed: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _lease_acquire_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _lease_cm: Any = field(default=None, repr=False)
    _environment_lease: Any = field(default=None, repr=False)
    _shared_binding: Any = field(default=None, repr=False)
    env_id: str = ''
    actual_bed: str = ''
    lease_acquired_at: float = 0.0
    lease_acquired_persisted: bool = False
    lease_released_persisted: bool = False
    shared_binding_persisted: bool = False
    lease_error: str = ''

    def record_admission_rejection(self, error: BaseException) -> dict:
        from cex_core.engine.ist_core.compile_engine.engine_quarantine import SessionAdmissionError, SESSION_ADMISSION_REJECTION_CODES
        from cex_core.engine.ist_core.security_scrub import scrub_value
        if current_worker_device_session() is not self:
            return {}
        if not isinstance(error, SessionAdmissionError) or error.code not in SESSION_ADMISSION_REJECTION_CODES:
            raise ValueError('admission stop requires a registered typed rejection')
        with self._lock:
            identity = {key: str(getattr(self, key) or '') for key in SESSION_ADMISSION_IDENTITY_FIELDS}
            previous = self.admission_rejection.get('record')
            if valid_session_admission_rejection(previous, require_identity=False) and all((previous[key] == value for key, value in identity.items())):
                return copy.deepcopy(self.admission_rejection)
            raw_detail = str(error)
            record = scrub_value({**identity, 'code': error.code, 'detail': raw_detail, 'message_sha256': hashlib.sha256(raw_detail.encode('utf-8')).hexdigest(), 'exception_type': 'SessionAdmissionError', 'source_manifest_ref': str(self.source_manifest_ref or ''), 'source_manifest_sha256': str(self.source_manifest_sha256 or ''), 'source_case_slice_sha256': str(self.source_case_slice_sha256 or '')})
            record['record_id'] = persisted_surface_sha256(record)
            self.admission_rejection = {'record': record, 'persisted': False}
        try:
            persisted = bool(persist_worker_session_event(self, {'ev': SESSION_ADMISSION_REJECTION_EVENT, 'rejection': record}))
        except Exception:
            persisted = False
        with self._lock:
            if (self.admission_rejection.get('record') or {}).get('record_id') == record['record_id']:
                self.admission_rejection['persisted'] = persisted
            return copy.deepcopy(self.admission_rejection)

    def _persistent_admission_reason(self) -> str:
        from cex_core.engine.ist_core.compile_engine import engine_quarantine as Q
        with self._lock:
            if self.closed:
                return 'worker_session_closed'
        try:
            Q.require_session_admission(self)
        except Q.SessionAdmissionError as exc:
            with self._lock:
                self.lease_error = str(exc)
                if exc.code == 'dispatch_revoked':
                    self.revoked = True
            return exc.code
        except (ValueError, OSError, RuntimeError) as exc:
            with self._lock:
                self.lease_error = str(exc)
            return 'dispatch_admission_unverified'
        return ''

    def acquire_device_lease(self, *, timeout: float, poll_s: float=0.25) -> tuple[Any | None, str]:
        if self.device_access:
            reason = self._persistent_admission_reason()
            if reason:
                return (None, reason)
        with self._lease_acquire_lock:
            with self._lock:
                if not self.device_access:
                    self.lease_error = 'pre_ask_static_phase'
                    return (None, self.lease_error)
                if self.revoked or (self.dispatch_id and self.dispatch_id in _REVOKED_DISPATCHES):
                    self.revoked = True
                    return (None, 'dispatch_revoked')
                current = self._environment_lease
                if current is not None and (not current.released):
                    return (current, '')
                if not self.expected_bed:
                    self.lease_error = 'execution_bed_missing'
                    return (None, self.lease_error)
            from cex_core.engine.case_compiler import env_pool
            cm = env_pool.acquire_lease(required_host=self.expected_bed, timeout=max(0.0, float(timeout)), poll_s=max(0.01, float(poll_s)), strict_ready=True)
            try:
                lease = cm.__enter__()
            except Exception as exc:
                reason = f'lease_acquire_failed:{type(exc).__name__}'
                with self._lock:
                    self.lease_error = reason
                return (None, reason)
            actual_bed = str(getattr(lease, 'bed_host', '') or '')
            if actual_bed != self.expected_bed:
                try:
                    cm.__exit__(None, None, None)
                except Exception:
                    pass
                reason = 'lease_bed_identity_mismatch'
                with self._lock:
                    self.lease_error = reason
                    self.actual_bed = actual_bed
                return (None, reason)
            reason = self._persistent_admission_reason()
            if reason:
                try:
                    cm.__exit__(None, None, None)
                except Exception as exc:
                    with self._lock:
                        self._lease_cm, self._environment_lease = (cm, lease)
                        self.lease_error = f'{reason}; lease_release_failed:{type(exc).__name__}'
                    return (None, self.lease_error)
                return (None, reason)
            with self._lock:
                self._lease_cm = cm
                self._environment_lease = lease
                self.bed_lease_id = str(lease.lease_id or '')
                self.env_id = str(lease.env_id or '')
                self.actual_bed = actual_bed
                self.lease_acquired_at = float(lease.acquired_at or 0.0)
                self.lease_acquired_persisted = False
                self.lease_released_persisted = False
            persisted = persist_worker_session_event(self, {'ev': 'worker_device_lease_acquired', 'lease_acquired_at': self.lease_acquired_at, 'ts': self.lease_acquired_at})
            if persisted:
                with self._lock:
                    self.lease_acquired_persisted = True
                return (lease, '')
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass
            with self._lock:
                self._lease_cm = None
                self._environment_lease = None
                self.lease_error = 'lease_identity_unpersisted'
                self.stop_reason = 'lease_identity_unpersisted'
            return (None, 'lease_identity_unpersisted')

    def acquire_shared_environment(self) -> tuple[Any | None, str]:
        if self.device_access:
            reason = self._persistent_admission_reason()
            if reason:
                return (None, reason)
        with self._lock:
            if not self.device_access:
                self.lease_error = 'pre_ask_static_phase'
                return (None, self.lease_error)
            if self.revoked or (self.dispatch_id and self.dispatch_id in _REVOKED_DISPATCHES):
                self.revoked = True
                return (None, 'dispatch_revoked')
            if not self.expected_bed:
                self.lease_error = 'execution_bed_missing'
                return (None, self.lease_error)
            bound = self._shared_binding
        if bound is not None:
            return (bound, '')
        from cex_core.engine.case_compiler import env_pool
        try:
            binding = env_pool.resolve_shared_environment(required_host=self.expected_bed)
        except Exception as exc:
            reason = f'shared_bind_failed:{type(exc).__name__}'
            with self._lock:
                self.lease_error = reason
            return (None, reason)
        actual_bed = str(getattr(binding, 'bed_host', '') or '')
        if actual_bed != self.expected_bed:
            reason = 'shared_bind_bed_identity_mismatch'
            with self._lock:
                self.lease_error = reason
                self.actual_bed = actual_bed
            return (None, reason)
        reason = self._persistent_admission_reason()
        if reason:
            return (None, reason)
        with self._lock:
            self.env_id = str(binding.env_id or '')
            self.actual_bed = actual_bed
        if not persist_worker_session_event(self, {'ev': 'worker_device_shared_bound', 'bound_at': float(getattr(binding, 'bound_at', 0.0) or 0.0), 'access': 'read_only'}):
            with self._lock:
                self.lease_error = 'shared_bind_unpersisted'
                self.stop_reason = 'shared_bind_unpersisted'
            return (None, 'shared_bind_unpersisted')
        with self._lock:
            self._shared_binding = binding
            self.shared_binding_persisted = True
        return (binding, '')

    def release_device_lease(self) -> bool:
        with self._lease_acquire_lock:
            with self._lock:
                cm = self._lease_cm
                lease = self._environment_lease
                if cm is None or lease is None:
                    return True
                self._lease_cm = None
                self._environment_lease = None
            release_ok = True
            try:
                cm.__exit__(None, None, None)
            except Exception:
                release_ok = False
            persisted = persist_worker_session_event(self, {'ev': 'worker_device_lease_released', 'released': bool(getattr(lease, 'released', False)), 'release_ok': release_ok})
            with self._lock:
                self.lease_released_persisted = bool(release_ok and getattr(lease, 'released', False) and persisted)
                if not self.lease_released_persisted:
                    self.lease_error = 'lease_release_unpersisted'
            return self.lease_released_persisted

    @property
    def leased_environment(self) -> Any | None:
        with self._lock:
            lease = self._environment_lease
            if lease is None or lease.released:
                return None
            return lease.env

    def control_snapshot(self) -> dict:
        fields = ('attempts', 'semantic_attempts', 'infrastructure_attempts', 'last_artifact_sha256', 'current_artifact_sha256', 'current_remote_artifact_sha256', 'lint_credential_id', 'current_attempt_id', 'current_prediction', 'prediction_chain', 'last_verdict', 'last_fail_signatures', 'seen_fail_signatures', 'accumulated_fail_signatures', 'device_no_progress_history', 'compile_no_progress_history', 'compile_learning_history', 'last_no_progress_decision', 'no_progress_decisions', 'current_compile_revision', 'current_compile_attempt_id', 'current_compile_recorded', 'compile_attempts', 'compile_exhausted', 'stop_reason', 'in_flight')
        with self._lock:
            return {name: copy.deepcopy(getattr(self, name)) for name in fields}

    def restore_control_snapshot(self, snapshot: dict) -> None:
        with self._lock:
            for name, value in snapshot.items():
                setattr(self, name, copy.deepcopy(value))

    def reserve_probe(self, *, command: str='', hypothesis: str='', require_plan: bool=False) -> tuple[bool, int, str]:
        if self.device_access:
            reason = self._persistent_admission_reason()
            if reason:
                return (False, self.probe_calls, reason)
        with self._lock:
            if not self.device_access:
                return (False, self.probe_calls, 'pre_ask_static_phase')
            if self.revoked or (self.dispatch_id and self.dispatch_id in _REVOKED_DISPATCHES):
                self.revoked = True
                return (False, self.probe_calls, 'dispatch_revoked')
            if self.closed:
                return (False, self.probe_calls, 'worker_session_closed')
            if self.stop_reason:
                return (False, self.probe_calls, self.stop_reason)
            plan = ' '.join(str(hypothesis or '').split())
            if require_plan and (not plan):
                return (False, self.probe_calls, 'probe_hypothesis_required')
            plan_key = hashlib.sha256((' '.join(str(command or '').lower().split()) + '\n' + plan.lower()).encode('utf-8')).hexdigest()
            if require_plan and plan_key in self.probe_plan_keys:
                return (False, self.probe_calls, 'probe_plan_repeated')
            if self.probe_calls >= self.max_probe_calls:
                self.probe_exhausted = True
                return (False, self.probe_calls, 'worker_probe_budget_exhausted')
            self.probe_calls += 1
            if require_plan:
                self.probe_plan_keys.add(plan_key)
            return (True, self.probe_calls, '')

    def _mutation_receipt_summary(self) -> dict:
        try:
            from cex_core.engine.ist_core.compile_engine import _shared as sh
            payload = (sh.outputs_root() / self.autoid / 'case.mutation.json').read_bytes()
            receipt = json.loads(payload.decode('utf-8'))
        except Exception:
            return {}
        if not isinstance(receipt, dict):
            return {}
        rows = [row for row in receipt.get('requirements') or [] if isinstance(row, dict)]
        if not rows:
            return {}
        return {'assertion_count': len(rows), 'exempt_ordinals': sorted((int(row.get('assertion_ordinal') or 0) for row in rows if row.get('status') == 'exempt')), 'control_flip_expected': sum((1 for row in rows if row.get('status') == 'pending')), 'mutation_receipt_sha256': hashlib.sha256(payload).hexdigest()}

    def record_probe_evidence(self, event: dict) -> None:
        with self._lock:
            self.probe_evidence.append(copy.deepcopy(event))

    def record_command_heads_query(self, query_result: dict) -> tuple[dict, str]:
        if not isinstance(query_result, dict):
            return ({}, 'command heads query result must be an object')
        if query_result.get('schema') != 'ist.command-heads-query' or query_result.get('status') != 'complete':
            return ({}, 'command heads query result is not an accepted v1 result')
        prefix = str(query_result.get('module_prefix') or '').strip().casefold()
        device_build = str(query_result.get('device_build') or '').strip()
        projection_version = str(query_result.get('projection_version') or '').strip()
        heads = query_result.get('heads')
        if not command_heads_prefix_shape_valid(prefix) or not isinstance(heads, list) or any((not isinstance(head, str) or not head.strip() for head in heads)):
            return ({}, 'command heads query result has an invalid module or heads list')
        normalized_heads = [str(head).strip() for head in heads]
        if normalized_heads != sorted(set(normalized_heads)) or query_result.get('count') != len(normalized_heads) or any((not command_head_matches_prefix(head, prefix) for head in normalized_heads)):
            return ({}, 'command heads query result is not a canonical module inventory')
        identity_values = (self.dispatch_id, self.capability_build, self.capability_generation_id, self.capability_manifest_sha256)
        if not all((str(value or '').strip() for value in identity_values)):
            return ({}, 'command heads query requires complete sealed capability identity')
        if not re.fullmatch('[0-9a-f]{64}', str(self.capability_manifest_sha256 or '').strip().lower()):
            return ({}, 'command heads query capability manifest sha256 is invalid')
        if device_build != str(self.capability_build or '').strip():
            return ({}, 'command heads query device build does not match the worker session')
        material = {'schema': 'ist.command-heads-query', 'status': 'complete', 'module_prefix': prefix, 'device_build': device_build, 'capability_generation_id': self.capability_generation_id, 'capability_manifest_sha256': self.capability_manifest_sha256.lower(), 'projection_version': projection_version, 'count': len(normalized_heads), 'heads': normalized_heads}
        result_sha256 = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        with self._lock:
            sequence = len(self.command_heads_query_receipts) + 1
            receipt = {**material, 'receipt_id': f'{self.dispatch_id}:heads:{sequence}:{result_sha256[:16]}', 'result_sha256': result_sha256}
            validation_error = validate_command_heads_query_receipt(receipt, {'dispatch_id': self.dispatch_id, 'capability_build': self.capability_build, 'capability_generation_id': self.capability_generation_id, 'capability_manifest_sha256': self.capability_manifest_sha256})
            if validation_error:
                return ({}, validation_error)
            if not persist_worker_session_event(self, {'ev': 'command_heads_query_receipt', 'receipt': receipt}):
                return ({}, 'command heads query receipt could not be persisted')
            self.command_heads_query_receipts.append(copy.deepcopy(receipt))
        return (receipt, '')

    def record_worker_claim(self, claim: dict, *, reason_code: str, rejection_code: str) -> dict:
        if not isinstance(claim, dict):
            return {}
        reason_code = str(reason_code or '').strip()
        rejection_code = str(rejection_code or '').strip()
        if reason_code not in NOT_COMPILABLE_REASON_CODES or not rejection_code:
            return {}
        record = {'schema': WORKER_CLAIM_SCHEMA, 'autoid': self.autoid, 'reason_code': reason_code, 'rejection_code': rejection_code, 'test_point': str(claim.get('test_point') or '').strip(), 'sources': [{'kind': str(source.get('kind') or '').strip(), 'quote': str(source.get('quote') or '').strip()} for source in claim.get('sources') or [] if isinstance(source, dict)], 'obstacle': str(claim.get('obstacle') or '').strip(), 'no_equivalent_reason': str(claim.get('no_equivalent_reason') or '').strip()}
        if not persist_worker_session_event(self, {'ev': 'worker_claim', 'claim': record}):
            return {}
        with self._lock:
            record['ordinal'] = len(self.worker_claims) + 1
            self.worker_claims.append(copy.deepcopy(record))
        return record

    def record_not_compilable(self, claim: dict, command_heads_receipt_ids: list[str], reason_code: str=NOT_COMPILABLE_REASON_NO_CLI) -> tuple[dict, str]:
        if not isinstance(claim, dict):
            return ({}, 'not-compilable claim must be an object')
        reason_code = str(reason_code or '').strip()
        if reason_code not in NOT_COMPILABLE_REASON_CODES:
            return ({}, 'not-compilable reason_code outside the closed set')
        refs = [str(value or '').strip() for value in command_heads_receipt_ids]
        refs = list(dict.fromkeys((value for value in refs if value)))
        with self._lock:
            session_receipts = copy.deepcopy(self.command_heads_query_receipts)
        expected_query_identity = {'dispatch_id': self.dispatch_id, 'capability_build': self.capability_build, 'capability_generation_id': self.capability_generation_id, 'capability_manifest_sha256': self.capability_manifest_sha256}
        by_id, receipt_error = validate_command_heads_session_receipts(session_receipts, expected_query_identity)
        if receipt_error:
            return ({}, receipt_error)
        if not refs:
            return ({}, NOT_COMPILABLE_HEADS_REFS_MISSING)
        if any((receipt_id not in by_id for receipt_id in refs)):
            return ({}, NOT_COMPILABLE_HEADS_REF_UNKNOWN)
        sources = claim.get('sources')
        source_error = validate_source_case_anchors(sources, self.source_case_slice, autoid=self.autoid, source_case_slice_sha256=self.source_case_slice_sha256)
        if source_error:
            return ({}, f'not-compilable report requires source anchors bound to the sealed case slice ({source_error})')
        for field_name in ('test_point', 'obstacle', 'no_equivalent_reason'):
            if not str(claim.get(field_name) or '').strip():
                return ({}, f'not-compilable report requires {field_name}')
        identity_values = (self.autoid, self.dispatch_id, self.capability_build, self.capability_generation_id, self.capability_manifest_sha256, self.source_manifest_ref, self.source_manifest_sha256, self.source_case_slice_sha256)
        if not all((str(value or '').strip() for value in identity_values)):
            return ({}, 'not-compilable report requires complete sealed capability identity')
        query_receipts = [{'receipt_id': receipt_id, 'module_prefix': str(by_id[receipt_id]['module_prefix']), 'result_sha256': str(by_id[receipt_id]['result_sha256']), 'head_count': int(by_id[receipt_id]['count'])} for receipt_id in refs]
        summary_error = validate_not_compilable_heads_summary(query_receipts, by_id)
        if summary_error:
            return ({}, summary_error)
        material = canonical_persisted_value({'schema': 'ist.not-compilable', 'autoid': self.autoid, 'reason_code': reason_code, 'test_point': str(claim['test_point']).strip(), 'sources': [{'kind': str(source['kind']).strip(), 'quote': str(source['quote']).strip()} for source in sources], 'obstacle': str(claim['obstacle']).strip(), 'no_equivalent_reason': str(claim['no_equivalent_reason']).strip(), 'command_heads_receipts': query_receipts, 'capability_build': self.capability_build, 'capability_generation_id': self.capability_generation_id, 'capability_manifest_sha256': self.capability_manifest_sha256.lower(), 'source_manifest_ref': self.source_manifest_ref, 'source_manifest_sha256': self.source_manifest_sha256, 'source_case_slice_sha256': self.source_case_slice_sha256})
        report = {**material, 'report_hash': persisted_surface_sha256(material)}
        if not persist_worker_session_event(self, {'ev': 'not_compilable', 'report': report}):
            return ({}, 'not-compilable report could not be persisted')
        with self._lock:
            self.not_compilable_reports.append(copy.deepcopy(report))
        return (report, '')

    def record_unsupported_feature(self, probe_evidence_refs: list[str], *, claim: dict | None=None) -> tuple[dict, str]:
        refs = [str(value or '').strip() for value in probe_evidence_refs]
        refs = [value for value in refs if value]
        with self._lock:
            selected = [copy.deepcopy(event) for event in self.probe_evidence if str(event.get('probe_id') or '') in refs]
        if len(set(refs)) < 2 or len(selected) != len(set(refs)):
            return ({}, 'unsupported_feature requires two existing probe evidence refs')
        if len({str(item.get('command') or '').strip() for item in selected}) < 2:
            return ({}, 'unsupported_feature co-probes must use two distinct commands')
        if len({str(item.get('hypothesis') or '').strip() for item in selected}) < 2:
            return ({}, 'unsupported_feature co-probes must test two distinct hypotheses')
        if any((item.get('outcome') not in {'observed', 'cli_rejected'} or item.get('expectation_authority') is not False for item in selected)):
            return ({}, 'unsupported_feature co-probes contain unusable evidence')
        material = canonical_persisted_value({'schema': 'ist.compile.unsupported-feature', 'autoid': self.autoid, 'probe_evidence_refs': sorted(set(refs)), 'claim': copy.deepcopy(claim) if isinstance(claim, dict) else {}, 'co_probes': [{'probe_id': str(item.get('probe_id') or ''), 'command_sha256': hashlib.sha256(str(item.get('command') or '').encode('utf-8')).hexdigest(), 'hypothesis_sha256': hashlib.sha256(str(item.get('hypothesis') or '').encode('utf-8')).hexdigest(), 'outcome': str(item.get('outcome') or '')} for item in selected]})
        report = {**material, 'report_hash': persisted_surface_sha256(material)}
        if not persist_worker_session_event(self, {'ev': 'unsupported_feature', **report}):
            return ({}, 'unsupported_feature evidence could not be persisted')
        with self._lock:
            self.unsupported_feature_reports.append(copy.deepcopy(report))
        return (report, '')

    def fail_probe_persistence(self) -> None:
        with self._lock:
            self.stop_reason = 'probe_evidence_unpersisted'

    def reserve_run(self, artifact_sha256: str) -> tuple[bool, int, str]:
        if self.device_access:
            reason = self._persistent_admission_reason()
            if reason:
                return (False, self.attempts, reason)
        with self._lock:
            if not self.device_access:
                return (False, self.attempts, 'pre_ask_static_phase')
            if self.revoked or (self.dispatch_id and self.dispatch_id in _REVOKED_DISPATCHES):
                self.revoked = True
                return (False, self.attempts, 'dispatch_revoked')
            if self.in_flight:
                return (False, self.attempts, 'run_already_in_flight')
            if self.stop_reason:
                return (False, self.attempts, self.stop_reason)
            if self.semantic_attempts >= self.max_rounds:
                self.stop_reason = 'max_semantic_rounds_reached'
                return (False, self.attempts, self.stop_reason)
            if self.infrastructure_attempts > self.max_infra_retries:
                self.stop_reason = 'infrastructure_retry_limit'
                return (False, self.attempts, self.stop_reason)
            if self.last_verdict == 'fail' and self.last_artifact_sha256 and (artifact_sha256 == self.last_artifact_sha256):
                return (False, self.attempts, 'artifact_revision_required_after_fail')
            self.attempts += 1
            self.current_artifact_sha256 = artifact_sha256
            self.current_remote_artifact_sha256 = ''
            self.current_attempt_id = f'{self.dispatch_id or self.fork_id}:{self.attempts}:{artifact_sha256[:16]}'
            parent_hash = str(self.prediction_chain[-1].get('prediction_hash') or '') if self.prediction_chain else ''
            seen_probe_ids = {str(ref.get('probe_id') or '') for entry in self.prediction_chain for ref in entry.get('hypothesis_refs') or []}
            hypothesis_refs = [{'probe_id': str(p.get('probe_id') or ''), 'hypothesis_sha256': hashlib.sha256(str(p.get('hypothesis') or '').encode('utf-8')).hexdigest()} for p in self.probe_evidence if str(p.get('probe_id') or '') and str(p.get('probe_id') or '') not in seen_probe_ids]
            material = {'schema': 'ist.compile.prediction', 'prediction_before_run': {'claim': 'all_product_assertions_pass', **self._mutation_receipt_summary()}, 'artifact_sha256': artifact_sha256, 'attempt_id': self.current_attempt_id, 'revision': len(self.prediction_chain) + 1, 'parent_prediction_hash': parent_hash, 'hypothesis_refs': hypothesis_refs}
            self.current_prediction = {**material, 'prediction_hash': hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}
            self.in_flight = True
            return (True, self.attempts, '')

    def commit_prediction(self) -> dict:
        with self._lock:
            prediction = copy.deepcopy(self.current_prediction)
            if not prediction:
                return {}
            if not self.prediction_chain or self.prediction_chain[-1].get('prediction_hash') != prediction.get('prediction_hash'):
                self.prediction_chain.append(prediction)
            return prediction

    def complete_run(self, verdict: str, fail_signatures=()) -> str:
        normalized = frozenset(fail_signatures or ())
        with self._lock:
            self.in_flight = False
            revision = self.current_artifact_sha256
            self.current_artifact_sha256 = ''
            self.current_remote_artifact_sha256 = ''
            if verdict not in ('pass', 'fail'):
                self.infrastructure_attempts += 1
                if self.infrastructure_attempts > self.max_infra_retries:
                    self.stop_reason = 'infrastructure_retry_limit'
                return self.stop_reason
            self.semantic_attempts += 1
            self.last_artifact_sha256 = revision
            if verdict == 'fail':
                from cex_core.engine.ist_core.compile_engine.facts import no_progress_step
                decision = no_progress_step(self.device_no_progress_history, domain='device', value=normalized, revision_sha256=revision)
                self.device_no_progress_history = decision.pop('history')
                self.last_no_progress_decision = dict(decision)
                self.no_progress_decisions.append(dict(decision))
                if decision['stop']:
                    self.stop_reason = 'device_exhausted'
                self.seen_fail_signatures = normalized
            elif verdict == 'pass':
                self.seen_fail_signatures = frozenset()
                self.accumulated_fail_signatures = frozenset()
                self.device_no_progress_history = []
                self.last_no_progress_decision = {}
            self.last_verdict = verdict
            self.last_fail_signatures = normalized
            if verdict == 'fail' and self.semantic_attempts >= self.max_rounds and (not self.stop_reason):
                self.stop_reason = 'max_semantic_rounds_reached'
            return self.stop_reason

    def begin_compile_attempt(self, revision_sha256: str) -> str:
        with self._lock:
            self.current_compile_revision = str(revision_sha256 or '')
            self.current_compile_attempt_id = f'{self.dispatch_id or self.fork_id}:compile:{len(self.compile_attempts) + 1}:{self.current_compile_revision[:16]}'
            self.current_compile_recorded = False
            return self.current_compile_attempt_id

    def begin_mechanical_case_submission(self) -> int:
        with self._lock:
            self.mechanical_case_submission_attempts += 1
            return self.mechanical_case_submission_attempts

    def remember_mechanical_case_submission_body(self, body: dict) -> bool:
        try:
            snapshot = copy.deepcopy(body)
        except (MemoryError, RecursionError):
            return False
        with self._lock:
            self.last_mechanical_case_submission_body = snapshot
        return True

    def prepare_mechanical_case_envelope_sections(self, body: dict, *, block_edit_authorization_codes: frozenset[str]=frozenset()) -> tuple[dict | None, str, dict | None]:
        missing_expectation = body.get('expectation_binding') is None
        missing_escape = body.get('escape_hatches') is None
        if not missing_expectation and (not missing_escape):
            return (body, '', None)
        try:
            current = copy.deepcopy(body)
        except (MemoryError, RecursionError):
            return (None, 'submission_body_not_copyable', None)
        with self._lock:
            try:
                previous = copy.deepcopy(self.last_mechanical_case_submission_body)
            except (MemoryError, RecursionError):
                return (None, 'prior_submission_not_copyable', None)
            latest = self.mechanical_case_rejections[-1] if self.mechanical_case_rejections else {}
            latest_codes = {str(item.get('code') or '') for item in latest.get('violations') or [] if isinstance(item, dict) and str(item.get('code') or '')}
        if not previous:
            if missing_expectation:
                return (None, 'no_prior_complete_submission', None)
            current['escape_hatches'] = []
            return (current, '', None)
        if str(previous.get('schema') or '') != str(current.get('schema') or '') or str(previous.get('autoid') or '') != str(current.get('autoid') or ''):
            return (None, 'submission_identity_changed', None)
        try:
            previous_blocks = json.dumps(previous.get('blocks'), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
            current_blocks = json.dumps(current.get('blocks'), ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            return (None, 'blocks_not_canonical_json', None)
        blocks_changed = previous_blocks != current_blocks
        authorized_codes = sorted(latest_codes.intersection(block_edit_authorization_codes))
        if blocks_changed and (not authorized_codes):
            return (None, 'blocks_change_not_authorized', None)
        disclosure: dict | None = None
        if blocks_changed:
            disclosure = {'code': 'submission_repair_blocks_changed_for_cited_violation', 'authorized_by': authorized_codes, 'restored_sections': []}
        current_block_rows = current.get('blocks')
        previous_block_rows = previous.get('blocks')
        if not isinstance(current_block_rows, list) or not isinstance(previous_block_rows, list):
            return (None, 'blocks_not_arrays', None)

        def _binding_still_resolves(entries: object) -> bool:
            if not isinstance(entries, list) or not entries:
                return False
            for entry in entries:
                if not isinstance(entry, dict):
                    return False
                block_index = entry.get('block_index')
                if not isinstance(block_index, int) or isinstance(block_index, bool) or (not 0 <= block_index < len(current_block_rows)) or (not isinstance(current_block_rows[block_index], dict)):
                    return False
                carried = current_block_rows[block_index]
                assert_index = entry.get('assert_index')
                if assert_index is not None:
                    assertions = carried.get('asserts')
                    if not isinstance(assert_index, int) or isinstance(assert_index, bool) or (not isinstance(assertions, list)) or (not 0 <= assert_index < len(assertions)) or (not isinstance(assertions[assert_index], dict)):
                        return False
                    carried = assertions[assert_index]
                if str(carried.get('expectation_id') or '') != str(entry.get('expectation_id') or '') or str(carried.get('semantic_key') or '') != str(entry.get('semantic_key') or ''):
                    return False
            return True
        if missing_expectation:
            previous_binding = previous.get('expectation_binding')
            if not _binding_still_resolves(previous_binding):
                return (None, 'changed_blocks_require_expectation_binding', disclosure)
            current['expectation_binding'] = copy.deepcopy(previous_binding)
            if disclosure is not None:
                disclosure['restored_sections'].append('expectation_binding')
        if missing_escape:
            previous_escape = previous.get('escape_hatches')
            if not isinstance(previous_escape, list):
                return (None, 'prior_escape_hatches_unavailable', disclosure)
            if blocks_changed:
                step_indices = {index for index, block in enumerate(current_block_rows) if isinstance(block, dict) and str(block.get('kind') or '').strip().upper() == 'STEP'}
                escaped_indices = {entry.get('block_index') for entry in previous_escape if isinstance(entry, dict)}
                if step_indices != escaped_indices:
                    return (None, 'changed_blocks_require_escape_hatches', disclosure)
                for block_index in step_indices:
                    if block_index >= len(previous_block_rows) or current_block_rows[block_index] != previous_block_rows[block_index]:
                        return (None, 'changed_blocks_require_escape_hatches', disclosure)
            current['escape_hatches'] = copy.deepcopy(previous_escape)
            if disclosure is not None:
                disclosure['restored_sections'].append('escape_hatches')
        return (current, '', disclosure)

    def restore_mechanical_case_envelope_sections(self, body: dict) -> tuple[dict | None, str]:
        restored, error, _disclosure = self.prepare_mechanical_case_envelope_sections(body)
        if error == 'blocks_change_not_authorized':
            error = 'blocks_changed'
        return (restored, error)

    def record_mechanical_case_acceptance(self, attempt: int, mechanical_case: dict, *, input_sha256: str='') -> None:
        """被接受的那份输入：与先前被拒的输入配对成修复见证（反馈自查的回放料）。"""
        with self._lock:
            self.mechanical_case_accepted = {'attempt': int(attempt), 'input_sha256': str(input_sha256 or ''), 'input': copy.deepcopy(mechanical_case) if isinstance(mechanical_case, dict) else {}}

    def record_mechanical_case_rejection(self, attempt: int, violations: list[dict[str, object]], *, input_sha256: str='', rule_identity: str='', mechanical_case: dict | None=None) -> None:
        normalized = []
        for item in violations:
            if not isinstance(item, dict):
                continue
            finding: dict[str, object] = {key: str(item.get(key) or '') for key in ('gate', 'code', 'locus', 'detail', 'legal_form')}
            expectation_ids = item.get('expectation_ids')
            if isinstance(expectation_ids, list):
                bound = sorted({str(value).strip() for value in expectation_ids if str(value).strip()})
                if bound:
                    finding['expectation_ids'] = bound
            normalized.append(finding)
        with self._lock:
            self.mechanical_case_rejections.append({'attempt': int(attempt), 'violations': normalized, **({'input_sha256': str(input_sha256)} if input_sha256 else {}), **({'rule_identity': str(rule_identity)} if rule_identity else {}), **({'input': copy.deepcopy(mechanical_case)} if isinstance(mechanical_case, dict) and input_sha256 else {})})

    def record_gate_advisory(self, advisory: dict) -> None:
        with self._lock:
            self.gate_advisories.append(dict(advisory))

    def _reject_authoring_statement(self, code: str) -> tuple[dict, str]:
        from cex_core.engine.ist_core.tools.device.authoring_account_tools import statement_rejection_stops_dispatch
        if statement_rejection_stops_dispatch(code):
            self.authoring_channel_rejection = {'code': code, 'fork_id': self.fork_id, 'autoid': self.autoid, 'dispatch_id': self.dispatch_id, 'batch_run_id': self.batch_run_id}
        return ({}, code)

    def _record_authoring_statement(self, kind: str, payload: dict) -> tuple[dict, str]:
        from cex_core.engine.ist_core.security_scrub import scrub_value
        from cex_core.engine.ist_core.tools.device.authoring_account_tools import AuthoringAccountSubmission, EngineGapSubmission
        from pydantic import ValidationError
        if kind not in {'engine_gap', 'authoring_account'}:
            return ({}, 'authoring_statement_invalid')
        try:
            schema = EngineGapSubmission if kind == 'engine_gap' else AuthoringAccountSubmission
            payload = schema.model_validate(payload).model_dump(mode='python')
        except ValidationError:
            return ({}, 'authoring_statement_invalid')
        with self._lock:
            from cex_core.engine.ist_core.skills.authoring_account_supplement import current_supplement_grant
            grant = current_supplement_grant()
            supplementary = bool(grant is not None and self.account_supplement and (grant['diagnostic_dispatch_id'] == self.dispatch_id) and (grant['batch_run_id'] == self.batch_run_id) and (grant['autoid'] == self.autoid))
            if not supplementary and (self.skill != 'compile-worker' or self.agent not in {'compile-worker', 'compile-worker-flash'}) or not re.fullmatch('[0-9]{18}', str(self.autoid or '')) or (not self.fork_id) or (not _DISPATCH_ID_RE.fullmatch(str(self.dispatch_id or ''))) or (not _DISPATCH_ID_RE.fullmatch(str(self.batch_run_id or ''))):
                return self._reject_authoring_statement('no_engine_dispatch')
            if self.account_supplement and (not supplementary or kind != 'authoring_account'):
                return self._reject_authoring_statement('no_engine_dispatch')
            if self.closed:
                return self._reject_authoring_statement('authoring_session_closed')
            if self.revoked or self.dispatch_id in _REVOKED_DISPATCHES:
                return self._reject_authoring_statement('authoring_dispatch_revoked')
            verification: dict = {'status': 'model_account', 'scope': 'model_statement_only'}
            if kind == 'engine_gap':
                checks = []
                for reference in payload['rejection_refs']:
                    matches = []
                    for attempt in self.mechanical_case_rejections:
                        if reference['submission_attempt'] is not None and reference['submission_attempt'] != attempt.get('attempt'):
                            continue
                        for violation in attempt.get('violations') or []:
                            if all((reference[key] == violation.get(key) for key in ('gate', 'code', 'locus'))):
                                matches.append({'attempt': attempt['attempt'], 'violation': copy.deepcopy(violation), 'violation_sha256': persisted_surface_sha256(scrub_value(violation)), 'input_sha256': str(attempt.get('input_sha256') or ''), 'rule_identity': str(attempt.get('rule_identity') or ''), 'identity_status': 'complete' if all((re.fullmatch('[0-9a-f]{64}', str(attempt.get(key) or '')) for key in ('input_sha256', 'rule_identity'))) else 'incomplete'})
                    checks.append({'reference': copy.deepcopy(reference), 'matches': matches})
                verification = {'status': 'claim_reference_confirmed' if checks and all((row['matches'] and all((match['identity_status'] == 'complete' for match in row['matches'])) for row in checks)) else 'unverified', 'scope': 'rejection_occurrence_only', 'references': checks}
            if supplementary:
                verification = {'status': 'model_account', 'scope': 'supplementary_visible_records_only'}
            body = scrub_value({'schema': engine_schema_id('engine_gap') if kind == 'engine_gap' else engine_schema_id('authoring_account'), 'autoid': self.autoid, 'fork_id': self.fork_id, 'dispatch_id': self.dispatch_id, 'batch_run_id': self.batch_run_id, 'authored_round': self.authored_round, 'payload': copy.deepcopy(payload), 'verification': verification})
            identifier = persisted_surface_sha256(body)
            records = self.engine_gaps if kind == 'engine_gap' else self.authoring_accounts
            for previous in records:
                if previous['record_id'] == identifier:
                    return (copy.deepcopy(previous), '')
            if supplementary and records:
                return self._reject_authoring_statement('authoring_session_closed')
            record = {**body, 'record_id': identifier, 'ordinal': len(records) + 1}
            event = 'engine_gap_submitted' if kind == 'engine_gap' else 'authoring_account_submitted'
            if not persist_worker_session_event(self, {'ev': event, 'record': record}):
                return ({}, 'authoring_journal_unavailable')
            if self.revoked or self.dispatch_id in _REVOKED_DISPATCHES:
                return self._reject_authoring_statement('authoring_dispatch_revoked')
            records.append(copy.deepcopy(record))
            return (copy.deepcopy(record), '')

    def record_engine_gap(self, payload: dict) -> tuple[dict, str]:
        return self._record_authoring_statement('engine_gap', payload)

    def record_authoring_account(self, payload: dict) -> tuple[dict, str]:
        return self._record_authoring_statement('authoring_account', payload)

    def observe_authoring_budget(self, *, total_limit: int, domain_limit: int, schema_names: list[str], calls: list[str] | None) -> dict:
        from cex_core.engine.ist_core.middleware.authoring_account_reserve import AuthoringAccountBudgetError, ACCOUNT_TOOL
        with self._lock:
            policy = {'total_limit': total_limit, 'domain_limit': domain_limit, 'schema_names': schema_names}
            previous = self.authoring_budget
            if previous and any((previous.get(key) != value for key, value in policy.items())):
                raise AuthoringAccountBudgetError('authoring budget policy changed within a dispatch')
            if previous.get('closed') or previous.get('unavailable'):
                raise AuthoringAccountBudgetError('authoring budget journal is closed or unavailable')
            if previous and calls is None:
                return copy.deepcopy(previous)
            record = {'schema': engine_schema_id('authoring_tool_budget'), **policy, 'sequence': previous.get('sequence', 0) + 1, 'used_tool_calls': previous.get('used_tool_calls', 0) + len(calls or []), 'used_domain_calls': previous.get('used_domain_calls', 0) + sum((name not in {*schema_names, ACCOUNT_TOOL} for name in calls or [])), 'response_calls': calls, 'closed': False}
            record['remaining_tool_calls'] = max(0, total_limit - record['used_tool_calls'])
            if not persist_worker_session_event(self, {'ev': 'authoring_budget_observed', 'budget': record}):
                self.authoring_budget = {**record, 'unavailable': True}
                raise AuthoringAccountBudgetError('authoring budget observation was not durably persisted')
            self.authoring_budget = record
            return copy.deepcopy(record)

    def close_authoring_budget(self) -> None:
        with self._lock:
            if not self.authoring_budget or self.authoring_budget.get('unavailable'):
                return
            record = {**self.authoring_budget, 'closed': True}
            if persist_worker_session_event(self, {'ev': 'authoring_budget_closed', 'budget': record}):
                self.authoring_budget = record
            else:
                self.authoring_budget = {**record, 'closed': False, 'unavailable': True}

    def structural_rejection_streak(self) -> dict:
        with self._lock:
            records = list(self.mechanical_case_rejections)
        from cex_core.engine.ist_core.compile_engine.rejection_history import repeated_rejection
        return repeated_rejection(records, group_fields=('attempt',))

    def record_mechanical_case_repair_disclosure(self, attempt: int, disclosure: dict[str, object]) -> None:
        authorized_by = sorted({str(value).strip() for value in disclosure.get('authorized_by') or [] if str(value).strip()})
        restored_sections = sorted({str(value).strip() for value in disclosure.get('restored_sections') or [] if str(value).strip()})
        with self._lock:
            self.mechanical_case_repair_disclosures.append({'attempt': int(attempt), 'code': str(disclosure.get('code') or ''), 'authorized_by': authorized_by, 'restored_sections': restored_sections})

    def consistency_conflict_terminal_allowed(self, autoid: str) -> bool:
        with self._lock:
            if str(autoid or '') != self.autoid:
                return False
            return any((str(item.get('code') or '') == 'case_abandoned_by_consistency' for record in self.mechanical_case_rejections if isinstance(record, dict) for item in record.get('violations') or [] if isinstance(item, dict)))

    def record_compile_rejection(self, gate_codes) -> dict:
        from cex_core.engine.ist_core.compile_engine.facts import no_progress_step
        violations = []
        for value in gate_codes or ():
            if isinstance(value, dict):
                code = str(value.get('code') or value.get('gate') or '').strip()
                detail = str(value.get('detail') or '').strip()
                step = value.get('step_index', value.get('step', -1))
            else:
                code = str(value or '').strip()
                detail = ''
                step = -1
            if code:
                violations.append({'code': code, 'detail': detail, 'step_index': step if isinstance(step, int) else -1})
        codes = sorted({item['code'] for item in violations})
        learning = bool(codes) and all((code in _COMPILE_LEARNING_GATES for code in codes))
        with self._lock:
            if learning:
                signature = hashlib.sha256(json.dumps(violations, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
                if not any((item.get('revision_sha256') == self.current_compile_revision for item in self.compile_learning_history)):
                    self.compile_learning_history.append({'revision_sha256': self.current_compile_revision, 'violation_signature': signature, 'gate_codes': codes})
                try:
                    threshold = int(os.environ.get('IST_COMPILE_LEARNING_MAX', '12'))
                except (TypeError, ValueError):
                    threshold = 12
                threshold = max(4, min(threshold, 30))
                streak = len(self.compile_learning_history)
                decision = {'domain': 'compile', 'gate_class': 'contract_learning', 'failure_key': f'compile_learning:"{signature}"', 'streak': streak, 'threshold': threshold, 'revision_refs': [str(item.get('revision_sha256') or '') for item in self.compile_learning_history], 'stop_keys': [f'compile_learning:"{signature}"'] if streak >= threshold else [], 'stop': streak >= threshold}
                decision['decision_id'] = hashlib.sha256(json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:24]
            else:
                decision = no_progress_step(self.compile_no_progress_history, domain='compile', value=codes, revision_sha256=self.current_compile_revision)
                self.compile_no_progress_history = decision.pop('history')
                decision['gate_class'] = 'no_progress'
            self.last_no_progress_decision = dict(decision)
            self.no_progress_decisions.append(dict(decision))
            self.compile_attempts.append({'compile_attempt_id': self.current_compile_attempt_id, 'revision_sha256': self.current_compile_revision, 'result': 'rejected', 'gate_codes': codes, 'violations': violations, 'no_progress_decision': dict(decision)})
            self.current_compile_recorded = True
            if decision['stop']:
                self.compile_exhausted = True
                unresolved = any((str(key or '') == 'compile:"provenance_source_unresolved"' for key in decision.get('stop_keys') or []))
                self.stop_reason = 'missing_authority_exhausted' if unresolved else 'compile_contract_learning_exhausted' if learning else 'compile_exhausted'
            return dict(decision)

    def cancel_compile_attempt(self) -> None:
        with self._lock:
            self.current_compile_revision = ''
            self.current_compile_attempt_id = ''
            self.current_compile_recorded = False

    def finish_compile_attempt(self, *, success: bool) -> dict:
        with self._lock:
            if not self.current_compile_recorded:
                record = {'compile_attempt_id': self.current_compile_attempt_id, 'revision_sha256': self.current_compile_revision, 'result': 'pass' if success else 'error', 'gate_codes': []}
                self.compile_attempts.append(record)
            else:
                record = dict(self.compile_attempts[-1])
            if success:
                self.compile_no_progress_history = []
                self.compile_learning_history = []
                self.compile_exhausted = False
                if self.stop_reason in {'compile_exhausted', 'compile_contract_learning_exhausted'}:
                    self.stop_reason = ''
            self.current_compile_revision = ''
            self.current_compile_attempt_id = ''
            self.current_compile_recorded = False
            return dict(record)

    def cancel_reservation(self) -> None:
        with self._lock:
            if self.in_flight and self.attempts > 0:
                self.attempts -= 1
            self.in_flight = False
            self.current_artifact_sha256 = ''
            self.current_remote_artifact_sha256 = ''
            self.current_attempt_id = ''
            self.current_prediction = {}

@contextmanager
def worker_device_scope(*, skill: str, agent: str, autoid: str, fork_id: str, device_access: bool=True, dispatch_id: str='', batch_run_id: str='', expected_bed: str='', expected_build: str='', expected_module: str='', capability_bed: str='', capability_full_version: str='', capability_version: str='', capability_build: str='', capability_generation_id: str='', capability_manifest_sha256: str='', capability_projection_sha256: str='', authored_round: int=1, source_manifest_ref: str='', source_manifest_sha256: str='', source_case_slice_sha256: str='', source_case_slice: dict | None=None) -> Iterator[WorkerDeviceSession | None]:
    session = None
    from cex_core.engine.ist_core.skills.authoring_account_supplement import current_supplement_grant
    supplement_grant = current_supplement_grant()
    supplementary = bool(skill == 'authoring-account-supplement' and supplement_grant is not None and (supplement_grant['diagnostic_dispatch_id'] == dispatch_id) and (supplement_grant['batch_run_id'] == batch_run_id) and (supplement_grant['autoid'] == autoid))
    if (skill == 'compile-worker' or supplementary) and fork_id:
        bound_source_ref, bound_source_manifest_sha256, bound_source_slice_sha256, bound_source_slice = _validated_source_binding(autoid=autoid, source_manifest_ref=source_manifest_ref, source_manifest_sha256=source_manifest_sha256, source_case_slice_sha256_value=source_case_slice_sha256, source_case_slice=source_case_slice or {})
        session = WorkerDeviceSession(skill=skill, agent=agent, autoid=autoid, fork_id=fork_id, device_access=device_access is True and (not supplementary), dispatch_id=dispatch_id, batch_run_id=batch_run_id, bed_lease_id='', expected_bed=expected_bed, expected_build=expected_build, expected_module=expected_module, capability_bed=capability_bed, capability_full_version=capability_full_version, capability_version=capability_version, capability_build=capability_build, capability_generation_id=capability_generation_id, capability_manifest_sha256=capability_manifest_sha256, capability_projection_sha256=capability_projection_sha256, authored_round=max(1, int(authored_round or 1)), source_manifest_ref=bound_source_ref, source_manifest_sha256=bound_source_manifest_sha256, source_case_slice_sha256=bound_source_slice_sha256, source_case_slice=bound_source_slice, account_supplement=copy.deepcopy(supplement_grant) if supplementary else {})
        if dispatch_id:
            with _COMPLETED_LOCK:
                session.revoked = dispatch_id in _REVOKED_DISPATCHES
        with _SESSIONS_LOCK:
            _SESSIONS[fork_id] = session
    token = _SCOPE.set(session)
    fork_token = _FORK_SCOPE.set({'skill': str(skill or ''), 'agent': str(agent or ''), 'fork_id': str(fork_id or '')} if fork_id else None)
    try:
        yield session
    finally:
        _SCOPE.reset(token)
        _FORK_SCOPE.reset(fork_token)
        if session is not None:
            session.release_device_lease()
            session.close_authoring_budget()
            with session._lock:
                session.closed = True
                summary = {'schema': 'worker_loop_outcome', 'autoid': session.autoid, 'fork_id': session.fork_id, 'dispatch_id': session.dispatch_id, 'batch_run_id': session.batch_run_id, 'bed_lease_id': session.bed_lease_id, 'env_id': session.env_id, 'bed': session.actual_bed, 'device_access': session.device_access, 'capability_generation': {'bed': session.capability_bed, 'full_version': session.capability_full_version, 'version': session.capability_version, 'build': session.capability_build, 'generation_id': session.capability_generation_id, 'manifest_sha256': session.capability_manifest_sha256, 'projection_sha256': session.capability_projection_sha256}, 'source_binding': {'manifest_ref': session.source_manifest_ref, 'manifest_sha256': session.source_manifest_sha256, 'case_slice_sha256': session.source_case_slice_sha256}, 'lease_acquired_persisted': session.lease_acquired_persisted, 'lease_released_persisted': session.lease_released_persisted, 'shared_binding_persisted': session.shared_binding_persisted, 'lease_error': session.lease_error, 'stop_reason': session.stop_reason, 'compile_exhausted': session.compile_exhausted, 'max_probe_calls': session.max_probe_calls, 'probe_calls': session.probe_calls, 'probe_exhausted': session.probe_exhausted, 'probe_evidence': [dict(item) for item in session.probe_evidence], 'command_heads_query_receipts': [dict(item) for item in session.command_heads_query_receipts], 'not_compilable_reports': [dict(item) for item in session.not_compilable_reports], 'worker_claims': [copy.deepcopy(item) for item in session.worker_claims], 'unsupported_feature_reports': [dict(item) for item in session.unsupported_feature_reports], 'semantic_attempts': session.semantic_attempts, 'infrastructure_attempts': session.infrastructure_attempts, 'prediction_chain': [dict(item) for item in session.prediction_chain], 'no_progress_decisions': [dict(item) for item in session.no_progress_decisions], 'compile_attempts': [dict(item) for item in session.compile_attempts], 'mechanical_case_submission_attempts': session.mechanical_case_submission_attempts, 'engine_gaps': copy.deepcopy(session.engine_gaps), 'authoring_accounts': copy.deepcopy(session.authoring_accounts), 'admission_rejection': copy.deepcopy(session.admission_rejection), 'authoring_budget': copy.deepcopy(session.authoring_budget), 'account_supplement': copy.deepcopy(session.account_supplement), 'mechanical_case_rejections': [{'attempt': int(item.get('attempt') or 0), **({'input_sha256': item['input_sha256']} if item.get('input_sha256') else {}), **({'rule_identity': item['rule_identity']} if item.get('rule_identity') else {}), **({'input': copy.deepcopy(item['input'])} if isinstance(item.get('input'), dict) else {}), 'violations': [dict(violation) for violation in item.get('violations') or [] if isinstance(violation, dict)]} for item in session.mechanical_case_rejections], 'mechanical_case_accepted': copy.deepcopy(session.mechanical_case_accepted), 'gate_advisories': [dict(item) for item in session.gate_advisories], 'mechanical_case_repair_disclosures': [dict(item) for item in session.mechanical_case_repair_disclosures]}
            try:
                from cex_core.engine.ist_core.security_scrub import scrub_value
                exact_heads_receipts = copy.deepcopy(summary['command_heads_query_receipts'])
                exact_not_compilable_reports = copy.deepcopy(summary['not_compilable_reports'])
                summary = scrub_value(summary)
            except Exception:
                exact_heads_receipts = copy.deepcopy(summary['command_heads_query_receipts'])
                exact_not_compilable_reports = copy.deepcopy(summary['not_compilable_reports'])
            base_identity_complete = all((str(value or '').strip() for value in (session.autoid, session.fork_id, session.dispatch_id, session.batch_run_id, session.expected_bed, session.expected_build, session.expected_module)))
            _touched_device = session.attempts > 0 or session.probe_calls > 0
            device_identity_complete = not _touched_device or (all((str(value or '').strip() for value in (session.env_id, session.actual_bed))) and (session.attempts == 0 or bool(str(session.bed_lease_id or '').strip())))
            identity_complete = base_identity_complete and device_identity_complete
            with _SESSION_OUTCOMES_LOCK:
                if not identity_complete:
                    summary['quarantined_reason'] = 'execution_identity_incomplete'
                    with _COMPLETED_LOCK:
                        _QUARANTINED.append(summary)
                        if len(_QUARANTINED) > 4096:
                            del _QUARANTINED[:-4096]
                elif session.revoked or session.dispatch_id in _REVOKED_DISPATCHES:
                    summary['quarantined_reason'] = 'dispatch_revoked'
                    with _COMPLETED_LOCK:
                        _QUARANTINED.append(summary)
                        if len(_QUARANTINED) > 4096:
                            del _QUARANTINED[:-4096]
                else:
                    summary['command_heads_query_receipts'] = exact_heads_receipts
                    summary['not_compilable_reports'] = exact_not_compilable_reports
                    _SESSION_OUTCOMES.append(summary)
                    if len(_SESSION_OUTCOMES) > 4096:
                        del _SESSION_OUTCOMES[:-4096]
            with _SESSIONS_LOCK:
                _SESSIONS.pop(fork_id, None)

def current_worker_device_session() -> WorkerDeviceSession | None:
    session = _SCOPE.get()
    if session is not None:
        return session
    try:
        from langgraph.config import get_config
        meta = (get_config() or {}).get('metadata') or {}
        if str(meta.get('fork_skill') or '') not in {'compile-worker', 'authoring-account-supplement'}:
            return None
        fork_id = str(meta.get('fork_id') or '')
    except Exception:
        return None
    if not fork_id:
        return None
    with _SESSIONS_LOCK:
        return _SESSIONS.get(fork_id)

def current_fork_execution_context() -> dict[str, str]:
    current = _FORK_SCOPE.get()
    return dict(current) if current else {}

def publish_worker_oracle(record: dict) -> None:
    session = current_worker_device_session()
    if session is None:
        return
    item = dict(record)
    item['autoid'] = session.autoid
    item['fork_id'] = session.fork_id
    item['dispatch_id'] = session.dispatch_id
    item['batch_run_id'] = session.batch_run_id
    item['bed_lease_id'] = session.bed_lease_id
    item['env_id'] = session.env_id
    item['bed'] = session.actual_bed
    required_identity = (session.autoid, session.fork_id, session.dispatch_id, session.batch_run_id, session.bed_lease_id, session.env_id, session.actual_bed, session.expected_bed, session.expected_build, session.expected_module, str(item.get('run_id') or ''), str(item.get('artifact_sha256') or ''))
    with _COMPLETED_LOCK:
        if not all((str(value or '').strip() for value in required_identity)):
            item['quarantined_reason'] = 'execution_identity_incomplete'
            _QUARANTINED.append(item)
            if len(_QUARANTINED) > 4096:
                del _QUARANTINED[:-4096]
            return
        if session.revoked or session.dispatch_id in _REVOKED_DISPATCHES:
            item['quarantined_reason'] = 'dispatch_revoked'
            _QUARANTINED.append(item)
            if len(_QUARANTINED) > 4096:
                del _QUARANTINED[:-4096]
            return
        _COMPLETED.append(item)
        if len(_COMPLETED) > 4096:
            del _COMPLETED[:-4096]

def claim_worker_oracles(autoid: str, *, dispatch_id: str, batch_run_id: str='', since: float=0.0) -> list[dict]:
    if not dispatch_id:
        return []
    claimed: list[dict] = []
    keep: list[dict] = []
    with _COMPLETED_LOCK:
        for item in _COMPLETED:
            if str(item.get('autoid') or '') == autoid and str(item.get('dispatch_id') or '') == dispatch_id and (not batch_run_id or str(item.get('batch_run_id') or '') == batch_run_id) and (float(item.get('ts') or 0.0) >= since):
                claimed.append(dict(item))
            else:
                keep.append(item)
        _COMPLETED[:] = keep
    return claimed

def claim_worker_session_outcomes(autoid: str, *, dispatch_id: str, batch_run_id: str='') -> list[dict]:
    if not dispatch_id:
        return []
    claimed: list[dict] = []
    keep: list[dict] = []
    with _SESSION_OUTCOMES_LOCK:
        for item in _SESSION_OUTCOMES:
            if str(item.get('autoid') or '') == autoid and str(item.get('dispatch_id') or '') == dispatch_id and (not batch_run_id or str(item.get('batch_run_id') or '') == batch_run_id):
                claimed.append(dict(item))
            else:
                keep.append(item)
        _SESSION_OUTCOMES[:] = keep
    return claimed

def recover_worker_dispatch_journal(autoid: str, *, dispatch_id: str, batch_run_id: str) -> list[dict]:
    if not autoid or not dispatch_id or (not batch_run_id):
        return []
    from cex_core.engine.ist_core.compile_engine import _shared as sh
    root = sh.project_root() / 'runtime' / 'worker_oracle_journal'
    if not root.is_dir() or root.is_symlink():
        return []
    out: list[dict] = []
    for path in sorted(root.glob('*.jsonl')):
        try:
            if path.is_symlink() or path.stat().st_size > 8 * 1024 * 1024:
                continue
            for line_no, line in enumerate(path.read_text(encoding='utf-8', errors='strict').splitlines(), start=1):
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(item, dict):
                    continue
                if str(item.get('autoid') or '') != autoid or str(item.get('dispatch_id') or '') != dispatch_id or str(item.get('batch_run_id') or '') != batch_run_id:
                    continue
                out.append({**item, '_journal_file': path.name, '_journal_line': line_no})
        except (OSError, UnicodeError):
            continue
    return out

def authoring_budget_receipt(autoid: str, *, dispatch_id: str, batch_run_id: str) -> tuple[dict, str]:
    rows = recover_worker_dispatch_journal(autoid, dispatch_id=dispatch_id, batch_run_id=batch_run_id)
    if not rows:
        return ({}, 'authoring_budget_missing')
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row.get('fork_id') or ''), []).append(row)
    receipts = []
    for fork_id, events in groups.items():
        observed = [row for row in events if row.get('ev') == 'authoring_budget_observed']
        closed = [row for row in events if row.get('ev') == 'authoring_budget_closed']
        if not fork_id or not observed or len(closed) != 1:
            return ({}, 'authoring_budget_unclosed')
        total = domain = 0
        first = observed[0].get('budget') or {}
        limit = first.get('total_limit')
        domain_limit = first.get('domain_limit')
        schema_names = first.get('schema_names')
        if type(limit) is not int or limit < 1 or type(domain_limit) is not int or (domain_limit < 0) or (not isinstance(schema_names, list)) or (not all((isinstance(name, str) for name in schema_names))) or (limit != domain_limit + 1 + bool(schema_names)):
            return ({}, 'authoring_budget_invalid')
        for index, row in enumerate(observed, 1):
            budget = row.get('budget') or {}
            calls = budget.get('response_calls')
            if calls is not None and (not isinstance(calls, list) or not all((isinstance(name, str) for name in calls))):
                return ({}, 'authoring_budget_invalid')
            total += len(calls or [])
            domain += sum((name not in {*schema_names, 'submit_authoring_account'} for name in calls or []))
            if not accepts_engine_schema(budget.get('schema'), 'authoring_tool_budget') or budget.get('sequence') != index or budget.get('total_limit') != limit or (budget.get('domain_limit') != domain_limit) or (budget.get('schema_names') != schema_names) or (budget.get('closed') is not False) or (budget.get('used_tool_calls') != total) or (budget.get('used_domain_calls') != domain) or (budget.get('remaining_tool_calls') != max(0, limit - total)):
                return ({}, 'authoring_budget_invalid')
        end = closed[0]
        if (end.get('budget') or {}) != {**observed[-1]['budget'], 'closed': True} or end.get('_journal_line', 0) <= observed[-1].get('_journal_line', 0):
            return ({}, 'authoring_budget_invalid')
        receipts.append({'fork_id': fork_id, 'total_limit': limit, 'used_tool_calls': total, 'source_manifest_ref': end.get('source_manifest_ref'), 'source_manifest_sha256': end.get('source_manifest_sha256'), 'source_case_slice_sha256': end.get('source_case_slice_sha256'), 'closed_fact_sha256': persisted_surface_sha256({key: value for key, value in end.items() if not key.startswith('_')})})
    limit = min((row['total_limit'] for row in receipts))
    used = sum((row['used_tool_calls'] for row in receipts))
    result = {'schema': engine_schema_id('authoring_tool_budget_receipt'), 'autoid': autoid, 'dispatch_id': dispatch_id, 'batch_run_id': batch_run_id, 'total_limit': limit, 'used_tool_calls': used, 'remaining_tool_calls': max(0, limit - used), 'closed': True, 'fork_receipts': sorted(receipts, key=lambda row: row['fork_id'])}
    return ({**result, 'receipt_sha256': persisted_surface_sha256(result)}, '')

def persist_worker_dispatch_termination(*, skill: str, agent: str, autoid: str, fork_id: str, dispatch_id: str, batch_run_id: str, execution_identity: dict, source_binding: dict, termination: dict, usage: dict, tool_calls: dict, structured_response_attempts: int) -> bool:
    if not dispatch_id or not batch_run_id or (not autoid) or (not fork_id):
        return False
    recorder = WorkerDeviceSession(skill=skill, agent=agent, autoid=autoid, fork_id=fork_id, dispatch_id=dispatch_id, batch_run_id=batch_run_id, device_access=False, **{key: value for key, value in execution_identity.items() if key in WorkerDeviceSession.__dataclass_fields__ and key not in {'skill', 'agent', 'autoid', 'fork_id', 'dispatch_id', 'batch_run_id', 'device_access'}}, **source_binding)
    return persist_worker_session_event(recorder, {'ev': 'worker_dispatch_terminated', 'invocation_finished': True, 'termination': copy.deepcopy(termination), 'usage': copy.deepcopy(usage), 'tool_calls': dict(tool_calls), 'structured_response_attempts': structured_response_attempts})

def dispatch_identity_from_brief(brief: str) -> tuple[str, str]:
    try:
        from cex_core.engine.ist_core.compile_engine.worker_protocol import parse_compile_worker_brief
        payload = parse_compile_worker_brief(str(brief or ''))
    except (TypeError, ValueError):
        return ('', '')
    identity = payload['identity']
    dispatch_id = str(identity.get('worker_dispatch_id') or '')
    batch_run_id = str(identity.get('batch_run_id') or '')
    if not _DISPATCH_ID_RE.fullmatch(dispatch_id):
        dispatch_id = ''
    if batch_run_id and (not _DISPATCH_ID_RE.fullmatch(batch_run_id)):
        batch_run_id = ''
    return (dispatch_id, batch_run_id)

def device_access_from_brief(brief: str) -> bool:
    try:
        from cex_core.engine.ist_core.compile_engine.worker_protocol import parse_compile_worker_brief
        payload = parse_compile_worker_brief(str(brief or ''))
    except (TypeError, ValueError):
        return False
    identity = payload['identity']
    try:
        attempt = int(identity.get('dispatch_attempt') or 0)
    except (TypeError, ValueError):
        return False
    return attempt > 1

def worker_execution_identity_from_brief(brief: str) -> dict[str, Any]:
    try:
        from cex_core.engine.ist_core.compile_engine.worker_protocol import parse_compile_worker_brief
        payload = parse_compile_worker_brief(str(brief or ''))
    except (TypeError, ValueError):
        return {}
    identity = payload['identity']
    execution = identity['execution']
    capability = identity['capability']
    out = {'bed_lease_id': '', 'expected_bed': str(execution.get('bed') or ''), 'expected_build': str(execution.get('build') or ''), 'expected_module': str(execution.get('module') or ''), 'capability_bed': str(capability.get('bed') or ''), 'capability_full_version': str(capability.get('full_version') or ''), 'capability_version': str(capability.get('version') or ''), 'capability_build': str(capability.get('build') or ''), 'capability_generation_id': str(capability.get('generation_id') or ''), 'capability_manifest_sha256': str(capability.get('manifest_sha256') or ''), 'capability_projection_sha256': str(capability.get('projection_sha256') or ''), 'authored_round': int(identity.get('authored_round') or 1)}
    for key, value in tuple(out.items()):
        if key == 'authored_round':
            continue
        if len(value) > 256 or any((ord(ch) < 32 for ch in value)):
            out[key] = ''
    if out['capability_version'] and (not re.fullmatch('\\d+(?:\\.\\d+){1,2}', out['capability_version'])):
        out['capability_version'] = ''
    if out['capability_build'] and (not re.fullmatch('\\d+', out['capability_build'])):
        out['capability_build'] = ''
    if out['capability_generation_id'] and (not re.fullmatch('g-[0-9a-f]{24}-[0-9a-f]{24}', out['capability_generation_id'])):
        out['capability_generation_id'] = ''
    if out['capability_manifest_sha256'] and (not re.fullmatch('[0-9a-f]{64}', out['capability_manifest_sha256'])):
        out['capability_manifest_sha256'] = ''
    if out['capability_projection_sha256'] and (not re.fullmatch('[0-9a-f]{64}', out['capability_projection_sha256'])):
        out['capability_projection_sha256'] = ''
    return out

def revoke_worker_dispatch(dispatch_id: str) -> None:
    dispatch_id = str(dispatch_id or '')
    if not dispatch_id:
        return
    with _COMPLETED_LOCK:
        _REVOKED_DISPATCHES.add(dispatch_id)
    with _SESSIONS_LOCK:
        sessions = list(_SESSIONS.values())
    for session in sessions:
        if session.dispatch_id == dispatch_id:
            with session._lock:
                session.revoked = True

def quarantined_worker_oracles() -> list[dict]:
    with _COMPLETED_LOCK:
        return [dict(item) for item in _QUARANTINED]
__all__ = ['COMMAND_HEADS_RECEIPT_VALIDATION_CODES', 'NOT_COMPILABLE_HEADS_VALIDATION_CODES', 'NOT_COMPILABLE_REASON_CODES', 'NOT_COMPILABLE_REASON_NO_CLI', 'NOT_COMPILABLE_REASON_ENV_GAP', 'NOT_COMPILABLE_REASON_AUTHOR_GAP', 'NOT_COMPILABLE_REASON_AUTHOR_CONFLICT', 'AUTHOR_SIDE_NOT_COMPILABLE_REASON_CODES', 'WorkerDeviceSession', 'canonical_source_case_slice', 'canonical_source_case_slice_sha256', 'claim_worker_oracles', 'claim_worker_session_outcomes', 'current_fork_execution_context', 'current_worker_device_session', 'dispatch_identity_from_brief', 'publish_worker_oracle', 'quarantined_worker_oracles', 'recover_worker_dispatch_journal', 'revoke_worker_dispatch', 'validate_command_heads_query_receipt', 'validate_command_heads_session_receipts', 'validate_not_compilable_heads_summary', 'validate_source_case_anchors', 'worker_device_loop_enabled', 'worker_device_infra_retries', 'worker_device_max_rounds', 'worker_probe_max_calls', 'worker_device_scope', 'worker_execution_identity_from_brief']
