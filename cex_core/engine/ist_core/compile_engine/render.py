# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/render.py（sha256 a8cf9e5655593691）。不在这里手改。
from __future__ import annotations
import copy
import re
import time
from cex_core.engine.ist_core.compile_engine.execution_failure import is_runtime_infrastructure_terminal_fact
from cex_core.engine.ist_core.display_lexicon import ATTRIBUTION_EVIDENCE_REACQUISITION_CN, AUTHORING_EVIDENCE_UNCLOSED_CN, GOVERNANCE_END_UNCLOSED_CN, EXECUTION_CAUSE_UNCONFIRMED_CN, AUTHORITY_DECISION_BLOCKED_CN, AUTHORITY_UNVERIFIED_BLOCKED_CN, UNATTRIBUTED_AUTHORING_STOP_CN, UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN, unproven_stop_cause_cn, DELIVERY_INCOMPLETE_REASON_CN as _DELIVERY_INCOMPLETE_REASON_CN, PREFLIGHT_ATLAS_GAP_NOUN_CN, PREFLIGHT_CONFIG_NOUN_CN, PREFLIGHT_RESIDUAL_NOUN_CN, PREFLIGHT_PROGRESS_LABEL, preflight_head_line_cn
STATUS_CN = {'quarantined': '引擎缺陷隔离（待修复验证）', 'deliverable': '验证通过', 'subset_verified': '单独验证通过(待整卷复验)', 'authored': '已编写(未上机)', 'failed': '上机未通过', 'contradicted': '单独能过、整卷复验会挂(用例间相互干扰)', 'failed_terminal': '按裁决收尾(未通过卷)', 'escalated': '引擎机械分流中', 'awaiting_user': '等待你的决定', 'suspended': '挂起(下批继续)', 'unsupported_feature': '当前设备不支持所需能力(共探确认)', 'pending': '未开始', 'composed': '已写好用例规格(excel 尚未生成)', 'delivery_blocked': '验证通过但卷面缺案尾清理——暂不交付(重编补自清后可交付)', 'broken': '未跑成(执行中断/日志陈腐/级联受害)——结论无效', 'broken_errored': '未跑成·断言/命令写坏了(断言被设备实际回显反证,或命令执行失败)——原样复跑必再错', 'broken_blocked': '未跑成·设备不可达(ping 不通)——复跑救不了死设备,需恢复环境后继续', 'broken_aborted': '未跑成·测试框架自身崩溃(非用例、非设备问题)', 'broken_verdict_unrecognized': '未跑成·框架返回了认不出的裁决值(非用例、非设备问题,可能是框架版本变化)'}
CTX_CN = {'delivery': '整卷连跑复验', 'subset': '单独验证'}
LAYER_CN = {'G': '设备拒绝了命令(语法/能力)', 'E': '环境/测试设备问题', 'V': '用例断言或验证机制问题', 'transient': '疑似偶发波动', 'dispatch': '引擎把验证命令发到了错误通道', 'product_defect': '疑似产品缺陷', 'user': '用户裁决', 'engine': '引擎自动判定(非设备实测结论)'}
DISP_CN = {'reflow': '带反馈重新编写', 'frozen': '原方法已证无效,换法重编', 'env_blocked': '按环境阻塞收尾', 'defect_candidate': '疑似产品缺陷，保留证据待核', 'fixed': '已修复待复跑', 'rerun_isolated': '保留当前卷面复跑核验', 'ist_core_defect': 'IST-Core 派发通道缺陷(修复后可重入)', 'user_stop': '按你的裁决停止(未通过如实报告)', 'engineering_fault': '工程故障(引擎缺口,已呈报,非产品缺陷)', 'expectation_suspect': '预期值可疑(需核对出处)', 'transient': '疑似偶发波动'}
_ESC_SUBCLASS_CN = {'no_output': '本轮编写未产出(可能撞到并发或墙钟限制)', 'not_executed': '连续多轮未能在设备上跑成', 'no_ledger_channel': '编写侧的终态声明没走对应的结构化落账(引擎已先自行重试一次)', 'harness_fault': '测试框架自身在收集/初始化阶段崩溃(非用例、非设备)', 'verdict_unrecognized': '框架返回了不在认识范围内的裁决值(非用例、非设备)', 'worker_envelope_invalid': '编写侧没有交回引擎认得的结果信封(非用例、非设备)'}
_ESC_ROUTE_CN = {'no_output': '重编', 'not_executed': '设备已处理复跑'}
SHAPE_CN = {'manual_vs_device': '手册与实机不符', 'expected_vs_observed': '预期结果与上机行为不符', 'method_vs_implementation': '验证方法与功能实现不符', 'ordering_vs_persistence': '执行顺序与持久化状态互扰', 'other': '意图记载有差异'}
ACTION_CN = {'self_cleanup': '让这个用例结束时清理自己留下的持久产物', 'recompile_directed': '按已找到的方向重新编写', 'rerun_isolated': '不改卷面,单独复跑对照确认', 'vary_form': '换一种配置形态实现同一意图(坐实/排除产品缺陷)'}
_DEFECT_DISPATCH = 'dispatch_channel'
_DEFECT_ON_DEVICE = 'on_device_attempts'
_DEFECT_ENGINE_ARTIFACT = 'engine_artifact'
_DEFECT_AUTHORING_EVIDENCE = 'authoring_evidence'
_DEFECT_ARTIFACT_CN = {'final_volume_identity_failed': '最终交付卷的身份自检没通过', 'final_volume_authority_unverified': '最终交付卷的来源权威链没核验完成', 'final_volume_missing': '最终交付卷不在盘上', 'case_absent_from_final_volume': '本案不在最终交付卷里', 'case_state_outside_v12_terminal_graph': '本案停在终态图之外的状态上', 'engine_budget_exhausted_turn_budget': '编写这一案时引擎自己的轮次预算先用尽（与用例内容无关）', 'engine_budget_exhausted_wallclock': '编写这一案时引擎自己的时间预算先用尽（与用例内容无关）'}

