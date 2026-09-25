# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/xml_conflict_core.py（sha256 94399e26f0b99e46）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import re
from typing import Any, Callable, Iterable
CONFLICT_CLAIM_SCHEMA = 'ist.delta.conflict-claim'
S3_CLAIM_KIND = 'xml_command_shape_conflict'
S3_REASON_CODE = 'parameter_contract_violation'
S3_DELTA_SCHEMA = 'ist.delta.xml-command-shape-delta'
S3_OPTIONS = ['xml_replace_command', 'xml_keep_case_blocked', 'abandon_generation']
S3_NEAR_HEAD_REASON_CODE = 'command_head_near_miss'
S3_NEAR_HEAD_DELTA_SCHEMA = 'ist.delta.xml-command-near-head-delta'
S4_CLAIM_KIND = 'xml_expectation_conflict'
S4_REASON_CODE = 'capability_xml_expectation_mismatch'
S4_DELTA_SCHEMA = 'ist.delta.xml-expectation-delta'
S4_OPTIONS = ['use_xml_expectation', 'use_case_expectation', 'abandon_generation']
Verdict = dict
Resolve = Callable[[str], Verdict]

def _canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def is_scenario3_violation(verdict: Verdict) -> bool:
    return bool(verdict.get('kind') == 'hit' and (not verdict.get('parameters_valid')) and (verdict.get('reason_code') == S3_REASON_CODE) and (verdict.get('origin') == 'vendor_xml'))
_LOCATOR_TOKEN = re.compile('^\\[[^\\]]*\\]$')

def is_command_attempt(occurrence: dict, verdict: Verdict) -> bool:
    if verdict.get('kind') != 'hit':
        return True
    head = str(verdict.get('head') or '').split()
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    remainder = norm_command_tokens(str(occurrence.get('command') or ''))[len(head):]
    if occurrence.get('source_surface') == 'mindmap_step' and verdict.get('parameters_valid') is False and ((verdict.get('parameter_error') or {}).get('code') == 'arity_too_few') and (not any((not _LOCATOR_TOKEN.match(token) for token in remainder))):
        return False
    if 'truncated_by' not in occurrence:
        return True
    if occurrence.get('truncated_by') == 'cjk':
        return False
    if len(head) < 2:
        return False
    return any((not _LOCATOR_TOKEN.match(token) for token in remainder))

def slice_is_admissible(occurrence: dict, verdict: Verdict) -> bool:
    return is_command_attempt(occurrence, verdict)

def scenario3_violations(commands: Iterable[dict], *, resolve: Resolve) -> list[dict]:
    out: list[dict] = []
    for item in commands:
        command = str(item.get('command') or '')
        verdict = resolve(command)
        if not is_scenario3_violation(verdict):
            continue
        if not is_command_attempt(item, verdict):
            continue
        out.append({'occurrence_index': int(item.get('occurrence_index') or 0), 'command': command, 'result': verdict})
    return out

def build_head_index(heads: Any) -> dict[int, tuple[str, ...]]:
    grouped: dict[int, list[str]] = {}
    for head in heads or ():
        parts = str(head or '').split()
        if parts:
            grouped.setdefault(len(parts), []).append(' '.join(parts))
    return {size: tuple(sorted(names)) for size, names in grouped.items()}

def build_xml_menu_index(heads: Any) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    table = heads if isinstance(heads, dict) else {}
    for raw_head, raw_entry in table.items():
        if not isinstance(raw_entry, dict):
            continue
        if str(raw_entry.get('origin') or '') != 'vendor_xml':
            continue
        locator = str(raw_entry.get('src') or '')
        source_kind, sep, rest = locator.partition(':')
        _build, sep2, xml_path = rest.partition(':')
        if source_kind != 'vendor_xml' or not sep or (not sep2):
            continue
        parts = [part.strip().casefold() for part in xml_path.split('/') if part.strip()]
        menu_parts = parts[1:-1]
        head = ' '.join(str(raw_head or '').casefold().split())
        command_path = ' '.join(parts[1:])
        if not head or head != command_path:
            continue
        for depth in range(1, len(menu_parts) + 1):
            menu = ' '.join(menu_parts[:depth])
            if menu:
                grouped.setdefault(menu, set()).add(head)
    return {menu: tuple(sorted(descendants)) for menu, descendants in sorted(grouped.items())}

