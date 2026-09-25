# 生成：tools/extract_engine.py ← InfoTest main/ist_core/display_lexicon.py（sha256 1ce3eb396f2675f3）。不在这里手改。
from __future__ import annotations
from collections.abc import Mapping
DELIVERY_INCOMPLETE_REASON_CN = {'final_volume_identity': '主卷的组成或字节身份没通过收口核对', 'execution_terminal': '有用例在上机这一步失败、需引擎修复后重跑', 'not_fixpoint': '有用例本轮没走到定局(既没通过也没判死)', 'defect_candidates_unwritable': '处置候选单没能写到盘上', 'deliverable_files_missing': '交付物清单里有文件没写到盘上', 'merge_rejected': '整卷合并被卷面规则拒绝,本轮没有可上机的卷', 'api_error': '有用例因API接口错误未编写，引擎未补派第二波', 'population_unfinished': '本批仍有未终结用例，不算完整交付'}

def window_audit_summary_cn(record: Mapping) -> str:
    from cex_core.engine.ist_core.tools.device.window_audit import CONFIRMED_DISTORTION_KINDS
    parts = []
    distortion = record.get('window_distortion')
    if distortion is True:
        parts.append('历史窗口失真记录，明细缺失')
    elif isinstance(distortion, list) and any((isinstance(row, Mapping) and row.get('kind') in CONFIRMED_DISTORTION_KINDS for row in distortion)):
        parts.append(f"确认断言窗口出处不符 {record.get('window_distortion_total', len(distortion))} 项")
    desync = record.get('session_desync') or record.get('observations') or []
    if isinstance(desync, list) and desync:
        count = record.get('session_desync_total', record.get('observation_total', len(desync)))
        if str(record.get('broken_subtype') or '') == 'errored':
            parts.append(f'本案自身命令读窗超时后会话响应失步 {count} 处，本用例结果记为未跑成，本轮未取得有效结果')
        else:
            parts.append(f'会话响应落后一拍 {count} 处，读取到的返回窗里是本会话早先命令的回显，本用例结果记为未跑成，本轮未取得有效结果')
    uncertain = record.get('window_alignment_uncertain')
    if isinstance(uncertain, list) and uncertain:
        parts.append(f"窗口对齐未确定 {record.get('window_alignment_uncertain_total', len(uncertain))} 项，只披露")
    if record.get('ev') == 'session_desync_cluster':
        parts.append(f"同次执行中相邻 {len(record.get('autoids') or [])} 案出现会话失步；仅记录共现，未确定共同原因")
    if not parts:
        return ''
    aid = str(record.get('aid') or record.get('autoid') or '')
    prefix = f'用例 {aid}：' if aid else ''
    return prefix + '；'.join(parts)
TOOL_SHORT_NAMES: dict[str, str] = {'fs_read': 'Read', 'fs_grep': 'Grep', 'fs_glob': 'Glob', 'fs_ls': 'Ls', 'fs_write': 'Write', 'fs_edit': 'Edit', 'run_shell': 'Bash', 'run_python': 'Exec', 'invoke_skill': 'Skill', 'kb_footprint': 'Footprint', 'kb_bug_search': 'BugSearch', 'kb_memory_search': 'Memory', 'write_todos': 'TodoWrite', 'task': 'Agent', 'compile_emit': 'Emit', 'compile_emit_merged': 'EmitMerged', 'compile_engine_run': 'EngineRun', 'compile_fanout': 'Fanout', 'compile_prep': 'Prep', 'compile_check_verifiability': 'Verifiability', 'compile_expected_hits': 'ExpectedHits', 'compile_attribute': 'Attribute', 'compile_runtime_slots': 'RuntimeSlots', 'compile_runtime_fill': 'RuntimeFill', 'package_publish': 'PackagePublish', 'compile_footprint_writeback': 'FpWriteback', 'submit_attribution': 'Attribution', 'dev_probe': 'Probe', 'dev_ssh': 'Ssh', 'dev_rest': 'Rest', 'dev_run_case': 'RunCase', 'dev_run_batch': 'RunBatch', 'dev_run_batch_digest': 'RunDigest', 'agent_define': 'AgentDefine', 'dev_help': 'Help', 'dev_init_device': 'InitDevice', 'kb_intent_search': 'IntentSearch', 'compile_report_underdetermined': 'Underdet', 'lang_query': 'LangQuery', 'compile_query': 'LangQuery', 'compile_lint': 'Lint', 'local_replay': 'Replay', 'compile_user_decision': 'UserDecision', 'submit_ask_panel': 'AskPanel', 'submit_behavior_fact': 'BehaviorFact', 'actor': 'Actor', 'ask_user': 'AskUser', 'compile_env_identity': 'EnvIdentity', 'compile_env_preflight': 'EnvPreflight', 'compile_verified_writeback': 'VerifiedWriteback', 'dev_batch_analysis': 'BatchAnalysis', 'download_agile_case': 'DownloadCase', 'ide_compile': 'IdeCompile', 'ide_execute_log': 'IdeLog', 'ide_validate': 'IdeValidate', 'remember': 'Remember', 'svc_ask_route': 'AskRoute', 'svc_brief_build': 'BriefBuild', 'svc_close_deliver': 'CloseDeliver', 'svc_dev_run': 'DevRun', 'svc_emit': 'SvcEmit', 'svc_merge': 'SvcMerge', 'svc_recompose': 'Recompose', 'svc_reconcile': 'Reconcile', 'svc_submit_status': 'SubmitStatus', 'svc_writeback': 'Writeback', 'typesafe_judge': 'Jev'}
_SUMMARY_MAX = 60
TOOL_ARG_SUMMARY: dict[str, tuple[tuple[str, str], ...]] = {'fs_read': (('path', 'path_tail'), ('file_path', 'path_tail')), 'fs_write': (('path', 'path_tail'), ('file_path', 'path_tail')), 'fs_edit': (('path', 'path_tail'), ('file_path', 'path_tail')), 'fs_ls': (('path', 'path_tail'), ('file_path', 'path_tail')), 'fs_glob': (('pattern', 'text'),), 'fs_grep': (('pattern', 'text'), ('query', 'text')), 'run_python': (('code', 'first_line'),), 'run_shell': (('command', 'first_line'),), 'remember': (('lesson', 'first_line'), ('topic', 'text')), 'invoke_skill': (('skill', 'skill'),), 'task': (('description', 'text'), ('subagent_type', 'text')), 'agent_define': (('name', 'text'),), 'actor': (('operation', 'text'),), 'ask_user': (('questions', 'text'),), 'write_todos': (('todos', 'text'),), 'kb_footprint': (('command', 'command'),), 'kb_bug_search': (('ticket_id', 'text'), ('case_context', 'text')), 'kb_memory_search': (('query', 'text'),), 'kb_intent_search': (('query', 'text'),), 'typesafe_judge': (('questions', 'text'),), 'dev_probe': (('command', 'command'),), 'dev_ssh': (('command', 'command'),), 'dev_rest': (('path', 'text'), ('command', 'command')), 'dev_help': (('command', 'command'),), 'dev_init_device': (('host', 'text'),), 'dev_run_case': (('autoid', 'autoid'), ('xlsx_path', 'path_tail')), 'dev_run_batch': (('xlsx_path', 'path_tail'),), 'dev_run_batch_digest': (('xlsx_path', 'path_tail'),), 'dev_batch_analysis': (('autoid', 'autoid'), ('out_name', 'text')), 'compile_emit': (('autoid', 'autoid'),), 'compile_emit_merged': (('out_name', 'text'), ('xlsx_path', 'path_tail')), 'compile_engine_run': (('mindmap_path', 'stem'), ('out_name', 'text'), ('product_version', 'text')), 'compile_prep': (('mindmap_path', 'stem'), ('out_name', 'text')), 'compile_fanout': (('skill', 'text'),), 'compile_check_verifiability': (('autoid', 'autoid'),), 'compile_expected_hits': (('autoid', 'autoid'),), 'compile_attribute': (('autoid', 'autoid'), ('verdict_detail', 'text')), 'compile_runtime_slots': (('xlsx_path', 'path_tail'),), 'compile_runtime_fill': (('xlsx_path', 'path_tail'),), 'compile_user_decision': (('autoid', 'autoid'),), 'compile_verified_writeback': (('xlsx_path', 'path_tail'),), 'compile_footprint_writeback': (('autoid', 'autoid'),), 'compile_report_underdetermined': (('autoid', 'autoid'),), 'compile_env_identity': (), 'compile_env_preflight': (), 'package_publish': (('autoid', 'autoid'), ('xlsx_path', 'path_tail')), 'submit_attribution': (('autoid', 'autoid'), ('xlsx_path', 'path_tail')), 'submit_ask_panel': (('autoid', 'autoid'),), 'submit_behavior_fact': (('autoid', 'autoid'),), 'download_agile_case': (('case_id', 'text'), ('suite_name', 'text')), 'ide_validate': (('build', 'text'),), 'ide_compile': (('batch_name', 'text'), ('mechanical_case_path', 'stem')), 'ide_execute_log': (('autoid', 'autoid'), ('batch_name', 'text')), 'lang_query': (('kind', 'text'), ('name', 'text')), 'compile_query': (('kind', 'text'), ('name', 'text')), 'compile_lint': (('autoid', 'autoid'),), 'local_replay': (('autoid', 'autoid'),), 'svc_recompose': (('batch', 'text'),), 'svc_brief_build': (('batch', 'text'),), 'svc_submit_status': (('batch', 'text'),), 'svc_emit': (('batch', 'text'),), 'svc_merge': (('batch', 'text'),), 'svc_dev_run': (('batch', 'text'),), 'svc_reconcile': (('batch', 'text'),), 'svc_writeback': (('batch', 'text'),), 'svc_ask_route': (('batch', 'text'),), 'svc_close_deliver': (('batch', 'text'),)}
IDE_TOOL_FAMILY: dict[str, str] = {'lang_query': 'query', 'compile_query': 'query', 'compile_lint': 'lint', 'submit_mechanical_case': 'lint', 'local_replay': 'replay'}
LEGACY_LABEL_FAMILY: dict[str, str] = {'补全/悬停': 'query', '写时检查': 'lint', '本地模拟考': 'replay'}
LEGACY_KIND_CN: dict[str, str] = {'signature': '方法签名', 'dispatch': '角色/派发', 'usage': '真实用法', 'nearest': '近似补全', 'prompt_pattern': '交互序列'}
LINT_ACTION = '规则校验'
REPLAY_ACTION = '离线回放'
DISPATCH_PROGRESS_LABEL = '准备用例材料'
GROUNDING_REFERENCE_STALE_CN = '命令查询参考未能按当前环境更新，本批编写不带这份可选参考'
PREFLIGHT_PROGRESS_LABEL = '上机前环境检查'
PREFLIGHT_PROGRESS_UNIT = '项'
PREFLIGHT_RETRY_SUFFIX = '重试'
PREFLIGHT_SKIP_LEAD = '个用例暂不上机'
PREFLIGHT_UNAVAILABLE_CN = '连不上测试设备，本卷不上机；设备恢复后以同参数续跑'
PREFLIGHT_RESIDUAL_NOUN_CN = '设备上已有'
PREFLIGHT_CONFIG_NOUN_CN = '配置'
PREFLIGHT_ATLAS_GAP_NOUN_CN = '没有对应的查看命令'

