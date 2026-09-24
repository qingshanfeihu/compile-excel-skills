# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/blocks.py（sha256 fd9c31d8c99845f7）。不在这里手改。
from __future__ import annotations
import copy
import hashlib
import json
import re
import shlex
from typing import Any
from cex_core.engine.case_compiler.case_ir import IInjectionSyntaxError, parse_found_times_cells, validate_i_injection_syntax
from cex_core.engine.case_compiler.distribution_assertion import distribution_count_binding_error
_ASSERT_OPS = ('found', 'not_found', 'abs_found')
_EXIT_STATUS_EXPECTS = ('success', 'failure')
_ANSWERER_KINDS = ('device', 'fixture', 'bed_service', 'undetermined')
_ANSWERER_FIELD_KEYS = frozenset({'kind', 'ref', 'note'})
_EXIT_STATUS_MASKING_REFUSAL = "OBSERVE_EXIT.cmd must leave the observed command's status unmasked; pipes, ';', '||', background execution, newlines, and command substitution are rejected (use a direct command, or '&&' only when every command must succeed)"
_REGISTER_NAME_RE = re.compile('^[a-zA-Z_][a-zA-Z0-9_]*$')
_AUTO_REGISTER_RE = re.compile('^v\\d+$')
_REF_KINDS = ('footprint', 'manual', 'precedent', 'env_facts', 'intent', 'config_derived', 'skeleton', 'test_env_dispatch', 'device_runtime', 'distribution_derived', 'membership_derived', 'captured_relation')
_REF_LOCATOR_REQUIRED = frozenset({'footprint', 'manual', 'precedent', 'env_facts', 'intent', 'skeleton'})

def _parse_ref(ref: Any) -> dict:
    s = str(ref or '').strip()
    if not s:
        return {'kind': 'emit_auto', 'ref': ''}
    head, _, tail = s.partition(':')
    if head in _REF_KINDS:
        return {'kind': head, 'ref': tail.strip()}
    return {'kind': 'emit_auto', 'ref': s}

def _dispatch_source(e: str, f: str, g: str, ref: Any=None) -> dict:
    source_text = str(ref or '').strip()
    parsed = _parse_ref(ref)
    if parsed == {'kind': 'test_env_dispatch', 'ref': ''}:
        parsed = {'kind': 'emit_auto', 'ref': ''}
        source_text = ''
    if parsed['kind'] != 'emit_auto':
        return parsed
    if source_text:
        return parsed
    if str(e or '').strip() != 'test_env':
        return parsed
    dispatch_method = str(f or '').strip().lower()
    try:
        from cex_core.engine.case_compiler.excel_contract import ExcelContractError, contract_entry, load_excel_contract
        contract = load_excel_contract()
        entry = contract_entry('test_env', dispatch_method, contract)
    except ExcelContractError:
        return parsed
    if entry is None or entry.get('status') != 'enabled':
        return parsed
    return {'kind': 'test_env_dispatch', 'ref': f'lib/env.py#Env.{dispatch_method}'}

def _err(i: int, kind: str, msg: str) -> str:
    return f'blocks[{i}]({kind}): {msg}'
_DUT_HOSTS = ('APV_0', 'APV_1')
_CONFIG_STEP_FUNCTIONS = frozenset({'cmd_config', 'cmds_config'})

def _observe_step(host: str, cmd: str, desc: str, save_as: str='') -> dict:
    host = (host or '').strip()
    if host in _DUT_HOSTS:
        st = {'E': host, 'F': 'cmd_config', 'G': cmd, 'desc': desc}
    else:
        st = {'E': 'test_env', 'F': host.lower(), 'G': cmd, 'desc': desc}
    if save_as:
        st['H'] = save_as
    return st

def _answerer_shape_error(i: int, kind: str, b: dict) -> str | None:
    answerer = b.get('answerer')
    if answerer is None:
        return None
    if not isinstance(answerer, dict):
        return _err(i, kind, 'answerer must be an object {kind, ref|note} naming who answers this observation')
    extra = sorted(set(answerer) - _ANSWERER_FIELD_KEYS)
    if extra:
        return _err(i, kind, f"answerer has unsupported field(s): {', '.join(extra)} (closed set: kind, ref, note)")
    a_kind = str(answerer.get('kind') or '').strip()
    if a_kind not in _ANSWERER_KINDS:
        return _err(i, kind, f'answerer.kind must be one of {_ANSWERER_KINDS}; got {a_kind!r}')
    if a_kind in ('device', 'fixture'):
        ref = answerer.get('ref')
        if not isinstance(ref, int) or isinstance(ref, bool) or ref < 0:
            return _err(i, kind, f'answerer.ref for kind={a_kind} must be a blocks[] index (non-negative integer) of the block that establishes the answerer')
    elif a_kind == 'bed_service':
        ref = answerer.get('ref')
        if not isinstance(ref, str) or not ref.strip():
            return _err(i, kind, 'answerer.ref for kind=bed_service must be a device name from the bed topology (non-empty text)')
    else:
        note = answerer.get('note')
        if not isinstance(note, str) or not note.strip():
            return _err(i, kind, 'answerer.note for kind=undetermined must be one line naming what no source states about who answers')
    return None
_STEP_FIELDS = frozenset({'kind', 'E', 'F', 'G', 'H', 'I', 'desc', 'ref', 'assertion_type', 'exempt', 'reason_code', 'observation_id', 'result_channel', 'observation_ref', 'binding_input', 'timeout_s', 'expectation_id', 'semantic_key'})
_ASSERTION_ID_FIELDS = ('expectation_id', 'semantic_key')
COMMAND_TIMEOUT_MIN_S = 1
COMMAND_TIMEOUT_MAX_S = 600

def _command_timeout_error(i: int, kind: str, b: dict) -> str | None:
    if 'timeout_s' not in b:
        return None
    value = b.get('timeout_s')
    if isinstance(value, bool) or not isinstance(value, int):
        return _err(i, kind, 'timeout_s must be an integer; booleans are not accepted')
    if not COMMAND_TIMEOUT_MIN_S <= value <= COMMAND_TIMEOUT_MAX_S:
        return _err(i, kind, f'timeout_s must be between {COMMAND_TIMEOUT_MIN_S} and {COMMAND_TIMEOUT_MAX_S} seconds')
    return None

def _timeout_command_error(i: int, kind: str, command: str) -> str | None:
    from cex_core.engine.case_compiler.excel_contract import ExcelContractError, parse_g_arguments
    try:
        args, kwargs = parse_g_arguments(command, 'cmd_config')
    except ExcelContractError:
        return _err(i, kind, 'timeout_s requires a valid single-command G argument list')
    if len(args) != 1:
        return _err(i, kind, 'timeout_s requires exactly one product command per entry')
    if 'timeout' in kwargs:
        return _err(i, kind, 'timeout_s conflicts with an existing timeout= argument; supply only one')
    return None