def _one_edit_apart(left: str, right: str) -> bool:
    if left == right:
        return False
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum((1 for a, b in zip(left, right) if a != b)) == 1
    short, long = (left, right) if len(left) < len(right) else (right, left)
    index = 0
    while index < len(short) and short[index] == long[index]:
        index += 1
    return short[index:] == long[index + 1:]

def near_head_candidate(command: str, head_index: dict[int, tuple[str, ...]], *, menu_index: dict[str, tuple[str, ...]] | None=None) -> tuple[str, str] | None:
    from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens
    tokens = norm_command_tokens(command)
    for size in range(min(len(tokens), 8), 1, -1):
        prefix = tokens[:size]
        hits = []
        for head in head_index.get(size, ()):
            parts = head.split()
            differing = [i for i in range(size) if parts[i] != prefix[i]]
            if len(differing) != 1:
                continue
            position = differing[0]
            if position != size - 1:
                continue
            if _one_edit_apart(prefix[position], parts[position]):
                hits.append(head)
        if hits:
            authored = ' '.join(prefix)
            if authored in (menu_index or {}):
                return None
            return (authored, sorted(hits)[0])
    return None

def generation_binding(inventory: dict | None, capability_receipt: dict | None=None) -> dict:
    inv = inventory if isinstance(inventory, dict) else {}
    source = inv.get('source') if isinstance(inv.get('source'), dict) else {}
    binding = {'version': str(inv.get('version') or ''), 'build': str(inv.get('device_os_build') or ''), 'source_filename': str(source.get('filename') or ''), 'source_sha256': str(source.get('sha256') or '')}
    if isinstance(capability_receipt, dict):
        binding.update({key: str(capability_receipt.get(key) or '') for key in ('bed', 'full_version', 'product', 'platform', 'generation_id', 'manifest_sha256', 'projection_sha256')})
    return binding

def _xml_parameter_signature(result: dict) -> str:
    head = str(result.get('head') or '').strip()
    error = result.get('parameter_error')
    if not head or not isinstance(error, dict):
        return head
    required = error.get('required_min')
    maximum = error.get('pmax')
    if isinstance(required, int) and (not isinstance(required, bool)) and isinstance(maximum, int) and (not isinstance(maximum, bool)) and (0 <= required <= maximum <= 64):
        placeholders = [f'<arg{index}>' for index in range(1, required + 1)]
        placeholders.extend((f'[arg{index}]' for index in range(required + 1, maximum + 1)))
        return ' '.join([head, *placeholders])
    index = error.get('argument_index')
    expected_type = str(error.get('expected_type') or '').strip().lower()
    if isinstance(index, int) and (not isinstance(index, bool)) and (index > 0):
        marker = f'{expected_type}:arg{index}' if expected_type else f'arg{index}'
        return f'{head} <{marker}>'
    return head

def scenario3_delta_payload(autoid: str, occurrence: dict, generation: dict) -> dict:
    result = occurrence.get('result') or {}
    return {'autoid': autoid, 'occurrence_index': occurrence['occurrence_index'], 'command': occurrence['command'], 'xml_command': str(result.get('head') or ''), 'xml_signature': _xml_parameter_signature(result), 'xml_locator': str(result.get('src') or ''), 'device_build': str(result.get('device_build') or ''), 'parameter_error': dict(result.get('parameter_error') or {}), 'capability_generation': generation}

def scenario3_claim(autoid: str, occurrence: dict, generation: dict) -> dict:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import conflict_chain_id
    result = occurrence.get('result') or {}
    delta_payload = scenario3_delta_payload(autoid, occurrence, generation)
    delta_id = _canonical_sha256({'schema': S3_DELTA_SCHEMA, 'payload': delta_payload})
    chain_id = conflict_chain_id({'autoid': autoid, 'scenario': 'scenario_3', 'delta_id': delta_id, 'payload': delta_payload})
    return {'schema': CONFLICT_CLAIM_SCHEMA, 'source_kind': 'CapabilityXml', 'claim_kind': S3_CLAIM_KIND, 'conflict_scenario': 'scenario_3', 'reason_code': S3_REASON_CODE, 'delta_id': delta_id, 'conflict_chain_id': chain_id, 'options': list(S3_OPTIONS), 'xml_present': True, 'command': occurrence['command'], 'xml_command': str(result.get('head') or ''), 'xml_signature': _xml_parameter_signature(result), 'xml_locator': str(result.get('src') or ''), 'device_build': str(result.get('device_build') or ''), 'parameter_error': dict(result.get('parameter_error') or {}), 'occurrence_index': occurrence['occurrence_index'], 'capability_generation': generation, 'requires_user_decision': True, 'terminal': False, 'reason': '用例命令与设备 XML 的参数形态不一致'}

