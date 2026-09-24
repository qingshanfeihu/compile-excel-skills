# 生成：tools/extract_engine.py ← InfoTest scripts/gen_blocks_schema.py（sha256 84e26648d0438e91）。不在这里手改。
"""从 blocks.py 源码机械解析组合子字段契约，产 blocks_schema.json 机读投影。

worker 写 blocks 之前唯一能查的字段契约是 EXCEL_FUNCTIONS.md 的散文示意——
示意里没有「哪些字段必选」，kind 闭集只在被拒绝时才出现。本投影把
``expand_blocks`` 自己的判据抽成机读形态：kind 闭集、每个 kind 消费哪些字段、
哪些字段缺席即拒、取值域闭集是什么、断言身份键的承载位在哪、以及每条拒绝
文案的原文。

**解析而非抄写**:全部结论从 ``main/case_compiler/blocks.py`` 的 AST 现算,
改了展开器不重跑本脚本,守门测试当场红(投影过期即红)。

**scope 边界(写进产物 `_meta.scope`,别读成「过了这层就安全」)**:这里记的只有
``expand_blocks`` **展开期**自己的拒绝。下游还有 provenance authority 规则、
15 道必崩规则、emit 双射规则——本投影标 optional 的字段仍可能在那些规则被拒。

用法::

    python -m scripts.gen_blocks_schema
"""
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
ROOT = _cex_data_path('')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_RELPATH = 'main/case_compiler/blocks.py'
SSL_SOURCE_RELPATH = 'main/ist_core/tools/device/emit_xlsx_tool.py'
SSL_FIXTURE_SOURCE_RELPATH = 'main/case_compiler/excel_capability_samples.py'
DISTRIBUTION_SOURCE_RELPATH = 'main/case_compiler/distribution_assertion.py'
DEFAULT_OUTPUT = ROOT / 'knowledge/data/compile_ref/blocks_schema.json'
SCHEMA = 'ist.blocks-schema'
EXPANDER = 'main.case_compiler.blocks.expand_blocks'
SCOPE_NOTE = "Every requirement below is a refusal expand_blocks itself raises at expansion time. Downstream gates refuse more: provenance authority (a source.kind of emit_auto is refused on every step except the time.sleep primitive), the mandatory crash rules, and the emit expectation bijection. A field marked optional here can still be refused later, and passing expansion is not a statement that the case is sound. SSL_CERT_LOAD is the one engine-owned standard-library sugar: compile_lint and submit_mechanical_case lower it with the reference function named in that kind's entry before expand_blocks runs."
REQUIREMENT_NOTE = {'required': 'expand_blocks refuses the block when this field is absent or empty.', 'checked': 'expand_blocks runs a refusal check whose test consumes this field, but the check is not a plain presence test, so whether absence alone is refused is not derivable mechanically — read the verbatim refusals attached to it.', 'optional': 'No expansion-time refusal consumes this field.'}
_UNRESOLVED = object()
_IDENTITY_HELPER = '_assertion_identity'
_MAX_FOLLOW_DEPTH = 2

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _str_const(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        pass
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id == 'frozenset') and (len(node.args) == 1) and (not node.keywords):
        try:
            return set(ast.literal_eval(node.args[0]))
        except (ValueError, TypeError, SyntaxError):
            return None
    return None

def _ordered(values: Any) -> list[Any]:
    if isinstance(values, (list, tuple)):
        return list(values)
    return sorted(values, key=repr)

def _module_constants(tree: ast.Module) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = _literal(node.value)
        if value is not None:
            out[target.id] = value
    return out

def _module_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

def _render_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append('{' + ast.unparse(value.value) + '}')
        return ''.join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _render_text(node.left)
        right = _render_text(node.right)
        if left is None and right is None:
            return None
        return (left or '') + (right or '')
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.args:
            return _render_text(node.args[-1])
    return None

def _key_access(node: ast.AST, var: str) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == 'get' and isinstance(node.func.value, ast.Name):
            if node.func.value.id == var and node.args:
                return _str_const(node.args[0])
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        if node.value.id == var:
            return _str_const(node.slice)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        if isinstance(node.ops[0], (ast.In, ast.NotIn)):
            comparator = node.comparators[0]
            if isinstance(comparator, ast.Name) and comparator.id == var:
                return _str_const(node.left)
    return None

