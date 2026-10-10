// 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/environment_prepare.py（sha256 1dd6000da6f7d32c）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";

import { _cex_data_path } from "../../_root";
import { P, PyValueError, pyJsonDumps } from "../../_py";
import { acquireLockSync } from "../../../../platform/index";
import * as knowledge_paths from "../../knowledge_paths";
import { atomic_write_bytes_nofollow, canonical_json, lexical_absolute, sha256_bytes } from "../../case_compiler/_sealed_io";

const logger = {
  warning: (..._args: any[]) => {},
  error: (..._args: any[]) => {},
  info: (..._args: any[]) => {},
};

const _PROJECT_ROOT = new P(_cex_data_path(''));
const _RUNTIME_ROOT = _PROJECT_ROOT.joinpath('runtime');
const _WORKSPACE_OUTPUTS = new P(knowledge_paths.workspace_bucket_root('outputs', { project_root: _PROJECT_ROOT.toString() }));
const _LOCK_PATH = _RUNTIME_ROOT.joinpath('locks', 'compile-environment-prepare.lock');
let _PREPARATION_ACTIONS: string[] | null = null;
const _REDEPLOYABLE_REMOTE_ATTESTATION_CODES = new Set(['remote_deployment_contract_mismatch', 'remote_runtime_closure_drifted']);

export class CompileEnvironmentPrepareError extends Error {
  code: string;
  user_reason: string;
  constructor(code: string, user_reason: string = '') {
    super(code);
    this.code = code;
    this.user_reason = user_reason || '编译环境收敛的本地安全边界不成立';
  }
}

class CompileEnvironmentPrepareErrorAsError extends CompileEnvironmentPrepareError {
  constructor(message: string = '') {
    super('environment_prepare_error', message);
    (this as any).code = 'environment_prepare_error';
    (this as any).user_reason = message || '编译环境收敛的本地安全边界不成立';
  }
}

export class DeviceReleaseIdentity {
  raw_build: string = '';
  execution_build: string = '';
  host: string = '';

  constructor(raw_build: string = '', execution_build: string = '', host: string = '') {
    this.raw_build = raw_build;
    this.execution_build = execution_build;
    this.host = host;
  }

  get environment(): string {
    return `env-${this.host}`;
  }
}

export class DeploymentEvidence {
  receipt_path: P;
  backup_manifest_path: P;
  source: string;

  constructor(init: { receipt_path: P; backup_manifest_path: P; source: string }) {
    this.receipt_path = init.receipt_path;
    this.backup_manifest_path = init.backup_manifest_path;
    this.source = init.source;
  }
}

export class PreparationResult {
  ok: boolean;
  status: string;
  actions: string[];
  error_code: string = '';
  error_reason: string = '';
  device_identity: DeviceReleaseIdentity | null = null;

  constructor(ok: boolean, status: string, actions: string[], opts: { error_code?: string; error_reason?: string; device_identity?: DeviceReleaseIdentity | null } = {}) {
    this.ok = ok;
    this.status = status;
    this.actions = actions;
    this.error_code = opts.error_code ?? '';
    this.error_reason = opts.error_reason ?? '';
    this.device_identity = opts.device_identity ?? null;
  }

  format_markdown(): string {
    const lines = ['## 编译环境自动收敛', ''];
    if (this.ok) {
      lines.push(`- 结果：已就绪（${this.status}）`);
    } else {
      lines.push(`- 结果：未收敛（${this.error_code || this.status}）`);
      if (this.error_reason) {
        lines.push(`- 原因：${this.error_reason}`);
      }
    }
    if (this.actions.length) {
      lines.push('- 动作：' + this.actions.join('；'));
    } else {
      lines.push('- 动作：无');
    }
    return lines.join('\n');
  }
}

function _preparation_lock<T>(fn: () => T): T {
  const lock = acquireLockSync(_LOCK_PATH.toString());
  try {
    try {
      fs.writeFileSync(_LOCK_PATH.toString(), `${process.pid}\t${(Date.now() / 1000).toFixed(6)}\n`, 'utf-8');
    } catch {}
    return fn();
  } finally {
    lock.release();
  }
}

function _load_local_configuration(): void {
  const { langchain_load_dotenv_if_present } = require("../../langchain_env");
  langchain_load_dotenv_if_present();
  const { get_config } = require("../../case_compiler/config");
  get_config({ reload: true });
}

export function load_compile_configuration(): void {
  _load_local_configuration();
}

function _sync_markdown_knowledge_buckets(): Record<string, Record<string, any>> {
  const { sync } = require("../../kms/webdav_sync");
  const results: Record<string, Record<string, any>> = {};
  for (const bucket of ['product', 'qa']) {
    const result = sync({ bucket, echo: (message: string) => logger.info('KMS %s sync: %s', bucket, message) });
    const bucket_result = result[bucket];
    if (result['_failed'] || typeof bucket_result !== "object" || bucket_result === null || Array.isArray(bucket_result)) {
      throw new CompileEnvironmentPrepareError(`kms_${bucket}_not_converged`, `KMS ${bucket} 知识桶未能形成完整远端快照；旧快照未获准进入新编译上下文`);
    }
    results[bucket] = bucket_result;
  }
  return results;
}

function _sync_framework(opts: { defer_projection_failure?: boolean } = {}): Record<string, any> {
  const defer_projection_failure = opts.defer_projection_failure ?? false;
  const { VerifiedCorpusError, converge_verified_corpus } = require("./verified_corpus");
  let corpus: Record<string, any>;
  try {
    corpus = converge_verified_corpus(_PROJECT_ROOT);
  } catch (exc: any) {
    if (exc instanceof VerifiedCorpusError) {
      throw new CompileEnvironmentPrepareError(exc.reason_code, '旧版已验证卷未能安全迁移或隔离');
    }
    throw exc;
  }
  const { sync } = require("../../sync/framework_sync");
  const result: Record<string, any> = sync({ verbose: false });
  result['topology_action'] = _converge_network_topology();
  try {
    _converge_framework_projections();
    _converge_excel_candidate_artifacts();
  } catch (exc) {
    if (!defer_projection_failure) {
      throw exc;
    }
    logger.warning('投影重生失败，押后到部署之后重试：%s', (exc as any)?.constructor?.name ?? 'Error');
    result['projection_error'] = exc;
  }
  result['verified_corpus_status'] = corpus['status'];
  result['verified_corpus_count'] = corpus['active_count'];
  result['verified_corpus_events'] = (corpus['events'] || []).length;
  return result;
}