def scenario3_ledger_mutator(autoid: str, violations: list[dict], generation: dict) -> Callable[[list], list]:

    def _mutate(claims: list) -> list:
        kept = [claim for claim in claims if not (claim.get('claim_kind') == S3_CLAIM_KIND and claim.get('reason_code') == S3_REASON_CODE)]
        for occurrence in violations:
            kept.append(scenario3_claim(autoid, occurrence, generation))
        return kept
    return _mutate

def near_head_violations(commands: Iterable[dict], *, resolve: Resolve, head_index: dict[int, tuple[str, ...]], heads: Any=None) -> list[dict]:
    """收「命令头写错了名字」的全部 Δ。判据见 `near_head_candidate`。

    只看树里**没有**这个头的候选（`kind != "hit"`）：头在树里就该走参数契约
    那条（③ 本形），不该再问一遍名字对不对。

    `heads` 用来取近似头在树里的 `src` 定位。**这不是可选装饰**：
    `conflict_chain.capability_xml_claim_reviewable` 要求 claim 带非空
    `xml_locator`，缺了它 `_build_scenario3_question` 直接返回 None，用户拿到的是
    「引擎未能构造出可回答的问题」——比压根不检测更糟（闸还把整批停着）。
    """
    table = heads if isinstance(heads, dict) else {}
    menu_index = build_xml_menu_index(table)
    out: list[dict] = []
    for item in commands:
        command = str(item.get('command') or '')
        if not command.strip():
            continue
        verdict = resolve(command)
        if verdict.get('kind') == 'hit':
            continue
        near = near_head_candidate(command, head_index, menu_index=menu_index)
        if near is None:
            continue
        entry = table.get(near[1])
        if not isinstance(entry, dict):
            continue
        if str(entry.get('origin') or '') != 'vendor_xml':
            continue
        locator = str(entry.get('src') or '')
        if not locator:
            continue
        out.append({'occurrence_index': int(item.get('occurrence_index') or 0), 'command': command, 'authored_head': near[0], 'xml_command': near[1], 'xml_locator': locator, 'result': verdict})
    return out

def near_head_delta_payload(autoid: str, occurrence: dict, generation: dict) -> dict:
    result = occurrence.get('result') or {}
    return {'autoid': autoid, 'occurrence_index': occurrence['occurrence_index'], 'command': occurrence['command'], 'authored_head': occurrence['authored_head'], 'xml_command': occurrence['xml_command'], 'xml_locator': str(occurrence.get('xml_locator') or ''), 'device_build': str(result.get('device_build') or ''), 'capability_generation': generation}

def near_head_claim(autoid: str, occurrence: dict, generation: dict) -> dict:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import conflict_chain_id
    delta_payload = near_head_delta_payload(autoid, occurrence, generation)
    delta_id = _canonical_sha256({'schema': S3_NEAR_HEAD_DELTA_SCHEMA, 'payload': delta_payload})
    chain_id = conflict_chain_id({'autoid': autoid, 'scenario': 'scenario_3', 'delta_id': delta_id, 'payload': delta_payload})
    result = occurrence.get('result') or {}
    return {'schema': CONFLICT_CLAIM_SCHEMA, 'source_kind': 'CapabilityXml', 'claim_kind': S3_CLAIM_KIND, 'conflict_scenario': 'scenario_3', 'reason_code': S3_NEAR_HEAD_REASON_CODE, 'delta_id': delta_id, 'conflict_chain_id': chain_id, 'options': list(S3_OPTIONS), 'xml_present': True, 'command': occurrence['command'], 'authored_head': occurrence['authored_head'], 'xml_command': occurrence['xml_command'], 'xml_locator': str(occurrence.get('xml_locator') or ''), 'device_build': str(result.get('device_build') or ''), 'parameter_error': {}, 'occurrence_index': occurrence['occurrence_index'], 'capability_generation': generation, 'requires_user_decision': True, 'terminal': False, 'reason': '用例写的命令名在设备命令树里不存在，树里有一个只差一个字符的'}

