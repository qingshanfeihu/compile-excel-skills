# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/case_ir.py（sha256 3f5ab045668d6632）。不在这里手改。
from __future__ import annotations
import ast
from dataclasses import dataclass, field
import hashlib
import re
from string import Formatter
from typing import Any, Optional
from cex_core.engine.case_compiler.excel_contract import ExcelContractError, contract_entry, enabled_fs_by_e, load_excel_contract, parse_g_arguments
from cex_core.engine.knowledge_paths import KNOWLEDGE_FRAMEWORK_MIRROR
_CONTRACT_WHITELIST_SLOTS: dict[str, int] = {'VALID_TEST_OBJECTS': 0, 'VALID_CHECK_METHODS': 1, 'VALID_TEST_ENV_HOSTS': 2, 'VALID_APV_METHODS': 3}

def _contract_whitelists() -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    contract = load_excel_contract()
    enabled = enabled_fs_by_e(contract)
    objects = {str(item['e']) for item in contract['objects']}
    return (frozenset(objects), frozenset(enabled.get('check_point', ())), frozenset(enabled.get('test_env', ())), frozenset(enabled.get('APV_0', ())))

def __getattr__(name: str) -> frozenset[str]:
    slot = _CONTRACT_WHITELIST_SLOTS.get(name)
    if slot is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    values = _contract_whitelists()
    globals().update({attribute: values[index] for attribute, index in _CONTRACT_WHITELIST_SLOTS.items()})
    return values[slot]

def __dir__() -> list[str]:
    return sorted({*globals(), *_CONTRACT_WHITELIST_SLOTS})

class IInjectionSyntaxError(ValueError):

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
_STATIC_INJECTION_PLACEHOLDER_RE = re.compile('(?<!\\{)\\{(?:0)?\\}(?!\\})')

def _runtime_static_literal_braces_supported() -> bool:
    try:
        contract = load_excel_contract()
        expected_sha = str((contract.get('runtime') or {}).get('runner_sha256') or '')
        path = KNOWLEDGE_FRAMEWORK_MIRROR / 'lib/test_xlsx.py'
        raw = path.read_bytes()
        if not expected_sha or hashlib.sha256(raw).hexdigest() != expected_sha:
            return False
        tree = ast.parse(raw.decode('utf-8'), filename='<sealed-excel-runner>')
    except (OSError, UnicodeError, SyntaxError, TypeError, ValueError):
        return False
    function = next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == '_validate_call_placeholders'), None)
    if function is None:
        return False
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    first = body[0] if body else None
    return bool(isinstance(first, ast.If) and isinstance(first.test, ast.UnaryOp) and isinstance(first.test.op, ast.Not) and isinstance(first.test.operand, ast.Name) and (first.test.operand.id == 'has_input') and first.body and isinstance(first.body[-1], ast.Return))

def _placeholder_fields(raw_value: Any, *, location: str) -> list[str]:
    if raw_value is None:
        return []
    try:
        parsed = list(Formatter().parse(str(raw_value)))
    except ValueError as exc:
        raise IInjectionSyntaxError('format', f'{location} contains unpaired placeholder braces') from exc
    fields: list[str] = []
    for _literal, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in ('', '0') or format_spec or conversion:
            shown = '{}' if field_name == '' else '{' + field_name + '}'
            raise IInjectionSyntaxError('format', f'{location} contains unsupported placeholder {shown}; only exact {{}} or {{0}} is allowed')
        fields.append(field_name)
    if '' in fields and len(fields) > 1:
        raise IInjectionSyntaxError('format', f'{location} automatic placeholder {{}} may appear once and cannot mix with {{0}}')
    return fields

def validate_i_injection_syntax(g_value: Any, i_value: Any, method: str) -> None:
    args, kwargs = parse_g_arguments(g_value, method)
    has_input = i_value is not None and bool(str(i_value).strip())
    if not has_input:
        static_values = [*args, *kwargs.values()]
        if any((_STATIC_INJECTION_PLACEHOLDER_RE.search(str(value or '')) for value in static_values)):
            raise IInjectionSyntaxError('scope', 'G contains an exact {} or {0} injection placeholder but column I is blank')
        if _runtime_static_literal_braces_supported():
            return
        for index, value in enumerate(args, start=1):
            _placeholder_fields(value, location=f'G positional argument {index}')
        for key, value in kwargs.items():
            _placeholder_fields(value, location=f'G keyword argument {key!r}')
        return
    positional_fields = [_placeholder_fields(value, location=f'G positional argument {index}') for index, value in enumerate(args, start=1)]
    keyword_fields = {key: _placeholder_fields(value, location=f'G keyword argument {key!r}') for key, value in kwargs.items()}
    if any(positional_fields[1:]) or any(keyword_fields.values()):
        raise IInjectionSyntaxError('scope', 'G placeholders are allowed only in the first positional argument')
    first = positional_fields[0] if positional_fields else []
    if not args:
        raise IInjectionSyntaxError('missing', 'I injection requires G to provide a first positional argument')
    if not first:
        raise IInjectionSyntaxError('missing', 'I injection requires the first positional argument to contain {} or {0}')

