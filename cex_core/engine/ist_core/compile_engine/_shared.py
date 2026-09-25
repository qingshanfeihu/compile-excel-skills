# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/_shared.py（sha256 0527fcd83855b091）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import contextlib
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from contextvars import ContextVar
from collections import Counter
from pathlib import Path
from typing import Any, Mapping
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.ist_core.compile_engine import engine_errors as EE
from cex_core.engine.ist_core.compile_engine import facts as F
from cex_core.engine.ist_core.compile_engine import views as V
logger = logging.getLogger(__name__)
_ENGINE_NODE_CONTEXT: ContextVar[tuple[dict, str] | None] = ContextVar('engine_node_error_context', default=None)

@contextlib.contextmanager
def engine_node_context(state: dict, node: str):
    token = _ENGINE_NODE_CONTEXT.set((state, node))
    try:
        yield
    finally:
        _ENGINE_NODE_CONTEXT.reset(token)

def current_engine_node_context() -> tuple[dict, str] | None:
    return _ENGINE_NODE_CONTEXT.get()

def require_current_compile_context(state: dict) -> None:
    if not state.get('compile_context_sha256'):
        return
    from cex_core.engine.ist_core.compile_engine.engine_tool import _assert_compile_context_current
    _assert_compile_context_current(project_root=project_root(), outputs_root=outputs_root(), out_name=str(state.get('out_name') or ''), mindmap_path=str(state.get('mindmap_path') or ''), product_version=str(state.get('product_version') or ''), local_xml_ref=str(state.get('local_command_tree_xml') or ''), expected_local_xml_sha256=str(state.get('local_command_tree_xml_sha256') or ''))
_AID_LEASES: dict[str, dict[str, object]] = {}

def acquire_aid_leases(out_name: str, aids) -> list[str]:
    import errno
    import fcntl
    held = _AID_LEASES.setdefault(str(out_name), {})
    conflicts: list[str] = []
    lock_dir = project_root() / 'runtime' / 'locks'
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.warning('aid 租约目录不可用——本批在无 aid 级互斥下运行', exc_info=True)
        return []
    for raw in aids:
        try:
            aid = safe_output_component(str(raw), field='autoid')
        except ValueError:
            logger.warning('跳过不安全的租约 autoid:%r', raw)
            continue
        if aid in held:
            continue
        holder = next((n for n, m in _AID_LEASES.items() if n != str(out_name) and aid in m), '')
        if holder:
            conflicts.append(f'{aid}(本进程批 {holder!r} 持有)')
            continue
        try:
            fh = open(lock_dir / f'compile_aid_{aid}.lock', 'a+')
        except OSError:
            logger.warning('aid 租约锁文件不可开(%s)——该 aid 无互斥', aid, exc_info=True)
            continue
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            try:
                fh.close()
            except Exception:
                pass
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                conflicts.append(f'{aid}(另一活进程持有)')
            else:
                logger.warning('aid 租约 flock 不可用(%s, errno=%s)——该 aid 无互斥', aid, exc.errno)
        else:
            held[aid] = fh
    if conflicts:
        release_aid_leases(out_name)
    return conflicts

def release_aid_leases(out_name: str) -> None:
    for fh in _AID_LEASES.pop(str(out_name), {}).values():
        try:
            fh.close()
        except Exception:
            pass

def aid_leased_by(out_name: str, aid: str) -> bool | None:
    held = _AID_LEASES.get(str(out_name))
    if not held:
        return None
    return str(aid) in held
PANEL_QID_PREFIX = 'panel:'
SUSPEND_KIND_REGISTRY: dict[str, dict[str, bool]] = {'panel': {'renders_as_no_answer': True, 'resume_reopenable': True}, 'cap': {'renders_as_no_answer': True, 'resume_reopenable': True}, 'contra': {'renders_as_no_answer': True, 'resume_reopenable': True}, 'nd': {'renders_as_no_answer': True, 'resume_reopenable': True}, 'env': {'renders_as_no_answer': True, 'resume_reopenable': False}, 'bed': {'renders_as_no_answer': False, 'resume_reopenable': False}, 'resume': {'renders_as_no_answer': False, 'resume_reopenable': False}, 'bed_gate': {'renders_as_no_answer': False, 'resume_reopenable': False}, 'bedclosure': {'renders_as_no_answer': False, 'resume_reopenable': False}, 'execution_pause': {'renders_as_no_answer': False, 'resume_reopenable': True}}

def suspend_kind_renders_as_no_answer(kind: str) -> bool:
    return bool(SUSPEND_KIND_REGISTRY.get(kind, {}).get('renders_as_no_answer'))

def suspend_kind_resume_reopenable(kind: str) -> bool:
    return bool(SUSPEND_KIND_REGISTRY.get(kind, {}).get('resume_reopenable'))
_USER_DECISION_REOPEN_KINDS: frozenset[str] = frozenset({'改描述', 'suspend'})
_USER_DECISION_KIND_ALIASES: dict[str, str] = {'挂起': 'suspend'}

def classify_suspend_reason(reason: 'str | Mapping[str, object]') -> tuple[str, str]:
    if isinstance(reason, Mapping):
        kind = str(reason.get('suspension_kind') or '')
        if not kind and str(reason.get('pause_kind') or '').strip():
            kind = 'execution_pause'
        if kind:
            if kind not in SUSPEND_KIND_REGISTRY:
                return ('unknown', kind)
            return ('reopen' if suspend_kind_resume_reopenable(kind) else 'no_reopen', kind)
        reason = str(reason.get('reason') or '')
    reason = str(reason or '')
    if not reason:
        return ('no_reopen', '')
    if reason.startswith('auto:'):
        kind = reason[len('auto:'):].split(':', 1)[0]
        if kind not in SUSPEND_KIND_REGISTRY:
            return ('unknown', kind)
        return ('reopen' if suspend_kind_resume_reopenable(kind) else 'no_reopen', kind)
    if reason.startswith('keep:'):
        return ('no_reopen', 'keep')
    if reason.startswith('user_decision:'):
        kind = reason[len('user_decision:'):].split(':', 1)[0]
        kind = _USER_DECISION_KIND_ALIASES.get(kind, kind)
        if kind not in _USER_DECISION_REOPEN_KINDS:
            return ('unknown', kind)
        return ('reopen', kind)
    return ('unknown', '')

def suspend_reason_embedded_qid(reason: str) -> str:
    reason = str(reason or '')
    prefix = 'user_decision:suspend:'
    if not reason.startswith(prefix):
        return ''
    return reason[len(prefix):]

def require_suspend_kind_known(reason: str | Mapping[str, object]) -> None:
    disposition, kind = classify_suspend_reason(reason)
    if disposition == 'unknown':
        raise AssertionError(f'suspended.reason={reason!r} 解析出的 kind={kind!r} 不在 内部工单 登记的闭集内——新 kind 请先在 _shared.py 的 SUSPEND_KIND_REGISTRY / _USER_DECISION_REOPEN_KINDS 登记,再落地这个写点')

def project_root() -> Path:
    return _cex_data_path('')

def outputs_root() -> Path:
    """当前作用域的 outputs 根；project_root 保持可注入（测试打到 tmp）。

    用户段问 ``knowledge_paths.output_scope()``——与读写闸同一个权威。
    编译交付物放在 ``workspace/outputs/<user>/<batch>/``。
    """
    from cex_core.engine import knowledge_paths as _kp
    return _kp.scoped_bucket_root('outputs', project_root=project_root())

def inputs_root() -> Path:
    """当前作用域的 inputs 根，与 ``outputs_root()`` 同一套 ``output_scope()``。"""
    from cex_core.engine import knowledge_paths as _kp
    return _kp.scoped_bucket_root('inputs', project_root=project_root())

def compile_tenant_token() -> str:
    """多租户下的租户段；单租户返回空串。

    早先用 ``"local"`` 当单租户哨兵，而 ``local`` 落在合法租户字符集里
    （``validate_output_scope("local") == "local"``）：真叫 local 的租户会被判成单
    租户，锁名与线程 id 跟单租户 TUI 逐字重合，互斥与 cursor 回收一起失效。分支
    判据改成 ``multi_tenant()`` 布尔，不靠字符串比对。
    """
    from cex_core.engine.knowledge_paths import multi_tenant, output_scope
    if not multi_tenant():
        return ''
    return output_scope()

def compile_lock_filename(name: str) -> str:
    """``runtime/locks/`` 里那把跨进程互斥锁的文件名，口径与 ``_compile_thread_id`` 逐字对齐。

    单租户（TUI）保持 ``compile_run_{批名}.lock``：换了名字就等于把旧进程持有的那把
    锁变成看不见——升级前后两个进程会同时跑同一批，而互斥正是这把锁存在的理由。
    多租户用 ``:`` 分隔而不是 ``_``：``_SCOPE_RE`` 允许 ``_``、``safe_output_component``
    也允许，``{租户}_{批名}`` 因此有歧义（租户 alice + 批 b 与单租户批 alice_b 撞同一
    个文件名）；``:`` 不在租户字符集内，第一个冒号必然是分隔符。

    住在这里而不是 ``engine_tool``：同一把锁有三个持有方（引擎图、
    ``authoring_services._batch_service_lock``、``_studio_run_guard._acquire``），
    后两个 import 不到 ``engine_tool``（循环导入）。名字各拼各的就不是一把锁了。
    """
    return f'compile_run_{compile_batch_registry_key(name)}.lock'

def compile_batch_registry_key(name: str) -> str:
    """进程内按批登记时的键。与锁文件名同一个租户段，同一条判据。

    只按批名键时，两个租户的同名批会被判成同一个批：先到的那个把后到的挡在外面，
    而「被挡住了」本身就告诉后者另一个租户正在跑一个叫这个名字的批。
    """
    tenant = compile_tenant_token()
    return f'{tenant}:{name}' if tenant else name

def safe_output_component(value: str, *, field: str='out_name') -> str:
    name = str(value or '').strip()
    if not name or name in {'.', '..'} or Path(name).is_absolute() or ('/' in name) or ('\\' in name) or ('~' in name) or any((ord(ch) < 32 for ch in name)) or (len(name) > 180):
        raise ValueError(f'{field} must be one safe directory name under workspace/outputs')
    root = outputs_root()
    candidate = root / name
    if candidate.is_symlink():
        raise ValueError(f'{field} resolves through a symbolic-link directory')
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f'{field} escapes workspace/outputs') from exc
    return name

def facts_path(state: dict) -> Path:
    name = safe_output_component(str(state.get('out_name') or 'engine'), field='out_name')
    ref = str(state.get('facts_ref') or '')
    if ref:
        candidate = project_root() / ref
        expected_parent = outputs_root() / name
        try:
            if candidate.is_symlink():
                raise ValueError('facts_ref must not be a symbolic link')
            resolved = candidate.resolve()
            resolved.relative_to(expected_parent.resolve())
        except ValueError as exc:
            raise ValueError('facts_ref must stay inside the bound output batch') from exc
        if resolved.parent != expected_parent.resolve() or resolved.name != 'facts.jsonl':
            raise ValueError('facts_ref must identify the bound batch facts.jsonl')
        return candidate
    return outputs_root() / name / 'facts.jsonl'

