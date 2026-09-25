# 生成：tools/extract_engine.py ← InfoTest main/ist_core/tools/device/emit_xlsx_tool.py（sha256 f4d92af2f9c3fd57）。不在这里手改。
"""compile_emit: 从简单步骤列表产出**结构正确**的 A-I ``case.xlsx``。

为什么要它:agent 用 run_python 手搓 openpyxl 容易造成表头、执行页或 E/F/G 列错位，
框架随后可能找不到 case 行并形成空真结果。本工具复用
``case_compiler.xlsx_emit.emit_xlsx``：生产模式由发布规则选择已完成同 SHA
真机验收的新契约模板；缺晋升凭证时用现役 v2 候选模板（含 IST_EXCEL_CONTRACT），
不再回落跳转机已拒收的 markerless legacy。只重写定位后的执行数据区。**结构由工具保证，内容由 agent 决定。**

agent 只需给:文件级前置命令(init) + 步骤列表(每步 actor/action/data)。列语义:
  E=操作对象(被测设备/check_point/test_env/time)  F=方法(cmd_config/cmds_config/found/
  not_found/found_times/事实源主机名/sleep...)  G=数据(命令/期望文本)
  H=save_as(存变量,可选)  I=input_var(引用变量,可选)
工具自动放进正确的行/列,agent 不碰模板结构。
"""
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import contextlib
import functools
import json
import hashlib
import inspect
import logging
import os
import re
import stat
import time
from collections import Counter
from collections.abc import Mapping as _Mapping
from collections.abc import Sequence
from contextvars import ContextVar
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, TypedDict
from langchain_core.tools import tool
from cex_core.engine.common.schema_identity import accepts_schema
from cex_core.engine.engine_managed_outputs import MECHANICAL_FINDINGS_SIDECAR_NAME as _MECHANICAL_FINDINGS_SIDECAR_NAME
from cex_core.engine.ist_core.compile_engine import _shared as _sh
from cex_core.engine.case_compiler import xml_conflict_core as _XC
from cex_core.engine.case_compiler.vendor_stdlib import XML_COMMAND_NOT_FOUND
logger = logging.getLogger(__name__)
_CURRENT_EMIT_GATE_CODES: ContextVar[list[str] | None] = ContextVar('ist_current_emit_gate_codes', default=None)

def _safe_output_component(value: str, *, field: str) -> str:
    """校验外部标识只能是 outputs 下的单个目录名，并拒绝符号链接逃逸。"""
    name = str(value or '').strip()
    if not name:
        raise ValueError(f'{field} is required')
    if name in {'.', '..'} or Path(name).is_absolute() or '/' in name or ('\\' in name) or ('~' in name) or any((ord(ch) < 32 for ch in name)) or (len(name) > 180):
        raise ValueError(f'{field} must be one safe directory name under workspace/outputs')
    try:
        from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
        session = current_worker_device_session()
    except Exception:
        session = None
    if session is not None and session.autoid and (field in {'autoid', 'out_name'}) and (name != session.autoid):
        raise ValueError(f'{field} is outside the bound compile-worker case scope')
    root = _sh.outputs_root()
    candidate = root / name
    if candidate.is_symlink():
        raise ValueError(f'{field} resolves through a symbolic-link directory')
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f'{field} escapes workspace/outputs') from exc
    from cex_core.engine import knowledge_paths as _kp
    from cex_core.engine.ist_core.tools.deepagent import file_tools as _file_tools
    production_root = _kp.workspace_bucket_root('outputs', workspace_root=_file_tools._WORKSPACE_ROOT).resolve()
    if root_resolved == production_root:
        guarded = _file_tools._resolve_writable_path(str(candidate / 'case.xlsx'))
        if guarded.parent.resolve() != candidate_resolved:
            raise ValueError(f'{field} failed the workspace write-path guard')
    return name

def _safe_case_path(value: str, *, field: str) -> tuple[str, Path]:
    """返回已过写路径约束的目录名与 case.xlsx 路径；既有文件不得是 symlink。"""
    name = _safe_output_component(value, field=field)
    path = _sh.outputs_root() / name / 'case.xlsx'
    if path.is_symlink():
        raise ValueError(f'{field}/case.xlsx must not be a symbolic link')
    return (name, path)

def _read_claims_ledger(ndp: Path, autoid: str) -> dict | None:
    """读 needs_decision 台账;**读损返回 None=调用方必须跳过落盘,不得覆写**。

    旧行为:parse 失败静默 `pass` → data 停在空 claims → 整份覆写把**其他规则**已落的
    claims 一起抹掉,用户题面凭空消失且无任何痕迹(P0,Design 发现+leader 盘面坐实)。
    台账是「先问后落」的凭据,损坏时正确处置是保留原文件 + 出声,不是拿空账盖掉。
    """
    aid = (autoid or '').strip()
    if not ndp.is_file():
        return {'autoid': aid, 'claims': []}
    try:
        loaded = json.loads(ndp.read_text(encoding='utf-8'))
    except Exception:
        logger.warning('needs_decision 台账读损(autoid=%s, path=%s):保留原文件不覆写,本次 claim 跳过落盘', aid, ndp, exc_info=True)
        return None
    if isinstance(loaded, dict) and isinstance(loaded.get('claims'), list):
        return loaded
    logger.warning('needs_decision 台账结构不符(autoid=%s, path=%s):保留原文件不覆写,本次 claim 跳过落盘', aid, ndp)
    return None

def _land_claims(autoid: str, mutate, *, gate: str) -> bool:
    """读台账 → 由 mutate(claims)->claims 改写 → **原子**落盘。返回是否真落成。

    读损/写失败一律返回 False 且出声(logger.warning),调用方据此**不得**再向 LLM 承诺
    「ledger entry is already written」——台账没写成却报已写,用户面就少一道题且无人
    知道(P0 三件:读损清账 / 非原子 / 假承诺)。各规则自己的 claim 合并语义留在 mutate 里。
    """
    try:
        from cex_core.engine.ist_core.tools.device.verifiability_tool import _write_json_atomic
        outd = _sh.outputs_root() / (autoid or '').strip()
        outd.mkdir(parents=True, exist_ok=True)
        ndp = outd / 'needs_decision.json'
        data = _read_claims_ledger(ndp, autoid)
        if data is None:
            return False
        data['claims'] = mutate(list(data.get('claims') or []))
        _write_json_atomic(ndp, data)
        return True
    except Exception:
        logger.warning('%s needs_decision 落盘失败(autoid=%s):返回文本不再承诺台账已写', gate, autoid, exc_info=True)
        return False

def _answerer_undetermined_mutator(entry: dict):
    """answerer_undetermined claim 的台账改写子工厂（撤旧同 kind + 追加）。

    命名工厂而非匿名 lambda：闭集守门
    ``test_emit_ledger_claim_kind_closed_set_covers_live_writer_sites`` 的 AST
    扫描面只认命名回调里机械可提取的 ``claim_kind`` 字面量——写点藏进匿名函数
    那一刻扫描面就悄悄漏掉一个写手。
    """

    def _apply(claims: list[dict]) -> list[dict]:
        kept = [claim for claim in claims if str(claim.get('claim_kind') or '') != 'answerer_undetermined']
        kept.append({**entry, 'claim_kind': 'answerer_undetermined'})
        return kept
    return _apply

def land_answerer_undetermined_claim(autoid: str, entry: dict) -> bool:
    """answerer_statement option 4 的 typed claim 落账（开链永不密封，路由 ASK）。

    台账机制与 emit 系 claim 同一家门（``_land_claims``：读损保护 + 原子写）；
    路由决策在 ``mechanical_case_submit_tool._route_answerer_undetermined``——
    它判「该问用户」，这里只管「把题落账」。返回是否真落成，调用方据此不得
    假承诺 routed。
    """
    return _land_claims(autoid, _answerer_undetermined_mutator(entry), gate='answerer_statement')
_SENTINEL_AUTOID = '999999999999999'
import threading as _threading
_EMIT_FAIL_STREAK: dict[str, int] = {}
_EMIT_FAIL_LOCK = _threading.Lock()

def _emit_fail_streak_bump(autoid: str) -> int:
    with _EMIT_FAIL_LOCK:
        _EMIT_FAIL_STREAK[autoid] = _EMIT_FAIL_STREAK.get(autoid, 0) + 1
        return _EMIT_FAIL_STREAK[autoid]

def _emit_fail_streak_clear(autoid: str) -> None:
    with _EMIT_FAIL_LOCK:
        _EMIT_FAIL_STREAK.pop(autoid, None)

def _parse_autoids_arg(autoids: str | list[str] | None) -> tuple[list[str] | None, str | None]:
    """解析 ``compile_emit_merged`` 的 autoids 参数。

    返回 ``(aid_list, error)``：
    - ``(None, None)`` — 未提供 autoids（缺省、空串、空 list），走 cases_json 分支；
    - ``([], "error: …")`` — 显式传了 autoids 但解析后无有效 id（如 ``'[]'``、``["", "  "]``）；
    - ``(aid_list, None)`` — 解析成功，aid_list 非空。

    与旧 ``bool(autoids) and (list or strip())`` 不同：不再把「参数存在」与「解析非空」混在一个布尔里。
    """
    if autoids is None:
        return (None, None)
    if isinstance(autoids, list):
        if not autoids:
            return (None, None)
        aid_list = [str(a).strip() for a in autoids if str(a).strip()]
        if not aid_list:
            return ([], 'error: autoids list has no valid id (all elements empty)')
        return (aid_list, None)
    s = str(autoids).strip()
    if not s:
        return (None, None)
    try:
        parsed = json.loads(s) if s.startswith('[') else [x.strip() for x in s.split(',') if x.strip()]
    except json.JSONDecodeError as e:
        return ([], f'error: autoids JSON parse failed: {e}')
    if not isinstance(parsed, list):
        return ([], 'error: autoids must be a JSON array or a comma-separated id list')
    aid_list = [str(a).strip() for a in parsed if str(a).strip()]
    if not aid_list:
        return ([], 'error: autoids resolved to empty (pass a non-empty JSON array, a comma-separated string, or a native list)')
    return (aid_list, None)

def _build_sentinel():
    """构造垫底哨兵 case；只用框架内建最短合法等待，不携带设备命令。"""
    from cex_core.engine.case_compiler.case_ir import CaseIR, Row, Step
    return CaseIR(autoid=_SENTINEL_AUTOID, priority='P9', title='sentinel-do-not-execute', steps=[Step(stmt_type=2, description='sentinel', rows=[Row(test_object='time', method='sleep', data='1')])])

def _steps_to_caseir(autoid: str, steps: list, *, title: str=''):
    """把 [{E,F,G,H?,I?,desc?}, ...] 步骤列表转成一个 CaseIR。

    返回 (CaseIR, has_check_point) 或 (None, 错误字符串)。单 case 和合并多 case 共用,
    保证 stmt_type 递增/列语义/check_point 校验完全一致。
    """
    from cex_core.engine.case_compiler.blocks import capture_register_final_operator
    from cex_core.engine.case_compiler.case_ir import CaseIR, Row, Step
    ist_steps = []
    has_cp = False
    seen_vars: set[str] = set()
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            return (None, f'step[{i}] is not a dict')
        e = str(s.get('E', '')).strip()
        f = str(s.get('F', '')).strip()
        if not e or not f:
            return (None, f'step[{i}] is missing E or F')
        if e == 'test_env':
            f = f.lower()
        g_val = str(s.get('G', '') or '')
        h_val = s.get('H') or None
        i_val = str(s.get('I')) if s.get('I') is not None else None
        if e == 'check_point' and (not h_val) and (g_val in seen_vars):
            h_val, g_val = (g_val, '')
        if e == 'check_point':
            has_cp = True
            f = capture_register_final_operator(f, h_val)
            s['F'] = f
            s['G'] = g_val
            if h_val:
                s['H'] = h_val
        elif h_val:
            seen_vars.add(str(h_val))
        row = Row(test_object=e, method=f, data=g_val, save_as=h_val, input_var=i_val)
        ist_steps.append(Step(stmt_type=2 + i, description=str(s.get('desc', '') or ''), rows=[row]))
    if not has_cp:
        return (None, f'case {autoid} has no check_point step at all — it is bound to fail on-device (pass requires success>0). Add a found assertion.')
    case = CaseIR(autoid=autoid, priority='P1', title=title or f'agent_{autoid}', steps=ist_steps)
    return (case, has_cp)

def _unreachable_ip_admission(autoid: str, steps: list, init: str='', *, source_case_slice: dict | None=None, source_case_slice_sha256: str='', recorded_author_values: Sequence[str] | None=None, recorded_author_ip_literals: Sequence[str] | None=None) -> dict:
    """把不可达部署值拆成作者原值与 worker 自造值；判据仍同读 env_facts。

    作者身份只认 loader/engine 绑定的 canonical 单案切片，并逐 quote 走
    ``validate_source_case_anchors``。绑定缺失或失效时不发豁免：全部不可达值仍按
    worker 自造值处理，保留旧规则的防编造侧。

    ``recorded_author_values`` 是**已判定**的作者出处集合（合卷/归档回读 emit 期
    签在同一份 case.xlsx 上的判决）。传了它就不再从切片重推出处——同一份成品的作者
    出处只判一次，三个消费点读的是同一个判决，不是三次各自推导后碰巧一致。

    返回值里的 ``author_ip_literals`` 是同一份判决的另一半（2026-09-08，02 章 §2.27 T5
    扩到触发可达性与执行体路径两条规则）：作者亲笔写在密封切片里的**全部**地址字面
    （规范化后），不限于不可达值——那两条规则拒的是「落在触发够不着的段」与「执行体
    无声明路径」，值本身在拓扑声明集内，``author_unreachable_values`` 装不下它们。
    合卷/归档同样只按凭证读回（``recorded_author_ip_literals``），存量凭证没有这个
    字段就是空集，等于旧判据。
    """
    from cex_core.engine.ist_core.tools._shared.env_facts import _IPV4_RE, normalize_ip_literal, require_env_facts
    facts = require_env_facts()
    if recorded_author_values is not None:
        source_case_slice = None
        source_case_slice_sha256 = ''
    elif source_case_slice is None:
        try:
            from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
            session = current_worker_device_session()
        except Exception:
            session = None
        if session is not None and str(session.autoid or '') == str(autoid or ''):
            source_case_slice = dict(session.source_case_slice or {})
            source_case_slice_sha256 = str(session.source_case_slice_sha256 or '')
    compiled_values: set[str] = set()
    texts: list[str] = [init] if init else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        e = str(step.get('E', '')).strip()
        f = str(step.get('F', '')).strip()
        if e.startswith('APV') and f in ('cmd_config', 'cmds_config'):
            texts.append(str(step.get('G', '') or ''))
        elif e == 'test_env':
            texts.append(str(step.get('G', '') or ''))
    for text in texts:
        compiled_values.update(facts.unreachable_ipv4s(text))
        compiled_values.update(facts.unreachable_ipv6s(text))
    author_values: set[str] = set()
    author_ip_literals: set[str] = set()
    anchors: list[dict[str, str]] = []
    if recorded_author_values is not None:
        author_values.update((str(value) for value in recorded_author_values if str(value)))
        author_ip_literals.update((normalized for normalized in (normalize_ip_literal(value) for value in recorded_author_ip_literals or ()) if normalized))
    elif isinstance(source_case_slice, dict) and source_case_slice:

        def _literals(text: str) -> set[str]:
            found = {m.group(1) for m in _IPV4_RE.finditer(text)}
            found.update((normalize_ip_literal(lit) for lit, _addr in facts._iter_ipv6_literals(text)))
            return {value for value in found if value}
        title = str(source_case_slice.get('title') or '')
        if title:
            values = set(facts.unreachable_ipv4s(title)) | set(facts.unreachable_ipv6s(title))
            literals = _literals(title)
            if values or literals:
                author_values.update(values)
                author_ip_literals.update(literals)
                anchors.append({'kind': 'title', 'quote': title})
        for item in source_case_slice.get('step_intents') or []:
            if not isinstance(item, dict):
                continue
            for kind, key in (('step', 'desc'), ('expected', 'expected')):
                quote = str(item.get(key) or '')
                if not quote:
                    continue
                values = set(facts.unreachable_ipv4s(quote)) | set(facts.unreachable_ipv6s(quote))
                literals = _literals(quote)
                if values or literals:
                    author_values.update(values)
                    author_ip_literals.update(literals)
                    anchors.append({'kind': kind, 'quote': quote})
        if author_values or author_ip_literals:
            try:
                from cex_core.engine.ist_core.worker_device_context import validate_source_case_anchors
                source_error = validate_source_case_anchors(anchors, source_case_slice, autoid=str(autoid or ''), source_case_slice_sha256=str(source_case_slice_sha256 or ''))
            except (TypeError, ValueError, KeyError, RecursionError):
                source_error = 'source_case_slice_invalid'
            if source_error:
                author_values.clear()
                author_ip_literals.clear()
    return {'compiled_unreachable_values': sorted(compiled_values), 'author_unreachable_values': sorted(author_values), 'invented_unreachable_values': sorted(compiled_values - author_values), 'author_ip_literals': sorted(author_ip_literals)}

def _gate_unreachable_ips(autoid: str, steps: list, init: str='', *, source_case_slice: dict | None=None, source_case_slice_sha256: str='', recorded_author_values: Sequence[str] | None=None) -> str | None:
    """可达性校验规则：拒无作者出处的不可达部署值，作者值改落环境披露。

    病根:draft 凭空写 1.1.1.1/2.2.2.2 等示例 IP 当 service IP→设备不可达→dig 失败→断言全 fail。
    这里在 emit 出口兜底：无作者出处的不可达 IP 直接打回，并把可达集合原样告诉
    draft 让它重写；作者逐字出处由密封单案切片复核，只从硬拒中豁免并交上游落
    ``environment_execution_disclosure``，不在本层替作者或 worker 猜映射。

    ``recorded_author_values`` 供合卷与归档回读同一份 case.xlsx 上 emit 期已签发的
    作者出处判决（见 ``_recorded_author_unreachable_values``）：那两处没有密封单案
    切片，若照旧按"无作者绑定"重判，同一份成品会在单案 emit 放行、在合卷被拒——
    2026-09-04 <batch> 实证:一案的作者原值把 21 个已编写案的整卷一起拒掉。

    只校验**配置类**(APV_0 的 cmd_config/cmds_config)与 init 的 G;check_point 的期望文本里
    可能有正则/IP 片段不在此列(那是断言匹配目标,不是要连接的设备),不拦。

    v6 对称(D3,2026-08-15 交叉分析):同一批文本同时过 v4 与 v6 抽取面——此前只抽
    IPv4 字面,凭空编的 IPv6(池后端/VIP,如 2001:db8::99)零规则放行,与 v4 同判据
    (1.1.1.1 必拒)不对称。v6 可达=精确接口地址∪逐设备声明前缀(env_facts 白名单
    投影),全零地址豁免照 v4 非宿主样板。
    """
    from cex_core.engine.ist_core.tools._shared.env_facts import require_env_facts
    facts = require_env_facts()
    admission = _unreachable_ip_admission(autoid, steps, init=init, source_case_slice=source_case_slice, source_case_slice_sha256=source_case_slice_sha256, recorded_author_values=recorded_author_values)
    bad = list(admission['invented_unreachable_values'])
    if not bad:
        return None
    return f"case {autoid} uses {len(bad)} **environment-unreachable IP(s)**: {', '.join(bad)}\nThese IPs are not in any subnet of this testbed; on-device dig/connections are bound to fail (Hit=0, all assertions fail).\nRewrite with real reachable IPs — use real server IPs for backend service/pool, and unused in-segment IPs for VIP/listener:\n\n{facts.summary_for_agent()}"
import re as _re_dev

def _destructive_res() -> list:
    """自毁命令形态(2026-07-13 双源合流:与 structural_gate 同读 grammar
    destructive_commands.patterns 单一源——原 emit 与 structural_gate 各写一份、覆盖面
    不等已实漂移)。读失败留声回落硬编集(安全规则不能因数据不可读而消失,INV-11)。"""
    try:
        from cex_core.engine.case_compiler.domain_grammar import load_grammar
        pats = (load_grammar().get('destructive_commands') or {}).get('patterns') or []
        if pats:
            return [_re_dev.compile(p, _re_dev.IGNORECASE) for p in pats]
    except Exception:
        import logging
        logging.getLogger(__name__).warning('destructive_commands 文法读取失败——emit 自毁规则回落硬编集', exc_info=True)
    return [_re_dev.compile('^\\s*(reboot|reload|shutdown|halt|poweroff|clear\\s+config\\s+all|restore\\s+factory)\\b', _re_dev.IGNORECASE)]

def _gate_destructive_commands(autoid: str, steps: list, init: str='', *, stage: str='emit') -> str | None:
    """安全规则:拒绝 system reboot/reload/shutdown 等**破坏性设备生命周期命令**。

    禁令理由只有一条,而且是**引擎纪律**、不是框架能力缺失:床是共享的,上机 verify
    跑到生命周期命令会真把别人在用的 APV 重启/关机,整机清配还会把管理口一起带走
    (2026-07-13 两床被跑死、需 console 恢复)。

    2026-08-20 纠正一条写了很久的**假理由**:旧 docstring 与拒绝文案都写着「框架不
    支持:apv_ssh 单连接、read_until 5s、无重连——重启后必在死通道上读空 → 必 fail」。
    这句话与框架源码相反——`knowledge/framework/mirror/lib/apv/apv.py::reboot()`
    (:522-538)实有 30s 静默 + **10 轮 ping 探测** + **5 次重连**尝试,它就是为「重启
    后把设备等回来」写的。假理由的后果是指错修复方向:读到的人会去查连接层/超时,
    而真正的边界是「这台床不归你一个人用」——那是环境与纪律问题,不是命令写错了,
    也不是框架做不到。同一条纠正已落在 structural_gate.GATE_LESSON_TEXT
    ["destructive_command"] 里,两处文案同向。

    持久化/配置保存类用例**不该真重启**:替代范式的推导归 worker(要点先行+配置面
    模型),规则只给禁令与路由、不给命令序列。
    2026-07-13 双源合流后本规则读 grammar destructive_commands.patterns(与 structural_gate
    同源):拦生命周期命令(reboot/reload/shutdown/halt/poweroff,含 `system reboot` 形态)
    **加**整机清配形态(两床被跑死的那两条);**对象级** clear 不匹配、照常放行(范式要用)。
    """
    bad: list[tuple[int, str]] = []
    _res = _destructive_res()

    def _scan(text: str, idx: int) -> None:
        for line in (text or '').splitlines():
            line = line.strip()
            if line and any((r.search(line) for r in _res)):
                bad.append((idx, line))
    _scan(init, -1)
    for i, s in enumerate(steps):
        if is_apv_command_step(s, methods=None):
            _scan(str(s.get('G', '') or ''), i)
    if not bad:
        return None
    lines = '; '.join((f'step[{i}]={cmd!r}' for i, cmd in bad))
    _msg = f"case {autoid} contains {len(bad)} **destructive device-lifecycle command(s)**: {lines}\nRefused by engine discipline, NOT because the command is wrong: these are valid product CLI commands, and framework capability is not the limit either — the framework ships a device-lifecycle helper that waits a restarted device back up (it polls the device and retries the connection). The blocking fact is the environment: the testbed is shared, so a compiled case that restarts, powers down or wipes a whole device takes every other run on that bed down with it (two beds needed console recovery on 2026-07-13). Re-wording the command will not clear this gate; only a different objective shape or a not-compilable report will.\nTwo exits. (1) If the case objective can still be falsified without changing the device's lifecycle state, rewrite the mechanical case with a non-destructive CLI observation that preserves the case's own falsifying direction, and undo only what the case itself created (object-scoped cleanup or the paired inverse of what it configured). (2) If the objective genuinely requires the device to restart or be wiped, it cannot be compiled for a shared bed: query the sealed command-tree inventory with lang_query(kind='heads') and sign the structured not-compilable terminal using the returned receipt — state the reason as environment/policy, not as a missing command. Do not request a user ruling and do not force-emit."
    return _reject_compile_gate(autoid, 'destructive_command', _msg, detail=f'environment/policy refusal (shared bed), not a wrong command: {lines}', step_index=bad[0][0], stage=stage)
_SAVE_RE = _re_dev.compile('\\bwrite\\s+(memory|mem|file|all|net)\\b', _re_dev.IGNORECASE)
_RESTORE_RE = _re_dev.compile('(?<!clear\\s)(?<!show\\s)\\bconfig\\s+(memory|file|all|net)\\b', _re_dev.IGNORECASE)
_SAVE_REMOTE = ('file', 'all', 'net')

def _norm_family(tok: str) -> str:
    t = tok.lower()
    return 'memory' if t in ('memory', 'mem') else t
_INTENT_SAVE_RE = _re_dev.compile('(?<![a-z])(?:write|config)\\s*(all|mem(?:ory)?|file|net)(?![a-z0-9])', _re_dev.IGNORECASE)

def _intent_save_variant(autoid: str) -> str:
    """从引擎盖章的意图侧写(outputs/<autoid>/intent.json,author 派发时从 manifest 原文落)
    推导本案应测的保存变体——P1c 的证据源修正(2026-07-14 run20 实弹)。

    此前 expected_save_variant 仅由 worker 自我申报:漂移的 worker 恰恰不会申报——<case>
    把 write all 静默换成 write memory,P1c no-op 放行、与 668000 撞题,若非床污染挡下将
    交付假覆盖并把 write-memory 内容以 write-all 标题写回成投毒先例。盖章文件缺失或意图
    无保存族词 → 返回 ""(回退 no-op:非引擎路径/非持久化用例零回归)。"""
    try:
        p = _sh.outputs_root() / (autoid or '').strip() / 'intent.json'
        from cex_core.engine.case_compiler.contract_entry import read_intent_json
        d, _raw = read_intent_json(p, trusted_root=_sh.outputs_root())
        text = ' '.join([str(d.get('title') or '')] + [f"{si.get('desc') or ''} {si.get('expected') or ''}" for si in d.get('step_intents') or [] if isinstance(si, dict)])
        m = _INTENT_SAVE_RE.search(text)
        return _norm_family(m.group(1)) if m else ''
    except Exception:
        return ''

def _save_family(cmd: str) -> str | None:
    m = _SAVE_RE.search(cmd)
    return _norm_family(m.group(1)) if m else None

def _restore_family(cmd: str) -> str | None:
    m = _RESTORE_RE.search(cmd)
    return m.group(1).lower() if m else None

class ApvCommandRef(TypedDict):
    """APV 命令及其草稿步骤位置；Python 内部按 JSON-native 对象传递。"""
    command: str
    step_index: int
APV_CONFIG_METHODS = frozenset({'cmd_config', 'cmds_config'})
APV_NET_STATE_METHODS = APV_CONFIG_METHODS | frozenset({'cmd_enable'})

def is_apv_command_step(step: object, *, methods: frozenset[str] | None=APV_CONFIG_METHODS) -> bool:
    """这一步的 ``G`` 是不是「发到 APV 上执行的产品命令」。

    存在性规则 / ③④ 判定 / 裁决 3 的漂移回修都要回答同一个问题：**命令在卷面的哪里**。
    判据只此一份——各写一套的下场是「规则说这条命令有问题、回修却在卷面里找不到它」，
    表现成一句无从下手的「定位不到」。

    ``methods`` 是调用规则的**辖区声明**，默认沿用配置面两原语。传 ``None`` 表示
    **不按 F 过滤**（收全部 APV 执行步）——自毁闭集用这一档：那条规则是床安全不变量，
    按 `F` 分辖区等于留一个「换个值就能绕」的口子（<batch> 实证：`\\breboot\\b`
    只查 `cmd_config`/`cmds_config`，<case> 用 `F=cmd` 把 `system reboot noninteractive`
    送进了交付卷并 PASS）。断言行的 ``E`` 是 ``check_point``，不以 APV 打头，
    两档都自然排除，本函数不另设断言判据。
    """
    if not isinstance(step, _Mapping):
        return False
    if not str(step.get('E', '')).strip().startswith('APV'):
        return False
    if methods is None:
        return True
    return str(step.get('F', '')).strip() in methods

def _apv_command_lines_for_step(steps: list, index: int) -> list[str]:
    """把一个 APV 执行步还原成真正发给产品 CLI 的命令行。

    ``cmd_config`` 的 G 同时承载命令位置参数与执行器关键字；紧邻带
    ``prompt`` 调用的 YES/NO 是交互应答，不是另一条产品命令。存在性门、
    footprint 门和批前命令域预检必须共用这份解释，否则前两道门放行的标准库
    展开会在最后一道门被空命令头反向拒绝。

    调用方先决定哪些 F 属于自己的辖区；本函数只解释已选中步骤的 G。
    """
    if index < 0 or index >= len(steps) or (not isinstance(steps[index], dict)):
        return []
    step = steps[index]
    method = str(step.get('F') or '').strip()
    raw = str(step.get('G', '') or '')
    from cex_core.engine.case_compiler.excel_contract import parse_g_arguments, strip_apv_command_kwargs
    try:
        command = strip_apv_command_kwargs(raw, method)
    except Exception:
        command = raw
    lines = [line.strip() for line in command.splitlines() if line.strip()]
    if method != 'cmd_config':
        return lines
    if not lines or lines[0].upper() not in {'YES', 'NO'} or index <= 0:
        return lines
    previous = steps[index - 1]
    if not (isinstance(previous, dict) and str(previous.get('E') or '').strip() == str(step.get('E') or '').strip() and (str(previous.get('F') or '').strip() == 'cmd_config')):
        return lines
    try:
        _previous_args, previous_kwargs = parse_g_arguments(str(previous.get('G') or ''), 'cmd_config')
    except Exception:
        previous_kwargs = {}
    if str(previous_kwargs.get('prompt') or '').strip():
        return []
    return lines

def _ordered_apv_command_refs(steps: list, init: str) -> list[ApvCommandRef]:
    """按执行顺序收集 APV 配置命令，并保留草稿步骤位置。"""
    out: list[ApvCommandRef] = []
    for line in (init or '').splitlines():
        line = line.strip()
        if line:
            out.append({'command': line, 'step_index': -1})
    for index, s in enumerate(steps):
        if not is_apv_command_step(s):
            continue
        lines = _apv_command_lines_for_step(steps, index)
        for line in lines:
            line = line.strip()
            if line:
                out.append({'command': line, 'step_index': index})
    return out

def _ordered_apv_cmds(steps: list, init: str) -> list[str]:
    """APV 收集器的字符串投影；存在性判据与带位置 lint 共用同一事实源。"""
    return [item['command'] for item in _ordered_apv_command_refs(steps, init)]

def _structured_command_assertion_groups(steps: list, init: str) -> list[dict]:
    """把单命令观测步与其后连续的静态断言机械配对。

    本函数不猜命令或断言语义。多命令 ``cmds_config`` 无法证明后续断言属于
    其中哪一条，因此不进入情景 4；动态寄存器断言和 ``found_times`` 也因 XML
    result 声明缺少对应结构字段而不比较。条款引用见 判定图 §2.3/§2.4。
    """
    try:
        from cex_core.engine.case_compiler.case_ir import VALID_CHECK_METHODS
    except Exception:
        return []
    groups: list[dict] = []
    occurrence_index = sum((1 for line in str(init or '').splitlines() if line.strip()))
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        e = str(step.get('E') or '').strip()
        f = str(step.get('F') or '').strip()
        command_lines = [line.strip() for line in str(step.get('G') or '').splitlines() if line.strip()]
        is_command_step = e.startswith('APV') and f in {'cmd_config', 'cmds_config'}
        if not is_command_step:
            continue
        current_occurrence = occurrence_index
        occurrence_index += len(command_lines)
        if len(command_lines) != 1:
            continue
        assertions: list[dict[str, str]] = []
        for following in steps[index + 1:]:
            if not isinstance(following, dict):
                break
            if str(following.get('E') or '').strip() != 'check_point':
                break
            operator = str(following.get('F') or '').strip()
            value = str(following.get('G') or '')
            if operator not in VALID_CHECK_METHODS or operator == 'found_times' or str(following.get('H') or '').strip() or (not value):
                continue
            assertions.append({'operator': operator, 'value': value})
        if assertions:
            groups.append({'occurrence_index': current_occurrence, 'command': command_lines[0], 'assertions': assertions})
    return groups

def _param_tail(cmd: str, fam: str) -> str:
    """取 write/config <file|all|net> 命令在族词之后的参数尾(判断是否缺参)。"""
    m = _re_dev.search(f'\\b(?:write|config)\\s+{fam}\\b(.*)$', cmd, _re_dev.IGNORECASE)
    return m.group(1).strip() if m else ''

def _gate_save_restore_pairing(autoid: str, steps: list, init: str='', expected_save_variant: str='') -> str | None:
    """持久化测试结构规则(按执行顺序的有限状态校验,论文 correct-by-construction)。

    **仅在 case 含 config 恢复命令(memory/file/all/net)时触发**——即"配置保存/持久化"类用例。
    无恢复命令的用例(listener/forward/rr/pool 等 99%)直接 no-op,行为零变化(零回归)。

    校验(都与意图无关、确定性可判):
    - P0a 基线污染:首个对象配置之前不得有 write 保存(否则 config 恢复的是配置对象
      之前的旧快照→not_found 假通过);
    - P0b 紧邻配对:每个 config X 须配对其**前最近**的 write Y 且同族(不是无序集合成员);
    - P1a 清除步:对象配置与 config 恢复之间须有同一文法族的变更/清除步骤(否则恢复
      空操作、not_found 永真、测试空转);
    - P1b 参数完整:file/all/net 保存/恢复变体须带参数(裸 write net 设备拒,<case> 类);
    - P1c 意图变体:被 config 配对的那个 save 变体须 == manifest 透传的 expected_save_variant
      (防 draft 偷换 write all→write memory,<case> 类)。**缺 expected 则 no-op 放行**(防误拒)。

    write↔config 对称命令对(memory/file/all/net 各恢复各的存储,手册4015-4049);先例 log_backup。
    """
    cmds = _ordered_apv_cmds(steps, init)
    restores = [(i, c, _restore_family(c)) for i, c in enumerate(cmds) if _restore_family(c)]
    if expected_save_variant:
        _ev = _norm_family(expected_save_variant.strip())
        _used_any = next((f for f in (_save_family(c) for c in cmds) if f), None)
        if _used_any and _used_any != _ev:
            return f"case {autoid} intent variant mismatch: this case should test write {_ev}, but the sheet's save command uses write {_used_any} — the intent got swapped (and likely collides with the sibling case that owns write {_used_any}). Change the save back to write {_ev}."
    if not restores:
        return None
    errs: list[str] = []
    object_index: int | None = None
    object_family = None
    clear_family_matched = False
    family_window_unknown = False
    try:
        from cex_core.engine.case_compiler.domain_grammar import cleanup_family, is_object_config_command, restore_gate_grammar
        grammar = restore_gate_grammar()
        for index, command in enumerate(cmds):
            if not is_object_config_command(command, grammar):
                continue
            object_index = index
            object_family = cleanup_family(command, grammar)
            break
        if object_index is None or object_family is None:
            raise LookupError('first object-config command has no cleanup-rule family')
        first_restore_idx = restores[0][0]
        for command in cmds[object_index + 1:first_restore_idx]:
            tokens = str(command or '').strip().split(None, 1)
            if not tokens or tokens[0].casefold() not in grammar.mutating:
                continue
            family = cleanup_family(command, grammar, strip_mutating_verb=True)
            if family is None:
                family_window_unknown = True
                continue
            if family.rule_order == object_family.rule_order:
                clear_family_matched = True
    except Exception as exc:
        logger.warning('save/restore P0a/P1a skipped for case %s: %s', autoid, type(exc).__name__, exc_info=True)
        object_index = None
        object_family = None
    if object_index is not None and object_family is not None and family_window_unknown and (not clear_family_matched):
        logger.warning('save/restore P0a/P1a skipped for case %s: mutating command family is unknown', autoid)
        object_index = None
        object_family = None
    if object_index is not None and object_family is not None:
        for c in cmds[:object_index]:
            if _save_family(c):
                errs.append(f'baseline pollution: save command {c!r} appears before the object is configured — config would restore the old snapshot taken before the object config, and not_found passes falsely. Delete it (the baseline should not be pre-saved).')
                break
    last_save = None
    for c in cmds:
        sf = _save_family(c)
        if sf:
            last_save = sf
        rf = _restore_family(c)
        if rf:
            if last_save is None:
                errs.append(f'restore config {rf} has no preceding write save command (restoring a storage that was never saved).')
            elif last_save != rf:
                errs.append(f'restore config {rf} and its nearest preceding save write {last_save} are of different families — it does not read the copy just saved. Change it to config {last_save}, or change the save to write {rf} (the two must be the same family).')
    if object_index is not None and object_family is not None and (not clear_family_matched):
        errs.append('missing clear step: nothing between the object config and the config restore removes the configured object from running config — the restore then restores over an unchanged state (no-op), a not_found check is always true, and the test verifies nothing. Add a clear/negate step for the object THIS case configured, after the save and before the restore; derive the inverse form from the manual (the `no`/`clear` pairing of the construct you used), scoped to that object only.')
    for c in cmds:
        fam = _save_family(c) or _restore_family(c)
        if fam in _SAVE_REMOTE and (not _param_tail(c, fam)):
            verb = 'write' if _save_family(c) else 'config'
            errs.append(f"""command missing argument: {c!r} — the {fam} variant needs an argument (like {verb} {fam} <filename/target>); complete it from the manual (resolve its root with lang_query(kind="docs", query="vendor_manual") and grep that version's cli_cn.md), the device rejects the bare command.""")
    if expected_save_variant:
        ev = _norm_family(expected_save_variant.strip())
        used = None
        ls = None
        for c in cmds:
            sf = _save_family(c)
            if sf:
                ls = sf
            if _restore_family(c):
                used = ls
                break
        if used and used != ev:
            errs.append(f'intent variant mismatch: this case should test persistence of write {ev}, but the save actually used write {used} (the intent got swapped and this duplicates another variant). Change the save back to write {ev} and restore with config {ev}.')
    if not errs:
        return None
    body = '\n'.join((f'  - {e}' for e in errs))
    return f"case {autoid} persistence test (config-restore class) structural errors:\n{body}\nMechanism note (not a command recipe): a config-restore (config <variant>) is an IMPORT of the saved artifact back into running config — assert per your case's stated test point (a not-persisted intent asserts absence WITHOUT any restore step; a save/restore round-trip intent asserts presence AFTER the restore). Which commands realize each step: inspect the version manual and query the version-bound grammar with lang_query."