def near_head_ledger_mutator(autoid: str, violations: list[dict], generation: dict) -> Callable[[list], list]:

    def _mutate(claims: list) -> list:
        kept = [claim for claim in claims if not (claim.get('claim_kind') == S3_CLAIM_KIND and claim.get('reason_code') == S3_NEAR_HEAD_REASON_CODE)]
        for occurrence in violations:
            kept.append(near_head_claim(autoid, occurrence, generation))
        return kept
    return _mutate

def static_scenario3_ledger_mutator(autoid: str, parameter_violations: list[dict], near_head_misses: list[dict], generation: dict, *, superseded_delta_ids: Iterable[str]=()) -> Callable[[list], list]:
    fresh = [scenario3_claim(autoid, occurrence, generation) for occurrence in parameter_violations] + [near_head_claim(autoid, occurrence, generation) for occurrence in near_head_misses]
    replace_ids = {str(value) for value in superseded_delta_ids if str(value)} | {str(claim.get('delta_id') or '') for claim in fresh if str(claim.get('delta_id') or '')}

    def _mutate(claims: list) -> list:
        kept = [claim for claim in claims if not (isinstance(claim, dict) and str(claim.get('delta_id') or '') in replace_ids)]
        return kept + fresh
    return _mutate

def xml_result_assertions(verdict: Verdict, valid_operators: Iterable[str]) -> list[dict]:
    if not (verdict.get('kind') == 'hit' and verdict.get('origin') == 'vendor_xml'):
        return []
    raw_results = verdict.get('results')
    if not isinstance(raw_results, list) or not raw_results:
        return []
    operators = frozenset(valid_operators)
    assertions: list[dict[str, str]] = []
    for declaration in raw_results:
        if not isinstance(declaration, dict) or not set(declaration).issubset({'operator', 'text', 'locator'}):
            return []
        operator = str(declaration.get('operator') or '').strip()
        text = str(declaration.get('text') or '')
        locator = str(declaration.get('locator') or '').strip()
        if operator not in operators or not text or (not locator):
            return []
        if operator == 'found_times':
            return []
        assertions.append({'operator': operator, 'value': text, 'locator': locator})
    return assertions

def scenario4_conflict(group: dict, verdict: Verdict, valid_operators: Iterable[str]) -> dict | None:
    xml_assertions = xml_result_assertions(verdict, valid_operators)
    if not xml_assertions:
        return None
    case_assertions = [dict(item) for item in group.get('assertions') or []]
    if not case_assertions:
        return None
    case_multiset = sorted(((item['operator'], item['value']) for item in case_assertions))
    xml_multiset = sorted(((item['operator'], item['value']) for item in xml_assertions))
    if case_multiset == xml_multiset:
        return None
    return {'occurrence_index': int(group['occurrence_index']), 'original_command': str(group['command']), 'rewritten_command': str(verdict.get('head') or group['command']), 'xml_locator': str(verdict.get('src') or ''), 'case_assertions': case_assertions, 'xml_assertions': xml_assertions}

def scenario4_claim(autoid: str, conflict: dict, generation: dict) -> dict:
    from cex_core.engine.ist_core.compile_engine.conflict_chain import conflict_chain_id
    delta_payload = {'autoid': autoid, **conflict, 'capability_generation': generation}
    delta_id = _canonical_sha256({'schema': S4_DELTA_SCHEMA, 'payload': delta_payload})
    return {'schema': CONFLICT_CLAIM_SCHEMA, 'source_kind': 'CapabilityXml', 'claim_kind': S4_CLAIM_KIND, 'conflict_scenario': 'scenario_4', 'reason_code': S4_REASON_CODE, 'delta_id': delta_id, 'conflict_chain_id': conflict_chain_id({'autoid': autoid, 'scenario': 'scenario_4', 'delta_id': delta_id, 'payload': delta_payload}), 'options': list(S4_OPTIONS), 'xml_present': True, **conflict, 'case_expectation': json.dumps(conflict['case_assertions'], ensure_ascii=False, sort_keys=True), 'xml_expectation': json.dumps(conflict['xml_assertions'], ensure_ascii=False, sort_keys=True), 'case_expectation_supported': False, 'capability_generation': generation, 'requires_user_decision': True, 'terminal': False, 'reason': '用例静态断言与设备 XML 的结构化结果声明不一致'}

def scenario4_ledger_mutator(autoid: str, conflicts: list[dict], generation: dict) -> Callable[[list], list]:

    def _mutate(claims: list) -> list:
        kept = [claim for claim in claims if not (claim.get('claim_kind') == S4_CLAIM_KIND and claim.get('reason_code') == S4_REASON_CODE)]
        for conflict in conflicts:
            kept.append(scenario4_claim(autoid, conflict, generation))
        return kept
    return _mutate
