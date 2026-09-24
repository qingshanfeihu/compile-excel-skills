# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/facts.py（sha256 9355591cb06cfeb4）。不在这里手改。
from __future__ import annotations
import enum
import fcntl
import json
import logging
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow, validate_json_budget
from cex_core.engine.ist_core.compile_engine import engine_errors as EE
from cex_core.engine.ist_core.compile_engine import conflict_chain as CC
from cex_core.engine.ist_core.compile_engine.fact_events import FACT_EVENTS, REGISTRY_LOCATION, UnregisteredFactEvent, require_registered, unregistered_fact_events
logger = logging.getLogger(__name__)
_DISCLOSED_UNREGISTERED: set[tuple[str, str]] = set()
CTX_DELIVERY = 'delivery'
CTX_SUBSET = 'subset'
EXECUTION_DISPATCH_EVENTS = {CTX_DELIVERY: 'delivery_dispatch_started', CTX_SUBSET: 'subset_dispatch_started'}
FRAMEWORK_RESULT_DOMAIN = frozenset({'pass', 'fail'})
RESULT_DOMAIN = frozenset({'pass', 'fail', 'broken', 'not_run'})
NO_PROGRESS_K = 3
ATTRIBUTION_TEXT_MAX_CHARS = 8000
FRAMEWORK_RESULT_SCHEMA_SINCE = '内部评审日期（已脱敏）'

def _is_wsl_ntfs() -> bool:
    try:
        if sys.platform == 'win32':
            return False
        from pathlib import Path as _P
        return str(_P.cwd()).startswith('/mnt/')
    except Exception:
        return False
_WSL_NTFS = _is_wsl_ntfs()

def _is_ntfs_path(path: str | Path) -> bool:
    if sys.platform == 'win32':
        return False
    try:
        s = str(path)
        return s.startswith('/mnt/') or (len(s) >= 2 and s[1] == ':')
    except Exception:
        return False

def _check_uid_match(file_uid: int) -> bool:
    if int(file_uid) == os.getuid():
        return True
    return _WSL_NTFS

def _clear_nonblock(file_fd: int) -> None:
    """确认普通文件后去掉 O_NONBLOCK。

    打开时带 NONBLOCK 是为了 FIFO 在 fstat 前不堵死。DrvFS/9p 上这个旗会让
    单次 pread 截在约 64KiB，健康账会被误判成身份漂移。写路径已经在循环里
    消化短 write；读路径同样按 POSIX 短读处理。
    """
    nonblock = getattr(os, 'O_NONBLOCK', 0)
    if not nonblock or not hasattr(fcntl, 'F_GETFL'):
        return
    flags = fcntl.fcntl(file_fd, fcntl.F_GETFL)
    if flags & nonblock:
        fcntl.fcntl(file_fd, fcntl.F_SETFL, flags & ~nonblock)

def _pread_all(file_fd: int, size: int, offset: int=0) -> bytes:
    """从普通文件读满 ``size`` 字节，或读到 EOF。"""
    if size <= 0:
        return b''
    chunks: list[bytes] = []
    got = 0
    while got < size:
        part = os.pread(file_fd, size - got, offset + got)
        if not part:
            break
        chunks.append(part)
        got += len(part)
    return b''.join(chunks)

class FactLedgerCorruptError(RuntimeError):
    pass
_MAX_FACT_LEDGER_BYTES = 512 * 1024 * 1024
_MAX_FACT_LINE_BYTES = 4 * 1024 * 1024

def _ledger_size_error(path: Path, size: int, *, stage: str) -> FactLedgerCorruptError:
    return FactLedgerCorruptError(f'事实流超出大小限制: stage={stage}, path={path}, logical_size_bytes={int(size)}, limit_bytes={_MAX_FACT_LEDGER_BYTES}')

def _decode_fact_line(raw: bytes, path: Path, line_number: int) -> dict:
    if len(raw) > _MAX_FACT_LINE_BYTES:
        raise FactLedgerCorruptError(f'事实流第 {line_number} 行超出大小限制: {path}')
    validate_json_budget(raw, error_type=FactLedgerCorruptError, message=f'事实流第 {line_number} 行超出结构预算: {path}', max_depth=128, max_tokens=500000)

    def reject_duplicate_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise FactLedgerCorruptError(f'事实流第 {line_number} 行包含重复键: {path}')
            value[key] = item
        return value

    def reject_constant(_value: str):
        raise FactLedgerCorruptError(f'事实流第 {line_number} 行包含非有限数: {path}')
    try:
        item = json.loads(raw.decode('utf-8'), object_pairs_hook=reject_duplicate_keys, parse_constant=reject_constant)
    except FactLedgerCorruptError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FactLedgerCorruptError(f'事实流第 {line_number} 行损坏: {path}') from exc
    if not isinstance(item, dict) or not item.get('ev'):
        raise FactLedgerCorruptError(f'事实流第 {line_number} 行不是有效事实: {path}')
    return item

def _disclose_unregistered_events(facts: list[dict], path: Path) -> None:
    """读到没登记的事件名：记名，不丢行。

    闭集在写侧（`append_facts`），这里只披露。读侧硬拒会把冻结语料里的旧事件名
    连同整批历史一起读不出来；而一声不吭就是本条要修的那个静默通过。
    """
    for name in unregistered_fact_events(facts):
        mark = (str(path), name)
        if mark in _DISCLOSED_UNREGISTERED:
            continue
        _DISCLOSED_UNREGISTERED.add(mark)
        logger.warning('事实流含未登记的事件名（照常读出，不丢行）: ev=%s, path=%s, registry=%s', name, path, REGISTRY_LOCATION)

def _decode_facts(payload: bytes, path: Path) -> list[dict]:
    out: list[dict] = []
    for line_number, raw in enumerate(payload.splitlines(), 1):
        if not raw.strip():
            continue
        out.append(_decode_fact_line(raw, path, line_number))
    out = dedup(out)
    _disclose_unregistered_events(out, path)
    return out

def _repair_torn_tail(file_fd: int, path: Path) -> None:
    size = os.fstat(file_fd).st_size
    if not _is_ntfs_path(path) and size > _MAX_FACT_LEDGER_BYTES:
        raise _ledger_size_error(path, size, stage='repair_precheck')
    if size <= 0 or _pread_all(file_fd, 1, size - 1) == b'\n':
        return
    start = max(0, size - _MAX_FACT_LINE_BYTES - 1)
    tail = _pread_all(file_fd, size - start, start)
    last_newline = tail.rfind(b'\n')
    if last_newline < 0 and start > 0:
        raise FactLedgerCorruptError('事实流尾帧超出大小限制，不能安全修复')
    frame_start = start + last_newline + 1
    frame = _pread_all(file_fd, size - frame_start, frame_start)
    try:
        _decode_fact_line(frame, path, 1)
        complete = True
    except FactLedgerCorruptError:
        complete = False
    if complete:
        os.lseek(file_fd, 0, os.SEEK_END)
        os.write(file_fd, b'\n')
    else:
        os.ftruncate(file_fd, frame_start)
    os.fsync(file_fd)

