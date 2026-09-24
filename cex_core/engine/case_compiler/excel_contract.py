# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/excel_contract.py（sha256 ee81243ff0546430）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import hashlib
import json
import re
import threading
import copy
from collections.abc import Iterator, Mapping as AbcMapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from cex_core.engine.case_compiler.config import XlsxLayout
from cex_core.engine.common.schema_identity import accepts_schema as _accepts_schema
from cex_core.engine.case_compiler._sealed_io import read_regular_nofollow, stat_regular_nofollow, validate_json_budget, validate_xlsx_zip_budget
SCHEMA = 'ist.excel.function-contract'
EXECUTION_HEADERS = ('自动化ID', '优先级', '语句类型', '描述', '测试对象', '方法', '数据', '临时保存期望结果', '输入变量')
EXECUTION_SHEET_MARKER = 'IST_EXECUTION_SHEET'
CONTRACT_MARKER = 'IST_EXCEL_CONTRACT'
_ROOT = _cex_data_path('')
_MIRROR_ROOT = _ROOT / 'knowledge/framework/mirror'
_DEFAULT_PATH = _ROOT / 'knowledge/data/compile_ref/excel_contract.json'
_DEFAULT_TEMPLATE_PATH = _ROOT / 'knowledge/data/compile_ref/excel_runtime_template.xlsx'
_DEFAULT_MANIFEST_PATH = _ROOT / 'knowledge/data/compile_ref/excel_workbook_manifest.json'
_STATUS = frozenset({'enabled', 'disabled', 'internal'})
_ENTRY_FIELDS = frozenset({'e', 'f', 'python_symbol', 'signature', 'g_syntax', 'h_semantics', 'i_semantics', 'dispatch', 'status', 'reason', 'source', 'minimum_runtime', 'status_authority'})

class ExcelContractError(ValueError):
    pass

class _ReadOnlyMapping(AbcMapping):
    __slots__ = ('__data',)

    def __init__(self, value: Mapping[str, Any]) -> None:
        self.__data = MappingProxyType({key: _freeze_value(item) for key, item in value.items()})

    def __getitem__(self, key):
        return self.__data[key]

    def __iter__(self) -> Iterator:
        return iter(self.__data)

    def __len__(self) -> int:
        return len(self.__data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AbcMapping):
            return dict(self.items()) == dict(other.items())
        return False

    def __repr__(self) -> str:
        return repr(dict(self))

    def __deepcopy__(self, memo):
        return {copy.deepcopy(key, memo): copy.deepcopy(value, memo) for key, value in self.items()}

class _ReadOnlySequence(Sequence):
    __slots__ = ('__data',)

    def __init__(self, value) -> None:
        self.__data = tuple((_freeze_value(item) for item in value))

    def __getitem__(self, index):
        return self.__data[index]

    def __len__(self) -> int:
        return len(self.__data)

    def __iter__(self) -> Iterator:
        return iter(self.__data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Sequence) and (not isinstance(other, (str, bytes, bytearray))):
            return list(self) == list(other)
        return False

    def __repr__(self) -> str:
        return repr(list(self))

    def __deepcopy__(self, memo):
        return [copy.deepcopy(value, memo) for value in self]

class ValidatedExcelContract(AbcMapping):
    __slots__ = ('__data', '__mutable')

    def __init__(self, value: Mapping[str, Any], *, mutable: bool=True) -> None:
        self.__mutable = mutable
        self.__data = dict(value) if mutable else MappingProxyType({key: _freeze_value(item) for key, item in value.items()})

    def __getitem__(self, key):
        return self.__data[key]

    def __iter__(self) -> Iterator:
        return iter(self.__data)

    def __len__(self) -> int:
        return len(self.__data)

    def __setitem__(self, key, value) -> None:
        if not self.__mutable:
            raise TypeError('validated Excel contract is immutable')
        self.__data[key] = value

    def update(self, *args, **kwargs) -> None:
        if not self.__mutable:
            raise TypeError('validated Excel contract is immutable')
        self.__data.update(*args, **kwargs)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AbcMapping):
            return dict(self.items()) == dict(other.items())
        return False

    def __deepcopy__(self, memo):
        return {copy.deepcopy(key, memo): copy.deepcopy(value, memo) for key, value in self.items()}

def _freeze_value(value: Any) -> Any:
    if isinstance(value, AbcMapping):
        return _ReadOnlyMapping(value)
    if isinstance(value, Sequence) and (not isinstance(value, (str, bytes, bytearray))):
        return _ReadOnlySequence(value)
    return value

