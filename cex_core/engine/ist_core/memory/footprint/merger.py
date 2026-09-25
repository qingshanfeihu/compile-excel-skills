# 生成：tools/extract_engine.py ← InfoTest main/ist_core/memory/footprint/merger.py（sha256 f558491f88c57287）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import logging
import os
import re
import stat
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from cex_core.engine.ist_core.memory.footprint.schema import LEVEL_KINDS, MergeResult, RoutedFact, TEMPLATE_MAP
from cex_core.engine.ist_core.memory.footprint.router import catalog_head_tokens_clean
logger = logging.getLogger(__name__)
_MAX_FOOTPRINT_JSON_BYTES = 16 * 1024 * 1024
_FOOTPRINT_LOCK_NAME = '.footprint.write.lock'
_FOOTPRINT_THREAD_LOCK = threading.Lock()

class FootprintWriteError(OSError):
    pass

def _strict_json_object(payload: bytes) -> dict:
    from cex_core.engine.case_compiler._sealed_io import validate_json_budget
    validate_json_budget(payload, error_type=FootprintWriteError, message='footprint JSON exceeds the structural budget', max_depth=128, max_tokens=500000)

    def no_duplicate_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise FootprintWriteError('footprint JSON contains duplicate keys')
            value[key] = item
        return value

    def reject_constant(_value: str):
        raise FootprintWriteError('footprint JSON contains a non-finite number')
    try:
        value = json.loads(payload.decode('utf-8'), object_pairs_hook=no_duplicate_keys, parse_constant=reject_constant)
    except FootprintWriteError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FootprintWriteError('footprint JSON is invalid') from exc
    if not isinstance(value, dict):
        raise FootprintWriteError('footprint JSON root must be an object')
    return value

@contextmanager
def _locked_footprint_root(footprint_dir: Path):
    from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow, open_or_create_regular_at_nofollow
    root_fd = open_directory_nofollow(footprint_dir, error_type=FootprintWriteError, invalid_message='footprint root path is invalid', unavailable_message='footprint root is unavailable or unsafe')
    lock_fd = None
    with _FOOTPRINT_THREAD_LOCK:
        try:
            flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0)
            if not getattr(os, 'O_NOFOLLOW', 0):
                raise FootprintWriteError('no-follow locking is unavailable')
            try:
                lock_fd = open_or_create_regular_at_nofollow(root_fd, _FOOTPRINT_LOCK_NAME, flags, mode=384, error_type=FootprintWriteError, unavailable_message='footprint lock is unavailable or unsafe')
            except FootprintWriteError as exc:
                raise FootprintWriteError('footprint lock is unavailable or unsafe') from exc
            info = os.fstat(lock_fd)
            if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or int(info.st_size) != 0 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()):
                raise FootprintWriteError('footprint lock is not a current-owner single-link regular file')
            os.fchmod(lock_fd, 384)
            try:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            except (ImportError, OSError) as exc:
                raise FootprintWriteError('footprint process locking is unavailable') from exc
            locked = os.fstat(lock_fd)
            named = os.stat(_FOOTPRINT_LOCK_NAME, dir_fd=root_fd, follow_symlinks=False)
            if int(named.st_dev) != int(locked.st_dev) or int(named.st_ino) != int(locked.st_ino) or any((not stat.S_ISREG(current.st_mode) or int(current.st_nlink) != 1 or int(current.st_size) != 0 or (hasattr(os, 'getuid') and int(current.st_uid) != os.getuid()) for current in (locked, named))):
                raise FootprintWriteError('footprint lock pathname changed before the critical section')
            try:
                yield root_fd
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            os.close(root_fd)

def _read_footprint_at(parent_fd: int, name: str) -> dict | None:
    payload = _read_footprint_payload_at(parent_fd, name)
    return None if payload is None else _strict_json_object(payload)

def _read_footprint_payload_at(parent_fd: int, name: str) -> bytes | None:
    from cex_core.engine.case_compiler._sealed_io import read_regular_at_nofollow
    try:
        payload = read_regular_at_nofollow(parent_fd, name, error_type=FootprintWriteError, open_message='footprint target is unavailable or unsafe', bounds_message='footprint target is not a bounded single-link regular file', changed_message='footprint target changed while being read', max_bytes=_MAX_FOOTPRINT_JSON_BYTES, min_bytes=1, preserve_missing=True, require_current_uid=True)
    except FileNotFoundError:
        return None
    return payload