REACHABILITY_SCOPE_SCHEMA = 'ist.trigger-reachability-scope'
UNREACHABLE_IP_ADMISSION_SCHEMA = 'ist.unreachable-ip-admission'

class ReachabilityExcludedRow(TypedDict):
    block_index: int
    E: str
    F: Literal['cmd_config', 'cmds_config']
    G: str

class ReachabilityScope(TypedDict):
    schema: Literal['ist.trigger-reachability-scope']
    source: Literal['sealed_mechanical_case', 'tool_blocks', 'raw_steps']
    mechanical_case_sha256: str
    blocks_sha256: str
    excluded_kinds: list[str]
    excluded_rows: list[ReachabilityExcludedRow]

def _canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()

def _reachability_scope_from_blocks(blocks: list, *, mechanical_case_sha256: str='') -> ReachabilityScope:
    """从组合子 JSON 原文铸出 CONFIG 排除行；不从 xlsx/G 文本反猜 kind。"""
    if not isinstance(blocks, list) or not blocks:
        raise ValueError('blocks must be a non-empty array')
    seal = str(mechanical_case_sha256 or '').strip()
    if seal and re.fullmatch('[0-9a-f]{64}', seal) is None:
        raise ValueError('mechanical_case_sha256 must be 64 lowercase hex characters')
    rows: list[ReachabilityExcludedRow] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise ValueError(f'blocks[{index}] must be an object')
        kind = str(block.get('kind') or '').strip().upper()
        if not kind:
            raise ValueError(f'blocks[{index}].kind is required')
        if kind != 'CONFIG':
            continue
        commands = block.get('cmds')
        if not isinstance(commands, list) or not commands:
            raise ValueError(f'blocks[{index}](CONFIG).cmds must be a non-empty array')
        normalized = [str(command).strip().replace('\\n', '\n').replace('，', ',') for command in commands if isinstance(command, str) and str(command).strip()]
        if len(normalized) != len(commands):
            raise ValueError(f'blocks[{index}](CONFIG).cmds must contain only non-empty strings')
        rows.append({'block_index': index, 'E': str(block.get('host') or 'APV_0').strip(), 'F': 'cmd_config' if len(normalized) == 1 else 'cmds_config', 'G': '\n'.join(normalized)})
    blocks_sha256 = _canonical_json_sha256(blocks)
    return {'schema': REACHABILITY_SCOPE_SCHEMA, 'source': 'sealed_mechanical_case' if seal else 'tool_blocks', 'mechanical_case_sha256': seal, 'blocks_sha256': blocks_sha256, 'excluded_kinds': ['CONFIG'], 'excluded_rows': rows}

def _raw_reachability_scope() -> ReachabilityScope:
    return {'schema': REACHABILITY_SCOPE_SCHEMA, 'source': 'raw_steps', 'mechanical_case_sha256': '', 'blocks_sha256': '', 'excluded_kinds': [], 'excluded_rows': []}

def _validate_reachability_scope(value: object) -> tuple[ReachabilityScope | None, str]:
    required = {'schema', 'source', 'mechanical_case_sha256', 'blocks_sha256', 'excluded_kinds', 'excluded_rows'}
    if not isinstance(value, dict) or set(value) != required:
        return (None, 'scope must be an object with the exact v1 field set')
    if value.get('schema') != REACHABILITY_SCOPE_SCHEMA:
        return (None, 'scope schema is not ist.trigger-reachability-scope')
    source = value.get('source')
    if source not in {'sealed_mechanical_case', 'tool_blocks', 'raw_steps'}:
        return (None, 'scope source is outside the closed set')
    seal = value.get('mechanical_case_sha256')
    blocks_sha = value.get('blocks_sha256')
    if not isinstance(seal, str) or not isinstance(blocks_sha, str):
        return (None, 'scope digests must be strings')
    kinds = value.get('excluded_kinds')
    rows = value.get('excluded_rows')
    if not isinstance(kinds, list) or not all((isinstance(item, str) for item in kinds)):
        return (None, 'scope excluded_kinds must be a string array')
    if not isinstance(rows, list):
        return (None, 'scope excluded_rows must be an array')
    if source == 'raw_steps':
        if seal or blocks_sha or kinds or rows:
            return (None, 'raw_steps scope cannot claim block-kind exclusions')
    else:
        if kinds != ['CONFIG'] or re.fullmatch('[0-9a-f]{64}', blocks_sha) is None:
            return (None, 'block scope must bind CONFIG and a 64-hex blocks digest')
        if source == 'sealed_mechanical_case' and re.fullmatch('[0-9a-f]{64}', seal) is None:
            return (None, 'sealed block scope must bind a 64-hex mechanical-case digest')
        if source == 'tool_blocks' and seal:
            return (None, 'tool_blocks scope cannot claim a mechanical-case digest')
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {'block_index', 'E', 'F', 'G'}:
            return (None, f'excluded_rows[{index}] has an invalid field set')
        if not isinstance(row['block_index'], int) or isinstance(row['block_index'], bool) or row['block_index'] < 0 or (not all((isinstance(row[key], str) for key in ('E', 'F', 'G')))) or (row['F'] not in {'cmd_config', 'cmds_config'}) or (not row['E'].startswith('APV')) or (not row['G']):
            return (None, f'excluded_rows[{index}] is not a valid CONFIG expansion row')
    return (value, '')

def _gate_unreachable_listener(autoid: str, steps: list, init: str='', *, blocks: list | None=None, reachability_scope: ReachabilityScope | dict | None=None, author_ip_literals: Sequence[str] | None=None, findings_out: dict | None=None) -> str | None:
    """触发可达性规则:listener/VIP 及 dig/curl 目标 IP 不能落在「触发够不着」的 APV 接口段。

    病根(<case> 类):listener 配在 APV 的纯管理/纯后端段接口,
    该网段没有路由器/客户端,dig/curl 源够不着 → 上机 NXDOMAIN/无应答、断言全 fail。
    与意图无关、确定性可判(IP 是否在「触发同段」是拓扑客观事实),且对 dig/curl/任意触发
    通用——不针对具体命令。env_facts 派生,零硬编码 IP。

    ``author_ip_literals``(2026-09-08,02 章 §2.27 T5 扩展):**已判定**的作者亲笔地址
    集合。命中值若在其中,不再硬拒——那是「这张床上没有触发设备够得着作者写的地址」
    的环境事实,命令没写错、框架也做得到;改由上游落环境执行披露。不在其中的命中值
    照旧拒(防编造那一半原样保留)。判决只在单案 emit 判一次,合卷按凭证读回,交卷规则
    用密封切片算同一份;本函数不自己推出处。``findings_out`` 传 dict 时把两类命中
    (作者/自造)结构化回填,供交卷规则落呈报。
    """
    if findings_out is None:
        findings_out = {}
    findings_out.update({'scope_error': '', 'blind_hits': [], 'bad_targets': [], 'author_blind_hits': [], 'author_bad_targets': [], 'invented_blind_hits': [], 'invented_bad_targets': [], 'author_sourced_targets': []})
    if reachability_scope is None and blocks is not None:
        try:
            reachability_scope = _reachability_scope_from_blocks(blocks)
        except (TypeError, ValueError) as exc:
            findings_out['scope_error'] = str(exc)
            return f'case {autoid} trigger reachability scope is invalid: {exc}'
    if reachability_scope is None:
        scope = _raw_reachability_scope()
    else:
        scope, scope_error = _validate_reachability_scope(reachability_scope)
        if scope is None:
            findings_out['scope_error'] = str(scope_error)
            return f'case {autoid} trigger reachability scope is invalid: {scope_error}'
    excluded = Counter(((str(row['E']), str(row['F']), str(row['G'])) for row in scope['excluded_rows']))
    from cex_core.engine.ist_core.tools._shared.env_facts import normalize_ip_literal, require_env_facts
    facts = require_env_facts()
    import ipaddress as _ipaddr
    import re as _re
    _ip_re = _re.compile('\\b(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\b')

    def _norm6(value: str) -> str:
        """v6 字面规范化(2001:db8::0099 与 2001:db8::99 是同一地址,字符串集合比不出来)。"""
        try:
            return str(_ipaddr.IPv6Address(str(value).split('/')[0].split('%')[0].strip('[]')))
        except ValueError:
            return ''
    author_set = {normalized for normalized in (normalize_ip_literal(value) for value in author_ip_literals or ()) if normalized}
    blind = set(facts.unreachable_lb_ips())
    blind6 = {n for n in (_norm6(x) for x in facts.v6_lb_ips_without_driver_prefix()) if n}
    texts: list[str] = []
    if init:
        texts.append(init)
    for s in steps:
        if not isinstance(s, dict):
            continue
        e = str(s.get('E', '')).strip()
        f = str(s.get('F', '')).strip()
        if e.startswith('APV') and f in ('cmd_config', 'cmds_config') or e == 'test_env':
            g = str(s.get('G', '') or '')
            row_key = (e, f, g)
            if e.startswith('APV') and excluded[row_key] > 0:
                excluded[row_key] -= 1
                continue
            texts.append(g)
    hit: list[str] = []
    if blind:
        for t in texts:
            for m in _ip_re.finditer(t):
                ip = m.group(1)
                if ip in blind and ip not in hit:
                    hit.append(ip)
    if blind6:
        for t in texts:
            for lit, _addr in facts._iter_ipv6_literals(t):
                if _norm6(lit) in blind6 and lit not in hit:
                    hit.append(lit)
    allow = set(facts.listener_ips()) | set(facts.service_ips())
    allow6 = {n for n in (_norm6(x) for x in facts.listener_ips6() + facts.service_ips6()) if n}
    _tgt_re = _re.compile('@(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})|://(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})')
    _tgt6_re = _re.compile('(?:@|://)\\[?([0-9A-Fa-f:.]+)\\]?')
    bad_target: list[str] = []
    if facts.listener_ips():
        for s in steps:
            if not isinstance(s, dict) or str(s.get('E', '')).strip() != 'test_env':
                continue
            for m in _tgt_re.finditer(str(s.get('G', '') or '')):
                ip = m.group(1) or m.group(2)
                if ip and ip not in allow and (ip not in bad_target):
                    bad_target.append(ip)
    if facts.listener_ips6():
        for s in steps:
            if not isinstance(s, dict) or str(s.get('E', '')).strip() != 'test_env':
                continue
            for m in _tgt6_re.finditer(str(s.get('G', '') or '')):
                tok = m.group(1)
                if tok.count(':') < 2:
                    continue
                n6 = _norm6(tok)
                if n6 and int(_ipaddr.IPv6Address(n6)) != 0 and (n6 not in allow6) and (tok not in bad_target):
                    bad_target.append(tok)
    author_hit = [ip for ip in hit if normalize_ip_literal(ip) in author_set]
    invented_hit = [ip for ip in hit if ip not in author_hit]
    author_bad = [ip for ip in bad_target if normalize_ip_literal(ip) in author_set]
    invented_bad = [ip for ip in bad_target if ip not in author_bad]
    findings_out.update({'blind_hits': list(hit), 'bad_targets': list(bad_target), 'author_blind_hits': author_hit, 'author_bad_targets': author_bad, 'invented_blind_hits': invented_hit, 'invented_bad_targets': invented_bad, 'author_sourced_targets': sorted(set(author_hit) | set(author_bad))})
    if not invented_hit and (not invented_bad):
        return None
    listener = facts.listener_ips() + facts.listener_ips6()
    lines = [f'case {autoid} trigger reachability is illegal:']
    if invented_hit:
        lines.append(f"- listener/VIP or dig/curl target falls in an APV interface segment the trigger hosts cannot reach: {', '.join(invented_hit)}")
    if invented_bad:
        lines.append(f"- dig/curl target IP is not a ★ reachable listener of the testbed (nor a known backend): {', '.join(invented_bad)} (most likely made up)")
    lines.append(f"dig/curl targets must use a ★ reachable listener IP (consistent with the configured listener): {', '.join(listener)}")
    return '\n'.join(lines) + '\n\n' + facts.summary_for_agent()

def _trigger_reachability_findings(autoid: str, steps: list, init: str='', *, blocks: list | None=None, reachability_scope: ReachabilityScope | dict | None=None, author_ip_literals: Sequence[str] | None=None) -> dict:
    """触发可达性规则的结构化结果:硬拒原文 + 作者出处豁免的命中值,同一判据一次算出。"""
    findings: dict = {}
    message = _gate_unreachable_listener(autoid, steps, init=init, blocks=blocks, reachability_scope=reachability_scope, author_ip_literals=author_ip_literals, findings_out=findings)
    findings['message'] = message
    return findings

def _driver_reachability_findings(autoid: str, steps: list, *, author_ip_literals: Sequence[str] | None=None) -> dict:
    """驱动侧路径规则的结构化结果:硬拒违例 + 作者出处豁免呈报,同一判据一次算出。"""
    from cex_core.engine.ist_core.tools.device.structural_gate import StructuralResult, _check_driver_no_declared_path
    result = StructuralResult()
    author_hits: list[dict] = []
    _check_driver_no_declared_path(steps if isinstance(steps, list) else [], result, author_ip_literals=author_ip_literals, author_hits=author_hits)
    return {'violations': [{'code': v.code, 'detail': v.detail, 'step_index': v.step_index} for v in result.violations], 'author_sourced': author_hits, 'author_sourced_targets': sorted({str(item['target']) for item in author_hits})}

def _gate_driver_reachability(autoid: str, steps: list, *, author_ip_literals: Sequence[str] | None=None) -> str | None:
    """驱动侧路径规则:测试驱动到目标 IP 无声明路径 ⇒ 编译期证伪(2026-08-14 用户裁决)。

    与 `_gate_unreachable_ips`(IP∈拓扑声明集,防编造地址)、`_gate_unreachable_listener`
    (目的段里有没有**任何**触发设备)并排的第三道可达性规则——前两道都不判「**这台**执行体
    自己有没有路」,<batch> 真机批因此漏放 4 案(<case> v6 空返回、<case> 'network
    unreachable'、<case>/<case> client 十秒零输出),归因层误判环境阻塞、烧掉真机轮次。
    判据核心=`env_facts.driver_path_verdict`(共享声明网段 v4 子网/v6 前缀,或显式路由
    声明;现版拓扑无 routes 字段=按直连判);步骤扫描与作用面收窄(仅断言消费回包的驱动
    步)复用 `structural_gate._check_driver_no_declared_path` 本体——同一条规则在起草期
    (lint_draft)与落卷期(本规则)各问一次,不重写第二遍。无 env 级开关(§2.8);
    床事实取不到即抛(批入口已排除,见 `require_env_facts`),routes 字段不可解释仍按
    直连判(那是「这份拓扑没声明路由」,不是「没有拓扑」)。

    ``author_ip_literals``(2026-09-08,T5 扩展):作者亲笔写的目标、且床上没有任何驱动
    与它同段时,判据本体改落呈报而不是违例——本规则据此不拒,由上游落环境执行披露。
    作者写的目标若有别的驱动够得着,仍是执行体选错,照旧拒。
    """
    findings = _driver_reachability_findings(autoid, steps, author_ip_literals=author_ip_literals)
    if not findings['violations']:
        return None
    from cex_core.engine.ist_core.tools._shared.env_facts import require_env_facts
    facts = require_env_facts()
    lines = [f'case {autoid} has an assertion-consumed query whose executor has no declared path to the target (falsified at compile time, before any device round):']
    for v in findings['violations']:
        loc = f"step[{v['step_index']}] " if v['step_index'] >= 0 else ''
        lines.append(f"- {loc}{v['detail']}")
    return '\n'.join(lines) + '\n\n' + facts.summary_for_agent()
_EMIT_REASON_PATTERNS = (('组合子无效', 'blocks_invalid'), ('invalid blocks combinator', 'blocks_invalid'), ('provenance 解析失败', 'prov_parse'), ('provenance parse failed', 'prov_parse'), ('provenance steps 数', 'prov_shape'), ('必传 provenance', 'prov_missing'), ('G 列为 None', 'payload_empty'), ('column G is None', 'payload_empty'), ('解析失败', 'parse'), ('parse failed', 'parse'), ('违反结构约束', 'structural'), ('violates structural constraints', 'structural'), ('违反用户决策', 'user_decision'), ('violates user decision', 'user_decision'), ('frozen', 'frozen'), ('冻结', 'frozen'), ('lint', 'lint'))

def _evidence_search_roots() -> list[Path]:
    """引用证据的候选搜索根。

    2026-08-01 修:旧版只认 `vendor_stdlib.source_dir`(实测=
    `knowledge/data/markdown/product/manual_10.5`,只含 CLI 手册章节),而 worker
    合法引用的产品规格文档在**上一层** `knowledge/data/markdown/product/`——
    文件在、引用对、规则看错地方,报 `evidence ref unreadable`。<run> 实证:
    <case> 连改 3 次路径写法全败(而本函数只用 basename,改路径不可能有用),叠加
    轮次封顶漏洞一路重试到批末,最后被误归类成「手册问题」(真相是本 bug)。
    候选根限定在 knowledge/data/ 只读知识库子树内。

    规格书根必须由同一次活动代际解析取得；禁止回退到
    `knowledge/data/spec/*.md` 静态路径，否则指针切换时会把 docs/index 混代。

    顺序只为可复现搜索，不是真值权重。同一 basename 跨根同时命中
    时由读取函数显式报歧义，绝不取“第一个”自动吞掉反证。"""
    root = _cex_data_path('')
    from cex_core.engine.knowledge_paths import resolve_active_spec_generation
    from cex_core.engine.case_compiler.vendor_stdlib import manual_source_dir
    active_spec = resolve_active_spec_generation(root)
    primary = manual_source_dir()
    candidates = [active_spec.docs, *([primary, primary.parent] if primary is not None else []), root / 'knowledge/data/markdown', root / 'knowledge/data/markdown/product']
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out
_EVIDENCE_REF_RE = re.compile('[^,]+?\\.md\\s*:\\s*\\d+(?:\\s*-\\s*\\d+)?', re.IGNORECASE)

def _norm_name_key(name: str) -> str:
    """文件名比对键:各类空白折成一个普通空格 + 大小写折叠。"""
    return re.sub('\\s+', ' ', str(name or '').replace('\xa0', ' ')).strip().casefold()

def _read_evidence_window(ref: str) -> tuple[str, str, str]:
    """解析一条 `<file>.md:<line>` 或 `<file>.md:<start>-<end>` 引用
    → (窗口文本, 错因, 命中根类别 "spec"|"manual")。

    成功返回 (窗口小写文本, "", 根类别);失败返回 ("", 人可读错因——**必须披露
    搜索根**,否则调用方只能继续猜路径,实证浪费 5 次尝试, "")。行号支持单行与
    区间两形态(<case> 写过 `268-270`,旧版 `int()` 直接抛)。

    根类别只供终态 claim 保留来源 basis:无论命中 SPEC 还是手册,
    build 绑定 XML 未收录都是上机前终态拒卷;文档引用不放行、不转人裁。"""
    fname, _, lno = ref.rpartition(':')
    base = Path(fname).name
    try:
        roots = _evidence_search_roots()
    except Exception as exc:
        return ('', f'evidence ref unreadable: active spec generation unavailable ({exc})', '')
    repo_root = _cex_data_path('')
    spec_root = roots[0]
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import load_vendor_stdlib as _lvs
        _srcdir = str((_lvs() or {}).get('source_dir') or 'knowledge/data/manual')
    except Exception:
        _srcdir = 'knowledge/data/manual'
    cli_manual_roots = (repo_root / _srcdir,)
    target: Path | None = None
    words = re.split('[ \xa0\u3000]', base)
    candidates = [' '.join(words[k:]).strip() for k in range(len(words))]
    for cand_name in candidates:
        if not cand_name:
            continue
        hits = [d / cand_name for d in roots if (d / cand_name).is_file() and (not (d / cand_name).is_symlink())]
        if len(hits) > 1:
            return ('', f'evidence ref ambiguous: {ref} — file name {cand_name!r} exists in multiple independent evidence roots; cite a source identity/receipt and reconcile the claims instead of relying on search order (hits: ' + ' | '.join((str(item) for item in hits)) + ')', '')
        if len(hits) == 1:
            target = hits[0]
            break
    if target is None:
        for cand_name in candidates:
            if not cand_name:
                continue
            key = _norm_name_key(cand_name)
            hits = [p for d in roots for p in d.glob('*.md') if _norm_name_key(p.name) == key and (not p.is_symlink())]
            if len(hits) > 1:
                return ('', f'evidence ref ambiguous: {ref} — whitespace-normalized file name matches multiple independent evidence roots (hits: ' + ' | '.join((str(item) for item in hits)) + ')', '')
            if len(hits) == 1:
                target = hits[0]
                break
    if target is None:
        tried = ' | '.join((str(d) for d in roots))
        return ('', f'evidence ref unreadable: {ref} — no file named {base!r} under any evidence root (searched: {tried}). Only the file NAME is used; the path prefix you write is ignored, so rewriting the prefix cannot help — check the file name and that it lives in the read-only knowledge tree.', '')
    if spec_root in target.parents:
        root_kind = 'spec'
    elif any((r in target.parents for r in cli_manual_roots)):
        root_kind = 'cli_manual'
    else:
        root_kind = 'product_doc'
    m = re.fullmatch('\\s*(\\d+)\\s*(?:-\\s*(\\d+)\\s*)?', lno or '')
    if not m:
        return ('', f'evidence ref unreadable: {ref} — line part {lno!r} must be `<line>` or `<start>-<end>`', '')
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    if end < start:
        start, end = (end, start)
    try:
        lines = target.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        return ('', f'evidence ref unreadable: {ref} — {type(exc).__name__} on {target}', '')
    return ('\n'.join(lines[max(0, start - 4):end + 3]).lower(), '', root_kind)

def _verify_command_evidence(evidence: str, missing_cmds: list[str]) -> tuple[bool, str, str]:
    """机械核验存在性旁证。

    ① `<file>.md:<line>`(可多个,逗号/空格分隔;行号也可写 `<start>-<end>` 区间)
      ——该行 ±3 行内须含对应命令前两个词(每条 miss 至少被一个引用覆盖);
    ② `dev_help: <一句>`——只识别为未核实 device_attestation，原文进入 claim，
      不签发 XML 存在性，也不放行。

    **只用文件名解析,路径前缀无关**;搜索根见 `_evidence_search_roots()`。

    多条引用只以**逗号**分隔:文件名本身可以含空格(规格书 135/663 份含空格),
    按空白切词会把这类文件名切碎、任何一份都引不到。"""
    ev = (evidence or '').strip()
    if ev.lower().startswith('dev_help:'):
        return (False, f'device attestation no longer grants passage — the command tree is the authority for whether a command exists. The statement is retained only as an unverified claim. (recorded: {ev[:100]})', 'device_attestation')
    refs = [m.group(0).strip() for m in _EVIDENCE_REF_RE.finditer(ev)]
    if not refs:
        return (False, 'evidence must be `<file>.md:<line>` (manual line ref)', '')
    windows: list[str] = []
    kinds: set[str] = set()
    for r in refs:
        window, err, root_kind = _read_evidence_window(r)
        if err:
            return (False, err, '')
        windows.append(window)
        kinds.add(root_kind)
    for cmd in missing_cmds:
        toks = re.sub('\\s+', ' ', cmd.strip().lower()).split(' ')[:2]
        if not any((all((t in w for t in toks)) for w in windows)):
            return (False, f'evidence does not cover command {cmd!r} — the referenced line vicinity must actually contain its leading words', '')
    if 'spec' in kinds:
        kind = 'spec'
    elif 'product_doc' in kinds:
        kind = 'product_doc'
    else:
        kind = 'cli_manual'
    return (True, f'{kind} line evidence verified for {len(missing_cmds)} command(s)', kind)

def _first_token(line: str) -> str:
    s = (line or '').strip()
    return s.split(None, 1)[0] if s else ''

def _atlas_method_signature(token: str) -> dict | None:
    """T1(SPEC 内部任务 §1)辅助:token 是否命中 atlas 的 direct_method_call
    方法名集(apv_full 四个 mixin family 之一)——只在"确认命中"方向可靠
    (atlas 是登记的事实,S1 表注:命中⇒它确实是方法;未命中⇒什么都推不出)。
    apv_lang 不可达/atlas 不可达/名字确实不在里面,一律返回 `None`——调用方
    据此继续走 T2→T3→T4/T5 的既有判定,不能把 `None` 读成"确认不是方法调用"。

    fail-soft 故意不牵连 `_gate_command_existence` 的主判定:T1 只是诊断增强
    (把一条本来就会呈报的 miss 换个更准的说法),不是这条规则存在的理由——
    command_inventory 才是;apv_lang 查不到不该让整条规则连带瘫痪。"""
    if not token:
        return None
    try:
        from cex_core.engine.case_compiler.apv_lang import QueryUnavailable, capability_signature
    except Exception:
        return None
    try:
        sig = capability_signature(token)
    except QueryUnavailable:
        return None
    if sig is None:
        return None
    return {'name': token, **sig}

def _confirmation_trigger_hint(prev_cmds: list[str]) -> str:
    """T2(SPEC 内部任务 §1)辅助:若紧邻前一条命令的首词命中 内部任务 的
    confirmation-prompt 投影(`confirmation_prompt_patterns.json`,11 条真实
    lib/ 序列之一),直接引用真实出处(文件:行号+步数);查不到时退回通用
    指路。两种情况下都点名 `lang_query(kind='prompt_pattern')`/
    `confirmation_prompt_of`,不是一句"这不是命令"就完事——内部工单 的机制才是
    正确出口,诊断要把 worker 指到那条路上。"""
    prev_tok = _first_token(prev_cmds[-1]) if prev_cmds else ''
    if prev_tok:
        entry = None
        try:
            from cex_core.engine.case_compiler.apv_lang import QueryUnavailable, confirmation_prompt_of
            try:
                entry = confirmation_prompt_of(prev_tok)
            except QueryUnavailable:
                entry = None
        except Exception:
            entry = None
        if entry is not None:
            p = entry['provenance']
            return f"the immediately preceding line ({prev_tok!r}) matches a known confirmation-prompt trigger recorded at {p['file']}:{p['def_line']} ({len(entry['steps'])}-step sequence) — query lang_query(kind='prompt_pattern', name={prev_tok!r}) for the exact steps; the answer belongs inside that call's own prompt/steps, not as an independent cmd_config/cmds_config line"
    return "per 内部任务, confirmation-prompt responses belong inside the *triggering* call's own step sequence — query lang_query(kind='prompt_pattern', name=<the method that should have triggered this prompt>), or see knowledge/data/compile_ref/confirmation_prompt_patterns.json for the real trigger+response sequences; this should not be a standalone cmd_config/cmds_config line"

def _build_line_shape_block(method_hits: list[tuple[str, dict]], confirm_hits: list[tuple[str, str]], chinese_hits: list[str]) -> str:
    """SPEC 内部任务 §1(T1/T2/T3 命中的合并出口)。

    这三类问题**不是**"命令在手册里查不到"——是"这一行根本不该被当命令行
    读"。故意不走 command_existence 的 XML 终态审计账：这里不是“树里没有”，
    而是**确定性**的结构写错位置，worker 自己就能修，不需要存在性旁证或用户裁决。
    §2 的代价不对称对这三类同样成立(方向都是:宁可多拦一次、不可漏放一次)
    ——三类都硬拒 emit,不落 case.xlsx/凭证,措辞刻意不出现"not found"/
    "does not exist"字样(S1b:这是关于我们读到了什么**形态**的陈述,不是
    关于设备的断言——那个判断留给真正的 command_existence XML 硬规则，见下方
    T5 分支不受影响)。"""
    lines = ['error: command-line-shape gate — the following G-column line(s) were written as raw cmd_config/cmds_config text but are not CLI command syntax. Each is a structural misroute (wrong column, or wrong dispatch mechanism) that must be fixed before this batch can even be checked for real CLI commands:']
    if method_hits:
        lines.append(f'\n<misplaced_method_call n={len(method_hits)}>')
        lines.append("Framework method call written as command text. Move it to the F column (F=<method name>, G=<comma-separated arguments>); do not put it in cmd_config/cmds_config G text. Signature is the atlas's, not a guess (lang_query(kind='signature', name=<method>) gives the same answer at draft time):")
        for cmd, sig in method_hits:
            lines.append(f"  - {cmd!r} -> F={sig['name']!r}, required={sig['required']}, optional={sig['optional']} (source: {sig['source']})")
        lines.append('</misplaced_method_call>')
    if confirm_hits:
        lines.append(f'\n<confirmation_prompt_answer n={len(confirm_hits)}>')
        lines.append("This looks like a confirmation-prompt response (bare yes/no/y/n, or `prompt=...`), not a command. Task#100's mechanism embeds the answer sequence inside the triggering call itself, not as a separate line:")
        for cmd, hint in confirm_hits:
            lines.append(f'  - {cmd!r} — {hint}')
        lines.append('</confirmation_prompt_answer>')
    if chinese_hits:
        lines.append(f'\n<execute_action_description n={len(chinese_hits)}>')
        lines.append("This looks like an execute-action description (Chinese-led text, or an `execute:`/`execute：` prefix) written as command text. Move it to F=execute, G=<the exact registered action name>：<payload>. The action names come from the generated contract: lang_query(kind='contract', domain=<this row's E value>, name='execute') lists every action registered for that object, each with its exact name, enablement status and payload grammar. Two places that cannot answer this: lang_query(kind='nearest', …) ranks column-F method names and holds no action names, and EXCEL_FUNCTIONS.md states that it carries no action list:")
        for cmd in chinese_hits:
            lines.append(f'  - {cmd!r}')
        lines.append('</execute_action_description>')
    lines.append('\nFix these lines and re-emit. This gate does not record a needs_decision entry for any of the above — they are deterministic authoring mistakes you can correct yourself, not cases needing evidence or a user decision.')
    return '\n'.join(lines)

def _verified_precedent_commands(case) -> dict[str, list[dict]]:
    """把带真机 PASS + build 的先例来源投影到其命令行。

    F12 只允许这些字段改变报错说明，绝不改变 XML miss 的拒卷结论。旁挂损坏、
    先例未绑定 delivery PASS、build/OID 缺失时返回空映射，避免把“文件存在”
    冒充“该版本真机通过”。
    """
    registry_path = _cex_data_path('') / 'knowledge' / 'framework' / 'mirror_precedent_provenance.json'
    try:
        raw = registry_path.read_bytes()
        registry = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(registry, dict):
        return {}
    registry_sha256 = hashlib.sha256(raw).hexdigest()
    out: dict[str, list[dict]] = {}
    for step in getattr(case, 'steps', ()):
        source = getattr(step, 'source', None)
        if str(getattr(source, 'kind', '') or '') != 'precedent':
            continue
        receipt = getattr(source, 'receipt', None)
        ref = str(getattr(source, 'ref', '') or '')
        filename = Path(str((receipt or {}).get('path') or ref).split('#', 1)[0]).name
        entry = registry.get(filename)
        if not isinstance(entry, dict):
            continue
        delivery_pass = str(entry.get('ctx') or '') == 'delivery' and str(entry.get('result') or '') == 'pass' or ('result' not in entry and entry.get('provisional') is False)
        build = str(entry.get('build') or '').strip()
        oid_match = re.search('(?<!\\d)(\\d{18})(?!\\d)', filename + ' ' + ref)
        if not delivery_pass or not build or oid_match is None:
            continue
        evidence = {'source_filename': filename, 'oid': oid_match.group(1), 'build': build, 'verification': 'device_delivery_pass', 'registry_sha256': registry_sha256}
        commands = _ordered_apv_cmds([{'E': str(getattr(step, 'E', '') or ''), 'F': str(getattr(step, 'F', '') or ''), 'G': str(getattr(step, 'G', '') or '')}], '')
        for command in commands:
            out.setdefault(command, []).append(evidence)
    return out

def _worker_bound_capability_inventory() -> tuple[dict | None, dict | None, str]:
    """返回 worker 收据指定代际的单一 inventory；普通调用返回兼容空态。"""
    try:
        from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
        session = current_worker_device_session()
    except Exception:
        session = None
    if session is None:
        return (None, None, '')
    fields = {'bed': str(session.capability_bed or '').strip(), 'full_version': str(session.capability_full_version or '').strip(), 'version': str(session.capability_version or '').strip(), 'build': str(session.capability_build or '').strip(), 'generation_id': str(session.capability_generation_id or '').strip(), 'manifest_sha256': str(session.capability_manifest_sha256 or '').strip().lower(), 'projection_sha256': str(session.capability_projection_sha256 or '').strip().lower()}
    expected_bed = str(session.expected_bed or '').strip()
    if any((not value for value in fields.values())) or not expected_bed:
        return (None, None, 'engine-issued capability generation identity is incomplete')
    if fields['bed'] != expected_bed:
        return (None, None, 'engine-issued capability bed identity does not match execution bed')
    try:
        from cex_core.engine.sync.command_tree_sync import parse_build_identity, resolve_command_tree_generation
        from cex_core.engine.case_compiler.vendor_stdlib import _build_suffix, load_vendor_stdlib_generation
        identity = parse_build_identity(fields['full_version'])
        if identity.inventory_version != fields['version'] or identity.build != fields['build'] or _build_suffix(session.expected_build) != fields['build']:
            return (None, None, 'engine-issued capability version/build identity is inconsistent')
        store_root = _sh.project_root() / 'runtime' / 'command_tree'
        generation = resolve_command_tree_generation(product=identity.product, platform=identity.platform, version=fields['version'], device_build=fields['build'], generation_id=fields['generation_id'], manifest_sha256=fields['manifest_sha256'], store_root=store_root)
        if generation.full_version != fields['full_version']:
            return (None, None, 'engine-issued capability full-version identity drifted')
        if generation.projection_sha256 != fields['projection_sha256']:
            return (None, None, 'engine-issued capability projection identity drifted')
        inventory = load_vendor_stdlib_generation(product=identity.product, platform=identity.platform, version=fields['version'], device_build=fields['build'], generation_id=fields['generation_id'], manifest_sha256=fields['manifest_sha256'], store_root=store_root)
        if inventory is None:
            return (None, None, 'engine-issued capability generation could not be loaded')
        return (inventory, {'schema': 'ist.capability_consumed', 'bed': fields['bed'], 'full_version': fields['full_version'], 'product': identity.product, 'platform': identity.platform, 'version': fields['version'], 'build': fields['build'], 'generation_id': fields['generation_id'], 'manifest_sha256': fields['manifest_sha256'], 'projection_sha256': fields['projection_sha256']}, '')
    except Exception as exc:
        logger.error('worker capability generation sealing failed', exc_info=True)
        return (None, None, f'engine-issued capability generation could not be sealed ({type(exc).__name__})')
COMMAND_EXISTENCE_VERDICT_SCHEMA = 'ist.command-existence-verdict'
COMMAND_NOT_IN_TREE_CODE = 'command_not_in_tree'
COMMAND_PARAMETER_CONTRACT_CODE = 'command_parameter_contract'

class CommandExistenceVerdict(TypedDict):
    """Python 内部直接传递的 JSON-native 三值结构；只在落盘/工具边界序列化。"""
    schema: Literal['ist.command-existence-verdict']
    kind: Literal['hit', 'missing', 'tree_unavailable']
    command: str
    decided: bool
    hit: bool
    head: str
    src: str
    version: str
    device_build: str
    origin: str
    reason_code: str
    parameters_valid: bool
    parameter_error: dict
    results: list
    detail: str
XML_ABSENT_CATALOG_UNAVAILABLE = 'xml_absent_catalog_unavailable'

def _manual_version_from_full_version(full_version: str) -> str:
    """手册 catalog 版本目录 = 设备完整自述的前三个数字段；解析不出返回 ""。

    严格身份（``Sample Build 10.5.0``）经 ``parse_build_identity``
    取 release；配置/清单里亦有点分数字形态（``10.5.0.585``）。短尾号（``585``）
    与 major.minor（``10.5``）一律 ""——第三段没有就是没有，不猜、不模糊匹配目录。
    """
    value = str(full_version or '').strip()
    if not value:
        return ''
    release = ''
    try:
        from cex_core.engine.sync.command_tree_sync import parse_build_identity
        release = parse_build_identity(value).release
    except Exception:
        if re.fullmatch('\\d+(?:\\.\\d+)+', value):
            release = value
    parts = release.split('.')
    if len(parts) < 3 or any((not part.isdigit() for part in parts[:3])):
        return ''
    return '.'.join(parts[:3])

