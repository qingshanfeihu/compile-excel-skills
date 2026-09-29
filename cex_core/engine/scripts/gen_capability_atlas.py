# 生成：tools/extract_engine.py ← InfoTest scripts/gen_capability_atlas.py（sha256 fadfa8bfe9c93f1f）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import argparse
import copy
import hashlib
import json
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Iterable
_ROOT = _cex_data_path('')
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from cex_core.engine.case_compiler.credential_literals import MirrorCredentialLiteralError, matching_credential_literal_count, mirror_credential_literals, mirror_credential_literals_with_overlays
from cex_core.engine.case_compiler.apv_lang import mirror_src, LIFECYCLE_FS, APV_CMD_PRIMITIVE_FS, SEG_CMD_PRIMITIVE_FS, CMD_PRIMITIVE_FS, valid_es, valid_fs_by_e, execute_action_registry, execute_action_registry_by_dispatch, host_slot_es, norm_action
from cex_core.engine.case_compiler.excel_contract import SCHEMA as EXCEL_CONTRACT_SCHEMA
from cex_core.engine.case_compiler.excel_contract import contract_sha256, validate_excel_contract
from cex_core.engine.case_compiler.excel_capability_receipts import ValidatedReceiptSet, load_receipt_directory, passed_receipt_groups
from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow
from cex_core.engine.case_compiler.framework_projection_identity import FRAMEWORK_PROJECTION_SOURCE_PATHS, FrameworkProjectionIdentityError, build_framework_source_identity
from cex_core.engine.scripts.compile_ref_windowed import WindowedProjectionError, build_method_reference_window, render_json, write_method_reference_window
_ATLAS_OUT = _ROOT / 'knowledge/data/compile_ref/capability_atlas.json'
_METHOD_REF_OUT = _ROOT / 'knowledge/data/compile_ref/method_reference.json'
_EXCEL_CONTRACT_OUT = _ROOT / 'knowledge/data/compile_ref/excel_contract.json'
_MIRROR_ROOT = _ROOT / 'knowledge/framework/mirror'
_RUNTIME_ROOT = _ROOT / 'runtime'
_CERTIFICATION_ROOT = _RUNTIME_ROOT / 'excel_capability_receipts'
from cex_core.engine.common.schema_identity import accepts_schema
_EXCEL_RUNTIME = 'ist.excel.runtime'
_CONTRACT_SOURCE_PATHS = FRAMEWORK_PROJECTION_SOURCE_PATHS
_APV_WRITABLE = APV_CMD_PRIMITIVE_FS
_SEG_WRITABLE = SEG_CMD_PRIMITIVE_FS
_APV_INTERNAL = frozenset({'__init__', 'xlsx_begin', 'reset_time', 'ssh_connect', 'ttys_connect', 'tel_connect', 'ccypher_connect', 'console_login', 'read_until', 'clear_buff', 'clear', 'cmd_tmp', 'global_init', 'clear_seg_name', 'reboot', 'upgrade', 'config_ip', 'close', 'soft_close', 'hard_close', 'console_close'})
_SEG_INTERNAL = frozenset({'__init__', 'read_until', 'xlsx_begin', 'reset_time', 'soft_close', 'close', 'clear'})
_DIC_INTERNAL = frozenset({'__init__', 'check_direct_match', 'get_same', 'get_similar_function', 'load_synonyms'})
_SSH_SERVER_INTERNAL = frozenset({'__init__', 'xlsx_begin', 'read_until', 'delete_route', 'delete_ip', 'close', 'soft_close', 'get_similar_function'})
_CHECKPOINT_ENABLED = frozenset({'found', 'abs_found', 'not_found', 'found_times'})
_HTTP_ENABLED = frozenset({'add_page', 'add_header'})
_HTTP_INTERNAL = frozenset({'__init__', 'start', 'stop'})
_MIXIN_STUB_METHODS = frozenset({'__init__', 'cmd_config'})
_STATUS_AUTHORITY_POLICY = 'project_policy:excel-authoring-v1'
_STATUS_AUTHORITY_MIRROR = 'mirror_ast:reachability-and-lifecycle'
_STATUS_AUTHORITY_RUNTIME = 'mirror_ast:active-runtime-call-chain'
_STATUS_AUTHORITY_ACTION = 'mirror_ast:pure-execute-action-v1'
_STATUS_AUTHORITY_BED = 'bed_topology:network_topology.json'
_TOPOLOGY_PATH = _ROOT / 'knowledge/data/auto_env/network_topology.json'
_FUNC_DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)

def _ast_class_methods(rel: str, cls: str) -> frozenset[str]:
    src = mirror_src(rel)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return frozenset()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            return frozenset((n.name for n in node.body if isinstance(n, _FUNC_DEF_TYPES)))
    return frozenset()

def _ast_class_bases(rel: str, cls: str) -> list[str]:
    src = mirror_src(rel)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            return [b.id for b in node.bases if isinstance(b, ast.Name)]
    return []

def _ast_env_trigger_hosts(rel: str='lib/env.py', cls: str='Env') -> list[str]:
    src = mirror_src(rel)
    tree = ast.parse(src)
    hosts: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == cls):
            continue
        for item in node.body:
            if not isinstance(item, _FUNC_DEF_TYPES):
                continue
            opens_session = any((isinstance(child, ast.Call) and (isinstance(child.func, ast.Name) and child.func.id == 'ssh_server' or (isinstance(child.func, ast.Attribute) and child.func.attr == 'ssh_server')) for child in ast.walk(item)))
            if opens_session:
                hosts.append(item.name)
    if not hosts:
        raise ValueError(f'mirror {rel} 的 {cls} 类里解析不出任何 ssh_server 主机槽方法——server_trigger_hosts.hosts 是解析产物,不得回落到手抄清单')
    return hosts

def _server_trigger_hosts() -> dict:
    return {'hosts': _ast_env_trigger_hosts(), **_CURATED['server_trigger_hosts']}

def _curated_sections() -> dict:
    sections = {**_CURATED, 'server_trigger_hosts': _server_trigger_hosts()}
    for section, fields in _CURATED_GENERATED_FIELDS.items():
        built = sections.get(section) or {}
        missing = [f for f in fields if f not in built]
        if missing:
            raise ValueError(f'_CURATED_GENERATED_FIELDS 声明 {section}.{missing} 为生成字段,但构建期没填上——声明与实现漂移了')
        stale = [f for f in fields if f in (_CURATED.get(section) or {})]
        if stale:
            raise ValueError(f'{section}.{stale} 同时在 _CURATED 字面量与生成路上——手抄值会影子化解析产物,字面量里必须删掉它')
    return sections

def _ast_signature(rel: str, cls: str, method: str) -> dict | None:
    src = mirror_src(rel)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == cls):
            continue
        for n in node.body:
            if isinstance(n, _FUNC_DEF_TYPES) and n.name == method:
                args = n.args
                if args.vararg or args.kwarg:
                    return None
                names = [a.arg for a in args.args if a.arg != 'self']
                n_defaults = len(args.defaults)
                if n_defaults:
                    required, optional = (names[:-n_defaults], names[-n_defaults:])
                else:
                    required, optional = (names, [])
                return {'required': required, 'optional': optional}
    return None

def _ast_dict_str_keys(rel: str, dict_name: str) -> frozenset[str]:
    src = mirror_src(rel)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return frozenset()
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        matched = any((isinstance(t, ast.Name) and t.id == dict_name or (isinstance(t, ast.Attribute) and t.attr == dict_name) for t in node.targets))
        if not matched:
            continue
        for k in node.value.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value)
    return frozenset(keys)

def _ast_action_mapping(rel: str) -> dict[str, str]:
    src = mirror_src(rel)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) and any((isinstance(target, ast.Attribute) and target.attr == 'command_function_mapping' for target in node.targets))):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and (value.value.id == 'self')):
                continue
            mapping[key.value] = value.attr
    return mapping

def _ast_action_payload_schema(rel: str, cls: str, method: str) -> dict:
    src = mirror_src(rel)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {'required': None, 'separator': '：', 'min_length': None, 'status': 'unclassified'}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == cls):
            continue
        for item in node.body:
            if not (isinstance(item, _FUNC_DEF_TYPES) and item.name == method):
                continue
            args = [arg.arg for arg in item.args.args if arg.arg != 'self']
            if not args:
                return {'required': False, 'separator': '：', 'min_length': 0, 'status': 'classified', 'cell_mode': 'unsplit_single_argument', 'argument_count': 0, 'split_delimiters': [], 'regex_patterns': []}
            input_name = args[0]
            reads_input = any((isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and (child.id == input_name) for child in ast.walk(item)))
            return {'required': reads_input, 'separator': '：', 'min_length': 1 if reads_input else 0, 'status': 'classified', **_action_payload_syntax_facts(item, argument_count=len(args))}
    return {'required': None, 'separator': '：', 'min_length': None, 'status': 'unclassified', 'cell_mode': 'unknown', 'argument_count': None, 'split_delimiters': [], 'regex_patterns': []}

def _action_payload_syntax_facts(node: ast.FunctionDef | ast.AsyncFunctionDef, *, argument_count: int) -> dict[str, Any]:
    delimiters: set[str] = set()
    patterns: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and (child.func.attr == 'split') and child.args and isinstance(child.args[0], ast.Constant) and isinstance(child.args[0].value, str):
            delimiters.add(child.args[0].value)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name) and (child.func.value.id == 're') and (child.func.attr in {'compile', 'search', 'match', 'findall', 'finditer'}) and child.args and isinstance(child.args[0], ast.Constant) and isinstance(child.args[0].value, str):
            patterns.add(child.args[0].value)
    return {'cell_mode': 'unsplit_single_argument', 'argument_count': argument_count, 'split_delimiters': sorted(delimiters), 'regex_patterns': sorted(patterns)}

def _name_sets(node: ast.AST, context: type[ast.expr_context]) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, context)}

def _conditional_unbound_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    known = {arg.arg for arg in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)}
    failures: set[str] = set()
    statements = list(node.body)
    for index, statement in enumerate(statements):
        if isinstance(statement, ast.If):
            body_stores = set().union(*(_name_sets(item, ast.Store) for item in statement.body), set())
            else_stores = set().union(*(_name_sets(item, ast.Store) for item in statement.orelse), set())
            definitely_assigned = body_stores & else_stores if statement.orelse else set()
            later_loads = set().union(*(_name_sets(item, ast.Load) for item in statements[index + 1:]), set())
            failures.update((body_stores | else_stores) - definitely_assigned - known & later_loads)
            known.update(definitely_assigned)
        else:
            known.update(_name_sets(statement, ast.Store))
    return failures

def _action_runtime_status(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str, str]:
    if any((isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and (child.id == 'self') for child in ast.walk(node))):
        return ('disabled', 'action reaches device/object state through self and has no same-SHA safety receipt', _STATUS_AUTHORITY_ACTION)
    if any((isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and (child.func.attr == 'group') and isinstance(child.func.value, ast.Call) and isinstance(child.func.value.func, ast.Attribute) and isinstance(child.func.value.func.value, ast.Name) and (child.func.value.func.value.id == 're') and (child.func.value.func.attr in {'search', 'match'}) for child in ast.walk(node))):
        return ('disabled', 'action dereferences an unguarded regex match', _STATUS_AUTHORITY_ACTION)
    unbound = sorted(_conditional_unbound_names(node))
    if unbound:
        return ('disabled', f"action can read conditionally unassigned locals: {', '.join(unbound)}", _STATUS_AUTHORITY_ACTION)
    return ('enabled', 'AST-local pure transform with no self/device/network call and closed input paths', _STATUS_AUTHORITY_ACTION)

def _synonym_aliases(rel: str) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for line in mirror_src(rel).splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '：' not in line:
            continue
        canonical, values = line.split('：', 1)
        aliases[canonical.strip()] = [value.strip() for value in values.split('，') if value.strip()]
    return aliases