def load_facts(state: dict) -> list[dict]:
    return F.load_facts(facts_path(state))

def require_decision_identity(new_facts: list[dict]) -> None:
    for index, fact in enumerate(new_facts):
        if str(fact.get('ev') or '') != 'decision':
            continue
        if str(fact.get('token') or '').strip():
            continue
        if fact.get('freeform') is True:
            continue
        raise ValueError(f"decision fact requires a non-empty token or freeform=true (index={index}, question_id={fact.get('question_id', '')!r})")

def append(state: dict, new_facts: list[dict]) -> int:
    from cex_core.engine.ist_core.compile_engine.engine_quarantine import transition_lock
    with transition_lock(facts_path(state)):
        return _append_with_admission(state, new_facts)

def _append_with_admission(state: dict, new_facts: list[dict]) -> int:
    from cex_core.engine.ist_core.security_scrub import scrub_value
    require_decision_identity(new_facts)
    safe_facts = scrub_value(new_facts, scrub_paths=False)
    from cex_core.engine.ist_core.compile_engine import engine_checkpoints as EC, engine_quarantine as EQ
    existing = load_facts(state)
    accepted = []
    for fact in safe_facts:
        if fact.get('ev') == EQ.RELEASE_EVENT:
            EQ.validate_release_at_write(project_root(), fact, existing + accepted)
        if fact.get('ev') == 'engine_condition_disclosure':
            EC.validate_condition_disclosure(fact)
            accepted.append(fact)
            if fact.get('scope') == 'batch':
                accepted.append({'ev': 'batch_execution_paused', 'aid': '', 'diagnostic_id': fact['diagnostic_id'], 'source_fact_sha256': __import__('cex_core.engine.ist_core.compile_engine.terminal_credentials', fromlist=['_fact_sha256'])._fact_sha256(fact), 'reason': 'a required batch condition is unavailable; responsibility is unverified', 'revoked_dispatch_ids': sorted({str(row['dispatch_id']) for row in F.this_run_slice(existing + accepted) if row.get('ev') == 'worker_dispatch_started' and row.get('dispatch_id')})})
            elif fact.get('aid'):
                aid = str(fact['aid'])
                mine = [row for row in existing + accepted if row.get('aid') == aid]
                explicit_pause = any((row.get('ev') == 'suspended' and row.get('aid') == aid and (row.get('suspension_kind') == 'execution_pause') for row in safe_facts))
                if not explicit_pause and (not V.active_execution_pause(mine)):
                    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
                    accepted.extend([{'ev': 'de_escalated', 'aid': aid, 'note': 'auto: preserve the observed condition and pause this invocation'}, {'ev': 'suspended', 'aid': aid, 'source': 'engine_auto', 'suspension_kind': 'execution_pause', 'pause_kind': 'engine_condition', 'question_id': 'condition-pause:' + fact['diagnostic_id'], 'reason': '已记录当前条件或校验异常，本轮暂挂；责任方尚未确认。', 'source_event': fact['ev'], 'source_fact_sha256': _fact_sha256(fact), 'basis_status': 'source_bound', 'resume_stage': 'author'}])
            continue
        from cex_core.engine.ist_core.compile_engine.authoring_evidence import uses_new_policy
        unverified_authoring = False
        if fact.get('ev') == 'authoring_failure' and uses_new_policy(existing + accepted):
            from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
            try:
                issued = TC.build_verified_authoring_failure_fact(aid=str(fact.get('aid') or ''), facts=existing + accepted)
                unverified_authoring = issued != {k: v for k, v in fact.items() if not k.startswith('_')}
            except (ValueError, KeyError, OSError):
                unverified_authoring = True
        if uses_new_policy(existing + accepted) and (fact.get('ev') == 'attribution' and fact.get('disposition') == 'engineering_fault' or unverified_authoring):
            accepted.append({'ev': 'unconfirmed_terminal_claim', 'aid': fact.get('aid') or '', 'original_record': fact, 'reason': 'the legacy terminal label has no current proof'})
            aid = str(fact.get('aid') or '')
            if aid:
                from cex_core.engine.ist_core.compile_engine.authoring_evidence import incomplete_evidence_terminal
                terminal = incomplete_evidence_terminal(existing + accepted, aid=aid, source=accepted[-1], round_no=F.effective_rounds_used(existing + accepted, aid))
                if terminal is not None:
                    accepted.append(terminal)
            continue
        from cex_core.engine.ist_core.compile_engine import forced_closure as _FC_BOOK
        if fact.get('ev') in EQ.INVALIDATABLE_EVENTS and str(fact.get('aid') or '') and (not _FC_BOOK.is_closing_bookkeeping(fact)):
            try:
                EQ.require_admission(existing + accepted, aid=str(fact['aid']), dispatch_id=str(fact.get('dispatch_id') or ''), batch_run_id=str(fact.get('batch_run_id') or ''), dispatch_event=F.EXECUTION_DISPATCH_EVENTS.get(str(fact.get('ctx') or ''), 'worker_dispatch_started'))
            except ValueError as exc:
                accepted.append({'ev': 'quarantined_result', 'aid': fact['aid'], 'original_event': fact['ev'], 'original_record': fact, 'reason': str(exc), 'admission_status': 'denied'})
                aid = str(fact['aid'])
                mine = [row for row in existing + accepted if row.get('aid') == aid]
                if not EQ.batch_halted(existing + accepted) and aid not in EQ.quarantined_aids(existing + accepted) and (not V.active_execution_pause(mine)):
                    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
                    rejected = accepted[-1]
                    accepted.extend([{'ev': 'de_escalated', 'aid': aid, 'note': 'auto: preserve the result and pause on an unverified dispatch identity'}, {'ev': 'suspended', 'aid': aid, 'source': 'engine_auto', 'suspension_kind': 'execution_pause', 'pause_kind': 'engine_condition', 'source_event': rejected['ev'], 'source_fact_sha256': _fact_sha256(rejected), 'question_id': 'result-identity:' + _fact_sha256(rejected), 'basis_status': 'source_bound', 'resume_stage': 'run', 'reason': '结果身份未通过本轮准入核验，保留原件并暂挂；责任方未确认。'}])
                continue
        accepted.append(fact)
        if fact.get('schema') == EC.SCHEMA and fact.get('ev') == 'engine_error':
            EC.validate_error(fact)
            population = [str(c.get('autoid') or '') for c in manifest(state).get('cases', [])]
            accepted.extend(EQ.quarantine_facts(fact, existing + accepted, population=population))
            if fact.get('owner') == 'api' and fact.get('scope') == 'batch':
                accepted.append({'ev': 'batch_execution_paused', 'aid': '', 'pause_kind': 'api', 'error_id': fact['error_id'], 'source_record_sha256': fact['record_sha256'], 'reason': 'The recorded API response paused batch execution; no engine defect was confirmed.', 'revoked_dispatch_ids': sorted({str(row['dispatch_id']) for row in F.this_run_slice(existing + accepted) if row.get('ev') == 'worker_dispatch_started' and row.get('dispatch_id')})})
    from cex_core.engine.ist_core.compile_engine import engine_errors as EE
    recorded_disclosures = {row.get('diagnostic_id') for row in existing + accepted if row.get('ev') == EE.UNVERIFIABLE_ERROR_EVENT}
    for row in EE.unverifiable_error_disclosures(existing + accepted):
        if row['diagnostic_id'] not in recorded_disclosures:
            accepted.append(row)
            recorded_disclosures.add(row['diagnostic_id'])
    count = F.append_facts(facts_path(state), accepted)
    if any((f.get('ev') in {EQ.QUARANTINE_EVENT, 'engine_halt', 'batch_execution_paused'} for f in accepted)):
        from cex_core.engine.ist_core.worker_device_context import revoke_worker_dispatch
        for f in accepted:
            for dispatch_id in f.get('revoked_dispatch_ids', []):
                revoke_worker_dispatch(dispatch_id)
    for fact in accepted:
        if fact.get('schema') != EC.SCHEMA or fact.get('ev') != 'engine_error' or fact.get('owner') != 'engine':
            continue
        followups = []
        try:
            from cex_core.engine.ist_core.compile_engine.engine_debt import record_error
            record_error(project_root(), fact)
        except (OSError, ValueError) as exc:
            followups.append({'ev': 'engine_debt_index_unavailable', 'error_id': fact['error_id'], 'error': type(exc).__name__})
        try:
            from cex_core.engine.ist_core.compile_engine.engine_incidents import capture_incident
            followups.append(capture_incident(state, fact, load_facts(state)))
        except (OSError, ValueError) as exc:
            followups.append({'ev': 'engine_incident_capture', 'error_id': fact['error_id'], 'status': 'incomplete', 'error': type(exc).__name__})
        if followups:
            F.append_facts(facts_path(state), scrub_value(followups, scrub_paths=False))
    return count

class ManifestUnavailable(RuntimeError):

    def __init__(self, path: str, detail: str):
        self.path = str(path)
        self.detail = str(detail)
        super().__init__(f'{self.path}: {self.detail}')

def is_bound_manifest_error(state: dict, exc: object) -> bool:
    if not isinstance(exc, (ManifestUnavailable, LedgerCorruptError)):
        return False
    source = str(getattr(exc, 'path', '') or '')
    if not source:
        return False
    try:
        name = safe_output_component(str(state.get('out_name') or 'engine'), field='out_name')
        expected = (outputs_root() / name / 'manifest.json').resolve()
        candidate = Path(source)
        if not candidate.is_absolute():
            candidate = project_root() / candidate
        return candidate.resolve() == expected
    except (OSError, ValueError):
        return False

def manifest(state: dict) -> dict:
    name = safe_output_component(str(state.get('out_name') or 'engine'), field='out_name')
    expected = outputs_root() / name / 'manifest.json'
    ref = str(state.get('manifest_ref') or '')
    candidate = project_root() / ref if ref else expected
    try:
        if candidate.is_symlink():
            raise ValueError('manifest_ref must not be a symbolic link')
        resolved = candidate.resolve()
        if resolved != expected.resolve():
            raise ValueError('manifest_ref must identify the bound batch manifest.json')
    except (OSError, ValueError) as exc:
        raise ValueError('manifest_ref must stay inside the bound output batch') from exc
    payload = read_json_checked(candidate, None)
    if payload is None:
        raise ManifestUnavailable(str(candidate), 'bound batch manifest.json is missing')
    if not isinstance(payload, dict):
        raise LedgerCorruptError(str(candidate), 'manifest must be a JSON object')
    cases = payload.get('cases')
    if not isinstance(cases, list):
        raise LedgerCorruptError(str(candidate), 'manifest.cases must be an array')
    if not cases:
        raise ManifestUnavailable(str(candidate), 'bound batch manifest contains no cases')
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise LedgerCorruptError(str(candidate), f'manifest.cases[{index}] must be an object')
        aid = str(case.get('autoid') or '')
        try:
            safe_output_component(aid, field='autoid')
        except ValueError as exc:
            raise LedgerCorruptError(str(candidate), f'manifest.cases[{index}].autoid is not a safe path component') from exc
        if aid in seen:
            raise LedgerCorruptError(str(candidate), f'duplicate manifest autoid: {aid}')
        seen.add(aid)
    return payload