def append_facts(path: Path, facts: list[dict]) -> int:
    require_registered(facts, where=str(path))
    from cex_core.engine.ist_core.compile_engine.routing_closed_sets import stamp_decision_axis
    facts = [stamp_decision_axis(fact) for fact in facts]
    directory_fd = open_directory_nofollow(path.parent, error_type=FactLedgerCorruptError, invalid_message='事实流路径无效', unavailable_message='事实流目录不可安全写入', create_missing=True)
    flags = os.O_RDWR | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
    try:
        from cex_core.engine.case_compiler._sealed_io import open_or_create_regular_at_nofollow
        file_fd = open_or_create_regular_at_nofollow(directory_fd, path.name, flags, mode=384, error_type=FactLedgerCorruptError, unavailable_message='事实流不可安全打开')
    except FactLedgerCorruptError:
        os.close(directory_fd)
        raise
    try:
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (not _check_uid_match(info.st_uid)):
            raise FactLedgerCorruptError('事实流必须是当前用户拥有的单链接普通文件')
        if not _is_ntfs_path(path) and info.st_size > _MAX_FACT_LEDGER_BYTES:
            raise _ledger_size_error(path, info.st_size, stage='open_precheck')
        fcntl.flock(file_fd, fcntl.LOCK_EX)
        locked_info = os.fstat(file_fd)
        path_info = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        if int(path_info.st_dev) != int(locked_info.st_dev) or int(path_info.st_ino) != int(locked_info.st_ino) or (not stat.S_ISREG(locked_info.st_mode)) or (not stat.S_ISREG(path_info.st_mode)) or (int(locked_info.st_nlink) != 1) or (int(path_info.st_nlink) != 1) or (not _check_uid_match(locked_info.st_uid)) or (not _check_uid_match(path_info.st_uid)) or (not _is_ntfs_path(path) and int(locked_info.st_size) > _MAX_FACT_LEDGER_BYTES) or (not _is_ntfs_path(path) and int(path_info.st_size) > _MAX_FACT_LEDGER_BYTES):
            raise FactLedgerCorruptError('事实流在加锁前被替换')
        locked_size = max(int(locked_info.st_size), int(path_info.st_size))
        if not _is_ntfs_path(path) and locked_size > _MAX_FACT_LEDGER_BYTES:
            raise _ledger_size_error(path, locked_size, stage='locked_precheck')
        _repair_torn_tail(file_fd, path)
        repaired_info = os.fstat(file_fd)
        if not stat.S_ISREG(repaired_info.st_mode) or int(repaired_info.st_nlink) != 1 or (not _check_uid_match(repaired_info.st_uid)) or (not _is_ntfs_path(path) and repaired_info.st_size > _MAX_FACT_LEDGER_BYTES):
            raise FactLedgerCorruptError('事实流修复后身份异常')
        if not _is_ntfs_path(path) and repaired_info.st_size > _MAX_FACT_LEDGER_BYTES:
            raise _ledger_size_error(path, repaired_info.st_size, stage='repair_postcheck')
        size = repaired_info.st_size
        payload = _pread_all(file_fd, size)
        if len(payload) != size:
            raise FactLedgerCorruptError(f'事实流短读未拿到完整快照: path={path}, logical_size_bytes={int(size)}, read_bytes={len(payload)}')
        existing = {idem_key(f) for f in _decode_facts(payload, path)}
        written = 0
        for f in facts:
            f = {**f, '_pid': os.getpid()}
            k = idem_key(f)
            if k in existing:
                continue
            encoded = (json.dumps(f, ensure_ascii=False) + '\n').encode('utf-8')
            _decode_fact_line(encoded.rstrip(b'\n'), path, written + 1)
            current_size = os.fstat(file_fd).st_size
            if not _is_ntfs_path(path) and current_size + len(encoded) > _MAX_FACT_LEDGER_BYTES:
                raise FactLedgerCorruptError(f'事实流追加将超出大小限制: path={path}, logical_size_bytes={int(current_size)}, append_bytes={len(encoded)}, limit_bytes={_MAX_FACT_LEDGER_BYTES}')
            view = memoryview(encoded)
            while view:
                count = os.write(file_fd, view)
                if count <= 0:
                    raise FactLedgerCorruptError('事实流发生短写')
                view = view[count:]
            os.fsync(file_fd)
            existing.add(k)
            written += 1
        return written
    finally:
        os.close(file_fd)
        os.close(directory_fd)

def _read_facts_under_shared_lock(path: Path) -> bytes:
    try:
        directory_fd = open_directory_nofollow(path.parent, error_type=FactLedgerCorruptError, invalid_message='事实流路径无效', unavailable_message='事实流目录不可安全读取', preserve_missing=True)
    except FileNotFoundError:
        return b''
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        try:
            file_fd = os.open(path.name, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return b''
        except OSError as exc:
            raise FactLedgerCorruptError('事实流不可读') from exc
        try:
            fcntl.flock(file_fd, fcntl.LOCK_SH)
            before = os.fstat(file_fd)
            try:
                named = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise FactLedgerCorruptError('事实流在共享锁内不可用') from exc
            if int(before.st_dev) != int(named.st_dev) or int(before.st_ino) != int(named.st_ino) or (not stat.S_ISREG(before.st_mode)) or (not stat.S_ISREG(named.st_mode)) or (int(before.st_nlink) != 1) or (int(named.st_nlink) != 1) or (not _check_uid_match(before.st_uid)) or (not _check_uid_match(named.st_uid)):
                raise FactLedgerCorruptError('事实流必须是未替换的单链接普通文件')
            size = int(before.st_size)
            if not _is_ntfs_path(path) and size > _MAX_FACT_LEDGER_BYTES:
                raise _ledger_size_error(path, size, stage='shared_read_precheck')
            _clear_nonblock(file_fd)
            payload = _pread_all(file_fd, size)
            after = os.fstat(file_fd)
            if int(after.st_dev) != int(before.st_dev) or int(after.st_ino) != int(before.st_ino) or int(after.st_size) != size or (int(after.st_mtime_ns) != int(before.st_mtime_ns)):
                raise FactLedgerCorruptError('事实流共享锁快照身份漂移')
            if len(payload) != size:
                raise FactLedgerCorruptError(f'事实流短读未拿到完整快照: path={path}, logical_size_bytes={int(size)}, read_bytes={len(payload)}')
            return payload
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)

def load_facts(path: Path) -> list[dict]:
    payload = _read_facts_under_shared_lock(Path(path))
    return _decode_facts(payload, path)

def is_suspend_placeholder_decision(f: dict) -> bool:
    return f.get('ev') == 'decision' and str(f.get('token') or '') == 'suspend'

def idem_key(f: dict) -> tuple:
    ev, aid = (str(f.get('ev')), str(f.get('aid', '')))
    if ev == 'attribution_protocol_error':
        dispatch_id = str(f.get('dispatch_id') or '')
        if dispatch_id:
            return (ev, aid, dispatch_id, str(f.get('reason_code') or ''))
    if ev == 'verdict':
        return (ev, aid, str(f.get('run_id')))
    if ev == 'authored':
        return (ev, aid, int(f.get('round') or 0))
    if ev == 'attribution':
        rid = str(f.get('run_id') or '')
        key = (ev, aid, rid) if rid else (ev, aid, int(f.get('round') or 0))
        return (*key, 'structural_interference') if structural_interference_attribution(f) else key
    if ev == 'escalated':
        rid = str(f.get('run_id') or '')
        if rid:
            return (ev, aid, rid)
    if ev == 'decision':
        key = (ev, aid, str(f.get('question_id') or f.get('question', ''))[:120])
        if CC.is_direct_abandon_decision(f):
            return key + ('direct_abandon',)
        if is_suspend_placeholder_decision(f):
            return key + ('suspend',)
        return key
    if ev in ('writeback', 'rollback'):
        return (ev, aid, str(f.get('voucher_run') or f.get('of', '')), str(f.get('reason', '')))
    if ev == 'metrics_scope':
        return (ev, str(f.get('schema') or ''), int(f.get('run_seq') or 0))
    if ev in ('gate_rejected', 'gate_disabled', 'ir_gap'):
        occurrence_id = str(f.get('occurrence_id') or '')
        if occurrence_id:
            return (ev, aid, occurrence_id)
    if ev == 'worker_device_attempt':
        rid = str(f.get('run_id') or '')
        if rid:
            return (ev, aid, rid)
    if ev == 'probe_evidence':
        probe_id = str(f.get('probe_id') or '')
        if probe_id:
            return (ev, aid, probe_id)
    if ev == 'llm_usage':
        usage_id = str(f.get('usage_id') or '')
        if usage_id:
            return (ev, aid, usage_id)
    if ev == 'worker_outcome':
        rid = str(f.get('run_id') or '')
        artifact = str(f.get('artifact') or '')
        if rid or artifact:
            return (ev, aid, str(f.get('outcome') or ''), rid, artifact, int(f.get('round') or 0))
    if ev == 'worker_loop_outcome':
        dispatch_id = str(f.get('dispatch_id') or '')
        if dispatch_id:
            return (ev, aid, dispatch_id)
    if ev == 'compile_attempt_resolved':
        attempt_id = str(f.get('compile_attempt_id') or '')
        if attempt_id:
            return (ev, aid, attempt_id)
    if ev == 'mechanical_case_submission_rejected':
        occurrence_id = str(f.get('occurrence_id') or '')
        if occurrence_id:
            return (ev, aid, occurrence_id)
    if ev == 'worker_claim':
        claim_id = str(f.get('claim_id') or '')
        if claim_id:
            return (ev, aid, claim_id)
    if ev == 'no_progress_decision':
        decision_id = str(f.get('decision_id') or '')
        if decision_id:
            return (ev, aid, decision_id)
    if ev == 'compilation_assessment':
        assessment_id = str(f.get('assessment_id') or '')
        if assessment_id:
            return (ev, aid, assessment_id)
    if ev == 'case_terminal_outcome':
        terminal_id = str(f.get('terminal_id') or '')
        if terminal_id:
            return (ev, aid, terminal_id)
    if ev == 'compilability':
        revision = str(f.get('revision') or f.get('decision_id') or f.get('artifact') or f.get('round') or '')
        if revision:
            return (ev, aid, revision, str(f.get('status') or f.get('compilability') or ''), f.get('compilable'))
    if ev in ('pass_audit', 'assertion_strength_audit'):
        artifact = str(f.get('artifact') or '')
        revision = str(f.get('audit_revision') or f.get('run_id') or '')
        detector = str(f.get('detector') or '')
        if artifact or revision or detector:
            return (ev, aid, artifact, revision, detector)
    core = {k: v for k, v in f.items() if not str(k).startswith('_') and k != 'decision_axis'}
    return (ev, aid, json.dumps(core, sort_keys=True, ensure_ascii=False))

