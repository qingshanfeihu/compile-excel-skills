# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/environment_prepare.py（sha256 1dd6000da6f7d32c）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import contextlib
import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from cex_core.engine import knowledge_paths
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, canonical_json, lexical_absolute, sha256_bytes
logger = logging.getLogger(__name__)
_PROJECT_ROOT = _cex_data_path('')
_RUNTIME_ROOT = _PROJECT_ROOT / 'runtime'
_WORKSPACE_OUTPUTS = knowledge_paths.workspace_bucket_root('outputs', project_root=_PROJECT_ROOT)
_LOCK_PATH = _RUNTIME_ROOT / 'locks' / 'compile-environment-prepare.lock'
_PREPARATION_ACTIONS: ContextVar[list[str] | None] = ContextVar('compile_preparation_actions', default=None)
_REDEPLOYABLE_REMOTE_ATTESTATION_CODES = frozenset({'remote_deployment_contract_mismatch', 'remote_runtime_closure_drifted'})

class CompileEnvironmentPrepareError(RuntimeError):

    def __init__(self, code: str, user_reason: str='') -> None:
        super().__init__(code)
        self.code = code
        self.user_reason = user_reason or '编译环境收敛的本地安全边界不成立'

@dataclass(frozen=True)
class DeviceReleaseIdentity:
    raw_build: str
    execution_build: str
    host: str

    @property
    def environment(self) -> str:
        return f'env-{self.host}'

@dataclass(frozen=True)
class DeploymentEvidence:
    receipt_path: Path
    backup_manifest_path: Path
    source: str

@dataclass(frozen=True)
class PreparationResult:
    ok: bool
    status: str
    actions: tuple[str, ...]
    error_code: str = ''
    error_reason: str = ''
    device_identity: DeviceReleaseIdentity | None = None

    def format_markdown(self) -> str:
        lines = ['## 编译环境自动收敛', '']
        if self.ok:
            lines.append(f'- 结果：已就绪（{self.status}）')
        else:
            lines.append(f'- 结果：未收敛（{self.error_code or self.status}）')
            if self.error_reason:
                lines.append(f'- 原因：{self.error_reason}')
        if self.actions:
            lines.append('- 动作：' + '；'.join(self.actions))
        else:
            lines.append('- 动作：无')
        return '\n'.join(lines)

@contextmanager
def _preparation_lock() -> Iterator[None]:
    from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow, open_or_create_regular_at_nofollow
    parent_fd = open_directory_nofollow(_LOCK_PATH.parent, error_type=CompileEnvironmentPrepareError, invalid_message='compile environment lock path is invalid', unavailable_message='compile environment lock directory is unavailable', create_missing=True, create_mode=448)
    fd: int | None = None
    stream = None
    try:
        flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
        fd = open_or_create_regular_at_nofollow(parent_fd, _LOCK_PATH.name, flags, mode=384, error_type=CompileEnvironmentPrepareError, unavailable_message='compile environment lock is unavailable')
        stream = os.fdopen(fd, 'r+', encoding='utf-8')
        fd = None
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0)
        stream.truncate()
        stream.write(f'{os.getpid()}\t{time.time():.6f}\n')
        stream.flush()
        yield
    finally:
        if stream is not None:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()
        elif fd is not None:
            os.close(fd)
        os.close(parent_fd)

def _load_local_configuration() -> None:
    from cex_core.engine.langchain_env import langchain_load_dotenv_if_present
    langchain_load_dotenv_if_present()
    from cex_core.engine.case_compiler.config import get_config
    get_config(reload=True)

def load_compile_configuration() -> None:
    _load_local_configuration()

def _sync_markdown_knowledge_buckets() -> dict[str, dict[str, Any]]:
    from cex_core.engine.kms.webdav_sync import sync
    results: dict[str, dict[str, Any]] = {}
    for bucket in ('product', 'qa'):
        result = sync(bucket=bucket, echo=lambda message, _bucket=bucket: logger.info('KMS %s sync: %s', _bucket, message))
        bucket_result = result.get(bucket)
        if result.get('_failed') or not isinstance(bucket_result, dict):
            raise CompileEnvironmentPrepareError(f'kms_{bucket}_not_converged', f'KMS {bucket} 知识桶未能形成完整远端快照；旧快照未获准进入新编译上下文')
        results[bucket] = bucket_result
    return results

def _sync_framework(*, defer_projection_failure: bool=False) -> dict[str, Any]:
    """同步 mirror 并重生随它变的投影。

    defer_projection_failure 只给第一次同步用：投影生成排在 _deploy_candidate
    之前，不押后就够不着那条修法。押后的失败必须由调用方了结。
    """
    from cex_core.engine.ist_core.compile_engine.verified_corpus import VerifiedCorpusError, converge_verified_corpus
    try:
        corpus = converge_verified_corpus(_PROJECT_ROOT)
    except VerifiedCorpusError as exc:
        raise CompileEnvironmentPrepareError(exc.reason_code, '旧版已验证卷未能安全迁移或隔离') from exc
    from cex_core.engine.sync.framework_sync import sync
    result = sync(verbose=False)
    result['topology_action'] = _converge_network_topology()
    try:
        _converge_framework_projections()
        _converge_excel_candidate_artifacts()
    except Exception as exc:
        if not defer_projection_failure:
            raise
        logger.warning('投影重生失败，押后到部署之后重试：%s', type(exc).__name__, exc_info=True)
        result['projection_error'] = exc
    result['verified_corpus_status'] = corpus['status']
    result['verified_corpus_count'] = corpus['active_count']
    result['verified_corpus_events'] = len(corpus['events'])
    return result