def _write_footprint_at(parent_fd: int, name: str, data: dict) -> None:
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    _write_footprint_payload_at(parent_fd, name, payload)

def _write_footprint_payload_at(parent_fd: int, name: str, payload: bytes) -> None:
    from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_at_nofollow
    if len(payload) > _MAX_FOOTPRINT_JSON_BYTES:
        raise FootprintWriteError('footprint JSON exceeds the byte budget')
    atomic_write_bytes_at_nofollow(parent_fd, name, payload, error_type=FootprintWriteError, unavailable_message='footprint target cannot be published safely', mode=384)

def _entry_device_autoid(item: dict, *, node_name: str) -> str:
    evidence = item.get('evidence') or {}
    if not isinstance(evidence, dict):
        raise FootprintWriteError(f'footprint node {node_name} has an invalid evidence object')
    device_run = evidence.get('device_run') or {}
    if not isinstance(device_run, dict):
        raise FootprintWriteError(f'footprint node {node_name} has an invalid device_run object')
    return str(device_run.get('autoid') or '')

def _rollback_footprint_autoid(*, autoid: str, footprint_dir: Path | None=None) -> str:
    aid = str(autoid or '').strip()
    if re.fullmatch('\\d{18}', aid) is None:
        return 'error: footprint rollback autoid is invalid'
    if footprint_dir is None:
        from cex_core.engine.knowledge_paths import KNOWLEDGE_FOOTPRINTS
        footprint_dir = Path(KNOWLEDGE_FOOTPRINTS)
    from cex_core.engine.case_compiler._sealed_io import lexical_absolute
    root = lexical_absolute(footprint_dir)
    prepared: list[tuple[str, bytes, dict]] = []
    changed_names: list[str] = []
    nodes_fd = None
    try:
        with _locked_footprint_root(root) as root_fd:
            try:
                nodes_fd = _open_target_directory_at(root_fd, ('nodes',))
                names = sorted(os.listdir(nodes_fd))
                for name in names:
                    if not name.endswith('.json') or name.startswith('.') or Path(name).name != name:
                        continue
                    payload = _read_footprint_payload_at(nodes_fd, name)
                    if payload is None:
                        raise FootprintWriteError('footprint node disappeared during rollback precheck')
                    data = _strict_json_object(payload)
                    changed = False
                    for field in ('behaviors', 'decision_rules'):
                        entries = data.get(field, [])
                        if not isinstance(entries, list) or any((not isinstance(item, dict) for item in entries)):
                            raise FootprintWriteError(f'footprint node {name} has an invalid {field} array')
                        kept = [item for item in entries if _entry_device_autoid(item, node_name=name) != aid]
                        if len(kept) != len(entries):
                            data[field] = kept
                            changed = True
                    cli = data.get('cli', {})
                    if not isinstance(cli, dict):
                        raise FootprintWriteError(f'footprint node {name} has an invalid cli object')
                    commands = cli.get('commands', [])
                    if not isinstance(commands, list) or any((not isinstance(item, dict) for item in commands)):
                        raise FootprintWriteError(f'footprint node {name} has an invalid cli.commands array')
                    kept_commands = [item for item in commands if _entry_device_autoid(item, node_name=name) != aid]
                    if len(kept_commands) != len(commands):
                        cli['commands'] = kept_commands
                        data['cli'] = cli
                        changed = True
                    if changed:
                        prepared.append((name, payload, data))
                try:
                    for name, _old_payload, data in prepared:
                        _write_footprint_at(nodes_fd, name, data)
                        changed_names.append(name)
                except BaseException:
                    restore_errors: list[BaseException] = []
                    old_by_name = {name: old_payload for name, old_payload, _data in prepared}
                    for name in reversed(changed_names):
                        try:
                            _write_footprint_payload_at(nodes_fd, name, old_by_name[name])
                        except BaseException as restore_exc:
                            restore_errors.append(restore_exc)
                    if restore_errors:
                        raise FootprintWriteError('footprint rollback failed and restoration was incomplete') from restore_errors[0]
                    raise
            finally:
                if nodes_fd is not None:
                    os.close(nodes_fd)
                    nodes_fd = None
    except Exception as exc:
        return f'error: footprint rollback rejected ({type(exc).__name__}: {exc})'
    return f'footprint rollback autoid={aid}: nodes updated {len(prepared)}'

