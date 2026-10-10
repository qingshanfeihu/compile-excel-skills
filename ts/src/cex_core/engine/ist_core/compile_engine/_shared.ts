// 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/_shared.py（sha256 0527fcd83855b091）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";

import { _cex_data_path } from "../../_root";
import {
  P,
  PyAssertionError,
  PyValueError,
  PyRuntimeError,
  pyJsonDumps,
  FileNotFoundError,
  IsADirectoryError,
} from "../../_py";
import { acquireLockSync } from "../../../../platform/index";
import { accepts_schema } from "../../common/schema_identity";
import * as EE from "./engine_errors";
import * as F from "./facts";
import * as V from "./views";

function sha256Hex(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function sha1Hex(data: string | Buffer): string {
  return crypto.createHash("sha1").update(data).digest("hex");
}

const logger = {
  warning: (..._args: any[]) => {},
  debug: (..._args: any[]) => {},
};

let _ENGINE_NODE_CONTEXT: [Record<string, any>, string] | null = null;

export function engine_node_context<T>(state: Record<string, any>, node: string, fn: () => T): T {
  const prev = _ENGINE_NODE_CONTEXT;
  _ENGINE_NODE_CONTEXT = [state, node];
  try {
    return fn();
  } finally {
    _ENGINE_NODE_CONTEXT = prev;
  }
}

export function current_engine_node_context(): [Record<string, any>, string] | null {
  return _ENGINE_NODE_CONTEXT;
}

export function require_current_compile_context(state: Record<string, any>): void {
  if (!state['compile_context_sha256']) {
    return;
  }
  const { _assert_compile_context_current } = require("./engine_tool");
  _assert_compile_context_current({
    project_root: project_root(),
    outputs_root: outputs_root(),
    out_name: String(state['out_name'] || ''),
    mindmap_path: String(state['mindmap_path'] || ''),
    product_version: String(state['product_version'] || ''),
    local_xml_ref: String(state['local_command_tree_xml'] || ''),
    expected_local_xml_sha256: String(state['local_command_tree_xml_sha256'] || ''),
  });
}

const _AID_LEASES: Map<string, Map<string, any>> = new Map();

export function acquire_aid_leases(out_name: string, aids: any): string[] {
  let held = _AID_LEASES.get(String(out_name));
  if (!held) {
    held = new Map();
    _AID_LEASES.set(String(out_name), held);
  }
  const conflicts: string[] = [];
  const lock_dir = project_root().joinpath('runtime', 'locks');
  try {
    fs.mkdirSync(lock_dir.toString(), { recursive: true });
  } catch {
    logger.warning('aid 租约目录不可用——本批在无 aid 级互斥下运行');
    return [];
  }
  for (const raw of aids) {
    let aid: string;
    try {
      aid = safe_output_component(String(raw), { field: 'autoid' });
    } catch (e) {
      if (e instanceof PyValueError) {
        logger.warning('跳过不安全的租约 autoid:%r', raw);
        continue;
      }
      throw e;
    }
    if (held.has(aid)) {
      continue;
    }
    let holder = '';
    for (const [n, m] of _AID_LEASES) {
      if (n !== String(out_name) && m.has(aid)) {
        holder = n;
        break;
      }
    }
    if (holder) {
      conflicts.push(`${aid}(本进程批 '${holder}' 持有)`);
      continue;
    }
    const lockPath = lock_dir.joinpath(`compile_aid_${aid}.lock`).toString();
    let lock: any = null;
    try {
      lock = acquireLockSync(lockPath, 0);
    } catch (exc: any) {
      const code = String(exc?.code || '');
      if (code === 'EWOULDBLOCK' || code === 'EAGAIN' || code === 'EACCES' || code === 'EPERM' || code === 'EBUSY') {
        conflicts.push(`${aid}(另一活进程持有)`);
      } else {
        logger.warning('aid 租约 flock 不可用(%s)——该 aid 无互斥', aid);
      }
      continue;
    }
    held.set(aid, lock);
  }
  if (conflicts.length) {
    release_aid_leases(out_name);
  }
  return conflicts;
}

export function release_aid_leases(out_name: string): void {
  const held = _AID_LEASES.get(String(out_name));
  _AID_LEASES.delete(String(out_name));
  if (!held) {
    return;
  }
  for (const lock of held.values()) {
    try {
      if (lock && typeof lock.release === "function") {
        lock.release();
      } else if (lock && typeof lock.close === "function") {
        lock.close();
      }
    } catch {}
  }
}

export function aid_leased_by(out_name: string, aid: string): boolean | null {
  const held = _AID_LEASES.get(String(out_name));
  if (!held || held.size === 0) {
    return null;
  }
  return held.has(String(aid));
}

export const PANEL_QID_PREFIX = 'panel:';

export const SUSPEND_KIND_REGISTRY: Record<string, Record<string, boolean>> = { 'panel': { 'renders_as_no_answer': true, 'resume_reopenable': true }, 'cap': { 'renders_as_no_answer': true, 'resume_reopenable': true }, 'contra': { 'renders_as_no_answer': true, 'resume_reopenable': true }, 'nd': { 'renders_as_no_answer': true, 'resume_reopenable': true }, 'env': { 'renders_as_no_answer': true, 'resume_reopenable': false }, 'bed': { 'renders_as_no_answer': false, 'resume_reopenable': false }, 'resume': { 'renders_as_no_answer': false, 'resume_reopenable': false }, 'bed_gate': { 'renders_as_no_answer': false, 'resume_reopenable': false }, 'bedclosure': { 'renders_as_no_answer': false, 'resume_reopenable': false }, 'execution_pause': { 'renders_as_no_answer': false, 'resume_reopenable': true } };

export function suspend_kind_renders_as_no_answer(kind: string): boolean {
  return !!((SUSPEND_KIND_REGISTRY[kind] || {})['renders_as_no_answer']);
}

export function suspend_kind_resume_reopenable(kind: string): boolean {
  return !!((SUSPEND_KIND_REGISTRY[kind] || {})['resume_reopenable']);
}

const _USER_DECISION_REOPEN_KINDS: Set<string> = new Set(['改描述', 'suspend']);
const _USER_DECISION_KIND_ALIASES: Record<string, string> = { '挂起': 'suspend' };

export function classify_suspend_reason(reason: string | Record<string, any>): [string, string] {
  if (reason !== null && typeof reason === "object" && !Array.isArray(reason)) {
    let kind = String(reason['suspension_kind'] || '');
    if (!kind && String(reason['pause_kind'] || '').trim()) {
      kind = 'execution_pause';
    }
    if (kind) {
      if (!(kind in SUSPEND_KIND_REGISTRY)) {
        return ['unknown', kind];
      }
      return [suspend_kind_resume_reopenable(kind) ? 'reopen' : 'no_reopen', kind];
    }
    reason = String(reason['reason'] || '');
  }
  reason = String(reason || '');
  if (!reason) {
    return ['no_reopen', ''];
  }
  if (reason.startsWith('auto:')) {
    const kind = reason.slice('auto:'.length).split(':', 2)[0];
    if (!(kind in SUSPEND_KIND_REGISTRY)) {
      return ['unknown', kind];
    }
    return [suspend_kind_resume_reopenable(kind) ? 'reopen' : 'no_reopen', kind];
  }
  if (reason.startsWith('keep:')) {
    return ['no_reopen', 'keep'];
  }
  if (reason.startsWith('user_decision:')) {
    let kind = reason.slice('user_decision:'.length).split(':', 2)[0];
    kind = _USER_DECISION_KIND_ALIASES[kind] ?? kind;
    if (!_USER_DECISION_REOPEN_KINDS.has(kind)) {
      return ['unknown', kind];
    }
    return ['reopen', kind];
  }
  return ['unknown', ''];
}

export function suspend_reason_embedded_qid(reason: string): string {
  reason = String(reason || '');
  const prefix = 'user_decision:suspend:';
  if (!reason.startsWith(prefix)) {
    return '';
  }
  return reason.slice(prefix.length);
}

export function require_suspend_kind_known(reason: string | Record<string, any>): void {
  const [disposition, kind] = classify_suspend_reason(reason);
  if (disposition === 'unknown') {
    throw new PyAssertionError(`suspended.reason=${JSON.stringify(reason)} 解析出的 kind=${JSON.stringify(kind)} 不在 内部工单 登记的闭集内——新 kind 请先在 _shared.py 的 SUSPEND_KIND_REGISTRY / _USER_DECISION_REOPEN_KINDS 登记,再落地这个写点`);
  }
}

export function project_root(): P {
  return new P(_cex_data_path(''));
}

export function outputs_root(): P {
  const _kp = require("../../knowledge_paths");
  return _kp.scoped_bucket_root('outputs', { project_root: project_root() });
}

export function inputs_root(): P {
  const _kp = require("../../knowledge_paths");
  return _kp.scoped_bucket_root('inputs', { project_root: project_root() });
}

export function compile_tenant_token(): string {
  const { multi_tenant, output_scope } = require("../../knowledge_paths");
  if (!multi_tenant()) {
    return '';
  }
  return output_scope();
}

export function compile_lock_filename(name: string): string {
  return `compile_run_${compile_batch_registry_key(name)}.lock`;
}

export function compile_batch_registry_key(name: string): string {
  const tenant = compile_tenant_token();
  return tenant ? `${tenant}:${name}` : name;
}

export function safe_output_component(value: string, opts: { field?: string } = {}): string {
  const field = opts.field ?? 'out_name';
  const name = String(value || '').trim();
  if (!name || name === '.' || name === '..' || new P(name).is_absolute() || name.includes('/') || name.includes('\\') || name.includes('~') || [...name].some((ch) => ch.codePointAt(0)! < 32) || name.length > 180) {
    throw new PyValueError(`${field} must be one safe directory name under workspace/outputs`);
  }
  const root = outputs_root();
  const candidate = root.joinpath(name);
  if (candidate.is_symlink()) {
    throw new PyValueError(`${field} resolves through a symbolic-link directory`);
  }
  try {
    candidate.resolve().relative_to(root.resolve());
  } catch (exc) {
    throw new PyValueError(`${field} escapes workspace/outputs`);
  }
  return name;
}

export function facts_path(state: Record<string, any>): P {
  const name = safe_output_component(String(state['out_name'] || 'engine'), { field: 'out_name' });
  const ref = String(state['facts_ref'] || '');
  if (ref) {
    const candidate = project_root().joinpath(ref);
    const expected_parent = outputs_root().joinpath(name);
    let resolved: P;
    try {
      if (candidate.is_symlink()) {
        throw new PyValueError('facts_ref must not be a symbolic link');
      }
      resolved = candidate.resolve();
      resolved.relative_to(expected_parent.resolve());
    } catch (exc) {
      if (exc instanceof PyValueError && String(exc.message).includes('facts_ref must not')) {
        throw exc;
      }
      throw new PyValueError('facts_ref must stay inside the bound output batch');
    }
    if (!resolved.parent.eq(expected_parent.resolve()) || resolved.name !== 'facts.jsonl') {
      throw new PyValueError('facts_ref must identify the bound batch facts.jsonl');
    }
    return candidate;
  }
  return outputs_root().joinpath(name, 'facts.jsonl');
}

export function load_facts(state: Record<string, any>): Record<string, any>[] {
  return F.load_facts(facts_path(state));
}

export function require_decision_identity(new_facts: Record<string, any>[]): void {
  for (let index = 0; index < new_facts.length; index++) {
    const fact = new_facts[index];
    if (String(fact['ev'] || '') !== 'decision') {
      continue;
    }
    if (String(fact['token'] || '').trim()) {
      continue;
    }
    if (fact['freeform'] === true) {
      continue;
    }
    throw new PyValueError(`decision fact requires a non-empty token or freeform=true (index=${index}, question_id=${JSON.stringify(fact['question_id'] ?? '')})`);
  }
}

export function append(state: Record<string, any>, new_facts: Record<string, any>[]): number {
  const { transition_lock } = require("./engine_quarantine");
  return transition_lock(facts_path(state), () => _append_with_admission(state, new_facts));
}

export function _append_with_admission(state: Record<string, any>, new_facts: Record<string, any>[]): number {
  const { scrub_value } = require("../security_scrub");
  require_decision_identity(new_facts);
  const safe_facts: Record<string, any>[] = scrub_value(new_facts, { scrub_paths: false });
  const EC = require("./engine_checkpoints");
  const EQ = require("./engine_quarantine");
  const existing = load_facts(state);
  const accepted: Record<string, any>[] = [];
  for (const fact of safe_facts) {
    if (fact['ev'] === EQ.RELEASE_EVENT) {
      EQ.validate_release_at_write(project_root(), fact, existing.concat(accepted));
    }
    if (fact['ev'] === 'engine_condition_disclosure') {
      EC.validate_condition_disclosure(fact);
      accepted.push(fact);
      if (fact['scope'] === 'batch') {
        const TC = require("./terminal_credentials");
        accepted.push({ 'ev': 'batch_execution_paused', 'aid': '', 'diagnostic_id': fact['diagnostic_id'], 'source_fact_sha256': TC._fact_sha256(fact), 'reason': 'a required batch condition is unavailable; responsibility is unverified', 'revoked_dispatch_ids': [...new Set<string>(F.this_run_slice(existing.concat(accepted)).filter((row: any) => row['ev'] === 'worker_dispatch_started' && row['dispatch_id']).map((row: any) => String(row['dispatch_id'])))].sort() });
      } else if (fact['aid']) {
        const aid = String(fact['aid']);
        const mine = existing.concat(accepted).filter((row: any) => row['aid'] === aid);
        const explicit_pause = safe_facts.some((row: any) => row['ev'] === 'suspended' && row['aid'] === aid && row['suspension_kind'] === 'execution_pause');
        if (!explicit_pause && !V.active_execution_pause(mine)) {
          const { _fact_sha256 } = require("./terminal_credentials");
          accepted.push({ 'ev': 'de_escalated', 'aid': aid, 'note': 'auto: preserve the observed condition and pause this invocation' }, { 'ev': 'suspended', 'aid': aid, 'source': 'engine_auto', 'suspension_kind': 'execution_pause', 'pause_kind': 'engine_condition', 'question_id': 'condition-pause:' + fact['diagnostic_id'], 'reason': '已记录当前条件或校验异常，本轮暂挂；责任方尚未确认。', 'source_event': fact['ev'], 'source_fact_sha256': _fact_sha256(fact), 'basis_status': 'source_bound', 'resume_stage': 'author' });
        }
      }
      continue;
    }
    const { uses_new_policy } = require("./authoring_evidence");
    let unverified_authoring = false;
    if (fact['ev'] === 'authoring_failure' && uses_new_policy(existing.concat(accepted))) {
      const TC = require("./terminal_credentials");
      try {
        const issued = TC.build_verified_authoring_failure_fact({ aid: String(fact['aid'] || ''), facts: existing.concat(accepted) });
        unverified_authoring = JSON.stringify(issued) !== JSON.stringify(Object.fromEntries(Object.entries(fact).filter(([k]) => !k.startsWith('_'))));
      } catch (e) {
        if (e instanceof PyValueError || e instanceof Error) {
          unverified_authoring = true;
        } else {
          throw e;
        }
      }
    }
    if (uses_new_policy(existing.concat(accepted)) && ((fact['ev'] === 'attribution' && fact['disposition'] === 'engineering_fault') || unverified_authoring)) {
      accepted.push({ 'ev': 'unconfirmed_terminal_claim', 'aid': fact['aid'] || '', 'original_record': fact, 'reason': 'the legacy terminal label has no current proof' });
      const aid = String(fact['aid'] || '');
      if (aid) {
        const { incomplete_evidence_terminal } = require("./authoring_evidence");
        const terminal = incomplete_evidence_terminal(existing.concat(accepted), { aid, source: accepted[accepted.length - 1], round_no: F.effective_rounds_used(existing.concat(accepted), aid) });
        if (terminal !== null && terminal !== undefined) {
          accepted.push(terminal);
        }
      }
      continue;
    }
    const _FC_BOOK = require("./forced_closure");
    if (EQ.INVALIDATABLE_EVENTS.has ? EQ.INVALIDATABLE_EVENTS.has(fact['ev']) : (EQ.INVALIDATABLE_EVENTS as any).includes?.(fact['ev'])) {
      if (String(fact['aid'] || '') && !_FC_BOOK.is_closing_bookkeeping(fact)) {
        try {
          EQ.require_admission(existing.concat(accepted), { aid: String(fact['aid']), dispatch_id: String(fact['dispatch_id'] || ''), batch_run_id: String(fact['batch_run_id'] || ''), dispatch_event: F.EXECUTION_DISPATCH_EVENTS[String(fact['ctx'] || '')] ?? 'worker_dispatch_started' });
        } catch (exc) {
          if (!(exc instanceof PyValueError)) {
            throw exc;
          }
          accepted.push({ 'ev': 'quarantined_result', 'aid': fact['aid'], 'original_event': fact['ev'], 'original_record': fact, 'reason': String(exc.message), 'admission_status': 'denied' });
          const aid = String(fact['aid']);
          const mine = existing.concat(accepted).filter((row: any) => row['aid'] === aid);
          if (!EQ.batch_halted(existing.concat(accepted)) && !EQ.quarantined_aids(existing.concat(accepted)).has(aid) && !V.active_execution_pause(mine)) {
            const { _fact_sha256 } = require("./terminal_credentials");
            const rejected = accepted[accepted.length - 1];
            accepted.push({ 'ev': 'de_escalated', 'aid': aid, 'note': 'auto: preserve the result and pause on an unverified dispatch identity' }, { 'ev': 'suspended', 'aid': aid, 'source': 'engine_auto', 'suspension_kind': 'execution_pause', 'pause_kind': 'engine_condition', 'source_event': rejected['ev'], 'source_fact_sha256': _fact_sha256(rejected), 'question_id': 'result-identity:' + _fact_sha256(rejected), 'basis_status': 'source_bound', 'resume_stage': 'run', 'reason': '结果身份未通过本轮准入核验，保留原件并暂挂；责任方未确认。' });
          }
          continue;
        }
      }
    }
    accepted.push(fact);
    if (fact['schema'] === EC.SCHEMA && fact['ev'] === 'engine_error') {
      EC.validate_error(fact);
      const population = (manifest(state)['cases'] || []).map((c: any) => String(c['autoid'] || ''));
      accepted.push(...EQ.quarantine_facts(fact, existing.concat(accepted), { population }));
      if (fact['owner'] === 'api' && fact['scope'] === 'batch') {
        accepted.push({ 'ev': 'batch_execution_paused', 'aid': '', 'pause_kind': 'api', 'error_id': fact['error_id'], 'source_record_sha256': fact['record_sha256'], 'reason': 'The recorded API response paused batch execution; no engine defect was confirmed.', 'revoked_dispatch_ids': [...new Set<string>(F.this_run_slice(existing.concat(accepted)).filter((row: any) => row['ev'] === 'worker_dispatch_started' && row['dispatch_id']).map((row: any) => String(row['dispatch_id'])))].sort() });
      }
    }
  }
  const recorded_disclosures = new Set(existing.concat(accepted).filter((row: any) => row['ev'] === EE.UNVERIFIABLE_ERROR_EVENT).map((row: any) => row['diagnostic_id']));
  for (const row of EE.unverifiable_error_disclosures(existing.concat(accepted))) {
    if (!recorded_disclosures.has(row['diagnostic_id'])) {
      accepted.push(row);
      recorded_disclosures.add(row['diagnostic_id']);
    }
  }
  const count = F.append_facts(facts_path(state), accepted);
  if (accepted.some((f) => f['ev'] === EQ.QUARANTINE_EVENT || f['ev'] === 'engine_halt' || f['ev'] === 'batch_execution_paused')) {
    const { revoke_worker_dispatch } = require("../worker_device_context");
    for (const f of accepted) {
      for (const dispatch_id of (f['revoked_dispatch_ids'] || [])) {
        revoke_worker_dispatch(dispatch_id);
      }
    }
  }
  for (const fact of accepted) {
    if (fact['schema'] !== EC.SCHEMA || fact['ev'] !== 'engine_error' || fact['owner'] !== 'engine') {
      continue;
    }
    const followups: Record<string, any>[] = [];
    try {
      const { record_error } = require("./engine_debt");
      record_error(project_root(), fact);
    } catch (exc: any) {
      followups.push({ 'ev': 'engine_debt_index_unavailable', 'error_id': fact['error_id'], 'error': exc?.constructor?.name ?? 'Error' });
    }
    try {
      const { capture_incident } = require("./engine_incidents");
      followups.push(capture_incident(state, fact, load_facts(state)));
    } catch (exc: any) {
      followups.push({ 'ev': 'engine_incident_capture', 'error_id': fact['error_id'], 'status': 'incomplete', 'error': exc?.constructor?.name ?? 'Error' });
    }
    if (followups.length) {
      F.append_facts(facts_path(state), scrub_value(followups, { scrub_paths: false }));
    }
  }
  return count;
}

export class ManifestUnavailable extends PyRuntimeError {
  path: string;
  detail: string;
  constructor(path: string, detail: string) {
    super(`${path}: ${detail}`);
    this.path = String(path);
    this.detail = String(detail);
  }
}

export function is_bound_manifest_error(state: Record<string, any>, exc: any): boolean {
  if (!(exc instanceof ManifestUnavailable) && !(exc instanceof LedgerCorruptError)) {
    return false;
  }
  const source = String(exc?.path || '');
  if (!source) {
    return false;
  }
  try {
    const name = safe_output_component(String(state['out_name'] || 'engine'), { field: 'out_name' });
    const expected = outputs_root().joinpath(name, 'manifest.json').resolve();
    let candidate = new P(source);
    if (!candidate.is_absolute()) {
      candidate = project_root().joinpath(candidate.toString());
    }
    return candidate.resolve().eq(expected);
  } catch {
    return false;
  }
}

export function manifest(state: Record<string, any>): Record<string, any> {
  const name = safe_output_component(String(state['out_name'] || 'engine'), { field: 'out_name' });
  const expected = outputs_root().joinpath(name, 'manifest.json');
  const ref = String(state['manifest_ref'] || '');
  const candidate = ref ? project_root().joinpath(ref) : expected;
  try {
    if (candidate.is_symlink()) {
      throw new PyValueError('manifest_ref must not be a symbolic link');
    }
    const resolved = candidate.resolve();
    if (!resolved.eq(expected.resolve())) {
      throw new PyValueError('manifest_ref must identify the bound batch manifest.json');
    }
  } catch (exc) {
    if (exc instanceof PyValueError && String(exc.message).includes('manifest_ref')) {
      throw exc;
    }
    throw new PyValueError('manifest_ref must stay inside the bound output batch');
  }
  const payload = read_json_checked(candidate, null);
  if (payload === null || payload === undefined) {
    throw new ManifestUnavailable(candidate.toString(), 'bound batch manifest.json is missing');
  }
  if (typeof payload !== "object" || Array.isArray(payload)) {
    throw new LedgerCorruptError(candidate.toString(), 'manifest must be a JSON object');
  }
  const cases = payload['cases'];
  if (!Array.isArray(cases)) {
    throw new LedgerCorruptError(candidate.toString(), 'manifest.cases must be an array');
  }
  if (!cases.length) {
    throw new ManifestUnavailable(candidate.toString(), 'bound batch manifest contains no cases');
  }
  const seen: Set<string> = new Set();
  for (let index = 0; index < cases.length; index++) {
    const case_ = cases[index];
    if (typeof case_ !== "object" || case_ === null || Array.isArray(case_)) {
      throw new LedgerCorruptError(candidate.toString(), `manifest.cases[${index}] must be an object`);
    }
    const aid = String(case_['autoid'] || '');
    try {
      safe_output_component(aid, { field: 'autoid' });
    } catch (exc) {
      throw new LedgerCorruptError(candidate.toString(), `manifest.cases[${index}].autoid is not a safe path component`);
    }
    if (seen.has(aid)) {
      throw new LedgerCorruptError(candidate.toString(), `duplicate manifest autoid: ${aid}`);
    }
    seen.add(aid);
  }
  return payload;
}

function _live_capability_projection_sha256(sync_fact: Record<string, any> | null): string {
  if (typeof sync_fact !== "object" || sync_fact === null || Array.isArray(sync_fact)) {
    return '';
  }
  const product = String(sync_fact['product'] || '').trim();
  const platform = String(sync_fact['platform'] || '').trim();
  const version = String(sync_fact['version'] || '').trim();
  const device_build = String(sync_fact['device_build_tail'] || '').trim();
  if (!(product && platform && version && device_build)) {
    return '';
  }
  try {
    const { resolve_active_command_tree } = require("../../sync/command_tree_sync");
    const resolved = resolve_active_command_tree({ product, platform, version, device_build });
    const sha = String(resolved?.projection_sha256 || '').trim().toLowerCase();
    return /^[0-9a-f]{64}$/.test(sha) ? sha : '';
  } catch {
    return '';
  }
}

function _live_governing_spec_sha256(recompose_fact: Record<string, any>, batch_name: string): string {
  const status = String(recompose_fact['governing_spec_status'] || '').trim();
  if (status === 'bound') {
    const spec_name = String(recompose_fact['governing_spec'] || '').trim();
    if (!spec_name) {
      return '';
    }
    try {
      const { resolve_indexed_spec } = require("../../kms/spec_index");
      const resolved = resolve_indexed_spec(project_root(), spec_name);
      const sha = String(resolved?.sha256 || '').trim().toLowerCase();
      return /^[0-9a-f]{64}$/.test(sha) ? sha : '';
    } catch {
      return '';
    }
  }
  try {
    const { read_regular_nofollow } = require("../../case_compiler/_sealed_io");
    const raw = read_regular_nofollow(outputs_root().joinpath(batch_name, 'governing_spec_status.json'), { error_type: PyValueError, invalid_message: 'governing spec status path is invalid', directory_message: 'governing spec status parent is unavailable', open_message: 'governing spec status is unavailable', bounds_message: 'governing spec status exceeds its sealed boundary', changed_message: 'governing spec status changed while hashing', max_bytes: 4 * 1024 * 1024, min_bytes: 1 });
    return sha256Hex(raw);
  } catch {
    return '';
  }
}

export function batch_conflict_bindings(state: Record<string, any>, fs_: Record<string, any>[] | null = null): Record<string, string> {
  manifest(state);
  const name = safe_output_component(String(state['out_name'] || 'engine'), { field: 'out_name' });
  const manifest_path = outputs_root().joinpath(name, 'manifest.json');
  let manifest_sha = '';
  try {
    const { read_regular_nofollow } = require("../../case_compiler/_sealed_io");
    const raw = read_regular_nofollow(manifest_path, { error_type: PyValueError, invalid_message: 'bound manifest path is invalid', directory_message: 'bound manifest parent is unavailable', open_message: 'bound manifest is unavailable', bounds_message: 'bound manifest exceeds its sealed size boundary', changed_message: 'bound manifest changed while hashing', max_bytes: 32 * 1024 * 1024, min_bytes: 1, require_current_uid: true });
    manifest_sha = sha256Hex(raw);
  } catch {
    manifest_sha = '';
  }
  const timeline = fs_ !== null ? fs_ : load_facts(state);
  let capability_sha = String(state['capability_projection_sha256'] || '').trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(capability_sha)) {
    let last_sync: any = null;
    for (let i = timeline.length - 1; i >= 0; i--) {
      const fact = timeline[i];
      if (fact['ev'] === 'capability_synced' && /^[0-9a-f]{64}$/.test(String(fact['projection_sha256'] || '').trim().toLowerCase())) {
        last_sync = fact;
        break;
      }
    }
    capability_sha = String((last_sync || {})['projection_sha256'] || '').trim().toLowerCase();
    const live_capability = _live_capability_projection_sha256(last_sync);
    if (live_capability) {
      capability_sha = live_capability;
    }
  }
  let spec_sha = '';
  for (let i = timeline.length - 1; i >= 0; i--) {
    const fact = timeline[i];
    if (fact['ev'] !== 'recompose_done') {
      continue;
    }
    const direct = String(fact['governing_spec_sha256'] || '').trim().toLowerCase();
    const status = String(fact['governing_spec_status_sha256'] || '').trim().toLowerCase();
    if (/^[0-9a-f]{64}$/.test(direct)) {
      spec_sha = direct;
    } else if (/^[0-9a-f]{64}$/.test(status)) {
      spec_sha = status;
    }
    const live_spec = _live_governing_spec_sha256(fact, name);
    if (live_spec) {
      spec_sha = live_spec;
    }
    break;
  }
  return { 'case_manifest_sha256': manifest_sha, 'capability_projection_sha256': capability_sha, 'governing_spec_sha256': spec_sha };
}