def dedup(facts: list[dict]) -> list[dict]:
    seen: set = set()
    out: list[dict] = []
    for f in facts:
        k = idem_key(f)
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out

def this_run_slice(facts: list[dict]) -> list[dict]:
    idx = max((i for i, f in enumerate(facts) if f.get('ev') == 'run_start'), default=-1)
    return facts[idx + 1:] if idx >= 0 else facts

def volume_sequence(facts: list[dict]) -> int:
    """全账本 merged.run_id 的最大尾号。两条口径的由来见 03 章 §9 第 1 条。"""
    seqs = [int(tail) for tail in (str(f.get('run_id') or '').rsplit(':', 1)[-1] for f in facts if f.get('ev') == 'merged') if tail.isdigit()]
    return max(seqs, default=0)

def _facts_of(facts: list[dict], aid: str, ev: str | None=None) -> list[dict]:
    if ev in {'verdict', 'attribution', 'diagnosis', 'case_terminal_outcome'}:
        from cex_core.engine.ist_core.compile_engine.engine_quarantine import effective_case_facts
        facts = effective_case_facts(facts, aid)
    return [f for f in facts if str(f.get('aid')) == aid and (ev is None or f.get('ev') == ev)]

def latest_verdict(facts: list[dict], aid: str, ctx: str | None=None, artifact: str | None=None) -> dict | None:
    vs = [f for f in _facts_of(facts, aid, 'verdict') if (ctx is None or f.get('ctx') == ctx) and (artifact is None or str(f.get('artifact')) == artifact)]
    return vs[-1] if vs else None
_NON_PASS_VERDICT_RESULTS = ('fail', 'broken', 'not_run')

def delivery_verdict_bound_to_volume(facts: list[dict], aid: str, current_volume: str, current_volume_artifact_sha256: str='') -> dict | None:
    v = latest_verdict(facts, aid, ctx=CTX_DELIVERY)
    if not v:
        return None
    current_sha = str(current_volume_artifact_sha256 or '').lower()
    verdict_sha = str(v.get('volume_artifact_sha256') or '').lower()
    if not (re.fullmatch('[0-9a-f]{64}', current_sha) and re.fullmatch('[0-9a-f]{64}', verdict_sha) and (verdict_sha == current_sha)):
        return None
    if str(v.get('volume')) != str(current_volume):
        return None
    return v

def deliverable(facts: list[dict], aid: str, current_artifact: str, current_volume: str, current_volume_artifact_sha256: str='') -> bool:
    v = delivery_verdict_bound_to_volume(facts, aid, current_volume, current_volume_artifact_sha256)
    return bool(v and v.get('result') == 'pass' and (str(v.get('artifact')) == current_artifact))

def volume_resident_accounted(facts: list[dict], aid: str, current_volume: str, current_volume_artifact_sha256: str='') -> bool:
    v = delivery_verdict_bound_to_volume(facts, aid, current_volume, current_volume_artifact_sha256)
    return bool(v) and str(v.get('result') or '') in _NON_PASS_VERDICT_RESULTS

def subset_verified(facts: list[dict], aid: str, current_artifact: str) -> bool:
    v = latest_verdict(facts, aid, artifact=current_artifact)
    return bool(v and v.get('result') == 'pass')

def _norm_sigs(xs):
    try:
        from cex_core.engine.ist_core.tools.device.batch_tools import normalize_fail_signature as _n
    except Exception:

        def _n(s):
            return s
    out: set = set()
    for x in xs or []:
        if isinstance(x, (list, tuple)) and len(x) == 2:
            out.add((str(x[0]), _n(str(x[1]))))
        else:
            out.add(_n(str(x)))
    return out

def sig_key_text(s) -> str:
    if isinstance(s, (list, tuple)) and len(s) == 2:
        return str(s[1])
    return str(s)

def sig_key_texts(raw_sigs) -> list[str]:
    return sorted((sig_key_text(s) for s in _norm_sigs(raw_sigs)), key=str)

def canonical_failure_key(domain: str, value: Any) -> str:
    try:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        payload = str(value)
    return f"{str(domain or 'unknown').strip().lower()}:{payload}"

def _atomic_failure_keys(domain: str, value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set, frozenset)):
        atoms = list(value)
    elif value in (None, ''):
        atoms = []
    else:
        atoms = [value]
    return sorted({canonical_failure_key(domain, atom) for atom in atoms if atom not in (None, '')})

def _history_failure_keys(item: dict, domain: str) -> list[str]:
    keys = item.get('failure_keys')
    if isinstance(keys, (list, tuple, set, frozenset)):
        return sorted({str(key) for key in keys if str(key or '')})
    return []

def no_progress_step(history: list[dict] | tuple[dict, ...], *, domain: str, value: Any, revision_sha256: str) -> dict:
    normalized_domain = str(domain or 'unknown').strip().lower()
    current_keys = _atomic_failure_keys(normalized_domain, value)
    revision = str(revision_sha256 or '')
    rows = [{'failure_keys': _history_failure_keys(item, normalized_domain), 'revision_sha256': str(item.get('revision_sha256') or '')} for item in history or () if isinstance(item, dict)]
    rows.append({'failure_keys': current_keys, 'revision_sha256': revision})
    refs_by_key: dict[str, list[str]] = {}
    for key in current_keys:
        revisions: list[str] = []
        for item in reversed(rows):
            if key not in item['failure_keys']:
                break
            candidate = item['revision_sha256']
            if candidate and candidate not in revisions:
                revisions.append(candidate)
        refs_by_key[key] = list(reversed(revisions))
    ranked_keys = sorted(current_keys, key=lambda key: (-len(refs_by_key[key]), key))
    primary_key = ranked_keys[0] if ranked_keys else ''
    primary_refs = refs_by_key.get(primary_key, [])
    streaks = {key: len(refs_by_key[key]) for key in sorted(refs_by_key)}
    stop_keys = sorted((key for key, streak in streaks.items() if streak >= NO_PROGRESS_K))
    return {'domain': normalized_domain, 'failure_key': primary_key, 'failure_keys': current_keys, 'streak': len(primary_refs), 'streaks': streaks, 'threshold': NO_PROGRESS_K, 'revision_refs': primary_refs, 'revision_refs_by_key': refs_by_key, 'stop_keys': stop_keys, 'stop': bool(stop_keys), 'history': rows}

def signature_freeze_step(prev_sigs, cur_sigs, seen=(), accumulated=()) -> tuple[bool, frozenset, frozenset]:
    prev, cur = (frozenset(prev_sigs or ()), frozenset(cur_sigs or ()))
    seen, acc = (frozenset(seen or ()), frozenset(accumulated or ()))
    seen = seen | prev
    recurring = cur & seen
    new_seen = seen | cur
    new_acc = acc | recurring
    if not cur:
        return (False, new_seen, new_acc)
    if cur < prev:
        return (False, new_seen, new_acc)
    return (cur <= new_acc, new_seen, new_acc)

def frozen_signatures_and_status(fail_sig_sequence) -> tuple[bool, frozenset]:
    seq = [frozenset(s or ()) for s in fail_sig_sequence]
    if not seq:
        return (False, frozenset())
    seen: frozenset = seq[0]
    acc: frozenset = frozenset()
    is_frozen = False
    for i in range(1, len(seq)):
        is_frozen, seen, acc = signature_freeze_step(seq[i - 1], seq[i], seen, acc)
    return (is_frozen, acc)

