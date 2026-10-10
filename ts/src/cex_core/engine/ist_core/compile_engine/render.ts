// 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/render.py（sha256 a8cf9e5655593691）。不在这里手改。
import { deepcopy, PyValueError } from "../../_py";
import { is_runtime_infrastructure_terminal_fact } from "./execution_failure";
import {
  ATTRIBUTION_EVIDENCE_REACQUISITION_CN,
  AUTHORING_EVIDENCE_UNCLOSED_CN,
  GOVERNANCE_END_UNCLOSED_CN,
  EXECUTION_CAUSE_UNCONFIRMED_CN,
  AUTHORITY_DECISION_BLOCKED_CN,
  AUTHORITY_UNVERIFIED_BLOCKED_CN,
  UNATTRIBUTED_AUTHORING_STOP_CN,
  UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN,
  unproven_stop_cause_cn,
  DELIVERY_INCOMPLETE_REASON_CN as _DELIVERY_INCOMPLETE_REASON_CN,
  PREFLIGHT_ATLAS_GAP_NOUN_CN,
  PREFLIGHT_CONFIG_NOUN_CN,
  PREFLIGHT_RESIDUAL_NOUN_CN,
  PREFLIGHT_PROGRESS_LABEL,
  preflight_head_line_cn,
} from "../display_lexicon";

export const STATUS_CN: Record<string, string> = { 'quarantined': '引擎缺陷隔离（待修复验证）', 'deliverable': '验证通过', 'subset_verified': '单独验证通过(待整卷复验)', 'authored': '已编写(未上机)', 'failed': '上机未通过', 'contradicted': '单独能过、整卷复验会挂(用例间相互干扰)', 'failed_terminal': '按裁决收尾(未通过卷)', 'escalated': '引擎机械分流中', 'awaiting_user': '等待你的决定', 'suspended': '挂起(下批继续)', 'unsupported_feature': '当前设备不支持所需能力(共探确认)', 'pending': '未开始', 'composed': '已写好用例规格(excel 尚未生成)', 'delivery_blocked': '验证通过但卷面缺案尾清理——暂不交付(重编补自清后可交付)', 'broken': '未跑成(执行中断/日志陈腐/级联受害)——结论无效', 'broken_errored': '未跑成·断言/命令写坏了(断言被设备实际回显反证,或命令执行失败)——原样复跑必再错', 'broken_blocked': '未跑成·设备不可达(ping 不通)——复跑救不了死设备,需恢复环境后继续', 'broken_aborted': '未跑成·测试框架自身崩溃(非用例、非设备问题)', 'broken_verdict_unrecognized': '未跑成·框架返回了认不出的裁决值(非用例、非设备问题,可能是框架版本变化)' };
export const CTX_CN: Record<string, string> = { 'delivery': '整卷连跑复验', 'subset': '单独验证' };
const LAYER_CN: Record<string, string> = { 'G': '设备拒绝了命令(语法/能力)', 'E': '环境/测试设备问题', 'V': '用例断言或验证机制问题', 'transient': '疑似偶发波动', 'dispatch': '引擎把验证命令发到了错误通道', 'product_defect': '疑似产品缺陷', 'user': '用户裁决', 'engine': '引擎自动判定(非设备实测结论)' };
const DISP_CN: Record<string, string> = { 'reflow': '带反馈重新编写', 'frozen': '原方法已证无效,换法重编', 'env_blocked': '按环境阻塞收尾', 'defect_candidate': '疑似产品缺陷，保留证据待核', 'fixed': '已修复待复跑', 'rerun_isolated': '保留当前卷面复跑核验', 'ist_core_defect': 'IST-Core 派发通道缺陷(修复后可重入)', 'user_stop': '按你的裁决停止(未通过如实报告)', 'engineering_fault': '工程故障(引擎缺口,已呈报,非产品缺陷)', 'expectation_suspect': '预期值可疑(需核对出处)', 'transient': '疑似偶发波动' };
const _ESC_SUBCLASS_CN: Record<string, string> = { 'no_output': '本轮编写未产出(可能撞到并发或墙钟限制)', 'not_executed': '连续多轮未能在设备上跑成', 'no_ledger_channel': '编写侧的终态声明没走对应的结构化落账(引擎已先自行重试一次)', 'harness_fault': '测试框架自身在收集/初始化阶段崩溃(非用例、非设备)', 'verdict_unrecognized': '框架返回了不在认识范围内的裁决值(非用例、非设备)', 'worker_envelope_invalid': '编写侧没有交回引擎认得的结果信封(非用例、非设备)' };
const _ESC_ROUTE_CN: Record<string, string> = { 'no_output': '重编', 'not_executed': '设备已处理复跑' };
const SHAPE_CN: Record<string, string> = { 'manual_vs_device': '手册与实机不符', 'expected_vs_observed': '预期结果与上机行为不符', 'method_vs_implementation': '验证方法与功能实现不符', 'ordering_vs_persistence': '执行顺序与持久化状态互扰', 'other': '意图记载有差异' };
const ACTION_CN: Record<string, string> = { 'self_cleanup': '让这个用例结束时清理自己留下的持久产物', 'recompile_directed': '按已找到的方向重新编写', 'rerun_isolated': '不改卷面,单独复跑对照确认', 'vary_form': '换一种配置形态实现同一意图(坐实/排除产品缺陷)' };
const _DEFECT_DISPATCH = 'dispatch_channel';
const _DEFECT_ON_DEVICE = 'on_device_attempts';
const _DEFECT_ENGINE_ARTIFACT = 'engine_artifact';
const _DEFECT_AUTHORING_EVIDENCE = 'authoring_evidence';
const _DEFECT_ARTIFACT_CN: Record<string, string> = { 'final_volume_identity_failed': '最终交付卷的身份自检没通过', 'final_volume_authority_unverified': '最终交付卷的来源权威链没核验完成', 'final_volume_missing': '最终交付卷不在盘上', 'case_absent_from_final_volume': '本案不在最终交付卷里', 'case_state_outside_v12_terminal_graph': '本案停在终态图之外的状态上', 'engine_budget_exhausted_turn_budget': '编写这一案时引擎自己的轮次预算先用尽（与用例内容无关）', 'engine_budget_exhausted_wallclock': '编写这一案时引擎自己的时间预算先用尽（与用例内容无关）' };

function _isDict(v: any): v is Record<string, any> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function _strictInt(v: any): number | null {
  if (typeof v === "boolean") return null;
  if (typeof v === "number") return Number.isFinite(v) ? Math.trunc(v) : null;
  if (typeof v === "string" && /^[+-]?\d+$/.test(v.trim())) return parseInt(v.trim(), 10);
  return null;
}

function _execution_cause_unconfirmed(fact: Record<string, any>): boolean {
  const { FailureCategory } = require("./execution_failure");
  return fact['ev'] === 'ist_core_defect' && _strictInt(fact['attempt']) !== null && fact['category'] === FailureCategory.UNKNOWN;
}

function _is_unattributed_stop(fact: Record<string, any>): boolean {
  const { is_unattributed_authoring_stop } = require("./authoring_stops");
  return is_unattributed_authoring_stop(fact);
}

function _unattributed_stop_state_cn(fact: Record<string, any>): string {
  const { is_contradiction_stop } = require("./contradiction_stop");
  if (is_contradiction_stop(fact)) {
    const { reason_cn } = require("./forced_closure");
    return reason_cn(fact);
  }
  return `${UNATTRIBUTED_AUTHORING_STOP_CN}。账上记的停止成因：${unproven_stop_cause_cn(fact['stop_cause'])}。`;
}

function _defect_family(fact: Record<string, any>): string {
  if (fact['reason_code'] === 'authoring_evidence_unclosed') {
    return _DEFECT_AUTHORING_EVIDENCE;
  }
  if (String(fact['reason_code'] || '') === 'dispatch_channel_misroute') {
    return _DEFECT_DISPATCH;
  }
  if (_strictInt(fact['attempt']) !== null && fact['category']) {
    return _DEFECT_ON_DEVICE;
  }
  return _DEFECT_ENGINE_ARTIFACT;
}

function _authority_chain_error_text(fact: Record<string, any>, facts: Record<string, any>[] | null): string {
  const _TO = require("./terminal_outcomes");
  const rows = (facts || []).filter((row) => _isDict(row));
  const aid = String(fact['aid'] || '');
  if (!aid || !rows.length) {
    return '';
  }
  const volume = [...rows].reverse().find((row) => String(row['aid'] || '') === aid && _TO.FINAL_VOLUME_FAILURE_EVENTS.includes(row['ev'])) || {};
  const prefixes = new Set((volume['reasons'] || []).map((item: any) => String(item || '').split(':')[0]).filter((s: string) => s));
  const artifact = String(volume['expected_artifact_sha256'] || '');
  if (!prefixes.size || !artifact) {
    return '';
  }
  const match = [...rows].reverse().find((row) => String(row['aid'] || '') === aid && row['ev'] === 'authority_reconcile_failed' && prefixes.has(String(row['reason_code'] || '')) && String(row['artifact_sha256'] || '') === artifact) || {};
  return String(match['error_text'] || '').trim();
}

function _defect_artifact_cause_cn(fact: Record<string, any>, facts: Record<string, any>[] | null = null): string {
  const FC = require("./forced_closure");
  const reason_code = String(fact['reason_code'] || '');
  if (reason_code === 'governance_end_unclosed') {
    return GOVERNANCE_END_UNCLOSED_CN;
  }
  if (FC.FORCED_CLOSURE_DISPLAY_REASONS.includes(reason_code)) {
    return FC.reason_cn(fact);
  }
  if (reason_code.startsWith('engine_error_')) {
    const _EE = require("./engine_errors");
    const title = _EE.CODE_TITLE_CN[reason_code.slice('engine_error_'.length)] || '';
    if (title) {
      return title;
    }
  }
  const _TOC = require("./terminal_outcomes");
  if (_TOC.FINAL_VOLUME_FAILURE_EVENTS.includes(reason_code) && String(fact['failure_axis'] || '') === _TOC.AUTHORITY_CHAIN_AXIS) {
    const _cause = '收口来源权威链未核验完成，卷面身份及具体责任仍待核实';
    const _first = _authority_chain_error_text(fact, facts);
    return _first ? `${_cause}；未核成的环节留证：${_ellip(_first, 240)}` : _cause;
  }
  return _DEFECT_ARTIFACT_CN[reason_code] ?? '引擎自有产物没过引擎自己的检查';
}

function _is_env_engine_error_terminal(fact: Record<string, any>): boolean {
  const _EE = require("./engine_errors");
  return String(fact['reason_code'] || '') === `engine_error_${_EE.E_ENVIRONMENT}`;
}

function _is_contract_engine_error_terminal(fact: Record<string, any>): boolean {
  const _EE = require("./engine_errors");
  return String(fact['reason_code'] || '') === `engine_error_${_EE.E_CONTRACT_STAMP}`;
}

function _is_worker_timeout_engine_error_terminal(fact: Record<string, any>): boolean {
  const _EE = require("./engine_errors");
  return String(fact['reason_code'] || '') === `engine_error_${_EE.E_WORKER_TIMEOUT}`;
}

function _api_engine_error_terminal_code(fact: Record<string, any>): string {
  const _EE = require("./engine_errors");
  const reason_code = String(fact['reason_code'] || '');
  const prefix = 'engine_error_';
  if (!reason_code.startsWith(prefix)) {
    return '';
  }
  const code = reason_code.slice(prefix.length);
  return _EE.API_SIDE_CODES.has(code) ? code : '';
}

const _API_OWNER_ACTION_CN: Record<string, string> = { '0016': '核对API接口的原始配额响应及对应账户限制，按已确认条件恢复调用。', '0017': '核对API接口的失败与重试记录，恢复条件满足后重试。', '0018': '核对API接口拒绝的原始请求和响应，按证据修正调用条件。', '0019': '核对API接口返回的身份、权限或用量限制，按原始响应处理。' };
const _AUTHORING_CAUSE_CN: Record<string, string> = { 'verified_authoring_attempt_failure': '已核验的编写失败', 'submission_rejected': '交卷被拒', 'no_output': '编写孔无产出', 'device_result_case_side': '上机后归因在用例侧', 'compile_policy_exhausted': '有限规则策略耗尽', 'worker_claim_not_compilable': '编写侧主张不可编(未受理)' };

function _is_worker_claim_handoff_terminal(fact: Record<string, any>): boolean {
  const { AUTHORING_ROUTE_WORKER_CLAIM_HANDOFF } = require("./terminal_credentials");
  return String(fact['settlement_route'] || '') === AUTHORING_ROUTE_WORKER_CLAIM_HANDOFF;
}

function _authoring_causes_cn(fact: Record<string, any>): string {
  const counts: Record<string, number> = {};
  for (const row of fact['round_causes'] || []) {
    if (!_isDict(row)) {
      continue;
    }
    const cause = String(row['cause'] || '');
    counts[cause] = (counts[cause] || 0) + 1;
  }
  const parts = Object.entries(counts).map(([cause, n]) => `${_AUTHORING_CAUSE_CN[cause] ?? cause} ${n} 轮`);
  return parts.length ? parts.join('、') : '原因记录缺失';
}

function _execution_terminal_status_cn(fact: Record<string, any>, opts: { facts?: Record<string, any>[] | null } = {}): string {
  const facts = opts.facts ?? null;
  const { authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block } = require("./authority_delivery_policy");
  if (is_authority_block_terminal(fact)) {
    if (is_authority_unverified_block(fact)) {
      return AUTHORITY_UNVERIFIED_BLOCKED_CN;
    }
    return authority_decision_confirmed(fact, facts || []) ? AUTHORITY_DECISION_BLOCKED_CN : '来源待裁记录未核验';
  }
  if (_is_unattributed_stop(fact)) {
    const { is_contradiction_stop } = require("./contradiction_stop");
    if (is_contradiction_stop(fact)) {
      return '阻塞（判决矛盾本轮未消解）';
    }
    return UNATTRIBUTED_AUTHORING_STOP_CN;
  }
  const event = String(fact['ev'] || '');
  if (event === 'ist_core_defect' && fact['reason_code'] === 'governance_end_unclosed') {
    return GOVERNANCE_END_UNCLOSED_CN;
  }
  if (_execution_cause_unconfirmed(fact)) {
    return EXECUTION_CAUSE_UNCONFIRMED_CN;
  }
  if (is_runtime_infrastructure_terminal_fact(fact)) {
    return '阻塞(本轮执行基础设施未闭合)';
  }
  if (event === 'ist_core_defect') {
    const family = _defect_family(fact);
    if (family === _DEFECT_AUTHORING_EVIDENCE) {
      return AUTHORING_EVIDENCE_UNCLOSED_CN;
    }
    if (family === _DEFECT_DISPATCH) {
      return `IST-Core 缺陷(${DISP_CN['ist_core_defect']})`;
    }
    if (family === _DEFECT_ON_DEVICE) {
      return 'IST-Core 缺陷(同一执行身份三次仍未跑成)';
    }
    return `IST-Core 缺陷(${_defect_artifact_cause_cn(fact, facts)})`;
  }
  if (event === 'authoring_failure') {
    if (_is_worker_claim_handoff_terminal(fact)) {
      return '模型未找到解决方案(编写侧主张：不可编，未受理)';
    }
    return '模型未找到解决方案(编写轮次用尽，每一轮都败在编写侧)';
  }
  if (event === 'unable_to_compile' && fact['category'] === 'connection') {
    return '无法编写(平台限制：连续三次无法完成设备连接)';
  }
  if (event === 'unable_to_compile') {
    return '无法编写(设备前提不具备)';
  }
  return '';
}

function _active_execution_terminal(mine: Record<string, any>[], opts: { facts?: Record<string, any>[] | null } = {}): Record<string, any> {
  const _V = require("./views");
  return _V.active_execution_terminal(mine, { facts: opts.facts ?? null });
}

function _unverified_authority_record(mine: Record<string, any>[], facts: Record<string, any>[] | null): boolean {
  const { unverified_authority_pending } = require("./authority_delivery_policy");
  const rows = facts !== null ? facts : mine;
  let aid = '';
  for (let i = mine.length - 1; i >= 0; i--) {
    if (mine[i]['aid']) { aid = String(mine[i]['aid']); break; }
  }
  const merged = [...rows].reverse().find((row) => row['ev'] === 'merged' && row['ctx'] === 'delivery') || {};
  return unverified_authority_pending(rows, { aid, current_volume_sha256: String(merged['artifact_sha256'] || '') });
}

const _TS_PREFIX = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} +[\d.]+ +- +/;

export function clean_device_echo(text: string, limit: number = 0): string {
  const { scrub_text } = require("../security_scrub");
  const lines: string[] = [];
  let blank = false;
  for (let ln of scrub_text(text).split(/\r?\n/)) {
    ln = ln.replace(_TS_PREFIX, '').replace(/\s+$/, '');
    if (!ln) {
      if (blank) {
        continue;
      }
      blank = true;
    } else {
      blank = false;
    }
    lines.push(ln);
  }
  const out = lines.join('\n').trim();
  return limit > 0 ? out.slice(0, limit) : out;
}

function _ellip(s: string, n: number): string {
  s = String(s || '');
  return s.length <= n ? s : s.slice(0, n).replace(/\s+$/, '') + '…';
}

function _xml_precedent_note(card: Record<string, any>): string {
  const entry = (card['basis'] || []).find((item: any) => _isDict(item) && ['version_difference', 'xml_projection_anomaly'].includes(item['field']) && _isDict(item['details'])) ?? null;
  if (entry === null) {
    return '';
  }
  const details = entry['details'];
  const precedents = (details['precedents'] || []).filter((item: any) => _isDict(item) && item['build'] && item['oid']);
  if (!precedents.length) {
    return '';
  }
  const prior = precedents.map((item: any) => `${item['build']} 版本有 OID ${item['oid']} 的真机 PASS 编写`).join('、');
  const current = String(details['current_build'] || '?');
  const command = String(details['command'] || '');
  const nodes = (details['nearest_node_paths'] || []).map((value: any) => String(value)).join('、') || '无';
  let conclusion: string;
  if (entry['field'] === 'version_difference') {
    conclusion = '疑似版本变动，不归因命令书问题（除非 XML 注入错误）';
  } else {
    conclusion = '同 build 先例与 XML 自相矛盾，疑似 XML 注入或投影异常，不归因命令书问题';
  }
  return `${prior}；当前 build ${current} 的 XML 未收录命令「${command}」；可得邻近节点路径：${nodes}；${conclusion}。`;
}