def preflight_skip_reason_cn(reason_code: str, command_head: str) -> str:
    head = str(command_head or '').strip()
    if str(reason_code or '') == 'command_domain_residual':
        parts = [PREFLIGHT_RESIDUAL_NOUN_CN, head, PREFLIGHT_CONFIG_NOUN_CN]
        return ' '.join((part for part in parts if part))
    tail = f'{PREFLIGHT_ATLAS_GAP_NOUN_CN}可核对'
    return f'{head} {tail}' if head else tail

def preflight_skip_summary_cn(items: object) -> str:
    rows = [item for item in items or [] if isinstance(item, Mapping)]
    if not rows:
        return ''
    parts = []
    for item in rows:
        aid = str(item.get('autoid') or '')
        reason = preflight_skip_reason_cn(str(item.get('reason_code') or ''), str(item.get('command_head') or ''))
        parts.append(f'{aid[-6:]} {reason}'.strip())
    return f'{len(rows)} {PREFLIGHT_SKIP_LEAD}：' + ' · '.join(parts)

def preflight_head_line_cn(snapshot_key: str, item: Mapping) -> str:
    target = str(snapshot_key).split(':', 1)[0]
    aid = str(item.get('autoid') or '')
    head = str(item.get('command_head') or '')
    count = int(item.get('line_count') or 0)
    round_number = item.get('preflight_round')
    prefix = f'第 {round_number} 次检查，' if round_number else ''
    return f'{prefix}用例 {aid}，设备 {target} 上 {head} 下有 {count} 行配置；本检查不据此隔离用例'

def preflight_head_lines_summary_cn(disclosures: Mapping) -> str:
    total = sum((len(items) for items in disclosures.values()))
    if not total:
        return ''
    key, items = next(((key, items) for key, items in disclosures.items() if items))
    preview = preflight_head_line_cn(key, items[0])
    if len(preview) > 200:
        preview = preview[:199] + '…'
    return f'配置观察共 {total} 项（逐案、逐次计，预览 1 项）：{preview}；完整记录见检查收据'
DISCLOSURE_LOAD_LEAD_CN = '机械脑图无法读回'
DEVICE_DISCLOSURE_TAG_CN = {'T1': '采样口径', 'T2': '设备特性', 'T3': '本案触发', 'T4': '未钉住'}
DEVICE_DISCLOSURE_TAG_FALLBACK_CN = '设备特性'
DEVICE_DISCLOSURE_HEAD_CN = '这台设备在这件事上记着什么'
DEVICE_DISCLOSURE_SUMMARY_TMPL_CN = '共 {count} 条，分{tiers}几档；下面每条都注明手册出处，按需展开。引擎不替作者定采样次数，也不据此判定通过与否。'
_DEVICE_DISCLOSURE_CN = {'sampling_required': '这条预期看的是多次请求的命中分布，单次命中判不了，要采样', 'count_is_worker_declared': '采样几次、每档容差多少由编写侧自己声明，引擎不定这个数', 'device_decides': '实际命中分布以设备回显为准', 'characteristics_unavailable': '设备特性本轮取不到，这一案没有按设备性质的提示', 'no_characteristic_for_pair': '这类对象在文档里没有可用的设备性质，本轮不提示', 'no_object_kind_declared': '本案步骤没有写明对象类型，设备性质无从匹配，本轮不提示', 'trigger_echo_bounded': '触发端回显按字节上限携带，超长的部分会被截断', 'observation_pairing_unavailable': '对不上这条预期是在哪一步观测的', 'characteristics_truncated': '这类对象的设备性质还有没列出来的，其余见设备特性投影'}
DEVICE_DISCLOSURE_TRIGGER_FALLBACK_CN = '本案结构触发'

def device_disclosure_cn(row: Mapping[str, object]) -> str:
    if not isinstance(row, Mapping):
        return ''
    code = str(row.get('code') or '')
    detail = row.get('detail')
    detail = detail if isinstance(detail, Mapping) else {}
    if code == 'authored_count':
        step = str(detail.get('step') or '').strip()
        count = detail.get('count')
        if not isinstance(count, int) or isinstance(count, bool):
            return ''
        where = f'第{step}步' if step else ''
        source_text = ' '.join(str(detail.get('source_text') or '').split())
        if source_text:
            return f'{where}作者数量条件：{source_text}'
        return f'{where}作者记录的数量值：{count}（单位未记录）'
    if code == 'behaviour_unclassified':
        method = str(detail.get('method') or '').strip()
        named = f'「{method}」' if method else ''
        return f'算法{named}在手册里没查到属于哪一类，本轮不按类别提示'
    if code == 'counter_field_undocumented':
        command = str(detail.get('show_command') or '').strip()
        named = f'「{command}」' if command else ''
        return f'计数命令{named}的字段手册没有定义，读回的数字含义未钉死'
    if code == 'characteristic_scope_unverified':
        declared = '、'.join((str(value) for value in detail.get('object_kinds') or ())) or '未记录'
        documented = '、'.join((str(value) for value in detail.get('documented_object_kinds') or ())) or '未记录'
        text = str(row.get('text') or '').strip()
        locator = str(row.get('locator') or '').strip()
        source = f'（{locator}）' if locator else ''
        note = f'本案结构列出{declared}，这条文档特性适用于{documented}，适用范围未核'
        return f'{note}：{text}{source}' if text else note
    if code in _DEVICE_DISCLOSURE_CN:
        return _DEVICE_DISCLOSURE_CN[code]
    if code in ('characteristic', 'structure_characteristic'):
        text = str(row.get('text') or '').strip()
        if not text:
            return ''
        locator = str(row.get('locator') or '').strip()
        source = f'（{locator}）' if locator else ''
        if code == 'characteristic':
            return f'{text}{source}'
        steps = [str(value).strip() for value in detail.get('steps') or () if str(value).strip()]
        where = f"第 {'、'.join(steps)} 步" if steps else ''
        label = str(detail.get('label_zh') or '').strip() or DEVICE_DISCLOSURE_TRIGGER_FALLBACK_CN
        return f'{where}{label}：{text}{source}'
    return ''
MECHANICAL_FINDING_HEAD_CN = '交卷时的机械核对'
MECHANICAL_FINDING_SUMMARY_TMPL_CN = '共 {count} 条，都不阻断本次提交；每条注明手册出处，按需展开。'
_MECHANICAL_FINDING_CN = {'bed_facts_unavailable': '本轮取不到床上的触发机与地址登记，本案没有做触发机与查询目标的配对核对'}

def mechanical_finding_cn(finding: Mapping[str, object]) -> str:
    if not isinstance(finding, Mapping):
        return ''
    code = str(finding.get('code') or '')
    if code in _MECHANICAL_FINDING_CN:
        return _MECHANICAL_FINDING_CN[code]
    locator = str(finding.get('locator') or '').strip()
    source = f'（{locator}）' if locator else ''
    text = ' '.join(str(finding.get('text') or '').split())
    host = str(finding.get('host') or '').strip()
    target = str(finding.get('target') or '').strip()
    if code == 'feature_prerequisite_missing':
        if not text:
            return ''
        return f'本案配置了这类对象并从触发机发查询，但没有启用步；手册记着：{text}{source}'
    if code == 'query_target_not_listener':
        if not text or not target:
            return ''
        return f'观测步查的是 {target}，本案没有把这个地址配成监听地址；手册记着：{text}{source}'
    if code == 'trigger_host_not_paired_with_target':
        if not host or not target:
            return ''
        paired = [str(name).strip() for name in finding.get('paired_hosts') or () if str(name).strip()]
        who = '、'.join(paired) if paired else ''
        tail = f'床上与 {target} 同段的触发机是 {who}' if who else f'床上没有与 {target} 同段的触发机'
        return f'观测步在 {host} 上查 {target}，{tail}'
    if code == 'query_target_not_on_device':
        if not host or not target:
            return ''
        return f'观测步在 {host} 上查 {target}，这个地址不在床上任何一台设备的登记里'
    return ''

def device_disclosure_tag_cn(tier: object) -> str:
    return DEVICE_DISCLOSURE_TAG_CN.get(str(tier or ''), DEVICE_DISCLOSURE_TAG_FALLBACK_CN)
