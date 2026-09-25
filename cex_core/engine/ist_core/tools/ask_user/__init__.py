# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/ask_user/__init__.py（sha256 61111044ed4739aa）。不在这里手改。
from __future__ import annotations
import contextvars
import json
import hashlib
import logging
import math
import os
import re
import threading
import time
from contextlib import contextmanager
from typing import Any
from langchain_core.tools import tool
from cex_core.engine.common.schema_identity import accepts_schema
logger = logging.getLogger(__name__)
TIMEOUT_MARK = 'User did not answer within the timeout window (no answer).'
CANCEL_MARK = 'User cancelled the question (no answer).'
_PENDING: dict[str, dict[str, Any]] = {}
_PENDING_LOCK = threading.Lock()
_WAIT_TIMEOUT_OVERRIDE = threading.local()
_LIFECYCLE_LOCK = threading.RLock()
_LIFECYCLE_PHASES: dict[str, set[str]] = {}
_LIFECYCLE_SCHEMA = 'ist.ask_user.lifecycle'
_REASK_REQUESTED_PHASE = 'reask_requested'
_ANSWER_REPLAYED_PHASE = 'answer_replayed'
_REASK_REASON_CODES = frozenset({'answer_token_unmapped', 'signer_invalid', 'run_window_unavailable', 'answer_credential_mismatch'})
_RENDER_VERSION = 'ask_user'
_QID_RESERVATIONS: set[str] = set()
_HIL_OWNER: 'contextvars.ContextVar[str]' = contextvars.ContextVar('ist_hil_owner', default='')
_HIL_THREAD_ID: 'contextvars.ContextVar[str]' = contextvars.ContextVar('ist_hil_thread_id', default='')
_HIL_ID_RE = re.compile('^[A-Za-z0-9_.@+:-]{1,256}$')
_POSITIONAL_ANSWERS: contextvars.ContextVar[list[Any] | None] = contextvars.ContextVar('ist_ask_user_positional_answers', default=None)

def _publish_positional_answers(values: list[Any]) -> None:
    _POSITIONAL_ANSWERS.set(list(values))

def reset_positional_answers() -> None:
    _POSITIONAL_ANSWERS.set(None)

def positional_answers() -> list[Any] | None:
    return _POSITIONAL_ANSWERS.get()

def _validated_hil_identity(value: Any, *, field: str) -> str:
    text = str(value or '').strip()
    if text in {'', '.', '..'} or _HIL_ID_RE.fullmatch(text) is None:
        raise RuntimeError(f'HIL {field} identity is invalid')
    return text

@contextmanager
def hil_identity(owner: str, thread_id: str):
    safe_owner = _validated_hil_identity(owner, field='owner')
    safe_thread = _validated_hil_identity(thread_id, field='thread')
    owner_token = _HIL_OWNER.set(safe_owner)
    thread_token = _HIL_THREAD_ID.set(safe_thread)
    try:
        yield
    finally:
        _HIL_THREAD_ID.reset(thread_token)
        _HIL_OWNER.reset(owner_token)

def _current_hil_identity() -> tuple[str, str]:
    owner = _HIL_OWNER.get()
    thread_id = _HIL_THREAD_ID.get()
    if bool(owner) != bool(thread_id):
        raise RuntimeError('HIL owner/thread binding is incomplete')
    return (owner, thread_id)

def current_hil_identity() -> tuple[str, str]:
    return _current_hil_identity()

def hil_identity_sha256(owner: str='', thread_id: str='') -> str:
    safe_owner = str(owner or '')
    safe_thread = str(thread_id or '')
    if bool(safe_owner) != bool(safe_thread):
        raise RuntimeError('HIL owner/thread binding is incomplete')
    payload = json.dumps({'owner': safe_owner, 'thread_id': safe_thread}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def current_hil_identity_sha256() -> str:
    return hil_identity_sha256(*_current_hil_identity())

def hil_identity_digest_is_current(value: Any, *, allow_legacy_unbound: bool=True) -> bool:
    owner, thread_id = _current_hil_identity()
    expected = hil_identity_sha256(owner, thread_id)
    actual = str(value or '')
    if owner or thread_id:
        return actual == expected
    return actual == expected or (allow_legacy_unbound and (not actual))

def _pending_authorized(pending: dict[str, Any], *, owner: str='', thread_id: str='') -> bool:
    requested_owner = str(owner or '').strip()
    requested_thread = str(thread_id or '').strip()
    if bool(requested_owner) != bool(requested_thread):
        return False
    bound_owner = str(pending.get('owner') or '')
    bound_thread = str(pending.get('thread_id') or '')
    if bool(bound_owner) != bool(bound_thread):
        return False
    if bound_owner:
        return requested_owner == bound_owner and requested_thread == bound_thread
    return not requested_owner and (not requested_thread)

def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))

def _persist_safe(value: Any) -> Any:
    from cex_core.engine.ist_core.security_scrub import scrub_value
    return _json_safe(scrub_value(_json_safe(value)))