def _kind_guard(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None
    if not isinstance(node.ops[0], ast.Eq):
        return None
    if not (isinstance(node.left, ast.Name) and node.left.id == 'kind'):
        return None
    return _str_const(node.comparators[0])

def _sweep(node: ast.AST, var: str, guard: str | None, sink: dict[str, set[str | None]]) -> None:
    if isinstance(node, ast.IfExp):
        inner = _kind_guard(node.test) or guard
        _sweep(node.test, var, guard, sink)
        _sweep(node.body, var, inner, sink)
        _sweep(node.orelse, var, guard, sink)
        return
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        running = guard
        for value in node.values:
            _sweep(value, var, running, sink)
            running = _kind_guard(value) or running
        return
    if isinstance(node, ast.If):
        inner = _kind_guard(node.test) or guard
        _sweep(node.test, var, guard, sink)
        for statement in node.body:
            _sweep(statement, var, inner, sink)
        for statement in node.orelse:
            _sweep(statement, var, guard, sink)
        return
    key = _key_access(node, var)
    if key is not None:
        sink.setdefault(key, set()).add(guard)
    for child in ast.iter_child_nodes(node):
        _sweep(child, var, guard, sink)

def _eval_default(node: ast.AST, var: str, defaults: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return defaults.get(node.id, _UNRESOLVED)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        for value in node.values:
            resolved = _eval_default(value, var, defaults)
            if resolved is _UNRESOLVED:
                return _UNRESOLVED
            if resolved:
                return resolved
        return resolved
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == 'get' and isinstance(func.value, ast.Name) and (func.value.id == var):
                if len(node.args) >= 2:
                    return _eval_default(node.args[1], var, defaults)
                return None
            if func.attr in {'strip', 'lower', 'upper'} and (not node.args):
                base = _eval_default(func.value, var, defaults)
                if not isinstance(base, str):
                    return _UNRESOLVED
                return getattr(base, func.attr)()
        if isinstance(func, ast.Name) and func.id == 'str' and (len(node.args) == 1):
            base = _eval_default(node.args[0], var, defaults)
            if base is _UNRESOLVED or base is None:
                return _UNRESOLVED
            return str(base)
    return _UNRESOLVED

def _keys_of(node: ast.AST, var: str, env: dict[str, set[str]]) -> set[str]:
    keys: set[str] = set()
    for sub in ast.walk(node):
        key = _key_access(sub, var)
        if key is not None:
            keys.add(key)
        elif isinstance(sub, ast.Name) and sub.id in env:
            keys |= env[sub.id]
    return keys

def _distribution_count_binding_refusal() -> str:
    """分布计数绑定缺失的拒绝原文——调真函数取，不手抄。

    入参是一份**必然触发**的绑定缺失：`field` 空、桶也不给含 `{range}` 的完整
    `pattern`。函数哪天不再拒它，下面那句 raise 当场把生成器停住——手抄文案会在
    文案改动时静默失配，取样例不会。
    """
    from cex_core.engine.case_compiler.distribution_assertion import distribution_count_binding_error
    sample = distribution_count_binding_error('', [{'anchor': 'pool_a', 'expected': 40}])
    if not sample:
        raise ValueError('distribution_count_binding_error no longer refuses an unbound count; its refusal example would go silently missing from the table')
    return sample
_REFUSAL_SAMPLERS = {'distribution_count_binding_error': _distribution_count_binding_refusal}

def _refusal_carrier(body: list[ast.stmt]) -> ast.Name | None:
    """拒绝原文装在哪个局部变量里——`_render_text` 渲不出来时的第二条路。

    三种形态都剥到最里面那个名字：`return None, None, name`、
    `return None, None, _err(i, kind, name)`、`… name or "literal"`。
    """
    for statement in body:
        if not isinstance(statement, ast.Return) or statement.value is None:
            continue
        value: ast.AST = statement.value
        if isinstance(value, ast.Tuple) and value.elts:
            value = value.elts[-1]
        if isinstance(value, ast.Call) and value.args:
            value = value.args[-1]
        if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or):
            value = value.values[0]
        if isinstance(value, ast.Name):
            return value
    return None

def _sampled_refusal(body: list[ast.stmt], call_env: dict[str, str]) -> str | None:
    """把变量回溯到产出它的函数，函数登记过就调它取例句。"""
    carrier = _refusal_carrier(body)
    if carrier is None:
        return None
    sampler = _REFUSAL_SAMPLERS.get(call_env.get(carrier.id, ''))
    return None if sampler is None else sampler()

def _refusal_message(body: list[ast.stmt]) -> tuple[bool, str | None]:
    for statement in body:
        if not isinstance(statement, ast.Return):
            continue
        value = statement.value
        if value is None:
            continue
        if isinstance(value, ast.Tuple) and len(value.elts) in {2, 3}:
            head = value.elts[0]
            if isinstance(head, ast.Constant) and head.value is None:
                return (True, _render_text(value.elts[-1]))
            continue
        message = _render_text(value)
        if message:
            return (True, message)
    return (False, None)

def _atoms(test: ast.AST) -> list[ast.AST]:
    if isinstance(test, ast.BoolOp):
        out: list[ast.AST] = []
        for value in test.values:
            out.extend(_atoms(value))
        return out
    return [test]

def _classify_atom(atom: ast.AST, var: str, env: dict[str, set[str]], constants: dict[str, Any]) -> tuple[str, set[str], list[Any] | None]:
    if isinstance(atom, ast.UnaryOp) and isinstance(atom.op, ast.Not):
        if isinstance(atom.operand, ast.BoolOp):
            return ('other', _keys_of(atom.operand, var, env), None)
        return ('presence', _keys_of(atom.operand, var, env), None)
    if isinstance(atom, ast.Compare) and len(atom.ops) == 1:
        op = atom.ops[0]
        right = atom.comparators[0]
        if isinstance(op, ast.Is) and isinstance(right, ast.Constant) and (right.value is None):
            return ('presence', _keys_of(atom.left, var, env), None)
        if isinstance(op, ast.NotIn):
            domain = _literal(right)
            if domain is None and isinstance(right, ast.Name):
                domain = constants.get(right.id)
            if isinstance(domain, (list, tuple, set, frozenset)):
                return ('domain', _keys_of(atom.left, var, env), _ordered(domain))
    return ('other', _keys_of(atom, var, env), None)

class _Scope:

    def __init__(self) -> None:
        self.consulted: dict[str, set[str | None]] = {}
        self.presence: set[str] = set()
        self.presence_when: dict[str, str] = {}
        self.domains: dict[str, list[Any]] = {}
        self.defaults: dict[str, Any] = {}
        self.refusals: dict[str, list[str]] = {}
        self.all_refusals: list[str] = []
        self.touched_by_refusal: set[str] = set()
        self.items: dict[str, '_Scope'] = {}
        self.identity_carriers: set[str] = set()
        self.closed_field_set: str | None = None

    def add_refusal(self, key: str, message: str) -> None:
        bucket = self.refusals.setdefault(key, [])
        if message not in bucket:
            bucket.append(message)

    def note_refusal(self, message: str) -> None:
        if message not in self.all_refusals:
            self.all_refusals.append(message)

def _analyze(stmts: list[ast.stmt], var: str, *, scope: _Scope, constants: dict[str, Any], functions: dict[str, ast.FunctionDef], seen: frozenset[str], depth: int) -> None:
    for statement in stmts:
        _sweep(statement, var, None, scope.consulted)
    env: dict[str, set[str]] = {}
    defaults: dict[str, Any] = {}
    _dataflow(stmts, var, env, defaults, scope=scope, constants=constants, functions=functions, seen=seen, depth=depth)

def _record_identity_carrier(node: ast.AST, var: str, scope: _Scope, item_vars: dict[str, str]) -> None:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return
    if node.func.id != _IDENTITY_HELPER or not node.args:
        return
    argument = node.args[0]
    if not isinstance(argument, ast.Name):
        return
    if argument.id == var:
        scope.identity_carriers.add('block')
    elif argument.id in item_vars:
        scope.identity_carriers.add(item_vars[argument.id])

def _assignment_pairs(statement: ast.Assign) -> list[tuple[str, ast.AST]]:
    target = statement.targets[0]
    if isinstance(target, ast.Name):
        return [(target.id, statement.value)]
    if isinstance(target, ast.Tuple):
        if isinstance(statement.value, ast.Tuple) and len(target.elts) == len(statement.value.elts):
            return [(name.id, value) for name, value in zip(target.elts, statement.value.elts) if isinstance(name, ast.Name)]
        return [(name.id, ast.Constant(value=None)) for name in target.elts if isinstance(name, ast.Name)]
    return []

def _direct_key(node: ast.AST, var: str, direct_env: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return direct_env.get(node.id)
    return _key_access(node, var)

def _dataflow(stmts: list[ast.stmt], var: str, env: dict[str, set[str]], defaults: dict[str, Any], *, scope: _Scope, constants: dict[str, Any], functions: dict[str, ast.FunctionDef], seen: frozenset[str], depth: int, item_vars: dict[str, str] | None=None, direct_env: dict[str, str] | None=None, call_env: dict[str, str] | None=None, top_level: bool=True) -> None:
    item_vars = dict(item_vars or {})
    direct_env = dict(direct_env or {})
    call_env = dict(call_env or {})
    for statement in stmts:
        for node in ast.walk(statement):
            _record_identity_carrier(node, var, scope, item_vars)
            if scope.closed_field_set is None:
                scope.closed_field_set = _closed_field_set(node, var, constants)
            _follow_call(node, var, scope=scope, constants=constants, functions=functions, seen=seen, depth=depth)
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            for name, value in _assignment_pairs(statement):
                keys = _keys_of(value, var, env)
                env[name] = keys
                resolved = _eval_default(value, var, defaults)
                defaults[name] = resolved
                if _direct_key(value, var, direct_env) is not None:
                    direct_env[name] = _direct_key(value, var, direct_env)
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                    call_env[name] = value.func.id
                if len(keys) == 1 and resolved is not _UNRESOLVED:
                    scope.defaults.setdefault(next(iter(keys)), resolved)
            continue
        if isinstance(statement, ast.If):
            is_refusal, message = _refusal_message(statement.body)
            if is_refusal and message is None:
                message = _sampled_refusal(statement.body, call_env)
            if is_refusal:
                atoms = _atoms(statement.test)
                guard = next((guarded for guarded in map(_kind_guard, atoms) if guarded), None)
                if message is not None:
                    scope.note_refusal(message)
                for atom in atoms:
                    category, keys, domain = _classify_atom(atom, var, env, constants)
                    scope.touched_by_refusal |= keys
                    if len(keys) != 1:
                        continue
                    if message is not None:
                        scope.add_refusal(next(iter(keys)), message)
                    if not top_level:
                        continue
                    key = next(iter(keys))
                    if category == 'presence':
                        if guard is None:
                            scope.presence.add(key)
                        else:
                            scope.presence_when.setdefault(key, f'kind == "{guard}"')
                    elif category == 'domain' and domain is not None:
                        scope.domains.setdefault(key, domain)
            _dataflow(statement.body, var, dict(env), dict(defaults), scope=scope, constants=constants, functions=functions, seen=seen, depth=depth, item_vars=item_vars, direct_env=direct_env, call_env=call_env, top_level=False)
            _dataflow(statement.orelse, var, dict(env), dict(defaults), scope=scope, constants=constants, functions=functions, seen=seen, depth=depth, item_vars=item_vars, direct_env=direct_env, call_env=call_env, top_level=False)
            continue
        if isinstance(statement, ast.For):
            label = _item_label(statement, var, direct_env)
            item_name = _item_variable(statement)
            if label is not None and item_name is not None:
                nested = scope.items.setdefault(label, _Scope())
                item_vars[item_name] = label
                _analyze(statement.body, item_name, scope=nested, constants=constants, functions=functions, seen=seen, depth=depth)
            _dataflow(statement.body, var, dict(env), dict(defaults), scope=scope, constants=constants, functions=functions, seen=seen, depth=depth, item_vars=item_vars, direct_env=direct_env, call_env=call_env, top_level=False)
            continue
        if isinstance(statement, ast.Try):
            for handler in statement.handlers:
                _is_refusal, message = _refusal_message(handler.body)
                if _is_refusal and message is None:
                    message = _sampled_refusal(handler.body, call_env)
                if message is None:
                    continue
                scope.note_refusal(message)
                for node in statement.body:
                    keys = _keys_of(node, var, env)
                    scope.touched_by_refusal |= keys
                    if len(keys) == 1:
                        scope.add_refusal(next(iter(keys)), message)
        for field in ('body', 'orelse', 'finalbody'):
            nested_body = getattr(statement, field, None)
            if isinstance(nested_body, list) and nested_body and isinstance(nested_body[0], ast.stmt):
                _dataflow(nested_body, var, dict(env), dict(defaults), scope=scope, constants=constants, functions=functions, seen=seen, depth=depth, item_vars=item_vars, direct_env=direct_env, call_env=call_env, top_level=False)

def _closed_field_set(node: ast.AST, var: str, constants: dict[str, Any]) -> str | None:
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)):
        return None
    left, right = (node.left, node.right)
    if not (isinstance(left, ast.Call) and isinstance(left.func, ast.Name)):
        return None
    if left.func.id != 'set' or len(left.args) != 1:
        return None
    if not (isinstance(left.args[0], ast.Name) and left.args[0].id == var):
        return None
    if isinstance(right, ast.Name) and right.id in constants:
        return right.id
    return None