def _converge_network_topology() -> str:
    """按跳板机现况重写床拓扑。探不到时保留盘上现有那份，不写半份。"""
    from cex_core.engine.scripts import gen_network_topology as gen
    try:
        topology = gen.generate()
    except Exception as exc:
        if gen._JSON_OUT.is_file():
            from cex_core.engine.ist_core.tools._shared import env_facts as _env_facts
            _env_facts.get_env_facts.cache_clear()
            try:
                _env_facts.require_env_facts()
            except _env_facts.EnvFactsUnavailable as inner:
                raise CompileEnvironmentPrepareError('network_topology_unavailable', f'床拓扑未能重探且盘上现有那份读不成事实：{inner}') from inner
            logger.warning('拓扑重探失败，沿用盘上现有那份', exc_info=True)
            return f'床拓扑未能重探（{type(exc).__name__}），沿用盘上现有那份——它可能已与实况不符'
        raise CompileEnvironmentPrepareError('network_topology_unavailable', '床拓扑既探不到也没有现存文件，可达性判据无基准') from exc
    from cex_core.engine.ist_core.tools._shared import env_facts as _env_facts
    _env_facts.get_env_facts.cache_clear()
    try:
        _env_facts.require_env_facts()
    except _env_facts.EnvFactsUnavailable as exc:
        raise CompileEnvironmentPrepareError('network_topology_unavailable', str(exc)) from exc
    devices = len(topology.get('devices') or ())
    domains = len(topology.get('_l2_domains') or ())
    observation = topology.get('_observation') or {}
    unprobed = len(observation.get('unprobed_devices') or ())
    text = f'已按跳板机现况重写床拓扑（{devices} 台设备 / {domains} 个二层域'
    text += f'，{unprobed} 台未能逐台探到）' if unprobed else '）'
    mismatched = [str(name) for name in observation.get('host_key_mismatch_devices') or ()]
    if mismatched:
        text += f"。其中 {len(mismatched)} 台主机密钥与已登记的不一致（{'、'.join(mismatched)}），已拒绝递送凭据——这不是机器没开机，请确认该地址上现在是哪台机器"
    return text

def _contract_drift_reason() -> str:
    """点名**全部**漂移的源文件。

    `_validate_contract` 按 `sorted()` 只报第一个——新床上四个补丁文件全漂，
    `lib/apv/apv.py` 只是字典序最前，只报它会把人引到错误的方向。这里从
    结构化字段现算，不解析异常正文（那条纪律是「不回显可能含路径/端点的正文」，
    而源文件相对路径是契约自己的字段，可显）。
    """
    import hashlib
    from cex_core.engine.case_compiler import excel_contract as ec
    try:
        pinned = json.loads((_PROJECT_ROOT / 'knowledge/data/compile_ref/excel_contract.json').read_text(encoding='utf-8'))['source_hashes']
    except (OSError, ValueError, KeyError, TypeError):
        return 'Excel 函数契约不可读，无法定位漂移源'
    drifted, missing = ([], [])
    for relative, expected in sorted(pinned.items()):
        path = ec._MIRROR_ROOT / relative
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            missing.append(relative)
            continue
        if actual != expected:
            drifted.append(relative)
    parts = []
    if drifted:
        parts.append(f"与契约钉的版本不一致：{'、'.join(drifted)}")
    if missing:
        parts.append(f"在 mirror 中读不到：{'、'.join(missing)}")
    detail = '；'.join(parts) or '逐文件复核时未再复现漂移'
    return f'跳板机框架源码与本仓 Excel 函数契约不同版本（{detail}）。属入口可修复：确认跳板机框架版本后重跑开批，引擎会按当前 mirror 重生契约'

def _converge_framework_projections() -> None:
    from cex_core.engine.case_compiler.framework_projection_identity import FrameworkProjectionIdentityError, validate_attribution_projection_binding
    attribution_current = True
    try:
        validate_attribution_projection_binding(_PROJECT_ROOT)
    except FrameworkProjectionIdentityError:
        attribution_current = False
    if not attribution_current:
        from cex_core.engine.scripts import gen_capability_atlas
        gen_capability_atlas.regenerate_with_carry_forward(_PROJECT_ROOT)
    try:
        validate_attribution_projection_binding(_PROJECT_ROOT)
    except FrameworkProjectionIdentityError as exc:
        raise CompileEnvironmentPrepareError(exc.reason_code, 'framework 镜像与重生后的公开投影仍未闭合') from exc
    _converge_confirmation_prompt_projection()
    _converge_framework_derived_projections()

def _converge_confirmation_prompt_projection() -> bool:
    """按当前 mirror 重写确认提示投影。内容同一则复用。

    它只从 mirror 源码 AST 派生、不入库，所以新克隆上第一次开批前盘上没有这份。
    排在 mirror 同步之后、读它的 emit/apv_lang 投影生成之前。

    空投影 fail-closed：`build()` 对不在场的 mirror 只会扫出 0 条 lib_patterns，
    静默交一份空表会让确认提示判据整片失效而卷面照出。
    """
    from cex_core.engine.scripts import gen_confirmation_prompt_projection as gen
    try:
        payload = gen.build()
    except Exception as exc:
        raise CompileEnvironmentPrepareError('confirmation_prompt_projection_not_converged', '确认提示投影未能按当前 mirror 重生') from exc
    if not (payload.get('lib_patterns') or ()):
        raise CompileEnvironmentPrepareError('confirmation_prompt_projection_not_converged', '确认提示投影重生出空表——mirror 源码不在场或读不成 AST')
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    out = _PROJECT_ROOT / 'knowledge/data/compile_ref/confirmation_prompt_patterns.json'
    try:
        if out.is_file() and out.read_text(encoding='utf-8') == rendered:
            return False
    except OSError:
        pass
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered, encoding='utf-8')
    return True

def _converge_framework_derived_projections() -> dict[str, Any]:
    from cex_core.engine.ist_core.compile_engine.framework_projections import FrameworkDerivedProjectionError, converge_framework_derived_projections
    try:
        return converge_framework_derived_projections(_PROJECT_ROOT)
    except FrameworkDerivedProjectionError as exc:
        raise CompileEnvironmentPrepareError(exc.reason_code, 'framework/已验证卷换代后的生成式投影未能安全收敛') from exc

def _converge_language_docs_projection() -> bool:
    from cex_core.engine.ist_core.compile_engine.framework_projections import FrameworkDerivedProjectionError, converge_language_docs_projection
    try:
        return converge_language_docs_projection(_PROJECT_ROOT)
    except FrameworkDerivedProjectionError as exc:
        raise CompileEnvironmentPrepareError(exc.reason_code, '判据规则换代后的语言目录投影未能安全收敛') from exc

def _converge_excel_candidate_artifacts() -> None:
    from cex_core.engine.case_compiler import excel_release
    try:
        excel_release.validate_candidate_artifact_set()
        return
    except (excel_release.ExcelReleaseError, FileNotFoundError):
        pass
    from cex_core.engine.scripts.maintenance import build_excel_contract_workbooks as builder
    paths = excel_release.CandidateArtifactPaths()
    preview_dir = _RUNTIME_ROOT / 'excel_release' / 'candidate_previews'
    try:
        builder.build(['--contract', str(paths.contract), '--runtime', str(paths.runtime_template), '--review', str(paths.ide_workbook), '--manifest', str(paths.manifest), '--preview-dir', str(preview_dir)])
        excel_release.validate_candidate_artifact_set(paths)
    except Exception as exc:
        raise CompileEnvironmentPrepareError('excel_candidate_identity_not_converged', '现役 Excel 契约与原子重建后的候选四件套仍未闭合') from exc