function _converge_network_topology(): string {
  const gen = require("../../scripts/gen_network_topology");
  let topology: Record<string, any>;
  try {
    topology = gen.generate();
  } catch (exc: any) {
    if (gen._JSON_OUT.is_file()) {
      const _env_facts = require("../tools/_shared/env_facts");
      _env_facts.get_env_facts.cache_clear();
      try {
        _env_facts.require_env_facts();
      } catch (inner: any) {
        if (inner instanceof _env_facts.EnvFactsUnavailable) {
          throw new CompileEnvironmentPrepareError('network_topology_unavailable', `床拓扑未能重探且盘上现有那份读不成事实：${inner}`);
        }
        throw inner;
      }
      logger.warning('拓扑重探失败，沿用盘上现有那份');
      return `床拓扑未能重探（${exc?.constructor?.name ?? 'Error'}），沿用盘上现有那份——它可能已与实况不符`;
    }
    throw new CompileEnvironmentPrepareError('network_topology_unavailable', '床拓扑既探不到也没有现存文件，可达性判据无基准');
  }
  const _env_facts = require("../tools/_shared/env_facts");
  _env_facts.get_env_facts.cache_clear();
  try {
    _env_facts.require_env_facts();
  } catch (exc: any) {
    if (exc instanceof _env_facts.EnvFactsUnavailable) {
      throw new CompileEnvironmentPrepareError('network_topology_unavailable', String(exc?.message ?? exc));
    }
    throw exc;
  }
  const devices = (topology['devices'] || []).length;
  const domains = (topology['_l2_domains'] || []).length;
  const observation = topology['_observation'] || {};
  const unprobed = (observation['unprobed_devices'] || []).length;
  let text = `已按跳板机现况重写床拓扑（${devices} 台设备 / ${domains} 个二层域`;
  text += unprobed ? `，${unprobed} 台未能逐台探到）` : '）';
  const mismatched = (observation['host_key_mismatch_devices'] || []).map((name: any) => String(name));
  if (mismatched.length) {
    text += `。其中 ${mismatched.length} 台主机密钥与已登记的不一致（${mismatched.join('、')}），已拒绝递送凭据——这不是机器没开机，请确认该地址上现在是哪台机器`;
  }
  return text;
}

function _contract_drift_reason(): string {
  const ec = require("../../case_compiler/excel_contract");
  let pinned: Record<string, string>;
  try {
    pinned = JSON.parse(fs.readFileSync(_PROJECT_ROOT.joinpath('knowledge/data/compile_ref/excel_contract.json').toString(), 'utf-8'))['source_hashes'];
  } catch {
    return 'Excel 函数契约不可读，无法定位漂移源';
  }
  const drifted: string[] = [];
  const missing: string[] = [];
  for (const [relative, expected] of Object.entries(pinned).sort()) {
    const p = new P(String(ec._MIRROR_ROOT)).joinpath(relative);
    let actual: string;
    try {
      actual = crypto.createHash("sha256").update(fs.readFileSync(p.toString())).digest("hex");
    } catch {
      missing.push(relative);
      continue;
    }
    if (actual !== expected) {
      drifted.push(relative);
    }
  }
  const parts: string[] = [];
  if (drifted.length) {
    parts.push(`与契约钉的版本不一致：${drifted.join('、')}`);
  }
  if (missing.length) {
    parts.push(`在 mirror 中读不到：${missing.join('、')}`);
  }
  const detail = parts.join('；') || '逐文件复核时未再复现漂移';
  return `跳板机框架源码与本仓 Excel 函数契约不同版本（${detail}）。属入口可修复：确认跳板机框架版本后重跑开批，引擎会按当前 mirror 重生契约`;
}

function _converge_framework_projections(): void {
  const { FrameworkProjectionIdentityError, validate_attribution_projection_binding } = require("../../case_compiler/framework_projection_identity");
  let attribution_current = true;
  try {
    validate_attribution_projection_binding(_PROJECT_ROOT);
  } catch (exc) {
    if (exc instanceof FrameworkProjectionIdentityError) {
      attribution_current = false;
    } else {
      throw exc;
    }
  }
  if (!attribution_current) {
    const gen_capability_atlas = require("../../scripts/gen_capability_atlas");
    gen_capability_atlas.regenerate_with_carry_forward(_PROJECT_ROOT);
  }
  try {
    validate_attribution_projection_binding(_PROJECT_ROOT);
  } catch (exc: any) {
    if (exc instanceof FrameworkProjectionIdentityError) {
      throw new CompileEnvironmentPrepareError(exc.reason_code, 'framework 镜像与重生后的公开投影仍未闭合');
    }
    throw exc;
  }
  _converge_confirmation_prompt_projection();
  _converge_framework_derived_projections();
}

function _converge_confirmation_prompt_projection(): boolean {
  const gen = require("../../scripts/gen_confirmation_prompt_projection");
  let payload: Record<string, any>;
  try {
    payload = gen.build();
  } catch (exc) {
    throw new CompileEnvironmentPrepareError('confirmation_prompt_projection_not_converged', '确认提示投影未能按当前 mirror 重生');
  }
  if (!(payload['lib_patterns'] || []).length) {
    throw new CompileEnvironmentPrepareError('confirmation_prompt_projection_not_converged', '确认提示投影重生出空表——mirror 源码不在场或读不成 AST');
  }
  const rendered = pyJsonDumps(payload, { ensure_ascii: false, indent: 2 }) + '\n';
  const out = _PROJECT_ROOT.joinpath('knowledge/data/compile_ref/confirmation_prompt_patterns.json');
  try {
    if (out.is_file() && fs.readFileSync(out.toString(), 'utf-8') === rendered) {
      return false;
    }
  } catch {}
  fs.mkdirSync(out.parent.toString(), { recursive: true });
  fs.writeFileSync(out.toString(), rendered, 'utf-8');
  return true;
}

function _converge_framework_derived_projections(): Record<string, any> {
  const { FrameworkDerivedProjectionError, converge_framework_derived_projections } = require("./framework_projections");
  try {
    return converge_framework_derived_projections(_PROJECT_ROOT);
  } catch (exc: any) {
    if (exc instanceof FrameworkDerivedProjectionError) {
      throw new CompileEnvironmentPrepareError(exc.reason_code, 'framework/已验证卷换代后的生成式投影未能安全收敛');
    }
    throw exc;
  }
}

function _converge_language_docs_projection(): boolean {
  const { FrameworkDerivedProjectionError, converge_language_docs_projection } = require("./framework_projections");
  try {
    return converge_language_docs_projection(_PROJECT_ROOT);
  } catch (exc: any) {
    if (exc instanceof FrameworkDerivedProjectionError) {
      throw new CompileEnvironmentPrepareError(exc.reason_code, '判据规则换代后的语言目录投影未能安全收敛');
    }
    throw exc;
  }
}

function _converge_excel_candidate_artifacts(): void {
  const excel_release = require("../../case_compiler/excel_release");
  try {
    excel_release.validate_candidate_artifact_set();
    return;
  } catch (exc: any) {
    if (!(exc instanceof excel_release.ExcelReleaseError) && !(exc?.code === 'ENOENT')) {
      throw exc;
    }
  }
  const builder = require("../../scripts/maintenance/build_excel_contract_workbooks");
  const paths = excel_release.CandidateArtifactPaths();
  const preview_dir = _RUNTIME_ROOT.joinpath('excel_release', 'candidate_previews');
  try {
    builder.build(['--contract', String(paths.contract), '--runtime', String(paths.runtime_template), '--review', String(paths.ide_workbook), '--manifest', String(paths.manifest), '--preview-dir', preview_dir.toString()]);
    excel_release.validate_candidate_artifact_set(paths);
  } catch (exc) {
    throw new CompileEnvironmentPrepareError('excel_candidate_identity_not_converged', '现役 Excel 契约与原子重建后的候选四件套仍未闭合');
  }
}