def _open_target_directory_at(root_fd: int, relative_parts: tuple[str, ...]) -> int:
    from cex_core.engine.case_compiler._sealed_io import directory_flags
    flags = directory_flags(error_type=FootprintWriteError, unavailable_message='footprint target directory is unavailable or unsafe')
    descriptor = os.dup(root_fd)
    try:
        for component in relative_parts:
            if not component or component in {'.', '..'} or Path(component).name != component:
                raise FootprintWriteError('footprint target directory is invalid')
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 493, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise
_LINE_PREFIX_RE = re.compile('^\\s*\\d+:\\s*')
_ELLIPSIS_RE = re.compile('\\.{3,}')

def _project_root() -> Path:
    return _cex_data_path('')
_MARKDOWN_ROOT = ('knowledge', 'data', 'markdown')
_EVIDENCE_ROOTS = (_MARKDOWN_ROOT, ('knowledge', 'data', 'manual'))

def _evidence_root_dirs() -> list[Path]:
    root = _project_root()
    out: list[Path] = []
    for parts in _EVIDENCE_ROOTS:
        candidate = Path(os.path.abspath(os.fspath(root.joinpath(*parts))))
        if candidate.is_dir():
            out.append(candidate)
    return out

def _evidence_trusted_root(path: Path) -> Path | None:
    for base in _evidence_root_dirs():
        try:
            path.relative_to(base)
            return base
        except ValueError:
            continue
    return None

def _rglob_roots(roots: list[Path], name: str) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for base in roots:
        for hit in base.rglob(name):
            key = str(hit)
            if key not in seen:
                seen.add(key)
                out.append(hit)
    return out

def _resolve_evidence_path(evidence_file: str) -> Path | None:
    if not evidence_file:
        return None
    root = _project_root()
    roots = _evidence_root_dirs()
    if not roots:
        return None
    raw = Path(str(evidence_file).strip())
    if not str(raw) or '..' in raw.parts or str(raw).startswith('~') or ('\x00' in str(raw)):
        return None
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(Path(os.path.abspath(os.fspath(raw))))
    elif any((raw.parts[:3] == parts for parts in _EVIDENCE_ROOTS)):
        candidates.append(Path(os.path.abspath(os.fspath(root / raw))))
    elif len(raw.parts) > 1:
        candidates.extend((Path(os.path.abspath(os.fspath(base / raw))) for base in roots))
    for direct in candidates:
        if _evidence_trusted_root(direct) is None:
            continue
        try:
            from cex_core.engine.case_compiler._sealed_io import stat_regular_nofollow
            stat_regular_nofollow(direct, error_type=OSError, invalid_message='manual evidence path is invalid', directory_message='manual evidence directory is unsafe', open_message='manual evidence file is unavailable', bounds_message='manual evidence file is not regular or too large', max_bytes=32 * 1024 * 1024)
            return direct
        except (ValueError, OSError):
            continue
    if candidates:
        return None
    name = raw.name
    usable: list[Path] = []
    for p in _rglob_roots(roots, name):
        try:
            candidate = Path(os.path.abspath(os.fspath(p)))
            if _evidence_trusted_root(candidate) is None:
                continue
            from cex_core.engine.case_compiler._sealed_io import stat_regular_nofollow
            stat_regular_nofollow(candidate, error_type=OSError, invalid_message='manual evidence path is invalid', directory_message='manual evidence directory is unsafe', open_message='manual evidence file is unavailable', bounds_message='manual evidence file is not regular or too large', max_bytes=32 * 1024 * 1024)
            usable.append(candidate)
        except (ValueError, OSError):
            continue
    if len(usable) == 1:
        return usable[0]
    if len(usable) > 1:
        logger.warning('证据 basename %r 在可信手册树里有 %d 份同名候选，拒绝解析——请在 evidence_file 里带上版本段（如 manual/10.5.0/%s）', name, len(usable), name)
    return None
_BR_RE = re.compile('<br\\s*/?>')
_CJK_RANGE = '\u3000-〿㐀-䶿一-鿿\uff00-\uffef'
_CJK_SPACE_RE = re.compile(f'(?<=[{_CJK_RANGE}])\\s+|\\s+(?=[{_CJK_RANGE}])')

def _normalize(s: str) -> str:
    s = _LINE_PREFIX_RE.sub('', s)
    s = _ELLIPSIS_RE.sub('', s)
    s = _BR_RE.sub('', s)
    s = s.replace('**', '').replace('\u3000', ' ')
    s = ' '.join(s.split())
    return _CJK_SPACE_RE.sub('', s)