def _item_variable(statement: ast.For) -> str | None:
    target = statement.target
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Tuple) and len(target.elts) == 2:
        second = target.elts[1]
        if isinstance(second, ast.Name):
            return second.id
    return None

def _item_label(statement: ast.For, var: str, direct_env: dict[str, str]) -> str | None:
    iterator = statement.iter
    if isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name) and (iterator.func.id == 'enumerate') and iterator.args:
        iterator = iterator.args[0]
    key = _direct_key(iterator, var, direct_env)
    if key is None:
        return None
    return f'{key}[]'

def _follow_call(node: ast.AST, var: str, *, scope: _Scope, constants: dict[str, Any], functions: dict[str, ast.FunctionDef], seen: frozenset[str], depth: int) -> None:
    if depth >= _MAX_FOLLOW_DEPTH:
        return
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return
    name = node.func.id
    if name in seen or name not in functions:
        return
    target = functions[name]
    parameter = _parameter_bound_to(node, target, var)
    if parameter is None:
        return
    _analyze(target.body, parameter, scope=scope, constants=constants, functions=functions, seen=seen | {name}, depth=depth + 1)

def _parameter_bound_to(call: ast.Call, target: ast.FunctionDef, var: str) -> str | None:
    names = [argument.arg for argument in target.args.args]
    for index, argument in enumerate(call.args):
        if isinstance(argument, ast.Name) and argument.id == var:
            if index < len(names):
                return names[index]
    for keyword in call.keywords:
        if isinstance(keyword.value, ast.Name) and keyword.value.id == var:
            if keyword.arg:
                return keyword.arg
    return None