function _converge_device_command_tree(identity: DeviceReleaseIdentity, opts: { product_version: string; local_xml_path?: string; local_xml_sha256?: string }): void {
  const { product_version } = opts;
  const local_xml_path = opts.local_xml_path ?? '';
  const local_xml_sha256 = opts.local_xml_sha256 ?? '';
  const { clear_vendor_stdlib_cache, load_vendor_stdlib } = require("../../case_compiler/vendor_stdlib");
  const { CommandTreeSyncError, publish_local_command_tree, resolve_family_key, sync_vendor_command_tree_from_config } = require("../../sync/command_tree_sync");
  const { generate_vendor_stdlib_projection } = require("../../scripts/maintenance/build_vendor_stdlib");
  let version = String(product_version || '').trim();
  if (!version) {
    throw new CompileEnvironmentPrepareError('product_version_missing', '命令树收敛缺少产品版本身份');
  }
  try {
    version = resolve_family_key(version, identity.raw_build);
  } catch (exc: any) {
    if (exc instanceof CommandTreeSyncError) {
      throw new CompileEnvironmentPrepareError('product_version_axis_mismatch', String(exc?.message ?? exc));
    }
    throw exc;
  }
  try {
    if (local_xml_path) {
      const candidate = new P(lexical_absolute(_PROJECT_ROOT.joinpath(local_xml_path).toString()));
      const inputs = new P(lexical_absolute(knowledge_paths.workspace_bucket_root('inputs', { project_root: _PROJECT_ROOT.toString() })));
      try {
        candidate.relative_to(inputs);
      } catch (exc) {
        throw new CompileEnvironmentPrepareError('local_command_tree_outside_inputs', '本地命令树不在 workspace/inputs 边界内');
      }
      publish_local_command_tree({ xml_path: candidate, expected_sha256: String(local_xml_sha256 || ''), full_version: identity.raw_build, version, projection_builder: generate_vendor_stdlib_projection });
    } else if (load_vendor_stdlib(version, identity.raw_build) === null || load_vendor_stdlib(version, identity.raw_build) === undefined) {
      sync_vendor_command_tree_from_config(identity.raw_build, version);
    }
  } catch (exc: any) {
    if (exc instanceof CommandTreeSyncError) {
      throw new CompileEnvironmentPrepareError('device_command_tree_sync_failed', String(exc?.message ?? exc) || '真机命令树同步失败');
    }
    throw exc;
  }
  clear_vendor_stdlib_cache(version, identity.raw_build);
  if (load_vendor_stdlib(version, identity.raw_build) === null || load_vendor_stdlib(version, identity.raw_build) === undefined) {
    throw new CompileEnvironmentPrepareError('device_command_tree_not_converged', '真机 build 对应的密封命令树投影未能加载');
  }
}

export function active_projection_rebuild_verdict(identity: DeviceReleaseIdentity, opts: { product_version: string }): Record<string, string> {
  const { clear_vendor_stdlib_cache, load_vendor_stdlib } = require("../../case_compiler/vendor_stdlib");
  const { projection_catalog_freshness } = require("../../kms/manual_catalog_store");
  const { projection_policy_identity } = require("../../sync/command_tree_sync");
  const version = String(opts.product_version || '').trim();
  clear_vendor_stdlib_cache(version, identity.raw_build);
  let payload: any;
  try {
    payload = load_vendor_stdlib(version, identity.raw_build);
  } catch (exc: any) {
    return { 'rebuild': 'yes', 'reason': `projection_unloadable:${exc?.constructor?.name ?? 'Error'}` };
  }
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    return { 'rebuild': 'yes', 'reason': 'projection_unavailable' };
  }
  if (payload['projection_policy'] !== projection_policy_identity()) {
    return { 'rebuild': 'yes', 'reason': 'policy_stale' };
  }
  const verdict = projection_catalog_freshness(payload);
  const status = (typeof verdict === "object" && verdict !== null) ? String(verdict['status'] || '') : '';
  if (status !== 'current') {
    return { 'rebuild': 'yes', 'reason': `catalog_${status || 'unknown'}` };
  }
  return { 'rebuild': 'no', 'reason': 'current' };
}

export function refresh_compile_projections(identity: DeviceReleaseIdentity, opts: { product_version: string }): string[] {
  const { clear_vendor_stdlib_cache, device_os_build_suffix, load_vendor_stdlib } = require("../../case_compiler/vendor_stdlib");
  const { CommandTreeSyncError, parse_build_identity, rebuild_active_command_tree_projection, resolve_family_key } = require("../../sync/command_tree_sync");
  const gen_command_teardown_atlas = require("../../scripts/gen_command_teardown_atlas");
  const gen_criterion_rules = require("../../scripts/gen_criterion_rules");
  const gen_vendor_pacing_usage = require("../../scripts/gen_vendor_pacing_usage");
  let version = String(opts.product_version || '').trim();
  let parsed = true;
  try {
    parse_build_identity(identity.raw_build);
  } catch (exc) {
    if (!(exc instanceof CommandTreeSyncError)) throw exc;
    parsed = false;
  }
  if (parsed) {
    try {
      version = resolve_family_key(version, identity.raw_build);
    } catch (exc: any) {
      if (exc instanceof CommandTreeSyncError) {
        throw new CompileEnvironmentPrepareError('product_version_axis_mismatch', String(exc?.message ?? exc));
      }
      throw exc;
    }
  }
  const verdict = active_projection_rebuild_verdict(identity, { product_version: version });
  logger.info('入口命令树代际判定: rebuild=%s reason=%s build=%s version=%s', verdict['rebuild'], verdict['reason'], identity.raw_build, version);
  let generation_action: string;
  if (verdict['rebuild'] === 'yes') {
    rebuild_active_command_tree_projection(identity.raw_build, version);
    generation_action = `已按当前 Manual/catalog 收敛真机命令树代际（${verdict['reason']}）`;
  } else {
    generation_action = '命令树代际按预检判据仍是当前的（生成策略与分族 catalog 未变），沿用活动代际';
  }
  clear_vendor_stdlib_cache(version, identity.raw_build);
  if (load_vendor_stdlib(version, identity.raw_build) === null || load_vendor_stdlib(version, identity.raw_build) === undefined) {
    throw new CompileEnvironmentPrepareError('device_command_tree_rebuild_unreadable', '按当前 Manual/catalog 重生的真机命令树投影不可消费');
  }
  const build = device_os_build_suffix(identity.raw_build);
  if (!build) {
    throw new CompileEnvironmentPrepareError('device_build_suffix_unavailable', '真机 build 不能归一为派生投影身份');
  }
  gen_command_teardown_atlas.main(['--device-build', build, '--version', version]);
  gen_criterion_rules.main([]);
  gen_vendor_pacing_usage.main(['--version', version, '--device-build', build]);
  _converge_language_docs_projection();
  return [generation_action, '已收敛命令清场与判据规则投影（内容同一则复用）', '已闭合判据规则的全部下游公开投影'];
}