def _converge_device_command_tree(identity: DeviceReleaseIdentity, *, product_version: str, local_xml_path: str='', local_xml_sha256: str='') -> None:
    from cex_core.engine.case_compiler.vendor_stdlib import clear_vendor_stdlib_cache, load_vendor_stdlib
    from cex_core.engine.sync.command_tree_sync import CommandTreeSyncError, publish_local_command_tree, resolve_family_key, sync_vendor_command_tree_from_config
    from cex_core.engine.scripts.maintenance.build_vendor_stdlib import generate_vendor_stdlib_projection
    version = str(product_version or '').strip()
    if not version:
        raise CompileEnvironmentPrepareError('product_version_missing', '命令树收敛缺少产品版本身份')
    try:
        version = resolve_family_key(version, identity.raw_build)
    except CommandTreeSyncError as exc:
        raise CompileEnvironmentPrepareError('product_version_axis_mismatch', str(exc)) from exc
    try:
        if local_xml_path:
            candidate = lexical_absolute(_PROJECT_ROOT / local_xml_path)
            inputs = lexical_absolute(knowledge_paths.workspace_bucket_root('inputs', project_root=_PROJECT_ROOT))
            try:
                candidate.relative_to(inputs)
            except ValueError as exc:
                raise CompileEnvironmentPrepareError('local_command_tree_outside_inputs', '本地命令树不在 workspace/inputs 边界内') from exc
            publish_local_command_tree(xml_path=candidate, expected_sha256=str(local_xml_sha256 or ''), full_version=identity.raw_build, version=version, projection_builder=generate_vendor_stdlib_projection)
        elif load_vendor_stdlib(version, identity.raw_build) is None:
            sync_vendor_command_tree_from_config(identity.raw_build, version)
    except CommandTreeSyncError as exc:
        raise CompileEnvironmentPrepareError('device_command_tree_sync_failed', str(exc) or '真机命令树同步失败') from exc
    clear_vendor_stdlib_cache(version, identity.raw_build)
    if load_vendor_stdlib(version, identity.raw_build) is None:
        raise CompileEnvironmentPrepareError('device_command_tree_not_converged', '真机 build 对应的密封命令树投影未能加载')

def active_projection_rebuild_verdict(identity: DeviceReleaseIdentity, *, product_version: str) -> dict[str, str]:
    """入口要不要重铸命令树代际——与预检「投影 catalog 时新性」同一份判据（2026-09-14）。

    投影只随它声明的输入换代：源 XML（代际本身钉死）、生成策略（``projection_policy``）、
    分族 catalog（``stats.value_domain.manual_catalog.identity``）。三者都是当前的就沿用
    活动代际；策略过期、catalog 换代/不可比、投影不可加载才重铸。footprint 回填不在此列：
    它是引擎上机写回的产物，不是编译输入——无条件重铸时投影只差
    ``stats.value_domain.footprint_*`` 计数也会换出新 generation_id，同名续跑在 bed_gate
    绑定时判 capability_xml 换档、整批归档重编（<batch> 09:02 实证；与
    09-12「批自己的写回改了知识轴」同族，只是漏在能力轴）。
    返回 ``{"rebuild": "yes"|"no", "reason": <稳定码>}``。
    """
    from cex_core.engine.case_compiler.vendor_stdlib import clear_vendor_stdlib_cache, load_vendor_stdlib
    from cex_core.engine.kms.manual_catalog_store import projection_catalog_freshness
    from cex_core.engine.sync.command_tree_sync import projection_policy_identity
    version = str(product_version or '').strip()
    clear_vendor_stdlib_cache(version, identity.raw_build)
    try:
        payload = load_vendor_stdlib(version, identity.raw_build)
    except Exception as exc:
        return {'rebuild': 'yes', 'reason': f'projection_unloadable:{type(exc).__name__}'}
    if not isinstance(payload, dict):
        return {'rebuild': 'yes', 'reason': 'projection_unavailable'}
    if payload.get('projection_policy') != projection_policy_identity():
        return {'rebuild': 'yes', 'reason': 'policy_stale'}
    verdict = projection_catalog_freshness(payload)
    status = str(verdict.get('status') or '') if isinstance(verdict, dict) else ''
    if status != 'current':
        return {'rebuild': 'yes', 'reason': f"catalog_{status or 'unknown'}"}
    return {'rebuild': 'no', 'reason': 'current'}

def refresh_compile_projections(identity: DeviceReleaseIdentity, *, product_version: str) -> tuple[str, ...]:
    from cex_core.engine.case_compiler.vendor_stdlib import clear_vendor_stdlib_cache, device_os_build_suffix, load_vendor_stdlib
    from cex_core.engine.sync.command_tree_sync import CommandTreeSyncError, parse_build_identity, rebuild_active_command_tree_projection, resolve_family_key
    from cex_core.engine.scripts import gen_command_teardown_atlas, gen_criterion_rules, gen_vendor_pacing_usage
    version = str(product_version or '').strip()
    try:
        parse_build_identity(identity.raw_build)
    except CommandTreeSyncError:
        pass
    else:
        try:
            version = resolve_family_key(version, identity.raw_build)
        except CommandTreeSyncError as exc:
            raise CompileEnvironmentPrepareError('product_version_axis_mismatch', str(exc)) from exc
    verdict = active_projection_rebuild_verdict(identity, product_version=version)
    logger.info('入口命令树代际判定: rebuild=%s reason=%s build=%s version=%s', verdict['rebuild'], verdict['reason'], identity.raw_build, version)
    if verdict['rebuild'] == 'yes':
        rebuild_active_command_tree_projection(identity.raw_build, version)
        generation_action = f"已按当前 Manual/catalog 收敛真机命令树代际（{verdict['reason']}）"
    else:
        generation_action = '命令树代际按预检判据仍是当前的（生成策略与分族 catalog 未变），沿用活动代际'
    clear_vendor_stdlib_cache(version, identity.raw_build)
    if load_vendor_stdlib(version, identity.raw_build) is None:
        raise CompileEnvironmentPrepareError('device_command_tree_rebuild_unreadable', '按当前 Manual/catalog 重生的真机命令树投影不可消费')
    build = device_os_build_suffix(identity.raw_build)
    if not build:
        raise CompileEnvironmentPrepareError('device_build_suffix_unavailable', '真机 build 不能归一为派生投影身份')
    gen_command_teardown_atlas.main(['--device-build', build, '--version', version])
    gen_criterion_rules.main([])
    gen_vendor_pacing_usage.main(['--version', version, '--device-build', build])
    _converge_language_docs_projection()
    return (generation_action, '已收敛命令清场与判据规则投影（内容同一则复用）', '已闭合判据规则的全部下游公开投影')