import math
_EVIDENCE_COVERAGE = 0.6

def _covers_quote(quote: str, haystack: str) -> bool:
    n = len(quote)
    if n == 0:
        return False
    L = math.ceil(n * _EVIDENCE_COVERAGE)
    for i in range(0, n - L + 1):
        if quote[i:i + L] in haystack:
            return True
    return False
_VERIFIED_RUNS_LEDGER = ('runtime', 'logs', 'verified_runs.jsonl')
_VERIFIED_RUN_SNAPSHOT: ContextVar[dict | None] = ContextVar('footprint_verified_run_snapshot', default=None)

@contextmanager
def verified_run_snapshot(record: dict):
    token = _VERIFIED_RUN_SNAPSHOT.set(dict(record))
    try:
        yield
    finally:
        _VERIFIED_RUN_SNAPSHOT.reset(token)

def _record_contains_command(record: dict, cmd: str) -> bool:
    cmds = [str(item).strip() for item in record.get('apv_cmds') or []]
    body = re.split('[<\\[{]', cmd)[0].strip()
    return any((item == cmd or (body and item.startswith(body)) for item in cmds))

def _find_verified_run_record(aid: str, run_ts, *, require_pass: bool=True) -> dict | None:
    ledger = _project_root().joinpath(*_VERIFIED_RUNS_LEDGER)
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, validate_json_budget
        try:
            payload = read_regular_nofollow(ledger, error_type=OSError, invalid_message='verified-run ledger path is invalid', directory_message='verified-run ledger directory is unsafe', open_message='verified-run ledger is unavailable', bounds_message='verified-run ledger is not regular or too large', changed_message='verified-run ledger changed while being read', max_bytes=32 * 1024 * 1024, require_current_uid=True, preserve_missing=True)
        except FileNotFoundError:
            return None
        lines = payload.decode('utf-8').splitlines()
        records: list[dict] = []
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                encoded = line.encode('utf-8')
                if len(encoded) > 1024 * 1024:
                    return None
                validate_json_budget(encoded, error_type=ValueError, message='verified-run record exceeds structural budget')
                rec = json.loads(line)
            except Exception:
                if index == len(lines) - 1:
                    break
                return None
            if not isinstance(rec, dict):
                return None
            records.append(rec)
        for rec in records:
            if str(rec.get('autoid')) == aid and abs(float(rec.get('run_ts', -1)) - float(run_ts)) < 1e-06 and (not require_pass or str(rec.get('verdict')) == 'pass'):
                return rec
    except (OSError, UnicodeError, TypeError, ValueError):
        return None
    return None

def _device_evidence_supports(fact) -> bool:
    import os as _os
    if (_os.environ.get('IST_WRITEBACK_DEVICE_AUTHORITY') or '1').strip().lower() in ('0', 'false', 'no'):
        return False
    dev = getattr(fact, 'device_evidence', None) or {}
    aid = str(dev.get('autoid') or '').strip()
    run_ts = dev.get('run_ts')
    cmd = (getattr(fact, 'cli_syntax', '') or getattr(fact, 'content', '') or '').strip()
    if not aid or run_ts is None or (not cmd):
        return False
    sealed = _VERIFIED_RUN_SNAPSHOT.get()
    if sealed is not None:
        try:
            return bool(str(sealed.get('autoid') or '') == aid and str(sealed.get('verdict') or '') == 'pass' and (abs(float(sealed.get('run_ts')) - float(run_ts)) < 1e-06) and (not dev.get('build') or str(sealed.get('build') or '') == str(dev.get('build'))) and (re.fullmatch('[0-9a-f]{64}', str(sealed.get('xlsx_sha256') or '')) is not None) and _record_contains_command(sealed, cmd))
        except (TypeError, ValueError, OverflowError):
            return False
    rec = _find_verified_run_record(aid, run_ts, require_pass=True)
    return bool(rec is not None and _record_contains_command(rec, cmd))