function _probe_release_identity(): DeviceReleaseIdentity {
  const { get_config } = require("../../case_compiler/config");
  const bed = require("./bed");
  const { _do_probe } = require("../tools/device/run_case");
  const cfg = get_config({ reload: true });
  const probes = { ...(bed.load_grammar()['bed_probes'] || {}) };
  const spec = probes['build'];
  if (typeof spec !== "object" || spec === null || Array.isArray(spec)) {
    throw new CompileEnvironmentPrepareError('device_build_probe_unavailable', '领域文法没有可用的设备 build 探针');
  }
  const command = String(spec['cmd'] || '').trim();
  const extract = String(spec['extract'] || '').trim();
  if (!command || !extract) {
    throw new CompileEnvironmentPrepareError('device_build_probe_unavailable', '设备 build 探针契约不完整');
  }
  const raw = bed.probe_resilient((cmd: string) => _do_probe(cmd, { annotate: false }), command);
  if (bed._probe_failed(raw)) {
    throw new CompileEnvironmentPrepareError('device_build_probe_failed', '设备 build 只读探测失败，不能复用或签发 Excel 证据');
  }
  const match = new RegExp(extract).exec(raw);
  const captured = match ? String(match[1]).trim() : '';
  const { CommandTreeSyncError, parse_build_identity_from_text } = require("../../sync/command_tree_sync");
  let raw_build: string;
  try {
    raw_build = parse_build_identity_from_text(captured || raw).full_version;
  } catch (exc) {
    if (exc instanceof CommandTreeSyncError) {
      throw new CompileEnvironmentPrepareError('device_build_identity_unparseable', '设备 build 回显无法解析为完整产品身份');
    }
    throw exc;
  }
  const execution_build = bed.mysql_safe_build(raw_build, { fallback: cfg.build });
  if (!raw_build || !bed.is_mysql_safe_identifier(execution_build)) {
    throw new CompileEnvironmentPrepareError('device_build_identity_invalid', '设备 build 回显不能形成安全的上机身份');
  }
  const host = String(cfg.jumphost.host || '').trim();
  if (!host) {
    throw new CompileEnvironmentPrepareError('jumphost_endpoint_missing', '跳板机地址未配置');
  }
  return new DeviceReleaseIdentity(raw_build, execution_build, host);
}

function _promotion_receipt_path(): P {
  const configured = String(process.env['IST_EXCEL_PROMOTION_RECEIPT'] || '').trim();
  return configured ? new P(configured) : _RUNTIME_ROOT.joinpath('excel_release', 'promotion_receipt.json');
}

function _activate_canonical_promotion_receipt(): P {
  const canonical = lexical_absolute(_RUNTIME_ROOT.joinpath('excel_release', 'promotion_receipt.json').toString());
  let target = lexical_absolute(_promotion_receipt_path().toString());
  const runtime = lexical_absolute(_RUNTIME_ROOT.toString());
  try {
    new P(target).relative_to(new P(runtime));
  } catch {
    target = canonical;
    process.env['IST_EXCEL_PROMOTION_RECEIPT'] = canonical;
  }
  if (target === canonical) {
    const excel_release = require("../../case_compiler/excel_release");
    try {
      excel_release._read_regular_nofollow(canonical, { label: 'canonical promotion receipt', trusted_root: runtime });
    } catch (exc: any) {
      if (exc instanceof excel_release.ExcelReleaseError || exc?.code === 'ENOENT' || exc instanceof Error) {
        throw new CompileEnvironmentPrepareError('canonical_promotion_receipt_unavailable', '自动签发的标准 promotion receipt 不可用');
      }
      throw exc;
    }
    return new P(target);
  }
  const excel_release = require("../../case_compiler/excel_release");
  let raw: Buffer;
  try {
    raw = excel_release._read_regular_nofollow(canonical, { label: 'canonical promotion receipt', trusted_root: runtime });
  } catch (exc: any) {
    if (exc instanceof excel_release.ExcelReleaseError || exc instanceof Error) {
      throw new CompileEnvironmentPrepareError('canonical_promotion_receipt_unavailable', '自动签发的标准 promotion receipt 不可用');
    }
    throw exc;
  }
  atomic_write_bytes_nofollow(target, raw, { errorType: CompileEnvironmentPrepareErrorAsError, invalid_message: 'configured promotion receipt path is invalid', unavailable_message: 'configured promotion receipt could not be activated', mode: 0o600 });
  return new P(target);
}

function _stable_release_failure_code(payload: Record<string, any>): string {
  for (const field of ['error_code', 'error']) {
    const value = String(payload[field] || '');
    if (/^[a-z][a-z0-9_]{0,79}$/.test(value)) {
      return value;
    }
  }
  return 'excel_release_run_failed';
}

function _selection_matches_identity(selection: any, identity: DeviceReleaseIdentity): boolean {
  return selection?.release_state === 'promoted' && selection?.device_build === identity.execution_build && selection?.environment === identity.environment;
}

function _attest_current_remote_deployment(candidate: any, opts: { known_hosts: P }): P | null {
  const { known_hosts } = opts;
  const excel_release = require("../../case_compiler/excel_release");
  const backup = require("../../scripts/maintenance/backup_jumphost_framework");
  const patch = require("../../scripts/maintenance/patch_jumphost_excel_runtime");
  const target = backup._current_target();
  const ssh = backup._connect_strict(target, backup._read_password(target), known_hosts);
  let deployment: Record<string, any>;
  let deployment_sha: string;
  try {
    const transaction = patch._read_remote_transaction(ssh, target);
    if (transaction === null || transaction === undefined) {
      return null;
    }
    deployment = transaction['deployment_receipt'];
    if (transaction['schema'] !== 1 || transaction['scope'] !== 'excel_runtime_remote_transaction' || transaction['status'] !== 'committed' || typeof deployment !== "object" || deployment === null || Array.isArray(deployment)) {
      throw new CompileEnvironmentPrepareError('remote_deployment_not_committed', '跳板机 Excel runtime 事务不是可复用的 committed 终态');
    }
    deployment_sha = sha256_bytes(canonical_json(deployment, { ensure_ascii: true }));
    if (transaction['deployment_receipt_sha256'] !== deployment_sha) {
      throw new CompileEnvironmentPrepareError('remote_deployment_receipt_mismatch', '跳板机事务与内嵌 deployment receipt 身份不一致');
    }
    try {
      excel_release._validate_deployment_receipt(deployment, { contract: candidate.contract, contract_file_sha256: sha256_bytes(candidate.contract_bytes) });
    } catch (exc: any) {
      if (exc instanceof excel_release.ExcelReleaseError) {
        throw new CompileEnvironmentPrepareError('remote_deployment_contract_mismatch', '跳板机部署收据不绑定当前 Excel 契约');
      }
      throw exc;
    }
    const expected: Record<string, Record<string, any>> = {};
    for (const [relative, digest] of Object.entries(candidate.contract['source_hashes'])) {
      expected[relative] = { 'exists': true, 'sha256': digest };
    }
    expected['lib/excel_contract.json'] = { 'exists': true, 'sha256': sha256_bytes(candidate.contract_bytes) };
    const observed = patch.collect_remote_state(ssh, target, [...Object.keys(expected)].sort());
    if (JSON.stringify(observed) !== JSON.stringify(expected)) {
      throw new CompileEnvironmentPrepareError('remote_runtime_closure_drifted', '跳板机当前 runtime 文件闭包已与 committed 部署漂移');
    }
    if (deployment['host_key_sha256'] !== backup._remote_host_key_sha256(ssh)) {
      throw new CompileEnvironmentPrepareError('remote_host_identity_drifted', '跳板机主机密钥与部署收据不一致');
    }
  } finally {
    ssh.close();
  }
  const transaction_id = String(deployment['transaction'] || '');
  const safe_id = /^[0-9a-f]{32}$/.test(transaction_id) ? transaction_id : deployment_sha.slice(0, 32);
  const target_path = _RUNTIME_ROOT.joinpath('jumphost_deployments', `recovered-${safe_id}`, 'deployment_receipt.json');
  const raw = Buffer.from(pyJsonDumps(deployment, { ensure_ascii: false, indent: 1, sort_keys: true }) + '\n', 'utf-8');
  atomic_write_bytes_nofollow(target_path.toString(), raw, { errorType: CompileEnvironmentPrepareErrorAsError, invalid_message: 'recovered deployment receipt path is invalid', unavailable_message: 'recovered deployment receipt could not be stored', mode: 0o600 });
  return target_path;
}