def _probe_release_identity() -> DeviceReleaseIdentity:
    from cex_core.engine.case_compiler.config import get_config
    from cex_core.engine.ist_core.compile_engine import bed
    from cex_core.engine.ist_core.tools.device.run_case import _do_probe
    cfg = get_config(reload=True)
    probes = dict(bed.load_grammar().get('bed_probes') or {})
    spec = probes.get('build')
    if not isinstance(spec, dict):
        raise CompileEnvironmentPrepareError('device_build_probe_unavailable', '领域文法没有可用的设备 build 探针')
    command = str(spec.get('cmd') or '').strip()
    extract = str(spec.get('extract') or '').strip()
    if not command or not extract:
        raise CompileEnvironmentPrepareError('device_build_probe_unavailable', '设备 build 探针契约不完整')
    raw = bed.probe_resilient(lambda cmd: _do_probe(cmd, annotate=False), command)
    if bed._probe_failed(raw):
        raise CompileEnvironmentPrepareError('device_build_probe_failed', '设备 build 只读探测失败，不能复用或签发 Excel 证据')
    match = re.search(extract, raw)
    captured = match.group(1).strip() if match else ''
    from cex_core.engine.sync.command_tree_sync import CommandTreeSyncError, parse_build_identity_from_text
    try:
        raw_build = parse_build_identity_from_text(captured or raw).full_version
    except CommandTreeSyncError as exc:
        raise CompileEnvironmentPrepareError('device_build_identity_unparseable', '设备 build 回显无法解析为完整产品身份') from exc
    execution_build = bed.mysql_safe_build(raw_build, fallback=cfg.build)
    if not raw_build or not bed.is_mysql_safe_identifier(execution_build):
        raise CompileEnvironmentPrepareError('device_build_identity_invalid', '设备 build 回显不能形成安全的上机身份')
    host = str(cfg.jumphost.host or '').strip()
    if not host:
        raise CompileEnvironmentPrepareError('jumphost_endpoint_missing', '跳板机地址未配置')
    return DeviceReleaseIdentity(raw_build, execution_build, host)

def _promotion_receipt_path() -> Path:
    configured = os.environ.get('IST_EXCEL_PROMOTION_RECEIPT', '').strip()
    return Path(configured) if configured else _RUNTIME_ROOT / 'excel_release' / 'promotion_receipt.json'

def _activate_canonical_promotion_receipt() -> Path:
    canonical = lexical_absolute(_RUNTIME_ROOT / 'excel_release' / 'promotion_receipt.json')
    target = lexical_absolute(_promotion_receipt_path())
    runtime = lexical_absolute(_RUNTIME_ROOT)
    try:
        target.relative_to(runtime)
    except ValueError:
        target = canonical
        os.environ['IST_EXCEL_PROMOTION_RECEIPT'] = str(canonical)
    if target == canonical:
        from cex_core.engine.case_compiler import excel_release
        try:
            excel_release._read_regular_nofollow(canonical, label='canonical promotion receipt', trusted_root=runtime)
        except (OSError, excel_release.ExcelReleaseError) as exc:
            raise CompileEnvironmentPrepareError('canonical_promotion_receipt_unavailable', '自动签发的标准 promotion receipt 不可用') from exc
        return target
    from cex_core.engine.case_compiler import excel_release
    try:
        raw = excel_release._read_regular_nofollow(canonical, label='canonical promotion receipt', trusted_root=runtime)
    except (OSError, excel_release.ExcelReleaseError) as exc:
        raise CompileEnvironmentPrepareError('canonical_promotion_receipt_unavailable', '自动签发的标准 promotion receipt 不可用') from exc
    atomic_write_bytes_nofollow(target, raw, error_type=CompileEnvironmentPrepareError, invalid_message='configured promotion receipt path is invalid', unavailable_message='configured promotion receipt could not be activated', mode=384)
    return target

def _stable_release_failure_code(payload: dict[str, Any]) -> str:
    for field in ('error_code', 'error'):
        value = str(payload.get(field) or '')
        if re.fullmatch('[a-z][a-z0-9_]{0,79}', value):
            return value
    return 'excel_release_run_failed'

def _selection_matches_identity(selection: Any, identity: DeviceReleaseIdentity) -> bool:
    return getattr(selection, 'release_state', '') == 'promoted' and getattr(selection, 'device_build', None) == identity.execution_build and (getattr(selection, 'environment', None) == identity.environment)

def _attest_current_remote_deployment(candidate: Any, *, known_hosts: Path) -> Path | None:
    from cex_core.engine.case_compiler import excel_release
    from cex_core.engine.scripts.maintenance import backup_jumphost_framework as backup
    from cex_core.engine.scripts.maintenance import patch_jumphost_excel_runtime as patch
    target = backup._current_target()
    ssh = backup._connect_strict(target, backup._read_password(target), known_hosts)
    try:
        transaction = patch._read_remote_transaction(ssh, target)
        if transaction is None:
            return None
        deployment = transaction.get('deployment_receipt')
        if transaction.get('schema') != 1 or transaction.get('scope') != 'excel_runtime_remote_transaction' or transaction.get('status') != 'committed' or (not isinstance(deployment, dict)):
            raise CompileEnvironmentPrepareError('remote_deployment_not_committed', '跳板机 Excel runtime 事务不是可复用的 committed 终态')
        deployment_sha = sha256_bytes(canonical_json(deployment, ensure_ascii=True))
        if transaction.get('deployment_receipt_sha256') != deployment_sha:
            raise CompileEnvironmentPrepareError('remote_deployment_receipt_mismatch', '跳板机事务与内嵌 deployment receipt 身份不一致')
        try:
            excel_release._validate_deployment_receipt(deployment, contract=candidate.contract, contract_file_sha256=sha256_bytes(candidate.contract_bytes))
        except excel_release.ExcelReleaseError as exc:
            raise CompileEnvironmentPrepareError('remote_deployment_contract_mismatch', '跳板机部署收据不绑定当前 Excel 契约') from exc
        expected = {relative: {'exists': True, 'sha256': digest} for relative, digest in candidate.contract['source_hashes'].items()}
        expected['lib/excel_contract.json'] = {'exists': True, 'sha256': sha256_bytes(candidate.contract_bytes)}
        observed = patch.collect_remote_state(ssh, target, tuple(sorted(expected)))
        if observed != expected:
            raise CompileEnvironmentPrepareError('remote_runtime_closure_drifted', '跳板机当前 runtime 文件闭包已与 committed 部署漂移')
        if deployment.get('host_key_sha256') != backup._remote_host_key_sha256(ssh):
            raise CompileEnvironmentPrepareError('remote_host_identity_drifted', '跳板机主机密钥与部署收据不一致')
    finally:
        ssh.close()
    transaction_id = str(deployment.get('transaction') or '')
    safe_id = transaction_id if re.fullmatch('[0-9a-f]{32}', transaction_id) else deployment_sha[:32]
    target_path = _RUNTIME_ROOT / 'jumphost_deployments' / f'recovered-{safe_id}' / 'deployment_receipt.json'
    raw = json.dumps(deployment, ensure_ascii=False, indent=1, sort_keys=True).encode('utf-8') + b'\n'
    atomic_write_bytes_nofollow(target_path, raw, error_type=CompileEnvironmentPrepareError, invalid_message='recovered deployment receipt path is invalid', unavailable_message='recovered deployment receipt could not be stored', mode=384)
    return target_path