STEP_STRUCTURE_ABSENT_CN = '这份用例没有步骤结构层，本轮的作者场景没做逐步机械核对，全部交由审核判断'
STEP_STRUCTURE_KIND_SKIPPED_CN = '设备命令树本轮取不到，步骤结构层里的对象类型这一格没有核对'
STEP_STRUCTURE_INVALID_TAG_CN = '步骤结构不合规'
_STEP_STRUCTURE_CODE_CN = {'step_structure_missing': '有步骤没写结构条目', 'step_structure_condition_not_verbatim': '条件的作者原文锚接不到本步密封原文', 'step_structure_operation_head_unknown': '命令头本案没核过', 'step_structure_object_kind_unknown': '对象类型不在设备命令树里', 'step_structure_slot_ref_unresolved': '未写明取值的引用指不到', 'step_structure_count_out_of_range': '数值超出可判范围', 'step_structure_adaptation_invalid': '适配步骤旁列不合规'}

def _step_structure_codes_cn(codes: object) -> str:
    seen: list[str] = []
    for code in codes or ():
        text = _STEP_STRUCTURE_CODE_CN.get(str(code), str(code or '').strip())
        if text and text not in seen:
            seen.append(text)
    return '、'.join(seen)

def step_structure_quarantine_error_cn(codes: object) -> str:
    named = _step_structure_codes_cn(codes)
    detail = f'（{named}）' if named else ''
    return f'重组写的步骤结构层不合规{detail}，本轮退回，不编写'

def step_structure_quarantine_disclosure_cn(codes: object) -> str:
    named = _step_structure_codes_cn(codes)
    where = f'步骤结构层这几处不合规：{named}；' if named else '步骤结构层不合规；'
    return f'{where}本轮不出卡、不编写，再跑会重新重组，你的脑图原文不受影响'
SCENARIO_FIDELITY_MECHANICAL_LEAD_CN = '作者场景已按结构逐步核对'
SCENARIO_FIDELITY_EXEMPT_LEAD_CN = '以下几处不按偏离计'

def scenario_fidelity_exemption_cn(exemption: Mapping[str, object]) -> str:
    if not isinstance(exemption, Mapping):
        return ''
    kind = str(exemption.get('kind') or '')
    step = str(exemption.get('step') or '').strip()
    where = f'第{step}步' if step else ''
    if kind == 'added_precondition':
        text = str(exemption.get('text') or '').strip()
        return f'补齐用例未写的前置条件（{text}）' if text else '补齐用例未写的前置条件'
    if kind == 'distribution_sampling':
        authored = exemption.get('authored_count')
        declared = exemption.get('declared_count')
        steps = [str(n).strip() for n in exemption.get('steps') or () if str(n).strip()]
        where_steps = where or (f'第{steps[0]}步' if len(set(steps)) == 1 else '')
        originals = list(dict.fromkeys((str(row.get('text') or row.get('value') or '').strip() for row in exemption.get('overrides') or () if isinstance(row, Mapping) and str(row.get('text') or row.get('value') or '').strip())))
        if originals:
            head = f'{where_steps}作者数量条件：' + '；'.join(originals)
        elif isinstance(authored, int) and (not isinstance(authored, bool)):
            head = f'{where_steps}作者数量值 {authored}（单位未记录）'
        else:
            head = f'{where_steps}未取得可核的作者采样次数'
        tail = '；采样执行次数及其与计数的关系尚未核验'
        if isinstance(declared, int) and (not isinstance(declared, bool)):
            return f'{head}，编写侧按分布判据声明采样 {declared} 次{tail}'
        return f'{head}，本判据未唯一绑定编写侧的采样次数声明，不按次数偏离计{tail}'
    if kind == 'free_slot':
        slot = str(exemption.get('slot') or '').strip()
        named = f'「{slot}」' if slot else ''
        return f'{where}用例未写明的取值{named}由编写侧选定'
    return ''
SCENARIO_FIDELITY_HEAD_CN = {'preserved': '作者场景已核对：编写出来的用例保住了作者写的场景', 'rejected': '作者场景没保住：本轮按编写不合格退回重编', 'unavailable': '作者场景本轮没核对'}
SCENARIO_FIDELITY_HEAD_FALLBACK_CN = '作者场景核对'
SCENARIO_FIDELITY_UNAVAILABLE_TAIL_CN = '没核对不阻断交付，但这一案的场景保真这一项本轮没有结论，先例库不据此认证。'

def scenario_fidelity_mechanical_cn(mechanical: Mapping[str, object]) -> str:
    if not isinstance(mechanical, Mapping) or mechanical.get('status') != 'compared':
        return ''
    realized = [str(item) for item in mechanical.get('realized_steps') or []]
    residue = [str(item) for item in mechanical.get('residue_steps') or []]
    head = f'{SCENARIO_FIDELITY_MECHANICAL_LEAD_CN}：{len(realized)} 步逐条对上'
    if residue:
        head += f"，第 {'、'.join(residue)} 步交由审核判断"
    else:
        head += '，无待判步骤'
    lines = [text for text in (scenario_fidelity_exemption_cn(item) for item in mechanical.get('exemptions') or () if isinstance(item, Mapping)) if text]
    if not lines:
        return f'{head}。'
    return f'{head}。{SCENARIO_FIDELITY_EXEMPT_LEAD_CN}：' + '；'.join(lines[:8]) + '。'

def _byte_size_cn(value: object) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return ''
    if size < 0:
        return ''
    if size >= 1024 * 1024:
        text = f'{size / (1024 * 1024):.1f}'
        return f"{(text[:-2] if text.endswith('.0') else text)} MB"
    if size >= 1024:
        return f'{size / 1024:.0f} KB'
    return f'{size} 字节'

def _measured(diagnostic: Mapping[str, object] | None, key: str) -> int | None:
    rows = diagnostic if isinstance(diagnostic, Mapping) else {}
    try:
        return int(rows[key])
    except (KeyError, TypeError, ValueError):
        return None
_DISCLOSURE_LOAD_REASON_CN: dict[str, str] = {'bytes_over_limit': '披露记录太大', 'structure_budget_exceeded': '披露记录条目层次太多', 'json_invalid': '披露记录的内容读不成形', 'digest_mismatch': '披露记录与本轮登记的用例对不上', 'ref_invalid': '披露记录里指向用例的编号对不上', 'sealed_read_failed': '披露记录打不开'}

def disclosure_load_reason_parts(reason: str, diagnostic: Mapping[str, object] | None=None) -> tuple[str, str]:
    code = str(reason or '')
    size = _byte_size_cn(_measured(diagnostic, 'bytes'))
    size_limit = _byte_size_cn(_measured(diagnostic, 'max_bytes'))
    tokens = _measured(diagnostic, 'tokens')
    token_limit = _measured(diagnostic, 'max_tokens')
    tokens_over = tokens is not None and token_limit is not None and (tokens > token_limit)
    raw_bytes = _measured(diagnostic, 'bytes')
    raw_limit = _measured(diagnostic, 'max_bytes')
    bytes_over = raw_bytes is not None and raw_limit is not None and (raw_bytes > raw_limit)
    if code == 'bytes_over_limit' and bytes_over and size and size_limit:
        clause = f'披露记录 {size}，超过 {size_limit} 上限'
        if tokens_over:
            clause += f'（结构项 {tokens:,} / {token_limit:,}）'
        return (DISCLOSURE_LOAD_LEAD_CN, clause)
    if code == 'structure_budget_exceeded' and tokens_over:
        clause = f'结构项 {tokens:,} 超过 {token_limit:,} 上限'
        if size:
            clause += f'（披露记录 {size}）'
        return (DISCLOSURE_LOAD_LEAD_CN, clause)
    short = _DISCLOSURE_LOAD_REASON_CN.get(code)
    return (DISCLOSURE_LOAD_LEAD_CN, short or '')

def disclosure_load_reason_cn(reason: str, diagnostic: Mapping[str, object] | None=None) -> str:
    lead, detail = disclosure_load_reason_parts(reason, diagnostic)
    return f'{lead}：{detail}' if detail else lead
API_ERROR_LEAD_CN = 'API错误'
API_MESSAGE_CARD_MAX = 40
API_MESSAGE_TERMINAL_MAX = 120
TRUNCATION_MARK = '…'
API_ZERO_RESPONSE_CODE_CN = '无响应'
API_ZERO_RESPONSE_MESSAGE_CN = '0 token'
API_MESSAGE_UNAVAILABLE_CN = '接口未提供可读原因'

def _clip_message(message: object, limit: int) -> str:
    text = ' '.join(str(message or '').split())
    if not text:
        return ''
    try:
        width = int(limit)
    except (TypeError, ValueError):
        width = API_MESSAGE_TERMINAL_MAX
    if width <= 0 or len(text) <= width:
        return text
    return text[:width] + TRUNCATION_MARK

def api_error_sentence(code: object, message: object='', *, limit: int=API_MESSAGE_TERMINAL_MAX) -> str:
    head = str(code if code not in (None, '') else '').strip()
    if not head:
        return ''
    body = _clip_message(message, limit)
    return f'{API_ERROR_LEAD_CN}（{head}：{body}）' if body else f'{API_ERROR_LEAD_CN}（{head}）'
API_GOTO_NETWORK_CN = '检查网络后以同参数续跑'
API_NETWORK_CODES: frozenset[str] = frozenset({'ReadError', 'ConnectError', 'RemoteProtocolError', 'APIConnectionError', 'APITimeoutError', 'ReadTimeout', 'ConnectTimeout', 'TimeoutException'})
API_ERROR_GOTO_CN: dict[object, str] = {400: '更换模型或API接口后重跑', 401: '充值或更正密钥后重跑', 402: '充值或更换API接口后以同参数续跑', 403: '确认账号权限或等用量窗口重置后重试', 429: '稍后以同参数重试', **{name: API_GOTO_NETWORK_CN for name in sorted(API_NETWORK_CODES)}}
API_ERROR_GOTO_DEFAULT_CN = '稍后以同参数重试'
API_SCOPE_TURN = 'turn'
API_SCOPE_CASE = 'case'
API_SCOPE_BATCH = 'batch'
API_SCOPE_WAVE = 'wave'
_RETRY_GOTO_BY_SCOPE: dict[str, str] = {API_SCOPE_TURN: '请稍后重试', API_SCOPE_CASE: '本案稍后以同参数续跑', API_SCOPE_BATCH: '本批稍后以同参数续跑', API_SCOPE_WAVE: '这些用例稍后以同参数续跑'}
_SCOPE_FIXED_GOTO_CODES = frozenset({400, 401, 402, 403}) | API_NETWORK_CODES
API_GOTO_MODEL_UNAVAILABLE_CN = '更换模型后重试'
API_GOTO_ZERO_RESPONSE_CN = '检查API账户额度与接口状态后重试'