def _behavior_run_identity_supports(fact) -> bool:
    if getattr(fact, 'fact_kind', '') != 'behavior':
        return False
    import os as _os
    if (_os.environ.get('IST_WRITEBACK_DEVICE_AUTHORITY') or '1').strip().lower() in ('0', 'false', 'no'):
        return False
    dev = getattr(fact, 'device_evidence', None) or {}
    aid = str(dev.get('autoid') or '').strip()
    run_ts = dev.get('run_ts')
    run_id = str(dev.get('run_id') or '').strip()
    echo = str(dev.get('echo_sha256') or '').strip()
    cmd = (getattr(fact, 'cli_syntax', '') or getattr(fact, 'content', '') or '').strip()
    if not aid or run_ts is None or (not run_id) or (not cmd):
        return False
    if re.fullmatch('[0-9a-f]{64}', echo) is None:
        return False
    rec = _find_verified_run_record(aid, run_ts, require_pass=False)
    return bool(rec is not None and _record_contains_command(rec, cmd))

def _evidence_supports(fact) -> bool:
    if getattr(fact, 'device_evidence', None):
        if (getattr(fact, 'validity', '') or '').strip() == 'uncertain':
            dev = fact.device_evidence or {}
            cmd = (getattr(fact, 'cli_syntax', '') or getattr(fact, 'content', '') or '').strip()
            return bool(str(dev.get('autoid') or '').strip() and cmd)
        if _device_evidence_supports(fact):
            return True
        if _behavior_run_identity_supports(fact):
            return True
        return False
    if not fact.evidence_quote or not fact.evidence_file:
        return False
    path = _resolve_evidence_path(fact.evidence_file)
    if path is None:
        return False
    trusted = _evidence_trusted_root(path)
    if trusted is None:
        return False
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
        payload = read_regular_nofollow(path, error_type=OSError, invalid_message='manual evidence path is invalid', directory_message='manual evidence directory is unsafe', open_message='manual evidence file is unavailable', bounds_message='manual evidence file is not regular or too large', changed_message='manual evidence changed while being read', max_bytes=32 * 1024 * 1024, trusted_root=trusted)
        haystack = payload.decode('utf-8', errors='ignore')
    except OSError:
        return False
    haystack_norm = _normalize(haystack)
    quote = _normalize(fact.evidence_quote)
    if quote and (quote in haystack_norm or _covers_quote(quote, haystack_norm)):
        return True
    if getattr(fact, 'fact_kind', '') == 'cli_command':
        cmd = (getattr(fact, 'cli_syntax', '') or '').strip()
        body = re.split('[<\\[{]', cmd)[0].strip()
        if body and _normalize(f'**{body}**') in haystack_norm:
            return True
    return False

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')

def _update_meta(fp: dict, source_thread: str, *, count_verified: bool=True) -> None:
    meta = fp.setdefault('footprint_meta', {})
    if not meta.get('created_at'):
        meta['created_at'] = _now_iso()
    if count_verified:
        meta['verified_count'] = meta.get('verified_count', 0) + 1
    threads = meta.setdefault('source_threads', [])
    if source_thread and source_thread not in threads:
        threads.append(source_thread)
        if len(threads) > 10:
            threads[:] = threads[-10:]

def _evidence(fact) -> dict:
    ev: dict = {}
    if fact.evidence_file:
        ev['source_file'] = fact.evidence_file
    if fact.evidence_quote:
        ev['quoted_text'] = fact.evidence_quote
    _raw = (getattr(fact, 'raw_invocation', '') or '').strip()
    if _raw and _raw != (fact.cli_syntax or '').strip():
        ev['raw_invocation'] = _raw
    dev = getattr(fact, 'device_evidence', None) or {}
    if dev.get('autoid'):
        run: dict = {'autoid': str(dev['autoid'])}
        if dev.get('run_ts'):
            run['run_ts'] = dev['run_ts']
        if dev.get('build'):
            run['build'] = str(dev['build'])
        if dev.get('run_id'):
            run['run_id'] = str(dev['run_id'])
        if dev.get('echo_sha256'):
            run['echo_sha256'] = str(dev['echo_sha256'])
        ev['device_run'] = run
    return ev

def _merge_parameters(existing: list[dict], incoming: list[dict]) -> bool:
    changed = False
    by_name = {p.get('name'): p for p in existing if p.get('name')}
    for inc in incoming:
        name = inc.get('name')
        if not name:
            continue
        if name not in by_name:
            existing.append(inc)
            by_name[name] = inc
            changed = True
            continue
        cur = by_name[name]
        for k, v in inc.items():
            if k == 'name':
                continue
            if v not in (None, '') and (not cur.get(k)):
                cur[k] = v
                changed = True
    return changed