def frozen(facts: list[dict], aid: str, current_artifact: str | None=None) -> bool:
    vs = _facts_of(facts, aid, 'verdict')
    if current_artifact is not None:
        vs = [v for v in vs if str(v.get('artifact')) == current_artifact]
    vs = [v for v in vs if v.get('result') in ('pass', 'fail')]
    fail_run: list[dict] = []
    for v in reversed(vs):
        if v.get('result') != 'fail':
            break
        fail_run.append(v)
    fail_run.reverse()
    if len(fail_run) < 2:
        return False
    seq = [_norm_sigs(v.get('signatures')) for v in fail_run]
    is_frozen, _ = frozen_signatures_and_status(seq)
    return is_frozen

def transient_recur(facts: list[dict], aid: str) -> bool:
    fs = _facts_of(facts, aid)
    last_transient_i = None
    for i, f in enumerate(fs):
        if f.get('ev') == 'attribution' and f.get('layer') == 'transient':
            last_transient_i = i
    if last_transient_i is None:
        return False
    return any((f.get('ev') == 'verdict' and f.get('result') == 'fail' for f in fs[last_transient_i + 1:]))

def contradictions(facts: list[dict], aid: str, artifact: str | None=None) -> int:
    n = 0
    passed_artifacts: set[str] = set()
    for f in _facts_of(facts, aid, 'verdict'):
        art = str(f.get('artifact'))
        if artifact is not None and art != artifact:
            continue
        if f.get('result') == 'pass':
            passed_artifacts.add(art)
        elif f.get('ctx') == CTX_DELIVERY and f.get('result') == 'fail':
            if art in passed_artifacts:
                n += 1
    return n

def recovered(facts: list[dict], aid: str, artifact: str | None=None) -> int:
    n = 0
    failed_artifacts: set[str] = set()
    for f in _facts_of(facts, aid, 'verdict'):
        art = str(f.get('artifact'))
        if artifact is not None and art != artifact:
            continue
        if f.get('result') == 'fail':
            failed_artifacts.add(art)
        elif f.get('result') == 'pass' and art in failed_artifacts:
            n += 1
    return n

def rounds_used(facts: list[dict], aid: str) -> int:
    return len(_facts_of(facts, aid, 'authored'))

def dispatch_rounds_used(facts: list[dict], aid: str) -> int:
    base = max((row.get('last_ordinal', 0) for row in _facts_of(facts, aid, 'prior_dispatch_sequence') if type(row.get('last_ordinal')) is int and row['last_ordinal'] >= 0), default=0)
    return base + len(_facts_of(facts, aid, 'worker_dispatch_started'))

def next_authoring_attempt(facts: list[dict], aid: str, *, dispatch_reserved: bool=False) -> int:
    from cex_core.engine.ist_core.compile_engine.authoring_evidence import uses_new_policy, effective_budget_used
    if uses_new_policy(facts):
        return effective_budget_used(facts, aid, raw_count=0) + 1
    return max(rounds_used(facts, aid) + 1, dispatch_rounds_used(facts, aid) + (0 if dispatch_reserved else 1))
EMIT_REJECT_PRODUCER = 'producer'
EMIT_REJECT_LEDGER = 'ledger'

def pending_emit_aids(facts: list[dict]) -> set[str]:
    pending: set[str] = set()
    for fact in this_run_slice(facts):
        aid = str(fact.get('aid') or '')
        if not aid:
            continue
        event = fact.get('ev')
        if event == 'composed':
            pending.add(aid)
        elif event in ('authored', 'emit_invalid'):
            pending.discard(aid)
    return pending

def emit_todo_aids(facts: list[dict]) -> set[str]:
    return pending_emit_aids(facts)
AUTHORING_CAUSE_SUBMISSION_REJECTED = 'submission_rejected'
AUTHORING_CAUSE_NO_OUTPUT = 'no_output'
AUTHORING_CAUSE_DEVICE_RESULT_CASE_SIDE = 'device_result_case_side'
AUTHORING_CAUSE_COMPILE_POLICY_EXHAUSTED = 'compile_policy_exhausted'
AUTHORING_CAUSE_WORKER_CLAIM = 'worker_claim_not_compilable'
AUTHORING_CAUSE_API_SIDE = 'api_side'
AUTHORING_CAUSE_BUDGET_GOVERNANCE = 'budget_governance'
AUTHORING_CAUSE_ENGINE_SIDE = 'engine_side'
AUTHORING_CAUSE_ENV = 'environment'
AUTHORING_CAUSE_PRODUCT = 'product'
_AUTHORING_API_SIDE_FORK_FAULTS = frozenset(EE.API_CAUSE_CODES)
AUTHORING_CASE_SIDE_CAUSES = frozenset({AUTHORING_CAUSE_SUBMISSION_REJECTED, AUTHORING_CAUSE_NO_OUTPUT, AUTHORING_CAUSE_DEVICE_RESULT_CASE_SIDE, AUTHORING_CAUSE_COMPILE_POLICY_EXHAUSTED, AUTHORING_CAUSE_WORKER_CLAIM})
_AUTHORING_CASE_SIDE_LAYERS = frozenset({'G', 'E', 'V', 'dispatch'})
_AUTHORING_CASE_SIDE_DISPOSITIONS = frozenset({'reflow', 'frozen'})
_AUTHORING_PRESCRIPTION_DISPOSITIONS = frozenset({'rerun_isolated'})

def authoring_round_causes(facts: list[dict], aid: str) -> list[dict]:
    from cex_core.engine.ist_core.compile_engine.authoring_stops import aborted_dispatch
    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
    out: list[dict] = []

    def _add(fact: dict, cause: str) -> None:
        out.append({'round': fact.get('round'), 'cause': cause, 'case_side': cause in AUTHORING_CASE_SIDE_CAUSES, 'source_event': str(fact.get('ev') or ''), 'source_fact_sha256': _fact_sha256(fact)})
    for fact in _facts_of(facts, aid):
        event = str(fact.get('ev') or '')
        if event == 'compose_rejected':
            _add(fact, AUTHORING_CAUSE_SUBMISSION_REJECTED)
        elif event == 'worker_claim':
            _add(fact, AUTHORING_CAUSE_WORKER_CLAIM)
        elif event == 'escalated':
            if aborted_dispatch(fact):
                continue
            subclass = str(fact.get('subclass') or '')
            fork_fault = str(fact.get('fork_fault') or '')
            if fork_fault in _AUTHORING_API_SIDE_FORK_FAULTS or fact.get('api_error'):
                _add(fact, AUTHORING_CAUSE_API_SIDE)
            elif fork_fault == 'FUTILITY_BLOCKED' or str(fact.get('engine_budget_exhausted') or ''):
                _add(fact, AUTHORING_CAUSE_BUDGET_GOVERNANCE)
            else:
                _add(fact, AUTHORING_CAUSE_NO_OUTPUT if subclass == ESC_NO_OUTPUT else AUTHORING_CAUSE_ENGINE_SIDE)
        elif event == 'attribution':
            layer = str(fact.get('layer') or '')
            disposition = str(fact.get('disposition') or '')
            if layer == 'user':
                continue
            if layer == 'product_defect':
                _add(fact, AUTHORING_CAUSE_PRODUCT)
            elif layer == 'transient' or disposition == 'env_blocked':
                _add(fact, AUTHORING_CAUSE_ENV)
            elif disposition in _AUTHORING_PRESCRIPTION_DISPOSITIONS:
                continue
            elif layer in _AUTHORING_CASE_SIDE_LAYERS and disposition in _AUTHORING_CASE_SIDE_DISPOSITIONS:
                _add(fact, AUTHORING_CAUSE_DEVICE_RESULT_CASE_SIDE)
            else:
                _add(fact, AUTHORING_CAUSE_ENGINE_SIDE)
        elif event == 'worker_loop_outcome':
            outcome = str(fact.get('outcome') or '')
            if outcome == 'compile_exhausted':
                _add(fact, AUTHORING_CAUSE_COMPILE_POLICY_EXHAUSTED)
            elif outcome in ('broken', 'engine_defect'):
                _add(fact, AUTHORING_CAUSE_ENGINE_SIDE)
    return out

def authoring_failure_eligible(facts: list[dict], aid: str) -> bool:
    causes = authoring_round_causes(facts, aid)
    return bool(causes) and all((bool(row.get('case_side')) for row in causes))