def api_error_goto_cn(code: object, *, scope: str='') -> str:
    if scope and code not in _SCOPE_FIXED_GOTO_CODES:
        scoped = _RETRY_GOTO_BY_SCOPE.get(str(scope))
        if scoped:
            return scoped
    return API_ERROR_GOTO_CN.get(code, API_ERROR_GOTO_DEFAULT_CN)
API_IMPACT_TURN_CN = '本轮未完成'
API_IMPACT_CASE_CN = '本案未编写'
API_IMPACT_BATCH_CN = '本批已停止'
API_IMPACT_CASE_UNFINISHED_CN = '本案未完成'

def api_error_verdict(code: object, message: object='', *, impact: str=API_IMPACT_TURN_CN, scope: str='', limit: int=API_MESSAGE_TERMINAL_MAX) -> str:
    head = api_error_sentence(code, message, limit=limit)
    if not head:
        return ''
    goto = api_error_goto_cn(code, scope=scope)
    return f'{head}，{impact}；{goto}'
FOOTER_API_ERROR_LEAD = 'API error'
FOOTER_RETRY_TIMEOUT = 'retry time out'
FOOTER_LONG_WAIT_S = 120

def _wait_duration_slot(seconds: object) -> str:
    secs = _slot_int(seconds)
    if secs is None or secs < 0:
        return ''
    return f'{secs // 60}m' if secs >= FOOTER_LONG_WAIT_S else f'{secs}s'
FOOTER_NO_TOKENS_YET = 'no tokens yet'
FOOTER_MODEL_CALL = 'model call'
FOOTER_BETWEEN_ROUNDS = 'between rounds'
FOOTER_WORKER_PREFIX = 'worker'

def api_error_slot(code: object, attempt: object=None, max_attempts: object=None, waited_s: object=None, *, exhausted: bool=False) -> str:
    head = str(code if code not in (None, '') else '').strip()
    if not head:
        return ''
    parts = [f'{FOOTER_API_ERROR_LEAD} {head}']
    n, total = (_slot_int(attempt), _slot_int(max_attempts))
    if n is not None and total is not None and (total > 0):
        parts.append(f'retry {n}/{total}')
    elif n is not None and n > 0 and (max_attempts is None):
        parts.append(f'retry #{n}')
    if exhausted:
        parts.append(FOOTER_RETRY_TIMEOUT)
    else:
        secs = _slot_int(waited_s)
        if secs is not None and secs > 0:
            parts.append(f'waiting {secs}s')
    return ' · '.join(parts)

def api_waiting_aggregate_slot(workers: object, code: object, longest_s: object, worker_id: object='') -> str:
    n = _slot_int(workers) or 0
    if n <= 0:
        return ''
    head = str(code if code not in (None, '') else '').strip()
    parts = [f'{n} workers waiting']
    if head:
        parts.append(f'{FOOTER_API_ERROR_LEAD} {head}')
    span = _wait_duration_slot(longest_s)
    if span:
        name = str(worker_id or '').strip()
        parts.append(f'longest {span} ({name})' if name else f'longest {span}')
    return ' · '.join(parts)

def footer_model_call_slot(seconds: object) -> str:
    secs = _slot_int(seconds)
    return f'{FOOTER_MODEL_CALL} {secs}s · {FOOTER_NO_TOKENS_YET}' if secs is not None else ''
FOOTER_TOOL_NAME_MAX = 24

def footer_tool_slot(tool: object, seconds: object) -> str:
    name = middle_ellipsis(' '.join(tool_short_name(str(tool or '')).split()), FOOTER_TOOL_NAME_MAX).strip()
    secs = _slot_int(seconds)
    return f'{name} {secs}s' if name and secs is not None else ''

def footer_between_rounds_slot(seconds: object) -> str:
    secs = _slot_int(seconds)
    return f'{FOOTER_BETWEEN_ROUNDS} {secs}s' if secs is not None else ''

def footer_worker_slot(worker_id: object, tail: str) -> str:
    name = str(worker_id or '').strip()
    body = str(tail or '').strip()
    if not body:
        return ''
    return f'{FOOTER_WORKER_PREFIX}·{name} · {body}' if name else body
_CJK_CLOSERS = '）」』】》〉'

def _join_segments(head: str, *rest: str) -> str:
    tail = [seg for seg in rest if seg]
    if not tail:
        return head
    joined = ' · '.join(tail)
    if head and head[-1] in _CJK_CLOSERS:
        return f'{head}· {joined}'
    return f'{head} · {joined}' if head else joined

def _slot_int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

def api_waiting_cn(code: object, message: object='', attempt: object=None, max_attempts: object=None, waited_s: object=None) -> str:
    head = api_error_sentence(code, message, limit=API_MESSAGE_CARD_MAX)
    if not head:
        return ''
    parts = []
    n, total = (_slot_int(attempt), _slot_int(max_attempts))
    if n is not None and total is not None and (total > 0):
        parts.append(f'重试 {n}/{total}')
    elif n is not None and n > 0 and (max_attempts is None):
        parts.append(f'第 {n} 次重试')
    secs = _slot_int(waited_s)
    if secs is not None and secs > 0:
        parts.append(f'已等 {secs}s')
    return _join_segments(head, *parts)

def api_waiting_from_field(waiting: Mapping[str, object] | None) -> str:
    if not isinstance(waiting, Mapping) or not waiting:
        return ''
    return api_waiting_cn(waiting.get('code'), waiting.get('message'), waiting.get('attempt'), waiting.get('max'), waiting.get('waited_s'))
TRANSIENT_EXHAUSTED_CN = '反复出错，重试已耗尽'
QUOTA_EXHAUSTED_CN = 'API账户额度不足'
FORK_TRANSIENT_NO_API_CN = '反复出错，重试已耗尽，本案未完成；引擎重新派发'
ENGINE_INTERNAL_FAULT_LEAD_CN = '引擎内部故障'
ENGINE_INTERNAL_FAULT_GOTO_CN = '请重试；若反复出现，这一条需要引擎侧修复'
EXECUTION_CAUSE_UNCONFIRMED_CN = '执行未完成，根因及责任未确认'
AUTHORING_EVIDENCE_UNCLOSED_CN = '编写证据核验未完成，具体根因和责任尚未确认'
GOVERNANCE_END_UNCLOSED_CN = '治理停止后的处理未完成，具体根因和责任尚未确认'
UNATTRIBUTED_AUTHORING_STOP_CN = '这一案的编写没有以引擎可核的结果结束，责任未核；原始记录已保留，同参续跑重入'
UNRECOGNIZED_ROUTING_DISCLOSURE_CN = '引擎遇到登记表里没有的路由值，不能折叠成默认出口；本案转入待裁决。'
UNRECOGNIZED_ROUTING_NEXT_CN = '把未登记的路由值交给引擎维护者处理后按身份重入。'
ARTIFACT_UNVERIFIABLE_DISCLOSURE_CN = '交卷审计核不到个案产物身份；本案转入待裁决，不随卷交付。'
ARTIFACT_UNVERIFIABLE_NEXT_CN = '核对个案产物身份后按身份重入。'
UNPROVEN_STOP_CAUSE_CN = {'verdict_contradiction_unresolved': '子集与整卷判决的矛盾本轮尚未消解', 'worker_envelope_invalid': '交回的结果没过引擎的格式校验，引擎收不下', 'no_output': '这次编写没有交回任何结果', 'not_executed': '这一案在本次编写里没有被执行', 'attempt_receipt_missing': '这次编写结束了，账上没有可核的交卷回执，这次尝试算不出成本', 'attempt_scope_missing': '这次编写的范围记录缺失或与派发对不上', 'authoring_account_unbound': '编写过程说明缺失或对不上这次编写', 'feedback_replay_unverified': '编写自查记录无法复核', 'unrecognized_routing_value': '登记表里没有这个路由值', 'case_artifact_identity_unverifiable': '交卷审计核不到个案产物身份'}
UNPROVEN_STOP_CAUSE_UNRECORDED_CN = '引擎没有记下可读的停止成因'
UNATTRIBUTED_AUTHORING_STOP_USER_OPTIONS_CN: tuple[str, ...] = ('同参数重跑本批，这一案从停下的地方重新编', '换一个编写模型再跑', '按本批批名与用例编号查 `workspace/outputs/<批名>/facts.jsonl` 里这一案的落账，看它停在哪一步')
UNATTRIBUTED_AUTHORING_STOP_USER_ACTION_CN = '可做的三件事：' + '；'.join((f'{mark}{text}' for mark, text in zip('①②③', UNATTRIBUTED_AUTHORING_STOP_USER_OPTIONS_CN)))

def unproven_stop_cause_cn(cause: object) -> str:
    """成因码 → 中文释义。闭集外与空码给「没记下来」，不编一句解释。"""
    return UNPROVEN_STOP_CAUSE_CN.get(str(cause or ''), UNPROVEN_STOP_CAUSE_UNRECORDED_CN)