def _plain_value(value: Any) -> Any:
    if isinstance(value, AbcMapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and (not isinstance(value, (str, bytes, bytearray))):
        return [_plain_value(item) for item in value]
    return value

def _freeze_contract(value: Mapping[str, Any]) -> ValidatedExcelContract:
    return ValidatedExcelContract(value, mutable=False)
_FileIdentity = tuple[int, int, int, int, int]
_SourceIdentities = tuple[tuple[str, _FileIdentity], ...]
_CONTRACT_CACHE: dict[str, tuple[_FileIdentity, _SourceIdentities, ValidatedExcelContract]] = {}
_CONTRACT_CACHE_LOCK = threading.RLock()
_CONTRACT_CACHE_MAX = 8
_CONTRACT_MAX_BYTES = 16 * 1024 * 1024
_SOURCE_MAX_BYTES = 64 * 1024 * 1024

def _manifest_project_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ExcelContractError(f'{label} manifest path is invalid')
    relative = Path(value)
    if relative.is_absolute() or any((part in {'', '.', '..'} for part in relative.parts)):
        raise ExcelContractError(f'{label} manifest path is invalid')
    candidate_raw = _ROOT
    for part in relative.parts:
        candidate_raw = candidate_raw / part
        if candidate_raw.is_symlink():
            raise ExcelContractError(f'{label} manifest target may not use symlinks')
    candidate = candidate_raw.resolve()
    try:
        candidate.relative_to(_ROOT.resolve())
    except ValueError as exc:
        raise ExcelContractError(f'{label} manifest path escapes the project') from exc
    if candidate.is_symlink() or not candidate.is_file():
        raise ExcelContractError(f'{label} manifest target is unavailable')
    return candidate

def load_validated_workbook_manifest_artifacts(manifest_path: str | Path | None=None, *, contract_path: str | Path | None=None, template_path: str | Path | None=None) -> tuple[dict[str, Any], bytes]:
    selected_manifest = Path(manifest_path) if manifest_path else _DEFAULT_MANIFEST_PATH
    try:
        manifest_bytes, _identity = _read_bound_file(selected_manifest, label='Excel workbook manifest', max_bytes=_CONTRACT_MAX_BYTES)
        validate_json_budget(manifest_bytes, error_type=ExcelContractError, message='Excel workbook manifest exceeds the JSON structure budget')
        manifest = json.loads(manifest_bytes.decode('utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise ExcelContractError('Excel workbook manifest is unavailable') from exc
    if not isinstance(manifest, dict) or not _accepts_schema(manifest.get('schema'), 'ist.excel.workbook-manifest'):
        raise ExcelContractError('Excel workbook manifest schema mismatch')
    contract_info = manifest.get('contract')
    runtime_info = manifest.get('runtime_template')
    review_info = manifest.get('ide_review_workbook')
    if not all((isinstance(item, dict) for item in (contract_info, runtime_info, review_info))):
        raise ExcelContractError('Excel workbook manifest is incomplete')
    manifest_contract = _manifest_project_path(contract_info.get('path'), label='contract')
    manifest_template = _manifest_project_path(runtime_info.get('path'), label='runtime template')
    manifest_review = _manifest_project_path(review_info.get('path'), label='IDE workbook')
    expected_contract = Path(contract_path).resolve() if contract_path else _DEFAULT_PATH.resolve()
    expected_template = Path(template_path).resolve() if template_path else _DEFAULT_TEMPLATE_PATH.resolve()
    if manifest_contract != expected_contract or manifest_template != expected_template:
        raise ExcelContractError('Excel workbook manifest targets an unexpected canonical artifact')
    try:
        contract_bytes, _contract_identity = _read_bound_file(manifest_contract, label='Excel function contract', max_bytes=_CONTRACT_MAX_BYTES)
        runtime_bytes, _runtime_identity = _read_bound_file(manifest_template, label='Excel runtime template', max_bytes=128 * 1024 * 1024)
        review_bytes, _review_identity = _read_bound_file(manifest_review, label='Excel IDE workbook', max_bytes=128 * 1024 * 1024)
        validate_json_budget(contract_bytes, error_type=ExcelContractError, message='Excel function contract exceeds the JSON structure budget')
        contract_payload = json.loads(contract_bytes.decode('utf-8'))
        contract = _validate_contract(contract_payload)
        validate_xlsx_zip_budget(runtime_bytes, error_type=ExcelContractError, message='Excel runtime template exceeds the XLSX expansion budget')
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise ExcelContractError('Excel workbook manifest artifact closure is unavailable') from exc
    if contract_info.get('canonical_sha256') != contract['contract_sha256'] or contract_info.get('runtime_version') != contract['runtime']['minimum_version'] or contract_info.get('file_sha256') != hashlib.sha256(contract_bytes).hexdigest() or (runtime_info.get('sha256') != hashlib.sha256(runtime_bytes).hexdigest()) or (review_info.get('sha256') != hashlib.sha256(review_bytes).hexdigest()) or (runtime_info.get('columns') != list(EXECUTION_HEADERS)) or (runtime_info.get('worksheets') != 1) or (review_info.get('entry_count') != len(contract['entries'])) or (review_info.get('execute_action_count') != len(contract['execute_actions'])):
        raise ExcelContractError('Excel workbook manifest SHA or contract identity mismatch')
    return (manifest, runtime_bytes)

def validate_workbook_manifest(manifest_path: str | Path | None=None, *, contract_path: str | Path | None=None, template_path: str | Path | None=None) -> dict[str, Any]:
    manifest, _runtime_bytes = load_validated_workbook_manifest_artifacts(manifest_path, contract_path=contract_path, template_path=template_path)
    return manifest

def _canonical_payload(contract: Mapping[str, Any]) -> bytes:
    body = _plain_value(contract)
    body.pop('contract_sha256', None)
    body.pop('generated_at', None)
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def contract_sha256(contract: Mapping[str, Any] | None=None) -> str:
    payload = load_excel_contract() if contract is None else contract
    return hashlib.sha256(_canonical_payload(payload)).hexdigest()

def _overlay_bytes(relative_path: str, source_overlays: Mapping[str, bytes | bytearray] | None) -> bytes | None:
    if not source_overlays or relative_path not in source_overlays:
        return None
    source = source_overlays[relative_path]
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    raise ExcelContractError(f'contract source overlay must be sealed bytes: {relative_path!r}')

def _source_sha256(relative_path: str, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> str:
    overlay = _overlay_bytes(relative_path, source_overlays)
    if overlay is not None:
        return hashlib.sha256(overlay).hexdigest()
    payload, _identity = _read_bound_file(_mirror_source_path(relative_path), label=f'contract source {relative_path!r}', max_bytes=_SOURCE_MAX_BYTES)
    return hashlib.sha256(payload).hexdigest()

def _mirror_source_path(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or any((part in {'', '.', '..'} for part in relative.parts)):
        raise ExcelContractError(f'source path escapes framework mirror: {relative_path!r}')
    return _MIRROR_ROOT / relative

def _bound_file_identity(path: Path, *, label: str, max_bytes: int) -> _FileIdentity:
    return stat_regular_nofollow(path, error_type=ExcelContractError, invalid_message=f'{label} path is invalid', directory_message=f'{label} parent is unavailable', open_message=f'{label} is unavailable', bounds_message=f'{label} must be a bounded single-link regular file', max_bytes=max_bytes, min_bytes=1)

def _read_bound_file(path: Path, *, label: str, max_bytes: int) -> tuple[bytes, _FileIdentity]:
    result = read_regular_nofollow(path, error_type=ExcelContractError, invalid_message=f'{label} path is invalid', directory_message=f'{label} parent is unavailable', open_message=f'{label} is unavailable', bounds_message=f'{label} must be a bounded single-link regular file', changed_message=f'{label} changed while being read', max_bytes=max_bytes, min_bytes=1, return_identity=True)
    assert isinstance(result, tuple)
    return result

def _source_identities(paths: tuple[str, ...]) -> _SourceIdentities:
    return tuple(((relative, _bound_file_identity(_mirror_source_path(relative), label=f'contract source {relative!r}', max_bytes=_SOURCE_MAX_BYTES)) for relative in paths))

def _read_source_closure(paths: tuple[str, ...]) -> tuple[dict[str, bytes], _SourceIdentities]:
    overlays: dict[str, bytes] = {}
    identities: list[tuple[str, _FileIdentity]] = []
    for relative in paths:
        payload, identity = _read_bound_file(_mirror_source_path(relative), label=f'contract source {relative!r}', max_bytes=_SOURCE_MAX_BYTES)
        overlays[relative] = payload
        identities.append((relative, identity))
    return (overlays, tuple(identities))

def clear_excel_contract_cache() -> None:
    with _CONTRACT_CACHE_LOCK:
        _CONTRACT_CACHE.clear()

def _validate_signature(signature: Any, pair: tuple[str, str]) -> None:
    if not isinstance(signature, dict):
        raise ExcelContractError(f'{pair!r} signature must be an object')
    parameters = signature.get('parameters')
    if not isinstance(parameters, list):
        raise ExcelContractError(f'{pair!r} signature.parameters must be a list')
    names: set[str] = set()
    for parameter in parameters:
        if not isinstance(parameter, dict):
            raise ExcelContractError(f'{pair!r} contains a malformed parameter')
        name = parameter.get('name')
        if not isinstance(name, str) or not name or name in names:
            raise ExcelContractError(f'{pair!r} contains a duplicate/empty parameter')
        names.add(name)
        if parameter.get('kind') not in {'positional_only', 'positional_or_keyword', 'var_positional', 'keyword_only', 'var_keyword'}:
            raise ExcelContractError(f'{pair!r} contains an unknown parameter kind')
        if not isinstance(parameter.get('required'), bool):
            raise ExcelContractError(f'{pair!r} parameter.required must be boolean')
        if 'default' not in parameter:
            raise ExcelContractError(f'{pair!r} parameter has no default-presence record')
        if parameter['required'] and parameter['default'] is not None:
            raise ExcelContractError(f'{pair!r} required parameter cannot have a default')
        if not parameter['required'] and parameter['kind'] not in {'var_positional', 'var_keyword'} and (not isinstance(parameter['default'], str)):
            raise ExcelContractError(f'{pair!r} optional parameter default must be serialized')

def _validate_contract(payload: Any, *, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> ValidatedExcelContract:
    if not isinstance(payload, dict):
        raise ExcelContractError('Excel function contract must be a JSON object')
    if not _accepts_schema(payload.get('schema'), SCHEMA):
        raise ExcelContractError(f"Excel function contract schema mismatch: {payload.get('schema')!r}")
    if payload.get('complete') is not True:
        raise ExcelContractError('Excel function contract is not complete')
    sources = payload.get('source_hashes')
    if not isinstance(sources, dict) or not sources:
        raise ExcelContractError('Excel function contract has no source hash closure')
    for relative_path, expected in sorted(sources.items()):
        if not isinstance(relative_path, str) or not re.fullmatch('[0-9a-f]{64}', str(expected)):
            raise ExcelContractError('Excel function contract contains a malformed source hash')
        actual = _source_sha256(relative_path, source_overlays)
        if actual != expected:
            raise ExcelContractError(f'Excel function contract source drift: {relative_path!r}')
    runtime = payload.get('runtime')
    if not isinstance(runtime, dict):
        raise ExcelContractError('Excel function contract has no runtime identity')
    if not _accepts_schema(runtime.get('minimum_version'), 'ist.excel.runtime'):
        raise ExcelContractError('Excel function contract runtime version mismatch')
    runner_source = runtime.get('runner_source')
    runner_sha = runtime.get('runner_sha256')
    if not isinstance(runner_source, str) or runner_source not in sources or (not re.fullmatch('[0-9a-f]{64}', str(runner_sha))) or (sources[runner_source] != runner_sha) or (not isinstance(runtime.get('found_times_supported'), bool)):
        raise ExcelContractError('Excel function contract runner identity is invalid')
    entries = payload.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ExcelContractError('Excel function contract has no entries')
    seen: set[tuple[str, str]] = set()
    certified_entry_count = 0
    source_paths = set(sources)
    for entry in entries:
        if not isinstance(entry, dict) or not _ENTRY_FIELDS <= entry.keys():
            raise ExcelContractError('Excel function contract contains a malformed entry')
        e, f = (entry.get('e'), entry.get('f'))
        if not isinstance(e, str) or not e or (not isinstance(f, str)) or (not f):
            raise ExcelContractError('Excel function contract contains an empty E/F value')
        pair = (e, f)
        if pair in seen:
            raise ExcelContractError(f'duplicate Excel function contract entry: {pair!r}')
        seen.add(pair)
        if entry.get('status') not in _STATUS:
            raise ExcelContractError(f'{pair!r} has an unknown status')
        if not isinstance(entry.get('reason'), str):
            raise ExcelContractError(f'{pair!r} reason must be a string')
        if not isinstance(entry.get('status_authority'), str) or not entry['status_authority']:
            raise ExcelContractError(f'{pair!r} has no status authority')
        if not isinstance(entry.get('python_symbol'), str) or not entry['python_symbol']:
            raise ExcelContractError(f'{pair!r} has no Python symbol')
        _validate_signature(entry.get('signature'), pair)
        source = entry.get('source')
        if not isinstance(source, dict) or source.get('path') not in source_paths or (not isinstance(source.get('line'), int)) or (source['line'] < 1):
            raise ExcelContractError(f'{pair!r} has invalid source provenance')
        for key in ('g_syntax', 'h_semantics', 'i_semantics', 'dispatch', 'minimum_runtime'):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise ExcelContractError(f'{pair!r} has an empty {key}')
        if entry['minimum_runtime'] != runtime['minimum_version']:
            raise ExcelContractError(f'{pair!r} runtime version does not match the contract')
        certification_candidate = entry.get('certification_candidate')
        if certification_candidate is not None:
            if certification_candidate is not True:
                raise ExcelContractError(f'{pair!r} has an invalid certification candidate flag')
            if entry['status'] == 'enabled':
                if not entry['status_authority'].startswith('device_receipt_set:'):
                    raise ExcelContractError(f'{pair!r} is enabled without a device certification authority')
                certified_entry_count += 1
            elif entry['status'] != 'disabled':
                raise ExcelContractError(f'{pair!r} certification candidate has an invalid status')
    found_times = next((entry for entry in entries if (entry['e'], entry['f']) == ('check_point', 'found_times')), None)
    if found_times is None or (found_times['status'] == 'enabled') != runtime['found_times_supported']:
        raise ExcelContractError('found_times status does not match the runner capability')
    objects = payload.get('objects')
    if not isinstance(objects, list) or not objects:
        raise ExcelContractError('Excel function contract has no object list')
    required_object_fields = {'e', 'python_type', 'mro', 'status', 'reason', 'status_authority', 'source'}
    object_names_list: list[str] = []
    for item in objects:
        if not isinstance(item, dict) or not required_object_fields <= item.keys():
            raise ExcelContractError('Excel function contract contains a malformed object')
        e_value = item.get('e')
        if not isinstance(e_value, str) or not e_value:
            raise ExcelContractError('Excel function contract contains an empty object name')
        object_names_list.append(e_value)
        if item.get('status') not in _STATUS or not isinstance(item.get('reason'), str):
            raise ExcelContractError(f"object {item.get('e')!r} has invalid status/reason")
        if not isinstance(item.get('status_authority'), str) or not item['status_authority']:
            raise ExcelContractError(f"object {item.get('e')!r} has no status authority")
        if not isinstance(item.get('python_type'), str) or not item['python_type'] or (not isinstance(item.get('mro'), list)) or any((not isinstance(name, str) or not name for name in item['mro'])):
            raise ExcelContractError(f"object {item.get('e')!r} has invalid Python type/MRO")
        source = item.get('source')
        if not isinstance(source, dict) or source.get('path') not in source_paths or (not isinstance(source.get('line'), int)) or (source['line'] < 1):
            raise ExcelContractError(f"object {item.get('e')!r} has invalid source provenance")
    object_names = set(object_names_list)
    if len(object_names) != len(object_names_list):
        raise ExcelContractError('Excel function contract contains a duplicate object')
    if {e for e, _ in seen} != object_names:
        raise ExcelContractError('Excel function contract object/entry closure mismatch')
    object_status = {item['e']: item['status'] for item in objects}
    leaked = sorted(((entry['e'], entry['f']) for entry in entries if object_status[entry['e']] == 'disabled' and entry['status'] == 'enabled'))
    if leaked:
        raise ExcelContractError(f'disabled object exposes enabled function entries: {leaked!r}')
    actions = payload.get('execute_actions')
    if not isinstance(actions, list):
        raise ExcelContractError('Excel function contract execute_actions must be a list')
    action_keys: set[tuple[str, str]] = set()
    certified_action_count = 0
    action_fields = {'name', 'normalized', 'canonical', 'equivalent_originals', 'dispatcher', 'allowed_es', 'python_symbol', 'signature', 'payload_schema', 'g_syntax', 'h_semantics', 'i_semantics', 'minimum_runtime', 'source', 'status', 'reason', 'status_authority'}
    for action in actions:
        if not isinstance(action, dict) or not action_fields <= action.keys():
            raise ExcelContractError('Excel function contract contains a malformed execute action')
        dispatcher = action.get('dispatcher')
        normalized = action.get('normalized')
        if dispatcher not in {'apv', 'client'} or not isinstance(normalized, str) or (not normalized):
            raise ExcelContractError('Excel function contract contains an invalid execute action key')
        key = (dispatcher, normalized)
        if key in action_keys:
            raise ExcelContractError(f'duplicate execute action contract entry: {key!r}')
        action_keys.add(key)
        if action.get('status') not in _STATUS or not isinstance(action.get('reason'), str):
            raise ExcelContractError(f'execute action {key!r} has invalid status/reason')
        if not isinstance(action.get('status_authority'), str) or not action['status_authority']:
            raise ExcelContractError(f'execute action {key!r} has no status authority')
        if not isinstance(action.get('name'), str) or not action['name'] or re.sub('\\s+', '', action['name'].lower()) != normalized or (not isinstance(action.get('canonical'), str)) or (not action['canonical']) or (not isinstance(action.get('equivalent_originals'), list)) or (action['name'] not in action['equivalent_originals']) or any((not isinstance(name, str) or not name for name in action['equivalent_originals'])):
            raise ExcelContractError(f'execute action {key!r} has invalid names')
        allowed_es = action.get('allowed_es')
        if not isinstance(allowed_es, list) or not allowed_es or any((not isinstance(e, str) or e not in object_names for e in allowed_es)) or (len(set(allowed_es)) != len(allowed_es)):
            raise ExcelContractError(f'execute action {key!r} has an invalid E closure')
        candidate_es = action.get('candidate_allowed_es')
        if candidate_es is not None:
            if not isinstance(candidate_es, list) or not candidate_es or any((not isinstance(e, str) or e not in object_names for e in candidate_es)) or (len(set(candidate_es)) != len(candidate_es)) or (not set(allowed_es) <= set(candidate_es)) or (action.get('status') != 'enabled') or (not str(action.get('status_authority') or '').startswith('device_receipt_set:')):
                raise ExcelContractError(f'execute action {key!r} has an invalid certified E projection')
            certified_action_count += 1
        if not isinstance(action.get('python_symbol'), str) or not action['python_symbol']:
            raise ExcelContractError(f'execute action {key!r} has no Python symbol')
        _validate_signature(action.get('signature'), (dispatcher, normalized))
        payload_schema = action.get('payload_schema')
        if not isinstance(payload_schema, dict) or payload_schema.get('status') != 'classified' or (not isinstance(payload_schema.get('required'), bool)) or (payload_schema.get('separator') != '：') or (not isinstance(payload_schema.get('min_length'), int)) or (payload_schema['min_length'] < 0) or (payload_schema['required'] and payload_schema['min_length'] < 1) or (payload_schema.get('cell_mode') != 'unsplit_single_argument') or (not isinstance(payload_schema.get('argument_count'), int)) or (payload_schema['argument_count'] < 0) or (not isinstance(payload_schema.get('split_delimiters'), list)) or any((not isinstance(value, str) for value in payload_schema['split_delimiters'])) or (not isinstance(payload_schema.get('regex_patterns'), list)) or any((not isinstance(value, str) for value in payload_schema['regex_patterns'])):
            raise ExcelContractError(f'execute action {key!r} has an invalid payload schema')
        if not isinstance(action.get('g_syntax'), str) or not action['g_syntax']:
            raise ExcelContractError(f'execute action {key!r} has no G syntax')
        for field in ('h_semantics', 'i_semantics', 'minimum_runtime'):
            if not isinstance(action.get(field), str) or not action[field]:
                raise ExcelContractError(f'execute action {key!r} has no {field}')
        if action['minimum_runtime'] != runtime['minimum_version']:
            raise ExcelContractError(f'execute action {key!r} runtime version does not match the contract')
        source = action.get('source')
        if not isinstance(source, dict) or source.get('path') not in source_paths or (not isinstance(source.get('line'), int)) or (source['line'] < 1):
            raise ExcelContractError(f'execute action {key!r} has invalid source provenance')
    certification = payload.get('certification')
    if certification is not None:
        if not isinstance(certification, dict):
            raise ExcelContractError('Excel certification metadata must be an object')
        required_certification = {'schema', 'basis_contract_sha256', 'basis_contract_file_sha256', 'deployment_receipt_sha256', 'receipt_set_sha256', 'receipt_count'}
        if not required_certification <= certification.keys() or not _accepts_schema(certification.get('schema'), 'ist.excel.capability-certification-set') or any((not isinstance(certification.get(field), str) or not re.fullmatch('[0-9a-f]{64}', certification[field]) for field in ('basis_contract_sha256', 'basis_contract_file_sha256', 'deployment_receipt_sha256', 'receipt_set_sha256'))) or (not isinstance(certification.get('receipt_count'), int)) or (certification['receipt_count'] < 1):
            raise ExcelContractError('Excel certification metadata is incomplete')
        if certified_action_count == 0 and certified_entry_count == 0:
            leaked_authority = any((str(action.get('status_authority') or '').startswith('device_receipt_set:') for action in actions))
            if leaked_authority:
                raise ExcelContractError('certification authority has no certified action')
    elif certified_action_count or certified_entry_count:
        raise ExcelContractError('certified capabilities have no receipt-set metadata')
    stored = payload.get('contract_sha256')
    computed = hashlib.sha256(_canonical_payload(payload)).hexdigest()
    if stored != computed:
        raise ExcelContractError('Excel function contract digest mismatch')
    return ValidatedExcelContract(payload)

def load_excel_contract(path: str | Path | None=None, *, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> ValidatedExcelContract:
    contract_path = Path(path) if path is not None else _DEFAULT_PATH

    def read_payload() -> tuple[Any, _FileIdentity]:
        try:
            raw, identity = _read_bound_file(contract_path, label='Excel function contract', max_bytes=_CONTRACT_MAX_BYTES)
            validate_json_budget(raw, error_type=ExcelContractError, message='Excel function contract exceeds the JSON structure budget')
            return (json.loads(raw.decode('utf-8')), identity)
        except ExcelContractError:
            raise
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            raise ExcelContractError(f'Excel function contract is unavailable: {contract_path}') from exc
    if source_overlays is not None:
        payload, _identity = read_payload()
        return _validate_contract(payload, source_overlays=source_overlays)
    cache_key = str(contract_path.expanduser().absolute())
    with _CONTRACT_CACHE_LOCK:
        contract_identity = _bound_file_identity(contract_path, label='Excel function contract', max_bytes=_CONTRACT_MAX_BYTES)
        cached = _CONTRACT_CACHE.get(cache_key)
        if cached is not None and cached[0] == contract_identity:
            source_paths = tuple((relative for relative, _identity in cached[1]))
            if _source_identities(source_paths) == cached[1]:
                return cached[2]
        for _attempt in range(2):
            payload, read_contract_identity = read_payload()
            raw_sources = payload.get('source_hashes') if isinstance(payload, dict) else None
            source_paths = tuple(sorted(raw_sources)) if isinstance(raw_sources, dict) and all((isinstance(relative, str) for relative in raw_sources)) else ()
            source_bytes, read_sources = _read_source_closure(source_paths) if source_paths else ({}, ())
            validated = _validate_contract(payload, source_overlays=source_bytes)
            after_contract = _bound_file_identity(contract_path, label='Excel function contract', max_bytes=_CONTRACT_MAX_BYTES)
            after_sources = _source_identities(source_paths)
            if read_contract_identity == after_contract and read_sources == after_sources:
                frozen = _freeze_contract(validated)
                if len(_CONTRACT_CACHE) >= _CONTRACT_CACHE_MAX:
                    _CONTRACT_CACHE.pop(next(iter(_CONTRACT_CACHE)))
                _CONTRACT_CACHE[cache_key] = (after_contract, after_sources, frozen)
                return frozen
        raise ExcelContractError('Excel function contract changed while being validated')

def validate_excel_contract(payload: Mapping[str, Any], *, source_overlays: Mapping[str, bytes | bytearray] | None=None) -> ValidatedExcelContract:
    return _validate_contract(dict(payload), source_overlays=source_overlays)

def contract_entry(e: str, f: str, contract: Mapping[str, Any] | None=None) -> Mapping[str, Any] | None:
    if contract is None:
        payload = load_excel_contract()
    elif isinstance(contract, ValidatedExcelContract):
        payload = contract
    else:
        payload = _validate_contract(dict(contract))
    for entry in payload['entries']:
        if entry['e'] == e and entry['f'] == f:
            return entry
    return None

def enabled_fs_by_e(contract: Mapping[str, Any] | None=None) -> dict[str, frozenset[str]]:
    if contract is None:
        payload = load_excel_contract()
    elif isinstance(contract, ValidatedExcelContract):
        payload = contract
    else:
        payload = _validate_contract(dict(contract))
    grouped: dict[str, set[str]] = {item['e']: set() for item in payload['objects']}
    for entry in payload['entries']:
        if entry['status'] == 'enabled':
            grouped[entry['e']].add(entry['f'])
    return {e: frozenset(values) for e, values in grouped.items()}

def _split_parameter_parts(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == '\\':
            current.append(char)
            escaped = True
            continue
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            current.append(char)
            quote = char
            continue
        if char == ',':
            part = ''.join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    if quote is not None:
        raise ExcelContractError('G contains an unclosed quote')
    tail = ''.join(current).strip()
    if tail:
        parts.append(tail)
    return parts

def _unquote_parameter(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] in {'"', "'"} and (text[-1] == text[0]):
        return text[1:-1].strip()
    return text

def _keyword_split(part: str) -> tuple[str, str] | None:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(part):
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == '=':
            key = part[:index].strip()
            if re.fullmatch('[A-Za-z_]\\w*', key):
                return (key, part[index + 1:].strip())
            return None
    return None

def parse_g_arguments(raw: Any, method: str) -> tuple[list[Any], dict[str, Any]]:
    if raw is None or (isinstance(raw, str) and (not raw.strip())):
        return ([], {})
    text = str(raw)
    if method == 'cmd_config' and ('\n' in text or '\r' in text):
        raise ExcelContractError('cmd_config rejects multiline G; use cmds_config')
    if method in {'execute', 'cmds_config'}:
        return ([text], {})
    if '\n' in text or '\r' in text:
        _split_parameter_parts(text)
        return ([text], {})
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    for part in _split_parameter_parts(text):
        keyword = _keyword_split(part)
        if keyword is None:
            args.append(_unquote_parameter(part))
            continue
        key, raw_value = keyword
        if key in kwargs:
            raise ExcelContractError(f'G contains duplicate keyword: {key}')
        value: Any = _unquote_parameter(raw_value)
        if value.isdigit():
            value = int(value)
        kwargs[key] = value
    if method == 'sleep':
        if len(args) != 1 or kwargs:
            raise ExcelContractError('sleep requires exactly one integer argument')
        try:
            args[0] = int(args[0])
        except (TypeError, ValueError) as exc:
            raise ExcelContractError('sleep requires exactly one integer argument') from exc
    return (args, kwargs)

def strip_apv_command_kwargs(raw: Any, method: str) -> str:
    text = str(raw or '')
    if method not in {'cmd', 'cmd_enable', 'cmd_config'}:
        return text
    args, _kwargs = parse_g_arguments(text, method)
    if len(args) != 1 or not isinstance(args[0], str):
        raise ExcelContractError('APV command requires exactly one command string')
    return args[0]

def _bind_contract_signature(signature: Mapping[str, Any], args: list[Any], kwargs: Mapping[str, Any]) -> None:
    parameters = list(signature.get('parameters') or [])
    positional = [item for item in parameters if item.get('kind') in {'positional_only', 'positional_or_keyword'}]
    var_positional = next((item for item in parameters if item.get('kind') == 'var_positional'), None)
    var_keyword = next((item for item in parameters if item.get('kind') == 'var_keyword'), None)
    if len(args) > len(positional) and var_positional is None:
        raise ExcelContractError('G arity supplies too many positional arguments')
    bound = {item['name'] for item in positional[:len(args)]}
    by_name = {item['name']: item for item in parameters}
    for key in kwargs:
        parameter = by_name.get(key)
        if parameter is None:
            if var_keyword is None:
                raise ExcelContractError(f'G supplies unexpected keyword: {key}')
            continue
        if parameter.get('kind') == 'positional_only':
            raise ExcelContractError(f'G supplies positional-only parameter by keyword: {key}')
        if key in bound:
            raise ExcelContractError(f'G supplies parameter more than once: {key}')
        if parameter.get('kind') in {'var_positional', 'var_keyword'}:
            if var_keyword is None:
                raise ExcelContractError(f'G supplies unexpected keyword: {key}')
            continue
        bound.add(key)
    missing = [item['name'] for item in parameters if item.get('required') and item.get('kind') not in {'var_positional', 'var_keyword'} and (item['name'] not in bound)]
    if missing:
        raise ExcelContractError(f"G arity is missing required parameters: {', '.join(missing)}")

def execute_action_name(raw: Any) -> str:
    text = '' if raw is None else str(raw)
    prefix, separator, _action_payload = text.rpartition('：')
    return prefix if separator else text

def validate_execute_action(e: str, raw: Any, contract: Mapping[str, Any] | None=None) -> dict:
    if contract is None:
        payload = load_excel_contract()
    elif isinstance(contract, ValidatedExcelContract):
        payload = contract
    else:
        payload = _validate_contract(dict(contract))
    text = '' if raw is None else str(raw)
    _prefix, separator, action_payload = text.rpartition('：')
    action = execute_action_name(text)
    normalized = re.sub('\\s+', '', action.lower())
    matches = [item for item in payload['execute_actions'] if item['status'] == 'enabled' and e in item['allowed_es'] and (item['normalized'] == normalized)]
    if len(matches) != 1:
        dispatchers = sorted({item['dispatcher'] for item in payload['execute_actions'] if e in item['allowed_es']})
        registry = '/'.join(dispatchers) if dispatchers else 'E-bound'
        raise ExcelContractError(f'execute action {action.strip()!r} is not in the exact enabled {registry} action registry for E={e!r}')
    action_contract = matches[0]
    schema = action_contract['payload_schema']
    required = bool(schema['required'])
    minimum = int(schema['min_length'])
    if required and (not separator or len(action_payload.strip()) < minimum):
        raise ExcelContractError(f'execute action {action.strip()!r} requires a non-empty payload after the full-width separator')
    return action_contract

def validate_g_arguments_for_entry(entry: Mapping[str, Any], raw: Any) -> None:
    args, kwargs = parse_g_arguments(raw, str(entry.get('f') or ''))
    signature = entry.get('signature')
    if not isinstance(signature, Mapping):
        raise ExcelContractError('contract entry has no valid signature')
    _bind_contract_signature(signature, args, kwargs)

def validate_g_for_entry(entry: Mapping[str, Any], raw: Any, contract: Mapping[str, Any] | None=None) -> None:
    if entry.get('status') != 'enabled':
        raise ExcelContractError(f"function {entry.get('e')}::{entry.get('f')} is not enabled")
    dispatch = entry.get('dispatch')
    if dispatch == 'checkpoint_v2_three_argument':
        return
    if dispatch == 'checkpoint_two_argument':
        return
    if dispatch == 'execute_registry':
        validate_execute_action(str(entry.get('e') or ''), raw, contract)
    validate_g_arguments_for_entry(entry, raw)

def _normalized_header(row: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(('' if value is None else str(value).strip() for value in row))

def _defined_name_destinations(workbook: Any) -> list[tuple[str, str]] | None:
    names = getattr(workbook, 'defined_names', None)
    if names is None:
        return None
    try:
        marker = names.get(EXECUTION_SHEET_MARKER)
    except (AttributeError, KeyError):
        marker = None
    if marker is None:
        return None
    try:
        return list(marker.destinations)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ExcelContractError('execution-sheet marker is malformed') from exc

def _unquote_sheet_name(name: str) -> str:
    if len(name) >= 2 and name[0] == name[-1] == "'":
        return name[1:-1].replace("''", "'")
    return name

def resolve_execution_sheet(workbook: Any, *, allow_legacy: bool=True, contract: Mapping[str, Any] | None=None) -> tuple[Any, XlsxLayout]:
    matches: list[tuple[Any, int]] = []
    for worksheet in getattr(workbook, 'worksheets', ()):
        for row_no, row in enumerate(worksheet.iter_rows(min_col=1, max_col=len(EXECUTION_HEADERS), values_only=True), start=1):
            if _normalized_header(row) == EXECUTION_HEADERS:
                matches.append((worksheet, row_no))
    if len(matches) != 1:
        raise ExcelContractError(f'expected exactly one complete A-I execution header, found {len(matches)}')
    worksheet, header_row = matches[0]
    destinations = _defined_name_destinations(workbook)
    markers: list[tuple[Any, int, tuple[Any, ...]]] = []
    for candidate in getattr(workbook, 'worksheets', ()):
        for row_no, row in enumerate(candidate.iter_rows(min_col=1, max_col=3, values_only=True), start=1):
            if row and str(row[0] or '').strip() == CONTRACT_MARKER:
                markers.append((candidate, row_no, tuple(row)))
    if destinations is None and (not markers):
        if not allow_legacy:
            raise ExcelContractError(f'current workbook is missing {EXECUTION_SHEET_MARKER!r} and {CONTRACT_MARKER!r} markers')
    else:
        if destinations is None:
            raise ExcelContractError(f'current workbook is missing {EXECUTION_SHEET_MARKER!r} marker')
        expected_ref = f'$A${header_row}:$I${header_row}'
        normalized = [(_unquote_sheet_name(sheet), ref.upper()) for sheet, ref in destinations]
        if normalized != [(worksheet.title, expected_ref)]:
            raise ExcelContractError(f'{EXECUTION_SHEET_MARKER!r} does not target the unique A-I header')
        if len(markers) != 1:
            raise ExcelContractError(f'expected exactly one {CONTRACT_MARKER!r} identity marker, found {len(markers)}')
        marker_sheet, marker_row, marker_values = markers[0]
        if marker_sheet is not worksheet or marker_row >= header_row:
            raise ExcelContractError(f'{CONTRACT_MARKER!r} must precede the unique A-I header')
        if contract is None:
            active_contract = load_excel_contract()
        elif isinstance(contract, ValidatedExcelContract):
            active_contract = contract
        else:
            active_contract = validate_excel_contract(contract)
        marker_version = str(marker_values[1] or '').strip()
        marker_sha = str(marker_values[2] or '').strip()
        from cex_core.engine.common.schema_identity import accepts_schema
        if not accepts_schema(marker_version, active_contract['runtime']['minimum_version']):
            raise ExcelContractError(f"workbook runtime identity does not match the current contract (workbook {marker_version!r} vs current {active_contract['runtime']['minimum_version']!r})")
        if marker_sha != active_contract['contract_sha256'] and (not allow_legacy):
            raise ExcelContractError(f"workbook contract identity does not match the current contract (workbook sha {marker_sha[:12]}… vs current {active_contract['contract_sha256'][:12]}…)")
    return (worksheet, XlsxLayout(header_row=header_row, data_start=header_row + 1, header_anchor=EXECUTION_HEADERS[0], n_cols=len(EXECUTION_HEADERS)))
__all__ = ['SCHEMA', 'EXECUTION_HEADERS', 'EXECUTION_SHEET_MARKER', 'CONTRACT_MARKER', 'ExcelContractError', 'ValidatedExcelContract', 'load_excel_contract', 'clear_excel_contract_cache', 'validate_excel_contract', 'contract_entry', 'enabled_fs_by_e', 'contract_sha256', 'parse_g_arguments', 'strip_apv_command_kwargs', 'execute_action_name', 'validate_execute_action', 'validate_g_for_entry', 'resolve_execution_sheet', 'validate_workbook_manifest']