def effective_rounds_used(facts: list[dict], aid: str) -> int:
    from cex_core.engine.ist_core.compile_engine.authoring_evidence import effective_budget_used
    return effective_budget_used(facts, aid, max(rounds_used(facts, aid), dispatch_rounds_used(facts, aid)))
ESC_NO_OUTPUT = 'no_output'
ESC_NOT_EXECUTED = 'not_executed'
ESC_NO_LEDGER_CHANNEL = 'no_ledger_channel'
ESC_HARNESS_FAULT = 'harness_fault'
ESC_WORKER_ENVELOPE = 'worker_envelope_invalid'
ESC_VERDICT_UNRECOGNIZED = 'verdict_unrecognized'
ESCALATION_FAMILY_UNDERDETERMINED_CLAIM = 'underdetermined_claim'
ESCALATION_FAMILY_BINDING_UNAVAILABLE = 'binding_unavailable'
ESCALATION_FAMILY_WORKER_PROTOCOL_DRIFT = 'worker_protocol_drift'
ESCALATION_FAMILIES: frozenset[str] = frozenset({ESCALATION_FAMILY_UNDERDETERMINED_CLAIM, ESCALATION_FAMILY_BINDING_UNAVAILABLE, ESCALATION_FAMILY_WORKER_PROTOCOL_DRIFT})
_ESC_LEGACY_PREFIX = (('no output from fork', ESC_NO_OUTPUT), ('case did not execute for', ESC_NOT_EXECUTED), ('worker declared underdetermined', ESC_NO_LEDGER_CHANNEL))

def _fact_subclass(f: dict) -> str:
    sub = str(f.get('subclass') or '').strip()
    if sub:
        return sub
    reason = str(f.get('reason') or '')
    for prefix, kind in _ESC_LEGACY_PREFIX:
        if prefix in reason:
            return kind
    return ''

def _fact_esc_family(f: dict) -> str:
    family = str(f.get('esc_family') or '').strip()
    if family in ESCALATION_FAMILIES:
        return family
    if not family and _fact_subclass(f) == ESC_NO_LEDGER_CHANNEL:
        return ESCALATION_FAMILY_UNDERDETERMINED_CLAIM
    return ''

def escalated_family(facts: list[dict], aid: str) -> str:
    esc = _facts_of(facts, aid, 'escalated')
    return _fact_esc_family(esc[-1]) if esc else ''
_WORKER_SAID_MARKER = 'worker said: '

def underdetermined_declaration(fact: dict) -> str:
    declared = str(fact.get('worker_declaration') or '').strip()
    if declared:
        return declared
    reason = str(fact.get('reason') or '')
    marker = reason.find(_WORKER_SAID_MARKER)
    if marker < 0:
        return ''
    return reason[marker + len(_WORKER_SAID_MARKER):].strip()

def surviving_underdetermined_declaration(facts: list[dict], aid: str) -> dict:
    mine = [f for f in facts if str(f.get('aid')) == aid]
    last_esc = -1
    last_authored = -1
    for index, fact in enumerate(mine):
        if fact.get('ev') == 'escalated':
            last_esc = index
        elif fact.get('ev') == 'authored':
            last_authored = index
    if last_esc < 0 or last_authored > last_esc:
        return {}
    fact = mine[last_esc]
    if _fact_esc_family(fact) != ESCALATION_FAMILY_UNDERDETERMINED_CLAIM:
        return {}
    if not underdetermined_declaration(fact):
        return {}
    return fact

def author_definition_gap_landing_facts(facts: list[dict], aid: str, declaration_fact: dict) -> list[dict]:
    from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
    declaration = underdetermined_declaration(declaration_fact)
    if not declaration:
        return []
    abandon = TC.build_author_definition_gap_abandon_fact(aid=aid, declaration=declaration, declaration_basis='surviving_claim', source_fact=declaration_fact)
    out: list[dict] = []
    mine = [f for f in facts if str(f.get('aid')) == aid]
    released = False
    seen_declaration = False
    for fact in mine:
        if fact is declaration_fact or (fact.get('ev') == 'escalated' and fact.get('run_id') and (fact.get('run_id') == declaration_fact.get('run_id'))):
            seen_declaration = True
            released = False
            continue
        if seen_declaration and fact.get('ev') in ('authored', 'de_escalated'):
            released = True
    if not released:
        out.append({'ev': 'de_escalated', 'aid': aid, 'note': "auto: underdetermined claim survived the engine's recovery attempt — landing it as the disclosed author-definition-gap disposition (2026-08-21 ruling; the verbatim gap list goes into the delivery report)"})
    out.append(abandon)
    return out

def engine_budget_terminal_facts(facts: list[dict], aid: str, new_escalated: dict, budget_kind: str) -> list[dict]:
    from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
    mine = [f for f in facts if str(f.get('aid')) == aid]
    return [{'ev': 'ist_core_defect', 'aid': aid, 'round': effective_rounds_used(mine, aid), 'reason_code': f'engine_budget_exhausted_{budget_kind}', 'terminal_layer': 'engine', 'source_event': 'escalated', 'source_fact_sha256': TC._fact_sha256(TC.canonical_persisted_value(dict(new_escalated))), 'reentrant': True, 'terminal': False}]

def structural_interference_attribution(fact: dict) -> bool:
    return fact.get('ev') == 'attribution' and fact.get('provenance') == 'engine_auto:g6_prescreen'

def current_attribution(facts: list[dict], aid: str='') -> dict:
    mine = [fact for fact in facts if not aid or str(fact.get('aid') or '') == aid]
    verdict = next((fact for fact in reversed(mine) if fact.get('ev') == 'verdict'), None)
    if verdict is not None and (not verdict.get('run_id')):
        return {}
    attributions = [fact for fact in mine if fact.get('ev') == 'attribution' and (not structural_interference_attribution(fact)) and (fact.get('provenance') != 'engine_auto:execution_pause_reentry') and (verdict is None or fact.get('run_id') == verdict['run_id'])]
    return attributions[-1] if attributions else {}

def current_execution_prescription(facts: list[dict], aid: str) -> dict:
    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
    mine = [fact for fact in facts if str(fact.get('aid') or '') == aid]
    pause_index = max((index for index, fact in enumerate(mine) if fact.get('ev') == 'suspended'), default=-1)
    resume_index = max((index for index, fact in enumerate(mine) if fact.get('ev') == 'resumed'), default=-1)
    consumed = max((index for index, fact in enumerate(mine) if fact.get('ev') in {'verdict', 'authored', 'composed'}), default=-1)
    if pause_index >= 0 and resume_index > max(pause_index, consumed):
        pause = mine[pause_index]
        resumed = mine[resume_index]
        source_sha = _fact_sha256(pause)
        question_id = pause.get('question_id')
        if pause.get('suspension_kind') == 'execution_pause' and isinstance(question_id, str) and question_id and (resumed.get('of') == question_id):
            later = mine[resume_index + 1:]
            bound = any((fact.get('ev') == 'suspension_reentered' and fact.get('source_suspended_sha256') == source_sha for fact in later))
            requests = [fact for fact in later if fact.get('ev') == 'attribution' and fact.get('source') == 'engine_auto' and (fact.get('mechanical') is True) and (fact.get('provenance') == 'engine_auto:execution_pause_reentry') and (fact.get('run_id') == f'execution-reentry:{source_sha}') and (fact.get('source_event') == 'suspended') and (fact.get('source_fact_sha256') == source_sha) and (fact.get('disposition') == 'rerun_isolated') and (fact.get('is_terminal') is False)]
            if bound and requests:
                return requests[-1]
    return current_attribution(mine, aid)

def execution_retry_requested(facts: list[dict], aid: str) -> bool:
    return current_execution_prescription(facts, aid).get('disposition') in {'rerun_isolated', 'transient'}

def retired_execution_attribution_kind(att: dict) -> str:
    aid = str(att.get('aid') or '')
    if not aid or att.get('source') != 'engine_auto' or att.get('mechanical') is not True:
        return ''
    for kind, layer, disposition in (('env', 'E', 'env_blocked'), ('bed', 'E', 'env_blocked'), ('contra', 'V', 'defect_candidate')):
        if att.get('run_id') == f'retired_ask:{kind}:{aid}' and att.get('provenance') == f'engine_auto:retired_ask:{kind}' and (att.get('layer') == layer) and (att.get('disposition') == disposition):
            return kind
    return ''