def _render_digest(questions: list[dict[str, Any]]) -> str:
    raw = json.dumps(_persist_safe(questions), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def _normalize_questions(questions: Any) -> tuple[list[dict[str, Any]] | None, str]:
    if not isinstance(questions, list) or not questions:
        return (None, "'questions' must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(questions):
        if not isinstance(raw, dict):
            return (None, f'question[{index}] must be a dict')
        question = str(raw.get('question') or '').strip()
        if not question:
            return (None, f'question[{index}].question must not be empty')
        header = str(raw.get('header') or f'问题{index + 1}').strip()
        if not header:
            return (None, f'question[{index}].header must not be empty')
        multi_select = raw.get('multiSelect', False)
        if not isinstance(multi_select, bool):
            return (None, f'question[{index}].multiSelect must be a bool')
        accepts_file = raw.get('accepts_file', False)
        if not isinstance(accepts_file, bool):
            return (None, f'question[{index}].accepts_file must be a bool')
        options = raw.get('options')
        if not isinstance(options, list) or not options:
            return (None, f'question[{index}].options must be a non-empty list')
        normalized_options: list[dict[str, Any]] = []
        labels: set[str] = set()
        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                return (None, f'question[{index}].options[{option_index}] must be a dict')
            label = str(option.get('label') or '').strip()
            description = option.get('description')
            if not label or label in labels:
                return (None, f'question[{index}].options[{option_index}].label must be unique and non-empty')
            if not isinstance(description, str):
                return (None, f'question[{index}].options[{option_index}].description must be a string')
            if 'preview' in option and (not isinstance(option.get('preview'), (str, dict, list, type(None)))):
                return (None, f'question[{index}].options[{option_index}].preview has an unsupported type')
            labels.add(label)
            normalized_options.append({**option, 'label': label})
        normalized_q = {**raw, 'question': question, 'header': header, 'options': normalized_options, 'multiSelect': multi_select}
        if 'accepts_file' in raw:
            normalized_q['accepts_file'] = accepts_file
        normalized.append(normalized_q)
    return (normalized, '')

def _engine_visible_question(question: dict[str, Any]) -> dict[str, Any]:
    rendered = {key: value for key, value in dict(question).items() if not str(key).startswith('_')}
    answer_key = str(question.get('_answer_key') or '').strip()
    if answer_key:
        rendered['answer_key'] = answer_key
    if question.get('_allow_other') is False:
        rendered['allow_other'] = False
    return rendered

def _normalize_engine_question(question: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(question, dict):
        return (None, 'engine question must be a dict')
    rendered = _engine_visible_question(question)
    normalized, error = _normalize_questions([rendered])
    if normalized is None or error:
        return (None, error)
    return (normalized[0], '')

def _engine_question_digest(question: dict[str, Any]) -> str:
    normalized, error = _normalize_engine_question(question)
    if normalized is None or error:
        return ''
    return _render_digest([normalized])

def _lifecycle_records() -> list[dict[str, Any]]:
    from cex_core.engine.common.runtime_paths import runtime_path
    path = runtime_path('ask_user_lifecycle.jsonl')
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(item, dict) and item.get('schema') == _LIFECYCLE_SCHEMA:
            records.append(item)
    return records

def _allocate_question_id(questions: list[dict[str, Any]], *, owner: str='', thread_id: str='') -> tuple[str, set[str], dict[str, Any] | None]:
    from cex_core.engine.knowledge_paths import current_username, multi_tenant, output_scope
    if bool(owner) != bool(thread_id):
        raise RuntimeError('HIL owner/thread binding is incomplete')
    if owner:
        namespace_parts = (owner, thread_id, _render_digest(questions))
    else:
        ident = output_scope() if multi_tenant() else str(current_username() or '')
        namespace_parts = (ident, os.environ.get('IST_CONVERSATION_ID', '').strip(), os.environ.get('IST_SESSION_ID', '').strip(), _render_digest(questions))
    namespace = '|'.join(namespace_parts)
    prefix = hashlib.sha256(namespace.encode('utf-8')).hexdigest()[:24]
    with _LIFECYCLE_LOCK:
        by_qid: dict[str, set[str]] = {}
        terminal_by_qid: dict[str, dict[str, Any]] = {}
        reask_requested_qids: set[str] = set()
        answer_replayed_qids: set[str] = set()
        for record in _lifecycle_records():
            qid = str(record.get('question_id') or '')
            record_owner = str(record.get('owner') or '')
            record_thread = str(record.get('thread_id') or '')
            binding_matches = record_owner == owner and record_thread == thread_id if owner else not record_owner and (not record_thread)
            if qid.startswith(prefix + '-') and binding_matches:
                phase = str(record.get('phase') or '')
                by_qid.setdefault(qid, set()).add(phase)
                if record.get('phase') == 'resolved':
                    terminal_by_qid[qid] = record
                elif phase == _REASK_REQUESTED_PHASE:
                    reask_requested_qids.add(qid)
                elif phase == _ANSWER_REPLAYED_PHASE:
                    answer_replayed_qids.add(qid)
        sequences = sorted((int(qid.rsplit('-', 1)[1]) for qid in by_qid if qid.rsplit('-', 1)[1].isdigit()))
        sequence = sequences[-1] if sequences else 1
        qid = f'{prefix}-{sequence:08d}'
        phases = set(by_qid.get(qid, set()))
        if 'resolved' in phases:
            terminal = terminal_by_qid.get(qid)
            if str((terminal or {}).get('outcome') or '') == 'answered' and qid not in reask_requested_qids and (not answer_replayed_qids):
                return (qid, phases, terminal)
            sequence += 1
            qid = f'{prefix}-{sequence:08d}'
            phases = set(by_qid.get(qid, set()))
        if qid in _QID_RESERVATIONS:
            return ('', phases, None)
        _QID_RESERVATIONS.add(qid)
        _LIFECYCLE_PHASES[qid] = set(phases)
        return (qid, phases, None)

def _option_tokens(questions: list[dict[str, Any]]) -> list[list[str]]:
    return _persist_safe([[str(opt.get('label') or '') for opt in q.get('options') or []] + (['Other'] if q.get('allow_other') is not False else []) for q in questions])

def _append_lifecycle_record(record: dict[str, Any]) -> None:
    from cex_core.engine.common.runtime_paths import runtime_path
    path = runtime_path('ask_user_lifecycle.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    safe_record = _persist_safe(record)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(safe_record, ensure_ascii=False, sort_keys=True) + '\n')
        fh.flush()
        os.fsync(fh.fileno())
    if not existed and hasattr(os, 'O_DIRECTORY'):
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

def request_reask_after_rejection(answer_key: str, *, question_digest: str='', reason_code: str) -> bool:
    key = str(answer_key or '').strip()
    digest = str(question_digest or '').strip()
    reason = str(reason_code or '').strip()
    if not key or reason not in _REASK_REASON_CODES:
        return False
    owner, thread_id = _current_hil_identity()
    with _LIFECYCLE_LOCK:
        records = _lifecycle_records()
        scheduled_by_qid: dict[str, dict[str, Any]] = {}
        answered_by_qid: dict[str, dict[str, Any]] = {}
        already_requested: set[str] = set()
        for record in records:
            record_owner = str(record.get('owner') or '')
            record_thread = str(record.get('thread_id') or '')
            binding_matches = record_owner == owner and record_thread == thread_id if owner else not record_owner and (not record_thread)
            if not binding_matches:
                continue
            qid = str(record.get('question_id') or '')
            phase = str(record.get('phase') or '')
            if not qid:
                continue
            if phase == 'scheduled':
                scheduled_by_qid[qid] = record
            elif phase == 'resolved' and record.get('outcome') == 'answered':
                answered_by_qid[qid] = record
            elif phase == _REASK_REQUESTED_PHASE:
                already_requested.add(qid)
        candidates: list[tuple[float, str, str, str, str]] = []
        for qid in set(scheduled_by_qid) & set(answered_by_qid):
            scheduled = scheduled_by_qid[qid]
            for question in scheduled.get('render_input') or []:
                if not isinstance(question, dict):
                    continue
                recorded_key = str(question.get('answer_key') or '').strip()
                recorded_digest = _render_digest([question])
                if recorded_key != key and (not (digest and recorded_digest == digest)):
                    continue
                try:
                    terminal_ts = float(answered_by_qid[qid].get('ts') or 0.0)
                except (TypeError, ValueError):
                    terminal_ts = 0.0
                candidates.append((terminal_ts, qid, recorded_key, recorded_digest, str(scheduled.get('owner') or '')))
        if not candidates:
            return False
        _ts, qid, recorded_key, recorded_digest, _recorded_owner = max(candidates)
        if qid in already_requested:
            return True
        record = {'schema': _LIFECYCLE_SCHEMA, 'phase': _REASK_REQUESTED_PHASE, 'question_id': qid, 'owner': owner, 'thread_id': thread_id, 'ts': time.time(), 'render_version': _RENDER_VERSION, 'reason_code': reason, 'answer_key': recorded_key or key, 'rejected_question_digest': digest, 'recorded_question_digest': recorded_digest, 'digest_matched': bool(digest and digest == recorded_digest)}
        _append_lifecycle_record(record)
        _LIFECYCLE_PHASES.setdefault(qid, set()).add(_REASK_REQUESTED_PHASE)
        _QID_RESERVATIONS.discard(qid)
    _emit_lifecycle('ask_user_reask_requested', record)
    return True

def _append_answer_credential(question_id: str, questions: list[dict[str, Any]], answers: dict[str, str], *, owner: str='', thread_id: str='') -> None:
    from cex_core.engine.common.runtime_paths import runtime_path
    path = runtime_path('ask_user_answers.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    answer_bindings = []
    for question in questions:
        answer_key = str(question.get('answer_key') or '').strip()
        if not answer_key:
            continue
        question_text = str(question.get('question') or '')
        header = str(question.get('header') or '')
        matched_key = next((key for key in (question_text, header, answer_key) if key and key in answers), '')
        if not matched_key:
            continue
        answer_bindings.append({'answer_key': answer_key, 'question_digest': _render_digest([question]), 'answer': str(answers[matched_key])[:500]})
    record = _persist_safe({'schema': 'ist.ask_user.answer', 'question_id': str(question_id or ''), 'owner': str(owner or ''), 'thread_id': str(thread_id or ''), 'ts': time.time(), 'questions': [str(question.get('question') or '')[:500] for question in questions], 'folded_members': sorted({str(aid) for question in questions for aid in question.get('folded_members') or []}), 'answers': {str(key)[:500]: (', '.join(map(str, value)) if isinstance(value, list) else str(value))[:500] for key, value in answers.items()}, 'answer_bindings': answer_bindings})
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    if not existed and hasattr(os, 'O_DIRECTORY'):
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

def operator_answer_credential_binding(answer_key: str, *, question_digest: str, not_before: float) -> dict[str, Any] | None:
    from cex_core.engine.common.runtime_paths import runtime_path
    key = str(answer_key or '').strip()
    digest = str(question_digest or '').strip()
    try:
        lower_bound = float(not_before)
    except (TypeError, ValueError):
        return None
    if not key or not digest or (not math.isfinite(lower_bound)) or (lower_bound <= 0.0):
        return None
    path = runtime_path('ask_user_answers.jsonl')
    expected_owner, expected_thread = _current_hil_identity()
    newest: tuple[float, dict[str, Any]] | None = None
    try:
        handle = path.open('rb')
    except OSError:
        return None
    with handle:
        for raw in handle:
            if b'ist.ask_user.answer' not in raw:
                continue
            try:
                item = json.loads(raw.decode('utf-8', 'replace'))
                recorded_at = float(item.get('ts') or 0.0)
            except (AttributeError, TypeError, ValueError):
                continue
            if not isinstance(item, dict) or not accepts_schema(item.get('schema'), 'ist.ask_user.answer') or recorded_at < lower_bound:
                continue
            recorded_owner = str(item.get('owner') or '')
            recorded_thread = str(item.get('thread_id') or '')
            if recorded_owner != expected_owner or recorded_thread != expected_thread:
                continue
            for binding in item.get('answer_bindings') or []:
                if not isinstance(binding, dict):
                    continue
                if str(binding.get('answer_key') or '') != key or str(binding.get('question_digest') or '') != digest:
                    continue
                answer = str(binding.get('answer') or '')
                if not answer:
                    continue
                candidate = {'answer_key': key, 'question_digest': digest, 'answer': answer, 'question_id': str(item.get('question_id') or ''), 'owner': recorded_owner, 'thread_id': recorded_thread, 'recorded_at': recorded_at, 'provenance_channel': 'operator'}
                if newest is None or recorded_at >= newest[0]:
                    newest = (recorded_at, candidate)
    return None if newest is None else newest[1]

def answer_credential_recorded(answer_key: str, *, question_digest: str='', not_before: float | None=None, accept_answered_replay: bool=False) -> bool:
    from cex_core.engine.common.runtime_paths import runtime_path
    key = str(answer_key or '').strip()
    if not key:
        return False
    path = runtime_path('ask_user_answers.jsonl')
    replayed: set[tuple[str, str, str]] = set()
    if accept_answered_replay and not_before is not None:
        for record in _lifecycle_records():
            if record.get('phase') != _ANSWER_REPLAYED_PHASE:
                continue
            try:
                replayed_at = float(record.get('ts') or 0.0)
            except (TypeError, ValueError):
                continue
            if replayed_at < not_before:
                continue
            qid = str(record.get('question_id') or '')
            for binding in record.get('answer_bindings') or []:
                if not isinstance(binding, dict):
                    continue
                replayed.add((qid, str(binding.get('answer_key') or ''), str(binding.get('question_digest') or '')))
    try:
        fh = path.open('rb')
    except OSError:
        return False
    with fh:
        for raw in fh:
            if b'ist.ask_user.answer' not in raw:
                continue
            try:
                item = json.loads(raw.decode('utf-8', 'replace'))
            except (TypeError, ValueError):
                continue
            if not isinstance(item, dict):
                continue
            if item.get('schema') != 'ist.ask_user.answer':
                continue
            outside_run_window = False
            if not_before is not None:
                try:
                    recorded_at = float(item.get('ts') or 0.0)
                except (TypeError, ValueError):
                    continue
                if recorded_at < not_before:
                    outside_run_window = True
            for binding in item.get('answer_bindings') or []:
                if not isinstance(binding, dict):
                    continue
                if str(binding.get('answer_key') or '') != key:
                    continue
                if question_digest and str(binding.get('question_digest') or '') != question_digest:
                    continue
                if outside_run_window and (str(item.get('question_id') or ''), key, str(binding.get('question_digest') or '')) not in replayed:
                    continue
                return True
    return False

def _record_lifecycle(question_id: str, phase: str, *, questions: list[dict[str, Any]] | None=None, channel: str='', outcome: str='', answers: dict[str, str] | None=None, reason: str='', wait_budget_s: float | None=None, deadline_at: float | None=None, owner: str='', thread_id: str='') -> tuple[bool, dict[str, Any]]:
    qid = str(question_id or '')
    if not qid or phase not in {'scheduled', 'presented', 'resolved'}:
        return (False, {})
    if bool(owner) != bool(thread_id):
        return (False, {})
    safe_questions = _persist_safe(questions or [])
    with _LIFECYCLE_LOCK:
        phases = _LIFECYCLE_PHASES.setdefault(qid, set())
        if phase in phases or 'resolved' in phases:
            return (False, {})
        if phase == 'presented' and 'scheduled' not in phases:
            return (False, {})
        record: dict[str, Any] = {'schema': _LIFECYCLE_SCHEMA, 'phase': phase, 'question_id': qid, 'owner': str(owner or ''), 'thread_id': str(thread_id or ''), 'ts': time.time(), 'render_version': _RENDER_VERSION}
        if phase == 'scheduled':
            record.update({'render_input': safe_questions, 'redacted_render_digest': _render_digest(safe_questions), 'option_tokens': _option_tokens(safe_questions), 'wait_budget_s': wait_budget_s, 'deadline_at': deadline_at})
        elif phase == 'presented':
            record.update({'channel': str(channel or 'unknown'), 'redacted_render_digest': _render_digest(safe_questions), 'option_tokens': _option_tokens(safe_questions)})
        else:
            record.update({'outcome': str(outcome or ''), 'accepted_answers': _persist_safe(dict(answers or {})), 'reason': _persist_safe(str(reason or '')), 'presented': 'presented' in phases})
        try:
            _append_lifecycle_record(record)
        except Exception:
            logger.exception('ask_user 生命周期账写入失败: question_id=%s phase=%s', qid, phase)
            if not phases:
                _LIFECYCLE_PHASES.pop(qid, None)
            return (False, {'question_id': qid, 'phase': phase, 'persistence_error': True})
        phases.add(phase)
    return (True, record)

def _render_terminal_replay(questions: list[dict[str, Any]], record: dict[str, Any]) -> str:
    outcome = str(record.get('outcome') or '')
    if outcome == 'answered':
        answers = record.get('accepted_answers') or {}
        if not isinstance(answers, dict):
            return 'error: persisted ask_user answer is invalid'
        positional: list[Any] = []
        for question in questions:
            keys = (str(question.get('question') or ''), str(question.get('header') or ''), str(question.get('answer_key') or ''))
            positional.append(next((answers[key] for key in keys if key and key in answers), None))
        answer_bindings = [{'answer_key': str(question.get('answer_key') or ''), 'question_digest': _render_digest([question])} for question, answer in zip(questions, positional) if str(question.get('answer_key') or '') and answer not in (None, '')]
        if answer_bindings:
            replay_record = {'schema': _LIFECYCLE_SCHEMA, 'phase': _ANSWER_REPLAYED_PHASE, 'question_id': str(record.get('question_id') or ''), 'owner': str(record.get('owner') or ''), 'thread_id': str(record.get('thread_id') or ''), 'ts': time.time(), 'render_version': _RENDER_VERSION, 'answer_bindings': answer_bindings}
            try:
                _append_lifecycle_record(replay_record)
            except Exception:
                logger.exception('ask_user answered 重放收据写入失败: question_id=%s', replay_record['question_id'])
                return 'error: persisted ask_user answer replay could not be recorded'
            with _LIFECYCLE_LOCK:
                _LIFECYCLE_PHASES.setdefault(replay_record['question_id'], set()).add(_ANSWER_REPLAYED_PHASE)
            _emit_lifecycle('ask_user_answer_replayed', replay_record)
        _publish_positional_answers(positional)
        header_by_q = {str(q.get('question', '')): str(q.get('header', '') or '') for q in questions}
        parts: list[str] = []
        for q_text, answer in answers.items():
            if isinstance(answer, list):
                answer = ', '.join((str(item) for item in answer))
            header = header_by_q.get(str(q_text), '')
            key = header or str(q_text)[:40] + ('…' if len(str(q_text)) > 40 else '')
            parts.append(f'"{key}"="{answer}"')
        return 'User has answered your questions: ' + '. '.join(parts)
    if outcome == 'timeout':
        return TIMEOUT_MARK
    if outcome in {'cancelled', 'teardown'}:
        return CANCEL_MARK
    if outcome == 'non_interactive':
        return 'error: ask_user previously resolved without an interactive channel'
    return 'error: persisted ask_user terminal outcome is unknown'

def _emit_lifecycle(kind: str, payload: dict[str, Any]) -> None:
    try:
        from cex_core.engine.ist_core.events import get_default_bus
        get_default_bus().emit(kind, payload=_persist_safe(payload), tags={'name': 'ask_user'})
    except Exception:
        logger.debug('ask_user 生命周期事件发射失败: %s', kind, exc_info=True)

def mark_presented(question_id: str, rendered_questions: list[dict[str, Any]], *, channel: str='ink_tui', owner: str='', thread_id: str='') -> bool:
    normalized, _error = _normalize_questions(rendered_questions)
    if normalized is None:
        return False
    rendered_questions = normalized
    payload: dict[str, Any] = {}
    with _PENDING_LOCK:
        pending = _PENDING.get(question_id)
        if pending is None or pending.get('outcome') is not None:
            return False
        if not _pending_authorized(pending, owner=owner, thread_id=thread_id):
            return False
        if _render_digest(rendered_questions) != _render_digest(list(pending.get('questions') or [])):
            return False
        if pending.get('presented') is True:
            return False
        accepted, record = _record_lifecycle(question_id, 'presented', questions=rendered_questions, channel=channel, owner=str(pending.get('owner') or ''), thread_id=str(pending.get('thread_id') or ''))
        if not accepted:
            if not (pending.get('recovered') and 'presented' in _LIFECYCLE_PHASES.get(question_id, set())):
                return False
            record = {'channel': channel, 'redacted_render_digest': _render_digest(rendered_questions), 'option_tokens': _option_tokens(rendered_questions), 'ts': time.time(), 'recovered': True}
        pending['presented'] = True
        payload = {'question_id': question_id, 'owner': str(pending.get('owner') or ''), 'thread_id': str(pending.get('thread_id') or ''), 'channel': record.get('channel', channel), 'redacted_render_digest': record.get('redacted_render_digest', ''), 'option_tokens': record.get('option_tokens', []), 'ts': record.get('ts'), 'recovered': bool(record.get('recovered'))}
    _emit_lifecycle('ask_user_presented', payload)
    return True

def _emit_resolved(question_id: str, outcome: str, *, answers: dict[str, str] | None=None, reason: str='', owner: str='', thread_id: str='') -> bool:
    accepted, record = _record_lifecycle(question_id, 'resolved', outcome=outcome, answers=answers, reason=reason, owner=owner, thread_id=thread_id)
    if not accepted:
        return False
    _emit_lifecycle('ask_user_resolved', {'question_id': question_id, 'owner': owner, 'thread_id': thread_id, 'outcome': outcome, 'answers': dict(answers or {}), 'reason': reason, 'presented': bool(record.get('presented')), 'ts': record.get('ts')})
    with _LIFECYCLE_LOCK:
        _QID_RESERVATIONS.discard(question_id)
    return True

def _configured_timeout_s() -> float:
    import os
    raw = os.environ.get('IST_ASK_TIMEOUT_S')
    try:
        value = float(raw if raw not in (None, '') else 0)
    except (TypeError, ValueError):
        logger.warning('IST_ASK_TIMEOUT_S=%r 非法，回落缺省（不超时）', raw)
        return 0.0
    if not math.isfinite(value):
        logger.warning('IST_ASK_TIMEOUT_S=%r 非有限值，回落缺省（不超时）', raw)
        return 0.0
    return value

def ask_user_with_timeout(questions: list[dict[str, Any]], *, timeout_s: float) -> str:
    previous = getattr(_WAIT_TIMEOUT_OVERRIDE, 'deadline', None)
    _WAIT_TIMEOUT_OVERRIDE.deadline = time.monotonic() + max(0.0, float(timeout_s))
    try:
        return ask_user.func(questions)
    finally:
        if previous is None:
            try:
                del _WAIT_TIMEOUT_OVERRIDE.deadline
            except AttributeError:
                pass
        else:
            _WAIT_TIMEOUT_OVERRIDE.deadline = previous

def get_pending_question(question_id: str, *, owner: str='', thread_id: str='') -> dict[str, Any] | None:
    with _PENDING_LOCK:
        pending = _PENDING.get(question_id)
        if pending is None or not _pending_authorized(pending, owner=owner, thread_id=thread_id):
            return None
        return pending

def pending_question_access(question_id: str, *, owner: str, thread_id: str) -> str:
    with _PENDING_LOCK:
        pending = _PENDING.get(str(question_id or ''))
        if pending is None:
            return 'missing'
        if _pending_authorized(pending, owner=owner, thread_id=thread_id):
            return 'authorized'
        return 'foreign'

def list_pending_questions(*, owner: str='', thread_id: str='') -> list[dict[str, Any]]:
    with _PENDING_LOCK:
        return [{'question_id': qid, **{k: v for k, v in q.items() if k != '_event'}} for qid, q in _PENDING.items() if _pending_authorized(q, owner=owner, thread_id=thread_id)]

def has_live_pending_questions() -> bool:
    with _PENDING_LOCK:
        return bool(_PENDING)

def cancel_all_pending(reason: str='', *, owner: str='', thread_id: str='') -> int:
    resolved: list[tuple[str, threading.Event]] = []
    with _PENDING_LOCK:
        for qid, pending in _PENDING.items():
            if not _pending_authorized(pending, owner=owner, thread_id=thread_id):
                continue
            evt = pending.get('_event')
            if pending.get('outcome') is None and evt is not None:
                pending['answers'] = {}
                pending['outcome'] = 'teardown'
                pending['reason'] = reason or 'session teardown'
                resolved.append((qid, evt))
    for qid, evt in resolved:
        pending = _PENDING.get(qid, {})
        _emit_resolved(qid, 'teardown', reason=reason or 'session teardown', owner=str(pending.get('owner') or ''), thread_id=str(pending.get('thread_id') or ''))
        evt.set()
    n = len(resolved)
    if n:
        logger.info('ask_user teardown:取消 %d 个挂起问询%s', n, f'({reason})' if reason else '')
    return n

def submit_answers(question_id: str, answers: dict[str, str], *, owner: str='', thread_id: str='') -> bool:
    expired = False
    resolved_record: dict[str, Any] = {}
    with _PENDING_LOCK:
        pending = _PENDING.get(question_id)
        if pending is None or pending.get('outcome') is not None or pending.get('answers') is not None:
            return False
        if not _pending_authorized(pending, owner=owner, thread_id=thread_id):
            return False
        bound_owner = str(pending.get('owner') or '')
        bound_thread = str(pending.get('thread_id') or '')
        deadline = pending.get('deadline_monotonic')
        if deadline is not None and time.monotonic() >= float(deadline):
            pending['answers'] = {}
            pending['outcome'] = 'timeout'
            pending['reason'] = 'wait deadline reached before answer submission'
            pending['terminal_event_emitted'] = True
            evt = pending.get('_event')
            expired = True
        else:
            accepted = dict(answers or {})
            outcome = 'answered' if any((str(v) for v in accepted.values())) else 'cancelled'
            reason = 'user submitted answers' if outcome == 'answered' else 'user cancelled'
            questions = list(pending.get('questions') or [])
            if outcome == 'answered':
                try:
                    _append_answer_credential(question_id, questions, accepted, owner=bound_owner, thread_id=bound_thread)
                except Exception:
                    logger.exception('ask_user 答案凭证写入失败: question_id=%s', question_id)
                    return False
            recorded, resolved_record = _record_lifecycle(question_id, 'resolved', outcome=outcome, answers=accepted, reason=reason, owner=bound_owner, thread_id=bound_thread)
            if not recorded:
                return False
            pending['answers'] = accepted
            pending['outcome'] = outcome
            pending['reason'] = reason
            evt = pending.get('_event')
    if expired:
        _emit_resolved(question_id, 'timeout', reason='wait deadline reached before answer submission', owner=bound_owner, thread_id=bound_thread)
        if evt is not None:
            evt.set()
        return False
    _emit_lifecycle('ask_user_resolved', {'question_id': question_id, 'owner': bound_owner, 'thread_id': bound_thread, 'outcome': outcome, 'answers': accepted, 'reason': reason, 'presented': bool(resolved_record.get('presented')), 'ts': resolved_record.get('ts')})
    if evt is not None:
        evt.set()
    return True
_REDECIDE_LOOKBACK_S = 6 * 3600.0
_ENGINE_PANEL_ORIGIN: 'contextvars.ContextVar[bool]' = contextvars.ContextVar('ist_engine_panel_origin', default=False)

@contextmanager
def engine_panel_origin():
    token = _ENGINE_PANEL_ORIGIN.set(True)
    try:
        yield
    finally:
        _ENGINE_PANEL_ORIGIN.reset(token)

def _recently_decided_autoids() -> dict[str, str]:
    import re as _re
    from pathlib import Path as _Path
    try:
        from cex_core.engine.knowledge_paths import WORKSPACE_OUTPUTS
        root = _Path(WORKSPACE_OUTPUTS)
        from cex_core.engine.ist_core.compile_engine.batch_storage import active_batch_fact_paths
        cands = sorted(active_batch_fact_paths(root), key=lambda x: x.stat().st_mtime, reverse=True)
    except Exception:
        return {}
    now = time.time()
    for fj in cands[:1]:
        try:
            if now - fj.stat().st_mtime > _REDECIDE_LOOKBACK_S:
                break
            decided: set[str] = set()
            terminal: set[str] = set()
            with open(fj, encoding='utf-8') as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    ev = d.get('ev')
                    if ev == 'run_start':
                        decided.clear()
                        terminal.clear()
                    elif ev == 'decision' and d.get('aid'):
                        decided.add(str(d['aid']))
                    elif ev == 'case_terminal_outcome' and d.get('aid'):
                        terminal.add(str(d['aid']))
            both = decided & terminal
            if both:
                try:
                    rel = str(fj.relative_to(root.parent.parent))
                except ValueError:
                    rel = str(fj)
                return {aid: rel for aid in both}
        except OSError:
            continue
    return {}

def _redecide_guard(questions: list[dict[str, Any]]) -> str | None:
    if _ENGINE_PANEL_ORIGIN.get():
        return None
    import re as _re
    text = ' '.join((str(q.get('question') or '') + ' ' + str(q.get('header') or '') for q in questions if isinstance(q, dict)))
    aids = set(_re.findall('(?<!\\d)\\d{18}(?!\\d)', text))
    tails = set(_re.findall('尾号\\s*[:：]?\\s*(\\d{4,18})', text))
    if not aids and (not tails):
        return None
    decided = _recently_decided_autoids()
    hit = sorted({a for a in decided if a in aids} | {a for a in decided for t in tails if a.endswith(t)})
    if not hit:
        return None
    ref = decided[hit[0]]
    return 'error: re-ask blocked — case(s) ' + ', '.join((f'…{a[-6:]}' for a in hit)) + f" were already decided AND reached terminal outcome in the batch that just closed (see `{ref}`: decision + case_terminal_outcome facts). The user's answers are final for that batch; read them from the facts instead of re-opening a panel. Drop those questions, or re-dispatch the batch if a genuinely new decision is needed."

@tool
def ask_user(questions: list[dict[str, Any]]) -> str:
    """Ask the user multiple choice questions to gather information, clarify ambiguity, understand preferences, or offer them choices.

    Use this tool when you need user input during execution, especially:
    1. To gather user preferences or requirements
    2. To clarify ambiguous instructions
    3. To get decisions on implementation choices
    4. To offer choices about direction (e.g. "Is this P0 a real bug or intentional?")

    Reserve this for decisions where the user's answer changes what you do next — not
    for choices with a conventional default or facts you can verify in the codebase
    yourself. In those cases pick the obvious option, mention it in your response,
    and proceed. A round-trip costs minutes when the user answers through WeCom, so look
    in the knowledge base (kb_footprint / kb_memory_search), the context and the request
    text first. The cases that do warrant a question: the request is ambiguous in a way
    that changes the operation; a device verdict needs a human call (product defect vs.
    case error); a mindmap lacks a field (expected result, steps) that no manual,
    precedent or knowledge source supplies — ask for it rather than invent it.

    Usage notes:
    - Users will always be able to select "Other" to provide custom text input
    - Use `multiSelect: true` to allow multiple answers to be selected for a question
    - If you recommend a specific option, make it the first option and add
      "(Recommended)" to its label

    `questions` is a list of 1-4 question dicts. Each question is a dict with:
      - `question` (str, required): the full question text, ending with `?`
      - `header` (str, required): a short label (≤ 12 chars) shown as a chip
      - `options` (list, required): 2-4 mutually exclusive options. Each option is
        `{label, description, preview?}`
      - `multiSelect` (bool, default false): allow multiple answers
      - `accepts_file` (bool, default false): this question can be answered by an
        attachment rather than text. On channels that carry files (WeCom), a file
        the user sends while the question is pending — or had already sent before
        it was asked — is auto-submitted as the answer with the saved path; set it
        only when an attachment genuinely answers the question (e.g. "评审对象在哪").

    Returns plain-text summary `User has answered your questions: "Q1"="A1". "Q2"="A2"`.
    """
    normalized, validation_error = _normalize_questions(questions)
    if normalized is None:
        return f'error: {validation_error}'
    questions = normalized
    blocked = _redecide_guard(questions)
    if blocked:
        return blocked
    hil_owner, hil_thread_id = _current_hil_identity()
    question_id, restored_phases, terminal_record = _allocate_question_id(questions, owner=hil_owner, thread_id=hil_thread_id)
    if terminal_record is not None:
        return _render_terminal_replay(questions, terminal_record)
    if not question_id:
        return 'error: an identical ask_user request is already pending'
    event = threading.Event()
    _timeout_s = _configured_timeout_s()
    _override_deadline = getattr(_WAIT_TIMEOUT_OVERRIDE, 'deadline', None)
    _now = time.monotonic()
    _wall_now = time.time()
    if _override_deadline is not None:
        _override_remaining_s = max(0.0, float(_override_deadline) - _now)
        _effective_timeout_s = min(_timeout_s, _override_remaining_s) if _timeout_s > 0 else _override_remaining_s
    else:
        _effective_timeout_s = _timeout_s if _timeout_s > 0 else None
    _restored_schedule = next((record for record in reversed(_lifecycle_records()) if record.get('question_id') == question_id and record.get('phase') == 'scheduled' and (str(record.get('owner') or '') == hil_owner) and (str(record.get('thread_id') or '') == hil_thread_id)), None)
    _restored_deadline_at: float | None = None
    if isinstance(_restored_schedule, dict):
        try:
            _restored_deadline_at = float(_restored_schedule.get('deadline_at'))
        except (TypeError, ValueError):
            try:
                budget = float(_restored_schedule.get('wait_budget_s'))
                _restored_deadline_at = float(_restored_schedule.get('ts')) + budget
            except (TypeError, ValueError):
                _restored_deadline_at = None
    if _restored_deadline_at is not None and _effective_timeout_s is not None:
        _effective_timeout_s = max(0.0, _restored_deadline_at - _wall_now)
        _deadline_at = _restored_deadline_at
    else:
        _deadline_at = _wall_now + max(0.0, float(_effective_timeout_s)) if _effective_timeout_s is not None else None
    _deadline = _now + max(0.0, float(_effective_timeout_s)) if _effective_timeout_s is not None else None
    pending = {'question_id': question_id, 'owner': hil_owner, 'thread_id': hil_thread_id, 'questions': questions, 'answers': None, 'outcome': None, 'reason': '', 'presented': False, 'terminal_event_emitted': False, 'recovered': bool(restored_phases), 'deadline_monotonic': _deadline, '_event': event}
    if 'scheduled' in restored_phases and 'resolved' not in restored_phases:
        scheduled_ok = True
        scheduled = {'question_id': question_id, 'render_version': _RENDER_VERSION, 'redacted_render_digest': _render_digest(questions), 'option_tokens': _option_tokens(questions), 'wait_budget_s': _effective_timeout_s, 'deadline_at': _deadline_at, 'ts': time.time(), 'recovered': True}
    else:
        scheduled_ok, scheduled = _record_lifecycle(question_id, 'scheduled', questions=questions, wait_budget_s=_effective_timeout_s, deadline_at=_deadline_at, owner=hil_owner, thread_id=hil_thread_id)
    if not scheduled_ok:
        with _LIFECYCLE_LOCK:
            _QID_RESERVATIONS.discard(question_id)
        return 'error: ask_user request could not be durably scheduled; no question was presented'
    with _PENDING_LOCK:
        _PENDING[question_id] = pending
    _emit_lifecycle('ask_user_scheduled', {'question_id': question_id, 'owner': hil_owner, 'thread_id': hil_thread_id, 'questions': _json_safe(questions), 'render_version': scheduled.get('render_version', _RENDER_VERSION), 'redacted_render_digest': scheduled.get('redacted_render_digest', ''), 'option_tokens': scheduled.get('option_tokens', []), 'wait_budget_s': _effective_timeout_s, 'ts': scheduled.get('ts'), 'recovered': bool(scheduled.get('recovered'))})
    import os as _os
    _non_interactive = (_os.environ.get('IST_NON_INTERACTIVE') or '').strip() in ('1', 'true', 'True')
    _wecom_bot = (_os.environ.get('IST_WECOM_BOT') or '').strip() in ('1', 'true', 'True')
    if _non_interactive and (not _wecom_bot):
        with _PENDING_LOCK:
            pending['answers'] = {}
            pending['outcome'] = 'non_interactive'
            pending['reason'] = 'no interactive channel'
            _PENDING.pop(question_id, None)
        _emit_resolved(question_id, 'non_interactive', reason='no interactive channel', owner=hil_owner, thread_id=hil_thread_id)
        _q_summary = ' | '.join((str(q.get('question', '')) for q in questions))
        return f'error: 当前为非交互模式（无 TUI，无法向用户提问），ask_user 不可用。请改为：从用户请求原文中提取该信息；若请求确实未提供该必要信息，请停止并明确报告『缺少哪项信息、为何无法在不询问用户的情况下继续』，不要臆测或自行选默认值。 你本想问的是：{_q_summary}'
    if _deadline is not None and time.monotonic() >= _deadline:
        with _PENDING_LOCK:
            pending['answers'] = {}
            pending['outcome'] = 'timeout'
            pending['reason'] = 'wait budget exhausted before presentation'
            pending['terminal_event_emitted'] = True
            _PENDING.pop(question_id, None)
        _emit_resolved(question_id, 'timeout', reason='wait budget exhausted before presentation', owner=hil_owner, thread_id=hil_thread_id)
        return TIMEOUT_MARK
    _emit_lifecycle('ask_user_request', {'question_id': question_id, 'owner': hil_owner, 'thread_id': hil_thread_id, 'questions': _json_safe(questions)})
    try:
        import sys as _sys
        from cex_core.engine.ist_core.security_scrub import scrub_text
        _qs = '; '.join((str(q.get('question', '')) + ' [' + '/'.join((str(o.get('label', '')) for o in q.get('options') or [])) + ']' for q in questions))
        print(f'[ask_user] agent 提问: {scrub_text(_qs)}', file=_sys.stderr, flush=True)
    except Exception:
        pass
    _wait_s = None if _deadline is None else max(0.0, _deadline - time.monotonic())
    _answered_in_time = event.wait(timeout=_wait_s)
    emit_timeout = False
    with _PENDING_LOCK:
        outcome = str(pending.get('outcome') or '')
        if not outcome:
            outcome = 'timeout' if not _answered_in_time else 'cancelled'
            pending['answers'] = {}
            pending['outcome'] = outcome
            pending['reason'] = 'wait deadline reached' if outcome == 'timeout' else 'question ended without answer'
        answers = dict(pending.get('answers') or {})
        reason = str(pending.get('reason') or '')
        if outcome == 'timeout' and (not pending.get('terminal_event_emitted')):
            pending['terminal_event_emitted'] = True
            emit_timeout = True
        _PENDING.pop(question_id, None)
    if outcome != 'answered':
        if outcome == 'timeout':
            if emit_timeout:
                _emit_resolved(question_id, 'timeout', reason=reason, owner=hil_owner, thread_id=hil_thread_id)
            return TIMEOUT_MARK
        return CANCEL_MARK
    header_by_q = {str(q.get('question', '')): str(q.get('header', '') or '') for q in questions}
    _publish_positional_answers([answers.get(str(q.get('question', ''))) for q in questions])
    parts = []
    for q_text, a in answers.items():
        if isinstance(a, list):
            a = ', '.join((str(x) for x in a))
        h = header_by_q.get(str(q_text), '')
        key = h if h else str(q_text)[:40] + ('…' if len(str(q_text)) > 40 else '')
        parts.append(f'"{key}"="{a}"')
    return 'User has answered your questions: ' + '. '.join(parts)
