# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/blocking_taxonomy.py（sha256 956e9a537ab1cd5d）。不在这里手改。
from __future__ import annotations
import re
from typing import Any
from cex_core.engine.case_compiler.provenance_ir import product_expected_source_is_valid
from cex_core.engine.ist_core import display_lexicon as _L
from cex_core.engine.ist_core.compile_engine.views import SCENARIO2_REASON_CODE, active_execution_terminal, scenario2_abandon_active
from cex_core.engine.ist_core.compile_engine.terminal_credentials import _decision_resolves_question, _fact_sha256, _object_sha256, _structured_claims
SCHEMA_CARD = 'ist.compile.blocking_card'
B_SPEC_CASE = 'spec_case_conflict'
B_XML_CONFLICT = 'xml_conflict_pending'
B_MANUAL_ERROR = 'manual_error'
B_DEVICE_MANUAL = 'device_and_manual_error'
B_DEVICE_DEFECT = 'device_defect'
B_ENV_UNMET = 'environment_unmet'
B_EXECUTION_INFRA = 'execution_infrastructure_blocked'
B_EXCEL_FN = 'excel_function_gap'
B_AUTHORITY_CONFLICT = 'authority_conflict'
B_AUTHORING_UNATTRIBUTED = 'authoring_stop_unattributed'
B_CONTRA_UNATTRIBUTED = 'verdict_contradiction_unresolved'
B_AUTHORITY_UNVERIFIED = 'authority_chain_unverified'
B_UNRECOGNIZED_ROUTING = 'unrecognized_routing_value'
B_ARTIFACT_UNVERIFIABLE = 'case_artifact_identity_unverifiable'
BLOCKING_CLASSES = (B_SPEC_CASE, B_XML_CONFLICT, B_MANUAL_ERROR, B_DEVICE_MANUAL, B_DEVICE_DEFECT, B_ENV_UNMET, B_EXECUTION_INFRA, B_EXCEL_FN, B_AUTHORITY_CONFLICT, B_AUTHORING_UNATTRIBUTED, B_CONTRA_UNATTRIBUTED, B_AUTHORITY_UNVERIFIED, B_UNRECOGNIZED_ROUTING, B_ARTIFACT_UNVERIFIABLE)
B_UNCLASSIFIED = 'unclassified_blocking'
NOT_OBJECTIVE = 'not_objective_blocking'
A_SPEC_CASE_CONFLICT = 'abandoned_spec_case_conflict'
A_SPEC_PRESENT_CASE_INCOMPLETE = 'abandoned_spec_present_case_incomplete'
A_INCOMPLETE_CASE = 'abandoned_incomplete_case'
A_ROUND_CAP = 'abandoned_round_cap'
A_NO_CLI_EQUIVALENT = 'abandoned_no_cli_equivalent'
A_ENV_PREREQ_GAP = 'abandoned_environment_prerequisite_gap'
A_AUTHOR_DEFINITION_GAP = 'abandoned_author_definition_gap'
A_BATCH_USER_ABANDON = 'abandoned_batch_user_abandon'
ABANDON_CLASSES = (A_SPEC_CASE_CONFLICT, A_SPEC_PRESENT_CASE_INCOMPLETE, A_INCOMPLETE_CASE, A_ROUND_CAP, A_NO_CLI_EQUIVALENT, A_ENV_PREREQ_GAP, A_AUTHOR_DEFINITION_GAP, A_BATCH_USER_ABANDON)
ABANDON_CN = {A_SPEC_CASE_CONFLICT: '放弃：规格书与人工脑图不一致', A_SPEC_PRESENT_CASE_INCOMPLETE: '放弃：规格书有表态、人工脑图缺项', A_INCOMPLETE_CASE: '放弃：人工脑图不完整', A_ROUND_CAP: '放弃：编译轮次已用尽', A_NO_CLI_EQUIVALENT: '放弃：自动化平台没有等价的 CLI 观测方式', A_ENV_PREREQ_GAP: '放弃：测试环境不具备编写条件', A_AUTHOR_DEFINITION_GAP: '放弃：通过标准欠定，需作者补充定义', A_BATCH_USER_ABANDON: '放弃：用户选择整批放弃'}
ABANDON_REASON_ZH = {A_SPEC_CASE_CONFLICT: '规格书和人工脑图对同一条判据各说各的，两侧都完整但对不上。这次不编机械用例、不入库。', A_SPEC_PRESENT_CASE_INCOMPLETE: '规格书对这条人工脑图有明确说法，但人工脑图缺描述、步骤或预期，还编不出来。缺的是人工脑图本身，编译期补不上。这次不编机械用例、不入库。', A_INCOMPLETE_CASE: '人工脑图和规格书都没给出能编的判据，缺口是真的。缺的是输入本身。这次不编机械用例、不入库。', A_ROUND_CAP: '来源冲突挡住过，改完再编，轮次用尽。这次不编机械用例、不入库。', A_NO_CLI_EQUIVALENT: '这条人工脑图要用后台或非 CLI 的观察方式，自动化这边找不到同等的 CLI 写法，编不成机械用例。这次不编机械用例、不入库。', A_ENV_PREREQ_GAP: '你的人工脑图没问题。是测试环境缺编写前提：作者指定的部署值不在这台设备的任何可达子网，或这步被共享设备运行纪律禁了。环境不变，再跑还是这样。这次不编机械用例、不入库。', A_AUTHOR_DEFINITION_GAP: '通过标准欠定：读得懂要验什么，但从人工脑图、规格书和其它带身份来源推不出能判定的预期。缺的定义只有作者或规格书能补，引擎不猜，也不拿设备观测当预期。输入不变，再跑还是这样。这次不编机械用例、不入库。', A_BATCH_USER_ABANDON: '情景③④的来源冲突已经在同一面板问过，你选了放弃。整批这次都不编机械用例、不入库，输入不变就不再问。'}
ABANDON_USER_ACTION_ZH = {A_SPEC_CASE_CONFLICT: '这次不编机械用例。修正人工脑图或规格书使两侧一致后，请用新的批名重新编译。', A_SPEC_PRESENT_CASE_INCOMPLETE: '这次不编机械用例。补齐人工脑图缺少的描述、步骤或预期后，请用新的批名重新编译。', A_INCOMPLETE_CASE: '这次不编机械用例。在人工脑图或规格书里补上可编译的判据后，请用新的批名重新编译。', A_NO_CLI_EQUIVALENT: '这次不编机械用例：这条人工脑图要求的后台或非 CLI 观测方式在自动化平台上没有等价的 CLI 实现。把人工脑图改写成可用 CLI 观测的形式后，请用新的批名重新编译。', A_ENV_PREREQ_GAP: '这次不编机械用例：测试环境不具备编写条件。请先处理本案记录的环境限制，或使用具备条件的测试设备，再用新的批名重新编译。', A_AUTHOR_DEFINITION_GAP: '这次不编机械用例：通过标准欠定。人工脑图与规格书都没有把预期定义到可编译的程度。请按报告里编写侧逐字列出的缺口，在人工脑图或管辖规格书里补充对应定义（如部署映射、监听地址/端口、查询前提，或把「正常响应」这类判词写成可判定的输出标准），再用新的批名重新编译。', A_BATCH_USER_ABANDON: '整批已按你的选择放弃，本轮绑定输入不变时不会重问。若要重新编译，请先修改人工脑图、能力 XML 或管辖规格书，再用新的批名发起。'}
AUTHOR_GAP_VARIANT = 'gap'
AUTHOR_CONFLICT_VARIANT = 'conflict'