def _kind_branches(expander: ast.FunctionDef) -> tuple[list[tuple[str, ast.If]], list[ast.stmt], ast.For]:
    loop = next((node for node in ast.walk(expander) if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple)))
    prelude: list[ast.stmt] = []
    chain: ast.If | None = None
    for statement in loop.body:
        if isinstance(statement, ast.If) and _kind_guard(statement.test):
            chain = statement
            break
        prelude.append(statement)
    if chain is None:
        raise ValueError('expand_blocks 里找不到 kind 分支链')
    branches: list[tuple[str, ast.If]] = []
    node: ast.stmt | None = chain
    while isinstance(node, ast.If):
        kind = _kind_guard(node.test)
        if kind is None:
            break
        branches.append((kind, node))
        node = node.orelse[0] if len(node.orelse) == 1 else None
    return (branches, prelude, loop)

def _unknown_kind_refusal(branches: list[tuple[str, ast.If]]) -> str | None:
    if not branches:
        return None
    _kind, last = branches[-1]
    _is_refusal, message = _refusal_message(last.orelse)
    return message

def _tail_calls(loop: ast.For, chain_kinds: set[str]) -> list[ast.stmt]:
    tail: list[ast.stmt] = []
    passed = False
    for statement in loop.body:
        if not passed:
            if isinstance(statement, ast.If) and _kind_guard(statement.test) in chain_kinds:
                passed = True
            continue
        tail.append(statement)
    return tail