export function view(state: Record<string, any>, fs_: Record<string, any>[] | null = null): Record<string, any> {
  if (fs_ === null) {
    fs_ = load_facts(state);
  }
  const vw = V.batch_view(fs_, manifest(state));
  for (const aid of deesc_recovery_waiting(state, fs_, vw)) {
    const c = vw['cases'][aid];
    if (c !== null && c !== undefined && c['status'] === V.S_ESCALATED) {
      c['status'] = V.S_AWAITING_USER;
    }
  }
  const _quarantined_this_run = [...new Set<string>(F.this_run_slice(fs_).filter((f: any) => f['ev'] === 'recompose_case_quarantined' && f['aid']).map((f: any) => String(f['aid'])))];
  for (const aid of _quarantined_this_run) {
    const c = vw['cases'][aid];
    if (c !== null && c !== undefined && !V.is_settled(c['status'])) {
      c['status'] = V.S_TERMINAL;
    }
  }
  const counts: Record<string, number> = {};
  for (const v of Object.values(vw['cases']) as any[]) {
    const s = v['status'];
    counts[s] = (counts[s] || 0) + 1;
  }
  vw['counts'] = counts;
  return vw;
}

export function case_rows(aid: string): Record<string, any>[] {
  const { _load_case_rows: _l } = require("../tools/device/package_registry_tool");
  const p = outputs_root().joinpath(aid, 'case.xlsx');
  try {
    return p.is_file() ? _l(p.toString()) : [];
  } catch {
    return [];
  }
}