def _jumphost_runtime_drifted() -> tuple[bool, str]:
    """跳板机上那份 Excel runtime 是不是我们部署的版本。

    不连跳板机：mirror 忠实反映远端字节，所以对它跑一遍部署用的 transform，
    结果与它自己不同就说明远端那份还没被补过。
    """
    from cex_core.engine.scripts.maintenance import patch_jumphost_excel_runtime as patch
    mirror = _PROJECT_ROOT / 'knowledge' / 'framework' / 'mirror'
    transforms = {'lib/test_xlsx.py': patch.transform_test_xlsx, 'lib/apv/apv.py': patch.transform_apv, 'lib/apv/apv_ssh.py': patch.transform_apv_ssh, 'lib/apv/clear.py': patch.transform_clear}
    differences: list[str] = []
    unsupported: list[str] = []
    for relative, transform in transforms.items():
        source_path = mirror / relative
        if not source_path.is_file():
            unsupported.append(f'{relative} 不在本地镜像里')
            continue
        try:
            current = source_path.read_text(encoding='utf-8')
        except OSError:
            unsupported.append(f'{relative} 读不出来')
            continue
        try:
            expected = transform(current)
        except Exception as exc:
            detail = str(exc) if isinstance(exc, patch.PatchError) else type(exc).__name__
            unsupported.append(f'{relative}：{detail}')
            continue
        if expected != current:
            differences.append(f'{relative} 有可应用的受管补丁')
    if unsupported:
        raise CompileEnvironmentPrepareError('excel_runtime_source_unsupported', '运行时源码尚无确定性转换路径：' + '；'.join(unsupported) + '。未进入运行时备份与部署；同一输入重复开批不会修复这些差异。')
    return (bool(differences), '；'.join(differences))

def _backup_current_contract(*, known_hosts: Path) -> Path:
    from cex_core.engine.scripts.maintenance import backup_jumphost_framework as backup
    result = backup.backup_current(known_hosts=known_hosts, allowlist=backup.contract_source_allowlist())
    return Path(result['snapshot']) / 'manifest.json'

def _sidecar_contract_for(stage_path: Path, generated: Path) -> Path:
    """设备上的 sidecar 该用哪份契约。

    设备 runtime 拿 sidecar 判 E/F 是否 enabled，并核对 xlsx 的 marker sha，
    所以它必须是**本地生效那份**（含认证晋升）；用 staging 产的裸契约，ssl/ha
    会是 disabled、marker 也对不上。只有当本地契约按的源与 staged runner 不同
    （框架换版的首次部署）才退回裸契约，那一轮之后本地契约会按新源重生。
    """
    from pathlib import PurePosixPath
    from cex_core.engine.scripts.maintenance import patch_jumphost_excel_runtime as patch
    current = _PROJECT_ROOT / 'knowledge/data/compile_ref/excel_contract.json'
    if not current.is_file():
        return generated
    try:
        overrides = {relative: (stage_path / 'tree' / Path(*PurePosixPath(relative).parts)).read_bytes() for relative in patch.TARGET_FILES}
        patch.load_contract_sidecar(current, source_overrides=overrides)
    except Exception:
        return generated
    return current

def _deploy_candidate(*, known_hosts: Path) -> DeploymentEvidence:
    from cex_core.engine.scripts.maintenance import backup_jumphost_framework as backup
    from cex_core.engine.scripts.maintenance import patch_jumphost_excel_runtime as patch
    from cex_core.engine.scripts import gen_capability_atlas
    snapshot = backup.backup_current(known_hosts=known_hosts, allowlist=backup.contract_source_allowlist())
    snapshot_path = Path(snapshot['snapshot'])
    actions = _PREPARATION_ACTIONS.get()
    if actions is not None:
        actions.append('已完成跳板机框架密封备份')
    sources = patch.stage_sources_from_backup(snapshot_path)
    if actions is not None:
        actions.append('运行时源码变换与同源校验已完成')
    stage_path = Path(sources['stage'])
    generated_contract = stage_path / 'generated_excel_contract.json'
    gen_capability_atlas.main(['--source-overlay-root', str(sources['overlay_root']), '--excel-contract-out', str(generated_contract)])
    patch.seal_staging(snapshot_path, stage_path, _sidecar_contract_for(stage_path, generated_contract))
    deployed = patch.deploy_staged(snapshot_path, stage_path, known_hosts=known_hosts)
    return DeploymentEvidence(receipt_path=Path(deployed['receipt']), backup_manifest_path=snapshot_path / 'manifest.json', source='deployed')

def _new_release_id(candidate: Any) -> str:
    from cex_core.engine.case_compiler.excel_release_bundle import candidate_fingerprint
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    return f'auto-{stamp}-{candidate_fingerprint(candidate)[:12]}-{uuid.uuid4().hex[:8]}'

def _release_row_matches_identity(row: dict[str, Any], identity: DeviceReleaseIdentity) -> bool:
    from cex_core.engine.ist_core.compile_engine.facts import FrameworkResultState, read_framework_result
    framework = read_framework_result(row)
    return bool(row.get('verdict') == 'pass' and framework.state == FrameworkResultState.GIVEN and (framework.value == 'pass') and (row.get('execution_build') == identity.execution_build) and (row.get('_env_jumphost') == identity.host))