def is_abandon_class(token: str) -> bool:
    return str(token or '') in ABANDON_CLASSES
LEGACY_CLASS_MAP = {'topology_change': B_ENV_UNMET, 'device_investment': B_ENV_UNMET, 'product_defect_blocking': B_DEVICE_DEFECT, 'manual_issue': B_MANUAL_ERROR, 'mindmap_issue': B_SPEC_CASE, 'excel_function_gap': B_EXCEL_FN}

def canonical_class(token: str) -> str:
    t = str(token or '')
    if t in BLOCKING_CLASSES or t in ABANDON_CLASSES or t in (B_UNCLASSIFIED, NOT_OBJECTIVE):
        return t
    return LEGACY_CLASS_MAP.get(t, B_UNCLASSIFIED)
BLOCKING_CN = {B_CONTRA_UNATTRIBUTED: '判决矛盾未消解（责任未核）', B_AUTHORITY_UNVERIFIED: '期望值来源链未记清（待裁决）', B_UNRECOGNIZED_ROUTING: '路由值未登记（待裁决）', B_ARTIFACT_UNVERIFIABLE: '个案产物身份不可核（待裁决）', B_AUTHORITY_CONFLICT: '来源声明冲突', B_SPEC_CASE: '脑图问题(与规格书冲突或判据待厘清)', B_XML_CONFLICT: '能力注册表与来源声明冲突(待仲裁)', B_MANUAL_ERROR: '人工脑图与手册声明冲突(待仲裁)', B_DEVICE_MANUAL: '手册声明、人工脑图与设备行为多源冲突', B_DEVICE_DEFECT: '声明与设备行为冲突(待仲裁)', B_ENV_UNMET: '环境不满足(需开通道，非人工脑图问题)', B_EXECUTION_INFRA: '执行基础设施阻塞(下发/结果回收未闭合)', B_EXCEL_FN: '引擎能力不足(自动化函数表达不了)', B_AUTHORING_UNATTRIBUTED: '编写未以引擎可核的结果结束(责任未核)', B_UNCLASSIFIED: '引擎缺陷(未落入冲突处置闭集)', **ABANDON_CN}
OVERRIDE_TOKEN_PREFIX = 'override:'
OVERRIDE_DECISION_SCHEMA = 'ist.delta.blocking-override'