_PLACEHOLDER_RE = re.compile('[<\\[{]')
_MANUAL_VERSION_RES = (re.compile('(?:^|/)manual_(\\d+(?:\\.\\d+)*)'), re.compile('(?:^|/)manual/(\\d+(?:\\.\\d+)*)(?:/|$)'))

def _derive_valid_for(fact) -> list[str]:
    out: list[str] = []
    for v in getattr(fact, 'valid_for', None) or []:
        v = str(v).strip()
        if v and v not in out:
            out.append(v)
    src = (getattr(fact, 'evidence_file', '') or '').strip()
    if src:
        for rx in _MANUAL_VERSION_RES:
            m = rx.search(src)
            if m:
                if m.group(1) not in out:
                    out.append(m.group(1))
                break
    dev = getattr(fact, 'device_evidence', None) or {}
    build = str(dev.get('build') or '').strip()
    if build and build not in out:
        out.append(build)
    return out

def _entry_valid_for(entry: dict) -> set:
    return {str(v).strip() for v in entry.get('valid_for') or [] if str(v).strip()}

def _apply_temporal_fields(entry: dict, fact, valid_for: list[str]) -> None:
    if valid_for:
        entry['valid_for'] = list(valid_for)
    superseded_by = (getattr(fact, 'superseded_by', '') or '').strip()
    if superseded_by:
        entry['superseded_by'] = superseded_by

def command_words(cmd: str) -> list[str]:
    words: list[str] = []
    for tok in _PLACEHOLDER_RE.split(str(cmd or ''))[0].split():
        t = tok.strip().rstrip(',')
        if not t or not t.replace('-', '').isalpha():
            break
        words.append(t)
    return words

def _attach_device_run(existing: dict, fact) -> str:
    ev = existing.setdefault('evidence', {})
    new_ev = _evidence(fact)
    if not new_ev.get('device_run'):
        return 'skip'
    ev['device_run'] = new_ev['device_run']
    if new_ev.get('raw_invocation'):
        ev['raw_invocation'] = new_ev['raw_invocation']
    return 'update'
_DRIFT_CAP = 20

def _record_drift(fp: dict, kind: str, detail: dict) -> None:
    observations = fp.setdefault('drift_observations', [])
    dedup_key = str(detail.get('catalog_head') or detail.get('command') or '')
    for existing in observations:
        if existing.get('kind') == kind and str(existing.get('catalog_head') or existing.get('command') or '') == dedup_key:
            existing['at'] = _now_iso()
            return
    entry = {'kind': kind, 'at': _now_iso()}
    entry.update(detail)
    observations.append(entry)
    if len(observations) > _DRIFT_CAP:
        del observations[:len(observations) - _DRIFT_CAP]

def _append_catalog_command(fp: dict, fact, commands: list) -> str:
    head = (getattr(fact, 'catalog_head', '') or '').strip()
    ident = {str(k): str(v) for k, v in (getattr(fact, 'catalog_identity', None) or {}).items() if str(v or '').strip()}
    reject = _catalog_head_write_reject_reason(head, ident)
    if reject:
        _record_drift(fp, 'catalog_head_rejected', {'catalog_head': head, 'reason': reject, 'catalog': ident})
        return 'reject'
    for existing in commands:
        if (existing.get('catalog_head') or '').strip() != head:
            continue
        old_sha = str((existing.get('catalog') or {}).get('sha256') or '')
        new_sha = str(ident.get('sha256') or '')
        if old_sha == new_sha:
            if (getattr(fact, 'device_evidence', None) or {}).get('autoid'):
                return _attach_device_run(existing, fact)
            return 'skip'
        _record_drift(fp, 'catalog_ref_updated', {'catalog_head': head, 'previous': existing.get('catalog') or {}, 'current': ident})
        existing['catalog'] = ident
        if fact.evidence_file or fact.evidence_quote:
            existing['evidence'] = _evidence(fact)
        _apply_temporal_fields(entry=existing, fact=fact, valid_for=_derive_valid_for(fact))
        return 'update'
    entry = {'fact_key': fact.fact_key, 'catalog_head': head, 'catalog': ident, 'evidence': _evidence(fact)}
    _apply_temporal_fields(entry, fact, _derive_valid_for(fact))
    commands.append(entry)
    return 'append'