export function emit_summary(state: Record<string, any>, summary: Record<string, any>): void {
  try {
    const { _fork_emit_event } = require("../skills/loader");
    _fork_emit_event({ 'event': 'engine_summary', 'run': String(state['out_name'] || 'engine'), ...summary });
  } catch {
    logger.debug('engine summary emit 失败');
  }
}

export function granted_rounds(fs_: Record<string, any>[], aid: string): number {
  const { effective_decision_token } = require("./questions");
  let n = 0;
  for (const f of fs_) {
    if (f['ev'] === 'decision' && String(f['aid']) === aid && String(f['question_id'] ?? '').startsWith('cap:')) {
      const tok = effective_decision_token(f);
      if (tok === 'continue' || tok === 'correct' || (!tok && String(f['answer'] ?? '').includes('继续'))) {
        n += 2;
      }
    }
  }
  return n;
}

export function env_qid(aid: string, mine: Record<string, any>[]): string {
  const seq = mine.filter((d) => d['ev'] === 'decision' && String(d['question_id'] ?? '').startsWith(`env:${aid}:`)).length + 1;
  return `env:${aid}:${seq}`;
}

export function env_confirm_waiting(fs_: Record<string, any>[], vw: Record<string, any>): string[] {
  const out: string[] = [];
  for (const [aid, c] of Object.entries(vw['cases']) as [string, any][]) {
    if ([V.S_DELIVERABLE, V.S_TERMINAL, V.S_SUSPENDED, V.S_ESCALATED, V.S_UNSUPPORTED_FEATURE].includes(c['status'])) {
      continue;
    }
    const mine = fs_.filter((f) => String(f['aid']) === aid);
    const atts = mine.filter((f) => f['ev'] === 'attribution');
    if (!atts.length || String(atts[atts.length - 1]['disposition']) !== 'env_blocked') {
      continue;
    }
    if (V._user_sourced(atts[atts.length - 1])) {
      continue;
    }
    let pos = -1;
    for (let i = 0; i < mine.length; i++) {
      if (mine[i]['ev'] === 'attribution') pos = i;
    }
    const answered = mine.some((f, i) => i > pos && f['ev'] === 'decision' && String(f['question_id'] ?? '').startsWith(`env:${aid}:`));
    if (!answered) {
      out.push(aid);
    }
  }
  return out;
}

export function panel_qid_matches(question_id: any, aid: string, round_number: number): boolean {
  const base = `${PANEL_QID_PREFIX}${aid}:${Math.trunc(round_number)}`;
  const value = String(question_id || '');
  if (value === base) {
    return true;
  }
  const prefix = `${base}:`;
  if (!value.startsWith(prefix)) {
    return false;
  }
  const suffix = value.slice(prefix.length);
  return /^(?:[2-9]|[1-9]\d+)\d*$/.test(suffix);
}

export function panel_question_id(aid: string, round_number: number, facts: Record<string, any>[]): string {
  const base = `${PANEL_QID_PREFIX}${aid}:${Math.trunc(round_number)}`;
  const prior = facts.filter((fact) => fact['ev'] === 'decision' && String(fact['aid'] || '') === aid && panel_qid_matches(fact['question_id'], aid, round_number)).length;
  return prior === 0 ? base : `${base}:${prior + 1}`;
}

export function panel_waiting(fs_: Record<string, any>[], vw: Record<string, any>): string[] {
  const { effective_decision_token, is_retired_manual_panel_shape } = require("./questions");
  const out: string[] = [];
  for (const f of fs_) {
    if (f['ev'] !== 'ask_panel') {
      continue;
    }
    if (is_retired_manual_panel_shape(f)) {
      continue;
    }
    const aid = String(f['aid']);
    const rnd = Math.trunc(Number(f['round']) || 0);
    const c = vw['cases'][aid];
    if (!c || [V.S_DELIVERABLE, V.S_TERMINAL, V.S_SUSPENDED, V.S_ESCALATED, V.S_UNSUPPORTED_FEATURE].includes(c['status'])) {
      continue;
    }
    const answered = fs_.some((d) => d['ev'] === 'decision' && panel_qid_matches(d['question_id'], aid, rnd) && ['confirm', 'correct', 'defect', 'stop', 'downgrade'].includes(effective_decision_token(d)));
    const adopted = fs_.some((d) => d['ev'] === 'adopted' && String(d['aid']) === aid && Math.trunc(Number(d['round']) || 0) === rnd);
    const conditional = fs_.some((d) => d['ev'] === 'conditional_decision' && panel_qid_matches(d['question_id'], aid, rnd));
    if (!answered && !adopted && !conditional && !out.includes(aid)) {
      out.push(aid);
    }
  }
  return out;
}

export function command_domain_isolated(fs_: Record<string, any>[], vw: Record<string, any>, atlas_identity_sha: string): string[] {
  const sha = String(atlas_identity_sha || '').trim();
  if (!sha) {
    return [];
  }
  const out: string[] = [];
  for (const f of fs_) {
    if (f['ev'] !== 'command_domain_case_excluded') {
      continue;
    }
    if (String(f['atlas_identity_sha256'] || '').trim() !== sha) {
      continue;
    }
    const aid = String(f['aid'] || '');
    const case_ = (vw['cases'] || {})[aid];
    if (!case_) {
      continue;
    }
    if (String(f['artifact'] || '') !== String(case_['artifact'] || '')) {
      continue;
    }
    if (!out.includes(aid)) {
      out.push(aid);
    }
  }
  return out;
}

export function suspended_resume_waiting(fs_: Record<string, any>[], vw: Record<string, any>): string[] {
  const n_runs = fs_.filter((f) => f['ev'] === 'run_start').length;
  const _batch_pending = batch_conflict_decision_aids(fs_);
  const out: string[] = [];
  for (const [aid, c] of Object.entries(vw['cases']) as [string, any][]) {
    if (c['status'] !== V.S_SUSPENDED) {
      continue;
    }
    if (_batch_pending.has(aid)) {
      continue;
    }
    let idx_susp = -1;
    for (let i = 0; i < fs_.length; i++) {
      if (fs_[i]['ev'] === 'suspended' && String(fs_[i]['aid']) === aid) idx_susp = i;
    }
    if (idx_susp < 0 || !fs_.slice(idx_susp + 1).some((f) => f['ev'] === 'run_start')) {
      continue;
    }
    const qid = `resume:${aid}:${n_runs}`;
    if (!fs_.some((d) => d['ev'] === 'decision' && d['question_id'] === qid && String(d['aid']) === aid)) {
      out.push(aid);
    }
  }
  return out;
}