def _override_class_from_token(token: str) -> str:
    text = str(token or '')
    if not text.startswith(OVERRIDE_TOKEN_PREFIX):
        return ''
    raw = text[len(OVERRIDE_TOKEN_PREFIX):]
    if raw in (*BLOCKING_CLASSES, *ABANDON_CLASSES):
        return raw
    return LEGACY_CLASS_MAP.get(raw, '')

def _override_token_sha256(blocking_class: str) -> str:
    return _object_sha256({'schema': OVERRIDE_DECISION_SCHEMA, 'override_class': blocking_class, 'token': f'{OVERRIDE_TOKEN_PREFIX}{blocking_class}'})

def project_override_decision(token: str) -> dict[str, str]:
    blocking_class = _override_class_from_token(token)
    if not blocking_class:
        return {}
    return {'override_schema': OVERRIDE_DECISION_SCHEMA, 'override_class': blocking_class, 'override_token_sha256': _override_token_sha256(blocking_class)}

def _override_class_from_decision(fact: dict) -> tuple[str, str]:
    token = str(fact.get('token') or '')
    legacy_class = _override_class_from_token(token)
    if legacy_class:
        return (legacy_class, 'token')
    blocking_class = str(fact.get('override_class') or '')
    if token != '****' or fact.get('override_schema') != OVERRIDE_DECISION_SCHEMA or blocking_class not in (*BLOCKING_CLASSES, *ABANDON_CLASSES) or (fact.get('override_token_sha256') != _override_token_sha256(blocking_class)):
        return ('', '')
    return (blocking_class, 'override_class')