def _live_capability_projection_sha256(sync_fact: dict | None) -> str:
    if not isinstance(sync_fact, dict):
        return ''
    product = str(sync_fact.get('product') or '').strip()
    platform = str(sync_fact.get('platform') or '').strip()
    version = str(sync_fact.get('version') or '').strip()
    device_build = str(sync_fact.get('device_build_tail') or '').strip()
    if not (product and platform and version and device_build):
        return ''
    try:
        from cex_core.engine.sync.command_tree_sync import resolve_active_command_tree
        resolved = resolve_active_command_tree(product=product, platform=platform, version=version, device_build=device_build)
    except Exception:
        return ''
    sha = str(getattr(resolved, 'projection_sha256', '') or '').strip().lower()
    return sha if re.fullmatch('[0-9a-f]{64}', sha) else ''

def _live_governing_spec_sha256(recompose_fact: dict, batch_name: str) -> str:
    status = str(recompose_fact.get('governing_spec_status') or '').strip()
    if status == 'bound':
        spec_name = str(recompose_fact.get('governing_spec') or '').strip()
        if not spec_name:
            return ''
        try:
            from cex_core.engine.kms.spec_index import resolve_indexed_spec
            resolved = resolve_indexed_spec(project_root(), spec_name)
        except Exception:
            return ''
        sha = str(getattr(resolved, 'sha256', '') or '').strip().lower()
        return sha if re.fullmatch('[0-9a-f]{64}', sha) else ''
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
        raw = read_regular_nofollow(outputs_root() / batch_name / 'governing_spec_status.json', error_type=ValueError, invalid_message='governing spec status path is invalid', directory_message='governing spec status parent is unavailable', open_message='governing spec status is unavailable', bounds_message='governing spec status exceeds its sealed boundary', changed_message='governing spec status changed while hashing', max_bytes=4 * 1024 * 1024, min_bytes=1)
        assert isinstance(raw, bytes)
    except Exception:
        return ''
    return hashlib.sha256(raw).hexdigest()

def batch_conflict_bindings(state: dict, fs: list[dict] | None=None) -> dict[str, str]:
    """复算 §2.4 批级 ASK 的三个不可变输入身份。

    用例身份是绑定 ``manifest.json`` 的发布字节 SHA；能力身份只认当前床同步后
    的投影 SHA；SPEC 存在时取文档内容 SHA，不存在时取密封的 governing-status
    receipt SHA，使“本轮确实无管辖 SPEC”也有不可伪造的输入身份。任一位缺失或
    畸形都返回空串，由 ASK/消费规则 fail closed，绝不签一个可被旧答案复用的残缺轮次。

    **三轴一律现读盘（2026-08-13 符合性审查 D18）**：§2.4:338-341 逐字「一轮 = 一次
    **携带修改的新对话**……任一 sha 变 → 旧答案自动失效，重走判定链」。三个 sha 说的
    都是**输入**的当前状态。manifest 轴一直是现读；能力与 SPEC 两轴此前只回读台账
    ——能力取上一条 ``capability_synced``、SPEC 取上一条 ``recompose_done``，而这两条
    事实本轮的写点都在重入闸**之后**（``capability_synced`` 在 bed_gate、
    ``recompose_done`` 在 recompose 尾）。于是闸拿上一轮的身份和上一轮的答案对比，
    恒定相等：改了 XML 或 SPEC 也要等下一轮才生效（只读复现坐实——第 2 轮闸零新增
    事实，补一条新 ``capability_synced`` 或 ``recompose_done`` 后立刻产
    ``conflict_chain_reentered(round=2)``）。现在两轴都按台账记下的**身份**去盘上取
    当前字节，取不到才回落台账值（回落＝维持旧行为，不制造新的假重入）。

    **残留边界（现读也看不见的两种改动，仍慢一轮）**：① 设备升级换 build——命令树
    按 build 分区，闸跑在 bed_gate 之前，只能用上一条 ``capability_synced`` 的四元
    身份解析，指向的还是旧分区；② 原本没有管辖 SPEC、这一轮新加了一份——SPEC 定位
    要用脑图根标题，那是 recompose 在闸之后才解析的。两者都由下一轮的闸捕获。
    """
    manifest(state)
    name = safe_output_component(str(state.get('out_name') or 'engine'), field='out_name')
    manifest_path = outputs_root() / name / 'manifest.json'
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
        raw = read_regular_nofollow(manifest_path, error_type=ValueError, invalid_message='bound manifest path is invalid', directory_message='bound manifest parent is unavailable', open_message='bound manifest is unavailable', bounds_message='bound manifest exceeds its sealed size boundary', changed_message='bound manifest changed while hashing', max_bytes=32 * 1024 * 1024, min_bytes=1, require_current_uid=True)
        assert isinstance(raw, bytes)
        manifest_sha = hashlib.sha256(raw).hexdigest()
    except Exception:
        manifest_sha = ''
    timeline = fs if fs is not None else load_facts(state)
    capability_sha = str(state.get('capability_projection_sha256') or '').strip().lower()
    if re.fullmatch('[0-9a-f]{64}', capability_sha) is None:
        last_sync = next((fact for fact in reversed(timeline) if fact.get('ev') == 'capability_synced' and re.fullmatch('[0-9a-f]{64}', str(fact.get('projection_sha256') or '').strip().lower())), None)
        capability_sha = str((last_sync or {}).get('projection_sha256') or '').strip().lower()
        live_capability = _live_capability_projection_sha256(last_sync)
        if live_capability:
            capability_sha = live_capability
    spec_sha = ''
    for fact in reversed(timeline):
        if fact.get('ev') != 'recompose_done':
            continue
        direct = str(fact.get('governing_spec_sha256') or '').strip().lower()
        status = str(fact.get('governing_spec_status_sha256') or '').strip().lower()
        if re.fullmatch('[0-9a-f]{64}', direct):
            spec_sha = direct
        elif re.fullmatch('[0-9a-f]{64}', status):
            spec_sha = status
        live_spec = _live_governing_spec_sha256(fact, name)
        if live_spec:
            spec_sha = live_spec
        break
    return {'case_manifest_sha256': manifest_sha, 'capability_projection_sha256': capability_sha, 'governing_spec_sha256': spec_sha}

def view(state: dict, fs: list[dict] | None=None) -> dict:
    if fs is None:
        fs = load_facts(state)
    vw = V.batch_view(fs, manifest(state))
    for aid in deesc_recovery_waiting(state, fs, vw):
        c = vw['cases'].get(aid)
        if c is not None and c['status'] == V.S_ESCALATED:
            c['status'] = V.S_AWAITING_USER
    _quarantined_this_run = {str(f.get('aid')) for f in F.this_run_slice(fs) if f.get('ev') == 'recompose_case_quarantined' and f.get('aid')}
    for aid in _quarantined_this_run:
        c = vw['cases'].get(aid)
        if c is not None and (not V.is_settled(c['status'])):
            c['status'] = V.S_TERMINAL
    vw['counts'] = dict(Counter((v['status'] for v in vw['cases'].values())))
    return vw

def case_rows(aid: str) -> list[dict]:
    from cex_core.engine.ist_core.tools.device.package_registry_tool import _load_case_rows as _l
    p = outputs_root() / aid / 'case.xlsx'
    try:
        return _l(str(p)) if p.is_file() else []
    except Exception:
        return []

def emit_summary(state: dict, summary: dict) -> None:
    try:
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        _fork_emit_event({'event': 'engine_summary', 'run': str(state.get('out_name') or 'engine'), **summary})
    except Exception:
        logger.debug('engine summary emit 失败', exc_info=True)

def granted_rounds(fs: list[dict], aid: str) -> int:
    from cex_core.engine.ist_core.compile_engine.questions import effective_decision_token
    n = 0
    for f in fs:
        if f.get('ev') == 'decision' and str(f.get('aid')) == aid and str(f.get('question_id', '')).startswith('cap:'):
            tok = effective_decision_token(f)
            if tok in ('continue', 'correct') or (not tok and '继续' in str(f.get('answer', ''))):
                n += 2
    return n

def env_qid(aid: str, mine: list[dict]) -> str:
    seq = sum((1 for d in mine if d.get('ev') == 'decision' and str(d.get('question_id', '')).startswith(f'env:{aid}:'))) + 1
    return f'env:{aid}:{seq}'

def env_confirm_waiting(fs: list[dict], vw: dict) -> list[str]:
    out = []
    for aid, c in vw['cases'].items():
        if c['status'] in (V.S_DELIVERABLE, V.S_TERMINAL, V.S_SUSPENDED, V.S_ESCALATED, V.S_UNSUPPORTED_FEATURE):
            continue
        mine = [f for f in fs if str(f.get('aid')) == aid]
        atts = [f for f in mine if f.get('ev') == 'attribution']
        if not atts or str(atts[-1].get('disposition')) != 'env_blocked':
            continue
        if V._user_sourced(atts[-1]):
            continue
        pos = max((i for i, f in enumerate(mine) if f.get('ev') == 'attribution'), default=-1)
        answered = any((i > pos and f.get('ev') == 'decision' and str(f.get('question_id', '')).startswith(f'env:{aid}:') for i, f in enumerate(mine)))
        if not answered:
            out.append(aid)
    return out

def panel_qid_matches(question_id: object, aid: str, round_number: int) -> bool:
    base = f'{PANEL_QID_PREFIX}{aid}:{int(round_number)}'
    value = str(question_id or '')
    if value == base:
        return True
    prefix = f'{base}:'
    if not value.startswith(prefix):
        return False
    suffix = value[len(prefix):]
    return bool(re.fullmatch('(?:[2-9]|[1-9]\\d+)\\d*', suffix))

def panel_question_id(aid: str, round_number: int, facts: list[dict]) -> str:
    base = f'{PANEL_QID_PREFIX}{aid}:{int(round_number)}'
    prior = sum((1 for fact in facts if fact.get('ev') == 'decision' and str(fact.get('aid') or '') == aid and panel_qid_matches(fact.get('question_id'), aid, round_number)))
    return base if prior == 0 else f'{base}:{prior + 1}'