function _jumphost_runtime_drifted(): [boolean, string] {
  const patch = require("../../scripts/maintenance/patch_jumphost_excel_runtime");
  const mirror = _PROJECT_ROOT.joinpath('knowledge', 'framework', 'mirror');
  const transforms: Record<string, (s: string) => string> = { 'lib/test_xlsx.py': patch.transform_test_xlsx, 'lib/apv/apv.py': patch.transform_apv, 'lib/apv/apv_ssh.py': patch.transform_apv_ssh, 'lib/apv/clear.py': patch.transform_clear };
  const differences: string[] = [];
  const unsupported: string[] = [];
  for (const [relative, transform] of Object.entries(transforms)) {
    const source_path = mirror.joinpath(relative);
    if (!source_path.is_file()) {
      unsupported.push(`${relative} 不在本地镜像里`);
      continue;
    }
    let current: string;
    try {
      current = fs.readFileSync(source_path.toString(), 'utf-8');
    } catch {
      unsupported.push(`${relative} 读不出来`);
      continue;
    }
    let expected: string;
    try {
      expected = transform(current);
    } catch (exc: any) {
      const detail = exc instanceof patch.PatchError ? String(exc?.message ?? exc) : (exc?.constructor?.name ?? 'Error');
      unsupported.push(`${relative}：${detail}`);
      continue;
    }
    if (expected !== current) {
      differences.push(`${relative} 有可应用的受管补丁`);
    }
  }
  if (unsupported.length) {
    throw new CompileEnvironmentPrepareError('excel_runtime_source_unsupported', '运行时源码尚无确定性转换路径：' + unsupported.join('；') + '。未进入运行时备份与部署；同一输入重复开批不会修复这些差异。');
  }
  return [!!differences.length, differences.join('；')];
}

function _backup_current_contract(opts: { known_hosts: P }): P {
  const backup = require("../../scripts/maintenance/backup_jumphost_framework");
  const result = backup.backup_current({ known_hosts: opts.known_hosts, allowlist: backup.contract_source_allowlist() });
  return new P(result['snapshot']).joinpath('manifest.json');
}

function _sidecar_contract_for(stage_path: P, generated: P): P {
  const patch = require("../../scripts/maintenance/patch_jumphost_excel_runtime");
  const current = _PROJECT_ROOT.joinpath('knowledge/data/compile_ref/excel_contract.json');
  if (!current.is_file()) {
    return generated;
  }
  try {
    const overrides: Record<string, Buffer> = {};
    for (const relative of patch.TARGET_FILES) {
      overrides[relative] = fs.readFileSync(stage_path.joinpath('tree', ...String(relative).split('/')).toString());
    }
    patch.load_contract_sidecar(current, { source_overrides: overrides });
  } catch {
    return generated;
  }
  return current;
}

function _deploy_candidate(opts: { known_hosts: P }): DeploymentEvidence {
  const backup = require("../../scripts/maintenance/backup_jumphost_framework");
  const patch = require("../../scripts/maintenance/patch_jumphost_excel_runtime");
  const gen_capability_atlas = require("../../scripts/gen_capability_atlas");
  const snapshot = backup.backup_current({ known_hosts: opts.known_hosts, allowlist: backup.contract_source_allowlist() });
  const snapshot_path = new P(snapshot['snapshot']);
  const actions = _PREPARATION_ACTIONS;
  if (actions !== null) {
    actions.push('已完成跳板机框架密封备份');
  }
  const sources = patch.stage_sources_from_backup(snapshot_path);
  if (actions !== null) {
    actions.push('运行时源码变换与同源校验已完成');
  }
  const stage_path = new P(sources['stage']);
  const generated_contract = stage_path.joinpath('generated_excel_contract.json');
  gen_capability_atlas.main(['--source-overlay-root', String(sources['overlay_root']), '--excel-contract-out', generated_contract.toString()]);
  patch.seal_staging(snapshot_path, stage_path, _sidecar_contract_for(stage_path, generated_contract));
  const deployed = patch.deploy_staged(snapshot_path, stage_path, { known_hosts: opts.known_hosts });
  return new DeploymentEvidence({ receipt_path: new P(deployed['receipt']), backup_manifest_path: snapshot_path.joinpath('manifest.json'), source: 'deployed' });
}

function _new_release_id(candidate: any): string {
  const { candidate_fingerprint } = require("../../case_compiler/excel_release_bundle");
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, 'Z');
  return `auto-${stamp}-${candidate_fingerprint(candidate).slice(0, 12)}-${crypto.randomBytes(4).toString('hex')}`;
}

function _release_row_matches_identity(row: Record<string, any>, identity: DeviceReleaseIdentity): boolean {
  const { FrameworkResultState, read_framework_result } = require("./facts");
  const framework = read_framework_result(row);
  return !!(row['verdict'] === 'pass' && framework.state === FrameworkResultState.GIVEN && framework.value === 'pass' && row['execution_build'] === identity.execution_build && row['_env_jumphost'] === identity.host);
}

const _BASELINE_NON_RESIDUE_KINDS = new Set(['build_anchor', 'mirror_sync', 'vendor_build_anchor', 'bed_closure_failed']);

function _baseline_residue(report: Record<string, any>): Record<string, any>[] {
  return (report['findings'] || []).filter((finding: any) => typeof finding === "object" && finding !== null && !Array.isArray(finding) && !_BASELINE_NON_RESIDUE_KINDS.has(finding['kind']) && !finding['probe_failed'] && !finding['ledger_stuck'] && !finding['maintenance_explained']);
}