def attribution_is_terminal(att: dict) -> bool:
    if structural_interference_attribution(att) or retired_execution_attribution_kind(att):
        return False
    if 'is_terminal' in att:
        return bool(att.get('is_terminal'))
    return int(att.get('round') or 0) == 99

def scenario5_device_defect(layer: str, disposition: str) -> bool:
    return str(layer or '') == 'product_defect' and str(disposition or '') == 'defect_candidate'

def scenario5_terminal_needs_run_evidence(attribution: dict) -> bool:
    return attribution_source(attribution) != 'user'

def scenario5_device_run_evidence(mine: list[dict], *, aid: str, run_id: str) -> bool:
    if not aid or not isinstance(run_id, str) or (not run_id.strip()):
        return False
    latest = next((fact for fact in reversed(mine) if fact.get('ev') == 'verdict' and str(fact.get('aid') or '') == aid and (fact.get('run_id') == run_id)), {})
    return latest.get('result') in {'pass', 'fail'}

def scenario5_attribution_has_evidence(attribution: dict, mine: list[dict]) -> bool:
    if not scenario5_device_defect(attribution.get('layer'), attribution.get('disposition')):
        return False
    if not scenario5_terminal_needs_run_evidence(attribution):
        return True
    return scenario5_device_run_evidence(mine, aid=str(attribution.get('aid') or ''), run_id=attribution.get('run_id'))

def attribution_source(att: dict) -> str:
    if 'source' in att:
        return str(att.get('source') or '')
    if str(att.get('evidence') or '') == 'user':
        return 'user'
    if str(att.get('layer') or '') == 'engine' or str(att.get('provenance') or '').startswith('engine_auto'):
        return 'engine_auto'
    return ''

def escalated_subclass(facts: list[dict], aid: str) -> str:
    esc = _facts_of(facts, aid, 'escalated')
    return _fact_subclass(esc[-1]) if esc else ''

def de_escalated_after_last_escalation(facts: list[dict], aid: str) -> dict | None:
    mine = [f for f in facts if str(f.get('aid')) == aid]
    last_esc = max((i for i, f in enumerate(mine) if f.get('ev') == 'escalated'), default=-1)
    if last_esc < 0:
        return None
    for f in mine[last_esc + 1:]:
        if f.get('ev') == 'de_escalated':
            return f
    return None

def recovery_attempts(facts: list[dict], aid: str) -> int:
    return len(_facts_of(facts, aid, 'de_escalated'))

def deesc_cap_threshold(max_rounds: int=3, granted: int=0) -> int:
    return max(1, int(max_rounds or 3) + int(granted or 0))

def escalation_attempts(facts: list[dict], aid: str, subclass: str, *, fork_fault: str | None=None) -> int:
    rows = [f for f in _facts_of(facts, aid, 'escalated') if _fact_subclass(f) == subclass]
    if fork_fault is None:
        return len(rows)
    want = str(fork_fault or '').strip()
    return sum((1 for f in rows if str(f.get('fork_fault') or '').strip() == want))

def fold_wave_common_cause(deaths: list[dict], *, total: int) -> dict | None:
    if total <= 0:
        return None
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in deaths:
        if not isinstance(row, dict):
            continue
        cause = str(row.get('cause_code') or '').strip()
        if not cause:
            continue
        api_error = row.get('api_error')
        api_error = api_error if isinstance(api_error, dict) else None
        code = str((api_error or {}).get('code') or '')
        groups.setdefault((cause, code), []).append({'aid': str(row.get('aid') or ''), 'api_error': api_error})
    if not groups:
        return None
    (cause, _code), members = max(groups.items(), key=lambda kv: len(kv[1]))
    count = len(members)
    if count * 2 <= int(total):
        return None
    return {'cause_code': cause, 'api_error': next((m['api_error'] for m in members if m['api_error']), None), 'count': count, 'total': int(total), 'aids': sorted({m['aid'] for m in members if m['aid']})}
_API_FIRST_OCCURRENCE_FAULTS: dict[str, tuple[str, str]] = {'API_REQUEST_REJECTED': ('the API endpoint rejected the request (non-transient 400/422)', 'switch the model or the API endpoint, then recompile'), 'API_AUTH_REJECTED': ('the API endpoint rejected the credentials or permissions (401/403)', 'top up the account, correct the key, or wait for the usage window to reset, then recompile; the whole batch stops here because the same credentials gate every remaining case')}