SSL_CERT_LOAD_KIND = 'SSL_CERT_LOAD'
_NO_ASSERTION_ID_KINDS = frozenset({'CONFIG', 'OBSERVE_ONLY', 'CAPTURE', 'SLEEP', 'OBSERVE_ASSERT', 'SSL_CERT_LOAD'})
_ASSERTION_ID_BLOCK_KINDS = frozenset({'CAPTURE_COMPARE', 'OBSERVE_DIST', 'OBSERVE_MEMBER', 'EXPECT_FROM', 'OBSERVE_EXIT'})

def _exit_status_command(command: str) -> str:
    return f"""( {command} ); ist_case_exit_code=$?; echo; printf 'IST_EXIT_STATUS=%s' "$ist_case_exit_code"; echo"""

def _probe_tool_name(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ''
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.match('^[A-Za-z_][A-Za-z0-9_]*=', token) or token in ('sudo', 'env'):
            index += 1
            continue
        if token == 'timeout':
            index += 1
            if index < len(tokens) and re.match('^\\d+(?:\\.\\d+)?[smhd]?$', tokens[index]):
                index += 1
            continue
        return token.rsplit('/', 1)[-1].lower()
    return ''

def _exit_status_masking_error(command: str) -> str:
    if '\n' in command or '\r' in command:
        return _EXIT_STATUS_MASKING_REFUSAL
    if '`' in command or '$(' in command:
        return _EXIT_STATUS_MASKING_REFUSAL
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars='();<>|&')
        lexer.whitespace_split = True
        lexer.commenters = ''
        tokens = list(lexer)
    except ValueError:
        return _EXIT_STATUS_MASKING_REFUSAL
    punctuation = frozenset('();<>|&')
    for token in tokens:
        if not token or not all((char in punctuation for char in token)):
            continue
        if '|' in token or ';' in token:
            return _EXIT_STATUS_MASKING_REFUSAL
        if '&' in token and token != '&&' and ('<' not in token) and ('>' not in token):
            return _EXIT_STATUS_MASKING_REFUSAL
    return ''

def _assertion_identity(container: dict) -> tuple[dict[str, str], str]:
    out: dict[str, str] = {}
    for name in _ASSERTION_ID_FIELDS:
        if name not in container:
            continue
        value = container[name]
        if not isinstance(value, str) or not value.strip():
            return ({}, f'{name}, when present, must be the non-empty identifier minted by the typed expectation contract (copy it verbatim)')
        out[name] = value.strip()
    return (out, '')

def _reject_block_level_assertion_ids(i: int, kind: str, b: dict) -> str | None:
    present = [name for name in _ASSERTION_ID_FIELDS if name in b]
    if not present:
        return None
    hint = ' — declare them on each asserts[] entry instead' if kind == 'OBSERVE_ASSERT' else ' — this combinator produces no check_point to bind them to'
    return _err(i, kind, f"unsupported field(s): {', '.join(present)}{hint}")