def _manual_catalog_location(*, device_build: str='') -> tuple[str, Path | None]:
    """(手册版本, 手册根) 的唯一解析点；测试 monkeypatch 本缝植入 catalog。

    生产路径 root 恒 ``None``（store 默认根）；版本沿密封身份链取：
    ① 调用方下传的完整设备自述（worker 执行身份/探针）；
    ② worker 会话的 ``capability_full_version``——密封路径已与代际 manifest
       对账（`_worker_bound_capability_inventory`），即 emit 密封用的
       ``fields["full_version"]``；
    ③ 维护路径的配置身份完整串（与 loader 绑定投影同轴同源）。
    三处都取不到 ⇒ ``("", None)``，catalog 视图不可用，措辞走
    ``xml_absent_catalog_unavailable``（仍 missing，不猜手册有没有）。
    """
    version = _manual_version_from_full_version(device_build)
    if version:
        return (version, None)
    try:
        from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
        session = current_worker_device_session()
    except Exception:
        session = None
    if session is not None:
        version = _manual_version_from_full_version(getattr(session, 'capability_full_version', ''))
        if version:
            return (version, None)
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import configured_device_os_build_identity
        version = _manual_version_from_full_version(configured_device_os_build_identity())
    except Exception:
        version = ''
    return (version, None) if version else ('', None)

def _manual_catalog_claims(*, device_build: str='') -> tuple[dict[str, dict], str]:
    """cli+app 两族 catalog 合并的 claim 视图。

    返回 ``(claims, unavailable_reason)``。``unavailable_reason`` 非空表示
    catalog 取不到——不得把空 dict 当成「查了、手册没有」。fail-closed 的单族
    不进视图；两族都取不到才是 unavailable。
    """
    version, root = _manual_catalog_location(device_build=device_build)
    if not version:
        return ({}, 'manual catalog version could not be resolved from device identity')
    try:
        from cex_core.engine.kms import manual_catalog_store
        claims: dict[str, dict] = {}
        family_failures: list[str] = []
        loaded_any = False
        for family in ('cli', 'app'):
            view, verdict = manual_catalog_store.manual_claims_view(version, family, root=root)
            if verdict['status'] != 'ok':
                family_failures.append(f"{family}:{verdict.get('status') or 'unavailable'}")
                continue
            loaded_any = True
            for head, entry in view.items():
                claims.setdefault(head, entry)
        if not loaded_any:
            why = ', '.join(family_failures) or 'no family loaded'
            return ({}, f'manual catalog claim view is unavailable ({why})')
        return (claims, '')
    except Exception as exc:
        logger.error('手册 catalog claim 视图解析失败', exc_info=True)
        return ({}, f'manual catalog claim view could not be parsed ({type(exc).__name__}: {exc})')

def _unpack_command_tree_context(ctx: tuple) -> tuple[object | None, dict | None, dict[str, dict], str, str]:
    vendor, inv, claims, tree_detail, *rest = ctx
    catalog_detail = str(rest[0] or '') if rest else ''
    return (vendor, inv, claims if isinstance(claims, dict) else {}, tree_detail, catalog_detail)

def _command_tree_context(*, device_build: str='', inventory: dict | None=None) -> tuple[object | None, dict | None, dict[str, dict], str, str]:
    """命令树模块/投影的唯一加载与最小结构校验点。

    第三元是手册 catalog claim 视图——与投影同点一次性解析（catalog 不按
    verdict 逐条重读；store 内部按 catalog sha 缓存视图推导），供 missing
    措辞走查消费。第五元是 catalog 取不到的 why-unknown；空串表示已经查过。
    加载失败的早退路径 claims 配 {}，catalog 原因配空（存在性已是 tree_unavailable）。
    """
    try:
        import importlib
        vendor = importlib.import_module('cex_core.engine.case_compiler.vendor_stdlib')
    except Exception as exc:
        logger.error('命令树投影模块导入失败', exc_info=True)
        return (None, None, {}, f'command-tree projection module could not be imported ({type(exc).__name__}: {exc})', '')
    try:
        loaded = inventory if inventory is not None else vendor.load_vendor_stdlib(device_build=device_build)
    except Exception as exc:
        logger.error('命令树投影加载失败', exc_info=True)
        return (vendor, None, {}, f'command-tree projection could not be loaded ({type(exc).__name__}: {exc})', '')
    if loaded is None:
        return (vendor, None, {}, 'command-tree projection is unavailable', '')
    if not isinstance(loaded, dict):
        return (vendor, None, {}, 'command-tree projection root is not an object', '')
    heads = loaded.get('heads')
    headers = loaded.get('headers')
    if not isinstance(heads, dict) or not isinstance(headers, dict):
        return (vendor, None, {}, 'command-tree projection is structurally invalid: heads/headers must be objects', '')
    if any((not isinstance(head, str) or not isinstance(entry, dict) for head, entry in heads.items())):
        return (vendor, None, {}, 'command-tree projection is structurally invalid: every head must map to an object', '')
    claims, catalog_unavailable = _manual_catalog_claims(device_build=device_build)
    return (vendor, loaded, claims, '', catalog_unavailable)

def command_existence_verdict(command: str, *, device_build: str='', inventory: dict | None=None, _loaded_context: tuple | None=None) -> CommandExistenceVerdict:
    """以 build 绑定 XML 命令树签发 ``hit/missing/tree_unavailable`` 唯一判据。"""
    cmd = str(command or '').strip()
    vendor, inv, manual_claims, unavailable_detail, catalog_unavailable = _unpack_command_tree_context(_loaded_context if _loaded_context is not None else _command_tree_context(device_build=device_build, inventory=inventory))
    if vendor is None or inv is None:
        return {'schema': COMMAND_EXISTENCE_VERDICT_SCHEMA, 'kind': 'tree_unavailable', 'command': cmd, 'decided': False, 'hit': False, 'head': '', 'src': '', 'version': '', 'device_build': str(device_build or ''), 'origin': '', 'reason_code': 'tree_unavailable', 'parameters_valid': False, 'parameter_error': {}, 'results': [], 'detail': unavailable_detail}
    base = {'schema': COMMAND_EXISTENCE_VERDICT_SCHEMA, 'command': cmd, 'version': str(inv.get('version') or ''), 'device_build': str(inv.get('device_os_build') or device_build or '')}
    tokens = vendor.norm_command_tokens(cmd)
    candidate = vendor._head_candidate(tokens, inv['headers'])
    if candidate is not None:
        head, entry, remainder = candidate
        origin = str(entry.get('origin') or '')
        parameter_error = vendor._parameter_contract_error(remainder, entry)
        return {**base, 'kind': 'hit', 'decided': True, 'hit': True, 'head': head, 'src': str(entry.get('src') or ''), 'origin': origin, 'reason_code': 'parameter_contract_violation' if parameter_error is not None else '', 'parameters_valid': parameter_error is None, 'parameter_error': dict(parameter_error or {}), 'results': list(entry.get('results') or []), 'detail': 'command head exists but its arguments violate the XML contract' if parameter_error is not None else ''}
    candidate = vendor._head_candidate(tokens, manual_claims)
    if candidate is None:
        if catalog_unavailable:
            return {**base, 'kind': 'missing', 'decided': True, 'hit': False, 'head': '', 'src': '', 'origin': '', 'reason_code': XML_ABSENT_CATALOG_UNAVAILABLE, 'parameters_valid': False, 'parameter_error': {}, 'results': [], 'detail': 'command head is absent from the build-bound XML command tree; manual catalog wording could not be confirmed: ' + catalog_unavailable}
        return {**base, 'kind': 'missing', 'decided': True, 'hit': False, 'head': '', 'src': '', 'origin': '', 'reason_code': XML_COMMAND_NOT_FOUND, 'parameters_valid': False, 'parameter_error': {}, 'results': [], 'detail': 'command head is absent from the build-bound XML command tree'}
    head, entry, remainder = candidate
    origin = str(entry.get('origin') or '')
    parameter_error = vendor._parameter_contract_error(remainder, entry)
    return {**base, 'kind': 'missing', 'decided': True, 'hit': False, 'head': head, 'src': str(entry.get('src') or ''), 'origin': origin, 'reason_code': 'xml_absent_manual_only', 'parameters_valid': parameter_error is None, 'parameter_error': dict(parameter_error or {}), 'results': list(entry.get('results') or []), 'detail': 'command is declared outside the XML tree but absent from XML headers'}

def build_command_tree_resolver(*, device_build: str='', inventory: dict | None=None) -> tuple[object, dict, 'callable']:
    """一次加载 build 绑定命令树，返回 ``(vendor, inv, resolve)``。

    存在的理由是**单谓词纪律**：`command_existence_verdict` 全仓只许两个模块
    直接调用（守门 `test_command_existence_gate::test_existence_predicate_has_
    exactly_two_consumer_modules`），而 2026-08-14 起「编写之前的 ③ 静态扫描」
    多了一个消费点。它拿的不是自己的判据，而是**本函数交出来的同一个 resolve**
    ——判据仍只有一份，调用方也仍只有这两个模块。

    投影不可得直接抛 ``CommandTreeUnavailable``（引擎错误 0008 的入口），
    绝不静默回落成「设备不支持这个功能」——那会把引擎故障说成用户输入问题。
    """
    from cex_core.engine.ist_core.compile_engine.engine_errors import CommandTreeUnavailable
    loaded_context = _command_tree_context(device_build=device_build, inventory=inventory)
    vendor, inv, _manual_claims, unavailable_detail, _catalog_unavailable = _unpack_command_tree_context(loaded_context)
    if vendor is None or inv is None:
        raise CommandTreeUnavailable(unavailable_detail, device_build=str(device_build or ''))

    def _resolve(command: str) -> CommandExistenceVerdict:
        verdict = command_existence_verdict(command, device_build=device_build, _loaded_context=loaded_context)
        if verdict['kind'] == 'tree_unavailable':
            raise CommandTreeUnavailable(verdict['detail'], device_build=verdict['device_build'] or device_build)
        return verdict
    return (vendor, inv, _resolve)
_SHELL_WORDING_RE = re.compile('(?:^\\s*/|(?:^|\\s)(?:bash|sh|zsh|python\\d*|perl|ruby|systemctl|journalctl|netstat|ss|grep|awk|sed|cat|tail|head)\\b|\\|\\||&&|[|;]|`|\\$\\()', re.IGNORECASE)

def _looks_like_shell(command: str) -> bool:
    """只选择拒绝话术；绝不参与 ``hit/missing`` 判定。"""
    return bool(_SHELL_WORDING_RE.search(str(command or '')))
ENGINE_DEFECT_GATE_ASSERTION_BINDING = 'assertion_binding'
ENGINE_DEFECT_CODE_MUTATION_CONTROL_BINDING = 'mutation_control_binding'
_CURRENT_ENGINE_DEFECT: ContextVar[dict | None] = ContextVar('ist_current_engine_defect', default=None)

@contextlib.contextmanager
def engine_defect_channel():
    """引擎调用方开一次带外槽,收本次 `compile_emit` 的引擎缺陷分类。

    用法(唯一消费点 `compile_engine.nodes.emit`)::

        with engine_defect_channel() as slot:
            res = compile_emit.func(aid, ...)
        defect = read_engine_defect(slot, aid)

    槽是 per-call 的:`with` 退出即复位 ContextVar,上一次调用的信号漏不到下一次。
    没有调用方开槽时铸造点写空(普通维护调用、`compile_emit_merged` 都属这类),
    分类回落到「产者可控」——与本通道落地之前的行为一致,不是新的静默失败。
    """
    slot: dict = {}
    token = _CURRENT_ENGINE_DEFECT.set(slot)
    try:
        yield slot
    finally:
        _CURRENT_ENGINE_DEFECT.reset(token)

def _signal_engine_defect(autoid: str, gate: str, code: str, *, proof=None) -> None:
    """铸造点往带外槽里写分类;没有调用方开槽就什么都不做。"""
    slot = _CURRENT_ENGINE_DEFECT.get()
    if slot is None:
        return
    slot.clear()
    slot.update({'autoid': str(autoid or '').strip(), 'gate': str(gate), 'code': str(code), 'proof': proof})

def read_engine_defect(slot: dict | None, autoid: str) -> dict | None:
    """读带外槽;槽空或案身份对不上返回 None。

    案身份自检:一个槽只服务一次单案 `compile_emit`,写进来的案与问的案不一致
    只可能是引擎自己接线接错了。那种情况下宁可当没有信号(回落产者可控、照旧烧
    一轮),也不能拿另一个案的分类去把整批停掉——整批停会连带作废健康兄弟案。
    """
    if not slot:
        return None
    if str(slot.get('autoid') or '') != str(autoid or '').strip():
        logger.error('引擎缺陷带外槽的案身份与调用方不一致:槽=%r 调用方=%r', slot.get('autoid'), autoid)
        return None
    return {'gate': str(slot.get('gate') or ''), 'code': str(slot.get('code') or ''), 'proof': slot.get('proof')}
MERGE_PRECHECK_REFUSAL_GATE_EXEMPT_GOVERNANCE = 'exempt_governance'
_CURRENT_MERGE_PRECHECK_REFUSAL: ContextVar[dict | None] = ContextVar('ist_current_merge_precheck_refusal', default=None)

@contextlib.contextmanager
def merge_precheck_refusal_channel():
    """引擎 merge 节点开一次带外槽,收本次 `precheck_merge_case` 的拒绝分类。

    用法(唯一消费点 `compile_engine.nodes.merge` 的预检循环)::

        with merge_precheck_refusal_channel() as slot:
            reason = precheck_merge_case(aid, out_name=out_name)
        refusal = read_merge_precheck_refusal(slot, aid)

    槽是 per-call 的:`with` 退出即复位 ContextVar,上一案的分类漏不到下一案。
    """
    slot: dict = {}
    token = _CURRENT_MERGE_PRECHECK_REFUSAL.set(slot)
    try:
        yield slot
    finally:
        _CURRENT_MERGE_PRECHECK_REFUSAL.reset(token)

def _signal_merge_precheck_refusal(autoid: str, gate: str, code: str, *, detail: dict | None=None) -> None:
    """拒绝发生点往带外槽里写分类;没有调用方开槽就什么都不做。"""
    slot = _CURRENT_MERGE_PRECHECK_REFUSAL.get()
    if slot is None:
        return
    slot.clear()
    slot.update({'autoid': str(autoid or '').strip(), 'gate': str(gate), 'code': str(code), 'detail': dict(detail or {})})

def read_merge_precheck_refusal(slot: dict | None, autoid: str) -> dict | None:
    """读带外槽;槽空或案身份对不上返回 None(案身份自检同 `read_engine_defect`)。"""
    if not slot:
        return None
    if str(slot.get('autoid') or '') != str(autoid or '').strip():
        logger.error('合卷预检拒绝带外槽的案身份与调用方不一致:槽=%r 调用方=%r', slot.get('autoid'), autoid)
        return None
    return {'gate': str(slot.get('gate') or ''), 'code': str(slot.get('code') or ''), 'detail': dict(slot.get('detail') or {})}

def _binding_steps_from_provenance(items: list) -> list[dict]:
    result = []
    if not isinstance(items, list) or any((not isinstance(item, dict) for item in items)):
        return []
    for index, item in enumerate(items):
        step = dict(item)
        step['produces_observation'] = bool(str(step.get('observation_id') or '').strip())
        step['expectation'] = str(step.get('G') or '')
        step['expectation_source_kind'] = str((step.get('source') or {}).get('kind') or '')
        step['provenance_step_index'] = index
        result.append(step)
    return result

def engine_inserted_binding_rejection(autoid: str, exc: Exception, mutation_receipt: dict | None, *, before_binding_steps: list | None=None, binding_steps: list | None=None) -> str:
    """复核补行前后绑定契约；只有原输入通过且新增行触发违例才签内部故障票据。

    观测名在mutation收据中只证明名义对应关系。缺少可复核的前后输入时，
    仅披露该关联与未核范围，不据此判断编写、引擎或设备责任。
    """
    from cex_core.engine.case_compiler.mutation_testing import compiler_inserted_observation_ids
    subject = str(getattr(exc, 'subject', '') or '')
    if not subject or subject not in compiler_inserted_observation_ids(mutation_receipt):
        return ''
    from cex_core.engine.ist_core.compile_engine.engine_checkpoints import check_engine_control_binding
    proof = None
    if before_binding_steps is not None and binding_steps is not None:
        proof = check_engine_control_binding(aid=autoid, before_binding_steps=before_binding_steps, binding_steps=binding_steps, mutation_receipt=mutation_receipt or {})
    if proof is None:
        return f'error: case {autoid} binding failure refers to {subject!r}, an identity listed in the mutation receipt. The before/after contract violation has not been verified.'
    _signal_engine_defect(autoid, ENGINE_DEFECT_GATE_ASSERTION_BINDING, ENGINE_DEFECT_CODE_MUTATION_CONTROL_BINDING, proof=proof)
    return f'error: case {autoid} binding accepted the original steps and rejected the engine-added control binding at {subject!r}; the before/after inputs and failure were independently replayed.'

def _gate_command_existence(autoid: str, steps: list, init: str='', evidence: str='', device_build: str='', precedent_passes: dict[str, list[dict]] | None=None, inventory: dict | None=None, capability_receipt: dict | None=None) -> str | None:
    """S6 XML 命令存在性硬规则（理论 (33) 版本参数化；DESIGN §2.2/§26.7）。

    「测本版本不存在的功能」在 v8 曾烧 3 编写轮+多次上机+1 个封顶面板才到人
    (<case> fulldns,10.5 专属手册零记载而设备 585 拒绝=行为正确、记载互斥)。
    2026-08-03 裁定后，本规则在 emit 期以 build 绑定 XML 判存在性：XML miss
    直接拒卷、保留终态 claim，不问人；SPEC/手册/先例/dev_help 只作旁证。
    命令头存在但实参违反 XML 契约时拒当前卷，并签发结构化 S3 claim。
    投影模块/文件/结构损坏抛 ``CommandTreeUnavailable``，不能假称设备不支持。"""
    ordered = _ordered_apv_cmds(steps, init)
    if not ordered:
        return None
    _vendor, inv, _resolve_from_snapshot = build_command_tree_resolver(device_build=device_build, inventory=inventory)

    def _complete_from_snapshot(command: str, limit: int=3) -> list[str]:
        tokens = _vendor.norm_command_tokens(command)
        scored: list[tuple[int, int, str]] = []
        for head in inv['headers']:
            head_tokens = head.split(' ')
            common = 0
            while common < len(head_tokens) and common < len(tokens) and (head_tokens[common] == tokens[common]):
                common += 1
            if common:
                scored.append((-common, len(head_tokens), head))
        scored.sort()
        return [head for _common, _length, head in scored[:limit]]
    seen: set[str] = set()
    misses: list[tuple[str, list[str]]] = []
    method_hits: list[tuple[str, dict]] = []
    confirm_hits: list[tuple[str, str]] = []
    chinese_hits: list[str] = []
    parameter_violations: list[dict] = []
    manual_only: dict[str, str] = {}
    for idx, cmd in enumerate(ordered):
        r = _resolve_from_snapshot(cmd)
        if _XC.is_scenario3_violation(r):
            parameter_violations.append({'occurrence_index': idx, 'command': cmd, 'result': r})
            continue
        if cmd in seen:
            continue
        seen.add(cmd)
        _manual_only = r['kind'] == 'missing' and r['reason_code'] == 'xml_absent_manual_only'
        if r['kind'] != 'missing':
            continue
        if _manual_only:
            raw_src = str(r.get('src') or '')
            from cex_core.engine.kms.manual_locator import display_manual_locator, parse_adoc_style_src
            man_ver, man_root = _manual_catalog_location()
            if man_ver and parse_adoc_style_src(raw_src):
                raw_src = display_manual_locator(raw_src, version=man_ver, root=man_root)
            manual_only[cmd] = raw_src
            misses.append((cmd, _complete_from_snapshot(cmd)))
            continue
        method_sig = _atlas_method_signature(_first_token(cmd))
        if method_sig is not None:
            method_hits.append((cmd, method_sig))
            misses.append((cmd, _complete_from_snapshot(cmd)))
            continue
        non_cmd_kind = _vendor.classify_non_command(cmd)
        if non_cmd_kind == 'confirmation_answer':
            confirm_hits.append((cmd, _confirmation_trigger_hint(ordered[:idx])))
            continue
        if non_cmd_kind == 'chinese_action_description':
            chinese_hits.append(cmd)
            continue
        misses.append((cmd, _complete_from_snapshot(cmd)))
    shape_block = _build_line_shape_block(method_hits, confirm_hits, chinese_hits) if method_hits or confirm_hits or chinese_hits else None

    def _with_shape(msg: str | None) -> str | None:
        """把 line-shape 诊断与 command_existence 呈报**并列**给出,谁也不吃掉谁。

        起因(内部评审日期（已脱敏） Design 评审复现):初版在这里 `return _build_line_shape_block(...)`
        提前返回,于是同一次 emit 里**另一条真实的 T5 miss 被整个吞掉**——不是
        "这轮不显示但账上有",是 needs_decision.json 压根没落盘。实测构造:steps 里
        同时放一条 `importKey vh1,cert/x.key`(T1)与一条 `sdns zzznonexistent on`
        (真 miss),返回的错误里搜不到 zzznonexistent、台账也没写。

        worker 一次只被告知一个问题、修完再撞下一个,本身就是本项目在治的"烧轮次"
        病;而这里更坏的是**没被告知的那个还不留痕**。所以两块都给。
        """
        if shape_block is None:
            return msg
        return shape_block if msg is None else shape_block + '\n\n' + msg
    generation_binding = _XC.generation_binding(inv, capability_receipt)
    parameter_block = None
    if parameter_violations:
        details = []
        for occurrence in parameter_violations:
            cmd = str(occurrence['command'])
            result = occurrence['result']
            details.append({'occurrence_index': occurrence['occurrence_index'], 'command': cmd, 'head': result.get('head'), 'xml_node': result.get('src'), 'build': result.get('device_build'), 'reason_code': result.get('reason_code'), 'parameter_error': result.get('parameter_error') or {}})
        ledger_landed = _land_claims(autoid, _XC.scenario3_ledger_mutator(autoid, parameter_violations, generation_binding), gate='command_parameter_contract')
        try:
            from types import SimpleNamespace
            _write_gate_rejections(autoid, [SimpleNamespace(code='command_parameter_contract', detail=json.dumps(details, ensure_ascii=False, sort_keys=True)[:360], step_index=-1)], stage='emit')
        except Exception:
            logger.debug('command parameter contract mailbox 落盘失败', exc_info=True)
        parameter_block = 'error: command-existence gate — XML parameter contract rejected the following command argument(s); this volume cannot be emitted or sent to a device. Structured reason:\n' + json.dumps(details, ensure_ascii=False, sort_keys=True) + ('\nThe scenario-3 conflict ledger is bound to the exact XML match.' if ledger_landed else '\nThe scenario-3 conflict ledger could not be written; the volume remains refused.')
    scenario4_conflicts: list[dict] = []
    try:
        from cex_core.engine.case_compiler.case_ir import VALID_CHECK_METHODS
    except Exception:
        VALID_CHECK_METHODS = frozenset()
    for group in _structured_command_assertion_groups(steps, init):
        conflict = _XC.scenario4_conflict(group, _resolve_from_snapshot(str(group['command'])), VALID_CHECK_METHODS)
        if conflict is not None:
            scenario4_conflicts.append(conflict)
    scenario4_landed = True
    scenario4_ledger_path = _sh.outputs_root() / str(autoid or '').strip() / 'needs_decision.json'
    existing_scenario4 = False
    if scenario4_ledger_path.is_file():
        existing_ledger = _read_claims_ledger(scenario4_ledger_path, autoid)
        existing_scenario4 = bool(isinstance(existing_ledger, dict) and any((isinstance(claim, dict) and claim.get('claim_kind') == 'xml_expectation_conflict' for claim in existing_ledger.get('claims') or [])))
    if scenario4_conflicts or existing_scenario4:
        scenario4_landed = _land_claims(autoid, _XC.scenario4_ledger_mutator(autoid, scenario4_conflicts, generation_binding), gate='command_expectation_contract')
    scenario4_block = None
    if scenario4_conflicts:
        scenario4_block = "error: command-existence gate — XML expectation contract conflicts with the case's structured check_point assertion(s); this volume cannot be emitted before the scenario-4 decision is bound:\n" + json.dumps(scenario4_conflicts, ensure_ascii=False, sort_keys=True) + ('\nThe scenario-4 conflict ledger is bound to the exact XML result declaration.' if scenario4_landed else '\nThe scenario-4 conflict ledger could not be written; the volume remains refused.')

    def _combine_contract_blocks(*blocks: str | None) -> str | None:
        present = [block for block in blocks if block]
        return '\n\n'.join(present) if present else None
    if not misses:
        return _with_shape(_combine_contract_blocks(parameter_block, scenario4_block))
    ver = str(inv.get('version', ''))
    stats = inv.get('stats') or {}
    evidence_claim: dict | None = None
    device_attestation: dict | None = None
    evidence_note = ''
    if (evidence or '').strip():
        ok, note, ev_kind = _verify_command_evidence(evidence, [c for c, _ in misses])
        evidence_note = note
        if ev_kind == 'device_attestation':
            raw_claim = (evidence or '').strip()
            if raw_claim.lower().startswith('dev_help:'):
                raw_claim = raw_claim.split(':', 1)[1].strip()
            device_attestation = {'basis': 'worker_supplied_dev_help', 'claim': raw_claim, 'verification': 'unverified', 'authoritative_for_existence': False}
        else:
            evidence_claim = {'kind': 'manual' if ev_kind == 'cli_manual' else ev_kind or 'unresolved', 'claim': (evidence or '').strip()[:500], 'verified_reference': bool(ok), 'note': note[:300], 'authoritative_for_existence': False}

    def _xml_basis(command: str, near: list[str]) -> dict:
        source = inv.get('source') or {}
        node_paths: list[str] = []
        for head in near:
            entry = (inv.get('headers') or {}).get(head) or {}
            src = str(entry.get('src') or '')
            prefix = f"vendor_xml:{inv.get('device_os_build', '')}:"
            if src.startswith(prefix):
                node_paths.append(src[len(prefix):])
        if not node_paths:
            command_tokens = re.sub('\\s+', ' ', command.strip().lower()).split(' ')
            scored: list[tuple[int, int, str]] = []
            for head, entry in (inv.get('headers') or {}).items():
                head_tokens = str(head).split(' ')
                count = 0
                while count < len(command_tokens) and count < len(head_tokens) and (command_tokens[count] == head_tokens[count]):
                    count += 1
                if count:
                    scored.append((-count, len(head_tokens), str(entry.get('src') or '')))
            for _score, _length, src in sorted(scored)[:3]:
                prefix = f"vendor_xml:{inv.get('device_os_build', '')}:"
                if src.startswith(prefix):
                    node_paths.append(src[len(prefix):])
        return {'build': str(inv.get('device_os_build') or '?'), 'source_filename': str(source.get('filename') or ''), 'source_sha256': str(source.get('sha256') or ''), 'requested_node_path': None, 'nearest_node_paths': list(dict.fromkeys(node_paths))}

    def _mutate_command_existence(claims: list) -> list:
        old = [c for c in claims if not (c.get('claim_kind') == 'command_existence' and c.get('command') in {m[0] for m in misses})]
        for cmd, near in misses:
            xml_basis = _xml_basis(cmd, near)
            verified_precedents = [dict(item) for item in (precedent_passes or {}).get(cmd, []) if isinstance(item, dict) and item.get('verification') == 'device_delivery_pass' and item.get('build') and item.get('oid')]
            cross_build = [item for item in verified_precedents if str(item.get('build')) != str(xml_basis.get('build'))]
            if _looks_like_shell(cmd):
                reason = f"『{cmd}』不是当前 build {xml_basis.get('build', '?')} 命令树里的 CLI 命令。机械用例的 E=APV_* 只承载产品 CLI；后台/shell 观测须改用等价 CLI，找不到时按无法编写报告。"
            elif cross_build:
                prior = '、'.join((f"{item['build']} 版本 OID {item['oid']}" for item in cross_build))
                reason = f"设备不支持这个功能；{prior} 有真机 PASS 编写，但当前 build {xml_basis.get('build', '?')} 的 XML 命令树未收录命令『{cmd}』；疑似版本变动，不归因命令书问题（除非 XML 注入错误）。可得邻近 XML 节点:{'、'.join(xml_basis['nearest_node_paths']) or '无'}"
            elif verified_precedents:
                prior = '、'.join((f"{item['build']} 版本 OID {item['oid']}" for item in verified_precedents))
                reason = f"设备不支持这个功能；{prior} 有真机 PASS 编写，但同一 build {xml_basis.get('build', '?')} 的 XML 命令树未收录命令『{cmd}』；疑似 XML 注入或投影异常，不归因命令书问题。可得邻近 XML 节点:{'、'.join(xml_basis['nearest_node_paths']) or '无'}"
            else:
                reason = f"设备不支持这个功能；命令『{cmd}』在设备命令树 build {xml_basis.get('build', '?')} 未收录。可得邻近 XML 节点:{'、'.join(xml_basis['nearest_node_paths']) or '无'}"
            claim = {'claim_kind': 'command_existence', 'command': cmd, 'xml_absent_manual_only': True, 'terminal': True, 'requires_user_decision': False, 'xml_basis': xml_basis, 'reason': reason, 'suggested_fix': '修改用例，或在绑定同一 build 的 XML 投影更新后重新编译', 'min_requests': 0, 'ordering_sensitive': False, 'decision_binding': {'status': 'interface_required', 'required_fields': ['claim_fingerprint', 'signer'], 'integration_owner': 'G6', 'note': 'G3 未发现 claim fingerprint signer 接口；旧案级 decision 不得放行'}}
            if cmd in manual_only:
                claim['manual_src'] = manual_only[cmd]
            if evidence_claim is not None:
                claim['evidence_claim'] = evidence_claim
                if evidence_claim.get('kind') == 'spec':
                    claim['spec_agrees'] = True
                elif evidence_claim.get('kind') == 'manual' and (not claim.get('manual_src')):
                    claim['manual_src'] = evidence_claim.get('claim')
            if device_attestation is not None:
                claim['device_attestation'] = device_attestation
            if verified_precedents:
                claim['precedent_device_passes'] = verified_precedents
            old.append(claim)
        return old
    ledger_landed = _land_claims(autoid, _mutate_command_existence, gate='command_existence')
    try:
        from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
        emit_signal('command_existence_miss', autoid, source='compile_emit', commands=[c for c, _ in misses], version=ver)
    except Exception:
        pass
    try:
        from types import SimpleNamespace
        _write_gate_rejections(autoid, [SimpleNamespace(code=COMMAND_NOT_IN_TREE_CODE, detail='; '.join((f'{c!r} not in vendor set' for c, _ in misses))[:360], step_index=-1)], stage='emit')
    except Exception:
        logger.debug('command_existence gate mailbox 落盘失败', exc_info=True)
    lines = '\n'.join((f'  - {cmd!r} is not a CLI command in this build. E=APV_* G may contain only build-bound product CLI commands (DESIGN §26.7); use an equivalent CLI observation, or report that the case cannot be compiled.' if _looks_like_shell(cmd) else f"  - {cmd!r}; nearest XML node(s): {', '.join(_xml_basis(cmd, near)['nearest_node_paths']) or 'unavailable'}" for cmd, near in misses))
    if any((_looks_like_shell(cmd) for cmd, _near in misses)):
        terminal_intro = f"error: command-existence gate — the following APV G-column line(s) are not CLI commands in build {inv.get('device_os_build', '?')} or are absent from its XML command tree. Shell/backend text and ordinary missing command heads have the same terminal disposition: no device run and no human arbitration:"
    else:
        terminal_intro = f"error: command-existence gate — 设备不支持这个功能；build {inv.get('device_os_build', '?')}。XML 命令树未收录以下命令，SPEC、用例、手册、先例或设备自签均不能覆盖这项存在性结论；本案不上机、不进入人工仲裁："
    terminal_block = f'{terminal_intro}\n{lines}\n' + (f'旁证已作为非放行 claim 留档：{evidence_note[:240]}。\n' if evidence_note else '') + ('终态台账已保留。' if ledger_landed else 'terminal ledger write FAILED；终态事实未落盘，请按原错误上报。')
    secondary_blocks = _combine_contract_blocks(parameter_block, scenario4_block)
    if secondary_blocks:
        terminal_block += '\n\n' + secondary_blocks
    return _with_shape(terminal_block)

def _bounded_case_json(path: Path, *, max_bytes: int=4 * 1024 * 1024) -> dict | None:
    try:
        from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, validate_json_budget
        raw = read_regular_nofollow(path, error_type=ValueError, invalid_message='case JSON path is invalid', directory_message='case JSON directory is unavailable', open_message='case JSON is unavailable', bounds_message='case JSON exceeds the byte budget', changed_message='case JSON changed while being read', max_bytes=max_bytes)
        assert isinstance(raw, bytes)
        validate_json_budget(raw, error_type=ValueError, message='case JSON exceeds the structure budget')
        payload = json.loads(raw.decode('utf-8'))
    except (OSError, ValueError, RecursionError):
        return None
    return payload if isinstance(payload, dict) else None

def _recorded_author_unreachable_values(autoid: str, *, xlsx_sha256: str='') -> list[str]:
    """回读 emit 期签在同一份 ``case.xlsx`` 上的作者出处不可达值。

    出处只判一次:单案 emit 手里有引擎密封的 canonical 单案切片，判完连同 ``xlsx_sha256``
    一起签进 lint 凭证。合卷与未通过卷归档手里没有切片(工具没有批身份、够不着
    ``manifest.json``，唯一能承载切片的入参又是主 agent 可写的 LLM 面)，因此不重推
    出处、只把那份判决按 artifact 指纹读回来。

    身份不闭合(凭证缺失/autoid 不符/SHA 对不上/存量凭证没有这个字段)一律返回空集
    ——退回"无作者绑定"，防编造那一半原样保留。传 ``xlsx_sha256`` 时用调用方已核过的
    那个指纹，不再重读卷面(避免与调用方的字节快照之间出现竞态窗口)。
    """
    return _recorded_admission_values(autoid, 'author_unreachable_values', xlsx_sha256=xlsx_sha256)

def _recorded_author_ip_literals(autoid: str, *, xlsx_sha256: str='') -> list[str]:
    """回读 emit 期签在同一份 ``case.xlsx`` 上的作者亲笔地址字面(T5 扩展,2026-09-08)。

    触发可达性与执行体路径两条规则在合卷/归档回读的豁免依据。身份闭合判据与
    ``_recorded_author_unreachable_values`` 完全相同(同一凭证、同一 SHA 绑定);存量
    凭证没有 ``author_ip_literals`` 字段一律空集——退回旧判据,防编造那一半原样保留。
    """
    return _recorded_admission_values(autoid, 'author_ip_literals', xlsx_sha256=xlsx_sha256)

def _recorded_admission_values(autoid: str, field: str, *, xlsx_sha256: str='') -> list[str]:
    """按 artifact 指纹读回 lint 凭证里 ``unreachable_ip_admission`` 的一个字符串列表字段。"""
    aid = str(autoid or '').strip()
    try:
        aid, xp = _safe_case_path(aid, field='autoid')
    except ValueError:
        return []
    credential = _bounded_case_json(_sh.outputs_root() / aid / '.grade_credential.json', max_bytes=512 * 1024)
    if not isinstance(credential, dict):
        return []
    if str(credential.get('autoid') or '') != aid:
        return []
    credential_sha = str(credential.get('xlsx_sha256') or '')
    if re.fullmatch('[0-9a-f]{64}', credential_sha) is None:
        return []
    known_sha = str(xlsx_sha256 or '').strip().lower()
    if not known_sha:
        try:
            known_sha = hashlib.sha256(xp.read_bytes()).hexdigest()
        except OSError:
            return []
    if known_sha != credential_sha:
        return []
    record = credential.get('unreachable_ip_admission')
    if not isinstance(record, dict) or not accepts_schema(record.get('schema'), UNREACHABLE_IP_ADMISSION_SCHEMA):
        return []
    values = record.get(field)
    if not isinstance(values, list) or not all((isinstance(item, str) and item for item in values)):
        return []
    return sorted(set(values))

def _reachability_scope_from_credential(autoid: str, *, xlsx_sha256: str) -> tuple[ReachabilityScope | None, str]:
    """安全回读 lint 凭证，并对 sealed mechanical_case 复算 blocks.kind 分域。"""
    aid = str(autoid or '').strip()
    credential = _bounded_case_json(_sh.outputs_root() / aid / '.grade_credential.json', max_bytes=512 * 1024)
    if not isinstance(credential, dict):
        return (None, 'lint credential JSON is unavailable')
    if str(credential.get('autoid') or '') != aid or str(credential.get('xlsx_sha256') or '') != str(xlsx_sha256 or ''):
        return (None, 'lint credential identity does not match this case.xlsx snapshot')
    scope, error = _validate_reachability_scope(credential.get('reachability_scope'))
    if scope is None:
        return (None, f'lint credential has no valid blocks.kind scope: {error}')
    if 'consistency_contract_sha256' not in credential:
        return (None, 'lint credential predates the explicit consistency identity field')
    if 'consistency_requirement_proof' not in credential:
        return (None, 'lint credential has no explicit consistency requirement proof')
    credential_consistency_sha = credential.get('consistency_contract_sha256')
    credential_requirement_proof = credential.get('consistency_requirement_proof')
    if scope['source'] != 'sealed_mechanical_case':
        if credential_consistency_sha is not None or credential_requirement_proof is not None:
            return (None, 'unsealed lint credential cannot claim consistency evidence')
        return (scope, '')
    if not isinstance(credential_requirement_proof, dict):
        return (None, 'sealed lint credential consistency proof is not a JSON object')
    try:
        from cex_core.engine.case_compiler.mechanical_case import load_mechanical_case
        mechanical_case, _byte_sha256 = load_mechanical_case(_sh.outputs_root() / aid / 'mechanical_case.json')
    except Exception as exc:
        return (None, f'sealed mechanical_case.json cannot be read for reachability scope ({type(exc).__name__}: {exc})')
    seal = str(mechanical_case.seal.mechanical_case_sha256 or '')
    if seal != scope['mechanical_case_sha256']:
        return (None, 'mechanical-case seal differs from the lint credential scope')
    try:
        expected = _reachability_scope_from_blocks(list(mechanical_case.blocks), mechanical_case_sha256=seal)
    except (TypeError, ValueError) as exc:
        return (None, f'mechanical-case blocks.kind scope is invalid: {exc}')
    if expected != scope:
        return (None, 'lint credential reachability scope differs from sealed blocks JSON')
    observed_consistency_sha, observed_requirement_proof, consistency_error = _validated_consistency_contract_identity(aid, mechanical_case_sha256=seal, blocks=list(mechanical_case.blocks), sealed_requirement_proof=credential_requirement_proof)
    if consistency_error:
        return (None, consistency_error)
    if credential_consistency_sha != observed_consistency_sha:
        return (None, 'lint credential consistency identity differs from sealed inputs')
    if credential_requirement_proof != observed_requirement_proof:
        return (None, 'lint credential consistency proof differs from sealed inputs')
    return (scope, '')