function _check_baseline_probe_health(report: Record<string, any>): void {
  for (const finding of report['findings'] || []) {
    if (typeof finding !== "object" || finding === null || Array.isArray(finding)) {
      continue;
    }
    if (finding['probe_failed']) {
      throw new CompileEnvironmentPrepareError('device_bed_probe_failed', '设备只读探测失败，床态未知，不能安全进入编译');
    }
    if (finding['kind'] === 'build_anchor') {
      const anchor = finding['detail'] || {};
      if (String(anchor['status'] || '') === 'unknown') {
        throw new CompileEnvironmentPrepareError('device_build_anchor_unknown', '真机或配置 build 无法解析出版本家族；请核对 IST_DEVICE_BUILD 后重跑');
      }
      throw new CompileEnvironmentPrepareError('device_build_family_mismatch', '真机 build 与配置 IST_DEVICE_BUILD 跨 minor 失配；请更新配置后重跑');
    }
  }
}

function _serial_baseline_reset(identity: DeviceReleaseIdentity, actions: string[] | null = null): void {
  logger.warning('设备基线未闭合，启动串口基线重置: host=%s build=%s', identity.host, identity.raw_build);
  const { FrameworkMCPClient } = require("../../case_compiler/device_mcp_client");
  let res: any;
  try {
    const client = new FrameworkMCPClient();
    try {
      if (client.host !== identity.host) {
        throw new CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '串口初始化通道指向的跳板机与当前验证床不一致，已放弃自动重置');
      }
      res = client.init_device({ device_index: 0 });
    } finally {
      if (typeof client.close === "function") {
        client.close();
      }
    }
  } catch (exc) {
    if (exc instanceof CompileEnvironmentPrepareError) {
      throw exc;
    }
    throw new CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '设备串口基线重置通道异常，已失败关闭');
  }
  const data = (typeof res === "object" && res !== null && !Array.isArray(res)) ? res : {};
  let ok = !!Object.keys(data).length && !data['error'];
  let initialized: number, failed: number, total: number;
  try {
    initialized = Math.trunc(Number(data['initialized']) || 0);
    failed = Math.trunc(Number(data['failed']) || 0);
    total = Math.trunc(Number(data['total']) || 0);
  } catch {
    ok = false;
    initialized = 0; failed = 0; total = 0;
  }
  ok = ok && failed === 0 && initialized === total && total > 0;
  if (!ok) {
    if (String(data['error'] || '').includes('IST_LOCALHOST_SSH_PASS')) {
      throw new CompileEnvironmentPrepareError('serial_reset_credentials_missing', '串口基线重置通道缺 IST_LOCALHOST_SSH_PASS；设备本身未被判定有残留');
    }
    throw new CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '设备串口基线重置未成功（含床被其它会话占用），已失败关闭');
  }
  const reprobed = _probe_release_identity();
  if (reprobed.raw_build !== identity.raw_build || reprobed.host !== identity.host) {
    throw new CompileEnvironmentPrepareError('excel_release_baseline_init_failed', '串口基线重置后设备身份与初探不一致，已失败关闭');
  }
  if (actions !== null) {
    actions.push('已通过物理串口重置设备干净基线（清配并还原接口 IP），身份复探一致');
  }
}

function _converge_device_baseline(identity: DeviceReleaseIdentity, actions: string[]): void {
  const { get_config } = require("../../case_compiler/config");
  const bed = require("./bed");
  const { _do_probe } = require("../tools/device/run_case");
  const cfg_build = String(get_config().build || '').trim();
  const _check_once = (): Record<string, any>[] => {
    const report = bed.bed_check((cmd: string) => _do_probe(cmd, { annotate: false }), cfg_build, { root: _PROJECT_ROOT, host: identity.host });
    _check_baseline_probe_health(report);
    return _baseline_residue(report);
  };
  let residue = _check_once();
  if (!residue.length) {
    actions.push('已核对设备床基线（只读体检无残留）');
    return;
  }
  const clean = bed.bed_cleanup((cmd: string) => _do_probe(cmd, { mode: 'config' }), residue, { root: _PROJECT_ROOT, host: identity.host, batch: 'environment-prepare' });
  actions.push(`床体检发现残留，已按文法清理引用执行开工必净（清成 ${(clean['cleaned'] || []).length} 项` + ((clean['failed'] || []).length ? `，失败 ${clean['failed'].length} 项` : '') + ((clean['skipped'] || []).length ? `，无清理引用 ${clean['skipped'].length} 项` : '') + '）');
  residue = _check_once();
  if (!residue.length) {
    actions.push('文法清理后复检床态已干净');
    return;
  }
  logger.warning('文法清理后仍有 %d 项床残留，启动串口基线兜底: host=%s', residue.length, identity.host);
  _serial_baseline_reset(identity, actions);
  residue = _check_once();
  if (residue.length) {
    throw new CompileEnvironmentPrepareError('device_bed_baseline_not_converged', '文法清理与串口基线重置后床残留仍未闭合，需人工检查设备');
  }
  actions.push('串口基线重置后复检床态已干净');
}

function _execute_release_volume(workbook_path: P, identity: DeviceReleaseIdentity): Record<string, any>[] {
  const { execFileSync } = require("node:child_process");
  let completed: { stdout: string; stderr: string };
  try {
    const stdout = execFileSync(process.execPath, ['-e', 'require("scripts.maintenance.run_excel_release_volume")', '--workbook', workbook_path.toString(), '--build', identity.execution_build, '--required-host', identity.host], { cwd: _PROJECT_ROOT.toString(), encoding: 'utf-8', timeout: 2700 * 1000, maxBuffer: 256 * 1024 * 1024 });
    completed = { stdout, stderr: '' };
  } catch (exc: any) {
    if (exc?.status !== 0 && exc?.status !== undefined && exc?.status !== null) {
      throw new CompileEnvironmentPrepareError('excel_release_runner_failed', 'Excel release 隔离上机进程未正常收口');
    }
    completed = { stdout: String(exc?.stdout ?? ''), stderr: String(exc?.stderr ?? '') };
    if (exc?.signal) {
      throw new CompileEnvironmentPrepareError('excel_release_runner_failed', 'Excel release 隔离上机进程未正常收口');
    }
  }
  let result_text = '';
  for (const line of [...completed.stdout.split(/\r?\n/)].reverse()) {
    const stripped = line.trim();
    if (stripped.startsWith('[') || stripped.startsWith('{')) {
      result_text = stripped;
      break;
    }
  }
  let rows: any;
  try {
    rows = JSON.parse(result_text);
  } catch {
    throw new CompileEnvironmentPrepareError('excel_release_run_protocol_error', 'Excel release 上机返回了不可解析的证据');
  }
  if (typeof rows === "object" && rows !== null && !Array.isArray(rows)) {
    throw new CompileEnvironmentPrepareError(_stable_release_failure_code(rows), 'Excel release 整卷上机未完成，未签发 promotion');
  }
  if (!Array.isArray(rows) || rows.length !== 1 || typeof rows[0] !== "object" || rows[0] === null || Array.isArray(rows[0])) {
    throw new CompileEnvironmentPrepareError('excel_release_run_not_pass', 'Excel release 覆盖卷没有形成同床、同 build 的真实 PASS 闭包');
  }
  return rows;
}