_BASELINE_NON_RESIDUE_KINDS = frozenset({'build_anchor', 'mirror_sync', 'vendor_build_anchor', 'bed_closure_failed'})

def _baseline_residue(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for finding in report.get('findings') or [] if isinstance(finding, dict) and finding.get('kind') not in _BASELINE_NON_RESIDUE_KINDS and (not finding.get('probe_failed')) and (not finding.get('ledger_stuck')) and (not finding.get('maintenance_explained'))]

def _check_baseline_probe_health(report: dict[str, Any]) -> None:
    for finding in report.get('findings') or []:
        if not isinstance(finding, dict):
            continue
        if finding.get('probe_failed'):
            raise CompileEnvironmentPrepareError('device_bed_probe_failed', '设备只读探测失败，床态未知，不能安全进入编译')
        if finding.get('kind') == 'build_anchor':
            anchor = finding.get('detail') or {}
            if str(anchor.get('status') or '') == 'unknown':
                raise CompileEnvironmentPrepareError('device_build_anchor_unknown', '真机或配置 build 无法解析出版本家族；请核对 IST_DEVICE_BUILD 后重跑')
            raise CompileEnvironmentPrepareError('device_build_family_mismatch', '真机 build 与配置 IST_DEVICE_BUILD 跨 minor 失配；请更新配置后重跑')

def _serial_baseline_reset(identity: DeviceReleaseIdentity, actions: list[str] | None=None) -> None:
    logger.warning('设备基线未闭合，启动串口基线重置: host=%s build=%s', identity.host, identity.raw_build)
    from cex_core.engine.case_compiler.device_mcp_client import FrameworkMCPClient
    try:
        with FrameworkMCPClient() as client:
            if client.host != identity.host:
                raise CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '串口初始化通道指向的跳板机与当前验证床不一致，已放弃自动重置')
            res = client.init_device(device_index=0)
    except CompileEnvironmentPrepareError:
        raise
    except Exception as exc:
        raise CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '设备串口基线重置通道异常，已失败关闭') from exc
    data = res if isinstance(res, dict) else {}
    ok = bool(data) and (not data.get('error'))
    try:
        initialized = int(data.get('initialized') or 0)
        failed = int(data.get('failed') or 0)
        total = int(data.get('total') or 0)
    except (TypeError, ValueError):
        ok = False
    else:
        ok = ok and failed == 0 and (initialized == total) and (total > 0)
    if not ok:
        if 'IST_LOCALHOST_SSH_PASS' in str(data.get('error') or ''):
            raise CompileEnvironmentPrepareError('serial_reset_credentials_missing', '串口基线重置通道缺 IST_LOCALHOST_SSH_PASS；设备本身未被判定有残留')
        raise CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '设备串口基线重置未成功（含床被其它会话占用），已失败关闭')
    reprobed = _probe_release_identity()
    if reprobed.raw_build != identity.raw_build or reprobed.host != identity.host:
        raise CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '串口基线重置后设备身份与初探不一致，已失败关闭')
    if actions is not None:
        actions.append('已通过物理串口重置设备干净基线（清配并还原接口 IP），身份复探一致')

def _converge_device_baseline(identity: DeviceReleaseIdentity, actions: list[str]) -> None:
    from cex_core.engine.case_compiler.config import get_config
    from cex_core.engine.ist_core.compile_engine import bed
    from cex_core.engine.ist_core.tools.device.run_case import _do_probe
    cfg_build = str(get_config().build or '').strip()

    def _check_once() -> list[dict[str, Any]]:
        report = bed.bed_check(lambda cmd: _do_probe(cmd, annotate=False), cfg_build, root=_PROJECT_ROOT, host=identity.host)
        _check_baseline_probe_health(report)
        return _baseline_residue(report)
    residue = _check_once()
    if not residue:
        actions.append('已核对设备床基线（只读体检无残留）')
        return
    clean = bed.bed_cleanup(lambda cmd: _do_probe(cmd, mode='config'), residue, root=_PROJECT_ROOT, host=identity.host, batch='environment-prepare')
    actions.append(f"床体检发现残留，已按文法清理引用执行开工必净（清成 {len(clean['cleaned'])} 项" + (f"，失败 {len(clean.get('failed') or [])} 项" if clean.get('failed') else '') + (f"，无清理引用 {len(clean['skipped'])} 项" if clean.get('skipped') else '') + '）')
    residue = _check_once()
    if not residue:
        actions.append('文法清理后复检床态已干净')
        return
    logger.warning('文法清理后仍有 %d 项床残留，启动串口基线兜底: host=%s', len(residue), identity.host)
    _serial_baseline_reset(identity, actions)
    residue = _check_once()
    if residue:
        raise CompileEnvironmentPrepareError('device_bed_baseline_not_converged', '文法清理与串口基线重置后床残留仍未闭合，需人工检查设备')
    actions.append('串口基线重置后复检床态已干净')

def _execute_release_volume(workbook_path: Path, identity: DeviceReleaseIdentity) -> list[dict[str, Any]]:
    completed = subprocess.run([sys.executable, '-m', 'scripts.maintenance.run_excel_release_volume', '--workbook', str(workbook_path), '--build', identity.execution_build, '--required-host', identity.host], cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=2700, check=False)
    if completed.returncode != 0:
        raise CompileEnvironmentPrepareError('excel_release_runner_failed', 'Excel release 隔离上机进程未正常收口')
    result_text = ''
    for line in reversed(completed.stdout.splitlines()):
        stripped = line.strip()
        if stripped.startswith(('[', '{')):
            result_text = stripped
            break
    try:
        rows = json.loads(result_text)
    except (TypeError, ValueError) as exc:
        raise CompileEnvironmentPrepareError('excel_release_run_protocol_error', 'Excel release 上机返回了不可解析的证据') from exc
    if isinstance(rows, dict):
        raise CompileEnvironmentPrepareError(_stable_release_failure_code(rows), 'Excel release 整卷上机未完成，未签发 promotion')
    if not isinstance(rows, list) or len(rows) != 1 or (not isinstance(rows[0], dict)):
        raise CompileEnvironmentPrepareError('excel_release_run_not_pass', 'Excel release 覆盖卷没有形成同床、同 build 的真实 PASS 闭包')
    return rows