function _deesc_precedent_key(aid: string, subclass: string, state: Record<string, any>): string {
  const fam = String(state['evidence_build'] || '').split('.').slice(0, 3).join('.');
  return `${aid}|${subclass}|${fam}|${state['bed_host'] || ''}`;
}

export function deesc_qid(aid: string, mine: Record<string, any>[]): string {
  const seq = mine.filter((d) => d['ev'] === 'decision' && String(d['question_id'] ?? '').startsWith(`deesc:${aid}:`)).length + 1;
  return `deesc:${aid}:${seq}`;
}

function _escalation_is_engine_budget(mine: Record<string, any>[]): boolean {
  for (let i = mine.length - 1; i >= 0; i--) {
    if (mine[i]['ev'] !== 'escalated') {
      continue;
    }
    return !!escalation_budget_kind(mine[i]);
  }
  return false;
}

export function escalation_budget_kind(fact: Record<string, any>): string {
  const { FORK_RECURSION_LIMIT_MARKER, FORK_WALLCLOCK_MARKER } = require("../resilience");
  const declared = String(fact['engine_budget_exhausted'] || '');
  if (declared) {
    return declared;
  }
  const reason = String(fact['reason'] || '');
  if (reason.includes(`no ${FORK_WALLCLOCK_MARKER}`)) {
    return '';
  }
  if (reason.includes(`${FORK_WALLCLOCK_MARKER} marker present`)) {
    return 'wallclock';
  }
  if (reason.includes(`${FORK_RECURSION_LIMIT_MARKER} marker present`)) {
    return 'turn_budget';
  }
  return '';
}

export function deesc_recovery_waiting(state: Record<string, any>, fs_: Record<string, any>[], vw: Record<string, any>): string[] {
  const out: string[] = [];
  for (const aid of Object.keys(vw['cases'])) {
    const mine = fs_.filter((f) => String(f['aid']) === aid);
    if (!V._is_escalated(mine)) {
      continue;
    }
    if (_escalation_is_engine_budget(mine)) {
      continue;
    }
    const sub = F.escalated_subclass(fs_, aid);
    let last_esc_i = -1;
    for (let i = 0; i < mine.length; i++) {
      if (mine[i]['ev'] === 'escalated') last_esc_i = i;
    }
    const deesc_this_round = mine.filter((f, i) => i > last_esc_i && f['ev'] === 'decision' && String(f['question_id'] ?? '').startsWith(`deesc:${aid}:`));
    if (!deesc_this_round.length) {
      out.push(aid);
      continue;
    }
    const last = deesc_this_round[deesc_this_round.length - 1];
    if (String(last['token']) !== 'deesc_keep') {
      continue;
    }
    const key = _deesc_precedent_key(aid, sub, state);
    if (mine.some((f) => f['ev'] === 'deesc_keep' && f['precedent_key'] === key)) {
      continue;
    }
    out.push(aid);
  }
  return out;
}

export function ask_targets(state: Record<string, any>, fs_: Record<string, any>[], vw: Record<string, any>): Record<string, any> {
  const contra: string[] = [];
  for (const [aid, c] of Object.entries(vw['cases']) as [string, any][]) {
    if (c['status'] === V.S_CONTRADICTED && c['contradictions'] >= 2) {
      const mine = fs_.filter((fact) => String(fact['aid'] || '') === aid);
      if (V.execution_pause_resume_pending(mine)) {
        continue;
      }
      const qid = `contra:${aid}:${c['contradictions']}`;
      if (!fs_.some((d) => d['ev'] === 'decision' && d['question_id'] === qid)) {
        contra.push(aid);
      }
    }
  }
  return { 'panel': panel_waiting(fs_, vw), 'contra': contra, 'env': env_confirm_waiting(fs_, vw), 'suspended': suspended_resume_waiting(fs_, vw), 'deesc': deesc_recovery_waiting(state, fs_, vw) };
}

function _decision_resolves_needs_decision(need: Record<string, any>, decision: Record<string, any>, migration_facts: Record<string, any>[] | null = null): boolean {
  if (decision['ev'] !== 'decision') {
    return false;
  }
  const question_id = String(need['question_id'] || '');
  if (!question_id || String(decision['question_id'] || '') !== question_id) {
    return false;
  }
  const need_aid = String(need['aid'] || '');
  const decision_aid = String(decision['aid'] || '');
  if (need_aid && decision_aid !== need_aid) {
    return false;
  }
  if (accepts_schema(decision['schema'], 'ist.case-terminal-static-void')) {
    if (!(decision['answer'] === 'case_terminal_static_void' && ['case_terminal_static_void', '****'].includes(String(decision['token'] || '')))) {
      return false;
    }
    if (migration_facts === null) {
      return true;
    }
    return case_terminal_settled_aids(migration_facts).has(need_aid);
  }
  if (accepts_schema(decision['schema'], 'ist.author-definition-gap-auto-resolution')) {
    const token = String(decision['token'] || '');
    const base_valid = !!(decision['answer'] === 'author_definition_gap_disclosed' && ['author_definition_gap_disclosed', '****'].includes(token) && /^[0-9a-f]{64}$/.test(String(decision['ledger_sha256'] || '')));
    if (!base_valid) {
      return false;
    }
    if (migration_facts === null) {
      return true;
    }
    const { author_definition_gap_auto_resolution_valid } = require("./terminal_credentials");
    return author_definition_gap_auto_resolution_valid({ aid: need_aid, ledger_sha256: String(decision['ledger_sha256'] || ''), facts: migration_facts });
  }
  if (need['criterion_rule_batch'] === true) {
    return !!(accepts_schema(decision['schema'], 'ist.criterion-author-batch-decision') && String(decision['answer'] || '') === 'criterion_author_rules_committed' && String(decision['token'] || '') === 'criterion_author_rules_committed' && Math.trunc(Number(decision['question_count']) || 0) > 0 && (Math.trunc(Number(decision['committed_count']) || 0) === Math.trunc(Number(decision['question_count']) || 0)));
  }
  const CC = require("./conflict_chain");
  if (CC.is_direct_abandon_decision(decision)) {
    return CC.need_accepts_direct_abandon(need, String(decision['conflict_scenario'] || ''));
  }
  if (CC.batch_auto_case_decision_resolves(need, decision)) {
    return true;
  }
  if (CC.batch_conflict_decision_resolves_need(need, decision)) {
    return true;
  }
  if ((migration_facts || []).some((migration: any) => CC.batch_conflict_binding_migration_resolves_need(need, decision, migration))) {
    return true;
  }
  const legacy_conflict_scenarios = need['conflict_scenarios'];
  if (['scenario_3', 'scenario_4'].includes(String(need['conflict_scenario'] || '')) || (Array.isArray(legacy_conflict_scenarios) && legacy_conflict_scenarios.some((value) => ['scenario_3', 'scenario_4'].includes(value))) || 'expected_delta_ids' in need) {
    return false;
  }
  const answer = decision['answer'];
  if (typeof answer !== "string" || !answer.trim()) {
    return false;
  }
  const { CONFLICT_DECISIONS, DECISIONS, SCENARIO4_DECISIONS, SPEC_UNKNOWN_DECISIONS, effective_decision_token } = require("./questions");
  const by_scenario: Record<string, Set<string>> = { 'scenario_1': new Set(['abandon_generation']), 'scenario_2': new Set(['abandon_generation']), 'scenario_3': new Set(CONFLICT_DECISIONS), 'scenario_4': new Set(SCENARIO4_DECISIONS), 'spec_unknown': new Set(['continue_without_spec']) };
  const resolving_tokens: Set<string> = new Set([...DECISIONS, ...CONFLICT_DECISIONS, ...SCENARIO4_DECISIONS, ...SPEC_UNKNOWN_DECISIONS, 'conflict_delta_conjunction']);
  let token = effective_decision_token(decision);
  if (['', '****'].includes(token) && decision['freeform'] !== true) {
    token = resolving_tokens.has(answer.trim()) ? answer.trim() : '';
  }
  const need_scenario = String(need['conflict_scenario'] || '');
  const decision_scenario = String(decision['conflict_scenario'] || '');
  if (need_scenario && decision_scenario && need_scenario !== decision_scenario) {
    return false;
  }
  const scenario = need_scenario || decision_scenario;
  const delta_mode = 'expected_delta_ids' in need;
  const auxiliary_claims = need['auxiliary_claims'];
  if (!delta_mode && Array.isArray(auxiliary_claims)) {
    if (auxiliary_claims.length !== 1 || scenario !== 'spec_unknown') {
      return false;
    }
    const claim = auxiliary_claims[0];
    if (typeof claim !== "object" || claim === null || Array.isArray(claim) || !accepts_schema(claim['schema'], 'ist.delta.conflict-claim') || claim['conflict_scenario'] !== 'spec_unknown') {
      return false;
    }
    const chain_id = String(claim['conflict_chain_id'] || '');
    return by_scenario['spec_unknown'].has(token) && decision['conflict_chain_id'] === chain_id && /^[0-9a-f]{64}$/.test(chain_id);
  }
  if (['scenario_3', 'scenario_4'].includes(scenario) && !delta_mode) {
    return false;
  }
  if (delta_mode) {
    const expected_delta_ids = need['expected_delta_ids'];
    const expected_count = need['expected_count'];
    const conflict_scenarios = need['conflict_scenarios'];
    const needs_decision_sha256 = need['needs_decision_sha256'];
    const delta_claims = need['delta_claims'];
    if (!Array.isArray(expected_delta_ids) || !expected_delta_ids.length || expected_delta_ids.some((delta_id: any) => typeof delta_id !== "string" || !delta_id.trim() || delta_id !== delta_id.trim()) || new Set(expected_delta_ids).size !== expected_delta_ids.length || typeof expected_count !== "number" || !Number.isInteger(expected_count) || expected_count !== expected_delta_ids.length || !Array.isArray(conflict_scenarios) || !conflict_scenarios.length || conflict_scenarios.some((item: any) => typeof item !== "string" || !['scenario_3', 'scenario_4'].includes(item)) || JSON.stringify(conflict_scenarios) !== JSON.stringify([...new Set(conflict_scenarios as string[])].sort()) || typeof needs_decision_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(needs_decision_sha256)) {
      return false;
    }
    if (conflict_scenarios.length === 1) {
      if (need_scenario && need_scenario !== conflict_scenarios[0]) {
        return false;
      }
    } else if (need_scenario || decision_scenario) {
      return false;
    }
    if (Array.isArray(delta_claims)) {
      const { CONFLICT_DECISION_SCHEMA, DeltaAction, conflict_token_action, decision_is_current, reduce_delta_frontier } = require("./conflict_chain");
      if (delta_claims.length !== expected_count || delta_claims.some((claim: any) => typeof claim !== "object" || claim === null || Array.isArray(claim)) || JSON.stringify(delta_claims.map((claim: any) => claim['delta_id'])) !== JSON.stringify(expected_delta_ids) || delta_claims.some((claim: any) => !accepts_schema(claim['schema'], 'ist.delta.conflict-claim') || !['scenario_3', 'scenario_4'].includes(claim['conflict_scenario']) || !/^[0-9a-f]{64}$/.test(String(claim['conflict_chain_id'] || ''))) || JSON.stringify([...new Set(delta_claims.map((claim: any) => String(claim['conflict_scenario'] || '')))].sort()) !== JSON.stringify(conflict_scenarios) || token !== 'conflict_delta_conjunction' || decision['needs_decision_sha256'] !== needs_decision_sha256) {
        return false;
      }
      const rows = decision['delta_decisions'];
      if (!Array.isArray(rows)) {
        return false;
      }
      const claim_by_delta: Record<string, any> = {};
      for (const claim of delta_claims) {
        claim_by_delta[String(claim['delta_id'])] = claim;
      }
      for (const row of rows) {
        if (typeof row !== "object" || row === null || Array.isArray(row)) {
          return false;
        }
        const delta_id = String(row['delta_id'] || '');
        const claim = claim_by_delta[delta_id];
        const row_token = String(row['token'] || '');
        let action = conflict_token_action(row_token);
        if (claim === null || claim === undefined || row['schema'] !== CONFLICT_DECISION_SCHEMA || row['conflict_scenario'] !== claim['conflict_scenario'] || !decision_is_current(row, claim['conflict_chain_id'], { expected_delta_id: delta_id })) {
          return false;
        }
        const allowed = by_scenario[String(claim['conflict_scenario'])];
        if (!allowed.has(row_token) || action === null || action === undefined) {
          return false;
        }
        if (row_token === 'use_case_expectation' && claim['case_expectation_supported'] === false) {
          action = DeltaAction.TERMINATE;
        }
        if (row['action'] !== action.value) {
          return false;
        }
      }
      const frontier = reduce_delta_frontier(delta_claims, rows);
      if (!frontier.valid) {
        return false;
      }
      const effective_ids = Array.from(frontier.effective_delta_ids);
      const pruned_ids = Array.from(frontier.pruned_delta_ids);
      const effective_scenarios = [...new Set(effective_ids.map((delta_id: any) => String(claim_by_delta[delta_id]['conflict_scenario'])))].sort();
      if (JSON.stringify(decision['original_expected_delta_ids']) !== JSON.stringify(expected_delta_ids) || typeof decision['original_expected_count'] !== "number" || !Number.isInteger(decision['original_expected_count']) || decision['original_expected_count'] !== expected_count || JSON.stringify(decision['expected_delta_ids']) !== JSON.stringify(effective_ids) || typeof decision['expected_count'] !== "number" || !Number.isInteger(decision['expected_count']) || decision['expected_count'] !== effective_ids.length || JSON.stringify(decision['pruned_delta_ids']) !== JSON.stringify(pruned_ids) || typeof decision['pruned_count'] !== "number" || !Number.isInteger(decision['pruned_count']) || decision['pruned_count'] !== pruned_ids.length || typeof decision['decided_count'] !== "number" || !Number.isInteger(decision['decided_count']) || decision['decided_count'] !== frontier.reduction.decided_count || JSON.stringify(decision['conflict_scenarios']) !== JSON.stringify(effective_scenarios)) {
        return false;
      }
      const expected_auxiliary = Array.isArray(auxiliary_claims) ? auxiliary_claims : [];
      const actual_auxiliary = decision['auxiliary_decisions'] || [];
      if (!Array.isArray(actual_auxiliary)) {
        return false;
      }
      const aux_by_chain: Record<string, any> = {};
      for (const claim of expected_auxiliary) {
        if (typeof claim !== "object" || claim === null || Array.isArray(claim) || !accepts_schema(claim['schema'], 'ist.delta.conflict-claim') || claim['conflict_scenario'] !== 'spec_unknown' || !/^[0-9a-f]{64}$/.test(String(claim['conflict_chain_id'] || ''))) {
          return false;
        }
        aux_by_chain[String(claim['conflict_chain_id'])] = claim;
      }
      if (Object.keys(aux_by_chain).length !== expected_auxiliary.length) {
        return false;
      }
      const seen_auxiliary: Set<string> = new Set();
      for (const row of actual_auxiliary) {
        if (typeof row !== "object" || row === null || Array.isArray(row)) {
          return false;
        }
        const chain_id = String(row['conflict_chain_id'] || '');
        if (!accepts_schema(row['schema'], 'ist.delta.auxiliary-decision') || row['conflict_scenario'] !== 'spec_unknown' || !(chain_id in aux_by_chain) || seen_auxiliary.has(chain_id) || !by_scenario['spec_unknown'].has(row['token']) || !String(row['answer_key'] || '')) {
          return false;
        }
        seen_auxiliary.add(chain_id);
      }
      return seen_auxiliary.size === Object.keys(aux_by_chain).length && [...seen_auxiliary].every((c) => c in aux_by_chain);
    }
    if (token === 'conflict_delta_conjunction') {
      const decision_expected_count = decision['expected_count'];
      if (!Array.isArray(decision['expected_delta_ids']) || JSON.stringify(decision['expected_delta_ids']) !== JSON.stringify(expected_delta_ids) || typeof decision_expected_count !== "number" || !Number.isInteger(decision_expected_count) || decision_expected_count !== expected_count || !Array.isArray(decision['conflict_scenarios']) || JSON.stringify(decision['conflict_scenarios']) !== JSON.stringify(conflict_scenarios) || decision['needs_decision_sha256'] !== needs_decision_sha256) {
        return false;
      }
      const decided_count = decision['decided_count'];
      if (typeof decided_count !== "number" || !Number.isInteger(decided_count) || decided_count !== expected_count) {
        return false;
      }
      const rows = decision['delta_decisions'];
      if (!Array.isArray(rows) || rows.length !== decided_count) {
        return false;
      }
      const { reduce_delta_decisions } = require("./conflict_chain");
      const reduction = reduce_delta_decisions(expected_delta_ids, rows);
      return reduction.valid && reduction.expected_count === expected_count && reduction.decided_count === decided_count;
    }
    if (expected_delta_ids.length !== 1 || conflict_scenarios.length !== 1) {
      return false;
    }
    const allowed = by_scenario[conflict_scenarios[0]];
    return allowed !== undefined && allowed.has(token) && decision['delta_id'] === expected_delta_ids[0] && decision['needs_decision_sha256'] === needs_decision_sha256;
  }
  if (token === 'conflict_delta_conjunction') {
    return false;
  }
  if (scenario) {
    const allowed = by_scenario[scenario];
    return allowed !== undefined && allowed.has(token);
  }
  return resolving_tokens.has(token);
}