def _requirement(key: str, scope: _Scope) -> str:
    if key in scope.presence:
        return 'required'
    if key in scope.domains:
        default = scope.defaults.get(key, _UNRESOLVED)
        if default is _UNRESOLVED or default not in scope.domains[key]:
            return 'required'
        return 'optional'
    if key in scope.touched_by_refusal or scope.refusals.get(key):
        return 'checked'
    return 'optional'

def _render_fields(scope: _Scope) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in sorted(scope.consulted):
        entry: dict[str, Any] = {'requirement': _requirement(key, scope)}
        default = scope.defaults.get(key, _UNRESOLVED)
        if default is not _UNRESOLVED and default not in (None, ''):
            entry['default'] = default
        if key in scope.domains:
            entry['domain'] = scope.domains[key]
        guards = {guard for guard in scope.consulted[key] if guard}
        if guards and len(guards) == 1 and (None not in scope.consulted[key]):
            entry['only_when_kind'] = sorted(guards)[0]
        if key in scope.presence_when and key not in scope.presence:
            entry['required_when'] = scope.presence_when[key]
        if scope.refusals.get(key):
            entry['refusals'] = scope.refusals[key]
        fields[key] = entry
    return fields

def _identity_carrier(kind: str, scope: _Scope, constants: dict[str, Any]) -> dict[str, Any]:
    block_kinds = set(constants.get('_ASSERTION_ID_BLOCK_KINDS') or ())
    forbidden = set(constants.get('_NO_ASSERTION_ID_KINDS') or ())
    carriers = set(scope.identity_carriers)
    if kind in block_kinds:
        carriers.add('block')
    entry: dict[str, Any] = {'carrier': sorted(carriers) or ['none'], 'block_level_refused': kind in forbidden}
    if kind in block_kinds:
        entry['note'] = 'this combinator synthesizes exactly one assertion, so block level IS assertion level'
    if kind == 'STEP':
        entry['only_when'] = 'E == check_point'
    return entry

def _ssl_standard_library_kind(root: Path, *, identity_constants: dict[str, Any]) -> dict[str, Any]:
    source = root / SSL_SOURCE_RELPATH
    tree = ast.parse(source.read_text(encoding='utf-8'))
    constants = _module_constants(tree)
    functions = _module_functions(tree)
    expander = functions['ssl_certificate_load_blocks']
    from cex_core.engine.case_compiler.excel_capability_samples import certified_ssl_release_fixture
    certified_default = certified_ssl_release_fixture()
    scope = _Scope()
    _analyze(expander.body, 'block', scope=scope, constants=constants, functions=functions, seen=frozenset({'ssl_certificate_load_blocks'}), depth=0)
    entry: dict[str, Any] = {'fields': _render_fields(scope), 'refusals': scope.all_refusals, 'assertion_identity': _identity_carrier('SSL_CERT_LOAD', scope, identity_constants), 'preprocessor': 'main.ist_core.tools.device.emit_xlsx_tool.ssl_certificate_load_blocks', 'sealed_form': 'lowered CONFIG/STEP blocks', 'lifecycle': {'setup_position': 'after the bound virtual object is created and before its first TLS business observation', 'teardown_position': 'engine-deferred until after the final signed business assertion and before trailing dependent-object teardown, in LIFO order'}, 'certified_default': certified_default, 'certification_source_path': SSL_FIXTURE_SOURCE_RELPATH, 'certification_source_sha256': _sha256(root / SSL_FIXTURE_SOURCE_RELPATH), 'source_path': SSL_SOURCE_RELPATH, 'source_sha256': _sha256(source)}
    if scope.closed_field_set:
        closed_fields = sorted(constants[scope.closed_field_set])
        entry['closed_field_set'] = {'constant': scope.closed_field_set, 'fields': closed_fields}
        for field in closed_fields:
            entry['fields'].setdefault(field, {'requirement': 'optional'})
    entry['fields'].setdefault('host', {})['requirement'] = 'optional'
    entry['fields']['host'].setdefault('default', list(identity_constants.get('_DUT_HOSTS') or ['APV_0'])[0])
    for field, default in (('vhost_role', 'virtual'), ('activate_index', 1)):
        entry['fields'].setdefault(field, {})['requirement'] = 'optional'
        entry['fields'][field].setdefault('default', default)
    for field in ('cert_group', 'pairs', 'rootca_file'):
        entry['fields'].setdefault(field, {})['requirement'] = 'optional'
        entry['fields'][field]['default_source'] = 'certified_default'
    for label in sorted(scope.items):
        item = scope.items[label]
        item_entry: dict[str, Any] = {'fields': _render_fields(item), 'refusals': item.all_refusals, 'assertion_identity': {'carrier': ['none']}}
        if item.closed_field_set:
            item_closed_fields = sorted(constants[item.closed_field_set])
            item_entry['closed_field_set'] = {'constant': item.closed_field_set, 'fields': item_closed_fields}
            for field in item_closed_fields:
                item_entry['fields'].setdefault(field, {'requirement': 'optional'})
        if label == 'pairs[]':
            item_entry['fields'].setdefault('index', {})['requirement'] = 'optional'
            item_entry['fields']['index'].setdefault('default', 1)
        entry.setdefault('items', {})[label] = item_entry
    return entry

