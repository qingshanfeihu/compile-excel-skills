# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/ir_coverage.py（sha256 04b0f521b93f110b）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
from pathlib import Path
_ATLAS_PATH = _cex_data_path('') / 'knowledge/data/compile_ref/capability_atlas.json'
_VALIDATION_GAP_FAMILIES: frozenset[str] = frozenset()

def _is_disabled(info) -> bool:
    return isinstance(info, dict) and bool(info.get('disabled'))

def load_atlas() -> dict:
    return json.loads(_ATLAS_PATH.read_text(encoding='utf-8'))

def _contract(contract: 'object | None'=None) -> dict:
    """取当前 Excel 契约。

    只接受 ValidatedExcelContract 或 None;旧的 capability_atlas.json 裸 dict
    实参已不再被静默忽略——传错类型当场炸,别让调用方以为自己传的 atlas 生效了。
    """
    from cex_core.engine.case_compiler.excel_contract import ValidatedExcelContract, load_excel_contract
    if contract is None:
        return load_excel_contract()
    if not isinstance(contract, ValidatedExcelContract):
        raise TypeError('ir_coverage expects a ValidatedExcelContract; the legacy raw atlas dict is no longer accepted')
    return contract

def _enabled_entries(contract: dict) -> list[dict]:
    return [entry for entry in contract['entries'] if entry['status'] == 'enabled']

def all_capability_names(atlas: dict | None=None) -> frozenset[str]:
    contract = _contract(atlas)
    names = {str(entry['f']) for entry in _enabled_entries(contract)}
    names.update((f"execute:{item['dispatcher']}:{item['normalized']}" for item in contract['execute_actions'] if item['status'] == 'enabled'))
    return frozenset(names)

def all_enabled_entry_capability_names(contract: dict | None=None) -> frozenset[str]:
    source = _contract(contract)
    return frozenset((f"{entry['e']}::{entry['f']}" for entry in _enabled_entries(source)))

def _execute_capability_info(name: str, contract: dict) -> dict | None:
    if not name.startswith('execute:'):
        return None
    _, _, tail = name.partition('execute:')
    dispatcher, separator, normalized = tail.partition(':')
    if not separator:
        return None
    matches = [item for item in contract['execute_actions'] if item['status'] == 'enabled' and item['dispatcher'] == dispatcher and (item['normalized'] == normalized)]
    return matches[0] if len(matches) == 1 else None

def _entry_for_name(name: str, contract: dict) -> dict | None:
    candidates = [entry for entry in _enabled_entries(contract) if entry['f'] == name]
    if not candidates:
        return None
    priority = {'check_point': 0, 'time': 1, 'APV_0': 2, 'test_env': 3}
    return min(candidates, key=lambda entry: (priority.get(entry['e'], 9), entry['e']))

def _arguments_for_entry(entry: dict, contract: dict) -> str:
    e, f = (entry['e'], entry['f'])
    if e == 'check_point':
        return 'expected'
    if e == 'time' and f == 'sleep':
        return '1'
    if f == 'cmds_config':
        return 'probe\nprobe_second'
    if f in {'cmd', 'cmd_enable', 'cmd_config', 'array_config'}:
        return 'probe'
    if f == 'execute':
        action = next((item for item in contract['execute_actions'] if item['status'] == 'enabled' and e in item['allowed_es']), None)
        if action is None:
            return ''
        value = str(action['name'])
        if (action.get('signature') or {}).get('required'):
            value += '：payload'
        return value
    parts: list[str] = []
    for index, parameter in enumerate(entry['signature']['parameters'], start=1):
        if not parameter['required']:
            continue
        value = f'arg_{index}'
        if parameter['kind'] == 'keyword_only':
            value = f"{parameter['name']}={value}"
        parts.append(value)
    return ', '.join(parts)

def _block_for_entry(entry: dict, contract: dict) -> dict:
    block = {'kind': 'STEP', 'E': entry['e'], 'F': entry['f'], 'G': _arguments_for_entry(entry, contract), 'ref': 'precedent:excel_contract'}
    if entry['e'] == 'check_point' and entry['f'] == 'found_times':
        block['I'] = '1'
    if entry['e'] == 'check_point':
        block['observation_ref'] = 'obs_excel_contract_probe'
    return block

def _expression_blocks(block: dict) -> list[dict]:
    if block.get('E') != 'check_point':
        return [block]
    return [{'kind': 'STEP', 'E': 'APV_0', 'F': 'cmd_config', 'G': 'probe', 'ref': 'precedent:excel_contract', 'observation_id': 'obs_excel_contract_probe', 'result_channel': 'result_excel_contract_probe'}, block]

def _capability_block(name: str, atlas: dict) -> dict | None:
    contract = _contract(atlas)
    action = _execute_capability_info(name, contract)
    if action is not None:
        if not action.get('allowed_es'):
            return None
        g = str(action['name'])
        if (action.get('signature') or {}).get('required'):
            g += '：payload'
        return {'kind': 'STEP', 'E': action['allowed_es'][0], 'F': 'execute', 'G': g, 'ref': 'precedent:excel_contract'}
    entry = _entry_for_name(name, contract)
    if entry is None:
        return None
    return _block_for_entry(entry, contract)