export function unresolved_static_decision_facts(fs_: Record<string, any>[]): Record<string, any>[] {
  const decisions_by_question_id: Record<string, Record<string, any>[]> = {};
  for (const fact of fs_) {
    if (fact['ev'] !== 'decision' || !fact['question_id']) {
      continue;
    }
    const qid = String(fact['question_id']);
    if (!decisions_by_question_id[qid]) decisions_by_question_id[qid] = [];
    decisions_by_question_id[qid].push(fact);
  }
  const unresolved: Record<string, any>[] = [];
  for (let index = 0; index < fs_.length; index++) {
    const fact = fs_[index];
    if (fact['ev'] !== 'needs_decision' || !fact['aid']) {
      continue;
    }
    const aid = String(fact['aid'] || '');
    const superseded = fs_.slice(index + 1).some((later) => later['ev'] === 'conflict_chain_reentered' && String(later['aid'] || '') === aid && later['invalidate_decisions'] === true);
    if (superseded) {
      continue;
    }
    if (!(decisions_by_question_id[String(fact['question_id'] || '')] || []).some((decision) => _decision_resolves_needs_decision(fact, decision, fs_))) {
      unresolved.push(fact);
    }
  }
  return unresolved;
}

export function unresolved_static_decision_aids(fs_: Record<string, any>[]): Set<string> {
  return new Set(unresolved_static_decision_facts(fs_).filter((fact) => fact['aid']).map((fact) => String(fact['aid'] || '')));
}

export function case_terminal_settled_aids(fs_: Record<string, any>[]): Set<string> {
  const settled = new Set(fs_.filter((fact) => fact['ev'] === 'case_terminal_outcome' && fact['aid']).map((fact) => String(fact['aid'] || '')));
  for (const fact of EE.case_scoped_engine_errors(fs_)) {
    if (fact['aid']) settled.add(String(fact['aid'] || ''));
  }
  return settled;
}

export function batch_conflict_decision_aids(fs_: Record<string, any>[]): Set<string> {
  const out: Set<string> = new Set();
  for (const fact of unresolved_static_decision_facts(fs_)) {
    const aid = String(fact['aid'] || '');
    const ids = fact['batch_conflict_claim_ids'];
    if (aid && Array.isArray(ids) && ids.some((v: any) => String(v).trim())) {
      out.add(aid);
    }
  }
  return out;
}

export function static_ask_settled_aids(fs_: Record<string, any>[]): Set<string> {
  const settled: Set<string> = new Set();
  const mine_slice = F.this_run_slice(fs_);
  const decisions = mine_slice.filter((f) => f['ev'] === 'decision');
  for (let index = 0; index < mine_slice.length; index++) {
    const need = mine_slice[index];
    if (need['ev'] !== 'needs_decision' || !need['aid']) {
      continue;
    }
    const aid = String(need['aid'] || '');
    let resolved_at = -1;
    for (let position = 0; position < mine_slice.length; position++) {
      const decision = mine_slice[position];
      if (decision['ev'] === 'decision' && decisions.includes(decision) && _decision_resolves_needs_decision(need, decision, mine_slice)) {
        resolved_at = position;
        break;
      }
    }
    if (resolved_at < 0) {
      continue;
    }
    const reentered = mine_slice.slice(Math.max(resolved_at, index) + 1).some((later) => later['ev'] === 'conflict_chain_reentered' && String(later['aid'] || '') === aid && later['invalidate_decisions'] === true);
    if (!reentered) {
      settled.add(aid);
    }
  }
  const { batch_conflict_binding_migration_resolves_need } = require("./conflict_chain");
  const all_needs = fs_.filter((fact) => fact['ev'] === 'needs_decision');
  const all_decisions = fs_.filter((fact) => fact['ev'] === 'decision');
  for (let index = 0; index < mine_slice.length; index++) {
    const migration = mine_slice[index];
    if (migration['ev'] !== 'needs_decision_binding_migrated') {
      continue;
    }
    const aid = String(migration['aid'] || '');
    const qid = String(migration['question_id'] || '');
    if (!aid || !qid) {
      continue;
    }
    const migrated = all_needs.some((need) => String(need['aid'] || '') === aid && String(need['question_id'] || '') === qid && all_decisions.some((decision) => String(decision['aid'] || '') === aid && String(decision['question_id'] || '') === qid && batch_conflict_binding_migration_resolves_need(need, decision, migration)));
    if (!migrated) {
      continue;
    }
    const reentered = mine_slice.slice(index + 1).some((later) => later['ev'] === 'conflict_chain_reentered' && String(later['aid'] || '') === aid && later['invalidate_decisions'] === true);
    if (!reentered) {
      settled.add(aid);
    }
  }
  return settled;
}

export function settled_claim_chain_ids(fs_: Record<string, any>[], aid: string): Set<string> {
  const mine_slice = F.this_run_slice(fs_).filter((fact) => String(fact['aid'] || '') === String(aid));
  const reentered_at = mine_slice.map((fact, position) => [position, fact] as const).filter(([, fact]) => fact['ev'] === 'conflict_chain_reentered' && fact['invalidate_decisions'] === true).map(([position]) => position);
  const floor = reentered_at.length ? Math.max(...reentered_at) + 1 : 0;
  return new Set(mine_slice.slice(floor).filter((fact) => fact['ev'] === 'decision' && String(fact['conflict_chain_id'] || '')).map((fact) => String(fact['conflict_chain_id'] || '')));
}

export function ledger_claims_all_settled(fs_: Record<string, any>[], aid: string, ledger: any): boolean {
  if (typeof ledger !== "object" || ledger === null || Array.isArray(ledger)) {
    return false;
  }
  const claims = (ledger['claims'] || []).filter((claim: any) => typeof claim === "object" && claim !== null && !Array.isArray(claim));
  if (!claims.length) {
    return false;
  }
  const chain_ids = claims.map((claim: any) => String(claim['conflict_chain_id'] || ''));
  if (!chain_ids.every((x: string) => x)) {
    return false;
  }
  const settled = settled_claim_chain_ids(fs_, aid);
  return chain_ids.every((id: string) => settled.has(id));
}

export const REAUTHOR_UNAVAILABLE_EVENT = 'author_reauthor_unavailable';