_CJK_BOUNDARY = re.compile('[⺀-鿿豈-\ufaff︰-﹏\uff00-\uffef\u3000-〿]')
_SENTENCE_BREAK = re.compile('[,;]')
_ASCII_WORD = re.compile('[A-Za-z][A-Za-z0-9_-]*')

def _normalize_unicode_spaces(text: str) -> str:
    return ''.join((' ' if char.isspace() and (not char.isascii()) else char for char in str(text or '')))

def command_head_first_tokens(heads: Any) -> frozenset[str]:
    out: set[str] = set()
    for head in heads or ():
        parts = str(head or '').split()
        if parts:
            out.add(parts[0].lower())
    return frozenset(out)

def mindmap_command_slices(line: str, *, head_first_tokens) -> list[dict]:
    text = str(line or '')
    if not text.strip():
        return []
    out: list[dict] = []
    for match in _ASCII_WORD.finditer(text):
        if match.group(0).lower() not in head_first_tokens:
            continue
        prev = text[match.start() - 1] if match.start() else ''
        if prev and prev.isascii() and (prev.isalnum() or prev == '_'):
            continue
        tail = text[match.start():]
        cjk = _CJK_BOUNDARY.search(tail)
        punct = _SENTENCE_BREAK.search(tail)
        first = min([found for found in (cjk, punct) if found is not None], key=lambda found: found.start(), default=None)
        truncated_by = 'eol'
        if first is not None:
            truncated_by = 'cjk' if first is cjk else 'punct'
            tail = tail[:first.start()]
        raw_span_end = match.start() + len(tail)
        tail = _normalize_unicode_spaces(tail).strip()
        if tail:
            out.append({'command': tail, 'truncated_by': truncated_by, 'span_start': match.start(), 'span_end': raw_span_end})
    return out

def mindmap_command_occurrences(case: dict, *, head_first_tokens=None) -> list[dict]:
    out: list[dict] = []
    index = 0
    for step in case.get('steps') or []:
        if not isinstance(step, dict):
            continue
        for line in str(step.get('text') or '').splitlines():
            text = line.strip()
            if not text:
                continue
            step_n = str(step.get('n') or '')
            out.append({'command': text, 'occurrence_index': index, 'step_n': step_n, 'source_surface': 'mindmap_step'})
            if head_first_tokens:
                seen = {text}
                covered_until = -1
                for slice_index, sliced in enumerate(mindmap_command_slices(line, head_first_tokens=head_first_tokens), start=1):
                    command = sliced['command']
                    span_start = sliced.get('span_start')
                    span_end = sliced.get('span_end')
                    if span_start is not None and span_start < covered_until:
                        continue
                    if span_end is not None:
                        covered_until = max(covered_until, int(span_end))
                    if command in seen:
                        continue
                    seen.add(command)
                    out.append({'command': command, 'occurrence_index': index, 'slice_index': slice_index, 'truncated_by': sliced['truncated_by'], 'step_n': step_n, 'source_surface': 'mindmap_step'})
            index += 1
    return out

def mindmap_assertion_groups(case: dict, *, resolve: Resolve) -> list[dict]:
    by_step: dict[str, list[dict]] = {}
    for item in case.get('expectations_by_step') or []:
        if not isinstance(item, dict):
            continue
        assertion = item.get('assertion')
        if not isinstance(assertion, dict):
            continue
        operator = str(assertion.get('operator') or '').strip()
        value = str(assertion.get('value') or '')
        if not operator or not value:
            continue
        by_step.setdefault(str(item.get('n') or '').strip(), []).append({'operator': operator, 'value': value})
    if not by_step:
        return []
    groups: list[dict] = []
    for occurrence in mindmap_command_occurrences(case):
        assertions = by_step.get(occurrence['step_n'])
        if not assertions:
            continue
        verdict = resolve(occurrence['command'])
        if verdict.get('kind') != 'hit':
            continue
        siblings = [other for other in mindmap_command_occurrences(case) if other['step_n'] == occurrence['step_n'] and other['command'] != occurrence['command'] and (resolve(other['command']).get('kind') == 'hit')]
        if siblings:
            continue
        groups.append({'occurrence_index': occurrence['occurrence_index'], 'command': occurrence['command'], 'assertions': assertions})
    return groups