CASE_STATE_CN: dict[str, str] = {'pending': '待编写', 'awaiting_user': '待你回答问询', 'composed': '已出机械稿，还没出卷', 'authored': '已出卷，待上机', 'subset_verified': '子集已过，待整卷终验', 'failed': '上机判失败，待归因后重编', 'contradicted': '同一卷面两次判决互斥，待裁决', 'broken': '没拿到可判读的结果，待原样复跑', 'broken_errored': '执行过程报错，待归因后重编', 'broken_blocked': '被外部条件挡住，条件恢复后重入', 'broken_aborted': '上机被中止，待原样复跑', 'broken_verdict_unrecognized': '回执里的判决读不出来，待原样复跑'}
PAUSE_KIND_CN = {'engine_condition': '引擎条件', 'supply': '供给预检', 'governance': '治理预算', 'authoring_evidence': '编写证据', 'env': '环境', 'bed': '测试设备', 'contra': '判决矛盾', 'api': '接口'}
FORCED_CLOSURE_PAUSE_UNCLOSED_CN = '收口时{kind}暂挂仍未闭合：引擎未在本轮给出结论，按引擎侧未闭合显式结案；原始记录保留，同参续跑重入'
CONTRADICTION_PAUSE_UNCLOSED_CN = '判决矛盾暂挂仍未闭合；原预期与原始记录已保留'
FORCED_CLOSURE_ESCALATION_UNCLOSED_CN = '收口时结果升级记录仍未落账：结果通道未闭合，按引擎侧未闭合显式结案；原始记录保留，同参续跑重入'
BATCH_BOUNDARY_EVENT_CN = {'bed_gate_mechanical_blocked': '测试设备就绪核验阻塞', 'engine_halt': '引擎停止记录', 'batch_execution_paused': '批级执行暂停', 'node_crash': '节点异常退出'}
FORCED_CLOSURE_BOUNDARY_UNCLOSED_CN = '本批在{event}后停止，该案本轮未结；批级停止记录与本案原始记录已保留'
FORCED_CLOSURE_COMMAND_DOMAIN_ISOLATED_CN = '命令域净态核缺少本案命令的图谱条目，本案被隔离未合卷：按引擎侧未闭合显式结案，补齐图谱后同参续跑重入'
FORCED_CLOSURE_NO_BOUNDARY_CN = '收口时该案仍未结，且本轮没有批级边界记录：按引擎侧未闭合显式结案；原始记录保留，同参续跑重入'
FORCED_CLOSURE_BROKEN_CN = '收口时该案停在判定图之外的损坏状态：按引擎侧未闭合显式结案；原始记录保留，同参续跑重入'
FORCED_CLOSURE_UNPROJECTABLE_CN = '该案已有终态主张但没有可核验的收口投影（例如未跑出结果的归因主张）：按引擎侧未闭合显式结案；主张与原始记录保留，同参续跑重入'
ATTRIBUTION_EVIDENCE_REACQUISITION_CN = '归因原证据没有可验证的密封件；引擎已尽量保留仍可识别的工作副本。若工作副本仍在，修复存储/权限后以同参数重试；若已缺失，请先用 ist-verify 对当前 Excel 重新上机取证，再续跑'
FORCED_CLOSURE_BLOCKED_CN = {'bed': '本批交付前净态核被测试设备侧阻塞，该案本轮未结，按阻塞记账；设备条件恢复后同参续跑重入', 'api': '本批在接口侧暂停，该案本轮未结，按阻塞记账；接口恢复后同参续跑重入'}
FORCED_CLOSURE_CONTRA_UNCLOSED_CN = '子集判决与整卷判决矛盾，本轮未消解：按引擎侧未闭合显式结案（整卷分族 / 逐案重跑待做）；原始判决保留，同参续跑重入'
FORCED_CLOSURE_CASE_SCOPE_CN = '本案按收口强制落地记账，本批其余用例不受影响，照常继续'
FORCED_CLOSURE_PROJECTION_BLOCKED_CN = '框架归因投影身份不可用（{reason}）：本案本轮不能归因，按引擎侧未闭合显式结案；重生成投影后同参续跑重入'
AUTHORITY_DECISION_BLOCKED_CN = '来源冲突尚未解决，本案按阻塞结案'
AUTHORITY_UNVERIFIED_BLOCKED_CN = '本案多处预期值的来源互相矛盾，收口时没能确定以哪一个为准，按阻塞结案'
ENGINE_OUTPUT_TRUNCATED_CN = '模型输出反复截断，本次编写未完成；引擎重新派发'
ENGINE_OUTPUT_REPEATING_CN = '模型输出持续重复，本次编写已停止；引擎重新派发'
ENGINE_NO_RESPONSE_ABANDON_CN = '超过 30 分钟没有响应，已放弃；引擎重新派发'
ENGINE_INTERNAL_FAULT_CN = '引擎内部故障，本次编写作废并重新派发'
ENGINE_TOOL_BUDGET_EXCEEDED_CN = '编写工具次数已用尽，本次编写已停止'
ENGINE_ROUNDS_EXHAUSTED_CN = '编写轮次用尽，未得出结果'
ENGINE_NO_PROGRESS_CN = '连续 3 次提交格式不合规，本次编写已停止；引擎重新派发'
ENGINE_INVALID_ENVELOPE_CN = '模型交回的结果不合规范，本次编写作废并重新派发'
ENGINE_LEDGER_FAULT_CN = '引擎内部记账故障，本次编写作废并重新派发'
ENGINE_ASSEMBLY_FAULT_CN = '引擎内部装配故障，本次编写作废并重新派发'
ENGINE_NO_TEXT_OUTPUT_CN = '跑完了但没有产出结果，引擎按无产出处理'
FORK_TERMINATION_CAUSE_CN: dict[str, str] = {'COMPLETED': '正常完成', 'TRANSIENT_ERROR': FORK_TRANSIENT_NO_API_CN, 'LLM_QUOTA_EXHAUSTED': 'API账户额度不足，本批已停止；充值或更换API接口后以同参数续跑', 'API_REQUEST_REJECTED': 'API接口拒绝了这次请求，本案未编写；更换模型或API接口后重跑', 'API_AUTH_REJECTED': 'API接口拒绝了这次请求的身份或权限，本批已停止；充值或更正密钥后重跑；若是用量窗口上限，等窗口重置后重试', 'GRAPH_RECURSION_LIMIT': ENGINE_ROUNDS_EXHAUSTED_CN, 'TOOL_BUDGET_EXCEEDED': ENGINE_TOOL_BUDGET_EXCEEDED_CN, 'FUTILITY_BLOCKED': ENGINE_NO_PROGRESS_CN, 'CANCELLED': '已中止，本轮产物不采用', 'EXCEPTION': ENGINE_INTERNAL_FAULT_CN, 'NO_TEXT_OUTPUT': ENGINE_NO_TEXT_OUTPUT_CN, 'INVALID_STRUCTURED_RESPONSE': ENGINE_INVALID_ENVELOPE_CN, 'INVALID_RETURN_HEADER': '模型交回的结果缺少必需的收尾信息，本次编写作废并重新派发', 'FORK_REPORTED_FAILED': '模型报告本次编写失败，引擎重新派发', 'ERROR_RETURN': '模型以错误收尾，引擎重新派发', 'REGISTRY_UNKNOWN': ENGINE_LEDGER_FAULT_CN, 'LEDGER_UNKNOWN': ENGINE_LEDGER_FAULT_CN, 'TASK_INCOMPLETE': ENGINE_LEDGER_FAULT_CN, 'SUBAGENT_BUILD_FAILED': ENGINE_ASSEMBLY_FAULT_CN, 'SUBAGENT_DEFINITION_NOT_FOUND': '引擎内部装配故障：找不到这项编写任务的定义', 'TUI_EXIT_WITH_ACTIVE_FORKS': '上次退出时这一案还在编写；重新下达同一条指令可续跑', 'SESSION_RESET_WITHOUT_TERMINAL_EVENT': '会话被重置，这一案没留下结果', 'PROCESS_EXIT_WITHOUT_TERMINAL_EVENT': '进程退出，这一案没留下结果', 'BACKGROUND_DISPATCH_EXCEPTION': '后台派发失败，这一案没有开始编写', 'BACKGROUND_THREAD_START_FAILED': '后台任务起不来，这一案没有开始编写', 'BACKGROUND_NOT_ADOPTED': '后台任务在被接管前就结束了', 'ABANDONED_BEFORE_DISPATCH': '派发前已中止'}

def fork_termination_cn(cause_code: object) -> str:
    return FORK_TERMINATION_CAUSE_CN.get(str(cause_code or '').strip(), '')
_FORK_API_IMPACT_CN: dict[str, str] = {'API_REQUEST_REJECTED': API_IMPACT_CASE_CN, 'LLM_QUOTA_EXHAUSTED': API_IMPACT_BATCH_CN, 'API_AUTH_REJECTED': API_IMPACT_BATCH_CN}

def fork_failure_cn(cause_code: object, api_error: Mapping[str, object] | None=None, *, limit: int=API_MESSAGE_CARD_MAX) -> str:
    code = str(cause_code or '').strip()
    if isinstance(api_error, Mapping) and api_error:
        impact = _FORK_API_IMPACT_CN.get(code, API_IMPACT_CASE_UNFINISHED_CN)
        sentence = api_error_verdict(api_error.get('code'), api_error.get('message'), impact=impact, scope=API_SCOPE_BATCH if impact == API_IMPACT_BATCH_CN else API_SCOPE_CASE, limit=limit)
        if sentence:
            return sentence
    return fork_termination_cn(code)