FACTOR_ZH = {B_AUTHORITY_UNVERIFIED: '交付卷身份一致、设备已通过；该案部分断言的期望值来源链未记清。不可证不等于引擎可证，本案转入待裁决，不随卷交付。', B_UNRECOGNIZED_ROUTING: '引擎遇到登记表里没有的路由值，不能折叠成默认出口，本案转入待裁决。', B_ARTIFACT_UNVERIFIABLE: '交卷审计核不到个案产物身份，本案转入待裁决，不随卷交付。', B_AUTHORITY_CONFLICT: '当前产物与交付身份已核验，来源声明仍有未解决的冲突；具体依据见权威对齐记录。', B_SPEC_CASE: '人工脑图与管辖规格书冲突,或验证判据在两侧都缺席,需要作者厘清', B_XML_CONFLICT: '规格书或人工脑图声明与版本化能力注册表不一致,当前不选胜', B_MANUAL_ERROR: '手册声明与规格书或人工脑图声明不一致,当前不选胜', B_DEVICE_MANUAL: '手册声明、人工脑图与设备行为形成多方冲突,需要绑定身份后仲裁', B_DEVICE_DEFECT: '文档/人工脑图声明与同一 artifact 的设备行为不一致,仅形成待仲裁候选', B_ENV_UNMET: '你的人工脑图没问题。是当前自动化环境缺它需要的通道/拓扑/网段/统计面，要先把环境开出来才能跑，改人工脑图没有用', B_EXECUTION_INFRA: '本轮下发或结果回收通道未闭合；卷面没有因此被判为 IST-Core 产物缺陷。只阻塞受影响用例，批内兄弟用例继续', B_EXCEL_FN: '你的人工脑图没问题。是引擎现有的自动化函数表达不了这个验证方式，属引擎能力缺口，已进工程处置候选单', B_AUTHORING_UNATTRIBUTED: '你的人工脑图没问题。这一案的编写没有以引擎可核的结果结束，账上的记录不足以判定是模型、引擎还是环境的问题，所以不给任何一方定责。原始记录与出处链已保留，同参续跑可以重入这一案', B_CONTRA_UNATTRIBUTED: _L.CONTRADICTION_PAUSE_UNCLOSED_CN, B_UNCLASSIFIED: '这一条卡住不是你的人工脑图的问题。它没有落进任何一类来源冲突(规格书×人工脑图、人工脑图×命令树、文档×设备行为、上机结果×预期),说明卡点在引擎自己。已进工程处置候选单,你的人工脑图不受影响', A_SPEC_CASE_CONFLICT: ABANDON_REASON_ZH[A_SPEC_CASE_CONFLICT], A_SPEC_PRESENT_CASE_INCOMPLETE: ABANDON_REASON_ZH[A_SPEC_PRESENT_CASE_INCOMPLETE], A_INCOMPLETE_CASE: ABANDON_REASON_ZH[A_INCOMPLETE_CASE], A_ROUND_CAP: ABANDON_REASON_ZH[A_ROUND_CAP], A_NO_CLI_EQUIVALENT: ABANDON_REASON_ZH[A_NO_CLI_EQUIVALENT], A_ENV_PREREQ_GAP: ABANDON_REASON_ZH[A_ENV_PREREQ_GAP], A_AUTHOR_DEFINITION_GAP: ABANDON_REASON_ZH[A_AUTHOR_DEFINITION_GAP], A_BATCH_USER_ABANDON: ABANDON_REASON_ZH[A_BATCH_USER_ABANDON]}
OPTIONS_ZH = {B_CONTRA_UNATTRIBUTED: (), B_AUTHORITY_UNVERIFIED: ('核对期望值来源链后按身份重入',), B_UNRECOGNIZED_ROUTING: ('把未登记的路由值交给引擎维护者处理后按身份重入',), B_ARTIFACT_UNVERIFIABLE: ('核对个案产物身份后按身份重入',), B_AUTHORITY_CONFLICT: ('修正冲突来源后重新发起编写',), B_SPEC_CASE: ('改描述', '改过程', '改预期', '挂起'), B_XML_CONFLICT: ('以设备命令树为准,换等价命令重编', '保留人工脑图命令,冲突案不编机械用例', '放弃本次生成'), B_EXECUTION_INFRA: ('恢复下发/结果回收基础设施后重新发起本案',), B_AUTHORING_UNATTRIBUTED: _L.UNATTRIBUTED_AUTHORING_STOP_USER_OPTIONS_CN, A_SPEC_CASE_CONFLICT: ('放弃本次生成',), A_SPEC_PRESENT_CASE_INCOMPLETE: ('放弃本次生成',), A_INCOMPLETE_CASE: ('放弃本次生成',), A_ROUND_CAP: ('放弃本次生成',), A_NO_CLI_EQUIVALENT: ('放弃本次生成',), A_ENV_PREREQ_GAP: ('放弃本次生成',), A_AUTHOR_DEFINITION_GAP: ('放弃本次生成',), A_BATCH_USER_ABANDON: ('放弃整批',)}
_VARIANT_TEXTS: dict[str, dict[str, str]] = {AUTHOR_GAP_VARIANT: {'declaration_label': '作者需补充定义的具体缺口（编写侧原文）', 'reason_lead': '通过标准欠定：'}, AUTHOR_CONFLICT_VARIANT: {'class_cn': '放弃：人工脑图两处说法互斥，需作者定这条验哪一个', 'reason': '人工脑图自己两处说法对不上：标题或所在分组说这条要验的行为，与某个步骤实际配置的行为不是同一个，而预期只在其中一种下成立。定义不缺，是打架——没有哪一条预期能同时兑现，上机也只能否掉其中一边，引擎不替你选。输入不变，再跑还是这样。这次不编机械用例、不入库。', 'user_action': '这次不编机械用例：人工脑图两处说法互斥。请按报告里编写侧逐字列出的分歧，定这条用例要考察哪一边，把另一处改成与它一致（改标题/分组，或改那个步骤），再用新的批名重新编译。', 'declaration_label': '作者需决定的具体分歧（编写侧原文）', 'reason_lead': '人工脑图两处说法互斥：'}}
_VARIANT_TEXTS[AUTHOR_CONFLICT_VARIANT]['factor'] = _VARIANT_TEXTS[AUTHOR_CONFLICT_VARIANT]['reason']
_CLASS_TEXTS: dict[str, tuple[dict[str, str], str]] = {'class_cn': (BLOCKING_CN, '待归类(信号不足)'), 'reason': (ABANDON_REASON_ZH, ''), 'user_action': (ABANDON_USER_ACTION_ZH, ''), 'factor': (FACTOR_ZH, FACTOR_ZH[B_UNCLASSIFIED])}