def _catalog_head_write_reject_reason(head: str, ident: dict) -> str | None:
    if not head:
        return 'empty_catalog_head'
    version = str(ident.get('version') or '').strip()
    family = str(ident.get('family') or '').strip()
    if not version or not family:
        return 'catalog_identity_incomplete'
    try:
        from cex_core.engine.kms.manual_catalog_store import load_coupled_catalog
        catalog, verdict = load_coupled_catalog(version, family)
    except Exception:
        logger.exception('catalog_head 写侧校验失败: %s/%s', version, family)
        return 'catalog_lookup_failed'
    if catalog is None or str(verdict.get('status') or '') != 'ok':
        return 'catalog_not_in_effect'
    for signature in catalog.get('signatures') or []:
        if not isinstance(signature, dict):
            continue
        tokens = signature.get('head_tokens') or []
        if ' '.join((str(t) for t in tokens if str(t))).strip() == head:
            return None
    return 'catalog_head_absent'

def _append_cli_command(fp: dict, fact) -> str:
    commands = fp.setdefault('cli', {}).setdefault('commands', [])
    if (getattr(fact, 'catalog_head', '') or '').strip():
        return _append_catalog_command(fp, fact, commands)
    syntax = fact.cli_syntax.strip()
    valid_for = _derive_valid_for(fact)
    vf_key = set(valid_for)
    for existing in commands:
        if existing.get('command', '').strip() == syntax and _entry_valid_for(existing) == vf_key:
            if fact.parameters:
                changed = _merge_parameters(existing.setdefault('parameters', []), fact.parameters)
                return 'append' if changed else 'skip'
            return 'skip'
    is_device_verbatim = bool((getattr(fact, 'device_evidence', None) or {}).get('autoid'))
    if is_device_verbatim:
        words = command_words(syntax)
        if words:
            targets = [e for e in commands if (e.get('evidence') or {}).get('source_file') and command_words(e.get('command', '')) == words]
            targets += [e for e in commands if (e.get('catalog_head') or '').strip() and catalog_head_tokens_clean(str(e['catalog_head']).split()) == words]
            if len(targets) == 1:
                return _attach_device_run(targets[0], fact)
            if not targets:
                cat_heads = [str(e['catalog_head']).strip() for e in commands if (e.get('catalog_head') or '').strip()]
                if cat_heads:
                    _record_drift(fp, 'device_form_not_in_catalog', {'command': syntax, 'catalog_heads': cat_heads[:8]})
    entry = {'fact_key': fact.fact_key, 'command': fact.cli_syntax, 'evidence': _evidence(fact)}
    _apply_temporal_fields(entry, fact, valid_for)
    if is_device_verbatim:
        entry['syntax_provenance'] = 'device_run_verbatim'
    if fact.parameters:
        entry['parameters'] = fact.parameters
    commands.append(entry)
    return 'append'

def _append_decision_rule(fp: dict, fact) -> str:
    rules = fp.setdefault('decision_rules', [])
    for existing in rules:
        if existing.get('fact_key') == fact.fact_key:
            return 'skip'
    entry = {'fact_key': fact.fact_key, 'condition': fact.condition, 'decision': fact.decision, 'evidence': _evidence(fact)}
    _apply_temporal_fields(entry, fact, _derive_valid_for(fact))
    rules.append(entry)
    return 'append'

def _append_behavior(fp: dict, fact) -> str:
    behaviors = fp.setdefault('behaviors', [])
    validity = (getattr(fact, 'validity', '') or 'verified').strip() or 'verified'
    observed_under = (getattr(fact, 'observed_under', '') or '').strip()
    for existing in behaviors:
        if existing.get('fact_key') == fact.fact_key:
            if existing.get('validity') == 'uncertain' and validity == 'verified':
                existing['content'] = fact.content or existing.get('content', '')
                existing['evidence'] = _evidence(fact)
                existing['validity'] = 'verified'
                if observed_under:
                    existing['observed_under'] = observed_under
                try:
                    from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
                    emit_signal('upgraded_verified', fact.fact_key, source='merger._append_behavior', autoid=str((fact.device_evidence or {}).get('autoid') or ''))
                except Exception:
                    pass
                return 'update'
            return 'skip'
    entry = {'fact_key': fact.fact_key, 'content': fact.content, 'evidence': _evidence(fact)}
    _apply_temporal_fields(entry, fact, _derive_valid_for(fact))
    if validity != 'verified':
        entry['validity'] = validity
    if observed_under:
        entry['observed_under'] = observed_under
    behaviors.append(entry)
    return 'append'