FORK_FAILURE_INFO_CN: dict[str, str] = {'transient': FORK_TRANSIENT_NO_API_CN, 'overflow': f'这一案的材料超出模型容量，{API_IMPACT_CASE_UNFINISHED_CN}；缩减材料后重跑', 'auth': f'API接口认证或权限失败，{API_IMPACT_CASE_UNFINISHED_CN}；{API_ERROR_GOTO_CN[401]}；或{API_ERROR_GOTO_CN[403]}', 'aborted': '已中止，本轮产物不采用', 'rejected': FORK_TERMINATION_CAUSE_CN['API_REQUEST_REJECTED']}
FORK_LEGACY_ERROR_CN: tuple[tuple[str, str], ...] = (('no text output', ENGINE_NO_TEXT_OUTPUT_CN), ('returned no text', ENGINE_NO_TEXT_OUTPUT_CN), ('no output from fork', '未产出结果，已安排重写'), ('recursion-limit', ENGINE_ROUNDS_EXHAUSTED_CN), ('recursionerror', ENGINE_ROUNDS_EXHAUSTED_CN), ('toolcalllimitexceeded', ENGINE_TOOL_BUDGET_EXCEEDED_CN), ('tool call limit', ENGINE_TOOL_BUDGET_EXCEEDED_CN), ('declared underdetermined', '报了欠定但没落账，引擎按内部故障分流'), ('execution failed', '执行失败，已安排重试'), ('no matching fork_end', FORK_TERMINATION_CAUSE_CN['TUI_EXIT_WITH_ACTIVE_FORKS']))
FORK_UNKNOWN_CAUSE_CN = '编写未成功·该记录未带终止码'
BATCH_COMMON_CAUSE_NOT_STARTED_CN = '个用例都没开始编写'
BATCH_COMMON_CAUSE_NO_SECOND_WAVE_CN = '引擎未对它们补派第二波'
BATCH_COMMON_CAUSE_REST_UNAFFECTED_CN = '本批其余用例照常'

def batch_api_error_line_cn(api_error: Mapping[str, object] | None, count: object, total: object=None) -> str:
    if not isinstance(api_error, Mapping) or not api_error:
        return ''
    head = api_error_sentence(api_error.get('code'), api_error.get('message'), limit=API_MESSAGE_CARD_MAX)
    if not head:
        return ''
    n = _slot_int(count) or 0
    t = _slot_int(total)
    if t is not None and t > 0:
        body = f'本波 {t} 个用例里 {n} 个同因未编写，{BATCH_COMMON_CAUSE_NO_SECOND_WAVE_CN}'
    else:
        body = f'{n} {BATCH_COMMON_CAUSE_NOT_STARTED_CN}'
    goto = api_error_goto_cn(api_error.get('code'), scope=API_SCOPE_WAVE)
    return _join_segments(head, body) + f'；{BATCH_COMMON_CAUSE_REST_UNAFFECTED_CN}，{goto}'
RECOMPOSE_SUBMITTED_LABEL_CN = '已提交'
RECOMPOSE_PRECHECK_LABEL_CN = '核对机械脑图'
RECOMPOSE_ACCEPTED_LABEL_CN = '验收'
RECOMPOSE_PHASE_REMAINING_CN: dict[str, str] = {RECOMPOSE_SUBMITTED_LABEL_CN: '待提交', RECOMPOSE_PRECHECK_LABEL_CN: '待核对', RECOMPOSE_ACCEPTED_LABEL_CN: '未通过'}
RECOMPOSE_CASE_UNIT_CN = '用例'
RECOMPOSE_ITEM_UNIT_CN = '项'
MACHINE_MINDMAP_SUBMITTED_CN = '机械脑图已提交'

def machine_mindmap_submitted_cn(count: object, total: object=None) -> str:
    n = _slot_int(count) or 0
    t = _slot_int(total)
    t = n if t is None else t
    return f'{MACHINE_MINDMAP_SUBMITTED_CN} {n}/{t}'
MACHINE_MINDMAP_PARTIALLY_SEALED_CN = '机械脑图重组部分完成'

def machine_mindmap_partially_sealed_cn(sealed: object, total: object, missing: object) -> str:
    """台账已有案、剩余片零进展时引擎密封已落盘案（PR 内部工单）：缺案隔离走作者原文兜底。"""
    n = _slot_int(sealed) or 0
    t = _slot_int(total)
    t = n if t is None else t
    m = _slot_int(missing) or 0
    return f'{MACHINE_MINDMAP_PARTIALLY_SEALED_CN} {n}/{t}，{m} 案隔离走作者原文兜底，引擎已密封已落盘案'
MACHINE_MINDMAP_ENDPOINT_STOP_LEAD_CN = 'API接口中止了本轮重组'
MACHINE_MINDMAP_SEALED_BY_ENGINE_CN = '引擎已密封已落盘案，缺案走作者原文兜底'
MACHINE_MINDMAP_ENDPOINT_STOP_CAUSE_CN: dict[str, str] = {'LLM_QUOTA_EXHAUSTED': '账户额度不足', 'API_REQUEST_REJECTED': '接口拒绝了请求', 'API_AUTH_REJECTED': '接口拒绝了身份或权限'}

def machine_mindmap_sealed_after_endpoint_stop_cn(cause_code: object, sealed: object, total: object) -> str:
    """端点侧中止本轮派发、但台账有案可救时的屏幕句。

    死因只以中文投影出现——`cause_code` 是机读枚举，不进用户面（07 章显示契约：
    屏幕句的用词来源只有本表）。取不到投影就整段省掉那个括号，不印裸枚举。
    """
    n = _slot_int(sealed) or 0
    t = _slot_int(total)
    t = n if t is None else t
    reason = MACHINE_MINDMAP_ENDPOINT_STOP_CAUSE_CN.get(str(cause_code or '').strip(), '')
    head = MACHINE_MINDMAP_ENDPOINT_STOP_LEAD_CN + (f'（{reason}）' if reason else '')
    return f'{head}——{n}/{t} 案已落盘，{MACHINE_MINDMAP_SEALED_BY_ENGINE_CN}'
DISCLOSURE_BLOCKED_CASES_SUFFIX_CN = '案未进入编写'

def disclosure_blocked_head_cn(cases: object) -> str:
    n = _slot_int(cases)
    if n is None or n <= 0:
        return DISCLOSURE_LOAD_LEAD_CN
    return f'{DISCLOSURE_LOAD_LEAD_CN}，{n} {DISCLOSURE_BLOCKED_CASES_SUFFIX_CN}'

def disclosure_blocked_line_cn(reason: str, diagnostic: Mapping[str, object] | None=None, cases: object=None) -> str:
    head = disclosure_load_reason_cn(reason, diagnostic)
    if not head:
        return ''
    n = _slot_int(cases)
    if n is None or n <= 0:
        return head
    return _join_segments(head, f'{n} {DISCLOSURE_BLOCKED_CASES_SUFFIX_CN}')
DELIVERY_INCOMPLETE_HEAD_CN = '交付不完整'
DELIVERY_COMPLETE_HEAD_CN = '交付完成'
DELIVERY_MISMATCH_HEAD_CN = '交付完成(对账失配)'
DELIVERY_MISMATCH_WHY_CN = '报告数字与引擎账目对账不一致,以机读报告为准'
DELIVERY_FILES_MADE_CN = '已生成'
DELIVERY_FILES_NOT_MADE_CN = '未生成'
DELIVERY_FILE_LABEL_CN: dict[str, str] = {'case.xlsx': 'case.xlsx', 'delivery_report.md': '交付报告', 'unsuccessful_cases.md': '未通过详报', 'engine_report.json': '机读报告', 'facts.jsonl': '事实流', 'defect_candidates.md': '处置候选单', 'defect_candidates.json': '处置候选单（机读）', 'engine_errors.md': '引擎错误报告', 'metrics.md': '用量与耗时'}
DELIVERY_MAIN_ARTIFACT = 'case.xlsx'

def delivery_file_label_cn(name: object) -> str:
    text = str(name or '').strip()
    return DELIVERY_FILE_LABEL_CN.get(text, text)

def delivery_files_line_cn(files, missing=()) -> str:
    made = [delivery_file_label_cn(x) for x in files or [] if str(x or '')]
    gone = [delivery_file_label_cn(x) for x in missing or [] if str(x or '')]
    if DELIVERY_MAIN_ARTIFACT not in [str(x) for x in files or []] and DELIVERY_MAIN_ARTIFACT not in gone:
        gone.insert(0, DELIVERY_MAIN_ARTIFACT)
    segs = []
    if made:
        segs.append(f"{DELIVERY_FILES_MADE_CN}：{'、'.join(made[:6])}")
    if gone:
        segs.append(f"{DELIVERY_FILES_NOT_MADE_CN} {'、'.join(gone[:4])}")
    return ' · '.join(segs)
DISCLOSURE_COUNT_LEAD_CN = '提醒'
DISCLOSURE_COUNT_SHOWN_CN = '显示最近'
DISCLOSURE_COUNT_EXPAND_CN = 'ctrl+o 展开'
DISCLOSURE_FULL_TEXT_IN_REPORT_CN = '全文见交付报告'

def recompose_decision_counts_cn(summary: Mapping[str, object]) -> str:
    human = _slot_int(summary.get('human_pending'))
    automatic = _slot_int(summary.get('automatic_pending'))
    pieces = []
    if human is not None and human > 0:
        pieces.append(f'待人工确认 {human}')
    if automatic is not None and automatic > 0:
        pieces.append(f'待自动处置 {automatic}')
    if human is None and automatic is None:
        legacy = _slot_int(summary.get('needs_decision'))
        if legacy is not None and legacy > 0:
            pieces.append(f'处置项 {legacy}（分类未记录）')
    return ' · '.join(pieces)

def recompose_disclosure_count_cn(total: object, received: object) -> str:
    n, k = (_slot_int(total), _slot_int(received))
    k = k if k is not None and k >= 0 else 0
    if n is None:
        return f'已收到 {k} 条提醒（总数未记录）' if k else ''
    if n == 0 and k == 0:
        return ''
    head = f'提醒 {n} 条'
    return head if n == k else f'{head} · 当前已收到 {k} 条'

def recompile_comparison_cn(comparison: Mapping[str, object]) -> str:
    status = comparison.get('status')
    if status == 'coverage_unverified':
        return '本次重编与上一版的数据区执行字段不同，两份程序的语义等价尚未核验。上一版原卷已留存，当前作者场景审核另见保真结果。'
    if status == 'same_formatted_steps':
        return '与上一版的数据区执行字段相同；本次比较未核验语义等价，当前作者场景审核另见保真结果。'
    if status == 'unavailable':
        return '本次新旧卷面比较未完成，测试覆盖是否保持尚未核验。'
    return ''