def panel_waiting(fs: list[dict], vw: dict) -> list[str]:
    from cex_core.engine.ist_core.compile_engine.questions import effective_decision_token, is_retired_manual_panel_shape
    out = []
    for f in fs:
        if f.get('ev') != 'ask_panel':
            continue
        if is_retired_manual_panel_shape(f):
            continue
        aid = str(f.get('aid'))
        rnd = int(f.get('round') or 0)
        c = vw['cases'].get(aid)
        if not c or c['status'] in (V.S_DELIVERABLE, V.S_TERMINAL, V.S_SUSPENDED, V.S_ESCALATED, V.S_UNSUPPORTED_FEATURE):
            continue
        answered = any((d.get('ev') == 'decision' and panel_qid_matches(d.get('question_id'), aid, rnd) and (effective_decision_token(d) in {'confirm', 'correct', 'defect', 'stop', 'downgrade'}) for d in fs))
        adopted = any((d.get('ev') == 'adopted' and str(d.get('aid')) == aid and (int(d.get('round') or 0) == rnd) for d in fs))
        conditional = any((d.get('ev') == 'conditional_decision' and panel_qid_matches(d.get('question_id'), aid, rnd) for d in fs))
        if not answered and (not adopted) and (not conditional) and (aid not in out):
            out.append(aid)
    return out

def command_domain_isolated(fs: list[dict], vw: dict, atlas_identity_sha: str) -> list[str]:
    sha = str(atlas_identity_sha or '').strip()
    if not sha:
        return []
    out: list[str] = []
    for f in fs:
        if f.get('ev') != 'command_domain_case_excluded':
            continue
        if str(f.get('atlas_identity_sha256') or '').strip() != sha:
            continue
        aid = str(f.get('aid') or '')
        case = (vw.get('cases') or {}).get(aid)
        if not case:
            continue
        if str(f.get('artifact') or '') != str(case.get('artifact') or ''):
            continue
        if aid not in out:
            out.append(aid)
    return out

def suspended_resume_waiting(fs: list[dict], vw: dict) -> list[str]:
    n_runs = sum((1 for f in fs if f.get('ev') == 'run_start'))
    _batch_pending = batch_conflict_decision_aids(fs)
    out = []
    for aid, c in vw['cases'].items():
        if c['status'] != V.S_SUSPENDED:
            continue
        if aid in _batch_pending:
            continue
        idx_susp = max((i for i, f in enumerate(fs) if f.get('ev') == 'suspended' and str(f.get('aid')) == aid), default=-1)
        if idx_susp < 0 or not any((f.get('ev') == 'run_start' for f in fs[idx_susp + 1:])):
            continue
        qid = f'resume:{aid}:{n_runs}'
        if not any((d.get('ev') == 'decision' and d.get('question_id') == qid and (str(d.get('aid')) == aid) for d in fs)):
            out.append(aid)
    return out

def _deesc_precedent_key(aid: str, subclass: str, state: dict) -> str:
    fam = '.'.join(str(state.get('evidence_build') or '').split('.')[:3])
    return f"{aid}|{subclass}|{fam}|{state.get('bed_host') or ''}"

def deesc_qid(aid: str, mine: list[dict]) -> str:
    seq = sum((1 for d in mine if d.get('ev') == 'decision' and str(d.get('question_id', '')).startswith(f'deesc:{aid}:'))) + 1
    return f'deesc:{aid}:{seq}'

def _escalation_is_engine_budget(mine: list[dict]) -> bool:
    for f in reversed(mine):
        if f.get('ev') != 'escalated':
            continue
        return bool(escalation_budget_kind(f))
    return False

def escalation_budget_kind(fact: dict) -> str:
    from cex_core.engine.ist_core.resilience import FORK_RECURSION_LIMIT_MARKER, FORK_WALLCLOCK_MARKER
    declared = str(fact.get('engine_budget_exhausted') or '')
    if declared:
        return declared
    reason = str(fact.get('reason') or '')
    if f'no {FORK_WALLCLOCK_MARKER}' in reason:
        return ''
    if f'{FORK_WALLCLOCK_MARKER} marker present' in reason:
        return 'wallclock'
    if f'{FORK_RECURSION_LIMIT_MARKER} marker present' in reason:
        return 'turn_budget'
    return ''

def deesc_recovery_waiting(state: dict, fs: list[dict], vw: dict) -> list[str]:
    out = []
    for aid in vw['cases']:
        mine = [f for f in fs if str(f.get('aid')) == aid]
        if not V._is_escalated(mine):
            continue
        if _escalation_is_engine_budget(mine):
            continue
        sub = F.escalated_subclass(fs, aid)
        last_esc_i = max((i for i, f in enumerate(mine) if f.get('ev') == 'escalated'), default=-1)
        deesc_this_round = [f for i, f in enumerate(mine) if i > last_esc_i and f.get('ev') == 'decision' and str(f.get('question_id', '')).startswith(f'deesc:{aid}:')]
        if not deesc_this_round:
            out.append(aid)
            continue
        last = deesc_this_round[-1]
        if str(last.get('token')) != 'deesc_keep':
            continue
        key = _deesc_precedent_key(aid, sub, state)
        if any((f.get('ev') == 'deesc_keep' and f.get('precedent_key') == key for f in mine)):
            continue
        out.append(aid)
    return out

def ask_targets(state: dict, fs: list[dict], vw: dict) -> dict:
    contra = []
    for aid, c in vw['cases'].items():
        if c['status'] == V.S_CONTRADICTED and c['contradictions'] >= 2:
            mine = [fact for fact in fs if str(fact.get('aid') or '') == aid]
            if V.execution_pause_resume_pending(mine):
                continue
            qid = f"contra:{aid}:{c['contradictions']}"
            if not any((d.get('ev') == 'decision' and d.get('question_id') == qid for d in fs)):
                contra.append(aid)
    return {'panel': panel_waiting(fs, vw), 'contra': contra, 'env': env_confirm_waiting(fs, vw), 'suspended': suspended_resume_waiting(fs, vw), 'deesc': deesc_recovery_waiting(state, fs, vw)}