function _scenario1_evidence_lines(mine: Record<string, any>[]): string[] {
  const fact = [...mine].reverse().find((item) => item['ev'] === 'policy_abandon' && item['reason_code'] === 'scenario1_spec_case_conflict' && Array.isArray(item['scenario1_evidence'])) ?? null;
  if (fact === null) {
    return [];
  }
  const records = (fact['scenario1_evidence'] || []).filter((item: any) => _isDict(item));
  const lines: string[] = [];
  for (let index = 0; index < records.length; index++) {
    const record = records[index];
    const spec_quote = String(record['spec_quote'] || '');
    const case_quote = String(record['case_quote'] || '');
    const spec_locator = String(record['spec_locator'] || '');
    const case_locator = String(record['case_locator'] || '');
    const incompatibility = String(record['incompatibility'] || '');
    if (!(spec_quote && case_quote && spec_locator && case_locator && incompatibility)) {
      continue;
    }
    if (records.length > 1) {
      lines.push(`- **规格书与用例原文对照 ${index + 1}**`);
    } else {
      lines.push('- **规格书与用例原文对照**');
    }
    lines.push('  - **SPEC 逐字引用**:');
    for (const part of spec_quote.split(/\r?\n/)) lines.push(`    > ${part}`);
    lines.push(`  - **SPEC 定位**:\`${spec_locator}\``);
    lines.push('  - **用例逐字引用**:');
    for (const part of case_quote.split(/\r?\n/)) lines.push(`    > ${part}`);
    lines.push(`  - **用例定位**:\`${case_locator}\``);
    lines.push('  - **不相容说明**:');
    for (const part of incompatibility.split(/\r?\n/)) lines.push(`    > ${part}`);
  }
  return lines;
}

function _scenario1_missing_fields_lines(mine: Record<string, any>[]): string[] {
  const fact = [...mine].reverse().find((item) => item['ev'] === 'policy_abandon' && item['reason_code'] === 'scenario1_case_incomplete') ?? null;
  if (fact === null) {
    return [];
  }
  const { MISSING_FIELD_CN: _FIELD_CN, missing_fields_text: _fields_text } = require("./questions");
  const fields = (fact['missing_fields'] || []).filter((field: any) => typeof field === "string" && field in _FIELD_CN);
  if (!fields.length) {
    return [];
  }
  return [`- **人工脑图缺项**:管辖规格书对这条人工脑图有表态，人工脑图缺少 ${_fields_text(fields)}；缺的是人工脑图本身，编译期补不上`];
}

function _decision_anchor(fact: Record<string, any>, ordinal: number | null = null): string {
  if ('round' in fact) {
    let round_no: number;
    try {
      round_no = Math.trunc(Number(fact['round'] || 0));
      if (Number.isNaN(round_no)) round_no = -1;
    } catch {
      round_no = -1;
    }
    if (round_no > 0) {
      return `第${round_no}轮`;
    }
    if (round_no === 0) {
      return '批前自动化环境状态确认';
    }
  }
  if (ordinal !== null && ordinal > 0) {
    return `本案事实序号${ordinal}`;
  }
  return '本案历史事实';
}

function _decision_display(fact: Record<string, any>, ordinal: number | null = null, limit: number = 80): string {
  const { DECISION_TOKEN_LABELS } = require("./questions");
  const raw = _ellip(String(fact['answer'] || '').trim(), limit);
  const token = String(fact['token'] || '').trim();
  const anchor = _decision_anchor(fact, ordinal);
  if (!!fact['freeform']) {
    return `${raw || '(自由输入为空)'}（${anchor}，自由输入，措辞可能已变）`;
  }
  if (token in DECISION_TOKEN_LABELS) {
    return DECISION_TOKEN_LABELS[token];
  }
  if (token) {
    return `该选项已退休（原文案:${raw || '(空)'}；${anchor}）`;
  }
  return `${raw || '(空)'}（${anchor}，历史记录未绑定选项，措辞可能已变）`;
}

function _decision_has_current_label(fact: Record<string, any>): boolean {
  const { DECISION_TOKEN_LABELS } = require("./questions");
  return !fact['freeform'] && String(fact['token'] || '') in DECISION_TOKEN_LABELS;
}

function _fact_ordinal(facts: Record<string, any>[], target: Record<string, any>): number | null {
  for (let idx = 0; idx < facts.length; idx++) {
    if (facts[idx] === target) {
      return idx + 1;
    }
  }
  for (let idx = 0; idx < facts.length; idx++) {
    if (JSON.stringify(facts[idx]) === JSON.stringify(target)) {
      return idx + 1;
    }
  }
  return null;
}

const _REVISION_HDR = /^#+\s*Revision\b.*$/gm;
const _RULING_HDR = /^#+\s*裁决\s*$/gm;