def _run_release_and_promote(candidate: Any, identity: DeviceReleaseIdentity, evidence: DeploymentEvidence, actions: list[str] | None=None) -> Any:
    from cex_core.engine.case_compiler.excel_capability_samples import build_capability_sample_artifacts
    from cex_core.engine.case_compiler.excel_release import select_promoted_runtime_template
    from cex_core.engine.scripts.maintenance import emit_excel_release_evidence
    release_id = _new_release_id(candidate)
    output_dir = _WORKSPACE_OUTPUTS / 'excel_environment' / release_id
    output_dir.mkdir(mode=448, parents=True, exist_ok=False)
    workbook_path = output_dir / 'excel_capability_samples.xlsx'
    manifest_path = output_dir / 'excel_capability_samples.manifest.json'
    build_capability_sample_artifacts(contract_path=candidate.paths.contract, template_path=candidate.paths.runtime_template, workbook_path=workbook_path, manifest_path=manifest_path, autoid='990000000000000001', trusted_runtime_root=_WORKSPACE_OUTPUTS, device_build=identity.raw_build)
    rows = _execute_release_volume(workbook_path, identity)
    if not _release_row_matches_identity(rows[0], identity):
        logger.warning('Excel release 覆盖卷首轮未形成 PASS 闭包，启动串口基线自愈: host=%s build=%s', identity.host, identity.raw_build)
        _serial_baseline_reset(identity, actions)
        rows = _execute_release_volume(workbook_path, identity)
        if not _release_row_matches_identity(rows[0], identity):
            raise CompileEnvironmentPrepareError('excel_release_run_not_pass', 'Excel release 覆盖卷经串口基线重置重试后仍没有形成同床、同 build 的真实 PASS 闭包')
        if actions is not None:
            actions.append('设备首次验证未闭合，已自动通过串口重置干净基线并重新验证签发 promotion')
    last_run = output_dir / 'last_run.json'
    atomic_write_bytes_nofollow(last_run, json.dumps(rows, ensure_ascii=False, indent=1, sort_keys=True).encode('utf-8') + b'\n', error_type=CompileEnvironmentPrepareError, invalid_message='release run evidence path is invalid', unavailable_message='release run evidence could not be stored', mode=384)
    argv = ['--evidence-dir', str(output_dir), '--run-evidence', str(last_run), '--deployment-receipt', str(evidence.receipt_path), '--backup-manifest', str(evidence.backup_manifest_path), '--release-id', release_id, '--jumphost-host', identity.host]
    with contextlib.redirect_stdout(__import__('io').StringIO()):
        try:
            result = emit_excel_release_evidence.main(argv)
        except SystemExit as exc:
            raise CompileEnvironmentPrepareError('excel_release_signing_failed', 'Excel release 证据签发器拒绝了本次闭包') from exc
    if result != 0:
        raise CompileEnvironmentPrepareError('excel_release_signing_failed', 'Excel release 证据签发器未成功收口')
    _activate_canonical_promotion_receipt()
    selected = select_promoted_runtime_template()
    if not _selection_matches_identity(selected, identity):
        raise CompileEnvironmentPrepareError('excel_release_identity_drifted', '新签发的 promotion 与当前设备/跳板机身份不一致')
    return selected

def _publish_bundle(candidate: Any, identity: DeviceReleaseIdentity, *, known_hosts: Path) -> None:
    from cex_core.engine.case_compiler.excel_release_bundle import build_release_bundle, publish_remote_release_bundle
    raw = build_release_bundle(_promotion_receipt_path())
    publish_remote_release_bundle(raw, candidate=candidate, device_build=identity.execution_build, environment=identity.environment, known_hosts=known_hosts)

def _try_restore_bundle(candidate: Any, identity: DeviceReleaseIdentity, *, known_hosts: Path) -> Any | None:
    from cex_core.engine.case_compiler.excel_release_bundle import fetch_remote_release_bundle, install_release_bundle
    raw = fetch_remote_release_bundle(candidate=candidate, device_build=identity.execution_build, known_hosts=known_hosts)
    if raw is None:
        return None
    install_release_bundle(raw, device_build=identity.execution_build, environment=identity.environment)
    _activate_canonical_promotion_receipt()
    from cex_core.engine.case_compiler.excel_release import select_promoted_runtime_template
    return select_promoted_runtime_template()