def _append_known_issue(fp: dict, fact) -> str:
    issues = fp.setdefault('known_issues', [])
    for existing in issues:
        if existing.get('issue_id') == fact.issue_id:
            updated = False
            if fact.issue_title and (not existing.get('title')):
                existing['title'] = fact.issue_title
                updated = True
            if fact.affected_versions:
                merged = sorted(set(existing.get('affected_versions', [])) | set(fact.affected_versions))
                if merged != existing.get('affected_versions'):
                    existing['affected_versions'] = merged
                    updated = True
            return 'update' if updated else 'skip'
    entry: dict[str, Any] = {'issue_id': fact.issue_id}
    if fact.issue_title:
        entry['title'] = fact.issue_title
    if fact.affected_versions:
        entry['affected_versions'] = sorted(set(fact.affected_versions))
        if fp.get('level') == 'leaf':
            vs = fp.setdefault('version_scope', {})
            cur = set(vs.get('product_versions', []))
            cur.update(fact.affected_versions)
            vs['product_versions'] = sorted(cur)
    issues.append(entry)
    return 'append'

def _distinct_observation_contexts(fp: dict) -> set:
    out = set()
    for e in (fp.get('decision_rules') or []) + (fp.get('behaviors') or []):
        if isinstance(e, dict):
            ou = (e.get('observed_under') or '').strip()
            if ou:
                out.add(ou)
    return out
_DISPATCH = {'cli_command': _append_cli_command, 'decision_rule': _append_decision_rule, 'behavior': _append_behavior, 'known_issue': _append_known_issue}

def merge_fact(routed: RoutedFact, footprint_dir: Path) -> MergeResult:
    fact = routed.fact
    from cex_core.engine.case_compiler._sealed_io import lexical_absolute, lexical_path_inside_root
    root = lexical_absolute(footprint_dir)
    try:
        target_path = lexical_path_inside_root(routed.target_file, root, error_type=FootprintWriteError, traversal_message='path escapes footprint dir', outside_message='path escapes footprint dir')
        if target_path.suffix.lower() != '.json' or target_path.name.startswith('.'):
            raise FootprintWriteError('footprint target must be a public JSON node')
        relative_parts = target_path.relative_to(root).parts
        if len(relative_parts) != 2:
            raise FootprintWriteError('footprint target must be one node directory plus one JSON file')
    except FootprintWriteError as exc:
        return MergeResult(action='skip', target_file=routed.target_file, detail=str(exc))
    if fact.fact_kind not in LEVEL_KINDS.get(routed.level, set()):
        return MergeResult(action='skip', target_file=routed.target_file, detail='kind not allowed at level')
    if fact.fact_kind != 'known_issue' and (not _evidence_supports(fact)):
        return MergeResult(action='skip', target_file=routed.target_file, detail='evidence not found in source file')
    handler = _DISPATCH.get(fact.fact_kind)
    if handler is None:
        return MergeResult(action='skip', target_file=routed.target_file, detail='unknown fact_kind')
    _ctx_before: set = set()
    _ctx_after: set = set()
    try:
        with _locked_footprint_root(root) as root_fd:
            parent_fd = _open_target_directory_at(root_fd, relative_parts[:-1])
            try:
                fp = _read_footprint_at(parent_fd, target_path.name)
                created = fp is None
                if created:
                    fp = TEMPLATE_MAP[routed.level](target_path.stem)
                else:
                    _ctx_before = _distinct_observation_contexts(fp)
                action = handler(fp, fact)
                if action == 'skip':
                    return MergeResult(action='skip', target_file=routed.target_file, detail='empty after handler' if created else 'duplicate')
                _update_meta(fp, fact.source_thread, count_verified=(getattr(fact, 'validity', '') or 'verified') != 'uncertain')
                _write_footprint_at(parent_fd, target_path.name, fp)
                _ctx_after = _distinct_observation_contexts(fp)
                result_action = 'create' if created else action
            finally:
                os.close(parent_fd)
    except (FootprintWriteError, OSError) as exc:
        logger.warning('footprint read/write failed %s: %s', target_path, exc)
        return MergeResult(action='skip', target_file=routed.target_file, detail=str(exc))
    if len(_ctx_before) < 2 <= len(_ctx_after):
        try:
            from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
            emit_signal('observation_group_formed', target_path.stem, source='merger.merge_fact', fact_key=fact.fact_key, contexts=sorted(_ctx_after)[:6])
        except Exception:
            pass
    return MergeResult(action=result_action, target_file=routed.target_file, detail=fact.fact_kind)