def _execution_cause_unconfirmed(fact: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine.execution_failure import FailureCategory
    return fact.get('ev') == 'ist_core_defect' and type(fact.get('attempt')) is int and (fact.get('category') == FailureCategory.UNKNOWN.value)

def _is_unattributed_stop(fact: dict) -> bool:
    """编写侧停了、责任没核出来那一格。用户面各处只认这一个谓词（单源在
    `authoring_stops.is_unattributed_authoring_stop`）。"""
    from cex_core.engine.ist_core.compile_engine.authoring_stops import is_unattributed_authoring_stop
    return is_unattributed_authoring_stop(fact)

def _unattributed_stop_state_cn(fact: dict) -> str:
    """现状一句 + 账上那条成因码的中文释义。不含行动，也不给任何一方定责。"""
    from cex_core.engine.ist_core.compile_engine.contradiction_stop import is_contradiction_stop
    if is_contradiction_stop(fact):
        from cex_core.engine.ist_core.compile_engine.forced_closure import reason_cn
        return reason_cn(fact)
    return f"{UNATTRIBUTED_AUTHORING_STOP_CN}。账上记的停止成因：{unproven_stop_cause_cn(fact.get('stop_cause'))}。"

def _defect_family(fact: dict) -> str:
    if fact.get('reason_code') == 'authoring_evidence_unclosed':
        return _DEFECT_AUTHORING_EVIDENCE
    if str(fact.get('reason_code') or '') == 'dispatch_channel_misroute':
        return _DEFECT_DISPATCH
    if type(fact.get('attempt')) is int and fact.get('category'):
        return _DEFECT_ON_DEVICE
    return _DEFECT_ENGINE_ARTIFACT

def _authority_chain_error_text(fact: dict, facts: list[dict] | None) -> str:
    """取本案权威链失败的脱敏首因；三键对不上就不带——宁可不说，不说错。

    诊断本来就落在 ``authority_reconcile_failed.error_text``（已 scrub、已截断），
    但那条事实全仓零读点。终态 fact 自己不带 ``artifact_sha256`` 也不带 ``reasons``，
    所以配对要经同案的收口卷面失败事件中转（新账签
    ``final_volume_authority_unverified``，三批冻结语料里是旧名
    ``final_volume_identity_failed`` + ``failure_axis=authority_chain``，两者载荷同构）：

        终态(reason_code + failure_axis)
          → 该事件(reasons 前缀集 + expected_artifact_sha256)
            → authority_reconcile_failed(reason_code 落在前缀集内 ∧ artifact_sha256 相同)

    三键互证不通过就返回空串：权威链本来就是「责任待核实」，配错一条首因比不给更糟。
    """
    from cex_core.engine.ist_core.compile_engine import terminal_outcomes as _TO
    rows = [row for row in facts or [] if isinstance(row, dict)]
    aid = str(fact.get('aid') or '')
    if not aid or not rows:
        return ''
    volume = next((row for row in reversed(rows) if str(row.get('aid') or '') == aid and row.get('ev') in _TO.FINAL_VOLUME_FAILURE_EVENTS), {})
    prefixes = {str(item or '').partition(':')[0] for item in volume.get('reasons') or [] if str(item or '')}
    artifact = str(volume.get('expected_artifact_sha256') or '')
    if not prefixes or not artifact:
        return ''
    match = next((row for row in reversed(rows) if str(row.get('aid') or '') == aid and row.get('ev') == 'authority_reconcile_failed' and (str(row.get('reason_code') or '') in prefixes) and (str(row.get('artifact_sha256') or '') == artifact)), {})
    return str(match.get('error_text') or '').strip()

def _defect_artifact_cause_cn(fact: dict, facts: list[dict] | None=None) -> str:
    from cex_core.engine.ist_core.compile_engine import forced_closure as FC
    reason_code = str(fact.get('reason_code') or '')
    if reason_code == 'governance_end_unclosed':
        return GOVERNANCE_END_UNCLOSED_CN
    if reason_code in FC.FORCED_CLOSURE_DISPLAY_REASONS:
        return FC.reason_cn(fact)
    if reason_code.startswith('engine_error_'):
        from cex_core.engine.ist_core.compile_engine import engine_errors as _EE
        title = _EE.CODE_TITLE_CN.get(reason_code[len('engine_error_'):]) or ''
        if title:
            return title
    from cex_core.engine.ist_core.compile_engine import terminal_outcomes as _TOC
    if reason_code in _TOC.FINAL_VOLUME_FAILURE_EVENTS and str(fact.get('failure_axis') or '') == _TOC.AUTHORITY_CHAIN_AXIS:
        _cause = '收口来源权威链未核验完成，卷面身份及具体责任仍待核实'
        _first = _authority_chain_error_text(fact, facts)
        return f'{_cause}；未核成的环节留证：{_ellip(_first, 240)}' if _first else _cause
    return _DEFECT_ARTIFACT_CN.get(reason_code, '引擎自有产物没过引擎自己的检查')

def _is_env_engine_error_terminal(fact: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine import engine_errors as _EE
    return str(fact.get('reason_code') or '') == f'engine_error_{_EE.E_ENVIRONMENT}'

def _is_contract_engine_error_terminal(fact: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine import engine_errors as _EE
    return str(fact.get('reason_code') or '') == f'engine_error_{_EE.E_CONTRACT_STAMP}'

def _is_worker_timeout_engine_error_terminal(fact: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine import engine_errors as _EE
    return str(fact.get('reason_code') or '') == f'engine_error_{_EE.E_WORKER_TIMEOUT}'

def _api_engine_error_terminal_code(fact: dict) -> str:
    from cex_core.engine.ist_core.compile_engine import engine_errors as _EE
    reason_code = str(fact.get('reason_code') or '')
    prefix = 'engine_error_'
    if not reason_code.startswith(prefix):
        return ''
    code = reason_code[len(prefix):]
    return code if code in _EE.API_SIDE_CODES else ''
_API_OWNER_ACTION_CN = {'0016': '核对API接口的原始配额响应及对应账户限制，按已确认条件恢复调用。', '0017': '核对API接口的失败与重试记录，恢复条件满足后重试。', '0018': '核对API接口拒绝的原始请求和响应，按证据修正调用条件。', '0019': '核对API接口返回的身份、权限或用量限制，按原始响应处理。'}
_AUTHORING_CAUSE_CN = {'verified_authoring_attempt_failure': '已核验的编写失败', 'submission_rejected': '交卷被拒', 'no_output': '编写孔无产出', 'device_result_case_side': '上机后归因在用例侧', 'compile_policy_exhausted': '有限规则策略耗尽', 'worker_claim_not_compilable': '编写侧主张不可编(未受理)'}

def _is_worker_claim_handoff_terminal(fact: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine.terminal_credentials import AUTHORING_ROUTE_WORKER_CLAIM_HANDOFF
    return str(fact.get('settlement_route') or '') == AUTHORING_ROUTE_WORKER_CLAIM_HANDOFF

def _authoring_causes_cn(fact: dict) -> str:
    counts: dict[str, int] = {}
    for row in fact.get('round_causes') or []:
        if not isinstance(row, dict):
            continue
        cause = str(row.get('cause') or '')
        counts[cause] = counts.get(cause, 0) + 1
    parts = [f'{_AUTHORING_CAUSE_CN.get(cause, cause)} {n} 轮' for cause, n in counts.items()]
    return '、'.join(parts) if parts else '原因记录缺失'

def _execution_terminal_status_cn(fact: dict, *, facts: list[dict] | None=None) -> str:
    from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block
    if is_authority_block_terminal(fact):
        if is_authority_unverified_block(fact):
            return AUTHORITY_UNVERIFIED_BLOCKED_CN
        return AUTHORITY_DECISION_BLOCKED_CN if authority_decision_confirmed(fact, facts or []) else '来源待裁记录未核验'
    if _is_unattributed_stop(fact):
        from cex_core.engine.ist_core.compile_engine.contradiction_stop import is_contradiction_stop
        if is_contradiction_stop(fact):
            return '阻塞（判决矛盾本轮未消解）'
        return UNATTRIBUTED_AUTHORING_STOP_CN
    event = str(fact.get('ev') or '')
    if event == 'ist_core_defect' and fact.get('reason_code') == 'governance_end_unclosed':
        return GOVERNANCE_END_UNCLOSED_CN
    if _execution_cause_unconfirmed(fact):
        return EXECUTION_CAUSE_UNCONFIRMED_CN
    if is_runtime_infrastructure_terminal_fact(fact):
        return '阻塞(本轮执行基础设施未闭合)'
    if event == 'ist_core_defect':
        family = _defect_family(fact)
        if family == _DEFECT_AUTHORING_EVIDENCE:
            return AUTHORING_EVIDENCE_UNCLOSED_CN
        if family == _DEFECT_DISPATCH:
            return f"IST-Core 缺陷({DISP_CN['ist_core_defect']})"
        if family == _DEFECT_ON_DEVICE:
            return 'IST-Core 缺陷(同一执行身份三次仍未跑成)'
        return f'IST-Core 缺陷({_defect_artifact_cause_cn(fact, facts)})'
    if event == 'authoring_failure':
        if _is_worker_claim_handoff_terminal(fact):
            return '模型未找到解决方案(编写侧主张：不可编，未受理)'
        return '模型未找到解决方案(编写轮次用尽，每一轮都败在编写侧)'
    if event == 'unable_to_compile' and fact.get('category') == 'connection':
        return '无法编写(平台限制：连续三次无法完成设备连接)'
    if event == 'unable_to_compile':
        return '无法编写(设备前提不具备)'
    return ''

def _active_execution_terminal(mine: list[dict], *, facts: list[dict] | None=None) -> dict:
    from cex_core.engine.ist_core.compile_engine import views as _V
    return _V.active_execution_terminal(mine, facts=facts)

def _unverified_authority_record(mine: list[dict], facts: list[dict] | None) -> bool:
    from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import unverified_authority_pending
    rows = facts if facts is not None else mine
    aid = next((str(row['aid']) for row in reversed(mine) if row.get('aid')), '')
    merged = next((row for row in reversed(rows) if row.get('ev') == 'merged' and row.get('ctx') == 'delivery'), {})
    return unverified_authority_pending(rows, aid=aid, current_volume_sha256=str(merged.get('artifact_sha256') or ''))
_TS_PREFIX = re.compile('^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} +[\\d.]+ +- +')

def clean_device_echo(text: str, limit: int=0) -> str:
    from cex_core.engine.ist_core.security_scrub import scrub_text
    lines, blank = ([], False)
    for ln in scrub_text(text).splitlines():
        ln = _TS_PREFIX.sub('', ln).rstrip()
        if not ln:
            if blank:
                continue
            blank = True
        else:
            blank = False
        lines.append(ln)
    out = '\n'.join(lines).strip()
    return out[:limit] if limit > 0 else out

def _ellip(s: str, n: int) -> str:
    s = str(s or '')
    return s if len(s) <= n else s[:n].rstrip() + '…'

def _xml_precedent_note(card: dict) -> str:
    entry = next((item for item in card.get('basis') or [] if isinstance(item, dict) and item.get('field') in {'version_difference', 'xml_projection_anomaly'} and isinstance(item.get('details'), dict)), None)
    if entry is None:
        return ''
    details = entry['details']
    precedents = [item for item in details.get('precedents') or [] if isinstance(item, dict) and item.get('build') and item.get('oid')]
    if not precedents:
        return ''
    prior = '、'.join((f"{item['build']} 版本有 OID {item['oid']} 的真机 PASS 编写" for item in precedents))
    current = str(details.get('current_build') or '?')
    command = str(details.get('command') or '')
    nodes = '、'.join((str(value) for value in details.get('nearest_node_paths') or [])) or '无'
    if entry.get('field') == 'version_difference':
        conclusion = '疑似版本变动，不归因命令书问题（除非 XML 注入错误）'
    else:
        conclusion = '同 build 先例与 XML 自相矛盾，疑似 XML 注入或投影异常，不归因命令书问题'
    return f'{prior}；当前 build {current} 的 XML 未收录命令「{command}」；可得邻近节点路径：{nodes}；{conclusion}。'

def _scenario1_evidence_lines(mine: list[dict]) -> list[str]:
    fact = next((item for item in reversed(mine) if item.get('ev') == 'policy_abandon' and item.get('reason_code') == 'scenario1_spec_case_conflict' and isinstance(item.get('scenario1_evidence'), list)), None)
    if fact is None:
        return []
    records = [item for item in fact.get('scenario1_evidence') or [] if isinstance(item, dict)]
    lines: list[str] = []
    for index, record in enumerate(records, 1):
        spec_quote = str(record.get('spec_quote') or '')
        case_quote = str(record.get('case_quote') or '')
        spec_locator = str(record.get('spec_locator') or '')
        case_locator = str(record.get('case_locator') or '')
        incompatibility = str(record.get('incompatibility') or '')
        if not all((spec_quote, case_quote, spec_locator, case_locator, incompatibility)):
            continue
        if len(records) > 1:
            lines.append(f'- **规格书与用例原文对照 {index}**')
        else:
            lines.append('- **规格书与用例原文对照**')
        lines.append('  - **SPEC 逐字引用**:')
        lines.extend((f'    > {part}' for part in spec_quote.splitlines()))
        lines.append(f'  - **SPEC 定位**:`{spec_locator}`')
        lines.append('  - **用例逐字引用**:')
        lines.extend((f'    > {part}' for part in case_quote.splitlines()))
        lines.append(f'  - **用例定位**:`{case_locator}`')
        lines.append('  - **不相容说明**:')
        lines.extend((f'    > {part}' for part in incompatibility.splitlines()))
    return lines

def _scenario1_missing_fields_lines(mine: list[dict]) -> list[str]:
    fact = next((item for item in reversed(mine) if item.get('ev') == 'policy_abandon' and item.get('reason_code') == 'scenario1_case_incomplete'), None)
    if fact is None:
        return []
    from cex_core.engine.ist_core.compile_engine.questions import MISSING_FIELD_CN as _FIELD_CN, missing_fields_text as _fields_text
    fields = [field for field in fact.get('missing_fields') or [] if isinstance(field, str) and field in _FIELD_CN]
    if not fields:
        return []
    return [f'- **人工脑图缺项**:管辖规格书对这条人工脑图有表态，人工脑图缺少 {_fields_text(fields)}；缺的是人工脑图本身，编译期补不上']

def _decision_anchor(fact: dict, ordinal: int | None=None) -> str:
    if 'round' in fact:
        try:
            round_no = int(fact.get('round') or 0)
        except (TypeError, ValueError):
            round_no = -1
        if round_no > 0:
            return f'第{round_no}轮'
        if round_no == 0:
            return '批前自动化环境状态确认'
    if ordinal is not None and ordinal > 0:
        return f'本案事实序号{ordinal}'
    return '本案历史事实'

def _decision_display(fact: dict, ordinal: int | None=None, limit: int=80) -> str:
    from cex_core.engine.ist_core.compile_engine.questions import DECISION_TOKEN_LABELS
    raw = _ellip(str(fact.get('answer') or '').strip(), limit)
    token = str(fact.get('token') or '').strip()
    anchor = _decision_anchor(fact, ordinal)
    if bool(fact.get('freeform')):
        return f"{raw or '(自由输入为空)'}（{anchor}，自由输入，措辞可能已变）"
    if token in DECISION_TOKEN_LABELS:
        return DECISION_TOKEN_LABELS[token]
    if token:
        return f"该选项已退休（原文案:{raw or '(空)'}；{anchor}）"
    return f"{raw or '(空)'}（{anchor}，历史记录未绑定选项，措辞可能已变）"

def _decision_has_current_label(fact: dict) -> bool:
    from cex_core.engine.ist_core.compile_engine.questions import DECISION_TOKEN_LABELS
    return not bool(fact.get('freeform')) and str(fact.get('token') or '') in DECISION_TOKEN_LABELS

def _fact_ordinal(facts: list[dict], target: dict) -> int | None:
    for idx, fact in enumerate(facts, 1):
        if fact is target:
            return idx
    for idx, fact in enumerate(facts, 1):
        if fact == target:
            return idx
    return None
_REVISION_HDR = re.compile('^#+\\s*Revision\\b.*$', re.MULTILINE)
_RULING_HDR = re.compile('^#+\\s*裁决\\s*$', re.MULTILINE)

def _ruling_summary(ruling: str, limit: int=120) -> str:
    s = str(ruling or '').strip()
    if not s:
        return ''
    body = ''
    for seg in reversed(_REVISION_HDR.split(s)):
        seg = _RULING_HDR.sub('', seg)
        seg = re.sub('^#+\\s*', '', seg.strip(), flags=re.MULTILINE).strip()
        if seg:
            body = seg
            break
    body = re.sub('\\s+', ' ', body or _RULING_HDR.sub('', s)).strip()
    return body[:limit].rstrip() + '…' if len(body) > limit else body

def _replay_pending_question(mine: list[dict]) -> str:
    shown = [f for f in mine if f.get('ev') == 'ask_shown' and f.get('render_input')]
    if not shown:
        return ''
    fact = shown[-1]
    render_input = fact.get('render_input')
    if not isinstance(render_input, dict):
        return ''
    try:
        from cex_core.engine.ist_core.compile_engine.questions import build_ask_question
        question = str(build_ask_question(dict(render_input)).get('question') or '').strip()
    except Exception:
        return ''
    autoid = str(fact.get('aid') or '')
    if not autoid or autoid not in question or 'None' in question:
        return ''
    return question.replace('\n', ' ')

def case_timeline(mine: list[dict]) -> list[str]:
    out: list[str] = []
    for ordinal, f in enumerate(mine, 1):
        ev = f.get('ev')
        if ev == 'authored':
            r = int(f.get('round') or 0)
            out.append(f'第 {r} 次编写完成' + ('(重新编写)' if r > 1 else ''))
        elif ev == 'verdict':
            ctx = CTX_CN.get(str(f.get('ctx')), str(f.get('ctx')))
            res = str(f.get('result'))
            word = {'pass': '通过', 'fail': '未通过'}.get(res, '未跑成(结论无效)')
            out.append(f'{ctx}:{word}')
        elif ev == 'rollback':
            out.append('此前的通过结论被复验推翻,已从先例知识库撤销')
        elif ev == 'verdict_recovered':
            out.append('此前未通过的断言在同一卷面上转为通过(变好留痕)')
        elif ev == 'ask_panel':
            out.append('发现意图记载差异,向你呈报')
        elif ev == 'adopted':
            out.append('同一问题你此前已有裁决,直接沿用(免问)')
        elif ev == 'decision' and f.get('answer'):
            if str(f.get('provenance') or '').startswith('adopted:'):
                continue
            _r = f.get('round')
            _r_tag = f'(第{_r}轮)' if _decision_has_current_label(f) and _r is not None and (int(_r) > 0) else ''
            out.append(f'你的裁决{_r_tag}:{_decision_display(f, ordinal)}')
        elif ev == 'suspended':
            out.append('未作答,留待下批再问' if _is_no_answer_reason(str(f.get('reason') or '')) else '挂起,留待下批继续')
            _asked = _replay_pending_question(mine)
            if _asked:
                out.append(f'当时问你的是:{_asked}')
        elif ev == 'resumed':
            out.append('恢复处理')
        elif ev == 'delivery_blocked':
            out.append('验证通过,但卷面缺案尾清理(会污染后续用例),暂不交付')
    return out

def _latest_attribution(mine: list[dict]) -> dict:
    atts = [f for f in mine if f.get('ev') == 'attribution']
    return atts[-1] if atts else {}

def on_defect_candidate_list(mine: list[dict]) -> bool:
    return any((fact.get('ev') == 'attribution' and str(fact.get('disposition') or '') == 'defect_candidate' for fact in mine))

def on_engine_delivery_action_list(mine: list[dict], *, facts: list[dict] | None=None) -> bool:
    from cex_core.engine.ist_core.compile_engine.views import active_execution_pause
    pause = active_execution_pause(mine)
    if pause:
        return pause.get('pause_kind') != 'contra' and pause.get('basis_status') == 'source_unavailable'
    execution_terminal = _active_execution_terminal(mine, facts=facts)
    if is_runtime_infrastructure_terminal_fact(execution_terminal):
        return False
    if str(execution_terminal.get('ev') or '') == 'ist_core_defect':
        return True
    if any((fact.get('ev') == 'delivery_blocked' for fact in mine)):
        return True
    return str(_latest_attribution(mine).get('disposition') or '') == 'engineering_fault'

def delivery_incomplete_why_cn(reasons) -> str:
    return '、'.join((_DELIVERY_INCOMPLETE_REASON_CN[code] for code in reasons or [] if code in _DELIVERY_INCOMPLETE_REASON_CN)) or '本批的收口条件没有全部满足'

def _latest_semantic_attribution(mine: list[dict]) -> dict:
    from cex_core.engine.ist_core.compile_engine import facts as F
    semantic = [row for row in mine if row.get('ev') != 'attribution' or not (row.get('disposition') == 'user_stop' or row.get('user_stop'))]
    return F.current_attribution(semantic)

def _latest_panel_dict(mine: list[dict], read_json) -> dict:
    pf = [f for f in mine if f.get('ev') == 'ask_panel']
    if not pf:
        return {}
    return read_json(str(pf[-1].get('ref') or '')) or {}
_NOT_FIXPOINT_REASON_CN = {'hard_error': '本轮图状态为 error，该用例未走到定局（不要据此推断设备断连；以 facts.jsonl 里本轮最后一条 error/phase 为准）', 'attribution_projection_blocked': '框架归因投影的来源身份不可用或已漂移；请先同步 framework mirror，运行 scripts/gen_capability_atlas.py 重生成 capability_atlas/method_reference，再以同参数重试', 'attribution_evidence_reacquisition_required': ATTRIBUTION_EVIDENCE_REACQUISITION_CN, 'capped': '该用例的重编/复跑轮次已达上限,需要你的授权才能继续', 'command_domain_isolated': f'该用例里有配置命令{PREFLIGHT_ATLAS_GAP_NOUN_CN}可核对,本轮被单独隔离、没有上机;它不影响同批其它用例交付。等这条查看命令补齐后,以同参数续跑即可自动恢复', 'merge_blocked': '本轮组卷这一步被拦下,该用例没能进入上机卷', 'merge_rejected': '整卷合并被卷面规则拒绝,本轮没有可上机的卷,该用例因此没上机', 'contract_blocked': '本轮机械脑图无法读回，该用例未进入编写；修复后以同参数续跑', 'non_interactive': '本轮未对该用例采取进一步动作'}
_UNKNOWN_NOT_FIXPOINT_REASON_CN = '引擎未能说明本轮未推进的原因(属引擎缺口,请报工程)'

def _latest_command_domain_exclusion(mine: list[dict]) -> dict:
    excluded: dict = {}
    for fact in reversed(mine):
        if fact.get('ev') == 'command_domain_case_excluded':
            excluded = fact
            break
    if not excluded:
        return {}
    authored = [f for f in mine if f.get('ev') == 'authored']
    current = str((authored[-1] if authored else {}).get('artifact') or '')
    if current and str(excluded.get('artifact') or '') != current:
        return {}
    return excluded

def command_domain_isolation_reason_cn(mine: list[dict]) -> str:
    excluded = _latest_command_domain_exclusion(mine)
    if str(excluded.get('reason_code') or '') != 'command_domain_residual':
        return _NOT_FIXPOINT_REASON_CN['command_domain_isolated']
    disclosure = str(excluded.get('disclosure') or '').strip().rstrip('。')
    if disclosure:
        return disclosure
    return f'{PREFLIGHT_RESIDUAL_NOUN_CN}该用例要动的配置命令的{PREFLIGHT_CONFIG_NOUN_CN}行,当前环境给不了它净态,本轮被单独隔离、没有上机;它不影响同批其它用例交付。环境具备条件后重编本案即自动复检'

def _h_s0_polluter_cause(diag: dict) -> str:
    pol = [str(p.get('aid', ''))[-6:] for p in diag.get('polluters') or [] if isinstance(p, dict)][:3]
    if pol:
        return f"原记录列出前序用例(尾号 {'、'.join(pol)})，但没有独立证实这些用例导致了本案失败。"
    return '记录未给出已独立核验的影响来源。'

def _execution_pause_narrative(mine: list[dict], pause: dict) -> str:
    kind = str(pause.get('pause_kind') or '')
    if pause.get('basis_status') == 'source_unavailable':
        return '当前未取得与本次暂挂绑定的依据，原因尚未确认。本轮暂挂，保留原始记录。'
    if kind in {'api', 'governance', 'supply'}:
        return str(pause.get('reason') or '编写条件尚未闭合，本轮暂挂。')
    if kind == 'bed':
        from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
        source_sha = str(pause.get('source_fact_sha256') or '')
        diag = next((fact for fact in mine if source_sha and _fact_sha256(fact) == source_sha), {})
        if not diag or not str(diag.get('h_position') or '').startswith('h_s0'):
            return '本次暂挂的环境依据未确认状态残留及其责任方，保留原始记录，待重新核验。'
        return '本次绑定记录只提出前序状态影响假设。' + _h_s0_polluter_cause(diag) + '原暂挂记录保留；该假设不证明环境责任，也不能替代本案归因。'
    if kind == 'env':
        return '现有记录提示本案受测试环境或执行条件阻碍。本轮暂挂，处理后同参续跑核验。'
    if kind == 'contra':
        from cex_core.engine.ist_core.compile_engine.contradiction_stop import pause_narrative, pause_observations
        return pause_narrative(pause_observations(pause, mine) or {}, closing=False)
    return str(pause.get('reason') or '本轮暂挂，执行原因尚未闭合。')

def diagnosis_text(mine: list[dict], panel: dict | None=None, not_fixpoint_reason: str='', *, facts: list[dict] | None=None) -> str:
    from cex_core.engine.ist_core.compile_engine.views import active_execution_pause
    pause = active_execution_pause(mine)
    if pause:
        return _execution_pause_narrative(mine, pause)
    execution_terminal = _active_execution_terminal(mine, facts=facts)
    execution_event = str(execution_terminal.get('ev') or '')
    if execution_event == 'ist_core_defect' and execution_terminal.get('reason_code') == 'governance_end_unclosed':
        return GOVERNANCE_END_UNCLOSED_CN + '；原始停止记录与出处链已保留。'
    from cex_core.engine.ist_core.compile_engine import forced_closure as _FC
    if execution_event == 'ist_core_defect' and _FC.is_forced_landing(execution_terminal):
        return _FC.reason_cn(execution_terminal) + '；出处链与批级边界记录已保留，本批其余用例不受影响。'
    if _execution_cause_unconfirmed(execution_terminal):
        return EXECUTION_CAUSE_UNCONFIRMED_CN + '；原错误与执行身份保留，由 IST-Core 核查记录并继续处理。'
    from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block
    if is_authority_block_terminal(execution_terminal):
        if is_authority_unverified_block(execution_terminal):
            return AUTHORITY_UNVERIFIED_BLOCKED_CN + '；卷面与设备结论照常保留，具体分歧见权威对齐记录。'
        if not authority_decision_confirmed(execution_terminal, facts if facts is not None else mine):
            return '来源待裁记录的身份和凭据未核，当前处理缺口需由引擎复核。'
        return AUTHORITY_DECISION_BLOCKED_CN + '；当前产物与交付身份已核对，具体冲突见权威对齐记录。'
    if _is_unattributed_stop(execution_terminal):
        return _unattributed_stop_state_cn(execution_terminal)
    if _unverified_authority_record(mine, facts):
        _unverified = '收口来源权威链未核验完成；当前记录不能确认来源待裁或卷面变化，具体原因及责任仍待核实。'
        _first = _authority_chain_error_text({'aid': next((str(row['aid']) for row in reversed(mine) if row.get('aid')), '')}, facts if facts is not None else mine)
        return f'{_unverified}未核成的环节留证：{_ellip(_first, 240)}' if _first else _unverified
    if is_runtime_infrastructure_terminal_fact(execution_terminal):
        detail = str(execution_terminal.get('error_text') or '').strip()
        suffix = f'；生产者留证：{_ellip(detail, 240)}' if detail else ''
        return f'本轮执行基础设施（下发或结果回收通道）未闭合；卷面未因此被判为 IST-Core 产物缺陷，只阻塞该案，本批兄弟案继续{suffix}。'
    if execution_event == 'ist_core_defect':
        if _defect_family(execution_terminal) == _DEFECT_AUTHORING_EVIDENCE:
            return AUTHORING_EVIDENCE_UNCLOSED_CN + '；原始停止记录与出处链已保留。'
        if (_api_code := _api_engine_error_terminal_code(execution_terminal)):
            from cex_core.engine.ist_core.compile_engine import engine_errors as _EEA
            return f'历史记录包含 API 分类（{_EEA.CODE_TITLE_CN[_api_code]}，旧码 {_api_code}）；具体响应与当前处置分别按原始记录核对，其他组件的责任尚未由此确认。'
        if _is_env_engine_error_terminal(execution_terminal):
            return '运行环境不满足运行前提（环境错误 0004，判定经确认或多次未能上机执行坐实）；该用例按案级终局记账，修复权在环境侧。'
        if _is_contract_engine_error_terminal(execution_terminal):
            return '引擎给该用例盖不上意图/SPEC 身份章（引擎错误 0003，盘上没有本案的契约投影）；该用例按案级终局记账，本批其余用例不受影响，判为 IST-Core 缺陷。'
        if _is_worker_timeout_engine_error_terminal(execution_terminal):
            return '编写孔在一次有界自动恢复后仍未产出该用例（引擎错误 0001）；该用例按案级终局记账，本批其余用例不受影响，判为可重入的 IST-Core 缺陷。'
        _family = _defect_family(execution_terminal)
        if _family == _DEFECT_DISPATCH:
            return f"{LAYER_CN['dispatch']}，未达设备 CLI，判为 IST-Core 缺陷。"
        if _family == _DEFECT_ON_DEVICE:
            return '同一上机执行身份连续三次未完成；结构化错误码归入引擎拒收或未知执行故障，判为 IST-Core 缺陷。'
        if execution_terminal.get('reason_code') == 'legacy_mechanical_engineering_fault':
            return '历史机械归因被保存为兼容记录；当前责任仍须由本次有效凭据核实。'
        from cex_core.engine.ist_core.compile_engine import terminal_outcomes as _TOD
        if execution_terminal.get('reason_code') in _TOD.FINAL_VOLUME_FAILURE_EVENTS and execution_terminal.get('failure_axis') == _TOD.AUTHORITY_CHAIN_AXIS:
            return _defect_artifact_cause_cn(execution_terminal, mine) + '；保留原始记录，由引擎完成处理与复核。'
        return f'{_defect_artifact_cause_cn(execution_terminal, mine)}；问题出在引擎自有产物上，判为 IST-Core 缺陷。'
    if execution_event == 'authoring_failure':
        if _is_worker_claim_handoff_terminal(execution_terminal):
            return f'编写侧交回了结构化的「不可编」报告，但报告缺少引擎可复核的凭据、未被受理（{_authoring_causes_cn(execution_terminal)}）；该案就地收口把剩余轮次让给同批其它用例，作者内容未改、未报设备缺陷，判为模型未找到解决方案。'
        return f'编写轮次用尽，每一轮都败在编写侧（{_authoring_causes_cn(execution_terminal)}）；作者内容未改、未报设备缺陷，判为模型未找到解决方案。'
    if execution_event == 'unable_to_compile':
        if execution_terminal.get('category') == 'connection':
            return '同一上机执行身份连续三次未完成；结构化错误码均指向设备连接或运行环境不可达，作为平台限制归入无法编写终态。'
        return '同一上机执行身份连续三次未完成；设备结构化返回运行前提不具备，判为当前平台无法编写。'
    if not_fixpoint_reason in {'attribution_projection_blocked', 'attribution_evidence_reacquisition_required'}:
        reason_cn = _NOT_FIXPOINT_REASON_CN[not_fixpoint_reason]
        return f'本轮深归因未被消费——{reason_cn}。'
    att = _latest_semantic_attribution(mine)
    parts = []
    diags = [f for f in mine if f.get('ev') == 'diagnosis']
    diag = diags[-1] if diags else {}
    s0_note = ''
    if str(diag.get('h_position', '')).startswith('h_s0'):
        s0_note = '前序状态影响尚未证实；' + _h_s0_polluter_cause(diag)
    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
    last_verdict = next((fact for fact in reversed(mine) if fact.get('ev') == 'verdict'), {})
    candidates = [fact for fact in mine if fact.get('ev') == 's0_candidate' and last_verdict and (fact.get('source_fact_sha256') == _fact_sha256(last_verdict))]
    if candidates:
        s0_note = '记录中存在前序配置影响线索，尚未证实因果；本案仍依据独立执行证据归因。'
    hyp = str((panel or {}).get('hypothesis') or '').strip()
    shape = str((panel or {}).get('conflict_shape') or '')
    if hyp and (not parts):
        parts.append((f"{SHAPE_CN.get(shape, SHAPE_CN['other'])}:" if shape else '') + hyp)
    elif att and (not parts):
        cn = LAYER_CN.get(str(att.get('layer') or ''), '')
        if cn:
            parts.append(f'判断:{cn}。')
    if s0_note:
        parts.append(s0_note)
    if not att and (not hyp) and (not parts):
        if not_fixpoint_reason:
            reason_cn = _NOT_FIXPOINT_REASON_CN.get(not_fixpoint_reason, _UNKNOWN_NOT_FIXPOINT_REASON_CN)
            if not_fixpoint_reason == 'command_domain_isolated':
                reason_cn = command_domain_isolation_reason_cn(mine)
            verdicts = [f for f in mine if f.get('ev') == 'verdict']
            last_v = verdicts[-1] if verdicts else {}
            if str(last_v.get('result')) in ('broken', 'not_run'):
                return f'此用例未跑成(结论无效),不适用逐案根因分析——按规则处置是原样复跑而非分析;{reason_cn}。'
            return f'此用例本轮未被引擎推进——{reason_cn}。'
        return '本轮收口前未能完成原因分析(证据在案,可续跑补齐)。'
    from cex_core.engine.ist_core.compile_engine import facts as _F
    if att.get('evidence') and _F.attribution_source(att) == '':
        parts.append(f"关键证据:「{clean_device_echo(str(att.get('evidence')), 200)}」。")
    return ' '.join(parts) or '(证据在案,见事实台账)'

def _escalated_remedy_text(mine: list[dict]) -> str:
    from cex_core.engine.ist_core.compile_engine import facts as _F
    aid = str(mine[0].get('aid')) if mine else ''
    sub = _F.escalated_subclass(mine, aid)
    cause = _ESC_SUBCLASS_CN.get(sub, '引擎侧遇到无法自行推进的情况')
    deesc_decs = [f for f in mine if f.get('ev') == 'decision' and str(f.get('question_id', '')).startswith(f'deesc:{aid}:') and str(f.get('answer') or '').strip() and (str(f.get('token') or '') != 'suspend')]
    if not deesc_decs:
        if sub == 'no_ledger_channel':
            opts = '重编/工程故障呈报/保持'
        elif sub == 'harness_fault':
            opts = '工程故障呈报/保持'
        else:
            opts = f"{_ESC_ROUTE_CN.get(sub, '重编')}/缺陷候选/保持"
        return f'**去向**:{cause};引擎已呈报恢复问询(可选「{opts}」),答复后重跑同参数会按你的选择继续;未答复则重跑同参数会再次呈报。'
    last = deesc_decs[-1]
    if str(last.get('token')) == 'deesc_keep':
        n = _F.recovery_attempts(mine, aid)
        tried = f'(此前已尝试恢复 {n} 次)' if n else ''
        return f'**去向**:{cause}{tried};你选择保持,本用例暂不再自动重试。重跑同参数会沿用这次的保持,除非换了测试设备或产品版本——那种情况下会再次问你是否恢复。'
    _last_r = last.get('round')
    _last_tag = f'(第{_last_r}轮)' if _decision_has_current_label(last) and _last_r is not None and (int(_last_r) > 0) else ''
    _last_display = _decision_display(last, _fact_ordinal(mine, last), 24)
    return f'**去向**:{cause};已按你的裁决{_last_tag}「{_last_display}」处理,详见时间线。'

def _ledger_corrupt_type_cn(detail: str) -> str:
    d = str(detail or '')
    if d.startswith('UnicodeDecodeError'):
        return '文件编码损坏'
    if 'JSONDecodeError' in d:
        return 'JSON 格式损坏'
    return '文件内容损坏'

def _direct_abandon_class(mine: list[dict]) -> str:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.compile_engine.views import direct_abandon_terminal
    cls = str(direct_abandon_terminal(mine).get('blocking_class') or '')
    if not cls:
        latest = next((fact for fact in reversed(mine) if fact.get('ev') == 'policy_abandon' and fact.get('reason_code') in {'no_cli_equivalent', 'environment_prerequisite_gap', 'author_definition_gap', 'batch_user_abandon'}), {})
        expected = {'no_cli_equivalent': BT.A_NO_CLI_EQUIVALENT, 'environment_prerequisite_gap': BT.A_ENV_PREREQ_GAP, 'author_definition_gap': BT.A_AUTHOR_DEFINITION_GAP, 'batch_user_abandon': BT.A_BATCH_USER_ABANDON}.get(str(latest.get('reason_code') or ''), '')
        if latest.get('blocking_class') == expected:
            cls = expected
    return cls if cls in BT.ABANDON_USER_ACTION_ZH else ''

def _author_gap_variant(mine: list[dict], cls: str) -> str:
    """第八格才有变体；别的格恒空（取词函数按空值走默认表）。"""
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
    if str(cls or '') != BT.A_AUTHOR_DEFINITION_GAP:
        return ''
    aid = next((str(row.get('aid') or '') for row in mine if row.get('aid')), '')
    return TC.author_gap_variant(aid, mine) if aid else ''

def _direct_abandon_remedy_text(mine: list[dict]) -> str | None:
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    cls = _direct_abandon_class(mine)
    if not cls:
        return None
    variant = _author_gap_variant(mine, cls)
    text = '**去向**:' + BT.variant_text('reason', cls=cls, variant=variant)
    if cls == BT.A_NO_CLI_EQUIVALENT and any((item.get('ev') == 'environment_execution_disclosure' for item in mine)):
        return text + '本次不生成的原因是自动化环境不具备,不是用例或命令本身有问题——详见上方环境限制披露。'
    if cls == BT.A_AUTHOR_DEFINITION_GAP:
        latest = next((fact for fact in reversed(mine) if fact.get('ev') == 'policy_abandon' and fact.get('blocking_class') == BT.A_AUTHOR_DEFINITION_GAP), {})
        declaration = str(latest.get('author_gap_declaration') or '').strip()
        text += BT.variant_text('user_action', cls=cls, variant=variant)
        if declaration:
            text += '\n\n**' + BT.variant_text('declaration_label', variant=variant) + '**：' + declaration
        return text
    return text + BT.variant_text('user_action', cls=cls, variant=variant)

def _ledger_fate_remedy_text(mine: list[dict]) -> str | None:
    RECOVERED_BY = {'authored', 'verdict', 'de_escalated'}
    FATE = {'ledger_unreadable', 'question_unbuildable', 'question_form_blocked'}
    state: dict | None = None
    for f in mine:
        ev = f.get('ev')
        if ev in FATE:
            state = f
        elif ev in RECOVERED_BY:
            state = None
    if state is None:
        return None
    if state.get('ev') == 'ledger_unreadable':
        kind = _ledger_corrupt_type_cn(str(state.get('detail') or ''))
        return f'**去向**:此用例的待决记录文件损坏(无法解析,{kind}),本轮已隔离、未能向你呈报问题——需重新生成该用例的待决记录后复跑。'
    if state.get('ev') == 'question_form_blocked':
        return '**去向**:此用例的问询题面未通过机械格式校验，本轮没有向你呈现；这是引擎题面缺陷，需修复题面生成后复跑，不应被记成你未作答。'
    return '**去向**:此用例被判定为需你确认,但引擎未能从中构造出可回答的问题(待决项为空或与题面不匹配)——需检查该用例的待决项来源后复跑。'

def _awaiting_unasked_remedy_text(mine: list[dict]) -> str | None:
    RECOVERED_BY = {'decision', 'authored', 'verdict', 'de_escalated', 'adopted'}
    state: dict | None = None
    for f in mine:
        ev = f.get('ev')
        if ev == 'awaiting_user_unasked':
            state = f
        elif ev in RECOVERED_BY:
            state = None
    if state is None:
        return None
    if state.get('shown'):
        return '**去向**:此用例的确认面板本轮已呈报,但未被答复(非交互模式下无人应答/面板被跳过)——重跑同参数会再次呈报,请给出裁决。'
    return '**去向**:此用例本轮需要你确认,但批处理未能问到它(问询预算被本批其他用例用尽,或本轮以非交互方式运行、未进入问询环节)——重跑同参数会重新排队呈报。'

def _conditional_suspend_predicate(mine: list[dict]) -> str | None:
    last_susp: dict | None = None
    for f in mine:
        ev = f.get('ev')
        if ev == 'suspended':
            last_susp = f
        elif ev == 'resumed':
            last_susp = None
    if not last_susp or last_susp.get('source') != 'conditional_decision':
        return None
    qid = last_susp.get('question_id')
    cond = next((f for f in mine if f.get('ev') == 'conditional_decision' and f.get('question_id') == qid), None)
    return str(cond.get('condition_predicate') or '') if cond else None

def _latest_adopted_still_relevant(mine: list[dict]) -> dict | None:
    RECOVERED_BY = {'authored', 'verdict', 'de_escalated', 'decision'}
    adopted: dict | None = None
    for f in mine:
        ev = f.get('ev')
        if ev == 'adopted':
            adopted = f
        elif ev in RECOVERED_BY:
            adopted = None
    return adopted

def remedy_text(queue: list[dict], mine: list[dict], panel: dict | None=None, advanced_this_round: bool=False, *, facts: list[dict] | None=None) -> str:
    execution_terminal = _active_execution_terminal(mine, facts=facts)
    execution_event = str(execution_terminal.get('ev') or '')
    if execution_event == 'ist_core_defect' and execution_terminal.get('reason_code') == 'governance_end_unclosed':
        return f'**处理结论**：{GOVERNANCE_END_UNCLOSED_CN}。由 IST-Core 核查原始停止记录和预算依据。'
    if _execution_cause_unconfirmed(execution_terminal):
        return '**处理结论**：' + EXECUTION_CAUSE_UNCONFIRMED_CN + '。由 IST-Core 核对原始错误与执行条件后确定处理方向。'
    from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block
    if is_authority_block_terminal(execution_terminal):
        if is_authority_unverified_block(execution_terminal):
            return '**处理结论**：' + AUTHORITY_UNVERIFIED_BLOCKED_CN + '。确定这些预期值以哪一份来源为准后重新核验；其他案继续。'
        if not authority_decision_confirmed(execution_terminal, facts if facts is not None else mine):
            return '**处理结论**：来源待裁记录未核，由引擎核验当前产物、来源与凭据后继续处理。'
        return '**处理结论**：' + AUTHORITY_DECISION_BLOCKED_CN + '。修正记录中的冲突来源后重新核验；其他案继续。'
    if _is_unattributed_stop(execution_terminal):
        from cex_core.engine.ist_core.compile_engine.contradiction_stop import is_contradiction_stop
        if is_contradiction_stop(execution_terminal):
            return '**处理结论**：' + _unattributed_stop_state_cn(execution_terminal) + '。'
        return '**处理结论**：' + _unattributed_stop_state_cn(execution_terminal) + UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN + '。其他案继续。'
    if _unverified_authority_record(mine, facts):
        return '**处理结论**：来源权威链尚有未核缺口，由引擎补齐核验与披露，其他案继续。'
    if is_runtime_infrastructure_terminal_fact(execution_terminal):
        return '**结论**:本轮执行基础设施未闭合，该案按可重入阻塞结案；恢复下发/结果回收通道后重试本案，本批其余用例照常继续，无需为此修改用例。'
    if execution_event == 'ist_core_defect':
        if _defect_family(execution_terminal) == _DEFECT_AUTHORING_EVIDENCE:
            return f'**处理结论**：{AUTHORING_EVIDENCE_UNCLOSED_CN}。本次编写已结束；引擎需要核对出处链并修复处理缺口后重新验证，其他案继续。'
        if (_api_code := _api_engine_error_terminal_code(execution_terminal)):
            from cex_core.engine.ist_core.compile_engine import engine_errors as _EEA
            return f'**历史记录**:{_EEA.CODE_TITLE_CN[_api_code]}（旧码 {_api_code}）。按本条接口响应及当前暂停凭据处理；该分类不单独证明其他组件的责任。'
        if _is_env_engine_error_terminal(execution_terminal):
            from cex_core.engine.ist_core.compile_engine import facts as _F04
            _user_env = any((f.get('ev') == 'attribution' and str(f.get('disposition') or '') == 'env_blocked' and _F04.attribution_is_terminal(f) for f in mine))
            if _user_env:
                return '**结论**:按你的确认，该用例以环境阻塞终局（引擎错误 0004）——设备/跳转机/网络拓扑不满足运行前提，引擎无权自行修复；本批其余用例照常继续，环境处理好后可重新发起编译重走该用例。'
            return '**结论**:该用例卷面完好但连续多次未能上机执行，按环境错误终局（引擎错误 0004）——运行环境不满足运行前提，引擎无权自行修复；本批其余用例照常继续，环境处理好后可重新发起编译重走该用例。'
        if _is_contract_engine_error_terminal(execution_terminal):
            return '**结论**:这是 IST-Core 缺陷；引擎给该用例盖不上意图/SPEC 身份章（引擎错误 0003），缺章生成不出用例。本批其余用例照常继续；由引擎工程修复契约投影后重新发起编译重走该用例，当前无需用户修改用例。'
        if _is_worker_timeout_engine_error_terminal(execution_terminal):
            return '**结论**:这是 IST-Core 缺陷；编写孔自动恢复一次后仍未产出该用例（引擎错误 0001）。本批其余用例照常继续；由引擎工程修复编写链路后重新发起编译重走该用例，当前无需用户修改用例。平台无等价能力不从空转次数推断。'
        from cex_core.engine.ist_core.compile_engine import forced_closure as _FCN
        if _FCN.is_forced_landing(execution_terminal):
            from cex_core.engine.ist_core.display_lexicon import FORCED_CLOSURE_CASE_SCOPE_CN
            return f'**结论**:{_FCN.reason_cn(execution_terminal)}；{FORCED_CLOSURE_CASE_SCOPE_CN}，当前无需用户修改用例。'
        _family = _defect_family(execution_terminal)
        if _family == _DEFECT_DISPATCH:
            return '**结论**:这是 IST-Core 缺陷；修好派发通道后重入，不重编卷面，当前无需用户修改用例。'
        if _family == _DEFECT_ON_DEVICE:
            return '**结论**:这是 IST-Core 缺陷；须先修复引擎并完成回归，再以新编译轮重走完整判定链，当前无需用户修改用例。'
        if execution_terminal.get('reason_code') == 'legacy_mechanical_engineering_fault':
            return '**历史记录**:保留了机械归因；责任尚需复核，本条兼容标签不签发新的引擎缺陷。'
        return f'**结论**:这是 IST-Core 缺陷；{_defect_artifact_cause_cn(execution_terminal, mine)}，须先修复引擎并完成回归，再以新编译轮重走完整判定链，当前无需用户修改用例。'
    if execution_event == 'authoring_failure':
        if _is_worker_claim_handoff_terminal(execution_terminal):
            return '**结论**:模型未找到解决方案（编写侧主张：不可编，未受理）；这条历史主张不证明作者内容整体正确。编写侧交回的「不可编」报告缺少引擎可复核的凭据，本案就地终结、把剩余轮次让给同批其它用例；引擎能力更新后可用新的批名重新编译该用例。'
        return f"**记录结论**:模型未找到解决方案；该结论限于凭据绑定的尝试。记录的编写尝试为 {execution_terminal.get('rounds_used')} 轮，模型自述、输入范围与未核事项见案级凭据；后续编写须重新验证当前条件。"
    if execution_event == 'unable_to_compile':
        if execution_terminal.get('category') == 'connection':
            return '**结论**:连续三次仍无法完成设备连接，属于平台限制并归入无法编写；本案已如实终结，恢复平台连通性后可重新发起编译。'
        return '**结论**:当前平台不具备该用例所需前提，无法编写；本案已如实终结，同一平台条件下不再重试。'
    if queue:
        head = queue[0]
        act = ACTION_CN.get(str(head.get('action')), str(head.get('action')))
        line = f'**修复方案**:{act}'
        _dir = str(head.get('direction') or '').strip()
        if _dir:
            line += f'。方向:{_ellip(_dir, 160)}'
        rest = [ACTION_CN.get(str(q.get('action')), '') for q in queue[1:]]
        if any(rest):
            line += f"。若仍未通过,后续依次:{'、'.join((r for r in rest if r))}"
        return line + '。'
    from cex_core.engine.ist_core.compile_engine.views import _is_escalated
    if _is_escalated(mine):
        return _escalated_remedy_text(mine)
    from cex_core.engine.ist_core.compile_engine import facts as _F
    att = _latest_attribution(mine)
    disp = str(att.get('disposition') or '')
    decs = [f for f in mine if f.get('ev') == 'decision' and f.get('answer')]
    _src = _F.attribution_source(att)
    if disp == 'defect_candidate' and _src == 'engine_auto':
        return '**结论**:引擎已尽轮次(多次重试仍未能推进、未产生新证据),记为缺陷候选(`defect_candidates.md`);修复对应原因后可重新运行。'
    if disp == 'engineering_fault':
        return '**结论**:引擎侧遇到结构性缺口(非产品缺陷),已呈报记录、不计入缺陷候选单;该缺口需要工程侧后续处理,当前用例结果按未通过卷收尾。'
    if disp == 'defect_candidate' and _src == 'user':
        return '**结论**:你已确认为产品缺陷,已记入缺陷候选单(`defect_candidates.md`),该用例以缺陷结案。'
    if disp == 'defect_candidate':
        return '**结论**:疑似产品缺陷,已列入缺陷候选单(`defect_candidates.md`);坐实需换一种配置形态复现。'
    if disp in ('env_blocked', 'user_stop') and _F.attribution_is_terminal(att):
        _ld = decs[-1] if decs else None
        if _ld and str(_ld.get('provenance') or '').startswith('adopted:'):
            _shown = _decision_display(_ld, _fact_ordinal(mine, _ld))
            who = f'(依据此前批的同键判例「{_shown}」)'
        else:
            _ldr = _ld.get('round') if _ld else None
            _r_tag = f'第{_ldr}轮' if _ld and _decision_has_current_label(_ld) and (_ldr is not None) and (int(_ldr) > 0) else ''
            _who_stem = f'依据{_r_tag}你的裁决' if _r_tag else '依据你的裁决'
            _shown = _decision_display(_ld, _fact_ordinal(mine, _ld)) if _ld else ''
            who = f'({_who_stem}「{_shown}」)' if _ld else ''
        if disp == 'user_stop' or att.get('user_stop'):
            had_dc = any((f.get('ev') == 'attribution' and str(f.get('disposition')) == 'defect_candidate' for f in mine))
            tail = '此前轮次曾达缺陷候选,其主张与证据已汇总在缺陷候选单(`defect_candidates.md`)。' if had_dc else ''
            return f'**结论**:按你的止损裁决收尾{who},该用例记入未通过卷,下批可继续。{tail}'
        return f'**结论**:按环境/取舍收尾{who},该用例记入未通过卷,下批可继续。'
    _adopted = _latest_adopted_still_relevant(mine)
    if _adopted:
        _rs = _ruling_summary(_adopted.get('ruling') or '')
        return '**去向**:同一差异你此前已有裁决,本批直接沿用并按其重编' + (f'(裁决要点:{_rs})。' if _rs else '。')
    pf = [f for f in mine if f.get('ev') == 'ask_panel']
    if pf:
        from cex_core.engine.ist_core.compile_engine import _shared as _sh
        from cex_core.engine.ist_core.compile_engine.questions import effective_decision_token
        prnd = int(pf[-1].get('round') or 0)
        aid = str(pf[-1].get('aid') or '')
        answered = any((d.get('ev') == 'decision' and _sh.panel_qid_matches(d.get('question_id'), aid, prnd) and (effective_decision_token(d) in {'confirm', 'correct', 'defect', 'stop', 'downgrade'}) for d in mine))
        ask = str((panel or {}).get('ask') or '').strip()
        if not answered:
            return '**去向**:已向你呈报差异待确认' + (f'(问题:{ask})' if ask else '') + ',答复后按你的裁决继续。'
    blocked = [f for f in mine if f.get('ev') == 'delivery_blocked']
    if blocked and (not any((f.get('ev') == 'authored' for f in mine[mine.index(blocked[-1]):]))):
        return '**去向**:功能验证已通过,只差案尾清理步(自己留下的网络层配置要在案内恢复);下批续跑会带此反馈重新编写,补上后即可交付。'
    from cex_core.engine.ist_core.compile_engine.views import _is_suspended, active_execution_pause
    if _is_suspended(mine):
        _pause = active_execution_pause(mine)
        if _pause:
            if _pause.get('pause_kind') == 'contra':
                return '**去向**:' + _execution_pause_narrative(mine, _pause) + '；同参续跑会自动重入完整判定链。'
            if str(_pause.get('pause_kind') or '') in {'env', 'bed'}:
                return '**去向**:按环境/取舍收尾方向暂挂——本轮不签永久环境结论,该用例记入未通过卷;环境处理后同参续跑会自动重入完整判定链。'
            return '**去向**:执行结果的归因尚未闭合,本轮暂挂并保留原预期与原始执行记录;同参续跑会自动重入完整判定链。'
        _cond = _conditional_suspend_predicate(mine)
        if _cond:
            return f'**去向**:有条件确认,待核验:{_cond};核验前本用例先挂起。'
        if _no_answer_suspended(mine):
            return '**去向**:你未作答,本轮先挂起;重跑同参数会再次呈报请你裁决。'
        return '**去向**:已挂起;同参重跑会自动重入完整判定链。'
    _direct_abandon = _direct_abandon_remedy_text(mine)
    if _direct_abandon is not None:
        return _direct_abandon
    _fate = _ledger_fate_remedy_text(mine)
    if _fate is not None:
        return _fate
    _unasked = _awaiting_unasked_remedy_text(mine)
    if _unasked is not None:
        return _unasked
    if advanced_this_round:
        return '**去向**:本轮已复跑,结论仍为无结论。'
    return '**去向**:本轮引擎未复跑该用例(原因见顶部说明)。'

def _is_no_answer_reason(reason: str) -> bool:
    if not str(reason).startswith('auto:'):
        return False
    from cex_core.engine.ist_core.compile_engine import _shared as _sh
    kind = str(reason)[len('auto:'):].split(':')[0]
    return _sh.suspend_kind_renders_as_no_answer(kind)

def _no_answer_suspended(mine: list[dict]) -> bool:
    sus = [f for f in mine if f.get('ev') == 'suspended']
    return bool(sus) and _is_no_answer_reason(str(sus[-1].get('reason') or ''))

def _status_cn(status: str, mine: list[dict]) -> str:
    return _status_cn_with_facts(status, mine)

def _status_cn_with_facts(status: str, mine: list[dict], *, facts: list[dict] | None=None) -> str:
    if status == 'suspended' and _no_answer_suspended(mine):
        return '未作答(下批会再次问你)'
    if status == 'failed_terminal':
        execution_terminal = _active_execution_terminal(mine, facts=facts)
        if execution_terminal:
            return _execution_terminal_status_cn(execution_terminal, facts=facts if facts is not None else mine)
    if _unverified_authority_record(mine, facts):
        return '来源权威链未核验完成'
    return STATUS_CN.get(status, '未知状态')

def _rejection_cn(code: str) -> str:
    from cex_core.engine.ist_core.display_lexicon import not_compilable_rejection_cn
    return not_compilable_rejection_cn(code) if str(code or '').strip() else '（拒绝原因缺失）'

def _worker_claim_superseded(mine: list[dict]) -> bool:
    last_claim = max((index for index, fact in enumerate(mine) if fact.get('ev') == 'worker_claim'), default=-1)
    if last_claim < 0:
        return False
    return any((str(fact.get('ev') or '') in ('authored', 'composed', 'writeback', 'merged') for fact in mine[last_claim + 1:]))

def _unbound_device_claim_lines(mine: list[dict]) -> list[str]:
    from cex_core.engine.ist_core.compile_engine import facts as F
    claims = [row for row in mine if row.get('ev') == 'attribution' and F.scenario5_device_defect(row.get('layer'), row.get('disposition')) and F.scenario5_terminal_needs_run_evidence(row) and (not F.scenario5_attribution_has_evidence(row, mine))]
    if not claims:
        return []
    return ['\n**归因证据未闭合**:', f'- {len(claims)} 条模型设备缺陷主张没有绑定到对应的有效执行结果；这些主张未作为设备缺陷终局依据，原始判断仍保留在事实记录中。']

def _worker_claim_lines(mine: list[dict]) -> list[str]:
    claims = [fact for fact in mine if fact.get('ev') == 'worker_claim' and isinstance(fact.get('report'), dict)]
    if not claims:
        return []
    superseded = _worker_claim_superseded(mine)
    out = ['\n**编写侧主张（未受理）**:以下是编写侧提交、引擎未认定为事实的说法。']
    for fact in claims:
        report = fact.get('report') or {}
        test_point = str(report.get('test_point') or '').strip()
        obstacle = str(report.get('obstacle') or '').strip()
        no_equivalent = str(report.get('no_equivalent_reason') or '').strip()
        code = str(fact.get('rejection_code') or '')
        out.append(f"- 测试点:{test_point or '（未填写）'}\n  - 编写侧说的障碍:{obstacle or '（未填写）'}\n  - 编写侧说的「本设备没有等价做法」的理由:{no_equivalent or '（未填写）'}\n  - 引擎为何未受理:{_rejection_cn(code)}")
    out.append('  以上是编写侧的主张，引擎未认定为事实；' + ('该案在这之后仍编出了用例，主张未成立，此处只作过程留痕。' if superseded else '用例是否真的编不出来，需要由人依据作者原文与设备实况判断。'))
    return out

def _criterion_binding_declaration_lines(mine: list[dict]) -> list[str]:
    rows = [row for fact in mine if fact.get('ev') == 'criterion_binding_declared' for row in fact.get('declarations') or [] if isinstance(row, dict) and str(row.get('disclosure') or '').strip()]
    if not rows:
        return []
    out = ['\n**断言绑定由编写侧声明**:']
    for row in rows:
        out.append(f"- 第 {int(row.get('state_change_step') or 0) + 1} 个步骤造成本条要看的状态变化：{str(row.get('disclosure') or '').strip()}")
    out.append('  该声明由编写侧给出、随卷上机验证，引擎未据此认定用例通过。')
    return out

def _authored_scope_disclosure_lines(mine: list[dict]) -> list[str]:
    rows = [row for fact in mine if fact.get('ev') == 'authored_scope_disclosed' for row in fact.get('items') or [] if isinstance(row, dict) and str(row.get('head') or '')]
    if not rows:
        return []
    out = ['\n**作者步骤只核到命令头**:']
    for row in rows:
        head = str(row.get('head') or '')
        out.append(f"- 作者步骤在命令 `{head}` 之后写的是描述性条件而不是参数字面量；引擎只核了该命令在卷面出现的次数（{int(row.get('landed') or 0)}/{int(row.get('needed') or 0)}），条件所指的对象身份未机械比对。")
    out.append('  对象是否正确由上机结果与人工复核确认，引擎未据此认定用例通过。')
    return out

def _scenario_fidelity_lines(mine: list[dict]) -> list[str]:
    from cex_core.engine.case_compiler.scenario_fidelity import SCENARIO_FIDELITY_FACT_EVENT
    from cex_core.engine.ist_core.display_lexicon import SCENARIO_FIDELITY_HEAD_CN, SCENARIO_FIDELITY_HEAD_FALLBACK_CN, SCENARIO_FIDELITY_UNAVAILABLE_TAIL_CN, scenario_fidelity_mechanical_cn
    fact = next((item for item in reversed(mine) if item.get('ev') == SCENARIO_FIDELITY_FACT_EVENT), None)
    if not isinstance(fact, dict):
        return []
    status = str(fact.get('status') or '')
    head = SCENARIO_FIDELITY_HEAD_CN.get(status, SCENARIO_FIDELITY_HEAD_FALLBACK_CN)
    out = [f'\n**{head}**:']
    mechanical = fact.get('mechanical') if isinstance(fact.get('mechanical'), dict) else {}
    mechanical_cn = scenario_fidelity_mechanical_cn(mechanical)
    if mechanical_cn:
        out.append(f'- {mechanical_cn}')
    disclosure = str(fact.get('disclosure') or '').strip()
    if disclosure and disclosure != mechanical_cn:
        out.append(f'- {disclosure}')
    if status == 'unavailable':
        out.append(f'  {SCENARIO_FIDELITY_UNAVAILABLE_TAIL_CN}')
    return out

def _device_disclosure_lines(mine: list[dict]) -> list[str]:
    from cex_core.engine.case_compiler.device_characteristics import DEVICE_DISCLOSURE_FACT_EVENT, TIERS
    from cex_core.engine.ist_core.display_lexicon import DEVICE_DISCLOSURE_HEAD_CN, DEVICE_DISCLOSURE_SUMMARY_TMPL_CN, device_disclosure_tag_cn
    fact = next((item for item in reversed(mine) if item.get('ev') == DEVICE_DISCLOSURE_FACT_EVENT), None)
    if not isinstance(fact, dict):
        return []
    rows = [row for row in fact.get('rows') or [] if isinstance(row, dict)]
    if not rows:
        return []
    by_tier: dict[str, list[dict]] = {}
    for row in rows:
        by_tier.setdefault(str(row.get('tier') or ''), []).append(row)
    present = [tier for tier in TIERS if by_tier.get(tier)]
    out = [f'\n**{DEVICE_DISCLOSURE_HEAD_CN}**:']
    out.append('- ' + DEVICE_DISCLOSURE_SUMMARY_TMPL_CN.format(tiers='、'.join((device_disclosure_tag_cn(tier) for tier in present)), count=int(fact.get('row_count') or len(rows))))
    for tier in present:
        for row in by_tier[tier]:
            message = ' '.join(str(row.get('message') or '').split())
            if message:
                out.append(f'  - [{device_disclosure_tag_cn(tier)}] {message}')
    return out

def _recompile_comparison_lines(mine: list[dict]) -> list[str]:
    from cex_core.engine.case_compiler.recompile_comparison import current_direction_disclosure
    from cex_core.engine.ist_core.display_lexicon import direction_disclosure_lines_cn, recompile_comparison_cn
    fact = next((row for row in reversed(mine) if row.get('ev') == 'recompile_comparison'), {})
    message = recompile_comparison_cn(fact)
    lines = [message] if message else []
    if fact:
        lines.extend(direction_disclosure_lines_cn(current_direction_disclosure(mine, autoid=str(fact.get('aid') or ''))))
    return ['\n**重编覆盖核对**:', *('- ' + line for line in lines)] if lines else []

def _prerequisite_finding_lines(mine: list[dict]) -> list[str]:
    from cex_core.engine.case_compiler.device_characteristics import PREREQUISITE_FINDING_FACT_EVENT
    from cex_core.engine.ist_core.display_lexicon import MECHANICAL_FINDING_HEAD_CN, MECHANICAL_FINDING_SUMMARY_TMPL_CN
    fact = next((item for item in reversed(mine) if item.get('ev') == PREREQUISITE_FINDING_FACT_EVENT), None)
    if not isinstance(fact, dict):
        return []
    rows = [row for row in fact.get('rows') or [] if isinstance(row, dict)]
    if not rows:
        return []
    out = [f'\n**{MECHANICAL_FINDING_HEAD_CN}**:']
    out.append('- ' + MECHANICAL_FINDING_SUMMARY_TMPL_CN.format(count=int(fact.get('row_count') or len(rows))))
    for row in rows:
        message = ' '.join(str(row.get('message') or '').split())
        if message:
            out.append(f'  - {message}')
    return out

def _case_section(aid: str, c: dict, mine: list[dict], mcase: dict, queue: list[dict], panel: dict | None, not_fixpoint_reason: str='', advanced_this_round: bool=False, *, facts: list[dict] | None=None) -> list[str]:
    title = str(mcase.get('title') or '')
    out = [f"## {title or '用例 …' + aid[-6:]}", f"- 编号 `{aid}`(尾号 {aid[-6:]}) · 状态:{_status_cn_with_facts(str(c.get('status')), mine, facts=facts)} · 编写 {c.get('rounds')} 次"]
    tl = case_timeline(mine)
    if tl:
        out.append('\n**发生了什么**:' + '→ '.join(tl) + '。')
    out.append('\n**怎么判断的**:' + diagnosis_text(mine, panel, not_fixpoint_reason, facts=facts))
    out += _worker_claim_lines(mine)
    out += _unbound_device_claim_lines(mine)
    out += _criterion_binding_declaration_lines(mine)
    out += _authored_scope_disclosure_lines(mine)
    out += _scenario_fidelity_lines(mine)
    out += _device_disclosure_lines(mine)
    out += _prerequisite_finding_lines(mine)
    out += _recompile_comparison_lines(mine)
    if not_fixpoint_reason in {'attribution_projection_blocked', 'attribution_evidence_reacquisition_required'}:
        out.append('\n**去向**:' + _NOT_FIXPOINT_REASON_CN[not_fixpoint_reason] + '。')
    elif not_fixpoint_reason == 'command_domain_isolated':
        out.append('\n**去向**:' + command_domain_isolation_reason_cn(mine) + '。')
    else:
        out.append('\n' + remedy_text(queue, mine, panel, advanced_this_round, facts=facts))
    return out

def _path_stem(s: str) -> str:
    base = str(s or '').replace('\\', '/').rsplit('/', 1)[-1]
    return base.rsplit('.', 1)[0] if '.' in base else base

def _batch_name(manifest: dict, report: dict | None=None) -> str:
    out_name = str(manifest.get('out_name') or '').strip()
    if out_name:
        return out_name
    stem = _path_stem(str(manifest.get('source') or ''))
    return stem or str((report or {}).get('batch') or '')
ACTION_OWNER_CN: dict[str, str] = {'user': '你', 'environment': '环境', 'engine': '引擎工程', 'product': '产品', 'api': 'API接口'}
DELIVERY_REPORT_OWNER_SECTIONS: tuple[tuple[str, str], ...] = (('user', '你能做的'), ('environment', '环境要处理的'), ('api', 'API接口要处理的'))
CLOSING_CARD_OWNERS: frozenset[str] = frozenset({'engine'} | {owner for owner, _ in DELIVERY_REPORT_OWNER_SECTIONS})

def project_action_owner(status: str, mine: list[dict], *, facts: list[dict] | None=None) -> dict[str, str]:
    status = str(status or '')
    from cex_core.engine.ist_core.compile_engine.views import active_execution_pause
    pause = active_execution_pause(mine)
    if pause:
        if pause.get('closing_forced') and str(pause.get('pause_kind') or '') in {'bed', 'api'}:
            return {'owner': 'environment', 'action': str(pause.get('reason') or '') + '。'}
        if pause.get('pause_kind') == 'contra':
            return {'owner': 'user', 'action': _execution_pause_narrative(mine, pause)}
        if pause.get('basis_status') == 'source_unavailable':
            return {'owner': 'engine', 'action': '核对当前卷面与原始执行记录，补齐归因后复验；保留作者预期。'}
        return {'owner': 'environment', 'action': '检查记录指出的执行条件或通道，处理后同参续跑核验。'}
    execution_terminal = _active_execution_terminal(mine, facts=facts)
    execution_event = str(execution_terminal.get('ev') or '')
    if execution_event == 'ist_core_defect' and execution_terminal.get('reason_code') == 'governance_end_unclosed':
        return {'owner': 'engine', 'action': GOVERNANCE_END_UNCLOSED_CN + '。核查原始停止记录和预算依据，继续处理本案。'}
    from cex_core.engine.ist_core.compile_engine import forced_closure as _FC
    if execution_event == 'ist_core_defect' and _FC.is_forced_landing(execution_terminal):
        from cex_core.engine.ist_core.display_lexicon import FORCED_CLOSURE_CASE_SCOPE_CN
        return {'owner': 'engine', 'action': _FC.reason_cn(execution_terminal) + '。' + FORCED_CLOSURE_CASE_SCOPE_CN + '。'}
    if _execution_cause_unconfirmed(execution_terminal):
        return {'owner': 'engine', 'action': EXECUTION_CAUSE_UNCONFIRMED_CN + '。由 IST-Core 核查出处及执行记录，再确定处理方向。'}
    from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import authority_decision_confirmed, is_authority_block_terminal, is_authority_unverified_block
    if is_authority_block_terminal(execution_terminal):
        if is_authority_unverified_block(execution_terminal):
            return {'owner': 'user', 'action': '按权威对齐记录确认这些预期值以哪一份来源为准，再重新发起编写；设备 PASS 不替代来源裁定。'}
        if not authority_decision_confirmed(execution_terminal, facts if facts is not None else mine):
            return {'owner': 'engine', 'action': '核验来源待裁记录的身份与凭据，按核验结果继续处理本案。'}
        return {'owner': 'user', 'action': '按权威对齐记录修正冲突来源，再重新发起编写；设备 PASS 不替代来源裁定。'}
    if _is_unattributed_stop(execution_terminal):
        from cex_core.engine.ist_core.compile_engine.contradiction_stop import is_contradiction_stop
        if is_contradiction_stop(execution_terminal):
            return {'owner': 'user', 'action': _unattributed_stop_state_cn(execution_terminal)}
        return {'owner': 'user', 'action': UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN + '。'}
    if _unverified_authority_record(mine, facts):
        return {'owner': 'engine', 'action': '核验当前产物、来源权威与原始记录，补齐处理缺口后复验；具体根因仍待确认。'}
    if is_runtime_infrastructure_terminal_fact(execution_terminal):
        return {'owner': 'environment', 'action': '恢复下发或结果回收基础设施后，重新发起本案；本批其余用例继续。'}
    if execution_event == 'ist_core_defect':
        if (_api_code := _api_engine_error_terminal_code(execution_terminal)):
            return {'owner': 'api', 'action': _API_OWNER_ACTION_CN[_api_code]}
        if _defect_family(execution_terminal) == _DEFECT_AUTHORING_EVIDENCE:
            return {'owner': 'engine', 'action': AUTHORING_EVIDENCE_UNCLOSED_CN + '。核查原始输入、尝试与停止记录后确定处理方向。'}
        if _is_env_engine_error_terminal(execution_terminal):
            return {'owner': 'environment', 'action': '处理好设备/跳转机/网络拓扑后，重新发起编译重走该用例。'}
        if _is_contract_engine_error_terminal(execution_terminal):
            return {'owner': 'engine', 'action': '由引擎工程修复该案的契约投影/身份章链路后，重新发起编译重走该用例；本批其余用例不受影响。'}
        if _is_worker_timeout_engine_error_terminal(execution_terminal):
            return {'owner': 'engine', 'action': '由引擎工程修复该案的编写链路后，重新发起编译重走该用例；本批其余用例不受影响。'}
        if _defect_family(execution_terminal) == _DEFECT_DISPATCH:
            return {'owner': 'engine', 'action': '由引擎工程修好派发通道后重入本案；不重编卷面。'}
        return {'owner': 'engine', 'action': '由引擎工程修复并完成回归，再以新编译轮重走完整判定链。'}
    if execution_event == 'authoring_failure':
        return {'owner': 'engine', 'action': '模型未找到解决方案；保留本次输入、尝试和自述，后续编写重新验证当前条件。'}
    if execution_event == 'unable_to_compile':
        if execution_terminal.get('category') == 'connection':
            return {'owner': 'environment', 'action': '恢复平台与测试设备连通性后，重新发起编译。'}
        return {'owner': 'environment', 'action': '当前平台不具备运行前提；能力条件改变后再重新发起编译。'}
    atts = [f for f in mine if f.get('ev') == 'attribution']
    dispositions = [str(f.get('disposition') or '') for f in atts]
    if dispositions and dispositions[-1] == 'engineering_fault':
        return {'owner': 'engine', 'action': '由引擎工程修复并完成回归验证；当前无需用户操作。'}
    from cex_core.engine.case_compiler.provenance_ir import product_expected_source_is_valid
    from cex_core.engine.ist_core.compile_engine import facts as F
    product_ready = any((str(a.get('disposition') or '') == 'defect_candidate' and str(a.get('evidence') or '').strip() not in ('', 'user') and isinstance(a.get('defect_candidate'), dict) and product_expected_source_is_valid((a.get('defect_candidate') or {}).get('expected_with_source')) and F.scenario5_attribution_has_evidence(a, mine) for a in atts))
    if product_ready:
        return {'owner': 'product', 'action': '由产品负责人依据设备证据与预期出处复核；当前仅为候选，非终判。'}
    if 'defect_candidate' in dispositions:
        return {'owner': 'engine', 'action': '由引擎工程补齐设备证据与预期出处后再转产品复核；当前非产品终判。'}
    if status == 'unsupported_feature' or any((f.get('ev') == 'unsupported_feature' for f in mine)):
        return {'owner': 'user', 'action': '该功能经双探针确认当前环境不支持；请裁决：调整环境/修改脑图/确认不支持结案（重新发起本批编译后在问询中选择）。'}
    if 'env_blocked' in dispositions or status == 'broken_blocked':
        return {'owner': 'environment', 'action': '恢复测试设备连通性或切换到可用测试设备后，重新发起本批编译。'}
    if status == 'authored' and str(_latest_command_domain_exclusion(mine).get('reason_code') or '') == 'command_domain_residual':
        return {'owner': 'environment', 'action': f'{PREFLIGHT_RESIDUAL_NOUN_CN}该用例要动的配置命令的{PREFLIGHT_CONFIG_NOUN_CN}行，当前环境给不了它净态；处理好环境（清场或换设备）后重编本案；本批其余用例不受影响。'}
    _direct_abandon_cls = _direct_abandon_class(mine)
    if _direct_abandon_cls:
        from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as _BT_owner
        return {'owner': 'environment' if _direct_abandon_cls == _BT_owner.A_ENV_PREREQ_GAP else 'user', 'action': _BT_owner.variant_text('user_action', cls=_direct_abandon_cls, variant=_author_gap_variant(mine, _direct_abandon_cls))}
    last_ask = max((i for i, f in enumerate(mine) if f.get('ev') in ('ask_panel', 'needs_decision', 'awaiting_user_unasked')), default=-1)
    last_answer = max((i for i, f in enumerate(mine) if f.get('ev') == 'decision'), default=-1)
    if status == 'awaiting_user' or last_ask > last_answer:
        return {'owner': 'user', 'action': '重新发起本批编译，进入问询后回答该用例的待定问题。'}
    if status == 'suspended':
        return {'owner': 'user', 'action': '重新发起本批编译，并在恢复问询中选择继续处理。'}
    if 'user_stop' in dispositions:
        return {'owner': 'user', 'action': '如需继续，重新发起本批编译，并在问询中选择继续处理。'}
    from cex_core.engine.ist_core.compile_engine import facts as F
    _aid = next((str(f.get('aid') or '') for f in mine if f.get('aid')), '')
    if _aid and F.serial_recovery_pending(mine, [_aid]):
        return {'owner': 'engine', 'action': '引擎欠该案一次派发（fork 无产出后签发的一次性恢复票）：同参重调即续跑；无需改动用例或环境。'}
    return {'owner': 'engine', 'action': '由引擎工程定位并修复该内部缺口；当前无需用户操作。'}

def _unbound_observation_lines(fs: list[dict]) -> list[str]:
    items: dict[str, list[dict]] = {}
    for fact in fs:
        if fact.get('ev') != 'unbound_observation_target':
            continue
        aid = str(fact.get('aid') or '')
        rows = [r for r in fact.get('items') or [] if isinstance(r, dict)]
        if aid and rows:
            items[aid] = rows
    if not items:
        return []
    out = ['- **有断言依赖了本案没有配置过的服务地址**(仅提示,不影响放行):']
    for aid in sorted(items):
        addresses = sorted({str(r.get('address') or '') for r in items[aid]})
        out.append(f'  - `{aid}`(尾号 {aid[-6:]}):断言依赖 ' + '、'.join((f'`{a}`' for a in addresses if a)) + ' 的服务响应,但案内没有任何步骤在该地址绑定服务——确认是有意依赖测试设备上的常驻服务吗?')
    return out

def _source_conflict_auto_resolved_lines(fs: list[dict]) -> list[str]:
    per_case: dict[str, str] = {}
    for fact in fs:
        if fact.get('ev') != 'source_conflict_auto_resolved':
            continue
        aid = str(fact.get('aid') or '')
        text = str(fact.get('disclosure') or '').strip()
        if aid and text:
            per_case[aid] = text
    if not per_case:
        return []
    out = [f'- ℹ **源冲突已按冻结权威序自动裁定**（{len(per_case)} 个用例，按 2026-08-20 裁决）:']
    for aid in sorted(per_case):
        out.append(f'  - `{aid}`(尾号 {aid[-6:]}):{per_case[aid]}')
    return out

def _claim_conflict_both_true_lines(fs: list[dict]) -> list[str]:
    """2026-09-23 裁定的 both-true 放行披露（哪几行、各自来源、按裁定保留）。

    呈报级：只读 ``claim_conflict_both_true_released`` 事实。触发频率计数义务已随
    2026-09-23 范围更正撤销（「编号太粗」根因不修，无法统计的事不记录）。
    """
    per_case: dict[str, dict] = {}
    for fact in fs:
        if fact.get('ev') != 'claim_conflict_both_true_released':
            continue
        aid = str(fact.get('aid') or '')
        if aid:
            per_case[aid] = fact
    if not per_case:
        return []
    out = ['- ℹ **配置推导与其它来源断言不完全相同、上机两侧逐条成立，已按 2026-09-23 裁定双双保留放行**:']
    for aid in sorted(per_case):
        text = str(per_case[aid].get('disclosure') or '').strip()
        out.append(f'  - `{aid}`(尾号 {aid[-6:]}):{text}')
    return out

def _environment_execution_disclosure_lines(fs: list[dict]) -> list[str]:
    per_case: dict[str, dict] = {}
    for fact in fs:
        if fact.get('ev') != 'environment_execution_disclosure':
            continue
        aid = str(fact.get('aid') or '')
        if aid and str(fact.get('disclosure') or '').strip():
            per_case[aid] = fact
    if not per_case:
        return []
    out = [f'- ℹ **有用例受自动化环境限制、非用例本身问题**（{len(per_case)} 个用例）:']
    for aid in sorted(per_case):
        fact = per_case[aid]
        values = [str(v) for v in fact.get('author_unreachable_values') or [] if str(v)]
        tail = '；作者原文里的 ' + '、'.join((f'`{v}`' for v in values)) + ' 在本设备不可达' if values else ''
        out.append(f"  - `{aid}`(尾号 {aid[-6:]}):{str(fact.get('disclosure') or '').strip()}{tail}")
    return out

def _preflight_observation_disclosure_lines(fs: list[dict]) -> list[str]:
    scopes: set[tuple[str, str, str]] = set()
    historical_scope_unknown = False
    for fact in fs:
        if fact.get('ev') != 'command_domain_preflight_checked':
            continue
        details = fact.get('running_config_fallbacks')
        recorded = False
        for item in details if isinstance(details, list) else []:
            if not isinstance(item, dict):
                historical_scope_unknown = True
                continue
            aid = str(item.get('autoid') or '')
            head = str(item.get('command_head') or '')
            target = str(item.get('target_device') or '')
            if aid and head and target:
                scopes.add((aid, target, head))
                recorded = True
            else:
                historical_scope_unknown = True
        counts = fact.get('show_derivation_counts')
        count = counts.get('running_config_fallback') if isinstance(counts, dict) else None
        if not recorded and isinstance(count, int) and (not isinstance(count, bool)) and (count > 0):
            historical_scope_unknown = True
    if not scopes and (not historical_scope_unknown):
        return []
    lines = ['', '- **运行配置兜底的观察范围**：本批环境预检曾安排运行配置查询。此方法只能检查是否存在匹配的配置行；动作效果不写入运行配置时，即使查询无匹配行，也不能据此确认动作状态干净。']
    for aid, target, head in sorted(scopes):
        lines.append(f'  - 用例 `{aid}` · 执行槽 `{target}` · 命令头 `{head}`。')
    if scopes:
        lines.append('  - 上述范围按本批累计预检计划去重，包含后来被隔离或重新检查的用例。')
    if historical_scope_unknown:
        lines.append('  - 部分预检记录缺少完整范围，逐案对应关系未记录，具体受影响用例和命令未确定。')
    return lines

def merge_rejected_fact(fs: list[dict]) -> dict:
    for fact in reversed(fs or []):
        ev = str(fact.get('ev') or '')
        if ev == 'merged':
            return {}
        if ev == 'merge_rejected':
            return dict(fact)
    return {}

def _merge_rejected_lines(fs: list[dict]) -> list[str]:
    fact = merge_rejected_fact(fs)
    if not fact:
        return []
    reason = str(fact.get('reason') or '').strip()
    if not reason:
        return []
    composition = [str(a) for a in fact.get('composition') or [] if str(a)]
    scope = '整卷' if str(fact.get('ctx') or '') == 'delivery' else '子集卷'
    members = f"（尾号 {'、'.join((a[-6:] for a in composition[:8]))}" + ('…' if len(composition) > 8 else '') + '）' if composition else ''
    if str(fact.get('reason_class') or '') == 'artifact_io':
        out = [f'- ⛔ **{scope}合并后主卷读不出（引擎或文件系统故障，不是卷面规则）**:本轮组卷这一步没通过，{len(composition)} 个已编写用例都没能上机{members}。故障原文如下（逐字，未改写），处置在引擎侧，不需要改用例:', '```merge-artifact-io', reason[:2000], '```']
        return out
    out = [f'- ⛔ **{scope}合并被卷面规则拒绝**:本轮组卷这一步没通过，{len(composition)} 个已编写用例都没能上机' + members + '。规则原文如下（逐字，未改写）:', '```merge-rejection', reason[:2000], '```']
    return out

def _criterion_adjudication_disclosure_lines(fs: list[dict]) -> list[str]:
    by_identity: dict[tuple[str, str, str], dict] = {}
    for fact in fs:
        if fact.get('ev') != 'criterion_engine_adjudicated':
            continue
        for decision in fact.get('decisions') or []:
            if not isinstance(decision, dict):
                continue
            key = (str(decision.get('shape_key') or ''), str(decision.get('version_family') or ''), str(decision.get('rule_sha256') or ''))
            if all(key):
                by_identity[key] = decision
    if not by_identity:
        return []
    out = [f'- ℹ **引擎内部判据裁定（{len(by_identity)} 个 shape，作者原文未改写）**:']
    for key in sorted(by_identity):
        decision = by_identity[key]
        evidence = decision.get('evidence_chain') or {}
        manuals = [f"{row.get('source_path')}:{int(row.get('line_start') or 0)}" + (f"-{int(row.get('line_end') or 0)}" if int(row.get('line_end') or 0) != int(row.get('line_start') or 0) else '') for row in evidence.get('manual_anchors') or [] if isinstance(row, dict) and row.get('source_path')]
        trees = [str(row.get('context_id') or '') for row in evidence.get('tree_context') or [] if isinstance(row, dict) and row.get('context_id')]
        language = evidence.get('language') or {}
        out.append(f"  - shape `{key[0]}` · 版本族 `{key[1]}` → `{str(decision.get('criterion_type') or '')}`；规则 `{str(decision.get('rule_id') or '')}`（SHA-256 `{key[2]}`）；{str(decision.get('disclosure') or '').strip()}；证据链：手册 {'、'.join(manuals) or '缺失'}；树语境 {'、'.join(trees) or '缺失'}；L 闭集 `{str(language.get('criterion_type') or '')}`")
    return out

def _fixture_value_disclosure_lines(fs: list[dict]) -> list[str]:
    per_case: dict[str, list[dict]] = {}
    for fact in fs:
        if fact.get('ev') != 'fixture_values_disclosed':
            continue
        aid = str(fact.get('aid') or '')
        values = [row for row in fact.get('values') or [] if isinstance(row, dict)]
        if aid and values:
            per_case[aid] = values
    if not per_case:
        return []
    out = ['- ℹ **引擎自造测试夹具值（均由前序配置字面值回指签发）**:']
    for aid in sorted(per_case):
        rendered = []
        for row in per_case[aid]:
            value = str(row.get('value') or '')
            kind = str(row.get('fixture_kind') or '')
            block = int(row.get('config_block_index') or 0)
            command = int(row.get('config_command_index') or 0)
            if value and kind:
                rendered.append(f'`{value}`（{kind}，CONFIG[{block}].cmds[{command}]）')
        if rendered:
            out.append(f'  - `{aid}`(尾号 {aid[-6:]}):' + '、'.join(rendered))
    return out if len(out) > 1 else []

def _certifiability_lines(fs: list[dict]) -> list[str]:
    from cex_core.engine.case_compiler.pass_audit import group_audits, latest_terminals, select_pass_audit, terminal_artifacts
    terminals = latest_terminals(fs)
    delivered = [aid for aid, terminal in terminals.items() if terminal.get('outcome') == 'delivered']
    if not delivered:
        return []
    views = {}
    grouped = group_audits(fs)
    for aid in delivered:
        final_sha, case_sha = terminal_artifacts(terminals[aid])
        views[aid] = select_pass_audit(grouped.get(aid, []), aid=aid, final_sha=final_sha, case_sha=case_sha)
    n_clean = sum((view.clean for view in views.values()))
    if n_clean == len(delivered):
        return [f'- ✓ **判别力凭据齐全**:{len(delivered)} 个交付用例的断言翻转凭据均已关联到本次交付卷，无豁免；这不是对断言语义正确性的额外证明。']
    known = [view.counts for view in views.values() if view.counts is not None]
    total, flipped = (sum((row[0] for row in known)), sum((row[1] for row in known)))
    summary = f'- **判别力凭据未齐或未核**:{len(delivered)} 个交付用例中 {n_clean} 个的凭据已完整对账'
    if known:
        summary += f'；已取得统计的 {len(known)}/{len(delivered)} 个用例共 {total} 条断言，其中 {flipped} 条有翻转证据'
    out = [summary + '。尚未完成的凭据、身份和统计分别列在下面。', '  - 本轮保留原上机判决；未通过变异凭据收口的记录按凭据不完整保留。']
    reasons = {'delivery_identity_missing': '交付记录缺少完整卷面身份', 'audit_artifact_mismatch': '审计与最终整卷身份不一致', 'case_artifact_mismatch': '审计与交付单案身份不一致或身份缺失', 'audit_schema_invalid': '审计记录结构或来源标识不完整', 'audit_state_invalid': '审计状态与结论不一致', 'audit_counts_invalid': '审计计数或收据身份不能闭合'}
    for aid in sorted(delivered):
        view = views[aid]
        prefix = f'  - `{aid}`(尾号 {aid[-6:]}):'
        if view.audit is None:
            out.append(prefix + '**无凭据审计记录**；统计未取得')
            continue
        if view.clean:
            continue
        if view.counts is None:
            description = reasons.get(view.reason, '翻转审计不可用')
            read_error = (view.audit or {}).get('read_error')
            if isinstance(read_error, dict):
                error_type = read_error.get('error_type')
                explanation = {'FileNotFoundError': '对照凭据文件未找到', 'JSONDecodeError': '对照凭据内容无法解析', 'UnicodeDecodeError': '对照凭据编码无效', 'PermissionError': '对照凭据无读取权限'}.get(error_type if isinstance(error_type, str) else '', '对照凭据读取失败')
                description += '；' + explanation
            out.append(prefix + description + '；统计未取得')
            continue
        count, flipped, exempt, pending = view.counts
        seg = [f'断言 {count}', f'有翻转证据 {flipped}']
        if view.status == 'complete' and view.audit.get('outcome') == 'false_pass':
            seg.insert(0, '审计记录标注假通过')
        if exempt:
            seg.append(f'豁免 {exempt}')
            issued = view.audit.get('compiler_issued_exempt_assertions')
            declared = view.audit.get('author_declared_exempt_assertions')
            if type(issued) is int and type(declared) is int:
                seg.append(f'其中编译器签发 {issued}、作者声明 {declared}')
        if pending:
            seg.append(f'待定 {pending}')
        out.append(prefix + '、'.join(seg))
    return out

def _authoring_attempt_requirement_lines(fs: list[dict]) -> list[str]:
    """逐案保留每次 AF 检查的全部原项；显示不重算成因或责任。"""
    import json
    lines: list[str] = []
    counts: dict[str, int] = {}
    for row in fs:
        if row.get('ev') != 'authoring_failure_unconfirmed':
            continue
        aid = str(row.get('aid') or '未记录')
        counts[aid] = counts.get(aid, 0) + 1
        missing = row.get('missing_evidence')
        notes = ['台账记录的缺项，不据此补判原因或责任。']
        if isinstance(missing, list):
            if 'three_valid_authoring_attempts_required' in missing:
                notes.append('该次编写证据检查未满足三次独立、有效编写失败的证据条件。')
        else:
            notes.append('缺项字段形态未核，以下保留记录原值。')
        original = json.dumps(missing, ensure_ascii=False, indent=2)
        fence = '`' * max(3, max((len(run) for run in re.findall('`+', original)), default=0) + 1)
        lines.append(f'\n**用例 `{aid}` · 编写证据检查 {counts[aid]}（AF-0001）**\n\n' + ''.join(notes) + '\n\n原始缺项：\n\n' + fence + 'json\n' + original + '\n' + fence + '\n')
    return lines

def _api_error_wave_lines(report: dict) -> list[str]:
    wave = report.get('api_error_wave')
    if not isinstance(wave, dict) or not wave:
        return []
    from cex_core.engine.ist_core import display_lexicon as _DL
    api_error = wave.get('api_error') or {}
    head = _DL.api_error_sentence(api_error.get('code'), api_error.get('message'))
    if not head:
        return []
    count = int(wave.get('count') or 0)
    total = int(wave.get('total') or 0)
    return [f"- **{_DELIVERY_INCOMPLETE_REASON_CN['api_error']}**:{head} · 本波 {total} 个用例里 {count} 个同因未编写；本批其余用例照常"]

def _network_outage_disclosure_lines(fs: list[dict]) -> list[str]:
    outages = [f for f in fs if f.get('ev') == 'network_outage']
    if not outages:
        return []
    total = 0.0
    for fact in outages:
        try:
            total += float(fact.get('waited_s') or 0)
        except (TypeError, ValueError):
            continue
    if total <= 0:
        return []
    from cex_core.engine.ist_core import display_lexicon as _DL
    return [f'- **{_DL.network_outage_disclosure_cn(total)}**']

def _thinking_degraded_disclosure_lines(fs: list[dict]) -> list[str]:
    seen: list[str] = []
    for fact in fs:
        if fact.get('ev') != 'disclosure':
            continue
        if str(fact.get('kind') or '') != 'thinking_degraded':
            continue
        text = str(fact.get('text') or '').strip()
        if text and text not in seen:
            seen.append(text)
    return [f'- **思考模式降级披露**:{text}' for text in seen]

def _contract_warning_panel_lines(report: dict) -> list[str]:
    from cex_core.engine.case_compiler.contract_entry import WARNING_PANEL_SCHEMA
    panel = report.get('warning_panel')
    if not isinstance(panel, dict) or panel.get('schema') != WARNING_PANEL_SCHEMA:
        return []
    items = [item for item in panel.get('items') or [] if isinstance(item, dict)]
    unreported = panel.get('unreported')
    if not items:
        if isinstance(unreported, dict) and unreported.get('count'):
            return [f"> **批级验证提示未能呈报**：{unreported['count']} 条提示取不回（{unreported.get('reason') or 'unknown'}）。提示不阻断编译，但这一批的复核项在本报告里是缺的。"]
        return []
    lines = ['> **批级验证提示（不阻断编译）**：以下项目保留给用户复核，未进入 worker 上下文。']
    for item in items:
        autoid = ' '.join(str(item.get('autoid') or '').split())
        code = ' '.join(str(item.get('code') or '').split())
        message = ' '.join(str(item.get('message') or '').split())
        if autoid and code and message:
            lines.append(f'> - `{autoid}`：{message}（`{code}`）')
    return lines if len(lines) > 1 else []

def _preflight_head_lines_disclosure_lines(fs: list[dict]) -> list[str]:
    lines: list[str] = []
    for fact in fs:
        if fact.get('ev') != 'command_domain_preflight_checked':
            continue
        disclosures = fact.get('head_lines_present')
        if not isinstance(disclosures, dict) or not any(disclosures.values()):
            continue
        if not lines:
            lines += ['', f'## {PREFLIGHT_PROGRESS_LABEL}：设备已有配置', '']
        for key, items in disclosures.items():
            for item in items:
                lines.append('- ' + preflight_head_line_cn(key, item))
        receipt = str(fact.get('receipt_ref') or '')
        if receipt:
            lines.append(f'完整回显保存在本地收据 `{receipt}`。')
    return lines

def render_delivery_report(report: dict, fs: list[dict], manifest: dict, queues: dict[str, list[dict]], panels: dict[str, dict] | None=None) -> str:
    t = report.get('totals', {})
    ok = int(t.get('deliverable') or 0)
    total = int(t.get('cases') or 0)
    mcases = {str(c.get('autoid')): c for c in manifest.get('cases') or []}
    lines = [f'# 交付报告 — {_batch_name(manifest, report)}', f"> 生成 {time.strftime('%Y-%m-%d %H:%M', time.localtime())}", '', f'本批 {total} 个用例:**{ok} 个通过整卷复验,已入交付卷**' + (f';其余 {total - ok} 个已按行动主体分流，下面列你、环境或API接口侧可执行的动作，以及需要引擎继续核查或修复的执行记录；其它引擎/产品责任项进入工程与产品处置候选单。' if total > ok else '。'), '']
    _oc = str(report.get('outcome') or '')
    from cex_core.engine.ist_core.compile_engine.authoring_evidence import uses_new_policy
    if uses_new_policy(fs):
        lines[3] = f'本批登记 {total} 个用例。有效终态、隔离与其余未终结案见下方人口账；未核责任不写成结论。'
    if _oc == 'delivery_incomplete':
        _why = delivery_incomplete_why_cn(report.get('delivery_incomplete_reasons'))
        lines.append(f'- **收口结论:交付不完整**——{_why},请以 `engine_report.json` 为准,勿把本报告当完整交付凭证')
    elif _oc == 'report_mismatch':
        lines.append('- **收口结论:报告与事实台账不一致**——本批暂不可作为交付依据(详见 `REPORT_MISMATCH.json`)')
    _excel_runtime = report.get('excel_runtime') or {}
    if isinstance(_excel_runtime, dict):
        _release_state = str(_excel_runtime.get('release_state') or '')
        if _release_state == 'legacy':
            lines.append('> **Excel 运行模板告警**：`release_state=legacy`，当前生产选择仍是无契约 marker 的历史模板；已部署 runner 会拒绝该卷，完成 promotion 前不得据此声称可上机。')
        elif _release_state:
            lines.append(f'- Excel 运行模板：`release_state={_release_state}`')
    _sup = report.get('volume_composition_superset')
    if isinstance(_sup, dict) and (_sup.get('residents') or []):
        _n_res = len(_sup.get('residents') or [])
        _n_ok = len(_sup.get('deliverable') or [])
        lines.append(f'- **主卷不止交付案**:`case.xlsx` 里除了 {_n_ok} 个通过案,还有 {_n_res} 个同卷跑过但未交付的用例(结论各异——有真未通过,也有上机 PASS 但收口案级核对未过被撤销的;它们的结论见未通过卷)。本批在重新组卷之前停下了,请按上面的通过清单取用,不要把整份主卷当通过卷。')
    _tr = report.get('this_run') or {}
    if _tr and (not _tr.get('active')):
        lines.append(f"> **本轮无新进展**:引擎本轮未编写、未上机、未产生新判决(本轮新增 {int(_tr.get('new_facts') or 0)} 条过程记录)。下方各用例的过程与状态来自**历史累计**台账,不是本轮新产出。")
    _dov = [f for f in fs if f.get('ev') == 'delivery_overwritten']
    if _dov:
        _files = '、'.join((str(x) for x in _dov[-1].get('files') or []))
        lines.append(f'- **交付物在上轮 closing 后被改写**:{_files}——引擎交付物应确定性产出,请核对是否被手工重建')
    _merge_rejection_lines = _merge_rejected_lines(fs)
    lines.extend(_merge_rejection_lines)
    _phase_error = str((report.get('phase_error') or {}).get('error') or '').strip()
    if _phase_error and (not _merge_rejection_lines):
        lines.append(f'- ⛔ **本轮在收口前以错误状态终止**，引擎留下的原文（逐字，未改写）:`{_ellip(_phase_error, 400)}`')
    from cex_core.engine.ist_core.display_lexicon import window_audit_summary_cn
    _latest_verdicts: dict = {}
    for f in fs:
        if f.get('ev') == 'verdict' and f.get('aid'):
            _latest_verdicts[str(f.get('aid'))] = f
    _audit_lines = [window_audit_summary_cn(f) for f in _latest_verdicts.values()]
    _clusters: dict = {}
    for f in fs:
        if f.get('ev') == 'session_desync_cluster':
            _clusters[str(f.get('device') or ''), tuple(f.get('autoids') or [])] = f
    _audit_lines += [window_audit_summary_cn(f) for f in _clusters.values()]
    if any(_audit_lines):
        lines += ['', '## 窗口审计与会话观察', '']
        lines += ['- ' + line for line in _audit_lines if line]
    lines.extend(_api_error_wave_lines(report))
    lines.extend(_network_outage_disclosure_lines(fs))
    lines.extend(_thinking_degraded_disclosure_lines(fs))
    lines.extend(_contract_warning_panel_lines(report))
    lines.extend(_certifiability_lines(fs))
    from cex_core.engine.ist_core.compile_engine.terminal_reentry_identity import HELD_CN, HELD_EVENT
    from cex_core.engine.ist_core.compile_engine.facts import this_run_slice
    held = {str(row.get('aid') or ''): row for row in this_run_slice(fs) if row.get('ev') == HELD_EVENT}
    for aid, row in sorted(held.items()):
        lines.append(f'- `{aid}`：' + HELD_CN.get(row.get('reason_code'), '本轮重入身份未核，原终态保留') + '。')
    denied_writebacks = sorted({str(row.get('aid') or '') for row in fs if row.get('ev') == 'writeback_failed' and row.get('denied_by_identity') is True and row.get('aid')})
    for aid in denied_writebacks:
        lines.append(f'- `{aid}`：归档写回记录显示封禁规则拒绝，未完成该次写回；原上机记录保留。')
    lines.extend(_authoring_attempt_requirement_lines(fs))
    lines.extend(_unbound_observation_lines(fs))
    lines.extend(_source_conflict_auto_resolved_lines(fs))
    lines.extend(_claim_conflict_both_true_lines(fs))
    lines.extend(_criterion_adjudication_disclosure_lines(fs))
    lines.extend(_environment_execution_disclosure_lines(fs))
    lines.extend(_preflight_observation_disclosure_lines(fs))
    lines.extend(_fixture_value_disclosure_lines(fs))
    lines.extend(_preflight_head_lines_disclosure_lines(fs))
    _case_xml_inconsistent = sorted({str(f.get('aid') or '') for f in fs if f.get('ev') == 'case_source_inconsistency' and str(f.get('aid') or '')})
    if _case_xml_inconsistent:
        _tails = '、'.join((aid[-6:] for aid in _case_xml_inconsistent))
        lines.append(f'- **用例与设备 XML 不一致**:{len(_case_xml_inconsistent)} 个用例（尾号 {_tails}）已按本批裁决采用 XML 继续编写、上机与出卷；原用例预期/命令需另行核对。')
    n_broken = int(t.get('broken') or 0) + int(t.get('broken_errored') or 0) + int(t.get('broken_blocked') or 0) + int(t.get('broken_aborted') or 0) + int(t.get('broken_verdict_unrecognized') or 0)
    if n_broken:
        lines.append(f'- 有 {n_broken} 个用例本轮**未跑成**(执行中断/日志陈腐/级联受害/断言被实机回显反证/设备不可达)——它们的结果是「无结论」而非「未通过」,不计入通过率分母叙事')
    _gd = {}
    for f in fs:
        if f.get('ev') == 'gate_disabled':
            _gd[str(f.get('gate'))] = str(f.get('reason') or '')
    if _gd:
        _cn = {'diagnose_s0': '批级污染诊断', 'inverse_forms': 'τ 覆盖规则/机械恢复', 'touch_profile': '触碰画像(s₀ 配对输入)', 'dispatch_targets_disabled_for_e': 'F 列分发校验(部分 E 值未覆盖白名单)'}
        items = '；'.join((_cn.get(g, '未登记判定规则') for g in sorted(_gd)))
        lines.append(f'- **K 健康度**:{len(_gd)} 个判定规则本轮因数据面缺席而降级({items})——相关诊断/覆盖判定的可信度下降,详见 engine_report.json 机读报告中的规则降级记录')
    from cex_core.engine.case_compiler.gate_advisories import advisory_check_status
    from cex_core.engine.ist_core.compile_engine import facts as F
    _ga = [f for f in F.this_run_slice(fs) if f.get('ev') == 'gate_advisory']
    for f in _ga:
        code = str(f.get('code') or '')
        status = advisory_check_status(code)
        label = {'not_checked': '未执行检查', 'checked_limitation': '已检查，发现局限', 'unknown': '历史记录未注明检查状态'}[status]
        lines.append(f"- **规则呈报**:{f.get('aid') or '批级'} · {code} · {label} · {f.get('locus') or f.get('step_index', '')}；详见 engine_report.json。")
    _disclosure_labels = {'round_cap_side_disclosure': '接口或治理中断，本轮编写暂挂', 'structural_rejection_disclosure': '连续两轮同码拒绝，停止重复策略，保留剩余尝试', 'criterion_satisfiability_gap': '声明未匹配或类型未登记；完整承载能力尚未证明'}
    for f in F.this_run_slice(fs):
        if f.get('ev') in _disclosure_labels:
            lines.append(f"- **编写条件披露**:{f.get('aid') or '批级'} · {_disclosure_labels[f['ev']]} · {f.get('code') or f.get('expectation_id') or ''}。")
    _vuc_latest: dict[str, dict] = {}
    for _cc in fs:
        if _cc.get('ev') != 'verdict_unrecognized_cluster':
            continue
        _rv = str(_cc.get('raw_value') or '')
        if _rv:
            _vuc_latest[_rv] = _cc
    for _rv in sorted(_vuc_latest):
        _cc = _vuc_latest[_rv]
        _c_aids = [str(a) for a in _cc.get('aids') or []]
        _c_batches = [str(b) for b in _cc.get('batches_seen') or []]
        _c_tail = '、'.join((a[-6:] for a in _c_aids[:6])) + ('…' if len(_c_aids) > 6 else '')
        if len(_c_batches) >= 2:
            lines.append(f'- **框架返回值超出已识别范围,已跨批次复现**:某个未识别值本批命中 {len(_c_aids)} 个用例(尾号 {_c_tail}),另在 {len(_c_batches) - 1} 个其它批次也出现过——这更像我们的裁决闭集已过时,不像个案偶发,建议核对框架侧接口')
        else:
            lines.append(f'- **框架本批返回了同一个未识别的裁决值**:该未识别值出现在 {len(_c_aids)} 个不同用例(尾号 {_c_tail})——这更像闭集过时,不像某个用例偶发出错')
    _ask_t = t.get('ask') or {}
    _ask_answered = int(_ask_t.get('answered') or 0)
    _ask_unresolved = _ask_answered - int(_ask_t.get('effective') or 0)
    if _ask_unresolved > 0:
        _freeform_n = int(_ask_t.get('freeform') or 0)
        _other_n = _ask_unresolved - _freeform_n
        if _freeform_n > 0:
            lines.append(f'- 本轮 {_ask_answered} 个裁决中,其中 {_freeform_n} 个你走了自由输入(说明给的选项没覆盖你的情况)')
        if _other_n > 0:
            if _tr and (not _tr.get('active')):
                lines.append(f'- 这 {_other_n} 个的裁决引擎本轮没有执行(不是选项不适配),原因见顶部说明')
            else:
                lines.append(f'- {_other_n} 个裁决尚未达成终局(处理仍在进行中,非选项不适配)')
    _sc = [f for f in fs if f.get('ev') == 'sibling_collision']
    if _sc:
        pairs = '、'.join((f"{str(c.get('aid'))[-6:]}↔{str(c.get('with'))[-6:]}" for c in _sc[:4]))
        lines.append(f'- {len(_sc)} 组同组变体疑似撞题(尾号 {pairs}' + ('…' if len(_sc) > 4 else '') + '),详见机读报告')
    _scu = [f for f in fs if f.get('ev') == 'strong_claim_unaddressed']
    if _scu:
        aids = '、'.join((str(f.get('aid'))[-6:] for f in _scu[:4]))
        lines.append(f'- {len(_scu)} 案存在未被本轮正面回应的历史强主张(尾号 {aids}' + ('…' if len(_scu) > 4 else '') + '),可能被静默降级,详见机读报告')
    _fwf = [f for f in fs if f.get('ev') == 'frozen_write_failed']
    if _fwf:
        aids = '、'.join((str(f.get('aid'))[-6:] for f in _fwf[:4]))
        lines.append(f'- {len(_fwf)} 案本轮冻结标记未能落盘(尾号 {aids}' + ('…' if len(_fwf) > 4 else '') + '),已证伪的方法下轮可能被无声重试,详见机读报告')
    _awf = [f for f in fs if f.get('ev') == 'adjudication_write_failed']
    if _awf:
        aids = '、'.join((str(f.get('aid'))[-6:] for f in _awf[:4]))
        lines.append(f'- {len(_awf)} 案本轮判例写回失败(尾号 {aids}' + ('…' if len(_awf) > 4 else '') + '),下批可能重复问同一问题,详见机读报告')
    moved = report.get('moved_tail') or []
    if moved:
        names = [str((mcases.get(a) or {}).get('title') or '…' + a[-6:]) for a in moved]
        lines.append(f"- 有 {len(moved)} 个用例会在设备上留下跨用例存活的配置(保存/同步类),已按规则排到卷尾执行:{'、'.join(names)}")
    if report.get('coexist_violations'):
        if report.get('coexist_blocked'):
            lines.append('- 本卷存在官方标注互斥的操作组合,已在组卷前阻断,未向设备发车(详见机读报告)')
        else:
            lines.append('- 历史事实记录到互斥操作组合；当前规则会在组卷前阻断(详见机读报告)')
    _spec_cov = report.get('spec_coverage') or {}
    _spec_cases = _spec_cov.get('cases') or {}
    from cex_core.engine.ist_core.compile_engine.conflict_chain import spec_absent
    _spec_status_token = str(_spec_cov.get('governing_spec_status') or '')
    if spec_absent(_spec_status_token):
        if _spec_status_token == 'ambiguous':
            lines.append('- **SPEC 背书**:本批管辖 SPEC 检索命中多个候选、打分分不开,按 SPEC 缺失处理；用例按完整性及其它带身份来源继续处理。此注记不等同于证明不存在相关规格。')
            _spec_refs = _spec_cov.get('spec_references') or []
            if _spec_refs:
                _rnames = '、'.join((str(r.get('name') or '?') for r in _spec_refs[:6]))
                _rmore = f' 等 {len(_spec_refs)} 份' if len(_spec_refs) > 6 else ''
                lines.append(f'- **参考规范书**:本批 {len(_spec_refs)} 份产品规范书候选（非管辖）已降为定向参考（零签发权·不判用例与规格书互斥）:{_rnames}{_rmore}；切片锚点见机读 governing_spec_status.json。')
        else:
            lines.append('- **SPEC 背书**:本批未声明管辖 SPEC；用例按完整性及其它带身份来源继续处理。此注记不等同于证明不存在相关规格。')
    else:
        _not_projected = [aid for aid, item in _spec_cases.items() if str((item or {}).get('status') or '') == 'not_projected']
        if _not_projected:
            _tails = '、'.join((str(aid)[-6:] for aid in _not_projected[:8]))
            _more = '…' if len(_not_projected) > 8 else ''
            lines.append(f'- **SPEC 覆盖注记**:{len(_not_projected)} 案的当前密封契约未投影出 SPEC 签发声明(尾号 {_tails}{_more})；不阻断编写或上机，也不是对 SPEC 全文的穷尽否定。')
    _prec = report.get('precedent_polarity_flags') or []
    if _prec:
        _pn = sum((int(p.get('count') or 0) for p in _prec))
        _pnames = [str((mcases.get(p.get('autoid')) or {}).get('title') or '…' + str(p.get('autoid'))[-6:]) for p in _prec]
        lines.append(f"- {len(_prec)} 个交付用例的 {_pn} 条断言极性照抄先例语法(已上机验方向,仅作来源标注供复核抽查):{'、'.join(_pnames)}")
    bad = {a: c for a, c in (report.get('cases') or {}).items() if c.get('status') != 'deliverable'}
    _nfp_reasons = (report.get('not_fixpoint') or {}).get('reasons') or {}
    _advanced = set(report.get('advanced_this_round') or [])
    from cex_core.engine.ist_core.compile_engine import blocking_taxonomy as BT
    _cards: dict[str, dict] = {}
    for f in fs:
        if f.get('ev') == 'blocking_card':
            _cards[str(f.get('aid') or '')] = f
    _delivered_carded = [(aid, c, _cards[aid]) for aid, c in sorted((report.get('cases') or {}).items()) if c.get('status') == 'deliverable' and aid in _cards]
    if _delivered_carded:
        lines += ['', '**已交付案的不一致留痕**', '']
        for aid, _case, card in _delivered_carded:
            mine = [f for f in fs if str(f.get('aid')) == aid]
            title = str((mcases.get(aid) or {}).get('title') or '…' + aid[-6:])
            cls = BT.canonical_class(str(card.get('blocking_class') or ''))
            lines.append(f'## {title}')
            lines.append(f'- 编号 `{aid}`(尾号 {aid[-6:]}) · 已通过整卷复验并交付')
            timeline = case_timeline(mine)
            if timeline:
                lines.append('- **发生了什么**:' + '→ '.join(timeline) + '。')
            lines.append(f'- **不一致因素**:{BT.FACTOR_ZH.get(cls, BT.FACTOR_ZH[BT.B_UNCLASSIFIED])}')
            version_note = _xml_precedent_note(card)
            if version_note:
                lines.append(f'- **版本差异**:{version_note}')
            lines.extend(_scenario1_evidence_lines(mine))
            lines.extend(_scenario1_missing_fields_lines(mine))
            lines.append(f"- **凭据**:{len(card.get('basis') or [])} 条结构化依据已保留在事实台账")
            lines.append('')
    if bad:
        projected = []
        for aid, c in sorted(bad.items()):
            mine = [f for f in fs if str(f.get('aid')) == aid]
            own = project_action_owner(str(c.get('status') or ''), mine, facts=fs)
            projected.append((aid, c, mine, own))
        for owner, heading in DELIVERY_REPORT_OWNER_SECTIONS:
            owned = [x for x in projected if x[3]['owner'] == owner]
            if not owned:
                continue
            lines += ['', f'**{heading}**', '']
            for aid, c, mine, own in owned:
                lines += _case_section(aid, c, mine, mcases.get(aid) or {}, queues.get(aid) or [], (panels or {}).get(aid), not_fixpoint_reason=_nfp_reasons.get(aid, ''), advanced_this_round=aid in _advanced, facts=fs)
                lines.append(f"- **下一步动作**:{own['action']}")
                lines.append('')
        engine_must = [item for item in projected if item[3]['owner'] == 'engine' and on_engine_delivery_action_list(item[2], facts=fs)]
        if engine_must:
            lines += ['', '**引擎必须处理的**', '']
            for aid, c, mine, own in engine_must:
                lines += _case_section(aid, c, mine, mcases.get(aid) or {}, queues.get(aid) or [], (panels or {}).get(aid), not_fixpoint_reason=_nfp_reasons.get(aid, ''), advanced_this_round=aid in _advanced, facts=fs)
                lines.append(f"- **下一步动作**:{own['action']}")
                lines.append('')
        _carded = [(aid, _cards[aid]) for aid, _c, _m, _own in projected if aid in _cards and (_own['owner'] in ('user', 'environment') or BT.is_abandon_class(str(_cards[aid].get('blocking_class') or '')))]
        if _carded:
            lines += ['', '**客观阻塞对账**(每个未交付案的因素+凭据+已实现处置入口)', '']
            _order = {cls: i for i, cls in enumerate((*BT.ABANDON_CLASSES, *BT.BLOCKING_CLASSES, BT.B_UNCLASSIFIED))}
            for aid, card in sorted(_carded, key=lambda x: (_order.get(BT.canonical_class(str(x[1].get('blocking_class') or '')), 99), x[0])):
                mine = [f for f in fs if str(f.get('aid') or '') == aid]
                cls = BT.canonical_class(str(card.get('blocking_class') or ''))
                title = str((mcases.get(aid) or {}).get('title') or '')
                _gap_variant = _author_gap_variant(mine, cls)
                cn = BT.variant_text('class_cn', cls=cls, variant=_gap_variant)
                lines.append(f"## [{cn}] {title or '…' + aid[-6:]}")
                lines.append(f'- 编号 `{aid}`(尾号 {aid[-6:]})')
                factor = BT.variant_text('factor', cls=cls, variant=_gap_variant)
                co = [BT.BLOCKING_CN.get(BT.canonical_class(s), '') for s in card.get('co_signals') or [] if BT.BLOCKING_CN.get(BT.canonical_class(s))]
                lines.append(f'- **因素**:{factor}' + (f"(并存信号:{'、'.join(co)})" if co else ''))
                if cls == BT.B_AUTHORING_UNATTRIBUTED:
                    _stop = _active_execution_terminal(mine, facts=fs)
                    lines.append('- **停止成因**:' + unproven_stop_cause_cn(_stop.get('stop_cause')))
                version_note = _xml_precedent_note(card)
                if version_note:
                    lines.append(f'- **版本差异**:{version_note}')
                lines.extend(_scenario1_evidence_lines(mine))
                lines.extend(_scenario1_missing_fields_lines(mine))
                _synthetic_evs = {'needs_decision_ledger', 'manual_audit'}
                fact_shas = [str(b.get('sha256') or '')[:8] for b in card.get('basis') or [] if b.get('sha256') and str(b.get('ev') or '') not in _synthetic_evs]
                ledger_n = sum((1 for b in card.get('basis') or [] if str(b.get('ev') or '') in _synthetic_evs))
                _cred_parts = []
                if fact_shas:
                    _cred_parts.append(f"依据 {len(fact_shas)} 条已落账事实(指纹 {'、'.join(fact_shas)};全文按指纹在 `facts.jsonl` 可查)")
                if ledger_n:
                    _cred_parts.append(f'另有 {ledger_n} 条结构化凭据在案(欠定台账主张/手册差分对照,原文与出处引用可查)')
                lines.append('- **凭据**:' + ('；'.join(_cred_parts) if _cred_parts else '本类归属来自案级状态投影,过程事实在 `facts.jsonl`'))
                opts = BT.OPTIONS_ZH.get(cls, ())
                _direct_cls = _direct_abandon_class(mine)
                if cls == BT.B_EXECUTION_INFRA and opts:
                    lines.append(f'- **处置**:{opts[0]}')
                elif _direct_cls:
                    lines.append('- **处置**:' + BT.variant_text('user_action', cls=_direct_cls, variant=_author_gap_variant(mine, _direct_cls)))
                elif opts:
                    lines.append(f"- **处置选项**:{' / '.join(opts)}(重新发起本批编译,在对应问询中选择)")
                lines.append('')
    from cex_core.engine.ist_core.compile_engine.engine_disclosure import render_cn
    lines.extend(render_cn(fs, report))
    _dc = report.get('defect_candidates') or {}
    lines.append('---')
    _ux = report.get('unsuccessful_xlsx')
    _uns_claim = ''
    if bad:
        if _ux is True:
            _uns_claim = '、`unsuccessful_cases.xlsx`+`unsuccessful_cases.md`(未通过卷与详报)'
        elif _ux is False:
            _uns_claim = '、`unsuccessful_cases.md`(未通过详报;xlsx 未能产出)'
        else:
            _uns_claim = '、`unsuccessful_cases.xlsx`+`unsuccessful_cases.md`(未通过卷与详报)'
    lines.append('交付物:`case.xlsx`(通过卷)' + _uns_claim + (f"、`defect_candidates.md`(工程与产品处置候选单,{int(_dc.get('count') or 0)} 案,含结构化表单与处置轨迹)" if _dc else '') + '、`engine_report.json`(机读)。全部过程事实在 `facts.jsonl`,可据此核对,亦可手动重新发起编译。')
    return '\n'.join(lines) + '\n'

def render_engine_errors_md(fs: list[dict], manifest: dict, population: list[str], terminal_note: str='') -> str:
    import json
    import re
    from cex_core.engine.ist_core.compile_engine import engine_errors as _EE
    from cex_core.engine.ist_core.compile_engine import engine_checkpoints as C, facts as F
    from cex_core.engine.ist_core.security_scrub import scrub_value
    records = [row for row in F.this_run_slice(fs) if row.get('ev') in {_EE.ENGINE_ERROR_EVENT, 'engine_condition_disclosure'}]
    lines = [f'# 引擎错误与条件披露 — {_batch_name(manifest)}', f"> 生成 {time.strftime('%Y-%m-%d %H:%M', time.localtime())} · 本轮共 {len(records)} 条记录", '']
    if terminal_note:
        lines.extend([f'> 调用方收口说明：{scrub_value(terminal_note, scrub_paths=False)}', ''])

    def raw_block(label: str, value: object) -> None:
        safe = scrub_value(value, scrub_paths=False)
        text = safe if isinstance(safe, str) else json.dumps(safe, ensure_ascii=False, sort_keys=True, indent=2)
        fence = '`' * max(3, max((len(run) for run in re.findall('`+', text)), default=0) + 1)
        lines.extend([f'- {label}：', '', fence, text, fence])
    for err in records:
        code = str(err.get('code') or '')
        aid = str(err.get('aid') or '')
        diagnostic = str(err.get('diagnostic_id') or err.get('error_id') or '')
        verified = False
        if err.get('ev') == 'engine_condition_disclosure':
            try:
                C.validate_condition_disclosure(err)
                label = '观察条件（责任未核）'
            except (ValueError, TypeError, KeyError):
                label = '条件记录校验未通过（责任未核）'
            code = str(err.get('legacy_code') or '')
        elif err.get('schema') == C.SCHEMA:
            try:
                C.validate_error(err)
                verified = True
                label = '已验证内部契约违例' if err.get('owner') == 'engine' else 'API响应记录'
            except (ValueError, TypeError, KeyError):
                label = '历史或证明未闭合记录（责任未核）'
        else:
            label = '历史错误记录（责任未核）'
        title = C.BY_CODE[code].title_cn if code in C.BY_CODE else _EE.CODE_TITLE_CN.get(code, '未登记的历史编号')
        lines.append(f"## {label} — {diagnostic or '旧码 ' + (code or '(缺码)')}")
        lines.append(f"- 编号/标签：`{code or '(未记录)'}` · {title}")
        if err.get('ev') == 'engine_error' and err.get('schema') != C.SCHEMA and code:
            lines.append(f'- 历史机读标签：`ENGINE ERROR {code}`（保留旧字节，不补判当前责任）。')
        lines.append(f"- 检查点/调用点：`{str(err.get('site') or '未记录')}`")
        if code in C.BY_CODE and C.BY_CODE[code].implementation_status == 'reserved':
            lines.append('- 该编号已预留，尚没有当前可用的内部契约证明检查器。')
        if aid:
            lines.append(f'- 触发用例：`{aid}`（尾号 {aid[-6:]}）')
        if err.get('source_location'):
            raw_block('原始调用位置', err['source_location'])
        if verified:
            side = '内部契约检查侧' if err['owner'] == 'engine' else '响应记录来源侧'
            lines.append(f"- {side}：`{err['owner']}`；登记作用域：`{err['scope']}`；登记策略：`{err['mode']}`。实际处置须由对应事实确认。")
            if err.get('owner') == 'engine':
                raw_block('内部契约声明', err.get('expected'))
                lines.append(f"- 可复核证明摘要：`{err.get('proof_sha256')}`")
        elif 'owner' in err:
            lines.append(f"- 原记录责任标签：`{err['owner']}`；本报告未将该标签认定为已验证责任。")
        if not verified and code in _EE.CODE_CAUSE_CN:
            lines.append(f'- 旧编号说明：{_EE.CODE_CAUSE_CN[code]}')
        if 'observed' in err:
            raw_block('原始 observed（沿用既有脱敏）', err['observed'])
        detail = str(err.get('detail') or '')
        if detail:
            raw_block('原记录 detail（沿用既有脱敏）', detail)
        lines.append('')
    from cex_core.engine.ist_core.compile_engine.engine_disclosure import render_unverifiable_errors_cn
    lines.extend(render_unverifiable_errors_cn(fs))
    lines.extend(_authoring_attempt_requirement_lines(fs))
    lines.extend(['---', '', '## 调用方提供的人口清单', '', f'共 {len(population)} 个案号；逐案执行、隔离、暂停和交付状态以对应事实及凭据为准。', ''])
    lines.extend((f'- `{aid}`' for aid in population))
    lines.append('')
    return '\n'.join(lines)

def render_defect_candidates_md(entries: list[dict], manifest: dict) -> str:
    lines = [f'# 工程与产品处置候选单 — {_batch_name(manifest)}', f"> 生成 {time.strftime('%Y-%m-%d %H:%M', time.localtime())} · 共 {len(entries)} 案 · 候选非终判", '']
    for e in entries:
        _dc_aid = str(e.get('autoid') or '')
        lines.append(f"## {e.get('title') or '用例 …' + _dc_aid[-6:]}")
        _owner = str(e.get('action_owner') or 'product')
        _owner_cn = '引擎工程' if _owner == 'engine' else '产品'
        _kind_cn = '工程修复候选（非产品缺陷）' if _owner == 'engine' else '产品缺陷候选'
        lines.append(f'- 负责人:{_owner_cn} · {_kind_cn} · 候选非终判')
        if e.get('owner_action'):
            lines.append(f"- 负责人动作:{e['owner_action']}")
        if e.get('device_evidence_binding') == 'unverified':
            lines.append('- 执行依据:未绑定到对应的有效执行结果；模型主张保留待核。')
        elif e.get('device_evidence_binding') == 'operator_ruling':
            lines.append('- 判断来源:用户裁决；此标记不表示设备实测凭据已闭合。')
        _uc = e.get('user_confirmed')
        if str(e.get('action_owner') or '') == 'engine':
            _uc_tag = ' · 工程修复候选 / 非产品缺陷'
        elif _uc is True:
            _uc_tag = ' · **你已确认为产品缺陷**'
        elif _uc is False:
            _uc_tag = ' · 机器疑似 / 待后续核验'
        else:
            _uc_tag = ' · 待条件核验(你的回答附有条件,条件尚未验证)'
        lines.append(f"- 编号 `{_dc_aid}`(尾号 {_dc_aid[-6:]}) · 当前状态:{STATUS_CN.get(str(e.get('status')), e.get('status'))}" + _uc_tag)
        claims = e.get('claims') or []
        if claims:
            lines.append('\n**缺陷主张**(全史,后轮改判不隐去先前主张):')
            for cl in claims:
                _rd = '引擎自动裁决' if cl.get('is_terminal') else f"第 {cl.get('round')} 轮"
                lines.append(f"- {_rd}:{cl.get('user_note') or '(详见 facts.jsonl 缺陷候选记录)'}")
                if cl.get('evidence'):
                    lines.append('  ```device-evidence\n  ' + clean_device_echo(str(cl['evidence']), 300) + '\n  ```')
        else:
            lines.append(f"\n**缺陷主张**:{e.get('latest_claim') or '(详见 facts.jsonl 缺陷候选记录)'}")
        form = e.get('form') or {}
        if form:
            lines.append('\n**结构化表单**:')
            for key, label in (('repro', '复现步骤'), ('expected_with_source', '预期(含出处)'), ('actual', '实际'), ('version', '版本'), ('ticket_id', '单号')):
                raw = form.get(key)
                if key == 'expected_with_source' and isinstance(raw, dict):
                    source = raw.get('source') if isinstance(raw.get('source'), dict) else {}
                    receipt = source.get('receipt') if isinstance(source.get('receipt'), dict) else {}
                    source_label = {'manual': '手册来源已核验', 'precedent': '验证先例来源已核验', 'footprint': '设备事实来源已核验'}.get(str(source.get('kind') or ''), '来源已核验')
                    if receipt.get('line_start'):
                        source_label += f"，第 {int(receipt['line_start'])} 行"
                    v = f"{str(raw.get('expected') or '').strip()} [{source_label}]".strip()
                else:
                    v = str(raw or '').strip()
                if v:
                    lines.append(f'- {label}:{v}')
        trail = e.get('disposition_trail') or []
        if trail:
            words = []
            for t in trail:
                w = DISP_CN.get(str(t.get('disposition')), str(t.get('disposition')))
                if t.get('by_user'):
                    r = '用户裁决'
                elif t.get('is_terminal'):
                    r = '引擎自动裁决'
                else:
                    r = f"第{t.get('round')}轮"
                words.append(f'{r} {w}' + ('(你的裁决)' if t.get('by_user') else ''))
            lines.append('\n**处置轨迹**:' + ' → '.join(words))
        lines.append('')
    return '\n'.join(lines) + '\n'

def public_defect_candidates(entries: list[dict]) -> list[dict]:
    public = copy.deepcopy(entries)
    kind_cn = {'manual': '手册', 'precedent': '验证先例', 'footprint': '设备事实'}
    for entry in public:
        form = entry.get('form')
        if not isinstance(form, dict):
            continue
        expected = form.get('expected_with_source')
        if not isinstance(expected, dict):
            continue
        source = expected.get('source')
        if not isinstance(source, dict):
            continue
        receipt = source.get('receipt') if isinstance(source.get('receipt'), dict) else {}
        expected['source'] = {'type': kind_cn.get(str(source.get('kind') or ''), '已核验来源'), 'verified': bool(receipt.get('sha256')), 'sha256': str(receipt.get('sha256') or ''), **({'line_start': int(receipt['line_start']), 'line_end': int(receipt.get('line_end') or receipt['line_start'])} if receipt.get('line_start') else {})}
    return public

def render_unsuccessful_md(report: dict, fs: list[dict], manifest: dict, queues: dict[str, list[dict]], evidence: dict[str, str], panels: dict[str, dict] | None=None) -> str:
    mcases = {str(c.get('autoid')): c for c in manifest.get('cases') or []}
    bad = {a: c for a, c in (report.get('cases') or {}).items() if c.get('status') != 'deliverable'}
    _nfp_reasons = (report.get('not_fixpoint') or {}).get('reasons') or {}
    _advanced = set(report.get('advanced_this_round') or [])
    lines = [f'# 未通过用例详报 — {_batch_name(manifest)}', f"> 生成 {time.strftime('%Y-%m-%d %H:%M', time.localtime())} · 共 {len(bad)} 个", '']
    _merge_rejection = _merge_rejected_lines(fs)
    if _merge_rejection:
        lines += _merge_rejection + ['']
    for aid, c in sorted(bad.items()):
        mine = [f for f in fs if str(f.get('aid')) == aid]
        mc = mcases.get(aid) or {}
        lines += _case_section(aid, c, mine, mc, queues.get(aid) or [], (panels or {}).get(aid), not_fixpoint_reason=_nfp_reasons.get(aid, ''), advanced_this_round=aid in _advanced, facts=fs)
        lines.extend(_authoring_attempt_requirement_lines(mine))
        sis = mc.get('step_intents') or []
        if sis:
            lines.append('\n**脑图原始用例**:')
            for si in sis:
                d, e = (str(si.get('desc') or ''), str(si.get('expected') or ''))
                lines.append(f'- {d}' + (f' → 预期:{e}' if e else ''))
        ev = evidence.get(aid) or ''
        if ev:
            lines.append('\n**最后一次设备关键回显**(已剥时间戳,原文在事实台账):')
            lines.append('```device-evidence\n' + clean_device_echo(ev, 1500) + '\n```')
        lines.append('')
    return '\n'.join(lines) + '\n'

def precedent_sourced_assertions(provenance: dict) -> list:
    out = []
    for i, step in enumerate((provenance or {}).get('steps') or []):
        if not isinstance(step, dict):
            continue
        src = step.get('source') or {}
        f = str(step.get('F') or '')
        if str(src.get('kind')) == 'precedent' and f in ('found', 'not_found', 'abs_found'):
            out.append({'step': i, 'F': f, 'ref': str(src.get('ref') or '')})
    return out