def _mixin_family(rel: str, cls: str, dispatch_kind: str) -> dict:
    all_names = _ast_class_methods(rel, cls) - _MIXIN_STUB_METHODS - LIFECYCLE_FS
    methods: dict[str, dict] = {}
    unclassified: list[dict] = []
    for name in sorted(all_names):
        sig = _ast_signature(rel, cls, name)
        if sig is None:
            unclassified.append({'name': name, 'reason': 'signature uses *args/**kwargs — required/optional split not applicable'})
            continue
        methods[name] = {**sig, 'dispatch_kind': dispatch_kind, 'source': rel}
    return {'methods': methods, 'unclassified': unclassified}

def _execute_actions() -> dict:
    domains = ({'dispatcher': 'apv', 'rel': 'lib/apv/apv_action.py', 'cls': 'action', 'synonyms': 'lib/apv/apv_synonyms', 'allowed_es': ['APV_0', 'APV_1', 'APV_2']}, {'dispatcher': 'client', 'rel': 'lib/client_action.py', 'cls': 'client_action', 'synonyms': 'lib/client_synonyms', 'allowed_es': sorted(host_slot_es())})
    capabilities: dict[str, dict] = {}
    registry: dict[str, dict] = {}
    raw_counts: dict[str, int] = {}
    for domain in domains:
        try:
            domain_tree = ast.parse(mirror_src(domain['rel']), filename=domain['rel'])
        except SyntaxError as exc:
            raise ValueError(f"execute action source is not parseable: {domain['rel']}") from exc
        method_nodes = {item.name: item for class_node in ast.walk(domain_tree) if isinstance(class_node, ast.ClassDef) and class_node.name == domain['cls'] for item in class_node.body if isinstance(item, _FUNC_DEF_TYPES)}
        mapping = _ast_action_mapping(domain['rel'])
        aliases = _synonym_aliases(domain['synonyms'])
        aliases_by_norm = {norm_action(canonical): values for canonical, values in aliases.items()}
        raw_counts[f"{domain['dispatcher']}_action_mapping_raw"] = len(mapping)
        for canonical, function in mapping.items():
            method_node = method_nodes.get(function)
            if method_node is None:
                raise ValueError(f"execute action mapping points to missing method: {domain['rel']}:{function}")
            payload_schema = _ast_action_payload_schema(domain['rel'], domain['cls'], function)
            status, reason, status_authority = _action_runtime_status(method_node)
            variants = [(canonical, 'mapping')]
            variants.extend(((alias, 'synonym') for alias in aliases_by_norm.get(norm_action(canonical), [])))
            for original, origin_kind in variants:
                normalized = norm_action(original)
                key = f"{domain['dispatcher']}:{normalized}"
                if key in capabilities:
                    prior = capabilities[key]
                    if prior.get('canonical') == canonical and prior.get('source_function') == function:
                        aliases_out = prior.setdefault('equivalent_originals', [])
                        if original not in aliases_out:
                            aliases_out.append(original)
                        continue
                    raise ValueError(f'ambiguous execute capability key: {key}')
                info = {'original': original, 'canonical': canonical, 'dispatcher': domain['dispatcher'], 'allowed_es': list(domain['allowed_es']), 'origin': f"{domain['dispatcher']}_action_{origin_kind}", 'source': domain['rel'], 'source_function': function, 'payload_schema': payload_schema, 'status': status, 'reason': reason, 'status_authority': status_authority}
                capabilities[key] = info
                previous = registry.get(normalized)
                if previous and previous.get('dispatcher') != domain['dispatcher']:
                    registry[normalized] = {'original': previous['original'], 'origin': 'ambiguous_cross_dispatcher', 'dispatcher': 'ambiguous', 'dispatchers': sorted({previous['dispatcher'], domain['dispatcher']})}
                else:
                    registry[normalized] = {'original': original, 'origin': info['origin'], 'dispatcher': domain['dispatcher']}
    return {'registry': registry, 'capabilities': capabilities, 'counts': {**raw_counts, 'total_normalized': len(registry), 'total_normalized_legacy_names': len(registry), 'total_dispatch_capabilities': len(capabilities)}, 'note': 'F=execute 的 G 动作名必须是本集精确成员(全角冒号前段);非精确会落 fuzzy≥0.8 静默派发、可语义反转(内部工单 规则在 emit 期拒非精确名)。覆盖律与规则使用 capabilities 的 dispatcher/E/payload schema；registry 只为旧查询面保留。'}