def direction_disclosure_lines_cn(disclosure: Mapping[str, object]) -> list[str]:
    if disclosure.get('status') in {'not_recorded', 'unavailable'}:
        return ['当前卷的方向集合披露未记录或无法核验；逐条断言的语义方向是否保持仍未核验。']
    rows = disclosure.get('items')
    if disclosure.get('status') != 'recorded' or not isinstance(rows, list):
        return []
    return [f"判词 {row['expectation_id']}：方向令牌集合由 {' / '.join(row['sealed_directions'])} 变为 {' / '.join(row['current_directions'])}。令牌集合不标识断言的比较对象、操作数或阶段；逐条断言的语义方向仍未核验。" for row in rows]

def disclosure_count_line_cn(total: object, shown: object) -> str:
    n = _slot_int(total)
    k = _slot_int(shown)
    if n is None or n <= 0:
        return ''
    if k is None or k <= 0 or k >= n:
        return f'{DISCLOSURE_COUNT_LEAD_CN} {n} 条'
    return f'{DISCLOSURE_COUNT_LEAD_CN} {n} 条 · {DISCLOSURE_COUNT_SHOWN_CN} {k} 条（{DISCLOSURE_COUNT_EXPAND_CN}）'
INTERRUPTED_CN = '已中止'
RUN_ERROR_STICKY_FALLBACK_CN = '本轮未完成'
ERROR_WITHOUT_TEXT_CN = '引擎报错，但没有给出可读的说明'

def api_error_sticky_cn(api_error: Mapping[str, object] | None) -> str:
    if not isinstance(api_error, Mapping) or not api_error:
        return ''
    head = api_error_sentence(api_error.get('code'), '')
    return f'{head}，{API_IMPACT_TURN_CN}' if head else ''
FORK_ELAPSED_BUDGET_CN = '本案时限'
FORK_DETAIL_RECONCILE_CN = '编写结果对账'
FORK_DETAIL_NO_STEPS_CN = '这一案的事件账里暂时没有可显示的步骤'
FORK_OVER_BUDGET_CN = '已过时限，等待引擎回收'
FORK_BUDGET_LEFT_CN = '距时限'
SESSION_ABANDON_LEAD_CN = '已放弃在途会话编写'
SESSION_ABANDON_TAIL_CN = '产物作废，正在等的模型请求已被掐断、这一路就地退出（掐不中的会在下一个回调边界停）；退出前仍可能在后台短暂运行'
NETWORK_OUTAGE_LEAD_CN = 'API接口连不上'
NETWORK_OUTAGE_RESUME_CN = '恢复后自动继续'
NETWORK_OUTAGE_MINUTE_FLOOR_S = 60.0
NETWORK_OUTAGE_JUST_NOW_CN = '刚刚断开'