function _run_release_and_promote(candidate: any, identity: DeviceReleaseIdentity, evidence: DeploymentEvidence, actions: string[] | null = null): any {
  const { build_capability_sample_artifacts } = require("../../case_compiler/excel_capability_samples");
  const { select_promoted_runtime_template } = require("../../case_compiler/excel_release");
  const emit_excel_release_evidence = require("../../scripts/maintenance/emit_excel_release_evidence");
  const release_id = _new_release_id(candidate);
  const output_dir = _WORKSPACE_OUTPUTS.joinpath('excel_environment', release_id);
  fs.mkdirSync(output_dir.toString(), { recursive: false, mode: 0o700 });
  const workbook_path = output_dir.joinpath('excel_capability_samples.xlsx');
  const manifest_path = output_dir.joinpath('excel_capability_samples.manifest.json');
  build_capability_sample_artifacts({ contract_path: candidate.paths.contract, template_path: candidate.paths.runtime_template, workbook_path, manifest_path, autoid: '990000000000000001', trusted_runtime_root: _WORKSPACE_OUTPUTS, device_build: identity.raw_build });
  let rows = _execute_release_volume(workbook_path, identity);
  if (!_release_row_matches_identity(rows[0], identity)) {
    logger.warning('Excel release 覆盖卷首轮未形成 PASS 闭包，启动串口基线自愈: host=%s build=%s', identity.host, identity.raw_build);
    _serial_baseline_reset(identity, actions);
    rows = _execute_release_volume(workbook_path, identity);
    if (!_release_row_matches_identity(rows[0], identity)) {
      throw new CompileEnvironmentPrepareError('excel_release_run_not_pass', 'Excel release 覆盖卷经串口基线重置重试后仍没有形成同床、同 build 的真实 PASS 闭包');
    }
    if (actions !== null) {
      actions.push('设备首次验证未闭合，已自动通过串口重置干净基线并重新验证签发 promotion');
    }
  }
  const last_run = output_dir.joinpath('last_run.json');
  atomic_write_bytes_nofollow(last_run.toString(), Buffer.from(pyJsonDumps(rows, { ensure_ascii: false, indent: 1, sort_keys: true }) + '\n', 'utf-8'), { errorType: CompileEnvironmentPrepareErrorAsError, invalid_message: 'release run evidence path is invalid', unavailable_message: 'release run evidence could not be stored', mode: 0o600 });
  const argv = ['--evidence-dir', output_dir.toString(), '--run-evidence', last_run.toString(), '--deployment-receipt', evidence.receipt_path.toString(), '--backup-manifest', evidence.backup_manifest_path.toString(), '--release-id', release_id, '--jumphost-host', identity.host];
  let result: any;
  try {
    result = emit_excel_release_evidence.main(argv);
  } catch (exc: any) {
    if (exc?.name === 'SystemExit' || exc?.code === 'EXIT') {
      throw new CompileEnvironmentPrepareError('excel_release_signing_failed', 'Excel release 证据签发器拒绝了本次闭包');
    }
    throw exc;
  }
  if (result !== 0) {
    throw new CompileEnvironmentPrepareError('excel_release_signing_failed', 'Excel release 证据签发器未成功收口');
  }
  _activate_canonical_promotion_receipt();
  const selected = select_promoted_runtime_template();
  if (!_selection_matches_identity(selected, identity)) {
    throw new CompileEnvironmentPrepareError('excel_release_identity_drifted', '新签发的 promotion 与当前设备/跳板机身份不一致');
  }
  return selected;
}

function _publish_bundle(candidate: any, identity: DeviceReleaseIdentity, opts: { known_hosts: P }): void {
  const { build_release_bundle, publish_remote_release_bundle } = require("../../case_compiler/excel_release_bundle");
  const raw = build_release_bundle(_promotion_receipt_path());
  publish_remote_release_bundle(raw, { candidate, device_build: identity.execution_build, environment: identity.environment, known_hosts: opts.known_hosts });
}

function _try_restore_bundle(candidate: any, identity: DeviceReleaseIdentity, opts: { known_hosts: P }): any | null {
  const { fetch_remote_release_bundle, install_release_bundle } = require("../../case_compiler/excel_release_bundle");
  const raw = fetch_remote_release_bundle({ candidate, device_build: identity.execution_build, known_hosts: opts.known_hosts });
  if (raw === null || raw === undefined) {
    return null;
  }
  install_release_bundle(raw, { device_build: identity.execution_build, environment: identity.environment });
  _activate_canonical_promotion_receipt();
  const { select_promoted_runtime_template } = require("../../case_compiler/excel_release");
  return select_promoted_runtime_template();
}