export function emit_reauthor_aids(fs_: Record<string, any>[], vw: Record<string, any>, opts: { waiting: Set<string> }): Set<string> {
  const { waiting } = opts;
  const latest: Record<string, string> = {};
  for (const fact of F.this_run_slice(fs_)) {
    const aid = String(fact['aid'] || '');
    if (!aid) {
      continue;
    }
    const event = fact['ev'];
    if (event === 'composed') {
      latest[aid] = 'composed';
    } else if (event === 'authored') {
      latest[aid] = 'authored';
    } else if (event === REAUTHOR_UNAVAILABLE_EVENT) {
      latest[aid] = 'no_reauthor_path';
    } else if (event === 'emit_invalid') {
      const { active_producer_refs, mechanical_emit_refusal } = require("./emit_failure_evidence");
      const supported = !mechanical_emit_refusal(fact) || active_producer_refs(fs_, { aid, dispatch_id: String(fact['dispatch_id'] || ''), batch_run_id: String(fact['batch_run_id'] || '') });
      latest[aid] = (fact['reject_class'] === F.EMIT_REJECT_PRODUCER && supported) ? 'reauthor' : 'not_producer';
    }
  }
  const out: Set<string> = new Set();
  for (const [aid, mark] of Object.entries(latest)) {
    if (mark !== 'reauthor' || waiting.has(aid)) {
      continue;
    }
    const case_ = (vw['cases'] || {})[aid];
    if (!case_ || V.is_settled(String(case_['status'] || ''))) {
      continue;
    }
    out.add(aid);
  }
  return out;
}

export function emit_reauthor_waiting(state: Record<string, any>, fs_: Record<string, any>[], vw: Record<string, any>, opts: { targets?: Record<string, any> | null } = {}): Set<string> {
  const targets = opts.targets ?? null;
  const t = targets === null ? ask_targets(state, fs_, vw) : targets;
  const waiting = new Set<string>([...t['panel'], ...t['contra'], ...t['env'], ...t['suspended'], ...t['deesc']]);
  const suspendedSet = new Set<string>(t['suspended']);
  const out = new Set<string>([...waiting, ...[...unresolved_static_decision_aids(fs_)].filter((a) => !suspendedSet.has(a))]);
  return out;
}

export function emit_reauthor_route_aids(state: Record<string, any>, fs_: Record<string, any>[], vw: Record<string, any>, opts: { targets?: Record<string, any> | null } = {}): Set<string> {
  return emit_reauthor_aids(fs_, vw, { waiting: emit_reauthor_waiting(state, fs_, vw, opts) });
}

function _deescalated_pending_aids(fs_: Record<string, any>[], vw: Record<string, any>): Set<string> {
  const out: Set<string> = new Set();
  const cases = (vw || {})['cases'] || {};
  for (const [aid, case_] of Object.entries(cases) as [string, any][]) {
    if (String((case_ || {})['status'] || '') !== V.S_PENDING) {
      continue;
    }
    const mine = F.this_run_slice(fs_).filter((f) => String(f['aid'] || '') === aid);
    let last_deesc = -1;
    for (let i = 0; i < mine.length; i++) {
      if (mine[i]['ev'] === 'de_escalated') last_deesc = i;
    }
    if (last_deesc < 0) {
      continue;
    }
    const spent = mine.slice(last_deesc + 1).some((f) => f['ev'] === 'composed' || f['ev'] === 'authored');
    if (!spent) {
      out.add(String(aid));
    }
  }
  return out;
}

export function counts_update(state: Record<string, any>, fs_: Record<string, any>[] | null = null): Record<string, any> {
  if (fs_ === null) {
    fs_ = load_facts(state);
  }
  const vw = view(state, fs_);
  const c = vw['counts'];
  const t = ask_targets(state, fs_, vw);
  const _waiting = new Set<string>([...t['panel'], ...t['contra'], ...t['env'], ...t['suspended'], ...t['deesc']]);
  const _suspendedSet = new Set<string>(t['suspended']);
  const _pending_decision_aids = new Set<string>([...unresolved_static_decision_aids(fs_)].filter((a) => !_suspendedSet.has(a)));
  const _delivery_merges = fs_.filter((fact) => fact['ev'] === 'merged' && fact['ctx'] !== F.CTX_SUBSET);
  const _current_delivery_comp = new Set<string>((_delivery_merges.length ? (_delivery_merges[_delivery_merges.length - 1]['composition'] || []) : []).filter((aid: any) => aid).map((aid: any) => String(aid)));
  const _deliverable_aids = new Set(Object.entries(vw['cases']).filter(([, case_]) => (case_ as any)['status'] === V.S_DELIVERABLE).map(([aid]) => aid));
  let _delivery_reverify = !!(_deliverable_aids.size && !(_current_delivery_comp.size === _deliverable_aids.size && [..._current_delivery_comp].every((a: string) => _deliverable_aids.has(a))));
  const current_capability_sha = String(state['capability_projection_sha256'] || '').trim().toLowerCase();
  const _delivery_capability_stale = new Set([..._deliverable_aids].filter((aid) => {
    if (!/^[0-9a-f]{64}$/.test(current_capability_sha)) return false;
    let found = '';
    for (let i = fs_!.length - 1; i >= 0; i--) {
      const fact = fs_![i];
      if (fact['ev'] === 'verdict' && fact['ctx'] === F.CTX_DELIVERY && fact['result'] === 'pass' && String(fact['aid'] || '') === aid) {
        found = String(fact['capability_projection_sha256'] || '');
        break;
      }
    }
    return found !== current_capability_sha;
  }));
  _delivery_reverify = _delivery_reverify || _delivery_capability_stale.size > 0;
  const { latest_batch_backstop_stop } = require("./backstops");
  const { batch_halted } = require("./engine_quarantine");
  const suspended_aids = new Set(Object.entries(vw['cases']).filter(([, case_]) => String((case_ as any)['status'] || '') === V.S_SUSPENDED).map(([aid]) => aid));
  const _batch_suspended_conflicts = [...batch_conflict_decision_aids(fs_)].filter((a) => suspended_aids.has(a));
  const ask_shown_aids = new Set<string>(F.this_run_slice(fs_).filter((f: any) => f['ev'] === 'ask_shown').map((f: any) => String(f['aid'])));
  const _waiting_unshown = [..._waiting].filter((a) => !ask_shown_aids.has(a));
  return { 'n_recorded_batch_stop': batch_halted(fs_) ? 1 : 0, 'n_batch_backstop': latest_batch_backstop_stop(fs_) !== null && latest_batch_backstop_stop(fs_) !== undefined ? 1 : 0, 'n_batch_execution_pause': F.this_run_slice(fs_).some((f: any) => f['ev'] === 'batch_execution_paused') ? 1 : 0, 'n_engine_error': EE.active_engine_errors(fs_).filter((_e: any) => EE.error_halts_batch(_e)).length, 'n_pending': c[V.S_PENDING] || 0, 'n_composed': F.emit_todo_aids(fs_).size, 'n_compose_rejected': [...new Set<string>(F.this_run_slice(fs_).filter((f: any) => f['ev'] === 'compose_rejected' && f['aid']).map((f: any) => String(f['aid'] || '')))].length, 'n_emit_reauthor': emit_reauthor_route_aids(state, fs_, vw, { targets: t }).size, 'n_reauthor_pending': _deescalated_pending_aids(fs_, vw).size, 'n_awaiting_user': c[V.S_AWAITING_USER] || 0, 'n_awaiting_decision': _pending_decision_aids.size, 'n_batch_conflict_suspended': _batch_suspended_conflicts.length, 'n_static_unanswered': unresolved_static_decision_aids(fs_).size, 'n_authored': c[V.S_AUTHORED] || 0, 'n_failed': (c[V.S_FAILED] || 0) + (c[V.S_CONTRADICTED] || 0), 'n_subset_verified': c[V.S_SUBSET_VERIFIED] || 0, 'n_broken': c[V.S_BROKEN] || 0, 'n_broken_errored': c[V.S_BROKEN_ERRORED] || 0, 'n_broken_blocked': c[V.S_BROKEN_BLOCKED] || 0, 'n_broken_aborted': c[V.S_BROKEN_ABORTED] || 0, 'n_broken_verdict_unrecognized': c[V.S_BROKEN_VERDICT_UNRECOGNIZED] || 0, 'n_rerunnable': (c[V.S_BROKEN] || 0) + (c[V.S_BROKEN_ABORTED] || 0) + (c[V.S_BROKEN_VERDICT_UNRECOGNIZED] || 0), 'n_deliverable': c[V.S_DELIVERABLE] || 0, 'n_delivery_reverify': _delivery_reverify ? _deliverable_aids.size : 0, 'n_contradicted': c[V.S_CONTRADICTED] || 0, 'n_settled_bad': (c[V.S_ESCALATED] || 0) + (c[V.S_TERMINAL] || 0) + (c[V.S_SUSPENDED] || 0) + (c[V.S_UNSUPPORTED_FEATURE] || 0), 'n_ask_contradiction': _waiting.size, 'n_ask_contradiction_unshown': _waiting_unshown.length };
}

export function _latest_rerun_prescription(fs_: Record<string, any>[], aid: string): boolean {
  return F.execution_retry_requested(fs_, aid);
}

export function lint_credential_snapshot(aid: string): [Buffer, string, string] {
  try {
    aid = safe_output_component(aid, { field: 'autoid' });
  } catch (e) {
    if (e instanceof PyValueError) {
      return [Buffer.from(''), '', 'credential_unreadable'];
    }
    throw e;
  }
  const { _MAX_CREDENTIAL_BYTES, _MAX_XLSX_BYTES, _read_regular_under_root } = require("../tools/device/run_case");
  const root = outputs_root();
  const case_rel = new P(aid).joinpath('case.xlsx');
  const credential_rel = new P(aid).joinpath('.grade_credential.json');
  let case_payload: Buffer;
  try {
    [case_payload] = _read_regular_under_root(root, case_rel, { max_bytes: _MAX_XLSX_BYTES });
  } catch (e: any) {
    if (e instanceof FileNotFoundError || e?.code === 'ENOENT') {
      return [Buffer.from(''), '', 'case_missing'];
    }
    return [Buffer.from(''), '', 'case_unreadable'];
  }
  let credential_payload: Buffer;
  try {
    [credential_payload] = _read_regular_under_root(root, credential_rel, { max_bytes: _MAX_CREDENTIAL_BYTES });
  } catch (e: any) {
    if (e instanceof FileNotFoundError || e?.code === 'ENOENT') {
      return [Buffer.from(''), '', 'credential_missing'];
    }
    return [Buffer.from(''), '', 'credential_unreadable'];
  }
  let credential: any;
  try {
    credential = JSON.parse(credential_payload.toString('utf-8'));
  } catch {
    return [Buffer.from(''), '', 'credential_unreadable'];
  }
  const credential_sha256 = (typeof credential === "object" && credential !== null && !Array.isArray(credential)) ? String(credential['xlsx_sha256'] || '') : '';
  if (!(typeof credential === "object" && credential !== null && !Array.isArray(credential) && credential['source'] === 'lint' && credential['lint_ok'] === true && String(credential['autoid'] || '') === aid && credential['xlsx'] === new P('workspace').joinpath('outputs', aid, 'case.xlsx').as_posix() && credential['verdict'] === 'PASS' && credential_sha256.length === 64 && [...credential_sha256].every((ch) => '0123456789abcdef'.includes(ch)))) {
    return [Buffer.from(''), '', 'credential_contract_invalid'];
  }
  const live_sha256 = sha256Hex(case_payload);
  if (credential_sha256 !== live_sha256) {
    return [Buffer.from(''), '', 'credential_sha256_mismatch'];
  }
  return [case_payload, live_sha256, 'ok'];
}

export const MECHANICAL_FINDINGS_DROP_REASONS: string[] = ['autoid_invalid', 'credential_not_ok', 'sidecar_missing', 'oversized', 'unreadable', 'json_invalid', 'schema_mismatch', 'autoid_mismatch', 'xlsx_sha256_mismatch', 'rows_invalid'];

function _drop_mechanical_findings(aid: string, reason: string, opts: { trace?: boolean } = {}): Record<string, any>[] {
  const trace = opts.trace ?? false;
  if (!MECHANICAL_FINDINGS_DROP_REASONS.includes(reason)) {
    throw new PyAssertionError(reason);
  }
  logger.debug('交卷机械发现读回丢弃(aid=%s, reason=%s)', aid, reason);
  return [];
}