def enabled_entry_expression_evidence(identity: str, contract: dict | None=None) -> dict:
    source = _contract(contract)
    e_value, separator, f_value = str(identity).partition('::')
    if not separator or not e_value or (not f_value):
        return {'name': identity, 'valid': False, 'block': None, 'steps': [], 'validated_by': '', 'error': 'entry identity must use E::F'}
    entries = [entry for entry in _enabled_entries(source) if entry['e'] == e_value and entry['f'] == f_value]
    if len(entries) != 1:
        return {'name': identity, 'valid': False, 'block': None, 'steps': [], 'validated_by': '', 'error': 'E::F is not one exact enabled contract entry'}
    block = _block_for_entry(entries[0], source)
    blocks = _expression_blocks(block)
    from cex_core.engine.case_compiler.blocks import expand_blocks
    steps, provenance, error = expand_blocks(blocks)
    bound = bool(steps) and any((step.get('E') == e_value and step.get('F') == f_value for step in steps))
    binding_error = '' if bound else f'expanded steps do not contain exact {identity}'
    valid = error is None and bound and bool(provenance)
    return {'name': identity, 'valid': valid, 'block': block, 'steps': steps or [], 'provenance': provenance or [], 'validated_by': 'blocks.STEP:excel_contract+signature+exact_EF_binding' if valid else '', 'error': error or binding_error}

def _binding_error(name: str, steps: list[dict], atlas: dict) -> str:
    contract = _contract(atlas)
    action = _execute_capability_info(name, contract)
    if action is not None:
        from cex_core.engine.case_compiler.excel_contract import ExcelContractError, validate_execute_action
        for step in steps:
            if step.get('F') != 'execute':
                continue
            try:
                actual = validate_execute_action(str(step.get('E') or ''), str(step.get('G') or ''), contract)
            except ExcelContractError:
                continue
            if actual['dispatcher'] == action['dispatcher'] and actual['normalized'] == action['normalized']:
                return ''
        return f'queried execute action {name!r} is absent from expanded E/F/G'
    entry = _entry_for_name(name, contract)
    if entry is None:
        return f'{name!r} is not an enabled contract capability'
    if any((step.get('E') == entry['e'] and step.get('F') == entry['f'] for step in steps)):
        return ''
    label = 'check_point' if entry['e'] == 'check_point' else 'contract method'
    return f"queried {label} {name!r} expected E={entry['e']!r}, F={entry['f']!r}, but expanded steps do not contain it"

def capability_expression_evidence(name: str, atlas: dict | None=None) -> dict:
    source = _contract(atlas)
    block = _capability_block(name, source)
    if block is None:
        return {'name': name, 'valid': False, 'block': None, 'steps': [], 'validated_by': '', 'error': 'no blocks construction path'}
    from cex_core.engine.case_compiler.blocks import expand_blocks
    blocks = _expression_blocks(block)
    steps, provenance, error = expand_blocks(blocks)
    binding_error = _binding_error(name, steps or [], source) if error is None else ''
    valid = error is None and (not binding_error) and bool(steps) and bool(provenance)
    return {'name': name, 'valid': valid, 'block': block, 'steps': steps or [], 'provenance': provenance or [], 'validated_by': 'blocks.STEP:excel_contract+signature+execute_action+H/I+independent_EFG_binding' if valid else '', 'error': error or binding_error}

def classify_capability(name: str, atlas: dict | None=None) -> str:
    if name not in all_capability_names(atlas):
        return 'out_of_range'
    return 'covered' if capability_expression_evidence(name, atlas)['valid'] else 'todo'

def coverage_partition(atlas: dict | None=None) -> tuple[frozenset[str], frozenset[str]]:
    source = _contract(atlas)
    names = all_capability_names(source)
    covered = frozenset((n for n in names if classify_capability(n, source) == 'covered'))
    todo = names - covered
    return (covered, todo)
IR_GAP_FACT_EVENTS: frozenset[str] = frozenset({'ir_gap', 'step_escape'})

def select_ir_gap_facts(facts: list[dict]) -> list[dict]:
    return [fact for fact in facts if isinstance(fact, dict) and str(fact.get('ev') or '') in IR_GAP_FACT_EVENTS]

def ir_gap_unresolved(todo_set: frozenset[str], ir_gap_facts: list[dict]) -> frozenset[str]:
    touched: set[str] = set()
    for fact in ir_gap_facts:
        touched.update(fact.get('capabilities_touched') or [])
    return frozenset(todo_set) & touched
_PRODUCER_EVENTS_WITH_CAPABILITIES = frozenset({'composed', 'mechanical_case_repaired'})

def production_covered(facts: list[dict]) -> frozenset[str]:
    used: set[str] = set()
    for fact in facts:
        if not isinstance(fact, dict) or fact.get('ev') not in _PRODUCER_EVENTS_WITH_CAPABILITIES:
            continue
        used.update((str(name) for name in fact.get('capabilities_used') or [] if str(name)))
    return frozenset(used)