function _ruling_summary(ruling: string, limit: number = 120): string {
  const s = String(ruling || '').trim();
  if (!s) {
    return '';
  }
  let body = '';
  for (const seg of s.split(/^#+\s*Revision\b.*$/gm).reverse()) {
    let part = seg.replace(/^#+\s*裁决\s*$/gm, '');
    part = part.replace(/^#+\s*/gm, '').trim();
    if (part) {
      body = part;
      break;
    }
  }
  body = (body || s.replace(/^#+\s*裁决\s*$/gm, '')).replace(/\s+/g, ' ').trim();
  return body.length > limit ? body.slice(0, limit).replace(/\s+$/, '') + '…' : body;
}

function _replay_pending_question(mine: Record<string, any>[]): string {
  const shown = mine.filter((f) => f['ev'] === 'ask_shown' && f['render_input']);
  if (!shown.length) {
    return '';
  }
  const fact = shown[shown.length - 1];
  const render_input = fact['render_input'];
  if (!_isDict(render_input)) {
    return '';
  }
  let question: string;
  try {
    const { build_ask_question } = require("./questions");
    question = String(build_ask_question({ ...render_input })['question'] || '').trim();
  } catch {
    return '';
  }
  const autoid = String(fact['aid'] || '');
  if (!autoid || !question.includes(autoid) || question.includes('None')) {
    return '';
  }
  return question.replace(/\n/g, ' ');
}

function _is_no_answer_reason(reason: string): boolean {
  if (!String(reason).startsWith('auto:')) return false;
  const _sh = require('./_shared');
  const kind = String(reason).slice('auto:'.length).split(':')[0];
  return _sh.suspend_kind_renders_as_no_answer(kind);
}

export function case_timeline(mine: Record<string, any>[]): string[] {
  const out: string[] = [];
  for (let ordinal = 0; ordinal < mine.length; ordinal++) {
    const f = mine[ordinal];
    const ev = f['ev'];
    if (ev === 'authored') {
      const r = Math.trunc(Number(f['round'] || 0));
      out.push(`第 ${r} 次编写完成` + (r > 1 ? '(重新编写)' : ''));
    } else if (ev === 'verdict') {
      const ctx = CTX_CN[String(f['ctx'])] ?? String(f['ctx']);
      const res = String(f['result']);
      const word = ({ 'pass': '通过', 'fail': '未通过' } as Record<string, string>)[res] ?? '未跑成(结论无效)';
      out.push(`${ctx}:${word}`);
    } else if (ev === 'rollback') {
      out.push('此前的通过结论被复验推翻,已从先例知识库撤销');
    } else if (ev === 'verdict_recovered') {
      out.push('此前未通过的断言在同一卷面上转为通过(变好留痕)');
    } else if (ev === 'ask_panel') {
      out.push('发现意图记载差异,向你呈报');
    } else if (ev === 'adopted') {
      out.push('同一问题你此前已有裁决,直接沿用(免问)');
    } else if (ev === 'decision' && f['answer']) {
      if (String(f['provenance'] || '').startsWith('adopted:')) {
        continue;
      }
      const _r = f['round'];
      const _r_tag = _decision_has_current_label(f) && _r !== null && _r !== undefined && Math.trunc(Number(_r)) > 0 ? `(第${_r}轮)` : '';
      out.push(`你的裁决${_r_tag}:${_decision_display(f, ordinal + 1)}`);
    } else if (ev === 'suspended') {
      out.push(_is_no_answer_reason(String(f['reason'] || '')) ? '未作答,留待下批再问' : '挂起,留待下批继续');
      const _asked = _replay_pending_question(mine);
      if (_asked) {
        out.push(`当时问你的是:${_asked}`);
      }
    } else if (ev === 'resumed') {
      out.push('恢复处理');
    } else if (ev === 'delivery_blocked') {
      out.push('验证通过,但卷面缺案尾清理(会污染后续用例),暂不交付');
    }
  }
  return out;
}

function _latest_attribution(mine: Record<string, any>[]): Record<string, any> {
  const atts = mine.filter((f) => f['ev'] === 'attribution');
  return atts.length ? atts[atts.length - 1] : {};
}

export function on_defect_candidate_list(mine: Record<string, any>[]): boolean {
  return mine.some((fact) => fact['ev'] === 'attribution' && String(fact['disposition'] || '') === 'defect_candidate');
}

export function on_engine_delivery_action_list(mine: Record<string, any>[], opts: { facts?: Record<string, any>[] | null } = {}): boolean {
  const { active_execution_pause } = require("./views");
  const pause = active_execution_pause(mine);
  if (pause) {
    return pause['pause_kind'] !== 'contra' && pause['basis_status'] === 'source_unavailable';
  }
  const execution_terminal = _active_execution_terminal(mine, opts);
  if (is_runtime_infrastructure_terminal_fact(execution_terminal)) {
    return false;
  }
  if (String(execution_terminal['ev'] || '') === 'ist_core_defect') {
    return true;
  }
  if (mine.some((fact) => fact['ev'] === 'delivery_blocked')) {
    return true;
  }
  return String(_latest_attribution(mine)['disposition'] || '') === 'engineering_fault';
}

export function delivery_incomplete_why_cn(reasons: any): string {
  const parts = (reasons || []).filter((code: string) => code in _DELIVERY_INCOMPLETE_REASON_CN).map((code: string) => _DELIVERY_INCOMPLETE_REASON_CN[code]);
  return parts.join('、') || '本批的收口条件没有全部满足';
}

function _latest_semantic_attribution(mine: Record<string, any>[]): Record<string, any> {
  const F = require("./facts");
  const semantic = mine.filter((row) => row['ev'] !== 'attribution' || !(row['disposition'] === 'user_stop' || row['user_stop']));
  return F.current_attribution(semantic);
}

function _latest_panel_dict(mine: Record<string, any>[], read_json: (p: string) => any): Record<string, any> {
  const pf = mine.filter((f) => f['ev'] === 'ask_panel');
  if (!pf.length) {
    return {};
  }
  return read_json(String(pf[pf.length - 1]['ref'] || '')) || {};
}

const _NOT_FIXPOINT_REASON_CN: Record<string, string> = { 'hard_error': '本轮图状态为 error，该用例未走到定局（不要据此推断设备断连；以 facts.jsonl 里本轮最后一条 error/phase 为准）', 'attribution_projection_blocked': '框架归因投影的来源身份不可用或已漂移；请先同步 framework mirror，运行 scripts/gen_capability_atlas.py 重生成 capability_atlas/method_reference，再以同参数重试', 'attribution_evidence_reacquisition_required': ATTRIBUTION_EVIDENCE_REACQUISITION_CN, 'capped': '该用例的重编/复跑轮次已达上限,需要你的授权才能继续', 'command_domain_isolated': `该用例里有配置命令${PREFLIGHT_ATLAS_GAP_NOUN_CN}可核对,本轮被单独隔离、没有上机;它不影响同批其它用例交付。等这条查看命令补齐后,以同参数续跑即可自动恢复`, 'merge_blocked': '本轮组卷这一步被拦下,该用例没能进入上机卷', 'merge_rejected': '整卷合并被卷面规则拒绝,本轮没有可上机的卷,该用例因此没上机', 'contract_blocked': '本轮机械脑图无法读回，该用例未进入编写；修复后以同参数续跑', 'non_interactive': '本轮未对该用例采取进一步动作' };
const _UNKNOWN_NOT_FIXPOINT_REASON_CN = '引擎未能说明本轮未推进的原因(属引擎缺口,请报工程)';

function _latest_command_domain_exclusion(mine: Record<string, any>[]): Record<string, any> {
  let excluded: Record<string, any> = {};
  for (let i = mine.length - 1; i >= 0; i--) {
    if (mine[i]['ev'] === 'command_domain_case_excluded') {
      excluded = mine[i];
      break;
    }
  }
  if (!Object.keys(excluded).length) {
    return {};
  }
  const authored = mine.filter((f) => f['ev'] === 'authored');
  const current = String((authored.length ? authored[authored.length - 1] : {})['artifact'] || '');
  if (current && String(excluded['artifact'] || '') !== current) {
    return {};
  }
  return excluded;
}

export function command_domain_isolation_reason_cn(mine: Record<string, any>[]): string {
  const excluded = _latest_command_domain_exclusion(mine);
  if (String(excluded['reason_code'] || '') !== 'command_domain_residual') {
    return _NOT_FIXPOINT_REASON_CN['command_domain_isolated'];
  }
  const disclosure = String(excluded['disclosure'] || '').trim().replace(/。+$/, '');
  if (disclosure) {
    return disclosure;
  }
  return `${PREFLIGHT_RESIDUAL_NOUN_CN}该用例要动的配置命令的${PREFLIGHT_CONFIG_NOUN_CN}行,当前环境给不了它净态,本轮被单独隔离、没有上机;它不影响同批其它用例交付。环境具备条件后重编本案即自动复检`;
}

function _h_s0_polluter_cause(diag: Record<string, any>): string {
  const pol = (diag['polluters'] || []).filter((p: any) => _isDict(p)).map((p: any) => String(p['aid'] || '').slice(-6)).slice(0, 3);
  if (pol.length) {
    return `原记录列出前序用例(尾号 ${pol.join('、')})，但没有独立证实这些用例导致了本案失败。`;
  }
  return '记录未给出已独立核验的影响来源。';
}

function _execution_pause_narrative(mine: Record<string, any>[], pause: Record<string, any>): string {
  const kind = String(pause['pause_kind'] || '');
  if (pause['basis_status'] === 'source_unavailable') {
    return '当前未取得与本次暂挂绑定的依据，原因尚未确认。本轮暂挂，保留原始记录。';
  }
  if (['api', 'governance', 'supply'].includes(kind)) {
    return String(pause['reason'] || '编写条件尚未闭合，本轮暂挂。');
  }
  if (kind === 'bed') {
    const { _fact_sha256 } = require("./terminal_credentials");
    const source_sha = String(pause['source_fact_sha256'] || '');
    const diag = mine.find((fact) => source_sha && _fact_sha256(fact) === source_sha) || {};
    if (!Object.keys(diag).length || !String(diag['h_position'] || '').startsWith('h_s0')) {
      return '本次暂挂的环境依据未确认状态残留及其责任方，保留原始记录，待重新核验。';
    }
    return '本次绑定记录只提出前序状态影响假设。' + _h_s0_polluter_cause(diag) + '原暂挂记录保留；该假设不证明环境责任，也不能替代本案归因。';
  }
  if (kind === 'env') {
    return '现有记录提示本案受测试环境或执行条件阻碍。本轮暂挂，处理后同参续跑核验。';
  }
  if (kind === 'contra') {
    const { pause_narrative, pause_observations } = require("./contradiction_stop");
    return pause_narrative(pause_observations(pause, mine) || {}, { closing: false });
  }
  return String(pause['reason'] || '本轮暂挂，执行原因尚未闭合。');
}

export function _escalated_remedy_text(mine: Record<string, any>[]): string {
  const F = require("./facts");
  const aid = mine.length > 0 ? String(mine[0]['aid']) : '';
  const sub = F.escalated_subclass(mine, aid);
  const cause = _ESC_SUBCLASS_CN[sub] ?? '引擎侧遇到无法自行推进的情况';
  const deesc_decs = mine.filter((f) =>
    f['ev'] === 'decision' && String(f['question_id'] ?? '').startsWith(`deesc:${aid}:`) && String(f['answer'] ?? '').trim() && String(f['token'] ?? '') !== 'suspend'
  );
  if (deesc_decs.length === 0) {
    let opts: string;
    if (sub === 'no_ledger_channel') {
      opts = '重编/工程故障呈报/保持';
    } else if (sub === 'harness_fault') {
      opts = '工程故障呈报/保持';
    } else {
      opts = `${_ESC_ROUTE_CN[sub] ?? '重编'}/缺陷候选/保持`;
    }
    return `**去向**:${cause};引擎已呈报恢复问询(可选「${opts}」),答复后重跑同参数会按你的选择继续;未答复则重跑同参数会再次呈报。`;
  }
  const last = deesc_decs[deesc_decs.length - 1];
  if (String(last['token']) === 'deesc_keep') {
    const n = F.recovery_attempts(mine, aid);
    const tried = n ? `(此前已尝试恢复 ${n} 次)` : '';
    return `**去向**:${cause}${tried};你选择保持,本用例暂不再自动重试。重跑同参数会沿用这次的保持,除非换了测试设备或产品版本——那种情况下会再次问你是否恢复。`;
  }
  const _last_r = last['round'];
  const _last_tag = _decision_has_current_label(last) && _last_r !== null && _last_r !== undefined && Number(_last_r) > 0 ? `(第${_last_r}轮)` : '';
  const _last_display = _decision_display(last, _fact_ordinal(mine, last), 24);
  return `**去向**:${cause};已按你的裁决${_last_tag}「${_last_display}」处理,详见时间线。`;
}

export function _ledger_corrupt_type_cn(detail: string): string {
  const d = String(detail ?? '');
  if (d.startsWith('UnicodeDecodeError')) {
    return '文件编码损坏';
  }
  if (d.includes('JSONDecodeError')) {
    return 'JSON 格式损坏';
  }
  return '文件内容损坏';
}

export function _direct_abandon_class(mine: Record<string, any>[]): string {
  const BT = require("./blocking_taxonomy");
  const views = require("./views");
  let cls = String(views.direct_abandon_terminal(mine)['blocking_class'] ?? '');
  if (!cls) {
    const latest = [...mine].reverse().find((fact) =>
      fact['ev'] === 'policy_abandon' && ['no_cli_equivalent', 'environment_prerequisite_gap', 'author_definition_gap', 'batch_user_abandon'].includes(String(fact['reason_code'] ?? ''))
    ) ?? {};
    const expected_map: Record<string, string> = {
      'no_cli_equivalent': BT.A_NO_CLI_EQUIVALENT,
      'environment_prerequisite_gap': BT.A_ENV_PREREQ_GAP,
      'author_definition_gap': BT.A_AUTHOR_DEFINITION_GAP,
      'batch_user_abandon': BT.A_BATCH_USER_ABANDON,
    };
    const expected = expected_map[String(latest['reason_code'] ?? '')] ?? '';
    if (latest['blocking_class'] === expected) {
      cls = expected;
    }
  }
  return cls && BT.ABANDON_USER_ACTION_ZH[cls] ? cls : '';
}

export function _author_gap_variant(mine: Record<string, any>[], cls: string): string {
  const BT = require("./blocking_taxonomy");
  const TC = require("./terminal_credentials");
  if (String(cls ?? '') !== BT.A_AUTHOR_DEFINITION_GAP) {
    return '';
  }
  const aid = mine.find((row) => row['aid'])?.['aid'] ? String(mine.find((row) => row['aid'])?.['aid']) : '';
  return aid ? TC.author_gap_variant(aid, mine) : '';
}

export function _direct_abandon_remedy_text(mine: Record<string, any>[]): string | null {
  const BT = require("./blocking_taxonomy");
  const cls = _direct_abandon_class(mine);
  if (!cls) {
    return null;
  }
  const variant = _author_gap_variant(mine, cls);
  let text = '**去向**:' + BT.variant_text('reason', { cls, variant });
  if (cls === BT.A_NO_CLI_EQUIVALENT && mine.some((item) => item['ev'] === 'environment_execution_disclosure')) {
    return text + '本次不生成的原因是自动化环境不具备,不是用例或命令本身有问题——详见上方环境限制披露。';
  }
  if (cls === BT.A_AUTHOR_DEFINITION_GAP) {
    const latest = [...mine].reverse().find((fact) =>
      fact['ev'] === 'policy_abandon' && fact['blocking_class'] === BT.A_AUTHOR_DEFINITION_GAP
    ) ?? {};
    const declaration = String(latest['author_gap_declaration'] ?? '').trim();
    text += BT.variant_text('user_action', { cls, variant });
    if (declaration) {
      text += '\n\n**' + BT.variant_text('declaration_label', { variant }) + '**：' + declaration;
    }
    return text;
  }
  return text + BT.variant_text('user_action', { cls, variant });
}

export function _ledger_fate_remedy_text(mine: Record<string, any>[]): string | null {
  const RECOVERED_BY = new Set(['authored', 'verdict', 'de_escalated']);
  const FATE = new Set(['ledger_unreadable', 'question_unbuildable', 'question_form_blocked']);
  let state: Record<string, any> | null = null;
  for (const f of mine) {
    const ev = f['ev'];
    if (FATE.has(ev)) {
      state = f;
    } else if (RECOVERED_BY.has(ev)) {
      state = null;
    }
  }
  if (state === null) {
    return null;
  }
  if (state['ev'] === 'ledger_unreadable') {
    const kind = _ledger_corrupt_type_cn(String(state['detail'] ?? ''));
    return `**去向**:此用例的待决记录文件损坏(无法解析,${kind}),本轮已隔离、未能向你呈报问题——需重新生成该用例的待决记录后复跑。`;
  }
  if (state['ev'] === 'question_form_blocked') {
    return '**去向**:此用例的问询题面未通过机械格式校验，本轮没有向你呈现；这是引擎题面缺陷，需修复题面生成后复跑，不应被记成你未作答。';
  }
  return '**去向**:此用例被判定为需你确认,但引擎未能从中构造出可回答的问题(待决项为空或与题面不匹配)——需检查该用例的待决项来源后复跑。';
}

export function _awaiting_unasked_remedy_text(mine: Record<string, any>[]): string | null {
  const RECOVERED_BY = new Set(['decision', 'authored', 'verdict', 'de_escalated', 'adopted']);
  let state: Record<string, any> | null = null;
  for (const f of mine) {
    const ev = f['ev'];
    if (ev === 'awaiting_user_unasked') {
      state = f;
    } else if (RECOVERED_BY.has(ev)) {
      state = null;
    }
  }
  if (state === null) {
    return null;
  }
  if (state['shown']) {
    return '**去向**:此用例的确认面板本轮已呈报,但未被答复(非交互模式下无人应答/面板被跳过)——重跑同参数会再次呈报,请给出裁决。';
  }
  return '**去向**:此用例本轮需要你确认,但批处理未能问到它(问询预算被本批其他用例用尽,或本轮以非交互方式运行、未进入问询环节)——重跑同参数会重新排队呈报。';
}

export function _conditional_suspend_predicate(mine: Record<string, any>[]): string | null {
  let last_susp: Record<string, any> | null = null;
  for (const f of mine) {
    const ev = f['ev'];
    if (ev === 'suspended') {
      last_susp = f;
    } else if (ev === 'resumed') {
      last_susp = null;
    }
  }
  if (!last_susp || last_susp['source'] !== 'conditional_decision') {
    return null;
  }
  const qid = last_susp['question_id'];
  const cond = mine.find((f) => f['ev'] === 'conditional_decision' && f['question_id'] === qid);
  return cond ? String(cond['condition_predicate'] ?? '') : null;
}

export function _latest_adopted_still_relevant(mine: Record<string, any>[]): Record<string, any> | null {
  const RECOVERED_BY = new Set(['authored', 'verdict', 'de_escalated', 'decision']);
  let adopted: Record<string, any> | null = null;
  for (const f of mine) {
    const ev = f['ev'];
    if (ev === 'adopted') {
      adopted = f;
    } else if (RECOVERED_BY.has(ev)) {
      adopted = null;
    }
  }
  return adopted;
}

export function remedy_text(queue: Record<string, any>[], mine: Record<string, any>[], panel: Record<string, any> | null = null, advanced_this_round: boolean = false, opts: { facts?: Record<string, any>[] | null } = {}): string {
  const { facts = null } = opts;
  const execution_terminal = _active_execution_terminal(mine, { facts });
  const execution_event = String(execution_terminal['ev'] ?? '');
  if (execution_event === 'ist_core_defect' && execution_terminal['reason_code'] === 'governance_end_unclosed') {
    return `**处理结论**：${GOVERNANCE_END_UNCLOSED_CN}。由 IST-Core 核查原始停止记录和预算依据。`;
  }
  if (_execution_cause_unconfirmed(execution_terminal)) {
    return '**处理结论**：' + EXECUTION_CAUSE_UNCONFIRMED_CN + '。由 IST-Core 核对原始错误与执行条件后确定处理方向。';
  }
  const { authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block } = require("./authority_delivery_policy");
  if (is_authority_block_terminal(execution_terminal)) {
    if (is_authority_unverified_block(execution_terminal)) {
      return '**处理结论**：' + AUTHORITY_UNVERIFIED_BLOCKED_CN + '。确定这些预期值以哪一份来源为准后重新核验；其他案继续。';
    }
    if (!authority_decision_confirmed(execution_terminal, facts ?? mine)) {
      return '**处理结论**：来源待裁记录未核，由引擎核验当前产物、来源与凭据后继续处理。';
    }
    return '**处理结论**：' + AUTHORITY_DECISION_BLOCKED_CN + '。修正记录中的冲突来源后重新核验；其他案继续。';
  }
  if (_is_unattributed_stop(execution_terminal)) {
    const { is_contradiction_stop } = require("./contradiction_stop");
    if (is_contradiction_stop(execution_terminal)) {
      return '**处理结论**：' + _unattributed_stop_state_cn(execution_terminal) + '。';
    }
    return '**处理结论**：' + _unattributed_stop_state_cn(execution_terminal) + UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN + '。其他案继续。';
  }
  if (_unverified_authority_record(mine, facts)) {
    return '**处理结论**：来源权威链尚有未核缺口，由引擎补齐核验与披露，其他案继续。';
  }
  if (is_runtime_infrastructure_terminal_fact(execution_terminal)) {
    return '**结论**:本轮执行基础设施未闭合，该案按可重入阻塞结案；恢复下发/结果回收通道后重试本案，本批其余用例照常继续，无需为此修改用例。';
  }
  if (execution_event === 'ist_core_defect') {
    if (_defect_family(execution_terminal) === _DEFECT_AUTHORING_EVIDENCE) {
      return `**处理结论**：${AUTHORING_EVIDENCE_UNCLOSED_CN}。本次编写已结束；引擎需要核对出处链并修复处理缺口后重新验证，其他案继续。`;
    }
    const _api_code = _api_engine_error_terminal_code(execution_terminal);
    if (_api_code) {
      const EEA = require("./engine_errors");
      return `**历史记录**:${EEA.CODE_TITLE_CN[_api_code]}（旧码 ${_api_code}）。按本条接口响应及当前暂停凭据处理；该分类不单独证明其他组件的责任。`;
    }
    if (_is_env_engine_error_terminal(execution_terminal)) {
      const F04 = require("./facts");
      const _user_env = mine.some((f) =>
        f['ev'] === 'attribution' && String(f['disposition'] ?? '') === 'env_blocked' && F04.attribution_is_terminal(f)
      );
      if (_user_env) {
        return '**结论**:按你的确认，该用例以环境阻塞终局（引擎错误 0004）——设备/跳转机/网络拓扑不满足运行前提，引擎无权自行修复；本批其余用例照常继续，环境处理好后可重新发起编译重走该用例。';
      }
      return '**结论**:该用例卷面完好但连续多次未能上机执行，按环境错误终局（引擎错误 0004）——运行环境不满足运行前提，引擎无权自行修复；本批其余用例照常继续，环境处理好后可重新发起编译重走该用例。';
    }
    if (_is_contract_engine_error_terminal(execution_terminal)) {
      return '**结论**:这是 IST-Core 缺陷；引擎给该用例盖不上意图/SPEC 身份章（引擎错误 0003），缺章生成不出用例。本批其余用例照常继续；由引擎工程修复契约投影后重新发起编译重走该用例，当前无需用户修改用例。';
    }
    if (_is_worker_timeout_engine_error_terminal(execution_terminal)) {
      return '**结论**:这是 IST-Core 缺陷；编写孔自动恢复一次后仍未产出该用例（引擎错误 0001）。本批其余用例照常继续；由引擎工程修复编写链路后重新发起编译重走该用例，当前无需用户修改用例。平台无等价能力不从空转次数推断。';
    }
    const FCN = require("./forced_closure");
    if (FCN.is_forced_landing(execution_terminal)) {
      const { FORCED_CLOSURE_CASE_SCOPE_CN } = require("../display_lexicon");
      return `**结论**:${FCN.reason_cn(execution_terminal)}；${FORCED_CLOSURE_CASE_SCOPE_CN}，当前无需用户修改用例。`;
    }
    const family = _defect_family(execution_terminal);
    if (family === _DEFECT_DISPATCH) {
      return '**结论**:这是 IST-Core 缺陷；修好派发通道后重入，不重编卷面，当前无需用户修改用例。';
    }
    if (family === _DEFECT_ON_DEVICE) {
      return '**结论**:这是 IST-Core 缺陷；须先修复引擎并完成回归，再以新编译轮重走完整判定链，当前无需用户修改用例。';
    }
    if (execution_terminal['reason_code'] === 'legacy_mechanical_engineering_fault') {
      return '**历史记录**:保留了机械归因；责任尚需复核，本条兼容标签不签发新的引擎缺陷。';
    }
    return `**结论**:这是 IST-Core 缺陷；${_defect_artifact_cause_cn(execution_terminal, mine)}，须先修复引擎并完成回归，再以新编译轮重走完整判定链，当前无需用户修改用例。`;
  }
  if (execution_event === 'authoring_failure') {
    if (_is_worker_claim_handoff_terminal(execution_terminal)) {
      return '**结论**:模型未找到解决方案（编写侧主张：不可编，未受理）；这条历史主张不证明作者内容整体正确。编写侧交回的「不可编」报告缺少引擎可复核的凭据，本案就地终结、把剩余轮次让给同批其它用例；引擎能力更新后可用新的批名重新编译该用例。';
    }
    return `**记录结论**:模型未找到解决方案；该结论限于凭据绑定的尝试。记录的编写尝试为 ${execution_terminal['rounds_used']} 轮，模型自述、输入范围与未核事项见案级凭据；后续编写须重新验证当前条件。`;
  }
  if (execution_event === 'unable_to_compile') {
    if (execution_terminal['category'] === 'connection') {
      return '**结论**:连续三次仍无法完成设备连接，属于平台限制并归入无法编写；本案已如实终结，恢复平台连通性后可重新发起编译。';
    }
    return '**结论**:当前平台不具备该用例所需前提，无法编写；本案已如实终结，同一平台条件下不再重试。';
  }
  if (queue.length > 0) {
    const head = queue[0];
    const act = ACTION_CN[String(head['action'])] ?? String(head['action']);
    let line = `**修复方案**:${act}`;
    const _dir = String(head['direction'] ?? '').trim();
    if (_dir) {
      line += `。方向:${_ellip(_dir, 160)}`;
    }
    const rest = queue.slice(1).map((q) => ACTION_CN[String(q['action'])] ?? '');
    if (rest.some(Boolean)) {
      line += `。若仍未通过,后续依次:${rest.filter(Boolean).join('、')}`;
    }
    return line + '。';
  }
  const { _is_escalated } = require("./views");
  if (_is_escalated(mine)) {
    return _escalated_remedy_text(mine);
  }
  const F = require("./facts");
  const att = _latest_attribution(mine);
  const disp = String(att['disposition'] ?? '');
  const decs = mine.filter((f) => f['ev'] === 'decision' && f['answer']);
  const _src = F.attribution_source(att);
  if (disp === 'defect_candidate' && _src === 'engine_auto') {
    return '**结论**:引擎已尽轮次(多次重试仍未能推进、未产生新证据),记为缺陷候选(`defect_candidates.md`);修复对应原因后可重新运行。';
  }
  if (disp === 'engineering_fault') {
    return '**结论**:引擎侧遇到结构性缺口(非产品缺陷),已呈报记录、不计入缺陷候选单;该缺口需要工程侧后续处理,当前用例结果按未通过卷收尾。';
  }
  if (disp === 'defect_candidate' && _src === 'user') {
    return '**结论**:你已确认为产品缺陷,已记入缺陷候选单(`defect_candidates.md`),该用例以缺陷结案。';
  }
  if (disp === 'defect_candidate') {
    return '**结论**:疑似产品缺陷,已列入缺陷候选单(`defect_candidates.md`);坐实需换一种配置形态复现。';
  }
  if (['env_blocked', 'user_stop'].includes(disp) && F.attribution_is_terminal(att)) {
    const _ld = decs.length > 0 ? decs[decs.length - 1] : null;
    let who: string;
    if (_ld && String(_ld['provenance'] ?? '').startsWith('adopted:')) {
      const _shown = _decision_display(_ld, _fact_ordinal(mine, _ld));
      who = `(依据此前批的同键判例「${_shown}」)`;
    } else {
      const _ldr = _ld ? _ld['round'] : null;
      const _r_tag = _ld && _decision_has_current_label(_ld) && _ldr !== null && _ldr !== undefined && Number(_ldr) > 0 ? `第${_ldr}轮` : '';
      const _who_stem = _r_tag ? `依据${_r_tag}你的裁决` : '依据你的裁决';
      const _shown = _ld ? _decision_display(_ld, _fact_ordinal(mine, _ld)) : '';
      who = _ld ? `(${_who_stem}「${_shown}」)` : '';
    }
    if (disp === 'user_stop' || att['user_stop']) {
      const had_dc = mine.some((f) => f['ev'] === 'attribution' && String(f['disposition']) === 'defect_candidate');
      const tail = had_dc ? '此前轮次曾达缺陷候选,其主张与证据已汇总在缺陷候选单(`defect_candidates.md`)。' : '';
      return `**结论**:按你的止损裁决收尾${who},该用例记入未通过卷,下批可继续。${tail}`;
    }
    return `**结论**:按环境/取舍收尾${who},该用例记入未通过卷,下批可继续。`;
  }
  const _adopted = _latest_adopted_still_relevant(mine);
  if (_adopted) {
    const _rs = _ruling_summary(_adopted['ruling'] ?? '');
    return '**去向**:同一差异你此前已有裁决,本批直接沿用并按其重编' + (_rs ? `(裁决要点:${_rs})。` : '。');
  }
  const pf = mine.filter((f) => f['ev'] === 'ask_panel');
  if (pf.length > 0) {
    const _sh = require("./_shared");
    const { effective_decision_token } = require("./questions");
    const prnd = Number(pf[pf.length - 1]['round'] ?? 0);
    const aid = String(pf[pf.length - 1]['aid'] ?? '');
    const answered = mine.some((d) =>
      d['ev'] === 'decision' && _sh.panel_qid_matches(d['question_id'], aid, prnd) &&
      ['confirm', 'correct', 'defect', 'stop', 'downgrade'].includes(effective_decision_token(d))
    );
    const ask = String((panel ?? {})['ask'] ?? '').trim();
    if (!answered) {
      return '**去向**:已向你呈报差异待确认' + (ask ? `(问题:${ask})` : '') + ',答复后按你的裁决继续。';
    }
  }
  const blocked = mine.filter((f) => f['ev'] === 'delivery_blocked');
  if (blocked.length > 0 && !mine.slice(mine.indexOf(blocked[blocked.length - 1])).some((f) => f['ev'] === 'authored')) {
    return '**去向**:功能验证已通过,只差案尾清理步(自己留下的网络层配置要在案内恢复);下批续跑会带此反馈重新编写,补上后即可交付。';
  }
  const { _is_suspended, active_execution_pause } = require("./views");
  if (_is_suspended(mine)) {
    const _pause = active_execution_pause(mine);
    if (_pause) {
      if (_pause['pause_kind'] === 'contra') {
        return '**去向**:' + _execution_pause_narrative(mine, _pause) + '；同参续跑会自动重入完整判定链。';
      }
      if (['env', 'bed'].includes(String(_pause['pause_kind'] ?? ''))) {
        return '**去向**:按环境/取舍收尾方向暂挂——本轮不签永久环境结论,该用例记入未通过卷;环境处理后同参续跑会自动重入完整判定链。';
      }
      return '**去向**:执行结果的归因尚未闭合,本轮暂挂并保留原预期与原始执行记录;同参续跑会自动重入完整判定链。';
    }
    const _cond = _conditional_suspend_predicate(mine);
    if (_cond) {
      return `**去向**:有条件确认,待核验:${_cond};核验前本用例先挂起。`;
    }
    if (_no_answer_suspended(mine)) {
      return '**去向**:你未作答,本轮先挂起;重跑同参数会再次呈报请你裁决。';
    }
    return '**去向**:已挂起;同参重跑会自动重入完整判定链。';
  }
  const _direct_abandon = _direct_abandon_remedy_text(mine);
  if (_direct_abandon !== null) {
    return _direct_abandon;
  }
  const _fate = _ledger_fate_remedy_text(mine);
  if (_fate !== null) {
    return _fate;
  }
  const _unasked = _awaiting_unasked_remedy_text(mine);
  if (_unasked !== null) {
    return _unasked;
  }
  if (advanced_this_round) {
    return '**去向**:本轮已复跑,结论仍为无结论。';
  }
  return '**去向**:本轮引擎未复跑该用例(原因见顶部说明)。';
}

export function _no_answer_suspended(mine: Record<string, any>[]): boolean {
  const sus = mine.filter((f) => f['ev'] === 'suspended');
  return sus.length > 0 && _is_no_answer_reason(String(sus[sus.length - 1]['reason'] ?? ''));
}

export function _status_cn(status: string, mine: Record<string, any>[]): string {
  return _status_cn_with_facts(status, mine);
}

export function _status_cn_with_facts(status: string, mine: Record<string, any>[], opts: { facts?: Record<string, any>[] | null } = {}): string {
  const { facts = null } = opts;
  if (status === 'suspended' && _no_answer_suspended(mine)) {
    return '未作答(下批会再次问你)';
  }
  if (status === 'failed_terminal') {
    const execution_terminal = _active_execution_terminal(mine, { facts });
    if (execution_terminal && Object.keys(execution_terminal).length > 0) {
      return _execution_terminal_status_cn(execution_terminal, { facts: facts ?? mine });
    }
  }
  if (_unverified_authority_record(mine, facts)) {
    return '来源权威链未核验完成';
  }
  return STATUS_CN[status] ?? '未知状态';
}

export function _rejection_cn(code: string): string {
  const { not_compilable_rejection_cn } = require("../display_lexicon");
  return String(code ?? '').trim() ? not_compilable_rejection_cn(code) : '（拒绝原因缺失）';
}

export function _worker_claim_superseded(mine: Record<string, any>[]): boolean {
  let last_claim = -1;
  for (let index = mine.length - 1; index >= 0; index--) {
    if (mine[index]['ev'] === 'worker_claim') {
      last_claim = index;
      break;
    }
  }
  if (last_claim < 0) {
    return false;
  }
  return mine.slice(last_claim + 1).some((fact) =>
    ['authored', 'composed', 'writeback', 'merged'].includes(String(fact['ev'] ?? ''))
  );
}

export function _unbound_device_claim_lines(mine: Record<string, any>[]): string[] {
  const F = require("./facts");
  const claims = mine.filter((row) =>
    row['ev'] === 'attribution' && F.scenario5_device_defect(row['layer'], row['disposition']) &&
    F.scenario5_terminal_needs_run_evidence(row) && !F.scenario5_attribution_has_evidence(row, mine)
  );
  if (claims.length === 0) {
    return [];
  }
  return ['\n**归因证据未闭合**:', `- ${claims.length} 条模型设备缺陷主张没有绑定到对应的有效执行结果；这些主张未作为设备缺陷终局依据，原始判断仍保留在事实记录中。`];
}

export function _worker_claim_lines(mine: Record<string, any>[]): string[] {
  const claims = mine.filter((fact) => fact['ev'] === 'worker_claim' && typeof fact['report'] === 'object' && fact['report'] !== null);
  if (claims.length === 0) {
    return [];
  }
  const superseded = _worker_claim_superseded(mine);
  const out = ['\n**编写侧主张（未受理）**:以下是编写侧提交、引擎未认定为事实的说法。'];
  for (const fact of claims) {
    const report = fact['report'] ?? {};
    const test_point = String(report['test_point'] ?? '').trim();
    const obstacle = String(report['obstacle'] ?? '').trim();
    const no_equivalent = String(report['no_equivalent_reason'] ?? '').trim();
    const code = String(fact['rejection_code'] ?? '');
    out.push(`- 测试点:${test_point || '（未填写）'}\n  - 编写侧说的障碍:${obstacle || '（未填写）'}\n  - 编写侧说的「本设备没有等价做法」的理由:${no_equivalent || '（未填写）'}\n  - 引擎为何未受理:${_rejection_cn(code)}`);
  }
  out.push('  以上是编写侧的主张，引擎未认定为事实；' + (superseded ? '该案在这之后仍编出了用例，主张未成立，此处只作过程留痕。' : '用例是否真的编不出来，需要由人依据作者原文与设备实况判断。'));
  return out;
}

export function _criterion_binding_declaration_lines(mine: Record<string, any>[]): string[] {
  const rows = mine.flatMap((fact) =>
    fact['ev'] === 'criterion_binding_declared'
      ? (fact['declarations'] ?? []).filter((row: any) => typeof row === 'object' && row !== null && String(row['disclosure'] ?? '').trim())
      : []
  );
  if (rows.length === 0) {
    return [];
  }
  const out = ['\n**断言绑定由编写侧声明**:'];
  for (const row of rows) {
    out.push(`- 第 ${Number(row['state_change_step'] ?? 0) + 1} 个步骤造成本条要看的状态变化：${String(row['disclosure'] ?? '').trim()}`);
  }
  out.push('  该声明由编写侧给出、随卷上机验证，引擎未据此认定用例通过。');
  return out;
}

export function _authored_scope_disclosure_lines(mine: Record<string, any>[]): string[] {
  const rows = mine.flatMap((fact) =>
    fact['ev'] === 'authored_scope_disclosed'
      ? (fact['items'] ?? []).filter((row: any) => typeof row === 'object' && row !== null && String(row['head'] ?? ''))
      : []
  );
  if (rows.length === 0) {
    return [];
  }
  const out = ['\n**作者步骤只核到命令头**:'];
  for (const row of rows) {
    const head = String(row['head'] ?? '');
    out.push(`- 作者步骤在命令 \`${head}\` 之后写的是描述性条件而不是参数字面量；引擎只核了该命令在卷面出现的次数（${Number(row['landed'] ?? 0)}/${Number(row['needed'] ?? 0)}），条件所指的对象身份未机械比对。`);
  }
  out.push('  对象是否正确由上机结果与人工复核确认，引擎未据此认定用例通过。');
  return out;
}

export function _scenario_fidelity_lines(mine: Record<string, any>[]): string[] {
  const { SCENARIO_FIDELITY_FACT_EVENT } = require("../../case_compiler/scenario_fidelity");
  const { SCENARIO_FIDELITY_HEAD_CN, SCENARIO_FIDELITY_HEAD_FALLBACK_CN, SCENARIO_FIDELITY_UNAVAILABLE_TAIL_CN, scenario_fidelity_mechanical_cn } = require("../display_lexicon");
  const fact = [...mine].reverse().find((item) => item['ev'] === SCENARIO_FIDELITY_FACT_EVENT);
  if (!fact || typeof fact !== 'object') {
    return [];
  }
  const status = String(fact['status'] ?? '');
  const head = SCENARIO_FIDELITY_HEAD_CN[status] ?? SCENARIO_FIDELITY_HEAD_FALLBACK_CN;
  const out = [`\n**${head}**:`];
  const mechanical = typeof fact['mechanical'] === 'object' && fact['mechanical'] !== null ? fact['mechanical'] : {};
  const mechanical_cn = scenario_fidelity_mechanical_cn(mechanical);
  if (mechanical_cn) {
    out.push(`- ${mechanical_cn}`);
  }
  const disclosure = String(fact['disclosure'] ?? '').trim();
  if (disclosure && disclosure !== mechanical_cn) {
    out.push(`- ${disclosure}`);
  }
  if (status === 'unavailable') {
    out.push(`  ${SCENARIO_FIDELITY_UNAVAILABLE_TAIL_CN}`);
  }
  return out;
}

export function _device_disclosure_lines(mine: Record<string, any>[]): string[] {
  const { DEVICE_DISCLOSURE_FACT_EVENT, TIERS } = require("../../case_compiler/device_characteristics");
  const { DEVICE_DISCLOSURE_HEAD_CN, DEVICE_DISCLOSURE_SUMMARY_TMPL_CN, device_disclosure_tag_cn } = require("../display_lexicon");
  const fact = [...mine].reverse().find((item) => item['ev'] === DEVICE_DISCLOSURE_FACT_EVENT);
  if (!fact || typeof fact !== 'object') {
    return [];
  }
  const rows = (fact['rows'] ?? []).filter((row: any) => typeof row === 'object' && row !== null);
  if (rows.length === 0) {
    return [];
  }
  const by_tier: Record<string, Record<string, any>[]> = {};
  for (const row of rows) {
    const tier = String(row['tier'] ?? '');
    if (!by_tier[tier]) by_tier[tier] = [];
    by_tier[tier].push(row);
  }
  const present = TIERS.filter((tier: string) => by_tier[tier]?.length > 0);
  const out = [`\n**${DEVICE_DISCLOSURE_HEAD_CN}**:`];
  out.push('- ' + DEVICE_DISCLOSURE_SUMMARY_TMPL_CN.replace('{tiers}', present.map((t: string) => device_disclosure_tag_cn(t)).join('、')).replace('{count}', String(Number(fact['row_count'] ?? rows.length))));
  for (const tier of present) {
    for (const row of by_tier[tier]) {
      const message = String(row['message'] ?? '').split(/\s+/).join(' ');
      if (message) {
        out.push(`  - [${device_disclosure_tag_cn(tier)}] ${message}`);
      }
    }
  }
  return out;
}

export function _recompile_comparison_lines(mine: Record<string, any>[]): string[] {
  const { current_direction_disclosure } = require("../../case_compiler/recompile_comparison");
  const { direction_disclosure_lines_cn, recompile_comparison_cn } = require("../display_lexicon");
  const fact = [...mine].reverse().find((row) => row['ev'] === 'recompile_comparison') ?? {};
  const message = recompile_comparison_cn(fact);
  const lines = message ? [message] : [];
  if (Object.keys(fact).length > 0) {
    lines.push(...direction_disclosure_lines_cn(current_direction_disclosure(mine, { autoid: String(fact['aid'] ?? '') })));
  }
  return lines.length > 0 ? ['\n**重编覆盖核对**:', ...lines.map((line) => '- ' + line)] : [];
}

export function _prerequisite_finding_lines(mine: Record<string, any>[]): string[] {
  const { PREREQUISITE_FINDING_FACT_EVENT } = require("../../case_compiler/device_characteristics");
  const { MECHANICAL_FINDING_HEAD_CN, MECHANICAL_FINDING_SUMMARY_TMPL_CN } = require("../display_lexicon");
  const fact = [...mine].reverse().find((item) => item['ev'] === PREREQUISITE_FINDING_FACT_EVENT);
  if (!fact || typeof fact !== 'object') {
    return [];
  }
  const rows = (fact['rows'] ?? []).filter((row: any) => typeof row === 'object' && row !== null);
  if (rows.length === 0) {
    return [];
  }
  const out = [`\n**${MECHANICAL_FINDING_HEAD_CN}**:`];
  out.push('- ' + MECHANICAL_FINDING_SUMMARY_TMPL_CN.replace('{count}', String(Number(fact['row_count'] ?? rows.length))));
  for (const row of rows) {
    const message = String(row['message'] ?? '').split(/\s+/).join(' ');
    if (message) {
      out.push(`  - ${message}`);
    }
  }
  return out;
}

export function _case_section(aid: string, c: Record<string, any>, mine: Record<string, any>[], mcase: Record<string, any>, queue: Record<string, any>[], panel: Record<string, any> | null, not_fixpoint_reason: string = '', advanced_this_round: boolean = false, opts: { facts?: Record<string, any>[] | null } = {}): string[] {
  const { facts = null } = opts;
  const title = String(mcase['title'] ?? '');
  const out = [`## ${title || '用例 …' + aid.slice(-6)}`, `- 编号 \`${aid}\`(尾号 ${aid.slice(-6)}) · 状态:${_status_cn_with_facts(String(c['status']), mine, { facts })} · 编写 ${c['rounds']} 次`];
  const tl = case_timeline(mine);
  if (tl.length > 0) {
    out.push('\n**发生了什么**:' + tl.join('→ ') + '。');
  }
  out.push('\n**怎么判断的**:' + diagnosis_text(mine, panel, not_fixpoint_reason, { facts }));
  out.push(..._worker_claim_lines(mine));
  out.push(..._unbound_device_claim_lines(mine));
  out.push(..._criterion_binding_declaration_lines(mine));
  out.push(..._authored_scope_disclosure_lines(mine));
  out.push(..._scenario_fidelity_lines(mine));
  out.push(..._device_disclosure_lines(mine));
  out.push(..._prerequisite_finding_lines(mine));
  out.push(..._recompile_comparison_lines(mine));
  if (['attribution_projection_blocked', 'attribution_evidence_reacquisition_required'].includes(not_fixpoint_reason)) {
    out.push('\n**去向**:' + _NOT_FIXPOINT_REASON_CN[not_fixpoint_reason] + '。');
  } else if (not_fixpoint_reason === 'command_domain_isolated') {
    out.push('\n**去向**:' + command_domain_isolation_reason_cn(mine) + '。');
  } else {
    out.push('\n' + remedy_text(queue, mine, panel, advanced_this_round, { facts }));
  }
  return out;
}

export function _path_stem(s: string): string {
  const base = String(s ?? '').replace(/\\/g, '/').split('/').pop() ?? '';
  return base.includes('.') ? base.slice(0, base.lastIndexOf('.')) : base;
}

export function _batch_name(manifest: Record<string, any>, report: Record<string, any> | null = null): string {
  const out_name = String(manifest['out_name'] ?? '').trim();
  if (out_name) {
    return out_name;
  }
  const stem = _path_stem(String(manifest['source'] ?? ''));
  return stem || String((report ?? {})['batch'] ?? '');
}

export const ACTION_OWNER_CN: Record<string, string> = { 'user': '你', 'environment': '环境', 'engine': '引擎工程', 'product': '产品', 'api': 'API接口' };
export const DELIVERY_REPORT_OWNER_SECTIONS: [string, string][] = [['user', '你能做的'], ['environment', '环境要处理的'], ['api', 'API接口要处理的']];
export const CLOSING_CARD_OWNERS: Set<string> = new Set(['engine', ...DELIVERY_REPORT_OWNER_SECTIONS.map(([owner]) => owner)]);

export function project_action_owner(status: string, mine: Record<string, any>[], opts: { facts?: Record<string, any>[] | null } = {}): Record<string, string> {
  const { facts = null } = opts;
  status = String(status ?? '');
  const { active_execution_pause } = require("./views");
  const pause = active_execution_pause(mine);
  if (pause) {
    if (pause['closing_forced'] && ['bed', 'api'].includes(String(pause['pause_kind'] ?? ''))) {
      return { 'owner': 'environment', 'action': String(pause['reason'] ?? '') + '。' };
    }
    if (pause['pause_kind'] === 'contra') {
      return { 'owner': 'user', 'action': _execution_pause_narrative(mine, pause) };
    }
    if (pause['basis_status'] === 'source_unavailable') {
      return { 'owner': 'engine', 'action': '核对当前卷面与原始执行记录，补齐归因后复验；保留作者预期。' };
    }
    return { 'owner': 'environment', 'action': '检查记录指出的执行条件或通道，处理后同参续跑核验。' };
  }
  const execution_terminal = _active_execution_terminal(mine, { facts });
  const execution_event = String(execution_terminal['ev'] ?? '');
  if (execution_event === 'ist_core_defect' && execution_terminal['reason_code'] === 'governance_end_unclosed') {
    return { 'owner': 'engine', 'action': GOVERNANCE_END_UNCLOSED_CN + '。核查原始停止记录和预算依据，继续处理本案。' };
  }
  const FC = require("./forced_closure");
  if (execution_event === 'ist_core_defect' && FC.is_forced_landing(execution_terminal)) {
    const { FORCED_CLOSURE_CASE_SCOPE_CN } = require("../display_lexicon");
    return { 'owner': 'engine', 'action': FC.reason_cn(execution_terminal) + '。' + FORCED_CLOSURE_CASE_SCOPE_CN + '。' };
  }
  if (_execution_cause_unconfirmed(execution_terminal)) {
    return { 'owner': 'engine', 'action': EXECUTION_CAUSE_UNCONFIRMED_CN + '。由 IST-Core 核查出处及执行记录，再确定处理方向。' };
  }
  const { authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block } = require("./authority_delivery_policy");
  if (is_authority_block_terminal(execution_terminal)) {
    if (is_authority_unverified_block(execution_terminal)) {
      return { 'owner': 'user', 'action': '按权威对齐记录确认这些预期值以哪一份来源为准，再重新发起编写；设备 PASS 不替代来源裁定。' };
    }
    if (!authority_decision_confirmed(execution_terminal, facts ?? mine)) {
      return { 'owner': 'engine', 'action': '核验来源待裁记录的身份与凭据，按核验结果继续处理本案。' };
    }
    return { 'owner': 'user', 'action': '按权威对齐记录修正冲突来源，再重新发起编写；设备 PASS 不替代来源裁定。' };
  }
  if (_is_unattributed_stop(execution_terminal)) {
    const { is_contradiction_stop } = require("./contradiction_stop");
    if (is_contradiction_stop(execution_terminal)) {
      return { 'owner': 'user', 'action': _unattributed_stop_state_cn(execution_terminal) };
    }
    return { 'owner': 'user', 'action': UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN + '。' };
  }
  if (_unverified_authority_record(mine, facts)) {
    return { 'owner': 'engine', 'action': '核验当前产物、来源权威与原始记录，补齐处理缺口后复验；具体根因仍待确认。' };
  }
  if (is_runtime_infrastructure_terminal_fact(execution_terminal)) {
    return { 'owner': 'environment', 'action': '恢复下发或结果回收基础设施后，重新发起本案；本批其余用例继续。' };
  }
  if (execution_event === 'ist_core_defect') {
    const _api_code = _api_engine_error_terminal_code(execution_terminal);
    if (_api_code) {
      return { 'owner': 'api', 'action': _API_OWNER_ACTION_CN[_api_code] };
    }
    if (_defect_family(execution_terminal) === _DEFECT_AUTHORING_EVIDENCE) {
      return { 'owner': 'engine', 'action': AUTHORING_EVIDENCE_UNCLOSED_CN + '。核查原始输入、尝试与停止记录后确定处理方向。' };
    }
    if (_is_env_engine_error_terminal(execution_terminal)) {
      return { 'owner': 'environment', 'action': '处理好设备/跳转机/网络拓扑后，重新发起编译重走该用例。' };
    }
    if (_is_contract_engine_error_terminal(execution_terminal)) {
      return { 'owner': 'engine', 'action': '由引擎工程修复该案的契约投影/身份章链路后，重新发起编译重走该用例；本批其余用例不受影响。' };
    }
    if (_is_worker_timeout_engine_error_terminal(execution_terminal)) {
      return { 'owner': 'engine', 'action': '由引擎工程修复该案的编写链路后，重新发起编译重走该用例；本批其余用例不受影响。' };
    }
    if (_defect_family(execution_terminal) === _DEFECT_DISPATCH) {
      return { 'owner': 'engine', 'action': '由引擎工程修好派发通道后重入本案；不重编卷面。' };
    }
    return { 'owner': 'engine', 'action': '由引擎工程修复并完成回归，再以新编译轮重走完整判定链。' };
  }
  if (execution_event === 'authoring_failure') {
    return { 'owner': 'engine', 'action': '模型未找到解决方案；保留本次输入、尝试和自述，后续编写重新验证当前条件。' };
  }
  if (execution_event === 'unable_to_compile') {
    if (execution_terminal['category'] === 'connection') {
      return { 'owner': 'environment', 'action': '恢复平台与测试设备连通性后，重新发起编译。' };
    }
    return { 'owner': 'environment', 'action': '当前平台不具备运行前提；能力条件改变后再重新发起编译。' };
  }
  const atts = mine.filter((f) => f['ev'] === 'attribution');
  const dispositions = atts.map((f) => String(f['disposition'] ?? ''));
  if (dispositions.length > 0 && dispositions[dispositions.length - 1] === 'engineering_fault') {
    return { 'owner': 'engine', 'action': '由引擎工程修复并完成回归验证；当前无需用户操作。' };
  }
  const { product_expected_source_is_valid } = require("../../case_compiler/provenance_ir");
  const F = require("./facts");
  const product_ready = atts.some((a) =>
    String(a['disposition'] ?? '') === 'defect_candidate' && !['', 'user'].includes(String(a['evidence'] ?? '').trim()) &&
    typeof a['defect_candidate'] === 'object' && a['defect_candidate'] !== null &&
    product_expected_source_is_valid((a['defect_candidate'] ?? {})['expected_with_source']) &&
    F.scenario5_attribution_has_evidence(a, mine)
  );
  if (product_ready) {
    return { 'owner': 'product', 'action': '由产品负责人依据设备证据与预期出处复核；当前仅为候选，非终判。' };
  }
  if (dispositions.includes('defect_candidate')) {
    return { 'owner': 'engine', 'action': '由引擎工程补齐设备证据与预期出处后再转产品复核；当前非产品终判。' };
  }
  if (dispositions.includes('env_blocked') || status === 'broken_blocked') {
    return { 'owner': 'environment', 'action': '恢复测试设备连通性或切换到可用测试设备后，重新发起本批编译。' };
  }
  if (status === 'authored' && String(_latest_command_domain_exclusion(mine)['reason_code'] ?? '') === 'command_domain_residual') {
    return { 'owner': 'environment', 'action': `${PREFLIGHT_RESIDUAL_NOUN_CN}该用例要动的配置命令的${PREFLIGHT_CONFIG_NOUN_CN}行，当前环境给不了它净态；处理好环境（清场或换设备）后重编本案；本批其余用例不受影响。` };
  }
  const _direct_abandon_cls = _direct_abandon_class(mine);
  if (_direct_abandon_cls) {
    const BT_owner = require("./blocking_taxonomy");
    return { 'owner': _direct_abandon_cls === BT_owner.A_ENV_PREREQ_GAP ? 'environment' : 'user', 'action': BT_owner.variant_text('user_action', { cls: _direct_abandon_cls, variant: _author_gap_variant(mine, _direct_abandon_cls) }) };
  }
  let last_ask = -1;
  for (let i = mine.length - 1; i >= 0; i--) {
    if (['ask_panel', 'needs_decision', 'awaiting_user_unasked'].includes(String(mine[i]['ev']))) {
      last_ask = i;
      break;
    }
  }
  let last_answer = -1;
  for (let i = mine.length - 1; i >= 0; i--) {
    if (mine[i]['ev'] === 'decision') {
      last_answer = i;
      break;
    }
  }
  if (status === 'awaiting_user' || last_ask > last_answer) {
    return { 'owner': 'user', 'action': '重新发起本批编译，进入问询后回答该用例的待定问题。' };
  }
  if (status === 'suspended') {
    return { 'owner': 'user', 'action': '重新发起本批编译，并在恢复问询中选择继续处理。' };
  }
  if (dispositions.includes('user_stop')) {
    return { 'owner': 'user', 'action': '如需继续，重新发起本批编译，并在问询中选择继续处理。' };
  }
  const _aid = mine.find((f) => f['aid'])?.['aid'] ? String(mine.find((f) => f['aid'])?.['aid']) : '';
  if (_aid && F.serial_recovery_pending(mine, [_aid])) {
    return { 'owner': 'engine', 'action': '引擎欠该案一次派发（fork 无产出后签发的一次性恢复票）：同参重调即续跑；无需改动用例或环境。' };
  }
  return { 'owner': 'engine', 'action': '由引擎工程定位并修复该内部缺口；当前无需用户操作。' };
}

export function _unbound_observation_lines(fs: Record<string, any>[]): string[] {
  const items: Record<string, Record<string, any>[]> = {};
  for (const fact of fs) {
    if (fact['ev'] !== 'unbound_observation_target') continue;
    const aid = String(fact['aid'] ?? '');
    const rows = (fact['items'] ?? []).filter((r: any) => typeof r === 'object' && r !== null);
    if (aid && rows.length > 0) {
      items[aid] = rows;
    }
  }
  if (Object.keys(items).length === 0) {
    return [];
  }
  const out = ['- **有断言依赖了本案没有配置过的服务地址**(仅提示,不影响放行):'];
  for (const aid of Object.keys(items).sort()) {
    const addresses = [...new Set(items[aid].map((r) => String(r['address'] ?? '')))].sort();
    out.push(`  - \`${aid}\`(尾号 ${aid.slice(-6)}):断言依赖 ` + addresses.filter(Boolean).map((a) => `\`${a}\``).join('、') + ' 的服务响应,但案内没有任何步骤在该地址绑定服务——确认是有意依赖测试设备上的常驻服务吗?');
  }
  return out;
}

export function _source_conflict_auto_resolved_lines(fs: Record<string, any>[]): string[] {
  const per_case: Record<string, string> = {};
  for (const fact of fs) {
    if (fact['ev'] !== 'source_conflict_auto_resolved') continue;
    const aid = String(fact['aid'] ?? '');
    const text = String(fact['disclosure'] ?? '').trim();
    if (aid && text) {
      per_case[aid] = text;
    }
  }
  if (Object.keys(per_case).length === 0) {
    return [];
  }
  const out = [`- ℹ **源冲突已按冻结权威序自动裁定**（${Object.keys(per_case).length} 个用例，按 2026-08-20 裁决）:`];
  for (const aid of Object.keys(per_case).sort()) {
    out.push(`  - \`${aid}\`(尾号 ${aid.slice(-6)}):${per_case[aid]}`);
  }
  return out;
}

export function _claim_conflict_both_true_lines(fs: Record<string, any>[]): string[] {
  const per_case: Record<string, Record<string, any>> = {};
  for (const fact of fs) {
    if (fact['ev'] !== 'claim_conflict_both_true_released') continue;
    const aid = String(fact['aid'] ?? '');
    if (aid) {
      per_case[aid] = fact;
    }
  }
  if (Object.keys(per_case).length === 0) {
    return [];
  }
  const out = ['- ℹ **配置推导与其它来源断言不完全相同、上机两侧逐条成立，已按 2026-09-23 裁定双双保留放行**:'];
  for (const aid of Object.keys(per_case).sort()) {
    const text = String(per_case[aid]['disclosure'] ?? '').trim();
    out.push(`  - \`${aid}\`(尾号 ${aid.slice(-6)}):${text}`);
  }
  return out;
}

export function _environment_execution_disclosure_lines(fs: Record<string, any>[]): string[] {
  const per_case: Record<string, Record<string, any>> = {};
  for (const fact of fs) {
    if (fact['ev'] !== 'environment_execution_disclosure') continue;
    const aid = String(fact['aid'] ?? '');
    if (aid && String(fact['disclosure'] ?? '').trim()) {
      per_case[aid] = fact;
    }
  }
  if (Object.keys(per_case).length === 0) {
    return [];
  }
  const out = [`- ℹ **有用例受自动化环境限制、非用例本身问题**（${Object.keys(per_case).length} 个用例）:`];
  for (const aid of Object.keys(per_case).sort()) {
    const fact = per_case[aid];
    const values = (fact['author_unreachable_values'] ?? []).filter((v: any) => String(v)).map((v: any) => String(v));
    const tail = values.length > 0 ? '；作者原文里的 ' + values.map((v: any) => `\`${v}\``).join('、') + ' 在本设备不可达' : '';
    out.push(`  - \`${aid}\`(尾号 ${aid.slice(-6)}):${String(fact['disclosure'] ?? '').trim()}${tail}`);
  }
  return out;
}

export function _preflight_observation_disclosure_lines(fs: Record<string, any>[]): string[] {
  const scopes: Set<string> = new Set();
  let historical_scope_unknown = false;
  for (const fact of fs) {
    if (fact['ev'] !== 'command_domain_preflight_checked') continue;
    const details = fact['running_config_fallbacks'];
    let recorded = false;
    for (const item of (Array.isArray(details) ? details : [])) {
      if (typeof item !== 'object' || item === null) {
        historical_scope_unknown = true;
        continue;
      }
      const aid = String(item['autoid'] ?? '');
      const head = String(item['command_head'] ?? '');
      const target = String(item['target_device'] ?? '');
      if (aid && head && target) {
        scopes.add(`${aid}|${target}|${head}`);
        recorded = true;
      } else {
        historical_scope_unknown = true;
      }
    }
    const counts = fact['show_derivation_counts'];
    const count = typeof counts === 'object' && counts !== null ? counts['running_config_fallback'] : null;
    if (!recorded && typeof count === 'number' && count > 0) {
      historical_scope_unknown = true;
    }
  }
  if (scopes.size === 0 && !historical_scope_unknown) {
    return [];
  }
  const lines = ['', '- **运行配置兜底的观察范围**：本批环境预检曾安排运行配置查询。此方法只能检查是否存在匹配的配置行；动作效果不写入运行配置时，即使查询无匹配行，也不能据此确认动作状态干净。'];
  const sorted_scopes = [...scopes].sort();
  for (const scope of sorted_scopes) {
    const [aid, target, head] = scope.split('|');
    lines.push(`  - 用例 \`${aid}\` · 执行槽 \`${target}\` · 命令头 \`${head}\`。`);
  }
  if (scopes.size > 0) {
    lines.push('  - 上述范围按本批累计预检计划去重，包含后来被隔离或重新检查的用例。');
  }
  if (historical_scope_unknown) {
    lines.push('  - 部分预检记录缺少完整范围，逐案对应关系未记录，具体受影响用例和命令未确定。');
  }
  return lines;
}

export function merge_rejected_fact(fs: Record<string, any>[]): Record<string, any> {
  for (let i = fs.length - 1; i >= 0; i--) {
    const ev = String(fs[i]['ev'] ?? '');
    if (ev === 'merged') {
      return {};
    }
    if (ev === 'merge_rejected') {
      return { ...fs[i] };
    }
  }
  return {};
}

export function _merge_rejected_lines(fs: Record<string, any>[]): string[] {
  const fact = merge_rejected_fact(fs);
  if (Object.keys(fact).length === 0) {
    return [];
  }
  const reason = String(fact['reason'] ?? '').trim();
  if (!reason) {
    return [];
  }
  const composition = (fact['composition'] ?? []).filter((a: any) => String(a)).map((a: any) => String(a));
  const scope = String(fact['ctx'] ?? '') === 'delivery' ? '整卷' : '子集卷';
  const members = composition.length > 0 ? `（尾号 ${composition.slice(0, 8).map((a: any) => a.slice(-6)).join('、')}${composition.length > 8 ? '…' : ''}）` : '';
  if (String(fact['reason_class'] ?? '') === 'artifact_io') {
    return [`- ⛔ **${scope}合并后主卷读不出（引擎或文件系统故障，不是卷面规则）**:本轮组卷这一步没通过，${composition.length} 个已编写用例都没能上机${members}。故障原文如下（逐字，未改写），处置在引擎侧，不需要改用例:`, '```merge-artifact-io', reason.slice(0, 2000), '```'];
  }
  return [`- ⛔ **${scope}合并被卷面规则拒绝**:本轮组卷这一步没通过，${composition.length} 个已编写用例都没能上机` + members + '。规则原文如下（逐字，未改写）:', '```merge-rejection', reason.slice(0, 2000), '```'];
}

export function _criterion_adjudication_disclosure_lines(fs: Record<string, any>[]): string[] {
  const by_identity: Record<string, Record<string, any>> = {};
  for (const fact of fs) {
    if (fact['ev'] !== 'criterion_engine_adjudicated') continue;
    for (const decision of (fact['decisions'] ?? [])) {
      if (typeof decision !== 'object' || decision === null) continue;
      const key = [String(decision['shape_key'] ?? ''), String(decision['version_family'] ?? ''), String(decision['rule_sha256'] ?? '')];
      if (key.every(Boolean)) {
        by_identity[key.join('|')] = decision;
      }
    }
  }
  if (Object.keys(by_identity).length === 0) {
    return [];
  }
  const out = [`- ℹ **引擎内部判据裁定（${Object.keys(by_identity).length} 个 shape，作者原文未改写）**:`];
  for (const key of Object.keys(by_identity).sort()) {
    const [shape_key, version_family, rule_sha256] = key.split('|');
    const decision = by_identity[key];
    const evidence = decision['evidence_chain'] ?? {};
    const manuals = (evidence['manual_anchors'] ?? [])
      .filter((row: any) => typeof row === 'object' && row !== null && row['source_path'])
      .map((row: any) => `${row['source_path']}:${Number(row['line_start'] ?? 0)}${Number(row['line_end'] ?? 0) !== Number(row['line_start'] ?? 0) ? `-${Number(row['line_end'] ?? 0)}` : ''}`);
    const trees = (evidence['tree_context'] ?? [])
      .filter((row: any) => typeof row === 'object' && row !== null && row['context_id'])
      .map((row: any) => String(row['context_id'] ?? ''));
    const language = evidence['language'] ?? {};
    out.push(`  - shape \`${shape_key}\` · 版本族 \`${version_family}\` → \`${String(decision['criterion_type'] ?? '')}\`；规则 \`${String(decision['rule_id'] ?? '')}\`（SHA-256 \`${rule_sha256}\`）；${String(decision['disclosure'] ?? '').trim()}；证据链：手册 ${manuals.join('、') || '缺失'}；树语境 ${trees.join('、') || '缺失'}；L 闭集 \`${String(language['criterion_type'] ?? '')}\``);
  }
  return out;
}

export function _fixture_value_disclosure_lines(fs: Record<string, any>[]): string[] {
  const per_case: Record<string, Record<string, any>[]> = {};
  for (const fact of fs) {
    if (fact['ev'] !== 'fixture_values_disclosed') continue;
    const aid = String(fact['aid'] ?? '');
    const values = (fact['values'] ?? []).filter((row: any) => typeof row === 'object' && row !== null);
    if (aid && values.length > 0) {
      per_case[aid] = values;
    }
  }
  if (Object.keys(per_case).length === 0) {
    return [];
  }
  const out = ['- ℹ **引擎自造测试夹具值（均由前序配置字面值回指签发）**:'];
  for (const aid of Object.keys(per_case).sort()) {
    const rendered: string[] = [];
    for (const row of per_case[aid]) {
      const value = String(row['value'] ?? '');
      const kind = String(row['fixture_kind'] ?? '');
      const block = Number(row['config_block_index'] ?? 0);
      const command = Number(row['config_command_index'] ?? 0);
      if (value && kind) {
        rendered.push(`\`${value}\`（${kind}，CONFIG[${block}].cmds[${command}]）`);
      }
    }
    if (rendered.length > 0) {
      out.push(`  - \`${aid}\`(尾号 ${aid.slice(-6)}):` + rendered.join('、'));
    }
  }
  return out.length > 1 ? out : [];
}

export function _certifiability_lines(fs: Record<string, any>[]): string[] {
  const { group_audits, latest_terminals, select_pass_audit, terminal_artifacts } = require("../../case_compiler/pass_audit");
  const terminals = latest_terminals(fs);
  const delivered = Object.entries(terminals).filter(([, terminal]: [string, any]) => terminal['outcome'] === 'delivered').map(([aid]) => aid);
  if (delivered.length === 0) {
    return [];
  }
  const views: Record<string, any> = {};
  const grouped = group_audits(fs);
  for (const aid of delivered) {
    const [final_sha, case_sha] = terminal_artifacts(terminals[aid]);
    views[aid] = select_pass_audit(grouped[aid] ?? [], { aid, final_sha, case_sha });
  }
  const n_clean = Object.values(views).filter((view: any) => view.clean).length;
  if (n_clean === delivered.length) {
    return [`- ✓ **判别力凭据齐全**:${delivered.length} 个交付用例的断言翻转凭据均已关联到本次交付卷，无豁免；这不是对断言语义正确性的额外证明。`];
  }
  const known = Object.values(views).filter((view: any) => view.counts !== null).map((view: any) => view.counts);
  const total = known.reduce((sum: number, row: any) => sum + (row[0] ?? 0), 0);
  const flipped = known.reduce((sum: number, row: any) => sum + (row[1] ?? 0), 0);
  let summary = `- **判别力凭据未齐或未核**:${delivered.length} 个交付用例中 ${n_clean} 个的凭据已完整对账`;
  if (known.length > 0) {
    summary += `；已取得统计的 ${known.length}/${delivered.length} 个用例共 ${total} 条断言，其中 ${flipped} 条有翻转证据`;
  }
  const out = [summary + '。尚未完成的凭据、身份和统计分别列在下面。', '  - 本轮保留原上机判决；未通过变异凭据收口的记录按凭据不完整保留。'];
  const reasons: Record<string, string> = {
    'delivery_identity_missing': '交付记录缺少完整卷面身份',
    'audit_artifact_mismatch': '审计与最终整卷身份不一致',
    'case_artifact_mismatch': '审计与交付单案身份不一致或身份缺失',
    'audit_schema_invalid': '审计记录结构或来源标识不完整',
    'audit_state_invalid': '审计状态与结论不一致',
    'audit_counts_invalid': '审计计数或收据身份不能闭合',
  };
  for (const aid of [...delivered].sort()) {
    const view = views[aid];
    const prefix = `  - \`${aid}\`(尾号 ${aid.slice(-6)}):`;
    if (view.audit === null || view.audit === undefined) {
      out.push(prefix + '**无凭据审计记录**；统计未取得');
      continue;
    }
    if (view.clean) {
      continue;
    }
    if (view.counts === null || view.counts === undefined) {
      let description = reasons[view.reason] ?? '翻转审计不可用';
      const read_error = (view.audit ?? {})['read_error'];
      if (typeof read_error === 'object' && read_error !== null) {
        const error_type = read_error['error_type'];
        const explanation_map: Record<string, string> = {
          'FileNotFoundError': '对照凭据文件未找到',
          'JSONDecodeError': '对照凭据内容无法解析',
          'UnicodeDecodeError': '对照凭据编码无效',
          'PermissionError': '对照凭据无读取权限',
        };
        const explanation = explanation_map[typeof error_type === 'string' ? error_type : ''] ?? '对照凭据读取失败';
        description += '；' + explanation;
      }
      out.push(prefix + description + '；统计未取得');
      continue;
    }
    const [count, flipped_count, exempt, pending] = view.counts;
    const seg = [`断言 ${count}`, `有翻转证据 ${flipped_count}`];
    if (view.status === 'complete' && view.audit['outcome'] === 'false_pass') {
      seg.unshift('审计记录标注假通过');
    }
    if (exempt) {
      seg.push(`豁免 ${exempt}`);
      const issued = view.audit['compiler_issued_exempt_assertions'];
      const declared = view.audit['author_declared_exempt_assertions'];
      if (typeof issued === 'number' && typeof declared === 'number') {
        seg.push(`其中编译器签发 ${issued}、作者声明 ${declared}`);
      }
    }
    if (pending) {
      seg.push(`待定 ${pending}`);
    }
    out.push(prefix + seg.join('、'));
  }
  return out;
}

export function _authoring_attempt_requirement_lines(fs: Record<string, any>[]): string[] {
  const lines: string[] = [];
  const counts: Record<string, number> = {};
  for (const row of fs) {
    if (row['ev'] !== 'authoring_failure_unconfirmed') continue;
    const aid = String(row['aid'] ?? '未记录');
    counts[aid] = (counts[aid] ?? 0) + 1;
    const missing = row['missing_evidence'];
    const notes = ['台账记录的缺项，不据此补判原因或责任。'];
    if (Array.isArray(missing)) {
      if (missing.includes('three_valid_authoring_attempts_required')) {
        notes.push('该次编写证据检查未满足三次独立、有效编写失败的证据条件。');
      }
    } else {
      notes.push('缺项字段形态未核，以下保留记录原值。');
    }
    const original = JSON.stringify(missing, null, 2);
    const max_backticks = Math.max(3, ...(original.match(/`+/g) ?? []).map((m: string) => m.length), 0) + 1;
    const fence = '`'.repeat(max_backticks);
    lines.push(`\n**用例 \`${aid}\` · 编写证据检查 ${counts[aid]}（AF-0001）**\n\n` + notes.join('') + '\n\n原始缺项：\n\n' + fence + 'json\n' + original + '\n' + fence + '\n');
  }
  return lines;
}

export function _api_error_wave_lines(report: Record<string, any>): string[] {
  const wave = report['api_error_wave'];
  if (!wave || typeof wave !== 'object' || Array.isArray(wave) || Object.keys(wave).length === 0) {
    return [];
  }
  const DL = require("../display_lexicon");
  const api_error = wave['api_error'] ?? {};
  const head = DL.api_error_sentence(api_error['code'], api_error['message']);
  if (!head) {
    return [];
  }
  const count = Number(wave['count'] ?? 0);
  const total = Number(wave['total'] ?? 0);
  return [`- **${_DELIVERY_INCOMPLETE_REASON_CN['api_error']}**:${head} · 本波 ${total} 个用例里 ${count} 个同因未编写；本批其余用例照常`];
}

export function _network_outage_disclosure_lines(fs: Record<string, any>[]): string[] {
  const outages = fs.filter((f) => f['ev'] === 'network_outage');
  if (outages.length === 0) {
    return [];
  }
  let total = 0;
  for (const fact of outages) {
    try {
      total += Number(fact['waited_s'] ?? 0);
    } catch {
      continue;
    }
  }
  if (total <= 0) {
    return [];
  }
  const DL = require("../display_lexicon");
  return [`- **${DL.network_outage_disclosure_cn(total)}**`];
}

export function _thinking_degraded_disclosure_lines(fs: Record<string, any>[]): string[] {
  const seen: string[] = [];
  for (const fact of fs) {
    if (fact['ev'] !== 'disclosure') continue;
    if (String(fact['kind'] ?? '') !== 'thinking_degraded') continue;
    const text = String(fact['text'] ?? '').trim();
    if (text && !seen.includes(text)) {
      seen.push(text);
    }
  }
  return seen.map((text) => `- **思考模式降级披露**:${text}`);
}

export function _contract_warning_panel_lines(report: Record<string, any>): string[] {
  const { WARNING_PANEL_SCHEMA } = require("../../case_compiler/contract_entry");
  const panel = report['warning_panel'];
  if (!panel || typeof panel !== 'object' || Array.isArray(panel) || panel['schema'] !== WARNING_PANEL_SCHEMA) {
    return [];
  }
  const items = (panel['items'] ?? []).filter((item: any) => typeof item === 'object' && item !== null);
  const unreported = panel['unreported'];
  if (items.length === 0) {
    if (unreported && typeof unreported === 'object' && !Array.isArray(unreported) && unreported['count']) {
      return [`> **批级验证提示未能呈报**：${unreported['count']} 条提示取不回（${unreported['reason'] ?? 'unknown'}）。提示不阻断编译，但这一批的复核项在本报告里是缺的。`];
    }
    return [];
  }
  const lines = ['> **批级验证提示（不阻断编译）**：以下项目保留给用户复核，未进入 worker 上下文。'];
  for (const item of items) {
    const autoid = String(item['autoid'] ?? '').split(/\s+/).join(' ');
    const code = String(item['code'] ?? '').split(/\s+/).join(' ');
    const message = String(item['message'] ?? '').split(/\s+/).join(' ');
    if (autoid && code && message) {
      lines.push(`> - \`${autoid}\`：${message}（\`${code}\`）`);
    }
  }
  return lines.length > 1 ? lines : [];
}

export function _preflight_head_lines_disclosure_lines(fs: Record<string, any>[]): string[] {
  const lines: string[] = [];
  for (const fact of fs) {
    if (fact['ev'] !== 'command_domain_preflight_checked') continue;
    const disclosures = fact['head_lines_present'];
    if (!disclosures || typeof disclosures !== 'object' || Array.isArray(disclosures) || !Object.values(disclosures).some(Boolean)) {
      continue;
    }
    if (lines.length === 0) {
      lines.push('', `## ${PREFLIGHT_PROGRESS_LABEL}：设备已有配置`, '');
    }
    for (const [key, items] of Object.entries(disclosures)) {
      for (const item of (items as any[])) {
        lines.push('- ' + preflight_head_line_cn(key, item));
      }
    }
    const receipt = String(fact['receipt_ref'] ?? '');
    if (receipt) {
      lines.push(`完整回显保存在本地收据 \`${receipt}\`。`);
    }
  }
  return lines;
}

function diagnosis_text(mine: Record<string, any>[], panel: Record<string, any> | null = null, not_fixpoint_reason: string = '', opts: { facts?: Record<string, any>[] | null } = {}): string {
  const { active_execution_pause } = require("./views");
  const facts = opts.facts ?? null;
  const pause = active_execution_pause(mine);
  if (pause) {
    return _execution_pause_narrative(mine, pause);
  }
  const execution_terminal = _active_execution_terminal(mine, { facts });
  const execution_event = String(execution_terminal['ev'] || '');
  if (execution_event === 'ist_core_defect' && execution_terminal['reason_code'] === 'governance_end_unclosed') {
    return GOVERNANCE_END_UNCLOSED_CN + '；原始停止记录与出处链已保留。';
  }
  const _FC = require("./forced_closure");
  if (execution_event === 'ist_core_defect' && _FC.is_forced_landing(execution_terminal)) {
    return _FC.reason_cn(execution_terminal) + '；出处链与批级边界记录已保留，本批其余用例不受影响。';
  }
  if (_execution_cause_unconfirmed(execution_terminal)) {
    return EXECUTION_CAUSE_UNCONFIRMED_CN + '；原错误与执行身份保留，由 IST-Core 核查记录并继续处理。';
  }
  const { authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block } = require("./authority_delivery_policy");
  if (is_authority_block_terminal(execution_terminal)) {
    if (is_authority_unverified_block(execution_terminal)) {
      return AUTHORITY_UNVERIFIED_BLOCKED_CN + '；卷面与设备结论照常保留，具体分歧见权威对齐记录。';
    }
    if (!authority_decision_confirmed(execution_terminal, facts !== null ? facts : mine)) {
      return '来源待裁记录的身份和凭据未核，当前处理缺口需由引擎复核。';
    }
    return AUTHORITY_DECISION_BLOCKED_CN + '；当前产物与交付身份已核对，具体冲突见权威对齐记录。';
  }
  if (_is_unattributed_stop(execution_terminal)) {
    return _unattributed_stop_state_cn(execution_terminal);
  }
  if (_unverified_authority_record(mine, facts)) {
    const _unverified = '收口来源权威链未核验完成；当前记录不能确认来源待裁或卷面变化，具体原因及责任仍待核实。';
    const _first = _authority_chain_error_text({ aid: String(([...mine].reverse().find((row: any) => row['aid']) || {})['aid'] || '') }, facts !== null ? facts : mine);
    return _first ? _unverified + '未核成的环节留证：' + _ellip(_first, 240) : _unverified;
  }
  if (is_runtime_infrastructure_terminal_fact(execution_terminal)) {
    const detail = String(execution_terminal['error_text'] || '').trim();
    const suffix = detail ? '；生产者留证：' + _ellip(detail, 240) : '';
    return '本轮执行基础设施（下发或结果回收通道）未闭合；卷面未因此被判为 IST-Core 产物缺陷，只阻塞该案，本批兄弟案继续' + suffix + '。';
  }
  if (execution_event === 'ist_core_defect') {
    if (_defect_family(execution_terminal) === _DEFECT_AUTHORING_EVIDENCE) {
      return AUTHORING_EVIDENCE_UNCLOSED_CN + '；原始停止记录与出处链已保留。';
    }
    const _api_code = _api_engine_error_terminal_code(execution_terminal);
    if (_api_code) {
      const _EEA = require("./engine_errors");
      return '历史记录包含 API 分类（' + _EEA.CODE_TITLE_CN[_api_code] + '，旧码 ' + _api_code + '）；具体响应与当前处置分别按原始记录核对，其他组件的责任尚未由此确认。';
    }
    if (_is_env_engine_error_terminal(execution_terminal)) {
      return '运行环境不满足运行前提（环境错误 0004，判定经确认或多次未能上机执行坐实）；该用例按案级终局记账，修复权在环境侧。';
    }
    if (_is_contract_engine_error_terminal(execution_terminal)) {
      return '引擎给该用例盖不上意图/SPEC 身份章（引擎错误 0003，盘上没有本案的契约投影）；该用例按案级终局记账，本批其余用例不受影响，判为 IST-Core 缺陷。';
    }
    if (_is_worker_timeout_engine_error_terminal(execution_terminal)) {
      return '编写孔在一次有界自动恢复后仍未产出该用例（引擎错误 0001）；该用例按案级终局记账，本批其余用例不受影响，判为可重入的 IST-Core 缺陷。';
    }
    const _family = _defect_family(execution_terminal);
    if (_family === _DEFECT_DISPATCH) {
      return LAYER_CN['dispatch'] + '，未达设备 CLI，判为 IST-Core 缺陷。';
    }
    if (_family === _DEFECT_ON_DEVICE) {
      return '同一上机执行身份连续三次未完成；结构化错误码归入引擎拒收或未知执行故障，判为 IST-Core 缺陷。';
    }
    if (execution_terminal['reason_code'] === 'legacy_mechanical_engineering_fault') {
      return '历史机械归因被保存为兼容记录；当前责任仍须由本次有效凭据核实。';
    }
    const _TOD = require("./terminal_outcomes");
    if (_TOD.FINAL_VOLUME_FAILURE_EVENTS.includes(execution_terminal['reason_code']) && execution_terminal['failure_axis'] === _TOD.AUTHORITY_CHAIN_AXIS) {
      return _defect_artifact_cause_cn(execution_terminal, mine) + '；保留原始记录，由引擎完成处理与复核。';
    }
    return _defect_artifact_cause_cn(execution_terminal, mine) + '；问题出在引擎自有产物上，判为 IST-Core 缺陷。';
  }
  if (execution_event === 'authoring_failure') {
    if (_is_worker_claim_handoff_terminal(execution_terminal)) {
      return '编写侧交回了结构化的「不可编」报告，但报告缺少引擎可复核的凭据、未被受理（' + _authoring_causes_cn(execution_terminal) + '）；该案就地收口把剩余轮次让给同批其它用例，作者内容未改、未报设备缺陷，判为模型未找到解决方案。';
    }
    return '编写轮次用尽，每一轮都败在编写侧（' + _authoring_causes_cn(execution_terminal) + '）；作者内容未改、未报设备缺陷，判为模型未找到解决方案。';
  }
  if (execution_event === 'unable_to_compile') {
    if (execution_terminal['category'] === 'connection') {
      return '同一上机执行身份连续三次未完成；结构化错误码均指向设备连接或运行环境不可达，作为平台限制归入无法编写终态。';
    }
    return '同一上机执行身份连续三次未完成；设备结构化返回运行前提不具备，判为当前平台无法编写。';
  }
  if (['attribution_projection_blocked', 'attribution_evidence_reacquisition_required'].includes(not_fixpoint_reason)) {
    const reason_cn = _NOT_FIXPOINT_REASON_CN[not_fixpoint_reason];
    return '本轮深归因未被消费——' + reason_cn + '。';
  }
  const att = _latest_semantic_attribution(mine);
  const parts: string[] = [];
  const diags = mine.filter((f: any) => f['ev'] === 'diagnosis');
  const diag = diags.length ? diags[diags.length - 1] : {};
  let s0_note = '';
  if (String(diag['h_position'] || '').startsWith('h_s0')) {
    s0_note = '前序状态影响尚未证实；' + _h_s0_polluter_cause(diag);
  }
  const { _fact_sha256 } = require("./terminal_credentials");
  const last_verdict = [...mine].reverse().find((fact: any) => fact['ev'] === 'verdict') || {};
  const candidates = mine.filter((fact: any) => fact['ev'] === 's0_candidate' && Object.keys(last_verdict).length && fact['source_fact_sha256'] === _fact_sha256(last_verdict));
  if (candidates.length) {
    s0_note = '记录中存在前序配置影响线索，尚未证实因果；本案仍依据独立执行证据归因。';
  }
  const hyp = String((panel || {})['hypothesis'] || '').trim();
  const shape = String((panel || {})['conflict_shape'] || '');
  if (hyp && !parts.length) {
    parts.push((shape ? SHAPE_CN[shape] ?? SHAPE_CN['other'] + ':' : '') + hyp);
  } else if (Object.keys(att).length && !parts.length) {
    const cn = LAYER_CN[String(att['layer'] || '')] || '';
    if (cn) parts.push('判断:' + cn + '。');
  }
  if (s0_note) parts.push(s0_note);
  if (!Object.keys(att).length && !hyp && !parts.length) {
    if (not_fixpoint_reason) {
      let reason_cn = _NOT_FIXPOINT_REASON_CN[not_fixpoint_reason] ?? _UNKNOWN_NOT_FIXPOINT_REASON_CN;
      if (not_fixpoint_reason === 'command_domain_isolated') {
        reason_cn = command_domain_isolation_reason_cn(mine);
      }
      const verdicts = mine.filter((f: any) => f['ev'] === 'verdict');
      const last_v = verdicts.length ? verdicts[verdicts.length - 1] : {};
      if (['broken', 'not_run'].includes(String(last_v['result']))) {
        return '此用例未跑成(结论无效),不适用逐案根因分析——按规则处置是原样复跑而非分析;' + reason_cn + '。';
      }
      return '此用例本轮未被引擎推进——' + reason_cn + '。';
    }
    return '本轮收口前未能完成原因分析(证据在案,可续跑补齐)。';
  }
  const _F = require("./facts");
  if (att['evidence'] && _F.attribution_source(att) === '') {
    parts.push('关键证据:「' + clean_device_echo(String(att['evidence']), 200) + '」。');
  }
  return parts.join(' ') || '(证据在案,见事实台账)';
}

export function render_delivery_report(report: Record<string, any>, fs: Record<string, any>[], manifest: Record<string, any>, queues: Record<string, Record<string, any>[]>, panels: Record<string, Record<string, any>> | null = null): string {
  const t = report['totals'] ?? {};
  const ok = Number(t['deliverable'] ?? 0);
  const total = Number(t['cases'] ?? 0);
  const mcases: Record<string, any> = {};
  for (const c of (manifest['cases'] ?? [])) {
    mcases[String(c['autoid'])] = c;
  }
  const lines = [
    `# 交付报告 — ${_batch_name(manifest, report)}`,
    `> 生成 ${new Date().toLocaleString('sv-SE').slice(0, 16)}`,
    '',
    `本批 ${total} 个用例:**${ok} 个通过整卷复验,已入交付卷**` + (total > ok ? `;其余 ${total - ok} 个已按行动主体分流，下面列你、环境或API接口侧可执行的动作，以及需要引擎继续核查或修复的执行记录；其它引擎/产品责任项进入工程与产品处置候选单。` : '。'),
    '',
  ];
  const _oc = String(report['outcome'] ?? '');
  const { uses_new_policy } = require("./authoring_evidence");
  if (uses_new_policy(fs)) {
    lines[3] = `本批登记 ${total} 个用例。有效终态、隔离与其余未终结案见下方人口账；未核责任不写成结论。`;
  }
  if (_oc === 'delivery_incomplete') {
    const _why = delivery_incomplete_why_cn(report['delivery_incomplete_reasons']);
    lines.push(`- **收口结论:交付不完整**——${_why},请以 \`engine_report.json\` 为准,勿把本报告当完整交付凭证`);
  } else if (_oc === 'report_mismatch') {
    lines.push('- **收口结论:报告与事实台账不一致**——本批暂不可作为交付依据(详见 `REPORT_MISMATCH.json`)');
  }
  const _excel_runtime = report['excel_runtime'] ?? {};
  if (typeof _excel_runtime === 'object' && _excel_runtime !== null && !Array.isArray(_excel_runtime)) {
    const _release_state = String(_excel_runtime['release_state'] ?? '');
    if (_release_state === 'legacy') {
      lines.push('> **Excel 运行模板告警**：`release_state=legacy`，当前生产选择仍是无契约 marker 的历史模板；已部署 runner 会拒绝该卷，完成 promotion 前不得据此声称可上机。');
    } else if (_release_state) {
      lines.push(`- Excel 运行模板：\`release_state=${_release_state}\``);
    }
  }
  const _sup = report['volume_composition_superset'];
  if (_sup && typeof _sup === 'object' && !Array.isArray(_sup) && (_sup['residents'] ?? []).length > 0) {
    const _n_res = (_sup['residents'] ?? []).length;
    const _n_ok = (_sup['deliverable'] ?? []).length;
    lines.push(`- **主卷不止交付案**:\`case.xlsx\` 里除了 ${_n_ok} 个通过案,还有 ${_n_res} 个同卷跑过但未交付的用例(结论各异——有真未通过,也有上机 PASS 但收口案级核对未过被撤销的;它们的结论见未通过卷)。本批在重新组卷之前停下了,请按上面的通过清单取用,不要把整份主卷当通过卷。`);
  }
  const _tr = report['this_run'] ?? {};
  if (_tr && !_tr['active']) {
    lines.push(`> **本轮无新进展**:引擎本轮未编写、未上机、未产生新判决(本轮新增 ${Number(_tr['new_facts'] ?? 0)} 条过程记录)。下方各用例的过程与状态来自**历史累计**台账,不是本轮新产出。`);
  }
  const _dov = fs.filter((f) => f['ev'] === 'delivery_overwritten');
  if (_dov.length > 0) {
    const _files = (_dov[_dov.length - 1]['files'] ?? []).map((x: any) => String(x)).join('、');
    lines.push(`- **交付物在上轮 closing 后被改写**:${_files}——引擎交付物应确定性产出,请核对是否被手工重建`);
  }
  const _merge_rejection_lines = _merge_rejected_lines(fs);
  lines.push(..._merge_rejection_lines);
  const _phase_error = String((report['phase_error'] ?? {})['error'] ?? '').trim();
  if (_phase_error && _merge_rejection_lines.length === 0) {
    lines.push(`- ⛔ **本轮在收口前以错误状态终止**，引擎留下的原文（逐字，未改写）:\`${_ellip(_phase_error, 400)}\``);
  }
  const { window_audit_summary_cn } = require("../display_lexicon");
  const _latest_verdicts: Record<string, any> = {};
  for (const f of fs) {
    if (f['ev'] === 'verdict' && f['aid']) {
      _latest_verdicts[String(f['aid'])] = f;
    }
  }
  const _audit_lines = Object.values(_latest_verdicts).map((f) => window_audit_summary_cn(f));
  const _clusters: Record<string, any> = {};
  for (const f of fs) {
    if (f['ev'] === 'session_desync_cluster') {
      _clusters[`${String(f['device'] ?? '')}|${JSON.stringify(f['autoids'] ?? [])}`] = f;
    }
  }
  _audit_lines.push(...Object.values(_clusters).map((f) => window_audit_summary_cn(f)));
  if (_audit_lines.some(Boolean)) {
    lines.push('', '## 窗口审计与会话观察', '');
    lines.push(..._audit_lines.filter(Boolean).map((line) => '- ' + line));
  }
  lines.push(..._api_error_wave_lines(report));
  lines.push(..._network_outage_disclosure_lines(fs));
  lines.push(..._thinking_degraded_disclosure_lines(fs));
  lines.push(..._contract_warning_panel_lines(report));
  lines.push(..._certifiability_lines(fs));
  const { HELD_CN, HELD_EVENT } = require("./terminal_reentry_identity");
  const { this_run_slice } = require("./facts");
  const held: Record<string, any> = {};
  for (const row of this_run_slice(fs)) {
    if (row['ev'] === HELD_EVENT) {
      held[String(row['aid'] ?? '')] = row;
    }
  }
  for (const [aid, row] of Object.entries(held).sort()) {
    lines.push(`- \`${aid}\`：` + (HELD_CN[row['reason_code']] ?? '本轮重入身份未核，原终态保留') + '。');
  }
  const denied_writebacks = [...new Set(fs.filter((row) => row['ev'] === 'writeback_failed' && row['denied_by_identity'] === true && row['aid']).map((row) => String(row['aid'])))].sort();
  for (const aid of denied_writebacks) {
    lines.push(`- \`${aid}\`：归档写回记录显示封禁规则拒绝，未完成该次写回；原上机记录保留。`);
  }
  lines.push(..._authoring_attempt_requirement_lines(fs));
  lines.push(..._unbound_observation_lines(fs));
  lines.push(..._source_conflict_auto_resolved_lines(fs));
  lines.push(..._claim_conflict_both_true_lines(fs));
  lines.push(..._criterion_adjudication_disclosure_lines(fs));
  lines.push(..._environment_execution_disclosure_lines(fs));
  lines.push(..._preflight_observation_disclosure_lines(fs));
  lines.push(..._fixture_value_disclosure_lines(fs));
  lines.push(..._preflight_head_lines_disclosure_lines(fs));
  const _case_xml_inconsistent = [...new Set(fs.filter((f) => f['ev'] === 'case_source_inconsistency' && String(f['aid'] ?? '')).map((f) => String(f['aid'] ?? '')))].sort();
  if (_case_xml_inconsistent.length > 0) {
    const _tails = _case_xml_inconsistent.map((aid) => aid.slice(-6)).join('、');
    lines.push(`- **用例与设备 XML 不一致**:${_case_xml_inconsistent.length} 个用例（尾号 ${_tails}）已按本批裁决采用 XML 继续编写、上机与出卷；原用例预期/命令需另行核对。`);
  }
  const n_broken = Number(t['broken'] ?? 0) + Number(t['broken_errored'] ?? 0) + Number(t['broken_blocked'] ?? 0) + Number(t['broken_aborted'] ?? 0) + Number(t['broken_verdict_unrecognized'] ?? 0);
  if (n_broken > 0) {
    lines.push(`- 有 ${n_broken} 个用例本轮**未跑成**(执行中断/日志陈腐/级联受害/断言被实机回显反证/设备不可达)——它们的结果是「无结论」而非「未通过」,不计入通过率分母叙事`);
  }
  const _gd: Record<string, string> = {};
  for (const f of fs) {
    if (f['ev'] === 'gate_disabled') {
      _gd[String(f['gate'])] = String(f['reason'] ?? '');
    }
  }
  if (Object.keys(_gd).length > 0) {
    const _cn: Record<string, string> = {
      'diagnose_s0': '批级污染诊断',
      'inverse_forms': 'τ 覆盖规则/机械恢复',
      'touch_profile': '触碰画像(s₀ 配对输入)',
      'dispatch_targets_disabled_for_e': 'F 列分发校验(部分 E 值未覆盖白名单)',
    };
    const items = Object.keys(_gd).sort().map((g) => _cn[g] ?? '未登记判定规则').join('；');
    lines.push(`- **K 健康度**:${Object.keys(_gd).length} 个判定规则本轮因数据面缺席而降级(${items})——相关诊断/覆盖判定的可信度下降,详见 engine_report.json 机读报告中的规则降级记录`);
  }
  const { advisory_check_status } = require("../../case_compiler/gate_advisories");
  const F = require("./facts");
  const _ga = this_run_slice(fs).filter((f: any) => f['ev'] === 'gate_advisory');
  for (const f of _ga) {
    const code = String(f['code'] ?? '');
    const status = advisory_check_status(code);
    const label_map: Record<string, string> = { 'not_checked': '未执行检查', 'checked_limitation': '已检查，发现局限', 'unknown': '历史记录未注明检查状态' };
    const label = label_map[status] ?? '历史记录未注明检查状态';
    lines.push(`- **规则呈报**:${f['aid'] ?? '批级'} · ${code} · ${label} · ${f['locus'] ?? f['step_index'] ?? ''}；详见 engine_report.json。`);
  }
  const _disclosure_labels: Record<string, string> = {
    'round_cap_side_disclosure': '接口或治理中断，本轮编写暂挂',
    'structural_rejection_disclosure': '连续两轮同码拒绝，停止重复策略，保留剩余尝试',
    'criterion_satisfiability_gap': '声明未匹配或类型未登记；完整承载能力尚未证明',
  };
  for (const f of this_run_slice(fs)) {
    if (f['ev'] in _disclosure_labels) {
      lines.push(`- **编写条件披露**:${f['aid'] ?? '批级'} · ${_disclosure_labels[f['ev']]} · ${f['code'] ?? f['expectation_id'] ?? ''}。`);
    }
  }
  const _vuc_latest: Record<string, any> = {};
  for (const _cc of fs) {
    if (_cc['ev'] !== 'verdict_unrecognized_cluster') continue;
    const _rv = String(_cc['raw_value'] ?? '');
    if (_rv) {
      _vuc_latest[_rv] = _cc;
    }
  }
  for (const _rv of Object.keys(_vuc_latest).sort()) {
    const _cc = _vuc_latest[_rv];
    const _c_aids = (_cc['aids'] ?? []).map((a: any) => String(a));
    const _c_batches = (_cc['batches_seen'] ?? []).map((b: any) => String(b));
    const _c_tail = _c_aids.slice(0, 6).map((a: string) => a.slice(-6)).join('、') + (_c_aids.length > 6 ? '…' : '');
    if (_c_batches.length >= 2) {
      lines.push(`- **框架返回值超出已识别范围,已跨批次复现**:某个未识别值本批命中 ${_c_aids.length} 个用例(尾号 ${_c_tail}),另在 ${_c_batches.length - 1} 个其它批次也出现过——这更像我们的裁决闭集已过时,不像个案偶发,建议核对框架侧接口`);
    } else {
      lines.push(`- **框架本批返回了同一个未识别的裁决值**:该未识别值出现在 ${_c_aids.length} 个不同用例(尾号 ${_c_tail})——这更像闭集过时,不像某个用例偶发出错`);
    }
  }
  const _ask_t = t['ask'] ?? {};
  const _ask_answered = Number(_ask_t['answered'] ?? 0);
  const _ask_unresolved = _ask_answered - Number(_ask_t['effective'] ?? 0);
  if (_ask_unresolved > 0) {
    const _freeform_n = Number(_ask_t['freeform'] ?? 0);
    const _other_n = _ask_unresolved - _freeform_n;
    if (_freeform_n > 0) {
      lines.push(`- 本轮 ${_ask_answered} 个裁决中,其中 ${_freeform_n} 个你走了自由输入(说明给的选项没覆盖你的情况)`);
    }
    if (_other_n > 0) {
      if (_tr && !_tr['active']) {
        lines.push(`- 这 ${_other_n} 个的裁决引擎本轮没有执行(不是选项不适配),原因见顶部说明`);
      } else {
        lines.push(`- ${_other_n} 个裁决尚未达成终局(处理仍在进行中,非选项不适配)`);
      }
    }
  }
  const _sc = fs.filter((f) => f['ev'] === 'sibling_collision');
  if (_sc.length > 0) {
    const pairs = _sc.slice(0, 4).map((c) => `${String(c['aid']).slice(-6)}↔${String(c['with']).slice(-6)}`).join('、');
    lines.push(`- ${_sc.length} 组同组变体疑似撞题(尾号 ${pairs}${_sc.length > 4 ? '…' : ''}),详见机读报告`);
  }
  const _scu = fs.filter((f) => f['ev'] === 'strong_claim_unaddressed');
  if (_scu.length > 0) {
    const aids = _scu.slice(0, 4).map((f) => String(f['aid']).slice(-6)).join('、');
    lines.push(`- ${_scu.length} 案存在未被本轮正面回应的历史强主张(尾号 ${aids}${_scu.length > 4 ? '…' : ''}),可能被静默降级,详见机读报告`);
  }
  const _fwf = fs.filter((f) => f['ev'] === 'frozen_write_failed');
  if (_fwf.length > 0) {
    const aids = _fwf.slice(0, 4).map((f) => String(f['aid']).slice(-6)).join('、');
    lines.push(`- ${_fwf.length} 案本轮冻结标记未能落盘(尾号 ${aids}${_fwf.length > 4 ? '…' : ''}),已证伪的方法下轮可能被无声重试,详见机读报告`);
  }
  const _awf = fs.filter((f) => f['ev'] === 'adjudication_write_failed');
  if (_awf.length > 0) {
    const aids = _awf.slice(0, 4).map((f) => String(f['aid']).slice(-6)).join('、');
    lines.push(`- ${_awf.length} 案本轮判例写回失败(尾号 ${aids}${_awf.length > 4 ? '…' : ''}),下批可能重复问同一问题,详见机读报告`);
  }
  const moved = report['moved_tail'] ?? [];
  if (moved.length > 0) {
    const names = moved.map((a: any) => String((mcases[String(a)] ?? {})['title'] ?? '…' + String(a).slice(-6)));
    lines.push(`- 有 ${moved.length} 个用例会在设备上留下跨用例存活的配置(保存/同步类),已按规则排到卷尾执行:${names.join('、')}`);
  }
  if (report['coexist_violations']) {
    if (report['coexist_blocked']) {
      lines.push('- 本卷存在官方标注互斥的操作组合,已在组卷前阻断,未向设备发车(详见机读报告)');
    } else {
      lines.push('- 历史事实记录到互斥操作组合；当前规则会在组卷前阻断(详见机读报告)');
    }
  }
  const _spec_cov = report['spec_coverage'] ?? {};
  const _spec_cases = _spec_cov['cases'] ?? {};
  const { spec_absent } = require("./conflict_chain");
  const _spec_status_token = String(_spec_cov['governing_spec_status'] ?? '');
  if (spec_absent(_spec_status_token)) {
    if (_spec_status_token === 'ambiguous') {
      lines.push('- **SPEC 背书**:本批管辖 SPEC 检索命中多个候选、打分分不开,按 SPEC 缺失处理；用例按完整性及其它带身份来源继续处理。此注记不等同于证明不存在相关规格。');
      const _spec_refs = _spec_cov['spec_references'] ?? [];
      if (_spec_refs.length > 0) {
        const _rnames = _spec_refs.slice(0, 6).map((r: any) => String(r['name'] ?? '?')).join('、');
        const _rmore = _spec_refs.length > 6 ? ` 等 ${_spec_refs.length} 份` : '';
        lines.push(`- **参考规范书**:本批 ${_spec_refs.length} 份产品规范书候选（非管辖）已降为定向参考（零签发权·不判用例与规格书互斥）:${_rnames}${_rmore}；切片锚点见机读 governing_spec_status.json。`);
      }
    } else {
      lines.push('- **SPEC 背书**:本批未声明管辖 SPEC；用例按完整性及其它带身份来源继续处理。此注记不等同于证明不存在相关规格。');
    }
  } else {
    const _not_projected = Object.entries(_spec_cases).filter(([, item]: [string, any]) => String((item ?? {})['status'] ?? '') === 'not_projected').map(([aid]) => aid);
    if (_not_projected.length > 0) {
      const _tails = _not_projected.slice(0, 8).map((aid) => String(aid).slice(-6)).join('、');
      const _more = _not_projected.length > 8 ? '…' : '';
      lines.push(`- **SPEC 覆盖注记**:${_not_projected.length} 案的当前密封契约未投影出 SPEC 签发声明(尾号 ${_tails}${_more})；不阻断编写或上机，也不是对 SPEC 全文的穷尽否定。`);
    }
  }
  const _prec = report['precedent_polarity_flags'] ?? [];
  if (_prec.length > 0) {
    const _pn = _prec.reduce((sum: number, p: any) => sum + Number(p['count'] ?? 0), 0);
    const _pnames = _prec.map((p: any) => String((mcases[String(p['autoid'])] ?? {})['title'] ?? '…' + String(p['autoid']).slice(-6)));
    lines.push(`- ${_prec.length} 个交付用例的 ${_pn} 条断言极性照抄先例语法(已上机验方向,仅作来源标注供复核抽查):${_pnames.join('、')}`);
  }
  const bad = Object.fromEntries(Object.entries(report['cases'] ?? {}).filter(([, c]: [string, any]) => c['status'] !== 'deliverable'));
  const _nfp_reasons = (report['not_fixpoint'] ?? {})['reasons'] ?? {};
  const _advanced = new Set(report['advanced_this_round'] ?? []);
  const BT = require("./blocking_taxonomy");
  const _cards: Record<string, any> = {};
  for (const f of fs) {
    if (f['ev'] === 'blocking_card') {
      _cards[String(f['aid'] ?? '')] = f;
    }
  }
  const _delivered_carded = Object.entries(report['cases'] ?? {})
    .filter(([aid, c]: [string, any]) => c['status'] === 'deliverable' && aid in _cards)
    .map(([aid, c]: [string, any]) => [aid, c, _cards[aid]] as [string, any, any])
    .sort(([a], [b]) => a.localeCompare(b));
  if (_delivered_carded.length > 0) {
    lines.push('', '**已交付案的不一致留痕**', '');
    for (const [aid, _case, card] of _delivered_carded) {
      const mine = fs.filter((f) => String(f['aid']) === aid);
      const title = String((mcases[aid] ?? {})['title'] ?? '…' + aid.slice(-6));
      const cls = BT.canonical_class(String(card['blocking_class'] ?? ''));
      lines.push(`## ${title}`);
      lines.push(`- 编号 \`${aid}\`(尾号 ${aid.slice(-6)}) · 已通过整卷复验并交付`);
      const timeline = case_timeline(mine);
      if (timeline.length > 0) {
        lines.push('- **发生了什么**:' + timeline.join('→ ') + '。');
      }
      lines.push(`- **不一致因素**:${BT.FACTOR_ZH[cls] ?? BT.FACTOR_ZH[BT.B_UNCLASSIFIED]}`);
      const version_note = _xml_precedent_note(card);
      if (version_note) {
        lines.push(`- **版本差异**:${version_note}`);
      }
      lines.push(..._scenario1_evidence_lines(mine));
      lines.push(..._scenario1_missing_fields_lines(mine));
      lines.push(`- **凭据**:${(card['basis'] ?? []).length} 条结构化依据已保留在事实台账`);
      lines.push('');
    }
  }
  if (Object.keys(bad).length > 0) {
    const projected: [string, any, Record<string, any>[], Record<string, string>][] = [];
    for (const [aid, c] of Object.entries(bad as Record<string, any>).sort()) {
      const mine = fs.filter((f: any) => String(f['aid']) === aid);
      const own = project_action_owner(String(c['status'] ?? ''), mine, { facts: fs });
      projected.push([aid, c as any, mine, own]);
    }
    for (const [owner, heading] of DELIVERY_REPORT_OWNER_SECTIONS) {
      const owned = projected.filter((x) => x[3]['owner'] === owner);
      if (owned.length === 0) continue;
      lines.push('', `**${heading}**`, '');
      for (const [aid, c, mine, own] of owned) {
        lines.push(..._case_section(aid, c, mine, mcases[aid] ?? {}, queues[aid] ?? [], (panels ?? {})[aid], _nfp_reasons[aid] ?? '', _advanced.has(aid), { facts: fs }));
        lines.push(`- **下一步动作**:${own['action']}`);
        lines.push('');
      }
    }
    const engine_must = projected.filter((item) => item[3]['owner'] === 'engine' && on_engine_delivery_action_list(item[2], { facts: fs }));
    if (engine_must.length > 0) {
      lines.push('', '**引擎必须处理的**', '');
      for (const [aid, c, mine, own] of engine_must) {
        lines.push(..._case_section(aid, c, mine, mcases[aid] ?? {}, queues[aid] ?? [], (panels ?? {})[aid], _nfp_reasons[aid] ?? '', _advanced.has(aid), { facts: fs }));
        lines.push(`- **下一步动作**:${own['action']}`);
        lines.push('');
      }
    }
    const _carded = projected.filter((item) => item[0] in _cards && (item[3]['owner'] in { 'user': 1, 'environment': 1 } || BT.is_abandon_class(String(_cards[item[0]]['blocking_class'] ?? '')))).map((item) => [item[0], _cards[item[0]]] as [string, any]);
    if (_carded.length > 0) {
      lines.push('', '**客观阻塞对账**(每个未交付案的因素+凭据+已实现处置入口)', '');
      const _order: Record<string, number> = {};
      let idx = 0;
      for (const cls of [...BT.ABANDON_CLASSES, ...BT.BLOCKING_CLASSES, BT.B_UNCLASSIFIED]) {
        _order[cls] = idx++;
      }
      for (const [aid, card] of _carded.sort(([a1, c1], [a2, c2]) => (_order[BT.canonical_class(String(c1['blocking_class'] ?? ''))] ?? 99) - (_order[BT.canonical_class(String(c2['blocking_class'] ?? ''))] ?? 99) || a1.localeCompare(a2))) {
        const mine = fs.filter((f) => String(f['aid'] ?? '') === aid);
        const cls = BT.canonical_class(String(card['blocking_class'] ?? ''));
        const title = String((mcases[aid] ?? {})['title'] ?? '');
        const _gap_variant = _author_gap_variant(mine, cls);
        const cn = BT.variant_text('class_cn', { cls, variant: _gap_variant });
        lines.push(`## [${cn}] ${title || '…' + aid.slice(-6)}`);
        lines.push(`- 编号 \`${aid}\`(尾号 ${aid.slice(-6)})`);
        const factor = BT.variant_text('factor', { cls, variant: _gap_variant });
        const co = (card['co_signals'] ?? []).map((s: any) => BT.BLOCKING_CN[BT.canonical_class(String(s))] ?? '').filter(Boolean);
        lines.push(`- **因素**:${factor}${co.length > 0 ? `(并存信号:${co.join('、')})` : ''}`);
        if (cls === BT.B_AUTHORING_UNATTRIBUTED) {
          const _stop = _active_execution_terminal(mine, { facts: fs });
          lines.push('- **停止成因**:' + unproven_stop_cause_cn(_stop['stop_cause']));
        }
        const version_note = _xml_precedent_note(card);
        if (version_note) {
          lines.push(`- **版本差异**:${version_note}`);
        }
        lines.push(..._scenario1_evidence_lines(mine));
        lines.push(..._scenario1_missing_fields_lines(mine));
        const _synthetic_evs = new Set(['needs_decision_ledger', 'manual_audit']);
        const fact_shas = (card['basis'] ?? []).filter((b: any) => b['sha256'] && !_synthetic_evs.has(String(b['ev'] ?? ''))).map((b: any) => String(b['sha256'] ?? '').slice(0, 8));
        const ledger_n = (card['basis'] ?? []).filter((b: any) => _synthetic_evs.has(String(b['ev'] ?? ''))).length;
        const _cred_parts: string[] = [];
        if (fact_shas.length > 0) {
          _cred_parts.push(`依据 ${fact_shas.length} 条已落账事实(指纹 ${fact_shas.join('、')};全文按指纹在 \`facts.jsonl\` 可查)`);
        }
        if (ledger_n > 0) {
          _cred_parts.push(`另有 ${ledger_n} 条结构化凭据在案(欠定台账主张/手册差分对照,原文与出处引用可查)`);
        }
        lines.push('- **凭据**:' + (_cred_parts.length > 0 ? _cred_parts.join('；') : '本类归属来自案级状态投影,过程事实在 `facts.jsonl`'));
        const opts = BT.OPTIONS_ZH[cls] ?? [];
        const _direct_cls = _direct_abandon_class(mine);
        if (cls === BT.B_EXECUTION_INFRA && opts.length > 0) {
          lines.push(`- **处置**:${opts[0]}`);
        } else if (_direct_cls) {
          lines.push('- **处置**:' + BT.variant_text('user_action', { cls: _direct_cls, variant: _author_gap_variant(mine, _direct_cls) }));
        } else if (opts.length > 0) {
          lines.push(`- **处置选项**:${opts.join(' / ')}(重新发起本批编译,在对应问询中选择)`);
        }
        lines.push('');
      }
    }
  }
  const { render_cn } = require("./engine_disclosure");
  lines.push(...render_cn(fs, report));
  const _dc = report['defect_candidates'] ?? {};
  lines.push('---');
  const _ux = report['unsuccessful_xlsx'];
  let _uns_claim = '';
  if (Object.keys(bad).length > 0) {
    if (_ux === true) {
      _uns_claim = '、`unsuccessful_cases.xlsx`+`unsuccessful_cases.md`(未通过卷与详报)';
    } else if (_ux === false) {
      _uns_claim = '、`unsuccessful_cases.md`(未通过详报;xlsx 未能产出)';
    } else {
      _uns_claim = '、`unsuccessful_cases.xlsx`+`unsuccessful_cases.md`(未通过卷与详报)';
    }
  }
  lines.push('交付物:`case.xlsx`(通过卷)' + _uns_claim + (_dc ? `、\`defect_candidates.md\`(工程与产品处置候选单,${Number(_dc['count'] ?? 0)} 案,含结构化表单与处置轨迹)` : '') + '、`engine_report.json`(机读)。全部过程事实在 `facts.jsonl`,可据此核对,亦可手动重新发起编译。');
  return lines.join('\n') + '\n';
}

export function render_engine_errors_md(fs: Record<string, any>[], manifest: Record<string, any>, population: string[], terminal_note: string = ''): string {
  const EE = require("./engine_errors");
  const C = require("./engine_checkpoints");
  const F = require("./facts");
  const { scrub_value } = require("../security_scrub");
  const records = F.this_run_slice(fs).filter((row: any) => [EE.ENGINE_ERROR_EVENT, 'engine_condition_disclosure'].includes(String(row['ev'])));
  const lines = [`# 引擎错误与条件披露 — ${_batch_name(manifest)}`, `> 生成 ${new Date().toLocaleString('sv-SE').slice(0, 16)} · 本轮共 ${records.length} 条记录`, ''];
  if (terminal_note) {
    lines.push(`> 调用方收口说明：${scrub_value(terminal_note, { scrub_paths: false })}`, '');
  }
  function raw_block(label: string, value: any): void {
    const safe = scrub_value(value, { scrub_paths: false });
    const text = typeof safe === 'string' ? safe : JSON.stringify(safe, null, 2);
    const max_backticks = Math.max(3, ...(text.match(/`+/g) ?? []).map((m: string) => m.length), 0) + 1;
    const fence = '`'.repeat(max_backticks);
    lines.push(`- ${label}：`, '', fence, text, fence);
  }
  for (const err of records) {
    let code = String(err['code'] ?? '');
    const aid = String(err['aid'] ?? '');
    const diagnostic = String(err['diagnostic_id'] ?? err['error_id'] ?? '');
    let verified = false;
    let label: string;
    if (err['ev'] === 'engine_condition_disclosure') {
      try {
        C.validate_condition_disclosure(err);
        label = '观察条件（责任未核）';
      } catch {
        label = '条件记录校验未通过（责任未核）';
      }
      code = String(err['legacy_code'] ?? '');
    } else if (err['schema'] === C.SCHEMA) {
      try {
        C.validate_error(err);
        verified = true;
        label = err['owner'] === 'engine' ? '已验证内部契约违例' : 'API响应记录';
      } catch {
        label = '历史或证明未闭合记录（责任未核）';
      }
    } else {
      label = '历史错误记录（责任未核）';
    }
    const title = code in C.BY_CODE ? C.BY_CODE[code].title_cn : EE.CODE_TITLE_CN[code] ?? '未登记的历史编号';
    lines.push(`## ${label} — ${diagnostic || '旧码 ' + (code || '(缺码)')}`);
    lines.push(`- 编号/标签：\`${code || '(未记录)'}\` · ${title}`);
    if (err['ev'] === 'engine_error' && err['schema'] !== C.SCHEMA && code) {
      lines.push(`- 历史机读标签：\`ENGINE ERROR ${code}\`（保留旧字节，不补判当前责任）。`);
    }
    lines.push(`- 检查点/调用点：\`${String(err['site'] ?? '未记录')}\``);
    if (code in C.BY_CODE && C.BY_CODE[code].implementation_status === 'reserved') {
      lines.push('- 该编号已预留，尚没有当前可用的内部契约证明检查器。');
    }
    if (aid) {
      lines.push(`- 触发用例：\`${aid}\`（尾号 ${aid.slice(-6)}）`);
    }
    if (err['source_location']) {
      raw_block('原始调用位置', err['source_location']);
    }
    if (verified) {
      const side = err['owner'] === 'engine' ? '内部契约检查侧' : '响应记录来源侧';
      lines.push(`- ${side}：\`${err['owner']}\`；登记作用域：\`${err['scope']}\`；登记策略：\`${err['mode']}\`。实际处置须由对应事实确认。`);
      if (err['owner'] === 'engine') {
        raw_block('内部契约声明', err['expected']);
        lines.push(`- 可复核证明摘要：\`${err['proof_sha256']}\``);
      }
    } else if ('owner' in err) {
      lines.push(`- 原记录责任标签：\`${err['owner']}\`；本报告未将该标签认定为已验证责任。`);
    }
    if (!verified && code in EE.CODE_CAUSE_CN) {
      lines.push(`- 旧编号说明：${EE.CODE_CAUSE_CN[code]}`);
    }
    if ('observed' in err) {
      raw_block('原始 observed（沿用既有脱敏）', err['observed']);
    }
    const detail = String(err['detail'] ?? '');
    if (detail) {
      raw_block('原记录 detail（沿用既有脱敏）', detail);
    }
    lines.push('');
  }
  const { render_unverifiable_errors_cn } = require("./engine_disclosure");
  lines.push(...render_unverifiable_errors_cn(fs));
  lines.push(..._authoring_attempt_requirement_lines(fs));
  lines.push('---', '', '## 调用方提供的人口清单', '', `共 ${population.length} 个案号；逐案执行、隔离、暂停和交付状态以对应事实及凭据为准。`, '');
  lines.push(...population.map((aid) => `- \`${aid}\``));
  lines.push('');
  return lines.join('\n');
}

export function render_defect_candidates_md(entries: Record<string, any>[], manifest: Record<string, any>): string {
  const lines = [`# 工程与产品处置候选单 — ${_batch_name(manifest)}`, `> 生成 ${new Date().toLocaleString('sv-SE').slice(0, 16)} · 共 ${entries.length} 案 · 候选非终判`, ''];
  for (const e of entries) {
    const _dc_aid = String(e['autoid'] ?? '');
    lines.push(`## ${e['title'] || '用例 …' + _dc_aid.slice(-6)}`);
    const _owner = String(e['action_owner'] ?? 'product');
    const _owner_cn = _owner === 'engine' ? '引擎工程' : '产品';
    const _kind_cn = _owner === 'engine' ? '工程修复候选（非产品缺陷）' : '产品缺陷候选';
    lines.push(`- 负责人:${_owner_cn} · ${_kind_cn} · 候选非终判`);
    if (e['owner_action']) {
      lines.push(`- 负责人动作:${e['owner_action']}`);
    }
    if (e['device_evidence_binding'] === 'unverified') {
      lines.push('- 执行依据:未绑定到对应的有效执行结果；模型主张保留待核。');
    } else if (e['device_evidence_binding'] === 'operator_ruling') {
      lines.push('- 判断来源:用户裁决；此标记不表示设备实测凭据已闭合。');
    }
    const _uc = e['user_confirmed'];
    let _uc_tag: string;
    if (String(e['action_owner'] ?? '') === 'engine') {
      _uc_tag = ' · 工程修复候选 / 非产品缺陷';
    } else if (_uc === true) {
      _uc_tag = ' · **你已确认为产品缺陷**';
    } else if (_uc === false) {
      _uc_tag = ' · 机器疑似 / 待后续核验';
    } else {
      _uc_tag = ' · 待条件核验(你的回答附有条件,条件尚未验证)';
    }
    lines.push(`- 编号 \`${_dc_aid}\`(尾号 ${_dc_aid.slice(-6)}) · 当前状态:${STATUS_CN[String(e['status'])] ?? e['status']}` + _uc_tag);
    const claims = e['claims'] ?? [];
    if (claims.length > 0) {
      lines.push('\n**缺陷主张**(全史,后轮改判不隐去先前主张):');
      for (const cl of claims) {
        const _rd = cl['is_terminal'] ? '引擎自动裁决' : `第 ${cl['round']} 轮`;
        lines.push(`- ${_rd}:${cl['user_note'] ?? '(详见 facts.jsonl 缺陷候选记录)'}`);
        if (cl['evidence']) {
          lines.push('  ```device-evidence\n  ' + clean_device_echo(String(cl['evidence']), 300) + '\n  ```');
        }
      }
    } else {
      lines.push(`\n**缺陷主张**:${e['latest_claim'] ?? '(详见 facts.jsonl 缺陷候选记录)'}`);
    }
    const form = e['form'] ?? {};
    if (Object.keys(form).length > 0) {
      lines.push('\n**结构化表单**:');
      const fields: [string, string][] = [['repro', '复现步骤'], ['expected_with_source', '预期(含出处)'], ['actual', '实际'], ['version', '版本'], ['ticket_id', '单号']];
      for (const [key, label] of fields) {
        const raw = form[key];
        let v: string;
        if (key === 'expected_with_source' && typeof raw === 'object' && raw !== null) {
          const source = typeof raw['source'] === 'object' && raw['source'] !== null ? raw['source'] : {};
          const receipt = typeof source['receipt'] === 'object' && source['receipt'] !== null ? source['receipt'] : {};
          const source_label_map: Record<string, string> = { 'manual': '手册来源已核验', 'precedent': '验证先例来源已核验', 'footprint': '设备事实来源已核验' };
          let source_label = source_label_map[String(source['kind'] ?? '')] ?? '来源已核验';
          if (receipt['line_start']) {
            source_label += `，第 ${Number(receipt['line_start'])} 行`;
          }
          v = `${String(raw['expected'] ?? '').trim()} [${source_label}]`.trim();
        } else {
          v = String(raw ?? '').trim();
        }
        if (v) {
          lines.push(`- ${label}:${v}`);
        }
      }
    }
    const trail = e['disposition_trail'] ?? [];
    if (trail.length > 0) {
      const words: string[] = [];
      for (const t of trail) {
        const w = DISP_CN[String(t['disposition'])] ?? String(t['disposition']);
        let r: string;
        if (t['by_user']) {
          r = '用户裁决';
        } else if (t['is_terminal']) {
          r = '引擎自动裁决';
        } else {
          r = `第${t['round']}轮`;
        }
        words.push(`${r} ${w}${t['by_user'] ? '(你的裁决)' : ''}`);
      }
      lines.push('\n**处置轨迹**:' + words.join(' → '));
    }
    lines.push('');
  }
  return lines.join('\n') + '\n';
}

export function public_defect_candidates(entries: Record<string, any>[]): Record<string, any>[] {
  const public_ = deepcopy(entries);
  const kind_cn: Record<string, string> = { 'manual': '手册', 'precedent': '验证先例', 'footprint': '设备事实' };
  for (const entry of public_) {
    const form = entry['form'];
    if (typeof form !== 'object' || form === null) continue;
    const expected = form['expected_with_source'];
    if (typeof expected !== 'object' || expected === null) continue;
    const source = expected['source'];
    if (typeof source !== 'object' || source === null) continue;
    const receipt = typeof source['receipt'] === 'object' && source['receipt'] !== null ? source['receipt'] : {};
    const line_info: Record<string, any> = receipt['line_start'] ? { 'line_start': Number(receipt['line_start']), 'line_end': Number(receipt['line_end'] ?? receipt['line_start']) } : {};
    expected['source'] = {
      'type': kind_cn[String(source['kind'] ?? '')] ?? '已核验来源',
      'verified': Boolean(receipt['sha256']),
      'sha256': String(receipt['sha256'] ?? ''),
      ...line_info,
    };
  }
  return public_;
}