def _intent_payload(autoid: str) -> dict | None:
    from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
    try:
        payload, _raw = read_intent_json(_sh.outputs_root() / (autoid or '').strip() / 'intent.json', trusted_root=_sh.outputs_root())
    except ContractError:
        return None
    return payload

def _validated_consistency_contract_identity(autoid: str, *, mechanical_case_sha256: str, blocks: list, consistency_batch_name: str='', sealed_requirement_proof: dict | None=None) -> tuple[str | None, dict | None, str]:
    """复核 intent↔机械用例↔accepted ledger↔linked overlay 的同一身份。

    返回 ``(overlay_sha256_or_none, requirement_proof_or_none, error)``。overlay
    的 ``None`` 只表示引擎明确盖章 ``not_applicable_no_governing_spec``；proof
    仍必须存在。任一 required 边缺失或漂移均返回错误。emit/merge 共用此函数，
    不能只凭 mechanical SHA 间接相信 overlay。
    """
    aid = str(autoid or '').strip()
    seal = str(mechanical_case_sha256 or '').strip()
    if re.fullmatch('[0-9a-f]{64}', seal) is None:
        return (None, None, 'sealed mechanical-case identity is missing')
    intent = _intent_payload(aid)
    if not isinstance(intent, dict) or str(intent.get('autoid') or '') != aid:
        return (None, None, 'engine intent is unavailable or has another case identity')
    try:
        from cex_core.engine.ist_core.compile_engine.consistency_requirement import NOT_APPLICABLE, ConsistencyRequirementError, validate_recorded_consistency_requirement_proof, validate_consistency_requirement
        batch_name = str(consistency_batch_name or '').strip()
        if batch_name:
            requirement_proof = validate_consistency_requirement(outputs_root=_sh.outputs_root(), project_root=_sh.project_root(), batch_name=batch_name, autoid=aid, intent=intent, require_complete=True)
        elif isinstance(sealed_requirement_proof, dict):
            requirement_proof = validate_recorded_consistency_requirement_proof(outputs_root=_sh.outputs_root(), project_root=_sh.project_root(), autoid=aid, intent=intent, recorded_proof=sealed_requirement_proof, require_complete=True)
        else:
            raise ConsistencyRequirementError('recorded_proof_missing', 'merge has no xlsx-bound consistency requirement proof')
    except ConsistencyRequirementError as exc:
        return (None, None, f'{exc.code}: {exc.detail}')
    requirement = str(requirement_proof['requirement'])
    binding_status = str(intent.get('consistency_binding_status') or '')
    declared_path = intent.get('consistency_contract_path')
    declared_sha = intent.get('consistency_contract_sha256')
    receipt_sha = intent.get('consistency_receipt_sha256')
    try:
        from cex_core.engine.case_compiler.mechanical_case import load_mechanical_case
        mechanical_case, _byte_sha256 = load_mechanical_case(_sh.outputs_root() / aid / 'mechanical_case.json')
    except Exception as exc:
        return (None, None, f'sealed mechanical case is unavailable ({type(exc).__name__})')
    actual_seal = str(mechanical_case.seal.mechanical_case_sha256 or '')
    if actual_seal != seal:
        return (None, None, 'mechanical-case seal differs from the engine emit binding')
    if _canonical_json_sha256(list(mechanical_case.blocks)) != _canonical_json_sha256(blocks):
        return (None, None, 'emit blocks differ from the sealed mechanical case')
    mechanical_overlay_sha = mechanical_case.binding.consistency_contract_sha256
    mechanical_base_sha = str(mechanical_case.binding.contract_sha256 or '')
    if mechanical_base_sha != requirement_proof['base_contract_sha256']:
        return (None, None, 'mechanical base contract differs from the consistency requirement proof')
    if requirement == NOT_APPLICABLE:
        if mechanical_overlay_sha is not None:
            return (None, None, 'not-applicable mechanical binding must remain null')
        return (None, requirement_proof, '')
    if binding_status != 'complete' or not isinstance(declared_path, str) or re.fullmatch('[0-9a-f]{64}', str(declared_sha or '')) is None or (re.fullmatch('[0-9a-f]{64}', str(receipt_sha or '')) is None):
        return (None, None, 'required consistency binding is incomplete')
    overlay_path = _sh.outputs_root() / aid / 'consistency_contract.json'
    try:
        expected_rel = str(overlay_path.relative_to(_sh.project_root()))
    except ValueError:
        return (None, None, 'consistency overlay path escaped the project root')
    if declared_path != expected_rel:
        return (None, None, 'intent consistency overlay path is not the engine-owned case path')
    try:
        from cex_core.engine.case_compiler.consistency_contract import SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY, load_consistency_contract, validate_consistency_contract
        from cex_core.engine.ist_core.tools.device.consistency_receipt import accepted_consistency_record_for_receipt
        from cex_core.engine.ist_core.tools.device.mechanical_case_submit_tool import _frozen_contract
        overlay, observed_sha = load_consistency_contract(overlay_path)
        accepted = accepted_consistency_record_for_receipt(_sh.outputs_root(), aid, str(receipt_sha))
        base_contract, base_sha, violations = _frozen_contract(aid, _sh.outputs_root(), _sh.project_root())
    except Exception as exc:
        return (None, None, f'consistency overlay closure is unavailable ({type(exc).__name__})')
    material = accepted.get('material') if isinstance(accepted, dict) else None
    if observed_sha != declared_sha or mechanical_overlay_sha != declared_sha or accepted.get('receipt_sha256') != receipt_sha or (base_contract is None) or violations or (not isinstance(material, dict)) or (base_sha != requirement_proof['base_contract_sha256']):
        return (None, None, 'consistency overlay identity differs across intent, case, or ledger')
    error = validate_consistency_contract(overlay, base_contract=base_contract, base_contract_sha256=base_sha, accepted_material=material, consistency_receipt_sha256=str(receipt_sha), machine_case=None)
    scope = (overlay.get('spec_endorsement') or {}).get('scope') if isinstance(overlay, dict) else None
    if error == 'spec_endorsement_scope_invalid' and isinstance(scope, dict) and (scope.get('kind') == 'expectation'):
        endorsement = dict(overlay.get('spec_endorsement') or {})
        endorsement['scope'] = {'kind': 'case'}
        downgraded = {**overlay, 'spec_endorsement': endorsement}
        error = validate_consistency_contract(downgraded, base_contract=base_contract, base_contract_sha256=base_sha, accepted_material=material, consistency_receipt_sha256=str(receipt_sha), machine_case=None)
        expectation_id = str(scope.get('expectation_id') or '')
        base_ids: list[str] = []
        for item in base_contract.get('expectations') or []:
            if not isinstance(item, dict):
                continue
            carrier = next((item.get(key) for key in ('assertion', 'author_claim', 'defect_spec_claim') if isinstance(item.get(key), dict)), None)
            if isinstance(carrier, dict):
                base_ids.append(str(carrier.get('expectation_id') or ''))
        mechanical_ids = [str(item.expectation_id or '') for item in mechanical_case.expectation_binding]
        if error or not expectation_id or base_ids.count(expectation_id) != SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY or (mechanical_ids.count(expectation_id) != SPEC_ENDORSEMENT_EXPECTATION_CARDINALITY):
            return (None, None, error or 'consistency expectation scope is not uniquely bound')
        error = ''
    if error:
        return (None, None, error)
    return (str(observed_sha), requirement_proof, '')

def _gate_governing_spec_identity(autoid: str, provenance=None, *, mutation_receipt: dict | None=None) -> str | None:
    """闭合引擎 stamp、静态期望契约与本次最终断言的同一身份。

    ``mutation_receipt`` 是 ``compile_mutation_plan`` 本次的铸造记录，用来核对
    provenance 里带 ``mutation_role`` 的对照行确实是编译器插的（详见
    ``authority_reconcile.product_assertion_steps``）。不给＝一行都不摘；此时
    多条断言仍按“每个 id 有覆盖、形态两两有别”判定，不能退回旧的 1:1 计数规则。
    """
    case_dir = _sh.outputs_root() / (autoid or '').strip()
    stamp = _bounded_case_json(case_dir / 'intent_stamp_status.json', max_bytes=64 * 1024)
    payload = _intent_payload(autoid)
    if not isinstance(stamp, dict) or not accepts_schema(stamp.get('schema'), 'ist.intent-stamp-status'):
        return f'error: engine intent/spec identity stamp is missing for case {autoid}; compile_emit only accepts the current sealed author path'
    stamp_status = str(stamp.get('status') or 'unavailable')
    if stamp_status != 'complete' or str(stamp.get('autoid') or '') != autoid or payload is None or (str(payload.get('autoid') or '') != autoid):
        return f'error: engine intent/spec identity stamp is {stamp_status} or has the wrong case identity for case {autoid}; regenerate it before emitting'
    contract_sha = str(payload.get('typed_expectation_contract_sha256') or '').strip()
    contract_rel = str(payload.get('typed_expectation_contract_path') or '').strip()
    stamped_expectations = payload.get('typed_expectations')
    stamped_author_claims = payload.get('author_claims')
    stamped_defect_spec_claims = payload.get('defect_spec_claims')
    if stamped_author_claims is None:
        stamped_author_claims = {}
    if stamped_defect_spec_claims is None:
        stamped_defect_spec_claims = {}
    typed_status = str(payload.get('typed_expectation_status') or 'ready').strip()
    contract_declared = bool(contract_sha or contract_rel or stamped_expectations or stamped_author_claims or stamped_defect_spec_claims)
    typed_spec_locators: list[str] = []
    final_spec_locators: list[str] = []
    contract_author_fixture_policies: dict[str, dict[str, Any]] = {}
    if payload.get('stamped_by') == 'engine.author' and (not contract_declared):
        return f'error: engine-authored typed expectation stamp is missing for case {autoid}'
    if contract_declared:
        if re.fullmatch('[0-9a-f]{64}', contract_sha) is None or not contract_rel:
            return f'error: typed expectation stamp is incomplete for case {autoid}'
        if typed_status == 'ready':
            if not isinstance(stamped_expectations, dict) or not stamped_expectations:
                return f'error: typed expectation stamp is incomplete for case {autoid}'
        elif typed_status == 'pending':
            if not isinstance(stamped_expectations, dict) or not isinstance(stamped_author_claims, dict) or (not isinstance(stamped_defect_spec_claims, dict)) or (not (stamped_author_claims or stamped_defect_spec_claims)):
                return f'error: pending source claim stamp is incomplete for case {autoid}'
        else:
            return f'error: typed expectation status is invalid for case {autoid}'
        project_root = Path(os.path.abspath(os.fspath(_sh.project_root())))
        outputs_root = Path(os.path.abspath(os.fspath(_sh.outputs_root())))
        contract_path = Path(contract_rel)
        if contract_path.is_absolute():
            return f'error: typed expectation contract path is not project-relative for case {autoid}'
        contract_path = Path(os.path.abspath(os.fspath(project_root / contract_path)))
        try:
            contract_path.relative_to(outputs_root)
        except ValueError:
            return f'error: typed expectation contract escaped outputs for case {autoid}'
        try:
            from cex_core.engine.case_compiler._sealed_io import CONTRACT_CARD_MAX_BYTES, read_regular_nofollow, validate_json_budget
            contract_bytes = read_regular_nofollow(contract_path, error_type=ValueError, invalid_message='typed expectation contract path is invalid', directory_message='typed expectation contract directory is unavailable', open_message='typed expectation contract is unavailable', bounds_message='typed expectation contract exceeds the byte budget', changed_message='typed expectation contract changed while being read', max_bytes=CONTRACT_CARD_MAX_BYTES)
            assert isinstance(contract_bytes, bytes)
            validate_json_budget(contract_bytes, error_type=ValueError, message='typed expectation contract exceeds the structure budget')
            if hashlib.sha256(contract_bytes).hexdigest() != contract_sha:
                raise ValueError('typed expectation contract identity drift')
            contract_raw = json.loads(contract_bytes.decode('utf-8'))
            from cex_core.engine.ist_core.compile_engine.authority_reconcile import author_fixture_policies_from_contract
            contract_author_fixture_policies = author_fixture_policies_from_contract(contract_raw)
            contract_assertion_list = [assertion for item in contract_raw.get('expectations') or [] if isinstance(item, dict) for assertion in [item.get('assertion')] if isinstance(assertion, dict)]
            contract_author_claim_list = [claim for item in contract_raw.get('expectations') or [] if isinstance(item, dict) for claim in [item.get('author_claim')] if isinstance(claim, dict)]
            contract_defect_spec_claim_list = [claim for item in contract_raw.get('expectations') or [] if isinstance(item, dict) for claim in [item.get('defect_spec_claim')] if isinstance(claim, dict)]
            expectation_ids = [str(assertion.get('expectation_id') or '').strip() for assertion in contract_assertion_list]
            if contract_assertion_list and (any((not item for item in expectation_ids)) or len(set(expectation_ids)) != len(expectation_ids) or any((not str(assertion.get('semantic_key') or '').strip() for assertion in contract_assertion_list))):
                raise ValueError('typed expectation identities are incomplete or duplicated')
            contract_assertions = dict(zip(expectation_ids, contract_assertion_list))
            claim_ids = [str(claim.get('expectation_id') or '').strip() for claim in contract_author_claim_list]
            if contract_author_claim_list and (any((not item for item in claim_ids)) or len(set(claim_ids)) != len(claim_ids) or any((not str(claim.get('semantic_key') or '').strip() or str(claim.get('kind') or '') != 'Author' or str(claim.get('autoid') or '') != autoid for claim in contract_author_claim_list))):
                raise ValueError('pending Author claim identities are incomplete or duplicated')
            defect_claim_ids = [str(claim.get('expectation_id') or '').strip() for claim in contract_defect_spec_claim_list]
            if contract_defect_spec_claim_list and (any((not item for item in defect_claim_ids)) or len(set(defect_claim_ids)) != len(defect_claim_ids) or any((not str(claim.get('semantic_key') or '').strip() or str(claim.get('kind') or '') != 'DefectSpec' or str(claim.get('autoid') or '') != autoid for claim in contract_defect_spec_claim_list))):
                raise ValueError('pending DefectSpec claim identities are incomplete or duplicated')
            from cex_core.engine.case_compiler.provenance_ir import validate_defect_spec_claim
            for claim in contract_defect_spec_claim_list:
                verified_claim, claim_error = validate_defect_spec_claim(claim, autoid=autoid, expectation_id=str(claim.get('expectation_id') or ''), semantic_key=str(claim.get('semantic_key') or ''))
                if verified_claim is None:
                    raise ValueError(f'invalid pending DefectSpec claim: {claim_error}')
            all_contract_ids = [*expectation_ids, *claim_ids, *defect_claim_ids]
            if len(set(all_contract_ids)) != len(all_contract_ids):
                raise ValueError('typed expectation identities overlap across source kinds')
            if typed_status == 'ready' and (not contract_assertion_list):
                raise ValueError('typed expectation set is empty')
            if typed_status == 'pending' and (not (contract_author_claim_list or contract_defect_spec_claim_list)):
                raise ValueError('pending source claim set is empty')
            contract_author_claims = dict(zip(claim_ids, contract_author_claim_list))
            contract_defect_spec_claims = dict(zip(defect_claim_ids, contract_defect_spec_claim_list))
            typed_spec_locators = [str((assertion.get('source') or {}).get('locator') or '').strip() for assertion in contract_assertion_list if str((assertion.get('source') or {}).get('kind') or '') == 'spec']
        except Exception as exc:
            return f'error: typed expectation contract cannot be verified for case {autoid}: {type(exc).__name__}'
        if contract_assertions != stamped_expectations:
            return f'error: typed expectation stamp drifted from its contract for case {autoid}'
        if contract_author_claims != stamped_author_claims:
            return f'error: pending Author claim stamp drifted from its contract for case {autoid}'
        if contract_defect_spec_claims != stamped_defect_spec_claims:
            return f'error: pending DefectSpec claim stamp drifted from its contract for case {autoid}'
        if provenance is None:
            return f'error: typed expectation contract has no final provenance for case {autoid}'
        from cex_core.engine.ist_core.compile_engine.authority_reconcile import check_expectation_assertion_bijection, product_assertion_steps
        final_steps = product_assertion_steps(provenance.steps, mutation_receipt=mutation_receipt)
        final_spec_locators = [str(step.source.ref or '').strip() for step in final_steps if step.source.kind == 'spec']
        bijection_error = check_expectation_assertion_bijection(autoid=autoid, final_steps=final_steps, all_steps=provenance.steps, stamped_expectations=stamped_expectations, stamped_author_claims=stamped_author_claims, stamped_defect_spec_claims=stamped_defect_spec_claims, stamped_author_fixture_policies=contract_author_fixture_policies)
        if bijection_error:
            return bijection_error
    status = str(payload.get('governing_spec_status') or '').strip()
    from cex_core.engine.ist_core.compile_engine.conflict_chain import spec_absent as _spec_absent
    if not status or _spec_absent(status):
        if typed_spec_locators or final_spec_locators:
            return f'error: typed Spec claim has no governing spec identity for case {autoid}'
        return None
    identity = payload.get('governing_spec_identity')
    if status != 'bound' or not isinstance(identity, dict):
        return f"error: governing spec identity is {status or 'unavailable'} for case {autoid}; regenerate/reconcile the static spec index before emitting"
    name = str(identity.get('name') or '').strip()
    try:
        from cex_core.engine.kms.spec_index import resolve_indexed_spec
        resolved = resolve_indexed_spec(_sh.project_root(), name)
    except Exception:
        resolved = None
    if resolved is None or resolved.sha256 != identity.get('sha256') or resolved.size != identity.get('size') or (resolved.generation_id != identity.get('generation_id')) or (resolved.manifest_sha256 != identity.get('manifest_sha256')):
        return f'error: governing spec identity drifted for case {autoid} ({name}); regenerate/reconcile the static spec index before emitting'
    if any((locator.split(':', 1)[0] != name for locator in [*typed_spec_locators, *final_spec_locators])):
        return f'error: typed Spec claim locator does not match the governing spec identity for case {autoid}'
    return None

def _gate_manual_expect_conditional(autoid: str, prov) -> str | None:
    """保留旧调用形状，但不再按来源类型自动降级 Manual。

    SPEC 与 Manual 都是可错声明。同一语义主键上的不一致应保留两侧
    typed claim 并交给 U2 reconciliation，emit 不能在对账前代替用户选胜。
    """
    del autoid, prov
    return None

def _tau_gate_unavailable(autoid: str) -> str:
    """Deterministic τ authority unavailable: persist a stable rejection and block."""
    from types import SimpleNamespace
    _write_gate_rejections(autoid, [SimpleNamespace(code='tau_atlas_unavailable', detail='build-bound command teardown atlas could not be loaded and identity-verified', step_index=-1)], stage='emit')
    return "error: paired-teardown gate unavailable [tau_atlas_unavailable] — the build-bound command teardown atlas could not be loaded and identity-verified; xlsx and credential persistence are blocked. Most often this means one of its three sources changed without the atlas being regenerated (command-tree XML, the framework mirror's clear.py, or the switch-direction section of domain_grammar). Regenerate with: python -m scripts.gen_command_teardown_atlas"

def _gate_tau_coverage(autoid: str, steps: list, init: str='', *, device_build: str='') -> str | None:
    """G1 配对恢复规则(V8.5 片5;理论锚 (39) 六元组 τ/(32) 复位差集;DESIGN §17-G1)。

    atlas C2/C2b 配置写无案内恢复步 → 先写 needs_decision
    (missing_teardown claim,携 atlas 逆元建议与出处),再阻止 xlsx 与 lint 凭证持久化。
    C1 由框架承担；C3 只写案级 residual_config_disclosure，不拒卷、不进面板。
    逃生只有两条:①卷面补恢复步自然过 ②用户已裁决(同键不复问)。"""
    try:
        from cex_core.engine.case_compiler.tau_coverage import TauAtlasUnavailableError, check_tau_coverage, persist_residual_config_disclosure
    except Exception:
        return _tau_gate_unavailable(autoid)
    try:
        rep = check_tau_coverage(steps if isinstance(steps, list) else [], init, device_build=device_build)
    except TauAtlasUnavailableError:
        return _tau_gate_unavailable(autoid)
    except Exception:
        logger.exception('paired-teardown gate failed before producing a verdict')
        return _tau_gate_unavailable(autoid)
    if rep.residual_config:
        try:
            case_name = _safe_output_component(autoid, field='autoid')
            persist_residual_config_disclosure(_sh.outputs_root() / case_name, case_name, rep, discovery_stage='emit')
        except Exception:
            logger.warning('residual_config_disclosure 落盘失败(autoid=%s)', autoid, exc_info=True)
    if rep.ok:
        return None
    try:
        outd = _sh.outputs_root() / (autoid or '').strip()
        udp, ndp = (outd / 'user_decision.json', outd / 'needs_decision.json')
        from cex_core.engine.ist_core.tools.device.verifiability_tool import decision_covers_claims
        if decision_covers_claims(udp, ndp, claim_kinds={'missing_teardown'}, decisions={'改过程', '改预期'}):
            return None
    except Exception:
        logger.debug('missing_teardown 用户裁决检查失败(按未裁决)', exc_info=True)
    from cex_core.engine.case_compiler.tau_coverage import tau_ledger_mutator
    ledger_landed = _land_claims(autoid, tau_ledger_mutator(rep), gate='missing_teardown')
    if not ledger_landed:
        from types import SimpleNamespace
        _write_gate_rejections(autoid, [SimpleNamespace(code='tau_needs_decision_ledger_unavailable', detail='missing-teardown claim could not be persisted', step_index=-1)], stage='emit')
    try:
        from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
        emit_signal('missing_teardown', autoid, source='compile_emit', commands=[m['cmd'] for m in rep.missing])
    except Exception:
        pass
    lines = '\n'.join((f"  - {m['cmd']!r}  → suggested inverse: {m['suggested_inverse']!r}" for m in rep.missing))
    return f"error: paired-teardown gate — this case writes network-layer config that the framework's per-case cleanup cannot reach, with no in-case restore step:\n{lines}\nLeftovers of this kind poisoned the shared bed six times in one batch (measured: two cases repeatedly moved a listener IP onto a vlan/empty bond, killing every downstream case). Two exits:\n1) Append the restore steps at the end of the case (reverse-order `no` replay as suggested above; place them AFTER your assertions so they do not destroy what you are verifying), then re-emit.\n2) If the write itself IS the behavior under test and must persist, " + ('the structured needs_decision claim is durable; the engine emit node will collect it and route the user decision.' if ledger_landed else 'the structured claim could not be persisted; the engine emit node will collect the tau_needs_decision_ledger_unavailable mailbox event and keep this case blocked.')

def _gate_sleep_budget(autoid: str, steps: list) -> str | None:
    """D4 算术呈报规则:案内 sleep 秒数总和 ≥ 上机墙钟硬上限 ⇒ 算术上必超时,呈报不硬拒。

    事实链(2026-08-15 closedset×supply 交叉分析证实):
    - 上机墙钟被硬夹紧到 `batch_tools._RUN_TOTAL_CAP_S`,调用方参数无法突破
      (`total_max = max(default, min(max(floor, N×45s), CAP))`,floor 再大也被 min 夹回);
    - 运行器对 time/sleep 的 G 是强转整数的秒数(mirror `lib/test_xlsx.py`
      `int(parameters[0])`,契约 g_syntax="one numeric seconds argument");
    - 此前 emit 全部机械规则对 sleep 量值零约束——单案 sleep 总和 ≥CAP 的卷(老化/
      持久化超时类意图会写出)算术上不可能跑完,却能被密封上机,必烧整轮设备后以
      unknown/broken 收场。
    处置=**呈报**(needs_decision),不硬拒不静默:长等待可能就是被测意图(老化),
    「砍 sleep/拆案/照写」是用户的裁决不是引擎的;上限**按引用**读 batch_tools 常量,
    防两处漂移(红线:不在这里复制 2400)。G 不可整数解析的步不计入总和——那是
    `_check_contract_g_syntax` 的辖区,本规则只做算术对账,不重判语法。
    逃生:①总和 < 上限自然过;②该案已有用户裁决(同 claim 链身份不复问,与 τ 规则
    同一 `decision_covers_claims` 判据)。无 env 级开关(§2.8)。
    """
    from cex_core.engine.ist_core.tools.device.batch_tools import _RUN_TOTAL_CAP_S
    sleep_steps: list[dict] = []
    total = 0
    for i, s in enumerate(steps if isinstance(steps, list) else []):
        if not isinstance(s, dict):
            continue
        if str(s.get('E', '')).strip() != 'time' or str(s.get('F', '')).strip() != 'sleep':
            continue
        raw = str(s.get('G', '') or '').strip()
        try:
            seconds = int(raw)
        except ValueError:
            continue
        if seconds <= 0:
            continue
        total += seconds
        sleep_steps.append({'step_index': i, 'seconds': seconds})
    cap = int(_RUN_TOTAL_CAP_S)
    if total < cap:
        return None
    try:
        outd = _sh.outputs_root() / (autoid or '').strip()
        udp, ndp = (outd / 'user_decision.json', outd / 'needs_decision.json')
        from cex_core.engine.ist_core.tools.device.verifiability_tool import decision_covers_claims
        if decision_covers_claims(udp, ndp, claim_kinds={'sleep_budget_exceeded'}, decisions={'改过程', '改预期'}):
            return None
    except Exception:
        logger.debug('sleep_budget 用户裁决检查失败(按未裁决)', exc_info=True)
    from cex_core.engine.ist_core.compile_engine.conflict_chain import conflict_chain_id
    chain_id = conflict_chain_id({'scenario': 'sleep_budget_exceeded', 'sleep_steps': sleep_steps, 'sleep_total_s': total, 'run_wall_clock_cap_s': cap})

    def _mutate(claims: list) -> list:
        kept = [c for c in claims if c.get('claim_kind') != 'sleep_budget_exceeded']
        kept.append({'claim_kind': 'sleep_budget_exceeded', 'conflict_chain_id': chain_id, 'sleep_total_s': total, 'run_wall_clock_cap_s': cap, 'sleep_steps': sleep_steps, 'reason': f'案内 sleep 步秒数总和 {total}s ≥ 上机墙钟硬上限 {cap}s(整份提交、跑批超时按引用夹紧,参数无法突破)——算术上这份卷不可能在设备轮内跑完,密封上机只会烧掉整轮后以 unknown 收场。若长等待是被测意图(老化/持久化超时),需要你裁决:缩短等待、拆分用例,还是按原样保留(保留则本引擎的上机验证覆盖不了它)。', 'suggested_fix': '缩短 sleep 到墙钟内可完成,或拆分长等待用例;确属老化类意图则如实裁决保留', 'min_requests': 0, 'ordering_sensitive': False})
        return kept
    ledger_landed = _land_claims(autoid, _mutate, gate='sleep_budget')
    if not ledger_landed:
        from types import SimpleNamespace
        _write_gate_rejections(autoid, [SimpleNamespace(code='sleep_budget_needs_decision_ledger_unavailable', detail='sleep-budget claim could not be persisted', step_index=-1)], stage='emit')
    try:
        from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
        emit_signal('sleep_budget_exceeded', autoid, source='compile_emit', sleep_total_s=total, run_wall_clock_cap_s=cap)
    except Exception:
        pass
    lines = '\n'.join((f"  - steps[{s['step_index']}] time/sleep {s['seconds']}s" for s in sleep_steps))
    return f"error: sleep-budget gate — the arithmetic sum of this case's sleep seconds ({total}s) is not smaller than the on-device run wall-clock hard cap ({cap}s), so this volume cannot finish a device round under any parameters:\n{lines}\nThis is an arithmetic reconciliation, not a style rule: the whole xlsx is submitted as one suite and the run timeout is clamped to the cap by reference. " + ('The structured needs_decision claim is durable; the engine emit node will collect it and route the user decision (shorten the waits, split the case, or keep it as-is by explicit ruling).' if ledger_landed else 'The structured claim could not be persisted; the engine emit node will collect the sleep_budget_needs_decision_ledger_unavailable mailbox event and keep this case blocked.')
FrozenSealVerdict = Literal['not_frozen', 'same', 'changed', 'unavailable']

def _frozen_seal_verdict(autoid: str, new_seal_sha256: str, *, facts: list | None=None, facts_provider=None) -> tuple[FrozenSealVerdict, str, str]:
    """冻结法身份的**唯一**比对实现,返回 (判据, 机械基据文本, 签名摘要文本)。

    2026-08-20 收窄冻结规则时抽出:此前「同法/换法」只有引擎侧供给边
    (`engine_frozen_override_reason`)会算,而规则自己的放行判据是
    `override_frozen_reason` 非空字符串——实证 `override_frozen_reason='没换法,原样
    再跑一遍'` 照样通过规则(`内部取证文档（已脱敏）)。
    供给边与 enforcement 各判各的,规则就永远只信自报。收窄=两边同调这一个函数。

    读取顺序与既有 D1 供给边逐字相同(可得性递降,全部机械):
    1. `.frozen.json.frozen` 布尔 + `.sealed_mechanical_case_sha256`;
    2. 文件缺席时按 merge 内部工单 规则同一谓词 `F.frozen(facts, aid)` 现查,比对上一条
       产者事实的封印 sha;
    3. 两处都不可得 → `unavailable`(**不是** `same`)——按「重编换卷面即解冻」语义
       如实注明身份不可得,否则存量无字段冻结账在续跑批上原样复现死锁。

    `facts` 直接给账;`facts_provider` 是惰性取账回调(只在 `.frozen.json` 缺席分支
    才调用,避免每次 emit 都读整批事实流)。账层 OSError 原样上抛,由调用方按各自
    的 fail-closed 纪律处置。
    """
    aid = (autoid or '').strip()
    new_sha = (new_seal_sha256 or '').strip()
    if not aid:
        return ('not_frozen', '', '')
    fz_path = _sh.outputs_root() / aid / '.frozen.json'
    if fz_path.is_file():
        frozen = True
        frozen_sha = ''
        corrupt = False
        sig_text = ''
        try:
            peek = json.loads(fz_path.read_text(encoding='utf-8'))
            if 'frozen' not in peek:
                raise ValueError('frozen ledger carries no frozen flag')
            frozen = bool(peek['frozen'])
            frozen_sha = str(peek.get('sealed_mechanical_case_sha256') or '').strip()
            from cex_core.engine.ist_core.compile_engine import facts as _F_sig
            sig_text = ' | '.join((_F_sig.sig_key_text(s) for s in (peek.get('signatures') or [])[:2]))
        except Exception:
            corrupt = True
        if not frozen:
            return ('not_frozen', '', '')
        if not new_sha:
            return ('unavailable', 'this emit carries no sealed mechanical-case digest, so the frozen method identity cannot be compared', sig_text)
        if frozen_sha and frozen_sha == new_sha:
            return ('same', f'sealed mechanical case unchanged ({frozen_sha[:12]})', sig_text)
        if frozen_sha:
            return ('changed', f'sealed mechanical case changed {frozen_sha[:12]}->{new_sha[:12]}', sig_text)
        if corrupt:
            return ('unavailable', 'frozen ledger unreadable as JSON; prior sealed method identity unknown', sig_text)
        return ('unavailable', 'prior sealed method identity not recorded in the frozen ledger (legacy format)', sig_text)
    fl = list(facts) if facts is not None else list(facts_provider() or []) if callable(facts_provider) else []
    from cex_core.engine.ist_core.compile_engine import facts as _F
    if not _F.frozen(fl, aid):
        return ('not_frozen', '', '')
    verdicts = [f for f in fl if str(f.get('aid') or '') == aid and f.get('ev') == 'verdict' and (f.get('result') in ('pass', 'fail'))]
    sig_text = ' | '.join((_F.sig_key_text(s) for s in (verdicts[-1].get('signatures') or [])[:2])) if verdicts and verdicts[-1].get('result') == 'fail' else ''
    if not new_sha:
        return ('unavailable', 'this emit carries no sealed mechanical-case digest, so the frozen method identity cannot be compared (frozen file missing; judged via the fact ledger)', sig_text)
    producers = [f for f in fl if str(f.get('aid') or '') == aid and f.get('ev') in ('composed', 'mechanical_case_repaired') and str(f.get('mechanical_case_sha256') or '')]
    prev_sha = ''
    if producers:
        tail = str(producers[-1].get('mechanical_case_sha256') or '')
        if tail != new_sha:
            prev_sha = tail
        elif len(producers) >= 2:
            prev_sha = str(producers[-2].get('mechanical_case_sha256') or '')
    if prev_sha and prev_sha == new_sha:
        return ('same', f'sealed mechanical case unchanged ({prev_sha[:12]}; frozen file missing, judged via the fact ledger like the merge 内部工单 gate)', sig_text)
    if prev_sha:
        return ('changed', f'sealed mechanical case changed {prev_sha[:12]}->{new_sha[:12]} (frozen file missing, judged via the fact ledger like the merge 内部工单 gate)', sig_text)
    return ('unavailable', 'fact ledger shows frozen but no prior producer fact is on file (frozen file missing; cross-batch continuation)', sig_text)

def engine_frozen_override_reason(autoid: str, new_seal_sha256: str, facts: list | None=None, attribution_note: str='') -> str:
    """引擎侧机械拼装冻结换法声明(D1:两节点链的 override 供给边,2026-08-15)。

    背景:两节点拆图后 `compile_emit` 唯一生产调用方是引擎 emit 节点,它从不传
    `override_frozen_reason`;机械用例 schema 与 worker 协议也无承载字段——冻结案
    陷 compose→emit拒→re-author 烧轮死锁(<batch> 冻结墙,红线明文「勿改成 frozen
    即终态」)。修法=引擎在**能机械证明换法**时代为签发声明:理由=封印 sha 迁移
    (冻结法身份 → 本轮重铸新封印)+ 归因换法摘要,全程机械拼装、不经 LLM 转述。

    冻结规则本义**原样保住**:同签名同法重来(新封印 sha == 冻结时在卷的封印 sha)
    返回空串 → 规则照拒;冻结判定本身零改动(本函数只读,不碰 .frozen.json 的
    frozen 字段语义)。返回空串的含义是「引擎不代签」,不是「未冻结」。

    冻结法身份的来源(按可得性递降,全部机械):
    1. `.frozen.json.sealed_mechanical_case_sha256`——写侧(batch_tools 冻结落账)
       随账记录、重铸链(mint_and_land)对存量账回填;跨批续跑随文件原位存续;
    2. 文件缺席时(内部工单 写失败旁路)按 merge 内部工单 规则同一谓词 `F.frozen(facts, aid)`
       现查,比对上一条产者事实的封印 sha——引擎侧供给与引擎侧 enforcement 同源,
       ack(内部工单 单一声明源)因此有人写;
    3. 两处都不可得(legacy 格式/跨批零事实)→ 按「重编换卷面即解冻」语义
       (facts.py::frozen docstring)代签,理由如实注明身份不可得——否则 v10/v14
       存量 18 份无字段冻结账在续跑批上原样复现死锁,正是本修复要拆的墙。

    账层 OSError → 返回空串:规则自己会 fail-closed 并出声(gate_disabled 信号),
    引擎不在文件系统故障上代签。

    2026-08-20:判据本体搬去 `_frozen_seal_verdict`(规则与本供给边同调一个实现),
    本函数只剩「拿判据 → 拼声明文本」。行为逐字不变:same/not_frozen 返回空串,
    changed/unavailable 按机械基据代签。
    """
    aid = (autoid or '').strip()
    new_sha = (new_seal_sha256 or '').strip()
    if not aid or not new_sha:
        return ''
    try:
        verdict, basis, _sig = _frozen_seal_verdict(aid, new_sha, facts=facts)
    except OSError:
        return ''
    if verdict in ('not_frozen', 'same'):
        return ''
    reason = f'engine re-mint override: {basis}; re-authored via the two-node chain'
    note = (attribution_note or '').strip()
    if note:
        reason += f'; attribution: {note[:200]}'
    return reason[:500]

def _gate_observability(autoid: str, *, gate: str, state: str, **extra) -> None:
    """规则观测台账(runtime/logs/gate_observability.jsonl,T4):记「查过且通过/
    未触发」这类**非违例**状态——SIGNALS 闭集只记状态迁移,emit_stats 只记
    打回率,两者都不该被"没事发生"污染,故独立成账。追加失败静默。"""
    try:
        import time as _t
        from cex_core.engine.common.runtime_paths import runtime_path as _rt
        p = _rt('logs', 'gate_observability.jsonl')
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': _t.time(), 'autoid': str(autoid), 'gate': gate, 'state': state, **extra}, ensure_ascii=False) + '\n')
    except Exception:
        logger.debug('gate observability 追加失败', exc_info=True)