def build_blocks_schema(root: Path=ROOT) -> dict[str, Any]:
    source = root / SOURCE_RELPATH
    tree = ast.parse(source.read_text(encoding='utf-8'))
    constants = _module_constants(tree)
    functions = _module_functions(tree)
    expander = functions['expand_blocks']
    branches, prelude, loop = _kind_branches(expander)
    chain_kinds = {kind for kind, _ in branches}
    common = _Scope()
    _analyze(prelude, 'b', scope=common, constants=constants, functions=functions, seen=frozenset({'expand_blocks'}), depth=0)
    common.presence.add('kind')
    common.domains['kind'] = sorted(chain_kinds)
    unknown_kind = _unknown_kind_refusal(branches)
    if unknown_kind:
        common.add_refusal('kind', unknown_kind)
    binding = _Scope()
    _analyze(_tail_calls(loop, chain_kinds), 'b', scope=binding, constants=constants, functions=functions, seen=frozenset({'expand_blocks'}), depth=0)
    kinds: dict[str, Any] = {}
    for kind, node in branches:
        scope = _Scope()
        _analyze(node.body, 'b', scope=scope, constants=constants, functions=functions, seen=frozenset({'expand_blocks'}), depth=0)
        entry: dict[str, Any] = {'fields': _render_fields(scope), 'refusals': scope.all_refusals, 'assertion_identity': _identity_carrier(kind, scope, constants)}
        if scope.closed_field_set:
            entry['closed_field_set'] = {'constant': scope.closed_field_set, 'fields': sorted(constants[scope.closed_field_set])}
        for label in sorted(scope.items):
            item = scope.items[label]
            entry.setdefault('items', {})[label] = {'fields': _render_fields(item), 'refusals': item.all_refusals, 'assertion_identity': {'carrier': ['entry'] if item.identity_carriers else ['none']}}
        kinds[kind] = entry
    timeout_guard = functions['_command_timeout_error'].body[1]
    if not (isinstance(timeout_guard, ast.If) and isinstance(timeout_guard.test, ast.Compare) and isinstance(timeout_guard.test.ops[0], ast.NotIn) and (_str_const(timeout_guard.test.left) == 'timeout_s') and isinstance(timeout_guard.body[0], ast.Return) and isinstance(timeout_guard.body[0].value, ast.Constant) and (timeout_guard.body[0].value.value is None)):
        raise ValueError('timeout_s optionality guard is no longer derivable')
    timeout_refusals = [_render_text(node.value) for node in ast.walk(functions['_timeout_command_error']) if isinstance(node, ast.Return) and _render_text(node.value)]
    for kind in ('CONFIG', 'STEP'):
        field = kinds[kind]['fields'].setdefault('timeout_s', {'requirement': 'optional'})
        field.update({'requirement': 'optional', 'type': 'integer', 'boolean_allowed': False, 'minimum': constants['COMMAND_TIMEOUT_MIN_S'], 'maximum': constants['COMMAND_TIMEOUT_MAX_S'], 'description': 'Per-command response read window in seconds. CONFIG emits one cmd_config row per command. STEP requires an APV cmd_config row. An existing timeout= argument conflicts with this field.'})
        field['refusals'] = list(dict.fromkeys(field.get('refusals', []) + timeout_refusals))
    kinds['SSL_CERT_LOAD'] = _ssl_standard_library_kind(root, identity_constants=constants)
    config_ref = kinds['CONFIG']['fields'].setdefault('ref', {'requirement': 'optional'})
    config_ref.update({'pipeline_requirement': 'required before submit/emit', 'description': 'Put the provenance pointer directly in CONFIG.ref, written as kind:locator (for example manual:<exact-root-relative-path>:<line>). Do not add a nested provenance/source object. Every command in one CONFIG block shares this ref; split the block when commands came from different sources.'})
    for observe_kind in ('OBSERVE_ASSERT', 'OBSERVE_EXIT', 'OBSERVE_ONLY'):
        cmd_ref = kinds[observe_kind]['fields'].setdefault('cmd_ref', {'requirement': 'optional'})
        cmd_ref.update({'pipeline_requirement': 'engine-derived for a validated test_env host', 'description': 'The observation-command provenance lives in cmd_ref. Omit it for a validated test_env host so the engine derives test_env_dispatch:lib/env.py#Env.<lowercase-host>; a non-empty explicit locator is cross-checked and is never silently rewritten.'})
    for observe_kind in ('OBSERVE_ASSERT', 'OBSERVE_EXIT'):
        answerer = kinds[observe_kind]['fields'].setdefault('answerer', {'requirement': 'optional'})
        answerer['requirement'] = 'optional'
        answerer.update({'pipeline_requirement': 'required by the answerer_statement submission gate whenever host is not one of the two devices under test', 'description': 'A traffic-driving observation (host outside the two devices under test) names who answers: {kind: "device", ref: <blocks[] index of the block that establishes the answering configuration on a device under test — a CONFIG combinator or an accounted generic STEP writing device configuration>}, {kind: "fixture", ref: <blocks[] index of the block that establishes the in-case fixture>}, or {kind: "bed_service", ref: <device name in the bed topology>}. When no source says who answers, write {kind: "undetermined", note: <one user-facing Chinese line>} — the submit boundary routes it as a typed user-decision claim instead of sealing. The gate checks presence and ref resolution only, never semantic correctness.'})
    exit_masking_refusal = constants.get('_EXIT_STATUS_MASKING_REFUSAL')
    if isinstance(exit_masking_refusal, str) and exit_masking_refusal:
        exit_cmd = kinds['OBSERVE_EXIT']['fields'].setdefault('cmd', {'requirement': 'required'})
        exit_cmd.setdefault('refusals', []).append(exit_masking_refusal)
        exit_cmd['description'] = "The shell expression must expose the observed action's own exit status. A direct command is preferred; && is allowed only when every command in the conjunction must succeed."
        if exit_masking_refusal not in kinds['OBSERVE_EXIT']['refusals']:
            kinds['OBSERVE_EXIT']['refusals'].append(exit_masking_refusal)
    from cex_core.engine.case_compiler.apv_lang import observe_exit_channel_error
    exit_host = kinds['OBSERVE_EXIT']['fields'].setdefault('host', {'requirement': 'required'})
    exit_host['description'] = 'A shell host reached through test_env (routera / routerb / server*). APV_0 / APV_1 are refused at expansion: the framework sends the G cell verbatim to the product CLI, so there is no exit-status channel on a device under test — observe a product command with OBSERVE_ASSERT (found / abs_found on its output) or put the configuration in CONFIG.'
    exit_host_refusal = observe_exit_channel_error('APV_0')
    exit_host.setdefault('refusals', []).append(exit_host_refusal)
    if exit_host_refusal not in kinds['OBSERVE_EXIT']['refusals']:
        kinds['OBSERVE_EXIT']['refusals'].append(exit_host_refusal)
    exit_expect = kinds['OBSERVE_EXIT']['fields'].setdefault('expect', {'requirement': 'required'})
    exit_expect['description'] = "success asserts the engine-owned IST_EXIT_STATUS marker equals 0: the probe completed an exchange with the target, i.e. reachability. failure asserts the marker is one of the probe tool's documented transport-failure exit codes (grammar section probe_tools.transport_failure_exit_codes): the target did not answer. Under this reading an answered refusal (an HTTP error status, a device error line) is reachability, not failure; assert such outcomes with OBSERVE_ASSERT on the actual feedback instead. failure is refused when the probe tool is outside that table, when the command is an && conjunction, when the target is not an IP literal, or when the executor has no declared topology path to the target."
    assertion_ref = kinds['OBSERVE_ASSERT'].setdefault('items', {}).setdefault('asserts[]', {'fields': {}}).setdefault('fields', {}).setdefault('ref', {'requirement': 'optional'})
    assertion_ref.update({'pipeline_requirement': 'required before submit/emit', 'description': 'The expected-value authority pointer lives directly in asserts[].ref; Author claims use the exact intent:<expectation_id> minted by the contract card. Device output never signs expected.'})
    distribution_source = root / DISTRIBUTION_SOURCE_RELPATH
    distribution_contract = _module_constants(ast.parse(distribution_source.read_text(encoding='utf-8')))['DISTRIBUTION_DECLARATION_CONTRACT']
    kinds['OBSERVE_DIST']['lowering_contract'] = {'source_path': DISTRIBUTION_SOURCE_RELPATH, 'source_sha256': _sha256(distribution_source), **distribution_contract}
    kinds['OBSERVE_DIST']['fields']['field']['description'] = distribution_contract['field']
    kinds['OBSERVE_DIST']['fields']['total']['description'] = distribution_contract['sampling']
    kinds['OBSERVE_DIST'].setdefault('items', {}).setdefault('buckets[]', {'fields': {}})['fields']['pattern'] = {'requirement': 'optional', 'type': 'string', 'description': distribution_contract['bucket_pattern']}
    common.domains['kind'] = sorted(kinds)
    closed_sets = {name: sorted(value) for name, value in sorted(constants.items()) if name in {'_ASSERT_OPS', '_DUT_HOSTS', '_STEP_FIELDS', '_ASSERTION_ID_FIELDS', '_EXIT_STATUS_EXPECTS', '_ANSWERER_KINDS', '_ANSWERER_FIELD_KEYS', '_ASSERTION_ID_BLOCK_KINDS', '_NO_ASSERTION_ID_KINDS', '_REF_KINDS', '_REF_LOCATOR_REQUIRED'}}
    closed_sets['kinds'] = sorted(kinds)
    payload = {'schema': SCHEMA, '_meta': {'generator': 'scripts/gen_blocks_schema.py', 'expander': EXPANDER, 'source_path': source.relative_to(root).as_posix(), 'source_sha256': _sha256(source), 'standard_library_sources': [{'path': SSL_SOURCE_RELPATH, 'sha256': _sha256(root / SSL_SOURCE_RELPATH), 'kinds': ['SSL_CERT_LOAD']}, {'path': SSL_FIXTURE_SOURCE_RELPATH, 'sha256': _sha256(root / SSL_FIXTURE_SOURCE_RELPATH), 'kinds': ['SSL_CERT_LOAD:certified_default']}], 'scope': SCOPE_NOTE, 'requirement_semantics': REQUIREMENT_NOTE}, 'closed_sets': closed_sets, 'common_fields': _render_fields(common), 'binding_fields': _render_fields(binding), 'kinds': kinds, 'mechanical_case_envelope': _envelope_section(root), 'consistency_contract': _consistency_contract_section(root)}
    rendered = json.dumps(payload, ensure_ascii=False)
    for producer, sampler in _REFUSAL_SAMPLERS.items():
        if sampler() not in rendered:
            raise ValueError(f'{producer} 的拒绝例句没进投影：它在 {EXPANDER} 里的承载形态变了，生成器的回溯要跟着改（或该样例已不再是拒绝）')
    return payload