def _decision_resolves_needs_decision(need: dict, decision: dict, migration_facts: list[dict] | None=None) -> bool:
    if decision.get('ev') != 'decision':
        return False
    question_id = str(need.get('question_id') or '')
    if not question_id or str(decision.get('question_id') or '') != question_id:
        return False
    need_aid = str(need.get('aid') or '')
    decision_aid = str(decision.get('aid') or '')
    if need_aid and decision_aid != need_aid:
        return False
    if accepts_schema(decision.get('schema'), 'ist.case-terminal-static-void'):
        if not (decision.get('answer') == 'case_terminal_static_void' and str(decision.get('token') or '') in {'case_terminal_static_void', '****'}):
            return False
        if migration_facts is None:
            return True
        return need_aid in case_terminal_settled_aids(migration_facts)
    if accepts_schema(decision.get('schema'), 'ist.author-definition-gap-auto-resolution'):
        token = str(decision.get('token') or '')
        base_valid = bool(decision.get('answer') == 'author_definition_gap_disclosed' and token in {'author_definition_gap_disclosed', '****'} and re.fullmatch('[0-9a-f]{64}', str(decision.get('ledger_sha256') or '')))
        if not base_valid:
            return False
        if migration_facts is None:
            return True
        from cex_core.engine.ist_core.compile_engine.terminal_credentials import author_definition_gap_auto_resolution_valid
        return author_definition_gap_auto_resolution_valid(aid=need_aid, ledger_sha256=str(decision.get('ledger_sha256') or ''), facts=migration_facts)
    if need.get('criterion_rule_batch') is True:
        return bool(accepts_schema(decision.get('schema'), 'ist.criterion-author-batch-decision') and str(decision.get('answer') or '') == 'criterion_author_rules_committed' and (str(decision.get('token') or '') == 'criterion_author_rules_committed') and (int(decision.get('question_count') or 0) > 0) and (int(decision.get('committed_count') or 0) == int(decision.get('question_count') or 0)))
    from cex_core.engine.ist_core.compile_engine.conflict_chain import is_direct_abandon_decision, need_accepts_direct_abandon
    if is_direct_abandon_decision(decision):
        return need_accepts_direct_abandon(need, str(decision.get('conflict_scenario') or ''))
    from cex_core.engine.ist_core.compile_engine.conflict_chain import batch_auto_case_decision_resolves, batch_conflict_binding_migration_resolves_need, batch_conflict_decision_resolves_need
    if batch_auto_case_decision_resolves(need, decision):
        return True
    if batch_conflict_decision_resolves_need(need, decision):
        return True
    if any((batch_conflict_binding_migration_resolves_need(need, decision, migration) for migration in migration_facts or [])):
        return True
    legacy_conflict_scenarios = need.get('conflict_scenarios')
    if str(need.get('conflict_scenario') or '') in {'scenario_3', 'scenario_4'} or (isinstance(legacy_conflict_scenarios, list) and any((value in {'scenario_3', 'scenario_4'} for value in legacy_conflict_scenarios))) or 'expected_delta_ids' in need:
        return False
    answer = decision.get('answer')
    if not isinstance(answer, str) or not answer.strip():
        return False
    from cex_core.engine.ist_core.compile_engine.questions import CONFLICT_DECISIONS, DECISIONS, SCENARIO4_DECISIONS, SPEC_UNKNOWN_DECISIONS, effective_decision_token
    by_scenario = {'scenario_1': {'abandon_generation'}, 'scenario_2': {'abandon_generation'}, 'scenario_3': set(CONFLICT_DECISIONS), 'scenario_4': set(SCENARIO4_DECISIONS), 'spec_unknown': {'continue_without_spec'}}
    resolving_tokens = set(DECISIONS) | set(CONFLICT_DECISIONS) | set(SCENARIO4_DECISIONS) | set(SPEC_UNKNOWN_DECISIONS) | {'conflict_delta_conjunction'}
    token = effective_decision_token(decision)
    if token in {'', '****'} and decision.get('freeform') is not True:
        token = answer.strip() if answer.strip() in resolving_tokens else ''
    need_scenario = str(need.get('conflict_scenario') or '')
    decision_scenario = str(decision.get('conflict_scenario') or '')
    if need_scenario and decision_scenario and (need_scenario != decision_scenario):
        return False
    scenario = need_scenario or decision_scenario
    delta_mode = 'expected_delta_ids' in need
    auxiliary_claims = need.get('auxiliary_claims')
    if not delta_mode and isinstance(auxiliary_claims, list):
        if len(auxiliary_claims) != 1 or scenario != 'spec_unknown':
            return False
        claim = auxiliary_claims[0]
        if not isinstance(claim, dict) or not accepts_schema(claim.get('schema'), 'ist.delta.conflict-claim') or claim.get('conflict_scenario') != 'spec_unknown':
            return False
        chain_id = str(claim.get('conflict_chain_id') or '')
        return token in by_scenario['spec_unknown'] and decision.get('conflict_chain_id') == chain_id and (re.fullmatch('[0-9a-f]{64}', chain_id) is not None)
    if scenario in {'scenario_3', 'scenario_4'} and (not delta_mode):
        return False
    if delta_mode:
        expected_delta_ids = need.get('expected_delta_ids')
        expected_count = need.get('expected_count')
        conflict_scenarios = need.get('conflict_scenarios')
        needs_decision_sha256 = need.get('needs_decision_sha256')
        delta_claims = need.get('delta_claims')
        if not isinstance(expected_delta_ids, list) or not expected_delta_ids or any((not isinstance(delta_id, str) or not delta_id.strip() or delta_id != delta_id.strip() for delta_id in expected_delta_ids)) or (len(set(expected_delta_ids)) != len(expected_delta_ids)) or (type(expected_count) is not int) or (expected_count != len(expected_delta_ids)) or (not isinstance(conflict_scenarios, list)) or (not conflict_scenarios) or any((not isinstance(item, str) or item not in {'scenario_3', 'scenario_4'} for item in conflict_scenarios)) or (conflict_scenarios != sorted(set(conflict_scenarios))) or (not isinstance(needs_decision_sha256, str)) or (re.fullmatch('[0-9a-f]{64}', needs_decision_sha256) is None):
            return False
        if len(conflict_scenarios) == 1:
            if need_scenario and need_scenario != conflict_scenarios[0]:
                return False
        elif need_scenario or decision_scenario:
            return False
        if isinstance(delta_claims, list):
            from cex_core.engine.ist_core.compile_engine.conflict_chain import CONFLICT_DECISION_SCHEMA, DeltaAction, conflict_token_action, decision_is_current, reduce_delta_frontier
            if len(delta_claims) != expected_count or any((not isinstance(claim, dict) for claim in delta_claims)) or [claim.get('delta_id') for claim in delta_claims] != expected_delta_ids or any((not accepts_schema(claim.get('schema'), 'ist.delta.conflict-claim') or claim.get('conflict_scenario') not in {'scenario_3', 'scenario_4'} or re.fullmatch('[0-9a-f]{64}', str(claim.get('conflict_chain_id') or '')) is None for claim in delta_claims)) or (sorted({str(claim.get('conflict_scenario') or '') for claim in delta_claims}) != conflict_scenarios) or (token != 'conflict_delta_conjunction') or (decision.get('needs_decision_sha256') != needs_decision_sha256):
                return False
            rows = decision.get('delta_decisions')
            if not isinstance(rows, list):
                return False
            claim_by_delta = {str(claim['delta_id']): claim for claim in delta_claims}
            for row in rows:
                if not isinstance(row, dict):
                    return False
                delta_id = str(row.get('delta_id') or '')
                claim = claim_by_delta.get(delta_id)
                row_token = str(row.get('token') or '')
                action = conflict_token_action(row_token)
                if claim is None or row.get('schema') != CONFLICT_DECISION_SCHEMA or row.get('conflict_scenario') != claim.get('conflict_scenario') or (not decision_is_current(row, claim.get('conflict_chain_id'), expected_delta_id=delta_id)):
                    return False
                allowed = by_scenario[str(claim['conflict_scenario'])]
                if row_token not in allowed or action is None:
                    return False
                if row_token == 'use_case_expectation' and claim.get('case_expectation_supported') is False:
                    action = DeltaAction.TERMINATE
                if row.get('action') != action.value:
                    return False
            frontier = reduce_delta_frontier(delta_claims, rows)
            if not frontier.valid:
                return False
            effective_ids = list(frontier.effective_delta_ids)
            pruned_ids = list(frontier.pruned_delta_ids)
            effective_scenarios = sorted({str(claim_by_delta[delta_id]['conflict_scenario']) for delta_id in effective_ids})
            if decision.get('original_expected_delta_ids') != expected_delta_ids or type(decision.get('original_expected_count')) is not int or decision.get('original_expected_count') != expected_count or (decision.get('expected_delta_ids') != effective_ids) or (type(decision.get('expected_count')) is not int) or (decision.get('expected_count') != len(effective_ids)) or (decision.get('pruned_delta_ids') != pruned_ids) or (type(decision.get('pruned_count')) is not int) or (decision.get('pruned_count') != len(pruned_ids)) or (type(decision.get('decided_count')) is not int) or (decision.get('decided_count') != frontier.reduction.decided_count) or (decision.get('conflict_scenarios') != effective_scenarios):
                return False
            expected_auxiliary = auxiliary_claims if isinstance(auxiliary_claims, list) else []
            actual_auxiliary = decision.get('auxiliary_decisions') or []
            if not isinstance(actual_auxiliary, list):
                return False
            aux_by_chain: dict[str, dict] = {}
            for claim in expected_auxiliary:
                if not isinstance(claim, dict) or not accepts_schema(claim.get('schema'), 'ist.delta.conflict-claim') or claim.get('conflict_scenario') != 'spec_unknown' or (re.fullmatch('[0-9a-f]{64}', str(claim.get('conflict_chain_id') or '')) is None):
                    return False
                aux_by_chain[str(claim['conflict_chain_id'])] = claim
            if len(aux_by_chain) != len(expected_auxiliary):
                return False
            seen_auxiliary: set[str] = set()
            for row in actual_auxiliary:
                if not isinstance(row, dict):
                    return False
                chain_id = str(row.get('conflict_chain_id') or '')
                if not accepts_schema(row.get('schema'), 'ist.delta.auxiliary-decision') or row.get('conflict_scenario') != 'spec_unknown' or chain_id not in aux_by_chain or (chain_id in seen_auxiliary) or (row.get('token') not in by_scenario['spec_unknown']) or (not str(row.get('answer_key') or '')):
                    return False
                seen_auxiliary.add(chain_id)
            return seen_auxiliary == set(aux_by_chain)
        if token == 'conflict_delta_conjunction':
            decision_expected_count = decision.get('expected_count')
            if not isinstance(decision.get('expected_delta_ids'), list) or decision.get('expected_delta_ids') != expected_delta_ids or type(decision_expected_count) is not int or (decision_expected_count != expected_count) or (not isinstance(decision.get('conflict_scenarios'), list)) or (decision.get('conflict_scenarios') != conflict_scenarios) or (decision.get('needs_decision_sha256') != needs_decision_sha256):
                return False
            decided_count = decision.get('decided_count')
            if type(decided_count) is not int or decided_count != expected_count:
                return False
            rows = decision.get('delta_decisions')
            if not isinstance(rows, list) or len(rows) != decided_count:
                return False
            from cex_core.engine.ist_core.compile_engine.conflict_chain import reduce_delta_decisions
            reduction = reduce_delta_decisions(expected_delta_ids, rows)
            return reduction.valid and reduction.expected_count == expected_count and (reduction.decided_count == decided_count)
        if len(expected_delta_ids) != 1 or len(conflict_scenarios) != 1:
            return False
        allowed = by_scenario.get(conflict_scenarios[0])
        return allowed is not None and token in allowed and (decision.get('delta_id') == expected_delta_ids[0]) and (decision.get('needs_decision_sha256') == needs_decision_sha256)
    if token == 'conflict_delta_conjunction':
        return False
    if scenario:
        allowed = by_scenario.get(scenario)
        return allowed is not None and token in allowed
    return token in resolving_tokens

def unresolved_static_decision_facts(fs: list[dict]) -> list[dict]:
    decisions_by_question_id: dict[str, list[dict]] = {}
    for fact in fs:
        if fact.get('ev') != 'decision' or not fact.get('question_id'):
            continue
        decisions_by_question_id.setdefault(str(fact.get('question_id')), []).append(fact)
    unresolved: list[dict] = []
    for index, fact in enumerate(fs):
        if fact.get('ev') != 'needs_decision' or not fact.get('aid'):
            continue
        aid = str(fact.get('aid') or '')
        superseded = any((later.get('ev') == 'conflict_chain_reentered' and str(later.get('aid') or '') == aid and (later.get('invalidate_decisions') is True) for later in fs[index + 1:]))
        if superseded:
            continue
        if not any((_decision_resolves_needs_decision(fact, decision, fs) for decision in decisions_by_question_id.get(str(fact.get('question_id') or ''), []))):
            unresolved.append(fact)
    return unresolved

def unresolved_static_decision_aids(fs: list[dict]) -> set[str]:
    return {str(fact.get('aid') or '') for fact in unresolved_static_decision_facts(fs) if fact.get('aid')}

def case_terminal_settled_aids(fs: list[dict]) -> set[str]:
    settled = {str(fact.get('aid') or '') for fact in fs if fact.get('ev') == 'case_terminal_outcome' and fact.get('aid')}
    settled.update((str(fact.get('aid') or '') for fact in EE.case_scoped_engine_errors(fs) if fact.get('aid')))
    return settled

def batch_conflict_decision_aids(fs: list[dict]) -> set[str]:
    out: set[str] = set()
    for fact in unresolved_static_decision_facts(fs):
        aid = str(fact.get('aid') or '')
        ids = fact.get('batch_conflict_claim_ids')
        if aid and isinstance(ids, list) and any((str(v).strip() for v in ids)):
            out.add(aid)
    return out

def static_ask_settled_aids(fs: list[dict]) -> set[str]:
    settled: set[str] = set()
    mine_slice = F.this_run_slice(fs)
    decisions = [f for f in mine_slice if f.get('ev') == 'decision']
    for index, need in enumerate(mine_slice):
        if need.get('ev') != 'needs_decision' or not need.get('aid'):
            continue
        aid = str(need.get('aid') or '')
        resolved_at = next((position for position, decision in enumerate(mine_slice) if decision.get('ev') == 'decision' and decision in decisions and _decision_resolves_needs_decision(need, decision, mine_slice)), -1)
        if resolved_at < 0:
            continue
        reentered = any((later.get('ev') == 'conflict_chain_reentered' and str(later.get('aid') or '') == aid and (later.get('invalidate_decisions') is True) for later in mine_slice[max(resolved_at, index) + 1:]))
        if not reentered:
            settled.add(aid)
    from cex_core.engine.ist_core.compile_engine.conflict_chain import batch_conflict_binding_migration_resolves_need
    all_needs = [fact for fact in fs if fact.get('ev') == 'needs_decision']
    all_decisions = [fact for fact in fs if fact.get('ev') == 'decision']
    for index, migration in enumerate(mine_slice):
        if migration.get('ev') != 'needs_decision_binding_migrated':
            continue
        aid = str(migration.get('aid') or '')
        qid = str(migration.get('question_id') or '')
        if not aid or not qid:
            continue
        migrated = any((str(need.get('aid') or '') == aid and str(need.get('question_id') or '') == qid and (str(decision.get('aid') or '') == aid) and (str(decision.get('question_id') or '') == qid) and batch_conflict_binding_migration_resolves_need(need, decision, migration) for need in all_needs for decision in all_decisions))
        if not migrated:
            continue
        reentered = any((later.get('ev') == 'conflict_chain_reentered' and str(later.get('aid') or '') == aid and (later.get('invalidate_decisions') is True) for later in mine_slice[index + 1:]))
        if not reentered:
            settled.add(aid)
    return settled

def settled_claim_chain_ids(fs: list[dict], aid: str) -> set[str]:
    mine_slice = [fact for fact in F.this_run_slice(fs) if str(fact.get('aid') or '') == str(aid)]
    reentered_at = [position for position, fact in enumerate(mine_slice) if fact.get('ev') == 'conflict_chain_reentered' and fact.get('invalidate_decisions') is True]
    floor = max(reentered_at) + 1 if reentered_at else 0
    return {str(fact.get('conflict_chain_id') or '') for fact in mine_slice[floor:] if fact.get('ev') == 'decision' and str(fact.get('conflict_chain_id') or '')}