def _emit_stat(autoid: str, out: str, channel: str) -> None:
    """emit 出口台账(runtime/logs/emit_stats.jsonl)——打回率的机读事实源
    (E2 基线 48-52% 来自 fastlog 解析;此后量化规则直接聚合本文件)。追加失败静默。"""
    try:
        import time as _t
        ok = not str(out).startswith('error:')
        reason = 'ok'
        if not ok:
            reason = 'other'
            for pat, cls in _EMIT_REASON_PATTERNS:
                if pat in out:
                    reason = cls
                    break
        rec = {'ts': _t.time(), 'autoid': str(autoid), 'ok': ok, 'reason_class': reason, 'channel': channel}
        if reason == 'other':
            rec['error_head'] = str(out)[:80]
        from cex_core.engine.common.runtime_paths import runtime_path as _rt
        p = _rt('logs', 'emit_stats.jsonl')
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception:
        logger.debug('emit_stats 记账失败(忽略)', exc_info=True)
from cex_core.engine.case_compiler.blocks import SSL_CERT_LOAD_KIND
_SSL_CERT_LOAD_FIELDS = frozenset({'kind', 'host', 'vhost', 'vhost_role', 'bound_object', 'cert_group', 'rootca_file', 'interca_file', 'crlca_file', 'pairs', 'sni_domain', 'activate_index', 'activate_cert_type', 'desc'})
_SSL_CERT_PAIR_FIELDS = frozenset({'key_file', 'cert_file', 'index', 'key_passwd', 'sm2_key_type', 'sm2_cert_type'})
_SSL_HOST_ROLES = ('virtual', 'real')
_SSL_IMPORT_FUNCTIONS: dict[tuple[str, str], str] = {('rootca', 'plain'): 'importRootCA', ('rootca', 'sni'): 'importSniRootca', ('interca', 'plain'): 'importInterCA', ('interca', 'sni'): 'importSniInterca', ('crlca', 'plain'): 'importCRLCA', ('crlca', 'sni'): 'importSniCrlca', ('key', 'plain'): 'importKey', ('key', 'sni'): 'importSniKey', ('key', 'sm2'): 'sm2ImportKey', ('key', 'sm2_sni'): 'sm2ImportSniKey', ('cert', 'plain'): 'importCert', ('cert', 'sni'): 'importSniCert', ('cert', 'sm2'): 'sm2ImportCert', ('cert', 'sm2_sni'): 'sm2ImportSniCert'}
_SSL_ACTIVATE_FUNCTION = 'activeCert'
_SSL_CERT_ROOT = 'cert'
_SSL_FUNCTION_REF = 'skeleton:excel_contract.json'
_SSL_TEARDOWN_REF = 'skeleton:command_teardown_atlas.json'

def _leading_literal_words(value: ast.AST) -> tuple[str, ...]:
    """取调用参数在首个动态插值前的字面 token；不解释参数值。"""
    text = ''
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        text = value.value
    elif isinstance(value, ast.JoinedStr):
        chunks: list[str] = []
        for part in value.values:
            if not isinstance(part, ast.Constant) or not isinstance(part.value, str):
                break
            chunks.append(part.value)
        text = ''.join(chunks)
    return tuple(re.findall('[a-z0-9_-]+', text.casefold()))

@functools.lru_cache(maxsize=32)
def _ssl_import_embeds_activation(function: str) -> bool:
    """从当前 mirror AST 判定某证书导入 helper 是否已经执行激活。

    不维护命令字符串表：先从 ``activeCert`` 自己的 ``cmd_config`` 调用机械取得
    激活命令字面前缀，再检查目标 helper 是否发出同前缀调用。mirror 缺失、方法
    缺失或 activeCert 无可解析动作时失败关闭，标准块不会猜测是否需要再激活。
    """
    from cex_core.engine.case_compiler.apv_lang import mirror_src
    source = mirror_src('lib/apv/ssl_comm.py')
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError('SSL framework source cannot be parsed') from exc
    ssl_class = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ssl_comm'), None)
    if ssl_class is None:
        raise ValueError('SSL framework class is unavailable')
    methods = {node.name: node for node in ssl_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def _command_prefixes(method_name: str) -> set[tuple[str, ...]]:
        method = methods.get(method_name)
        if method is None:
            raise ValueError(f'SSL framework method {method_name!r} is unavailable')
        prefixes: set[tuple[str, ...]] = set()
        for node in ast.walk(method):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (node.func.attr == 'cmd_config') and node.args):
                continue
            prefix = _leading_literal_words(node.args[0])
            if prefix:
                prefixes.add(prefix)
        return prefixes
    activation_prefixes = _command_prefixes(_SSL_ACTIVATE_FUNCTION)
    if not activation_prefixes:
        raise ValueError('activeCert has no mechanically readable framework action')
    longest = max((len(prefix) for prefix in activation_prefixes))
    activation_prefixes = {prefix for prefix in activation_prefixes if len(prefix) == longest}
    import_prefixes = _command_prefixes(str(function or ''))
    return any((len(candidate) >= len(activation) and candidate[:len(activation)] == activation for candidate in import_prefixes for activation in activation_prefixes))

def _ssl_contract_parameters(host: str, function: str) -> tuple[set, set, str]:
    """从 Excel 函数契约取某函数的形参名集与必填集；查不到即错。

    只读 `signature`，**不看 status**：条目 disabled 时照样能算出机械序列，随后由
    `expand_blocks` 的契约规则给出如实拒绝（"这个席位上这个函数还没拿到真机收据"），
    比在这里提前伪装成"块坏了"要指对方向。
    """
    try:
        from cex_core.engine.case_compiler.excel_contract import contract_entry, load_excel_contract
        contract = load_excel_contract()
    except Exception as exc:
        return (set(), set(), f'Excel function contract is unavailable: {exc}')
    entry = contract_entry(host, function, contract)
    if entry is None:
        return (set(), set(), f'the framework function {function!r} is absent from the Excel function contract for {host} (contract is generated from the mirror; regenerate it if the framework really ships this helper)')
    signature = entry.get('signature') or {}
    names = {str(p.get('name') or '') for p in signature.get('parameters') or [] if str(p.get('name') or '')}
    required = {str(n) for n in signature.get('required') or []}
    if not names:
        return (set(), set(), f'contract entry for {function!r} carries no signature')
    return (names, required, '')

def _ssl_call_g(host: str, function: str, values: dict) -> tuple[str, str]:
    """按形参名拼 G（关键字实参形态）。

    用关键字而不是位置实参：同一角色的 plain/SNI/sm2 三个变体形参顺序各不相同
    （`importSniKey(vhost, keyfile, domain, id, passwd)` vs
    `sm2ImportSniKey(keyType, vhost, keyFile, domain, index, passwd)`），位置形态
    要在这里复刻一遍顺序＝把生成物里的事实手抄一份，抄错了还静默传错参。
    关键字形态只需形参**名**，顺序留给运行时按签名绑定。
    """
    names, required, error = _ssl_contract_parameters(host, function)
    if error:
        return ('', error)
    unknown = sorted(set(values) - names)
    if unknown:
        return ('', f"{function}: parameter(s) {', '.join(unknown)} are not in the contract signature (it takes {', '.join(sorted(names))})")
    missing = sorted(required - set(values))
    if missing:
        return ('', f"{function}: required parameter(s) {', '.join(missing)} have no value; supply them on the block")
    parts = []
    for name in sorted(values):
        value = values[name]
        if isinstance(value, int) and (not isinstance(value, bool)):
            parts.append(f'{name}={value}')
            continue
        text = str(value)
        if '"' in text:
            return ('', f'{function}: parameter {name} value must not contain a quote')
        parts.append(f'{name}="{text}"')
    return (', '.join(parts), '')

def _ssl_cert_path(group: str, filename: str) -> str:
    parts = [_SSL_CERT_ROOT] + [p for p in (group.strip('/ '), filename.strip('/ ')) if p]
    return '/'.join(parts)
_SSL_MATERIAL_FIELDS = frozenset({'cert_group', 'pairs', 'rootca_file', 'interca_file', 'crlca_file'})

def _prepare_certified_ssl_material(block: dict) -> dict:
    """全未指定材料时绑定 promotion 复验过的默认夹具；部分指定绝不静默改写。"""
    candidate = dict(block)
    if any((field in candidate for field in _SSL_MATERIAL_FIELDS)):
        return candidate
    from cex_core.engine.case_compiler.excel_capability_samples import certified_ssl_release_fixture
    fixture = certified_ssl_release_fixture()
    candidate['cert_group'] = fixture['cert_group']
    candidate['rootca_file'] = fixture['rootca_file']
    candidate['pairs'] = [dict(pair) for pair in fixture['pairs']]
    return candidate

def _certified_ssl_material_error(block: dict) -> str:
    """核对显式/默认材料最终解析路径是否等于当前 release 收据的输入。"""
    from cex_core.engine.case_compiler.excel_capability_samples import certified_ssl_release_fixture
    fixture = certified_ssl_release_fixture()
    expected = fixture['resolved_paths']
    group = str(block.get('cert_group') or '')
    pairs = block.get('pairs') or []
    resolved_keys = [_ssl_cert_path(group, str(pair.get('key_file') or '')) for pair in pairs]
    resolved_certs = [_ssl_cert_path(group, str(pair.get('cert_file') or '')) for pair in pairs]
    rootca = str(block.get('rootca_file') or '').strip()
    resolved_rootca = _ssl_cert_path(group, rootca) if rootca else ''
    unsupported_ca = any((str(block.get(field) or '').strip() for field in ('interca_file', 'crlca_file')))
    altered_pair = any((str(pair.get('key_passwd') or '').strip() or str(pair.get('sm2_key_type') or '').strip() or str(pair.get('sm2_cert_type') or '').strip() for pair in pairs))
    if resolved_keys == list(expected['keys']) and resolved_certs == list(expected['certs']) and (not resolved_rootca or resolved_rootca == str(expected['rootca'])) and (not unsupported_ca) and (not altered_pair) and (int(block.get('activate_index', 1)) == 1):
        return ''
    return f'certificate material is not bound to the promoted same-source release fixture. Do not invent a repository path or certificate filename. Omit cert_group, pairs, rootca_file, interca_file and crlca_file together to use the engine-owned certified default projected in blocks_schema.json. Resolved key(s)={resolved_keys!r}, cert(s)={resolved_certs!r}, rootca={resolved_rootca!r}.'

def _ssl_teardown_commands() -> tuple[list, str]:
    """清场命令取自 build 绑定的 teardown atlas 里 `ssl host` 那条规则。

    规则供给同源律（§26.4）：τ 配对规则读的是同一份 atlas（它由 `scripts.gen_command_teardown_atlas`
    从框架自己的 `lib/apv/clear.py` 机械解析），所以块自带的恢复对与规则的判据同源、
    天然成对，不是"我猜一条清理命令然后祈祷规则认"。
    """
    try:
        from cex_core.engine.case_compiler.tau_coverage import _derivation_data
        _pairs, atlas = _derivation_data()
    except Exception as exc:
        return ([], f'command teardown atlas is unavailable: {exc}')
    for rule in atlas.get('clear_rules') or []:
        prefixes = [str(p) for p in rule.get('prefixes') or []]
        if not any((p == _SSL_HOST_PREFIX for p in prefixes)):
            continue
        cleanup = [str(c) for c in rule.get('cleanup_commands') or [] if str(c).strip()]
        if cleanup:
            return (cleanup, '')
    return ([], f'the teardown atlas carries no cleanup rule for {_SSL_HOST_PREFIX!r}; regenerate it with: python -m scripts.gen_command_teardown_atlas')

def _ssl_start_command(vhost: str) -> tuple[str, str]:
    """从 build 绑定生命周期契约取得启用同一 SSL host 的命令头。"""
    try:
        from cex_core.engine.case_compiler.tau_coverage import _derivation_data
        from cex_core.engine.case_compiler.ssl_lifecycle_contract import load_ssl_lifecycle_contract
        _pairs, atlas = _derivation_data()
        lifecycle = load_ssl_lifecycle_contract(str(atlas.get('device_build') or ''))
    except Exception as exc:
        return ('', f'SSL host start lifecycle is unavailable: {exc}')
    head = str(lifecycle.get('ssl_host_start_head') or '').strip()
    if not head:
        return ('', 'SSL lifecycle contract carries no host start head')
    return (f'{head} "{vhost}"', '')
_SSL_HOST_PREFIX = 'ssl host'

def ssl_certificate_load_blocks(block: dict) -> tuple[list | None, str]:
    """把一个 `SSL_CERT_LOAD` 语法糖块展开成基础组合子序列。

    产出（顺序固定，逐条都能在框架 mirror 的 smoke_test 里找到同形先例）：
      1. CONFIG：`ssl host <role> "<vhost>" <bound_object>` —— 建 SSL 主机，也是 τ 锚点；
      2. STEP：rootca / interca（给了才展）；
      3. STEP：逐对 key → cert（sm2 双证书就是两对，signkey/enckey 各一对）；
      4. STEP：crlca（给了才展）；
      5. 激活：若证书导入 helper 已按 mirror 内嵌激活，不重复调用；否则追加
         ``activeCert``。是否内嵌由当前 mirror AST 机械推导，不由方法名表猜测；
      6. CONFIG：按 build 绑定生命周期契约启用 SSL host；
      7. CONFIG：配对清场，命令取自 teardown atlas 的 `ssl host` 规则。
    断言不在块里：expected 只由六源签发（红线1），块只产配置/动作步，断言由 worker
    按用例语义另写。
    """
    if not isinstance(block, dict):
        return (None, 'SSL_CERT_LOAD block must be an object')
    unknown = sorted(set(block) - _SSL_CERT_LOAD_FIELDS)
    if unknown:
        return (None, f"unsupported field(s): {', '.join(unknown)}")
    from cex_core.engine.case_compiler.blocks import _DUT_HOSTS
    host = str(block.get('host') or _DUT_HOSTS[0]).strip()
    if host not in _DUT_HOSTS:
        return (None, f'host must be one of {_DUT_HOSTS} (the device under test); got {host!r}')
    vhost = str(block.get('vhost') or '').strip()
    if not vhost:
        return (None, 'vhost is required (the SSL host name this case loads certificates onto)')
    role = str(block.get('vhost_role') or _SSL_HOST_ROLES[0]).strip().lower()
    if role not in _SSL_HOST_ROLES:
        return (None, f'vhost_role must be one of {_SSL_HOST_ROLES}; got {role!r}')
    bound = str(block.get('bound_object') or '').strip()
    if not bound:
        return (None, 'bound_object is required (the slb virtual/real object this SSL host binds to)')
    group = str(block.get('cert_group') or '').strip()
    sni = str(block.get('sni_domain') or '').strip()
    desc = str(block.get('desc') or '').strip()
    pairs = block.get('pairs')
    if not isinstance(pairs, list) or not pairs:
        return (None, 'pairs must be a non-empty array of {key_file, cert_file} objects (one entry per key/certificate pair; sm2 sign+enc is two entries)')
    if any((ch in vhost or ch in bound for ch in ('"', '\\'))):
        return (None, 'vhost and bound_object must not contain quotes or backslashes')
    _teardown_cmds, teardown_error = _ssl_teardown_commands()
    if teardown_error:
        return (None, teardown_error)
    out: list = [{'kind': 'CONFIG', 'host': host, 'cmds': [f'{_SSL_HOST_PREFIX} {role} "{vhost}" {bound}'], 'desc': desc or f'create the {role} SSL host {vhost}', 'ref': _SSL_TEARDOWN_REF}]
    certificate_import_functions: list[str] = []

    def _step(function: str, values: dict, note: str) -> str:
        g, error = _ssl_call_g(host, function, values)
        if error:
            return error
        out.append({'kind': 'STEP', 'E': host, 'F': function, 'G': g, 'desc': note, 'ref': _SSL_FUNCTION_REF})
        return ''

    def _ca_values(function: str, path: str) -> dict:
        values: dict = {'vhost': vhost}
        names, _required, error = _ssl_contract_parameters(host, function)
        if error:
            return {}
        values['certFile' if 'certFile' in names else 'certfile'] = path
        if sni and 'domain' in names:
            values['domain'] = sni
        elif sni and 'sni' in names:
            values['sni'] = sni
        return values
    for role_name, field in (('rootca', 'rootca_file'), ('interca', 'interca_file')):
        filename = str(block.get(field) or '').strip()
        if not filename:
            continue
        function = _SSL_IMPORT_FUNCTIONS[role_name, 'sni' if sni else 'plain']
        error = _step(function, _ca_values(function, _ssl_cert_path(group, filename)), f'import the {role_name} certificate onto {vhost}')
        if error:
            return (None, error)
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            return (None, f'pairs[{index}] must be an object')
        pair_unknown = sorted(set(pair) - _SSL_CERT_PAIR_FIELDS)
        if pair_unknown:
            return (None, f"pairs[{index}]: unsupported field(s): {', '.join(pair_unknown)}")
        key_file = str(pair.get('key_file') or '').strip()
        cert_file = str(pair.get('cert_file') or '').strip()
        if not key_file or not cert_file:
            return (None, f'pairs[{index}] requires both key_file and cert_file')
        slot = pair.get('index', 1)
        if not isinstance(slot, int) or isinstance(slot, bool) or slot < 1:
            return (None, f'pairs[{index}].index must be a positive integer')
        passwd = str(pair.get('key_passwd') or '')
        key_type = str(pair.get('sm2_key_type') or '').strip()
        cert_type = str(pair.get('sm2_cert_type') or '').strip()
        if bool(key_type) != bool(cert_type):
            return (None, f'pairs[{index}]: sm2_key_type and sm2_cert_type must be given together (the sm2 variant loads a typed key and its typed certificate as one pair)')
        if key_type:
            variant = 'sm2_sni' if sni else 'sm2'
        else:
            variant = 'sni' if sni else 'plain'
        for role_name, filename, typed in (('key', key_file, key_type), ('cert', cert_file, cert_type)):
            function = _SSL_IMPORT_FUNCTIONS[role_name, variant]
            names, _required, error_sig = _ssl_contract_parameters(host, function)
            if error_sig:
                return (None, error_sig)
            values: dict = {'vhost': vhost}
            for candidate in ('keyfile', 'keyFile', 'certfile', 'certFile'):
                if candidate in names:
                    values[candidate] = _ssl_cert_path(group, filename)
                    break
            else:
                return (None, f"{function}: the contract signature has no key/certificate file parameter (it takes {', '.join(sorted(names))})")
            if typed:
                for candidate in ('keyType', 'certType'):
                    if candidate in names:
                        values[candidate] = typed
                        break
                else:
                    return (None, f'{function}: the contract signature has no sm2 type parameter')
            if sni and 'domain' in names:
                values['domain'] = sni
            for candidate in ('index', 'id'):
                if candidate in names:
                    values[candidate] = slot
                    break
            if passwd and 'passwd' in names:
                values['passwd'] = passwd
            error = _step(function, values, f'import the {role_name} of pair {index + 1} onto {vhost}')
            if error:
                return (None, error)
            if role_name == 'cert':
                certificate_import_functions.append(function)
    crlca_file = str(block.get('crlca_file') or '').strip()
    if crlca_file:
        function = _SSL_IMPORT_FUNCTIONS['crlca', 'sni' if sni else 'plain']
        error = _step(function, _ca_values(function, _ssl_cert_path(group, crlca_file)), f'import the CRL issuer certificate onto {vhost}')
        if error:
            return (None, error)
    try:
        activation_is_embedded = bool(certificate_import_functions) and all((_ssl_import_embeds_activation(function) for function in certificate_import_functions))
    except ValueError as exc:
        return (None, f'cannot derive certificate activation from framework source: {exc}')
    if not activation_is_embedded:
        activate_index = block.get('activate_index', 1)
        if not isinstance(activate_index, int) or isinstance(activate_index, bool) or activate_index < 1:
            return (None, 'activate_index must be a positive integer')
        activate_values: dict = {'vhost': vhost, 'index': activate_index}
        if sni:
            activate_values['sni'] = sni
        cert_type_arg = str(block.get('activate_cert_type') or '').strip()
        if cert_type_arg:
            activate_values['certType'] = cert_type_arg
        error = _step(_SSL_ACTIVATE_FUNCTION, activate_values, f'activate the loaded certificate on {vhost} because the selected certificate-import helper does not embed activation')
        if error:
            return (None, error)
    start_command, start_error = _ssl_start_command(vhost)
    if start_error:
        return (None, start_error)
    out.append({'kind': 'CONFIG', 'host': host, 'cmds': [start_command], 'desc': f'start the SSL host {vhost} after certificate activation', 'ref': _SSL_TEARDOWN_REF})
    out.extend([{'kind': 'STEP', 'E': host, 'F': 'cmd_config', 'G': f'clear ssl host "{vhost}",prompt=abort:', 'desc': f'begin paired teardown for the SSL host {vhost}', 'ref': _SSL_TEARDOWN_REF}, {'kind': 'STEP', 'E': host, 'F': 'cmd_config', 'G': 'YES', 'desc': f'confirm paired teardown for the SSL host {vhost}', 'ref': _SSL_TEARDOWN_REF}])
    return (out, '')

def split_ssl_certificate_load_blocks(block: dict) -> tuple[list | None, list | None, str]:
    """把证书块拆成“前置装载”与“案末恢复”两段。

    ``ssl_certificate_load_blocks`` 保留完整、独立可审计的参考展开；但把它原位
    塞进包含业务访问的 blocks 数组，会在访问前立刻 ``clear ssl host``，等价于
    刚装好证书就删掉。三个生产入口都通过本函数把恢复段延迟到业务断言之后、
    后续依赖对象 teardown 之前，并保持多个证书块按 LIFO 恢复。这里按展开器
    自己铸造的结构拆分，不从描述或命令关键字
    猜边界。
    """
    prepared = _prepare_certified_ssl_material(block)
    expanded, error = ssl_certificate_load_blocks(prepared)
    if error or expanded is None:
        return (None, None, error)
    material_error = _certified_ssl_material_error(prepared)
    if material_error:
        return (None, None, material_error)
    if len(expanded) < 3:
        return (None, None, 'SSL_CERT_LOAD lowering omitted its paired teardown')
    cleanup = expanded[-2:]
    first, second = cleanup
    if not (isinstance(first, dict) and isinstance(second, dict) and (str(first.get('kind') or '').strip().upper() == 'STEP') and (str(first.get('F') or '').strip() == 'cmd_config') and ('prompt=abort:' in str(first.get('G') or '')) and (str(second.get('kind') or '').strip().upper() == 'STEP') and (str(second.get('F') or '').strip() == 'cmd_config') and (str(second.get('G') or '').strip().upper() == 'YES')):
        return (None, None, 'SSL_CERT_LOAD lowering no longer ends in the certified interactive object-scoped teardown pair')
    return (expanded[:-2], cleanup, '')

def _expand_ssl_cert_load_sugar(blocks: list) -> tuple[list | None, str]:
    """把糖块换成基础组合子，并把恢复放到最终业务断言之后。

    确定性、幂等：不含糖块时原样返回同一个列表对象，零行为变化。
    """
    if not any((isinstance(b, dict) and str(b.get('kind') or '').strip().upper() == SSL_CERT_LOAD_KIND for b in blocks)):
        return (blocks, '')
    out: list = []
    deferred_cleanup: list[list] = []
    assertion_kinds = {'OBSERVE_ASSERT', 'CAPTURE_COMPARE', 'OBSERVE_DIST', 'OBSERVE_MEMBER', 'EXPECT_FROM'}
    assertion_indices = [index for index, candidate in enumerate(blocks) if isinstance(candidate, dict) and (str(candidate.get('kind') or '').strip().upper() in assertion_kinds or (str(candidate.get('kind') or '').strip().upper() == 'STEP' and str(candidate.get('E') or '').strip() == 'check_point'))]
    business_anchor = max(assertion_indices) if assertion_indices else len(blocks) - 1

    def _flush_cleanup() -> None:
        for cleanup in reversed(deferred_cleanup):
            out.extend(cleanup)
        deferred_cleanup.clear()
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or str(block.get('kind') or '').strip().upper() != SSL_CERT_LOAD_KIND:
            out.append(block)
        else:
            setup, cleanup, error = split_ssl_certificate_load_blocks(block)
            if error:
                return (None, f'blocks[{index}]({SSL_CERT_LOAD_KIND}): {error}')
            out.extend(setup or [])
            deferred_cleanup.append(cleanup or [])
        if index == business_anchor:
            _flush_cleanup()
    _flush_cleanup()
    return (out, '')

def _reject_unbound_emit_identity(code: str, message: str) -> str:
    """案身份尚不合法时只签工具回执；不使用未验证路径写案级邮箱。"""
    captured = _CURRENT_EMIT_GATE_CODES.get()
    if captured is not None and code not in captured:
        captured.append(code)
    return f"error: [{code}] {message.removeprefix('error:').strip()}"

def _record_emit_error_return(autoid: str, code: str, message: str) -> str:
    """所有失败返回经显式检查点；下层已签具体码时保留原码、不重复兜底。"""
    if _CURRENT_EMIT_GATE_CODES.get():
        return message
    return _reject_compile_gate(autoid, code, message)

def _reject_compile_gate(autoid: str, code: str, message: str, *, detail: str='', step_index: int=-1, stage: str='emit', extra: dict | None=None, failure_observations: list[dict] | None=None) -> str:
    """在拒绝发生点铸造稳定 code，并给契约类错误附上两条合法入口。

    ``stage`` 透传给 mailbox：同一条规则在 emit 与 merge 预检两条路上都会响，
    收账机器按 stage 分批取，混写会让一次 merge 拒绝被下一轮 emit 收成自己的账。

    ``extra``（2026-08-31 单调规则反馈批）：规则在拒绝点签发的结构化随账字段
    （判据项/违例落点/前卷引用这类机读元数据），与 ``detail`` 散文分开落账——
    下一轮 brief 的机读指令只逐字段转写它，不解析散文。键名不得与 mailbox
    基础记录键（ev/aid/gate/detail/step_index/stage/ts/occurrence_id）冲突。
    """
    from cex_core.engine.ist_core.tools.device.structural_gate import StructuralViolation
    if code in {'mutation_contract_invalid', 'provenance_parse_failed', 'provenance_step_count_mismatch', 'assertion_type_invalid', 'assertion_binding_invalid', 'provenance_source_unresolved'} and 'COMPLIANT EMIT PATHS' not in message:
        message = f'{message}\n\n{_emit_contract_paths()}'
    _write_gate_rejections(autoid, [StructuralViolation(code, detail or message, step_index)], stage=stage, extra=extra, failure_observations=failure_observations)
    return message

def _emit_contract_paths() -> str:
    """LLM-facing single-track emit contract; no historical bypass is advertised."""
    return 'COMPLIANT EMIT PATH — IDE typed path only. Provide aligned step provenance; the compiler derives assertion types, ordinals, ledger mode, observation windows, and the engine-issued device build. For an allowed Exempt pragma, mark only the affected check_point step with exempt=true and a closed-set reason_code; omit mutation_requirements. Existing historical artifacts are diagnostic inputs only and cannot select a legacy generation or delivery path.'