def deesc_auto_resolution(facts: list[dict], aid: str, new_escalated: dict, *, max_rounds: int=3, granted: int=0) -> list[dict]:
    from cex_core.engine.ist_core.compile_engine import authoring_evidence as AE
    if AE.uses_new_policy(facts + [new_escalated]):
        return AE.interruption_facts(facts, aid, new_escalated)
    sub = _fact_subclass(new_escalated)
    if sub == ESC_NO_OUTPUT:
        from cex_core.engine.ist_core.compile_engine._shared import escalation_budget_kind
        _budget_kind = escalation_budget_kind(new_escalated)
        if _budget_kind:
            return engine_budget_terminal_facts(facts, aid, new_escalated, _budget_kind)
    if sub in (ESC_NO_OUTPUT, ESC_NOT_EXECUTED):
        prior = escalation_attempts(facts, aid, sub)
        cap = deesc_cap_threshold(2, granted)
        if prior == 0:
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: first {sub} occurrence — engine grants one bounded serial max-effort recovery', 'recovery_policy': 'serial_max_effort_once'}, {'ev': 'ask_path_retired_disclosure', 'aid': aid, 'retired_kind': 'deesc', 'mechanical_route': 'bounded_engine_recovery', 'disclosure': '本轮无产物/未执行由引擎自动恢复一次：该案在独立单槽中重试并提升 effort。'}]
        if prior + 1 >= cap:
            _n = prior + 1
            _disposition = 'engineering_fault' if sub == ESC_NO_OUTPUT else 'env_blocked'
            _layer = 'engine' if sub == ESC_NO_OUTPUT else 'E'
            _terminal_rows = [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: round-cap reached ({_n}x {sub}, threshold={cap})'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': _layer, 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_cap:{aid}:{sub}:{_n}', 'provenance': 'engine_auto:deesc_cap', 'disposition': _disposition, 'fix_direction': f'escalation round-cap reached ({_n}x {sub}, threshold={cap}) — engine exhausted its recovery attempts for this case without producing new evidence', 'evidence': '', 'user_note': f'引擎已自动恢复一次但第 {_n} 次仍无产物，已按引擎/框架工程故障收口。' if sub == ESC_NO_OUTPUT else f'自动恢复一次后第 {_n} 次仍无法执行，已按环境/平台限制如实收口。'}, EE.engine_error_fact(aid, EE.E_WORKER_TIMEOUT if sub == ESC_NO_OUTPUT else EE.E_ENVIRONMENT, f'escalation round-cap reached ({_n}x {sub}, threshold={cap})')]
            _terminal_rows.append({'ev': 'ask_path_retired_disclosure', 'aid': aid, 'retired_kind': 'deesc', 'mechanical_route': _disposition, 'disclosure': '引擎自动恢复一次后仍无产物，已按引擎/框架工程故障收口。' if sub == ESC_NO_OUTPUT else '引擎自动恢复一次后仍无法执行，已按环境/平台限制收口。'})
            if sub == ESC_NOT_EXECUTED:
                _terminal_rows.append({'ev': 'environment_execution_disclosure', 'aid': aid, 'obstacle_class': 'platform_limitation', 'environment_basis': [str(new_escalated.get('reason') or '')[:300]], 'author_unreachable_values': [], 'disclosure': '自动恢复后仍无法执行，当前平台无法完成编写/上机。'})
            return _terminal_rows
        return []
    if sub == ESC_HARNESS_FAULT:
        prior = escalation_attempts(facts, aid, sub)
        cap = deesc_cap_threshold(2, granted)
        if prior == 0:
            return [{'ev': 'de_escalated', 'aid': aid, 'note': 'auto: first harness fault — engine grants one bounded serial max-effort recovery', 'recovery_policy': 'serial_max_effort_once'}, {'ev': 'ask_path_retired_disclosure', 'aid': aid, 'retired_kind': 'deesc', 'mechanical_route': 'bounded_engine_recovery', 'disclosure': '测试框架首次失败由引擎自动恢复一次：该案在独立单槽中重试并提升 effort。'}]
        if prior + 1 >= cap:
            _n = prior + 1
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: harness fault recurred after recovery attempt ({_n}x {sub}, threshold={cap})'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_harness:{aid}:{_n}', 'provenance': 'engine_auto:deesc_harness', 'disposition': 'engineering_fault', 'fix_direction': f'test harness crashed at collect/setup and recurred after {_n}x recovery attempt(s) (threshold={cap}) — this is an engine/framework-side gap (e.g. an unsafe dispatch/build-string construction defect), not a product defect; do not record it in the defect-candidate ledger', 'evidence': '', 'user_note': f'测试框架自身崩溃,恢复尝试后仍复现(第 {_n} 次)——判定为工程故障(引擎/框架缺口),不是产品缺陷,已呈报。'}, EE.engine_error_fact(aid, EE.E_COLLECT_SETUP, f'harness crashed at collect/setup and recurred after {_n}x recovery attempt(s) (threshold={cap})')]
        return []
    if sub == ESC_WORKER_ENVELOPE:
        prior = escalation_attempts(facts, aid, sub, fork_fault=str(new_escalated.get('fork_fault') or '').strip())
        cap = deesc_cap_threshold(2, granted)
        _fault = str(new_escalated.get('fork_fault') or '').strip()
        if _fault == 'LLM_QUOTA_EXHAUSTED':
            _n = prior + 1
            _what = 'LLM endpoint account is out of quota/credit'
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: {_what} — signed on first occurrence; a retry cannot mint credit'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_envelope:{aid}:{_n}', 'provenance': 'engine_auto:deesc_envelope', 'disposition': 'engineering_fault', 'fix_direction': f'{_what} — top up the account or switch endpoints; retrying cannot change an empty account (signed on first occurrence, no recovery attempt spent), not a product defect', 'evidence': str(new_escalated.get('reason') or '')[:300]}, EE.engine_error_fact(aid, EE.E_LLM_QUOTA_EXHAUSTED, f'{_what} (signed on first occurrence)')]
        if _fault in _API_FIRST_OCCURRENCE_FAULTS:
            _n = prior + 1
            _what, _goto = _API_FIRST_OCCURRENCE_FAULTS[_fault]
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: {_what} — signed on first occurrence; resending the same request cannot change the verdict'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_envelope:{aid}:{_n}', 'provenance': 'engine_auto:deesc_envelope', 'disposition': 'engineering_fault', 'fix_direction': f'{_what} — {_goto}; resending the same request gets the same rejection (signed on first occurrence, no recovery attempt spent), an API-side condition, not a product defect and not an engine fault', 'evidence': str(new_escalated.get('reason') or '')[:300]}, EE.engine_error_fact(aid, EE.API_CAUSE_CODES[_fault], f'{_what} (signed on first occurrence)')]
        if _fault == 'TRANSIENT_ERROR' and new_escalated.get('wave_common_cause'):
            _n = prior + 1
            _what = "LLM endpoint transient pressure exhausted the engine's retries"
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: {_what} — over half of this dispatch wave died on the same endpoint condition; the engine stops here instead of spending a recovery attempt on the same window'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_envelope:{aid}:{_n}', 'provenance': 'engine_auto:deesc_envelope', 'disposition': 'engineering_fault', 'fix_direction': f'{_what} — rerun later with the same parameters, or raise the endpoint-side quota; over half of this wave died the same way, so no second wave was dispatched — an endpoint-side condition, not a product defect', 'evidence': str(new_escalated.get('reason') or '')[:300]}, EE.engine_error_fact(aid, EE.E_LLM_TRANSIENT_EXHAUSTED, f'{_what} (wave common cause, no second wave)')]
        if prior + 1 >= cap:
            _n = prior + 1
            if _fault == 'TRANSIENT_ERROR':
                _code = EE.E_LLM_TRANSIENT_EXHAUSTED
                _what = "LLM endpoint transient pressure exhausted the engine's retries"
                _gap = 'the endpoint kept rate-limiting/overloading through the call-level backoff retries; rerun later, or raise the endpoint-side quota — this repo no longer ships concurrency or rate knobs — an endpoint-side condition, not an engine fault'
            elif _fault:
                _code = EE.E_FORK_CHANNEL_FAULT
                _what = f'engine fork/governance channel aborted the worker ({_fault})'
                _gap = 'this is an engine-side fork channel gap (the worker process was aborted before its first round; repair the durable run registry / governance layer)'
            else:
                _code = EE.E_WORKER_RESULT_ENVELOPE
                _what = 'worker result envelope failed protocol validation'
                _gap = 'this is an engine-side fork channel gap (truncated tool call / missing structured response; repair the fork return-envelope channel)'
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: {_what} again after a recovery attempt ({_n}x {sub}, threshold={cap})'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_envelope:{aid}:{_n}', 'provenance': 'engine_auto:deesc_envelope', 'disposition': 'engineering_fault', 'fix_direction': f'{_what} and it recurred after {_n}x recovery attempt(s) (threshold={cap}) — {_gap}, not a product defect', 'evidence': str(new_escalated.get('reason') or '')[:300]}, EE.engine_error_fact(aid, _code, f'{_what} {_n}x (threshold={cap})')]
        return [{'ev': 'de_escalated', 'aid': aid, 'note': 'auto: first occurrence — engine spends its own recovery attempt'}]
    if sub == ESC_NO_LEDGER_CHANNEL:
        from cex_core.engine.ist_core.worker_device_context import COMMAND_HEADS_RECEIPT_REDACTION_FOLDED
        if str(new_escalated.get('diagnostic_code') or '') == COMMAND_HEADS_RECEIPT_REDACTION_FOLDED:
            return [{'ev': 'de_escalated', 'aid': aid, 'note': "auto: command inventory receipt was broken by the engine's own redaction — a retry cannot change it"}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f"auto_redact:{aid}:{len(_facts_of(facts, aid, 'escalated')) + 1}", 'provenance': 'engine_auto:deesc_redact', 'disposition': 'engineering_fault', 'fix_direction': 'the command-heads receipt was validated against a redacted copy; redaction folded distinct command heads into one literal, so a valid receipt was rejected — engine-side gap in where the redaction boundary sits, not a product defect', 'evidence': str(new_escalated.get('reason') or '')[:300]}, EE.engine_error_fact(aid, EE.E_INVENTORY_RECEIPT_REDACTED, 'command inventory receipt validated against a redacted copy; redaction folded distinct heads into duplicates')]
        family = _fact_esc_family(new_escalated)
        if family == ESCALATION_FAMILY_UNDERDETERMINED_CLAIM:
            landing = author_definition_gap_landing_facts(facts, aid, new_escalated)
            if landing:
                return [*landing, {'ev': 'ask_path_retired_disclosure', 'aid': aid, 'retired_kind': 'non_batch_gather', 'mechanical_route': 'author_definition_gap', 'disclosure': '作者定义缺口已直接披露收尾。'}]
        prior_esc = [f for f in _facts_of(facts, aid, 'escalated') if _fact_subclass(f) == sub and _fact_esc_family(f) == family]
        if not prior_esc:
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f"auto: first {family or 'unclassified'} occurrence — engine spends its own recovery attempt"}]
        if family == ESCALATION_FAMILY_UNDERDETERMINED_CLAIM:
            landing = author_definition_gap_landing_facts(facts, aid, new_escalated)
            if landing:
                return landing
            _n = len(prior_esc) + 1
            return [{'ev': 'de_escalated', 'aid': aid, 'note': 'auto: underdetermined claim recurred without a quotable declaration — the structured landing exists but was not used'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_eng:{aid}:{family}:{_n}', 'provenance': 'engine_auto:deesc_eng', 'disposition': 'engineering_fault', 'fix_direction': 'an underdetermined claim recurred for the same case after one recovery attempt, but carried no quotable declaration and the structured author-definition-gap terminal was never signed — a worker protocol/guidance gap (the landing channel exists since the 2026-08-21 ruling), not a product defect and not a missing ledger channel', 'evidence': str(new_escalated.get('reason') or '')[:300], 'user_note': '编写侧连续两轮声明「通过标准欠定」但未留下可引用的缺口清单，也未走结构化欠定终点；已按工程故障终止该案，待引擎侧修正编写引导。'}]
        if family in {ESCALATION_FAMILY_BINDING_UNAVAILABLE, ESCALATION_FAMILY_WORKER_PROTOCOL_DRIFT}:
            if family == ESCALATION_FAMILY_BINDING_UNAVAILABLE:
                failure = 'required engine-owned intent/consistency binding remained unavailable'
                provenance = 'engine_auto:deesc_binding'
                user_note = '引擎自有的意图/一致性绑定恢复后仍不可用，已按工程故障终止该案。'
            else:
                failure = 'worker terminal/protocol outcome again lacked its engine-owned receipt'
                provenance = 'engine_auto:deesc_worker_protocol'
                user_note = 'worker 终态/协议结果恢复后仍与引擎回执不一致，已按工程故障终止该案。'
            return [{'ev': 'de_escalated', 'aid': aid, 'note': f'auto: {family} recurred for the same case after a recovery attempt'}, {'ev': 'attribution', 'aid': aid, 'round': rounds_used(facts, aid), 'layer': 'engine', 'is_terminal': True, 'source': 'engine_auto', 'run_id': f'auto_eng:{aid}:{family}:{len(prior_esc) + 1}', 'provenance': provenance, 'disposition': 'engineering_fault', 'fix_direction': f"{failure} after one recovery attempt; this is an engine-side {family.replace('_', ' ')} failure, not an underdetermined claim or product defect", 'evidence': str(new_escalated.get('reason') or '')[:300], 'user_note': user_note}]
        return []
    return []

def serial_recovery_pending(facts: list[dict], aids: list[str]) -> bool:
    wanted = {str(aid) for aid in aids if str(aid)}
    for aid in wanted:
        mine = [fact for fact in facts if str(fact.get('aid') or '') == aid]
        latest = next((fact for fact in reversed(mine) if fact.get('ev') in {'de_escalated', 'authored', 'composed'}), None)
        if isinstance(latest, dict) and latest.get('ev') == 'de_escalated' and (latest.get('recovery_policy') == 'serial_max_effort_once'):
            return True
    return False
STRONG_DISPOSITIONS = ('defect_candidate', 'expectation_suspect')

def strong_claims(facts: list[dict], aid: str) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()
    for f in _facts_of(facts, aid, 'attribution'):
        if str(f.get('disposition')) not in STRONG_DISPOSITIONS:
            continue
        ev = str(f.get('evidence') or '')
        if not ev or attribution_source(f) in ('user', 'engine_auto'):
            continue
        claim = str(f.get('fix_direction') or '')[:ATTRIBUTION_TEXT_MAX_CHARS]
        k = (str(f.get('disposition')), claim)
        if k in seen:
            continue
        seen.add(k)
        out.append({'round': int(f.get('round') or 0), 'layer': str(f.get('layer') or ''), 'disposition': str(f.get('disposition')), 'claim': claim, 'evidence': ev[:ATTRIBUTION_TEXT_MAX_CHARS], 'user_note': str(f.get('user_note') or '')[:ATTRIBUTION_TEXT_MAX_CHARS], 'is_terminal': attribution_is_terminal(f)})
    return out

def reconcile(facts: list[dict], verdicts: list[dict]) -> dict:
    out = {'append': [], 'transition': [], 'confirm': [], 'duplicate': []}
    known = {idem_key(f) for f in facts}
    for v in verdicts:
        f = dict(v)
        f['ev'] = 'verdict'
        fr = f.get('framework_result')
        if fr is not None and fr not in FRAMEWORK_RESULT_DOMAIN:
            raise ValueError(f"framework_result 值域断言失败: {fr!r} 不在 {sorted(FRAMEWORK_RESULT_DOMAIN)} 内(aid={f.get('aid')})——这可能意味着框架版本变更引入了新的裁决值,请先核 knowledge/framework/mirror/lib/check_point.py + lib/config.py 确认真实值域,再决定是否扩大这个闭集;不要放行未知值。")
        r = f.get('result')
        if r not in RESULT_DOMAIN:
            raise ValueError(f"result 值域断言失败: {r!r} 不在 {sorted(RESULT_DOMAIN)} 内(aid={f.get('aid')})——写入前请确认没有把 framework_result 误当 result 写入。")
        if idem_key(f) in known:
            out['duplicate'].append(str(f.get('aid')))
            continue
        aid = str(f.get('aid'))
        prev = latest_verdict(facts, aid, ctx=str(f.get('ctx') or '') or None, artifact=str(f.get('artifact')))
        same = bool(prev and prev.get('result') == f.get('result'))
        out['append'].append(f)
        (out['confirm'] if same else out['transition']).append(aid)
        facts = facts + [f]
        known.add(idem_key(f))
    return out

class FrameworkResultState(enum.Enum):
    """framework_result 读出的四态(ABSENT/NOT_GIVEN/STRIPPED/GIVEN,SPEC §2 表)。

    `__bool__` 显式抛 TypeError(内部工单 补遗边界②,机械实测追加的硬约束——不是
    "不返回裸 Optional[str]" 就够了):plain Enum 默认真值走 `object.__bool__`
    恒为 True(与 IntEnum(0) 这类会静默假的特例不同),不会自己变成静默假,
    但显式抛更醒目,与 `FrameworkResultRead.__bool__`、同批
    `shadow_exec.ShadowVerdict.__bool__` 同一纪律——防的是将来有人图省事写
    `if state:`,而 ABSENT/NOT_GIVEN/STRIPPED/GIVEN 四个成员在默认真值下全部
    通过这个判断,等价于什么都没判、却读起来像判过了。
    """
    ABSENT = 'absent'
    NOT_GIVEN = 'not_given'
    STRIPPED = 'stripped'
    GIVEN = 'given'

    def __bool__(self) -> bool:
        raise TypeError('FrameworkResultState 禁止布尔化——四态判据没有真/假这一维,必须显式 `== FrameworkResultState.XXX` 比较,不能写 `if state:`。')

@dataclass(frozen=True)
class FrameworkResultRead:
    state: FrameworkResultState
    value: str | None

    def __bool__(self) -> bool:
        raise TypeError('FrameworkResultRead 禁止布尔化——必须显式判 .state 是 FrameworkResultState 的哪个成员,不能写 `if read_framework_result(event):` 或 `if not ...:`。')

def read_framework_result(event: dict) -> FrameworkResultRead:
    if 'framework_result' not in event:
        return FrameworkResultRead(FrameworkResultState.ABSENT, None)
    value = event.get('framework_result')
    if value is not None:
        return FrameworkResultRead(FrameworkResultState.GIVEN, value)
    if event.get('broken_subtype') == 'verdict_unrecognized':
        return FrameworkResultRead(FrameworkResultState.STRIPPED, None)
    return FrameworkResultRead(FrameworkResultState.NOT_GIVEN, None)
_SUBSET_VOLUME_DIR_RE = re.compile('^workspace/outputs/[^/]+__sub\\d+(/|$)')
_INTERMEDIATE_FILENAMES = frozenset({'manifest.json', 'last_run.json'})
_PERMANENT_SUBDIRS = frozenset({'delivered', 'unfinished'})

def classify_reference_permanence(rel_path: str) -> str:
    p = str(rel_path or '').strip().lstrip('/')
    if _SUBSET_VOLUME_DIR_RE.match(p):
        return 'intermediate'
    parts = p.split('/')
    if len(parts) >= 4 and parts[0] == 'workspace' and (parts[1] == 'outputs'):
        if len(parts) == 4 and parts[3] in _INTERMEDIATE_FILENAMES:
            return 'intermediate'
        if len(parts) == 4 and parts[3] == 'case.xlsx':
            return 'permanent'
        if len(parts) >= 5 and parts[3] in _PERMANENT_SUBDIRS:
            return 'permanent'
    return 'unknown'
_PATH_TYPE_FIELDS: dict[str, tuple[str, ...]] = {'merged': ('path',), 'verdict': ('evidence_ref',)}
_VALIDITY_EXEMPTION_WHITELIST: dict[tuple[str, str], dict] = {}

def find_lifecycle_mismatches(facts: list[dict]) -> list[dict]:
    violations: list[dict] = []
    for f in facts:
        ev = str(f.get('ev') or '')
        fields = _PATH_TYPE_FIELDS.get(ev)
        if not fields:
            continue
        for field in fields:
            val = f.get(field)
            if not val:
                continue
            kind = classify_reference_permanence(str(val))
            if kind == 'permanent':
                continue
            if kind == 'intermediate':
                exemption = _VALIDITY_EXEMPTION_WHITELIST.get((ev, field))
                if exemption and f.get(exemption['declares_via']):
                    continue
            violations.append({'ev': ev, 'aid': f.get('aid'), 'run_id': f.get('run_id'), 'field': field, 'value': val, 'classification': kind})
    return violations