def ledger_claims_all_settled(fs: list[dict], aid: str, ledger: object) -> bool:
    if not isinstance(ledger, dict):
        return False
    claims = [claim for claim in ledger.get('claims') or [] if isinstance(claim, dict)]
    if not claims:
        return False
    chain_ids = [str(claim.get('conflict_chain_id') or '') for claim in claims]
    if not all(chain_ids):
        return False
    return set(chain_ids) <= settled_claim_chain_ids(fs, aid)
REAUTHOR_UNAVAILABLE_EVENT = 'author_reauthor_unavailable'

def emit_reauthor_aids(fs: list[dict], vw: dict, *, waiting: set[str]) -> set[str]:
    latest: dict[str, str] = {}
    for fact in F.this_run_slice(fs):
        aid = str(fact.get('aid') or '')
        if not aid:
            continue
        event = fact.get('ev')
        if event == 'composed':
            latest[aid] = 'composed'
        elif event == 'authored':
            latest[aid] = 'authored'
        elif event == REAUTHOR_UNAVAILABLE_EVENT:
            latest[aid] = 'no_reauthor_path'
        elif event == 'emit_invalid':
            from cex_core.engine.ist_core.compile_engine.emit_failure_evidence import active_producer_refs, mechanical_emit_refusal
            supported = not mechanical_emit_refusal(fact) or active_producer_refs(fs, aid=aid, dispatch_id=str(fact.get('dispatch_id') or ''), batch_run_id=str(fact.get('batch_run_id') or ''))
            latest[aid] = 'reauthor' if fact.get('reject_class') == F.EMIT_REJECT_PRODUCER and supported else 'not_producer'
    out: set[str] = set()
    for aid, mark in latest.items():
        if mark != 'reauthor' or aid in waiting:
            continue
        case = (vw.get('cases') or {}).get(aid)
        if not case or V.is_settled(str(case.get('status') or '')):
            continue
        out.add(aid)
    return out

def emit_reauthor_waiting(state: dict, fs: list[dict], vw: dict, *, targets: dict | None=None) -> set[str]:
    """`n_emit_reauthor` 判据里的「不该回 author」集合。

    `counts_update` 与 author 共用这一份：路由算的集合和 author 处置的集合必须是同一个，
    否则会出现「路由说有 3 个案要重编、author 一个都认不出」的空转。
    """
    targets = ask_targets(state, fs, vw) if targets is None else targets
    waiting = set(targets['panel']) | set(targets['contra']) | set(targets['env']) | set(targets['suspended']) | set(targets['deesc'])
    return waiting | unresolved_static_decision_aids(fs) - set(targets['suspended'])

def emit_reauthor_route_aids(state: dict, fs: list[dict], vw: dict, *, targets: dict | None=None) -> set[str]:
    """路由读的那一份重编集合（`n_emit_reauthor` 的成员）。author 按它认案。

    **这里是唯一的组装点**：`counts_update` 与 author 都调本函数，不各自拿
    `emit_reauthor_aids(..., waiting=emit_reauthor_waiting(...))` 拼一遍——将来往集合上加一道
    过滤器时，两处各拼一遍就会分叉成两个集合，而那正是本回路空转的成因形态。
    `targets` 只是让已经算过 `ask_targets` 的调用方省一次重算，不改变结果。
    """
    return emit_reauthor_aids(fs, vw, waiting=emit_reauthor_waiting(state, fs, vw, targets=targets))

def _deescalated_pending_aids(fs: list[dict], vw: dict) -> set[str]:
    out: set[str] = set()
    cases = (vw or {}).get('cases') or {}
    for aid, case in cases.items():
        if str((case or {}).get('status') or '') != V.S_PENDING:
            continue
        mine = [f for f in F.this_run_slice(fs) if str(f.get('aid') or '') == aid]
        last_deesc = max((i for i, f in enumerate(mine) if f.get('ev') == 'de_escalated'), default=-1)
        if last_deesc < 0:
            continue
        spent = any((f.get('ev') in ('composed', 'authored') for f in mine[last_deesc + 1:]))
        if not spent:
            out.add(str(aid))
    return out

def counts_update(state: dict, fs: list[dict] | None=None) -> dict:
    if fs is None:
        fs = load_facts(state)
    vw = view(state, fs)
    c = vw['counts']
    t = ask_targets(state, fs, vw)
    _waiting = set(t['panel']) | set(t['contra']) | set(t['env']) | set(t['suspended']) | set(t['deesc'])
    _pending_decision_aids = unresolved_static_decision_aids(fs) - set(t['suspended'])
    _delivery_merges = [fact for fact in fs if fact.get('ev') == 'merged' and fact.get('ctx') != F.CTX_SUBSET]
    _current_delivery_comp = set((str(aid) for aid in (_delivery_merges[-1].get('composition') or [] if _delivery_merges else []) if aid))
    _deliverable_aids = {aid for aid, case in vw['cases'].items() if case['status'] == V.S_DELIVERABLE}
    _delivery_reverify = bool(_deliverable_aids and _current_delivery_comp != _deliverable_aids)
    current_capability_sha = str(state.get('capability_projection_sha256') or '').strip().lower()
    _delivery_capability_stale = {aid for aid in _deliverable_aids if re.fullmatch('[0-9a-f]{64}', current_capability_sha) is not None and next((str(fact.get('capability_projection_sha256') or '') for fact in reversed(fs) if fact.get('ev') == 'verdict' and fact.get('ctx') == F.CTX_DELIVERY and (fact.get('result') == 'pass') and (str(fact.get('aid') or '') == aid)), '') != current_capability_sha}
    _delivery_reverify = _delivery_reverify or bool(_delivery_capability_stale)
    from cex_core.engine.ist_core.compile_engine.backstops import latest_batch_backstop_stop
    from cex_core.engine.ist_core.compile_engine.engine_quarantine import batch_halted
    return {'n_recorded_batch_stop': int(batch_halted(fs)), 'n_batch_backstop': int(latest_batch_backstop_stop(fs) is not None), 'n_batch_execution_pause': int(any((f.get('ev') == 'batch_execution_paused' for f in F.this_run_slice(fs)))), 'n_engine_error': sum((1 for _e in EE.active_engine_errors(fs) if EE.error_halts_batch(_e))), 'n_pending': c.get(V.S_PENDING, 0), 'n_composed': len(F.emit_todo_aids(fs)), 'n_compose_rejected': len({str(f.get('aid') or '') for f in F.this_run_slice(fs) if f.get('ev') == 'compose_rejected' and f.get('aid')}), 'n_emit_reauthor': len(emit_reauthor_route_aids(state, fs, vw, targets=t)), 'n_reauthor_pending': len(_deescalated_pending_aids(fs, vw)), 'n_awaiting_user': c.get(V.S_AWAITING_USER, 0), 'n_awaiting_decision': len(_pending_decision_aids), 'n_batch_conflict_suspended': len(batch_conflict_decision_aids(fs) & {aid for aid, case in vw['cases'].items() if str(case.get('status') or '') == V.S_SUSPENDED}), 'n_static_unanswered': len(unresolved_static_decision_aids(fs)), 'n_authored': c.get(V.S_AUTHORED, 0), 'n_failed': c.get(V.S_FAILED, 0) + c.get(V.S_CONTRADICTED, 0), 'n_subset_verified': c.get(V.S_SUBSET_VERIFIED, 0), 'n_broken': c.get(V.S_BROKEN, 0), 'n_broken_errored': c.get(V.S_BROKEN_ERRORED, 0), 'n_broken_blocked': c.get(V.S_BROKEN_BLOCKED, 0), 'n_broken_aborted': c.get(V.S_BROKEN_ABORTED, 0), 'n_broken_verdict_unrecognized': c.get(V.S_BROKEN_VERDICT_UNRECOGNIZED, 0), 'n_rerunnable': c.get(V.S_BROKEN, 0) + c.get(V.S_BROKEN_ABORTED, 0) + c.get(V.S_BROKEN_VERDICT_UNRECOGNIZED, 0), 'n_deliverable': c.get(V.S_DELIVERABLE, 0), 'n_delivery_reverify': len(_deliverable_aids) if _delivery_reverify else 0, 'n_contradicted': c.get(V.S_CONTRADICTED, 0), 'n_settled_bad': c.get(V.S_ESCALATED, 0) + c.get(V.S_TERMINAL, 0) + c.get(V.S_SUSPENDED, 0) + c.get(V.S_UNSUPPORTED_FEATURE, 0), 'n_ask_contradiction': len(_waiting), 'n_ask_contradiction_unshown': len(_waiting - {str(f.get('aid')) for f in F.this_run_slice(fs) if f.get('ev') == 'ask_shown'} - {str(f.get('aid')) for f in fs if f.get('ev') == 'ledger_unreadable'} - {str(f.get('aid')) for f in fs if f.get('ev') == 'question_unbuildable'} - {str(f.get('aid')) for f in F.this_run_slice(fs) if f.get('ev') == 'question_form_blocked'}), 'n_failed_actionable': len({a for a, cc in vw['cases'].items() if cc['status'] in (V.S_FAILED, V.S_CONTRADICTED) or (cc['status'] == V.S_BROKEN_BLOCKED and _latest_rerun_prescription(fs, a))} - _waiting), 'n_awaiting_unasked': len((_pending_decision_aids & {aid for aid, case in vw['cases'].items() if str(case.get('status') or '') == V.S_AWAITING_USER}) - {str(f.get('aid')) for f in F.this_run_slice(fs) if f.get('ev') in ('ask_shown', 'question_form_blocked', 'suspended')} - {str(f.get('aid')) for f in fs if f.get('ev') == 'ledger_unreadable'} - {str(f.get('aid')) for f in fs if f.get('ev') == 'question_unbuildable'})}

def _latest_rerun_prescription(fs: list[dict], aid: str) -> bool:
    return F.execution_retry_requested(fs, aid)