export function mechanical_findings_rows(aid: string): Record<string, any>[] {
  try {
    aid = safe_output_component(aid, { field: 'autoid' });
  } catch (e) {
    if (e instanceof PyValueError) {
      return _drop_mechanical_findings(String(aid), 'autoid_invalid');
    }
    throw e;
  }
  const { MAX_MECHANICAL_FINDINGS_BYTES, MECHANICAL_FINDINGS_SCHEMA } = require("../../case_compiler/device_characteristics");
  const { MECHANICAL_FINDINGS_SIDECAR_NAME } = require("../../engine_managed_outputs");
  const { _read_regular_under_root } = require("../tools/device/run_case");
  const [_case_payload, credential_sha256, status] = lint_credential_snapshot(aid);
  if (status !== 'ok' || credential_sha256.length !== 64) {
    return _drop_mechanical_findings(aid, 'credential_not_ok');
  }
  let payload: Buffer;
  try {
    [payload] = _read_regular_under_root(outputs_root(), new P(aid).joinpath(MECHANICAL_FINDINGS_SIDECAR_NAME), { max_bytes: MAX_MECHANICAL_FINDINGS_BYTES });
  } catch (e: any) {
    if (e instanceof FileNotFoundError || e?.code === 'ENOENT') {
      return _drop_mechanical_findings(aid, 'sidecar_missing');
    }
    if (e instanceof PyValueError) {
      return _drop_mechanical_findings(aid, 'oversized', { trace: true });
    }
    return _drop_mechanical_findings(aid, 'unreadable', { trace: true });
  }
  let sidecar: any;
  try {
    sidecar = JSON.parse(payload.toString('utf-8'));
  } catch {
    return _drop_mechanical_findings(aid, 'json_invalid', { trace: true });
  }
  if (typeof sidecar !== "object" || sidecar === null || Array.isArray(sidecar)) {
    return _drop_mechanical_findings(aid, 'schema_mismatch');
  }
  if (sidecar['schema'] !== MECHANICAL_FINDINGS_SCHEMA) {
    return _drop_mechanical_findings(aid, 'schema_mismatch');
  }
  if (String(sidecar['autoid'] || '') !== aid) {
    return _drop_mechanical_findings(aid, 'autoid_mismatch');
  }
  if (String(sidecar['xlsx_sha256'] || '') !== credential_sha256) {
    return _drop_mechanical_findings(aid, 'xlsx_sha256_mismatch');
  }
  const rows = sidecar['findings'];
  if (!Array.isArray(rows)) {
    return _drop_mechanical_findings(aid, 'rows_invalid');
  }
  return rows.filter((row: any) => typeof row === "object" && row !== null && !Array.isArray(row));
}

export function recompile_comparison_fact(aid: string): Record<string, any> {
  const { EVENT, load_comparison } = require("../../case_compiler/recompile_comparison");
  const safe_aid = safe_output_component(aid, { field: 'autoid' });
  const [payload, _sha, status] = lint_credential_snapshot(safe_aid);
  if (status !== 'ok') {
    return { 'ev': EVENT, 'aid': safe_aid, 'status': 'unavailable', 'reason_code': 'current_credential_unavailable' };
  }
  const comparison = load_comparison(outputs_root().joinpath(safe_aid), { autoid: safe_aid, current: payload });
  const out: Record<string, any> = { 'ev': EVENT, 'aid': safe_aid };
  for (const [key, value] of Object.entries(comparison)) {
    if (key !== 'autoid') out[key] = value;
  }
  return out;
}

export function lint_credential_identity(aid: string): [string, string] {
  const [_payload, sha256, status] = lint_credential_snapshot(aid);
  return [sha256, status];
}

export function credential_stale(aid: string, cred_xlsx_mtime: any = null): boolean {
  void cred_xlsx_mtime;
  const [_sha256, status] = lint_credential_identity(aid);
  return status !== 'ok' && status !== 'case_missing';
}

export function artifact_fingerprint(aid: string): string {
  const [sha256, status] = lint_credential_identity(aid);
  if (status !== 'ok') {
    return '';
  }
  return `${aid}:${sha256}`;
}

export function volume_fingerprint(pairs: [string, string][]): string {
  const blob = JSON.stringify([...pairs].sort((a, b) => JSON.stringify(a) < JSON.stringify(b) ? -1 : 1));
  return sha1Hex(Buffer.from(blob, 'utf8')).slice(0, 16);
}

export function echo_fingerprint(payload: Record<string, any>): string {
  const blob = pyJsonDumps(payload, { ensure_ascii: false, sort_keys: true });
  return sha1Hex(Buffer.from(blob, 'utf8')).slice(0, 12);
}

export function emit(text: string): void {
  try {
    const { get_default_bus } = require("../events");
    get_default_bus().emit('evidence_added', { payload: { 'text': `[engine] ${text}` } });
  } catch {
    logger.debug('engine 进度 emit 失败');
  }
}

function _footer_bucket_counts(c: Record<string, any>): Record<string, any> {
  return { 'pending': c['pending'] || 0, 'dispatched': c['composed'] || 0, 'produced': (c['authored'] || 0) + (c['subset_verified'] || 0), 'pending_decision': (c['awaiting_user'] || 0) + (c['suspended'] || 0), 'awaiting_user': 0, 'passed': c['deliverable'] || 0, 'quarantined': c['quarantined'] || 0, 'failed_active': (c['failed'] || 0) + (c['contradicted'] || 0) + (c['broken'] || 0) + (c['broken_errored'] || 0) + (c['broken_aborted'] || 0) + (c['broken_verdict_unrecognized'] || 0), 'broken': c['broken_blocked'] || 0, 'failed_terminal': (c['failed_terminal'] || 0) + (c['unsupported_feature'] || 0), 'escalated': c['escalated'] || 0 };
}

export function emit_recompose_progress(run: string, stage: string, fields: Record<string, any> = {}): void {
  try {
    const { _fork_emit_event } = require("../skills/loader");
    _fork_emit_event({ 'event': 'recompose_progress', 'run': String(run || ''), 'stage': String(stage || ''), ...fields });
  } catch {
    logger.debug('recompose progress emit 失败');
  }
}

const _NETWORK_PAUSE_SLICE_S = 5.0;
const _NETWORK_PAUSE_ANNOUNCED: Map<number, boolean> = new Map();

function _network_outage_deadline_s(): number {
  try {
    const { network_persistent_deadline_s } = require("../agents/_llm");
    return Number(network_persistent_deadline_s());
  } catch {
    return 1800.0;
  }
}

function _all_in_flight_forks_are_waiting(gauge: Record<string, any>): boolean {
  const waiting = Math.trunc(Number(gauge['waiting_forks']) || 0);
  const in_flight = Math.trunc(Number(gauge['in_flight_forks']) || 0);
  return waiting > 0 && waiting >= in_flight;
}

export async function await_network_recovery(state: Record<string, any>, opts: { phase?: string; cancelled?: (() => boolean) | null } = {}): Promise<number> {
  const phase = opts.phase ?? 'author';
  const cancelled = opts.cancelled ?? null;
  const { NETWORK_OUTAGE_MINUTE_FLOOR_S, network_outage_card_cn } = require("../display_lexicon");
  const { network_outage_state } = require("../skills/loader");
  let gauge = network_outage_state();
  if (!_all_in_flight_forks_are_waiting(gauge)) {
    if ((gauge['since'] === null || gauge['since'] === undefined) && _NETWORK_PAUSE_ANNOUNCED.size) {
      _NETWORK_PAUSE_ANNOUNCED.clear();
    }
    return 0.0;
  }
  const since = gauge['since'] ?? Date.now() / 1000;
  let since_monotonic = gauge['since_monotonic'];
  if (since_monotonic === null || since_monotonic === undefined) {
    since_monotonic = performance.now() / 1000;
  }
  const deadline = _network_outage_deadline_s();
  let announced = false;
  if (!_NETWORK_PAUSE_ANNOUNCED.get(Number(since))) {
    _NETWORK_PAUSE_ANNOUNCED.set(Number(since), true);
    announced = true;
  }
  if (announced) {
    try {
      emit_tick(state, phase, null, { network_outage: { 'since': Number(since), 'waiting_forks': Math.trunc(Number(gauge['waiting_forks']) || 0) } });
      emit(network_outage_card_cn(performance.now() / 1000 - Number(since_monotonic)));
    } catch {
      logger.debug('断网播报失败');
    }
  }
  const started = performance.now() / 1000;
  let recovered = false;
  for (;;) {
    gauge = network_outage_state();
    if (!_all_in_flight_forks_are_waiting(gauge)) {
      recovered = true;
      break;
    }
    if (performance.now() / 1000 - Number(since_monotonic) >= deadline) {
      break;
    }
    if (typeof cancelled === "function" && cancelled()) {
      break;
    }
    await new Promise((r) => setTimeout(r, _NETWORK_PAUSE_SLICE_S * 1000));
  }
  const waited = performance.now() / 1000 - started;
  const outage_total = performance.now() / 1000 - Number(since_monotonic);
  if (announced) {
    try {
      emit_tick(state, phase, null, { network_outage: {} });
      if (outage_total >= NETWORK_OUTAGE_MINUTE_FLOOR_S) {
        append(state, [{ 'ev': 'network_outage', 'aid': '', 'since': Number(since), 'waited_s': Math.round(outage_total * 10) / 10, 'waiting_forks': Math.trunc(Number(gauge['waiting_forks']) || 0), 'run_id': `network_outage:${Math.floor(Number(since))}` }]);
      }
    } catch {
      logger.debug('断网恢复播报失败');
    }
    if (recovered) {
      _NETWORK_PAUSE_ANNOUNCED.delete(Number(since));
    }
  }
  return waited;
}

export function emit_dispatch_progress(run: string, opts: { current: number; total: number }): void {
  try {
    const { _fork_emit_event } = require("../skills/loader");
    _fork_emit_event({ 'event': 'dispatch_progress', 'run': String(run || ''), 'stage': 'brief_built', 'current': Math.trunc(opts.current), 'total': Math.trunc(opts.total) });
  } catch {
    logger.debug('dispatch progress emit 失败');
  }
}

export const PREFLIGHT_HEARTBEAT_S = 30.0;
const _PREFLIGHT_HEARTBEAT_POLL_S = 5.0;

export function emit_preflight_progress(run: string, opts: { index: number; total: number; env?: string; detail?: string; elapsed_s?: number; status?: string }): void {
  const { index, total, env = '', detail = '', elapsed_s = 0.0, status = 'running' } = opts;
  try {
    const { PREFLIGHT_PROGRESS_LABEL, PREFLIGHT_PROGRESS_UNIT } = require("../display_lexicon");
    const { _fork_emit_event } = require("../skills/loader");
    _fork_emit_event({ 'event': 'progress', 'key': `preflight:${run}`, 'phase': PREFLIGHT_PROGRESS_LABEL, 'unit': PREFLIGHT_PROGRESS_UNIT, 'env': String(env || ''), 'case_idx': Math.trunc(index), 'n_cases': Math.trunc(total), 'detail': String(detail || ''), 'elapsed_s': Math.trunc(elapsed_s), 'status': String(status || 'running') });
  } catch {
    logger.debug('上机前环境检查进度 emit 失败');
  }
}

export class PreflightProgressBeacon {
  private _run: string;
  private _env: string;
  private _started: number;
  private _item: Record<string, any> | null = null;
  private _closed = false;
  private _timer: ReturnType<typeof setInterval> | null = null;

  constructor(run: string, opts: { env?: string; started?: number | null } = {}) {
    this._run = String(run || '');
    this._env = String(opts.env || '');
    this._started = opts.started !== null && opts.started !== undefined ? Number(opts.started) : Date.now() / 1000;
    this._timer = setInterval(() => this._beat(), _PREFLIGHT_HEARTBEAT_POLL_S * 1000);
    if (this._timer.unref) this._timer.unref();
  }

  begin(opts: { total: number }): void {
    try {
      this._mark({ index: 0, total: Math.trunc(opts.total || 0), detail: '' });
    } catch {
      logger.debug('上机前环境检查起跑事件失败');
    }
  }

  probe(opts: { index: number; total: number; target_device?: string; show_head?: string; show_command?: string; retry?: boolean }): void {
    const { index, total, target_device = '', show_head = '', show_command = '', retry = false } = opts;
    try {
      const { PREFLIGHT_RETRY_SUFFIX } = require("../display_lexicon");
      const command = String(show_command || '') || String(show_head || '');
      let detail = [String(target_device || ''), command].filter((part) => part).join(' ');
      if (retry) {
        detail = detail ? `${detail} · ${PREFLIGHT_RETRY_SUFFIX}` : PREFLIGHT_RETRY_SUFFIX;
      }
      this._mark({ index: Math.trunc(index || 0), total: Math.trunc(total || 0), detail });
    } catch {
      logger.debug('上机前环境检查逐项事件失败');
    }
  }