function _ensure_compile_environment_locked(opts: { product_version?: string; local_xml_path?: string; local_xml_sha256?: string }): PreparationResult {
  const product_version = opts.product_version ?? '';
  const local_xml_path = opts.local_xml_path ?? '';
  const local_xml_sha256 = opts.local_xml_sha256 ?? '';
  const excel_release = require("../../case_compiler/excel_release");
  let actions = _PREPARATION_ACTIONS;
  if (actions === null) {
    actions = [];
  }
  const known_hosts = new P(require("node:os").homedir()).joinpath('.ssh', 'known_hosts');
  _load_local_configuration();
  actions.push('已启动 product/QA 知识桶同步');
  const markdown_sync = _sync_markdown_knowledge_buckets();
  actions.push(`已同步 product/QA 知识桶并隔离台账外或远端删除的旧件（更新 ${Object.values(markdown_sync).reduce((acc, row) => acc + (Math.trunc(Number(row['synced']) || 0)), 0)} 件）`);
  actions.push('已启动框架镜像同步与派生投影收敛');
  const sync_result = _sync_framework({ defer_projection_failure: true });
  actions.push(`已对账跳板机框架镜像（更新 ${Math.trunc(Number(sync_result['pulled']) || 0)} 个文件；旧卷处置 ${Math.trunc(Number(sync_result['verified_corpus_events']) || 0)} 件）`);
  const topology_action = String(sync_result['topology_action'] || '');
  if (topology_action) {
    actions.push(topology_action);
  }
  let deferred_projection_error: any = sync_result['projection_error'] ?? null;
  const [runtime_drifted, drift_detail] = _jumphost_runtime_drifted();
  let candidate: any;
  let deployed: DeploymentEvidence | null = null;
  try {
    if (runtime_drifted) {
      throw new excel_release.ExcelReleaseError(drift_detail);
    }
    candidate = excel_release.validate_candidate_artifact_set();
  } catch (exc) {
    if (!(exc instanceof excel_release.ExcelReleaseError)) throw exc;
    deployed = _deploy_candidate({ known_hosts });
    actions.push(runtime_drifted ? `跳板机自动化环境已按本仓目标更新并事务部署（${drift_detail}）` : '候选 Excel runtime 已经密封备份并事务部署');
    _sync_framework();
    if (deferred_projection_error !== null) {
      actions.push('部署后投影已按跳板机上的新框架重生');
    }
    deferred_projection_error = null;
    try {
      candidate = excel_release.validate_candidate_artifact_set();
    } catch (inner: any) {
      if (inner instanceof excel_release.ExcelReleaseError) {
        throw new CompileEnvironmentPrepareError('candidate_identity_not_converged', '事务部署后本地镜像仍不能验证 Excel 候选四件套');
      }
      throw inner;
    }
  }
  if (deferred_projection_error !== null) {
    throw new CompileEnvironmentPrepareError('framework_projection_not_converged', '框架派生投影重生失败，且候选 Excel runtime 无需部署——没有可自动执行的修法');
  }
  const identity = _probe_release_identity();
  actions.push('已核对当前设备 build 身份');
  _converge_device_command_tree(identity, { product_version, local_xml_path, local_xml_sha256 });
  actions.push('已按真机 build 收敛密封命令树投影');
  _converge_device_baseline(identity, actions);
  let redeploy_reason = '';
  let remote_receipt: P | null;
  try {
    remote_receipt = _attest_current_remote_deployment(candidate, { known_hosts });
  } catch (exc: any) {
    if (exc instanceof CompileEnvironmentPrepareError && _REDEPLOYABLE_REMOTE_ATTESTATION_CODES.has(exc.code)) {
      remote_receipt = null;
      redeploy_reason = exc.code;
    } else {
      throw exc;
    }
  }
  if (remote_receipt === null && deployed === null) {
    deployed = _deploy_candidate({ known_hosts });
    actions.push(redeploy_reason ? '远端部署身份与当前候选不一致，已自动重建密封事务收据' : '远端缺少可验证事务收据，已自动补做密封事务部署');
    _sync_framework();
    try {
      candidate = excel_release.validate_candidate_artifact_set();
    } catch (inner: any) {
      if (inner instanceof excel_release.ExcelReleaseError) {
        throw new CompileEnvironmentPrepareError('candidate_identity_not_converged', '远端事务部署后本地镜像仍不能验证 Excel 候选四件套');
      }
      throw inner;
    }
    remote_receipt = _attest_current_remote_deployment(candidate, { known_hosts });
    if (remote_receipt === null) {
      throw new CompileEnvironmentPrepareError('remote_deployment_receipt_missing', '自动事务部署后仍没有可验证的 committed 部署收据');
    }
  } else if (remote_receipt === null) {
    remote_receipt = deployed!.receipt_path;
  } else {
    actions.push('已从远端 committed 事务恢复 deployment receipt');
  }
  let selection: any = null;
  try {
    selection = excel_release.select_promoted_runtime_template();
  } catch (exc: any) {
    if (!(exc instanceof excel_release.ExcelReleaseError) && exc?.code !== 'ENOENT') {
      throw exc;
    }
    selection = null;
  }
  if (selection !== null && _selection_matches_identity(selection, identity)) {
    actions.push('已复用同候选、同跳板机、同 build 的本地 promotion');
    try {
      _publish_bundle(candidate, identity, { known_hosts });
    } catch {
      actions.push('可迁移证据缓存回写失败，下次将自动重试');
    }
    return new PreparationResult(true, 'promotion_reused', [...actions], { device_identity: identity });
  }
  if (selection !== null) {
    actions.push('本地 promotion 与当前环境身份不一致，已拒绝复用');
  }
  const restored = _try_restore_bundle(candidate, identity, { known_hosts });
  if (restored !== null) {
    if (!_selection_matches_identity(restored, identity)) {
      throw new CompileEnvironmentPrepareError('portable_promotion_identity_mismatch', '迁移后 promotion 未与当前环境身份闭合');
    }
    actions.push('已从跳板机内容寻址库迁移已认证 promotion，未重复上机');
    return new PreparationResult(true, 'promotion_restored', [...actions], { device_identity: identity });
  }
  let deployment: DeploymentEvidence;
  if (deployed === null) {
    const backup_manifest = _backup_current_contract({ known_hosts });
    deployment = new DeploymentEvidence({ receipt_path: remote_receipt!, backup_manifest_path: backup_manifest, source: 'recovered' });
  } else {
    deployment = new DeploymentEvidence({ receipt_path: remote_receipt!, backup_manifest_path: deployed.backup_manifest_path, source: deployed.source });
  }
  _run_release_and_promote(candidate, identity, deployment, actions);
  actions.push('未找到同身份可迁移证据；已自动完成一次 release 整卷上机与 promotion 签发');
  _publish_bundle(candidate, identity, { known_hosts });
  actions.push('已把完整 promotion 闭包回存跳板机，其它本地环境可直接迁移');
  const final = excel_release.select_promoted_runtime_template();
  if (!_selection_matches_identity(final, identity)) {
    throw new CompileEnvironmentPrepareError('final_promotion_validation_failed', '自动收敛结束后 production 模板仍未与当前环境身份闭合');
  }
  return new PreparationResult(true, 'promotion_created', [...actions], { device_identity: identity });
}

export function ensure_compile_environment(opts: { product_version?: string; local_xml_path?: string; local_xml_sha256?: string } = {}): PreparationResult {
  const product_version = opts.product_version ?? '';
  const local_xml_path = opts.local_xml_path ?? '';
  const local_xml_sha256 = opts.local_xml_sha256 ?? '';
  const actions: string[] = [];
  const prev = _PREPARATION_ACTIONS;
  _PREPARATION_ACTIONS = actions;
  try {
    const lock = acquireLockSync(_LOCK_PATH.toString());
    try {
      return _ensure_compile_environment_locked({ product_version, local_xml_path, local_xml_sha256 });
    } finally {
      lock.release();
    }
  } catch (exc: any) {
    if (exc instanceof CompileEnvironmentPrepareError) {
      return new PreparationResult(false, 'failed', [...actions], { error_code: exc.code, error_reason: exc.user_reason });
    }
    const { QueryUnavailable } = require("../../case_compiler/apv_lang");
    const { ExcelContractError } = require("../../case_compiler/excel_contract");
    const { CommandTreeSyncError } = require("../../sync/command_tree_sync");
    const { BackupError } = require("../../scripts/maintenance/backup_jumphost_framework");
    const { PatchError } = require("../../scripts/maintenance/patch_jumphost_excel_runtime");
    if (exc instanceof ExcelContractError) {
      return new PreparationResult(false, 'failed', [...actions], { error_code: 'excel_contract_source_drift', error_reason: _contract_drift_reason() });
    }
    if (exc instanceof QueryUnavailable) {
      return new PreparationResult(false, 'failed', [...actions], { error_code: 'framework_mirror_incomplete', error_reason: String(exc?.message ?? exc) || 'framework mirror 残缺，公开投影无法重生' });
    }
    if (exc instanceof CommandTreeSyncError) {
      logger.error('命令树同步失败: %s', exc);
      return new PreparationResult(false, 'failed', [...actions], { error_code: 'device_command_tree_sync_failed', error_reason: String(exc?.message ?? exc) || '真机命令树同步失败' });
    }
    if (exc instanceof PatchError) {
      return new PreparationResult(false, 'failed', [...actions], { error_code: 'excel_runtime_patch_failed', error_reason: String(exc?.message ?? exc) || '跳板机 Excel 运行时补丁失败' });
    }
    if (exc instanceof BackupError) {
      return new PreparationResult(false, 'failed', [...actions], { error_code: 'jumphost_backup_failed', error_reason: String(exc?.message ?? exc) || '跳板机密封备份失败' });
    }
    return new PreparationResult(false, 'failed', [...actions], { error_code: `environment_prepare_${exc?.constructor?.name ?? 'Error'}`, error_reason: '自动环境收敛发生未分类错误，已失败关闭' });
  } finally {
    _PREPARATION_ACTIONS = prev;
  }
}