def lint_credential_snapshot(aid: str) -> tuple[bytes, str, str]:
    try:
        aid = safe_output_component(aid, field='autoid')
    except ValueError:
        return (b'', '', 'credential_unreadable')
    from cex_core.engine.ist_core.tools.device.run_case import _MAX_CREDENTIAL_BYTES, _MAX_XLSX_BYTES, _read_regular_under_root
    root = outputs_root()
    case_rel = Path(aid) / 'case.xlsx'
    credential_rel = Path(aid) / '.grade_credential.json'
    try:
        case_payload, _case_stat = _read_regular_under_root(root, case_rel, max_bytes=_MAX_XLSX_BYTES)
    except FileNotFoundError:
        return (b'', '', 'case_missing')
    except Exception:
        return (b'', '', 'case_unreadable')
    try:
        credential_payload, _credential_stat = _read_regular_under_root(root, credential_rel, max_bytes=_MAX_CREDENTIAL_BYTES)
    except FileNotFoundError:
        return (b'', '', 'credential_missing')
    except Exception:
        return (b'', '', 'credential_unreadable')
    try:
        credential = json.loads(credential_payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return (b'', '', 'credential_unreadable')
    credential_sha256 = str(credential.get('xlsx_sha256') or '') if isinstance(credential, dict) else ''
    if not (isinstance(credential, dict) and credential.get('source') == 'lint' and (credential.get('lint_ok') is True) and (str(credential.get('autoid') or '') == aid) and (credential.get('xlsx') == (Path('workspace') / 'outputs' / aid / 'case.xlsx').as_posix()) and (credential.get('verdict') == 'PASS') and (len(credential_sha256) == 64) and all((ch in '0123456789abcdef' for ch in credential_sha256))):
        return (b'', '', 'credential_contract_invalid')
    live_sha256 = hashlib.sha256(case_payload).hexdigest()
    if credential_sha256 != live_sha256:
        return (b'', '', 'credential_sha256_mismatch')
    return (case_payload, live_sha256, 'ok')
MECHANICAL_FINDINGS_DROP_REASONS: tuple[str, ...] = ('autoid_invalid', 'credential_not_ok', 'sidecar_missing', 'oversized', 'unreadable', 'json_invalid', 'schema_mismatch', 'autoid_mismatch', 'xlsx_sha256_mismatch', 'rows_invalid')

def _drop_mechanical_findings(aid: str, reason: str, *, trace: bool=False) -> list[dict]:
    assert reason in MECHANICAL_FINDINGS_DROP_REASONS, reason
    logger.debug('交卷机械发现读回丢弃(aid=%s, reason=%s)', aid, reason, exc_info=trace)
    return []

def mechanical_findings_rows(aid: str) -> list[dict]:
    try:
        aid = safe_output_component(aid, field='autoid')
    except ValueError:
        return _drop_mechanical_findings(str(aid), 'autoid_invalid')
    from cex_core.engine.case_compiler.device_characteristics import MAX_MECHANICAL_FINDINGS_BYTES, MECHANICAL_FINDINGS_SCHEMA
    from cex_core.engine.engine_managed_outputs import MECHANICAL_FINDINGS_SIDECAR_NAME
    from cex_core.engine.ist_core.tools.device.run_case import _read_regular_under_root
    _case_payload, credential_sha256, status = lint_credential_snapshot(aid)
    if status != 'ok' or len(credential_sha256) != 64:
        return _drop_mechanical_findings(aid, 'credential_not_ok')
    try:
        payload, _stat = _read_regular_under_root(outputs_root(), Path(aid) / MECHANICAL_FINDINGS_SIDECAR_NAME, max_bytes=MAX_MECHANICAL_FINDINGS_BYTES)
    except FileNotFoundError:
        return _drop_mechanical_findings(aid, 'sidecar_missing')
    except ValueError:
        return _drop_mechanical_findings(aid, 'oversized', trace=True)
    except Exception:
        return _drop_mechanical_findings(aid, 'unreadable', trace=True)
    try:
        sidecar = json.loads(payload.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _drop_mechanical_findings(aid, 'json_invalid', trace=True)
    if not isinstance(sidecar, dict):
        return _drop_mechanical_findings(aid, 'schema_mismatch')
    if sidecar.get('schema') != MECHANICAL_FINDINGS_SCHEMA:
        return _drop_mechanical_findings(aid, 'schema_mismatch')
    if str(sidecar.get('autoid') or '') != aid:
        return _drop_mechanical_findings(aid, 'autoid_mismatch')
    if str(sidecar.get('xlsx_sha256') or '') != credential_sha256:
        return _drop_mechanical_findings(aid, 'xlsx_sha256_mismatch')
    rows = sidecar.get('findings')
    if not isinstance(rows, list):
        return _drop_mechanical_findings(aid, 'rows_invalid')
    return [row for row in rows if isinstance(row, dict)]

def recompile_comparison_fact(aid: str) -> dict:
    from cex_core.engine.case_compiler.recompile_comparison import EVENT, load_comparison
    safe_aid = safe_output_component(aid, field='autoid')
    payload, _sha, status = lint_credential_snapshot(safe_aid)
    if status != 'ok':
        return {'ev': EVENT, 'aid': safe_aid, 'status': 'unavailable', 'reason_code': 'current_credential_unavailable'}
    comparison = load_comparison(outputs_root() / safe_aid, autoid=safe_aid, current=payload)
    return {'ev': EVENT, 'aid': safe_aid, **{key: value for key, value in comparison.items() if key != 'autoid'}}

def lint_credential_identity(aid: str) -> tuple[str, str]:
    _payload, sha256, status = lint_credential_snapshot(aid)
    return (sha256, status)

def credential_stale(aid: str, cred_xlsx_mtime=None) -> bool:
    _ = cred_xlsx_mtime
    _sha256, status = lint_credential_identity(aid)
    return status not in {'ok', 'case_missing'}

def artifact_fingerprint(aid: str) -> str:
    sha256, status = lint_credential_identity(aid)
    if status != 'ok':
        return ''
    return f'{aid}:{sha256}'

def volume_fingerprint(pairs: list[tuple[str, str]]) -> str:
    blob = json.dumps(sorted(pairs), ensure_ascii=False)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]

def echo_fingerprint(payload: dict) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]

def emit(text: str) -> None:
    try:
        from cex_core.engine.ist_core.events import get_default_bus
        get_default_bus().emit('evidence_added', payload={'text': f'[engine] {text}'})
    except Exception:
        logger.debug('engine 进度 emit 失败', exc_info=True)

def _footer_bucket_counts(c: dict) -> dict:
    return {'pending': c.get('pending', 0), 'dispatched': c.get('composed', 0), 'produced': c.get('authored', 0) + c.get('subset_verified', 0), 'pending_decision': c.get('awaiting_user', 0) + c.get('suspended', 0), 'awaiting_user': 0, 'passed': c.get('deliverable', 0), 'quarantined': c.get('quarantined', 0), 'failed_active': c.get('failed', 0) + c.get('contradicted', 0) + c.get('broken', 0) + c.get('broken_errored', 0) + c.get('broken_aborted', 0) + c.get('broken_verdict_unrecognized', 0), 'broken': c.get('broken_blocked', 0), 'failed_terminal': c.get('failed_terminal', 0) + c.get('unsupported_feature', 0), 'escalated': c.get('escalated', 0)}

def emit_recompose_progress(run: str, stage: str, **fields: Any) -> None:
    try:
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        _fork_emit_event({'event': 'recompose_progress', 'run': str(run or ''), 'stage': str(stage or ''), **fields})
    except Exception:
        logger.debug('recompose progress emit 失败', exc_info=True)
_NETWORK_PAUSE_SLICE_S = 5.0
_NETWORK_PAUSE_LOCK = threading.Lock()
_NETWORK_PAUSE_ANNOUNCED: dict[float, bool] = {}

def _network_outage_deadline_s() -> float:
    try:
        from cex_core.engine.ist_core.agents._llm import network_persistent_deadline_s
        return float(network_persistent_deadline_s())
    except Exception:
        return 1800.0

def _all_in_flight_forks_are_waiting(gauge: Mapping[str, Any]) -> bool:
    waiting = int(gauge.get('waiting_forks') or 0)
    in_flight = int(gauge.get('in_flight_forks') or 0)
    return waiting > 0 and waiting >= in_flight

def await_network_recovery(state: dict, *, phase: str='author', cancelled: Any=None) -> float:
    from cex_core.engine.ist_core.display_lexicon import NETWORK_OUTAGE_MINUTE_FLOOR_S, network_outage_card_cn
    from cex_core.engine.ist_core.skills.loader import network_outage_state
    gauge = network_outage_state()
    if not _all_in_flight_forks_are_waiting(gauge):
        if gauge.get('since') is None and _NETWORK_PAUSE_ANNOUNCED:
            with _NETWORK_PAUSE_LOCK:
                _NETWORK_PAUSE_ANNOUNCED.clear()
        return 0.0
    since = gauge.get('since') or time.time()
    since_monotonic = gauge.get('since_monotonic')
    if since_monotonic is None:
        since_monotonic = time.monotonic()
    deadline = _network_outage_deadline_s()
    announced = False
    with _NETWORK_PAUSE_LOCK:
        if not _NETWORK_PAUSE_ANNOUNCED.get(float(since)):
            _NETWORK_PAUSE_ANNOUNCED[float(since)] = True
            announced = True
    if announced:
        try:
            emit_tick(state, phase, network_outage={'since': float(since), 'waiting_forks': int(gauge.get('waiting_forks') or 0)})
            emit(network_outage_card_cn(time.monotonic() - float(since_monotonic)))
        except Exception:
            logger.debug('断网播报失败', exc_info=True)
    started = time.monotonic()
    recovered = False
    while True:
        gauge = network_outage_state()
        if not _all_in_flight_forks_are_waiting(gauge):
            recovered = True
            break
        if time.monotonic() - float(since_monotonic) >= deadline:
            break
        if callable(cancelled) and cancelled():
            break
        time.sleep(_NETWORK_PAUSE_SLICE_S)
    waited = time.monotonic() - started
    outage_total = time.monotonic() - float(since_monotonic)
    if announced:
        try:
            emit_tick(state, phase, network_outage={})
            if outage_total >= NETWORK_OUTAGE_MINUTE_FLOOR_S:
                append(state, [{'ev': 'network_outage', 'aid': '', 'since': float(since), 'waited_s': round(outage_total, 1), 'waiting_forks': int(gauge.get('waiting_forks') or 0), 'run_id': f'network_outage:{float(since):.0f}'}])
        except Exception:
            logger.debug('断网恢复播报失败', exc_info=True)
        if recovered:
            with _NETWORK_PAUSE_LOCK:
                _NETWORK_PAUSE_ANNOUNCED.pop(float(since), None)
    return waited

def emit_dispatch_progress(run: str, *, current: int, total: int) -> None:
    try:
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        _fork_emit_event({'event': 'dispatch_progress', 'run': str(run or ''), 'stage': 'brief_built', 'current': int(current), 'total': int(total)})
    except Exception:
        logger.debug('dispatch progress emit 失败', exc_info=True)
PREFLIGHT_HEARTBEAT_S = 30.0
_PREFLIGHT_HEARTBEAT_POLL_S = 5.0

def emit_preflight_progress(run: str, *, index: int, total: int, env: str='', detail: str='', elapsed_s: float=0.0, status: str='running') -> None:
    try:
        from cex_core.engine.ist_core.display_lexicon import PREFLIGHT_PROGRESS_LABEL, PREFLIGHT_PROGRESS_UNIT
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        _fork_emit_event({'event': 'progress', 'key': f'preflight:{run}', 'phase': PREFLIGHT_PROGRESS_LABEL, 'unit': PREFLIGHT_PROGRESS_UNIT, 'env': str(env or ''), 'case_idx': int(index), 'n_cases': int(total), 'detail': str(detail or ''), 'elapsed_s': int(elapsed_s), 'status': str(status or 'running')})
    except Exception:
        logger.debug('上机前环境检查进度 emit 失败', exc_info=True)