def _envelope_section(root: Path) -> dict[str, Any]:
    import sys
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    from cex_core.engine.case_compiler import mechanical_case as mc
    envelope_source = root / 'main/case_compiler/mechanical_case.py'
    return {'schema_id': mc.MECHANICAL_CASE_SCHEMA, 'source_path': 'main/case_compiler/mechanical_case.py', 'source_sha256': _sha256(envelope_source), 'top_level_keys': list(mc.MECHANICAL_CASE_KEYS), 'submission_body_keys': sorted(mc.MECHANICAL_CASE_BODY_KEYS), 'submission_engine_stamped_binding_fields': ['contract_sha256', 'consistency_contract_sha256', 'mindmap_source_sha256', 'capability_generation_id', 'capability_projection_sha256', 'authored_round'], 'submission_note': 'submit_mechanical_case takes exactly the body keys listed in submission_body_keys as one native object. `schema` is the constant in schema_id; `autoid` is the 18-digit identity of the dispatched case. Never include `seal`: the engine mints it from its own dry run after the submission rules pass, and a self-reported seal is rejected. Pass binding as an empty object. Every field listed in submission_engine_stamped_binding_fields is engine-owned and the submission boundary stamps it from the trusted dispatch; a non-empty caller value is only an exact cross-check and a mismatch is rejected. The inner legality of blocks[] entries is specified by the `kinds` section of this same file.', 'json_schema': mc.MechanicalCase.model_json_schema(by_alias=True)}

def _consistency_contract_section(root: Path) -> dict[str, Any]:
    import sys
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    from cex_core.engine.case_compiler import consistency_contract as cc
    source_path = 'main/case_compiler/consistency_contract.py'
    return {'schema_id': cc.CONSISTENCY_CONTRACT_SCHEMA, 'source_path': source_path, 'source_sha256': _sha256(root / source_path), 'spec_endorsement': {'schema_id': cc.SPEC_ENDORSEMENT_SCHEMA, 'expectation_scope_binding': cc.spec_endorsement_expectation_binding_rule()}}

def write_blocks_schema(output: Path=DEFAULT_OUTPUT, *, root: Path=ROOT) -> dict[str, Any]:
    payload = build_blocks_schema(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')
    return payload

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.check:
        rendered = json.dumps(build_blocks_schema(), ensure_ascii=False, indent=2, sort_keys=False) + '\n'
        if not args.output.is_file() or args.output.read_text(encoding='utf-8') != rendered:
            print('blocks_schema projection is stale')
            return 1
    else:
        write_blocks_schema(args.output)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