def variant_text(field: str, *, cls: str=A_AUTHOR_DEFINITION_GAP, variant: str='') -> str:
    """按格与第八格变体取一句用户面文案（本模块唯一取词入口）。

    `field` ∈ class_cn / reason / user_action / factor / declaration_label /
    reason_lead。只有第八格有变体；别的格恒走 per-class 表，`variant` 被忽略。
    空变体与未登记值都按 `gap` 读（缺定义那一套是默认）。
    declaration_label / reason_lead 只属第八格，拿别的 `cls` 调是调用点写错，
    当场 KeyError。
    """
    if str(cls or '') == A_AUTHOR_DEFINITION_GAP:
        key = str(variant or '') if str(variant or '') in _VARIANT_TEXTS else AUTHOR_GAP_VARIANT
        text = _VARIANT_TEXTS[key].get(field)
        if text is not None:
            return text
    table, fallback = _CLASS_TEXTS[field]
    return table.get(str(cls or ''), fallback)
MINDMAP_CLAIM_KINDS = frozenset({'absolute_position', 'rotation_order', 'new_member_last', 'new_member_participates', 'weight_ratio', 'distribution', 'relation_same', 'relation_diff', 'cross_client_landing', 'missing_teardown', 'sequence_periodicity'})
DEVICE_CLAIM_KINDS = frozenset({'forbidden_mechanism'})
MANUAL_CLAIM_KINDS = frozenset({'command_existence'})
_ND_QID_RE = re.compile('^nd:\\d+:\\d+:(?P<kinds>[a-z_]+(?:\\+[a-z_]+)*)(?::delta:(?P<delta>[^:]+))?$')
_SELF_CLASSIFYING_TERMINALS = frozenset({'delivered', 'device_defect', 'authoring_failure'})
_NOT_OBJECTIVE_DISPOSITIONS = frozenset({'env_blocked', 'engineering_fault', 'rerun_isolated', 'fixed', 'reflow', 'ist_core_defect'})

def _basis_entry(fact: dict, field: str, value: str) -> dict:
    return {'ev': str(fact.get('ev') or ''), 'sha256': _fact_sha256(fact), 'field': field, 'value': value}

def _xml_precedent_basis(claim: dict) -> dict | None:
    xml_basis = claim.get('xml_basis')
    precedents = claim.get('precedent_device_passes')
    if not isinstance(xml_basis, dict) or not isinstance(precedents, list):
        return None
    current_build = str(xml_basis.get('build') or '').strip()
    verified = [{'build': str(item.get('build') or '').strip(), 'oid': str(item.get('oid') or '').strip(), 'source_filename': str(item.get('source_filename') or '').strip(), 'registry_sha256': str(item.get('registry_sha256') or '').strip()} for item in precedents if isinstance(item, dict) and item.get('verification') == 'device_delivery_pass' and str(item.get('build') or '').strip() and str(item.get('oid') or '').strip()]
    if not verified:
        return None
    cross_build = [item for item in verified if item['build'] != current_build]
    details = {'command': str(claim.get('command') or ''), 'current_build': current_build or '?', 'xml_source_filename': str(xml_basis.get('source_filename') or ''), 'xml_source_sha256': str(xml_basis.get('source_sha256') or ''), 'requested_node_path': xml_basis.get('requested_node_path'), 'nearest_node_paths': [str(value) for value in xml_basis.get('nearest_node_paths') or [] if str(value)], 'precedents': cross_build or verified}
    field = 'version_difference' if cross_build else 'xml_projection_anomaly'
    return {'ev': 'needs_decision_ledger', 'sha256': _fact_sha256({'claim': claim}), 'field': field, 'value': f"precedent_builds={','.join((item['build'] for item in details['precedents']))};current_build={details['current_build']};command={details['command']}", 'details': details}