def _ensure_compile_environment_locked(*, product_version: str='', local_xml_path: str='', local_xml_sha256: str='') -> PreparationResult:
    from cex_core.engine.case_compiler import excel_release
    actions = _PREPARATION_ACTIONS.get()
    if actions is None:
        actions = []
    known_hosts = Path.home() / '.ssh' / 'known_hosts'
    _load_local_configuration()
    actions.append('已启动 product/QA 知识桶同步')
    markdown_sync = _sync_markdown_knowledge_buckets()
    actions.append(f"已同步 product/QA 知识桶并隔离台账外或远端删除的旧件（更新 {sum((int(row.get('synced') or 0) for row in markdown_sync.values()))} 件）")
    actions.append('已启动框架镜像同步与派生投影收敛')
    sync_result = _sync_framework(defer_projection_failure=True)
    actions.append(f"已对账跳板机框架镜像（更新 {int(sync_result.get('pulled') or 0)} 个文件；旧卷处置 {int(sync_result.get('verified_corpus_events') or 0)} 件）")
    topology_action = str(sync_result.get('topology_action') or '')
    if topology_action:
        actions.append(topology_action)
    deferred_projection_error = sync_result.get('projection_error')
    runtime_drifted, drift_detail = _jumphost_runtime_drifted()
    try:
        if runtime_drifted:
            raise excel_release.ExcelReleaseError(drift_detail)
        candidate = excel_release.validate_candidate_artifact_set()
    except excel_release.ExcelReleaseError:
        deployed = _deploy_candidate(known_hosts=known_hosts)
        actions.append(f'跳板机自动化环境已按本仓目标更新并事务部署（{drift_detail}）' if runtime_drifted else '候选 Excel runtime 已经密封备份并事务部署')
        _sync_framework()
        if deferred_projection_error is not None:
            actions.append('部署后投影已按跳板机上的新框架重生')
        deferred_projection_error = None
        try:
            candidate = excel_release.validate_candidate_artifact_set()
        except excel_release.ExcelReleaseError as exc:
            raise CompileEnvironmentPrepareError('candidate_identity_not_converged', '事务部署后本地镜像仍不能验证 Excel 候选四件套') from exc
    else:
        deployed = None
    if deferred_projection_error is not None:
        raise CompileEnvironmentPrepareError('framework_projection_not_converged', '框架派生投影重生失败，且候选 Excel runtime 无需部署——没有可自动执行的修法') from deferred_projection_error
    identity = _probe_release_identity()
    actions.append('已核对当前设备 build 身份')
    _converge_device_command_tree(identity, product_version=product_version, local_xml_path=local_xml_path, local_xml_sha256=local_xml_sha256)
    actions.append('已按真机 build 收敛密封命令树投影')
    _converge_device_baseline(identity, actions)
    redeploy_reason = ''
    try:
        remote_receipt = _attest_current_remote_deployment(candidate, known_hosts=known_hosts)
    except CompileEnvironmentPrepareError as exc:
        if exc.code not in _REDEPLOYABLE_REMOTE_ATTESTATION_CODES:
            raise
        remote_receipt = None
        redeploy_reason = exc.code
    if remote_receipt is None and deployed is None:
        deployed = _deploy_candidate(known_hosts=known_hosts)
        actions.append('远端部署身份与当前候选不一致，已自动重建密封事务收据' if redeploy_reason else '远端缺少可验证事务收据，已自动补做密封事务部署')
        _sync_framework()
        try:
            candidate = excel_release.validate_candidate_artifact_set()
        except excel_release.ExcelReleaseError as exc:
            raise CompileEnvironmentPrepareError('candidate_identity_not_converged', '远端事务部署后本地镜像仍不能验证 Excel 候选四件套') from exc
        remote_receipt = _attest_current_remote_deployment(candidate, known_hosts=known_hosts)
        if remote_receipt is None:
            raise CompileEnvironmentPrepareError('remote_deployment_receipt_missing', '自动事务部署后仍没有可验证的 committed 部署收据')
    elif remote_receipt is None:
        remote_receipt = deployed.receipt_path
    else:
        actions.append('已从远端 committed 事务恢复 deployment receipt')
    try:
        selection = excel_release.select_promoted_runtime_template()
    except (excel_release.ExcelReleaseError, FileNotFoundError):
        selection = None
    if selection is not None and _selection_matches_identity(selection, identity):
        actions.append('已复用同候选、同跳板机、同 build 的本地 promotion')
        try:
            _publish_bundle(candidate, identity, known_hosts=known_hosts)
        except Exception:
            actions.append('可迁移证据缓存回写失败，下次将自动重试')
        return PreparationResult(True, 'promotion_reused', tuple(actions), device_identity=identity)
    if selection is not None:
        actions.append('本地 promotion 与当前环境身份不一致，已拒绝复用')
    restored = _try_restore_bundle(candidate, identity, known_hosts=known_hosts)
    if restored is not None:
        if not _selection_matches_identity(restored, identity):
            raise CompileEnvironmentPrepareError('portable_promotion_identity_mismatch', '迁移后 promotion 未与当前环境身份闭合')
        actions.append('已从跳板机内容寻址库迁移已认证 promotion，未重复上机')
        return PreparationResult(True, 'promotion_restored', tuple(actions), device_identity=identity)
    if deployed is None:
        backup_manifest = _backup_current_contract(known_hosts=known_hosts)
        deployment = DeploymentEvidence(receipt_path=remote_receipt, backup_manifest_path=backup_manifest, source='recovered')
    else:
        deployment = DeploymentEvidence(receipt_path=remote_receipt, backup_manifest_path=deployed.backup_manifest_path, source=deployed.source)
    _run_release_and_promote(candidate, identity, deployment, actions=actions)
    actions.append('未找到同身份可迁移证据；已自动完成一次 release 整卷上机与 promotion 签发')
    _publish_bundle(candidate, identity, known_hosts=known_hosts)
    actions.append('已把完整 promotion 闭包回存跳板机，其它本地环境可直接迁移')
    final = excel_release.select_promoted_runtime_template()
    if not _selection_matches_identity(final, identity):
        raise CompileEnvironmentPrepareError('final_promotion_validation_failed', '自动收敛结束后 production 模板仍未与当前环境身份闭合')
    return PreparationResult(True, 'promotion_created', tuple(actions), device_identity=identity)

def ensure_compile_environment(*, product_version: str='', local_xml_path: str='', local_xml_sha256: str='') -> PreparationResult:
    actions: list[str] = []
    token = _PREPARATION_ACTIONS.set(actions)
    try:
        with _preparation_lock():
            return _ensure_compile_environment_locked(product_version=product_version, local_xml_path=local_xml_path, local_xml_sha256=local_xml_sha256)
    except CompileEnvironmentPrepareError as exc:
        return PreparationResult(False, 'failed', tuple(actions), error_code=exc.code, error_reason=exc.user_reason)
    except Exception as exc:
        from cex_core.engine.case_compiler.apv_lang import QueryUnavailable
        from cex_core.engine.case_compiler.excel_contract import ExcelContractError
        from cex_core.engine.sync.command_tree_sync import CommandTreeSyncError
        from cex_core.engine.scripts.maintenance.backup_jumphost_framework import BackupError
        from cex_core.engine.scripts.maintenance.patch_jumphost_excel_runtime import PatchError
        if isinstance(exc, ExcelContractError):
            return PreparationResult(False, 'failed', tuple(actions), error_code='excel_contract_source_drift', error_reason=_contract_drift_reason())
        if isinstance(exc, QueryUnavailable):
            return PreparationResult(False, 'failed', tuple(actions), error_code='framework_mirror_incomplete', error_reason=str(exc) or 'framework mirror 残缺，公开投影无法重生')
        if isinstance(exc, CommandTreeSyncError):
            logger.error('命令树同步失败: %s', exc)
            return PreparationResult(False, 'failed', tuple(actions), error_code='device_command_tree_sync_failed', error_reason=str(exc) or '真机命令树同步失败')
        if isinstance(exc, PatchError):
            return PreparationResult(False, 'failed', tuple(actions), error_code='excel_runtime_patch_failed', error_reason=str(exc) or '跳板机 Excel 运行时补丁失败')
        if isinstance(exc, BackupError):
            return PreparationResult(False, 'failed', tuple(actions), error_code='jumphost_backup_failed', error_reason=str(exc) or '跳板机密封备份失败')
        return PreparationResult(False, 'failed', tuple(actions), error_code=f'environment_prepare_{type(exc).__name__}', error_reason='自动环境收敛发生未分类错误，已失败关闭')
    finally:
        _PREPARATION_ACTIONS.reset(token)
__all__ = ['CompileEnvironmentPrepareError', 'DeploymentEvidence', 'DeviceReleaseIdentity', 'PreparationResult', 'ensure_compile_environment', 'load_compile_configuration', 'active_projection_rebuild_verdict', 'refresh_compile_projections']