def parse_found_times_cells(g_value: Any, h_value: Any, i_value: Any) -> tuple[str, int]:
    expected = '' if g_value is None else str(g_value)
    if not expected.strip():
        raise ValueError('found_times requires a static expected regex in column G')
    if h_value is not None and str(h_value).strip():
        raise ValueError('found_times requires column H to be blank')
    count_text = '' if i_value is None else str(i_value).strip()
    try:
        count = int(count_text)
    except ValueError as exc:
        raise ValueError('found_times requires column I to be a positive integer count') from exc
    if count <= 0 or str(count) != count_text:
        raise ValueError('found_times requires column I to be a positive integer count')
    return (expected, count)

@dataclass
class Row:
    test_object: str = ''
    method: str = ''
    data: str = ''
    save_as: Optional[str] = None
    input_var: Optional[str] = None
    provenance: Optional[str] = None

    def is_check_point(self) -> bool:
        return self.test_object == 'check_point'

@dataclass
class Step:
    stmt_type: int
    description: str
    rows: list[Row] = field(default_factory=list)

@dataclass
class CaseIR:
    autoid: str
    priority: str = 'P1'
    title: str = ''
    steps: list[Step] = field(default_factory=list)
    source_module: str = ''
    source_text: str = ''
    expected: list[str] = field(default_factory=list)
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)
    is_passthrough: bool = False

    def check_point_count(self) -> int:
        return sum((1 for st in self.steps for r in st.rows if r.is_check_point()))

@dataclass
class FileIR:
    feature: str
    author: str = 'IST-Core'
    init_rows: list[Row] = field(default_factory=list)
    cases: list[CaseIR] = field(default_factory=list)
    module: str = ''
    rejected: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)

def _effective_whitelists(snapshot=None) -> tuple[set, set, set]:
    _objects, checks, hosts, generic = _contract_whitelists()
    return (checks, hosts, generic)

def validate_row(row: Row) -> list[str]:
    errs: list[str] = []
    e = str(row.test_object or '').strip()
    f = str(row.method or '').strip()
    try:
        contract = load_excel_contract()
    except ExcelContractError as exc:
        return [f'Excel function contract is unavailable; row cannot be validated: {exc}']
    entry = contract_entry(e, f, contract)
    if entry is None:
        object_names = {str(item['e']) for item in contract['objects']}
        if e not in object_names:
            errs.append(f'E={e!r} is not a valid test object')
        else:
            errs.append(f'F={f!r} is not declared for E={e!r}')
        return errs
    if entry['status'] != 'enabled':
        errs.append(f"E={e!r}, F={f!r} is {entry['status']}: {entry['reason']}")
        return errs
    if e == 'check_point' and f == 'found_times':
        try:
            parse_found_times_cells(row.data, row.save_as, row.input_var)
        except ValueError as exc:
            errs.append(str(exc))
    try:
        from cex_core.engine.case_compiler.excel_contract import validate_g_for_entry
        validate_g_for_entry(entry, str(row.data or ''), contract)
    except (ExcelContractError, ValueError) as exc:
        errs.append(f'E={e!r}, F={f!r} has invalid G syntax: {exc}')
    else:
        if e != 'check_point':
            try:
                validate_i_injection_syntax(row.data, row.input_var, f)
            except (ExcelContractError, IInjectionSyntaxError) as exc:
                errs.append(f'E={e!r}, F={f!r} has invalid I injection syntax: {exc}')
    return errs

def validate_case(case: CaseIR) -> list[str]:
    errs: list[str] = []
    if case.check_point_count() == 0:
        errs.append(f'case {case.autoid} has no check_point — guaranteed fail on device (pass requires success>0)')
    for st in case.steps:
        for r in st.rows:
            for e in validate_row(r):
                errs.append(f'case {case.autoid} step C={st.stmt_type}: {e}')
    return errs