def _collect_nested_assertion_ids(value: Any, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, sub in value.items():
            child = f'{path}.{key}' if path else str(key)
            if key in _ASSERTION_ID_FIELDS:
                out.append(child)
                continue
            _collect_nested_assertion_ids(sub, child, out)
    elif isinstance(value, list):
        for index, sub in enumerate(value):
            _collect_nested_assertion_ids(sub, f'{path}[{index}]', out)

def _nested_assertion_id_error(i: int, kind: str, b: dict) -> str | None:
    found: list[str] = []
    for key, value in b.items():
        if key in _ASSERTION_ID_FIELDS:
            continue
        if kind == 'OBSERVE_ASSERT' and key == 'asserts' and isinstance(value, list):
            for j, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                for sub_key, sub_value in item.items():
                    if sub_key in _ASSERTION_ID_FIELDS:
                        continue
                    _collect_nested_assertion_ids(sub_value, f'asserts[{j}].{sub_key}', found)
            continue
        _collect_nested_assertion_ids(value, str(key), found)
    if not found:
        return None
    return _err(i, kind, f"unsupported field(s): {', '.join(found)} — assertion identity is only read at the assertion-bearing position (the combinator itself, or each OBSERVE_ASSERT asserts[] entry); nested containers are never consulted, so an id written there is silently dropped")

def _reject_explicit_provenance_assertion_ids(i: int, kind: str, pv: Any) -> str | None:
    if not isinstance(pv, dict):
        return None
    present = [name for name in _ASSERTION_ID_FIELDS if name in pv]
    if not present:
        return None
    return f"provenance_steps[{i}] (for blocks[{i}]({kind})): unsupported field(s): {', '.join(present)} — the explicit provenance channel carries one entry per combinator, so one id there would be copied onto every row this combinator expands to (including non-assertion rows, and every one of N assertions). Declare the pair on the assertion itself: each OBSERVE_ASSERT asserts[] entry, the combinator that synthesizes exactly one assertion, or an E=check_point STEP."

def _assertion_slot_label(kind: str, block_index: int, offset: int) -> str:
    if kind == 'OBSERVE_ASSERT':
        return f'blocks[{block_index}].asserts[{offset - 1}]'
    return f'blocks[{block_index}]'

def _assertion_identity_coverage_error(prov_out: list[dict], slots: list[tuple[str, int]]) -> str | None:
    if not slots:
        return None
    touched = 0
    missing: list[tuple[str, list[str]]] = []
    for label, index in slots:
        entry = prov_out[index] if index < len(prov_out) else {}
        absent = [name for name in _ASSERTION_ID_FIELDS if not entry.get(name)]
        if len(absent) < len(_ASSERTION_ID_FIELDS):
            touched += 1
        if absent:
            missing.append((label, absent))
    if not touched or not missing:
        return None
    carried = len(slots) - len(missing)
    detail = '; '.join((f"{label} lacks {', '.join(names)}" for label, names in missing))
    return f'assertion identity coverage is partial: {carried} of {len(slots)} check_point assertions carry both {_ASSERTION_ID_FIELDS[0]} and {_ASSERTION_ID_FIELDS[1]}, but {detail}. The emit identity gate requires every final assertion to carry a contract identity, so within one case either all assertions carry the pair minted by the typed expectation contract, or none may.'

def _derived_binding_source(*, source_kind: str, recipe_id: str, rule_id: str, source_input: dict[str, Any], output_step: dict[str, Any], output_ordinal: int=0) -> tuple[dict[str, Any] | None, str]:
    from cex_core.engine.case_compiler.provenance_ir import build_config_binding_derivation_receipt
    receipt, error = build_config_binding_derivation_receipt(source_kind=source_kind, recipe_id=recipe_id, rule_id=rule_id, source_input=source_input, output_step=output_step, output_ordinal=output_ordinal)
    if receipt is None:
        return (None, error)
    return ({'kind': source_kind, 'ref': receipt['recipe_id'], 'receipt': receipt}, '')

def _expand_generic_step(i: int, b: dict, defined_registers: set[str], capture_registers: set[str] | None=None) -> tuple[dict | None, dict | None, str | None]:
    extra = sorted(set(b) - _STEP_FIELDS)
    if extra:
        client_hint = ' STEP has no host/cmd/asserts fields: a client command with an assertion belongs in OBSERVE_ASSERT {host, cmd, asserts}, which derives test_env dispatch provenance mechanically.' if any((field in extra for field in ('host', 'cmd', 'asserts'))) else ''
        return (None, None, _err(i, 'STEP', f"unsupported field(s): {', '.join(extra)}.{client_hint}"))
    e_raw, f_raw, g_raw = (b.get('E'), b.get('F'), b.get('G'))
    if not isinstance(e_raw, str) or not e_raw.strip():
        return (None, None, _err(i, 'STEP', 'E must be a non-empty framework object name'))
    if not isinstance(f_raw, str) or not f_raw.strip():
        return (None, None, _err(i, 'STEP', 'F must be a non-empty framework method name'))
    if not isinstance(g_raw, str):
        return (None, None, _err(i, 'STEP', 'G must be a string (empty text is allowed where the method arity is zero)'))
    e, f, g = (e_raw.strip(), f_raw.strip(), g_raw)
    timeout_error = _command_timeout_error(i, 'STEP', b)
    if timeout_error:
        return (None, None, timeout_error)
    if 'timeout_s' in b:
        if not e.startswith('APV') or f != 'cmd_config':
            return (None, None, _err(i, 'STEP', 'timeout_s on STEP requires E=APV* and F=cmd_config'))
        timeout_error = _timeout_command_error(i, 'STEP', g)
        if timeout_error:
            return (None, None, timeout_error)
        g = f"{g},timeout={b['timeout_s']}"
    ref = str(b.get('ref') or '').strip()
    from cex_core.engine.case_compiler.excel_contract import ExcelContractError, contract_entry, load_excel_contract, validate_g_for_entry
    try:
        contract = load_excel_contract()
    except ExcelContractError as exc:
        return (None, None, _err(i, 'STEP', f'Excel function contract is unavailable: {exc}'))
    f_cmp = f.lower() if e == 'test_env' else f
    entry = contract_entry(e, f_cmp, contract)
    if entry is None:
        client_hint = ' For an environment/client observation, use OBSERVE_ASSERT with the exact environment host in `host`, the command in `cmd`, and signed checks in `asserts`; do not encode the execution object itself as F.' if e == 'test_env' or f == 'test_env' else ''
        return (None, None, _err(i, 'STEP', f'E={e!r}, F={f!r} is not a valid method: the pair is absent from the Excel function contract.{client_hint}'))
    if entry['status'] != 'enabled':
        return (None, None, _err(i, 'STEP', f"E={e!r}, F={f!r} is {entry['status']}: {entry['reason']}"))
    try:
        validate_g_for_entry(entry, g, contract)
    except ExcelContractError as exc:
        return (None, None, _err(i, 'STEP', f'invalid G syntax for E={e!r}, F={f!r}: {exc}'))
    parsed_ref = _dispatch_source(e, f_cmp, g, ref)
    if parsed_ref['kind'] == 'emit_auto':
        return (None, None, _err(i, 'STEP', f'ref is required and must be a recognized provenance pointer (one of {_REF_KINDS}, written as kind:location); only a validated test_env dispatch derives its source mechanically. If this step is a client observation with an assertion, replace the raw STEP pair with one OBSERVE_ASSERT block instead of inventing a provenance locator'))
    if parsed_ref['kind'] in _REF_LOCATOR_REQUIRED and (not str(parsed_ref.get('ref') or '').strip()):
        return (None, None, _err(i, 'STEP', f"ref kind {parsed_ref['kind']!r} requires a non-empty source locator"))
    if e == 'time':
        try:
            seconds = int(g)
        except ValueError:
            return (None, None, _err(i, 'STEP', 'time.sleep G must be an integer number of seconds'))
        if seconds <= 0 or seconds > 300:
            return (None, None, _err(i, 'STEP', f'time.sleep G must be within 1..300; got {seconds}'))
    h = str(b.get('H') or '').strip()
    i_col = str(b.get('I') or '').strip()
    identifier_fields = [('H', h)]
    if not (e == 'check_point' and f == 'found_times'):
        identifier_fields.append(('I', i_col.split('.', 1)[0] if i_col else ''))
    for field_name, value in identifier_fields:
        if value and (not _REGISTER_NAME_RE.match(value)):
            return (None, None, _err(i, 'STEP', f'{field_name} register reference {value!r} is not a safe identifier'))
    if e == 'check_point':
        if f == 'found_times':
            try:
                parse_found_times_cells(g, h, i_col)
            except ValueError as exc:
                return (None, None, _err(i, 'STEP', str(exc)))
            check_refs = ()
        else:
            check_refs = (h, i_col)
        for ref_name in check_refs:
            if ref_name and ref_name.split('.', 1)[0] not in defined_registers:
                return (None, None, _err(i, 'STEP', f'{ref_name!r} must be captured by an earlier STEP before check_point use'))
    else:
        if i_col:
            base = i_col.split('.', 1)[0]
            object_names = {str(item['e']) for item in contract['objects']}
            if base not in defined_registers and base not in object_names:
                return (None, None, _err(i, 'STEP', f'I={i_col!r} must reference an earlier STEP capture or framework object'))
        try:
            validate_i_injection_syntax(g, i_col, f_cmp)
        except (ExcelContractError, IInjectionSyntaxError) as exc:
            return (None, None, _err(i, 'STEP', str(exc)))
        if h:
            if capture_registers and h in capture_registers:
                return (None, None, _err(i, 'STEP', f'H={h!r} names a register already captured by an earlier CAPTURE combinator — a raw STEP writing there overwrites that baseline while later EXPECT_FROM still reads it. Pick a different H, or drop the CAPTURE if this step is the capture you meant.'))
            defined_registers.add(h)
    step = {'E': e, 'F': f_cmp, 'G': g, 'desc': str(b.get('desc') or '')}
    exempt = b.get('exempt')
    reason_code = str(b.get('reason_code') or '').strip()
    if e != 'check_point' and (exempt is not None or reason_code):
        return (None, None, _err(i, 'STEP', 'exempt/reason_code are valid only on check_point steps'))
    if e != 'check_point':
        id_error = _reject_block_level_assertion_ids(i, 'STEP', b)
        if id_error:
            return (None, None, id_error)
    assertion_ids, id_error = _assertion_identity(b)
    if id_error:
        return (None, None, _err(i, 'STEP', id_error))
    if e == 'check_point':
        if exempt not in (None, False, True):
            return (None, None, _err(i, 'STEP', 'exempt must be a boolean when present'))
        if exempt is not True and reason_code:
            return (None, None, _err(i, 'STEP', 'reason_code is valid only when exempt=true'))
        if exempt is True:
            step['exempt'] = True
            step['reason_code'] = reason_code
    if h:
        step['H'] = h
    if i_col:
        step['I'] = i_col
    layer = 'V' if e == 'check_point' else 'E' if e == 'time' else 'G'
    if parsed_ref['kind'] == 'config_derived':
        binding_input = b.get('binding_input')
        if not isinstance(binding_input, dict):
            return (None, None, _err(i, 'STEP', 'config_derived requires binding_input with an independently recomputable rule_id and source_input'))
        if set(binding_input) != {'rule_id', 'source_input'}:
            return (None, None, _err(i, 'STEP', 'binding_input requires exactly rule_id/source_input'))
        source_input = binding_input.get('source_input')
        if not isinstance(source_input, dict):
            return (None, None, _err(i, 'STEP', 'binding_input.source_input must be an object'))
        parsed_ref, binding_error = _derived_binding_source(source_kind='config_derived', recipe_id=str(parsed_ref.get('ref') or ''), rule_id=str(binding_input.get('rule_id') or ''), source_input=source_input, output_step=step)
        if parsed_ref is None:
            return (None, None, _err(i, 'STEP', binding_error))
    step_provenance = {'layer': layer, 'source': parsed_ref}
    if e == 'check_point' and isinstance(b.get('assertion_type'), dict):
        step_provenance['assertion_type'] = copy.deepcopy(b['assertion_type'])
    if e == 'check_point':
        step_provenance.update(assertion_ids)
    return (step, step_provenance, None)

def _validate_expanded_contract_steps(steps: list[dict]) -> str | None:
    from cex_core.engine.case_compiler.excel_contract import ExcelContractError, contract_entry, enabled_fs_by_e, load_excel_contract, validate_g_for_entry
    try:
        contract = load_excel_contract()
    except ExcelContractError as exc:
        return f'Excel function contract is unavailable: {exc}'
    enabled_by_e = enabled_fs_by_e(contract)
    for index, step in enumerate(steps):
        e = str(step.get('E') or '').strip()
        f = str(step.get('F') or '').strip()
        if f in {'dist', 'member'}:
            continue
        f_cmp = f.lower() if e == 'test_env' else f
        entry = contract_entry(e, f_cmp, contract)
        if entry is None:
            enabled = sorted(enabled_by_e.get(e, ()))
            choices = ', '.join((repr(value) for value in enabled)) or '(none)'
            return f'expanded step[{index}] E={e!r}, F={f!r} is absent from the Excel function contract; enabled F values for E={e!r}: {choices}'
        if entry['status'] != 'enabled':
            return f"expanded step[{index}] E={e!r}, F={f!r} is {entry['status']}: {entry['reason']}"
        if e == 'check_point' and f_cmp == 'found_times':
            try:
                validate_g_for_entry(entry, str(step.get('G') or ''), contract)
                parse_found_times_cells(step.get('G'), step.get('H'), step.get('I'))
            except (ExcelContractError, ValueError) as exc:
                return f'expanded step[{index}] has invalid found_times A-I syntax: {exc}'
        else:
            try:
                validate_g_for_entry(entry, str(step.get('G') or ''), contract)
            except ExcelContractError as exc:
                return f'expanded step[{index}] has invalid G syntax: {exc}'
    return None

def _bind_expanded_block(*, block_index: int, kind: str, block: dict, steps: list[dict], provenance: list[dict], occurrences: dict[str, int], available_observation_refs: set[str]) -> str | None:
    if len(steps) != len(provenance):
        return _err(block_index, kind, 'expanded provenance is not step-aligned')
    observations: list[str] = []
    for offset, (step, prov) in enumerate(zip(steps, provenance)):
        e = str(step.get('E') or '').strip()
        f = str(step.get('F') or '').strip()
        if e in {'', 'check_point', 'time'} or not f:
            continue
        declared_step_observation = bool(kind == 'STEP' and str(block.get('observation_id') or '').strip())
        if not declared_step_observation and kind not in {'OBSERVE_ASSERT', 'OBSERVE_EXIT', 'CAPTURE_COMPARE', 'OBSERVE_ONLY', 'OBSERVE_DIST', 'OBSERVE_MEMBER', 'CAPTURE', 'EXPECT_FROM'}:
            continue
        material = json.dumps({'E': e, 'F': f, 'G': str(step.get('G') or ''), 'H': str(step.get('H') or ''), 'I': str(step.get('I') or '')}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        digest = hashlib.sha256(material).hexdigest()[:24]
        occurrence = occurrences.get(digest, 0)
        occurrences[digest] = occurrence + 1
        declared_id = str(block.get('observation_id') or '').strip() if kind == 'STEP' else ''
        observation_id = declared_id or f'obs_{digest}_{occurrence}'
        result_channel = (str(block.get('result_channel') or '').strip() if kind == 'STEP' else '') or f'result_{observation_id}'
        prov.pop('observation_ref', None)
        prov['observation_id'] = observation_id
        prov['result_channel'] = result_channel
        available_observation_refs.update({observation_id, result_channel})
        observations.append(observation_id)
    assertions = [(step, prov) for step, prov in zip(steps, provenance) if str(step.get('E') or '').strip() == 'check_point']
    if not assertions:
        return None
    explicit_ref = str(block.get('observation_ref') or '').strip()
    if kind == 'STEP' and (not explicit_ref):
        return _err(block_index, kind, 'check_point STEP requires observation_ref naming an earlier explicit observation_id/result_channel; row adjacency is not a binding')
    if explicit_ref and explicit_ref not in available_observation_refs:
        return _err(block_index, kind, f'observation_ref {explicit_ref!r} does not name an earlier explicit observation_id/result_channel in this blocks array')
    if kind != 'STEP' and (not observations):
        return _err(block_index, kind, 'assertion-producing combinator has no structural observation producer')
    reference = explicit_ref or observations[-1]
    for _step, prov in assertions:
        prov.pop('observation_id', None)
        prov.pop('result_channel', None)
        prov['observation_ref'] = reference
    return None

def expand_blocks(blocks: list, provenance_steps: list | None=None) -> tuple[list[dict] | None, list[dict] | None, str | None]:
    if not isinstance(blocks, list) or not blocks:
        return (None, None, 'blocks must be a non-empty array')
    if provenance_steps is not None and len(provenance_steps) != len(blocks):
        return (None, None, f"provenance steps count ({len(provenance_steps)}) must equal blocks count ({len(blocks)}) — annotate at **combinator granularity**, not expanded rows: with {len(blocks)} combinators, provenance.steps holds {len(blocks)} entries (each {{layer, source}} maps to one combinator; row expansion is the tool's job).")
    steps: list[dict] = []
    prov_out: list[dict] = []
    reg_n = 0
    defined_registers: set[str] = set()
    capture_registers: set[str] = set()
    observation_occurrences: dict[str, int] = {}
    available_observation_refs: set[str] = set()
    deferred_ssl_steps: list[tuple[list[dict], list[dict]]] = []
    assertion_slots: list[tuple[str, int]] = []
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            return (None, None, _err(i, '?', 'each combinator must be an object'))
        kind = str(b.get('kind', '')).strip().upper()
        desc = str(b.get('desc', '') or '')
        if 'timeout_s' in b and kind not in {'CONFIG', 'STEP'}:
            return (None, None, _err(i, kind, 'timeout_s is supported only by CONFIG or APV cmd_config STEP'))
        nested_id_error = _nested_assertion_id_error(i, kind or '?', b)
        if nested_id_error:
            return (None, None, nested_id_error)
        assertion_ids: dict[str, str] = {}
        if kind in _NO_ASSERTION_ID_KINDS:
            block_id_error = _reject_block_level_assertion_ids(i, kind, b)
            if block_id_error:
                return (None, None, block_id_error)
        elif kind in _ASSERTION_ID_BLOCK_KINDS:
            assertion_ids, block_id_error = _assertion_identity(b)
            if block_id_error:
                return (None, None, _err(i, kind, block_id_error))
        pv = provenance_steps[i] if provenance_steps is not None else None
        explicit_id_error = _reject_explicit_provenance_assertion_ids(i, kind or '?', pv)
        if explicit_id_error:
            return (None, None, explicit_id_error)
        produced = 0
        block_step_start = len(steps)
        block_prov_start = len(prov_out)
        block_auto: list[dict] = []
        if kind == 'SSL_CERT_LOAD':
            if provenance_steps is not None:
                return (None, None, _err(i, kind, "SSL_CERT_LOAD mints engine-owned per-step provenance while it lowers to CONFIG/STEP blocks; omit the explicit provenance_steps entry and use the block's projected fields"))
            from cex_core.engine.ist_core.tools.device.emit_xlsx_tool import split_ssl_certificate_load_blocks
            setup_blocks, cleanup_blocks, lower_error = split_ssl_certificate_load_blocks(b)
            if lower_error or setup_blocks is None or cleanup_blocks is None:
                return (None, None, _err(i, kind, lower_error))
            lowered_steps, lowered_prov, nested_error = expand_blocks(setup_blocks)
            if nested_error or lowered_steps is None or lowered_prov is None:
                return (None, None, _err(i, kind, nested_error or 'standard-library lowering returned no steps'))
            steps.extend(lowered_steps)
            produced = len(lowered_steps)
            block_auto.extend(lowered_prov)
            for step in lowered_steps:
                register = str(step.get('H') or '').strip()
                if register:
                    defined_registers.add(register)
            cleanup_steps, cleanup_prov, cleanup_error = expand_blocks(cleanup_blocks)
            if cleanup_error or cleanup_steps is None or cleanup_prov is None:
                return (None, None, _err(i, kind, cleanup_error or 'standard-library teardown returned no steps'))
            deferred_ssl_steps.append((cleanup_steps, cleanup_prov))
        elif kind == 'STEP':
            step, step_prov, step_err = _expand_generic_step(i, b, defined_registers, capture_registers)
            if step_err:
                return (None, None, step_err)
            steps.append(step)
            produced = 1
            block_auto.append(step_prov)
        elif kind == 'CONFIG':
            timeout_error = _command_timeout_error(i, kind, b)
            if timeout_error:
                return (None, None, timeout_error)
            cmds = b.get('cmds')
            if not isinstance(cmds, list) or not cmds or (not all((isinstance(c, str) for c in cmds))):
                return (None, None, _err(i, kind, 'cmds must be a non-empty list of command strings (one command per element)'))
            _short = [c for c in cmds if len(c.strip()) <= 2]
            if len(cmds) > 2 and len(_short) > len(cmds) // 2:
                return (None, None, _err(i, kind, f'cmds looks character-split ({len(_short)}/{len(cmds)} elements ≤2 chars) — each array element must be **one whole command**, not single characters. Pass the whole command as one string element.'))
            cmds = [c.strip() for c in cmds if c.strip()]
            if not cmds:
                return (None, None, _err(i, kind, 'cmds are all empty — provide real commands (one per element)'))
            _dut = str(b.get('host') or 'APV_0').strip()
            if _dut not in _DUT_HOSTS:
                return (None, None, _err(i, kind, f'CONFIG.host must be one of {_DUT_HOSTS} (the device under test); got {_dut!r}'))
            if 'timeout_s' in b:
                for cmd in cmds:
                    timeout_error = _timeout_command_error(i, kind, cmd)
                    if timeout_error:
                        return (None, None, timeout_error)
                    steps.append({'E': _dut, 'F': 'cmd_config', 'G': f"{cmd},timeout={b['timeout_s']}", 'desc': desc})
                    block_auto.append({'layer': 'G', 'source': _parse_ref(b.get('ref'))})
                produced = len(cmds)
            elif len(cmds) == 1:
                steps.append({'E': _dut, 'F': 'cmd_config', 'G': cmds[0], 'desc': desc})
            else:
                steps.append({'E': _dut, 'F': 'cmds_config', 'G': '\n'.join(cmds), 'desc': desc})
            if 'timeout_s' not in b:
                produced = 1
                block_auto.append({'layer': 'G', 'source': _parse_ref(b.get('ref'))})
        elif kind == 'OBSERVE_EXIT':
            cmd = str(b.get('cmd', '') or '').strip()
            host = str(b.get('host', '') or '').strip()
            expect = str(b.get('expect', '') or '').strip().lower()
            if not cmd or not host:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            if host in _DUT_HOSTS:
                from cex_core.engine.case_compiler.apv_lang import observe_exit_channel_error
                return (None, None, _err(i, kind, observe_exit_channel_error(host)))
            answerer_error = _answerer_shape_error(i, kind, b)
            if answerer_error:
                return (None, None, answerer_error)
            masking_error = _exit_status_masking_error(cmd)
            if masking_error:
                return (None, None, _err(i, kind, masking_error))
            if expect not in _EXIT_STATUS_EXPECTS:
                return (None, None, _err(i, kind, f'expect must be one of {_EXIT_STATUS_EXPECTS}; got {expect!r}'))
            from cex_core.engine.case_compiler.provenance_ir import exit_status_assertion
            probe = _probe_tool_name(cmd) if expect == 'failure' else ''
            probe_codes: tuple[int, ...] = ()
            if expect == 'failure':
                if '&&' in cmd:
                    return (None, None, _err(i, kind, 'expect=failure requires a single probe command; an && conjunction cannot name one transport-failure class'))
                from cex_core.engine.case_compiler.domain_grammar import probe_tool_transport_failure_codes
                table = probe_tool_transport_failure_codes()
                if probe not in table:
                    return (None, None, _err(i, kind, f"expect=failure asserts a transport-level failure of the probe tool, so the probe must be a tool whose transport-failure exit codes are documented in the grammar probe_tools table (registered: {', '.join(sorted(table))}); got {probe or '<none>'!r}. A bare non-zero exit code is not accepted: it also matches client-side errors and misses answered refusals."))
                probe_codes = table[probe]
            assertion_step, status_error = exit_status_assertion(expect, probe=probe, codes=probe_codes)
            if assertion_step is None:
                return (None, None, _err(i, kind, status_error))
            assertion_step['desc'] = desc
            steps.append(_observe_step(host, _exit_status_command(cmd), desc))
            steps.append(assertion_step)
            produced = 2
            status_recipe = 'status.exit:' + hashlib.sha256(json.dumps({'host': host.lower(), 'cmd': cmd, 'expect': expect}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:24]
            status_source, status_error = _derived_binding_source(source_kind='status_derived', recipe_id=status_recipe, rule_id='status.exit-code', source_input={'expect': expect, 'probe': probe, 'codes': list(probe_codes)} if expect == 'failure' else {'expect': expect}, output_step=assertion_step)
            if status_source is None:
                return (None, None, _err(i, kind, status_error))
            status_provenance = {'layer': 'V', 'source': status_source, **assertion_ids}
            if isinstance(b.get('assertion_type'), dict):
                status_provenance['assertion_type'] = copy.deepcopy(b['assertion_type'])
            block_auto.extend([{'layer': 'G', 'source': _dispatch_source(steps[-2]['E'], steps[-2]['F'], steps[-2]['G'], b.get('cmd_ref'))}, status_provenance])
        elif kind == 'OBSERVE_ASSERT':
            cmd = str(b.get('cmd', '') or '').strip()
            host = str(b.get('host', '') or '').strip()
            asserts = b.get('asserts')
            if not cmd or not host:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            if not isinstance(asserts, list) or not asserts:
                return (None, None, _err(i, kind, 'asserts must be a non-empty assertion list; use OBSERVE_ONLY for observation without assertions'))
            answerer_error = _answerer_shape_error(i, kind, b)
            if answerer_error:
                return (None, None, answerer_error)
            steps.append(_observe_step(host, cmd, desc))
            produced = 1
            block_auto.append({'layer': 'G', 'source': _dispatch_source(steps[-1]['E'], steps[-1]['F'], steps[-1]['G'], b.get('cmd_ref') or b.get('ref'))})
            for j, a in enumerate(asserts):
                if not isinstance(a, dict):
                    return (None, None, _err(i, kind, f'asserts[{j}] must be an object'))
                op = str(a.get('op', '') or '').strip()
                pattern = a.get('pattern')
                if op not in _ASSERT_OPS:
                    return (None, None, _err(i, kind, f'asserts[{j}].op must be one of {_ASSERT_OPS}; got {op!r}'))
                if not isinstance(pattern, str) or not pattern.strip():
                    return (None, None, _err(i, kind, f'asserts[{j}].pattern must be non-empty text/regex'))
                assertion_step = {'E': 'check_point', 'F': op, 'G': pattern, 'desc': str(a.get('desc', '') or '')}
                exempt = a.get('exempt')
                reason_code = str(a.get('reason_code') or '').strip()
                if exempt not in (None, False, True):
                    return (None, None, _err(i, kind, f'asserts[{j}].exempt must be a boolean when present'))
                if exempt is not True and reason_code:
                    return (None, None, _err(i, kind, f'asserts[{j}].reason_code is valid only when exempt=true'))
                if exempt is True:
                    assertion_step['exempt'] = True
                    assertion_step['reason_code'] = reason_code
                spec_gap = a.get('spec_gap')
                if spec_gap is not None and (not (isinstance(spec_gap, str) and spec_gap.strip())):
                    return (None, None, _err(i, kind, f'asserts[{j}].spec_gap, when present, must be one line naming what the governing spec does not state'))
                steps.append(assertion_step)
                produced += 1
                assertion_source = _parse_ref(a.get('ref'))
                if assertion_source['kind'] == 'config_derived':
                    binding_input = a.get('binding_input')
                    if not isinstance(binding_input, dict):
                        return (None, None, _err(i, kind, f'asserts[{j}] config_derived requires binding_input with an independently recomputable rule_id and source_input'))
                    if set(binding_input) != {'rule_id', 'source_input'}:
                        return (None, None, _err(i, kind, f'asserts[{j}].binding_input requires exactly rule_id/source_input'))
                    source_input = binding_input.get('source_input')
                    if not isinstance(source_input, dict):
                        return (None, None, _err(i, kind, f'asserts[{j}].binding_input.source_input must be an object'))
                    assertion_source, binding_error = _derived_binding_source(source_kind='config_derived', recipe_id=str(assertion_source.get('ref') or ''), rule_id=str(binding_input.get('rule_id') or ''), source_input=source_input, output_step=assertion_step)
                    if assertion_source is None:
                        return (None, None, _err(i, kind, f'asserts[{j}].binding_input is invalid: {binding_error}'))
                elif 'binding_input' in a:
                    return (None, None, _err(i, kind, f'asserts[{j}].binding_input is valid only when ref uses config_derived'))
                assert_ids, assert_id_error = _assertion_identity(a)
                if assert_id_error:
                    return (None, None, _err(i, kind, f'asserts[{j}].{assert_id_error}'))
                assertion_provenance = {'layer': 'V', 'source': assertion_source}
                if isinstance(a.get('assertion_type'), dict):
                    assertion_provenance['assertion_type'] = copy.deepcopy(a['assertion_type'])
                assertion_provenance.update(assert_ids)
                if isinstance(spec_gap, str) and spec_gap.strip():
                    assertion_provenance['spec_gap'] = spec_gap.strip()
                block_auto.append(assertion_provenance)
        elif kind == 'CAPTURE_COMPARE':
            host = str(b.get('host', '') or '').strip()
            cap = str(b.get('capture_cmd', '') or '').strip()
            cmd = str(b.get('cmd', '') or '').strip() or cap
            relation = str(b.get('relation', '') or '').strip().lower()
            if not host or not cap:
                return (None, None, _err(i, kind, 'host and capture_cmd are required'))
            if relation not in ('same', 'differs'):
                return (None, None, _err(i, kind, f'relation must be same (two observations equal) or differs (two observations differ); got {relation!r}'))
            while True:
                reg_n += 1
                reg = f'v{reg_n}'
                if reg not in defined_registers:
                    break
            defined_registers.add(reg)
            capture_registers.add(reg)
            steps.append(_observe_step(host, cap, desc + '(第一次观测,捕获基线)', save_as=reg))
            steps.append(_observe_step(host, cmd, desc + '(第二次观测,产生被比较输出)'))
            op = 'found' if relation == 'same' else 'not_found'
            steps.append({'E': 'check_point', 'F': op, 'G': '', 'H': reg, 'desc': desc + ('(两次相同)' if relation == 'same' else '(两次不同)')})
            produced = 3
            _src = _dispatch_source(steps[-3]['E'], steps[-3]['F'], steps[-3]['G'], b.get('ref'))
            relation_source, relation_error = _derived_binding_source(source_kind='captured_relation', recipe_id='', rule_id='capture.static-relation', source_input={'relation': relation}, output_step=steps[-1])
            if relation_source is None:
                return (None, None, _err(i, kind, relation_error))
            relation_provenance = {'layer': 'V', 'source': relation_source}
            if isinstance(b.get('assertion_type'), dict):
                relation_provenance['assertion_type'] = copy.deepcopy(b['assertion_type'])
            relation_provenance.update(assertion_ids)
            block_auto.extend([{'layer': 'G', 'source': dict(_src)}, {'layer': 'G', 'source': dict(_src)}, relation_provenance])
        elif kind == 'OBSERVE_ONLY':
            cmd = str(b.get('cmd', '') or '').strip()
            host = str(b.get('host', '') or '').strip()
            if not cmd or not host:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            steps.append(_observe_step(host, cmd, desc))
            produced = 1
            block_auto.append({'layer': 'G', 'source': _dispatch_source(steps[-1]['E'], steps[-1]['F'], steps[-1]['G'], b.get('cmd_ref') or b.get('ref'))})
        elif kind == 'OBSERVE_DIST':
            cmd = str(b.get('cmd', '') or '').strip()
            host = str(b.get('host', '') or '').strip()
            total = b.get('total')
            field = b.get('field')
            buckets = b.get('buckets')
            if not cmd or not host:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            if total is None:
                return (None, None, _err(i, kind, 'total (total request count for the distribution check) is required'))
            if not isinstance(buckets, list) or not buckets:
                return (None, None, _err(i, kind, 'buckets must be a non-empty list of {anchor, expected, tol?, pattern?}'))
            if field is None:
                return (None, None, _err(i, kind, 'field (a same-line count-field regex prefix, not a complete pattern) is required; use an empty string when every bucket supplies its own complete pattern containing {range}'))
            binding_error = distribution_count_binding_error(field, buckets)
            if binding_error:
                return (None, None, _err(i, kind, binding_error))
            steps.append(_observe_step(host, cmd, desc))
            steps.append({'E': 'check_point', 'F': 'dist', 'dist': {'total': total, 'field': str(field or ''), 'buckets': buckets}, 'desc': desc})
            if b.get('exempt') is True:
                steps[-1]['exempt'] = True
                steps[-1]['reason_code'] = str(b.get('reason_code') or '').strip()
            produced = 2
            block_auto.append({'layer': 'G', 'source': _dispatch_source(steps[-2]['E'], steps[-2]['F'], steps[-2]['G'], b.get('cmd_ref') or b.get('ref'))})
            parsed_dist_ref = _parse_ref(b.get('ref'))
            dist_provenance = {'layer': 'V', 'source': {'kind': 'distribution_derived', 'ref': str(parsed_dist_ref.get('ref') or '')}}
            if isinstance(b.get('assertion_type'), dict):
                dist_provenance['assertion_type'] = copy.deepcopy(b['assertion_type'])
            dist_provenance.update(assertion_ids)
            block_auto.append(dist_provenance)
        elif kind == 'OBSERVE_MEMBER':
            cmd = str(b.get('cmd', '') or '').strip()
            host = str(b.get('host', '') or '').strip()
            ips = b.get('ips')
            present = b.get('present')
            if not cmd or not host:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            if not isinstance(ips, list) or not ips:
                return (None, None, _err(i, kind, 'ips must be a non-empty list of member IP strings'))
            if present is None:
                return (None, None, _err(i, kind, 'present is required (true=expect output within ips, false=expect output NOT within ips)'))
            steps.append(_observe_step(host, cmd, desc))
            steps.append({'E': 'check_point', 'F': 'member', 'member': {'ips': ips, 'present': present}, 'desc': desc})
            produced = 2
            block_auto.append({'layer': 'G', 'source': _dispatch_source(steps[-2]['E'], steps[-2]['F'], steps[-2]['G'], b.get('cmd_ref') or b.get('ref'))})
            parsed_member_ref = _parse_ref(b.get('ref'))
            member_provenance = {'layer': 'V', 'source': {'kind': 'membership_derived', 'ref': str(parsed_member_ref.get('ref') or '')}}
            if isinstance(b.get('assertion_type'), dict):
                member_provenance['assertion_type'] = copy.deepcopy(b['assertion_type'])
            member_provenance.update(assertion_ids)
            block_auto.append(member_provenance)
        elif kind == 'CAPTURE':
            host = str(b.get('host', '') or '').strip()
            cmd = str(b.get('cmd', '') or '').strip()
            save_as = str(b.get('save_as', '') or '').strip()
            if not host or not cmd:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            if not save_as or not _REGISTER_NAME_RE.match(save_as):
                return (None, None, _err(i, kind, f'save_as must be a non-empty identifier (letters/digits/underscore, not starting with a digit) naming the register this capture is stored under; got {save_as!r}'))
            if _AUTO_REGISTER_RE.match(save_as):
                return (None, None, _err(i, kind, f'save_as {save_as!r} looks like the internal v<N> pattern CAPTURE_COMPARE auto-allocates — pick a descriptive name instead to avoid colliding with it in the shared runtime register namespace.'))
            if save_as in capture_registers:
                return (None, None, _err(i, kind, f'save_as {save_as!r} was already captured earlier in this same blocks array — pick a distinct name, or drop this duplicate CAPTURE.'))
            capture_registers.add(save_as)
            defined_registers.add(save_as)
            steps.append(_observe_step(host, cmd, desc, save_as=save_as))
            produced = 1
            block_auto.append({'layer': 'G', 'source': _dispatch_source(steps[-1]['E'], steps[-1]['F'], steps[-1]['G'], b.get('ref'))})
        elif kind == 'EXPECT_FROM':
            host = str(b.get('host', '') or '').strip()
            cmd = str(b.get('cmd', '') or '').strip()
            expected_from = str(b.get('expected_from', '') or '').strip()
            op = str(b.get('op', '') or '').strip()
            if not host or not cmd:
                return (None, None, _err(i, kind, 'host and cmd are required'))
            if op not in _ASSERT_OPS:
                return (None, None, _err(i, kind, f'op must be one of {_ASSERT_OPS}; got {op!r}'))
            if not expected_from:
                return (None, None, _err(i, kind, 'expected_from (the register name captured earlier by a CAPTURE combinator) is required'))
            if expected_from not in capture_registers:
                return (None, None, _err(i, kind, f'expected_from {expected_from!r} has not been captured by any earlier CAPTURE combinator in this blocks array — capture it first (add a CAPTURE block with save_as={expected_from!r} before this one), or fix the register name.'))
            steps.append(_observe_step(host, cmd, desc))
            steps.append({'E': 'check_point', 'F': op, 'G': '', 'H': expected_from, 'desc': desc})
            produced = 2
            block_auto.append({'layer': 'G', 'source': _dispatch_source(steps[-2]['E'], steps[-2]['F'], steps[-2]['G'], b.get('cmd_ref') or b.get('ref'))})
            expected_source, expected_error = _derived_binding_source(source_kind='captured_relation', recipe_id='', rule_id='capture.static-reference', source_input={'operator': op, 'register': expected_from}, output_step=steps[-1])
            if expected_source is None:
                return (None, None, _err(i, kind, expected_error))
            expected_provenance = {'layer': 'V', 'source': expected_source}
            if isinstance(b.get('assertion_type'), dict):
                expected_provenance['assertion_type'] = copy.deepcopy(b['assertion_type'])
            expected_provenance.update(assertion_ids)
            block_auto.append(expected_provenance)
        elif kind == 'SLEEP':
            try:
                sec = int(b.get('seconds'))
            except (TypeError, ValueError):
                return (None, None, _err(i, kind, 'seconds must be an integer'))
            if sec <= 0 or sec > 300:
                return (None, None, _err(i, kind, f'seconds must be within 1..300; got {sec}'))
            steps.append({'E': 'time', 'F': 'sleep', 'G': str(sec), 'desc': desc})
            produced = 1
            block_auto.append({'layer': 'E', 'source': {'kind': 'emit_auto', 'ref': ''}})
        else:
            _keys = list(b.keys())
            return (None, None, _err(i, kind or 'missing-kind', f"each combinator needs a kind field: one of CONFIG/OBSERVE_ASSERT/OBSERVE_EXIT/CAPTURE_COMPARE/OBSERVE_ONLY/OBSERVE_DIST/OBSERVE_MEMBER/CAPTURE/EXPECT_FROM/SLEEP/SSL_CERT_LOAD/STEP. This combinator's keys={_keys}" + (' — you probably omitted kind, or used an alias.' if 'kind' not in b else f"; kind value {b.get('kind')!r} is not in the allowed set.")))
        if provenance_steps is not None:
            base = pv if isinstance(pv, dict) else {}
            for offset in range(produced):
                entry = dict(base)
                auto = block_auto[offset] if offset < len(block_auto) else {}
                target = steps[block_step_start + offset]
                if str(target.get('E') or '').strip() == 'check_point':
                    for name in _ASSERTION_ID_FIELDS:
                        if name in auto:
                            entry[name] = auto[name]
                prov_out.append(entry)
        else:
            while len(block_auto) < produced:
                block_auto.append({'layer': 'G', 'source': {'kind': 'emit_auto', 'ref': ''}})
            prov_out.extend(block_auto[:produced])
        for offset in range(produced):
            if str(steps[block_step_start + offset].get('E') or '').strip() == 'check_point':
                assertion_slots.append((_assertion_slot_label(kind, i, offset), block_prov_start + offset))
        binding_error = _bind_expanded_block(block_index=i, kind=kind, block=b, steps=steps[block_step_start:], provenance=prov_out[block_prov_start:], occurrences=observation_occurrences, available_observation_refs=available_observation_refs)
        if binding_error:
            return (None, None, binding_error)
    if deferred_ssl_steps:
        cleanup_steps_all: list[dict] = []
        cleanup_prov_all: list[dict] = []
        for cleanup_steps, cleanup_prov in reversed(deferred_ssl_steps):
            cleanup_steps_all.extend(cleanup_steps)
            cleanup_prov_all.extend(cleanup_prov)
        assertion_positions = [index for index, step in enumerate(steps) if str(step.get('E') or '').strip() == 'check_point']
        insertion = max(assertion_positions) + 1 if assertion_positions else len(steps)
        steps[insertion:insertion] = cleanup_steps_all
        prov_out[insertion:insertion] = cleanup_prov_all
    coverage_error = _assertion_identity_coverage_error(prov_out, assertion_slots)
    if coverage_error:
        return (None, None, coverage_error)
    contract_error = _validate_expanded_contract_steps(steps)
    if contract_error:
        return (None, None, contract_error)
    return (steps, prov_out, None)

def capture_register_final_operator(operator: Any, register: Any) -> str:
    op = str(operator or '').strip()
    if op == 'found' and str(register or '').strip():
        return 'abs_found'
    return op

def lower_derived_assertions(steps: list[dict], provenance_steps: list[dict] | None) -> tuple[list[dict] | None, list[dict] | None, str | None]:
    from cex_core.engine.case_compiler.distribution_assertion import expand_distribution_steps, expand_provenance_steps_with_plan
    from cex_core.engine.case_compiler.membership_assertion import attach_membership_derivation_receipts, expand_membership_steps
    distribution_source_steps = steps
    expanded, plan, error = expand_distribution_steps(steps)
    if error or expanded is None or plan is None:
        return (None, None, 'distribution-interval assertion declaration is invalid: ' + str(error or 'expansion returned no steps'))
    try:
        expanded_provenance = expand_provenance_steps_with_plan(provenance_steps, plan, source_steps=distribution_source_steps, expanded_steps=expanded)
    except ValueError as exc:
        return (None, None, 'ConfigBinding distribution receipt could not be recomputed: ' + str(exc))
    membership_source_steps = expanded
    expanded, error = expand_membership_steps(expanded)
    if error or expanded is None:
        return (None, None, 'hit-membership assertion declaration is invalid: ' + str(error or 'expansion returned no steps'))
    try:
        expanded_provenance = attach_membership_derivation_receipts(expanded_provenance, membership_source_steps, expanded)
    except ValueError as exc:
        return (None, None, 'ConfigBinding membership receipt could not be recomputed: ' + str(exc))
    final_steps = []
    for step in expanded:
        if str((step or {}).get('E') or '').strip() == 'check_point':
            final_operator = capture_register_final_operator(step.get('F'), step.get('H'))
            if final_operator != str(step.get('F') or '').strip():
                step = {**step, 'F': final_operator}
        final_steps.append(step)
    return (final_steps, expanded_provenance, None)