def _ledger_mechanical_flags(raw: Any) -> dict[str, dict]:
    flags: dict[str, dict] = {}
    for item in raw if isinstance(raw, list) else ():
        if not isinstance(item, dict):
            continue
        kind = str(item.get('claim_kind') or '')
        if not kind:
            continue
        if item.get('spec_agrees'):
            flags.setdefault(kind, {})['spec_agrees'] = True
        if item.get('xml_absent_manual_only'):
            flags.setdefault(kind, {})['xml_absent_manual_only'] = True
    return flags

def _claim_kinds_from_facts(aid: str, mine: list[dict]) -> list[tuple[str, dict]]:
    answered = {str(f.get('question_id') or '') for f in mine if _decision_resolves_question(f) and str(f.get('question_id') or '')}
    out: list[tuple[str, dict]] = []
    for fact in mine:
        if fact.get('ev') != 'needs_decision':
            continue
        qid = str(fact.get('question_id') or '')
        if qid in answered:
            continue
        match = _ND_QID_RE.match(qid)
        if match:
            out.extend(((kind, fact) for kind in match.group('kinds').split('+')))
    return out

def classify_blocking(aid: str, mine: list[dict], ledger_claims: Any=None, raw_ledger_claims: Any=None, terminal_outcome: str='', *, facts: list[dict] | None=None) -> dict:
    basis: list[dict] = []
    matched: list[str] = []

    def _hit(cls: str, fact: dict, field: str, value: str) -> None:
        basis.append(_basis_entry(fact, field, value))
        if cls and cls not in matched:
            matched.append(cls)
    from cex_core.engine.ist_core.compile_engine.authority_delivery_policy import effective_authority_facts, is_authority_block_terminal, is_authority_unverified_block
    execution_terminal = active_execution_terminal(mine, facts=facts)
    if is_authority_block_terminal(execution_terminal):
        from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
        effective = effective_authority_facts(mine if facts is None else facts, aid)
        position = next((index for index, row in enumerate(effective) if row == execution_terminal), -1)
        evidence = effective[:position + 1] if position >= 0 else []
        refs = TC.build_terminal_credential(aid=aid, outcome='blocked', preferred_layer='delivery', facts=evidence)
        valid, errors = TC.validate_terminal_credential({'aid': aid, 'outcome': 'blocked', 'layer': 'delivery', 'credential_refs': refs}, facts=evidence)
        if valid:
            kind = B_AUTHORITY_UNVERIFIED if is_authority_unverified_block(execution_terminal) else B_AUTHORITY_CONFLICT
            _hit(kind, execution_terminal, 'reason_code', str(execution_terminal.get('reason_code') or ''))
            return {'class': kind, 'basis': basis, 'co_signals': []}
        return {'class': NOT_OBJECTIVE, 'basis': [{'field': 'credential_validation', 'value': errors}], 'co_signals': []}
    from cex_core.engine.ist_core.compile_engine.authoring_stops import is_unattributed_authoring_stop
    if is_unattributed_authoring_stop(execution_terminal):
        from cex_core.engine.ist_core.compile_engine import terminal_credentials as TC
        from cex_core.engine.ist_core.compile_engine.terminal_outcomes import UNATTRIBUTED_LAYER
        rows = mine if facts is None else facts
        position = next((index for index, row in enumerate(rows) if row == execution_terminal), -1)
        evidence = rows[:position + 1] if position >= 0 else []
        refs = TC.build_terminal_credential(aid=aid, outcome='blocked', preferred_layer=UNATTRIBUTED_LAYER, facts=evidence)
        valid, errors = TC.validate_terminal_credential({'aid': aid, 'outcome': 'blocked', 'layer': UNATTRIBUTED_LAYER, 'credential_refs': refs}, facts=evidence)
        if valid:
            from cex_core.engine.ist_core.compile_engine.contradiction_stop import is_contradiction_stop
            stop_cause = str(execution_terminal.get('stop_cause') or '')
            if stop_cause == B_UNRECOGNIZED_ROUTING:
                kind = B_UNRECOGNIZED_ROUTING
            elif stop_cause == B_ARTIFACT_UNVERIFIABLE:
                kind = B_ARTIFACT_UNVERIFIABLE
            elif is_contradiction_stop(execution_terminal):
                kind = B_CONTRA_UNATTRIBUTED
            else:
                kind = B_AUTHORING_UNATTRIBUTED
            _hit(kind, execution_terminal, 'stop_cause', stop_cause)
            return {'class': kind, 'basis': basis, 'co_signals': []}
        return {'class': NOT_OBJECTIVE, 'basis': [{'field': 'credential_validation', 'value': errors}], 'co_signals': []}
    for fact in reversed(mine):
        if fact.get('ev') != 'decision':
            continue
        cls, field = _override_class_from_decision(fact)
        if cls:
            _hit(cls, fact, field, str(fact.get(field) or ''))
            return {'class': cls, 'basis': basis, 'co_signals': []}
    atts = [f for f in mine if f.get('ev') == 'attribution']
    for att in atts:
        if str(att.get('disposition') or '') == 'defect_candidate' and str(att.get('evidence') or '').strip() not in ('', 'user') and isinstance(att.get('defect_candidate'), dict) and product_expected_source_is_valid((att.get('defect_candidate') or {}).get('expected_with_source')):
            _hit(B_DEVICE_DEFECT, att, 'disposition', 'defect_candidate')
    unsupported = [f for f in mine if f.get('ev') == 'unsupported_feature']
    for fact in unsupported:
        _hit(B_ENV_UNMET, fact, 'ev', 'unsupported_feature')
    for fact in mine:
        if fact.get('ev') == 'coexist_conflict':
            _hit(B_ENV_UNMET, fact, 'channel', str(fact.get('channel') or 'cross_case_coexistence'))
    active_scenario2 = scenario2_abandon_active(mine)
    for fact in mine:
        if fact.get('ev') == 'policy_abandon':
            if fact.get('reason_code') == SCENARIO2_REASON_CODE and (not active_scenario2):
                continue
            cls = canonical_class(str(fact.get('blocking_class') or ''))
            if cls in ABANDON_CLASSES:
                _hit(cls, fact, 'ev', 'policy_abandon')
                return {'class': cls, 'basis': basis, 'co_signals': []}
        if fact.get('ev') == 'source_conflict_blocked':
            _hit(B_XML_CONFLICT, fact, 'ev', 'source_conflict_blocked')
            return {'class': B_XML_CONFLICT, 'basis': basis, 'co_signals': []}
        if fact.get('ev') == 'authority_preflight_blocked':
            _hit(B_SPEC_CASE, fact, 'ev', 'authority_preflight_blocked')
            return {'class': B_SPEC_CASE, 'basis': basis, 'co_signals': []}
        if fact.get('ev') == 'recompose_case_quarantined':
            _hit(B_UNCLASSIFIED, fact, 'ev', 'recompose_case_quarantined')
            return {'class': B_UNCLASSIFIED, 'basis': basis, 'co_signals': []}
        if fact.get('ev') == 'xml_absence_terminal':
            _hit(B_XML_CONFLICT, fact, 'ev', 'xml_absence_terminal')
            return {'class': B_XML_CONFLICT, 'basis': basis, 'co_signals': []}
    claim_hits: list[tuple[str, dict, dict]] = []
    for claim in _structured_claims(ledger_claims):
        claim_hits.append((str(claim.get('claim_kind') or ''), {'ev': 'needs_decision_ledger', 'claim_kind': claim.get('claim_kind')}, claim))
    claim_hits.extend(((kind, fact, {}) for kind, fact in _claim_kinds_from_facts(aid, mine)))
    raw_terminal_claims = [claim for claim in (raw_ledger_claims if isinstance(raw_ledger_claims, list) else []) if isinstance(claim, dict) and claim.get('claim_kind') == 'command_existence' and (claim.get('terminal') is True) and (claim.get('requires_user_decision') is False) and isinstance(claim.get('xml_basis'), dict)]
    existing_commands = {str(claim.get('command') or '') for _kind, _fact, claim in claim_hits if isinstance(claim, dict)}
    for claim in raw_terminal_claims:
        if str(claim.get('command') or '') in existing_commands:
            continue
        claim_hits.append(('command_existence', {'ev': 'needs_decision_ledger', 'claim_kind': 'command_existence'}, claim))
    mech_flags = _ledger_mechanical_flags(raw_ledger_claims if raw_ledger_claims is not None else ledger_claims)
    for kind, fact, claim in claim_hits:
        if kind in DEVICE_CLAIM_KINDS:
            _hit(B_ENV_UNMET, fact, 'claim_kind', kind)
        elif kind in MANUAL_CLAIM_KINDS:
            if claim.get('xml_absent_manual_only') or mech_flags.get(kind, {}).get('xml_absent_manual_only'):
                _hit(B_MANUAL_ERROR, fact, 'claim_kind', f'{kind}+xml_absent_manual_only')
                version_basis = _xml_precedent_basis(claim)
                if version_basis is not None:
                    basis.append(version_basis)
                if claim.get('spec_agrees') or mech_flags.get(kind, {}).get('spec_agrees'):
                    basis.append(_basis_entry(fact, 'claim_kind', f'{kind}+spec_also_disagrees_with_xml'))
            elif claim.get('spec_agrees') or mech_flags.get(kind, {}).get('spec_agrees'):
                _hit(B_XML_CONFLICT, fact, 'claim_kind', f'{kind}+spec_agrees')
            else:
                _hit(B_MANUAL_ERROR, fact, 'claim_kind', kind)
        elif kind in MINDMAP_CLAIM_KINDS:
            _hit(B_SPEC_CASE, fact, 'claim_kind', kind)
    for fact in mine:
        if fact.get('ev') == 'contradiction' and str(fact.get('shape') or '') == 'manual_vs_device':
            _hit(B_MANUAL_ERROR, fact, 'shape', 'manual_vs_device')
    if matched:
        if B_MANUAL_ERROR in matched and B_DEVICE_DEFECT in matched:
            rest = [c for c in matched if c not in (B_MANUAL_ERROR, B_DEVICE_DEFECT)]
            return {'class': B_DEVICE_MANUAL, 'basis': basis, 'co_signals': [B_MANUAL_ERROR, B_DEVICE_DEFECT] + rest}
        return {'class': matched[0], 'basis': basis, 'co_signals': matched[1:]}
    dispositions = {str(f.get('disposition') or '') for f in atts}
    engine_internal = bool(dispositions & _NOT_OBJECTIVE_DISPOSITIONS) or any((f.get('ev') == 'delivery_blocked' for f in mine))
    if engine_internal and (not unsupported):
        return {'class': NOT_OBJECTIVE, 'basis': basis, 'co_signals': []}
    if terminal_outcome in _SELF_CLASSIFYING_TERMINALS:
        return {'class': NOT_OBJECTIVE, 'basis': basis, 'co_signals': []}
    from cex_core.engine.ist_core.compile_engine._shared import escalation_budget_kind
    for fact in reversed(mine):
        if fact.get('ev') != 'escalated':
            continue
        _kind = escalation_budget_kind(fact)
        if _kind:
            _hit(B_UNCLASSIFIED, fact, 'engine_budget_exhausted', _kind)
            return {'class': B_UNCLASSIFIED, 'basis': basis, 'co_signals': []}
        break
    from cex_core.engine.ist_core.compile_engine.execution_failure import is_runtime_infrastructure_terminal_fact
    execution_terminal = active_execution_terminal(mine, facts=facts)
    if is_runtime_infrastructure_terminal_fact(execution_terminal):
        reason_code = str(execution_terminal.get('reason_code') or '')
        _hit(B_EXECUTION_INFRA, execution_terminal, 'reason_code', reason_code)
        basis[-1]['details'] = {'layer': 'execution', 'error_text': str(execution_terminal.get('error_text') or '')}
        return {'class': B_EXECUTION_INFRA, 'basis': basis, 'co_signals': []}
    return {'class': B_UNCLASSIFIED, 'basis': basis, 'co_signals': []}