def _contract_source_bytes(rel: str, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> bytes:
    source = (source_overlays or {}).get(rel)
    if source is not None:
        if isinstance(source, (bytes, bytearray)):
            return bytes(source)
        raise ValueError(f'contract source overlay must be sealed bytes: {rel}')
    try:
        return (_MIRROR_ROOT / rel).read_bytes()
    except OSError as exc:
        raise ValueError(f'contract source unavailable: {rel}') from exc

def _contract_source_text(rel: str, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> str:
    try:
        return _contract_source_bytes(rel, source_overlays).decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError(f'contract source is not UTF-8: {rel}') from exc

def _parse_contract_tree(rel: str, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> ast.Module:
    try:
        return ast.parse(_contract_source_text(rel, source_overlays), filename=rel)
    except SyntaxError as exc:
        raise ValueError(f'contract source parse failed: {rel}') from exc

def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None

def _contract_class_index(source_overlays: Mapping[str, bytes | bytearray] | None=None) -> dict[str, dict[str, Any]]:
    paths = ('lib/apv/apv.py', 'lib/apv/apv_ssh.py', 'lib/apv/ssl_comm.py', 'lib/apv/seg_comm.py', 'lib/apv/ha_comm.py', 'lib/apv/preparation.py', 'lib/apv/apv_action.py', 'lib/dic_operation.py', 'lib/client_action.py', 'lib/env.py', 'lib/check_point.py', 'lib/ssh_server.py', 'smoke_test/conftest.py')
    found: dict[str, list[dict[str, Any]]] = {}
    for rel in paths:
        tree = _parse_contract_tree(rel, source_overlays)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            found.setdefault(node.name, []).append({'name': node.name, 'path': rel, 'line': node.lineno, 'bases': [name for base in node.bases if (name := _base_name(base))], 'node': node})
    required = {'APV', 'APV_SSH', 'ssl_comm', 'seg_comm', 'ha_comm', 'action', 'preparation', 'dic_operation', 'client_action', 'Env', 'Check_Point', 'ssh_server', 'http_server'}
    index: dict[str, dict[str, Any]] = {}
    for name in sorted(required):
        matches = found.get(name, [])
        if len(matches) != 1:
            raise ValueError(f'contract class {name!r} must resolve exactly once, found {len(matches)}')
        index[name] = matches[0]
    return index

def _c3_mro(name: str, index: Mapping[str, Mapping[str, Any]], memo: dict[str, list[str]] | None=None) -> list[str]:
    memo = memo if memo is not None else {}
    if name in memo:
        return list(memo[name])
    if name not in index:
        raise ValueError(f'contract MRO base is unclassified: {name!r}')
    bases = [base for base in index[name]['bases'] if base != 'object']
    for base in bases:
        if base not in index:
            raise ValueError(f'contract MRO base is unavailable: {name}->{base}')
    sequences = [_c3_mro(base, index, memo) for base in bases] + [list(bases)]
    result = [name]
    while any(sequences):
        sequences = [sequence for sequence in sequences if sequence]
        candidate = next((sequence[0] for sequence in sequences if not any((sequence[0] in other[1:] for other in sequences))), None)
        if candidate is None:
            raise ValueError(f'contract MRO is inconsistent for {name!r}')
        result.append(candidate)
        for sequence in sequences:
            if sequence and sequence[0] == candidate:
                sequence.pop(0)
    memo[name] = list(result)
    return result

def _render_parameter_default(name: str, default: ast.expr | None) -> str | None:
    if default is None:
        return None
    if re.search('pass(?:word|wd)?|secret|token|credential', name, re.I):
        return '<redacted>'
    try:
        return ast.unparse(default)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f'cannot serialize default for parameter {name!r}') from exc

def _signature_from_node(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    default_start = len(positional) - len(args.defaults)
    parameters: list[dict[str, Any]] = []
    defaults_by_index = {index: default for index, default in zip(range(default_start, len(positional)), args.defaults)}
    for index, parameter in enumerate(positional):
        if index == 0 and parameter.arg in {'self', 'cls'}:
            continue
        kind = 'positional_only' if index < len(args.posonlyargs) else 'positional_or_keyword'
        required = index < default_start
        parameters.append({'name': parameter.arg, 'kind': kind, 'required': required, 'default': _render_parameter_default(parameter.arg, defaults_by_index.get(index))})
    if args.vararg is not None:
        parameters.append({'name': args.vararg.arg, 'kind': 'var_positional', 'required': False, 'default': None})
    for parameter, default in zip(args.kwonlyargs, args.kw_defaults):
        parameters.append({'name': parameter.arg, 'kind': 'keyword_only', 'required': default is None, 'default': _render_parameter_default(parameter.arg, default)})
    if args.kwarg is not None:
        parameters.append({'name': args.kwarg.arg, 'kind': 'var_keyword', 'required': False, 'default': None})
    rendered = []
    for parameter in parameters:
        prefix = '*' if parameter['kind'] == 'var_positional' else '**' if parameter['kind'] == 'var_keyword' else ''
        suffix = '' if parameter['required'] else '' if parameter['kind'] in {'var_positional', 'var_keyword'} else f"={parameter['default']}"
        rendered.append(f"{prefix}{parameter['name']}{suffix}")
    required = [p['name'] for p in parameters if p['required']]
    optional = [p['name'] for p in parameters if not p['required']]
    return {'parameters': parameters, 'required': required, 'optional': optional, 'text': f"({', '.join(rendered)})"}

def _effective_methods(root_class: str, index: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    mro = _c3_mro(root_class, index)
    methods: dict[str, dict[str, Any]] = {}
    for owner in mro:
        class_info = index[owner]
        for node in class_info['node'].body:
            if not isinstance(node, _FUNC_DEF_TYPES):
                continue
            if node.name in methods:
                continue
            methods[node.name] = {'owner': owner, 'path': class_info['path'], 'line': node.lineno, 'node': node, 'signature': _signature_from_node(node)}
    return (mro, methods)

def _runner_contract_facts(tree: ast.Module) -> tuple[list[str], bool]:
    devices: list[str] | None = None
    version: str | None = None
    checkpoint_fn: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    active_test_fn: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'devices' and isinstance(node.value, ast.Dict):
                    keys = [key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)]
                    if len(keys) != len(node.value.keys):
                        raise ValueError('runner devices contains a non-literal key')
                    devices = keys
                if isinstance(target, ast.Name) and target.id == 'EXCEL_FUNCTION_CONTRACT_VERSION' and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    version = node.value.value
        if isinstance(node, _FUNC_DEF_TYPES) and node.name == '_invoke_checkpoint':
            checkpoint_fn = node
        if isinstance(node, _FUNC_DEF_TYPES) and node.name == 'test_xlsx':
            active_test_fn = node
    if devices is None or len(set(devices)) != len(devices):
        raise ValueError('runner devices closure is unavailable or duplicated')
    found_times_branch = False
    if checkpoint_fn is not None:
        for node in ast.walk(checkpoint_fn):
            if not isinstance(node, ast.If):
                continue
            compares_found_times = any((isinstance(child, ast.Compare) and any((isinstance(comparator, ast.Constant) and comparator.value == 'found_times' for comparator in child.comparators)) for child in ast.walk(node.test)))
            has_three_arg_call = any((isinstance(child, ast.Call) and len(child.args) == 3 for statement in node.body for child in ast.walk(statement)))
            if compares_found_times and has_three_arg_call:
                found_times_branch = True
                break
    active_dispatch = bool(active_test_fn is not None and any((isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and (child.func.id == '_invoke_checkpoint') for child in ast.walk(active_test_fn))))
    return (devices, accepts_schema(version or '', _EXCEL_RUNTIME) and found_times_branch and active_dispatch)

def _classification(root: str, owner: str, name: str, found_times_supported: bool) -> tuple[str, str, str]:
    if owner == 'APV':
        if name in _APV_WRITABLE:
            return ('enabled', 'APV writable transport primitive', _STATUS_AUTHORITY_POLICY)
        if name in _APV_INTERNAL:
            if name in {'reboot', 'upgrade'}:
                return ('disabled', 'device-wide lifecycle helper is unsafe in an Excel step', _STATUS_AUTHORITY_POLICY)
            return ('internal', 'framework connection or lifecycle helper', _STATUS_AUTHORITY_MIRROR)
        raise ValueError(f'unclassified APV method: {name}')
    if owner == 'APV_SSH':
        if name in _SEG_WRITABLE:
            return ('enabled', 'segment-compatible writable transport primitive', _STATUS_AUTHORITY_POLICY)
        if name in _SEG_INTERNAL:
            return ('internal', 'framework connection or lifecycle helper', _STATUS_AUTHORITY_MIRROR)
        raise ValueError(f'unclassified APV_SSH method: {name}')
    if owner == 'seg_comm':
        if name in {'__init__', 'cmd_config'}:
            return ('internal', 'mixin interface stub', _STATUS_AUTHORITY_MIRROR)
        return ('disabled', 'seg_comm semantics are not certified for Excel authoring', _STATUS_AUTHORITY_POLICY)
    if owner in {'ssl_comm', 'ha_comm'}:
        if name in {'__init__', 'cmd_config'}:
            return ('internal', 'mixin interface stub', _STATUS_AUTHORITY_MIRROR)
        return ('disabled', f'direct method from {owner} retains its legacy signature but requires same-source device certification before Excel authoring', _STATUS_AUTHORITY_POLICY)
    if owner == 'preparation':
        if name == '__init__':
            return ('internal', 'framework initializer', _STATUS_AUTHORITY_MIRROR)
        return ('disabled', 'preparation depends on attributes not initialized by APV/APV_SSH', _STATUS_AUTHORITY_POLICY)
    if owner in {'action', 'client_action'}:
        if name == '__init__' or re.fullmatch('func_\\d+', name):
            return ('internal', 'execute-registry implementation helper', _STATUS_AUTHORITY_MIRROR)
        raise ValueError(f'unclassified {owner} method: {name}')
    if owner == 'dic_operation':
        if name == 'execute':
            return ('enabled', 'execute registry dispatcher', _STATUS_AUTHORITY_MIRROR)
        if name in _DIC_INTERNAL:
            return ('internal', 'execute registry matching helper', _STATUS_AUTHORITY_MIRROR)
        raise ValueError(f'unclassified dic_operation method: {name}')
    if owner == 'Env':
        if name in {'__init__', 'close', 'xlsx_begin'}:
            return ('internal', 'environment lifecycle helper', _STATUS_AUTHORITY_MIRROR)
        return ('enabled', 'environment host command method', _STATUS_AUTHORITY_POLICY)
    if owner == 'Check_Point':
        if name in {'__init__', 'close', 'xlsx_begin'}:
            return ('internal', 'assertion lifecycle helper', _STATUS_AUTHORITY_MIRROR)
        if name not in _CHECKPOINT_ENABLED:
            raise ValueError(f'unclassified Check_Point method: {name}')
        if name == 'found_times' and (not found_times_supported):
            return ('disabled', 'runner lacks the v2 three-argument found_times dispatch', _STATUS_AUTHORITY_RUNTIME)
        return ('enabled', 'Excel check-point assertion', _STATUS_AUTHORITY_RUNTIME)
    if owner == 'ssh_server':
        if name in {'cmd', 'execute'}:
            return ('enabled', 'host-slot command method', _STATUS_AUTHORITY_POLICY)
        if name in _SSH_SERVER_INTERNAL:
            return ('internal', 'host-slot lifecycle or matching helper', _STATUS_AUTHORITY_MIRROR)
        raise ValueError(f'unclassified ssh_server method: {name}')
    if owner == 'http_server':
        if name in _HTTP_ENABLED:
            return ('disabled', 'nested HTTP fixture mutates a remote helper and requires same-source device certification before Excel authoring', _STATUS_AUTHORITY_POLICY)
        if name in _HTTP_INTERNAL:
            return ('internal', 'nested HTTP fixture lifecycle helper', _STATUS_AUTHORITY_MIRROR)
        raise ValueError(f'unclassified http_server method: {name}')
    raise ValueError(f'unclassified contract method owner: {root}/{owner}.{name}')

def _entry_semantics(e: str, f: str, signature: Mapping[str, Any]) -> dict[str, str]:
    if e == 'check_point':
        if f == 'found_times':
            return {'g_syntax': 'required static expected regex (Author/Manual/ConfigBinding)', 'h_semantics': 'must be blank; runtime captures cannot become expected values', 'i_semantics': 'required positive integer occurrence count; actual value is the previous result', 'dispatch': 'checkpoint_v2_three_argument'}
        return {'g_syntax': 'literal expected value when H is blank', 'h_semantics': 'optional expected-value register override', 'i_semantics': 'optional actual-value register; blank uses the previous result', 'dispatch': 'checkpoint_two_argument'}
    if f == 'execute':
        g_syntax = 'one unsplit cell: <exact action name>：<optional payload>'
        dispatch = 'execute_registry'
    elif f == 'cmds_config':
        g_syntax = 'one unsplit cell containing newline-separated commands'
        dispatch = 'cmd_primitive'
    elif f == 'cmd_config':
        g_syntax = 'one single-line command cell; multiline input is rejected'
        dispatch = 'cmd_primitive'
    elif f in CMD_PRIMITIVE_FS - {'cmd_config', 'cmds_config'}:
        g_syntax = 'comma-separated positional/keyword arguments with balanced quoting'
        dispatch = 'cmd_primitive'
    elif e == 'time' and f == 'sleep':
        g_syntax = 'one numeric seconds argument'
        dispatch = 'builtin_special_case'
    else:
        g_syntax = f"balanced-quote comma-separated positional/keyword arguments; empty cell means zero arguments; signature {signature.get('text', '')}"
        dispatch = 'direct_method_call'
    return {'g_syntax': g_syntax, 'h_semantics': 'optional output register receiving the function return value', 'i_semantics': "optional input register formatted into G's first positional argument via {} or {0}", 'dispatch': dispatch}

def _parse_action_mapping_from_tree(tree: ast.Module, cls: str) -> tuple[dict[str, str], dict[str, int]]:
    mapping: dict[str, str] = {}
    lines: dict[str, int] = {}
    for class_node in ast.walk(tree):
        if not isinstance(class_node, ast.ClassDef) or class_node.name != cls:
            continue
        method_lines = {node.name: node.lineno for node in class_node.body if isinstance(node, _FUNC_DEF_TYPES)}
        for node in ast.walk(class_node):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            if not any((isinstance(target, ast.Attribute) and target.attr == 'command_function_mapping' for target in node.targets)):
                continue
            for key, value in zip(node.value.keys, node.value.values):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and (value.value.id == 'self')):
                    raise ValueError(f'unclassified {cls} execute mapping entry')
                mapping[key.value] = value.attr
                lines[value.attr] = method_lines[value.attr]
    if not mapping:
        raise ValueError(f'empty {cls} execute action registry')
    return (mapping, lines)

def _contract_synonyms(rel: str, source_overlays: Mapping[str, bytes | bytearray] | None) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for raw in _contract_source_text(rel, source_overlays).splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '：' not in line:
            raise ValueError(f'unclassified synonym line in {rel}')
        canonical, values = line.split('：', 1)
        aliases[canonical.strip()] = [value.strip() for value in values.split('，') if value.strip()]
    return aliases

def _contract_action_payload_schema(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    positional = list(node.args.posonlyargs) + list(node.args.args)
    names = [parameter.arg for parameter in positional if parameter.arg not in {'self', 'cls'}]
    if not names:
        return {'required': False, 'separator': '：', 'min_length': 0, 'status': 'classified', 'cell_mode': 'unsplit_single_argument', 'argument_count': 0, 'split_delimiters': [], 'regex_patterns': []}
    input_name = names[0]
    reads_input = any((isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and (child.id == input_name) for child in ast.walk(node)))
    return {'required': reads_input, 'separator': '：', 'min_length': 1 if reads_input else 0, 'status': 'classified', **_action_payload_syntax_facts(node, argument_count=len(names))}

def _build_contract_actions(device_es: set[str], index: Mapping[str, Mapping[str, Any]], source_overlays: Mapping[str, bytes | bytearray] | None) -> list[dict]:
    domains = (('apv', 'lib/apv/apv_action.py', 'action', 'lib/apv/apv_synonyms', 'action'), ('client', 'lib/client_action.py', 'client_action', 'lib/client_synonyms', 'client_action'))
    result_by_key: dict[tuple[str, str], dict] = {}
    for dispatcher, rel, cls, synonyms_rel, mro_class in domains:
        mapping, lines = _parse_action_mapping_from_tree(_parse_contract_tree(rel, source_overlays), cls)
        synonyms = {norm_action(canonical): aliases for canonical, aliases in _contract_synonyms(synonyms_rel, source_overlays).items()}
        allowed_es = sorted((e for e in device_es if mro_class in _c3_mro('APV' if e.startswith('APV_') else 'APV_SSH' if re.fullmatch('Seg\\d+_tmp', e) else 'ssh_server' if e in {'routera', 'server213', 'server231', 'server232'} else 'Env' if e == 'test_env' else 'http_server' if e == 'http_server_231' else 'Check_Point', index)))
        for canonical, function in sorted(mapping.items()):
            variants = [(canonical, 'canonical')] + [(alias, 'synonym') for alias in synonyms.get(norm_action(canonical), [])]
            for name, origin in variants:
                normalized = norm_action(name)
                key = (dispatcher, normalized)
                prior = result_by_key.get(key)
                if prior is not None:
                    if prior['canonical'] != canonical or prior['python_symbol'] != f'{cls}.{function}':
                        raise ValueError(f'ambiguous execute action contract key: {key}')
                    if name not in prior['equivalent_originals']:
                        prior['equivalent_originals'].append(name)
                    continue
                method_node = next((node for node in index[cls]['node'].body if isinstance(node, _FUNC_DEF_TYPES) and node.name == function))
                status, reason, status_authority = _action_runtime_status(method_node)
                payload_schema = _contract_action_payload_schema(method_node)
                result_by_key[key] = {'name': name, 'normalized': normalized, 'canonical': canonical, 'equivalent_originals': [name], 'origin': origin, 'dispatcher': dispatcher, 'allowed_es': allowed_es, 'python_symbol': f'{cls}.{function}', 'signature': _signature_from_node(method_node), 'payload_schema': payload_schema, 'g_syntax': '<exact action name>：<required payload>' if payload_schema['required'] else '<exact action name> with an optional ：payload suffix', 'h_semantics': 'optional output register receiving the action return value', 'i_semantics': 'optional input register formatted into the unsplit G cell via {} or {0}', 'minimum_runtime': _EXCEL_RUNTIME, 'source': {'path': rel, 'line': lines[function]}, 'status': status, 'reason': reason, 'status_authority': status_authority}
    return sorted(result_by_key.values(), key=lambda item: (item['dispatcher'], item['normalized'], item['name']))

def _validate_excel_contract_alignment(atlas: Mapping[str, Any], e_values: list[str], entries: list[dict], actions: list[dict]) -> None:
    atlas_objects = atlas.get('objects')
    atlas_methods = atlas.get('methods')
    atlas_execute = atlas.get('execute_actions')
    if not isinstance(atlas_objects, dict) or not isinstance(atlas_methods, dict):
        raise ValueError('capability atlas object/method closure is unavailable')
    if set(atlas_objects) != set(e_values):
        raise ValueError('capability atlas object closure does not match the runner')
    if not isinstance(atlas_execute, dict) or not isinstance(atlas_execute.get('capabilities'), dict) or (not atlas_execute['capabilities']):
        raise ValueError('capability atlas execute closure is unavailable')
    live_es = set(valid_es())
    live_fs = {e: set(values) for e, values in valid_fs_by_e().items()}
    if live_es != set(e_values) or set(live_fs) != set(e_values):
        raise ValueError('apv_lang E/F closure is incomplete or differs from the runner')
    declared_by_e: dict[str, dict[str, str]] = {e: {} for e in e_values}
    for entry in entries:
        declared_by_e[entry['e']][entry['f']] = entry['status']
    for e in e_values:
        public = {f for f, status in declared_by_e[e].items() if status != 'internal'}
        enabled = {f for f, status in declared_by_e[e].items() if status == 'enabled'}
        if not live_fs[e] <= public or not enabled <= live_fs[e]:
            raise ValueError(f'apv_lang E/F closure disagrees with contract for {e!r}')
    apv_families = atlas_methods.get('apv_full')
    if not isinstance(apv_families, dict) or set(apv_families) != {'ssl_comm', 'seg_comm', 'ha_comm', 'preparation'}:
        raise ValueError('capability atlas APV family closure is incomplete')
    apv_entries = [entry for entry in entries if entry['e'] == 'APV_0']
    for family, payload in apv_families.items():
        methods = payload.get('methods') if isinstance(payload, dict) else None
        if not isinstance(methods, dict) or not methods:
            raise ValueError(f'capability atlas family {family!r} is empty')
        for name, info in methods.items():
            matches = [entry for entry in apv_entries if entry['f'] == name and entry['python_symbol'] == f'{family}.{name}']
            if len(matches) != 1:
                raise ValueError(f'capability atlas method {family}.{name} has no unique contract entry')
            entry = matches[0]
            if bool(info.get('disabled')) != (entry['status'] == 'disabled'):
                raise ValueError(f'capability atlas status disagrees for {family}.{name}')
            signature = entry['signature']
            if list(info.get('required') or []) != list(signature.get('required') or []) or list(info.get('optional') or []) != list(signature.get('optional') or []):
                raise ValueError(f'capability atlas signature disagrees for {family}.{name}')
    atlas_capabilities = atlas_execute['capabilities']
    contract_keys = {f"{action['dispatcher']}:{action['normalized']}" for action in actions}
    if set(atlas_capabilities) != contract_keys:
        raise ValueError('capability atlas execute action closure disagrees with contract')
    independent_actions = execute_action_registry_by_dispatch()
    independent_keys = {f'{dispatcher}:{normalized}' for dispatcher, registry in independent_actions.items() for normalized in registry}
    if independent_keys != contract_keys:
        raise ValueError('apv_lang execute action closure disagrees with contract')
    for action in actions:
        key = f"{action['dispatcher']}:{action['normalized']}"
        atlas_action = atlas_capabilities[key]
        if atlas_action.get('source_function') != action['python_symbol'].split('.', 1)[1]:
            raise ValueError(f'execute action implementation disagrees for {key!r}')
        if set(action['allowed_es']) != set(atlas_action.get('allowed_es') or []):
            raise ValueError(f'execute action E closure disagrees for {key!r}')
        if atlas_action.get('status') != action['status'] or atlas_action.get('reason') != action['reason'] or atlas_action.get('status_authority') != action['status_authority']:
            raise ValueError(f'execute action status disagrees for {key!r}')

def build_excel_contract(atlas: Mapping[str, Any], *, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> dict:
    """有 overlay 时连 apv_lang 的闭集一起换源，否则对齐校验会判两边不同源。"""
    from cex_core.engine.case_compiler import apv_lang as _apv_lang
    with _apv_lang.source_overlay(source_overlays):
        return _build_excel_contract_inner(atlas, source_overlays=source_overlays)

def _build_excel_contract_inner(atlas: Mapping[str, Any], *, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> dict:
    overlays = dict(source_overlays or {})
    unknown_overlays = set(overlays) - set(_CONTRACT_SOURCE_PATHS)
    if unknown_overlays:
        raise ValueError(f'unknown contract source overlays: {sorted(unknown_overlays)}')
    source_hashes = {rel: hashlib.sha256(_contract_source_bytes(rel, overlays)).hexdigest() for rel in _CONTRACT_SOURCE_PATHS}
    runner_tree = _parse_contract_tree('lib/test_xlsx.py', overlays)
    runner_devices, found_times_supported = _runner_contract_facts(runner_tree)
    time_import_line = next((node.lineno for node in runner_tree.body if isinstance(node, ast.Import) and any((alias.name == 'time' for alias in node.names))), None)
    if time_import_line is None:
        raise ValueError('runner does not import the time module')
    e_values = list(runner_devices)
    for special in ('check_point', 'time'):
        if special not in e_values:
            e_values.append(special)
    if len(set(e_values)) != 14:
        raise ValueError(f'runner E closure must contain 14 unique values (12 runner devices + check_point + time), found {len(set(e_values))}: {e_values}; a count mismatch means the synced framework (apv_src on the jumphost) is older or newer than the contract this generator expects — update the framework on the target env, re-run framework_sync, then re-run gen_capability_atlas')
    index = _contract_class_index(overlays)
    root_by_e: dict[str, str] = {}
    for e in e_values:
        if e in {'APV_0', 'APV_1', 'APV_2'}:
            root_by_e[e] = 'APV'
        elif re.fullmatch('Seg\\d+_tmp', e):
            root_by_e[e] = 'APV_SSH'
        elif e == 'test_env':
            root_by_e[e] = 'Env'
        elif e == 'check_point':
            root_by_e[e] = 'Check_Point'
        elif e == 'time':
            root_by_e[e] = 'time'
        elif e in {'routera', 'server213', 'server231', 'server232'}:
            root_by_e[e] = 'ssh_server'
        elif e == 'http_server_231':
            root_by_e[e] = 'http_server'
        else:
            raise ValueError(f'runner E is unclassified: {e}')
    objects: list[dict] = []
    entries: list[dict] = []
    for e in sorted(e_values):
        root = root_by_e[e]
        if root == 'time':
            source = {'path': 'lib/test_xlsx.py', 'line': time_import_line}
            signature = {'parameters': [{'name': 'seconds', 'kind': 'positional_only', 'required': True, 'default': None}], 'required': ['seconds'], 'optional': [], 'text': '(seconds, /)'}
            objects.append({'e': e, 'python_type': 'time module', 'mro': ['time module'], 'status': 'enabled', 'reason': 'runner-imported Python module with one explicit Excel special-case', 'status_authority': _STATUS_AUTHORITY_RUNTIME, 'source': source})
            semantics = _entry_semantics(e, 'sleep', signature)
            entries.append({'e': e, 'f': 'sleep', 'python_symbol': 'time.sleep', 'signature': signature, **semantics, 'status': 'enabled', 'reason': 'runner explicitly converts the first argument to an integer', 'status_authority': _STATUS_AUTHORITY_RUNTIME, 'source': source, 'minimum_runtime': _EXCEL_RUNTIME})
            continue
        mro, methods = _effective_methods(root, index)
        class_info = index[root]
        segment_disabled = bool(re.fullmatch('Seg\\d+_tmp', e))
        objects.append({'e': e, 'python_type': root, 'mro': mro, 'status': 'disabled' if segment_disabled else 'enabled', 'reason': 'Seg fixture setup mutates the environment before row dispatch and its Excel semantics are not certified' if segment_disabled else 'runner-resolved object with a complete AST/MRO method closure', 'status_authority': _STATUS_AUTHORITY_POLICY if segment_disabled else _STATUS_AUTHORITY_MIRROR, 'source': {'path': class_info['path'], 'line': class_info['line']}})
        for f, method in sorted(methods.items()):
            status, reason, status_authority = _classification(root, method['owner'], f, found_times_supported)
            if segment_disabled:
                status = 'disabled'
                reason = 'Seg fixture semantics are disabled until setup and cleanup are certified side-effect safe'
                status_authority = _STATUS_AUTHORITY_POLICY
            semantics = _entry_semantics(e, f, method['signature'])
            entry_payload = {'e': e, 'f': f, 'python_symbol': f"{method['owner']}.{f}", 'signature': method['signature'], **semantics, 'status': status, 'reason': reason, 'status_authority': status_authority, 'source': {'path': method['path'], 'line': method['line']}, 'minimum_runtime': _EXCEL_RUNTIME}
            if not segment_disabled and status == 'disabled' and (method['owner'] in {'ssl_comm', 'ha_comm', 'http_server'}):
                entry_payload['certification_candidate'] = True
            entries.append(entry_payload)
    actions = _build_contract_actions({e for e in runner_devices if not re.fullmatch('Seg\\d+_tmp', e)}, index, overlays)
    bed_seats = _bed_apv_seats()
    for entry in entries:
        seat_index = _absent_bed_seat(entry['e'], bed_seats)
        if seat_index is not None and entry['status'] == 'enabled':
            entry['status'] = 'disabled'
            entry['reason'] = _absent_bed_seat_reason(seat_index)
            entry['status_authority'] = _STATUS_AUTHORITY_BED
    enabled_action_es = {e for action in actions if action['status'] == 'enabled' for e in action['allowed_es']}
    for entry in entries:
        if entry['dispatch'] == 'execute_registry' and entry['e'] not in enabled_action_es:
            entry['status'] = 'disabled'
            entry['reason'] = 'execute dispatcher has no enabled action implementation for this E'
            entry['status_authority'] = _STATUS_AUTHORITY_ACTION
    _validate_excel_contract_alignment(atlas, e_values, entries, actions)
    contract = {'schema': EXCEL_CONTRACT_SCHEMA, 'complete': True, 'runtime': {'minimum_version': _EXCEL_RUNTIME, 'runner_source': 'lib/test_xlsx.py', 'runner_sha256': source_hashes['lib/test_xlsx.py'], 'found_times_supported': found_times_supported}, 'source_hashes': source_hashes, 'objects': objects, 'entries': sorted(entries, key=lambda entry: (entry['e'], entry['f'])), 'execute_actions': actions, 'atlas_snapshot': {'object_count': len(atlas.get('objects') or {}), 'execute_capability_count': len((atlas.get('execute_actions') or {}).get('capabilities') or {})}}
    contract['contract_sha256'] = contract_sha256(contract)
    return contract

class BedTopologyUnavailableError(RuntimeError):
    """床拓扑读不到。取不到 ≠ 确认没有席位，不能折叠成空集。"""

def _bed_apv_seats() -> frozenset[str]:
    try:
        payload = json.loads(_TOPOLOGY_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise BedTopologyUnavailableError(f'床拓扑不可读（{_TOPOLOGY_PATH.name}）；它是生成物，先跑一次环境收敛') from exc
    seats: set[str] = set()
    for device in payload.get('devices', []) or []:
        if not isinstance(device, dict):
            continue
        name_match = re.fullmatch('APV(\\d+)', str(device.get('name') or ''))
        if name_match:
            seats.add(f'APV_{name_match.group(1)}')
    return frozenset(seats)

def _absent_bed_seat(e_value: str, bed_seats: frozenset[str]) -> str | None:
    seat_match = re.fullmatch('APV_(\\d+)', str(e_value))
    if seat_match is None or e_value in bed_seats:
        return None
    return seat_match.group(1)

def _absent_bed_seat_reason(seat_index: str) -> str:
    return 'bed topology declares no APV%s seat; the binding cannot be device-certified on this environment' % seat_index

def apply_capability_certifications(atlas: Mapping[str, Any], basis_contract: Mapping[str, Any], receipt_set: ValidatedReceiptSet, *, basis_contract_file_sha256: str, deployment_receipt_sha256: str) -> tuple[dict, dict]:
    if receipt_set.phase != 'certification':
        raise ValueError('execute certification requires certification receipts')
    promoted_atlas = copy.deepcopy(dict(atlas))
    contract = copy.deepcopy(dict(basis_contract))
    basis_sha = str(contract.get('contract_sha256') or '')
    if not re.fullmatch('[0-9a-f]{64}', basis_sha):
        raise ValueError('basis contract has no canonical identity')
    passed = passed_receipt_groups(receipt_set)
    atlas_capabilities = promoted_atlas['execute_actions']['capabilities']
    bed_seats = _bed_apv_seats()
    for entry in contract['entries']:
        if entry.get('certification_candidate') is not True:
            continue
        seat_index = _absent_bed_seat(entry['e'], bed_seats)
        if seat_index is None:
            continue
        entry['status'] = 'disabled'
        entry['reason'] = _absent_bed_seat_reason(seat_index)
        entry['status_authority'] = _STATUS_AUTHORITY_BED
    candidate_groups: dict[str, list[dict]] = {}
    for entry in contract['entries']:
        if entry.get('certification_candidate') is True:
            candidate_groups.setdefault(entry['python_symbol'], []).append(entry)
    for symbol, entries in candidate_groups.items():
        seated = [entry for entry in entries if _absent_bed_seat(entry['e'], bed_seats) is None]
        apv0 = next((entry for entry in seated if entry['e'] == 'APV_0'), None)
        if not isinstance(apv0, dict):
            continue
        if apv0.get('status') == 'enabled' and str(apv0.get('status_authority') or '').startswith('device_receipt_set:'):
            owner, method_name = symbol.split('.', 1)
            if owner in {'ssl_comm', 'ha_comm'}:
                atlas_method = promoted_atlas['methods']['apv_full'][owner]['methods'][method_name]
                atlas_method['disabled'] = False
                atlas_method['reason'] = apv0['reason']
                atlas_method['status_authority'] = apv0['status_authority']
    for symbol, entries in candidate_groups.items():
        seated = [entry for entry in entries if _absent_bed_seat(entry['e'], bed_seats) is None]
        if not seated:
            continue
        receipt_hashes: set[str] = set()
        complete = True
        for entry in seated:
            key = ('entry', entry['e'], entry['f'], entry['python_symbol'])
            hashes = passed.get(key)
            if not hashes:
                complete = False
                break
            receipt_hashes.update(hashes)
        if not complete:
            continue
        authority_sha = hashlib.sha256(json.dumps(sorted(receipt_hashes), ensure_ascii=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        authority = f'device_receipt_set:{authority_sha}'
        for entry in seated:
            entry['status'] = 'enabled'
            entry['reason'] = 'every bed-seated E binding passed same-source device certification; final-contract release replay is still required'
            entry['status_authority'] = authority
        owner, method_name = symbol.split('.', 1)
        seated_apv0 = next((entry for entry in seated if entry['e'] == 'APV_0'), None)
        if owner in {'ssl_comm', 'ha_comm'} and seated_apv0 is not None:
            atlas_method = promoted_atlas['methods']['apv_full'][owner]['methods'][method_name]
            atlas_method['disabled'] = False
            atlas_method['reason'] = seated_apv0['reason']
            atlas_method['status_authority'] = authority
    for action in contract['execute_actions']:
        if action['status'] == 'enabled':
            continue
        certified_es: list[str] = []
        receipt_hashes: set[str] = set()
        for e_value in action['allowed_es']:
            if _absent_bed_seat(e_value, bed_seats) is not None:
                continue
            key = ('execute_action', e_value, action['dispatcher'], action['canonical'], action['python_symbol'])
            hashes = passed.get(key)
            if hashes:
                certified_es.append(e_value)
                receipt_hashes.update(hashes)
        if not certified_es:
            continue
        action['candidate_allowed_es'] = list(action['allowed_es'])
        action['allowed_es'] = sorted(certified_es)
        authority_sha = hashlib.sha256(json.dumps(sorted(receipt_hashes), ensure_ascii=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        action['status'] = 'enabled'
        action['reason'] = 'same-source device certification passed for the authorized E bindings; final-contract release replay is still required'
        action['status_authority'] = f'device_receipt_set:{authority_sha}'
        atlas_key = f"{action['dispatcher']}:{action['normalized']}"
        atlas_action = atlas_capabilities[atlas_key]
        atlas_action['candidate_allowed_es'] = list(atlas_action['allowed_es'])
        atlas_action['allowed_es'] = list(action['allowed_es'])
        atlas_action['status'] = action['status']
        atlas_action['reason'] = action['reason']
        atlas_action['status_authority'] = action['status_authority']
    enabled_action_es = {e_value for action in contract['execute_actions'] if action['status'] == 'enabled' for e_value in action['allowed_es']}
    authorities_by_e: dict[str, set[str]] = {}
    for action in contract['execute_actions']:
        if action['status'] != 'enabled':
            continue
        for e_value in action['allowed_es']:
            authorities_by_e.setdefault(e_value, set()).add(action['status_authority'])
    for entry in contract['entries']:
        if entry['dispatch'] != 'execute_registry':
            continue
        seat_index = _absent_bed_seat(entry['e'], bed_seats)
        if seat_index is not None:
            entry['status'] = 'disabled'
            entry['reason'] = _absent_bed_seat_reason(seat_index)
            entry['status_authority'] = _STATUS_AUTHORITY_BED
            continue
        if entry['e'] in enabled_action_es:
            entry['status'] = 'enabled'
            entry['reason'] = 'execute dispatcher has at least one enabled exact action for this E'
            authority_values = sorted(authorities_by_e.get(entry['e'], set()))
            entry['status_authority'] = authority_values[0] if len(authority_values) == 1 else 'mixed:execute-action-authorities'
        else:
            entry['status'] = 'disabled'
            entry['reason'] = 'execute dispatcher has no enabled action implementation for this E'
            entry['status_authority'] = _STATUS_AUTHORITY_ACTION
    contract['certification'] = {'schema': 'ist.excel.capability-certification-set', 'basis_contract_sha256': basis_sha, 'certified_entries_sha256': certified_entries_digest(contract['entries']), 'basis_contract_file_sha256': basis_contract_file_sha256, 'deployment_receipt_sha256': deployment_receipt_sha256, 'receipt_set_sha256': receipt_set.receipt_set_sha256, 'receipt_count': len(receipt_set.receipts)}
    _validate_excel_contract_alignment(promoted_atlas, [item['e'] for item in contract['objects']], contract['entries'], contract['execute_actions'])
    contract['contract_sha256'] = contract_sha256(contract)
    return (promoted_atlas, contract)
apply_execute_certifications = apply_capability_certifications

class CertifiedBasisCarryForwardError(ValueError):
    pass
_CERT_IDENTITY_EXCLUDED = frozenset({'status', 'status_authority', 'reason'})
_CERT_IDENTITY_REFERENCE_FIELDS = frozenset({'source'})

def _certified_entry_identity(entry: Mapping[str, Any], *, exclude_reference: bool=True) -> str:
    """被认证条目的内容身份；排除的三个字段是结转本身要改写的。

    exclude_reference=False 给出 2026-09-22 之前的旧口径（含引用层字段），
    只为承接存量合同里按旧口径记录的 certified_entries_sha256 保留。
    """
    excluded = _CERT_IDENTITY_EXCLUDED
    if exclude_reference:
        excluded = excluded | _CERT_IDENTITY_REFERENCE_FIELDS
    payload = {key: value for key, value in entry.items() if key not in excluded}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(serialized).hexdigest()

def _certified_entry_key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(entry.get('e') or ''), str(entry.get('f') or ''), str(entry.get('python_symbol') or ''))

def _is_receipt_certified(entry: Mapping[str, Any]) -> bool:
    return str(entry.get('status_authority') or '').startswith('device_receipt_set:')

def certified_entries_digest(entries: Iterable[Mapping[str, Any]], *, exclude_reference: bool=True) -> str:
    """被认证条目（device_receipt_set 授权）的内容身份有序摘要。"""
    parts = sorted((f'{_certified_entry_key(entry)}:{_certified_entry_identity(entry, exclude_reference=exclude_reference)}' for entry in entries if _is_receipt_certified(entry)))
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()

def carry_forward_capability_certifications(atlas: Mapping[str, Any], generated_basis: Mapping[str, Any], certified_contract: Mapping[str, Any]) -> tuple[dict, dict]:
    certification = certified_contract.get('certification')
    if not isinstance(certification, dict):
        raise CertifiedBasisCarryForwardError('certified contract carries no certification block')
    declared_digest = str(certification.get('certified_entries_sha256') or '')
    certified_entries = [entry for entry in certified_contract.get('entries') or () if _is_receipt_certified(entry)]
    bed_seats = _bed_apv_seats()
    for entry in certified_entries:
        seat_index = _absent_bed_seat(str(entry.get('e') or ''), bed_seats)
        if seat_index is not None:
            raise CertifiedBasisCarryForwardError(f"certified entry targets a seat absent from this bed: {entry.get('e')}")
    if declared_digest:
        if certified_entries_digest(certified_entries) != declared_digest and certified_entries_digest(certified_entries, exclude_reference=False) != declared_digest:
            raise CertifiedBasisCarryForwardError('certified entries do not match the digest recorded at certification')
    if not declared_digest and (not certified_entries) and (certification.get('basis_contract_sha256') != generated_basis.get('contract_sha256')):
        raise CertifiedBasisCarryForwardError('certified contract does not descend from the generated basis')
    basis_by_key = {_certified_entry_key(entry): entry for entry in generated_basis.get('entries') or ()}
    for entry in certified_entries:
        key = _certified_entry_key(entry)
        counterpart = basis_by_key.get(key)
        if counterpart is None:
            raise CertifiedBasisCarryForwardError(f'certified entry is absent from the generated basis: {key}')
        if _certified_entry_identity(entry) != _certified_entry_identity(counterpart):
            raise CertifiedBasisCarryForwardError(f'certified entry changed since certification: {key}')
    promoted_atlas = copy.deepcopy(dict(atlas))
    contract = copy.deepcopy(dict(certified_contract))
    for entry in contract['entries']:
        authority = str(entry.get('status_authority') or '')
        if entry.get('status') != 'enabled' or not authority.startswith('device_receipt_set:'):
            continue
        symbol = str(entry.get('python_symbol') or '')
        if '.' not in symbol:
            continue
        owner, method_name = symbol.split('.', 1)
        if owner not in {'ssl_comm', 'ha_comm'} or entry.get('e') != 'APV_0':
            continue
        atlas_method = promoted_atlas['methods']['apv_full'][owner]['methods'][method_name]
        atlas_method['disabled'] = False
        atlas_method['reason'] = entry['reason']
        atlas_method['status_authority'] = authority
    atlas_capabilities = promoted_atlas['execute_actions']['capabilities']
    for action in contract['execute_actions']:
        authority = str(action.get('status_authority') or '')
        if action.get('status') != 'enabled' or not authority.startswith('device_receipt_set:'):
            continue
        key = f"{action['dispatcher']}:{action['normalized']}"
        atlas_action = atlas_capabilities[key]
        for field in ('candidate_allowed_es', 'allowed_es', 'status', 'reason', 'status_authority'):
            if field in action:
                atlas_action[field] = copy.deepcopy(action[field])
            else:
                atlas_action.pop(field, None)
    _validate_excel_contract_alignment(promoted_atlas, [item['e'] for item in contract['objects']], contract['entries'], contract['execute_actions'])
    if contract_sha256(certified_contract) != certified_contract.get('contract_sha256'):
        raise CertifiedBasisCarryForwardError('certified contract canonical identity is invalid')
    contract['certification']['basis_contract_sha256'] = generated_basis['contract_sha256']
    contract['certification']['basis_contract_file_sha256'] = hashlib.sha256(render_json(generated_basis).encode('utf-8')).hexdigest()
    contract['source_hashes'] = copy.deepcopy(dict(generated_basis['source_hashes']))
    contract['certification']['certified_entries_sha256'] = certified_entries_digest(contract['entries'])
    contract['contract_sha256'] = contract_sha256(contract)
    return (promoted_atlas, contract)
_CURATED_GENERATED_FIELDS = {'server_trigger_hosts': ['hosts']}
_CURATED = {'dispatch_decision_table': {'mechanism': 'F 列派发的唯一真规则（框架执行器，出处已脱敏）:`func = getattr(E对象, F)`,F 不在对象方法集 → AttributeError → 崩整份 pytest 文件(无 try/except)。`execute` 只是**恰好可以被 getattr 到的众多方法之一**,它自己内部还要再查一层动作注册表(`execute_actions.registry`)。', 'paths': {'direct_method_call': 'F 直接是某 mixin 的方法名(如 csrVhost/seg_config/ha_default)——`getattr(E,F)(*G解析结果)` 一步到位,不经 execute 注册表。归属哪个 F 走这条路,查 `methods.*` 里该方法条目自己的 `dispatch_kind` 字段,不要在这里枚举(会漂移——本表只讲机制)。', 'execute_registry': 'F 字面等于 `execute` 时,G 的全角冒号前段是动作名,须是 `execute_actions.registry` 归一化后的精确成员;非精确名落 `SequenceMatcher≥0.8` 模糊匹配,可能派到语义相反的动作（已核）。', 'cmd_config_passthrough': 'F 是 `cmd_config`/`cmds_config` 时,G 原样(或按 `\\n` 切分)当 CLI 命令文本转发,不经任何方法/注册表查找——SLB/SDNS 两域没有专属 Python 方法家族,全部命令走这条路,是三条路里唯一“零认知门槛”的一条。'}, 'how_to_tell_apart': '先看 F 是不是字面 `cmd_config`/`cmds_config`(是→第③条,结束判断);再看 F 是不是字面 `execute`(是→第②条,G 前段去查注册表);都不是→第①条,F 本身就是要 getattr 的方法名,去 `methods.*` 里按方法名查它在哪个 family、需要什么参数。**SSL/segment/HA 是唯一有这第①条路的三个 mixin 家族**——SLB/SDNS 两域只有②③两条路,没有岔路口。', 'source': '框架内部实现（出处已脱敏）'}, 'register_semantics': {'mechanism': 'H(row[7])/I(row[8]) 在普通设备步与 check_point 步里角色互换（框架执行器逐行机械陈述，出处已脱敏）。', 'regular_step': {'H': '输出寄存器:None→返回值存临时变量 `result`(下一个 check_point 步的隐式默认比较对象,每个普通步都会覆盖它);非 None→按此名存入 `locals()`供后续任意步按名读取。', 'I': '输入注入:None→不注入;非 None→读同名 `locals()`/`globals()` 变量(或 `obj.attr` 点号取属性),`.format()` 注入进 G 的**首个**位置参数;引用不到→`NameError`。'}, 'check_point_step': {'H': '期望值来源:None→直接用 G 的字面量当期望值;非 None→按此名读 `locals()` 变量当期望值(读一个更早的普通步用 H 存下的值)。', 'I': '实际值来源:None→比较对象是上一个普通步隐式写的 `result`;非 None→按此名读 `locals()` 变量,**覆盖**默认的 `result`。'}, 'source': '框架内部实现（出处已脱敏）'}, 'cert_arity_notes': {'rsa_import': 'RSA importKey/importCert = 2 参 <vhost>,<file_path>（已核）', 'sm2_import': 'SM2 sm2ImportKey/Cert = 3 参 <keyType>,<vhost>,<file_path>;keyType=signkey/enckey(签名)或 signcertificate/enccertificate——SM2 国密双证书体系;参数个数写错崩整卷（已核，基准语料核对）。', 'csr_subject': 'CSR subject 为框架硬编码（含厂商/站点名，已脱敏），不可参数化。', 'file_branch': 'M4′精确化(旧文案把这条写成全体 cert 方法的通用性质,过泛化——实测只有 6/44 个方法有此双分支):文件名 .key/.crt/.pem 结尾→本地读文件内联粘贴;否则→TFTP 从 172.16.35.215 取。**仅这 6 个方法有此双分支**:importKey/importCert/importMutiKey/importMutiCert/sm2ImportMutiKey/sm2ImportMutiCert。其余方法要么恒走本地(如 importRealKey/importSniKey 等,源码没有扩展名判断,永远尝试本地 open())要么恒走 TFTP(全部 *_tftp 后缀方法,无本地分支)——用非这 6 个之一的方法时,不能假设“扩展名写对就能本地导入”。金标准全走本地分支（已核）,床就绪只需本地 cert 树。', 'activate_dependency': 'ssl activate certificate <h> 依赖先有 ssl host virtual <h>(文法规则 ssl_cert_activate_needs_host_define 已查)。'}, 'cert_role_confusion': {'ca_family': 'importRootCA/importInterCA/importCRLCA(+importSniRootca/importSniInterca/importSniCrlca 三个 Sni 变体)——组内各方法体逐行相同,唯一差异是内嵌的 CLI 动词(rootca/interca/crlca);三个动词都是设备合法命令,调错**不报错、不崩卷**,证书内容照常送上设备,只是装进了错误的信任链角色槽(根证书/中间证书/吊销列表证书三选一)——写用例前先确认要装的到底是哪一种角色,不要凭方法名相近猜。', 'source': '框架 SSL 模块（出处已脱敏）'}, 'cert_behavior_notes': {'importCert': {'note': '导入后**自动 ssl activate certificate + YES**,勿再手动 activate', 'source': '框架 SSL 模块（出处已脱敏）'}, 'importRealCert': {'note': '同 importCert,自动 activate', 'source': '框架 SSL 模块（出处已脱敏）'}, 'sm2ImportCert': {'note': '自动 activate', 'source': '框架 SSL 模块（出处已脱敏）'}}, 'server_trigger_hosts': {'contract': 'E=test_env,F=serverNNN;SSH 到 config [env] 段该逻辑名的 IP,凭据由框架运行时从自身配置取——卷面不写,worker 也不需要(不是“有个东西但轮不到”,是这件事根本不归案例作者管);worker 只需填 G=后端 shell 命令(起停真实服务器造 UP/DOWN);ip addr/route add 自动记账、case 尾框架自动恢复(勿自行 del)。**本段只给主机闭集,不列这些主机上跑着什么服务**——该起停哪个服务、命令怎么写,用 `lang_query` 现查(`kind=usage` 按主机名查语料里真出现过的 G;查得到即真用过,查不到只说明语料没有、不等于不能这么用),别照记忆猜服务名。', 'source': '框架 env 主机闭集（AST 解析框架传输会话构造，出处已脱敏）'}, 'silent_failure_faces': [{'id': 'S1', 'mechanism': '证书/密钥文件缺→print+return,import 没发生、不抛错(假象=断言错)', 'source': '框架 SSL 模块（出处已脱敏）'}, {'id': 'S2', 'mechanism': 'runner v2 精确动作规则之外的 execute miss/fuzzy 派发可静默返回 None；当前卷出现此形态说明 runner 身份不匹配或绕过规则', 'source': '框架执行器与动作注册（出处已脱敏）'}, {'id': 'S3', 'mechanism': 'server/read_until 超时→返回部分输出、非抛错(断言搜残缺窗口假 fail)', 'source': '框架传输模块（出处已脱敏）'}, {'id': 'S4', 'mechanism': 'TFTP 源 172.16.35.215 不可达/文件缺(金标准不走此分支,床需本地 cert 树)', 'source': '框架 SSL 模块（出处已脱敏）'}, {'id': 'S5', 'mechanism': 'H 存 None(多数 SSL import 无 return)→后续 H 引用无意义', 'source': '框架执行器（出处已脱敏）'}], 'attribution_note': '上机 fail 归因时,先用 S1-S5 把 harness 静默失败与真实设备行为分开——harness 静默失败伪装成 V 层断言错（归因器 S1-S5，出处已脱敏）。', 'exclusions': {'preparation_suspect_dead': {'methods': ['prepare', 'extract_components', 'preprocess_text', 'config_param'], 'reason': "直读源码确认(非推测):`prepare()` 内 `getattr(self,'ssl')`/`getattr(self,'security')`/`getattr(self,'acl')` 依赖的 `self.ssl`/`self.security`/`self.acl` 三个属性,在 `APV.__init__`/`preparation.__init__` 全部代码路径里从未被赋值(`__init__` 只设了`config_flag`/`feature_list`/`sslSubFeature` 等**不同名**的属性)——调用 `prepare()` 走到这几行必 `AttributeError`。方法条目仍保留在 `methods.apv_full.preparation` 里(供完整性核对),但标此注记,不推荐案例编写使用。"}, 'transport_variants_not_independent': {'modules': ['transport_ssh', 'transport_telnet', 'transport_tty', 'transport_cipher'], 'reason': '各自实现 cmd_config/cmd/cmd_enable/close/read_until(ssh/telnet/串口/加密通道四种连接方式的同款传输原语)——是 `cmd_config` 的底层传输实现,不是用例可选的另一套方法族,不单列为独立能力。'}, 'unexplored_e_values': {'values': [], 'reason': 'Excel function contract v1 now closes every runner E value, including Seg0_tmp/Seg1_tmp/Seg2_tmp and the nested http_server_231 fixture; the previous unexplored exclusion is retired.'}, 'engine_layer_kinds_not_framework_values': {'kinds': ['dist', 'member'], 'reason': '`dist`/`member` 是**编译引擎 blocks 组合子层**的 kind 语法糖（已裁定）,不是框架 `check_point` 的 F 方法、也不是任何mixin 的方法名——本图谱里查不到它们是正常的,不要当成framework能力缺口去找。它们展开后落地成的是普通 `found`/`abs_found` 等真实 F 值。'}}}

def build(*, framework_source_identity: Mapping[str, Any] | None=None, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> dict:
    """有 overlay 时连读源一起换，否则 atlas 与契约不同源。"""
    from cex_core.engine.case_compiler import apv_lang as _apv_lang
    with _apv_lang.source_overlay(source_overlays):
        return _build_inner(framework_source_identity=framework_source_identity)

def _build_inner(*, framework_source_identity: Mapping[str, Any] | None=None) -> dict:
    source_identity = copy.deepcopy(dict(framework_source_identity) if framework_source_identity is not None else _method_reference_source_identity())
    ssl_fam = _mixin_family('lib/apv/ssl_comm.py', 'ssl_comm', 'direct_method_call')
    seg_fam = _mixin_family('lib/apv/seg_comm.py', 'seg_comm', 'direct_method_call')
    ha_fam = _mixin_family('lib/apv/ha_comm.py', 'ha_comm', 'direct_method_call')
    prep_fam = _mixin_family('lib/apv/preparation.py', 'preparation', 'direct_method_call')
    _prep_dead = _CURATED['exclusions']['preparation_suspect_dead']
    for _name in _prep_dead['methods']:
        if _name in prep_fam['methods']:
            prep_fam['methods'][_name] = {**prep_fam['methods'][_name], 'disabled': True, 'reason': _prep_dead['reason']}
    _seg_disabled_reason = 'seg_comm is mechanically reachable but its Excel semantics and safe fixture lifecycle are not certified'
    for _name, _info in list(seg_fam['methods'].items()):
        seg_fam['methods'][_name] = {**_info, 'disabled': True, 'reason': _seg_disabled_reason}
    _direct_certification_reason = 'legacy direct signature is retained, but enabled authoring requires same-source device certification and final-contract release replay'
    for _family in (ssl_fam, ha_fam):
        for _name, _info in list(_family['methods'].items()):
            _family['methods'][_name] = {**_info, 'disabled': True, 'reason': _direct_certification_reason, 'certification_candidate': True}
    execute = _execute_actions()
    valid_fs = valid_fs_by_e()
    try:
        _, runner_found_times_supported = _runner_contract_facts(ast.parse(mirror_src('lib/test_xlsx.py'), filename='lib/test_xlsx.py'))
    except (SyntaxError, ValueError):
        runner_found_times_supported = False
    check_point_methods = {name: {'disabled': True, 'reason': 'runner lacks the v2 three-argument found_times dispatch'} if name == 'found_times' and (not runner_found_times_supported) else {} for name in sorted(valid_fs.get('check_point', frozenset()))}
    sorted_host_slot_names = sorted((e for e in host_slot_es() if e in valid_fs))
    assert len({frozenset(valid_fs[e]) for e in sorted_host_slot_names}) <= 1, f'host-slot E 值的方法集不再互相相同,不能再用其中任意一个代表 host_slot:{ {e: sorted(valid_fs[e]) for e in sorted_host_slot_names}}'
    non_apv_methods = {'env_hosts': sorted(valid_fs.get('test_env', frozenset())), 'check_point': check_point_methods, 'time': sorted(valid_fs.get('time', frozenset())), 'host_slot': sorted(valid_fs[sorted_host_slot_names[0]]) if sorted_host_slot_names else []}
    apv_bases = _ast_class_bases('lib/apv/apv.py', 'APV')
    objects = {'APV_0': {'source_class': f"APV({','.join(apv_bases)})", 'instantiation': 'apv_xlsx(id,idx) fixture 工厂,不经 request.getfixturevalue', 'capability_family': 'apv_full'}, 'APV_1': {'source_class': f"APV({','.join(apv_bases)})", 'instantiation': 'apv_xlsx(id,idx) fixture 工厂,不经 request.getfixturevalue', 'capability_family': 'apv_full'}, 'APV_2': {'source_class': f"APV({','.join(apv_bases)})", 'instantiation': 'apv_xlsx(id,idx) fixture 工厂,不经 request.getfixturevalue', 'capability_family': 'apv_full'}, 'test_env': {'source_class': 'Env', 'instantiation': 'pytest fixture', 'capability_family': 'env_hosts'}, 'check_point': {'source_class': 'Check_Point', 'instantiation': '显式传入(非 devices 表)', 'capability_family': 'check_point'}, 'time': {'source_class': 'python time module', 'instantiation': '内置', 'capability_family': 'time'}, 'Seg0_tmp': {'source_class': 'APV_SSH(ssl_comm,action,preparation)', 'instantiation': 'apv_seg fixture factory', 'capability_family': 'segment_full', 'status': 'disabled'}, 'Seg1_tmp': {'source_class': 'APV_SSH(ssl_comm,action,preparation)', 'instantiation': 'apv_seg fixture factory', 'capability_family': 'segment_full', 'status': 'disabled'}, 'Seg2_tmp': {'source_class': 'APV_SSH(ssl_comm,action,preparation)', 'instantiation': 'apv_seg fixture factory', 'capability_family': 'segment_full', 'status': 'disabled'}, 'http_server_231': {'source_class': 'nested http_server', 'instantiation': 'request.getfixturevalue', 'capability_family': 'http_server'}}
    for host in ('routera', 'server213', 'server231', 'server232'):
        objects[host] = {'source_class': 'ssh_server(client_action)', 'instantiation': 'request.getfixturevalue', 'capability_family': 'host_slot'}
    return {'_meta': {'purpose': 'worker-reachable full capability projection (v10 M1) — APV 全部 5 重 mixin(ssl_comm/seg_comm/ha_comm/action-execute/preparation)派发能力,补齐 method_reference.json(内部工单 方案a)只覆盖 ssl_comm+execute 两类的缺口(内部基准文档（已脱敏） §②)。', 'regenerate': 'python scripts/gen_capability_atlas.py(单命令同时产出本文件 + method_reference.json 兼容投影,避免生成顺序依赖——不读 JSON 产物,全部现场从 mirror 解析)', 'generated_at': datetime.now(timezone.utc).isoformat(), 'generated_parts': ['objects', 'methods', 'execute_actions'], 'curated_parts': list(_CURATED.keys()), 'curated_parts_generated_fields': {section: list(fields) for section, fields in _CURATED_GENERATED_FIELDS.items()}, 'framework_source_identity': source_identity, 'dispatch_kind_field_authority': '内部任务 评审约束A（内部评审）:每条 method 的 `dispatch_kind` 字段是**策展交叉核对值**(生成时按 mixin 归属静态打标),**不是查询的权威答案**——真正决定『这个 F 能不能这样派发』的权威源是 `apv_lang` 供 structural_gate.py 的规则直接使用的那份活体反射(`valid_fs_by_e()`/`apv_full_fs()`),lang_query 的 dispatch_kind 查询走的是对活体反射的反查,不读这个字段。直接把这个字段当派发权威去用=反向 <case>(<case> 是『规则拒了、worker 以为框架做不到』;反向 <case> 是『查询说能、规则其实会拒』——查询把 worker 引向一个执行时会被拦的动作,比查询说『不知道』更坏,因为 worker 会拿查询结果当行动依据)。这个字段仍然有用:拿它跟活体反射现查的结果比对,**不一致就是『atlas 该重新生成了』的直接证据**(比单纯比对 `generated_at` 时间戳更硬——一致不能证明没过期,但不一致是过期的充分证据)。', 'generated_from': '框架镜像源（出处已脱敏）', 'stub_methods_excluded': sorted(_MIXIN_STUB_METHODS), 'mixin_method_counts_note': '每个 mixin 的(总方法数, 候选能力数)两个数永远配对声明,差值恒等于该 mixin 里实际出现的桩方法数(至多 2 个:__init__/cmd_config):ssl_comm(46,44) / seg_comm(5,3) / ha_comm(3,1)——本行数字仅供人读,回归测试从 `len()` 现算,不手写锁定(§约束④)。', 'known_manual_count_discrepancy': "内部调研文档（已脱敏）曾人工计数 apv_action 设备侧动作为 31 个,本生成器机械核实(AST 解析 command_function_mapping 字面量)实为 32 个——人工计数的一次误差,这正是'能力要生成、不能手抄'的活证据,原样保留在此不静默订正原文档。"}, 'objects': objects, 'methods': {'apv_full': {'ssl_comm': ssl_fam, 'seg_comm': seg_fam, 'ha_comm': ha_fam, 'preparation': prep_fam}, **non_apv_methods}, 'execute_actions': execute, **_curated_sections()}

def _parse_cert_methods() -> dict:
    fam = _mixin_family('lib/apv/ssl_comm.py', 'ssl_comm', 'direct_method_call')
    return {name: {'required': v['required'], 'optional': v['optional']} for name, v in fam['methods'].items()}

def _execute_actions_legacy() -> dict:
    reg = execute_action_registry()
    return {'exact_action_names': sorted(set(reg.values())), 'note': 'F=execute 的 G 动作名必须是本集精确成员(全角冒号前段);非精确会落 fuzzy≥0.8 静默派发、可语义反转(内部工单 规则在 emit 期拒非精确名)。'}

def _method_reference_source_identity() -> dict:
    try:
        return build_framework_source_identity(_MIRROR_ROOT)
    except FrameworkProjectionIdentityError as exc:
        raise WindowedProjectionError(exc.detail) from exc

def _build_method_reference_projection(*, framework_source_identity: Mapping[str, Any] | None=None) -> dict:
    cert_methods = _parse_cert_methods()
    execute_actions = _execute_actions_legacy()
    source_identity = copy.deepcopy(dict(framework_source_identity) if framework_source_identity is not None else _method_reference_source_identity())
    return {'_meta': {'purpose': 'worker-reachable projection of framework method arg-signatures + execute action registry + silent-failure faces (mirror NOT in worker sandbox; this is the fs_read-able data-by-reference surface, 内部工单 FINDING 内部工单 fix a)', 'regenerate': 'python scripts/gen_method_reference.py（现为 gen_capability_atlas.py 的薄封装,二者等价,任跑其一都会同时重写两份产物）', 'generated_parts': ['cert_methods', 'execute_actions'], 'curated_parts': ['dispatch_skeleton', 'cert_arity_notes', 'cert_role_confusion', 'cert_behavior_notes', 'server_trigger_hosts', 'silent_failure_faces', 'attribution_note'], 'curated_parts_generated_fields': {section: list(fields) for section, fields in _CURATED_GENERATED_FIELDS.items()}, 'generated_from': '框架镜像源（出处已脱敏）', 'framework_source_identity': source_identity, 'superseded_by': 'capability_atlas.json（v10 M1 全量图谱；本文件是它的 ssl_comm+execute_actions 子集投影，只为不破坏既有 worker fs_read 指针而保留，新增能力面进 capability_atlas.json，不再进本文件）', 'cert_methods_count_note': "两个数各自为真、别混用:ssl_comm.py 类全量方法数=46(含 __init__/cmd_config 两个 mixin 接口桩方法,不是证书方法本身);本段cert_methods 只收候选证书方法=46-2=44 个——文档/审计记录里若单独出现'46'多半指类全量,单独出现'44'多半指本段条目数,二者差值恒等于那两个桩方法。其中恰好 6 个方法(见 cert_arity_notes.file_branch)有文件名扩展名双分支(本地读文件 vs TFTP 取)。", 'content_deviation_from_prior_version': '相对 v10 M1 基线的已知内容偏离=server_trigger_hosts.contract 移除凭据责任归属错误;server_trigger_hosts.hosts 由手抄字面量改为框架镜像 env 模块现场 AST 解析产物(集合同前,顺序改为源码声明序),同段 contract/source 仍为手写散文;silent_failure_faces.S2 更新为 runner v2 精确动作规则与旧 fuzzy/None 面的身份错配解释;silent_failure_faces.S5 的源码锚已脱敏（框架执行器内部锚点）;_meta.framework_source_identity 新增framework_sync 完整 lib 源码闭包与 conftest 身份。此声明不再声称除某一处外其余字段与历史版本完全等价。'}, 'cert_methods': cert_methods, 'execute_actions': execute_actions, 'dispatch_skeleton': {'E_F_G_H_I': 'getattr(E_obj, F)(*positional, **kwargs);G 逗号分参(引号感知);H=把返回值存进命名寄存器(device 步)/取期望值(check_point 步);I=把变量或对象.属性 .format() 注入 G 首参(须带 {} 占位)。', 'source': '框架执行器（出处已脱敏）'}, 'cert_arity_notes': _CURATED['cert_arity_notes'], 'cert_role_confusion': _CURATED['cert_role_confusion'], 'cert_behavior_notes': _CURATED['cert_behavior_notes'], 'server_trigger_hosts': _server_trigger_hosts(), 'silent_failure_faces': _CURATED['silent_failure_faces'], 'attribution_note': _CURATED['attribution_note']}

def _credential_closure_for_serialized_payloads(texts: list[str], source_overlays: Mapping[str, bytes | bytearray] | None=None) -> frozenset[str]:
    try:
        values = mirror_credential_literals_with_overlays(source_overlays) if source_overlays else mirror_credential_literals()
    except MirrorCredentialLiteralError as exc:
        raise WindowedProjectionError('credential literal closure is unavailable') from exc
    if not values:
        raise WindowedProjectionError('credential literal closure is empty')
    matches = sum((matching_credential_literal_count(text, values) for text in texts))
    if matches:
        raise WindowedProjectionError(f'refusing to write public capability projections with credential literal matches (count={matches})')
    return values

def _public_projection_credential_closure(atlas: dict, method_ref: dict, excel_contract: dict, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> frozenset[str]:
    index, shard_texts = build_method_reference_window(method_ref)
    return _credential_closure_for_serialized_payloads([render_json(atlas), render_json(excel_contract), render_json(index), *shard_texts.values()], source_overlays)

def _secure_runtime_path(path: Path, *, directory: bool) -> Path:
    runtime_root = _RUNTIME_ROOT.absolute()
    selected = path.absolute()
    try:
        relative = selected.relative_to(runtime_root)
    except ValueError as exc:
        raise ValueError('release evidence path escapes project runtime') from exc
    current = runtime_root
    try:
        root_stat = current.lstat()
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise ValueError('project runtime root is unsafe')
        for part in relative.parts:
            current = current / part
            entry = current.lstat()
            if stat.S_ISLNK(entry.st_mode):
                raise ValueError('release evidence path contains a symlink')
        final = current.lstat()
    except OSError as exc:
        raise ValueError('release evidence path is unavailable') from exc
    expected = stat.S_ISDIR(final.st_mode) if directory else stat.S_ISREG(final.st_mode)
    if not expected:
        raise ValueError('release evidence path has the wrong file type')
    return selected

def _source_overlays_from_root(root: Path) -> dict[str, bytes]:
    selected = _secure_runtime_path(root, directory=True)
    overlays: dict[str, bytes] = {}
    for rel in _CONTRACT_SOURCE_PATHS:
        candidate = selected / rel
        if not candidate.exists():
            continue
        safe = _secure_runtime_path(candidate, directory=False)
        overlays[rel] = safe.read_bytes()
    required = {'lib/test_xlsx.py', 'lib/apv/apv.py', 'lib/apv/apv_ssh.py'}
    if not required <= overlays.keys():
        raise ValueError(f'source overlay root is missing required staged files: {sorted(required - overlays.keys())}')
    return overlays
_CARRY_FORWARD_REFERENCE_SOURCES = frozenset({'lib/apv/clear.py'})

def _contract_source_paths_in_use(contract: Mapping[str, Any]) -> frozenset[str]:
    """合同条目/对象/动作实际引用到的源文件集合（判引用层闭集是否仍然悬空）。"""
    paths: set[str] = set()
    for section in ('entries', 'objects', 'execute_actions'):
        items = contract.get(section)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, Mapping):
                continue
            source = item.get('source')
            if isinstance(source, Mapping) and isinstance(source.get('path'), str):
                paths.add(source['path'])
    return frozenset(paths)

def _reference_only_source_drift(payload_hashes: Any, basis_hashes: Any, paths_in_use: frozenset[str]) -> frozenset[str] | None:
    """待结转合同与新基底之间的源文件漂移分类。

    空集＝无漂移；非空集＝漂移全部落在引用层闭集内、可结转；None＝漂移越过
    引用层（语义变化、文件集合增减、或闭集文件已被合同条目引用），结转必须拒。
    """
    if not isinstance(payload_hashes, Mapping) or not isinstance(basis_hashes, Mapping):
        return None
    if set(payload_hashes) != set(basis_hashes):
        return None
    drifted = frozenset((path for path in payload_hashes if payload_hashes[path] != basis_hashes[path]))
    if drifted - _CARRY_FORWARD_REFERENCE_SOURCES or drifted & paths_in_use:
        return None
    return drifted

def _load_basis_contract_file(path: Path, generated_basis: Mapping[str, Any], *, allow_canonical_projection: bool=False) -> tuple[str, bytes, dict[str, Any]]:
    selected = path.absolute()
    if allow_canonical_projection and selected == _EXCEL_CONTRACT_OUT.absolute():
        raw = read_regular_nofollow(selected, error_type=ValueError, invalid_message='canonical certified projection path is invalid', directory_message='canonical certified projection parent is unavailable', open_message='canonical certified projection is unavailable', bounds_message='canonical certified projection exceeds the size bound', changed_message='canonical certified projection changed while reading', max_bytes=16 * 1024 * 1024, min_bytes=2, trusted_root=_ROOT)
        assert isinstance(raw, bytes)
    else:
        selected = _secure_runtime_path(path, directory=False)
        raw = selected.read_bytes()
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise ValueError('basis contract file is not valid JSON') from exc
    if not isinstance(payload, dict):
        raise ValueError('basis contract file is not an object')
    source_drift = _reference_only_source_drift(payload.get('source_hashes'), generated_basis.get('source_hashes'), _contract_source_paths_in_use(generated_basis) | _contract_source_paths_in_use(payload))
    if source_drift:
        validation_payload = copy.deepcopy(payload)
        validation_payload['source_hashes'] = dict(generated_basis['source_hashes'])
    else:
        validation_payload = payload
    validate_excel_contract(validation_payload)
    if payload != generated_basis:
        certification = payload.get('certification')
        basis_runtime = generated_basis.get('runtime') or {}
        payload_runtime = payload.get('runtime') or {}
        runtime_drifted = any((payload_runtime.get(field) != basis_runtime.get(field) for field in ('minimum_version', 'runner_source', 'runner_sha256')))
        if not isinstance(certification, dict) or source_drift is None or runtime_drifted or (payload.get('schema') != generated_basis.get('schema')) or (payload.get('complete') is not True):
            raise ValueError('incremental basis does not descend from the generated source basis')

        def _entry_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
            return (str(item.get('e') or ''), str(item.get('f') or ''), str(item.get('python_symbol') or ''))
        generated_entries = {_entry_key(item): item for item in generated_basis['entries']}
        current_entries = {_entry_key(item): item for item in payload['entries']}
        if set(current_entries) != set(generated_entries):
            raise ValueError('incremental basis entry key set differs')
        for key, current in current_entries.items():
            generated = generated_entries[key]
            if generated.get('certification_candidate') is not True:
                if current.get('status') != generated.get('status'):
                    raise ValueError('incremental basis changed a non-candidate entry')
                continue
            if current.get('status') == 'enabled' and (not str(current.get('status_authority') or '').startswith('device_receipt_set:')):
                raise ValueError('incremental basis enabled a candidate without receipt authority')

        def _action_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
            return (str(item.get('dispatcher') or ''), str(item.get('normalized') or ''), str(item.get('python_symbol') or ''))
        if {_action_key(item) for item in payload['execute_actions']} != {_action_key(item) for item in generated_basis['execute_actions']} or {str(item.get('e') or '') for item in payload['objects']} != {str(item.get('e') or '') for item in generated_basis['objects']}:
            raise ValueError('incremental basis action/object key set differs')
    return (hashlib.sha256(raw).hexdigest(), raw, payload)

def _deployment_receipt_sha256(path: Path, basis_contract: Mapping[str, Any]) -> str:
    selected = _secure_runtime_path(path, directory=False)
    raw = selected.read_bytes()
    try:
        receipt = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise ValueError('deployment receipt is not valid JSON') from exc
    if not isinstance(receipt, dict) or receipt.get('schema') != 1 or receipt.get('scope') != 'excel_runtime_deployment' or (receipt.get('status') != 'deployed') or (receipt.get('contract_sha256') != basis_contract['contract_sha256']):
        raise ValueError('deployment receipt does not bind the basis contract')
    after = receipt.get('after')
    if not isinstance(after, dict):
        raise ValueError('deployment receipt has no complete post-state')
    for relative, expected in basis_contract['source_hashes'].items():
        state = after.get(relative)
        if not isinstance(state, dict) or state.get('exists') is not True or state.get('sha256') != expected:
            raise ValueError('deployment receipt source closure differs from the basis contract')
    return hashlib.sha256(raw).hexdigest()

def _record_certification_downgrade(prior_contract_path: Path, failure: Exception) -> Path:
    """结转失败回落裸重生前，把丢失的设备认证清单落成显式事实。

    2026-09-22 事故：结转失败静默回落，ssl/ha 认证从合同消失后无人知晓，
    且重认证通道自锁导致永久丢失。这里至少把「丢了什么、为什么」落盘，
    供预检与人工核对。
    """
    lost: list[dict[str, str]] = []
    try:
        prior = json.loads(prior_contract_path.read_text(encoding='utf-8'))
        for entry in prior.get('entries') or ():
            if entry.get('status') == 'enabled' and str(entry.get('status_authority') or '').startswith('device_receipt_set:'):
                lost.append({'e': str(entry.get('e') or ''), 'f': str(entry.get('f') or ''), 'python_symbol': str(entry.get('python_symbol') or '')})
    except (OSError, ValueError):
        pass
    record = {'schema': 'ist.excel.capability-certification-downgrade', 'prior_contract': str(prior_contract_path), 'failure_type': type(failure).__name__, 'failure_detail': str(failure)[:500], 'lost_certified_entries': lost, 'lost_count': len(lost), 'recorded_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'recovery': 'recoverable certification candidates re-enter the sample scope; rerun the certification volume to restore them'}
    out = _ROOT / 'runtime/excel_capability_receipts/certification_downgrade.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_json(record), encoding='utf-8')
    return out

def regenerate_with_carry_forward(project_root: Path | None=None) -> str:
    """按当前 mirror 重生公开投影，尽量把已签的设备认证结转过来。

    策略正本——`environment_prepare._converge_framework_projections` 与
    `scripts.regen_knowledge_base` 都调这里，不各写一份 try/fallback。裸调
    `main([])` 会把契约里 10 条 `device_receipt_set` 认证一并抹掉（ssl/ha 解锁
    丢失）；结转失败（真换版时必然）才回落。返回走的哪一路。
    """
    root = Path(project_root) if project_root is not None else _ROOT
    if root.resolve() != _ROOT.resolve():
        raise ValueError(f'generator is bound to another project root: {root} != {_ROOT}')
    prior_contract = root / 'knowledge/data/compile_ref/excel_contract.json'
    if prior_contract.is_file():
        try:
            main(['--carry-forward-certified-basis', str(prior_contract)])
            return 'carried_forward'
        except CertifiedBasisCarryForwardError as exc:
            downgrade_path = _record_certification_downgrade(prior_contract, exc)
            print(f'WARNING: certified basis carry-forward failed ({type(exc).__name__}); {downgrade_path}')
    main([])
    return 'regenerated'

def main(argv: list[str] | None=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-overlay-root', type=Path)
    parser.add_argument('--excel-contract-out', type=Path)
    parser.add_argument('--certification-receipts', type=Path)
    parser.add_argument('--basis-contract', type=Path)
    parser.add_argument('--deployment-receipt', type=Path)
    parser.add_argument('--carry-forward-certified-basis', type=Path)
    args = parser.parse_args([] if argv is None else argv)
    if bool(args.source_overlay_root) != bool(args.excel_contract_out):
        parser.error('--source-overlay-root and --excel-contract-out must be supplied together')
    certification_args = (args.certification_receipts, args.basis_contract, args.deployment_receipt)
    if any(certification_args) and (not all(certification_args)):
        parser.error('--certification-receipts, --basis-contract and --deployment-receipt must be supplied together')
    if args.carry_forward_certified_basis and any(certification_args):
        parser.error('--carry-forward-certified-basis cannot be combined with new certification receipts')
    overlays = _source_overlays_from_root(args.source_overlay_root) if args.source_overlay_root else {}
    if args.carry_forward_certified_basis and args.source_overlay_root:
        parser.error('--carry-forward-certified-basis cannot target a deployment source overlay')
    framework_source_identity = _method_reference_source_identity()
    atlas = build(framework_source_identity=framework_source_identity, source_overlays=overlays)
    if not args.source_overlay_root:
        _credential_closure_for_serialized_payloads([render_json(atlas)])
    excel_contract = build_excel_contract(atlas, source_overlays=overlays)
    if args.certification_receipts:
        basis_file_sha, _basis_bytes, certification_basis = _load_basis_contract_file(args.basis_contract, excel_contract)
        deployment_sha = _deployment_receipt_sha256(args.deployment_receipt, certification_basis)
        receipt_set = load_receipt_directory(args.certification_receipts, contract=certification_basis, phase='certification', contract_file_sha256=basis_file_sha, deployment_receipt_sha256=deployment_sha, trusted_root=_CERTIFICATION_ROOT)
        atlas, excel_contract = apply_capability_certifications(atlas, certification_basis, receipt_set, basis_contract_file_sha256=basis_file_sha, deployment_receipt_sha256=deployment_sha)
    elif args.carry_forward_certified_basis:
        try:
            _prior_sha, _prior_bytes, certified_basis = _load_basis_contract_file(args.carry_forward_certified_basis, excel_contract, allow_canonical_projection=True)
            atlas, excel_contract = carry_forward_capability_certifications(atlas, excel_contract, certified_basis)
        except CertifiedBasisCarryForwardError:
            raise
        except (OSError, ValueError) as exc:
            raise CertifiedBasisCarryForwardError('old certified projection is incompatible with the generated basis') from exc
    if args.source_overlay_root:
        _credential_closure_for_serialized_payloads([render_json(excel_contract)], overlays)
        args.excel_contract_out.parent.mkdir(parents=True, exist_ok=True)
        args.excel_contract_out.write_text(render_json(excel_contract), encoding='utf-8')
        print(f"wrote staged {args.excel_contract_out} — entries={len(excel_contract['entries'])} actions={len(excel_contract['execute_actions'])} sha256={excel_contract['contract_sha256']}")
        return
    method_ref = _build_method_reference_projection(framework_source_identity=framework_source_identity)
    atlas['_meta']['excel_contract'] = {'schema': EXCEL_CONTRACT_SCHEMA, 'path': 'knowledge/data/compile_ref/excel_contract.json', 'sha256': excel_contract['contract_sha256'], 'complete': True}
    credential_values = _public_projection_credential_closure(atlas, method_ref, excel_contract, overlays)
    if _method_reference_source_identity() != framework_source_identity:
        raise WindowedProjectionError('framework mirror changed while public projections were being generated')
    windowed = write_method_reference_window(method_ref, index_path=_METHOD_REF_OUT, credential_values=credential_values)
    _ATLAS_OUT.write_text(render_json(atlas), encoding='utf-8')
    _EXCEL_CONTRACT_OUT.write_text(render_json(excel_contract), encoding='utf-8')
    print(f'wrote {_ATLAS_OUT}')
    print(f"wrote {_EXCEL_CONTRACT_OUT} — entries={len(excel_contract['entries'])} actions={len(excel_contract['execute_actions'])} sha256={excel_contract['contract_sha256']}")
    print(f"wrote {_METHOD_REF_OUT} + method_reference/ shards={windowed['shard_count']} index_lines={windowed['index_lines']} — cert_methods={len(method_ref['cert_methods'])} exact_actions={len(method_ref['execute_actions']['exact_action_names'])}")
if __name__ == '__main__':
    main(sys.argv[1:])