def _outage_minutes(waited_s: object) -> int:
    try:
        return max(1, int(float(waited_s or 0) // 60))
    except (TypeError, ValueError):
        return 1

def _outage_elapsed_cn(waited_s: object) -> str:
    try:
        seconds = float(waited_s or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds < NETWORK_OUTAGE_MINUTE_FLOOR_S:
        return NETWORK_OUTAGE_JUST_NOW_CN
    return f'已等 {_outage_minutes(seconds)} 分钟'

def network_outage_card_cn(waited_s: object) -> str:
    return f'{NETWORK_OUTAGE_LEAD_CN} · {_outage_elapsed_cn(waited_s)} · {NETWORK_OUTAGE_RESUME_CN}'

def network_outage_disclosure_cn(waited_s: object) -> str:
    return f'本批曾因{NETWORK_OUTAGE_LEAD_CN}暂停 {_outage_minutes(waited_s)} 分钟，{NETWORK_OUTAGE_RESUME_CN}'

def api_zero_response_cn() -> str:
    head = api_error_sentence(API_ZERO_RESPONSE_CODE_CN, API_ZERO_RESPONSE_MESSAGE_CN)
    return f'{head}，{API_IMPACT_TURN_CN}；{API_GOTO_ZERO_RESPONSE_CN}'
USER_FACING_BANNED_WORDS: tuple[str, ...] = ('端点', 'provider', '网关', 'fork', 'worker', '孔', '整流', '台账', '墙钟', '看门狗', '状态机', '本仓', '旋钮', 'exception_type')
_QUERY_ACTION_BY_KIND: dict[str, str] = {'signature': '查方法参数', 'usage': '查历史写法', 'host': '查该机历史命令', 'prompt_pattern': '查二次确认', 'nearest': '核对方法名', 'param': '查命令参数', 'complete': '核对命令收录', 'heads': '列命令清单', 'docs': '查资料目录'}

def ide_action(tool: str, args: Mapping[str, object] | None=None) -> str:
    family = IDE_TOOL_FAMILY.get(tool)
    if family == 'lint':
        return LINT_ACTION
    if family == 'replay':
        return REPLAY_ACTION
    if family != 'query':
        return ''
    data = args if isinstance(args, Mapping) else {}
    kind = str(data.get('kind') or '')
    name = str(data.get('name') or '').strip()
    domain = str(data.get('domain') or '').strip()
    if kind == 'contract':
        if not domain:
            return '查可用执行对象'
        return '查方法用法' if name else '查可用方法'
    if kind == 'dispatch':
        return '列同类方法' if domain and (not name) else '查方法归类'
    return _QUERY_ACTION_BY_KIND.get(kind, '')
COUNT_UNIT_SINGLE = 'single'
COUNT_UNIT_METHOD = 'method'
COUNT_UNIT_USAGE = 'usage'
COUNT_UNIT_NEAREST = 'nearest'
COUNT_UNIT_HEAD = 'head'
COUNT_UNIT_OBJECT = 'object'
COUNT_UNIT_DOC = 'doc'

def count_phrase(unit: str, count: int | None, *, truncated: bool=False) -> str:
    if count is None:
        return ''
    if unit == COUNT_UNIT_NEAREST:
        if count == 0:
            return '无近似名'
        return '唯一命中' if count == 1 else f'近似名 {count} 个'
    if unit == COUNT_UNIT_USAGE:
        return f'历史写法 {count} 处' if count else '无历史写法'
    if unit == COUNT_UNIT_METHOD:
        return f'收录 {count} 个方法'
    if unit == COUNT_UNIT_HEAD:
        if count == 0:
            return '命令树无此前缀'
        return f'命令头 {count} 个' + ('（列表已截断）' if truncated else '')
    if unit == COUNT_UNIT_OBJECT:
        return f'收录 {count} 个执行对象'
    if unit == COUNT_UNIT_DOC:
        return f'资料 {count} 条' if count else '无匹配资料'
    return '已收录' if count else '未收录'
QUERY_ERROR_CN: dict[str, str] = {'UNKNOWN_DOMAIN': '查询对象无效（应填 ssl_comm / seg_comm / ha_comm / preparation）', 'QUERY_UNAVAILABLE': '资料源不可用', 'INVALID_QUERY': '查询条件不合法', 'QUERY_FAILED': '查询失败'}
RULE_CODE_CN: dict[str, str] = {'found_times_invalid_shape': '命中次数写法非法', 'excel_contract_unavailable': '用例契约不可用', 'disabled_dispatch_method': '该方法本运行时未启用', 'invalid_function_arguments': '参数与方法签名不符', 'dangling_assertion': '断言无观测步可依', 'manual_ip_cleanup': '手工增删 IP 与框架还原冲突', 'empty_command_payload': '命令内容为空', 'cmd_config_multiline': '单命令位写了多行', 'literal_backslash_n': '换行被写成字面 \\n', 'unknown_dispatch_target': '执行对象不在设备表', 'unknown_dispatch_method': '该对象没有这个方法', 'execute_action_not_in_registry': '动作名不在注册表', 'execute_payload_required': '该动作缺必填内容', 'line_anchor_never_matches': '行锚点永不命中', 'assertion_matches_command_echo': '断言匹配到命令回显', 'no_assertion_in_case': '全案无检查点', 'empty_assertion_pattern': '检查点无比对内容', 'mutation_control_after_config': '对照锚落在配置之后', 'undefined_capture_ref': '引用了未捕获的寄存器', 'injection_format_crash': '占位符形态非法', 'injection_without_placeholder': '注入值无占位符接收', 'injection_placeholder_scope': '占位符不在首个位置参', 'register_shadows_framework_name': '寄存器名与运行时对象撞名', 'destructive_command': '触碰自毁命令闭集', 'command_not_in_tree': '命令树未收录该命令', 'command_parameter_contract': '参数与命令树签名不符', 'driver_no_declared_path': '执行机到目标无声明路径', 'executor_networks_undeclared': '执行机未声明所在网段', 'cmd_not_in_allowlist': '命令模块未见于已验证足迹', 'dead_capture': '捕获后无人读取', 'assertion_regex_invalid': '断言正则编译不过', 'short_mode_status_assertion': '简报窗口无状态行可断言', 'comma_splits_parameters': '逗号被当成参数分隔符', 'autoid_malformed': 'autoid 不是 18 位数字', 'autoid_row_not_runnable': 'autoid 行缺执行对象', 'xlsx_unreadable': '工作簿打不开或身份不符', 'not_an_object': '用例正文不是 JSON 对象', 'body_keys_mismatch': '正文字段不符合信封', 'blocks_invalid': '结构块非法', 'segment_invalid': '结构块为空或形态非法', 'document_inconsistent': '用例文档自相矛盾', 'seal_uncastable': '密封铸不出来', 'seal_self_reported': '密封由提交方自签', 'contract_unreadable': '契约卡读不出来', 'contract_identity_drift': '契约身份与冻结卡不符', 'contract_autoid_mismatch': '契约卡属于另一个用例', 'contract_identity_duplicated': '期望项标识重复', 'contract_identity_incomplete': '期望项没有标识', 'capability_build_unbound': '能力 build 未绑定', 'consistency_contract_absent': '一致性契约缺失', 'consistency_contract_base_drift': '一致性叠加层不绑本案', 'consistency_contract_identity_drift': '一致性契约身份不符', 'consistency_endorsement_claim_kind_upgrade': '联署擅自改写声明类型', 'consistency_not_applicable_binding_present': '引擎判不适用却自签叠加层', 'criterion_binding_missing': '判据没有断言承接', 'criterion_claim_identity_invalid': '判据标识为空或重复', 'criterion_lowering_mismatch': '判据下沉走了不许的路径', 'criterion_status_claim_literalized': '状态判据被写成字面量', 'criterion_status_target_unbound': '状态判据的目标未绑定', 'criterion_state_change_step_invalid': '声明的状态变更步骤不成立', 'criterion_state_change_step_self_satisfying': '断言被声明步骤自己满足', 'criterion_type_unresolved': '判据类型未确定', 'expectation_bijection_failed': '期望与断言未一一对应', 'fixture_expected_not_config_backref': '夹具期望值未回指配置', 'spec_endorsement_expectation_not_bound': '规格联署未绑定唯一期望', 'semantic_key_group_rank_deficient': '同键断言重复做同一件事', 'provenance_source_unresolved': '出处来源无法解析', 'provenance_step_count_mismatch': '出处条数与步数不符', 'group_path_mismatch': '分组路径未逐字照抄', 'intent_verbatim_mismatch': '意图原文未逐字照抄', 'authored_command_occurrence_missing': '作者procedure的命令未落到步骤', 'environment_unreachable_ip': '目标 IP 不可达', 'trigger_reachability_invalid': '触发点到目标不可达', 'negative_probe_target_not_ip_literal': '否定式探针目标不是 IP 字面', 'negative_probe_path_undeclared': '执行体到否定式探针目标无声明路径', 'scenario_changed': '实现场景与作者步骤不一致', 'author_step_unrealized': '作者步骤未被实现', 'author_step_unbound': '作者步骤未绑定实现块', 'answerer_ref_unresolved': '应答配置块指向无效', 'answerer_statement_missing': '观测在被测设备之外且无应答声明', 'answerer_undetermined_unrouted': '应答未定却直接密封', 'missing_teardown': '建的配置没有配对清场', 'paired_teardown_uncomputable': '清场覆盖算不出结论', 'tau_atlas_unavailable': '清场图谱不可用', 'https_lifecycle_contract_unavailable': 'SSL 生命周期契约不可用', 'https_certificate_setup_missing': 'HTTPS 服务缺证书装载', 'https_certificate_setup_incomplete': '证书装载三步不齐', 'https_certificate_start_missing': '证书已激活但 SSL 主机未启动', 'https_certificate_teardown_missing': '证书主机缺配对清场', 'https_certificate_redundant_activation': '重复激活证书', 'https_certificate_material_unverified': '证书材料未经同源核验', 'https_certificate_activation_contract_unavailable': '证书激活契约不可用', 'escape_hatch_out_of_range': '逃逸口指向的块不存在', 'escape_hatch_duplicated': '逃逸口重复登记同一块', 'escape_hatch_set_mismatch': '逃逸口与通用步不对应', 'submission_repair_blocks_changed': '续交时结构块被改动', 'submission_repair_blocks_change_not_authorized': '该拒绝码不许改结构块', 'submission_repair_envelope_rebind_required': '续交需重交完整信封', 'blocks_expansion': '结构块未能展开', 'provenance_parse': '出处信息解析失败', 'provenance_step_count': '出处条数与步数不符', 'derived_assertion_expansion': '派生断言展开失败', 'command_tree_unavailable': '命令树投影不可用', 'compile_lint_error': '规则校验自身报错'}
UNNAMED_RULE_CN = '未命名规则'
NOT_COMPILABLE_REJECTION_CN: dict[str, str] = {'environment_gap_unverified': '引擎在本次会话里没有复核到「测试环境不具备条件」的凭据：作者原文写的部署值在当前拓扑上并非不可达，本次也没有哪一次用例提交被共享设备的操作禁令拒绝过', 'author_gap_expectation_already_signed': '该条通过标准已由作者原文签署并完成判据归类，不属于「无人定义」；要否掉它需要命令清单层面的机械否决，本次会话没有产生', 'no_cli_signed_expectation_unverified': '该条通过标准已由作者原文签署，而本次会话没有拿到「产品命令清单里没有这条命令」的机械否决', 'author_conflict_surfaces_insufficient': '说的是「用例自己两处说法打架」，但这份报告只引到人工脑图的一处原文：互斥要两侧都摆出来（标题/分组与过程步骤、或过程步骤与预期），只引一处说明缺的是定义、不是矛盾', 'author_conflict_expectation_unsigned': '说的是「用例自己两处说法打架挡住了已签的通过标准」，但这份报告引的原文没有一条对上本案已签的作者主张，没有被挡住的通过标准，这条出口不成立'}

def not_compilable_rejection_cn(code: str) -> str:
    key = str(code or '').strip()
    return NOT_COMPILABLE_REJECTION_CN.get(key, key)

def rule_code_cn(code: str) -> str:
    key = str(code or '').strip()
    if not key:
        return ''
    return RULE_CODE_CN.get(key, UNNAMED_RULE_CN)

def tool_short_name(raw: str) -> str:
    return TOOL_SHORT_NAMES.get(raw, raw)

def middle_ellipsis(s: str, maxw: int) -> str:
    s = str(s or '')
    if len(s) <= maxw:
        return s
    if '/' in s:
        parts = [p for p in s.replace('\\', '/').split('/') if p]
        if len(parts) > 3:
            cand = parts[0] + '/…/' + '/'.join(parts[-2:])
            if len(cand) <= maxw:
                return cand
    head = max(1, (maxw - 1) // 3)
    tail = max(1, maxw - 1 - head)
    return s[:head] + '…' + s[-tail:]

def path_stem(path: str) -> str:
    if not path:
        return ''
    base = str(path).replace('\\', '/').rsplit('/', 1)[-1]
    return base.rsplit('.', 1)[0] if '.' in base else base

def extract_from_raw(args: Mapping[str, object] | None, key: str) -> str:
    import re
    raw = (args or {}).get('raw') or ''
    if not isinstance(raw, str):
        return ''
    m = re.search(f"""['"]?{re.escape(key)}['"]?\\s*[:=]\\s*['"]([^'"]+)['"]""", raw)
    return m.group(1) if m else ''

def _autoid_in(text: str) -> str:
    import re
    m = re.search('(?<!\\d)\\d{18}(?!\\d)', str(text or ''))
    return m.group(0) if m else ''

def _clip(text: str, maxw: int=_SUMMARY_MAX) -> str:
    text = str(text or '')
    return text[:maxw] + '…' if len(text) > maxw else text

def _apply_style(style: str, value: object, *, blob: str='') -> str:
    if isinstance(value, (list, tuple, set, dict)):
        return ''
    text = '' if value is None else str(value).strip()
    if style == 'autoid':
        aid = text if text.isdigit() else _autoid_in(text) or _autoid_in(blob)
        return f'…{aid[-6:]}' if aid else ''
    if not text:
        return ''
    if style == 'path_tail':
        parts = text.replace('\\', '/').split('/')
        return '/'.join(parts[-2:]) if len(parts) > 2 else text
    if style == 'stem':
        return _clip(path_stem(text), 40)
    if style == 'first_line':
        line = next((ln for ln in text.splitlines() if ln.strip()), '')
        return _clip(line.strip())
    if style == 'command':
        return middle_ellipsis(text.replace('\n', ' '), _SUMMARY_MAX)
    if style == 'skill':
        aid = _autoid_in(blob)
        skill = _clip(text, 40)
        return f'{skill} · …{aid[-6:]}' if aid else skill
    return _clip(text)

def structured_args(args: Mapping[str, object] | None) -> Mapping[str, object]:
    if not args:
        return {}
    envelope = args.get('args') if 'raw' in args else None
    if isinstance(envelope, Mapping):
        return envelope
    return {k: v for k, v in args.items() if k != 'raw'}

def tool_arg_value(args: Mapping[str, object] | None, key: str) -> str:
    value = structured_args(args).get(key)
    if isinstance(value, str) and value:
        return value
    if value not in (None, '', (), [], {}) and (not isinstance(value, (list, tuple, set, dict))):
        return str(value)
    return extract_from_raw(args, key)
_ERROR_LEAD_TEXTS = ('error:', '错误')
_ERROR_LEAD_GLYPHS = ('✗', '❌', '✖')
_INBOUND_STATUS_GLYPHS = '✓✗❌✖●'
_INBOUND_STATUS_GLYPH_RE = __import__('re').compile('^[' + _INBOUND_STATUS_GLYPHS + ']\\s*')

def strip_leading_status_glyph(text: str) -> str:
    return _INBOUND_STATUS_GLYPH_RE.sub('', str(text or ''))

def tool_result_is_error(output: object, status: object='') -> bool:
    if str(status or '').strip().lower() == 'error':
        return True
    lead = str(output or '').lstrip()
    if not lead:
        return False
    return lead.lower().startswith(_ERROR_LEAD_TEXTS) or lead.startswith(_ERROR_LEAD_GLYPHS)

def tool_result_recoverable(payload: Mapping[str, object] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return payload.get('recoverable') is True

def tool_arg_summary(name: str, args: Mapping[str, object] | None) -> str:
    if not args:
        return ''
    structured = structured_args(args)
    blob = ''.join((str(structured.get(key) or '') for key in ('brief', 'payload', 'raw'))) + str(args.get('raw') or '')
    for key, style in TOOL_ARG_SUMMARY.get(str(name or ''), ()):
        value = structured.get(key)
        if value in (None, '', (), [], {}):
            value = extract_from_raw(args, key)
        got = _apply_style(style, value, blob=blob)
        if got:
            return got
    for value in structured.values():
        got = _apply_style('text', value)
        if got:
            return got
    return ''