def _with_emit_stats(fn):
    import functools

    def _candidate_revision(args, kwargs) -> str:
        """对 compile_emit 的候选 IR 输入取稳定摘要，不把理由文字伪装成新修订。"""
        try:
            bound = inspect.signature(fn).bind_partial(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
        except Exception:
            values = dict(kwargs)
            if args:
                values.setdefault('autoid', args[0])

        def _canonical_json_payload(value):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return {'unparsed_payload': value}
            return value

        def _bounded_workspace_payload(raw_path: str, *, channel: str):
            try:
                from cex_core.engine.ist_core.tools.device._sealed_output import read_bytes
                payload = read_bytes(raw_path, max_bytes=32 * 1024 * 1024)
                return _canonical_json_payload(payload.decode('utf-8'))
            except Exception as exc:
                return {f'unreadable_{channel}': type(exc).__name__}
        blocks_value = values.get('blocks')
        steps_value = values.get('steps')
        steps_path_value = str(values.get('steps_path') or '').strip()
        steps_json_value = values.get('steps_json')
        if blocks_value not in (None, '', []):
            payload = _canonical_json_payload(blocks_value)
        elif steps_value not in (None, []):
            payload = _canonical_json_payload(steps_value)
        elif steps_path_value:
            payload = _bounded_workspace_payload(steps_path_value, channel='steps_path')
        else:
            payload = _canonical_json_payload(steps_json_value)
        provenance_value = values.get('provenance')
        provenance_path_value = str(values.get('provenance_path') or '').strip()
        provenance_json_value = values.get('provenance_json')
        if provenance_value not in (None, '', [], {}):
            provenance_payload = _canonical_json_payload(provenance_value)
        elif provenance_path_value and (not str(provenance_json_value or '').strip()):
            provenance_payload = _bounded_workspace_payload(provenance_path_value, channel='provenance_path')
        else:
            provenance_payload = _canonical_json_payload(provenance_json_value)
        material = {'autoid': values.get('autoid'), 'init_commands': values.get('init_commands'), 'expected_save_variant': values.get('expected_save_variant'), 'payload': payload, 'provenance': provenance_payload}
        raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        _aid = kwargs.get('autoid') or (args[0] if args else '')
        _session = None
        try:
            from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
            _session = current_worker_device_session()
        except Exception:
            _session = None
        _tracks_compile = bool(_session is not None and _session.autoid and (str(_aid or '').strip() == _session.autoid))
        if _tracks_compile and _session.compile_exhausted:
            return 'error: compile_exhausted — the bounded compile strategy reached the shared no-progress threshold; hand the case back with its evidence'
        if _tracks_compile and _session.stop_reason == 'compile_journal_failed':
            return 'error: compile_journal_failed — the prior compile result could not be durably accounted; hand the case back to the engine'
        if _tracks_compile:
            _control_before = _session.control_snapshot()
            _revision = _candidate_revision(args, kwargs)
            _compile_attempt_id = _session.begin_compile_attempt(_revision)
            from cex_core.engine.ist_core.worker_device_context import persist_worker_session_event
            if not persist_worker_session_event(_session, {'ev': 'compile_attempt_started', 'compile_attempt_id': _compile_attempt_id, 'revision_sha256': _revision, 'ts': time.time()}):
                _session.cancel_compile_attempt()
                return 'error: compile attempt journal could not be persisted; the candidate was not executed'
        _gate_token = _CURRENT_EMIT_GATE_CODES.set([])

        def _ensure_rejection_accounted(*, code: str, detail: str) -> None:
            """任何未接专用分支的失败至少落 unclassified，禁止 M5 假零。"""
            if _CURRENT_EMIT_GATE_CODES.get():
                return
            try:
                safe_aid = _safe_output_component(str(_aid or ''), field='autoid')
            except Exception:
                return
            from cex_core.engine.ist_core.tools.device.structural_gate import StructuralViolation
            _write_gate_rejections(safe_aid, [StructuralViolation(code, detail[:400])], stage='emit')
        try:
            try:
                out = fn(*args, **kwargs)
            except Exception as exc:
                _ensure_rejection_accounted(code='compile_exception_unclassified', detail=f'{type(exc).__name__}: compile_emit raised before returning')
                if _tracks_compile:
                    _record = _session.finish_compile_attempt(success=False)
                    _resolved_ok = persist_worker_session_event(_session, {'ev': 'compile_attempt_resolved', **_record, 'error_type': type(exc).__name__, 'ts': time.time()})
                    if not _resolved_ok:
                        _session.restore_control_snapshot(_control_before)
                        with _session._lock:
                            _session.stop_reason = 'compile_journal_failed'
                raise
            _failed = str(out or '').lstrip().lower().startswith('error:')
            if _failed:
                _ensure_rejection_accounted(code='compile_rejected_unclassified', detail=str(out or '')[:400])
            if _tracks_compile:
                _record = _session.finish_compile_attempt(success=not _failed)
                if not persist_worker_session_event(_session, {'ev': 'compile_attempt_resolved', **_record, 'ts': time.time()}):
                    _session.restore_control_snapshot(_control_before)
                    with _session._lock:
                        _session.stop_reason = 'compile_journal_failed'
                    return 'error: compile result journal could not be persisted; the result was not promoted'
            try:
                if kwargs.get('blocks'):
                    _ch = 'blocks'
                elif isinstance(kwargs.get('steps'), list):
                    _ch = 'steps'
                elif (kwargs.get('steps_path') or '').strip():
                    _ch = 'steps_path'
                else:
                    _ch = 'json_string'
                _emit_stat(str(_aid), str(out), _ch)
            except Exception:
                pass
            return out
        finally:
            _CURRENT_EMIT_GATE_CODES.reset(_gate_token)
    return _wrapped

@tool(parse_docstring=True)
@_with_emit_stats
def compile_emit(autoid: str, steps_json: str='', init_commands: str='', out_name: str='', strict_structural: bool=False, provenance_json: str='', expected_save_variant: str='', steps: list[dict[str, Any]] | str | None=None, steps_path: str='', override_frozen_reason: str='', coverage_reduction_reason: str='', provenance: dict | list | str | None=None, provenance_path: str='', blocks: list | str | None=None, command_existence_evidence: str='', ir_gap_reason: str='', raw_reason: str='', mutation_requirements: list | str | None=None, mutation_requirements_path: str='', mechanical_case_sha256: str='', consistency_batch_name: str='') -> str:
    """Produce a structurally correct case.xlsx from a step list (clones the framework-native template; you never deal with template structure/column alignment).

    **When to use**: the semantic design of a single case (config/trigger/assertions) is settled
    and you want to land it as a runnable xlsx.
    **When not to use**: merging multiple cases into one package → ``compile_emit_merged``; and
    don't emit before the assertion form / expected-value provenance is thought through — every
    version rejected by the structural gates burns a round for nothing.
    **Use this instead of hand-rolling openpyxl via run_python** — hand-rolled sheets always get
    the 27-row description area / C=0/C=1 / E-F-G column alignment wrong, so the framework skips
    your case rows (zero check_point, vacuously true pass). This tool guarantees a 100% legal
    structure.

    You only decide the **content**: file-level preconfig commands + each step's
    object/method/data. **Prefer the blocks combinator channel** (native array; the documented
    combinator syntaxes are in the "Prefer typed blocks" section of EXCEL_FUNCTIONS.md, and the
    per-kind required/optional field contract with every refusal message verbatim is machine
    readable in knowledge/data/compile_ref/blocks_schema.json — read one of them before emitting)
    — you
    make only semantic decisions, and the low-level representation (capture three-step
    form/registers/column alignment) is expanded by the tool; shapes like dangling assertions
    cannot be written in the combinator language. ``STEP`` is the validated generic E/F/G/H/I
    combinator for atlas capabilities and remains inside blocks IR. Only fall back to the
    ``steps`` native-array channel (column semantics below) for a shape blocks still cannot
    express; every raw fallback must declare ``ir_gap_reason`` and is recorded as IR debt.

    Blocks carry provenance in place: use ``CONFIG.ref`` for configuration commands,
    ``OBSERVE_ASSERT.cmd_ref`` for the observation command, and
    ``OBSERVE_ASSERT.asserts[].ref`` for each expected value. A manual pointer has exactly
    this form:
    ``manual:<source-file-or-unique-stem>[:<line>|:<line-start>-<line-end>]``.
    A governing-spec pointer uses the same shape against knowledge/data/spec/:
    ``spec:<source-file-or-unique-stem>[:<line>|:<line-start>-<line-end>]``. Spec and
    manual are identity-bound, fallible claims; neither silently outranks the other.
    Claims with the same semantic key are reconciled explicitly, and a content conflict
    becomes NEEDS_DECISION. A device actual judges behavior but never creates expected.
    Line ranges use a hyphen; comma-separated line lists are not supported. Split disjoint
    source locations into separate combinators instead of concatenating locators.
    When an ``OBSERVE_ASSERT.asserts[]`` reference uses ``config_derived:<recipe>``, that
    assertion also requires ``binding_input`` with exactly ``rule_id`` and object-valued
    ``source_input``. The compiler reruns the registered rule over that independent input and
    accepts it only when the derived output equals the assertion tuple; the final G pattern
    cannot sign its own provenance.

    Column semantics (one dict per step):
    - ``E`` object to operate: device-under-test id / check_point (assertion) / test_env (test host) / time (wait)
    - ``F`` method: device→cmd_config (single) | cmds_config (multiple, \\n-separated);
      check_point→found (regex DOTALL) | not_found | abs_found (literal) | found_times (needs count in column I);
      test_env→a host name from the network facts source; time→sleep
    - ``G`` data (**data type = literal text / regex string — not a variable, not a Python expression, not a number**):
      config steps = raw CLI command text; check_point = the expected text/regex to **text-search** in the previous step's output.
      The framework matches G **verbatim** — write a variable name (e.g. init_ip) and it searches for the literal characters "init_ip", never found.
    - ``H`` save_as (optional) / ``I`` input_var (optional): capture + compare — store one observation output, later compare same/different
      (the correct form for session persistence/affinity/rotation). Full usage (the required three-step structure, why a step with H does not update result)
      is in the "Registers and placeholders" section of
      knowledge/data/compile_ref/EXCEL_FUNCTIONS.md.
    - ``desc`` (optional): step description

    check_point automatically checks **the output of the previous non-check_point step**, so an
    output-producing step (show/dig) must come before the assertion. Every case needs at least
    one check_point that will pass (otherwise it is bound to fail on-device).

    Args:
        autoid: case autoid for the first case row column A.
        steps_json: (compat channel) JSON array string. Prefer the ``steps`` native array:
            vendor function-calling serialization leaves trailing garbage after long string
            arguments; the array channel has no such exposure.
        blocks: **Top priority.** Native array of semantic combinators. Use ``STEP`` for a generic
            atlas-validated E/F/G/H/I step; its dispatch target, method arity, execute action,
            capture order, injection placeholder, and provenance pointer are checked before
            expansion. The other kinds provide stronger structure for config, assertions,
            capture/compare, observation, distribution/member checks, and sleep. Provenance
            is embedded in each combinator as documented above; prefer those in-place refs
            over a separate provenance object.
            ``SSL_CERT_LOAD`` loads certificate material onto an SSL host: give the case
            semantics (``vhost``, ``vhost_role``, ``bound_object``, ``cert_group``,
            ``pairs`` of key/certificate files, optional ``rootca_file``/``interca_file``/
            ``crlca_file``, optional ``sni_domain``, optional per-pair ``sm2_key_type``/
            ``sm2_cert_type``) and the engine expands the fixed framework call sequence —
            the import helpers, a separate ``activeCert`` only when the selected helper
            does not already activate according to the current mirror AST, the build-bound
            SSL-host start transition, and the paired teardown taken from the teardown
            atlas. It emits no assertions:
            expected values stay with the identity-bearing sources, so write your own
            assertion steps around it.
        steps: Raw escape hatch. Native array of step dicts (not a JSON string), each with E/F/G
            and optional H/I/desc; use only for a shape blocks cannot express and pass
            ``ir_gap_reason``. Empty reasons fail closed.
        steps_path: Fallback file channel. Path to a JSON file inside the current request's
            workspace/outputs scope (e.g. workspace/outputs/<autoid>/steps.json; content is
            the steps array). Cross-user and non-output paths are rejected. When the steps
            array repeatedly gets trailing garbage / grows too long, fs_write the file first
            and pass its path to bypass argument serialization.
        ir_gap_reason: Required for every raw ``steps``/``steps_path``/``steps_json`` call.
            State the concrete blocks-language shape that is missing. The reason is recorded
            with the capabilities touched. It is not required for blocks, including ``STEP``.
        raw_reason: Deprecated alias of ``ir_gap_reason`` for callers migrating to the canonical
            name. If both are supplied they must be identical.
        override_frozen_reason: Required when the case is frozen by cross-round on-device
            comparison (two consecutive rounds failed with the same signature = the same
            approach is proven ineffective) — one sentence on what you changed this time
            (which kind of assertion/config/trigger). Without it, re-emitting is refused;
            this is not a formality — it prevents slamming the exact same write-up into
            another round.
        command_existence_evidence: Only needed when the command-existence gate reported
            commands missing from the build-bound XML command tree. A manual/SPEC line
            reference may be supplied as a conflicting source claim, and ``dev_help`` text
            is retained as an unverified device_attestation. Neither form grants passage:
            XML absence is a deterministic pre-device terminal. Update the case or restore
            a valid XML projection bound to the same build, then re-emit.
        mutation_requirements: Deprecated compatibility input. New typed cases must omit
            it. The compiler derives natural check_point ordinals, ledger mode, the
            preceding observation-window command, and the engine-issued device build.
            When a controlled flip is not legal, put only ``exempt=true`` and a closed-set
            ``reason_code`` on the affected check_point step; those pragma fields are
            stripped before xlsx emission.
        mutation_requirements_path: Deprecated workspace-file form of
            mutation_requirements; new typed cases must omit it.
        mechanical_case_sha256: Engine-only 64-hex seal of the mechanical_case.json whose
            blocks are being emitted. It binds blocks.kind reachability scope into the lint
            credential; direct tool callers normally omit it.
        consistency_batch_name: Engine-only output batch identity that minted the frozen
            expectation contract. It is meaningful only with mechanical_case_sha256; merge
            readback recovers the same identity from the engine-owned intent contract ref.
        coverage_reduction_reason: Optional author-supplied note about a recompile.
            It is recorded as a declaration, not authorization to change the frozen
            source contract. The compiler compares formatted execution fields and
            reports changes as coverage-unverified; shared command words cannot
            prove equivalent observations. Signed expectation coverage, source and
            operator checks apply independently of this note.
        init_commands: this case's self-contained preconfig, newline separated; empty uses the
            project default. Emitted as the case's own first APV_0/cmds_config step (it shares
            the autoid row), exactly like the merged volume does — not as a file-level C=1 row.
        out_name: output subdir under workspace/outputs; empty uses autoid.
        strict_structural: True enables the structural constraint rule (commands ∈ manual
            allowlist + non-dangling assertions, correct-by-construction); violations are
            rejected with reasons. Default False.
        provenance: Preferred native-object channel, required. Three-layer Provenance IR (dict with a steps array, each step tagged layer one of G/E/V, source with kind and ref) — it is the sole basis for approval without re-retrieval, four-layer on-device attribution, and PASS write-back to the knowledge base; missing means the output is refused. The string channel is measured to fail from serialization trailing garbage; the object channel has no such exposure.
        provenance_json: compat channel, same as above but a JSON string; prefer provenance.
        provenance_path: fallback file channel (path to a JSON file inside workspace, e.g.
            workspace/outputs/<autoid>/prov.json). When the native provenance object keeps
            getting swallowed/nulled by the vendor, fs_write the file first and pass its path.
        expected_save_variant: pass only for config-save/persistence cases (memory|file|all|net).
            If the mindmap says "after running write all ...", pass "all". The persistence gate
            uses it to verify your save command's family was not swapped (write all must not
            become write memory). Leave empty for non-persistence cases.

    Returns:
        Output path + round-trip row stats. An engine-issued worker may optionally use this
        exact single-case artifact in its bounded on-device repair loop. That result is only
        subset evidence; release still requires independent whole-volume verification with
        the exact final artifact SHA.
    """
    autoid = (autoid or '').strip()
    if not autoid:
        return _reject_unbound_emit_identity('autoid_required', 'error: autoid is required')
    try:
        autoid = _safe_output_component(autoid, field='autoid')
        if (out_name or '').strip():
            _safe_output_component(out_name, field='out_name')
    except ValueError as exc:
        return _reject_unbound_emit_identity('output_identity_invalid', f'error: unsafe output identity: {exc}')
    _worker_capability_inventory, _worker_capability_receipt, _capability_identity_error = _worker_bound_capability_inventory()
    if _capability_identity_error:
        return _record_emit_error_return(autoid, 'capability_identity_unbound', f'error: command-existence gate — CAPABILITY_UNKNOWN: {_capability_identity_error}. The worker artifact is refused before lint because its command-tree generation is not mechanically bound.')
    if autoid.isdigit() and len(autoid) < 15:
        return _record_emit_error_return(autoid, 'autoid_truncated', f"error: autoid '{autoid}' looks like a truncated short id (all digits but fewer than 15). Pass the full requirements-system autoid (all 18 digits, copied whole from the mindmap) — a short id baked into the xlsx breaks requirement linkage and framework-report ID chains.")
    _using_blocks = blocks not in (None, '', [])
    _mechanical_case_sha = str(mechanical_case_sha256 or '').strip()
    _consistency_batch_name = str(consistency_batch_name or '').strip()
    _consistency_contract_sha: str | None = None
    _consistency_requirement_proof: dict | None = None
    if _consistency_batch_name and (not _mechanical_case_sha):
        return _reject_compile_gate(autoid, 'consistency_batch_name_requires_sealed_channel', 'error: consistency_batch_name is valid only with the sealed mechanical case channel')
    if _mechanical_case_sha and (not _using_blocks):
        return _reject_compile_gate(autoid, 'mechanical_case_sha256_requires_blocks_channel', 'error: mechanical_case_sha256 is valid only with the blocks channel; raw steps have no blocks.kind scope to bind')
    if _mechanical_case_sha and re.fullmatch('[0-9a-f]{64}', _mechanical_case_sha) is None:
        return _reject_compile_gate(autoid, 'mechanical_case_sha256_malformed', 'error: mechanical_case_sha256 must be 64 lowercase hex characters')
    _reachability_scope: ReachabilityScope = _raw_reachability_scope()
    _raw_requested = not _using_blocks and (steps not in (None, []) or bool((steps_path or '').strip()) or bool(steps_json if isinstance(steps_json, list) else str(steps_json or '').strip()))
    _canonical_gap_reason = (ir_gap_reason or '').strip()
    _alias_gap_reason = (raw_reason or '').strip()
    if _canonical_gap_reason and _alias_gap_reason and (_canonical_gap_reason != _alias_gap_reason):
        return _reject_compile_gate(autoid, 'ir_gap_reason_conflict', 'error: ir_gap_reason and deprecated raw_reason disagree — pass one canonical reason, or make both values identical during migration')
    _gap_reason = _canonical_gap_reason or _alias_gap_reason
    if _raw_requested and (not _gap_reason):
        return _reject_compile_gate(autoid, 'ir_gap_reason_required_for_raw_steps', 'error: raw steps escape hatch requires ir_gap_reason — state the concrete blocks-language shape that cannot be expressed. Use blocks kind=STEP for generic atlas-validated E/F/G/H/I steps; raw steps without a declared IR gap fail closed.')
    if _using_blocks:
        if isinstance(blocks, str):
            try:
                blocks = json.loads(blocks)
            except Exception:
                return _reject_compile_gate(autoid, 'blocks_parse_failed', f'error: case {autoid} blocks arrived as an unparseable string — pass a native array of combinator objects (preferred), or a valid JSON-encoded array string', detail='blocks string could not be parsed as a JSON array')
        if not isinstance(blocks, list):
            return _reject_compile_gate(autoid, 'blocks_type_invalid', f'error: case {autoid} blocks must be a native array (a list of semantic combinators), got ' + type(blocks).__name__, detail=f'blocks value type is {type(blocks).__name__}, expected list')
        if any((isinstance(_b, dict) and str(_b.get('kind') or '').strip().upper() == SSL_CERT_LOAD_KIND for _b in blocks)):
            if _mechanical_case_sha:
                return _reject_compile_gate(autoid, 'blocks_invalid', f'error: case {autoid} uses the {SSL_CERT_LOAD_KIND} combinator together with a sealed mechanical case. The engine expands this combinator inside compile_emit, so the expanded blocks would no longer match the sealed material and the seal comparison would fail. Until the combinator is registered in the blocks expander itself, author the expanded steps in the mechanical case, or emit this case through the unsealed tool_blocks channel.', detail=f'{SSL_CERT_LOAD_KIND} is expanded at emit time and cannot be reconciled with a sealed mechanical case')
            _sugar_blocks, _sugar_error = _expand_ssl_cert_load_sugar(blocks)
            if _sugar_error:
                return _reject_compile_gate(autoid, 'blocks_invalid', f'error: case {autoid} invalid blocks combinator — {_sugar_error}', detail=str(_sugar_error))
            blocks = _sugar_blocks
        from cex_core.engine.case_compiler.blocks import expand_blocks
        _prov_steps = None
        _prov_obj: dict | None = None
        if provenance is not None and isinstance(provenance, dict):
            _prov_obj = dict(provenance)
            _prov_steps = _prov_obj.get('steps')
        elif provenance_json and str(provenance_json).strip():
            try:
                _pj0 = json.loads(str(provenance_json))
                if isinstance(_pj0, dict):
                    _prov_obj = _pj0
                    _prov_steps = _pj0.get('steps')
            except Exception:
                return _reject_compile_gate(autoid, 'provenance_parse_failed', f'error: case {autoid} in blocks mode provenance_json parse failed — pass the native provenance object instead (steps count equal to blocks count, one entry per combinator).', detail='blocks-mode provenance_json could not be parsed')
        if _prov_obj is not None and str(_prov_obj.get('autoid') or '').strip() != autoid:
            return _reject_compile_gate(autoid, 'provenance_autoid_mismatch', f"error: provenance autoid={_prov_obj.get('autoid')!r} does not match compile_emit autoid={autoid!r}", detail='provenance and emit case identities differ')
        _bsteps, _bprov, _berr = expand_blocks(blocks, _prov_steps)
        if _berr:
            return _reject_compile_gate(autoid, 'blocks_invalid', f'error: case {autoid} invalid blocks combinator — {_berr}', detail=str(_berr))
        steps = _bsteps
        try:
            _reachability_scope = _reachability_scope_from_blocks(blocks, mechanical_case_sha256=_mechanical_case_sha)
        except (TypeError, ValueError) as exc:
            return _reject_compile_gate(autoid, 'blocks_reachability_scope_invalid', f'error: case {autoid} could not seal blocks.kind reachability scope — {exc}', detail=str(exc))
        if _mechanical_case_sha:
            _consistency_contract_sha, _consistency_requirement_proof, _consistency_identity_error = _validated_consistency_contract_identity(autoid, mechanical_case_sha256=_mechanical_case_sha, blocks=blocks, consistency_batch_name=_consistency_batch_name)
            if _consistency_identity_error:
                return _reject_compile_gate(autoid, 'consistency_contract_invalid', f'error: case {autoid} linked consistency contract is unavailable or identity-stale — {_consistency_identity_error}', detail=_consistency_identity_error)
        if _prov_obj is not None and _bprov is not None:
            _prov_obj['steps'] = _bprov
            provenance = _prov_obj
            provenance_json = ''
        elif _prov_obj is None and _bprov and ((os.environ.get('IST_PROV_AUTOASSEMBLE') or '1').strip().lower() not in ('0', 'false', 'no')):
            provenance = {'autoid': autoid, 'steps': _bprov}
            if any((isinstance(item, dict) and item.get('assertion_type') is not None for item in _bprov)):
                provenance['assertion_schema'] = 'ist.ide.assertion'
            provenance_json = ''
    _payload: list | None = None
    _src = ''
    if steps not in (None, []):
        if isinstance(steps, list):
            _payload = list(steps)
        else:
            _src = str(steps)
    elif (steps_path or '').strip():
        sp = (steps_path or '').strip()
        try:
            from cex_core.engine.ist_core.tools.device._sealed_output import read_bytes as _read_output_bytes
            _src = _read_output_bytes(sp, max_bytes=16 * 1024 * 1024).decode('utf-8')
        except Exception as e:
            return _record_emit_error_return(autoid, 'steps_source_unreadable', f'error: steps_path read failed: {e}')
    elif isinstance(steps_json, list):
        _payload = steps_json
    else:
        _src = steps_json if isinstance(steps_json, str) else str(steps_json or '')
    if _payload is None:
        if not (_src or '').strip():
            _streak = _emit_fail_streak_bump(autoid)
            _msg = f'error: case {autoid} step payload is empty — none of the four channels blocks/steps/steps_path/steps_json carried valid content (your array argument may have been dropped entirely by vendor serialization). Prefer blocks semantic combinators (native array); use the steps native array for shapes blocks cannot express.'
            if _streak >= 2:
                _msg += f'\n→ Consecutive empty payloads: do not retry as-is. First fs_write the steps array to workspace/outputs/{autoid}/steps.json, then pass steps_path=that path — the file channel bypasses argument serialization and cannot be swallowed.'
            if _streak >= 3:
                _msg += f'\n⚠ {_streak} consecutive empty payloads. If steps_path also fails to get through, stop retrying and copy this error verbatim into your reply for the orchestrator to re-dispatch.'
            return _record_emit_error_return(autoid, 'steps_payload_empty', _msg)
        try:
            _payload = json.loads(_src)
        except Exception as e:
            head = repr(_src[:120])
            tail = repr(_src[-120:]) if len(_src) > 240 else ''
            streak = _emit_fail_streak_bump(autoid)
            msg = f'error: steps_json parse failed: {e}\nargument actually received (len={len(_src)}) head: {head}' + (f'\ntail: {tail}' if tail else '')
            if streak >= 2:
                msg += '\n→ Switch channel: pass steps as a native array (not a JSON string), or first fs_write the steps array to workspace/outputs/<autoid>/steps.json and pass steps_path (only outputs/ under workspace is writable) — neither has the trailing-garbage exposure of the string channel.'
            if streak >= 3:
                msg += f'\n⚠ This case has failed parsing {streak} times in a row — stop retrying as-is; if switching channels still fails, stop and copy this error verbatim into your reply for the orchestrator to handle.'
            return _record_emit_error_return(autoid, 'steps_payload_parse_failed', msg)
    if not isinstance(_payload, list) or not _payload:
        return _reject_compile_gate(autoid, 'steps_payload_invalid', 'error: steps must be a non-empty array (each element a dict with E/F/G)')
    _emit_fail_streak_clear(autoid)
    steps = _payload
    if not _using_blocks:
        try:
            from cex_core.engine.case_compiler.ir_coverage import classify_capability, all_capability_names
            _touched = _raw_capabilities_touched(steps)
            _known = all_capability_names()
            _in_atlas = [c for c in _touched if c in _known]
            _out_of_atlas = [c for c in _touched if c not in _known]
            if _out_of_atlas:
                _expressible = False
            elif _in_atlas:
                _expressible = all((classify_capability(c) == 'covered' for c in _in_atlas))
            else:
                _expressible = None
            _ir_receipt = _write_ir_gap_touch(autoid, _touched, _expressible, out_of_atlas=_out_of_atlas, reason=_gap_reason)
        except Exception as exc:
            logger.warning('ir_gap 记账准备失败，raw emit 已拒绝', exc_info=True)
            return _record_emit_error_return(autoid, 'ir_gap_receipt_unavailable', f'error: raw steps IR-gap accounting could not be prepared; the raw emit was rejected before artifact creation ({type(exc).__name__})')
        if _ir_receipt.get('status') != 'durable':
            return _record_emit_error_return(autoid, 'ir_gap_receipt_not_persisted', f"error: raw steps IR-gap accounting did not return a durable receipt; the raw emit was rejected before artifact creation ({str(_ir_receipt.get('error') or 'sink unavailable')[:160]})")
    try:
        _fz_path = _sh.outputs_root() / autoid / '.frozen.json'
        _fz_present = _fz_path.is_file()
        if not _fz_present and (not (out_name or '').strip()):
            try:
                from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
                emit_signal('frozen_fallback_no_out_name', autoid, source='compile_emit', reason='fallback cannot locate batch facts.jsonl without out_name; frozen status via facts ledger is unverifiable this call (file-based gate unaffected)')
            except Exception:
                pass
        _fz_verdict, _fz_basis, _fz_sig = _frozen_seal_verdict(autoid, _mechanical_case_sha, facts_provider=lambda: _sh.load_facts({'out_name': out_name}))
        if _fz_verdict != 'not_frozen':
            _ov = (override_frozen_reason or '').strip()
            _sig_note = f'; signatures: {_fz_sig}' if _fz_sig else ''
            if _fz_verdict == 'same':
                try:
                    from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
                    emit_signal('frozen_same_method_refused', autoid, source='compile_emit', basis=_fz_basis[:200], declared=bool(_ov))
                except Exception:
                    pass
                return _record_emit_error_return(autoid, 'frozen_same_artifact', f"error: case {autoid} is frozen by cross-round on-device comparison (two consecutive rounds failed with the same signature), and this emit carries the same sealed mechanical case as the frozen attempt ({_fz_basis}{_sig_note}). The digest, not a declaration, is the criterion here: the sheet this emit would write is byte-identical to the one already proven ineffective, so re-running it can only reproduce the same failure. Re-author the mechanical case (different assertion/config/trigger shape); the new seal lifts this rule automatically, no declaration needed. If you judge it an environmental blockage rather than a case defect, check the testbed per ist-verify's stop-loss guidance instead of re-emitting.")
            if _fz_verdict == 'unavailable' and (not _ov):
                try:
                    from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
                    emit_signal('gate_disabled', autoid, source='compile_emit', gate='frozen_seal_digest', reason=f'seal identity unavailable: {_fz_basis}'[:200])
                except Exception:
                    pass
                return _record_emit_error_return(autoid, 'frozen_change_undeclared', f'error: case {autoid} is frozen by cross-round on-device comparison (two consecutive rounds failed with the same signature - the same approach is proven ineffective' + _sig_note + '). The digest criterion could not run here: ' + _fz_basis + ', so this call falls back to the weaker declaration criterion. Pass override_frozen_reason = one sentence on what you changed this time (which kind of assertion/config/trigger). Emitting from a sealed mechanical case makes the digest available and removes this fallback.')
            _declared = _ov or f'engine seal-digest override: {_fz_basis}'
            if _fz_present:
                _fz_corrupt = False
                try:
                    _fz = json.loads(_fz_path.read_text(encoding='utf-8'))
                except Exception:
                    _fz = {}
                    _fz_corrupt = True
                _hist = _fz.get('overrides') or []
                import time as _t1
                _hist.append({'reason': _declared, 'ts': _t1.time(), 'seal_verdict': _fz_verdict, 'basis': _fz_basis[:200]})
                _fz['overrides'] = _hist
                from cex_core.engine.ist_core.tools.device.verifiability_tool import _write_json_atomic
                _write_json_atomic(_fz_path, _fz)
            else:
                _fz_corrupt = False
            try:
                from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
                emit_signal('override_frozen', autoid, source='compile_emit', reason=_declared[:200], seal_verdict=_fz_verdict, basis=_fz_basis[:200], via_fallback=not _fz_present, ledger_rebuilt_from_corrupt=_fz_corrupt)
            except Exception:
                pass
            override_frozen_reason = _declared
    except OSError as _fz_os_err:
        logger.warning('frozen 规则账层文件系统异常(fail-closed 要求 override)', exc_info=True)
        try:
            from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
            emit_signal('gate_disabled', autoid, source='compile_emit', gate='frozen', reason=f'{type(_fz_os_err).__name__}: {_fz_os_err}'[:200])
        except Exception:
            pass
        return _record_emit_error_return(autoid, 'frozen_ledger_unavailable', f'error: case {autoid} - frozen-gate ledger unreadable/unwritable ({type(_fz_os_err).__name__}: {_fz_os_err}); cannot verify frozen status, treating as frozen for safety. Fix the underlying filesystem issue, or pass override_frozen_reason to proceed if you are certain this case is not frozen (the override is recorded once the ledger is writable again).')
    try:
        _ud_path = _sh.outputs_root() / autoid / 'user_decision.json'
        if _ud_path.is_file():
            _ud = json.loads(_ud_path.read_text(encoding='utf-8'))
            _form = str(_ud.get('expected_assertion_form') or '').strip()
            _fvals = [str(s.get('F', '') or '').strip() for s in steps if isinstance(s, dict)]
            _has_h = any((str(s.get('H', '') or '').strip() for s in steps if isinstance(s, dict)))
            _need = {'dist': 'dist' in _fvals, 'member': 'member' in _fvals, 'captured_relation': _has_h}
            if _form in _need and (not _need[_form]):
                return _record_emit_error_return(autoid, 'user_decision_form_mismatch', f'error: case {autoid} violates user decision — the user-approved assertion form is {_form}, which is absent from the produced steps (F values present: {sorted(set(_fvals))}, has H capture: {_has_h}). Rewrite the assertion in the form recorded in user_decision.json; substituting an easier form is not allowed.')
            _kinds = _ud.get('claim_kinds_preserved') or []
            _ordering_kinds = {'new_member_last'}
            try:
                _nd_path = _ud_path.parent / 'needs_decision.json'
                if _nd_path.is_file():
                    _nd = json.loads(_nd_path.read_text(encoding='utf-8'))
                    for _c in _nd.get('claims') or []:
                        if _c.get('ordering_sensitive') and _c.get('claim_kind'):
                            _ordering_kinds.add(str(_c['claim_kind']))
            except Exception:
                pass
            if any((k in _ordering_kinds for k in _kinds)):
                _presents = [s.get('member', {}).get('present') for s in steps if isinstance(s, dict) and str(s.get('F', '') or '').strip() == 'member' and isinstance(s.get('member'), dict)]
                if not (True in _presents and False in _presents):
                    return _record_emit_error_return(autoid, 'user_decision_ordering_missing', f"error: case {autoid} preserves an ordered-trajectory claim (user_decision's claim_kinds_preserved plus the ledger's ordering_sensitive mark) — the product must carry an ordering anchor: in time order, a not_found segment (target pool member set, member declared present=false) followed by a found segment (present=true). Distribution/participation statistics alone cannot prove ordering — that is a semantic downgrade, refused. If the ordering semantics has been proven unverifiable, report the underdetermination as-is to the orchestrator for the user to revise expectations, and update user_decision.json accordingly.")
    except Exception as exc:
        logger.warning('user_decision 规则校验异常(拒绝落卷)', exc_info=True)
        return _record_emit_error_return(autoid, 'user_decision_unreadable', f'error: user_decision credential is unreadable; refusing emit: {type(exc).__name__}: {exc}')
    if provenance is not None and (not (isinstance(provenance, str) and (not provenance.strip()))):
        if isinstance(provenance, (dict, list)):
            provenance_json = json.dumps(provenance, ensure_ascii=False)
        elif isinstance(provenance, str):
            provenance_json = provenance
    elif (provenance_path or '').strip() and (not (provenance_json and provenance_json.strip())):
        _pp = (provenance_path or '').strip()
        try:
            from cex_core.engine.ist_core.tools.device._sealed_output import read_bytes as _read_output_bytes
            provenance_json = _read_output_bytes(_pp, max_bytes=16 * 1024 * 1024).decode('utf-8')
        except Exception as _e:
            return _record_emit_error_return(autoid, 'provenance_source_unreadable', f'error: provenance_path read failed: {_e}')
    if not (provenance_json and provenance_json.strip()):
        return _record_emit_error_return(autoid, 'provenance_required', f'error: case {autoid} missing provenance — pass provenance along with steps (native object with a steps array, each step {{layer: G|E|V, source: {{kind, ref}}}}; aligned one-to-one with the sheet steps). It is the sole basis for approval without re-retrieval, four-layer on-device attribution, and PASS write-back to the knowledge base. layer meaning: G=command skeleton (from footprint/manual), E=environment binding (from topology), V=assertion semantics (from Author/Spec/DefectSpec/Manual/ConfigBinding/CapabilityXml claims). A DefectSpec is only an engine-bound safe projection of a fully resolved bug-to-case declaration; it belongs to the Spec authority group and introduces no new category winner.\n\n' + _emit_contract_paths())
    try:
        json.loads(provenance_json)
    except Exception:
        return _reject_compile_gate(autoid, 'provenance_parse_failed', f'error: case {autoid} provenance parse failed — payload content is withheld. Pass one complete JSON value or use the native object argument.', detail='provenance JSON is not a single complete value')
    from cex_core.engine.case_compiler.distribution_assertion import expand_distribution_steps, expand_provenance_steps_with_plan
    _dist_source_steps = steps
    steps, _dist_plan, _dist_err = expand_distribution_steps(steps)
    if _dist_err:
        return _record_emit_error_return(autoid, 'distribution_declaration_invalid', f'error: case {autoid} distribution-interval assertion declaration is invalid: {_dist_err}')
    if provenance_json and provenance_json.strip():
        try:
            _pj = json.loads(provenance_json)
            if isinstance(_pj, dict):
                _pj['steps'] = expand_provenance_steps_with_plan(_pj.get('steps'), _dist_plan, source_steps=_dist_source_steps, expanded_steps=steps)
                provenance_json = json.dumps(_pj, ensure_ascii=False)
        except ValueError as exc:
            return _record_emit_error_return(autoid, 'distribution_binding_invalid', f'error: case {autoid} ConfigBinding distribution receipt could not be recomputed: {exc}')
        except Exception:
            pass
    from cex_core.engine.case_compiler.membership_assertion import attach_membership_derivation_receipts, expand_membership_steps
    _member_source_steps = steps
    steps, _member_err = expand_membership_steps(steps)
    if _member_err:
        return _record_emit_error_return(autoid, 'membership_declaration_invalid', f'error: case {autoid} hit-membership assertion declaration is invalid: {_member_err}')
    if provenance_json and provenance_json.strip():
        try:
            _pj = json.loads(provenance_json)
            if isinstance(_pj, dict):
                _pj['steps'] = attach_membership_derivation_receipts(_pj.get('steps'), _member_source_steps, steps)
                provenance_json = json.dumps(_pj, ensure_ascii=False)
        except ValueError as exc:
            return _record_emit_error_return(autoid, 'membership_binding_invalid', f'error: case {autoid} ConfigBinding membership receipt could not be recomputed: {exc}')
        except Exception:
            pass
    if provenance_json and provenance_json.strip():
        from cex_core.engine.case_compiler.provenance_ir import backfill_efg as _preflight_backfill_efg, check_runtime_consistency as _preflight_runtime_consistency, check_source_locators as _preflight_check_source_locators, compile_expect_authority as _preflight_compile_expect_authority, parse_provenance as _preflight_parse_provenance
        try:
            _preflight_raw = json.loads(provenance_json)
        except Exception:
            _preflight_raw = None
        if isinstance(_preflight_raw, dict):
            for _raw_step in _preflight_raw.get('steps', []):
                _raw_source = _raw_step.get('source') if isinstance(_raw_step, dict) else None
                if isinstance(_raw_source, dict) and str(_raw_source.get('kind') or '') == 'poison_confirmed':
                    from cex_core.engine.case_compiler.package_advisories import validate_package_expect_reference
                    _asset_id = str(_raw_source.get('ref') or '-')
                    _package_error = validate_package_expect_reference(_asset_id, 'poison_confirmed')
                    return _reject_compile_gate(autoid, 'package_reference_denied', _package_error, detail=_package_error)
        _preflight_case = _preflight_parse_provenance(provenance_json)
        if _preflight_case is None:
            try:
                json.loads(provenance_json)
                _bad = 'JSON parses but the structure does not conform (need {autoid, steps:[{layer,source:{kind,ref}},…]})'
            except Exception as _je:
                _bad = f'the JSON itself is broken: {_je}'
            return _reject_compile_gate(autoid, 'provenance_parse_failed', f'error: case {autoid} provenance parse failed — {_bad}; payload content is withheld. Pass provenance as a native object argument; do not serialize a JSON string into another string channel.', detail=_bad)
        _preflight_case.autoid = autoid
        if not _preflight_backfill_efg(_preflight_case, steps):
            return _reject_compile_gate(autoid, 'provenance_step_count_mismatch', f'error: case {autoid} provenance step count ({len(_preflight_case.steps)}) does not match emit steps count ({len(steps)}). Provide exactly one source entry per final step.', detail=f'provenance steps={len(_preflight_case.steps)} emit steps={len(steps)}')
        _preflight_problems = _preflight_check_source_locators(_preflight_case, outputs_root=_sh.outputs_root()) + _preflight_runtime_consistency(_preflight_case) + _preflight_compile_expect_authority(_preflight_case)
        if _preflight_problems:
            _package_problem = next((problem for problem in _preflight_problems if problem.startswith(('E_PACKAGE_REFERENCE_DENIED', 'E_PACKAGE_INDEX_UNAVAILABLE'))), '')
            if _package_problem:
                return _reject_compile_gate(autoid, 'package_reference_denied', _package_problem, detail=_package_problem)
            return _reject_compile_gate(autoid, 'provenance_source_unresolved', 'error: case {} violates the provenance/no-fabrication contract:\n  - '.format(autoid) + '\n  - '.join(_preflight_problems) + '\n\nEvery command/method/action and expected value needs a resolvable source receipt. For values unknowable offline, use <RUNTIME> with source.kind=device_runtime.', detail='\n'.join(_preflight_problems))
    _mutation_value = mutation_requirements
    if (mutation_requirements_path or '').strip() and _mutation_value in (None, '', []):
        _frp = str(mutation_requirements_path).strip()
        try:
            from cex_core.engine.ist_core.tools.device._sealed_output import read_json as _read_output_json
            _mutation_value = _read_output_json(_frp, max_bytes=16 * 1024 * 1024)
        except Exception as exc:
            return _reject_compile_gate(autoid, 'mutation_contract_invalid', f'error: mutation_requirements_path could not be read: {exc}', detail=f'mutation requirements path unreadable: {type(exc).__name__}')
    from cex_core.engine.case_compiler.mutation_testing import compile_mutation_plan
    _prov_for_mutation = None
    if provenance_json and provenance_json.strip():
        try:
            _candidate_prov = json.loads(provenance_json)
            if isinstance(_candidate_prov, dict):
                _prov_for_mutation = _candidate_prov
        except Exception:
            pass
    if isinstance(_prov_for_mutation, dict) and (not _prov_for_mutation.get('assertion_schema')) and (not _using_blocks):
        return _reject_compile_gate(autoid, 'assertion_type_missing', f'error: case {autoid} raw provenance is untyped; project it to ist.ide.assertion before compile_emit', detail='raw provenance omitted assertion_schema')
    if isinstance(_prov_for_mutation, dict) and (not _prov_for_mutation.get('assertion_schema')):
        try:
            from cex_core.engine.case_compiler.provenance_ir import CaseProvenance, backfill_efg, synthesize_assertion_types
            _typed_case = CaseProvenance.from_dict(_prov_for_mutation)
            _typed_case.autoid = autoid
            _typed_errors: list[str] = []
            if not backfill_efg(_typed_case, steps):
                _typed_errors.append('provenance steps are not aligned with the final emit steps')
            else:
                _typed_errors.extend(synthesize_assertion_types(_typed_case))
            if _typed_errors:
                return _reject_compile_gate(autoid, 'assertion_type_derivation_failed', f'error: case {autoid} cannot enter the typed IDE path:\n  - ' + '\n  - '.join(_typed_errors), detail='\n'.join(_typed_errors))
            else:
                _prov_for_mutation = _typed_case.to_dict()
        except Exception as exc:
            return _reject_compile_gate(autoid, 'assertion_type_derivation_failed', f'error: case {autoid} typed assertion derivation failed: {exc}', detail=f'typed assertion derivation failed: {type(exc).__name__}')
    _mutation_required = bool(isinstance(_prov_for_mutation, dict) and accepts_schema(_prov_for_mutation.get('assertion_schema'), 'ist.ide.assertion'))
    _device_build = ''
    _device_build_source = ''
    try:
        from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
        _mutation_session = current_worker_device_session()
        if _mutation_session is not None:
            _device_build = str(_mutation_session.expected_build or '').strip()
            if _device_build:
                _device_build_source = 'worker_session'
    except Exception:
        pass
    if not _device_build:
        try:
            from cex_core.engine.case_compiler.vendor_stdlib import configured_device_os_build
            _device_build = str(configured_device_os_build() or '').strip()
            if _device_build:
                _device_build_source = 'configured_fallback'
        except Exception:
            pass
    _binding_before_mutation = _binding_steps_from_provenance(_prov_for_mutation.get('steps') or [] if isinstance(_prov_for_mutation, dict) else [])
    steps, _prov_for_mutation, _mutation_receipt, _mutation_error = compile_mutation_plan(steps, _prov_for_mutation, _mutation_value, required=_mutation_required, derive_defaults=_mutation_required, device_build=_device_build, device_build_source=_device_build_source)
    if _mutation_error:
        return _reject_compile_gate(autoid, 'mutation_contract_invalid', f'error: case {autoid} has an invalid IDE mutation contract — {_mutation_error}', detail=_mutation_error)
    if _prov_for_mutation is not None:
        provenance_json = json.dumps(_prov_for_mutation, ensure_ascii=False)
    try:
        from cex_core.engine.case_compiler.case_ir import FileIR
        from cex_core.engine.case_compiler.xlsx_emit import emit_xlsx
        from cex_core.engine.case_compiler.config import get_config
    except Exception as e:
        return _record_emit_error_return(autoid, 'compiler_module_unavailable', f'error: failed to load compiler modules: {e}')
    init_g = init_commands.strip() if init_commands.strip() else get_config().default_init_g()
    _fixed_literal_n = 0
    if '\\n' in init_g:
        init_g = init_g.replace('\\n', '\n')
        _fixed_literal_n += 1
    if isinstance(steps, list):
        for _s in steps:
            if not isinstance(_s, dict):
                continue
            if str(_s.get('E', '')).strip() in ('APV_0', 'test_env'):
                _g = _s.get('G')
                if isinstance(_g, str) and '\\n' in _g:
                    _s['G'] = _g.replace('\\n', '\n')
                    _fixed_literal_n += 1
    _fw_comma = 0
    if '，' in init_g:
        _fw_comma += init_g.count('，')
        init_g = init_g.replace('，', ',')
    if isinstance(steps, list):
        for _s in steps:
            if not isinstance(_s, dict) or str(_s.get('E', '')).strip() == 'check_point':
                continue
            _g = _s.get('G')
            if isinstance(_g, str) and '，' in _g:
                _fw_comma += _g.count('，')
                _s['G'] = _g.replace('，', ',')
    if _fw_comma:
        try:
            from cex_core.engine.ist_core.memory.footprint.signals import emit_signal
            emit_signal('fullwidth_comma_normalized', autoid, source='compile_emit', count=_fw_comma)
        except Exception:
            logger.debug('fullwidth_comma_normalized signal 落盘失败', exc_info=True)
    _init_case_step = [{'D': '初始化配置', 'desc': '初始化配置', 'E': 'APV_0', 'F': 'cmds_config', 'G': init_g}] if init_g.strip() else []
    _unreachable_admission = _unreachable_ip_admission(autoid, steps, init=init_g)
    gate = _gate_unreachable_ips(autoid, steps, init=init_g)
    if gate:
        return _record_emit_error_return(autoid, 'unreachable_ips', f'error: {gate}')
    _author_ip_literals = list(_unreachable_admission.get('author_ip_literals') or [])
    gate = _gate_unreachable_listener(autoid, steps, init=init_g, reachability_scope=_reachability_scope, author_ip_literals=_author_ip_literals)
    if gate:
        return _record_emit_error_return(autoid, 'unreachable_listener', f'error: {gate}')
    gate = _gate_driver_reachability(autoid, steps, author_ip_literals=_author_ip_literals)
    if gate:
        return _record_emit_error_return(autoid, 'driver_reachability', f'error: {gate}')
    gate = _gate_destructive_commands(autoid, steps, init=init_g)
    if gate:
        return _record_emit_error_return(autoid, 'destructive_commands', f'error: {gate}')
    gate = _gate_save_restore_pairing(autoid, steps, init=init_g, expected_save_variant=_intent_save_variant(autoid) or expected_save_variant)
    if gate:
        return _record_emit_error_return(autoid, 'save_restore_pairing', f'error: {gate}')
    from cex_core.engine.ist_core.tools.device.structural_gate import check_crash_gates_mandatory
    _gate_steps = list(steps) if isinstance(steps, list) else steps
    if isinstance(_gate_steps, list) and (init_g or '').strip():
        _gate_steps = [{'D': '初始化配置', 'E': 'APV_0', 'F': 'cmds_config', 'G': init_g}] + _gate_steps
    from cex_core.engine.ist_core.compile_engine.emit_failure_evidence import checker_prerequisites, structural_observations
    _structural_prerequisites = checker_prerequisites()
    _ftres = check_crash_gates_mandatory(_gate_steps)
    if _ftres.disabled:
        _write_gate_disabled(autoid, _ftres.disabled)
    if not _ftres.ok:
        _write_gate_rejections(autoid, _ftres.violations, failure_observations=structural_observations(_gate_steps, _ftres, checked_prerequisites=_structural_prerequisites))
        return _record_emit_error_return(autoid, 'structural_crash_gate_rejected', f'error: {_ftres.render(autoid)}')
    gate = _gate_command_existence(autoid, steps, init=init_g, evidence=command_existence_evidence, device_build=_device_build, precedent_passes=_verified_precedent_commands(_preflight_case), inventory=_worker_capability_inventory, capability_receipt=_worker_capability_receipt)
    if gate:
        return _record_emit_error_return(autoid, 'command_existence_rejected', gate)
    gate = _gate_tau_coverage(autoid, steps, init=init_g, device_build=_device_build)
    if gate:
        return _record_emit_error_return(autoid, 'tau_coverage_rejected', gate)
    gate = _gate_sleep_budget(autoid, steps)
    if gate:
        return _record_emit_error_return(autoid, 'sleep_budget_rejected', gate)
    if strict_structural:
        from cex_core.engine.ist_core.tools.device.structural_gate import check_structural_constraints
        sresult = check_structural_constraints(autoid, steps, init=init_g)
        if not sresult.ok:
            return _record_emit_error_return(autoid, 'structural_constraints_rejected', f'error: {sresult.render(autoid)}')
    case, info = _steps_to_caseir(autoid, [*_init_case_step, *steps])
    if case is None:
        return _record_emit_error_return(autoid, 'case_ir_invalid', f'error: {info}')
    try:
        sub, out = _safe_case_path(out_name or autoid, field='out_name')
    except ValueError as exc:
        return _record_emit_error_return(autoid, 'output_identity_invalid', f'error: unsafe output identity: {exc}')
    fir = FileIR(feature=sub, author='IST-Core-agent', init_rows=[], cases=[case, _build_sentinel()], module='ist_smoke')
    _validated_prov = None
    _direction_comparison_note = ''
    _direction_disclosures: list[dict] | None = None
    if provenance_json and provenance_json.strip():
        from cex_core.engine.case_compiler.provenance_ir import backfill_efg, compile_assertion_types, compile_expect_authority, check_runtime_consistency, check_source_locators, parse_provenance
        try:
            _raw_provenance = json.loads(provenance_json)
        except Exception:
            _raw_provenance = None
        if isinstance(_raw_provenance, dict):
            for _raw_step in _raw_provenance.get('steps', []):
                _raw_source = _raw_step.get('source') if isinstance(_raw_step, dict) else None
                if isinstance(_raw_source, dict) and str(_raw_source.get('kind') or '') == 'poison_confirmed':
                    from cex_core.engine.case_compiler.package_advisories import validate_package_expect_reference
                    _asset_id = str(_raw_source.get('ref') or '-')
                    _package_error = validate_package_expect_reference(_asset_id, 'poison_confirmed')
                    return _reject_compile_gate(autoid, 'package_reference_denied', _package_error, detail=_package_error)
        _validated_prov = parse_provenance(provenance_json)
        if _validated_prov is None:
            try:
                json.loads(provenance_json)
                _bad = 'JSON parses but the structure does not conform (need {autoid, steps:[{layer,source:{kind,ref}},…]})'
            except Exception as _je:
                _bad = f'the JSON itself is broken: {_je}'
            return _reject_compile_gate(autoid, 'provenance_parse_failed', f'error: case {autoid} provenance parse failed — {_bad}; payload content is withheld. Pass provenance as a native object argument; do not serialize a JSON string into another string channel.', detail=_bad)
        if str(_validated_prov.autoid or '').strip() != autoid:
            return _reject_compile_gate(autoid, 'provenance_autoid_mismatch', f'error: provenance autoid={_validated_prov.autoid!r} does not match compile_emit autoid={autoid!r}', detail='provenance and emit case identities differ')
        _validated_prov.autoid = autoid
        if not backfill_efg(_validated_prov, steps):
            return _reject_compile_gate(autoid, 'provenance_step_count_mismatch', f'error: case {autoid} provenance step count ({len(_validated_prov.steps)}) does not match emit steps count ({len(steps)}). Provide exactly one source entry per final step.', detail=f'provenance steps={len(_validated_prov.steps)} emit steps={len(steps)}')
        _current_case_run_ids: tuple[str, ...] = ()
        try:
            from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
            _worker_session = current_worker_device_session()
            if _worker_session is not None:
                _current_case_run_ids = tuple((value for value in (str(_worker_session.current_attempt_id or '').strip(),) if value))
        except Exception:
            pass
        assertion_type_problems = compile_assertion_types(_validated_prov, current_run_ids=_current_case_run_ids)
        if assertion_type_problems:
            return _reject_compile_gate(autoid, 'assertion_type_invalid', 'error: case {} has invalid IDE assertion types:\n  - '.format(autoid) + '\n  - '.join(assertion_type_problems), detail='\n'.join(assertion_type_problems))
        spec_identity_problem = _gate_governing_spec_identity(autoid, _validated_prov, mutation_receipt=_mutation_receipt)
        if spec_identity_problem:
            return _reject_compile_gate(autoid, 'governing_spec_identity_invalid', spec_identity_problem, detail=spec_identity_problem)
        manual_demotion = _gate_manual_expect_conditional(autoid, _validated_prov)
        if manual_demotion:
            return _reject_compile_gate(autoid, 'manual_expect_demoted', manual_demotion, detail=manual_demotion)
        provenance_problems = check_source_locators(_validated_prov, outputs_root=_sh.outputs_root()) + check_runtime_consistency(_validated_prov) + compile_expect_authority(_validated_prov)
        if provenance_problems:
            _package_problem = next((problem for problem in provenance_problems if problem.startswith(('E_PACKAGE_REFERENCE_DENIED', 'E_PACKAGE_INDEX_UNAVAILABLE'))), '')
            if _package_problem:
                return _reject_compile_gate(autoid, 'package_reference_denied', _package_problem, detail=_package_problem)
            return _reject_compile_gate(autoid, 'provenance_source_unresolved', 'error: case {} violates the provenance/no-fabrication contract:\n  - '.format(autoid) + '\n  - '.join(provenance_problems) + '\n\nEvery command/method/action and expected value needs a resolvable source receipt. For values unknowable offline, use <RUNTIME> with source.kind=device_runtime.', detail='\n'.join(provenance_problems))
        try:
            from cex_core.engine.case_compiler.assertion_binding import AssertionBindingError, compile_binding as compile_assertion_binding
            binding_steps = _binding_steps_from_provenance(_validated_prov.to_dict().get('steps') or [])
            candidate_sha = hashlib.sha256(json.dumps(binding_steps, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
            compile_assertion_binding({autoid: binding_steps}, artifact_sha256_value=candidate_sha, legacy_mode=False)
        except AssertionBindingError as exc:
            _engine_reject = engine_inserted_binding_rejection(autoid, exc, _mutation_receipt, before_binding_steps=_binding_before_mutation, binding_steps=binding_steps)
            if _engine_reject:
                return _reject_compile_gate(autoid, 'assertion_binding_invalid', _engine_reject, detail=str(exc))
            return _reject_compile_gate(autoid, 'assertion_binding_invalid', f'error: case {autoid} has invalid explicit observation/assertion binding: {exc}', detail=str(exc))
    try:
        from cex_core.engine.case_compiler import recompile_comparison as _recompile
        _prior_compilation = _recompile.capture_previous(Path(out))
    except Exception:
        _prior_compilation = {'status': 'unavailable', 'reason_code': 'comparison_producer_unavailable'}
    try:
        stats = emit_xlsx(fir, out, trusted_outputs_root=_sh.outputs_root())
    except Exception as e:
        return _record_emit_error_return(autoid, 'xlsx_emit_failed', f'error: emit failed: {e}')
    try:
        from cex_core.engine.ist_core.tools.device.run_case import _MAX_XLSX_BYTES, _read_regular_under_root
        _out_relative = Path(out).relative_to(_sh.outputs_root())
        _linted_xlsx_payload, _linted_xlsx_stat = _read_regular_under_root(_sh.outputs_root(), _out_relative, max_bytes=_MAX_XLSX_BYTES)
    except Exception as exc:
        return _record_emit_error_return(autoid, 'lint_snapshot_unavailable', f'error: emitted case {autoid} could not be fixed as an immutable lint snapshot; no credential was issued: {exc}')
    from cex_core.engine.ist_core.tools.device.structural_gate import lint_xlsx_case
    _finished_lint = lint_xlsx_case(BytesIO(_linted_xlsx_payload))
    if _finished_lint.disabled:
        _write_gate_disabled(autoid, _finished_lint.disabled, stage='emit_finished_sheet')
    if _finished_lint.advisories:
        _write_gate_advisories(autoid, _finished_lint.advisories, stage='emit_finished_sheet')
    if not _finished_lint.ok:
        _write_gate_rejections(autoid, _finished_lint.violations, stage='emit_finished_sheet')
        try:
            (out.parent / '.grade_credential.json').unlink(missing_ok=True)
        except OSError:
            logger.warning('坏卷 lint 凭证清理失败(autoid=%s)', autoid, exc_info=True)
        return _record_emit_error_return(autoid, 'finished_sheet_lint_rejected', 'error: ' + _finished_lint.render(autoid))
    _mutation_path = out.parent / 'case.mutation.json'
    if _mutation_receipt.get('schema'):
        try:
            _mutation_receipt = {**_mutation_receipt, 'autoid': autoid, 'xlsx_sha256': hashlib.sha256(_linted_xlsx_payload).hexdigest()}
            _durable_json_replace(_mutation_path, _mutation_receipt)
            from cex_core.engine.case_compiler.mutation_testing import clear_mutation_credential, mutation_receipt_ready, publish_mutation_credential
            _mutation_credential_root = _sh.project_root() / 'runtime' / 'mutation_credentials'
            from cex_core.engine.case_compiler.mutation_testing import mutation_receipt_run_ready
            if mutation_receipt_run_ready(_mutation_receipt, _mutation_receipt['xlsx_sha256']):
                publish_mutation_credential(_mutation_receipt, _mutation_credential_root)
            else:
                clear_mutation_credential(autoid, _mutation_credential_root)
        except Exception as exc:
            try:
                (out.parent / '.grade_credential.json').unlink(missing_ok=True)
            except OSError:
                pass
            return _record_emit_error_return(autoid, 'mutation_receipt_write_failed', f'error: case {autoid} mutation receipt write failed; no lint credential was issued: {exc}')
    elif _mutation_path.exists():
        try:
            _mutation_path.unlink()
        except OSError as exc:
            return _record_emit_error_return(autoid, 'stale_mutation_receipt_remove_failed', f'error: case {autoid} stale mutation receipt could not be removed; no lint credential was issued: {exc}')
    if (override_frozen_reason or '').strip():
        _write_frozen_override_ack(autoid, override_frozen_reason, out)
    prov_note = ''
    prov_target = out.parent / 'case.provenance.json'
    if _validated_prov is not None:
        try:
            receipt_sha = _durable_json_replace(prov_target, _validated_prov.to_dict())
            gn = len(_validated_prov.layer_steps('G'))
            en = len(_validated_prov.layer_steps('E'))
            vn = len(_validated_prov.layer_steps('V'))
            prov_note = f'\nprovenance side-mounted: G={gn} E={en} V={vn} steps; source receipts resolved and sidecar_sha256={receipt_sha}.'
        except Exception as e:
            try:
                (out.parent / '.grade_credential.json').unlink(missing_ok=True)
            except OSError:
                pass
            return _record_emit_error_return(autoid, 'provenance_receipt_write_failed', f'error: case {autoid} provenance receipt write failed; no lint credential was issued: {e}')
    elif prov_target.exists():
        try:
            prov_target.unlink()
            prov_note = '\n⚠ No provenance_json was provided this time; the stale old case.provenance.json was deleted (so grade will not be lenient by checking against stale sources). On redo, re-submit provenance along with steps.'
        except Exception as e:
            prov_note = f'\n⚠ An old provenance exists but deletion failed: {e} (clean it up manually to keep grade from misusing stale sources).'
    _fix_note = ''
    if _fixed_literal_n:
        _fix_note = f'\n⚠ Auto-corrected {_fixed_literal_n} literal backslash-n occurrence(s) in command payloads to real newlines (in command context it can only be a miswritten newline; in a JSON string a single backslash n is enough — a double backslash becomes literal characters).'
    try:
        import time as _time
        _credp = Path(out).parent / '.grade_credential.json'
        _current_xlsx_payload, _ = _read_regular_under_root(_sh.outputs_root(), _out_relative, max_bytes=_MAX_XLSX_BYTES)
        if _current_xlsx_payload != _linted_xlsx_payload:
            raise OSError('case.xlsx changed after finished-sheet lint')
        _xlsx_sha256 = hashlib.sha256(_linted_xlsx_payload).hexdigest()
        _cred = {'autoid': autoid, 'xlsx': (Path('workspace') / 'outputs' / _out_relative).as_posix(), 'xlsx_sha256': _xlsx_sha256, 'verdict': 'PASS', 'source': 'lint', 'lint_ok': True, 'verdict_ts': _time.time(), 'reachability_scope': _reachability_scope, 'unreachable_ip_admission': {'schema': UNREACHABLE_IP_ADMISSION_SCHEMA, 'author_unreachable_values': list(_unreachable_admission.get('author_unreachable_values') or []), 'author_ip_literals': list(_unreachable_admission.get('author_ip_literals') or [])}, 'consistency_contract_sha256': _consistency_contract_sha, 'consistency_requirement_proof': _consistency_requirement_proof}
        if _worker_capability_receipt is not None:
            _cred['capability_consumed'] = {**_worker_capability_receipt, 'autoid': autoid}
        if _validated_prov is not None:
            from cex_core.engine.case_compiler.provenance_ir import seal_defect_spec_compilations, seal_expectation_directions
            _defect_seal_problems = seal_defect_spec_compilations(_validated_prov, outputs_root=_sh.outputs_root())
            if _defect_seal_problems:
                return _record_emit_error_return(autoid, 'defect_spec_seal_invalid', f'error: case {autoid} DefectSpec compilation seal failed; no credential was issued:\n  - ' + '\n  - '.join(_defect_seal_problems))
            try:
                from cex_core.engine.ist_core.tools.device.mechanical_case_submit_tool import _frozen_contract
                _seal_contract, _, _seal_violations = _frozen_contract(autoid, _sh.outputs_root(), _sh.project_root())
                if _seal_violations:
                    _seal_contract = None
            except Exception:
                _seal_contract = None
            _direction_disclosures = []
            _direction_failure_observations = []
            _direction_problems = seal_expectation_directions(_validated_prov, outputs_root=_sh.outputs_root(), project_root=_sh.project_root(), contract=_seal_contract, disclosures=_direction_disclosures, failure_observations=_direction_failure_observations)
            if _direction_disclosures:
                for _disclosure in _direction_disclosures:
                    logger.info('expectation direction token comparison disclosed (autoid=%s): %s', autoid, _disclosure)
                _direction_comparison_note = '\ndirection-token comparison: per-assertion semantic direction remains unverified; this observation is not a verdict.\n' + json.dumps(_direction_disclosures, ensure_ascii=False)
            else:
                _direction_comparison_note = ''
            if _direction_problems:
                return _reject_compile_gate(autoid, 'expectation_direction_rewrite', f'error: case {autoid} expectation-direction seal check failed; no credential was issued:\n  - ' + '\n  - '.join(_direction_problems), detail='; '.join((str(p) for p in _direction_problems))[:400], extra={'problems': [str(p)[:300] for p in _direction_problems[:8]]}, failure_observations=[{'check': 'expectation_direction_seal', 'outcome': 'rejected', 'subject': {'kind': 'seal_comparison', 'observations': _direction_failure_observations}}])
        _durable_json_replace(_credp, _cred)
    except Exception as exc:
        logger.warning('lint 凭证落盘失败(autoid=%s)', autoid, exc_info=True)
        return _record_emit_error_return(autoid, 'lint_receipt_write_failed', f'error: case {autoid} lint credential write failed; no credential was issued: {exc}')
    try:
        _comparison = _recompile.persist_comparison(Path(out), autoid=autoid, current=_linted_xlsx_payload, previous=_prior_compilation, declaration=coverage_reduction_reason, direction_disclosures=_direction_disclosures)
    except Exception:
        logger.warning('重编卷面比较不可用(autoid=%s)', autoid, exc_info=True)
        _comparison = {'status': 'unavailable'}
    _gate_observability(autoid, gate='monotonicity', state=str(_comparison['status']))
    _comparison_note = ''
    if _comparison.get('status') in {'coverage_unverified', 'unavailable'}:
        _comparison_note = '\nrecompile comparison: semantic coverage equivalence is unverified. A changed program is not proof of either lost or preserved coverage. The current frozen expectation contract remains independently enforced.'
    _findings = mechanical_findings_for_emit(autoid, blocks, init_commands)
    try:
        from cex_core.engine.case_compiler.device_characteristics import MECHANICAL_FINDINGS_SCHEMA as _MF_SCHEMA
        _durable_json_replace(Path(out).parent / MECHANICAL_FINDINGS_SIDECAR_NAME, {'schema': _MF_SCHEMA, 'autoid': autoid, 'xlsx_sha256': _xlsx_sha256, 'findings': _findings})
    except Exception:
        logger.warning('交卷机械发现落盘失败(autoid=%s)', autoid, exc_info=True)
    try:
        _findings_note = _render_mechanical_findings(_findings)
    except Exception:
        logger.warning('交卷机械发现渲染失败(autoid=%s)', autoid, exc_info=True)
        _findings_note = ''
    return f'=== compile_emit ===\nproduced structurally-correct xlsx (cloned from the framework template): {out}\ncase={autoid}  steps={len(case.steps)}  check_points=present\nround-trip stats: {stats}{prov_note}{_fix_note}\nThe artifact may enter the engine-issued bounded worker feedback loop; release still requires independent whole-volume verification against the exact final artifact SHA.{_comparison_note}{_findings_note}{_direction_comparison_note}'
_GATE_EVENT_LOCK = _threading.Lock()
_GATE_MAILBOX_LOCK = _threading.Lock()
MECHANICAL_FINDINGS_SIDECAR_NAME = _MECHANICAL_FINDINGS_SIDECAR_NAME

def mechanical_findings_for_emit(autoid: str, blocks: object, init_commands: str='') -> list[dict]:
    """本案的前置条件与触发机配对发现（非阻断披露，2026-09-07）。

    判据与说法单源在 ``case_compiler.device_characteristics``；这里只负责取床事实、
    把 emit 手上的 blocks/init 拼成它要的形态，并且**吞掉一切失败**——发现是披露，
    披露算不出来绝不能变成一次拒绝（``compile_emit`` 的返回值只由机械规则决定）。
    """
    if not isinstance(blocks, list) or not blocks:
        return []
    try:
        from cex_core.engine.case_compiler.device_characteristics import mechanical_findings
        from cex_core.engine.ist_core.compile_engine.briefs import _bed_facts
        try:
            bed = _bed_facts()
        except Exception:
            bed = None
        return mechanical_findings({'blocks': blocks, 'init_commands': [line for line in str(init_commands or '').splitlines() if line.strip()]}, bed_facts=bed)
    except Exception:
        logger.warning('交卷机械发现计算失败(autoid=%s)', autoid, exc_info=True)
        return []

def _render_mechanical_findings(findings: list[dict]) -> str:
    """发现 → 附在已受理回执后面的那一段（LLM-facing 英文）。

    **只陈述**：手册原话＋出处＋这一案的结构观察（哪几个块配置了这类对象、哪几个
    观测步从触发机发查询、命令行上写的目标是谁）。**没有祈使句**——引擎不向 LLM
    注入领域命令建议（红线 2；引擎侧一条自毁族的清场建议曾被模型升级成整机清配置、
    跑死两台设备）。读到的人自己判要不要动、动什么。

    **也不点名命令头**（2026-09-07 用户裁决）：发现说的是事实，凭手册原话与出处
    站住；一条被点名的命令头在读到它的模型眼里与建议无异，何况那还是引擎替它挑的
    一条。该配哪条命令由读的人自己去查手册那一节。
    """
    if not findings:
        return ''
    lines = ['', f'mechanical findings: {len(findings)} (disclosure only — this submission is accepted and no rule rejected it):', 'mechanical_findings: ' + json.dumps([{key: value for key, value in item.items() if key != 'quote'} for item in findings], ensure_ascii=False)]
    for item in findings:
        code = str(item.get('code') or '')
        locator = str(item.get('locator') or '')
        quote = ' '.join(str(item.get('text') or item.get('quote') or '').split())
        parts = [f'  - {code}']
        if item.get('host'):
            parts.append(f"host={item['host']}")
        if item.get('target'):
            parts.append(f"target={item['target']}")
        if item.get('paired_hosts') is not None:
            parts.append(f"paired_hosts={list(item.get('paired_hosts') or [])}")
        if item.get('configured_blocks'):
            parts.append(f"configured_blocks={list(item['configured_blocks'])}")
        if item.get('observed_blocks'):
            parts.append(f"observed_blocks={list(item['observed_blocks'])}")
        lines.append(' '.join(parts))
        if quote and locator:
            lines.append(f'    documentation ({locator}): {quote}')
    return '\n'.join(lines)

def _append_gate_event_log(records: list[dict]) -> list[dict]:
    """把各调用点的规则事件写入同一 append-only 流；统计只按 gate 分组。"""
    if not records:
        return []
    try:
        from cex_core.engine.common.runtime_paths import runtime_path
        path = runtime_path('logs', 'gate_events.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        import fcntl
        references = []
        with path.open('ab') as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                for rec in records:
                    raw = (json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
                    offset = os.lseek(fh.fileno(), 0, os.SEEK_END)
                    fh.write(raw)
                    fh.flush()
                    info = os.fstat(fh.fileno())
                    references.append({'offset': offset, 'length': len(raw), 'device': info.st_dev, 'inode': info.st_ino, 'sha256': hashlib.sha256(raw).hexdigest()})
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return references
    except Exception:
        logger.debug('gate_events 记账失败(不改变规则本身裁决)', exc_info=True)
        return []

def _gate_records(autoid: str, items, *, ev: str, stage: str, extra: dict | None=None) -> list[dict]:
    """把 StructuralResult 条目投影为跨 emit/precheck/merge 同形态事实。

    ``extra``（2026-08-31 单调规则反馈批）：规则在拒绝点签发的结构化随账字段，
    逐值与 detail 同一脱敏通道过 ``_redact`` 后原样并入每条记录——键与值都是
    规则判据的机读元数据，不是散文建议。
    """
    import time as _time
    now = _time.time()
    try:
        from cex_core.engine.case_compiler.device_mcp_client import _redact
    except Exception:
        _redact = lambda _text: '[gate detail omitted: redactor unavailable]'

    def _redact_extra(value):
        if isinstance(value, str):
            return _redact(value)
        if isinstance(value, list):
            return [_redact_extra(item) for item in value]
        if isinstance(value, dict):
            return {str(key): _redact_extra(item) for key, item in value.items()}
        return value
    redacted_extra = {str(key): _redact_extra(value) for key, value in (extra or {}).items()}
    records: list[dict] = []
    for index, item in enumerate(items or [], start=1):
        gate = str(getattr(item, 'code', '') or '')
        step_index = getattr(item, 'step_index', -1)
        occurrence_seed = f'{autoid}|{ev}|{stage}|{gate}|{step_index}|{_time.time_ns()}|{index}|{os.getpid()}'
        records.append({'ev': ev, 'aid': str(autoid or '').strip(), 'gate': gate, 'detail' if ev == 'gate_rejected' else 'reason': _redact(str(getattr(item, 'detail', '') or ''))[:400], 'step_index': step_index, 'stage': str(stage or ''), 'ts': now, 'occurrence_id': hashlib.sha256(occurrence_seed.encode('utf-8')).hexdigest(), **redacted_extra})
    return records
_EMIT_ACCOUNTED_STAGES = frozenset({'emit', 'emit_finished_sheet'})

def _write_gate_rejections(autoid: str, violations, *, stage: str='emit', extra: dict | None=None, failure_observations: list[dict] | None=None) -> list[dict]:
    """内部工单(run_facts 结构批,Design 定稿):crash rule 拒绝按 autoid 落中转 mailbox
    (`outputs_root()/<autoid>/gate_rejections.json`,autoid 是本工具唯一可靠拿到的
    键,同 `.grade_credential.json`/`.frozen_override_ack.json` 一个模子)——落的是
    `violation.code`/`.detail`/`.step_index` 原文,供**同案后续轮次的审计**(这份
    mailbox 会被引擎的收账机器转成 gate_rejected 事实,事实本身保留原文可供归因/审计)。

    收账点有两个,各收自己那一段(编译链拆两节点之后,2026-08-08):
    `nodes.emit` 经 `_emit_gate_mailbox_facts` 收 `stage="emit"` 那一批(单案卷面
    的 15 道必崩规则 + 命令存在性规则,都在 `compile_emit` 里响);`nodes.merge` 经
    `_collect_merge_gate_facts` 收合卷阶段那一批。**author 不再收**——`compile_emit`
    已从编写孔白名单摘除,编写孔里根本不会响这些规则。

    **跨案共享的安全边界不在这里、在读侧**(`briefs._run_lessons`):那个函数只取
    `gate_rejected` 事实的 `gate` 码,查 `structural_gate.GATE_LESSON_TEXT`(静态、
    与任何具体 case 数据无关)——不读这份 mailbox/事实里的 `detail`(其中至少两个
    gate——destructive_command/assertion_matches_command_echo——的 detail 会内嵌
    本案的原始命令/回显片段,不适合跨案共享)。落原文 + 读侧收窄,两阶段分工;不在
    写这一步就阉割 detail,因为同案审计仍需要它的完整原文。

    累加式写(读现有、追加、写回)而非覆盖:同一次调用内可能重试多次、撞过不止一类
    gate,一次性覆盖会丢掉更早那次的信号。收账侧读回转事实后逐条 ack 清空这份
    mailbox(`nodes.emit` 尾部的 `_ack_gate_mailbox`,只 ack 真的已经落进
    facts.jsonl 的那些 occurrence——先 unlink 再 append 会在崩溃窗口里永久丢账),
    防止陈旧内容被下一轮误当"这轮新撞的"重新入账。fail-open:落盘失败不阻断 emit
    本体的拒绝返回。

    M3':同一份 mailbox 现有姊妹键 `disabled`(`_write_gate_disabled` 写,fail-open
    自曝,与本函数的 `hits` 键语义不同,见其 docstring)——本函数必须读现有整份 dict、
    只更新自己的 `hits` 键再整份写回,不能拿一个只含 `hits` 的新字面量覆盖整个文件
    (那样同一轮先落的 `disabled` 会被本函数悄悄抹掉,反之亦然;两个键各自独立累加、
    互不清空)。

    ``extra``(2026-08-31 单调规则反馈批):规则在拒绝点签发的结构化随账字段,
    原样并入 `hits` 每条记录(脱敏在 `_gate_records` 里统一过),供下一轮 brief
    的机读指令逐字段转写——不在这条通道里塞散文建议。"""
    safe_extra = {key: value for key, value in (extra or {}).items() if key not in {'failure_evidence', 'failure_evidence_ref'}}
    records = _gate_records(autoid, violations, ev='gate_rejected', stage=stage, extra=safe_extra)
    _session = None
    if stage in _EMIT_ACCOUNTED_STAGES:
        try:
            from cex_core.engine.ist_core.worker_device_context import current_worker_device_session
            _candidate_session = current_worker_device_session()
            if _candidate_session is not None and _candidate_session.autoid and (_candidate_session.autoid == str(autoid or '').strip()):
                _session = _candidate_session
                compile_attempt_id = str(_session.current_compile_attempt_id or '')
                for record in records:
                    record['compile_attempt_id'] = compile_attempt_id
        except Exception:
            logger.debug('worker compile attempt 身份读取失败', exc_info=True)
        captured = _CURRENT_EMIT_GATE_CODES.get()
        if captured is not None:
            captured.extend((str(record.get('gate') or '') for record in records if str(record.get('gate') or '')))
    if stage in _EMIT_ACCOUNTED_STAGES and _session is not None:
        try:
            _session.record_compile_rejection([{'code': getattr(item, 'code', ''), 'detail': getattr(item, 'detail', ''), 'step_index': getattr(item, 'step_index', -1)} for item in violations or []])
        except Exception:
            logger.debug('worker compile no-progress 记账失败', exc_info=True)
    if stage in _EMIT_ACCOUNTED_STAGES:
        from cex_core.engine.ist_core.compile_engine.emit_failure_evidence import bind_observation
        observations = failure_observations if isinstance(failure_observations, list) else []
        for index, record in enumerate(records):
            evidence = bind_observation(record, observations[index] if index < len(observations) else None)
            if evidence is not None:
                record['failure_evidence'] = evidence
    with _GATE_EVENT_LOCK:
        references = _append_gate_event_log(records) or []
    for record, reference in zip(records, references):
        if 'failure_evidence' in record:
            record['failure_evidence_ref'] = reference
    with _GATE_MAILBOX_LOCK:
        try:
            p = _sh.outputs_root() / str(autoid).strip() / 'gate_rejections.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            existing: dict = {}
            if p.is_file():
                try:
                    existing = json.loads(p.read_text(encoding='utf-8'))
                except Exception:
                    existing = {}
            hits = existing.get('hits') or []
            hits.extend(records)
            existing['schema'] = 'ist.compile.gate_mailbox'
            existing['hits'] = hits
            _durable_json_replace(p, existing)
        except Exception:
            logger.debug('gate_rejections 落盘失败(不阻断 emit 拒绝返回)', exc_info=True)
    return records

def _write_gate_disabled(autoid: str, disabled, *, stage: str='emit') -> list[dict]:
    """M3'(INV-11 式③,Design 终裁"诚实化不修对——五重 mixin 白名单对齐留上线后,
    这次只做自曝"):fail-open 自曝落中转 mailbox——同一个文件(`gate_rejections.json`)、
    姊妹键 `disabled`(与 `_write_gate_rejections` 写的 `hits` 键并存,同一个模子:
    `_write_gate_rejections` docstring 已记这份"互不清空"的约定)。

    落的是 `StructuralResult.disabled` 里的条目——这些不是违例(案没有因此被拒),是
    "某条规则这次没能真的检查、只是放行"的自曝信号(当前唯一来源:`_check_dispatch_targets`
    对 APV_0/Seg*_tmp 等白名单未覆盖的 E 的 fail-open 分支)。

    本函数只把信号落进 mailbox,不产 facts.jsonl 事实。引擎侧的收账点是
    `nodes._emit_gate_mailbox_facts`(emit 节点调,merge 另有 `_collect_merge_gate_facts`
    收合卷阶段):它一次读回 `hits` 与 `disabled` 两个键,分别转 `gate_rejected` 与
    `gate_disabled` 事实——后者用 `reason` 字段(不是 `detail`),对齐渲染层"K 健康度"
    行既有的 `gate_disabled` 消费逻辑。**这段接线已经在了**(本 docstring 早期版本记的
    "交由后续批次接线"已过时)。fail-open:落盘失败不阻断 emit 主流程。"""
    records = _gate_records(autoid, disabled, ev='gate_disabled', stage=stage)
    with _GATE_EVENT_LOCK:
        _append_gate_event_log(records)
    with _GATE_MAILBOX_LOCK:
        try:
            p = _sh.outputs_root() / str(autoid).strip() / 'gate_rejections.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            existing: dict = {}
            if p.is_file():
                try:
                    existing = json.loads(p.read_text(encoding='utf-8'))
                except Exception:
                    existing = {}
            items = existing.get('disabled') or []
            items.extend(records)
            existing['schema'] = 'ist.compile.gate_mailbox'
            existing['disabled'] = items
            _durable_json_replace(p, existing)
        except Exception:
            logger.debug('gate_disabled 落盘失败(不阻断 emit 主流程)', exc_info=True)
    return records

def _write_gate_advisories(autoid: str, advisories, *, stage: str='emit') -> list[dict]:
    """advisory（「未据此判定通过或失败」类呈报）落中转 mailbox——姊妹键 ``advisories``。

    2026-09-09 修复轮（呈报零消费者）：StructuralResult.advisories 此前没有
    mailbox/事实通道（line_anchor_window_unverified 等码只在 lint 返回里路过）。
    与 ``disabled`` 键同一模子：互不清空；引擎收账点 ``_emit_gate_mailbox_facts``
    读回转 ``gate_advisory`` 事实，交付报告按规则呈报行渲染。fail-open：落盘
    失败不阻断 emit 主流程。
    """
    records = _gate_records(autoid, advisories, ev='gate_advisory', stage=stage)
    with _GATE_MAILBOX_LOCK:
        try:
            p = _sh.outputs_root() / str(autoid).strip() / 'gate_rejections.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            existing: dict = {}
            if p.is_file():
                try:
                    existing = json.loads(p.read_text(encoding='utf-8'))
                except Exception:
                    existing = {}
            items = existing.get('advisories') or []
            items.extend(records)
            existing['schema'] = 'ist.compile.gate_mailbox'
            existing['advisories'] = items
            _durable_json_replace(p, existing)
        except Exception:
            logger.debug('gate_advisory 落盘失败(不阻断 emit 主流程)', exc_info=True)
    return records

def _gate_mailbox_occurrence_id(autoid: str, *, ev: str, item: dict, index: int) -> str:
    """给升级前无身份的 mailbox 条目派生稳定身份。

    V10 新写点都在拒绝/禁用发生处铸造 ``occurrence_id``；这里只为旧 checkpoint
    恢复提供兼容。索引参与摘要，确保同一旧文件里内容完全相同的两个物理条目仍
    各有身份。两阶段 ack 之前文件顺序不变，因此崩溃重放会得到同一结果。
    """
    existing = str(item.get('occurrence_id') or '').strip()
    if existing:
        return existing
    canonical = {key: value for key, value in item.items() if key != 'occurrence_id'}
    payload = {'schema': 'ist.compile.gate_mailbox.legacy_identity', 'aid': str(autoid or '').strip(), 'ev': ev, 'index': int(index), 'item': canonical}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def _gate_mailbox_records(autoid: str, data: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """读取时补全旧条目身份，但不修改原 mailbox。"""
    hits: list[dict] = []
    disabled: list[dict] = []
    advisories: list[dict] = []
    for index, raw in enumerate(data.get('hits') or [], start=1):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item['occurrence_id'] = _gate_mailbox_occurrence_id(autoid, ev='gate_rejected', item=item, index=index)
        hits.append(item)
    for index, raw in enumerate(data.get('disabled') or [], start=1):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item['occurrence_id'] = _gate_mailbox_occurrence_id(autoid, ev='gate_disabled', item=item, index=index)
        disabled.append(item)
    for index, raw in enumerate(data.get('advisories') or [], start=1):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item['occurrence_id'] = _gate_mailbox_occurrence_id(autoid, ev='gate_advisory', item=item, index=index)
        advisories.append(item)
    return (hits, disabled, advisories)

def _peek_gate_mailbox(autoid: str) -> tuple[list[dict], list[dict], list[dict]]:
    """只读领取候选；事实持久化前绝不删除 receipt。"""
    p = _sh.outputs_root() / str(autoid).strip() / 'gate_rejections.json'
    with _GATE_MAILBOX_LOCK:
        if not p.is_file() or p.is_symlink():
            return ([], [], [])
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('gate mailbox 不可读(autoid=%s)，保留原文件待审计', autoid)
            return ([], [], [])
        if not isinstance(data, dict):
            logger.warning('gate mailbox 根对象无效(autoid=%s)，保留原文件待审计', autoid)
            return ([], [], [])
        return _gate_mailbox_records(autoid, data)

def _ack_gate_mailbox(autoid: str, occurrence_ids) -> int:
    """仅删除已进入 append-only facts 的 occurrence，保留并发新写条目。

    返回实际确认的条目数。先重新读取再按身份删，避免 ``peek`` 与 ``ack`` 之间
    新发生的规则事件被整文件 ``unlink``。重写和删除都同步父目录，崩溃后要么保留
    receipt，要么 facts 已可证明消费完成。
    """
    expected = {str(value or '').strip() for value in occurrence_ids or [] if str(value or '').strip()}
    if not expected:
        return 0
    p = _sh.outputs_root() / str(autoid).strip() / 'gate_rejections.json'
    with _GATE_MAILBOX_LOCK:
        if not p.is_file() or p.is_symlink():
            return 0
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            logger.warning('gate mailbox ack 前不可读(autoid=%s)，保留原文件待审计', autoid)
            return 0
        if not isinstance(data, dict):
            return 0
        hits, disabled, advisories = _gate_mailbox_records(autoid, data)
        kept_hits = [item for item in hits if str(item.get('occurrence_id') or '') not in expected]
        kept_disabled = [item for item in disabled if str(item.get('occurrence_id') or '') not in expected]
        kept_advisories = [item for item in advisories if str(item.get('occurrence_id') or '') not in expected]
        acknowledged = len(hits) + len(disabled) + len(advisories) - len(kept_hits) - len(kept_disabled) - len(kept_advisories)
        if not acknowledged:
            return 0
        if kept_hits or kept_disabled or kept_advisories:
            data['schema'] = 'ist.compile.gate_mailbox'
            data['hits'] = kept_hits
            data['disabled'] = kept_disabled
            data['advisories'] = kept_advisories
            _durable_json_replace(p, data)
            return acknowledged
        try:
            p.unlink()
            dir_fd = os.open(p.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            logger.warning('gate mailbox 已确认但 ack 删除失败(autoid=%s)', autoid, exc_info=True)
            return 0
        return acknowledged

def _drain_gate_mailbox(autoid: str) -> tuple[list[dict], list[dict]]:
    """兼容测试/运维调用的一步领取；生产引擎使用 peek→append→ack。

    facts.jsonl 的引擎节点和工具侧 append-only `gate_events.jsonl` 是两个消费面：
    前者承载批内状态/报告，后者保证手工调用与最后防线同样可度量。本函数不应
    用在引擎节点，因为调用方无法证明清理前事实已经落盘。
    """
    hits, disabled, advisories = _peek_gate_mailbox(autoid)
    _ack_gate_mailbox(autoid, [str(item.get('occurrence_id') or '') for item in hits + disabled + advisories])
    return (hits, disabled, advisories)

def _raw_capabilities_touched(steps: list[dict]) -> list[str]:
    """抽取 raw 通道触碰的 F 能力，并补上 ``F=execute`` 内层的动作能力。"""
    touched = {str(step.get('F') or '') for step in steps if isinstance(step, dict) and step.get('F')}
    from cex_core.engine.case_compiler.apv_lang import execute_action_registry_by_dispatch, execute_dispatcher_for_e, norm_action
    registries = execute_action_registry_by_dispatch()
    for step in steps:
        if not isinstance(step, dict) or str(step.get('F') or '').strip() != 'execute':
            continue
        g = str(step.get('G') or '')
        action = g.rpartition('：')[0] if '：' in g else g
        normalized = norm_action(action)
        dispatcher = execute_dispatcher_for_e(str(step.get('E') or ''))
        if normalized in registries.get(dispatcher, {}):
            touched.add(f'execute:{dispatcher}:{normalized}')
        else:
            touched.add(f'execute:unknown:{normalized}')
    return sorted(touched)
_IR_GAP_LOCK = _threading.Lock()

def _durable_json_replace(path: Path, obj: dict) -> str:
    """原子、可持久化地替换 JSON，并返回最终字节 SHA。

    这里是 raw 逃生阀的凭据路径：仅 ``write_text``/``os.replace`` 不足以签
    durable receipt，因为掉电后目录项仍可能丢失。故数据文件与父目录都 fsync；
    目标/父目录若是符号链接或目标是多硬链接则拒绝，避免凭据被换到案目录外。
    """
    root = _sh.outputs_root()
    try:
        relative = Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError as exc:
        raise OSError('durable JSON sink escaped workspace outputs') from exc
    if len(relative.parts) < 2 or '..' in relative.parts:
        raise OSError('durable JSON sink has an invalid output-relative path')
    payload = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
    from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow
    digest = atomic_write_bytes_nofollow(path, payload, error_type=OSError, invalid_message='durable JSON sink has an invalid path', unavailable_message='durable JSON sink transaction failed', create_parents=True, mode=384)
    return digest

def _probe_ir_gap_sink(scope_name: str) -> dict:
    """实写、回读、清理一次 ir_gap sink，供 prep 签发健康事实。"""
    try:
        safe_scope = _safe_output_component(scope_name, field='out_name')
        probe_id = hashlib.sha256(os.urandom(32) + str(time.time_ns()).encode('ascii')).hexdigest()
        path = _sh.outputs_root() / safe_scope / f'.ir_gap_probe.{probe_id}.json'
        payload = {'schema': 'ist.compile.ir_gap_sink_probe', 'probe_id': probe_id}
        digest = _durable_json_replace(path, payload)
        loaded = json.loads(path.read_text(encoding='utf-8'))
        if loaded != payload:
            raise OSError('ir_gap sink probe payload mismatch')
        path.unlink()
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return {'status': 'healthy', 'schema': 'ist.compile.ir_gap_sink_health', 'probe_id': probe_id, 'receipt_sha256': digest}
    except Exception as exc:
        logger.warning('ir_gap sink 健康探针失败', exc_info=True)
        return {'status': 'unhealthy', 'schema': 'ist.compile.ir_gap_sink_health', 'error': type(exc).__name__}

def _write_ir_gap_touch(autoid: str, capabilities_touched: list[str], expressible: bool | None, out_of_atlas: list[str] | None=None, reason: str='') -> dict:
    """v10 §5.3 逃生阀记账(M2 批1,与 `_write_gate_rejections` 同一模子的独立 mailbox
    `ir_gap.json`,不复用 `gate_rejections.json`——语义不同:这不是规则拒绝/自曝,是
    "本案走了 raw steps 通道且声明了 blocks 表达缺口"这件事实。入口已 fail-closed
    拒绝空理由；本函数只接受并原样落入结构化 mailbox。

    调用时机:`compile_emit` 的 `blocks` 参数为空、raw 载荷已成功解析成非空步骤
    数组之后，且早于 frozen/结构/provenance/成品 lint 等后续规则——记的是
    “这案这次已选择 raw 逃生阀”这个事实，所以即使后续被规则拒绝也不得消失。
    无法解析或空载荷属于传输/语法失败，尚未形成可审计的步骤能力集合，不铸
    `ir_gap`；raw 无理由则在更早入口 fail-closed。mailbox 累加式写允许同轮重试。

    `capabilities_touched` 抽取口径(§0.1 机械可判,详见 `main.case_compiler.ir_coverage`
    docstring):**去重后的全部 F 列字面值**，另把 ``F=execute`` 的精确动作名加入
    (动作本身也是 atlas 能力，不能只记外层 execute)。普通 F 不做大小写归一
    (F 值本身大小写敏感，归一会把真实方法与不存在的拼写错误合并)；不排除
    found/not_found/abs_found 等已覆盖能力。

    `expressible`(批2③三态,内部评审日期（已脱敏） 团队裁,取代 Theory 内部评审日期（已脱敏） 的二态修正):
    调用方须先用 `ir_coverage.all_capability_names()` 把 `capabilities_touched`
    过滤到"在 atlas 范围内"的子集——子集非空时,里面只要有一个经
    `classify_capability` 判为非 "covered"(如 "todo"),本案整体记 False;全部
    "covered" 才记 True。**子集为空**(纯 cli 卷,touched 全是 cmd_config/execute
    等不在 atlas 范围内的通道名,一个真正的 atlas 能力都没碰到)时记 **None**——
    "无从判断",不是 True 也不是 False。**cmd_config/cmds_config/字面 dist/member
    这类不在 atlas 范围内的通道名,不参与这个计算**(旧版曾把它们也塞进来算,靠
    `classify_capability` 当时"未知即 covered"的错误兜底才没有让 expressible 恒为
    False——这个巧合掩盖了真正的 bug,已改正,不能再依赖它)。**本函数原样传递
    调用方算好的三态值,不做 `bool()` 强制转换**(那会把 None 悄悄压成 False,
    重新引入"零证据当成有证据的反例"这同一类假阳性/假阴性问题,只是换了个
    出现的位置)。

    `out_of_atlas`(第三桶):`capabilities_touched` 里不在 atlas 范围内的那部分,
    **留痕不静默丢弃**(M1 unclassified 同款纪律)。I5(权威链批)修订:旧注写
    "不参与 expressible 计算"——<case> 实证那正是自相矛盾账的来源(缺口能力
    不投票,剩下的全 covered ⇒ `expressible:true ∧ out_of_atlas 非空`)。现语义:
    out_of_atlas 非空 ⇒ 调用方置 expressible=False(缺口即不可表达的原因),
    本函数仍只原样传递。"""
    try:
        import time as _t5
        p = _sh.outputs_root() / str(autoid).strip() / 'ir_gap.json'
        occurrence_id = hashlib.sha256(os.urandom(32) + str(_t5.time_ns()).encode('ascii') + str(autoid).encode('utf-8')).hexdigest()
        with _IR_GAP_LOCK:
            existing: dict = {}
            if p.is_file():
                existing = json.loads(p.read_text(encoding='utf-8'))
                if not isinstance(existing, dict):
                    raise OSError('ir_gap mailbox is not a JSON object')
            touches = existing.get('touches') or []
            if not isinstance(touches, list):
                raise OSError('ir_gap mailbox touches is not a list')
            touches.append({'occurrence_id': occurrence_id, 'capabilities_touched': sorted(set(capabilities_touched)), 'expressible': expressible, 'out_of_atlas': sorted(set(out_of_atlas or [])), 'reason': str(reason or '').strip(), 'ts': _t5.time()})
            existing['schema'] = 'ist.compile.ir_gap_mailbox'
            existing['touches'] = touches
            digest = _durable_json_replace(p, existing)
            verified = json.loads(p.read_text(encoding='utf-8'))
            if not any((isinstance(item, dict) and item.get('occurrence_id') == occurrence_id for item in verified.get('touches') or [])):
                raise OSError('ir_gap receipt is absent after read-back')
        return {'status': 'durable', 'schema': 'ist.compile.ir_gap_receipt', 'occurrence_id': occurrence_id, 'mailbox_sha256': digest, 'touch_count': len(touches)}
    except Exception as exc:
        logger.warning('ir_gap 落盘失败，调用方必须拒绝 raw emit', exc_info=True)
        return {'status': 'failed', 'schema': 'ist.compile.ir_gap_receipt', 'error': type(exc).__name__}

def _write_frozen_override_ack(autoid: str, reason: str, xlsx_path) -> None:
    """内部工单(Design 定稿:sidecar 落 override 声明,不走 provenance IR——那是断言
    来源链、塞一条跟断言无关的"这次换法声明"进去语义不对,也牵连改 IR schema)。

    收紧①(Theory 内部工单 复核改,原注释"钥匙不给被管方/LLM 手写伪造不了"说过头
    ——改诚实边界):这不是 `THEORY_k_state_machine.md §5.5.6` 那类"规则凭证独立
    于被检查方"的抗伪凭证——ack 落在 outputs/<autoid>/,worker fork 的
    fs_write 常驻基础工具组(tool_gating 不门控)、写沙箱又放行
    workspace/outputs/,被管方够得着这条路径、能直接手写伪造一份 mtime 对得上
    的 ack,不满足其精确判据("规则不能读被检查方在凭证信号之前能自达写入的
    账")——这里没有独立于被管方的凭证信号。它实际防的是**意外**(LLM 没
    意识到已冻结、盲目同法重编),工具在正常路径顺手落的这条记录挡住这类
    无心之失;蓄意伪造挡不住,但后果有限——伪造只能混过这一条规则,案子仍要
    按同法重新上机,大概率同签名再 fail(冻结判定本身不受 ack 真伪影响,见
    收紧②),不产生假 PASS,只白烧一轮设备验证——真正的抗伪来自设备 oracle
    兜底,不是这份 ack。真要做成 §5.5.6 那类抗伪凭证,需把落点挪到被管方
    不可写的路径(如 runtime/,同 verified_runs.jsonl 套路)——当前威胁模型
    只到"意外"、oracle 已兜底"蓄意",挪路径过度,不做。

    收紧②(facts 权威不动摇):这份 ack **只承载"声明过+绑定哪份卷面"**,
    不承载"冻没冻"——那个判断永远是 merge 规则(precheck_merge_case)现查
    `F.frozen`(facts 派生),就算有人把这份 ack 文件复制/伪造到别的 aid 目录,
    顶多让"是否声明过 override"这件事被误判,冻结判定本身仍然是账本说了算,
    不会被绕过。

    xlsx_mtime 绑定当次 emit **实际产出**的 case.xlsx(调用时机在 emit_xlsx()
    成功之后,不是频率更早的冻结规则检查点那会儿——那时新卷面还没写出来,mtime
    无从谈起)——merge 规则核对时若卷面已被重编(新 mtime),旧 ack 天然不匹配、
    不会被当成"这份新卷面也声明过换法"误用(同 .grade_credential.json 的既有
    mtime 绑定套路,不是新发明)。fail-open:ack 落盘失败不阻断 emit 本体(它只是
    merge 规则的辅助证据,不是 emit 通过与否的判据)。"""
    try:
        from cex_core.engine.ist_core.tools.device.verifiability_tool import _write_json_atomic
        import time as _t2
        ack_path = _sh.outputs_root() / str(autoid).strip() / '.frozen_override_ack.json'
        _write_json_atomic(ack_path, {'reason': (reason or '').strip()[:200], 'ts': _t2.time(), 'xlsx_mtime': xlsx_path.stat().st_mtime})
    except Exception:
        logger.debug('frozen override ack 落盘失败(不阻断 emit)', exc_info=True)
MERGE_LEDGER_PENDING_REASONS: tuple[str, ...] = ('存在未裁或裁决身份不匹配的盘上冲突，拒绝合并', '未决冲突台账不可读，拒绝合并', '裁决台账不可读，拒绝合并', '批级来源冲突裁决要求停止编写或放弃整批，不得合并', '用户裁决为停止编写或放弃本次生成，不得合并')
MERGE_XML_ABSENCE_REASON = '设备 XML 命令树未收录用例命令，设备不支持这个功能'

def merge_reason_is_ledger_pending(reason: str | None) -> bool:
    """merge 预检不就绪原因是否属「台账未裁/身份不匹配/不可读/裁决停批」类(单源判别)。

    引擎 merge 循环据此把该类案从「踢出打回重编」改道「搁置等裁决/退役」——
    不落 emit_invalid(不触发 fold 打回)、不动盘上卷面与凭证。前缀匹配是因为
    「未决冲突台账不可读」带异常类型后缀。
    """
    text = str(reason or '')
    return any((text.startswith(token) for token in MERGE_LEDGER_PENDING_REASONS))

def merge_reason_is_xml_absence(reason: str | None) -> bool:
    """merge 预检不就绪原因是否是「命令树未收录」机械终态(单源判别)。

    引擎 merge 循环据此把该案从「踢出打回重编」改道「与 emit 同源补铸
    xml_absence_terminal 终态」——不落 emit_invalid、不动盘上卷面与凭证。
    """
    return str(reason or '').startswith(MERGE_XML_ABSENCE_REASON)

def merge_case_producer_rules(autoid: str, steps: object, *, init: str='', title: str='', reachability_scope: object=None, expected_save_variant: str='', recorded_author_values: Sequence[str] | None=None, recorded_author_ip_literals: Sequence[str] | None=None):
    """合卷逐案「产者可修」规则全集:通过返回 ``(CaseIR, "")``,否则 ``(None, 拒绝原文)``。

    单一源:`compile_emit_merged` 的逐案装配循环与引擎侧 `precheck_merge_case` 调**同一个**
    函数。引擎先逐案跑一遍,不过的案按既有 `emit_invalid` 通道踢出本卷、其余照合;工具本体
    照旧对整卷全拒(手动编排的最后防线)。两处各写一套就会出现「引擎说这卷能合、工具说不能」
    的对不上账——那正是 2026-09-04 <batch> 的形态:一案的规则拒绝把 21 个已编写案的整卷
    一起带走,收口再把它们全标成兜底桶。

    卷级检查(共存互斥、排序、哨兵、文件级前置)不在本函数内——那些按定义就不是单案可判的。
    拒绝原文不带 ``cases[i]`` 前缀,由调用方按各自呈报口径拼。
    """
    from cex_core.engine.case_compiler.distribution_assertion import expand_distribution_steps
    from cex_core.engine.case_compiler.membership_assertion import expand_membership_steps
    if not isinstance(steps, list) or not steps:
        return (None, f'(autoid={autoid}) steps must be a non-empty list')
    steps = [s for s in steps if not (isinstance(s, dict) and str(s.get('E', '')).strip() in ('APV_0', 'test_env') and (not str(s.get('G') or '').strip()))]
    if not steps:
        return (None, f'(autoid={autoid}) steps became empty after dropping empty command steps')
    steps, _dist_plan, _dist_err = expand_distribution_steps(steps)
    if _dist_err:
        return (None, f'(autoid={autoid}) distribution-interval assertion declaration is invalid: {_dist_err}')
    steps, _member_err = expand_membership_steps(steps)
    if _member_err:
        return (None, f'(autoid={autoid}) hit-membership assertion declaration is invalid: {_member_err}')
    case_init = str(init or '').strip()
    gate = _gate_unreachable_ips(autoid, steps, init=case_init, recorded_author_values=recorded_author_values)
    if gate:
        return (None, gate)
    gate = _gate_unreachable_listener(autoid, steps, init=case_init, reachability_scope=reachability_scope, author_ip_literals=recorded_author_ip_literals)
    if gate:
        return (None, gate)
    gate = _gate_driver_reachability(autoid, steps, author_ip_literals=recorded_author_ip_literals)
    if gate:
        return (None, gate)
    gate = _gate_destructive_commands(autoid, steps, init=case_init, stage='merge_precheck')
    if gate:
        return (None, gate)
    gate = _gate_save_restore_pairing(autoid, steps, init=case_init, expected_save_variant=_intent_save_variant(autoid) or str(expected_save_variant or ''))
    if gate:
        return (None, gate)
    full_steps = list(steps)
    if case_init:
        full_steps = [{'E': 'APV_0', 'F': 'cmds_config', 'G': case_init, 'desc': 'case 自包含前置配置'}] + full_steps
    case, info = _steps_to_caseir(autoid, full_steps, title=str(title or ''))
    if case is None:
        return (None, f'(autoid={autoid}): {info}')
    return (case, '')

def precheck_merge_case(aid: str, out_name: str='') -> str | None:
    """单案合并就绪预检(编译引擎 merge 节点消费;内部工单-② run13 二次实证驱动)。

    与 compile_emit_merged 的 autoids 规则同构三查:xlsx 在盘/lint 凭证新鲜/成品卷
    lint 干净。返回 None=就绪;str=不就绪原因(进 emit_invalid 事实与用户面叙述)。
    引擎在合并前逐案预检,把不就绪案踢出本卷——单案违例不再拖死全批
    (run13 实证:一案凭证过期曾致 merge error→closing,26 案零上机收口)。
    踢出后的去向由引擎按原因分流(2026-08-15):卷面类(凭证/lint/冻结)打回重编;
    台账类(`merge_reason_is_ledger_pending`)搁置等裁决/退役,不打回、不动卷面。
    工具本体的全拒行为不变(手动编排的最后防线)。

    内部工单(Design 定稿,第④查——回退 enforcement 挪到引擎侧,不靠 worker 传
    out_name):`F.frozen(fs, aid)`(引擎侧现查,不传 current_artifact,同 内部工单
    回退口径——回退存在的意义是复现 .frozen.json 本该给出的判定,那份文件由
    写侧纯签名比对逻辑写出、不看卷面身份)为真、且找不到针对**当前**卷面的有效
    override ack → 判定"未确认冻结换法",踢出重编(同前三查的既有踢出机制)。
    out_name 由 `merge()` 传入(引擎自己的 state 值,不依赖 worker——这正是
    内部工单/内部工单 要解决的"enforcement 不能靠被管方传数据"这条原则的落地:emit 规则
    (worker 路径)的回退在 worker 恒不传 out_name 的现实下结构性够不着账本,
    merge 规则(引擎路径)不这样,out_name 恒有)。
    """
    try:
        aid, xp = _safe_case_path(aid, field='autoid')
        if (out_name or '').strip():
            _safe_output_component(out_name, field='out_name')
    except ValueError as exc:
        return f'unsafe output identity: {exc}'
    if not xp.is_file():
        return 'case.xlsx 不在盘(编写未产出或已被挪走)'
    nd_path = xp.parent / 'needs_decision.json'
    ud_path = xp.parent / 'user_decision.json'
    if nd_path.is_file():
        try:
            nd = json.loads(nd_path.read_text(encoding='utf-8'))
            claims = [c for c in nd.get('claims') or [] if isinstance(c, dict)]
        except Exception as exc:
            return f'未决冲突台账不可读，拒绝合并:{type(exc).__name__}'
        if claims:
            from cex_core.engine.ist_core.compile_engine.terminal_credentials import xml_absence_veto_claims
            if xml_absence_veto_claims(claims):
                return MERGE_XML_ABSENCE_REASON
            from cex_core.engine.ist_core.tools.device.verifiability_tool import decision_covers_claims
            if not (ud_path.is_file() and decision_covers_claims(ud_path, nd_path)):
                return '存在未裁或裁决身份不匹配的盘上冲突，拒绝合并'
            try:
                ud = json.loads(ud_path.read_text(encoding='utf-8'))
            except Exception:
                return '裁决台账不可读，拒绝合并'
            decision = str(ud.get('decision') or '')
            action = str(ud.get('action') or '')
            if accepts_schema(ud.get('schema'), 'ist.delta.batch-conflict-decision'):
                from cex_core.engine.ist_core.compile_engine.conflict_chain import BATCH_USE_XML
                if decision != BATCH_USE_XML:
                    return '批级来源冲突裁决要求停止编写或放弃整批，不得合并'
                if xp.stat().st_mtime_ns <= ud_path.stat().st_mtime_ns:
                    return '批级裁决要求按 XML 重编，当前卷早于裁决'
            elif action in {'keep_case_and_block', 'abandon_generation'} or decision in {'xml_keep_case_blocked', 'abandon_generation'}:
                return '用户裁决为停止编写或放弃本次生成，不得合并'
            elif action.startswith('recompile_with_') and xp.stat().st_mtime_ns <= ud_path.stat().st_mtime_ns:
                return '用户裁决要求重编，当前卷早于裁决'
    _case_payload, _credential_sha256, _credential_status = _sh.lint_credential_snapshot(aid)
    if _credential_status == 'credential_missing':
        return '缺 lint 凭证(未经 compile_emit 通过规则产出)'
    if _credential_status in {'credential_unreadable', 'credential_contract_invalid'}:
        return 'lint 凭证不可读或身份契约不匹配'
    if _credential_status != 'ok':
        return 'lint 凭证过期或卷面身份不可安全核验(当前 case.xlsx 字节 SHA 与 emit 凭证不一致——须重新 compile_emit 通过规则)'
    _scope, _scope_error = _reachability_scope_from_credential(aid, xlsx_sha256=_credential_sha256)
    if _scope is None:
        return 'lint 凭证的 blocks.kind/一致性绑定无效，须从密封机械用例重新 emit: ' + _scope_error
    from cex_core.engine.ist_core.tools.device.structural_gate import lint_xlsx_case
    lr = lint_xlsx_case(BytesIO(_case_payload))
    if lr.disabled:
        _write_gate_disabled(aid, lr.disabled, stage='merge_precheck')
    if lr.advisories:
        _write_gate_advisories(aid, lr.advisories, stage='merge_precheck')
    if not lr.ok:
        _write_gate_rejections(aid, lr.violations, stage='merge_precheck')
        return '成品卷 lint 违例:' + '; '.join((f'[{it.code}]' for it in lr.violations))[:200]
    try:
        from cex_core.engine.ist_core.tools.device.package_registry_tool import _load_case_rows as _load_rows_for_rules
        _rows = _load_rows_for_rules(BytesIO(_case_payload))
    except Exception as exc:
        raise RuntimeError(f'merged rule readback failed: {exc}') from exc
    _case_ir, _rule_reason = merge_case_producer_rules(aid, _rows, init='', reachability_scope=_scope, recorded_author_values=_recorded_author_unreachable_values(aid, xlsx_sha256=_credential_sha256), recorded_author_ip_literals=_recorded_author_ip_literals(aid, xlsx_sha256=_credential_sha256))
    if _case_ir is None:
        return f'合卷卷面规则未通过:{_rule_reason}'
    _provenance_path = xp.parent / 'case.provenance.json'
    try:
        _typed_provenance = json.loads(_provenance_path.read_text(encoding='utf-8'))
    except Exception:
        _typed_provenance = {}
    if accepts_schema(_typed_provenance.get('assertion_schema'), 'ist.ide.assertion'):
        from cex_core.engine.case_compiler.mutation_testing import load_mutation_credential, mutation_receipt_ready
        _mutation = load_mutation_credential(aid, _sh.project_root() / 'runtime' / 'mutation_credentials')
        from cex_core.engine.case_compiler.mutation_testing import mutation_receipt_run_ready
        if not mutation_receipt_run_ready(_mutation, hashlib.sha256(_case_payload).hexdigest()):
            from cex_core.engine.case_compiler.mutation_testing import exempt_governance_failure_message
            _receipt_for_diag: dict = {}
            if isinstance(_mutation, dict) and _mutation.get('exempt_governance'):
                _receipt_for_diag = _mutation
            else:
                try:
                    _loaded = json.loads((xp.parent / 'case.mutation.json').read_text(encoding='utf-8'))
                    _receipt_for_diag = _loaded if isinstance(_loaded, dict) else {}
                except Exception:
                    _receipt_for_diag = {}
            _governance_reason = exempt_governance_failure_message(_receipt_for_diag)
            if _governance_reason:
                from cex_core.engine.case_compiler.mutation_testing import EXEMPT_MAX_RATIO, _exempt_governance_check, _governance_counts, _is_compiler_issued_exempt
                _gov_items = [item for item in _receipt_for_diag.get('requirements') or [] if isinstance(item, dict)]
                _gov_total, _gov_exempt, _gov_structural, _gov_compiler_issued, _gov_discretionary, _gov_ratio = _governance_counts(_gov_items)
                _signal_merge_precheck_refusal(aid, MERGE_PRECHECK_REFUSAL_GATE_EXEMPT_GOVERNANCE, _exempt_governance_check(_receipt_for_diag, allow_compiler_issued_full_exempt=True), detail={'total_assertions': _gov_total, 'exempt_assertions': _gov_exempt, 'discretionary_exempt_assertions': _gov_discretionary, 'author_declared_exempt_assertions': sum((item.get('status') == 'exempt' and (not _is_compiler_issued_exempt(item)) for item in _gov_items)), 'exempt_ratio': round(_gov_ratio, 6), 'max_exempt_ratio': EXEMPT_MAX_RATIO})
                return _governance_reason
            return 'IDE 类型案缺少引擎侧变异凭据，或凭据未翻转/未绑定当前 case.xlsx'
    from cex_core.engine.ist_core.compile_engine import facts as _F
    _fs = _sh.load_facts({'out_name': out_name})
    if _F.frozen(_fs, str(aid).strip()):
        ack_path = xp.parent / '.frozen_override_ack.json'
        _ack_ok = False
        if ack_path.is_file():
            try:
                _ack = json.loads(ack_path.read_text(encoding='utf-8'))
                _ack_ok = abs(float(_ack.get('xlsx_mtime', -1)) - xp.stat().st_mtime) < 1e-06
            except Exception:
                _ack_ok = False
        if not _ack_ok:
            return '同签名连续两轮 fail(引擎账本判定已冻结)但未见针对本次卷面的换法声明(override_frozen_reason)——须经 compile_emit 显式声明后重编'
    return None

def _replay_runtime_fills_before_emit(case_irs: list, sidecar: Path) -> tuple[str, dict[str, list[tuple[str, str, str]]]]:
    """拒绝把旧 ``runtime_fills.json`` 的设备 actual 重放成新卷 expected。

    参数 ``case_irs`` 只保留原内部调用形状；函数绝不修改它。空 sidecar 可忽略，
    非空记录一律要求回到 Author/Spec/DefectSpec/Manual/ConfigBinding/CapabilityXml
    重新出新期望。
    """
    del case_irs
    from cex_core.engine.case_compiler.runtime_fill import _json_list
    records = _json_list(sidecar, label='legacy runtime_fills sidecar')
    if records:
        raise ValueError('observe_then_assert_forbidden: legacy runtime_fills actuals cannot be replayed into expected; resolve via Author|Spec|DefectSpec|Manual|ConfigBinding|CapabilityXml')
    return ('', {})

@tool(parse_docstring=True)
def compile_emit_merged(cases_json: str='', shared_init: str='', out_name: str='', autoids: str | list[str]='') -> str:
    """Merge **multiple cases into one xlsx** (the packaging tool for one excel per mindmap).

    **Preferred usage (main-orchestrated): pass only ``autoids``.** Each worker has already
    landed its case at workspace/outputs/<autoid>/case.xlsx via compile_emit; this tool
    reads the steps back from those finished xlsx files itself and merges them, so the
    autoid list is the whole input: steps and init already live in each case.xlsx.
    ``cases_json`` is the engine closing node's archive channel (it bypasses the lint
    credential rule below) and is ignored whenever ``autoids`` is given.

    For batch-compile wrap-up: merges the N cases already generated one by one from the same
    mindmap into a single case.xlsx, automatically padding a sentinel case at the end
    (framework deferred-execution contract) — so the first N real cases all execute normally.
    Merging is not simple concatenation: it guarantees case order, column alignment, and the
    sentinel at the bottom; the structure is 100% legal.

    **Each case carries its own preconfig** (``init``): the framework clears device config
    before running every case, so each case must be self-contained. Put this case's full
    baseline config into its own ``init`` (emitted as the case's first APV_0 config step), and
    the test actions + assertions into ``steps``. When cases have different baselines (e.g.
    each with its own pool/algorithm), each writes its own init — never share one.

    ``shared_init`` is only for file-level preconfig (C=1) that **all cases truly share and
    that must rerun before every case**. Usually leave it empty; baselines go into each case's
    own ``init``.

    Zero hardcoding: this tool produces no commands; init/steps all come from you (the
    sub-agent that has consulted manuals/precedents).

    Args:
        autoids: **Pass this first.** autoid list (JSON array string like ["203...","203..."],
            or comma separated). For each autoid the tool reads
            workspace/outputs/<autoid>/case.xlsx and merges the steps read back via
            _load_case_rows (init is already included as the first APV_0 step). When autoids
            is given, cases_json is ignored.
        cases_json: (engine closing node only) JSON array string, each item a case dict
            with keys autoid, steps (each step {E,F,G,H?,I?,desc?}, at least one check_point),
            init (may be empty), title (optional).
        shared_init: file-level preconfig (C=1) shared by all cases, newline separated; usually empty.
        out_name: output subdir name (workspace/outputs/<out_name>/case.xlsx); e.g. the mindmap's file name.

    Returns:
        Output path + round-trip reconciliation (case count should = input count + 1 sentinel).
        This merge does not issue a release credential. Independent whole-volume verification
        must test this exact artifact SHA before delivery.

    Note:
        The autoids path carries the lint-credential mechanical rules: each autoid must have
        passed all of compile_emit's mechanical rules on the current case.xlsx (passing the
        gates auto-lands .grade_credential.json with the exact xlsx_sha256 signature). Missing
        or stale credential → the merge is refused with the case list. The cases_json path
        (engine closing archive) does not go through this rule.
    """
    try:
        if (out_name or '').strip():
            _safe_output_component(out_name, field='out_name')
    except ValueError as exc:
        return f'error: unsafe output identity: {exc}'
    aid_list, autoids_err = _parse_autoids_arg(autoids)
    if autoids_err:
        return autoids_err
    case_credential_sha256: dict[str, str] = {}
    if aid_list is not None:
        from cex_core.engine.ist_core.tools.device.package_registry_tool import _load_case_rows
        cases = []
        case_snapshots: dict[str, bytes] = {}
        case_reachability_scopes: dict[str, ReachabilityScope] = {}
        no_grade: list[str] = []
        stale_grade: list[str] = []
        scope_bad: list[str] = []
        for aid in aid_list:
            try:
                aid, xp = _safe_case_path(str(aid), field='autoid')
            except ValueError as exc:
                return f'error: unsafe output identity: {exc}'
            if not xp.is_file():
                return f'error: case.xlsx for autoid {aid} does not exist ({xp}); the case may not have compiled successfully — compile it first / re-dispatch the worker'
            _case_payload, _credential_sha256, _credential_status = _sh.lint_credential_snapshot(aid)
            if _credential_status == 'credential_missing':
                no_grade.append(aid)
                continue
            if _credential_status != 'ok':
                stale_grade.append(aid)
                continue
            _scope, _scope_error = _reachability_scope_from_credential(aid, xlsx_sha256=_credential_sha256)
            if _scope is None:
                scope_bad.append(f'{aid}: {_scope_error}')
                continue
            case_snapshots[aid] = _case_payload
            case_reachability_scopes[aid] = _scope
            case_credential_sha256[aid] = _credential_sha256
        if no_grade or stale_grade or scope_bad:
            parts = []
            if no_grade:
                parts.append(f"missing lint credential (did not go through gated compile_emit): {', '.join(no_grade)}")
            if stale_grade:
                parts.append(f"re-compiled but not re-emitted (the credential does not match the current case.xlsx): {', '.join(stale_grade)}")
            if scope_bad:
                parts.append('missing/stale blocks.kind reachability scope (re-emit from the sealed mechanical case; merge will not guess kind from xlsx text): ' + '; '.join(scope_bad))
            return "error: merge rejected by the lint-credential rule — the following cases have not passed all of emit's mechanical rules on their current case.xlsx:\n" + '\n'.join(parts) + '\nRun compile_emit again for each listed case (passing all mechanical rules auto-lands the lint credential), then merge.'
        from cex_core.engine.ist_core.tools.device.structural_gate import lint_xlsx_case
        lint_bad: list[str] = []
        for aid, snapshot_payload in case_snapshots.items():
            try:
                rows = _load_case_rows(BytesIO(snapshot_payload))
            except Exception as e:
                return f'error: failed to read back case.xlsx for {aid}: {e}'
            lr = lint_xlsx_case(BytesIO(snapshot_payload))
            if not rows:
                return f'error: {aid} read back empty steps (case.xlsx data area empty?)'
            cases.append({'autoid': aid, 'steps': rows, '_reachability_scope': case_reachability_scopes[aid]})
            if lr.disabled:
                _write_gate_disabled(aid, lr.disabled, stage='merge_final')
            if not lr.ok:
                _write_gate_rejections(aid, lr.violations, stage='merge_final')
                lint_bad.append(f'{aid}: ' + '; '.join((f'[{it.code}]' for it in lr.violations)))
        if lint_bad:
            return 'error: merge rejected by finished-sheet lint — the following cases carry mechanically decidable must-crash/always-fail shapes (one must-crash case crashes the whole pytest file and none of the rest run):\n  ' + '\n  '.join(lint_bad) + '\nFix them, run compile_emit again, then merge (violation details are in the corresponding emit returns).'
    else:
        try:
            cases = json.loads(cases_json)
            if not isinstance(cases, list) or not cases:
                return 'error: pass autoids (preferred; the tool reads the sheets back itself) or a non-empty cases_json'
        except Exception as e:
            return f'error: cases_json parse failed: {e}'
    try:
        from cex_core.engine.case_compiler.case_ir import FileIR, Row
        from cex_core.engine.case_compiler.xlsx_emit import emit_xlsx
        from cex_core.engine.case_compiler.config import get_config
        from cex_core.engine.case_compiler.distribution_assertion import expand_distribution_steps
        from cex_core.engine.case_compiler.membership_assertion import expand_membership_steps
    except Exception as e:
        return f'error: failed to load compiler modules: {e}'
    case_irs = []
    seen_autoids = set()
    for idx, c in enumerate(cases):
        if not isinstance(c, dict):
            return f'error: cases[{idx}] is not a dict'
        try:
            autoid = _safe_output_component(str(c.get('autoid', '')), field=f'cases[{idx}].autoid')
        except ValueError as exc:
            return f'error: unsafe output identity: {exc}'
        if autoid in seen_autoids:
            return f'error: autoid {autoid} is duplicated (autoid is the primary key and must be unique; titles may repeat)'
        seen_autoids.add(autoid)
        case, reason = merge_case_producer_rules(autoid, c.get('steps'), init=str(c.get('init', '') or '').strip(), title=str(c.get('title', '') or ''), reachability_scope=c.get('_reachability_scope'), expected_save_variant=str(c.get('expected_save_variant', '') or ''), recorded_author_values=_recorded_author_unreachable_values(autoid, xlsx_sha256=case_credential_sha256.get(autoid, '')), recorded_author_ip_literals=_recorded_author_ip_literals(autoid, xlsx_sha256=case_credential_sha256.get(autoid, '')))
        if case is None:
            return f'error: cases[{idx}] {reason}'
        case_irs.append(case)
    shared = shared_init.strip()
    init_rows = [Row(test_object='APV_0', method='cmds_config', data=shared)] if shared else []
    try:
        sub, out = _safe_case_path(out_name or case_irs[0].autoid, field='out_name')
    except ValueError as exc:
        return f'error: unsafe output identity: {exc}'
    replay_note = ''
    try:
        replay_note, _ = _replay_runtime_fills_before_emit(case_irs, out.parent / 'runtime_fills.json')
    except Exception as exc:
        return f'error: runtime_fills replay failed: {exc}'
    fir = FileIR(feature=sub, author='IST-Core-agent', init_rows=init_rows, cases=[*case_irs, _build_sentinel()], module='ist_smoke')
    try:
        stats = emit_xlsx(fir, out, trusted_outputs_root=_sh.outputs_root())
    except Exception as e:
        return f'error: emit failed: {e}'
    autoids = [c.autoid for c in case_irs]
    return f'=== compile_emit_merged ===\n已合并 {len(case_irs)} 个真 case + 1 哨兵 → {out}\nautoids: {autoids}\nround-trip stats: {stats}{replay_note}\n(case_count expected={len(case_irs)}+1 sentinel={len(case_irs) + 1})\nIndependent whole-volume verification must test this exact artifact SHA before delivery.'