class PreflightProgressBeacon:

    def __init__(self, run: str, *, env: str='', started: float | None=None) -> None:
        self._run = str(run or '')
        self._env = str(env or '')
        self._started = float(time.time() if started is None else started)
        self._lock = threading.Lock()
        self._item: dict | None = None
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._beat, name='preflight-progress', daemon=True)
        self._thread.start()

    def begin(self, *, total: int) -> None:
        try:
            self._mark(index=0, total=int(total or 0), detail='')
        except Exception:
            logger.debug('上机前环境检查起跑事件失败', exc_info=True)

    def probe(self, *, index: int, total: int, target_device: str='', show_head: str='', show_command: str='', retry: bool=False) -> None:
        try:
            from cex_core.engine.ist_core.display_lexicon import PREFLIGHT_RETRY_SUFFIX
            command = str(show_command or '') or str(show_head or '')
            detail = ' '.join((part for part in (str(target_device or ''), command) if part))
            if retry:
                detail = f'{detail} · {PREFLIGHT_RETRY_SUFFIX}' if detail else PREFLIGHT_RETRY_SUFFIX
            self._mark(index=int(index or 0), total=int(total or 0), detail=detail)
        except Exception:
            logger.debug('上机前环境检查逐项事件失败', exc_info=True)

    def finish(self, *, status: str='done', detail: str='') -> None:
        try:
            with self._lock:
                item = dict(self._item or {})
                self._item = None
            total = int(item.get('total') or 0)
            emit_preflight_progress(self._run, index=total, total=total, env=self._env, detail=str(detail or ''), elapsed_s=self._elapsed(), status=str(status or 'done'))
        except Exception:
            logger.debug('上机前环境检查收尾事件失败', exc_info=True)

    def close(self) -> None:
        try:
            self._closed.set()
            thread, self._thread = (self._thread, None)
            if thread is not None:
                thread.join(timeout=2.0)
        except Exception:
            logger.debug('上机前环境检查心跳落闸失败', exc_info=True)

    def __enter__(self) -> 'PreflightProgressBeacon':
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _elapsed(self) -> float:
        return max(0.0, time.time() - self._started)

    def _mark(self, *, index: int, total: int, detail: str) -> None:
        now = time.time()
        with self._lock:
            self._item = {'index': index, 'total': total, 'detail': detail, 'since': now, 'last_emit': now}
        emit_preflight_progress(self._run, index=index, total=total, env=self._env, detail=detail, elapsed_s=self._elapsed(), status='running')

    def _beat(self) -> None:
        while not self._closed.wait(_PREFLIGHT_HEARTBEAT_POLL_S):
            now = time.time()
            with self._lock:
                if self._closed.is_set():
                    return
                item = dict(self._item or {})
                due = bool(item) and (now - float(item.get('since') or now) >= PREFLIGHT_HEARTBEAT_S and now - float(item.get('last_emit') or now) >= PREFLIGHT_HEARTBEAT_S)
                if not due:
                    continue
                self._item = {**item, 'last_emit': now}
                emit_preflight_progress(self._run, index=int(item.get('index') or 0), total=int(item.get('total') or 0), env=self._env, detail=str(item.get('detail') or ''), elapsed_s=self._elapsed(), status='running')

def emit_tick(state: dict, phase: str, fs: list[dict] | None=None, *, blocked: dict | None=None, common_cause: dict | None=None, network_outage: dict | None=None) -> None:
    try:
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        vw = view(state, fs)
        rec = {'event': 'engine_tick', 'run': str(state.get('out_name') or 'engine'), 'phase': phase, 'round': int(state.get('vol_seq') or 0), 'wave': 0, 'counts': _footer_bucket_counts(vw['counts']), 'total': len(vw['cases'])}
        if isinstance(blocked, dict) and blocked:
            rec['blocked'] = dict(blocked)
        if isinstance(common_cause, dict) and common_cause:
            rec['common_cause'] = dict(common_cause)
        if network_outage is not None:
            rec['network_outage'] = dict(network_outage) if isinstance(network_outage, dict) else {}
        notices = engine_card_notices(state)
        if notices:
            rec['notices'] = notices
        _fork_emit_event(rec)
    except Exception:
        logger.debug('engine tick emit 失败', exc_info=True)
_THINKING_BASELINE: dict[str, frozenset[str]] = {}
_THINKING_BASELINE_LOCK = threading.Lock()

def thinking_degraded_models(state: Mapping[str, Any] | None=None) -> list[str]:
    try:
        from cex_core.engine.ist_core.agents._llm import thinking_rejections
        current = frozenset(thinking_rejections())
    except Exception:
        logger.debug('思考模式降级台账读取失败', exc_info=True)
        return []
    if state is None:
        return sorted(current)
    key = str((state or {}).get('out_name') or 'engine')
    with _THINKING_BASELINE_LOCK:
        baseline = _THINKING_BASELINE.setdefault(key, current)
    return sorted(current - baseline)

def thinking_degraded_notice_cn(model: str) -> str:
    return f'模型 {model} 不支持思考模式，本批已改按普通模式编写'

def engine_card_notices(state: Mapping[str, Any] | None=None) -> list[str]:
    return [thinking_degraded_notice_cn(name) for name in thinking_degraded_models(state)]

def _emit_engine_item(**fields: Any) -> None:
    try:
        from cex_core.engine.ist_core.skills.loader import _fork_emit_event
        _fork_emit_event({'event': 'engine_item', **fields})
    except Exception:
        logger.debug('engine item emit 失败', exc_info=True)

@contextlib.contextmanager
def engine_item_span(state: dict, phase: str, item: str, *, index: int, total: int, operation: str='case'):
    span_id = f'engine-item:{uuid.uuid4().hex}'
    run = str(state.get('out_name') or 'engine')
    started = time.monotonic()
    common = {'run': run, 'phase': str(phase or ''), 'operation': str(operation or 'case'), 'span_id': span_id, 'item': str(item or ''), 'index': int(index), 'total': int(total)}
    _emit_engine_item(edge='start', **common)
    outcome = 'ok'
    error_type = ''
    try:
        yield
    except GeneratorExit:
        outcome = 'cancelled'
        raise
    except BaseException as exc:
        outcome = 'error'
        error_type = type(exc).__name__
        raise
    finally:
        _emit_engine_item(edge='end', outcome=outcome, error_type=error_type, elapsed_s=max(0.0, time.monotonic() - started), **common)

def observe_engine_items(state: dict, phase: str, items, *, item_key, operation: str='case'):
    frozen = list(items)
    total = len(frozen)
    for index, item in enumerate(frozen, start=1):
        key = str(item_key(item) or '')
        if phase != 'closing':
            from cex_core.engine.ist_core.compile_engine import engine_quarantine as EQ
            ledger = load_facts(state)
            if EQ.batch_halted(ledger) or key in EQ.quarantined_aids(ledger):
                continue
        with engine_item_span(state, phase, key, index=index, total=total, operation=operation):
            yield item

def fork_executor():
    from cex_core.engine.ist_core.resilience import ForkExecutor
    return ForkExecutor(wallclock_s=fork_wallclock_s())

def fork_wallclock_s() -> float:
    override = os.environ.get('IST_FORK_WALLCLOCK_S')
    if override:
        try:
            return float(override)
        except (TypeError, ValueError):
            pass
    return min(fork_turn_budget() * fork_stall_after_s(), 7 * 24 * 3600.0)

def fork_stall_after_s() -> float:
    base = 10.0 * fork_seconds_per_turn()
    override = os.environ.get('IST_FORK_WALLCLOCK_S')
    if override:
        try:
            return min(base, float(override))
        except (TypeError, ValueError):
            pass
    return base
_DEFAULT_TURN_BUDGET = 200

def fork_turn_budget() -> int:
    try:
        from cex_core.engine.ist_core.skills.loader import _DEFAULT_FORK_RECURSION_LIMIT
        default = int(_DEFAULT_FORK_RECURSION_LIMIT)
    except Exception:
        default = _DEFAULT_TURN_BUDGET
    try:
        return max(1, int(os.environ.get('IST_FORK_RECURSION_LIMIT') or default))
    except (TypeError, ValueError):
        return default

def fork_seconds_per_turn() -> float:
    try:
        return max(1.0, float(os.environ.get('IST_LLM_STALL_TIMEOUT') or 180.0))
    except (TypeError, ValueError):
        return 180.0

def env_flag(name: str, default: str='1') -> bool:
    v = (os.environ.get(name) or default).strip().lower()
    return v not in ('0', 'false', 'no')

def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default

class LedgerCorruptError(Exception):

    def __init__(self, path: str, detail: str):
        self.path = path
        self.detail = detail
        super().__init__(f'{path}: {detail}')

def read_json_checked(path: Path, default=None):
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return default
    except IsADirectoryError:
        return default
    except UnicodeDecodeError as e:
        raise LedgerCorruptError(str(path), f'UnicodeDecodeError: {e}') from e
    try:
        return json.loads(text)
    except Exception as e:
        raise LedgerCorruptError(str(path), f'{type(e).__name__}: {e}') from e

def signal(name: str, subject: str, **payload) -> None:
    try:
        from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
        emit_signal(name, subject, source='engine_v8', **payload)
    except Exception:
        pass

def record_first_seen(name: str, subject: str, **payload) -> str:
    try:
        from cex_core.engine.ist_core.memory.footprint.signals import record_first_seen as _rfs
        return _rfs(name, subject, source='engine_v8', **payload)
    except Exception:
        return 'write_failed'

def subtype_first_seen_report() -> list[dict]:
    try:
        from cex_core.engine.ist_core.memory.footprint import signals as SIG
        recs = SIG.read_signals(signal='subtype_first_seen')
    except Exception:
        recs = []
    first_by_subject: dict[str, dict] = {}
    for r in recs:
        subj = str(r.get('subject') or '')
        if subj and subj not in first_by_subject:
            first_by_subject[subj] = r
    labels = sorted({v for k, v in vars(V).items() if k.startswith('S_BROKEN') and isinstance(v, str)})
    out: list[dict] = []
    for label in labels:
        hit = first_by_subject.get(label)
        if hit:
            ts = hit.get('ts')
            when = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts)) if isinstance(ts, (int, float)) else '?'
            batch = str(hit.get('batch') or '?')
            out.append({'subtype': label, 'triggered': True, 'batch': batch, 'when': when, 'text': f'已触发(首次批名 {batch}/时刻 {when})'})
        else:
            out.append({'subtype': label, 'triggered': False, 'text': '自记账起点以来未触发'})
    return out

def verdict_unrecognized_batch_spread() -> dict[str, list[str]]:
    try:
        from cex_core.engine.ist_core.memory.footprint import signals as SIG
        recs = SIG.read_signals(signal='verdict_unrecognized_seen')
    except Exception:
        recs = []
    out: dict[str, list[str]] = {}
    for r in recs:
        rv = str(r.get('subject') or '')
        b = str(r.get('batch') or '')
        if not rv or not b:
            continue
        lst = out.setdefault(rv, [])
        if b not in lst:
            lst.append(b)
    return out