  finish(opts: { status?: string; detail?: string } = {}): void {
    const { status = 'done', detail = '' } = opts;
    try {
      const item = { ...(this._item || {}) };
      this._item = null;
      const total = Math.trunc(Number(item['total']) || 0);
      emit_preflight_progress(this._run, { index: total, total, env: this._env, detail: String(detail || ''), elapsed_s: this._elapsed(), status: String(status || 'done') });
    } catch {
      logger.debug('上机前环境检查收尾事件失败');
    }
  }

  close(): void {
    try {
      this._closed = true;
      if (this._timer !== null) {
        clearInterval(this._timer);
        this._timer = null;
      }
    } catch {
      logger.debug('上机前环境检查心跳落闸失败');
    }
  }

  private _elapsed(): number {
    return Math.max(0.0, Date.now() / 1000 - this._started);
  }

  private _mark(opts: { index: number; total: number; detail: string }): void {
    const { index, total, detail } = opts;
    const now = Date.now() / 1000;
    this._item = { 'index': index, 'total': total, 'detail': detail, 'since': now, 'last_emit': now };
    emit_preflight_progress(this._run, { index, total, env: this._env, detail, elapsed_s: this._elapsed(), status: 'running' });
  }

  private _beat(): void {
    if (this._closed) {
      return;
    }
    const now = Date.now() / 1000;
    const item = { ...(this._item || {}) };
    const due = !!Object.keys(item).length && (now - (Number(item['since']) || now) >= PREFLIGHT_HEARTBEAT_S && now - (Number(item['last_emit']) || now) >= PREFLIGHT_HEARTBEAT_S);
    if (!due) {
      return;
    }
    this._item = { ...item, 'last_emit': now };
    emit_preflight_progress(this._run, { index: Math.trunc(Number(item['index']) || 0), total: Math.trunc(Number(item['total']) || 0), env: this._env, detail: String(item['detail'] || ''), elapsed_s: this._elapsed(), status: 'running' });
  }
}

export function emit_tick(state: Record<string, any>, phase: string, fs_: Record<string, any>[] | null = null, opts: { blocked?: Record<string, any> | null; common_cause?: Record<string, any> | null; network_outage?: Record<string, any> | null } = {}): void {
  const { blocked = null, common_cause = null, network_outage = null } = opts;
  try {
    const { _fork_emit_event } = require("../skills/loader");
    const vw = view(state, fs_);
    const rec: Record<string, any> = { 'event': 'engine_tick', 'run': String(state['out_name'] || 'engine'), 'phase': phase, 'round': Math.trunc(Number(state['vol_seq']) || 0), 'wave': 0, 'counts': _footer_bucket_counts(vw['counts']), 'total': Object.keys(vw['cases']).length };
    if (typeof blocked === "object" && blocked !== null && !Array.isArray(blocked) && Object.keys(blocked).length) {
      rec['blocked'] = { ...blocked };
    }
    if (typeof common_cause === "object" && common_cause !== null && !Array.isArray(common_cause) && Object.keys(common_cause).length) {
      rec['common_cause'] = { ...common_cause };
    }
    if (network_outage !== null) {
      rec['network_outage'] = (typeof network_outage === "object" && !Array.isArray(network_outage)) ? { ...network_outage } : {};
    }
    const notices = engine_card_notices(state);
    if (notices.length) {
      rec['notices'] = notices;
    }
    _fork_emit_event(rec);
  } catch {
    logger.debug('engine tick emit 失败');
  }
}

const _THINKING_BASELINE: Map<string, Set<string>> = new Map();

export function thinking_degraded_models(state: Record<string, any> | null = null): string[] {
  let current: Set<string>;
  try {
    const { thinking_rejections } = require("../agents/_llm");
    current = new Set(thinking_rejections());
  } catch {
    logger.debug('思考模式降级台账读取失败');
    return [];
  }
  if (state === null || state === undefined) {
    return [...current].sort();
  }
  const key = String((state || {})['out_name'] || 'engine');
  if (!_THINKING_BASELINE.has(key)) {
    _THINKING_BASELINE.set(key, current);
  }
  const baseline = _THINKING_BASELINE.get(key)!;
  return [...current].filter((x) => !baseline.has(x)).sort();
}

export function thinking_degraded_notice_cn(model: string): string {
  return `模型 ${model} 不支持思考模式，本批已改按普通模式编写`;
}

export function engine_card_notices(state: Record<string, any> | null = null): string[] {
  return thinking_degraded_models(state).map((name) => thinking_degraded_notice_cn(name));
}

function _emit_engine_item(fields: Record<string, any>): void {
  try {
    const { _fork_emit_event } = require("../skills/loader");
    _fork_emit_event({ 'event': 'engine_item', ...fields });
  } catch {
    logger.debug('engine item emit 失败');
  }
}

export function engine_item_span<T>(state: Record<string, any>, phase: string, item: string, opts: { index: number; total: number; operation?: string }, fn: () => T): T {
  const { index, total, operation = 'case' } = opts;
  const span_id = `engine-item:${crypto.randomBytes(16).toString('hex')}`;
  const run = String(state['out_name'] || 'engine');
  const started = performance.now() / 1000;
  const common = { 'run': run, 'phase': String(phase || ''), 'operation': String(operation || 'case'), 'span_id': span_id, 'item': String(item || ''), 'index': Math.trunc(index), 'total': Math.trunc(total) };
  _emit_engine_item({ 'edge': 'start', ...common });
  let outcome = 'ok';
  let error_type = '';
  try {
    return fn();
  } catch (exc: any) {
    outcome = 'error';
    error_type = exc?.constructor?.name ?? 'Error';
    throw exc;
  } finally {
    _emit_engine_item({ 'edge': 'end', 'outcome': outcome, 'error_type': error_type, 'elapsed_s': Math.max(0.0, performance.now() / 1000 - started), ...common });
  }
}

export function* observe_engine_items(state: Record<string, any>, phase: string, items: Iterable<any>, opts: { item_key: (item: any) => string; operation?: string }): Generator<any> {
  const { item_key, operation = 'case' } = opts;
  const frozen = Array.from(items);
  const total = frozen.length;
  for (let index = 0; index < frozen.length; index++) {
    const item = frozen[index];
    const key = String(item_key(item) || '');
    if (phase !== 'closing') {
      const EQ = require("./engine_quarantine");
      const ledger = load_facts(state);
      if (EQ.batch_halted(ledger) || EQ.quarantined_aids(ledger).has(key)) {
        continue;
      }
    }
    yield engine_item_span(state, phase, key, { index: index + 1, total, operation }, () => item);
  }
}

export function fork_executor(): any {
  const { ForkExecutor } = require("../resilience");
  return new ForkExecutor({ wallclock_s: fork_wallclock_s() });
}

export function fork_wallclock_s(): number {
  const override = process.env['IST_FORK_WALLCLOCK_S'];
  if (override) {
    try {
      return Number(override);
    } catch {}
  }
  return Math.min(fork_turn_budget() * fork_stall_after_s(), 7 * 24 * 3600.0);
}

export function fork_stall_after_s(): number {
  const base = 10.0 * fork_seconds_per_turn();
  const override = process.env['IST_FORK_WALLCLOCK_S'];
  if (override) {
    const n = Number(override);
    if (!Number.isNaN(n)) {
      return Math.min(base, n);
    }
  }
  return base;
}

const _DEFAULT_TURN_BUDGET = 200;

export function fork_turn_budget(): number {
  let default_budget: number;
  try {
    const { _DEFAULT_FORK_RECURSION_LIMIT } = require("../skills/loader");
    default_budget = Math.trunc(Number(_DEFAULT_FORK_RECURSION_LIMIT));
  } catch {
    default_budget = _DEFAULT_TURN_BUDGET;
  }
  try {
    const v = Math.trunc(Number(process.env['IST_FORK_RECURSION_LIMIT'] || default_budget));
    if (Number.isNaN(v)) return default_budget;
    return Math.max(1, v);
  } catch {
    return default_budget;
  }
}

export function fork_seconds_per_turn(): number {
  try {
    const v = Number(process.env['IST_LLM_STALL_TIMEOUT'] || 180.0);
    if (Number.isNaN(v)) return 180.0;
    return Math.max(1.0, v);
  } catch {
    return 180.0;
  }
}

export function env_flag(name: string, default_value: string = '1'): boolean {
  const v = String(process.env[name] || default_value).trim().toLowerCase();
  return !['0', 'false', 'no'].includes(v);
}

export function read_json(path: P, default_value: any = null): any {
  try {
    return JSON.parse(path.read_text('utf-8'));
  } catch {
    return default_value;
  }
}

export class LedgerCorruptError extends Error {
  path: string;
  detail: string;
  constructor(path: string, detail: string) {
    super(`${path}: ${detail}`);
    this.path = path;
    this.detail = detail;
  }
}

export function read_json_checked(path: P, default_value: any = null): any {
  let text: string;
  try {
    text = path.read_text('utf-8');
  } catch (e: any) {
    if (e instanceof FileNotFoundError || e?.code === 'ENOENT') {
      return default_value;
    }
    if (e instanceof IsADirectoryError || e?.code === 'EISDIR') {
      return default_value;
    }
    throw new LedgerCorruptError(path.toString(), `${e?.constructor?.name ?? 'Error'}: ${e?.message ?? e}`);
  }
  try {
    return JSON.parse(text);
  } catch (e: any) {
    throw new LedgerCorruptError(path.toString(), `${e?.constructor?.name ?? 'Error'}: ${e?.message ?? e}`);
  }
}

export function signal(name: string, subject: string, payload: Record<string, any> = {}): void {
  try {
    const { emit_signal } = require("../memory/footprint/signals");
    emit_signal(name, subject, { source: 'engine_v8', ...payload });
  } catch {}
}

export function record_first_seen(name: string, subject: string, payload: Record<string, any> = {}): string {
  try {
    const { record_first_seen: _rfs } = require("../memory/footprint/signals");
    return _rfs(name, subject, { source: 'engine_v8', ...payload });
  } catch {
    return 'write_failed';
  }
}

export function subtype_first_seen_report(): Record<string, any>[] {
  let recs: Record<string, any>[];
  try {
    const SIG = require("../memory/footprint/signals");
    recs = SIG.read_signals({ signal: 'subtype_first_seen' });
  } catch {
    recs = [];
  }
  const first_by_subject: Record<string, Record<string, any>> = {};
  for (const r of recs) {
    const subj = String(r['subject'] || '');
    if (subj && !(subj in first_by_subject)) {
      first_by_subject[subj] = r;
    }
  }
  const labels = Object.keys(V as any).filter((k) => k.startsWith('S_BROKEN') && typeof (V as any)[k] === "string").map((k) => (V as any)[k]).sort();
  const out: Record<string, any>[] = [];
  for (const label of labels) {
    const hit = first_by_subject[label];
    if (hit) {
      const ts = hit['ts'];
      let when = '?';
      if (typeof ts === "number") {
        const d = new Date(ts * 1000);
        const pad = (n: number) => String(n).padStart(2, '0');
        when = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
      }
      const batch = String(hit['batch'] || '?');
      out.push({ 'subtype': label, 'triggered': true, 'batch': batch, 'when': when, 'text': `已触发(首次批名 ${batch}/时刻 ${when})` });
    } else {
      out.push({ 'subtype': label, 'triggered': false, 'text': '自记账起点以来未触发' });
    }
  }
  return out;
}

export function verdict_unrecognized_batch_spread(): Record<string, string[]> {
  let recs: Record<string, any>[];
  try {
    const SIG = require("../memory/footprint/signals");
    recs = SIG.read_signals({ signal: 'verdict_unrecognized_seen' });
  } catch {
    recs = [];
  }
  const out: Record<string, string[]> = {};
  for (const r of recs) {
    const rv = String(r['subject'] || '');
    const b = String(r['batch'] || '');
    if (!rv || !b) {
      continue;
    }
    if (!out[rv]) out[rv] = [];
    if (!out[rv].includes(b)) {
      out[rv].push(b);
    }
  }
  return out;
}
